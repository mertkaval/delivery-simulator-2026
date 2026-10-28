"""CityForge archetype kit: houses, garage, street furniture and trees, each with a LOD1.

Every function fills a geo.Mesh in the model's local frame: origin on the ground at the footprint
centre, front towards +Y, metres. Houses are built at the nominal footprint HOUSE_W x HOUSE_D and
scaled per instance to the planned size. `lod=1` drops the small parts (frames, columns, steps)
and turns windows into flat panes, so the silhouette and window pattern survive at distance.

Material names are the contract with Godot (world/cityforge/cityforge_materials.gd):
  CF_Siding  tinted per instance (MultiMesh colour)   CF_Roof  tinted per instance (custom data)
  CF_Leaves  tinted per instance (colour)             the rest are fixed materials.
"""
import math
from geo import Mesh

HOUSE_W, HOUSE_D = 10.0, 12.0
ARCHETYPES = ["craftsman", "vancouver_special", "bungalow", "modern_box", "foursquare", "tudor", "split_level", "west_coast"]


# --- wall-face helpers -----------------------------------------------------------------------
class Face:
    """One outside wall: plane position, outward axis and the horizontal axis along it."""
    def __init__(self, side, x0, y0, x1, y1):
        self.side = side
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def P(self, u, z, o):
        s = self.side
        if s == "front": return (u, self.y1 + o, z)
        if s == "back": return (-u, self.y0 - o, z)
        if s == "right": return (self.x1 + o, -u, z)
        return (self.x0 - o, u, z)

    def box(self, m, u0, z0, o0, u1, z1, o1, mat):
        a, b = self.P(u0, z0, o0), self.P(u1, z1, o1)
        m.box(min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]), max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]), mat)

    def pane(self, m, u0, z0, u1, z1, o, mat):
        """Flat quad on the wall, facing out."""
        q = [self.P(u0, z0, o), self.P(u1, z0, o), self.P(u1, z1, o), self.P(u0, z1, o)]
        m.poly(q, mat)

    @property
    def length(self):
        return (self.x1 - self.x0) if self.side in ("front", "back") else (self.y1 - self.y0)


def faces(x0, y0, x1, y1):
    return {s: Face(s, x0, y0, x1, y1) for s in ("front", "back", "left", "right")}


def window(m, f, u, z0, w, h, lod, mullion=True, frame="CF_Trim"):
    if lod:
        f.pane(m, u - w / 2, z0, u + w / 2, z0 + h, 0.03, "CF_Glass")
        return
    f.box(m, u - w / 2, z0, -0.04, u + w / 2, z0 + h, 0.01, "CF_Glass")
    t = 0.09
    f.box(m, u - w / 2 - t, z0 + h, 0.0, u + w / 2 + t, z0 + h + t, 0.07, frame)       # head
    f.box(m, u - w / 2 - t - 0.04, z0 - 0.07, 0.0, u + w / 2 + t + 0.04, z0, 0.11, frame)  # sill
    f.box(m, u - w / 2 - t, z0, 0.0, u - w / 2, z0 + h, 0.07, frame)
    f.box(m, u + w / 2, z0, 0.0, u + w / 2 + t, z0 + h, 0.07, frame)
    if mullion and w > 0.9:
        f.box(m, u - 0.025, z0, 0.0, u + 0.025, z0 + h, 0.04, frame)
    if mullion and h > 1.1:
        f.box(m, u - w / 2, z0 + h * 0.62 - 0.025, 0.0, u + w / 2, z0 + h * 0.62 + 0.025, 0.04, frame)


def door(m, f, u, z0, lod, w=1.0, h=2.15, glass=False):
    if lod:
        f.pane(m, u - w / 2, z0, u + w / 2, z0 + h, 0.03, "CF_Door")
        return
    f.box(m, u - w / 2, z0, -0.06, u + w / 2, z0 + h, 0.0, "CF_Door")
    if glass: f.box(m, u - w / 2 + 0.18, z0 + h * 0.55, -0.05, u + w / 2 - 0.18, z0 + h - 0.2, 0.005, "CF_Glass")
    t = 0.1
    f.box(m, u - w / 2 - t, z0 + h, 0.0, u + w / 2 + t, z0 + h + t, 0.08, "CF_Trim")
    f.box(m, u - w / 2 - t, z0, 0.0, u - w / 2, z0 + h, 0.08, "CF_Trim")
    f.box(m, u + w / 2, z0, 0.0, u + w / 2 + t, z0 + h, 0.08, "CF_Trim")


def steps(m, f, u, z_top, w, lod, start=0.0):
    """Stairs down from z_top to the ground, starting `start` metres out from the wall."""
    n = max(1, int(round(z_top / 0.18)))
    if lod:
        f.box(m, u - w / 2, -0.3, start, u + w / 2, z_top, start + n * 0.28, "CF_Concrete")
        return
    for k in range(n):
        top = z_top - k * (z_top / n)
        f.box(m, u - w / 2, -0.3, start + k * 0.28, u + w / 2, top, start + (k + 1) * 0.28, "CF_Concrete")


