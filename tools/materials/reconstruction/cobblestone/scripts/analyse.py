"""Stone size statistics + object-mode constant-size check from measure_bakes.py output.
    python analyse.py DIR"""
import json, sys, os
import numpy as np
from PIL import Image

D = sys.argv[1]


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)[..., 0] / 255.0


def label(mask):
    """4-connected component labels by iterated min propagation (numpy only)."""
    H, W = mask.shape
    lab = np.where(mask, np.arange(H * W, dtype=np.int64).reshape(H, W), H * W + 1)
    big = H * W + 1
    for _ in range(2000):
        p = np.pad(lab, 1, constant_values=big)
        nb = np.minimum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        nb = np.where(mask, nb, big)
        # pointer jumping
        flat = nb.ravel(); idx = np.where(flat < big, flat, 0)
        nb2 = np.where(mask, np.minimum(nb, flat[idx].reshape(H, W)), big)
        if np.array_equal(nb2, lab): break
        lab = nb2
    return lab, big


def stones(path, metres):
    h = load(path); mask = h > 0.5
    lab, big = label(mask)
    H, W = mask.shape; px = metres / W
    # drop components touching the border
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {big}
    ids, areas = np.unique(lab[mask], return_counts=True)
    keep = np.array([i not in border for i in ids])
    a = areas[keep] * px * px
    a = a[a > (0.02 ** 2)]                       # ignore specks < 2 cm square
    d = np.sqrt(4 * a / np.pi)
    w = a / a.sum()
    order = np.argsort(d); cw = np.cumsum(w[order])
    return {"stone_fraction": round(float(mask.mean()), 3), "n_stones": int(len(d)),
            "stones_per_m2": round(len(d) / (metres * metres * (1 - 2 * 0)), 1),
            "eqdiam_median_cm": round(float(np.median(d)) * 100, 1),
            "eqdiam_p10_cm": round(float(np.percentile(d, 10)) * 100, 1),
            "eqdiam_p90_cm": round(float(np.percentile(d, 90)) * 100, 1),
            "eqdiam_areaweighted_median_cm": round(float(d[order][np.searchsorted(cw, 0.5)]) * 100, 1),
            "frac_area_in_10_25cm": round(float(a[(d >= 0.10) & (d <= 0.25)].sum() / a.sum()), 3)}


res = {}
for name, m in (("obj4m", 4.0), ("uv4m", 4.0), ("obj1m", 1.0)):
    p = os.path.join(D, name + "_height.png")
    if os.path.exists(p): res[name] = stones(p, m)
# object mode: 1 m plane == the centre metre of the 4 m plane
a1 = np.asarray(Image.open(os.path.join(D, "obj1m_albedo.png")).convert("RGB"), dtype=np.float32) / 255
a4 = np.asarray(Image.open(os.path.join(D, "obj4m_albedo.png")).convert("RGB"), dtype=np.float32) / 255
c = a4[384:640, 384:640]
res["obj_1m_vs_4m_centre"] = {"mad": round(float(np.abs(a1 - c).mean()), 4),
                              "corr": round(float(np.corrcoef(a1.ravel(), c.ravel())[0, 1]), 4)}
h1 = load(os.path.join(D, "obj1m_height.png")); h4 = load(os.path.join(D, "obj4m_height.png"))[384:640, 384:640]
res["obj_1m_vs_4m_centre_mask"] = {"mad": round(float(np.abs(h1 - h4).mean()), 4),
                                   "corr": round(float(np.corrcoef(h1.ravel(), h4.ravel())[0, 1]), 4)}
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(D, "analysis.json"), "w"), indent=1)
