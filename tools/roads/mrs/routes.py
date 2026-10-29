"""Pedestrian and bicycle route networks derived from the shared street model + placement, with
connectivity and usable-width validation (not just visual continuity).

Pedestrian graph
  * sidewalk edges along each road side (walking-corridor centre), split at every attachment station;
    usable width = the widest contiguous free paving across the sidewalk at 1 m stations (planting strip
    excluded, every non-flush placed footprint subtracted), checked against RULES["walk_min"];
  * junction corner edges (approach a's left-looking-out sidewalk to b's right one, as built by
    junction.build_junction), roundabout ring sectors, dead-end bulb rings and through paths;
  * crossing edges between the kerb-ramp landings (refuge node in the middle when present);
  * footbridge edges from the plan: sidewalk -> foot path -> stairs / ramp -> head landing -> deck;
  * bus-stop boarding nodes, building entrances (MRS_Entrance_*), park paths (objects with `mrs_ped_path`).
Bicycle graph
  * cycleway edges per road side (lane centre, direction), bike crossings through junctions to the
    straight-ahead approach (painted band when the junction has bike crossings, mixed traffic otherwise),
    turn connectors, roundabout shared-path rings, dead-end through paths; open road ends are network
    boundaries. Every cycleway end must continue somewhere (no abrupt dead ends).
`build(roads_col, placement_report)` -> {"ped": {...}, "bike": {...}, "validation": [...], "stats": {...}}
"""
import bpy, math, json
from mathutils import Vector
from .roads import all_roads, road_widths, road_input, road_ends
from .structures import road_sample, centre_line, surface_z
from . import placement as PL


class Graph:
    def __init__(self, kind):
        self.kind = kind; self.nodes = {}; self.edges = []

    def node(self, nid, pos, kind="sidewalk", **kw):
        if nid not in self.nodes: self.nodes[nid] = dict(id=nid, pos=[round(c, 3) for c in pos], kind=kind, **kw)
        return nid

    def edge(self, a, b, kind, pts=None, width=None, step_free=True, **kw):
        if a == b: return None
        pts = pts or [self.nodes[a]["pos"], self.nodes[b]["pos"]]
        L = sum((Vector(p) - Vector(q)).length for p, q in zip(pts, pts[1:]))
        e = dict(id="%s__%s" % (a, b), a=a, b=b, kind=kind, length=round(L, 2), width=None if width is None else round(width, 2), step_free=step_free,
                 points=[[round(c, 3) for c in p] for p in pts], **kw)
        self.edges.append(e); return e

    def components(self, edge_filter=None):
        adj = {n: [] for n in self.nodes}
        for e in self.edges:
            if edge_filter and not edge_filter(e): continue
            adj[e["a"]].append(e["b"]); adj[e["b"]].append(e["a"])
        seen = {}; comps = []
        for n in self.nodes:
            if n in seen: continue
            stack = [n]; comp = []; seen[n] = len(comps)
            while stack:
                x = stack.pop(); comp.append(x)
                for y in adj[x]:
                    if y not in seen: seen[y] = len(comps); stack.append(y)
            comps.append(comp)
        return comps

    def as_dict(self):
        return {"nodes": list(self.nodes.values()), "edges": self.edges}


def _side_of_lookout(end, looking):
    """Road side ('l'/'r') of an approach's left / right sidewalk when looking out of the junction."""
    if end == "start": return "l" if looking == "left" else "r"
    return "r" if looking == "left" else "l"


def _foot_rects(rep):
    out = []
    for it in rep.get("items", []):
        if it.get("flush") or not it.get("foot"): continue
        P = [Vector(c) for c in it["foot"]]
        c = sum(P, Vector((0, 0))) / 4
        out.append((PL.Rect(c, P[1] - P[0], (P[1] - P[0]).length / 2, (P[3] - P[0]).length / 2), it["name"]))
    return out


