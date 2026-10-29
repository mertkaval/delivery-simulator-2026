"""Street trees and planting from the game's landscape kit (assets/landscape/*.glb, built by
tools/prepare_landscape.py) as an MRS library, so placement in Blender and the Godot export use the very
same detailed trees: real bark / leaf-card textures, LOD0 + LOD1 (one shared atlas) + impostor in the game.

Why: the generated `Tree_Variants` trees lose their alpha leaf cards in the engine export (blob / frond
canopies only); the landscape kit trees were built for Godot (alpha-scissor leaf clusters with mipmapped
anisotropic filtering, crown AO + wind weights in COLOR_0, LODs that keep the crown silhouette).

`build_game_trees()` imports every species once into collection `MRS_GameTrees`:
  MRS_GTree_<sid>       LOD0 mesh (origin at the trunk base, real size)
  MRS_GTree_<sid>_LOD1  LOD1 mesh (shared atlas material)
custom properties: mrs_species, mrs_tree_height, mrs_crown_radius, mrs_crown_base, mrs_trunk_radius,
mrs_far_slot, mrs_source (res:// path).
v5 (docs/roads/FOLIAGE.md, default): the shading model shared with world/roads/mrs_foliage.gdshader (_v5_material), the
MRS LOD1 and hemi-octahedral impostors of assets/roads/foliage/ (bake_foliage_assets) and regraded hedge textures;
MrsFoliage (world/roads/mrs_foliage.gd) is the Godot side. Plants (grass, shrubs, hedges, boxwood, flower beds) go to
`MRS_GamePlants` as MRS_GPlant_<id>. Materials are rebuilt to match the game shader: albedo x crown AO
(COLOR_0.a), alpha clip 0.42 for leaves, roughness 0.78 leaves / 0.9 bark, a little translucency.
"""
import bpy, os, math, json
from .nodes import MRS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DIR = os.path.join(ROOT, "assets", "landscape")
TREES = ["plane_tree", "maple_a", "maple_b", "maple_c", "walnut_spring", "walnut_autumn_a", "walnut_autumn_b",
         "linden_a", "linden_b", "linden_c", "cherry", "grove_a", "grove_b"]
PLANT_FILES = {"garden": ["grass_a", "grass_b", "shrub_a", "shrub_b", "shrub_c", "bed_edging"],
               "yard": ["boxwood_ball", "hedge_section", "flower_bed_a", "flower_bed_b", "flower_bed_c", "flower_bed_d"]}
# street-tree pools by street style (species chosen for silhouette: avenue = big plane trees / lindens)
STREET_POOLS = {"avenue": ["plane_tree", "linden_a", "linden_b", "linden_c"], "residential": ["linden_a", "linden_c", "maple_a", "maple_b", "cherry"],
                "boulevard": ["plane_tree", "plane_tree", "linden_b"], "park": ["walnut_spring", "grove_a", "grove_b", "linden_b", "maple_c"]}
TREE_COL = MRS + "GameTrees"; PLANT_COL = MRS + "GamePlants"

# ---- v5 (docs/roads/FOLIAGE.md): one foliage shading model shared with world/roads/mrs_foliage.gdshader
FOLIAGE = os.path.join(ROOT, "assets", "roads", "foliage")     # MRS LOD1 meshes, impostor atlases, hedge textures
V5 = {"alpha_cut": 0.42,          # leaf-card alpha test (the kit's glTF alphaCutoff)
      "translucency": 0.25,       # Mix(Principled, Translucent, 0.25): thin-sheet leaves (Godot: custom light())
      "rough_leaf": 0.78, "rough_bark": 0.9, "rough_solid": 0.85,
      "crown_normals_both_sides": True}   # leaf cards keep their soft crown normal on the back face too
SOLID_FOLIAGE = ("yardleaf_hedge",)       # the clipped hedge / boxwood core: dense opaque leaf surface, no translucency
PLAIN = ("bed_stone", "bed_mulch", "yard_ground", "rock", "plant_Material__1", "plant_Material__6", "plant_Material__13")
HEDGE_TEXTURES = {"yard_hedge_leaves": "mrs_hedge_leaves.png", "yard_hedge_sprays": "mrs_hedge_sprays.png"}
HEDGE_TARGET_LUM = 0.13           # mean linear luminance of the regraded hedge leaves (kit: 0.042; garden shrubs: 0.22)
IMP_N = 8                         # hemi-octahedral impostor: IMP_N x IMP_N views over the upper hemisphere
IMP_PX = 64                       # albedo frame (px): ~1:1 with a tree at the impostor start (163 m, 78° game fov, 720p: ~35-50 px)
IMP_NPX = 32                      # normal frame (px); atlases 2048² / 1024² (asset budget: no 3D texture above 2048 px)
IMP_GRID = 4                      # species slots per atlas side (13 trees in a 4 x 4 atlas)
LOD1_KEEP = 0.4                   # fraction of LOD0 leaf cards kept in the MRS LOD1 ...
LOD1_GROW = 1.45                  # ... each grown by this factor about its centre (total card area ~ kept)
LOD1_BARK = 0.3                   # bark decimation ratio
_VERSION = [4]


def material_kind(name):
    """bark | solid (hedge core) | plain (stone, mulch, pots) | leaves - the same split as MrsFoliage.kind()."""
    n = name.split(".")[0]
    if n.endswith("_bark") or "trunk" in n.lower(): return "bark"
    if n in SOLID_FOLIAGE: return "solid"
    if n in PLAIN or n.startswith("rock") or n.startswith("yard_"): return "plain"
    return "leaves"


