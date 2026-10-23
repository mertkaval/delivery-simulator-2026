"""Slatted steel street litter bins -> assets/sketchup/props/street/litter_bin_slat_<colour>.glb.

Replace the perforated-cylinder litter bins of the PBR street pack (a textured tube with a flat
cap) on the sidewalks, park entrances, corridor restaurants and downtown: a bevelled base plinth,
24 powder-coated flat-bar slats on three hoops, a galvanised liner visible between the slats with
a black bin bag folded over its lip, and a domed rain bonnet on three stays (the opening for
rubbish runs all the way round under it). Powder coat and bag have roughness / grime variation in
small textures (dirt collects at the foot, the bonnet is a little worn).

  blender --background --factory-startup --python tools/prepare_litter_bins.py
Origin at the footprint centre on the ground, front +Y (Godot +Z after export), metres.
0.62 m across the bonnet, 1.0 m tall (StreetFurniture keeps its 0.6 x 0.9 x 0.6 kerbside box).
QA render: assets/landscape/qa/litter_bins.png.
"""
import bpy, bmesh, os, math
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "sketchup", "props", "street")
QA = os.path.join(ROOT, "assets", "landscape", "qa", "litter_bins.png")
TMP = os.path.join(ROOT, "tmp", "litter_bins")
os.makedirs(TMP, exist_ok=True)
COLOURS = {"green": (0.06, 0.2, 0.12), "black": (0.035, 0.037, 0.04), "red": (0.42, 0.06, 0.05)}


def image(name, px):
    h, w = px.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.ascontiguousarray(px, np.float32).ravel())
    img.filepath_raw = os.path.join(TMP, name + ".png")
    img.file_format = "PNG"
    img.save()
    return img


def smooth_noise(r, s, cells):
    """Bilinearly upsampled cells x cells normal noise (s x s): soft blotches, no blocky squares."""
    g = r.normal(0, 1, (cells + 1, cells + 1))
    t = np.linspace(0, cells, s)
    i = np.minimum(t.astype(int), cells - 1)
    f = t - i
    rows = g[i] * (1 - f)[:, None] + g[i + 1] * f[:, None]
    return rows[:, i] * (1 - f)[None, :] + rows[:, i + 1] * f[None, :]


