"""Footbridge solver + node group check on the saved street block (no full rebuild needed).

    blender -b --factory-startup tmp/roads/v3/street_block.blend --python tools/roads/tests/footbridge_test.py [-- --no-render] [--along 100]
"""
import bpy, sys, os, json, time, traceback, math
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "footbridge"); os.makedirs(OUT, exist_ok=True)
problems = []
def check(c, m):
    if not c: problems.append(m); print("PROBLEM", m)
try:
    import mrs
    from mrs import footbridge as fb, qa
    sc = bpy.data.scenes["MRS_StreetBlock"]; mrs.nodes.set_scene(sc)
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    t0 = time.time(); fb.build_footbridge_group(); print("GROUP %.1fs nodes %d" % (time.time() - t0, len(bpy.data.node_groups[fb.GROUP].nodes)))
    along = float(args[args.index("--along") + 1]) if "--along" in args else 100.0
    road = bpy.data.objects["SB_AvenueW"]
    obj, plan = fb.make("SB_Footbridge", road, along, col)
    for m in plan["messages"]: print("  ", m)
    print("PLAN ok=%s deck_z=%.2f rise=%.2f span=%.1f clearance=%.2f supports=%d lights=%d" % (plan["ok"], plan["deck_z"], plan["rise"], plan["span"], plan["clearance"], len(plan["supports"]), len(plan["lights"])))
    dg = mrs.nodes.depsgraph(); ev = obj.evaluated_get(dg); me = ev.to_mesh()
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    mats = sorted({obj.evaluated_get(dg).material_slots[p.material_index].material.name for p in me.polygons if p.material_index < len(ev.material_slots) and ev.material_slots[p.material_index].material})
    # walking surfaces must face up: faces using the deck material with |nz| > 0.7
    deck_i = [i for i, s in enumerate(ev.material_slots) if s.material and s.material.name in ("MRS_Paving", "MRS_FB_Deck")]
    up = down = 0
    for p in me.polygons:
        if p.material_index in deck_i and abs(p.normal.z) > 0.7:
            if p.normal.z > 0: up += 1
            else: down += 1
    zs = [v.co.z for v in me.vertices]
    print("MESH tris %d verts %d mats %s deck faces up %d down %d z %.2f..%.2f" % (tris, len(me.vertices), mats, up, down, min(zs), max(zs)))
    check(down == 0, "deck faces pointing down: %d" % down)
    ev.to_mesh_clear()
    mrs.mod_input_set(obj.modifiers[fb.MOD], "Collision Only", True); obj.update_tag(); dg = mrs.nodes.depsgraph()
    cm = obj.evaluated_get(dg).to_mesh(); ctris = sum(len(p.vertices) - 2 for p in cm.polygons); obj.evaluated_get(dg).to_mesh_clear()
    mrs.mod_input_set(obj.modifiers[fb.MOD], "Collision Only", False); obj.update_tag()
    print("COLLISION tris %d" % ctris)
    json.dump(plan, open(os.path.join(OUT, "plan.json"), "w"), indent=1)
    if "--no-render" not in args:
        p, t, r = mrs.structures.road_sample(road, along)
        def W(u, v, z): return p + t * u + r * v + Vector((0, 0, z))
        shots = [("over", W(-30, -55, 45), W(-8, 0, 2), 30), ("side", W(-45, -40, 4), W(-5, 0, 4), 35),
                 ("under", W(-14, -9, 1.6), W(0, 0, 6), 32), ("stairs", W(14, -26, 2.5), W(4, -22, 3), 40),
                 ("deck", W(0, -20, 7.8), W(0, 12, 6.8), 35), ("ramp", W(-30, -30, 3.5), W(-20, -22, 2), 38)]
        for name, eye, tgt, lens in shots:
            qa.render(os.path.join(OUT, "fb_%s.png" % name), eye, tgt, lens, scene=sc, samples=16)
    print("FOOTBRIDGE", "OK" if not problems else "PROBLEMS " + "; ".join(problems))
except Exception:
    traceback.print_exc(); print("FOOTBRIDGE FAILED")
