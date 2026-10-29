"""Actual movement paths (not graph links) for vehicles, cyclists and pedestrians, checked against the
evaluated road / junction surfaces.

* Lanes: per road, per side, per lane index k (counted from the median): a polyline at the lane centre for
  the stations where the lane exists (lane transitions add / drop the outermost lane over the taper: the
  extra lane's path starts / ends in the middle of the taper with a merge / diverge curve from lane k-1).
  Travel direction follows the road group: under right-hand traffic the forward lanes are on the right.
* Junction movements: incoming approach lane -> outgoing approach lane, using the lane-use rules that the
  painted arrows show (single lane: every movement; inner lane: straight + towards the centre side; outer
  lane: straight + away from it; middle lanes: straight); no U-turns; no movement into an approach without
  outgoing lanes (one-way). Each path = stop line -> junction edge (straight) -> cubic Bezier into the target
  lane (tangent continuous), with the controlling signal id / phase when the junction is signalised.
* Bicycle movements: cycleway end -> straight continuation / right turn into a cycleway or the carriageway.
* Pedestrian corners: quadratic curves through the corner paving instead of straight chords.
Checks (swept clearance): every 0.5 m along a path, the body's footprint corners (car 1.9 m wide, bicycle
0.7 m, pedestrian 0.6 m) are ray-cast onto the surfaces; each corner must land on an allowed surface kind
(car: asphalt / paint / crossing / bus / junction cycle band; bicycle: + cycleway; pedestrian: paving,
tactile, concrete kerb / island tops, crossings) without a vertical step > 6 cm (car) / 4 cm (bike) between
samples, and the curve radius must allow the movement (car >= 5 m, bike >= 2.5 m).
`build(roads_col, routes)` -> {"lanes": [...], "movements": [...], "bike_movements": [...], "validation": [...], "stats": {...}}
and refines `routes["ped"]` corner edges in place."""
import bpy, math, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .roads import all_roads, road_input, road_ends
from .structures import centre_line, surface_z
from . import placement as PL

DRIVE = {0, 1, 8, 9}            # asphalt, marking, crossing, bus lane (road kinds)
CYCLE = DRIVE | {5}             # + cycleway
WALK = {2, 6, 7, 8, 1, 11}      # concrete (kerb tops, islands), paving, tactile, crossing, paint (zebra stripes), driveway apron
ACCESS = DRIVE | {11}           # driveway apron (dropped kerb across the sidewalk) + service yard slab
JUNCTION_KIND = {0: 0, 1: 1, 2: 2, 3: 6, 4: 5, 5: 7, 6: 8}   # junction material slot -> kind (KIND_OF_SLOT)
BODY = {"car": (1.9, 4.5, DRIVE, 0.06, 4.5), "bike": (0.7, 1.8, CYCLE, 0.045, 2.5), "ped": (0.6, 0.5, WALK, 0.2, 0.0),
        "ped_road": (0.6, 0.5, WALK | DRIVE | {5}, 0.2, 0.0),      # crossings: asphalt between the stripes, cycle bands
        "car_access": (1.9, 4.5, ACCESS | {5}, 0.06, 4.5)}         # into a service yard: across the cycle lane and the dropped kerb only


class Surface:
    """Ray-cast access to the evaluated road + junction surfaces with their `kind` per face."""
    def __init__(self, roads_col):
        verts = []; polys = []; kinds = []
        from .nodes import depsgraph
        dg = depsgraph()
        for o in roads_col.all_objects:
            if o.get("mrs_placed") or o.get("mrs_debug"): continue
            is_road = o.type == "CURVE" and "MRS_Road" in o.modifiers
            is_j = o.type == "MESH" and o.get("mrs_junction")
            is_fb = o.type == "MESH" and o.get("mrs_footbridge")
            is_drive = o.type == "MESH" and o.get("mrs_kind") == "drive"
            if not (is_road or is_j or is_fb or is_drive): continue
            ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
            kd = me.attributes["kind"].data if "kind" in me.attributes else None
            base = len(verts)
            verts.extend(M @ v.co for v in me.vertices)
            for p in me.polygons:
                polys.append([base + i for i in p.vertices])
                k = round(kd[p.index].value) if (kd is not None and len(kd) == len(me.polygons)) else 2
                kinds.append(10 if is_fb else (11 if is_drive else k))
            ev.to_mesh_clear()
        self.kinds = kinds
        self.bvh = BVHTree.FromPolygons(verts, polys)

    def probe(self, p, up=3.0, down=6.0):
        hit = self.bvh.ray_cast(Vector((p.x, p.y, p.z + up)), Vector((0, 0, -1)), up + down)
        if hit[0] is None: return None, None
        return hit[0].z, self.kinds[hit[2]]


