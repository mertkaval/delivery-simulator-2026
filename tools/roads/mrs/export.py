"""Export: evaluated road meshes (instances realized, materials and metre UVs kept) as GLB plus a
collision GLB with only the drivable / walkable surfaces; 'export-ready' plain mesh copies."""
import bpy, bmesh, os
from .nodes import depsgraph, set_scene, MRS, mod_input_set, mod_input_get, scene as _scene
from .roads import all_roads


def evaluated_mesh_object(o, name, collection, realize=True, collision=False):
    """A static mesh copy of a road (or junction / structure) as an engine will see it."""
    mod = o.modifiers.get("MRS_Road") if o.type == "CURVE" else None
    vq = None
    if mod:
        mod_input_set(mod, "Realize Instances", realize); mod_input_set(mod, "Collision Only", collision)
        # game geometry at Final quality (1 m stations): Preview (2.5 m) cannot represent the 2.5 m crossing ramps or
        # the kerb drops (a 3 cm lip at refuges), and curves facet
        try:
            vq = mod_input_get(mod, "Viewport Quality"); mod_input_set(mod, "Viewport Quality", "Final")
        except Exception:
            vq = None
        o.update_tag()
    dg = depsgraph()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    if mod:
        mod_input_set(mod, "Realize Instances", False); mod_input_set(mod, "Collision Only", False)
        if vq is not None: mod_input_set(mod, "Viewport Quality", vq)
        o.update_tag()
    out = bpy.data.objects.new(name, me); out.matrix_world = o.matrix_world.copy(); collection.objects.link(out)
    return out


TILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tmp", "roads", "materials", "tiles")
TILE_SIZE = 4.0


