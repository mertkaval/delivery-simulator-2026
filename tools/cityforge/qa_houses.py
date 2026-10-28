"""Review renders of the house catalogue (house_catalogue.blend from houses.py).

    blender --background tmp/cityforge/house_catalogue.blend --python tools/cityforge/qa_houses.py -- <out_dir> [per_image]

One image per culture row (several houses per image, 3/4 front view, sun and sky, the baked
library materials), plus close-ups of the first house of each row.
"""
import math, os, sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
PER = int(argv[1]) if len(argv) > 1 else 6
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        pass
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items] else sc.view_settings.view_transform
world = sc.world or bpy.data.worlds.new("QA")
sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.55, 0.68, 0.88, 1.0)
bg.inputs[1].default_value = 1.0
sun = bpy.data.objects.new("QA_Sun", bpy.data.lights.new("QA_Sun", "SUN"))
sun.data.energy = 4.0
sun.data.angle = math.radians(2)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(-30))
ground = bpy.data.objects.new("QA_Ground", bpy.data.meshes.new("QA_Ground"))
ground.data.from_pydata([(-50, -200, 0), (400, -200, 0), (400, 60, 0), (-50, 60, 0)], [], [(0, 1, 2, 3)])
gm = bpy.data.materials.new("QA_Grass"); gm.use_nodes = True
next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.16, 0.28, 0.1, 1)
ground.data.materials.append(gm)
sc.collection.objects.link(ground)
cam = bpy.data.objects.new("QA_Cam", bpy.data.cameras.new("QA_Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_end = 2000

houses = sorted([o for o in bpy.data.objects if o.name.startswith("H_") and not o.name.endswith("_LOD1")], key=lambda o: o.name)
sc.render.resolution_x, sc.render.resolution_y = 480, 360
for o in houses:
    lo = Vector((min(v[0] for v in o.bound_box), min(v[1] for v in o.bound_box), 0))
    hi = Vector((max(v[0] for v in o.bound_box), max(v[1] for v in o.bound_box), max(v[2] for v in o.bound_box)))
    size = max(hi.x - lo.x, hi.y - lo.y, hi.z)
    c = o.location + (lo + hi) / 2
    eye = c + Vector((-0.55, 1.0, 0.42)).normalized() * size * 1.75
    cam.location = eye
    cam.rotation_euler = (c - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    for other in houses: other.hide_render = other is not o
    sc.render.filepath = os.path.join(OUT, o.name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", o.name)
