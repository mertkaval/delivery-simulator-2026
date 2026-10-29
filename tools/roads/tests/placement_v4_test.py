"""Quick iteration on the saved v3 block: game trees + footbridge + placement v4 + route graphs.

    blender -b --factory-startup tmp/roads/v3/street_block.blend --python tools/roads/tests/placement_v4_test.py [-- --no-render]
"""
import bpy, sys, os, json, time, traceback
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "placement"); os.makedirs(OUT, exist_ok=True)
try:
    import mrs
    from mrs import footbridge as fb, game_trees as gt, placement as PL, routes, qa
    t0 = time.time()
    gt.build_game_trees(); print("trees %.1fs" % (time.time() - t0))
    for nm in ("furniture", "lighting"):
        try:
            mod = __import__("mrs." + nm, fromlist=["x"])
            fn = getattr(mod, "build_furniture", None) or getattr(mod, "build_lighting", None)
            if fn: fn(); print("built", nm)
        except Exception as e: print("optional module", nm, "unavailable:", e)
    sc = bpy.data.scenes["MRS_StreetBlock"]; mrs.nodes.set_scene(sc)
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    south = bpy.data.objects["SB_South"]
    mrs.roads.set_road(south, Sidewalk_Width_Right=4.6)
    mrs.junction.rebuild_all()
    fb.build_footbridge_group()
    obj, plan = fb.make("SB_Footbridge", bpy.data.objects["SB_AvenueW"], 100.0, col)
    print("footbridge", plan["status"], plan["messages"][:2])
    t1 = time.time()
    rep = PL.place_all(col, seed=7, style="avenue", speed_limits={"SB_AvenueW": 50, "SB_AvenueE": 50, "SB_North": 30, "SB_South": 30, "SB_SCurve": 30, "SB_TSide": 30},
                       bus_stops=[{"id": "S1", "road": "SB_South", "along": 52.0, "side": "r"}])
    print("PLACEMENT %.1fs" % (time.time() - t1), rep["counts"], rep["by_kind"])
    for k, v in sorted(rep["skip_summary"].items(), key=lambda x: -x[1])[:30]: print("   skip %-60s %d" % (k, v))
    seen = {}
    for x in rep["skipped"]:
        k = x[1]
        if seen.get(k, 0) < 3: print("   SKIP", x); seen[k] = seen.get(k, 0) + 1
    print("bus stops", rep.get("bus_stops"))
    print("regions", [(r["name"], r["count"], r["layers"]) for r in rep["regions"]])
    t2 = time.time()
    rt = routes.build(col, rep)
    print("ROUTES %.1fs" % (time.time() - t2), rt["stats"])
    for v in rt["validation"][:25]: print("   ", v)
    json.dump({"placement": {k: v for k, v in rep.items() if k != "items"}, "routes": rt}, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
    if "--no-render" not in args:
        dbg = routes.debug_object(rt, col)
        qa.render(os.path.join(OUT, "routes_overhead.png"), (45, -30, 230), (45, 0, 0), 30, scene=sc, samples=16, res=(1920, 1080))
        bpy.data.objects.remove(dbg)
        qa.render(os.path.join(OUT, "overhead.png"), (-60, -70, 75), (-40, -5, 0), 32, scene=sc, samples=24)
        qa.render(os.path.join(OUT, "busstop.png"), (14, -40, 2.2), (6.5, -52, 1.0), 35, scene=sc, samples=24)
        qa.render(os.path.join(OUT, "avenue_ped.png"), (-120, -17.0, 1.65), (-100, -16.0, 1.4), 32, scene=sc, samples=24)
        qa.render(os.path.join(OUT, "north_ped.png"), (-6.2, 30, 1.65), (-6.0, 60, 1.2), 32, scene=sc, samples=24)
    if "--save" in args: bpy.ops.wm.save_as_mainfile(filepath=args[args.index("--save") + 1], compress=True)
    print("PLACEMENT_V4 OK")
except Exception:
    traceback.print_exc(); print("PLACEMENT_V4 FAILED")