def _library_collection(name):
    from .props import collection
    return collection(name)


def _import(path):
    before = set(bpy.data.objects); cols = set(bpy.data.collections); scenes = set(bpy.data.scenes)
    bpy.ops.import_scene.gltf(filepath=path, import_shading="NORMALS", merge_vertices=False)
    new = [o for o in bpy.data.objects if o not in before]
    _NEW.append((set(bpy.data.collections) - cols, set(bpy.data.scenes) - scenes))
    return new


_NEW = []        # collections / scenes the glTF importer created (the kit GLBs carry scenes named Bake / Scene)


def _cleanup_import_leftovers():
    for cols, scenes in _NEW:
        for c in cols:
            try:
                if len(c.all_objects) == 0 and len(c.children) == 0: bpy.data.collections.remove(c)
            except ReferenceError: pass
        for s in scenes:
            try:
                if len(s.objects) == 0 and s != bpy.context.scene: bpy.data.scenes.remove(s)
            except ReferenceError: pass
    _NEW.clear()


def _game_material(m, leaves):
    """Rebuild an imported glTF material like foliage_wind.gdshader: albedo x COLOR_0.a (crown AO),
    alpha clip for cut-out leaves, uniform roughness, a little translucency on leaves."""
    if m is None or m.get("mrs_game_mat"): return m
    nt = m.node_tree
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None and "norm" not in n.image.name.lower() and not n.image.name.lower().endswith("_n")), None)
    ntex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None and n is not tex and ("norm" in n.image.name.lower() or n.image.name.lower().endswith("_n"))), None)
    img = tex.image if tex else None; nimg = ntex.image if ntex else None
    cut = m.blend_method in ("CLIP", "HASHED", "BLEND") or getattr(m, "surface_render_method", "") == "DITHERED" and leaves
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (700, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (350, 0)
    b.inputs["Roughness"].default_value = 0.78 if leaves else 0.9
    if img:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.location = (-500, 100); t.interpolation = "Linear"
        ca = nt.nodes.new("ShaderNodeVertexColor"); ca.location = (-500, -200)
        try: ca.layer_name = "Color"
        except Exception: pass
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.location = (-150, 100)
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(t.outputs["Color"], mul.inputs[6])
        # ao = COLOR_0.a: multiply the albedo by (a, a, a)
        cmb = nt.nodes.new("ShaderNodeCombineColor"); cmb.location = (-300, -200)
        for k in ("Red", "Green", "Blue"): nt.links.new(ca.outputs["Alpha"], cmb.inputs[k])
        nt.links.new(cmb.outputs[0], mul.inputs[7])
        nt.links.new(mul.outputs[2], b.inputs["Base Color"])
        if leaves:
            nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
            b.inputs["Subsurface Weight"].default_value = 0.0
            try: b.inputs["Transmission Weight"].default_value = 0.0
            except KeyError: pass
            # translucency: a thin-sheet look via a Translucent BSDF mixed in
            tr = nt.nodes.new("ShaderNodeBsdfTranslucent"); tr.location = (350, -300); nt.links.new(mul.outputs[2], tr.inputs["Color"])
            mx = nt.nodes.new("ShaderNodeMixShader"); mx.location = (550, 0); mx.inputs[0].default_value = 0.25
            # keep the alpha cut-out on both shaders: transparent where alpha < cut
            tp = nt.nodes.new("ShaderNodeBsdfTransparent"); tp.location = (550, -250)
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.42; gt.location = (350, -500)
            nt.links.new(t.outputs["Alpha"], gt.inputs[0])
            mx2 = nt.nodes.new("ShaderNodeMixShader"); mx2.location = (650, -100)
            nt.links.new(b.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
            nt.links.new(gt.outputs[0], mx2.inputs[0]); nt.links.new(tp.outputs[0], mx2.inputs[1]); nt.links.new(mx.outputs[0], mx2.inputs[2])
            nt.links.new(mx2.outputs[0], out.inputs["Surface"])
            b.inputs["Alpha"].default_value = 1.0
            try: nt.links.remove(next(l for l in nt.links if l.to_socket == b.inputs["Alpha"]))
            except StopIteration: pass
        else:
            nt.links.new(b.outputs[0], out.inputs["Surface"])
        if nimg:
            nt2 = nt.nodes.new("ShaderNodeTexImage"); nt2.image = nimg; nimg.colorspace_settings.name = "Non-Color"; nt2.location = (-500, -500)
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-150, -500); nt.links.new(nt2.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    else:
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    try: m.surface_render_method = "DITHERED"
    except Exception: pass
    m.use_backface_culling = False
    m["mrs_game_mat"] = 1
    return m


def _take_mesh(obj, name, col, props):
    me = obj.data.copy(); me.name = name
    o = bpy.data.objects.get(name)
    if o is None: o = bpy.data.objects.new(name, me); col.objects.link(o)
    else:
        old = o.data; o.data = me
        if old.users == 0: bpy.data.meshes.remove(old)
    o.location = (0, 0, 0); o.rotation_euler = (0, 0, 0); o.scale = (1, 1, 1)
    for k, v in props.items(): o[k] = v
    for i, m in enumerate(me.materials):
        if m is None: continue
        if _VERSION[0] >= 5:
            _v5_material(m, material_kind(m.name))
            continue
        leaves = not (m.name.endswith("_bark") or "trunk" in m.name.lower() or m.name in ("bed_stone", "bed_mulch", "yard_ground"))
        _game_material(m, leaves)
    o.hide_render = True
    return o


def _cleanup(objs):
    for o in objs:
        d = o.data
        bpy.data.objects.remove(o)
        if d is not None and isinstance(d, bpy.types.Mesh) and d.users == 0: bpy.data.meshes.remove(d)


def build_game_trees(plants=True, version=5):
    """Import the landscape kit trees (LOD0 + LOD1) and plants into MRS_GameTrees / MRS_GamePlants.
    version 5 (default): v5 materials (the shading model of world/roads/mrs_foliage.gdshader, docs/roads/FOLIAGE.md), the
    MRS LOD1 meshes of assets/roads/foliage/<sid>_lod1.glb (kit LOD1 if not baked) and the regraded hedge / boxwood
    textures. version 4: the v4 materials (_game_material) and the kit LOD1 (kept for comparison)."""
    _VERSION[0] = version
    tcol = _library_collection(TREE_COL)
    far = _import(os.path.join(DIR, "trees_far.glb"))
    far_meshes = {o.name.split(".")[0]: o for o in far if o.type == "MESH"}
    for sid in TREES:
        objs = _import(os.path.join(DIR, sid + ".glb"))
        lod0 = next((o for o in objs if o.type == "MESH"), None)
        holder = next((o for o in objs if o.name.split(".")[0] == sid), None) or (lod0.parent if lod0 else None)
        ex = {k: holder[k] for k in holder.keys()} if holder is not None else {}
        props = {"mrs_species": sid, "mrs_tree_height": float(ex.get("height", 10.0)), "mrs_crown_radius": float(ex.get("crown_radius", 3.0)),
                 "mrs_crown_base": float(ex.get("crown_base", 2.5)), "mrs_trunk_radius": float(ex.get("trunk_radius", 0.25)),
                 "mrs_far_slot": int(ex.get("far_slot", TREES.index(sid))), "mrs_far_size": float(ex.get("far_size", ex.get("height", 10.0))),
                 "mrs_source": "res://assets/landscape/%s.glb" % sid}
        if lod0 is not None:
            o = _take_mesh(lod0, MRS + "GTree_" + sid, tcol, props)
            # measured crown reach (the catalogue radius can be smaller than the leaf cards' extent)
            xs = [v.co.x for v in o.data.vertices]; ys = [v.co.y for v in o.data.vertices]
            o["mrs_crown_reach"] = max(max(abs(min(xs)), max(xs)), max(abs(min(ys)), max(ys)), props["mrs_crown_radius"])
        l1 = far_meshes.get(sid + "_LOD1")
        v5l1 = os.path.join(FOLIAGE, sid + "_lod1.glb")
        if version >= 5 and os.path.exists(v5l1) and lod0 is not None:
            l1objs = _import(v5l1)
            l1 = next((o for o in l1objs if o.type == "MESH"), None)
            if l1 is not None:
                lo = _take_mesh(l1, MRS + "GTree_" + sid + "_LOD1", tcol, dict(props, mrs_lod=1, mrs_source="res://assets/roads/foliage/%s_lod1.glb" % sid))
                # the MRS LOD1 shares the LOD0 materials (same textures, same shading)
                l0m = {m.name.split(".")[0]: m for m in bpy.data.objects[MRS + "GTree_" + sid].data.materials if m}
                for i, m in enumerate(lo.data.materials):
                    if m is not None and m.name.split(".")[0] in l0m: lo.data.materials[i] = l0m[m.name.split(".")[0]]
            _cleanup(l1objs)
        elif l1 is not None: _take_mesh(l1, MRS + "GTree_" + sid + "_LOD1", tcol, dict(props, mrs_lod=1))
        for nm in (MRS + "GTree_" + sid, MRS + "GTree_" + sid + "_LOD1"):      # library trees stand at the origin: keep them out of
            if bpy.data.objects.get(nm): bpy.data.objects[nm].hide_viewport = True   # the viewport (placed copies are new objects)
        _cleanup(objs)
    _cleanup(far)
    if plants:
        pcol = _library_collection(PLANT_COL)
        for f, ids in PLANT_FILES.items():
            objs = _import(os.path.join(DIR, f + ".glb"))
            for pid in ids:
                src = next((o for o in objs if o.type == "MESH" and o.name.split(".")[0] == pid), None)
                if src is None: continue
                zs = [v.co.z for v in src.data.vertices]; xs = [v.co.x for v in src.data.vertices]; ys = [v.co.y for v in src.data.vertices]
                _take_mesh(src, MRS + "GPlant_" + pid, pcol, {"mrs_plant": pid, "mrs_height": max(zs) - min(zs), "mrs_size": [max(xs) - min(xs), max(ys) - min(ys)],
                                                              "mrs_source": "res://assets/landscape/%s.glb#%s" % (f, pid)})
            _cleanup(objs)
    _cleanup_import_leftovers()
    return tcol


def tree_info(lib_name):
    o = bpy.data.objects.get(lib_name)
    if o is None: return None
    return {"height": o.get("mrs_tree_height", 10.0), "crown": o.get("mrs_crown_reach", o.get("mrs_crown_radius", 3.0)),
            "crown_base": o.get("mrs_crown_base", 2.5), "trunk": o.get("mrs_trunk_radius", 0.25), "species": o.get("mrs_species")}


def tri_counts():
    out = {}
    for o in bpy.data.collections[TREE_COL].objects:
        out[o.name] = (sum(len(p.vertices) - 2 for p in o.data.polygons), len(o.data.materials))
    return out


# ============================================================================= v5 materials
def _images_of(m):
    """(albedo image, normal image) of a material: imported glTF or an earlier v4 / v5 game material."""
    imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image is not None]
    isn = lambda im: "norm" in im.name.lower() or im.name.lower().split(".")[0].endswith("_n") or im.colorspace_settings.name == "Non-Color"
    alb = next((im for im in imgs if not isn(im)), None)
    nrm = next((im for im in imgs if isn(im) and im is not alb), None)
    return alb, nrm


def hedge_image(img):
    """The MRS regrade of a yard-kit hedge / boxwood texture (assets/roads/foliage/mrs_hedge_*.png)."""
    if img is None: return None
    key = img.name.split(".")[0]
    for k, fn in HEDGE_TEXTURES.items():
        if key.endswith(k) or key.startswith("mrs_hedge"):
            if key.startswith("mrs_hedge"): return img
            path = os.path.join(FOLIAGE, fn)
            if not os.path.exists(path): regrade_hedge_textures()
            return bpy.data.images.load(path, check_existing=True)
    return img


def _v5_material(m, kind):
    """The v5 foliage shading model (identical to world/roads/mrs_foliage.gdshader):
       albedo = texture x COLOR_0.a (crown / bark AO; potted plants: none)
       leaves  Mix(Principled(rough 0.78, F0 0.04), Translucent, 0.25), thin-slab thickness 0; alpha test 0.42 on the full-resolution
               texel (Closest: no mipmap thinning - the coverage Cycles / supersampling gives); the soft crown normal
               is used on both sides of a card (no back-face flip), so a crown shades like one rounded volume
       bark    Principled(rough 0.9) + normal map, opaque
       solid   hedge / boxwood core: Principled(rough 0.85), opaque, regraded texture
       plain   bed stone, mulch, pots: the imported base colour, no vertex AO"""
    if m is None or m.get("mrs_v5"): return m
    nt = m.node_tree
    img, nimg = _images_of(m)
    if m.name.startswith("yardleaf"):
        img = hedge_image(img)
    base_rgba = None
    bsdf0 = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf0 is not None: base_rgba = tuple(bsdf0.inputs["Base Color"].default_value)
    nt.nodes.clear()
    L = nt.links
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (350, 100)
    b.inputs["Roughness"].default_value = {"leaves": V5["rough_leaf"], "bark": V5["rough_bark"], "solid": V5["rough_solid"]}.get(kind, 0.9)
    b.inputs["Specular IOR Level"].default_value = 0.5
    if base_rgba is not None: b.inputs["Base Color"].default_value = base_rgba
    base = None
    if img is not None:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.location = (-600, 200); t.interpolation = "Linear"
        base = t.outputs["Color"]
        if kind != "plain" and not m.name.startswith("plant_"):
            ca = nt.nodes.new("ShaderNodeVertexColor"); ca.location = (-600, -150)
            try: ca.layer_name = "Color"
            except Exception: pass
            cmb = nt.nodes.new("ShaderNodeCombineColor"); cmb.location = (-400, -150)
            for k in ("Red", "Green", "Blue"): L.new(ca.outputs["Alpha"], cmb.inputs[k])
            mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.location = (-200, 150)
            mul.inputs["Factor"].default_value = 1.0
            L.new(t.outputs["Color"], mul.inputs[6]); L.new(cmb.outputs[0], mul.inputs[7])
            base = mul.outputs[2]
        L.new(base, b.inputs["Base Color"])
    if kind == "leaves":
        nrm = None
        if V5["crown_normals_both_sides"]:
            geo = nt.nodes.new("ShaderNodeNewGeometry"); geo.location = (-600, -450)
            sgn = nt.nodes.new("ShaderNodeMath"); sgn.operation = "MULTIPLY_ADD"; sgn.location = (-400, -450)
            L.new(geo.outputs["Backfacing"], sgn.inputs[0]); sgn.inputs[1].default_value = -2.0; sgn.inputs[2].default_value = 1.0
            sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.location = (-200, -450)
            L.new(geo.outputs["Normal"], sc.inputs[0]); L.new(sgn.outputs[0], sc.inputs["Scale"])
            nrm = sc.outputs[0]
            L.new(nrm, b.inputs["Normal"])
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent"); tr.location = (350, -250)
        if base is not None: L.new(base, tr.inputs["Color"])
        if nrm is not None: L.new(nrm, tr.inputs["Normal"])
        mx = nt.nodes.new("ShaderNodeMixShader"); mx.location = (550, 0); mx.inputs[0].default_value = V5["translucency"]
        L.new(b.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
        surf = mx.outputs[0]
        if img is not None:
            ta = nt.nodes.new("ShaderNodeTexImage"); ta.image = img; ta.location = (-600, -700); ta.interpolation = "Closest"
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = V5["alpha_cut"]; gt.location = (350, -550)
            L.new(ta.outputs["Alpha"], gt.inputs[0])
            tp = nt.nodes.new("ShaderNodeBsdfTransparent"); tp.location = (550, -300)
            mx2 = nt.nodes.new("ShaderNodeMixShader"); mx2.location = (720, 0)
            L.new(gt.outputs[0], mx2.inputs[0]); L.new(tp.outputs[0], mx2.inputs[1]); L.new(surf, mx2.inputs[2])
            surf = mx2.outputs[0]
        L.new(surf, out.inputs["Surface"])
        # leaves are thin sheets: EEVEE's default (sphere) thickness lights the Translucent closure from the world
        # far too little (canopies 22 % darker than Cycles / Godot); a zero-thickness slab transmits as a thin leaf
        try: m.thickness_mode = "SLAB"
        except Exception: pass
        th = nt.nodes.new("ShaderNodeValue"); th.location = (720, -250); th.outputs[0].default_value = 0.0
        L.new(th.outputs[0], out.inputs["Thickness"])
    else:
        L.new(b.outputs[0], out.inputs["Surface"])
        if nimg is not None and kind == "bark":
            nimg.colorspace_settings.name = "Non-Color"
            t2 = nt.nodes.new("ShaderNodeTexImage"); t2.image = nimg; t2.location = (-600, -500)
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-200, -500)
            L.new(t2.outputs["Color"], nm.inputs["Color"]); L.new(nm.outputs[0], b.inputs["Normal"])
    try: m.surface_render_method = "DITHERED"
    except Exception: pass
    m.use_backface_culling = False
    m["mrs_v5"] = 1; m["mrs_kind"] = kind
    m["mrs_game_mat"] = 1
    return m


def upgrade_materials(version=5):
    """Rebuild the materials of an existing library (e.g. a saved street block) with the v5 model."""
    done = 0
    for cn in (TREE_COL, PLANT_COL):
        col = bpy.data.collections.get(cn)
        if col is None: continue
        for o in col.objects:
            for m in o.data.materials:
                if m is not None and not m.get("mrs_v5"):
                    _v5_material(m, material_kind(m.name)); done += 1
    return done


# ============================================================================= v5 assets (assets/roads/foliage)
def _np():
    import numpy as np
    return np


def _read_png(path):
    """Pixels of a PNG as float RGBA, row 0 = top. 8-bit sRGB PNGs come back as stored (sRGB-encoded)."""
    np = _np()
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"            # raw stored values, no colour conversion
    w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1].copy()


