"""CityForge Blender build: the planned city (plan_city.py output) -> GLBs for Godot.

    blender --background --factory-startup --python tools/cityforge/build_city.py -- \
        <plan_dir> <out_dir> [--blend preview.blend] [--chunks 0_0,3_4] [--no-kit] [--no-export]

Writes <out_dir>/kit.glb (every archetype as <name> and <name>_LOD1: houses, garage, street
furniture, trees; placed in Godot with MultiMeshes) and <out_dir>/chunks/c_<i>_<j>.glb, one per
256 m square: Terrain, Water, Roads (asphalt, intersections, bridges), Walks (sidewalks, verges,
curbs, corners, paths, plazas, parking), Fences and Buildings (shops, towers, warehouses, public).
Every chunk mesh is in city coordinates (Blender X = x - size/2, Y = y - size/2), so Godot puts
chunks at the origin. Material names (CF_*) are the contract with world/cityforge/.
"""
import json, math, os, sys
import numpy as np
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import Mesh, to_object
import kit

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PLAN, OUT = argv[0], argv[1]
opts = argv[2:]
def opt(name, default=None):
    return opts[opts.index(name) + 1] if name in opts else default

CITY = json.load(open(os.path.join(PLAN, "city.json"), encoding="utf-8"))
G = np.load(os.path.join(PLAN, "graded.npz"))
GH = G["height"].astype(np.float64)
WATER = G["water"].astype(bool)
WL = G["water_level"].astype(np.float64)
SIZE, CELL, N = CITY["size_m"], CITY["cell_m"], CITY["grid"]
HALF = SIZE / 2
CHUNK = 256.0
NCH = int(SIZE // CHUNK)
SPEC_W = {"sidewalk": 3.0, "verge": 1.6}
NODES = {n["id"]: n for n in CITY["nodes"]}
ROADS = {r["id"]: r for r in CITY["roads"]}


def h_at(x, y, a=GH):
    fx, fy = min(max(x / CELL, 0), N - 1.001), min(max(y / CELL, 0), N - 1.001)
    i, j = int(fx), int(fy)
    tx, ty = fx - i, fy - j
    return float(a[j, i] * (1 - tx) * (1 - ty) + a[j, i + 1] * tx * (1 - ty) + a[j + 1, i] * (1 - tx) * ty + a[j + 1, i + 1] * tx * ty)


def wet(x, y):
    return bool(WATER[int(min(max(round(y / CELL), 0), N - 1)), int(min(max(round(x / CELL), 0), N - 1))])


def B(x, y, z):
    """City metres -> Blender coordinates."""
    return (x - HALF, y - HALF, z)


def chunk_of(x, y):
    return (min(max(int(x // CHUNK), 0), NCH - 1), min(max(int(y // CHUNK), 0), NCH - 1))


# --- materials (preview colours; Godot replaces them by name) --------------------------------
PREVIEW = {
    "CF_Siding": (0.75, 0.72, 0.62), "CF_Roof": (0.25, 0.26, 0.28), "CF_Trim": (0.92, 0.91, 0.87), "CF_Glass": (0.18, 0.26, 0.32),
    "CF_Door": (0.35, 0.18, 0.12), "CF_Brick": (0.55, 0.28, 0.2), "CF_Concrete": (0.62, 0.62, 0.6), "CF_Wood": (0.55, 0.38, 0.22),
    "CF_Metal": (0.18, 0.2, 0.22), "CF_RoofFlat": (0.35, 0.35, 0.36), "CF_LampGlow": (1.0, 0.92, 0.7), "CF_SignalPole": (0.75, 0.62, 0.15),
    "CF_SignalRed": (0.8, 0.05, 0.03), "CF_SignalAmber": (0.85, 0.5, 0.0), "CF_SignalGreen": (0.05, 0.7, 0.3), "CF_SignalWalk": (0.95, 0.95, 0.9),
    "CF_SignGreen": (0.05, 0.4, 0.2), "CF_SignRed": (0.75, 0.05, 0.05), "CF_SignWhite": (0.95, 0.95, 0.95), "CF_SignBlue": (0.1, 0.25, 0.65),
    "CF_Hydrant": (0.85, 0.75, 0.1), "CF_HydrantCap": (0.7, 0.1, 0.08), "CF_Leaves": (0.25, 0.42, 0.16), "CF_Bark": (0.3, 0.22, 0.16),
    "CF_Terrain": (0.36, 0.48, 0.24), "CF_Water": (0.12, 0.3, 0.42), "CF_Asphalt": (0.16, 0.16, 0.17), "CF_Sidewalk": (0.68, 0.67, 0.64),
    "CF_Curb": (0.6, 0.6, 0.58), "CF_Verge": (0.3, 0.46, 0.2), "CF_Lane": (0.3, 0.29, 0.28), "CF_Parking": (0.22, 0.22, 0.23),
    "CF_Facade": (0.7, 0.66, 0.6), "CF_Curtain": (0.3, 0.42, 0.5), "CF_MetalSiding": (0.55, 0.57, 0.58), "CF_Awning": (0.6, 0.15, 0.12),
    "CF_Storefront": (0.2, 0.28, 0.33), "CF_SignBoard": (0.85, 0.82, 0.75), "CF_FenceWood": (0.48, 0.34, 0.22), "CF_Picket": (0.94, 0.94, 0.9),
    "CF_Iron": (0.08, 0.08, 0.09), "CF_Hedge": (0.16, 0.32, 0.12), "CF_FireDoor": (0.75, 0.08, 0.06), "CF_Stone": (0.78, 0.75, 0.68),
    "CF_Railing": (0.45, 0.47, 0.5), "CF_Path": (0.62, 0.58, 0.5), "CF_BrickFacade": (0.55, 0.3, 0.22),
    "CF_SidingV": (0.75, 0.72, 0.62), "CF_RoofV": (0.25, 0.26, 0.28), "CF_LeavesV": (0.25, 0.42, 0.16), "CF_RoofSeamV": (0.4, 0.42, 0.43),
    "CF_Stucco": (0.85, 0.82, 0.74), "CF_Plaster": (0.92, 0.9, 0.84), "CF_BrickPainted": (0.88, 0.88, 0.86), "CF_BrickLondon": (0.55, 0.43, 0.27),
    "CF_Ashlar": (0.76, 0.72, 0.64), "CF_Cedar": (0.45, 0.31, 0.2), "CF_Yakisugi": (0.08, 0.07, 0.06), "CF_LightWood": (0.62, 0.47, 0.3),
    "CF_TimberDark": (0.18, 0.12, 0.08), "CF_RoofSlate": (0.2, 0.22, 0.25), "CF_RoofTerracotta": (0.6, 0.28, 0.15), "CF_RoofKawara": (0.2, 0.21, 0.23),
    "CF_RoofSeam": (0.4, 0.42, 0.43), "CF_Shutter": (0.18, 0.32, 0.25), "CF_SignPlate": (0.1, 0.3, 0.6), "CF_SignEdge": (0.95, 0.95, 0.95),
    "CF_VendGlow": (0.9, 0.95, 1.0), "CF_PostRed": (0.7, 0.05, 0.05), "CF_Posters": (0.85, 0.8, 0.7), "CF_Brass": (0.8, 0.6, 0.25),
    "CF_Plaque": (0.9, 0.88, 0.8), "CF_Parasol": (0.9, 0.86, 0.76),
}
MATS = {}
for name, c in PREVIEW.items():
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    MATS[name] = mt


def palette(i, kind):
    P = {"facade": [(0.78, 0.74, 0.66), (0.62, 0.42, 0.34), (0.82, 0.8, 0.76), (0.55, 0.58, 0.6), (0.7, 0.6, 0.48), (0.48, 0.32, 0.26), (0.86, 0.84, 0.78), (0.64, 0.66, 0.58)],
         "awning": [(0.62, 0.12, 0.1), (0.1, 0.3, 0.2), (0.12, 0.2, 0.45), (0.85, 0.6, 0.12), (0.25, 0.25, 0.27), (0.5, 0.12, 0.3), (0.12, 0.42, 0.45), (0.7, 0.3, 0.1)],
         "metal": [(0.55, 0.57, 0.58), (0.36, 0.45, 0.52), (0.68, 0.66, 0.6), (0.42, 0.5, 0.44), (0.6, 0.38, 0.3), (0.75, 0.75, 0.76)],
         "glass": [(0.42, 0.55, 0.62), (0.35, 0.5, 0.48), (0.5, 0.52, 0.55), (0.32, 0.4, 0.55), (0.55, 0.5, 0.42)]}[kind]
    c = P[int(i) % len(P)]
    return (c[0], c[1], c[2], 1.0)


# --- terrain and water -----------------------------------------------------------------------
LOT_MASK = np.zeros((N, N), bool)
PARK_MASK = np.zeros((N, N), bool)
for lot in CITY["lots"]:
    x0, y0, x1, y1 = lot["rect"]
    LOT_MASK[int(y0 // CELL):int(y1 // CELL) + 1, int(x0 // CELL):int(x1 // CELL) + 1] = True
for pk in CITY["parks"]:
    if "rect" in pk:
        x0, y0, x1, y1 = pk["rect"]
        PARK_MASK[int(y0 // CELL):int(y1 // CELL) + 1, int(x0 // CELL):int(x1 // CELL) + 1] = True
gy, gx = np.gradient(GH, CELL)
SLOPE_DEG = np.degrees(np.arctan(np.hypot(gx, gy)))
# distance (cells) to water, a few cells far, for beaches
near_w = WATER.copy()
dist_w = np.where(WATER, 0, 99)
for k in range(1, 6):
    grown = near_w.copy()
    grown[1:] |= near_w[:-1]; grown[:-1] |= near_w[1:]; grown[:, 1:] |= near_w[:, :-1]; grown[:, :-1] |= near_w[:, 1:]
    dist_w = np.where(grown & (dist_w == 99), k, dist_w)
    near_w = grown
# water level filled outwards one ring so shore quads have a level
WLF = np.where(WATER, WL, -1e9)
for _ in range(2):
    pad = np.pad(WLF, 1, mode="edge")
    nb = np.max(np.stack([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]]), 0)
    WLF = np.where(WLF > -1e8, WLF, nb)


def terrain_colour(j, i):
    """R lawn (lots, parks), G sand (shore), B rock (steep) for the Godot terrain shader."""
    rock = min(max((SLOPE_DEG[j, i] - 20.0) / 14.0, 0.0), 1.0)
    sand = 0.0
    if not WATER[j, i] and dist_w[j, i] <= 3 and GH[j, i] < max(WLF[j, i], 0.0) + 2.5: sand = 1.0 - (dist_w[j, i] - 1) / 3.0
    if WATER[j, i]: sand = 1.0
    lawn = 1.0 if (LOT_MASK[j, i] or PARK_MASK[j, i]) else 0.0
    return (lawn, max(sand, 0.0), rock, 0.0 if WATER[j, i] else 1.0)


def build_terrain(ci, cj, m):
    i0, j0 = int(ci * CHUNK / CELL), int(cj * CHUNK / CELL)
    n = int(CHUNK / CELL)
    for j in range(j0, min(j0 + n, N - 1)):
        for i in range(i0, min(i0 + n, N - 1)):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            pts = [B(a * CELL, b * CELL, GH[b, a]) for a, b in q]
            m.poly(pts, "CF_Terrain", uv=[(p[0], p[1]) for p in pts], col=[terrain_colour(b, a) for a, b in q])


def build_water(ci, cj, m):
    i0, j0 = int(ci * CHUNK / CELL), int(cj * CHUNK / CELL)
    n = int(CHUNK / CELL)
    for j in range(j0, min(j0 + n, N - 1)):
        for i in range(i0, min(i0 + n, N - 1)):
            corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if not any(WATER[b, a] for a, b in corners): continue
            lv = [WLF[b, a] for a, b in corners]
            if min(lv) < -1e8: continue
            pts = [B(a * CELL, b * CELL, l) for (a, b), l in zip(corners, lv)]
            m.poly(pts, "CF_Water", uv=[(p[0], p[1]) for p in pts])


# --- roads -----------------------------------------------------------------------------------
def unit(v):
    L = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / L, v[1] / L)


def line_x(p, d, q, e):
    """Intersection parameter t along p + t*d with the line q + s*e."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9: return None
    return ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den


def walk_width(cls):
    return SPEC_W["sidewalk"] + SPEC_W["verge"]


# trims: (road id, end 'a'/'b') -> {"road": t, "left": t, "right": t}; corners: per node polygons
TRIM = {}
CORNERS = []      # (node id, [4 points])
PATCHES = {}      # node id -> polygon (city xy)
for nd in CITY["nodes"]:
    p = nd["pos"]
    ends = []
    for rid in nd["edges"]:
        r = ROADS[rid]
        end = "a" if r["a"] == nd["id"] else "b"
        other = NODES[r["b"] if end == "a" else r["a"]]["pos"]
        d = unit((other[0] - p[0], other[1] - p[1]))
        ends.append({"rid": rid, "end": end, "d": d, "w": r["width"] / 2, "ang": math.atan2(d[1], d[0]), "bridge": r["bridge"]})
        TRIM[(rid, end)] = {"road": 0.0, "left": 0.0, "right": 0.0}
    if len(ends) < 2: continue
    ends.sort(key=lambda e: e["ang"])
    for k in range(len(ends)):
        e1, e2 = ends[k], ends[(k + 1) % len(ends)]
        d1, d2 = e1["d"], e2["d"]
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if cross < 0.25: continue                         # straight on, reflex or tiny angle: no corner
        n1 = (-d1[1], d1[0]); n2 = (-d2[1], d2[0])
        R1, R2 = e1["w"] + walk_width(None), e2["w"] + walk_width(None)

        def P(o1, o2):
            q1 = (p[0] + n1[0] * o1, p[1] + n1[1] * o1)
            q2 = (p[0] - n2[0] * o2, p[1] - n2[1] * o2)
            t = line_x(q1, d1, q2, d2)
            return (q1[0] + d1[0] * t, q1[1] + d1[1] * t)
        quad = [P(e1["w"], e2["w"]), P(R1, e2["w"]), P(R1, R2), P(e1["w"], R2)]
        if max(math.hypot(q[0] - p[0], q[1] - p[1]) for q in quad) > 60: continue
        CORNERS.append((nd["id"], quad))
        proj1 = lambda q: (q[0] - p[0]) * d1[0] + (q[1] - p[1]) * d1[1]
        proj2 = lambda q: (q[0] - p[0]) * d2[0] + (q[1] - p[1]) * d2[1]
        t1, t2 = TRIM[(e1["rid"], e1["end"])], TRIM[(e2["rid"], e2["end"])]
        t1["road"] = max(t1["road"], proj1(quad[0]))
        t2["road"] = max(t2["road"], proj2(quad[0]))
        t1["left"] = max(t1["left"], proj1(quad[2]), proj1(quad[3]))
        t2["right"] = max(t2["right"], proj2(quad[2]), proj2(quad[1]))
    # the intersection patch: hull of the trimmed road ends
    pts = []
    for e in ends:
        t = TRIM[(e["rid"], e["end"])]["road"]
        if t <= 0.01: continue
        c = (p[0] + e["d"][0] * t, p[1] + e["d"][1] * t)
        n = (-e["d"][1], e["d"][0])
        pts += [(c[0] + n[0] * e["w"], c[1] + n[1] * e["w"]), (c[0] - n[0] * e["w"], c[1] - n[1] * e["w"])]
    if len(pts) >= 3:
        pts = sorted(set((round(a, 3), round(b, 3)) for a, b in pts))
        def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, hi = [], []
        for q in pts:
            while len(lo) >= 2 and cr(lo[-2], lo[-1], q) <= 0: lo.pop()
            lo.append(q)
        for q in reversed(pts):
            while len(hi) >= 2 and cr(hi[-2], hi[-1], q) <= 0: hi.pop()
            hi.append(q)
        PATCHES[nd["id"]] = lo[:-1] + hi[:-1]

MARK = {"arterial": 1.0, "boulevard": 1.0, "downtown": 2.0, "local": 0.0}
ASPH, WALK = 0.05, 0.19


def road_h(r, t):
    """Road surface height at fraction t along the road (bridges arch slightly)."""
    a, b = NODES[r["a"]], NODES[r["b"]]
    if r["bridge"]:
        return a["h"] + (b["h"] - a["h"]) * t + 1.2 * math.sin(math.pi * t)
    pa, pb = a["pos"], b["pos"]
    return h_at(pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)


def ribbon(m, r, t0, t1, o0, o1, z_off, mat, step=8.0, uv_kind="walk", col=None, mark=None):
    """Band from lateral offset o0 to o1 (left +) between distances t0..t1 (metres from a)."""
    a, b = NODES[r["a"]]["pos"], NODES[r["b"]]["pos"]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-d[1], d[0])
    if t1 - t0 < 0.05: return
    k = max(1, int(math.ceil((t1 - t0) / step)))
    ts = [t0 + (t1 - t0) * i / k for i in range(k + 1)]
    for s0, s1 in zip(ts, ts[1:]):
        h0, h1 = road_h(r, s0 / L) + z_off, road_h(r, s1 / L) + z_off
        q = [(a[0] + d[0] * s0 + n[0] * o0, a[1] + d[1] * s0 + n[1] * o0, h0), (a[0] + d[0] * s1 + n[0] * o0, a[1] + d[1] * s1 + n[1] * o0, h1),
             (a[0] + d[0] * s1 + n[0] * o1, a[1] + d[1] * s1 + n[1] * o1, h1), (a[0] + d[0] * s0 + n[0] * o1, a[1] + d[1] * s0 + n[1] * o1, h0)]
        if o1 < o0: q = [q[1], q[0], q[3], q[2]]
        pts = [B(*x) for x in q]
        if uv_kind == "road":
            uv = [(o0, s0 - t0), (o0, s1 - t0), (o1, s1 - t0), (o1, s0 - t0)]
            uv2 = [(mark[0], t1 - s0), (mark[0], t1 - s1), (mark[0], t1 - s1), (mark[0], t1 - s0)]
            if o1 < o0: uv, uv2 = [uv[1], uv[0], uv[3], uv[2]], [uv2[1], uv2[0], uv2[3], uv2[2]]
            m.poly(pts, mat, uv=uv, col=mark[1], uv2=uv2)
        else:
            m.poly(pts, mat, col=col)


def curb_face(m, r, t0, t1, o, z_lo, z_hi, outward, mat="CF_Curb"):
    """Vertical face along the road at lateral offset o; outward=+1 faces +n."""
    a, b = NODES[r["a"]]["pos"], NODES[r["b"]]["pos"]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-d[1], d[0])
    if t1 - t0 < 0.05: return
    k = max(1, int(math.ceil((t1 - t0) / 8.0)))
    ts = [t0 + (t1 - t0) * i / k for i in range(k + 1)]
    for s0, s1 in zip(ts, ts[1:]):
        h0, h1 = road_h(r, s0 / L), road_h(r, s1 / L)
        p0 = (a[0] + d[0] * s0 + n[0] * o, a[1] + d[1] * s0 + n[1] * o)
        p1 = (a[0] + d[0] * s1 + n[0] * o, a[1] + d[1] * s1 + n[1] * o)
        q = [B(p0[0], p0[1], h0 + z_lo), B(p1[0], p1[1], h1 + z_lo), B(p1[0], p1[1], h1 + z_hi), B(p0[0], p0[1], h0 + z_hi)]
        m.poly(q if outward < 0 else q[::-1], mat)


def build_road(r, roads, walks):
    a, b = NODES[r["a"]], NODES[r["b"]]
    L = math.hypot(b["pos"][0] - a["pos"][0], b["pos"][1] - a["pos"][1])
    ta, tb = TRIM[(r["id"], "a")], TRIM[(r["id"], "b")]
    w = r["width"] / 2
    ctrl_a, ctrl_b = a["control"], b["control"]
    def xw(c): return 1.0 if c == "signal" else (0.5 if c == "stop" else 0.0)
    mark = (MARK.get(r["cls"], 0.0), (xw(ctrl_a), xw(ctrl_b), 0.0, 1.0))
    t0, t1 = ta["road"], L - tb["road"]
    ribbon(roads, r, t0, t1, -w, w, ASPH, "CF_Asphalt", uv_kind="road", mark=mark)
    SW, VG = SPEC_W["sidewalk"], SPEC_W["verge"]
    if r["bridge"]:
        for side in (1, -1):
            ribbon(walks, r, t0, t1, side * w, side * (w + 2.2), WALK, "CF_Sidewalk")
            curb_face(walks, r, t0, t1, side * w, ASPH, WALK, -side)
            curb_face(walks, r, t0, t1, side * (w + 2.2), -1.2, WALK + 1.05, side, "CF_Railing")
            curb_face(walks, r, t0, t1, side * (w + 2.1), WALK, WALK + 1.05, -side, "CF_Railing")
        ribbon(walks, r, t0, t1, -(w + 2.2), w + 2.2, -1.2, "CF_Concrete")      # deck underside (faces down)
        for k in range(1, int(L // 32) + 1):
            s = L * k / (int(L // 32) + 1)
            px = a["pos"][0] + (b["pos"][0] - a["pos"][0]) * s / L
            py = a["pos"][1] + (b["pos"][1] - a["pos"][1]) * s / L
            top = road_h(r, s / L) - 1.2
            walks.obox(px - HALF, py - HALF, min(h_at(px, py), -3.0) - 2, 3.0, 3.0, top, math.atan2(b["pos"][1] - a["pos"][1], b["pos"][0] - a["pos"][0]), "CF_Concrete")
        return
    paved = r["cls"] in ("downtown", "boulevard")
    for side, key_a, key_b in ((1, "left", "right"), (-1, "right", "left")):
        s0, s1 = ta[key_a], L - tb[key_b]
        curb_face(walks, r, s0, s1, side * w, ASPH - 0.02, WALK - 0.02, -side)
        if paved:
            ribbon(walks, r, s0, s1, side * w, side * (w + SW + VG), WALK, "CF_Sidewalk")
        else:
            ribbon(walks, r, s0, s1, side * w, side * (w + VG), WALK - 0.02, "CF_Verge")
            ribbon(walks, r, s0, s1, side * (w + VG), side * (w + VG + SW), WALK, "CF_Sidewalk")
        curb_face(walks, r, s0, s1, side * (w + SW + VG), -0.4, WALK, side)


def build_patch(nid, roads):
    poly = PATCHES[nid]
    h = NODES[nid]["h"]
    pts = [B(p[0], p[1], h_at(p[0], p[1]) + ASPH + 0.004) for p in poly]
    roads.poly(pts, "CF_Asphalt", uv=[(0.0, 50.0)] * len(pts), col=(0.0, 0.0, 0.0, 1.0), uv2=[(-1.0, 50.0)] * len(pts))


def build_corner(quad, walks):
    pts = [B(p[0], p[1], h_at(p[0], p[1]) + WALK) for p in quad]
    walks.poly(pts, "CF_Sidewalk")


def build_lane(ln, roads):
    a, b = ln["a"], ln["b"]
    d = unit((b[0] - a[0], b[1] - a[1]))
    n = (-d[1], d[0])
    w = ln["width"] / 2
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    k = max(1, int(L // 4))
    for i in range(k):
        s0, s1 = L * i / k, L * (i + 1) / k
        q = []
        for s, o in ((s0, -w), (s1, -w), (s1, w), (s0, w)):
            x, y = a[0] + d[0] * s + n[0] * o, a[1] + d[1] * s + n[1] * o
            q.append(B(x, y, h_at(x, y) + 0.06))
        roads.poly(q, "CF_Lane")


# --- lots, fences ----------------------------------------------------------------------------
FENCE_MAT = {"wood": "CF_FenceWood", "picket": "CF_Picket", "iron": "CF_Iron", "hedge": "CF_Hedge", "brick": "CF_Brick",
             "block": "CF_Concrete", "stucco_wall": "CF_Stucco", "stone": "CF_Ashlar"}


def build_fence(fc, m):
    for x0, y0, x1, y1, kind, hgt in fc["segments"]:
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.3: continue
        rise = abs(h_at(x0, y0) - h_at(x1, y1))
        k = max(1, min(int(math.ceil(L / 3.0)), int(math.ceil(rise / 0.25))))   # split only where the ground changes
        yaw = math.atan2(y1 - y0, x1 - x0)
        th = {"hedge": 0.8, "brick": 0.32, "wood": 0.06, "picket": 0.05, "iron": 0.04, "block": 0.15, "stucco_wall": 0.25, "stone": 0.4}[kind]
        for i in range(k):
            ax, ay = x0 + (x1 - x0) * i / k, y0 + (y1 - y0) * i / k
            bx, by = x0 + (x1 - x0) * (i + 1) / k, y0 + (y1 - y0) * (i + 1) / k
            cx, cy = (ax + bx) / 2, (ay + by) / 2
            g = min(h_at(ax, ay), h_at(bx, by), h_at(cx, cy))
            seg = L / k + (0.02 if kind in ("hedge", "brick") else 0.0)
            hh = hgt + (0.15 * math.sin(cx * 1.7 + cy) if kind == "hedge" else 0.0)
            if kind == "stucco_wall" and hgt < 1.5:          # a low rendered wall with an iron railing on top
                m.obox(cx - HALF, cy - HALF, g - 0.2, seg, th, g + 0.6, yaw, "CF_Stucco", zb=g)
                m.obox(cx - HALF, cy - HALF, g + 0.6, seg + 0.04, th + 0.06, g + 0.68, yaw, "CF_Concrete")
                m.obox(cx - HALF, cy - HALF, g + 0.68, seg, 0.04, g + hh, yaw, "CF_Iron", zb=g + 0.68)
                continue
            m.obox(cx - HALF, cy - HALF, g - 0.2, seg, th, g + hh, yaw, FENCE_MAT[kind], zb=g)
            if kind in ("block", "stone", "stucco_wall"):
                m.obox(cx - HALF, cy - HALF, g + hh, seg + 0.02, th + 0.06, g + hh + 0.06, yaw, "CF_Concrete")
            if kind == "brick":
                m.obox(cx - HALF, cy - HALF, g + hh, seg + 0.02, th + 0.06, g + hh + 0.08, yaw, "CF_Concrete")
            elif kind in ("wood", "picket", "iron") and i == 0:
                m.obox(ax - HALF, ay - HALF, g - 0.2, 0.1, 0.1, g + hgt + 0.08, yaw, "CF_Wood" if kind == "wood" else "CF_Metal" if kind == "iron" else "CF_Trim")


def build_lot_extras(lot, house, m):
    """Front walk from the sidewalk to the door."""
    if house is None: return
    f = lot["front"]
    x = house["pos"][0] + 0.0
    y_front = lot["front_y"]
    y_door = house["pos"][1] + f * house["size"][1] / 2
    lo, hi = sorted((y_front, y_door))
    h = h_at(x, (lo + hi) / 2)
    m.box(x - 0.6 - HALF, lo - HALF, h - 0.2, x + 0.6 - HALF, hi - HALF, h + 0.06, "CF_Path")


# --- buildings -------------------------------------------------------------------------------
def build_shop(s, m):
    w, d = s["size"][0], s["size"][1]
    fl = s["floors"]
    H = fl * 3.4 + 0.4
    g = s["h"]
    col = hex_col(s["facade"]) if "facade" in s else palette(s["palette"], "facade")
    sub = Mesh()
    sub.box(-w / 2, -d / 2, -0.8, w / 2, d / 2, H, "CF_Facade", col=col, top=False, zb=0.0)
    sub.box(-w / 2, -d / 2, H, w / 2, d / 2, H + 0.1, "CF_RoofFlat")
    for (x0, y0, x1, y1) in ((-w / 2, -d / 2, w / 2, -d / 2 + 0.3), (-w / 2, d / 2 - 0.3, w / 2, d / 2), (-w / 2, -d / 2, -w / 2 + 0.3, d / 2), (w / 2 - 0.3, -d / 2, w / 2, d / 2)):
        sub.box(x0, y0, H, x1, y1, H + 0.9, "CF_Facade", col=col, zb=H + 50.0)
    # storefront: glass bays, sign band, awning
    bays = max(1, int(w // 6))
    for k in range(bays):
        u0 = -w / 2 + 0.5 + (w - 1.0) * k / bays + 0.25
        u1 = -w / 2 + 0.5 + (w - 1.0) * (k + 1) / bays - 0.25
        sub.box(u0, d / 2 - 0.15, 0.25, u1, d / 2 + 0.01, 3.0, "CF_Storefront")
    awn = hex_col(s["awning"]) if "awning" in s else palette(s["palette"], "awning")
    sub.box(-w / 2, d / 2, 3.05, w / 2, d / 2 + 0.25, 3.75, "CF_SignBoard", col=awn)
    sub.poly([(-w / 2 + 0.3, d / 2 + 1.6, 2.6), (w / 2 - 0.3, d / 2 + 1.6, 2.6), (w / 2 - 0.3, d / 2, 3.05), (-w / 2 + 0.3, d / 2, 3.05)], "CF_Awning", col=awn)
    sub.poly([(-w / 2 + 0.3, d / 2 + 1.6, 2.58), (-w / 2 + 0.3, d / 2, 3.03), (w / 2 - 0.3, d / 2, 3.03), (w / 2 - 0.3, d / 2 + 1.6, 2.58)], "CF_Awning", col=awn)
    if w > 14: sub.box(-2.0, -d / 4, H + 0.1, 2.0, d / 4 - 1.0, H + 1.6, "CF_MetalSiding", col=palette(0, "metal"))
    m.append(sub, s["yaw"], (s["pos"][0] - HALF, s["pos"][1] - HALF, g))


def build_tower(t, m, walks):
    ang = math.radians(t["angle"])
    g = t["h"]
    base, ph = t["podium"]
    sub = Mesh()
    sub.box(-base / 2 - 0.5, -base / 2 - 0.5, -0.5, base / 2 + 0.5, base / 2 + 0.5, WALK, "CF_Sidewalk")
    sub.box(-base / 2 + 2, -base / 2 + 2, -0.8, base / 2 - 2, base / 2 - 2, ph, "CF_Facade", col=palette(hash_i(t["id"]) % 8, "facade"), top=False, zb=0.0)
    sub.box(-base / 2 + 2, -base / 2 + 2, ph, base / 2 - 2, base / 2 - 2, ph + 0.15, "CF_RoofFlat")
    for side in range(4):
        f = Mesh()
        f.box(-base / 2 + 2.5, base / 2 - 2.12, 0.25, base / 2 - 2.5, base / 2 - 1.98, 4.0, "CF_Storefront")
        f.box(-base / 2 + 2, base / 2 - 2, 4.0, base / 2 - 2, base / 2 - 0.8, 4.3, "CF_Metal")     # canopy
        sub.append(f, side * math.pi / 2)
    for tw in t["towers"]:
        fp, hgt = tw["footprint"], tw["height"]
        ox, oy = tw["offset"]
        gl = palette(tw["style"], "glass")
        sub.box(ox - fp / 2, oy - fp / 2, ph, ox + fp / 2, oy + fp / 2, hgt, "CF_Curtain", col=gl, top=False, zb=ph)
        sub.box(ox - fp / 2, oy - fp / 2, hgt, ox + fp / 2, oy + fp / 2, hgt + 0.3, "CF_RoofFlat")
        sub.box(ox - fp / 2 - 0.1, oy - fp / 2 - 0.1, hgt, ox + fp / 2 + 0.1, oy + fp / 2 + 0.1, hgt + 1.2, "CF_Facade", col=(0.85, 0.85, 0.85, 1), top=False, zb=hgt + 50.0)
        sub.box(ox - fp / 4, oy - fp / 4, hgt + 0.3, ox + fp / 4, oy + fp / 4, hgt + 3.5, "CF_MetalSiding", col=palette(0, "metal"))
    m.append(sub, ang, (t["pos"][0] - HALF, t["pos"][1] - HALF, g))


def hash_i(s):
    return sum(ord(c) * (k + 1) for k, c in enumerate(s))


def build_warehouse(wh, m):
    w, d, h = wh["size"]
    sub = Mesh()
    col = palette(wh["palette"], "metal")
    sub.box(-w / 2, -d / 2, -0.8, w / 2, d / 2, h, "CF_MetalSiding", col=col, top=False, zb=0.0)
    sub.box(-w / 2, -d / 2, h, w / 2, d / 2, h + 0.2, "CF_RoofFlat")
    for k in range(max(1, int(w // 12))):
        u = -w / 2 + 6 + 12 * k
        sub.box(u - 2, d / 2 - 0.05, 0.0, u + 2, d / 2 + 0.02, 4.2, "CF_Door")
        sub.box(u - 2.5, d / 2, 4.2, u + 2.5, d / 2 + 1.2, 4.4, "CF_Metal")
    sub.box(-w / 2 - 0.5, d / 2, -0.6, w / 2 + 0.5, d / 2 + 14, 0.08, "CF_Parking")
    m.append(sub, wh["yaw"], (wh["pos"][0] - HALF, wh["pos"][1] - HALF, wh["h"]))


PUBLIC_STYLE = {
    "city_hall": dict(floors=4, mat="CF_Stone", col=(0.86, 0.83, 0.76, 1), band="CF_SignBoard", tower=24.0, columns=8),
    "hospital": dict(floors=7, mat="CF_Facade", col=(0.92, 0.92, 0.9, 1), band="CF_SignRed", tower=0.0, columns=0),
    "police": dict(floors=3, mat="CF_Facade", col=(0.7, 0.72, 0.74, 1), band="CF_SignBlue", tower=0.0, columns=0),
    "fire": dict(floors=2, mat="CF_BrickFacade", col=None, band="CF_SignRed", tower=14.0, columns=0),
    "school": dict(floors=2, mat="CF_BrickFacade", col=None, band="CF_SignGreen", tower=0.0, columns=0),
    "library": dict(floors=3, mat="CF_Stone", col=(0.8, 0.76, 0.68, 1), band="CF_SignBoard", tower=0.0, columns=6),
    "community_centre": dict(floors=2, mat="CF_Facade", col=(0.66, 0.5, 0.36, 1), band="CF_SignGreen", tower=0.0, columns=0),
}


def build_public(pb, m):
    st = PUBLIC_STYLE.get(pb["kind"], PUBLIC_STYLE["community_centre"])
    w = min(pb["size"][0], 90.0 if pb["kind"] in ("hospital", "school", "city_hall") else 54.0)
    d = min(pb["size"][1], 30.0)
    H = st["floors"] * 3.8 + 0.6
    sub = Mesh()
    # the forecourt reaches over CityForge's own verge and sidewalk; Mert Road Studio streets have their own, so it
    # stops at the lot line there (3 m in front of the building) instead of lying 1 cm over the new paving
    sub.box(-w / 2 - 3, -d / 2 - 3, -0.5, w / 2 + 3, d / 2 + (3.0 if CITY.get("streets") == "mrs" else 8.0), 0.2, "CF_Sidewalk")
    sub.box(-w / 2, -d / 2, -0.8, w / 2, d / 2, H, st["mat"], col=st["col"], top=False, zb=0.0)
    flat_band = Mesh()
    sub.box(-w / 2, -d / 2, H, w / 2, d / 2, H + 0.2, "CF_RoofFlat")
    sub.box(-w / 2 - 0.2, -d / 2 - 0.2, H - 0.2, w / 2 + 0.2, d / 2 + 0.2, H + 0.9, "CF_Trim" if st["mat"] != "CF_BrickFacade" else "CF_Concrete", top=False)
    sub.box(-w / 2 + 2, d / 2, H - 2.6, w / 2 - 2, d / 2 + 0.3, H - 1.0, st["band"])   # name band
    # storefront-glass ground floor along the front
    sub.box(-w / 2 + 2, d / 2 - 0.15, 0.3, w / 2 - 2, d / 2 + 0.01, 3.2, "CF_Storefront")
    if st["columns"]:
        sub.box(-w / 4, d / 2, H - 1.2, w / 4, d / 2 + 4.0, H - 0.4, "CF_Stone", col=st["col"])
        for k in range(st["columns"]):
            x = -w / 4 + 0.8 + (w / 2 - 1.6) * k / (st["columns"] - 1)
            sub.cylinder(x, d / 2 + 3.2, 0.2, H - 1.2, 0.45, 0.4, "CF_Stone", 10)
        for k in range(3):
            sub.box(-w / 4, d / 2 + 4.0 + k * 0.4, 0.2 - (k + 1) * 0.17, w / 4, d / 2 + 4.4 + k * 0.4, 0.2 - k * 0.17, "CF_Stone", col=st["col"])
    else:
        sub.box(-4, d / 2, 3.4, 4, d / 2 + 3.5, 3.7, "CF_Metal")                         # entrance canopy
    if pb["kind"] == "fire":
        for k in range(3):
            x = -w / 2 + 5 + k * 5.2
            sub.box(x - 2.0, d / 2 - 0.05, 0.0, x + 2.0, d / 2 + 0.02, 4.4, "CF_FireDoor")
        sub.box(-w / 2 - 0.5, d / 2, -0.5, -w / 2 + 16, d / 2 + 12, 0.12, "CF_Concrete")
    if pb["kind"] == "hospital":
        for x in (-w / 2 + 4, w / 2 - 4):
            sub.box(x - 1.5, d / 2 + 0.05, H - 5.0, x + 1.5, d / 2 + 0.25, H - 4.2, "CF_SignRed")
            sub.box(x - 0.4, d / 2 + 0.05, H - 6.1, x + 0.4, d / 2 + 0.25, H - 3.1, "CF_SignRed")
    if st["tower"]:
        tx = 0.0 if pb["kind"] == "city_hall" else w / 2 - 3
        sub.box(tx - 3, -3, H, tx + 3, 3, H + st["tower"], st["mat"], col=st["col"], top=False, zb=0.0)
        hip_m = Mesh()
        kit.hip(hip_m, tx - 3, tx + 3, -3, 3, H + st["tower"], 4.0, 0.3)
        sub.append(hip_m)
        if pb["kind"] == "city_hall":
            for yaw in range(4):
                c = Mesh()
                c.cylinder(0, 3.05, H + st["tower"] - 4, H + st["tower"] - 4, 1.6, 1.6, "CF_SignWhite", 12)
                c2 = Mesh()
                for k in range(12):
                    a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
                    c2.poly([(0, 3.06, H + st["tower"] - 4), (1.6 * math.cos(a1), 3.06, H + st["tower"] - 4 + 1.6 * math.sin(a1)), (1.6 * math.cos(a0), 3.06, H + st["tower"] - 4 + 1.6 * math.sin(a0))], "CF_SignWhite")
                sub.append(c2, yaw * math.pi / 2, (tx, 0, 0))
    m.append(sub, pb["yaw"], (pb["pos"][0] - HALF, pb["pos"][1] - HALF, pb["h"]))


def build_parking_behind_shops(s, m):
    pass


# --- far LOD: every repeated model merged per chunk (LOD1), tinted by vertex colour ------------
KIT = kit.build_all()
# the house catalogue's LOD1 meshes (tools/cityforge/houses.py) for the merged far meshes
HOUSE_LOD1 = {}
_lod1_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "cityforge", "houses_lod1.json")
if os.path.exists(_lod1_path):
    for hid, g in json.load(open(_lod1_path)).items():
        hm = Mesh()
        for f, mname in zip(g["f"], g["m"]):
            hm.poly([g["v"][i] for i in f], mname)
        HOUSE_LOD1["H_" + hid] = hm
PAL = CITY["palettes"]
TREE_NAMES = [t[0] for t in kit.TREES]
TINTED = {"CF_Siding": "CF_SidingV", "CF_Roof": "CF_RoofV", "CF_Leaves": "CF_LeavesV", "CF_RoofSeam": "CF_RoofSeamV",
          "CF_Stucco": "CF_Stucco", "CF_Plaster": "CF_Plaster", "CF_BrickPainted": "CF_BrickPainted"}
TINT_ROLE = {"CF_SidingV": "wall", "CF_Stucco": "wall", "CF_Plaster": "wall", "CF_BrickPainted": "wall", "CF_RoofV": "roof",
             "CF_RoofSeamV": "roof", "CF_LeavesV": "leaves"}


def hex_col(h):
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0, 1.0)


def pick(lst, k):
    """Same choice as world/cityforge/cityforge_world.gd (index-based, no RNG)."""
    return lst[(k * 7919) % len(lst)]


def tree_scale(k):
    return 0.85 + 0.3 * ((k * 0.6180339) % 1.0)


def place_far(far, name, yaw, x, y, h, scale=(1.0, 1.0, 1.0), siding=None, roof=None, leaves=None):
    first = len(far.f)
    src = HOUSE_LOD1[name] if name in HOUSE_LOD1 else KIT[name][-1]     # the coarsest LOD there is
    far.append(src, yaw, (x - HALF, y - HALF, h), scale)
    tint = {"wall": siding, "roof": roof, "leaves": leaves}
    for fi in range(first, len(far.f)):
        idx, mat, uv, col, zb = far.f[fi]
        if mat in TINTED:
            mat = TINTED[mat]
            far.f[fi] = (idx, mat, uv, tint[TINT_ROLE[mat]] or (1.0, 1.0, 1.0, 1.0), zb)


def build_far(M):
    for hs in CITY["houses"]:
        if "kit" in hs and hs["kit"] in HOUSE_LOD1:
            place_far(M(chunk_of(*hs["pos"]), "Far"), hs["kit"], hs["yaw"], hs["pos"][0], hs["pos"][1], hs["h"], (1.0, 1.0, 1.0),
                      hex_col(hs["tint"]), hex_col(hs["roof_tint"]))
            continue
        sx, sy = hs["size"][0] / kit.HOUSE_W, hs["size"][1] / kit.HOUSE_D
        place_far(M(chunk_of(*hs["pos"]), "Far"), "house_" + hs["archetype"], hs["yaw"], hs["pos"][0], hs["pos"][1], hs["h"], (sx, sy, 1.0),
                  hex_col(PAL["siding"][hs["siding"] % len(PAL["siding"])]), hex_col(PAL["roof"][hs["roof"] % len(PAL["roof"])]))
    for g in CITY["garages"]:
        place_far(M(chunk_of(*g["pos"]), "Far"), "garage", g["yaw"], g["pos"][0], g["pos"][1], g["h"], (1.0, 1.0, 1.0),
                  hex_col(PAL["siding"][g["siding"] % len(PAL["siding"])]), hex_col(PAL["roof"][g["roof"] % len(PAL["roof"])]))
    for k, t in enumerate(CITY["props"]["tree"]):
        s = tree_scale(k)
        place_far(M(chunk_of(t[0], t[1]), "Far"), TREE_NAMES[t[4]], t[3], t[0], t[1], t[2], (s, s, s), leaves=hex_col(pick(PAL["leaves"][t[4]], k)))


# --- outskirts: land and sea beyond the city square, to the horizon ---------------------------
def edge_height(x, y):
    """Outskirt ground height: the city edge carried outwards, rising into hills inland."""
    cx, cy = min(max(x, 0.0), SIZE), min(max(y, 0.0), SIZE)
    d = math.hypot(x - cx, y - cy)
    sx, sy = min(max(x, 12.0), SIZE - 12.0), min(max(y, 12.0), SIZE - 12.0)    # sample just inside the edge
    h0 = h_at(sx, sy)
    cx, cy = sx, sy
    if wet(cx, cy) or h0 < 0.5:
        return min(h0, 0.0) - 2.0 - d * 0.02 if d > 0 else h0
    hills = 18.0 * (0.5 + 0.5 * math.sin(x * 0.0021 + 1.3) * math.cos(y * 0.0017 + 0.4)) + 9.0 * math.sin(x * 0.0063 + y * 0.0049)
    rise = min(d / 900.0, 1.0)
    return h0 + rise * (60.0 + hills + d * 0.035) * (0.4 + 0.6 * rise)


def build_outskirts():
    m = Mesh()
    step, reach = 64.0, 4800.0
    xs = np.arange(-reach, SIZE + reach + 1, step)
    H = np.array([[edge_height(x, y) for x in xs] for y in xs])
    for j in range(len(xs) - 1):
        for i in range(len(xs) - 1):
            x0, x1, y0, y1 = xs[i], xs[i + 1], xs[j], xs[j + 1]
            if x0 >= 0 and x1 <= SIZE and y0 >= 0 and y1 <= SIZE: continue      # the city has its own ground
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            pts = []
            cols = []
            for a, b in q:
                x, y = float(xs[a]), float(xs[b])
                # snap the ring's inner edge onto the city edge so the two grounds meet
                if 0 <= x <= SIZE and 0 <= y <= SIZE: z = h_at(x, y)
                else: z = float(H[b, a])
                pts.append(B(x, y, z))
                slope = abs(float(H[min(b + 1, len(xs) - 1), a] - H[max(b - 1, 0), a])) / (2 * step)
                cols.append((0.0, 1.0 if z < 0.8 else 0.0, min(max((slope - 0.35) * 3.0, 0.0), 1.0), 0.0 if z < 0.0 else 1.0))
            m.poly(pts, "CF_Terrain", col=cols)
    sea = Mesh()
    r = reach + 3000.0
    sea.poly([B(-r, -r, 0.0), B(SIZE + r, -r, 0.0), B(SIZE + r, SIZE + r, 0.0), B(-r, SIZE + r, 0.0)], "CF_Water")
    return m, sea


# --- assembly --------------------------------------------------------------------------------
def collect():
    """Everything per chunk: chunk -> {part: Mesh}."""
    parts = {}
    def M(c, part):
        return parts.setdefault(c, {}).setdefault(part, Mesh())
    # streets = "mrs": Mert Road Studio built the roads, junctions, sidewalks, lanes and bridges
    # (tools/cityforge/mrs_streets.py -> assets/cityforge/mrs); CityForge keeps lots, buildings, ground
    own_streets = CITY.get("streets", "cityforge") != "mrs"
    for r in CITY["roads"] if own_streets else ():
        a, b = NODES[r["a"]]["pos"], NODES[r["b"]]["pos"]
        c = chunk_of((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        build_road(r, M(c, "Roads"), M(c, "Walks"))
    for nid, poly in PATCHES.items() if own_streets else ():
        c = chunk_of(*NODES[nid]["pos"])
        build_patch(nid, M(c, "Roads"))
    for nid, quad in CORNERS if own_streets else ():
        c = chunk_of(*NODES[nid]["pos"])
        build_corner(quad, M(c, "Walks"))
    for ln in CITY["lanes"] if own_streets else ():
        c = chunk_of((ln["a"][0] + ln["b"][0]) / 2, ln["a"][1])
        build_lane(ln, M(c, "Roads"))
    houses = {h["lot"]: h for h in CITY["houses"]}
    for lot in CITY["lots"]:
        x0, y0, x1, y1 = lot["rect"]
        c = chunk_of((x0 + x1) / 2, (y0 + y1) / 2)
        build_lot_extras(lot, houses.get(lot["id"]), M(c, "Walks"))
    for fc in CITY["fences"]:
        if not fc["segments"]: continue
        s = fc["segments"][0]
        build_fence(fc, M(chunk_of(s[0], s[1]), "Fences"))
    for s in CITY["shops"]: build_shop(s, M(chunk_of(*s["pos"]), "Buildings"))
    for t in CITY["towers"]: build_tower(t, M(chunk_of(*t["pos"]), "Buildings"), None)
    for wh in CITY["warehouses"]: build_warehouse(wh, M(chunk_of(*wh["pos"]), "Buildings"))
    for pb in CITY["public"]: build_public(pb, M(chunk_of(*pb["pos"]), "Buildings"))
    for pz in CITY["plazas"]:
        sub = Mesh()
        sz = pz["size"]
        sub.box(-sz / 2, -sz / 2, -0.5, sz / 2, sz / 2, WALK, "CF_Sidewalk")
        sub.cylinder(0, 0, WALK, 0.8, 4.0, 4.0, "CF_Stone", 16)
        sub.cylinder(0, 0, 0.8, 0.85, 3.6, 3.6, "CF_Water", 16)
        h = h_at(*pz["pos"])
        M(chunk_of(*pz["pos"]), "Buildings").append(sub, math.radians(pz["angle"]), (pz["pos"][0] - HALF, pz["pos"][1] - HALF, h))
    build_far(M)
    for ci in range(NCH):
        for cj in range(NCH):
            build_terrain(ci, cj, M((ci, cj), "Terrain"))
            build_water(ci, cj, M((ci, cj), "Water"))
    return parts


def export_glb(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
              export_materials="EXPORT", export_normals=True, export_texcoords=True)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    if "export_vertex_color" in props: kw["export_vertex_color"] = "ACTIVE"
    elif "export_colors" in props: kw["export_colors"] = True
    if "export_all_vertex_colors" in props: kw["export_all_vertex_colors"] = True
    if "export_extras" in props: kw["export_extras"] = True
    bpy.ops.export_scene.gltf(**kw)


def main():
    for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
    os.makedirs(os.path.join(OUT, "chunks"), exist_ok=True)
    scene = bpy.context.scene
    stats = {}
    want = opt("--chunks")
    want = None if want is None else {tuple(int(v) for v in s.split("_")) for s in want.split(",")}
    export = "--no-export" not in opts
    if "--no-kit" not in opts:
        col = bpy.data.collections.new("CF_Kit")
        scene.collection.children.link(col)
        objs = []
        for k, (name, lods) in enumerate(KIT.items()):
            m0, m1 = lods[0], lods[1]
            for suffix, m in (("", m0), ("_LOD1", m1)):
                ob = to_object(m, name + suffix, MATS, weld=True)
                ob.location = (k * 16.0 - 160.0, -HALF - 80.0 - (30.0 if suffix else 0.0), 0.0)
                col.objects.link(ob)
                objs.append(ob)
            stats[name] = [m0.tris(), m1.tris()]
        if export:
            # the kit is exported with every object at the origin
            locs = [o.location.copy() for o in objs]
            for o in objs: o.location = (0, 0, 0)
            bpy.context.view_layer.update()
            export_glb(os.path.join(OUT, "kit.glb"), objs)
            for o, l in zip(objs, locs): o.location = l
    parts = collect()
    root = bpy.data.collections.new("CF_City")
    scene.collection.children.link(root)
    total = 0
    for (ci, cj), pm in sorted(parts.items()):
        if want is not None and (ci, cj) not in want: continue
        col = bpy.data.collections.new("chunk_%d_%d" % (ci, cj))
        root.children.link(col)
        objs = []
        for part, m in pm.items():
            if not m.f: continue
            ob = to_object(m, "%s_%d_%d" % (part, ci, cj), MATS, smooth=(part in ("Terrain", "Water")), weld=(part in ("Terrain", "Water", "Far")),
                           uvs=part in ("Roads", "Buildings", "Fences"))
            col.objects.link(ob)
            objs.append(ob)
            total += m.tris()
        if export and objs:
            bpy.context.view_layer.update()
            export_glb(os.path.join(OUT, "chunks", "c_%d_%d.glb" % (ci, cj)), objs)
    stats["chunk_tris_total"] = total
    land, sea = build_outskirts()
    col = bpy.data.collections.new("outskirts")
    root.children.link(col)
    objs = [to_object(land, "Outskirts", MATS, smooth=True, weld=True, uvs=False), to_object(sea, "Sea", MATS, uvs=False)]
    for o in objs: col.objects.link(o)
    stats["outskirts_tris"] = land.tris()
    if export:
        bpy.context.view_layer.update()
        export_glb(os.path.join(OUT, "outskirts.glb"), objs)
    blend = opt("--blend")
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("BUILD", json.dumps(stats))


main()
