"""Headless bake + export of a prototype house carrying the procedural CF materials.

    blender --background <prototype.blend> --python tools/cityforge/proto_bake_cli.py -- <object> <out_glb> [res]

Splits the object into two bake groups (A: walls, roof, slabs; B: trim, frames, doors, railings,
shutters, glass) so the big surfaces keep real texel density, unwraps each (Smart UV Project),
bakes albedo / tangent normal / ORM per group (proto_materials.bake_object), and exports both as
one GLB with two glTF materials. Saves the .blend back with the baked copies beside the source.
"""
import bpy, bmesh, math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:]
NAME, GLB = argv[0], os.path.abspath(argv[1])
RES = int(argv[2]) if len(argv) > 2 else 2048
src = open(os.path.join(HERE, "proto_materials.py"), encoding="utf-8").read()
ns = {"__name__": "cf_proto", "__file__": os.path.join(HERE, "proto_materials.py")}
exec(compile(src, "proto_materials.py", "exec"), ns)

sc = bpy.data.scenes.get("CF_Prototype") or bpy.context.scene
bpy.context.window.scene = sc
house = bpy.data.objects[NAME]
for nm in ("H_casa_A", "H_casa_B", "H_casa_A_baked", "H_casa_B_baked"):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o)
big = {"CF_Stucco", "CF_RoofTerracotta", "CF_Concrete", "CF_Brick", "CF_BrickLondon", "CF_Siding", "CF_Plaster", "CF_RoofSlate", "CF_Roof", "CF_RoofKawara"}
parts = {}
for tag, keep in (("H_casa_A", lambda n: n in big), ("H_casa_B", lambda n: n not in big)):
    o = house.copy(); o.data = house.data.copy(); o.name = tag; sc.collection.objects.link(o)
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
    # split with bmesh: the mesh.delete operator leaves an edit mesh the UV operators refuse (Blender 5.2)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(o.data.materials[f.material_index].name)], context="FACES")
    # triangulate: the concave wall n-gons (window cut-outs) did not bake as n-gons; triangles always do
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(o.data); bm.free(); o.data.update()
    used = {p.material_index for p in o.data.polygons}
    for i in reversed(range(len(o.data.materials))):
        if i not in used: o.active_material_index = i; bpy.ops.object.material_slot_remove()
    ns["unwrap"](o, 0.003 if tag.endswith("A") else 0.002)
    parts[tag] = o
    print("PART", tag, len(o.data.polygons), "faces", [m.name for m in o.data.materials])
t0 = time.time()
B = os.path.join(os.path.dirname(GLB), "..", "..", "..", "tmp", "cityforge", "proto", "bake")
B = os.path.abspath(B)
paths = {tag: ns["bake_object"](o, B, res=RES, samples=16) for tag, o in parts.items()}
copies = []
for tag, o in parts.items():
    c = o.copy(); c.data = o.data.copy(); c.name = tag + "_baked"; sc.collection.objects.link(c)
    c.data.materials.clear(); c.data.materials.append(ns["baked_material"](o, paths[tag], tag + "_baked"))
    for p in c.data.polygons: p.material_index = 0
    copies.append(c); o.hide_set(True); o.hide_render = True
bpy.ops.object.select_all(action="DESELECT")
for c in copies: c.select_set(True); c.location = (0, 0, 0)
bpy.context.view_layer.objects.active = copies[0]
os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_materials="EXPORT", export_normals=True, export_texcoords=True)
for c in copies: c.location = (16.0, 0.0, 0.0)
tris = sum(len(p.vertices) - 2 for c in copies for p in c.data.polygons)
print("BAKED %s: %d tris, %d KB, %.0fs" % (NAME, tris, os.path.getsize(GLB) // 1024, time.time() - t0))
bpy.ops.wm.save_mainfile()