# --- roofs -----------------------------------------------------------------------------------
def gable_x(m, x0, x1, y0, y1, z, h, oh, gable_mat="CF_Siding", roof="CF_Roof"):
    """Gable roof, ridge along X over [x0,x1]x[y0,y1], eaves at z, ridge h above."""
    ym = (y0 + y1) / 2
    s = h / ((y1 - y0) / 2)
    ze, zr = z - oh * s, z + h
    xa, xb, ya, yb = x0 - oh, x1 + oh, y0 - oh, y1 + oh
    th = 0.16
    m.poly([(xa, ya, ze), (xb, ya, ze), (xb, ym, zr), (xa, ym, zr)], roof)
    m.poly([(xa, yb, ze), (xa, ym, zr), (xb, ym, zr), (xb, yb, ze)], roof)
    m.poly([(xa, ya, ze - th), (xa, ym, zr - th), (xb, ym, zr - th), (xb, ya, ze - th)], "CF_Trim")
    m.poly([(xa, yb, ze - th), (xb, yb, ze - th), (xb, ym, zr - th), (xa, ym, zr - th)], "CF_Trim")
    m.poly([(xa, ya, ze - th), (xb, ya, ze - th), (xb, ya, ze), (xa, ya, ze)], "CF_Trim")
    m.poly([(xa, yb, ze - th), (xa, yb, ze), (xb, yb, ze), (xb, yb, ze - th)], "CF_Trim")
    for x, sgn in ((xa, -1), (xb, 1)):
        a = [(x, ya, ze - th), (x, ya, ze), (x, ym, zr), (x, yb, ze), (x, yb, ze - th), (x, ym, zr - th)]
        if sgn < 0:
            m.poly([a[0], a[1], a[2], a[5]], "CF_Trim"); m.poly([a[5], a[2], a[3], a[4]], "CF_Trim")
        else:
            m.poly([a[5], a[2], a[1], a[0]], "CF_Trim"); m.poly([a[4], a[3], a[2], a[5]], "CF_Trim")
    if gable_mat:
        m.poly([(x0, y0, z), (x0, ym, zr), (x0, y1, z)], gable_mat, zb=0.0)
        m.poly([(x1, y0, z), (x1, y1, z), (x1, ym, zr)], gable_mat, zb=0.0)


def gable_y(m, x0, x1, y0, y1, z, h, oh, gable_mat="CF_Siding", roof="CF_Roof"):
    """Gable roof with the ridge along Y (gable end towards the front)."""
    sub = Mesh()
    gable_x(sub, y0, y1, -x1, -x0, z, h, oh, gable_mat, roof)
    m.append(sub, math.pi / 2)


def hip(m, x0, x1, y0, y1, z, h, oh, roof="CF_Roof"):
    if (x1 - x0) < (y1 - y0):
        sub = Mesh()
        hip(sub, y0, y1, -x1, -x0, z, h, oh, roof)
        m.append(sub, math.pi / 2)
        return
    ym = (y0 + y1) / 2
    s = h / ((y1 - y0) / 2)
    ze, zr = z - oh * s, z + h
    xa, xb, ya, yb = x0 - oh, x1 + oh, y0 - oh, y1 + oh
    half = (yb - ya) / 2
    r0, r1 = xa + half, xb - half
    if r1 < r0: r0 = r1 = (xa + xb) / 2
    m.poly([(xa, ya, ze), (xb, ya, ze), (r1, ym, zr), (r0, ym, zr)], roof)
    m.poly([(xa, yb, ze), (r0, ym, zr), (r1, ym, zr), (xb, yb, ze)], roof)
    m.poly([(xa, ya, ze), (r0, ym, zr), (xa, yb, ze)], roof)
    m.poly([(xb, ya, ze), (xb, yb, ze), (r1, ym, zr)], roof)
    m.poly([(xa, ya, ze - 0.14), (xa, yb, ze - 0.14), (xb, yb, ze - 0.14), (xb, ya, ze - 0.14)], "CF_Trim")
    for q in ([(xa, ya, ze - 0.14), (xb, ya, ze - 0.14), (xb, ya, ze), (xa, ya, ze)], [(xa, yb, ze - 0.14), (xa, yb, ze), (xb, yb, ze), (xb, yb, ze - 0.14)],
              [(xa, ya, ze - 0.14), (xa, ya, ze), (xa, yb, ze), (xa, yb, ze - 0.14)], [(xb, ya, ze - 0.14), (xb, yb, ze - 0.14), (xb, yb, ze), (xb, ya, ze)]):
        m.poly(q, "CF_Trim")


def flat_roof(m, x0, x1, y0, y1, z, parapet=0.5, mat="CF_Concrete", edge="CF_Trim"):
    m.box(x0, y0, z, x1, y1, z + 0.12, "CF_RoofFlat")
    t = 0.25
    m.box(x0 - 0.05, y0 - 0.05, z, x1 + 0.05, y0 + t, z + parapet, edge)
    m.box(x0 - 0.05, y1 - t, z, x1 + 0.05, y1 + 0.05, z + parapet, edge)
    m.box(x0 - 0.05, y0 + t, z, x0 + t, y1 - t, z + parapet, edge)
    m.box(x1 - t, y0 + t, z, x1 + 0.05, y1 - t, z + parapet, edge)


def chimney(m, x, y, z0, z1, lod):
    m.box(x - 0.35, y - 0.45, z0, x + 0.35, y + 0.45, z1, "CF_Brick")
    if not lod: m.box(x - 0.42, y - 0.52, z1, x + 0.42, y + 0.52, z1 + 0.12, "CF_Concrete")


