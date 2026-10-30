"""City street network for Mert Road Studio: a CityForge plan (city.json: nodes, roads, lanes) turned into
what the MRS builders need (pure Python + numpy, no bpy, so it can be checked outside Blender).

The CityForge graph is drawn as overlapping straight ribbons, so it tolerates things the MRS builders do not:
nodes a few metres apart joined by 4-12 m links, two roads leaving a node 1-7 degrees apart, bends drawn as
nodes. `build()` resolves them in this order:
  1. clusters   nodes joined by a road shorter than the two junctions' reach (half widths + corner radius)
                become one junction at their centroid; the link roads are absorbed
  2. duplicates two roads between the same pair of junctions: the more important one is kept
  3. angles     at a junction, approaches closer than MIN_ANGLE degrees: the less important road is dropped
  4. chains     roads through nodes with two approaches of the same class are one MRS road; a bend gets a
                circular fillet sized so the inner sidewalk keeps its radius (else the node stays a 2-way
                junction); closed loops are cut at one node
  5. lanes      back lanes become service roads from lot line to lot line; the streets they meet get a
                dropped-kerb driveway (MRS Driveways) where they cross the sidewalk
Every decision is recorded in `report`. Coordinates are plan metres (x east, y north); heights come from the
graded height field (the same one CityForge builds the ground from)."""
import json, math, os
import numpy as np

MIN_ANGLE = 25.0                      # the junction builder's minimum angle between neighbouring approaches
MAX_PLANE_GRADE = 0.22                # a junction on a slope is a plane up to this grade (steeper: the rest is levelled)
WALK = 4.6                            # CityForge verge 1.6 + sidewalk 3.0 beyond the carriageway edge
ASPH = 0.05                           # CityForge: asphalt this far above the graded ground
EDGE_DEPTH = 1.2                      # skirt under a sidewalk's back edge: hides the ground where a street runs on fill
RANK = {"boulevard": 4, "arterial": 3, "downtown": 2, "local": 1, "lane": 0}
CORNER = {"local": 6.0, "downtown": 5.0, "arterial": 8.0, "boulevard": 8.0}
CONTROL_RANK = {"signal": 3, "stop": 2, "uncontrolled": 1, "none": 0}

# MRS road inputs per CityForge class. Every profile fills the CityForge right of way exactly:
# carriageway = `width`, then kerb 0.25 + sidewalk 4.35 (= verge 1.6 + sidewalk 3.0), so lots, fences and
# front walks keep their places.
COMMON = {"Conform": False, "Embankment": False, "Superelevation": 0.0, "Curb Width": 0.25, "Curb Height": 0.15, "Smoothing": 4, "Resolution": 1.0,
          "Sidewalk Left": True, "Sidewalk Right": True, "Sidewalk Width Left": WALK - 0.25, "Sidewalk Width Right": WALK - 0.25,
          "Light Side": "None", "Prop Side": "None", "Tree Side": "None", "Scatter Density": 0.0, "Edge Depth": EDGE_DEPTH}
PROFILES = {
    "local": dict(preset="residential", **{"Crown": 2.0, "Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 3.0, "Parking Left": 2.5, "Parking Right": 2.5,
                                           "Centre Line": "None", "Edge Lines": False, "Lane Arrows": False, "Parking Ticks": False,
                                           "Planting Strip Left": 1.35, "Planting Strip Right": 1.35, "Median": 0.0, "Bike Left": "None", "Bike Right": "None"}),
    "arterial": dict(preset="urban", **{"Crown": 2.0, "Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.25, "Parking Left": 0.0, "Parking Right": 0.0, "Median": 0.0,
                                        "Centre Line": "Double", "Edge Lines": False, "Bike Left": "Buffered", "Bike Right": "Buffered", "Bike Width": 1.8, "Bike Buffer": 0.7,
                                        "Planting Strip Left": 1.35, "Planting Strip Right": 1.35}),
    "boulevard": dict(preset="urban", **{"Crown": 2.0, "Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.4, "Parking Left": 0.0, "Parking Right": 0.0, "Median": 4.4,
                                         "Centre Line": "None", "Edge Lines": False, "Bike Left": "None", "Bike Right": "None",
                                         "Planting Strip Left": 1.35, "Planting Strip Right": 1.35}),
    "downtown": dict(preset="urban", **{"Crown": 2.0, "Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.0, "Parking Left": 2.0, "Parking Right": 2.0, "Median": 0.0,
                                        "Centre Line": "Double", "Edge Lines": False, "Bike Left": "None", "Bike Right": "None",
                                        "Planting Strip Left": 0.0, "Planting Strip Right": 0.0}),
    "bridge": dict(preset="bridge", **{"Crown": 1.5, "Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.25, "Shoulder": 2.5, "Median": 0.0,
                                       "Sidewalk Width Left": 2.2, "Sidewalk Width Right": 2.2, "Centre Line": "Double", "Light Side": "None",
                                       "Planting Strip Left": 0.0, "Planting Strip Right": 0.0, "Pillar Spacing": 32.0}),
    "lane": dict(preset="service", **{"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 2.75, "Shoulder": 0.25, "Curb Height": 0.0, "Curb Width": 0.1,
                                      "Sidewalk Left": False, "Sidewalk Right": False, "Centre Line": "None", "Edge Lines": False, "Lane Arrows": False,
                                      "Crown": 1.0, "Edge Depth": 0.8}),
}
SPEED = {"local": 30, "downtown": 40, "arterial": 50, "boulevard": 50, "lane": 20}
MAX_GRADE = {"local": 0.12, "downtown": 0.12, "arterial": 0.12, "boulevard": 0.10, "lane": 0.18, "bridge": 0.06}   # vertical alignment (rise / run)
# the default grade table; a plan's own "max_grade" (port_halden_city.json grid.max_grade, carried in city.json)
# overrides it, so the planner and the network use one table (grade_table)
LANDING_GRADE = 0.03                  # a street's landing at a junction: at most this grade over its lock zone
LOCK_MAX = 14.0                       # longest Lock Length a street gets (m; the road group's default)
VC_K = 0.7                            # vertical curve length per % of grade change (m)
GRADE_WINDOW = 10.0                   # a street's grade is measured over every window of this much plan run (m)
GRADE_MARGIN = 0.002                  # the design keeps this below the class maximum (the validator's tolerance)
EARTH_MAX = 3.0                       # a junction moved further than this from its natural (or bridge) height: an optional link pulling it is dropped
EARTH_HARD = 6.0                      # no junction moves further than this
SMOOTH = {"local": 30.0, "downtown": 40.0, "arterial": 50.0, "boulevard": 60.0, "lane": 20.0}   # ground averaged over this length (m)
BRIDGE_CLEARANCE = 4.0                # deck height over the water level (m)
STYLE = {"local": "residential", "downtown": "avenue", "arterial": "avenue", "boulevard": "boulevard", "lane": "residential"}


def grade_table(city=None):
    """{class: max grade}: MAX_GRADE overridden by the plan's own table (city.json "max_grade")."""
    t = dict(MAX_GRADE); t.update((city or {}).get("max_grade") or {})
    return t


def carriageway_half(cls, bridge=False):
    """The wider side's carriageway half width of a class profile (Road_Profile: median / 2 + lanes x lane width +
    shoulder + parking + cycle buffer + cycle lane)."""
    _p, v = profile(cls, bridge)
    lanes = max(v.get("Lanes Forward", 1), v.get("Lanes Backward", 1))
    best = 0.0
    for side in ("Left", "Right"):
        bk = v.get("Bike " + side, "None"); bw = 0.0
        if bk != "None":
            bw = v.get("Bike Width", 1.6) * (2.0 if bk == "Two-Way" else 1.0) + (v.get("Bike Buffer", 0.5) if bk in ("Buffered", "Protected", "Two-Way") else 0.0)
        best = max(best, v.get("Parking " + side, 0.0) + bw)
    return v.get("Median", 0.0) / 2.0 + lanes * v.get("Lane Width", 3.2) + v.get("Shoulder", 0.0) + best


