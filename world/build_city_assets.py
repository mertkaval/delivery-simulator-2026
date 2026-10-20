"""Deterministic Blender asset workshop. Godot-space metres: X right, Y up, -Z forward.
Run: blender --background --python world/build_city_assets.py [-- category]
Custom lofts, swept tubes, shaped panels and leaf meshes; GLB runtime / .blend sources.
"""
import bpy, bmesh, math, os, random, json, sys
from mathutils import Vector
from collections import defaultdict
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'city_assets')
os.makedirs(os.path.join(OUT,'source'),exist_ok=True)
open(os.path.join(OUT,'source','.gdignore'),'w').close()
R=random.Random(6321)
REPORT={}

def P(p): return Vector((p[0],-p[2],p[1]))
def clear():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(name,color,rough=.7,metal=0,alpha=1):
    m=bpy.data.materials.get(name)
    if m: return m
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,alpha); m.use_nodes=True
    s=m.node_tree.nodes.get('Principled BSDF')
    s.inputs['Base Color'].default_value=(*color,alpha)
    s.inputs['Roughness'].default_value=rough; s.inputs['Metallic'].default_value=metal
    s.inputs['Alpha'].default_value=alpha
    if alpha<1: m.surface_render_method='DITHERED'
    return m

PAINT=mat('VehiclePaint',(.22,.34,.43),.23,.65)
BLACK=mat('Rubber',(.018,.023,.026),.88)
STEEL=mat('BrushedSteel',(.32,.37,.4),.30,.82)
CHROME=mat('PolishedAlloy',(.65,.69,.71),.19,.9)
GLASS=mat('AutomotiveGlass',(.025,.07,.10),.10,.35)
LAMP=mat('HeadlampLens',(.85,.89,.76),.20,.1)
RED=mat('TailLampLens',(.45,.018,.014),.24,.1)
WOOD=mat('OiledOak',(.25,.13,.055),.65)
STONE=mat('ArchitecturalConcrete',(.44,.44,.40),.9)
BRICK=mat('WarmBrick',(.37,.20,.13),.9)
IVORY=mat('PaintedIvory',(.72,.70,.62),.64)
LEAF=mat('Foliage',(.10,.23,.037),.87)
BARK=mat('TreeBark',(.16,.105,.06),1)
SKIN=mat('Skin',(.55,.32,.20),.7)
SHIRT=mat('Clothing',(.12,.24,.29),.95)
PANTS=mat('Denim',(.065,.09,.12),.97)
HAIR=mat('Hair',(.045,.025,.016),1)

def mesh(name,verts,faces,material,smooth=False):
    data=bpy.data.meshes.new(name); data.from_pydata([P(v) for v in verts],[],faces); data.update()
    o=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    if smooth:
        for poly in data.polygons: poly.use_smooth=True
    return o

def bevel(o,width=.025,segments=2):
    bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Manufactured edge radius','BEVEL'); mod.width=width; mod.segments=segments
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return o

def panel(name,p,d,material,edge=.018):
    x,y,z=p; a,b,c=[v/2 for v in d]
    o=mesh(name,[(x+sx*a,y+sy*b,z+sz*c) for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)],material)
    if edge: bevel(o,min(edge,min(d)*.35))
    return o

def tube(name,points,radii,material,sides=10):
    verts=[]; faces=[]
    for i,p in enumerate(points):
        direction=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
        direction.normalize(); u=direction.cross(Vector((0,1,0)))
        if u.length<.1: u=direction.cross(Vector((1,0,0)))
        u.normalize(); v=direction.cross(u).normalized()
        radius=radii[i] if isinstance(radii,(list,tuple)) else radii
        for j in range(sides):
            q=Vector(p)+radius*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides))
            verts.append(q)
    for i in range(len(points)-1):
        for j in range(sides):
            a=i*sides+j; b=i*sides+(j+1)%sides; faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(reversed(range(sides)))); faces.append(tuple((len(points)-1)*sides+j for j in range(sides)))
    return mesh(name,verts,faces,material,True)

def torus(name,center,major,minor,material,axis='x',n=40,m=8):
    verts=[]; faces=[]
    for i in range(n):
        a=i*math.tau/n
        for j in range(m):
            b=j*math.tau/m; r=major+minor*math.cos(b)
            q=(minor*math.sin(b),r*math.sin(a),r*math.cos(a)) if axis=='x' else (r*math.cos(a),minor*math.sin(b),r*math.sin(a))
            verts.append(tuple(center[k]+q[k] for k in range(3)))
    for i in range(n):
        for j in range(m): faces.append((i*m+j,((i+1)%n)*m+j,((i+1)%n)*m+(j+1)%m,i*m+(j+1)%m))
    return mesh(name,verts,faces,material,True)

def ellipsoid(name,p,d,material,n=16,m=10):
    verts=[]; faces=[]
    for i in range(m+1):
        a=math.pi*(.001+(i/m)*.998)
        for j in range(n):
            b=j*math.tau/n
            verts.append((p[0]+d[0]*math.sin(a)*math.cos(b),p[1]+d[1]*math.cos(a),p[2]+d[2]*math.sin(a)*math.sin(b)))
    for i in range(m):
        for j in range(n): faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    return mesh(name,verts,faces,material,True)

def loft(name,rings,material,n=20):
    # Elliptical transverse sections: (height, center x, center z, half-width, half-depth).
    verts=[]; faces=[]
    for y,x,z,rx,rz in rings:
        for j in range(n):
            a=j*math.tau/n; verts.append((x+rx*math.cos(a),y,z+rz*math.sin(a)))
    for i in range(len(rings)-1):
        for j in range(n): faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    faces.extend([tuple(reversed(range(n))),tuple((len(rings)-1)*n+j for j in range(n))])
    return mesh(name,verts,faces,material,True)

def pivot(name,p,objects):
    bpy.context.view_layer.update()
    transforms={o:o.matrix_world.copy() for o in objects}
    empty=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(empty); empty.location=P(p)
    bpy.context.view_layer.update()
    for o in objects:
        o.parent=empty; o.matrix_world=transforms[o]
    bpy.context.view_layer.update()
    return empty