def _bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append(p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3)
    return out


def _min_radius(pts):
    r = 1e9
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        ab = (b - a).to_2d(); bc = (c - b).to_2d(); ac = (c - a).to_2d()
        cr = abs(ab.x * bc.y - ab.y * bc.x)
        if cr < 1e-9: continue
        r = min(r, ab.length * bc.length * ac.length / (2 * cr))
    return r


def _sweep_check(surf, pts, body):
    """Footprint-corner ray casts every 0.5 m along pts; returns (ok, problems, max_step)."""
    width, length, allowed, max_step, _ = BODY[body]
    probs = []; last = None; max_dz = 0.0
    P = [Vector(p) for p in pts]
    acc = 0.0
    for a, b in zip(P, P[1:]):
        seg = (b - a); L = seg.to_2d().length
        if L < 1e-6: continue
        d = Vector((seg.x, seg.y, 0)).normalized(); n = Vector((-d.y, d.x, 0))
        k = max(1, int(L / 0.5))
        for i in range(k):
            c = a.lerp(b, i / k)
            for s in (-1, 1):
                q = c + n * s * width / 2
                z, kind = surf.probe(q)
                if z is None:
                    probs.append("no surface at %.1f, %.1f" % (q.x, q.y)); continue
                if kind not in allowed and kind != 10:
                    probs.append("kind %d under the %s at %.1f, %.1f" % (kind, body, q.x, q.y))
            zc, kc = surf.probe(c)
            if zc is not None and last is not None:
                max_dz = max(max_dz, abs(zc - last))
            last = zc
    ok = not probs and max_dz <= max_step
    if max_dz > max_step: probs.append("vertical step %.3f m" % max_dz)
    return ok, probs[:6], max_dz


def _access_moves(surf, lanes, models, val):
    """Every MRS_Driveway_* anchor with a yard (frontage.py): 'access_in' from the outermost lane on the
    driveway's side (a turn of >= 4.5 m radius through the dropped kerb into the yard) and 'access_out' from
    the yard back to that lane downstream. Checked with the car footprint on road / apron / yard kinds only."""
    import bpy
    out = []
    for o in bpy.data.objects:
        if o.type != "EMPTY" or not o.name.startswith("MRS_Driveway") or not o.get("mrs_yard"): continue
        rd = o.get("mrs_road"); s = o.get("mrs_side", "r"); m = models.get(rd)
        cand = [l for l in lanes if l["road"] == rd and l["side"] == s]
        if m is None or not cand: continue
        lane = max(cand, key=lambda l: l["index"])
        P = [Vector(p) for p in lane["points"]]
        mouth = Vector(o.location); yard = Vector(o["mrs_yard"])
        i0 = min(range(len(P)), key=lambda i: (P[i] - mouth).to_2d().length)
        kerb = P[i0]
        n_out = (mouth - kerb); n_out.z = 0; n_out.normalize()
        def lane_at(dist):
            """lane point `dist` m from the driveway along travel (negative = upstream) and its tangent"""
            i = i0; acc = 0.0; step = 1 if dist >= 0 else -1
            while 0 < i + step < len(P) - 1 and acc + (P[i + step] - P[i]).length < abs(dist):
                acc += (P[i + step] - P[i]).length; i += step
            t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]); t.z = 0
            return P[i], t.normalized()
        lat = (mouth - kerb).to_2d().length              # lane centre -> back of the sidewalk
        R = BODY["car"][4] + 0.5                          # tight (5 m): the swept body stays inside the dropped kerb
        k = R * 0.552                                     # cubic Bezier ~ quarter circle of radius R
        _, t0 = lane_at(0.0)
        C = kerb                                          # lane centre on the driveway axis
        S = C - t0 * R; Q = C + n_out * R; E_ = C + t0 * R
        inside = mouth + n_out * 2.5; inside.z = yard.z; Q.z = (C.z + mouth.z) * 0.5
        a0, _ = lane_at(-(R + 6.0)); a1, _ = lane_at(R + 6.0)
        pts_in = [a0] + _bezier(S, S + t0 * k, Q - n_out * k, Q, 16) + [inside, yard]
        pts_out = [yard, inside] + _bezier(Q, Q - n_out * k, E_ - t0 * k, E_, 16) + [a1]
        for kind, pts in (("access_in", pts_in), ("access_out", pts_out)):
            rmin = _min_radius(pts)
            ok, probs, dz = _sweep_check(surf, pts, "car_access")
            if rmin < BODY["car"][4]: ok = False; probs.append("radius %.1f m < %.1f m" % (rmin, BODY["car"][4]))
            mv = {"id": "%s_%s" % (o.name, kind), "junction": None, "from_lane": lane["id"] if kind == "access_in" else None,
                  "to_lane": lane["id"] if kind == "access_out" else None, "turn": kind, "from_road": rd, "to_road": rd, "signal": None, "phase": None,
                  "control": "yield", "driveway": o.name, "stop_point": [round(c, 3) for c in (inside if kind == "access_out" else pts[0])],
                  "length": round(sum((b - a).length for a, b in zip(pts, pts[1:])), 2), "min_radius": round(min(rmin, 999.0), 2),
                  "clearance_ok": ok, "max_step": round(dz, 3), "problems": probs, "points": [[round(c, 3) for c in q] for q in pts]}
            out.append(mv)
            if not ok: val.append({"level": "warning", "graph": "vehicle", "movement": mv["id"], "message": "; ".join(probs[:3])})
    return out


