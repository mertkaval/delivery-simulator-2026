"""Matched Blender | Godot comparison sheets for the street-block views (same camera list, cameras.json).

    python tools/roads/tests/compare_sheets.py <blender_renders_dir> <godot_dir> <out_dir> [view ...]

For each view name with both `blender_<view>.png` and `godot_<view>.png` (and the `_night` pair when present)
writes `<out_dir>/compare_<view>.jpg`: Blender left, Godot right, labelled, 960 px per side.
"""
import os, sys
from PIL import Image, ImageDraw


def pair(a, b, out, label_a="Blender (EEVEE)", label_b="Godot 4.7.2", w=960):
    ia = Image.open(a).convert("RGB"); ib = Image.open(b).convert("RGB")
    h = int(w * ia.size[1] / ia.size[0])
    ia = ia.resize((w, h)); ib = ib.resize((w, int(w * ib.size[1] / ib.size[0]))).crop((0, 0, w, h))
    S = Image.new("RGB", (w * 2 + 6, h + 26), (24, 24, 26))
    S.paste(ia, (0, 26)); S.paste(ib, (w + 6, 26))
    d = ImageDraw.Draw(S)
    d.text((8, 6), label_a + "   " + os.path.basename(a), fill=(255, 220, 120)); d.text((w + 14, 6), label_b + "   " + os.path.basename(b), fill=(140, 220, 255))
    S.save(out, quality=88)
    return out


def main(bdir, gdir, odir, views=None):
    os.makedirs(odir, exist_ok=True)
    names = views or sorted({f[len("blender_"):-4] for f in os.listdir(bdir) if f.startswith("blender_") and f.endswith(".png")})
    out = []
    for v in names:
        a = os.path.join(bdir, "blender_%s.png" % v); b = os.path.join(gdir, "godot_%s.png" % v)
        if os.path.exists(a) and os.path.exists(b):
            out.append(pair(a, b, os.path.join(odir, "compare_%s.jpg" % v)))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    print("\n".join(main(a[0], a[1], a[2], a[3:] or None)))
