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
    s = _stations(pts)
    return grade_limit(_profile_target(field, pts, s, z0, z1, smooth, clearance, bridge), s, max_grade, z0, z1)


def _profile_target(field, pts, s, z0, z1, smooth, clearance, bridge):
    """profile()'s height target before the grade limit (the averaged ground, the pinned ends blended in, decks)."""
    S = max(s[-1], 1e-9)
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
    return z


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


def grade(h0, own, surface, cell, slope=0.5, sink=0.3, water=None, max_passes=400, cut_slope=None, deep_cut=6.0, deep_slope=None):
    """The terrain graded to built road surfaces. own: cells under a surface; surface: its height there. Under a
    surface the ground is `sink` below it; elsewhere the natural height is clipped between the batter bounds
    (surface + cut_slope * distance above, surface - slope * distance below, from the nearest surface cell), so
    cuts and fills meet the roads at their batters (rise / run; a cut stands steeper than a fill: default
    2 * slope) and blend into the natural ground. A cut deeper than `deep_cut` m steepens to `deep_slope` beyond
    it (a rock cutting: default 2 * cut_slope), half as wide as a cut at one slope. Wet cells stay as they are.
    Returns the graded heights."""
    cut_slope = 2.0 * slope if cut_slope is None else cut_slope
    deep_slope = 2.0 * cut_slope if deep_slope is None else deep_slope
    h0 = np.asarray(h0, dtype=np.float64)
    big = 1e9
    hi = np.where(own, surface, big); lo = np.where(own, surface, -big); D = np.where(own, 0.0, big)
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
                nd = np.minimum(D[yd, xd], D[ys, xs] + dist * cell)
                if not changed and (np.any(nh < hi[yd, xd]) or np.any(nl > lo[yd, xd]) or np.any(nd < D[yd, xd])): changed = True
                hi[yd, xd] = nh; lo[yd, xd] = nl; D[yd, xd] = nd
        if not changed: break
    hi = np.where(hi >= big * 0.5, np.inf, hi); lo = np.where(lo <= -big * 0.5, -np.inf, lo)
    # beyond deep_cut of rise the cut steepens: the extra allowance over the single-slope bound
    d1 = deep_cut / cut_slope
    hi = hi + np.maximum(np.where(D >= big * 0.5, 0.0, D) - d1, 0.0) * (deep_slope - cut_slope)
    conflict = lo > hi                                  # two roads at different heights closer than their batters allow
    mid = np.where(conflict, 0.5 * (np.where(np.isfinite(lo), lo, 0) + np.where(np.isfinite(hi), hi, 0)), 0.0)
    g = np.where(conflict, mid, np.clip(h0, lo, hi))
    g = np.where(own, surface - sink, g)
    if water is not None: g = np.where(np.asarray(water).astype(bool) & ~own, h0, g)
    return g


# ============================================================================ landing-aware vertical design
# A built street exists only between its junctions' footprints (trims), and the road group blends each locked end to
# the junction's height over its Lock Length with a smoothstep that arrives level (the grade inside the blend peaks
# at 27/16 of the profile's). The design below budgets every edge's climb on what is built: level over the junction
# footprint and a platform past it, a gentle landing over the lock zone, a vertical curve, then the class maximum.
LOCK_K = 27.0 / 16.0                 # peak grade of road.py's constant-height smoothstep lock / the landing grade


def insert_stations(pts, stations):
    """pts (x, y) with extra collinear vertices at the given plan stations (the plan line is unchanged)."""
    s = _stations(pts); P = np.asarray(pts, float); S = s[-1]
    extra = sorted({round(float(v), 4) for v in stations if 1e-3 < v < S - 1e-3})
    extra = [v for v in extra if np.min(np.abs(s - v)) > 0.05]
    if not extra: return [tuple(p) for p in pts]
    allv = np.sort(np.concatenate([s, extra]), kind="stable")
    return list(zip(np.interp(allv, s, P[:, 0]).tolist(), np.interp(allv, s, P[:, 1]).tolist()))


