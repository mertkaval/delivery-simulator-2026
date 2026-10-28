"""Rule-based placement of signs, streetlights, furniture and trees along roads (Python, deterministic).

Placement priority (documented rule set, see docs/roads/PLACEMENT_RULES.md):
 1. Reserved zones are computed per road side from the street model: junction clear zones (trim ..
    trim + stop setback + crossing + 5 m), crossing ramps, bus stops, driveways/overrides, cycleway width
    (nothing stands in a cycleway) and the minimum unobstructed walking width.
 2. Signals come from the junction builder (not here). 3. Signs by explicit conditions. 4. Streetlights
    at a spacing, alternating sides. 5. Furniture (benches, bins, racks) in the furniture strip at a
    spacing, only where the sidewalk is wide enough. 6. Trees in planting strips / tree pits at a spacing
    with canopy clearance. Each candidate is tested against the reserved zones and already placed items;
    skipped items are reported with the reason.

Everything placed goes into `<roads collection>_Placed` as linked duplicates of library objects with
stable names `<road>_<kind>_<index>`; re-running removes the previous set first (no multiplying).
"""
import bpy, math, random
from mathutils import Vector
from .nodes import MRS
from .roads import all_roads, road_widths, road_input
from .structures import road_sample, road_length

RULES = {
    "sidewalk_min_walk": 1.5,       # m of unobstructed paving kept free (furniture goes in the strip beyond it)
    "light_spacing": 28.0, "light_setback": 0.45, "light_min_gap": 6.0,
    "furniture_spacing": 22.0, "furniture_min_sidewalk": 3.0,
    "tree_spacing": 11.0, "tree_min_strip": 0.9, "tree_canopy_clear": 2.5, "tree_junction_sightline": 15.0,
    "sign_setback": 0.5, "sign_min_gap": 4.0,
    "speed_sign_from_start": 12.0,
}
SPECIES_BY_STYLE = {"avenue": ("MRS_Tree_Oak", "MRS_Tree_Maple"), "residential": ("MRS_Tree_Birch", "MRS_Tree_Maple"), "boulevard": ("MRS_Tree_Poplar",), "coastal": ("MRS_Tree_Palm",),
                    "park": ("MRS_Tree_Oak", "MRS_Tree_Pine")}


class Zones:
    """Reserved along-intervals per road side."""
    def __init__(self): self.z = {"l": [], "r": []}
    def add(self, side, a0, a1, why):
        for s in (("l", "r") if side == "both" else (side,)): self.z[s].append((min(a0, a1), max(a0, a1), why))
    def blocked(self, side, a, half=0.0):
        for a0, a1, why in self.z[side]:
            if a + half >= a0 and a - half <= a1: return why
        return None


def _junction_meta_for(road):
    out = {}
    for o in bpy.data.objects:
        m = o.get("mrs_junction")
        if not m or road.name not in list(m.get("roads", [])): continue
        for ap in m.get("approaches", []):
            if ap["road"] == road.name: out[ap["end"]] = dict(ap, junction=o.name, control=m.get("control", "none"), crossing=bool(m.get("crosswalks", True)), main=ap.get("main", False))
    return out


def reserved_zones(road, L, ends):
    z = Zones()
    r = RULES
    w = road_widths(road)
    for end, ap in ends.items():
        a_end = 0.0 if end == "start" else L
        span = 2.5 + 0.6 + 5.0 if ap.get("crossing") else 3.0
        z.add("both", a_end, a_end + span if end == "start" else a_end - span, "junction / crossing zone (%s)" % ap["junction"])
        sight = r["tree_junction_sightline"]
        z.add("both", a_end, a_end + sight if end == "start" else a_end - sight, "junction sightline")
    # structures placed on this road (bus stops, gantries)
    for o in bpy.data.objects:
        if o.name.startswith(road.name + "_busstop"):
            p = o.location; a = _along_of(road, p)
            if a is not None: z.add("both", a - 10.0, a + 10.0, "bus stop")
    # manual exclusion overrides: empties named MRS_Exclude_* near the road
    for o in bpy.data.objects:
        if o.type == "EMPTY" and o.name.startswith("MRS_Exclude"):
            a = _along_of(road, o.location, max_dist=max(w["half"] + 6.0, 8.0))
            if a is not None:
                half = max(o.empty_display_size, 1.0)
                z.add("both", a - half, a + half, "manual exclusion " + o.name)
    return z


