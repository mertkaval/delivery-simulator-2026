"""Structures placed along roads by Python: overhead gantry signs, cable-stayed bridge pylons and
stays, tunnel portals, bus stops, custom text signs. They are plain objects parented to nothing,
positioned with the road's evaluated centre line (so they follow the terrain-conformed height)."""
import bpy, bmesh, math
from mathutils import Vector
from .nodes import depsgraph, set_scene, MRS
from .roads import road_widths


def road_sample(road, along):
    """World position, unit tangent and right vector of the evaluated road centre line at `along`
    metres from its (trimmed) start."""
    dg = depsgraph()
    me = road.evaluated_get(dg).to_mesh()
    lat = me.attributes["lat"].data; al = me.attributes["along"].data
    seen = {}
    for i in range(len(me.vertices)):
        if abs(lat[i].value) < 0.3:
            key = round(al[i].value, 2)
            if key not in seen: seen[key] = me.vertices[i].co.copy()       # one sample per station (strips share 'along')
    pts = sorted(seen.items())
    road.evaluated_get(dg).to_mesh_clear()
    if len(pts) < 2: raise ValueError("road %s has no centre line" % road.name)
    along = max(pts[0][0], min(pts[-1][0], along))
    i = next((k for k in range(1, len(pts)) if pts[k][0] >= along), len(pts) - 1)
    a0, p0 = pts[i - 1]; a1, p1 = pts[i]
    f = 0.0 if a1 == a0 else (along - a0) / (a1 - a0)
    p = road.matrix_world @ (p0.lerp(p1, f)); t = (road.matrix_world @ p1 - road.matrix_world @ p0); t.z = 0; t.normalize()
    return p, t, t.cross(Vector((0, 0, 1))).normalized()


def road_length(road):
    dg = depsgraph()
    me = road.evaluated_get(dg).to_mesh()
    al = me.attributes["along"].data; L = max(al[i].value for i in range(len(me.vertices))) if len(me.vertices) else 0.0
    road.evaluated_get(dg).to_mesh_clear(); return L


def _obj(name, me, collection, pos, yaw):
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me); collection.objects.link(o)
    o.location = pos; o.rotation_euler = (0, 0, yaw)
    return o


def _text_mesh(text, size, depth=0.004, align="CENTER"):
    cu = bpy.data.curves.new("mrs_txt", "FONT"); cu.body = text; cu.size = size; cu.extrude = depth; cu.align_x = align; cu.align_y = "CENTER"
    cu.resolution_u = 4
    tmp = bpy.data.objects.new("mrs_txt", cu)
    dg = depsgraph()
    bpy.context.scene.collection.objects.link(tmp); dg = depsgraph()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp); bpy.data.curves.remove(cu)
    return me


