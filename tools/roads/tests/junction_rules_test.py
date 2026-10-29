"""Junction rules test scene (Blender, headless): the cases the city produces, built from the same road classes, then
checked by mrs.validate and rendered.

    blender --background --factory-startup --python tools/roads/tests/junction_rules_test.py -- <out_dir> [--no-render]

  J1  4-way of arterials (2 + 2 lanes, buffered cycle lanes), signals: mast arms, StraightLeft / StraightRight arrows,
      cycle bands joining opposite cycle lanes through the junction, no paint on the zebras
  J2  T of an arterial and a 2 + 2 downtown stem, signals, yellow box: stem arrows Left / Right, through legs
      StraightLeft / Straight and Straight / StraightRight; the stem's bus lanes carry BUS
  J3  skewed 4-way of local streets (one leg at 45 deg), stop control: parallel crossings, STOP in every lane
  J4  priority T: an arterial through, a local street joining it gives way (dashed line + triangles), the main
      road has no end marking
Prints JUNCTION_RULES OK when the validation finds no problem."""
import bpy, json, math, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "junction_rules"))
RENDER = "--no-render" not in argv
BASE = os.path.join(ROOT, "tmp", "roads", "city", "base.blend")
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
Z = 0.05

ROADS = [  # id, class, plan points (x, y)
    ("T_A", "arterial", [(860, 1000), (1000, 1000)]),
    ("T_B", "arterial", [(1000, 1000), (1200, 1000)]),
    ("T_C", "arterial", [(1000, 860), (1000, 1000)]),
    ("T_D", "arterial", [(1000, 1000), (1000, 1140)]),
    ("T_E", "arterial", [(1200, 1000), (1340, 1000)]),
    ("T_F", "downtown", [(1200, 1000), (1200, 1140)]),
    ("T_G", "local", [(1000, 1140), (1000, 1260)]),
    ("T_H", "local", [(1000, 1140), (1090, 1230)]),
    ("T_K", "local", [(880, 1140), (1000, 1140)]),
    ("T_P", "arterial", [(1340, 1000), (1480, 1000)]),
    ("T_Q", "local", [(1340, 1000), (1340, 870)]),
]
JUNCTIONS = [  # id, at, roads, control, crossing, main roads
    ("TJ_1", (1000, 1000), ["T_A", "T_B", "T_C", "T_D"], "signals", "zebra", None),
    ("TJ_2", (1200, 1000), ["T_B", "T_E", "T_F"], "signals", "zebra", None),
    ("TJ_3", (1000, 1140), ["T_D", "T_G", "T_H", "T_K"], "stop", "parallel", None),
    ("TJ_4", (1340, 1000), ["T_E", "T_P", "T_Q"], "priority", "parallel", ["T_E", "T_P"]),
]