def porch(m, x0, x1, y0, depth, floor_z, roof_z, lod, cols=4, roof="shed", col_w=0.32):
    """Front porch: deck, columns, a roof and a railing-less open front (steps added separately)."""
    y1 = y0 + depth
    m.box(x0, y0, -0.4, x1, y1, floor_z, "CF_Concrete" if floor_z < 0.35 else "CF_Wood")
    if not lod:
        for k in range(cols):
            x = x0 + 0.25 + (x1 - x0 - 0.5) * k / max(1, cols - 1)
            m.box(x - col_w / 2 - 0.08, y1 - 0.55, floor_z, x + col_w / 2 + 0.08, y1 - 0.55 + col_w + 0.16, floor_z + 0.9, "CF_Brick" if col_w > 0.3 else "CF_Trim")
            m.box(x - col_w / 2, y1 - 0.55 + 0.08, floor_z + 0.9, x + col_w / 2, y1 - 0.55 + 0.08 + col_w, roof_z, "CF_Trim")
    else:
        for x in (x0 + 0.3, x1 - 0.3):
            m.box(x - 0.2, y1 - 0.5, floor_z, x + 0.2, y1 - 0.1, roof_z, "CF_Trim")
    if roof == "shed":
        sub_top = roof_z + 0.6
        m.poly([(x0 - 0.2, y1 + 0.3, roof_z), (x1 + 0.2, y1 + 0.3, roof_z), (x1 + 0.2, y0, sub_top), (x0 - 0.2, y0, sub_top)], "CF_Roof")
        m.poly([(x0 - 0.2, y1 + 0.3, roof_z - 0.15), (x0 - 0.2, y0, sub_top - 0.15), (x1 + 0.2, y0, sub_top - 0.15), (x1 + 0.2, y1 + 0.3, roof_z - 0.15)], "CF_Trim")
        m.poly([(x0 - 0.2, y1 + 0.3, roof_z - 0.15), (x1 + 0.2, y1 + 0.3, roof_z - 0.15), (x1 + 0.2, y1 + 0.3, roof_z), (x0 - 0.2, y1 + 0.3, roof_z)], "CF_Trim")
    elif roof == "gable":
        gable_y(m, x0, x1, y0, y1 + 0.2, roof_z, (x1 - x0) * 0.32, 0.25, gable_mat="CF_Trim")
    elif roof == "hip":
        hip(m, x0, x1, y0 + 0.01, y1, roof_z, 1.0, 0.3)
    elif roof == "flat":
        m.box(x0 - 0.2, y0, roof_z, x1 + 0.2, y1 + 0.3, roof_z + 0.25, "CF_Trim")


# --- houses ----------------------------------------------------------------------------------
W2, D2 = HOUSE_W / 2, HOUSE_D / 2


def body(m, x0, y0, x1, y1, z0, z1, mat="CF_Siding"):
    m.box(x0, y0, -0.6, x1, y1, max(z0, 0.05), "CF_Concrete", top=False)
    m.box(x0, y0, z0, x1, y1, z1, mat, top=False, zb=z0)


def side_windows(m, f, z0, h, n, w, lod, margin=1.4):
    L = f.length
    for k in range(n):
        u = -L / 2 + margin + (L - 2 * margin) * (k + 0.5) / n
        window(m, f, u, z0, w, h, lod)


def craftsman(m, lod):
    fz = 0.75
    body(m, -W2, -D2, W2, D2 - 2.6, fz, fz + 3.0)
    F = faces(-W2, -D2, W2, D2 - 2.6)
    gable_y(m, -W2, W2, -D2, D2 - 2.6, fz + 3.0, 3.1, 0.55)
    porch(m, -W2 + 0.3, W2 - 0.3, D2 - 2.6, 2.6, fz, fz + 2.75, lod, cols=3, roof="gable", col_w=0.38)
    window(m, F["front"], -2.6, fz + 0.85, 1.9, 1.5, lod)
    window(m, F["front"], 2.4, fz + 0.85, 1.3, 1.5, lod)
    door(m, F["front"], 0.2, fz, lod, glass=True)
    window(m, F["front"], 0.0, fz + 3.6, 1.6, 1.0, lod)           # attic gable window
    side_windows(m, F["left"], fz + 0.9, 1.35, 3, 1.0, lod)
    side_windows(m, F["right"], fz + 0.9, 1.35, 3, 1.0, lod)
    side_windows(m, F["back"], fz + 0.9, 1.3, 2, 1.2, lod)
    steps(m, Face("front", -W2, -D2, W2, D2), 0.2, fz, 1.6, lod)
    chimney(m, -W2 + 0.2, -1.0, fz + 2.0, fz + 6.6, lod)