def noise_px(size, seed, scale=8):
    r = np.random.default_rng(seed)
    return smooth_noise(r, size, size // (scale * 2)) * 0.6 + r.normal(0, 0.35, (size, size))


def coat_material(name, rgb, seed):
    """Powder coat: albedo with grime towards the foot (UV v = height), roughness texture."""
    s = 256
    n = noise_px(s, seed)
    v = np.linspace(0, 1, s)[:, None]                     # image rows from the bottom = UV v
    grime = np.clip(1.0 - v * 3.0, 0, 1) * 0.45            # dirt splash up to a third of the height
    alb = np.ones((s, s, 4), np.float32)
    base = np.array(rgb, np.float32)
    for c in range(3):
        alb[..., c] = np.clip(base[c] * (1.0 + 0.06 * n) * (1.0 - grime) + grime * 0.11 * (0.9 + 0.1 * n), 0, 1)
    rough = np.ones((s, s, 4), np.float32)
    rr = np.clip(0.42 + 0.06 * n + grime * 0.4, 0, 1)
    for c in range(3):
        rough[..., c] = rr
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = image(name + "_albedo", alb)
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeTexImage"); tr.image = image(name + "_rough", rough); tr.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tr.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = 0.25
    return m


def flat_material(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def lathe(bm, prof, seg, cap_top=False, uv_v=None):
    rings = []
    for (r, z) in prof:
        rings.append([bm.verts.new((r * math.cos(math.tau * s / seg), r * math.sin(math.tau * s / seg), z)) for s in range(seg)])
    faces = []
    for i in range(len(rings) - 1):
        for s in range(seg):
            faces.append(bm.faces.new((rings[i][s], rings[i][(s + 1) % seg], rings[i + 1][(s + 1) % seg], rings[i + 1][s])))
    if cap_top:
        faces.append(bm.faces.new(rings[-1]))
    return faces


def box(bm, c, size, rot):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    cs, sn = math.cos(rot), math.sin(rot)
    pts = []
    for z in (-hz, hz):
        for y in (-hy, hy):
            for x in (-hx, hx):
                pts.append((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, c[2] + z))
    v = [bm.verts.new(p) for p in pts]
    out = []
    for q in [(4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
        out.append(bm.faces.new([v[i] for i in q]))
    return out


def to_obj(name, bm, mats_of_faces, mats):
    me = bpy.data.meshes.new(name)
    for f, mi in mats_of_faces.items():
        f.material_index = mi
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    # UVs: cylindrical u, v = height (grime runs up from the foot)
    uvl = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = ((math.atan2(co.y, co.x) / math.tau) % 1.0, min(1.0, co.z / 1.0))
    for p in me.polygons:
        p.use_smooth = True
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    except Exception:
        pass
    o.select_set(False)
    return o


def build(colour):
    coat = coat_material("litter_bin_%s_coat" % colour, COLOURS[colour], {"green": 11, "black": 12, "red": 13}[colour])
    liner = flat_material("litter_bin_liner", (0.07, 0.072, 0.075), 0.7, 0.2)
    bag = flat_material("litter_bin_bag", (0.025, 0.025, 0.028), 0.28)
    bm = bmesh.new()
    fm = {}
    # Base plinth (bevelled lathe), hoops, slats.
    for f in lathe(bm, [(0.27, 0.0), (0.275, 0.012), (0.275, 0.045), (0.268, 0.058), (0.2, 0.06)], 32, cap_top=False):
        fm[f] = 0
    for z0, z1 in ((0.075, 0.115), (0.43, 0.46), (0.74, 0.785)):
        for f in lathe(bm, [(0.258, z0), (0.272, z0 + 0.006), (0.272, z1 - 0.006), (0.258, z1)], 32):
            fm[f] = 0
    n = 24
    for k in range(n):
        a = math.tau * (k + 0.5) / n
        c = (0.262 * math.cos(a), 0.262 * math.sin(a), 0.43)
        for f in box(bm, c, (0.012, 0.038, 0.72), a):
            fm[f] = 0
    # Liner (galvanised) with the bag folded over its lip, visible between the slats and from above.
    for f in lathe(bm, [(0.2, 0.06), (0.238, 0.075), (0.24, 0.76), (0.245, 0.79), (0.232, 0.8), (0.225, 0.62)], 40):
        fm[f] = 1
    bag_prof = [(0.218, 0.6), (0.236, 0.78), (0.252, 0.805), (0.258, 0.79), (0.255, 0.74)]
    bag_faces = lathe(bm, bag_prof, 40)
    for f in bag_faces:
        fm[f] = 2
    # wrinkle the bag rim
    for f in bag_faces:
        for v in f.verts:
            a = math.atan2(v.co.y, v.co.x)
            v.co.z += 0.004 * math.sin(a * 5.0) * max(0.0, min(1.0, (v.co.z - 0.7) / 0.08))
    # Three stays and the domed bonnet with a rolled rim.
    for k in range(3):
        a = math.tau * k / 3 + 0.5
        for f in box(bm, (0.255 * math.cos(a), 0.255 * math.sin(a), 0.84), (0.02, 0.04, 0.12), a):
            fm[f] = 0
    bonnet = [(0.31, 0.875), (0.315, 0.885), (0.31, 0.9), (0.27, 0.925), (0.2, 0.955), (0.11, 0.975), (0.0, 0.982)]
    for f in lathe(bm, bonnet, 32):
        fm[f] = 0
    under = [(0.0, 0.965), (0.2, 0.94), (0.295, 0.885), (0.31, 0.875)]
    for f in lathe(bm, under, 32):
        fm[f] = 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    o = to_obj("litter_bin_slat_" + colour, bm, fm, [coat, liner, bag])
    return o


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = []
    for colour in COLOURS:
        o = build(colour)
        objs.append(o)
        for x in bpy.data.objects:
            x.select_set(x == o)
        bpy.context.view_layer.objects.active = o
        path = os.path.join(OUT, o.name + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                                  export_animations=False, export_image_format="AUTO")
        tri = sum(len(p.vertices) - 2 for p in o.data.polygons)
        print("[litter] wrote %s %d tris %.2f MB" % (o.name, tri, os.path.getsize(path) / 1e6))
    # QA: the three bins beside the old perforated one.
    bpy.ops.import_scene.gltf(filepath=os.path.join(OUT, "litter_bin_red.glb"))
    old = [x for x in bpy.data.objects if x.type == "MESH" and x not in objs]
    for i, o in enumerate(objs + old):
        o.location.x = (i - 1.5) * 0.8
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1400, 700
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    gm = bpy.data.meshes.new("g"); gm.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("ground", gm); sc.collection.objects.link(g); gm.materials.append(flat_material("ground", (0.5, 0.5, 0.48), 0.9))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0.4, -3.4, 1.7)
    cam.rotation_euler = (Vector((0, 0, 0.5)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = QA
    bpy.ops.render.render(write_still=True)


main()
