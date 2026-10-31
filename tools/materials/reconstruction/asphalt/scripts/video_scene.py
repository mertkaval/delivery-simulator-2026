"""Renders of PM_Asphalt / PM_AsphaltTutorial in the video's scene (and the library's real-scale road check), built on
the core rig (procmat.rig: scene, engine, bundled-HDRI world, road strip, camera, render) plus the video's emitter
planes, which the rig does not have (its tutorial_lights() are area lights on the other side).

    blender --background --factory-startup --python video_scene.py -- --out DIR [--views video,closeup,road,flat]
            [--materials PM_Asphalt,PM_AsphaltTutorial] [--res 1024] [--samples 256] [--hdri studio] [--rotation 0] [--view Filmic]
            [--dir x,y,z] [--roll 0] [--dist 3.09] [--set "Crack Amount=0.6;Bump Damage=0.5"] [--prefix NAME]
            [--key 100] [--rim 5] [--key-size 2.1] [--filter-width 1.0] [--world-strength 0.2] [--no-denoise]

video   : the video's scene (A where seen, C/D where hidden): icosphere subdivisions 6, radius 1 m (C), Cycles, key
          emitter disc Strength 100 up and right of the camera, rim emitter strip Strength 5 behind on the left, world =
          a bundled HDRI (D6) hidden from the camera (black background like the F12 render), Filmic (U3), square image,
          50 mm lens framing the sphere at 95 % of the height (U5).
closeup : the same scene, 4x zoom on the sphere (the 25:10 render-region close-up); with --state2510 the roughness is
          the constant 0.5 it had at 25:10 (the roughness ramp came later).
flat    : albedo only (emission of the group's Albedo output, view Standard): pattern / colour checks without lighting.
road    : the rig's road strip 7 m x 20 m, eye level 1.7 m, bundled HDRI visible (real-world scale check).
road_baked: the same strip with the UV-mode bake (4 m tile, 1024 px) as an image material: what an engine shows.
World: the bundled HDRI desaturated (--tinted-world keeps its colour), so its tint does not read as material colour.
Headless only; never the user's Blender."""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))          # tools/materials
if LIB not in sys.path: sys.path.insert(0, LIB)
import procmat  # noqa: E402
from procmat import core, rig  # noqa: E402

SCENE = "PM_AsphaltVideo"


def video_sphere(sc):
    """The video's object: icosphere, subdivisions 6 (10,242 v / 20,480 f, as the 3.2 status bar), radius 1 m (C),
    smooth, at the origin (object coordinates = local coordinates, so the location does not matter)."""
    bm = bmesh.new(); bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_icosphere(bm, subdivisions=6, radius=1.0, calc_uvs=True)
    for f in bm.faces: f.smooth = True
    old = bpy.data.objects.get("Icosphere")
    if old is not None: bpy.data.objects.remove(old)
    me = bpy.data.meshes.new("Icosphere"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Icosphere", me); rig.collection(sc).objects.link(ob)
    return ob


def emitter(sc, name, size_x, size_y, strength, loc, target, rounded):
    """An emission plane like the video's 'Lighting' objects (white Emission, Strength as in the video). rounded = the
    key light's subdivided quad (81 v / 64 f in the scene stats, an ellipse in the viewport)."""
    old = bpy.data.objects.get(name)
    if old is not None: bpy.data.objects.remove(old)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); rig.collection(sc).objects.link(ob)
    if rounded:
        mod = ob.modifiers.new("Subdivision", "SUBSURF"); mod.levels = mod.render_levels = 3
    ob.scale = (size_x, size_y, 1.0)
    m = bpy.data.materials.get(name + "_Emission") or bpy.data.materials.new(name + "_Emission")
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (1, 1, 1, 1); em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    me.materials.append(m)
    ob.location = loc
    # the plane's normal (+Z) faces the target
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("Z", "Y").to_euler()
    ob.visible_camera = False                       # the video's camera never sees the emitters
    return ob


def camera_basis(direction, roll_deg):
    """(right, up, back) for a camera on `direction` (from the sphere centre) looking at it, rolled by roll_deg."""
    D = Vector(direction).normalized(); f = -D
    r = f.cross(Vector((0, 0, 1)))
    if r.length < 1e-6: r = f.cross(Vector((0, 1, 0)))
    r.normalize(); u = r.cross(f)
    c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
    return c * r + s * u, -s * r + c * u, D


