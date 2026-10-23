import bpy, json, os, math, bmesh
from mathutils import Matrix, Vector
ROOT='C:/GodotProjects/delivery-simulator-2026'
OUT=ROOT+'/assets/vehicles/repaired_car'
root=bpy.data.objects['RepairedCar']
# Bake source orientation into mesh data, leaving neutral local axle bases.
bpy.context.view_layer.update()
objects=list(bpy.context.scene.objects)
world={o:o.matrix_world.copy() for o in objects}
for ob in objects:
    if ob.type=='MESH':
        ob.data.transform(Matrix.Translation(world[ob].translation).inverted() @ world[ob])
        ob.data.update()
def depth(ob):
    n=0
    while ob.parent:
        ob=ob.parent;n+=1
    return n
for ob in sorted(objects,key=depth):
    ob.matrix_world=Matrix.Translation(world[ob].translation)
    bpy.context.view_layer.update()
root['wheel_radius']=.34; root['wheelbase']=2.62
# Set coherent silver response while retaining original atlas detail.
body=bpy.data.objects['Coachwork']
mat=body.data.materials[0]
bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
for key in ['Metallic','Roughness']:
    for link in list(bs.inputs[key].links):mat.node_tree.links.remove(link)
bs.inputs['Metallic'].default_value=.48
bs.inputs['Roughness'].default_value=.34
bs.inputs['Coat Weight'].default_value=.4
bs.inputs['Coat Roughness'].default_value=.21
color_link=bs.inputs['Base Color'].links[0]
source=color_link.from_socket
mat.node_tree.links.remove(color_link)
mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
mix.inputs[2].default_value=(.72,.76,.80,1)
mat.node_tree.links.new(source,mix.inputs[1]);mat.node_tree.links.new(mix.outputs[0],bs.inputs['Base Color'])
# Weld disconnected UV seam positions without discarding UV layers. Recompute outward normals.
report={'source':'sketchup_assets/car_model.glb','source_triangles':404598,'wheel_radius_m':.34,'wheelbase_m':2.62,'lods':[],'textures':[]}
for ob in objects:
    if ob.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
    ob.data.validate(clean_customdata=True)
    for p in ob.data.polygons:p.use_smooth=True
# Consolidate static trim and windows by material to reduce draw calls.
static=[o for o in objects if o.type=='MESH' and not o.name.startswith('Assembly_')]
bpy.ops.object.select_all(action='DESELECT')
for o in static:o.select_set(True)
bpy.context.view_layer.objects.active=body
bpy.ops.object.join();body.name='BodyAndGlazing'
# Remove unused slots (including old imported material copies).
bpy.ops.object.material_slot_remove_unused()
for im in [n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE']:
    im.pack()
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/source/repaired_car.blend')
# Keep 4K originals in source, publish a 2K atlas for the runtime GLBs.
for n in mat.node_tree.nodes:
    if n.type!='TEX_IMAGE':continue
    im=n.image
    if im.size[0]>2048:im.scale(2048,2048)
    name='body_albedo.png' if im.colorspace_settings.name=='sRGB' else 'body_orm.png'
    im.filepath_raw=OUT+'/textures/'+name;im.file_format='PNG';im.save()
    if im.packed_file: im.unpack(method='REMOVE')
    im.reload()
    report['textures'].append({'file':'textures/'+name,'width':im.size[0],'height':im.size[1]})
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
originals={o:o.data.copy() for o in meshes}
for level,ratio in [(0,1.0),(1,.38),(2,.13)]:
    for ob in meshes:
        ob.data=originals[ob].copy()
        if level:
            bpy.context.view_layer.objects.active=ob
            mod=ob.modifiers.new('LOD simplification','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        ob.data.validate(clean_customdata=True)
    tris=0; bounds=[]; uv_missing=[]
    for ob in meshes:
        ob.data.calc_loop_triangles();tris+=len(ob.data.loop_triangles)
        bounds.extend(ob.matrix_world @ Vector(c) for c in ob.bound_box)
        if not ob.data.uv_layers:uv_missing.append(ob.name)
    report['lods'].append({'level':level,'triangles':tris,'meshes':len(meshes),'uv_missing':uv_missing,'min':[min(p[i] for p in bounds) for i in range(3)],'max':[max(p[i] for p in bounds) for i in range(3)]})
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT+'/car_lod%d.glb'%level,export_format='GLB',use_selection=True,export_yup=True,export_extras=True)
for ob in meshes:ob.data=originals[ob]
with open(OUT+'/asset_report.json','w') as f:json.dump(report,f,indent=2)
print('CAR_EXPORT_REPORT',json.dumps(report),flush=True)
