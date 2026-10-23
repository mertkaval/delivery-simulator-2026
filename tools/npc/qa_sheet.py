"""QA contact sheet: front / 3-4 / side / back / face of a built NPC next to its reference image.
python tools/npc/qa_sheet.py <NPC_NAME> <reference.png> [tag]"""
import sys, os
from PIL import Image
name, ref = sys.argv[1], sys.argv[2]
tag = sys.argv[3] if len(sys.argv) > 3 else "qa"
d = os.path.join("source_assets", "npc", name, "renders")
views = [Image.open(os.path.join(d, f"{name}_{tag}_{v}.png")).convert("RGB").crop((250, 190, 650, 1010)) for v in ("front", "three_quarter", "side", "back")]
face = Image.open(os.path.join(d, f"{name}_{tag}_face.png")).convert("RGB").resize((410, 410))
r = Image.open(os.path.join("reference_images", "characters", ref)).convert("RGB")
r.thumbnail((410, 820))
s = Image.new("RGB", (4 * 400 + 410, 820), (60, 60, 60))
for i, im in enumerate(views): s.paste(im, (i * 400, 0))
s.paste(r, (1600, 0)); s.paste(face, (1600, 410))
s.save(os.path.join(d, f"{name}_{tag}_sheet.png"))
print(os.path.join(d, f"{name}_{tag}_sheet.png"))
