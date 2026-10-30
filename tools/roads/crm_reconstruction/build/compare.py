"""Comparison images: each evidence frame's 3D viewport (top) above the reconstruction's render of the same example
(bottom), from reconstruct.py's report.
    python -I tools/roads/crm_reconstruction/build/compare.py <reconstruct out_dir>"""
import json, os, sys
from PIL import Image, ImageDraw
RECON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWPORT = (0, 60, 1525, 605)          # the video's 3D viewport in the Layout workspace (1920 x 1080 frame)
out_dir = os.path.abspath(sys.argv[1])
rep = json.load(open(os.path.join(out_dir, "reconstruction.json")))
idx = {r["id"]: r for r in json.load(open(os.path.join(RECON, "evidence", "index.json")))}
os.makedirs(os.path.join(RECON, "comparisons"), exist_ok=True)
for name, v in rep["views"].items():
    ev = idx[v["evidence"]]
    a = Image.open(os.path.join(RECON, "evidence", ev["frame_after"])).convert("RGB").crop(VIEWPORT).resize((1280, 459))
    b = Image.open(v["render"]).convert("RGB").resize((1280, 720))
    out = Image.new("RGB", (1280, 459 + 720 + 40), (0, 0, 0)); out.paste(a, (0, 20)); out.paste(b, (0, 499))
    d = ImageDraw.Draw(out)
    d.text((8, 4), "City Road Maker 2.1 tutorial %s (%s): %s" % (ev["time"], ev["id"], ev["result"][:90]), fill=(255, 255, 0))
    d.text((8, 482), "Mert Road Studio reconstruction: %s" % name, fill=(120, 255, 120))
    out.save(os.path.join(RECON, "comparisons", name + ".jpg"), quality=88)
print("COMPARE %d images -> %s" % (len(rep["views"]), os.path.join(RECON, "comparisons")))
