"""Headless validation of the Mert Road Studio signage factories (mrs/signage.py).

    blender --background --factory-startup --python tools/roads/tests/signage_test.py [-- --quick]

Builds the hidden library (MRS_Signage) and the visible demo grid (MRS_SignageDemo), checks lens materials /
State nodes, head child objects, sign metadata + editable legends + bake_sign_text, dimensions, then renders a
catalogue with EEVEE to tmp/roads/signage/*.png (signs front view at 6 m, signals GREEN lit then RED lit, the
direction board close-up, a lens lit-vs-unlit pair whose pixels are compared) and saves signage.blend.
"""
import math, os, sys, time, traceback
ROOT = "C:/GodotProjects/delivery-simulator-2026"
sys.path.insert(0, ROOT + "/tools/roads")
import bpy
import numpy as np
from mathutils import Vector
import mrs.signage as S
from mrs.nodes import MRS
from mrs import qa

OUT = os.path.join(ROOT, "tmp", "roads", "signage"); os.makedirs(OUT, exist_ok=True)
QUICK = "--quick" in sys.argv
fails = []


def check(cond, msg):
    if not cond: fails.append(msg); print("FAIL:", msg)
    return cond


def world_bbox(o):
    objs = [o] + list(o.children_recursive); pts = []
    for ob in objs:
        if ob.type == "MESH": pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        elif ob.type == "FONT":
            bpy.context.view_layer.update(); pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ---------------------------------------------------------------------------- build
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
t0 = time.time()
lib = S.build_signage()
demo = S.demo_collection()
print("build: %.1f s  library: %d signs / %d signals / %d boards" % (time.time() - t0, len(lib["signs"]), len(lib["signals"]), len(lib["boards"])))
check(len(lib["signs"]) >= len(S.SIGN_KINDS), "library has %d signs, need >= %d" % (len(lib["signs"]), len(S.SIGN_KINDS)))
check(set(o["mrs_sign"]["kind"] for o in lib["signs"]) == set(S.SIGN_KINDS), "every sign kind must be in the library")
check(len(lib["signals"]) == len(S.SIGNAL_STYLES), "library signals: %d" % len(lib["signals"]))
check(set(o["mrs_signal"]["style"] for o in lib["signals"]) == set(S.SIGNAL_STYLES), "every signal style must be in the library")
for o in bpy.data.collections[S.LIB].objects: check(o.hide_viewport and o.hide_render, "library object %s not hidden" % o.name)
for o in bpy.data.collections[S.DEMO].objects: check(not o.hide_render, "demo object %s hidden" % o.name)

# ---------------------------------------------------------------------------- lens materials / State node convention
for key in S.LENS_RGB:
    m = bpy.data.materials.get(MRS + "Lens_" + key)
    if not check(m is not None, "material MRS_Lens_%s missing" % key): continue
    st = m.node_tree.nodes.get("State")
    if not check(st is not None and st.type == "VALUE", "MRS_Lens_%s has no Value node named State" % key): continue
    bsdf = m.node_tree.nodes.get("Lens")
    check(bsdf is not None and bsdf.type == "BSDF_PRINCIPLED", "MRS_Lens_%s: Principled node 'Lens' missing" % key)
    es = bsdf.inputs["Emission Strength"]
    check(es.is_linked and es.links[0].from_node.name == "StateStrength" and es.links[0].from_node.inputs[0].links[0].from_node == st,
          "MRS_Lens_%s: State must drive Emission Strength through StateStrength" % key)
    S.set_lens_state(m, 0.0); s0 = S.lens_strength(m); d0 = es.default_value
    S.set_lens_state(m, 1.0); s1 = S.lens_strength(m); d1 = es.default_value
    check(s0 == 0.0 and abs(s1 - S.LENS_PEAK) < 1e-6, "MRS_Lens_%s: State 0/1 gives strength %.2f/%.2f" % (key, s0, s1))
    check(d1 > d0, "MRS_Lens_%s: Emission Strength default did not change with State" % key)
    S.set_lens_state(m, 0.0)
