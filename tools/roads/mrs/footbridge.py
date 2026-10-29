"""Procedural pedestrian footbridge: a Python connection solver + the editable `Footbridge` Geometry
Nodes group.

Placement is explicit: an anchor empty `MRS_FootbridgeAnchor_<name>` next to a road (moved by the user
or by a route-demand rule) defines the crossing station; its custom property `mrs_footbridge` (JSON)
holds the solver parameters. `rebuild(name)` re-solves and rewrites the bridge in place (same object,
same mesh datablock, light children replaced), so regeneration never multiplies objects.

Solver (`solve`), all lengths in metres:
  * the main span crosses the road square to the centre line at the anchor station, from a head landing
    on one landside (behind the back of the sidewalk + `landside_gap`) to the other;
  * walking level = highest road surface under the span + `clearance` + structure depth of the style
    (Girder 1.05, Truss 0.55, Box 1.3), so the soffit keeps the clearance;
  * intermediate span supports only in allowed regions (median, planting strip / verge) when the span
    exceeds `max_span`; never in lanes, cycleways, sidewalks or crossings - otherwise reported;
  * each end gets its approaches (stairs and/or ramp) running parallel to the road behind the sidewalk;
    a ramp is split into runs of at most `ramp_max_rise` at `ramp_max_slope` with `ramp_landing`
    landings, stairs into flights of at most `stair_max_risers` risers with landings; legs switch back
    (k = 1..6 legs, 180-degree turn platforms) until the footprint fits the available length along the
    road and depth behind the sidewalk; when nothing fits, the approach is NOT generated and the reason
    is reported (a 1:12 ramp for 6 m of rise needs ~85 m of runs and landings);
  * the foot of every approach is connected to the sidewalk by a paved path (with a headroom check where
    it passes under the structure);
  * columns under head landings, turn platforms and along legs every <= `support_spacing`.

Skeleton -> geometry: the solver writes a mesh of edge chains (object `<name>`, mesh `<name>_skeleton`)
with point attributes `part` (0 walk slab, 1 stair flight, 2 column, 3 rail guide, 5 span rail guide),
`side` (mitred horizontal right vector), `width`, `depth`, `kind` (0 span 1 ramp 2 landing 3 stair 4 path
5 column), `fwd` (stair ascent direction), `going`, `rise`, `top`, `foot`. The `MRS_Footbridge` modifier
(group `Footbridge`) builds the deck / beams (style profile), stairs (steps on stringers), railings
(posts, handrail, infill, kick plate), truss (Truss style), columns with footings and crossheads,
handrail LEDs, UVs in metres, materials and an optional collision-only output.
"""
import bpy, bmesh, math, json
from mathutils import Vector
from .nodes import T, new_tree, add_inputs, sock, MRS, mod_input_set, mod_input_get, depsgraph
from .roads import road_widths, road_input, all_roads
from .structures import road_sample, road_length, surface_z

GROUP = "Footbridge"
MOD = "MRS_Footbridge"
STYLES = ("Girder", "Truss", "Box")
STYLE_DEPTH = {"Girder": 1.05, "Truss": 0.55, "Box": 1.3}
DEFAULTS = {
    "road": None, "width": 3.0, "clearance": 5.3, "style": "Girder", "landside_gap": 0.6, "landside_depth": 16.0,
    "max_span": 42.0, "support_spacing": 9.0, "column_clear": 0.5,
    "stair_rise_max": 0.165, "stair_going": 0.30, "stair_max_risers": 12, "stair_landing": 1.5,
    "ramp_max_slope": 1.0 / 12.0, "ramp_max_rise": 0.75, "ramp_landing": 1.6, "leg_gap": 0.5, "max_legs": 6,
    "approach_depth": 0.42, "path_depth": 0.30, "min_headroom": 2.3,
    # approaches per end: list of {type: stairs|ramp, dir: +1 (with the road direction) | -1, switchback: auto|none}
    # dir: +1 / -1 along the road, "long" / "short" = the side of the anchor with more / less free length
    "ends": {"l": [{"type": "stairs", "dir": "short", "switchback": "auto"}, {"type": "ramp", "dir": "long", "switchback": "auto"}],
             "r": [{"type": "stairs", "dir": "short", "switchback": "auto"}, {"type": "ramp", "dir": "long", "switchback": "auto"}]},
    "along_clear": 18.0,       # keep approaches this far from the road ends (junction zones)
    "lights": True, "light_spacing": 9.0,
}
KIND = {"span": 0, "ramp": 1, "landing": 2, "stair": 3, "path": 4, "column": 5}


# ============================================================================ solver
class Frame:
    """Local frame at the anchor: u along the road tangent, v to the right, z up (world metres)."""
    def __init__(self, p, t, r):
        self.o = Vector((p.x, p.y, 0.0)); self.t = Vector((t.x, t.y, 0.0)).normalized(); self.r = Vector((r.x, r.y, 0.0)).normalized()
    def w(self, u, v, z): return self.o + self.t * u + self.r * v + Vector((0, 0, z))
    def dir_w(self, du, dv): return (self.t * du + self.r * dv)


def _mitred_sides(pts):
    """Right-hand horizontal side vectors for a polyline, mitred at corners (length 1/cos(half angle))."""
    n = len(pts); out = []
    segs = []
    for i in range(n - 1):
        d = Vector((pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y, 0.0))
        segs.append(d.normalized() if d.length > 1e-6 else None)
    # fill degenerate (vertical) segments with neighbours
    for i in range(len(segs)):
        if segs[i] is None:
            segs[i] = next((segs[j] for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(segs))) if segs[j] is not None), Vector((1, 0, 0)))
    side = lambda d: Vector((d.y, -d.x, 0.0))          # right of travel
    for i in range(n):
        if i == 0: out.append(side(segs[0]))
        elif i == n - 1: out.append(side(segs[-1]))
        else:
            s1, s2 = side(segs[i - 1]), side(segs[i])
            m = s1 + s2
            if m.length < 1e-6: out.append(s1)
            else:
                m.normalize(); c = max(m.dot(s1), 0.2); out.append(m / c)
    return out


def _runs(H, max_rise):
    n = max(1, math.ceil(H / max_rise - 1e-6)); return n, H / n


def _split(n, k):
    """n items into k groups as evenly as possible (first groups larger)."""
    base, extra = divmod(n, k); return [base + (1 if i < extra else 0) for i in range(k)]


