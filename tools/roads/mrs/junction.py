"""Junctions v2 (explicit meshes, Python): any number of approaches, rounded curb corners, crosswalks,
stop lines, sidewalk corner pieces, traffic lights; roundabouts and dead ends (turning circles).
Roads are trimmed and height-locked to the junction level through their modifier inputs; junctions
remember their inputs and rebuild (`rebuild`, `rebuild_all`, optional depsgraph auto-update).
"""
import bpy, bmesh, math
from mathutils import Vector
from .nodes import MRS, mod_input_set
from .roads import road_widths, road_ends, all_roads, road_input

UP = Vector((0, 0, 1))
Z_PAINT = 0.004


def _line_x(p, d, q, e):
    den = d.x * e.y - d.y * e.x
    if abs(den) < 1e-9: return None
    t = ((q.x - p.x) * e.y - (q.y - p.y) * e.x) / den
    return p + d * t


def _fillet(p_a, d_a, p_b, d_b, radius, n=8):
    """Rounded corner between line A (point p_a, direction d_a pointing AWAY from the corner along
    the road) and line B (p_b, d_b likewise). Returns the polyline from A's tangent point to B's,
    or None when the lines are parallel."""
    C = _line_x(p_a, d_a, p_b, d_b)
    if C is None: return None
    ua = d_a.normalized(); ub = d_b.normalized()
    cosang = max(-1.0, min(1.0, ua.dot(ub)))
    theta = math.acos(cosang)                   # interior angle between the two edges at C
    if theta < 1e-3 or abs(math.pi - theta) < 1e-3: return None
    radius = min(radius, 12.0 * math.tan(theta / 2.0))     # sharp angles: keep the tangent distance within ~12 m
    t = radius / math.tan(theta / 2.0)          # tangent distance from C
    Ta = C + ua * t; Tb = C + ub * t
    bis = (ua + ub).normalized()
    centre = C + bis * (radius / math.sin(theta / 2.0))
    a0 = math.atan2(Ta.y - centre.y, Ta.x - centre.x); a1 = math.atan2(Tb.y - centre.y, Tb.x - centre.x)
    da = a1 - a0
    while da > math.pi: da -= 2 * math.pi
    while da < -math.pi: da += 2 * math.pi
    pts = [Vector((centre.x + radius * math.cos(a0 + da * k / n), centre.y + radius * math.sin(a0 + da * k / n), 0.0)) for k in range(n + 1)]
    return pts, C, t, centre, a0, da, radius


_bvh_cache = {}


def _terrain_bvh(terrain):
    """BVH of the terrain's own mesh data (the source terrain is hidden, so it has no evaluated copy)."""
    from mathutils.bvhtree import BVHTree
    me = terrain.data
    key = (terrain.name, len(me.vertices), len(me.polygons))
    if _bvh_cache.get("key") != key:
        M = terrain.matrix_world
        _bvh_cache["key"] = key
        _bvh_cache["bvh"] = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    return _bvh_cache["bvh"]


def _ground_z(at, terrain):
    if terrain is None: return at.z
    loc, _, _, _ = _terrain_bvh(terrain).ray_cast(Vector((at.x, at.y, at.z + 500)), Vector((0, 0, -1)), 2000.0)
    return loc.z + 0.08 if loc is not None else at.z


def _approaches(at, roads, snap):
    out = []
    for r in roads:
        for p, t, is_start in road_ends(r):
            if (p - at).length <= snap:
                w = road_widths(r, at_end=not is_start)        # lane counts at THIS end (transitions)
                if not is_start:
                    # approach dicts use "looking out of the junction" sides: at a road END that is the road's
                    # right side on the left, so every l / r pair is swapped
                    for k in ("half", "carr", "bike0", "bike1", "bike_on", "bike_prot", "lanes"):
                        w[k + "_l"], w[k + "_r"] = w[k + "_r"], w[k + "_l"]
                    w["swl"], w["swr"] = w["swr"], w["swl"]
                # traffic arriving at the junction: the backward lanes at a road start, the forward lanes at its end
                w["lanes_in"] = w["lanes_b"] if is_start else w["lanes_f"]; w["lanes_out"] = w["lanes_f"] if is_start else w["lanes_b"]
                out.append(dict(road=r, p=p, d=Vector((t.x, t.y, 0)).normalized(), start=is_start, **w))
    out.sort(key=lambda a: math.atan2(a["d"].y, a["d"].x))
    return out


def _set_end(a, trim, clear, lock_z, ramp=False):
    mod = a["road"].modifiers["MRS_Road"]
    s = a["start"]
    values = {("Trim Start" if s else "Trim End"): trim, ("Clear Start" if s else "Clear End"): clear, ("Lock Start" if s else "Lock End"): True,
              ("Lock Start Z" if s else "Lock End Z"): lock_z, ("Ramp Start" if s else "Ramp End"): bool(ramp)}
    for k, v in values.items(): mod_input_set(mod, k, v)
    inputs = dict(a["road"].get("mrs_inputs", {})); inputs.update(values); a["road"]["mrs_inputs"] = inputs
    a["road"].update_tag()


KIND_OF_SLOT = {0: 0.0, 1: 1.0, 2: 2.0, 3: 6.0, 4: 5.0, 5: 7.0, 6: 8.0}     # material slot -> kind attribute


