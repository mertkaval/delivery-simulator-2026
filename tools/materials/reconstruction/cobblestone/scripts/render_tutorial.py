"""Cobblestone validation renders: the tutorial's scene (as far as identified) with the core rig's helpers.

blender --background --factory-startup --python tools/materials/reconstruction/cobblestone/scripts/render_tutorial.py --
        --out DIR [--views sphere,closeup,road,road_top,uv_sphere] [--res 1024] [--samples 128] [--hdri courtyard]
        [--cam-az 0] [--cam-el 8] [--sun-az -40] [--sun-el 40] [--prefix NAME] [--set "Input=value;..."]

Scene (GRAPH_SPEC_a scene section; A unless noted): icosphere subdivisions 6, radius 0.5 m (scale applied), smooth,
Subdivision Surface render level 2 here (C: the build file had sub 4 + render level 3 = the same 81,920 base faces,
the demo object sub 6 + ?); material PM_CobblestoneDisplaced ("Displacement and Bump"); Cycles GPU; Film Transparent;
Blackman-Harris 1.5 px; Filmic + Very High Contrast; camera 80 mm, clip 0.1-1000 m (transform D: here level from -Y
rotated by cam-az / cam-el); sun strength 15, 6000 K, angle 0.526 deg (direction D); rim Area disk 1 m 300 W #FFEDE0
behind the object (position D); world: a bundled studio-light HDRI strength 1 instead of fish_hoek_beach_1k (D6).
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))       # tools/materials
if LIB not in sys.path: sys.path.insert(0, LIB)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import procmat  # noqa: E402
from procmat import core, rig  # noqa: E402


def srgb_lin(h):
    h = h.lstrip("#")
    return tuple(((c / 255.0) / 12.92 if c / 255.0 <= 0.04045 else ((c / 255.0 + 0.055) / 1.055) ** 2.4)
                 for c in (int(h[i:i + 2], 16) for i in (0, 2, 4)))


def kelvin_rgb(k):
    """Blackbody -> linear RGB (Blender's own Blackbody node values for 6000 K are about 1.0, 0.86, 0.75 normalised)."""
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def look_filmic(sc):
    """Filmic + Very High Contrast (dynamic enums: set by trying the names; 4.x+ prefixes looks with the view)."""
    vs = sc.view_settings
    try: vs.view_transform = "Filmic"
    except TypeError as e: print("[cb] no Filmic:", e)
    for cand in ("Filmic - Very High Contrast", "Very High Contrast"):
        try:
            vs.look = cand; break
        except TypeError as e:
            print("[cb] look %r: %s" % (cand, e))
    return vs.view_transform, vs.look


def setup(a):
    sc = rig.scene("PM_Cobble", "CYCLES", a.samples, (a.res, a.res), True, "AgX", a.hdri, a.strength, a.hdri_rot)
    look = look_filmic(sc)
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    try:
        sc.cycles.filter_type = "BLACKMAN_HARRIS"; sc.cycles.filter_width = 1.5
    except (AttributeError, TypeError):
        try: sc.cycles.pixel_filter_type = "BLACKMAN_HARRIS"; sc.cycles.filter_width = 1.5
        except (AttributeError, TypeError): pass
    col = rig.collection(sc)
    # sun
    sun = bpy.data.objects.get("CB_Sun")
    if sun is None:
        sun = bpy.data.objects.new("CB_Sun", bpy.data.lights.new("CB_Sun", "SUN")); col.objects.link(sun)
    sun.data.energy = 15.0; sun.data.angle = math.radians(0.526)
    if hasattr(sun.data, "use_temperature") and hasattr(sun.data, "temperature"):
        sun.data.use_temperature = True; sun.data.temperature = 6000.0; sun.data.color = (1, 1, 1)
        how = "temperature property"
    else:
        sun.data.color = kelvin_rgb(6000.0); how = "kelvin->rgb"
    az, el = math.radians(a.sun_az), math.radians(a.sun_el)
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))   # towards the sun
    rig.look_at(sun, d * 10.0, Vector((0, 0, 0)))
    # rim
    rim = bpy.data.objects.get("CB_Rim")
    if rim is None:
        rim = bpy.data.objects.new("CB_Rim", bpy.data.lights.new("CB_Rim", "AREA")); col.objects.link(rim)
    rim.data.shape = "DISK"; rim.data.size = 1.0; rim.data.energy = 300.0; rim.data.color = srgb_lin("FFEDE0")
    rig.look_at(rim, Vector((a.rim_x, 2.2, a.rim_z)), Vector((0, 0, 0)))
    print("[cb] look", look, "sun colour via", how)
    return sc, [sun, rim]


