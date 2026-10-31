"""Side-by-side comparison: a crop of a video frame | our render (RGBA composited on the video's background tone).

python -I compare.py VIDEO_FRAME CROP(x0,y0,x1,y1) OUR_PNG OUT_PNG [--labels "video" "ours"] [--bg auto|r,g,b] [--size 900]
Prints simple statistics of both crops (mean RGB, luminance std) inside the sphere disc (our alpha / a centred disc).
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageDraw


def disc_mask(w, h, frac=0.85):
    yy, xx = np.mgrid[0:h, 0:w]
    r = min(w, h) / 2.0 * frac
    return ((xx - w / 2.0) ** 2 + (yy - h / 2.0) ** 2) <= r * r


def stats(a, m):
    px = a[m][:, :3].astype(np.float64) / 255.0
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    return {"mean_rgb": [round(float(x), 3) for x in px.mean(0)], "lum_mean": round(float(lum.mean()), 3),
            "lum_std": round(float(lum.std()), 3), "lum_p10": round(float(np.percentile(lum, 10)), 3),
            "lum_p90": round(float(np.percentile(lum, 90)), 3)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("frame"); p.add_argument("crop"); p.add_argument("ours"); p.add_argument("out")
    p.add_argument("--labels", nargs=2, default=("video", "ours")); p.add_argument("--bg", default="auto")
    p.add_argument("--size", type=int, default=900); p.add_argument("--disc", type=float, default=0.85)
    a = p.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.crop.split(","))
    v = Image.open(a.frame).convert("RGB").crop((x0, y0, x1, y1))
    o = Image.open(a.ours).convert("RGBA")
    if a.bg == "auto":
        va = np.asarray(v); bg = tuple(int(c) for c in np.median(np.concatenate([va[:20, :20].reshape(-1, 3), va[:20, -20:].reshape(-1, 3)]), 0))
    else:
        bg = tuple(int(c) for c in a.bg.split(","))
    base = Image.new("RGBA", o.size, bg + (255,)); base.alpha_composite(o); o = base.convert("RGB")
    S = a.size
    v = v.resize((int(S * v.width / v.height), S), Image.LANCZOS); o = o.resize((int(S * o.width / o.height), S), Image.LANCZOS)
    W = v.width + o.width + 10
    out = Image.new("RGB", (W, S + 40), (20, 20, 20)); out.paste(v, (0, 40)); out.paste(o, (v.width + 10, 40))
    d = ImageDraw.Draw(out); d.text((10, 12), a.labels[0], fill=(255, 255, 255)); d.text((v.width + 20, 12), a.labels[1], fill=(255, 255, 255))
    out.save(a.out)
    va = np.asarray(v); oa = np.asarray(o)
    print("video", stats(va, disc_mask(va.shape[1], va.shape[0], a.disc)))
    print("ours ", stats(oa, disc_mask(oa.shape[1], oa.shape[0], a.disc)))
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