def _write_png(px, path):
    """Writes raw values (already encoded as the file should store them)."""
    np = _np()
    h, w = px.shape[:2]
    im = bpy.data.images.new("tmp_write", w, h, alpha=True, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    im.alpha_mode = "STRAIGHT"
    im.pixels.foreach_set(np.ascontiguousarray(np.clip(px[::-1], 0, 1)).astype(np.float32).ravel())
    im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)
    return path


def _dilate(px, passes=5):
    """Bleed opaque colours into transparent texels so mipmaps / bilinear filtering keep edge colours."""
    np = _np()
    rgb, a = px[..., :3].copy(), px[..., 3:4].copy()
    acc, wsum = rgb * a, a.copy()
    out = rgb.copy(); filled = a[..., 0] > 0.5
    for r in [1, 2, 4, 8, 16, 32][:passes]:
        k_acc = np.zeros_like(acc); k_w = np.zeros_like(wsum)
        for dy in (-r, 0, r):
            for dx in (-r, 0, r):
                k_acc += np.roll(np.roll(acc, dy, 0), dx, 1); k_w += np.roll(np.roll(wsum, dy, 0), dx, 1)
        acc, wsum = k_acc, k_w
        ok = (wsum[..., 0] > 1e-4) & ~filled
        out[ok] = acc[ok] / wsum[ok]; filled |= ok
    mean = (rgb * a).reshape(-1, 3).sum(0) / max(1e-4, float(a.sum()))
    out[~filled] = mean
    res = px.copy(); res[..., :3] = np.where(a > 0.5, rgb, out)
    return res


