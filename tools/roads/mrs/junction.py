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


def _smooth01(v):
    v = max(0.0, min(1.0, v)); return v * v * (3 - 2 * v)


def _road_depsgraph(road):
    """Evaluated depsgraph of a scene that contains `road`. rebuild_all() rebuilds the junctions of every scene; with
    another scene active the road was not in the depsgraph, the fit found no evaluated geometry and the junction
    fell back to the straight-line trim (a 3 cm crack at the avenue end of the T-junction)."""
    import bpy
    from .nodes import depsgraph
    scs = list(getattr(road, "users_scene", ()))
    if not scs: return depsgraph()
    sc = scs[0]
    if sc == bpy.context.scene: return bpy.context.evaluated_depsgraph_get()
    vl = sc.view_layers[0]; vl.update()
    return vl.depsgraph


def _end_section(road, start):
    """(E, R): centre and unit right vector of the road's evaluated end cross-section, a least-squares fit
    position = E + R * lat over the vertices of its first (start) / last station (|lat| <= 30 m)."""
    dg = _road_depsgraph(road); ev = road.evaluated_get(dg); me = ev.to_mesh()
    try:
        if "along" not in me.attributes or "lat" not in me.attributes: return None
        al = [d.value for d in me.attributes["along"].data]; lt = [d.value for d in me.attributes["lat"].data]
        if not al: return None
        tgt = min(al) if start else max(al); M = road.matrix_world
        pts = [(lt[i], M @ me.vertices[i].co) for i in range(len(al)) if abs(al[i] - tgt) < 0.004 and abs(lt[i]) <= 30.0]
    finally:
        ev.to_mesh_clear()
    n = len(pts)
    if n < 3: return None
    sl = sum(l for l, _ in pts); sll = sum(l * l for l, _ in pts); den = n * sll - sl * sl
    if abs(den) < 1e-9: return None
    sx = sum(p.x for _, p in pts); sy = sum(p.y for _, p in pts)
    slx = sum(l * p.x for l, p in pts); sly = sum(l * p.y for l, p in pts)
    rx = (n * slx - sl * sx) / den; ry = (n * sly - sl * sy) / den
    E = Vector(((sx - rx * sl) / n, (sy - ry * sl) / n, 0.0)); R = Vector((rx, ry, 0.0))
    if R.length < 0.5: return None
    # R keeps its fitted length: a banked end (tilted junction plane) is narrower in plan by cos(bank), and the
    # junction's edge points E + R * lat then land on the road's own edges
    return E, (R.normalized() if abs(R.length - 1.0) < 1e-4 else R)


def _actual_ends(approaches, at, setback, cw):
    """After the trims are set: each approach's real evaluated end (centre, right-of-d vector looking out) and the
    road's sidewalk ramp factor at its end (same dip as the road group), so the junction surface, corner paving and
    kerbs meet the road edge to edge (no 1-4 cm gaps from arc-length vs straight-line trims, no ramp steps)."""
    from .structures import centre_line, road_sample
    for a in approaches:
        road = a["road"]
        a["end_fit"] = "section"
        sec = _end_section(road, a["start"])          # first: the evaluated end cross-section (in the road's own scene)
        cl = None
        if sec is None:
            try:
                cl = centre_line(road)
            except Exception:
                cl = None
            if not cl:
                print("junction: no evaluated end for %s; straight-line trim used" % road.name)
                a["end_fit"] = "trim"
                a["E"] = at + a["d"] * a["trim"]; a["R"] = a["d"].cross(UP).normalized(); a["D"] = a["d"]; continue
        if sec is not None:
            # the road's real end cross-section (fitted to its first / last station's vertices): the chord tangent of
            # the cached centre line left a 0.7 m wedge at the curved S-curve end
            E, Rr = sec
            a["E"] = E; a["R"] = Rr * (1.0 if a["start"] else -1.0)
            t = UP.cross(Rr.normalized()).normalized(); a["D"] = t * (1.0 if a["start"] else -1.0)
        else:
            a["end_fit"] = "centre_line"
            print("junction: end section of %s not found; centre-line end used" % road.name)
            st = cl[0] if a["start"] else cl[-1]
            p, t, rr = road_sample(road, st[0])
            a["E"] = Vector((p.x, p.y, 0.0))
            a["R"] = Vector((rr.x, rr.y, 0.0)).normalized() * (1.0 if a["start"] else -1.0)
            a["D"] = Vector((t.x, t.y, 0.0)).normalized() * (1.0 if a["start"] else -1.0)
        if a.get("cross"):
            centre = setback + cw * 0.5; hw = cw * 0.5
            x = abs(0.0 - centre); v = 1.0 - max(0.0, min(1.0, (x - hw) / 1.0))
            a["ramp_f"] = 1.0 - 0.96 * _smooth01(v)
        else:
            a["ramp_f"] = 1.0


