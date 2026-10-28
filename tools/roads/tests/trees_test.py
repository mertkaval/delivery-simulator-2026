"""Mert Road Studio tree validation (headless):

    blender --background --factory-startup --python tools/roads/tests/trees_test.py [-- --quick]

Builds the Tree_Variants group, the bark / foliage shaders and every baked variant, then asserts counts,
triangle budgets, dimensions, UVs, materials and deterministic output, and renders with EEVEE:
closeup_<species>.png (6 m, 50 mm), street_row.png (8 trees, 10 m spacing, eye at 1.7 m),
catalogue.png (+ pair_<species>.png: Full next to LOD1), distance_150m.png (Full left, LOD1 right)
-> tmp/roads/trees/. Ends with a triangle-count summary and "TREES_TEST OK".
"""
import math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
import bpy
import numpy as np
from mathutils import Vector
from mrs import trees as TR, qa
from mrs.nodes import MRS

OUT = os.path.join(ROOT, "tmp", "roads", "trees"); os.makedirs(OUT, exist_ok=True)
QUICK = "--quick" in sys.argv
T0 = time.time()
fails = []


def log(*a): print("[trees_test]", *a, flush=True)


def check(cond, msg):
    if not cond: fails.append(msg); log("FAIL:", msg)


# ------------------------------------------------------------------------------------ build
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
t = time.time()
cols = TR.build_trees()
log("build_trees: %.1fs" % (time.time() - t))
g = bpy.data.node_groups.get(TR.GROUP); check(g is not None, "Tree_Variants group missing")
inputs = [i.name for i in g.interface.items_tree if getattr(i, "in_out", "") == "INPUT"]
check(inputs == TR.INPUT_NAMES, "group inputs %s" % inputs)
panels = [i.name for i in g.interface.items_tree if getattr(i, "item_type", "") == "PANEL"]
check(panels == ["Trunk", "Branches", "Foliage", "Variation", "Detail", "Materials"], "panels %s" % panels)
check(len([n for n in g.nodes if n.bl_idname == "NodeFrame"]) >= 6, "group is not framed")
log("group: %d nodes, inputs %s" % (len(g.nodes), inputs))
for grp, names in (("BarkShader", ["Bark Color", "Crevice Color", "Scale", "Crack Depth", "Bump Strength", "Lenticels", "Moss"]),
                   ("FoliageShader", ["Leaf Color", "Leaf Color 2", "Tint Variation", "Translucency", "Leaf Shape", "Alpha Clip", "Autumn"])):
    ng = bpy.data.node_groups.get(MRS + grp); check(ng is not None, grp + " missing")
    if ng:
        have = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]
        check(all(n in have for n in names), "%s inputs %s" % (grp, have))
        check(any(n.type == "ATTRIBUTE" and n.attribute_name == "foliage_tint" for n in ng.nodes) or grp == "BarkShader", grp + " does not read foliage_tint")
for nm in list(TR.BARK_VARIANTS) + list(TR.FOLIAGE_VARIANTS):
    m = bpy.data.materials.get(MRS + nm); check(m is not None, "material missing " + nm)
    if m:
        gn = m.node_tree.nodes.get("MRS"); check(gn is not None and gn.type == "GROUP", nm + " has no MRS group node")
        if nm.startswith("Foliage"): check(m.surface_render_method == "DITHERED", nm + " not alpha-clipped (dithered)")

