"""City kit: procedural modular architecture for Rainline (downtown + residential).

Coordinates in this file are GODOT space: x right, y up, z out of the facade.
A facade module's origin is the bottom centre of its bay and its front plane is z = 0;
material extends back to z = -0.3 (party wall depth). Godot: +Y up, facade faces +Z.

Module contract (drop-in for world/downtown/assets, see DowntownDistrict.build_building):
  bay_apartment_{0,1,2}, bay_office_{0,1,2}   4.0 x 3.2 m upper-floor bays
  storefront_{0,1,2}, entrance_{0,1,2}        4.0 x 4.2 m ground-floor bays
  blank_wall 4 x 3.2 x 0.3 (scaled), roof_slab 4 x 4 centred z=-2 (scaled),
  parapet 4 m, balcony, canopy, awning
Styles: 0 warehouse brick, 1 civic limestone, 2 contemporary charcoal/curtain wall.

Every module: planar metre-scale UVs (box projection by face normal), ambient occlusion
baked to the "AO" vertex colour attribute with Cycles, split into one mesh per material
(named Kit<Material>) and exported as <name>.glb plus a hand-built <name>_far.glb.
"""
import bmesh
import bpy
import json
import math
import os
from mathutils import Vector

ROOT = r"C:\GodotProjects\delivery-simulator-2026\world\citykit"
OUT = os.path.join(ROOT, "modules")
FLOOR = 3.2
GROUND = 4.2
BAY = 4.0

STYLE = [
    # wall, trim, frame, fascia, office wall
    {"wall": "BrickRed", "trim": "Limestone", "frame": "FrameDark", "fascia": "PaintGreen", "office": "BrickRed"},
    {"wall": "Limestone", "trim": "Concrete", "frame": "FrameBronze", "fascia": "PaintNavy", "office": "Limestone"},
    {"wall": "BrickCharcoal", "trim": "Concrete", "frame": "FrameLight", "fascia": "MetalPanel", "office": "MetalPanel"},
]


def G(x, y, z):
    """Godot (x, y up, z out) -> Blender (x, y forward, z up)."""
    return Vector((x, -z, y))


