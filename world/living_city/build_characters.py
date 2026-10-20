"""Skinned procedural citizens, metre scale, editable rig and authored animation clips."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
helper=open(os.path.join(HERE,'..','build_city_assets.py'),encoding='utf-8-sig').read().split('\ndef vehicle(')[0]
exec(compile(helper.replace("'city_assets'","'assets'"),'living_geometry','exec'),globals())
SKIN=mat('CitizenSkin',(.48,.29,.20),.64)
CLOTH=mat('CitizenCoat',(.095,.16,.19),.86)
TROUSER=mat('CitizenTrousers',(.045,.06,.073),.92)
HAIR=mat('CitizenHair',(.025,.018,.014),.86)
EYE=mat('CitizenEye',(.49,.48,.42),.36)
SOLE=mat('CitizenSole',(.025,.029,.033),.87)
TRIM=mat('CitizenTrim',(.12,.14,.15),.65)
WEIGHTS={}

def register(objects,rule):
    for o in objects:
        if o.type=='MESH': WEIGHTS[o.name]=rule
def emit(fn,rule,*args,**kwargs):
    o=fn(*args,**kwargs); register([o],rule); return o
def blend(y,a,b,lo,hi):
    t=max(0,min(1,(y-lo)/(hi-lo)))
    return {a:1-t,b:t}
def weight(rule,p):
    x,y,z=p
    if rule=='torso': return blend(y,'Hips','Chest',.98,1.37)
    if rule.startswith('arm'):
        side=rule[-1]
        if y>1.31: return blend(abs(x),'Chest','UpperArm'+side,.14,.255)
        return blend(y,'Forearm'+side,'UpperArm'+side,1.06,1.22)
    if rule.startswith('leg'):
        if y>.82: return blend(y,'Thigh'+rule[-1],'Hips',.82,.96)
        return blend(y,'Shin'+rule[-1],'Thigh'+rule[-1],.43,.61)
    return {rule:1}

def sculpt(index):
    clear(); WEIGHTS.clear()
    for action in list(bpy.data.actions): bpy.data.actions.remove(action)
    for material,colors in [(SKIN,[(.48,.29,.20),(.62,.42,.30),(.27,.15,.10),(.53,.36,.26),(.36,.22,.15),(.64,.44,.31)]),(HAIR,[(.025,.018,.014),(.09,.045,.022),(.015,.013,.012),(.26,.25,.23),(.035,.022,.015),(.08,.055,.032)])]:
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*colors[index],1)
    female=index in [1,4]
    coat=index in [1,3]
    chest=.185 if female else .205
    waist=.142 if female else .166
    emit(loft,'torso','Continuous tailored coat',[(.88,0,.008,.155,.102),(.98,0,0,.174,.11),(1.08,0,0,waist,.10),(1.25,0,-.012,chest*.95,.113),(1.38,0,0,chest,.105),(1.445,0,.01,chest*.84,.09),(1.475,0,.012,.075,.069)],CLOTH,32)
    if coat: emit(loft,'Hips','Raincoat hem',[(.73,0,.02,.178,.123),(.89,0,.01,.17,.114),(1.0,0,0,.168,.105)],CLOTH,32)
    emit(loft,'Hips','Trouser hip yoke',[(.84,0,.009,.153,.105),(.96,0,.006,.166,.112),(1.02,0,.0,.156,.10)],TROUSER,28)
    emit(tube,'Neck','Neck',[(0,1.43,.015),(0,1.56,.014)],[.058,.052],SKIN,20)
    # Jaw, cheek, brow and cranial vault have independent sections.
    emit(loft,'Head','Anatomical head',[(1.532,0,-.020,.038,.047),(1.55,0,-.014,.057,.063),(1.585,0,-.001,.072,.072),(1.625,0,.003,.079,.080),(1.666,0,.008,.081,.081),(1.709,0,.010,.077,.080),(1.75,0,.014,.065,.070),(1.783,0,.019,.042,.047),(1.796,0,.02,.01,.012)],SKIN,40)
    emit(loft,'Head','Nose cartilage',[(1.602,0,-.076,.009,.006),(1.613,0,-.085,.018,.016),(1.626,0,-.09,.014,.02),(1.65,0,-.079,.009,.012),(1.683,0,-.069,.008,.008)],SKIN,16)
    for side in [-1,1]:
        emit(ellipsoid,'Head','Auricle',(side*.080,1.64,.012),(.013,.027,.018),SKIN,n=16,m=12)
        emit(ellipsoid,'Head','Small recessed eye',(side*.031,1.663,-.069),(.014,.0055,.0045),EYE,n=20,m=10)
        emit(ellipsoid,'Head','Iris',(side*.031,1.663,-.073),(.004,.004,.0018),HAIR,n=12,m=8)
        emit(tube,'Head','Upper eyelid',[(side*.018,1.666,-.073),(side*.032,1.669,-.075),(side*.045,1.665,-.070)],.0025,SKIN,8)
        emit(tube,'Head','Subtle brow',[(side*.017,1.683,-.071),(side*.031,1.687,-.073),(side*.046,1.683,-.068)],.0028,HAIR,8)
    emit(tube,'Head','Lip contour',[(-.022,1.580,-.072),(-.008,1.582,-.077),(0,1.58,-.078),(.01,1.582,-.077),(.022,1.58,-.072)],.0023,mat('CitizenLip',(.28,.135,.10),.75),8)
    verts=[]; faces=[]
    for ring in range(6):
        for j in range(40):
            a=j*math.tau/40; t=ring/5
            low=1.68+.052*max(0,-math.sin(a))
            y=low+(1.806-low)*math.sin(t*math.pi/2)
            r=math.cos(t*math.pi/2)*1.02
            verts.append((.083*r*math.cos(a),y,.016+.084*r*math.sin(a)))
    for r in range(5):
        for j in range(40): faces.append((r*40+j,r*40+(j+1)%40,(r+1)*40+(j+1)%40,(r+1)*40+j))
    emit(mesh,'Head','Fitted hair cap',verts,faces,HAIR,True)
    if female:
        emit(ellipsoid,'Head','Tied hair',(0,1.688,.102),(.055,.078,.052),HAIR,n=24,m=16)
    for side in [-1,1]:
        s='L' if side<0 else 'R'
        emit(loft,'leg'+s,'Continuous trouser leg',[(.12,side*.091,.004,.045,.047),(.26,side*.093,.005,.051,.055),(.43,side*.096,.012,.059,.066),(.53,side*.099,.0,.063,.07),(.68,side*.098,.002,.076,.083),(.83,side*.094,.004,.086,.093),(.97,side*.086,.006,.088,.10)],TROUSER,24)
        emit(loft,'Foot'+s,'Contoured shoe',[(.025,side*.093,-.043,.059,.129),(.055,side*.093,-.047,.063,.134),(.10,side*.093,-.042,.06,.12),(.145,side*.093,.005,.045,.07),(.17,side*.093,.018,.042,.045)],SOLE,28)
        emit(tube,'Foot'+s,'Shoe welt',[(side*.093-.052,.055,-.13),(side*.093,.055,-.177),(side*.093+.052,.055,-.13)],.005,TRIM,8)
        # One continuous sleeve crosses the elbow; blended bone weights prevent gaps.
        emit(tube,'arm'+s,'Continuous sleeve',[(side*.158,1.375,.01),(side*.205,1.37,.003),(side*.236,1.30,.006),(side*.263,1.17,.007),(side*.274,1.10,-.005),(side*.276,.98,-.013),(side*.277,.905,-.02)],[.068,.073,.067,.060,.055,.044,.035],CLOTH,24)
        emit(ellipsoid,'Forearm'+s,'Palm',(side*.278,.863,-.02),(.034,.050,.025),SKIN,n=20,m=14)
        for finger in range(4):
            xx=side*.278+(finger-1.5)*.013
            end=.796+abs(finger-1.5)*.006
            emit(tube,'Forearm'+s,'Tapered finger',[(xx,.85,-.025),(xx,.817,-.026),(xx,end,-.035)],[.008,.007,.0045],SKIN,10)
        emit(tube,'Forearm'+s,'Thumb',[(side*.254,.884,-.025),(side*.239,.855,-.035),(side*.241,.827,-.043)],[.012,.009,.006],SKIN,10)
        emit(tube,'torso','Collar fold',[(side*.05,1.473,-.035),(side*.09,1.445,-.075),(side*.045,1.397,-.111)],[.008,.012,.004],CLOTH,10)
        emit(tube,'torso','Pocket seam',[(side*.06,1.075,-.094),(side*.127,1.115,-.075)],.0023,TRIM,6)
    emit(tube,'torso','Coat zip',[(0,.9,-.104),(0,1.29,-.124),(0,1.416,-.092)],.0028,TRIM,6)
    if index==2:
        emit(panel,'Chest','Courier backpack',(0,1.22,.19),(.30,.42,.16),mat('CitizenBag',(.27,.11,.06),.9),.055)
    if index==5:
        for x in [-.10,.10]: emit(tube,'torso','Worker reflective tape',[(x,.96,-.107),(x,1.35,-.10)],.015,mat('CitizenReflective',(.65,.69,.48),.4),8)

def rig_and_save(index):
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.ops.object.armature_add(enter_editmode=True,location=(0,0,0))
    rig=bpy.context.object; rig.name='CitizenRig'
    rig.data.edit_bones.remove(rig.data.edit_bones[0])
    definitions=[('Hips',(0,.91,0),(0,1.08,0),None),('Chest',(0,1.08,0),(0,1.44,0),'Hips'),('Neck',(0,1.44,.01),(0,1.55,.01),'Chest'),('Head',(0,1.55,.01),(0,1.79,.02),'Neck')]
    for side in [-1,1]:
        s='L' if side<0 else 'R'
        definitions += [('Thigh'+s,(side*.086,.93,0),(side*.096,.52,0),'Hips'),('Shin'+s,(side*.096,.52,0),(side*.093,.14,.01),'Thigh'+s),('Foot'+s,(side*.093,.14,.01),(side*.093,.07,-.14),'Shin'+s),('UpperArm'+s,(side*.19,1.412,0),(side*.27,1.145,0),'Chest'),('Forearm'+s,(side*.27,1.145,0),(side*.278,.855,-.02),'UpperArm'+s)]
    for name,head,tail,parent in definitions:
        b=rig.data.edit_bones.new(name); b.head=P(head); b.tail=P(tail)
        if parent: b.parent=rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in objects:
        rule=WEIGHTS[o.name]
        for v in o.data.vertices:
            weights=weight(rule,(v.co.x,v.co.z,-v.co.y))
            for bone,value in weights.items():
                if value>.0001:
                    vg=o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)
                    vg.add([v.index],value,'REPLACE')
        o.parent=rig
    # One skinned mesh, a small shared material set, no independently floating limbs.
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]; bpy.ops.object.join()
    body=bpy.context.object; body.name='CitizenSkinnedBody'
    bm=bmesh.new(); bm.from_mesh(body.data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(body.data); bm.free()
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=.015); bpy.ops.object.mode_set(mode='OBJECT')
    mod=body.modifiers.new('Weighted skin deformation','ARMATURE'); mod.object=rig
    rig.animation_data_create()
    for clip in ['Idle','Walk','Brisk','Wait','Talk','Sit','Carry','Cycle']:
        action=bpy.data.actions.new(clip); rig.animation_data.action=action
        for frame in range(1,34,2):
            phase=(frame-1)/32*math.tau
            for pb in rig.pose.bones: pb.rotation_mode='XYZ'; pb.rotation_euler=(0,0,0); pb.location=(0,0,0)
            moving=clip in ['Walk','Brisk','Carry']
            for s,shift in [('L',0),('R',math.pi)]:
                wave=math.sin(phase+shift)
                if moving:
                    rig.pose.bones['Thigh'+s].rotation_euler.x=wave*(.40 if clip!='Brisk' else .55)
                    rig.pose.bones['Shin'+s].rotation_euler.x=-max(0,-wave)*.62
                    rig.pose.bones['Foot'+s].rotation_euler.x=-wave*.12
                    rig.pose.bones['UpperArm'+s].rotation_euler.x=-wave*.27
                    rig.pose.bones['Forearm'+s].rotation_euler.x=-.12-max(0,wave)*.12
                if clip in ['Carry','Talk']:
                    rig.pose.bones['UpperArm'+s].rotation_euler.x=.32
                    rig.pose.bones['Forearm'+s].rotation_euler.x=.9+(math.sin(phase+shift)*.12 if clip=='Talk' else 0)
                if clip=='Sit':
                    rig.pose.bones['Thigh'+s].rotation_euler.x=1.45
                    rig.pose.bones['Shin'+s].rotation_euler.x=-1.45
                if clip=='Cycle':
                    rig.pose.bones['Thigh'+s].rotation_euler.x=1.1-wave*.25
                    rig.pose.bones['Shin'+s].rotation_euler.x=-1.55-wave*.4
                    rig.pose.bones['UpperArm'+s].rotation_euler.x=1.25
                    rig.pose.bones['Forearm'+s].rotation_euler.x=.35
                    rig.pose.bones['Chest'].rotation_euler.x=-.25
            rig.pose.bones['Chest'].rotation_euler.y=math.sin(phase)*(.025 if moving else .007)
            rig.pose.bones['Head'].rotation_euler.y=math.sin(phase*.5)*(.10 if clip in ['Wait','Talk'] else .025)
            rig.pose.bones['Hips'].location.y=math.sin(phase)*.003 if not moving else 0
            if clip=='Sit': rig.pose.bones['Hips'].location.y=-.45
            if moving:
                # Bake support-foot height from the deformed mesh into root translation.
                # Bone local Y is vertical; local Z is not the world up axis.
                bpy.context.view_layer.update()
                evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
                evaluated_mesh=evaluated.to_mesh()
                sole=min((evaluated.matrix_world@v.co).z for v in evaluated_mesh.vertices)
                evaluated.to_mesh_clear()
                rig.pose.bones['Hips'].location.y+=.025-sole
            for pb in rig.pose.bones:
                pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name)
                pb.keyframe_insert('location',frame=frame,group=pb.name)
        track=rig.animation_data.nla_tracks.new(); track.name=clip
        strip=track.strips.new(clip,1,action)
        track.mute=True
    rig.animation_data.action=None
    for pb in rig.pose.bones: pb.rotation_euler=(0,0,0); pb.location=(0,0,0)
    bpy.context.scene.frame_set(1); bpy.context.scene.render.fps=30
    name='citizen_%d'%index
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'source',name+'.blend'))
    for level,ratio in [(0,1),(1,.48),(2,.20)]:
        if level:
            bpy.context.view_layer.objects.active=body
            dec=body.modifiers.new('LOD simplification','DECIMATE'); dec.ratio=ratio/(1 if level==1 else .48)
            bpy.ops.object.modifier_move_up(modifier=dec.name)
            bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.validate(clean_customdata=False)
        tri=sum(len(p.vertices)-2 for p in body.data.polygons)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+('_lod%d'%level if level else '')+'.glb'),export_format='GLB',export_animations=True,export_animation_mode='ACTIONS',export_nla_strips=True,export_force_sampling=True,export_apply=False)
        REPORT[name+('_lod%d'%level if level else '')]={'triangles':tri,'bones':len(rig.data.bones),'clips':['Idle','Walk','Brisk','Wait','Talk','Sit','Carry','Cycle']}
        print('CHARACTER',name,level,tri,flush=True)

indices=[int(sys.argv[sys.argv.index('--')+1])] if '--' in sys.argv else list(range(6))
for index in indices: sculpt(index); rig_and_save(index)
with open(os.path.join(OUT,'source','characters_manifest.json'),'w') as f: json.dump(REPORT,f,indent=2)
