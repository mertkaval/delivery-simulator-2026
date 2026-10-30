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
  signal_lanes    every multi-lane signalised approach has a mast arm with one head over each arriving lane, a
                  lane-use sign showing that lane's movements, arrow lenses on a left-only / right-only lane's head
  speed_sign      (validate_speed_signs) every speed-limit sign shows its road's Speed Limit
  trimmed_away    a road keeps some length between its junction trims
  junction_zones  a road keeps both ends' paint zones (Mark Clear Start + End) + junction.ZONE_MARGIN between its trims
  grade           (a road tagged mrs_max_grade: the city's streets) its built asphalt crest at the centre climbs at
                  most its class maximum over every 10 m of plan run (grading.window_grades, the measure the design
                  used); the message names the station, its distance from the nearer end and the design's prediction
  buried          (check_buried) no terrain or ground object of the scene covers a road's walkable surface (a flat
                  ground over a banked road hid its sidewalk); tunnels are exempt
  limit           every numeric input of a road lies inside its tested range (limits.json; the UI enforces it, a
                  script setting the modifier directly does not)
  warning         (check_warnings) no MRS modifier shows a combination warning ("MRS: ..." node warnings: a bend
                  tighter than the road's width allows, a value in a forbidden gap, sign content off its panel, a
                  marking line off its road)
  tongue_uncovered (check_tongues) every road tongue lies under an area junction's surface (at least 90 % of its road
                  footprint): a tongue out of every junction's range leaves a hole at the road's end
Network check
  overlap         no two road / junction surfaces cover the same ground (within 1 m in height): roads meet only
                  at their own junctions (check_overlaps, a 1 m grid of the evaluated top surfaces)
  building        (footprints given) no building footprint stands on a road / junction surface (check_buildings,
                  the same grid)
Placed objects (check_placed: every top-level object of the placed collection, from its evaluated mesh)
  placed_conflict no two placed objects overlap: standing objects by the convex plan hull of their base (within
                  PLACED_BASE of their lowest point), flat ones (paths, pads, mulch, grates, painted words) by their
                  real top faces; paths may join paths, an object may stand on its own pad / mulch / grate
  placed_road     no base other than a flush item's stands on a carriageway (asphalt, paint, cycle / bus lane, crossing)
  placed_ground   every base sits on the surface under it (within PLACED_Z): not floating, not sunk
  placed_building (footprints given) no base stands inside a building footprint
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


def _surface_end(r, dg, default):
    """The largest `along` of the road's asphalt vertices: where its surface really ends."""
    ev = r.evaluated_get(dg); me = ev.to_mesh()
    try:
        kind = me.attributes.get("kind"); along = me.attributes.get("along")
        if kind is None or along is None or kind.domain != "FACE" or along.domain != "POINT": return default
        kv = kind.data; av = along.data; best = None
        for p in me.polygons:
            if int(round(kv[p.index].value)) != 0: continue
            m = max(av[i].value for i in p.vertices)
            if best is None or m > best: best = m
        return best if best is not None else default
    finally:
        ev.to_mesh_clear()


def check_road(r, dg, inst, out):
    try:
        L = centre_line(r)[-1][0]
    except ValueError:                                   # nothing left of the road: its junctions' trims cover it
        _problem(out, r.name, "trimmed_away", "nothing is left of the road between its trims (Trim Start %.1f + Trim End %.1f m)"
                 % (road_input(r, "Trim Start") or 0.0, road_input(r, "Trim End") or 0.0))
        return
    zones = ((road_input(r, "Mark Clear Start") or 0.0) + (road_input(r, "Mark Clear End") or 0.0)) * (1.0 + J.ZONE_MARGIN)
    if zones > 0 and L < zones - TOL:
        _problem(out, r.name, "junction_zones", "%.1f m left between the junctions, their paint zones need %.1f m" % (L, zones))
    mcs = road_input(r, "Mark Clear Start") or 0.0; mce = road_input(r, "Mark Clear End") or 0.0
    bad_s = bad_e = 0
    # the road's surface ends at its last station; the centre-line sample may stop up to a station earlier
    L_end = _surface_end(r, dg, L)
    for c, vs, a in _faces(r, dg, kinds=PAINT_KINDS):
        if a is None: continue
        if a < mcs - TOL: bad_s += 1
        elif a > L_end - mce + TOL: bad_e += 1
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
            got = [int(dict(h["mrs_signal_head"]).get("arrow", 0)) for h in sorted(heads, key=lambda h: int(h.name.rsplit("_head", 1)[1]))]
            if got != [c if c in (1, 4) else 0 for c in want]:
                _problem(out, o.name, "signal_lanes", "%s: head arrows %s, the lanes may make %s" % (r.name, got, want))
            E = Vector(ap["end_point"]); R = Vector(ap["right"])
            centres = [in_r * (w["median"] * 0.5 + (k + 0.5) * w["lw"]) for k in range(n_in)]
            for h in heads:
                lat = (h.matrix_world.translation - E).to_2d().dot(R.to_2d())
                off = min(abs(lat - c) for c in centres)
                if off > HEAD_TOL: _problem(out, o.name, "signal_lanes", "%s: head %s is %.2f m off its lane centre" % (r.name, h.name, off))