def plan_approach(kind, H, cfg, avail_len, avail_depth, W):
    """Solve one approach (stairs or ramp) of rise H. Returns dict(ok, legs=[[segments]], length, depth,
    message). A segment = (type, horizontal length, rise) with type in run|landing|flight."""
    if H <= 0.05: return {"ok": True, "legs": [], "length": 0.0, "depth": 0.0, "message": "no rise"}
    if kind == "ramp":
        n, rr = _runs(H, cfg["ramp_max_rise"]); run_len = rr / cfg["ramp_max_slope"]; Ll = cfg["ramp_landing"]
        units = [("run", run_len, rr)] * n; sep = ("landing", Ll, 0.0)
        desc = "%d runs of %.2f m rise / %.1f m at 1:%.0f" % (n, rr, run_len, 1.0 / cfg["ramp_max_slope"])
    else:
        n, r = _runs(H, cfg["stair_rise_max"]); g = cfg["stair_going"]
        f = max(1, math.ceil(n / cfg["stair_max_risers"])); per = _split(n, f)
        units = [("flight", m * g, m * r, m) for m in per]; sep = ("landing", cfg["stair_landing"], 0.0)
        desc = "%d risers of %.3f m (going %.2f m) in %d flights" % (n, r, g, f)
    kmax = int(cfg["max_legs"]) if cfg.get("switchback", "auto") != "none" else 1
    best = None
    for k in range(1, kmax + 1):
        if k > len(units): break
        groups = _split(len(units), k); legs = []; i = 0
        for m in groups:
            leg = []
            for j in range(m):
                if j: leg.append(sep)
                leg.append(units[i]); i += 1
            legs.append(leg)
        leg_lens = [sum(s[1] for s in leg) for leg in legs]
        length = max(leg_lens) + (W if k > 1 else 0.0)
        depth = k * W + (k - 1) * cfg["leg_gap"]
        cand = {"ok": length <= avail_len and depth <= avail_depth, "legs": legs, "length": length, "depth": depth, "k": k, "desc": desc}
        if cand["ok"]:
            cand["message"] = "%s: %d leg(s), footprint %.1f m along x %.1f m deep" % (desc, k, length, depth); return cand
        if best is None or (length - avail_len) < (best["length"] - avail_len): best = cand
    best = best or {"legs": [], "length": 0, "depth": 0}
    best["ok"] = False
    best["message"] = "%s does not fit: needs %.1f m along x %.1f m deep (%d legs), available %.1f m x %.1f m" % (
        desc, best["length"], best["depth"], best.get("k", 1), avail_len, avail_depth)
    return best


def widths_at(road, along):
    """road_widths at a station: the end layout after a completed lane transition, the wider of both inside the taper."""
    w0 = road_widths(road)
    if not road_input(road, "Transition"): return w0
    a0 = road_input(road, "Transition Start") or 0.0; tl = road_input(road, "Taper Length") or 0.0
    w1 = road_widths(road, at_end=True)
    if along >= a0 + tl: return w1
    if along <= a0: return w0
    out = dict(w0)
    for k in ("half_l", "half_r", "half", "carr_l", "carr_r", "bike0_l", "bike1_l", "bike0_r", "bike1_r"):
        if k in w1: out[k] = max(w0[k], w1[k])
    return out


def _road_surface_z(road, a, w, step=1.0):
    p, t, r = road_sample(road, a)
    return p.z + 0.08                      # crown / camber allowance at the centre


def _allowed_support_regions(w, road):
    """Lateral intervals (v, signed, right +) where an intermediate column may stand (with clearance)."""
    regs = []
    if w["median"] >= 0.45 + 2 * 0.5: regs.append((-w["median"] / 2 + 0.5, w["median"] / 2 - 0.5, "median"))
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        strip = road_input(road, "Planting Strip Right" if s == "r" else "Planting Strip Left") or 0.0
        if strip >= 0.45 + 0.6:
            a = w["half_" + s] + w["curb"]; b = a + strip
            regs.append((min(sgn * (a + 0.3), sgn * (b - 0.3)), max(sgn * (a + 0.3), sgn * (b - 0.3)), "verge " + s))
    return regs


