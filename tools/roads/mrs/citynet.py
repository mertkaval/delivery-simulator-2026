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
COMMON = {"Conform": False, "Embankment": False, "Superelevation": 0.0, "Curb Width": 0.25, "Curb Height": 0.15,
          "Sidewalk Left": True, "Sidewalk Right": True, "Sidewalk Width Left": WALK - 0.25, "Sidewalk Width Right": WALK - 0.25,
          "Light Side": "None", "Prop Side": "None", "Tree Side": "None", "Scatter Density": 0.0, "Edge Depth": EDGE_DEPTH}
PROFILES = {
    "local": dict(preset="residential", **{"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 3.0, "Parking Left": 2.5, "Parking Right": 2.5,
                                           "Centre Line": "None", "Edge Lines": False, "Lane Arrows": False, "Parking Ticks": False,
                                           "Planting Strip Left": 1.35, "Planting Strip Right": 1.35, "Median": 0.0, "Bike Left": "None", "Bike Right": "None"}),
    "arterial": dict(preset="urban", **{"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.25, "Parking Left": 0.0, "Parking Right": 0.0, "Median": 0.0,
                                        "Centre Line": "Double", "Edge Lines": False, "Bike Left": "Buffered", "Bike Right": "Buffered", "Bike Width": 1.8, "Bike Buffer": 0.7,
                                        "Planting Strip Left": 1.35, "Planting Strip Right": 1.35}),
    "boulevard": dict(preset="urban", **{"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.4, "Parking Left": 0.0, "Parking Right": 0.0, "Median": 4.4,
                                         "Centre Line": "None", "Edge Lines": False, "Bike Left": "None", "Bike Right": "None",
                                         "Planting Strip Left": 1.35, "Planting Strip Right": 1.35}),
    "downtown": dict(preset="urban", **{"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.0, "Parking Left": 2.0, "Parking Right": 2.0, "Median": 0.0,
                                        "Centre Line": "Double", "Edge Lines": False, "Bike Left": "None", "Bike Right": "None",
                                        "Planting Strip Left": 0.0, "Planting Strip Right": 0.0}),
    "bridge": dict(preset="bridge", **{"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.25, "Shoulder": 2.5, "Median": 0.0,
                                       "Sidewalk Width Left": 2.2, "Sidewalk Width Right": 2.2, "Centre Line": "Double", "Light Side": "None",
                                       "Planting Strip Left": 0.0, "Planting Strip Right": 0.0, "Pillar Spacing": 32.0}),
    "lane": dict(preset="service", **{"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 2.75, "Shoulder": 0.25, "Curb Height": 0.0, "Curb Width": 0.1,
                                      "Sidewalk Left": False, "Sidewalk Right": False, "Centre Line": "None", "Edge Lines": False, "Lane Arrows": False,
                                      "Crown": 1.0, "Edge Depth": 0.8}),
}
SPEED = {"local": 30, "downtown": 40, "arterial": 50, "boulevard": 50, "lane": 20}
STYLE = {"local": "residential", "downtown": "avenue", "arterial": "avenue", "boulevard": "boulevard", "lane": "residential"}


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
GAP = 2.0             # road left between two junction trims (m)


def build(city, heights, region=None):
    """-> dict(junctions, roads, lanes, report). Iterates: build the network, estimate every junction's trims
    exactly like junction.build_junction does, and where a road is shorter than its two trims first tighten
    the corner radii at its ends (down to MIN_RADIUS), then merge its two junctions. `region` =
    (x0, y0, x1, y1) plan metres keeps only roads with a point inside (a quick partial build)."""
    forced, radius = set(), {}
    for it in range(8):
        net = _build_once(city, heights, region, forced, radius)
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