def _clear_width(m, s, a, z, rects, paved=()):
    """Widest contiguous free walkable interval across the sidewalk at station a (m); the planting strip is
    not walkable except where it is paved (bus-stop boarding pads: `paved` station intervals)."""
    lo = z["strip"] if z["strip"] > 0.05 and not any(p0 <= a <= p1 for p0, p1 in paved) else 0.0; hi = z["sw"]
    p, t, r = m.frame(a); sgn = 1.0 if s == "r" else -1.0; n = r * sgn
    base = m.half(a, s) + m.curb
    blocked = []
    q0 = p + n * (base + lo); q1 = p + n * (base + hi)
    seg = PL.Rect((q0 + q1) / 2, n, (hi - lo) / 2, 0.05)
    for rc, nm in rects:
        if not rc.overlaps(seg): continue
        ds = [(Vector((c.x, c.y, 0)) - Vector((p.x, p.y, 0))).dot(n) - base for c in rc.corners()]
        blocked.append((max(lo, min(ds)), min(hi, max(ds)), nm))
    blocked.sort()
    best = 0.0; cur = lo; who = None
    for b0, b1, nm in blocked:
        if b0 > cur: best = max(best, b0 - cur)
        cur = max(cur, b1); who = nm
    best = max(best, hi - cur)
    return best, [b[2] for b in blocked]


def build(roads_col, rep=None):
    from . import structures as _st
    roads = all_roads(roads_col)
    for r in roads: centre_line(r)
    _st.freeze([r.name for r in roads])
    try:
        return _build(roads_col, rep or {})
    finally:
        _st.freeze(None)


