"""QA renders of a CityForge build (.blend from build_city.py --blend).

    blender --background <port_halden.blend> --python tools/cityforge/qa_render.py -- <out_dir> [view ...]

Views: kit (the archetype lineup, LOD0 above LOD1), aerial, downtown, street (residential street
level), harbour. Positions are in city metres (origin south-west corner, +y north).
"""
import math, os, sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
VIEWS = argv[1:] or ["kit", "aerial", "downtown", "street", "harbour"]
os.makedirs(OUT, exist_ok=True)
HALF = 1024.0
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        pass
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.render.film_transparent = False
world = bpy.data.worlds.new("QA") if sc.world is None else sc.world
sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.62, 0.74, 0.9, 1.0)
bg.inputs[1].default_value = 0.9
sun_data = bpy.data.lights.new("QA_Sun", "SUN")
sun_data.energy = 3.2
sun_data.angle = math.radians(3)
sun = bpy.data.objects.new("QA_Sun", sun_data)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
cam_data = bpy.data.cameras.new("QA_Cam")
cam_data.clip_end = 6000
cam = bpy.data.objects.new("QA_Cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(eye, target, lens=35):
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens


def city(x, y, z):
    return (x - HALF, y - HALF, z)


def show(kit_only):
    for c in bpy.data.collections:
        if c.name == "CF_Kit": c.hide_render = not kit_only
        if c.name == "CF_City": c.hide_render = kit_only


for v in VIEWS:
    if v == "kit":
        show(True)
        look((-80, -HALF - 230, 70), (-80, -HALF - 95, 0), 30)
    elif v == "aerial":
        show(False)
        look(city(1024, -500, 1300), city(1024, 1050, 0), 32)
    elif v == "downtown":
        show(False)
        look(city(980, 1300, 140), city(520, 1680, 40), 30)
    elif v == "street":
        show(False)
        look(city(1050, 1293, 1.7), city(1170, 1312, 3.0), 28)
    elif v == "harbour":
        show(False)
        look(city(1150, 2030, 60), city(700, 1700, 20), 32)
    elif v == "lake":
        show(False)
        look(city(1350, 800, 90), city(1580, 1000, 10), 30)
    sc.render.filepath = os.path.join(OUT, "qa_%s.png" % v)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", v)
