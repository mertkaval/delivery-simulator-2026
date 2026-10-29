"""Validation of built roads and junctions against the rules the tool derives them from. Nothing here is specific
to a city: every expectation is recomputed from the roads' own inputs and the junctions' metadata.

Road checks
  paint_clear     no lane / centre / edge / cycle paint inside a junction's clear zone (Mark Clear Start / End)
  arrow_kind      each lane arrow shows the movements the lane may make (junction.lane_use of the junction's
                  movement code), points in the lane's travel direction and stands beyond the stop line
  arrow_count     one arrow per arriving lane where the road asks for arrows
Junction checks
  end_inputs      the roads' Mark Clear / Turns inputs equal what the junction derived for each approach
  end_marking     each approach's end marking (stop line, STOP, give way, none) is the one its control asks for
  bike_on_zebra   no cycle band (junction) or road paint lies on a pedestrian crossing
  signal_lanes    every multi-lane signalised approach has a mast arm with one head over each arriving lane and a
                  lane-use sign showing that lane's movements
  speed_sign      (validate_speed_signs) every speed-limit sign shows its road's Speed Limit
`validate(roads_col)` -> {"roads", "junctions", "problems": [{object, check, message}], "counts": {check: n}}."""
import bpy, math, json
from mathutils import Vector
from .roads import all_roads, road_input, road_widths
from .structures import centre_line
from . import junction as J

ARROW_OF_CODE = {0: "ArrowStraight", 1: "ArrowLeft", 2: "ArrowStraight", 3: "ArrowStraightLeft", 4: "ArrowRight",
                 5: "ArrowLeftRight", 6: "ArrowStraightRight", 7: "ArrowAll"}      # = road.py arrow_index
PAINT_KINDS = (1, 5, 9)         # marking paint, cycleway colour, bus lane colour (road.py KIND)
CYCLE_SLOT = 6                  # junction material slot of the cycle bands
TOL = 0.05                      # m
HEAD_TOL = 0.35                 # a hanging head within this of its lane centre (m)


def _problem(out, obj, check, msg):
    out.append({"object": obj, "check": check, "message": msg})


_CACHE = {}


def _faces(obj, dg, kinds=None, slots=None):
    """[(centroid, [vertex co], mean along)] of the evaluated mesh's faces with `kind` in kinds / material in slots
    (cached for one validate() run: junctions look at their roads again)."""
    key = (obj.name, kinds, slots)
    if key in _CACHE: return _CACHE[key]
    _CACHE[key] = out = _faces_eval(obj, dg, kinds, slots)
    return out


def _faces_eval(obj, dg, kinds, slots):
    ev = obj.evaluated_get(dg); me = ev.to_mesh(); M = obj.matrix_world; out = []
    try:
        kind = me.attributes.get("kind"); along = me.attributes.get("along")
        kv = [d.value for d in kind.data] if kind is not None and kind.domain == "FACE" else None
        av = [d.value for d in along.data] if along is not None and along.domain == "POINT" else None
        for p in me.polygons:
            if kinds is not None and (kv is None or int(round(kv[p.index])) not in kinds): continue
            if slots is not None and p.material_index not in slots: continue
            vs = [M @ me.vertices[i].co for i in p.vertices]
            c = sum(vs, Vector()) / len(vs)
            a = sum(av[i] for i in p.vertices) / len(p.vertices) if av is not None else None
            out.append((c, vs, a))
    finally:
        ev.to_mesh_clear()
    return out


def _instances(dg):
    """{parent object name: [(instanced object name, world matrix)]} of every geometry-nodes instance."""
    out = {}
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None: continue
        out.setdefault(inst.parent.original.name, []).append((inst.object.original.name, inst.matrix_world.copy()))
    return out


def _station(road, p):
    """(along, lateral (right +), unit tangent) of plan point p on the road's evaluated centre line."""
    cl = centre_line(road); best = None
    for (a0, p0), (a1, p1) in zip(cl, cl[1:]):
        d = Vector((p1.x - p0.x, p1.y - p0.y)); L2 = d.length_squared
        if L2 < 1e-12: continue
        f = max(0.0, min(1.0, Vector((p.x - p0.x, p.y - p0.y)).dot(d) / L2))
        q = Vector((p0.x, p0.y)) + d * f; dd = (Vector((p.x, p.y)) - q).length
        if best is None or dd < best[0]:
            t = d.normalized(); r = Vector((t.y, -t.x))
            best = (dd, a0 + (a1 - a0) * f, (Vector((p.x, p.y)) - q).dot(r), t)
    return best[1], best[2], best[3]


def _in_crossing(c, x):
    """Plan point x inside crossing record c (centre line from -> to, width c['width'])."""
    a = Vector(c["from"][:2]); b = Vector(c["to"][:2]); d = b - a; L = d.length
    if L < 1e-6: return False
    u = d / L; v = Vector((x.x, x.y)) - a; t = v.dot(u)
    return -TOL <= t <= L + TOL and abs(v.x * u.y - v.y * u.x) < c["width"] * 0.5 - TOL


