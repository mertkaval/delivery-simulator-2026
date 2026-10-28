"""Headless junction v3 test: a 4-way (urban avenue with median + cycleways x residential) with signals,
a T-junction (priority) and a 2-way bend; checks trims, ramps, crossings metadata, signal IDs / phases;
renders overhead, driver, cyclist and pedestrian views + crossing / curb close-ups to tmp/roads/v3/j_*.png.

    blender --background --factory-startup --python tools/roads/tests/junction_v3_test.py [-- --no-render]
"""
import bpy, sys, os, time, collections, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
try:
    import mrs
    t0 = time.time(); mrs.build_all(); print("BUILD %.0fs" % (time.time() - t0))
    sc = bpy.context.scene; mrs.nodes.set_scene(sc)
    col = bpy.data.collections.new("J3_Roads"); sc.collection.children.link(col)
    mrs.samples._ground(col)
    R = lambda n, pts, preset, **kw: mrs.roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)
    avW = R("J3_AvW", [(-90, 0, 0), (-45, 0, 0), (0, 0, 0)], "urban", Median=1.8, Bike_Left="Protected", Bike_Right="Protected", Planting_Strip_Left=1.0, Planting_Strip_Right=1.0)
    avE = R("J3_AvE", [(0, 0, 0), (45, 0, 0), (90, 0, 0)], "urban", Median=1.8, Bike_Left="Protected", Bike_Right="Protected", Planting_Strip_Left=1.0, Planting_Strip_Right=1.0)
    stN = R("J3_StN", [(0, 0, 0), (0, 40, 0), (0, 80, 0)], "residential", Bike_Right="Painted")
    stS = R("J3_StS", [(0, 0, 0), (0, -40, 0), (0, -80, 0)], "residential", Bike_Left="Painted")
    avE2 = R("J3_AvE2", [(90, 0, 0), (130, 0, 0), (170, 0, 0)], "urban", Median=1.8, Bike_Left="Protected", Bike_Right="Protected", Planting_Strip_Left=1.0, Planting_Strip_Right=1.0)
    svc = R("J3_Svc", [(90, 0, 0), (90, 35, 0), (90, 70, 0)], "service")
    j4 = mrs.junction.build_junction("J3_4way", (0, 0, 0), [avW, avE, stN, stS], col, control="signals", corner_radius=5.0, main_roads=["J3_AvW", "J3_AvE"])
    jt = mrs.junction.build_junction("J3_T", (90, 0, 0), [avE, avE2, svc], col, control="priority", corner_radius=5.0, main_roads=["J3_AvE", "J3_AvE2"], crossing="parallel")
    meta = dict(j4["mrs_junction"])
    print("4WAY approaches", [(a["road"], round(a["trim"], 1), a["lanes_in"], a["lanes_out"]) for a in meta["approaches"]])
    print("4WAY crossings", [(c["id"], c["style"], c["refuge"]) for c in meta["crossings"]])
    print("4WAY signals", [(s["id"], s["controls_road"], s["phase"]) for s in meta.get("signals", [])], "phases", meta.get("signal_phases"))
    problems = []
    if len(meta["crossings"]) != 4: problems.append("expected 4 crossings, got %d" % len(meta["crossings"]))
    if len(meta.get("signals", [])) != 4: problems.append("expected 4 signals, got %d" % len(meta.get("signals", [])))
    ph = meta.get("signal_phases", [])
    if not (len(ph) == 2 and all(len(p) == 2 for p in ph)): problems.append("phases should pair opposite approaches: %s" % ph)
    if not any(c["refuge"] for c in meta["crossings"]): problems.append("avenue crossings should have a refuge island (median 1.8)")
    for r in (avW, stN):
        mod = r.modifiers["MRS_Road"]
        if not (mrs.mod_input_get(mod, "Ramp End") if r is avW else mrs.mod_input_get(mod, "Ramp Start")): problems.append("ramp flag not set on " + r.name)
    dg = mrs.nodes.depsgraph(); me = j4.evaluated_get(dg).to_mesh()
    kinds = collections.Counter(round(me.attributes["kind"].data[i].value) for i in range(len(me.polygons)))
    print("4WAY kinds", dict(kinds), "signal children", [c.name for c in j4.children])
    if kinds.get(8, 0) == 0: problems.append("no bicycle crossing faces")
    if kinds.get(1, 0) < 20: problems.append("too few paint faces")
    j4.evaluated_get(dg).to_mesh_clear()
    print("JUNCTION_V3 checks", "OK" if not problems else "PROBLEMS: " + "; ".join(problems))
    if "--no-render" not in args:
        out = os.path.join(ROOT, "tmp", "roads", "v3")
        mrs.qa.render(os.path.join(out, "j_over.png"), (45, -60, 140), (45, 0, 0), 32, scene=sc)
        mrs.qa.render(os.path.join(out, "j_4way.png"), (-28, -36, 16), (3, 3, 0), 35, scene=sc)
        mrs.qa.road_view(os.path.join(out, "j_driver.png"), stS, 0.7, lateral=1.6, height=1.3, ahead=40, lens=30, scene=sc)
        mrs.qa.road_view(os.path.join(out, "j_cyclist.png"), avW, 0.8, lateral=12.0, height=1.5, ahead=35, lens=30, scene=sc)
        mrs.qa.render(os.path.join(out, "j_pedestrian.png"), (-12, -14.5, 1.65), (0, -10, 1.0), 32, scene=sc)
        mrs.qa.render(os.path.join(out, "j_crossing.png"), (9, -14, 3.5), (3, -9, 0.1), 40, scene=sc)
        mrs.qa.render(os.path.join(out, "j_curb.png"), (-8.5, -12.0, 1.4), (-6.0, -9.5, 0.1), 45, scene=sc)
        mrs.qa.render(os.path.join(out, "j_T.png"), (70, -35, 18), (92, 2, 0), 35, scene=sc)
        print("RENDERS done %.0fs" % (time.time() - t0))
    if problems: sys.exit(1)
except Exception:
    traceback.print_exc(); print("JUNCTION_V3 FAILED"); sys.exit(1)