def sphere(sc, mat, subsurf, ico=6):
    ob = rig.icosphere(sc, subdivisions=ico, radius=0.5, location=(0.0, 0.0, 0.0), name="CB_Sphere")
    if subsurf:
        m = ob.modifiers.new("Subdivision", "SUBSURF"); m.levels = 0; m.render_levels = subsurf
    rig.assign(ob, mat)
    return ob


def cam_sphere(sc, a, lens=80.0, fill=0.93, target=(0, 0, 0), radius=0.5):
    cam = bpy.data.objects.get("CB_Cam")
    if cam is None:
        cam = bpy.data.objects.new("CB_Cam", bpy.data.cameras.new("CB_Cam")); rig.collection(sc).objects.link(cam)
    cam.data.lens = lens; cam.data.clip_start = 0.1; cam.data.clip_end = 1000.0; cam.data.sensor_fit = "AUTO"
    t = 18.0 / lens
    dist = radius / (fill * t) if fill else 2.4
    az, el = math.radians(a.cam_az), math.radians(a.cam_el)
    eye = Vector(target) + dist * Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    rig.look_at(cam, eye, Vector(target))
    sc.camera = cam
    return cam


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True); p.add_argument("--views", default="sphere,closeup,road")
    p.add_argument("--res", type=int, default=1024); p.add_argument("--samples", type=int, default=128)
    p.add_argument("--hdri", default="courtyard"); p.add_argument("--strength", type=float, default=1.0)
    p.add_argument("--hdri-rot", type=float, default=0.0)
    p.add_argument("--cam-az", type=float, default=0.0); p.add_argument("--cam-el", type=float, default=-1.0)
    p.add_argument("--sun-az", type=float, default=-40.0); p.add_argument("--sun-el", type=float, default=40.0)
    p.add_argument("--rim-x", type=float, default=0.6); p.add_argument("--rim-z", type=float, default=0.8)
    p.add_argument("--subsurf", type=int, default=3); p.add_argument("--ico", type=int, default=4); p.add_argument("--prefix", default="cb")
    p.add_argument("--set", default="")
    a = p.parse_args(argv)
    procmat.discover(["cobblestone"])
    mats = procmat.build("cobblestone")
    disp = core.material("CobblestoneDisplaced"); bump = core.material("Cobblestone")
    for kv in [x for x in a.set.split(";") if x.strip()]:
        k, v = kv.split("=")
        for m in (disp, bump):
            core.group_node(m).inputs[k.strip()].default_value = float(v)
    sc, lights = setup(a)
    os.makedirs(a.out, exist_ok=True)
    for v in [x.strip() for x in a.views.split(",") if x.strip()]:
        for o in rig.collection(sc).objects:
            if o.type == "MESH": o.hide_render = True
        if v in ("sphere", "closeup", "uv_sphere", "bump_sphere"):
            ob = sphere(sc, bump if v == "bump_sphere" else disp, a.subsurf, a.ico); ob.hide_render = False
            node = core.group_node(disp)
            if v == "uv_sphere": node.inputs["Use UV"].default_value = 1.0; node.inputs["Tile Size"].default_value = 4.0
            if v == "closeup":
                cam = cam_sphere(sc, a, lens=80.0, fill=None)
                cam.data.lens = 80.0 * 3.5            # the 1:10 render-region close-up: ~1/3.5 of the sphere width
            else:
                cam_sphere(sc, a)
            path = rig.render(os.path.join(a.out, "%s_%s.png" % (a.prefix, v)), (a.res, a.res), scene=sc)
            node.inputs["Use UV"].default_value = 0.0
        elif v in ("road", "road_top"):
            ob = rig.road_strip(sc, 7.0, 20.0, name="CB_Road"); rig.assign(ob, bump); ob.hide_render = False
            sc.render.film_transparent = False
            lights[1].hide_render = True          # the rim light belongs to the sphere set-up
            rig.camera(sc, "eye" if v == "road" else "top", ob)
            h = int(round(a.res * (9.0 / 16.0 if v == "road" else 0.35)))
            path = rig.render(os.path.join(a.out, "%s_%s.png" % (a.prefix, v)), (a.res, h), scene=sc)
            sc.render.film_transparent = True; lights[1].hide_render = False
        print("[cb] rendered", path)
    return True


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ok = False
    try:
        ok = main(argv)
    except Exception:
        import traceback; traceback.print_exc()
    print("CB OK" if ok else "CB FAIL")
    sys.exit(0 if ok else 1)
