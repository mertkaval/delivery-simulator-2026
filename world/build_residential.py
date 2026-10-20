"""Original residential exterior kit. Run with Blender --background --python this_file.
Coordinates below are in Godot metres (Y up, front +Z). Export keeps that convention.
"""
import bpy, math, os
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'residential')
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, 'source'), exist_ok=True)
open(os.path.join(OUT, 'source', '.gdignore'), 'w').close()

def material(name, color, rough=.75, metal=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    return m

def point(p): return (p[0], -p[2], p[1])

def box(name, p, d, mat, bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=point(p))
    o = bpy.context.object
    o.name = name
    o.scale = (d[0], d[2], d[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if bevel:
        mod = o.modifiers.new('Soft construction edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
        o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o

def beam(name, a, b, width, mat):
    pa, pb = Vector(point(a)), Vector(point(b))
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=width, depth=(pb-pa).length, location=(pa+pb)/2)
    o=bpy.context.object
    o.name=name
    o.rotation_mode='QUATERNION'
    o.rotation_quaternion=(pb-pa).to_track_quat('Z','Y')
    o.data.materials.append(mat)

for variant in range(3):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    siding=material('Painted cedar', [(0.40,.51,.46),(.62,.51,.40),(.40,.48,.56)][variant])
    trim=material('Warm ivory trim', (.83,.80,.69))
    roof=material('Slate shingles', (.12,.15,.17))
    brick=material('Chimney brick', (.36,.21,.15))
    mortar=material('Mortar', (.48,.43,.36))
    glass=material('Recessed window glass', (.12,.22,.28), .17, .32)
    dark=material('Window reveal', (.08,.11,.12))
    wood=material('Cedar porch', (.40,.27,.16))
    metal=material('Gutters and hardware', (.19,.23,.24), .36, .65)
    door=material('Painted front door', [(.16,.26,.28),(.29,.17,.13),(.26,.30,.21)][variant])
    concrete=material('Foundation', (.40,.42,.40))
    curtain=material('Interior linen', (.65,.61,.49))
    box('Foundation', (0,.18,-3),(10.12,.36,8.12),concrete)
    box('House shell',(0,2.2,-3),(10,4.4,8),siding)
    # Real overlapping boards on all four elevations.
    for row in range(22):
        y=.48+row*.177
        for z in [-7.025,1.025]:
            box('Lap siding',(0,y,z),(10,.17,.055),siding,.006)
        for x in [-5.025,5.025]:
            box('Side lap siding',(x,y,-3),(.055,.17,8),siding,.006)
    for x in [-4.94,4.94]:
        for z in [-7.065,1.065]: box('Corner board',(x,2.3,z),(.16,4.2,.10),trim)
    # Different roof pitches and facade treatments distinguish the three homes.
    rise = [2.0, 2.8, 1.5][variant]
    peak = 4.35 + rise
    if variant == 1:
        for z in [-7.07,1.07]:
            box('Brick wainscot',(0,.66,z),(10,1.0,.08),brick)
            box('Stone water table',(0,1.2,z),(10.15,.12,.15),concrete)
        for x in [-5.07,5.07]:
            box('Brick wainscot',(x,.66,-3),(.08,1.0,8),brick)
    # Closed gables and a continuous pitched roof.
    for z in [-7.03,1.03]:
        verts=[point((-5,4.35,z)),point((5,4.35,z)),point((0,peak,z))]
        mesh=bpy.data.meshes.new('Gable'); mesh.from_pydata(verts,[],[(0,1,2) if z > 0 else (2,1,0)]); mesh.update()
        o=bpy.data.objects.new('Closed gable',mesh); bpy.context.collection.objects.link(o); o.data.materials.append(siding)
    angle=math.atan2(rise,5)
    slope_length=5.45/math.cos(angle)
    for side in [-1,1]:
        o=box('Roof slope',(side*2.7,peak-2.7*rise/5,-3),(slope_length,.18,9),roof)
        o.rotation_euler.y=side*angle
        for z in [-7.52,1.52]:
            o=box('Rake fascia',(side*2.7,peak-2.7*rise/5-.03,z),(slope_length,.19,.14),trim)
            o.rotation_euler.y=side*angle
        box('Eave fascia',(side*5.42,4.23,-3),(.14,.24,9.12),trim)
        box('Rain gutter',(side*5.50,4.30,-3),(.16,.12,9.10),metal)
        beam('Downspout',(side*5.15,.35,-6.8),(side*5.15,4.27,-6.8),.045,metal)
        for row in range(12):
            x=side*(.16+row*.45)
            box('Shingle course',(x,peak+.10-abs(x)*rise/5,-3),(.025,.018,8.9),roof,.002)
    box('Ridge cap',(0,peak+.10,-3),(.20,.13,9.1),metal)
    # Deep reveals, casing, transoms, sills and curtains on front and sides.
    def window(cx,cy,cz,side=False):
        before=set(bpy.context.scene.objects)
        box('Window shadow',(cx,cy,cz),(2.05,1.75,.13),dark)
        box('Glazing',(cx,cy,cz+.08),(1.80,1.49,.05),glass)
        for dx in [-.96,.96]: box('Window casing',(cx+dx,cy,cz+.15),(.12,1.80,.14),trim)
        for dy in [-.84,.84]: box('Window casing',(cx,cy+dy,cz+.15),(2.05,.12,.14),trim)
        box('Mullion',(cx,cy,cz+.17),(.055,1.55,.09),trim)
        box('Transom',(cx,cy,cz+.17),(1.85,.065,.09),trim)
        box('Drip sill',(cx,cy-.93,cz+.2),(2.23,.10,.35),trim)
        for dx in [-.68,.68]: box('Curtain edge',(cx+dx,cy,cz+.115),(.22,1.42,.015),curtain,.005)
        if side:
            for o in set(bpy.context.scene.objects)-before:
                # Rotate front-window assembly around origin into side elevation.
                o.location=Vector((-o.location.y,o.location.x,o.location.z))
                o.rotation_euler.z+=math.pi/2
    for x in [-3,3]: window(x,2.35,1.09)
    if variant == 2:
        for x in [-3,3]:
            for side in [-1,1]:
                box('Cedar shutters',(x+side*1.28,2.35,1.16),(.38,1.85,.12),wood)
                for row in range(10): box('Shutter slats',(x+side*1.28,1.56+row*.17,1.24),(.35,.06,.05),trim,.005)
    for z in [-4.8,-1.2]:
        # Assembly rotation maps front +Z onto right +X.
        window(-z,2.35,5.09,True)
    # Attic vent with separate slats.
    box('Attic vent',(0,5.05,1.08),(1.05,.63,.12),dark)
    for y in range(5): box('Vent louver',(0,4.79+y*.13,1.17),(1.10,.065,.12),trim)
    box('Door slab',(0,1.13,1.16),(1.30,2.26,.20),door)
    for x in [-.72,.72]: box('Door casing',(x,1.19,1.22),(.13,2.38,.18),trim)
    box('Door lintel',(0,2.38,1.22),(1.58,.13,.18),trim)
    for y in [.57,1.48]:
        for x in [-.31,.31]: box('Door raised panel',(x,y,1.275),(.48,.65,.04),door)
    beam('Brass door pull',(.43,1.02,1.31),(.43,1.18,1.31),.028,metal)
    # Open, ground-level porch keeps existing delivery interaction accessible.
    box('Porch deck',(0,.055,2.45),(3.75,.11,2.7),wood)
    for n in range(19): box('Deck seam',(-1.8+n*.2,.113,2.45),(.014,.008,2.68),dark,.001)
    box('Porch canopy',(0,2.89,2.35),(4.15,.19,3.30),roof)
    box('Canopy fascia',(0,2.82,4.02),(4.25,.24,.12),trim)
    for x in [-1.8,1.8]:
        box('Porch column',(x,1.4,3.70),(.18,2.8,.18),trim)
        box('Column plinth',(x,.25,3.70),(.30,.38,.30),concrete)
        box('Porch handrail',(x,.98,2.50),(.10,.10,2.25),wood)
        for z in [1.5,1.85,2.2,2.55,2.9,3.25,3.55]: box('Porch baluster',(x,.56,z),(.045,.78,.045),trim,.005)
    box('Chimney',(3,5.30,-5),(.76,2.2,.76),mortar)
    for row in range(15):
        for j in range(3):
            x=2.68+j*.24
            for z in [-5.39,-4.61]: box('Brick',(x,4.27+row*.14,z),(.225,.125,.035),brick,.004)
    box('Chimney cap',(3,6.46,-5),(.94,.13,.94),concrete)
    beam('Chimney flue',(3,6.46,-5),(3,6.7,-5),.20,metal)
    box('Porch light backplate',(1.08,2.04,1.18),(.19,.34,.13),metal)
    box('Porch light glass',(1.08,2.04,1.29),(.14,.24,.11),curtain)
    # Join by material: a handful of draw calls per house instead of hundreds.
    for mat in [siding,trim,roof,brick,mortar,glass,dark,wood,metal,door,concrete,curtain]:
        bpy.ops.object.select_all(action='DESELECT')
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials and o.data.materials[0]==mat]
        for o in objects: o.select_set(True)
        if objects:
            bpy.context.view_layer.objects.active=objects[0]
            bpy.ops.object.join()
            bpy.context.object.name=mat.name.split('.')[0]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'source',f'house_{variant}.blend'))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,f'house_{variant}.glb'),export_format='GLB',export_apply=True)
print('RESIDENTIAL KIT COMPLETE')