def vancouver_special(m, lod):
    g, u = 2.6, 2.7
    body(m, -W2, -D2, W2, D2, 0.1, g, "CF_Brick")
    m.box(-W2, -D2, g, W2, D2, g + u, "CF_Siding", top=False, zb=g)
    F = faces(-W2, -D2, W2, D2)
    gable_x(m, -W2, W2, -D2, D2, g + u, 1.5, 0.7)
    # the upper balcony across the middle of the front, iron railing, on two brick piers
    m.box(-3.2, D2, g - 0.05, 3.2, D2 + 1.6, g + 0.15, "CF_Concrete")
    if not lod:
        for x in (-3.0, 2.8):
            m.box(x, D2 + 1.2, 0.0, x + 0.4, D2 + 1.6, g - 0.05, "CF_Brick")
        m.box(-3.2, D2 + 1.52, g + 0.15, 3.2, D2 + 1.58, g + 1.1, "CF_Metal")
        m.box(-3.2, D2, g + 1.05, -3.14, D2 + 1.6, g + 1.1, "CF_Metal")
        m.box(3.14, D2, g + 1.05, 3.2, D2 + 1.6, g + 1.1, "CF_Metal")
    window(m, F["front"], -3.6, g + 0.8, 1.8, 1.4, lod, frame="CF_Metal")
    window(m, F["front"], 0.0, g + 0.3, 2.4, 2.1, lod, frame="CF_Metal")    # balcony slider
    window(m, F["front"], 3.6, g + 0.8, 1.8, 1.4, lod, frame="CF_Metal")
    window(m, F["front"], -3.4, 0.9, 1.6, 1.2, lod, frame="CF_Metal")
    window(m, F["front"], 3.4, 0.9, 1.6, 1.2, lod, frame="CF_Metal")
    door(m, F["front"], 0.0, 0.1, lod, w=1.1)
    side_windows(m, F["left"], g + 0.8, 1.3, 3, 1.4, lod)
    side_windows(m, F["right"], g + 0.8, 1.3, 3, 1.4, lod)
    side_windows(m, F["back"], g + 0.8, 1.3, 3, 1.4, lod)
    side_windows(m, F["back"], 0.9, 1.1, 2, 1.2, lod)


def bungalow(m, lod):
    fz = 0.5
    body(m, -W2, -D2, W2, D2, fz, fz + 2.9)
    F = faces(-W2, -D2, W2, D2)
    hip(m, -W2, W2, -D2, D2, fz + 2.9, 2.5, 0.6)
    porch(m, 1.0, 4.2, D2, 1.8, fz, fz + 2.5, lod, cols=2, roof="gable", col_w=0.2)
    window(m, F["front"], -2.4, fz + 0.75, 2.8, 1.5, lod)           # picture window
    door(m, F["front"], 2.6, fz, lod)
    side_windows(m, F["left"], fz + 0.9, 1.3, 3, 1.0, lod)
    side_windows(m, F["right"], fz + 0.9, 1.3, 3, 1.0, lod)
    side_windows(m, F["back"], fz + 0.9, 1.2, 3, 1.0, lod)
    steps(m, Face("front", -W2, -D2, W2, D2 + 1.8), 2.6, fz, 1.4, lod)
    chimney(m, W2 - 1.0, -2.0, fz + 2.0, fz + 5.6, lod)


def modern_box(m, lod):
    g, u = 3.0, 3.0
    body(m, -W2, -D2, W2 - 1.5, D2 - 1.2, 0.15, g, "CF_Siding")
    m.box(-W2, -D2, g, W2, D2, g + u, "CF_Wood", top=False, zb=g)           # upper floor cantilevers
    m.box(-W2, -D2, g - 0.25, W2, D2, g, "CF_Trim")
    flat_roof(m, -W2, W2, -D2, D2, g + u, 0.35, edge="CF_Trim")
    F1 = faces(-W2, -D2, W2 - 1.5, D2 - 1.2)
    F2 = faces(-W2, -D2, W2, D2)
    if lod:
        F2["front"].pane(m, -4.3, g + 0.4, 2.8, g + 2.6, 0.03, "CF_Glass")
        F1["front"].pane(m, -4.3, 0.3, -0.2, 2.6, 0.03, "CF_Glass")
    else:
        F2["front"].box(m, -4.3, g + 0.4, -0.05, 2.8, g + 2.6, 0.0, "CF_Glass")
        for x in (-4.3, -1.9, 0.5, 2.8):
            F2["front"].box(m, x - 0.04, g + 0.4, 0.0, x + 0.04, g + 2.6, 0.05, "CF_Metal")
        F1["front"].box(m, -4.3, 0.3, -0.05, -0.2, 2.6, 0.0, "CF_Glass")
    door(m, F1["front"], 1.6, 0.15, lod, w=1.2, h=2.4)
    window(m, F2["left"], 0.0, g + 0.9, 3.5, 1.1, lod, mullion=False, frame="CF_Metal")
    window(m, F2["right"], 2.0, g + 0.9, 2.0, 1.1, lod, mullion=False, frame="CF_Metal")
    window(m, F2["back"], 0.0, g + 0.5, 5.0, 2.0, lod, mullion=False, frame="CF_Metal")
    window(m, F1["back"], 1.0, 0.3, 4.0, 2.3, lod, mullion=False, frame="CF_Metal")
    if not lod:
        m.box(-W2 + 0.4, D2 - 1.2, -0.2, W2 - 1.9, D2 + 0.6, 0.15, "CF_Concrete")  # front terrace


