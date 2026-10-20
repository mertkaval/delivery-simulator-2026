"""Prepare the supplied Jetta in an isolated Blender scene; preserve all source files."""
import bpy, bmesh, math, json, os, re, hashlib
from mathutils import Matrix, Vector
ROOT='C:/GodotProjects/delivery-simulator-2026'
SOURCE=ROOT+'/volkswagen-jetta-gli-2025/source/jetta_gli_my25_lights_on.glb'
OUT=ROOT+'/assets/vehicles/jetta_gli_2025'
for directory in ['source','textures','previews']:os.makedirs(OUT+'/'+directory,exist_ok=True)
open(OUT+'/source/.gdignore','w').close()
scene=bpy.data.scenes.new('JettaPreparation');bpy.context.window.scene=scene
bpy.ops.import_scene.gltf(filepath=SOURCE)
meshes=[o for o in scene.objects if o.type=='MESH']
original_triangles=0
for o in meshes:o.data.calc_loop_triangles();original_triangles+=len(o.data.loop_triangles)
points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
offset=Vector((0,-(min(p.y for p in points)+max(p.y for p in points))*.5,-min(p.z for p in points)))
removed=[]
for ob in list(meshes):
    if 'Airbag' in ob.name or (ob.name.startswith('Int') and '#Windows' in ob.name):
        removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True);meshes.remove(ob)
# Flatten imported transforms into copied mesh data, preserving normals and UVs.
for ob in meshes:
    world=ob.matrix_world.copy();ob.data=ob.data.copy();ob.parent=None
    ob.data.transform(Matrix.Translation(offset)@world)
    ob.data.update()
    ob.matrix_world=Matrix.Identity(4)
    ob.data.validate(clean_customdata=True)
for ob in list(scene.objects):
    if ob.type!='MESH':bpy.data.objects.remove(ob,do_unlink=True)

def empty(name,at=(0,0,0),parent=None):
    ob=bpy.data.objects.new(name,None);scene.collection.objects.link(ob);ob.location=at;ob.parent=parent
    return ob
root=empty('JettaGLI2025')
root['source_model']='Volkswagen Jetta GLI 2025 — user-supplied GLB'
root['collision_size']=[1.86,1.47,4.7567];root['collision_lift']=0.0
pivots={};axles={};wheel_report={}
for tag in ['FL','FR','RL','RR']:
    tire=next(o for o in meshes if o.name.startswith('Tire_'+tag+'#'))
    coords=[v.co for v in tire.data.vertices]
    bounds=[Vector((min(p.x for p in coords),min(p.y for p in coords),min(p.z for p in coords))),Vector((max(p.x for p in coords),max(p.y for p in coords),max(p.z for p in coords)))]
    center=(bounds[0]+bounds[1])*.5
    radius=(max(p.z for p in bounds)-min(p.z for p in bounds))*.5
    label={'FL':'FrontL','FR':'FrontR','RL':'RearL','RR':'RearR'}[tag]
    pivots[tag]=empty('Steer'+label,center,root)
    axles[tag]=empty('Wheel'+label,(0,0,0),pivots[tag])
    wheel_report[tag]={'center_blender':list(center),'radius_m':radius}
root['wheelbase']=(pivots['FL'].location.y+pivots['FR'].location.y-pivots['RL'].location.y-pivots['RR'].location.y)*.5
root['wheel_radius']=sum(w['radius_m'] for w in wheel_report.values())/4
# Steering column normal: align local Blender Y so exported Godot local Z spins the wheel.
sw_objects=[o for o in meshes if o.name.startswith('Int_SW#')]
sw_center=Vector((-.350075,.458260,.873983))+offset
sw=empty('SteeringWheel',sw_center,root)
sw.rotation_euler.x=math.radians(-22)
bpy.context.view_layer.update()
groups={root:[],sw:[]}
groups.update({p:[] for p in pivots.values()});groups.update({p:[] for p in axles.values()})
for ob in list(meshes):
    name=ob.name
    match=re.match(r'(?:Rim_.*_|Tire_)(FL|FR|RL|RR)#',name)
    if match:groups[axles[match.group(1)]].append(ob)
    elif name.startswith('Int_SW#'):groups[sw].append(ob)
    elif name.startswith('Ext_Brake_FL#') or name.startswith('Ext_Brake_FR#'):
        tag='FL' if name.startswith('Ext_Brake_FL') else 'FR'
        groups[pivots[tag] if '#Caliper' in name else axles[tag]].append(ob)
    elif name.startswith('Ext_Brake_Rear#') and '#Caliper' not in name:
        for tag,sign in [('RL',-1),('RR',1)]:
            copy=ob.copy();copy.data=ob.data.copy();scene.collection.objects.link(copy)
            bm=bmesh.new();bm.from_mesh(copy.data)
            bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.x*sign<0],context='VERTS')
            bm.to_mesh(copy.data);bm.free();groups[axles[tag]].append(copy)
        bpy.data.objects.remove(ob,do_unlink=True);meshes.remove(ob)
    else:groups[root].append(ob)

