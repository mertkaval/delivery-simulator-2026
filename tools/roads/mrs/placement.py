"""Rule-based street-asset placement, v4: footprints + access envelopes on an explicit sidewalk zone model.

Sidewalk zones per road side, measured as d (m) from the kerb line (asphalt edge + kerb width) outward:
    planting / furniture strip  [0, strip]          trees, grass, shrubs, benches on pads, racks, lights
    kerb zone (no strip)        [0, kerb_zone]      lights, signs, bollards, hydrants, bus pole
    furniture zone              [.., walk0]         benches, bins, racks, cabinets, tree pits, shelters
    walking corridor            [walk0, walk1]      continuous, width >= RULES["walk_min"]; no physical footprint
    frontage                    [walk1, sw]
Every candidate is an oriented rectangle (its `mrs_footprint`) plus an access envelope (`mrs_access`:
front / back / left / right clearances): the footprint may not touch any other footprint, access
envelope or reserved area; the access envelope may not touch another footprint or leave the paving
(it may overlap the walking corridor, except bike-rack access which must stay out of it).

Priority (each step sees everything placed before it):
  1. reservations: walking corridors, crossing landings + kerb ramps, junction corners, sight triangles,
     bus boarding areas, entrance / driveway / exclusion anchors, footbridge approaches, foot paths and
     columns, signal poles (from the junction builder);
  2. infrastructure: signs by condition, bus stops (shelter aligned to the kerb, pole, board, bin, pad),
     streetlights (road-class preset: spacing, setback, arrangement), hydrants, drain grates (gutter,
     spacing + upstream of crossings), utility cabinets (near junctions, outside sight triangles) with
     access covers;
  3. furniture: benches (front clearance), bins near activity points, bike racks (access out of the
     walking corridor), planters;
  4. planting: trees (species by street style and space; canopy checked against lights, signs, signals,
     traffic / cycleway clearance, footbridges; tree pits with grates on paving, mulch on strips), then
     landscape scatter in explicit regions (planting strips, park edges) by layered density.
A skipped optional asset is recorded with its reason. Deterministic for a seed. Everything placed goes to
`<roads collection>_Placed` (cleared first: no multiplying) with stable names `<road>_<kind>_<side><n>`.
"""
import bpy, bmesh, math, random, json, zlib
from mathutils import Vector
from .nodes import MRS
from .roads import all_roads, road_widths, road_input
from .structures import road_sample, road_length, centre_line, surface_z

RULES = {
    "walk_min": 1.8, "frontage": 0.3, "kerb_zone": 0.7, "pad_margin": 0.25,
    "light_spacing_scale": 1.0, "light_min_gap": 6.0,
    "tree_spacing": 12.0, "tree_scale": (0.85, 1.05), "tree_traffic_clear": 4.6, "tree_bike_clear": 2.6, "tree_walk_clear": 2.3,
    "tree_light_clear": 1.2, "sign_window": 30.0, "signal_window": 40.0,
    "bench_spacing": 36.0, "rack_spacing": 55.0, "bin_spacing": 60.0, "hydrant_spacing": 90.0, "drain_spacing": 24.0,
    "planter_spacing": 0.0, "cabinets": True,
    "sign_setback": 0.5, "speed_sign_from_start": 12.0,
    "crossing_landing": 1.2, "corner_extra": 3.0, "sightline": 12.0,
    "bus_boarding": 12.0, "bus_boarding_depth": 1.6,
    "grass_density": 1.6, "ground_z": -0.12, "landscape": {}, "default_landscape": "verge", "entrance_paths": True, "shrub_cluster_spacing": 9.0, "hedge_gap_at_paths": 2.5, "landscape_depth": 7.0,
}
STYLE_TREES = {"avenue": ["plane_tree", "linden_a", "linden_b", "linden_c"], "residential": ["linden_c", "maple_a", "maple_b", "cherry", "linden_a"],
               "boulevard": ["plane_tree", "linden_b"], "park": ["walnut_spring", "grove_a", "grove_b", "linden_b", "maple_c"]}
LIB = {"bench": ("MRS_F_Bench", "MRS_Bench_Wood"), "bench_backless": ("MRS_F_BenchBackless", "MRS_Bench_Modern"),
       "bin": ("MRS_F_BinWaste", "MRS_Bin_Round"), "bin_recycling": ("MRS_F_BinRecycling", "MRS_Bin_Square"),
       "rack": ("MRS_F_BikeRackRow", "MRS_BikeRack"), "rack1": ("MRS_F_BikeRackHoop", "MRS_BikeRack"),
       "shelter": ("MRS_F_BusShelter", "MRS_BusStopShelter"), "bus_pole": ("MRS_F_BusStopPole", "MRS_Sign_BusStop"),
       "info_board": ("MRS_F_InfoBoard", "MRS_Kiosk"), "bollard": ("MRS_F_Bollard", "MRS_Bollard_Steel"),
       "barrier": ("MRS_F_PedBarrier", "MRS_Railing"), "planter": ("MRS_F_Planter", "MRS_Planter"),
       "pit_grate": ("MRS_F_TreePitGrate",), "pit_open": ("MRS_F_TreePitOpen",), "cabinet": ("MRS_F_UtilityCabinet",),
       "hydrant": ("MRS_F_Hydrant", "MRS_Hydrant"), "drain": ("MRS_F_DrainGrate", "MRS_Gully1"), "cover": ("MRS_F_AccessCover", "MRS_Manhole_Square")}
# fallback footprints / access (when a library object has no mrs_footprint / mrs_access)
DEFAULT = {"bench": ((1.8, 0.65), {"front": 0.9}), "bench_backless": ((1.9, 0.5), {"front": 0.8, "back": 0.8}), "bin": ((0.6, 0.6), {"front": 0.6}),
           "bin_recycling": ((0.75, 0.75), {"front": 0.6}), "rack": ((2.2, 0.08), {"front": 1.0, "back": 1.0}), "rack1": ((0.8, 0.08), {"front": 1.0, "back": 1.0}),
           "shelter": ((3.3, 1.65), {"front": 1.5}), "bus_pole": ((0.3, 0.3), {}), "info_board": ((1.2, 0.4), {"front": 1.0}), "bollard": ((0.25, 0.25), {}),
           "barrier": ((2.0, 0.1), {}), "planter": ((1.0, 1.0), {"front": 0.3, "back": 0.3, "left": 0.3, "right": 0.3}), "pit_grate": ((1.2, 1.2), {}),
           "pit_open": ((1.2, 2.0), {}), "cabinet": ((0.9, 0.45), {"front": 0.9}), "hydrant": ((0.45, 0.4), {"front": 0.9, "back": 0.5, "left": 0.6, "right": 0.6}),
           "drain": ((0.6, 0.45), {}), "cover": ((0.7, 0.7), {}), "light": ((0.4, 0.4), {}), "sign": ((0.3, 0.3), {}), "signal": ((0.5, 0.5), {}), "tree": ((0.7, 0.7), {}),
           "column": ((0.9, 0.9), {})}
FLUSH = {"pit_grate", "drain", "cover", "pad"}
TALL = {"tree", "shelter", "cabinet", "planter", "info_board", "hedge", "shrub"}


