"""Textures Godot's scene import extracts from a GLB come in Lossless (compress/mode=0); only the editor flips them to
VRAM compression, a headless --import never does (4-8x the video memory, slow loads; tests/asset_budget_test.gd
fails on them). Sets compress/mode=2 (and normal_map=1 for *_normal.*) in every texture .import under the given
folders; reimport afterwards.
    python tools/cityforge/vram_textures.py assets/cityforge/mrs [more dirs]"""
import os, re, sys

changed = 0
for root_dir in sys.argv[1:]:
    for dp, dn, fn in os.walk(root_dir):
        for f in fn:
            if not f.endswith((".png.import", ".jpg.import")): continue
            p = os.path.join(dp, f); s = open(p, encoding="utf-8").read()
            t = re.sub(r"(?m)^compress/mode=\d+", "compress/mode=2", s)
            if "_normal." in f: t = re.sub(r"(?m)^compress/normal_map=\d+", "compress/normal_map=1", t)
            if t != s:
                open(p, "w", encoding="utf-8", newline="\n").write(t); changed += 1
print("VRAM_TEXTURES %d .import files set to VRAM compression" % changed)