def foursquare(m, lod):
    fz, fl = 0.7, 2.9
    body(m, -W2, -D2, W2, D2 - 2.4, fz, fz + 2 * fl)
    F = faces(-W2, -D2, W2, D2 - 2.4)
    hip(m, -W2, W2, -D2, D2 - 2.4, fz + 2 * fl, 2.6, 0.7)
    # front dormer
    m.box(-1.3, D2 - 3.9, fz + 2 * fl, 1.3, D2 - 2.9, fz + 2 * fl + 1.5, "CF_Siding", zb=fz + 2 * fl)
    hip(m, -1.3, 1.3, D2 - 5.0, D2 - 2.9, fz + 2 * fl + 1.5, 0.6, 0.2)
    window(m, Face("front", -1.3, D2 - 5, 1.3, D2 - 2.9), 0.0, fz + 2 * fl + 0.35, 1.4, 0.8, lod)
    porch(m, -W2, W2, D2 - 2.4, 2.4, fz, fz + fl - 0.2, lod, cols=4, roof="hip", col_w=0.28)
    door(m, F["front"], -2.4, fz, lod, glass=True)
    window(m, F["front"], 1.9, fz + 0.8, 2.2, 1.5, lod)
    for x in (-2.6, 2.6):
        window(m, F["front"], x, fz + fl + 0.8, 1.2, 1.4, lod)
    for side in ("left", "right", "back"):
        side_windows(m, F[side], fz + 0.85, 1.4, 3, 1.0, lod)
        side_windows(m, F[side], fz + fl + 0.85, 1.3, 3, 1.0, lod)
    steps(m, Face("front", -W2, -D2, W2, D2), -2.4, fz, 1.6, lod)
    chimney(m, -W2 + 0.2, -2.5, fz + 4.0, fz + 2 * fl + 3.4, lod)


def tudor(m, lod):
    fz = 0.45
    body(m, -W2, -D2, W2, D2 - 1.4, fz, fz + 2.8, "CF_Brick")
    F = faces(-W2, -D2, W2, D2 - 1.4)
    gable_x(m, -W2, W2, -D2, D2 - 1.4, fz + 2.8, 4.4, 0.4)
    # steep front cross-gable, projecting
    body(m, -4.6, D2 - 1.6, -0.6, D2, fz, fz + 2.8, "CF_Brick")
    gable_y(m, -4.6, -0.6, D2 - 5.0, D2, fz + 2.8, 3.6, 0.35, gable_mat="CF_Siding")
    if not lod:                                       # half-timbering on the front gable
        for k, x in enumerate((-4.2, -3.4, -2.6, -1.8, -1.0)):
            top = fz + 2.8 + 3.6 * (1 - abs(x + 2.6) / 2.0) - 0.15
            m.box(x - 0.07, D2 + 0.0, fz + 2.8, x + 0.07, D2 + 0.06, max(fz + 3.0, top), "CF_Wood")
        m.box(-4.6, D2, fz + 2.75, -0.6, D2 + 0.06, fz + 2.95, "CF_Wood")
    Fc = Face("front", -4.6, D2 - 1.6, -0.6, D2)
    window(m, Fc, -2.6, fz + 0.8, 2.0, 1.4, lod)
    window(m, Fc, -2.6, fz + 3.4, 0.9, 1.1, lod)
    door(m, F["front"], 1.2, fz, lod, w=1.0, h=2.2)
    window(m, F["front"], 3.4, fz + 0.9, 1.4, 1.3, lod)
    side_windows(m, F["left"], fz + 0.9, 1.3, 2, 1.0, lod)
    side_windows(m, F["right"], fz + 0.9, 1.3, 2, 1.0, lod)
    window(m, F["left"], 0.0, fz + 3.6, 1.0, 1.0, lod)
    window(m, F["right"], 0.0, fz + 3.6, 1.0, 1.0, lod)
    side_windows(m, F["back"], fz + 0.9, 1.2, 3, 1.0, lod)
    steps(m, Face("front", -W2, -D2, W2, D2 - 1.4), 1.2, fz, 1.3, lod)
    chimney(m, W2 - 0.3, -1.0, fz + 2.0, fz + 8.2, lod)


def split_level(m, lod):
    # two-storey half on the left, one-storey wing with an attached garage on the right
    body(m, -W2, -D2, 0.6, D2 - 0.6, 0.2, 5.4)
    gable_x(m, -W2, 0.6, -D2, D2 - 0.6, 5.4, 1.7, 0.6)
    body(m, 0.6, -D2, W2, D2, 0.0, 3.0)
    gable_x(m, 0.6, W2, -D2, D2, 3.0, 1.6, 0.6)
    FL = faces(-W2, -D2, 0.6, D2 - 0.6)
    FR = faces(0.6, -D2, W2, D2)
    if lod:
        FR["front"].pane(m, 0.6, 0.0, 4.6, 2.3, 0.03, "CF_Door")
    else:
        FR["front"].box(m, 0.6, 0.0, -0.06, 4.6, 2.3, 0.0, "CF_Door")
        FR["front"].box(m, 0.5, 2.3, 0.0, 4.7, 2.42, 0.07, "CF_Trim")
    window(m, FL["front"], -4.0, 3.2, 1.6, 1.3, lod)
    window(m, FL["front"], -1.4, 3.2, 1.6, 1.3, lod)
    window(m, FL["front"], -3.6, 0.9, 2.2, 1.3, lod)
    door(m, FL["front"], -0.9, 0.2, lod)
    side_windows(m, FL["left"], 0.9, 1.2, 3, 1.0, lod)
    side_windows(m, FL["left"], 3.2, 1.2, 3, 1.0, lod)
    side_windows(m, FR["right"], 0.9, 1.2, 3, 1.0, lod)
    side_windows(m, FL["back"], 3.2, 1.2, 2, 1.1, lod)
    side_windows(m, FR["back"], 0.9, 1.2, 2, 1.0, lod)
    if not lod: m.box(-1.6, D2 - 0.6, -0.3, -0.2, D2 + 0.4, 0.2, "CF_Concrete")