def export(name):
    # Apply edge modifiers, then consolidate surfaces without destroying articulation.
    groups=defaultdict(list)
    for o in list(bpy.context.scene.objects):
        if o.type=='MESH':
            bm=bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(o.data); bm.free()
            groups[(o.parent, o.data.materials[0].name)].append(o)
    for (parent,material),objects in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects: o.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        if len(objects)>1: bpy.ops.object.join()
        o=bpy.context.object; o.name=material if parent is None else parent.name+'_'+material
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in bpy.context.scene.objects if o.type=='MESH')
    REPORT[name]={'triangles':triangles,'meshes':sum(o.type=='MESH' for o in bpy.context.scene.objects)}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'source',name+'.blend'))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+'.glb'),export_format='GLB',export_apply=True)
    print('ASSET COMPLETE',name,REPORT[name],flush=True)

def vehicle(kind):
    clear()
    configs=[(1.78,4.35,1.46,1.36),(1.72,3.72,1.51,1.15),(1.96,4.72,1.83,1.48),(1.92,5.10,2.22,1.60),(1.98,5.35,1.89,1.65)]
    width,length,height,axle=configs[kind]; half=width/2; end=length/2
    wheel_r=.33 if kind<2 else .38
    # A longitudinal sculpted shell, with side lower edge cut around both wheel arches.
    verts=[]; faces=[]; sections=64
    for i in range(sections+1):
        z=-end+length*i/sections
        taper=1-.09*(abs(z)/end)**5
        hood=.96 if kind<2 else 1.18
        top=hood-.16*(abs(z)/end)**4
        arch=max([wheel_r+.12-math.sqrt(max(0,(wheel_r+.12)**2-(z-a)**2)) if False else (wheel_r+math.sqrt(max(0,(wheel_r+.10)**2-(z-a)**2)) if abs(z-a)<wheel_r+.10 else .30) for a in [-axle,axle]])
        low=max(.30,arch)
        ring=[(-half*.85,low,z),(-half*taper,low+.03,z),(-half*taper,top-.12,z),(-half*.84*taper,top,z),(0,top+.025,z),(half*.84*taper,top,z),(half*taper,top-.12,z),(half*taper,low+.03,z),(half*.85,low,z)]
        verts.extend(ring)
    for i in range(sections):
        for j in range(9): faces.append((i*9+j,(i+1)*9+j,(i+1)*9+(j+1)%9,i*9+(j+1)%9))
    faces.extend([tuple(reversed(range(9))),tuple(sections*9+j for j in range(9))])
    mesh('Sculpted body with open wheel arches',verts,faces,PAINT,True)
    # Tapered glasshouse profile: bonnet -> raked windshield -> roof -> rear screen.
    rear=1.45 if kind in [1,2,3] else .92
    roof_front=-.55 if kind<3 else -.95
    roof_rear=.72 if kind<3 else (1.8 if kind==3 else .35)
    belt=.98 if kind<2 else 1.22
    cabin=[(-1.05,belt,half*.86),(roof_front,height-.08,half*.70),(roof_rear,height,half*.70),(rear,belt,half*.85)]
    verts=[]
    for z,y,w in cabin: verts.extend([(-w,y,z),(w,y,z)])
    mesh('Raked windshield and rear glazing',verts,[(0,1,3,2),(4,5,7,6)],GLASS)
    mesh('Contoured roof',verts,[(2,3,5,4)],PAINT)
    for side in [-1,1]:
        v=[(side*w,y,z) for z,y,w in cabin]+[(side*half*.86,belt,rear),(side*half*.86,belt,-1.05)]
        mesh('Side glazing',v,[tuple(range(6))],GLASS)
        for a,b in [(0,1),(1,2),(2,3),(0,3)]:
            tube('Window surround',[(side*cabin[a][2],cabin[a][1],cabin[a][0]),(side*cabin[b][2],cabin[b][1],cabin[b][0])],.026,BLACK)
        tube('B pillar',[(side*half*.86,belt,.05),(side*half*.70,height-.04,.05)],.045,PAINT)
        for z in [-.45,.67]:
            panel('Recessed handle',(side*(half+.01),belt-.10,z),(.035,.045,.18),CHROME,.012)
            tube('Door seam',[(side*(half+.012),.40,z+.33),(side*(half+.012),belt-.02,z+.33)],.006,BLACK,6)
        ellipsoid('Aerodynamic mirror',(side*(half+.10),belt+.06,-.80),(.17,.08,.11),PAINT)
        tube('Mirror stalk',[(side*half*.82,belt,-.80),(side*(half+.08),belt+.03,-.80)],.028,BLACK)
        for z in [-axle,axle]:
            parts=set(bpy.context.scene.objects)
            torus('Treaded tire',(side*(half-.035),wheel_r,z),wheel_r-.085,.09,BLACK)
            torus('Alloy rim lip',(side*(half+.06),wheel_r,z),wheel_r-.13,.023,CHROME)
            tube('Wheel hub',[(side*(half-.04),wheel_r,z),(side*(half+.07),wheel_r,z)],.085,STEEL,16)
            for k in range(10):
                a=k*math.tau/10
                tube('Alloy spoke',[(side*(half+.068),wheel_r+.07*math.sin(a),z+.07*math.cos(a)),(side*(half+.07),wheel_r+(wheel_r-.14)*math.sin(a+.16),z+(wheel_r-.14)*math.cos(a+.16))],.025,CHROME,6)
            for k in range(32):
                a=k*math.tau/32
                tube('Tire tread',[(side*(half-.10),wheel_r+(wheel_r+.006)*math.sin(a),z+(wheel_r+.006)*math.cos(a)),(side*(half+.035),wheel_r+(wheel_r+.008)*math.sin(a+.025),z+(wheel_r+.008)*math.cos(a+.025))],.009,BLACK,5)
            pivot(('WheelFront' if z<0 else 'WheelRear')+('L' if side<0 else 'R'),(side*(half-.035),wheel_r,z),set(bpy.context.scene.objects)-parts)
            points=[(side*(half+.01),wheel_r+(wheel_r+.13)*math.sin(a),z+(wheel_r+.13)*math.cos(a)) for a in [j*math.pi/18 for j in range(19)]]
            tube('Wheel arch molding',points,.025,BLACK)
    for z in [-end-.01,end+.01]:
        panel('Formed bumper',(0,.45,z),(width*.95,.21,.15),PAINT,.055)
        panel('License plate',(0,.63,z*1.018),(.44,.14,.018),IVORY,.014)
        for x in [-half*.64,half*.64]: panel('Lamp cluster',(x,.85 if kind<2 else 1.0,z*1.01),(.41,.14,.055),LAMP if z<0 else RED,.04)
    for j in range(7): panel('Grille fin',(0,.76+j*.026,-end-.035),(.62,.012,.035),STEEL,.004)
    for x in [-.35,.35]: tube('Wiper',[(x,belt+.07,-1.065),(x+.15,belt+.18,-.95)],.012,BLACK,6)
    if kind==3:
        # Cargo van roof and tall side panels differ materially from a sedan.
        panel('Cargo roof',(0,height-.04,1.0),(width*.85,.12,1.65),PAINT,.05)
        for side in [-1,1]: panel('Cargo side panel',(side*half*.89,(height+belt)/2,1.05),(.07,height-belt,1.55),PAINT,.035)
    if kind==4:
        panel('Pickup bed floor',(0,.9,1.45),(width*.85,.12,1.5),BLACK)
        for side in [-1,1]: panel('Pickup bed rail',(side*half*.88,1.20,1.48),(.12,.5,1.7),PAINT,.04)
        panel('Tailgate',(0,1.16,end-.10),(width*.9,.55,.12),PAINT,.04)
    export(['sedan','hatchback','suv','van','pickup'][kind])

