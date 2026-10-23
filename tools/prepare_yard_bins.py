"""Lane carts for the residential lots -> assets/sketchup/props/street/cart_trio.glb.

Replace the kit's primitive `bins_trio` (three coloured boxes) behind every house: a black garbage
cart, a blue recycling cart and a green organics cart, as on Vancouver lanes. Modelled here rather
than reusing the street pack's wheelie bins, whose rims are built from layered shells a millimetre
apart that z-fight (tests/house_conflict_test.gd fails on them):
  * tapered body with rounded corners, a chamfered foot and a rolled top lip,
  * a slightly domed lid that overhangs the lip by 1-2 cm all round (never touching it), with a
    front grip and a hinge bar at the back,
  * back handle bar on two brackets, an axle with two 0.2 m wheels and hubs, a front foot,
  * HDPE plastic with a grime / scuff texture (dirt at the foot, rougher where dirty).

  blender --background --factory-startup --python tools/prepare_yard_bins.py
Origin at the footprint centre on the ground, front (lid grip) towards Blender -Y = Godot +Z,
metres: each cart about 0.62 x 0.76 x 1.08 m (240 l), the trio 2.06 m wide (0.72 m apart), one
shared plastic atlas (three colour strips), rubber and steel: 3 surfaces for the whole trio.
QA renders: assets/landscape/qa/yard_carts*.png.
"""
import bpy, bmesh, os, math
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "sketchup", "props", "street", "cart_%s.glb")
QA = os.path.join(ROOT, "assets", "landscape", "qa", "yard_carts.png")
TMP = os.path.join(ROOT, "tmp", "yard_carts")
os.makedirs(TMP, exist_ok=True)
COLOURS = {"black": (0.035, 0.037, 0.04), "blue": (0.04, 0.15, 0.42), "green": (0.06, 0.24, 0.09)}
SEEDS = {"black": 21, "blue": 22, "green": 23}


def image(name, px, noncolor=False):
    h, w = px.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.ascontiguousarray(px, np.float32).ravel())
    img.filepath_raw = os.path.join(TMP, name + ".png")
    img.file_format = "PNG"
    img.save()
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def smooth_noise(r, s, cells):
    """Bilinearly upsampled cells x cells normal noise (s x s): soft blotches, no blocky squares."""
    g = r.normal(0, 1, (cells + 1, cells + 1))
    t = np.linspace(0, cells, s)
    i = np.minimum(t.astype(int), cells - 1)
    f = t - i
    rows = g[i] * (1 - f)[:, None] + g[i + 1] * f[:, None]
    return rows[:, i] * (1 - f)[None, :] + rows[:, i + 1] * f[None, :]


def plastic_px(rgb, seed):
    """HDPE: albedo with dirt at the foot and faint scuffs; roughness higher where dirty."""
    r = np.random.default_rng(seed)
    s = 256
    coarse = smooth_noise(r, s, 12)
    fine = r.normal(0, 1, (s, s))
    v = np.linspace(0, 1, s)[:, None]
    dirt = np.clip(1.0 - v * 4.0, 0, 1) * (0.5 + 0.2 * coarse)
    scuff = np.clip(coarse * 0.5 - 0.6, 0, 1)
    alb = np.ones((s, s, 4), np.float32)
    base = np.array(rgb, np.float32)
    for c in range(3):
        alb[..., c] = np.clip(base[c] * (1 + 0.05 * fine + 0.06 * coarse) * (1 - dirt * 0.5) + dirt * 0.07 + scuff * 0.05, 0, 1)
    rough = np.ones((s, s, 4), np.float32)
    rr = np.clip(0.48 + 0.04 * fine + 0.25 * dirt + 0.2 * scuff, 0, 1)
    for c in range(3):
        rough[..., c] = rr
    return alb, rough