def solve(road, along, cfg):
    """Full plan for one bridge at `along` on `road`. Returns a JSON-able dict incl. chains to draw."""
    W = cfg["width"]; msgs = []; ok = True
    w = widths_at(road, along); L = road_length(road)
    a_min = cfg["along_clear"]; a_max = L - cfg["along_clear"]
    long_dir = 1 if (a_max - along) >= (along - a_min) else -1
    ends_cfg = {}
    for end, aps in cfg["ends"].items():
        ends_cfg[end] = []
        for ap in aps:
            ap = dict(ap); d = ap.get("dir", "long")
            ap["dir"] = long_dir if d == "long" else (-long_dir if d == "short" else (1 if float(d) > 0 else -1))
            ends_cfg[end].append(ap)
    p, t, r = road_sample(road, along); F = Frame(p, t, r)
    lats = [-w["half_l"] + 0.25 * i for i in range(int((w["half_l"] + w["half_r"]) / 0.25) + 1)]
    z_road = max(max(surface_z(road, a2, la) for la in lats) for a2 in (along - W / 2, along, along + W / 2))
    back0 = {"l": w["half_l"] + w["curb"] + w["swl"], "r": w["half_r"] + w["curb"] + w["swr"]}
    z_side = {"l": surface_z(road, along, -(back0["l"] - 0.3)), "r": surface_z(road, along, back0["r"] - 0.3)}
    z_walk_ground = min(z_side.values())                       # sidewalk top (lower side: the larger rise)
    depth_span = STYLE_DEPTH.get(cfg["style"], 1.05)
    z_deck = z_road + cfg["clearance"] + depth_span
    H = z_deck - z_walk_ground
    back = {"l": w["half_l"] + w["curb"] + w["swl"], "r": w["half_r"] + w["curb"] + w["swr"]}
    v_e = {"l": -(back["l"] + cfg["landside_gap"] + W / 2), "r": back["r"] + cfg["landside_gap"] + W / 2}
    span_len = v_e["r"] - v_e["l"]
    plan = {"version": 1, "road": road.name, "along": round(along, 2), "width": W, "style": cfg["style"], "deck_z": round(z_deck, 3),
            "rise": round(H, 3), "clearance_req": cfg["clearance"], "span": round(span_len, 2), "chains": [], "supports": [], "ped_edges": [],
            "footprint": [], "messages": msgs, "lights": []}
    # ---- span supports
    supports_v = [v_e["l"], v_e["r"]]
    if span_len > cfg["max_span"]:
        regs = _allowed_support_regions(w, road)
        cur = v_e["l"]; mids = []
        while v_e["r"] - cur > cfg["max_span"]:
            cand = [((a + b) / 2, why) for a, b, why in regs if cur + 4.0 < (a + b) / 2 <= cur + cfg["max_span"]]
            if not cand:
                msgs.append("span %.1f m exceeds max span %.1f m and no allowed support region (median >= 1.45 m or verge) lies within reach; "
                            "use the Truss style or a longer max span" % (span_len, cfg["max_span"])); ok = False; break
            v, why = max(cand); mids.append((v, why)); cur = v
        for v, why in mids: supports_v.append(v); msgs.append("intermediate span support in the %s at v=%.2f m" % (why, v))
    # ---- chains: span slab + span rail guides (openings where approaches leave the head landings)
    def chain(part, pts, kind, width=W, depth=0.4, extra=None):
        sides = _mitred_sides(pts)
        rec = {"part": part, "kind": kind, "pts": [list(map(float, q)) for q in pts], "side": [list(map(float, s)) for s in sides], "width": width, "depth": depth}
        if extra: rec.update(extra)
        plan["chains"].append(rec); return rec
    span_pts = [F.w(0, v_e["l"] - W / 2, z_deck), F.w(0, v_e["r"] + W / 2, z_deck)]
    nseg = max(2, int(span_len / 2.0))
    span_pts = [span_pts[0].lerp(span_pts[1], i / nseg) for i in range(nseg + 1)]
    chain(0, span_pts, KIND["span"], depth=depth_span)
    plan["footprint"].append({"kind": "span", "poly": [list(F.w(u, v, 0))[:2] for u, v in ((-W / 2, v_e["l"] - W / 2), (W / 2, v_e["l"] - W / 2), (W / 2, v_e["r"] + W / 2), (-W / 2, v_e["r"] + W / 2))], "z_min": z_deck - depth_span})
    inset = 0.06
    openings = {+1: [], -1: []}                                 # side (u sign) -> list of v intervals
    for end in ("l", "r"):
        for ap in ends_cfg.get(end, []):
            openings[1 if ap["dir"] > 0 else -1].append((v_e[end] - W / 2 + inset, v_e[end] + W / 2 - inset))
    for us in (+1, -1):
        u = us * (W / 2 - inset); v0 = v_e["l"] - W / 2 + inset; v1 = v_e["r"] + W / 2 - inset
        cuts = sorted(openings[us]); segs = []; cur = v0
        for a, b in cuts:
            if a > cur + 0.05: segs.append((cur, a))
            cur = max(cur, b)
        if v1 > cur + 0.05: segs.append((cur, v1))
        for a, b in segs:
            k = max(1, int((b - a) / 2.0))
            chain(5, [F.w(u, a + (b - a) * i / k, z_deck) for i in range(k + 1)], KIND["span"], depth=depth_span)
    for end in ("l", "r"):                                      # rail across the outer end of each head landing
        v = v_e[end] + (W / 2 - inset) * (1 if end == "r" else -1)
        chain(3, [F.w(-(W / 2 - inset), v, z_deck), F.w(W / 2 - inset, v, z_deck)], KIND["landing"], depth=depth_span)
    # columns under the head landings and intermediate span supports
    def column(u, v, ztop, side, why):
        g = z_side["r" if v > 0 else "l"] if abs(v) >= min(back.values()) else surface_z(road, along, v)
        top = F.w(u, v, ztop); bot = F.w(u, v, g)
        # validity: never in carriageway / cycleway / sidewalk walking zone
        lat = v; region = "landside"
        for s, sg in (("r", 1), ("l", -1)):
            if sg * lat > 0:
                half = w["half_" + s]; bk = back[s]
                if abs(lat) < bk + 0.25:
                    region = "road"
                    for a, b, why2 in _allowed_support_regions(w, road):
                        if a <= lat <= b: region = why2
        valid = region != "road"
        plan["supports"].append({"pos": [round(c, 3) for c in bot], "top": round(ztop, 3), "region": region, "valid": valid, "why": why})
        if not valid: msgs.append("support at v=%.2f m would stand in the road / sidewalk: skipped" % v); return
        chain(2, [top, bot], KIND["column"], width=W, depth=0.0, extra={"side_fixed": list(F.dir_w(0, 1))})
    for v in supports_v:
        is_end = v in (v_e["l"], v_e["r"])
        for u in ((-(W / 2 - 0.45), W / 2 - 0.45) if True else (0.0,)):
            column(u, v, z_deck - depth_span, None, "head landing" if is_end else "span support")
    # ---- approaches
    for end in ("l", "r"):
        sgn = 1.0 if end == "r" else -1.0
        for ap in ends_cfg.get(end, []):
            d = 1 if ap["dir"] > 0 else -1
            avail_len = ((a_max - along) if d > 0 else (along - a_min)) - W / 2
            res = plan_approach(ap["type"], z_deck - z_side[end], dict(cfg, switchback=ap.get("switchback", "auto")), avail_len, cfg["landside_depth"], W)
            tag = "%s %s %s" % (end, ap["type"], "+u" if d > 0 else "-u")
            if not res["ok"]:
                msgs.append("%s: %s" % (tag, res["message"])); ok = False if ap.get("required", True) else ok; continue
            msgs.append("%s: %s" % (tag, res["message"]))
            _build_approach(plan, F, chain, column, ap["type"], res, end, sgn, d, v_e[end], z_deck, z_side[end], back[end], W, cfg, tag)
    plan["ok"] = ok
    plan["status"] = "ok" if ok else "incomplete"
    # vertical clearance actually provided over the carriageway
    plan["clearance"] = round(z_deck - depth_span - z_road, 3)
    if plan["clearance"] < cfg["clearance"] - 1e-3: msgs.append("clearance %.2f m < required %.2f m" % (plan["clearance"], cfg["clearance"]))
    return plan