def _lane_counts(m, a):
    """Interpolated lane counts per side at station a (as the road group does)."""
    lf0, lb0 = m.w0["lanes_f"], m.w0["lanes_b"]
    lf1, lb1 = (m.w1["lanes_f"], m.w1["lanes_b"]) if m.trans else (lf0, lb0)
    f = PL._smooth((a - m.t0) / m.tl) if m.trans else 0.0
    lf = lf0 + (lf1 - lf0) * f; lb = lb0 + (lb1 - lb0) * f
    return {"r": lf, "l": lb} if m.rht else {"r": lb, "l": lf}


def lanes_of(m, step=2.0):
    """Lane centre polylines of one road (world points in travel order)."""
    out = []
    lw = m.w0["lw"]; mh = m.w0["median"] * 0.5
    nmax = {s: max(m.w0["lanes_" + s], m.w1["lanes_" + s]) for s in ("l", "r")}
    for s in ("l", "r"):
        sgn = 1.0 if s == "r" else -1.0
        fwd = (s == "r") == m.rht
        for k in range(int(round(nmax[s]))):
            pts = []
            a = m.A0
            while True:
                cnt = _lane_counts(m, a)[s]
                exists = cnt > k + 0.5 - 1e-6
                if exists:
                    p, t, r = m.frame(a)
                    off = mh + (k + 0.5) * lw
                    # a lane being added / dropped slides in from the neighbouring lane over the taper
                    if cnt < k + 1.0: off = mh + (k + cnt) * 0.5 * lw         # centred in the widening (or narrowing) part
                    q = p + r * sgn * off; q.z = surface_z(m.road, a, sgn * off)
                    pts.append((a, q))
                if a >= m.A1: break
                a = min(m.A1, a + step)
            if len(pts) < 2: continue
            seq = pts if fwd else list(reversed(pts))
            out.append({"id": "%s_%s%d" % (m.name, s, k), "road": m.name, "side": s, "index": k, "dir": "forward" if fwd else "backward",
                        "a0": round(pts[0][0], 2), "a1": round(pts[-1][0], 2), "points": [[round(c, 3) for c in q] for a_, q in seq]})
    return out


def build(roads_col, routes=None):
    from . import structures as _st
    roads = all_roads(roads_col)
    for r in roads: centre_line(r)
    _st.freeze([r.name for r in roads])
    try:
        return _build(roads_col, routes)
    finally:
        _st.freeze(None)