def _build(roads_col, rep):
    R = PL.RULES
    ped = Graph("pedestrian"); bike = Graph("bicycle"); val = []
    bike_attach = []                                   # (road, side, along, node, pts): links into a cycleway edge
    models = {r.name: PL.RoadModel(r) for r in all_roads(roads_col) if centre_line(r)[-1][0] - centre_line(r)[0][0] > 4.0}
    ends = {n: PL._junction_ends(m.road) for n, m in models.items()}
    rects = _foot_rects(rep)
    attach = {}                                        # (road, side) -> [(along, node id)]
    def side_node(road, s, a, tag):
        m = models[road]; z = m.zones(s)
        if z is None: return None
        q, t, n = m.point(a, s, (z["walk0"] + z["walk1"]) / 2)
        nid = ped.node("%s_%s_%s" % (road, s, tag), q, "sidewalk", road=road, side=s, along=round(a, 2))
        attach.setdefault((road, s), []).append((a, nid)); return nid
    # --- attachment stations first: road ends, crossings, bus stops, footbridge paths, entrances, park paths
    for rn, m in models.items():
        for s in ("l", "r"):
            if m.zones(s) is None: continue
            side_node(rn, s, m.A0, "a0"); side_node(rn, s, m.A1, "a1")
    jmeta = [(o, dict(o["mrs_junction"])) for o in roads_col.all_objects if o.get("mrs_junction")]
    for o, meta in jmeta:
        typ = meta.get("type", "junction")
        if typ in ("junction", "roundabout"):
            for x in meta.get("crossings", []):
                rn = x["road"]; m = models.get(rn)
                if m is None: continue
                end = x["end"]; a_end, dirn = PL._end_span(m, end)
                a_x = a_end + dirn * (meta.get("stop_setback", 0.6) + 1.25) if typ == "junction" else a_end + dirn * (x.get("y", 2.25))
                pf = Vector(x["from"]); pt = Vector(x["to"])
                # which road side is "from": from is left of d looking out
                s_from = _side_of_lookout(end, "left"); s_to = _side_of_lookout(end, "right")
                nf = side_node(rn, s_from, a_x, "x%s" % x["id"]); nt = side_node(rn, s_to, a_x, "x%s" % x["id"])
                kf = ped.node(x["id"] + "_from", pf, "kerb_ramp"); kt = ped.node(x["id"] + "_to", pt, "kerb_ramp")
                if nf: ped.edge(nf, kf, "ramp", width=2.5, tactile=True)
                if nt: ped.edge(kt, nt, "ramp", width=2.5, tactile=True)
                if x.get("refuge"):
                    mid = (pf + pt) / 2; kr = ped.node(x["id"] + "_refuge", mid, "refuge")
                    ped.edge(kf, kr, "crossing", width=2.5, style=x.get("style")); ped.edge(kr, kt, "crossing", width=2.5, style=x.get("style"))
                else:
                    ped.edge(kf, kt, "crossing", width=2.5, style=x.get("style"))
    for bs in rep.get("bus_stops", []):
        m = models.get(bs["road"])
        if m is None: continue
        sn = side_node(bs["road"], bs["side"], bs["along"], "bus_" + bs["id"])
        bn = ped.node("bus_" + bs["id"], bs["point"], "bus_stop", items=bs.get("items", []))
        if sn: ped.edge(sn, bn, "boarding", width=R["bus_boarding_depth"])
    for fbo in [o for o in roads_col.all_objects if o.get("mrs_footbridge_plan") and o.type == "MESH"]:
        plan = json.loads(fbo["mrs_footbridge_plan"]); m = models.get(plan["road"])
        heads = {}
        for e in plan.get("ped_edges", []):
            end = e["end"]; s = end
            sp = Vector(e["sidewalk_point"])
            a = PL._project(m, sp) if m else 0.0
            sn = side_node(plan["road"], s, a, "fb_%s" % e["id"]) if m else None
            path = e["approach_path"]; foot = path[0]
            fn = ped.node("%s_%s_foot" % (fbo.name, e["id"]), foot, "footbridge_foot")
            if sn: ped.edge(sn, fn, "path", pts=list(reversed(path)), width=min(plan["width"], 2.5))
            hn = heads.get(end) or ped.node("%s_head_%s" % (fbo.name, end), e["points"][-1], "footbridge_landing"); heads[end] = hn
            ped.edge(fn, hn, "footbridge_" + e["kind"], pts=e["points"], width=e["width"], step_free=e["step_free"], max_slope=e.get("max_slope"), rise=e.get("rise"))
            if e["kind"] == "ramp":
                bike.node(fn, foot, "footbridge_foot"); bike.node(hn, e["points"][-1], "footbridge_landing")
                bike.edge(fn, hn, "footbridge_ramp", pts=e["points"], width=e["width"], note="step-free 1:%d ramp, shared with pedestrians" % round(1.0 / max(e.get("max_slope") or 0.083, 0.01)))
                bike_attach.append((plan["road"], end, a, fn, list(reversed(path))))
        if "l" in heads and "r" in heads:
            ped.edge(heads["l"], heads["r"], "footbridge_deck", width=plan["width"], clearance=plan.get("clearance"))
            if heads["l"] in bike.nodes and heads["r"] in bike.nodes: bike.edge(heads["l"], heads["r"], "footbridge_deck", width=plan["width"])
    for o in list(roads_col.all_objects):
        if o.type == "EMPTY" and o.name.startswith("MRS_Entrance") and o.get("mrs_road") in models:
            m = models[o["mrs_road"]]; s = o.get("mrs_side", "r"); a = PL._project(m, o.location)
            sn = side_node(m.name, s, a, "ent_" + o.name)
            en = ped.node(o.name, o.location, "entrance")
            if sn: ped.edge(sn, en, "entrance_path", width=2.4)
        if o.get("mrs_ped_path"):
            pts = json.loads(o["mrs_ped_path"]); ids = []
            for k, (pnt, end_tag) in enumerate(((pts[0], "a"), (pts[-1], "b"))):
                dest = o.get("mrs_path_dest") if end_tag == "b" else None
                ids.append(ped.node("%s_%s" % (o.name, end_tag), pnt, "destination" if dest else "path_end", destination=dest))
            ped.edge(ids[0], ids[1], "park_path", pts=pts, width=o.get("mrs_path_width", 2.5))
    # --- sidewalk edges between consecutive attachment stations (with usable width)
    narrow = []
    paved = {}
    for bs in rep.get("bus_stops", []):
        paved.setdefault((bs["road"], bs["side"]), []).append(tuple(bs["boarding"]))
    for (rn, s), lst in attach.items():
        m = models[rn]; z = m.zones(s)
        lst = sorted(set(lst))
        for (a0, n0), (a1, n1) in zip(lst, lst[1:]):
            if a1 - a0 < 0.05: ped.edge(n0, n1, "sidewalk", width=z["sw"]); continue
            wmin = 99.0; who = []
            k = int((a1 - a0) / 1.0) + 1
            for i in range(k + 1):
                aa = a0 + (a1 - a0) * i / k
                wc, names = _clear_width(m, s, aa, z, rects, paved.get((rn, s), ()))
                if wc < wmin: wmin = wc; who = names
            pts = [list(m.point(a0 + (a1 - a0) * i / max(1, int((a1 - a0) / 3.0)), s, (z["walk0"] + z["walk1"]) / 2)[0]) for i in range(max(1, int((a1 - a0) / 3.0)) + 1)]
            e = ped.edge(n0, n1, "sidewalk", pts=pts, width=wmin, road=rn, side=s)
            if wmin < R["walk_min"] - 0.01:
                narrow.append(e); val.append({"level": "warning", "graph": "ped", "edge": e["id"], "message": "usable width %.2f m < %.2f m (%s)" % (wmin, R["walk_min"], ", ".join(sorted(set(who)))[:120])})
    # --- connect sidewalks around corners / rings / bulbs
    for o, meta in jmeta:
        typ = meta.get("type", "junction")
        if typ == "junction":
            aps = meta.get("approaches", [])
            n = len(aps)
            for i in range(n):
                a, b = aps[i], aps[(i + 1) % n]
                if n == 2 and i == 1: break
                sa = _side_of_lookout(a["end"], "left"); sb = _side_of_lookout(b["end"], "right")
                na = "%s_%s_%s" % (a["road"], sa, "a0" if a["end"] == "start" else "a1"); nb = "%s_%s_%s" % (b["road"], sb, "a0" if b["end"] == "start" else "a1")
                if na in ped.nodes and nb in ped.nodes:
                    ped.edge(na, nb, "corner", width=min(models[a["road"]].sw[sa], models[b["road"]].sw[sb]) if a["road"] in models and b["road"] in models else None, junction=o.name)
        elif typ == "roundabout":
            at = Vector(meta["at"])
            arms = []
            for rn in meta.get("roads", []):
                if rn not in models: continue
                e = min(road_ends(models[rn].road), key=lambda x: (x[0] - at).length)
                d = (e[0] - at); ang = math.atan2(d.y, d.x); arms.append((ang, rn, "start" if e[2] else "end"))
            arms.sort()
            for i in range(len(arms)):
                (a0, ra, ea), (a1, rb, eb) = arms[i], arms[(i + 1) % len(arms)]
                sa = _side_of_lookout(ea, "left"); sb = _side_of_lookout(eb, "right")
                na = "%s_%s_%s" % (ra, sa, "a0" if ea == "start" else "a1"); nb = "%s_%s_%s" % (rb, sb, "a0" if eb == "start" else "a1")
                if na in ped.nodes and nb in ped.nodes:
                    ped.edge(na, nb, "ring_sector", width=meta.get("sidewalk", 2.0), junction=o.name, shared=bool(meta.get("shared_path")))
        elif typ == "dead_end":
            rn = meta["roads"][0]
            if rn in models:
                tag = "a0" if meta.get("end") == "start" else "a1"
                nl, nr = "%s_l_%s" % (rn, tag), "%s_r_%s" % (rn, tag)
                if nl in ped.nodes and nr in ped.nodes: ped.edge(nl, nr, "bulb_ring", junction=o.name)
                if meta.get("path"):
                    pts = meta["path"]; pn = ped.node(o.name + "_path_end", pts[-1], "path_end")
                    src = nl if nl in ped.nodes else nr
                    if src in ped.nodes: ped.edge(src, pn, "through_path", pts=pts, width=meta.get("path_width", 3.0))
    # park paths: merge coincident path ends (hubs), then join the rest to the nearest route node within 8 m
    ends_ = [n for n, d_ in ped.nodes.items() if d_["kind"] == "path_end"]
    merged = set()
    for i, a_ in enumerate(ends_):
        for b_ in ends_[i + 1:]:
            if (Vector(ped.nodes[a_]["pos"]) - Vector(ped.nodes[b_]["pos"])).length < 1.0:
                ped.edge(a_, b_, "path_join"); merged.add(a_); merged.add(b_)
    for nid, nd in list(ped.nodes.items()):
        if nd["kind"] != "path_end" or nid in merged: continue
        P = Vector(nd["pos"]); best = None
        for mid, md in ped.nodes.items():
            if md["kind"] in ("path_end",) or mid == nid: continue
            dd = (Vector(md["pos"]) - P).length
            if best is None or dd < best[0]: best = (dd, mid)
        if best and best[0] < 8.0: ped.edge(nid, best[1], "path_join")
        else: val.append({"level": "warning", "graph": "ped", "node": nid, "message": "path end is not connected to the network (nearest node %.1f m)" % (best[0] if best else -1)})
    # --- bicycle network
    bike_ends = {}
    for rn, m in models.items():
        w = m.w0
        for s in ("l", "r"):
            if not w.get("bike_on_" + s): continue
            lat = (w["bike0_" + s] + w["bike1_" + s]) / 2; sgn = 1.0 if s == "r" else -1.0
            kind = road_input(m.road, "Bike Right" if s == "r" else "Bike Left")
            pts = []
            a = m.A0; step = 3.0
            while True:
                p, t, r = m.frame(a); q = p + r * sgn * lat; q.z = surface_z(m.road, a, sgn * lat); pts.append(list(q))
                if a >= m.A1: break
                a = min(m.A1, a + step)
            fwd = (s == "r") == m.rht
            n0 = bike.node("%s_%sbike_a0" % (rn, s), pts[0], "cycleway_end", road=rn, side=s, end="start")
            n1 = bike.node("%s_%sbike_a1" % (rn, s), pts[-1], "cycleway_end", road=rn, side=s, end="end")
            bike.edge(n0, n1, "cycleway", pts=pts, width=w["bike1_" + s] - w["bike0_" + s], direction="both" if kind == "Two-Way" else ("forward" if fwd else "backward"), facility=kind)
            bike_ends.setdefault((rn, "start"), []).append((s, n0)); bike_ends.setdefault((rn, "end"), []).append((s, n1))
    # attachments (footbridge ramps): split the cycleway of that road side at the station and link to it
    for rn, s, a, other, pts in bike_attach:
        e = next((x for x in bike.edges if x["kind"] == "cycleway" and x["a"] == "%s_%sbike_a0" % (rn, s)), None)
        if e is None:
            val.append({"level": "info", "graph": "bike", "node": other, "message": "no cycleway on %s %s: the footbridge ramp joins the sidewalk only" % (rn, s)}); continue
        m = models[rn]
        P = [Vector(q) for q in e["points"]]; target = Vector(pts[0])
        k = min(range(len(P)), key=lambda i: (P[i] - target).length)
        k = max(1, min(len(P) - 2, k))
        mid = bike.node("%s_%sbike_at%d" % (rn, s, int(a)), e["points"][k], "cycleway_split", road=rn, side=s)
        bike.edges.remove(e)
        e1 = dict(e, id=e["a"] + "__" + mid, b=mid, points=e["points"][:k + 1]); e2 = dict(e, id=mid + "__" + e["b"], a=mid, points=e["points"][k:])
        bike.edges.extend([e1, e2])
        bike.edge(mid, other, "dismount_link", pts=[e["points"][k]] + list(pts), note="across the sidewalk to the footbridge ramp (walk the bike)")
    for o, meta in jmeta:
        typ = meta.get("type", "junction")
        if typ == "junction":
            aps = meta.get("approaches", []); n = len(aps)
            band = bool(meta.get("bike_crossings", True))
            for i, a in enumerate(aps):
                ea = bike_ends.get((a["road"], a["end"]), [])
                if not ea: continue
                da = Vector(a["heading"])
                opp = min(range(n), key=lambda j: da.dot(Vector(aps[j]["heading"])) if j != i else 9.0)
                for k in (opp, (i + 1) % n, (i - 1) % n):
                    if k == i: continue
                    b = aps[k]; eb = bike_ends.get((b["road"], b["end"]), [])
                    kind = ("bike_crossing" if band else "mixed_traffic") if k == opp else "bike_turn"
                    if eb:
                        for sa, na in ea:
                            # same physical side through the junction: left-looking-out of a continues to right-looking-out of b
                            want = _side_of_lookout(b["end"], "right" if _side_of_lookout(a["end"], "left") == sa else "left")
                            nb = next((nn for ss, nn in eb if ss == want), eb[0][1])
                            bike.edge(na, nb, kind, junction=o.name)
                    else:
                        cn = bike.node("%s_%s_%s_carriageway" % (o.name, b["road"], b["end"]), meta["at"], "mixed_traffic", road=b["road"])
                        for sa, na in ea: bike.edge(na, cn, "mixed_traffic", junction=o.name, note="continues on the carriageway of %s" % b["road"])
        elif typ == "roundabout":
            ring = bike.node(o.name + "_ring", meta["at"], "roundabout_ring")
            for rn in meta.get("roads", []):
                for end in ("start", "end"):
                    for s, nn in bike_ends.get((rn, end), []):
                        if (Vector(bike.nodes[nn]["pos"]) - Vector(meta["at"])).length < 60.0:
                            bike.edge(nn, ring, "shared_path" if meta.get("shared_path") else "mixed_traffic", junction=o.name)
        elif typ == "dead_end":
            rn = meta["roads"][0]
            for s, nn in bike_ends.get((rn, meta.get("end", "end")), []):
                if meta.get("path"):
                    pe = bike.node(o.name + "_path_end", meta["path"][-1], "path_end"); bike.edge(nn, pe, "through_path", pts=meta["path"], width=meta.get("path_width", 3.0))
    # footbridge ramps are step-free: bikes may be pushed / ridden there (linked to the nearest cycleway end)
    # --- validation
    comps = ped.components()
    big = max(comps, key=len) if comps else []
    stray = [c for c in comps if c is not big]
    if stray:
        for c in stray: val.append({"level": "error", "graph": "ped", "message": "disconnected pedestrian component: %s" % ", ".join(sorted(c)[:6])})
    sf = ped.components(lambda e: e.get("step_free", True))
    sf_main = max(sf, key=len) if sf else []
    no_sf = [n for n in ped.nodes if n not in sf_main and ped.nodes[n]["kind"] in ("sidewalk", "bus_stop", "entrance", "footbridge_landing")]
    if no_sf: val.append({"level": "warning", "graph": "ped", "message": "%d nodes only reachable with steps: %s" % (len(no_sf), ", ".join(no_sf[:5]))})
    bdeg = {n: 0 for n in bike.nodes}
    for e in bike.edges: bdeg[e["a"]] += 1; bdeg[e["b"]] += 1
    boundary = []
    for nid, nd in bike.nodes.items():
        if nd["kind"] == "cycleway_end" and bdeg[nid] < 2:
            rn = nd["road"]; end = nd["end"]
            if end not in ends.get(rn, {}): boundary.append(nid)
            else: val.append({"level": "error", "graph": "bike", "node": nid, "message": "cycleway ends abruptly at %s" % ends[rn][end].get("junction")})
    stats = {"ped_nodes": len(ped.nodes), "ped_edges": len(ped.edges), "ped_components": len(comps), "ped_step_free_components": len(sf),
             "ped_length_m": round(sum(e["length"] for e in ped.edges), 1), "ped_narrow_edges": len(narrow),
             "bike_nodes": len(bike.nodes), "bike_edges": len(bike.edges), "bike_components": len(bike.components()), "bike_boundary_ends": len(boundary),
             "bike_length_m": round(sum(e["length"] for e in bike.edges if e["kind"] == "cycleway"), 1),
             "min_sidewalk_width": round(min([e["width"] for e in ped.edges if e["kind"] == "sidewalk" and e["width"] is not None] or [0.0]), 2)}
    return {"ped": ped.as_dict(), "bike": bike.as_dict(), "validation": val, "stats": stats, "boundary": boundary}