def _srgb_to_lin(c):
    np = _np(); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(c):
    np = _np(); c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


LUM = (0.2126, 0.7152, 0.0722)


def regrade_hedge_textures():
    """The yard kit paints its hedge / boxwood leaves at linear luminance 0.042 (5x darker than the garden
    shrubs' 0.22): near-black under the street lighting. MRS copies: linear RGB scaled so the leaf texels average
    HEDGE_TARGET_LUM, 15 % less saturated (privet / box green), the leaf gaps lifted from black to deep green."""
    np = _np()
    os.makedirs(FOLIAGE, exist_ok=True)
    rep = {}
    W = np.array(LUM)
    for k, fn in HEDGE_TEXTURES.items():
        px = _read_png(os.path.join(DIR, "yard_" + k + ".png"))
        rgb = _srgb_to_lin(px[..., :3]); a = px[..., 3]
        m = a > 0.42
        lum = rgb @ W
        cur = float(lum[m].mean())
        g = rgb * (HEDGE_TARGET_LUM / max(cur, 1e-4))
        gl = (g @ W)[..., None]
        g = gl + (g - gl) * 0.85
        g = np.maximum(g, np.array([0.010, 0.020, 0.007]))           # gaps: deep green, not black
        out = px.copy(); out[..., :3] = _lin_to_srgb(g)
        _write_png(out, os.path.join(FOLIAGE, fn))
        chk = _read_png(os.path.join(FOLIAGE, fn))
        newl = float((_srgb_to_lin(chk[..., :3]) @ W)[m].mean())
        rep[k] = {"lum_before": round(cur, 4), "lum_after": round(newl, 4), "gain": round(HEDGE_TARGET_LUM / max(cur, 1e-4), 2)}
    with open(os.path.join(FOLIAGE, "hedge_regrade.json"), "w") as f: json.dump(rep, f, indent=1)
    print("[foliage] hedge regrade", rep, flush=True)
    return rep