materials={m for group in groups.values() for ob in group for m in ob.data.materials if m}
for mat in materials:
    bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not bs:continue
    name=mat.name
    if 'Gris Franela' in name:
        bs.inputs['Coat Weight'].default_value=.55
        bs.inputs['Coat Roughness'].default_value=.17
        bs.inputs['Metallic'].default_value=.42
        bs.inputs['Roughness'].default_value=.28
    if 'Perforated' in name:
        # The source's materials named Black/Dark Grey had a bright .8 factor.
        socket=bs.inputs['Base Color']
        factor=.11 if 'Black' in name else .15
        if socket.is_linked:
            source=socket.links[0].from_socket
            mat.node_tree.links.remove(socket.links[0])
            mul=mat.node_tree.nodes.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1
            mul.inputs[2].default_value=(factor,factor,factor,1)
            mat.node_tree.links.new(source,mul.inputs[1]);mat.node_tree.links.new(mul.outputs[0],socket)
        else:socket.default_value=(.035,.037,.041,1)
    if 'Windows Ext' in name:
        bs.inputs['Alpha'].default_value=.30 if 'Tinted' in name else .20
        bs.inputs['Roughness'].default_value=.065
        mat.use_backface_culling=True
    if 'Tires' in name:bs.inputs['Roughness'].default_value=.83
    if 'Glow' in name:
        strength=bs.inputs['Emission Strength']
        strength.default_value=min(3,max(.7,strength.default_value))

# Preserve a full-detail, editable assembly with separate steering/brake/wheel groups.
for parent,objects in groups.items():
    bpy.context.view_layer.update()
    for ob in objects:
        world=ob.matrix_world.copy();ob.parent=parent;ob.matrix_world=world
root['wheel_report_json']=json.dumps(wheel_report)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
for mat in materials:
    for n in mat.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image:
            im=n.image
            if not im.packed_file:im.pack()
bpy.data.libraries.write(OUT+'/source/jetta_gli_2025.blend',{scene},fake_user=True,compress=True)

report={'source':SOURCE,'source_sha256':hashlib.sha256(open(SOURCE,'rb').read()).hexdigest(),'source_triangles':original_triangles,'removed_objects':removed,'wheels':wheel_report,'wheelbase_m':root['wheelbase'],'wheel_radius_m':root['wheel_radius'],'lods':[],'textures':[]}
images={n.image for mat in materials for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
for im in images:
    name=re.sub(r'[^a-zA-Z0-9_-]','_',im.name)+'.png'
    im.filepath_raw=OUT+'/textures/'+name;im.file_format='PNG';im.save()
    report['textures'].append({'file':'textures/'+name,'size':list(im.size)})

# Group all stationary surfaces together. Keep wheel rotation and caliper steering distinct.
for parent,objects in groups.items():
    if not objects:continue
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join();ob=bpy.context.object
    label='Body' if parent==root else 'SteeringAssembly' if parent==sw else 'Assembly_'+parent.name
    ob.name=label
    ob['part_role']='body' if parent==root else 'steering' if parent==sw else 'wheel'
    # Bake the old identity mesh into the group's local frame; give mesh nodes neutral transforms.
    delta=parent.matrix_world.inverted()@ob.matrix_world
    ob.data.transform(delta);ob.parent=parent;ob.matrix_basis=Matrix.Identity(4);ob.matrix_parent_inverse=Matrix.Identity(4)
    bpy.ops.object.material_slot_remove_unused()
near_meshes=[o for o in scene.objects if o.type=='MESH']
originals={ob:ob.data.copy() for ob in near_meshes}
for level in range(3):
    for ob in near_meshes:
        ob.data=originals[ob].copy()
        # Vertex group weights distinguish cabin detail from the visible body shell.
        if ob['part_role']=='body':ratio=[.37,.14,.045][level]
        elif ob['part_role']=='steering':ratio=[.28,.10,.045][level]
        else:ratio=[.78,.32,.14][level]
        bpy.context.view_layer.objects.active=ob
        if len(ob.data.polygons)>100:
            mod=ob.modifiers.new('Game LOD','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        ob.data.validate(clean_customdata=True)
    triangles=0;surfaces=0;missing=[]
    for ob in near_meshes:
        ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles);surfaces+=len(ob.data.materials)
        if not ob.data.uv_layers:missing.append(ob.name)
    if level==0:
        # Keep the exact optimized topology as a second editable Blender scene.
        bpy.data.libraries.write(OUT+'/source/jetta_runtime.blend',{scene},fake_user=True,compress=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT+'/jetta_lod%d.glb'%level,export_format='GLB',use_selection=True,export_yup=True,export_extras=True)
    report['lods'].append({'level':level,'triangles':triangles,'meshes':len(near_meshes),'surfaces':surfaces,'missing_uv':missing})
for ob in near_meshes:ob.data=originals[ob]
with open(OUT+'/asset_report.json','w') as f:json.dump(report,f,indent=2)
print('JETTA_REPORT',json.dumps({k:v for k,v in report.items() if k not in ['textures','removed_objects']}),flush=True)
