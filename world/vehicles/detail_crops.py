"""Orthographic 833 px/m detail crops (clay): both A-pillar side-glass front-top corners and the left tail lamp.
usage: blender --background --factory-startup --python detail_crops.py -- <glb> <out_dir>"""
import bpy, sys, os, math
args = sys.argv[sys.argv.index("--") + 1:]
asset, out = args[0], args[1]
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
for o in list(scene.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=asset)
clay = bpy.data.materials.new("Clay"); clay.use_nodes = True
b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value = (0.62, 0.62, 0.6, 1); b.inputs["Roughness"].default_value = 0.35
for o in scene.objects:
    if o.type == "MESH":
        for i in range(len(o.data.materials)): o.data.materials[i] = clay
world = scene.world or bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (0.35, 0.37, 0.4, 1); bg.inputs[1].default_value = 0.6
try: scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError: scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = 1000
cam_d = bpy.data.cameras.new("C"); cam_d.type = "ORTHO"; cam_d.ortho_scale = 1.2
cam = bpy.data.objects.new("C", cam_d); scene.collection.objects.link(cam); scene.camera = cam
ld = bpy.data.lights.new("K", "AREA"); ld.energy = 600; ld.size = 3
lo = bpy.data.objects.new("K", ld); scene.collection.objects.link(lo)
shots = (("apillar_corner_left", -1, 0.35, 1.15), ("apillar_corner_right", 1, 0.35, 1.15), ("tail_lamp_left", -1, -2.2, 0.85))
for name, sx, y, z in shots:
    cam.location = (sx * 4.0, y, z)
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90 if sx < 0 else 90))
    lo.location = (sx * 3, y, z + 1.6); lo.rotation_euler = (math.radians(55), 0, math.radians(-90 if sx < 0 else 90))
    scene.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)
print("DETAIL_CROPS done")