def _set_end(a, trim, clear, lock_z, ramp=False, bank=0.0, mark_clear=0.0, turns=7):
    """Write one road end's junction-derived inputs: trim, prop clear zone, height lock, crossing ramp, bank, the
    paint clear zone (no lane / centre / edge / bike paint over the crossing and stop line) and the movements open to
    the arriving lanes (1 left + 2 straight + 4 right: the lane arrows follow them)."""
    mod = a["road"].modifiers["MRS_Road"]
    s = a["start"]
    values = {("Trim Start" if s else "Trim End"): trim, ("Clear Start" if s else "Clear End"): clear, ("Lock Start" if s else "Lock End"): True,
              ("Lock Start Z" if s else "Lock End Z"): lock_z, ("Ramp Start" if s else "Ramp End"): bool(ramp)}
    optional = {("Bank Start" if s else "Bank End"): float(bank), ("Mark Clear Start" if s else "Mark Clear End"): float(mark_clear),
                ("Turns Start" if s else "Turns End"): int(turns)}
    try:
        items = mod.node_group.interface.items_tree
        for k, v in optional.items():
            if items.get(k) is not None: values[k] = v          # older road groups lack these inputs
    except Exception:
        pass
    for k, v in values.items(): mod_input_set(mod, k, v)
    inputs = dict(a["road"].get("mrs_inputs", {})); inputs.update(values); a["road"]["mrs_inputs"] = inputs
    a["road"].update_tag()


KIND_OF_SLOT = {0: 0.0, 1: 1.0, 2: 2.0, 3: 6.0, 4: 5.0, 5: 7.0, 6: 8.0, 7: 1.0}     # material slot -> kind attribute (7: yellow paint)

STRAIGHT_DEG = 35.0        # a leg within this angle of straight ahead is a "straight" movement; beyond it a left / right turn
UTURN_DEG = 160.0          # sharper than this is a U-turn (never a movement)
TURN_BIT = {"left": 1, "straight": 2, "right": 4}
BIKE_OPPOSITE = 0.85       # legs whose look-out directions have dot <= -this are opposite: a cycle band joins their lanes
STOP_LINE = (0.4, 0.4)     # stop line: gap after the crossing, width
NO_CROSS_STOP = 1.0        # stop line distance from the trimmed end without a crossing
STRIPE_STEP = 0.5          # junction paint is split across the road this often (follows the road's crown)
RAMP_DEPTH = 1.5           # crossing ramps rise from the kerb to the sidewalk's height over this width (road input Ramp Depth)
ARM_LANES = 2              # approaches with this many arriving lanes get a mast arm with one head over each lane
ARM_POLE = (0.8, 0.6)      # mast-arm pole: behind the stop line, behind the kerb (m)
ARM_HEIGHT = 7.0           # mast-arm pole height (heads clear the carriageway by ~5.3 m)


def turn_of(travel_in, travel_out):
    """Geometric movement from plan heading `travel_in` to `travel_out`: 'straight', 'left', 'right', or None (U-turn)."""
    ang = math.degrees(math.atan2(travel_in.x * travel_out.y - travel_in.y * travel_out.x, travel_in.dot(travel_out)))
    if abs(ang) > UTURN_DEG: return None
    return "straight" if abs(ang) < STRAIGHT_DEG else ("left" if ang > 0 else "right")


def movements(a, approaches):
    """Movements open to the traffic arriving on leg `a`: 1 left + 2 straight + 4 right, one bit per other leg that
    carries traffic away from the junction."""
    code = 0
    for b in approaches:
        if b is a or b.get("lanes_out", 0) <= 0: continue
        t = turn_of(-a["d"], b["d"])
        if t: code |= TURN_BIT[t]
    return code


def lane_use(code, n, rht=True):
    """Movement bits for each of `n` arriving lanes (index 0 nearest the centre) at a leg offering `code`: the lane
    nearest the centre takes the turn toward the centre side (left under right-hand traffic), the outermost lane the
    turn away from it, the lanes between go straight; a missing movement hands its lane the next one. The painted
    arrows (road.py, the same formulas as nodes) and the vehicle paths (movements.py) both follow this."""
    if n <= 1: return [code] * max(n, 0)
    cb = 1 if code & (1 if rht else 4) else 0; sb = 1 if code & 2 else 0; ob = 1 if code & (4 if rht else 1) else 0
    cbit, obit = (1, 4) if rht else (4, 1)
    def bits(c, s_, o): return (cbit if c else 0) | (2 if s_ else 0) | (obit if o else 0)
    out = []
    for k in range(n):
        if k == 0: out.append(bits(cb, sb or (not cb and not ob), not cb and not sb and ob))
        elif k == n - 1: out.append(bits(not ob and not sb and cb, sb or (not ob and not cb), ob))
        else: out.append(bits(not sb and cb, sb or (not cb and not ob), not sb and not cb and ob))
    return out


GIVE_WAY = (0.6, 0.3, 0.3)      # give-way line: dash, gap, width (m)
TEETH = (0.6, 0.8, 0.3)         # give-way triangles: base, height (pointing at the drivers), gap (after the line too)
STOP_TEXT = (1.0, 2.4, 0.7)     # STOP in each lane: gap after the stop line, length along the lane, width (x lane width)


BOX = (0.2, 1.6, 0.15, 0.6)     # yellow box: border width, hatch spacing, hatch width, inset from the approach ends (m)


