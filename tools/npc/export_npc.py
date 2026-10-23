"""Game export of an NPC built with npc_kit.py.

usage: blender --background --factory-startup --python tools/npc/export_npc.py -- <master.blend> <NAME> <out.glb>

From the master scene <NAME>: copies the rig and every visible skinned mesh into a scene
"<NAME>_Export", bakes MPFB shape keys, applies non-armature modifiers (under-clothes mask, helper
mask, garment thickness), decimates dense shoe lasts, keeps one UV map per mesh, limits skin
weights to 4 normalised influences and repairs unweighted vertices. MPFB materials route their
textures through MixRGB nodes the glTF exporter cannot follow, so they are rebuilt as plain
Principled materials (opaque skin, alpha-clipped hair/brows/lashes/eyes). Textures are scaled to
the game budget (skin 2048, the rest 1024) and written as JPEG (PNG where alpha is needed). Writes the GLB and an
export .blend next to it; the root node carries glTF extras (npc_id, height_m).
"""
import bpy, sys, os
from mathutils.kdtree import KDTree

master, name, out_glb = sys.argv[sys.argv.index("--") + 1:][:3]
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
            kind = "skin" if o.name == "EXP_Body" else ("clip" if any(p in o.name for p in ("Hair", "Eyebrows", "Eyelashes", "Eyes")) else "opaque")
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
                lim = 2048 if o.name == "EXP_Body" else 1024
                w, hh = img.size
                if max(w, hh) > lim:
                    img.scale(max(1, w * lim // max(w, hh)), max(1, hh * lim // max(w, hh)))

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
bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out_glb)[0] + "_export.blend", compress=True)
print("NPC_EXPORT_DONE", out_glb, os.path.getsize(out_glb) // 1024, "KB")
