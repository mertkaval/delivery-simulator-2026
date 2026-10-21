"""Convert the downloaded tree / plant packs (source_assets/incoming_2026_10_21/) into game-ready
landscape assets for Godot (assets/landscape/).

Run headless (never on the user's live Blender session):
  blender --background --factory-startup --python tools/prepare_landscape.py -- [--only id1,id2] [--no-qa]

Output
  assets/landscape/<tree>.glb      LOD0 of one tree species: node "LOD0" (surfaces Bark, Leaves).
  assets/landscape/trees_far.glb   every tree's LOD1 (node "<tree>_LOD1", ONE shared atlas material)
                                   plus "Impostor": a unit crossed-quad far card whose material holds
                                   the impostor atlas (2 views per species, slot from extras).
  assets/landscape/forest_pack.glb background conifer / birch card trees and understory cards
                                   (one shared atlas), trunk+branch pines.
  assets/landscape/rocks.glb       ten rocks (one material).
  assets/landscape/garden.glb      grass clumps, shrubs, potted plants, bed plants, a bed edging.
  assets/landscape/qa/*.png        QA renders (folder has .gdignore); qa/landscape_report.json metrics.

Conventions (Godot side: world/landscape/city_landscape.gd)
  * metres, Blender Z up -> Godot Y up; each asset's origin is the centre of its trunk/stem base on
    the ground (min Z = 0, a few cm sunk for rocks).
  * trees: LOD0 <= ~7k tris (bark decimated, leaves re-carded as leaf-cluster cards whose texture is
    rendered from the source leaves), LOD1 ~1.3k (one atlas for every species: leaf tile + bark
    swatch), far impostor card (2 crossed quads).
  * leaves are glTF alphaMode MASK (alpha scissor).
  * COLOR_0 carries wind data for the shared foliage shader (world/landscape/foliage_wind.gdshader):
      R = sway weight (0 at the trunk base, 1 at the crown tips),
      G = leaf flutter weight, B = flutter phase, A = crown ambient occlusion.
    The animated tree (tree_animate.glb) gets its sway weights from its wind shape keys.
  * node extras (Godot metadata): species, height, crown_radius, crown_base, trunk_radius,
    tris_lod0/lod1, far_slot, far_size.
"""
import bpy, bmesh, sys, os, math, json, time, random, tempfile
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source_assets", "incoming_2026_10_21")
OUT = os.path.join(ROOT, "assets", "landscape")
QA = os.path.join(OUT, "qa")
TMP = tempfile.mkdtemp(prefix="landscape_")
CACHE = os.path.join(ROOT, "tmp", "landscape_cache")  # per-species LOD1 / impostor data (partial rebuilds)
os.makedirs(CACHE, exist_ok=True)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def _arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) else default
    return default


ONLY = set(filter(None, (_arg("--only", "") or "").split(",")))
DO_QA = "--no-qa" not in ARGS
QA_ONLY = "--qa-only" in ARGS
os.makedirs(QA, exist_ok=True)
open(os.path.join(QA, ".gdignore"), "w").close()
REPORT = {}

# ----------------------------------------------------------------------------- species
# id, source, which tree in a multi-tree source (sorted by trunk x), target height (m),
# card counts for LOD0 / LOD1 (None = keep the source leaves for LOD0), bark budgets.
TREES = [
    {"id": "plane_tree", "src": "platano_tree.glb", "pick": 0, "trees": 1, "height": 13.0, "cards0": 2300, "cards1": 520},
    {"id": "maple_a", "src": "maple_trees.glb", "pick": 0, "trees": 3, "height": 7.5, "cards0": 1900, "cards1": 480},
    {"id": "maple_b", "src": "maple_trees.glb", "pick": 1, "trees": 3, "height": 7.0, "cards0": 1900, "cards1": 480},
    {"id": "maple_c", "src": "maple_trees.glb", "pick": 2, "trees": 3, "height": 7.8, "cards0": 1900, "cards1": 480},
    {"id": "walnut_spring", "keep": 4400, "grow_min": 1.3, "slab": 2.6, "src": "black_walnut_tree.glb", "pick": 0, "trees": 3, "height": 15.0, "cards0": 2300, "cards1": 520},
    {"id": "walnut_autumn_a", "keep": 4400, "grow_min": 1.55, "slab": 2.6, "src": "black_walnut_tree.glb", "pick": 1, "trees": 3, "height": 14.5, "cards0": 2300, "cards1": 520},
    {"id": "walnut_autumn_b", "keep": 4400, "grow_min": 1.5, "slab": 2.6, "src": "black_walnut_tree.glb", "pick": 2, "trees": 3, "height": 15.5, "cards0": 2300, "cards1": 520},
    {"id": "linden_a", "keep": 4600, "src": "tree_animate.glb", "pick": 0, "trees": 3, "height": 11.5, "cards0": 2100, "cards1": 500, "wind_keys": True},
    {"id": "linden_b", "keep": 4600, "src": "tree_animate.glb", "pick": 1, "trees": 3, "height": 12.5, "cards0": 2100, "cards1": 500, "wind_keys": True},
    {"id": "linden_c", "keep": 4600, "src": "tree_animate.glb", "pick": 2, "trees": 3, "height": 10.5, "cards0": 2100, "cards1": 500, "wind_keys": True},
    {"id": "cherry", "src": "tree.glb", "pick": 0, "trees": 1, "height": 7.0, "cards0": 2200, "cards1": 500, "weld": 0.03, "prune0": 0.9, "prune1": 0.6, "islands0": 160, "islands1": 25},
    {"id": "grove_a", "src": "low_poly_tree_scene_free.glb", "pick": "Bark.016", "trees": 1, "height": 12.5, "cards0": None, "cards1": 450},
    {"id": "grove_b", "src": "low_poly_tree_scene_free.glb", "pick": "Bark.009", "trees": 1, "height": 10.0, "cards0": None, "cards1": 420},
]
BARK0, BARK1 = 2200, 300
LEAF_TILE0, LEAF_TILE1, FAR_TILE = 512, 256, 256
BARK_WORDS = ("bark", "trunk", "branch_", "structure", "shd_trunk")


def wanted(pid):
    return not ONLY or pid in ONLY


def log(*a):
    print("[landscape]", *a, flush=True)


# ----------------------------------------------------------------------------- scene helpers
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_src(name, fresh=True):
    if fresh:
        reset()
    t0 = time.time()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    log("imported", name, "%.1fs" % (time.time() - t0))
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks:
                kb.value = 0.0
            if o.data.shape_keys.animation_data:
                o.data.shape_keys.animation_data.action = None
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def select_only(objs, active=None):
    for o in list(bpy.context.view_layer.objects):
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def bake(objs, name):
    """World-space static copy of meshes (modifiers applied), joined into one object."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in objs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        if not me.polygons:
            continue
        me.transform(o.matrix_world)
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        while len(n.data.uv_layers) > 1:
            n.data.uv_layers.remove(n.data.uv_layers[-1])
        if n.data.uv_layers:
            n.data.uv_layers[0].name = "UVMap"
        parts.append(n)
    if not parts:
        return None
    if len(parts) > 1:
        select_only(parts)
        bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    return obj


def new_obj(name, me):
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def delete(objs):
    for o in objs:
        if o is not None and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)


def keep_faces(obj, mask):
    """Delete the faces of obj where mask is False (and loose verts)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    dead = [f for f, k in zip(bm.faces, mask) if not k]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def copy_obj(obj, name):
    o = obj.copy()
    o.data = obj.data.copy()
    o.name = name
    bpy.context.scene.collection.objects.link(o)
    return o


def verts_np(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_verts(me, co):
    me.vertices.foreach_set("co", co.ravel())
    me.update()


def face_islands(me):
    """Island label per polygon (connected through shared vertices)."""
    n = len(me.vertices)
    lab = np.arange(n)
    e = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    for _ in range(400):
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        old = lab.copy()
        np.minimum.at(lab, e[:, 0], m)
        np.minimum.at(lab, e[:, 1], m)
        lab = lab[lab]
        if np.array_equal(old, lab):
            break
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    _, inv = np.unique(lab[lv[ls]], return_inverse=True)
    return inv


def poly_np(me):
    n = len(me.polygons)
    c = np.empty(n * 3); me.polygons.foreach_get("center", c)
    nr = np.empty(n * 3); me.polygons.foreach_get("normal", nr)
    a = np.empty(n); me.polygons.foreach_get("area", a)
    mi = np.empty(n, np.int64); me.polygons.foreach_get("material_index", mi)
    return c.reshape(-1, 3), nr.reshape(-1, 3), a, mi


def weld(obj, dist=0.0005):
    m = obj.modifiers.new("weld", "WELD")
    m.merge_threshold = dist
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier=m.name)