def _box_marking(bm, V, approaches, z):
    """Yellow box junction (keep clear): a border and criss-cross hatching over the junction core, the convex hull of
    the approach ends inset by BOX[3], so it never reaches a crossing or a stop line."""
    pts = []
    for a in approaches:
        for x in (-a["half_l"], a["half_r"]): pts.append((a["E"] + a["R"] * x - a["D"] * BOX[3]).to_2d())
    # convex hull (monotone chain)
    pts = sorted(set((round(p.x, 4), round(p.y, 4)) for p in pts))
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(p)
    hull = [Vector(p) for p in lower[:-1] + upper[:-1]]
    if len(hull) < 3: return
    c = sum(hull, Vector((0.0, 0.0))) / len(hull)
    inner = [c + (p - c) * max(0.0, 1.0 - BOX[0] / max((p - c).length, 1e-6)) for p in hull]
    def face(q, lift=Z_PAINT):
        try: f = bm.faces.new([V(Vector((p.x, p.y, 0.0)), z + lift) for p in q]); f.material_index = 7
        except ValueError: pass
    for i in range(len(hull)): face([hull[i], hull[(i + 1) % len(hull)], inner[(i + 1) % len(hull)], inner[i]])
    # hatching at +-45 deg, clipped to the inner polygon (convex: one span per line)
    for ang in (math.pi / 4, -math.pi / 4):
        u = Vector((math.cos(ang), math.sin(ang))); nrm = Vector((-u.y, u.x))
        ds = [p.dot(nrm) for p in inner]; d = min(ds) + BOX[1] * 0.5
        while d < max(ds):
            span = []
            for i in range(len(inner)):
                p, q = inner[i], inner[(i + 1) % len(inner)]; dp, dq = p.dot(nrm) - d, q.dot(nrm) - d
                if (dp < 0) != (dq < 0): span.append(p + (q - p) * (dp / (dp - dq)))
            if len(span) == 2:
                a_, b_ = sorted(span, key=lambda v: v.dot(u)); h = nrm * (BOX[2] * 0.5)
                face([a_ - h, b_ - h, b_ + h, a_ + h], Z_PAINT + 0.0005)
            d += BOX[1]


def end_marking(control, main, lanes_in):
    """What a junction paints across an approach's arriving lanes, from its control: 'line' (signals: a stop line),
    'stop' (stop line + STOP in every lane), 'give_way' (dashed line + triangles: yield, and the minor roads of a
    priority junction), None (the main road of a priority junction, uncontrolled, no arriving lanes). The sign placer
    follows the same control (stop / yield / priority-road signs)."""
    if lanes_in <= 0: return None
    if control == "signals": return "line"
    if control == "stop": return "stop"
    if control == "yield" or (control == "priority" and not main): return "give_way"
    return None


def end_zone(cross, marking, setback, cw):
    """Distance from a trimmed road end over which the junction owns the paint (crossing, its end marking): the road's
    lane, centre, edge and cycle markings start beyond it."""
    y = setback + cw if cross else 0.0
    gap = STOP_LINE[0] if cross else NO_CROSS_STOP
    if marking in ("line", "stop"): return y + gap + STOP_LINE[1]
    if marking == "give_way": return y + gap + GIVE_WAY[2] + TEETH[2] + TEETH[1]
    return y + STOP_LINE[0] if cross else 0.0


_GLYPHS = {}


def glyph(text):
    """Triangles [(x, y) * 3] of `text` in Blender's built-in font (size 1, centred), made once per text in a scratch
    scene (no depsgraph rebuild of a big scene)."""
    if text in _GLYPHS: return _GLYPHS[text]
    sc = bpy.data.scenes.new("MRS_tmp_glyph")
    cu = bpy.data.curves.new("MRS_tmp_glyph", "FONT"); cu.body = text; cu.size = 1.0; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.resolution_u = 4; cu.fill_mode = "BOTH"
    ob = bpy.data.objects.new("MRS_tmp_glyph", cu); sc.collection.objects.link(ob)
    vl = sc.view_layers[0]; vl.update(); ev = ob.evaluated_get(vl.depsgraph); me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        tris = [[tuple(me.vertices[i].co[:2]) for i in t.vertices] for t in me.loop_triangles if all(abs(me.vertices[i].co.z) < 1e-4 for i in t.vertices)]
    finally:
        ev.to_mesh_clear(); bpy.data.objects.remove(ob); bpy.data.curves.remove(cu); bpy.data.scenes.remove(sc)
    _GLYPHS[text] = tris
    return tris


def _inside(poly, p):
    """Point-in-polygon (even-odd) in plan."""
    inside = False; n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a.y > p.y) != (b.y > p.y) and p.x < a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y): inside = not inside
    return inside


