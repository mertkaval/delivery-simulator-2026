"""procmat.imaging: PNG helpers that work inside Blender (numpy + bpy images; Blender bundles no Pillow) and in the
system Python (Pillow + numpy). No OpenCV.

    load(path) -> float32 array (H, W, C), rows top-down, 0..1     save(array, path)
    seam_metric(png) -> {edge_mad, interior_mad, ratio, ...}       tile(png, n=2, out=None)
    side_by_side(left, right, out, labels=("left", "right"))      Pillow; inside Blender it runs this file in the
                                                                   system Python (python -I imaging.py side_by_side ...)
CLI (system Python):  python -I imaging.py side_by_side L.png R.png OUT.png [--labels A B]
                      python -I imaging.py seam X.png            python -I imaging.py tile X.png 2 OUT.png
This file imports nothing from the package, so it also runs standalone."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False
try:
    import bpy
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False


# ------------------------------------------------------------------------------------------ load / save
def load(path):
    """Float32 (H, W, C) top-down in 0..1 (the stored values, no colour management)."""
    if HAVE_PIL:
        im = Image.open(path)
        if im.mode not in ("RGB", "RGBA", "L", "I;16", "I"): im = im.convert("RGBA")
        a = np.asarray(im)
        if a.dtype == np.uint16 or im.mode in ("I;16", "I"): a = a.astype(np.float32) / 65535.0
        else: a = a.astype(np.float32) / 255.0
        return a[..., None] if a.ndim == 2 else a
    if not HAVE_BPY: raise RuntimeError("neither Pillow nor bpy available")
    img = bpy.data.images.load(os.path.abspath(path), check_existing=False)
    try:
        try: img.colorspace_settings.name = "Non-Color"     # stored values (16-bit / float files are not linearised)
        except (TypeError, ValueError): pass
        w, h = img.size; c = img.channels
        px = np.empty(w * h * c, dtype=np.float32); img.pixels.foreach_get(px)
        return px.reshape(h, w, c)[::-1].copy()
    finally:
        bpy.data.images.remove(img)


def save(a, path):
    a = np.clip(np.asarray(a, dtype=np.float32), 0.0, 1.0)
    if a.ndim == 2: a = a[..., None]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if HAVE_PIL:
        u8 = (a * 255.0 + 0.5).astype(np.uint8)
        Image.fromarray(u8[..., 0] if u8.shape[2] == 1 else u8).save(path)
        return path
    h, w, c = a.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :min(c, 4)] = a[..., :min(c, 4)]
    if c == 1: rgba[..., 1] = rgba[..., 2] = a[..., 0]
    img = bpy.data.images.new("pm_save_tmp", w, h, alpha=True, float_buffer=False)
    try:
        img.colorspace_settings.name = "Non-Color"       # write the values as they are
        img.pixels.foreach_set(rgba[::-1].ravel())
        img.filepath_raw = os.path.abspath(path); img.file_format = "PNG"; img.save()
    finally:
        bpy.data.images.remove(img)
    return path


# ------------------------------------------------------------------------------------------ seams / tiles
def seam_metric(path, channels=3):
    """How seamless a tile is: the mean absolute difference across the wrap-around seams (last column vs first,
    last row vs first) against the mean absolute difference of neighbouring pixels inside the image. ratio ~ 1:
    the seam looks like any other pixel step (tiles); ratio >> 1: a visible seam."""
    a = load(path)[..., :channels].astype(np.float64)
    colp = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2))        # every interior column pair
    rowp = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))        # every interior row pair
    ix, iy = colp.mean(), rowp.mean()
    ex = np.abs(a[:, 0] - a[:, -1]).mean(); ey = np.abs(a[0, :] - a[-1, :]).mean()
    interior = (ix + iy) / 2.0; edge = (ex + ey) / 2.0
    r = lambda v: round(float(v), 4)
    return {"edge_mad": round(float(edge), 6), "interior_mad": round(float(interior), 6), "ratio": r(edge / max(interior, 1e-9)),
            "ratio_x": r(ex / max(ix, 1e-9)), "ratio_y": r(ey / max(iy, 1e-9)),
            # one seam column is a small sample: compare it with the worst interior column / row pair as well
            "outlier_x": r(ex / max(colp.max(), 1e-9)), "outlier_y": r(ey / max(rowp.max(), 1e-9)),
            "pct_x": r((colp < ex).mean()), "pct_y": r((rowp < ey).mean()),
            "size": [int(a.shape[1]), int(a.shape[0])]}


def is_seamless(m, outlier=1.15, ratio=(0.6, 1.7)):
    """A seam_metric() result that looks like any other pixel step: each seam no worse than the worst interior
    column / row pair (x outlier) and within `ratio` of the mean step."""
    return (m["outlier_x"] <= outlier and m["outlier_y"] <= outlier and ratio[0] <= m["ratio_x"] <= ratio[1]
            and ratio[0] <= m["ratio_y"] <= ratio[1])


def tile(path, n=2, out=None):
    """An n x n repeat of a tile (to look at the seams)."""
    a = load(path)
    out = out or os.path.splitext(path)[0] + "_x%d.png" % n
    return save(np.tile(a, (n, n, 1)), out)


def stats(path):
    """Mean / std / min / max of an image (sanity checks of renders)."""
    a = load(path)[..., :3]
    return {"mean": round(float(a.mean()), 4), "std": round(float(a.std()), 4), "min": round(float(a.min()), 4), "max": round(float(a.max()), 4)}


# ------------------------------------------------------------------------------------------ side by side
_PY = {}


def find_python():
    """A system Python that has Pillow (PM_PYTHON, then python / python3 / py on PATH; not the Store alias)."""
    if "exe" in _PY: return _PY["exe"]
    cands = [os.environ.get("PM_PYTHON"), shutil.which("python"), shutil.which("python3"), shutil.which("py")]
    exe = None
    for c in cands:
        if not c or "WindowsApps" in c: continue
        try:
            r = subprocess.run([c, "-I", "-c", "import PIL, numpy"], capture_output=True, timeout=60)
            if r.returncode == 0: exe = c; break
        except (OSError, subprocess.SubprocessError):
            continue
    _PY["exe"] = exe
    return exe


def _font(size):
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()


def _pil_side_by_side(paths, out, labels, height=None, gap=8, bar=40):
    ims = [Image.open(p).convert("RGB") for p in paths]
    h = height or max(im.height for im in ims)
    ims = [im if im.height == h else im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS) for im in ims]
    W = sum(im.width for im in ims) + gap * (len(ims) - 1)
    has = labels is not None
    canvas = Image.new("RGB", (W, h + (bar if has else 0)), (18, 18, 18))
    x = 0; font = _font(22); d = ImageDraw.Draw(canvas)
    for i, im in enumerate(ims):
        canvas.paste(im, (x, bar if has else 0))
        if has and i < len(labels) and labels[i]:
            d.text((x + 10, 8), str(labels[i]), fill=(235, 235, 235), font=font)
        x += im.width + gap
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    canvas.save(out)
    return out


def side_by_side(left, right, out, labels=("left", "right"), extra=()):
    """left | right (| extra ...) at the same height with a label bar, written to `out` (Pillow). Inside Blender
    (no Pillow) the system Python runs this file; without one, the images are joined with numpy and no labels."""
    paths = [left, right] + list(extra)
    labels = list(labels) if labels is not None else None
    if HAVE_PIL: return _pil_side_by_side(paths, out, labels)
    exe = find_python()
    if exe:
        cmd = [exe, "-I", os.path.abspath(__file__), "side_by_side"] + [os.path.abspath(p) for p in paths[:2]] + [os.path.abspath(out)]
        for p in paths[2:]: cmd += ["--extra", os.path.abspath(p)]
        if labels: cmd += ["--labels"] + [str(x) for x in labels]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.exists(out): return out
        print("[procmat.imaging] system Python failed (%s): %s" % (exe, (r.stderr or "")[-400:]))
    print("[procmat.imaging] no Pillow: joining without labels")
    arrs = [load(p)[..., :3] for p in paths]
    h = max(a.shape[0] for a in arrs)
    arrs = [np.pad(a, ((0, h - a.shape[0]), (0, 8), (0, 0))) for a in arrs]
    return save(np.concatenate(arrs, axis=1), out)


def _main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="imaging.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("side_by_side"); s.add_argument("left"); s.add_argument("right"); s.add_argument("out")
    s.add_argument("--labels", nargs="*"); s.add_argument("--extra", action="append", default=[])
    q = sub.add_parser("seam"); q.add_argument("png")
    t = sub.add_parser("tile"); t.add_argument("png"); t.add_argument("n", type=int); t.add_argument("out")
    a = p.parse_args(argv)
    if a.cmd == "side_by_side": print(side_by_side(a.left, a.right, a.out, a.labels, a.extra))
    elif a.cmd == "seam": print(json.dumps(seam_metric(a.png)))
    else: print(tile(a.png, a.n, a.out))


if __name__ == "__main__":
    _main(sys.argv[1:])
