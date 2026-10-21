"""Godot import flags for assets/landscape/*.glb: no automatic mesh LODs (the GLBs carry explicit
LOD0 / LOD1 / impostor levels) and no animation import. Run after Godot has created the .import
files once, then reimport (Godot --headless --path . --import).

usage: python -I tools/landscape_import_flags.py
"""
import os
import re

folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "landscape")
changed = 0
for name in sorted(os.listdir(folder)):
    if not name.endswith(".glb.import"):
        continue
    path = os.path.join(folder, name)
    text = open(path, encoding="utf-8").read()
    new = text
    for key, value in {"meshes/generate_lods": "false", "animation/import": "false"}.items():
        new = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", new, flags=re.M)
    if new != text:
        open(path, "w", encoding="utf-8", newline="\n").write(new)
        changed += 1
print("updated", changed, "import files")