def debug_object(routes, collection, name="MRS_RouteMap", z_lift=0.25):
    """Thin ribbons for every route edge (green walk, orange steps, blue bike, red narrow) for overhead QA renders."""
    import bmesh
    from .props import mat
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    cols = {"walk": mat("MRS_RouteWalk", (0.1, 0.9, 0.2), 0.5), "steps": mat("MRS_RouteSteps", (1.0, 0.55, 0.0), 0.5), "bike": mat("MRS_RouteBike", (0.1, 0.4, 1.0), 0.5),
            "bad": mat("MRS_RouteBad", (1.0, 0.0, 0.0), 0.5)}
    for m_ in cols.values():
        b = next(n for n in m_.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); b.inputs["Emission Color"].default_value = m_.diffuse_color; b.inputs["Emission Strength"].default_value = 2.0
    bm = bmesh.new(); mats = list(cols.values())
    def ribbon(pts, w, mi):
        P = [Vector(p) + Vector((0, 0, z_lift)) for p in pts]
        for a, b in zip(P, P[1:]):
            d = b - a; d.z = 0
            if d.length < 1e-4: continue
            s = Vector((-d.y, d.x, 0)).normalized() * w
            try:
                f = bm.faces.new([bm.verts.new(q) for q in (a - s, b - s, b + s, a + s)]); f.material_index = mi
            except ValueError: pass
    for e in routes["ped"]["edges"]:
        mi = 3 if (e["width"] is not None and e["width"] < PL.RULES["walk_min"] - 0.01) else (1 if not e.get("step_free", True) else 0)
        ribbon(e["points"], 0.18, mi)
    for e in routes["bike"]["edges"]: ribbon(e["points"], 0.12, 2)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m_ in mats: me.materials.append(m_)
    o = bpy.data.objects.new(name, me); collection.objects.link(o); o["mrs_debug"] = 1
    return o