def bicycle():
    clear(); paint=mat('BicyclePaint',(.68,.24,.055),.26,.55)
    rear=(0,.35,.61); front=(0,.35,-.64); crank=(0,.32,.10); saddle=(0,.88,.27); head=(0,.85,-.43)
    for a,b,r in [(rear,saddle,.022),(rear,crank,.022),(saddle,crank,.029),(saddle,head,.028),(head,crank,.035)]:
        tube('Butted frame tubing',[a,b],r,paint,12)
    for side in [-1,1]:
        tube('Curved fork',[(side*.07,.35,-.64),(side*.08,.53,-.61),(side*.055,.87,-.44)],.020,STEEL)
        tube('Rear stay',[(side*.06,.35,.61),(side*.065,.59,.46),(side*.03,.83,.27)],.016,paint)
    tube('Seat post',[(0,.73,.29),(0,.98,.30)],.021,STEEL)
    # A shaped saddle loft and curved bars, not rectangular substitutes.
    loft('Leather saddle',[(.97,0,.29,.09,.17),(1.01,0,.30,.095,.18),(1.025,0,.30,.085,.16)],BLACK,24)
    tube('Stem',[(0,.82,-.43),(0,1.01,-.48),(0,1.03,-.58)],.024,STEEL)
    tube('Swept handlebar',[(-.34,1.0,-.51),(-.24,1.035,-.57),(0,1.04,-.60),(.24,1.035,-.57),(.34,1.0,-.51)],.019,STEEL,12)
    for side in [-1,1]:
        tube('Textured grip',[(side*.24,1.03,-.565),(side*.35,1.0,-.51)],.025,BLACK)
        tube('Brake lever',[(side*.23,1.01,-.60),(side*.30,.99,-.65)],.011,CHROME)
        tube('Brake cable',[(side*.19,1.01,-.61),(side*.10,.83,-.70),(0,.67,-.60)],.004,BLACK,6)
        tube('Pedal crank',[(side*.06,.32,.10),(side*.12,.32+side*.16,.10)],.018,STEEL)
        panel('Platform pedal',(side*.18,.32+side*.16,.10),(.15,.027,.08),BLACK,.01)
    for z in [-.64,.61]:
        before=set(bpy.context.scene.objects)
        torus('Road tire',(0,.35,z),.319,.031,BLACK,n=56)
        torus('Double wall rim',(0,.35,z),.285,.015,STEEL,n=56)
        tube('Axle',[(-.07,.35,z),(.07,.35,z)],.027,STEEL,12)
        for j in range(32):
            a=j*math.tau/32
            tube('Cross laced spoke',[((-.035 if j%2 else .035),.35,z),(0,.35+.28*math.sin(a),z+.28*math.cos(a))],.0025,CHROME,4)
        torus('Disc rotor',(.052,.35,z),.07,.008,STEEL,n=24,m=4)
        pivot('WheelFront' if z<0 else 'WheelRear',(0,.35,z),set(bpy.context.scene.objects)-before)
    torus('Chain ring',(.07,.32,.10),.077,.011,STEEL,n=32,m=6)
    for j in range(18):
        a=j*math.tau/18
        tube('Chain ring tooth',[(.073,.32+.072*math.sin(a),.10+.072*math.cos(a)),(.073,.32+.088*math.sin(a),.10+.088*math.cos(a))],.006,STEEL,4)
    for dy in [-.065,.065]: tube('Bicycle chain',[(.08,.32+dy,.10),(.08,.35+dy*.6,.61)],.007,BLACK,5)
    tube('Rear cargo rack',[(-.12,.72,.33),(-.12,.72,.77),(.12,.72,.77),(.12,.72,.33)],.012,STEEL)
    for z in [.40,.52,.64,.75]: tube('Rack slat',[(-.12,.72,z),(.12,.72,z)],.009,STEEL)
    for side in [-1,1]: tube('Rack strut',[(side*.12,.72,.70),(side*.075,.35,.61)],.011,STEEL)
    tube('Kickstand',[(.06,.3,.15),(.20,.03,.30)],.013,STEEL)
    ellipsoid('Front bicycle lamp',(0,.86,-.68),(.038,.035,.055),LAMP)
    panel('Rear reflector',(0,.72,.79),(.075,.04,.025),RED,.01)
    export('bicycle')