def _islands(me, faces):
    """Connected components (shared vertices) of the given polygon indices -> list of polygon index lists."""
    parent = {}
    def find(x):
        root = x
        while parent.get(root, root) != root: root = parent[root]
        while parent.get(x, x) != root:
            nxt = parent[x]; parent[x] = root; x = nxt
        return root
    for pi in faces:
        vs = me.polygons[pi].vertices
        r0 = find(vs[0])
        for v in vs[1:]:
            r = find(v)
            if r != r0: parent[r] = r0
    groups = {}
    for pi in faces:
        groups.setdefault(find(me.polygons[pi].vertices[0]), []).append(pi)
    return list(groups.values())


def make_lod1(lod0, sid, keep=None, grow=None, bark_ratio=None, seed=7):
    """MRS LOD1 from the LOD0 mesh: a random subset (keep) of the leaf cards / clusters, each grown about its
    centre (grow, so the total card area ~ stays), bark decimated (bark_ratio); same materials, same COLOR_0
    wind / AO data and crown normals as LOD0, so LOD0 -> LOD1 changes the card count, not the look."""
    import bmesh, random
    keep = LOD1_KEEP if keep is None else keep; grow = LOD1_GROW if grow is None else grow
    bark_ratio = LOD1_BARK if bark_ratio is None else bark_ratio
    rnd = random.Random(seed + sum(ord(c) for c in sid))
    sc = bpy.context.scene
    kinds = [material_kind(m.name) if m else "plain" for m in lod0.data.materials]
    # ---- leaves: subset + grow (custom normals are per-loop data: they survive vertex moves / face deletes)
    me = lod0.data.copy(); me.name = sid + "_LOD1"
    leaf_faces = [p.index for p in me.polygons if kinds[p.material_index] == "leaves"]
    isl = _islands(me, leaf_faces)
    drop = set(p.index for p in me.polygons if kinds[p.material_index] == "bark")
    kept = 0
    co = [v.co.copy() for v in me.vertices]
    for g in isl:
        if rnd.random() > keep:
            drop.update(g); continue
        kept += 1
        vs = sorted({v for pi in g for v in me.polygons[pi].vertices})
        c = co[vs[0]] * 0
        for v in vs: c += co[v]
        c /= len(vs)
        for v in vs: me.vertices[v].co = c + (co[v] - c) * grow
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sorted(drop)], context="FACES")
    bm.to_mesh(me); bm.free()
    leaves_obj = bpy.data.objects.new(sid + "_LOD1", me); sc.collection.objects.link(leaves_obj)
    # ---- bark: separate copy, decimated
    bark_me = lod0.data.copy(); bark_me.name = sid + "_LOD1_bark"
    bm = bmesh.new(); bm.from_mesh(bark_me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if kinds[f.material_index] != "bark"], context="FACES")
    bm.to_mesh(bark_me); bm.free()
    bark_obj = bpy.data.objects.new(sid + "_LOD1_bark", bark_me); sc.collection.objects.link(bark_obj)
    if len(bark_me.polygons):
        mod = bark_obj.modifiers.new("dec", "DECIMATE"); mod.ratio = bark_ratio; mod.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        nm = bpy.data.meshes.new_from_object(bark_obj.evaluated_get(dg), depsgraph=dg)
        bark_obj.modifiers.clear(); old = bark_obj.data; bark_obj.data = nm; bpy.data.meshes.remove(old)
    for o in sc.objects: o.select_set(False)
    leaves_obj.select_set(True); bark_obj.select_set(True); bpy.context.view_layer.objects.active = leaves_obj
    with bpy.context.temp_override(active_object=leaves_obj, selected_editable_objects=[leaves_obj, bark_obj], object=leaves_obj):
        bpy.ops.object.join()
    o = leaves_obj
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    return o, {"islands": len(isl), "kept": kept, "tris": tris}


