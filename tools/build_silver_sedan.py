"""Authored and executed in the user's live Blender via MCP. Metres, front -Y."""
import bpy, bmesh, math, json, os
from mathutils import Vector
from math import sin, cos, pi, sqrt
OUT='C:/GodotProjects/delivery-simulator-2026/assets/vehicles/silver_sedan'
os.makedirs(OUT,exist_ok=True)
scene=bpy.data.scenes.new('Silver Sedan • Studio')
bpy.context.window.scene=scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
asset=bpy.data.collections.new('SEDAN_SOURCE');scene.collection.children.link(asset)
studio=bpy.data.collections.new('STUDIO');scene.collection.children.link(studio)
root=bpy.data.objects.new('SilverSedan',None);asset.objects.link(root)
root['forward']='-Y';root['units']='metres';root['reference']='Silver Sedan Blueprint Showcase.png'
root['panel_clearance_m']=.002
M={}
def mat(name,color,metal,rough):
 m=bpy.data.materials.new('Sedan_'+name);m.use_nodes=True
 p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 m.diffuse_color=(*color,1);M[name]=m;return m
mat('Silver',(.63,.67,.70),.72,.26);mat('Glass',(.022,.043,.055),.28,.12)
mat('Rubber',(.013,.017,.019),0,.76);mat('Trim',(.025,.03,.033),.2,.4)
mat('Chrome',(.55,.60,.65),.92,.21);mat('Alloy',(.25,.29,.32),.85,.3)
mat('Headlamp',(.72,.83,.92),.45,.15);mat('Tail',(.42,.012,.018),.25,.24)
mat('Amber',(.95,.26,.025),.15,.28);mat('Brake',(.18,.2,.22),.7,.53)
mat('Interior',(.035,.041,.045),0,.9)

def mesh(name,v,f,material,sub=1,mirror=False):
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update()
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 ob=bpy.data.objects.new(name,me);asset.objects.link(ob);ob.parent=root;me.materials.append(M[material])
 for p in me.polygons:p.use_smooth=True
 if mirror:
  m=ob.modifiers.new('Bilateral design symmetry','MIRROR');m.use_clip=True;m.use_mirror_merge=True;m.merge_threshold=.0001
 if sub:
  b=ob.modifiers.new('Manufactured edge radius 2mm','BEVEL');b.width=.002;b.segments=2
  s=ob.modifiers.new('Curvature support cage','SUBSURF');s.levels=sub;s.render_levels=sub
 ob['smoothing_angle_degrees']=30;ob['minimum_panel_spacing_m']=.002
 return ob

T=[0,.025,.10,.25,.5,.75,.90,.975,1]
def patch(name,fn,material,thick=.012,axis=(0,0,-1),us=T,vs=T,sub=1,mirror=False):
 v=[];nu=len(us);nv=len(vs);off=Vector(axis)*thick
 for layer in [0,1]:
  for a in us:
   for b in vs:v.append(tuple(Vector(fn(a,b))+off*layer))
 n=nu*nv;f=[]
 for i in range(nu-1):
  for j in range(nv-1):
   k=i*nv+j;f.append((k,k+nv,k+nv+1,k+1));f.append((n+k+1,n+k+nv+1,n+k+nv,n+k))
 border=[i*nv for i in range(nu)]+[(nu-1)*nv+j for j in range(1,nv)]+[i*nv+nv-1 for i in range(nu-2,-1,-1)]+[j for j in range(nv-2,0,-1)]
 for a,b in zip(border,border[1:]+border[:1]):
  if mirror and abs(v[a][0])<1e-8 and abs(v[b][0])<1e-8:continue
  f.append((a,b,b+n,a+n))
 return mesh(name,v,f,material,sub,mirror)

def quad(name,points,material,thick=.008,axis=(0,0,-1),sub=1):
 p=list(map(Vector,points))
 return patch(name,lambda u,v:tuple(p[0]*(1-u)*(1-v)+p[1]*u*(1-v)+p[2]*u*v+p[3]*(1-u)*v),material,thick,axis,sub=sub)

