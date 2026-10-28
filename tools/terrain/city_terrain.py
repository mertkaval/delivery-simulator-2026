"""City terrain generator: the ground a city is planned on.

    blender --background --factory-startup --python tools/terrain/city_terrain.py -- <terrain.json> <out_dir> [norender]

From a small JSON description (size, seed, hills, basins, lakes, an optional sea edge) it builds a
heightmap with believable relief and real water: lakes fill their basins up to the spill level,
rivers follow the drainage downhill (priority-flood + D8 flow accumulation) and are carved into the
ground, thermal erosion softens the slopes. Outputs, for the road planner and the game:
  height_16.png    16-bit heightmap (0 = min_height, 65535 = max_height in meta.json)
  water.png        lakes, rivers and sea (white)          slope.png   slope in degrees x 4
  buildable.png    flat (< max_build_slope) dry land       meta.json   sizes, heights, levels, rivers
  terrain.blend    the terrain mesh coloured by ground type with water surfaces (and renders)
Everything is numpy (bundled with Blender); the same JSON and seed always give the same land.
"""
import bpy, bmesh, sys, os, json, math, heapq, time
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SPEC = json.load(open(argv[0])) if argv else {}
OUT = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
RENDER = "norender" not in argv
os.makedirs(OUT, exist_ok=True)

SIZE = float(SPEC.get("size_m", 2048))        # square side, metres
CELL = float(SPEC.get("cell_m", 4))           # grid spacing, metres
N = int(SIZE / CELL) + 1
SEED = int(SPEC.get("seed", 1))
rng = np.random.default_rng(SEED)
xs = np.linspace(0, SIZE, N)
X, Y = np.meshgrid(xs, xs)                     # Y rows: 0 = south edge


