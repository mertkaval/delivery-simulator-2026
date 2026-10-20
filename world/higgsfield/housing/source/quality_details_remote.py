
import bpy,math
from mathutils import Vector
K={};exec(bpy.data.texts['kitlib.py'].as_string(),K)
def box(c,s,m,r=None):
 a={'k':'box','c':c,'s':s,'m':m,'u':.5}
 if r:a['r']=r
 return a
def sloping(a,b,width,depth,mat):
 a,b=Vector(a),Vector(b);t=b-a
 return box(tuple((a+b)/2),(width,depth,t.length),mat,tuple(t.to_track_quat('Z','Y').to_euler()))
counts={}
for i in range(12):
 home=bpy.data.objects['Example_Home_%02d'%i];obj=next(c for c in home.children if c.type=='MESH')
 w=[8,9,10,8.6][i%4];d=[6.4,8,7.2][i%3];kind=i%4;a=[]
 if kind<3:
  h=[3.04,5.35,5.84][kind];rise=[1.75,2.15,1.2][kind]
  x0=-w/2; x1=w*.16 if kind==0 else w/2;cx=(x0+x1)/2;oh=.32 if kind<2 else .20
  a+=[box((cx,d/2,h+rise+.08),(.19,d+2*oh,.10),'HK_SlateRoof')]
  for y in [-oh,d+oh]:
   a+=[sloping((x0-oh,y,h),(cx,y,h+rise),.09,.12,'HK_Trim'),sloping((cx,y,h+rise),(x1+oh,y,h),.09,.12,'HK_Trim')]
  for xx in [x0-oh,x1+oh]:
   a += [box((xx,d/2,h-.065),(.11,d+2*oh,.15),'HK_Trim')]
   # Open three-sided gutter profile with actual wall thickness.
   a += [box((xx,d/2,h-.16),(.17,d+2*oh,.022),'HK_Zinc'),box((xx-.078,d/2,h-.11),(.018,d+2*oh,.10),'HK_Zinc'),box((xx+.078,d/2,h-.11),(.018,d+2*oh,.10),'HK_Zinc')]
  # Attic vent and a correctly embedded chimney rather than floating roof furniture.
  a += [box((cx,-.126,h+rise*.44),(.44,.08,.33),'HK_Recess')]
  for z in [-.12,-.06,0,.06,.12]:a += [box((cx,-.178,h+rise*.44+z),(.46,.035,.020),'HK_Trim')]
  chimney_x=cx-(x1-x0)*.24;surface=h+rise*(1-.48)
  a += K['chimney'](chimney_x,d*.70,surface-.20,surface+1.03,.58,.62)
  a += [box((chimney_x,d*.70,surface),(.76,.80,.075),'HK_Zinc')]
 else:
  # Coping and discreet ventilation to make the flat roof buildable.
  split=w*.15
  for x in [-w/2,split]:a += [box((x,d/2,6.35),(.19,d+.12,.045),'HK_Zinc')]
  for y in [0,d]:a += [box(((-w/2+split)/2,y,6.35),(split+w/2+.12,.19,.045),'HK_Zinc')]
  a += [box((-w*.30,d*.72,6.18),(.22,.24,.30),'HK_Zinc')]
 # A repaired lower wall patch and narrow plinth cap make age restrained, not noisy.
 a += [box((0,-.135,.29),(1.55,.065,.025),'HK_Foundation')]
 added=K['build']('FinishDetails_%02d'%i,a,coll='ASSEMBLED_HOMES');added.parent=home
 bpy.ops.object.select_all(action='DESELECT');added.select_set(True);obj.select_set(True);bpy.context.view_layer.objects.active=obj
 bpy.ops.object.join();obj.data.calc_loop_triangles();counts[str(i)]=len(obj.data.loop_triangles)
scene=bpy.context.scene;cam=bpy.data.objects['Housing delivery camera']
cam.location=(22,-16,10);cam.rotation_euler=(Vector((14,2.6,2.7))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=17;scene.camera=cam
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1050;scene.render.resolution_y=850;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
target=artifacts.file(name='cottage_material_closeup.png',media_type='image/png');scene.render.filepath=target.path;bpy.ops.render.render(write_still=True);target.publish()
result={'house_triangles':counts,'fixes':['roof edge thickness','ridge caps','supported rain gutters','embedded chimney bases','attic ventilation','flat roof coping']}