def curve(name,pts,r,material,closed=False):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=8;cu.bevel_depth=r;cu.bevel_resolution=2
 sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
 for p,co in zip(sp.bezier_points,pts):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 sp.use_cyclic_u=closed
 ob=bpy.data.objects.new(name,cu);asset.objects.link(ob);ob.parent=root;cu.materials.append(M[material]);return ob

def width(y):return .895-.105*(abs(y)/2.30)**5
def belt(y):return 1.005-.09*(abs(y)/2.30)**3
ys=sorted(set([-2.30,-2.285,-2.24,2.24,2.285,2.30]+[round(-2.2+i*4.4/64,5) for i in range(65)]+[c+d for c in [-1.37,1.32] for d in [-.405,-.399,-.38,-.33,-.26,-.15,0,.15,.26,.33,.38,.399,.405]]))
def bottom(y):
 z=.255
 for c in [-1.37,1.32]:
  d=abs(y-c)
  if d<.405:z=max(z,.325+sqrt(max(0,.405**2-d*d)))
 return z
for side in [-1,1]:
 patch('Body shoulder and wheel arches '+str(side),lambda u,v:(side*(width(u)-.035*sin(pi*v)-.02*(1-v)),u,bottom(u)+(belt(u)-bottom(u))*v),'Silver',.022,(-side,0,0),us=ys,vs=[0,.018,.06,.20,.45,.75,.92,.98,1])
 for c in [-1.37,1.32]:
  pts=[(side*(width(c+.405*cos(a))+.002),c+.405*cos(a),.325+.405*sin(a)) for a in [i*pi/20 for i in range(21)]]
  curve('Pressed fender lip',pts,.012,'Silver')
  # Wheel liner: annular quad strip sits 2cm behind painted fender.
  v=[];f=[]
  for rad in [.408,.43]:
   for i in range(33):
    a=i*pi/32;v.append((side*.85,c+rad*cos(a),.325+rad*sin(a)))
  for i in range(32):f.append((i,i+1,34+i,33+i))
  # Closed shell from a parametric arch rather than a primitive cutter result.
  patch('Wheelhouse liner',lambda u,v:(side*(.83-.19*v),c+.412*cos(u),.325+.412*sin(u)),'Rubber',.01,(-side,0,0),us=[i*pi/32 for i in range(33)],vs=[0,.05,.95,1],sub=0)
 # Rocker sill curves terminate outside wheel clearances.
 curve('Rocker bright edge',[(side*.873,-.955,.265),(side*.88,-.6,.25),(side*.88,.65,.25),(side*.873,.90,.265)],.013,'Chrome')

