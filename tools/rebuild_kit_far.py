"""Re-export only the far LODs (<name>_far.glb) of the city kit modules from build_kit.py, leaving
the hand-checked near GLBs untouched (no AO bake: far modules have none).

blender --background --factory-startup --python tools/rebuild_kit_far.py -- [name ...]
Default names: every facade module whose far LOD carries window / door quads.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "world", "citykit", "build_kit.py")
KIT = {"__name__": "kit_far", "__file__": SRC, "BUILD": False}
exec(compile(open(SRC).read(), SRC, "exec"), KIT)

import bpy  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = args or [f"{k}_{s}" for k in ("bay_apartment", "bay_office", "ground_residential", "entrance_residential", "th_ground", "th_upper") for s in range(3)]
col = bpy.data.collections.get("CityKitFar") or bpy.data.collections.new("CityKitFar")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
for name in names:
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    m = KIT["Mesh"]()
    KIT["MODULES"][name](m, "far")
    obj = m.emit(name, col)
    parts = KIT["split_by_material"](obj)
    path = os.path.join(KIT["OUT"], name + "_far.glb")
    KIT["export"](parts, path)
    print("KIT FAR", name, "->", path)
for o in list(col.objects):
    bpy.data.objects.remove(o, do_unlink=True)