_samples_cache = {}


def _centre_samples(road, step=2.0):
    key = (road.name, round(road_length(road), 1))
    if key not in _samples_cache:
        L = key[1]; pts = []
        a = 0.0
        while a <= L:
            p, t, r = road_sample(road, a); pts.append((a, p, t, r)); a += step
        _samples_cache[key] = pts
    return _samples_cache[key]


def _along_of(road, world_pos, max_dist=30.0):
    best = None
    for a, p, t, r in _centre_samples(road):
        d = (Vector((world_pos.x, world_pos.y, 0)) - Vector((p.x, p.y, 0))).length
        if d <= max_dist and (best is None or d < best[0]): best = (d, a)
    return best[1] if best else None


def _side_point(road, a, side, offset):
    """World position on `side` ('l'/'r') at `offset` m from the asphalt edge, on the sidewalk height."""
    p, t, r = road_sample(road, a)
    w = road_widths(road)
    sgn = 1.0 if side == "r" else -1.0
    half = w["half_r"] if side == "r" else w["half_l"]
    lat = half + w["curb"] + offset
    return p + r * sgn * lat + Vector((0, 0, w["h"])), t, r, sgn


def _place(lib_name, name, pos, yaw, col, scale=1.0):
    src = bpy.data.objects.get(lib_name)
    if src is None: return None
    o = bpy.data.objects.new(name, src.data); col.objects.link(o)
    o.location = pos; o.rotation_euler = (0, 0, yaw); o.scale = (scale, scale, scale)
    o["mrs_placed"] = lib_name
    for ch in src.children:                       # signal heads / sign text children
        c2 = bpy.data.objects.new(name + ch.name[len(src.name):], ch.data); col.objects.link(c2)
        c2.parent = o; c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy(); c2.location = ch.location; c2.rotation_euler = ch.rotation_euler; c2.scale = ch.scale
    return o


def clear_placed(roads_col):
    col = bpy.data.collections.get(roads_col.name + "_Placed")
    if col:
        for o in list(col.objects): bpy.data.objects.remove(o)
    else:
        col = bpy.data.collections.new(roads_col.name + "_Placed"); roads_col.children.link(col)
    return col