def engine_material(m, tiles_dir=None):
    """A glTF-friendly stand-in for a procedural material: baked seamless tiles for the road-surface
    materials (UVMap is in metres, so the mapping repeats every TILE_SIZE m), a flat Principled with the
    material's viewport colour for everything else. Lens materials and already-plain materials pass through."""
    from . import materials as mats
    if m is None: return None
    name = m.name
    if name.startswith(MRS + "Lens_") or name.endswith("_Baked") or name.endswith("_Engine"): return m
    if m.get("mrs_kit") and m.node_tree and any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes):
        # city-kit surfaces: the game replaces them by name (CityKit.material); export a flat stand-in, not the textures
        en = name + "_Engine"
        if en in bpy.data.materials: return bpy.data.materials[en]
        e = bpy.data.materials.new(en); e.use_nodes = True
        b = next(n for n in e.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = tuple(m.diffuse_color); b.inputs["Roughness"].default_value = 0.8
        e.diffuse_color = m.diffuse_color
        return e
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.use_nodes and m.node_tree else None
    if bsdf is not None and not bsdf.inputs["Base Color"].is_linked: return m
    if bsdf is not None and m.node_tree and any(n.type == "TEX_IMAGE" and n.image is not None for n in m.node_tree.nodes) and \
            bsdf.inputs["Base Color"].links and bsdf.inputs["Base Color"].links[0].from_node.type == "TEX_IMAGE":
        return m                                   # already image-textured (furniture atlas): the glTF exporter writes the textures
    tiles_dir = tiles_dir or TILES_DIR
    base = name[len(MRS):] if name.startswith(MRS) else None
    if base and os.path.exists(os.path.join(tiles_dir, "%s_albedo.png" % name)):
        bn = name + "_Baked"
        if bn in bpy.data.materials: return bpy.data.materials[bn]
        paths = {k: os.path.join(tiles_dir, "%s_%s.png" % (name, k)) for k in ("albedo", "normal", "roughness", "metallic") if os.path.exists(os.path.join(tiles_dir, "%s_%s.png" % (name, k)))}
        return mats.baked_material(bn, paths, repeat=1.0 / TILE_SIZE)
    en = name + "_Engine"
    if en in bpy.data.materials: return bpy.data.materials[en]
    e = bpy.data.materials.new(en); e.use_nodes = True
    b = next(n for n in e.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = tuple(m.diffuse_color)
    b.inputs["Roughness"].default_value = m.roughness; b.inputs["Metallic"].default_value = m.metallic
    if bsdf is not None and not bsdf.inputs["Emission Strength"].is_linked and bsdf.inputs["Emission Strength"].default_value > 0.5:
        b.inputs["Emission Color"].default_value = bsdf.inputs["Emission Color"].default_value; b.inputs["Emission Strength"].default_value = bsdf.inputs["Emission Strength"].default_value
    e.diffuse_color = m.diffuse_color
    return e


def road_masks(road, me):
    """Engine masks for the road shader (world/roads/mrs_road.gdshader), so position-dependent wear survives
    the tiled bake: COLOR_0 = (in-carriageway lanes, curb dirt band, gutter / drain wetness, 1) per vertex,
    UV2 = (lane width, half median) per road; the shader rebuilds the wheel tracks per pixel from UV.x (= lat)."""
    from .roads import road_widths, road_input
    n = len(me.vertices)
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
    vals = [0.0] * (4 * n)
    if road is not None and "lat" in me.attributes:
        lat = me.attributes["lat"].data; al = me.attributes["along"].data
        hl = me.attributes["half_l"].data if "half_l" in me.attributes else None; hr = me.attributes["half_r"].data if "half_r" in me.attributes else None
        dr = me.attributes["drain"].data if "drain" in me.attributes else None
        w0 = road_widths(road); w1 = road_widths(road, at_end=True) if road_input(road, "Transition") else w0
        a_mid = (road_input(road, "Transition Start") or 0.0) + (road_input(road, "Taper Length") or 0.0) * 0.5
        for i in range(n):
            la = lat[i].value; w = w1 if al[i].value > a_mid else w0
            half = (hr[i].value if la > 0 else hl[i].value) if (hl and hr) else (w["half_r"] if la > 0 else w["half_l"])
            if half < 0.01: half = w["half_r"] if la > 0 else w["half_l"]
            carr = w["carr_r"] if la > 0 else w["carr_l"]
            dist = half - abs(la)
            inroad = 1.0 if (w["median"] * 0.5 - 0.05) <= abs(la) <= carr + 0.05 else 0.0
            dirt = max(0.0, min(1.0, 1.0 - dist / 0.6)) if dist >= -0.05 else 0.0
            wet = max(dr[i].value if dr else 0.0, max(0.0, min(1.0, 1.0 - dist / 0.45)) if dist >= -0.05 else 0.0)
            vals[4 * i:4 * i + 4] = (inroad, dirt, wet * 0.85, 1.0)
        lw = w0["lw"]; mh = w0["median"] * 0.5
    else:
        for i in range(n): vals[4 * i + 3] = 1.0
        lw, mh = 3.5, 0.0
    col.data.foreach_set("color", vals)
    me.color_attributes.active_color = col
    try: me.color_attributes.render_color_index = me.color_attributes.find("Col")
    except Exception: pass
    uv2 = me.uv_layers.get("UV2") or me.uv_layers.new(name="UV2")
    if uv2 is not None:
        for d in uv2.data: d.uv = (lw, mh)
    return me


def apply_engine_materials(objs, tiles_dir=None):
    n = 0
    for o in objs:
        if o.type != "MESH": continue
        for i, m in enumerate(o.data.materials):
            em = engine_material(m, tiles_dir)
            if em is not m: o.data.materials[i] = em; n += 1
    return n


def _exportable(src):
    """Roads, junctions and structures; placed props and signals are exported separately (props / signals GLBs)."""
    for o in src.all_objects:
        if o.get("mrs_kind") in ("path", "pad") and o.type == "MESH": yield o; continue
        if o.get("mrs_debug"): continue
        if o.get("mrs_placed") or o.get("mrs_signal_id") or (o.parent is not None and (o.parent.get("mrs_signal_id") or o.parent.get("mrs_placed"))): continue
        if o.name.startswith(MRS + "GroundPlane"): continue                 # demo ground, not part of the asset
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


def export_glb(path, collection_name=MRS + "Roads", collision=True, engine_materials=True):
    """GLB of the evaluated roads, junctions and structures (instances realized, materials kept, UVs
    in metres), plus <path>_collision.glb with only the drivable and walkable surfaces (kind 0/2/3/4)."""
    src = bpy.data.collections[collection_name]
    tmp = bpy.data.collections.get(MRS + "ExportTmp") or bpy.data.collections.new(MRS + "ExportTmp")
    if tmp.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(tmp)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    sc = _scene(); vl = sc.view_layers[0]
    if tmp.name not in sc.collection.children: sc.collection.children.link(tmp)
    srcs = list(_exportable(src))
    objs = [evaluated_mesh_object(o, o.name + "_export", tmp) for o in srcs]
    for so, eo in zip(srcs, objs):
        if so.type == "CURVE" and "MRS_Road" in so.modifiers: road_masks(so, eo.data)
        elif so.get("mrs_junction"): road_masks(None, eo.data)
    objs = [o for o in objs if len(o.data.polygons)]
    if engine_materials: apply_engine_materials(objs)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if sc != bpy.context.scene:
        raise RuntimeError("export_glb: make %s the active scene first (headless: blender -b file.blend --scene %s)" % (sc.name, sc.name))
    def _export(sel, fp, **kw):
        for o in bpy.context.view_layer.objects: o.select_set(o in sel)
        bpy.context.view_layer.objects.active = sel[0]
        bpy.ops.export_scene.gltf(filepath=fp, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, use_active_scene=True, **kw)
    try: _export(objs, path, export_materials="EXPORT", export_normals=True, export_texcoords=True, export_vertex_color="ACTIVE")
    except TypeError: _export(objs, path, export_materials="EXPORT", export_normals=True, export_texcoords=True, export_colors=True)
    stats = {"objects": len(objs), "tris": sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons), "bytes": os.path.getsize(path)}
    if collision:
        for o in list(tmp.objects): bpy.data.objects.remove(o)
        cobjs = []
        for o in _exportable(src):
            fbm = o.modifiers.get("MRS_Footbridge") if o.type == "MESH" else None
            if fbm is not None:
                mod_input_set(fbm, "Collision Only", True); o.update_tag()
                c = evaluated_mesh_object(o, o.name + "_col", tmp)
                mod_input_set(fbm, "Collision Only", False); o.update_tag()
            else:
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
        stash = {k: sc[k] for k in list(sc.keys()) if k.startswith("mrs_")}
        for k in stash: del sc[k]
        try:
            bpy.ops.export_scene.gltf(filepath=fp, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_extras=True, use_active_scene=True, **kw)
        finally:
            for k, v in stash.items(): sc[k] = v
    def _copy_tree(o, extra=None):
        data = o.data.copy() if o.type == "MESH" else o.data
        c = bpy.data.objects.new(o.name, data); c.matrix_world = o.matrix_world.copy(); tmp.objects.link(c)
        for k, v in (extra or {}).items(): c[k] = v
        out = [c]
        for ch in o.children:
            c2 = bpy.data.objects.new(ch.name, ch.data.copy() if ch.type == "MESH" else ch.data); c2.parent = c; c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            c2.location = ch.location; c2.rotation_euler = ch.rotation_euler; c2.scale = ch.scale; tmp.objects.link(c2); out.append(c2)
        return out
    if placed:
        sel = []
        for o in placed.objects:
            if o.parent is not None: continue
            lib = o.get("mrs_placed", "")
            if o.get("mrs_kind") in ("tree", "landscape", "path", "pad") or lib.startswith(MRS + "GTree_") or o.get("mrs_debug"): continue   # instance records / main GLB
            if lod_trees and lib.startswith("MRS_Tree_") and bpy.data.objects.get(lib + "_LOD1"):
                me = bpy.data.objects[lib + "_LOD1"].data.copy()
                if "leaf_card" in me.attributes:          # alpha-masked leaf cards have no texture in the engine: keep blobs and fronds only
                    lc = me.attributes["leaf_card"].data
                    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
                    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in range(len(me.vertices)) if 0.5 < lc[i].value < 1.5], context="VERTS")
                    bm.to_mesh(me); bm.free()
                c = bpy.data.objects.new(o.name, me); c.matrix_world = o.matrix_world.copy(); tmp.objects.link(c); c["mrs_lib"] = lib + "_LOD1"; sel.append(c)
            else:
                sel += _copy_tree(o, {"mrs_lib": lib})
        if sel:
            apply_engine_materials(sel)
            vl.update(); _export(sel, path + "_props.glb", export_materials="EXPORT")
            stats["props"] = len([o for o in sel if o.parent is None]); stats["props_tris"] = sum(len(p.vertices) - 2 for o in sel if o.type == "MESH" for p in o.data.polygons); stats["props_bytes"] = os.path.getsize(path + "_props.glb")
        for o in list(tmp.objects):
            d = o.data; bpy.data.objects.remove(o)
            if d is not None and d.users == 0 and isinstance(d, bpy.types.Mesh): bpy.data.meshes.remove(d)
    signals = [o for o in src.all_objects if o.get("mrs_signal_id")]
    if signals:
        sel = []
        for o in signals: sel += _copy_tree(o, {"mrs_signal_id": o["mrs_signal_id"]})
        apply_engine_materials(sel)
        vl.update(); _export(sel, path + "_signals.glb", export_materials="EXPORT")
        stats["signals"] = len(signals); stats["signals_bytes"] = os.path.getsize(path + "_signals.glb")
        for o in list(tmp.objects): bpy.data.objects.remove(o)
    model = street_model.collect(src)
    model.update(block_records(src, sc))
    model["export"] = {"glb": os.path.basename(path) + ".glb", "collision": os.path.basename(path) + "_collision.glb", "props": os.path.basename(path) + "_props.glb",
                       "signals": os.path.basename(path) + "_signals.glb",
                       "lens_materials": "MRS_Lens_<Red|Amber|Green|PedRed|PedGreen>: KHR_materials_emissive_strength carries the lit state; in Blender a Value node named State (0/1) drives it",
                       "stats": stats}
    report = sc.get("mrs_placement_report")
    if report:
        import json as _json
        try: model["placement_report"] = _json.loads(report) if isinstance(report, str) else dict(report)
        except Exception: model["placement_report"] = str(report)
    if model.get("ground_files"):
        import shutil
        from .ground import TILES
        for fn in model["ground_files"]:
            src_f = os.path.join(TILES, fn)
            if os.path.exists(src_f): shutil.copy2(src_f, os.path.join(os.path.dirname(os.path.abspath(path)), fn))
    street_model.export_json(path + ".json", model)
    stats["json"] = path + ".json"; stats["validation"] = model["validation"]
    return stats


