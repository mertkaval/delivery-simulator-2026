"""Reflection-strip ("zebra") curvature renders of a vehicle asset.

usage: blender --background --factory-startup --python zebra_render.py -- <asset.glb> <out_dir> [size]

Glossy neutral clay under five long, thin parallel strip lights; the strips reflect as bands
whose kinks show curvature breaks. Views: zebra_left (orthographic side, strips along the car),
zebra_hood (perspective from the front-left above the hood, strips across the car).
"""
import bpy, sys, os, math
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
asset, out = args[0], args[1]
size = int(args[2]) if len(args) > 2 else 1400
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
for o in list(scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=asset)
meshes = [o for o in scene.objects if o.type == "MESH"]
mn, mx = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        mn, mx = Vector(map(min, mn, p)), Vector(map(max, mx, p))
centre = (mn + mx) / 2
L = (mx - mn).y

clay = bpy.data.materials.new("GlossClay")
clay.use_nodes = True
b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
b.inputs["Base Color"].default_value = (0.45, 0.45, 0.44, 1)
b.inputs["Roughness"].default_value = 0.06
b.inputs["Metallic"].default_value = 0.0
for o in meshes:
    for i in range(len(o.data.materials)):
        o.data.materials[i] = clay
    if not o.data.materials:
        o.data.materials.append(clay)

world = scene.world or bpy.data.worlds.new("Zebra")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.05, 0.055, 0.06, 1)
bg.inputs[1].default_value = 0.25

lights = []


def strip(name, loc, rot, length, width=0.08, energy=70):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = length, width
    ld.energy = energy
    ld.spread = math.radians(120)
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = rot
    scene.collection.objects.link(lo)
    lights.append(lo)


def clear_lights():
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)
    lights.clear()


try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 64
scene.render.resolution_x = size
scene.render.resolution_y = int(size * 0.62)
scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items] else "Standard"
scene.view_settings.exposure = -1.6
scene.render.image_settings.file_format = "PNG"
cam_d = bpy.data.cameras.new("Z")
cam = bpy.data.objects.new("Z", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(loc, target):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


# Left side: five strips on an arc on the left of the car, running along Y, so the body side shows
# horizontal bands (shoulder line, sill scallop, door skin bulge, pillar bases).
for k, ang in enumerate((8, 26, 44, 62, 80)):
    a = math.radians(ang)
    r = 3.2
    loc = (centre.x - r * math.cos(a), centre.y, 0.6 + r * math.sin(a))
    # the light's -Z must point at the car: rotate so the panel faces the body side
    strip(f"S{k}", loc, (math.radians(90 - ang), 0, math.radians(-90)), L * 1.6)
cam_d.type = "ORTHO"
cam_d.ortho_scale = L * 1.08
aim((centre.x - 12, centre.y, centre.z), (centre.x, centre.y, centre.z))
scene.render.filepath = os.path.join(out, "zebra_left.png")
bpy.ops.render.render(write_still=True)
print("ZEBRA zebra_left", flush=True)

# Hood: five strips across the car (along X), spaced along Y above the bonnet, seen from the
# front-left above so the power dome, hood edge groove and headlamp cut read as band kinks.
clear_lights()
for k in range(5):
    y = centre.y + 0.3 + k * 0.55
    strip(f"H{k}", (centre.x, y, mx.z + 1.4), (0, 0, math.radians(90)), 5.0, energy=45)
cam_d.type = "PERSP"
cam_d.lens = 40
aim((centre.x - 2.2, mx.y + 2.4, mx.z + 1.1), (centre.x + 0.1, mx.y - 1.1, 0.85))
scene.render.filepath = os.path.join(out, "zebra_hood.png")
bpy.ops.render.render(write_still=True)
print("ZEBRA zebra_hood", flush=True)
print("ZEBRA_DONE")
