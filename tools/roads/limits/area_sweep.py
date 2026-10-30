"""Limit sweeps for the area-junction workflow (phase B4): MRS_AreaJunction, MRS_ExtensionMesh / Curve, MRS_CustomSign,
MRS_MarkingLines. No MRS library needed.
    blender --background --factory-startup --python tools/roads/limits/area_sweep.py -- <out_dir>
Every numeric input of each group is swept over its declared range (21 values + bisection of each pass / fail
boundary to 1 % + five confirmations), all other inputs at their defaults. Checks:
  junction  evaluates with faces, finite; road asphalt over every red footprint cell (0.5 m raster, away from the
            fillets); no cell with both road and roadside; faces up; no loose edges
  extension the junction over a mesh / curve extension: as above, its own footprint is road
  sign      finite; panel = Scale X x Scale Y; every text / line / image face inside the panel; the post reaches the
            ground
  lines     finite; every painted face within Road Size / 2 + 1 m of the curve; patterns never wider than the line
Writes <out_dir>/area/<group>_<input>.json and <out_dir>/area_summary.json."""
import bpy, bmesh, json, math, os, sys, time, traceback
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "limits"))
def margin_of(v, typ):
    """The user's safety margin: 10 % of the boundary value itself (whole steps for integers, at least 1 mm)."""
    return math.floor(MARGIN * abs(v)) if typ == "int" else max(MARGIN * abs(v), 0.001)


GRID = 21; MARGIN = 0.10; REFINE = 0.01
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from mrs import areajunction as AJ, customsign as CS, markinglines as ML
from mrs.nodes import mod_input_set, mod_input_get

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
AJ.build_all(); CS.build_custom_sign(); ML.build_marking_lines()
sc = bpy.context.scene
roads = bpy.data.collections.new("Roads"); sc.collection.children.link(roads)
juncs = bpy.data.collections.new("Junctions"); sc.collection.children.link(juncs)
Z = 1.0; ROAD_W, SIDE_W, TONGUE = 8.0, 2.0, 10.0


def tongue(name, start, d):
    d = Vector(d).normalized(); n = Vector((-d.y, d.x, 0.0)); s = Vector(start)
    me = bpy.data.meshes.new(name); bm = bmesh.new(); lay = bm.faces.layers.float.new("mrs_tongue")
    for a0, a1, l0, l1, k in ((0, TONGUE, -ROAD_W / 2, ROAD_W / 2, 1.0), (0, TONGUE, ROAD_W / 2, ROAD_W / 2 + SIDE_W, 2.0), (0, TONGUE, -ROAD_W / 2 - SIDE_W, -ROAD_W / 2, 2.0)):
        f = bm.faces.new([bm.verts.new(s + d * a + n * l) for a, l in ((a0, l0), (a1, l0), (a1, l1), (a0, l1))]); f[lay] = k
    bm.to_mesh(me); bm.free()
    dr = me.attributes.new("mrs_drop", "FLOAT", "POINT")
    for i, v in enumerate(me.vertices): dr.data[i].value = AJ.TONGUE_DROP; v.co.z -= AJ.TONGUE_DROP
    o = bpy.data.objects.new(name, me); roads.objects.link(o); return o

TS = [((TONGUE - 2.0, 0, Z), (-1, 0, 0)), ((-TONGUE + 2.0, 0, Z), (1, 0, 0)), ((0, TONGUE - 2.0, Z), (0, -1, 0)), ((0, -TONGUE + 2.0, Z), (0, 1, 0))]
for k, (s_, d_) in enumerate(TS): tongue("T%d" % k, s_, d_)
BAY = AJ.add_extension("Bay", "square", roads, (7.0, 6.0, Z), (6.0, 4.0))
LANE = AJ.add_extension("Lane", "curve", roads, (0, 0, 0), points=[(-3.0, -3.0, Z), (-14.0, -14.0, Z)])
J = AJ.add_area_junction("J", (0.0, 0.0, 0.0), roads, juncs)
SIGN = CS.add_custom_sign("Sign", (60.0, 0.0, 0.0), "CRM 2.1", juncs)
LINES = ML.add_marking_lines("Lines", [(100.0, 0.0, 0.0), (100.0, 30.0, 0.0)], juncs, **{"Center Marking": True, "Lane Marking": True})