def tree(kind):
    clear(); R.seed(937+kind)
    height=[7.6,9.5,10.5][kind]
    # Tapered, irregular trunk and recursive branch sweeps.
    trunk=[(.10*math.sin(i*1.9),i*height/8,.06*math.cos(i*1.1)) for i in range(9)]
    bark=BARK if kind!=1 else mat('BirchBark',(.62,.60,.51),.96)
    tube('Tapered trunk',trunk,[.23*(1-i/10)**1.5 for i in range(9)],bark,12)
    verts=[]; faces=[]
    def leaf(center,size,angle,tilt):
        # Curved lanceolate leaf: six boundary vertices around a lifted vein.
        u=Vector((math.cos(angle),tilt,math.sin(angle))).normalized()
        v=Vector((-math.sin(angle),.1,math.cos(angle)))
        p=Vector(center); base=len(verts)
        for along,across,rise in [(-1,0,0),(-.35,.42,0),(.4,.35,0),(1,0,0),(.4,-.35,0),(-.35,-.42,0),(0,0,.12)]:
            verts.append(p+u*along*size+v*across*size*(.16 if kind==2 else 1)+Vector((0,rise*size,0)))
        for j in range(6): faces.append((base+j,base+(j+1)%6,base+6))
    for branch in range(30 if kind<2 else 45):
        a=branch*2.399+R.uniform(-.3,.3)
        y=height*(.38+.58*branch/(30 if kind<2 else 45))
        radius=(3.0*math.sin(math.pi*min(.96,max(.1,(y/height-.25)/.8)))) if kind==0 else (2.5 if kind==1 else 3.1)*(1-(y/height-.35))
        if kind==1: radius*=.75
        end=Vector((math.cos(a)*radius,y+(.7 if kind<2 else -.35),math.sin(a)*radius))
        mid=Vector((end.x*.55,y+.35,end.z*.55))
        tube('Primary branch',[(0,y-.4,0),mid,end],[.065,.032,.006],bark,7)
        for twig in range(5):
            t=twig/5; anchor=mid.lerp(end,t)
            tip=anchor+Vector((R.uniform(-.65,.65),R.uniform(-.25,.75),R.uniform(-.65,.65)))
            tube('Branchlet',[anchor,tip],[.014,.003],bark,5)
            for j in range(13 if kind<2 else 17):
                pos=tip+Vector((R.uniform(-.6,.6),R.uniform(-.35,.5),R.uniform(-.6,.6)))
                leaf(pos,R.uniform(.13,.24) if kind<2 else R.uniform(.12,.23),R.random()*math.tau,R.uniform(-.5,.8))
    mesh('Individual leaves',verts,faces,LEAF)
    for angle in range(7):
        a=angle*math.tau/7
        tube('Root flare',[(0,.3,0),(.45*math.cos(a),.06,.45*math.sin(a)),(.65*math.cos(a),.01,.65*math.sin(a))],[.14,.07,.004],bark,7)
    export(['maple','birch','conifer'][kind])

def grass():
    clear(); verts=[]; faces=[]; R.seed(81)
    for i in range(18):
        x,z=R.uniform(-.19,.19),R.uniform(-.19,.19); h=R.uniform(.10,.29); w=R.uniform(.007,.017)
        a=R.random()*math.tau; ux,uz=math.cos(a)*w,math.sin(a)*w; bx,bz=R.uniform(-.09,.09),R.uniform(-.09,.09); k=len(verts)
        verts.extend([(x-ux,0,z-uz),(x+ux,0,z+uz),(x+ux*.55+bx*.4,h*.55,z+uz*.55+bz*.4),(x-ux*.55+bx*.4,h*.55,z-uz*.55+bz*.4),(x+bx,h,z+bz)])
        faces.extend([(k,k+1,k+2,k+3),(k+3,k+2,k+4)])
    mesh('Bent grass blades',verts,faces,LEAF); export('grass_clump')

def person():
    clear()
    # Contoured torso with hip/waist/chest/shoulder sections and separate clothing.
    loft('Tailored jacket',[(.87,0,0,.14,.10),(.97,0,0,.17,.105),(1.12,0,0,.145,.095),(1.34,0,-.01,.19,.115),(1.43,0,0,.21,.10),(1.48,0,0,.14,.085)],SHIRT)
    tube('Neck',[(0,1.43,0),(0,1.57,0)],.062,SKIN,16)
    loft('Head sculpt',[(1.53,0,-.012,.055,.055),(1.56,0,-.012,.075,.07),(1.64,0,0,.092,.088),(1.72,0,.003,.086,.086),(1.78,0,.007,.063,.065),(1.80,0,.01,.02,.026)],SKIN,24)
    ellipsoid('Nose bridge',(0,1.659,-.088),(.018,.033,.029),SKIN)
    for side in [-1,1]:
        ellipsoid('Ear',(side*.092,1.665,.006),(.018,.038,.024),SKIN)
        ellipsoid('Eye',(side*.034,1.69,-.078),(.019,.010,.008),IVORY)
        ellipsoid('Iris',(side*.034,1.69,-.085),(.006,.006,.002),HAIR,n=10,m=6)
        tube('Eyebrow',[(side*.018,1.711,-.083),(side*.045,1.713,-.078)],.005,HAIR,5)
    tube('Mouth',[(-.023,1.602,-.077),(0,1.599,-.082),(.023,1.602,-.077)],.004,mat('Lip',(.33,.13,.095)),6)
    loft('Cropped hair',[(1.70,0,.018,.089,.077),(1.76,0,.012,.084,.082),(1.795,0,.01,.052,.055),(1.813,0,.01,.01,.013)],HAIR,24)
    tube('Jacket zip',[(0,.91,-.105),(0,1.43,-.104)],.005,STEEL,5)
    for side in [-1,1]:
        tube('Collar',[(side*.06,1.49,-.035),(side*.095,1.44,-.08),(side*.025,1.40,-.12)],.013,SHIRT)
        before=set(bpy.context.scene.objects)
        loft('Trouser thigh',[(.94,side*.085,0,.085,.105),(.82,side*.095,0,.087,.095),(.61,side*.095,0,.067,.071),(.49,side*.095,0,.060,.065)],PANTS)
        thigh=set(bpy.context.scene.objects)-before
        before=set(bpy.context.scene.objects)
        loft('Trouser calf',[(.52,side*.095,0,.062,.064),(.36,side*.095,.01,.062,.062),(.14,side*.095,0,.043,.046)],PANTS)
        loft('Leather shoe',[(.025,side*.095,-.045,.067,.137),(.05,side*.095,-.049,.068,.14),(.105,side*.095,-.025,.063,.117),(.16,side*.095,.014,.047,.061)],BLACK)
        for j in range(4): tube('Shoe lace',[(side*.095-.035,.12,-.04-j*.015),(side*.095+.035,.12,-.04-j*.015)],.002,IVORY,4)
        knee=pivot('KneeL' if side<0 else 'KneeR',(side*.095,.51,0),set(bpy.context.scene.objects)-before)
        pivot('HipL' if side<0 else 'HipR',(side*.085,.93,0),list(thigh)+[knee])
        before=set(bpy.context.scene.objects)
        tube('Shaped sleeve',[(side*.185,1.41,0),(side*.25,1.28,.005),(side*.27,1.12,-.01)],[.083,.073,.06],SHIRT,16)
        upper=set(bpy.context.scene.objects)-before; before=set(bpy.context.scene.objects)
        tube('Forearm',[(side*.27,1.14,-.01),(side*.275,.99,-.02),(side*.275,.9,-.035)],[.057,.049,.034],SHIRT,14)
        ellipsoid('Hand',(side*.277,.855,-.035),(.036,.060,.028),SKIN)
        for finger in range(4):
            x=side*.277+(finger-1.5)*.014
            tube('Finger',[(x,.84,-.036),(x,.795,-.04)],[.008,.006],SKIN,6)
        elbow=pivot('ElbowL' if side<0 else 'ElbowR',(side*.27,1.12,-.01),set(bpy.context.scene.objects)-before)
        pivot('ShoulderL' if side<0 else 'ShoulderR',(side*.185,1.41,0),list(upper)+[elbow])
    export('citizen')

