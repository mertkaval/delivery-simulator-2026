"""Build the game export copy of the v3 courier from the editable master.

usage: blender --background --factory-startup --python tools/build_courier_v3_export.py -- \
           <master.blend> <old_export_copy.blend> <out_export_copy.blend> <out.glb>

From the master scene "Courier_v3_Work": copies the rig and every visible skinned mesh into a scene
"Courier_v3_Export", bakes MPFB shape keys, applies non-armature modifiers (masks, solidify,
decimate, bevel), keeps one UV map per mesh, limits skin weights to 4 normalised influences and
repairs unweighted vertices. Game materials (EXP_*: baked skin, hair/eye alpha clip, fabric) are
taken from the previous export copy so the look matches the validated GLB.
"""
import bpy, sys
from mathutils.kdtree import KDTree

master, old_copy, out_blend, out_glb = sys.argv[sys.argv.index("--") + 1:][:4]
bpy.ops.wm.open_mainfile(filepath=master)
work = bpy.data.scenes["Courier_v3_Work"]
rig = bpy.data.objects["V3_Courier_Rig"]

NAMES = {"V3_Courier_Body": "EXP_Body", "V3_Courier_Body.eyelashes01": "EXP_Eyelashes", "V3_Courier_Body.short01": "EXP_Hair",
         "V3_Eyes_HighPoly": "EXP_Eyes", "V3_Eyebrows": "EXP_Eyebrows", "V3_Jersey": "EXP_Jersey", "V3_Zipper": "EXP_Zipper",
         "V3_ZipSlider": "EXP_ZipSlider", "V3_BibShorts": "EXP_Shorts", "V3_Sock_L": "EXP_Sock_L", "V3_Sock_R": "EXP_Sock_R",
         "V3_Shoe_L": "EXP_Shoe_L", "V3_Shoe_R": "EXP_Shoe_R", "V3_Laces_L": "EXP_Laces_L", "V3_Laces_R": "EXP_Laces_R",
         "V3_Tongue_L": "EXP_Tongue_L", "V3_Tongue_R": "EXP_Tongue_R"}

# old game materials, keyed by export object name
with bpy.data.libraries.load(old_copy, link=False) as (src, dst):
    dst.objects = [n for n in NAMES.values()]
old_mats = {}
for o in dst.objects:
    if o is not None:
        old_mats[o.name] = [s.material for s in o.material_slots]

exp = bpy.data.scenes.new("Courier_v3_Export")
col = bpy.data.collections.new("EXP_Courier")
exp.collection.children.link(col)
r2 = rig.copy()
r2.data = rig.data.copy()
r2.name = "Courier"
r2.data.name = "Courier_Skeleton"
r2.animation_data_clear()
col.objects.link(r2)
r2.data.pose_position = "REST"
for pb in r2.pose.bones:
    pb.matrix_basis.identity()

made = []
for src_name, dst_name in NAMES.items():
    o = bpy.data.objects[src_name]
    c = o.copy()
    c.data = o.data.copy()
    col.objects.link(c)
    c.parent = r2
    for m in c.modifiers:
        if m.type == "ARMATURE":
            m.object = r2
    for o2 in [x for x in dst.objects if x is not None and x.name == dst_name]:
        o2.name = dst_name + "_old"
    c.name = dst_name
    made.append(c)

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
            bpy.ops.object.modifier_apply(modifier=m.name)
        for m in arm:
            m.show_viewport = True
    # one UV map: the one the material samples (PatternUV for printed garments)
    uvs = o.data.uv_layers
    keep = "PatternUV" if "PatternUV" in uvs else ("UVMap" if "UVMap" in uvs else (uvs[0].name if len(uvs) else None))
    for u in [u.name for u in uvs]:
        if u != keep:
            uvs.remove(uvs[u])
    # weights: 4 influences, normalised, no unweighted vertices
    vg = {g.index: g.name for g in o.vertex_groups}
    for g in list(o.vertex_groups):
        if g.name not in bones:
            o.vertex_groups.remove(g)
    vg = {g.index: g.name for g in o.vertex_groups}
    good = []
    for v in o.data.vertices:
        gs = sorted([(g.weight, g.group) for g in v.groups if g.weight > 0], reverse=True)
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
    bad = [v for v in o.data.vertices if sum(g.weight for g in v.groups) < 0.5]
    if bad and good:
        kd = KDTree(len(good))
        for i, v in enumerate(good):
            kd.insert(v.co, i)
        kd.balance()
        for v in bad:
            srcv = good[kd.find(v.co)[1]]
            for g in srcv.groups:
                o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    # game materials from the previous export copy
    mats = old_mats.get(o.name)
    if mats and len(mats) == len(o.material_slots):
        for slot, m in zip(o.material_slots, mats):
            slot.material = m
    else:
        print("WARNING: material slots differ for", o.name, len(o.material_slots), mats and len(mats))
    print("built", o.name, len(o.data.vertices), "verts, unweighted fixed", len(bad))

for o in [x for x in dst.objects if x is not None]:
    bpy.data.objects.remove(o, do_unlink=True)
# the old copy's rig came along as the meshes' parent and took the name "Courier"
for o in [x for x in bpy.data.objects if x.type == "ARMATURE" and x != r2 and x.name not in col.objects]:
    bpy.data.objects.remove(o, do_unlink=True)
r2.name = "Courier"
for s in [s for s in bpy.data.scenes if s != exp]:
    bpy.data.scenes.remove(s)
for o in vl.objects:
    o.select_set(o.name in col.objects, view_layer=vl)
with bpy.context.temp_override(scene=exp, view_layer=vl):
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True, export_apply=False,
                              export_skins=True, export_animations=False, export_morph=False, export_yup=True,
                              export_image_format="AUTO", export_cameras=False, export_lights=False)
r2.data.pose_position = "POSE"
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
print("EXPORT_COPY_DONE", out_blend, out_glb)