# ------------------------------------------------------------------------------------ counts / budgets / hygiene
check(len(cols["Trees"].objects) == 12, "MRS_Trees has %d objects" % len(cols["Trees"].objects))
check(len(cols["Trees_LOD1"].objects) == 12, "MRS_Trees_LOD1 has %d objects" % len(cols["Trees_LOD1"].objects))
check(len(cols["Shrubs"].objects) == 2 and len(cols["Shrubs_LOD1"].objects) == 2, "shrub collections")
check(all(o.name.startswith("MRS_Tree_") for o in cols["Trees"].objects), "tree names must start with MRS_Tree_")
species = sorted({o.name.split("_")[2] for o in cols["Trees"].objects})
check(species == ["Birch", "Maple", "Oak", "Palm", "Pine", "Poplar"], "species %s" % species)
report = []
for key, lod_key, is_tree in (("Trees", "Trees_LOD1", True), ("Shrubs", "Shrubs_LOD1", False)):
    for o in cols[key].objects:
        me = o.data; lod = cols[lod_key].objects.get(o.name + "_LOD1")
        check(lod is not None, "no LOD1 for " + o.name)
        tri = TR.tri_count(me); ltri = TR.tri_count(lod.data) if lod else 0
        d = o.dimensions; zs = [v.co.z for v in me.vertices]
        lo, hi = (1500, 8000) if is_tree else (800, 8000)
        check(lo <= tri <= hi, "%s: %d triangles (budget %d-%d)" % (o.name, tri, lo, hi))
        check(ltri <= 2000 and ltri <= 0.25 * tri, "%s_LOD1: %d triangles (full %d, limit min(2000, 25 %%))" % (o.name, ltri, tri))
        if is_tree:
            check(6.0 <= d.z <= 18.0, "%s: height %.1f" % (o.name, d.z))
            check(4.0 <= max(d.x, d.y) <= 12.5, "%s: canopy %.1f x %.1f" % (o.name, d.x, d.y))
        else:
            check(1.2 <= d.z <= 4.0 and 1.5 <= max(d.x, d.y) <= 6.0, "%s: size %.1f x %.1f x %.1f" % (o.name, d.x, d.y, d.z))
        check(-0.1 <= min(zs) <= 0.1, "%s: base z %.2f (origin must be at the trunk base)" % (o.name, min(zs)))
        for ob in (o, lod):
            if ob is None: continue
            m2 = ob.data
            check("UVMap" in m2.uv_layers, ob.name + ": no UVMap")
            mats = [m for m in m2.materials if m]
            check(len(mats) == 2 and any(m.name.startswith(MRS + "Bark") for m in mats) and any(m.name.startswith(MRS + "Foliage") for m in mats), "%s: materials %s" % (ob.name, [m.name for m in mats]))
            check(all(p.material_index < len(m2.materials) for p in m2.polygons), ob.name + ": material index out of range")
            ft = m2.attributes.get("foliage_tint"); check(ft is not None and ft.domain == "POINT", ob.name + ": foliage_tint attribute missing")
            if ft: check(len({round(x.value, 3) for x in ft.data}) >= 6, ob.name + ": foliage_tint has too few distinct values")
            check(m2.attributes.get("leaf_card") is not None, ob.name + ": leaf_card attribute missing")
            check(ob.hide_viewport and ob.hide_render, ob.name + ": library object must be hidden")
            check(not any(p.area < 1e-10 for p in m2.polygons), ob.name + ": zero-area face")
            # bark UVs: u spans the circumference, v is metres along the trunk
            uv = m2.uv_layers["UVMap"].data; bark = {i for i, m in enumerate(m2.materials) if m and m.name.startswith(MRS + "Bark")}
            us = [uv[l].uv.x for p in m2.polygons if p.material_index in bark for l in p.loop_indices]
            vs = [uv[l].uv.y for p in m2.polygons if p.material_index in bark for l in p.loop_indices]
            check(us and min(us) >= -0.01 and max(us) <= 1.6 and max(vs) > 0.5 * d.z * 0.5, "%s: bark UV range u %.2f..%.2f v %.2f..%.2f" % (ob.name, min(us or [0]), max(us or [0]), min(vs or [0]), max(vs or [0])))
        report.append((o.name, tri, ltri, len(me.vertices), tuple(round(x, 1) for x in d)))

# ------------------------------------------------------------------------------------ determinism
def signature(me):
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    return (len(me.vertices), len(me.polygons), tuple(round(v, 4) for v in (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))))


p = TR.variant_params("Oak", {"Seed": 11})
a = TR.realize_tree(p, "Full", "det_a"); b = TR.realize_tree(p, "Full", "det_b"); c = TR.realize_tree(TR.variant_params("Oak", {"Seed": 12}), "Full", "det_c")
sa, sb, scs = signature(a), signature(b), signature(c)
check(sa == sb, "same seed gave different meshes: %s vs %s" % (sa, sb))
check(sa != scs, "different seed gave the same mesh: %s" % (sa,))
log("determinism: seed 11 twice ->", sa == sb, "; seed 12 differs ->", sa != scs)
for me in (a, b, c): bpy.data.meshes.remove(me)

print("\n  %-22s %6s %6s %6s  %s" % ("variant", "tris", "LOD1", "verts", "size (m)"))
for r in report: print("  %-22s %6d %6d %6d  %.1f x %.1f x %.1f" % (r[0], r[1], r[2], r[3], *r[4]))
if fails and QUICK:
    print("\nFAILURES:\n  " + "\n  ".join(fails)); sys.exit(1)