def block_records(src, sc=None):
    """Instance / metadata records for the game: trees and plants (the game's landscape-kit assets, placed
    by MultiMesh in Godot), real light sources, footbridge plans, route graphs, placed items with
    footprints. Coordinates stay Blender Z-up; Godot (x, y, z) = (x, z, -y)."""
    import json as _json, math as _m
    out = {"godot_axes": "Blender (x, y, z) -> Godot (x, z, -y); yaw_godot = yaw_blender", "trees": [], "plants": [], "lights": [], "footbridges": [],
           "routes": None, "items": []}
    placed = bpy.data.collections.get(src.name + "_Placed")
    if placed:
        for o in placed.objects:
            if o.get("mrs_kind") == "tree" and o.get("mrs_species"):
                out["trees"].append({"name": o.name, "species": o["mrs_species"], "pos": [round(c, 3) for c in o.location], "yaw": round(o.rotation_euler.z, 4),
                                     "scale": round(o.scale.x, 3), "source": "res://assets/landscape/%s.glb" % o["mrs_species"], "road": o.get("mrs_road", o.get("mrs_region", ""))})
            elif o.get("mrs_kind") == "landscape" and o.type == "MESH":
                me = o.data
                if "plant" not in me.attributes: continue
                plants = sorted(x.name for x in bpy.data.collections[MRS + "GamePlants"].objects)
                pl = me.attributes["plant"].data; scl = me.attributes["scale"].data; yw = me.attributes["yaw"].data
                for i, v in enumerate(me.vertices):
                    pid = plants[int(round(pl[i].value))][len(MRS + "GPlant_"):]
                    q = o.matrix_world @ v.co
                    out["plants"].append({"id": pid, "pos": [round(c, 3) for c in q], "yaw": round(yw[i].value, 3), "scale": round(scl[i].value, 3), "region": o.name})
    try:
        from . import lighting
        out["lights"] = lighting.light_records(src)
        out["night"] = lighting.lights_model(src).get("night", {})
    except Exception as e:
        out["lights_error"] = str(e)
    for o in src.all_objects:
        if o.get("mrs_footbridge_plan") and o.type == "MESH":
            pl = _json.loads(o["mrs_footbridge_plan"]); pl.pop("chains", None); out["footbridges"].append(dict(pl, name=o.name))
    for o in src.all_objects:
        if o.get("mrs_ground_record"):
            rec = _json.loads(o["mrs_ground_record"]); out["ground"] = rec
            out["ground_files"] = [rec["mask"]] + [f for maps in rec["tiles"].values() for f in maps.values()]
    try:
        from . import frontage
        out["destinations"] = frontage.destinations()
        out["frontages"] = [dict(_json.loads(o["mrs_building"]), name=o.name) for o in src.all_objects if o.get("mrs_building")]
    except Exception as e:
        out["destinations_error"] = str(e)
    sc = sc or bpy.context.scene
    for key, dst in (("mrs_routes", "routes"), ("mrs_placement_items", "items"), ("mrs_movements", "movements")):
        if sc.get(key):
            try: out[dst] = _json.loads(sc[key])
            except Exception: pass
    return out