class Mesh:
    """Face soup with intended normals, so every face winds outward without recalculation."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def slot(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def face(self, pts, mat, normal):
        verts = [self.bm.verts.new(G(*p)) for p in pts]
        f = self.bm.faces.new(verts)
        f.normal_update()
        if f.normal.dot(G(*normal)) < 0:
            f.normal_flip()
        f.material_index = self.slot(mat)
        return f

    def quad_z(self, x0, x1, y0, y1, z, mat, facing=1):
        return self.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], mat, (0, 0, facing))

    def box(self, c, s, mat, skip=()):
        cx, cy, cz = c
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        x0, x1, y0, y1, z0, z1 = cx - hx, cx + hx, cy - hy, cy + hy, cz - hz, cz + hz
        sides = {
            "+z": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            "-z": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "+x": ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0)),
            "-x": ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
            "+y": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "-y": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        }
        for key, (pts, n) in sides.items():
            if key not in skip:
                self.face(pts, mat, n)

    def wall(self, x0, x1, y0, y1, openings, mat, reveal=0.22, reveal_mat=None, z=0.0, margin=0.25):
        """Front wall at z with rectangular openings and inward reveals.
        The grid gets extra lines `margin` around each opening so baked vertex AO stays local."""
        xs, ys = {x0, x1}, {y0, y1}
        for ox0, ox1, oy0, oy1 in openings:
            xs |= {ox0, ox1, max(x0, ox0 - margin), min(x1, ox1 + margin)}
            ys |= {oy0, oy1, max(y0, oy0 - margin), min(y1, oy1 + margin)}
        xs, ys = sorted(xs), sorted(ys)
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if any(ox0 < cx < ox1 and oy0 < cy < oy1 for ox0, ox1, oy0, oy1 in openings):
                    continue
                self.quad_z(xs[i], xs[i + 1], ys[j], ys[j + 1], z, mat)
        rm = reveal_mat or mat
        zb = z - reveal
        for ox0, ox1, oy0, oy1 in openings:
            self.face([(ox0, oy0, z), (ox0, oy0, zb), (ox0, oy1, zb), (ox0, oy1, z)], rm, (1, 0, 0))
            self.face([(ox1, oy0, z), (ox1, oy0, zb), (ox1, oy1, zb), (ox1, oy1, z)], rm, (-1, 0, 0))
            self.face([(ox0, oy0, z), (ox1, oy0, z), (ox1, oy0, zb), (ox0, oy0, zb)], rm, (0, 1, 0))
            self.face([(ox0, oy1, z), (ox1, oy1, z), (ox1, oy1, zb), (ox0, oy1, zb)], rm, (0, -1, 0))

    def window(self, x0, x1, y0, y1, z, frame, glass="Glass", profile=0.06, depth=0.08, mullions=(), transoms=()):
        """Frame perimeter, mullions/transoms and a glass pane set 4 cm behind the frame face."""
        p, d = profile, depth
        zc = z - d / 2
        self.box(((x0 + x1) / 2, y0 + p / 2, zc), (x1 - x0, p, d), frame, skip=("-z",))
        self.box(((x0 + x1) / 2, y1 - p / 2, zc), (x1 - x0, p, d), frame, skip=("-z",))
        self.box((x0 + p / 2, (y0 + y1) / 2, zc), (p, y1 - y0 - 2 * p, d), frame, skip=("-z", "+y", "-y"))
        self.box((x1 - p / 2, (y0 + y1) / 2, zc), (p, y1 - y0 - 2 * p, d), frame, skip=("-z", "+y", "-y"))
        for mx in mullions:
            self.box((mx, (y0 + y1) / 2, zc + 0.005), (p * 0.8, y1 - y0 - 2 * p, d * 0.9), frame, skip=("-z", "+y", "-y"))
        for ty in transoms:
            self.box(((x0 + x1) / 2, ty, zc + 0.01), (x1 - x0 - 2 * p, p * 0.8, d * 0.9), frame, skip=("-z", "-x", "+x"))
        self.quad_z(x0 + p, x1 - p, y0 + p, y1 - p, z - d + 0.02, glass)

    def emit(self, name, collection):
        mesh = bpy.data.meshes.new(name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.mats:
            mesh.materials.append(kit_material(m))
        uv = mesh.uv_layers.new(name="UVMap")
        # Planar projection in metres, picked per face from its dominant axis.
        for poly in mesh.polygons:
            n = poly.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            for li in poly.loop_indices:
                co = mesh.vertices[mesh.loops[li].vertex_index].co
                if ax == 0:
                    uv.data[li].uv = (co.y * (-1 if n.x > 0 else 1), co.z)
                elif ax == 1:
                    uv.data[li].uv = (co.x * (1 if n.y < 0 else -1), co.z)
                else:
                    uv.data[li].uv = (co.x, co.y)
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        return obj


PALETTE = {
    "BrickRed": ("a24c35", 0.85), "BrickBuff": ("c9a979", 0.85), "BrickCharcoal": ("4a423e", 0.85),
    "Stucco": ("e6dfd0", 0.85), "Concrete": ("a3a49e", 0.85), "Limestone": ("d3cab6", 0.75),
    "MetalPanel": ("343b41", 0.45), "RoofGravel": ("8a877f", 0.95), "Slate": ("3c4248", 0.7),
    "Cedar": ("8b6141", 0.65), "FrameDark": ("1f2427", 0.4), "FrameBronze": ("4a3b2c", 0.4),
    "FrameLight": ("9ea3a6", 0.35), "Glass": ("1d3640", 0.1), "Spandrel": ("1b2328", 0.15),
    "PaintGreen": ("24493a", 0.6), "PaintNavy": ("22334a", 0.6), "Awning": ("3d5a49", 0.9),
    "Rail": ("22282b", 0.45), "Door": ("2a3134", 0.5), "PartyBrick": ("6e4434", 0.9),
}


def kit_material(key):
    name = "Kit" + key
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    h, rough = PALETTE[key]
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    bsdf.inputs["Base Color"].default_value = (*lin, 1)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


# ---------------------------------------------------------------- facade modules

def bay_apartment(m, s, lod):
    st = STYLE[s]
    wall, trim, frame = st["wall"], st["trim"], st["frame"]
    if lod == "far":
        m.quad_z(-2, 2, 0, FLOOR, 0, wall)
        for x0, x1, y0, y1 in apartment_openings(s):
            m.quad_z(x0, x1, y0, y1, 0.01, "Glass")
        return
    ops = apartment_openings(s)
    m.wall(-2, 2, 0, FLOOR, ops, wall, reveal=0.24 if s != 1 else 0.3)
    if s == 0:
        # Two tall sash windows, stone sills, stone lintels and a string course.
        for x0, x1, y0, y1 in ops:
            m.window(x0, x1, y0, y1, -0.12, frame, transoms=[(y0 + y1) / 2], mullions=[(x0 + x1) / 2])
            m.box(((x0 + x1) / 2, y0 - 0.04, 0.03), (x1 - x0 + 0.24, 0.08, 0.14), trim, skip=("-z",))
            m.box(((x0 + x1) / 2, y1 + 0.11, 0.02), (x1 - x0 + 0.2, 0.22, 0.04), trim, skip=("-z",))
        m.box((0, 0.06, 0.02), (BAY, 0.12, 0.04), trim, skip=("-z", "-x", "+x"))
    elif s == 1:
        # Deep stone surround, floor-to-head French window with a juliet railing.
        (x0, x1, y0, y1), = ops
        m.window(x0, x1, y0, y1, -0.16, frame, mullions=[(x0 + x1) / 2], transoms=[y1 - 0.45])
        for x in (x0 - 0.09, x1 + 0.09):
            m.box((x, (y0 + y1) / 2, 0.025), (0.18, y1 - y0 + 0.36, 0.05), trim, skip=("-z",))
        m.box(((x0 + x1) / 2, y1 + 0.13, 0.025), (x1 - x0 + 0.36, 0.26, 0.05), trim, skip=("-z",))
        m.box(((x0 + x1) / 2, y0 - 0.05, 0.05), (x1 - x0 + 0.4, 0.1, 0.1), trim, skip=("-z",))
        rail_z = 0.12
        m.box(((x0 + x1) / 2, y0 + 0.95, rail_z), (x1 - x0, 0.05, 0.05), "Rail", skip=("-z",))
        m.box(((x0 + x1) / 2, y0 + 0.1, rail_z), (x1 - x0, 0.04, 0.04), "Rail", skip=("-z",))
        for i in range(9):
            x = x0 + 0.12 + i * (x1 - x0 - 0.24) / 8
            m.box((x, y0 + 0.52, rail_z), (0.022, 0.82, 0.022), "Rail", skip=("-z", "+y", "-y"))
    else:
        # Contemporary: projecting metal window box, slab-edge band, flush glazing.
        (x0, x1, y0, y1), = ops
        m.window(x0, x1, y0, y1, -0.1, frame, mullions=[x0 + (x1 - x0) * 0.62])
        d = 0.28
        m.box(((x0 + x1) / 2, y1 + 0.04, d / 2), (x1 - x0 + 0.16, 0.08, d), "MetalPanel", skip=("-z",))
        m.box(((x0 + x1) / 2, y0 - 0.04, d / 2), (x1 - x0 + 0.16, 0.08, d), "MetalPanel", skip=("-z",))
        for x in (x0 - 0.04, x1 + 0.04):
            m.box((x, (y0 + y1) / 2, d / 2), (0.08, y1 - y0, d), "MetalPanel", skip=("-z", "+y", "-y"))
        m.box((0, 0.1, 0.03), (BAY, 0.2, 0.06), trim, skip=("-z", "-x", "+x"))


def apartment_openings(s):
    if s == 0:
        return [(-1.45, -0.45, 0.8, 2.7), (0.45, 1.45, 0.8, 2.7)]
    if s == 1:
        return [(-1.15, 1.15, 0.25, 2.75)]
    return [(-1.5, 0.9, 0.55, 2.75)]


def bay_office(m, s, lod):
    st = STYLE[s]
    wall, trim, frame = st["office"], st["trim"], st["frame"]
    if lod == "far":
        if s == 2:
            m.quad_z(-2, 2, 0, FLOOR, 0, "Glass")
            m.quad_z(-2, 2, 0, 0.9, 0.005, "Spandrel")
        else:
            m.quad_z(-2, 2, 0, FLOOR, 0, wall)
            m.quad_z(-1.6, 1.6, 0.85, 3.0, 0.01, "Glass")
        return
    if s == 0:
        # Brick piers and a three-light steel ribbon window over a brick spandrel.
        op = (-1.6, 1.6, 0.85, 3.0)
        m.wall(-2, 2, 0, FLOOR, [op], wall, reveal=0.2)
        m.window(*op, -0.1, frame, mullions=[-0.53, 0.53], transoms=[2.35], profile=0.07)
        m.box((0, 0.8, 0.03), (3.4, 0.1, 0.12), trim, skip=("-z",))
    elif s == 1:
        # Stone fins frame full-height glazing above a stone spandrel.
        op = (-1.75, 1.75, 0.75, 3.05)
        m.wall(-2, 2, 0, FLOOR, [op], wall, reveal=0.12)
        m.window(*op, -0.06, frame, mullions=[0.0])
        for x in (-1.85, 1.85):
            m.box((x, FLOOR / 2, 0.2), (0.3, FLOOR, 0.4), wall, skip=("-z", "+y", "-y"))
    else:
        # Unitised curtain wall: vision glass, back-painted spandrel, pressure caps.
        m.quad_z(-2, 2, 0.9, FLOOR, -0.06, "Glass")
        m.quad_z(-2, 2, 0, 0.9, -0.05, "Spandrel")
        for x in (-2, 0, 2):
            w = 0.07 if abs(x) == 2 else 0.06
            m.box((x - (w / 2 if x == 2 else -w / 2 if x == -2 else 0), FLOOR / 2, 0.0), (w, FLOOR, 0.12), frame, skip=("-z", "+y", "-y"))
        for y in (0.04, 0.9):
            m.box((0, y, -0.01), (BAY, 0.07, 0.1), frame, skip=("-z", "-x", "+x"))


def storefront(m, s, lod, entrance):
    st = STYLE[s]
    wall, trim, frame, fascia = st["wall"], st["trim"], st["frame"], st["fascia"]
    pier = 0.42 if s != 2 else 0.24
    if lod == "far":
        m.quad_z(-2, 2, 3.15, GROUND, 0.02, fascia)
        m.quad_z(-2, -2 + pier, 0, 3.15, 0, wall)
        m.quad_z(2 - pier, 2, 0, 3.15, 0, wall)
        m.quad_z(-2 + pier, 2 - pier, 0, 3.15, -0.15, "Glass")
        return
    # Piers, fascia (sign band) and a stone cornice.
    for x in (-2 + pier / 2, 2 - pier / 2):
        m.box((x, 1.575, -0.15), (pier, 3.15, 0.3), wall, skip=("-z", "-y"))
    m.box((0, 3.65, -0.12), (BAY, 1.0, 0.24), fascia, skip=("-z",))
    m.box((0, 4.13, 0.06), (BAY, 0.14, 0.42), trim, skip=("-z",))
    m.box((0, 3.12, -0.15), (BAY - 2 * pier, 0.06, 0.3), trim, skip=("-z", "-x", "+x"))  # head soffit
    x0, x1 = -2 + pier, 2 - pier
    if not entrance:
        bulk = 0.55
        m.box((0, bulk / 2, -0.12), (x1 - x0, bulk, 0.18), fascia if s != 1 else trim, skip=("-z", "-x", "+x"))
        m.window(x0, x1, bulk, 3.09, -0.2, frame, mullions=[(x0 + x1) / 2], transoms=[2.55], profile=0.07, depth=0.1)
    else:
        door = 1.84
        # Sidelights either side of an open double door; the 1.84 m doorway stays clear.
        for a, b in ((x0, -door / 2), (door / 2, x1)):
            m.window(a, b, 0.0, 2.55, -0.2, frame, transoms=[0.45], profile=0.07, depth=0.1)
        m.window(x0, x1, 2.55, 3.09, -0.2, frame, mullions=[-door / 2, door / 2], profile=0.07, depth=0.1)
        for side in (-1, 1):
            # Door leaf swung 90 degrees into the lobby, hinged at the jamb.
            hx = side * door / 2
            m.box((hx - side * 0.03, 1.27, -0.66), (0.05, 2.5, 0.88), frame, skip=())
            m.box((hx - side * 0.06, 1.05, -0.62), (0.03, 0.04, 0.5), "FrameLight")
        m.box((0, 0.012, -0.2), (door, 0.024, 0.4), trim, skip=("-y", "-z"))  # threshold


def blank_wall(m, lod):
    # Party wall; Godot scales it non-uniformly, so materials there are world-triplanar.
    m.box((0, FLOOR / 2, -0.15), (BAY, FLOOR, 0.3), "PartyBrick", skip=("-z",) if lod == "far" else ())


def roof_slab(m, lod):
    m.box((0, 0.0, -2.0), (BAY, 0.2, BAY), "Concrete", skip=("+y",))
    m.face([(-2, 0.1, 0), (2, 0.1, 0), (2, 0.1, -4), (-2, 0.1, -4)], "RoofGravel", (0, 1, 0))


def interior_slab(m, lod):
    # Same envelope as roof_slab, finished as a stone-paved lobby floor (and plain soffit).
    m.box((0, 0.0, -2.0), (BAY, 0.2, BAY), "Concrete", skip=("+y",))
    m.face([(-2, 0.1, 0), (2, 0.1, 0), (2, 0.1, -4), (-2, 0.1, -4)], "Limestone", (0, 1, 0))


def parapet(m, lod):
    m.box((0, 0.42, -0.14), (BAY, 0.84, 0.28), "Concrete", skip=("-x", "+x", "-y"))
    m.box((0, 0.88, -0.14), (BAY, 0.08, 0.38), "FrameDark", skip=("-x", "+x"))


def balcony(m, lod):
    m.box((0, 0.02, 0.62), (3.5, 0.18, 1.3), "Concrete")
    if lod == "far":
        m.quad_z(-1.7, 1.7, 0.1, 1.1, 1.25, "Rail")
        return
    m.box((0, -0.09, 1.23), (3.5, 0.04, 0.04), "FrameDark", skip=())  # drip edge
    m.box((0, 1.1, 1.22), (3.5, 0.05, 0.06), "Rail")
    for x in (-1.72, 1.72):
        m.box((x, 1.1, 0.62), (0.05, 0.05, 1.2), "Rail")
        m.box((x, 0.6, 1.22), (0.05, 1.0, 0.05), "Rail", skip=("+y", "-y"))
    for i in range(13):
        x = -1.6 + i * 3.2 / 12
        m.box((x, 0.6, 1.22), (0.022, 0.98, 0.022), "Rail", skip=("+y", "-y"))


def canopy(m, lod):
    m.box((0, 0.0, 0.62), (3.8, 0.12, 1.36), "FrameDark")
    m.box((0, 0.075, 0.62), (3.6, 0.03, 1.26), "Glass", skip=("-y",))
    if lod != "far":
        for x in (-1.6, 1.6):
            # Tie rod back to the wall above the canopy.
            m.box((x, 0.42, 0.6), (0.03, 0.03, 1.33), "FrameDark", skip=())


def awning(m, lod):
    # Sloped fabric with a scalloped-looking valance strip and steel arms.
    m.face([(-1.95, 0, 0), (1.95, 0, 0), (1.95, -0.42, 1.3), (-1.95, -0.42, 1.3)], "Awning", (0, 1, 0.3))
    m.face([(-1.95, 0, 0), (1.95, 0, 0), (1.95, -0.42, 1.3), (-1.95, -0.42, 1.3)], "Awning", (0, -1, -0.3))
    m.quad_z(-1.95, 1.95, -0.66, -0.42, 1.3, "Awning")
    if lod != "far":
        for x in (-1.85, 1.85):
            m.box((x, -0.3, 0.65), (0.03, 0.03, 1.3), "FrameDark")


# ---------------------------------------------------------------- residential modules
# Walk-up apartments reuse the 4 m bay; townhouses use a 5 m unit, 3.0 m floors and a
# 0.45 m raised ground floor reached by front steps.
TH_W = 5.0
TH_FLOOR = 3.0
TH_DEPTH = 10.0
TH_PLINTH = 0.45
TH_PITCH = math.radians(38)
TH_STYLE = [
    {"wall": "BrickRed", "trim": "Limestone", "frame": "FrameLight", "door": "PaintGreen", "ground": "BrickRed", "roof": "Slate"},
    {"wall": "Stucco", "trim": "Limestone", "frame": "FrameLight", "door": "PaintNavy", "ground": "Stucco", "roof": "Slate"},
    {"wall": "Cedar", "trim": "Concrete", "frame": "FrameDark", "door": "Door", "ground": "BrickCharcoal", "roof": "MetalPanel"},
]


def plain_wall(m, s, lod):
    # Style-matched wall strip for corners/remainders; scaled freely in Godot (triplanar).
    m.box((0, FLOOR / 2, -0.15), (BAY, FLOOR, 0.3), STYLE[s]["wall"], skip=("-z",))


def ground_residential(m, s, lod):
    st = STYLE[s]
    wall, trim, frame = st["wall"], st["trim"], st["frame"]
    op = (-1.2, 1.2, 1.2, 3.6)
    if lod == "far":
        m.quad_z(-2, 2, 0, GROUND, 0, wall)
        m.quad_z(*op, 0.01, "Glass")
        return
    m.wall(-2, 2, 0, GROUND, [op], wall, reveal=0.22)
    m.window(*op, -0.12, frame, mullions=[0.0], transoms=[3.0])
    m.box((0, 0.35, 0.04), (BAY, 0.7, 0.08), trim, skip=("-z", "-x", "+x"))  # rusticated plinth
    m.box((0, op[2] - 0.05, 0.06), (2.7, 0.1, 0.12), trim, skip=("-z",))
    m.box((0, GROUND - 0.12, 0.05), (BAY, 0.24, 0.1), trim, skip=("-z", "-x", "+x"))  # first-floor band


def entrance_residential(m, s, lod):
    st = STYLE[s]
    wall, trim, frame = st["wall"], st["trim"], st["frame"]
    door = (-0.9, 0.9, 0.3, 3.05)
    if lod == "far":
        m.quad_z(-2, 2, 0, GROUND, 0, wall)
        m.quad_z(*door, 0.01, "Door")
        return
    m.wall(-2, 2, 0, GROUND, [door], wall, reveal=0.3, reveal_mat=trim)
    # Glazed double door with a fanlight, stone surround and two front steps.
    m.window(door[0], door[1], door[2], 2.55, -0.24, frame, mullions=[0.0], profile=0.09)
    m.window(door[0], door[1], 2.55, door[3], -0.24, frame, profile=0.07)
    for x in (door[0] - 0.12, door[1] + 0.12):
        m.box((x, (door[2] + door[3]) / 2 + 0.1, 0.04), (0.24, door[3] - door[2] + 0.2, 0.08), trim, skip=("-z",))
    m.box((0, door[3] + 0.2, 0.06), (2.3, 0.3, 0.12), trim, skip=("-z",))
    for i, (h, d) in enumerate(((0.3, 0.75), (0.15, 1.1))):
        m.box((0, h / 2 if i == 0 else 0.075, d / 2 - 0.0), (2.4 + i * 0.3, h if i == 0 else 0.15, d), trim, skip=("-z", "-y"))
    m.box((0, 0.35, 0.04), (BAY, 0.7, 0.08), trim, skip=("-z", "-x", "+x"))
    m.box((0, GROUND - 0.12, 0.05), (BAY, 0.24, 0.1), trim, skip=("-z", "-x", "+x"))
    # Wall lantern.
    m.box((1.3, 2.4, 0.08), (0.16, 0.3, 0.16), "FrameDark")


def cornice(m, s, lod):
    st = STYLE[s]
    if s == 0:
        # Corbelled brick frieze capped in stone.
        m.box((0, 0.3, -0.12), (BAY, 0.6, 0.24), st["wall"], skip=("-z", "-x", "+x", "-y"))
        for i in range(8):
            m.box((-1.75 + i * 0.5, 0.42, 0.04), (0.22, 0.16, 0.08), st["wall"], skip=("-z",))
        m.box((0, 0.66, 0.0), (BAY, 0.12, 0.5), st["trim"], skip=("-x", "+x"))
    elif s == 1:
        m.box((0, 0.3, -0.12), (BAY, 0.6, 0.24), st["wall"], skip=("-z", "-x", "+x", "-y"))
        m.box((0, 0.5, 0.06), (BAY, 0.16, 0.36), st["trim"], skip=("-x", "+x", "-z"))
        m.box((0, 0.66, 0.14), (BAY, 0.12, 0.56), st["trim"], skip=("-x", "+x"))
    else:
        m.box((0, 0.45, -0.14), (BAY, 0.9, 0.28), "MetalPanel", skip=("-x", "+x", "-y", "-z"))
        m.box((0, 0.92, -0.14), (BAY, 0.05, 0.34), "FrameLight", skip=("-x", "+x"))


def th_ground(m, s, lod):
    st = TH_STYLE[s]
    wall, trim, frame = st["ground"], st["trim"], st["frame"]
    door = (-2.05, -1.05, TH_PLINTH, TH_PLINTH + 2.2)
    win = (-0.35, 1.85, TH_PLINTH + 0.6, TH_PLINTH + 2.3) if s != 1 else (-0.2, 1.7, TH_PLINTH + 0.3, TH_PLINTH + 2.3)
    if lod == "far":
        m.quad_z(-2.5, 2.5, 0, TH_FLOOR + TH_PLINTH, 0, wall)
        m.quad_z(*door, 0.01, st["door"])
        m.quad_z(*win, 0.01, "Glass")
        return
    ops = [door] if s == 1 else [door, win]
    m.wall(-2.5, 2.5, 0, TH_FLOOR + TH_PLINTH, ops, wall, reveal=0.22)
    # Panelled front door with fanlight.
    m.quad_z(door[0], door[1], door[2], door[3] - 0.45, -0.2, st["door"])
    for y in (door[2] + 0.35, door[2] + 1.05):
        m.box(((door[0] + door[1]) / 2, y + 0.3, -0.19), (0.7, 0.55, 0.03), st["door"], skip=("-z",))
    m.window(door[0], door[1], door[3] - 0.45, door[3], -0.16, frame, mullions=[(door[0] + door[1]) / 2])
    m.box(((door[0] + door[1]) / 2 + 0.08, door[2] + 1.0, -0.15), (0.05, 0.05, 0.08), "FrameLight")  # knob
    # Stone steps up to the raised ground floor.
    for i in range(3):
        h = TH_PLINTH - i * 0.15
        m.box(((door[0] + door[1]) / 2, h / 2, 0.3 * (3 - i) / 2), (1.4, h, 0.3 * (3 - i)), trim, skip=("-z", "-y"))
    m.box((0, TH_PLINTH / 2, 0.02), (TH_W, TH_PLINTH, 0.04), trim, skip=("-z", "-x", "+x", "-y"))  # plinth band
    if s == 1:
        # Canted bay window projecting 0.7 m, with a lead-capped roof.
        x0, x1, y0, y1 = win
        depth, chamfer = 0.7, 0.45
        pts = [(x0, -0.0), (x0 + chamfer, depth), (x1 - chamfer, depth), (x1, 0.0)]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            nx, nz = -(bz - az), bx - ax  # outward (towards the street) facet normal
            m.face([(ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az)], "Glass", (nx, 0, nz))
            m.face([(ax, TH_PLINTH, az), (bx, TH_PLINTH, bz), (bx, y0, bz), (ax, y0, az)], trim, (nx, 0, nz))
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            m.box(((ax + bx) / 2, (y0 + y1) / 2, (az + bz) / 2 + 0.03), (0.07, y1 - y0, 0.07), frame)
        m.face([(x0, y1, 0), (x1, y1, 0), (x1 - chamfer, y1, depth), (x0 + chamfer, y1, depth)], trim, (0, -1, 0))
        m.face([(x0 - 0.05, y1 + 0.35, 0), (x1 + 0.05, y1 + 0.35, 0), (x1 - chamfer + 0.05, y1, depth + 0.08), (x0 + chamfer - 0.05, y1, depth + 0.08)], "MetalPanel", (0, 1, 0.5))
        m.box(((x0 + x1) / 2, TH_PLINTH + 0.02, 0.0), (x1 - x0, 0.04, 0.05), trim)
        # Porch hood on brackets over the door.
        m.box(((door[0] + door[1]) / 2, door[3] + 0.15, 0.35), (1.5, 0.1, 0.7), trim)
    else:
        x0, x1, y0, y1 = win
        m.window(x0, x1, y0, y1, -0.12, frame, mullions=[(x0 + x1) / 2], transoms=[y1 - 0.5])
        m.box(((x0 + x1) / 2, y0 - 0.04, 0.04), (x1 - x0 + 0.2, 0.08, 0.14), trim, skip=("-z",))
        if s == 0:
            m.box(((x0 + x1) / 2, y1 + 0.11, 0.02), (x1 - x0 + 0.2, 0.22, 0.04), trim, skip=("-z",))
            m.box(((door[0] + door[1]) / 2, door[3] + 0.11, 0.02), (1.2, 0.22, 0.04), trim, skip=("-z",))
        else:
            # Modern: steel entrance canopy.
            m.box(((door[0] + door[1]) / 2, door[3] + 0.2, 0.45), (1.6, 0.08, 0.9), "FrameDark")
    # Wall lamp beside the door.
    m.box((door[1] + 0.25, door[3] - 0.3, 0.08), (0.14, 0.26, 0.14), "FrameDark")


def th_upper(m, s, lod):
    st = TH_STYLE[s]
    wall, trim, frame = st["wall"], st["trim"], st["frame"]
    ops = [(-1.9, -0.6, 0.75, 2.45), (0.6, 1.9, 0.75, 2.45)] if s != 2 else [(-2.0, 0.6, 0.45, 2.65)]
    if lod == "far":
        m.quad_z(-2.5, 2.5, 0, TH_FLOOR, 0, wall)
        for op in ops:
            m.quad_z(*op, 0.01, "Glass")
        return
    m.wall(-2.5, 2.5, 0, TH_FLOOR, ops, wall, reveal=0.2)
    for x0, x1, y0, y1 in ops:
        if s == 2:
            m.window(x0, x1, y0, y1, -0.08, frame, mullions=[x0 + (x1 - x0) * 0.35])
            # Projecting box frame, as on the contemporary apartment bay.
            d = 0.22
            for (cx, cy, sx, sy) in (((x0 + x1) / 2, y1 + 0.03, x1 - x0 + 0.12, 0.06), ((x0 + x1) / 2, y0 - 0.03, x1 - x0 + 0.12, 0.06),
                                     (x0 - 0.03, (y0 + y1) / 2, 0.06, y1 - y0), (x1 + 0.03, (y0 + y1) / 2, 0.06, y1 - y0)):
                m.box((cx, cy, d / 2), (sx, sy, d), "MetalPanel", skip=("-z",))
        else:
            m.window(x0, x1, y0, y1, -0.12, frame, mullions=[(x0 + x1) / 2], transoms=[(y0 + y1) / 2])
            m.box(((x0 + x1) / 2, y0 - 0.04, 0.04), (x1 - x0 + 0.2, 0.08, 0.14), trim, skip=("-z",))
            if s == 0:
                m.box(((x0 + x1) / 2, y1 + 0.11, 0.02), (x1 - x0 + 0.2, 0.22, 0.04), trim, skip=("-z",))
            else:
                for x in (x0 - 0.07, x1 + 0.07):
                    m.box((x, (y0 + y1) / 2, 0.03), (0.14, y1 - y0 + 0.14, 0.06), trim, skip=("-z",))
                m.box(((x0 + x1) / 2, y1 + 0.1, 0.04), (x1 - x0 + 0.34, 0.14, 0.08), trim, skip=("-z",))
    if s == 0:
        m.box((0, 0.06, 0.02), (TH_W, 0.12, 0.04), trim, skip=("-z", "-x", "+x"))  # string course
    if s == 2:
        m.box((0, 0.08, 0.03), (TH_W, 0.16, 0.06), "FrameDark", skip=("-z", "-x", "+x"))


def th_roof(m, s, lod, dormer=False):
    """Roof over one unit: origin at the front wall top, ridge parallel to the street."""
    st = TH_STYLE[s]
    if s == 2:
        # Flat roof behind a metal-capped parapet.
        m.face([(-2.5, 0.05, 0), (2.5, 0.05, 0), (2.5, 0.05, -TH_DEPTH), (-2.5, 0.05, -TH_DEPTH)], "RoofGravel", (0, 1, 0))
        for z, n in ((0.0, 1), (-TH_DEPTH, -1)):
            m.box((0, 0.45, z - n * 0.14), (TH_W, 0.9, 0.28), st["wall"], skip=("-x", "+x", "-y"))
            m.box((0, 0.92, z - n * 0.14), (TH_W, 0.05, 0.34), "FrameLight", skip=("-x", "+x"))
        return
    over = 0.35
    half = TH_DEPTH / 2
    rise = math.tan(TH_PITCH) * half
    eave_y = -math.tan(TH_PITCH) * over
    for sign in (1, -1):
        z_eave = over if sign == 1 else -TH_DEPTH - over
        z_ridge = -half
        pts = [(-2.5, eave_y, z_eave), (2.5, eave_y, z_eave), (2.5, rise, z_ridge), (-2.5, rise, z_ridge)]
        m.face(pts, st["roof"], (0, 1, sign * 0.8))
        m.face(pts, st["roof"], (0, -1, -sign * 0.8)) if lod != "far" else None  # visible soffit from below
        if lod != "far":
            # Fascia board and half-round gutter along each eave.
            m.box((0, eave_y - 0.08, z_eave + sign * 0.02), (TH_W, 0.2, 0.04), "FrameLight" if s == 0 else "Stucco")
            m.box((0, eave_y - 0.1, z_eave + sign * 0.1), (TH_W, 0.1, 0.12), "FrameDark")
    if lod != "far":
        m.box((0, rise + 0.05, -half), (TH_W, 0.1, 0.22), "FrameDark")  # ridge cap
    if dormer and lod != "far":
        # Pitched dormer on the front slope.
        dz0, dz1 = -1.4, -0.4
        y0 = math.tan(TH_PITCH) * (-dz1)
        x0, x1 = -0.75, 0.75
        top = y0 + 1.3
        m.wall(x0, x1, y0, top, [(-0.45, 0.45, y0 + 0.2, top - 0.15)], st["wall"] if s == 0 else "Stucco", reveal=0.12, z=dz1)
        m.window(-0.45, 0.45, y0 + 0.2, top - 0.15, dz1 - 0.06, st["frame"], transoms=[y0 + 0.75])
        for x in (x0, x1):
            m.face([(x, y0, dz1), (x, top, dz1), (x, top, dz0 - 1.2), (x, y0 + 0.01, dz0 - 1.2)], st["wall"] if s == 0 else "Stucco", (1 if x > 0 else -1, 0, 0))
        for sx in (1, -1):
            m.face([(0, top + 0.6, dz1 + 0.15), (sx * (x1 + 0.15), top - 0.05, dz1 + 0.15), (sx * (x1 + 0.15), top - 0.05, dz0 - 1.3), (0, top + 0.6, dz0 - 1.3)], st["roof"], (sx, 1, 0))


def th_gable(m, s, lod):
    """End wall of a terrace: two floors plus the gable triangle, facing local +z, spanning TH_DEPTH."""
    st = TH_STYLE[s]
    h = TH_PLINTH + 2 * TH_FLOOR
    if s == 2:
        m.box((0, h / 2, -0.15), (TH_DEPTH, h, 0.3), st["wall"], skip=("-z", "-x", "+x"))
        return
    m.box((0, h / 2, -0.15), (TH_DEPTH, h, 0.3), st["wall"], skip=("-z", "-x", "+x"))
    rise = math.tan(TH_PITCH) * TH_DEPTH / 2
    m.face([(-TH_DEPTH / 2, h, 0), (TH_DEPTH / 2, h, 0), (0, h + rise, 0)], st["wall"], (0, 0, 1))
    if lod != "far":
        # Small attic window and a brick chimney breast on the gable.
        m.box((0, h + rise * 0.4, 0.02), (0.6, 0.6, 0.04), "Glass")
        m.box((0, h + rise * 0.4, 0.04), (0.74, 0.74, 0.02), st["trim"], skip=("-z",))


def th_chimney(m, s, lod):
    st = TH_STYLE[s]
    m.box((0, 0.7, 0), (0.7, 1.4, 1.1), "BrickRed" if s != 1 else "Stucco", skip=("-y",))
    m.box((0, 1.45, 0), (0.82, 0.1, 1.22), "Limestone", skip=("-y",))
    if lod != "far":
        for z in (-0.25, 0.25):
            m.box((0, 1.65, z), (0.2, 0.3, 0.2), "BrickRed")


MODULES = {}
for s in range(3):
    MODULES[f"plain_wall_{s}"] = (lambda m, lod, s=s: plain_wall(m, s, lod))
    MODULES[f"ground_residential_{s}"] = (lambda m, lod, s=s: ground_residential(m, s, lod))
    MODULES[f"entrance_residential_{s}"] = (lambda m, lod, s=s: entrance_residential(m, s, lod))
    MODULES[f"cornice_{s}"] = (lambda m, lod, s=s: cornice(m, s, lod))
    MODULES[f"th_ground_{s}"] = (lambda m, lod, s=s: th_ground(m, s, lod))
    MODULES[f"th_upper_{s}"] = (lambda m, lod, s=s: th_upper(m, s, lod))
    MODULES[f"th_roof_{s}"] = (lambda m, lod, s=s: th_roof(m, s, lod))
    MODULES[f"th_roof_dormer_{s}"] = (lambda m, lod, s=s: th_roof(m, s, lod, True))
    MODULES[f"th_gable_{s}"] = (lambda m, lod, s=s: th_gable(m, s, lod))
    MODULES[f"th_chimney_{s}"] = (lambda m, lod, s=s: th_chimney(m, s, lod))
for s in range(3):
    MODULES[f"bay_apartment_{s}"] = (lambda m, lod, s=s: bay_apartment(m, s, lod))
    MODULES[f"bay_office_{s}"] = (lambda m, lod, s=s: bay_office(m, s, lod))
    MODULES[f"storefront_{s}"] = (lambda m, lod, s=s: storefront(m, s, lod, False))
    MODULES[f"entrance_{s}"] = (lambda m, lod, s=s: storefront(m, s, lod, True))
MODULES.update({"blank_wall": blank_wall, "roof_slab": roof_slab, "interior_slab": interior_slab, "parapet": parapet,
                "balcony": balcony, "canopy": canopy, "awning": awning})


# ---------------------------------------------------------------- bake + export

def bake_ao(obj):
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
    except TypeError as err:
        print("engine:", err)
    scene.cycles.samples = 64
    me = obj.data
    # Face-corner domain: each corner bakes with its own flat face normal, so hard edges
    # don't average normals into neighbouring geometry the way point-domain AO does.
    if "AO" not in me.color_attributes:
        me.color_attributes.new("AO", "FLOAT_COLOR", "CORNER")
    me.color_attributes.active_color = me.color_attributes["AO"]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 0.6
    # Occlusion must come from this module only, not whatever else is in the user's scene.
    hidden = [o for o in scene.objects if o is not obj and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    try:
        bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    finally:
        for o in hidden:
            o.hide_render = False
    # Art direction: keep contact shadow but never crush to black; real-time SSAO adds the rest.
    for c in me.color_attributes["AO"].data:
        v = 0.4 + 0.6 * (c.color[0] ** 0.8)
        c.color = (v, v, v, 1.0)


def export(objs, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    kwargs = dict(filepath=path, use_selection=True, export_format="GLB", export_yup=True,
                  export_apply=True, export_normals=True, export_texcoords=True)
    try:
        bpy.ops.export_scene.gltf(**kwargs, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(**kwargs, export_colors=True)


def split_by_material(obj):
    """One object per material, named Kit<Material> (UrbanKit-style part contract)."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if len(obj.data.materials) > 1:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.context.selected_objects]
    for p in parts:
        used = {poly.material_index for poly in p.data.polygons}
        mat = p.data.materials[used.pop()] if used else p.data.materials[0]
        p.data.materials.clear()
        p.data.materials.append(mat)
        p.name = mat.name
        p.data.name = mat.name
    return parts