def _export_glb(objs, path, root_name, extras):
    sc = bpy.context.scene
    root = bpy.data.objects.new(root_name, None); sc.collection.objects.link(root)
    for k, v in extras.items(): root[k] = v
    for o in objs:
        if o.name not in sc.collection.objects: sc.collection.objects.link(o)
        o.parent = root
    for o in sc.objects: o.select_set(False)
    for o in [root] + objs: o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True,
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_normals=True,
                              export_animations=False, export_morph=False, export_image_format="NONE", export_apply=False,
                              export_yup=True, export_tangents=False)
    bpy.data.objects.remove(root)
    return path


# ---- hemi-octahedral impostors -------------------------------------------------------------------------------
def hemi_oct_dir(i, j, n=IMP_N):
    """Godot-space (y up) unit view direction of frame (i, j) of an n x n hemi-octahedral grid
    (the mapping of world/roads/mrs_foliage_impostor.gdshader)."""
    a = i / (n - 1) * 2.0 - 1.0; b = j / (n - 1) * 2.0 - 1.0
    px, pz = (a + b) * 0.5, (a - b) * 0.5
    y = 1.0 - abs(px) - abs(pz)
    l = math.sqrt(px * px + y * y + pz * pz)
    return (px / l, y / l, pz / l)


def _g2b(v):      # Godot (x, y, z) -> Blender (x, -z, y)
    return (v[0], -v[2], v[1])


def _frame_basis_g(d):
    """Frame right / up (Godot space) for view direction d (towards the viewer): right = Y x d, up = d x right."""
    rx, ry, rz = d[2], 0.0, -d[0]
    l = math.sqrt(rx * rx + rz * rz)
    if l < 1e-5: rx, rz, l = 1.0, 0.0, 1.0
    r = (rx / l, 0.0, rz / l)
    u = (d[1] * r[2] - d[2] * r[1], d[2] * r[0] - d[0] * r[2], d[0] * r[1] - d[1] * r[0])
    return r, u


