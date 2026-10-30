"""Checks for the parameter-limit sweeps (tools/roads/limits). Each check takes evaluated geometry and returns a list
of problem strings (empty = pass). Every check must pass on the defaults (calibrated by sweep.py's self-test).

Road checks
  eval        the road evaluates: a mesh with faces, finite coordinates
  fold        no part of the road's own walking / driving surface lies over another part of it (a strip folding over
              itself on the inside of a tight bend, a taper crossing over): a raster of the up-facing base surfaces,
              each cell's layers counted by repeated ray casts
  flipped     every base surface faces up
  degenerate  no zero-area or needle faces in the base surfaces
  width       the carriageway measured across the road (from the `lat` attribute) matches road_widths()
  paint       paint (markings, kind 1) lies on a base surface, at most PAINT_LIFT above it, never floating or buried
  validate    mrs.validate.check_road finds no problem
  props       instanced objects: gullies / manholes on the carriageway; roadside objects (lights, trees, signs, props)
              on a surface within PROP_DROP, never on the carriageway; no two closer than 0.5 m
"""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

BASE_KINDS = (0, 5, 6, 9, 11)        # asphalt, bike, paving, bus, apron: surfaces cars / people stand on
CARRIAGEWAY_KINDS = (0, 5, 9)
PAINT_KIND = 1
FOLD_CELL = 0.5                      # m raster (a fold is metres wide; detector_test.py proves a 4 m-radius fold is found)
FOLD_DZ = 0.03                       # two layers closer than this are one surface (seams, crown)
PAINT_LIFT = 0.03                    # paint at most this far above the surface under it
PROP_DROP = 0.25                     # a prop's base at most this far above / below the surface under it
WIDTH_TOL = 0.03


def mesh_data(obj, dg):
    """Evaluated mesh facts: world verts, polys (vertex index lists), per-face kind / normal / area / centre, per-vertex lat."""
    ev = obj.evaluated_get(dg); me = ev.to_mesh(); M = obj.matrix_world; N = M.to_3x3()
    try:
        verts = [M @ v.co for v in me.vertices]
        kind = me.attributes.get("kind"); kv = [d.value for d in kind.data] if kind is not None and kind.domain == "FACE" else [0.0] * len(me.polygons)
        lat = me.attributes.get("lat"); lv = [d.value for d in lat.data] if lat is not None and lat.domain == "POINT" else None
        faces = []
        for p in me.polygons:
            n = (N @ p.normal).normalized() if p.normal.length > 0 else Vector((0, 0, 0))
            faces.append({"v": list(p.vertices), "kind": int(round(kv[p.index])), "n": n, "area": p.area, "c": M @ p.center})
        me.calc_loop_triangles()
        tris = [(tuple(t.vertices), t.polygon_index) for t in me.loop_triangles]
    finally:
        ev.to_mesh_clear()
    return {"verts": verts, "faces": faces, "lat": lv, "tris": tris}


def check_eval(md):
    if not md["faces"]: return ["no faces"]
    bad = sum(1 for v in md["verts"] if not all(math.isfinite(c) for c in v))
    return ["%d non-finite vertices" % bad] if bad else []


def _base_tris(md, kinds=BASE_KINDS):
    return [t for t, pi in md["tris"] if md["faces"][pi]["kind"] in kinds and md["faces"][pi]["n"].z > 0.5]


def check_flipped(md):
    bad = [f for f in md["faces"] if f["kind"] in BASE_KINDS and f["area"] > 1e-4 and abs(f["n"].z) > 0.5 and f["n"].z < 0]
    return ["%d base surface faces face down (e.g. at %s)" % (len(bad), tuple(round(c, 1) for c in bad[0]["c"]))] if bad else []


def check_degenerate(md):
    bad = 0
    for f in md["faces"]:
        if f["kind"] not in BASE_KINDS: continue
        vs = [md["verts"][i] for i in f["v"]]
        per = sum((vs[k] - vs[(k + 1) % len(vs)]).length for k in range(len(vs)))
        if per > 1e-6 and f["area"] < 1e-6 and per > 0.05: bad += 1               # a sliver: long edges, no area
    return ["%d degenerate base faces" % bad] if bad else []