def _mats():
    """Material names for the junction slots (asphalt, paint, concrete, paving, cycleway, tactile, crossing),
    falling back when a dedicated material is missing."""
    def pick(*names):
        return next((MRS + n for n in names if bpy.data.materials.get(MRS + n)), MRS + "Concrete")
    return (pick("Asphalt"), pick("Paint"), pick("Concrete"), pick("Paving", "Concrete"), pick("Cycleway", "BikeLane"), pick("Tactile", "Paint"), pick("Cycleway", "BikeLane"))


MATS = _mats


def _mesh_object(name, bm, collection, materials, meta):
    bm.normal_update()
    for f in bm.faces:
        if abs(f.normal.z) > 0.5 and f.normal.z < 0: f.normal_flip()
    big = [f for f in bm.faces if len(f.verts) > 4]
    if big: bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in materials: me.materials.append(bpy.data.materials[m])
    uvl = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        v = me.vertices[loop.vertex_index].co; uvl.data[loop.index].uv = (v.x, v.y)
    kind = me.attributes.new("kind", "FLOAT", "FACE")
    for p in me.polygons: kind.data[p.index].value = KIND_OF_SLOT.get(p.material_index, 2.0)
    old = bpy.data.objects.get(name)
    if old:
        def _remove_tree(ob):
            for ch in list(ob.children): _remove_tree(ch)
            bpy.data.objects.remove(ob)
        _remove_tree(old)                       # signal poles AND their head children
    o = bpy.data.objects.new(name, me); collection.objects.link(o)
    o["mrs_junction"] = meta
    return o


CONTROLS = ("none", "signals", "stop", "yield", "priority")