def west_coast(m, lod):
    lo, hi = 3.0, 5.6
    body(m, -W2, -D2, W2, D2, 0.2, lo, "CF_Wood")
    F = faces(-W2, -D2, W2, D2)
    # front wall rises to the high side of the shed roof
    if not lod:
        F["front"].box(m, -W2, lo, -0.001, W2, hi, 0.0, "CF_Wood")
    else:
        m.poly([(-W2, D2, lo), (W2, D2, lo), (W2, D2, hi), (-W2, D2, hi)], "CF_Wood", zb=0.2)
    for x, sgn in ((-W2, -1), (W2, 1)):
        tri = [(x, -D2, lo), (x, D2, lo), (x, D2, hi)]
        m.poly(tri if sgn > 0 else tri[::-1], "CF_Wood", zb=0.2)
    oh = 1.0
    m.poly([(-W2 - 0.4, -D2 - 0.6, lo - 0.1), (W2 + 0.4, -D2 - 0.6, lo - 0.1), (W2 + 0.4, D2 + oh, hi + 0.25), (-W2 - 0.4, D2 + oh, hi + 0.25)], "CF_Roof")
    m.poly([(-W2 - 0.4, -D2 - 0.6, lo - 0.3), (-W2 - 0.4, D2 + oh, hi + 0.05), (W2 + 0.4, D2 + oh, hi + 0.05), (W2 + 0.4, -D2 - 0.6, lo - 0.3)], "CF_Wood")
    m.poly([(-W2 - 0.4, D2 + oh, hi + 0.05), (-W2 - 0.4, D2 + oh, hi + 0.25), (W2 + 0.4, D2 + oh, hi + 0.25), (W2 + 0.4, D2 + oh, hi + 0.05)], "CF_Trim")
    # tall glass front with timber mullions
    if lod:
        F["front"].pane(m, -4.2, 0.4, 1.8, hi - 0.4, 0.03, "CF_Glass")
    else:
        F["front"].box(m, -4.2, 0.4, -0.05, 1.8, hi - 0.4, 0.0, "CF_Glass")
        for x in (-4.2, -2.2, -0.2, 1.8):
            F["front"].box(m, x - 0.06, 0.4, 0.0, x + 0.06, hi - 0.4, 0.08, "CF_Wood")
        F["front"].box(m, -4.2, 2.8, 0.0, 1.8, 2.92, 0.08, "CF_Wood")
        m.box(-W2, D2, -0.3, W2, D2 + 2.2, 0.2, "CF_Wood")                    # deck
    door(m, F["front"], 3.3, 0.2, lod, w=1.0, h=2.3)
    side_windows(m, F["left"], 0.9, 1.4, 2, 1.6, lod)
    side_windows(m, F["right"], 0.9, 1.4, 2, 1.6, lod)
    side_windows(m, F["back"], 1.0, 1.0, 3, 1.4, lod)


HOUSES = {"craftsman": craftsman, "vancouver_special": vancouver_special, "bungalow": bungalow, "modern_box": modern_box,
          "foursquare": foursquare, "tudor": tudor, "split_level": split_level, "west_coast": west_coast}


def garage(m, lod):
    w, d, h = 6.4, 6.4, 2.7
    m.box(-w / 2, -d / 2, -0.4, w / 2, d / 2, 0.1, "CF_Concrete", top=False)
    m.box(-w / 2, -d / 2, 0.1, w / 2, d / 2, h, "CF_Siding", top=False, zb=0.1)
    gable_x(m, -w / 2, w / 2, -d / 2, d / 2, h, 1.2, 0.35)
    F = Face("front", -w / 2, -d / 2, w / 2, d / 2)
    if lod:
        F.pane(m, -2.5, 0.1, 2.5, 2.25, 0.03, "CF_Door")
    else:
        F.box(m, -2.5, 0.1, -0.08, 2.5, 2.25, 0.0, "CF_Door")
        for k in range(1, 4):
            z = 0.1 + 2.15 * k / 4
            F.box(m, -2.5, z - 0.02, 0.0, 2.5, z + 0.02, 0.015, "CF_Trim")
        F.box(m, -2.62, 2.25, 0.0, 2.62, 2.37, 0.07, "CF_Trim")
        m.box(-w / 2, d / 2, -0.25, w / 2, d / 2 + 1.0, 0.08, "CF_Concrete")   # apron to the lane


# --- street furniture ------------------------------------------------------------------------
def lamp(m, lod):
    """Cobra-head street light: pole at the origin, arm reaching +Y over the road."""
    sides = 6 if lod else 10
    m.cylinder(0, 0, 0.0, 0.5, 0.2, 0.17, "CF_Concrete", sides)
    m.cylinder(0, 0, 0.5, 8.6, 0.11, 0.07, "CF_Metal", sides)
    m.box(-0.05, 0.0, 8.45, 0.05, 2.0, 8.55, "CF_Metal")
    m.box(-0.22, 1.7, 8.4, 0.22, 2.55, 8.62, "CF_Metal")
    m.poly([(-0.18, 1.78, 8.39), (-0.18, 2.5, 8.39), (0.18, 2.5, 8.39), (0.18, 1.78, 8.39)], "CF_LampGlow")