GRADE_TOL = 0.002                    # the built grade may exceed the design's prediction by this (sampling; = citynet.GRADE_MARGIN)


def _crest(r, dg):
    """(plan run, z) along the evaluated road: per station the highest asphalt vertex within the inner lanes (the
    crest at the centre line, crown included, no paint), world coordinates; None without the road's attributes."""
    ev = r.evaluated_get(dg); me = ev.to_mesh(); M = r.matrix_world
    try:
        kind = me.attributes.get("kind"); lat = me.attributes.get("lat"); al = me.attributes.get("along")
        if kind is None or lat is None or al is None or kind.domain != "FACE" or lat.domain != "POINT": return None
        reach = (road_input(r, "Median") or 0.0) * 0.5 + (road_input(r, "Lane Width") or 3.0)
        on = set()
        for p in me.polygons:
            if int(round(kind.data[p.index].value)) == 0: on.update(p.vertices)
        st = {}
        for i in on:
            if abs(lat.data[i].value) > reach: continue
            k = round(al.data[i].value, 2); co = M @ me.vertices[i].co
            if k not in st or co.z > st[k][2]: st[k] = (co.x, co.y, co.z)
    finally:
        ev.to_mesh_clear()
    if len(st) < 2: return None
    pts = [st[k] for k in sorted(st)]
    plan = [0.0]
    for a, b in zip(pts, pts[1:]): plan.append(plan[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return plan, [p[2] for p in pts]


def check_grade(r, dg, out):
    """A street held to a class maximum grade (mrs_max_grade, set by the city build) climbs no steeper over any 10 m of
    plan run than that maximum (+ GRADE_TOL)."""
    G = r.get("mrs_max_grade")
    if G is None: return
    from .grading import window_grades
    c = _crest(r, dg)
    if c is None: return
    plan, z = c
    worst, at = window_grades(plan, z, 10.0)
    if worst > float(G) + GRADE_TOL:
        L = plan[-1]; end = min(at, L - at - 10.0)
        pred = r.get("mrs_grade_predicted")
        _problem(out, r.name, "grade", "%.1f %% over 10 m from %.1f m (%.1f m from the nearer end; end to end %.1f %%) exceeds its class maximum %.1f %%%s"
                 % (100 * worst, at, max(end, 0.0), 100 * abs(z[-1] - z[0]) / max(L, 1e-6), 100 * float(G),
                    "" if pred is None else "; the design predicted %.1f %%" % (100 * float(pred))))


def check_limits(r, out):
    """Numeric inputs of the road's MRS_Road modifier outside the tested limits (limits.json)."""
    from .limits import out_of_range
    from .nodes import mod_input_get
    mod = r.modifiers.get("MRS_Road")
    if mod is None or mod.node_group is None: return
    vals = {}
    for it in mod.node_group.interface.items_tree:
        if getattr(it, "item_type", "") == "SOCKET" and it.in_out == "INPUT" and it.socket_type in ("NodeSocketFloat", "NodeSocketInt"):
            vals[it.name] = mod_input_get(mod, it.name)
    for k, v, lo, hi, gap in out_of_range(mod.node_group.name, vals):
        if gap: _problem(out, r.name, "limit", "%s = %g lies between %g and %g, where the tests found mistakes (docs/roads/LIMITS.md)" % (k, v, gap[0], gap[1]))
        else: _problem(out, r.name, "limit", "%s = %g is outside its tested range [%g, %g] (docs/roads/LIMITS.md)" % (k, v, lo, hi))


BURIED_TOL = 0.02                    # a ground this far over a road surface hides it (m)
BURIED_MIN = 1.0                     # ... over at least this much of the road's surface (m2) before it is reported


def _is_ground(o):
    """A scene's terrain / ground object: tagged as a terrain source, graded to the roads, or a sample's ground plane
    (debug probes excluded)."""
    if o.type != "MESH" or o.get("mrs_debug"): return False
    if o.get("mrs_terrain_source") or o.name.startswith("MRS_GroundPlane"): return True
    return any(m.type == "NODES" and m.node_group and m.node_group.name == "MRS_TerrainConform" for m in o.modifiers)


def check_buried(roads_col, objects, dg, out):
    """Road surfaces (asphalt, cycle / bus lane, paving, kerb tops, planting strips) hidden under a ground object: a ray
    from above each top face's centre meets the ground more than BURIED_TOL above the face (tunnel spans skipped)."""
    from mathutils.bvhtree import BVHTree
    grounds = [o for o in objects if _is_ground(o)]
    if not grounds: return 0
    vs, fs = [], []
    for o in grounds:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        try: b = len(vs); vs += [M @ v.co for v in me.vertices]; fs += [tuple(b + i for i in p.vertices) for p in me.polygons]
        finally: ev.to_mesh_clear()
    if not fs: return 0
    gb = BVHTree.FromPolygons(vs, fs); n_bad = 0
    for r in all_roads(roads_col):
        ev = r.evaluated_get(dg); me = ev.to_mesh(); M = r.matrix_world; area = 0.0; at = None
        try:
            kind = me.attributes.get("kind"); tun = me.attributes.get("tunnel_surface")
            for p in me.polygons:
                if kind is not None and kind.domain == "FACE" and int(round(kind.data[p.index].value)) not in (0, 2, 4, 5, 6, 7, 9, 11): continue
                if tun is not None and tun.domain == "FACE" and tun.data[p.index].value > 0.5: continue
                nz = (M.to_3x3() @ p.normal).z
                if nz < 0.5: continue
                c = M @ p.center
                h = gb.ray_cast(Vector((c.x, c.y, c.z + 100.0)), Vector((0, 0, -1)), 100.0 - BURIED_TOL)
                if h[0] is not None:
                    area += p.area; at = at or c
        finally:
            ev.to_mesh_clear()
        if area >= BURIED_MIN:
            n_bad += 1
            _problem(out, r.name, "buried", "%.0f m2 of its surface lie under the ground (e.g. at %.1f, %.1f): the ground does not follow the road there"
                     % (area, at.x, at.y))
    return n_bad


def check_warnings(objects, out):
    """Every MRS modifier's own combination warnings (node warnings starting "MRS:", see the module docstring)."""
    n = 0
    for o in objects:
        for m in getattr(o, "modifiers", ()):
            if m.type != "NODES" or m.node_group is None or not m.node_group.name.startswith("MRS_"): continue
            for w in getattr(m, "node_warnings", ()):
                if w.message.startswith("MRS:"): _problem(out, o.name, "warning", w.message[4:].strip()); n += 1
    return n


TONGUE_COVER = 0.9          # share of a tongue's road footprint an area junction must cover


def check_tongues(roads_col, objects, dg, out):
    """Each road tongue (Tongue Start / End > 0) lies under an area junction (any object with MRS_AreaJunction among
    `objects`): its road footprint faces' centres are covered from above (TONGUE_COVER of them)."""
    from mathutils.bvhtree import BVHTree
    rs = [r for r in all_roads(roads_col) if (road_input(r, "Tongue Start") or 0.0) > 0.0 or (road_input(r, "Tongue End") or 0.0) > 0.0]
    if not rs: return 0
    vs, fs = [], []
    for o in objects:
        if o.type != "MESH" or not any(m.type == "NODES" and m.node_group and m.node_group.name == MRS_AREA for m in o.modifiers): continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        try: b = len(vs); vs += [M @ v.co for v in me.vertices]; fs += [tuple(b + i for i in p.vertices) for p in me.polygons]
        finally: ev.to_mesh_clear()
    bvh = BVHTree.FromPolygons(vs, fs) if fs else None
    for r in rs:
        ev = r.evaluated_get(dg); me = ev.to_mesh(); M = r.matrix_world
        try:
            t = me.attributes.get("mrs_tongue")
            cs = [M @ p.center for p in me.polygons if t is not None and t.domain == "FACE" and abs(t.data[p.index].value - 1.0) < 0.5]
        finally:
            ev.to_mesh_clear()
        if not cs: continue
        hit = sum(1 for c in cs if bvh is not None and bvh.ray_cast(Vector((c.x, c.y, c.z + 50.0)), Vector((0, 0, -1)), 100.0)[0] is not None)
        if hit < TONGUE_COVER * len(cs):
            _problem(out, r.name, "tongue_uncovered", "%d of %d road footprint faces of its tongue lie under no area junction (out of every junction's range?)"
                     % (len(cs) - hit, len(cs)))
    return len(rs)


MRS_AREA = "MRS_AreaJunction"


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


OVERLAP_CELL = 1.0             # m grid
OVERLAP_MIN = 4                 # cells (m^2) before a pair counts (seams, lane aprons stay below)


def _top_cells(o, dg, cell, cand=None):
    """{(i, j): z} of the plan grid cells whose centre lies under an upward face of the evaluated object (ray from
    above); `cand` limits the cells tried (default: the mesh's bounding box)."""
    from mathutils.bvhtree import BVHTree
    ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
    try:
        kind = me.attributes.get("kind"); kv = [d.value for d in kind.data] if kind is not None and kind.domain == "FACE" else None
        # a road's tongues are footprints under an area junction, not a surface of its own (they overlap by design)
        tg = me.attributes.get("mrs_tongue"); tv = [d.value for d in tg.data] if tg is not None and tg.domain == "FACE" else None
        me.calc_loop_triangles()
        verts = [M @ v.co for v in me.vertices]
        tris = [tuple(t.vertices) for t in me.loop_triangles
                if (M.to_3x3() @ t.normal).z > 0.5 and (kv is None or int(round(kv[t.polygon_index])) != 4) and (tv is None or tv[t.polygon_index] < 0.5)]
    finally:
        ev.to_mesh_clear()
    if not tris: return {}
    bvh = BVHTree.FromPolygons(verts, tris)
    if cand is None:
        xs = [verts[i].x for t in tris for i in t]; ys = [verts[i].y for t in tris for i in t]
        cand = [(i, j) for i in range(int(math.floor(min(xs) / cell)), int(math.ceil(max(xs) / cell)) + 1)
                for j in range(int(math.floor(min(ys) / cell)), int(math.ceil(max(ys) / cell)) + 1)]
    zs = [v.z for v in verts]; top = max(zs) + 50.0; out = {}
    for i, j in cand:
        h = bvh.ray_cast(Vector(((i + 0.5) * cell, (j + 0.5) * cell, top)), Vector((0, 0, -1)), top - min(zs) + 60.0)
        if h[0] is not None: out[(i, j)] = h[0].z
    return out


def _road_cells(r, cell):
    """Candidate cells round a road: its centre line (every 1 m) widened by its full half widths."""
    w = road_widths(r); half = max(w["half_l"] + w["swl"], w["half_r"] + w["swr"]) + w["curb"] + 1.5
    try: cl = centre_line(r)
    except ValueError: return set()                     # trimmed away (check_road reports it)
    out = set()
    for (a0, p0), (a1, p1) in zip(cl, cl[1:]):
        d = p1 - p0; L = d.length
        if L < 1e-6: continue
        u = d / L; n = Vector((-u.y, u.x, 0.0)); k = 0.0
        while k <= L:
            c = p0 + u * k; o_ = -half
            while o_ <= half:
                q = c + n * o_; out.add((int(math.floor(q.x / cell)), int(math.floor(q.y / cell)))); o_ += cell * 0.7
            k += cell * 0.7
    return out


def surface_grid(roads_col, dg, cell=OVERLAP_CELL):
    """{(i, j): [(object name, z)]}: the evaluated top surfaces of every road and junction on a `cell` m world grid."""
    rs = all_roads(roads_col)
    js = [o for o in roads_col.all_objects if o.get("mrs_junction") and o.type == "MESH"]
    grid = {}
    for o in rs + js:
        cells = _top_cells(o, dg, cell, sorted(_road_cells(o, cell)) if o in rs else None)
        for k, z in cells.items(): grid.setdefault(k, []).append((o.name, z))
    return grid


def check_overlaps(roads_col, dg, out, cell=OVERLAP_CELL, min_cells=OVERLAP_MIN, grid=None):
    """Surfaces of different roads / junctions over the same cell (within 1 m of height: a bridge over a road is not an
    overlap). A road and its own junctions may share a seam, and so may a road that opens onto another road's edge
    (its "mrs_mouths": one row of cells across its width per mouth); anything else reports the pair, its area and a
    place."""
    rs = all_roads(roads_col)
    js = [o for o in roads_col.all_objects if o.get("mrs_junction") and o.type == "MESH"]
    own = {}
    for j in js:
        m = j["mrs_junction"]; m = m.to_dict() if hasattr(m, "to_dict") else dict(m)
        for rn in m.get("roads", []): own.setdefault(rn, set()).add(j.name)
    seam = {}                                                          # (road, road) -> cells a mouth may share
    for r in rs:
        mouths = list(r.get("mrs_mouths", []))
        if not mouths: continue
        w = road_widths(r)
        across = w["half_l"] + w["half_r"] + 2.0 * w["curb"] + w["swl"] + w["swr"]
        for m_ in mouths:
            key = tuple(sorted((r.name, m_)))
            seam[key] = seam.get(key, 0) + int(math.ceil(across / cell)) + 1
    if grid is None: grid = surface_grid(roads_col, dg, cell)
    pairs = {}
    for k, lst in grid.items():
        if len(lst) < 2: continue
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                (na, za), (nb, zb) = lst[a], lst[b]
                if abs(za - zb) > 1.0: continue                        # one passes over the other
                if nb in own.get(na, ()) or na in own.get(nb, ()): continue
                key = tuple(sorted((na, nb)))
                pairs.setdefault(key, []).append(k)
    for (na, nb), cs in sorted(pairs.items()):
        if len(cs) < max(min_cells, seam.get((na, nb), 0) + 1): continue
        i, j = cs[len(cs) // 2]
        _problem(out, na, "overlap", "%s and %s cover the same %d m2 (e.g. at %.0f, %.0f)" % (na, nb, len(cs), (i + 0.5) * cell, (j + 0.5) * cell))
    return len(pairs)


BUILDING_INSET = 0.5        # m inside a footprint before a road surface there counts (a wall may stand on a sidewalk edge)


def check_buildings(grid, footprints, out, cell=OVERLAP_CELL, inset=BUILDING_INSET, dz=4.0):
    """`footprints` [(id, [(x, y), ...] convex world polygon, ground z or None)]: a grid cell centre more than `inset`
    m inside a footprint that carries a road / junction surface within `dz` m of the building's ground (any height
    when None: a bridge high over a building is fine only when the ground is known) reports the building."""
    n_bad = 0
    for bid, poly, z0 in footprints:
        if len(poly) < 3: continue
        area = sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))
        sgn = 1.0 if area > 0 else -1.0
        edges = []
        for k in range(len(poly)):
            (x0, y0), (x1, y1) = poly[k], poly[(k + 1) % len(poly)]
            L = math.hypot(x1 - x0, y1 - y0)
            if L > 1e-6: edges.append((x0, y0, (x1 - x0) / L, (y1 - y0) / L))
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        hits = []
        for i in range(int(math.floor(min(xs) / cell)), int(math.ceil(max(xs) / cell)) + 1):
            for j in range(int(math.floor(min(ys) / cell)), int(math.ceil(max(ys) / cell)) + 1):
                lst = grid.get((i, j))
                if not lst: continue
                cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
                # inside by more than `inset`: left of every edge (counter-clockwise) by that much
                if any(sgn * (ex * (cy - y0) - ey * (cx - x0)) < inset for x0, y0, ex, ey in edges): continue
                near = [nm for nm, z in lst if z0 is None or abs(z - z0) <= dz]
                if near: hits.append((i, j, near[0]))
        if hits:
            n_bad += 1
            i, j, nm = hits[len(hits) // 2]
            _problem(out, bid, "building", "%s stands on %s (%d m2, e.g. at %.0f, %.0f)" % (bid, nm, len(hits), (i + 0.5) * cell, (j + 0.5) * cell))
    return n_bad


PLACED_FLUSH = {"drain", "cover", "pit_grate", "pit_open", "tree_pit", "pad", "mulch", "path", "marking", "tree_edging"}   # lie in the surface they cover
PLACED_PARTS = ("pad", "plinth", "mulch", "guard", "edging", "grate")   # name suffixes of an object's own parts (X_pad, X_guard ...)
PLACED_SKIP = {"landscape"}          # grass / shrub scatter (points): no footprint of its own
PLACED_JOIN = {("path", "path"), ("pad", "path"), ("path", "pad")}     # flat items that may overlap: paths join paths and pads
PLACED_STAND_ON = {"pad", "path"}    # flat items made to be stood on (a bus pole on its boarding pad, a bench on its slab)
CARRIAGEWAY = (0, 1, 5, 8, 9)        # asphalt, marking, cycle lane, crossing, bus lane (road.py KIND)
PLACED_BASE = 0.25                   # a standing object's base: its vertices within this of its lowest point (m)
PLACED_OVERLAP = 0.03                # two standing bases may touch; overlapping deeper than this is a conflict (m)
PLACED_CELL = 0.2                    # plan grid of the footprints (m)
PLACED_Z = 0.05                      # no point of a base floats more than this over the surface under it (m)
PLACED_SINK = 0.125                  # free-standing furniture may sink this far into a slope: placement.FREE_RISE (0.10 m across its base) + its 0.02 m pad + 5 mm sampling
PLACED_SINK_EMBEDDED = 0.6           # poles, posts, trees: set into the ground, but not buried
PLACED_FREE = {"bench", "bench_backless", "bin", "bin_recycling", "bike_rack", "planter", "barrier"}   # free-standing (placement.FREE_STANDING)


def _tri_cells(a, b, c, cell=PLACED_CELL):
    """The plan cells whose centre lies in the triangle abc."""
    d = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
    if abs(d) < 1e-12: return set()
    out = set()
    for i in range(int(math.floor(min(a.x, b.x, c.x) / cell)), int(math.floor(max(a.x, b.x, c.x) / cell)) + 1):
        x = (i + 0.5) * cell
        for j in range(int(math.floor(min(a.y, b.y, c.y) / cell)), int(math.floor(max(a.y, b.y, c.y) / cell)) + 1):
            y = (j + 0.5) * cell
            l1 = ((b.y - c.y) * (x - c.x) + (c.x - b.x) * (y - c.y)) / d; l2 = ((c.y - a.y) * (x - c.x) + (a.x - c.x) * (y - c.y)) / d
            if l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1.0 + 1e-9: out.add((i, j))
    return out


def _in_tris(p, tris):
    for a, b, c in tris:
        d = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
        if abs(d) < 1e-12: continue
        l1 = ((b.y - c.y) * (p.x - c.x) + (c.x - b.x) * (p.y - c.y)) / d; l2 = ((c.y - a.y) * (p.x - c.x) + (a.x - c.x) * (p.y - c.y)) / d
        if l1 >= 0.0 and l2 >= 0.0 and l1 + l2 <= 1.0: return True
    return False


def _footprints(placed_col, dg):
    """Every placed top-level mesh object's footprint: {o, kind, flush, hull, tris, cells, z0, c}. A flat item (paths,
    pads, mulch, grates, painted words) covers its real top faces; a standing item the convex plan hull of its base
    (its vertices within PLACED_BASE of its lowest point: a trunk, a pole's foot, a bench's legs). Paths and pads are
    built in world coordinates, so an object's own heading says nothing about their shape (a bounding rectangle in it
    called a diagonal path a conflict with trees beside it)."""
    from mathutils.geometry import convex_hull_2d
    out = []
    for o in placed_col.all_objects:
        kind = str(o.get("mrs_kind", ""))
        if o.parent is not None or o.type != "MESH" or not kind or kind in PLACED_SKIP: continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world; R3 = M.to_3x3()
        try:
            vs = [M @ v.co for v in me.vertices]
            if not vs: continue
            z0 = min(v.z for v in vs); flush = kind in PLACED_FLUSH; hull = None
            tris3 = []
            if flush:
                me.calc_loop_triangles()
                tris3 = [tuple(vs[i].copy() for i in t.vertices) for t in me.loop_triangles if (R3 @ t.normal).z > 0.5]
                tris = [tuple(Vector((p.x, p.y)) for p in t) for t in tris3]
                pts = [p for t in tris for p in t]
            else:
                base = [Vector((v.x, v.y)) for v in vs if v.z <= z0 + PLACED_BASE]
                hull = [base[i] for i in convex_hull_2d([tuple(p) for p in base])]
                if len(hull) < 3:                                     # a single foot point: a 10 cm square round it
                    c_ = sum(base, Vector((0.0, 0.0))) / len(base); hull = [c_ + Vector((sx, sy)) * 0.05 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                tris = [(hull[0], hull[k], hull[k + 1]) for k in range(1, len(hull) - 1)]
                pts = hull
        finally:
            ev.to_mesh_clear()
        if not pts: continue
        cen = sum(pts, Vector((0.0, 0.0))) / len(pts)
        cells = set()
        for t in tris: cells |= _tri_cells(*t)
        cells.add((int(math.floor(cen.x / PLACED_CELL)), int(math.floor(cen.y / PLACED_CELL))))
        out.append({"o": o, "kind": kind, "flush": flush, "hull": hull, "tris": tris, "tris3": tris3, "cells": cells, "z0": z0, "c": Vector((cen.x, cen.y, z0))})
    return out


def _owner_of(name):
    """The object a placed part belongs to (X for X_pad, X_guard, X_edging ...; a name with no part suffix is its own)."""
    head, _sep, tail = name.rpartition("_")
    return head if head and tail in PLACED_PARTS else name


def _hull_depth(a, b):
    """How deep two convex plan polygons overlap: the smallest penetration over their edge normals (<= 0: apart)."""
    depth = 1e9
    for poly in (a, b):
        for k in range(len(poly)):
            e = poly[(k + 1) % len(poly)] - poly[k]
            if e.length < 1e-9: continue
            ax = Vector((-e.y, e.x)).normalized()
            pa = [p.dot(ax) for p in a]; pb = [p.dot(ax) for p in b]
            depth = min(depth, min(max(pa), max(pb)) - max(min(pa), min(pb)))
    return depth


def _surface_bvh(roads_col, dg, kinds=None):
    """One BVH of every road / junction face (the faces of `kinds` only when given), world space."""
    from mathutils.bvhtree import BVHTree
    vs, fs = [], []
    for o in all_roads(roads_col) + [o for o in roads_col.all_objects if o.get("mrs_junction") and o.type == "MESH"]:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        try:
            kind = me.attributes.get("kind"); kv = [d.value for d in kind.data] if kind is not None and kind.domain == "FACE" else None
            b = len(vs); vs += [M @ v.co for v in me.vertices]
            fs += [tuple(b + i for i in f.vertices) for f in me.polygons if kinds is None or (kv is not None and int(round(kv[f.index])) in kinds)]
        finally:
            ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, fs) if fs else None


def check_placed(placed_col, roads_col, dg, out, footprints=None, ground=None):
    """The placed objects against each other, the carriageway, the surface under them and the buildings (see the module
    docstring). `ground` (optional BVH) is the terrain beside the roads. Returns the number of objects checked."""
    items = _footprints(placed_col, dg)
    if not items: return 0
    cw = _surface_bvh(roads_col, dg, CARRIAGEWAY); surf = _surface_bvh(roads_col, dg)
    # what a standing object stands on: the road surfaces and the flat placed items over them (its pad, a plinth, a path)
    from mathutils.bvhtree import BVHTree
    fv, ff = [], []
    for it in items:
        for t in it["tris3"]:
            b = len(fv); fv += list(t); ff.append((b, b + 1, b + 2))
    flats = BVHTree.FromPolygons(fv, ff) if ff else None
    by_cell = {}
    for k, it in enumerate(items):
        for c in it["cells"]: by_cell.setdefault(c, []).append(k)
    seen = set()
    for lst in by_cell.values():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                ka, kb = sorted((lst[x], lst[y]))
                if (ka, kb) in seen: continue
                seen.add((ka, kb)); a, b = items[ka], items[kb]
                if abs(a["z0"] - b["z0"]) > 2.0: continue                               # one passes over the other
                na, nb = a["o"].name, b["o"].name
                if nb.startswith(na + "_") or na.startswith(nb + "_"): continue         # its own pad / mulch / grate
                if _owner_of(na) == _owner_of(nb): continue                             # two parts of one object (a tree's guard and edging)
                if a["flush"] and b["flush"]:
                    if (a["kind"], b["kind"]) in PLACED_JOIN: continue
                    if na.rsplit("_", 1)[0] == nb.rsplit("_", 1)[0]: continue          # one object's pad and plinth
                    shared = len(a["cells"] & b["cells"])
                    if shared < 2: continue
                    why = "overlap over %.2f m2" % (shared * PLACED_CELL ** 2)
                elif not a["flush"] and not b["flush"]:
                    dep = _hull_depth(a["hull"], b["hull"])
                    if dep <= PLACED_OVERLAP: continue
                    why = "overlap by %.2f m" % dep
                else:                                                                  # a standing item on a flat one
                    st, fl = (a, b) if not a["flush"] else (b, a)
                    if fl["kind"] in PLACED_STAND_ON: continue
                    probe = [st["c"].to_2d()] + [p + (st["c"].to_2d() - p) * 0.2 for p in st["hull"]]
                    if not any(_in_tris(p, fl["tris"]) for p in probe): continue
                    why = "%s stands on %s" % (st["o"].name, fl["o"].name)
                _problem(out, na, "placed_conflict", "%s (%s) and %s (%s): %s at %.1f, %.1f" % (na, a["kind"], nb, b["kind"], why, a["c"].x, a["c"].y))
    down = Vector((0.0, 0.0, -1.0))
    def under(bvh, p):
        if bvh is None: return None
        h = bvh.ray_cast(Vector((p.x, p.y, p.z + 2.0)), down, 4.0); return h[0].z if h[0] is not None else None
    for it in items:
        o, kind, c, z0 = it["o"], it["kind"], it["c"], it["z0"]
        if not it["flush"]:
            probe = [c] + [Vector((p.x, p.y, z0)) + (c - Vector((p.x, p.y, z0))) * 0.2 for p in it["hull"]]
            hit = next((p for p in probe if (lambda z: z is not None and abs(z - z0) <= PLACED_Z + 0.3)(under(cw, p))), None)
            if hit is not None:
                _problem(out, o.name, "placed_road", "%s (%s) stands on the carriageway at %.1f, %.1f" % (o.name, kind, hit.x, hit.y)); continue
        if kind != "path":                           # a path ramps from the sidewalk down to the ground beyond the roads
            pts = [c] + ([Vector((p.x, p.y, z0)) for p in it["hull"]] if it["hull"] else [])
            zs = []
            for p in pts:
                # a standing object meets the top of whatever is under it (road surface, its pad or plinth); a flat item the
                # road surface itself
                zz = [z for z in (under(surf, p), under(ground, p), under(flats, p) if not it["flush"] else None) if z is not None]
                if zz: zs.append(max(z for z in zz if z <= z0 + 0.5) if any(z <= z0 + 0.5 for z in zz) else min(zz))
            if zs:
                float_by = z0 - min(zs); sink_by = max(zs) - z0
                sink_max = PLACED_SINK if kind in PLACED_FREE else (None if it["flush"] else PLACED_SINK_EMBEDDED)
                if float_by > PLACED_Z:
                    _problem(out, o.name, "placed_ground", "%s (%s) floats over the surface by %.2f m at %.1f, %.1f" % (o.name, kind, float_by, c.x, c.y))
                elif sink_max is not None and sink_by > sink_max:
                    _problem(out, o.name, "placed_ground", "%s (%s) sinks into the surface by %.2f m at %.1f, %.1f" % (o.name, kind, sink_by, c.x, c.y))
        if footprints:
            for bid, poly, _z in footprints:
                if len(poly) >= 3 and _inside(poly, c.x, c.y):
                    _problem(out, o.name, "placed_building", "%s (%s) stands inside %s at %.1f, %.1f" % (o.name, kind, bid, c.x, c.y)); break
    return len(items)


def _inside(poly, x, y):
    inside = False
    for k in range(len(poly)):
        (x0, y0), (x1, y1) = poly[k], poly[(k + 1) % len(poly)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0): inside = not inside
    return inside


def validate(roads_col, placed=None, log=print, overlaps=True, footprints=None):
    from .nodes import depsgraph
    _CACHE.clear()
    dg = depsgraph(); inst = _instances(dg)
    rs = all_roads(roads_col); by_name = {r.name: r for r in rs}
    out = []
    for r in rs: check_road(r, dg, inst, out); check_limits(r, out); check_grade(r, dg, out)
    js = [o for o in roads_col.all_objects if o.get("mrs_junction") and o.type == "MESH"]
    for o in js: check_junction(o, dg, out, by_name)
    grid = surface_grid(roads_col, dg) if overlaps or footprints else None
    if overlaps: check_overlaps(roads_col, dg, out, grid=grid)
    if footprints: check_buildings(grid, footprints, out)
    n_signs = validate_speed_signs(placed.all_objects if placed else bpy.data.objects, out)
    n_placed = check_placed(placed, roads_col, dg, out, footprints) if placed else 0
    scene_objs = list(bpy.context.scene.objects)
    check_warnings(set(roads_col.all_objects) | set(o for o in scene_objs if o.type in ("MESH", "CURVE")), out)
    check_tongues(roads_col, scene_objs, dg, out)
    check_buried(roads_col, scene_objs, dg, out)
    counts = {}
    for p in out: counts[p["check"]] = counts.get(p["check"], 0) + 1
    rep = {"roads": len(rs), "junctions": len(js), "speed_signs": n_signs, "placed": n_placed, "problems": out, "counts": counts}
    log("VALIDATE roads %d junctions %d speed signs %d placed %d problems %d %s" % (len(rs), len(js), n_signs, n_placed, len(out), json.dumps(counts)))
    return rep