def remesh(obj, voxel):
    """Voxel-remesh a mesh made of thousands of loose plates into one closed surface (so it can be
    decimated), then transfer the UVs back from the original."""
    if tris(obj.data) > 100000:
        # a plain first collapse keeps the remesh quick (no weld on millions of vertices)
        d = obj.modifiers.new("pre", "DECIMATE")
        d.ratio = 100000 / tris(obj.data)
        select_only([obj])
        bpy.ops.object.modifier_apply(modifier=d.name)
    t0 = time.time()
    src = copy_obj(obj, obj.name + "_uvsrc")
    m = obj.modifiers.new("rm", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    m.use_smooth_shade = True
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier=m.name)
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    dt = obj.modifiers.new("dt", "DATA_TRANSFER")
    dt.object = src
    dt.use_loop_data = True
    dt.data_types_loops = {"UV"}
    dt.loop_mapping = "POLYINTERP_NEAREST"
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier=dt.name)
    log("remesh + uv transfer %.1fs, %d tris" % (time.time() - t0, tris(obj.data)))
    mats = list(src.data.materials)
    obj.data.materials.clear()
    for mt in mats[:1]:
        obj.data.materials.append(mt)
    delete([src])


def decimate(obj, budget):
    if tris(obj.data) <= budget:
        return
    weld(obj, 0.0005 * max(obj.dimensions))
    for _ in range(5):
        m = obj.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(0.002, budget / max(1, tris(obj.data)) * 0.97)
        m.use_collapse_triangulate = True
        select_only([obj])
        bpy.ops.object.modifier_apply(modifier=m.name)
        if tris(obj.data) <= budget:
            break
    if obj.data.has_custom_normals:
        select_only([obj])
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    obj.data.shade_smooth()


def prune_islands(obj, keep_area, max_islands=None):
    """Drop the smallest islands (twigs) keeping `keep_area` of the total surface."""
    me = obj.data
    if not me.polygons:
        return
    isl = face_islands(me)
    _, _, area, _ = poly_np(me)
    tot = np.bincount(isl, weights=area)
    order = np.argsort(-tot)
    cum = np.cumsum(tot[order]) / tot.sum()
    n = int(np.searchsorted(cum, keep_area)) + 1
    if max_islands:
        n = min(n, max_islands)
    log("prune: %d islands, keeping %d (%.0f%% of the area)" % (len(tot), n, cum[n - 1] * 100))
    keep = set(order[:n].tolist())
    keep_faces(obj, np.array([i in keep for i in isl]))


# ----------------------------------------------------------------------------- materials
def principled(mat):
    if mat is None or not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def upstream_images(sock):
    out, seen, stack = [], set(), [l.from_node for l in sock.links]
    while stack:
        n = stack.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        if n.type == "TEX_IMAGE" and n.image:
            out.append(n)
        for i in n.inputs:
            stack += [l.from_node for l in i.links]
    return out