def plastic(name, alb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = image(name + "_albedo", alb)
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeTexImage"); tr.image = image(name + "_rough", rough, True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tr.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    return m


def flat(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def rrect(hx, hy, rad, per_corner=4):
    """Rounded rectangle outline (counter-clockwise from +x), corner radius `rad`."""
    pts = []
    for k, (cx, cy) in enumerate(((hx - rad, hy - rad), (-hx + rad, hy - rad), (-hx + rad, -hy + rad), (hx - rad, -hy + rad))):
        a0 = k * math.pi / 2
        for i in range(per_corner + 1):
            a = a0 + (math.pi / 2) * i / per_corner
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


def loft(bm, rings, cap_bottom=False, cap_top=False):
    """rings: list of (outline points, z). Quads between consecutive rings, optional caps."""
    vr = [[bm.verts.new((x, y, z)) for (x, y) in pts] for (pts, z) in rings]
    faces = []
    n = len(vr[0])
    for i in range(len(vr) - 1):
        for k in range(n):
            faces.append(bm.faces.new((vr[i][k], vr[i][(k + 1) % n], vr[i + 1][(k + 1) % n], vr[i + 1][k])))
    if cap_bottom:
        faces.append(bm.faces.new(list(reversed(vr[0]))))
    if cap_top:
        faces.append(bm.faces.new(vr[-1]))
    return faces


def cylinder_x(bm, x0, x1, y, z, r, seg=16):
    a = [bm.verts.new((x0, y + r * math.cos(math.tau * k / seg), z + r * math.sin(math.tau * k / seg))) for k in range(seg)]
    b = [bm.verts.new((x1, y + r * math.cos(math.tau * k / seg), z + r * math.sin(math.tau * k / seg))) for k in range(seg)]
    faces = [bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k])) for k in range(seg)]
    faces.append(bm.faces.new(list(reversed(a))))
    faces.append(bm.faces.new(b))
    return faces


def box(bm, c, s):
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    v = [bm.verts.new((c[0] + x, c[1] + y, c[2] + z)) for z in (-hz, hz) for y in (-hy, hy) for x in (-hx, hx)]
    return [bm.faces.new([v[i] for i in q]) for q in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]]


