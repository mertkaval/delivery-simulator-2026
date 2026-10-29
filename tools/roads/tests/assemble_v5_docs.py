"""Copy / compose the v5 evidence images into docs/roads/v5 (JPEG, Git LFS): matched Blender | Godot sheets,
frontage rule adaptation (before / after), recording frame strips, asset-library thumbnails, foliage and hardware
comparison sheets.   python tools/roads/tests/assemble_v5_docs.py"""
import os, shutil, subprocess
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
F = os.path.join(ROOT, "tmp", "roads", "v5", "final")
D = os.path.join(ROOT, "docs", "roads", "v5"); os.makedirs(D, exist_ok=True)
out = []


def save(im, name, q=86):
    p = os.path.join(D, name); im.convert("RGB").save(p, quality=q); out.append(p)


def label(im, text, pos=(8, 6)):
    ImageDraw.Draw(im).text(pos, text, fill=(255, 230, 120)); return im


# matched Blender | Godot sheets (same camera list)
for v in ("pedestrian_avenue", "cyclist", "tree_close", "park", "overhead", "busstop", "bridge_2_ramp", "bridge_3_deck", "bridge_4_stairs",
          "shop_front", "shop_door", "shop_yard", "shop_sidewalk", "shop_front_night", "shop_sidewalk_night", "bridge_3_deck_night",
          "busstop_night", "pedestrian_avenue_night", "aerial_bridge_night"):
    p = os.path.join(F, "compare", "compare_%s.jpg" % v)
    if os.path.exists(p): save(Image.open(p), "compare_%s.jpg" % v)

# frontage: the rules adapting when the shop moves 8 m along the street (top views)
a = os.path.join(F, "renders", "blender_frontage_top.png"); b = os.path.join(F, "renders", "blender_frontage_moved_top.png")
if os.path.exists(a) and os.path.exists(b):
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    w = 900; h = int(w * ia.size[1] / ia.size[0])
    S = Image.new("RGB", (w * 2 + 6, h + 24), (24, 24, 26)); S.paste(ia.resize((w, h)), (0, 24)); S.paste(ib.resize((w, h)), (w + 6, 24))
    label(S, "shop at station 22 m (baseline)"); label(S, "shop moved to 14 m: driveway kerb drop, entrance envelope, bike rack follow", (w + 14, 6))
    save(S, "frontage_rules_adapt.jpg")

# recording frame strips (4 frames per clip)
for sc, ts in (("junction", (3, 10, 16, 21)), ("street", (2, 6, 10, 14)), ("frontage", (3, 7, 13, 22)), ("footbridge", (3, 12, 24, 34)),
               ("trees", (1, 7, 13, 20)), ("night", (2, 7, 11, 16))):
    mp4 = os.path.join(F, "rec", "%s.mp4" % sc)
    if not os.path.exists(mp4): continue
    frames = []
    for t in ts:
        fp = os.path.join(F, "rec", "_f_%s_%d.jpg" % (sc, t))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", "-vf", "scale=480:-1", fp])
        if os.path.exists(fp): frames.append((t, Image.open(fp).convert("RGB")))
    if not frames: continue
    w, h = frames[0][1].size
    S = Image.new("RGB", (w * len(frames), h), (0, 0, 0))
    for i, (t, im) in enumerate(frames): S.paste(im, (i * w, 0)); label(S, "%s  %ds" % (sc, t), (i * w + 6, 4))
    save(S, "rec_%s.jpg" % sc)

# asset library thumbnails, foliage and hardware sheets made by their own tests
for src, dst in ((os.path.join(ROOT, "tmp", "roads", "v5", "library", "thumbnails_sheet.jpg"), "asset_library_thumbnails.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "foliage", "video", "frames", "sbs_matched_sheet.jpg"), "foliage_blender_godot_matched.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "foliage", "video", "frames", "dolly.jpg"), "foliage_lod_dolly_before_after.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "foliage", "hedges", "hedges_compare.jpg"), "foliage_hedges.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "hardware", "compare_lights.jpg"), "hardware_lights.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "hardware", "compare_signs.jpg"), "hardware_signs.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "hardware", "compare_barriers.jpg"), "hardware_barriers.jpg"),
                 (os.path.join(ROOT, "tmp", "roads", "v5", "hardware", "compare_footbridge_materials.jpg"), "hardware_footbridge_materials.jpg")):
    if os.path.exists(src):
        im = Image.open(src)
        if im.size[0] > 2400: im = im.resize((2400, int(2400 * im.size[1] / im.size[0])))
        save(im, dst)
print("\n".join(os.path.relpath(p, ROOT) for p in out))
print(len(out), "images,", round(sum(os.path.getsize(p) for p in out) / 1e6, 1), "MB")