# ============================================================================ geometry
class Rect:
    """Oriented rectangle in world XY: centre c, unit axes ux, uy, half extents hx, hy."""
    __slots__ = ("c", "ux", "uy", "hx", "hy")

    def __init__(self, c, ux, hx, hy):
        self.c = Vector((c.x, c.y)); self.ux = Vector((ux.x, ux.y)).normalized(); self.uy = Vector((-self.ux.y, self.ux.x)); self.hx = hx; self.hy = hy

    def corners(self):
        return [self.c + self.ux * sx * self.hx + self.uy * sy * self.hy for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    def overlaps(self, o, tol=0.0):
        for ax in (self.ux, self.uy, o.ux, o.uy):
            ra = abs(self.ux.dot(ax)) * self.hx + abs(self.uy.dot(ax)) * self.hy
            rb = abs(o.ux.dot(ax)) * o.hx + abs(o.uy.dot(ax)) * o.hy
            if abs((o.c - self.c).dot(ax)) >= ra + rb - tol: return False
        return True

    def contains(self, p, margin=0.0):
        d = Vector((p.x, p.y)) - self.c
        return abs(d.dot(self.ux)) <= self.hx + margin and abs(d.dot(self.uy)) <= self.hy + margin

    def circle(self, p, r):
        d = Vector((p.x, p.y)) - self.c
        qx = max(-self.hx, min(self.hx, d.dot(self.ux))); qy = max(-self.hy, min(self.hy, d.dot(self.uy)))
        return (d - self.ux * qx - self.uy * qy).length < r


def _poly_circle(poly, p, r):
    """Circle (p, r) intersects the convex polygon (list of 2D points)?"""
    P = Vector((p.x, p.y)); inside = True
    n = len(poly)
    for i in range(n):
        a = Vector(poly[i][:2]); b = Vector(poly[(i + 1) % n][:2]); e = b - a
        t = max(0.0, min(1.0, (P - a).dot(e) / max(e.length_squared, 1e-9)))
        if (a + e * t - P).length < r: return True
        if e.x * (P.y - a.y) - e.y * (P.x - a.x) < 0: inside = False
    if inside: return True
    inside2 = all(((Vector(poly[(i + 1) % n][:2]) - Vector(poly[i][:2])).x * (P.y - poly[i][1]) - (Vector(poly[(i + 1) % n][:2]) - Vector(poly[i][:2])).y * (P.x - poly[i][0])) > 0 for i in range(n))
    return inside2


class Occupancy:
    """Reserved areas, footprints and access envelopes on a 4 m spatial hash (entries: dicts with
    t = keep | solid | access, r = Rect, alive flag)."""
    CELL = 4.0

    def __init__(self):
        self.entries = []; self.grid = {}; self.canopy = []

    def _cells(self, r, pad=0.0):
        cs = r.corners(); xs = [c.x for c in cs]; ys = [c.y for c in cs]
        C = self.CELL
        for ix in range(int(math.floor((min(xs) - pad) / C)), int(math.floor((max(xs) + pad) / C)) + 1):
            for iy in range(int(math.floor((min(ys) - pad) / C)), int(math.floor((max(ys) + pad) / C)) + 1):
                yield (ix, iy)

    def _add(self, e):
        self.entries.append(e)
        for c in self._cells(e["r"]): self.grid.setdefault(c, []).append(e)
        return e

    def add_keep(self, r, why, blocks): return self._add({"t": "keep", "r": r, "why": why, "blocks": blocks, "alive": True})
    def add_solid(self, r, owner, kind): return self._add({"t": "solid", "r": r, "owner": owner, "kind": kind, "alive": True})

    def add(self, foot, access, owner, kind):
        self.add_solid(foot, owner, kind)
        for a in access: self._add({"t": "access", "r": a, "owner": owner, "alive": True})

    def near(self, r, pad=0.0):
        seen = set(); out = []
        for c in self._cells(r, pad):
            for e in self.grid.get(c, ()):
                if e["alive"] and id(e) not in seen: seen.add(id(e)); out.append(e)
        return out

    def keeps(self, prefix):
        return [e for e in self.entries if e["t"] == "keep" and e["why"].startswith(prefix) and e["alive"]]

    def solids(self, kind=None):
        return [e for e in self.entries if e["t"] == "solid" and e["alive"] and (kind is None or e["kind"] == kind)]

    def blocked(self, foot, access, kind, owner, cat, height=1.0):
        near = self.near(foot)
        for e in near:
            if e["t"] == "keep":
                b = e["blocks"]
                if ("*" in b or cat in b or (height > 1.2 and "tall" in b and cat not in ("sign", "light", "signal", "bus_pole"))) and e["r"].overlaps(foot, 0.01): return "reserved: " + e["why"]
        for e in near:
            if e["t"] == "solid" and e["r"].overlaps(foot, 0.01): return "overlaps %s" % e["owner"]
            if e["t"] == "access" and e["owner"] != owner and kind not in FLUSH and e["r"].overlaps(foot, 0.01): return "inside the access space of %s" % e["owner"]
        for a in access:
            for e in self.near(a):
                if e["t"] == "solid" and e["kind"] not in FLUSH and e["r"].overlaps(a, 0.01): return "its access space hits %s" % e["owner"]
        return None


# ============================================================================ road side model
def _smooth(v): v = max(0.0, min(1.0, v)); return v * v * (3 - 2 * v)


class RoadModel:
    """Per-road geometry used by every rule: drawn extent, half widths along the taper, side zones."""
    def __init__(self, road):
        self.road = road; self.name = road.name
        self.w0 = road_widths(road); self.w1 = road_widths(road, at_end=True) if road_input(road, "Transition") else self.w0
        self.trans = bool(road_input(road, "Transition"))
        self.t0 = road_input(road, "Transition Start") or 0.0; self.tl = max(road_input(road, "Taper Length") or 1.0, 0.1)
        cl = centre_line(road); self.A0 = cl[0][0]; self.A1 = cl[-1][0]; self.L = self.A1
        self.rht = self.w0["rht"]; self.curb = self.w0["curb"]; self.h = self.w0["h"]
        self.strip = {s: min(road_input(road, "Planting Strip Right" if s == "r" else "Planting Strip Left") or 0.0, max(0.0, (self.w0["sw" + s] if False else (self.w0["swr"] if s == "r" else self.w0["swl"])) - 1.0)) for s in ("l", "r")}
        self.sw = {"l": self.w0["swl"], "r": self.w0["swr"]}

    def w_at(self, a):
        """road_widths at station a (numeric fields interpolated through the lane taper like the road group)."""
        if not self.trans: return self.w0
        f = _smooth((a - self.t0) / self.tl)
        return {k: (v + (self.w1[k] - v) * f) if isinstance(v, (int, float)) and not isinstance(v, bool) else (self.w1[k] if f > 0.5 else v) for k, v in self.w0.items()}

    def half(self, a, s):
        if not self.trans: return self.w0["half_" + s]
        f = _smooth((a - self.t0) / self.tl)
        return self.w0["half_" + s] + (self.w1["half_" + s] - self.w0["half_" + s]) * f

    def frame(self, a):
        return road_sample(self.road, a)

    def point(self, a, s, d, lift=0.0):
        """World point d m beyond the kerb line on side s at station a, on the evaluated surface."""
        p, t, r = road_sample(self.road, a); sgn = 1.0 if s == "r" else -1.0
        lat = self.half(a, s) + self.curb + d
        q = p + r * sgn * lat
        q.z = surface_z(self.road, a, sgn * lat) + lift
        return q, t, r * sgn

    def zones(self, s):
        sw = self.sw[s]; strip = self.strip[s]
        if sw <= 0.05: return None
        walk1 = sw - RULES["frontage"]; walk0 = walk1 - RULES["walk_min"]
        if walk0 < 0.0: walk0, walk1 = 0.0, sw
        fz0 = 0.35; fz1 = walk0
        return {"sw": sw, "strip": strip, "walk0": walk0, "walk1": walk1, "fz": (fz0, fz1) if fz1 - fz0 >= 0.45 else None}


# ============================================================================ library helpers
def lib_object(kind):
    for n in LIB.get(kind, (kind,)):
        if n and bpy.data.objects.get(n): return bpy.data.objects[n]
    return None


def footprint(kind, obj=None):
    (w, d), acc = DEFAULT.get(kind, ((0.5, 0.5), {}))
    if obj is not None:
        try:
            if obj.get("mrs_footprint"): w, d = json.loads(obj["mrs_footprint"]) if isinstance(obj["mrs_footprint"], str) else tuple(obj["mrs_footprint"])
            if obj.get("mrs_access"): acc = json.loads(obj["mrs_access"]) if isinstance(obj["mrs_access"], str) else dict(obj["mrs_access"])
        except Exception: pass
    return float(w), float(d), {k: float(acc.get(k, 0.0)) for k in ("front", "back", "left", "right")}


def item_rects(pos, f_dir, w, d, acc):
    """Footprint rect (local X along ux = right of front) and access rects (front/back/left/right strips)."""
    fy = Vector((f_dir.x, f_dir.y)).normalized(); ux = Vector((fy.y, -fy.x))
    c = Vector((pos.x, pos.y))
    foot = Rect(c, ux, w / 2, d / 2)
    rs = []
    if acc.get("front", 0) > 0.01: rs.append(Rect(c + fy * (d / 2 + acc["front"] / 2), ux, w / 2, acc["front"] / 2))
    if acc.get("back", 0) > 0.01: rs.append(Rect(c - fy * (d / 2 + acc["back"] / 2), ux, w / 2, acc["back"] / 2))
    if acc.get("left", 0) > 0.01: rs.append(Rect(c - ux * (w / 2 + acc["left"] / 2), ux, acc["left"] / 2, d / 2))
    if acc.get("right", 0) > 0.01: rs.append(Rect(c + ux * (w / 2 + acc["right"] / 2), ux, acc["right"] / 2, d / 2))
    return foot, rs


def _place(lib, name, pos, yaw, col, scale=1.0, kind=None, meta=None):
    src = bpy.data.objects.get(lib) if isinstance(lib, str) else lib
    if src is None: return None
    o = bpy.data.objects.new(name, src.data); col.objects.link(o)
    o.location = pos; o.rotation_euler = (0, 0, yaw); o.scale = (scale, scale, scale)
    o["mrs_placed"] = src.name
    if kind: o["mrs_kind"] = kind
    for k, v in (meta or {}).items(): o[k] = v
    for ch in src.children:                       # signal heads / sign text children
        c2 = bpy.data.objects.new(name + ch.name[len(src.name):], ch.data); col.objects.link(c2)
        c2.parent = o; c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy(); c2.location = ch.location; c2.rotation_euler = ch.rotation_euler; c2.scale = ch.scale
    return o


def clear_placed(roads_col):
    col = bpy.data.collections.get(roads_col.name + "_Placed")
    if col:
        for o in list(col.objects):
            d = o.data; bpy.data.objects.remove(o)
            if d is not None and getattr(d, "users", 1) == 0 and isinstance(d, bpy.types.Mesh) and d.name.startswith("MRS_PL_"): bpy.data.meshes.remove(d)
    else:
        col = bpy.data.collections.new(roads_col.name + "_Placed"); roads_col.children.link(col)
    return col


def _yaw(f): return math.atan2(f.y, f.x) - math.pi / 2


# ============================================================================ main entry
def place_all(roads_col, seed=0, style="avenue", speed_limits=None, bus_stops=None, rules=None, log=None):
    """Run the whole placement for every road in the collection. Returns a report dict:
    placed [(road, kind, side, along, lib)], skipped [(road, kind, along, reason)], counts, by_kind,
    items [{name, kind, road, side, along, pos, foot (corners), solid}], regions (landscape)."""
    if rules: RULES.update(rules)
    from . import structures as _st
    rng = random.Random(seed)
    col = clear_placed(roads_col)
    roads = all_roads(roads_col)
    for r in roads: centre_line(r)
    _st.freeze([r.name for r in roads])
    try:
        return _place_all(roads_col, roads, col, rng, seed, style, speed_limits, bus_stops)
    finally:
        _st.freeze(None)


def _place_all(roads_col, roads, col, rng, seed, style, speed_limits, bus_stops):
    rep = {"placed": [], "skipped": [], "items": [], "regions": [], "corridors": {}}
    occ = Occupancy()
    speed_limits = speed_limits or {}
    models = {r.name: RoadModel(r) for r in roads if road_length(r) >= 4.0}
    ends = {n: _junction_ends(m.road) for n, m in models.items()}
    bridges = _footbridges(roads_col)
    ctx = dict(col=col, rep=rep, occ=occ, rng=rng, models=models, ends=ends, bridges=bridges, style=style, seed=seed)
    # ---------------------------------------------------------------- 1. reservations
    for n, m in models.items(): _reserve_road(ctx, m)
    _reserve_signals(ctx, roads_col)
    _reserve_bridges(ctx)
    _reserve_anchors(ctx, roads_col)
    _reserve_buildings(ctx)
    stops = list(bus_stops or []) + _bus_anchor_list(roads_col)
    for st in stops: _reserve_bus(ctx, st)
    # ---------------------------------------------------------------- 2. infrastructure
    for n, m in models.items(): _signs(ctx, m, speed_limits)
    for st in stops: _bus_stop(ctx, st)
    for n, m in models.items(): _lights(ctx, m)
    for n, m in models.items(): _utilities(ctx, m)
    # ---------------------------------------------------------------- 3. furniture
    for n, m in models.items(): _furniture(ctx, m)
    # ---------------------------------------------------------------- 4. planting
    for n, m in models.items(): _trees(ctx, m)
    for n, m in models.items(): _landscape(ctx, m)
    rep["_occ"] = occ; rep["_ctx_models"] = models
    rep["counts"] = {"placed": len(rep["placed"]), "skipped": len(rep["skipped"])}
    by = {}
    for _, kind, *_r in rep["placed"]: by[kind] = by.get(kind, 0) + 1
    rep["by_kind"] = by
    why = {}
    for x in rep["skipped"]:
        k = x[3].split(":")[0] if x[3].startswith("reserved") else x[3].split(" ")[0]
        why[x[1] + " / " + k] = why.get(x[1] + " / " + k, 0) + 1
    rep["skip_summary"] = why
    return rep


def _skip(ctx, m, kind, a, reason):
    ctx["rep"]["skipped"].append((m.name if m else "-", kind, round(a, 1), reason))


def _put(ctx, m, s, a, d, kind, lib_kind=None, f_dir=None, lift=0.0, cat=None, owner=None, extra_access=None, scale=1.0, quiet=False,
         allow_strip=True, pad=False, meta=None, access_no_walk=False, pos=None):
    """Try to place one library item at station a, d m from the kerb on side s, front toward f_dir
    ('out' = away from the road, 'in' = toward the road, 'along', 'traffic' or a Vector)."""
    lib_kind = lib_kind or kind; cat = cat or kind
    src = lib_object(lib_kind)
    if src is None:
        if not quiet: _skip(ctx, m, kind, a, "library object missing: %s" % "/".join(LIB.get(lib_kind, (lib_kind,))))
        return None
    if pos is None:
        pos, t, n = m.point(a, s, d, lift)
    else:
        p_, t, r_ = m.frame(a); n = r_ * (1.0 if s == "r" else -1.0)
    if f_dir == "out": fv = n
    elif f_dir == "in": fv = -n
    elif f_dir == "along": fv = t
    elif f_dir == "traffic":
        travel = 1.0 if ((s == "r") == m.rht) else -1.0; fv = -t * travel
    elif isinstance(f_dir, Vector): fv = f_dir
    else: fv = n
    w, dd, acc = footprint(lib_kind, src)
    if extra_access: acc = dict(acc, **extra_access)
    foot, accs = item_rects(pos, fv, w * scale, dd * scale, acc)
    owner = owner or "%s_%s_%s%d" % (m.name, kind, s, len([x for x in ctx["rep"]["items"] if x["road"] == m.name and x["kind"] == kind and x["side"] == s]))
    height = float(src.get("mrs_height", src.dimensions.z)) * scale
    why = ctx["occ"].blocked(foot, accs, lib_kind, owner, cat, height)
    if why is None and access_no_walk:
        for a_ in accs:
            for e in ctx["occ"].near(a_):
                if e["t"] == "keep" and e["why"].startswith("walking corridor") and e["r"].overlaps(a_, 0.01): why = "bike access would enter the walking corridor"; break
            if why: break
    if why is None and cat in ("bench", "bin", "rack", "cabinet", "planter", "bus", "info_board"):
        # access envelopes must stay on paving / strip of this side (not on the carriageway)
        z = m.zones(s)
        if z is not None:
            for a_ in accs:
                for cpt in a_.corners():
                    dd_ = (Vector((cpt.x, cpt.y, 0)) - Vector((m.frame(a)[0].x, m.frame(a)[0].y, 0))).dot(n) - (m.half(a, s) + m.curb)
                    if dd_ < -0.05 and kind not in ("drain",): why = "access space would reach into the carriageway"; break
                if why: break
    if why:
        if not quiet: _skip(ctx, m, kind, a, why)
        return None
    o = _place(src, owner, pos, _yaw(fv), ctx["col"], scale, kind, dict(meta or {}, mrs_road=m.name, mrs_side=s, mrs_along=round(a, 2)))
    ctx["occ"].add(foot, accs, owner, lib_kind)
    ctx["rep"]["placed"].append((m.name, kind, s, round(a, 1), src.name))
    ctx["rep"]["items"].append({"name": owner, "kind": kind, "lib": src.name, "road": m.name, "side": s, "along": round(a, 2), "d": round(d, 2),
                                "pos": [round(c, 3) for c in pos], "yaw": round(_yaw(fv), 4), "scale": scale, "foot": [[round(c.x, 3), round(c.y, 3)] for c in foot.corners()],
                                "flush": lib_kind in FLUSH, "access": [[[round(c.x, 3), round(c.y, 3)] for c in r.corners()] for r in accs]})
    if pad: _pad(ctx, m, s, a, pos, fv, w * scale + 2 * RULES["pad_margin"], dd * scale + acc.get("front", 0) * 0.6 + 2 * RULES["pad_margin"], owner)
    return o


# ============================================================================ reservations
def _junction_ends(road):
    out = {}
    for o in bpy.data.objects:
        m = o.get("mrs_junction")
        if not m or road.name not in list(m.get("roads", [])): continue
        m = dict(m)
        for ap in m.get("approaches", []):
            if ap["road"] == road.name: out[ap["end"]] = dict(ap, junction=o.name, control=m.get("control", "none"), crossing=bool(m.get("crosswalks", True)),
                                                          type=m.get("type", "junction"), setback=m.get("stop_setback", 0.6))
        if m.get("type") in ("dead_end",) and road.name in m.get("roads", []):
            out[m.get("end", "end")] = {"junction": o.name, "type": "dead_end", "crossing": False, "control": "none", "lanes_in": 1, "trim": 0.0}
        if m.get("type") == "roundabout":
            for rn in m.get("roads", []):
                if rn == road.name:
                    # which end touches the roundabout
                    from .roads import road_ends
                    at = Vector(m["at"]); e = min(road_ends(road), key=lambda x: (x[0] - at).length)
                    out["start" if e[2] else "end"] = {"junction": o.name, "type": "roundabout", "crossing": bool(m.get("crossings", True)), "control": "yield", "lanes_in": 1,
                                                       "trim": 0.0, "setback": m.get("crossing_setback", 1.0)}
    return out


def _end_span(m, end):
    """(a_lo, a_hi) of the station interval next to a road end, and the station of the end itself."""
    return (m.A0, +1) if end == "start" else (m.A1, -1)


def _reserve_road(ctx, m):
    occ = ctx["occ"]; R = RULES
    for s in ("l", "r"):
        z = m.zones(s)
        if z is None: continue
        # walking corridor, piecewise rects every 3 m
        a = m.A0; strips = []
        while a < m.A1:
            b = min(m.A1, a + 3.0); am = (a + b) / 2
            p0, t0, n0 = m.point(am, s, (z["walk0"] + z["walk1"]) / 2)
            occ.add_keep(Rect(p0, t0, (b - a) / 2 + 0.05, (z["walk1"] - z["walk0"]) / 2), "walking corridor (%s %s)" % (m.name, s), {"*"})
            a = b
        ctx["rep"]["corridors"]["%s_%s" % (m.name, s)] = {"walk0": z["walk0"], "walk1": z["walk1"], "sw": z["sw"], "strip": z["strip"]}
    for end, ap in ctx["ends"][m.name].items():
        a_end, dirn = _end_span(m, end)
        if ap.get("type") == "dead_end": continue
        cw = 2.5; setback = ap.get("setback", 0.6)
        land = setback + cw + R["crossing_landing"] if ap.get("crossing") else 2.0
        corner = land + R["corner_extra"]
        for s in ("l", "r"):
            if m.sw[s] <= 0.05: continue
            sw = m.sw[s]
            def rect(a0, a1, d0, d1):
                am = a_end + dirn * (a0 + a1) / 2; p, t, n = m.point(am, s, (d0 + d1) / 2)
                return Rect(p, t, abs(a1 - a0) / 2, (d1 - d0) / 2)
            if ap.get("crossing"):
                occ.add_keep(rect(0.0, land, -0.3, sw + 0.3), "crossing landing / kerb ramp (%s)" % ap["junction"], {"*"})
            occ.add_keep(rect(0.0, corner, -0.3, sw + 0.3), "junction corner (%s)" % ap["junction"], {"furniture", "tree", "light", "utility", "bus", "bench", "bin", "rack", "planter", "cabinet", "shelter"})
            occ.add_keep(rect(0.0, R["sightline"] + corner, -0.3, sw + 6.0), "junction sightline (%s)" % ap["junction"], {"tall"})


def _reserve_signals(ctx, roads_col):
    for o in roads_col.all_objects:
        if o.get("mrs_signal_id"):
            p = o.matrix_world.translation
            ctx["occ"].add_solid(Rect(p, Vector((1, 0, 0)), 0.3, 0.3), o.name, "signal")


def _footbridges(roads_col):
    out = []
    for o in roads_col.all_objects:
        if o.get("mrs_footbridge_plan") and o.type == "MESH":
            try: out.append((o, json.loads(o["mrs_footbridge_plan"])))
            except Exception: pass
    return out


def _reserve_bridges(ctx):
    occ = ctx["occ"]
    for o, plan in ctx["bridges"]:
        for fp in plan.get("footprint", []):
            pts = [Vector((p[0], p[1])) for p in fp["poly"]]
            c = sum(pts, Vector((0, 0))) / len(pts)
            ux = (pts[1] - pts[0]); hx = ux.length / 2; hy = (pts[3] - pts[0]).length / 2
            r = Rect(c, ux, hx, hy)
            occ.add_keep(r, "footbridge %s %s" % (o.name, fp["kind"]), {"tree", "light", "tall", "plant", "shelter"} if fp["kind"] == "span" else {"*"})
        for e in plan.get("ped_edges", []):
            pts = [Vector(q) for q in e["approach_path"]]
            for a_, b_ in zip(pts, pts[1:]):
                d = b_ - a_; d.z = 0
                if d.length < 0.05: continue
                occ.add_keep(Rect((a_ + b_) / 2, d, d.length / 2 + 0.8, 1.6), "footbridge foot path %s" % o.name, {"*"})
        for sp in plan.get("supports", []):
            occ.add_solid(Rect(Vector(sp["pos"]), Vector((1, 0, 0)), 0.6, 0.6), "%s column" % o.name, "column")


def _reserve_anchors(ctx, roads_col):
    """MRS_Entrance_* (building entrances: a 2.4 m access path to the walking corridor), MRS_Driveway_*,
    MRS_Exclude_* (manual override: nothing optional inside display size)."""
    occ = ctx["occ"]
    for o in bpy.data.objects:
        if o.type != "EMPTY": continue
        nm = o.name
        if nm.startswith("MRS_Exclude"):
            s = max(o.empty_display_size, 1.0)
            occ.add_keep(Rect(o.location, Vector((1, 0, 0)), s, s), "manual exclusion " + nm, {"*"})
        elif nm.startswith(("MRS_Entrance", "MRS_Driveway")):
            road = bpy.data.objects.get(o.get("mrs_road", ""))
            m = ctx["models"].get(road.name) if road else None
            if m is None: continue
            a = _project(m, o.location); s = o.get("mrs_side", "r")
            q, t, n = m.point(a, s, 0.0)
            far = Vector((o.location.x, o.location.y, 0)); near = Vector((q.x, q.y, 0))
            d = far - near; L = d.length
            wid = 2.4 if nm.startswith("MRS_Entrance") else float(o.get("mrs_width", 4.0)) + 2.0    # driveway + its kerb-drop flanks
            occ.add_keep(Rect((far + near) / 2, d if L > 0.1 else t, max(L, 0.5) / 2 + 0.3, wid / 2), ("entrance " if wid < 3 else "driveway ") + nm, {"*"})


def _reserve_buildings(ctx):
    """Frontage buildings (objects with `mrs_building` JSON: world footprint) and their service yards
    (`mrs_kind` drive) are keep-out areas for everything optional (landscape, trees, furniture)."""
    occ = ctx["occ"]
    for o in bpy.data.objects:
        poly = None
        if o.type == "MESH" and o.get("mrs_building"):
            poly = [Vector((p[0], p[1], 0.0)) for p in json.loads(o["mrs_building"]).get("footprint", [])]
        elif o.type == "MESH" and o.get("mrs_kind") == "drive":
            M = o.matrix_world; vs = [M @ v.co for v in o.data.vertices]
            if vs:
                # oriented box of the slab: its first edge direction
                e = (vs[1] - vs[0]); e.z = 0
                d_ = e.normalized() if e.length > 1e-6 else Vector((1, 0, 0)); n_ = Vector((-d_.y, d_.x, 0))
                us = [v.dot(d_) for v in vs]; ws = [v.dot(n_) for v in vs]
                poly = [d_ * u + n_ * w_ for u, w_ in ((min(us), min(ws)), (max(us), min(ws)), (max(us), max(ws)), (min(us), max(ws)))]
        if not poly or len(poly) < 4: continue
        c = sum(poly, Vector()) / len(poly); a_ = poly[1] - poly[0]; b_ = poly[3] - poly[0]
        occ.add_keep(Rect(c, a_ if a_.length > 1e-6 else Vector((1, 0, 0)), a_.length / 2 + 0.6, b_.length / 2 + 0.6), "building " + o.name, {"*"})
        if o.get("mrs_building") and b_.length > 1e-6:
            # active frontage: the 1.6 m in front of shop windows / doors stays free of cabinets, bins, planters and
            # info boards (benches, lights, trees and racks keep their own rules); poly[0]-poly[1] is the facade
            n_ = b_.normalized(); fc = (poly[0] + poly[1]) / 2 - n_ * 0.8
            occ.add_keep(Rect(fc, a_, a_.length / 2, 0.8), "active frontage " + o.name, {"cabinet", "bin", "planter", "info_board", "hydrant", "cover"})
        ctx["rep"].setdefault("buildings", []).append(o.name)


def _project(m, pos):
    """Station of the point on the road centre line nearest to pos (projected onto the centre-line segments,
    not just the nearest sample: the samples are ~2.5 m apart)."""
    cl = centre_line(m.road); P = Vector((pos.x, pos.y)); best = None
    for (a0, p0), (a1, p1) in zip(cl, cl[1:]):
        A = Vector((p0.x, p0.y)); Bv = Vector((p1.x, p1.y)); d = Bv - A; L2 = d.length_squared
        f = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (P - A).dot(d) / L2))
        dd = (A + d * f - P).length
        if best is None or dd < best[0]: best = (dd, a0 + (a1 - a0) * f)
    return best[1] if best else cl[0][0]


