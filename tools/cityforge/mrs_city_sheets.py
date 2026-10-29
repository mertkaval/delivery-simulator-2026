"""Evidence sheets for Port Halden's MRS streets (docs/roads/city): CityForge streets | Mert Road Studio streets
from the same game cameras (tests/capture_cityforge.gd), street-level views of the MRS streets, and the Blender
QA renders (tools/cityforge/mrs_streets_render.py).
    python tools/cityforge/mrs_city_sheets.py <before_dir> <after_dir> <blender_renders_dir> <out_dir>"""
import os, sys
from PIL import Image, ImageDraw

before, after, renders, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
made = []


def label(im, text, xy=(10, 8)):
    d = ImageDraw.Draw(im)
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 8 * len(text) + 6, xy[1] + 15], fill=(20, 20, 22))
    d.text(xy, text, fill=(255, 230, 120))
    return im


def save(im, name):
    p = os.path.join(out, name); im.convert("RGB").save(p, quality=85); made.append(p)


W = 960
for v in ("aerial", "street", "corner", "downtown", "night", "night_downtown"):
    a, b = os.path.join(before, "cf_%s.png" % v), os.path.join(after, "cf_%s.png" % v)
    if not (os.path.exists(a) and os.path.exists(b)): continue
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    h = int(W * ia.size[1] / ia.size[0])
    S = Image.new("RGB", (W * 2 + 6, h), (24, 24, 26))
    S.paste(ia.resize((W, h)), (0, 0)); S.paste(ib.resize((W, h)), (W + 6, 0))
    label(S, "%s: CityForge streets (before)" % v); label(S, "Mert Road Studio streets (after)", (W + 16, 8))
    save(S, "compare_%s.jpg" % v)
views = [v for v in ("junction", "junction_close", "sidewalk", "busstop") if os.path.exists(os.path.join(after, "cf_%s.png" % v))]
if views:
    ims = [Image.open(os.path.join(after, "cf_%s.png" % v)).convert("RGB") for v in views]
    h = int(W * ims[0].size[1] / ims[0].size[0])
    S = Image.new("RGB", (W * 2, h * ((len(ims) + 1) // 2)), (24, 24, 26))
    for i, (v, im) in enumerate(zip(views, ims)):
        S.paste(im.resize((W, h)), ((i % 2) * W, (i // 2) * h)); label(S, v, ((i % 2) * W + 10, (i // 2) * h + 8))
    save(S, "game_street_level.jpg")
if os.path.isdir(renders):
    ps = sorted(p for p in os.listdir(renders) if p.endswith(".png") and not p.startswith("sheet"))
    if ps:
        ims = [Image.open(os.path.join(renders, p)).convert("RGB") for p in ps]
        w = 640; h = int(w * ims[0].size[1] / ims[0].size[0]); cols = 3
        S = Image.new("RGB", (w * cols, h * ((len(ims) + cols - 1) // cols)), (24, 24, 26))
        for i, (p, im) in enumerate(zip(ps, ims)):
            S.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h)); label(S, p[:-4], ((i % cols) * w + 8, (i // cols) * h + 6))
        save(S, "blender_renders.jpg")
print("\n".join(made))
