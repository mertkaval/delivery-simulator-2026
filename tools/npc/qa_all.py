"""Overview of built NPCs: front + three-quarter render of each next to its reference, 4 per row.
python tools/npc/qa_all.py <out.png> [id ...]"""
import sys, os
from PIL import Image, ImageDraw
ns = {}
exec(open("tools/npc/people.py", encoding="utf-8").read(), ns)
P = ns["PEOPLE"]
out = sys.argv[1]
ids = sys.argv[2:] or list(P)
tiles = []
for pid in ids:
    s = P[pid]
    d = os.path.join("source_assets", "npc", s["name"], "renders")
    f = os.path.join(d, "%s_qa_front.png" % s["name"])
    if not os.path.exists(f):
        continue
    t = Image.new("RGB", (600, 420), (50, 50, 50))
    for i, v in enumerate(("front", "three_quarter")):
        im = Image.open(os.path.join(d, "%s_qa_%s.png" % (s["name"], v))).convert("RGB").crop((250, 190, 650, 1010)).resize((200, 410))
        t.paste(im, (i * 200, 0))
    r = Image.open(os.path.join("reference_images", "characters", s["ref"])).convert("RGB")
    r.thumbnail((200, 410)); t.paste(r, (400, 0))
    ImageDraw.Draw(t).text((4, 404), pid, fill=(255, 255, 0))
    tiles.append(t)
cols = 4
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 600, rows * 420), (30, 30, 30))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 600, (i // cols) * 420))
sheet.save(out)
print(out, len(tiles))
