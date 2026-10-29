"""The whole new city in one Blender file, to open and check in Blender before it goes to Godot: the Mert Road Studio
street build (roads, junctions, signals, signs, markings, street assets) with CityForge's graded terrain and water
chunks appended, daylight and a camera over the map.

    blender --background <port_halden_streets.blend> --python tools/cityforge/assemble_map.py -- <city build .blend> <out map .blend>

(street build: tools/cityforge/mrs_streets.py --blend; city build: tools/cityforge/build_city.py --blend)"""
import bpy, os, sys
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:]
CITY, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
sc = bpy.context.scene
with bpy.data.libraries.load(CITY, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith(("Terrain_", "Water_", "Outskirts", "Sea"))]
col = bpy.data.collections.get("PH_Terrain") or bpy.data.collections.new("PH_Terrain")
if col.name not in sc.collection.children: sc.collection.children.link(col)
n = 0
for o in dst.objects:
    if o is None: continue
    col.objects.link(o); n += 1
# the roads show at Final quality: exactly the geometry the game gets (the ground was fitted to it)
from mrs.nodes import mod_input_set
for o in bpy.data.objects:
    if o.type == "CURVE" and "MRS_Road" in o.modifiers:
        try: mod_input_set(o.modifiers["MRS_Road"], "Viewport Quality", "Final")
        except Exception: pass
probe = bpy.data.objects.get("PH_GroundProbe")
if probe is not None: probe.hide_viewport = True; probe.hide_render = True          # the real terrain is here now
try:
    from mrs import lighting
    lighting.day_setup(sc)
except Exception as e:
    print("daylight:", e)
cam = bpy.data.objects.get("PH_MapCam") or bpy.data.objects.new("PH_MapCam", bpy.data.cameras.new("PH_MapCam"))
if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
cam.data.lens = 28.0; cam.data.clip_end = 6000.0
cam.location = Vector((0.0, -1400.0, 900.0)); cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
for scr in bpy.data.screens:                     # the viewports see the whole 2 km map without z-fighting up close
    for a in scr.areas:
        if a.type != "VIEW_3D": continue
        for s_ in a.spaces:
            if s_.type == "VIEW_3D": s_.clip_end = 6000.0; s_.clip_start = 0.5
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print("MAP saved %s: %d terrain / water objects appended" % (OUT, n))