def _mats():
    """Material names for the junction slots (asphalt, paint, concrete, paving, cycleway, tactile, crossing),
    falling back when a dedicated material is missing."""
    def pick(*names):
        return next((MRS + n for n in names if bpy.data.materials.get(MRS + n)), MRS + "Concrete")
    return (pick("Asphalt"), pick("Paint"), pick("Concrete"), pick("Paving", "Concrete"), pick("Cycleway", "BikeLane"), pick("Tactile", "Paint"), pick("Cycleway", "BikeLane"),
            pick("PaintYellow", "Paint"))


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
    gs = me.attributes.new("ground_surface", "FLOAT", "FACE")      # a terrain grades to it (MRS_TerrainConform)
    gs.data.foreach_set("value", [1.0] * len(me.polygons))
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
                   main_roads=None, bike_crossings=True, crossing_width=2.5, edge_depth=0.0, plane=None, z=None, box=False):
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
    z_given = z
    if z is None: z = _ground_z(at, terrain) if terrain is not None else sum(zs) / len(zs)
    # plane = (gx, gy): the junction surface is the tilted plane z + g . (p - at) (a junction on a slope); every vertex,
    # the road locks and the road ends' cross-fall follow it
    gx, gy = (float(plane[0]), float(plane[1])) if plane else (0.0, 0.0)
    def dz(p): return gx * (p.x - at.x) + gy * (p.y - at.y)
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
        sw_c = max(swa, swb)
        offs = [0.0, a["curb"], a["curb"] + min(RAMP_DEPTH, sw_c * 0.6), a["curb"] + sw_c]      # asphalt, kerb, ramp top, back
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
        E0 = at + a["d"] * a["trim"]
        # the road's own right vector at this end: along d at a start, against d at an end
        rv = Vector((a["d"].y, -a["d"].x, 0.0)) if a["start"] else Vector((-a["d"].y, a["d"].x, 0.0))
        a["marking"] = end_marking(control, a["road"].name in main_roads, a["lanes_in"]) if stop_lines else None
        a["mark_clear"] = end_zone(a["cross"], a["marking"], stop_setback, cw)
        a["turns"] = movements(a, approaches)
        _set_end(a, a["trim"], clear, z + dz(E0), ramp=a["cross"], bank=math.atan(gx * rv.x + gy * rv.y), mark_clear=a["mark_clear"], turns=a["turns"])
        mod = a["road"].modifiers["MRS_Road"]
        mod_input_set(mod, "Ramp Offset", stop_setback); mod_input_set(mod, "Ramp Width", cw)
    _actual_ends(approaches, at, stop_setback, cw)
    bm = bmesh.new()
    def V(p, zz): return bm.verts.new((p.x, p.y, zz + dz(p)))
    def quad(p0, p1, p2, p3, zz, mat):
        try:
            ff = bm.faces.new([V(p, zz) for p in (p0, p1, p2, p3)]); ff.material_index = mat; return ff
        except ValueError: return None
    poly = []
    for i, a in enumerate(approaches):
        r = a["R"]; end = a["E"]
        poly.append(end + r * a["half_r"]); poly.append(end - r * a["half_l"])
        poly.extend(corners[i]["rings"][0][0])
    verts = []; last = None
    for p in poly:
        if last is not None and (p - last).length < 0.02: continue
        verts.append(V(p, z)); last = p
    try:
        f = bm.faces.new(verts); f.material_index = 0
    except ValueError: pass
    corner_paths = []
    for c in corners:
        a, b = c["a"], c["b"]
        if a["h"] <= 0 and b["h"] <= 0: continue
        h = max(a["h"], b["h"])
        ea = a["E"]; eb = b["E"]; la_ = a["R"]; lb_ = b["R"]
        def ring_pts(k):
            offa = (a["half_l"], a["half_l"] + a["curb"], a["half_l"] + a["curb"] + min(RAMP_DEPTH, a["swl"] * 0.6), a["half_l"] + a["curb"] + a["swl"])[k]
            offb = (b["half_r"], b["half_r"] + b["curb"], b["half_r"] + b["curb"] + min(RAMP_DEPTH, b["swr"] * 0.6), b["half_r"] + b["curb"] + b["swr"])[k]
            return [ea - la_ * offa] + list(c["rings"][k][0]) + [eb + lb_ * offb]
        r0, r1, r15, r2 = ring_pts(0), ring_pts(1), ring_pts(2), ring_pts(3)
        fa = a.get("ramp_f", 1.0); fb = b.get("ramp_f", 1.0)
        def hz(t):
            """corner height factor: the road's ramped sidewalk height at both ends, full height mid-corner"""
            wa = _smooth01(t / 0.35); wb = _smooth01((1.0 - t) / 0.35)
            return min(fa + (1.0 - fa) * wa, fb + (1.0 - fb) * wb)
        def loft(ra, rb, za, zb, mat):
            m = max(len(ra), len(rb))
            def samp(ring, k):
                if len(ring) == 1: return ring[0]
                t = k / (m - 1) * (len(ring) - 1); i0 = int(t); i1 = min(len(ring) - 1, i0 + 1); f_ = t - i0
                return ring[i0] * (1 - f_) + ring[i1] * f_
            def zv(zz, k): return zz(k / (m - 1)) if callable(zz) else zz
            for k in range(m - 1):
                p0, p1, p2, p3 = samp(ra, k), samp(ra, k + 1), samp(rb, k + 1), samp(rb, k)
                try:
                    ff = bm.faces.new((V(p0, zv(za, k)), V(p1, zv(za, k + 1)), V(p2, zv(zb, k + 1)), V(p3, zv(zb, k)))); ff.material_index = mat
                except ValueError: pass
        top = lambda t: z + h * hz(t)
        # the walking line round the corner (middle of the paving band), for the pedestrian route graph
        mm = max(len(r1), len(r2))
        def _sp(ring, k):
            if len(ring) == 1: return ring[0]
            tt = k / (mm - 1) * (len(ring) - 1); i0 = int(tt); i1 = min(len(ring) - 1, i0 + 1); f_ = tt - i0
            return ring[i0] * (1 - f_) + ring[i1] * f_
        corner_paths.append({"a": approaches.index(a), "b": approaches.index(b),
                             "points": [[round(c, 3) for c in ((_sp(r1, k) + _sp(r2, k)) * 0.5).to_2d()] + [round(top(k / (mm - 1)) + dz((_sp(r1, k) + _sp(r2, k)) * 0.5), 3)] for k in range(mm)]})
        full = z + h
        loft(r0, r0, z, top, 2); loft(r0, r1, top, top, 2)
        if a["swl"] > 0 or b["swr"] > 0:
            # the ramp: from the dipped kerb up to the full height over the ramp depth; the back of the sidewalk stays level
            loft(r1, r15, top, full, 3); loft(r15, r2, full, full, 3); loft(r2, r2, full, z - edge_depth, 2)
    crossings_meta = []
    for ai, a in enumerate(approaches):
        r = a["R"]; end = a["E"]
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
            # split across the road every STRIPE_STEP m so the paint follows the residual crown (one long quad across
            # a crowned stub lay under the crown's middle: crossing and stop lines showed only their tapered ends)
            k = max(1, int(math.ceil(abs(x1 - x0) / STRIPE_STEP)))
            for i in range(k):
                u0 = x0 + (x1 - x0) * i / k; u1 = x0 + (x1 - x0) * (i + 1) / k
                try:
                    ff = bm.faces.new((V(end + a["D"] * ya + r * u0, z + lift + zc(u0, ya)), V(end + a["D"] * ya + r * u1, z + lift + zc(u1, ya)),
                                       V(end + a["D"] * yb + r * u1, z + lift + zc(u1, yb)), V(end + a["D"] * yb + r * u0, z + lift + zc(u0, yb)))); ff.material_index = mat
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
                                   "from": list(end + a["D"] * (y0 + cw / 2) - r * (a["half_l"] + a["curb"])), "to": list(end + a["D"] * (y0 + cw / 2) + r * (a["half_r"] + a["curb"])),
                                   "style": crossing, "refuge": has_refuge})
            if has_refuge:
                quad(end + a["D"] * (y0 - 0.3) - r * med, end + a["D"] * (y0 - 0.3) + r * med, end + a["D"] * (y1 + 0.3) + r * med, end + a["D"] * (y1 + 0.3) - r * med, z + 0.02, 5)
        # the end marking across the arriving lanes (end_marking: from the junction's control)
        mk = a.get("marking")
        if mk:
            yl = (y1 + STOP_LINE[0]) if a["cross"] else NO_CROSS_STOP
            xa, xb = sorted((in_r * (med + 0.05), in_r * half_in))
            if mk in ("line", "stop"): stripe(xa, xb, yl, yl + STOP_LINE[1])
            if mk == "give_way":
                x = xa
                while x + GIVE_WAY[0] <= xb + 1e-6:
                    stripe(x, x + GIVE_WAY[0], yl, yl + GIVE_WAY[2]); x += GIVE_WAY[0] + GIVE_WAY[1]
                ty = yl + GIVE_WAY[2] + TEETH[2]; x = xa + TEETH[2]
                while x + TEETH[0] <= xb - TEETH[2] + 1e-6:              # triangles, apex toward the approaching drivers
                    pts = [(x, ty), (x + TEETH[0], ty), (x + TEETH[0] * 0.5, ty + TEETH[1])]
                    try:
                        ff = bm.faces.new([V(end + a["D"] * yy + r * xx, z + Z_PAINT + zc(xx, yy)) for xx, yy in pts]); ff.material_index = 1
                    except ValueError: pass
                    x += TEETH[0] + TEETH[2]
            if mk == "stop":
                # STOP in every arriving lane, read by its drivers (letters' tops toward the junction, elongated along the lane)
                tris = glyph("STOP")
                gx0 = min(p[0] for t in tris for p in t); gx1 = max(p[0] for t in tris for p in t)
                gy0 = min(p[1] for t in tris for p in t); gy1 = max(p[1] for t in tris for p in t)
                n_in = int(round(a["lanes_in"])); lw = a.get("lw", 3.0)
                sx = lw * STOP_TEXT[2] / max(gx1 - gx0, 1e-6); sy = STOP_TEXT[1] / max(gy1 - gy0, 1e-6)
                yt = yl + STOP_LINE[1] + STOP_TEXT[0]
                for k in range(n_in):
                    xc = in_r * (med + (k + 0.5) * lw)
                    for t in tris:
                        # the driver drives toward the junction (-D): reading to the right runs along -R
                        pts = [(xc - (gx - (gx0 + gx1) * 0.5) * sx, yt + (gy1 - gy) * sy) for gx, gy in t]
                        try:
                            ff = bm.faces.new([V(end + a["D"] * yy + r * xx, z + Z_PAINT + zc(xx, yy)) for xx, yy in pts]); ff.material_index = 1
                        except ValueError: pass
        if med > 0.05 and not (a["cross"] and refuge and med >= 0.85):
            # (with a refuge crossing the road's own median drops flush through the crossing - see road.py MHa -
            #  so no raised nose is placed there: it used to reach 0.6 m into the crossing as a 0.15 m lip)
            nose_y = 0.0
            mh = max(0.02, a["h"] if a["h"] > 0 else 0.15)
            base = end + a["D"] * nose_y
            ring = [base + r * (med * math.cos(math.pi * k / 8)) - a["D"] * (med * math.sin(math.pi * k / 8)) for k in range(9)]
            try:
                ff = bm.faces.new([V(q, z + mh) for q in ring]); ff.material_index = 2
            except ValueError: pass
            for k in range(8):
                try:
                    ff = bm.faces.new((V(ring[k], z), V(ring[k + 1], z), V(ring[k + 1], z + mh), V(ring[k], z + mh))); ff.material_index = 2
                except ValueError: pass
            if nose_y > 0.0:
                quad(end + r * med, end - r * med, base - r * med, base + r * med, z + 0.02, 5)
    # bicycle crossings: a coloured band through the junction joining the cycle lanes of opposite legs, bordered by
    # elephant-feet squares. It starts at the legs' trimmed ends, so it never lies on a zebra (the road's own cycle
    # paint stops at its clear zone); a band that would leave the junction's asphalt (offset legs) is not drawn.
    if box: _box_marking(bm, V, approaches, z)
    bike_bands = []
    if bike_crossings:
        for ai, a in enumerate(approaches):
            for bi, b in enumerate(approaches):
                if bi <= ai or a["d"].dot(b["d"]) > -BIKE_OPPOSITE: continue
                for s, sa, o, sb in (("r", 1.0, "l", -1.0), ("l", -1.0, "r", 1.0)):
                    if not (a.get("bike_on_" + s) and b.get("bike_on_" + o)): continue
                    a_in = a["E"] + a["R"] * (a["bike0_" + s] * sa); a_out = a["E"] + a["R"] * (a["bike1_" + s] * sa)
                    b_in = b["E"] + b["R"] * (b["bike0_" + o] * sb); b_out = b["E"] + b["R"] * (b["bike1_" + o] * sb)
                    probes = [p_.lerp(q_, t_) for p_, q_ in ((a_in, b_in), (a_out, b_out)) for t_ in (0.05, 0.5, 0.95)]
                    if not all(_inside(poly, q_) for q_ in probes): continue
                    quad(a_in, a_out, b_out, b_in, z + 0.003, 6)
                    for e0, e1, inward in ((a_in, b_in, (a_out - a_in)), (a_out, b_out, (a_in - a_out))):
                        u = (e1 - e0); length = u.length; u.normalize(); w_ = inward.normalized()
                        t_ = 0.2
                        while t_ + 0.4 <= length - 0.2:
                            p0 = e0 + u * t_ - w_ * 0.1
                            quad(p0, p0 + u * 0.4, p0 + u * 0.4 + w_ * 0.4, p0 + w_ * 0.4, z + Z_PAINT, 1)
                            t_ += 0.8
                    bike_bands.append({"from": [a["road"].name, s], "to": [b["road"].name, o]})
    params = {"crosswalks": crosswalks, "stop_lines": stop_lines, "corner_radius": corner_radius, "crossing": crossing, "stop_setback": stop_setback,
              "refuge": refuge, "control": control, "main_roads": sorted(main_roads), "bike_crossings": bike_crossings, "crossing_width": crossing_width,
              "edge_depth": edge_depth, "plane": list(plane) if plane else None, "z": z_given, "snap": snap, "box": box}
    meta = {"at": list(at), "roads": [a["road"].name for a in approaches], "crosswalks": crosswalks, "stop_lines": stop_lines, "corner_radius": corner_radius, "params": params,
            "traffic_lights": traffic_lights, "control": control, "main_roads": sorted(main_roads), "terrain": terrain.name if terrain else "", "z": z, "type": "junction",
            "crossing": crossing, "stop_setback": stop_setback, "refuge": refuge, "crossings": crossings_meta, "corner_paths": corner_paths, "plane": [gx, gy],
            "bike_bands": bike_bands, "crossing_width": cw,
            "approaches": [{"road": a["road"].name, "end": "start" if a["start"] else "end", "heading": [a["d"].x, a["d"].y], "trim": a["trim"],
                            "lanes_in": a["lanes_in"], "lanes_out": a["lanes_out"], "mark_clear": a["mark_clear"], "turns": a["turns"], "cross": bool(a["cross"]), "marking": a["marking"],
                            "end_point": [round(c, 4) for c in a["E"]], "right": [round(c, 5) for c in a["R"].normalized()], "out": [round(c, 5) for c in a["D"]],
                            "half_l": a["half_l"], "half_r": a["half_r"], "main": a["road"].name in main_roads} for a in approaches]}
    o = _mesh_object(name, bm, collection, _mats(), meta)
    if traffic_lights and n >= 3:
        _place_signals(name, o, at, z, approaches, corners, collection, dz)
    return o