def crown_h(cls, bridge=False):
    """The crown's rise at the centre line (m): Crown % of the carriageway half width."""
    _p, v = profile(cls, bridge)
    return v.get("Crown", 2.0) * 0.01 * carriageway_half(cls, bridge)


def lock_length(ch, G, live, locked_ends):
    """A street's Lock Length: long enough that its crown fades in at <= LANDING_GRADE, at least the blur reach,
    short enough to leave GRADE_WINDOW m of climbing between its two landings, never more than half its live length."""
    m = COMMON["Smoothing"] * COMMON["Resolution"]
    ll_c = min(LOCK_MAX, max(m, 1.5 * ch / LANDING_GRADE))
    floor = max(m, 1.5 * ch / max(G, 1e-6))
    room = (live - GRADE_WINDOW) / max(locked_ends, 1) - m
    return float(min(live / 2.0, max(floor, min(ll_c, room))))


def profile(cls, bridge=False):
    """(preset, MRS inputs) for a CityForge road class."""
    p = dict(PROFILES["bridge" if bridge else cls])
    preset = p.pop("preset")
    vals = dict(COMMON); vals.update(p)
    if bridge: vals.pop("Edge Depth", None)
    return preset, vals


class Heights:
    """The graded height field (plan metres -> m), bilinear like CityForge's h_at."""
    def __init__(self, arr, cell):
        self.a = np.asarray(arr, dtype=np.float64); self.cell = float(cell); self.n = self.a.shape[0]

    @classmethod
    def load(cls, path, grid=513, cell=4.0):
        if path.endswith(".npz"): return cls(np.load(path)["height"], cell)
        return cls(np.fromfile(path, dtype=np.float32).reshape(grid, grid), cell)

    def __call__(self, x, y):
        N = self.n; fx = min(max(x / self.cell, 0.0), N - 1.001); fy = min(max(y / self.cell, 0.0), N - 1.001)
        i, j = int(fx), int(fy); tx, ty = fx - i, fy - j; a = self.a
        return float(a[j, i] * (1 - tx) * (1 - ty) + a[j, i + 1] * tx * (1 - ty) + a[j + 1, i] * (1 - tx) * ty + a[j + 1, i + 1] * tx * ty)


def _d(p, q): return math.hypot(q[0] - p[0], q[1] - p[1])
def _unit(v):
    L = math.hypot(v[0], v[1]); return (v[0] / L, v[1] / L) if L > 1e-9 else (1.0, 0.0)
def _ang(v): return math.degrees(math.atan2(v[1], v[0])) % 360.0


class _UF:
    def __init__(self): self.p = {}
    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


TINY = 10.0           # links shorter than this always merge their two nodes
MIN_RADIUS = 3.0      # corner radius floor when a short link needs room
CROSSING = (0.6, 2.5)  # stop setback, crossing width of the city's junctions (city.py builds them so)


def build(city, heights, region=None, natural=None, profiles=None):
    """-> dict(junctions, roads, lanes, report). Iterates: build the network, estimate every junction's trims
    exactly like junction.build_junction does, and where a road is shorter than its two trims first tighten
    the corner radii at its ends (down to MIN_RADIUS), then merge its two junctions. `region` =
    (x0, y0, x1, y1) plan metres keeps only roads with a point inside (a quick partial build)."""
    forced, radius = set(), {}
    for it in range(8):
        net = _build_once(city, heights, region, forced, radius, natural, profiles)
        short = _short_roads(net)
        net["report"]["iterations"] = it + 1
        if not short: break
        for rd, ja, jb, L, need in short:
            tight = [j for j in (ja, jb) if j["kind"] == "junction" and j["corner_radius"] > MIN_RADIUS + 1e-6]
            if tight:
                for j in tight:
                    for m in j["nodes"]: radius[m] = max(MIN_RADIUS, j["corner_radius"] - 2.0)
            else:
                forced.add((ja["nodes"][0], jb["nodes"][0]))
                net["report"]["notes"].append("merged %s + %s: %s is %.1f m, the trims need %.1f m" % (ja["id"], jb["id"], rd["id"], L, need))
    net["report"]["short_roads"] = [(rd["id"], round(L, 1), round(need, 1)) for rd, ja, jb, L, need in _short_roads(net)]
    net["report"]["summary"]["iterations"] = net["report"]["iterations"]
    net["report"]["summary"]["tight_corners"] = len([j for j in net["junctions"] if j["corner_radius"] < 5.0 and j["kind"] == "junction"])
    return net


def layer_offsets(rd):
    """(half, curb, sidewalk) of a plan road from its class profile (the profile fills the right of way: carriageway =
    width, then kerb + sidewalk)."""
    _, v = profile(rd["cls"], bool(rd.get("bridge")))
    sw = v.get("Sidewalk Width Left", 0.0) if v.get("Sidewalk Left", True) else 0.0
    return rd["width"] / 2.0, v.get("Curb Width", 0.25), sw


def junction_trims(j, roads_by_id):
    """{(road id, end): trim} for a junction dict: the same corner rule as the junction builder (junction._corner_rings:
    the asphalt fillet and, at acute corners, where the kerb / sidewalk-back edges cross), from the class profiles."""
    from mathutils import Vector
    from .junction import _corner_rings
    at = j["pos"]; aps = []
    for rid, end in j["approaches"]:
        rd = roads_by_id[rid]; pts = rd["pts"] if end == "start" else rd["pts"][::-1]
        far = next((p for p in pts[1:] if _d(p, at) > 3.0), pts[-1])
        d = _unit((far[0] - at[0], far[1] - at[1])); half, curb, sw = layer_offsets(rd)
        aps.append({"key": (rid, end), "d": Vector((d[0], d[1], 0.0)), "half": half, "half_l": half, "half_r": half, "curb": curb, "swl": sw, "swr": sw})
    aps.sort(key=lambda a: math.atan2(a["d"].y, a["d"].x))
    n = len(aps); out = {}; c = Vector((at[0], at[1], 0.0))
    reach = [0.0] * n
    if n >= 2:
        for i in range(n):
            a, b = aps[i], aps[(i + 1) % n]
            _, _, rings = _corner_rings(c, a, b, j["corner_radius"])
            for pts, _C, _t in rings:
                for p in pts:
                    reach[i] = max(reach[i], (p - c).dot(a["d"])); reach[(i + 1) % n] = max(reach[(i + 1) % n], (p - c).dot(b["d"]))
    for i, a in enumerate(aps): out[a["key"]] = max(reach[i] + 0.3, a["half"] + 1.0)
    return out


from .junction import ZONE_MARGIN  # noqa: E402


def junction_control(j):
    """The MRS junction control of a plan junction: 2 arms none, signal -> signals, stop -> stop, an uncontrolled T ->
    priority, else none (city.py builds the junctions with it)."""
    c = j["control"]; n = len(j["approaches"])
    if n == 2: return "none"
    if c == "signal": return "signals"
    if c == "stop": return "stop"
    if c == "uncontrolled" and n == 3: return "priority"
    return "none"


def end_zone_of(j, rd):
    """The paint zone a junction claims on a road's end (junction.end_zone): its crossing and the end marking its
    control paints (the widest one when it depends on the road's priority)."""
    from .junction import end_zone
    if j is None or j.get("kind") != "junction": return 0.0
    marking = {"signals": "line", "stop": "stop", "priority": "give_way"}.get(junction_control(j))
    return end_zone(True, marking, CROSSING[0], CROSSING[1])


