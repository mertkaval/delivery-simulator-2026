"""Object mode vs UV mode on the whole material (audit ASP-1): PM_Asphalt at its defaults baked on a PLANE m plane
(default 16 m, 4096 px, 4 spp) in object mode and in UV mode (Tile Size = PLANE), split into windows of WIN m
(default 4 m = 16 windows). Three float emission bakes per mode, read from the group's own sockets:

    albedo  the group's Albedo (darken_damage), reported in sRGB (display) values
    crack   crack_bump_ramp (0 in a crack groove, 1 outside): crack pixel = crack < 0.5 (groove geometry)
    tone    crack-tone pixel: the cracks darken the base colour by more than 0.01 (sRGB): color_ramp vs darken_cracks
    damage  damage_mask_ramp (0 where the pebbles show, 1 intact): damage pixel = damage < 0.5
    intact  = neither: albedo spread p95 - p5 and std of the intact surface (the base-cell mottling)

Per window: intact p95-p5, intact std, crack fraction, damage fraction, crack-tone fraction; mean / sd over the windows -> <out>/uv_stats.json.
--no-match builds the material without the UV_MATCH remap (the state before AS17) for the before / after table.

    blender --background --factory-startup --python uv_stats.py -- OUT_DIR [--plane 16] [--res 4096] [--win 4] [--no-match]
            [--set "Damage Amount=0.343"] [--modes object,uv]
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import uv_match  # noqa: E402  (also puts tools/materials on sys.path)
import procmat  # noqa: E402
from procmat import core  # noqa: E402


def to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def main(argv):
    out = argv[0]; os.makedirs(out, exist_ok=True)
    arg = lambda k, d: type(d)(argv[argv.index(k) + 1]) if k in argv else d
    plane, res, win = arg("--plane", 16.0), arg("--res", 4096), arg("--win", 4.0)
    procmat.discover(verbose=False)
    import procmat.asphalt as A
    if "--no-match" in argv: A._uv_match = lambda G, tex, *a, **k: tex
    procmat.build("asphalt")
    mat = core.material("PM_Asphalt"); node = core.group_node(mat); tree = node.node_tree
    sets = arg("--set", "")
    for item in sets.split(";"):
        if "=" in item: core.set_inputs(mat, **{item.split("=")[0].strip(): float(item.split("=")[1])})
    modes = arg("--modes", "object,uv").split(",")
    go = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput" and n.is_active_output)
    socks = {"albedo": go.inputs["Albedo"].links[0].from_socket,
             "crack": next(s for s in tree.nodes["crack_bump_ramp"].outputs if s.enabled),
             "damage": next(s for s in tree.nodes["damage_mask_ramp"].outputs if s.enabled),
             "base": next(s for s in tree.nodes["color_ramp"].outputs if s.enabled),
             "darken": next(s for s in tree.nodes["darken_cracks"].outputs if s.enabled)}
    n = int(round(plane / win)); w = res // n
    result = {"plane_m": plane, "res": res, "window_m": win, "windows": n * n, "uv_match": "--no-match" not in argv, "modes": {}}
    result["set"] = sets
    for mode, use_uv in [m for m in (("object", False), ("uv", True)) if m[0] in modes]:
        img = {k: uv_match.bake_socket(mat, node, tree, s, use_uv, plane, res, samples=4) for k, s in socks.items()}
        alb = to_srgb(img["albedo"]).mean(axis=2); crack = img["crack"][..., 0] < 0.5; dmg = img["damage"][..., 0] < 0.5
        tone = (to_srgb(img["base"]).mean(axis=2) - to_srgb(img["darken"]).mean(axis=2)) > 0.01
        rows = []
        for i in range(n):
            for j in range(n):
                sl = (slice(i * w, (i + 1) * w), slice(j * w, (j + 1) * w))
                intact = ~crack[sl] & ~dmg[sl]; a = alb[sl][intact]
                rows.append((float(np.percentile(a, 95) - np.percentile(a, 5)), float(a.std()), float(crack[sl].mean()), float(dmg[sl].mean()),
                             float(tone[sl].mean())))
        R = np.array(rows)
        names = ("intact_p95_p5", "intact_std", "crack_fraction", "damage_fraction", "crack_tone_fraction")
        result["modes"][mode] = {k: {"mean": round(float(R[:, c].mean()), 5), "sd": round(float(R[:, c].std()), 5)} for c, k in enumerate(names)}
        result["modes"][mode]["albedo_mean_srgb"] = round(float(alb.mean()), 5)
        np.save(os.path.join(out, "%s_albedo_srgb.npy" % mode), alb[: w, : w].astype(np.float32))
        print("UVSTATS", mode, json.dumps(result["modes"][mode]))
    with open(os.path.join(out, "uv_stats.json"), "w") as f: json.dump(result, f, indent=1)
    print("UVSTATS OK")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
