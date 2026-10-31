"""procmat.rig: a headless preview scene for procedural materials (its own scene "PM_Rig"; other scenes untouched).

    sc = rig.scene(engine="EEVEE", samples=64, res=(800, 800), hdri="city", strength=1.0, rotation=0.0)
    ob = rig.icosphere(sc)                    # also plane(), cube(), road_strip() (7 m x 20 m, UVs in metres)
    rig.assign(ob, mat); rig.camera(sc, "front", ob); rig.render("out.png", scene=sc)
    rig.preview(mat, out_dir, views=("sphere", "road"))   # the usual pair of renders, -> {view: path}
    rig.side_by_side("a.png", "b.png", "ab.png", labels=("video", "ours"))

World lighting comes from Blender's bundled studio-light HDRIs (decision D6: no downloads):
city, courtyard, forest, interior, night, studio, sunrise, sunset.
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

from . import imaging

RIG_SCENE = "PM_Rig"
HDRIS = ("city", "courtyard", "forest", "interior", "night", "studio", "sunrise", "sunset")


# ======================================================================================== scene / engine / world
def hdri_path(name):
    """Path of a bundled HDRI (datafiles/studiolights/world/<name>.exr)."""
    d = bpy.utils.system_resource("DATAFILES", path="studiolights/world")
    p = os.path.join(d, name if name.lower().endswith(".exr") else name + ".exr")
    if not os.path.exists(p): raise FileNotFoundError("bundled HDRI %r not found (have %s)" % (name, ", ".join(HDRIS)))
    return p


def cycles_gpu(sc):
    """Cycles on the GPU when one is available (OPTIX, CUDA, HIP, ONEAPI, METAL), else the CPU. Returns True on GPU."""
    try: sc.render.engine = "CYCLES"
    except TypeError: return False
    try:
        cp = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                cp.compute_device_type = dev; cp.get_devices()
            except (TypeError, ValueError):
                continue
            if any(d.type == dev for d in cp.devices):
                for d in cp.devices: d.use = d.type == dev
                sc.cycles.device = "GPU"; return True
    except Exception:
        pass
    sc.cycles.device = "CPU"
    return False


def set_engine(sc, engine="EEVEE", samples=64, gpu=True, denoise=True):
    """EEVEE (whatever its identifier is: BLENDER_EEVEE in 5.x) or CYCLES. Returns the engine identifier."""
    if engine.upper() in ("CYCLES",):
        on_gpu = cycles_gpu(sc) if gpu else False
        if not gpu: sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
        sc.cycles.samples = samples; sc.cycles.use_denoising = denoise
        try: sc.cycles.use_adaptive_sampling = True
        except AttributeError: pass
        sc["pm_gpu"] = bool(on_gpu)
        return sc.render.engine
    ids = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for cand in [i for i in ids if "EEVEE" in i] + ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]:
        try:
            sc.render.engine = cand; break
        except TypeError:
            continue
    ee = sc.eevee
    for k, v in (("taa_render_samples", samples), ("use_raytracing", True), ("use_shadows", True)):
        try: setattr(ee, k, v)
        except (AttributeError, TypeError): pass
    return sc.render.engine


def world(sc, hdri="city", strength=1.0, rotation=0.0, visible=True):
    """World PM_World_<hdri>: Environment Texture (bundled HDRI) rotated `rotation` degrees about Z, Background
    strength `strength`. visible=False hides it from the camera (lighting only, black background)."""
    name = "PM_World_%s" % hdri
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    if w.node_tree is None: w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-700, 0); mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation))
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.location = (-480, 0)
    env.image = bpy.data.images.load(hdri_path(hdri), check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.location = (-200, 0); bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (0, 0)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"]); nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w["pm_hdri"] = hdri; w["pm_strength"] = strength; w["pm_rotation"] = rotation
    sc.world = w
    if not visible:
        try: w.cycles_visibility.camera = False
        except AttributeError: pass
    return w


def scene(name=RIG_SCENE, engine="EEVEE", samples=64, res=(800, 800), gpu=True, view="AgX", hdri="city", strength=1.0, rotation=0.0):
    """The preview scene (created once, settings re-applied on every call)."""
    sc = bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
    set_engine(sc, engine, samples, gpu)
    sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1]); sc.render.resolution_percentage = 100
    st = sc.render.image_settings
    st.file_format = "PNG"; st.color_mode = "RGB"; st.color_depth = "8"
    try: sc.view_settings.view_transform = view
    except TypeError: pass
    try: sc.view_settings.look = "None"
    except TypeError: pass
    if hdri: world(sc, hdri, strength, rotation)
    return sc


def collection(sc):
    """<scene>_Objects under the scene's master collection: every rig object lives there."""
    name = sc.name + "_Objects"
    col = bpy.data.collections.get(name)
    if col is None: col = bpy.data.collections.new(name)
    if col.name not in sc.collection.children: sc.collection.children.link(col)
    return col


