"""The shared street model: one JSON-able description of the network that every generated system is
derived from, plus the metadata export for the game.

`collect(roads_collection)` reads the authored roads (curves + MRS_Road inputs, remembered in
`o["mrs_inputs"]`) and junction objects (their `mrs_junction` metadata) into a StreetModel dict:

  roads[i] = {id, name, points (m, world), length (trimmed), driving_side, lanes_forward, lanes_backward,
              transition {forward_end, backward_end, start, taper}, lane_width, lanes [ {id, dir, type, width,
              offset, continuation} ], shoulders, parking, cycleways {l, r}, sidewalks, median, surface preset,
              seed, trims, clears, locks, lane_paths [ {lane_id, dir, points} ], bike_paths, ped_paths}
  junctions[j] = {id, at, control, approaches [ {road, end, heading, lanes_in, lanes_out} ], crossings,
                  signals, signal_phases}
  validation = [ {level, road|junction, message} ]   (short tapers, tapers near junctions, slopes...)

`export_json(path, model)` writes it; `validate(model)` fills the warnings. Units: metres, world space,
Blender Z-up (the GLB export converts to Y-up; the JSON stays Z-up and says so in `axes`).
"""
import bpy, json, math
from mathutils import Vector
from .nodes import MRS, mod_input_get
from .roads import all_roads, road_widths, road_input, BIKE_KINDS
from .structures import road_sample, road_length

LANE_TYPES = ("drive", "bus", "bike", "parking", "shoulder")


def _lanes(road, w, at_end=False):
    """Lane list with ids, directions and lateral offsets (centre of each lane, right = +)."""
    lw = w["lw"]; med = w["median"] * 0.5
    ww = road_widths(road, at_end=at_end)
    lanes = []
    for side, sgn in (("r", 1.0), ("l", -1.0)):
        n = int(round(ww["lanes_" + side]))
        fwd = (side == "r") == w["rht"]            # the right side carries the forward direction under RHT
        bus = road_input(road, "Bus Lane Forward" if fwd else "Bus Lane Backward")
        for k in range(n):
            lanes.append({"id": "%s_%s%d" % (road.name, side, k), "dir": "forward" if fwd else "backward", "type": "bus" if (bus and k == n - 1) else "drive",
                          "width": lw, "offset": sgn * (med + (k + 0.5) * lw), "index_from_centre": k})
        if ww.get("bike_on_" + side):
            kind = road_input(road, "Bike Right" if side == "r" else "Bike Left")
            lanes.append({"id": "%s_%sbike" % (road.name, side), "dir": "both" if kind == "Two-Way" else ("forward" if fwd else "backward"), "type": "bike", "kind": kind,
                          "width": ww["bike1_" + side] - ww["bike0_" + side], "offset": sgn * (ww["bike0_" + side] + ww["bike1_" + side]) * 0.5})
        pk = road_input(road, "Parking Right" if side == "r" else "Parking Left") or 0.0
        if pk > 0.05:
            lanes.append({"id": "%s_%spark" % (road.name, side), "dir": "none", "type": "parking", "width": pk, "offset": sgn * (ww["half_" + side] - pk * 0.5) if not ww.get("bike_prot_" + side) else sgn * (ww["half_" + side] - pk * 0.5)})
    return lanes


def _paths(road, lanes, step=3.0):
    """Polylines along each lane centre (world, trimmed road), sidewalk centre lines both sides."""
    L = road_length(road)
    stations = [a for a in [k * step for k in range(int(L / step) + 1)]] + [L]
    samples = [(a,) + tuple(road_sample(road, a)) for a in stations]
    w0 = road_widths(road)
    trans = road_input(road, "Transition")
    t0 = road_input(road, "Transition Start") or 0.0; tl = max(road_input(road, "Taper Length") or 1.0, 0.1)
    out = []
    for ln in lanes:
        pts = [[round(c, 3) for c in (p + r * ln["offset"])] for (a, p, t, r) in samples]
        path = dict(ln); path["points"] = pts if ln["dir"] != "backward" else list(reversed(pts))
        out.append(path)
    ped = []
    for side, sgn in (("r", 1.0), ("l", -1.0)):
        sw = w0["swr"] if side == "r" else w0["swl"]
        if sw <= 0.05: continue
        pts = []
        for (a, p, t, r) in samples:
            ww = road_widths(road, at_end=(a > t0 + tl / 2)) if trans else w0
            pts.append([round(c, 3) for c in (p + r * sgn * (ww["half_" + side] + w0["curb"] + sw * 0.5) + Vector((0, 0, w0["h"])))])
        ped.append({"id": "%s_%sped" % (road.name, side), "side": side, "points": pts})
    return out, ped