def _bus_anchor_list(roads_col):
    out = []
    for o in bpy.data.objects:
        if o.type == "EMPTY" and o.name.startswith("MRS_BusStopAnchor") and o.get("mrs_road"):
            road = bpy.data.objects.get(o["mrs_road"])
            if road is None: continue
            out.append({"id": o.name[len("MRS_BusStopAnchor_"):] or o.name, "road": road.name, "along": None, "pos": o.location.copy(), "side": o.get("mrs_side", "r")})
    return out


def _bus_frame(ctx, st):
    m = ctx["models"].get(st["road"])
    if m is None: return None, None
    a = st["along"] if st.get("along") is not None else _project(m, st["pos"])
    st["along_resolved"] = a
    return m, a


def _reserve_bus(ctx, st):
    m, a = _bus_frame(ctx, st)
    if m is None: return
    s = st.get("side", "r"); z = m.zones(s)
    if z is None: return
    L = RULES["bus_boarding"]; D = RULES["bus_boarding_depth"]
    p, t, n = m.point(a, s, D / 2)
    ctx["occ"].add_keep(Rect(p, t, L / 2, D / 2), "bus boarding area (%s)" % st["id"], {"furniture", "tree", "light", "utility", "bench", "bin", "rack", "planter", "cabinet", "sign", "plant", "hydrant", "bollard"})


