"""Place our square sphere render into a video frame's geometry (render width W px centred at (cx, cy) in frame
pixels) and write video crop | our crop side by side.  python -I place_compare.py FRAME OURS W CX CY CROP OUT"""
import sys
from PIL import Image
frame, ours, W, cx, cy, crop, out = sys.argv[1:8]
W, cx, cy = int(W), int(cx), int(cy); box = tuple(int(x) for x in crop.split(","))
v = Image.open(frame).convert("RGB")
o = Image.open(ours).convert("RGBA").resize((W, W), Image.LANCZOS)
canvas = Image.new("RGBA", v.size, (40, 40, 40, 255)); canvas.alpha_composite(o, (cx - W // 2, cy - W // 2))
a = v.crop(box); c = canvas.convert("RGB").crop(box)
res = Image.new("RGB", (a.width * 2 + 10, a.height), (0, 0, 0)); res.paste(a, (0, 0)); res.paste(c, (a.width + 10, 0))
res.save(out); print("wrote", out)
