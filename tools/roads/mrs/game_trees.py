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
mrs_far_slot, mrs_source (res:// path). Plants (grass, shrubs, hedges, boxwood, flower beds) go to
`MRS_GamePlants` as MRS_GPlant_<id>. Materials are rebuilt to match the game shader: albedo x crown AO
(COLOR_0.a), alpha clip 0.42 for leaves, roughness 0.78 leaves / 0.9 bark, a little translucency.
"""
import bpy, os, math
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
        leaves = not (m.name.endswith("_bark") or "trunk" in m.name.lower() or m.name in ("bed_stone", "bed_mulch", "yard_ground"))
        _game_material(m, leaves)
    o.hide_render = True
    return o


def _cleanup(objs):
    for o in objs:
        d = o.data
        bpy.data.objects.remove(o)
        if d is not None and isinstance(d, bpy.types.Mesh) and d.users == 0: bpy.data.meshes.remove(d)


def build_game_trees(plants=True):
    """Import the landscape kit trees (LOD0 + LOD1) and plants into MRS_GameTrees / MRS_GamePlants."""
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
        if l1 is not None: _take_mesh(l1, MRS + "GTree_" + sid + "_LOD1", tcol, dict(props, mrs_lod=1))
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