def mesh(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
    verts = [M @ v.co for v in me.vertices]; me.calc_loop_triangles()
    mats = [m.name if m else "" for m in me.materials]
    tris = [(tuple(t.vertices), mats[me.polygons[t.polygon_index].material_index] if mats else "") for t in me.loop_triangles]
    fe = set()
    for p in me.polygons: fe.update(p.edge_keys)
    loose = sum(1 for e in me.edges if e.key not in fe)
    down = sum(1 for p in me.polygons if (M.to_3x3() @ p.normal).z < -0.5)
    faces = [(mats[p.material_index] if mats else "", [M @ me.vertices[i].co for i in p.vertices]) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, tris, loose, down, faces


def surface(verts, tris, prefix):
    sel = [t for t, m in tris if m.startswith(prefix)]
    return BVHTree.FromPolygons(verts, sel) if sel else None


def hit(bvh, x, y):
    if bvh is None: return None
    h = bvh.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)), 200.0); return None if h[0] is None else h[0].z


def check_junction():
    verts, tris, loose, down, faces = mesh(J); out = []
    if not tris: return ["no faces"]
    if any(not all(math.isfinite(c) for c in v) for v in verts): out.append("non-finite vertices")
    if loose: out.append("%d loose edges" % loose)
    if down: out.append("%d faces face down" % down)
    if not mod_input_get(J.modifiers[0], "Show"): return out
    road = surface(verts, tris, "MRS_Asphalt"); side = surface(verts, tris, "MRS_Paving")
    r_in = mod_input_get(J.modifiers[0], "Inner Radius") + 0.5
    missing = both = 0
    for s_, d_ in TS:
        d = Vector(d_); n = Vector((-d.y, d.x, 0.0))
        for a in (2.0, 5.0, 8.0):
            for l in (-2.5, 0.0, 2.5):
                p = Vector(s_) + d * a + n * l
                if abs(p.x) < ROAD_W / 2 + r_in and abs(p.y) < ROAD_W / 2 + r_in and abs(abs(p.x) - abs(p.y)) < r_in: continue    # fillet zone
                if hit(road, p.x, p.y) is None: missing += 1
    for i in range(-30, 31):
        for j in range(-30, 31):
            x, y = i * 0.5 + 0.25, j * 0.5 + 0.25
            if hit(road, x, y) is not None and hit(side, x, y) is not None:
                # a shared boundary through the cell centre hits both: count only an overlap that has area (it persists
                # 5 cm off the centre in at least three of four directions)
                around = sum(1 for dx, dy in ((0.05, 0.05), (-0.05, 0.05), (0.05, -0.05), (-0.05, -0.05))
                             if hit(road, x + dx, y + dy) is not None and hit(side, x + dx, y + dy) is not None)
                if around >= 3: both += 1
    if missing: out.append("%d red footprint points without road" % missing)
    if both: out.append("%d cells with road and roadside" % both)
    return out


def check_sign():
    verts, tris, loose, down, faces = mesh(SIGN); out = []
    if not tris: return ["no faces"]
    if any(not all(math.isfinite(c) for c in v) for v in verts): out.append("non-finite vertices")
    m = SIGN.modifiers[0]; sx = mod_input_get(m, "Scale X"); sy = mod_input_get(m, "Scale Y"); ph = mod_input_get(m, "Panel Height")
    cx = SIGN.location.x
    colour = "MRS_SignFace_" + str(mod_input_get(m, "Color"))
    rot = mod_input_get(m, "Rotation")
    pv = []; pt = []
    for mat, vs in faces:
        if mat == colour:
            b = len(pv); pv += vs; pt += [tuple(range(b, b + len(vs)))]
    panel = [v for v in pv]
    if panel and abs(math.sin(rot)) < 1e-3:                      # the bounding box equals the panel only unrotated
        w = max(v.x for v in panel) - min(v.x for v in panel); h = max(v.z for v in panel) - min(v.z for v in panel)
        if abs(w - sx) > 0.01 or abs(h - sy) > 0.01: out.append("panel %.3f x %.3f, inputs %.3f x %.3f" % (w, h, sx, sy))
    # paint (text, lines, images) on the panel: a ray from each vertex into the panel (+y) hits it (1 cm tolerance)
    pb = BVHTree.FromPolygons(pv, pt) if pt else None
    def on_panel(v):
        if pb is None: return False
        for dx, dz in ((0, 0), (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01)):
            if pb.ray_cast(Vector((v.x + dx, v.y - 0.05, v.z + dz)), Vector((0, 1, 0)), 0.2)[0] is not None: return True
        return False
    outside = 0
    for mat, vs in faces:
        if mat == colour or "Metal" in mat or "Grey" in mat: continue
        if any(not on_panel(v) for v in vs): outside += 1
    if outside: out.append("%d text / line faces off the panel" % outside)
    post = [v for mat, vs in faces if "Metal" in mat or mat.endswith("Grey") for v in vs]
    if mod_input_get(m, "Poles Count") > 0 and post and min(v.z for v in post) > 0.01: out.append("the post does not reach the ground")
    return out