def check_road(r, dg, inst, out):
    L = centre_line(r)[-1][0]
    mcs = road_input(r, "Mark Clear Start") or 0.0; mce = road_input(r, "Mark Clear End") or 0.0
    bad_s = bad_e = 0
    for c, vs, a in _faces(r, dg, kinds=PAINT_KINDS):
        if a is None: continue
        if a < mcs - TOL: bad_s += 1
        elif a > L - mce + TOL: bad_e += 1
    if bad_s: _problem(out, r.name, "paint_clear", "%d paint faces inside the start clear zone (%.1f m)" % (bad_s, mcs))
    if bad_e: _problem(out, r.name, "paint_clear", "%d paint faces inside the end clear zone (%.1f m)" % (bad_e, mce))
    # lane arrows
    rht = (road_input(r, "Driving Side") or "Right") == "Right"
    med = (road_input(r, "Median") or 0.0) * 0.5; lw = road_input(r, "Lane Width") or 3.0
    seen = {True: 0, False: 0}
    for name, M in inst.get(r.name, []):
        if not name.startswith("MRS_Arrow") or "Merge" in name: continue
        p = M.translation; a, lat, t = _station(r, p)
        at_end = a > L * 0.5
        travel = t if at_end else -t
        fwd = Vector((M.col[1].x, M.col[1].y)).normalized()
        if fwd.dot(travel) < 0.9: _problem(out, r.name, "arrow_kind", "%s at %.1f m points against the traffic" % (name, a))
        arriving_right = rht if at_end else not rht
        if (lat > 0) != arriving_right: _problem(out, r.name, "arrow_kind", "%s at %.1f m stands in a leaving lane" % (name, a))
        w = road_widths(r, at_end=at_end)
        n = int(round(w["lanes_r"] if arriving_right else w["lanes_l"]))
        k = max(0, min(n - 1, int((abs(lat) - med) / lw)))
        turns = int(road_input(r, "Turns End" if at_end else "Turns Start") or 0)
        want = "MRS_" + ARROW_OF_CODE[J.lane_use(turns, n, rht)[k] if n else 0]
        if name.split(".")[0] != want: _problem(out, r.name, "arrow_kind", "%s in lane %d at %.1f m: the lane may make %s" % (name, k, a, want))
        clear = mce if at_end else mcs
        if (L - a if at_end else a) < clear + 1.0: _problem(out, r.name, "arrow_kind", "%s at %.1f m is inside the junction's clear zone" % (name, a))
        seen[at_end] += 1
    if road_input(r, "Lane Arrows"):
        dist = road_input(r, "Arrow Distance") or 9.0; min_l = road_input(r, "Arrow Min Lanes") or 2
        for at_end in (True, False):
            trim = road_input(r, "Trim End" if at_end else "Trim Start") or 0.0
            turns = int(road_input(r, "Turns End" if at_end else "Turns Start") or 0)
            clear = mce if at_end else mcs
            w = road_widths(r, at_end=at_end); arr_r = rht if at_end else not rht
            n = int(round(w["lanes_r"] if arr_r else w["lanes_l"]))
            want = n if (trim > 0.5 and turns > 0 and n >= min_l and L > 2 * (clear + dist)) else 0
            if seen[at_end] != want: _problem(out, r.name, "arrow_count", "%d arrows at the %s, %d arriving lanes want them" % (seen[at_end], "end" if at_end else "start", want))