def _sc(sc):
    return sc or bpy.data.scenes.get(RIG_SCENE) or scene()


# ======================================================================================== objects
def _mesh_obj(sc, name, bm, location, smooth=False):
    old = bpy.data.objects.get(name)
    if old is not None:
        me_old = old.data; bpy.data.objects.remove(old)
        if me_old is not None and me_old.users == 0: bpy.data.meshes.remove(me_old)
    me = bpy.data.meshes.new(name)
    if smooth:
        for f in bm.faces: f.smooth = True
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.location = location
    collection(sc).objects.link(ob)
    return ob


def icosphere(sc=None, subdivisions=6, radius=1.0, location=(0.0, 0.0, 1.0), name="PM_Sphere"):
    """The tutorials' preview object: a smooth-shaded icosphere (radius 1 m, subdivisions 6) with UVs."""
    sc = _sc(sc); bm = bmesh.new(); bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius, calc_uvs=True)
    return _mesh_obj(sc, name, bm, location, smooth=True)


def plane(sc=None, size=2.0, uv_tiles=1.0, cuts=0, location=(0.0, 0.0, 0.0), name="PM_Plane"):
    """A size x size m plane, UVs 0..uv_tiles; cuts = grid subdivisions (for displacement previews)."""
    sc = _sc(sc); bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    n = max(1, int(cuts) + 1)
    bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=size / 2.0)
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co; lp[uvl].uv = ((co.x / size + 0.5) * uv_tiles, (co.y / size + 0.5) * uv_tiles)
    return _mesh_obj(sc, name, bm, location)


def plane_hd(sc=None, size=2.0, cuts=300, location=(0.0, 0.0, 0.0), name="PM_PlaneHD"):
    """A densely subdivided plane (cuts x cuts quads) for true-displacement previews (contract_material(displacement=True))."""
    return plane(sc, size, 1.0, cuts, location, name)


def pane(sc=None, width=1.2, height=1.8, location=(0.0, 0.0, 0.0), name="PM_Pane"):
    """A vertical glass-pane quad in the XZ plane (bottom at z = 0, facing -Y), UVs 0..1."""
    sc = _sc(sc); bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(p) for p in ((-width / 2, 0.0, 0.0), (width / 2, 0.0, 0.0), (width / 2, 0.0, height), (-width / 2, 0.0, height))]
    f = bm.faces.new(vs)
    for lp, uv in zip(f.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))): lp[uvl].uv = uv
    bm.normal_update()
    if f.normal.y > 0: f.normal_flip()
    return _mesh_obj(sc, name, bm, location)


def cube(sc=None, size=2.0, location=(0.0, 0.0, 1.0), name="PM_Cube"):
    sc = _sc(sc); bm = bmesh.new(); bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_cube(bm, size=size, calc_uvs=True)
    return _mesh_obj(sc, name, bm, location)


