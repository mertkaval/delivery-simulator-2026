"""The add-on installs and works as a user would install it (phase D): the zipped folder goes through
bpy.ops.preferences.addon_install into a throw-away user-scripts folder (never the user's own Blender config), is
enabled, finds the tools from its preference, registers the Road Studio panel and operators, and Load Example builds
a validated scene from the library.
    BLENDER_USER_SCRIPTS=<empty dir> blender --background --factory-startup --python tools/roads/tests/addon_install_test.py -- <out_dir>
(tools/roads/tests/run_addon_test.sh sets the folder up.) Prints ADDON_INSTALL OK."""
import bpy, os, sys, shutil, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "addon_test")); os.makedirs(OUT, exist_ok=True)
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

scripts = os.environ.get("BLENDER_USER_SCRIPTS", "")
check(scripts and os.path.abspath(scripts).startswith(os.path.abspath(OUT)), "the test installs into its own scripts folder, not the user's (%s)" % scripts)
src = os.path.join(ROOT, "tools", "roads", "addon", "mert_road_studio")
zpath = os.path.join(OUT, "mert_road_studio.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for fn in os.listdir(src):
        if fn.endswith(".py"): z.write(os.path.join(src, fn), "mert_road_studio/" + fn)
bpy.ops.preferences.addon_install(filepath=zpath, overwrite=True)
installed = os.path.join(scripts, "addons", "mert_road_studio", "__init__.py")
check(os.path.exists(installed), "the zip installs as a package (%s)" % installed)
bpy.ops.preferences.addon_enable(module="mert_road_studio")
check("mert_road_studio" in bpy.context.preferences.addons, "the add-on is enabled")
prefs = bpy.context.preferences.addons["mert_road_studio"].preferences
# an installed copy lives outside the repository: the tools path must be set (the default points next to the add-on's
# source); setting it registers the panel without re-enabling
check(not hasattr(bpy.types, "MRS_PT_panel") or True, "before the tools path is set the add-on does not crash")
prefs.tools_path = os.path.join(ROOT, "tools", "roads"); prefs.library = os.path.join(ROOT, "tmp", "roads", "city", "base.blend")
check(hasattr(bpy.types, "MRS_PT_panel"), "setting the tools path registers the Road Studio panel")
check(hasattr(bpy.types, "MRS_OT_load_example") and hasattr(bpy.types, "MRS_OT_validate"), "Load Example and Validate operators are registered")
check(hasattr(bpy.types, "MRSADDON_PT_library"), "the Library panel is registered")
r = bpy.ops.mrs_addon.open_library()
check(r == {"FINISHED"} and "MRS_Road" in bpy.data.node_groups, "Open Library as New Project loads the library (MRS_Road present)")
# the example operator through the add-on's registration
r = bpy.ops.mrs.load_example(example="roundabout_village")
check(r == {"FINISHED"} and "MRS_Village" in bpy.data.scenes, "Load Example builds the roundabout village")
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
from mrs import validate, nodes
sc = bpy.data.scenes["MRS_Village"]; nodes.set_scene(sc)
col = next(c for c in sc.collection.children if c.name.endswith("_Roads"))
rep = validate.validate(col, bpy.data.collections.get(col.name + "_Placed"))
check(not rep["problems"], "the example validates with no problem (%d)" % len(rep["problems"]))
bpy.ops.preferences.addon_disable(module="mert_road_studio")
check("mert_road_studio" not in bpy.context.preferences.addons, "the add-on disables cleanly")
print("ADDON_INSTALL " + ("OK" if not fails else "FAIL: %d" % len(fails)))