# ============================================================================ 2. infrastructure
def _signs(ctx, m, speed_limits):
    """Signs by explicit conditions (v3 rules): approach control, crossings, one-way entries, speed zones,
    cycleway starts; street-name blades once per junction; all face the traffic they address."""
    R = RULES; road = m.road
    try:
        from . import signage
    except ImportError:
        signage = None
    for end, ap in ctx["ends"][m.name].items():
        if ap.get("type") in ("dead_end",): continue
        a_end, dirn = _end_span(m, end)
        arriving = ("r" if m.rht else "l") if end == "end" else ("l" if m.rht else "r")
        a_sign = a_end + dirn * (ap.get("setback", 0.6) + 2.5 + R["crossing_landing"] + 1.5)
        a_sign = min(max(a_sign, m.A0 + 1.0), m.A1 - 1.0)
        if ap.get("lanes_in", 1) <= 0:
            _put(ctx, m, arriving, a_sign, R["sign_setback"], "sign_no_entry", "MRS_Sign_NoEntry", "traffic", cat="sign"); continue
        ctrl = ap.get("control", "none")
        if ap.get("type") == "roundabout":
            _put(ctx, m, arriving, a_sign, R["sign_setback"], "sign_yield", "MRS_Sign_Yield", "traffic", cat="sign")
        elif ctrl == "stop" or (ctrl == "priority" and not ap.get("main")):
            k = "MRS_Sign_Stop" if ctrl == "stop" else "MRS_Sign_Yield"
            _put(ctx, m, arriving, a_sign, R["sign_setback"], "sign_" + ("stop" if ctrl == "stop" else "yield"), k, "traffic", cat="sign")
        elif ctrl == "priority" and ap.get("main"):
            _put(ctx, m, arriving, a_sign, R["sign_setback"], "sign_priority", "MRS_Sign_PriorityRoad", "traffic", cat="sign")
        if ap.get("crossing"):
            _put(ctx, m, arriving, a_sign + dirn * 6.0, R["sign_setback"], "sign_crossing", "MRS_Sign_PedestrianCrossing", "traffic", cat="sign")
        jn = ap.get("junction")
        if jn and signage is not None and not any(o.name.startswith(jn + "_streetname") for o in ctx["col"].objects):
            names = [bpy.data.objects[rn].get("mrs_street_name", rn) for rn in bpy.data.objects[jn]["mrs_junction"]["roads"] if rn in bpy.data.objects]
            uniq = list(dict.fromkeys(names))
            if len(uniq) >= 2:
                try:
                    pos, t, n = m.point(a_sign + dirn * 2.0, arriving, R["sign_setback"] + 0.4)
                    foot = Rect(pos, t, 0.35, 0.35)
                    why = ctx["occ"].blocked(foot, [], "sign", jn, "sign")
                    if why: _skip(ctx, m, "sign_street_name", a_sign, why)
                    else:
                        so = signage.make_sign(jn + "_streetname", "street_name", text=uniq[0][:14] + "|" + uniq[1][:14], double=True, collection=ctx["col"])
                        so.location = pos; so.rotation_euler = (0, 0, math.atan2(t.y, t.x)); so["mrs_placed"] = "street_name"; so["mrs_kind"] = "sign_street_name"
                        ctx["occ"].add(foot, [], so.name, "sign")
                        ctx["rep"]["placed"].append((m.name, "sign_street_name", arriving, round(a_sign, 1), "street_name"))
                except Exception as e:
                    _skip(ctx, m, "sign_street_name", a_sign, "signage error: %s" % e)
    sp = speed_limits.get(m.name)
    if sp:
        lib = "MRS_Sign_Speed%d" % sp if bpy.data.objects.get("MRS_Sign_Speed%d" % sp) else "MRS_Sign_Speed50"
        for side, a in (("r" if m.rht else "l", m.A0 + R["speed_sign_from_start"] + 8.0), ("l" if m.rht else "r", m.A1 - R["speed_sign_from_start"] - 8.0)):
            for k in range(4):
                if _put(ctx, m, side, a + (k * 3.0 if side == ("r" if m.rht else "l") else -k * 3.0), R["sign_setback"], "sign_speed", lib, "traffic", cat="sign", quiet=k < 3): break
    w = m.w0
    if w["lanes_b"] == 0 or w["lanes_f"] == 0:
        _put(ctx, m, "r" if m.rht else "l", m.A0 + 10.0 if w["lanes_f"] > 0 else m.A1 - 10.0, R["sign_setback"], "sign_one_way", "MRS_Sign_OneWay", "traffic", cat="sign")
    for side in ("l", "r"):
        if w.get("bike_on_" + side):
            fwd_side = (side == "r") == m.rht
            a = m.A0 + 14.0 if fwd_side else m.A1 - 14.0
            for k in range(4):
                if _put(ctx, m, side, a + (k * 2.5 if fwd_side else -k * 2.5), R["sign_setback"], "sign_bicycle", "MRS_Sign_BicycleRoute", "traffic", cat="sign", quiet=k < 3): break


def _bus_stop(ctx, st):
    """Shelter in the furniture zone with its open side to the kerb, boarding area kept clear, flag pole at
    the front end of the boarding area (facing the arriving bus), information board, bin, boarding pad and
    BUS STOP lane marking. Skips (with reason) when the sidewalk cannot hold shelter + walking corridor."""
    m, a = _bus_frame(ctx, st)
    if m is None: return
    s = st.get("side", "r"); z = m.zones(s)
    if z is None: _skip(ctx, m, "bus_stop", a, "no sidewalk on side " + s); return
    D = RULES["bus_boarding_depth"]
    src = lib_object("shelter"); w, d, acc = footprint("shelter", src)
    # the shelter stands at the back of the sidewalk, open side to the kerb; the boarding area and the
    # walking corridor share the paving in front of it (the planting strip is paved along the stop)
    d_sh = z["sw"] - RULES["frontage"] - d / 2
    clear = d_sh - d / 2
    if clear < max(D, RULES["walk_min"]) - 0.01:
        _skip(ctx, m, "bus_shelter", a, "sidewalk %.1f m: %.2f m left in front of a %.2f m deep shelter < %.1f m (boarding / walking)" % (z["sw"], clear, d, max(D, RULES["walk_min"])))
        d_sh = None
    travel = 1.0 if ((s == "r") == m.rht) else -1.0
    # remove the boarding keep-out for the bus items themselves (they are part of the stop)
    occ = ctx["occ"]
    keep = occ.keeps("bus boarding area (%s)" % st["id"])
    for k in keep: k["alive"] = False
    placed = []
    if d_sh is not None:
        # the corridor moves in front of the shelter here: drop the corridor rects overlapping the shelter, add a shifted one
        p, t, n = m.point(a, s, d_sh)
        foot, accs = item_rects(p, -n, w, d, {})
        for k in [k for k in occ.keeps("walking corridor (%s %s)" % (m.name, s)) if k["r"].overlaps(foot)]: k["alive"] = False
        pc, tc, nc = m.point(a, s, (d_sh - d / 2) / 2)
        occ.add_keep(Rect(pc, tc, w / 2 + 2.0, (d_sh - d / 2) / 2 - 0.05), "walking corridor (%s %s) at the bus stop" % (m.name, s), {"tree", "bench", "rack", "planter", "cabinet", "light", "hydrant", "plant"})
        o = _put(ctx, m, s, a, d_sh, "bus_shelter", "shelter", "in", cat="bus", meta={"mrs_bus_stop": st["id"]})
        if o: placed.append(o)
    # the stop flag at the front of the boarding area; if a sign already stands there it steps back along the boarding area
    o = None
    for back in (0.5, 1.5, 2.5, 3.5):
        pole_a = a + travel * (RULES["bus_boarding"] / 2 - back)
        o = _put(ctx, m, s, pole_a, 0.45, "bus_pole", "bus_pole", "traffic", cat="bus_pole", meta={"mrs_bus_stop": st["id"]}, quiet=back != 3.5)
        if o: placed.append(o); break
    if d_sh is not None:
        for ob in (_put(ctx, m, s, a - travel * (w / 2 + 1.0), d_sh, "bus_info", "info_board", "in", cat="bus", meta={"mrs_bus_stop": st["id"]}),
                   _put(ctx, m, s, a + travel * (w / 2 + 0.8), d_sh, "bin", "bin", "in", cat="bus", meta={"mrs_bus_stop": st["id"]})):
            if ob: placed.append(ob)
    for k in keep: k["alive"] = True
    # boarding pad (paving over the planting strip along the boarding area) + BUS STOP lane text
    if z["strip"] > 0.05:
        p, t, n = m.point(a, s, z["strip"] / 2)
        _slab(ctx, "%s_busstop_pad" % m.name, p, t, n, RULES["bus_boarding"] + 1.0, z["strip"] + 0.02, 0.025, bpy.data.materials.get(MRS + "Paving"))
    try:
        from .structures import _text_mesh
        p, t, r = m.frame(a); sgn = 1.0 if s == "r" else -1.0
        q = p + r * sgn * (m.half(a, s) - 1.7); q.z = surface_z(m.road, a, sgn * (m.half(a, s) - 1.7)) + 0.006
        tm = _text_mesh("BUS STOP", 1.1, 0.002); tm.name = "MRS_PL_bustext"
        if bpy.data.materials.get(MRS + "Paint"): tm.materials.append(bpy.data.materials[MRS + "Paint"])
        to = bpy.data.objects.new("%s_busstop_text" % m.name, tm); ctx["col"].objects.link(to)
        to.location = q; to.rotation_euler = (0, 0, math.atan2(t.y, t.x) - math.pi / 2 + (math.pi / 2 if sgn > 0 else -math.pi / 2))
        to["mrs_placed"] = "bus_text"; to["mrs_kind"] = "marking"
    except Exception as e:
        _skip(ctx, m, "bus_marking", a, "text error %s" % e)
    ctx["rep"].setdefault("bus_stops", []).append({"id": st["id"], "road": m.name, "side": s, "along": round(a, 2), "items": [o.name for o in placed],
                                                   "boarding": [round(a - RULES["bus_boarding"] / 2, 2), round(a + RULES["bus_boarding"] / 2, 2)],
                                                   "point": [round(c, 3) for c in m.point(a, s, RULES["bus_boarding_depth"] / 2)[0]]})


