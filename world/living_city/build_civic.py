"""Civic architecture and landscape kit, metres, front +Z. Reproducible Blender sources."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
source=open(os.path.join(HERE,'..','build_city_assets.py'),encoding='utf-8-sig').read()
exec(compile(source.split('\ndef vehicle(')[0].replace("'city_assets'","'assets'"),'civic_helpers','exec'),globals())
GLAZE=mat('CivicGlazing',(.085,.18,.22),.19,.3)
FRAME=mat('CivicFrames',(.065,.095,.11),.35,.7)
CLAY=mat('CivicBrick',(.40,.21,.13),.88)
CREAM=mat('CivicStone',(.67,.68,.62),.85)
BLUE=mat('CivicBlue',(.035,.22,.35),.42)
WHITE=mat('SignWhite',(.87,.88,.79),.5)
SOIL=mat('PlantingSoil',(.085,.055,.028),1)
GREEN=mat('CycleLane',(.07,.31,.23),.94)
PETAL=mat('FlowerGold',(.86,.51,.07),.82)
PURPLE=mat('FlowerLavender',(.41,.22,.53),.86)

def lettering(words,p,size,material=WHITE):
    curve=bpy.data.curves.new('Raised civic lettering','FONT'); curve.body=words; curve.size=size; curve.align_x='CENTER'; curve.extrude=.002
    obj=bpy.data.objects.new(words,curve); bpy.context.collection.objects.link(obj); obj.location=P(p); obj.rotation_euler.x=math.pi/2; obj.data.materials.append(material)
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj; bpy.ops.object.convert(target='MESH'); obj.select_set(False)

def window(x,y,z,w=2.3,h=1.8):
    panel('Deep reveal',(x,y,z),(w+.18,h+.18,.17),FRAME,.025)
    panel('Double glazing',(x,y,z+.095),(w,h,.025),GLAZE,.008)
    panel('Stone sill',(x,y-h/2-.08,z+.13),(w+.32,.12,.38),CREAM,.02)
    panel('Glazing mullion',(x,y,z+.12),(.05,h,.06),FRAME,.008)

def facade(w,d,floors,material):
    height=floors*3.6
    panel('Rear wall',(0,height/2,-d),(w,height,.32),material,.035)
    for side in [-1,1]: panel('Return wall',(side*(w/2-.15),height/2,-d/2),(.3,height,d),material,.035)
    for level in range(floors):
        y=level*3.6
        # Floor edge and spandrel course 2 cm proud of the return walls at both ends (their end
        # faces lay in the return walls' outer planes).
        # ... and 2 cm proud of the facade: its front face lay in the masonry piers' face plane.
        panel('Floor edge',(0,y+.13,-d/2+.02),(w+.04,.26,d),CREAM,.025)
        for j in range(int(w/3)):
            x=-w/2+1.5+j*3
            if level==0 and abs(x)<3.1: continue
            panel('Masonry pier',(x,y+1.8,-.17),(2.98,3.4,.34),material,.02)
            window(x,y+2.1,.03,2.2,1.9)
        panel('Spandrel course',(0,y+3.35,0),(w+.04,.43,.38),CREAM,.02)
    # 3 mm above the wall heads: its underside lay on their tops (both drawn double-sided).
    panel('Insulated roof',(0,height+.123,-d/2),(w+.45,.24,d+.45),CREAM,.025)
    for x in [-w/2,w/2]: panel('Parapet return',(x,height+.43,-d/2),(.22,.55,d),CREAM,.018)
    for z in [0,-d]: panel('Parapet coping',(0,height+.45,z),(w,.58,.22),CREAM,.018)
    for x in [-w*.25,w*.25]:
        panel('HVAC curb',(x,height+.45,-d*.65),(2.5,.6,1.8),FRAME,.04)
        for dx in [-.6,.6]: torus('Rooftop fan',(x+dx,height+.79,-d*.65),.44,.035,STEEL,'y',24,6)
    # Ground vestibule is open and furnished; collision supplied in Godot.
    panel('Lobby back',(0,1.8,-5),(6,3.6,.18),CREAM,.02)
    for side in [-1,1]: panel('Lobby partition',(side*3,1.8,-2.5),(.18,3.6,5),CREAM,.02)
    panel('Reception desk',(0,.6,-3.65),(3.1,1.2,.72),WOOD,.06)
    panel('Reception stone top',(0,1.23,-3.65),(3.3,.10,.85),CREAM,.02)
    panel('Reception monitor',(.75,1.52,-3.75),(.45,.35,.06),FRAME,.025)
    for side in [-1,1]:
        panel('Entrance jamb',(side*2.95,1.65,.08),(.11,3.3,.2),FRAME,.01)
        panel('Vestibule glazing',(side*2.30,1.65,.10),(1.1,3.2,.04),GLAZE,.008)
    panel('Entrance lintel',(0,3.25,.08),(6,.16,.20),FRAME,.01)

def civic(kind):
    clear()
    if kind=='hospital':
        facade(42,24,4,CREAM)
        panel('Blue entrance fascia',(0,3.75,.8),(14,.70,1.9),BLUE,.05)
        lettering('MERIDIAN GENERAL',(0,3.57,1.78),.54)
        lettering('HOSPITAL',(0,12.3,.27),.90,BLUE)
        for x in [-19,19]:
            panel('Vertical sun screen',(x,7.4,.38),(.38,13.8,.7),BLUE,.035)
        panel('Ambulance canopy',(12,3.45,4.0),(15,.28,8),CREAM,.03)
        for x in [5,19]: tube('Canopy steel column',[(x,0,7.3),(x,3.4,7.3)],.095,FRAME,12)
        lettering('EMERGENCY',(12,3.02,7.99),.50,RED)
        for x in [10,14]:
            panel('Accessible bench',(x,.48,1.8),(2,.12,.48),WOOD,.03)
            panel('Bench back',(x,.78,1.99),(2,.55,.10),WOOD,.025)
    elif kind=='fire_station':
        # Three clear vehicle bays, deep apparatus hall and attached crew rooms.
        w,d=30,23
        panel('Station rear',(0,4.3,-d),(w,8.6,.35),CLAY,.03)
        for x in [-15,15]: panel('Station return',(x,4.3,-11.5),(.35,8.6,23),CLAY,.03)
        panel('Hall floor',(0,.10,-11.5),(30,.20,23),CREAM,.02)
        for x in [-14,-4.7,4.7,14]: panel('Garage brick pier',(x,2.8,-.15),(.85,5.6,.6),CLAY,.03)
        panel('Crew floor edge',(0,5.7,-11.48),(30,.30,23),CREAM,.02)   # 2 cm proud of the crew facade
        panel('Crew facade',(0,7.2,-.2),(30,2.8,.4),CLAY,.03)
        for x in [-12,-8,-4,0,4,8,12]: window(x,7.3,.08,2.5,1.7)
        for x in [-9.3,0,9.3]:
            panel('Raised sectional door',(x,5.18,-.15),(8.3,.65,.20),FRAME,.025)
            for y in [4.95,5.15,5.35]: panel('Door horizontal rib',(x,y,.0),(8.3,.025,.025),STEEL,.005)
            for side in [-1,1]: tube('Garage guide rail',[(x+side*4.3,.1,-.12),(x+side*4.3,5.5,-.12)],.035,STEEL,8)
        panel('Station roof',(0,8.753,-11.5),(30.7,.3,23.7),FRAME,.03)   # 3 mm above the wall heads
        lettering('FIRE & RESCUE  /  STATION 04',(0,6.05,.23),.53)
        for x in [-11,-7]:
            panel('Equipment locker',(x,1.15,-21),(1.4,2.3,.6),RED,.04)
            for y in [.5,.65,.8,1.8,1.95]: panel('Locker louvre',(x,y,-20.67),(1.1,.03,.04),FRAME,.005)
    elif kind=='school':
        facade(48,22,2,CLAY)
        panel('School porch',(0,3.3,2),(12,.30,4.5),FRAME,.05)
        for x in [-5.5,5.5]: tube('Porch column',[(x,0,3.7),(x,3.3,3.7)],.12,BLUE,12)
        lettering('MERIDIAN COMMUNITY SCHOOL',(0,6.9,.31),.65)
        panel('Gymnasium',(17,4.4,-32),(14,8.8,18),CLAY,.06)
        for x in [12,15,18,21]: window(x,7.0,-22.9,1.8,1.4)
        panel('Gym roof',(17,8.9,-32),(14.5,.28,18.5),FRAME,.04)
        for x in [-12,-6,6,12]:
            panel('School planter',(x,.34,2.2),(3,.68,1.2),CREAM,.04)
            panel('Planter soil',(x,.68,2.2),(2.8,.025,1.0),SOIL,.005)
    finish(kind)

def flowerbed():
    clear(); R.seed(190)
    panel('Rain garden edging',(0,.08,0),(3.4,.16,1.35),CREAM,.045)
    panel('Mulched planting bed',(0,.17,0),(3.18,.08,1.15),SOIL,.028)
    for i in range(46):
        x=R.uniform(-1.46,1.46); z=R.uniform(-.48,.48); y=R.uniform(.40,.76)
        tube('Flower stem',[(x,.18,z),(x+.03,y,z-.02)],.009,LEAF,5)
        for side in [-1,1]:
            mesh('Lanceolate leaf',[(x,y*.55,z),(x+side*.17,y*.68,z+.05),(x+side*.24,y*.66,z),(x+side*.12,y*.56,z-.035)],[(0,1,2,3)],LEAF)
        for j in range(6):
            a=j*math.tau/6
            p=Vector((x+.03,y,z-.02)); u=Vector((math.cos(a),.16,math.sin(a))); v=Vector((-math.sin(a),0,math.cos(a)))
            mesh('Curved petal',[p,p+u*.065-v*.033,p+u*.12+Vector((0,.015,0)),p+u*.065+v*.033],[(0,1,2,3)],PETAL if i%3 else PURPLE)
        ellipsoid('Flower seed head',(x+.03,y+.008,z-.02),(.03,.018,.03),SOIL,8,5)
    finish('rain_garden')

def signs():
    for kind,words,color,shape in [('stop','STOP',RED,'octagon'),('speed','30',WHITE,'square'),('school_zone','SCHOOL\n30',ORANGE if 'ORANGE' in globals() else PETAL,'square'),('cycle_sign','BIKES\nONLY',BLUE,'square'),('hospital_sign','H',BLUE,'square'),('taxi_sign','TAXI',BLUE,'square')]:
        clear(); tube('Galvanized sign pole',[(0,0,0),(0,2.8,0)],.032,STEEL,10)
        if shape=='octagon':
            verts=[(0,2.4,.06)]+[(.40*math.cos(i*math.tau/8+math.pi/8),2.4+.40*math.sin(i*math.tau/8+math.pi/8),.06) for i in range(8)]
            mesh('Octagonal reflective sign',verts,[(0,j+1,(j+1)%8+1) for j in range(8)],color)
            tube('Reflective sign rim',verts[1:]+[verts[1]],.014,WHITE,6)
        else: panel('Reflective sign face',(0,2.35,.06),(.68,.85,.035),color,.025)
        lettering(words,(0,2.29 if kind=='stop' else 2.23,.088),.21 if '\n' not in words else .135,FRAME if kind in ['speed','school_zone'] else WHITE)
        finish(kind)

def cycle_kit():
    clear(); panel('Coloured asphalt wearing course',(0,.008,0),(2.0,.016,6),GREEN,.0)
    # Boundary lines 1 cm short of the tile ends: their end faces lay in the tile's end faces.
    for x in [-.96,.96]: panel('Lane boundary',(x,.019,0),(.07,.008,5.98),WHITE,0)
    finish('cycle_lane')
    clear()
    for z in [-.48,.48]:
        # Bicycle marking lies flat, +Y normal.
        torus('Bicycle stencil wheel',(0,.018,z),.28,.018,WHITE,'y',20,4)
    for a,b in [((0,.02,-.48),(.18,.02,-.1)),((.18,.02,-.1),(0,.02,.48)),((0,.02,.48),(-.17,.02,.12)),((-.17,.02,.12),(.18,.02,-.1)),((-.17,.02,.12),(0,.02,-.48))]: tube('Bicycle stencil frame',[a,b],.021,WHITE,4)
    tube('Direction arrow',[(-.25,.02,-1.1),(0,.02,-1.5),(.25,.02,-1.1)],.03,WHITE,4)
    finish('cycle_stencil')
    clear(); panel('Lane separator',(0,.08,0),(.22,.16,1.8),CREAM,.055)
    tube('Flexible delineator',[(0,.13,0),(0,.9,0)],.033,WHITE,8)
    tube('Reflective band',[(0,.68,0),(0,.8,0)],.034,PETAL,8)
    finish('cycle_separator')
    clear()
    mesh('Grassed rain garden surface',[(-5,.012,-5),(5,.012,-5),(5,.012,5),(-5,.012,5)],[(0,3,2,1)],mat('CivicGrass',(.20,.28,.09),1))
    finish('garden_lawn')

def finish(name):
    export(name)
    for o in bpy.context.scene.objects:
        if o.type=='MESH':
            bpy.context.view_layer.objects.active=o; bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=.014); bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'source',name+'.blend'))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+'.glb'),export_format='GLB',export_apply=True)
    for level,ratio in [(1,.45),(2,.40)]:
        for o in bpy.context.scene.objects:
            if o.type=='MESH' and len(o.data.polygons)>30:
                bpy.context.view_layer.objects.active=o; mod=o.modifiers.new('Civic distance LOD','DECIMATE'); mod.ratio=ratio; bpy.ops.object.modifier_apply(modifier=mod.name); o.data.validate(clean_customdata=False)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+'_lod%d.glb'%level),export_format='GLB',export_apply=True)

for name in ['hospital','fire_station','school']: civic(name)
flowerbed(); signs(); cycle_kit()
with open(os.path.join(OUT,'source','civic_manifest.json'),'w') as f: json.dump(REPORT,f,indent=2)
