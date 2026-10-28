"""Mert Road Studio materials validation (headless):

    blender --background --factory-startup --python tools/roads/tests/materials_test.py [-- --quick]

Builds every MRS material, asserts group / material / input names, applies every preset, renders an EEVEE
demo (12 x 40 m road slab with lat / along / half_l / half_r / drain / kind / UVMap attributes, paint lines,
concrete and paved sidewalks, tactile strip, cycle lane, pole, embankment) per Surface Type and per preset,
the three wear presets side by side, uniform vs drain-localized wetness, 1 m / 4 m close-ups of the street
materials with a 10 cm ruler, a shader-ball row, bakes the tiles at 1024 px into tmp/roads/materials/tiles/
and renders a seam check. Output: tmp/roads/materials/*.png + contact_sheet.png.
"""
import math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
import bpy
import numpy as np
from mathutils import Vector
from mrs import materials, qa
from mrs.nodes import MRS

OUT = os.path.join(ROOT, "tmp", "roads", "materials")
QUICK = "--quick" in sys.argv
os.makedirs(OUT, exist_ok=True)
T0 = time.time()


def log(*a):
    print("[materials_test]", " ".join(str(x) for x in a), flush=True)


# ------------------------------------------------------------------------------------ build + assert
mats = materials.build_materials(); extra = materials.extra_materials()
assert set(mats) == {"Asphalt", "Paint", "Concrete"}, mats
assert len(extra) == 3
REQUIRED = {
    "AsphaltShader": ["Asphalt Scale", "Asphalt Roughness", "Color Variation", "Patch Amount", "Wetness", "Base Color", "Bump Strength",
                      "Surface Type", "Cracks", "Tire Wear", "Lane Width", "Lanes", "Edge Dirt", "Half Width", "Curb Dirt Width", "Repair Seed",
                      "Use Drain", "Wear Along Start", "Wear Along End", "Slab Size", "Stone Size", "Use UV", "Tile Size"],
    "PaintShader": ["Paint Wear", "Wetness", "Paint Color", "Asphalt Scale", "Bump Strength", "Yellow", "Sparkle", "Chipping", "Use Drain",
                    "Wear Along Start", "Wear Along End", "Use UV", "Tile Size"],
    "ConcreteShader": ["Concrete Variation", "Slab Size", "Wetness", "Base Color", "Bump Strength", "Asphalt Scale", "Rust Streaks", "Grime", "Grime Height", "Use Drain", "Use UV", "Tile Size"],
    "EmbankmentShader": ["Grass Color", "Dirt Color", "Rockiness", "Slope Override", "Use UV", "Tile Size"],
    "PavingShader": ["Paving Size", "Joint Width", "Base Color", "Tone Variation", "Chipping", "Grime", "Curb Dirt Width", "Half Width", "Wetness", "Use UV", "Tile Size"],
    "TactileShader": ["Dome Spacing", "Dome Diameter", "Base Color", "Wear", "Grime", "Wetness", "Use UV", "Tile Size"],
    "CyclewayShader": ["Surface Color", "Wear", "Wetness", "Wear Along Start", "Wear Along End", "Use Drain", "Use UV", "Tile Size"],
    "MetalShader": ["Color", "Roughness", "Spangle", "Anisotropy", "Rust", "Rust Height", "Use UV", "Tile Size"],
}
for grp, names in REQUIRED.items():
    ng = bpy.data.node_groups.get(MRS + grp); assert ng is not None, grp
    have = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]
    missing = [n for n in names if n not in have]; assert not missing, (grp, missing)
    outs = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "OUTPUT"]
    assert outs[0] == "BSDF" and (outs == ["BSDF"] or grp == "MetalShader"), (grp, outs)
    log(grp, len(ng.nodes), "nodes; inputs:", have)
