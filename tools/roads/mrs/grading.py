"""Road - terrain integration on heightfields, for any game: the vertical alignment of a road network over a natural
terrain, and the terrain graded to the built roads. Pure numpy: no Blender and no city data, so any heightfield and
any road graph can use it.

  Field(h, cell, origin, water, water_level)   a square-cell heightfield: bilinear height, wetness, water level
  network_profiles(field, nodes, edges, ...)   node heights and a height per polyline point of every edge:
      nodes  {id: (x, y)}; edges [{"a", "b", "pts": [(x, y)...], "max_grade", "smooth", "bridge"}]
      * a node sits on the natural ground averaged round it (`node_radius`)
      * node heights are relaxed until every edge can climb between them at its max grade
      * an edge follows the natural ground averaged over its `smooth` length, ends pinned to its nodes, then grade
        limited; over water the deck spans bank to bank at least `clearance` above the water
  corridor_field(field, roads, ...)            the natural heights with every road corridor set to its profile
      (what a network builder samples for road and junction heights)
  grade(h, own, surface, ...)                  the terrain graded to the built road surfaces: under a surface
      `sink` below it; beyond, the natural ground limited to cut / fill batters from the surfaces, so
      the ground meets every road edge and blends back into the natural terrain
Units: metres, plan (x, y) = column, row * cell + origin."""
import math
import numpy as np


class Field:
    def __init__(self, h, cell, origin=(0.0, 0.0), water=None, water_level=None):
        self.h = np.asarray(h, dtype=np.float64); self.cell = float(cell); self.ox, self.oy = origin
        self.n_y, self.n_x = self.h.shape
        self.water = None if water is None else np.asarray(water).astype(bool)
        self.wl = None if water_level is None else np.asarray(water_level, dtype=np.float64)

    def _ij(self, x, y):
        fx = (x - self.ox) / self.cell; fy = (y - self.oy) / self.cell
        i0 = int(np.clip(math.floor(fx), 0, self.n_x - 2)); j0 = int(np.clip(math.floor(fy), 0, self.n_y - 2))
        return i0, j0, min(max(fx - i0, 0.0), 1.0), min(max(fy - j0, 0.0), 1.0)

    def _bilinear(self, a, x, y):
        i, j, u, v = self._ij(x, y)
        return float(a[j, i] * (1 - u) * (1 - v) + a[j, i + 1] * u * (1 - v) + a[j + 1, i] * (1 - u) * v + a[j + 1, i + 1] * u * v)

    def __call__(self, x, y): return self._bilinear(self.h, x, y)

    def wet(self, x, y):
        if self.water is None: return False
        i = int(round((x - self.ox) / self.cell)); j = int(round((y - self.oy) / self.cell))
        return bool(self.water[j, i]) if 0 <= i < self.n_x and 0 <= j < self.n_y else False

    def level(self, x, y):
        return self._bilinear(self.wl, x, y) if self.wl is not None else None


def densify(pts, step):
    out = [tuple(pts[0])]
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(math.ceil(L / step)))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def _stations(pts):
    s = [0.0]
    for a, b in zip(pts, pts[1:]): s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return np.array(s)


def grade_limit(z, s, g, z0=None, z1=None):
    """z clipped so |dz/ds| <= g everywhere, keeping pinned ends (an infeasible pair falls back to their line)."""
    z = np.array(z, dtype=np.float64); S = s[-1]
    if z0 is not None and z1 is not None and abs(z1 - z0) > g * S: return z0 + (z1 - z0) * s / max(S, 1e-9)
    lo = np.full_like(z, -np.inf); hi = np.full_like(z, np.inf)
    if z0 is not None: lo = np.maximum(lo, z0 - g * s); hi = np.minimum(hi, z0 + g * s)
    if z1 is not None: lo = np.maximum(lo, z1 - g * (S - s)); hi = np.minimum(hi, z1 + g * (S - s))
    z = np.clip(z, lo, hi)
    for _ in range(2):
        for k in range(1, len(z)): z[k] = min(max(z[k], z[k - 1] - g * (s[k] - s[k - 1])), z[k - 1] + g * (s[k] - s[k - 1]))
        for k in range(len(z) - 2, -1, -1): z[k] = min(max(z[k], z[k + 1] - g * (s[k + 1] - s[k])), z[k + 1] + g * (s[k + 1] - s[k]))
    if z0 is not None: z[0] = z0
    if z1 is not None: z[-1] = z1
    return z


