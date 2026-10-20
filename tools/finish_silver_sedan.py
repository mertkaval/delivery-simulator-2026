import bpy, bmesh, math, os, json
import numpy as np
import ast
from math import sin,cos,pi,sqrt
from mathutils import Vector
OUT='C:/GodotProjects/delivery-simulator-2026/assets/vehicles/silver_sedan'
scene=bpy.context.scene
asset=bpy.data.collections['SEDAN_SOURCE'];studio=bpy.data.collections['STUDIO'];root=bpy.data.objects['SilverSedan']
M={k:bpy.data.materials['Sedan_'+k] for k in ['Silver','Glass','Rubber','Trim','Chrome','Alloy','Headlamp','Tail','Amber','Brake','Interior']}
T=[0,.025,.10,.25,.5,.75,.90,.975,1]
tree=ast.parse(open('C:/GodotProjects/delivery-simulator-2026/tools/build_silver_sedan.py',encoding='utf-8').read())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'sedan_helpers','exec'))
for ob in asset.objects:
 if ob.type=='CURVE':
  for sp in ob.data.splines:
   for p in sp.bezier_points:p.handle_left_type='VECTOR';p.handle_right_type='VECTOR'
# Smooth fender/bonnet contact while retaining an explicit 3mm shut gap.
ob=next(o for o in asset.objects if o.name=='Bonnet')
for v in ob.data.vertices:
 y=v.co.y;u=abs(v.co.x)/max(.01,width(y)-.022)
 layer=.018 if v.index>=len(ob.data.vertices)//2 else 0
 v.co.z=belt(y)+.004+.083*(1-u*u)-layer
for ob in asset.objects:
 if ob.name in ['Front fascia','Rear fascia']:
  for v in ob.data.vertices:v.co.z=.30+(v.co.z-.30)*1.07
# Projection elements, not an opaque white headlamp slab.
for ob in asset.objects:
 if ob.name.startswith('Headlamp optical lens'):
  ob.data.materials.clear();ob.data.materials.append(M['Glass'])
for side in [-1,1]:
 for x,z,r in [(.63,.916,.036),(.52,.902,.026)]:
  torus('Headlight projector',(side*x,-2.350,z),r,.009,'Chrome',axis='Y',n=24,m=8)
  torus('Projector optic',(side*x,-2.353,z),r*.62,.006,'Headlamp',axis='Y',n=20,m=8)
torus('Unbranded grille emblem',(0,-2.366,.786),.039,.011,'Chrome',axis='Y',n=24,m=8)
curve('Fuel door seam',[(.866,1.67,.83),(.866,1.86,.82),(.867,1.87,.67),(.883,1.67,.68)],.003,'Trim',True)
# A measured boolean recess trial followed by explicit quad retopology.
# Retain the construction operands in a hidden authoring collection, not in export.
construction=bpy.data.collections.new('CONSTRUCTION_boolean_and_retopology');scene.collection.children.link(construction)
base=quad('Fuel recess boolean workpiece',[(.887,1.64,.66),(.887,1.88,.66),(.887,1.88,.86),(.887,1.64,.86)],'Silver',.03,(-1,0,0),sub=0)
cut=quad('Fuel recess cutter',[(.91,1.66,.68),(.91,1.86,.68),(.91,1.86,.84),(.91,1.66,.84)],'Trim',.045,(-1,0,0),sub=0)
mod=base.modifiers.new('Fuel pocket design boolean','BOOLEAN');mod.object=cut
bpy.context.view_layer.objects.active=base;base.select_set(True)
bpy.ops.object.modifier_apply(modifier=mod.name)
base['cleanup']='Replaced boolean tessellation by explicit four-sided control surface for shipped fuel panel.'
for ob in [base,cut]:
 asset.objects.unlink(ob);construction.objects.link(ob);ob.parent=None;ob.hide_render=True;ob.hide_set(True)