def _build_approach(plan, F, chain, column, kind, res, end, sgn, d, v_line, z_top, z_ground, back, W, cfg, tag):
    """Lay out the legs of one solved approach in the local frame and emit its chains."""
    gap = cfg["leg_gap"]; inset = 0.06
    u = d * W / 2                         # start at the head landing edge
    v = v_line; z = z_top
    centre = [F.w(u, v, z)]; kinds = [KIND["landing"]]
    slab_chains = []                       # (part, pts, kind)
    cur_slab = [F.w(u, v, z)]; cur_kinds = []
    dirn = d
    flights = []
    max_u = abs(u)
    for li, leg in enumerate(res["legs"]):
        for seg in leg:
            typ, length, rise = seg[0], seg[1], seg[2]
            u2 = u + dirn * length; z2 = z - rise
            if typ == "flight":
                # close the current slab chain, add the flight as its own chain (bottom -> top)
                if len(cur_slab) > 1: slab_chains.append((0, cur_slab, cur_kinds))
                m = seg[3]; pts = [F.w(u2 - dirn * (length * i / m), v, z2 + rise * i / m) for i in range(m + 1)]
                flights.append({"pts": pts, "fwd": list(F.dir_w(-dirn, 0)), "going": length / m, "rise": rise / m, "n": m})
                cur_slab = [F.w(u2, v, z2)]; cur_kinds = []
                centre.append(F.w(u2, v, z2)); kinds.append(KIND["stair"])
            else:
                n = 1 if typ == "landing" else max(1, int(length / 2.5))
                for i in range(1, n + 1):
                    q = F.w(u + dirn * length * i / n, v, z - rise * i / n); cur_slab.append(q); cur_kinds.append(KIND["ramp"] if typ == "run" else KIND["landing"])
                    centre.append(q); kinds.append(KIND["ramp"] if typ == "run" else KIND["landing"])
            u, z = u2, z2; max_u = max(max_u, abs(u))
        if li < len(res["legs"]) - 1:
            # 180-degree turn platform: continue W/2, cross to the next leg line, come back W/2
            v_next = v + sgn * (W + gap)
            for q in (F.w(u + dirn * W / 2, v, z), F.w(u + dirn * W / 2, v_next, z), F.w(u, v_next, z)):
                cur_slab.append(q); cur_kinds.append(KIND["landing"]); centre.append(q); kinds.append(KIND["landing"])
            column(u + dirn * W / 2, v, z - cfg["approach_depth"], None, "turn platform") if z - z_ground > 1.0 else None
            column(u + dirn * W / 2, v_next, z - cfg["approach_depth"], None, "turn platform") if z - z_ground > 1.0 else None
            max_u = max(max_u, abs(u + dirn * W))
            v = v_next; dirn = -dirn
    if len(cur_slab) > 1: slab_chains.append((0, cur_slab, cur_kinds))
    for part, pts, ks in slab_chains:
        chain(part, pts, ks[0] if ks else KIND["landing"], depth=cfg["approach_depth"])
    for fl in flights:
        chain(1, fl["pts"], KIND["stair"], depth=cfg["approach_depth"], extra={"fwd": fl["fwd"], "going": fl["going"], "rise": fl["rise"]})
    # rails: offsets of the centre path (mitred), both sides
    sides = _mitred_sides(centre)
    for s in (+1, -1):
        rail = [c + sd * s * (W / 2 - inset) for c, sd in zip(centre, sides)]
        chain(3, rail, KIND["ramp"], depth=cfg["approach_depth"])
    # columns along the legs (skip low parts: the slab rests on its plinth there)
    for i in range(len(centre) - 1):
        a, b = centre[i], centre[i + 1]; L = (Vector((b.x - a.x, b.y - a.y, 0))).length
        nsup = int(L / cfg["support_spacing"])
        for k in range(1, nsup + 1):
            q = a.lerp(b, k / (nsup + 1))
            if q.z - z_ground > 1.4:
                lu = (q - F.o).dot(F.t); lv = (q - F.o).dot(F.r)
                column(lu, lv, q.z - cfg["approach_depth"], None, "approach")
    # foot: a flat run-out, then a paved path to the back of the sidewalk (headroom-checked)
    foot = centre[-1]
    fu = (foot - F.o).dot(F.t)
    run_out = 1.6
    pu = fu + dirn * run_out
    # headroom: the lateral path crosses the leg lines between the foot and the sidewalk; move it beyond the structure if needed
    def soffit_at(uq, vq):
        best = None
        for c in plan["chains"]:
            if c["part"] not in (0, 1): continue
            for qa, qb in zip(c["pts"], c["pts"][1:]):
                qa = Vector(qa); qb = Vector(qb)
                for f in (0.0, 0.25, 0.5, 0.75, 1.0):
                    q = qa.lerp(qb, f); du = (q - F.o).dot(F.t) - uq; dv = (q - F.o).dot(F.r) - vq
                    if abs(du) < W / 2 + 0.3 and abs(dv) < W / 2 + 0.3:
                        z = q.z - c["depth"]
                        best = z if best is None else min(best, z)
        return best
    v_path_end = sgn * (back - 0.15)
    for attempt in range(30):
        low = None; vv = v
        steps = max(2, int(abs(v - v_path_end) / 0.5))
        for i in range(steps + 1):
            vq = v + (v_path_end - v) * i / steps
            if abs(vq - v) < W / 2 + 0.1: continue
            so = soffit_at(pu, vq)
            if so is not None and so - z_ground < cfg["min_headroom"]: low = so; break
        if low is None: break
        pu += dirn * 1.0
    path = [foot, F.w(pu, v, z_ground)]
    path.append(F.w(pu, v_path_end, z_ground))
    chain(0, path, KIND["path"], width=min(W, 2.5), depth=cfg["path_depth"])
    plan["footprint"].append({"kind": "approach", "end": end, "type": kind,
                              "poly": [list(F.w(uu, vv, 0))[:2] for uu, vv in ((d * W / 2, v_line - sgn * W / 2), (d * (max_u + W / 2 + 1.0), v_line - sgn * W / 2),
                                                                                  (d * (max_u + W / 2 + 1.0), v_line + sgn * (res["depth"] - W / 2)), (d * W / 2, v_line + sgn * (res["depth"] - W / 2)))]})
    # pedestrian route edges (sidewalk -> foot -> head landing); deck edge added by the caller
    joined = [list(map(lambda c: round(c, 3), q)) for q in [F.w(0, v_line, z_top)] + centre]
    plan["ped_edges"].append({"id": "%s_%s_%s" % (end, kind, "p" if d > 0 else "m"), "kind": kind, "end": end, "step_free": kind == "ramp",
                              "max_slope": round(cfg["ramp_max_slope"], 4) if kind == "ramp" else None, "width": W, "rise": round(z_top - z_ground, 3),
                              "length": round(sum((Vector(a) - Vector(b)).length for a, b in zip(joined, joined[1:])), 2),
                              "points": list(reversed(joined)) + [], "sidewalk_point": [round(c, 3) for c in path[-1]],
                              "approach_path": [[round(c, 3) for c in q] for q in path]})


# ============================================================================ objects
def _anchor(name):
    return bpy.data.objects.get("MRS_FootbridgeAnchor_" + name)


def make(name, road, along, collection, **cfg):
    """Create (or reset) a footbridge with an anchor empty at `along` on `road`, then build it."""
    p, t, r = road_sample(road, along)
    a = _anchor(name)
    if a is None:
        a = bpy.data.objects.new("MRS_FootbridgeAnchor_" + name, None); a.empty_display_type = "SINGLE_ARROW"; a.empty_display_size = 4.0
        collection.objects.link(a)
    a.location = p; a.rotation_euler = (0, 0, math.atan2(r.y, r.x) - math.pi / 2)
    conf = dict(DEFAULTS); conf.update(cfg); conf["road"] = road.name
    a["mrs_footbridge"] = json.dumps(conf); a["mrs_footbridge_name"] = name
    return rebuild(name, collection)


def _along_of_point(road, pos):
    L = road_length(road); best = None
    a = 0.0
    while a <= L:
        p, t, r = road_sample(road, a); d = (Vector((pos.x, pos.y)) - Vector((p.x, p.y))).length
        if best is None or d < best[0]: best = (d, a)
        a += 2.0
    lo, hi = max(0.0, best[1] - 2.0), min(L, best[1] + 2.0)
    for _ in range(18):
        m1 = lo + (hi - lo) / 3; m2 = hi - (hi - lo) / 3
        d1 = (Vector(pos[:2]) - road_sample(road, m1)[0].to_2d()).length; d2 = (Vector(pos[:2]) - road_sample(road, m2)[0].to_2d()).length
        if d1 < d2: hi = m2
        else: lo = m1
    return (lo + hi) / 2


def config(name):
    a = _anchor(name)
    conf = dict(DEFAULTS); conf.update(json.loads(a["mrs_footbridge"])); return conf


def rebuild(name, collection=None):
    """Re-solve from the anchor (position + config) and the modifier's Style, rewrite the skeleton in place."""
    a = _anchor(name); conf = config(name)
    road = bpy.data.objects[conf["road"]]
    obj = bpy.data.objects.get(name)
    if obj is not None and MOD in obj.modifiers:
        try: conf["style"] = mod_input_get(obj.modifiers[MOD], "Style") or conf["style"]
        except Exception: pass
    along = _along_of_point(road, a.location)
    plan = solve(road, along, conf)
    me = _skeleton_mesh(name + "_skeleton", plan)
    collection = collection or a.users_collection[0]
    if obj is None:
        obj = bpy.data.objects.new(name, me); collection.objects.link(obj)
    else:
        old = obj.data; obj.data = me
        if old is not me and old.users == 0: bpy.data.meshes.remove(old)
    me.name = name + "_skeleton"
    obj["mrs_footbridge"] = name; obj["mrs_footbridge_plan"] = json.dumps(plan)
    mod = obj.modifiers.get(MOD) or obj.modifiers.new(MOD, "NODES")
    if mod.node_group is None: mod.node_group = bpy.data.node_groups[GROUP]
    try: mod_input_set(mod, "Style", conf["style"])
    except Exception: pass
    _lights(obj, plan, conf)
    obj.update_tag()
    return obj, plan


