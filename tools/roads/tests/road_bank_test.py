"""Tilted junction planes (Mert Road Studio): a junction on a slope is a plane, its roads bank at the locked ends
to the plane's cross-fall (road inputs Bank Start / Bank End), and the road edges meet the junction edges with no
step. Builds a four-way on a 10 % cross slope plus a T on a 15 % diagonal slope, evaluates the roads and the junction
meshes, and measures the height difference wherever a junction boundary vertex lies on a road end cross-section.

    blender --background --factory-startup --python tools/roads/tests/road_bank_test.py
Prints BANK_TEST OK / FAILED: every banked road end matches the plane's cross-fall within 0.004, and the largest
seam step on a tilted plane stays within 1 cm of the same junction built flat (the kerb bevel)."""
import bpy, os, sys, math
from mathutils import Vector
from mathutils.kdtree import KDTree
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
problems = []
try:
    import mrs
    from mrs import city, roads, junction, citynet
    mrs = city.ensure_base(os.path.join(ROOT, "tmp", "roads", "city", "base.blend"))
    from mrs.nodes import set_scene
    sc = bpy.context.scene; set_scene(sc)
    col = bpy.data.collections.new("BankTest"); sc.collection.children.link(col)
    preset, vals = citynet.profile("local")
    kw = {k.replace(" ", "_"): v for k, v in vals.items()}

    def plane_road(name, a, b, g, z0, at):
        pts = []
        for k in range(0, 11):
            p = Vector(a).lerp(Vector(b), k / 10.0)
            pts.append((p.x, p.y, z0 + g[0] * (p.x - at[0]) + g[1] * (p.y - at[1])))
        return roads.make_road(name, pts, col, preset, **kw)

    worst = 0.0; seams = 0; bad = []
    steps = {}
    for case, at, g, arms in (("flat", (-300.0, 0.0), (0.0, 0.0), [(-220, 0), (-380, 0), (-300, 80), (-300, -80)]),
                              ("cross", (0.0, 0.0), (0.0, 0.10), [(80, 0), (-80, 0), (0, 80), (0, -80)]),
                              ("tee", (300.0, 0.0), (0.106, 0.106), [(380, 0), (220, 0), (300, 80)])):
        worst = 0.0
        rs = []
        for i, (x, y) in enumerate(arms):
            # half the roads start at the junction, half end there (both lock / bank paths)
            a, b = ((at[0], at[1]), (x, y)) if i % 2 == 0 else ((x, y), (at[0], at[1]))
            rs.append(plane_road("BT_%s_%d" % (case, i), a, b, g, 10.0, at))
        j = junction.build_junction("BT_J_" + case, Vector((at[0], at[1], 10.0)), rs, col, plane=g, z=10.0, corner_radius=6.0, edge_depth=0.6)
        dg = bpy.context.evaluated_depsgraph_get()
        jm = j.evaluated_get(dg).to_mesh(); M = j.matrix_world
        jv = [M @ v.co for v in jm.vertices]; j.evaluated_get(dg).to_mesh_clear()
        for r in rs:
            me = r.evaluated_get(dg).to_mesh(); Mr = r.matrix_world
            al = me.attributes["along"].data; lt = me.attributes["lat"].data
            amin, amax = min(d.value for d in al), max(d.value for d in al)
            sel = [i for i in range(len(me.vertices)) if (abs(al[i].value - amin) < 0.005 or abs(al[i].value - amax) < 0.005) and abs(lt[i].value) < 10.2]
            ends = [Mr @ me.vertices[i].co for i in sel]; lats = [lt[i].value for i in sel]
            r.evaluated_get(dg).to_mesh_clear()
            # cross-fall of the road's end section (asphalt) against the plane's along the road's right vector
            near_end = [(lats[k], ends[k]) for k in range(len(ends)) if abs(lats[k]) < 5.0 and (ends[k].to_2d() - Vector(at)).length < 30.0]
            if len(near_end) >= 2:
                n_ = len(near_end); sl = sum(l for l, _ in near_end); sll = sum(l * l for l, _ in near_end); sz = sum(e.z for _, e in near_end); slz = sum(l * e.z for l, e in near_end)
                meas = (n_ * slz - sl * sz) / max(n_ * sll - sl * sl, 1e-9)
                sp_ = r.data.splines[0]; cps = sp_.bezier_points if sp_.type == "BEZIER" else sp_.points
                d_out = (Vector(cps[-1].co[:3]) - Vector(cps[0].co[:3])); d_out.z = 0.0; d_out.normalize()
                rv = Vector((d_out.y, -d_out.x, 0.0)); want = g[0] * rv.x + g[1] * rv.y
                print("BANK slope %s: measured %.4f, plane %.4f" % (r.name, meas, want))
                if abs(meas - want) > 0.004: problems.append("%s end cross-fall %.4f, plane %.4f" % (r.name, meas, want))
            kd = KDTree(len(ends))
            for i, p in enumerate(ends): kd.insert(Vector((p.x, p.y, 0.0)), i)
            kd.balance()
            plane_z = lambda q: 10.0 + g[0] * (q.x - at[0]) + g[1] * (q.y - at[1])
            for v in jv:
                if v.z < plane_z(v) - 0.05: continue                 # skirts under the surface: never seen
                co, i, d = kd.find(Vector((v.x, v.y, 0.0)))
                if d < 0.03:
                    step = abs(v.z - ends[i].z)
                    # vertices of the same seam stacked at different heights (kerb faces) pick the closest height
                    near = [ends[k] for (c2, k, d2) in kd.find_range(Vector((v.x, v.y, 0.0)), 0.03) if ends[k].z >= plane_z(ends[k]) - 0.05]
                    step = min(abs(v.z - e.z) for e in near) if near else step
                    if step > 0.02 and len(bad) < 12: bad.append((case, r.name, round(v.x, 2), round(v.y, 2), round(v.z - 10.0 - g[0] * (v.x - at[0]) - g[1] * (v.y - at[1]), 3), [round(e.z - 10.0 - g[0] * (e.x - at[0]) - g[1] * (e.y - at[1]), 3) for e in near], round(lats[i], 2)))
                    worst = max(worst, step); seams += 1
        print("BANK %s: plane %s, %d seam vertices, worst step %.4f m" % (case, g, seams, worst)); steps[case] = worst
    for b in bad: print("BANK seam", b)
    if seams < 20: problems.append("too few seam vertices compared (%d)" % seams)
    # the only step left is the kerb bevel (the junction's corner kerb has none), the same at a flat junction
    for case in ("cross", "tee"):
        if steps.get(case, 1.0) > steps.get("flat", 0.0) + 0.01: problems.append("%s: seam step %.3f m (flat junction %.3f m)" % (case, steps[case], steps["flat"]))
except Exception:
    import traceback; traceback.print_exc(); problems.append("exception")
print("BANK_TEST", "OK" if not problems else "FAILED " + "; ".join(problems))