def _bake_materials(src_mats, mode):
    """Emission copies of the v5 materials for the impostor bake: 'albedo' = texture x AO (alpha test as the
    v5 leaves), 'normal' = shading normal (crown normal on both card sides for leaves) as 0.5 + 0.5 n."""
    out = []
    for m in src_mats:
        kind = material_kind(m.name) if m else "plain"
        bm = bpy.data.materials.new("bake_%s_%s" % (mode, m.name if m else "none")); bm.use_nodes = True
        nt = bm.node_tree; nt.nodes.clear(); L = nt.links
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        img = _images_of(m)[0] if m else None
        if m is not None and m.name.startswith("yardleaf"): img = hedge_image(img)
        if mode == "albedo":
            if img is not None:
                t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = "Linear"
                ca = nt.nodes.new("ShaderNodeVertexColor")
                try: ca.layer_name = "Color"
                except Exception: pass
                mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
                cmb = nt.nodes.new("ShaderNodeCombineColor")
                for k in ("Red", "Green", "Blue"): L.new(ca.outputs["Alpha"], cmb.inputs[k])
                L.new(t.outputs["Color"], mul.inputs[6]); L.new(cmb.outputs[0], mul.inputs[7])
                L.new(mul.outputs[2], em.inputs["Color"])
            else:
                em.inputs["Color"].default_value = (0.3, 0.3, 0.3, 1)
        else:
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nrm = geo.outputs["Normal"]
            if kind == "leaves" and V5["crown_normals_both_sides"]:
                sgn = nt.nodes.new("ShaderNodeMath"); sgn.operation = "MULTIPLY_ADD"
                L.new(geo.outputs["Backfacing"], sgn.inputs[0]); sgn.inputs[1].default_value = -2.0; sgn.inputs[2].default_value = 1.0
                sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"
                L.new(nrm, sc.inputs[0]); L.new(sgn.outputs[0], sc.inputs["Scale"]); nrm = sc.outputs[0]
            ma = nt.nodes.new("ShaderNodeVectorMath"); ma.operation = "MULTIPLY_ADD"
            L.new(nrm, ma.inputs[0]); ma.inputs[1].default_value = (0.5, 0.5, 0.5); ma.inputs[2].default_value = (0.5, 0.5, 0.5)
            L.new(ma.outputs[0], em.inputs["Color"])
        surf = em.outputs[0]
        if kind == "leaves" and img is not None:
            ta = nt.nodes.new("ShaderNodeTexImage"); ta.image = img; ta.interpolation = "Closest"
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = V5["alpha_cut"]
            L.new(ta.outputs["Alpha"], gt.inputs[0])
            tp = nt.nodes.new("ShaderNodeBsdfTransparent")
            mx = nt.nodes.new("ShaderNodeMixShader")
            L.new(gt.outputs[0], mx.inputs[0]); L.new(tp.outputs[0], mx.inputs[1]); L.new(surf, mx.inputs[2]); surf = mx.outputs[0]
        L.new(surf, o.inputs["Surface"])
        try: bm.surface_render_method = "DITHERED"
        except Exception: pass
        out.append(bm)
    return out