def _skeleton_mesh(name, plan):
    verts = []; edges = []; attrs = {k: [] for k in ("part", "kind", "width", "depth", "going", "rise", "top", "foot")}
    vattrs = {k: [] for k in ("side", "fwd")}
    for c in plan["chains"]:
        n0 = len(verts); m = len(c["pts"])
        for i, (q, s) in enumerate(zip(c["pts"], c["side"])):
            verts.append(q)
            attrs["part"].append(float(c["part"])); attrs["kind"].append(float(c["kind"])); attrs["width"].append(float(c["width"])); attrs["depth"].append(float(c["depth"]))
            attrs["going"].append(float(c.get("going", 0.0))); attrs["rise"].append(float(c.get("rise", 0.0)))
            attrs["top"].append(1.0 if i == m - 1 else 0.0); attrs["foot"].append(1.0 if (c["part"] == 2 and i == m - 1) else 0.0)
            vattrs["side"].append(c.get("side_fixed") and Vector(c["side_fixed"]).normalized()[:] or s)
            vattrs["fwd"].append(c.get("fwd", [0.0, 0.0, 0.0]))
        if c["part"] == 2: attrs["top"][n0] = 1.0; attrs["top"][n0 + 1] = 0.0          # column: first point = top, last = foot
        for i in range(m - 1): edges.append((n0 + i, n0 + i + 1))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, edges, [])
    for k, vals in attrs.items():
        at = me.attributes.new(k, "FLOAT", "POINT"); at.data.foreach_set("value", vals)
    for k, vals in vattrs.items():
        at = me.attributes.new(k, "FLOAT_VECTOR", "POINT"); at.data.foreach_set("vector", [x for v in vals for x in v])
    me.update()
    return me


def _lights(obj, plan, conf):
    """Real light sources along the deck and approaches (children `<name>_Lamp<i>`), kept apart from the
    emissive handrail strip. Uses mrs.lighting when available (path preset), else plain point lights."""
    for ch in list(obj.children):
        if ch.get("mrs_light"): bpy.data.objects.remove(ch)
    plan["lights"] = []
    if not conf.get("lights"): return
    pts = []
    for c in plan["chains"]:
        if c["part"] != 0 or c["kind"] == KIND["path"]: continue
        P = [Vector(q) for q in c["pts"]]; acc = conf["light_spacing"] * 0.5
        for a, b in zip(P, P[1:]):
            L = (b - a).length; s = acc
            while s < L:
                pts.append(a.lerp(b, s / L)); s += conf["light_spacing"]
            acc = s - L
    for i, q in enumerate(pts):
        ld = bpy.data.lights.get(obj.name + "_LampData") or bpy.data.lights.new(obj.name + "_LampData", "POINT")
        # ~15 lx on the deck 1 m below / ~3 m away (mrs.lighting calibration: E = P / (4 pi d^2) x 683 lm/W)
        ld.energy = 2.5; ld.shadow_soft_size = 0.15; ld.color = (1.0, 1.0, 1.0)
        try: ld.use_temperature = True; ld.temperature = 3000          # the same 3000 K the light record gives Godot
        except AttributeError: ld.color = (1.0, 0.72, 0.45)
        try: ld.use_custom_distance = True; ld.cutoff_distance = 9.0
        except Exception: pass
        lo = bpy.data.objects.new("%s_Lamp%d" % (obj.name, i), ld)
        for col in obj.users_collection: col.objects.link(lo)
        lo.location = q + Vector((0, 0, 1.0)); lo.parent = obj; lo.matrix_parent_inverse = obj.matrix_world.inverted()
        lo["mrs_light"] = 1; lo["mrs_light_class"] = "footbridge"; lo["mrs_godot_range"] = 9.0; lo["mrs_temperature"] = 3000
        plan["lights"].append([round(c, 3) for c in lo.location])


def rebuild_all(collection=None):
    names = [o["mrs_footbridge_name"] for o in list(collection.all_objects if collection else bpy.data.objects)
             if o.type == "EMPTY" and o.name.startswith("MRS_FootbridgeAnchor_") and o.get("mrs_footbridge_name")]
    return [rebuild(n, collection) for n in names]


def all_bridges(collection=None):
    return [o for o in (collection.all_objects if collection else bpy.data.objects) if o.get("mrs_footbridge") and o.type == "MESH"]


# ============================================================================ profiles (style cross-sections)
PROFILE_COL = MRS + "FootbridgeProfiles"


def _profile(name, rows):
    """A closed edge loop with per-point attributes px (fraction of width), pxm (m), pd (fraction of depth),
    pt (m, + = down), pmat (0 walking surface, 1 structure). Positions are only for display."""
    col = bpy.data.collections.get(PROFILE_COL) or bpy.data.collections.new(PROFILE_COL)
    me = bpy.data.meshes.get(name)
    if me is None: me = bpy.data.meshes.new(name)
    else: me.clear_geometry()
    verts = [(r[0] * 3.0 + r[1], -(r[2] * 1.0 + r[3]), 0.0) for r in rows]
    me.from_pydata(verts, [(i, (i + 1) % len(rows)) for i in range(len(rows))], [])
    for k, idx in (("px", 0), ("pxm", 1), ("pd", 2), ("pt", 3), ("pmat", 4)):
        at = me.attributes.get(k) or me.attributes.new(k, "FLOAT", "POINT"); at.data.foreach_set("value", [float(r[idx]) for r in rows])
    o = bpy.data.objects.get(name)
    if o is None: o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.hide_render = True
    return o


def build_profiles():
    T_ = 0.22   # deck slab thickness (m)
    girder = [(-0.5, 0.0, 0.0, -0.08, 0), (-0.5, 0.0, 0.0, 0.0, 1), (0.5, 0.0, 0.0, 0.0, 1), (0.5, 0.0, 0.0, -0.08, 0)]
    # walking surface across (pmat 0), then down the right fascia, inner fascia, soffit, left fascia
    girder = [(-0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.02, 1), (0.5, 0.0, 1.0, 0.0, 1), (0.5, -0.32, 1.0, 0.0, 1),
              (0.5, -0.32, 0.0, T_, 1), (-0.5, 0.32, 0.0, T_, 1), (-0.5, 0.32, 1.0, 0.0, 1), (-0.5, 0.0, 1.0, 0.0, 1), (-0.5, 0.0, 0.0, 0.02, 1)]
    box = [(-0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.02, 1), (0.5, 0.0, 0.0, T_, 1), (0.5, -0.45, 1.0, 0.0, 1),
           (-0.5, 0.45, 1.0, 0.0, 1), (-0.5, 0.0, 0.0, T_, 1), (-0.5, 0.0, 0.0, 0.02, 1)]
    truss = [(-0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.0, 0), (0.5, 0.0, 0.0, 0.02, 1), (0.5, 0.0, 1.0, 0.0, 1), (-0.5, 0.0, 1.0, 0.0, 1), (-0.5, 0.0, 0.0, 0.02, 1)]
    # approaches and stairs: slab with upstand edges (stair stringers rise 0.12 m above the nosing line)
    stair = [(-0.5, 0.06, 0.0, -0.0, 0), (0.5, -0.06, 0.0, 0.0, 0), (0.5, -0.06, 0.0, -0.12, 1), (0.5, 0.0, 0.0, -0.12, 1), (0.5, 0.0, 1.0, 0.0, 1),
             (-0.5, 0.0, 1.0, 0.0, 1), (-0.5, 0.0, 0.0, -0.12, 1), (-0.5, 0.06, 0.0, -0.12, 1)]
    return {"Girder": _profile(MRS + "FB_Profile_Girder", girder), "Box": _profile(MRS + "FB_Profile_Box", box),
            "Truss": _profile(MRS + "FB_Profile_Truss", truss), "Stair": _profile(MRS + "FB_Profile_Stair", stair)}


