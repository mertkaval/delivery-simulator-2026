"""Vancouver / Burnaby house prefabs built from the city-kit geometry library.

Seven house types after the reference images (docs/reference), plus yard, lane and forest
props. Local frame (Godot): origin at the front-centre of the footprint on the ground,
street facade faces +Z, the house extends to z = -D. Body/trim/door/roof surfaces use
near-white "paint" materials so the game tints every instance differently.

  house_craftsman     1.5-storey craftsman: side gable, front gable dormer, porch on tapered
                      columns, tall concrete foundation, black-railed stair      (image 1)
  house_special       Vancouver Special: brick base with garage, stucco upper, low hip roof,
                      recessed split entry with iron-railed stair                (image 2)
  house_modern        Modern two-storey: cedar and black panels, mono-pitch metal roofs  (image 3)
  house_foursquare    Craftsman foursquare: shingle siding, front gable with brackets,
                      full-width porch with balustrade, brick chimney           (image 4)
  house_splitlevel    1970s split-level: brick lower, stucco upper, gable, chimney     (image 5)
  house_laneway       Narrow laneway/farmhouse: board-and-batten over cedar, metal gable (image 6)
  house_bungalow      Hip-roof bungalow on a raised basement, side stair, chimney      (image 7)

Run inside Blender (MCP) or headless; reuses build_kit.py (Mesh, bake_ao, export, split).
"""
import math
import os

KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\citykit", "build_kit.py")
_ns = {"__name__": "build_kit_lib", "BUILD": False}
exec(compile(open(KIT).read(), KIT, "exec"), _ns)
Mesh, kit_material, PALETTE = _ns["Mesh"], _ns["kit_material"], _ns["PALETTE"]
bake_ao, export, split_by_material, G = _ns["bake_ao"], _ns["export"], _ns["split_by_material"], _ns["G"]
import bpy  # noqa: E402
import json  # noqa: E402

OUT = os.path.join(os.path.dirname(KIT), "houses")
PALETTE.update({
    "LapSiding": ("e8e6e1", 0.6), "ShingleSiding": ("e6e2da", 0.7), "BoardBatten": ("ecebe6", 0.6),
    "HouseStucco": ("e9e2d3", 0.85), "AsphaltShingles": ("8a8a8a", 0.85), "TrimPaint": ("f2f0ea", 0.45),
    "DoorPaint": ("f0f0f0", 0.4), "DoorWood": ("7a4a2a", 0.45), "RailBlack": ("15181a", 0.4),
    "GaragePaint": ("ebe9e4", 0.5), "DeckBoards": ("8a6d4f", 0.7), "Soil": ("3d2a1c", 0.95),
    "Foliage": ("3a5a2a", 0.8), "Bark": ("4a3424", 0.9), "BinBlack": ("1d2124", 0.55),
    "BinBlue": ("1f4f8f", 0.5), "BinGreen": ("2d6a3a", 0.5), "PoleWood": ("4b3a2c", 0.9),
    "Insulator": ("cfd6d8", 0.3), "Hedge": ("2f4f25", 0.85), "LampGlow": ("ffd9a0", 0.3),
    "Conifer": ("24391f", 0.9), "SignGreen": ("1f5c3a", 0.4), "Bronze": ("5a4128", 0.35),
})


class XMesh(Mesh):
    """Mesh with a placement transform (translation + yaw about Y) applied to every face."""

    def __init__(self):
        super().__init__()
        self.ox, self.oy, self.oz, self.yaw = 0.0, 0.0, 0.0, 0.0
        self.stack = []

    def push(self, x=0.0, y=0.0, z=0.0, yaw=0.0):
        self.stack.append((self.ox, self.oy, self.oz, self.yaw))
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        self.ox, self.oy, self.oz = self.ox + c * x + s * z, self.oy + y, self.oz - s * x + c * z
        self.yaw += yaw
        return self

    def pop(self):
        self.ox, self.oy, self.oz, self.yaw = self.stack.pop()

    def _xf(self, p):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        x, y, z = p
        return (self.ox + c * x + s * z, self.oy + y, self.oz - s * x + c * z)

    def face(self, pts, mat, normal):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        nx, ny, nz = normal
        return Mesh.face(self, [self._xf(p) for p in pts], mat, (c * nx + s * nz, ny, -s * nx + c * nz))


LOD = "near"


def near():
    return LOD == "near"


# ------------------------------------------------------------------------------ helpers