def video_camera(sc, direction=(0.0, -1.0, 0.0), roll=0.0, dist=None, lens=50.0, fill=0.95, zoom=1.0, offset=(0.0, 0.0)):
    """50 mm camera on `direction` aimed at the sphere centre; dist (sphere radii) defaults to the distance that
    frames the sphere at `fill` of the square image (U5). zoom > 1 = narrower view (render-region close-ups) moved by
    `offset` (fractions of the sphere's image radius, x right, y up)."""
    t_half = 18.0 / lens
    if dist is None:
        a = math.atan(fill * t_half); dist = 1.0 / math.sin(a)
    r, u, D = camera_basis(direction, roll)
    cd = bpy.data.cameras.get("VideoCam") or bpy.data.cameras.new("VideoCam")
    cd.type = "PERSP"; cd.sensor_fit = "AUTO"; cd.sensor_width = 36.0; cd.lens = lens * zoom; cd.clip_start = 0.05
    t_sil = math.tan(math.asin(1.0 / dist)) / t_half       # sphere image radius in half-frame units at zoom 1
    cd.shift_x = offset[0] * t_sil * zoom / 2.0; cd.shift_y = offset[1] * t_sil * zoom / 2.0
    cam = bpy.data.objects.get("VideoCam")
    if cam is None:
        cam = bpy.data.objects.new("VideoCam", cd); rig.collection(sc).objects.link(cam)
    cam.matrix_world = Matrix.Translation(D * dist) @ Matrix((r, u, D)).transposed().to_4x4()
    cam.location = D * dist
    sc.camera = cam
    return cam, (r, u, D), dist


KEY_DIR = (0.80, 0.58, 0.25)    # camera basis (right, up, toward camera): fitted to the 26:38 shading (C, VALIDATION.md)
RIM_DIR = (-0.80, 0.10, -0.60)  # behind the sphere on the left: the thin rim on the left limb (C)


def video_lights(sc, basis, key=100.0, rim=5.0, key_size=1.6, key_dir=KEY_DIR, rim_dir=RIM_DIR, key_dist=4.0):
    """Key disc (Strength 100, A) and rim strip (Strength 5, A); sizes and positions are hidden in the video (U6, D):
    directions in the camera's basis, the key from a Lambert fit of the final render's shading (C)."""
    r, u, D = basis
    kdir = (key_dir[0] * r + key_dir[1] * u + key_dir[2] * D).normalized()
    rdir = (rim_dir[0] * r + rim_dir[1] * u + rim_dir[2] * D).normalized()
    k = emitter(sc, "Lighting", key_size, key_size, key, kdir * key_dist, (0, 0, 0), True)
    s = emitter(sc, "Lighting.001", 0.35, 5.0, rim, rdir * 3.0, (0, 0, 0), False)
    return k, s


