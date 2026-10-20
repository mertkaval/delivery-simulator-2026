"""Seven-view QA renders of a vehicle asset under neutral studio lighting.

usage: blender --background --factory-startup --python qa_render.py -- <asset.glb|.blend> <out_dir> [clay|material|both] [size]

Views: front, rear, left, right, top, front_34, rear_34 (orthographic for the first five,
perspective 50 mm for the three-quarters). Clay = uniform grey matte with a horizontal
reflection-strip light so curvature defects read; material = the asset's own materials under
the same studio. Also writes <out_dir>/metrics.json (bounds, triangles per object, materials).
"""
import bpy, sys, os, json, math
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
asset, out = args[0], args[1]
mode = args[2] if len(args) > 2 else "both"
size = int(args[3]) if len(args) > 3 else 1200
os.makedirs(out, exist_ok=True)

scene = bpy.context.scene
for o in list(scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
if asset.lower().endswith(".blend"):
    with bpy.data.libraries.load(asset) as (src, dst):
        dst.objects = src.objects
    for o in dst.objects:
        if o is not None:
            scene.collection.objects.link(o)
else:
    bpy.ops.import_scene.gltf(filepath=asset)
meshes = [o for o in scene.objects if o.type == "MESH"]
bpy.context.view_layer.update()

# Bounds and metrics.
mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
metrics = {"asset": asset, "objects": [], "materials": sorted({m.name for o in meshes for m in o.data.materials if m})}
total = 0
for o in meshes:
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, p))
        mx = Vector(map(max, mx, p))
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    total += tris
    metrics["objects"].append({"name": o.name, "triangles": tris, "flat_faces": sum(1 for p in o.data.polygons if not p.use_smooth),
                               "materials": [m.name if m else None for m in o.data.materials]})
metrics["bounds_m"] = {"min": [round(v, 3) for v in mn], "max": [round(v, 3) for v in mx], "size": [round(v, 3) for v in (mx - mn)]}
metrics["triangles_total"] = total
centre = (mn + mx) / 2
extent = max(mx - mn)
json.dump(metrics, open(os.path.join(out, "metrics.json"), "w"), indent=1)

# Studio: grey ground, soft key/fill, and a long thin "reflection strip" area light above.
world = scene.world or bpy.data.worlds.new("Studio")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.35, 0.37, 0.4, 1)
bg.inputs[1].default_value = 0.6
ground = bpy.data.meshes.new("ground")
r = extent * 4
ground.from_pydata([(-r, -r, mn.z), (r, -r, mn.z), (r, r, mn.z), (-r, r, mn.z)], [], [(0, 1, 2, 3)])
g = bpy.data.objects.new("Ground", ground)
scene.collection.objects.link(g)
gm = bpy.data.materials.new("GroundMat")
gm.use_nodes = True
next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.22, 0.22, 0.23, 1)
ground.materials.append(gm)


def light(name, kind, loc, rot, energy, size=(2.0, 2.0)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    if kind == "AREA":
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = rot
    scene.collection.objects.link(lo)


light("Strip", "AREA", (centre.x, centre.y, mx.z + extent * 0.7), (0, 0, 0), 70 * extent, (extent * 2.5, extent * 0.25))
light("Key", "AREA", (centre.x + extent, centre.y - extent, mx.z + extent * 0.6), (math.radians(55), 0, math.radians(45)), 120 * extent, (extent, extent))
light("Fill", "AREA", (centre.x - extent * 1.2, centre.y + extent * 0.8, mx.z + extent * 0.3), (math.radians(70), 0, math.radians(-125)), 40 * extent, (extent, extent))
scene.view_settings.exposure = -0.3

try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 48
scene.render.resolution_x = size
scene.render.resolution_y = int(size * 0.62)
scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items] else "Standard"
scene.render.image_settings.file_format = "PNG"

clay = bpy.data.materials.new("Clay")
clay.use_nodes = True
cb = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
cb.inputs["Base Color"].default_value = (0.62, 0.62, 0.6, 1)
cb.inputs["Roughness"].default_value = 0.35
cb.inputs["Metallic"].default_value = 0.0

cam_data = bpy.data.cameras.new("QA")
cam = bpy.data.objects.new("QA", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
L = (mx - mn).y
W = (mx - mn).x
H = (mx - mn).z
views = {
    "front": ((0, 1, 0), "ORTHO", W * 1.25, H),
    "rear": ((0, -1, 0), "ORTHO", W * 1.25, H),
    "left": ((-1, 0, 0), "ORTHO", L * 1.1, H),
    "right": ((1, 0, 0), "ORTHO", L * 1.1, H),
    "top": ((0, 0, 1), "ORTHO", L * 1.1, W),
    "front_34": ((0.75, 0.75, 0.3), "PERSP", 0, 0),
    "rear_34": ((-0.75, -0.75, 0.3), "PERSP", 0, 0),
}


def aim(direction, kind, ortho):
    d = Vector(direction).normalized()
    dist = extent * 3.2
    cam.location = centre + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = kind
    cam_data.lens = 50
    if kind == "ORTHO":
        cam_data.ortho_scale = ortho
    if kind == "PERSP":
        # Frame the whole car with a little margin.
        cam_data.lens = 45
        cam.location = centre + d * extent * 1.25


def render(tag):
    for name, (direction, kind, ortho, _h) in views.items():
        aim(direction, kind, ortho)
        if kind == "ORTHO" and name == "top":
            cam.rotation_euler = (0, 0, math.radians(90))
            cam.location = centre + Vector((0, 0, extent * 3.2))
        scene.view_settings.exposure = -1.3 if name == "top" else -0.3
        scene.render.filepath = os.path.join(out, f"{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("QA_RENDER", tag, name, scene.render.filepath, flush=True)


originals = {o: list(o.data.materials) for o in meshes}
if mode in ("clay", "both"):
    for o in meshes:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = clay
        if not o.data.materials:
            o.data.materials.append(clay)
    render("clay")
    for o, mats in originals.items():
        for i, m in enumerate(mats):
            o.data.materials[i] = m
if mode in ("material", "both"):
    render("material")
print("QA_DONE", json.dumps(metrics["bounds_m"]), "tris", total)
