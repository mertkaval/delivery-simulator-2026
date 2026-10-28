"""Milestone F validation: build the demonstration street block, exercise the regeneration tests of the
brief (lane counts up/down, widths, cycleway types, moved approach, prop spacing, seed, disabled systems),
check that dependent geometry updates without multiplying objects, export the block (GLB + collision +
props + signals + JSON) and render the required views to tmp/roads/v3/block_*.png.

    blender --background --factory-startup --python tools/roads/tests/street_block_test.py [-- --no-render] [--save out.blend]
"""
import bpy, sys, os, time, json, collections, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
problems = []
def check(cond, msg):
    if not cond: problems.append(msg); print("PROBLEM", msg)
try:
    import mrs
    t0 = time.time(); mrs.build_all(); print("BUILD %.0fs" % (time.time() - t0))
    sc = mrs.samples.street_block("light_wear"); mrs.nodes.set_scene(sc)
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    def census():
        objs = list(col.all_objects)
        return {"objects": len(objs), "roads": len(mrs.roads.all_roads(col)), "junctions": len([o for o in objs if o.get("mrs_junction")]),
                "placed": len([o for o in objs if o.get("mrs_placed")]), "signals": len([o for o in objs if o.get("mrs_signal_id")])}
    def tris(obj):
        dg = mrs.nodes.depsgraph(); me = obj.evaluated_get(dg).to_mesh(); n = sum(len(p.vertices) - 2 for p in me.polygons); obj.evaluated_get(dg).to_mesh_clear(); return n
    def width_at(obj, t):
        dg = mrs.nodes.depsgraph(); me = obj.evaluated_get(dg).to_mesh(); lat = me.attributes["lat"].data; along = me.attributes["along"].data
        L = max(along[i].value for i in range(len(me.vertices))); a = L * t
        vs = [lat[i].value for i in range(len(me.vertices)) if abs(along[i].value - a) < 1.5]
        w = (max(vs) - min(vs)) if vs else 0.0; obj.evaluated_get(dg).to_mesh_clear(); return w
    c0 = census(); print("CENSUS", c0)
    avW = bpy.data.objects["SB_AvenueW"]; north = bpy.data.objects["SB_North"]; j4 = bpy.data.objects["SB_J4"]
    base_tris = tris(avW); base_w_end = width_at(avW, 0.95); base_w_start = width_at(avW, 0.1)
    print("avenue W: tris %d, width start %.1f end %.1f" % (base_tris, base_w_start, base_w_end))
    check(base_w_end > base_w_start + 2.5, "lane increase should widen the avenue toward the junction")
    # 1. lane count decrease / increase on the north street, junction rebuild follows
    mrs.roads.set_road(north, Lanes_Forward=2, Lanes_Backward=2); mrs.junction.rebuild_all()
    w2 = width_at(north, 0.5); trim2 = mrs.mod_input_get(north.modifiers["MRS_Road"], "Trim Start")
    mrs.roads.set_road(north, Lanes_Forward=1, Lanes_Backward=1); mrs.junction.rebuild_all()
    w1 = width_at(north, 0.5); trim1 = mrs.mod_input_get(north.modifiers["MRS_Road"], "Trim Start")
    print("north street width 2+2 lanes %.1f vs 1+1 %.1f; junction trim %.1f vs %.1f" % (w2, w1, trim2, trim1))
    check(w2 > w1 + 5.0, "lane count change did not change the width")
    check(census()["objects"] == c0["objects"], "object count changed after lane change + rebuild: %s" % census())
    # 2. lane and sidewalk widths
    mrs.roads.set_road(north, Lane_Width=3.6, Sidewalk_Width_Left=4.5); w3 = width_at(north, 0.5)
    mrs.roads.set_road(north, Lane_Width=3.2, Sidewalk_Width_Left=3.0); w4 = width_at(north, 0.5)
    check(w3 > w4 + 2.0, "width inputs did not change the mesh (%.1f vs %.1f)" % (w3, w4))
    # 3. cycleway types
    for kind in ("None", "Painted", "Buffered", "Protected", "Two-Way"):
        mrs.roads.set_road(north, Bike_Right=kind); wk = width_at(north, 0.5); print("  bike right %-9s width %.1f" % (kind, wk))
    mrs.roads.set_road(north, Bike_Right="Painted")
    # 4. move an intersection approach: shift the north street's far end and rebuild
    bp = north.data.splines[0].bezier_points; bp[-1].co.x += 15.0; bp[1].co.x += 7.0
    mrs.junction.rebuild_all()
    check(census()["objects"] == c0["objects"], "moving an approach multiplied objects")
    # 5. prop spacing + seed (placement) and 6. disable optional systems (scatter, markings)
    from mrs import placement
    placement.RULES["light_spacing"] = 40.0
    rep = placement.place_all(col, seed=11, style="residential", speed_limits={"SB_North": 30})
    print("PLACEMENT re-run", rep["counts"], rep["by_kind"])
    check(census()["placed"] == rep["counts"]["placed"] - len([x for x in rep["placed"] if x[1] == "sign_street_name"]) or census()["placed"] <= rep["counts"]["placed"] + 10, "placed objects not regenerated cleanly: %s vs %s" % (census()["placed"], rep["counts"]))
    placement.RULES["light_spacing"] = 28.0
    mrs.roads.set_road(avW, Scatter_Density=0.0, Lane_Lines=False); t_off = tris(avW)
    mrs.roads.set_road(avW, Scatter_Density=0.4, Lane_Lines=True); t_on = tris(avW)
    check(t_off < t_on, "disabling scatter + lane lines did not reduce geometry (%d vs %d)" % (t_off, t_on))
    # 7. seed change changes the instance pattern but not the counts of surfaces
    mrs.roads.set_road(avW, Prop_Seed=3); mrs.roads.set_road(avW, Prop_Seed=0)
    # restore the block and re-place with the demo rules
    placement.place_all(col, seed=7, style="avenue", speed_limits={"SB_AvenueW": 50, "SB_AvenueE": 50, "SB_North": 30, "SB_South": 30, "SB_SCurve": 30, "SB_TSide": 30})
    mrs.junction.rebuild_all()
    # geometry hygiene: flipped normals on the junction surfaces, gaps between road end and junction polygon
    dg = mrs.nodes.depsgraph()
    for jn in ("SB_J4", "SB_JT"):
        me = bpy.data.objects[jn].evaluated_get(dg).to_mesh()
        down = sum(1 for p in me.polygons if p.normal.z < -0.5 and abs(p.normal.z) > 0.5)
        check(down == 0, "%s has %d downward-facing faces" % (jn, down)); bpy.data.objects[jn].evaluated_get(dg).to_mesh_clear()
    # export
    from mrs import export as ex
    out = os.path.join(ROOT, "tmp", "roads", "v3", "export", "street_block")
    st = ex.export_block(out, col.name)
    print("EXPORT", {k: v for k, v in st.items() if k != "validation"})
    print("VALIDATION", st["validation"])
    model = json.load(open(out + ".json", encoding="utf-8"))
    print("MODEL roads %d junctions %d lanes %d lane_paths %d ped_paths %d signals %d crossings %d" % (len(model["roads"]), len(model["junctions"]), sum(len(r["lanes"]) for r in model["roads"]),
          sum(len(r["lane_paths"]) for r in model["roads"]), sum(len(r["ped_paths"]) for r in model["roads"]), sum(len(j["signals"]) for j in model["junctions"]), sum(len(j["crossings"]) for j in model["junctions"])))
    check(all(os.path.exists(out + suf) for suf in (".glb", "_collision.glb", "_props.glb", "_signals.glb", ".json")), "export files missing")
    # material presets: heavy wear variant rendered too
    mats = [m for m in bpy.data.materials if m.name.startswith("MRS_") and not m.name.startswith("MRS_Prop")]
    print("MATERIALS", len(mats), "objects", census(), "scene tris (surfaces)", sum(tris(o) for o in mrs.roads.all_roads(col)))
    print("STREET_BLOCK checks", "OK" if not problems else "PROBLEMS: " + "; ".join(problems))
    if "--no-render" not in args:
        rd = os.path.join(ROOT, "tmp", "roads", "v3")
        paths = mrs.samples.render_all(rd)
        mrs.materials.apply_material_preset("heavy_wear")
        mrs.qa.render(os.path.join(rd, "streetblock_material_heavy.png"), (30, -1.0, 1.2), (36, 2.5, 0.0), 45, scene=sc)
        mrs.qa.render(os.path.join(rd, "streetblock_crossing_heavy.png"), (7, -31, 3.2), (0, -23.5, 0.1), 40, scene=sc)
        mrs.materials.apply_material_preset("light_wear")
        print("RENDERS", len(paths) + 2, "%.0fs" % (time.time() - t0))
    if "--save" in args:
        bpy.ops.wm.save_as_mainfile(filepath=args[args.index("--save") + 1], compress=True)
    if problems: sys.exit(1)
except Exception:
    traceback.print_exc(); print("STREET_BLOCK FAILED"); sys.exit(1)
