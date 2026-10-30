"""Limit sweeps for terrain integration (phase B3): MRS_TerrainConform's inputs on the mountain-road sample (a winding
road on hills with cuts, fills and a tunnel).
    blender --background tmp/roads/city/base.blend --python tools/roads/limits/terrain_sweep.py -- <out_dir>
Checks (as tools/roads/tests/terrain_conform_test.py, with the batter allowances from the CURRENT slopes): along every
ground road every 4 m, both sides: the terrain never pokes through the road; it meets the road's outer edge (within
the batter 1 m out, plus Sink); the cut / fill batters hold 4 and 8 m out (cut: Cut Slope up to Deep Cut, Deep Slope
beyond; fill: Fill Slope). Pass: no poke-through, at most 1 station in 50 off at the edge or the batters (the test's
tolerance). Writes <out_dir>/terrain/<input>.json and <out_dir>/terrain_summary.json."""
import bpy, json, math, os, sys, time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "limits"))
def margin_of(v, typ):
    """The user's safety margin: 10 % of the boundary value itself (whole steps for integers, at least 1 mm)."""
    return math.floor(MARGIN * abs(v)) if typ == "int" else max(MARGIN * abs(v), 0.001)


GRID = 15; MARGIN = 0.10; REFINE = 0.01
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from mrs import samples, structures, roads, nodes
from mrs.nodes import mod_input_set, mod_input_get

sc = samples.mountain_road(); nodes.set_scene(sc)
TER = next(o for o in sc.objects if o.get("mrs_terrain_source"))
CONF = next(o for o in sc.objects if any(m.type == "NODES" and m.node_group and m.node_group.name == "MRS_TerrainConform" for m in o.modifiers))
MOD = next(m for m in CONF.modifiers if m.type == "NODES" and m.node_group and m.node_group.name == "MRS_TerrainConform")
COL = bpy.data.collections[sc.name + "_Roads"]