GROUP_OF = {"Asphalt": "AsphaltShader", "Paint": "PaintShader", "Concrete": "ConcreteShader", "BikeLane": "CyclewayShader", "Structure": "ConcreteShader",
            "Embankment": "EmbankmentShader", "Paving": "PavingShader", "Tactile": "TactileShader", "Cycleway": "CyclewayShader", "PoleMetal": "MetalShader"}
for suffix in materials.MATERIAL_NAMES:
    m = bpy.data.materials.get(MRS + suffix); assert m is not None, suffix
    g = [n for n in m.node_tree.nodes if n.type == "GROUP"]; assert len(g) == 1 and g[0].name == "MRS", (suffix, [n.name for n in g])
    assert g[0].node_tree.name == MRS + GROUP_OF[suffix], (suffix, g[0].node_tree.name)
    out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"); assert out.inputs["Surface"].links[0].from_node.name == "MRS"
assert set(materials.MATERIAL_PRESETS) == {"clean", "light_wear", "heavy_wear", "wet", "old_village", "dirt_track", "fresh_highway"}, list(materials.MATERIAL_PRESETS)
for p in materials.MATERIAL_PRESETS: materials.apply_material_preset(p)
materials.apply_material_preset("wet")
for mat, node in materials.mrs_nodes():
    if "Wetness" in node.inputs: assert abs(node.inputs["Wetness"].default_value - 0.85) < 1e-6, mat.name
materials.apply_material_preset("old_village")
assert abs(bpy.data.materials[MRS + "Asphalt"].node_tree.nodes["MRS"].inputs["Surface Type"].default_value - 4.0) < 1e-6
assert abs(bpy.data.materials[MRS + "Paint"].node_tree.nodes["MRS"].inputs["Yellow"].default_value - 0.85) < 1e-6
materials.apply_material_preset("clean")
A = bpy.data.materials[MRS + "Asphalt"].node_tree.nodes["MRS"].inputs
assert A["Cracks"].default_value == 0.0 and A["Patch Amount"].default_value == 0.0 and abs(A["Wetness"].default_value) < 1e-6
log("presets:", list(materials.MATERIAL_PRESETS))


# ------------------------------------------------------------------------------------ demo geometry
def mesh_obj(name, verts, faces, mat, kind, smooth=False, half=6.0, drain=None, lat0=0.0):
    """Mesh with UVMap = (x, y) metres, point attrs lat = x - lat0, along = y, half_l / half_r, drain, face attr kind."""
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    me.attributes.new("lat", "FLOAT", "POINT").data.foreach_set("value", [v[0] - lat0 for v in verts])
    me.attributes.new("along", "FLOAT", "POINT").data.foreach_set("value", [v[1] for v in verts])
    me.attributes.new("half_l", "FLOAT", "POINT").data.foreach_set("value", [half] * len(verts))
    me.attributes.new("half_r", "FLOAT", "POINT").data.foreach_set("value", [half] * len(verts))
    me.attributes.new("drain", "FLOAT", "POINT").data.foreach_set("value", [drain(v[0] - lat0, v[1]) if drain else 0.0 for v in verts])
    me.attributes.new("kind", "FLOAT", "FACE").data.foreach_set("value", [float(kind)] * len(faces))
    uv = me.uv_layers.new(name="UVMap")
    for lp in me.loops: uv.data[lp.index].uv = (verts[lp.vertex_index][0], verts[lp.vertex_index][1])
    me.materials.append(mat)
    for p in me.polygons: p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob


