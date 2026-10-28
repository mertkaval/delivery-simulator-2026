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