def _place_signals(name, jobj, at, z, approaches, corners, collection, dz=None):
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
        if dz is not None: pos.z += dz(pos)
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
                             "position": list(pos), "heading": [d.x, d.y], "kind": "corner", "variant": ""})
    # multi-lane approaches: a mast arm at the stop line on the arriving side, one vehicle head over each arriving lane
    # (the arm length and head positions follow the approach's lane count, lane width and median)
    for ai, a in enumerate(approaches):
        n_in = int(round(a["lanes_in"]))
        if n_in < ARM_LANES or signage is None or "E" not in a: continue
        in_r = -1.0 if a["rht"] else 1.0
        half_in = a["half_l"] if in_r < 0 else a["half_r"]; sw_in = a["swl"] if in_r < 0 else a["swr"]
        if sw_in < ARM_POLE[1] + 0.3: continue                          # no sidewalk to stand on
        x_pole = half_in + a["curb"] + ARM_POLE[1]
        offs = [round(x_pole - (a["median"] * 0.5 + (k + 0.5) * a["lw"]), 2) for k in range(n_in)]
        arm = round(max(offs) + 0.7, 1)
        R = a["R"].normalized(); y = a.get("mark_clear", 0.0) + ARM_POLE[0]
        pos = a["E"] + a["D"] * y + R * (in_r * x_pole); pos = Vector((pos.x, pos.y, z + a["h"]))
        if dz is not None: pos.z += dz(pos)
        d = a["d"]; sid = "%s_A%d" % (name, ai)
        codes = lane_use(a.get("turns", 7), n_in, a["rht"])
        variant = "Arm%d_%.1f_%s_U%s" % (n_in, arm, "_".join("%.1f" % o_ for o_ in offs), "".join(str(c) for c in codes))
        sig = signage.make_signal(sid, style="mast_arm", pole_height=ARM_HEIGHT, arm_length=arm, heads=("vehicle",) * n_in, collection=collection,
                                  arm_side=in_r, head_x=offs)
        # a lane-use sign over every head: the movements its lane may make (the arrows painted in that lane)
        heads = [h for h in dict(sig["mrs_signal"]).get("heads", []) if dict(h).get("kind") == "vehicle"]
        for k, h in enumerate(heads[:n_in]):
            ho = bpy.data.objects.get(dict(h)["object"])
            if ho is None: continue
            hl = ho.location
            signage.lane_use_sign("%s_use%d" % (sid, k), codes[k], collection, parent=sig, at=(hl.x, hl.y, hl.z + 0.305 + 0.1 + signage.LANE_SIGN[1] * 0.5))
        sig.location = pos; sig.rotation_euler = (0, 0, math.atan2(d.y, d.x) + math.pi / 2)
        sig.parent = jobj; sig.matrix_parent_inverse = jobj.matrix_world.inverted()
        sig["mrs_signal_id"] = sid; sig["mrs_signal_variant"] = variant
        phase = next(k for k, p in enumerate(phases) if ai in p)
        signals_meta.append({"id": sid, "controls_road": a["road"].name, "approach": ai, "phase": phase, "pedestrian_crossing": None,
                             "position": list(pos), "heading": [d.x, d.y], "kind": "mast_arm", "variant": variant, "lanes": n_in, "lane_use": codes})
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
    _set_end(a, trim, trim + 4.0, z, turns=0)
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
        bike_arm = cross and bike_crossings and (a.get("bike_on_l") or a.get("bike_on_r"))
        a["mark_clear"] = (crossing_setback + cw + (2.6 if bike_arm else STOP_LINE[0])) if cross else 0.0
        a["turns"] = 7          # every exit is reached round the ring
        _set_end(a, trim, trim + crossing_setback + cw + (2.5 if any_bike else 0.0) + 5.0, z, ramp=cross, mark_clear=a["mark_clear"], turns=a["turns"])
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
    params = dict(meta.get("params") or {})
    if params:
        params = {k: (v.to_list() if hasattr(v, "to_list") else (list(v) if isinstance(v, tuple) else v)) for k, v in params.items()}
        params["snap"] = max(float(params.get("snap") or 0.8), 6.0)        # the ends may have moved since
        return build_junction(obj.name, at, roads, col, terrain=terrain, **params)
    return build_junction(obj.name, at, roads, col, meta.get("crosswalks", True), meta.get("stop_lines", True), meta.get("corner_radius", 6.0),
                          meta.get("traffic_lights", False), snap=6.0, terrain=terrain, crossing=meta.get("crossing", "zebra"), stop_setback=meta.get("stop_setback", 0.6),
                          refuge=meta.get("refuge", True), control=meta.get("control"), main_roads=list(meta.get("main_roads", [])))