green = bpy.data.materials[MRS + "Lens_Green"]; es_green = green.node_tree.nodes["Lens"].inputs["Emission Strength"]
before = (S.lens_strength(green), es_green.default_value); S.set_lens_state(green, 1.0); after = (S.lens_strength(green), es_green.default_value)
check(after[0] > before[0] and after[1] > before[1], "setting State=1 on MRS_Lens_Green must raise the emission strength (%s -> %s)" % (before, after))
S.set_lens_state(green, 0.0)

# ---------------------------------------------------------------------------- signals
for o in lib["signals"] + demo["signals"]:
    meta = o.get("mrs_signal")
    if not check(meta is not None, "%s has no mrs_signal" % o.name): continue
    meta = meta.to_dict(); heads = meta["heads"]
    check(meta["style"] in S.SIGNAL_STYLES and meta["faces"] == "-Y", "%s metadata: %s" % (o.name, meta))
    kids = sorted(c.name for c in o.children)
    check(kids == ["%s_head%d" % (o.name, i) for i in range(len(heads))], "%s heads %s vs children %s" % (o.name, len(heads), kids))
    for i, h in enumerate(heads):
        ho = bpy.data.objects.get("%s_head%d" % (o.name, i))
        if not check(ho is not None and ho.parent == o and ho.type == "MESH", "%s head %d missing / not parented" % (o.name, i)): continue
        check(h["lenses"] == S.HEAD_LENSES[h["kind"]] and h["mesh_names"] == [ho.data.name], "%s head %d metadata %s" % (o.name, i, h))
        names = [m.name for m in ho.data.materials if m]
        check(all((MRS + "Lens_" + k) in names for k in h["lenses"]), "%s head %d lacks lens materials: %s" % (o.name, i, names))
        check(any(m.name == MRS + "SignalHousing" for m in ho.data.materials if m), "%s head %d has no MRS_SignalHousing" % (o.name, i))
        hm = ho.get("mrs_signal_head"); check(hm is not None and hm["kind"] == h["kind"], "%s head %d: mrs_signal_head" % (o.name, i))
        # lens faces look towards -Y: the lens material's faces have an outward normal with y < 0 somewhere
        li = [j for j, m in enumerate(ho.data.materials) if m and m.get("mrs_lens")]
        ny = [p.normal.y for p in ho.data.polygons if p.material_index in li]
        check(ny and min(ny) < -0.9, "%s head %d: no lens face pointing -Y" % (o.name, i))
        me = ho.data; used = {v for p in me.polygons for v in p.vertices}
        check(len(used) == len(me.vertices), "%s head %d loose verts" % (o.name, i)); check(bool(me.uv_layers), "%s head %d no UV" % (o.name, i))
    lo, hi = world_bbox(o); hgt = hi.z - o.matrix_world.translation.z
    check(3.5 <= hgt <= 6.5, "%s height %.2f not in 3.5..6.5" % (o.name, hgt))
    if meta["style"] == "mast_arm":
        xs = [(o.matrix_world @ v.co).x - o.matrix_world.translation.x for v in o.data.vertices]
        check(abs(max(xs) - meta["arm_length"]) <= 0.2, "%s arm reaches %.2f, want %.2f" % (o.name, max(xs), meta["arm_length"]))
        check(all(h["mount"] == "hang" for h in heads if h["kind"] == "vehicle"), "%s vehicle heads should hang from the arm" % o.name)
    me = o.data; check(bool(me.uv_layers) and len(me.materials) >= 1, "%s pole mesh hygiene" % o.name)
    check(all(p.material_index < len(me.materials) for p in me.polygons), "%s material index out of range" % o.name)
on = S.set_signal_state(demo["signals"][0], "green")
check(on == {"Green", "PedGreen", "BikeGreen"} and S.lens_strength(green) == S.LENS_PEAK and S.lens_strength(bpy.data.materials[MRS + "Lens_Red"]) == 0.0, "set_signal_state green")
S.set_signal_state(demo["signals"][0], "off")
# custom signal through the public API
cs = S.make_signal("MRS_Test_Signal", "mast_arm", pole_height=5.5, arm_length=4.0, heads=("vehicle", "pedestrian"), setback=0.5, lens_size=0.3,
                   housing_color=(0.3, 0.25, 0.05))
