
import bpy
from mathutils import Vector
fixed={}
for i in range(8,12):
 home=bpy.data.objects['Example_Home_%02d'%i];ob=next(o for o in home.children if o.type=='MESH')
 w=[8,9,10,8.6][i%4];d=[6.4,8,7.2][i%3];h=.24+(1 if i%4==0 else 2)*2.8
 to_home=home.matrix_world.inverted()@ob.matrix_world;inv=to_home.inverted();count=0
 for v in ob.data.vertices:
  p=to_home@v.co
  if abs(p.x+w*.28)<.65 and abs(p.y-d*.7)<.65 and p.z>h+.50:
   p.z-=.52;v.co=inv@p;count+=1
 ob.data.update();fixed[str(i)]=count
scene=bpy.context.scene
cam=bpy.data.objects['Housing delivery camera'];cam.location=(13,-17,10);cam.rotation_euler=(Vector((0,2.5,2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=17;scene.camera=cam
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=900;scene.render.resolution_y=700;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
target=artifacts.file(name='housing_close_daylight.png',media_type='image/png');scene.render.filepath=target.path;bpy.ops.render.render(write_still=True);target.publish()
result={'grounded_flat_roof_chimney_vertices':fixed,'source':'Higgsfield 3D Jutsu'}

