"""Sedan body shell v2 — controlled quad cage + creased subdivision surface.

The body is a lofted quad cage: one ring of named landmark points per longitudinal station.
Landmark indices are constant along the car, so edge loops can be creased (shoulder line, sill,
cant rail), panel gaps become real recessed grooves (double stations), and faces can be
assigned to glass / paint / trim zones by (station, landmark) rules. A Catmull-Clark
subdivision then gives smooth automotive surfaces with crisp character lines.

Frame: Blender; metres; +Y = front; origin on the ground at the wheelbase centre.
Dimensions come from production/references/dimension_sheet.json when present (values flagged
"measured" or "target"); otherwise the labelled defaults below are used.
"""
import bpy, bmesh, math, json, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "production", "references", "dimension_sheet.json")

# PROPOSED TARGETS (real mid-size sedan); overridden by the dimension sheet if it defines them.
DIM = {
    "length": 4.80, "width": 1.86, "height": 1.46, "wheelbase": 2.85, "track": 1.60,
    "front_overhang": 1.0, "wheel_diameter": 0.66, "tyre_width": 0.225, "ground_clearance": 0.15,
    "sill_bottom": 0.30, "sill_top": 0.42, "belt_front_door": 0.93, "hood_nose": 0.72, "cowl_height": 1.0,
    "cowl_y_from_front": 1.42, "roof_peak": 1.47, "roof_peak_y_from_front": 2.75,
    "windscreen_top_y_from_front": 2.45, "roof_end_y_from_front": 3.55, "trunk_start_y_from_front": 4.22,
    "trunk_height": 1.06, "tail_height": 0.98, "roof_half_width": 0.66, "bumper_top": 0.64, "end_round_radius": 0.34,
    "a_pillar_base_y_from_front": 1.5, "b_pillar_y_from_front": 2.73, "c_pillar_base_y_from_front": 4.0,
    "door_gap_front_y_from_front": 1.46, "door_gap_mid_y_from_front": 2.66, "door_gap_rear_y_from_front": 3.66,
}


def load_sheet():
    if not os.path.exists(SHEET):
        return
    try:
        data = json.load(open(SHEET, encoding="utf-8"))
        vals = {k: (e.get("value") if isinstance(e, dict) else e) for k, e in data.get("values", {}).items()}
        # Sheet key -> module parameter (sheet names follow the Reference Engineer's report).
        alias = {"overall_length": "length", "overall_width_body": "width", "overall_height": "height", "wheelbase": "wheelbase",
                 "track_front": "track", "front_overhang": "front_overhang", "tyre_diameter": "wheel_diameter", "tyre_width": "tyre_width",
                 "ground_clearance": "ground_clearance", "sill_height": "sill_bottom", "belt_line_height_front_door": "belt_front_door",
                 "hood_height_nose": "hood_nose", "hood_height_cowl": "cowl_height", "cowl_from_front": "cowl_y_from_front",
                 "overall_height": "roof_peak", "roof_peak_from_front": "roof_peak_y_from_front", "roof_start_from_front": "windscreen_top_y_from_front",
                 "roof_end_from_front": "roof_end_y_from_front", "rear_screen_end_from_front": "trunk_start_y_from_front",
                 "trunk_height_at_screen_end": "trunk_height", "trunk_height_at_lip": "tail_height"}
        for key, param in alias.items():
            v = vals.get(key)
            if isinstance(v, (int, float)):
                DIM[param] = float(v)
        if isinstance(vals.get("roof_width_cant_rails"), (int, float)):
            DIM["roof_half_width"] = float(vals["roof_width_cant_rails"]) / 2
        y_front = DIM["wheelbase"] / 2 + DIM["front_overhang"]
        for key, param in (("front_door_leading_edge_y", "door_gap_front_y_from_front"), ("b_pillar_y", "door_gap_mid_y_from_front"),
                           ("rear_door_trailing_edge_y", "door_gap_rear_y_from_front")):
            v = vals.get(key)
            if isinstance(v, (int, float)):
                DIM[param] = y_front - float(v)
        DIM["a_pillar_base_y_from_front"] = DIM["door_gap_front_y_from_front"] + 0.04
        DIM["b_pillar_y_from_front"] = DIM["door_gap_mid_y_from_front"]
        DIM["c_pillar_base_y_from_front"] = DIM["trunk_start_y_from_front"] - 0.25
        print("dimension sheet applied:", {k: DIM[k] for k in ("length", "height", "sill_bottom", "belt_front_door", "cowl_y_from_front", "roof_end_y_from_front")})
    except Exception as err:  # the sheet is advisory; a broken sheet must not stop the build
        print("dimension sheet ignored:", err)


