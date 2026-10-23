"""Game export of an NPC built with npc_kit.py.

usage: blender --background --factory-startup --python tools/npc/export_npc.py -- <master.blend> <NAME> <out.glb>

From the master scene <NAME>: copies the rig and every visible skinned mesh into a scene
"<NAME>_Export", bakes MPFB shape keys, applies non-armature modifiers (under-clothes mask, helper
mask, garment thickness), decimates dense shoe lasts, keeps one UV map per mesh, limits skin
weights to 4 normalised influences and repairs unweighted vertices. MPFB materials route their
textures through MixRGB nodes the glTF exporter cannot follow, so they are rebuilt as plain
Principled materials (opaque skin, alpha-clipped hair/brows/lashes/eyes). Textures are scaled to
the game budget (skin 2048, the rest 1024) and written as JPEG (PNG where alpha is needed). Writes the GLB and an
export .blend beside the master; the root node carries glTF extras (npc_id, height_m).

Crowd export (townspeople, texture budget <= 512, or "atlas" as 6th argument): every opaque garment,
shoe and hair-cap material is packed into one clothing atlas (base colour, normal, roughness and,
for hi-vis dye, emission), hair cards, brows, lashes and eyes into one alpha-cut atlas, and all
meshes are joined into a single skinned mesh: three surfaces (skin, clothes, cut-outs) instead of
~12 mesh instances and materials per person.
"""
import numpy as np
import bpy, sys, os
from mathutils.kdtree import KDTree

_args = sys.argv[sys.argv.index("--") + 1:]
master, name, out_glb = _args[:3]
# texture budget (px): skin, everything else; townspeople use (1024, 512), hero characters (2048, 1024)
SKIN_PX = int(_args[3]) if len(_args) > 3 else 2048
TEX_PX = int(_args[4]) if len(_args) > 4 else 1024
ATLAS = TEX_PX <= 512 or "atlas" in _args[5:]
bpy.ops.wm.open_mainfile(filepath=master)
src = bpy.data.scenes[name]
rig = bpy.data.objects[name + "_Rig"]

exp = bpy.data.scenes.new(name + "_Export")
col = bpy.data.collections.new("EXP_" + name)
exp.collection.children.link(col)
r2 = rig.copy()
r2.data = rig.data.copy()
r2.name = name
r2.data.name = name + "_Skeleton"
r2.animation_data_clear()
col.objects.link(r2)
r2.data.pose_position = "REST"
for pb in r2.pose.bones:
    pb.matrix_basis.identity()

meshes = [o for o in src.objects if o.type == "MESH" and o.parent == rig and not o.hide_render
          and any(m.type == "ARMATURE" for m in o.modifiers)]
made = []
for o in meshes:
    c = o.copy()
    c.data = o.data.copy()
    col.objects.link(c)
    c.parent = r2
    for m in c.modifiers:
        if m.type == "ARMATURE":
            m.object = r2
    c.name = "EXP_" + o.name[len(name) + 1:]
    made.append(c)


def principled(m):
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def color_image(m):
    """the image that feeds Base Color, directly or through MixRGB"""
    p = principled(m)
    link = p.inputs["Base Color"].links[0] if p.inputs["Base Color"].links else None
    node = link.from_node if link else None
    while node is not None and node.type != "TEX_IMAGE":
        ins = [i for i in node.inputs if i.links]
        node = ins[-1].links[0].from_node if ins else None
    return node.image if node else None


