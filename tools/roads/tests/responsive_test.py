"""Every part of a street follows a change to a road's inputs (Blender, headless, on the junction rules scene):
lanes 2 -> 3 on an arterial approach, a downtown street's speed 40 -> 20, a cycle lane removed; the auto-update
rebuilds the junctions and re-places the street assets, and mrs.validate finds nothing wrong afterwards.

    blender --background tmp/roads/junction_rules/junction_rules.blend --python tools/roads/tests/responsive_test.py -- <out_dir>
(the scene comes from tools/roads/tests/junction_rules_test.py). Prints RESPONSIVE OK."""
import bpy, json, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "responsive"))
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

try:
    import mrs
    from mrs import junction, validate, qa, nodes, roads, structures
    from mrs.nodes import mod_input_set
    sc = bpy.context.scene; nodes.set_scene(sc)
    col = bpy.data.collections["JR_Roads"]; placed = bpy.data.collections["JR_Roads_Placed"]
    def meta(n): m = bpy.data.objects[n]["mrs_junction"]; return m.to_dict() if hasattr(m, "to_dict") else dict(m)
    def heads(sig): return [c for c in bpy.data.objects[sig].children if c.get("mrs_signal_head") and dict(c["mrs_signal_head"]).get("kind") == "vehicle"]
    def arm_for(jn, road):
        m = meta(jn); ai = next(i for i, a in enumerate(m["approaches"]) if a["road"] == road)
        return next((s["id"] for s in m.get("signals", []) if s.get("approach") == ai and s.get("kind") == "mast_arm"), None)
    before = len(heads(arm_for("TJ_1", "T_A")))
    junction.enable_auto_update(True); sc["mrs_auto_place"] = True; sc["mrs_place_seed"] = 3
    # 1. T_A gets a third forward lane (it arrives at TJ_1 at its end: the forward lanes arrive)
    a = bpy.data.objects["T_A"]; mod = a.modifiers["MRS_Road"]
    mod_input_set(mod, "Lanes Forward", 3); mod_input_set(mod, "Lanes Forward End", 3)
    # 2. T_F posts 20 km/h; 3. T_E loses its cycle lanes
    mod_input_set(bpy.data.objects["T_F"].modifiers["MRS_Road"], "Speed Limit", 20)
    for k in ("Bike Left", "Bike Right"): mod_input_set(bpy.data.objects["T_E"].modifiers["MRS_Road"], k, "None")
    for o in (a, bpy.data.objects["T_F"], bpy.data.objects["T_E"]): o.update_tag()
    bpy.context.view_layer.update()
    pend = set(junction._pending["junctions"])
    check({"TJ_1", "TJ_2"} <= pend, "the edits queue their junctions for a rebuild %s" % sorted(pend))
    t = time.time(); junction._flush(); dt = time.time() - t        # (the timer runs this in a live Blender)
    print("flush %.1fs" % dt)
    bpy.context.view_layer.update()
    m1 = meta("TJ_1"); apA = next(x for x in m1["approaches"] if x["road"] == "T_A")
    check(int(round(apA["lanes_in"])) == 3, "TJ_1 sees three arriving lanes on T_A (%s)" % apA["lanes_in"])
    sig = arm_for("TJ_1", "T_A")
    check(sig is not None and len(heads(sig)) == 3, "the mast arm over T_A carries a head for every lane (%d -> %d)" % (before, len(heads(sig)) if sig else -1))
    m2 = meta("TJ_2")
    check(not any("T_E" in (b["from"][0], b["to"][0]) for b in m2.get("bike_bands", [])), "TJ_2 draws no cycle band for T_E's removed cycle lanes")
    sp = sorted({o.get("mrs_placed") for o in placed.objects if o.get("mrs_kind") == "sign_speed" and o.get("mrs_road") == "T_F"})
    check(sp == ["MRS_Sign_Speed20"], "T_F's speed signs show 20 (%s)" % sp)
    res = validate.validate(col, placed)
    for p in res["problems"][:20]: print("PROBLEM", p["check"], p["object"], p["message"])
    check(not res["problems"], "the whole scene validates after the edits (%d problems)" % len(res["problems"]))
    os.makedirs(OUT, exist_ok=True)
    W = __import__("mrs.city", fromlist=["B"]).B
    qa.render(os.path.join(OUT, "j1_three_lanes.png"), W(955, 997.5, 3.0), W(1000, 1003, 0.5), 32.0, res=(1280, 800), samples=16, scene=sc)
    qa.render(os.path.join(OUT, "j1_top.png"), W(1000, 1000, 70), W(1000, 1000.1, 0), 30.0, res=(1280, 800), samples=16, scene=sc)
    junction.enable_auto_update(False)
    print("RESPONSIVE %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
except Exception:
    traceback.print_exc(); print("RESPONSIVE FAILED")
    sys.exit(1)
