"""Rebuild the supplied car as articulated, metre-scale glTF using Blender.
Run inside the isolated car repair Blender session. Original car_model.glb is read-only.
"""
import bpy, bmesh, math, json, os
import numpy as np
from mathutils import Vector
ROOT = 'C:/GodotProjects/delivery-simulator-2026'
OUT = ROOT + '/assets/vehicles/repaired_car'
for folder in ['source', 'textures', 'previews']:
    os.makedirs(OUT+'/'+folder, exist_ok=True)
open(OUT+'/source/.gdignore','w').close()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=ROOT+'/car_model.glb')
body = next(o for o in bpy.context.selected_objects if o.type=='MESH')
body.name='Coachwork'
a=np.array([v.co[:] for v in body.data.vertices]); lo=a.min(0); hi=a.max(0)
for v in body.data.vertices:
    v.co.x=(v.co.x-(lo[0]+hi[0])/2)*2.0/(hi[0]-lo[0])
    v.co.y=(v.co.y-(lo[1]+hi[1])/2)*4.29/(hi[1]-lo[1])
    v.co.z=(v.co.z-lo[2])*1.47/(hi[2]-lo[2])
body.data.update()
original=body.data.materials[0]
original.name='Car_DetailedTrim'
base_node=next(n for n in original.node_tree.nodes if n.type=='TEX_IMAGE' and any(l.to_socket.name=='Base Color' for l in n.outputs['Color'].links))
image=base_node.image
pixels=np.empty(len(image.pixels),dtype=np.float32); image.pixels.foreach_get(pixels)
pixels=pixels.reshape(image.size[1],image.size[0],4)
for n in original.node_tree.nodes:
    if n.type=='TEX_IMAGE':
        n.image.filepath_raw=OUT+'/textures/'+('body_albedo.png' if n==base_node else 'body_orm.png')
        n.image.file_format='PNG'; n.image.save()

def material(name,color,metal=0,rough=.4):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metal
    bs.inputs['Roughness'].default_value=rough
    mat.diffuse_color=(*color,1)
    return mat
paint=material('Car_SilverClearcoat',(.40,.43,.46),.78,.25)
bs=next(n for n in paint.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
bs.inputs['Coat Weight'].default_value=.65; bs.inputs['Coat Roughness'].default_value=.15
glass=material('Car_SmokedGlass',(.025,.045,.052),.25,.14)
rubber=material('Car_TireRubber',(.018,.021,.024),0,.82)
trim=material('Car_BlackTrim',(.012,.016,.019),.1,.43)
alloy=material('Car_MachinedAlloy',(.49,.52,.56),.90,.22)
disc=material('Car_BrakeSteel',(.16,.17,.18),.8,.43)
lamp=material('Car_LED',(.75,.88,1),.15,.18)
bs=next(n for n in lamp.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
bs.inputs['Emission Color'].default_value=(.75,.88,1,1); bs.inputs['Emission Strength'].default_value=.5
tail=material('Car_RedLens',(.35,.008,.012),.25,.21)
for mat in [paint,glass,trim]: body.data.materials.append(mat)
uvs=body.data.uv_layers.active.data

def inside(poly,y,z):
    inside=False; j=len(poly)-1
    for i in range(len(poly)):
        yi,zi=poly[i]; yj,zj=poly[j]
        if (zi>z)!=(zj>z) and y<(yj-yi)*(z-zi)/(zj-zi)+yi: inside=not inside
        j=i
    return inside
side_glass=[(-.90,1.015),(-.31,1.385),(.56,1.38),(1.31,1.04),(.98,1.01)]
counts={}
for p in body.data.polygons:
    x,y,z=p.center
    uv=sum((uvs[i].uv for i in p.loop_indices),Vector((0,0)))/len(p.loop_indices)
    c=pixels[int(uv.y*(image.size[1]-1))%image.size[1],int(uv.x*(image.size[0]-1))%image.size[0],:3]
    lum=float(c.mean()); chroma=float(c.max()-c.min())
    # Preserve grille, lamps, badges-free handles and small trim from the source atlas.
    side=abs(x)>.55 and inside(side_glass,y,z) and abs(y-.13)>.048
    front=abs(x)<.70 and -1.22<y<-.33 and z>1.005 and z<1.42
    rear=abs(x)<.65 and .65<y<1.60 and z>1.025 and z<1.41
    if (side or front or rear) and lum>.17 and chroma<.19:
        p.material_index=2
    elif lum>.28 and chroma<.18 and z>.24:
        p.material_index=1
    elif lum<.09 and z>.35:
        p.material_index=3
    p.material_index=0
    counts[p.material_index]=counts.get(p.material_index,0)+1
print('SURFACE_CLASSIFICATION',counts,flush=True)

# Delete the fused, oval wheels. New circular tires sit inside lined wheel arches.
AXLES=[-1.35,1.27]; WHEEL_Z=.34; RADIUS=.34; TRACK=.79
bm=bmesh.new(); bm.from_mesh(body.data)
remove=[]
for v in bm.verts:
    x,y,z=v.co
    if abs(x)>.62 and any(((y-yc)/.48)**2+((z-.325)/.34)**2<1.035 for yc in AXLES):
        remove.append(v)
bmesh.ops.delete(bm,geom=remove,context='VERTS')
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0008)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
for v in bm.verts:
    x,y,z=v.co
    if abs(x)>.57 and z<.99:
        for yc in AXLES:
            dy=y-yc
            if abs(dy)<.78:
                weight=min(1,max(0,(.78-abs(dy))/.20))*min(1,max(0,(.99-z)/.26))
                v.co.y=yc+dy*(1-.22*weight)
                break
bm.to_mesh(body.data); bm.free()
body.data.validate(clean_customdata=True)
bpy.context.view_layer.objects.active=body
smooth=body.modifiers.new('Relax generated surface ripples','SMOOTH'); smooth.factor=.3; smooth.iterations=3
bpy.ops.object.modifier_apply(modifier=smooth.name)
dec=body.modifiers.new('Runtime body topology','DECIMATE'); dec.ratio=min(1,60000/max(1,len(body.data.polygons))); dec.use_collapse_triangulate=True
bpy.ops.object.modifier_apply(modifier=dec.name)
body.data.validate(clean_customdata=True)
for p in body.data.polygons: p.use_smooth=True

def mesh(name,verts,faces,mat,parent=None):
    data=bpy.data.meshes.new(name); data.from_pydata(verts,[],faces); data.update()
    obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj); obj.data.materials.append(mat)
    obj.parent=parent
    for p in data.polygons: p.use_smooth=True
    return obj

