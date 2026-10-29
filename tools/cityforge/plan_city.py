"""CityForge planner: terrain + city spec -> the whole city as data (city.json).

    python tools/cityforge/plan_city.py <city_spec.json> <terrain_dir> <out_dir>

Reads the terrain (tools/terrain/city_terrain.py: terrain.npz, meta.json) and a city spec, and
plans, deterministically:
  roads      main grid (avenues E-W, streets N-S, arterials), the rotated downtown grid, the
             downtown boundary boulevard, a diagonal arterial; cut at water (arterials bridge short
             spans) and on slopes too steep for local streets; split into a node/edge graph
  zoning     downtown, commercial strips along arterials, residential, industrial, parks (named
             parks, steep / high ground, a neighbourhood park every N blocks), public buildings
  lots       Burnaby-style 15 m lots off the avenues with a back lane, a house and (often) a
             detached garage on the lane, fences / hedges / walls round each lot
  buildings  houses (archetype + colours), shop rows, downtown podium towers, warehouses, public
  furniture  street lamps, traffic lights, stop signs, bus stops, boulevard trees, hydrants, benches
  names      street, avenue and neighbourhood names; addresses for every lot
  grading    the ground levelled under roads (smooth profiles) and lot pads -> graded height
Every item has a stable id; tools/cityforge/overrides.json (optional, next to the spec) changes any
single item by id ({"house_0123": {"archetype": "bungalow", "fence": "hedge"}, "tree_0042": {"remove": true}})
and survives regeneration. Outputs: city.json, graded.npz, heights.f32 (Godot), plan.png (preview).
"""
import json, math, os, sys, hashlib
import numpy as np

spec_path, terrain_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out_dir, exist_ok=True)
SPEC = json.load(open(spec_path, encoding="utf-8"))
META = json.load(open(os.path.join(terrain_dir, "meta.json")))
T = np.load(os.path.join(terrain_dir, "terrain.npz"))
H0 = T["height"].astype(np.float64)
WATER = T["water"]
SLOPE = T["slope"]
SIZE, CELL, N = META["size_m"], META["cell_m"], META["grid"]
W = SPEC["widths"]
OVR_PATH = os.path.join(os.path.dirname(os.path.abspath(spec_path)), "overrides.json")
OVR = json.load(open(OVR_PATH, encoding="utf-8")) if os.path.exists(OVR_PATH) else {}
SPEC_DIR = os.path.dirname(os.path.abspath(spec_path))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from street_names import StreetNamer
CAT_PATH = os.path.join(SPEC_DIR, SPEC.get("house_catalogue", "../../assets/cityforge/houses.json"))
CATALOGUE = json.load(open(CAT_PATH, encoding="utf-8")) if os.path.exists(CAT_PATH) else []
CULTURES = SPEC["cultures"]
TINTABLE = ("CF_Stucco", "CF_Siding", "CF_BrickPainted", "CF_Plaster")


def yaw_of(f):
    """Yaw (about +Z, counter-clockwise) that turns a model's +Y front towards direction f."""
    return math.atan2(-f[0], f[1])


def rnd(key, k=0):
    """Deterministic 0..1 from a key (stable across runs and machines)."""
    h = hashlib.md5(("%s|%s|%d" % (SPEC.get("seed", 0), key, k)).encode()).digest()
    return int.from_bytes(h[:4], "little") / 4294967296.0


def cell(x, y):
    return int(np.clip(round(y / CELL), 0, N - 1)), int(np.clip(round(x / CELL), 0, N - 1))


def h_at(x, y, arr=None):
    a = H0 if arr is None else arr
    fx, fy = np.clip(x / CELL, 0, N - 1.001), np.clip(y / CELL, 0, N - 1.001)
    i, j = int(fx), int(fy)
    tx, ty = fx - i, fy - j
    return float(a[j, i] * (1 - tx) * (1 - ty) + a[j, i + 1] * tx * (1 - ty) + a[j + 1, i] * (1 - tx) * ty + a[j + 1, i + 1] * tx * ty)


def wet(x, y):
    j, i = cell(x, y)
    return bool(WATER[j, i])


def slope_at(x, y):
    j, i = cell(x, y)
    return float(SLOPE[j, i])


def in_poly(p, poly):
    x, y = p
    inside = False
    for k in range(len(poly)):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def seg_intersect(a, b, c, d):
    """Intersection point of segments ab and cd (or None)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9: return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
        return (a[0] + r[0] * t, a[1] + r[1] * t), t, u
    return None


def dist_point_seg(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] ** 2 + ab[1] ** 2
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    q = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return math.hypot(p[0] - q[0], p[1] - q[1]), t


DT = SPEC["downtown"]
DT_POLY = DT["poly"]
MARGIN = SPEC["grid"]["margin_m"]
MAX_GRADE = SPEC["grid"]["max_local_grade"]
BRIDGE_MAX = SPEC["bridge_max_span_m"]


def inset_poly(poly, d):
    """Convex polygon moved inwards by d metres (counter-clockwise or clockwise)."""
    area = sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))
    sgn = 1.0 if area > 0 else -1.0
    lines = []
    for k in range(len(poly)):
        a, b = poly[k], poly[(k + 1) % len(poly)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = (-(b[1] - a[1]) / L * sgn, (b[0] - a[0]) / L * sgn)     # inward normal
        lines.append(((a[0] + n[0] * d, a[1] + n[1] * d), (b[0] - a[0], b[1] - a[1])))
    out = []
    for k in range(len(lines)):
        (p, r), (q, s_) = lines[k - 1], lines[k]
        den = r[0] * s_[1] - r[1] * s_[0]
        t = ((q[0] - p[0]) * s_[1] - (q[1] - p[1]) * s_[0]) / den
        out.append([p[0] + r[0] * t, p[1] + r[1] * t])
    return out


DT_RING = inset_poly(DT_POLY, 14.0)       # Seawall Drive's centreline
DT_STREETS = inset_poly(DT_POLY, 8.0)     # downtown streets run a little past it, then the stubs are pruned
DT_CLEAR = inset_poly(DT_POLY, -25.0)     # local grid streets keep this far from the peninsula


# --- 1. road pieces --------------------------------------------------------------------------
def cut_line(p0, p1, cls, name, inside=None, outside=None, step=4.0):
    """Straight line p0->p1 cut into drivable pieces: [(a, b, bridge), ...]."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    n = max(2, int(L / step))
    pts = [(p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n) for k in range(n + 1)]
    state = []
    prev_h = None
    for p in pts:
        x, y = p
        if not (MARGIN <= x <= SIZE - MARGIN and MARGIN <= y <= SIZE - MARGIN): st = "out"
        elif inside is not None and not in_poly(p, inside): st = "out"
        elif outside is not None and in_poly(p, outside): st = "out"
        elif wet(x, y): st = "water"
        else: st = "ok"
        if st == "ok" and cls == "local":
            hh = h_at(x, y)
            if prev_h is not None and abs(hh - prev_h) / step > MAX_GRADE: st = "steep"
            prev_h = hh
        else:
            prev_h = None if st != "ok" else h_at(x, y)
        state.append(st)
    # runs
    runs = []
    k = 0
    while k <= n:
        st = state[k]
        j = k
        while j + 1 <= n and state[j + 1] == st: j += 1
        runs.append([st, k, j])
        k = j + 1
    # short water runs between land runs become bridges on arterials
    pieces = []
    for idx, (st, a, b) in enumerate(runs):
        if st == "ok":
            pieces.append([a, b, False])
        elif st == "water" and cls in ("arterial", "boulevard") and 0 < idx < len(runs) - 1 \
                and runs[idx - 1][0] == "ok" and runs[idx + 1][0] == "ok" and (b - a + 2) * L / n <= BRIDGE_MAX:
            pieces.append([a - 1, b + 1, True])
    out = []
    for a, b, br in pieces:
        if (b - a) * L / n < (6 if br else 30): continue
        out.append((pts[max(a, 0)], pts[min(b, n)], br))
    return out


pieces = []   # dicts: a, b, cls, width, name, bridge, family


def add_pieces(p0, p1, cls, name, family, **kw):
    for a, b, br in cut_line(p0, p1, cls, name, **kw):
        pieces.append({"a": a, "b": b, "cls": cls, "width": W.get(cls, W["local"]), "name": name, "bridge": br, "family": family})


G = SPEC["grid"]
names = SPEC["names"]


def ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


