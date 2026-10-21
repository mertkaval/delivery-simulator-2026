"""Small hand props for townspeople: waiter's tray, a plate of food, a tea glass and a phone.

blender --background --factory-startup --python tools/build_npc_props.py

Output: assets/props/npc/<name>.glb (metres, Y-up after export, origin at the bottom centre;
the phone's origin is its centre with the screen facing Godot +Y). Used by LivingAssets /
LivingCitizen (phone in hand), the restaurant waiters (tray + plate) and diners' tables.
"""
import bpy
import bmesh
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "props", "npc")
os.makedirs(OUT, exist_ok=True)


def material(name, rgb, rough=0.5, metal=0.0, emit=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*[c ** 2.2 for c in rgb], 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*[c ** 2.2 for c in emit], 1.0)
        p.inputs["Emission Strength"].default_value = 0.6
    return m


def obj_from(bm, name, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    return ob


def lathe(name, profile, mat, segments=24):
    """Surface of revolution about Z from (radius, z) points."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = []
        for k in range(segments):
            a = math.tau * k / segments
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segments):
            j = (k + 1) % segments
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    if profile[0][0] > 0:
        bm.faces.new(list(reversed(rings[0])))
    if profile[-1][0] > 0:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from(bm, name, mat)


def box(name, size, at, mat, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * size[0] + at[0], v.co.y * size[1] + at[1], v.co.z * size[2] + at[2])
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    return obj_from(bm, name, mat)


def blob(name, at, scale, mat, rot=0.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=1.0)
    c, s = math.cos(rot), math.sin(rot)
    for v in bm.verts:
        x, y, z = v.co.x * scale[0], v.co.y * scale[1], max(v.co.z, -0.2) * scale[2]
        v.co = (x * c - y * s + at[0], x * s + y * c + at[1], z + at[2])
    return obj_from(bm, name, mat)


def export(name):
    path = os.path.join(OUT, name + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_materials='EXPORT', export_cameras=False, export_lights=False)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print("PROP", name, "tris", tris, path)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


steel = lambda: material("TraySteel", (0.74, 0.75, 0.76), 0.32, 0.9)
ceramic = lambda: material("PlateCeramic", (0.95, 0.94, 0.91), 0.18)

# ---- tray: 38 cm round serving tray, 2 cm rim
reset()
lathe("Tray", [(0.0, 0.0), (0.17, 0.0), (0.185, 0.006), (0.19, 0.02), (0.183, 0.021), (0.176, 0.008), (0.0, 0.008)], steel(), 32)
export("tray")

# ---- plate of food: kebab, rice, salad, tomato, lavash
reset()
lathe("Plate", [(0.0, 0.0), (0.07, 0.0), (0.09, 0.008), (0.125, 0.016), (0.13, 0.022), (0.124, 0.022), (0.09, 0.012), (0.0, 0.012)], ceramic(), 28)
rice = material("FoodRice", (0.93, 0.87, 0.72), 0.85)
meat = material("FoodKebab", (0.45, 0.22, 0.11), 0.6)
green = material("FoodSalad", (0.36, 0.6, 0.2), 0.7)
tomato = material("FoodTomato", (0.78, 0.18, 0.12), 0.35)
bread = material("FoodBread", (0.86, 0.66, 0.4), 0.85)
blob("Rice", (-0.035, 0.03, 0.012), (0.055, 0.045, 0.032), rice)
for k in range(4):
    blob("Kebab%d" % k, (0.03 + k * 0.012, -0.03 + k * 0.022, 0.016), (0.045, 0.016, 0.014), meat, rot=0.9)
for k, (x, y) in enumerate([(-0.07, -0.05), (-0.04, -0.075), (-0.085, -0.02)]):
    blob("Salad%d" % k, (x, y, 0.012), (0.025, 0.02, 0.012), green, rot=k)
for k, (x, y) in enumerate([(0.07, 0.06), (0.045, 0.08)]):
    lathe("Tomato%d" % k, [(0.0, 0.0), (0.02, 0.0), (0.02, 0.006), (0.0, 0.006)], tomato, 10).location = (x, y, 0.013)
box("Lavash", (0.09, 0.05, 0.006), (0.0, 0.085, 0.016), bread, 0.002).rotation_euler = (0.0, 0.0, 0.3)
export("plate_food")

# ---- tea glass on a saucer (Turkish tulip glass with tea)
reset()
lathe("Saucer", [(0.0, 0.0), (0.035, 0.0), (0.055, 0.006), (0.06, 0.01), (0.055, 0.01), (0.0, 0.006)], ceramic(), 20)
glass = material("TeaGlass", (0.62, 0.22, 0.1), 0.08)
lathe("Glass", [(0.0, 0.006), (0.022, 0.006), (0.026, 0.02), (0.019, 0.05), (0.024, 0.085), (0.027, 0.095), (0.0, 0.09)], glass, 16)
export("tea_glass")

# ---- phone: 7.2 x 14.8 x 0.8 cm, screen up (Blender +Z -> Godot +Y)
reset()
box("PhoneBody", (0.072, 0.148, 0.008), (0, 0, 0), material("PhoneBody", (0.08, 0.08, 0.09), 0.35, 0.4), 0.003)
box("PhoneScreen", (0.066, 0.14, 0.001), (0, 0, 0.0042), material("PhoneScreen", (0.05, 0.08, 0.12), 0.1, 0.0, emit=(0.35, 0.5, 0.7)))
export("phone")