def collect(roads_col, presets=None):
    model = {"version": 3, "units": "m", "axes": "Z up (Blender); the GLB is Y up", "roads": [], "junctions": [], "validation": []}
    for road in all_roads(roads_col):
        w = road_widths(road)
        L = road_length(road)
        inputs = dict(road.get("mrs_inputs", {}))
        lanes = _lanes(road, w)
        paths, ped = _paths(road, lanes)
        entry = {
            "id": road.name, "name": road.get("mrs_street_name", road.name), "preset": road.get("mrs_preset", "custom"), "length": round(L, 2),
            "points": [[round(c, 3) for c in (road.matrix_world @ bp.co)] for bp in road.data.splines[0].bezier_points] if road.data.splines[0].type == "BEZIER" else [[round(c, 3) for c in (road.matrix_world @ Vector(p.co[:3]))] for p in road.data.splines[0].points],
            "driving_side": "right" if w["rht"] else "left", "lanes_forward": w["lanes_f"], "lanes_backward": w["lanes_b"], "lane_width": w["lw"],
            "transition": {"enabled": bool(road_input(road, "Transition")), "forward_end": road_input(road, "Lanes Forward End"), "backward_end": road_input(road, "Lanes Backward End"),
                           "start": road_input(road, "Transition Start"), "taper": road_input(road, "Taper Length")},
            "shoulder": road_input(road, "Shoulder"), "median": w["median"], "parking": {"l": road_input(road, "Parking Left"), "r": road_input(road, "Parking Right")},
            "cycleways": {s: {"kind": road_input(road, "Bike Right" if s == "r" else "Bike Left"), "width": road_input(road, "Bike Width"), "buffer": road_input(road, "Bike Buffer")} for s in ("l", "r")},
            "sidewalks": {"l": {"on": bool(road_input(road, "Sidewalk Left")), "width": w["swl"], "planting": road_input(road, "Planting Strip Left")},
                          "r": {"on": bool(road_input(road, "Sidewalk Right")), "width": w["swr"], "planting": road_input(road, "Planting Strip Right")}, "curb_height": w["h"]},
            "half_widths": {"l": w["half_l"], "r": w["half_r"]}, "seed": road_input(road, "Prop Seed"),
            "trims": {"start": road_input(road, "Trim Start"), "end": road_input(road, "Trim End")}, "ramps": {"start": bool(road_input(road, "Ramp Start")), "end": bool(road_input(road, "Ramp End"))},
            "lanes": lanes, "lane_paths": paths, "ped_paths": ped,
        }
        model["roads"].append(entry)
    for o in bpy.data.objects:
        m = o.get("mrs_junction")
        if not m or o.name not in [x.name for x in roads_col.all_objects]: continue
        m = dict(m)
        model["junctions"].append({"id": o.name, "type": m.get("type"), "at": list(m.get("at", [])), "z": m.get("z"), "control": m.get("control", "none"), "roads": list(m.get("roads", [])),
                                   "approaches": [dict(a) for a in m.get("approaches", [])], "crossings": [dict(c) for c in m.get("crossings", [])],
                                   "signals": [dict(s) for s in m.get("signals", [])], "signal_phases": [list(p) for p in m.get("signal_phases", [])],
                                   "corner_radius": m.get("corner_radius"), "crossing_style": m.get("crossing")})
    validate(model)
    return model


def validate(model):
    v = model["validation"]
    for r in model["roads"]:
        tr = r["transition"]
        if tr["enabled"]:
            changed = abs((tr["forward_end"] or 0) - r["lanes_forward"]) + abs((tr["backward_end"] or 0) - r["lanes_backward"])
            min_taper = max(15.0, 10.0 * r["lane_width"] * changed)          # ~1:10 taper per lane dropped / added
            if (tr["taper"] or 0) < min_taper:
                v.append({"level": "warning", "road": r["id"], "message": "taper %.0f m is shorter than %.0f m for %d lane change(s)" % (tr["taper"], min_taper, changed)})
            if tr["start"] < r["trims"]["start"] + 12.0 or tr["start"] + tr["taper"] > r["length"] - 12.0:
                v.append({"level": "warning", "road": r["id"], "message": "transition lies within 12 m of a road end / junction"})
        if r["length"] < 12.0: v.append({"level": "info", "road": r["id"], "message": "very short road (%.1f m)" % r["length"]})
    ids = [j["id"] for j in model["junctions"]]
    pts = {j["id"]: Vector(j["at"]) for j in model["junctions"] if j.get("at")}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a in pts and b in pts and (pts[a] - pts[b]).length < 25.0:
                v.append({"level": "warning", "junction": a, "message": "junction %s is only %.0f m away" % (b, (pts[a] - pts[b]).length)})
    return v


def export_json(path, model):
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    def _plain(o):
        if hasattr(o, "to_dict"): return o.to_dict()
        if hasattr(o, "to_list"): return o.to_list()
        if hasattr(o, "__iter__") and not isinstance(o, (str, bytes, dict)): return list(o)
        return str(o)
    with open(path, "w", encoding="utf-8") as f: json.dump(model, f, indent=1, default=_plain)
    return path


def apply(model, roads_col):
    """Push lane / cycleway / sidewalk settings from a (possibly edited) model back to the road modifiers."""
    from .roads import set_road
    by_name = {o.name: o for o in all_roads(roads_col)}
    for r in model["roads"]:
        o = by_name.get(r["id"])
        if o is None: continue
        kw = {"Lanes Forward": r["lanes_forward"], "Lanes Backward": r["lanes_backward"], "Lane Width": r["lane_width"], "Driving Side": "Right" if r["driving_side"] == "right" else "Left",
              "Transition": r["transition"]["enabled"], "Lanes Forward End": r["transition"]["forward_end"], "Lanes Backward End": r["transition"]["backward_end"],
              "Transition Start": r["transition"]["start"], "Taper Length": r["transition"]["taper"], "Shoulder": r["shoulder"], "Median": r["median"],
              "Parking Left": r["parking"]["l"], "Parking Right": r["parking"]["r"], "Bike Left": r["cycleways"]["l"]["kind"], "Bike Right": r["cycleways"]["r"]["kind"],
              "Sidewalk Left": r["sidewalks"]["l"]["on"], "Sidewalk Right": r["sidewalks"]["r"]["on"], "Sidewalk Width Left": r["sidewalks"]["l"]["width"] or 2.0,
              "Sidewalk Width Right": r["sidewalks"]["r"]["width"] or 2.0, "Planting Strip Left": r["sidewalks"]["l"]["planting"], "Planting Strip Right": r["sidewalks"]["r"]["planting"]}
        set_road(o, None, **{k.replace(" ", "_"): v for k, v in kw.items() if v is not None})
