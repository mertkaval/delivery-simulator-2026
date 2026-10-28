"""Mert Road Studio materials validation (headless):

    blender --background --factory-startup --python tools/roads/tests/materials_test.py [-- --quick]

Builds every MRS material, asserts group / material / input names, applies every preset, renders an EEVEE
demo (12 x 40 m road slab with lat / along / kind / UVMap attributes, paint lines, sidewalks, embankment)
per Surface Type and per preset, a shader-ball row, bakes the tiles at 1024 px into tmp/roads/materials/tiles/
and renders a 2x2 seam check. Output: tmp/roads/materials/*.png + contact_sheet.png.
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
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); LOG.append(s); print("[materials_test]", s, flush=True)


# ------------------------------------------------------------------------------------ build + assert
mats = materials.build_materials(); extra = materials.extra_materials()
assert set(mats) == {"Asphalt", "Paint", "Concrete"}, mats
assert len(extra) == 3
REQUIRED = {
    "AsphaltShader": ["Asphalt Scale", "Asphalt Roughness", "Color Variation", "Patch Amount", "Wetness", "Base Color", "Bump Strength",
                      "Surface Type", "Cracks", "Tire Wear", "Lane Width", "Edge Dirt", "Half Width", "Slab Size", "Use UV", "Tile Size"],
    "PaintShader": ["Paint Wear", "Wetness", "Paint Color", "Asphalt Scale", "Bump Strength", "Yellow", "Use UV", "Tile Size"],
    "ConcreteShader": ["Concrete Variation", "Slab Size", "Wetness", "Base Color", "Bump Strength", "Asphalt Scale", "Rust Streaks", "Grime", "Use UV", "Tile Size"],
    "EmbankmentShader": ["Grass Color", "Dirt Color", "Rockiness", "Use UV", "Tile Size"],
}
for grp, names in REQUIRED.items():
    ng = bpy.data.node_groups.get(MRS + grp); assert ng is not None, grp
    have = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]
    missing = [n for n in names if n not in have]; assert not missing, (grp, missing)
    outs = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "OUTPUT"]; assert outs == ["BSDF"], outs
    log(grp, len(ng.nodes), "nodes; inputs:", have)
for suffix in materials.MATERIAL_NAMES:
    m = bpy.data.materials.get(MRS + suffix); assert m is not None, suffix
    g = [n for n in m.node_tree.nodes if n.type == "GROUP"]; assert len(g) == 1 and g[0].name == "MRS", (suffix, [n.name for n in g])
    out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"); assert out.inputs["Surface"].links[0].from_node.name == "MRS"
for p in materials.MATERIAL_PRESETS: materials.apply_material_preset(p)
materials.apply_material_preset("wet")
for mat, node in materials.mrs_nodes(): assert abs(node.inputs["Wetness"].default_value - 0.85) < 1e-6, mat.name
materials.apply_material_preset("old_village")
assert abs(bpy.data.materials[MRS + "Asphalt"].node_tree.nodes["MRS"].inputs["Surface Type"].default_value - 4.0) < 1e-6
assert abs(bpy.data.materials[MRS + "BikeLane"].node_tree.nodes["MRS"].inputs["Surface Type"].default_value - 1.0) < 1e-6
assert abs(bpy.data.materials[MRS + "Paint"].node_tree.nodes["MRS"].inputs["Yellow"].default_value - 0.85) < 1e-6
materials.apply_material_preset("dry")
log("presets:", list(materials.MATERIAL_PRESETS))


# ------------------------------------------------------------------------------------ demo geometry
def mesh_obj(name, verts, faces, mat, kind, smooth=False):
    """Mesh with UVMap = (x, y) metres, point attrs lat = x, along = y, face attr kind."""
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    lat = me.attributes.new("lat", "FLOAT", "POINT"); lat.data.foreach_set("value", [v[0] for v in verts])
    al = me.attributes.new("along", "FLOAT", "POINT"); al.data.foreach_set("value", [v[1] for v in verts])
    k = me.attributes.new("kind", "FLOAT", "FACE"); k.data.foreach_set("value", [float(kind)] * len(faces))
    uv = me.uv_layers.new(name="UVMap")
    for lp in me.loops: uv.data[lp.index].uv = (verts[lp.vertex_index][0], verts[lp.vertex_index][1])
    me.materials.append(mat)
    for p in me.polygons: p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob


def grid(name, x0, x1, y0, y1, z, nx, ny, mat, kind):
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx; y = y0 + (y1 - y0) * j / ny
            verts.append((x, y, z(x, y) if callable(z) else z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i; faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    return mesh_obj(name, verts, faces, mat, kind)


def strip(name, profile, y0, y1, ny, mat, kind, smooth=False):
    """profile: [(x, z), ...] swept along y."""
    verts, faces = [], []
    n = len(profile)
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        for (x, z) in profile: verts.append((x, y, z))
    for j in range(ny):
        for i in range(n - 1):
            a = j * n + i; faces.append((a, a + 1, a + n + 1, a + n))
    return mesh_obj(name, verts, faces, mat, kind, smooth)


L = 40.0
M = lambda s: bpy.data.materials[MRS + s]
sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o)
road = grid("Demo_Road", -6, 6, 0, L, 0.0, 12, 40, M("Asphalt"), 0)
# paint: dashed lane lines at +-1.8 m (3 m / 6 m), solid edge lines at +-5.5 m
pv, pf = [], []
def quad(x0, x1, y0, y1, z=0.003):
    b = len(pv); pv.extend([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]); pf.append((b, b + 1, b + 2, b + 3))
for x in (-1.8, 1.8):
    y = 1.0
    while y + 3.0 <= L: quad(x - 0.06, x + 0.06, y, y + 3.0); y += 9.0
for x in (-5.5, 5.5): quad(x - 0.075, x + 0.075, 0, L)
quad(-3.0, 3.0, 24.0, 24.6)  # a stop bar
paint = mesh_obj("Demo_Paint", pv, pf, M("Paint"), 1)
for s in (1, -1):
    strip("Demo_Sidewalk%+d" % s, [(6 * s, 0.0), (6 * s, 0.15), (8.5 * s, 0.15)], 0, L, 8, M("Concrete"), 2)
    strip("Demo_Embankment%+d" % s, [(8.5 * s, 0.15), (9.6 * s, 0.05), (13.0 * s, -2.1), (14.5 * s, -2.4), (24 * s, -2.6)], 0, L, 8, M("Embankment"), 4)
# a concrete structure wall at the far end (rust streaks / grime by object Z)
wall = mesh_obj("Demo_Wall", [(-24, L + 3, -2.6), (24, L + 3, -2.6), (24, L + 3, 4.0), (-24, L + 3, 4.0)], [(0, 1, 2, 3)], M("Structure"), 3)
asph = M("Asphalt").node_tree.nodes["MRS"].inputs
asph["Lanes"].default_value = 3.0; asph["Lane Width"].default_value = 3.6; asph["Half Width"].default_value = 6.0

# shader balls: six spheres on a grey floor, parked far off to the side of the road demo
BALL_X0 = 200.0
floor = grid("Demo_BallFloor", BALL_X0 - 12, BALL_X0 + 12, -8, 12, -1.0, 2, 2, bpy.data.materials.new("Demo_Floor"), 0)
floor.data.materials[0].diffuse_color = (0.3, 0.3, 0.3, 1); floor.data.materials[0].use_nodes = True
floor.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.25, 0.25, 1)
balls = []
for i, suffix in enumerate(materials.MATERIAL_NAMES):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.9, segments=64, ring_count=32, location=(BALL_X0 - 7.5 + 3.0 * i, 0, -0.1))
    b = bpy.context.active_object; b.name = "Ball_" + suffix; b.data.materials.append(M(suffix))
    for p in b.data.polygons: p.use_smooth = True
    balls.append(b)
    # a 2.4 x 2.4 m tile behind each ball so the flat read is visible too
    grid("Tile_" + suffix, BALL_X0 - 7.5 + 3.0 * i - 1.2, BALL_X0 - 7.5 + 3.0 * i + 1.2, 1.6, 4.0, -0.99, 1, 1, M(suffix), 0)


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
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast" if "AgX - Medium High Contrast" in [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else "None"
    sc.view_settings.exposure = 0.0
    r.resolution_x, r.resolution_y = res; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.filepath = os.path.abspath(path)
    t = time.time(); bpy.ops.render.render(write_still=True)
    log("render %s (%.1fs)" % (os.path.basename(path), time.time() - t))
    return r.filepath


# sky-coloured world with a gentle horizon gradient
w = bpy.data.worlds.get(MRS + "World") or bpy.data.worlds.new(MRS + "World"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld"); nt.links.new(bg.outputs[0], out.inputs[0])
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
cr.elements[0].position = 0.0; cr.elements[0].color = (0.14, 0.13, 0.11, 1)              # below the horizon: ground bounce
e1 = cr.elements.new(0.5); e1.color = (0.5, 0.55, 0.64, 1)                               # horizon haze (low saturation)
cr.elements[2].position = 0.85; cr.elements[2].color = (0.14, 0.26, 0.58, 1)             # zenith
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1.0; mr.inputs["From Max"].default_value = 1.0
nt.links.new(sep.outputs[2], mr.inputs["Value"]); nt.links.new(mr.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.7
sun_ob = bpy.data.objects.get(MRS + "QASun") or qa.ensure_camera_and_sun(sc)[1]
sun_ob.data.energy = 4.0; sun_ob.data.color = (1.0, 0.95, 0.86); sun_ob.data.angle = math.radians(1.5); sun_ob.rotation_euler = (math.radians(50), 0, math.radians(-35))

STREET = dict(eye=(1.2, -3.0, 1.55), target=(0.0, 16.0, -0.2), lens=30.0)
CLOSE = dict(eye=(1.6, 5.0, 1.5), target=(0.7, 7.2, 0.0), lens=45.0)
TYPES = ["fresh_asphalt", "aged_asphalt", "cracked_asphalt", "concrete_road", "cobblestone", "dirt_gravel"]
renders = []
materials.apply_material_preset("dry")
asph["Tire Wear"].default_value = 0.7; asph["Edge Dirt"].default_value = 0.6; asph["Patch Amount"].default_value = 0.3; asph["Cracks"].default_value = 0.2
for i, name in enumerate(TYPES):
    asph["Surface Type"].default_value = float(i)
    renders.append(render(os.path.join(OUT, "type%d_%s.png" % (i, name)), **STREET))
    if not QUICK or i in (1, 4):
        renders.append(render(os.path.join(OUT, "close%d_%s.png" % (i, name)), res=(1280, 720), **CLOSE))
for p in materials.MATERIAL_PRESETS:
    materials.apply_material_preset(p)
    renders.append(render(os.path.join(OUT, "preset_%s.png" % p), **STREET))
materials.apply_material_preset("dry")          # a complete state: every preset key is defined by _BASE
renders.append(render(os.path.join(OUT, "balls.png"), eye=(BALL_X0, -17.0, 5.0), target=(BALL_X0, 1.0, -0.4), lens=36.0, res=(1920, 720)))
renders.append(render(os.path.join(OUT, "wall_structure.png"), eye=(-6, L - 4, 1.6), target=(0, L + 3, 0.6), lens=35.0))
renders.append(render(os.path.join(OUT, "embankment_close.png"), eye=(17.0, 6.0, -0.6), target=(10.5, 14.0, -0.6), lens=30.0))

# ------------------------------------------------------------------------------------ tiles
TILES = os.path.join(OUT, "tiles")
t = time.time()
baked = materials.bake_tiles(TILES, res=1024, samples=16 if not QUICK else 4)
log("bake_tiles: %d materials in %.0fs" % (len(baked), time.time() - t))
assert len(baked) == 6, baked
seam_report = []
for mname, paths in baked.items():
    for key, p in paths.items():
        assert os.path.exists(p) and os.path.getsize(p) > 1000, p
    im = bpy.data.images.load(paths["albedo"], check_existing=True)
    px = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    seam_lr = float(np.abs(px[:, 0] - px[:, -1]).mean()); seam_tb = float(np.abs(px[0] - px[-1]).mean())
    inner = float(np.abs(px[:, 1:] - px[:, :-1]).mean())
    seam_report.append((mname, seam_lr, seam_tb, inner))
    log("seam %-16s left/right %.4f top/bottom %.4f (neighbour-column mean %.4f)" % (mname, seam_lr, seam_tb, inner))
    assert seam_lr < max(0.06, 4.0 * inner) and seam_tb < max(0.06, 4.0 * inner), (mname, seam_lr, seam_tb, inner)
# 2x2 seam check: each material's baked tile repeated twice on an 8 x 8 m plane, viewed from above
CHECK_X0 = 400.0
for i, (mname, paths) in enumerate(baked.items()):
    bm = materials.baked_material("Check_" + mname, paths, repeat=2.0)
    x = CHECK_X0 + (i % 3) * 9.0; y = (i // 3) * 9.0
    me = bpy.data.meshes.new("Check_" + mname); me.from_pydata([(x - 4, y - 4, 0), (x + 4, y - 4, 0), (x + 4, y + 4, 0), (x - 4, y + 4, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for j, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))): uv.data[j].uv = co
    me.materials.append(bm); ob = bpy.data.objects.new("Check_" + mname, me); sc.collection.objects.link(ob)
renders.append(render(os.path.join(OUT, "seam_check_2x2.png"), eye=(CHECK_X0 + 9.0, -14.0, 22.0), target=(CHECK_X0 + 9.0, 4.5, 0.0), lens=30.0, res=(1600, 900)))
renders.append(render(os.path.join(OUT, "seam_check_close.png"), eye=(CHECK_X0 + 2.0, -6.5, 3.0), target=(CHECK_X0, 0.0, 0.0), lens=35.0))


# ------------------------------------------------------------------------------------ contact sheet (numpy)
def contact_sheet(paths, out, cols=4, cell=(640, 360)):
    cw, ch = cell; rows = (len(paths) + cols - 1) // cols
    S = np.zeros((rows * ch, cols * cw, 4), np.float32); S[:, :, 3] = 1.0; S[:, :, :3] = 0.12
    for i, p in enumerate(paths):
        im = bpy.data.images.load(p, check_existing=True)
        px = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)
        ys = (np.arange(ch) * im.size[1] / ch).astype(int); xs = (np.arange(cw) * im.size[0] / cw).astype(int)
        small = px[ys][:, xs]
        r, c = rows - 1 - i // cols, i % cols            # image rows are bottom-up
        S[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = small
    img = bpy.data.images.new("ContactSheet", cols * cw, rows * ch, alpha=False); img.pixels = S.ravel().tolist()
    img.filepath_raw = out; img.file_format = "PNG"; img.save(); return out


sheet = contact_sheet(renders, os.path.join(OUT, "contact_sheet.png"))
log("contact sheet:", sheet, "(%d renders)" % len(renders))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "materials_demo.blend"), copy=True)
log("TOTAL %.0fs" % (time.time() - T0))
print("MATERIALS_TEST OK")
