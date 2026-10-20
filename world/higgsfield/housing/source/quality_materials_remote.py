
import bpy, numpy as np, math
N=2048
y,x=np.mgrid[0:N,0:N].astype(np.float32);u=x/N;v=y/N
random=np.random.default_rng(391)
def noise(grid):
 a=random.random((grid,grid)).astype(np.float32)
 xx=u*grid;yy=v*grid;ix=xx.astype(int);iy=yy.astype(int);fx=xx-ix;fy=yy-iy
 fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
 return (a[iy%grid,ix%grid]*(1-fx)+a[iy%grid,(ix+1)%grid]*fx)*(1-fy)+(a[(iy+1)%grid,ix%grid]*(1-fx)+a[(iy+1)%grid,(ix+1)%grid]*fx)*fy
macro=noise(7);medium=noise(67);micro=random.random((N,N)).astype(np.float32)
def image(name,rgb,linear=False):
 step=4 if name.endswith('_Roughness') else (2 if name.endswith('_Normal') or any(s in name for s in ['HK_Trim','HK_Zinc','HK_Concrete','HK_Foundation','HK_Cedar','HK_SlateRoof']) else 1)
 if step>1:rgb=rgb.reshape(N//step,step,N//step,step,3).mean(axis=(1,3))
 size=rgb.shape[0]
 im=bpy.data.images.new(name,width=size,height=size,alpha=True);im.colorspace_settings.name='Non-Color' if linear else 'sRGB'
 arr=np.ones((size,size,4),np.float32);arr[:,:,:3]=np.clip(rgb,0,1);im.pixels.foreach_set(arr.ravel());im.pack();return im
specs=[('HK_Brick','brick',(.49,.285,.19)),('HK_StuccoTint','stucco',(.76,.74,.67)),('HK_SidingTint','painted',(.75,.78,.74)),('HK_Cedar','cedar',(.44,.31,.20)),('HK_SlateRoof','slate',(.23,.25,.26)),('HK_Foundation','stone',(.43,.43,.39)),('HK_Trim','trim',(.71,.71,.64)),('HK_Zinc','metal',(.19,.22,.23)),('HK_Concrete','stone',(.49,.49,.46))]
for name,kind,c in specs:
 m=bpy.data.materials.get(name)
 if m is None:continue
 if kind in ['brick','stone']:
  rows=26 if kind=='brick' else 9;cols=8 if kind=='brick' else 5
  row=np.floor(v*rows);xx=u*cols+(row%2)*.5;col=np.floor(xx)
  fy=(v*rows)%1;fx=xx%1
  edge=np.minimum(np.minimum(fx,1-fx)*2/cols,np.minimum(fy,1-fy)*2/rows)
  irregular=(medium-.5)*.0024
  brickmask=np.clip((edge-.0045+irregular)/.003,0,1)
  variation=.94+.13*np.sin(col*19.3+row*27.1)+.06*(macro-.5)+.11*(medium-.5)
  rgb=np.stack([brickmask*(val*variation+.025*(micro-.5))+(1-brickmask)*(.43+.028*(medium-.5)) for val in c],axis=-1)
  height=brickmask*.0025+(medium-.5)*.0008+(micro-.5)*.00016
  rough=.80+.13*(medium-.5)-brickmask*.06
 elif kind in ['painted','cedar','trim']:
  rows=14;fy=(v*rows)%1;seam=np.clip((np.minimum(fy,1-fy)-.013)/.018,0,1)
  grain=np.sin(u*690+medium*9+np.sin(v*32)*3)*.5+.5
  knots=np.sin(u*43+np.sin(v*29)*2)*np.sin(v*57)
  variation=.98+(grain-.5)*(.025 if kind!='cedar' else .10)+(medium-.5)*.07+(macro-.5)*.055
  rgb=np.stack([val*variation*(.65+.35*seam) for val in c],axis=-1)
  height=seam*.00065+fy*.00035+(grain-.5)*.00008
  rough=.65+(medium-.5)*.17
 elif kind=='slate':
  row=np.floor(v*10);fy=(v*10)%1;xx=u*7+(row%2)*.5;fx=xx%1;col=np.floor(xx)
  mask=np.clip((np.minimum(fx,1-fx)-.012)/.013,0,1)*np.clip((np.minimum(fy,1-fy)-.016)/.02,0,1)
  variation=.94+.10*np.sin(col*8.7+row*14.4)+(medium-.5)*.16+(macro-.5)*.06
  rgb=np.stack([val*variation*(.62+.38*mask) for val in c],axis=-1)
  height=mask*.0015+(medium-.5)*.00045
  rough=.78+(medium-.5)*.12
 elif kind=='metal':
  rgb=np.stack([val*(.97+(macro-.5)*.1+(medium-.5)*.05) for val in c],axis=-1)
  height=(micro-.5)*.000018;rough=.58+(macro-.5)*.13
 else:
  rgb=np.stack([val*(.99+(macro-.5)*.045+(medium-.5)*.027)+(micro-.5)*.015 for val in c],axis=-1)
  height=(medium-.5)*.00024+(micro-.5)*.00012;rough=.88+(medium-.5)*.08
 dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))/(4/N)
 dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))/(4/N)
 normals=np.stack([-dx,-dy,np.ones_like(dx)],axis=-1);normals/=np.linalg.norm(normals,axis=-1,keepdims=True)
 nt=m.node_tree;p=nt.nodes.get('Principled BSDF')
 for node in list(nt.nodes):
  if node!=p and node.type!='OUTPUT_MATERIAL':nt.nodes.remove(node)
 tx=nt.nodes.new('ShaderNodeTexImage');tx.image=image(name+'_Q2_Albedo',rgb);nt.links.new(tx.outputs['Color'],p.inputs['Base Color'])
 tx=nt.nodes.new('ShaderNodeTexImage');tx.image=image(name+'_Q2_Normal',normals*.5+.5,True)
 nn=nt.nodes.new('ShaderNodeNormalMap');nn.inputs['Strength'].default_value=.65;nt.links.new(tx.outputs['Color'],nn.inputs['Color']);nt.links.new(nn.outputs['Normal'],p.inputs['Normal'])
 tx=nt.nodes.new('ShaderNodeTexImage');tx.image=image(name+'_Q2_Roughness',np.stack([rough]*3,axis=-1),True);nt.links.new(tx.outputs['Color'],p.inputs['Roughness'])
 p.inputs['Metallic'].default_value=.65 if kind=='metal' else 0
 p.inputs['Coat Weight'].default_value=.08 if kind=='painted' else 0
 m.diffuse_color=(*c,1)
result={'updated_materials':[a[0] for a in specs],'texture_resolution':2048,'maps':['albedo','normal','roughness'],'brick_size_m':[.25,.077],'lap_siding_course_m':.143}