def grid(name, x0, x1, y0, y1, z, nx, ny, mat, kind, **kw):
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx; y = y0 + (y1 - y0) * j / ny
            verts.append((x, y, z(x, y) if callable(z) else z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i; faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    return mesh_obj(name, verts, faces, mat, kind, **kw)


def strip(name, profile, y0, y1, ny, mat, kind, smooth=False, **kw):
    verts, faces = [], []
    n = len(profile)
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        for (x, z) in profile: verts.append((x, y, z))
    for j in range(ny):
        for i in range(n - 1):
            a = j * n + i; faces.append((a, a + 1, a + n + 1, a + n))
    return mesh_obj(name, verts, faces, mat, kind, smooth, **kw)


def pole(name, x, y, z0, radius, height, mat):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, vertices=32, location=(x, y, z0))
    ob = bpy.context.active_object; ob.name = name
    for v in ob.data.vertices: v.co.z += height / 2          # origin at the base: rust by object Z starts at the ground
    ob.data.materials.append(mat)
    for p in ob.data.polygons: p.use_smooth = True
    return ob


L = 40.0
M = lambda s: bpy.data.materials[MRS + s]
sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o)
DRAIN = lambda x, y: min(max(x / 6.0, 0.0), 1.0)                 # gradient toward the right curb (x = +6)
road = grid("Demo_Road", -6, 6, 0, L, 0.0, 24, 40, M("Asphalt"), 0, drain=DRAIN)
pv, pf = [], []
def quad(x0, x1, y0, y1, z=0.003):
    b = len(pv); pv.extend([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]); pf.append((b, b + 1, b + 2, b + 3))
for x in (-1.8, 1.8):
    y = 1.0
    while y + 3.0 <= L: quad(x - 0.06, x + 0.06, y, y + 3.0); y += 9.0
quad(-5.575, -5.425, 0, L); quad(3.925, 4.075, 0, L)
quad(-3.0, 3.0, 24.0, 24.6)
paint = mesh_obj("Demo_Paint", pv, pf, M("Paint"), 1, drain=DRAIN)
grid("Demo_Cycleway", 4.2, 5.8, 0, L, 0.002, 2, 20, M("Cycleway"), 5, drain=DRAIN)
strip("Demo_Sidewalk-1", [(-6, 0.0), (-6, 0.15), (-8.5, 0.15)], 0, L, 8, M("Concrete"), 2)
strip("Demo_Curb+1", [(6, 0.0), (6, 0.15)], 0, L, 8, M("Concrete"), 2)
strip("Demo_Paving+1", [(6, 0.15), (8.5, 0.15)], 0, L, 8, M("Paving"), 6)
grid("Demo_Tactile", 6.3, 7.5, 22.0, 25.2, 0.152, 2, 2, M("Tactile"), 7)
for s in (1, -1):
    strip("Demo_Embankment%+d" % s, [(8.5 * s, 0.15), (9.6 * s, 0.05), (13.0 * s, -2.1), (14.5 * s, -2.4), (24 * s, -2.6)], 0, L, 8, M("Embankment"), 4)
wall = mesh_obj("Demo_Wall", [(-24, L + 3, -2.6), (24, L + 3, -2.6), (24, L + 3, 4.0), (-24, L + 3, 4.0)], [(0, 1, 2, 3)], M("Structure"), 3)
pole("Demo_Pole", 7.2, 14.0, 0.15, 0.06, 3.6, M("PoleMetal"))
asph = M("Asphalt").node_tree.nodes["MRS"].inputs
asph["Lanes"].default_value = 3.0; asph["Lane Width"].default_value = 3.6; asph["Half Width"].default_value = 6.0

# shader balls (far off to the side)
BALL_X0 = 200.0
floor = grid("Demo_BallFloor", BALL_X0 - 16, BALL_X0 + 16, -8, 12, -1.0, 2, 2, bpy.data.materials.new("Demo_Floor"), 0)
floor.data.materials[0].use_nodes = True
floor.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.25, 0.25, 1)
for i, suffix in enumerate(materials.MATERIAL_NAMES):
    x = BALL_X0 - 13.5 + 3.0 * i
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.9, segments=64, ring_count=32, location=(x, 0, -0.1))
    b = bpy.context.active_object; b.name = "Ball_" + suffix; b.data.materials.append(M(suffix))
    for p in b.data.polygons: p.use_smooth = True
    grid("Tile_" + suffix, x - 1.2, x + 1.2, 1.6, 4.0, -0.99, 1, 1, M(suffix), 0)