def _mean_window(v, s, w):
    """Moving average of v over a window of w metres (stations s)."""
    if w <= 0 or len(v) < 3: return np.array(v, dtype=np.float64)
    c = np.concatenate([[0.0], np.cumsum(v)])
    lo = np.searchsorted(s, s - w / 2, "left"); hi = np.searchsorted(s, s + w / 2, "right")
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def profile(field, pts, z0=None, z1=None, max_grade=0.08, smooth=30.0, clearance=4.0, bridge=False):
    """Heights for the points of a polyline (already dense): the natural ground averaged over `smooth` m, the end
    differences to the pinned heights blended out along the length, grade limited. Wet stretches (and a `bridge`)
    span bank to bank: the line between the dry ends, lifted to `clearance` over the water level with a smooth
    crest, then grade limited (the approaches ramp up at the max grade)."""
    s = _stations(pts); S = max(s[-1], 1e-9)
    g = np.array([field(x, y) for x, y in pts])
    wet = np.array([field.wet(x, y) for x, y in pts])
    if wet.all() or (bridge and not wet.any()):
        dry_z = np.interp(s, [0.0, S], [z0 if z0 is not None else g[0], z1 if z1 is not None else g[-1]])
    else:
        dry_s = s[~wet]; dry_g = _mean_window(g[~wet], dry_s, smooth)
        dry_z = np.interp(s, dry_s, dry_g)
    z = dry_z.copy()
    if z0 is not None or z1 is not None:
        d0 = (z0 - z[0]) if z0 is not None else 0.0; d1 = (z1 - z[-1]) if z1 is not None else 0.0
        t = s / S; w = t * t * (3 - 2 * t)
        z = z + d0 * (1 - w) + d1 * w
    if wet.any():
        lv = max((field.level(x, y) or -1e9) for (x, y), w_ in zip(pts, wet) if w_)
        need = lv + clearance
        # a crest: the deck at the clearance over the water, easing back to the banks
        k = np.nonzero(wet)[0]; sa, sb = s[k[0]], s[k[-1]]
        mid = 0.5 * (sa + sb); half = max(0.5 * (sb - sa), 1.0)
        lift = np.clip(1.0 - ((s - mid) / (half + 30.0)) ** 2, 0.0, 1.0)
        z = np.maximum(z, z + (need - z) * lift * (s >= sa - 30.0) * (s <= sb + 30.0))
        z[wet] = np.maximum(z[wet], need)
    return grade_limit(z, s, max_grade, z0, z1)


def network_profiles(field, nodes, edges, node_radius=8.0, iterations=40, clearance=4.0):
    """({node: z}, [z array per edge]) for a road graph over the natural terrain (see the module notes)."""
    zn = {}
    for nid, (x, y) in nodes.items():
        ring = [(x + node_radius * math.cos(a), y + node_radius * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]] + [(x, y)]
        dry = [field(px, py) for px, py in ring if not field.wet(px, py)]
        zn[nid] = float(np.mean(dry)) if dry else field(x, y)
    lens = [float(_stations(e["pts"])[-1]) for e in edges]
    # a bridge lifts its end nodes so the deck can reach its clearance over the water at its own grade
    lifted = {}
    for e in edges:
        if not e.get("bridge"): continue
        pts = e["pts"]; s = _stations(pts); wet = [field.wet(x, y) for x, y in pts]
        if not any(wet): continue
        need = max(field.level(x, y) for (x, y), w in zip(pts, wet) if w) + e.get("clearance", clearance)
        k0 = wet.index(True); k1 = len(wet) - 1 - wet[::-1].index(True); g = e.get("max_grade", 0.06)
        for nid, d in ((e["a"], s[k0]), (e["b"], s[-1] - s[k1])):
            if nid in zn: lifted[nid] = max(lifted.get(nid, -1e9), need - g * d)
    for nid, zmin in lifted.items(): zn[nid] = max(zn[nid], zmin)
    # relax: an edge too steep for its max grade pulls its two nodes toward each other (bridges included)
    for _ in range(iterations):
        moved = 0.0
        for e, L in zip(edges, lens):
            a, b = e["a"], e["b"]
            if a == b or a not in zn or b not in zn: continue
            lim = e.get("max_grade", 0.08) * L; dz = zn[b] - zn[a]
            if abs(dz) > lim:
                c = (abs(dz) - lim) * math.copysign(1.0, dz)
                fa = 0.0 if (a in lifted and c < 0) else (1.0 if (b in lifted and c > 0) else 0.5)     # the lifted end holds
                zn[a] += c * fa; zn[b] -= c * (1.0 - fa); moved = max(moved, abs(c))
        if moved < 0.01: break
    out = []
    for e in edges:
        out.append(profile(field, e["pts"], zn.get(e["a"]), zn.get(e["b"]), e.get("max_grade", 0.08), e.get("smooth", 30.0),
                           clearance=e.get("clearance", clearance), bridge=e.get("bridge", False)))
    return zn, out