def game_material(m, kind):
    """plain Principled material the glTF exporter maps 1:1"""
    img = color_image(m)
    p0 = principled(m)
    rough = p0.inputs["Roughness"].default_value
    g = bpy.data.materials.new("EXP_" + m.name.split(".")[1] if "." in m.name else "EXP_" + m.name)
    nt = g.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs[0], out.inputs[0])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Base Color"].default_value = p0.inputs["Base Color"].default_value   # untextured parts (hair cap)
    p.inputs["Specular IOR Level"].default_value = 0.35 if kind == "skin" else 0.2
    if img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
        if kind == "clip":
            r = nt.nodes.new("ShaderNodeMath")
            r.operation = "ROUND"                    # glTF alphaMode MASK, cutoff 0.5
            nt.links.new(t.outputs["Alpha"], r.inputs[0])
            nt.links.new(r.outputs[0], p.inputs["Alpha"])
    # the kit's skin detail maps (npc_kit.skin_detail): normal + roughness (green channel)
    src = {n.name: n for n in m.node_tree.nodes}
    if "NPC_SkinNormal" in src and src["NPC_SkinNormal"].image:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = src["NPC_SkinNormal"].image
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    if "NPC_SkinRough" in src and src["NPC_SkinRough"].image:
        tr = nt.nodes.new("ShaderNodeTexImage")
        tr.image = src["NPC_SkinRough"].image
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tr.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], p.inputs["Roughness"])
    return g


vl = exp.view_layers[0]
bones = set(r2.data.bones.keys())
for o in made:
    with bpy.context.temp_override(scene=exp, view_layer=vl, object=o, active_object=o, selected_objects=[o]):
        if o.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
        arm = [m for m in o.modifiers if m.type == "ARMATURE"]
        for m in arm:
            m.show_viewport = False
        for m in [m for m in o.modifiers if m.type != "ARMATURE"]:
            if m.show_viewport:
                bpy.ops.object.modifier_apply(modifier=m.name)
            else:
                o.modifiers.remove(m)
        if len(o.data.polygons) > 3000 and any(s in o.name for s in ("Flats", "Shoe", "Boot", "Sneaker")):
            d = o.modifiers.new("lod", "DECIMATE")
            d.ratio = 2400 / len(o.data.polygons)
            bpy.ops.object.modifier_apply(modifier=d.name)
        for m in arm:
            m.show_viewport = True
    if o.data.validate(verbose=False, clean_customdata=False):
        print("repaired invalid geometry in", o.name)
    uvs = o.data.uv_layers
    keep = "PatternUV" if "PatternUV" in uvs else (uvs.active.name if uvs.active else None)
    for u in [u.name for u in uvs]:
        if u != keep:
            uvs.remove(uvs[u])
    for g in list(o.vertex_groups):
        if g.name not in bones:
            o.vertex_groups.remove(g)
    vg = {g.index: g.name for g in o.vertex_groups}
    good = []
    for v in o.data.vertices:
        gs = sorted([(g.weight, g.group) for g in v.groups if g.weight > 0 and g.group in vg], reverse=True)
        keepw = gs[:4]
        s = sum(w for w, _ in keepw)
        ks = {gi for _, gi in keepw}
        for w, gi in gs:
            if gi in ks and s > 0:
                o.vertex_groups[gi].add([v.index], w / s, "REPLACE")
            else:
                o.vertex_groups[gi].remove([v.index])
        if s >= 0.5:
            good.append(v)
    bad = [v for v in o.data.vertices if sum(g.weight for g in v.groups if g.group in vg) < 0.5]
    if bad and good:
        kd = KDTree(len(good))
        for i, v in enumerate(good):
            kd.insert(v.co, i)
        kd.balance()
        for v in bad:
            srcv = good[kd.find(v.co)[1]]
            for g in srcv.groups:
                if g.group in vg:
                    o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    # MPFB parts get plain game materials; kit fabric materials are already glTF-shaped
    for slot in o.material_slots:
        m = slot.material
        if m and not m.name.startswith("M_"):
            kind = "skin" if o.name == "EXP_Body" else ("clip" if any(p in o.name for p in ("Hair", "Eyebrows", "Eyelashes", "Eyes")) and "HairCap" not in o.name else "opaque")
            slot.material = game_material(m, kind)
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    print("built", o.name, len(o.data.vertices), "verts", tris, "tris, unweighted fixed", len(bad))