# material samples for the 1 m / 4 m close-ups, each with a 10 cm x 1 cm white ruler (Paint) beside it
SAMPLE_X0 = 300.0
samples = {}
samples["paving"] = grid("Sample_Paving", SAMPLE_X0 + 6.1, SAMPLE_X0 + 9.1, 0, 3, 0.0, 1, 1, M("Paving"), 6, lat0=SAMPLE_X0)      # lat 6.1..9.1: grime at the kerb side
samples["tactile"] = grid("Sample_Tactile", SAMPLE_X0 + 20, SAMPLE_X0 + 21.2, 0, 1.2, 0.0, 1, 1, M("Tactile"), 7, lat0=SAMPLE_X0 + 20)
samples["cycleway"] = grid("Sample_Cycleway", SAMPLE_X0 + 30, SAMPLE_X0 + 33, 0, 3, 0.0, 1, 1, M("Cycleway"), 5, lat0=SAMPLE_X0 + 31.5)
pole("Sample_Pole", SAMPLE_X0 + 40, 1.5, 0.0, 0.06, 3.0, M("PoleMetal"))
grid("Sample_PoleFloor", SAMPLE_X0 + 38, SAMPLE_X0 + 42, -1, 4, -0.001, 1, 1, M("Paving"), 6, lat0=SAMPLE_X0 + 34)
SAMPLE_CENTRES = {"paving": (SAMPLE_X0 + 7.6, 1.2, 0.0), "tactile": (SAMPLE_X0 + 20.6, 0.6, 0.0), "cycleway": (SAMPLE_X0 + 31.5, 1.2, 0.0), "pole": (SAMPLE_X0 + 40.0, 1.5, 0.35)}
for key, (cx, cy, cz) in SAMPLE_CENTRES.items():                # 10 cm x 1 cm white ruler just in front of the 1 m camera target
    x, y = cx - 0.22, cy - 0.16
    rv, rf = [(x - 0.05, y, 0.004), (x + 0.05, y, 0.004), (x + 0.05, y + 0.01, 0.004), (x - 0.05, y + 0.01, 0.004)], [(0, 1, 2, 3)]
    mesh_obj("Ruler_" + key, rv, rf, M("Paint"), 1, lat0=x)


# ------------------------------------------------------------------------------------ rendering
def render(path, eye, target, lens=32.0, res=(1280, 720), samples=32):
    sc = bpy.context.scene
    cam, sun = qa.ensure_camera_and_sun(sc); qa.look(cam, eye, target, lens)
    r = sc.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    ee = sc.eevee
    ee.taa_render_samples = samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 4), ("use_gtao", True)):
        if hasattr(ee, attr):
            try: setattr(ee, attr, val)
            except Exception: pass
    looks = [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items]
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast" if "AgX - Medium High Contrast" in looks else "None"
    sc.view_settings.exposure = 0.0
    r.resolution_x, r.resolution_y = res; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.filepath = os.path.abspath(path)
    t = time.time(); bpy.ops.render.render(write_still=True)
    log("render %s (%.1fs)" % (os.path.basename(path), time.time() - t))
    return r.filepath


def closeup(path, centre, dist, lens=40.0, res=(1280, 720)):
    cx, cy, cz = centre
    return render(path, eye=(cx + dist * 0.15, cy - dist * 0.7, cz + dist * 0.68), target=centre, lens=lens, res=res)


