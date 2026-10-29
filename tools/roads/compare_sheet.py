"""Blender vs Godot comparison sheet (system Python + Pillow):
    python tools/roads/compare_sheet.py <blender_dir> <godot_dir> <out.jpg> view1 view2 ...
Each row: blender_<view>.png | godot_<view>.png, labelled; missing images are drawn grey."""
import os, sys
from PIL import Image, ImageDraw

bd, gd, out, views = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
W, H = 960, 540
S = Image.new("RGB", (W * 2, H * len(views)), (35, 35, 35))
d = ImageDraw.Draw(S)
for i, v in enumerate(views):
    for j, (folder, pre) in enumerate(((bd, "blender_"), (gd, "godot_"))):
        p = os.path.join(folder, pre + v + ".png")
        if os.path.exists(p):
            im = Image.open(p).convert("RGB"); im = im.resize((W, int(im.height * W / im.width)))
            S.paste(im.crop((0, 0, W, H)), (j * W, i * H))
        d.text((j * W + 10, i * H + 8), ("Blender  " if j == 0 else "Godot 4.7  ") + v, fill=(255, 230, 0))
S.save(out, quality=86)
print(out, S.size)
