"""Export: evaluated road meshes (instances realized, materials and metre UVs kept) as GLB plus a
collision GLB with only the drivable / walkable surfaces; 'export-ready' plain mesh copies."""
import bpy, bmesh, os
from .nodes import depsgraph, set_scene, MRS, mod_input_set, scene as _scene
from .roads import all_roads


def evaluated_mesh_object(o, name, collection, realize=True, collision=False):
    """A static mesh copy of a road (or junction / structure) as an engine will see it."""
    mod = o.modifiers.get("MRS_Road") if o.type == "CURVE" else None
    if mod:
        mod_input_set(mod, "Realize Instances", realize); mod_input_set(mod, "Collision Only", collision); o.update_tag()
    dg = depsgraph()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    if mod:
        mod_input_set(mod, "Realize Instances", False); mod_input_set(mod, "Collision Only", False); o.update_tag()
    out = bpy.data.objects.new(name, me); out.matrix_world = o.matrix_world.copy(); collection.objects.link(out)
    return out


def _exportable(src):
    for o in src.all_objects:
        if o.type == "CURVE" and "MRS_Road" in o.modifiers: yield o
        elif o.type == "MESH" and not o.hide_viewport and not o.get("mrs_terrain_source"): yield o


def export_ready(objs, collection):
    """Plain mesh copies (instances realized) in a collection '<name>_Export'; sources are hidden."""
    col = bpy.data.collections.get(collection.name + "_Export") or bpy.data.collections.new(collection.name + "_Export")
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    out = []
    for o in objs:
        for old in [x for x in col.objects if x.name == o.name + "_mesh"]: bpy.data.objects.remove(old)
        m = evaluated_mesh_object(o, o.name + "_mesh", col)
        o.hide_viewport = True; o.hide_render = True
        out.append(m)
    return out


def export_glb(path, collection_name=MRS + "Roads", collision=True):
    """GLB of the evaluated roads, junctions and structures (instances realized, materials kept, UVs
    in metres), plus <path>_collision.glb with only the drivable and walkable surfaces (kind 0/2/3/4)."""
    src = bpy.data.collections[collection_name]
    tmp = bpy.data.collections.get(MRS + "ExportTmp") or bpy.data.collections.new(MRS + "ExportTmp")
    if tmp.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(tmp)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    sc = _scene(); vl = sc.view_layers[0]
    if tmp.name not in sc.collection.children: sc.collection.children.link(tmp)
    objs = [evaluated_mesh_object(o, o.name + "_export", tmp) for o in _exportable(src)]
    objs = [o for o in objs if len(o.data.polygons)]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if sc != bpy.context.scene:
        raise RuntimeError("export_glb: make %s the active scene first (headless: blender -b file.blend --scene %s)" % (sc.name, sc.name))
    def _export(sel, fp, **kw):
        for o in bpy.context.view_layer.objects: o.select_set(o in sel)
        bpy.context.view_layer.objects.active = sel[0]
        bpy.ops.export_scene.gltf(filepath=fp, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, **kw)
    _export(objs, path, export_materials="EXPORT", export_normals=True, export_texcoords=True)
    stats = {"objects": len(objs), "tris": sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons), "bytes": os.path.getsize(path)}
    if collision:
        for o in list(tmp.objects): bpy.data.objects.remove(o)
        cobjs = []
        for o in _exportable(src):
            c = evaluated_mesh_object(o, o.name + "_col", tmp, realize=False, collision=True) if o.type == "CURVE" else evaluated_mesh_object(o, o.name + "_col", tmp)
            me = c.data
            if "kind" in me.attributes:
                kind = me.attributes["kind"].data
                bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[i] for i in range(len(me.polygons)) if round(kind[i].value) in (1, 5)], context="FACES")
                bm.to_mesh(me); bm.free()
            if len(me.polygons): cobjs.append(c)
        if cobjs:
            cpath = os.path.splitext(path)[0] + "_collision.glb"
            _export(cobjs, cpath, export_materials="NONE", export_normals=False, export_texcoords=False)
            stats["collision_tris"] = sum(len(p.vertices) - 2 for o in cobjs for p in o.data.polygons); stats["collision_bytes"] = os.path.getsize(cpath)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    return stats