ARTERIAL_AVENUE_NAMES = {600: "Marlow Avenue", 1000: "Centennial Avenue", 1200: "Broadmoor Avenue", 1700: "Harbour Avenue"}
street_names = {}
xs = list(range(G["streets_x"]["from"], G["streets_x"]["to"] + 1, G["streets_x"]["step"]))
for k, x in enumerate(xs):
    street_names[x] = ("%s Boulevard" if x in G["arterials_x"] else "%s Street") % names["streets"][k % len(names["streets"])]
ys = list(range(G["avenues_y"]["from"], G["avenues_y"]["to"] + 1, G["avenues_y"]["step"]))
avenue_names = {y: ARTERIAL_AVENUE_NAMES.get(y, "%s Avenue" % ordinal(k + 1)) for k, y in enumerate(ys)}
for x in xs:
    add_pieces((x, 0), (x, SIZE), "arterial" if x in G["arterials_x"] else "local", street_names[x], ("x", x), outside=DT_POLY if x in G["arterials_x"] else DT_CLEAR)
for y in ys:
    add_pieces((0, y), (SIZE, y), "arterial" if y in G["arterials_y"] else "local", avenue_names[y], ("y", y), outside=DT_POLY if y in G["arterials_y"] else DT_CLEAR)
# downtown boundary boulevard
br = DT["boundary_road"]
for k in range(len(br) - 1):
    add_pieces(tuple(br[k]), tuple(br[k + 1]), "boulevard", "Gateway Boulevard", ("b", k))
# rotated downtown grid
ang = math.radians(DT["angle_deg"])
du, dv = (math.cos(ang), math.sin(ang)), (-math.sin(ang), math.cos(ang))
cx, cy = DT["centre"]
sp = DT["spacing"]
dt_names = names["downtown"]
for k in range(-9, 10):
    for d_dir, d_off, fam in ((du, dv, "du"), (dv, du, "dv")):
        o = (cx + d_off[0] * k * sp, cy + d_off[1] * k * sp)
        p0 = (o[0] - d_dir[0] * 900, o[1] - d_dir[1] * 900)
        p1 = (o[0] + d_dir[0] * 900, o[1] + d_dir[1] * 900)
        nm = "%s %s" % (dt_names[(k + 9) % len(dt_names)], "Street" if fam == "du" else "Way")
        add_pieces(p0, p1, "downtown", nm, (fam, k), inside=DT_STREETS)
# the waterfront drive round the peninsula (south, west and north sides): the grid ends on it
for k, (a, b) in enumerate(zip(DT_RING, DT_RING[1:] + DT_RING[:1])):
    if k == 1: continue                                   # the east side is Gateway Boulevard
    add_pieces(tuple(a), tuple(b), "boulevard", "Seawall Drive", ("r", k))
# diagonal arterial
dg = SPEC["diagonal"]
add_pieces(tuple(dg["from"]), tuple(dg["to"]), "arterial", dg["name"], ("d", 0), outside=DT_POLY)
DIAG = (tuple(dg["from"]), tuple(dg["to"]))

# --- 2. graph: split pieces at crossings, nodes, connectors ----------------------------------
cuts = [[0.0, 1.0] for _ in pieces]
for i in range(len(pieces)):
    for j in range(i + 1, len(pieces)):
        if pieces[i]["family"] == pieces[j]["family"]: continue
        if pieces[i]["bridge"] or pieces[j]["bridge"]: continue
        hit = seg_intersect(pieces[i]["a"], pieces[i]["b"], pieces[j]["a"], pieces[j]["b"])
        if hit:
            _, t, u = hit
            cuts[i].append(t); cuts[j].append(u)
nodes = []          # {"id", "pos", "edges"}
node_index = {}


def node_at(p):
    key = (round(p[0] / 3.0), round(p[1] / 3.0))
    for dk in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        k2 = (key[0] + dk[0], key[1] + dk[1])
        if k2 in node_index and math.hypot(nodes[node_index[k2]]["pos"][0] - p[0], nodes[node_index[k2]]["pos"][1] - p[1]) < 3.5:
            return node_index[k2]
    nid = len(nodes)
    nodes.append({"id": nid, "pos": [round(p[0], 2), round(p[1], 2)], "edges": []})
    node_index[key] = nid
    return nid


edges = []
for i, pc in enumerate(pieces):
    ts = sorted(set(round(t, 6) for t in cuts[i]))
    a, b = pc["a"], pc["b"]
    for t0, t1 in zip(ts, ts[1:]):
        if (t1 - t0) * math.hypot(b[0] - a[0], b[1] - a[1]) < 2.0: continue
        p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
        p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
        n0, n1 = node_at(p0), node_at(p1)
        if n0 == n1: continue
        e = {"id": "road_%04d" % len(edges), "a": n0, "b": n1, "cls": pc["cls"], "width": pc["width"], "name": pc["name"], "bridge": pc["bridge"],
             "family": str(pc["family"])}
        edges.append(e)
        nodes[n0]["edges"].append(len(edges) - 1); nodes[n1]["edges"].append(len(edges) - 1)
# prune short dead-end stubs (streets running past the waterfront drive, slivers at cuts)
def edge_len(e):
    a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
    return math.hypot(b[0] - a[0], b[1] - a[1])


changed = True
while changed:
    changed = False
    for nd in nodes:
        if len(nd["edges"]) == 1:
            ei = nd["edges"][0]
            e = edges[ei]
            if e is not None and edge_len(e) < 20.0:
                edges[ei] = None
                nodes[e["a"]]["edges"].remove(ei); nodes[e["b"]]["edges"].remove(ei)
                changed = True
keep = [e for e in edges if e is not None]
remap = {id(e): k for k, e in enumerate(keep)}
for nd in nodes:
    nd["edges"] = [remap[id(edges[ei])] for ei in nd["edges"]]
edges = keep
for k, e in enumerate(edges): e["id"] = "road_%04d" % k
# connectors: dead ends near another road join it (downtown <-> grid, bridge landings)
for nd in nodes:
    if len(nd["edges"]) != 1: continue
    best, bd = None, 75.0
    own = edges[nd["edges"][0]]["name"]
    for other in nodes:
        if other is nd or not other["edges"]: continue
        if any(edges[e]["name"] == own for e in other["edges"]): continue
        d = math.hypot(other["pos"][0] - nd["pos"][0], other["pos"][1] - nd["pos"][1])
        if d < bd:
            mid_ok = all(not wet(nd["pos"][0] + (other["pos"][0] - nd["pos"][0]) * f, nd["pos"][1] + (other["pos"][1] - nd["pos"][1]) * f) for f in (0.25, 0.5, 0.75))
            if mid_ok: best, bd = other, d
    if best is not None:
        e = {"id": "road_%04d" % len(edges), "a": nd["id"], "b": best["id"], "cls": "local", "width": W["local"], "name": own, "bridge": False,
             "family": "conn", "source": nd["edges"][0]}
        edges.append(e)
        nd["edges"].append(len(edges) - 1); best["edges"].append(len(edges) - 1)
MAJOR = ("arterial", "boulevard", "downtown")
for nd in nodes:
    cls = [edges[e]["cls"] for e in nd["edges"]]
    majors = sum(1 for c in cls if c in MAJOR)
    nd["control"] = "signal" if (majors >= 3 or (majors >= 2 and len(cls) >= 3)) else ("stop" if len(cls) >= 3 and majors >= 1 else ("none" if len(cls) < 3 else "uncontrolled"))

# --- street names: one name per line per district, from the pioneers file -------------------
NEIGH = SPEC["neighbourhoods"]


def district(p):
    return min(NEIGH, key=lambda n: math.hypot(p[0] - n["centre"][0], p[1] - n["centre"][1]))


def culture_at(p):
    return district(p)["culture"]


NAMER = StreetNamer(os.path.join(SPEC_DIR, SPEC["street_names_file"]))
groups = {}
for k, e in enumerate(edges):
    if e.get("source") is not None: continue
    a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    cul = "downtown" if in_poly(mid, DT_POLY) or e["cls"] == "downtown" else culture_at(mid)
    groups.setdefault((cul, e["family"]), []).append(k)