# ============================================================================ node group
INPUTS = [
    ("Structure", [("Style", "NodeSocketMenu", None, None, None, "Girder: steel fascia beams; Truss: through Warren truss on the span; Box: closed box girder"),
                   ("Column Radius", "NodeSocketFloat", 0.28, 0.12, 1.0, "m", "DISTANCE"),
                   ("Truss Height", "NodeSocketFloat", 1.9, 1.2, 3.5, "m (Truss style)", "DISTANCE"),
                   ("Truss Panel", "NodeSocketFloat", 2.6, 1.0, 5.0, "m between truss verticals", "DISTANCE")]),
    ("Railing", [("Railing Height", "NodeSocketFloat", 1.3, 0.9, 1.8, "m above the walking surface (cyclists: 1.3 m)", "DISTANCE"),
                 ("Handrail Height", "NodeSocketFloat", 0.9, 0.7, 1.1, "m, inner handrail", "DISTANCE"),
                 ("Post Spacing", "NodeSocketFloat", 1.6, 0.8, 4.0, "m", "DISTANCE"),
                 ("Baluster Spacing", "NodeSocketFloat", 0.12, 0.08, 0.5, "m between vertical bars", "DISTANCE"),
                 ("Balusters", "NodeSocketBool", True, None, None, "vertical bar infill (off: no infill)")]),
    ("Lighting", [("Handrail LED", "NodeSocketBool", True, None, None, "emissive LED strip under the top rail (decorative; real lights are separate objects)")]),
    ("Materials", [("Deck Material", "NodeSocketMaterial", None, None, None, "walking surface"),
                   ("Structure Material", "NodeSocketMaterial", None, None, None, "beams, truss, stringers"),
                   ("Concrete Material", "NodeSocketMaterial", None, None, None, "columns, footings, steps"),
                   ("Railing Material", "NodeSocketMaterial", None, None, None, "posts, rails, bars"),
                   ("LED Material", "NodeSocketMaterial", None, None, None, "handrail LED strip")]),
    ("Output", [("Collision Only", "NodeSocketBool", False, None, None, "walk surfaces (stairs as inclines), rail walls and columns only")]),
]


def _attr(tb, name, kind="FLOAT"): return tb.named(name, kind)


def _part(tb, geo, k):
    sep = tb.n("GeometryNodeSeparateGeometry", domain="POINT"); tb.inp(sep, "Geometry", geo)
    tb.inp(sep, "Selection", tb.compare("LESS_THAN", tb.math("ABSOLUTE", tb.math("SUBTRACT", _attr(tb, "part"), float(k))), 0.1))
    return sep.outputs["Selection"]


def _obj_geo(tb, obj):
    n = tb.n("GeometryNodeObjectInfo", transform_space="ORIGINAL"); n.inputs["Object"].default_value = obj
    return n.outputs["Geometry"]


def _slab(tb, curves, profile_geo, mat_deck, mat_struct):
    """Sweep with a parametric profile; positions rebuilt from the stored side / width / depth attributes."""
    sp = tb.n("GeometryNodeSplineParameter")
    c = tb.store(curves, "cpos", tb.n("GeometryNodeInputPosition").outputs[0], "FLOAT_VECTOR")
    c = tb.store(c, "along", sp.outputs["Length"])
    m2c = tb.n("GeometryNodeMeshToCurve"); tb.inp(m2c, "Mesh", profile_geo)
    c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", c); tb.inp(c2m, "Profile Curve", m2c.outputs[0]); tb.inp(c2m, "Fill Caps", True)
    lat = tb.math("ADD", tb.math("MULTIPLY", _attr(tb, "px"), _attr(tb, "width")), _attr(tb, "pxm"))
    dz = tb.math("MULTIPLY", -1.0, tb.math("ADD", tb.math("MULTIPLY", _attr(tb, "pd"), _attr(tb, "depth")), _attr(tb, "pt")))
    pos = tb.vmath("ADD", tb.vmath("ADD", _attr(tb, "cpos", "FLOAT_VECTOR"), tb.vmath("SCALE", _attr(tb, "side", "FLOAT_VECTOR"), scale=lat)), tb.combine(0.0, 0.0, dz))
    sp2 = tb.n("GeometryNodeSetPosition"); tb.inp(sp2, "Geometry", c2m.outputs[0]); tb.inp(sp2, "Position", pos)
    g = tb.store(sp2.outputs[0], "lat", lat)
    g = tb.store(g, "UVMap", tb.combine(lat, _attr(tb, "along"), 0.0), "FLOAT2", "CORNER")
    # faces whose corners are all walking-surface points (pmat 0) get the deck material
    deck_sel = tb.compare("LESS_THAN", _attr(tb, "pmat"), 0.01)
    sm1 = tb.n("GeometryNodeSetMaterial"); tb.inp(sm1, "Geometry", g); tb.inp(sm1, "Material", mat_struct)
    sm2 = tb.n("GeometryNodeSetMaterial"); tb.inp(sm2, "Geometry", sm1.outputs[0]); tb.inp(sm2, "Material", mat_deck); tb.inp(sm2, "Selection", deck_sel)
    ss = tb.n("GeometryNodeSetShadeSmooth", domain="FACE"); tb.inp(ss, "Geometry", sm2.outputs[0]); tb.inp(ss, "Shade Smooth", False)
    return ss.outputs[0]


def _cube(tb, size=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0)):
    c = tb.n("GeometryNodeMeshCube"); tb.inp(c, "Size", size)
    tr = tb.n("GeometryNodeTransform"); tb.inp(tr, "Geometry", c.outputs[0]); tb.inp(tr, "Translation", offset)
    return tr.outputs[0]


def _instance(tb, points, inst, rotation=None, scale=None, material=None):
    n = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(n, "Points", points); tb.inp(n, "Instance", inst)
    if rotation is not None: tb.inp(n, "Rotation", rotation)
    if scale is not None: tb.inp(n, "Scale", scale)
    r = tb.n("GeometryNodeRealizeInstances"); tb.inp(r, "Geometry", n.outputs[0])
    out = r.outputs[0]
    if material is not None:
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", out); tb.inp(sm, "Material", material); out = sm.outputs[0]
    return out


def _align(tb, axis, vec):
    n = tb.n("FunctionNodeAlignRotationToVector", axis=axis, pivot_axis="AUTO"); tb.inp(n, "Vector", vec); tb.inp(n, "Factor", 1.0)
    return n.outputs[0]


def _resample(tb):
    n = tb.n("GeometryNodeResampleCurve"); n.inputs["Mode"].default_value = "Length"; return n


def _points(tb, curves, spacing=None):
    if spacing is not None:
        rs = _resample(tb); tb.inp(rs, "Curve", curves); tb.inp(rs, "Length", spacing); curves = rs.outputs[0]
    cp = tb.n("GeometryNodeCurveToPoints", mode="EVALUATED"); tb.inp(cp, "Curve", curves)
    return cp.outputs["Points"]


