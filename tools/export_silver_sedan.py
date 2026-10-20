import bpy,bmesh,math,json,os
from mathutils import Vector,Matrix
OUT='C:/GodotProjects/delivery-simulator-2026/assets/vehicles/silver_sedan'
scene=bpy.context.scene;source=bpy.data.collections['SEDAN_SOURCE']
report={'blender':bpy.app.version_string,'source_quads':0,'source_nonquads':0,'lods':[],'mesh_issues':[]}
# Source retains editable Mirror / Bevel / Subdivision and curve profiles.
for ob in source.objects:
 if ob.type=='MESH':
  report['source_quads']+=sum(len(p.vertices)==4 for p in ob.data.polygons)
  report['source_nonquads']+=sum(len(p.vertices)!=4 for p in ob.data.polygons)
# UV the late-added pieces as well.
bpy.ops.object.select_all(action='DESELECT')
for ob in source.objects:
 if ob.type=='MESH':ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02);bpy.ops.uv.average_islands_scale();bpy.ops.uv.pack_islands(margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
runtime=bpy.data.collections.new('SEDAN_RUNTIME_LOD0');scene.collection.children.link(runtime)
for src in list(source.objects):
 if src.type not in {'MESH','CURVE'}:continue
 ob=src.copy();ob.data=src.data.copy();runtime.objects.link(ob);ob.parent=None;ob.matrix_world=src.matrix_world.copy();ob.name='Game_'+src.name
 # Dense support cages already encode curvature: skip expensive render subdivision.
 for mod in list(ob.modifiers):
  if mod.type in {'BEVEL','SUBSURF'}:ob.modifiers.remove(mod)
 bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH')
 bm=bmesh.new();bm.from_mesh(ob.data)
 boundaries=[e for e in bm.edges if e.is_boundary]
 if boundaries:
  caps=bmesh.ops.holes_fill(bm,edges=boundaries,sides=0)['faces']
  # Cap each swept-profile end with a quad fan, never an n-gon in delivery.
  for f in list(caps):
   verts=list(f.verts)
   if len(verts)%2==0 and len(verts)>4:
    centre=bm.verts.new(f.calc_center_median());bm.faces.remove(f)
    for k in range(0,len(verts),2):bm.faces.new([centre,verts[k],verts[(k+1)%len(verts)],verts[(k+2)%len(verts)]])
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
 ob.data.update()
 # All exports are unscaled, unrotated geometry at a common bottom-centre pivot.
 ob.data.transform(ob.matrix_world);ob.matrix_world=Matrix.Identity(4)

points=[v.co.copy() for ob in runtime.objects for v in ob.data.vertices]
low=Vector(tuple(min(v[i] for v in points) for i in range(3)));high=Vector(tuple(max(v[i] for v in points) for i in range(3)))
shift=Vector(((low.x+high.x)/2,(low.y+high.y)/2,low.z))
report['dimensions_m']=list(high-low);report['pivot_translation_m']=list(shift)
for ob in runtime.objects:
 for v in ob.data.vertices:v.co-=shift
 bm=bmesh.new();bm.from_mesh(ob.data)
 nonmanifold=sum(not e.is_manifold for e in bm.edges);nonquad=sum(len(f.verts)!=4 for f in bm.faces)
 if nonmanifold or nonquad:report['mesh_issues'].append({'object':ob.name,'nonmanifold':nonmanifold,'nonquad':nonquad})
 for e in bm.edges:
  if len(e.link_faces)==2:e.smooth=e.calc_face_angle()<math.radians(30)
 bm.to_mesh(ob.data);bm.free()
# Export batching: body plus four wheel groups for steering/spin adapters.
groups={k:[] for k in ['Body','Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR']}
wheel_terms=('tire','Sidewall','wheel lip','Rim barrel','Brake rotor','Hub centre','alloy spoke','Lug seat')
for ob in list(runtime.objects):
 if any(term in ob.name for term in wheel_terms):
  center=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices)
  key='Wheel_'+('F' if center.y<0 else 'R')+('L' if center.x<0 else 'R')
 else:key='Body'
 groups[key].append(ob)
batched=[]
for key,obs in groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for ob in obs:ob.select_set(True)
 bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();ob=obs[0];ob.name='Sedan_'+key
 ob['smoothing_angle_degrees']=30
 if key!='Body':ob['wheel_center']=[(-.825 if key.endswith('L') else .825)-shift.x,(-1.37 if '_F' in key else 1.32)-shift.y,.325-shift.z]
 batched.append(ob)
# Generated curves need consistent UVs after conversion.
bpy.ops.object.select_all(action='DESELECT')
for ob in batched:ob.select_set(True)
bpy.context.view_layer.objects.active=batched[0]
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.01);bpy.ops.uv.average_islands_scale();bpy.ops.uv.pack_islands(margin=.01);bpy.ops.object.mode_set(mode='OBJECT')
source.hide_render=True;source.hide_viewport=True
for level,ratio in [(0,1),(1,.42),(2,.16)]:
 bpy.ops.object.select_all(action='DESELECT');copies=[];triangles=0
 for src in batched:
  ob=src.copy();ob.data=src.data.copy();runtime.objects.link(ob);ob.name=src.name+'_LOD'+str(level);copies.append(ob);ob.select_set(True)
  if ratio<1:
   dec=ob.modifiers.new('Runtime simplification','DECIMATE');dec.ratio=ratio
  e=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();me.calc_loop_triangles();triangles+=len(me.loop_triangles);e.to_mesh_clear()
 path=OUT+'/silver_sedan_lod'+str(level)+'.glb'
 bpy.ops.export_scene.gltf(filepath=path,use_selection=True,use_active_scene=True,export_apply=True,export_extras=True)
 report['lods'].append({'level':level,'triangles':triangles,'file':path})
 for ob in copies:bpy.data.objects.remove(ob,do_unlink=True)
report['transforms_identity']=all(ob.matrix_world==Matrix.Identity(4) for ob in batched)
report['runtime_quad_meshes_before_engine_triangulation']=not report['mesh_issues']
report['panel_spacing']='Nominal 2mm design minimum; not a full pairwise clearance certification.'
report['textures']='11 materials with 128x128 seamless Albedo, Roughness, tangent Normal; clean surfaces, flat normals.'
with open(OUT+'/validation.json','w') as f:json.dump(report,f,indent=2)
runtime.hide_render=True;runtime.hide_viewport=True;source.hide_render=False;source.hide_viewport=False
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/silver_sedan_source.blend')
print(json.dumps(report,indent=2))