def chair(x,z):
    for sx in [-.22,.22]:
        for sz in [-.22,.22]: tube('Chair bent steel leg',[(x+sx,.02,z+sz),(x+sx*.88,.47,z+sz*.88)],.022,BLACK)
    panel('Shaped chair seat',(x,.47,z),(.51,.065,.51),WOOD,.04)
    for sx in [-.23,.23]: tube('Chair back support',[(x+sx,.45,z+.22),(x+sx,.95,z+.23)],.019,BLACK)
    panel('Chair curved back',(x,.84,z+.23),(.49,.22,.055),WOOD,.035)

def restaurant(kind):
    clear(); wall=mat('RestaurantPlaster',(.50,.47,.39),.93); accent=mat('RestaurantAccent',[(.11,.25,.20),(.38,.14,.09),(.13,.23,.34)][kind],.64)
    window=mat('ShopWindow',(.49,.62,.64),.10,.05,.20)
    panel('Terrazzo floor',(-4,.025,-2.6),(12,.05,10.6),STONE)
    for x in [-10,2]: panel('Side masonry',(x,2.15,-2.6),(.22,4.3,10.6),BRICK)
    panel('Rear wall',(-4,2.15,-7.9),(12,4.3,.22),BRICK)
    panel('Ceiling',(-4,4.28,-2.6),(12.3,.17,10.9),IVORY)
    panel('Roof coping',(-4,4.45,-2.6),(12.6,.18,11.2),BLACK)
    panel('Fascia sign band',(-4,3.65,2.86),(12.3,.80,.32),accent,.035)
    # Glazed shopfront with a 2.5m clear entrance in front of the pickup counter.
    for x in [-8.55,-5.8,-3.05]:
        panel('Shopfront glass',(x,1.65,2.70),(2.5,2.9,.025),window,.005)
    for x in [-9.9,-7.2,-4.4,-1.65,1.65]: panel('Shopfront mullion',(x,1.64,2.75),(.075,3.2,.1),BLACK,.009)
    for y in [.14,3.22]: panel('Shopfront transom',(-4,y,2.76),(12,.09,.1),BLACK,.012)
    for i in range(25):
        x=-9.9+i*.48
        panel('Awning rib',(x,3.12,3.22),(.23,.055,1.25),accent if i%2 else IVORY,.007)
    # Customer counter retains the exact gameplay pickup face and bag position.
    panel('Counter oak carcass',(-3,.52,0),(7,1.04,.96),WOOD,.025)
    panel('Stone counter top',(-3,1.09,0),(7.15,.12,1.12),STONE,.035)
    for x in [-6,-4,-2,0]: panel('Counter fluted detail',(x,.55,.49),(.032,.82,.025),BLACK,.007)
    panel('Pickup paper bag',(0,1.37,0),(.45,.50,.30),mat('KraftPaper',(.52,.37,.19),.96),.016)
    tube('Bag handle',[(-.11,1.6,0),(-.10,1.73,0),(.10,1.73,0),(.11,1.6,0)],.012,WOOD,6)
    panel('POS terminal foot',(-1.25,1.17,-.03),(.24,.06,.20),BLACK)
    tube('POS stand',[(-1.25,1.18,-.03),(-1.25,1.38,-.08)],.034,BLACK)
    panel('POS screen',(-1.25,1.45,-.08),(.34,.25,.04),GLASS,.025)
    # Open kitchen, service pass, prep island, refrigerator and appliances.
    panel('Kitchen tile wall',(-4,1.55,-7.76),(11.7,3,.035),IVORY,.004)
    for x in [-8.8,-6.6,-4.4]:
        panel('Kitchen cabinet',(x,.46,-6.92),(2.0,.92,1.3),STEEL,.03)
        panel('Prep worktop',(x,.97,-6.92),(2.08,.07,1.4),STEEL,.025)
        for sx in [-.45,.45]: panel('Cabinet handle',(x+sx,.74,-6.25),(.28,.025,.04),CHROME,.008)
    panel('Refrigerator',(0.9,1.15,-6.9),(1.45,2.3,1.3),STEEL,.06)
    for y in [.75,1.72]: panel('Fridge handle',(.4,y,-6.2),(.035,.42,.055),CHROME,.013)
    panel('Range hood',(-4.4,2.35,-6.9),(2.3,.6,1.4),STEEL,.08)
    panel('Hood flue',(-4.4,3.25,-7.1),(.7,1.3,.65),STEEL)
    for x in [-4.8,-4.0]:
        for z in [-7.15,-6.65]: torus('Gas burner',(x,1.02,z),.15,.023,BLACK,axis='y',n=20,m=6)
    for x in [-8.5,-7.7]:
        torus('Sink rim',(x,.999,-6.9),.25,.025,CHROME,axis='y',n=24)
        tube('Gooseneck faucet',[(x,1,-7.35),(x,1.30,-7.35),(x,1.38,-7.19),(x,1.28,-7.05)],.019,CHROME)
    for x in [-8.4,-6.3,-4.2]:
        panel('Kitchen shelf',(x,2.1,-7.45),(1.85,.06,.5),WOOD)
        for j in range(4): tube('Storage canister',[(x-.55+j*.35,2.13,-7.42),(x-.55+j*.35,2.36,-7.42)],.10,IVORY,16)
    if kind==2:
        panel('Pizza oven',(-1.7,1.22,-6.9),(1.75,1.05,1.35),BRICK,.15)
        panel('Oven opening',(-1.7,1.24,-6.21),(1.2,.48,.04),BLACK,.12)
    # Dining area left of the delivery lane; no furniture blocks the counter.
    for x,z in [(-8.4,.65),(-8.4,-2.3),(-5.9,-3.6)]:
        tube('Table pedestal',[(x,.04,z),(x,.73,z)],.065,BLACK,14)
        panel('Table foot',(x,.035,z),(.62,.07,.62),BLACK,.05)
        panel('Dining tabletop',(x,.78,z),(1.2,.075,.85),WOOD,.06)
        chair(x,z+.70)
        chair(x,z-.70)
        for sx in [-.28,.28]:
            torus('Plate rim',(x+sx,.827,z),.15,.01,IVORY,axis='y',n=24,m=4)
            tube('Water glass',[(x+sx,.83,z-.22),(x+sx,.98,z-.22)],.037,window,12)
        tube('Bud vase',[(x,.82,z),(x,1.02,z)],.035,STONE,12)
    for x in [-7.5,-4,.0]:
        tube('Pendant cord',[(x,4.2,-2.4),(x,2.65,-2.4)],.008,BLACK,6)
        loft('Pendant shade',[(2.58,x,-2.4,.30,.30),(2.68,x,-2.4,.28,.28),(2.91,x,-2.4,.10,.10)],accent,24)
    for x in [-7.8,-5.6,-3.4]:
        panel('Menu frame',(x,2.65,-4.7),(1.7,1.05,.08),WOOD,.02)
        panel('Menu board',(x,2.65,-4.64),(1.56,.9,.03),BLACK,.01)
        for j in range(5): panel('Menu typography line',(x-.12,2.92-j*.14,-4.61),(1.05 if j else 1.25,.025,.01),IVORY,.002)
    export('restaurant_'+str(kind))

