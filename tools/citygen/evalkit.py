"""Shared helpers for the tool-evaluation scenes: enable add-ons, scene stats, quick EEVEE renders."""
import bpy, addon_utils, math, os, time
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
os.makedirs(OUT, exist_ok=True)


def enable(*mods):
    for m in mods:
        addon_utils.enable(m, default_set=True)


def stats(objects=None):
    objs = objects if objects is not None else [o for o in bpy.context.scene.objects]
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    meshes = 0
    for o in objs:
        if o.type != "MESH": continue
        meshes += 1
        ev = o.evaluated_get(dg)
        tris += sum(len(p.vertices) - 2 for p in ev.data.polygons)
    mats = {s.material.name for o in objs if o.type == "MESH" for s in o.material_slots if s.material}
    return {"objects": len(objs), "meshes": meshes, "tris": tris, "materials": len(mats)}


def bounds(objects):
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in objects:
        if o.type not in {"MESH", "CURVE"}: continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def light_scene(strength=3.0):
    sc = bpy.context.scene
    if not sc.world: sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.8, 1); bg.inputs[1].default_value = 0.8
    if not any(o.type == "LIGHT" and o.data.type == "SUN" for o in sc.objects):
        sun = bpy.data.objects.new("EvalSun", bpy.data.lights.new("EvalSun", "SUN"))
        sun.data.energy = strength
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
        sc.collection.objects.link(sun)


def render(name, eye, target, lens=35, res=(1280, 720), clip_end=5000.0):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("EvalCam") or bpy.data.objects.new("EvalCam", bpy.data.cameras.new("EvalCam"))
    if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
    cam.data.lens = lens; cam.data.clip_end = clip_end; cam.data.clip_start = 0.1
    cam.location = eye
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


class Timer:
    def __enter__(self): self.t = time.time(); return self
    def __exit__(self, *a): self.s = time.time() - self.t
