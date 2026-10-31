"""Side-by-side comparisons of the glass renders with the video (system Python: python -I compare.py ...; Pillow + numpy).

    python -I tools/materials/reconstruction/glass/scripts/compare.py --ours tmp/materials_glass/r1 --tag r1
           [--out tools/materials/reconstruction/glass/comparisons] [--label "round 1"]

For every material: the video's pane (a converged "Rendering Done" frame, pane box measured from the orange selection
outline) | our pane from the same camera (video mode of glass_scene.py), cropped to the same pane-relative region and
resized to the same height. Measures (luminance, written to compare_<tag>.json):
  ncc0 / ncc_peak / shift  normalised cross-correlation of the high-passed panes at zero shift and its best value within
                           +-6 % of the pane: a peak near zero shift = the same cell layout as the video (same object
                           coordinates and texture hashes), not just the same statistics
  wavelength               dominant feature wavelength (pane fraction) from the radially averaged power spectrum
  hf_contrast              std of the high-passed luminance (texture contrast through the glass)
Also the whole camera view (33:23) next to our full render.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GLASS = os.path.abspath(os.path.join(HERE, ".."))
EV = os.path.join(GLASS, "evidence")

# material -> (frame under evidence/, pane box (x0, y0, x1, y1) in frame pixels incl. the outline, label)
REFS = {
    "GlassCircles": ("a/frames/t1044_circles_viewport_look.jpg", (-121, 386, 698, 1205), "video 10:44.5 (Rendering Done)"),
    "GlassVoronoi": ("a/frames/t1626_voronoi_group_final_graph.jpg", (98, 545, 674, 1121), "video 16:26.5 (Rendering Done)"),
    "GlassCells": ("a/frames/t2207_cells_group_interior.jpg", (14, 448, 662, 1097), "video 22:07.5 (Rendering Done)"),
    "GlassWavy": ("validation/t2520_wavy_rendering_done.png", (66, 542, 611, 1087), "video 25:20 (Rendering Done)"),
    "GlassBlobby": ("validation/t2936_blobby_rendering_done.png", (122, 559, 575, 1012), "video 29:36 (Rendering Done)"),
    "GlassFrosted": ("b/frames/t3303_frosted_final_group_node.jpg", (77, 483, 643, 1051), "video 33:03 (Rendering Done)"),
}
FULL_REF = ("b/frames/t3323_closing_viewport_all_panes.jpg", (84, 480, 995, 992), "video 33:23 camera view (sample 1/100)")
INSET = 4          # px of the outline / edge to drop on every side


def _font(size):
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()


def ref_pane(name):
    f, (x0, y0, x1, y1), label = REFS[name]
    im = Image.open(os.path.join(EV, f)).convert("RGB")
    W, H = im.size
    w, h = x1 - x0, y1 - y0
    vx0, vy0, vx1, vy1 = max(x0 + INSET, 0), max(y0 + INSET, 0), min(x1 - INSET, W), min(y1 - INSET, H)
    frac = ((vx0 - x0) / w, (vy0 - y0) / h, (vx1 - x0) / w, (vy1 - y0) / h)     # visible part, pane-relative
    return im.crop((vx0, vy0, vx1, vy1)), frac, label


def our_pane(path, frac):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.crop((int(round(frac[0] * w)), int(round(frac[1] * h)), int(round(frac[2] * w)), int(round(frac[3] * h))))


def lum(im, size=None):
    if size: im = im.resize(size, Image.LANCZOS)
    a = np.asarray(im).astype(np.float64) / 255.0
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def highpass(L, sigma_frac=0.03):
    """L minus a box-blurred copy (feature scale: a few % of the pane)."""
    k = max(3, int(round(sigma_frac * L.shape[1])) | 1)
    pad = k // 2
    P = np.pad(L, pad, mode="reflect")
    c = np.cumsum(np.cumsum(P, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    blur = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    return L - blur[:L.shape[0], :L.shape[1]]


def ncc_search(A, B, max_shift):
    """Normalised cross-correlation of A and B over integer shifts |dx|, |dy| <= max_shift (overlap region)."""
    best = (-2.0, 0, 0); zero = None
    H, W = A.shape
    for dy in range(-max_shift, max_shift + 1, 1):
        for dx in range(-max_shift, max_shift + 1, 1):
            a = A[max(0, dy):H + min(0, dy), max(0, dx):W + min(0, dx)]
            b = B[max(0, -dy):H + min(0, -dy), max(0, -dx):W + min(0, -dx)]
            a = a - a.mean(); b = b - b.mean()
            d = np.sqrt((a * a).sum() * (b * b).sum())
            v = float((a * b).sum() / d) if d > 0 else 0.0
            if dx == 0 and dy == 0: zero = v
            if v > best[0]: best = (v, dx, dy)
    return zero, best


def red_mask(im, size):
    """True where a pane shows the red backdrop (excluded from the layout test: the monkeys' placement is class D)."""
    a = np.asarray(im.resize(size, Image.LANCZOS)).astype(np.float64) / 255.0
    return (a[..., 0] - np.maximum(a[..., 1], a[..., 2])) > 0.12


def grad_mag(L):
    """Gradient magnitude divided by its local mean (~6 % of the pane): cell edges independent of the background
    brightness behind the glass."""
    gy, gx = np.gradient(L)
    G = np.sqrt(gx * gx + gy * gy)
    return G / (G - highpass(G, 0.06) + 1e-3)


def masked_ncc(A, B, M, max_shift):
    """NCC of A and B over shifts, counting only pixels valid (M True) in both. Returns (zero, (best, dx, dy), second-best
    away from the peak)."""
    H, W = A.shape; vals = {}
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            sa = (slice(max(0, dy), H + min(0, dy)), slice(max(0, dx), W + min(0, dx)))
            sb = (slice(max(0, -dy), H + min(0, -dy)), slice(max(0, -dx), W + min(0, -dx)))
            m = M[sa] & M[sb]
            if m.sum() < 500: continue
            a = A[sa][m]; b = B[sb][m]; a = a - a.mean(); b = b - b.mean()
            d = np.sqrt((a * a).sum() * (b * b).sum())
            vals[(dx, dy)] = float((a * b).sum() / d) if d > 0 else 0.0
    (bx, by), best = max(vals.items(), key=lambda kv: kv[1])
    far = [v for (dx, dy), v in vals.items() if max(abs(dx - bx), abs(dy - by)) > 3]
    return vals.get((0, 0)), (best, bx, by), (max(far) if far else None), float(np.median(list(vals.values())))


def wavelength(L):
    """Dominant wavelength (fraction of the image width) of a high-passed image: peak of the radially averaged spectrum."""
    Hp = highpass(L)
    F = np.abs(np.fft.fftshift(np.fft.fft2(Hp - Hp.mean()))) ** 2
    h, w = F.shape
    yy, xx = np.indices(F.shape)
    r = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)       # cycles per pixel, normalised per axis
    bins = np.linspace(0.0, 0.5, 101)
    idx = np.digitize(r.ravel(), bins)
    prof = np.array([F.ravel()[idx == i].mean() if np.any(idx == i) else 0.0 for i in range(1, len(bins))])
    centers = (bins[1:] + bins[:-1]) / 2
    sel = centers > 0.01                                                  # ignore the lowest frequencies (lighting)
    k = np.argmax(prof[sel]); f = centers[sel][k]
    return round(float(1.0 / (f * w)), 4) if f > 0 else None, prof