t0 = time.time()
try:
    import mrs
    from mrs import city
    mrs = city.ensure_base(BASE)
    from mrs import citynet, junction, placement, validate, qa, nodes
    sc = bpy.context.scene; nodes.set_scene(sc)            # the base library's scene (its asset collections are excluded)
    col = bpy.data.collections.new("JR_Roads"); sc.collection.children.link(col)
    objs = {}
    for rid, cls, pts in ROADS:
        objs[rid] = city._road_object({"id": rid, "cls": cls, "pts": [(x, y, Z) for x, y in pts], "width": 12}, col)
    from mrs.nodes import mod_input_set
    for k in ("Bus Lane Forward", "Bus Lane Backward"): mod_input_set(objs["T_F"].modifiers["MRS_Road"], k, True)      # BUS in the stem's outer lanes
    mod_input_set(objs["T_A"].modifiers["MRS_Road"], "Centre Colour", "Yellow"); mod_input_set(objs["T_A"].modifiers["MRS_Road"], "Edge Lines", True)
    for jid, at, rs, ctrl, crossing, main in JUNCTIONS:
        junction.build_junction(jid, city.B(at[0], at[1], Z), [objs[r] for r in rs], col, crosswalks=True, stop_lines=True, corner_radius=8.0,
                                control=ctrl, crossing=crossing, snap=1.0, edge_depth=citynet.EDGE_DEPTH, z=Z, main_roads=main, box=(jid == "TJ_2"))
    # ground under everything (placement and the renders want a terrain below the sidewalks)
    me = bpy.data.meshes.new("JR_Ground"); x0, y0 = city.B(800, 800, 0)[:2]; x1, y1 = city.B(1540, 1320, 0)[:2]
    me.from_pydata([(x0, y0, -0.25), (x1, y0, -0.25), (x1, y1, -0.25), (x0, y1, -0.25)], [], [(0, 1, 2, 3)])
    from mrs.props import mat
    me.materials.append(mat("MRS_Ground", (0.16, 0.24, 0.09), 0.95)); g = bpy.data.objects.new("JR_Ground", me); sc.collection.objects.link(g)
    rep = placement.place_all(col, seed=3, style="avenue")
    placed = bpy.data.collections.get(col.name + "_Placed") or next((c for c in bpy.data.collections if c.name.startswith("MRS_Placed")), None)
    res = validate.validate(col, placed)
    os.makedirs(OUT, exist_ok=True)
    jmeta = {o.name: dict(o["mrs_junction"].to_dict() if hasattr(o["mrs_junction"], "to_dict") else o["mrs_junction"]) for o in col.all_objects if o.get("mrs_junction")}
    summary = {"validation": res, "junctions": {k: {"approaches": [{kk: a.get(kk) for kk in ("road", "end", "lanes_in", "mark_clear", "turns", "marking")} for a in v["approaches"]],
                                                   "signals": [(s["id"], s.get("kind"), s.get("lanes")) for s in v.get("signals", [])], "bike_bands": v.get("bike_bands")}
                                               for k, v in jmeta.items()},
               "speed_signs": sorted({o.get("mrs_placed") for o in bpy.data.objects if o.get("mrs_kind") == "sign_speed"})}
    with open(os.path.join(OUT, "junction_rules.json"), "w") as f: json.dump(summary, f, indent=1, default=str)
    for p in res["problems"][:60]: print("PROBLEM", p["check"], p["object"], p["message"])
    print("SUMMARY", json.dumps(summary["junctions"], default=str)[:3000])
    if RENDER:
        def W(x, y, z): return city.B(x, y, z)
        views = [("j1_top", W(1000, 1000, 70), W(1000, 1000.1, 0), 30.0), ("j2_top", W(1200, 1000, 60), W(1200, 1000.1, 0), 30.0),
                 ("j3_top", W(1010, 1150, 60), W(1010, 1150.1, 0), 30.0),
                 ("j1_west", W(955, 997.5, 3.0), W(1000, 1003, 0.5), 32.0), ("j1_bike", W(970, 1010, 6.0), W(1000, 1000, 0), 28.0),
                 ("j2_stem", W(1203, 1050, 3.0), W(1196, 1000, 0.5), 32.0), ("j2_west", W(1150, 997, 3.0), W(1200, 1004, 1.5), 32.0),
                 ("j3_skew", W(1040, 1180, 8.0), W(1000, 1140, 0), 30.0), ("j3_stop", W(1000.5, 1158, 4.0), W(999.5, 1142, 0.0), 40.0),
                 ("j4_top", W(1340, 1000, 55), W(1340, 1000.1, 0), 30.0), ("j4_minor", W(1343, 958, 3.0), W(1338, 1000, 0.5), 34.0)]
        for name, eye, tgt, lens in views:
            qa.render(os.path.join(OUT, name + ".png"), eye, tgt, lens, res=(1280, 800), samples=16, scene=sc)
            print("RENDER", name)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "junction_rules.blend"), compress=True, copy=True)
    print("JUNCTION_RULES %s %.0fs" % ("OK" if not res["problems"] else "PROBLEMS %d" % len(res["problems"]), time.time() - t0))
except Exception:
    traceback.print_exc()
    print("JUNCTION_RULES FAILED")
    sys.exit(1)
