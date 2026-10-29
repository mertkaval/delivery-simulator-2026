"""Street generator v4 validation: build the demonstration block from a factory scene, check routes /
placement / footbridge, run the regeneration scenarios of the brief (lane count, sidewalk width, cycleway
type, junction position, tree + light spacing, footbridge anchor, placement seed), verify the inherited
roundabout / dead-end builders now form continuous networks, export the block for Godot (+ camera list),
render day / night / traversal / close-up views, save the .blend and reopen it in a second process.

    blender --background --factory-startup --python tools/roads/tests/street_block_v4_test.py [-- --no-render] [--quick]
"""
import bpy, sys, os, time, json, math, traceback, subprocess
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.environ.get("MRS_V4_OUT") or os.path.join(ROOT, "tmp", "roads", "v4"); EXP = os.path.join(OUT, "export"); REN = os.path.join(OUT, "renders")
for d in (OUT, EXP, REN): os.makedirs(d, exist_ok=True)
BLEND = os.path.join(OUT, "street_block_v4.blend")
problems = []; results = {}
def check(c, m):
    if not c: problems.append(m); print("PROBLEM", m)
    return c


def scene_census(col):
    placed = bpy.data.collections.get(col.name + "_Placed")
    objs = list(col.all_objects)
    dup = [o.name for o in objs if len(o.name) > 4 and o.name[-4] == "." and o.name[-3:].isdigit() and not o.name.startswith(("MRS_", "AU_"))]
    return {"objects": len(objs), "placed": len(placed.objects) if placed else 0, "dup_suffix": dup[:5], "n_dup": len(dup),
            "footbridges": len([o for o in objs if o.get("mrs_footbridge") and o.type == "MESH"]), "lamps": len([o for o in objs if o.get("mrs_light")])}


def overlaps(rep):
    """Pairwise physical-footprint overlaps among placed items (should be 0) + items inside walking corridors."""
    from mrs import placement as PL
    rects = []
    for it in rep_items():
        if it.get("flush") or not it.get("foot"): continue
        P = [Vector(c) for c in it["foot"]]
        c = sum(P, Vector((0, 0))) / 4
        rects.append((PL.Rect(c, P[1] - P[0], (P[1] - P[0]).length / 2 - 0.02, (P[3] - P[0]).length / 2 - 0.02), it["name"]))
    n = 0; ex = []
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if (rects[i][0].c - rects[j][0].c).length < 6.0 and rects[i][0].overlaps(rects[j][0]):
                n += 1; ex.append((rects[i][1], rects[j][1]))
    return n, ex[:4]


def rep_items():
    return json.loads(bpy.context.scene.get("mrs_placement_items", "[]")) if bpy.context.scene.get("mrs_placement_items") else json.loads(SC.get("mrs_placement_items", "[]"))


def route_ok(rt, tag):
    st = rt["stats"]
    errs = [v for v in rt["validation"] if v["level"] == "error"]
    check(st["ped_components"] == 1, "%s: pedestrian network has %d components" % (tag, st["ped_components"]))
    check(st["ped_step_free_components"] == 1, "%s: step-free network split (%d)" % (tag, st["ped_step_free_components"]))
    check(st["ped_narrow_edges"] == 0, "%s: %d sidewalk edges narrower than the walking width" % (tag, st["ped_narrow_edges"]))
    check(not errs, "%s: route errors %s" % (tag, errs[:3]))
    return st