def check_lines():
    verts, tris, loose, down, faces = mesh(LINES); out = []
    if any(not all(math.isfinite(c) for c in v) for v in verts): out.append("non-finite vertices")
    rs = mod_input_get(LINES.modifiers[0], "Road Size")
    far = sum(1 for mat, vs in faces if any(abs(v.x - 100.0) > rs / 2 + 1.0 for v in vs))
    if far: out.append("%d painted faces beyond Road Size / 2 + 1 m" % far)
    return out

GROUPS = {"MRS_AreaJunction": (J, check_junction), "MRS_ExtensionMesh": (BAY, check_junction), "MRS_ExtensionCurve": (LANE, check_junction),
          "MRS_CustomSign": (SIGN, check_sign), "MRS_MarkingLines": (LINES, check_lines)}


def sweep(group, obj, check, name, typ, default, lo, hi):
    mod = obj.modifiers[0]; evals = []; t0 = time.time()
    def run(v):
        v = int(round(v)) if typ == "int" else float(v)
        mod_input_set(mod, name, v); obj.update_tag(); J.update_tag()
        try: probs = check()
        except Exception as e: probs = ["exception %s" % e]
        evals.append({"value": v, "pass": not probs, "problems": probs[:4]}); return not probs
    grid = sorted({int(round(lo + (hi - lo) * k / (GRID - 1))) for k in range(GRID)}) if typ == "int" else sorted({lo + (hi - lo) * k / (GRID - 1) for k in range(GRID)})
    ok = {v: run(v) for v in grid}
    ok[default] = run(default)
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
    mod_input_set(mod, name, default); obj.update_tag(); J.update_tag()
    rec = {"group": group, "param": name, "type": typ, "default": default, "declared": [lo, hi], "regions": refined, "allowed": allowed,
           "gaps": [[allowed[k][1], allowed[k + 1][0]] for k in range(len(allowed) - 1)], "limit": [min(x[0] for x in allowed), max(x[1] for x in allowed)] if allowed else None,
           "default_passes": ok[default], "n_evals": len(evals), "seconds": round(time.time() - t0, 1), "evals": evals}
    print("%-18s %-22s %-5s declared [%g, %g] regions %s -> allowed %s (%d evals, %.0fs)%s" % (group, name, typ, lo, hi, [[round(r[0], 3), round(r[1], 3)] for r in refined],
          [[round(x, 3) for x in r] for r in allowed], len(evals), time.time() - t0, "" if ok[default] else "  DEFAULT FAILS"))
    return rec


os.makedirs(os.path.join(OUT, "area"), exist_ok=True)
for g, (o, chk) in GROUPS.items():
    p = chk(); print("SELFTEST %s: %s" % (g, "OK" if not p else p))
summary = {}
for g, (o, chk) in GROUPS.items():
    for it in bpy.data.node_groups[g].interface.items_tree:
        if it.item_type != "SOCKET" or it.in_out != "INPUT" or it.socket_type not in ("NodeSocketFloat", "NodeSocketInt"): continue
        rec = sweep(g, o, chk, it.name, "int" if it.socket_type == "NodeSocketInt" else "float", mod_input_get(o.modifiers[0], it.name), it.min_value, it.max_value)
        with open(os.path.join(OUT, "area", "%s_%s.json" % (g, it.name.replace(" ", "_"))), "w") as f: json.dump(rec, f, indent=1, default=str)
        summary["%s/%s" % (g, it.name)] = {k: rec[k] for k in ("type", "default", "declared", "regions", "allowed", "gaps", "limit", "default_passes", "n_evals")}
        with open(os.path.join(OUT, "area_summary.json"), "w") as f: json.dump(summary, f, indent=1, default=str)
print("AREA_SWEEP done %d inputs" % len(summary))
