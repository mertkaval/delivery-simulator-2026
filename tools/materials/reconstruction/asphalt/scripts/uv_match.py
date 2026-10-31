"""Object mode vs UV mode, per texture (audit ASP-1): the value distribution of every 3D texture of PM_Asphalt
(object mode, the video's field) against its 4D twin on the seamless torus (UV mode, the bake path).

For every Dual (nodes <id>_3d / <id>_4d) and every output the graph uses, the "object 3D | UV 4D" Mix that selects the
mode is baked through an emission bake into a float image: object mode (Use UV 0) on a PLANE x PLANE m plane, UV mode
(Use UV 1, Tile Size = PLANE) on the same plane. 1 sample per pixel = point samples of the field. Because the Mix is
measured (not the raw 4D node), the same script measures the raw mismatch (before the fit) and the remapped UV branch
(after it). Writes <out>/uv_match.json: per output mean, std, p1/p5/p25/p50/p75/p95/p99 in both modes and the linear fit
gain = std3 / std4, offset = mean3 - gain * mean4 (per channel for colours: fit_gain_rgb / fit_offset_rgb; what
procmat/asphalt.py UV_MATCH holds).

    blender --background --factory-startup --python uv_match.py -- OUT_DIR [--plane 32] [--res 2048] [--material PM_Asphalt]
"""
import json
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if LIB not in sys.path: sys.path.insert(0, LIB)
import procmat  # noqa: E402
from procmat import bake as B, core  # noqa: E402

QS = (1, 5, 25, 50, 75, 95, 99)


def mode_mixes(tree):
    """{(node_id, output identifier): the Mix node that selects 3D (A) / 4D (B)} for every Dual output in use."""
    out = {}
    for n in tree.nodes:
        if n.bl_idname != "ShaderNodeMix" or n.label != "object 3D | UV 4D": continue
        a = next(s for s in n.inputs if s.enabled and s.identifier.startswith("A_") and s.is_linked)
        src = a.links[0].from_node
        if not src.name.endswith("_3d"): continue
        out[(src.name[:-3], a.links[0].from_socket.identifier)] = n
    return out


def result_socket(n):
    return next(s for s in n.outputs if s.enabled)


def bake_socket(mat, node, tree, sock, use_uv, plane, res, samples=1):
    """Emission bake of a group-internal socket (routed to the group's Albedo output) into a float array (H, W, 3)."""
    go = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput" and n.is_active_output)
    alb = go.inputs["Albedo"]; prev = alb.links[0].from_socket if alb.is_linked else None
    tree.links.new(sock, alb)
    nt = mat.node_tree
    out_node = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    surf = out_node.inputs["Surface"]; surf_from = surf.links[0].from_socket
    sc, _ = B._scene(samples, True, 0)
    ob = B._plane(sc, plane); ob.data.materials.append(mat)
    tex = nt.nodes.new("ShaderNodeTexImage"); nt.nodes.active = tex
    im = bpy.data.images.new("PM_UVMatch", res, res, alpha=False, float_buffer=True)
    im.colorspace_settings.name = "Non-Color"; tex.image = im
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(node.outputs["Albedo"], em.inputs["Color"])
    nt.links.new(em.outputs[0], surf)
    saved = {k: node.inputs[k].default_value for k in ("Use UV", "Tile Size")}
    try:
        node.inputs["Use UV"].default_value = 1.0 if use_uv else 0.0
        node.inputs["Tile Size"].default_value = plane
        B._run_bake(sc, ob, type="EMIT", margin=0, use_clear=True, uv_layer=B.BAKE_UV)
        a = np.empty(res * res * 4, np.float32); im.pixels.foreach_get(a)
        return a.reshape(res, res, 4)[..., :3].copy()
    finally:
        for k, v in saved.items(): node.inputs[k].default_value = v
        nt.nodes.remove(em); nt.links.new(surf_from, surf); nt.nodes.remove(tex)
        bpy.data.images.remove(im)
        me = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
        if prev is not None: tree.links.new(prev, alb)


def stats(x):
    x = x.ravel().astype(np.float64)
    q = np.percentile(x, QS)
    return {"mean": round(float(x.mean()), 5), "std": round(float(x.std()), 5),
            **{"p%d" % k: round(float(v), 5) for k, v in zip(QS, q)}}


def main(argv):
    out = argv[0]; os.makedirs(out, exist_ok=True)
    plane = float(argv[argv.index("--plane") + 1]) if "--plane" in argv else 32.0
    res = int(argv[argv.index("--res") + 1]) if "--res" in argv else 2048
    mname = argv[argv.index("--material") + 1] if "--material" in argv else "PM_Asphalt"
    procmat.discover(verbose=False); procmat.build("asphalt")
    mat = core.material(mname); node = core.group_node(mat); tree = node.node_tree
    result = {"material": mname, "plane_m": plane, "res": res, "outputs": {}}
    for (nid, key), mix in sorted(mode_mixes(tree).items()):
        sock = result_socket(mix)
        o = bake_socket(mat, node, tree, sock, False, plane, res)
        u = bake_socket(mat, node, tree, sock, True, plane, res)
        chans = 1 if sock.type == "VALUE" else 3
        r = {"object": stats(o[..., :chans]), "uv": stats(u[..., :chans])}
        if chans == 3:
            r["object_per_channel_std"] = [round(float(o[..., c].std()), 5) for c in range(3)]
            r["uv_per_channel_std"] = [round(float(u[..., c].std()), 5) for c in range(3)]
            gc = [float(o[..., c].std() / max(u[..., c].std(), 1e-9)) for c in range(3)]
            r["fit_gain_rgb"] = [round(g_, 4) for g_ in gc]
            r["fit_offset_rgb"] = [round(float(o[..., c].mean() - gc[c] * u[..., c].mean()), 4) for c in range(3)]
        g = r["object"]["std"] / max(r["uv"]["std"], 1e-9)
        r["fit_gain"] = round(g, 4); r["fit_offset"] = round(r["object"]["mean"] - g * r["uv"]["mean"], 4)
        # quantile error of the linear fit (UV values remapped vs object quantiles)
        r["fit_quantile_err"] = {"p%d" % k: round(g * r["uv"]["p%d" % k] + r["fit_offset"] - r["object"]["p%d" % k], 4) for k in QS}
        result["outputs"]["%s.%s" % (nid, key)] = r
        print("UVMATCH %-22s %-8s obj mean %.4f std %.4f | uv mean %.4f std %.4f | gain %.4f offset %.4f"
              % (nid, key, r["object"]["mean"], r["object"]["std"], r["uv"]["mean"], r["uv"]["std"], r["fit_gain"], r["fit_offset"]))
    with open(os.path.join(out, "uv_match.json"), "w") as f: json.dump(result, f, indent=1)
    print("UVMATCH OK", os.path.join(out, "uv_match.json"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