def _tube(tb, curves, radius, res=8, material=None, offset=None, square=False):
    if offset is not None:
        sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", curves); tb.inp(sp, "Offset", offset); curves = sp.outputs[0]
    if square:
        prof = tb.n("GeometryNodeCurvePrimitiveQuadrilateral", mode="RECTANGLE"); tb.inp(prof, "Width", radius * 2); tb.inp(prof, "Height", radius * 2); pg = prof.outputs[0]
    else:
        prof = tb.n("GeometryNodeCurvePrimitiveCircle", mode="RADIUS"); tb.inp(prof, "Resolution", res); tb.inp(prof, "Radius", radius); pg = prof.outputs[0]
    c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", curves); tb.inp(c2m, "Profile Curve", pg); tb.inp(c2m, "Fill Caps", True)
    out = c2m.outputs[0]
    if material is not None:
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", out); tb.inp(sm, "Material", material); out = sm.outputs[0]
    return out


def _ribbon(tb, curves, z0, z1, material=None):
    """Vertical ribbon from z0 to z1 above the curve (single-sided wall: collision rails, LED strip)."""
    ln = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(ln, "Start", (0.0, 0.0, 0.0)); tb.inp(ln, "End", (1.0, 0.0, 0.0))
    idx = tb.n("GeometryNodeInputIndex").outputs[0]
    lnp = tb.store(ln.outputs[0], "pf", idx)
    c = tb.store(curves, "cpos", tb.n("GeometryNodeInputPosition").outputs[0], "FLOAT_VECTOR")
    c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", c); tb.inp(c2m, "Profile Curve", lnp)
    z = tb.math("ADD", z0, tb.math("MULTIPLY", _attr(tb, "pf"), tb.math("SUBTRACT", z1, z0)))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", c2m.outputs[0]); tb.inp(sp, "Position", tb.vmath("ADD", _attr(tb, "cpos", "FLOAT_VECTOR"), tb.combine(0.0, 0.0, z)))
    out = sp.outputs[0]
    if material is not None:
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", out); tb.inp(sm, "Material", material); out = sm.outputs[0]
    return out


def build_footbridge_group():
    profiles = build_profiles()
    g = new_tree(GROUP)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry"); sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    add_inputs(g, INPUTS)
    tb = T(g)
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    I = {s.name: s for s in gi.outputs}
    tb.frame_("Skeleton -> curves (solver output)")
    m2c = tb.n("GeometryNodeMeshToCurve"); tb.inp(m2c, "Mesh", I["Geometry"]); crv = m2c.outputs[0]
    walk = _part(tb, crv, 0); flights = _part(tb, crv, 1); cols = _part(tb, crv, 2); rails = _part(tb, crv, 3); span_rails = _part(tb, crv, 5)
    all_rails = tb.join(rails, span_rails)
    style = tb.menu_switch(I["Style"], [(s, float(i)) for i, s in enumerate(STYLES)], "FLOAT", "Style")
    is_truss = tb.compare("EQUAL", style, 1.0)
    tb.frame_("Road_Surface: deck, landings, ramps (style profile)")
    prof = tb.switch(tb.compare("LESS_THAN", style, 0.5), tb.switch(is_truss, _obj_geo(tb, profiles["Box"]), _obj_geo(tb, profiles["Truss"]), "GEOMETRY"), _obj_geo(tb, profiles["Girder"]), "GEOMETRY")
    # the main span uses the style profile, approaches the stair/approach profile (kind 0 = span)
    span_sel = tb.n("GeometryNodeSeparateGeometry", domain="POINT"); tb.inp(span_sel, "Geometry", walk); tb.inp(span_sel, "Selection", tb.compare("LESS_THAN", _attr(tb, "kind"), 0.5))
    deck = _slab(tb, span_sel.outputs["Selection"], prof, I["Deck Material"], I["Structure Material"])
    appr = _slab(tb, span_sel.outputs["Inverted"], _obj_geo(tb, profiles["Stair"]), I["Deck Material"], I["Concrete Material"])
    stringers = _slab(tb, flights, _obj_geo(tb, profiles["Stair"]), I["Deck Material"], I["Concrete Material"])
    tb.frame_("Stairs: steps between stringers")
    sp = _points(tb, flights)
    dl = tb.n("GeometryNodeDeleteGeometry", domain="POINT"); tb.inp(dl, "Geometry", sp); tb.inp(dl, "Selection", tb.compare("GREATER_THAN", _attr(tb, "top"), 0.5))
    step_scale = tb.combine(tb.math("SUBTRACT", _attr(tb, "width"), 0.16), _attr(tb, "going"), _attr(tb, "rise"))
    steps = _instance(tb, dl.outputs[0], _cube(tb, (1.0, 1.0, 1.0), (0.0, 0.5, 0.5)), _align(tb, "Y", _attr(tb, "fwd", "FLOAT_VECTOR")), step_scale, I["Concrete Material"])
    steps = tb.store(steps, "UVMap", tb.combine(tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])[0], tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])[1], 0.0), "FLOAT2", "CORNER")
    tb.frame_("Columns, footings, crossheads")
    col_mesh = _tube(tb, cols, I["Column Radius"], 16, I["Concrete Material"])
    cpts = _points(tb, cols)
    foot_pts = tb.n("GeometryNodeSeparateGeometry", domain="POINT"); tb.inp(foot_pts, "Geometry", cpts); tb.inp(foot_pts, "Selection", tb.compare("GREATER_THAN", _attr(tb, "foot"), 0.5))
    fsz = tb.math("MULTIPLY", I["Column Radius"], 4.0)
    footings = _instance(tb, foot_pts.outputs["Selection"], _cube(tb, (1.0, 1.0, 0.6), (0.0, 0.0, -0.25)), None, tb.combine(fsz, fsz, 1.0), I["Concrete Material"])
    head_pts = tb.n("GeometryNodeSeparateGeometry", domain="POINT"); tb.inp(head_pts, "Geometry", cpts); tb.inp(head_pts, "Selection", tb.compare("GREATER_THAN", _attr(tb, "top"), 0.5))
    hsz = tb.math("MULTIPLY", I["Column Radius"], 2.6)
    heads = _instance(tb, head_pts.outputs["Selection"], _cube(tb, (1.0, 1.0, 0.45), (0.0, 0.0, -0.225)), _align(tb, "X", _attr(tb, "side", "FLOAT_VECTOR")), tb.combine(hsz, hsz, 1.0), I["Concrete Material"])
    tb.frame_("Railings: posts, top rail, handrail, bars, kick plate, LED")
    rh = I["Railing Height"]
    posts_pts = _points(tb, all_rails, I["Post Spacing"])
    mbd = tb.n("GeometryNodeMergeByDistance"); tb.inp(mbd, "Geometry", posts_pts); tb.inp(mbd, "Distance", 0.3)
    posts = _instance(tb, mbd.outputs[0], _cube(tb, (0.06, 0.06, 1.0), (0.0, 0.0, 0.5)), None, tb.combine(1.0, 1.0, rh), I["Railing Material"])
    top_rail = _tube(tb, all_rails, 0.032, 10, I["Railing Material"], tb.combine(0.0, 0.0, rh))
    hand_rail = _tube(tb, all_rails, 0.022, 8, I["Railing Material"], tb.combine(0.0, 0.0, I["Handrail Height"]))
    bottom_rail = _tube(tb, all_rails, 0.02, 6, I["Railing Material"], tb.combine(0.0, 0.0, 0.12), square=True)
    bars_pts = _points(tb, all_rails, I["Baluster Spacing"])
    # bars: open 4-sided prisms (8 tris each, no caps hidden inside the rails)
    bar = tb.n("GeometryNodeMeshCylinder", fill_type="NONE"); tb.inp(bar, "Vertices", 4); tb.inp(bar, "Radius", 0.012); tb.inp(bar, "Depth", 1.0)
    bar_t = tb.n("GeometryNodeTransform"); tb.inp(bar_t, "Geometry", bar.outputs["Mesh"]); tb.inp(bar_t, "Translation", (0.0, 0.0, 0.5))
    bars = _instance(tb, bars_pts, bar_t.outputs[0], None, tb.combine(1.0, 1.0, tb.math("SUBTRACT", rh, 0.12)), I["Railing Material"])
    bars = tb.switch(I["Balusters"], tb.empty(), bars, "GEOMETRY")
    kick = _ribbon(tb, all_rails, 0.0, 0.1, I["Structure Material"])
    led = _ribbon(tb, all_rails, tb.math("SUBTRACT", rh, 0.06), tb.math("SUBTRACT", rh, 0.045), I["LED Material"])
    led = tb.switch(I["Handrail LED"], tb.empty(), led, "GEOMETRY")
    tb.frame_("Truss (span only, Truss style)")
    th = I["Truss Height"]
    top_chord = _tube(tb, span_rails, 0.09, 4, I["Structure Material"], tb.combine(0.0, 0.0, th), square=True)
    bot_chord = _tube(tb, span_rails, 0.12, 4, I["Structure Material"], tb.combine(0.0, 0.0, -0.1), square=True)
    tp = _points(tb, span_rails, I["Truss Panel"])
    verts_ = _instance(tb, tp, _cube(tb, (0.14, 0.14, 1.0), (0.0, 0.0, 0.5)), None, tb.combine(1.0, 1.0, th), I["Structure Material"])
    ends = tb.n("GeometryNodeCurveEndpointSelection"); tb.inp(ends, "Start Size", 0); tb.inp(ends, "End Size", 1)
    # endpoint selection is a curve field: evaluate it on the curve and keep it as an attribute before the point conversion
    rs = _resample(tb); tb.inp(rs, "Curve", span_rails); tb.inp(rs, "Length", I["Truss Panel"])
    rs_e = tb.store(rs.outputs[0], "is_end", ends.outputs[0], "BOOLEAN")
    cp = tb.n("GeometryNodeCurveToPoints", mode="EVALUATED"); tb.inp(cp, "Curve", rs_e)
    tpe = cp.outputs["Points"]
    si2 = tb.n("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(si2, "Geometry", tpe); tb.inp(si2, "Value", tb.n("GeometryNodeInputPosition").outputs[0]); tb.inp(si2, "Index", tb.math("ADD", tb.n("GeometryNodeInputIndex").outputs[0], 1.0))
    idx2 = tb.n("GeometryNodeInputIndex").outputs[0]; odd2 = tb.math("FLOORED_MODULO", idx2, 2.0)
    q0 = tb.vmath("ADD", tb.n("GeometryNodeInputPosition").outputs[0], tb.combine(0.0, 0.0, tb.math("MULTIPLY", odd2, th)))
    q1 = tb.vmath("ADD", si2.outputs[0], tb.combine(0.0, 0.0, tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, odd2), th)))
    dq = tb.vmath("SUBTRACT", q1, q0)
    tq = tb.store(tpe, "dvec", dq, "FLOAT_VECTOR"); tq = tb.store(tq, "q0", q0, "FLOAT_VECTOR")
    dle = tb.n("GeometryNodeDeleteGeometry", domain="POINT"); tb.inp(dle, "Geometry", tq); tb.inp(dle, "Selection", tb.named("is_end", "BOOLEAN"))
    spq = tb.n("GeometryNodeSetPosition"); tb.inp(spq, "Geometry", dle.outputs[0]); tb.inp(spq, "Position", _attr(tb, "q0", "FLOAT_VECTOR"))
    dlen = tb.vmath("LENGTH", _attr(tb, "dvec", "FLOAT_VECTOR"))
    diags = _instance(tb, spq.outputs[0], _cube(tb, (0.11, 0.11, 1.0), (0.0, 0.0, 0.5)), _align(tb, "Z", _attr(tb, "dvec", "FLOAT_VECTOR")), tb.combine(1.0, 1.0, dlen), I["Structure Material"])
    truss = tb.join(top_chord, bot_chord, verts_, diags)
    truss = tb.switch(is_truss, tb.empty(), truss, "GEOMETRY")
    tb.frame_("Assembly + collision")
    full = tb.join(deck, appr, stringers, steps, col_mesh, footings, heads, posts, top_rail, hand_rail, bottom_rail, bars, kick, led, truss)
    coll = tb.join(deck, appr, stringers, col_mesh, _ribbon(tb, all_rails, 0.0, rh))
    out = tb.switch(I["Collision Only"], full, coll, "GEOMETRY")
    out = tb.store(out, "kind", 3.0, "FLOAT", "FACE")
    tb.link(out, go.inputs[0])
    _defaults(g)
    return g