def lattice_noise(freq, seed_offset):
    """Smooth value noise in [-1, 1] at `freq` cells across the map (quintic interpolation)."""
    g = np.random.default_rng(SEED * 7919 + seed_offset).uniform(-1, 1, (freq + 2, freq + 2))
    u = X / SIZE * freq
    v = Y / SIZE * freq
    i = np.floor(u).astype(int)
    j = np.floor(v).astype(int)
    fu = u - i
    fv = v - j
    fu = fu * fu * fu * (fu * (fu * 6 - 15) + 10)
    fv = fv * fv * fv * (fv * (fv * 6 - 15) + 10)
    a = g[j, i]; b = g[j, i + 1]; c = g[j + 1, i]; d = g[j + 1, i + 1]
    return (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv


def fbm(base_freq, octaves, seed_offset, ridged=False):
    total = np.zeros_like(X)
    amp, freq, norm = 1.0, base_freq, 0.0
    for o in range(octaves):
        n = lattice_noise(int(freq), seed_offset + o * 31)
        if ridged:
            n = 1.0 - np.abs(n)
            n = n * n
        total += n * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm


def falloff(cx, cy, radius, power=2.0):
    d = np.hypot(X - cx, Y - cy) / max(radius, 1.0)
    return np.clip(1.0 - d, 0.0, 1.0) ** power


def shifted(a, dy, dx):
    """a moved by (dy, dx) cells with the edges repeated (np.roll would wrap north onto south)."""
    w = max(abs(dy), abs(dx), 1)
    p = np.pad(a, w, mode="edge")
    return p[w - dy:w - dy + a.shape[0], w - dx:w - dx + a.shape[1]]


t0 = time.time()
# --- relief ----------------------------------------------------------------------------------
H = np.full_like(X, float(SPEC.get("base_height", 12.0)))
H += fbm(4, 6, 1) * float(SPEC.get("rolling", 6.0))                       # gentle rolling ground
warp_x = fbm(3, 3, 50) * SIZE * 0.06
warp_y = fbm(3, 3, 60) * SIZE * 0.06
for k, hill in enumerate(SPEC.get("hills", [])):                          # [x, y, radius, height, ridged 0/1]
    cx, cy, r, h = hill[:4]
    ridged = bool(hill[4]) if len(hill) > 4 else True
    shape = falloff(cx + warp_x, cy + warp_y, r, 1.6)
    detail = 0.45 + 0.55 * fbm(5, 6, 100 + k * 17, ridged=ridged)
    H += shape * detail * h
for k, basin in enumerate(SPEC.get("basins", [])):                        # [x, y, radius, depth]: lowlands
    cx, cy, r, depth = basin
    H -= falloff(cx + warp_x * 0.5, cy + warp_y * 0.5, r, 1.2) * depth


def irregular(cx, cy, r, k):
    """0..1 inside an irregular blob of radius ~r (wobbly, warped shoreline)."""
    ang = np.arctan2(Y - cy, X - cx)
    wob = 1.0 + 0.22 * np.sin(3 * ang + k) + 0.12 * np.sin(5 * ang + 2 * k) + 0.25 * fbm(6, 3, 300 + k * 13)
    d = np.hypot(X - cx + warp_x * 0.4, Y - cy + warp_y * 0.4) / (r * wob)
    return np.clip(1.0 - d, 0.0, 1.0)


for k, lk in enumerate(SPEC.get("lakes", [])):                            # [x, y, radius, depth]: a lake with its rim
    cx, cy, r, depth = lk
    inner = irregular(cx, cy, r, k)
    H -= np.sqrt(inner) * depth                                            # bowl, steeper near the shore
    rim = irregular(cx, cy, r * 1.35, k) * (1 - inner)
    H += np.where(inner <= 0, rim ** 0.7 * depth * 0.18, 0.0)               # a low rim keeps the water in
sea = SPEC.get("sea")                                                      # {"edge": "south"|"north"|"east"|"west", "width": m, "tilt_m": m}
if sea:
    edge, width = sea["edge"], float(sea.get("width", 300))
    dist = {"south": Y, "north": SIZE - Y, "west": X, "east": SIZE - X}[edge]
    # land rises gently away from the coast, so rivers and lake outlets run to the sea
    H += dist / SIZE * float(sea.get("tilt_m", 25.0))

    shore = width * (1.0 + 0.35 * fbm(3, 4, 200))
    H = np.where(dist < shore, H - (1.0 - dist / shore) ** 1.5 * (H + 8.0), H)


def poly_mask(poly):
    """Cells inside a polygon [[x, y], ...] (metres), even-odd rule."""
    inside = np.zeros(X.shape, bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        if y1 == y2: continue
        cond = (Y >= min(y1, y2)) & (Y < max(y1, y2))
        xint = x1 + (Y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (X < xint)
    return inside


def distance_from(mask, max_cells):
    """Approximate distance (cells) from the mask, up to max_cells (chamfer, 8-neighbour)."""
    d = np.where(mask, 0.0, max_cells)
    for _ in range(max_cells):
        nd = d
        for dy, dx, w in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
            nd = np.minimum(nd, shifted(d, dy, dx) + w)
        if np.array_equal(nd, d): break
        d = nd
    return d


# Authored water and land (fictional city maps): sea / bay / inlet polygons with beaches, land that
# must stay above water (a peninsula), and rivers along a drawn path to the sea.
SEA_POLY = np.zeros(X.shape, bool)
for poly in SPEC.get("sea_areas", []):
    SEA_POLY |= poly_mask(poly)
if SEA_POLY.any():
    shore_m = float(SPEC.get("beach_m", 36.0))
    d_out = distance_from(SEA_POLY, int(shore_m / CELL) + 1) * CELL
    d_in = distance_from(~SEA_POLY, 12) * CELL
    H = np.where(SEA_POLY, -1.5 - np.minimum(d_in, 40.0) * 0.18 + fbm(8, 2, 400) * 0.6, H)
    t = np.clip(d_out / shore_m, 0, 1)
    t = t * t * (3 - 2 * t)
    H = np.where(~SEA_POLY & (d_out < shore_m), 0.8 + (H - 0.8) * t, H)
    sea = sea or {"edge": None}
for poly in SPEC.get("land_areas", []):
    H = np.where(poly_mask(poly) & ~SEA_POLY, np.maximum(H, float(SPEC.get("land_min_m", 2.5))), H)
RIVER_PATH = np.zeros(X.shape, bool)
river_bed = np.full(X.shape, np.inf)
for rv in SPEC.get("rivers", []):                                          # {"path": [[x, y], ...] source -> mouth, "width": m, "depth": m}
    pts = np.array(rv["path"], float)
    w2 = float(rv.get("width", 40)) / 2
    depth_m = float(rv.get("depth", 5))
    seg_len = np.hypot(*(pts[1:] - pts[:-1]).T)
    cum = np.concatenate([[0], np.cumsum(seg_len)])
    best_d = np.full(X.shape, np.inf)
    best_s = np.zeros(X.shape)
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        ab = b - a
        tt = np.clip(((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / max(ab @ ab, 1e-9), 0, 1)
        dd = np.hypot(X - (a[0] + ab[0] * tt), Y - (a[1] + ab[1] * tt))
        closer = dd < best_d
        best_d = np.where(closer, dd, best_d)
        best_s = np.where(closer, cum[k] + tt * seg_len[k], best_s)
    j0, i0 = int(np.clip(pts[0][1] / CELL, 0, N - 1)), int(np.clip(pts[0][0] / CELL, 0, N - 1))
    top = float(H[j0, i0]) - depth_m
    bed = top + (-2.5 - top) * (best_s / cum[-1])                         # falls steadily to the mouth
    bank = float(rv.get("bank_m", 30))
    H = np.where(best_d < w2, np.minimum(H, bed), H)
    H = np.where((best_d >= w2) & (best_d < w2 + bank), np.minimum(H, bed + depth_m * 0.6 + (best_d - w2) * 0.22), H)
    RIVER_PATH |= best_d < w2
    river_bed = np.where(best_d < w2, np.minimum(river_bed, bed), river_bed)

# --- thermal erosion: material slides off slopes steeper than the talus angle ----------------
talus = math.tan(math.radians(float(SPEC.get("talus_deg", 33)))) * CELL
for it in range(int(SPEC.get("thermal_iterations", 40))):
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        diff = H - shifted(H, dy, dx) - talus
        move = np.where(diff > 0, diff * 0.25, 0.0)
        H -= move
        H += shifted(move, -dy, -dx)

SEA_LEVEL = 0.0 if sea else -1e9


def coast_sea():
    """Ground below sea level that is connected to the coast edge (inland pits are not sea)."""
    if not sea: return np.zeros(H.shape, bool)
    low = H < SEA_LEVEL
    out = np.zeros(H.shape, bool)
    seeds = SEA_POLY.copy()
    if sea.get("edge"):
        edge_cells = {"south": (0, slice(None)), "north": (N - 1, slice(None)), "west": (slice(None), 0), "east": (slice(None), N - 1)}[sea["edge"]]
        seeds[edge_cells] = True
    stack = list(zip(*np.nonzero(seeds & low)))
    for j, i in stack: out[j, i] = True
    while stack:
        j, i = stack.pop()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nj, ni = j + dj, i + di
            if 0 <= nj < N and 0 <= ni < N and low[nj, ni] and not out[nj, ni]:
                out[nj, ni] = True; stack.append((nj, ni))
    return out


SEA = coast_sea()


# --- hydrology: priority flood (lakes fill to their spill level) + D8 flow accumulation ------
def priority_flood(h):
    """Filled surface: every cell drains to the map edge (or the sea) without going uphill."""
    filled = h.copy()
    done = np.zeros(h.shape, bool)
    heap = []
    if sea:
        # with a coast, the sea is the only outlet: every basin drains to it
        for j, i in zip(*np.nonzero(SEA)):
            heapq.heappush(heap, (filled[j, i], j, i)); done[j, i] = True
    else:
        for j in range(N):
            for i in (0, N - 1):
                heapq.heappush(heap, (filled[j, i], j, i)); done[j, i] = True
        for i in range(1, N - 1):
            for j in (0, N - 1):
                heapq.heappush(heap, (filled[j, i], j, i)); done[j, i] = True
    while heap:
        z, j, i = heapq.heappop(heap)
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nj, ni = j + dj, i + di
            if 0 <= nj < N and 0 <= ni < N and not done[nj, ni]:
                done[nj, ni] = True
                if filled[nj, ni] < z + 1e-4:
                    filled[nj, ni] = z + 1e-4
                heapq.heappush(heap, (filled[nj, ni], nj, ni))
    return filled


filled = priority_flood(H)
depth = filled - H
# small puddles are not lakes: fill them in (lakes need area and depth)
lake = depth > float(SPEC.get("min_lake_depth", 1.0))
lake_cells_min = int(float(SPEC.get("min_lake_area_m2", 20000)) / (CELL * CELL))


def label(mask):
    lab = np.zeros(mask.shape, np.int32)
    n = 0
    for j, i in zip(*np.nonzero(mask)):
        if lab[j, i]: continue
        n += 1
        stack = [(j, i)]; lab[j, i] = n
        while stack:
            cj, ci = stack.pop()
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nj, ni = cj + dj, ci + di
                if 0 <= nj < N and 0 <= ni < N and mask[nj, ni] and not lab[nj, ni]:
                    lab[nj, ni] = n; stack.append((nj, ni))
    return lab, n


lab, nlakes = label(depth > 0.05)
lakes = []
lake_mask = np.zeros(H.shape, bool)
for k in range(1, nlakes + 1):
    cells = lab == k
    area = int(cells.sum())
    if area >= lake_cells_min and depth[cells].max() > float(SPEC.get("min_lake_depth", 1.0)):
        lake_mask |= cells
        lakes.append({"id": len(lakes), "level": round(float(filled[cells].mean()), 2), "area_m2": area * CELL * CELL,
                      "max_depth": round(float(depth[cells].max()), 1), "centre": [round(float(X[cells].mean())), round(float(Y[cells].mean()))]})
    else:
        H[cells] = filled[cells]                               # puddle: raise the ground instead

# D8 flow on the filled surface
NB = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
DIST = (1, 1, 1, 1, math.sqrt(2), math.sqrt(2), math.sqrt(2), math.sqrt(2))
order = np.argsort(-filled, axis=None)
down = np.full(N * N, -1, np.int64)
flat_f = filled.ravel()
for idx in order:
    j, i = divmod(int(idx), N)
    best, best_drop = -1, 0.0
    for (dj, di), dd in zip(NB, DIST):
        nj, ni = j + dj, i + di
        if 0 <= nj < N and 0 <= ni < N:
            drop = (flat_f[idx] - flat_f[nj * N + ni]) / dd
            if drop > best_drop:
                best_drop, best = drop, nj * N + ni
    down[idx] = best
acc = np.ones(N * N)
for idx in order:
    d = down[idx]
    if d >= 0: acc[d] += acc[idx]
acc = acc.reshape(N, N)
catch_m2 = acc * CELL * CELL
river_min = float(SPEC.get("river_catchment_km2", 0.35)) * 1e6
river = (catch_m2 > river_min) & ~lake_mask & ~SEA

# carve the channels: deeper and wider downstream
strength = np.clip(np.log10(np.maximum(catch_m2 / river_min, 1.0)) + 0.5, 0.5, 3.0)
carve = np.where(river, 1.2 * strength + 0.8, 0.0)
for _ in range(2):                                             # widen the banks
    carve = np.maximum(carve, 0.55 * np.maximum.reduce([shifted(carve, dy, dx) for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))]))
H -= carve
river_wide = (carve > 0.6) | RIVER_PATH
water_level = np.where(lake_mask, filled, H + np.where(river_wide, np.minimum(carve * 0.7, 2.5), 0.0))
water_level = np.where(RIVER_PATH, np.maximum(np.minimum(river_bed, H) + float(SPEC.get("river_water_depth", 3.0)), SEA_LEVEL if sea else -1e9), water_level)
water = lake_mask | river_wide | SEA

# river polylines (for the road planner): trace from each source down to a lake, the sea or the edge
rivers = []
heads = [int(j * N + i) for j, i in zip(*np.nonzero(river)) if not any(
    0 <= j + dj < N and 0 <= i + di < N and river[j + dj, i + di] and down[(j + dj) * N + (i + di)] == j * N + i for dj, di in NB)]
seen = set()
for h0 in sorted(heads, key=lambda c: -catch_m2.ravel()[c])[:60]:
    line, c = [], h0
    while c >= 0 and c not in seen:
        j, i = divmod(c, N)
        line.append([round(float(X[j, i]), 1), round(float(Y[j, i]), 1)])
        seen.add(c)
        if lake_mask[j, i] or SEA[j, i]: break
        c = int(down[c])
    if len(line) > 8: rivers.append(line[::2])

# masks
gy, gx = np.gradient(H, CELL)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
buildable = (slope < float(SPEC.get("max_build_slope", 8.0))) & ~water
hmin, hmax = float(H.min()), float(H.max())
print("TERRAIN %dx%d cells (%.0f m, %.0f m spacing) height %.1f..%.1f m, %d lakes, %d rivers, water %.1f%%, buildable %.1f%%, %.1f s" % (
    N, N, SIZE, CELL, hmin, hmax, len(lakes), len(rivers), water.mean() * 100, buildable.mean() * 100, time.time() - t0))


def write_png16(path, arr01):
    """Greyscale 16-bit PNG, row 0 = north (image top)."""
    import zlib, struct
    a = (np.clip(arr01, 0, 1) * 65535 + 0.5).astype(">u2")[::-1]
    raw = b"".join(bytes(1) + row.tobytes() for row in a)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    hdr = struct.pack(">IIBBBBB", a.shape[1], a.shape[0], 16, 0, 0, 0, 0)
    signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    open(path, "wb").write(signature + chunk(b"IHDR", hdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def save_png(name, arr01, depth16=False):
    if depth16:
        write_png16(os.path.join(OUT, name + ".png"), arr01)
        return
    img = bpy.data.images.new(name, N, N, alpha=False, float_buffer=depth16)
    rgba = np.repeat(np.clip(arr01, 0, 1)[:, :, None], 4, 2).astype(np.float32)
    rgba[..., 3] = 1.0
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(OUT, name + ".png")
    img.file_format = "PNG"
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "BW"
    sc.render.image_settings.color_depth = "16" if depth16 else "8"
    img.save_render(img.filepath_raw, scene=sc)


save_png("height_16", (H - hmin) / max(hmax - hmin, 1e-6), True)
save_png("water", water.astype(float))
save_png("slope", np.clip(slope / 64.0, 0, 1))
save_png("buildable", buildable.astype(float))
# planning map: hillshade + elevation tint + 10 m contours + water + rivers (north up)
nx, ny = -gx, -gy
light = np.array([-0.6, 0.6, 0.75]); light /= np.linalg.norm(light)
shade = np.clip((nx * light[0] + ny * light[1] + light[2]) / np.sqrt(nx * nx + ny * ny + 1.0), 0, 1)
e = (H - max(hmin, 0.0)) / max(hmax - max(hmin, 0.0), 1e-6)
low = np.array([0.55, 0.68, 0.45]); mid = np.array([0.80, 0.76, 0.55]); high = np.array([0.66, 0.58, 0.50])
tint = np.where(e[..., None] < 0.5, low + (mid - low) * (e[..., None] / 0.5), mid + (high - mid) * ((e[..., None] - 0.5) / 0.5))
rgb = tint * (0.45 + 0.65 * shade[..., None])
contour = (np.floor(H / 10.0) != np.floor(shifted(H, 1, 0) / 10.0)) | (np.floor(H / 10.0) != np.floor(shifted(H, 0, 1) / 10.0))
rgb = np.where(contour[..., None], rgb * 0.72, rgb)
rgb = np.where(water[..., None], np.array([0.30, 0.55, 0.80]), rgb)
rgb = np.where(river[..., None], np.array([0.20, 0.45, 0.85]), rgb)
rgb = np.where((~buildable & ~water)[..., None], rgb * np.array([1.0, 0.92, 0.88]), rgb)
pm = bpy.data.images.new("plan_map", N, N, alpha=False)
pm.pixels.foreach_set(np.concatenate([np.clip(rgb, 0, 1) ** 2.2, np.ones((N, N, 1))], 2).astype(np.float32).ravel())
pm.filepath_raw = os.path.join(OUT, "plan_map.png"); pm.file_format = "PNG"
sc_ = bpy.context.scene
sc_.render.image_settings.file_format = "PNG"; sc_.render.image_settings.color_mode = "RGB"; sc_.render.image_settings.color_depth = "8"
pm.save_render(pm.filepath_raw, scene=sc_)
meta = {"size_m": SIZE, "cell_m": CELL, "grid": N, "min_height": hmin, "max_height": hmax, "sea_level": SEA_LEVEL if sea else None,
        "seed": SEED, "lakes": lakes, "rivers": rivers, "spec": SPEC,
        "water_fraction": float(water.mean()), "buildable_fraction": float(buildable.mean())}
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
# raw arrays for the city planner (row 0 = south, x east; metres)
np.savez_compressed(os.path.join(OUT, "terrain.npz"), height=H.astype(np.float32), water=water, water_level=water_level.astype(np.float32),
                    slope=slope.astype(np.float32), sea=SEA, lake=lake_mask, river=river_wide)

# --- Blender: terrain mesh coloured by ground type, water surfaces ---------------------------
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
STEP = max(1, N // 257)                                        # mesh at <= 257 x 257 for viewing
idx = np.arange(0, N, STEP)
sub = H[np.ix_(idx, idx)]
M = len(idx)
me = bpy.data.meshes.new("CityTerrain")
verts = np.stack([X[np.ix_(idx, idx)].ravel() - SIZE / 2, Y[np.ix_(idx, idx)].ravel() - SIZE / 2, sub.ravel()], 1)
faces = [(j * M + i, j * M + i + 1, (j + 1) * M + i + 1, (j + 1) * M + i) for j in range(M - 1) for i in range(M - 1)]
me.from_pydata(verts.tolist(), [], faces)
me.shade_smooth() if hasattr(me, "shade_smooth") else None
col = me.color_attributes.new("Ground", "BYTE_COLOR", "POINT")
s_sub = slope[np.ix_(idx, idx)].ravel()
w_sub = water[np.ix_(idx, idx)].ravel()
h_sub = sub.ravel()
grass = np.array([0.30, 0.42, 0.20]); dry = np.array([0.52, 0.50, 0.32]); rock = np.array([0.42, 0.40, 0.38]); sand = np.array([0.72, 0.66, 0.50]); bed = np.array([0.30, 0.28, 0.22])
t_slope = np.clip((s_sub - 14) / 16, 0, 1)[:, None]
t_high = np.clip((h_sub - (hmin + 0.6 * (hmax - hmin))) / (0.4 * (hmax - hmin) + 1e-6), 0, 1)[:, None]
c = grass * (1 - t_high) + dry * t_high
c = c * (1 - t_slope) + rock * t_slope
near_water = np.zeros(N * N, bool).reshape(N, N)
for dy, dx in ((2, 0), (-2, 0), (0, 2), (0, -2)):
    near_water |= shifted(water, dy, dx)
nw = near_water[np.ix_(idx, idx)].ravel()[:, None]
c = np.where(nw & ~w_sub[:, None], sand, c)
c = np.where(w_sub[:, None], bed, c)
col.data.foreach_set("color", np.concatenate([c, np.ones((len(c), 1))], 1).astype(np.float32).ravel())
terrain = bpy.data.objects.new("CityTerrain", me)
bpy.context.scene.collection.objects.link(terrain)
mat = bpy.data.materials.new("Ground")
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
attr = mat.node_tree.nodes.new("ShaderNodeVertexColor"); attr.layer_name = "Ground"
mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.95
me.materials.append(mat)
# water surface: one mesh over every water cell, at its water level
wl = water_level[np.ix_(idx, idx)]
wm = water[np.ix_(idx, idx)]
bm = bmesh.new()
vmap = {}
def wv(j, i):
    if (j, i) not in vmap:
        vmap[(j, i)] = bm.verts.new((X[idx[j], idx[i]] - SIZE / 2, Y[idx[j], idx[i]] - SIZE / 2, max(wl[j, i], SEA_LEVEL if sea else -1e9) + 0.05))
    return vmap[(j, i)]
for j in range(M - 1):
    for i in range(M - 1):
        if wm[j, i] or wm[j + 1, i] or wm[j, i + 1] or wm[j + 1, i + 1]:
            if wm[j, i] + wm[j + 1, i] + wm[j, i + 1] + wm[j + 1, i + 1] >= 2:
                bm.faces.new((wv(j, i), wv(j, i + 1), wv(j + 1, i + 1), wv(j + 1, i)))
wme = bpy.data.meshes.new("Water"); bm.to_mesh(wme); bm.free()
wobj = bpy.data.objects.new("Water", wme); bpy.context.scene.collection.objects.link(wobj)
wmat = bpy.data.materials.new("Water")
wb = next(n for n in wmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
wb.inputs["Base Color"].default_value = (0.03, 0.18, 0.36, 1); wb.inputs["Roughness"].default_value = 0.25
wb.inputs["Specular IOR Level"].default_value = 0.15
wme.materials.append(wmat)
# river lines as curves (what the road planner gets)
cu = bpy.data.curves.new("Rivers", "CURVE"); cu.dimensions = "3D"
for line in rivers:
    sp = cu.splines.new("POLY"); sp.points.add(len(line) - 1)
    for p_, (x, y) in zip(sp.points, line):
        j, i = int(round(y / CELL)), int(round(x / CELL))
        p_.co = (x - SIZE / 2, y - SIZE / 2, float(water_level[min(j, N - 1), min(i, N - 1)]) + 0.4, 1)
cu.bevel_depth = 1.2
robj = bpy.data.objects.new("RiverLines", cu); bpy.context.scene.collection.objects.link(robj)
rmat = bpy.data.materials.new("RiverLine"); rb = next(n for n in rmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
rb.inputs["Base Color"].default_value = (0.1, 0.45, 0.95, 1); cu.materials.append(rmat)
robj.hide_render = True

if RENDER:
    sc = bpy.context.scene
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.35, 0.5, 0.8, 1); bg.inputs[1].default_value = 0.6
    sc.view_settings.look = "AgX - Medium High Contrast" if "AgX - Medium High Contrast" in [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else sc.view_settings.look
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(55), 0, math.radians(30)); sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_end = 20000
    sc.render.resolution_x, sc.render.resolution_y = 1400, 800
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try: sc.render.engine = eng; break
        except TypeError: pass
    sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.color_depth = "8"
    from mathutils import Vector
    for name, eye in (("terrain_overview", (-0.55, -0.75, 0.55)), ("terrain_low", (-0.7, -0.6, 0.12))):
        e = Vector(eye).normalized() * SIZE * 1.15
        e.z += hmax
        cam.location = e
        cam.rotation_euler = (Vector((0, 0, (hmin + hmax) / 2)) - e).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 30
        sc.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "terrain.blend"))
print("TERRAIN outputs in", OUT)