def build_junction(name, at, roads, collection, crosswalks=True, stop_lines=True, corner_radius=6.0, traffic_lights=False,
                   snap=0.8, terrain=None, lights_collection=None, crossing="zebra", stop_setback=0.6, refuge=True, control=None,
                   main_roads=None, bike_crossings=True, crossing_width=2.5):
    """Connect the road ends within `snap` of `at`. Any number (>= 2) of approaches; neighbours must be at
    least 25 degrees apart. Builds the asphalt surface with filleted corners, curb / paving corner pieces,
    crossings (zebra or parallel lines) with ramps on the roads, stop lines set back from the crossing,
    median noses and refuge islands, coloured bicycle crossings, and signal poles with IDs
    (control = "signals"); "stop" / "yield" / "priority" are consumed by the sign placer.
    Returns the junction object; raises ValueError for unsupported layouts."""
    at = Vector(at)
    approaches = _approaches(at, roads, snap)
    n = len(approaches)
    if n < 2: raise ValueError("%s: %d road ends at the junction point; at least 2 are needed" % (name, n))
    for i in range(n):
        a, b = approaches[i], approaches[(i + 1) % n]
        ang = math.degrees(math.atan2(b["d"].y, b["d"].x) - math.atan2(a["d"].y, a["d"].x)) % 360.0
        if n > 2 and ang < 25.0: raise ValueError("%s: roads %s and %s meet at %.0f degrees (min 25)" % (name, a["road"].name, b["road"].name, ang))
    zs = [a["p"].z for a in approaches]
    if max(zs) - min(zs) > 1.5: raise ValueError("%s: road ends differ in height by %.1f m (max 1.5 for a flat junction)" % (name, max(zs) - min(zs)))
    z = _ground_z(at, terrain) if terrain is not None else sum(zs) / len(zs)
    if control is None: control = "signals" if traffic_lights else ("priority" if n >= 3 else "none")
    traffic_lights = control == "signals"
    main_roads = set(main_roads or [])
    corners = []
    for i in range(n):
        a, b = approaches[i], approaches[(i + 1) % n]
        la = a["d"].cross(UP).normalized(); lb = b["d"].cross(UP).normalized()
        swa, swb = a["swl"], b["swr"]
        rings = []
        # ring 0: fillet of the asphalt edges; rings 1 / 2 (curb, sidewalk back): concentric arcs around the same
        # centre with radius R - offset (the back of a sidewalk corner is a TIGHTER arc; <= 0 collapses to a point),
        # so every ring starts at the same station as the asphalt tangent point and meets the road's straight edges
        pa = at - la * a["half_l"]; pb = at + lb * b["half_r"]
        span = math.degrees(math.atan2(b["d"].y, b["d"].x) - math.atan2(a["d"].y, a["d"].x)) % 360.0
        # a corner wider than 150 deg is a straight continuation: a fillet there would run almost parallel to
        # the edges and push its tangent points (and the road trims) tens of metres out
        fil = _fillet(pa, a["d"], pb, b["d"], corner_radius) if span <= 150.0 else None
        offs = [0.0, a["curb"], a["curb"] + max(swa, swb)]
        if fil is None:
            for k, off in enumerate(offs):
                mid = ((at - la * (a["half_l"] + off)) + (at + lb * (b["half_r"] + off))) * 0.5
                rings.append(([mid], mid, 0.0))
        else:
            pts, C, t, centre, a0, da, Rr = fil
            for k, off in enumerate(offs):
                rk = Rr - off
                if rk > 0.05:
                    rings.append(([Vector((centre.x + rk * math.cos(a0 + da * j / 8), centre.y + rk * math.sin(a0 + da * j / 8), 0.0)) for j in range(9)], C, t))
                else:
                    rings.append(([Vector((centre.x, centre.y, 0.0))], C, t))
        corners.append(dict(a=a, b=b, la=la, lb=lb, rings=rings))
    cw = crossing_width
    for i, a in enumerate(approaches):
        reach = 0.0
        for c in (corners[i - 1], corners[i]):
            for pts, C, t in c["rings"]:
                reach = max(reach, max((p - at).dot(a["d"]) for p in pts))
        a["trim"] = max(reach + 0.3, a["half"] + 1.0)
        a["cross"] = crosswalks and (a["swl"] > 0 or a["swr"] > 0)
        clear = a["trim"] + (stop_setback + cw + 5.0 if a["cross"] else 3.0)
        _set_end(a, a["trim"], clear, z, ramp=a["cross"])
        mod = a["road"].modifiers["MRS_Road"]
        mod_input_set(mod, "Ramp Offset", stop_setback); mod_input_set(mod, "Ramp Width", cw)
    bm = bmesh.new()
    def V(p, zz): return bm.verts.new((p.x, p.y, zz))
    def quad(p0, p1, p2, p3, zz, mat):
        try:
            ff = bm.faces.new([V(p, zz) for p in (p0, p1, p2, p3)]); ff.material_index = mat; return ff
        except ValueError: return None
    poly = []
    for i, a in enumerate(approaches):
        r = a["d"].cross(UP).normalized(); end = at + a["d"] * a["trim"]
        poly.append(end + r * a["half_r"]); poly.append(end - r * a["half_l"])
        poly.extend(corners[i]["rings"][0][0])
    verts = []; last = None
    for p in poly:
        if last is not None and (p - last).length < 0.02: continue
        verts.append(V(p, z)); last = p
    try:
        f = bm.faces.new(verts); f.material_index = 0
    except ValueError: pass
    for c in corners:
        a, b = c["a"], c["b"]
        if a["h"] <= 0 and b["h"] <= 0: continue
        h = max(a["h"], b["h"])
        ea = at + a["d"] * a["trim"]; eb = at + b["d"] * b["trim"]
        def ring_pts(k):
            offa = (a["half_l"], a["half_l"] + a["curb"], a["half_l"] + a["curb"] + a["swl"])[k]
            offb = (b["half_r"], b["half_r"] + b["curb"], b["half_r"] + b["curb"] + b["swr"])[k]
            return [ea - c["la"] * offa] + list(c["rings"][k][0]) + [eb + c["lb"] * offb]
        r0, r1, r2 = ring_pts(0), ring_pts(1), ring_pts(2)
        def loft(ra, rb, za, zb, mat):
            m = max(len(ra), len(rb))
            def samp(ring, k):
                if len(ring) == 1: return ring[0]
                t = k / (m - 1) * (len(ring) - 1); i0 = int(t); i1 = min(len(ring) - 1, i0 + 1); f_ = t - i0
                return ring[i0] * (1 - f_) + ring[i1] * f_
            for k in range(m - 1):
                p0, p1, p2, p3 = samp(ra, k), samp(ra, k + 1), samp(rb, k + 1), samp(rb, k)
                try:
                    ff = bm.faces.new((V(p0, za), V(p1, za), V(p2, zb), V(p3, zb))); ff.material_index = mat
                except ValueError: pass
        loft(r0, r0, z, z + h, 2); loft(r0, r1, z + h, z + h, 2)
        if a["swl"] > 0 or b["swr"] > 0:
            loft(r1, r2, z + h, z + h, 3); loft(r2, r2, z + h, z, 2)
    crossings_meta = []
    for ai, a in enumerate(approaches):
        r = a["d"].cross(UP).normalized(); end = at + a["d"] * a["trim"]
        med = a["median"] * 0.5
        y0 = stop_setback; y1 = y0 + cw
        in_r = -1.0 if a["rht"] else 1.0            # incoming traffic is on the junction's left (looking out) under RHT
        half_in = a["half_l"] if in_r < 0 else a["half_r"]
        crown_pct = road_input(a["road"], "Crown") or 0.0; lock_len = road_input(a["road"], "Lock Length") or 14.0
        crown_h = crown_pct * 0.01 * max(a["half_l"], a["half_r"])
        def zc(x, d):
            """Residual camber on the road stub `d` m beyond the trimmed end (the road flattens its crown toward the junction)."""
            half = a["half_r"] if x > 0 else a["half_l"]
            f = min(1.0, max(0.0, d / lock_len)); f = f * f * (3 - 2 * f)
            return crown_h * max(0.0, 1.0 - (abs(x) / max(half, 0.01)) ** 2) * f
        def stripe(x0, x1, ya, yb, mat=1, lift=Z_PAINT):
            try:
                ff = bm.faces.new((V(end + a["d"] * ya + r * x0, z + lift + zc(x0, ya)), V(end + a["d"] * ya + r * x1, z + lift + zc(x1, ya)),
                                   V(end + a["d"] * yb + r * x1, z + lift + zc(x1, yb)), V(end + a["d"] * yb + r * x0, z + lift + zc(x0, yb)))); ff.material_index = mat
            except ValueError: pass
        if a["cross"]:
            has_refuge = refuge and med >= 0.85
            spans = [(-a["half_l"] + 0.3, -med - 0.4), (med + 0.4, a["half_r"] - 0.3)] if has_refuge else [(-a["half_l"] + 0.3, a["half_r"] - 0.3)]
            for x_lo, x_hi in spans:
                if crossing == "zebra":
                    x = x_lo
                    while x + 0.5 <= x_hi:
                        stripe(x, x + 0.5, y0, y1); x += 1.0
                else:
                    stripe(x_lo, x_hi, y0, y0 + 0.2); stripe(x_lo, x_hi, y1 - 0.2, y1)
            crossings_meta.append({"id": "%s_X%d" % (name, ai), "road": a["road"].name, "end": "start" if a["start"] else "end",
                                   "from": list(end + a["d"] * (y0 + cw / 2) - r * (a["half_l"] + a["curb"])), "to": list(end + a["d"] * (y0 + cw / 2) + r * (a["half_r"] + a["curb"])),
                                   "style": crossing, "refuge": has_refuge})
            if has_refuge:
                quad(end + a["d"] * (y0 - 0.3) - r * med, end + a["d"] * (y0 - 0.3) + r * med, end + a["d"] * (y1 + 0.3) + r * med, end + a["d"] * (y1 + 0.3) - r * med, z + 0.02, 5)
            if stop_lines and a["lanes_in"] > 0:
                xa, xb = sorted((in_r * (med + 0.05), in_r * half_in))
                stripe(xa, xb, y1 + 0.4, y1 + 0.8)
        elif stop_lines and a["lanes_in"] > 0:
            xa, xb = sorted((in_r * (med + 0.05), in_r * half_in))
            stripe(xa, xb, 1.0, 1.4)
        if bike_crossings:
            for s, sgn in (("r", 1.0), ("l", -1.0)):
                if not a.get("bike_on_" + s): continue
                x0, x1 = sorted((a["bike0_" + s] * sgn, a["bike1_" + s] * sgn))
                ymax = (y1 + 1.0) if a["cross"] else 2.5
                stripe(x0, x1, 0.0, ymax, 6, 0.003)
                yy = 0.3
                while yy + 0.4 <= ymax:
                    stripe(x0 - 0.1, x0 + 0.3, yy, yy + 0.4); stripe(x1 - 0.3, x1 + 0.1, yy, yy + 0.4)
                    yy += 0.8
        if med > 0.05:
            nose_y = (y1 + 0.3) if (a["cross"] and refuge and med >= 0.9) else 0.0
            mh = max(0.02, a["h"] if a["h"] > 0 else 0.15)
            base = end + a["d"] * nose_y
            ring = [base + r * (med * math.cos(math.pi * k / 8)) - a["d"] * (med * math.sin(math.pi * k / 8)) for k in range(9)]
            try:
                ff = bm.faces.new([V(q, z + mh) for q in ring]); ff.material_index = 2
            except ValueError: pass
            for k in range(8):
                try:
                    ff = bm.faces.new((V(ring[k], z), V(ring[k + 1], z), V(ring[k + 1], z + mh), V(ring[k], z + mh))); ff.material_index = 2
                except ValueError: pass
            if nose_y > 0.0:
                quad(end + r * med, end - r * med, base - r * med, base + r * med, z + 0.02, 5)
    meta = {"at": list(at), "roads": [a["road"].name for a in approaches], "crosswalks": crosswalks, "stop_lines": stop_lines, "corner_radius": corner_radius,
            "traffic_lights": traffic_lights, "control": control, "main_roads": sorted(main_roads), "terrain": terrain.name if terrain else "", "z": z, "type": "junction",
            "crossing": crossing, "stop_setback": stop_setback, "refuge": refuge, "crossings": crossings_meta,
            "approaches": [{"road": a["road"].name, "end": "start" if a["start"] else "end", "heading": [a["d"].x, a["d"].y], "trim": a["trim"],
                            "lanes_in": a["lanes_in"], "lanes_out": a["lanes_out"],
                            "half_l": a["half_l"], "half_r": a["half_r"], "main": a["road"].name in main_roads} for a in approaches]}
    o = _mesh_object(name, bm, collection, _mats(), meta)
    if traffic_lights and n >= 3:
        _place_signals(name, o, at, z, approaches, corners, collection)
    return o