def _slab(ctx, name, centre, t, n, length, depth, thick, material):
    """A thin paved slab (boarding pad, furniture pad) on the surface, edges bevelled down so nothing floats."""
    bm = bmesh.new()
    hx, hy = length / 2, depth / 2
    top = [centre + t * sx * hx + n * sy * hy + Vector((0, 0, thick)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bot = [centre + t * sx * (hx + 0.02) + n * sy * (hy + 0.02) + Vector((0, 0, -0.03)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    vt = [bm.verts.new(q) for q in top]; vb = [bm.verts.new(q) for q in bot]
    bm.faces.new(vt)
    for i in range(4): bm.faces.new((vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]))
    me = bpy.data.meshes.new("MRS_PL_" + name); bm.to_mesh(me); bm.free()
    uv = me.uv_layers.new(name="UVMap")
    for li, l in enumerate(me.loops):
        co = me.vertices[l.vertex_index].co; uv.data[li].uv = (co.x, co.y)
    if material: me.materials.append(material)
    o = bpy.data.objects.new(name, me); ctx["col"].objects.link(o); o["mrs_placed"] = "pad"; o["mrs_kind"] = "pad"
    return o


def _pad(ctx, m, s, a, pos, f_dir, w, d, owner):
    z = m.zones(s)
    if z is None or z["strip"] < 0.05: return
    # only when the item stands in the planting strip
    p, t, n = m.frame(a)
    dd = (Vector((pos.x, pos.y, 0)) - Vector((p.x, p.y, 0))).dot(n * (1.0 if s == "r" else -1.0)) - (m.half(a, s) + m.curb)
    if dd > z["strip"] + 0.1: return
    fy = Vector((f_dir.x, f_dir.y, 0)).normalized(); ux = Vector((fy.y, -fy.x, 0))
    c = pos.copy(); c.z = pos.z - 0.0
    _slab(ctx, owner + "_pad", c + fy * 0.15, ux, fy, w, d, 0.02, bpy.data.materials.get(MRS + "Paving"))


def _light_preset(m):
    w = m.w0
    carriage = w["half_l"] + w["half_r"]
    cls = "urban" if carriage > 14.0 else ("residential" if carriage > 6.0 else "path")
    try:
        from . import lighting
        p = dict(lighting.preset_for(cls, carriage)); p["_lighting"] = lighting; p["_class"] = cls
        return p
    except Exception:
        lib = "MRS_Light_Double" if (w["median"] >= 1.5) else ("MRS_Light_LED" if carriage < 14 else "MRS_Light_Highway")
        return {"lib": lib, "spacing": 28.0 if carriage < 14 else 32.0, "setback": 0.5, "arrangement": "median" if w["median"] >= 1.5 else ("staggered" if carriage > 12 else "single_right"),
                "_class": cls}


def _lights(ctx, m):
    """Streetlights by road-class preset: spacing, setback, arrangement (single / opposite / staggered /
    median); real light sources added by mrs.lighting (separate from the emissive lamp mesh)."""
    pr = _light_preset(m); R = RULES
    lib = pr.get("lib") or pr.get("library") or "MRS_Light_LED"
    spacing = float(pr.get("spacing", 30.0)) * R["light_spacing_scale"]; setback = float(pr.get("setback", 0.5))
    arr = pr.get("arrangement", "staggered")
    if arr == "median" and m.w0["median"] < 1.5: arr = "staggered"
    ctx["rep"].setdefault("light_presets", {})[m.name] = {k: v for k, v in pr.items() if not k.startswith("_")}
    a = m.A0 + spacing * 0.5; k = 0
    lit = []
    while a < m.A1 - 2.0:
        if arr == "median":
            slots = [("m", 0.0)]
        elif arr == "opposite": slots = [("r", 0.0), ("l", 0.0)]
        elif arr == "staggered": slots = [("r" if k % 2 == 0 else "l", 0.0)]
        elif arr == "single_left": slots = [("l", 0.0)]
        else: slots = [("r", 0.0)]
        for s, _ in slots:
            ok = None
            for shift in (0.0, 2.0, -2.0, 4.0, -4.0):
                if s == "m":
                    p, t, r = m.frame(a + shift)
                    pos = p.copy(); pos.z = surface_z(m.road, a + shift, 0.0)
                    foot = Rect(pos, t, 0.25, 0.25)
                    why = ctx["occ"].blocked(foot, [], "light", "light", "light", 9.0)
                    if why: continue
                    o = _place(lib, "%s_light_m%d" % (m.name, k), pos, math.atan2(t.y, t.x), ctx["col"], 1.0, "light", {"mrs_road": m.name, "mrs_side": "m", "mrs_along": round(a + shift, 2)})
                    ctx["occ"].add(foot, [], o.name, "light"); ok = o
                    ctx["rep"]["placed"].append((m.name, "light", "m", round(a + shift, 1), lib))
                    ctx["rep"]["items"].append({"name": o.name, "kind": "light", "lib": lib, "road": m.name, "side": "m", "along": round(a + shift, 2), "pos": [round(c, 3) for c in pos], "flush": False, "foot": [[round(c.x, 3), round(c.y, 3)] for c in foot.corners()]})
                    break
                if m.sw[s] <= 0.05: break
                ok = _put(ctx, m, s, a + shift, setback, "light", lib, "in", cat="light", quiet=shift != -4.0)
                if ok: break
            if ok is not None:
                lit.append(ok)
                lg = pr.get("_lighting")
                if lg is not None:
                    try:
                        if RULES.get("light_sources", True): lg.add_light_sources(ok, pr)
                    except Exception as e: _skip(ctx, m, "light_source", a, "lighting error %s" % e)
        a += spacing; k += 1
    ctx.setdefault("lights", {})[m.name] = lit


def _utilities(ctx, m):
    """Hydrants (kerb zone, spacing, access all round), drain grates (gutter: spacing + upstream of each
    crossing), utility cabinets near each junction end just outside the sight triangle + an access cover."""
    R = RULES
    for s in ("l", "r"):
        z = m.zones(s)
        # drains in the gutter (inside the carriageway edge), first upstream of crossings, then by spacing
        sgn = 1.0 if s == "r" else -1.0
        gut = []
        for end, ap in ctx["ends"][m.name].items():
            if ap.get("type") == "dead_end": continue
            a_end, dirn = _end_span(m, end)
            gut.append(a_end + dirn * (ap.get("setback", 0.6) + 2.5 + 1.2))
        a = m.A0 + R["drain_spacing"] * 0.7
        while a < m.A1 - 4.0:
            if all(abs(a - g) > 6.0 for g in gut): gut.append(a)
            a += R["drain_spacing"]
        for i, a in enumerate(sorted(gut)):
            if not (m.A0 + 1.0 < a < m.A1 - 1.0): continue
            p, t, r = m.frame(a)
            lat = m.half(a, s) - 0.28
            pos = p + r * sgn * lat; pos.z = surface_z(m.road, a, sgn * lat) + 0.002
            _put(ctx, m, s, a, -0.28, "drain", "drain", "in", cat="drain", pos=pos, quiet=True)
        if z is None: continue
        # hydrant: one per side per block segment, near the first quarter, kerb zone
        a = m.A0 + max(20.0, (m.A1 - m.A0) * 0.25) if s == "r" else m.A1 - max(20.0, (m.A1 - m.A0) * 0.25)
        n_h = max(1, int((m.A1 - m.A0) / R["hydrant_spacing"]))
        for i in range(n_h):
            aa = a + (i * R["hydrant_spacing"] if s == "r" else -i * R["hydrant_spacing"])
            for sh in (0.0, 3.0, -3.0, 6.0, -6.0):
                if _put(ctx, m, s, aa + sh, max(0.45, min(z["strip"] / 2, 0.6)) if z["strip"] > 0.6 else 0.45, "hydrant", "hydrant", "in", cat="hydrant", quiet=sh != -6.0): break
        # utility cabinet near each junction end of this side (outside sight triangles), with an access cover
        if not R["cabinets"]: continue
        for end, ap in ctx["ends"][m.name].items():
            if ap.get("type") == "dead_end": continue
            if R.get("cabinet_controls") and ap.get("control", "none") not in R["cabinet_controls"]: continue     # e.g. signal controllers only
            a_end, dirn = _end_span(m, end)
            base = a_end + dirn * (ap.get("setback", 0.6) + 2.5 + R["crossing_landing"] + R["corner_extra"] + R["sightline"] + 1.5)
            if not (m.A0 < base < m.A1): continue
            fz = z["fz"]
            if fz is None: _skip(ctx, m, "cabinet", base, "no furniture zone (sidewalk %.1f m)" % z["sw"]); continue
            src = lib_object("cabinet"); w, d, acc = footprint("cabinet", src)
            dd = (fz[0] + fz[1]) / 2
            if fz[1] - fz[0] < d: _skip(ctx, m, "cabinet", base, "furniture zone %.2f m < cabinet depth %.2f m" % (fz[1] - fz[0], d)); continue
            for sh in (0.0, 2.0, 4.0, 6.0):
                o = _put(ctx, m, s, base + dirn * sh, dd, "cabinet", "cabinet", "out", cat="cabinet", quiet=sh != 6.0, pad=True)
                if o:
                    for c in (1.6, -1.6, 2.6):
                        if _put(ctx, m, s, base + dirn * sh + c, max(fz[0], dd - 0.1), "access_cover", "cover", "out", cat="flush", quiet=c != 2.6): break
                    break


# ============================================================================ 3. furniture
def _furniture(ctx, m):
    """Benches (front clearance onto the paving), bins next to benches / crossings / bus stops, bike racks
    with their access envelope outside the walking corridor; pads under items standing in a planting strip."""
    R = RULES; rng = ctx["rng"]
    for s in ("l", "r"):
        z = m.zones(s)
        if z is None: continue
        fz = z["fz"]
        if fz is None:
            _skip(ctx, m, "furniture", m.A0, "sidewalk %.1f m has no furniture zone beside the %.1f m walking corridor" % (z["sw"], R["walk_min"])); continue
        depth = fz[1] - fz[0]
        # benches
        a = m.A0 + R["bench_spacing"] * (0.45 if s == "r" else 0.75)
        while a < m.A1 - 3.0:
            kind = "bench" if rng.random() < 0.7 else "bench_backless"
            src = lib_object(kind); w, d, acc = footprint(kind, src)
            if depth < d: _skip(ctx, m, "bench", a, "furniture zone %.2f m < bench depth %.2f m" % (depth, d)); a += R["bench_spacing"]; continue
            dd = fz[1] - d / 2 - 0.05                         # bench back toward the kerb, front onto the walking corridor
            ok = None
            for sh in (0.0, 2.5, -2.5, 5.0, -5.0):
                ok = _put(ctx, m, s, a + sh, dd, "bench", kind, "out", cat="bench", quiet=sh != -5.0, pad=True)
                if ok: break
            if ok:
                # a bin beside the bench (activity point), not in front of it
                for side_off in (w / 2 + 0.75, -(w / 2 + 0.75)):
                    if _put(ctx, m, s, a + side_off + (ok["mrs_along"] - a), dd, "bin", "bin_recycling" if rng.random() < 0.3 else "bin", "out", cat="bin", quiet=True, pad=True): break
            a += R["bench_spacing"]
        # bike parking at destinations: a rack 5-13 m from every entrance anchor with mrs_bike_parking
        # (first free spot either way along the street), generic racks keep 25 m from it
        dest_racks = []
        for eo in bpy.data.objects:
            if eo.type != "EMPTY" or not eo.name.startswith("MRS_Entrance") or not eo.get("mrs_bike_parking"): continue
            if eo.get("mrs_road") != m.name or eo.get("mrs_side", "r") != s: continue
            a_e = _project(m, eo.location); ok = None
            for sh in (5.0, -5.0, 7.0, -7.0, 9.0, -9.0, 11.0, -11.0, 13.0, -13.0):
                if not (m.A0 + 2.0 < a_e + sh < m.A1 - 2.0): continue
                for kind in ("rack", "rack1"):
                    src = lib_object(kind); w, d, acc = footprint(kind, src)
                    need = d + acc.get("front", 0) + acc.get("back", 0)
                    f_ = m.frame(a_e + sh)[1] if depth + 0.35 < need else "out"
                    ok = _put(ctx, m, s, a_e + sh, (fz[0] + fz[1]) / 2, "bike_rack", kind, f_, cat="rack", quiet=True, pad=True, access_no_walk=True, meta={"serves": eo.name})
                    if ok: break
                if ok: break
            if ok:
                dest_racks.append(a_e + sh)
                ctx["rep"].setdefault("destination_racks", []).append({"entrance": eo.name, "rack": ok.name, "offset_m": sh})
            else:
                _skip(ctx, m, "bike_rack", a_e, "no rack spot 5-13 m from %s (furniture zone %.2f m)" % (eo.name, depth))
        # bike racks: access envelope out of the walking corridor (bikes stand in the furniture / strip zone)
        a = m.A0 + R["rack_spacing"] * (0.6 if s == "r" else 0.35)
        while a < m.A1 - 3.0:
            if any(abs(a - x) < 25.0 for x in dest_racks):
                a += R["rack_spacing"]; continue
            ok = None
            for kind in ("rack", "rack1"):
                src = lib_object(kind); w, d, acc = footprint(kind, src)
                need = d + acc.get("front", 0) + acc.get("back", 0)
                if depth + 0.35 < need:
                    # bikes parallel to the kerb: rotate the rack so its access runs along the street
                    for sh in (0.0, 3.0, -3.0):
                        p_, t_, r_ = m.frame(a + sh)
                        ok = _put(ctx, m, s, a + sh, (fz[0] + fz[1]) / 2, "bike_rack", kind, t_, cat="rack", quiet=not (kind == "rack1" and sh == -3.0), pad=True, access_no_walk=True)
                        if ok: break
                else:
                    for sh in (0.0, 3.0, -3.0):
                        ok = _put(ctx, m, s, a + sh, (fz[0] + fz[1]) / 2, "bike_rack", kind, "out", cat="rack", quiet=True, pad=True, access_no_walk=True)
                        if ok: break
                if ok: break
            if not ok and depth >= 1.0: pass
            elif not ok: _skip(ctx, m, "bike_rack", a, "no spot whose bike access stays out of the walking corridor (furniture zone %.2f m)" % depth)
            a += R["rack_spacing"]
        # bins near crossing landings (activity points)
        for end, ap in ctx["ends"][m.name].items():
            if not ap.get("crossing"): continue
            a_end, dirn = _end_span(m, end)
            base = a_end + dirn * (ap.get("setback", 0.6) + 2.5 + R["crossing_landing"] + R["corner_extra"] + 0.8)
            for sh in (0.0, 1.5, 3.0):
                if _put(ctx, m, s, base + dirn * sh, (fz[0] + fz[1]) / 2, "bin", "bin", "out", cat="bin", quiet=sh != 3.0, pad=True): break
        if R["planter_spacing"] > 0:
            a = m.A0 + R["planter_spacing"] / 2
            while a < m.A1:
                _put(ctx, m, s, a, (fz[0] + fz[1]) / 2, "planter", "planter", "out", cat="planter", quiet=False, pad=True); a += R["planter_spacing"]


# ============================================================================ 4. trees
def _tree_lib(sid):
    o = bpy.data.objects.get(MRS + "GTree_" + sid)
    if o is not None: return o, {"height": o.get("mrs_tree_height", 10.0), "reach": o.get("mrs_crown_reach", 4.0), "base": o.get("mrs_crown_base", 3.0), "trunk": o.get("mrs_trunk_radius", 0.25)}
    return None, None


def _trees(ctx, m):
    """Street trees in planting strips (or tree pits with grates in a furniture zone >= 1.3 m), species
    from the street style; each candidate tries species / scales until the crown clears traffic (crown
    base over the carriageway), cycleways, streetlight heads, sign and signal sightlines and footbridges."""
    R = RULES; rng = ctx["rng"]; pool = STYLE_TREES.get(R.get("road_styles", {}).get(m.name, ctx["style"]), STYLE_TREES["avenue"])
    lights = ctx.get("lights", {}).get(m.name, [])
    heads = []
    for lo in lights:
        src = bpy.data.objects.get(lo.get("mrs_placed", ""))
        reach = 0.0
        if src is not None and src.type == "MESH" and len(src.data.vertices):
            reach = max(abs(v.co.y) for v in src.data.vertices)
        yaw = lo.rotation_euler.z; fy = Vector((-math.sin(yaw), math.cos(yaw), 0))
        heads.append((lo.location + fy * reach * 0.8, src.dimensions.z if src else 8.0))
    signs = [it for it in ctx["rep"]["items"] if it["road"] == m.name and it["kind"].startswith("sign")]
    signals = [(e["r"].c, e["owner"]) for e in ctx["occ"].solids("signal")]
    for s in ("l", "r"):
        z = m.zones(s)
        if z is None: continue
        strip = z["strip"]
        mode = "strip" if strip >= 0.9 else ("pit" if z["fz"] and z["fz"][1] - z["fz"][0] >= 1.25 else None)
        if mode is None:
            _skip(ctx, m, "tree", m.A0, "side %s: no planting strip >= 0.9 m and no furniture zone >= 1.25 m for a tree pit" % s); continue
        d_tree = strip / 2 if mode == "strip" else (z["fz"][0] + z["fz"][1]) / 2
        # phase: midway between the streetlights on this side when possible
        a = m.A0 + R["tree_spacing"] * 0.5; k = 0
        while a < m.A1 - 1.0:
            placed = None; reasons = []
            order = pool[k % len(pool):] + pool[:k % len(pool)]
            for sid in order:
                src, info = _tree_lib(sid)
                if src is None: reasons.append("%s missing" % sid); continue
                for sc in (R["tree_scale"][1], (R["tree_scale"][0] + R["tree_scale"][1]) / 2, R["tree_scale"][0]):
                    for sh in (0.0, 1.5, -1.5):
                        why = _tree_check(ctx, m, s, a + sh, d_tree, info, sc, heads, signs, signals)
                        if why: reasons.append(why); continue
                        pos, t, n = m.point(a + sh, s, d_tree)
                        foot = Rect(pos, t, 0.35, 0.35)
                        why = ctx["occ"].blocked(foot, [], "tree", "tree", "tree", info["height"] * sc)
                        if why: reasons.append(why); continue
                        owner = "%s_tree_%s%d" % (m.name, s, k)
                        o = _place(src, owner, pos, rng.uniform(0, math.tau), ctx["col"], sc * rng.uniform(0.97, 1.03), "tree",
                                   {"mrs_road": m.name, "mrs_side": s, "mrs_along": round(a + sh, 2), "mrs_species": sid})
                        ctx["occ"].add(foot, [], owner, "tree"); ctx["occ"].canopy.append((pos, info["reach"] * sc, owner))
                        ctx["rep"]["placed"].append((m.name, "tree", s, round(a + sh, 1), src.name))
                        ctx["rep"]["items"].append({"name": owner, "kind": "tree", "lib": src.name, "species": sid, "road": m.name, "side": s, "along": round(a + sh, 2),
                                                    "pos": [round(c, 3) for c in pos], "yaw": round(o.rotation_euler.z, 4), "scale": round(o.scale.x, 3), "flush": False,
                                                    "foot": [[round(c.x, 3), round(c.y, 3)] for c in foot.corners()], "crown": round(info["reach"] * sc, 2)})
                        # tree base: grate on paving, mulch bed in a strip
                        if mode == "pit":
                            _put(ctx, m, s, a + sh, d_tree, "tree_pit", "pit_grate", "out", cat="flush", quiet=True)
                        else:
                            _mulch(ctx, owner, pos, min(0.7, strip / 2 - 0.05))
                        placed = o; break
                    if placed: break
                if placed: break
            if not placed: _skip(ctx, m, "tree", a, reasons[-1] if reasons else "no species fits")
            a += R["tree_spacing"]; k += 1


def _tree_check(ctx, m, s, a, d, info, sc, heads, signs, signals):
    R = RULES
    reach = info["reach"] * sc; base = info["base"] * sc
    pos, t, n = m.point(a, s, d)
    over = reach - (d + m.curb)                              # crown overhang into the carriageway
    if over > 0.2:
        bike = m.w0.get("bike_on_" + s)
        need = R["tree_traffic_clear"] if over > (m.w0["half_" + s] - m.w0.get("carr_" + s, m.w0["half_" + s])) else R["tree_bike_clear"]
        if bike and over <= (m.w0["half_" + s] - m.w0["bike0_" + s]): need = max(R["tree_bike_clear"], 0.0)
        if base < need: return "crown base %.1f m over the carriageway < %.1f m" % (base, need)
    if base < R["tree_walk_clear"]: return "crown base %.1f m over the sidewalk < %.1f m" % (base, R["tree_walk_clear"])
    for hp, hh in heads:
        if (Vector((hp.x, hp.y)) - Vector((pos.x, pos.y))).length < reach * 0.85 + R["tree_light_clear"] and hh > base:
            return "canopy would engulf a streetlight head"
    for it in signs:
        if it["side"] != s: continue
        da = it["along"] - a
        travel = 1.0 if ((s == "r") == m.rht) else -1.0
        up = da * travel                                      # >0: the tree stands upstream of the sign (between the driver and it)
        if -2.0 < up < R["sign_window"] and base < 3.4: return "would hide %s" % it["kind"]
    for c, o in signals:
        if (Vector((c.x, c.y)) - Vector((pos.x, pos.y))).length < R["signal_window"] * 0.4 and base < 5.6: return "would hide signal %s" % o
    for o, plan in ctx["bridges"]:
        for fp in plan.get("footprint", []):
            if _poly_circle(fp["poly"], pos, reach + 1.0): return "canopy reaches footbridge %s" % o.name
    for c, r, ow in ctx["occ"].canopy:
        if (Vector((c.x, c.y)) - Vector((pos.x, pos.y))).length < (r + reach) * 0.55: return "too close to %s (canopies)" % ow
    return None


def _mulch(ctx, owner, pos, r):
    """Low domed mulch ring around a trunk in a planting strip (edges flush with the strip: nothing floats)."""
    bm = bmesh.new(); n = 14
    c = bm.verts.new(pos + Vector((0, 0, 0.035)))
    ring1 = [bm.verts.new(pos + Vector((math.cos(2 * math.pi * k / n) * r * 0.55, math.sin(2 * math.pi * k / n) * r * 0.55, 0.03))) for k in range(n)]
    ring2 = [bm.verts.new(pos + Vector((math.cos(2 * math.pi * k / n) * r, math.sin(2 * math.pi * k / n) * r, -0.01))) for k in range(n)]
    for k in range(n):
        bm.faces.new((c, ring1[k], ring1[(k + 1) % n]))
        bm.faces.new((ring1[k], ring2[k], ring2[(k + 1) % n], ring1[(k + 1) % n]))
    me = bpy.data.meshes.new("MRS_PL_mulch"); bm.to_mesh(me); bm.free()
    me.materials.append(_mulch_material())
    o = bpy.data.objects.new(owner + "_mulch", me); ctx["col"].objects.link(o); o["mrs_placed"] = "mulch"; o["mrs_kind"] = "mulch"


def _mulch_material():
    from .props import mat
    m = bpy.data.materials.get(MRS + "Mulch")
    if m is None:
        m = mat(MRS + "Mulch", (0.16, 0.10, 0.06), 0.95)
        nt = m.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40.0; nz.inputs["Detail"].default_value = 6.0
        rp = nt.nodes.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].color = (0.07, 0.045, 0.03, 1); rp.color_ramp.elements[1].color = (0.26, 0.17, 0.10, 1)
        nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
        bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs[0], b.inputs["Normal"])
    return m


# ============================================================================ 4b. landscape regions
# (the yard kit's clipped hedge / boxwood read near-black / grey under the shared foliage shader in a street
#  view, so park edges use an informal line of shrub_b and the low layer uses shrub_c)
PLANT_LAYERS = {"grass": ["grass_a", "grass_b"], "low": ["shrub_c"], "shrub": ["shrub_a", "shrub_b"], "hedge": ["shrub_b"]}


def _landscape(ctx, m):
    """Landscape regions of this road: the planting strips (grass layer + low shrub clusters between the
    trees) and the park edge behind each sidewalk (`landscape_depth` m: hedge line with gaps at paths,
    shrub groups, grass), excluding crossings, pads, bus boarding, footbridge paths / approaches,
    entrances and sight triangles (low plants only there). Points are written to one scatter object per
    region with the `Landscape_Scatter` node group (instances from MRS_GamePlants)."""
    R = RULES; rng = random.Random(zlib.crc32(("%s|%s" % (ctx["seed"], m.name)).encode()))
    plants = sorted(o.name for o in (bpy.data.collections.get(MRS + "GamePlants").objects if bpy.data.collections.get(MRS + "GamePlants") else []))
    if not plants: _skip(ctx, m, "landscape", m.A0, "MRS_GamePlants missing (game_trees.build_game_trees)"); return
    idx = {n[len(MRS + "GPlant_"):]: i for i, n in enumerate(plants)}
    occ = ctx["occ"]
    def free_for(p, r, tall):
        P = Vector((p.x, p.y))
        probe = Rect(p, Vector((1, 0, 0)), r + 0.2, r + 0.2)
        for e in occ.near(probe):
            if e["t"] == "keep":
                b = e["blocks"]
                if (e["why"].startswith("walking corridor") or "*" in b or "plant" in b or (tall and "tall" in b)) and e["r"].circle(p, r): return False
            elif e["t"] == "solid":
                if e["r"].circle(p, r + 0.15): return False
            elif e["r"].circle(p, r): return False
        for c, cr, o in occ.canopy:
            if (Vector((c.x, c.y)) - P).length < 0.55 + r: return False      # keep the trunk base / mulch clear
        return True
    for s in ("l", "r"):
        z = m.zones(s)
        if z is None: continue
        pts = []
        # --- planting strip
        if z["strip"] >= 0.6:
            a = m.A0 + 0.5
            while a < m.A1 - 0.5:
                dens = R["grass_density"] * (0.55 + 0.9 * (0.5 + 0.5 * math.sin(a * 0.21 + rng.random())))
                n_ = int(dens * z["strip"] * 1.0 + rng.random())
                for _ in range(n_):
                    aa = a + rng.uniform(-0.5, 0.5); dd = rng.uniform(0.15, z["strip"] - 0.15)
                    p, t, n = m.point(aa, s, dd)
                    if free_for(p, 0.25, False): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["grass"]), 0), rng.uniform(0.7, 1.1), "grass", rng.uniform(0, math.tau)))
                a += 1.0
            # low shrub clusters midway between trees, never in sight triangles (tall check)
            a = m.A0 + R["shrub_cluster_spacing"] * 0.5
            while a < m.A1 - 1.0:
                if z["strip"] >= 0.9 and rng.random() < 0.7:
                    for j in range(rng.randint(2, 4)):
                        p, t, n = m.point(a + j * 0.8 + rng.uniform(-0.2, 0.2), s, z["strip"] / 2 + rng.uniform(-0.12, 0.12))
                        if free_for(p, 0.45, True): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["low"]), 0), rng.uniform(0.75, 1.0), "low", rng.uniform(0, math.tau)))
                a += R["shrub_cluster_spacing"]
        # --- region behind the sidewalk: "park" (hedge line with gaps, shrub groups, grass), "verge" (grass, a few shrubs), "none"
        style = R["landscape"].get("%s:%s" % (m.name, s), R["default_landscape"])
        D = R["landscape_depth"] if style != "none" else 0.0
        if D > 0.5 and style == "verge":
            a = m.A0 + 4.0
            while a < m.A1 - 4.0:
                if rng.random() < 0.45:
                    p, t, n = m.point(a + rng.uniform(-2, 2), s, z["sw"] + rng.uniform(1.8, D - 1.0)); p.z = R["ground_z"]
                    if free_for(p, 1.0, True): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["shrub"]), 0), rng.uniform(0.7, 1.0), "shrub", rng.uniform(0, math.tau)))
                for j in range(int(3 + rng.random() * 4)):
                    p, t, n = m.point(a + rng.uniform(-3, 3), s, z["sw"] + rng.uniform(0.4, D)); p.z = R["ground_z"]
                    if free_for(p, 0.3, False): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["grass"]), 0), rng.uniform(0.8, 1.2), "grass", rng.uniform(0, math.tau)))
                a += rng.uniform(6.0, 10.0)
        if D > 0.5 and style == "park":
            a = m.A0 + 2.0; hedge_run = 0
            while a < m.A1 - 2.0:
                p, t, n = m.point(a, s, z["sw"] + 1.0)
                p.z = R["ground_z"]
                if free_for(p, 1.1, True):
                    pts.append((p, idx.get(PLANT_LAYERS["hedge"][0], 0), rng.uniform(0.85, 1.0), "hedge", rng.uniform(0, math.tau))); hedge_run += 1
                else: hedge_run = 0
                a += 2.35
            a = m.A0 + 4.0
            while a < m.A1 - 4.0:
                for j in range(rng.randint(1, 3)):
                    p, t, n = m.point(a + rng.uniform(-2, 2), s, z["sw"] + rng.uniform(2.8, D - 0.8)); p.z = R["ground_z"]
                    if free_for(p, 1.0, True): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["shrub"]), 0), rng.uniform(0.8, 1.15), "shrub", rng.uniform(0, math.tau)))
                for j in range(int(6 + rng.random() * 6)):
                    p, t, n = m.point(a + rng.uniform(-3, 3), s, z["sw"] + rng.uniform(2.2, D)); p.z = R["ground_z"]
                    if free_for(p, 0.3, False): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["grass"]), 0), rng.uniform(0.8, 1.2), "grass", rng.uniform(0, math.tau)))
                a += rng.uniform(5.0, 8.0)
        if not pts: continue
        name = "%s_landscape_%s" % (m.name, s)
        me = bpy.data.meshes.new("MRS_PL_" + name); me.from_pydata([tuple(p[0]) for p in pts], [], [])
        for k, vals in (("plant", [float(p[1]) for p in pts]), ("scale", [p[2] for p in pts]), ("yaw", [p[4] for p in pts])):
            at = me.attributes.new(k, "FLOAT", "POINT"); at.data.foreach_set("value", vals)
        o = bpy.data.objects.new(name, me); ctx["col"].objects.link(o); o["mrs_placed"] = "landscape"; o["mrs_kind"] = "landscape"
        mod = o.modifiers.new("Landscape_Scatter", "NODES"); mod.node_group = ensure_scatter_group()
        layers = {}
        for p in pts: layers[p[3]] = layers.get(p[3], 0) + 1
        ctx["rep"]["regions"].append({"name": name, "road": m.name, "side": s, "count": len(pts), "layers": layers, "plants": plants})
        ctx["rep"]["placed"].append((m.name, "landscape", s, 0.0, name))


