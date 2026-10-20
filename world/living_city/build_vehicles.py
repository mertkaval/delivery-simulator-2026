"""Distinct road and civic fleet. Editable Blender models, GLB and two reduced LODs."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
source=open(os.path.join(HERE,'..','build_city_assets.py'),encoding='utf-8-sig').read()
exec(compile(source.split('\ndef vehicle(')[0].replace("'city_assets'","'assets'"),'fleet_helpers','exec'),globals())
base_vehicle=source[source.index('def vehicle('):source.index('\ndef bicycle(')]
real_export=export
export=lambda name: None
GLASS=mat('FleetGlass',(.035,.075,.10),.12,.32,.78)
GLASS.use_backface_culling=False
INTERIOR=mat('FleetLeather',(.15,.075,.036),.67)
CARPET=mat('FleetCabin',(.025,.03,.035),.95)
LED=mat('FleetLED',(.80,.91,.96),.18,.1)
BLUE=mat('FleetBlue',(.035,.16,.55),.22,.15)
ORANGE=mat('FleetAmber',(.85,.37,.035),.23,.1)
CONFIGS={
 'compact_sport':(1,(1.79,4.29,1.47,1.31),(.61,.66,.045)),
 'executive_sedan':(0,(1.92,5.25,1.51,1.60),(.018,.026,.034)),
 'urban_crossover':(2,(1.97,4.73,1.73,1.43),(.28,.34,.35)),
 'cargo_van':(3,(2.02,5.45,2.35,1.73),(.72,.73,.69)),
 'utility_pickup':(4,(2.02,5.45,1.88,1.68),(.15,.25,.20)),
 'taxi_sedan':(0,(1.83,4.78,1.50,1.44),(.85,.56,.035)),
 'police_cruiser':(0,(1.93,5.04,1.55,1.51),(.035,.05,.065)),
 'ambulance':(3,(2.28,6.38,2.84,1.92),(.80,.81,.75)),
 'fire_engine':(4,(2.44,7.8,3.04,2.40),(.64,.035,.02)),
 'school_bus':(3,(2.43,9.20,3.10,2.91),(.84,.48,.025))}

def text(words,p,size,material=IVORY,rotation=(math.pi/2,0,0)):
    data=bpy.data.curves.new('Fleet lettering','FONT'); data.body=words; data.size=size; data.align_x='CENTER'; data.extrude=.0007
    o=bpy.data.objects.new(words,data); bpy.context.collection.objects.link(o); o.location=P(p); o.rotation_euler=rotation; o.data.materials.append(material)
    bpy.context.view_layer.objects.active=o; o.select_set(True); bpy.ops.object.convert(target='MESH'); o.select_set(False)

def interior(width,length,height,kind):
    half=width*.5; belt=.98 if kind<2 else 1.22
    panel('Cabin floor',(0,.39,.2),(width*.78,.08,2.05),CARPET,.012)
    panel('Sculpted dashboard',(0,belt-.17,-.89),(width*.78,.22,.36),CARPET,.08)
    panel('Centre console',(0,.62,-.03),(.22,.24,.8),CARPET,.055)
    panel('Infotainment display',(0,belt-.04,-.71),(.25,.16,.025),GLASS,.008)
    tube('Steering column',[(-half*.48,belt-.34,-.74),(-half*.48,belt-.19,-.51)],.045,BLACK,12)
    torus('Steering wheel',(-half*.48,belt-.17,-.48),.145,.019,CARPET,axis='y',n=28,m=8)
    for row in [0,1]:
        for side in [-1,1]:
            x=side*half*.49; z=-.23+row*.83
            panel('Seat cushion',(x,.58,z),(.43,.16,.48),INTERIOR,.065)
            panel('Seat back',(x,.91,z+.19),(.43,.59,.14),INTERIOR,.06)
            panel('Head restraint',(x,1.23,z+.2),(.25,.17,.12),INTERIOR,.04)
            for dx in [-.15,.15]: tube('Seat piping',[(x+dx,.63,z-.19),(x+dx,.65,z+.14),(x+dx,1.14,z+.10)],.006,TRIM if 'TRIM' in globals() else STEEL,6)
    for side in [-1,1]: panel('Inner door card',(side*half*.84,.76,.20),(.055,.37,1.47),CARPET,.035)

def coachwork(w,l,h,kind):
    """Rounded transverse sections, crowned roof and individually inset glazing."""
    half=w/2; end=l/2; belt=.99 if kind<2 else 1.22
    front=-.58 if kind<3 else -.94
    back=.73 if kind<3 else (1.78 if kind==3 else .36)
    rear=1.46 if kind in [1,2,3] else 1.02
    # The roof is crowned rather than a flat plane; glass meets its drip edge.
    verts=[]; faces=[]
    for iz in range(13):
        z=front+(back-front)*iz/12
        for ix in range(17):
            u=-1+ix/8
            y=h-.052*u*u-.018*math.cos(iz/12*math.tau)
            verts.append((u*half*.73,y,z))
    for iz in range(12):
        for ix in range(16):
            a=iz*17+ix; faces.append((a,a+1,a+18,a+17))
    roof=mesh('Crowned roof panel',verts,faces,PAINT,True)
    solid=roof.modifiers.new('Roof folded lip','SOLIDIFY'); solid.thickness=.028
    bpy.context.view_layer.objects.active=roof; bpy.ops.object.modifier_apply(modifier=solid.name)
    for front_screen,z0,z1,y0,y1 in [(True,-1.10,front,belt,h-.07),(False,back,rear,h-.07,belt)]:
        vs=[]; fs=[]
        for row in range(9):
            t=row/8; z=z0+(z1-z0)*t; y=y0+(y1-y0)*t
            hw=half*((.85 if front_screen else .73)*(1-t)+(.73 if front_screen else .85)*t)
            for col in range(17):
                u=-1+col/8
                vs.append((u*hw,y+.025*(1-u*u),z+(-1 if front_screen else 1)*.028*(1-u*u)))
        for row in range(8):
            for col in range(16):
                a=row*17+col; fs.append((a,a+1,a+18,a+17))
        glass=mesh('Laminated windscreen' if front_screen else 'Heated rear screen',vs,fs,GLASS,True)
        sol=glass.modifiers.new('Glass thickness','SOLIDIFY'); sol.thickness=.007
        bpy.context.view_layer.objects.active=glass; bpy.ops.object.modifier_apply(modifier=sol.name)
    for side in [-1,1]:
        a=(side*half*.85,belt,-1.1); b=(side*half*.73,h-.055,front)
        c=(side*half*.73,h-.055,back); d=(side*half*.85,belt,rear)
        low=(side*half*.85,belt,.13); high=(side*half*.73,h-.05,.13)
        for points in [[a,b,high,low],[low,high,c,d]]:
            glass=mesh('Recessed side window',points,[(0,1,2,3)],GLASS)
            sol=glass.modifiers.new('Window thickness','SOLIDIFY'); sol.thickness=.007
            bpy.context.view_layer.objects.active=glass; bpy.ops.object.modifier_apply(modifier=sol.name)
        for points,r,material in [([a,b],.047,PAINT),([b,c],.035,PAINT),([c,d],.060,PAINT),([a,low,d],.023,BLACK),([low,high],.044,BLACK)]:
            tube('Formed pillar and window seal',points,r,material,12)

def custom_lights(width,length,luxury):
    end=length*.5; half=width*.5
    for side in [-1,1]:
        x=side*half*.62
        points=[(x-side*.22,.77,-end-.075),(x,.79,-end-.09),(x+side*.19,.80,-end+.012)]
        tube('Swept LED signature',points,.012,LED,10)
        panel('Projector enclosure',(x,.728,-end-.04),(.43,.13,.045),CARPET,.033)
        for dx in [-.10,.08]: ellipsoid('Projector lens',(x+dx,.738,-end-.073),(.055,.036,.022),LED,n=20,m=12)
        tube('Rear light signature',[(x-side*.23,.75,end+.04),(x,.79,end+.06),(x+side*.19,.80,end+.015)],.018,RED,10)
    if luxury:
        tube('Grille chrome perimeter',[(-.47,.50,-end-.074),(-.54,.63,-end-.075),(-.46,.80,-end-.07),(.46,.80,-end-.07),(.54,.63,-end-.075),(.47,.50,-end-.074),(-.47,.50,-end-.074)],.014,CHROME,12)
        panel('Grille recess',(0,.65,-end-.065),(1.01,.27,.035),BLACK,.07)
        for x in [-.44+i*.055 for i in range(17)]: tube('Grille blade',[(x,.53,-end-.092),(x,.77,-end-.092)],.007,CHROME,6)
    else:
        panel('Lower air intake',(0,.43,-end-.085),(width*.66,.19,.028),BLACK,.035)
        for y in [.39,.44,.49]: tube('Intake louvre',[(-width*.31,y,-end-.108),(width*.31,y,-end-.108)],.009,STEEL,6)
    for side in [-1,1]:
        tube('Rocker sill',[(side*half,.30,-1.05),(side*half,.29,1.05)],.022,BLACK,8)
        tube('Exhaust outlet',[(side*.43,.25,end-.08),(side*.43,.25,end+.035)],.041,CHROME,12)

def emergency(name,w,l,h):
    end=l*.5
    if name=='police_cruiser':
        for side in [-1,1]:
            panel('White patrol door',(side*w*.5,.73,.16),(.018,.40,1.25),IVORY,.006)
        panel('Lightbar base',(0,h+.02,.12),(1.12,.05,.24),BLACK,.025)
        for side in [-1,1]: panel('Emergency lens',(side*.32,h+.09,.12),(.46,.10,.23),BLUE if side<0 else RED,.028)
        text('POLICE',(0,.69,-end-.055),.085,IVORY,(math.pi/2,0,math.pi))
        tube('Radio aerial',[(.55,h-.13,.70),(.55,h+.47,.70)],.005,BLACK,6)
    if name=='ambulance':
        panel('Medical box',(0,1.70,.96),(w*.97,2.17,l*.58),IVORY,.07)
        for side in [-1,1]:
            panel('Medical red stripe',(side*w*.49,1.52,.95),(.022,.25,l*.57),RED,.006)
            panel('Star of life vertical',(side*w*.501,2.1,1.0),(.025,.52,.13),BLUE,.009)
            panel('Star of life horizontal',(side*w*.505,2.1,1.0),(.025,.13,.52),BLUE,.009)
            for z in [-.1,2.1]: panel('Scene light',(side*w*.50,2.67,z),(.055,.12,.22),LED,.012)
        for side in [-1,1]:
            panel('Medical rear door',(side*w*.235,1.73,end+.005),(w*.46,1.85,.035),IVORY,.018)
            panel('Rear door window',(side*w*.235,2.15,end+.026),(.47,.49,.018),GLASS,.018)
            panel('Medical beacon',(side*.68,2.77,-.6),(.35,.12,.18),RED,.025)
        text('AMBULANCE',(0,2.5,end+.05),.17,BLUE)
    if name=='fire_engine':
        panel('Apparatus body',(0,1.61,1.12),(w*.96,1.92,l*.56),PAINT,.06)
        for side in [-1,1]:
            for z in [-.3,.9,2.1,3.1]:
                panel('Equipment shutter',(side*w*.488,1.49,z),(.025,1.13,.94),STEEL,.02)
                for y in [.99+i*.10 for i in range(11)]: tube('Shutter slat',[(side*w*.503,y,z-.43),(side*w*.503,y,z+.43)],.007,CHROME,5)
            tube('Ladder rail',[(side*.45,2.74,-.7),(side*.45,2.74,3.3)],.033,CHROME,10)
            if side==1:
                for z in [-.5+i*.3 for i in range(13)]: tube('Ladder rung',[(-.45,2.74,z),(.45,2.74,z)],.025,CHROME,8)
            panel('Fire beacon',(side*.7,h-.08,-.7),(.34,.13,.21),RED,.025)
        text('FIRE RESCUE',(0,1.2,end+.065),.17)
    if name=='school_bus':
        panel('Bus lower saloon',(0,1.01,.6),(w*.96,1.10,l*.79),PAINT,.09)
        for side in [-1,1]: panel('Bus window framing',(side*w*.475,2.08,.6),(.05,1.6,l*.79),PAINT,.018)
        panel('Rear bus wall',(0,1.84,4.21),(w*.96,1.9,.09),PAINT,.035)
        panel('Passenger roof',(0,2.87,.65),(w*.98,.20,l*.80),PAINT,.085)
        for side in [-1,1]:
            for z in [-1.6+i*.72 for i in range(9)]:
                panel('Bus passenger window',(side*w*.493,2.2,z),(.025,.69,.59),GLASS,.025)
            for y in [1.19,1.38]: tube('Bus rub rail',[(side*w*.501,y,-2.08),(side*w*.501,y,4.05)],.026,BLACK,8)
            for z in [-1.4,3.6]: panel('Bus warning lamp',(side*.87,2.82,z),(.16,.14,.035),ORANGE,.018)
        panel('School destination board',(0,2.75,-3.09),(1.5,.25,.05),BLACK,.02)
        text('SCHOOL BUS',(0,2.69,-3.13),.16,ORANGE,(math.pi/2,0,math.pi))
        for z in [-1.65+i*.75 for i in range(8)]:
            for side in [-1,1]: panel('Passenger bench',(side*.65,1.50,z),(.75,.65,.16),INTERIOR,.05)
        panel('Folding entrance',(w*.50,1.45,-2.38),(.025,1.9,.72),BLACK,.018)
        panel('Door glazing',(w*.517,1.72,-2.38),(.018,1.05,.58),GLASS,.012)

def heavy_cab(name,w,l,h):
    """Purpose-built commercial cab; wheel assemblies are retained from the chassis."""
    end=l/2; half=w/2
    for o in list(bpy.context.scene.objects):
        if o.type=='MESH' and o.parent is None: bpy.data.objects.remove(o,do_unlink=True)
    panel('Heavy ladder chassis',(0,.52,0),(w*.72,.25,l*.94),BLACK,.05)
    front=-end+.10
    if name=='fire_engine':
        lower=1.55; roof=2.89; screen_bottom=front+.06; screen_top=front+.44; back=-1.10
        panel('Crew cab lower pressing',(0,1.01,(front+back)/2),(w*.95,1.20,back-front),PAINT,.15)
    elif name=='ambulance':
        lower=1.35; roof=2.36; screen_bottom=front+.79; screen_top=front+1.22; back=-.96
        panel('Medical cab lower pressing',(0,.91,(front+back)/2),(w*.89,1.0,back-front),PAINT,.13)
        panel('Short sculpted bonnet',(0,1.20,front+.35),(w*.84,.22,.75),PAINT,.10)
    else:
        lower=1.57; roof=2.79; screen_bottom=-3.075; screen_top=-2.89; back=-1.7
        panel('Bus engine hood',(0,1.00,(front-3.06)/2),(w*.85,1.20,-3.06-front),PAINT,.14)
    cabin_width=half*.91
    corners=[(-cabin_width,lower,screen_bottom),(cabin_width,lower,screen_bottom),(-cabin_width*.97,roof-.08,screen_top),(cabin_width*.97,roof-.08,screen_top)]
    windshield=mesh('Commercial wraparound windshield',corners,[(0,1,3,2)],GLASS)
    solid=windshield.modifiers.new('Laminated glass','SOLIDIFY'); solid.thickness=.01
    bpy.context.view_layer.objects.active=windshield; bpy.ops.object.modifier_apply(modifier=solid.name)
    panel('Commercial cabin roof',(0,roof,(screen_top+back)/2),(w*.91,.12,back-screen_top),PAINT,.055)
    panel('Cab rear bulkhead',(0,(roof+lower)/2,back),(w*.91,roof-lower,.09),PAINT,.04)
    for side in [-1,1]:
        p=[(side*cabin_width,lower,screen_bottom),(side*cabin_width*.97,roof-.08,screen_top),(side*cabin_width*.97,roof-.08,back),(side*cabin_width,lower,back)]
        mesh('Commercial door glazing',p,[(0,1,2,3)],GLASS)
        for a,b in [(0,1),(1,2),(2,3),(0,3)]: tube('Cab pressed pillar',[p[a],p[b]],.047,PAINT,12)
        panel('Commercial door lower',(side*cabin_width,.98,(screen_bottom+back)*.5),(.075,.95,back-screen_bottom),PAINT,.045)
        tube('Door shut line',[(side*(cabin_width+.045),.55,back-.14),(side*(cabin_width+.045),lower-.08,back-.14)],.007,BLACK,6)
        panel('Recessed truck handle',(side*(cabin_width+.06),1.25,back-.32),(.06,.06,.22),BLACK,.018)
        tube('Mirror support',[(side*cabin_width,lower-.1,screen_bottom+.2),(side*(half+.16),lower+.12,screen_bottom+.04)],.025,BLACK,8)
        panel('Commercial mirror',(side*(half+.17),lower+.30,screen_bottom+.05),(.12,.35,.17),BLACK,.035)
        panel('Mirror glass',(side*(half+.17),lower+.30,screen_bottom+.14),(.10,.29,.018),CHROME,.012)
        panel('Cab access step',(side*(half-.1),.34,back-.50),(.35,.12,.85),STEEL,.025)
        panel('Headlight housing',(side*half*.70,.83,front-.055),(.40,.22,.05),BLACK,.035)
        for dx in [-.10,.10]: ellipsoid('Truck projector',(side*half*.70+dx,.85,front-.09),(.069,.068,.024),LED,n=16,m=10)
        panel('Amber side marker',(side*half*.94,1.0,front+.30),(.025,.06,.12),ORANGE,.01)
        panel('Rear brake lamp',(side*half*.77,.70,end-.03),(.22,.20,.04),RED,.025)
    tube('Windscreen center mullion',[(0,lower,screen_bottom-.006),(0,roof-.08,screen_top-.006)],.023,BLACK,10)
    panel('Heavy bumper',(0,.43,front-.06),(w*.99,.26,.22),CHROME,.055)
    panel('Radiator grille',(0,.98,front-.065),(w*.40,.35,.045),BLACK,.035)
    for y in [.85,.93,1.01,1.09]: tube('Radiator slat',[(-w*.19,y,front-.095),(w*.19,y,front-.095)],.014,STEEL,8)
    panel('Commercial license plate',(0,.46,front-.18),(.44,.14,.015),IVORY,.012)
    for x in [-.55,.55]:
        tube('Commercial wiper',[(x,lower+.02,screen_bottom-.025),(x+.19,lower+.30,screen_bottom+.10)],.012,BLACK,8)
        panel('Driver seat',(x,.89,(screen_bottom+back)*.5),(.51,.19,.54),INTERIOR,.06)
        panel('Driver backrest',(x,1.28,back-.24),(.51,.68,.14),INTERIOR,.06)
    panel('Commercial dashboard',(0,lower-.16,screen_bottom+.13),(w*.83,.25,.34),CARPET,.06)

def build(name):
    kind,cfg,color=CONFIGS[name]
    PAINT.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color,1)
    code=base_vehicle.replace('width,length,height,axle=configs[kind]','width,length,height,axle='+repr(cfg))
    if name in ['fire_engine','ambulance','school_bus']:
        radius={'fire_engine':.50,'ambulance':.46,'school_bus':.52}[name]
        code=code.replace('wheel_r=.33 if kind<2 else .38','wheel_r='+str(radius))
    if name=='fire_engine': code=code.replace('if kind==4:','if False:')
    exec(compile(code,'base_fleet_body','exec'),globals())
    vehicle(kind)
    if name in ['fire_engine','ambulance','school_bus']:
        for obj in list(bpy.context.scene.objects):
            if obj.name.startswith('Alloy spoke'): bpy.data.objects.remove(obj,do_unlink=True)
        for side in [-1,1]:
            for axle_z in [-cfg[3],cfg[3]]:
                wheel=bpy.data.objects[('WheelFront' if axle_z<0 else 'WheelRear')+('L' if side<0 else 'R')]
                before=set(bpy.context.scene.objects)
                x=side*(cfg[0]/2+.065)
                tube('Pressed steel wheel disc',[(x-side*.045,radius,axle_z),(x,radius,axle_z)],radius-.135,STEEL,40)
                for j in range(8):
                    a=j*math.tau/8; rr=(radius-.135)*.72
                    tube('Recessed wheel ventilation',[(x,radius+rr*math.sin(a),axle_z+rr*math.cos(a)),(x+side*.006,radius+rr*math.sin(a),axle_z+rr*math.cos(a))],.037,BLACK,12)
                    rr=.098
                    tube('Wheel lug',[(x,radius+rr*math.sin(a),axle_z+rr*math.cos(a)),(x+side*.021,radius+rr*math.sin(a),axle_z+rr*math.cos(a))],.018,CHROME,6)
                bpy.context.view_layer.update()
                for obj in set(bpy.context.scene.objects)-before:
                    transform=obj.matrix_world.copy(); obj.parent=wheel; obj.matrix_world=transform
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(('Lamp cluster','Grille fin','Raked windshield','Contoured roof','Side glazing','Window surround','B pillar','Tire tread')): bpy.data.objects.remove(o,do_unlink=True)
    w,l,h,axle=cfg
    if name in ['fire_engine','ambulance','school_bus']:
        heavy_cab(name,w,l,h)
    else:
        coachwork(w,l,h,kind)
        interior(w,l,h,kind)
        custom_lights(w,l,name=='executive_sedan')
    if name=='executive_sedan':
        panel('Panoramic roof',(0,h+.012,.12),(w*.61,.018,1.11),GLASS,.02)
        for side in [-1,1]: tube('Chrome beltline',[(side*w*.445,1.0,-1.02),(side*w*.445,1.0,1.03)],.008,CHROME,8)
    if name=='taxi_sedan':
        panel('Taxi roof sign',(0,h+.14,.15),(.57,.23,.22),ORANGE,.035)
        text('TAXI',(0,h+.10,.028),.13,BLACK,(math.pi/2,0,math.pi))
    emergency(name,w,l,h)
    if name in ['fire_engine','ambulance','school_bus']:
        for side in [-1,1]:
            for axle_z in [-axle,axle]:
                cutter=tube('Temporary wheel clearance',[(side*(w*.5-.27),radius,axle_z),(side*(w*.5+.30),radius,axle_z)],radius+.055,BLACK,48)
                bm=bmesh.new(); bm.from_mesh(cutter.data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(cutter.data); bm.free()
                for obj in list(bpy.context.scene.objects):
                    if obj.type!='MESH' or obj.parent or obj==cutter or not obj.data.materials or obj.data.materials[0] not in [PAINT,IVORY]: continue
                    positions=[obj.matrix_world@v.co for v in obj.data.vertices]
                    if min(p.z for p in positions)>radius*2+.07: continue
                    if not min(-p.y for p in positions)<axle_z+radius or not max(-p.y for p in positions)>axle_z-radius: continue
                    bpy.context.view_layer.objects.active=obj
                    cut=obj.modifiers.new('Pressed wheel arch opening','BOOLEAN'); cut.operation='DIFFERENCE'; cut.object=cutter
                    bpy.ops.object.modifier_apply(modifier=cut.name)
                bpy.data.objects.remove(cutter,do_unlink=True)
                tube('Commercial wheel arch lip',[(side*(w*.5+.015),radius+(radius+.068)*math.sin(j*math.pi/24),axle_z+(radius+.068)*math.cos(j*math.pi/24)) for j in range(25)],.025,BLACK,8)
    # Preserve articulated wheel pivots and consolidate every other surface.
    real_export(name)
    for o in bpy.context.scene.objects:
        if o.type=='MESH':
            bpy.context.view_layer.objects.active=o; bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=.015); bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'source',name+'.blend'))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+'.glb'),export_format='GLB',export_apply=True)
    for level,ratio in [(1,.42),(2,.45)]:
        for o in bpy.context.scene.objects:
            if o.type=='MESH' and len(o.data.polygons)>30:
                bpy.context.view_layer.objects.active=o
                mod=o.modifiers.new('Fleet LOD','DECIMATE'); mod.ratio=ratio; bpy.ops.object.modifier_apply(modifier=mod.name)
                o.data.validate(clean_customdata=False)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+'_lod%d.glb'%level),export_format='GLB',export_apply=True)
    REPORT[name]['dimensions']=cfg[:3]

names=[sys.argv[sys.argv.index('--')+1]] if '--' in sys.argv else list(CONFIGS)
for name in names: build(name)
with open(os.path.join(OUT,'source','vehicles_manifest.json'),'w') as f: json.dump(REPORT,f,indent=2)
