
import bpy, math
from mathutils import Vector
K={};exec(bpy.data.texts['kitlib.py'].as_string(),K)
def box(c,s,m,rot=None):
 it={'k':'box','c':c,'s':s,'m':m,'u':.5}
 if rot:it['r']=rot
 return it
def perimeter(x0,x1,y0,y1,h,mat,front,back=True,z0=.18):
 a=K['wall']('x',x0,x1,y0,z0,h,.22,mat,front)
 if back:
  mid=(x0+x1)/2;ops=[(mid-.65,mid+.65,1.0,2.3)]
  a+=K['wall']('x',x0,x1,y1,z0,h,.22,mat,ops)
  a+=K['window']('x',mid,y1,1.65,1.30,1.30)
 for side,x in [(-1,x0),(1,x1)]:
  ys=[y0+(y1-y0)*.36,y0+(y1-y0)*.72];ops=[(y-.52,y+.52,.94,2.28) for y in ys]
  if h>4:ops +=[(y-.52,y+.52,3.84,5.05) for y in []] # Ground wall split handled separately below.
  a+=K['wall']('y',y0,y1,x,z0,min(h,3.04),.22,mat,[(y-.52,y+.52,.94,2.28) for y in ys])
  for y in ys:a+=K['window']('y',y,x,1.61,1.04,1.34)
  if h>3.1:
   a+=K['wall']('y',y0,y1,x,3.04,h,.22,mat,[(y-.52,y+.52,3.84,5.05) for y in ys])
   for y in ys:a+=K['window']('y',y,x,4.445,1.04,1.21)
 a += [it for it in K['dress'](x0,x1,y0,y1,.14,h,corner=.085,fascia=False) if it['m']!='HK_Zinc']
 a+=[box(((x0+x1)/2,y0,.13),(x1-x0+.08,.30,.26),'HK_Foundation'),box(((x0+x1)/2,y1,.13),(x1-x0+.08,.30,.26),'HK_Foundation')]
 for x in [x0,x1]:a.append(box((x,(y0+y1)/2,.13),(.30,y1-y0,.26),'HK_Foundation'))
 # Lower splash-zone masonry and drip caps.
 a+=[box(((x0+x1)/2,y0-.025,.31),(x1-x0,.27,.06),'HK_Foundation')]
 return a
def framed_front(items,x,y,z,w=1.25,h=1.32):
 items+=K['window']('x',x,y,z,w,h)
 items.append(box((x,y-.15,z+h/2+.14),(w+.27,.33,.10),'HK_Foundation'))
def porch_gabled():
 a=[box((0,-.88,.05),(2.6,1.8,.10),'HK_Concrete')]
 for x in [-1.12,1.12]:
  a+=[box((x,-1.48,.27),(.32,.32,.54),'HK_Foundation'),box((x,-1.48,1.45),(.14,.14,2.34),'HK_Cedar')]
 a+=[box((0,-1.48,2.60),(2.50,.18,.18),'HK_Cedar')]
 a+=K['gable'](0,-.77,2.72,2.7,1.8,.58,.09,.1,'HK_SlateRoof','HK_Cedar',.5)
 for side in [-1,1]:a.append(box((side*.89,-1.47,2.33),(.09,.10,.72),'HK_Cedar',(0,side*-.65,0)))
 return a
def bay(x,y):
 a=[box((x,y-.33,.45),(1.80,.68,.65),'HK_Foundation')]
 # Three glazed facets with actual solid side cheeks, not a painted flat box.
 a+=K['window']('x',x,y-.68,1.67,1.40,1.60)
 for side in [-1,1]:
  a+=K['window']('y',y-.32,x+side*.82,1.67,.43,1.60,thick=.13)
 a+=[box((x,y-.32,2.55),(1.95,.85,.12),'HK_Zinc'),box((x,y-.32,.83),(1.95,.85,.10),'HK_Foundation')]
 return a
def terrace_rail(x0,x1,y0,y1,z):
 a=K['rail']('x',x0,x1,y0,z,.97)
 a+=K['rail']('y',y0,y1,x1,z,.97)
 return a
modules={'quality_porch_gabled':porch_gabled(),'quality_bay_window':bay(0,0),'quality_terrace_guard':terrace_rail(-1,1,0,1,0)}
kit=bpy.data.objects['HousingKit']
for name,items in modules.items():
 old=bpy.data.objects.get(name)
 if old:bpy.data.objects.remove(old,do_unlink=True)
 ob=K['build'](name,items);ob.parent=kit;ob.hide_render=True
