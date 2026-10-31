"""Damaged-patch coverage of the video's final render against PM_Asphalt's spread across views (audit ASP-2).

One detector for every image: the pebbles of a damaged patch are 9 mm cells (~5-6 px at the video's pixel scale) with a
crumpled relief, darkened by the damage ramp. Score (energy()): log10 of the local energy of the fine band (DoG sigma
1.2 - 2.5 px) over that of the mid band (4 - 12 px), plus local darkness (log luminance, sigma 8 px minus sigma 40 px);
a pixel is "pebbled" when the score exceeds a threshold T. Raw band energy alone does not separate patches from the
intact relief (d' ~ 0). Only the lit region is scored (inside 0.85 of the sphere's image radius and smoothed luminance above LIT_MIN in both
the video and the view, so shadow and limb are excluded the same way).

T is calibrated on PM_Asphalt's own views, where the truth is known (v<i>_mask.png: damage_mask_ramp < 0.5): the T
that makes the detected fraction equal the true fraction on average. Then: per-view detected fraction (our spread),
the detector's error against the truth, and the video's detected fraction with the same T and region.

    python -I damage_detect.py VIDEO_FRAME VIEWS_DIR OUT_JSON [--crop 630,98,1301] [--extra NAME=DIR ...] [--panel OUT.jpg]
"""
import json
import os
import sys

import numpy as np
from PIL import Image

LIT_MIN = 0.06          # smoothed display luminance (0..1) below this = shadow, not scored
R_FRAC = 0.85


def gauss(img, s):
    """Gaussian blur through the FFT (wrap-around is harmless: the sphere sits on black)."""
    h, w = img.shape
    y = np.fft.fftfreq(h)[:, None]; x = np.fft.fftfreq(w)[None, :]
    k = np.exp(-2.0 * (np.pi * s) ** 2 * (x * x + y * y))
    return np.real(np.fft.ifft2(np.fft.fft2(img) * k))


def lum(path, crop=None):
    im = Image.open(path).convert("RGB")
    if crop: x, y, s = crop; im = im.crop((x, y, x + s, y + s))
    a = np.asarray(im, np.float32) / 255.0
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def disk(L):
    """Sphere centre / radius from the non-black silhouette."""
    m = L > 0.004
    ys, xs = np.nonzero(m)
    cy, cx = ys.mean(), xs.mean(); r = np.sqrt(m.sum() / np.pi)
    yy, xx = np.mgrid[:L.shape[0], :L.shape[1]]
    return np.hypot(yy - cy, xx - cx) / r


def energy(L):
    """Pebble score: fine-band texture energy relative to the mid band (pebbles are finer than the base cells and the
    crack network) plus local darkness (the patches are darkened and recessed), each divided by its spread on the
    intact surface of our views, smoothed into blobs."""
    g = np.log(L + 0.01)
    b1 = gauss(g, 1.2) - gauss(g, 2.5); b2 = gauss(g, 4.0) - gauss(g, 12.0)
    ratio = np.log10(gauss(b1 * b1, 10.0) + 1e-9) - np.log10(gauss(b2 * b2, 10.0) + 1e-9)
    dark = -(gauss(g, 8.0) - gauss(g, 40.0))
    return gauss(ratio / 0.20 + dark / 0.11, 4.0)


def region(L, rr):
    return (rr < R_FRAC) & (gauss(L, 6.0) > LIT_MIN)


def load_views(d):
    out = []
    i = 0
    while os.path.exists(os.path.join(d, "v%02d_lit.png" % i)):
        L = lum(os.path.join(d, "v%02d_lit.png" % i))
        mp = os.path.join(d, "v%02d_mask.png" % i)
        M = lum(mp) < 0.5 if os.path.exists(mp) else None
        out.append((L, M)); i += 1
    return out


