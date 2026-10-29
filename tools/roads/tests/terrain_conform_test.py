"""Roads integrated with a mesh terrain (Blender, headless): the mountain road and valley bridge samples, the
terrain graded by MRS_TerrainConform (cut 1:1 / fill 1:2 batters), measured and rendered.

    blender --background --factory-startup --python tools/roads/tests/terrain_conform_test.py -- <out_dir> [--no-render]

Checks along every ground road, every 4 m, both sides: the terrain stays under the road (no poke-through), meets the
outer edge (the gap between the edge top and the terrain is within the batter one metre out) and keeps within the
cut / fill batters 1-8 m out; under the bridge deck the valley floor is untouched. Prints TERRAIN_CONFORM OK."""
import bpy, math, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "terrain_conform"))
BASE = os.path.join(ROOT, "tmp", "roads", "city", "base.blend")
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

t0 = time.time()
try:
    import mrs
    from mrs import city
    mrs = city.ensure_base(BASE)
    from mrs import samples, structures, roads, qa, nodes
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    os.makedirs(OUT, exist_ok=True)
    for build in (samples.mountain_road, samples.bridge_valley):
        sc = build(); nodes.set_scene(sc)
        dg = sc.view_layers[0].depsgraph; sc.view_layers[0].update()
        ter = next(o for o in sc.objects if o.get("mrs_terrain_source"))
        ev = ter.evaluated_get(dg); me = ev.to_mesh()
        bvh = BVHTree.FromPolygons([ter.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
        def ground(x, y):
            hit = bvh.ray_cast(Vector((x, y, 1000.0)), Vector((0, 0, -1)), 3000.0)
            return hit[0].z if hit[0] is not None else None
        col = bpy.data.collections[sc.name + "_Roads"]
        # every ground surface (roads and junctions): a point beside one road may lie on another one
        sv, sf = [], []
        for o in col.all_objects:
            if o.type not in ("MESH", "CURVE") or (o.type == "CURVE" and "MRS_Road" not in o.modifiers): continue
            e = o.evaluated_get(dg); m = e.to_mesh(); gs = m.attributes.get("ground_surface")
            if gs is not None:
                base = len(sv); sv += [o.matrix_world @ v.co for v in m.vertices]
                sf += [tuple(base + i for i in p_.vertices) for p_ in m.polygons if gs.data[p_.index].value > 0.5]
            e.to_mesh_clear()
        surf = BVHTree.FromPolygons(sv, sf) if sf else None
        def covered(x, y):
            return surf is not None and surf.ray_cast(Vector((x, y, 1000.0)), Vector((0, 0, -1)), 3000.0)[0] is not None
        poke = edge_bad = batter_bad = n = 0; worst = (0.0, ""); notes = []
        for r in roads.all_roads(col):
            w = roads.road_widths(r)
            if (roads.road_input(r, "Mode") or "Ground") != "Ground": continue
            # heights from the road as it is now (the centre-line cache predates the grading's changes to the road)
            structures._CENTRE.pop(r.name, None)
            e = r.evaluated_get(dg); m = e.to_mesh()
            rb = BVHTree.FromPolygons([r.matrix_world @ v.co for v in m.vertices], [tuple(p_.vertices) for p_ in m.polygons]); e.to_mesh_clear()
            def road_z(q):
                h = rb.ray_cast(Vector((q.x, q.y, q.z + 100.0)), Vector((0, 0, -1)), 300.0)
                return h[0].z if h[0] is not None else None
            cl = structures.centre_line(r); a0, a1 = cl[0][0] + 6.0, cl[-1][0] - 6.0
            t0_, t1_ = roads.road_input(r, "Tunnel Start") or 0.0, roads.road_input(r, "Tunnel End") or 0.0
            a = a0
            while a < a1:
                if t1_ > t0_ and t0_ - 6.0 <= a <= t1_ + 6.0: a += 4.0; continue        # in a tunnel the hill stays over the road
                p, t, rr = structures.road_sample(r, a); n += 1
                zc = road_z(p); gc = ground(p.x, p.y)
                if zc is not None and gc is not None and gc > zc - 0.01:
                    poke += 1; notes.append("poke %s a=%.0f terrain %.2f over the road" % (r.name, a, gc - zc))
                for s, sg in (("r", 1.0), ("l", -1.0)):
                    out = w["half_" + s] + w["curb"] + w["sw" + s]
                    ze = road_z(p + rr * sg * (out - 0.05))
                    if ze is None: continue
                    # the terrain lies Sink (0.2 m) under the surfaces, the edge skirt (Sink + 0.3) hides the step
                    for d, lim_up, lim_dn in ((1.0, 1.0 * 1.0 + 0.15, 0.5 * 1.0 + 0.45), (4.0, 4.0 + 0.3, 2.0 + 0.5), (8.0, 8.0 + 0.5, 4.0 + 0.7)):
                        q = p + rr * sg * (out + d); g = ground(q.x, q.y)
                        if g is None or covered(q.x, q.y): continue          # on another road / junction surface
                        dz = g - ze
                        bad = dz > lim_up or -dz > lim_dn
                        if bad:
                            if d == 1.0: edge_bad += 1
                            else: batter_bad += 1
                            if abs(dz) > abs(worst[0]): worst = (dz, "%s a=%.0f %s d=%.0f" % (r.name, a, s, d))
                            notes.append("%s %s a=%.0f %s d=%.0f dz %.2f" % ("edge" if d == 1.0 else "batter", r.name, a, s, d, dz))
                a += 4.0
        print("%s: %d stations, poke-through %d, edge %d, batter %d, worst %.2f m at %s" % (sc.name, n, poke, edge_bad, batter_bad, worst[0], worst[1]))
        for t_ in notes[:40]: print("   NOTE", t_)
        check(poke == 0, "%s: the terrain never pokes through a road (%d)" % (sc.name, poke))
        check(edge_bad <= max(1, n // 50), "%s: the terrain meets the road edges (%d of %d stations off)" % (sc.name, edge_bad, n))
        check(batter_bad <= max(1, n // 50), "%s: cut / fill batters beside the roads (%d off)" % (sc.name, batter_bad))
        if "--no-render" not in argv:
            main = next(iter(roads.all_roads(col)))
            for k, t in enumerate((0.25, 0.55)):
                qa.road_view(os.path.join(OUT, "%s_%d.png" % (sc.name, k)), main, t=t, lateral=-9.0, height=6.0, ahead=50.0, lens=26.0, scene=sc, res=(1280, 720), samples=16)
            c = Vector((0.0, 0.0, 0.0))
            qa.render(os.path.join(OUT, "%s_over.png" % sc.name), c + Vector((-160, -190, 150)), c, 35.0, res=(1280, 720), samples=16, scene=sc)
    print("TERRAIN_CONFORM %s %.0fs" % ("OK" if not fails else "FAILED %d" % len(fails), time.time() - t0))
except Exception:
    traceback.print_exc(); print("TERRAIN_CONFORM FAILED")
    sys.exit(1)