def _fillet_reach(at, a, b, R):
    """Station along approach a (from `at`) of the corner tangent point between a's left edge and b's right
    edge, as junction._fillet computes it (radius clamped to 12 m tangent); None for a straight-on corner."""
    da, db = a["d"], b["d"]
    span = (_ang(db) - _ang(da)) % 360.0
    if span > 150.0: return 0.0
    la = (da[1], -da[0]); lb = (db[1], -db[0])
    pa = (at[0] - la[0] * a["half"], at[1] - la[1] * a["half"]); pb = (at[0] + lb[0] * b["half"], at[1] + lb[1] * b["half"])
    den = da[0] * db[1] - da[1] * db[0]
    if abs(den) < 1e-9: return None
    s = ((pb[0] - pa[0]) * db[1] - (pb[1] - pa[1]) * db[0]) / den
    C = (pa[0] + da[0] * s, pa[1] + da[1] * s)
    theta = math.acos(max(-1.0, min(1.0, da[0] * db[0] + da[1] * db[1])))
    if theta < 1e-3 or abs(math.pi - theta) < 1e-3: return None
    r = min(R, 12.0 * math.tan(theta / 2.0)); t = r / math.tan(theta / 2.0)
    return (C[0] - at[0]) * da[0] + (C[1] - at[1]) * da[1] + t


def junction_trims(j, roads_by_id):
    """{(road id, end): trim} for a junction dict (approach directions from the road polylines)."""
    at = j["pos"]; aps = []
    for rid, end in j["approaches"]:
        rd = roads_by_id[rid]; pts = rd["pts"] if end == "start" else rd["pts"][::-1]
        far = next((p for p in pts[1:] if _d(p, at) > 3.0), pts[-1])
        aps.append({"key": (rid, end), "d": _unit((far[0] - at[0], far[1] - at[1])), "half": rd["width"] / 2.0})
    aps.sort(key=lambda a: _ang(a["d"]))
    n = len(aps); out = {}
    for i, a in enumerate(aps):
        reach = 0.0
        for c, dd in (((aps[i - 1], a), 1), ((a, aps[(i + 1) % n]), 0)):
            r = _fillet_reach(at, c[0], c[1], j["corner_radius"]) if dd == 0 else _fillet_reach_b(at, c[0], c[1], j["corner_radius"])
            if r is not None: reach = max(reach, r)
        out[a["key"]] = max(reach + 0.3, a["half"] + 1.0)
    return out


def _fillet_reach_b(at, a, b, R):
    """Station along b (the CCW-later approach) of the tangent point of the corner (a, b)."""
    da, db = a["d"], b["d"]
    span = (_ang(db) - _ang(da)) % 360.0
    if span > 150.0: return 0.0
    la = (da[1], -da[0]); lb = (db[1], -db[0])
    pa = (at[0] - la[0] * a["half"], at[1] - la[1] * a["half"]); pb = (at[0] + lb[0] * b["half"], at[1] + lb[1] * b["half"])
    den = da[0] * db[1] - da[1] * db[0]
    if abs(den) < 1e-9: return None
    s = ((pb[0] - pa[0]) * db[1] - (pb[1] - pa[1]) * db[0]) / den
    C = (pa[0] + da[0] * s, pa[1] + da[1] * s)
    theta = math.acos(max(-1.0, min(1.0, da[0] * db[0] + da[1] * db[1])))
    if theta < 1e-3 or abs(math.pi - theta) < 1e-3: return None
    r = min(R, 12.0 * math.tan(theta / 2.0)); t = r / math.tan(theta / 2.0)
    return (C[0] - at[0]) * db[0] + (C[1] - at[1]) * db[1] + t


def _short_roads(net):
    by = {r["id"]: r for r in net["roads"]}; J = {j["id"]: j for j in net["junctions"]}
    trims = {}
    for j in net["junctions"]:
        if j["kind"] == "junction": trims.update(junction_trims(j, by))
    out = []
    for rd in net["roads"]:
        need = trims.get((rd["id"], "start"), 0.0) + trims.get((rd["id"], "end"), 0.0) + GAP
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