def apartment(kind):
    clear(); floors=5 if kind==0 else 7; width=16; depth=15; h=floors*3.05
    facade=BRICK if kind==0 else STONE
    panel('Apartment structure',(0,h/2,0),(width,h,depth),facade,.07)
    for floor in range(floors):
        y=1.8+floor*3.05
        panel('Floor string course',(0,y-1.4,0),(16.25,.16,15.25),IVORY)
        for side in [-1,1]:
            for x in [-5.7,-1.9,1.9,5.7]:
                z=side*7.56
                panel('Window recess',(x,y,z),(2.4,1.85,.12),BLACK)
                panel('Double glazing',(x,y,z+side*.08),(2.16,1.62,.035),GLASS,.008)
                for sx in [-1.14,0,1.14]: panel('Window frame',(x+sx,y,z+side*.13),(.055,1.8,.06),IVORY,.007)
                if floor>0 and (kind==1 or abs(x)<3):
                    panel('Balcony slab',(x,y-1.02,side*8.3),(2.9,.18,1.6),STONE)
                    tube('Balcony handrail',[(x-1.4,y,side*9.02),(x+1.4,y,side*9.02)],.026,STEEL)
                    for j in range(9): tube('Balcony baluster',[(x-1.35+j*.3375,y-1,side*9.02),(x-1.35+j*.3375,y,side*9.02)],.014,STEEL,6)
            for z in [-4.8,0,4.8]:
                panel('Side window',(side*8.04,y,z),(.06,1.75,2.05),GLASS)
                for dz in [-1.05,0,1.05]: panel('Side mullion',(side*8.08,y,z+dz),(.08,1.83,.045),IVORY,.006)
    panel('Roof parapet',(0,h+.2,0),(16.5,.4,15.5),IVORY)
    for x in [-4,3]:
        panel('Rooftop heat pump',(x,h+.75,1),(2,1.1,1.5),STEEL,.04)
        for z in [.5,1.5]: torus('Vent fan',(x,h+1.32,z),.35,.025,BLACK,axis='y',n=20,m=4)
    panel('Entrance surround',(0,1.4,7.65),(3.1,2.8,.2),STONE)
    panel('Lobby glazing',(0,1.3,7.78),(2.6,2.55,.035),GLASS)
    panel('Entry canopy',(0,3.0,8.7),(4.2,.18,2.5),STEEL)
    for x in [-1.4,1.4]: tube('Entrance canopy brace',[(x,3,9.5),(x,3.8,7.6)],.035,STEEL)
    export('apartment_'+str(kind))

def park():
    clear()
    # Cast bench ends with curved seat/back slats and fasteners.
    for x in [-.86,.86]:
        tube('Bench cast frame',[(x,.02,.30),(x,.40,.20),(x,.47,-.15),(x,1.0,-.36)],.047,BLACK,12)
        tube('Bench front foot',[(x,.02,-.38),(x,.45,-.16)],.042,BLACK)
        tube('Curved armrest',[(x,.49,.19),(x,.73,.17),(x,.76,-.22),(x,.6,-.3)],.032,BLACK)
    for z in [-.22,-.07,.08,.23]: panel('Bench timber seat',(0,.48,z),(2.03,.065,.12),WOOD,.025)
    for y in [.64,.79,.94]: panel('Bench timber back',(0,y,-.32),(2.03,.115,.055),WOOD,.02)
    for x in [-.86,.86]:
        for z in [-.2,.1]: ellipsoid('Bolt',(x,.52,z),(.017,.009,.017),STEEL,n=8,m=4)
    export('park_bench')
    clear()
    loft('Cast fountain basin',[(.02,0,0,1.65,1.65),(.15,0,0,1.74,1.74),(.47,0,0,1.78,1.78),(.57,0,0,1.68,1.68),(.49,0,0,1.51,1.51),(.18,0,0,1.48,1.48)],STONE,64)
    loft('Fountain pedestal',[(.2,0,0,.42,.42),(.4,0,0,.32,.32),(1.15,0,0,.20,.20),(1.28,0,0,.54,.54)],STONE,40)
    torus('Fountain rim',(0,.55,0),1.68,.07,STONE,axis='y',n=64)
    export('fountain')
    clear()
    gravel=mat('ParkGravel',(.34,.31,.23),.96)
    # Continuous oval loop, with a clear cross-axis promenade.
    verts=[]; faces=[]
    for i in range(96):
        a=i*math.tau/96
        for inset in [0,1.15]: verts.append(((9-inset)*math.cos(a),.035,(14-inset)*math.sin(a)))
    for i in range(96): faces.append((i*2,((i+1)%96)*2,((i+1)%96)*2+1,i*2+1))
    mesh('Oval gravel promenade',verts,faces,gravel)
    panel('North south path',(0,.027,0),(2.6,.054,32),gravel,.01)
    panel('East west path',(0,.028,0),(20,.056,2.6),gravel,.01)
    # Pergola: timber posts, knee braces, edge beams and spaced sun battens.
    for x in [-6.5,-2.5]:
        for z in [4,8]:
            panel('Pergola post shoe',(x,.13,z),(.24,.26,.24),STEEL,.015)
            panel('Pergola post',(x,1.42,z),(.16,2.84,.16),WOOD,.02)
            tube('Pergola knee brace',[(x,2.15,z),(x+(.6 if x< -4 else -.6),2.8,z)],.065,WOOD,8)
    for z in [4,8]: panel('Pergola beam',(-4.5,2.87,z),(4.7,.22,.15),WOOD,.02)
    for x in [-6.6+i*.45 for i in range(11)]: panel('Pergola rafters',(x,3.02,6),(.09,.13,4.8),WOOD,.014)
    for x,z in [(-5,-7),(5,8)]:
        loft('Raised planting bowl',[(0,x,z,.85,.65),(.12,x,z,.95,.72),(.42,x,z,1.0,.76),(.47,x,z,.88,.65)],STONE,28)
        for j in range(35):
            a=j*2.4; r=R.uniform(.1,.7)
            tube('Flower stem',[(x+r*math.cos(a),.42,z+r*math.sin(a)),(x+r*math.cos(a),.7+R.random()*.2,z+r*math.sin(a))],.008,LEAF,5)
            ellipsoid('Flower head',(x+r*math.cos(a),.84,z+r*math.sin(a)),(.045,.035,.045),mat('ParkFlowers',(.53,.24,.20)),n=8,m=4)
    export('park_garden')