# Hood and trunk lofts use centre-line Mirror and deliberate shoulder curvature.
patch('Bonnet',lambda u,v:(u*(width(-2.285+1.19*v)-.022),-2.285+1.19*v,1.0+.045*v-.10*u*u-.09*(1-v)**3),'Silver',.018,mirror=True)
patch('Boot lid',lambda u,v:(u*(width(1.43+.845*v)-.024),1.43+.845*v,1.035-.095*v+.018*sin(pi*v)-.035*u*u),'Silver',.018,mirror=True)
patch('Roof crown',lambda u,v:(u*(.67+.035*sin(pi*v)),-.48+1.20*v,1.455+.045*sin(pi*v)-.055*u*u),'Silver',.018,mirror=True)
patch('Windscreen',lambda u,v:((2*u-1)*(.80-.14*v),-1.078+.585*v,1.025+.424*v+.022*sin(pi*u)),'Glass',.008,sub=1)
patch('Rear heated glass',lambda u,v:((2*u-1)*(.68+.095*v),.739+.667*v,1.446-.393*v+.014*sin(pi*u)),'Glass',.008,sub=1)
for side in [-1,1]:
 # Individual apertures leave substantial A/B/C pillars, like the supplied sedan.
 front=[(side*.817,-1.028,1.018),(side*.856,.055,1.028),(side*.685,.055,1.43),(side*.681,-.45,1.426)]
 rear=[(side*.858,.125,1.028),(side*.810,1.365,1.029),(side*.706,.735,1.419),(side*.687,.125,1.43)]
 for label,p in [('Front',front),('Rear',rear)]:
  quad(label+' door glass '+str(side),p,'Glass',.008,(-side,0,0))
  curve(label+' aperture rubber '+str(side),p,.019,'Trim',True)
  curve(label+' bright window surround '+str(side),[(x+side*.007,y,z+.004) for x,y,z in p],.008,'Chrome',True)
 quad('A pillar '+str(side),[(side*.836,-1.075,1.013),(side*.79,-.99,1.018),(side*.642,-.47,1.445),(side*.70,-.50,1.46)],'Silver',.018,(-side,0,0))
 quad('B pillar '+str(side),[(side*.865,.065,1.02),(side*.865,.115,1.02),(side*.688,.115,1.438),(side*.688,.065,1.438)],'Trim',.02,(-side,0,0))
 quad('C pillar '+str(side),[(side*.82,1.395,1.027),(side*.866,1.59,1.025),(side*.718,.78,1.449),(side*.68,.732,1.448)],'Silver',.022,(-side,0,0))
 for y0,y1 in [(-1.035,.085),(.105,1.15)]:
  curve('Door shutline '+str(side),[(side*(width(y0)+.003),y0,.99),(side*(width(y0)+.003),y0,.77),(side*.861,y0+.055,.33),(side*.865,y1-.04,.33),(side*(width(y1)+.003),y1,.70),(side*(width(y1)+.003),y1,.99)],.003,'Trim')
 for y in [-.12,.96]:
  patch('Flush door handle',lambda u,v,s=side,y=y:(s*(width(y)+.017+.016*sin(pi*u)*sin(pi*v)),y-.09+.18*u,.876+.027*(2*v-1)),'Chrome',.012,(-side,0,0),sub=1)
 # Aerodynamic mirror cap with a true curved shell, stalk and rear mirror lens.
 patch('Mirror housing',lambda u,v,s=side:(s*(.85+.22*u),-.91+.12*cos(pi*v)*sin(pi*u),1.09+.065*sin(pi*u)*sin(pi*v)),'Silver',.035,(0,0,-1))
 quad('Mirror glass',[(side*.87,-.825,1.05),(side*1.055,-.825,1.065),(side*1.055,-.825,1.115),(side*.87,-.825,1.105)],'Chrome',.009,(0,-1,0))
 curve('Mirror stalk',[(side*.81,-.9,1.02),(side*.87,-.9,1.055),(side*.915,-.9,1.07)],.019,'Trim')

# Front and rear fascias: controlled curved patches; grille recess remains separate.
for end in [-1,1]:
 patch(('Front' if end<0 else 'Rear')+' fascia',lambda u,v,e=end:((2*u-1)*(.79+.025*sin(pi*v)),e*(2.285+.035*sin(pi*u)),.30+.57*v+.025*sin(pi*u)),'Silver',.025,(0,-end,0))
 curve('Lower bumper splitter',[(x,end*(2.315-.03*abs(x)),.30) for x in [-.76,-.5,0,.5,.76]],.023,'Trim')
for side in [-1,1]:
 p=[(side*.405,-2.331,.83),(side*.77,-2.293,.88),(side*.785,-2.289,1.00),(side*.535,-2.329,.954)]
 quad('Swept headlamp housing',p,'Trim',.025,(0,1,0))
 p2=[(x,y-.008,z+.005) for x,y,z in p]
 quad('Headlamp optical lens',p2,'Headlamp',.009,(0,1,0))
 curve('LED daytime running signature',[(side*.43,-2.346,.848),(side*.58,-2.337,.855),(side*.74,-2.309,.905)],.009,'Headlamp')
 quad('Rear lamp housing',[(side*.40,2.326,.81),(side*.77,2.298,.79),(side*.79,2.292,.96),(side*.46,2.326,.93)],'Tail',.014,(0,-1,0))
 curve('Rear LED signature',[(side*.44,2.341,.87),(side*.59,2.331,.86),(side*.75,2.313,.87)],.01,'Tail')
 quad('Fog lamp recess',[(side*.62,-2.331,.39),(side*.765,-2.319,.42),(side*.745,-2.322,.59),(side*.60,-2.333,.56)],'Trim',.012,(0,1,0))
 curve('Fog optic',[(side*(.685+.036*cos(a)),-2.347,.481+.036*sin(a)) for a in [i*2*pi/16 for i in range(16)]],.009,'Headlamp',True)
