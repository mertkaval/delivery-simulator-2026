"""Contact sheet of PNG renders (system Python with Pillow): python tools/roads/sheet.py out.png cols a.png b.png ..."""
import os, sys
from PIL import Image, ImageDraw

out, cols, paths = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
ims = [Image.open(p).convert("RGB") for p in paths]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (w * cols, h * rows), (30, 30, 30))
for i, (p, im) in enumerate(zip(paths, ims)):
    S.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    ImageDraw.Draw(S).text(((i % cols) * w + 8, (i // cols) * h + 6), os.path.splitext(os.path.basename(p))[0], fill=(255, 230, 0))
S.save(out)
print(out, S.size)
