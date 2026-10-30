"""The reconstruction scene: every example the City Road Maker 2.1 tutorial builds, made with the Mert Road Studio tool
(MRS_Road tongues, MRS_AreaJunction, extensions, MRS_CustomSign, MRS_MarkingLines), rendered from views like the video's,
then composed under the matching evidence frame by compare.py (plain Python + Pillow).

    blender --background tmp/roads/city/base.blend --python tools/roads/crm_reconstruction/build/reconstruct.py -- <out_dir>
        [--rebuild-groups] [--no-render]

Examples (evidence ids in ../evidence/index.json):
  A crossing      four roads with 10 m tongues, one junction (E21-E25)
  B downhill      a T with one road climbing to the junction, its last points level (E28)
  C bus bay       a square extension at a straight road's kerb inside a junction, shelter + BUS / STOP (E35-E36)
  D cul-de-sac    a round extension at a road end (E37)
  E roundabout    four roads, a round extension, an island (E38-E39)
  F car park      a square extension + entrance square off a road, bay lines (marking lines + Array) (E40-E41)
  G signs         the CRM 2.1 sign and the stop sign (E43-E48)
Writes <out>/CRM_Reconstruction.blend, <out>/renders/*.png, <out>/reconstruction.json."""
import bpy, json, math, os, sys, time
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); RECON = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(RECON)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "crm_reconstruction"))
os.makedirs(os.path.join(OUT, "renders"), exist_ok=True)
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
import mrs
from mrs import areajunction as AJ, customsign as CS, markinglines as ML, roads, nodes
from mrs.nodes import mod_input_set
if "--rebuild-groups" in argv:
    from mrs import road
    road.build_road_group()
AJ.build_all(); CS.build_custom_sign(); ML.build_marking_lines()

t0 = time.time()
sc = bpy.data.scenes.get("CRM_Reconstruction") or bpy.data.scenes.new("CRM_Reconstruction")
nodes.set_scene(sc)
try: bpy.context.window.scene = sc
except Exception: pass
ROADS = bpy.data.collections.new("Roads"); sc.collection.children.link(ROADS)
JUNCS = bpy.data.collections.new("Junctions"); sc.collection.children.link(JUNCS)
PROPS = bpy.data.collections.new("Props"); sc.collection.children.link(PROPS)
LEVEL = 1.0                       # CRM's "level one": every tongue at the same global height
TG = 10.0                         # CRM's default Tongue Size
SPACING = 160.0
REPORT = {"examples": {}}


def road(name, pts, **kw):
    kw.setdefault("Conform", False); kw.setdefault("Embankment", False)
    for k in ("Trees", "Streetlights"): kw.setdefault(k, None)          # collection inputs: None = none
    return roads.make_road(name, pts, ROADS, "residential", Props=None, **kw)


def ground(cx, cy, size=140.0):
    me = bpy.data.meshes.new("Ground"); h = size / 2
    me.from_pydata([(cx - h, cy - h, LEVEL - 0.35), (cx + h, cy - h, LEVEL - 0.35), (cx + h, cy + h, LEVEL - 0.35), (cx - h, cy + h, LEVEL - 0.35)], [], [(0, 1, 2, 3)])
    from mrs.props import mat
    me.materials.append(mat("MRS_Ground", (0.16, 0.24, 0.09), 0.95)); o = bpy.data.objects.new("Ground", me); PROPS.objects.link(o)