def build(names=None, bake=True):
    os.makedirs(OUT, exist_ok=True)
    src = os.path.join(OUT, "source")
    os.makedirs(src, exist_ok=True)
    open(os.path.join(src, ".gdignore"), "w").close()
    col = bpy.data.collections.get("CityKit")
    if col is None:
        col = bpy.data.collections.new("CityKit")
        bpy.context.scene.collection.children.link(col)
    manifest_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    for i, name in enumerate(names or MODULES):
        for lod in ("near", "far"):
            for o in list(col.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            m = Mesh()
            MODULES[name](m, lod)
            obj = m.emit(name, col)
            tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            if bake and lod == "near":
                bake_ao(obj)
            mats = [mt.name for mt in obj.data.materials]
            parts = split_by_material(obj)
            export(parts, os.path.join(OUT, name + ("" if lod == "near" else "_far") + ".glb"))
            manifest.setdefault(name, {})[lod] = {"triangles": tris, "materials": mats}
            print(f"KIT {name} {lod}: {tris} tris, {len(mats)} materials")
    json.dump(manifest, open(manifest_path, "w"), indent=1)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for me in [x for x in bpy.data.meshes if x.users == 0]:
        bpy.data.meshes.remove(me)
    # Editable source: every module laid out in a row (near LOD).
    preview(list(MODULES))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(src, "city_kit.blend"), copy=True)


def preview(names=None, lod="near", spacing=5.0):
    """Lay modules out in a row in the 'CityKitPreview' collection (no bake/export)."""
    col = bpy.data.collections.get("CityKitPreview")
    if col is None:
        col = bpy.data.collections.new("CityKitPreview")
        bpy.context.scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    objs = []
    for i, name in enumerate(names or MODULES):
        m = Mesh()
        MODULES[name](m, lod)
        obj = m.emit(name + ("_far" if lod == "far" else ""), col)
        obj.location.x = i * spacing
        objs.append(obj.name)
    return objs


if globals().get("PREVIEW"):
    print(preview(globals().get("NAMES"), globals().get("LOD", "near")))
elif globals().get("BUILD", True):
    build(globals().get("NAMES"), globals().get("BAKE", True))
