"""Headless test of the v3 road group: builds the library + group, one road with a lane transition, a
protected and a painted cycleway, a planting strip and ramps; checks attributes, kinds, taper widths,
ramp heights and tactile faces; renders 4 views to tmp/roads/v3/.

    blender --background --factory-startup --python tools/roads/tests/road_v3_test.py [-- --no-render]
"""
import bpy, sys, os, time, collections, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
try:
    import mrs
    t0 = time.time()
    mrs.build_all()
    print("BUILD %.0fs nodes %d" % (time.time() - t0, len(bpy.data.node_groups["MRS_Road"].nodes)))
    sc = bpy.context.scene; mrs.nodes.set_scene(sc)
    col = bpy.data.collections.new("V3_Roads"); sc.collection.children.link(col)
    mrs.samples._ground(col)
    r = mrs.roads.make_road("V3_Test", [(-80, 0, 0), (0, 0, 0), (80, 0, 0)], col, "urban", Conform=False, Embankment=False, Transition=True, Lanes_Forward_End=3, Lanes_Backward_End=2,
                            Transition_Start=50.0, Taper_Length=35.0, Bike_Right="Protected", Bike_Left="Painted", Separator="Posts", Ramp_Start=True, Ramp_End=True,
                            Trim_Start=5.0, Trim_End=5.0, Planting_Strip_Right=1.2, Median=0.0, Render_Quality="Final", Viewport_Quality="Final")
    dg = mrs.nodes.depsgraph(); me = r.evaluated_get(dg).to_mesh()
    kind = me.attributes["kind"].data; along = me.attributes["along"].data; lat = me.attributes["lat"].data
    kinds = collections.Counter(round(kind[i].value) for i in range(len(me.polygons)))
    print("KINDS", dict(kinds), "faces", len(me.polygons))
    if kinds[7] == 0: print("PROBLEM no tactile faces")
    # taper: asphalt half width right at along 10 vs 140 (2 lanes -> 3 lanes forward: RHT forward lanes are on the right)
    def half_at(a, sgn):
        vs = [lat[i].value for i in range(len(me.vertices)) if abs(along[i].value - a) < 1.0 and (lat[i].value * sgn) > 0]
        return max(abs(v) for v in vs)
    w10, w140 = half_at(10.0, 1), half_at(140.0, 1)
    print("right extent at 10 m %.2f, at 140 m %.2f" % (w10, w140))
    problems = [] if w140 > w10 + 3.0 else ["taper did not widen the carriageway"]
    # ramps: paving height near the start crossing vs mid-road
    pav_z = {}
    for p in me.polygons:
        if round(kind[p.index].value) in (6, 7):
            for v in p.vertices:
                if lat[v].value > 0: pav_z.setdefault(round(along[v].value), []).append(me.vertices[v].co.z)
    z_ramp = min(pav_z.get(2, pav_z.get(1, [0.15]))); z_mid = max(pav_z.get(70, [0.15]))
    print("paving z at the crossing %.3f, mid-road %.3f" % (z_ramp, z_mid))
    if not (z_ramp < 0.03 and z_mid > 0.14): problems.append("ramp did not lower the sidewalk")
    r.evaluated_get(dg).to_mesh_clear()
    print("ROAD_V3 checks", "OK" if not problems else "PROBLEMS: " + "; ".join(problems))
    if "--no-render" not in args:
        out = os.path.join(ROOT, "tmp", "roads", "v3")
        mrs.qa.render(os.path.join(out, "t_over.png"), (0, -70, 90), (0, 0, 0), 35, scene=sc)
        mrs.qa.render(os.path.join(out, "t_taper.png"), (30, -40, 12), (25, 0, 0), 35, scene=sc)
        mrs.qa.road_view(os.path.join(out, "t_drive.png"), r, 0.15, lateral=3.0, height=1.6, ahead=40, lens=28, scene=sc)
        mrs.qa.render(os.path.join(out, "t_ramp.png"), (-62, -22, 4), (-72, -11, 0.2), 40, scene=sc)
        mrs.qa.render(os.path.join(out, "t_cycle.png"), (20, -22, 2.0), (40, -9, 0.3), 35, scene=sc)
        print("RENDERS done %.0fs" % (time.time() - t0))
    if problems: sys.exit(1)
except Exception:
    traceback.print_exc(); print("ROAD_V3 FAILED"); sys.exit(1)