load_sheet()

L = DIM["length"]
W = DIM["width"]
WB = DIM["wheelbase"]
Y_FRONT = WB / 2 + DIM["front_overhang"] + 0.04   # +4 cm: subdivision pulls the end caps in
Y_REAR = Y_FRONT - L - 0.08
AXLE_F, AXLE_R = WB / 2, -WB / 2
WHEEL_R = DIM["wheel_diameter"] / 2
TRACK_X = DIM["track"] / 2
FLOOR_Z = DIM["sill_bottom"]      # visible lower edge of the body side; the underbody is a separate dark plate
SILL_TOP = DIM["sill_top"]
ROOF_X = DIM["roof_half_width"]


def yf(from_front):
    """Station y from a 'distance from the front bumper' value."""
    return Y_FRONT - from_front


Y_COWL = yf(DIM["cowl_y_from_front"])
Y_WS_TOP = yf(DIM["windscreen_top_y_from_front"])
Y_ROOF_PEAK = yf(DIM["roof_peak_y_from_front"])
Y_ROOF_END = yf(DIM["roof_end_y_from_front"])
Y_TRUNK = yf(DIM["trunk_start_y_from_front"])
Y_A_PILLAR = yf(DIM["a_pillar_base_y_from_front"])
Y_B_PILLAR = yf(DIM["b_pillar_y_from_front"])
Y_C_PILLAR = yf(DIM["c_pillar_base_y_from_front"])
GAPS = [yf(DIM["door_gap_front_y_from_front"]), yf(DIM["door_gap_mid_y_from_front"]), yf(DIM["door_gap_rear_y_from_front"])]
Y_BUMPER_F = Y_FRONT - 0.40     # front bumper / fender cut (just inside the nose rounding)
Y_BUMPER_R = Y_REAR + 0.42      # rear bumper / quarter cut
HOOD_X = 0.74                   # hood / fender break line (half width at the cowl)
HOOD_X_NOSE = 0.56

# ---------------------------------------------------------------------------- design curves


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def half_width(y):
    """Plan-view half width of the lower body at door-mid height."""
    w = W / 2 - 0.035   # shoulder/arch flare bring the widest point back to W
    nose = smooth(Y_FRONT - 1.05, Y_FRONT, y)
    tail = smooth(Y_REAR + 1.0, Y_REAR, y)
    return w - 0.22 * nose ** 2.3 - 0.10 * tail ** 2.0


def flare(y):
    """Fender flare over the wheels (added to the side at arch-lip height)."""
    f = 0.0
    for axle in (AXLE_F, AXLE_R):
        d = abs(y - axle)
        f = max(f, 0.03 * max(0.0, 1.0 - (d / 0.62) ** 2))
    return f


def belt_z(y):
    """Shoulder / belt line. Rises gently to the rear; drops over the bonnet to the nose."""
    if y > Y_COWL:
        t = (y - Y_COWL) / (Y_FRONT - Y_COWL)
        return DIM["cowl_height"] - (DIM["cowl_height"] - DIM["hood_nose"]) * (t ** 1.2)
    if y < Y_TRUNK:
        t = (Y_TRUNK - y) / (Y_TRUNK - Y_REAR)
        return DIM["trunk_height"] - (DIM["trunk_height"] - DIM["tail_height"]) * t ** 1.5
    # door run: belt rises ~4 cm front to rear, blends up into the cowl at the front and into the
    # trunk-lid level over the rear quarter (no step where the greenhouse ends).
    run = DIM["belt_front_door"] + 0.04 * smooth(Y_COWL, Y_TRUNK, y)
    run += (DIM["cowl_height"] - run) * smooth(Y_A_PILLAR, Y_COWL, y)
    run += (DIM["trunk_height"] - run) * smooth(Y_C_PILLAR + 0.15, Y_TRUNK, y)
    return run