def lathe(name,profile,mat,parent,n=64):
    vs=[]; fs=[]
    for x,r in profile:
        vs.extend((x,r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n)) for i in range(n))
    for j in range(len(profile)-1):
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n
            fs.append((a,b,b+n,a+n))
    ob=mesh(name,vs,fs,mat,parent)
    uv=ob.data.uv_layers.new(name='UVMap')
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            vi=ob.data.loops[li].vertex_index
            uv.data[li].uv=(vi%n/n,vi//n/max(1,len(profile)-1))
    return ob

def box(name,loc,size,mat,parent=None,bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    ob=bpy.context.object; ob.name=name; ob.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(mat)
    if bevel:
        mod=ob.modifiers.new('Rounded manufacture edges','BEVEL'); mod.width=bevel; mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod=ob.modifiers.new('Face weighted normals','WEIGHTED_NORMAL')
        bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.parent=parent
    return ob

def empty(name,loc=(0,0,0),parent=None):
    ob=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(ob); ob.location=loc; ob.parent=parent
    return ob
root=empty('RepairedCar')
body.parent=root
for y,label in zip(AXLES,['Front','Rear']):
    for side,side_name in [(-1,'L'),(1,'R')]:
        steer=empty('Steer'+label+side_name,(side*TRACK,y,WHEEL_Z),root)
        wheel=empty('Wheel'+label+side_name,parent=steer)
        wheel['radius']=RADIUS
        # Closed tire section, including sidewall beads and longitudinal tread channels.
        profile=[(-.105,.218),(-.116,.25),(-.111,.30),(-.087,.332),(-.067,.34),(-.045,.34),(-.039,.334),(-.033,.34),(-.010,.34),(-.004,.334),(.002,.34),(.027,.34),(.033,.334),(.039,.34),(.066,.34),(.087,.332),(.111,.30),(.116,.25),(.105,.218),(-.105,.218)]
        lathe('Tire_'+label+side_name,profile,rubber,wheel,64)
        lathe('Rim_'+label+side_name,[(-.102,.202),(-.104,.218),(-.095,.225),(.095,.225),(.104,.218),(.102,.202),(-.102,.202)],alloy,wheel,48)
        lathe('Rotor_'+label+side_name,[(-.025,0),(-.025,.182),(.025,.182),(.025,0)],disc,wheel,40)
        outer=side*.108
        lathe('Hub_'+label+side_name,[(outer-side*.035,0),(outer-side*.035,.056),(outer,.056),(outer,0)],alloy,wheel,24)
        for i in range(10):
            ang=i*math.tau/10
            vs=[]
            for xx in [outer-side*.028,outer]:
                for r,off in [(.05,-.015),(.212,-.011),(.212,.011),(.05,.015)]:
                    vs.append((xx,r*math.cos(ang)+off*math.sin(ang),r*math.sin(ang)-off*math.cos(ang)))
            spoke=mesh('AlloySpoke',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],alloy,wheel)
        for i in range(5):
            ang=i*math.tau/5
            lug=lathe('Lug',[(outer,0),(outer,.008),(outer+side*.009,.008),(outer+side*.009,0)],disc,wheel,8)
            lug.location=(0,.037*math.cos(ang),.037*math.sin(ang))
        # Stationary arch liners mask the cut boundary and underbody; they never rotate.
        vs=[]; fs=[]
        for x in [side*.64,side*.88]:
            for i in range(25):
                ang=math.pi*i/24
                vs.append((x,y+.382*math.cos(ang),.325+.36*math.sin(ang)))
        fs=[(i,i+1,i+26,i+25) for i in range(24)]
        liner=mesh('ArchLiner',vs,fs,trim,root)
        liner.data.materials[0].use_backface_culling=False

box('Undertray',(0,0,.24),(1.48,3.70,.09),trim,root,.04)
# Clean fitted glazing patches. Their UV-free PBR shader exports directly.
from mathutils.bvhtree import BVHTree
bvh=BVHTree.FromPolygons([v.co for v in body.data.vertices],[list(p.vertices) for p in body.data.polygons])
def tube(name,points,r,mat):
    curve=bpy.data.curves.new(name,'CURVE'); curve.dimensions='3D'; curve.resolution_u=1
    curve.bevel_depth=r; curve.bevel_resolution=2
    sp=curve.splines.new('POLY'); sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    ob=bpy.data.objects.new(name,curve); bpy.context.collection.objects.link(ob); ob.parent=root; ob.data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active=ob
    bpy.ops.object.convert(target='MESH')
    return bpy.context.object

def glazing(name,corners,side=0):
    # Bilinear curved pane with planar boundaries; fit to the retained body surface.
    vs=[]; fs=[]; n=14
    for j in range(n+1):
        v=j/n
        for i in range(n+1):
            u=i/n
            p=Vector(corners[0]).lerp(Vector(corners[1]),u).lerp(Vector(corners[3]).lerp(Vector(corners[2]),u),v)
            if side:
                hit=bvh.ray_cast(Vector((side*2,p.y,p.z)),Vector((-side,0,0)))
                if hit[0]:p.x=hit[0].x+side*.012
            else:
                hit=bvh.ray_cast(Vector((p.x,p.y,3)),Vector((0,0,-1)))
                if hit[0]:p.z=hit[0].z+.012
            vs.append(tuple(p))
    for j in range(n):
        for i in range(n):
            k=j*(n+1)+i;fs.append((k,k+1,k+n+2,k+n+1))
    pane=mesh(name,vs,fs,glass,root)
    mod=pane.modifiers.new('Polished glass surface','SMOOTH');mod.factor=.5;mod.iterations=3
    bpy.context.view_layer.objects.active=pane;bpy.ops.object.modifier_apply(modifier=mod.name)
    edges=list(range(n+1))+[j*(n+1)+n for j in range(1,n+1)]+[n*(n+1)+i for i in range(n-1,-1,-1)]+[j*(n+1) for j in range(n-1,0,-1)]+[0]
    tube('WindowGasket',[tuple(pane.data.vertices[k].co) for k in edges],.009,trim)
    return pane
for s in [-1,1]:
    glazing('FrontSideGlass',[(s*.82,-.99,1.015),(s*.82,.09,1.02),(s*.66,.055,1.385),(s*.68,-.34,1.36)],s)
    glazing('RearSideGlass',[(s*.82,.20,1.02),(s*.82,1.34,1.04),(s*.67,.82,1.355),(s*.66,.17,1.385)],s)
glazing('Windshield',[(-.70,-1.28,1.00),(.70,-1.28,1.00),(.60,-.40,1.36),(-.60,-.40,1.36)])
glazing('RearGlass',[(-.61,.95,1.36),(.61,.95,1.36),(.67,1.78,1.02),(-.67,1.78,1.02)])

# Consolidate wheel pieces into one mesh per wheel, retaining per-surface materials.
for pivot in [o for o in bpy.context.scene.objects if o.name.startswith('Wheel') and o.type=='EMPTY']:
    pieces=[o for o in pivot.children if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in pieces:o.select_set(True)
    bpy.context.view_layer.objects.active=pieces[0]
    bpy.ops.object.join(); ob=bpy.context.object; ob.name='Assembly_'+pivot.name
    bpy.context.scene.cursor.location=pivot.matrix_world.translation
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

# UVs for added details, valid applied transforms; glTF converts +Y front to −Z.
# Source is Blender −Y front. Rotate all geometry 180 around Z for Godot −Z front.
root.rotation_euler.z=math.pi
bpy.context.view_layer.update()
for ob in list(bpy.context.scene.objects):
    if ob.type=='MESH' and not ob.data.uv_layers:
        bpy.context.view_layer.objects.active=ob
        bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.02)
        bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1.0
print('REPAIR_ASSEMBLED',flush=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/source/repaired_car.blend')