def _defaults(g):
    from .props import mat
    # v5: the street-hardware materials (hardware.py, tileable PBR on the metre UVs) when built, else the v4 fallbacks
    try:
        from . import hardware as _hw
        if not bpy.data.materials.get(MRS + "HW_DeckAntiSlip"): _hw.build_hardware_materials(bake="auto")
    except Exception as e:
        print("footbridge: hardware materials unavailable (%s); v4 materials used" % e)
    hw = lambda n: bpy.data.materials.get(MRS + "HW_" + n)
    vals = {"Deck Material": hw("DeckAntiSlip") or bpy.data.materials.get(MRS + "Paving") or mat(MRS + "FB_Deck", (0.42, 0.42, 0.40), 0.85),
            "Structure Material": hw("PaintedSteel") or mat(MRS + "FB_Steel", (0.20, 0.26, 0.30), 0.45, 0.6),
            "Concrete Material": hw("Concrete") or bpy.data.materials.get(MRS + "PropConcrete") or mat(MRS + "FB_Concrete", (0.56, 0.55, 0.52), 0.85),
            "Railing Material": hw("Galvanized") or bpy.data.materials.get(MRS + "PropSteel") or mat(MRS + "FB_Rail", (0.7, 0.72, 0.74), 0.3, 1.0),
            "LED Material": hw("LEDDiffuser") or _led_material()}
    for it in g.interface.items_tree:
        if getattr(it, "in_out", "") == "INPUT" and it.name in vals:
            try: it.default_value = vals[it.name]
            except Exception: pass
        if getattr(it, "in_out", "") == "INPUT" and it.name == "Style":
            try: it.default_value = "Girder"
            except Exception: pass


def _led_material():
    from .props import mat
    m = mat(MRS + "FB_LED", (1.0, 0.9, 0.75), 0.4)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Emission Color"].default_value = (1.0, 0.86, 0.66, 1); b.inputs["Emission Strength"].default_value = 3.0
    return m


def ensure_group():
    if GROUP not in bpy.data.node_groups or not len(bpy.data.node_groups[GROUP].nodes): build_footbridge_group()
    return bpy.data.node_groups[GROUP]