def check_junction(o, dg, out, roads_by_name):
    meta = o["mrs_junction"]; meta = meta.to_dict() if hasattr(meta, "to_dict") else dict(meta)
    if meta.get("type", "junction") != "junction": return
    aps = meta.get("approaches", [])
    for ap in aps:
        r = roads_by_name.get(ap["road"])
        if r is None or "mark_clear" not in ap: continue
        sfx = "Start" if ap["end"] == "start" else "End"
        mc = road_input(r, "Mark Clear " + sfx); tu = road_input(r, "Turns " + sfx)
        if mc is None or abs(mc - ap["mark_clear"]) > 1e-3: _problem(out, o.name, "end_inputs", "%s Mark Clear %s = %s, junction derived %.2f" % (r.name, sfx, mc, ap["mark_clear"]))
        if tu is None or int(tu) != int(ap["turns"]): _problem(out, o.name, "end_inputs", "%s Turns %s = %s, junction derived %d" % (r.name, sfx, tu, ap["turns"]))
    # end markings follow the junction's control (signals: line, stop: line + STOP, give way on yield / minor roads)
    for ap in aps:
        if "marking" not in ap: continue
        want = J.end_marking(meta.get("control"), ap["road"] in set(meta.get("main_roads", [])), ap.get("lanes_in", 0)) if meta.get("stop_lines", True) else None
        if ap["marking"] != want: _problem(out, o.name, "end_marking", "%s: %s painted, the %s control wants %s" % (ap["road"], ap["marking"], meta.get("control"), want))
    crossings = []
    for c in meta.get("crossings", []):
        c = dict(c); c["width"] = meta.get("crossing_width", 2.5); crossings.append(c)
    if crossings:
        hits = 0
        for c_, vs, _a in _faces(o, dg, slots=(CYCLE_SLOT,)):
            pts = [c_] + [c_.lerp(v, 0.9) for v in vs]
            if any(_in_crossing(c, x) for c in crossings for x in pts): hits += 1
        if hits: _problem(out, o.name, "bike_on_zebra", "%d cycle-band faces on a pedestrian crossing" % hits)
        for ap in aps:
            r = roads_by_name.get(ap["road"])
            if r is None: continue
            hits = sum(1 for c_, vs, _a in _faces(r, dg, kinds=PAINT_KINDS) if (c_ - Vector(meta["at"])).length < 60.0 and any(_in_crossing(c, c_) for c in crossings))
            if hits: _problem(out, o.name, "bike_on_zebra", "%s: %d paint faces on a pedestrian crossing" % (r.name, hits))
    if meta.get("control") == "signals" and len(aps) >= 3:
        sigs = meta.get("signals", [])
        for ai, ap in enumerate(aps):
            r = roads_by_name.get(ap["road"])
            n_in = int(round(ap.get("lanes_in", 0)))
            if r is None or n_in < J.ARM_LANES or "end_point" not in ap: continue
            w = road_widths(r, at_end=ap["end"] != "start")
            rht = w["rht"]; in_r = -1.0 if rht else 1.0
            sw_in = (w["swl"] if in_r < 0 else w["swr"]) if ap["end"] == "start" else (w["swr"] if in_r < 0 else w["swl"])
            if sw_in < J.ARM_POLE[1] + 0.3: continue
            arm = next((s for s in sigs if s.get("approach") == ai and s.get("kind") == "mast_arm"), None)
            if arm is None: _problem(out, o.name, "signal_lanes", "%s: %d arriving lanes but no mast arm" % (r.name, n_in)); continue
            pole = bpy.data.objects.get(arm["id"])
            heads = [ch for ch in (pole.children if pole else []) if ch.get("mrs_signal_head") and dict(ch["mrs_signal_head"]).get("kind") == "vehicle"]
            if len(heads) != n_in: _problem(out, o.name, "signal_lanes", "%s: %d vehicle heads over %d lanes" % (r.name, len(heads), n_in)); continue
            signs = sorted([c for c in pole.children if c.get("mrs_lane_use") is not None], key=lambda c: c.name)
            want = J.lane_use(int(ap.get("turns", 7)), n_in, rht)
            if [int(c["mrs_lane_use"]) for c in signs] != want:
                _problem(out, o.name, "signal_lanes", "%s: lane-use signs %s, the lanes may make %s" % (r.name, [int(c["mrs_lane_use"]) for c in signs], want))
            E = Vector(ap["end_point"]); R = Vector(ap["right"])
            centres = [in_r * (w["median"] * 0.5 + (k + 0.5) * w["lw"]) for k in range(n_in)]
            for h in heads:
                lat = (h.matrix_world.translation - E).to_2d().dot(R.to_2d())
                off = min(abs(lat - c) for c in centres)
                if off > HEAD_TOL: _problem(out, o.name, "signal_lanes", "%s: head %s is %.2f m off its lane centre" % (r.name, h.name, off))


def validate_speed_signs(objects, out):
    """Every placed speed-limit sign shows its road's Speed Limit."""
    n = 0
    for o in objects:
        if o.get("mrs_kind") != "sign_speed": continue
        r = bpy.data.objects.get(o.get("mrs_road", ""))
        if r is None: continue
        n += 1
        want = "MRS_Sign_Speed%d" % int(road_input(r, "Speed Limit") or 0)
        if o.get("mrs_placed") != want: _problem(out, o.name, "speed_sign", "shows %s on %s (Speed Limit %s)" % (o.get("mrs_placed"), r.name, want))
    return n


def driveway_at(road, station, tol=1.0):
    """True when the road has a driveway (dropped kerb) within `tol` m of `station`."""
    lst = json.loads(road.get("mrs_driveways", "[]") or "[]")
    return any(abs(a - station) <= tol for a, s, w in lst)


def validate(roads_col, placed=None, log=print):
    from .nodes import depsgraph
    _CACHE.clear()
    dg = depsgraph(); inst = _instances(dg)
    rs = all_roads(roads_col); by_name = {r.name: r for r in rs}
    out = []
    for r in rs: check_road(r, dg, inst, out)
    js = [o for o in roads_col.all_objects if o.get("mrs_junction") and o.type == "MESH"]
    for o in js: check_junction(o, dg, out, by_name)
    n_signs = validate_speed_signs(placed.all_objects if placed else bpy.data.objects, out)
    counts = {}
    for p in out: counts[p["check"]] = counts.get(p["check"], 0) + 1
    rep = {"roads": len(rs), "junctions": len(js), "speed_signs": n_signs, "problems": out, "counts": counts}
    log("VALIDATE roads %d junctions %d speed signs %d problems %d %s" % (len(rs), len(js), n_signs, len(out), json.dumps(counts)))
    return rep