def origin(i):
    return Vector(((i % 4) * SPACING, -(i // 4) * SPACING, 0.0))

# ---------------------------------------------------------------- A crossing (E21-E25)
o = origin(0); ground(o.x, o.y)
for nm, d in (("A_E", (1, 0)), ("A_W", (-1, 0)), ("A_N", (0, 1)), ("A_S", (0, -1))):
    road(nm, [(o.x + d[0] * 60, o.y + d[1] * 60, LEVEL), (o.x - d[0] * 2, o.y - d[1] * 2, LEVEL)], Tongue_End=TG)   # 2 m past the centre
AJ.add_area_junction("A_Junction", (o.x, o.y, LEVEL), ROADS, JUNCS)
REPORT["examples"]["A"] = {"centre": list(o), "evidence": ["E21", "E23", "E25"]}

# ---------------------------------------------------------------- B downhill (E28): the south road climbs 6 m, its last points level
o = origin(1); ground(o.x, o.y)
road("B_W", [(o.x - 60, o.y, LEVEL), (o.x + 2, o.y, LEVEL)], Tongue_End=TG)
road("B_E", [(o.x + 60, o.y, LEVEL), (o.x - 2, o.y, LEVEL)], Tongue_End=TG)
road("B_S", [(o.x, o.y - 70, LEVEL - 6.0), (o.x, o.y - 30, LEVEL - 1.0), (o.x, o.y - 16, LEVEL), (o.x, o.y - 8, LEVEL), (o.x, o.y + 2, LEVEL)], Tongue_End=TG)
AJ.add_area_junction("B_Junction", (o.x, o.y, LEVEL), ROADS, JUNCS)
REPORT["examples"]["B"] = {"centre": list(o), "evidence": ["E28"]}

# ---------------------------------------------------------------- C bus bay (E35-E36)
o = origin(2); ground(o.x, o.y)
road("C_W", [(o.x - 70, o.y, LEVEL), (o.x + 2, o.y, LEVEL)], Tongue_End=24.0)
road("C_E", [(o.x + 70, o.y, LEVEL), (o.x - 2, o.y, LEVEL)], Tongue_End=24.0)
w = roads.road_widths(bpy.data.objects["C_W"])
bay_w = 3.0; bay_y = w["half_l"] + bay_w * 0.5 - 0.3                     # the bay cuts into the north kerb by its width
AJ.add_extension("C_Bay", "square", ROADS, (o.x, o.y + bay_y, LEVEL), (24.0, bay_w), **{"Roadside Size": w["curb"] + w["swl"]})
AJ.add_area_junction("C_Junction", (o.x, o.y, LEVEL), ROADS, JUNCS, Distance=30.0)
shelter = bpy.data.objects.get("MRS_BusShelter")
if shelter is not None:
    s = bpy.data.objects.new("C_Shelter", shelter.data); PROPS.objects.link(s)
    s.location = (o.x, o.y + bay_y + bay_w * 0.5 + w["curb"] + 1.2, LEVEL + 0.15); s.rotation_euler = (0, 0, math.pi)
for word, dx in (("BUS", -3.5), ("STOP", 3.5)):
    src = bpy.data.objects.get("MRS_Text" + word)
    if src is not None:
        t = bpy.data.objects.new("C_" + word, src.data); PROPS.objects.link(t)
        t.location = (o.x + dx, o.y + bay_y, LEVEL + 0.004); t.rotation_euler = (0, 0, math.pi / 2)
REPORT["examples"]["C"] = {"centre": list(o), "evidence": ["E35", "E36"]}

# ---------------------------------------------------------------- D cul-de-sac (E37)
o = origin(3); ground(o.x, o.y)
road("D_Road", [(o.x - 70, o.y, LEVEL), (o.x + 4, o.y, LEVEL)], Tongue_End=TG)
AJ.add_extension("D_Round", "round", ROADS, (o.x + 6, o.y, LEVEL), (20.0, 20.0), **{"Roadside Size": 2.5})
AJ.add_area_junction("D_Junction", (o.x + 4, o.y, LEVEL), ROADS, JUNCS, Distance=25.0)
REPORT["examples"]["D"] = {"centre": list(o), "evidence": ["E37"]}

# ---------------------------------------------------------------- E roundabout (E38-E39)
o = origin(4); ground(o.x, o.y)
for nm, d in (("E_E", (1, 0)), ("E_W", (-1, 0)), ("E_N", (0, 1)), ("E_S", (0, -1))):
    road(nm, [(o.x + d[0] * 70, o.y + d[1] * 70, LEVEL), (o.x + d[0] * 12, o.y + d[1] * 12, LEVEL)], Tongue_End=TG)
AJ.add_extension("E_Ring", "round", ROADS, (o.x, o.y, LEVEL), (34.0, 34.0), **{"Roadside Size": 2.5})
AJ.add_extension("E_Island", "round", ROADS, (o.x, o.y, LEVEL), (14.0, 14.0), Island=True)
AJ.add_area_junction("E_Junction", (o.x, o.y, LEVEL), ROADS, JUNCS, Distance=30.0)
REPORT["examples"]["E"] = {"centre": list(o), "evidence": ["E38", "E39"]}

# ---------------------------------------------------------------- F car park (E40-E41)
o = origin(5); ground(o.x, o.y)
road("F_W", [(o.x - 70, o.y, LEVEL), (o.x + 2, o.y, LEVEL)], Tongue_End=TG)
road("F_E", [(o.x + 70, o.y, LEVEL), (o.x - 2, o.y, LEVEL)], Tongue_End=TG)
# the entrance reaches into the carriageway (as in E40): from 1 m inside the road to the car park
AJ.add_extension("F_Entrance", "square", ROADS, (o.x, o.y + 9.0, LEVEL), (7.0, 14.0), **{"Roadside Size": 2.0})
AJ.add_extension("F_Park", "square", ROADS, (o.x, o.y + 28.0, LEVEL), (40.0, 24.0), **{"Roadside Size": 2.5})
AJ.add_area_junction("F_Junction", (o.x, o.y + 12.0, LEVEL), ROADS, JUNCS, Distance=45.0)
for row_y, flip in ((o.y + 18.5, 1.0), (o.y + 37.5, -1.0)):
    bay = ML.add_marking_lines("F_Bay", [(o.x - 17.0, row_y, LEVEL), (o.x - 17.0, row_y + 5.0 * flip, LEVEL)], PROPS,
                               **{"Edge Marking": False, "Center Marking": True, "Center Line 1": "Solid", "Center Color": "White", "Center Width": 0.12})
    arr = bay.modifiers.new("Array", "ARRAY"); arr.count = 14; arr.use_relative_offset = False; arr.use_constant_offset = True
    arr.constant_offset_displace = (2.6, 0.0, 0.0)
REPORT["examples"]["F"] = {"centre": list(o), "evidence": ["E40", "E41"]}

# ---------------------------------------------------------------- G signs (E43-E48)
o = origin(6); ground(o.x, o.y, 40.0)
CS.add_custom_sign("G_CRM", (o.x - 0.8, o.y, LEVEL - 0.35), "CRM 2.1", PROPS)
CS.add_custom_sign("G_Stop", (o.x + 0.8, o.y, LEVEL - 0.35), "Stop", PROPS)
REPORT["examples"]["G"] = {"centre": list(o), "evidence": ["E44", "E47"]}

dg = bpy.context.evaluated_depsgraph_get()
for j in JUNCS.objects:
    me = j.evaluated_get(dg).to_mesh(); REPORT["examples"][j.name[0]]["junction_faces"] = len(me.polygons); j.evaluated_get(dg).to_mesh_clear()
print("RECON built in %.0fs: %s" % (time.time() - t0, {k: v.get("junction_faces") for k, v in REPORT["examples"].items()}))

VIEWS = {   # name: (example, eye offset, target offset, lens, evidence frame for the comparison)
    "A_top": ("A", (0, 0.01, 75), (0, 0, LEVEL), 30.0, "E25"), "A_persp": ("A", (26, -22, 12), (0, 0, LEVEL), 28.0, "E27"),
    "B_persp": ("B", (24, -46, 16), (0, -6, LEVEL), 30.0, "E28"),
    "C_top": ("C", (0, 0.01, 60), (0, 3, LEVEL), 30.0, "E35"), "C_persp": ("C", (-14, -12, 6), (0, 4, LEVEL), 24.0, "E36"),
    "D_top": ("D", (-6, 0.01, 70), (-6, 0, LEVEL), 30.0, "E37"),
    "E_top": ("E", (0, 0.01, 80), (0, 0, LEVEL), 30.0, "E38"),
    "F_top": ("F", (0, 22.01, 85), (0, 22, LEVEL), 30.0, "E40"),
    "G_front": ("G", (0, -3.4, 2.0), (0, 0, 1.75), 45.0, "E47"),
}
if "--no-render" not in argv:
    from mrs import qa, lighting
    try: lighting.day_setup(sc)
    except Exception as e: print("daylight:", e)
    for name, (ex, eye, tgt, lens, ev) in VIEWS.items():
        c = Vector(REPORT["examples"][ex]["centre"])
        path = os.path.join(OUT, "renders", name + ".png")
        qa.render(path, c + Vector(eye), c + Vector(tgt), lens, res=(1280, 720), samples=24, scene=sc); print("RENDER", name)
REPORT["views"] = {k: {"example": v[0], "evidence": v[4], "render": os.path.join(OUT, "renders", k + ".png")} for k, v in VIEWS.items()}
with open(os.path.join(OUT, "reconstruction.json"), "w") as f: json.dump(REPORT, f, indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "CRM_Reconstruction.blend"), copy=True, compress=True)
print("RECONSTRUCTION done in %.0fs -> %s" % (time.time() - t0, OUT))