def place_all(roads_col, seed=0, style="avenue", speed_limits=None, log=None):
    """Run the whole placement for every road in the collection. Returns a report dict."""
    rng = random.Random(seed)
    col = clear_placed(roads_col)
    report = {"placed": [], "skipped": []}
    speed_limits = speed_limits or {}
    try:
        from . import signage
    except ImportError:
        signage = None
    for road in all_roads(roads_col):
        L = road_length(road)
        if L < 4.0: continue
        ends = _junction_meta_for(road)
        zones = reserved_zones(road, L, ends)
        w = road_widths(road)
        rht = w["rht"]
        placed_along = {"l": [], "r": []}
        def free(side, a, kind, half=0.0, min_gap=2.0):
            why = zones.blocked(side, a, half)
            if why: return "reserved: " + why
            for a2, k2 in placed_along[side]:
                if abs(a2 - a) < min_gap: return "too close to %s" % k2
            return None
        def put(side, a, lib, kind, offset, face_road=True, yaw_extra=0.0, scale=1.0, min_gap=2.0, min_sidewalk=0.0, facing=None):
            """facing: 'traffic' (sign front toward the cars driving on this side), 'road' (prop front toward the
            road), 'along' (aligned with the road). Signs default to 'traffic', everything else to 'road'."""
            if facing is None: facing = "traffic" if kind.startswith("sign") else ("road" if face_road else "along")
            sw = w["swr"] if side == "r" else w["swl"]
            if sw <= 0.05: report["skipped"].append((road.name, kind, round(a, 1), "no sidewalk on side " + side)); return None
            if sw < min_sidewalk: report["skipped"].append((road.name, kind, round(a, 1), "sidewalk %.1f m < %.1f m" % (sw, min_sidewalk))); return None
            why = free(side, a, kind, min_gap=min_gap)
            if why: report["skipped"].append((road.name, kind, round(a, 1), why)); return None
            pos, t, r, sgn = _side_point(road, a, side, offset)
            travel = 1.0 if ((side == "r") == rht) else -1.0            # direction of the traffic on this side (+1 = with the curve)
            if facing == "traffic": f = -t * travel                     # the plate's +Y looks back at the arriving cars
            elif facing == "road": f = -r * sgn                         # +Y toward the carriageway
            else: f = t
            yaw = math.atan2(f.y, f.x) - math.pi / 2 + yaw_extra        # local +Y -> f
            o = _place(lib, "%s_%s_%s%d" % (road.name, kind, side, len(placed_along[side])), pos, yaw, col, scale)
            if o is None: report["skipped"].append((road.name, kind, round(a, 1), "library object missing: " + lib)); return None
            placed_along[side].append((a, kind)); report["placed"].append((road.name, kind, side, round(a, 1), lib))
            return o
        # ---- signs by condition
        # traffic arriving at an end drives on the right side (RHT) toward that end: 'r' side arrives at the END, 'l' at the START
        for end, ap in ends.items():
            arriving_side = ("r" if rht else "l") if end == "end" else ("l" if rht else "r")
            a_sign = (L - ap["trim"] - 2.5 - 0.6 - 3.0) if end == "end" else (ap["trim"] + 2.5 + 0.6 + 3.0)
            a_sign = min(max(a_sign, 1.0), L - 1.0)
            lanes_in = ap["lanes_in"]
            if lanes_in <= 0:
                # one-way against this approach: NO ENTRY facing the junction
                put(arriving_side, a_sign, "MRS_Sign_NoEntry", "sign_no_entry", RULES["sign_setback"], yaw_extra=0.0)
                continue
            ctrl = ap.get("control", "none")
            if ctrl == "stop" or (ctrl == "priority" and not ap.get("main")):
                put(arriving_side, a_sign, "MRS_Sign_Stop" if ctrl == "stop" else "MRS_Sign_Yield", "sign_" + ("stop" if ctrl == "stop" else "yield"), RULES["sign_setback"])
            elif ctrl == "priority" and ap.get("main"):
                put(arriving_side, a_sign, "MRS_Sign_PriorityRoad", "sign_priority", RULES["sign_setback"])
            if ap.get("crossing"):
                put(arriving_side, a_sign + (-6.0 if end == "end" else 6.0), "MRS_Sign_PedestrianCrossing", "sign_crossing", RULES["sign_setback"])
            # street-name blades: one double blade per junction corner, placed once per junction (first road that reaches it)
            jn = ap.get("junction")
            if jn and not any(o.name.startswith(jn + "_streetname") for o in bpy.data.objects):
                names = [bpy.data.objects[rn].get("mrs_street_name", rn) for rn in bpy.data.objects[jn]["mrs_junction"]["roads"] if rn in bpy.data.objects]
                if signage is not None and len(names) >= 2:
                    try:
                        sgn_obj = signage.make_sign(jn + "_streetname", "street_name", text=names[0][:14] + "|" + names[1][:14], double=True, collection=col)
                        pos, t, r, sg = _side_point(road, a_sign + (-2.0 if end == "end" else 2.0), arriving_side, RULES["sign_setback"] + 0.4)
                        sgn_obj.location = pos; sgn_obj.rotation_euler = (0, 0, math.atan2(t.y, t.x))
                        report["placed"].append((road.name, "sign_street_name", arriving_side, round(a_sign, 1), "street_name"))
                    except Exception as e:
                        report["skipped"].append((road.name, "sign_street_name", round(a_sign, 1), "signage error: %s" % e))
        # speed limit after the start of the road for each driving direction
        sp = speed_limits.get(road.name)
        if sp:
            for side, a in (("r" if rht else "l", RULES["speed_sign_from_start"]), ("l" if rht else "r", L - RULES["speed_sign_from_start"])):
                put(side, a, "MRS_Sign_Speed%d" % sp if bpy.data.objects.get("MRS_Sign_Speed%d" % sp) else "MRS_Sign_Speed50", "sign_speed", RULES["sign_setback"])
        # one-way roads: ONE WAY sign at the entry
        if w["lanes_b"] == 0 or w["lanes_f"] == 0:
            side = "r" if rht else "l"
            put(side, 8.0 if w["lanes_f"] > 0 else L - 8.0, "MRS_Sign_OneWay", "sign_one_way", RULES["sign_setback"])
        # bicycle route signs where a cycleway starts
        for side in ("l", "r"):
            if w.get("bike_on_" + side):
                put(side, 10.0 if (side == "r") == rht else L - 10.0, "MRS_Sign_BicycleRoute", "sign_bicycle", RULES["sign_setback"])
        # ---- streetlights (alternate sides)
        a = RULES["light_spacing"] * 0.5; k = 0
        lib_light = "MRS_Light_LED" if w["half"] < 6 else "MRS_Light_Highway"
        while a < L:
            side = "r" if k % 2 == 0 else "l"
            put(side, a, lib_light if bpy.data.objects.get(lib_light) else "MRS_Streetlight", "light", RULES["light_setback"], min_gap=RULES["light_min_gap"])
            a += RULES["light_spacing"]; k += 1
        # ---- furniture in the strip beyond the walking width
        a = RULES["furniture_spacing"] * 0.6
        furn = ["MRS_Bench_Wood", "MRS_Bin_Round", "MRS_BikeRack", "MRS_Bench_Modern", "MRS_Bin_Square"]
        while a < L:
            for side in ("l", "r"):
                sw = w["swr"] if side == "r" else w["swl"]
                lib = furn[rng.randrange(len(furn))]
                if sw >= RULES["furniture_min_sidewalk"]:
                    off = max(RULES["light_setback"] + 0.3, sw - RULES["sidewalk_min_walk"] - 0.4)
                    put(side, a + rng.uniform(-2.0, 2.0), lib, "furniture", min(off, sw - 0.5), min_gap=3.0, min_sidewalk=RULES["furniture_min_sidewalk"])
                else:
                    report["skipped"].append((road.name, "furniture", round(a, 1), "sidewalk %.1f m < %.1f m" % (sw, RULES["furniture_min_sidewalk"])))
            a += RULES["furniture_spacing"]
        # ---- trees in planting strips (or beyond a wide sidewalk), species by street style, deterministic
        species = SPECIES_BY_STYLE.get(style, SPECIES_BY_STYLE["avenue"])
        for side in ("l", "r"):
            strip = road_input(road, "Planting Strip Right" if side == "r" else "Planting Strip Left") or 0.0
            sw = w["swr"] if side == "r" else w["swl"]
            if strip < RULES["tree_min_strip"]:
                report["skipped"].append((road.name, "tree", 0.0, "planting strip %.1f m < %.1f m on side %s" % (strip, RULES["tree_min_strip"], side))); continue
            a = RULES["tree_spacing"] * 0.5; k = 0
            while a < L:
                sp_name = species[(k + (0 if side == "r" else 1)) % len(species)] + ("_A" if (k // 2) % 2 == 0 else "_B")
                if free(side, a, "tree", min_gap=RULES["tree_canopy_clear"]) is None:
                    pos, t, r, sgn = _side_point(road, a, side, strip * 0.5)
                    pos.z -= w["h"] * 0.0
                    o = _place(sp_name if bpy.data.objects.get(sp_name) else "MRS_Tree_Oak_A", "%s_tree_%s%d" % (road.name, side, k), pos, rng.uniform(0, 6.283), col, 0.9 + 0.2 * rng.random())
                    if o: placed_along[side].append((a, "tree")); report["placed"].append((road.name, "tree", side, round(a, 1), sp_name))
                else:
                    report["skipped"].append((road.name, "tree", round(a, 1), free(side, a, "tree", min_gap=RULES["tree_canopy_clear"])))
                a += RULES["tree_spacing"]; k += 1
    report["counts"] = {"placed": len(report["placed"]), "skipped": len(report["skipped"])}
    by_kind = {}
    for _, kind, *_r in report["placed"]: by_kind[kind] = by_kind.get(kind, 0) + 1
    report["by_kind"] = by_kind
    return report