def road_strip(sc=None, width=7.0, length=20.0, uv_scale=1.0, step=0.5, location=(0.0, 0.0, 0.0), name="PM_RoadStrip"):
    """A flat strip like a road surface: x across (-width/2..width/2), y along (0..length), z up. UVMap = (x, y) x
    uv_scale (metres like the road tool's meshes when uv_scale = 1; uv_scale = 1 / Tile Size previews UV mode as a
    baked tile would repeat). Float point attributes "lat" (= x) and "along" (= y) as on road meshes."""
    sc = _sc(sc); bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    lat = bm.verts.layers.float.new("lat"); along = bm.verts.layers.float.new("along")
    nx = max(1, round(width / step)); ny = max(1, round(length / step))
    grid = [[bm.verts.new((-width / 2 + width * i / nx, length * j / ny, 0.0)) for i in range(nx + 1)] for j in range(ny + 1)]
    for row in grid:
        for v in row: v[lat] = v.co.x; v[along] = v.co.y
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp in f.loops: lp[uvl].uv = (lp.vert.co.x * uv_scale, lp.vert.co.y * uv_scale)
    return _mesh_obj(sc, name, bm, location)


def assign(ob, mat):
    """Material in slot 0 (the only slot) of a rig object."""
    me = ob.data; me.materials.clear(); me.materials.append(mat)
    return ob


def show_only(sc, objs):
    """Render only `objs` among the rig's meshes (cameras and lights are left alone)."""
    keep = {o.name for o in objs}
    for o in collection(sc).objects:
        if o.type in ("CAMERA", "LIGHT"): continue
        o.hide_render = o.name not in keep


def tutorial_lights(sc=None, key=1000.0, rim=300.0, target=(0.0, 0.0, 1.0)):
    """Two area lights like the tutorials' emission planes (a bright key front-left-above, a rim light behind).
    Approximation (the tutorials use emissive planes of strength 100 and 5); remove with remove_lights()."""
    sc = _sc(sc); out = []
    for nm, power, pos, size in (("PM_KeyLight", key, (-2.5, -2.8, 3.2), 1.5), ("PM_RimLight", rim, (1.5, 3.0, 2.0), 2.0)):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            ld = bpy.data.lights.new(nm, "AREA"); ob = bpy.data.objects.new(nm, ld); collection(sc).objects.link(ob)
        ob.data.energy = power; ob.data.size = size; ob.location = pos
        look_at(ob, Vector(pos), Vector(target)); out.append(ob)
    return out


def remove_lights():
    for nm in ("PM_KeyLight", "PM_RimLight"):
        ob = bpy.data.objects.get(nm)
        if ob is not None: bpy.data.objects.remove(ob)


# ======================================================================================== cameras
def look_at(ob, eye, target):
    eye = Vector(eye); d = Vector(target) - eye
    ob.location = eye; ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def _bounds(ob):
    # matrix_world of a just-created object is stale until a depsgraph update: unparented objects use matrix_basis
    M = ob.matrix_basis if ob.parent is None else ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


CAMERA_PRESETS = ("front", "45", "top", "eye")


def camera(sc=None, preset="front", target=None, lens=None, name="PM_Camera"):
    """Camera presets around `target` (an object; default: the 2 m sphere at (0, 0, 1)):
    front  close-up, level, from -Y (the tutorials' view of the sphere), lens 50
    45     45 degrees above the object, from -Y, lens 50
    top    orthographic, straight down, framing the object's XY extent exactly (texel / scale checks)
    eye    eye level 1.7 m above a road strip's start, looking along +Y (a driver / pedestrian view), lens 30"""
    sc = _sc(sc)
    cam = bpy.data.objects.get(name)
    if cam is None or cam.type != "CAMERA":
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); collection(sc).objects.link(cam)
    elif cam.name not in collection(sc).objects:
        collection(sc).objects.link(cam)
    cd = cam.data; cd.type = "PERSP"; cd.sensor_fit = "AUTO"; cd.clip_start = 0.05; cd.clip_end = 2000.0
    if target is not None:
        lo, hi = _bounds(target)
    else:
        lo, hi = Vector((-1, -1, 0)), Vector((1, 1, 2))
    c = (lo + hi) / 2.0; dims = hi - lo; r = max(dims.length / 2.0, 1e-3)
    if preset == "front":
        cd.lens = lens or 50.0; t = 18.0 / cd.lens
        d = 1.35 * max(dims.x, dims.z) / 2.0 / t
        look_at(cam, c + Vector((0.0, -d, 0.0)), c)
    elif preset == "45":
        cd.lens = lens or 50.0; t = 18.0 / cd.lens; d = 1.35 * max(dims.x, dims.y, dims.z) / 2.0 / t
        look_at(cam, c + Vector((0.0, -d * math.cos(math.pi / 4), d * math.sin(math.pi / 4))), c)
    elif preset == "top":
        cd.type = "ORTHO"; cd.ortho_scale = max(dims.x, dims.y)
        cam.location = (c.x, c.y, hi.z + max(10.0, r))
        # image x = world x; a strip longer in y is turned so its length runs across the (landscape) frame
        cam.rotation_euler = (0.0, 0.0, math.pi / 2.0 if dims.y > dims.x * 1.01 else 0.0)
    elif preset == "eye":
        cd.lens = lens or 30.0
        eye = Vector((c.x - 0.12 * dims.x, lo.y - 1.5, hi.z + 1.7))
        look_at(cam, eye, Vector((c.x + 0.05 * dims.x, lo.y + 0.6 * dims.y, hi.z)))
    else:
        raise ValueError("camera preset %r (have %s)" % (preset, CAMERA_PRESETS))
    sc.camera = cam
    return cam