def _build(roads_col, routes):
    surf = Surface(roads_col)
    if routes and "nodes_by_id" not in routes["ped"]: routes["ped"]["nodes_by_id"] = {n["id"]: n for n in routes["ped"]["nodes"]}
    models = {r.name: PL.RoadModel(r) for r in all_roads(roads_col)}
    lanes = []
    for m in models.values(): lanes.extend(lanes_of(m))
    by_id = {l["id"]: l for l in lanes}
    val = []; moves = []; bmoves = []
    jmeta = [(o, dict(o["mrs_junction"])) for o in roads_col.all_objects if o.get("mrs_junction")]
    for o, meta in jmeta:
        if meta.get("type", "junction") != "junction": continue
        aps = meta.get("approaches", []); at = Vector(meta["at"])
        sig_by_ap = {s["approach"]: s for s in meta.get("signals", [])}
        # arriving / leaving lanes per approach (looking out of the junction: d = away from it)
        info = []
        for ai, ap in enumerate(aps):
            m = models.get(ap["road"])
            if m is None: info.append(None); continue
            start = ap["end"] == "start"
            d = Vector((ap["heading"][0], ap["heading"][1], 0)).normalized()
            arriving_side = ("l" if m.rht else "r") if start else ("r" if m.rht else "l")
            leaving_side = "r" if arriving_side == "l" else "l"
            setback = meta.get("stop_setback", 0.6) + 2.5 + 0.6
            a_edge = m.A0 if start else m.A1
            a_stop = a_edge + (setback if start else -setback)
            arr = sorted([l for l in lanes if l["road"] == m.name and l["side"] == arriving_side and (l["a0"] <= a_edge + 1 if start else l["a1"] >= a_edge - 1)], key=lambda l: l["index"])
            lev = sorted([l for l in lanes if l["road"] == m.name and l["side"] == leaving_side and (l["a0"] <= a_edge + 1 if start else l["a1"] >= a_edge - 1)], key=lambda l: l["index"])
            info.append(dict(ap=ap, m=m, d=d, start=start, arr=arr, lev=lev, a_edge=a_edge, a_stop=a_stop, idx=ai))
        for A in info:
            if A is None or not A["arr"]: continue
            n_in = len(A["arr"])
            for B in info:
                if B is None or B is A or not B["lev"]: continue
                travel_in = -A["d"]; travel_out = B["d"]
                ang = math.degrees(math.atan2(travel_in.x * travel_out.y - travel_in.y * travel_out.x, travel_in.dot(travel_out)))
                if abs(ang) > 160: continue                                      # U-turn
                turn = "straight" if abs(ang) < 35 else ("left" if ang > 0 else "right")
                if not A["m"].rht: turn = {"left": "right", "right": "left"}.get(turn, turn)
                centre_turn = "left" if A["m"].rht else "right"                  # the turn towards the road centre
                for lane in A["arr"]:
                    k = lane["index"]
                    if n_in > 1:
                        if turn == centre_turn and k != 0: continue
                        if turn != centre_turn and turn != "straight" and k != n_in - 1: continue
                    n_out = len(B["lev"])
                    tk = 0 if turn == centre_turn else (n_out - 1 if turn != "straight" else min(k, n_out - 1))
                    tgt = B["lev"][tk]
                    # stop point -> edge point on the incoming lane, edge point -> target lane start
                    P_in = [Vector(p) for p in lane["points"]]
                    P_out = [Vector(p) for p in tgt["points"]]
                    p_edge = P_in[-1]; p_entry = P_out[0]
                    m = A["m"]; sgn = 1.0 if lane["side"] == "r" else -1.0
                    off = m.w0["median"] * 0.5 + (k + 0.5) * m.w0["lw"]
                    ps, ts, rs = m.frame(A["a_stop"]); p_stop = ps + rs * sgn * off; p_stop.z = surface_z(m.road, A["a_stop"], sgn * off)
                    T0 = (P_in[-1] - P_in[-2]).normalized(); T3 = (P_out[1] - P_out[0]).normalized()
                    L = (p_entry - p_edge).length
                    h = L * (0.33 if turn == "straight" else 0.55)
                    curve = _bezier(p_edge, p_edge + T0 * h, p_entry - T3 * h, p_entry, max(6, int(L / 1.0)))
                    pts = [p_stop] + curve
                    rmin = _min_radius(curve)
                    ok, probs, dz = _sweep_check(surf, pts, "car")
                    if rmin < BODY["car"][4]: ok = False; probs.append("radius %.1f m < %.1f m" % (rmin, BODY["car"][4]))
                    sig = sig_by_ap.get(A["idx"])
                    mv = {"id": "%s_%s_%s" % (o.name, lane["id"], tgt["id"]), "junction": o.name, "from_lane": lane["id"], "to_lane": tgt["id"], "turn": turn,
                          "from_road": A["ap"]["road"], "to_road": B["ap"]["road"], "signal": sig["id"] if sig else None, "phase": sig["phase"] if sig else None,
                          "control": meta.get("control", "none"), "stop_point": [round(c, 3) for c in p_stop], "length": round(sum((b - a).length for a, b in zip(pts, pts[1:])), 2),
                          "min_radius": round(min(rmin, 999.0), 2), "clearance_ok": ok, "max_step": round(dz, 3), "problems": probs,
                          "points": [[round(c, 3) for c in q] for q in pts]}
                    moves.append(mv)
                    if not ok: val.append({"level": "warning", "graph": "vehicle", "movement": mv["id"], "message": "; ".join(probs[:3])})
        # bicycles: straight on to the opposite cycleway (or carriageway), right turn into the next approach
        for A in info:
            if A is None: continue
            m = A["m"]; side = ("l" if m.rht else "r") if A["start"] else ("r" if m.rht else "l")
            if not m.w0.get("bike_on_" + side): continue
            wa = m.w_at(A["a_edge"]); sgn = 1.0 if side == "r" else -1.0; lat = (wa["bike0_" + side] + wa["bike1_" + side]) / 2
            pa, ta, ra = m.frame(A["a_edge"]); p0 = pa + ra * sgn * lat; p0.z = surface_z(m.road, A["a_edge"], sgn * lat)
            T0 = -A["d"]
            for B in info:
                if B is None or B is A: continue
                travel_out = B["d"]; ang = math.degrees(math.atan2(T0.x * travel_out.y - T0.y * travel_out.x, T0.dot(travel_out)))
                turn = "straight" if abs(ang) < 35 else ("left" if ang > 0 else "right")
                if not m.rht: turn = {"left": "right", "right": "left"}.get(turn, turn)
                if turn == ("left" if m.rht else "right") or abs(ang) > 160: continue   # left turns: two-stage via the crossings (not generated)
                mb = B["m"]; bside = ("r" if mb.rht else "l") if B["start"] else ("l" if mb.rht else "r")
                wb = mb.w_at(B["a_edge"])
                if mb.w0.get("bike_on_" + bside):
                    blat = (wb["bike0_" + bside] + wb["bike1_" + bside]) / 2; kind = "cycleway"
                else:
                    blat = wb["half_" + bside] - 0.9; kind = "carriageway"
                bs = 1.0 if bside == "r" else -1.0
                pb, tb_, rb = mb.frame(B["a_edge"]); p3 = pb + rb * bs * blat; p3.z = surface_z(mb.road, B["a_edge"], bs * blat)
                L = (p3 - p0).length; h = L * (0.33 if turn == "straight" else 0.55)
                curve = _bezier(p0, p0 + T0 * h, p3 - travel_out * h, p3, max(6, int(L / 1.0)))
                ok, probs, dz = _sweep_check(surf, curve, "bike")
                rmin = _min_radius(curve)
                if rmin < BODY["bike"][4]: ok = False; probs.append("radius %.1f m" % rmin)
                bm_ = {"id": "%s_%s_bike_%s_%s" % (o.name, m.name, B["ap"]["road"], turn), "junction": o.name, "from_road": m.name, "to_road": B["ap"]["road"],
                       "turn": turn, "into": kind, "clearance_ok": ok, "problems": probs, "max_step": round(dz, 3), "min_radius": round(min(rmin, 999.0), 2),
                       "signal": (sig_by_ap.get(A["idx"]) or {}).get("id"), "points": [[round(c, 3) for c in q] for q in curve]}
                bmoves.append(bm_)
                if not ok: val.append({"level": "warning", "graph": "bicycle", "movement": bm_["id"], "message": "; ".join(probs[:3])})
    # bicycle graph links through junctions -> the ridden movement path where one exists (else a two-stage link)
    if routes:
        nodes = {n["id"]: n for n in routes["bike"]["nodes"]}
        for e in routes["bike"]["edges"]:
            if e["kind"] not in ("bike_crossing", "bike_turn"): continue
            ra = nodes.get(e["a"], {}).get("road"); rb = nodes.get(e["b"], {}).get("road")
            mv_ = next((b_ for b_ in bmoves if b_["junction"] == e.get("junction") and b_["from_road"] == ra and b_["to_road"] == rb), None)
            if mv_ is not None:
                e["points"] = mv_["points"]; e["geometry"] = "path"; e["length"] = round(sum((Vector(p) - Vector(q)).length for p, q in zip(mv_["points"], mv_["points"][1:])), 2)
            else:
                e["geometry"] = "link"; e["note"] = "two-stage turn via the crossings (no ridden path generated)"
    # pedestrian corners: curve through the corner paving, then check every walking edge
    ped_checked = 0; ped_bad = 0
    if routes:
        for e in routes["ped"]["edges"]:
            if e["kind"] == "corner" and len(e["points"]) == 2:
                A = Vector(e["points"][0]); B = Vector(e["points"][1])
                jo = bpy.data.objects.get(e.get("junction", ""))
                at = Vector(jo["mrs_junction"]["at"]) if jo else (A + B) / 2
                # control point: the corner of the two walking lines, found as the point at the same distance from
                # the junction centre direction as the two ends (keeps the curve on the corner paving)
                na = routes["ped"]["nodes_by_id"].get(e["a"]) if "nodes_by_id" in routes["ped"] else None
                nb = routes["ped"]["nodes_by_id"].get(e["b"]) if "nodes_by_id" in routes["ped"] else None
                def into(nd):
                    m = models.get(nd.get("road")) if nd else None
                    if m is None: return None
                    a = nd["along"]; p_, t_, r_ = m.frame(a)
                    return (-t_ if abs(a - m.A0) < abs(a - m.A1) else t_).to_2d().normalized()
                dA = into(na); dB = into(nb); ctrl = (A + B) / 2
                if dA is not None and dB is not None:
                    den = dA.x * dB.y - dA.y * dB.x
                    if abs(den) > 0.15:                       # walking lines meet: bend round their corner
                        w = (B - A).to_2d(); sA = (w.x * dB.y - w.y * dB.x) / den
                        c2 = A.to_2d() + dA * sA
                        if 0.0 < sA < 3.0 * (B - A).length: ctrl = Vector((c2.x, c2.y, 0.0))
                ctrl.z = (A.z + B.z) / 2
                pts = [A * (1 - t) ** 2 + ctrl * 2 * (1 - t) * t + B * t * t for t in (i / 10 for i in range(11))]
                e["points"] = [[round(c, 3) for c in q] for q in pts]
                e["length"] = round(sum((b - a).length for a, b in zip(pts, pts[1:])), 2)
            if e["kind"] in ("corner", "sidewalk", "crossing", "ramp", "ring_sector", "bulb_ring"):
                ok, probs, dz = _sweep_check(surf, e["points"], "ped_road" if e["kind"] in ("crossing", "ramp") else "ped")
                e["walk_ok"] = ok; ped_checked += 1
                if not ok:
                    ped_bad += 1; e["walk_problems"] = probs
                    val.append({"level": "warning", "graph": "ped", "edge": e["id"], "message": "; ".join(probs[:3])})
    # service accesses: from the kerb-side lane into the yard (forward) and back out to the lane downstream
    access = _access_moves(surf, lanes, models, val)
    moves.extend(access)
    stats = {"lanes": len(lanes), "movements": len(moves), "movements_ok": sum(1 for m_ in moves if m_["clearance_ok"]),
             "bike_movements": len(bmoves), "bike_movements_ok": sum(1 for m_ in bmoves if m_["clearance_ok"]),
             "ped_edges_checked": ped_checked, "ped_edges_ok": ped_checked - ped_bad,
             "turns": {t: sum(1 for m_ in moves if m_["turn"] == t) for t in ("left", "straight", "right")},
             "signalised_movements": sum(1 for m_ in moves if m_["signal"]), "access_movements": len(access),
             "access_ok": sum(1 for m_ in access if m_["clearance_ok"])}
    if routes: routes["ped"].pop("nodes_by_id", None)
    return {"lanes": lanes, "movements": moves, "bike_movements": bmoves, "validation": val, "stats": stats}
