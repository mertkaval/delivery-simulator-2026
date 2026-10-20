
import bpy
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
for m in list(bpy.data.materials):bpy.data.materials.remove(m)
for i in list(bpy.data.images):
 if i.name!='Render Result':bpy.data.images.remove(i)
for c in list(bpy.data.collections):
 if c.name in ['MODULAR_LIBRARY','ASSEMBLED_HOMES']:bpy.data.collections.remove(c)

import bpy, math, random
import numpy as np
from mathutils import Vector
from math import sin,cos,pi
rng=random.Random(742)
lib=bpy.data.collections.new('MODULAR_LIBRARY');bpy.context.scene.collection.children.link(lib)
kit=bpy.data.objects.new('HousingKit',None);lib.objects.link(kit)
modules={}
def material(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 return m
def texture_material(n,kind,c):
 m=material(n,c);size=512
 yy,xx=np.mgrid[0:size,0:size].astype(float);noise=np.random.default_rng(724+len(n)).random((size,size))
 if kind=='brick':
  row=np.floor(yy/64);col=np.floor((xx+(row%2)*64)/128)
  mortar=(yy%64<5)|((xx+(row%2)*64)%128<5)
  variation=.82+.12*np.sin(col*17+row*31)+noise*.09
  h=np.where(mortar,.1,.75+noise*.12)
  rgb=np.stack([np.where(mortar,.34,variation*v) for v in c],axis=-1)
 elif kind=='siding':
  gap=yy%64<3;grain=np.sin(xx*.18+np.sin(yy*.061)*3)*.018+noise*.045
  h=np.where(gap,.1,.45+yy%64/128+grain)
  rgb=np.stack([np.where(gap,v*.42,v*(.86+grain+yy%64/600)) for v in c],axis=-1)
 elif kind=='roof':
  row=np.floor(yy/64);col=np.floor((xx+(row%2)*32)/64)
  gap=(yy%64<3)|((xx+(row%2)*32)%64<2)
  h=np.where(gap,.1,.5+noise*.22)
  val=.68+.22*np.sin(col*3+row*11)**2+noise*.18
  rgb=np.stack([np.where(gap,v*.5,val*v) for v in c],axis=-1)
 else:
  h=.45+noise*.16;rgb=np.stack([v*(.89+noise*.14) for v in c],axis=-1)
 def image(name,arr,noncolor=False):
  im=bpy.data.images.new(name,width=size,height=size,alpha=True);im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB'
  rgba=np.ones((size,size,4),dtype=np.float32);rgba[:,:,:3]=arr;im.pixels.foreach_set(rgba.ravel());im.pack();return im
 nt=m.node_tree;p=nt.nodes.get('Principled BSDF')
 tx=nt.nodes.new('ShaderNodeTexImage');tx.image=image(n+'_Albedo',np.clip(rgb,0,1));nt.links.new(tx.outputs['Color'],p.inputs['Base Color'])
 dy,dx=np.gradient(h);norm=np.stack([-dx*1.6,-dy*1.6,np.ones_like(h)],axis=-1);norm/=np.linalg.norm(norm,axis=-1,keepdims=True)
 tx=nt.nodes.new('ShaderNodeTexImage');tx.image=image(n+'_Normal',norm*.5+.5,True);nn=nt.nodes.new('ShaderNodeNormalMap');nt.links.new(tx.outputs['Color'],nn.inputs['Color']);nt.links.new(nn.outputs['Normal'],p.inputs['Normal'])
 return m
siding=texture_material('HK_SidingTint','siding',(.73,.77,.72))
stucco=texture_material('HK_StuccoTint','stucco',(.79,.77,.68))
brick=texture_material('HK_Brick','brick',(.49,.22,.13))
roof=texture_material('HK_SlateRoof','roof',(.15,.18,.21))
stone=texture_material('HK_Foundation','brick',(.42,.43,.40))
wood=texture_material('HK_Cedar','siding',(.39,.23,.12))
trim=material('HK_Trim',(.84,.82,.72),0,.5)
metal=material('HK_Zinc',(.12,.16,.18),.78,.35)
glass=material('HK_Glass',(.033,.09,.13),.38,.16)
door=material('HK_DoorTint',(.08,.16,.15),.15,.36)
dark=material('HK_Recess',(.016,.019,.021),0,.95)
leaf=material('HK_Leaf',(.13,.25,.09),0,.85)
flower=material('HK_Flower',(.54,.16,.095),0,.74)
clay=material('HK_Planter',(.29,.16,.10),0,.85)
brass=material('HK_Brass',(.49,.33,.13),.75,.26)
lightmat=material('HK_LampGlass',(.94,.71,.36),0,.34)
p=lightmat.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(.94,.57,.2,1);p.inputs['Emission Strength'].default_value=.22
active=None
def newmodule(n):
 global active
 active=bpy.data.objects.new(n,None);lib.objects.link(active);active.parent=kit;modules[n]=active;return active
def mesh(n,vs,fs,m,bevel=0):
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new(n,me);lib.objects.link(ob);ob.parent=active;me.materials.append(m)
 uv=me.uv_layers.new(name='UVMap')
 for poly in me.polygons:
  normal=poly.normal;axis=max(range(3),key=lambda a:abs(normal[a]))
  for li in poly.loop_indices:
   v=me.vertices[me.loops[li].vertex_index].co
   uv.data[li].uv=(v.x/2,v.z/2) if axis==1 else ((v.y/2,v.z/2) if axis==0 else (v.x/2,v.y/2))
 if bevel:
  mod=ob.modifiers.new('Architectural edge bevel','BEVEL');mod.width=bevel;mod.segments=2
  ob.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
 return ob
def box(n,c,s,m,b=0):
 x,y,z=c;a,d,h=[v/2 for v in s]
 vs=[(x+sx*a,y+sy*d,z+sz*h) for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
 return mesh(n,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m,b)
def beam(n,a,b,r,m,N=8):
 a,b=Vector(a),Vector(b);t=(b-a).normalized();u=t.cross(Vector((0,0,1)))
 if u.length<.01:u=t.cross(Vector((0,1,0)))
 u.normalize();v=t.cross(u);vs=[tuple(p+r*(u*cos(i*2*pi/N)+v*sin(i*2*pi/N))) for p in [a,b] for i in range(N)]
 return mesh(n,vs,[tuple(reversed(range(N))),tuple(N+i for i in range(N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)],m)
def batch(n):
 ob=modules[n];items=[o for o in ob.children_recursive if o.type=='MESH']
 bpy.ops.object.select_all(action='DESELECT')
 for o in items:o.select_set(True)
 bpy.context.view_layer.objects.active=items[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
 part=bpy.context.object;part.name=n+'_Mesh'
 for poly in part.data.polygons:poly.use_smooth=False
 return ob
def wallfinish(m,z0=0,z1=2.8):
 if m==siding:
  for z in np.arange(z0+.10,z1,.18):box('Lapped siding edge',(0,-.119,float(z)),(2,.028,.016),m)
 elif m==stucco:
  for x in [-.96,.96]:box('Plaster corner return',(x,-.12,1.4),(.08,.05,2.8),trim,.004)
def window():
 # Solid dark backing excludes interiors; frame sits in a true wall opening.
 box('Opaque glazing',(0,-.07,1.54),(1.19,.038,1.31),glass,.008)
 for x in [-.64,.64]:box('Window jamb',(x,-.16,1.54),(.11,.19,1.52),trim,.009)
 for z in [.79,2.29]:box('Window head sill',(0,-.16,z),(1.38,.19,.10),trim,.008)
 box('Projecting stone sill',(0,-.25,.75),(1.48,.40,.09),stone,.012)
 box('Drip flashing',(0,-.235,2.36),(1.44,.30,.035),metal,.005)
 box('Centre mullion',(0,-.205,1.54),(.038,.04,1.35),trim,.003)
 box('Sash meeting rail',(0,-.206,1.65),(1.23,.04,.04),trim,.003)
 for x in [-.34,.34]:box('Glass reflection strip',(x,-.094,1.66),(.027,.004,1.06),material('Reflection'+str(x),(.17,.23,.24),.25,.23))
for kind,m in [('siding',siding),('stucco',stucco),('brick',brick)]:
 for opening in ['solid','window','door']:
  n='wall_'+kind+'_'+opening;newmodule(n)
  if opening=='solid':box('Wall',(0,0,1.4),(2,.22,2.8),m);wallfinish(m)
  elif opening=='window':
   for x in [-.815,.815]:box('Wall pier',(x,0,1.4),(.37,.22,2.8),m)
   box('Spandrel',(0,0,.37),(1.26,.22,.74),m);box('Lintel',(0,0,2.555),(1.26,.22,.49),m);window()
  else:
   for x in [-.80,.80]:box('Entrance pier',(x,0,1.4),(.40,.22,2.8),m)
   box('Door lintel',(0,0,2.53),(1.20,.22,.54),m)
   box('Door leaf',(0,-.025,1.13),(1.14,.14,2.26),door,.01)
   for x in [-.62,.62]:box('Door frame',(x,-.155,1.16),(.10,.12,2.32),trim,.007)
   box('Door head',(0,-.155,2.33),(1.34,.12,.12),trim,.007)
   for x in [-.29,.29]:
    for z in [.46,1.04]:box('Raised door panel',(x,-.106,z),(.45,.025,.43),door,.014)
   box('Frosted transom',(0,-.103,1.85),(.82,.012,.47),glass,.008)
   box('Door transom bar',(0,-.126,1.85),(.035,.025,.49),trim)
   beam('Door handle',(.43,-.17,.98),(.43,-.17,1.13),.012,brass)
   box('Letter slot',(0,-.13,1.34),(.30,.025,.05),brass,.004)
   box('Threshold',(0,-.20,.025),(1.36,.47,.05),stone,.005)
  batch(n)
newmodule('foundation');box('Raised foundation',(0,0,.12),(2,.28,.24),stone,.009);box('Water table cap',(0,-.045,.265),(2,.35,.05),trim,.006);batch('foundation')
newmodule('cornice');box('Fascia',(0,-.04,0),(2,.20,.20),trim,.007);box('Soffit',(0,.055,-.11),(2,.38,.045),trim)
for x in np.arange(-.90,1,.2):box('Soffit vent',(float(x),-.05,-.137),(.11,.06,.008),metal)
beam('Rain gutter',(-1,-.19,-.035),(1,-.19,-.035),.065,metal,12);batch('cornice')
newmodule('corner');box('Corner trim',(0,0,1.4),(.14,.14,2.8),trim,.007);batch('corner')
newmodule('downpipe')
for a,b in [((0,0,2.8),(0,0,.25)),((0,0,.25),(0,-.22,.07))]:beam('Downspout',a,b,.036,metal)
for z in [.45,1.55,2.65]:box('Pipe wall bracket',(0,.02,z),(.10,.12,.035),metal,.003)
batch('downpipe')
newmodule('shutters')
for s in [-1,1]:
 box('Shutter frame',(s*.84,-.18,1.54),(.28,.075,1.4),door,.008)
 for z in np.arange(.9,2.2,.10):box('Shutter louvre',(s*.84,-.23,float(z)),(.235,.04,.035),door,.003)
batch('shutters')
# Roof modules use width 10m, 2m length. Ridge runs Y.
newmodule('roof_gable_slice')
mesh('Roof slopes',[(-5.3,-1,0),(0,-1,1.8),(5.3,-1,0),(-5.3,1,0),(0,1,1.8),(5.3,1,0)],[(0,3,4,1),(1,4,5,2)],roof)
for side in [-1,1]:
 for x in np.arange(.25,5.3,.32):
  xx=side*float(x);zz=1.8*(1-abs(xx)/5.3)
  beam('Shingle course edge',(xx,-1,zz+.01),(xx,1,zz+.01),.013,roof,4)
beam('Ridge cap',(0,-1,1.83),(0,1,1.83),.085,roof,8);batch('roof_gable_slice')
newmodule('gable_end')
mesh('Closed gable',[(-5,0,0),(5,0,0),(0,0,1.70),(-5,.16,0),(5,.16,0),(0,.16,1.70)],[(0,1,2),(3,5,4),(0,3,4,1),(1,4,5,2),(2,5,3,0)],siding)
for s in [-1,1]:beam('Bargeboard',(s*5.34,-.12,-.015),(0,-.12,1.83),.065,trim,4)
box('Attic vent',(0,-.105,.62),(.7,.05,.47),dark)
for z in [.43,.53,.63,.73,.83]:box('Vent louvre',(0,-.145,z),(.72,.04,.026),trim)
batch('gable_end')
newmodule('roof_hip')
mesh('Hip roof',[(-5.35,-4.35,0),(5.35,-4.35,0),(5.35,4.35,0),(-5.35,4.35,0),(0,-1.65,1.8),(0,1.65,1.8)],[(0,1,4),(1,2,5,4),(2,3,5),(3,0,4,5)],roof)
for a,b in [((-5.35,-4.35,0),(0,-1.65,1.8)),((5.35,-4.35,0),(0,-1.65,1.8)),((-5.35,4.35,0),(0,1.65,1.8)),((5.35,4.35,0),(0,1.65,1.8)),((0,-1.65,1.8),(0,1.65,1.8))]:beam('Hip ridge',a,b,.065,roof)
batch('roof_hip')
newmodule('roof_flat')
box('Warm flat roof',(0,0,.05),(10.5,8.5,.10),roof)
for x in [-5.15,5.15]:box('Parapet side',(x,0,.19),(.18,8.5,.35),stucco);box('Parapet coping',(x,0,.38),(.24,8.55,.045),metal,.007)
for y in [-4.15,4.15]:box('Parapet front',(0,y,.19),(10.15,.18,.35),stucco);box('Parapet coping',(0,y,.38),(10.5,.24,.045),metal,.007)
batch('roof_flat')
newmodule('porch')
# Low flush paving keeps the delivery path walkable; columns flank the route.
box('Porch paving',(0,-1.2,.035),(3.4,2.4,.07),stone,.01)
for x in [-1.45,1.45]:
 box('Stone pier base',(x,-2.05,.28),(.38,.38,.56),stone,.014)
 box('Porch column',(x,-2.05,1.50),(.16,.16,2.45),trim,.008)
 box('Column capital',(x,-2.05,2.64),(.26,.26,.13),trim,.01)
box('Porch header',(0,-2.05,2.77),(3.35,.20,.22),trim,.01)
mesh('Porch standing seam canopy',[(-1.8,.06,2.94),(1.8,.06,2.94),(1.8,-2.4,2.78),(-1.8,-2.4,2.78)],[(0,1,2,3)],metal)
for x in np.arange(-1.7,1.8,.35):beam('Canopy seam',(float(x),.06,2.958),(float(x),-2.4,2.798),.011,metal,4)
batch('porch')
newmodule('entry_canopy');box('Canopy slab',(0,-.7,2.65),(2.1,1.4,.12),metal,.015)
for x in [-.85,.85]:beam('Canopy support',(x,0,2.35),(x,-1.15,2.61),.018,metal)
batch('entry_canopy')
newmodule('chimney');box('Masonry chimney',(0,0,.75),(.70,.74,1.5),brick,.015);box('Chimney cap',(0,0,1.53),(.90,.94,.10),stone,.01)
for x in [-.20,.20]:beam('Flue pot',(x,0,1.56),(x,0,1.84),.105,clay,12)
box('Lead flashing',(0,0,.04),(.94,.99,.08),metal,.007);batch('chimney')
newmodule('entry_lamp')
box('Lamp backplate',(0,0,0),(.12,.05,.25),metal,.008);box('Lamp glazing',(0,-.13,.0),(.14,.15,.22),lightmat,.008)
for z in [-.14,.14]:box('Lamp cap',(0,-.13,z),(.20,.20,.04),metal,.005)
for x in [-.08,.08]:beam('Lantern bar',(x,-.21,-.12),(x,-.21,.12),.009,metal)
batch('entry_lamp')
newmodule('flowerbox')
box('Timber planter',(0,-.31,.52),(1.42,.40,.25),wood,.015);box('Soil',(0,-.31,.66),(1.31,.31,.018),dark)
for i in range(22):
 x=rng.uniform(-.6,.6);y=rng.uniform(-.44,-.18);z=rng.uniform(.73,.93)
 beam('Flower stem',(x,y,.66),(x,y,z),.008,leaf,5)
 for a in range(5):
  angle=a*2*pi/5
  mesh('Flower petal',[(x,y,z),(x+.068*cos(angle-.45),y+.068*sin(angle-.45),z+.02),(x+.086*cos(angle),y+.086*sin(angle),z),(x+.068*cos(angle+.45),y+.068*sin(angle+.45),z+.02)],[(0,1,2,3)],flower)
 for s in [-1,1]:mesh('Leaf',[(x,y,z-.13),(x+s*.09,y-.035,z-.10),(x+s*.14,y,z-.07),(x+s*.07,y+.035,z-.10)],[(0,1,2,3)],leaf)
batch('flowerbox')
newmodule('utility')
box('Meter cabinet',(0,0,1.1),(.38,.18,.5),metal,.015)
for x in [-.11,.11]:beam('Service conduit',(x,.03,.08),(x,.03,.88),.016,metal)
box('Vent grille',(0,-.10,1.12),(.26,.025,.30),dark)
for z in [1.02,1.07,1.12,1.17,1.22]:box('Grille strip',(0,-.12,z),(.28,.015,.012),metal)
batch('utility')

gallery=bpy.data.collections.new('ASSEMBLED_HOMES');bpy.context.scene.collection.children.link(gallery)
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
 place(home,'chimney',(-w*.28,d*.7,h+(.08 if i//4==2 else .6)))
 place(home,'utility',(w/2+.12,d*.75,.1),-pi/2)
 return home


# Create lighting and delivery camera before assembling the production gallery.
# Catalog meshes retained for GLB.
for o in kit.children_recursive:o.hide_render=True
bpy.context.scene.world=bpy.data.worlds.new('Coastal daylight');bpy.context.scene.world.use_nodes=True
bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.67,.8,1);bpy.context.scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
data=bpy.data.lights.new('Warm afternoon sun','SUN');data.energy=2.3;data.angle=.12;o=bpy.data.objects.new('Warm afternoon sun',data);bpy.context.collection.objects.link(o);o.rotation_euler=(.55,-.4,-.5)
data=bpy.data.lights.new('Sky fill','AREA');data.energy=1800;data.size=20;o=bpy.data.objects.new('Sky fill',data);bpy.context.collection.objects.link(o);o.location=(10,-12,16);o.rotation_euler=(Vector((10,8,0))-o.location).to_track_quat('-Z','Y').to_euler()
active=None
ground=box('Gallery ground',(14,12,-.08),(75,65,.12),material('Ground',(.24,.29,.23)))
camd=bpy.data.cameras.new('Housing delivery camera');cam=bpy.data.objects.new('Housing delivery camera',camd);bpy.context.collection.objects.link(cam);cam.location=(43,-39,30);cam.rotation_euler=(Vector((14,9,2))-cam.location).to_track_quat('-Z','Y').to_euler();camd.type='ORTHO';camd.ortho_scale=53

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