try:
    import mrs
    from mrs import samples, placement as PL, footbridge as FB, routes as RT, lighting as LG, qa, roads as RD, junction as JN
    BASE = os.path.join(ROOT, "tmp", "roads", "v4", "base_built.blend")
    if "--base" in args and os.path.exists(BASE):
        bpy.ops.wm.open_mainfile(filepath=BASE); results["build_s"] = "cached " + BASE
    else:
        t0 = time.time(); mrs.build_all(); results["build_s"] = round(time.time() - t0, 1); print("BUILD %.0fs" % results["build_s"])
        for g_ in bpy.data.node_groups: g_.use_fake_user = True
        for m_ in bpy.data.materials: m_.use_fake_user = True
        bpy.ops.wm.save_as_mainfile(filepath=BASE, compress=True, copy=True)
    t1 = time.time()
    SC = samples.street_block("light_wear"); mrs.nodes.set_scene(SC)
    results["block_s"] = round(time.time() - t1, 1)
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    rep0 = json.loads(SC["mrs_placement_report"]); rt0 = json.loads(SC["mrs_routes"])
    c0 = scene_census(col); print("CENSUS", c0)
    check(c0["footbridges"] == 1, "footbridge missing")
    check(c0["n_dup"] == 0, "duplicate-suffixed objects after the first build: %s" % c0["dup_suffix"])
    plan = json.loads(bpy.data.objects["SB_Footbridge"]["mrs_footbridge_plan"])
    results["footbridge"] = {k: plan[k] for k in ("status", "deck_z", "rise", "span", "clearance", "width", "style")}
    results["footbridge"]["messages"] = plan["messages"]; results["footbridge"]["supports"] = len(plan["supports"])
    check(plan["status"] == "ok", "footbridge plan incomplete: %s" % plan["messages"])
    check(plan["clearance"] >= 5.3 - 1e-3, "footbridge clearance %.2f" % plan["clearance"])
    check(all(s["valid"] for s in plan["supports"]), "footbridge support in a forbidden region")
    results["placement"] = {"counts": rep0["counts"], "by_kind": rep0["by_kind"], "bus_stops": rep0.get("bus_stops"), "parks": rep0.get("parks"),
                            "regions": [(r["name"], r["count"]) for r in rep0["regions"]], "skip_summary": rep0["skip_summary"]}
    results["routes"] = rt0["stats"]; results["route_validation"] = rt0["validation"]
    route_ok(rt0, "baseline")
    bus = (rep0.get("bus_stops") or [{}])[0]
    check(len(bus.get("items", [])) >= 3, "bus stop not furnished: %s" % bus)
    nov, ex = overlaps(rep0); results["overlaps"] = nov
    check(nov == 0, "placed footprints overlap: %s" % ex)
    kinds = rep0["by_kind"]
    for k in ("tree", "light", "bench", "bin", "drain", "hydrant", "cabinet"):
        check(kinds.get(k, 0) > 0, "no %s placed" % k)

    # ------------------------------------------------------------------ regeneration scenarios
    scen = {}
    def regen(tag, rebuild_junctions=True):
        t = time.time()
        rep, rt = samples.regenerate_block(SC, col, rebuild_junctions=rebuild_junctions)
        c = scene_census(col)
        no, ex_ = overlaps(rep)
        scen[tag] = {"s": round(time.time() - t, 1), "placed": rep["counts"]["placed"], "skipped": rep["counts"]["skipped"], "objects": c["objects"],
                     "routes": rt["stats"], "overlaps": no, "dups": c["n_dup"], "by_kind": rep["by_kind"]}
        print("SCENARIO %-26s %s" % (tag, {k: v for k, v in scen[tag].items() if k != "by_kind"}))
        check(c["n_dup"] == 0, "%s: duplicated objects %s" % (tag, c["dup_suffix"]))
        check(no == 0, "%s: overlapping footprints %s" % (tag, ex_))
        route_ok(rt, tag)
        return rep, rt, c
    north = bpy.data.objects["SB_North"]; south = bpy.data.objects["SB_South"]; avE = bpy.data.objects["SB_AvenueE"]
    if "--quick" not in args:
        RD.set_road(north, Lanes_Forward=2, Lanes_Backward=2); regen("lanes north 2+2")
        RD.set_road(north, Lanes_Forward=1, Lanes_Backward=1); _, _, cb = regen("lanes north 1+1 (restored)")
        check(cb["objects"] == c0["objects"], "object count after lane round-trip %d != %d" % (cb["objects"], c0["objects"]))
        RD.set_road(south, Sidewalk_Width_Right=3.2); rep_n, _, _ = regen("south sidewalk 3.2 m")
        bs = (rep_n.get("bus_stops") or [{}])[0]
        check(not any("shelter" in n for n in bs.get("items", [])) and any(x[1] == "bus_shelter" for x in rep_n["skipped"]), "narrow sidewalk should skip the shelter with a reason")
        RD.set_road(south, Sidewalk_Width_Right=4.6); regen("south sidewalk 4.6 m (restored)")
        RD.set_road(avE, Bike_Right="Painted", Bike_Left="Buffered"); regen("avenue E cycleway painted/buffered")
        RD.set_road(avE, Bike_Right="Protected", Bike_Left="Protected"); regen("avenue E cycleway protected (restored)")
        # move the T-junction 6 m north: the ends of the three roads that meet there
        moved = []
        for rn, idx in (("SB_AvenueE", -1), ("SB_SCurve", 0), ("SB_TSide", 0)):
            bp = bpy.data.objects[rn].data.splines[0].bezier_points[idx]; bp.co.y += 4.0; bp.handle_left.y += 4.0; bp.handle_right.y += 4.0; moved.append(bp)
        regen("T-junction moved +4 m")
        for bp in moved: bp.co.y -= 4.0; bp.handle_left.y -= 4.0; bp.handle_right.y -= 4.0
        regen("T-junction restored")
        PL.RULES["tree_spacing"] = 9.0; PL.RULES["light_spacing_scale"] = 0.8; rs, _, _ = regen("tree 9 m / lights x0.8", False)
        check(rs["by_kind"].get("tree", 0) >= kinds.get("tree", 0) and rs["by_kind"].get("light", 0) >= kinds.get("light", 0), "denser spacing did not add trees / lights")
        PL.RULES["tree_spacing"] = 12.0; PL.RULES["light_spacing_scale"] = 1.0; regen("spacing restored", False)
        anchor = bpy.data.objects["MRS_FootbridgeAnchor_SB_Footbridge"]; a_loc = anchor.location.copy()
        anchor.location.x -= 22.0; rf, rtf, _ = regen("footbridge anchor -22 m", False)
        pf = json.loads(bpy.data.objects["SB_Footbridge"]["mrs_footbridge_plan"])
        check(abs(pf["along"] - (plan["along"] - 22.0)) < 1.5, "footbridge did not follow its anchor (%.1f)" % pf["along"])
        check(sum(1 for e in rtf["ped"]["edges"] if e["kind"].startswith("footbridge")) >= 4, "footbridge not in the route graph after moving")
        anchor.location = a_loc; regen("footbridge anchor restored", False)
        SC["mrs_block_seed"] = 11; r11, _, _ = regen("seed 11", False)
        SC["mrs_block_seed"] = 7; r7, _, c7 = regen("seed 7 (restored)", False)
        check(c7["objects"] == c0["objects"], "object count after all scenarios %d != %d" % (c7["objects"], c0["objects"]))
    results["scenarios"] = scen

    # ------------------------------------------------------------------ roundabout + dead end (inherited builders, now connected)
    try:
        cur = SC
        vsc = samples.roundabout_village()
        vcol = bpy.data.collections["MRS_Village_Roads"]
        RD.set_road(bpy.data.objects["VL_East"], Bike_Right="Painted", Bike_Left="Painted"); JN.rebuild_all()
        rv = RT.build(vcol, {})
        csc = samples.city_block(); ccol = bpy.data.collections["MRS_CityBlock_Roads"]
        rc = RT.build(ccol, {})
        rmeta = dict(bpy.data.objects["VL_Roundabout"]["mrs_junction"]); dmeta = dict(bpy.data.objects["CB_DeadEnd"]["mrs_junction"])
        results["roundabout"] = {"crossings": len(rmeta.get("crossings", [])), "shared_path": rmeta.get("shared_path"), "routes": rv["stats"],
                                 "errors": [v for v in rv["validation"] if v["level"] == "error"][:4]}
        results["dead_end"] = {"through_path": dmeta.get("through_path"), "routes": rc["stats"], "errors": [v for v in rc["validation"] if v["level"] == "error"][:4]}
        print("ROUNDABOUT", results["roundabout"]); print("DEAD END", results["dead_end"])
        arms_sw = sum(1 for rn in rmeta["roads"] if (RD.road_widths(bpy.data.objects[rn])["swl"] > 0 or RD.road_widths(bpy.data.objects[rn])["swr"] > 0))
        results["roundabout"]["arms_with_sidewalks"] = arms_sw
        check(len(rmeta.get("crossings", [])) == arms_sw, "roundabout crossings %d != arms with sidewalks %d" % (len(rmeta.get("crossings", [])), arms_sw))
        check(rv["stats"]["ped_components"] == 1, "village pedestrian network split: %d" % rv["stats"]["ped_components"])
        check(rc["stats"]["ped_components"] == 1, "city-block pedestrian network split: %d" % rc["stats"]["ped_components"])
        mrs.nodes.set_scene(cur)
    except Exception:
        traceback.print_exc(); problems.append("roundabout / dead-end validation crashed")
        mrs.nodes.set_scene(SC)

    # ------------------------------------------------------------------ export
    from mrs import export as ex
    t2 = time.time()
    st = ex.export_block(os.path.join(EXP, "street_block"), col.name)
    results["export"] = {k: v for k, v in st.items() if k not in ("validation",)}
    results["export_s"] = round(time.time() - t2, 1)
    model = json.load(open(os.path.join(EXP, "street_block.json"), encoding="utf-8"))
    results["json"] = {"roads": len(model["roads"]), "trees": len(model["trees"]), "plants": len(model["plants"]), "lights": len(model["lights"]),
                       "footbridges": len(model["footbridges"]), "ped_edges": len(model["routes"]["ped"]["edges"]) if model.get("routes") else 0,
                       "items": len(model["items"])}
    print("EXPORT", results["export"], results["json"])
    check(results["json"]["trees"] > 10 and results["json"]["lights"] > 10 and results["json"]["plants"] > 100, "export records incomplete %s" % results["json"])

    # ------------------------------------------------------------------ cameras (shared with Godot) + renders
    items = json.loads(SC["mrs_placement_items"]); rt = json.loads(SC["mrs_routes"])
    plan = json.loads(bpy.data.objects["SB_Footbridge"]["mrs_footbridge_plan"])
    E = {e["id"]: e for e in plan["ped_edges"]}
    def V(x): return Vector(x)
    ramp_r = next(e for e in plan["ped_edges"] if e["kind"] == "ramp" and e["end"] == "r")
    stairs_l = next(e for e in plan["ped_edges"] if e["kind"] == "stairs" and e["end"] == "l")
    hl = V(stairs_l["points"][-1]); hr = V(ramp_r["points"][-1])
    eye = Vector((0, 0, 1.65))
    rp = ramp_r["points"]; sp_ = stairs_l["points"]
    tree = next(i for i in items if i["kind"] == "tree" and i["road"] == "SB_AvenueW")
    bench = next(i for i in items if i["kind"] == "bench")
    busp = V((json.loads(SC["mrs_placement_report"]).get("bus_stops") or [{"point": [-6, -52, 0.15]}])[0]["point"])
    cyc = None
    w = RD.road_widths(avE); p, t, r = mrs.structures.road_sample(avE, 30.0); lat = (w["bike0_r"] + w["bike1_r"]) / 2
    cyc_eye = p + r * lat + Vector((0, 0, 1.5)); cyc_tgt = cyc_eye + t * 30.0 - Vector((0, 0, 0.3))
    bp_, bt_, br_ = mrs.structures.road_sample(bpy.data.objects["SB_AvenueW"], bench["along"])
    cams = [
        {"name": "overhead", "eye": [20, -125, 110], "target": [10, -15, 0], "lens": 24, "night": True},
        {"name": "aerial_bridge", "eye": [-95, -80, 45], "target": [-50, -10, 2], "lens": 32, "night": True},
        {"name": "pedestrian_avenue", "eye": list(V(ramp_r["sidewalk_point"]) + Vector((-14, 1.0, 1.65))), "target": list(V(ramp_r["sidewalk_point"]) + Vector((20, 1.5, 1.2))), "lens": 30, "night": True},
        {"name": "cyclist", "eye": list(cyc_eye), "target": list(cyc_tgt), "lens": 30, "night": False},
        {"name": "bridge_1_sidewalk", "eye": list(V(ramp_r["sidewalk_point"]) + Vector((0, 0, 1.65))), "target": list(V(ramp_r["approach_path"][0]) + Vector((0, 0, 1.4))), "lens": 30, "night": False},
        {"name": "bridge_2_ramp", "eye": list(V(rp[len(rp) // 3]) + eye), "target": list(V(rp[len(rp) // 3 + 3]) + eye), "lens": 30, "night": False},
        {"name": "bridge_3_deck", "eye": list(hr + eye + (hl - hr).normalized() * 3.0), "target": list(hl + eye), "lens": 30, "night": True},
        {"name": "bridge_4_stairs", "eye": list(V(sp_[-2]) + eye), "target": list(V(sp_[len(sp_) // 2]) + Vector((0, 0, 0.8))), "lens": 30, "night": False},
        {"name": "busstop", "eye": list(busp + Vector((11.0, 7.0, 1.7))), "target": list(busp + Vector((-2.5, 0.0, 1.0))), "lens": 32, "night": True},
        {"name": "tree_close", "eye": list(V(tree["pos"]) + Vector((5.0, -9.0, 1.7))), "target": list(V(tree["pos"]) + Vector((0, 0, 4.0))), "lens": 30, "night": False},
        {"name": "furniture_close", "eye": list(V(bench["pos"]) - br_ * 3.4 * (1 if bench["side"] == "r" else -1) * -1 + bt_ * 2.2 + Vector((0, 0, 1.5))), "target": list(V(bench["pos"]) + Vector((0, 0, 0.5))), "lens": 35, "night": False},
        {"name": "park", "eye": [-36.0, -66.0, 1.7], "target": [-55.0, -35.0, 3.5], "lens": 30, "night": False},
    ]
    json.dump(cams, open(os.path.join(EXP, "cameras.json"), "w"), indent=1)
    if "--no-render" not in args:
        tr = time.time()
        def shot(c, suffix=""):
            qa.render(os.path.join(REN, "blender_%s%s.png" % (c["name"], suffix)), Vector(c["eye"]), Vector(c["target"]), c["lens"], scene=SC, samples=24)
        for c in cams: shot(c)
        dbg = RT.debug_object(rt, col)
        qa.render(os.path.join(REN, "blender_routes.png"), (45, -42, 230), (45, 0, 0), 30, scene=SC, samples=16, res=(1920, 1080))
        bpy.data.objects.remove(dbg)
        LG.night_setup(SC)
        for c in cams:
            if c.get("night"): shot(c, "_night")
        LG.day_setup(SC)
        results["render_s"] = round(time.time() - tr, 1)
    results["census"] = scene_census(col)
    # ------------------------------------------------------------------ save + reopen
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    results["blend_mb"] = round(os.path.getsize(BLEND) / 1e6, 1)
    probe = ("import bpy,sys,json; sys.path.insert(0, r'%s'); import mrs; sc=bpy.data.scenes['MRS_StreetBlock']; mrs.nodes.set_scene(sc); "
             "col=bpy.data.collections['MRS_StreetBlock_Roads']; dg=mrs.nodes.depsgraph(); "
             "fb=bpy.data.objects['SB_Footbridge'].evaluated_get(dg).to_mesh(); road=bpy.data.objects['SB_AvenueW'].evaluated_get(dg).to_mesh(); "
             "print('REOPEN', json.dumps({'objects': len(col.all_objects), 'footbridge_tris': sum(len(p.vertices)-2 for p in fb.polygons), 'road_tris': sum(len(p.vertices)-2 for p in road.polygons), "
             "'groups': [g for g in ('MRS_Road','Road_Profile','Road_Sweep','Footbridge','Landscape_Scatter','Tree_Variants') if g in bpy.data.node_groups], 'scenes': len(bpy.data.scenes)}))") % os.path.join(ROOT, "tools", "roads").replace("\\", "/")
    out = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", BLEND, "--python-expr", probe], capture_output=True, text=True, timeout=600)
    line = next((l for l in out.stdout.splitlines() if l.startswith("REOPEN")), None)
    results["reopen"] = json.loads(line[7:]) if line else {"error": out.stdout[-800:] + out.stderr[-800:]}
    print("REOPEN", results["reopen"])
    check(line is not None and results["reopen"]["objects"] == results["census"]["objects"] and results["reopen"]["footbridge_tris"] > 1000, "reopen check failed: %s" % results["reopen"])
except Exception:
    traceback.print_exc(); problems.append("crash: " + traceback.format_exc().splitlines()[-1])
results["problems"] = problems
json.dump(results, open(os.path.join(OUT, "street_block_v4_results.json"), "w"), indent=1, default=str)
print("STREET_BLOCK_V4", "OK" if not problems else "PROBLEMS: " + " | ".join(problems))
sys.exit(1 if problems else 0)