ORDER = ["japanese", "korean", "british", "european", "turkish", "downtown", "mixed"]
RANK = {"local": 0, "downtown": 1, "boulevard": 2, "arterial": 3}
for key in sorted(groups, key=lambda g: (ORDER.index(g[0]), g[1])):
    cul, fam = key
    cls = max((edges[k]["cls"] for k in groups[key]), key=lambda c: RANK.get(c, 0))
    name = NAMER.take("mixed" if cul == "downtown" else cul, "downtown" if cul == "downtown" and cls == "downtown" else cls)
    for k in groups[key]:
        edges[k]["name"] = name
        edges[k]["culture"] = "mixed" if cul == "downtown" else cul
for e in edges:
    if e.get("source") is not None:
        e["name"] = edges[e["source"]]["name"]
        e["culture"] = edges[e["source"]].get("culture", "mixed")
        del e["source"]


def road_near(p, max_d=60.0):
    """The road edge nearest a point."""
    best, bd = None, max_d
    for e in edges:
        a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
        d, _ = dist_point_seg(p, a, b)
        if d < bd: best, bd = e, d
    return best

# --- 3. zoning, blocks, lots -----------------------------------------------------------------
PARKS = []
for pk in SPEC["parks"]:
    PARKS.append(pk)
items = {"houses": [], "garages": [], "fences": [], "shops": [], "towers": [], "warehouses": [], "public": [], "parks": [], "lots": [],
         "lanes": [], "plazas": []}


def half_width(x_or_y, axis):
    if axis == "x": return (W["arterial"] if x_or_y in G["arterials_x"] else W["local"]) / 2
    return (W["arterial"] if x_or_y in G["arterials_y"] else W["local"]) / 2


def park_at(p):
    for pk in PARKS:
        if "centre" in pk and math.hypot(p[0] - pk["centre"][0], p[1] - pk["centre"][1]) < pk["radius"]: return pk["name"]
        if "min_height" in pk and h_at(*p) > pk["min_height"]: return pk["name"]
    return None


def zone_of(p):
    for poly in SPEC["industrial"]:
        if in_poly(p, poly): return "industrial"
    return None


def near_diagonal(p, pad):
    d, _ = dist_point_seg(p, *DIAG)
    return d < W["arterial"] / 2 + pad


def buildable(p, pad=0.0):
    return not wet(*p) and slope_at(*p) < 9.0 and not in_poly(p, DT_POLY) and not near_diagonal(p, pad) and MARGIN < p[0] < SIZE - MARGIN and MARGIN < p[1] < SIZE - MARGIN


def neighbourhood(p):
    return min(NEIGH, key=lambda n: math.hypot(p[0] - n["centre"][0], p[1] - n["centre"][1]))["name"]


ARCHETYPES = ["craftsman", "vancouver_special", "bungalow", "modern_box", "foursquare", "tudor", "split_level", "west_coast"]
FENCES = ["wood", "hedge", "brick", "picket", "iron", "hedge", "wood"]
public_left = list(SPEC["public"])
blocks = []
block_counter = 0
for ix in range(len(xs) - 1):
    for iy in range(len(ys) - 1):
        x0, x1, y0, y1 = xs[ix], xs[ix + 1], ys[iy], ys[iy + 1]
        c = ((x0 + x1) / 2, (y0 + y1) / 2)
        samples = [(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy) for fx in (0.15, 0.4, 0.6, 0.85) for fy in (0.2, 0.5, 0.8)]
        ok = sum(1 for p in samples if buildable(p)) / len(samples)
        pk = park_at(c)
        bid = "block_%03d" % block_counter
        block_counter += 1
        rect = [x0 + half_width(x0, "x"), y0 + half_width(y0, "y"), x1 - half_width(x1, "x"), y1 - half_width(y1, "y")]
        if pk:
            blocks.append({"id": bid, "kind": "park", "rect": rect, "name": pk}); continue
        if ok < 0.45:
            if sum(1 for p in samples if not wet(*p)) / len(samples) > 0.5 and not in_poly(c, DT_POLY):
                blocks.append({"id": bid, "kind": "green", "rect": rect})
            continue
        if zone_of(c) == "industrial":
            blocks.append({"id": bid, "kind": "industrial", "rect": rect}); continue
        nb = SPEC["neighbourhood_park_every"]
        if rnd(bid, 1) < 1.0 / nb and not any(a in (x0, x1) for a in G["arterials_x"]):
            blocks.append({"id": bid, "kind": "park", "rect": rect, "name": "%s Park" % neighbourhood(c)}); continue
        blocks.append({"id": bid, "kind": "residential", "rect": rect, "x": (x0, x1), "y": (y0, y1)})
# public buildings take the nearest residential half-block
for pub in public_left:
    if in_poly(pub["at"], DT_POLY): continue
    best = min((b for b in blocks if b["kind"] == "residential"), key=lambda b: math.hypot((b["rect"][0] + b["rect"][2]) / 2 - pub["at"][0], (b["rect"][1] + b["rect"][3]) / 2 - pub["at"][1]))
    half = "south" if pub["at"][1] < (best["rect"][1] + best["rect"][3]) / 2 else "north"
    best.setdefault("public", {})[half] = pub