stats={}
for i in range(12):
 w=[8,9,10,8.6][i%4];d=[6.4,8,7.2][i%3];kind=i%4
 mat=['HK_SidingTint','HK_StuccoTint','HK_Brick'][i//4]
 if kind==0:
  # Craftsman: tall main cottage and lower recessed side wing.
  split=w*.16
  a=perimeter(-w/2,split,0,d,3.04,mat,[(-.58,.58,.18,2.36),(-w*.34-.63,-w*.34+.63,.97,2.31)])
  a+=K['door']('x',0,0,.18,1.16,2.18);framed_front(a,-w*.34,0,1.64)
  a+=perimeter(split,w/2,1.2,d,2.72,'HK_Cedar',[(w*.33-.58,w*.33+.58,.9,2.15)])
  framed_front(a,w*.33,1.2,1.525,1.16,1.25)
  a+=K['gable']((-w/2+split)/2,d/2,3.04,split+w/2,d,1.75,.12,.32,'HK_SlateRoof',mat,.5)
  a+=K['flat_roof']((split+w/2)/2,(d+1.2)/2,2.72,w/2-split,d-1.2,.10,'HK_Zinc',False)
  a+=porch_gabled()
 elif kind==1:
  # Cottage: upper storey under a steep roof, asymmetric ground-floor bay.
  lower=[(-.58,.58,.18,2.36),(-w*.29-.74,-w*.29+.74,.82,2.48),(w*.29-.6,w*.29+.6,1.02,2.28)]
  a=perimeter(-w/2,w/2,0,d,3.04,'HK_Foundation',lower)
  a+=K['wall']('x',-w/2,w/2,0,3.04,5.35,.22,mat,[(-2.1,-.9,3.72,4.96),(.9,2.1,3.72,4.96)])
  a+=K['wall']('x',-w/2,w/2,d,3.04,5.35,.22,mat,[(-.65,.65,3.72,4.96)])
  for xx in [-w/2,w/2]:a+=K['wall']('y',0,d,xx,3.04,5.35,.22,mat,[(d*.5-.6,d*.5+.6,3.72,4.96)]);a+=K['window']('y',d*.5,xx,4.34,1.2,1.24)
  for x in [-1.5,1.5]:framed_front(a,x,0,4.34,1.2,1.24)
  a+=K['window']('x',0,d,4.34,1.3,1.24)
  a+=K['door']('x',0,0,.18,1.16,2.18);a+=bay(-w*.29,0);framed_front(a,w*.29,0,1.65,1.2,1.26)
  a+=K['gable'](0,d/2,5.35,w,d,2.15,.12,.33,'HK_SlateRoof',mat,.5)
  a+=[box((0,-.60,2.64),(1.85,1.20,.12),'HK_Zinc')]
  # Continuous string course articulates the two materials.
  a+=[box((0,-.04,3.04),(w+.12,.30,.10),'HK_Trim')]
 elif kind==2:
  # Brick urban house with taller vertically proportioned windows and a clipped canopy.
  lower=[(-.58,.58,.18,2.36),(-w*.3-.66,-w*.3+.66,.85,2.40),(w*.3-.66,w*.3+.66,.85,2.40)]
  a=perimeter(-w/2,w/2,0,d,3.04,'HK_Brick',lower)
  upper=[(x-.60,x+.60,3.64,5.16) for x in [-w*.30,0,w*.30]]
  a+=K['wall']('x',-w/2,w/2,0,3.04,5.84,.22,mat,upper)
  a+=K['wall']('x',-w/2,w/2,d,3.04,5.84,.22,mat,upper)
  for xx in [-w/2,w/2]:a+=K['wall']('y',0,d,xx,3.04,5.84,.22,mat,[(d*.5-.6,d*.5+.6,3.64,5.16)]);a+=K['window']('y',d*.5,xx,4.40,1.2,1.52)
  for x in [-w*.30,0,w*.30]:
   framed_front(a,x,0,4.40,1.2,1.52);a+=K['window']('x',x,d,4.40,1.2,1.52)
  for x in [-w*.3,w*.3]:framed_front(a,x,0,1.625,1.32,1.55)
  a+=K['door']('x',0,0,.18,1.16,2.18)
  a+=K['gable'](0,d/2,5.84,w,d,1.20,.12,.20,'HK_SlateRoof','HK_Brick',.5)
  a+=[box((0,-.04,5.78),(w+.20,.35,.20),'HK_Foundation'),box((0,-.62,2.64),(2.1,1.25,.12),'HK_Zinc')]
  for x in [-w/2+.2,w/2-.2]:a+=[box((x,-.08,2.95),(.22,.30,5.65),'HK_Brick')]
 else:
  # Contemporary: two-storey main volume, one-storey offset cedar wing and real terrace.
  split=w*.15
  a=perimeter(-w/2,split,0,d,3.04,'HK_StuccoTint',[(-.58,.58,.18,2.36),(-w*.33-.68,-w*.33+.68,.92,2.32)])
  a+=K['wall']('x',-w/2,split,0,3.04,5.84,.22,'HK_StuccoTint',[(-w*.28-.85,-w*.28+.85,3.80,5.15)])
  a+=K['wall']('x',-w/2,split,d,3.04,5.84,.22,'HK_StuccoTint',[])
  a+=K['wall']('y',0,d,-w/2,3.04,5.84,.22,'HK_StuccoTint',[])
  # Closed terrace access opening on upper side wall.
  a+=K['wall']('y',0,d,split,3.04,5.84,.22,'HK_Cedar',[(1.6,2.6,3.16,5.30)])
  a+=K['door']('y',2.1,split,3.16,1.0,2.14)
  a+=K['door']('x',0,0,.18,1.16,2.18);framed_front(a,-w*.33,0,1.62,1.36,1.4);framed_front(a,-w*.28,0,4.475,1.70,1.35)
  a+=perimeter(split,w/2,.65,d,3.04,'HK_Cedar',[(w*.325-.63,w*.325+.63,1.0,2.35)])
  framed_front(a,w*.325,.65,1.675,1.26,1.35)
  a+=K['flat_roof']((-w/2+split)/2,d/2,5.84,split+w/2,d,.15,'HK_SlateRoof',True,'HK_StuccoTint')
  a+=K['flat_roof']((split+w/2)/2,(d+.65)/2,3.04,w/2-split,d-.65,.12,'HK_SlateRoof',False)
  a+=terrace_rail(split+.12,w/2-.12,.77,d-.12,3.16)
  a+=[box((0,-.7,2.65),(2.15,1.4,.13),'HK_Zinc')]
 # Door threshold is reachable from the existing delivery path; no interior is built.
 a+=[box((0,-.22,.09),(1.42,.50,.18),'HK_Concrete')]
 # Plaque and doorbell, grounding household-scale details.
 a+=[box((.89,-.155,1.48),(.22,.055,.12),'HK_Zinc'),box((.75,-.16,1.17),(.055,.05,.09),'HK_Brass')]
 # Retain working lanterns and selected flower boxes from original authored kit.
 home=bpy.data.objects['Example_Home_%02d'%i]
 for child in list(home.children_recursive):bpy.data.objects.remove(child,do_unlink=True)
 obj=K['build']('HouseExterior_%02d'%i,a,coll='ASSEMBLED_HOMES');obj.parent=home
 mod=obj.modifiers.new('Fine manufactured edge highlights','BEVEL');mod.width=.009;mod.segments=2
 mod=obj.modifiers.new('Weighted architectural normals','WEIGHTED_NORMAL')
 extras=[]
 def instance_module(name,loc,scale=(1,1,1)):
  src=bpy.data.objects[name]
  for ch in ([src] if src.type=='MESH' else src.children):
   if ch.type!='MESH':continue
   ob=bpy.data.objects.new('Detail_'+name,ch.data);bpy.data.collections['ASSEMBLED_HOMES'].objects.link(ob);ob.parent=home;ob.location=loc;ob.scale=scale;ob.hide_render=False;extras.append(ob)
 instance_module('entry_lamp',(1.10,-.18,2.10))
 if kind in [0,1]:
  instance_module('flowerbox',(-w*.29,-.70 if kind==1 else 0,.17))
  if i%2==0:instance_module('flowerbox',(w*.33,1.2,.17))
 # Downpipes and rain gutters belong to actual eaves, not arbitrary wall centres.
 h=[3.04,5.35,5.84,5.84][kind]
 for side in [-1,1]:
  ph=(2.72 if kind==0 else 3.04) if kind in [0,3] and side==1 else h
  instance_module('downpipe',(side*(w/2+.055),-.10,.18),(1,1,(ph-.18)/2.8))
 # Modifiers are applied before joining to retain bevels in exported mesh.
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
 for ob in extras:ob.select_set(True)
 bpy.context.view_layer.objects.active=obj;bpy.ops.object.join()
 obj.data.calc_loop_triangles()
 stats[str(i)]={'family':['craftsman_bungalow','stone_cottage','brick_townhouse','terrace_house'][kind],'triangles':len(obj.data.loop_triangles)}
 home['architecture_family']=stats[str(i)]['family'];home['asset_revision']='quality_oct03'
# Keep all independently authored Home_* and yard/library objects intact.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
cam=bpy.data.objects['Housing delivery camera'];cam.location=(34,-31,20);cam.rotation_euler=(Vector((16,3,2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=49;scene.camera=cam
target=artifacts.file(name='housing_character_revision.png',media_type='image/png');scene.render.image_settings.file_format='PNG';scene.render.filepath=target.path;bpy.ops.render.render(write_still=True);target.publish()
result={'homes':stats,'preserved_existing_archetypes':True,'new_modules':list(modules)}