def configure(obj, **changes):
    """Change any of a junction's build parameters (build_junction keywords: control, crossing, crosswalks, stop_lines,
    corner_radius, crossing_width, stop_setback, bike_crossings, refuge, box ...) and rebuild it from its roads."""
    meta = obj["mrs_junction"]; meta = meta.to_dict() if hasattr(meta, "to_dict") else dict(meta)
    params = dict(meta.get("params") or {}); params.update(changes); meta["params"] = params
    obj["mrs_junction"] = meta
    return rebuild(obj)


def all_junctions():
    return [o for o in bpy.data.objects if o.get("mrs_junction") and o.type == "MESH"]


def rebuild_all():
    out = []
    for o in list(all_junctions()):
        try: out.append(rebuild(o))
        except Exception as e: print("junction rebuild failed", o.name, e)
    return out


_curve_hashes = {}
# road inputs a junction (or the driveway step) writes: changes to them never trigger a rebuild (no feedback loop)
DERIVED = {k + " " + e for k in ("Trim", "Clear", "Lock", "Ramp", "Bank", "Mark Clear", "Turns") for e in ("Start", "End")} \
    | {"Lock Start Z", "Lock End Z", "Ramp Offset", "Ramp Width", "Driveways"}
_pending = {"junctions": set(), "collections": set()}
AUTO_DELAY = 0.3           # s: edits within this time are rebuilt together