SW, VG = W["sidewalk"], W["verge"]
LOT = SPEC["lots"]
lot_n = house_n = 0
for b in blocks:
    r = b["rect"]
    if b["kind"] in ("park", "green"):
        items["parks"].append({"id": "park_" + b["id"], "rect": [r[0] + SW, r[1] + SW, r[2] - SW, r[3] - SW], "name": b.get("name", "Green"), "kind": b["kind"]})
        continue
    if b["kind"] == "industrial":
        x0, y0, x1, y1 = r[0] + SW + 4, r[1] + SW + 4, r[2] - SW - 4, r[3] - SW - 4
        n = max(1, int((x1 - x0) / 60))
        for k in range(n):
            wx0 = x0 + (x1 - x0) * k / n + 3; wx1 = x0 + (x1 - x0) * (k + 1) / n - 3
            cxw, cyw = (wx0 + wx1) / 2, (y0 + y1) / 2
            if not buildable((cxw, cyw), 6) and wet(cxw, cyw): continue
            items["warehouses"].append({"id": "warehouse_%03d" % len(items["warehouses"]), "pos": [cxw, cyw], "size": [wx1 - wx0, y1 - y0, 8 + 6 * rnd(b["id"], k)], "yaw": 0.0,
                                         "palette": int(rnd(b["id"], k + 9) * 6)})
        continue
    (x0, x1), (y0, y1) = b["x"], b["y"]
    ymid = (y0 + y1) / 2
    lane_ok = all(buildable((x, ymid)) for x in np.linspace(r[0] + 6, r[2] - 6, 8))
    if lane_ok:
        items["lanes"].append({"id": "lane_" + b["id"], "a": [x0 + half_width(x0, "x"), ymid], "b": [x1 - half_width(x1, "x"), ymid], "width": W["lane"]})
    for half in ("south", "north"):
        front_y = y0 + half_width(y0, "y") + SW + VG if half == "south" else y1 - half_width(y1, "y") - SW - VG
        back_y = ymid - W["lane"] / 2 if half == "south" else ymid + W["lane"] / 2
        if not lane_ok: back_y = ymid
        facing = -1.0 if half == "south" else 1.0           # +y = north: the house front faces the avenue
        avenue_y = y0 if half == "south" else y1
        lx0 = x0 + half_width(x0, "x") + SW + VG
        lx1 = x1 - half_width(x1, "x") - SW - VG
        pub = b.get("public", {}).get(half)
        if pub:
            cxp, cyp = (lx0 + lx1) / 2, (front_y + back_y) / 2
            items["public"].append({"id": "public_%02d" % len(items["public"]), "kind": pub["kind"], "name": pub["name"], "pos": [cxp, cyp],
                                    "size": [lx1 - lx0 - 8, abs(back_y - front_y) - 6], "yaw": 0.0 if facing > 0 else math.pi, "front": facing,
                                    "address": "%d %s" % (int((cxp - xs[0]) / 2) * 2 + 100, avenue_names[avenue_y])})
            continue
        commercial = avenue_y in G["arterials_y"] or near_diagonal(((lx0 + lx1) / 2, (front_y + back_y) / 2), 70)
        arterial_end = [k for k in (x0, x1) if k in G["arterials_x"]]
        if commercial:
            # a row of shops along the arterial: frontages 18-36 m
            x = lx0
            k = 0
            while x < lx1 - 12:
                fw = min(lx1 - x, 18 + 18 * rnd(b["id"] + half, k))
                cxs = x + fw / 2
                depth = min(24.0, abs(back_y - front_y) - 2)
                cys = front_y + math.copysign(depth / 2, back_y - front_y)
                if not near_diagonal((cxs, cys), 10) and not wet(cxs, cys) and slope_at(cxs, cys) < 9:
                    items["shops"].append({"id": "shop_%04d" % len(items["shops"]), "pos": [cxs, cys], "size": [fw - 0.4, depth, 0],
                                           "floors": 2 + int(rnd(b["id"] + half, k + 50) * 3), "yaw": 0.0 if facing > 0 else math.pi,
                                           "palette": int(rnd(b["id"] + half, k + 70) * 8), "address": "%d %s" % (int((cxs - xs[0]) / 2) * 2 + 100, avenue_names[avenue_y])})
                x += fw
                k += 1
            continue
        # residential lots
        span = lx1 - lx0
        # a corner shop on an arterial street end
        if arterial_end:
            for ae in arterial_end:
                cw = 24.0
                cxs = lx0 + cw / 2 if ae == x0 else lx1 - cw / 2
                cys = (front_y + back_y) / 2
                if not wet(cxs, cys) and slope_at(cxs, cys) < 9:
                    # turned a quarter to face the arterial: the facade (size[0], local x) runs along y, the depth along x
                    items["shops"].append({"id": "shop_%04d" % len(items["shops"]), "pos": [cxs, cys], "size": [abs(back_y - front_y) - 3, cw - 1, 0],
                                           "floors": 2 + int(rnd(b["id"] + half, 90) * 2), "yaw": (math.pi / 2 if ae == x0 else -math.pi / 2),
                                           "palette": int(rnd(b["id"] + half, 91) * 8), "address": "%d %s" % (int((cys - ys[0]) / 2) * 2 + 100, street_names[ae])})
            if x0 in G["arterials_x"]: lx0 += 24.0
            if x1 in G["arterials_x"]: lx1 -= 24.0
            span = lx1 - lx0
        n = int(span // LOT["width"])
        if n < 1: continue
        lw = span / n
        depth = abs(back_y - front_y)
        for k in range(n):
            lid = "lot_%04d" % lot_n
            lot_n += 1
            ax0 = lx0 + k * lw
            ax1 = ax0 + lw
            lcx = (ax0 + ax1) / 2
            lcy = (front_y + back_y) / 2
            if not buildable((lcx, lcy), 6) or not buildable((lcx, front_y + (back_y - front_y) * 0.2), 4):
                continue
            o = OVR.get(lid, {})
            if o.get("remove"): continue
            addr = "%d %s" % (int((lcx - xs[0]) / 2) * 2 + 100 + (1 if half == "north" else 0), avenue_names[avenue_y])
            lot = {"id": lid, "rect": [ax0, min(front_y, back_y), ax1, max(front_y, back_y)], "front": facing, "front_y": front_y, "back_y": back_y,
                   "address": addr, "neighbourhood": neighbourhood((lcx, lcy)), "lane": lane_ok}
            items["lots"].append(lot)
            hid = "house_%04d" % house_n
            house_n += 1
            ho = OVR.get(hid, {})
            cul = culture_at((lcx, lcy))
            rules = CULTURES[cul]
            lot["culture"] = cul
            # a catalogue house of the district's culture that fits the lot (mixed districts borrow 20 %)
            pool_c = cul if cul != "mixed" or rnd(hid, 13) > 0.2 else ["turkish", "japanese", "korean", "european", "british"][int(rnd(hid, 14) * 5)]
            fits = [c for c in CATALOGUE if c["culture"] == pool_c and c["w"] <= lw - 1.0] or [c for c in CATALOGUE if c["w"] <= lw - 1.0]
            entry = fits[int(rnd(hid, 5) * len(fits))]
            if "archetype" in ho:
                entry = next((c for c in CATALOGUE if c["id"] == ho["archetype"]), entry)
            hw, hd = entry["w"], entry["d"]
            setback = rules["setback"] + 1.5 * rnd(hid, 3)
            hcy = front_y + (back_y - front_y) / depth * (setback + hd / 2)
            hcx = lcx + (rnd(hid, 4) - 0.5) * max(0.0, lw - hw - 2.0)
            walls, roofs = rules["walls"], rules["roofs"]
            house = {"id": hid, "lot": lid, "pos": [round(hcx, 2), round(hcy, 2)], "yaw": 0.0 if facing > 0 else math.pi, "size": [hw, hd],
                     "archetype": entry["id"], "kit": "H_" + entry["id"], "scale": [1.0, 1.0], "culture": cul, "door": entry["door"],
                     "tint": ho.get("tint", walls[int(rnd(hid, 6) * len(walls))] if entry["wall"] in TINTABLE else "ffffff"),
                     "roof_tint": ho.get("roof_tint", roofs[int(rnd(hid, 7) * len(roofs))]),
                     "siding": int(rnd(hid, 6) * 10), "roof": int(rnd(hid, 7) * 5), "storeys": entry["storeys"], "height": entry["height"], "address": addr}
            if ho.get("remove"): continue
            items["houses"].append(house)
            fence = ho.get("fence", rules["fences"][int(rnd(hid, 10) * len(rules["fences"]))])
            lot["fence"] = fence
            # garage on the lane
            garage = lane_ok and rnd(hid, 11) < rules["garage"]
            if garage:
                gx = ax0 + 4.0 if rnd(hid, 12) < 0.5 else ax1 - 4.0
                gy = back_y - (back_y - front_y) / depth * 4.0
                items["garages"].append({"id": "garage_%04d" % len(items["garages"]), "lot": lid, "pos": [round(gx, 2), round(gy, 2)], "yaw": math.pi if facing > 0 else 0.0,
                                         "roof": house["roof"], "siding": house["siding"]})
            # fence segments: front (low, gap for the walk), east side (and west on the first lot), back (gap for the garage)
            fh_front = {"hedge": 1.2, "picket": 0.9, "brick": 0.9, "iron": 0.9, "stucco_wall": 1.2, "block": 1.2, "stone": 0.8}.get(fence, 1.1)
            fh_side = 1.6 if fence == "hedge" else 1.8
            walk = hcx + (entry["door"][0] if facing > 0 else -entry["door"][0])
            segs = []
            if fence != "none":
                segs.append([ax0 + 0.2, front_y, walk - 0.8, front_y, fence, fh_front])
                segs.append([walk + 0.8, front_y, ax1 - 0.2, front_y, fence, fh_front])
                side_type = "hedge" if fence == "hedge" else rules["side"]
                house_front = front_y + (back_y - front_y) / depth * setback
                if k == n - 1:                     # the last lot's east side faces a street: a front fence all along
                    segs.append([ax1, front_y, ax1, back_y, fence, fh_front])
                else:
                    segs.append([ax1, front_y, ax1, house_front, fence if fence in ("hedge", "picket") else side_type, fh_front])
                    segs.append([ax1, house_front, ax1, back_y, side_type, fh_side])
                if k == 0:                         # the first lot's west side faces a street too
                    segs.append([ax0, front_y, ax0, back_y, fence, fh_front])
                if lane_ok:
                    if garage:
                        gx0 = gx - 3.3; gx1 = gx + 3.3
                        if gx0 - ax0 > 0.6: segs.append([ax0, back_y, gx0, back_y, side_type, fh_side])
                        if ax1 - gx1 > 0.6: segs.append([gx1, back_y, ax1, back_y, side_type, fh_side])
                    else:
                        segs.append([ax0, back_y, ax1 - 3.2, back_y, side_type, fh_side])
            items["fences"].append({"id": "fence_" + lid, "lot": lid, "segments": [[round(v, 2) if isinstance(v, float) else v for v in s] for s in segs]})

# downtown blocks: podium + tower(s)
for a in range(-9, 9):
    for bb in range(-9, 9):
        c = (cx + du[0] * (a + 0.5) * sp + dv[0] * (bb + 0.5) * sp, cy + du[1] * (a + 0.5) * sp + dv[1] * (bb + 0.5) * sp)
        if not in_poly(c, DT_POLY): continue
        did = "dt_%02d_%02d" % (a + 9, bb + 9)
        fit = None                                   # the largest footprint (fraction of the block) that fits on land
        for f in (0.4, 0.3, 0.22):
            corners = [(c[0] + du[0] * su * sp * f + dv[0] * sv * sp * f, c[1] + du[1] * su * sp * f + dv[1] * sv * sp * f) for su in (-1, 1) for sv in (-1, 1)]
            if not any(wet(*p) or not in_poly(p, DT_RING) for p in corners + [c]):
                fit = f
                break
        if fit is None:
            if in_poly(c, DT_RING) and not wet(*c):
                items["parks"].append({"id": "park_" + did, "rot_rect": [c[0], c[1], sp * 0.45, sp * 0.45, DT["angle_deg"]], "name": "Harbour Point Park", "kind": "pocket"})
            continue
        if c[0] < DT["park_west_of_x"]:
            items["parks"].append({"id": "park_" + did, "rot_rect": [c[0], c[1], sp - W["downtown"] - 2 * SW, sp - W["downtown"] - 2 * SW, DT["angle_deg"]], "name": "Harbour Point Park", "kind": "park"})
            continue
        if rnd(did, 1) < 0.08:
            items["plazas"].append({"id": "plaza_" + did, "pos": list(c), "size": sp - W["downtown"] - 2 * SW, "angle": DT["angle_deg"]})
            continue
        dist = math.hypot(c[0] - DT["centre"][0], c[1] - DT["centre"][1])
        base = sp - W["downtown"] - 2 * SW - 2 if fit == 0.4 else 2 * fit * sp - 4
        towers = 1 + (1 if rnd(did, 2) < 0.4 else 0)
        podium_h = 7 + 5 * rnd(did, 3)
        tlist = []
        for t in range(towers):
            fp = min(22 + 8 * rnd(did, 10 + t), base - 6)
            off = (rnd(did, 20 + t) - 0.5) * (base - fp) * (0.0 if towers == 1 else 1.0)
            off2 = (rnd(did, 30 + t) - 0.5) * (base - fp) * 0.5 + (-1 if t == 0 else 1) * (base - fp) * (0.25 if towers == 2 else 0)
            h = 30 + 140 * math.exp(-dist / 330.0) * (0.55 + 0.45 * rnd(did, 40 + t))
            if fit < 0.4: h = min(h, 22 + 24 * rnd(did, 45 + t))      # the waterfront fringe: mid-rises
            tlist.append({"offset": [round(off, 2), round(off2, 2)], "footprint": round(fp, 2), "height": round(h, 1), "style": int(rnd(did, 50 + t) * 5)})
        items["towers"].append({"id": "tower_" + did, "pos": [round(c[0], 2), round(c[1], 2)], "angle": DT["angle_deg"], "podium": [round(base, 2), round(podium_h, 1)],
                                "towers": tlist, "address": "%d %s" % (100 + (a + 9) * 20 + (bb + 9) * 2, "%s Street" % dt_names[(a + 9) % len(dt_names)])})
# downtown public buildings take the nearest tower block
for pub in SPEC["public"]:
    if not in_poly(pub["at"], DT_POLY): continue
    best = min(items["towers"], key=lambda t: math.hypot(t["pos"][0] - pub["at"][0], t["pos"][1] - pub["at"][1]))
    items["towers"].remove(best)
    items["public"].append({"id": "public_%02d" % len(items["public"]), "kind": pub["kind"], "name": pub["name"], "pos": best["pos"], "size": [best["podium"][0], best["podium"][0]],
                            "yaw": math.radians(DT["angle_deg"]), "front": 1.0, "address": best["address"]})

# --- 4. street furniture ---------------------------------------------------------------------
props = {k: [] for k in ("lamp", "traffic_light", "stop_sign", "bus_stop", "tree", "hydrant", "bench", "street_sign", "utility_pole", "vending_machine",
                         "post_box", "phone_box", "ad_column", "cesme", "cafe_set")}


def edge_geom(e):
    a = nodes[e["a"]]["pos"]; b = nodes[e["b"]]["pos"]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    return a, b, L, d, (-d[1], d[0])


bus_acc = {}
for e in edges:
    a, b, L, d, nrm = edge_geom(e)
    if e["cls"] == "lane": continue
    off = e["width"] / 2 + VG * 0.5
    yaw = math.atan2(d[0], d[1])
    # lamps every 32 m, alternating sides
    k = 0
    s = 12.0
    while s < L - 8:
        side = 1 if k % 2 == 0 else -1
        p = (a[0] + d[0] * s + nrm[0] * off * side, a[1] + d[1] * s + nrm[1] * off * side)
        if not wet(*p) or e["bridge"]:
            kind = "utility_pole" if e.get("culture") == "japanese" and e["cls"] == "local" else "lamp"
            props[kind].append([round(p[0], 2), round(p[1], 2), round(yaw_of((-nrm[0] * side, -nrm[1] * side)), 3)])
        s += 32.0
        k += 1
    # boulevard trees on residential locals
    if e["cls"] == "local" and not e["bridge"]:
        s = 14.0                                  # clear of the paved corner and its name board
        while s < L - 14.0:
            for side in (1, -1):
                p = (a[0] + d[0] * s + nrm[0] * off * side, a[1] + d[1] * s + nrm[1] * off * side)
                if not wet(*p) and not in_poly(p, DT_POLY) and slope_at(*p) < 14:
                    if all(math.hypot(p[0] - l[0], p[1] - l[1]) > 3.0 for l in props["lamp"][-4:]):
                        tv = CULTURES[e.get("culture", "mixed")]["trees"]
                        props["tree"].append([round(p[0], 2), round(p[1], 2), round(rnd(e["id"], int(s)) * 6.28, 2), tv[int(rnd(e["id"], int(s) + 1) * len(tv))]])
            s += 11.0
        s = 30.0
        while s < L - 10:
            p = (a[0] + d[0] * s + nrm[0] * off, a[1] + d[1] * s + nrm[1] * off)
            if not wet(*p): props["hydrant"].append([round(p[0], 2), round(p[1], 2), round(yaw_of(nrm), 3)])
            s += 95.0
    # bus stops on arterials: about every 380 m along the line, both sides
    if e["cls"] in ("arterial", "boulevard") and not e["bridge"]:
        acc = bus_acc.get(e["name"], 190.0) + L
        if acc >= 380.0 and L > 60:
            for side in (1, -1):
                p = (a[0] + d[0] * L * 0.5 + nrm[0] * (e["width"] / 2 + SW * 0.6) * side, a[1] + d[1] * L * 0.5 + nrm[1] * (e["width"] / 2 + SW * 0.6) * side)
                if not wet(*p):
                    props["bus_stop"].append([round(p[0], 2), round(p[1], 2), round(yaw_of((-nrm[0] * side, -nrm[1] * side)), 3), e["name"]])
            acc = 0.0
        bus_acc[e["name"]] = acc
for nd in nodes:
    if nd["control"] not in ("signal", "stop"): continue
    for ei in nd["edges"]:
        e = edges[ei]
        other = e["b"] if e["a"] == nd["id"] else e["a"]
        op = nodes[other]["pos"]
        L = math.hypot(op[0] - nd["pos"][0], op[1] - nd["pos"][1])
        if L < 1: continue
        d = ((op[0] - nd["pos"][0]) / L, (op[1] - nd["pos"][1]) / L)
        nrm = (-d[1], d[0])                                      # drivers' right as they come in (they travel along -d)
        cross_w = max((edges[x]["width"] for x in nd["edges"] if x != ei), default=e["width"])
        p = (nd["pos"][0] + d[0] * (cross_w / 2 + 2.0) + nrm[0] * (e["width"] / 2 + 1.0), nd["pos"][1] + d[1] * (cross_w / 2 + 2.0) + nrm[1] * (e["width"] / 2 + 1.0))
        yaw = yaw_of(d)                                          # the signal faces the oncoming drivers
        if nd["control"] == "signal":
            props["traffic_light"].append([round(p[0], 2), round(p[1], 2), round(yaw, 3), nd["id"]])
        elif e["cls"] not in MAJOR:
            props["stop_sign"].append([round(p[0], 2), round(p[1], 2), round(yaw, 3), nd["id"]])
# street-name boards at every corner of every junction, and the districts' corner furniture
CORNER_PROPS = {"japanese": "vending_machine", "british": "post_box", "european": "ad_column", "turkish": "cesme", "korean": "vending_machine"}
for nd in nodes:
    if len(nd["edges"]) < 3: continue
    p = nd["pos"]
    ends = []
    for ei in nd["edges"]:
        e = edges[ei]
        other = nodes[e["b"] if e["a"] == nd["id"] else e["a"]]["pos"]
        L = math.hypot(other[0] - p[0], other[1] - p[1])
        if L < 1: continue
        ends.append(((other[0] - p[0]) / L, (other[1] - p[1]) / L, e))
    ends.sort(key=lambda t: math.atan2(t[1], t[0]))
    cul = culture_at(p)
    for k in range(len(ends)):
        d1x, d1y, e1 = ends[k]
        d2x, d2y, e2 = ends[(k + 1) % len(ends)]
        if d1x * d2y - d1y * d2x < 0.25 or e1["name"] == e2["name"]: continue
        o1, o2 = e1["width"] / 2 + VG + SW * 0.55, e2["width"] / 2 + VG + SW * 0.55
        n1, n2 = (-d1y, d1x), (-d2y, d2x)
        q1 = (p[0] + n1[0] * o1, p[1] + n1[1] * o1)
        q2 = (p[0] - n2[0] * o2, p[1] - n2[1] * o2)
        den = d1x * d2y - d1y * d2x
        t = ((q2[0] - q1[0]) * d2y - (q2[1] - q1[1]) * d2x) / den
        c = (q1[0] + d1x * t, q1[1] + d1y * t)
        far = math.hypot(c[0] - p[0], c[1] - p[1])
        if far > 22.0:                         # a sharp corner: the board stands 22 m out along its bisector
            c = (p[0] + (c[0] - p[0]) * 22.0 / far, p[1] + (c[1] - p[1]) * 22.0 / far)
        if wet(*c): continue
        props["street_sign"].append([round(c[0], 2), round(c[1], 2), round(math.atan2(d1y, d1x), 3), round(math.atan2(d2y, d2x), 3), e1["name"], e2["name"], cul])
        extra = CORNER_PROPS.get(cul)
        if extra and rnd(str(nd["id"]), k + 40) < (0.3 if extra != "cesme" else 0.12):
            q = (c[0] + (d1x + d2x) * 2.2, c[1] + (d1y + d2y) * 2.2)
            if not wet(*q): props[extra].append([round(q[0], 2), round(q[1], 2), round(yaw_of((-(n1[0] - n2[0]), -(n1[1] - n2[1]))), 3)])
# shop-front furniture: cafe tables (European, Turkish, mixed), phone boxes (British), vending machines (Japanese, Korean)
for k, sh in enumerate(items["shops"]):
    cul = culture_at(sh["pos"])
    f = (-math.sin(sh["yaw"]), math.cos(sh["yaw"]))          # the shop's front (+Y turned by yaw)
    front = (sh["pos"][0] + f[0] * (sh["size"][1] / 2 + 1.4), sh["pos"][1] + f[1] * (sh["size"][1] / 2 + 1.4))
    r = rnd(sh["id"], 77)
    if cul in ("european", "turkish", "mixed") and r < 0.35:
        props["cafe_set"].append([round(front[0], 2), round(front[1], 2), round(sh["yaw"], 3)])
    elif cul == "british" and r < 0.15:
        props["phone_box"].append([round(front[0], 2), round(front[1], 2), round(sh["yaw"], 3)])
    elif cul in ("japanese", "korean") and r < 0.4:
        props["vending_machine"].append([round(front[0], 2), round(front[1], 2), round(sh["yaw"], 3)])
# park trees and benches
for pk in items["parks"]:
    if "rot_rect" in pk:                                   # downtown parks, turned with the grid
        pcx, pcy, sx, sy, adeg = pk["rot_rect"]
        ca, sa = math.cos(math.radians(adeg)), math.sin(math.radians(adeg))
        for k in range(int(sx * sy / 160)):
            u, v = (rnd(pk["id"], k * 2) - 0.5) * (sx - 6), (rnd(pk["id"], k * 2 + 1) - 0.5) * (sy - 6)
            p = (pcx + u * ca - v * sa, pcy + u * sa + v * ca)
            if not wet(*p): props["tree"].append([round(p[0], 2), round(p[1], 2), round(rnd(pk["id"], k + 999) * 6.28, 2), 4 + int(rnd(pk["id"], k + 1999) * 3)])
        for k in range(3):
            u, v = (rnd(pk["id"], k + 3000) - 0.5) * (sx - 10), (rnd(pk["id"], k + 4000) - 0.5) * (sy - 10)
            props["bench"].append([round(pcx + u * ca - v * sa, 2), round(pcy + u * sa + v * ca, 2), round(math.radians(adeg) + (k % 2) * math.pi, 2)])
    if "rect" in pk:
        x0, y0, x1, y1 = pk["rect"]
        n = int((x1 - x0) * (y1 - y0) / 220)
        for k in range(n):
            p = (x0 + (x1 - x0) * rnd(pk["id"], k * 2), y0 + (y1 - y0) * rnd(pk["id"], k * 2 + 1))
            if not wet(*p): props["tree"].append([round(p[0], 2), round(p[1], 2), round(rnd(pk["id"], k + 999) * 6.28, 2), 4 + int(rnd(pk["id"], k + 1999) * 3)])
        for k in range(max(1, n // 12)):
            p = (x0 + 6 + (x1 - x0 - 12) * rnd(pk["id"], k + 3000), y0 + 6 + (y1 - y0 - 12) * rnd(pk["id"], k + 4000))
            if not wet(*p): props["bench"].append([round(p[0], 2), round(p[1], 2), round(rnd(pk["id"], k + 5000) * 6.28, 2)])
# --- placement resolver: every prop checked against the street and against each other ---------
# Priority order (traffic control first, decoration last); a prop in conflict slides along its
# street up to 3 m, else it is dropped. Conflicts: on a carriageway or in a junction box, on the
# sidewalk's walking line (except name boards at corners and shop-front furniture), inside a
# building, house, garage or lot fence line, or closer to another prop than their radii allow.
RADIUS = {"traffic_light": 0.45, "street_sign": 0.35, "bus_stop": 2.4, "lamp": 0.35, "utility_pole": 0.35, "hydrant": 0.35,
          "stop_sign": 0.25, "post_box": 0.45, "phone_box": 0.7, "ad_column": 0.85, "cesme": 1.1, "vending_machine": 0.65,
          "cafe_set": 1.3, "tree": 1.7, "bench": 1.0}
PRIORITY = ["traffic_light", "street_sign", "stop_sign", "bus_stop", "lamp", "utility_pole", "hydrant", "post_box", "phone_box",
            "ad_column", "cesme", "vending_machine", "cafe_set", "tree", "bench"]
ON_WALK_OK = {"street_sign", "cafe_set", "bus_stop", "vending_machine", "phone_box", "ad_column", "post_box", "cesme", "bench"}
BLOCKERS = []                                # oriented footprints (cx, cy, half w, half d, cos, sin) of every building


def _footprint(it, w, d, yaw):
    return (it["pos"][0], it["pos"][1], w / 2, d / 2, math.cos(yaw), math.sin(yaw))


for hs in items["houses"]: BLOCKERS.append(_footprint(hs, hs["size"][0] + 0.6, hs["size"][1] + 0.6, hs["yaw"]))
for g in items["garages"]: BLOCKERS.append(_footprint(g, 7.0, 7.0, g["yaw"]))
for sh in items["shops"]: BLOCKERS.append(_footprint(sh, sh["size"][0], sh["size"][1], sh["yaw"]))
for wh in items["warehouses"]: BLOCKERS.append(_footprint(wh, wh["size"][0], wh["size"][1], 0.0))
for pb in items["public"]: BLOCKERS.append(_footprint(pb, min(pb["size"][0], 90), min(pb["size"][1], 30), pb["yaw"]))
for tw in items["towers"]:
    BLOCKERS.append(_footprint(tw, tw["podium"][0] + 1.0, tw["podium"][0] + 1.0, math.radians(tw["angle"])))
LOT_RECTS = [lot["rect"] for lot in items["lots"]]
CELL_R = 32.0
EDGE_GRID = {}
for ei, e in enumerate(edges):
    a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
    for t in np.linspace(0, 1, max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 16) + 1)):
        q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        EDGE_GRID.setdefault((int(q[0] // CELL_R), int(q[1] // CELL_R)), set()).add(ei)
BLOCK_GRID = {}
for bi, (bx, by, bw, bd_, bc, bs) in enumerate(BLOCKERS):
    ext = bw * abs(bc) + bd_ * abs(bs), bw * abs(bs) + bd_ * abs(bc)
    x0, y0, x1, y1 = bx - ext[0], by - ext[1], bx + ext[0], by + ext[1]
    for gx in range(int(x0 // CELL_R), int(x1 // CELL_R) + 1):
        for gy in range(int(y0 // CELL_R), int(y1 // CELL_R) + 1):
            BLOCK_GRID.setdefault((gx, gy), []).append(bi)
LOT_GRID = {}
for li, (x0, y0, x1, y1) in enumerate(LOT_RECTS):
    for gx in range(int(x0 // CELL_R), int(x1 // CELL_R) + 1):
        for gy in range(int(y0 // CELL_R), int(y1 // CELL_R) + 1):
            LOT_GRID.setdefault((gx, gy), []).append(li)


def near_cells(p, r=1):
    gx, gy = int(p[0] // CELL_R), int(p[1] // CELL_R)
    return [(gx + i, gy + j) for i in range(-r, r + 1) for j in range(-r, r + 1)]


def street_conflict(kind, p):
    """Why a prop may not stand at p (or None)."""
    rad = RADIUS[kind]
    for ce in near_cells(p):
        for ei in EDGE_GRID.get(ce, ()):
            e = edges[ei]
            a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
            d, t = dist_point_seg(p, a, b)
            half = e["width"] / 2
            if d < half + 0.3 and not e["bridge"]:               # every prop stands at least 0.3 m behind the kerb
                return "carriageway"
            walk0, walk1 = half + VG + SW * 0.3, half + VG + SW * 0.75
            if kind not in ON_WALK_OK and walk0 < d < walk1 and 0.05 < t < 0.95:
                return "walking line"
    for ce in near_cells(p, 0):
        for bi in BLOCK_GRID.get(ce, ()):
            bx, by, bw, bd_, bc, bs = BLOCKERS[bi]
            dx, dy = p[0] - bx, p[1] - by
            if abs(dx * bc + dy * bs) < bw + rad and abs(-dx * bs + dy * bc) < bd_ + rad:
                return "building"
        if kind not in ("tree", "bench"):          # trees and benches may stand in parks; not inside lots
            for li in LOT_GRID.get(ce, ()):
                x0, y0, x1, y1 = LOT_RECTS[li]
                if x0 + 0.3 < p[0] < x1 - 0.3 and y0 + 0.3 < p[1] < y1 - 0.3:
                    return "inside a lot"
    return None


placed_grid = {}
resolver_log = {"moved": 0, "dropped": {}, "kept": 0}


def prop_conflict(kind, p):
    why = street_conflict(kind, p)
    if why: return why
    for ce in near_cells(p):
        for k2, q in placed_grid.get(ce, ()):
            if math.hypot(p[0] - q[0], p[1] - q[1]) < RADIUS[kind] + RADIUS[k2]:
                return "too close to a " + k2
    return None


def nearest_edge_dir(p):
    best, bd = None, 1e9
    for ce in near_cells(p):
        for ei in EDGE_GRID.get(ce, ()):
            e = edges[ei]
            a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
            d, _ = dist_point_seg(p, a, b)
            if d < bd:
                L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                best, bd = ((b[0] - a[0]) / L, (b[1] - a[1]) / L), d
    return best or (1.0, 0.0)


for kind in PRIORITY:
    keep = []
    for it in props[kind]:
        p = (it[0], it[1])
        why = prop_conflict(kind, p)
        if why and kind not in ("traffic_light", "street_sign"):
            d = nearest_edge_dir(p)
            for step in (1.0, -1.0, 2.0, -2.0, 3.0, -3.0):
                q = (p[0] + d[0] * step, p[1] + d[1] * step)
                if prop_conflict(kind, q) is None:
                    it[0], it[1] = round(q[0], 2), round(q[1], 2)
                    p, why = q, None
                    resolver_log["moved"] += 1
                    break
        if why and kind in ("traffic_light", "street_sign"):
            # traffic control must stay at its junction: search outwards (and inwards) from the junction
            # centre along the line through the prop for the nearest clear spot
            nd = min(nodes, key=lambda n: (n["pos"][0] - p[0]) ** 2 + (n["pos"][1] - p[1]) ** 2)
            vx, vy = p[0] - nd["pos"][0], p[1] - nd["pos"][1]
            L = math.hypot(vx, vy) or 1.0
            cands = [(p[0] + vx / L * st, p[1] + vy / L * st) for st in (1.0, 2.0, 3.0, -1.0, 4.0, 5.0, -2.0, 6.0, 8.0, 10.0, 12.0)]
            cands += [(p[0] + r * math.cos(t * math.pi / 8), p[1] + r * math.sin(t * math.pi / 8)) for r in (1.0, 2.0, 3.0, 4.5, 6.0, 7.5, 9.0) for t in range(16)]
            for q in cands:
                if prop_conflict(kind, q) is None:
                    it[0], it[1] = round(q[0], 2), round(q[1], 2)
                    p, why = q, None
                    resolver_log["moved"] += 1
                    break
        if why:
            resolver_log["dropped"][kind + ": " + why.split(" a ")[0]] = resolver_log["dropped"].get(kind + ": " + why.split(" a ")[0], 0) + 1
            continue
        keep.append(it)
        placed_grid.setdefault((int(p[0] // CELL_R), int(p[1] // CELL_R)), []).append((kind, p))
        resolver_log["kept"] += 1
    props[kind] = keep
# a street whose own corner board was dropped gets an extra blade on a neighbouring board of the junction
extra_blades = 0
for nd in nodes:
    if len(nd["edges"]) < 3: continue
    p = nd["pos"]
    boards = [sg for sg in props["street_sign"] if math.hypot(sg[0] - p[0], sg[1] - p[1]) < 30.0]
    if not boards: continue
    for ei in nd["edges"]:
        e = edges[ei]
        if any(e["name"] in sg[4:6] or e["name"] in sg[7::2] for sg in boards): continue
        other = nodes[e["b"] if e["a"] == nd["id"] else e["a"]]["pos"]
        yaw = math.atan2(other[1] - p[1], other[0] - p[0])
        board = min(boards, key=lambda sg: math.hypot(sg[0] - p[0], sg[1] - p[1]))
        board.extend([round(yaw, 3), e["name"]])
        extra_blades += 1
resolver_log["extra_blades"] = extra_blades
print("RESOLVER", json.dumps(resolver_log))

# overrides on props: "tree_0012": {"remove": true}
for kind, lst in props.items():
    keep = []
    for k, it in enumerate(lst):
        o = OVR.get("%s_%04d" % (kind, k), {})
        if not o.get("remove"):
            if "pos" in o: it[0], it[1] = o["pos"]
            keep.append(it)
    props[kind] = keep

# district colours on shop fronts
for sh in items["shops"]:
    sh["culture"] = culture_at(sh["pos"])
    rules = CULTURES[sh["culture"]]
    sh["awning"] = rules["awnings"][int(rnd(sh["id"], 81) * len(rules["awnings"]))]
    sh["facade"] = rules["facades"][int(rnd(sh["id"], 82) * len(rules["facades"]))]

# addresses from the named streets: every lot, house, shop and public building faces its nearest road
for lot in items["lots"]:
    x0, y0, x1, y1 = lot["rect"]
    e = road_near(((x0 + x1) / 2, lot["front_y"] - lot["front"] * 6.0))
    if e is not None: lot["address"] = "%s %s" % (lot["address"].split(" ")[0], e["name"])
addr_of = {lot["id"]: lot["address"] for lot in items["lots"]}
for hs in items["houses"]: hs["address"] = addr_of.get(hs["lot"], hs["address"])
for kind in ("shops", "public", "towers"):
    for it in items[kind]:
        e = road_near((it["pos"][0], it["pos"][1]), 120.0)
        if e is not None: it["address"] = "%s %s" % (it["address"].split(" ")[0], e["name"])

# --- 5. grading: smooth road profiles and lot pads -------------------------------------------
G_H = H0.copy()
node_h = {nd["id"]: float(np.mean([h_at(nd["pos"][0] + dx, nd["pos"][1] + dy) for dx in (-5, 0, 5) for dy in (-5, 0, 5)])) for nd in nodes}
acc_t = np.zeros_like(G_H)
acc_w = np.zeros_like(G_H)
for e in edges:
    a, b, L, d, nrm = edge_geom(e)
    ha, hb = node_h[e["a"]], node_h[e["b"]]
    if e["bridge"]:
        continue
    n = max(2, int(L / 4))
    prof = np.array([h_at(a[0] + d[0] * L * k / n, a[1] + d[1] * L * k / n) for k in range(n + 1)])
    kern = np.ones(9) / 9
    smooth = np.convolve(np.pad(prof, 4, mode="edge"), kern, mode="valid")
    lin = np.linspace(ha, hb, n + 1)
    prof = lin + np.clip(smooth - lin, -3.0, 3.0) * 0.6
    e["profile"] = [round(float(v), 2) for v in prof[:: max(1, (n + 1) // 24)]] + ([round(float(prof[-1]), 2)] if n % max(1, (n + 1) // 24) else [])
    e["heights"] = [round(ha, 2), round(hb, 2)]
    half = e["width"] / 2 + SW + VG + 1.0
    feather = 10.0
    x0, x1 = min(a[0], b[0]) - half - feather, max(a[0], b[0]) + half + feather
    y0, y1 = min(a[1], b[1]) - half - feather, max(a[1], b[1]) + half + feather
    j0, i0 = cell(x0, y0)
    j1, i1 = cell(x1, y1)
    jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
    px, py = ii * CELL, jj * CELL
    t = np.clip(((px - a[0]) * d[0] + (py - a[1]) * d[1]) / L, 0, 1)
    dist = np.hypot(px - (a[0] + d[0] * L * t), py - (a[1] + d[1] * L * t))
    target = np.interp(t, np.linspace(0, 1, n + 1), prof)
    wgt = np.clip(1.0 - (dist - half) / feather, 0, 1)
    wgt = wgt * wgt * (3 - 2 * wgt)
    sl = (slice(j0, j1 + 1), slice(i0, i1 + 1))
    acc_t[sl] += target * wgt
    acc_w[sl] += wgt
mask = acc_w > 0
blend = np.clip(acc_w, 0, 1)
G_H = np.where(mask, G_H * (1 - blend) + (acc_t / np.maximum(acc_w, 1e-6)) * blend, G_H)
# lot pads: each lot level with its front road (+0.3 m), feathered
for lot in items["lots"]:
    x0, y0, x1, y1 = lot["rect"]
    fy = lot["front_y"]
    pad_h = h_at((x0 + x1) / 2, fy - lot["front"] * 2.0, G_H) + 0.3
    j0, i0 = cell(x0, y0)
    j1, i1 = cell(x1, y1)
    sl = (slice(j0, j1 + 1), slice(i0, i1 + 1))
    G_H[sl] = G_H[sl] * 0.25 + pad_h * 0.75
    lot["pad_h"] = round(pad_h, 2)
G_H = np.where(WATER, H0, G_H)

# heights of every placed item on the graded ground
for kind in ("houses", "garages", "shops", "towers", "warehouses", "public"):
    for it in items[kind]:
        it["h"] = round(h_at(it["pos"][0], it["pos"][1], G_H), 2)
for lot in items["lots"]:
    pass
for kind, lst in props.items():
    for it in lst:
        it.insert(2, round(h_at(it[0], it[1], G_H), 2))

# --- 6. write --------------------------------------------------------------------------------
city = {"name": SPEC["name"], "size_m": SIZE, "cell_m": CELL, "grid": N, "sea_level": 0.0,
        "nodes": [{"id": n["id"], "pos": n["pos"], "h": round(node_h[n["id"]], 2), "control": n["control"], "edges": [edges[e]["id"] for e in n["edges"]]} for n in nodes],
        "roads": edges, "lanes": items["lanes"], "lots": items["lots"], "houses": items["houses"], "garages": items["garages"], "fences": items["fences"],
        "shops": items["shops"], "towers": items["towers"], "warehouses": items["warehouses"], "public": items["public"], "parks": items["parks"],
        "plazas": items["plazas"], "props": props, "palettes": SPEC["palettes"], "cultures": {k: {"sign": v["sign"]} for k, v in CULTURES.items()}, "neighbourhoods": NEIGH, "water": {"lakes": META.get("lakes", []), "rivers": SPEC.get("rivers", [])},
        "terrain": {"min_height": float(G_H.min()), "max_height": float(G_H.max())}}
for lane in city["lanes"]:
    lane["h"] = [round(h_at(*lane["a"], G_H), 2), round(h_at(*lane["b"], G_H), 2)]
json.dump(city, open(os.path.join(out_dir, "city.json"), "w", encoding="utf-8"), separators=(",", ":"))
np.savez_compressed(os.path.join(out_dir, "graded.npz"), height=G_H.astype(np.float32), water=WATER, water_level=T["water_level"], sea=T["sea"])
G_H.astype("<f4").tofile(os.path.join(out_dir, "heights.f32"))
T["water_level"].astype("<f4").tofile(os.path.join(out_dir, "water_level.f32"))
WATER.astype(np.uint8).tofile(os.path.join(out_dir, "water.u8"))
stats = {k: len(v) for k, v in city.items() if isinstance(v, list)}
stats.update({"props_" + k: len(v) for k, v in props.items()})
stats["signals"] = sum(1 for n in nodes if n["control"] == "signal")
stats["bridges"] = sum(1 for e in edges if e["bridge"])
print("PLAN", json.dumps(stats))

# --- 7. preview map --------------------------------------------------------------------------
try:
    from PIL import Image, ImageDraw
    S = 2048 / SIZE
    gy, gx = np.gradient(G_H)
    shade = np.clip(0.75 + (gx * -0.6 + gy * 0.6) * 0.25, 0.4, 1.1)
    base = np.stack([0.62 * shade, 0.72 * shade, 0.52 * shade], -1)
    base[WATER] = (0.45, 0.65, 0.85)
    img = Image.fromarray((np.clip(base[::-1], 0, 1) * 255).astype(np.uint8)).resize((2048, 2048))
    dr = ImageDraw.Draw(img)
    def P(p): return (p[0] * S, (SIZE - p[1]) * S)
    for pk in items["parks"]:
        if "rect" in pk:
            x0, y0, x1, y1 = pk["rect"]; dr.rectangle([P((x0, y1)), P((x1, y0))], fill=(120, 175, 105))
    for lot in items["lots"]:
        x0, y0, x1, y1 = lot["rect"]; dr.rectangle([P((x0, y1)), P((x1, y0))], outline=(150, 150, 130))
    colours = {"arterial": (250, 220, 120), "boulevard": (250, 200, 110), "local": (255, 255, 255), "downtown": (240, 240, 240)}
    for e in edges:
        a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
        dr.line([P(a), P(b)], fill=(120, 120, 160) if e["bridge"] else colours.get(e["cls"], (255, 255, 255)), width=max(2, int(e["width"] * S)))
    for ln in items["lanes"]:
        dr.line([P(ln["a"]), P(ln["b"])], fill=(205, 200, 185), width=max(1, int(ln["width"] * S)))
    for hs in items["houses"]:
        x, y = hs["pos"]; w_, d_ = hs["size"]; dr.rectangle([P((x - w_ / 2, y + d_ / 2)), P((x + w_ / 2, y - d_ / 2))], fill=(196, 120, 96))
    for sh in items["shops"]:
        x, y = sh["pos"]; w_, d_ = sh["size"][:2]; dr.rectangle([P((x - w_ / 2, y + d_ / 2)), P((x + w_ / 2, y - d_ / 2))], fill=(150, 110, 170))
    for tw in items["towers"]:
        x, y = tw["pos"]; r_ = tw["podium"][0] / 2; dr.rectangle([P((x - r_, y + r_)), P((x + r_, y - r_))], fill=(90, 110, 140))
    for wh in items["warehouses"]:
        x, y = wh["pos"]; w_, d_ = wh["size"][:2]; dr.rectangle([P((x - w_ / 2, y + d_ / 2)), P((x + w_ / 2, y - d_ / 2))], fill=(140, 140, 140))
    for pb in items["public"]:
        x, y = pb["pos"]; dr.ellipse([P((x - 18, y + 18)), P((x + 18, y - 18))], fill=(220, 60, 60))
    for n in nodes:
        if n["control"] == "signal": dr.ellipse([P((n["pos"][0] - 5, n["pos"][1] + 5)), P((n["pos"][0] + 5, n["pos"][1] - 5))], fill=(230, 40, 40))
    for bs in props["bus_stop"]:
        dr.rectangle([P((bs[0] - 4, bs[1] + 4)), P((bs[0] + 4, bs[1] - 4))], fill=(30, 90, 220))
    img.save(os.path.join(out_dir, "plan.png"))
except ImportError:
    pass