def gantry_sign(road, along, texts=("EXIT 12", "CITY CENTRE"), collection=None, height=5.6, name=None):
    """Overhead gantry spanning the road at `along`: two posts outside the sidewalks, a truss beam,
    one green sign plate per text (one per lane group) with white legends."""
    w = road_widths(road)
    p, t, r = road_sample(road, along)
    span = w["half_l"] + w["half_r"] + 2 * w["curb"] + w["swl"] + w["swr"] + 1.6
    bm = bmesh.new()
    from .props import _box, _cyl
    for sgn in (-1, 1):
        _cyl(bm, sgn * span / 2, 0, 0, height + 1.2, 0.22, 0.2, 12)
        _box(bm, sgn * span / 2 - 0.5, -0.5, 0, sgn * span / 2 + 0.5, 0.5, 0.08)
    _box(bm, -span / 2, -0.35, height, span / 2, 0.35, height + 0.7)
    for k in range(int(span / 1.5)):
        x = -span / 2 + 0.75 + k * 1.5
        _box(bm, x - 0.05, -0.3, height + 0.05, x + 0.05, 0.3, height + 0.65)
    me = bpy.data.meshes.new("MRS_Gantry"); bm.to_mesh(me); bm.free()
    from .props import mat
    me.materials.append(mat(MRS + "PropMetal", (0.2, 0.21, 0.22), 0.45, 0.8))
    name = name or "%s_gantry_%d" % (road.name, int(along))
    yaw = math.atan2(t.y, t.x) - math.pi / 2       # local +Y = road direction
    g = _obj(name, me, collection or road.users_collection[0], p, yaw)
    # plates: distributed over the carriageway width, facing the oncoming (backward) traffic (-Y local) and forward traffic
    n = len(texts); width = (w["half_l"] + w["half_r"]) / max(1, n) - 0.4
    green = mat(MRS + "PropSignGreen", (0.02, 0.22, 0.09), 0.5); white = mat(MRS + "PropSignWhite", (0.95, 0.95, 0.95), 0.4)
    for i, txt in enumerate(texts):
        xc = -w["half_l"] + (i + 0.5) * (w["half_l"] + w["half_r"]) / max(1, n)
        bm = bmesh.new(); _box(bm, -width / 2, -0.06, 0.0, width / 2, 0.06, 1.6); pm = bpy.data.meshes.new("MRS_GantryPlate"); bm.to_mesh(pm); bm.free(); pm.materials.append(green)
        plate = bpy.data.objects.new(name + "_plate%d" % i, pm); (collection or road.users_collection[0]).objects.link(plate); plate.parent = g
        plate.location = (xc, 0, height + 0.75); plate.rotation_euler = (0, 0, 0)
        tm = _text_mesh(txt, min(0.5, width / (0.65 * max(1, len(txt)))), 0.01); tm.materials.append(white)
        to = bpy.data.objects.new(name + "_text%d" % i, tm); (collection or road.users_collection[0]).objects.link(to); to.parent = plate
        to.location = (0, -0.07, 0.8); to.rotation_euler = (math.pi / 2, 0, 0)     # readable from -Y (traffic driving toward +Y looks at the back? no: drivers heading +Y see the plate's -Y face)
    return g


def text_sign(text, pos, yaw=0.0, collection=None, shape="rect", color=(0.02, 0.22, 0.09), size=0.9, name=None, height=2.3):
    """A free-standing sign post with a plate carrying `text` (used by the UI 'Custom Sign' button)."""
    from .props import _box, _cyl, mat
    bm = bmesh.new(); _cyl(bm, 0, 0, 0, height, 0.04, 0.04, 8)
    me = bpy.data.meshes.new("MRS_TextSignPost"); bm.to_mesh(me); bm.free(); me.materials.append(mat(MRS + "PropMetal", (0.2, 0.21, 0.22), 0.45, 0.8))
    name = name or "MRS_Sign_" + text.replace(" ", "_")[:16]
    post = _obj(name, me, collection or bpy.context.scene.collection, pos, yaw)
    bm = bmesh.new()
    if shape == "circle": _cyl(bm, 0, 0, -0.03, 0.03, size / 2, size / 2, 28)
    else: _box(bm, -size * 0.75, -0.03, -size * 0.3, size * 0.75, 0.03, size * 0.3)
    pm = bpy.data.meshes.new("MRS_TextSignPlate"); bm.to_mesh(pm); bm.free(); pm.materials.append(mat(MRS + "PropSign_%02x%02x%02x" % tuple(int(c * 255) for c in color), color, 0.45))
    plate = bpy.data.objects.new(name + "_plate", pm); (collection or bpy.context.scene.collection).objects.link(plate); plate.parent = post
    plate.location = (0, 0, height - size * 0.35)
    if shape == "circle": plate.rotation_euler = (math.pi / 2, 0, 0)
    tm = _text_mesh(text, size * 0.22 if len(text) > 6 else size * 0.35, 0.006); tm.materials.append(mat(MRS + "PropSignWhite", (0.95, 0.95, 0.95), 0.4))
    to = bpy.data.objects.new(name + "_text", tm); (collection or bpy.context.scene.collection).objects.link(to); to.parent = plate
    to.location = (0, -0.035, 0); to.rotation_euler = (math.pi / 2, 0, 0)
    return post