def roof_z(y):
    if y >= Y_COWL:
        return belt_z(y) + 0.015
    if y <= Y_TRUNK:
        return belt_z(y) + 0.012
    peak = DIM["roof_peak"]
    if y > Y_WS_TOP:        # windscreen: a near-flat plane, eased at the cowl and the header
        t = (Y_COWL - y) / (Y_COWL - Y_WS_TOP)
        e = 0.75 * t + 0.25 * (t * t * (3 - 2 * t))
        return DIM["cowl_height"] + (peak - 0.015 - DIM["cowl_height"]) * e
    if y > Y_ROOF_END:      # roof panel, peak then gentle fall
        t = (Y_WS_TOP - y) / (Y_WS_TOP - Y_ROOF_END)
        return peak - 0.015 + 0.015 * math.sin(t * math.pi * 0.9) - 0.05 * max(0.0, t - 0.55) ** 1.5
    # rear screen: long, nearly straight fastback plane, eased at the header and the trunk lip
    t = (y - Y_TRUNK) / (Y_ROOF_END - Y_TRUNK)
    e = 0.7 * t + 0.3 * (t * t * (3 - 2 * t))
    return DIM["trunk_height"] + (roof_z(Y_ROOF_END + 1e-4) - DIM["trunk_height"]) * e


def greenhouse(y):
    return Y_TRUNK < y < Y_COWL


def glass_base_x(y):
    return half_width(y) - 0.035


# ---------------------------------------------------------------------------- cross sections

# Landmark indices (half profile, bottom centre -> top centre).
FLOOR_C, FLOOR_E, SILL_B, SILL_T, LOWER, MID, SHOULDER, BELT, G0, G1, G2, CANT, ROOF_E, ROOF_C = range(14)
N_HALF = 14


def end_shape(x, z, y):
    """Nose/tail shaping: the hood/trunk plane rolls over a tight corner into a near-vertical
    bumper face (z 0.40-0.62), the lower lip chamfers back (approach angle) and the plan view
    corners round off. Returns the adjusted (x, z)."""
    d = min(y - Y_REAR, Y_FRONT - y)
    face_top, face_bottom = 0.62, 0.40
    rt, rb, rp = 0.17, 0.22, 0.30
    if z > face_top and d < rt:
        u = (rt - d) / rt
        z = face_top + (z - face_top) * math.sqrt(max(0.0, 1.0 - u * u))
    if z < face_bottom and d < rb:
        z = z + (face_bottom - z) * ((rb - d) / rb) ** 1.6
    if d < rp:
        u = (rp - d) / rp
        x = x * (0.80 + 0.20 * math.sqrt(max(0.0, 1.0 - u * u)))
    return x, z


def section(y):
    """Half profile [(x, z)] for station y."""
    w = half_width(y)
    fl = flare(y)
    zb = belt_z(y)
    zr = roof_z(y)
    pts = [None] * N_HALF
    pts[FLOOR_C] = (0.0, FLOOR_Z)
    pts[FLOOR_E] = (w * 0.80, FLOOR_Z)
    pts[SILL_B] = (w * 0.965, FLOOR_Z + 0.045)
    pts[SILL_T] = (w * 0.985 + fl * 0.4, SILL_TOP)
    pts[LOWER] = (w * 0.982 + fl * 0.8, 0.54)          # concave scallop above the sill
    pts[MID] = (w + 0.006 + fl, 0.70)                  # arch-lip height: fullest point
    # Shoulder line: crisp and proud along the doors, fading out before the nose and tail.
    fade = smooth(0.0, 0.5, min(y - Y_REAR, Y_FRONT - y))
    pts[SHOULDER] = (w + 0.006 + (0.028 + fl * 0.5) * fade, zb - 0.07)   # 3 cm proud crease
    pts[BELT] = (w - 0.02, zb)
    if greenhouse(y):
        gb = glass_base_x(y)
        top = min(ROOF_X, gb - 0.03)
        for i, t in ((G0, 0.08), (G1, 0.42), (G2, 0.76)):
            a = t * math.pi / 2
            x = gb + (top - gb) * (1 - math.cos(a)) ** 0.9
            z = zb + (zr - zb) * math.sin(a) ** 1.05
            pts[i] = (x, z)
        pts[CANT] = (top + 0.015, zr - 0.035)
        pts[ROOF_E] = (top - 0.12, zr - 0.004)
        pts[ROOF_C] = (0.0, zr)
    else:
        # bonnet / boot: fender crown, hood/fender groove at HOOD_X, domed hood
        hx = HOOD_X if y < Y_COWL + 0.2 else HOOD_X + (HOOD_X_NOSE - HOOD_X) * smooth(Y_COWL + 0.2, Y_FRONT, y)
        if y < Y_TRUNK:
            hx = 0.62 + 0.1 * smooth(Y_REAR, Y_TRUNK, y)
        hx = min(hx, pts[BELT][0] - 0.05)
        # The hood/fender gap only exists between the hood edge grooves; beyond them (bumper
        # faces, nose and tail rounding) the crown is a plain surface.
        gap = GAP_D if (Y_REAR + 0.36 < y < Y_FRONT - 0.36) else 0.0
        pts[G0] = (hx + 0.006, zr - 0.006 * (gap / GAP_D))
        pts[G1] = (hx, zr - 0.014 * (gap / GAP_D))
        pts[G2] = (hx - 0.006, zr - 0.006 * (gap / GAP_D))
        pts[CANT] = (hx * 0.62, zr + 0.004)
        pts[ROOF_E] = (hx * 0.28, zr + 0.005)  # gentle power dome
        pts[ROOF_C] = (0.0, zr + 0.007)
    pts = [end_shape(x, z, y) for (x, z) in pts]
    pts = arch_section(pts, y)
    return pts