# ======================================================================================== render
def render(path, res=None, samples=None, scene=None):
    """Render the scene's camera to a PNG at `path` (res = (w, h), samples override). Returns the path."""
    sc = _sc(scene)
    if res: sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
    if samples:
        if sc.render.engine == "CYCLES": sc.cycles.samples = samples
        else:
            try: sc.eevee.taa_render_samples = samples
            except AttributeError: pass
    path = os.path.abspath(path); os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    st = sc.render.image_settings; st.file_format = "PNG"
    bpy.ops.render.render(write_still=True, scene=sc.name)
    return path


def side_by_side(left_png, right_png, out_png, labels=("left", "right"), extra=()):
    """Two (or more) renders side by side at the same height with a label bar (Pillow; see imaging)."""
    return imaging.side_by_side(left_png, right_png, out_png, labels, extra)


VIEWS = {  # view -> (object builder, camera preset, aspect h/w)
    "sphere": (icosphere, "front", 1.0), "sphere45": (icosphere, "45", 1.0), "plane": (plane, "top", 1.0),
    "plane_hd": (plane_hd, "45", 1.0), "cube": (cube, "45", 1.0), "pane": (pane, "front", 1.0),
    "road": (road_strip, "eye", 9.0 / 16.0), "road_top": (road_strip, "top", 0.35),
}


def preview(material, out_dir, views=("sphere", "road"), engine="EEVEE", res=800, samples=64, hdri="city", strength=1.0,
            rotation=0.0, prefix=None, lights=False, scene_name=RIG_SCENE, **inputs):
    """Render `material` on the preset objects: views from VIEWS (sphere, sphere45, plane, cube, road, road_top).
    inputs: group input overrides for these renders (restored afterwards), e.g. Use_UV=1.0.
    Files: <out_dir>/<prefix or material name>_<view>.png. Returns {view: path}."""
    from . import core
    mat = core.material(material)
    sc = scene(scene_name, engine, samples, (res, res), True, "AgX", hdri, strength, rotation)
    if lights: tutorial_lights(sc)
    else: remove_lights()
    node = core.group_node(mat); saved = {}
    if node is not None and inputs:
        for k in inputs:
            k2 = core._key(node.inputs, k)
            if k2 in node.inputs: saved[k2] = tuple(node.inputs[k2].default_value) if hasattr(node.inputs[k2].default_value, "__len__") else node.inputs[k2].default_value
        core.set_inputs(node, **inputs)
    out = {}
    try:
        for v in views:
            build, preset, aspect = VIEWS[v]
            ob = build(sc); assign(ob, mat); show_only(sc, [ob] + [o for o in collection(sc).objects if o.type == "LIGHT"])
            camera(sc, preset, ob)
            p = os.path.join(out_dir, "%s_%s.png" % (prefix or mat.name, v))
            out[v] = render(p, (res, max(16, int(round(res * aspect)))), scene=sc)
    finally:
        for k, val in saved.items(): node.inputs[k].default_value = val
    return out