def prism(m, a, b, w, h, mat, up=(0.0, 1.0, 0.0), caps=True):
    """Rectangular beam from a to b, w wide (side axis) and h tall (up axis)."""
    ax, ay, az = a
    bx, by, bz = b
    d = (bx - ax, by - ay, bz - az)
    ln = math.sqrt(sum(c * c for c in d)) or 1e-6
    d = tuple(c / ln for c in d)
    side = (d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0])
    sl = math.sqrt(sum(c * c for c in side)) or 1e-6
    side = tuple(c / sl for c in side)
    upv = (side[1] * d[2] - side[2] * d[1], side[2] * d[0] - side[0] * d[2], side[0] * d[1] - side[1] * d[0])
    def corner(p, i, j):
        return tuple(p[k] + side[k] * w / 2 * i + upv[k] * h / 2 * j for k in range(3))
    ring_a = [corner(a, i, j) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    ring_b = [corner(b, i, j) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    normals = [tuple(-upv[k] for k in range(3)), side, upv, tuple(-side[k] for k in range(3))]
    for k in range(4):
        m.face([ring_a[k], ring_a[(k + 1) % 4], ring_b[(k + 1) % 4], ring_b[k]], mat, normals[k])
    if caps:
        m.face(ring_a, mat, tuple(-c for c in d))
        m.face(ring_b, mat, d)


def opening_trim(m, x0, x1, y0, y1, trim, z=0.0, width=0.11, sill=True):
    """Craftsman casing: side boards, a capped head and a projecting sill."""
    if not near():
        return
    for x in (x0 - width / 2, x1 + width / 2):
        m.box((x, (y0 + y1) / 2, z + 0.015), (width, y1 - y0, 0.03), trim, skip=("-z",))
    m.box(((x0 + x1) / 2, y1 + 0.08, z + 0.02), (x1 - x0 + 2 * width + 0.04, 0.16, 0.04), trim, skip=("-z",))
    m.box(((x0 + x1) / 2, y1 + 0.17, z + 0.04), (x1 - x0 + 2 * width + 0.1, 0.03, 0.08), trim, skip=("-z",))
    if sill:
        m.box(((x0 + x1) / 2, y0 - 0.03, z + 0.045), (x1 - x0 + 2 * width + 0.06, 0.05, 0.09), trim, skip=("-z",))


def house_window(m, x0, x1, y0, y1, frame="TrimPaint", trim="TrimPaint", grid=None, z=0.0, depth=0.12, casing=True):
    """Window in a wall opening (the wall supplies the hole). grid: (cols, top-sash rows)."""
    if not near():
        m.quad_z(x0, x1, y0, y1, z + 0.005, "Glass")
        return
    mullions = [x0 + (x1 - x0) * i / grid[0] for i in range(1, grid[0])] if grid else []
    split = y0 + (y1 - y0) * 0.62 if grid else None
    m.window(x0, x1, y0, y1, z - depth + 0.08, frame, mullions=[], transoms=[split] if split else [], profile=0.055, depth=0.08)
    if grid and grid[1]:
        # Craftsman upper-sash muntins.
        for i in range(1, grid[0]):
            x = x0 + (x1 - x0) * i / grid[0]
            m.box((x, (split + y1) / 2, z - depth + 0.09), (0.025, y1 - split, 0.02), frame)
        for j in range(1, grid[1] + 1):
            y = split + (y1 - split) * j / (grid[1] + 1)
            m.box(((x0 + x1) / 2, y, z - depth + 0.09), (x1 - x0, 0.025, 0.02), frame)
    elif mullions:
        for x in mullions:
            m.box((x, (y0 + y1) / 2, z - depth + 0.09), (0.05, y1 - y0, 0.05), frame)
    if casing:
        opening_trim(m, x0, x1, y0, y1, trim, z)


def door(m, x0, x1, y0, y1, finish="DoorWood", lites=True, z=0.0, frame="TrimPaint"):
    """Panel door with a row of glass lites, set 12 cm back, cased in trim."""
    m.quad_z(x0, x1, y0, y1, z - 0.12, finish)
    if near():
        if lites:
            for i in range(3):
                lx = x0 + 0.12 + i * (x1 - x0 - 0.24) / 3
                m.quad_z(lx + 0.02, lx + (x1 - x0 - 0.24) / 3 - 0.02, y1 - 0.62, y1 - 0.32, z - 0.115, "Glass")
        for yy in (y0 + 0.25, y0 + 0.85):
            m.box(((x0 + x1) / 2, yy + 0.25, z - 0.11), (x1 - x0 - 0.3, 0.45, 0.02), finish, skip=("-z",))
        m.box((x1 - 0.12, y0 + 1.0, z - 0.08), (0.04, 0.16, 0.05), "RailBlack")
        opening_trim(m, x0, x1, y0, y1, frame, z, width=0.13, sill=False)


def stairs(m, x0, x1, top, z_front, run=0.28, mat="Concrete"):
    """Steps descending from height `top` at z_front out towards +z."""
    n = max(1, round(top / 0.18))
    rise = top / n
    for i in range(n):
        h = top - i * rise
        m.box(((x0 + x1) / 2, h / 2, z_front + run * (i + 0.5)), (x1 - x0, h, run), mat, skip=("-y",) + (("-z",) if i == 0 else ()))
    return z_front + run * n


def stair_rail(m, x, top, z_front, z_end, mat="RailBlack", balusters=True):
    """Sloped handrail with posts and balusters from the landing down to the ground."""
    if not near():
        return
    h = 0.9
    prism(m, (x, top + h, z_front), (x, h, z_end), 0.04, 0.05, mat)
    prism(m, (x, top + 0.12, z_front), (x, 0.12, z_end), 0.03, 0.03, mat)
    for zz, yy in ((z_front, top), (z_end, 0.0)):
        m.box((x, yy + h / 2 + 0.05, zz), (0.06, h + 0.1, 0.06), mat)
    if balusters:
        steps = int(abs(z_end - z_front) / 0.13)
        for i in range(1, steps):
            t = i / steps
            zz = z_front + (z_end - z_front) * t
            yy = top * (1 - t)
            m.box((x, yy + 0.12 + (h - 0.12) / 2, zz), (0.018, h - 0.12, 0.018), mat, skip=("+y", "-y"))


def flat_rail(m, x0, x1, y, z, mat="RailBlack", h=0.9, step=0.12, picket=0.018):
    if not near():
        return
    m.box(((x0 + x1) / 2, y + h, z), (x1 - x0, 0.05, 0.06), mat)
    m.box(((x0 + x1) / 2, y + 0.1, z), (x1 - x0, 0.04, 0.04), mat)
    n = int((x1 - x0) / step)
    for i in range(1, n):
        m.box((x0 + i * step, y + 0.1 + (h - 0.1) / 2, z), (picket, h - 0.1, picket), mat, skip=("+y", "-y"))


def gutter_run(m, x0, x1, y, z, mat="TrimPaint"):
    if near():
        m.box(((x0 + x1) / 2, y - 0.07, z + 0.06), (x1 - x0, 0.12, 0.12), mat)


def downpipe(m, x, y_top, z, mat="TrimPaint"):
    if near():
        m.box((x, y_top / 2, z), (0.08, y_top, 0.07), mat)
        m.box((x, 0.1, z + 0.18), (0.08, 0.06, 0.32), mat)


def walls(m, W, D, y0, y1, faces, mat, reveal=0.12):
    """faces: {'front'|'back'|'left'|'right': [openings (x0,x1,y0,y1) in facade coords]}.
    Facade coords: x along the face (left to right seen from outside), y height."""
    spec = {"front": (0.0, 0.0, 0.0, W), "back": (0.0, -D, math.pi, W), "left": (-W / 2, -D / 2, -math.pi / 2, D), "right": (W / 2, -D / 2, math.pi / 2, D)}
    for name, (x, z, yaw, width) in spec.items():
        m.push(x, 0, z, yaw)
        m.wall(-width / 2, width / 2, y0, y1, faces.get(name, []), mat, reveal=reveal, reveal_mat="TrimPaint")
        m.pop()


def on_face(m, W, D, face):
    spec = {"front": (0.0, 0.0, 0.0), "back": (0.0, -D, math.pi), "left": (-W / 2, -D / 2, -math.pi / 2), "right": (W / 2, -D / 2, math.pi / 2)}
    x, z, yaw = spec[face]
    m.push(x, 0, z, yaw)


def foundation(m, W, D, h, mat="Concrete", windows=()):
    """Concrete basement wall, 3 cm proud of the siding, with optional basement windows."""
    m.push(0, 0, 0.03)
    walls(m, W + 0.06, D + 0.06, 0.0, h, {"front": list(windows)}, mat, reveal=0.15)
    m.pop()
    for x0, x1, y0, y1 in windows:
        m.push(0, 0, 0.03)
        house_window(m, x0, x1, y0, y1, grid=(2, 0), casing=False)
        m.pop()
    if near():
        # Water-table trim board where siding meets the foundation.
        for face in ("front", "back", "left", "right"):
            width = W if face in ("front", "back") else D
            on_face(m, W, D, face)
            m.box((0, h + 0.06, 0.03), (width + 0.06, 0.12, 0.06), "TrimPaint", skip=("-z",))
            m.pop()


def gable_roof(m, W, D, y, pitch, over=0.45, rake=0.3, mat="AsphaltShingles", gable="LapSiding", ridge="x", z_front=0.0):
    """Ridge along x (gables at the sides) or z (gable facing the street)."""
    t = math.tan(math.radians(pitch))
    if ridge == "x":
        half = D / 2
        zc = z_front - half
        rise = half * t
        ye = y - over * t
        x0, x1 = -W / 2 - rake, W / 2 + rake
        for sgn in (1, -1):
            ze = zc + sgn * (half + over)
            pts = [(x0, ye, ze), (x1, ye, ze), (x1, y + rise, zc), (x0, y + rise, zc)]
            m.face(pts, mat, (0, 1, sgn * t))
            m.face(pts, "TrimPaint", (0, -1, -sgn * t))  # soffit
            gutter_run(m, x0, x1, ye, ze if sgn > 0 else ze - 0.12, "TrimPaint")
            if near():
                m.box(((x0 + x1) / 2, ye - 0.08, ze), (x1 - x0, 0.18, 0.04), "TrimPaint")  # fascia
        for sx in (-1, 1):
            xg = sx * W / 2
            m.face([(xg, y, z_front), (xg, y, z_front - D), (xg, y + rise, zc)], gable, (sx, 0, 0))
            if near():
                for sgn in (1, -1):
                    prism(m, (sx * (W / 2 + rake), ye - 0.02, zc + sgn * (half + over)), (sx * (W / 2 + rake), y + rise + 0.02, zc), 0.05, 0.2, "TrimPaint")
        if near():
            m.box((0, y + rise + 0.03, zc), (x1 - x0, 0.06, 0.18), mat)
        return y + rise
    # Ridge along z: front-facing gable.
    half = W / 2
    rise = half * t
    ye = y - over * t
    z0, z1 = z_front + rake, z_front - D - rake
    for sgn in (1, -1):
        xe = sgn * (half + over)
        pts = [(xe, ye, z0), (xe, ye, z1), (0, y + rise, z1), (0, y + rise, z0)]
        m.face(pts, mat, (sgn * t, 1, 0))
        m.face(pts, "TrimPaint", (-sgn * t, -1, 0))
        if near():
            m.box((xe + sgn * 0.06, ye - 0.07, (z0 + z1) / 2), (0.12, 0.12, z0 - z1), "TrimPaint")
            m.box((xe, ye - 0.08, (z0 + z1) / 2), (0.04, 0.18, z0 - z1), "TrimPaint")
    for zz, sz in ((z_front, 1), (z_front - D, -1)):
        m.face([(-half, y, zz), (half, y, zz), (0, y + rise, zz)], gable, (0, 0, sz))
        if near():
            for sgn in (1, -1):
                prism(m, (sgn * (half + over), ye - 0.02, zz + sz * rake), (0, y + rise + 0.02, zz + sz * rake), 0.2, 0.05, "TrimPaint", up=(0, 0, 1))
    if near():
        m.box((0, y + rise + 0.03, z_front - D / 2), (0.18, 0.06, D + 2 * rake), mat)
    return y + rise


def hip_roof(m, W, D, y, pitch, over=0.5, mat="AsphaltShingles", z_front=0.0, x_off=0.0):
    t = math.tan(math.radians(pitch))
    x0, x1 = x_off - W / 2 - over, x_off + W / 2 + over
    zf, zb = z_front + over, z_front - D - over
    ww, dd = x1 - x0, zf - zb
    ye = y - over * t
    rise = min(ww, dd) / 2 * t
    yr = ye + rise
    zc = (zf + zb) / 2
    xc = (x0 + x1) / 2
    if ww >= dd:
        r0, r1 = (xc - (ww - dd) / 2, yr, zc), (xc + (ww - dd) / 2, yr, zc)
        m.face([(x0, ye, zf), (x1, ye, zf), r1, r0], mat, (0, 1, t))
        m.face([(x1, ye, zb), (x0, ye, zb), r0, r1], mat, (0, 1, -t))
        m.face([(x0, ye, zb), (x0, ye, zf), r0], mat, (-t, 1, 0))
        m.face([(x1, ye, zf), (x1, ye, zb), r1], mat, (t, 1, 0))
    else:
        r0, r1 = (xc, yr, zc + (dd - ww) / 2), (xc, yr, zc - (dd - ww) / 2)
        m.face([(x0, ye, zf), (x1, ye, zf), r0], mat, (0, 1, t))
        m.face([(x1, ye, zb), (x0, ye, zb), r1], mat, (0, 1, -t))
        m.face([(x0, ye, zb), (x0, ye, zf), r0, r1], mat, (-t, 1, 0))
        m.face([(x1, ye, zf), (x1, ye, zb), r1, r0], mat, (t, 1, 0))
    m.face([(x0, ye, zf), (x1, ye, zf), (x1, ye, zb), (x0, ye, zb)], "TrimPaint", (0, -1, 0))  # soffit
    if near():
        for (a, b) in (((x0, zf), (x1, zf)), ((x1, zf), (x1, zb)), ((x1, zb), (x0, zb)), ((x0, zb), (x0, zf))):
            mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            sx, sz = abs(b[0] - a[0]) or 0.12, abs(b[1] - a[1]) or 0.12
            m.box((mx, ye - 0.08, mz), (sx + 0.02, 0.18, sz + 0.02), "TrimPaint")
            m.box((mx, ye - 0.16, mz), (sx + 0.1, 0.1, sz + 0.1), "TrimPaint")  # gutter
    return yr


def chimney(m, x, z, y0, y1, mat="BrickRed"):
    m.box((x, (y0 + y1) / 2, z), (0.75, y1 - y0, 0.65), mat, skip=("-y",))
    m.box((x, y1 + 0.04, z), (0.85, 0.08, 0.75), "Concrete", skip=("-y",))
    if near():
        m.box((x + 0.15, y1 + 0.25, z), (0.2, 0.35, 0.2), "BrickRed")


def porch_light(m, x, y, z):
    if near():
        m.box((x, y, z + 0.08), (0.16, 0.26, 0.16), "RailBlack")
        m.box((x, y - 0.02, z + 0.08), (0.12, 0.16, 0.17), "LampGlow")


def column(m, x, z, y0, y1, w0=0.34, w1=0.24, pier=0.55, mat="TrimPaint"):
    """Craftsman tapered column on a square pier."""
    m.box((x, y0 + pier / 2, z), (w0 + 0.08, pier, w0 + 0.08), mat, skip=("-y",))
    if not near():
        m.box((x, (y0 + pier + y1) / 2, z), (w1, y1 - y0 - pier, w1), mat, skip=("-y", "+y"))
        return
    ya, yb = y0 + pier, y1 - 0.2
    pts0 = [(x - w0 / 2, ya, z - w0 / 2), (x + w0 / 2, ya, z - w0 / 2), (x + w0 / 2, ya, z + w0 / 2), (x - w0 / 2, ya, z + w0 / 2)]
    pts1 = [(x - w1 / 2, yb, z - w1 / 2), (x + w1 / 2, yb, z - w1 / 2), (x + w1 / 2, yb, z + w1 / 2), (x - w1 / 2, yb, z + w1 / 2)]
    normals = [(0, 0.1, -1), (1, 0.1, 0), (0, 0.1, 1), (-1, 0.1, 0)]
    for k in range(4):
        m.face([pts0[k], pts0[(k + 1) % 4], pts1[(k + 1) % 4], pts1[k]], mat, normals[k])
    m.box((x, y1 - 0.1, z), (w1 + 0.1, 0.2, w1 + 0.1), mat)


def knee_brackets(m, xs, y, z, depth=0.5, mat="TrimPaint"):
    if not near():
        return
    for x in xs:
        prism(m, (x, y - 0.45, z), (x, y - 0.02, z + depth), 0.08, 0.08, mat)
        m.box((x, y - 0.06, z + depth / 2), (0.09, 0.1, depth), mat)


# ------------------------------------------------------------------------------ house types

def house_craftsman(m):
    W, D, F, H = 8.4, 11.0, 1.05, 2.8
    foundation(m, W, D, F, windows=[(-3.4, -2.2, 0.35, 0.8), (2.4, 3.6, 0.35, 0.8)])
    top = F + H
    front = [(-3.7, -1.0, 1.6, 3.3), (0.15, 1.15, F, 3.15), (2.35, 3.55, 1.6, 3.3)]
    side = [(-3.0, -1.8, 1.7, 3.2), (1.2, 2.3, 1.7, 3.2)]
    walls(m, W, D, F, top, {"front": front, "left": side, "right": side, "back": [(-2.5, -1.0, 1.7, 3.1), (1.0, 1.9, F, 3.1)]}, "LapSiding")
    house_window(m, -3.7, -1.0, 1.6, 3.3, grid=(3, 1))
    door(m, 0.15, 1.15, F, 3.15, "DoorWood")
    house_window(m, 2.35, 3.55, 1.6, 3.3, grid=(2, 1))
    for face in ("left", "right"):
        on_face(m, W, D, face)
        for x0, x1, y0, y1 in side:
            house_window(m, x0, x1, y0, y1, grid=(2, 1))
        m.pop()
    on_face(m, W, D, "back")
    house_window(m, -2.5, -1.0, 1.7, 3.1, grid=(2, 0))
    door(m, 1.0, 1.9, F, 3.1, "DoorPaint")
    m.pop()
    ridge = gable_roof(m, W, D, top, 40, over=0.45, rake=0.35, gable="LapSiding", ridge="x")
    # Front gable dormer with knee brackets.
    t = math.tan(math.radians(40))
    dz = -1.3
    dy0 = top + 1.3 * t
    m.push(0.6, 0, dz)
    m.wall(-1.6, 1.6, dy0 - 0.2, top + 2.9, [(-1.0, 1.0, dy0 + 0.25, top + 2.55)], "LapSiding", reveal=0.1, reveal_mat="TrimPaint")
    house_window(m, -1.0, 1.0, dy0 + 0.25, top + 2.55, grid=(2, 1))
    for sx in (-1, 1):
        m.face([(sx * 1.6, dy0 - 0.2, 0), (sx * 1.6, top + 2.9, 0), (sx * 1.6, top + 2.9, -2.6), (sx * 1.6, dy0 - 0.2, -2.6)], "LapSiding", (sx, 0, 0))
    m.pop()
    m.push(0.6, top + 2.9, dz)
    gable_roof(m, 3.2, 3.0, 0.0, 45, over=0.5, rake=0.25, gable="LapSiding", ridge="z", z_front=0.0)
    knee_brackets(m, (-1.6, 1.6), -0.05, 0.0, 0.45)
    m.pop()
    # Porch: deck at foundation height, two tapered columns, hip roof, stair with black rails.
    px0, px1, pd = -1.15, 2.75, 2.1
    m.box(((px0 + px1) / 2, F / 2, pd / 2), (px1 - px0, F, pd), "Concrete", skip=("-z",))
    m.box(((px0 + px1) / 2, F + 0.02, pd / 2), (px1 - px0, 0.04, pd), "DeckBoards", skip=("-y",))
    for x in (px0 + 0.25, px1 - 0.25):
        column(m, x, pd - 0.25, F, top - 0.1)
    m.push((px0 + px1) / 2, 0, 0)
    hip_roof(m, px1 - px0 - 0.2, pd - 0.1, top - 0.05, 25, over=0.35, z_front=pd - 0.1)
    m.pop()
    z_end = stairs(m, 0.0, 1.3, F, pd)
    stair_rail(m, -0.02, F, pd, z_end)
    stair_rail(m, 1.32, F, pd, z_end)
    flat_rail(m, px0 + 0.4, -0.05, F, pd - 0.1)
    flat_rail(m, 1.35, px1 - 0.4, F, pd - 0.1)
    porch_light(m, 0.65, 3.55, 0.0)
    downpipe(m, -W / 2 - 0.15, top - 0.3, 0.3)
    downpipe(m, W / 2 + 0.15, top - 0.3, 0.3)
    if near():
        m.box((2.1, ridge - 0.6, -D / 2 - 1.5), (0.12, 1.2, 0.12), "RailBlack")  # plumbing vent


def house_special(m):
    W, D, L, U = 12.0, 11.0, 2.6, 2.8
    # Recessed split entry: a 1.5 m wide, 1.1 m deep porch void through both storeys' front.
    ex0, ex1, rec = -1.1, 0.5, 1.1
    lower = [(-5.0, -2.0, 0.8, 1.9), (1.4, 4.6, 0.0, 2.25)]
    walls(m, W, D, 0.0, L, {"front": lower + [(ex0, ex1, 0.0, L)], "left": [(-3.0, -1.8, 0.9, 1.8)], "right": [(1.0, 2.2, 0.9, 1.8)], "back": [(-3, 0, 0.0, 2.2), (2, 4, 0.9, 1.9)]}, "BrickRed", reveal=0.15)
    upper = [(-5.3, -1.6, 3.1, 4.9), (1.2, 4.7, 3.3, 4.85)]
    walls(m, W, D, L, L + U, {"front": upper + [(ex0, ex1, L, L + U - 0.35)], "left": [(-3.5, -2.0, 3.3, 4.6), (2.0, 3.2, 3.3, 4.6)], "right": [(-3.5, -2.3, 3.3, 4.6), (1.5, 2.7, 3.3, 4.6)], "back": [(-4, -1, 3.2, 4.8), (1.5, 4, 3.2, 4.8)]}, "HouseStucco", reveal=0.15)
    house_window(m, -5.0, -2.0, 0.8, 1.9, frame="FrameBronze", grid=(3, 0), casing=False)
    # Garage door: panelled, painted.
    m.quad_z(1.4, 4.6, 0.0, 2.25, -0.15, "GaragePaint")
    if near():
        for r in range(4):
            for c in range(2):
                m.box((1.4 + 0.8 + c * 1.6, 0.3 + r * 0.53, -0.14), (1.4, 0.4, 0.02), "GaragePaint", skip=("-z",))
    house_window(m, -5.3, -1.6, 3.1, 4.9, frame="FrameBronze", grid=(3, 0), casing=False)
    house_window(m, 1.2, 4.7, 3.3, 4.85, frame="FrameBronze", grid=(2, 0), casing=False)
    for x0, x1, y0 in ((-5.3, -1.6, 3.1), (1.2, 4.7, 3.3), (-5.0, -2.0, 0.8)):
        m.box(((x0 + x1) / 2, y0 - 0.05, 0.06), (x1 - x0 + 0.2, 0.1, 0.12), "Limestone", skip=("-z",))
    for face, specs in (("left", [(-3.0, -1.8, 0.9, 1.8), (-3.5, -2.0, 3.3, 4.6), (2.0, 3.2, 3.3, 4.6)]), ("right", [(1.0, 2.2, 0.9, 1.8), (-3.5, -2.3, 3.3, 4.6), (1.5, 2.7, 3.3, 4.6)]), ("back", [(-4, -1, 3.2, 4.8), (1.5, 4, 3.2, 4.8), (2, 4, 0.9, 1.9)])):
        on_face(m, W, D, face)
        for x0, x1, y0, y1 in specs:
            house_window(m, x0, x1, y0, y1, frame="FrameBronze", grid=(2, 0), casing=False)
        m.pop()
    on_face(m, W, D, "back")
    door(m, -3.0, 0.0, 0.0, 2.2, "DoorPaint", lites=False)
    m.pop()
    # Entry recess: floor at the split level, back wall with the front door, stair out front.
    split = 1.35
    m.box(((ex0 + ex1) / 2, split / 2, -rec / 2), (ex1 - ex0, split, rec), "Concrete", skip=("-z",))
    m.push(0, 0, -rec)
    m.wall(ex0, ex1, split, L + U - 0.35, [(ex0 + 0.25, ex1 - 0.25, split, split + 2.1)], "HouseStucco", reveal=0.08)
    door(m, ex0 + 0.25, ex1 - 0.25, split, split + 2.1, "DoorPaint")
    m.pop()
    for sx in (ex0, ex1):
        m.face([(sx, 0, 0), (sx, L + U - 0.35, 0), (sx, L + U - 0.35, -rec), (sx, 0, -rec)], "HouseStucco", (1 if sx == ex0 else -1, 0, 0))
    m.face([(ex0, L + U - 0.35, 0), (ex1, L + U - 0.35, 0), (ex1, L + U - 0.35, -rec), (ex0, L + U - 0.35, -rec)], "TrimPaint", (0, -1, 0))
    z_end = stairs(m, ex0 + 0.02, ex1 - 0.02, split, 0.0)   # inset: sides would sit on the stucco jambs
    stair_rail(m, ex0 - 0.02, split, 0.0, z_end)
    stair_rail(m, ex1 + 0.02, split, 0.0, z_end)
    porch_light(m, ex1 - 0.15, split + 2.4, -rec)
    hip_roof(m, W, D, L + U, 22, over=0.6)
    downpipe(m, W / 2 + 0.2, L + U - 0.3, 0.3)
    m.box((W / 2 - 0.4, L + U + 1.4, -D / 2), (0.15, 1.0, 0.15), "RailBlack")


def house_modern(m):
    W, D = 10.0, 11.0
    G1, G2 = 3.0, 3.0
    front_g = [(-4.4, -1.4, 0.4, 2.6), (-0.6, 0.6, 0.0, 2.4), (1.2, 4.2, 0.4, 2.6)]
    walls(m, W, D, 0.0, G1, {"front": front_g, "back": [(-4.0, 0.0, 0.0, 2.6), (1.0, 4.2, 0.0, 2.6)], "left": [(-2, 0, 0.8, 2.4)], "right": [(-3, -1.8, 0.8, 2.4), (1.5, 2.7, 0.8, 2.4)]}, "Cedar")
    for x0, x1, y0, y1 in front_g:
        if x0 == -0.6:
            door(m, x0, x1, y0, y1, "DoorPaint", lites=False, frame="RailBlack")
        else:
            house_window(m, x0, x1, y0, y1, frame="FrameDark", grid=(2, 0), casing=False)
    on_face(m, W, D, "back")
    for x0, x1 in ((-4.0, 0.0), (1.0, 4.2)):
        house_window(m, x0, x1, 0.0, 2.6, frame="FrameDark", grid=(2, 0), casing=False)
    m.pop()
    for face, specs in (("left", [(-2, 0, 0.8, 2.4)]), ("right", [(-3, -1.8, 0.8, 2.4), (1.5, 2.7, 0.8, 2.4)])):
        on_face(m, W, D, face)
        for o in specs:
            house_window(m, *o, frame="FrameDark", grid=(1, 0), casing=False)
        m.pop()
    # Lean-to metal canopy along the front at first-floor level.
    t = math.tan(math.radians(14))
    m.face([(-W / 2 - 0.3, G1 - 0.05, 1.4), (W / 2 + 0.3, G1 - 0.05, 1.4), (W / 2 + 0.3, G1 + 1.4 * t, 0), (-W / 2 - 0.3, G1 + 1.4 * t, 0)], "MetalPanel", (0, 1, 0.25))
    m.face([(-W / 2 - 0.3, G1 - 0.05, 1.4), (W / 2 + 0.3, G1 - 0.05, 1.4), (W / 2 + 0.3, G1 + 1.4 * t, 0), (-W / 2 - 0.3, G1 + 1.4 * t, 0)], "FrameDark", (0, -1, -0.25))
    porch_light(m, -0.95, 2.2, 0.0)
    porch_light(m, 0.95, 2.2, 0.0)
    # Upper floor set back 1.5 m; black panel bay on the left, cedar elsewhere.
    m.push(0, 0, -1.5)
    UD = D - 1.5
    uf = [(-4.2, -2.2, 3.5, 5.6), (0.4, 4.0, 3.6, 5.6)]
    walls(m, W, UD, G1, G1 + G2, {"front": uf, "back": [(-3, 0, 3.6, 5.5), (1, 3, 3.6, 5.5)], "left": [(-1.5, 0, 3.7, 5.4)], "right": [(-2, -0.5, 3.7, 5.4)]}, "Cedar")
    m.box((-3.2, G1 + G2 / 2, 0.06), (2.8, G2, 0.12), "MetalPanel", skip=("-z",))
    for o in uf:
        house_window(m, *o, frame="FrameDark", grid=(2, 0), casing=False, z=0.12 if o[0] < -3 else 0.0)
    for face, specs in (("back", [(-3, 0, 3.6, 5.5), (1, 3, 3.6, 5.5)]), ("left", [(-1.5, 0, 3.7, 5.4)]), ("right", [(-2, -0.5, 3.7, 5.4)])):
        on_face(m, W, UD, face)
        for o in specs:
            house_window(m, *o, frame="FrameDark", grid=(1, 0), casing=False)
        m.pop()
    # Mono-pitch roof rising to the street, 0.6 m overhangs.
    s = math.tan(math.radians(9))
    yb, yf = G1 + G2, G1 + G2 + (UD + 1.2) * s
    pts = [(-W / 2 - 0.4, yb - 0.6 * s, -UD - 0.6), (W / 2 + 0.4, yb - 0.6 * s, -UD - 0.6), (W / 2 + 0.4, yf, 0.6), (-W / 2 - 0.4, yf, 0.6)]
    m.face(pts, "MetalPanel", (0, 1, -s))
    m.face(pts, "Cedar", (0, -1, s))
    for sx in (-1, 1):
        m.face([(sx * W / 2, yb, -UD), (sx * W / 2, yb, 0), (sx * W / 2, yb + UD * s, 0)], "Cedar", (sx, 0, 0))
    m.face([(-W / 2, yb, 0), (W / 2, yb, 0), (W / 2, yb + UD * s, 0), (-W / 2, yb + UD * s, 0)], "Cedar", (0, 0, 1))
    m.box((0, yf + 0.05, 0.6), (W + 0.8, 0.22, 0.08), "FrameDark")
    m.pop()
    downpipe(m, W / 2 + 0.15, G1, 0.2, "FrameDark")


def house_foursquare(m):
    W, D, F, H1, H2 = 9.0, 10.0, 0.8, 2.8, 2.7
    top = F + H1 + H2
    f1 = [(-3.6, -2.0, 1.4, 3.2), (-0.7, 0.7, F, 3.0), (2.0, 3.6, 1.4, 3.2)]
    f2 = [(-3.2, -1.2, 4.1, 5.8), (1.2, 3.2, 4.1, 5.8)]
    side = [(-3.0, -1.8, 1.5, 3.1), (1.0, 2.2, 1.5, 3.1), (-3.0, -1.8, 4.2, 5.7), (1.0, 2.2, 4.2, 5.7)]
    foundation(m, W, D, F)
    walls(m, W, D, F, top, {"front": f1 + f2, "left": side, "right": side, "back": [(-3, -1.5, 1.5, 3.1), (1.0, 1.9, F, 3.0), (-3, -1.5, 4.2, 5.7), (1.5, 3, 4.2, 5.7)]}, "ShingleSiding")
    for o in (f1[0], f1[2]) + tuple(f2):
        house_window(m, *o, grid=(2, 1))
    door(m, *f1[1], "DoorWood")
    for face, specs in (("left", side), ("right", side), ("back", [(-3, -1.5, 1.5, 3.1), (-3, -1.5, 4.2, 5.7), (1.5, 3, 4.2, 5.7)])):
        on_face(m, W, D, face)
        for o in specs:
            house_window(m, *o, grid=(2, 1))
        m.pop()
    on_face(m, W, D, "back")
    door(m, 1.0, 1.9, F, 3.0, "DoorPaint")
    m.pop()
    # Belt course between storeys.
    for face in ("front", "back", "left", "right"):
        on_face(m, W, D, face)
        m.box((0, F + H1, 0.04), ((W if face in ("front", "back") else D) + 0.08, 0.2, 0.08), "TrimPaint", skip=("-z",))
        m.pop()
    ridge = gable_roof(m, W, D, top, 42, over=0.55, rake=0.45, gable="ShingleSiding", ridge="z")
    knee_brackets(m, (-W / 2 - 0.1, W / 2 + 0.1), top + 0.02, 0.0, 0.5)
    m.push(0, 0, 0)
    m.wall(-0.9, 0.9, top + 0.6, top + 2.2, [(-0.7, 0.7, top + 0.75, top + 2.0)], "ShingleSiding", z=0.0)
    house_window(m, -0.7, 0.7, top + 0.75, top + 2.0, grid=(2, 1))
    m.pop()
    # Full-width porch with balustrade and hip roof on four columns.
    pd = 2.6
    m.box((0, F / 2, pd / 2), (W, F, pd), "Concrete", skip=("-z",))
    m.box((0, F + 0.02, pd / 2), (W, 0.04, pd), "DeckBoards", skip=("-y",))
    for x in (-W / 2 + 0.3, -1.1, 1.1, W / 2 - 0.3):
        column(m, x, pd - 0.3, F, F + H1 - 0.1, w0=0.3, w1=0.22, pier=0.35)
    flat_rail(m, -W / 2 + 0.45, -1.25, F, pd - 0.3, "TrimPaint", h=0.85, step=0.14, picket=0.05)
    flat_rail(m, 1.25, W / 2 - 0.45, F, pd - 0.3, "TrimPaint", h=0.85, step=0.14, picket=0.05)
    hip_roof(m, W, pd, F + H1 - 0.05, 20, over=0.35, z_front=pd)
    z_end = stairs(m, -1.0, 1.0, F, pd, mat="DeckBoards")
    stair_rail(m, -1.05, F, pd, z_end, "TrimPaint", balusters=False)
    stair_rail(m, 1.05, F, pd, z_end, "TrimPaint", balusters=False)
    porch_light(m, 1.0, F + 2.3, 0.0)
    chimney(m, -W / 2 - 0.35, -D * 0.6, 0.0, ridge + 0.6)
    downpipe(m, W / 2 + 0.15, top - 0.3, 0.3)


def house_splitlevel(m):
    W, D, L, U = 12.0, 9.0, 2.5, 2.7
    lower = [(-5.0, -2.2, 0.7, 1.9), (0.6, 1.6, 0.0, 2.15), (2.4, 4.8, 0.7, 1.9)]
    upper = [(-5.0, -0.8, 3.0, 4.6), (1.4, 4.8, 3.1, 4.6)]
    walls(m, W, D, 0.0, L, {"front": lower, "back": [(-3.5, -1.5, 0.0, 2.2), (1.5, 4.0, 0.8, 1.9)], "left": [(-2, -0.8, 0.9, 1.9)], "right": [(-2, -0.8, 0.9, 1.9)]}, "BrickRed", reveal=0.15)
    walls(m, W, D, L, L + U, {"front": upper, "back": [(-5.2, -0.5, 3.1, 4.6), (1.0, 4.0, 3.1, 4.6)], "left": [(-1.5, 0.5, 3.2, 4.4)], "right": [(-1.5, 0.5, 3.2, 4.4)]}, "HouseStucco", reveal=0.15)
    for o in (lower[0], lower[2]) + tuple(upper):
        house_window(m, *o, frame="TrimPaint", grid=(2, 0), casing=False)
        m.box(((o[0] + o[1]) / 2, o[2] - 0.05, 0.06), (o[1] - o[0] + 0.2, 0.1, 0.12), "Concrete", skip=("-z",))
    door(m, *lower[1], "DoorPaint")
    m.box((1.1, 0.05, 0.6), (1.6, 0.1, 1.2), "Concrete")
    porch_light(m, 1.95, 2.0, 0.0)
    for face, specs in (("back", [(-5.2, -0.5, 3.1, 4.6), (1.0, 4.0, 3.1, 4.6), (1.5, 4.0, 0.8, 1.9)]), ("left", [(-2, -0.8, 0.9, 1.9), (-1.5, 0.5, 3.2, 4.4)]), ("right", [(-2, -0.8, 0.9, 1.9), (-1.5, 0.5, 3.2, 4.4)])):
        on_face(m, W, D, face)
        for o in specs:
            house_window(m, *o, frame="TrimPaint", grid=(2, 0), casing=False)
        m.pop()
    on_face(m, W, D, "back")
    house_window(m, -3.5, -1.5, 0.0, 2.2, frame="FrameBronze", grid=(2, 0), casing=False)  # patio slider
    m.pop()
    ridge = gable_roof(m, W, D, L + U, 24, over=0.5, rake=0.4, gable="HouseStucco", ridge="x")
    chimney(m, -W / 2 + 1.2, -D - 0.33, 0.0, ridge + 0.7)
    downpipe(m, W / 2 + 0.15, L + U - 0.2, 0.3)


def house_laneway(m):
    W, D, L, U = 6.4, 8.5, 3.0, 2.6
    lower = [(-2.6, 0.4, 0.0, 2.4), (1.0, 2.4, 0.8, 2.4)]
    upper = [(-1.8, 1.8, 3.4, 5.3)]
    walls(m, W, D, 0.0, L, {"front": lower, "back": [(-1.2, 1.2, 0.8, 2.4)], "left": [(-2.5, -1, 0.9, 2.3)], "right": [(1.0, 2.2, 0.9, 2.3)]}, "Cedar")
    walls(m, W, D, L, L + U, {"front": upper, "left": [(-1.0, 0.0, 3.5, 5.0)], "right": [(-2.0, -1.2, 3.5, 5.0)], "back": [(-1.0, 1.0, 3.5, 5.0)]}, "BoardBatten")
    house_window(m, -2.6, 0.4, 0.0, 2.4, frame="FrameDark", grid=(2, 0), casing=False)  # sliding door
    house_window(m, 1.0, 2.4, 0.8, 2.4, frame="FrameDark", grid=(1, 0), casing=False)
    house_window(m, -1.8, 1.8, 3.4, 5.3, frame="FrameDark", grid=(2, 0), casing=False)
    for face, specs in (("back", [(-1.2, 1.2, 0.8, 2.4), (-1.0, 1.0, 3.5, 5.0)]), ("left", [(-2.5, -1, 0.9, 2.3), (-1.0, 0.0, 3.5, 5.0)]), ("right", [(1.0, 2.2, 0.9, 2.3), (-2.0, -1.2, 3.5, 5.0)])):
        on_face(m, W, D, face)
        for o in specs:
            house_window(m, *o, frame="FrameDark", grid=(1, 0), casing=False)
        m.pop()
    gable_roof(m, W, D, L + U, 45, over=0.25, rake=0.2, mat="MetalPanel", gable="BoardBatten", ridge="z")
    # Small deck with two steps and wall lamps.
    m.box((-0.6, 0.18, 0.9), (4.2, 0.36, 1.8), "DeckBoards")
    stairs(m, -1.4, -0.2, 0.36, 1.8, mat="DeckBoards")
    porch_light(m, -2.9, 2.2, 0.0)
    porch_light(m, 0.7, 2.2, 0.0)
    downpipe(m, W / 2 + 0.12, L + U - 0.2, 0.2, "FrameDark")


def house_bungalow(m):
    W, D, B, H = 10.4, 9.6, 1.3, 2.7
    foundation(m, W, D, B, mat="HouseStucco", windows=[(-4.0, -2.6, 0.45, 1.05), (2.6, 4.0, 0.45, 1.05)])
    top = B + H
    front = [(-4.2, -1.6, 2.0, 3.6), (-0.45, 0.45, B, 3.45), (1.6, 3.4, 2.0, 3.6)]
    walls(m, W, D, B, top, {"front": front, "back": [(-3.5, -1.5, 2.1, 3.5), (0.0, 0.9, B, 3.45), (2.0, 3.4, 2.1, 3.5)], "left": [(-2.5, -1.2, 2.1, 3.5), (1.0, 2.0, 2.4, 3.5)], "right": [(-2.0, -0.8, 2.1, 3.5), (1.2, 2.4, 2.1, 3.5)]}, "LapSiding")
    house_window(m, -4.2, -1.6, 2.0, 3.6, grid=(3, 0))
    door(m, -0.45, 0.45, B, 3.45, "DoorPaint")
    house_window(m, 1.6, 3.4, 2.0, 3.6, grid=(2, 0))
    for face, specs in (("back", [(-3.5, -1.5, 2.1, 3.5), (2.0, 3.4, 2.1, 3.5)]), ("left", [(-2.5, -1.2, 2.1, 3.5), (1.0, 2.0, 2.4, 3.5)]), ("right", [(-2.0, -0.8, 2.1, 3.5), (1.2, 2.4, 2.1, 3.5)])):
        on_face(m, W, D, face)
        for o in specs:
            house_window(m, *o, grid=(2, 0))
        m.pop()
    on_face(m, W, D, "back")
    door(m, 0.0, 0.9, B, 3.45, "DoorPaint")
    m.pop()
    # Front landing and wooden stair with painted rails.
    m.box((0, B / 2, 0.75), (2.0, B, 1.5), "DeckBoards", skip=("-z",))
    z_end = stairs(m, -0.6, 0.6, B, 1.5, mat="DeckBoards")
    stair_rail(m, -0.65, B, 1.5, z_end, "TrimPaint")
    stair_rail(m, 0.65, B, 1.5, z_end, "TrimPaint")
    flat_rail(m, -1.0, -0.65, B, 1.45, "TrimPaint")
    flat_rail(m, 0.65, 1.0, B, 1.45, "TrimPaint")
    porch_light(m, 0.75, B + 2.35, 0.0)
    ridge = hip_roof(m, W, D, top, 30, over=0.55)
    chimney(m, W / 2 - 1.5, -D * 0.7, top - 0.5, ridge + 0.4)
    downpipe(m, -W / 2 - 0.15, top - 0.3, 0.3)
    downpipe(m, W / 2 + 0.15, top - 0.3, 0.3)


# ------------------------------------------------------------------------------ yard / lane / forest props

def fence_privacy(m, lattice=False):
    """2.4 m cedar privacy fence panel (posts at both ends), 1.8 m tall; optional lattice top."""
    h = 1.5 if lattice else 1.8
    m.box((0, h / 2 + 0.05, 0), (2.4, h, 0.03), "Cedar")
    if near():
        for x in (-1.2, 1.2):
            m.box((x, (h + 0.35) / 2, 0), (0.1, h + 0.35, 0.1), "Cedar")
        for y in (0.3, h - 0.15):
            m.box((0, y, -0.04), (2.4, 0.09, 0.04), "Cedar")
        m.box((0, h + 0.1, 0), (2.4, 0.06, 0.1), "Cedar")
        if lattice:
            for i in range(9):
                x = -1.1 + i * 0.275
                prism(m, (x - 0.12, h + 0.12, 0), (x + 0.12, h + 0.42, 0), 0.02, 0.02, "Cedar", up=(0, 0, 1))
                prism(m, (x + 0.12, h + 0.12, 0), (x - 0.12, h + 0.42, 0), 0.02, 0.02, "Cedar", up=(0, 0, 1))
            m.box((0, h + 0.45, 0), (2.4, 0.05, 0.06), "Cedar")


def fence_picket(m):
    """Low painted picket fence, 2.4 m section."""
    for i in range(12):
        x = -1.1 + i * 0.2
        m.box((x, 0.45, 0), (0.07, 0.9, 0.02), "TrimPaint")
    for y in (0.25, 0.7):
        m.box((0, y, -0.03), (2.4, 0.07, 0.03), "TrimPaint")


def hedge(m):
    """2.4 m clipped hedge, 1.1 m tall, slightly bulged sides."""
    m.box((0, 0.55, 0), (2.4, 1.1, 0.8), "Hedge")
    if near():
        m.box((0, 1.13, 0), (2.3, 0.08, 0.7), "Hedge", skip=("-y",))


def blob(m, cx, cy, cz, rx, ry, rz, mat, seg=7, rings=4, seed=0.0):
    """Lumpy low-poly ellipsoid (shrubs, hedge tops): jittered radius gives a leafy silhouette."""
    pts = []
    for i in range(rings + 1):
        a = math.pi * i / rings
        row = []
        for j in range(seg):
            b = math.tau * j / seg
            k = 1.0 + 0.12 * math.sin(3.1 * j + 1.7 * i + seed * 5.3) if 0 < i < rings else 1.0
            row.append((cx + rx * k * math.sin(a) * math.cos(b), cy + ry * math.cos(a), cz + rz * k * math.sin(a) * math.sin(b)))
        pts.append(row)
    for i in range(rings):
        for j in range(seg):
            p0, p1, p2, p3 = pts[i][j], pts[i][(j + 1) % seg], pts[i + 1][(j + 1) % seg], pts[i + 1][j]
            mid = ((p0[0] + p2[0]) / 2 - cx, (p0[1] + p2[1]) / 2 - cy, (p0[2] + p2[2]) / 2 - cz)
            m.face([p0, p1, p2, p3], mat, mid)


def shrub_blob(m, x, z, r, mat="Foliage"):
    blob(m, x, r * 0.75, z, r, r * 0.8, r, mat, seed=x + z)
    if near():
        blob(m, x + r * 0.35, r * 1.1, z - r * 0.2, r * 0.6, r * 0.55, r * 0.6, mat, seg=6, rings=3, seed=x - z)


def garden_bed(m):
    """2.4 x 1 m planting bed: mulch, edging and shrubs."""
    m.box((0, 0.06, 0), (2.4, 0.12, 1.0), "Soil", skip=("-y",))
    for x, z, r in ((-0.8, 0.1, 0.32), (0.0, -0.15, 0.42), (0.8, 0.1, 0.3)):
        shrub_blob(m, x, z, r)


def raised_bed(m):
    """Cedar raised vegetable bed, 2.4 x 1.2 x 0.45 m, with plants."""
    for sx in (-1, 1):
        m.box((sx * 1.2, 0.225, 0), (0.06, 0.45, 1.2), "Cedar")
    for sz in (-1, 1):
        m.box((0, 0.225, sz * 0.6), (2.4, 0.45, 0.06), "Cedar")
    m.box((0, 0.4, 0), (2.34, 0.04, 1.14), "Soil")
    if near():
        for i in range(6):
            shrub_blob(m, -0.9 + i * 0.36, 0.25 if i % 2 else -0.2, 0.14)


def patio_set(m):
    """Table with four chairs on a paver slab."""
    m.box((0, 0.03, 0), (3.0, 0.06, 3.0), "Concrete")
    m.box((0, 0.74, 0), (1.4, 0.04, 0.8), "DeckBoards")
    for x in (-0.6, 0.6):
        for z in (-0.32, 0.32):
            m.box((x, 0.37, z), (0.05, 0.72, 0.05), "RailBlack")
    for x, z, yaw in ((-0.4, 0.75, 0), (0.4, 0.75, 0), (-0.4, -0.75, math.pi), (0.4, -0.75, math.pi)):
        m.push(x, 0, z, yaw)
        m.box((0, 0.45, 0), (0.45, 0.04, 0.45), "RailBlack")
        m.box((0, 0.8, 0.21), (0.45, 0.6, 0.04), "RailBlack")
        for cx in (-0.2, 0.2):
            for cz in (-0.2, 0.2):
                m.box((cx, 0.22, cz), (0.03, 0.45, 0.03), "RailBlack")
        m.pop()


def bbq(m):
    m.box((0, 0.85, 0), (1.0, 0.4, 0.55), "RailBlack")
    m.box((0, 1.12, 0), (0.95, 0.14, 0.5), "FrameLight")
    for x in (-0.4, 0.4):
        m.box((x, 0.42, 0), (0.05, 0.84, 0.45), "RailBlack")


def bins_trio(m):
    """Vancouver carts: garbage (black), recycling (blue), green compost."""
    for i, mat in enumerate(("BinBlack", "BinBlue", "BinGreen")):
        x = -0.75 + i * 0.75
        m.box((x, 0.5, 0), (0.6, 1.0, 0.7), mat)
        m.box((x, 1.03, 0.02), (0.64, 0.06, 0.76), mat)
        if near():
            for sx in (-0.24, 0.24):
                m.box((x + sx, 0.12, -0.36), (0.08, 0.24, 0.24), "RailBlack")


def garage_single(m):
    """Lane garage 3.8 x 6.2 m: board-and-batten, gable roof, panelled overhead door facing +z."""
    W, D, H = 3.8, 6.2, 2.6
    walls(m, W, D, 0.0, H, {"front": [(-1.4, 1.4, 0.0, 2.2)], "left": [(-1, 0, 0.9, 1.7)]}, "BoardBatten")
    m.quad_z(-1.4, 1.4, 0.0, 2.2, -0.1, "GaragePaint")
    if near():
        for r in range(4):
            m.box((0, 0.3 + r * 0.53, -0.09), (2.6, 0.4, 0.02), "GaragePaint", skip=("-z",))
        on_face(m, W, D, "left")
        house_window(m, -1, 0, 0.9, 1.7, grid=(1, 0), casing=False)
        m.pop()
    gable_roof(m, W, D, H, 30, over=0.3, rake=0.2, gable="BoardBatten", ridge="z")
    porch_light(m, 1.65, 2.3, 0.0)


def shed(m):
    W, D, H = 2.4, 1.9, 2.0
    walls(m, W, D, 0.0, H, {"front": [(-0.45, 0.45, 0.0, 1.85)]}, "Cedar")
    m.quad_z(-0.45, 0.45, 0.0, 1.85, -0.05, "DoorPaint")
    gable_roof(m, W, D, H, 30, over=0.15, rake=0.1, gable="Cedar", ridge="z")


def utility_pole(m, transformer=False):
    """BC Hydro-style wooden pole: 10 m, crossarm with insulators, optional transformer can."""
    m.box((0, 5.0, 0), (0.28, 10.0, 0.28), "PoleWood", skip=("-y",))
    if not near():
        m.box((0, 9.3, 0), (2.4, 0.12, 0.12), "PoleWood")
        return
    m.box((0, 9.3, 0), (2.4, 0.12, 0.14), "PoleWood")
    for x in (-1.05, -0.35, 0.35, 1.05):
        m.box((x, 9.45, 0), (0.08, 0.18, 0.08), "Insulator")
    prism(m, (-0.7, 9.25, 0.0), (0.0, 8.7, 0.0), 0.05, 0.05, "RailBlack")
    prism(m, (0.7, 9.25, 0.0), (0.0, 8.7, 0.0), 0.05, 0.05, "RailBlack")
    m.box((0, 7.4, -0.05), (0.9, 0.08, 0.1), "PoleWood")  # telecom arm
    if transformer:
        m.box((0.32, 8.0, 0), (0.45, 0.9, 0.45), "FrameLight")
        m.box((0.32, 8.47, 0), (0.5, 0.06, 0.5), "FrameLight")


def tapered_trunk(m, h, r0, r1, n=7):
    for i in range(n):
        a0, a1 = math.tau * i / n, math.tau * (i + 1) / n
        pts = [(r0 * math.cos(a0), 0, r0 * math.sin(a0)), (r0 * math.cos(a1), 0, r0 * math.sin(a1)),
               (r1 * math.cos(a1), h, r1 * math.sin(a1)), (r1 * math.cos(a0), h, r1 * math.sin(a0))]
        m.face(pts, "Bark", (math.cos((a0 + a1) / 2), 0.1, math.sin((a0 + a1) / 2)))


def skirt(m, y, r, droop, n, mat, jag=0.18, twist=0.0):
    """One branch tier: a drooping, jagged skirt from the trunk out to radius r.
    Inner ring sits high on the trunk, outer tips hang `droop` lower; alternate tips are longer."""
    inner = []
    outer = []
    for i in range(n):
        a = math.tau * i / n + twist
        rr = r * (1.0 + (jag if i % 2 == 0 else -jag))
        inner.append((0.25 * math.cos(a), y, 0.25 * math.sin(a)))
        outer.append((rr * math.cos(a), y - droop * (1.1 if i % 2 == 0 else 0.85), rr * math.sin(a)))
    for i in range(n):
        j = (i + 1) % n
        nx, nz = math.cos(math.tau * (i + 0.5) / n + twist), math.sin(math.tau * (i + 0.5) / n + twist)
        m.face([inner[i], outer[i], outer[j], inner[j]], mat, (nx * droop, r, nz * droop))


def fir(m, h=15.0):
    """Douglas fir: straight trunk, nine drooping jagged branch tiers narrowing to a spire."""
    tapered_trunk(m, h * 0.8, 0.22, 0.06)
    tiers = 9 if near() else 5
    for i in range(tiers):
        t = i / (tiers - 1)
        y = h * (0.2 + 0.72 * t)
        r = h * 0.2 * (1 - t) ** 0.9 + 0.35
        skirt(m, y, r, r * 0.55, 10 if near() else 6, "Conifer", twist=i * 0.7)
    skirt(m, h * 0.98, 0.35, 0.9, 5, "Conifer")


def cedar_tree(m, h=17.0):
    """Western red cedar: buttressed trunk, long sweeping skirts that droop strongly."""
    tapered_trunk(m, h * 0.85, 0.3, 0.07)
    tiers = 8 if near() else 5
    for i in range(tiers):
        t = i / (tiers - 1)
        y = h * (0.14 + 0.8 * t)
        r = h * 0.16 * (1 - t) ** 0.75 + 0.45
        skirt(m, y, r, r * 0.95, 12 if near() else 6, "Conifer", jag=0.25, twist=i * 1.1)
    skirt(m, h * 0.97, 0.45, 1.2, 5, "Conifer")


def street_sign(m):
    """Street-name post: galvanised pole, two crossed green blades with white borders, finial.
    Blade A runs along local x (top), blade B along z; Godot adds the names as Label3D text."""
    m.box((0, 1.6, 0), (0.07, 3.2, 0.07), "FrameLight", skip=("-y",))
    m.box((0, 3.27, 0), (0.1, 0.1, 0.1), "FrameLight")
    for (sx, sz, y) in ((1.3, 0.04, 3.02), (0.04, 1.3, 2.74)):
        m.box((0, y, 0), (sx, 0.24, sz), "SignGreen")
        if near():
            for dy in (-0.11, 0.11):
                m.box((0, y + dy, 0), (sx + 0.005, 0.015, sz + 0.005), "TrimPaint")


def park_sign(m):
    """Timber park sign: two posts, routed board with a dark green field."""
    for x in (-1.1, 1.1):
        m.box((x, 0.7, 0), (0.14, 1.4, 0.14), "Cedar", skip=("-y",))
    m.box((0, 1.15, 0), (2.5, 0.6, 0.08), "Cedar")
    m.box((0, 1.15, 0.045), (2.3, 0.45, 0.01), "SignGreen")
    m.box((0, 1.15, -0.045), (2.3, 0.45, 0.01), "SignGreen")
    m.box((0, 1.5, 0), (2.7, 0.08, 0.16), "Cedar")


def bust_figure(m, base_y):
    """Bronze bust: shoulders and lapelled coat, neck, head with brow, nose and ears."""
    m.box((0, base_y + 0.16, 0), (0.62, 0.32, 0.34), "Bronze", skip=("-y",))  # truncated chest
    blob(m, 0, base_y + 0.36, 0, 0.36, 0.14, 0.18, "Bronze", seg=10, rings=5)  # shoulder line
    blob(m, 0, base_y + 0.55, 0.0, 0.07, 0.08, 0.075, "Bronze", seg=8, rings=4)
    blob(m, 0, base_y + 0.73, 0.0, 0.12, 0.155, 0.135, "Bronze", seg=12, rings=7)
    if near():
        blob(m, 0, base_y + 0.72, 0.125, 0.025, 0.04, 0.035, "Bronze", seg=6, rings=3)  # nose
        blob(m, 0, base_y + 0.78, 0.105, 0.085, 0.02, 0.03, "Bronze", seg=6, rings=3)  # brow ridge
        for sx in (-1, 1):
            blob(m, sx * 0.12, base_y + 0.73, -0.01, 0.02, 0.04, 0.03, "Bronze", seg=6, rings=3)  # ears
            prism(m, (sx * 0.05, base_y + 0.46, 0.172), (sx * 0.15, base_y + 0.12, 0.172), 0.05, 0.012, "Bronze")  # lapels


def statue_bust(m):
    """Memorial bust on a stepped limestone pedestal; the front face carries the name plaque."""
    m.box((0, 0.1, 0), (1.6, 0.2, 1.6), "Limestone")
    m.box((0, 0.75, 0), (0.9, 1.1, 0.9), "Limestone", skip=("-y",))
    m.box((0, 1.34, 0), (1.05, 0.08, 1.05), "Limestone")
    m.box((0, 0.85, 0.455), (0.62, 0.36, 0.01), "Bronze")  # plaque
    bust_figure(m, 1.38)


def monument_plinth(m):
    """Atatürk Square monument base: three granite steps, a tall pedestal, bronze cornice band
    and a 2.6 m standing figure placed on top in Godot (statue_figure)."""
    for i, (w, h) in enumerate(((7.0, 0.3), (5.6, 0.3), (4.2, 0.3))):
        m.box((0, 0.15 + i * 0.3, 0), (w, h, w), "Limestone", skip=("-y",))
    m.box((0, 0.9 + 1.5, 0), (2.4, 3.0, 2.4), "Limestone", skip=("-y",))
    m.box((0, 3.95, 0), (2.7, 0.14, 2.7), "Bronze")
    m.box((0, 4.08, 0), (2.5, 0.12, 2.5), "Limestone")
    m.box((0, 2.4, 1.215), (1.6, 0.9, 0.02), "Bronze")  # inscription panel


def loft(m, rings, mat, n=10):
    """Closed-top loft through elliptical rings [(cx, y, cz, rx, rz), ...] (statue limbs, coat)."""
    pts = [[(cx + rx * math.cos(math.tau * j / n), y, cz + rz * math.sin(math.tau * j / n)) for j in range(n)]
           for (cx, y, cz, rx, rz) in rings]
    for i in range(len(pts) - 1):
        for j in range(n):
            k = (j + 1) % n
            a = math.tau * (j + 0.5) / n
            m.face([pts[i][j], pts[i][k], pts[i + 1][k], pts[i + 1][j]], mat, (math.cos(a), 0.05, math.sin(a)))
    top = pts[-1]
    m.face(list(reversed(top)), mat, (0, 1, 0))


def statue_figure(m):
    """2.6 m bronze standing figure in a long greatcoat and kalpak, left hand on the coat,
    right arm raised forward-low (pointing the way); faces +z."""
    s = 1.45  # scale from a 1.8 m figure
    def r(v): return v * s
    for sx in (-1, 1):  # boots and trouser legs under the coat hem
        loft(m, [(r(0.1 * sx), 0.0, r(0.03), r(0.07), r(0.13)), (r(0.1 * sx), r(0.12), r(0.0), r(0.065), r(0.09)),
                 (r(0.1 * sx), r(0.45), 0, r(0.07), r(0.075))], "Bronze", n=8)
    loft(m, [(0, r(0.42), 0, r(0.3), r(0.2)), (0, r(0.9), 0, r(0.23), r(0.15)), (0, r(1.25), 0, r(0.21), r(0.13)),
             (0, r(1.42), 0, r(0.24), r(0.13)), (0, r(1.5), 0, r(0.12), r(0.09))], "Bronze", n=12)  # greatcoat
    blob(m, 0, r(1.47), 0, r(0.25), r(0.06), r(0.13), "Bronze", seg=10, rings=4)  # shoulders / epaulettes
    loft(m, [(0, r(1.48), 0, r(0.05), r(0.05)), (0, r(1.56), 0, r(0.05), r(0.05))], "Bronze", n=8)  # neck
    blob(m, 0, r(1.65), r(0.01), r(0.085), r(0.11), r(0.1), "Bronze", seg=12, rings=7)  # head
    blob(m, 0, r(1.64), r(0.1), r(0.018), r(0.03), r(0.025), "Bronze", seg=6, rings=3)  # nose
    loft(m, [(0, r(1.7), 0, r(0.095), r(0.105)), (0, r(1.84), 0, r(0.1), r(0.11))], "Bronze", n=10)  # kalpak
    # Left arm down, hand at the coat front; right arm forward and out.
    prism(m, (r(-0.24), r(1.44), 0), (r(-0.27), r(1.12), r(0.02)), r(0.1), r(0.1), "Bronze")
    prism(m, (r(-0.27), r(1.12), r(0.02)), (r(-0.12), r(0.98), r(0.14)), r(0.09), r(0.09), "Bronze")
    prism(m, (r(0.24), r(1.44), 0), (r(0.36), r(1.2), r(0.16)), r(0.1), r(0.1), "Bronze")
    prism(m, (r(0.36), r(1.2), r(0.16)), (r(0.44), r(1.18), r(0.45)), r(0.085), r(0.085), "Bronze")
    blob(m, r(0.45), r(1.18), r(0.5), r(0.04), r(0.05), r(0.06), "Bronze", seg=6, rings=3)


HOUSES = {
    "house_craftsman": house_craftsman, "house_special": house_special, "house_modern": house_modern,
    "house_foursquare": house_foursquare, "house_splitlevel": house_splitlevel, "house_laneway": house_laneway,
    "house_bungalow": house_bungalow,
}
PROPS = {
    "fence_privacy": fence_privacy, "fence_lattice": lambda m: fence_privacy(m, True), "fence_picket": fence_picket,
    "hedge": hedge, "garden_bed": garden_bed, "raised_bed": raised_bed, "patio_set": patio_set, "bbq": bbq,
    "bins_trio": bins_trio, "garage_single": garage_single, "shed": shed, "utility_pole": utility_pole,
    "utility_pole_transformer": lambda m: utility_pole(m, True), "tree_fir": fir, "tree_cedar": cedar_tree,
    "street_sign": street_sign, "park_sign": park_sign, "statue_bust": statue_bust, "monument_plinth": monument_plinth, "statue_figure": statue_figure,
}
ALL = dict(HOUSES, **PROPS)


def build(names=None, bake=True):
    global LOD
    os.makedirs(OUT, exist_ok=True)
    col = bpy.data.collections.get("CityKit") or bpy.data.collections.new("CityKit")
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    manifest_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    for name in names or ALL:
        for lod in ("near", "far"):
            LOD = lod
            for o in list(col.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            m = XMesh()
            ALL[name](m)
            obj = m.emit(name, col)
            tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            if bake and lod == "near":
                bake_ao(obj)
            mats = [mt.name for mt in obj.data.materials]
            parts = split_by_material(obj)
            export(parts, os.path.join(OUT, name + ("" if lod == "near" else "_far") + ".glb"))
            manifest.setdefault(name, {})[lod] = {"triangles": tris, "materials": mats}
            print(f"HOUSEKIT {name} {lod}: {tris} tris, {len(mats)} materials")
    LOD = "near"
    json.dump(manifest, open(manifest_path, "w"), indent=1)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def preview(names=None, spacing=16.0):
    global LOD
    LOD = "near"
    col = bpy.data.collections.get("HousePreview") or bpy.data.collections.new("HousePreview")
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    made = []
    for i, name in enumerate(names or HOUSES):
        m = XMesh()
        ALL[name](m)
        o = m.emit(name, col)
        o.location.x = i * spacing
        made.append(o.name)
    return made


if globals().get("PREVIEW"):
    print(preview(globals().get("NAMES")))
elif globals().get("BUILD", True):
    build(globals().get("NAMES"), globals().get("BAKE", True))