def _build_once(city, heights, region, forced, radius_override):
    rep = {"clusters": [], "absorbed": [], "duplicates": [], "angle_drops": [], "bends": [], "bend_junctions": [], "loops": [], "lanes": [], "notes": []}
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
        if bridge:
            ja, jb = jid[seq_j[0]], jid[seq_j[-1]]
            ha = heights(*ja["pos"]); hb = heights(*jb["pos"]); Ltot = sum(_d(p, q) for p, q in zip(dense, dense[1:])); s = 0.0
            z = []
            for k, p in enumerate(dense):
                if k: s += _d(dense[k - 1], p)
                t = s / max(Ltot, 1e-6); z.append(ha + (hb - ha) * t + 1.2 * math.sin(math.pi * t) + ASPH)
        else:
            z = [heights(*p) + ASPH for p in dense]
        name = "PH_" + seq_r[0].replace("road_", "R")
        out_roads.append({"id": name, "cf_roads": seq_r, "cls": r0["cls"], "width": r0["width"], "bridge": bridge, "street": r0.get("name", ""),
                          "culture": r0.get("culture", ""), "start": seq_j[0], "end": seq_j[-1], "pts": [(p[0], p[1], zz) for p, zz in zip(dense, z)],
                          "length": round(sum(_d(p, q) for p, q in zip(dense, dense[1:])), 2)})
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
            st = _street_at(out_roads, p)
            if st is None:
                ends.append({"pos": p, "street": None}); rep["notes"].append("lane %s: no street at %s" % (ln["id"], [round(c, 1) for c in p])); continue
            rd, along, side, dist = st
            q = (p[0] + d[0] * sgn * WALK, p[1] + d[1] * sgn * WALK)          # from the street's lot line, not its carriageway edge
            ends.append({"pos": q, "street": rd["id"], "along_pos": p, "side": side, "dist": round(dist, 2)})
        p0, p1 = ends[0]["pos"], ends[1]["pos"]
        dense = _densify([p0, p1], 6.0)
        out_lanes.append({"id": "PH_" + ln["id"].replace("lane_", "L_"), "cf_lane": ln["id"], "cls": "lane", "width": ln.get("width", 6),
                          "pts": [(p[0], p[1], heights(*p) + ASPH) for p in dense], "ends": ends, "length": round(_d(p0, p1), 2)})
        rep["lanes"].append(ln["id"])
    rep["summary"] = {"cf_nodes": len([n for n in city["nodes"] if n["edges"]]), "cf_roads": len(roads_in), "mrs_roads": len(out_roads),
                      "junctions": len([j for j in out_j if j["kind"] == "junction"]), "dead_ends": len([j for j in out_j if j["kind"] == "dead_end"]),
                      "lanes": len(out_lanes), "clusters": len(rep["clusters"]), "absorbed": len(rep["absorbed"]), "duplicates": len(rep["duplicates"]),
                      "angle_drops": len(rep["angle_drops"]), "bend_junctions": len(rep["bend_junctions"]), "fillets": len(rep["bends"]),
                      "road_km": round(sum(r["length"] for r in out_roads) / 1000.0, 2), "lane_km": round(sum(l["length"] for l in out_lanes) / 1000.0, 2)}
    return {"junctions": out_j, "roads": out_roads, "lanes": out_lanes, "report": rep}


def junction_plane(heights, at, approaches, reach=22.0):
    """(z at the centre, (gx, gy)): least-squares plane through the graded road profiles (+ asphalt) of the approaches,
    0-`reach` m out from the junction, so the locked road ends blend into it; the grade is capped at MAX_PLANE_GRADE
    (a steeper junction is levelled that much)."""
    xs, ys, zs = [0.0], [0.0], [heights(*at) + ASPH]
    for pts in approaches:
        s = 0.0; nxt = 2.0
        for a, b in zip(pts, pts[1:]):
            L = _d(a, b)
            while nxt <= s + L and nxt <= reach:
                f = (nxt - s) / L; x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                xs.append(x - at[0]); ys.append(y - at[1]); zs.append(heights(x, y) + ASPH); nxt += 2.0
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


def _street_at(roads, p, tol=1.5):
    """The road whose carriageway edge passes through p (a lane mouth): (road, along, side, |d - half|)."""
    best = None
    for rd in roads:
        pr = _project_poly(rd["pts"], p)
        if pr is None: continue
        dd = abs(pr[0] - rd["width"] / 2.0)
        if dd < tol and (best is None or dd < best[3]): best = (rd, pr[1], pr[2], dd)
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