def main(argv):
    video, vdir, out_json = argv[:3]
    crop = (630, 98, 1301)
    if "--crop" in argv: crop = tuple(int(v) for v in argv[argv.index("--crop") + 1].split(","))
    extra = [a.split("=", 1) for i, a in enumerate(argv) if i > 0 and argv[i - 1] == "--extra"]
    Lv = lum(video, crop); rrv = disk(Lv); Ev = energy(Lv); Rv = region(Lv, rrv)
    views = load_views(vdir)
    Es = [energy(L) for L, _ in views]
    regs = [region(L, disk(L)) & Rv for L, _ in views]          # the same lit region as the video
    truth = [float(M[r].mean()) for (L, M), r in zip(views, regs)]
    grid = np.linspace(-4.0, 8.0, 1201)
    det = np.array([[float((E[r] > t).mean()) for t in grid] for E, r in zip(Es, regs)])
    T = float(grid[np.argmin(np.abs(det.mean(axis=0) - np.mean(truth)))])
    k = int(np.argmin(np.abs(grid - T)))
    ours = det[:, k]
    iou = []
    for E, r, (L, M) in zip(Es, regs, views):
        d_ = (E > T) & r; t_ = M & r
        iou.append(float((d_ & t_).sum() / max((d_ | t_).sum(), 1)))
    vid = float((Ev[Rv] > T).mean())
    res = {"threshold_log10_energy": round(T, 3), "region_px_video": int(Rv.sum()),
           "true_fraction_per_view": [round(x, 4) for x in truth],
           "detected_fraction_per_view": [round(float(x), 4) for x in ours],
           "true_mean": round(float(np.mean(truth)), 4), "true_sd": round(float(np.std(truth)), 4),
           "true_min": round(float(np.min(truth)), 4), "true_max": round(float(np.max(truth)), 4),
           "detected_mean": round(float(ours.mean()), 4), "detected_sd": round(float(ours.std()), 4),
           "detected_min": round(float(ours.min()), 4), "detected_max": round(float(ours.max()), 4),
           "detector_abs_err_mean": round(float(np.mean(np.abs(ours - np.array(truth)))), 4),
           "detector_corr_truth": round(float(np.corrcoef(ours, truth)[0, 1]), 3),
           "iou_mean": round(float(np.mean(iou)), 3),
           "video_detected_fraction": round(vid, 4),
           "video_z": round((vid - float(ours.mean())) / max(float(ours.std()), 1e-9), 2),
           "views_above_video": int((ours >= vid).sum()), "views": len(views)}
    # energy level inside detected patches (how strong / dark the pebbles read), video vs ours
    res["video_energy_in_detected_p50"] = round(float(np.median(Ev[Rv & (Ev > T)])), 3) if (Rv & (Ev > T)).any() else None
    res["ours_energy_in_detected_p50"] = round(float(np.median(np.concatenate([E[r & (E > T)] for E, r in zip(Es, regs)]))), 3)
    res["video_lum_in_detected_p50"] = round(float(np.median(gauss(Lv, 3.0)[Rv & (Ev > T)])), 4)
    res["ours_lum_in_detected_p50"] = round(float(np.median(np.concatenate([gauss(L, 3.0)[r & (E > T)] for (L, _), E, r in zip(views, Es, regs)]))), 4)
    for name, d in extra:
        vs = load_views(d)
        fr = []; tr = []
        for L, M in vs:
            r = region(L, disk(L)) & Rv; E = energy(L)
            fr.append(float((E[r] > T).mean()))
            if M is not None: tr.append(float(M[r].mean()))
        res["extra_" + name] = {"detected_mean": round(float(np.mean(fr)), 4), "detected_sd": round(float(np.std(fr)), 4),
                                "true_mean": round(float(np.mean(tr)), 4) if tr else None, "views": len(vs)}
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, "w") as f: json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if "per_view" not in k}, indent=1))
    if "--panel" in argv:
        panel = argv[argv.index("--panel") + 1]
        def over(L, E, r, M=None):
            g = np.clip(L * 2.2, 0, 1); rgb = np.stack([g, g, g], -1)
            d_ = (E > T) & r
            rgb[d_] = rgb[d_] * 0.45 + np.array([0.55, 0.12, 0.0])
            edge = r & ~np.roll(r, 2, 0) | r & ~np.roll(r, 2, 1)
            rgb[edge] = (0.0, 0.6, 1.0)
            if M is not None:
                mb = (M & r) & ~(np.roll(M, 1, 0) & np.roll(M, 1, 1) & np.roll(M, -1, 0) & np.roll(M, -1, 1))
                rgb[mb] = (1.0, 1.0, 0.0)
            return (rgb * 255).astype(np.uint8)
        L0, M0 = views[0]
        tiles = [over(Lv, Ev, Rv), over(L0, Es[0], regs[0], M0)]
        # the view with the most detected damage, for scale
        j = int(np.argmax(ours)); tiles.append(over(views[j][0], Es[j], regs[j], views[j][1]))
        im = Image.fromarray(np.hstack(tiles)); im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        im.save(panel, quality=90)
        print("panel", panel, "(video | view 0 | view %d; red = detected pebbles, yellow = true mask edge, blue = scored region)" % j)


if __name__ == "__main__":
    main(sys.argv[1:])