def traffic_light(m, lod):
    """Mast-arm signal: pole on the drivers' right, arm along +X over the lanes, heads facing +Y."""
    sides = 6 if lod else 10
    m.cylinder(0, 0, 0.0, 0.4, 0.3, 0.26, "CF_Concrete", sides)
    m.cylinder(0, 0, 0.4, 6.4, 0.14, 0.11, "CF_SignalPole", sides)
    m.box(0.0, -0.06, 5.75, 7.0, 0.06, 5.9, "CF_SignalPole")
    for x in (3.4, 6.4):
        m.box(x - 0.2, -0.15, 4.7, x + 0.2, 0.12, 5.75, "CF_SignalPole")
        if not lod:
            m.box(x - 0.3, -0.16, 4.62, x + 0.3, -0.13, 5.83, "CF_SignalPole")    # backplate
        for k, mat in enumerate(("CF_SignalRed", "CF_SignalAmber", "CF_SignalGreen")):
            z = 5.5 - k * 0.33
            m.poly([(x - 0.12, 0.125, z - 0.12), (x + 0.12, 0.125, z - 0.12), (x + 0.12, 0.125, z + 0.12), (x - 0.12, 0.125, z + 0.12)], mat)
            if not lod: m.box(x - 0.14, 0.12, z + 0.11, x + 0.14, 0.3, z + 0.14, "CF_SignalPole")   # visor
    # pedestrian head on the pole
    m.box(-0.18, 0.12, 2.7, 0.18, 0.42, 3.15, "CF_SignalPole")
    m.poly([(-0.12, 0.43, 2.76), (0.12, 0.43, 2.76), (0.12, 0.43, 3.09), (-0.12, 0.43, 3.09)], "CF_SignalWalk")
    # street name sign on the arm
    if not lod:
        m.box(1.0, 0.07, 6.0, 2.6, 0.1, 6.35, "CF_SignGreen")