def export_block(path, collection_name, lod_trees=True):
    """Game export of a street block: `<path>.glb` (roads, junctions, structures), `<path>_collision.glb`,
    `<path>_props.glb` (placed props as named nodes, tree LOD1 swapped in when `lod_trees`),
    `<path>_signals.glb` (signal poles and heads as separate named nodes with the per-lens State
    materials) and `<path>.json` (shared street model: lanes, paths, crossings, signals, phases,
    placement report, validation). Returns stats."""
    from . import street_model
    src = bpy.data.collections[collection_name]
    stats = export_glb(path + ".glb", collection_name, collision=True)
    placed = bpy.data.collections.get(collection_name + "_Placed")
    sc = _scene(); vl = sc.view_layers[0]
    tmp = bpy.data.collections.get(MRS + "ExportTmp") or bpy.data.collections.new(MRS + "ExportTmp")
    if tmp.name not in sc.collection.children: sc.collection.children.link(tmp)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    def _export(sel, fp, **kw):
        for o in bpy.context.view_layer.objects: o.select_set(o in sel)
        bpy.context.view_layer.objects.active = sel[0]
        bpy.ops.export_scene.gltf(filepath=fp, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_extras=True, **kw)
    def _copy_tree(o, extra=None):
        c = bpy.data.objects.new(o.name, o.data); c.matrix_world = o.matrix_world.copy(); tmp.objects.link(c)
        for k, v in (extra or {}).items(): c[k] = v
        out = [c]
        for ch in o.children:
            c2 = bpy.data.objects.new(ch.name, ch.data); c2.parent = c; c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            c2.location = ch.location; c2.rotation_euler = ch.rotation_euler; c2.scale = ch.scale; tmp.objects.link(c2); out.append(c2)
        return out
    if placed:
        sel = []
        for o in placed.objects:
            if o.parent is not None: continue
            lib = o.get("mrs_placed", "")
            if lod_trees and lib.startswith("MRS_Tree_") and bpy.data.objects.get(lib + "_LOD1"):
                c = bpy.data.objects.new(o.name, bpy.data.objects[lib + "_LOD1"].data); c.matrix_world = o.matrix_world.copy(); tmp.objects.link(c); c["mrs_lib"] = lib + "_LOD1"; sel.append(c)
            else:
                sel += _copy_tree(o, {"mrs_lib": lib})
        if sel:
            vl.update(); _export(sel, path + "_props.glb", export_materials="EXPORT")
            stats["props"] = len([o for o in sel if o.parent is None]); stats["props_tris"] = sum(len(p.vertices) - 2 for o in sel for p in o.data.polygons); stats["props_bytes"] = os.path.getsize(path + "_props.glb")
        for o in list(tmp.objects): bpy.data.objects.remove(o)
    signals = [o for o in src.all_objects if o.get("mrs_signal_id")]
    if signals:
        sel = []
        for o in signals: sel += _copy_tree(o, {"mrs_signal_id": o["mrs_signal_id"]})
        vl.update(); _export(sel, path + "_signals.glb", export_materials="EXPORT")
        stats["signals"] = len(signals); stats["signals_bytes"] = os.path.getsize(path + "_signals.glb")
        for o in list(tmp.objects): bpy.data.objects.remove(o)
    model = street_model.collect(src)
    model["export"] = {"glb": os.path.basename(path) + ".glb", "collision": os.path.basename(path) + "_collision.glb", "props": os.path.basename(path) + "_props.glb",
                       "signals": os.path.basename(path) + "_signals.glb",
                       "lens_materials": "MRS_Lens_<Red|Amber|Green|PedRed|PedGreen>: KHR_materials_emissive_strength carries the lit state; in Blender a Value node named State (0/1) drives it",
                       "stats": stats}
    report = sc.get("mrs_placement_report")
    if report: model["placement_report"] = {k: (dict(v) if hasattr(v, "keys") else list(v)) for k, v in dict(report).items()}
    street_model.export_json(path + ".json", model)
    stats["json"] = path + ".json"; stats["validation"] = model["validation"]
    return stats