def _short_roads(net):
    by = {r["id"]: r for r in net["roads"]}; J = {j["id"]: j for j in net["junctions"]}
    trims = {}
    for j in net["junctions"]:
        if j["kind"] == "junction": trims.update(junction_trims(j, by))
    out = []
    for rd in net["roads"]:
        # between its trims a road keeps both ends' paint zones (the junction builder's rule, junction.end_zone)
        zones = sum(end_zone_of(J.get("PH_" + rd[e]), rd) for e in ("start", "end")) * (1.0 + ZONE_MARGIN)
        need = trims.get((rd["id"], "start"), 0.0) + trims.get((rd["id"], "end"), 0.0) + zones
        rd["trims"] = (round(trims.get((rd["id"], "start"), 0.0), 2), round(trims.get((rd["id"], "end"), 0.0), 2))
        if rd["length"] < need and rd["start"] != rd["end"]:
            out.append((rd, J["PH_" + rd["start"]], J["PH_" + rd["end"]], rd["length"], need))
    return out


def _adopt_classes(city, N, rep, short=45.0):
    """A short connector between two roads of another class at plain bends (CityForge sometimes draws a 25 m
    'local' piece inside a boulevard) takes the class and width of the road it continues, so the chain stays
    one MRS road instead of two 2-way junctions a few metres apart."""
    roads = [dict(r) for r in city["roads"]]; by = {r["id"]: r for r in roads}
    L = lambda r: _d(N[r["a"]]["pos"], N[r["b"]]["pos"])
    for r in roads:
        if r["bridge"] or L(r) >= short: continue
        nb = []
        for nid in (r["a"], r["b"]):
            es = [by[e] for e in N[nid]["edges"] if e != r["id"]]
            if len(es) == 1 and not es[0]["bridge"]: nb.append(es[0])
        if not nb: continue
        best = max(nb, key=lambda o: (RANK[o["cls"]], o["width"]))
        if (best["cls"], best["width"]) != (r["cls"], r["width"]) and all(L(o) >= short for o in nb):
            rep.setdefault("adopted", []).append({"road": r["id"], "from": r["cls"], "to": best["cls"]})
            r["cls"], r["width"] = best["cls"], best["width"]
    return roads