for label,z0,z1,w0,w1 in [('Upper grille',.695,.848,.39,.49),('Lower intake',.337,.552,.58,.49)]:
 quad(label, [(-w0,-2.337,z0),(w0,-2.337,z0),(w1,-2.337,z1),(-w1,-2.337,z1)],'Trim',.013,(0,1,0))
 curve(label+' polished surround',[(-w0,-2.349,z0),(w0,-2.349,z0),(w1,-2.349,z1),(-w1,-2.349,z1)],.009,'Chrome',True)
 for z in [z0+.04,z0+.08,z0+.12]:
  if z<z1-.014:curve('Grille blade',[(-w0+.035,-2.351,z),(0,-2.355,z),(w0-.035,-2.351,z)],.006,'Alloy')
quad('Rear registration recess',[(-.23,2.33,.56),(.23,2.33,.56),(.23,2.33,.67),(-.23,2.33,.67)],'Trim',.014,(0,-1,0))
curve('Boot shutline',[(-.45,2.327,.93),(-.43,2.33,.76),(0,2.336,.73),(.43,2.33,.76),(.45,2.327,.93)],.003,'Trim')

def torus(name,c,major,minor,material,axis='X',n=48,m=12,flatten=1):
 v=[];f=[]
 for i in range(n):
  a=2*pi*i/n
  for j in range(m):
   b=2*pi*j/m;r=major+minor*cos(b);p=(minor*sin(b)*flatten,r*cos(a),r*sin(a))
   if axis=='Y':p=(p[1],p[0],p[2])
   v.append(tuple(Vector(c)+Vector(p)))
 for i in range(n):
  for j in range(m):f.append((i*m+j,((i+1)%n)*m+j,((i+1)%n)*m+(j+1)%m,i*m+(j+1)%m))
 return mesh(name,v,f,material,0)
for side in [-1,1]:
 for cy,label in [(-1.37,'Front'),(1.32,'Rear')]:
  cx=side*.825;cz=.325
  tire=torus(label+' tire '+str(side),(cx,cy,cz),.252,.073,'Rubber',flatten=1.52)
  tire['wheel_center']=[cx,cy,cz];tire['steerable']=label=='Front'
  for offset in [-.055,.055]:torus('Sidewall protective bead',(cx+offset,cy,cz),.257,.016,'Rubber',n=48,m=8)
  torus('Machined wheel lip',(cx+side*.106,cy,cz),.215,.013,'Chrome',n=48,m=8)
  torus('Rim barrel',(cx,cy,cz),.209,.022,'Alloy',n=40,m=8,flatten=3)
  torus('Brake rotor',(cx+side*.065,cy,cz),.143,.018,'Brake',n=40,m=8)
  torus('Hub centre',(cx+side*.11,cy,cz),.043,.019,'Alloy',n=24,m=8)
  for k in range(10):
   a=k*2*pi/10
   p=[]
   for r,ang in [(.06,a-.11),(.207,a+.045),(.207,a+.13),(.06,a+.12)]:p.append((cx+side*(.103+.014*r/.207),cy+r*cos(ang),cz+r*sin(ang)))
   quad('Swept alloy spoke',p,'Chrome',.017,(-side,0,0),sub=0)
  for k in range(5):
   a=k*2*pi/5;torus('Lug seat',(cx+side*.132,cy+.052*cos(a),cz+.052*sin(a)),.007,.003,'Chrome',n=8,m=4)
# Wipers and exhaust use curve profiles, with no primitive cylinders.
for side in [-1,1]:curve('Wiper',[(side*.10,-1.083,1.051),(side*.40,-.97,1.137),(side*.67,-.88,1.20)],.007,'Trim')
torus('Exhaust rolled tip',(-.50,2.32,.295),.045,.007,'Chrome',axis='Y',n=24,m=8)
curve('Roof antenna',[(0,.65,1.51),(0,.68,1.58),(0,.72,1.61)],.012,'Trim')
print('Created',len(asset.objects),'objects; custom quad cages and curve trims')