def _road_state(o):
    """Everything about a road a junction or the street assets depend on: its curve, its placement and every input
    except the derived ones (lanes, widths, cycle lanes, sidewalks, median, kerbs, speed, driving side ...)."""
    sp = o.data.splines[0] if o.data.splines else None
    pts = () if sp is None else tuple(round(c, 3) for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)
                                      for c in (p.co[:3] if sp.type != "BEZIER" else (*p.co, *p.handle_left, *p.handle_right)))
    vals = []
    mod = o.modifiers.get("MRS_Road")
    if mod is not None and mod.node_group is not None:
        props = getattr(mod, "properties", None); inputs = getattr(props, "inputs", None) if props is not None else None
        for it in mod.node_group.interface.items_tree:
            if getattr(it, "in_out", "") != "INPUT" or getattr(it, "item_type", "SOCKET") != "SOCKET" or it.name in DERIVED or it.name == "Geometry": continue
            entry = getattr(inputs, it.identifier, None) if inputs is not None else None      # read by item: no name search per input
            v = entry.value if entry is not None else mod.get(it.identifier, getattr(it, "default_value", None))
            v = getattr(v, "name", v)
            vals.append((it.name, round(v, 5) if isinstance(v, float) else (tuple(v) if hasattr(v, "__len__") and not isinstance(v, str) else v)))
    return hash((pts, tuple(round(c, 3) for c in o.matrix_world.translation), tuple(vals)))