def _build_once(city, heights, region, forced, radius_override, natural=None, profiles=None):
    rep = {"clusters": [], "absorbed": [], "duplicates": [], "angle_drops": [], "bends": [], "bend_junctions": [], "loops": [], "lanes": [], "notes": [],
           "profile_fallbacks": []}
    designed = profiles if isinstance(profiles, dict) and isinstance(profiles.get("roads"), dict) else None
    N = {n["id"]: n for n in city["nodes"]}
    roads_in = _adopt_classes(city, N, rep)
    R = {r["id"]: r for r in roads_in}
    # ---------------------------------------------------------------- 1. clusters
    uf = _UF()
    for n in city["nodes"]:
        if n["edges"]: uf.find(n["id"])
    for r in roads_in:
        if _d(N[r["a"]]["pos"], N[r["b"]]["pos"]) < TINY: uf.union(r["a"], r["b"])
    for a, b in forced: uf.union(a, b)
    members = {}
    for nid in uf.p: members.setdefault(uf.find(nid), []).append(nid)
    J = {}
    root_of = {m: root for root, ms in members.items() for m in ms}
    for root, ms in members.items():
        # a merged junction sits at the centroid of its nodes weighted by the roads leaving it (rank^2 x width), so
        # boulevards and arterials keep their line and the short stubs of minor streets bend to meet them
        wsum = 0.0; px = py = 0.0
        for m in ms:
            w = sum((RANK[R[e]["cls"]] + 1) ** 2 * R[e]["width"] for e in N[m]["edges"]
                    if root_of.get(R[e]["a"]) != root or root_of.get(R[e]["b"]) != root) or 1e-3
            px += N[m]["pos"][0] * w; py += N[m]["pos"][1] * w; wsum += w
        pos = (px / wsum, py / wsum)
        ctrl = max((N[m]["control"] for m in ms), key=lambda c: CONTROL_RANK.get(c, 0))
        J[root] = {"id": "J%04d" % min(ms), "members": sorted(ms), "pos": pos, "control": ctrl, "edges": []}
        if len(ms) > 1:
            diam = max(_d(N[a]["pos"], N[b]["pos"]) for a in ms for b in ms)
            rep["clusters"].append({"junction": J[root]["id"], "nodes": sorted(ms), "diameter": round(diam, 1)})
    cj = lambda nid: J[uf.find(nid)]
    # ---------------------------------------------------------------- 2. edges between junctions, duplicates
    edges = {}
    for r in roads_in:
        ja, jb = cj(r["a"]), cj(r["b"])
        if ja is jb:
            rep["absorbed"].append(r["id"]); continue
        key = tuple(sorted((ja["id"], jb["id"])))
        old = edges.get(key)
        if old is not None:
            keep, drop = (old, r) if (RANK[old["cls"]], old["width"], _d(N[old["a"]]["pos"], N[old["b"]]["pos"])) >= (RANK[r["cls"]], r["width"], _d(N[r["a"]]["pos"], N[r["b"]]["pos"])) else (r, old)
            edges[key] = keep; rep["duplicates"].append({"kept": keep["id"], "dropped": drop["id"]}); continue
        edges[key] = r
    live = {r["id"]: r for r in edges.values()}
    jid = {j["id"]: j for j in J.values()}

    def ends_of(r):
        return cj(r["a"]), cj(r["b"])

    def dir_from(j, r):
        """Direction from junction j along road r (towards the road's far node, 25 m out at most)."""
        a, b = ends_of(r)
        far = N[r["b"]]["pos"] if a is j else N[r["a"]]["pos"]
        return _unit((far[0] - j["pos"][0], far[1] - j["pos"][1]))
    # ---------------------------------------------------------------- 3. angles
    changed = True
    while changed:
        changed = False
        inc = {}
        for r in live.values():
            a, b = ends_of(r); inc.setdefault(a["id"], []).append(r); inc.setdefault(b["id"], []).append(r)
        for j_id, rs in inc.items():
            if len(rs) < 3: continue
            j = jid[j_id]
            angs = sorted(((_ang(dir_from(j, r)), r) for r in rs), key=lambda t: t[0])
            for k in range(len(angs)):
                (a0, r0), (a1, r1) = angs[k], angs[(k + 1) % len(angs)]
                sep = (a1 - a0) % 360.0
                if sep < MIN_ANGLE:
                    weak = min((r0, r1), key=lambda r: (RANK[r["cls"]], r["width"], _d(N[r["a"]]["pos"], N[r["b"]]["pos"])))
                    live.pop(weak["id"], None)
                    rep["angle_drops"].append({"junction": j_id, "dropped": weak["id"], "name": weak.get("name", ""), "angle": round(sep, 1)})
                    changed = True; break
            if changed: break
    inc = {}
    for r in live.values():
        a, b = ends_of(r); inc.setdefault(a["id"], []).append(r); inc.setdefault(b["id"], []).append(r)
    for j in J.values(): j["edges"] = [r["id"] for r in inc.get(j["id"], [])]
    # ---------------------------------------------------------------- 4. chains through bends
    def same_kind(r1, r2):
        return r1["cls"] == r2["cls"] and r1["width"] == r2["width"] and bool(r1["bridge"]) == bool(r2["bridge"])
    passthrough = {j["id"] for j in J.values() if len(j["edges"]) == 2 and same_kind(live[j["edges"][0]], live[j["edges"][1]])}
    # a bend that cannot take a fillet with room for the inner sidewalk stays a (2-way) junction
    for j_id in sorted(passthrough):
        j = jid[j_id]; r1, r2 = live[j["edges"][0]], live[j["edges"][1]]
        d1, d2 = dir_from(j, r1), dir_from(j, r2)
        turn = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))))
        if turn < 2.0: continue
        need_r = r1["width"] / 2.0 + WALK + 2.0
        t_need = need_r * math.tan(math.radians(turn) / 2.0)
        L1 = _d(N[r1["a"]]["pos"], N[r1["b"]]["pos"]); L2 = _d(N[r2["a"]]["pos"], N[r2["b"]]["pos"])
        if t_need > 0.45 * min(L1, L2) or turn > 100.0:
            passthrough.discard(j_id); rep["bend_junctions"].append({"junction": j_id, "turn": round(turn, 1), "tangent_needed": round(t_need, 1)})
    used = set(); chains = []
    def walk(start_j, r):
        seq_j = [start_j["id"]]; seq_r = [r["id"]]; cur = r; j = start_j
        while True:
            a, b = ends_of(cur); nxt = b if a is j else a
            seq_j.append(nxt["id"])
            if nxt["id"] not in passthrough or nxt["id"] == start_j["id"]: break
            other = next(e for e in nxt["edges"] if e != cur["id"])
            if other in seq_r: break
            seq_r.append(other); cur = live[other]; j = nxt
        return seq_j, seq_r
    for r in sorted(live.values(), key=lambda r: r["id"]):
        if r["id"] in used: continue
        a, b = ends_of(r)
        start = a
        # walk back to a non-passthrough end first
        seen = set()
        cur_j, cur_r = a, r
        while cur_j["id"] in passthrough and cur_j["id"] not in seen:
            seen.add(cur_j["id"])
            other = next(e for e in cur_j["edges"] if e != cur_r["id"])
            o = live[other]; oa, ob = ends_of(o)
            cur_r = o; cur_j = ob if oa is cur_j else oa
        if cur_j["id"] in seen:                              # a closed loop of bends: cut it at this node
            passthrough.discard(cur_j["id"]); rep["loops"].append(cur_j["id"])
        seq_j, seq_r = walk(cur_j, cur_r)
        used.update(seq_r)
        chains.append((seq_j, seq_r))
    # ---------------------------------------------------------------- geometry of each chain
    out_roads = []
    for seq_j, seq_r in chains:
        r0 = live[seq_r[0]]
        pts = [jid[x]["pos"] for x in seq_j]
        bridge = bool(r0["bridge"])
        hw = r0["width"] / 2.0
        poly = _fillet_poly(pts, hw + WALK + 2.0, rep, seq_j)
        if region is not None and not any(region[0] <= p[0] <= region[2] and region[1] <= p[1] <= region[3] for p in poly): continue
        dense = _densify(poly, 6.0)
        name = "PH_" + seq_r[0].replace("road_", "R")
        own = designed["roads"].get(name) if designed else (profiles or {}).get(name)
        extra = {}
        if designed and own is not None:
            P = own["pts"]
            if _d(P[0], dense[0]) < 1e-3 and _d(P[-1], dense[-1]) < 1e-3 and abs(sum(_d(a, b) for a, b in zip(P, P[1:])) - sum(_d(a, b) for a, b in zip(dense, dense[1:]))) < 1e-2:
                dense = [tuple(q) for q in P]                  # the designed line: the same plan line with the landing stations
                z = [float(v) + ASPH for v in own["z"]]
                extra = {"lock_length": own["lock_length"], "max_grade": own["max_grade"], "grade_predicted": own["predicted"],
                         "grade_infeasible": own.get("infeasible", False), "designed": True}
            else:
                rep["profile_fallbacks"].append(name); own = None
        if extra:
            pass
        elif own is not None and not designed and len(own) == len(dense):
            z = [float(v) + ASPH for v in own]            # the road's own vertical alignment (design_heights)
        elif bridge and natural is not None:
            # the deck spans bank to bank at the clearance over the water, ramps at the bridge grade (mrs.grading)
            from . import grading
            ja, jb = jid[seq_j[0]], jid[seq_j[-1]]
            z = [float(v) + ASPH for v in grading.profile(natural, dense, heights(*ja["pos"]), heights(*jb["pos"]), MAX_GRADE["bridge"], 0.0,
                                                          clearance=BRIDGE_CLEARANCE, bridge=True)]
        elif bridge:
            ja, jb = jid[seq_j[0]], jid[seq_j[-1]]
            ha = heights(*ja["pos"]); hb = heights(*jb["pos"]); Ltot = sum(_d(p, q) for p, q in zip(dense, dense[1:])); s = 0.0
            z = []
            for k, p in enumerate(dense):
                if k: s += _d(dense[k - 1], p)
                t = s / max(Ltot, 1e-6); z.append(ha + (hb - ha) * t + 1.2 * math.sin(math.pi * t) + ASPH)
        else:
            z = [heights(*p) + ASPH for p in dense]
        name = "PH_" + seq_r[0].replace("road_", "R")
        out_roads.append(dict({"id": name, "cf_roads": seq_r, "cls": r0["cls"], "width": r0["width"], "bridge": bridge, "street": r0.get("name", ""),
                               "culture": r0.get("culture", ""), "start": seq_j[0], "end": seq_j[-1], "pts": [(p[0], p[1], zz) for p, zz in zip(dense, z)],
                               "length": round(sum(_d(p, q) for p, q in zip(dense, dense[1:])), 2)}, **extra))
    kept = {r["id"] for r in out_roads}
    jz = {}
    deg = {}
    for r in out_roads:
        deg.setdefault(r["start"], []).append((r["id"], "start")); deg.setdefault(r["end"], []).append((r["id"], "end"))
    out_j = []
    for j_id, lst in sorted(deg.items()):
        j = jid[j_id]
        kind = "junction" if len(lst) >= 2 else "dead_end"
        if len(lst) == 2 and j_id in passthrough: continue           # (cannot happen: chains run through these)
        aps = [(next(r for r in out_roads if r["id"] == rid), end) for rid, end in lst]
        if designed and j_id in designed["nodes"]:
            # the designed node height, level: every locked street end meets it exactly at its own height (Lock Z equals
            # the street's level platform), so nothing is blended into the street's grade
            z, plane = designed["nodes"][j_id] + ASPH, (0.0, 0.0)
        else:
            z, plane = junction_plane(heights, j["pos"], [r["pts"] if end == "start" else r["pts"][::-1] for r, end in aps])
            if kind == "dead_end": z, plane = heights(*j["pos"]) + ASPH, (0.0, 0.0)
        cls = [next(r for r in out_roads if r["id"] == rid)["cls"] for rid, _ in lst]
        cr = min(CORNER.get(c, 6.0) for c in cls) if cls else 6.0
        over = [radius_override[m] for m in j["members"] if m in radius_override]
        if over: cr = min(cr, min(over))
        out_j.append({"id": "PH_" + j_id, "nodes": j["members"], "pos": j["pos"], "z": z, "plane": plane, "control": j["control"], "kind": kind,
                      "approaches": lst, "classes": cls, "corner_radius": cr,
                      "bridge": any(next(r for r in out_roads if r["id"] == rid)["bridge"] for rid, _ in lst)})
    for j in out_j: jz[j["id"][3:]] = j["z"]
    for rd in out_roads:
        p0, p1 = rd["pts"][0], rd["pts"][-1]
        if rd["start"] in jz: rd["pts"][0] = (p0[0], p0[1], jz[rd["start"]])
        if rd["end"] in jz: rd["pts"][-1] = (p1[0], p1[1], jz[rd["end"]])
    # ---------------------------------------------------------------- 5. back lanes
    out_lanes = []
    for ln in city.get("lanes", []):
        a, b = tuple(ln["a"]), tuple(ln["b"]); d = _unit((b[0] - a[0], b[1] - a[1]))
        if region is not None and not any(region[0] <= p[0] <= region[2] and region[1] <= p[1] <= region[3] for p in (a, b)): continue
        ends = []
        for p, sgn in ((a, 1.0), (b, -1.0)):
            out = (-d[0] * sgn, -d[1] * sgn)                                 # leaving the lane through this end
            st = _lane_mouth(out_roads, p, out)
            if st is None:
                ends.append({"pos": p, "street": None}); rep["notes"].append("lane %s: no street at %s" % (ln["id"], [round(c, 1) for c in p])); continue
            rd, along, side, c, t = st
            # the lane ends at the street's lot line (back of its sidewalk); city.build refines `back` from the built
            # street's own cross-section
            back = rd["width"] / 2.0 + WALK
            q = (c[0] - out[0] * back, c[1] - out[1] * back)
            ends.append({"pos": q, "street": rd["id"], "along_pos": c, "out": out, "side": side, "dist": round(t, 2)})
        p0, p1 = ends[0]["pos"], ends[1]["pos"]
        dense = _densify([p0, p1], 6.0)
        lid = "PH_" + ln["id"].replace("lane_", "L_"); own = designed["lanes"].get(lid) if designed else (profiles or {}).get(lid)
        zs_ = [float(v) + ASPH for v in own] if own is not None and len(own) == len(dense) else [heights(*p) + ASPH for p in dense]
        out_lanes.append(dict({"id": lid, "cf_lane": ln["id"], "cls": "lane", "width": ln.get("width", 6),
                               "pts": [(p[0], p[1], z_) for p, z_ in zip(dense, zs_)], "ends": ends, "length": round(_d(p0, p1), 2)},
                              **({"max_grade": designed["lane_max_grade"]} if designed else {})))
        rep["lanes"].append(ln["id"])
    rep["summary"] = {"cf_nodes": len([n for n in city["nodes"] if n["edges"]]), "cf_roads": len(roads_in), "mrs_roads": len(out_roads),
                      "junctions": len([j for j in out_j if j["kind"] == "junction"]), "dead_ends": len([j for j in out_j if j["kind"] == "dead_end"]),
                      "lanes": len(out_lanes), "clusters": len(rep["clusters"]), "absorbed": len(rep["absorbed"]), "duplicates": len(rep["duplicates"]),
                      "angle_drops": len(rep["angle_drops"]), "bend_junctions": len(rep["bend_junctions"]), "fillets": len(rep["bends"]),
                      "road_km": round(sum(r["length"] for r in out_roads) / 1000.0, 2), "lane_km": round(sum(l["length"] for l in out_lanes) / 1000.0, 2)}
    return {"junctions": out_j, "roads": out_roads, "lanes": out_lanes, "report": rep}


