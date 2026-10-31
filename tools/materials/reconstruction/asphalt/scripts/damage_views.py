"""Damaged-patch coverage across views of the video sphere (audit ASP-2). For N camera directions (Fibonacci sphere;
view 0 = (0, -1, 0), the direction of renders/PM_Asphalt_video.png) render, in the video scene of video_scene.py
(lights follow the camera, so every view is lit the same way):

    v<i>_lit.png   the lit render (Cycles, Filmic, same settings as PM_Asphalt_video.png unless --samples)
    v<i>_mask.png  the ground truth: emission of damage_mask_ramp (0 = pebbles show, 1 = intact), view Standard

damage_detect.py then runs one pebble-texture detector on the lit renders and the video frame and checks it against
the masks.

    blender --background --factory-startup --python damage_views.py -- OUT_DIR [--n 24] [--res 1301] [--samples 256]
            [--set "Damage Amount=0.343"] [--material PM_Asphalt] [--masks-only]
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import video_scene as VS  # noqa: E402  (puts tools/materials on sys.path)
import procmat  # noqa: E402
from procmat import core, rig  # noqa: E402


def mask_material(src, socket_node="damage_mask_ramp", name="PM_DamageMaskFlat"):
    grp = core.group_node(src)
    tree = grp.node_tree.copy(); tree.name = grp.node_tree.name + "_mask"
    go = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput" and n.is_active_output)
    tree.links.new(next(s for s in tree.nodes[socket_node].outputs if s.enabled), go.inputs["Albedo"])
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = tree
    for s in grp.inputs:
        if hasattr(s, "default_value") and s.name in g.inputs: g.inputs[s.name].default_value = s.default_value
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(g.outputs["Albedo"], em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def directions(n):
    out = [(0.0, -1.0, 0.0)]
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n - 1):
        z = 1.0 - 2.0 * (i + 0.5) / (n - 1); r = math.sqrt(max(0.0, 1.0 - z * z))
        out.append((r * math.cos(ga * i), r * math.sin(ga * i), z))
    return out


def main(argv):
    out = argv[0]; os.makedirs(out, exist_ok=True)
    arg = lambda k, d: type(d)(argv[argv.index(k) + 1]) if k in argv else d
    n, res, samples, sets, mname = arg("--n", 24), arg("--res", 1301), arg("--samples", 256), arg("--set", ""), arg("--material", "PM_Asphalt")
    procmat.discover(verbose=False); procmat.build("asphalt")
    mat = core.material(mname)
    if sets: core.set_inputs(mat, **VS.parse_sets(sets))
    mmat = mask_material(mat)
    info = {"material": mname, "set": sets, "res": res, "samples": samples, "views": []}
    for i, d in enumerate(directions(n)):
        for kind in ("lit", "mask"):
            if kind == "lit" and "--masks-only" in argv: continue
            sc = rig.scene(VS.SCENE, "CYCLES", samples if kind == "lit" else 8, (res, res), True,
                           "Filmic" if kind == "lit" else "Standard", "studio", 0.2, 0.0)
            sc.world.cycles_visibility.camera = False
            sc.cycles.use_denoising = kind == "lit"
            VS.neutral_world(sc.world)
            for o in list(rig.collection(sc).objects): bpy.data.objects.remove(o)
            ob = VS.video_sphere(sc); rig.assign(ob, mat if kind == "lit" else mmat)
            cam, basis, dist = VS.video_camera(sc, d, 0.0)
            if kind == "lit": VS.video_lights(sc, basis, 100.0, 5.0, 2.1)
            else: sc.world = None
            rig.render(os.path.join(out, "v%02d_%s.png" % (i, kind)), scene=sc)
        info["views"].append({"i": i, "dir": [round(x, 4) for x in d]})
        print("DVIEWS view", i, d, flush=True)
    with open(os.path.join(out, "views.json"), "w") as f: json.dump(info, f, indent=1)
    print("DVIEWS OK")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