def emission_copy(mat, ao_from_vcol=False):
    """Unlit copy of a material: Base Color -> Emission, Alpha -> clip; for albedo bakes."""
    m = mat.copy()
    m.name = mat.name + "_emit"
    nt = m.node_tree
    bsdf = principled(m)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.5
    col_src = None
    if bsdf is not None:
        bc = bsdf.inputs["Base Color"]
        if bc.is_linked:
            col_src = bc.links[0].from_socket
        else:
            em.inputs["Color"].default_value = bc.default_value
        al = bsdf.inputs["Alpha"]
        if al.is_linked:
            nt.links.new(al.links[0].from_socket, gt.inputs[0])
        else:
            gt.inputs[0].default_value = al.default_value
    else:
        gt.inputs[0].default_value = 1.0
    if col_src is not None:
        if ao_from_vcol:
            vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "Col"
            mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
            mul.inputs["Factor"].default_value = 1.0
            nt.links.new(col_src, mul.inputs[6])
            nt.links.new(vc.outputs["Alpha"], mul.inputs[7])
            nt.links.new(mul.outputs[2], em.inputs["Color"])
        else:
            nt.links.new(col_src, em.inputs["Color"])
    nt.links.new(gt.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    return m


def image_file(img, max_px, path, keep_alpha=False):
    """Resize an image to <= max_px (power of two) and save it (png keeps alpha, jpg otherwise)."""
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    s = min(1.0, max_px / max(w, h))
    tw = int(2 ** round(math.log2(max(4, w * s))))
    th = int(2 ** round(math.log2(max(4, h * s))))
    tw, th = min(tw, max_px), min(th, max_px)
    tmp = bpy.data.images.new("tmp_resize", w, h, alpha=True)
    tmp.colorspace_settings.name = img.colorspace_settings.name
    tmp.pixels.foreach_set(px)
    if (tw, th) != (w, h):
        tmp.scale(tw, th)
    tmp.filepath_raw = path
    tmp.file_format = "PNG" if keep_alpha else "JPEG"
    if not keep_alpha:
        tmp.alpha_mode = "NONE"
    tmp.save()
    bpy.data.images.remove(tmp)
    return path


def load_image(path, noncolor=False, name=None):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
    if name:
        img.name = name
    return img


def make_material(name, color_img=None, normal_img=None, cutout=False, rough=0.85, rgba=None, vcol_mul=False):
    """glTF-friendly Principled material. cutout -> alpha MASK (1 - (a < .5) chain)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = principled(m)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.3
    if color_img is not None:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = color_img; t.interpolation = "Linear"
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if cutout:
            lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.5
            sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[0].default_value = 1.0
            nt.links.new(t.outputs["Alpha"], lt.inputs[0])
            nt.links.new(lt.outputs[0], sub.inputs[1])
            nt.links.new(sub.outputs[0], b.inputs["Alpha"])
            m.surface_render_method = "DITHERED"
        nt.nodes.active = t
    elif rgba is not None:
        b.inputs["Base Color"].default_value = rgba
    if normal_img is not None:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = normal_img
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def base_and_normal(mat):
    """(base colour image, normal image) of a source material."""
    b = principled(mat)
    if b is None:
        return None, None
    col = upstream_images(b.inputs["Base Color"])
    nrm = upstream_images(b.inputs["Normal"])
    return (col[0].image if col else None), (nrm[0].image if nrm else None)


def bark_material(src_mat, sid, size=512):
    col, nrm = base_and_normal(src_mat)
    ci = load_image(image_file(col, size, os.path.join(TMP, sid + "_bark.jpg")), name=sid + "_bark") if col else None
    ni = load_image(image_file(nrm, size, os.path.join(TMP, sid + "_bark_n.jpg")), True, sid + "_bark_n") if nrm else None
    return make_material(sid + "_bark", ci, ni, rough=0.9)


# ----------------------------------------------------------------------------- rendering
def bake_scene():
    sc = bpy.data.scenes.get("Bake") or bpy.data.scenes.new("Bake")
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.eevee.taa_render_samples = 16
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("BakeWorld")
    sc.world.use_nodes = True
    bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[1].default_value = 0.0
    if "BakeCam" not in sc.objects:
        cam = bpy.data.objects.new("BakeCam", bpy.data.cameras.new("BakeCam"))
        sc.collection.objects.link(cam)
        cam.data.type = "ORTHO"
        sc.camera = cam
    return sc


def render_ortho(objs, centre, view_dir, size, px, path, up=Vector((0, 0, 1))):
    """Orthographic unlit render of objs (already using emission materials) into path."""
    sc = bake_scene()
    for o in list(sc.collection.objects):
        if o.name != "BakeCam":
            sc.collection.objects.unlink(o)
    for o in objs:
        sc.collection.objects.link(o)
    cam = sc.objects["BakeCam"]
    d = Vector(view_dir).normalized()
    cam.data.ortho_scale = size
    cam.data.clip_start = 0.01
    cam.data.clip_end = size * 40 + 200
    cam.location = Vector(centre) - d * (size * 10 + 50)
    cam.rotation_euler = d.to_track_quat("-Z", "Y" if abs(d.z) < 0.9 else "X").to_euler()
    if abs(d.z) < 0.9:
        # keep world up as image up
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x = sc.render.resolution_y = px
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    for o in objs:
        sc.collection.objects.unlink(o)
    return path


def read_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def dilate(px, passes=6):
    """Bleed opaque colours into transparent pixels so mipmaps do not darken leaf edges."""
    rgb, a = px[..., :3].copy(), px[..., 3:4].copy()
    acc, wsum = rgb * a, a.copy()
    out = rgb.copy()
    filled = a[..., 0] > 0.5
    for r in [1, 2, 4, 8, 16, 32][:passes]:
        k_acc = np.zeros_like(acc); k_w = np.zeros_like(wsum)
        for dy in (-r, 0, r):
            for dx in (-r, 0, r):
                k_acc += np.roll(np.roll(acc, dy, 0), dx, 1)
                k_w += np.roll(np.roll(wsum, dy, 0), dx, 1)
        acc, wsum = k_acc, k_w
        ok = (wsum[..., 0] > 1e-4) & ~filled
        out[ok] = acc[ok] / wsum[ok]
        filled |= ok
    mean = (rgb * a).reshape(-1, 3).sum(0) / max(1e-4, a.sum())
    out[~filled] = mean
    res = px.copy()
    res[..., :3] = np.where(a > 0.5, rgb, out)
    return res


def write_png(px, path):
    h, w = px.shape[:2]
    img = bpy.data.images.new("out", w, h, alpha=True)
    img.pixels.foreach_set(px.astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


# ----------------------------------------------------------------------------- tree pipeline
def is_bark(mat):
    n = (mat.name if mat else "").lower()
    return any(w in n for w in BARK_WORDS) and "leaf" not in n and "foliage" not in n


def split_by_trunks(bark, leaves, count, pick):
    """Several trees in one source: assign islands to the nearest trunk (sorted by x)."""
    if count <= 1:
        return
    me = bark.data
    isl = face_islands(me)
    c, _, a, _ = poly_np(me)
    zmin = c[:, 2].min()
    zr = c[:, 2].max() - zmin
    low = c[:, 2] < zmin + 0.04 * zr
    roots = []
    for i in np.unique(isl[low]):
        p = c[(isl == i) & low][:, :2].mean(0)
        if all(np.linalg.norm(p - r) > zr * 0.15 for r in roots):
            roots.append(p)
    roots = sorted(roots, key=lambda p: p[0])[:count]
    roots = np.array(roots)
    target = roots[pick]
    for obj in [bark] + ([leaves] if leaves else []):
        me = obj.data
        isl = face_islands(me)
        cc, _, aa, _ = poly_np(me)
        n = isl.max() + 1
        cen = np.stack([np.bincount(isl, weights=cc[:, k] * aa, minlength=n) for k in range(2)], 1) / np.maximum(1e-9, np.bincount(isl, weights=aa, minlength=n))[:, None]
        d = np.linalg.norm(cen[:, None, :] - roots[None, :, :], axis=2)
        mine = np.argmin(d, 1) == pick
        keep_faces(obj, mine[isl])


def normalise(objs, height):
    """Trunk base centre -> origin, bark bottom -> z 0, uniform scale to `height`."""
    bark = objs[0]
    co = verts_np(bark.data)
    zmin = co[:, 2].min()
    allz = np.concatenate([verts_np(o.data)[:, 2] for o in objs if o])
    H = allz.max() - zmin
    base = co[co[:, 2] < zmin + 0.02 * H][:, :2].mean(0)
    s = height / H
    for o in objs:
        if o is None:
            continue
        v = verts_np(o.data)
        v[:, 0] -= base[0]; v[:, 1] -= base[1]; v[:, 2] -= zmin
        set_verts(o.data, v * s)
    return s


def crown_shape(leaves):
    c, _, a, _ = poly_np(leaves.data)
    centre = (c * a[:, None]).sum(0) / a.sum()
    lo, hi = np.percentile(c, 3, axis=0), np.percentile(c, 97, axis=0)
    radii = np.maximum((hi - lo) / 2, 0.3)
    centre = (lo + hi) / 2
    return centre, radii


def wind_weights(co, H, crown_c, crown_r, bark=False):
    z = np.clip((co[:, 2] - 0.18 * H) / (0.82 * H), 0, 1) ** 1.4
    rxy = np.linalg.norm(co[:, :2], axis=1) / max(crown_r[0], crown_r[1], 0.3)
    w = z * (0.55 + 0.45 * np.clip(rxy, 0, 1))
    return w * (0.7 if bark else 1.0)


def crown_ao(co, crown_c, crown_r):
    q = np.linalg.norm((co - crown_c) / crown_r, axis=1)
    return 0.5 + 0.5 * np.clip(q, 0, 1) ** 0.8


def set_vcol(me, rgba_per_vertex):
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    attr = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
    attr.data.foreach_set("color", np.clip(rgba_per_vertex, 0, 1).astype(np.float32).ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = 0


def outward_normals(co, centre, radii, base_n, k=0.65):
    o = (co - centre) / radii
    o /= np.maximum(1e-6, np.linalg.norm(o, axis=1))[:, None]
    n = base_n * (1 - k) + o * k
    return n / np.maximum(1e-6, np.linalg.norm(n, axis=1))[:, None]


def leaf_islands(leaves, sway_attr=None):
    me = leaves.data
    isl = face_islands(me)
    c, nr, a, _ = poly_np(me)
    n = isl.max() + 1
    A = np.maximum(1e-9, np.bincount(isl, weights=a, minlength=n))
    cen = np.stack([np.bincount(isl, weights=c[:, k] * a, minlength=n) for k in range(3)], 1) / A[:, None]
    nor = np.stack([np.bincount(isl, weights=nr[:, k] * a, minlength=n) for k in range(3)], 1)
    nor /= np.maximum(1e-9, np.linalg.norm(nor, axis=1))[:, None]
    return {"isl": isl, "cen": cen, "nor": nor, "area": A}


def voxel_cards(cen, area, count):
    """Cell size h such that the occupied voxels of the island centroids number ~count."""
    lo_h, hi_h = 0.02, 20.0
    for _ in range(40):
        h = math.sqrt(lo_h * hi_h)
        keys = np.floor(cen / h).astype(np.int64)
        n = len(np.unique(keys, axis=0))
        if n > count:
            lo_h = h
        else:
            hi_h = h
    h = hi_h
    keys = np.floor(cen / h).astype(np.int64)
    uk, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    W = np.bincount(inv, weights=area)
    pos = np.stack([np.bincount(inv, weights=cen[:, k] * area) for k in range(3)], 1) / W[:, None]
    return h, pos, inv


def render_leaf_tiles(leaves, li, crown_c, crown_r, card, tiles, px, sid, tag, rng, slab=1.0):
    """Render `tiles` leaf-cluster textures (card x card metres) from sample spots on the crown."""
    paths = []
    cen = li["cen"]
    q = np.linalg.norm((cen - crown_c) / crown_r, axis=1)
    cand = np.where((q > 0.45) & (q < 0.85))[0]
    if len(cand) < tiles:
        cand = np.arange(len(cen))
    r = card * 0.5 / 1.12
    for t in range(tiles):
        tries = []
        for _ in range(24):
            i = int(rng.choice(cand))
            spot = cen[i]
            out = spot - crown_c
            out[2] *= 0.35
            vd = out / max(1e-6, np.linalg.norm(out))
            rel = cen - spot
            depth = rel @ vd
            lat = np.linalg.norm(rel - depth[:, None] * vd[None, :], axis=1)
            near = (lat < r) & (np.abs(depth) < r * slab)
            tries.append((int(near.sum()), spot, near))
        tries.sort(key=lambda x: x[0])
        _, spot, near = tries[int(len(tries) * 0.75)]
        obj = copy_obj(leaves, "tile_%d" % t)
        keep_faces(obj, near[li["isl"]])
        out = spot - crown_c
        out[2] *= 0.35
        view = -(out / max(1e-6, np.linalg.norm(out)))
        path = os.path.join(TMP, "%s_%s_tile%d.png" % (sid, tag, t))
        render_ortho([obj], Vector(spot), Vector(view), card, px, path)
        delete([obj])
        paths.append(path)
    return paths


def atlas2x2(paths, px):
    tiles = [dilate(read_png(p)) for p in paths]
    out = np.zeros((px * 2, px * 2, 4), np.float32)
    for t, im in enumerate(tiles):
        x, y = (t % 2) * px, (t // 2) * px
        out[y:y + px, x:x + px] = im
    return out


def build_cards(pos, h, nor_hint, crown_c, crown_r, H, rng, tiles_per_side, tile_index_fn, scale=1.7):
    """Quads at pos; returns verts, faces, uvs (per loop), loop normals, vcol (per vertex)."""
    n = len(pos)
    verts, faces, uvs, lnor, vcol = [], [], [], [], []
    for i in range(n):
        p = pos[i]
        out = (p - crown_c) / crown_r
        out /= max(1e-6, np.linalg.norm(out))
        rnd = rng.normal(size=3); rnd /= np.linalg.norm(rnd)
        nn = out * 0.55 + nor_hint[i] * 0.25 + rnd * 0.6
        nn /= np.linalg.norm(nn)
        size = h * scale * rng.uniform(0.85, 1.15)
        t = np.cross(nn, [0, 0, 1.0])
        if np.linalg.norm(t) < 1e-3:
            t = np.array([1.0, 0, 0])
        t /= np.linalg.norm(t)
        b = np.cross(nn, t)
        ang = rng.uniform(-0.6, 0.6)
        t, b = t * math.cos(ang) + b * math.sin(ang), -t * math.sin(ang) + b * math.cos(ang)
        k = len(verts)
        for su, sv in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
            verts.append(p + t * su * size + b * sv * size)
        faces.append((k, k + 1, k + 2, k + 3))
        u0, v0, du = tile_index_fn(i)
        for su, sv in [(0, 0), (1, 0), (1, 1), (0, 1)]:
            uvs.append((u0 + su * du, v0 + sv * du))
        phase = rng.uniform(0, 1)
        for _ in range(4):
            vcol.append(phase)
    verts = np.array(verts)
    fn = np.array([np.cross(verts[f[1]] - verts[f[0]], verts[f[3]] - verts[f[0]]) for f in faces])
    fn /= np.maximum(1e-9, np.linalg.norm(fn, axis=1))[:, None]
    lnor = outward_normals(verts, crown_c, crown_r, np.repeat(fn, 4, axis=0), 0.85)
    return verts, faces, uvs, lnor, np.array(vcol)


def mesh_from_cards(name, verts, faces, uvs, lnor, rgba):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", np.array(uvs, np.float32).ravel())
    set_vcol(me, rgba)
    me.normals_split_custom_set([tuple(n) for n in lnor])
    return me


def vcol_for(co, H, crown_c, crown_r, flutter, phase, bark=False, sway=None):
    w = sway if sway is not None else wind_weights(co, H, crown_c, crown_r, bark)
    ao = crown_ao(co, crown_c, crown_r) if not bark else np.clip(0.62 + 0.38 * co[:, 2] / H, 0, 1)
    return np.stack([w, np.full(len(co), flutter) if np.isscalar(flutter) else flutter,
                     np.full(len(co), phase) if np.isscalar(phase) else phase, ao], 1)


def join_meshes(objs, name):
    objs = [o for o in objs if o is not None]
    for o in objs:
        if o.data.uv_layers:
            o.data.uv_layers[0].name = "UVMap"
    select_only(objs)
    bpy.ops.object.join()
    o = objs[0]
    o.name = name
    o.data.name = name
    return o


def tree_species(spec, lod1_atlas, far_atlas, slot):
    sid = spec["id"]
    rng = np.random.default_rng(abs(hash(sid)) % (2 ** 31))
    meshes = import_src(spec["src"])
    lod1_atlas = make_lod1_atlas()
    if isinstance(spec["pick"], str):
        # A named tree in the scene pack: its bark node and the leaves parented under it.
        root = next(o for o in bpy.data.objects if o.name.startswith(spec["pick"]))
        meshes = [o for o in [root] + list(root.children_recursive) if o.type == "MESH"]
    bark_src = [o for o in meshes if o.data.materials and is_bark(o.data.materials[0])]
    leaf_src = [o for o in meshes if o.data.materials and not is_bark(o.data.materials[0])]
    if spec.get("wind_keys"):
        # Sway weights from the wind animation: per-vertex displacement over the shape keys.
        for o in leaf_src + bark_src:
            me = o.data
            attr = me.attributes.new("sway", "FLOAT", "POINT")
            if me.shape_keys:
                kb = me.shape_keys.key_blocks
                base = np.empty(len(me.vertices) * 3); kb[0].data.foreach_get("co", base)
                d = np.zeros(len(me.vertices))
                for k in kb[1:]:
                    co = np.empty(len(me.vertices) * 3); k.data.foreach_get("co", co)
                    d = np.maximum(d, np.linalg.norm((co - base).reshape(-1, 3), axis=1))
                attr.data.foreach_set("value", d)
            else:
                attr.data.foreach_set("value", np.zeros(len(me.vertices)))
    leaf_mats = {}
    for o in leaf_src:
        for m in o.data.materials:
            if m:
                leaf_mats[m.name] = m
    bark_mat_src = bark_src[0].data.materials[0]
    bark = bake(bark_src, sid + "_bark")
    leaves = bake(leaf_src, sid + "_leaves")
    log(sid, "baked", tris(bark.data), tris(leaves.data))
    split_by_trunks(bark, leaves, spec["trees"], spec["pick"] if isinstance(spec["pick"], int) else 0)
    scale = normalise([bark, leaves], spec["height"])
    H = spec["height"]
    if spec.get("weld"):
        # The trunk is an unwelded triangle soup of sub-millimetre bark detail: weld it first so
        # collapse decimation keeps the trunk instead of discarding loose triangles.
        weld(bark, spec["weld"])
    crown_c, crown_r = crown_shape(leaves)
    sway_src = None
    if spec.get("wind_keys"):
        # normalise by the displacement range (scaled into metres)
        sway_l = np.empty(len(leaves.data.vertices)); leaves.data.attributes["sway"].data.foreach_get("value", sway_l)
        sway_b = np.empty(len(bark.data.vertices)); bark.data.attributes["sway"].data.foreach_get("value", sway_b)
        top = max(1e-6, np.percentile(sway_l, 98))
        sway_src = (np.clip(sway_l / top, 0, 1), np.clip(sway_b / top, 0, 1))
    log(sid, "normalised", tris(bark.data), tris(leaves.data))
    li = leaf_islands(leaves)
    q = np.linalg.norm((li["cen"] - crown_c) / crown_r, axis=1)
    if (q > 1.45).any():
        keep_faces(leaves, (q <= 1.45)[li["isl"]])
        li = leaf_islands(leaves)
    src_leaf_tris = tris(leaves.data)
    src_bark_tris = tris(bark.data)
    log(sid, "islands", tris(bark.data), tris(leaves.data))
    # ---- bark LOD0 / LOD1
    bark0 = copy_obj(bark, sid + "_bark0")
    if spec.get("prune", True):
        prune_islands(bark0, spec.get("prune0", 0.93), spec.get("islands0"))
    decimate(bark0, BARK0)
    bark1 = copy_obj(bark0, sid + "_bark1")
    if spec.get("prune", True):
        prune_islands(bark1, spec.get("prune1", 0.6), spec.get("islands1"))
    decimate(bark1, BARK1)
    for b in (bark0, bark1):
        co = verts_np(b.data)
        sway = None
        if sway_src is not None:
            # nearest original bark vertex sway (coarse: by height band)
            sway = np.clip(wind_weights(co, H, crown_c, crown_r, True) * 0.8, 0, 1)
        set_vcol(b.data, vcol_for(co, H, crown_c, crown_r, 0.0, 0.0, bark=True, sway=sway))
    log(sid, "bark lods", tris(bark.data), tris(leaves.data))
    bmat = bark_material(bark_mat_src, sid)
    bark0.data.materials.clear(); bark0.data.materials.append(bmat)
    # emission copies of the source leaf materials for the tile renders
    emit = {}
    for i, m in enumerate(leaves.data.materials):
        emit[i] = emission_copy(m) if m else None
    tile_src = copy_obj(leaves, sid + "_tilesrc")
    for i, m in emit.items():
        if m:
            tile_src.data.materials[i] = m
    # ---- leaves LOD0
    if spec.get("keep"):
        # Source leaves are already multi-leaf cluster cards: thin them to the budget and enlarge
        # the survivors about their own centre so the crown keeps its coverage.
        leaves0 = copy_obj(leaves, sid + "_leaves0")
        f = min(1.0, spec["keep"] / max(1, tris(leaves.data)))
        n_isl = len(li["cen"])
        chosen = rng.uniform(0, 1, n_isl) < f
        grow = float(np.clip(max(math.sqrt(1.0 / f) * 0.82, spec.get("grow_min", 1.0)), 1.0, 1.9))
        me = leaves0.data
        co = verts_np(me)
        ls = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get("loop_start", ls)
        vert_isl = np.zeros(len(co), np.int64)
        for poly, i in zip(me.polygons, li["isl"]):
            for v in poly.vertices:
                vert_isl[v] = i
        co = li["cen"][vert_isl] + (co - li["cen"][vert_isl]) * grow
        set_verts(me, co)
        keep_faces(leaves0, chosen[li["isl"]])
        mats = []
        for i, m in enumerate(leaves0.data.materials):
            col, _ = base_and_normal(m)
            img = load_image(image_file(col, 1024, os.path.join(TMP, "%s_leaf%d.png" % (sid, i)), keep_alpha=True), name="%s_leaves%d" % (sid, i)) if col else None
            leaves0.data.materials[i] = make_material(sid + ("_leaves" if i == 0 else "_twigs"), img, cutout=True, rough=0.8)
        limg = leaves0.data.materials[0].node_tree.nodes.active.image
        me = leaves0.data
        co = verts_np(me)
        isl2 = face_islands(me)
        ph = rng.uniform(0, 1, isl2.max() + 1)
        vphase = np.zeros(len(co))
        for poly, i in zip(me.polygons, isl2):
            for v in poly.vertices:
                vphase[v] = ph[i]
        sway = None
        if sway_src is not None and "sway" in me.attributes:
            sw = np.empty(len(co)); me.attributes["sway"].data.foreach_get("value", sw)
            top = max(1e-6, np.percentile(sw, 98))
            sway = np.clip(sw / top, 0, 1) * np.clip(co[:, 2] / (0.3 * H), 0, 1)
        set_vcol(me, vcol_for(co, H, crown_c, crown_r, 1.0, vphase, sway=sway))
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
        cn = np.array([p.normal for p in me.polygons])
        pl = np.repeat(np.arange(len(me.polygons)), [len(p.vertices) for p in me.polygons])
        me.normals_split_custom_set([tuple(n) for n in outward_normals(co[lv], crown_c, crown_r, cn[pl], 0.6)])
        card0 = "keep %.2f grow %.2f" % (f, grow)
    elif spec["cards0"] is None:
        leaves0 = copy_obj(leaves, sid + "_leaves0")
        col, _ = base_and_normal(leaves.data.materials[0])
        limg = load_image(image_file(col, 1024, os.path.join(TMP, sid + "_leaf.png"), keep_alpha=True), name=sid + "_leaves")
        lmat = make_material(sid + "_leaves", limg, cutout=True, rough=0.8)
        leaves0.data.materials.clear(); leaves0.data.materials.append(lmat)
        co = verts_np(leaves0.data)
        isl = li["isl"]
        ls = np.empty(len(leaves0.data.polygons), np.int64); leaves0.data.polygons.foreach_get("loop_start", ls)
        phase_isl = rng.uniform(0, 1, isl.max() + 1)
        vphase = np.zeros(len(co))
        for p, f in zip(leaves0.data.polygons, isl):
            for v in p.vertices:
                vphase[v] = phase_isl[f]
        set_vcol(leaves0.data, vcol_for(co, H, crown_c, crown_r, 1.0, vphase))
        # soft crown normals
        me = leaves0.data
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
        cn = np.array([me.polygons[i].normal for i in range(len(me.polygons))])
        pl = np.repeat(np.arange(len(me.polygons)), [len(p.vertices) for p in me.polygons])
        me.normals_split_custom_set([tuple(n) for n in outward_normals(co[lv], crown_c, crown_r, cn[pl], 0.6)])
        card0 = None
    else:
        h0, pos0, inv0 = voxel_cards(li["cen"], li["area"], spec["cards0"])
        card0 = h0 * 1.7
        tiles = render_leaf_tiles(tile_src, li, crown_c, crown_r, card0, 4, LEAF_TILE0, sid, "lod0", rng, spec.get("slab", 1.0))
        atlas = atlas2x2(tiles, LEAF_TILE0)
        limg = load_image(write_png(atlas, os.path.join(TMP, sid + "_leaves.png")), name=sid + "_leaves")
        lmat = make_material(sid + "_leaves", limg, cutout=True, rough=0.8)
        nor_hint = np.stack([np.bincount(inv0, weights=li["nor"][:, k] * li["area"]) for k in range(3)], 1)
        nor_hint /= np.maximum(1e-9, np.linalg.norm(nor_hint, axis=1))[:, None]
        tidx = rng.integers(0, 4, len(pos0))
        verts, faces, uvs, lnor, ph = build_cards(pos0, h0, nor_hint, crown_c, crown_r, H, rng, 2,
                                                lambda i: ((tidx[i] % 2) * 0.5, (tidx[i] // 2) * 0.5, 0.5))
        sway = None
        if sway_src is not None:
            sw_isl = np.bincount(li["isl"], weights=np.array([sway_src[0][p.vertices[0]] for p in leaves.data.polygons]), minlength=len(li["cen"]))
            cnt = np.maximum(1, np.bincount(li["isl"], minlength=len(li["cen"])))
            sw_isl = sw_isl / cnt
            sw_card = np.bincount(inv0, weights=sw_isl) / np.maximum(1, np.bincount(inv0))
            sway = np.repeat(sw_card, 4)
        rgba = vcol_for(verts, H, crown_c, crown_r, 1.0, ph, sway=sway)
        leaves0 = new_obj(sid + "_leaves0", mesh_from_cards(sid + "_leaves0", verts, faces, uvs, lnor, rgba))
        leaves0.data.materials.append(lmat)
    log(sid, "leaves lod0", tris(bark.data), tris(leaves.data))
    # ---- leaves LOD1 (one tile in the shared atlas)
    h1, pos1, inv1 = voxel_cards(li["cen"], li["area"], spec["cards1"])
    card1 = h1 * 1.7
    t1 = render_leaf_tiles(tile_src, li, crown_c, crown_r, card1, 1, LEAF_TILE1, sid, "lod1", rng, spec.get("slab", 1.0))[0]
    np.save(os.path.join(CACHE, sid + "_lod1tile.npy"), dilate(read_png(t1)))
    nor1 = np.stack([np.bincount(inv1, weights=li["nor"][:, k] * li["area"]) for k in range(3)], 1)
    nor1 /= np.maximum(1e-9, np.linalg.norm(nor1, axis=1))[:, None]
    g = lod1_atlas["grid"]
    u0, v0 = (slot % g) / g, (slot // g) / g
    verts, faces, uvs, lnor, ph = build_cards(pos1, h1, nor1, crown_c, crown_r, H, rng, 1, lambda i: (u0, v0, 1.0 / g), scale=1.75)
    sway1 = None
    if sway_src is not None:
        sway1 = np.repeat(np.clip(wind_weights(verts[::4], H, crown_c, crown_r), 0, 1), 4)
    leaves1 = new_obj(sid + "_leaves1", mesh_from_cards(sid + "_leaves1", verts, faces, uvs, lnor, vcol_for(verts, H, crown_c, crown_r, 1.0, ph, sway=sway1)))
    # bark of LOD1 samples its swatch (mean bark colour) in the atlas
    bcol, _ = base_and_normal(bark_mat_src)
    mean = np.array([0.25, 0.2, 0.15, 1.0])
    if bcol is not None:
        w, hh = bcol.size
        pxb = np.empty(w * hh * 4, np.float32); bcol.pixels.foreach_get(pxb)
        mean = pxb.reshape(-1, 4)[::7].mean(0)
    np.save(os.path.join(CACHE, sid + "_lod1sw.npy"), mean)
    sw = lod1_atlas["swatch_uv"](slot)
    me = bark1.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", np.tile(np.array(sw, np.float32), len(me.loops)))
    lod1 = join_meshes([leaves1, bark1], sid + "_LOD1")
    lod1.data.materials.clear()
    lod1.data.materials.append(lod1_atlas["material"])
    for p in lod1.data.polygons:
        p.material_index = 0
    # ---- LOD0 object
    lod0 = join_meshes([bark0, leaves0], "LOD0")
    # ---- far impostor: albedo x AO renders of LOD0, front (-Y view) and side (+X view)
    co0 = verts_np(lod0.data)
    width = max(np.abs(co0[:, 0]).max(), np.abs(co0[:, 1]).max()) * 2.0
    S = max(width, H) * 1.03
    far_obj = copy_obj(lod0, sid + "_farsrc")
    for i, m in enumerate(far_obj.data.materials):
        far_obj.data.materials[i] = emission_copy(m, ao_from_vcol=True)
    views = []
    for k, d in enumerate([(0, 1, 0), (-1, 0, 0)]):
        p = os.path.join(TMP, "%s_far%d.png" % (sid, k))
        render_ortho([far_obj], Vector((0, 0, S / 2)), Vector(d), S, FAR_TILE, p)
        np.save(os.path.join(CACHE, "%s_far%d.npy" % (sid, k)), dilate(read_png(p)))
    delete([far_obj, tile_src])
    tri0, tri1 = tris(lod0.data), tris(lod1.data)
    crown_base = float(np.percentile(li["cen"][:, 2], 4))
    trunk_r = float(np.percentile(np.linalg.norm(verts_np(bark.data)[verts_np(bark.data)[:, 2] < 1.0][:, :2], axis=1), 80)) if (verts_np(bark.data)[:, 2] < 1.0).any() else 0.25
    extras = {"species": sid, "height": H, "crown_radius": float(max(crown_r[0], crown_r[1])), "crown_base": crown_base,
              "trunk_radius": round(trunk_r, 3), "tris_lod0": tri0, "tris_lod1": tri1, "far_slot": slot, "far_size": float(S)}
    REPORT[sid] = dict(extras, source=spec["src"], source_tris={"bark": src_bark_tris, "leaves": src_leaf_tris},
                       card_size_lod0=card0, card_size_lod1=card1, source_scale=scale,
                       textures={"leaves": list(limg.size), "bark": [list(n.image.size) for n in bmat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]})
    log(sid, "LOD0", tri0, "LOD1", tri1, "H", H, "crown r", crown_r.round(2), "far", round(S, 2))
    delete([bark, leaves])
    return lod0, lod1, extras


def export_glb(objs, path, root_name, extras=None):
    sc = bpy.context.scene
    root = bpy.data.objects.new(root_name, None)
    sc.collection.objects.link(root)
    if extras:
        for k, v in extras.items():
            root[k] = v
    for o, ex in objs:
        if o.name not in sc.collection.objects:
            sc.collection.objects.link(o)
        o.parent = root
        for k, v in (ex or {}).items():
            o[k] = v
    select_only([root] + [o for o, _ in objs], root)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True,
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_normals=True,
                              export_animations=False, export_morph=False, export_image_format="AUTO", export_apply=False,
                              export_yup=True, export_tangents=False)
    log("wrote", os.path.relpath(path, ROOT), "%.1f MB" % (os.path.getsize(path) / 1e6))


def qa_neutral_vcols():
    """The glTF importer multiplies COLOR_0 into the base colour; ours is wind data, so whiten it."""
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            for a in o.data.color_attributes:
                a.data.foreach_set("color", np.ones(len(a.data) * 4, np.float32))


def qa_tree(sid, lod0_path, extras):
    """QA: LOD0 lit (front, 3/4 and top), LOD0 albedo crown close-up, plus a 1.8 m figure."""
    if not DO_QA:
        return
    reset()
    bpy.ops.import_scene.gltf(filepath=lod0_path)
    qa_neutral_vcols()
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 600
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 1.2
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(45), 0, math.radians(35)); sun.data.angle = 0.05
    gm = bpy.data.meshes.new("g"); gm.from_pydata([(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)], [], [(0, 1, 2, 3)])
    g = new_obj("ground", gm); gmat = make_material("ground", rgba=(0.18, 0.26, 0.1, 1)); gm.materials.append(gmat)
    fig = bpy.data.meshes.new("fig"); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.25, radius2=0.2, depth=1.8)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.9)); bm.to_mesh(fig); bm.free()
    f = new_obj("figure", fig); f.location = (extras["crown_radius"] + 1.5, -1.0, 0)
    fig.materials.append(make_material("fig", rgba=(0.8, 0.1, 0.05, 1)))
    for m in bpy.data.materials:
        if "leaves" in m.name:
            m.surface_render_method = "DITHERED"
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    H = extras["height"]
    for name, loc, tgt, lens in [("side", (0, -H * 2.6, H * 0.45), (0, 0, H * 0.5), 35), ("low", (H * 0.9, -H * 1.1, 1.7), (0, 0, H * 0.6), 24)]:
        cam.location = loc; cam.data.lens = lens
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(QA, "%s_%s.png" % (sid, name))
        bpy.ops.render.render(write_still=True)


# ----------------------------------------------------------------------------- LOD1 / far atlases
def make_lod1_atlas():
    """4x4 tiles of 256: species leaf tile = its far slot (0..12), bark swatches in tile 15 (4x4 of 64)."""
    g = 4
    mat = bpy.data.materials.get("TreeLod1Atlas") or make_material("TreeLod1Atlas", rgba=(0.2, 0.3, 0.1, 1))

    def swatch_uv(slot):
        tile = g * g - 1
        tx, ty = (tile % g) / g, (tile // g) / g
        sx, sy = (slot % 4 + 0.5) / 4 / g, (slot // 4 + 0.5) / 4 / g
        return (tx + sx, ty + sy)
    return {"grid": g, "material": mat, "swatch_uv": swatch_uv}


def finish_lod1_atlas(slots):
    g, t = 4, LEAF_TILE1
    px = np.zeros((g * t, g * t, 4), np.float32)
    tile = g * g - 1
    bx, by = (tile % g) * t, (tile // g) * t
    sw = t // 4
    for slot, sid in slots:
        im = np.load(os.path.join(CACHE, sid + "_lod1tile.npy"))
        x, y = (slot % g) * t, (slot // g) * t
        px[y:y + t, x:x + t] = im
        col = np.load(os.path.join(CACHE, sid + "_lod1sw.npy"))
        x, y = bx + (slot % 4) * sw, by + (slot // 4) * sw
        px[y:y + sw, x:x + sw, :3] = col[:3]
        px[y:y + sw, x:x + sw, 3] = 1.0
    path = write_png(px, os.path.join(TMP, "trees_lod1_atlas.png"))
    write_png(px, os.path.join(QA, "trees_lod1_atlas.png"))
    img = load_image(path, name="trees_lod1_atlas")
    return make_material("TreeLod1Atlas", img, cutout=True, rough=0.85)


def finish_far_atlas(slots):
    # 8 x 4 tiles of 256 -> 2048 x 1024; species slot s: tiles (2*(s%4), s//4) and the one right of
    # it (Blender image rows count from the bottom).
    t = FAR_TILE
    px = np.zeros((4 * t, 8 * t, 4), np.float32)
    for slot, sid in slots:
        for k in range(2):
            im = np.load(os.path.join(CACHE, "%s_far%d.npy" % (sid, k)))
            x, y = (2 * (slot % 4) + k) * t, (slot // 4) * t
            px[y:y + t, x:x + t] = im
    path = write_png(px, os.path.join(TMP, "tree_impostors.png"))
    img = load_image(path, name="tree_impostors")
    mat = make_material("TreeImpostorAtlas", img, cutout=True, rough=0.9)
    # unit crossed quad: plane A in XZ (seen from -Y) uses u 0..0.5, plane B in YZ uses 0.5..1
    verts = [(-0.5, 0, 0), (0.5, 0, 0), (0.5, 0, 1), (-0.5, 0, 1), (0, -0.5, 0), (0, 0.5, 0), (0, 0.5, 1), (0, -0.5, 1)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7)]
    me = bpy.data.meshes.new("Impostor")
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", np.array([(0, 0), (0.5, 0), (0.5, 1), (0, 1), (0.5, 0), (1, 0), (1, 1), (0.5, 1)], np.float32).ravel())
    set_vcol(me, np.tile([0.0, 0.0, 0.0, 1.0], (8, 1)))
    me.materials.append(mat)
    write_png(px, os.path.join(QA, "tree_impostors_atlas.png"))
    return new_obj("Impostor", me)


# ----------------------------------------------------------------------------- forest pack, rocks
def base_to_origin(obj, sink=0.0, scale=1.0):
    co = verts_np(obj.data)
    zmin = co[:, 2].min()
    H = co[:, 2].max() - zmin
    low = co[co[:, 2] < zmin + 0.05 * max(H, 0.01)]
    base = low[:, :2].mean(0)
    co[:, 0] -= base[0]; co[:, 1] -= base[1]; co[:, 2] -= zmin + sink * H
    set_verts(obj.data, co * scale)
    return H * scale


def simple_material(src, name, size, cutout):
    col, nrm = base_and_normal(src)
    ext = ".png" if cutout else ".jpg"
    ci = load_image(image_file(col, size, os.path.join(TMP, name + ext), keep_alpha=cutout), name=name) if col else None
    return make_material(name, ci, None, cutout=cutout, rough=0.85)


def generic_vcol(obj, H, bark=False, flutter=1.0, sway_scale=1.0):
    co = verts_np(obj.data)
    w = np.clip(co[:, 2] / max(H, 0.01), 0, 1) ** 1.5 * sway_scale
    ao = np.clip(0.6 + 0.4 * co[:, 2] / max(H, 0.01), 0, 1)
    me = obj.data
    isl = face_islands(me) if len(me.polygons) else np.zeros(0, int)
    phase = np.zeros(len(co))
    rng = np.random.default_rng(len(co))
    if len(isl):
        ph = rng.uniform(0, 1, isl.max() + 1)
        for p, i in zip(me.polygons, isl):
            for v in p.vertices:
                phase[v] = ph[i]
    set_vcol(me, np.stack([w, np.full(len(co), 0.0 if bark else flutter), phase, ao], 1))


FOREST_IMPOSTORS = {0: 13, 3: 14, 6: 15}   # fp_tree index -> impostor atlas slot


def render_far(obj, sid, H):
    """Albedo x AO renders of obj from the front (-Y) and side (+X) into the cache; returns the card size."""
    co = verts_np(obj.data)
    width = max(np.abs(co[:, 0]).max(), np.abs(co[:, 1]).max()) * 2.0
    S = max(width, H) * 1.03
    far_obj = copy_obj(obj, sid + "_farsrc")
    for i, m in enumerate(far_obj.data.materials):
        far_obj.data.materials[i] = emission_copy(m, ao_from_vcol=True)
    for k, d in enumerate([(0, 1, 0), (-1, 0, 0)]):
        p = os.path.join(TMP, "%s_far%d.png" % (sid, k))
        render_ortho([far_obj], Vector((0, 0, S / 2)), Vector(d), S, FAR_TILE, p)
        np.save(os.path.join(CACHE, "%s_far%d.npy" % (sid, k)), dilate(read_png(p)))
    delete([far_obj])
    return float(S)


def forest_pack():
    meshes = import_src("low_poly_forest_tree_pack.glb")
    out = []
    atlas_mat = None
    # Background_Tree_Atlas nodes: big ones are conifers / birches, small ones understory.
    cards = sorted([o for o in meshes if o.data.materials[0].name == "Background_Tree_Atlas"], key=lambda o: o.matrix_world.translation.x)
    big, small = [], []
    for o in cards:
        b = bake([o], "x")
        H = base_to_origin(b)
        (big if H > 8 else small).append((b, H))
    src_mat = cards[0].data.materials[0]
    atlas_mat = simple_material(src_mat, "forest_atlas", 1024, True)
    for i, (b, H) in enumerate(big):
        b.name = b.data.name = "fp_tree_%d" % i
        b.data.materials.clear(); b.data.materials.append(atlas_mat)
        generic_vcol(b, H, flutter=0.4)
        ex = {"height": float(H), "kind": "forest_tree"}
        if i in FOREST_IMPOSTORS:
            # Far impostor of this conifer in a free slot of the tree impostor atlas.
            slot = FOREST_IMPOSTORS[i]
            ex.update({"far_slot": slot, "far_size": render_far(b, "fp_tree_%d" % i, H)})
            json.dump(ex, open(os.path.join(CACHE, "fp_tree_%d_extras.json" % i), "w"))
        out.append((b, ex))
    for i, (b, H) in enumerate(small):
        b.name = b.data.name = "fp_small_%d" % i
        b.data.materials.clear(); b.data.materials.append(atlas_mat)
        generic_vcol(b, H, flutter=0.6)
        out.append((b, {"height": float(H), "kind": "understory"}))
    # Trunk + branch card pines.
    trunks = sorted([o for o in meshes if o.name.startswith("Tree_Trunk")], key=lambda o: o.matrix_world.translation.x)
    branches = [o for o in meshes if o.name.startswith("Tree_Branches")]
    mats = {}
    for i, t in enumerate(trunks):
        tx = Vector(t.matrix_world.translation)
        br = min(branches, key=lambda o: (Vector(o.matrix_world.translation).xy - tx.xy).length)
        bk = bake([t], "t"); bb = bake([br], "b")
        for o, cut in ((bk, False), (bb, True)):
            m = o.data.materials[0]
            key = m.name
            if key not in mats:
                mats[key] = simple_material(m, "fp_" + key.replace(".", "_").lower(), 512, cut)
            o.data.materials.clear(); o.data.materials.append(mats[key])
        j = join_meshes([bk, bb], "fp_pine_%d" % i)
        H = base_to_origin(j)
        generic_vcol(j, H, flutter=0.5)
        out.append((j, {"height": float(H), "kind": "forest_pine"}))
    rocks = [o for o in meshes if o.name.startswith("Rocks")]
    rmat = simple_material(rocks[0].data.materials[0], "rock", 512, False)
    rk = []
    for i, r in enumerate(sorted(rocks, key=lambda o: o.name)):
        b = bake([r], "rock_%d" % i)
        H = base_to_origin(b, sink=0.12)
        b.data.materials.clear(); b.data.materials.append(rmat)
        set_vcol(b.data, np.tile([0, 0, 0, 1.0], (len(b.data.vertices), 1)))
        rk.append((b, {"height": float(H), "kind": "rock"}))
    for o in meshes:
        delete([o])
    export_glb(out, os.path.join(OUT, "forest_pack.glb"), "ForestPack")
    report = {o.name: {"tris": tris(o.data), **e} for o, e in out}
    for o, _ in out:
        delete([o])
    export_glb(rk, os.path.join(OUT, "rocks.glb"), "Rocks")
    report.update({o.name: {"tris": tris(o.data), **e} for o, e in rk})
    REPORT["forest_pack"] = report
    if DO_QA:
        qa_lineup(os.path.join(OUT, "forest_pack.glb"), os.path.join(QA, "forest_pack.png"))
        qa_lineup(os.path.join(OUT, "rocks.glb"), os.path.join(QA, "rocks.png"))


# ----------------------------------------------------------------------------- garden kit
def garden():
    out = []
    # Grass clumps and shrubs from the tree scene.
    meshes = import_src("low_poly_tree_scene_free.glb")
    grass = [o for o in meshes if o.data.materials and o.data.materials[0].name == "Grass_C"]
    gmat = simple_material(grass[0].data.materials[0], "grass_clump", 512, True)
    for i, t in enumerate([50, 80]):
        g = next(o for o in grass if tris(o.data) == t)
        b = bake([g], "grass_%s" % "ab"[i])
        H = base_to_origin(b)
        s = (0.55 if i == 0 else 0.42) / H
        set_verts(b.data, verts_np(b.data) * s)
        b.data.materials.clear(); b.data.materials.append(gmat)
        generic_vcol(b, H * s, flutter=0.3, sway_scale=1.0)
        out.append((b, {"height": float(H * s), "kind": "grass"}))
    leaves = {o.parent.parent.name.split("_")[0]: o for o in meshes if o.data.materials and o.data.materials[0].name == "Leaves" and o.parent and o.parent.parent}
    lmat = simple_material(next(iter(leaves.values())).data.materials[0], "shrub_leaves", 512, True)
    for i, (key, size) in enumerate([("Bark.009", (1.5, 1.5, 1.05)), ("Bark.016", (2.2, 2.0, 1.35)), ("Bark.012", (1.0, 1.0, 0.75))]):
        src = leaves.get(key)
        if src is None:
            continue
        b = bake([src], "shrub_%s" % "abc"[i])
        co = verts_np(b.data)
        lo, hi = co.min(0), co.max(0)
        c = (lo + hi) / 2
        co = (co - [c[0], c[1], lo[2]]) / (hi - lo) * size
        co[:, 2] -= 0.08
        set_verts(b.data, co)
        b.data.materials.clear(); b.data.materials.append(lmat)
        generic_vcol(b, size[2], flutter=0.5, sway_scale=0.25)
        out.append((b, {"height": float(size[2]), "kind": "shrub"}))
    for o in meshes:
        delete([o])
    # Potted plants (SketchUp inches -> metres; the wire stands are dropped).
    before = set(bpy.context.scene.objects)
    meshes = [o for o in import_src("flower_model.glb", fresh=False) if o not in before]
    stand = [o for o in meshes if o.data.materials and o.data.materials[0] and o.data.materials[0].name == "Material__wrtrt2"]
    meshes = [o for o in meshes if o not in stand]
    delete(stand)
    whole = bake(meshes, "plants")
    set_verts(whole.data, verts_np(whole.data) * 0.0254)
    isl = face_islands(whole.data)
    c, _, a, _ = poly_np(whole.data)
    n = isl.max() + 1
    cx = np.bincount(isl, weights=c[:, 0] * a, minlength=n) / np.maximum(1e-9, np.bincount(isl, weights=a, minlength=n))
    groups = {"snake": cx[isl] < 0.46, "croton": (cx[isl] >= 0.46) & (cx[isl] < 0.98), "lily": cx[isl] >= 0.98}
    mats = {}
    for pid, mask in groups.items():
        o = copy_obj(whole, "potted_" + pid)
        keep_faces(o, mask)
        H = base_to_origin(o)
        for si, m in enumerate(o.data.materials):
            if m is None:
                continue
            if m.name not in mats:
                col, _ = base_and_normal(m)
                b = principled(m)
                if col is not None:
                    ci = load_image(image_file(col, 512, os.path.join(TMP, "pl_" + m.name + ".jpg")), name="plant_" + m.name)
                    mats[m.name] = make_material("plant_" + m.name, ci, rough=0.7)
                else:
                    mats[m.name] = make_material("plant_" + m.name, rgba=tuple(b.inputs["Base Color"].default_value) if b else (0.3, 0.3, 0.3, 1), rough=0.6)
            o.data.materials[si] = mats[m.name]
        decimate(o, 3000)
        generic_vcol(o, H, flutter=0.3, sway_scale=0.25)
        out.append((o, {"height": float(H), "kind": "potted"}))
        # bed version: the foliage only (above the pot rim), planted at ground level
        bed = copy_obj(o, "bed_" + pid)
        me = bed.data
        pc, _, _, _ = poly_np(me)
        pot_names = {"Material__13", "Material__1", "Material__6"}
        is_pot = np.array([(me.materials[p.material_index].name.replace("plant_", "") in pot_names) for p in me.polygons])
        keep_faces(bed, ~is_pot)
        if len(bed.data.polygons):
            co = verts_np(bed.data)
            co[:, 2] -= co[:, 2].min() + 0.05
            set_verts(bed.data, co)
            generic_vcol(bed, co[:, 2].max(), flutter=0.3, sway_scale=0.25)
            out.append((bed, {"height": float(co[:, 2].max()), "kind": "bed_plant"}))
        else:
            delete([bed])
    delete([whole])
    # Bed edging: low granite kerb ring round a mulch bed, 2.4 x 0.9 m.
    bm = bmesh.new()
    def box(x0, y0, z0, x1, y1, z1):
        vs = [bm.verts.new(v) for v in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
        for f in [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]:
            bm.faces.new([vs[i] for i in f])
    L, W, T, Hh = 1.2, 0.45, 0.07, 0.12
    box(-L, -W, 0, L, -W + T, Hh); box(-L, W - T, 0, L, W, Hh); box(-L, -W + T, 0, -L + T, W - T, Hh); box(L - T, -W + T, 0, L, W - T, Hh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("bed_edging"); bm.to_mesh(me); bm.free()
    stone = make_material("bed_stone", rgba=(0.42, 0.41, 0.38, 1), rough=0.9)
    mulch = make_material("bed_mulch", rgba=(0.12, 0.075, 0.045, 1), rough=1.0)
    me.materials.append(stone)
    mb = bmesh.new()
    vs = [mb.verts.new(v) for v in [(-L + T, -W + T, 0.07), (L - T, -W + T, 0.07), (L - T, W - T, 0.07), (-L + T, W - T, 0.07)]]
    mb.faces.new(vs)
    mm = bpy.data.meshes.new("m"); mb.to_mesh(mm); mb.free()
    mo = new_obj("m", mm); mm.materials.append(mulch)
    eo = new_obj("bed_edging", me)
    e = join_meshes([eo, mo], "bed_edging")
    set_vcol(e.data, np.tile([0, 0, 0, 1.0], (len(e.data.vertices), 1)))
    out.append((e, {"height": 0.12, "kind": "bed"}))
    good = []
    for o, x in out:
        try:
            o.name
            good.append((o, x))
        except ReferenceError:
            log("lost garden object", x)
    out = good
    export_glb(out, os.path.join(OUT, "garden.glb"), "Garden")
    REPORT["garden"] = {o.name: {"tris": tris(o.data), **x} for o, x in out}
    if DO_QA:
        qa_lineup(os.path.join(OUT, "garden.glb"), os.path.join(QA, "garden.png"))


def qa_lineup(path, png, skip=()):
    reset()
    bpy.ops.import_scene.gltf(filepath=path)
    sc = bpy.context.scene
    for o in [o for o in sc.objects if o.type == "MESH" and any(k in o.name for k in skip)]:
        delete([o])
    qa_neutral_vcols()
    objs = [o for o in sc.objects if o.type == "MESH"]
    x = 0.0
    for o in objs:
        co = np.array([o.matrix_world @ Vector(c) for c in o.bound_box])
        w = co[:, 0].max() - co[:, 0].min()
        o.location.x += x + w / 2 - (co[:, 0].max() + co[:, 0].min()) / 2
        x += w + 0.4
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    for m in bpy.data.materials:
        m.surface_render_method = "DITHERED"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 500
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 1.2
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(45), 0, math.radians(35))
    hmax = max(max((o.matrix_world @ Vector(c)).z for c in o.bound_box) for o in objs)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = max(x, hmax * 3.2) * 1.02
    cam.location = (x / 2, -200, hmax * 0.45 + 20); cam.rotation_euler = (math.radians(84), 0, 0)
    cam.data.clip_end = 1000
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    if QA_ONLY:
        for spec in TREES:
            if wanted(spec["id"]):
                qa_tree(spec["id"], os.path.join(OUT, spec["id"] + ".glb"), json.load(open(os.path.join(CACHE, spec["id"] + "_extras.json"))))
        qa_lineup(os.path.join(OUT, "trees_far.glb"), os.path.join(QA, "trees_lod1.png"), skip=("Impostor",))
        qa_lineup(os.path.join(OUT, "forest_pack.glb"), os.path.join(QA, "forest_pack.png"))
        return
    for slot, spec in enumerate(TREES):
        if not wanted(spec["id"]):
            continue
        sid = spec["id"]
        lod0, lod1, extras = tree_species(spec, make_lod1_atlas(), None, slot)
        path = os.path.join(OUT, sid + ".glb")
        for o in [o for o in bpy.context.scene.objects if o not in (lod0, lod1) and o.type == "MESH"]:
            delete([o])
        export_glb([(lod0, {})], path, sid, extras)
        # LOD1 waits in the cache until the shared atlas is assembled.
        for o in [o for o in bpy.context.scene.objects if o != lod1]:
            delete([o])
        select_only([lod1])
        bpy.ops.export_scene.gltf(filepath=os.path.join(CACHE, sid + "_lod1.glb"), export_format="GLB", use_selection=True,
                                  export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_materials="PLACEHOLDER",
                                  export_animations=False)
        json.dump(extras, open(os.path.join(CACHE, sid + "_extras.json"), "w"))
        qa_tree(sid, path, extras)
    if wanted("forest_pack"):
        forest_pack()
    if not ONLY or any(s["id"] in ONLY for s in TREES) or "trees_far" in ONLY or "forest_pack" in ONLY:
        # Every species' LOD1 with one shared atlas, plus the impostor card and its atlas.
        reset()
        slots = [(i, s["id"]) for i, s in enumerate(TREES) if os.path.exists(os.path.join(CACHE, s["id"] + "_lod1.glb"))]
        mat = finish_lod1_atlas(slots)
        entries = []
        for slot, sid in slots:
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=os.path.join(CACHE, sid + "_lod1.glb"))
            new = [x for x in bpy.data.objects if x not in before]
            o = next(x for x in new if x.type == "MESH")
            for x in new:
                if x != o:
                    delete([x])
            o.parent = None
            o.matrix_world = Matrix.Identity(4)
            o.data.materials.clear(); o.data.materials.append(mat)
            if o.data.color_attributes:
                o.data.color_attributes.active_color = o.data.color_attributes[0]
            o.name = o.data.name = sid + "_LOD1"
            entries.append((o, json.load(open(os.path.join(CACHE, sid + "_extras.json")))))
        far_slots = list(slots) + [(slot, "fp_tree_%d" % i) for i, slot in FOREST_IMPOSTORS.items()
                                   if os.path.exists(os.path.join(CACHE, "fp_tree_%d_far0.npy" % i))]
        imp = finish_far_atlas(far_slots)
        entries.append((imp, {"grid": [8, 4]}))
        export_glb(entries, os.path.join(OUT, "trees_far.glb"), "TreesFar")
        if DO_QA:
            qa_lineup(os.path.join(OUT, "trees_far.glb"), os.path.join(QA, "trees_lod1.png"), skip=("Impostor",))
    if wanted("garden"):
        garden()
    rp = os.path.join(QA, "landscape_report.json")
    old = json.load(open(rp)) if os.path.exists(rp) else {}
    old.update(REPORT)
    json.dump(old, open(rp, "w"), indent=1)
    log("done in %.0fs" % (time.time() - t0))

main()