def planarize(city, margin=1.0, min_split=6.0, max_rounds=200):
    """Make the road graph planar before anything is built (in place; returns a report): roads only touch where they
    share a node. A node lying in another road's corridor (within its half width + sidewalk + `margin`, off its ends)
    splits that road there and moves onto it (a T-junction); two segments crossing in plan (neither a bridge) split
    at a new node. Collinear overlapping edges become duplicates between the same nodes (build drops them). Without
    this a boulevard ran straight through six downtown junctions it was not part of."""
    nodes = {n["id"]: n for n in city["nodes"]}; roads = {r["id"]: r for r in city["roads"]}
    rep = {"snapped": [], "crossings": [], "conflicts": []}
    fixed = set()                                  # nodes already moved onto a road: they never move again
    next_node = max(nodes) + 1; k_road = [0]

    def corridor(r): return r["width"] / 2.0 + WALK + margin

    def split(r, nid):
        """r (a -> b) becomes a -> nid and a new road nid -> b."""
        nonlocal roads
        k_road[0] += 1; rid = "%s_s%d" % (r["id"], k_road[0])
        r2 = dict(r, id=rid, a=nid, profile=[], heights=[])
        b = r["b"]; r["b"] = nid; r["profile"] = []; r["heights"] = []
        nodes[b]["edges"] = [rid if e == r["id"] else e for e in nodes[b]["edges"]]
        nodes[nid]["edges"] += [r["id"], rid]
        roads[rid] = r2; city["roads"].append(r2)
        return r2

    def project(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        if L2 < 1e-9: return None
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
        q = (a[0] + dx * t, a[1] + dy * t)
        return t, q, math.sqrt(L2), _d(p, q)

    for _ in range(max_rounds):
        changed = False
        # 1. a node in another road's corridor: split that road at the node's projection and move the node onto it
        for nid, n in list(nodes.items()):
            if not n["edges"]: continue
            for r in list(roads.values()):
                if r.get("bridge") or nid in (r["a"], r["b"]): continue
                if any(roads[e].get("bridge") for e in n["edges"] if e in roads): continue
                pa, pb = nodes[r["a"]]["pos"], nodes[r["b"]]["pos"]
                pr = project(n["pos"], pa, pb)
                if pr is None: continue
                t, q, L, d = pr
                if d > corridor(r) or t * L < min_split or (1.0 - t) * L < min_split: continue
                if nid in fixed and d > 2.0:
                    if (nid, r["id"]) not in {(c_["node"], c_["road"]) for c_ in rep["conflicts"]}:
                        rep["conflicts"].append({"node": nid, "road": r["id"], "distance": round(d, 2)})
                    continue
                rep["snapped"].append({"node": nid, "road": r["id"], "moved": round(d, 2)}); fixed.add(nid)
                n["pos"] = [round(q[0], 3), round(q[1], 3)]
                split(r, nid)
                if n.get("control", "none") == "none": n["control"] = "uncontrolled"
                changed = True; break
        # 2. segments crossing in plan: a new node at the crossing, both split
        rl = [r for r in roads.values() if not r.get("bridge")]
        for i in range(len(rl)):
            for j in range(i + 1, len(rl)):
                r1, r2 = rl[i], rl[j]
                if {r1["a"], r1["b"]} & {r2["a"], r2["b"]}: continue
                a, b = nodes[r1["a"]]["pos"], nodes[r1["b"]]["pos"]; c_, d_ = nodes[r2["a"]]["pos"], nodes[r2["b"]]["pos"]
                den = (b[0] - a[0]) * (d_[1] - c_[1]) - (b[1] - a[1]) * (d_[0] - c_[0])
                if abs(den) < 1e-9: continue
                t = ((c_[0] - a[0]) * (d_[1] - c_[1]) - (c_[1] - a[1]) * (d_[0] - c_[0])) / den
                u = ((c_[0] - a[0]) * (b[1] - a[1]) - (c_[1] - a[1]) * (b[0] - a[0])) / den
                L1, L2 = _d(a, b), _d(c_, d_)
                if not (min_split / L1 < t < 1 - min_split / L1 and min_split / L2 < u < 1 - min_split / L2): continue
                p = [round(a[0] + (b[0] - a[0]) * t, 3), round(a[1] + (b[1] - a[1]) * t, 3)]
                major = RANK[r1["cls"]] >= 3 and RANK[r2["cls"]] >= 3
                nodes[next_node] = {"id": next_node, "pos": p, "h": None, "control": "signal" if major else "uncontrolled", "edges": []}
                city["nodes"].append(nodes[next_node])
                split(r1, next_node); split(r2, next_node)
                rep["crossings"].append({"node": next_node, "roads": [r1["id"], r2["id"]], "at": p})
                next_node += 1; changed = True
                break
            if changed: break
        if not changed: break
    # 3. a road whose corridor still runs over a junction it does not join, starting / ending close to it: its near end
    #    joins that junction (one junction where there were two overlapping ones)
    for cf in list(rep["conflicts"]):
        f, r = cf["node"], roads.get(cf["road"])
        if r is None: continue
        near = min((r["a"], r["b"]), key=lambda e: _d(nodes[e]["pos"], nodes[f]["pos"]))
        if _d(nodes[near]["pos"], nodes[f]["pos"]) > 1.6 * corridor(r) or near == f: continue
        for e in list(nodes[near]["edges"]):
            rr = roads.get(e)
            if rr is None: continue
            if f in (rr["a"], rr["b"]):                 # the short link between the two: gone
                other = rr["b"] if rr["a"] == f else rr["a"]
                nodes[f]["edges"].remove(e); nodes[other]["edges"] = [x for x in nodes[other]["edges"] if x != e]
                city["roads"].remove(rr); del roads[e]; continue
            if rr["a"] == near: rr["a"] = f
            if rr["b"] == near: rr["b"] = f
            rr["profile"] = []; rr["heights"] = []
            nodes[f]["edges"].append(e)
        nodes[near]["edges"] = []
        rep["merged"] = rep.get("merged", []) + [{"node": near, "into": f}]
        rep["conflicts"].remove(cf)
    for n in nodes.values():                       # new nodes: heights from their roads' ends (h is informational)
        if n.get("h") is None: n["h"] = 0.0
    return rep


def bridge_gaps(city, natural, max_span=160.0, aligned=0.95, probe=40.0):
    """Join dead-end streets that face each other across water with a bridge road (in place; returns the new
    roads). A dead end qualifies when water lies ahead of it within `probe` m; a pair qualifies when each points at
    the other (cosine >= `aligned`), they are at most `max_span` m apart and the line between them crosses water.
    The bridge takes the lower class of the two streets and the first one's name."""
    nodes = {n["id"]: n for n in city["nodes"]}; roads = {r["id"]: r for r in city["roads"]}
    ends = []
    for nid, n in nodes.items():
        if len(n["edges"]) != 1: continue
        r = roads.get(n["edges"][0])
        if r is None: continue
        other = nodes[r["b"] if r["a"] == nid else r["a"]]["pos"]; p = n["pos"]
        d = _unit((p[0] - other[0], p[1] - other[1]))
        if any(natural.wet(p[0] + d[0] * k, p[1] + d[1] * k) for k in range(2, int(probe) + 1, 2)): ends.append((nid, p, d, r))
    added = []; used = set()
    for i, (n1, p1, d1, r1) in enumerate(ends):
        for n2, p2, d2, r2 in ends[i + 1:]:
            if n1 in used or n2 in used: continue
            L = _d(p1, p2)
            if L > max_span or L < 1.0: continue
            u = _unit((p2[0] - p1[0], p2[1] - p1[1]))
            if u[0] * d1[0] + u[1] * d1[1] < aligned or -(u[0] * d2[0] + u[1] * d2[1]) < aligned: continue
            wet = sum(natural.wet(p1[0] + u[0] * L * k / 20, p1[1] + u[1] * L * k / 20) for k in range(21))
            if wet < 3: continue
            weak = min((r1, r2), key=lambda r: (RANK[r["cls"]], r["width"]))
            rid = "road_br%02d" % len(added)
            br = dict(weak, id=rid, a=n1, b=n2, bridge=True, name=r1.get("name") or r2.get("name", ""), profile=[], heights=[])
            city["roads"].append(br); nodes[n1]["edges"].append(rid); nodes[n2]["edges"].append(rid)
            used.update((n1, n2)); added.append({"id": rid, "a": n1, "b": n2, "span": round(L, 1), "cls": br["cls"], "name": br["name"]})
    return added


def design_heights(net, natural, feather=10.0, table=None):
    """(Heights, report, profiles) for the network built on the NATURAL terrain: every street's vertical alignment
    designed on what is built (mrs.grading.network_profiles_landed). Each locked street end is level over its
    junction's footprint and a platform past it (to the paint zone, at least the blur reach), climbs at most
    LANDING_GRADE over its lock zone (so road.py's level-arriving lock and the crown fading in stay within the class
    maximum), then eases into the class maximum over a vertical curve; node heights are relaxed on that capacity,
    within EARTH_HARD of the natural ground. Junctions are built level at the designed node height. Every street's
    built grade is predicted with grading.rail_model. `profiles`: {"roads": {id: {pts, z, lock_length, max_grade,
    predicted, infeasible}}, "nodes": {node: z}, "lanes": {id: z}, "lane_max_grade": g}; feed it back to build()."""
    from . import grading
    table = table or MAX_GRADE
    J = {j["id"][3:]: j for j in net["junctions"]}
    nodes = {k: tuple(j["pos"]) for k, j in J.items()}
    m_flat = COMMON["Smoothing"] * COMMON["Resolution"]          # the blur reach: the platform past a footprint is at least this
    edges, meta = [], []
    for rd in net["roads"]:
        for key, p in ((rd["start"], rd["pts"][0]), (rd["end"], rd["pts"][-1])): nodes.setdefault(key, (p[0], p[1]))
        P2 = [(p[0], p[1]) for p in rd["pts"]]; S = float(grading._stations(P2)[-1])
        ja, jb = J.get(rd["start"]), J.get(rd["end"])
        la = ja is not None and ja["kind"] == "junction"; lb = jb is not None and jb["kind"] == "junction"
        ta, tb = rd.get("trims", (0.0, 0.0)); ta = float(ta) if la else 0.0; tb = float(tb) if lb else 0.0
        live = S - ta - tb
        k = "bridge" if rd["bridge"] else rd["cls"]
        G = table[k] - GRADE_MARGIN
        ch = crown_h(rd["cls"], rd["bridge"])
        LL = lock_length(ch, G, live, int(la) + int(lb)) if (la or lb) else LOCK_MAX
        fa = max(m_flat, end_zone_of(ja, rd)) if la else m_flat
        fb = max(m_flat, end_zone_of(jb, rd)) if lb else m_flat
        land_a = max(LL + m_flat, fa); land_b = max(LL + m_flat, fb)
        gl = min(LANDING_GRADE, max(0.0, (G - 1.5 * ch / max(LL, 1e-6)) / grading.LOCK_K))
        vc = VC_K * 100.0 * (G - gl)
        br = [ta, S - tb]
        if la: br += [ta + fa, ta + land_a, ta + land_a + vc]
        if lb: br += [S - tb - fb, S - tb - land_b, S - tb - land_b - vc]
        pts = grading.insert_stations(P2, br)
        edges.append({"a": rd["start"], "b": rd["end"], "pts": pts, "bridge": bool(rd["bridge"]), "max_grade": G, "smooth": SMOOTH.get(rd["cls"], 30.0),
                      "clearance": BRIDGE_CLEARANCE, "ends": ((ta, land_a if la else 0.0), (tb, land_b if lb else 0.0)), "land_grade": gl, "vc": vc,
                      "flat": (fa, fb)})
        meta.append({"rd": rd, "la": la, "lb": lb, "ta": ta, "tb": tb, "LL": LL, "live": live, "G": table[k], "ch": ch, "gl": gl})
    info = {}
    zn, zs = grading.network_profiles_landed(natural, nodes, edges, iterations=2000, tol=1e-4, info=info, max_move=EARTH_HARD)
    roads_prof = {}; predicted = {}
    for i, (e, z, m) in enumerate(zip(edges, zs, meta)):
        rd = m["rd"]
        P3 = [(x, y, float(zz) + ASPH) for (x, y), zz in zip(e["pts"], z)]
        o = grading.rail_model(P3, m["ta"], m["tb"], m["la"], m["lb"], zn[rd["start"]] + ASPH, zn[rd["end"]] + ASPH, m["LL"], m["ch"],
                               COMMON["Resolution"], COMMON["Smoothing"])
        pred = 0.0
        if o is not None:
            _a, plan, z_rail, z_crest = o
            pred = max(grading.window_grades(plan, z_crest, GRADE_WINDOW)[0], grading.window_grades(plan, z_rail, GRADE_WINDOW)[0])
        predicted[rd["id"]] = pred
        roads_prof[rd["id"]] = {"pts": [(float(x), float(y)) for x, y in e["pts"]], "z": [round(float(v), 4) for v in z], "lock_length": round(m["LL"], 3),
                                "max_grade": m["G"], "predicted": round(pred, 4), "infeasible": i in info["infeasible"]}
    streets = [{"pts": e["pts"], "z": z, "half": rd["width"] / 2.0 + WALK + 0.5} for e, z, rd in zip(edges, zs, net["roads"]) if not rd["bridge"]]
    f1 = grading.Field(grading.corridor_field(natural, streets, feather), natural.cell, (natural.ox, natural.oy), natural.water, natural.wl)
    lanes = []; lanes_prof = {}
    for ln in net["lanes"]:
        pts = [(p[0], p[1]) for p in ln["pts"]]
        z = grading.profile(f1, pts, f1(*pts[0]), f1(*pts[-1]), table["lane"] - GRADE_MARGIN, SMOOTH["lane"])
        lanes.append({"pts": pts, "z": z, "half": float(ln.get("width", 6)) / 2.0 + 1.0})
        lanes_prof[ln["id"]] = [round(float(v), 3) for v in z]
    h = grading.corridor_field(f1, lanes, feather * 0.5)
    # earthwork: each node against its natural (or bridge-lifted) height, and each junction's level footprint against
    # the natural ground along its arms out to the platform's end (centre and both sidewalk edges)
    zref = {k: max(info["z_nat"][k], info["lifted"].get(k, -1e9)) for k in zn}
    moves = {k: zn[k] - zref[k] for k in zn}
    foot = {}
    for e, m in zip(edges, meta):
        rd = m["rd"]; half = rd["width"] / 2.0 + WALK
        for key, la_, t, f, sgn in ((rd["start"], m["la"], m["ta"], e["flat"][0], 1), (rd["end"], m["lb"], m["tb"], e["flat"][1], -1)):
            if not la_: continue
            pts = e["pts"] if sgn > 0 else e["pts"][::-1]; st = grading._stations(pts); reach = t + f
            for d in np.linspace(0.0, min(reach, st[-1]), 8):
                x = float(np.interp(d, st, [p[0] for p in pts])); y = float(np.interp(d, st, [p[1] for p in pts]))
                x2 = float(np.interp(min(d + 1.0, st[-1]), st, [p[0] for p in pts])); y2 = float(np.interp(min(d + 1.0, st[-1]), st, [p[1] for p in pts]))
                u = _unit((x2 - x, y2 - y)); n = (-u[1], u[0])
                for off in (0.0, half, -half):
                    px, py = x + n[0] * off, y + n[1] * off
                    if natural.wet(px, py): continue
                    dz = zn[key] - natural(px, py)
                    if abs(dz) > abs(foot.get(key, 0.0)): foot[key] = dz
    mv = np.abs(np.array(list(moves.values()))) if moves else np.zeros(1)
    over = sorted([(k, round(v, 2)) for k, v in moves.items() if abs(v) > EARTH_MAX], key=lambda t: -abs(t[1]))
    fv = np.abs(np.array(list(foot.values()))) if foot else np.zeros(1)
    by_cls = {}
    for m in meta:
        c = "bridge" if m["rd"]["bridge"] else m["rd"]["cls"]
        by_cls[c] = max(by_cls.get(c, 0.0), predicted[m["rd"]["id"]] / max(m["G"], 1e-6))
    rep = {"nodes": len(zn), "edges": len(edges), "sweeps": info["iterations"],
           "residual": {net["roads"][i]["id"]: round(r, 3) for i, r in info["residual"].items()},
           "infeasible": [{"road": net["roads"][i]["id"], "cf_roads": net["roads"][i]["cf_roads"]} for i in info["infeasible"]],
           "predicted_over": sorted([(m["rd"]["id"], round(100 * predicted[m["rd"]["id"]], 2)) for m in meta if predicted[m["rd"]["id"]] > m["G"] + GRADE_MARGIN], key=lambda t: -t[1]),
           "predicted_ratio_by_class": {k: round(v, 3) for k, v in by_cls.items()},
           "earthwork": {"node_max": round(float(mv.max()), 2), "node_p90": round(float(np.percentile(mv, 90)), 2), "over_bound": over,
                         "footprint_max": round(float(fv.max()), 2), "footprint_p90": round(float(np.percentile(fv, 90)), 2),
                         "footprint_over": sorted([(k, round(v, 2)) for k, v in foot.items() if abs(v) > EARTH_MAX], key=lambda t: -abs(t[1]))[:20]},
           "lock_length": {"min": round(min([m["LL"] for m in meta] or [0]), 2), "max": round(max([m["LL"] for m in meta] or [0]), 2)},
           "_info": info, "_capacity": {rd["id"]: c for rd, c in zip(net["roads"], info["capacity"])}, "_zref": zref, "_zn": zn}
    profiles = {"roads": roads_prof, "nodes": {k: float(v) for k, v in zn.items()}, "lanes": lanes_prof, "lane_max_grade": table["lane"]}
    return Heights(h, natural.cell), rep, profiles


def design_network(city, natural, region=None, rounds=4, log=print):
    """(net0, Heights, report, profiles): the network built on the natural terrain and designed (design_heights), with
    the earthwork bound applied: a junction moved more than EARTH_MAX from its natural (or bridge) height by an
    optional link (a planner connector, family "conn") whose two ends stay connected without it loses that link (the
    city's road dict and its nodes; city["mrs_steep_drops"] records it), and the network is rebuilt and redesigned.
    Junctions that no droppable link explains stay, reported in report["earthwork"]["over_bound"]."""
    table = grade_table(city)
    fam = {r["id"]: r.get("family", "") for r in city["roads"]}
    for rnd in range(1, rounds + 1):
        net0 = build(city, Heights(natural.h, natural.cell), region, natural=natural)
        H, rep, prof = design_heights(net0, natural, table=table)
        cap = rep.pop("_capacity"); zref = rep.pop("_zref"); zn = rep.pop("_zn"); rep.pop("_info", None)
        new = []
        for k, _mv in rep["earthwork"]["over_bound"]:
            inc = [r for r in net0["roads"] if k in (r["start"], r["end"])]
            if not inc: continue
            worst = max(inc, key=lambda r: abs(zref.get(r["end"], 0.0) - zref.get(r["start"], 0.0)) - cap.get(r["id"], 0.0))
            conn = [c for c in worst["cf_roads"] if fam.get(c) == "conn"]
            adj = {}
            for r in net0["roads"]:
                if r["id"] == worst["id"]: continue
                adj.setdefault(r["start"], set()).add(r["end"]); adj.setdefault(r["end"], set()).add(r["start"])
            seen = {worst["start"]}; st = [worst["start"]]
            while st:
                for m_ in adj.get(st.pop(), ()):
                    if m_ not in seen: seen.add(m_); st.append(m_)
            connected = worst["end"] in seen
            log("EARTHWORK round %d: %s moved %.2f m beyond its natural / bridge height, pulled by %s %s; connector pieces %s; network connected without it: %s"
                % (rnd, k, zn[k] - zref[k], worst["id"], worst["cf_roads"], conn, connected))
            if conn and connected: new += [c for c in conn if c not in new]
        if not new: break
        drop = set(new)
        city["roads"] = [r for r in city["roads"] if r["id"] not in drop]
        for nd in city["nodes"]: nd["edges"] = [e for e in nd["edges"] if e not in drop]
        city.setdefault("mrs_steep_drops", []).extend(sorted(drop))
    rep["rounds"] = rnd; rep["steep_drops"] = list(city.get("mrs_steep_drops", []))
    return net0, H, rep, prof


def junction_plane(heights, at, approaches, reach=22.0):
    """(z at the centre, (gx, gy)): least-squares plane through the road profiles (pts z, else the heights + asphalt) of the approaches,
    0-`reach` m out from the junction, so the locked road ends blend into it; the grade is capped at MAX_PLANE_GRADE
    (a steeper junction is levelled that much)."""
    xs, ys, zs = [0.0], [0.0], [heights(*at) + ASPH]
    for pts in approaches:
        s = 0.0; nxt = 2.0
        for a, b in zip(pts, pts[1:]):
            L = _d(a, b)
            while nxt <= s + L and nxt <= reach:
                f = (nxt - s) / L; x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                # the approach's own profile when it has one (a bridge deck is not the river bed under it)
                z = a[2] + (b[2] - a[2]) * f if len(a) > 2 and len(b) > 2 else heights(x, y) + ASPH
                xs.append(x - at[0]); ys.append(y - at[1]); zs.append(z); nxt += 2.0
            s += L
            if nxt > reach: break
    A = np.column_stack([np.ones(len(xs)), xs, ys]); c = np.linalg.lstsq(A, np.array(zs), rcond=None)[0]
    gx, gy = float(c[1]), float(c[2]); g = math.hypot(gx, gy)
    if g > MAX_PLANE_GRADE: gx, gy = gx * MAX_PLANE_GRADE / g, gy * MAX_PLANE_GRADE / g
    z0 = float(np.mean(zs) - gx * np.mean(xs) - gy * np.mean(ys))
    return z0, (round(gx, 5), round(gy, 5))


def _fillet_poly(pts, r_need, rep, seq_j):
    """Polyline through the chain's junction centres; each interior vertex gets a circular arc (points every
    2.5 m) whose radius keeps `r_need` where the segments allow (tangent <= 45 % of the shorter segment)."""
    if len(pts) <= 2: return list(pts)
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        p0, p1, p2 = pts[k - 1], pts[k], pts[k + 1]
        u = _unit((p0[0] - p1[0], p0[1] - p1[1])); v = _unit((p2[0] - p1[0], p2[1] - p1[1]))
        inner = math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))         # angle between the two legs
        turn = math.pi - inner
        if turn < math.radians(2.0):
            out.append(p1); continue
        t_max = 0.45 * min(_d(p0, p1), _d(p1, p2))
        R = min(max(r_need, 12.0) * 1.5, t_max / math.tan(turn / 2.0))
        t = R * math.tan(turn / 2.0)
        a = (p1[0] + u[0] * t, p1[1] + u[1] * t); b = (p1[0] + v[0] * t, p1[1] + v[1] * t)
        bis = _unit((u[0] + v[0], u[1] + v[1])); cdist = R / math.sin(inner / 2.0)
        c = (p1[0] + bis[0] * cdist, p1[1] + bis[1] * cdist)
        a0 = math.atan2(a[1] - c[1], a[0] - c[0]); a1 = math.atan2(b[1] - c[1], b[0] - c[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        n = max(2, int(abs(da) * R / 2.5))
        out += [(c[0] + R * math.cos(a0 + da * i / n), c[1] + R * math.sin(a0 + da * i / n)) for i in range(n + 1)]
        rep["bends"].append({"junction": seq_j[k], "turn": round(math.degrees(turn), 1), "radius": round(R, 1)})
    out.append(pts[-1])
    return out


def _densify(poly, step):
    out = [poly[0]]
    for p, q in zip(poly, poly[1:]):
        L = _d(p, q); n = max(1, int(math.ceil(L / step)))
        out += [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(1, n + 1)]
    return out


def _project_poly(pts, p):
    """(distance, along, side 'r'/'l', point) of p's projection on a polyline (side: right of the direction)."""
    best = None; s = 0.0
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        if L2 < 1e-12: continue
        f = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        q = (a[0] + dx * f, a[1] + dy * f); dd = _d(p, q)
        if best is None or dd < best[0]:
            cross = dx * (p[1] - a[1]) - dy * (p[0] - a[0])
            best = (dd, s + math.sqrt(L2) * f, "l" if cross > 0 else "r", q)
        s += math.sqrt(L2)
    return best


def _lane_mouth(roads, p, out, back=3.0, reach=30.0):
    """Where a back lane leaving through p (unit direction `out`) meets a street: the nearest crossing of the ray
    p + out * t (-back <= t <= reach) with a road centre line -> (road, along, side of the street the lane is on,
    crossing point, t). Geometric, so it holds whatever the street's width or a shifted (filleted) centre line."""
    best = None
    inner = (p[0] - out[0] * 5.0, p[1] - out[1] * 5.0)
    for rd in roads:
        s = 0.0; pts = rd["pts"]
        for a, b in zip(pts, pts[1:]):
            ex, ey = b[0] - a[0], b[1] - a[1]; L = math.hypot(ex, ey)
            if L < 1e-9: continue
            den = out[0] * ey - out[1] * ex
            if abs(den) > 1e-9 * L:
                wx, wy = a[0] - p[0], a[1] - p[1]
                t = (wx * ey - wy * ex) / den; u = (wx * out[1] - wy * out[0]) / den
                if 0.0 <= u <= 1.0 and -back <= t <= reach and (best is None or t < best[4]):
                    side = "l" if ex * (inner[1] - a[1]) - ey * (inner[0] - a[0]) > 0 else "r"
                    best = (rd, s + L * u, side, (p[0] + out[0] * t, p[1] + out[1] * t), t)
            s += L
    return best


def nearest_road(roads, p, max_d=40.0, index=None):
    """(road, along, side, distance) of the road centre line nearest p (for doors, bus stops, props)."""
    cand = roads if index is None else index.near(p)
    best = None
    for rd in cand:
        pr = _project_poly(rd["pts"], p)
        if pr is not None and pr[0] <= max_d and (best is None or pr[0] < best[3]): best = (rd, pr[1], pr[2], pr[0])
    return best


class RoadIndex:
    """Grid index of road polylines (64 m cells) for nearest-road queries over thousands of points."""
    def __init__(self, roads, cell=64.0):
        self.cell = cell; self.g = {}
        for rd in roads:
            ks = set()
            for p in rd["pts"]:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1): ks.add((int(p[0] // cell) + dx, int(p[1] // cell) + dy))
            for k in ks: self.g.setdefault(k, []).append(rd)

    def near(self, p):
        return self.g.get((int(p[0] // self.cell), int(p[1] // self.cell)), [])


if __name__ == "__main__":
    import sys
    city = json.load(open(sys.argv[1], encoding="utf-8"))
    H = Heights.load(sys.argv[2], city["grid"], city["cell_m"])
    net = build(city, H)
    print(json.dumps(net["report"]["summary"], indent=1))
    for k in ("clusters", "duplicates", "angle_drops", "bend_junctions", "loops"):
        print(k, net["report"][k][:12])
    print("notes", net["report"]["notes"][:8])