def flat_material(src, name="PM_AlbedoFlat"):
    """Emission of the group's Albedo output (same group, same input values): the pattern without lighting."""
    grp = core.group_node(src)
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = grp.node_tree
    for s in grp.inputs:
        if hasattr(s, "default_value") and s.name in g.inputs: g.inputs[s.name].default_value = s.default_value
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(g.outputs["Albedo"], em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def state_2510(src):
    """PM_AsphaltTutorial as it was at 25:10: the roughness ramp was not connected yet (Principled Roughness 0.5)."""
    tree = core.group_node(src).node_tree.copy(); tree.name = "PM_AsphaltTutorial_2510"
    n = tree.nodes.get("rough_ramp")
    for e in n.color_ramp.elements: e.color = (0.5, 0.5, 0.5, 1.0)
    m = src.copy(); m.name = "PM_AsphaltTutorial_2510"
    core.group_node(m).node_tree = tree
    return m


def neutral_world(w):
    """Hue/Saturation (saturation 0) between the HDRI and the Background: same light, no colour cast."""
    nt = w.node_tree
    env = next(n for n in nt.nodes if n.type == "TEX_ENVIRONMENT"); bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.0
    nt.links.new(env.outputs["Color"], hs.inputs["Color"]); nt.links.new(hs.outputs[0], bg.inputs["Color"])


def set_filter_width(mat, fw):
    """PM_Asphalt: its "Bump Filter Width" input; PM_AsphaltTutorial: the four Bump nodes (constants)."""
    node = core.group_node(mat)
    if "Bump Filter Width" in node.inputs:
        node.inputs["Bump Filter Width"].default_value = fw; return
    for n in node.node_tree.nodes:
        if n.bl_idname == "ShaderNodeBump" and "Filter Width" in n.inputs: n.inputs["Filter Width"].default_value = fw


def parse_sets(s):
    out = {}
    for item in (s or "").split(";"):
        if "=" in item:
            k, v = item.split("=", 1); out[k.strip()] = float(v)
    return out


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True); p.add_argument("--views", default="video")
    p.add_argument("--materials", default="PM_Asphalt"); p.add_argument("--res", type=int, default=1024)
    p.add_argument("--samples", type=int, default=256); p.add_argument("--hdri", default="studio")
    p.add_argument("--world-strength", type=float, default=0.2); p.add_argument("--rotation", type=float, default=0.0)
    p.add_argument("--view", default="Filmic"); p.add_argument("--dir", default="0,-1,0"); p.add_argument("--roll", type=float, default=0.0)
    p.add_argument("--dist", type=float, default=None); p.add_argument("--set", default="")
    p.add_argument("--prefix", default=""); p.add_argument("--key", type=float, default=100.0); p.add_argument("--rim", type=float, default=5.0)
    p.add_argument("--key-size", type=float, default=2.1); p.add_argument("--filter-width", type=float, default=None)
    p.add_argument("--zoom", type=float, default=4.0); p.add_argument("--offset", default="0.35,0.55")
    p.add_argument("--state2510", action="store_true"); p.add_argument("--road-engine", default="CYCLES")
    p.add_argument("--key-dir", default=",".join(str(x) for x in KEY_DIR)); p.add_argument("--rim-dir", default=",".join(str(x) for x in RIM_DIR))
    p.add_argument("--key-dist", type=float, default=4.0); p.add_argument("--no-denoise", action="store_true")
    p.add_argument("--tinted-world", action="store_true", help="keep the HDRI colour (default: desaturated fill, D6 / AS7)")
    a = p.parse_args(argv)
    procmat.discover(verbose=False); procmat.build("asphalt")
    os.makedirs(a.out, exist_ok=True)
    sets = parse_sets(a.set)
    direction = tuple(float(x) for x in a.dir.split(","))
    for mname in [m.strip() for m in a.materials.split(",") if m.strip()]:
        mat = core.material(mname)
        if sets:
            miss = core.set_inputs(mat, **sets)
            if miss: print("[scene] %s: unknown inputs %s" % (mname, miss))
        if a.filter_width is not None: set_filter_width(mat, a.filter_width)
        tag = a.prefix or mat.name
        for view in [v.strip() for v in a.views.split(",") if v.strip()]:
            if view == "road_baked":
                from procmat import bake as BK
                tile = 4.0
                paths = BK.bake(mat, os.path.join(a.out, "_bake"), tile=tile, res=1024, samples=16, prefix=tag)
                bm_ = BK.baked_material(tag + "_Baked", paths, repeat=1.0 / tile)
                out = rig.preview(bm_, a.out, views=("road",), engine=a.road_engine, res=a.res, samples=min(a.samples, 128),
                                  hdri="city", prefix=tag + "_baked")
                print("[scene] wrote", out["road"]); continue
            if view == "road":
                out = rig.preview(mat, a.out, views=("road",), engine=a.road_engine, res=a.res, samples=min(a.samples, 128),
                                  hdri="city", prefix=tag)
                print("[scene] wrote", out["road"]); continue
            sc = rig.scene(SCENE, "CYCLES", a.samples, (a.res, a.res), True, a.view if view != "flat" else "Standard",
                           a.hdri, a.world_strength, a.rotation)
            sc.world.cycles_visibility.camera = False              # black background like the F12 render
            sc.cycles.use_denoising = not a.no_denoise
            if not a.tinted_world and sc.world is not None: neutral_world(sc.world)
            for o in list(rig.collection(sc).objects): bpy.data.objects.remove(o)
            ob = video_sphere(sc)
            use = mat
            if view == "flat": use = flat_material(mat)
            elif view == "closeup" and a.state2510 and mat.name == "PM_AsphaltTutorial": use = state_2510(mat)
            rig.assign(ob, use)
            zoom = a.zoom if view == "closeup" else 1.0
            off = tuple(float(x) for x in a.offset.split(",")) if view == "closeup" else (0.0, 0.0)
            cam, basis, dist = video_camera(sc, direction, a.roll, a.dist, zoom=zoom, offset=off)
            if view != "flat":
                video_lights(sc, basis, a.key, a.rim, a.key_size, tuple(float(x) for x in a.key_dir.split(",")),
                             tuple(float(x) for x in a.rim_dir.split(",")), a.key_dist)
            else: sc.world = None
            path = os.path.join(a.out, "%s_%s.png" % (tag, view))
            rig.render(path, scene=sc)
            print("[scene] wrote", path, "dist %.3f" % dist)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
