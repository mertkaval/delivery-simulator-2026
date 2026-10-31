"""Metre semantics of PM_Asphalt's size inputs (object mode): a 2 m plane at Pattern Size 1 / Aggregate Size 1/110 must
bake the same albedo as a 4 m plane at Pattern Size 2 / Aggregate Size 2/110 (every texture scaled by 2), and a 4 m
plane at Pattern Size 2 with the aggregate kept at 1/110 m must differ only where pebbles show (damaged patches).

    blender --background --factory-startup --python metres_check.py -- OUT_DIR"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if LIB not in sys.path: sys.path.insert(0, LIB)
import procmat  # noqa: E402
from procmat import bake as B, core, imaging  # noqa: E402


def main(out):
    procmat.discover(verbose=False); procmat.build("asphalt")
    mat = core.material("PM_Asphalt"); node = core.group_node(mat)
    keep = {k: node.inputs[k].default_value for k in ("Pattern Size", "Aggregate Size")}
    runs = {"A_2m_ps1": (2.0, 1.0, 1 / 110), "B_4m_ps2_agg2": (4.0, 2.0, 2 / 110), "C_4m_ps2_agg1": (4.0, 2.0, 1 / 110)}
    img = {}
    for k, (size, ps, agg) in runs.items():
        core.set_inputs(mat, **{"Pattern Size": ps, "Aggregate Size": agg})
        p = B.bake(mat, out, tile=size, res=512, samples=16, maps=["albedo"], use_uv=False, plane_size=size, prefix=k, verbose=False)
        img[k] = imaging.load(p["albedo"])[..., :3]
    core.set_inputs(mat, **keep)
    A, Bm, C = img["A_2m_ps1"], img["B_4m_ps2_agg2"], img["C_4m_ps2_agg1"]
    res = {"A_vs_B_mad": float(np.abs(A - Bm).mean()), "A_vs_B_corr": float(np.corrcoef(A.ravel(), Bm.ravel())[0, 1]),
           "B_vs_C_mad": float(np.abs(Bm - C).mean()), "B_vs_C_share_px_differing_gt_2_255": float((np.abs(Bm - C).max(axis=2) > 2 / 255).mean()),
           "albedo_mean": float(A.mean())}
    res["ok"] = res["A_vs_B_mad"] < 0.002 and res["A_vs_B_corr"] > 0.99 and res["B_vs_C_mad"] > res["A_vs_B_mad"]
    with open(os.path.join(out, "metres_check.json"), "w") as f: json.dump(res, f, indent=1)
    print("METRES", "OK" if res["ok"] else "FAIL", json.dumps(res))
    return res["ok"]


if __name__ == "__main__":
    good = main(sys.argv[sys.argv.index("--") + 1])
    sys.stdout.flush(); sys.exit(0 if good else 1)