def _place_signals(name, jobj, at, z, approaches, corners, collection):
    """Signal poles on the corners: the pole at corner (a, b) stands on a's left sidewalk corner and faces
    the cars arriving on a (looking out along a); combined vehicle + pedestrian head. IDs link heads to
    approaches and crossings; phases pair opposite approaches (no conflicting greens)."""
    try:
        from . import signage
    except ImportError:
        signage = None
    n = len(approaches)
    phases = []
    for i, a in enumerate(approaches):
        opp = next((j for j in range(n) if j != i and abs(approaches[j]["d"].dot(a["d"]) + 1.0) < 0.35), None)
        grp = tuple(sorted({i} | ({opp} if opp is not None else set())))
        if grp not in phases: phases.append(grp)
    signals_meta = []
    for i, c in enumerate(corners):
        a, b = c["a"], c["b"]
        ring = c["rings"][1][0]
        mid = ring[len(ring) // 2]
        out_v = (mid - at); out_v.z = 0; out_v.normalize()
        pos = Vector((mid.x, mid.y, z + max(a["h"], b["h"]))) + out_v * 0.7
        d = a["d"]
        sid = "%s_S%d" % (name, i)
        if signage is not None:
            sig = signage.make_signal(sid, style="combined", pole_height=4.2, collection=collection)
            sig.location = pos
            sig.rotation_euler = (0, 0, math.atan2(d.y, d.x) + math.pi / 2)      # heads (local -Y) look along +d at the arriving cars
        else:
            lights = bpy.data.collections.get(MRS + "TrafficLights")
            src = next((ob for ob in lights.objects), None) if lights else None
            if src is None: continue
            sig = bpy.data.objects.new(sid, src.data); collection.objects.link(sig)
            sig.location = pos; sig.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
        sig.parent = jobj; sig.matrix_parent_inverse = jobj.matrix_world.inverted()
        ai = approaches.index(a)
        phase = next(k for k, p in enumerate(phases) if ai in p)
        sig["mrs_signal_id"] = sid
        signals_meta.append({"id": sid, "controls_road": a["road"].name, "approach": ai, "phase": phase, "pedestrian_crossing": "%s_X%d" % (name, approaches.index(b)),
                             "position": list(pos), "heading": [d.x, d.y]})
    meta = dict(jobj["mrs_junction"]); meta["signals"] = signals_meta; meta["signal_phases"] = [list(p) for p in phases]
    jobj["mrs_junction"] = meta


def build_dead_end(name, road, end="end", radius=9.0, collection=None, terrain=None, through_path=True, path_width=3.0, path_length=14.0):
    """Turning circle (cul-de-sac) at one end of a road. The sidewalk continues round the bulb; with
    `through_path` a filtered pedestrian / cycle path leaves the far side of the bulb (dropped kerb flush
    with the carriageway, so cycle lanes and sidewalks continue instead of ending abruptly)."""
    (p0, t0, _), (p1, t1, _) = road_ends(road)
    p, t, is_start = (p0, t0, True) if end == "start" else (p1, t1, False)
    w = road_widths(road)
    inward = Vector((t.x, t.y, 0)).normalized()   # road_ends tangents point back into the road
    d = -inward                                     # outward, past the road end
    centre = p + d * (radius - 1.0)
    z = _ground_z(p, terrain) if terrain is not None else p.z
    a = dict(road=road, start=is_start)
    half = max(w["half_l"], w["half_r"]) + w["curb"] + max(w["swl"], w["swr"])
    trim = max(0.0, math.sqrt(max(0.0, radius ** 2 - half ** 2)) - (radius - 1.0))     # the road ends where its edges meet the circle
    _set_end(a, trim, trim + 4.0, z)
    bm = bmesh.new()
    def V(q, zz): return bm.verts.new((q.x, q.y, zz))
    nseg = 40
    circle = [centre + Vector((math.cos(2 * math.pi * k / nseg) * radius, math.sin(2 * math.pi * k / nseg) * radius, 0)) for k in range(nseg)]
    f = bm.faces.new([V(q, z) for q in circle]); f.material_index = 0
    h = w["h"]; curb = w["curb"]; sw = max(w["swl"], w["swr"])
    path_pts = []
    if h > 0:
        ring1 = [centre + (q - centre).normalized() * (radius + curb) for q in circle]
        ring2 = [centre + (q - centre).normalized() * (radius + curb + sw) for q in circle]
        back = inward
        gap_cos = math.cos(math.asin(min(1.0, (w["half"] + curb + sw) / radius)))
        half_path = math.asin(min(1.0, (path_width / 2 + 0.3) / (radius + curb)))
        for k in range(nseg):
            q0, q1 = circle[k], circle[(k + 1) % nseg]
            m = ((q0 + q1) * 0.5 - centre).normalized()
            if m.dot(back) > gap_cos: continue
            dropped = through_path and math.acos(max(-1.0, min(1.0, m.dot(d)))) < half_path
            hh = 0.0 if dropped else h
            if not dropped:
                ff = bm.faces.new((V(q0, z), V(q1, z), V(ring1[(k + 1) % nseg], z + h), V(ring1[k], z + h))); ff.material_index = 2
            # dropped kerb: the paving ramps from the carriageway to the sidewalk level across the ring
            ff = bm.faces.new((V(ring1[k] if not dropped else q0, z + hh), V(ring1[(k + 1) % nseg] if not dropped else q1, z + hh), V(ring2[(k + 1) % nseg], z + h), V(ring2[k], z + h)))
            ff.material_index = 5 if dropped else 2
            ff = bm.faces.new((V(ring2[k], z + h), V(ring2[(k + 1) % nseg], z + h), V(ring2[(k + 1) % nseg], z), V(ring2[k], z))); ff.material_index = 2
        if through_path:
            # paved path leaving the bulb, sidewalk height, edges skirted to the ground
            s_ = Vector((-d.y, d.x, 0.0)) * (path_width / 2)
            a0 = centre + d * (radius + curb + sw - 0.05); a1 = a0 + d * path_length
            q = [a0 - s_, a0 + s_, a1 + s_, a1 - s_]
            ff = bm.faces.new([V(x, z + h) for x in q]); ff.material_index = 3
            for k2 in range(4):
                x0, x1 = q[k2], q[(k2 + 1) % 4]
                ff = bm.faces.new((V(x1, z + h), V(x0, z + h), V(x0, z - 0.2), V(x1, z - 0.2))); ff.material_index = 2
            path_pts = [list(centre + d * radius), list(a0), list(a0 + d * (path_length / 2)), list(a1)]
            path_pts = [[c[0], c[1], z + h] for c in path_pts]
    meta = {"at": list(p), "roads": [road.name], "end": end, "radius": radius, "terrain": terrain.name if terrain else "", "z": z, "type": "dead_end",
            "through_path": bool(through_path), "path_width": path_width, "path_length": path_length, "path": path_pts}
    return _mesh_object(name, bm, collection or road.users_collection[0], _mats(), meta)


def _zebra_band(bm, V, end, d, r, z, x0, x1, y0, y1, mat, zc=None, pitch=1.0, bar=0.5):
    x = x0
    while x + bar <= x1:
        q = [end + d * y0 + r * x, end + d * y0 + r * (x + bar), end + d * y1 + r * (x + bar), end + d * y1 + r * x]
        zz = [z + Z_PAINT + (zc(xx, yy) if zc else 0.0) for xx, yy in ((x, y0), (x + bar, y0), (x + bar, y1), (x, y1))]
        try:
            ff = bm.faces.new([V(qq, z_) for qq, z_ in zip(q, zz)]); ff.material_index = mat
        except ValueError: pass
        x += pitch


def build_roundabout(name, at, roads, collection, island_radius=8.0, lanes=1, lane_width=5.5, snap=0.8, terrain=None, sidewalk=2.0, curb=0.25, h=0.15,
                     crossings=True, crossing_setback=1.5, crossing_width=2.5, bike_crossings=True):
    """Roundabout: raised central island, circulatory carriageway, approaches trimmed at the outer
    circle with rounded entries, yield lines at each entry, outer sidewalk ring between approaches.
    v3 parity: zebra crossings set back on every arm with kerb ramps + tactile paving on the road
    sidewalks, corner paving + kerbs that join each arm's sidewalks to the ring (continuous walking
    route), and - when an arm has a cycleway - a coloured parallel bicycle crossing beside the zebra with
    the ring widened to a shared foot / cycle path (meta shared_path)."""
    at = Vector(at)
    approaches = _approaches(at, roads, snap)
    if len(approaches) < 2: raise ValueError("%s: a roundabout needs at least 2 approaches" % name)
    z = _ground_z(at, terrain) if terrain is not None else at.z
    r_in = island_radius; r_out = island_radius + lanes * lane_width
    any_bike = bike_crossings and any(a.get("bike_on_l") or a.get("bike_on_r") for a in approaches)
    if any_bike: sidewalk = max(sidewalk, 3.0)
    bm = bmesh.new()
    def V(q, zz): return bm.verts.new((q.x, q.y, zz))
    nseg = 64
    def circ(rad, k): return at + Vector((math.cos(2 * math.pi * k / nseg) * rad, math.sin(2 * math.pi * k / nseg) * rad, 0))
    for k in range(nseg):
        ff = bm.faces.new((V(circ(r_in, k), z), V(circ(r_out, k), z), V(circ(r_out, k + 1), z), V(circ(r_in, k + 1), z))); ff.material_index = 0
    for k in range(nseg):
        ff = bm.faces.new((V(circ(r_in, k), z), V(circ(r_in, k + 1), z), V(circ(r_in, k + 1), z + h), V(circ(r_in, k), z + h))); ff.material_index = 2
        ff = bm.faces.new((V(circ(r_in, k), z + h), V(circ(r_in, k + 1), z + h), V(circ(r_in - curb, k + 1), z + h), V(circ(r_in - curb, k), z + h))); ff.material_index = 2
    f = bm.faces.new([V(circ(r_in - curb, k), z + h) for k in range(nseg)]); f.material_index = 2
    for ring_i in range(4):
        rad0 = (r_in - curb) * (1 - ring_i / 4); rad1 = (r_in - curb) * (1 - (ring_i + 1) / 4)
        z0 = z + h + 0.35 * (1 - (1 - ring_i / 4) ** 2); z1 = z + h + 0.35 * (1 - (1 - (ring_i + 1) / 4) ** 2)
        for k in range(nseg):
            if rad1 < 0.05:
                ff = bm.faces.new((V(circ(rad0, k), z0), V(circ(rad0, k + 1), z0), V(at, z1)))
            else:
                ff = bm.faces.new((V(circ(rad0, k), z0), V(circ(rad0, k + 1), z0), V(circ(rad1, k + 1), z1), V(circ(rad1, k), z1)))
            ff.material_index = 2
    occupied = []
    crossings_meta = []
    cw = crossing_width
    for a in approaches:
        d = a["d"]; r = d.cross(UP).normalized()
        trim = math.sqrt(max(0.0, r_out ** 2 - 0.0)) + a["half"] * 0.6 + 1.0
        a["trim"] = trim
        has_sw = (a["swl"] > 0 or a["swr"] > 0)
        cross = crossings and has_sw
        _set_end(a, trim, trim + crossing_setback + cw + (2.5 if any_bike else 0.0) + 5.0, z, ramp=cross)
        if cross:
            mod = a["road"].modifiers["MRS_Road"]; mod_input_set(mod, "Ramp Offset", crossing_setback); mod_input_set(mod, "Ramp Width", cw)
        end = at + d * trim
        def edge_to_circle(sign, half):
            p = end + r * sign * half
            q = at + (p - at).normalized() * r_out
            pts = []
            for k in range(7):
                t = k / 6.0
                ctrl = Vector((p.x, p.y, 0)) - d * (half * 1.2)
                pts.append((1 - t) ** 2 * p + 2 * (1 - t) * t * ctrl + t ** 2 * q)
            return pts
        right = edge_to_circle(1.0, a["half_r"]); left = edge_to_circle(-1.0, a["half_l"])
        ang_r = math.atan2(right[-1].y - at.y, right[-1].x - at.x); ang_l = math.atan2(left[-1].y - at.y, left[-1].x - at.x)
        da = (ang_l - ang_r) % (2 * math.pi)
        arc = [at + Vector((math.cos(ang_r + da * k / 8) * r_out, math.sin(ang_r + da * k / 8) * r_out, 0)) for k in range(9)]
        outline = right + arc[1:-1] + list(reversed(left))
        verts = []
        for p in outline:
            if verts and (p - outline[0]).length < 0.01: continue
            verts.append(V(p, z))
        try:
            ff = bm.faces.new(verts); ff.material_index = 0
        except ValueError: pass
        # corner paving: kerb along the entry curve and paving out to the ring sector, so the arm's
        # sidewalks run into the ring without a gap (both sides of every arm)
        ang = math.atan2(d.y, d.x)
        half_ang = math.asin(min(1.0, (a["half"] + curb + 1.5) / r_out)) + 0.12
        occupied.append((ang, half_ang))
        for sign, curve, sw_, half_ in ((1.0, right, a["swr"], a["half_r"]), (-1.0, left, a["swl"], a["half_l"])):
            if sw_ <= 0.05 or h <= 0: continue
            k_edge = (ang - sign * half_ang) / (2 * math.pi) * nseg
            k_edge = math.floor(k_edge) if sign > 0 else math.ceil(k_edge)
            ring_in = circ(r_out + curb, k_edge); ring_out = circ(r_out + curb + sidewalk, k_edge)
            kerb_end = end + r * sign * (half_ + curb); back_end = end + r * sign * (half_ + curb + sw_)
            nC = len(curve)
            inner = [c + (c - at).normalized() * 0.0 for c in curve]
            outer = [back_end.lerp(ring_out, i / (nC - 1)) for i in range(nC)]
            inner_k = [kerb_end.lerp(ring_in, i / (nC - 1)) for i in range(nC)]
            for i in range(nC - 1):
                try:
                    ff = bm.faces.new((V(curve[i], z), V(curve[i + 1], z), V(inner_k[i + 1], z + h), V(inner_k[i], z + h))); ff.material_index = 2
                    ff = bm.faces.new((V(inner_k[i], z + h), V(inner_k[i + 1], z + h), V(outer[i + 1], z + h), V(outer[i], z + h))); ff.material_index = 3
                    ff = bm.faces.new((V(outer[i], z + h), V(outer[i + 1], z + h), V(outer[i + 1], z), V(outer[i], z))); ff.material_index = 2
                except ValueError: pass
        # yield line
        if a["lanes_in"] > 0:
            for k in range(int(a["half_l"] / 0.8)):
                x = 0.2 + k * 0.8
                if x + 0.5 > a["half_l"]: break
                base = at + d * (r_out + 0.5)
                p0 = base - r * x; p1 = base - r * (x + 0.5); p2 = p1 + d * 0.5; p3 = p0 + d * 0.5
                ff = bm.faces.new([V(p, z + Z_PAINT) for p in (p0, p1, p2, p3)]); ff.material_index = 1
        if a["lanes_b"] > 0 and a["lanes_f"] > 0 and a["median"] < 0.1:
            w0 = 0.5; L0 = r_out + 1.5; L1 = trim - 1.5
            pts = [end * 0 + at + d * L0, at + d * (L0 + 2.0) + r * 0.9, at + d * L1 + r * w0, at + d * L1 - r * w0, at + d * (L0 + 2.0) - r * 0.9]
            ff = bm.faces.new([V(p, z + h) for p in pts]); ff.material_index = 2
            for k in range(len(pts)):
                p0, p1 = pts[k], pts[(k + 1) % len(pts)]
                ff = bm.faces.new((V(p0, z), V(p1, z), V(p1, z + h), V(p0, z + h))); ff.material_index = 2
        # crossing on the arm, beyond the trimmed end (the road's own ramps + tactile line up with it)
        if cross:
            y0 = crossing_setback; y1 = y0 + cw
            _zebra_band(bm, V, end, d, r, z, -a["half_l"] + 0.3, a["half_r"] - 0.3, y0, y1, 1)
            bike_here = bike_crossings and (a.get("bike_on_l") or a.get("bike_on_r"))
            if bike_here:
                # parallel crossing: coloured cycle band beside the zebra, bordered by elephant-feet squares
                b0, b1 = y1 + 0.3, y1 + 2.3
                q = [end + d * b0 - r * (a["half_l"] - 0.3), end + d * b0 + r * (a["half_r"] - 0.3), end + d * b1 + r * (a["half_r"] - 0.3), end + d * b1 - r * (a["half_l"] - 0.3)]
                try:
                    ff = bm.faces.new([V(qq, z + 0.003) for qq in q]); ff.material_index = 6
                except ValueError: pass
                for yy in (b0 - 0.05, b1 - 0.35):
                    _zebra_band(bm, V, end, d, r, z, -a["half_l"] + 0.3, a["half_r"] - 0.3, yy, yy + 0.4, 1, pitch=0.8, bar=0.4)
            crossings_meta.append({"id": "%s_X%d" % (name, len(crossings_meta)), "road": a["road"].name, "end": "start" if a["start"] else "end",
                                   "from": list(end + d * (y0 + cw / 2) - r * (a["half_l"] + a["curb"])), "to": list(end + d * (y0 + cw / 2) + r * (a["half_r"] + a["curb"])),
                                   "style": "zebra", "refuge": False, "y": y0 + cw / 2, "bike": bool(bike_here)})
    if sidewalk > 0:
        def free(k):
            ang = 2 * math.pi * (k + 0.5) / nseg
            return all(abs((ang - a0 + math.pi) % (2 * math.pi) - math.pi) > ha for a0, ha in occupied)
        for k in range(nseg):
            if not free(k): continue
            ff = bm.faces.new((V(circ(r_out, k), z), V(circ(r_out, k + 1), z), V(circ(r_out, k + 1), z + h), V(circ(r_out, k), z + h))); ff.material_index = 2
            ff = bm.faces.new((V(circ(r_out, k), z + h), V(circ(r_out, k + 1), z + h), V(circ(r_out + curb + sidewalk, k + 1), z + h), V(circ(r_out + curb + sidewalk, k), z + h))); ff.material_index = 3
            ff = bm.faces.new((V(circ(r_out + curb + sidewalk, k), z + h), V(circ(r_out + curb + sidewalk, k + 1), z + h), V(circ(r_out + curb + sidewalk, k + 1), z), V(circ(r_out + curb + sidewalk, k), z))); ff.material_index = 2
    meta = {"at": list(at), "roads": [a["road"].name for a in approaches], "island_radius": island_radius, "lanes": lanes, "lane_width": lane_width,
            "terrain": terrain.name if terrain else "", "z": z, "type": "roundabout", "sidewalk": sidewalk, "crossings": crossings_meta,
            "crossing_setback": crossing_setback, "crossing_width": cw, "shared_path": bool(any_bike), "crosswalks": bool(crossings),
            "approaches": [{"road": a["road"].name, "end": "start" if a["start"] else "end", "heading": [a["d"].x, a["d"].y], "trim": a["trim"],
                            "lanes_in": a["lanes_in"], "lanes_out": a["lanes_out"],
                            "half_l": a["half_l"], "half_r": a["half_r"], "main": False} for a in approaches]}
    return _mesh_object(name, bm, collection, _mats(), meta)


# ---------------------------------------------------------------------------- rebuild / auto update
def rebuild(obj):
    meta = obj.get("mrs_junction")
    if not meta: return None
    meta = dict(meta)
    roads = [bpy.data.objects[n] for n in meta["roads"] if n in bpy.data.objects]
    col = obj.users_collection[0]
    terrain = bpy.data.objects.get(meta.get("terrain", "")) if meta.get("terrain") else None
    at = Vector(meta["at"])
    if meta.get("type") == "roundabout":
        return build_roundabout(obj.name, at, roads, col, island_radius=meta["island_radius"], lanes=meta["lanes"], lane_width=meta["lane_width"], terrain=terrain,
                                sidewalk=meta.get("sidewalk", 2.0) if not meta.get("shared_path") else 2.0, crossings=meta.get("crosswalks", True),
                                crossing_setback=meta.get("crossing_setback", 1.5), crossing_width=meta.get("crossing_width", 2.5))
    if meta.get("type") == "dead_end":
        return build_dead_end(obj.name, roads[0], meta["end"], meta["radius"], col, terrain, through_path=meta.get("through_path", True),
                              path_width=meta.get("path_width", 3.0), path_length=meta.get("path_length", 14.0))
    # the junction point follows the roads' ends (average of the ends that were connected)
    ends = [p for r in roads for p, t, s in road_ends(r) if (p - at).length < 12.0]
    if ends: at = sum(ends, Vector()) / len(ends)
    return build_junction(obj.name, at, roads, col, meta.get("crosswalks", True), meta.get("stop_lines", True), meta.get("corner_radius", 6.0),
                          meta.get("traffic_lights", False), snap=6.0, terrain=terrain, crossing=meta.get("crossing", "zebra"), stop_setback=meta.get("stop_setback", 0.6),
                          refuge=meta.get("refuge", True), control=meta.get("control"), main_roads=list(meta.get("main_roads", [])))


def all_junctions():
    return [o for o in bpy.data.objects if o.get("mrs_junction") and o.type == "MESH"]


def rebuild_all():
    out = []
    for o in list(all_junctions()):
        try: out.append(rebuild(o))
        except Exception as e: print("junction rebuild failed", o.name, e)
    return out


_curve_hashes = {}


def _curve_hash(o):
    sp = o.data.splines[0] if o.data.splines else None
    if sp is None: return 0
    pts = sp.bezier_points if sp.type == "BEZIER" else sp.points
    return hash((tuple(round(c, 3) for p in pts for c in (p.co[:3] if sp.type != "BEZIER" else (*p.co, *p.handle_left, *p.handle_right))), tuple(round(c, 3) for c in o.matrix_world.translation)))


def _on_depsgraph(scene, depsgraph):
    changed = set()
    for u in depsgraph.updates:
        ob = u.id
        if isinstance(ob, bpy.types.Object) and ob.type == "CURVE" and "MRS_Road" in ob.modifiers:
            hsh = _curve_hash(ob)
            if _curve_hashes.get(ob.name) != hsh:
                _curve_hashes[ob.name] = hsh; changed.add(ob.name)
    if not changed: return
    for j in all_junctions():
        if changed & set(j["mrs_junction"]["roads"]):
            try: bpy.app.timers.register(lambda jn=j.name: (rebuild(bpy.data.objects[jn]) if jn in bpy.data.objects else None) and None, first_interval=0.05)
            except Exception as e: print("auto junction", e)


def enable_auto_update(on=True):
    h = bpy.app.handlers.depsgraph_update_post
    while _on_depsgraph in h: h.remove(_on_depsgraph)
    if on:
        for r in all_roads(): _curve_hashes[r.name] = _curve_hash(r)
        h.append(_on_depsgraph)
