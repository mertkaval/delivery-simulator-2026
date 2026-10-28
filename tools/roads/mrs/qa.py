"""QA renders (EEVEE) and contact sheets for validation."""
import bpy, math, os
from mathutils import Vector
from .nodes import depsgraph, set_scene, MRS, scene as _scene


def ensure_camera_and_sun(scene):
    cam = bpy.data.objects.get(MRS + "QACam")
    if cam is None:
        cam = bpy.data.objects.new(MRS + "QACam", bpy.data.cameras.new(MRS + "QACam"))
    if cam.name not in scene.collection.objects: scene.collection.objects.link(cam)
    sun = bpy.data.objects.get(MRS + "QASun")
    if sun is None:
        ld = bpy.data.lights.new(MRS + "QASun", "SUN"); ld.energy = 3.5; ld.angle = math.radians(2.0)
        sun = bpy.data.objects.new(MRS + "QASun", ld); sun.rotation_euler = (math.radians(52), 0, math.radians(-35))
    if sun.name not in scene.collection.objects: scene.collection.objects.link(sun)
    scene.camera = cam
    if scene.world is None: scene.world = bpy.data.worlds.get(MRS + "World") or bpy.data.worlds.new(MRS + "World")
    w = scene.world; w.use_nodes = True
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg: bg.inputs[0].default_value = (0.55, 0.68, 0.85, 1); bg.inputs[1].default_value = 1.0
    return cam, sun


def look(cam, eye, target, lens=35.0):
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens; cam.data.clip_end = 5000.0


def road_frame(road, t):
    """Position and unit tangent of the road's curve at parameter t (0..1), from the evaluated mesh
    centre line (lat ~ 0), so the camera follows the terrain-conformed height."""
    dg = depsgraph()
    me = road.evaluated_get(dg).to_mesh()
    lat = me.attributes["lat"].data; along = me.attributes["along"].data
    seen = {}
    for i in range(len(me.vertices)):
        if abs(lat[i].value) < 0.3:
            key = round(along[i].value, 2)
            if key not in seen: seen[key] = me.vertices[i].co.copy()       # one sample per station (strips share 'along')
    pts = sorted(seen.items())
    road.evaluated_get(dg).to_mesh_clear()
    if len(pts) < 2: return Vector((0, 0, 0)), Vector((0, 1, 0))
    i = max(1, min(len(pts) - 1, int(t * (len(pts) - 1))))
    p = road.matrix_world @ pts[i][1]; q = road.matrix_world @ pts[i - 1][1]
    return p, (p - q).normalized()


def road_view(path, road, t=0.3, lateral=2.0, height=1.7, ahead=40.0, lens=30.0, scene=None, **kw):
    """Street-level render standing on the road at parameter t, looking ahead along it."""
    p, d = road_frame(road, t)
    side = d.cross(Vector((0, 0, 1))).normalized()
    eye = p + side * lateral + Vector((0, 0, height))
    target = p + d * ahead + Vector((0, 0, height * 0.5))
    return render(path, eye, target, lens, scene=scene, **kw)


def render(path, eye, target, lens=35.0, res=(1280, 720), samples=24, scene=None):
    scene = scene or _scene()
    cam, _ = ensure_camera_and_sun(scene)
    look(cam, eye, target, lens)
    r = scene.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = samples
    r.resolution_x, r.resolution_y = res; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.filepath = os.path.abspath(path)
    os.makedirs(os.path.dirname(r.filepath), exist_ok=True)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    return r.filepath


def sheet(paths, out, cols=2, label=True):
    """Contact sheet with PIL if available (falls back to the first image)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return paths[0]
    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (w * cols, h * rows), (30, 30, 30))
    for i, (p, im) in enumerate(zip(paths, ims)):
        S.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
        if label: ImageDraw.Draw(S).text(((i % cols) * w + 8, (i // cols) * h + 6), os.path.splitext(os.path.basename(p))[0], fill=(255, 230, 0))
    S.save(out); return out