def label_bar(canvas_w, labels, xs, bar=44):
    bar_im = Image.new("RGB", (canvas_w, bar), (18, 18, 18)); d = ImageDraw.Draw(bar_im); font = _font(20)
    for x, t in zip(xs, labels): d.text((x + 8, 10), t, fill=(235, 235, 235), font=font)
    return bar_im


def pair(left, right, labels, out, height=640):
    ims = [im.resize((max(1, round(im.width * height / im.height)), height), Image.LANCZOS) for im in (left, right)]
    W = ims[0].width + 8 + ims[1].width
    canvas = Image.new("RGB", (W, height + 44), (18, 18, 18))
    canvas.paste(label_bar(W, labels, (0, ims[0].width + 8)), (0, 0))
    canvas.paste(ims[0], (0, 44)); canvas.paste(ims[1], (ims[0].width + 8, 44))
    canvas.save(out)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ours", required=True); p.add_argument("--tag", default="r1"); p.add_argument("--label", default=None)
    p.add_argument("--light", default="bundled HDRI x 0.5", help="lighting caption (D6: the video HDRI is not available)")
    p.add_argument("--out", default=os.path.join(GLASS, "comparisons"))
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    label = a.label or a.tag
    res = {}
    for name in REFS:
        rp, frac, rlabel = ref_pane(name)
        op = our_pane(os.path.join(a.ours, "video_%s.png" % name), frac)
        out = os.path.join(a.out, "%s_%s_video_vs_ours.png" % (name, a.tag))
        pair(rp, op, (rlabel, "ours %s (%s: lighting differs, D6)" % (label, a.light)), out)
        size = (512, int(round(512 * rp.height / rp.width)))
        La, Lb = lum(rp, size), lum(op, size)
        Ha, Hb = highpass(La), highpass(Lb)
        z, (peak, dx, dy) = ncc_search(Ha, Hb, int(0.06 * size[0]))
        wa, _ = wavelength(La); wb, _ = wavelength(Lb)
        M = ~(red_mask(rp, size) | red_mask(op, size))
        Ga, Gb = grad_mag(highpass(La, 0.02)), grad_mag(highpass(Lb, 0.02))
        gz, (gpeak, gdx, gdy), gfar, gmed = masked_ncc(Ga, Gb, M, int(0.04 * size[0]))
        res[name] = {"file": os.path.relpath(out, GLASS).replace("\\", "/"), "visible_pane_fraction": [round(v, 3) for v in frac],
                     "ncc0": round(z, 3), "ncc_peak": round(peak, 3), "peak_shift_px512": [dx, dy],
                     "layout_ncc0": round(gz, 3) if gz is not None else None, "layout_peak": round(gpeak, 3),
                     "layout_peak_shift_px512": [gdx, gdy], "layout_best_elsewhere": round(gfar, 3) if gfar is not None else None,
                     "layout_median": round(gmed, 3), "valid_fraction": round(float(M.mean()), 3),
                     "wavelength_video": wa, "wavelength_ours": wb,
                     "hf_contrast_video": round(float(Ha.std()), 4), "hf_contrast_ours": round(float(Hb.std()), 4),
                     "mean_lum_video": round(float(La.mean()), 3), "mean_lum_ours": round(float(Lb.mean()), 3)}
        print(name, json.dumps(res[name]))
    # whole camera view
    f, box, rlabel = FULL_REF
    ref = Image.open(os.path.join(EV, f)).convert("RGB").crop(box)
    ours = Image.open(os.path.join(a.ours, "video_full_grey.png")).convert("RGB")
    out = os.path.join(a.out, "all_panes_%s_video_vs_ours.png" % a.tag)
    pair(ref, ours, (rlabel, "ours %s, same camera (50 mm, 4.435 m)" % label), out, height=720)
    res["all_panes"] = {"file": os.path.relpath(out, GLASS).replace("\\", "/")}
    with open(os.path.join(a.out, "compare_%s.json" % a.tag), "w", encoding="utf-8") as fh: json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()