def ensure_scatter_group():
    from .nodes import T, new_tree, sock
    g = bpy.data.node_groups.get("Landscape_Scatter")
    if g is not None and len(g.nodes) > 3: return g
    g = new_tree("Landscape_Scatter")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry"); sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    sock(g, "Realize", "INPUT", "NodeSocketBool", False, desc="realize instances (export)")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    ci = tb.n("GeometryNodeCollectionInfo", transform_space="ORIGINAL"); ci.inputs["Collection"].default_value = bpy.data.collections.get(MRS + "GamePlants")
    tb.inp(ci, "Separate Children", True); tb.inp(ci, "Reset Children", True)
    iop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(iop, "Points", gi.outputs["Geometry"]); tb.inp(iop, "Instance", ci.outputs[0])
    tb.inp(iop, "Pick Instance", True); tb.inp(iop, "Instance Index", tb.named("plant")); tb.inp(iop, "Scale", tb.named("scale"))
    eul = tb.combine(0.0, 0.0, tb.named("yaw"))
    er = tb.n("FunctionNodeEulerToRotation"); tb.inp(er, "Euler", eul); tb.inp(iop, "Rotation", er.outputs[0])
    rz = tb.n("GeometryNodeRealizeInstances"); tb.inp(rz, "Geometry", iop.outputs[0])
    out = tb.switch(gi.outputs["Realize"], iop.outputs[0], rz.outputs[0], "GEOMETRY")
    tb.link(out, go.inputs[0])
    return g