def corridor_field(field, roads, feather=10.0):
    """The natural heights with each road corridor at its profile: roads [{"pts": [(x, y)], "z": [...], "half": m}]
    (half = half width out to the back of the sidewalks); a `feather` m blend beyond. Wet cells keep their height
    (a bridge deck does not fill the river)."""
    h = field.h.copy(); acc = np.zeros_like(h); wsum = np.zeros_like(h); c = field.cell
    for r in roads:
        P = np.asarray(r["pts"], dtype=np.float64); Z = np.asarray(r["z"], dtype=np.float64); half = float(r["half"])
        if len(P) < 2: continue
        reach = half + feather
        x0, y0 = P.min(0) - reach; x1, y1 = P.max(0) + reach
        i0 = max(0, int((x0 - field.ox) / c)); i1 = min(field.n_x - 1, int(math.ceil((x1 - field.ox) / c)))
        j0 = max(0, int((y0 - field.oy) / c)); j1 = min(field.n_y - 1, int(math.ceil((y1 - field.oy) / c)))
        if i1 < i0 or j1 < j0: continue
        jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
        px = ii * c + field.ox; py = jj * c + field.oy
        best = np.full(px.shape, np.inf); bz = np.zeros(px.shape)
        for k in range(len(P) - 1):
            a, b = P[k], P[k + 1]; d = b - a; L2 = float(d @ d)
            if L2 < 1e-12: continue
            t = np.clip(((px - a[0]) * d[0] + (py - a[1]) * d[1]) / L2, 0.0, 1.0)
            dist = np.hypot(px - (a[0] + d[0] * t), py - (a[1] + d[1] * t))
            sel = dist < best; best = np.where(sel, dist, best); bz = np.where(sel, Z[k] + (Z[k + 1] - Z[k]) * t, bz)
        w = np.clip(1.0 - (best - half) / feather, 0.0, 1.0); w = w * w * (3 - 2 * w)
        if field.water is not None: w = np.where(field.water[j0:j1 + 1, i0:i1 + 1], 0.0, w)
        sl = (slice(j0, j1 + 1), slice(i0, i1 + 1))
        # the nearest corridor wins where two overlap (a weight^4 average keeps junction cells on the plane)
        acc[sl] += bz * w ** 4; wsum[sl] += w ** 4
        h[sl] = np.where(w >= 0.999, bz, h[sl])
    m = wsum > 1e-9; blend = np.clip(np.sqrt(np.sqrt(wsum)), 0.0, 1.0)
    return np.where(m, h * (1 - blend) + (acc / np.maximum(wsum, 1e-12)) * blend, h)


def grade(h0, own, surface, cell, slope=0.5, sink=0.3, water=None, max_passes=400, cut_slope=None):
    """The terrain graded to built road surfaces. own: cells under a surface; surface: its height there. Under a
    surface the ground is `sink` below it; elsewhere the natural height is clipped between the batter bounds
    (surface + cut_slope * distance above, surface - slope * distance below, from the nearest surface cell), so
    cuts and fills meet the roads at their batters (rise / run; a cut stands steeper than a fill: default
    2 * slope) and blend into the natural ground. Wet cells stay as they are. Returns the graded heights."""
    cut_slope = 2.0 * slope if cut_slope is None else cut_slope
    h0 = np.asarray(h0, dtype=np.float64)
    big = 1e9
    hi = np.where(own, surface, big); lo = np.where(own, surface, -big)
    steps = [(0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0))]
    ny, nx = hi.shape
    for _ in range(max_passes):          # each pass carries the bounds one cell further (8 directions)
        changed = False
        for dj, di, dist in steps:
            for sj, si in ((dj, di), (-dj, -di)):
                d_cut = cut_slope * dist * cell; d_fill = slope * dist * cell
                ys = slice(max(0, sj), ny + min(0, sj)); yd = slice(max(0, -sj), ny + min(0, -sj))
                xs = slice(max(0, si), nx + min(0, si)); xd = slice(max(0, -si), nx + min(0, -si))
                nh = np.minimum(hi[yd, xd], hi[ys, xs] + d_cut); nl = np.maximum(lo[yd, xd], lo[ys, xs] - d_fill)
                if not changed and (np.any(nh < hi[yd, xd]) or np.any(nl > lo[yd, xd])): changed = True
                hi[yd, xd] = nh; lo[yd, xd] = nl
        if not changed: break
    hi = np.where(hi >= big * 0.5, np.inf, hi); lo = np.where(lo <= -big * 0.5, -np.inf, lo)
    conflict = lo > hi                                  # two roads at different heights closer than their batters allow
    mid = np.where(conflict, 0.5 * (np.where(np.isfinite(lo), lo, 0) + np.where(np.isfinite(hi), hi, 0)), 0.0)
    g = np.where(conflict, mid, np.clip(h0, lo, hi))
    g = np.where(own, surface - sink, g)
    if water is not None: g = np.where(np.asarray(water).astype(bool) & ~own, h0, g)
    return g