def street_details():
    clear()
    # Galvanized tapered mast, curved bracket and aerodynamic LED housing.
    tube('Lamp mast',[(0,0,0),(0,.22,0),(0,4.6,0)],[.095,.075,.045],STEEL,12)
    tube('Swan neck',[(0,4.55,0),(0,4.9,0),(.25,5.03,0),(.66,5.02,0)],.045,STEEL,12)
    ellipsoid('Luminaire shell',(.66,5.02,0),(.40,.075,.18),STEEL,n=24,m=8)
    panel('LED diffuser',(.67,4.965,0),(.60,.027,.25),LAMP,.018)
    loft('Mast base',[(0,0,0,.15,.15),(.08,0,0,.15,.15),(.28,0,0,.09,.09)],BLACK,16)
    export('street_lamp')
    clear()
    tube('Mailbox post',[(0,0,0),(0,1.05,0)],.04,STEEL)
    verts=[]; faces=[]
    profile=[(-.20,.92),(.20,.92),(.20,1.16)]+[(.20*math.cos(a),1.16+.20*math.sin(a)) for a in [i*math.pi/14 for i in range(1,15)]]
    for z in [-.30,.30]: verts.extend([(x,y,z) for x,y in profile])
    n=len(profile)
    for i in range(n): faces.append((i,(i+1)%n,(i+1)%n+n,i+n))
    faces.extend([tuple(reversed(range(n))),tuple(n+i for i in range(n))])
    bevel(mesh('Rolled steel mailbox',verts,faces,mat('MailboxEnamel',(.09,.15,.13),.30,.5)),.01)
    panel('Mailbox door handle',(0,1.10,.322),(.08,.025,.025),CHROME,.008)
    tube('Mailbox flag',[(.218,1.02,0),(.218,1.4,0)],.009,RED,6)
    panel('Flag blade',(.218,1.36,.055),(.02,.10,.12),RED,.007)
    export('mailbox')
    clear()
    for x in [-.55,.55]: panel('Planter end',(x,.22,0),(.065,.44,1.0),WOOD,.015)
    for z in [-.5,.5]:
        for y in [.08,.21,.34]: panel('Planter cedar slat',(0,y,z),(1.16,.115,.045),WOOD,.012)
    panel('Planter soil',(0,.40,0),(1.07,.04,.91),mat('PottingSoil',(.04,.025,.012)),.006)
    R.seed(50); verts=[]; faces=[]
    for j in range(240):
        a=j*2.399; r=R.random()**.5*.58; x=r*math.cos(a); z=r*math.sin(a)*.80; y=.52+.44*(1-r/.8)+R.uniform(-.10,.10)
        u=Vector((math.cos(a),.5,math.sin(a)))*R.uniform(.10,.17); v=Vector((-math.sin(a),0,math.cos(a)))*.055; p=Vector((x,y,z)); k=len(verts)
        verts.extend([p-u,p+v,p+u,p-v,p+Vector((0,.022,0))]); faces.extend([(k,k+1,k+4),(k+1,k+2,k+4),(k+2,k+3,k+4),(k+3,k,k+4)])
    mesh('Boxwood leaves',verts,faces,LEAF)
    export('garden_planter')
    clear()
    loft('Helmet shell',[(0,0,0,.105,.12),(.045,0,0,.12,.135),(.09,0,0,.10,.12),(.13,0,0,.045,.06)],PAINT,32)
    for x in [-.055,0,.055]: panel('Helmet cooling vent',(x,.108,-.02),(.017,.009,.105),BLACK,.004)
    tube('Helmet strap',[(-.10,0,0),(-.06,-.13,-.025),(.06,-.13,-.025),(.1,0,0)],.007,BLACK,6)
    export('helmet')