check(cs["mrs_signal"]["setback"] == 0.5 and len(cs.children) == 2 and "SignalHousing_" in cs["mrs_signal"]["housing"], "custom signal")
xs = [v.co.x for v in cs.data.vertices]; check(abs(max(xs) - 4.0) <= 0.2, "custom arm reaches %.2f" % max(xs))
S._remove_tree(cs)

# ---------------------------------------------------------------------------- signs
textual = 0
for o in lib["signs"] + demo["signs"] + lib["boards"] + demo["boards"]:
    meta = o.get("mrs_sign")
    if not check(meta is not None, "%s has no mrs_sign" % o.name): continue
    meta = meta.to_dict()
    check(meta["kind"] in S.SIGN_KINDS and "text" in meta and "value" in meta, "%s metadata %s" % (o.name, meta))
    fonts = [c for c in o.children if c.type == "FONT"]
    for c in fonts:
        check(c.name.startswith(o.name + "_text") or c.name.startswith(o.name + "_dist"), "%s legend child badly named: %s" % (o.name, c.name))
        check(c.data.body.strip() != "" and len(c.data.materials) == 1, "%s legend %s empty / no material" % (o.name, c.name))
    if meta.get("legends"):
        check(any(c.name == o.name + "_text" or c.name == o.name + "_text0" for c in fonts), "%s: primary legend child <name>_text missing" % o.name)
        check(len(fonts) >= len(meta["legends"]), "%s: %d FONT children for %d legends" % (o.name, len(fonts), len(meta["legends"])))
        textual += 1
    lo, hi = world_bbox(o); hgt = hi.z - o.matrix_world.translation.z
    if meta["kind"] == "direction_board" and o in lib["boards"] + demo["boards"]:
        check(3.5 <= hgt <= 5.0 and lo.z - o.matrix_world.translation.z > -0.01, "%s board height %.2f" % (o.name, hgt))
    else:
        check(2.0 <= hgt <= 3.2, "%s height %.2f not in 2.0..3.2" % (o.name, hgt))
    me = o.data; used = {v for p in me.polygons for v in p.vertices}
    check(len(used) == len(me.vertices), "%s loose verts" % o.name); check(bool(me.uv_layers), "%s no UV" % o.name)
    check(all(p.material_index < len(me.materials) for p in me.polygons), "%s material index out of range" % o.name)
    check(any(m and m.name.startswith(MRS + "SignFace_") for m in me.materials), "%s has no MRS_SignFace material" % o.name)