# ============================================================================ paths, entrances, parks
def _path_mesh(col, name, pts, width, z_top, z_ground, material, ped=True, ramp_len=3.0):
    """A paved path ribbon along `pts` (world XY) with a skirt down to `z_ground`; the first `ramp_len` m
    descend from z_top (back of the sidewalk) to z_ground + 0.03 so it meets both without steps."""
    P = [Vector((p[0], p[1], 0.0)) for p in pts]
    acc = [0.0]
    for a, b in zip(P, P[1:]): acc.append(acc[-1] + (b - a).length)
    def zf(s): return z_top + (z_ground + 0.03 - z_top) * min(1.0, s / max(ramp_len, 0.01))
    bm = bmesh.new(); top_l = []; top_r = []
    for i, p in enumerate(P):
        d = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]); d.z = 0; d.normalize()
        sd = Vector((d.y, -d.x, 0.0)) * width / 2
        z = zf(acc[i])
        top_l.append(bm.verts.new(p - sd + Vector((0, 0, z)))); top_r.append(bm.verts.new(p + sd + Vector((0, 0, z))))
    bot_l = [bm.verts.new((v.co.x, v.co.y, z_ground - 0.15)) for v in top_l]; bot_r = [bm.verts.new((v.co.x, v.co.y, z_ground - 0.15)) for v in top_r]
    for i in range(len(P) - 1):
        bm.faces.new((top_l[i], top_r[i], top_r[i + 1], top_l[i + 1]))
        bm.faces.new((bot_l[i], top_l[i], top_l[i + 1], bot_l[i + 1]))
        bm.faces.new((top_r[i], bot_r[i], bot_r[i + 1], top_r[i + 1]))
    me = bpy.data.meshes.new("MRS_PL_" + name); bm.to_mesh(me); bm.free()
    uv = me.uv_layers.new(name="UVMap")
    for li, l in enumerate(me.loops):
        co = me.vertices[l.vertex_index].co; uv.data[li].uv = (co.x, co.y)
    if material: me.materials.append(material)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o["mrs_placed"] = "path"; o["mrs_kind"] = "path"
    if ped:
        o["mrs_ped_path"] = json.dumps([[round(p.x, 3), round(p.y, 3), round(zf(s), 3)] for p, s in zip(P, acc)]); o["mrs_path_width"] = width
    return o