def _curve_hash(o):
    return _road_state(o)


def _flush():
    """Rebuild the junctions whose roads changed, then (scene option) re-place the street assets of their collections."""
    js, cols = set(_pending["junctions"]), set(_pending["collections"])
    _pending["junctions"].clear(); _pending["collections"].clear()
    for jn in sorted(js):
        if jn in bpy.data.objects:
            try: rebuild(bpy.data.objects[jn])
            except Exception as e: print("auto junction", jn, e)
    sc = bpy.context.scene
    if sc is not None and sc.get("mrs_auto_place"):
        from . import placement
        for cn in sorted(cols):
            c = bpy.data.collections.get(cn)
            if c is None or bpy.data.collections.get(cn + "_Placed") is None: continue
            try: placement.place_all(c, seed=int(sc.get("mrs_place_seed", 0)))
            except Exception as e: print("auto placement", cn, e)
    return None


def _on_depsgraph(scene, depsgraph):
    changed = set()
    for u in depsgraph.updates:
        ob = u.id
        if isinstance(ob, bpy.types.Object) and ob.type == "CURVE" and "MRS_Road" in ob.modifiers:
            ob = ob.original if hasattr(ob, "original") else ob
            hsh = _road_state(ob)
            if _curve_hashes.get(ob.name) != hsh:
                _curve_hashes[ob.name] = hsh; changed.add(ob.name)
                for c in ob.users_collection: _pending["collections"].add(c.name)
    if not changed: return
    for j in all_junctions():
        if changed & set(j["mrs_junction"]["roads"]): _pending["junctions"].add(j.name)
    try:
        if bpy.app.timers.is_registered(_flush): bpy.app.timers.unregister(_flush)
        bpy.app.timers.register(_flush, first_interval=AUTO_DELAY)
    except Exception as e: print("auto update", e)


def enable_auto_update(on=True):
    h = bpy.app.handlers.depsgraph_update_post
    while _on_depsgraph in h: h.remove(_on_depsgraph)
    if on:
        for r in all_roads(): _curve_hashes[r.name] = _curve_hash(r)
        h.append(_on_depsgraph)