check(textual >= 12, "only %d signs carry legends" % textual)
# legend readability: the text must sit proud of the plate front (y > plate face) and face +Y
for o in demo["signs"]:
    for c in o.children:
        if c.type != "FONT": continue
        ang = (c.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        face = Vector((0, 1, 0)) if "StreetNameDouble" not in o.name or c.name.endswith("_text") else Vector((1, 0, 0))
        check(ang.dot(face) > 0.99, "%s legend %s extrudes along %s, not %s" % (o.name, c.name, tuple(round(v, 2) for v in ang), tuple(face)))
# bake_sign_text on the library signs
for o in lib["signs"] + lib["boards"]:
    names = [c.name for c in o.children if c.type == "FONT"]
    baked = S.bake_sign_text(o)
    check(not [c for c in o.children if c.type == "FONT"], "%s still has FONT children after bake" % o.name)
    check(sorted(b.name for b in baked) == sorted(names), "%s baked names %s vs %s" % (o.name, [b.name for b in baked], names))
    for b in baked:
        check(b.type == "MESH" and len(b.data.polygons) > 0 and b.parent == o and len(b.data.materials) >= 1, "%s baked legend %s is not a usable mesh" % (o.name, b.name))
    check(o["mrs_sign"].get("text_baked"), "%s metadata not marked baked" % o.name)
# custom signs through the public API
for kw in (dict(kind="speed_limit", value=30), dict(kind="street_name", text="OAK LANE", double=True), dict(kind="stop", face_color=(0.1, 0.1, 0.6), size=1.0),
           dict(kind="direction_board", text="HARBOUR|3 km\nSTATION|800 m\nUNIVERSITY|2 km", value="left"), dict(kind="one_way", text="left")):
    try:
        o = S.make_sign("MRS_Test_Sign", **kw); lo, hi = world_bbox(o)
        check(2.0 <= hi.z <= 3.2, "custom sign %s height %.2f" % (kw, hi.z)); S._remove_tree(o)
    except Exception:
        fails.append("custom sign %s raised:\n%s" % (kw, traceback.format_exc()))
# unknown kinds / styles must raise
for bad in (lambda: S.make_sign("x", "nope"), lambda: S.make_signal("x", "nope")):
    try: bad(); fails.append("bad kind/style did not raise")
    except ValueError: pass

print("checks done: %d failures" % len(fails))
if QUICK:
    print("\n".join(fails) if fails else "SIGNAGE OK (quick)"); sys.exit(1 if fails else 0)

# ---------------------------------------------------------------------------- rendering
import bmesh
scene = bpy.context.scene
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200.0); gm = bpy.data.meshes.new("Ground"); bm.to_mesh(gm); bm.free()
ground = bpy.data.objects.new("Ground", gm); bpy.data.collections[S.DEMO].objects.link(ground); ground.location = (14, 4, -0.002)
gm.materials.append(S.pmat(MRS + "CatalogueGround", (0.42, 0.42, 0.4), 0.9, var=0.08, scale=0.3))
cam, sun = qa.ensure_camera_and_sun(scene)
sun.data.energy = 4.0
try: scene.render.engine = "BLENDER_EEVEE"
except TypeError: scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.view_settings.view_transform = "Standard"; scene.render.film_transparent = False
try: scene.eevee.use_raytracing = True
except Exception: pass
renders = []


def render(name, eye, target, lens, res=(1280, 720), samples=32, sun_yaw=150.0):
    sun.rotation_euler = (math.radians(48), 0, math.radians(sun_yaw))
    path = os.path.join(OUT, name + ".png")
    qa.render(path, eye, target, lens, res=res, samples=samples, scene=scene); print("rendered", path); renders.append(path)
    return path


def load_rgb(path):
    img = bpy.data.images.load(path); w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px); bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3]


def sheet(paths, out, cols):
    ims = [load_rgb(p) for p in paths]; h, w = ims[0].shape[:2]; rows = (len(ims) + cols - 1) // cols
    big = np.full((rows * h, cols * w, 4), (0.12, 0.12, 0.12, 1.0), dtype=np.float32)
    for i, im in enumerate(ims):
        r, c = divmod(i, cols); r = rows - 1 - r        # Blender rows run bottom-up; keep reading order top-left first
        big[r * h:(r + 1) * h, c * w:(c + 1) * w, :3] = im[:h, :w]
    img = bpy.data.images.new("sheet", cols * w, rows * h); img.pixels.foreach_set(big.ravel())
    img.filepath_raw = out; img.file_format = "PNG"; img.save(); bpy.data.images.remove(img); print("sheet", out)
    return out


pos = demo["positions"]
# signs: front view at 6 m, one render each, then a contact sheet
sign_paths = []
for o in demo["signs"]:
    x, y, z = pos[o.name]; zc = o["mrs_sign"]["pole_height"]; lo, hi = world_bbox(o)
    lens = min(85.0, 6.0 * 36.0 / ((hi.x - lo.x) * 1.3 + 0.3))          # wide boards get a wider frame
    sign_paths.append(render("sign_" + o.name.replace(MRS + "Demo_Sign_", ""), (x, y + 6.0, zc), (x, y, zc), lens, res=(512, 512), samples=24, sun_yaw=150.0))