# ------------------------------------------------------------------------------------ showroom
sc = bpy.context.scene
show = bpy.data.collections.get("Showroom") or bpy.data.collections.new("Showroom")
if show.name not in sc.collection.children: sc.collection.children.link(show)
placed = []


def place(name, loc, rot=0.0, lod=False):
    src = bpy.data.objects[name + ("_LOD1" if lod else "")]
    o = bpy.data.objects.new(src.name + ".show", src.data); show.objects.link(o); o.location = loc; o.rotation_euler = (0, 0, rot)
    placed.append(o); return o


def clear():
    for o in placed: bpy.data.objects.remove(o)
    placed.clear()


ground_me = bpy.data.meshes.new("Ground"); ground_me.from_pydata([(-600, -600, 0), (600, -600, 0), (600, 600, 0), (-600, 600, 0)], [], [(0, 1, 2, 3)])
ground = bpy.data.objects.new("Ground", ground_me); show.objects.link(ground)
gm = bpy.data.materials.new("Showroom_Ground"); gm.use_nodes = True; nt = gm.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); bsdf.inputs["Roughness"].default_value = 0.95
tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.6; nz.inputs["Detail"].default_value = 6.0
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (0.09, 0.14, 0.04, 1); ramp.color_ramp.elements[1].color = (0.22, 0.26, 0.09, 1)
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"]); nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
ground_me.materials.append(gm)
# a dark asphalt strip for the street shot
road_me = bpy.data.meshes.new("Road"); road_me.from_pydata([(2, -40, 0.01), (10, -40, 0.01), (10, 120, 0.01), (2, 120, 0.01)], [], [(0, 1, 2, 3)])
road = bpy.data.objects.new("Road", road_me); show.objects.link(road)
rm = bpy.data.materials.new("Showroom_Road"); rm.use_nodes = True; next(n for n in rm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.08, 0.08, 0.085, 1)
road_me.materials.append(rm)

cam, sun = qa.ensure_camera_and_sun(sc)
w = sc.world; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld"); nt.links.new(bg.outputs[0], out.inputs[0])
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
cr.elements[0].position = 0.0; cr.elements[0].color = (0.16, 0.15, 0.12, 1)
e1 = cr.elements.new(0.5); e1.color = (0.62, 0.68, 0.78, 1)
cr.elements[2].position = 0.85; cr.elements[2].color = (0.18, 0.32, 0.65, 1)
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1.0; mr.inputs["From Max"].default_value = 1.0
nt.links.new(sep.outputs[2], mr.inputs["Value"]); nt.links.new(mr.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.9
sun.data.energy = 4.5; sun.data.color = (1.0, 0.96, 0.88); sun.data.angle = math.radians(1.5); sun.rotation_euler = (math.radians(48), 0, math.radians(-50))


def render(name, eye, target, lens=35.0, res=(1280, 720), samples=32):
    path = os.path.join(OUT, name + ".png")
    qa.look(cam, eye, target, lens)
    r = sc.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    ee = sc.eevee; ee.taa_render_samples = samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 4), ("use_fast_gi", True)):
        if hasattr(ee, attr):
            try: setattr(ee, attr, val)
            except Exception: pass
    sc.view_settings.view_transform = "AgX"; sc.view_settings.exposure = 0.1
    r.resolution_x, r.resolution_y = res; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.filepath = path
    t = time.time(); bpy.ops.render.render(write_still=True)
    log("render %s (%.1fs)" % (os.path.basename(path), time.time() - t))
    return path


renders = []
# (a) close-ups: 6 m from the trunk, 50 mm
for sp in ("Oak", "Birch", "Pine"):
    place("MRS_Tree_%s_A" % sp, (0, 0, 0))
    renders.append(render("closeup_%s" % sp.lower(), (3.6, -4.8, 1.6), (0.0, 0.0, 2.2), 50.0))
    clear()
