"""Set Godot import flags for baked kit textures: VRAM compression + mipmaps,
normal maps as RGTC normal maps. Run after build_materials.py, then reimport in Godot.

usage: python -I set_import_flags.py <textures dir>
"""
import os
import re
import sys

folder = sys.argv[1]
changed = 0
for name in sorted(os.listdir(folder)):
    if not name.endswith(".png.import"):
        continue
    path = os.path.join(folder, name)
    text = open(path, encoding="utf-8").read()
    wanted = {"compress/mode": "2", "mipmaps/generate": "true", "compress/high_quality": "true" if "_albedo" in name else "false",
              "compress/normal_map": "1" if "_normal" in name else "2"}
    for key, value in wanted.items():
        text = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", text, flags=re.M)
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    changed += 1
print("updated", changed, "import files")