def entrance_paths(roads_col, rep):
    """Paved access paths from the back of the sidewalk to every MRS_Entrance_* anchor (already reserved)."""
    if not RULES.get("entrance_paths", True): return []
    col = bpy.data.collections[roads_col.name + "_Placed"]; out = []
    models = rep.get("_ctx_models", {})
    for o in bpy.data.objects:
        if o.type != "EMPTY" or not o.name.startswith("MRS_Entrance"): continue
        m = models.get(o.get("mrs_road", ""))
        if m is None: continue
        s = o.get("mrs_side", "r"); a = _project(m, o.location); z = m.zones(s)
        if o.get("mrs_on_sidewalk"): continue
        q, t, n = m.point(a, s, z["sw"] - 0.05)
        out.append(_path_mesh(col, "%s_path" % o.name, [q, o.location], 2.4, q.z, o.location.z - 0.03, bpy.data.materials.get(MRS + "Paving"), ped=False, ramp_len=0.01))
    return out


def place_park(roads_col, rep, name, poly, paths=(), seed=0, tree_spacing=11.0, pool=None, path_width=2.5):
    """Plant a park region (convex or simple polygon in world XY): paved paths (route-connected), Poisson-
    spaced park trees kept clear of reserved areas and footbridges, shrub groups and grass by layered density.
    Uses the occupancy of the preceding place_all() (rep["_occ"]), so nothing overlaps what is already there."""
    occ = rep["_occ"]; col = bpy.data.collections[roads_col.name + "_Placed"]
    rng = random.Random(zlib.crc32(("%s|%s" % (seed, name)).encode()))
    pool = pool or STYLE_TREES["park"]
    R = RULES; gz = R["ground_z"]
    poly2 = [Vector((p[0], p[1])) for p in poly]
    def inside(p):
        x, y = p.x, p.y; c = False; n = len(poly2)
        for i in range(n):
            a, b = poly2[i], poly2[(i + 1) % n]
            if (a.y > y) != (b.y > y) and x < (b.x - a.x) * (y - a.y) / (b.y - a.y + 1e-12) + a.x: c = not c
        return c
    out = {"name": name, "paths": [], "trees": 0, "plants": 0}
    for i, pp in enumerate(paths):
        z0 = pp.get("z_top", gz + 0.03)
        o = _path_mesh(col, "%s_path%d" % (name, i), pp["pts"], path_width, z0, gz, bpy.data.materials.get(MRS + "Paving"), ped=True, ramp_len=pp.get("ramp", 3.0))
        out["paths"].append(o.name)
        if pp.get("dest"): o["mrs_path_dest"] = pp["dest"]
        P = [Vector((q[0], q[1], 0)) for q in pp["pts"]]
        for a_, b_ in zip(P, P[1:]):
            d = b_ - a_
            if d.length > 0.05: occ.add_keep(Rect((a_ + b_) / 2, d, d.length / 2 + 0.6, path_width / 2 + 0.6), "park path %s" % name, {"*"})
    xs = [p.x for p in poly2]; ys = [p.y for p in poly2]
    # trees: dart throwing with a minimum spacing
    trees = []
    for _ in range(600):
        p = Vector((rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)), gz))
        if not inside(p) or any((p - q).length < tree_spacing for q in trees): continue
        sid = pool[len(trees) % len(pool)]
        src, info = _tree_lib(sid)
        if src is None: continue
        sc = rng.uniform(0.85, 1.05); reach = info["reach"] * sc
        foot = Rect(p, Vector((1, 0, 0)), 0.4, 0.4)
        if occ.blocked(foot, [], "tree", "park", "tree", info["height"] * sc): continue
        if any(_poly_circle(fp["poly"], p, reach + 1.0) for o_, plan in _footbridges(roads_col) for fp in plan.get("footprint", [])): continue
        if any((Vector((c.x, c.y)) - p.to_2d()).length < (cr + reach) * 0.5 for c, cr, ow in occ.canopy): continue
        if any(e["t"] == "keep" and e["r"].circle(p, reach * 0.6) for e in occ.near(Rect(p, Vector((1, 0, 0)), reach, reach)) if e.get("why", "").startswith(("walking corridor", "junction sightline", "footbridge", "park path"))): continue
        owner = "%s_tree%d" % (name, len(trees))
        o = _place(src, owner, p, rng.uniform(0, math.tau), col, sc, "tree", {"mrs_species": sid, "mrs_region": name})
        occ.add(foot, [], owner, "tree"); occ.canopy.append((p, reach, owner)); trees.append(p)
        rep["placed"].append((name, "tree", "park", 0.0, src.name))
        rep["items"].append({"name": owner, "kind": "tree", "lib": src.name, "species": sid, "road": name, "side": "park", "along": 0.0,
                             "pos": [round(c, 3) for c in p], "yaw": round(o.rotation_euler.z, 4), "scale": round(sc, 3), "flush": False,
                             "foot": [[round(c.x, 3), round(c.y, 3)] for c in foot.corners()], "crown": round(reach, 2)})
    out["trees"] = len(trees)
    # shrubs and grass: clusters around tree bases and path edges, sparse meadow tufts elsewhere
    plants = sorted(o.name for o in bpy.data.collections[MRS + "GamePlants"].objects)
    idx = {n[len(MRS + "GPlant_"):]: i for i, n in enumerate(plants)}
    pts = []
    def free(p, r):
        probe = Rect(p, Vector((1, 0, 0)), r + 0.2, r + 0.2)
        for e in occ.near(probe):
            if e["t"] == "keep" and e["r"].circle(p, r): return False
            if e["t"] == "solid" and e["r"].circle(p, r + 0.3): return False
        return inside(p)
    for t in trees:
        for j in range(rng.randint(1, 3)):
            a = rng.uniform(0, math.tau); r = rng.uniform(2.0, 4.0)
            p = Vector((t.x + math.cos(a) * r, t.y + math.sin(a) * r, gz))
            if free(p, 0.9): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["shrub"] + PLANT_LAYERS["low"]), 0), rng.uniform(0.8, 1.15), "shrub", rng.uniform(0, math.tau)))
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    for _ in range(int(area * 0.08)):
        p = Vector((rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)), gz))
        # meadow tufts gather in patches (low-frequency density)
        dens = 0.5 + 0.5 * math.sin(p.x * 0.11) * math.cos(p.y * 0.13)
        if rng.random() > 0.25 + 0.75 * dens: continue
        if free(p, 0.3): pts.append((p, idx.get(rng.choice(PLANT_LAYERS["grass"]), 0), rng.uniform(0.8, 1.25), "grass", rng.uniform(0, math.tau)))
    if pts:
        me = bpy.data.meshes.new("MRS_PL_" + name + "_planting"); me.from_pydata([tuple(p[0]) for p in pts], [], [])
        for k, vals in (("plant", [float(p[1]) for p in pts]), ("scale", [p[2] for p in pts]), ("yaw", [p[4] for p in pts])):
            at = me.attributes.new(k, "FLOAT", "POINT"); at.data.foreach_set("value", vals)
        o = bpy.data.objects.new(name + "_planting", me); col.objects.link(o); o["mrs_placed"] = "landscape"; o["mrs_kind"] = "landscape"
        mod = o.modifiers.new("Landscape_Scatter", "NODES"); mod.node_group = ensure_scatter_group()
        layers = {}
        for p in pts: layers[p[3]] = layers.get(p[3], 0) + 1
        rep["regions"].append({"name": o.name, "road": name, "side": "park", "count": len(pts), "layers": layers, "plants": plants})
    out["plants"] = len(pts)
    rep.setdefault("parks", []).append(out)
    return out
