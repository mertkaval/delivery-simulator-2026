"""Push every face of one material in a GLB out along its own normal (decals, chalkboards and
lettering that sat in - or dipped into - the surface they are mounted on), then re-export the GLB
with its vertex colours and extras.

blender --background --factory-startup --python tools/offset_glb_material.py -- <glb> <material substring> <metres> [...]
(several "<material substring> <metres>" pairs may follow the GLB path)
"""
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
path = args[0]
pairs = [(args[i], float(args[i + 1])) for i in range(1, len(args) - 1, 2)]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
moved = 0
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for key, dist in pairs:
        slots = [i for i, m in enumerate(me.materials) if m is not None and key in m.name]
        if not slots:
            continue
        faces = [f for f in bm.faces if f.material_index in slots]
        # Split them off so neighbouring faces of other materials keep their shape, then move.
        res = bmesh.ops.split(bm, geom=faces, use_only_faces=False)
        faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
        bm.normal_update()
        push = {}
        for f in faces:
            for v in f.verts:
                push[v] = push.get(v, f.normal * 0.0) + f.normal
            moved += 1
        for v, n in push.items():
            if n.length > 1e-9:
                v.co += n.normalized() * dist
    bm.to_mesh(me)
    bm.free()
try:
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_extras=True, export_yup=True, export_vertex_color="ACTIVE")
except TypeError:
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_extras=True, export_yup=True)
print("OFFSET", path, "moved", moved, "faces", pairs)