def measure():
    dg = sc.view_layers[0].depsgraph; sc.view_layers[0].update()
    ev = CONF.evaluated_get(dg); me = ev.to_mesh()
    bvh = BVHTree.FromPolygons([CONF.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); ev.to_mesh_clear()
    def ground(x, y):
        h = bvh.ray_cast(Vector((x, y, 1000.0)), Vector((0, 0, -1)), 3000.0); return h[0].z if h[0] is not None else None
    sv, sf = [], []
    for o in COL.all_objects:
        if o.type not in ("MESH", "CURVE") or (o.type == "CURVE" and "MRS_Road" not in o.modifiers): continue
        e = o.evaluated_get(dg); m = e.to_mesh(); gs = m.attributes.get("ground_surface")
        if gs is not None:
            base = len(sv); sv += [o.matrix_world @ v.co for v in m.vertices]
            sf += [tuple(base + i for i in p_.vertices) for p_ in m.polygons if gs.data[p_.index].value > 0.5]
        e.to_mesh_clear()
    surf = BVHTree.FromPolygons(sv, sf) if sf else None
    covered = lambda x, y: surf is not None and surf.ray_cast(Vector((x, y, 1000.0)), Vector((0, 0, -1)), 3000.0)[0] is not None
    cut, fill = mod_input_get(MOD, "Cut Slope"), mod_input_get(MOD, "Fill Slope")
    deep, deep_s = mod_input_get(MOD, "Deep Cut"), mod_input_get(MOD, "Deep Slope")
    sink = mod_input_get(MOD, "Sink"); band = mod_input_get(MOD, "Edge Band")
    def cut_allow(run):
        r0 = deep / max(cut, 1e-6)
        return cut * min(run, r0) + deep_s * max(run - r0, 0.0)
    poke = edge_bad = batter_bad = n = 0
    for r in roads.all_roads(COL):
        if (roads.road_input(r, "Mode") or "Ground") != "Ground": continue
        w = roads.road_widths(r); structures._CENTRE.pop(r.name, None)
        e = r.evaluated_get(dg); m = e.to_mesh()
        rb = BVHTree.FromPolygons([r.matrix_world @ v.co for v in m.vertices], [tuple(p_.vertices) for p_ in m.polygons]); e.to_mesh_clear()
        def road_z(q):
            h = rb.ray_cast(Vector((q.x, q.y, q.z + 100.0)), Vector((0, 0, -1)), 300.0); return h[0].z if h[0] is not None else None
        cl = structures.centre_line(r); a, a1 = cl[0][0] + 6.0, cl[-1][0] - 6.0
        t0_, t1_ = roads.road_input(r, "Tunnel Start") or 0.0, roads.road_input(r, "Tunnel End") or 0.0
        while a < a1:
            if t1_ > t0_ and t0_ - 6.0 <= a <= t1_ + 6.0: a += 4.0; continue
            p, t, rr = structures.road_sample(r, a); n += 1
            zc = road_z(p); gc = ground(p.x, p.y)
            if zc is not None and gc is not None and gc > zc - 0.01: poke += 1
            for s, sg in (("r", 1.0), ("l", -1.0)):
                out = w["half_" + s] + w["curb"] + w["sw" + s]
                ze = road_z(p + rr * sg * (out - 0.05))
                if ze is None: continue
                # the terrain test's allowances (terrain_conform_test.py: the batter from the edge, with its slack for the
                # terrain mesh between vertices), the slopes taken from the CURRENT inputs instead of the defaults
                for d, slack_up, slack_dn in ((1.0, 0.15, 0.45), (4.0, 0.3, 0.5), (8.0, 0.5, 0.7)):
                    q = p + rr * sg * (out + d); g = ground(q.x, q.y)
                    if g is None or covered(q.x, q.y): continue
                    lim_up = cut_allow(d) + slack_up + max(sink - 0.2, 0.0); lim_dn = fill * d + slack_dn + max(sink - 0.2, 0.0)
                    dz = g - ze
                    if dz > lim_up or -dz > lim_dn:
                        if d == 1.0: edge_bad += 1
                        else: batter_bad += 1
            a += 4.0
    probs = []
    if poke: probs.append("terrain pokes through the road at %d stations" % poke)
    if edge_bad > max(1, n // 50): probs.append("edge off at %d of %d stations" % (edge_bad, n))
    if batter_bad > max(1, n // 50): probs.append("batters off at %d of %d stations" % (batter_bad, n))
    return probs


def sweep(name, typ, default, lo, hi):
    evals = []; t0 = time.time()
    def run(v):
        v = int(round(v)) if typ == "int" else float(v)
        mod_input_set(MOD, name, v); CONF.update_tag()
        probs = measure(); evals.append({"value": v, "pass": not probs, "problems": probs}); return not probs
    grid = sorted({int(round(lo + (hi - lo) * k / (GRID - 1))) for k in range(GRID)}) if typ == "int" else sorted({lo + (hi - lo) * k / (GRID - 1) for k in range(GRID)})
    ok = {v: run(v) for v in grid}; ok[default] = run(default)
    # a boundary is found to within REFINE of its own value (at least 1 mm; integers to adjacent values)
    tol = lambda g, b: 1.0 if typ == "int" else max(REFINE * max(abs(g), abs(b)), 0.001)
    def bisect(good, bad):
        while abs(bad - good) > tol(good, bad):
            m_ = (good + bad) * 0.5
            if typ == "int":
                m_ = int(round(m_))
                if m_ in (good, bad): break
            if run(m_): good = m_
            else: bad = m_
        return good, bad
    vs = sorted(ok); regions = []; cur = None
    for k, v in enumerate(vs):
        if ok[v]:
            if cur is None: cur = [v, v, vs[k - 1] if k > 0 else None, None]
            cur[1] = v
        elif cur is not None: cur[3] = v; regions.append(cur); cur = None
    if cur is not None: regions.append(cur)
    refined = []
    for a, b, fa, fb in regions:
        if fa is not None: a, fa = bisect(a, fa)
        if fb is not None: b, fb = bisect(b, fb)
        refined.append([a, b, fa, fb])
    allowed = []
    for a, b, fa, fb in refined:
        la = a if fa is None else a + margin_of(a, typ); lb = b if fb is None else b - margin_of(b, typ)
        allowed.append([la, lb] if la <= lb else [(a + b) * 0.5, (a + b) * 0.5])
    mod_input_set(MOD, name, default); CONF.update_tag()
    rec = {"group": "MRS_TerrainConform", "param": name, "type": typ, "default": default, "declared": [lo, hi], "regions": refined, "allowed": allowed,
           "gaps": [[allowed[k][1], allowed[k + 1][0]] for k in range(len(allowed) - 1)], "limit": [min(x[0] for x in allowed), max(x[1] for x in allowed)] if allowed else None,
           "default_passes": ok[default], "n_evals": len(evals), "seconds": round(time.time() - t0, 1), "evals": evals}
    print("%-18s %-5s declared [%g, %g] regions %s -> allowed %s (%d evals, %.0fs)%s" % (name, typ, lo, hi, [[round(r[0], 3), round(r[1], 3)] for r in refined],
          [[round(x, 3) for x in r] for r in allowed], len(evals), time.time() - t0, "" if ok[default] else "  DEFAULT FAILS: %s" % evals[-1]["problems"]))
    return rec


os.makedirs(os.path.join(OUT, "terrain"), exist_ok=True)
p0 = measure(); print("SELFTEST terrain defaults: %s" % ("OK" if not p0 else p0))
summary = {}
for it in (MOD.node_group.interface.items_tree if not p0 else ()):         # no sweep on a failing self-test
    if "--selftest" in argv: break
    if it.item_type != "SOCKET" or it.in_out != "INPUT" or it.socket_type not in ("NodeSocketFloat", "NodeSocketInt"): continue
    rec = sweep(it.name, "int" if it.socket_type == "NodeSocketInt" else "float", mod_input_get(MOD, it.name), it.min_value, it.max_value)
    with open(os.path.join(OUT, "terrain", it.name.replace(" ", "_") + ".json"), "w") as f: json.dump(rec, f, indent=1, default=str)
    summary["MRS_TerrainConform/" + it.name] = {k: rec[k] for k in ("type", "default", "declared", "regions", "allowed", "gaps", "limit", "default_passes", "n_evals")}
    with open(os.path.join(OUT, "terrain_summary.json"), "w") as f: json.dump(summary, f, indent=1, default=str)
print("TERRAIN_SWEEP done %d inputs" % len(summary))