# game texture budget: 2048 skin, 1024 everything else (sources stay full size in the master)
done = set()
for o in made:
    for slot in o.material_slots:
        for n in slot.material.node_tree.nodes if slot.material else ():
            img = getattr(n, "image", None)
            if n.type == "TEX_IMAGE" and img and img.name not in done:
                done.add(img.name)
                lim = SKIN_PX if o.name == "EXP_Body" else TEX_PX
                w, hh = img.size
                if max(w, hh) > lim:
                    img.scale(max(1, w * lim // max(w, hh)), max(1, hh * lim // max(w, hh)))



def to_srgb(c):
    return [((1.055 * (x ** (1 / 2.4)) - 0.055) if x > 0.0031308 else 12.92 * x) for x in c[:3]]


def tex_input(m, socket):
    """image feeding a Principled input directly or through Separate Color / Normal Map"""
    p = principled(m)
    if p is None or not p.inputs[socket].links:
        return None
    node = p.inputs[socket].links[0].from_node
    while node is not None and node.type != "TEX_IMAGE":
        ins = [i for i in node.inputs if i.links]
        node = ins[0].links[0].from_node if ins else None
    return node.image if node else None


def tile_pixels(img, t, fill):
    """img resized to t x t as float RGBA (raw stored values), or a flat tile"""
    if img is None or img.size[0] == 0:
        return np.tile(np.array(fill, np.float32), (t, t, 1))
    c = img.copy()
    if tuple(c.size) != (t, t):
        c.scale(t, t)
    a = np.empty(t * t * 4, np.float32)
    c.pixels.foreach_get(a)
    bpy.data.images.remove(c)
    return a.reshape(t, t, 4)


def build_atlas(mats, tag, alpha):
    """packs `mats` into a grid of TEX_PX tiles; returns (material, {material name: (col, row, grid)})"""
    t = TEX_PX
    g = 1
    while g * g < len(mats):
        g += 1
    size = g * t
    base = np.zeros((size, size, 4), np.float32)
    nrm = np.zeros((size, size, 4), np.float32)
    nrm[...] = (0.5, 0.5, 1.0, 1.0)
    rough = np.ones((size, size, 4), np.float32)
    emit = np.zeros((size, size, 4), np.float32)
    emit[..., 3] = 1.0
    emissive = False
    place = {}
    for i, m in enumerate(mats):
        tc, tr_ = i % g, i // g
        p = principled(m)
        bc = list(p.inputs["Base Color"].default_value)
        bimg = tex_input(m, "Base Color")
        tb = tile_pixels(bimg, t, to_srgb(bc) + [1.0])
        if bimg is None:
            tb[..., 3] = p.inputs["Alpha"].default_value
        r = p.inputs["Roughness"].default_value
        tr = tile_pixels(tex_input(m, "Roughness"), t, [r, r, r, 1.0])
        tn = tile_pixels(tex_input(m, "Normal"), t, [0.5, 0.5, 1.0, 1.0])
        ys, xs = slice(tr_ * t, tr_ * t + t), slice(tc * t, tc * t + t)
        base[ys, xs] = tb
        nrm[ys, xs] = tn
        rough[ys, xs] = tr
        es = p.inputs["Emission Strength"].default_value
        if es > 0 and p.inputs["Emission Color"].links:
            emissive = True
            emit[ys, xs, :3] = tb[..., :3] * es
        place[m.name] = (tc, tr_, g)

    def image(name, px, cs):
        im = bpy.data.images.new("%s_%s" % (name, tag), size, size, alpha=alpha and cs == "sRGB")
        im.colorspace_settings.name = cs
        im.pixels.foreach_set(np.ascontiguousarray(px).ravel())
        im.filepath_raw = os.path.join(export_dir, im.name + ".png")
        im.file_format = "PNG"
        im.save()
        return im
    am = bpy.data.materials.new("EXP_%s_%s" % (name, tag))
    nt = am.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(pr.outputs[0], out.inputs[0])
    pr.inputs["Specular IOR Level"].default_value = 0.25
    tb = nt.nodes.new("ShaderNodeTexImage")
    tb.image = image(name, base, "sRGB")
    nt.links.new(tb.outputs["Color"], pr.inputs["Base Color"])
    if alpha:
        rd = nt.nodes.new("ShaderNodeMath")
        rd.operation = "ROUND"
        nt.links.new(tb.outputs["Alpha"], rd.inputs[0])
        nt.links.new(rd.outputs[0], pr.inputs["Alpha"])
    trn = nt.nodes.new("ShaderNodeTexImage")
    trn.image = image(name, rough, "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(trn.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], pr.inputs["Roughness"])
    tnn = nt.nodes.new("ShaderNodeTexImage")
    tnn.image = image(name + "_n", nrm, "Non-Color")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tnn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], pr.inputs["Normal"])
    if emissive:
        te = nt.nodes.new("ShaderNodeTexImage")
        te.image = image(name + "_e", emit, "sRGB")
        nt.links.new(te.outputs["Color"], pr.inputs["Emission Color"])
        pr.inputs["Emission Strength"].default_value = 1.0
    return am, place


if ATLAS:
    export_dir = os.path.join(os.path.dirname(os.path.abspath(master)), "export")
    os.makedirs(export_dir, exist_ok=True)
    groups = {"clothes": [], "cutout": []}
    for o in made:
        if o.name == "EXP_Body":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            cut = any(l.to_socket.name == "Alpha" for l in m.node_tree.links)
            key = "cutout" if cut else "clothes"
            if m not in groups[key]:
                groups[key].append(m)
    built = {}
    for key, mats in groups.items():
        if len(mats) > 1:
            built[key] = build_atlas(mats, key, key == "cutout")
    # every mesh keeps one UV map, renamed alike so the join merges them
    for o in made:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")         # untextured parts (gear boxes): flat tiles
        o.data.uv_layers[0].name = "UVMap"
        for key, (am, place) in built.items():
            idx = [i for i, sl in enumerate(o.material_slots) if sl.material and sl.material.name in place]
            if not idx:
                continue
            uv = o.data.uv_layers[0].data
            for poly in o.data.polygons:
                if poly.material_index not in idx:
                    continue
                tc, tr_, g = place[o.material_slots[poly.material_index].material.name]
                inset = 1.5 / TEX_PX                     # keeps bilinear taps inside the tile
                for li in poly.loop_indices:
                    u, v = uv[li].uv
                    u = min(max(u, 0.0), 1.0) * (1 - 2 * inset) + inset
                    v = min(max(v, 0.0), 1.0) * (1 - 2 * inset) + inset
                    # pixel rows and v both run bottom-up: tile row 0 is the bottom of the image
                    uv[li].uv = ((tc + u) / g, (tr_ + v) / g)
            for i in idx:
                o.material_slots[i].material = am
    body = next(o for o in made if o.name == "EXP_Body")
    with bpy.context.temp_override(scene=exp, view_layer=vl, object=body, active_object=body, selected_objects=made, selected_editable_objects=made):
        bpy.ops.object.join()
    with bpy.context.temp_override(scene=exp, view_layer=vl, object=body, active_object=body, selected_objects=[body]):
        bpy.ops.object.material_slot_remove_unused()
    made = [body]
    print("atlas groups:", {k: [m.name for m in v] for k, v in groups.items()})
    print("atlas: one mesh,", len(body.material_slots), "materials,", len(body.data.polygons), "faces")

h = max((r2.matrix_world @ v.co).z for o in made if o.name == "EXP_Body" for v in o.data.vertices)
r2["npc_id"] = name
r2["height_m"] = round(h, 3)
for s in [s for s in bpy.data.scenes if s != exp]:
    bpy.data.scenes.remove(s)
bpy.ops.outliner.orphans_purge(do_recursive=True)
for o in vl.objects:
    o.select_set(o.name in col.objects, view_layer=vl)
with bpy.context.temp_override(scene=exp, view_layer=vl):
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True, export_apply=False,
                              export_skins=True, export_animations=False, export_morph=False, export_yup=True,
                              export_image_format="JPEG", export_jpeg_quality=88, export_cameras=False, export_lights=False, export_extras=True)
r2.data.pose_position = "POSE"
# the export scene is kept beside the master (never under assets/: Godot would try to import it)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(master)), "export"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(master)), "export", name + "_export.blend"), compress=True)
print("NPC_EXPORT_DONE", out_glb, os.path.getsize(out_glb) // 1024, "KB")