def cable_stays(road, collection=None, pylon_spacing=90.0, pylon_height=28.0, stays=7, name=None):
    """Cable-stayed bridge dressing for an Elevated road: A-shaped pylons through the deck every
    `pylon_spacing` metres with fan stays to both sides of the deck. The road keeps its own deck and pillars."""
    from .props import _box, _cyl, mat
    w = road_widths(road)
    L = road_length(road)
    n = max(1, int(L / pylon_spacing))
    out = []
    concrete = mat(MRS + "PropConcrete", (0.55, 0.55, 0.53), 0.85); steel = mat(MRS + "PropCable", (0.8, 0.8, 0.82), 0.3, 0.9)
    for k in range(n):
        along = (k + 0.5) * L / n
        p, t, r = road_sample(road, along)
        half = w["half_l"] + w["half_r"]
        bm = bmesh.new()
        for sgn in (-1, 1):
            x0 = sgn * (half / 2 + 1.2)
            # leg from below the deck (-14 m) to the top, leaning inwards
            v = [bm.verts.new(c) for c in ((x0 - 0.8, -0.8, -14), (x0 + 0.8, -0.8, -14), (x0 + 0.8, 0.8, -14), (x0 - 0.8, 0.8, -14),
                                          (x0 * 0.35 - 0.6, -0.6, pylon_height), (x0 * 0.35 + 0.6, -0.6, pylon_height), (x0 * 0.35 + 0.6, 0.6, pylon_height), (x0 * 0.35 - 0.6, 0.6, pylon_height))]
            for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)): bm.faces.new([v[i] for i in f])
        _box(bm, -half / 2 - 0.4, -0.6, pylon_height - 1.0, half / 2 + 0.4, 0.6, pylon_height + 0.2)      # cross beam at the top
        _box(bm, -half / 2 - 0.4, -0.6, -1.6, half / 2 + 0.4, 0.6, -0.2)                                      # beam under the deck
        pm = bpy.data.meshes.new("MRS_Pylon"); bm.to_mesh(pm); bm.free(); pm.materials.append(concrete)
        yaw = math.atan2(t.y, t.x) - math.pi / 2
        nm = (name or road.name + "_pylon") + "_%d" % k
        py = _obj(nm, pm, collection or road.users_collection[0], p + Vector((0, 0, -0.0)), yaw)
        # stays: from the pylon top to deck anchor points on both sides, both directions
        bm = bmesh.new()
        for sgn_dir in (-1, 1):
            for j in range(1, stays + 1):
                dist = sgn_dir * j * (pylon_spacing * 0.42 / stays)
                for sgn_x in (-1, 1):
                    xa = sgn_x * (half / 2 + 0.3)
                    top = Vector((sgn_x * (half / 2 + 1.2) * 0.35, 0, pylon_height - 0.6 - j * 0.35))
                    anchor = Vector((xa, dist, 0.6))
                    d = anchor - top; n_ = d.length; d.normalize()
                    # a thin tube between top and anchor (8-gon)
                    axis = d; a = axis.orthogonal().normalized(); b = axis.cross(a)
                    ring0 = [bm.verts.new(top + (a * math.cos(2 * math.pi * q / 6) + b * math.sin(2 * math.pi * q / 6)) * 0.06) for q in range(6)]
                    ring1 = [bm.verts.new(anchor + (a * math.cos(2 * math.pi * q / 6) + b * math.sin(2 * math.pi * q / 6)) * 0.06) for q in range(6)]
                    for q in range(6): bm.faces.new((ring0[q], ring0[(q + 1) % 6], ring1[(q + 1) % 6], ring1[q]))
        sm = bpy.data.meshes.new("MRS_Stays"); bm.to_mesh(sm); bm.free(); sm.materials.append(steel)
        st = bpy.data.objects.new(nm + "_stays", sm); (collection or road.users_collection[0]).objects.link(st); st.parent = py
        out.append(py)
    return out