# (b) street-level row: 8 trees at 10 m spacing, eye at 1.7 m
row = ["MRS_Tree_Oak_A", "MRS_Tree_Maple_A", "MRS_Tree_Poplar_A", "MRS_Tree_Pine_A", "MRS_Tree_Palm_A", "MRS_Tree_Birch_A", "MRS_Tree_Oak_B", "MRS_Tree_Maple_B"]
for i, nm in enumerate(row): place(nm, (0, 10.0 * i, 0), rot=0.7 * i)
place("MRS_Shrub_Round", (3.0, -4.0, 0)); place("MRS_Shrub_Hedge", (-3.5, 3.0, 0))
renders.append(render("street_row", (7.5, -14.0, 1.7), (0.0, 30.0, 5.0), 28.0, res=(1600, 900)))
renders.append(render("street_row_side", (-26.0, 30.0, 1.7), (0.0, 36.0, 6.0), 35.0, res=(1600, 900)))
clear()
# (c) catalogue: 12 variants with the LOD1 beside each, two rows of six
names = [v[0] for v in TR.VARIANTS]
for i, nm in enumerate(names):
    r_, c_ = divmod(i, 6); x = c_ * 18.0; y = -r_ * 45.0
    place(nm, (x, y, 0)); place(nm, (x + 8.0, y, 0), lod=True)
place("MRS_Shrub_Round", (108.0, 0.0, 0)); place("MRS_Shrub_Round", (112.0, 0.0, 0), lod=True)
place("MRS_Shrub_Hedge", (108.0, -45.0, 0)); place("MRS_Shrub_Hedge", (113.0, -45.0, 0), lod=True)
renders.append(render("catalogue", (55.0, -175.0, 40.0), (55.0, -20.0, 7.0), 40.0, res=(2400, 1200), samples=24))
clear()
for sp in ("Oak", "Maple", "Poplar", "Pine", "Palm", "Birch"):
    place("MRS_Tree_%s_A" % sp, (0, 0, 0)); place("MRS_Tree_%s_A" % sp, (12.0, 0, 0), lod=True); place("MRS_Tree_%s_B" % sp, (26.0, 0, 0))
    h = bpy.data.objects["MRS_Tree_%s_A" % sp].dimensions.z
    renders.append(render("pair_%s" % sp.lower(), (13.0, -h * 2.9 - 8.0, h * 0.45), (13.0, 0.0, h * 0.5), 35.0, samples=24))
    clear()
place("MRS_Shrub_Round", (0, 0, 0)); place("MRS_Shrub_Round", (5.0, 0, 0), lod=True); place("MRS_Shrub_Hedge", (11.0, 0, 0)); place("MRS_Shrub_Hedge", (17.0, 0, 0), lod=True)
renders.append(render("pair_shrubs", (8.5, -16.0, 2.6), (8.5, 0.0, 1.2), 35.0, samples=24)); clear()
# (d) 150 m: Full on the left, LOD1 on the right, same six species
for i, sp in enumerate(("Oak", "Maple", "Poplar", "Pine", "Palm", "Birch")):
    place("MRS_Tree_%s_A" % sp, (-44.0 + 7.0 * i, 150.0, 0)); place("MRS_Tree_%s_A" % sp, (9.0 + 7.0 * i, 150.0, 0), lod=True)
renders.append(render("distance_150m", (0.0, 0.0, 1.7), (0.0, 150.0, 6.0), 55.0, res=(1920, 800), samples=24))
clear()


def contact_sheet(paths, out, cols=4, cell=(640, 360)):
    cw, ch = cell; rows = (len(paths) + cols - 1) // cols
    S = np.zeros((rows * ch, cols * cw, 4), np.float32); S[:, :, 3] = 1.0; S[:, :, :3] = 0.12
    for i, p in enumerate(paths):
        im = bpy.data.images.load(p, check_existing=True)
        px = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)
        ys = (np.arange(ch) * im.size[1] / ch).astype(int); xs = (np.arange(cw) * im.size[0] / cw).astype(int)
        r, c = rows - 1 - i // cols, i % cols
        S[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = px[ys][:, xs]
    img = bpy.data.images.new("ContactSheet", cols * cw, rows * ch, alpha=False); img.pixels = S.ravel().tolist()
    img.filepath_raw = out; img.file_format = "PNG"; img.save(); return out


log("contact sheet:", contact_sheet(renders, os.path.join(OUT, "contact_sheet.png")))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "trees_demo.blend"), copy=True)
log("TOTAL %.0fs" % (time.time() - T0))
if fails:
    print("\nFAILURES:\n  " + "\n  ".join(fails)); print("RESULT: FAIL"); sys.exit(1)
print("RESULT: PASS")
print("TREES_TEST OK")
