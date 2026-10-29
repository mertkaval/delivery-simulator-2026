"""Labelled contact sheets from a manifest [[image, label, flagged], ...] (written by mrs_junction_atlas.py).
    python tools/cityforge/contact_sheet.py <manifest.json> [cols rows]"""
import json, os, sys
from PIL import Image, ImageDraw

man = json.load(open(sys.argv[1])); cols = int(sys.argv[2]) if len(sys.argv) > 2 else 6; rows = int(sys.argv[3]) if len(sys.argv) > 3 else 5
out_dir = os.path.dirname(os.path.abspath(sys.argv[1])); per = cols * rows
size = Image.open(man[0][0]).size[0] if man else 384
for sh in range(0, len(man), per):
    img = Image.new("RGB", (cols * size, rows * (size + 22)), (20, 20, 20)); dr = ImageDraw.Draw(img)
    for i, (p, label, flagged) in enumerate(man[sh:sh + per]):
        x = (i % cols) * size; y = (i // cols) * (size + 22)
        img.paste(Image.open(p).convert("RGB").resize((size, size)), (x, y + 22))
        dr.text((x + 6, y + 4), label, fill=(255, 90, 80) if flagged else (200, 230, 200))
    img.save(os.path.join(out_dir, "junctions_%02d.jpg" % (sh // per)), quality=88)
print("SHEETS", (len(man) + per - 1) // per)