def bake_impostors(lod0_by_sid, samples=24):
    """Hemi-octahedral impostor atlases of every species' LOD0 (v5 materials):
       assets/roads/foliage/impostor_albedo.png  (IMP_GRID x IMP_GRID species, IMP_N x IMP_N frames of IMP_PX;
                                                  sRGB albedo x AO, alpha = coverage)
       assets/roads/foliage/impostor_normal.png  (same layout, IMP_NPX frames; Godot object-space normals)
       assets/roads/foliage/impostors.json       (frames, sizes, per-species slot / centre / radius in Godot space)
       Frame (i, j) looks along -hemi_oct_dir(i, j), right = Y x dir, up = dir x right, ortho size 2 R."""
    np = _np()
    from mathutils import Matrix, Vector
    sc = bpy.data.scenes.new("MRS_ImpostorBake")
    w = bpy.data.worlds.new("MRS_ImpostorBakeWorld"); w.use_nodes = True; sc.world = w
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[1].default_value = 0.0
    cam = bpy.data.objects.new("MRS_ImpCam", bpy.data.cameras.new("MRS_ImpCam")); sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"; sc.camera = cam
    r = sc.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = samples
    r.film_transparent = True; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGBA"; r.image_settings.color_depth = "8"
    sc.view_settings.look = "None"; sc.view_settings.exposure = 0.0; sc.view_settings.gamma = 1.0
    tmp = os.path.join(ROOT, "tmp", "roads", "v5", "foliage", "imp_frames"); os.makedirs(tmp, exist_ok=True)
    side = IMP_GRID * IMP_N
    alb = np.zeros((side * IMP_PX, side * IMP_PX, 4), np.float32)
    nrm = np.zeros((side * IMP_NPX, side * IMP_NPX, 4), np.float32)
    nrm[..., :3] = 0.5; nrm[..., 1] = 1.0
    meta = {"frames": IMP_N, "px": IMP_PX, "npx": IMP_NPX, "grid": IMP_GRID, "albedo": "impostor_albedo.png",
            "normal": "impostor_normal.png", "species": {}}
    for slot, sid in enumerate(TREES):
        src = lod0_by_sid.get(sid)
        if src is None: continue
        me = src.data.copy(); o = bpy.data.objects.new("imp_" + sid, me); sc.collection.objects.link(o)
        vs = np.array([v.co[:] for v in me.vertices])
        lo, hi = vs.min(0), vs.max(0); c = (lo + hi) / 2
        R = float(np.linalg.norm(vs - c, axis=1).max()) * 1.01
        mats = list(me.materials)
        sets = {"albedo": _bake_materials(mats, "albedo"), "normal": _bake_materials(mats, "normal")}
        cam.data.ortho_scale = 2 * R; cam.data.clip_start = 0.1; cam.data.clip_end = 4 * R + 10
        tile_y, tile_x = slot // IMP_GRID, slot % IMP_GRID
        for mode, px, view in (("albedo", IMP_PX, "Standard"), ("normal", IMP_NPX, "Raw")):
            for i, mm in enumerate(sets[mode]): me.materials[i] = mm
            r.resolution_x = r.resolution_y = px
            sc.view_settings.view_transform = view
            for j in range(IMP_N):
                for i in range(IMP_N):
                    dg = hemi_oct_dir(i, j)
                    rg, ug = _frame_basis_g(dg)
                    d, rr, uu = Vector(_g2b(dg)), Vector(_g2b(rg)), Vector(_g2b(ug))
                    rot = Matrix((rr, uu, d)).transposed().to_4x4()
                    cam.matrix_world = Matrix.Translation(Vector(c) + d * (R + 5.0)) @ rot
                    r.filepath = os.path.join(tmp, "%s_%s_%d_%d.png" % (sid, mode, i, j))
                    bpy.ops.render.render(write_still=True, scene=sc.name)
                    fr = _read_png(r.filepath)
                    y0 = (tile_y * IMP_N + j) * px; x0 = (tile_x * IMP_N + i) * px
                    if mode == "albedo":
                        alb[y0:y0 + px, x0:x0 + px] = _dilate(fr)
                    else:
                        n = fr[..., :3] * 2.0 - 1.0                                   # Blender object space
                        ng = np.stack([n[..., 0], n[..., 2], -n[..., 1]], -1)         # -> Godot object space
                        ng /= np.maximum(np.linalg.norm(ng, axis=-1, keepdims=True), 1e-4)
                        q = fr.copy(); q[..., :3] = ng * 0.5 + 0.5
                        nrm[y0:y0 + px, x0:x0 + px] = _dilate(q)
        meta["species"][sid] = {"slot": slot, "centre": [float(c[0]), float(c[2]), float(-c[1])], "radius": R}
        print("[foliage] impostor", sid, "slot", slot, "R %.2f" % R, flush=True)
        bpy.data.objects.remove(o); bpy.data.meshes.remove(me)
        for ms in sets.values():
            for mm in ms: bpy.data.materials.remove(mm)
    _write_png(alb, os.path.join(FOLIAGE, meta["albedo"]))
    nrm[..., 3] = 1.0
    _write_png(nrm, os.path.join(FOLIAGE, meta["normal"]))
    with open(os.path.join(FOLIAGE, "impostors.json"), "w") as f: json.dump(meta, f, indent=1)
    bpy.data.scenes.remove(sc)
    return meta


def _write_import(png, normal=False):
    """Godot import settings: VRAM compressed, mipmaps (Godot fills in uid / dest on --import)."""
    with open(png + ".import", "w") as f:
        f.write('[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\ncompress/mode=2\ncompress/high_quality=false\n'
                'compress/lossy_quality=0.7\ncompress/normal_map=%d\nmipmaps/generate=true\nmipmaps/limit=-1\n'
                'process/fix_alpha_border=true\nprocess/premult_alpha=false\ndetect_3d/compress_to=0\n' % (2 if normal else 0))


def bake_foliage_assets(args=()):
    """All v5 assets: regraded hedge textures, MRS LOD1 per species, impostor atlases
    (headless: tools/roads/tests/foliage_v5_test.py -- bake [--only hedge|lod1|imp])."""
    args = list(args)
    only = args[args.index("--only") + 1] if "--only" in args else None
    os.makedirs(FOLIAGE, exist_ok=True)
    report = {}
    if only in (None, "hedge"):
        report["hedge"] = regrade_hedge_textures()
        for fn in HEDGE_TEXTURES.values(): _write_import(os.path.join(FOLIAGE, fn))
    if only in (None, "lod1", "imp"):
        build_game_trees(plants=False, version=5)
        lod0s = {sid: bpy.data.objects.get(MRS + "GTree_" + sid) for sid in TREES}
        if only in (None, "lod1"):
            report["lod1"] = {}
            for sid, src in lod0s.items():
                if src is None: continue
                o, st = make_lod1(src, sid)
                st["tris_lod0"] = sum(len(p.vertices) - 2 for p in src.data.polygons)
                _export_glb([o], os.path.join(FOLIAGE, sid + "_lod1.glb"), sid + "_lod1",
                            {"species": sid, "lod": 1, "tris": st["tris"], "keep": LOD1_KEEP, "grow": LOD1_GROW})
                report["lod1"][sid] = st
                print("[foliage] lod1", sid, st, flush=True)
                me = o.data; bpy.data.objects.remove(o); bpy.data.meshes.remove(me)
        if only in (None, "imp"):
            meta = bake_impostors(lod0s)
            _write_import(os.path.join(FOLIAGE, meta["albedo"])); _write_import(os.path.join(FOLIAGE, meta["normal"]), normal=True)
            report["impostors"] = {k: v for k, v in meta.items() if k != "species"}
    with open(os.path.join(FOLIAGE, "bake_report_%s.json" % (only or "all")), "w") as f: json.dump(report, f, indent=1)
    return report
