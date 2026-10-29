"""QA renders of an MRS city build (.blend saved by mrs_streets.py --blend): views chosen from the built network
(a signalised junction, a priority junction, a back-lane mouth, a street-level walk, an overhead), with a grass
ground under the streets.
    blender --background <city.blend> --python tools/cityforge/mrs_streets_render.py -- <out_dir> [--junctions PH_J0074,...] [--no-overhead]"""
import bpy, json, math, os, sys
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]; os.makedirs(OUT, exist_ok=True)
import mrs
from mrs import qa, lighting, roads as RD
sc = bpy.context.scene
probe = bpy.data.objects.get("PH_GroundProbe")
if probe is not None:
    probe.hide_render = False; probe.hide_viewport = False
    from mrs.props import mat
    probe.data.materials.clear(); probe.data.materials.append(mat("PH_Grass", (0.12, 0.2, 0.07), 0.95))
    probe.location.z = -0.6
try: lighting.day_setup(sc)
except Exception as e: print("day setup", e)
J = [o for o in bpy.data.objects if o.type == "MESH" and o.get("mrs_junction")]
def meta(o): m = o["mrs_junction"]; return m.to_dict() if hasattr(m, "to_dict") else dict(m)
sig = next((o for o in J if meta(o).get("control") == "signals"), J[0] if J else None)
pri = next((o for o in J if meta(o).get("control") == "priority"), None)
views = []
for tag, o in (("signals", sig), ("priority", pri)):
    if o is None: continue
    at = Vector(meta(o)["at"]); z = meta(o)["z"]
    views.append(("%s_over" % tag, at + Vector((-28, -34, 36)), at + Vector((0, 0, z - at.z)), 30))
    views.append(("%s_street" % tag, at + Vector((-22, -9.5, 1.7)), at + Vector((0, -2, 1.0)), 32))
dw = next((o for o in bpy.data.objects if o.name.startswith("MRS_Driveways_PH_")), None)
if dw is not None:
    rn = dw.name[len("MRS_Driveways_"):]; road = bpy.data.objects.get(rn)
    lst = json.loads(road.get("mrs_driveways", "[]")) if road else []
    if lst:
        from mrs import structures
        a, s, w = lst[0]
        p, t, r = structures.road_sample(road, a); sg = 1.0 if s == "r" else -1.0
        q = p + r * sg * 9.0
        views.append(("lane_mouth", q - r * sg * 14.0 + t * 12.0 + Vector((0, 0, 4.0)), q, 32))
local = next((o for o in bpy.data.objects if o.type == "CURVE" and o.get("ph_cls") == "local"), None)
if local is not None:
    views.append(("local_walk", "road", local))
art = next((o for o in bpy.data.objects if o.type == "CURVE" and o.get("ph_cls") == "arterial"), None)
if art is not None: views.append(("arterial_drive", "road", art))
# named junctions (e.g. the merged diagonal / boulevard clusters): --junctions PH_J0074,PH_J0276
if "--junctions" in argv:
    for jn in argv[argv.index("--junctions") + 1].split(","):
        o = bpy.data.objects.get(jn)
        if o is None: continue
        at = Vector(meta(o)["at"])
        views.append((jn + "_over", at + Vector((-30, -38, 46)), at, 34))
# bridges (elevated decks)
for o in [o for o in bpy.data.objects if o.type == "CURVE" and dict(o.get("mrs_inputs") or {}).get("Mode") == "Elevated"][:2]:
    views.append(("bridge_" + o.name, "road", o))
xs = [o.matrix_world.translation for o in J]
if xs:
    c = sum(xs, Vector()) / len(xs)
    views.append(("overhead", c + Vector((-60, -260, 260)), c, 30))
if "--no-overhead" in argv: views = [v for v in views if v[0] != "overhead"]
paths = []
for v in views:
    p = os.path.join(OUT, v[0] + ".png")
    if v[1] == "road":
        qa.road_view(p, v[2], 0.45, lateral=-(RD.road_widths(v[2])["half"] + 2.6), height=1.7, ahead=40, lens=30, scene=sc)
    else:
        qa.render(p, v[1], v[2], v[3], scene=sc, samples=16)
    paths.append(p); print("RENDER", p)
qa.sheet(paths, os.path.join(OUT, "sheet.png"), cols=2)
print("RENDERS", len(paths))