def tunnel(road, along_start, along_end, collection=None, name=None):
    """Tunnel lining (horseshoe arch) between two distances along a road, with portals at both ends."""
    from .props import mat
    w = road_widths(road)
    half = w["half_l"] + w["half_r"] + 2 * w["curb"] + w["swl"] + w["swr"]
    R = half / 2 + 1.0; wall_h = 2.5
    bm = bmesh.new()
    rings = []
    n_along = max(2, int((along_end - along_start) / 2.0) + 1)
    for k in range(n_along):
        along = along_start + (along_end - along_start) * k / (n_along - 1)
        p, t, r = road_sample(road, along)
        ring = []
        for q in range(17):
            a = math.pi * q / 16
            x = R * math.cos(a); zz = wall_h + R * 0.85 * math.sin(a)
            ring.append(bm.verts.new(p + r * x + Vector((0, 0, zz))))
        ring = [bm.verts.new(p + r * R + Vector((0, 0, 0)))] + ring + [bm.verts.new(p - r * R + Vector((0, 0, 0)))]
        rings.append(ring)
    for k in range(n_along - 1):
        for q in range(len(rings[k]) - 1):
            bm.faces.new((rings[k][q], rings[k + 1][q], rings[k + 1][q + 1], rings[k][q + 1]))
    # portals: a flat frame (2.5 m) around the arch in the portal plane, at both ends
    for k, along in ((0, along_start), (n_along - 1, along_end)):
        ring = rings[k]
        p, t, r = road_sample(road, along)
        outer = []
        for v in ring:
            c = v.co.copy(); d = c - p
            lat_ = d.dot(r); zz = d.z
            s_ = 1.0 + 2.5 / max(R, 0.1)
            outer.append(bm.verts.new(p + r * lat_ * s_ + Vector((0, 0, max(0.0, zz) * (1.0 + 2.5 / (wall_h + R * 0.85)) if zz > 0.3 else zz))))
        for q in range(len(ring) - 1):
            try: bm.faces.new((ring[q], ring[q + 1], outer[q + 1], outer[q]))
            except ValueError: pass
    me = bpy.data.meshes.new("MRS_Tunnel"); bm.to_mesh(me); bm.free()
    me.materials.append(mat(MRS + "PropConcrete", (0.55, 0.55, 0.53), 0.85))
    for p_ in me.polygons: p_.use_smooth = True
    name = name or road.name + "_tunnel"
    return _obj(name, me, collection or road.users_collection[0], (0, 0, 0), 0.0)


def bus_stop(road, along, side=1, collection=None, name=None):
    """Bus bay marking ('BUS STOP' text on the lane) and a shelter on the sidewalk at `along`."""
    from .props import _box, mat
    w = road_widths(road)
    p, t, r = road_sample(road, along)
    sgn = 1 if side > 0 else -1
    half = w["half_r"] if sgn > 0 else w["half_l"]
    yaw = math.atan2(t.y, t.x) - math.pi / 2
    tm = _text_mesh("BUS STOP", 1.1, 0.002); tm.materials.append(bpy.data.materials[MRS + "Paint"])
    name = name or "%s_busstop_%d" % (road.name, int(along))
    txt = _obj(name + "_text", tm, collection or road.users_collection[0], p + r * sgn * (half - 1.7) + Vector((0, 0, 0.006)), yaw + (math.pi / 2 if sgn > 0 else -math.pi / 2))
    txt.scale = (1, 1, 1)
    # shelter: roof on two posts + back glass, on the sidewalk facing the road
    bm = bmesh.new()
    _box(bm, -2.0, 0.9, 0.0, 2.0, 1.1, 2.4); _box(bm, -2.2, -0.5, 2.4, 2.2, 1.3, 2.55)
    for x in (-1.9, 1.9): _box(bm, x - 0.05, -0.4, 0, x + 0.05, -0.3, 2.4)
    _box(bm, -1.6, 0.6, 0.45, 1.6, 0.95, 0.5)
    sm = bpy.data.meshes.new("MRS_BusShelter"); bm.to_mesh(sm); bm.free()
    sm.materials.append(mat(MRS + "PropGlass", (0.6, 0.7, 0.75), 0.1))
    sw_off = half + w["curb"] + 1.4
    shelter = _obj(name, sm, collection or road.users_collection[0], p + r * sgn * sw_off + Vector((0, 0, w["h"])), yaw + (0 if sgn > 0 else math.pi))
    return shelter
