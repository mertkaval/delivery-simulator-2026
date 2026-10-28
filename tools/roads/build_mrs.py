"""Headless build of the Mert Road Studio v2 deliverable .blend + smoke test + validation renders.

    blender --background --factory-startup --python tools/roads/build_mrs.py -- [out.blend] [--renders DIR] [--no-render]

Builds the node groups, materials and prop collections, the five sample scenes, marks the reusable
node groups and materials as assets, saves the file and prints a summary. Exit code 1 on failure.
"""
import bpy, sys, os, time, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = next((a for a in args if a.endswith(".blend")), os.path.join(ROOT, "tools", "roads", "mert_road_studio_v2.blend"))
render_dir = args[args.index("--renders") + 1] if "--renders" in args else None
do_render = "--no-render" not in args

t0 = time.time()
try:
    import mrs
    mrs.build_all()
    mrs.register()
    scenes = mrs.samples.build_all()
    # assets library inside the file (if the generated library module is present)
    if getattr(mrs, "assets", None) and hasattr(mrs.assets, "build_assets"):
        mrs.assets.build_assets()
    # mark the reusable datablocks as assets for the Asset Browser
    for ng in bpy.data.node_groups:
        if ng.name in ("MRS_Road", "MRS_TerrainConform"): ng.asset_mark(); ng.asset_data.tags.new("road studio")
    for m in bpy.data.materials:
        if m.name.startswith("MRS_") and not m.name.startswith("MRS_Prop"): m.asset_mark()
    # checks
    roads = mrs.roads.all_roads(); junctions = mrs.junction.all_junctions()
    assert len(roads) >= 25, "roads: %d" % len(roads)
    assert len(junctions) >= 12, "junctions: %d" % len(junctions)
    for r in roads:
        sc = next(s for s in bpy.data.scenes if r.name in s.objects)
        mrs.nodes.set_scene(sc); dg = mrs.nodes.depsgraph()
        me = r.evaluated_get(dg).to_mesh()
        assert len(me.polygons) > 50, "%s has %d faces" % (r.name, len(me.polygons))
        assert "UVMap" in me.attributes or me.uv_layers, "%s has no UVMap" % r.name
        r.evaluated_get(dg).to_mesh_clear()
    mrs.nodes.set_scene(bpy.data.scenes["MRS_CityBlock"])
    # the default scene the file opens on
    mrs.nodes.set_scene(bpy.data.scenes["MRS_CityBlock"])
    for sc in list(bpy.data.scenes):
        if sc.name == "Scene": bpy.data.scenes.remove(sc)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("MRS BUILD OK %s (%.1f MB) roads %d junctions %d in %.0fs" % (out, os.path.getsize(out) / 1e6, len(roads), len(junctions), time.time() - t0))
    # second pass per scene: the glTF exporter and the renderer want the active scene, which background
    # Blender can only set from the command line (--scene)
    import subprocess
    rd = render_dir or os.path.join(ROOT, "tmp", "roads", "v2", "samples")
    for sc in bpy.data.scenes:
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", out, "--scene", sc.name, "--python", os.path.join(ROOT, "tools", "roads", "validate_mrs.py"), "--", rd]
        if not do_render: cmd.append("--no-render")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        lines = [l for l in res.stdout.splitlines() if l.startswith("VALIDATE")]
        print("\n".join(lines) if lines else "VALIDATE %s FAILED rc=%d\n%s" % (sc.name, res.returncode, res.stdout[-1500:] + res.stderr[-500:]))
except Exception:
    traceback.print_exc(); print("MRS BUILD FAILED"); sys.exit(1)