def build(colour, k, body_m, rubber, steel):
    """One cart; its plastic UVs go to strip k of the shared three-colour plastic atlas."""
    bm = bmesh.new()
    mat = {}
    # Body: tapered rounded box, chamfered foot, rolled lip; the open top is capped below the lid.
    hx0, hy0, hx1, hy1 = 0.235, 0.27, 0.27, 0.315

    def ring(t, grow=0.0):
        return rrect(hx0 + (hx1 - hx0) * t + grow, hy0 + (hy1 - hy0) * t + grow, 0.06 + grow * 0.5)
    rings = [(ring(0.0, -0.02), 0.0), (ring(0.0), 0.03), (ring(1.0), 0.95), (ring(1.0, 0.012), 0.957),
             (ring(1.0, 0.016), 0.975), (ring(1.0, 0.004), 0.982), (ring(1.0, -0.012), 0.975)]
    for f in loft(bm, rings, cap_bottom=True, cap_top=True):
        mat[f] = 0
    # Lid: skirt outside the lip, domed top (closed shell: skirt, top, flat underside).
    lid = [(rrect(hx1 + 0.03, hy1 + 0.03, 0.08), 0.99), (rrect(hx1 + 0.03, hy1 + 0.03, 0.08), 1.03),
           (rrect(hx1 + 0.015, hy1 + 0.015, 0.07), 1.045), (rrect(hx1 - 0.04, hy1 - 0.04, 0.06), 1.065),
           (rrect(hx1 - 0.12, hy1 - 0.12, 0.05), 1.075)]
    for f in loft(bm, lid, cap_bottom=True, cap_top=True):
        mat[f] = 0
    for f in box(bm, (0, -(hy1 + 0.05), 1.01), (0.22, 0.03, 0.035)):
        mat[f] = 0
    # Back: hinge bar, handle bar on brackets.
    for f in cylinder_x(bm, -0.22, 0.22, hy1 + 0.052, 1.005, 0.016):
        mat[f] = 0
    for sx in (-0.18, 0.18):
        for f in box(bm, (sx, hy1 + 0.035, 0.9), (0.04, 0.06, 0.07)):
            mat[f] = 0
    for f in cylinder_x(bm, -0.21, 0.21, hy1 + 0.08, 0.9, 0.017):
        mat[f] = 0
    # Axle, wheels with hubs, front foot.
    # The axle runs clear of the body wall and ends inside the wheels; the hubs start inside the
    # tyres and stand 2.5 cm proud of them (no two faces within the audit's 1.5 cm).
    wy, wz, wr = hy0 + 0.035, 0.1, 0.1
    for f in cylinder_x(bm, -0.29, 0.29, wy, wz, 0.013, 10):
        mat[f] = 2
    for sx in (-1, 1):
        for f in cylinder_x(bm, min(sx * 0.255, sx * 0.305), max(sx * 0.255, sx * 0.305), wy, wz, wr, 20):
            mat[f] = 1
        for f in cylinder_x(bm, min(sx * 0.295, sx * 0.33), max(sx * 0.295, sx * 0.33), wy, wz, 0.045, 12):
            mat[f] = 0
    for f in box(bm, (0, -(hy0 - 0.02), 0.025), (0.3, 0.05, 0.05)):
        mat[f] = 0
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f, mi in mat.items():
        if f.is_valid:
            f.material_index = mi
    me = bpy.data.meshes.new("cart_" + colour)
    bm.to_mesh(me)
    bm.free()
    for m in (body_m, rubber, steel):
        me.materials.append(m)
    o = bpy.data.objects.new("cart_" + colour, me)
    bpy.context.scene.collection.objects.link(o)
    uvl = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = ((k + 0.02 + 0.96 * ((math.atan2(co.y, co.x) / math.tau) % 1.0)) / 3.0, min(1.0, co.z / 1.1))
        p.use_smooth = True
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    except Exception:
        pass
    o.select_set(False)
    return o


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    strips = [plastic_px(COLOURS[c], SEEDS[c]) for c in COLOURS]
    body_m = plastic("cart_plastic", np.concatenate([a for a, _ in strips], axis=1), np.concatenate([r for _, r in strips], axis=1))
    # The three carts as one asset (garbage, recycling, organics), 0.72 m apart, each a little turned:
    # one MultiMesh per material for the whole trio.
    rubber = flat("cart_rubber", (0.025, 0.025, 0.027), 0.9)
    steel = flat("cart_steel", (0.55, 0.56, 0.58), 0.35, 0.9)
    carts = []
    for k, colour in enumerate(COLOURS):
        o = build(colour, k, body_m, rubber, steel)
        o.rotation_euler.z = (-0.05, 0.0, 0.06)[k]
        o.location.x = (k - 1) * 0.72
        carts.append(o)
    for o in carts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = carts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    trio = bpy.context.view_layer.objects.active
    trio.name = trio.data.name = "cart_trio"
    for x in bpy.data.objects:
        x.select_set(x == trio)
    path = OUT % "trio"
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                              export_animations=False, export_image_format="AUTO")
    tri = sum(len(p.vertices) - 2 for p in trio.data.polygons)
    print("[bins] wrote %s %d tris, %d materials, %.2f MB" % (trio.name, tri, len(trio.data.materials), os.path.getsize(path) / 1e6))
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1000, 700
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    gm = bpy.data.meshes.new("g"); gm.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("ground", gm); sc.collection.objects.link(g); gm.materials.append(flat("ground", (0.4, 0.38, 0.35), 0.9))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    for tag, loc in (("", (1.2, -3.2, 1.6)), ("_back", (-1.4, 2.8, 1.5))):
        cam.location = loc
        cam.rotation_euler = (Vector((0, 0, 0.55)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = QA.replace(".png", tag + ".png")
        bpy.ops.render.render(write_still=True)


main()