def layers_raster(md, kinds=BASE_KINDS, cell=FOLD_CELL, dz=FOLD_DZ, bounds=None):
    """{(i, j): [z, ...]} distinct surface heights over each cell centre (top-down repeated ray casts)."""
    tris = _base_tris(md, kinds)
    if not tris: return {}
    vs = md["verts"]; bvh = BVHTree.FromPolygons(vs, tris)
    used = {i for t in tris for i in t}
    xs = [vs[i].x for i in used]; ys = [vs[i].y for i in used]; zs = [vs[i].z for i in used]
    x0, x1, y0, y1 = bounds or (min(xs), max(xs), min(ys), max(ys))
    top = max(zs) + 5.0; bottom = min(zs) - 5.0; out = {}
    for i in range(int(math.floor(x0 / cell)), int(math.ceil(x1 / cell)) + 1):
        for j in range(int(math.floor(y0 / cell)), int(math.ceil(y1 / cell)) + 1):
            o = Vector(((i + 0.5) * cell, (j + 0.5) * cell, top)); zl = []
            while True:
                h = bvh.ray_cast(o, Vector((0, 0, -1)), o.z - bottom)
                if h[0] is None: break
                if not zl or zl[-1] - h[0].z > dz: zl.append(h[0].z)
                o = Vector((o.x, o.y, h[0].z - 1e-4))
                if len(zl) > 6: break
            if zl: out[(i, j)] = zl
    return out


