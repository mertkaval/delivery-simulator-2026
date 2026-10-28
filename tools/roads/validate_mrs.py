"""Per-scene validation pass (run by build_mrs.py): blender -b file.blend --scene NAME -P validate_mrs.py -- RENDER_DIR [--no-render]
Exports the scene's roads collection to GLB (+ collision) and renders its validation views."""
import bpy, sys, os, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:]
render_dir = args[0]; do_render = "--no-render" not in args
try:
    import mrs
    sc = bpy.context.scene; mrs.nodes.set_scene(sc)
    col = sc.name + "_Roads"
    if col in bpy.data.collections:
        st = mrs.export.export_glb(os.path.join(ROOT, "tmp", "roads", "v2", sc.name[4:].lower() + ".glb"), col)
        print("VALIDATE %s export objects %d tris %d collision_tris %s" % (sc.name, st["objects"], st["tris"], st.get("collision_tris")))
    if do_render:
        paths = [p for p in mrs.samples.render_all(render_dir) if os.path.exists(p)]
        print("VALIDATE %s renders %d" % (sc.name, len(paths)))
except Exception:
    traceback.print_exc(); print("VALIDATE %s FAILED" % bpy.context.scene.name); sys.exit(1)