def caps(s, G, ends=None, land_grade=0.0, vc=0.0, flat=0.0):
    """The grade cap of every segment (len(s) - 1) of an edge. `ends` ((trim_a, land_a), (trim_b, land_b)): metres
    from each node centre; 0 over the junction footprint and the first `flat` m past it (level, at the node height),
    `land_grade` over the rest of the landing, a linear ramp to G over `vc` m (a vertical curve), G elsewhere. `flat`
    and `land_grade` may be (a, b) pairs. Without `ends` every segment is capped at G."""
    s = np.asarray(s, float); mid = 0.5 * (s[1:] + s[:-1]); S = s[-1]
    g = np.full(len(mid), float(G))
    if not ends: return g
    for k, (trim, land) in enumerate(ends):
        if trim <= 0 and land <= 0: continue
        gl = land_grade[k] if isinstance(land_grade, (list, tuple)) else land_grade
        fl = flat[k] if isinstance(flat, (list, tuple)) else flat
        d = mid if k == 0 else S - mid
        cap = np.where(d < trim + min(fl, land), 0.0, np.where(d < trim + land, gl, G))
        if vc > 0: cap = np.where(d >= trim + land, np.minimum(G, gl + (G - gl) * (d - trim - land) / vc), cap)
        g = np.minimum(g, cap)
    return g


def grade_limit_caps(z, s, gk, z0=None, z1=None, tol=1e-3):
    """(z, feasible): z clipped so |dz| <= gk * ds on every segment, pinned ends kept. Pins further apart than the
    capacity spread the difference in proportion to the caps (level segments stay level) and report infeasible."""
    z = np.array(z, dtype=np.float64); ds = np.diff(s); cum = np.concatenate([[0.0], np.cumsum(gk * ds)]); C = cum[-1]
    if z0 is not None and z1 is not None and abs(z1 - z0) > C:
        ok = abs(z1 - z0) <= C + tol
        if C > 1e-9: return z0 + (z1 - z0) * cum / C, ok
        return z0 + (z1 - z0) * s / max(s[-1], 1e-9), ok
    lo = np.full_like(z, -np.inf); hi = np.full_like(z, np.inf)
    if z0 is not None: lo = np.maximum(lo, z0 - cum); hi = np.minimum(hi, z0 + cum)
    if z1 is not None: lo = np.maximum(lo, z1 - (C - cum)); hi = np.minimum(hi, z1 + (C - cum))
    z = np.clip(z, lo, hi); step = gk * ds
    for _ in range(2):
        for k in range(1, len(z)): z[k] = min(max(z[k], z[k - 1] - step[k - 1]), z[k - 1] + step[k - 1])
        for k in range(len(z) - 2, -1, -1): z[k] = min(max(z[k], z[k + 1] - step[k]), z[k + 1] + step[k])
    if z0 is not None: z[0] = z0
    if z1 is not None: z[-1] = z1
    return z, True


def node_heights(field, nodes, node_radius=8.0):
    """{node: the natural ground averaged round it} (dry points of a ring of `node_radius`)."""
    zn = {}
    for nid, (x, y) in nodes.items():
        ring = [(x + node_radius * math.cos(a), y + node_radius * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]] + [(x, y)]
        dry = [field(px, py) for px, py in ring if not field.wet(px, py)]
        zn[nid] = float(np.mean(dry)) if dry else field(x, y)
    return zn