R_ARCH = 0.37      # wheel-arch opening radius (Ø0.74 per the dimension sheet)
FLANGE = 0.03      # inward return of the arch lip


def skin_x(pts, z):
    """x of the body side at height z, interpolated along the lower side polyline."""
    side = [pts[i] for i in (SILL_B, SILL_T, LOWER, MID, SHOULDER, BELT)]
    for (x0, z0), (x1, z1) in zip(side, side[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / max(z1 - z0, 1e-6)
            return x0 + (x1 - x0) * t
    return side[-1][0] if z > side[-1][1] else side[0][0]


def arch_section(pts, y):
    """Inside a wheel arch, the lower side landmarks become the arch lip and its inward
    flange, so the opening is quad topology (no boolean) and subdivides to a clean circle."""
    for axle in (AXLE_F, AXLE_R):
        dy = y - axle
        if abs(dy) >= R_ARCH:
            continue
        z_lip = WHEEL_R + math.sqrt(R_ARCH * R_ARCH - dy * dy)
        if z_lip < SILL_TOP + 0.03:
            continue
        x_lip = skin_x(pts, z_lip)
        pts = list(pts)
        pts[FLOOR_E] = (0.60, FLOOR_Z)
        pts[SILL_B] = (x_lip - FLANGE, z_lip - 0.008)
        pts[SILL_T] = (x_lip - 0.012, z_lip - 0.002)
        pts[LOWER] = (x_lip, z_lip)
        if pts[MID][1] < z_lip + 0.035:
            zm = z_lip + 0.035
            pts[MID] = (skin_x(pts, zm) if zm < pts[SHOULDER][1] else pts[SHOULDER][0], zm)
    return pts


def full_ring(y):
    half = section(y)
    right = [(x, y, z) for (x, z) in half]
    left = [(-x, y, z) for (x, z) in reversed(half[1:-1])]
    return right + left       # indices 0..13 right side, 14..25 mirrored (26 points)


N_RING = 2 * N_HALF - 2


def mirror_index(i):
    """Landmark index (0..13) for ring position i (0..25)."""
    return i if i < N_HALF else N_RING - i


# ---------------------------------------------------------------------------- stations


def base_stations():
    ys = []
    y = Y_REAR + 0.02
    while y < Y_FRONT - 0.02:
        step = 0.08 if (abs(y - Y_COWL) < 0.3 or abs(y - Y_TRUNK) < 0.35 or y > Y_FRONT - 0.5 or y < Y_REAR + 0.5) else 0.14
        for axle in (AXLE_F, AXLE_R):
            if abs(y - axle) < R_ARCH + 0.08:
                step = min(step, 0.055)
        ys.append(y)
        y += step
    return ys


GAP_W = 0.0045
GAP_D = 0.009


class Groove:
    """Transverse panel gap at station y over landmark range [i0, i1]."""

    def __init__(self, y, i0, i1):
        self.y, self.i0, self.i1 = y, i0, i1

    def stations(self):
        return [self.y - GAP_W * 1.6, self.y - GAP_W * 0.5, self.y + GAP_W * 0.5, self.y + GAP_W * 1.6]

    def inset(self, i):
        return self.i0 <= mirror_index(i) <= self.i1


def build_cage(grooves):
    ys = base_stations()
    for g in grooves:
        ys = [y for y in ys if abs(y - g.y) > GAP_W * 3.0] + g.stations()
    ys.sort()
    bm = bmesh.new()
    crease = bm.edges.layers.float.new("crease_edge")
    rings = []
    station_info = []
    for y in ys:
        pts = full_ring(y)
        groove = next((g for g in grooves if abs(y - g.y) <= GAP_W * 0.6), None)
        verts = []
        for i, (x, yy, z) in enumerate(pts):
            if groove is not None and groove.inset(i):
                # push the groove floor inwards along the section's local outward normal
                px, _, pz = pts[(i - 1) % N_RING]
                nx_, _, nz_ = pts[(i + 1) % N_RING]
                tx, tz = nx_ - px, nz_ - pz
                ln = math.hypot(tx, tz) or 1e-6
                # section runs bottom-centre -> right side -> top -> left side (counter-clockwise seen from +y)
                ox, oz = tz / ln, -tx / ln
                if ox * x + oz * (z - 0.6) < 0:
                    ox, oz = -ox, -oz
                x -= ox * GAP_D
                z -= oz * GAP_D
            verts.append(bm.verts.new((x, yy, z)))
        rings.append(verts)
        station_info.append({"y": y, "groove": groove is not None, "edge": any(abs(y - s) < 1e-6 for g in grooves for s in (g.stations()[0], g.stations()[3]))})
    # Bumper faces: concentric quad rings instead of a single n-gon cap, so the nose and tail
    # subdivide into a smooth, slightly bulged face.
    def cap_rings(y_end, sign):
        base = full_ring(y_end)
        zs = [z for (_, _, z) in base]
        zc = (min(zs) + max(zs)) / 2
        rx = max(abs(x) for (x, _, _) in base)
        rz = (max(zs) - min(zs)) / 2
        out = []
        # Inner rings relax from the squarish end ring towards an ellipse, so the face domes
        # smoothly instead of folding along lines from the corners.
        # Planar face: any forward bulge makes a shallow pyramid whose diagonals subdivide into ridges.
        for sk, bulge, relax in ((0.62, 0.0, 0.55), (0.30, 0.0, 1.0)):
            ring = []
            for (x, _, z) in base:
                a = math.atan2((z - zc) / max(rz, 1e-6), x / max(rx, 1e-6))
                ex, ez = rx * math.cos(a), zc + rz * math.sin(a)
                px, pz = x + (ex - x) * relax, z + (ez - z) * relax
                ring.append(bm.verts.new((px * sk, y_end + sign * bulge, zc + (pz - zc) * sk)))
            out.append(ring)
        return out
    front_caps = cap_rings(ys[-1], 1)
    rear_caps = cap_rings(ys[0], -1)
    rings = list(reversed(rear_caps)) + rings + front_caps
    ys = [ys[0] - 0.026, ys[0] - 0.014] + ys + [ys[-1] + 0.014, ys[-1] + 0.026]
    pad = {"y": 0.0, "groove": False, "edge": False}
    station_info = [pad, pad] + station_info + [pad, pad]
    faces = {}
    for s in range(len(rings) - 1):
        for i in range(N_RING):
            k = (i + 1) % N_RING
            f = bm.faces.new((rings[s][i], rings[s][k], rings[s + 1][k], rings[s + 1][i]))
            faces[(s, i)] = f
    # end caps
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Creases: longitudinal character lines and the groove rims.
    def ring_edge(s, i):
        a, b = rings[s][i], rings[s][(i + 1) % N_RING]
        return next((e for e in a.link_edges if e.other_vert(a) is b), None)

    def long_edge(s, i):
        a, b = rings[s][i], rings[s + 1][i]
        return next((e for e in a.link_edges if e.other_vert(a) is b), None)

    line_crease = {SHOULDER: 0.95, SILL_B: 0.7, SILL_T: 0.3, LOWER: 0.0, CANT: 0.55, BELT: 0.35, G1: 0.9, G0: 0.6, G2: 0.6}
    for s in range(len(rings) - 1):
        y_mid = (ys[s] + ys[s + 1]) / 2
        for i in range(N_RING):
            li = mirror_index(i)
            c = line_crease.get(li, 0.0)
            if li in (G0, G1, G2) and (greenhouse(y_mid) or not (Y_REAR + 0.36 < y_mid < Y_FRONT - 0.36)):
                c = 0.0   # glass on the greenhouse; plain crown beyond the hood/trunk edge grooves
            if li == BELT and not greenhouse(y_mid):
                c = 0.6   # hood/fender shoulder edge
            in_arch = any(abs(y_mid - axle) < R_ARCH for axle in (AXLE_F, AXLE_R))
            if in_arch and li == LOWER:
                c = 0.7    # the arch lip
            if c and li in (SHOULDER, SILL_B, SILL_T, BELT):
                # character lines fade out over the last 0.5 m so they do not wrap the bumpers
                c *= smooth(0.0, 0.5, min(y_mid - Y_REAR, Y_FRONT - y_mid))
            if c:
                e = long_edge(s, i)
                if e: e[crease] = c
    for s, info in enumerate(station_info):
        if info["groove"] or info["edge"]:
            for i in range(N_RING):
                if any(g.inset(i) and abs(ys[s] - g.y) <= GAP_W * 1.7 for g in grooves):
                    e = ring_edge(s, i)
                    if e: e[crease] = 1.0
    return bm, rings, ys, faces


def zone(y_mid, li):
    """Material zone for a cage face: 0 paint, 1 glass, 2 trim/black."""
    if greenhouse(y_mid) and G0 <= li <= G2:
        # pillars stay paint: A (windscreen edges handled by geometry), B, C
        if Y_B_PILLAR - 0.07 < y_mid < Y_B_PILLAR + 0.05:
            return 0
        if Y_A_PILLAR < y_mid < Y_COWL and li >= G1:
            return 1   # windscreen
        if Y_A_PILLAR < y_mid < Y_COWL:
            return 0   # A-pillar base / scuttle
        if Y_TRUNK < y_mid < Y_C_PILLAR and li <= G1:
            return 0   # C pillar / rear quarter
        return 1
    if li <= SILL_B and (y_mid > Y_BUMPER_F or y_mid < Y_BUMPER_R):
        return 2   # lower bumper skirt
    return 0


def build_body(name="Body", materials=None, subdiv=2):
    grooves = [Groove(g, SILL_B, BELT) for g in GAPS]
    grooves += [Groove(Y_COWL - 0.02, G0, ROOF_C), Groove(Y_FRONT - 0.36, G0, ROOF_C)]   # hood rear / front edge
    grooves += [Groove(Y_TRUNK + 0.01, G0, ROOF_C), Groove(Y_REAR + 0.36, G0, ROOF_C)]   # trunk lid edges
    grooves += [Groove(Y_BUMPER_F, FLOOR_E, MID), Groove(Y_BUMPER_R, FLOOR_E, MID)]
    bm, rings, ys, faces = build_cage(grooves)
    for (s, i), f in faces.items():
        f.material_index = zone((ys[s] + ys[s + 1]) / 2, mirror_index(i))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in (materials or []):
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    mod = o.modifiers.new("Subdivision", "SUBSURF")
    mod.levels = subdiv
    mod.render_levels = subdiv
    mod.use_creases = True if hasattr(mod, "use_creases") else None
    return o


def apply_modifiers(o):
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def separate_material(o, index, new_name):
    """Split the faces with material index `index` off into a new object."""
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    o.active_material_index = index
    bpy.ops.object.material_slot_select()
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    new = [x for x in bpy.context.selected_objects if x is not o][0]
    new.name = new_name
    return new


def arch_flange(body, sx, y, radius, depth=0.028, lip=0.006):
    """Turn the raw arch cut into a real wheel-arch lip: extrude the opening edge inward
    (towards the car centre) by `depth`, with a slight radial step `lip`. Hides the stair-step
    boolean edge and gives the arch a visible rolled rim like a pressed fender."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    # The boolean leaves slivers along the cut; dissolve them so the rim is an even polyline.
    bmesh.ops.dissolve_degenerate(bm, dist=0.003, edges=bm.edges)
    centre = Vector((0.0, y, WHEEL_R))
    edges = []
    for e in bm.edges:
        if not e.is_boundary:
            continue
        v = e.verts[0].co
        if sx * v.x < 0.5:
            continue
        r = math.hypot(v.y - y, v.z - WHEEL_R)
        if abs(r - radius) < 0.06:
            edges.append(e)
    if not edges:
        bm.free()
        return
    # Re-space the rim vertices evenly along the exact circle: the boolean leaves them at
    # irregular intervals, and an uneven rim polyline shades as scallops after the flange.
    rim = {v for e in edges for v in e.verts}
    def ang(v):
        return math.atan2(v.co.z - WHEEL_R, v.co.y - y)
    ordered = sorted(rim, key=ang)
    # the opening is an arc open at the bottom: find the largest angular gap and start after it
    angs = [ang(v) for v in ordered]
    gaps = [((angs[(i + 1) % len(angs)] - angs[i]) % math.tau, i) for i in range(len(angs))]
    big, start = max(gaps)
    ordered = ordered[start + 1:] + ordered[:start + 1]
    a0 = ang(ordered[0])
    span = math.tau - big
    for k, v in enumerate(ordered):
        a = a0 + span * k / (len(ordered) - 1)
        v.co.y = y + radius * math.cos(a)
        v.co.z = WHEEL_R + radius * math.sin(a)
    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    new_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in new_verts:
        radial = Vector((0.0, v.co.y - y, v.co.z - WHEEL_R))
        if radial.length > 1e-6:
            radial.normalize()
        v.co.x -= sx * depth
        v.co += radial * (-lip)
    # Rim stays smooth-shaded: a hard edge on an uneven boolean polyline reads as scallops.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(body.data)
    bm.free()
    for p in body.data.polygons:
        p.use_smooth = True


def cut_wheel_arches(body, radius_margin=0.042, liner_material=None):
    for y in (AXLE_F, AXLE_R):
        for sx in (-1, 1):
            cutter_me = bpy.data.meshes.new("cutter")
            cb = bmesh.new()
            bmesh.ops.create_cone(cb, cap_ends=True, segments=128, radius1=WHEEL_R + radius_margin, radius2=WHEEL_R + radius_margin, depth=0.7)
            bmesh.ops.rotate(cb, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"), verts=cb.verts)
            cb.to_mesh(cutter_me)
            cb.free()
            cutter = bpy.data.objects.new("cutter", cutter_me)
            cutter.location = (sx * (TRACK_X + 0.08), y, WHEEL_R)
            bpy.context.scene.collection.objects.link(cutter)
            bpy.data.objects.remove(cutter, do_unlink=True)   # arches are built into the cage (arch_section)
            if liner_material is not None:
                # Arc liner (open at the bottom, ends just inside the fender surface).
                lb = bmesh.new()
                rl = R_ARCH - 0.012                   # just inside the flange
                n = 64
                a0 = math.asin(max(-1.0, (0.04 - WHEEL_R) / rl))      # start just above the ground
                angles = [a0 + (math.pi - 2 * a0) * i / (n - 1) for i in range(n)]
                x_in, x_out = sx * (TRACK_X - 0.34), sx * (half_width(y) + flare(y) - 0.012)   # ends just inside the fender skin
                ring_in = [lb.verts.new((x_in, y + rl * math.cos(a), WHEEL_R + rl * math.sin(a))) for a in angles]
                ring_out = [lb.verts.new((x_out, y + rl * math.cos(a), WHEEL_R + rl * math.sin(a))) for a in angles]
                for i in range(n - 1):
                    lb.faces.new((ring_in[i], ring_in[i + 1], ring_out[i + 1], ring_out[i]))
                lb.faces.new(ring_in + [lb.verts.new((x_in, y, 0.04))])
                bmesh.ops.recalc_face_normals(lb, faces=lb.faces)
                for f in lb.faces:
                    f.normal_flip()
                me = bpy.data.meshes.new("ArchLiner")
                lb.to_mesh(me)
                lb.free()
                me.materials.append(liner_material)
                for p in me.polygons:
                    p.use_smooth = True
                liner = bpy.data.objects.new("ArchLiner", me)
                bpy.context.scene.collection.objects.link(liner)
