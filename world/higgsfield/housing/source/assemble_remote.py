
import bpy, math
from mathutils import Vector
from math import pi
modules={o.name:o for o in bpy.data.objects['HousingKit'].children}
gallery=bpy.data.collections['ASSEMBLED_HOMES']
for ob in list(gallery.objects):bpy.data.objects.remove(ob,do_unlink=True)
def place(parent,n,loc=(0,0,0),rot=0,scale=(1,1,1)):
 src=modules[n];o=bpy.data.objects.new(n,None);gallery.objects.link(o);o.parent=parent;o.location=loc;o.rotation_euler.z=rot;o.scale=scale
 for ch in src.children:
  c=bpy.data.objects.new(ch.name,ch.data);gallery.objects.link(c);c.parent=o;c.matrix_basis=ch.matrix_basis.copy()
 return o
def house(i,offset):
 w=[8,9,10,8.6][i%4];d=[6.4,8,7.2][i%3];floors=1 if i%4==0 else 2;kind=['siding','stucco','brick'][i%3]
 home=bpy.data.objects.new('Example_Home_%02d'%i,None);gallery.objects.link(home);home.location=offset
 for f in range(floors):
  for j in range(5):
   x=(j-2)*w/5
   for back in [False,True]:
    opening='door' if f==0 and j==2 and not back else ('window' if j in [1,3] or (f>0 and j==2) else 'solid')
    place(home,'wall_'+kind+'_'+opening,(x,d if back else 0,.24+f*2.8),pi if back else 0,(w/10,1,1))
  for side in [-1,1]:
   for j in range(4):place(home,'wall_'+kind+('_window' if j in [1,2] else '_solid'),(side*w/2,(j+.5)*d/4,.24+f*2.8),side*pi/2,(d/8,1,1))
  for x in [-w/2,w/2]:
   for y in [0,d]:place(home,'corner',(x,y,.24+f*2.8))
 h=.24+floors*2.8
 for j in range(5):
  for y,rot in [(0,0),(d,pi)]:
   place(home,'foundation',((j-2)*w/5,y,0),rot,(w/10,1,1))
   place(home,'cornice',((j-2)*w/5,y,h),rot,(w/10,1,1))
 for side in [-1,1]:
  for j in range(4):
   place(home,'foundation',(side*w/2,(j+.5)*d/4,0),side*pi/2,(d/8,1,1))
   place(home,'cornice',(side*w/2,(j+.5)*d/4,h),side*pi/2,(d/8,1,1))
 if i//4==0:
  for j in range(4):place(home,'roof_gable_slice',(0,(j+.5)*d/4,h),0,(w/10,d/8,1))
  place(home,'gable_end',(0,-.14,h),0,(w/10,1,1));place(home,'gable_end',(0,d+.14,h),pi,(w/10,1,1))
 elif i//4==1:place(home,'roof_hip',(0,d/2,h),0,(w/10,d/8,1))
 else:place(home,'roof_flat',(0,d/2,h),0,(w/10,d/8,1))
 place(home,'porch' if i%2==0 else 'entry_canopy',(0,0,0))
 place(home,'entry_lamp',(1.12,-.16,2.07))
 for s in [-1,1]:
  place(home,'downpipe',(s*(w/2-.13),-.22,.2),0,(1,1,floors))
  place(home,'flowerbox',(s*w/5,0,.24))
  if i%2==0:place(home,'shutters',(s*w/5,0,.24))
 place(home,'chimney',(-w*.28,d*.7,h+.6))
 place(home,'utility',(w/2+.12,d*.75,.1),-pi/2)
 return home

stats={}
for i in range(12):
 home=house(i,((i%4)*14,(i//4)*17,0))
 items=[o for o in home.children_recursive if o.type=='MESH']
 bpy.ops.object.select_all(action='DESELECT')
 for o in items:o.select_set(True)
 items[0].data=items[0].data.copy()
 bpy.context.view_layer.objects.active=items[0];bpy.ops.object.join()
 joined=bpy.context.object;mw=joined.matrix_world.copy();joined.parent=home;joined.matrix_world=mw;joined.name='HouseExterior_%02d'%i
 # Keep the library editable, while preassembled variants share one static mesh per house.
 for o in list(home.children_recursive):
  if o!=joined and o.type=='EMPTY':bpy.data.objects.remove(o,do_unlink=True)
 joined.data.calc_loop_triangles();stats[home.name]={'triangles':len(joined.data.loop_triangles),'materials':len(joined.data.materials)}
 home['variant_id']=i;home['footprint_width']=[8,9,10,8.6][i%4];home['footprint_depth']=[6.4,8,7.2][i%3];home['stories']=1 if i%4==0 else 2
scene=bpy.context.scene;cam=bpy.data.objects['Housing delivery camera'];cam.location=(60,-52,43);cam.rotation_euler=(Vector((21,18,2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=73
scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=1440;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
target=artifacts.file(name='twelve_modular_homes.png',media_type='image/png');scene.render.filepath=target.path;bpy.ops.render.render(write_still=True);target.publish()
result={'variants':stats,'module_count':24}