w = bpy.data.worlds.get(MRS + "World") or bpy.data.worlds.new(MRS + "World"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld"); nt.links.new(bg.outputs[0], out.inputs[0])
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
cr.elements[0].position = 0.0; cr.elements[0].color = (0.14, 0.13, 0.11, 1)
e1 = cr.elements.new(0.5); e1.color = (0.5, 0.55, 0.64, 1)
cr.elements[2].position = 0.85; cr.elements[2].color = (0.14, 0.26, 0.58, 1)
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1.0; mr.inputs["From Max"].default_value = 1.0
nt.links.new(sep.outputs[2], mr.inputs["Value"]); nt.links.new(mr.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.7
sun_ob = bpy.data.objects.get(MRS + "QASun") or qa.ensure_camera_and_sun(sc)[1]
sun_ob.data.energy = 4.0; sun_ob.data.color = (1.0, 0.95, 0.86); sun_ob.data.angle = math.radians(1.5); sun_ob.rotation_euler = (math.radians(50), 0, math.radians(-35))

STREET = dict(eye=(1.2, -3.0, 1.55), target=(0.0, 16.0, -0.2), lens=30.0)
CLOSE = dict(eye=(1.6, 5.0, 1.5), target=(0.7, 7.2, 0.0), lens=45.0)
TYPES = ["fresh_asphalt", "aged_asphalt", "cracked_asphalt", "concrete_road", "cobblestone", "dirt_gravel"]
renders = []


def set_drain(flag):
    for suffix in ("Asphalt", "Paint", "Cycleway", "Concrete", "Paving"):
        n = M(suffix).node_tree.nodes["MRS"]
        if "Use Drain" in n.inputs: n.inputs["Use Drain"].default_value = flag


# surface types under light wear
materials.apply_material_preset("light_wear")
for i, name in enumerate(TYPES):
    asph["Surface Type"].default_value = float(i)
    renders.append(render(os.path.join(OUT, "type%d_%s.png" % (i, name)), **STREET))
    if not QUICK or i in (1, 4):
        renders.append(render(os.path.join(OUT, "close%d_%s.png" % (i, name)), **CLOSE))
# presets, and the three wear levels side by side
for p in materials.MATERIAL_PRESETS:
    materials.apply_material_preset(p)
    renders.append(render(os.path.join(OUT, "preset_%s.png" % p), **STREET))
# wetness: uniform vs localized by the drain gradient (right curb) and the gutter line
materials.apply_material_preset("wet")
WETCAM = dict(eye=(-2.0, 2.0, 5.5), target=(1.0, 18.0, -0.5), lens=30.0)
set_drain(0.0); renders.append(render(os.path.join(OUT, "wet_uniform.png"), **WETCAM))
set_drain(1.0); renders.append(render(os.path.join(OUT, "wet_localized.png"), **WETCAM))
set_drain(0.0)
materials.apply_material_preset("light_wear")
# street materials: 1 m and 4 m close-ups with the 10 cm ruler
for key in ("paving", "tactile", "cycleway", "pole"):
    c = SAMPLE_CENTRES[key]
    renders.append(closeup(os.path.join(OUT, "%s_1m.png" % key), c, 1.0, lens=45.0))
    renders.append(closeup(os.path.join(OUT, "%s_4m.png" % key), (c[0], c[1], c[2] + (0.9 if key == "pole" else 0.0)), 4.0, lens=40.0))
renders.append(render(os.path.join(OUT, "street_right_side.png"), eye=(3.0, 8.0, 1.6), target=(7.0, 22.0, 0.2), lens=32.0))
renders.append(render(os.path.join(OUT, "balls.png"), eye=(BALL_X0, -24.0, 6.0), target=(BALL_X0, 1.0, -0.4), lens=36.0, res=(1920, 720)))
renders.append(render(os.path.join(OUT, "wall_structure.png"), eye=(-6, L - 4, 1.6), target=(0, L + 3, 0.6), lens=35.0))
renders.append(render(os.path.join(OUT, "embankment_close.png"), eye=(17.0, 6.0, -0.6), target=(10.5, 14.0, -0.6), lens=30.0))


# ------------------------------------------------------------------------------------ image helpers (numpy)
def load_px(p):
    im = bpy.data.images.load(p, check_existing=True)
    return np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)


def save_px(S, out):
    img = bpy.data.images.new(os.path.basename(out), S.shape[1], S.shape[0], alpha=False); img.pixels = S.ravel().tolist()
    img.filepath_raw = out; img.file_format = "PNG"; img.save(); return out


def shrink(px, cw, ch):
    ys = (np.arange(ch) * px.shape[0] / ch).astype(int); xs = (np.arange(cw) * px.shape[1] / cw).astype(int)
    return px[ys][:, xs]


def contact_sheet(paths, out, cols=4, cell=(640, 360)):
    cw, ch = cell; rows = (len(paths) + cols - 1) // cols
    S = np.zeros((rows * ch, cols * cw, 4), np.float32); S[:, :, 3] = 1.0; S[:, :, :3] = 0.12
    for i, p in enumerate(paths):
        r, c = rows - 1 - i // cols, i % cols
        S[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = shrink(load_px(p), cw, ch)
    return save_px(S, out)


side = np.concatenate([shrink(load_px(os.path.join(OUT, "preset_%s.png" % p)), 853, 480) for p in ("clean", "light_wear", "heavy_wear")], axis=1)
renders.append(save_px(side, os.path.join(OUT, "wear_presets_side_by_side.png")))
log("wear presets side by side:", renders[-1])


# ------------------------------------------------------------------------------------ tiles
TILES = os.path.join(OUT, "tiles")
t = time.time()
materials.apply_material_preset("light_wear")
baked = materials.bake_tiles(TILES, res=1024, samples=16 if not QUICK else 4)
log("bake_tiles: %d materials in %.0fs" % (len(baked), time.time() - t))
assert len(baked) == len(materials.MATERIAL_NAMES), baked
assert "metallic" in baked[MRS + "PoleMetal"]
for mname, paths in baked.items():
    for key, p in paths.items():
        assert os.path.exists(p) and os.path.getsize(p) > 1000, p
    px = load_px(paths["albedo"])[:, :, :3]
    seam_lr = float(np.abs(px[:, 0] - px[:, -1]).mean()); seam_tb = float(np.abs(px[0] - px[-1]).mean())
    inner = float(np.abs(px[:, 1:] - px[:, :-1]).mean())
    log("seam %-16s left/right %.4f top/bottom %.4f (neighbour-column mean %.4f)" % (mname, seam_lr, seam_tb, inner))
    assert seam_lr < max(0.06, 4.0 * inner) and seam_tb < max(0.06, 4.0 * inner), (mname, seam_lr, seam_tb, inner)
    assert px.mean() > 0.02, (mname, "black albedo bake")
CHECK_X0 = 400.0
for i, (mname, paths) in enumerate(baked.items()):
    bm = materials.baked_material("Check_" + mname, paths, repeat=2.0)
    x = CHECK_X0 + (i % 5) * 9.0; y = (i // 5) * 9.0
    me = bpy.data.meshes.new("Check_" + mname); me.from_pydata([(x - 4, y - 4, 0), (x + 4, y - 4, 0), (x + 4, y + 4, 0), (x - 4, y + 4, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for j, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))): uv.data[j].uv = co
    me.materials.append(bm); ob = bpy.data.objects.new("Check_" + mname, me); sc.collection.objects.link(ob)
renders.append(render(os.path.join(OUT, "seam_check_2x2.png"), eye=(CHECK_X0 + 18.0, -22.0, 30.0), target=(CHECK_X0 + 18.0, 4.5, 0.0), lens=30.0, res=(1600, 900)))
renders.append(render(os.path.join(OUT, "seam_check_close.png"), eye=(CHECK_X0 + 2.0, -6.5, 3.0), target=(CHECK_X0, 0.0, 0.0), lens=35.0))

sheet = contact_sheet(renders, os.path.join(OUT, "contact_sheet.png"))
log("contact sheet:", sheet, "(%d renders)" % len(renders))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "materials_demo.blend"), copy=True)
log("TOTAL %.0fs" % (time.time() - T0))
print("MATERIALS_TEST OK")