def commerce():
    clear()
    for x in [-.055,.055]:
        tube('Scooter chassis',[(x,.30,.65),(x,.25,-.25),(x,.75,-.65)],.04,STEEL,12)
    loft('Pressed scooter body',[(.22,0,.40,.15,.48),(.38,0,.40,.26,.52),(.63,0,.48,.24,.42),(.72,0,.48,.17,.33)],PAINT,36)
    loft('Sculpted seat',[(.70,0,.40,.17,.34),(.76,0,.40,.22,.37),(.81,0,.40,.20,.35)],BLACK,32)
    panel('Footboard',(0,.28,-.12),(.46,.08,.65),BLACK,.035)
    loft('Leg shield',[(.30,0,-.50,.22,.055),(.65,0,-.57,.26,.065),(.95,0,-.61,.18,.07)],PAINT,32)
    tube('Steering column',[(0,.36,-.69),(0,1.05,-.58)],.035,CHROME)
    tube('Handlebar',[(-.32,1.08,-.53),(-.20,1.1,-.62),(.20,1.1,-.62),(.32,1.08,-.53)],.024,STEEL)
    ellipsoid('Headlamp',(0,1.02,-.68),(.13,.09,.045),LAMP)
    for z in [-.70,.73]:
        before=set(bpy.context.scene.objects)
        torus('Scooter tyre',(0,.25,z),.195,.055,BLACK,axis='x',n=40)
        torus('Scooter rim',(0,.25,z),.14,.026,CHROME,axis='x',n=32)
        for a in range(8):
            angle=a*math.tau/8
            tube('Cast wheel spoke',[(0,.25,z),(0,.25+.14*math.cos(angle),z+.14*math.sin(angle))],.018,CHROME,6)
        pivot('WheelFront' if z<0 else 'WheelRear',(0,.25,z),set(bpy.context.scene.objects)-before)
    for x in [-.30,.30]:
        tube('Mirror stem',[(x,1.08,-.53),(x*1.22,1.29,-.58)],.01,CHROME)
        ellipsoid('Mirror',(x*1.22,1.30,-.59),(.065,.04,.016),CHROME)
    panel('Rear lamp',(0,.62,.92),(.20,.075,.03),RED,.018)
    export('scooter')
    fabric=mat('WovenEquipment',(.10,.19,.17),.9)
    for name,w,h,d in [('delivery_bag',.46,.49,.43),('backpack',.32,.46,.22)]:
        clear()
        loft('Sewn bag body',[(0,0,0,w*.42,d*.42),(.05,0,0,w*.5,d*.5),(h*.8,0,0,w*.5,d*.5),(h,0,0,w*.40,d*.42)],fabric,32)
        for x in [-w*.33,w*.33]:
            tube('Shoulder webbing',[(x,h*.9,-d*.4),(x,h*.65,-d*.75),(x,.06,-d*.42)],.018,BLACK,8)
        tube('Carry handle',[(-.07,h,0),(-.06,h+.08,0),(.06,h+.08,0),(.07,h,0)],.014,BLACK,8)
        panel('Reflective strip',(0,h*.4,d*.505),(w*.8,.025,.012),CHROME,.006)
        tube('Zip seam',[(-w*.42,h*.81,d*.40),(0,h*.83,d*.5),(w*.42,h*.81,d*.40)],.005,CHROME,6)
        export(name)
    clear()
    for side in [-1,1]:
        ellipsoid('Glove palm',(side*.10,.035,0),(.065,.025,.085),fabric,n=20,m=10)
        for i in range(4):
            tube('Glove finger',[(side*.10-.045+i*.029,.035,-.05),(side*.10-.045+i*.029,.032,-.13+abs(i-1.5)*.015)],.012,fabric,10)
        tube('Glove thumb',[(side*.10+.05,.035,0),(side*.10+.084,.03,-.05)],.017,fabric,10)
    export('gloves')
    for kind in ['equipment','bikes','cars','scooters','wc']:
        clear()
        panel('Polished showroom floor',(0,.05,0),(14,.10,10),STONE,.015)
        panel('Brick rear wall',(0,1.9,-5),(14,3.8,.26),BRICK,.025)
        for x in [-7,7]: panel('Side wall',(x,1.9,0),(.26,3.8,10),BRICK,.025)
        panel('Roof fascia',(0,3.9,0),(14.5,.25,10.5),STEEL,.035)
        for x in [-4.5,4.5]:
            panel('Shopfront glazing',(x,1.65,5),(5,3.3,.025),mat('RetailGlass',(.49,.62,.64),.10,.05,.20),.003)
            for dx in [-2.5,0,2.5]: panel('Aluminium mullion',(x+dx,1.65,5),(.045,3.3,.06),STEEL,.008)
        panel('Sign fascia',(0,3.5,5.12),(14,.55,.16),PAINT,.025)
        panel('Service counter',(4,.55,1),(3,1.1,.8),WOOD,.025)
        panel('Countertop',(4,1.13,1),(3.1,.08,.95),STONE,.02)
        for x in [-5,0,5]:
            tube('Pendant cable',[(x,3.8,-1),(x,2.8,-1)],.008,BLACK,6)
            loft('Spun light shade',[(2.7,x,-1,.3,.3),(2.8,x,-1,.22,.22),(2.92,x,-1,.06,.06)],STEEL,24)
        if kind in ['equipment','wc']:
            for x in [-5,-2]:
                for y in [.4,1.1,1.8]: panel('Retail shelves',(x,y,-4.5),(2.5,.07,.7),WOOD,.01)
        if kind=='wc':
            panel('Washroom privacy partition',(-1,1.1,-2.5),(.12,2.2,4.5),IVORY,.02)
            panel('Cubicle screen',(-3.5,1.1,-.4),(5,2.2,.12),IVORY,.02)
            loft('Ceramic WC pedestal',[(0,-3,-2,.20,.24),(.35,-3,-2,.28,.35),(.43,-3,-2,.29,.36)],IVORY,32)
            torus('Toilet seat',(-3,.44,-2),.26,.035,IVORY,axis='y')
            panel('Cistern',(-3,.62,-2.4),(.55,.65,.23),IVORY,.05)
            loft('Wash basin',[(.8,3,-3,.20,.15),(.94,3,-3,.42,.32),(1.02,3,-3,.43,.33)],IVORY,32)
            tube('Tap',[(3,1,-3.2),(3,1.22,-3.2),(3,1.22,-3.0)],.025,CHROME)
        export('store_'+kind)
    clear()
    for x in [-1.5,1.5]:
        for z in [-.6,.6]: tube('Kiosk steel post',[(x,0,z),(x,2.65,z)],.04,STEEL,10)
    panel('Kiosk oak counter',(0,1,0),(3.3,.1,1.5),WOOD,.03)
    for x in [-1.4+i*.14 for i in range(21)]: panel('Counter vertical slat',(x,.5,.6),(.10,.9,.06),WOOD,.012)
    panel('Kiosk canopy',(0,2.65,0),(3.5,.12,1.9),PAINT,.025)
    panel('Kiosk fascia',(0,2.45,.9),(3.5,.4,.08),STEEL,.015)
    export('gear_kiosk')

def landscape():
    clear(); verts=[]; faces=[]
    for iz in range(81):
        z=-1120+iz*20
        for ix in range(67):
            x=-660+ix*20
            outside=max(abs(x)-135,z-78,-718-z,0)
            rise=max(0,outside-35)
            y=-.12+rise*(.04+.07*(math.sin(x*.011+z*.004)**2)) + min(rise,80)*.15*math.sin(z*.018)*math.cos(x*.016)
            verts.append((x,y,z))
    for iz in range(80):
        for ix in range(66):
            k=iz*67+ix; faces.append((k,k+1,k+68,k+67))
    mesh('Meadow hills',verts,faces,mat('DistantMeadow',(.15,.21,.08),1),True)
    export('horizon_terrain')

category=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'all'
if category in ['all','landscape']: landscape()
if category in ['all','commerce']: commerce()
if category in ['all','vehicles']:
    for k in range(5): vehicle(k)
    bicycle()
if category in ['all','nature']:
    for k in range(3): tree(k)
    grass(); park()
if category in ['all','people']: person()
if category in ['all','details']: street_details()
if category in ['all','buildings']:
    for k in range(3): restaurant(k)
    for k in range(2): apartment(k)
with open(os.path.join(OUT,'source','manifest_'+category+'.json'),'w') as f: json.dump(REPORT,f,indent=2)
print('CITY ASSET WORKSHOP COMPLETE',flush=True)