sheet(sign_paths, os.path.join(OUT, "catalogue_signs.png"), 5)
# signals: whole row from the -Y side, GREEN lit then RED lit
sig = demo["signals"]; xs = [pos[o.name][0] for o in sig]; y0 = pos[sig[0].name][1]
x_end = max(xs) + 2.0; cx = (min(xs) + x_end) / 2; span = x_end - min(xs)
for state in ("green", "red"):
    for o in sig: S.set_signal_state(o, state)
    render("catalogue_signals_%s" % state, (cx, y0 - span * 0.9, 4.0), (cx, y0, 3.4), 35.0, res=(1920, 900), samples=32, sun_yaw=30.0)
    render("signals_closeup_%s" % state, (xs[1] + 2.5, y0 - 11.0, 3.6), (xs[1] + 2.5, y0, 3.6), 45.0, res=(1600, 900), samples=32, sun_yaw=30.0)


def lit_pixels(im, chan):
    """Pixels dominated by `chan` (0 red / 1 green): bright and clearly ahead of the other two channels."""
    o1, o2 = [c for c in range(3) if c != chan]
    return int(((im[:, :, chan] > 0.6) & (im[:, :, chan] - im[:, :, o1] > 0.3) & (im[:, :, chan] - im[:, :, o2] > 0.3)).sum())


# lens lit vs unlit on one vehicle head (pixel comparison)
px, py, _ = pos[sig[0].name]; head = bpy.data.objects[sig[0].name + "_head0"]; hz = (head.matrix_world.translation.z - 0.47)
S.set_signal_state(sig[0], "off"); off_p = render("lens_off", (px, py - 2.8, hz), (px, py - 0.23, hz), 85.0, res=(512, 512), samples=24, sun_yaw=30.0)
S.set_signal_state(sig[0], "green"); on_p = render("lens_green", (px, py - 2.8, hz), (px, py - 0.23, hz), 85.0, res=(512, 512), samples=24, sun_yaw=30.0)
S.set_signal_state(sig[0], "red"); red_p = render("lens_red", (px, py - 2.8, hz), (px, py - 0.23, hz), 85.0, res=(512, 512), samples=24, sun_yaw=30.0)
a, b, c = load_rgb(off_p), load_rgb(on_p), load_rgb(red_p)
g_off, g_on, r_off, r_on = lit_pixels(a, 1), lit_pixels(b, 1), lit_pixels(a, 0), lit_pixels(c, 0)
gain = float(((b[:, :, 1] - b[:, :, 0]) - (a[:, :, 1] - a[:, :, 0])).clip(0).sum())
print("lens check: green gain %.1f, green-dominated pixels off=%d lit=%d, red-dominated off=%d lit=%d" % (gain, g_off, g_on, r_off, r_on))
check(g_on > g_off + 1500 and gain > 50.0, "green lens does not visibly light up (gain %.1f, pixels %d -> %d)" % (gain, g_off, g_on))
check(r_on > r_off + 1500, "red lens does not visibly light up (pixels %d -> %d)" % (r_off, r_on))
for o in sig: S.set_signal_state(o, "off")
# direction board close-up + overview
bx, by, _ = pos[demo["boards"][0].name]; bm_ = demo["boards"][0]["mrs_sign"]; bz = bm_["clearance"] + bm_["height"] / 2
render("catalogue_direction_board", (bx + 0.5, by + 7.5, 3.0), (bx, by, bz), 45.0, res=(1600, 900), samples=32, sun_yaw=150.0)
render("catalogue_overview", (18.0, -34.0, 14.0), (16.0, 6.0, 2.0), 30.0, res=(1920, 1080), samples=32, sun_yaw=120.0)

# ---------------------------------------------------------------------------- save
blend = os.path.join(OUT, "signage.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True); print("saved", blend)
print("renders:", len(renders))
if fails:
    print("\nFAILURES (%d):\n  " % len(fails) + "\n  ".join(fails)); sys.exit(1)
print("SIGNAGE OK")