def stop_sign(m, lod):
    m.box(-0.04, -0.04, 0.0, 0.04, 0.04, 2.6, "CF_Metal")
    oct_ = [(0.38 * math.cos(math.pi / 8 + k * math.pi / 4), 0.06, 2.3 + 0.38 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    m.poly(oct_[::-1], "CF_SignRed")
    m.poly([(p[0], 0.04, p[2]) for p in oct_], "CF_SignWhite")


def bus_stop(m, lod):
    """Bus shelter: open side towards +Y (the kerb), sign post at the right."""
    w, d, h = 4.0, 1.6, 2.5
    m.box(-w / 2 - 0.2, -d / 2 - 0.2, -0.05, w / 2 + 0.2, d / 2 + 0.3, 0.05, "CF_Concrete")
    for x in (-w / 2, w / 2):
        for y in (-d / 2, d / 2):
            m.box(x - 0.05, y - 0.05, 0.05, x + 0.05, y + 0.05, h, "CF_Metal")
    if lod:
        m.poly([(-w / 2, -d / 2, 0.3), (w / 2, -d / 2, 0.3), (w / 2, -d / 2, h), (-w / 2, -d / 2, h)][::-1], "CF_Glass")
    else:
        m.box(-w / 2, -d / 2 - 0.01, 0.3, w / 2, -d / 2 + 0.01, h - 0.05, "CF_Glass")
        m.box(w / 2 - 0.01, -d / 2, 0.3, w / 2 + 0.01, d / 2 - 0.4, h - 0.05, "CF_Glass")
        m.box(-w / 2 + 0.4, -d / 2 + 0.05, 0.45, w / 2 - 0.4, -d / 2 + 0.45, 0.5, "CF_Wood")   # bench
        m.box(-w / 2 + 0.4, -d / 2 + 0.05, 0.5, w / 2 - 0.4, -d / 2 + 0.1, 0.9, "CF_Wood")
    m.box(-w / 2 - 0.15, -d / 2 - 0.15, h, w / 2 + 0.15, d / 2 + 0.25, h + 0.15, "CF_Metal")
    m.box(w / 2 + 0.6, d / 2 + 0.1, 0.0, w / 2 + 0.68, d / 2 + 0.18, 2.9, "CF_Metal")
    m.box(w / 2 + 0.36, d / 2 + 0.1, 2.3, w / 2 + 0.92, d / 2 + 0.16, 2.9, "CF_SignBlue")


def hydrant(m, lod):
    s = 6 if lod else 10
    m.cylinder(0, 0, 0.0, 0.08, 0.16, 0.16, "CF_Hydrant", s)
    m.cylinder(0, 0, 0.08, 0.62, 0.12, 0.12, "CF_Hydrant", s)
    m.cylinder(0, 0, 0.62, 0.8, 0.13, 0.04, "CF_HydrantCap", s)
    if not lod:
        m.box(-0.22, -0.05, 0.38, 0.22, 0.05, 0.48, "CF_HydrantCap")
        m.box(-0.06, 0.1, 0.32, 0.06, 0.2, 0.46, "CF_HydrantCap")


def bench(m, lod):
    m.box(-0.9, -0.25, 0.42, 0.9, 0.25, 0.47, "CF_Wood")
    m.box(-0.9, -0.28, 0.5, 0.9, -0.22, 0.9, "CF_Wood")
    for x in (-0.75, 0.75):
        m.box(x - 0.04, -0.28, 0.0, x + 0.04, 0.25, 0.42, "CF_Metal")


def blob(m, cx, cy, cz, rx, ry, rz, mat, seed, rings=4, segs=7):
    """Lumpy ellipsoid (a tree crown or a hedge ball)."""
    import random
    rr = random.Random(seed)
    pts = [[None] * segs for _ in range(rings + 1)]
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(segs):
            ph = 2 * math.pi * (j + 0.5 * (i % 2)) / segs
            k = 1.0 if i in (0, rings) else 0.82 + 0.3 * rr.random()
            pts[i][j] = (cx + rx * k * math.sin(th) * math.cos(ph), cy + ry * k * math.sin(th) * math.sin(ph), cz + rz * k * math.cos(th))
    for i in range(rings):
        for j in range(segs):
            n = (j + 1) % segs
            a, b, c, d = pts[i][j], pts[i][n], pts[i + 1][n], pts[i + 1][j]
            if i == 0: m.poly([a, d, c], mat, smooth=True)
            elif i == rings - 1: m.poly([a, d, b], mat, smooth=True)
            else: m.poly([a, d, c, b], mat, smooth=True)


TREES = [  # name, trunk height, trunk radius, crowns [(dx, dy, dz, rx, ry, rz)]
    ("tree_maple", 3.4, 0.17, [(0, 0, 6.4, 2.9, 2.9, 2.5), (1.2, 0.6, 7.6, 1.9, 1.9, 1.7), (-1.1, -0.5, 7.2, 1.8, 1.8, 1.6)]),
    ("tree_cherry", 2.8, 0.15, [(0, 0, 5.0, 2.7, 2.7, 1.7), (0.8, -0.6, 5.8, 1.6, 1.6, 1.2)]),
    ("tree_column", 2.6, 0.14, [(0, 0, 6.2, 1.3, 1.3, 3.4), (0, 0, 8.6, 0.9, 0.9, 1.4)]),
    ("tree_linden", 3.2, 0.19, [(0, 0, 6.6, 3.2, 3.2, 2.8), (0, 0, 8.6, 2.0, 2.0, 1.5)]),
    ("tree_oak", 3.0, 0.32, [(0, 0, 7.0, 4.6, 4.6, 3.4), (1.8, 1.0, 8.4, 2.8, 2.8, 2.2), (-1.9, -0.8, 7.9, 2.6, 2.6, 2.0)]),
    ("tree_fir", 1.6, 0.28, None),
    ("tree_birch", 3.4, 0.12, [(0, 0, 6.6, 2.0, 2.0, 2.6), (0.5, 0.3, 8.4, 1.3, 1.3, 1.4)]),
]


def tree(m, lod, spec):
    name, th, tr, crowns = spec
    if lod == 2:            # far: a 4-sided trunk and one coarse crown per tree
        top = (crowns[0] if crowns else (0, 0, 5.5, 2.6, 2.6, 4.5))
        m.cylinder(0, 0, 0.0, top[2] - top[5] * 0.6, tr, tr * 0.6, "CF_Bark", 4, cap=False)
        if crowns is None:
            ring = [(2.8 * math.cos(2 * math.pi * i / 5), 2.8 * math.sin(2 * math.pi * i / 5), 1.6) for i in range(5)]
            for i in range(5): m.poly([ring[i], ring[(i + 1) % 5], (0, 0, 12.5)], "CF_Leaves")
            return
        dx, dy, dz, rx, ry, rz = top
        blob(m, dx, dy, dz + rz * 0.15, rx * 1.1, ry * 1.1, rz * 1.15, "CF_Leaves", sum(map(ord, name)), rings=2, segs=5)
        return
    sides = 5 if lod else 7
    if crowns is None:     # conifer: stacked cones
        m.cylinder(0, 0, 0.0, 2.2, tr, tr * 0.7, "CF_Bark", sides)
        for k, (z, r) in enumerate(((1.6, 3.0), (4.4, 2.4), (7.0, 1.8), (9.3, 1.2))):
            n = 6 if lod else 9
            ring = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
            apex = (0, 0, z + 3.6)
            for i in range(n):
                m.poly([ring[i], ring[(i + 1) % n], apex], "CF_Leaves")
            if not lod: m.poly(ring[::-1], "CF_Leaves")
        return
    m.cylinder(0, 0, 0.0, th + 1.2, tr, tr * 0.6, "CF_Bark", sides, cap=False)
    if not lod:
        for k, (ax, ay) in enumerate(((0.9, 0.4), (-0.7, -0.6), (0.2, -0.9))):
            m.poly([(0, 0, th + 0.6), (ax * 0.12, ay * 0.12, th + 0.4), (ax * 1.4, ay * 1.4, th + 2.0)], "CF_Bark")
            m.poly([(0, 0, th + 0.6), (ax * 1.4, ay * 1.4, th + 2.0), (ax * 0.12, ay * 0.12, th + 0.4)], "CF_Bark")
    for k, (dx, dy, dz, rx, ry, rz) in enumerate(crowns):
        blob(m, dx, dy, dz, rx, ry, rz, "CF_Leaves", sum(map(ord, name)) + k, rings=3 if lod else 5, segs=6 if lod else 9)


PROPS = {"garage": garage, "lamp": lamp, "traffic_light": traffic_light, "stop_sign": stop_sign, "bus_stop": bus_stop, "hydrant": hydrant, "bench": bench}


def build_all():
    """name -> (LOD0 mesh, LOD1 mesh) for every kit item."""
    out = {}
    for name, fn in list(HOUSES.items()) + list(PROPS.items()):
        meshes = []
        for lod in (0, 1):
            m = Mesh()
            fn(m, lod)
            meshes.append(m)
        out[name if name in PROPS else "house_" + name] = meshes
    for spec in TREES:
        meshes = []
        for lod in (0, 1):
            m = Mesh()
            tree(m, lod, spec)
            meshes.append(m)
        far = Mesh()
        tree(far, 2, spec)
        meshes.append(far)
        out[spec[0]] = meshes
    return out