def check_fold(md, cell=FOLD_CELL):
    ras = layers_raster(md, cell=cell)
    bad = [(k, z) for k, z in ras.items() if len(z) > 1]
    if not bad: return []
    (i, j), z = bad[len(bad) // 2]
    return ["surface folds over itself: %d cells (%.1f m2) with %d layers (e.g. at %.1f, %.1f)" % (len(bad), len(bad) * cell * cell, len(z), (i + 0.5) * cell, (j + 0.5) * cell)]


def check_width(md, road, at=None):
    """The asphalt / bike / bus lateral extent at a few stations equals road_widths' half_l + half_r."""
    from mrs.roads import road_widths
    if md["lat"] is None: return []
    w = road_widths(road); want_l, want_r = w["half_l"], w["half_r"]
    lats = [md["lat"][i] for f in md["faces"] if f["kind"] in CARRIAGEWAY_KINDS for i in f["v"]]
    if not lats: return ["no carriageway faces"]
    got_l, got_r = -min(lats), max(lats)
    out = []
    if abs(got_l - want_l) > WIDTH_TOL or abs(got_r - want_r) > WIDTH_TOL:
        out.append("carriageway %.2f / %.2f m, the profile says %.2f / %.2f" % (got_l, got_r, want_l, want_r))
    return out


def check_paint(md):
    """Every paint face's centre lies over a base surface, PAINT_LIFT or less above it (not floating, not buried)."""
    tris = _base_tris(md)
    if not tris: return []
    bvh = BVHTree.FromPolygons(md["verts"], tris); bad_f = bad_b = bad_n = 0
    for f in md["faces"]:
        if f["kind"] != PAINT_KIND or f["n"].z < 0.5: continue
        c = f["c"]; h = bvh.ray_cast(c + Vector((0, 0, 0.5)), Vector((0, 0, -1)), 3.0)
        if h[0] is None: bad_n += 1; continue
        d = c.z - h[0].z
        if d > PAINT_LIFT: bad_f += 1
        elif d < -0.002: bad_b += 1
    out = []
    if bad_n: out.append("%d paint faces over no surface" % bad_n)
    if bad_f: out.append("%d paint faces floating > %.0f mm" % (bad_f, PAINT_LIFT * 1000))
    if bad_b: out.append("%d paint faces buried under the surface" % bad_b)
    return out


def check_validate(road, dg):
    from mrs import validate
    validate._CACHE.clear(); out = []
    validate.check_road(road, dg, validate._instances(dg), out)
    return ["%s: %s" % (p["check"], p["message"]) for p in out]


IN_ROAD = ("MRS_Gully", "MRS_Manhole", "MRS_Drain")      # items that belong ON the carriageway
SKIP_INST = ("MRS_Arrow", "MRS_Mark", "MRS_Text", "MRS_Bike", "MRS_Merge")   # paint (check_paint covers it)


def check_props(road, md, dg, scene_ground=None):
    """Instanced objects of the road: in-road items (gullies, manholes) lie on the carriageway within PROP_DROP of it;
    roadside items (lights, trees, props, signs) stand on a surface within PROP_DROP (the road's own or the scene
    ground) and never on the carriageway; no two closer than 0.5 m."""
    from mrs.nodes import mod_input_get
    sc_col = mod_input_get(road.modifiers["MRS_Road"], "Scatter") if "MRS_Road" in road.modifiers else None
    scatter = {o.name for o in sc_col.all_objects} if sc_col is not None else set()       # vegetation: may clump together
    inst = []
    for i in dg.object_instances:
        if not i.is_instance or i.parent is None or i.parent.original.name != road.name: continue
        nm = i.object.original.name
        if nm == road.name or nm.startswith(SKIP_INST) or "Paint" in nm: continue
        inst.append((nm, i.matrix_world.translation.copy()))
    if not inst: return []
    vs = md["verts"]
    all_tris = [t for t, pi in md["tris"] if md["faces"][pi]["n"].z > 0.3]
    cw_tris = [t for t, pi in md["tris"] if md["faces"][pi]["kind"] in CARRIAGEWAY_KINDS and md["faces"][pi]["n"].z > 0.5]
    bvh = BVHTree.FromPolygons(vs, all_tris) if all_tris else None
    cw = BVHTree.FromPolygons(vs, cw_tris) if cw_tris else None
    def cw_z(p):
        if cw is None: return None
        h = cw.ray_cast(p + Vector((0, 0, 2.0)), Vector((0, 0, -1)), 6.0)
        return h[0].z if h[0] is not None else None
    out = []; in_off = in_float = side_on_cw = side_float = 0
    for nm, p in inst:
        zc = cw_z(p)
        if nm.startswith(IN_ROAD):
            if zc is None: in_off += 1
            elif abs(p.z - zc) > PROP_DROP: in_float += 1
            continue
        if zc is not None and abs(zc - p.z) < PROP_DROP: side_on_cw += 1
        h = bvh.ray_cast(p + Vector((0, 0, 2.0)), Vector((0, 0, -1)), 6.0) if bvh else (None,)
        hg = scene_ground(p) if scene_ground else None
        z = max([x for x in (h[0].z if h[0] is not None else None, hg) if x is not None], default=None)
        if z is None or abs(p.z - z) > PROP_DROP: side_float += 1
    if in_off: out.append("%d gullies / manholes off the carriageway" % in_off)
    if in_float: out.append("%d gullies / manholes float / sink (> %.2f m from the carriageway)" % (in_float, PROP_DROP))
    if side_on_cw: out.append("%d roadside objects stand on the carriageway" % side_on_cw)
    if side_float: out.append("%d roadside objects float / sink (> %.2f m from a surface)" % (side_float, PROP_DROP))
    items = sorted(inst, key=lambda t: tuple(t[1])); close = 0
    for a in range(len(items)):
        for b in range(a + 1, min(a + 12, len(items))):
            if items[a][0] in scatter and items[b][0] in scatter: continue              # grass beside grass is fine
            if (items[a][1] - items[b][1]).length < 0.5: close += 1
    if close: out.append("%d pairs of objects closer than 0.5 m (not both scatter)" % close)
    return out


def road_checks(road, dg, which=("eval", "flipped", "degenerate", "fold", "width", "paint", "validate", "props"), scene_ground=None):
    """{check: [problems]} for one road."""
    md = mesh_data(road, dg); res = {}
    if "eval" in which: res["eval"] = check_eval(md)
    if res.get("eval"): return res
    if "flipped" in which: res["flipped"] = check_flipped(md)
    if "degenerate" in which: res["degenerate"] = check_degenerate(md)
    if "fold" in which: res["fold"] = check_fold(md)
    if "width" in which: res["width"] = check_width(md, road)
    if "paint" in which: res["paint"] = check_paint(md)
    if "validate" in which: res["validate"] = check_validate(road, dg)
    if "props" in which: res["props"] = check_props(road, md, dg, scene_ground)
    return res
