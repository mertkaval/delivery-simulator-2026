"""Search the camera direction under which our object-space stone pattern matches the video's sphere.

blender --background --factory-startup --python view_search.py -- --frame VIDEO.png --crop x0,y0,x1,y1 --out DIR
        [--step 15] [--res 112] [--refine]

The video's material samples Object coordinates with Blender's deterministic 3D Noise / Voronoi, so if Blender 5.2
produces the same field as 5.0.1, some camera direction shows the same stones. We render the stone mask (group output
Height through an emission shader, flat, no lighting) of PM_Cobblestone on the 0.5 m sphere with an 80 mm camera from
many (azimuth, elevation, roll = 0) directions and correlate each with the high-passed grey video crop. Prints the best
directions; writes best_<i>.png. Evidence class C (search), never a claim unless the overlay shows the same stones.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if LIB not in sys.path: sys.path.insert(0, LIB)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import procmat  # noqa: E402
from procmat import core, rig  # noqa: E402


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, im.channels)[::-1]
    bpy.data.images.remove(im)
    return a


def gray(a):
    return a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def box_blur(a, r):
    if r < 1: return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def highpass(g, mask):
    g = g - box_blur(g, max(2, g.shape[0] // 12))
    g = box_blur(g, 1)
    v = g[mask]; v = (v - v.mean()) / (v.std() + 1e-6)
    return v


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--frame", required=True); p.add_argument("--crop", required=True); p.add_argument("--out", required=True)
    p.add_argument("--step", type=float, default=15.0); p.add_argument("--res", type=int, default=112)
    p.add_argument("--center", default=""); p.add_argument("--span", type=float, default=0.0)
    p.add_argument("--rolls", default="0")
    a = p.parse_args(argv); a.out = os.path.abspath(a.out)
    os.makedirs(a.out, exist_ok=True)
    procmat.discover(["cobblestone"]); procmat.build("cobblestone")
    mat = core.material("Cobblestone")
    nt = mat.node_tree; node = core.group_node(mat)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission"); mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    nt.links.new(node.outputs["Height"], mul.inputs[0]); mul.inputs[1].default_value = 1.0 / (0.3185 * 0.02)
    nt.links.new(mul.outputs[0], em.inputs["Strength"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    for l in list(out.inputs["Displacement"].links): nt.links.remove(l)
    sc = rig.scene("PM_Search", "CYCLES", 4, (a.res, a.res), True, "Standard", None)
    sc.cycles.use_denoising = False
    sc.world = bpy.data.worlds.new("black")
    ob = rig.icosphere(sc, 6, 0.5, (0, 0, 0), name="S_Sphere"); rig.assign(ob, mat)
    cam = bpy.data.objects.new("S_Cam", bpy.data.cameras.new("S_Cam")); rig.collection(sc).objects.link(cam)
    cam.data.lens = 80.0; sc.camera = cam
    dist = 0.5 / (0.93 * 18.0 / 80.0)
    # video target (crop is read with Blender's loader; crop indices in the full frame, top-down)
    x0, y0, x1, y1 = (int(v) for v in a.crop.split(","))
    full = load(os.path.abspath(a.frame))
    v = gray(full[y0:y1, x0:x1])
    # area resize to res
    n = a.res; hh, ww = v.shape
    yi = (np.arange(n + 1) * hh / n).astype(int); xi = (np.arange(n + 1) * ww / n).astype(int)
    vs = np.array([[v[yi[i]:yi[i + 1], xi[j]:xi[j + 1]].mean() for j in range(n)] for i in range(n)], dtype=np.float32)
    yy, xx = np.mgrid[0:n, 0:n]
    mask = ((xx - n / 2 + 0.5) ** 2 + (yy - n / 2 + 0.5) ** 2) <= (n / 2 * 0.93 * 0.8) ** 2
    target = highpass(vs, mask)
    if a.center:
        ca, ce = (float(x) for x in a.center.split(","))
        azs = np.arange(ca - a.span, ca + a.span + 1e-6, a.step); els = np.arange(ce - a.span, ce + a.span + 1e-6, a.step)
    else:
        azs = np.arange(0.0, 360.0, a.step); els = np.arange(-75.0, 75.0 + 1e-6, a.step)
    rolls = [float(r) for r in a.rolls.split(",")]
    res = []
    tmp = os.path.join(a.out, "_tmp.png")
    for el in els:
        for az in azs:
            for roll in rolls:
                azr, elr = math.radians(az), math.radians(el)
                eye = dist * Vector((math.sin(azr) * math.cos(elr), -math.cos(azr) * math.cos(elr), math.sin(elr)))
                rig.look_at(cam, eye, Vector((0, 0, 0)))
                if roll: cam.rotation_euler.rotate_axis("Z", math.radians(roll))
                rig.render(tmp, (n, n), scene=sc)
                g = gray(load(tmp))
                c = float(np.mean(highpass(g, mask) * target))
                res.append((c, az, el, roll))
    res.sort(reverse=True)
    for i, (c, az, el, roll) in enumerate(res[:8]):
        print("[search] %d corr %.3f az %.1f el %.1f roll %.1f" % (i, c, az, el, roll))
    corrs = np.array([r[0] for r in res])
    print("[search] n %d mean %.3f std %.3f max %.3f" % (len(res), corrs.mean(), corrs.std(), corrs.max()))
    for i, (c, az, el, roll) in enumerate(res[:3]):
        azr, elr = math.radians(az), math.radians(el)
        rig.look_at(cam, dist * Vector((math.sin(azr) * math.cos(elr), -math.cos(azr) * math.cos(elr), math.sin(elr))), Vector((0, 0, 0)))
        if roll: cam.rotation_euler.rotate_axis("Z", math.radians(roll))
        rig.render(os.path.join(a.out, "best_%d_az%g_el%g_r%g.png" % (i, az, el, roll)), (512, 512), scene=sc)
    return True


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ok = False
    try: ok = main(argv)
    except Exception:
        import traceback; traceback.print_exc()
    print("SEARCH OK" if ok else "SEARCH FAIL")
    sys.exit(0 if ok else 1)