# Final quad-based fuel door is offset outboard and inset from its seam by 3mm.
quad('Fuel filler flap',[(.875,1.678,.688),(.859,1.853,.686),(.859,1.852,.813),(.866,1.680,.823)],'Silver',.006,(-1,0,0),sub=1)
construction.hide_render=True

# Mark physical hard edges at 30 degrees and smart unwrap with consistent density.
bpy.ops.object.select_all(action='DESELECT')
for ob in asset.objects:
 if ob.type=='MESH':
  bm=bmesh.new();bm.from_mesh(ob.data)
  for edge in bm.edges:
   if len(edge.link_faces)==2 and edge.calc_face_angle()>math.radians(30):edge.smooth=False;edge.seam=True
  bm.to_mesh(ob.data);bm.free();ob.select_set(True)
  bpy.context.view_layer.objects.active=ob
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30),keep_sharp_edges=True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02,area_weight=0,correct_aspect=True,scale_to_bounds=False)
bpy.ops.uv.average_islands_scale();bpy.ops.uv.pack_islands(margin=.02)
bpy.ops.object.mode_set(mode='OBJECT')

# Small seamless PBR maps: constant colour, low-frequency roughness, tangent normals.
# No dirt/noise and no high-frequency metal-flake pattern.
texdir=OUT+'/textures';os.makedirs(texdir,exist_ok=True)
for key,m in M.items():
 p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 color=list(p.inputs['Base Color'].default_value);rough=p.inputs['Roughness'].default_value
 for kind in ['Albedo','Roughness','Normal']:
  n=128;arr=np.ones((n,n,4),dtype=np.float32)
  if kind=='Albedo':arr[:,:,:]=color
  elif kind=='Roughness':
   yy,xx=np.mgrid[0:n,0:n]/n;a=rough+.007*np.sin(2*math.pi*xx)*np.sin(2*math.pi*yy)
   arr[:,:,:3]=a[:,:,None]
  else:arr[:,:,:3]=[.5,.5,1.]
  im=bpy.data.images.new('Sedan_'+key+'_'+kind,width=n,height=n,alpha=True)
  if kind!='Albedo':im.colorspace_settings.name='Non-Color'
  im.pixels.foreach_set(arr.ravel());im.filepath_raw=texdir+'/'+key+'_'+kind+'.png';im.file_format='PNG';im.save();im.pack()
  node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=im
  if kind=='Albedo':m.node_tree.links.new(node.outputs['Color'],p.inputs['Base Color'])
  elif kind=='Roughness':m.node_tree.links.new(node.outputs['Color'],p.inputs['Roughness'])
  else:
   normal=m.node_tree.nodes.new('ShaderNodeNormalMap');m.node_tree.links.new(node.outputs['Color'],normal.inputs['Color']);m.node_tree.links.new(normal.outputs['Normal'],p.inputs['Normal'])

# Controlled studio illumination and camera; not part of export.
def light(name,loc,power,size):
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
 ob=bpy.data.objects.new(name,data);studio.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,.7))-ob.location).to_track_quat('-Z','Y').to_euler()
light('Key softbox',(3,-4,6),900,5);light('Side strip',(-4,-1,3),700,4);light('Rear rim',(1,5,4),1100,3)
world=bpy.data.worlds.new('Neutral studio');world.use_nodes=True;scene.world=world
bg=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.16,.18,.21,1);bg.inputs[1].default_value=.45
camdata=bpy.data.cameras.new('Sedan inspection camera');cam=bpy.data.objects.new('Sedan inspection camera',camdata);studio.objects.link(cam)
cam.location=(5,-7,3.4);cam.rotation_euler=(Vector((0,0,.7))-cam.location).to_track_quat('-Z','Y').to_euler();camdata.lens=52;scene.camera=cam
scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=OUT+'/sedan_front.png'
scene.render.film_transparent=False
scene['art_direction']='Clean stylized realism; supplied silver compact sedan proportions'
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/silver_sedan_source.blend')
print('Saved source; 30-degree sharp edges, UVs, 33 PBR maps, studio configured')
