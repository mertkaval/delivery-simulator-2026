"""Publish preview of the baked material library: every material on a shader sphere and a 2 m wall
panel, lit by a sun and sky, EEVEE.

    blender --background --factory-startup --python tools/cityforge/qa_materials.py -- <out_dir>

Reads assets/cityforge/materials/<name>_albedo/_normal/_orm and builds the same image-based
material Godot uses (albedo, OpenGL normal, ORM split into AO / roughness / metallic).
"""
import json, math, os, sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LIB = os.path.join(ROOT, "assets", "cityforge", "materials")
names = sorted(json.load(open(os.path.join(LIB, "library.json"))).keys())
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        pass
sc.render.resolution_x, sc.render.resolution_y = 2400, 1350
sc.eevee.taa_render_samples = 64
world = bpy.data.worlds.new("Preview")
sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.5, 0.62, 0.8, 1.0)
bg.inputs[1].default_value = 1.1
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 4.5
sun.data.angle = math.radians(2.5)
sun.rotation_euler = (math.radians(48), math.radians(12), math.radians(-35))
sc.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def material(name):
    m = bpy.data.materials.new("PV_" + name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    def img(suffix, colour):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(LIB, name + suffix), check_existing=True)
        n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        n.projection = "BOX"
        n.projection_blend = 0.2
        nt.links.new(mp.outputs[0], n.inputs["Vector"])
        return n
    a = img("_albedo.jpg", True)
    nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    o = img("_orm.jpg", False)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(o.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    ao = nt.nodes.new("ShaderNodeMix"); ao.data_type = "RGBA"; ao.blend_type = "MULTIPLY"; ao.inputs[0].default_value = 0.7
    nt.links.new(a.outputs["Color"], ao.inputs[6]); nt.links.new(sep.outputs[0], ao.inputs[7])
    nt.links.new(ao.outputs[2], bsdf.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nn = img("_normal.png", False)
    nt.links.new(nn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


cols = 7
for k, name in enumerate(names):
    m = material(name)
    x, y = (k % cols) * 3.2, -(k // cols) * 3.6
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.75, segments=48, ring_count=24, location=(x, y, 0.75))
    ball = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(m)
    me = bpy.data.meshes.new("panel")
    me.from_pydata([(x - 1.3, y + 1.0, 0), (x + 1.3, y + 1.0, 0), (x + 1.3, y + 1.0, 2.0), (x - 1.3, y + 1.0, 2.0)], [], [(0, 1, 2, 3)])
    panel = bpy.data.objects.new("panel_" + name, me)
    sc.collection.objects.link(panel)
    panel.data.materials.append(m)
    me2 = bpy.data.meshes.new("floor")
    me2.from_pydata([(x - 1.4, y - 1.6, 0), (x + 1.4, y - 1.6, 0), (x + 1.4, y + 1.0, 0), (x - 1.4, y + 1.0, 0)], [], [(0, 1, 2, 3)])
    fl = bpy.data.objects.new("floor_" + name, me2)
    sc.collection.objects.link(fl)
    fl.data.materials.append(m)
    # a label
    bpy.ops.object.text_add(location=(x - 1.2, y - 1.55, 0.02))
    t = bpy.context.active_object
    t.data.body = name
    t.data.size = 0.28
    t.rotation_euler = (0, 0, 0)
rows = (len(names) + cols - 1) // cols
cx, cy = (cols - 1) * 3.2 / 2, -(rows - 1) * 3.6 / 2
eye = Vector((cx, cy - rows * 4.4 - 4.0, rows * 3.6 + 3.5))
cam.location = eye
cam.rotation_euler = (Vector((cx, cy, 0.8)) - eye).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 40
sc.render.filepath = os.path.join(OUT, "materials_preview.png")
bpy.ops.render.render(write_still=True)
# close-ups of four
for name in ("brick_painted", "brick_red", "terracotta", "cedar_planks"):
    if name not in names: continue
    k = names.index(name)
    x, y = (k % cols) * 3.2, -(k // cols) * 3.6
    eye = Vector((x - 1.6, y - 3.4, 1.9))
    cam.location = eye
    cam.rotation_euler = (Vector((x, y + 0.2, 0.8)) - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 45
    sc.render.filepath = os.path.join(OUT, "material_%s.png" % name)
    bpy.ops.render.render(write_still=True)
print("PREVIEW", len(names), "materials")
