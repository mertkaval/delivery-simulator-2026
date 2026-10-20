import bpy, math, bmesh
import numpy as np

def material(name,color,rough=.5,metal=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    return m,p

frame,p=material('HK_WindowEnamel',(.70,.72,.67),.29)
seal,p=material('HK_WindowSeal',(.025,.028,.027),.7)
curtain,p=material('HK_WindowPrivacy',(.72,.68,.57),.9)
# Woven linen, deep pleats and a subtle irregular hem, shared by all windows.
n=512
y,x=np.mgrid[0:n,0:n].astype(np.float32)/n
fold=.65+.22*np.cos(x*math.pi*24)+.045*np.cos(x*math.pi*48)
weave=.012*np.sin(x*math.pi*512)*np.sin(y*math.pi*512)
rgb=np.stack([(fold+weave)*v for v in [.84,.79,.67]],axis=-1)
arr=np.concatenate([rgb,np.ones((n,n,1),dtype=np.float32)],axis=-1).astype(np.float32)
im=bpy.data.images.new('HK_PrivacyLinen_512',width=n,height=n,alpha=True)
im.pixels.foreach_set(arr.ravel());im.pack()
t=curtain.node_tree.nodes.new('ShaderNodeTexImage');t.image=im
curtain.node_tree.links.new(t.outputs['Color'],p.inputs['Base Color'])
glass,p=material('HK_Glass',(.72,.82,.86),.14)
for link in list(glass.node_tree.links):
    if link.to_node==p:glass.node_tree.links.remove(link)
p.inputs['Alpha'].default_value=.24
p.inputs['IOR'].default_value=1.46
glass.surface_render_method='DITHERED'
glass.diffuse_color=(.72,.82,.86,.24)

patch=r'''
def wall(axis,a0,a1,cross,z0,z1,thick,mat,openings=(),u=.5):
    # Matching cells permit removal of interior faces and coplanar edge dissolves.
    xs=sorted(set([a0,a1]+[max(a0,min(a1,v)) for o in openings for v in o[:2]]))
    zs=sorted(set([z0,z1]+[max(z0,min(z1,v)) for o in openings for v in o[2:]]))
    out=[]
    for lo,hi in zip(xs,xs[1:]):
        for bot,top in zip(zs,zs[1:]):
            ac=(lo+hi)/2;zc=(bot+top)/2
            if any(o[0]<ac<o[1] and o[2]<zc<o[3] for o in openings):continue
            q=B(axis,ac,hi-lo,cross,thick,zc,top-bot,mat,u)
            q['structural_wall']=True;out.append(q)
    return out

def window(axis,ac,cross,zc,w,h,thick=.24,trim='HK_Trim',glass='HK_Glass',u=.5):
    trim='HK_WindowEnamel';out=[];t=.065
    def add(a,l,c,d,z,hh,m):out.append(B(axis,a,l,c,d,z,hh,m,u))
    # Continuous opaque linen backing prevents all views into an empty shell.
    add(ac,w,cross,.022,zc,h,'HK_WindowPrivacy')
    # Two external faces serve front/back and both side-wall orientations.
    for side in [-1,1]:
        c=cross+side*.085
        add(ac,w,c,.009,zc,h,glass)
        # Perimeter rubber seal; no coplanar faces with glazing or timber.
        for a in [ac-w/2+.014,ac+w/2-.014]:add(a,.028,c+side*.012,.018,zc,h,'HK_WindowSeal')
        for z in [zc-h/2+.014,zc+h/2-.014]:add(ac,w-.056,c+side*.012,.018,z,.028,'HK_WindowSeal')
    for a in [ac-w/2-t/2,ac+w/2+t/2]:add(a,t,cross,.25,zc,h,trim)
    add(ac,w+2*t,cross,.25,zc+h/2+t/2,t,trim)
    add(ac,w+2*t+.08,cross,.34,zc-h/2-t/2,t,trim)
    add(ac,.045,cross,.25,zc,h,trim)
    for side in [-1,1]:add(ac+side*(w+.045)/4,(w-.045)/2,cross,.25,zc,.04,trim)
    # Small latch below the meeting rail, visible outside through the glass.
    add(ac+.045,.045,cross-.137,.025,zc-.052,.075,'HK_WindowSeal')
    return out

_build_before_window_fix=build
def build(name,items,coll=COLL,loc=(0,0,0)):
    walls=[q for q in items if q.get('structural_wall')]
    rest=[q for q in items if not q.get('structural_wall')]
    ob=_build_before_window_fix(name,rest,coll,loc)
    if walls:
        wo=_build_before_window_fix(name+'_continuous_walls',walls,coll,loc)
        bm=bmesh.new();bm.from_mesh(wo.data)
        # Remove paired internal faces by geometry before welding vertices.
        seen={};remove=[]
        for f in bm.faces:
            key=tuple(sorted(tuple(round(v,5) for v in vert.co) for vert in f.verts))
            if key in seen:remove.extend([seen.pop(key),f])
            else:seen[key]=f
        bmesh.ops.delete(bm,geom=list(set(remove)),context='FACES_ONLY')
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        bmesh.ops.dissolve_limit(bm,angle_limit=.0001,verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL'})
        bm.to_mesh(wo.data);bm.free();wo.data.update()
        # Reproject metric UVs after dissolving to keep brick courses continuous.
        uv=wo.data.uv_layers.active
        for face in wo.data.polygons:
            vs=[wo.data.vertices[v].co for v in face.vertices]
            for li,co in zip(face.loop_indices,_uvs(vs,face.normal,.5)):uv.data[li].uv=co
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);wo.select_set(True)
        bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
    # Linen mapping belongs to each pane, not the world-scale brick UV grid.
    uv=ob.data.uv_layers.active
    for face in ob.data.polygons:
        if ob.data.materials[face.material_index].name!='HK_WindowPrivacy':continue
        vs=[ob.data.vertices[v].co for v in face.vertices]
        coords=_uvs(vs,face.normal,1)
        us=[v[0] for v in coords];vs2=[v[1] for v in coords]
        for li,(uu,vv) in zip(face.loop_indices,coords):
            uv.data[li].uv=((uu-min(us))/max(.001,max(us)-min(us)),(vv-min(vs2))/max(.001,max(vs2)-min(vs2)))
    return ob
'''
lib=bpy.data.texts['kitlib.py']
lib.write('\nimport bmesh\n'+patch)
result={'patched_shared_window_and_wall_library':True}
