"""Godot import settings for the baked material library: VRAM-compressed with mipmaps, normal maps
flagged (Godot only flips a texture to 3D settings the first time the editor renders it; the asset
budget test wants every 3D texture compressed from the start).

    python tools/cityforge/setup_materials.py            (then: Godot --headless --path . --import)
"""
import glob, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "assets", "cityforge", "materials")
PROTO = os.path.join(HERE, "..", "..", "assets", "cityforge", "prototypes")
changed = 0
for path in glob.glob(os.path.join(LIB, "*.import")) + glob.glob(os.path.join(PROTO, "*.png.import")):
    s = open(path, encoding="utf-8").read()
    if "importer=\"texture\"" not in s: continue
    normal = "_normal." in os.path.basename(path)
    t = re.sub(r"compress/mode=\d", "compress/mode=2", s)
    t = re.sub(r"compress/normal_map=\d", "compress/normal_map=%d" % (1 if normal else 0), t)
    t = re.sub(r"mipmaps/generate=\w+", "mipmaps/generate=true", t)
    t = re.sub(r"detect_3d/compress_to=\d", "detect_3d/compress_to=0", t)
    if t != s:
        open(path, "w", encoding="utf-8").write(t)
        changed += 1
print("SETUP materials: %d import files updated" % changed)