def network_profiles_landed(field, nodes, edges, node_radius=8.0, iterations=2000, clearance=4.0, tol=1e-4, info=None, max_move=None):
    """network_profiles with per-edge caps (see caps): an edge may carry "ends", "land_grade", "vc", "flat". Node
    heights are relaxed on each edge's CAPACITY (sum of cap x run: the climb its built part can make), each node kept
    within `max_move` of its natural (or bridge-lifted) height. `info` receives iterations, residual {edge: m},
    infeasible edges, moves, z_nat, lifted, capacity and caps."""
    zn = node_heights(field, nodes, node_radius); z_nat = dict(zn)
    st = [_stations(e["pts"]) for e in edges]
    gks = [caps(s, e.get("max_grade", 0.08), e.get("ends"), e.get("land_grade", 0.0), e.get("vc", 0.0), e.get("flat", 0.0)) for e, s in zip(edges, st)]
    cums = [np.concatenate([[0.0], np.cumsum(gk * np.diff(s))]) for gk, s in zip(gks, st)]
    lifted = {}
    for e, cum in zip(edges, cums):
        if not e.get("bridge"): continue
        pts = e["pts"]; wet = [field.wet(x, y) for x, y in pts]
        if not any(wet): continue
        need = max(field.level(x, y) for (x, y), w in zip(pts, wet) if w) + e.get("clearance", clearance)
        k0 = wet.index(True); k1 = len(wet) - 1 - wet[::-1].index(True)
        for nid, cap_to_water in ((e["a"], cum[k0]), (e["b"], cum[-1] - cum[k1])):
            if nid in zn: lifted[nid] = max(lifted.get(nid, -1e9), need - cap_to_water)
    for nid, zmin in lifted.items(): zn[nid] = max(zn[nid], zmin)
    box = {k: (v - max_move, v + max_move) for k, v in zn.items()} if max_move else {}
    it = 0
    for it in range(1, iterations + 1):
        moved = 0.0
        for e, cum in zip(edges, cums):
            a, b = e["a"], e["b"]
            if a == b or a not in zn or b not in zn: continue
            lim = cum[-1]; dz = zn[b] - zn[a]
            if abs(dz) > lim:
                c = (abs(dz) - lim) * math.copysign(1.0, dz)
                fa = 0.0 if (a in lifted and c < 0) else (1.0 if (b in lifted and c > 0) else 0.5)
                za = zn[a] + c * fa; zb = zn[b] - c * (1.0 - fa)
                if box: za = min(max(za, box[a][0]), box[a][1]); zb = min(max(zb, box[b][0]), box[b][1])
                moved = max(moved, abs(za - zn[a]), abs(zb - zn[b])); zn[a] = za; zn[b] = zb
        if moved < tol: break
    out = []; infeasible = []
    for i, (e, gk, s) in enumerate(zip(edges, gks, st)):
        z0, z1 = zn.get(e["a"]), zn.get(e["b"])
        target = _profile_target(field, e["pts"], s, z0, z1, e.get("smooth", 30.0), e.get("clearance", clearance), e.get("bridge", False))
        z, ok = grade_limit_caps(target, s, gk, z0, z1)
        out.append(z)
        if not ok: infeasible.append(i)
    if info is not None:
        res = {}
        for i, (e, cum) in enumerate(zip(edges, cums)):
            a, b = e["a"], e["b"]
            if a in zn and b in zn and a != b:
                r = abs(zn[b] - zn[a]) - cum[-1]
                if r > 1e-3: res[i] = r
        info.update(iterations=it, residual=res, infeasible=infeasible, moves={k: zn[k] - z_nat[k] for k in zn}, z_nat=z_nat,
                    capacity=[float(c[-1]) for c in cums], caps=gks, lifted=lifted)
    return zn, out


def window_grades(plan, z, w=10.0):
    """(worst, station): the steepest |dz| / w over every window of `w` m of PLAN run (rise over horizontal run,
    interpolated), or the whole length once when it is shorter. The design, the tests and the validator all measure
    a street's grade with this."""
    plan = np.asarray(plan, float); z = np.asarray(z, float)
    if len(plan) < 2: return 0.0, 0.0
    if plan[-1] - plan[0] <= w: return abs(z[-1] - z[0]) / max(plan[-1] - plan[0], 1e-6), float(plan[0])
    zi = np.interp(plan + w, plan, z); ok = plan + w <= plan[-1] + 1e-9
    g = np.abs(zi[ok] - z[ok]) / w; k = int(np.argmax(g))
    return float(g[k]), float(plan[ok][k])


def _smooth01(v):
    v = np.clip(v, 0.0, 1.0); return v * v * (3 - 2 * v)


def rail_model(pts, ta, tb, lock_a, lock_b, za, zb, lock_length=14.0, crown_h=0.0, resolution=1.0, smoothing=4):
    """A numpy twin of the MRS_Road rail and its crest (road.py: trim, resample every `resolution` m, Blur Attribute
    `smoothing` times, smoothstep locks toward a constant Lock Z over `lock_length`, the crown fading in over the same
    length): (along, plan run, z rail, z crest) of the road built on the 3D polyline `pts`, or None when the trims
    leave nothing. The design uses it to predict the built grade."""
    P = np.asarray(pts, float)
    s3 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    sp = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1))])
    s0, s1 = ta, s3[-1] - tb; Lt = s1 - s0
    if Lt < 0.5: return None
    ss = np.linspace(s0, s1, max(int(Lt / resolution) + 1, 2))
    z = np.interp(ss, s3, P[:, 2]); plan = np.interp(ss, s3, sp)
    for _ in range(int(smoothing)):
        zz = z.copy()
        if len(z) >= 3: zz[1:-1] = (z[:-2] + z[1:-1] + z[2:]) / 3.0
        if len(z) >= 2: zz[0] = (z[0] + z[1]) / 2; zz[-1] = (z[-1] + z[-2]) / 2
        z = zz
    a = ss - s0; LL = max(lock_length, 1e-6)
    if lock_a: z = z + (za - z) * _smooth01(1 - a / LL)
    if lock_b: z = z + (zb - z) * _smooth01(1 - (Lt - a) / LL)
    fs = _smooth01(a / LL) if lock_a else 1.0; fe = _smooth01((Lt - a) / LL) if lock_b else 1.0
    return a, plan - plan[0], z, z + crown_h * fs * fe
