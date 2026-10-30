"""Sidewalk furniture library for Mert Road Studio (Blender 5.2, headless-safe).

    import mrs.furniture as F
    F.build_furniture()                      # -> collection MRS_Furniture (bakes the atlas on first use)
    F.export_library_glb("furniture.glb")    # every object as a named node at the origin, extras on

Twenty street-furniture objects (+ MRS_F_BusShelter_LOD1) built from bmesh primitives at real scale. All
of them share ONE texture atlas: `bake_atlas()` renders 30 procedural shader-node cells (painted / galvanised
/ stainless / cast metal, hardwood and recycled-plastic slats, concrete, granite, soil, foliage, printed
panels ...) through an orthographic Cycles emission capture into albedo / ORM / normal PNGs, and the
material MRS_FurnitureAtlas reads them through a plain Principled BSDF, so the glTF exporter writes real
textures (MRS_FurnitureGlass is the only other material). Every face is UV-mapped into its atlas cell:
tiling cells by box projection at 256 px per metre (islands placed at a seeded offset inside the cell,
scaled down uniformly only when larger than the cell), decal cells (map, timetable, flag, poster,
display, labels, tree grate) fitted to their panel.

Custom properties read by the placement solver (contract in docs/roads/FURNITURE.md):
    mrs_kind, mrs_footprint "[w, d]", mrs_access '{"front","back","left","right"}', mrs_zone,
    mrs_walkable, mrs_height  (+ mrs_facing, mrs_base_footprint, and mrs_pitch / mrs_anchor /
    mrs_lod1 / mrs_lod / mrs_lod_of where they apply)
Conventions: metres, Z up, origin = ground centre of the footprint (XY bounding-box centre, min z = 0),
local X along the kerb, +Y the front (left = -X, right = +X). Faces lying on the ground are removed.
Importing this module has no side effects.
"""
import json, math, os, random, zlib
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from .nodes import MRS
from .props import collection
from .assets import _box, _cyl, _tube, _lathe, _prism, _band, _ico, _ngon, _xf, _finish

TAU = math.pi * 2.0
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEX_DIR = os.path.join(ROOT, "tmp", "roads", "materials", "furniture")
COLLECTION = MRS + "Furniture"
ATLAS = MRS + "FurnitureAtlas"
GLASS = MRS + "FurnitureGlass"
AW, AH, PPM = 2048, 1024, 256          # atlas size (px) and tiling-cell density (px per metre)
BAKE_VERSION = 5
KINDS = ("bench", "bin", "bike_rack", "bus_shelter", "bus_pole", "info_board", "bollard", "barrier", "planter", "tree_pit",
         "tree_guard", "utility", "hydrant", "drain", "access_cover")
ZONES = ("furniture", "curb", "frontage", "flush", "gutter")
FACINGS = ("walk", "carriageway", "any")

# ============================================================================== atlas layout
# name, x, y, w, h (pixels, top-left origin), kind ("tile": box-projected at PPM, "decal": fitted), grain axis
CELLS = [
    ("wood", 0, 0, 512, 256, "tile", "u"), ("steel_dark", 512, 0, 256, 256, "tile", None), ("galv", 768, 0, 256, 256, "tile", None),
    ("stainless", 1024, 0, 256, 256, "tile", "u"), ("iron", 1280, 0, 256, 256, "tile", None), ("black", 1536, 0, 256, 256, "tile", None),
    ("alu", 1792, 0, 256, 256, "tile", "u"),
    ("concrete", 0, 256, 512, 256, "tile", None), ("green", 512, 256, 256, 256, "tile", None), ("blue", 768, 256, 256, 256, "tile", None),
    ("yellow", 1024, 256, 256, 256, "tile", None), ("red", 1280, 256, 256, 256, "tile", None), ("grey_light", 1536, 256, 256, 256, "tile", "v"),
    ("granite", 1792, 256, 256, 256, "tile", None),
    ("soil", 0, 512, 256, 384, "tile", None), ("rubber", 0, 896, 256, 128, "tile", None),
    ("map", 256, 512, 256, 512, "decal", None),
    ("poster", 512, 512, 256, 384, "decal", None), ("white", 512, 896, 256, 128, "tile", None),
    ("timetable", 768, 512, 256, 384, "decal", None), ("display", 768, 896, 256, 128, "decal", None),
    ("flag", 1024, 512, 256, 384, "decal", None), ("void", 1024, 896, 256, 128, "tile", None),
    ("grate_tree", 1280, 512, 256, 256, "decal", None),
    ("label_recycle", 1280, 768, 128, 128, "decal", None), ("label_hazard", 1408, 768, 128, 128, "decal", None),
    ("label_info", 1280, 896, 128, 128, "decal", None), ("label_litter", 1408, 896, 128, 128, "decal", None),
    ("iron_tread", 1536, 512, 256, 256, "tile", None), ("foliage", 1536, 768, 256, 256, "tile", None),
    ("plastic", 1792, 512, 256, 512, "tile", "v"),
]
CELL = {c[0]: c for c in CELLS}
CID = {c[0]: i for i, c in enumerate(CELLS)}
CID["glass"] = len(CELLS)               # faces of the glass material (no atlas cell)


def cell_uv_rect(name):
    """(u0, v0, u1, v1) of a cell in Blender UV space (v up)."""
    _, x, y, w, h, _, _ = CELL[name]
    return x / AW, 1.0 - (y + h) / AH, (x + w) / AW, 1.0 - y / AH


def _nt(mat):
    """Node tree of a material (5.x materials are always node based; older builds need use_nodes)."""
    if mat.node_tree is None: mat.use_nodes = True
    return mat.node_tree


def _lin(hexs):
    h = hexs.lstrip("#"); c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _k(rgb, f):
    return tuple(min(1.0, max(0.0, c * f)) for c in rgb)


# ============================================================================== shader-node helper
class _G:
    """Compact shader-node graph builder: constants or sockets everywhere, sockets returned."""
    def __init__(self, nt):
        self.nt = nt; self.i = 0
        tc = self.n("ShaderNodeTexCoord"); self.P = tc.outputs["Object"]; self.UV = tc.outputs["UV"]

    def n(self, idname, **props):
        nd = self.nt.nodes.new(idname); nd.location = (-3200 + 230 * (self.i % 15), 1600 - 280 * (self.i // 15)); self.i += 1
        for k, v in props.items(): setattr(nd, k, v)
        return nd

    def put(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket): self.nt.links.new(val, sock)
        elif isinstance(val, (tuple, list)) and len(val) == 3 and sock.type == "RGBA": sock.default_value = (*val, 1.0)
        else: sock.default_value = val

    @staticmethod
    def _on(s): return getattr(s, "enabled", True)

    def inp(self, nd, key):
        if isinstance(key, int): return nd.inputs[key]
        for s in nd.inputs:
            if s.identifier == key and self._on(s): return s
        for s in nd.inputs:
            if s.name == key and self._on(s): return s
        raise KeyError("%s has no input %s" % (nd.bl_idname, key))

    def out(self, nd, key=0):
        outs = [o for o in nd.outputs if self._on(o)]
        if isinstance(key, int): return outs[key]
        return next(o for o in outs if o.identifier == key or o.name == key)

    def node(self, idname, ins=None, props=None, out=0):
        nd = self.n(idname, **(props or {}))
        for k, v in (ins or {}).items(): self.put(self.inp(nd, k), v)
        return nd if out is None else self.out(nd, out)

    # math
    def m(self, op, a, b=0.0, c=None, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(nd.inputs[0], a); self.put(nd.inputs[1], b)
        if c is not None: self.put(nd.inputs[2], c)
        return nd.outputs[0]
    def add(self, a, b): return self.m("ADD", a, b)
    def sub(self, a, b): return self.m("SUBTRACT", a, b)
    def mul(self, a, b): return self.m("MULTIPLY", a, b)
    def gt(self, a, b): return self.m("GREATER_THAN", a, b)
    def lt(self, a, b): return self.m("LESS_THAN", a, b)
    def mx(self, a, b): return self.m("MAXIMUM", a, b)
    def mn(self, a, b): return self.m("MINIMUM", a, b)
    def absf(self, a): return self.m("ABSOLUTE", a)
    def inside(self, x, a, b): return self.mul(self.gt(x, a), self.lt(x, b))

    def mr(self, x, a, b, c=0.0, d=1.0, smooth=False):
        return self.node("ShaderNodeMapRange", {"Value": x, "From Min": a, "From Max": b, "To Min": c, "To Max": d},
                         {"data_type": "FLOAT", "interpolation_type": "SMOOTHSTEP" if smooth else "LINEAR", "clamp": True}, "Result")

    # vectors
    def vmath(self, op, a, b=None, scale=None):
        nd = self.n("ShaderNodeVectorMath", operation=op); self.put(nd.inputs[0], a)
        if b is not None: self.put(nd.inputs[1], b)
        if scale is not None: self.put(self.inp(nd, "Scale"), scale)
        return self.out(nd, 0)                 # only enabled outputs are listed: index 0 is the result
    def vmul(self, v, s): return self.vmath("MULTIPLY", v, s)
    def vadd(self, v, s): return self.vmath("ADD", v, s)
    def sep(self, v):
        nd = self.n("ShaderNodeSeparateXYZ"); self.put(nd.inputs[0], v); return nd.outputs[0], nd.outputs[1], nd.outputs[2]
    def comb(self, x=0.0, y=0.0, z=0.0):
        nd = self.n("ShaderNodeCombineXYZ"); self.put(nd.inputs[0], x); self.put(nd.inputs[1], y); self.put(nd.inputs[2], z); return nd.outputs[0]
    def rgb3(self, r, g, b):
        nd = self.n("ShaderNodeCombineColor"); self.put(nd.inputs[0], r); self.put(nd.inputs[1], g); self.put(nd.inputs[2], b); return nd.outputs[0]

    # colours
    def col(self, rgb):
        nd = self.n("ShaderNodeRGB"); nd.outputs[0].default_value = (*rgb, 1.0); return nd.outputs[0]
    def as_col(self, c):
        return c if isinstance(c, bpy.types.NodeSocket) else self.col(c)
    def mixc(self, f, a, b):
        return self.node("ShaderNodeMix", {"Factor_Float": f, "A_Color": a, "B_Color": b}, {"data_type": "RGBA", "clamp_factor": True}, "Result_Color")
    def mixf(self, f, a, b):
        return self.node("ShaderNodeMix", {"Factor_Float": f, "A_Float": a, "B_Float": b}, {"data_type": "FLOAT", "clamp_factor": True}, "Result_Float")
    def tone(self, c, f): return self.vmath("SCALE", c, scale=f)
    def ramp(self, f, stops, interp="LINEAR"):
        nd = self.n("ShaderNodeValToRGB"); cr = nd.color_ramp; cr.interpolation = interp
        e0, e1 = cr.elements[0], cr.elements[1]
        e0.position, e0.color = stops[0][0], (*stops[0][1], 1.0)
        e1.position, e1.color = stops[-1][0], (*stops[-1][1], 1.0)
        for p, c in stops[1:-1]: cr.elements.new(p).color = (*c, 1.0)
        self.put(nd.inputs["Fac"], f); return nd.outputs["Color"]

    # textures
    def noise(self, v, scale, detail=2.0, rough=0.5, dist=0.0):
        return self.node("ShaderNodeTexNoise", {"Vector": v, "Scale": scale, "Detail": detail, "Roughness": rough, "Distortion": dist}, {"noise_dimensions": "3D"}, "Fac")
    def vor(self, v, scale, feature="F1", rand=1.0):
        return self.node("ShaderNodeTexVoronoi", {"Vector": v, "Scale": scale, "Randomness": rand}, {"voronoi_dimensions": "3D", "feature": feature}, None)
    def white(self, v):
        return self.node("ShaderNodeTexWhiteNoise", {"Vector": v}, {"noise_dimensions": "3D"}, "Value")
    def wave(self, v, scale, direction="X", dist=0.0, detail=2.0, dscale=1.0, profile="SIN"):
        return self.node("ShaderNodeTexWave", {"Vector": v, "Scale": scale, "Distortion": dist, "Detail": detail, "Detail Scale": dscale},
                         {"wave_type": "BANDS", "bands_direction": direction, "wave_profile": profile}, "Fac")
    def rnd(self, vnode):
        """Per-cell random value of a Voronoi node (red channel of its Color output)."""
        return self.sep(self.out(vnode, "Color"))[0]


# ============================================================================== cell shaders
# each returns (albedo colour, roughness, metallic, height in metres); P = object coords in metres inside the cell
def _powder(hexc, rough=0.42, dirt=0.10, chips=None, streaks=False, metal=0.0):
    def sh(g, W, H):
        P = g.P; base = _lin(hexc)
        t = g.noise(P, 2.5, 3.0, 0.5)
        c = g.mixc(g.mr(t, 0.3, 0.7), _k(base, 0.93), _k(base, 1.06))
        d = g.mr(g.noise(P, 6.0, 4.0, 0.62), 0.56, 0.8)
        if streaks:                                          # vertical grime streaks (cell v = up on side faces)
            s = g.mr(g.noise(g.vmul(P, (1.0, 0.07, 1.0)), 9.0, 3.0, 0.6), 0.5, 0.75)
            d = g.mx(d, s)
        c = g.mixc(g.mul(d, dirt), c, _lin("#56534b"))
        rough_s = g.add(rough, g.mul(d, 0.14)); h = g.mul(g.noise(P, 140.0, 2.0, 0.5), 0.00018)          # orange peel
        if chips:
            ch = g.mr(g.noise(P, 16.0, 3.0, 0.65), 0.705, 0.73)
            c = g.mixc(ch, c, _lin(chips)); rough_s = g.add(rough_s, g.mul(ch, 0.35)); h = g.sub(h, g.mul(ch, 0.0005))
        return c, rough_s, metal, h
    return sh


def _sh_wood(g, W, H):
    P = g.P
    grain = g.wave(g.vmul(P, (0.1, 1.0, 1.0)), 26.0, "Y", dist=3.0, detail=3.0, dscale=0.6)      # ~12 mm grain lines
    plank = g.noise(g.vmul(P, (0.12, 1.0, 1.0)), 2.2, 2.0, 0.5)
    pores = g.mr(g.noise(g.vmul(P, (0.04, 1.0, 1.0)), 120.0, 1.0, 0.5), 0.64, 0.72)
    c = g.ramp(plank, [(0.25, _lin("#6c4327")), (0.55, _lin("#8d5c37")), (0.8, _lin("#a77246"))])
    c = g.mixc(g.mul(g.mr(grain, 0.5, 1.0), 0.6), c, _lin("#4a2c18"))
    c = g.mixc(g.mul(pores, 0.55), c, _lin("#3a2213"))
    return c, g.add(0.56, g.mul(grain, 0.14)), 0.0, g.sub(g.mul(grain, 0.0006), g.mul(pores, 0.0004))


def _sh_plastic(g, W, H):
    P = g.P
    streak = g.noise(g.vmul(P, (1.0, 0.06, 1.0)), 9.0, 3.0, 0.55)
    q = g.vmath("FLOOR", g.vmul(P, (320.0, 320.0, 320.0)))
    fleck = g.mul(g.mr(g.white(q), 0.978, 0.985), 0.7)
    fc = g.mixc(g.mr(g.white(g.vadd(q, (17.0, 5.0, 3.0))), 0.4, 0.6), _lin("#6e665c"), _lin("#4d5860"))
    c = g.mixc(g.mr(streak, 0.25, 0.75), _lin("#3a2f27"), _lin("#55473b"))
    c = g.mixc(fleck, c, fc)
    return c, g.add(0.66, g.mul(streak, 0.1)), 0.0, g.add(g.mul(streak, 0.0004), g.mul(fleck, 0.0002))


def _sh_concrete(g, W, H):
    P = g.P
    agg = g.rnd(g.vor(P, 140.0))
    blot = g.noise(P, 1.6, 3.0, 0.55)
    pore = g.mr(g.noise(P, 180.0, 0.0, 0.5), 0.70, 0.76)
    c = g.mixc(g.mr(blot, 0.3, 0.75), _lin("#9a968d"), _lin("#b2aea5"))
    c = g.tone(c, g.add(0.9, g.mul(agg, 0.2)))
    c = g.mixc(g.mul(pore, 0.8), c, _lin("#5b5852"))
    return c, g.add(0.84, g.mul(agg, 0.08)), 0.0, g.sub(g.mul(agg, 0.0006), g.mul(pore, 0.0016))


def _sh_galv(g, W, H):
    P = g.P
    r = g.rnd(g.vor(P, 28.0))
    dull = g.mr(g.noise(P, 3.5, 3.0, 0.6), 0.55, 0.8)
    c = g.ramp(r, [(0.0, _lin("#8e9498")), (0.5, _lin("#a6acb0")), (1.0, _lin("#c2c7ca"))])
    c = g.mixc(g.mul(dull, 0.5), c, _lin("#8a8e91"))
    wr = g.mr(g.noise(P, 11.0, 4.0, 0.7), 0.74, 0.8)
    c = g.mixc(g.mul(wr, 0.5), c, _lin("#d0d2d0"))
    return c, g.add(0.30, g.add(g.mul(r, 0.18), g.mul(wr, 0.3))), 0.9, g.add(g.mul(r, 0.00025), g.mul(wr, 0.0003))


def _brushed(lo, hi, rough):
    def sh(g, W, H):
        s = g.noise(g.vmul(g.P, (0.015, 1.0, 1.0)), 380.0, 2.0, 0.5)
        c = g.mixc(g.mr(s, 0.3, 0.7), _lin(lo), _lin(hi))
        return c, g.add(rough, g.mul(s, 0.1)), 1.0, g.mul(g.noise(g.vmul(g.P, (0.03, 1.0, 1.0)), 90.0, 2.0, 0.5), 0.00012)
    return sh


def _iron_base(g):
    P = g.P
    rust = g.mr(g.noise(P, 5.0, 5.0, 0.65), 0.52, 0.66)
    cast = g.noise(P, 120.0, 2.0, 0.6)
    c = g.mixc(g.mr(cast, 0.3, 0.7), _lin("#32302e"), _lin("#4a4744"))
    return c, rust, cast


def _sh_iron(g, W, H):
    c, rust, cast = _iron_base(g)
    c = g.mixc(g.mul(rust, 0.65), c, _lin("#5a3a26"))
    return c, g.add(0.62, g.mul(rust, 0.25)), g.sub(0.6, g.mul(rust, 0.45)), g.add(g.mul(cast, 0.0008), g.mul(rust, 0.0004))


def _sh_iron_tread(g, W, H):
    c, rust, cast = _iron_base(g)
    x, y, _ = g.sep(g.P); p = 0.032
    lx = g.sub(g.m("FRACT", g.m("DIVIDE", x, p)), 0.5); ly = g.sub(g.m("FRACT", g.m("DIVIDE", y, p)), 0.5)
    stud = g.mr(g.add(g.absf(lx), g.absf(ly)), 0.31, 0.25, smooth=True)
    c = g.mixc(stud, g.tone(c, 0.75), _lin("#6c6965"))
    c = g.mixc(g.mul(rust, g.sub(1.0, stud)), c, _lin("#4d3424"))
    return c, g.mixf(stud, 0.84, 0.42), g.mixf(stud, 0.3, 0.85), g.add(g.mul(stud, 0.0022), g.mul(cast, 0.0002))


def _sh_granite(g, W, H):
    P = g.P
    r = g.rnd(g.vor(P, 380.0))
    c = g.ramp(r, [(0.0, _lin("#262626")), (0.18, _lin("#5f5d5a")), (0.5, _lin("#8f8c88")), (0.82, _lin("#c4c1bc"))], "CONSTANT")
    c = g.tone(c, g.add(0.95, g.mul(g.noise(P, 2.0, 2.0, 0.5), 0.1)))
    return c, g.add(0.6, g.mul(r, 0.1)), 0.0, g.mul(r, 0.0004)


def _sh_soil(g, W, H):
    P = g.P; Ps = g.vmul(P, (1.0, 1.7, 1.0))
    r = g.rnd(g.vor(Ps, 26.0))
    edge = g.out(g.vor(Ps, 26.0, "DISTANCE_TO_EDGE"), "Distance")
    chip = g.mr(edge, 0.03, 0.07)
    fib = g.noise(g.vmul(P, (6.0, 0.5, 1.0)), 60.0, 2.0, 0.5)
    cc = g.tone(g.ramp(r, [(0.0, _lin("#4a2f1f")), (0.5, _lin("#6b4630")), (1.0, _lin("#86603f"))]), g.add(0.85, g.mul(fib, 0.3)))
    sc = g.mixc(g.noise(P, 40.0, 2.0, 0.5), _lin("#1e1611"), _lin("#2e2219"))
    return g.mixc(chip, sc, cc), g.add(0.88, g.mul(chip, 0.08)), 0.0, g.mul(chip, g.add(0.003, g.mul(r, 0.004)))


def _sh_foliage(g, W, H):
    P = g.P
    vn = g.vor(P, 48.0); r = g.rnd(vn); d1 = g.out(vn, "Distance")
    leaf = g.mr(g.out(g.vor(P, 48.0, "DISTANCE_TO_EDGE"), "Distance"), 0.02, 0.06)
    lc = g.tone(g.ramp(r, [(0.0, _lin("#233f19")), (0.5, _lin("#3a6a27")), (1.0, _lin("#5c8c34"))]), g.sub(1.15, g.mul(d1, 0.5)))
    return g.mixc(leaf, _lin("#10200c"), lc), 0.68, 0.0, g.mul(leaf, g.sub(0.004, g.mul(d1, 0.003)))


def _sh_flat(hexc, rough, var=0.03, dirt=None):
    def sh(g, W, H):
        P = g.P; base = _lin(hexc)
        c = g.mixc(g.noise(P, 30.0, 2.0, 0.5), _k(base, 1.0 - var), _k(base, 1.0 + var))
        if dirt: c = g.mixc(g.mul(g.mr(g.noise(P, 5.0, 4.0, 0.6), 0.55, 0.85), 0.25), c, _lin(dirt))
        return c, rough, 0.0, g.mul(g.noise(P, 120.0, 2.0, 0.5), 0.00012)
    return sh


# ---- decal cells: UV (0..1) inside the panel; overlays (text, shapes) are added by _OVERLAYS
def _sh_map(g, W, H):
    u, v, _ = g.sep(g.UV); x, y, _ = g.sep(g.P)
    navy = _lin("#1e2c4c")
    inmap = g.mul(g.inside(u, 0.05, 0.95), g.inside(v, 0.27, 0.845))
    b1 = g.node("ShaderNodeTexBrick", {"Vector": g.P, "Color1": _lin("#e9e0cd"), "Color2": _lin("#d5ccba"), "Mortar": _lin("#ffffff"), "Scale": 1.0,
                                       "Mortar Size": 0.012, "Brick Width": 0.16, "Row Height": 0.09, "Bias": 0.0}, {"offset": 0.5, "offset_frequency": 2}, "Color")
    rot = g.node("ShaderNodeVectorRotate", {"Vector": g.P, "Center": (0.5, 1.1, 0.0), "Angle": 0.5}, {"rotation_type": "Z_AXIS"}, 0)
    b2 = g.node("ShaderNodeTexBrick", {"Vector": rot, "Color1": _lin("#e4dccb"), "Color2": _lin("#cfc8b8"), "Mortar": _lin("#ffffff"), "Scale": 1.0,
                                       "Mortar Size": 0.011, "Brick Width": 0.12, "Row Height": 0.11, "Bias": 0.0}, {"offset": 0.35, "offset_frequency": 3}, "Color")
    c = g.mixc(g.mr(g.noise(g.P, 1.1, 1.0, 0.5), 0.55, 0.56), b1, b2)
    c = g.mixc(g.mr(g.noise(g.vadd(g.P, (3.0, 1.0, 0.0)), 2.3, 2.0, 0.5), 0.62, 0.63), c, _lin("#b3d59a"))          # parks
    yr = g.add(0.92, g.mul(g.m("SINE", g.mul(x, 5.0)), 0.07))
    c = g.mixc(g.mr(g.absf(g.sub(y, yr)), 0.046, 0.04), c, _lin("#8cc0e2"))                                         # river
    road = g.mx(g.lt(g.absf(g.sub(x, 0.42)), 0.011), g.lt(g.absf(g.sub(y, 1.36)), 0.011))
    c = g.mixc(road, c, _lin("#f2d48a"))
    c = g.mixc(inmap, navy, c)
    div = g.mul(g.inside(v, 0.851, 0.855), g.inside(u, 0.05, 0.95))
    c = g.mixc(div, c, _lin("#f2c230"))
    return c, 0.35, 0.0, 0.0


def _sh_poster(g, W, H):
    u, v, _ = g.sep(g.UV)
    sky = g.ramp(v, [(0.33, _lin("#0f3d52")), (0.55, _lin("#2a6f80")), (0.78, _lin("#f09a4a")), (1.0, _lin("#f7cf7a"))])
    sea = g.ramp(v, [(0.0, _lin("#0a2638")), (0.34, _lin("#145068"))])
    ph = g.add(g.mul(v, 95.0), g.mul(g.m("SINE", g.mul(u, 14.0)), 2.5))
    lines = g.mr(g.absf(g.m("SINE", ph)), 0.96, 1.0)
    sea = g.mixc(g.mul(lines, 0.6), sea, _lin("#2f7f98"))
    c = g.mixc(g.lt(v, 0.34), sky, sea)
    c = g.mixc(g.lt(v, 0.075), c, _lin("#f4f1ea"))
    return c, 0.28, 0.0, 0.0


def _sh_timetable(g, W, H):
    u, v, _ = g.sep(g.UV); x, y, _ = g.sep(g.P)
    c = g.col(_lin("#fbfbf8"))
    stripe = g.mul(g.lt(g.m("FRACT", g.m("DIVIDE", g.sub(y, 0.1175), 0.15)), 0.5), g.inside(y, 0.1175, 1.1675))
    c = g.mixc(stripe, c, _lin("#eaf0f8"))
    sepl = g.mul(g.mx(g.lt(g.absf(g.sub(u, 0.355)), 0.002), g.lt(g.absf(g.sub(u, 0.67)), 0.002)), g.inside(y, 0.1175, 1.20))
    c = g.mixc(sepl, c, _lin("#b8c0cc"))
    c = g.mixc(g.inside(v, 0.80, 0.855), c, _lin("#e1e5ec"))
    c = g.mixc(g.mx(g.gt(v, 0.855), g.lt(v, 0.055)), c, _lin("#1e2c4c"))
    return c, 0.3, 0.0, 0.0


def _sh_flag(g, W, H):
    u, v, _ = g.sep(g.UV)
    c = g.mixc(g.gt(v, 0.36), _lin("#f6f6f2"), _lin("#00664f"))
    border = g.mx(g.mx(g.lt(u, 0.025), g.gt(u, 0.975)), g.mx(g.lt(v, 0.0167), g.gt(v, 0.9833)))
    return g.mixc(border, c, _lin("#1c1c1c")), 0.3, 0.0, 0.0


def _sh_display(g, W, H):
    x, y, _ = g.sep(g.P)
    dot = g.mul(g.lt(g.absf(g.sub(g.m("FRACT", g.m("DIVIDE", x, 0.0125)), 0.5)), 0.3), g.lt(g.absf(g.sub(g.m("FRACT", g.m("DIVIDE", y, 0.0125)), 0.5)), 0.3))
    return g.mixc(dot, _lin("#050505"), _lin("#151515")), 0.2, 0.0, 0.0


def _sh_label(hexc, border=None):
    def sh(g, W, H):
        u, v, _ = g.sep(g.UV)
        c = g.col(_lin(hexc))
        if border:
            b = g.mx(g.mx(g.lt(u, 0.05), g.gt(u, 0.95)), g.mx(g.lt(v, 0.05), g.gt(v, 0.95)))
            c = g.mixc(b, c, _lin(border))
        return c, 0.35, 0.0, 0.0
    return sh


def _sh_grate(g, W, H):
    u, v, _ = g.sep(g.UV)
    cx, cy = g.sub(u, 0.5), g.sub(v, 0.5)
    r = g.vmath("LENGTH", g.comb(cx, cy, 0.0))
    a = g.m("ARCTAN2", cy, cx)
    sq = g.mx(g.absf(cx), g.absf(cy))
    ring_slot = g.mul(g.gt(g.m("FRACT", g.m("DIVIDE", g.sub(r, 0.215), 0.045)), 0.42), g.inside(r, 0.215, 0.44))
    rib = g.lt(g.m("FRACT", g.mul(g.add(a, math.pi), 24.0 / TAU)), 0.16)
    ring_slot = g.mul(ring_slot, g.sub(1.0, rib))
    hx = g.inside(g.m("FRACT", g.m("DIVIDE", cx, 0.04)), 0.22, 0.78)
    hy = g.inside(g.m("FRACT", g.m("DIVIDE", cy, 0.04)), 0.22, 0.78)
    corner_slot = g.mul(g.mul(hx, hy), g.mul(g.gt(r, 0.465), g.lt(sq, 0.455)))
    split = g.mul(g.lt(g.absf(cy), 0.0035), g.gt(r, 0.2))
    slot = g.mx(g.mx(ring_slot, corner_slot), split)
    ci, rust, cast = _iron_base(g)
    ci = g.mixc(g.mul(rust, 0.5), ci, _lin("#5a3a26"))
    c = g.mixc(slot, ci, _lin("#0a0a0a"))
    solid = g.sub(1.0, slot)
    return c, g.mixf(slot, 0.62, 1.0), g.mul(solid, 0.55), g.mul(solid, 0.005)


SHADERS = {
    "wood": _sh_wood, "plastic": _sh_plastic, "concrete": _sh_concrete, "galv": _sh_galv,
    "stainless": _brushed("#aeb1b3", "#cdd0d2", 0.24), "alu": _brushed("#a5aaae", "#bdc1c5", 0.32),
    "iron": _sh_iron, "iron_tread": _sh_iron_tread, "granite": _sh_granite, "soil": _sh_soil, "foliage": _sh_foliage,
    "steel_dark": _powder("#383e42", 0.44), "black": _powder("#1d1e20", 0.40), "green": _powder("#2f7a3f", 0.40),
    "blue": _powder("#1d4f9c", 0.40), "yellow": _powder("#e3ac12", 0.40), "red": _powder("#a8231c", 0.36, chips="#4a4846"),
    "grey_light": _powder("#c3c5c1", 0.48, dirt=0.18, streaks=True),
    "rubber": _sh_flat("#1b1b1b", 0.88), "white": _sh_flat("#e4e4de", 0.40, dirt="#b8b7ad"), "void": _sh_flat("#090909", 1.0, 0.02),
    "map": _sh_map, "poster": _sh_poster, "timetable": _sh_timetable, "flag": _sh_flag, "display": _sh_display, "grate_tree": _sh_grate,
    "label_recycle": _sh_label("#2f7a3f", "#f4f4f0"), "label_hazard": _sh_label("#f2c400", "#111111"),
    "label_info": _sh_label("#1d4f9c", "#f4f4f0"), "label_litter": _sh_label("#1d1e20", "#e9e9e4"),
}


# ============================================================================== decal overlays (text and flat shapes over the cell quads)
class _Ov:
    """Adds emission-only text / polygons above one decal quad (cell-local world units, 1 unit = 256 px)."""
    def __init__(self, col, x0, y0, made, ovmats):
        self.col, self.x0, self.y0, self.made, self.ovmats = col, x0, y0, made, ovmats; self.z = 0.01; self.cache = {}

    def mat(self, hexc, rough=0.4):
        key = (hexc, rough)
        if key not in self.cache:
            m = bpy.data.materials.new("MRSBakeInk"); nt = _nt(m); nt.nodes.clear()
            em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], out.inputs[0])
            self.made.append(m); self.ovmats.append((em, _lin(hexc), rough)); self.cache[key] = m
        return self.cache[key]

    def _obj(self, name, data, hexc, rough):
        data.materials.append(self.mat(hexc, rough))
        ob = bpy.data.objects.new(name, data); ob.location = (self.x0, self.y0, self.z); self.z += 0.002
        self.col.objects.link(ob); self.made += [ob, data]
        return ob

    def poly(self, pts, hexc, rough=0.4):
        me = bpy.data.meshes.new("MRSBakePoly"); me.from_pydata([(x, y, 0.0) for x, y in pts], [], [list(range(len(pts)))])
        return self._obj("MRSBakePoly", me, hexc, rough)

    def circle(self, cx, cy, r, hexc, n=48, a0=0.0, a1=TAU):
        full = abs(a1 - a0 - TAU) < 1e-6
        pts = [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n if full else n + 1)]
        return self.poly(pts if full else pts + [(cx, cy)], hexc)

    def ring(self, cx, cy, r0, r1, hexc, a0=0.0, a1=TAU, n=48):
        me = bpy.data.meshes.new("MRSBakeRing"); vs = []; fs = []
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            vs += [(cx + r0 * math.cos(a), cy + r0 * math.sin(a), 0.0), (cx + r1 * math.cos(a), cy + r1 * math.sin(a), 0.0)]
        for k in range(n): fs.append((2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1))
        me.from_pydata(vs, [], fs)
        return self._obj("MRSBakeRing", me, hexc, 0.4)

    def rrect(self, x0, y0, x1, y1, r, hexc):
        pts = []
        for cx, cy, a in ((x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, math.pi / 2), (x0 + r, y0 + r, math.pi)):
            pts += [(cx + r * math.cos(a + math.pi / 2 * k / 6), cy + r * math.sin(a + math.pi / 2 * k / 6)) for k in range(7)]
        return self.poly(pts, hexc)

    def rect(self, x0, y0, x1, y1, hexc):
        return self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], hexc)

    def text(self, body, x, y, size, hexc, align="LEFT", bold=0.0):
        cu = bpy.data.curves.new("MRSBakeText", "FONT"); cu.body = body; cu.size = size
        cu.align_x = align; cu.align_y = "CENTER"; cu.offset = bold; cu.fill_mode = "BOTH"; cu.resolution_u = 6
        ob = self._obj("MRSBakeText", cu, hexc, 0.4); ob.location.x += x; ob.location.y += y
        return ob

    def at(self, ob, x, y):
        ob.location.x += x; ob.location.y += y; return ob


def _ov_map(o, W, H):
    navy, white, ink = "#1e2c4c", "#ffffff", "#2a2a2a"
    o.circle(0.14, 1.86, 0.085, "#f2c230"); o.text("i", 0.14, 1.862, 0.15, navy, "CENTER", 0.004)
    o.text("Harbour Quarter", 0.27, 1.885, 0.088, white, bold=0.004); o.text("Port Halden  -  walking map", 0.27, 1.80, 0.046, "#c9d3e6")
    o.ring(0.47, 1.05, 0.325, 0.333, "#4f6593", n=96)                       # 5 minute walk
    o.circle(0.47, 1.05, 0.042, white); o.circle(0.47, 1.05, 0.03, "#d7263d")
    o.text("You are here", 0.53, 1.03, 0.036, navy, bold=0.002)
    o.poly([(0.86, 1.56), (0.90, 1.56), (0.88, 1.62)], navy); o.text("N", 0.88, 1.645, 0.035, navy, "CENTER", 0.002)
    for t, x, y in (("Ferry Terminal", 0.62, 0.70), ("Market Sq", 0.17, 1.30), ("Old Town", 0.15, 0.80), ("Harbour", 0.60, 1.45), ("Station", 0.25, 1.58)):
        o.text(t, x, y, 0.032, ink, bold=0.0015)
    for i, (t, mins) in enumerate((("Ferry Terminal", "6 min"), ("Market Square", "4 min"), ("Old Town Hall", "5 min"), ("Central Station", "9 min"))):
        y = 0.45 - i * 0.085
        o.text("> " + t, 0.07, y, 0.052, white); o.text(mins, 0.93, y, 0.052, "#f2c230", "RIGHT")
    o.text("porthalden.example/walk", 0.07, 0.09, 0.032, "#9fb0cf")


def _ov_poster(o, W, H):
    o.circle(0.70, 0.51, 0.17, "#fde3a1", 40, 0.0, math.pi)                                 # setting sun
    for i, w in enumerate((0.15, 0.11, 0.08, 0.05)): o.rect(0.70 - w, 0.46 - i * 0.06, 0.70 + w, 0.475 - i * 0.06, "#f3c47a")
    o.poly([(0.14, 0.53), (0.46, 0.53), (0.41, 0.47), (0.19, 0.47)], "#10202c")                   # boat
    o.poly([(0.31, 0.545), (0.31, 0.86), (0.45, 0.555)], "#f7f4ec"); o.poly([(0.29, 0.555), (0.29, 0.78), (0.18, 0.565)], "#e9e4d8")
    o.text("HARBOUR", 0.5, 1.31, 0.165, "#ffffff", "CENTER", 0.008); o.text("FESTIVAL", 0.5, 1.15, 0.165, "#ffffff", "CENTER", 0.008)
    o.text("12 - 14 JULY   PORT HALDEN", 0.5, 1.02, 0.05, "#13324a", "CENTER", 0.003)
    o.text("Live music  -  Street food  -  Tall ships", 0.5, 0.072, 0.036, "#1d2b3a", "CENTER", 0.0015)
    o.text("porthalden.example", 0.5, 0.028, 0.028, "#4c5b6b", "CENTER")


def _ov_timetable(o, W, H):
    o.text("BUS TIMES", 0.07, 1.41, 0.095, "#ffffff", bold=0.005); o.text("Harbour Road  (stop H2)", 0.07, 1.315, 0.05, "#d6deeb")
    o.rrect(0.78, 1.32, 0.94, 1.45, 0.025, "#d9480f"); o.text("12", 0.86, 1.385, 0.085, "#ffffff", "CENTER", 0.004)
    for t, x in (("Mon - Fri", 0.06), ("Saturday", 0.39), ("Sunday", 0.70)): o.text(t, x, 1.24, 0.042, "#1e2c4c", bold=0.003)
    def times(start, step, n):
        return ["%02d:%02d" % divmod(start + i * step, 60) for i in range(n)]
    cols = (times(6 * 60 + 5, 15, 28), times(6 * 60 + 40, 20, 28), times(7 * 60 + 10, 30, 28))
    for c, x in zip(cols, (0.06, 0.39, 0.70)):
        for r in range(14): o.text("%s   %s" % (c[2 * r], c[2 * r + 1]), x, 1.13 - r * 0.075, 0.038, "#1b1b1b")
    o.text("Real time: porthalden.example/bus", 0.07, 0.04, 0.032, "#ffffff")


def _ov_flag(o, W, H):
    green = "#00664f"
    o.rrect(0.25, 0.85, 0.75, 1.35, 0.07, "#ffffff")
    o.rrect(0.31, 0.95, 0.69, 1.25, 0.04, green)                                           # bus body
    o.rect(0.34, 1.13, 0.66, 1.22, "#ffffff")                                               # windscreen / windows
    for x in (0.42, 0.50, 0.58): o.rect(x - 0.004, 1.13, x + 0.004, 1.22, green)
    o.rect(0.35, 1.03, 0.43, 1.08, "#f2c230"); o.rect(0.57, 1.03, 0.65, 1.08, "#f2c230")    # lights
    for x in (0.38, 0.62): o.circle(x, 0.95, 0.04, "#003d2f"); o.circle(x, 0.95, 0.018, "#9aa5a0")
    o.text("BUS STOP", 0.5, 0.66, 0.13, "#ffffff", "CENTER", 0.006)
    for x, t, c in ((0.20, "12", "#222222"), (0.50, "47", "#222222"), (0.80, "N8", "#1d4f9c")):
        o.rrect(x - 0.12, 0.25, x + 0.12, 0.42, 0.025, c); o.text(t, x, 0.335, 0.105, "#ffffff", "CENTER", 0.004)
    o.text("Harbour Road   H2", 0.5, 0.12, 0.05, "#222222", "CENTER", 0.002)


def _ov_display(o, W, H):
    amber = "#ffae00"
    for i, (a, b) in enumerate((("12  Harbour", "2 min"), ("47  Old Town", "9 min"), ("N8  Airport", "23:41"))):
        y = 0.385 - i * 0.135
        o.text(a, 0.05, y, 0.088, amber, bold=0.002); o.text(b, 0.95, y, 0.088, amber, "RIGHT", 0.002)


def _ov_recycle(o, W, H):
    cx, cy, r, t = 0.25, 0.29, 0.105, 0.032
    for k in range(3):
        a0 = math.radians(100 + 120 * k); a1 = a0 + math.radians(88)
        o.ring(cx, cy, r - t / 2, r + t / 2, "#ffffff", a0, a1, 16)
        ex, ey = cx + r * math.cos(a1), cy + r * math.sin(a1); tx, ty = -math.sin(a1), math.cos(a1); nx, ny = math.cos(a1), math.sin(a1)
        s = 0.045
        o.poly([(ex + nx * s * 0.75, ey + ny * s * 0.75), (ex + tx * s, ey + ty * s), (ex - nx * s * 0.75, ey - ny * s * 0.75)], "#ffffff")
    o.text("RECYCLE", 0.25, 0.085, 0.06, "#ffffff", "CENTER", 0.003)


def _ov_hazard(o, W, H):
    def tri(rad, cy):
        return [(0.25 + rad * math.cos(math.radians(a)), cy + rad * math.sin(math.radians(a))) for a in (90, 210, 330)]
    o.poly(tri(0.2, 0.25), "#111111"); o.poly(tri(0.145, 0.235), "#f2c400")
    o.poly([(0.268, 0.33), (0.215, 0.235), (0.252, 0.235), (0.228, 0.155), (0.288, 0.262), (0.252, 0.262)], "#111111")


def _ov_info(o, W, H):
    o.text("i", 0.25, 0.25, 0.34, "#ffffff", "CENTER", 0.008)


def _ov_litter(o, W, H):
    o.rect(0.18, 0.17, 0.32, 0.35, "#ffffff"); o.rect(0.16, 0.355, 0.34, 0.385, "#ffffff"); o.rect(0.225, 0.39, 0.275, 0.41, "#ffffff")
    for x in (0.215, 0.25, 0.285): o.rect(x - 0.006, 0.20, x + 0.006, 0.32, "#1d1e20")
    o.text("LITTER", 0.25, 0.085, 0.062, "#ffffff", "CENTER", 0.003)


_OVERLAYS = {"map": _ov_map, "poster": _ov_poster, "timetable": _ov_timetable, "flag": _ov_flag, "display": _ov_display,
             "label_recycle": _ov_recycle, "label_hazard": _ov_hazard, "label_info": _ov_info, "label_litter": _ov_litter}


# ============================================================================== baking
def _paths(tex_dir):
    return {k: os.path.join(tex_dir, "%s_%s.png" % (ATLAS, k)) for k in MAPS}


MAPS = ("albedo", "orm", "normal")


def _layout_json():
    return {"version": BAKE_VERSION, "size": [AW, AH], "px_per_m": PPM,
            "cells": {c[0]: {"px": list(c[1:5]), "uv": [round(x, 6) for x in cell_uv_rect(c[0])], "kind": c[5], "grain": c[6],
                             "metres": [c[3] / PPM, c[4] / PPM] if c[5] == "tile" else None} for c in CELLS}}


def atlas_current(tex_dir=None):
    tex_dir = tex_dir or TEX_DIR
    if not all(os.path.exists(p) for p in _paths(tex_dir).values()): return False
    try:
        with open(os.path.join(tex_dir, "atlas_layout.json"), encoding="utf-8") as f: lay = json.load(f)
    except (OSError, ValueError):
        return False
    return lay.get("version") == BAKE_VERSION and lay.get("cells") == _layout_json()["cells"]


def _read_exr(path):
    im = bpy.data.images.load(path)
    a = np.empty(im.size[0] * im.size[1] * im.channels, np.float32); im.pixels.foreach_get(a)
    a = a.reshape(im.size[1], im.size[0], im.channels); bpy.data.images.remove(im)
    return a


def _write_png(path, rgb, colorspace):
    im = bpy.data.images.new(os.path.basename(path), AW, AH, alpha=False)
    im.colorspace_settings.name = colorspace
    a = np.ones((AH, AW, 4), np.float32); a[..., :3] = np.clip(rgb, 0.0, 1.0)
    im.pixels.foreach_set(a.ravel()); im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)


def _srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def _normals(h):
    """Tangent-space normal map (OpenGL / glTF convention, +Y = +v) from a height field in metres, per cell."""
    n = np.zeros(h.shape + (3,), np.float32); n[..., 2] = 1.0
    for name, x, y, w, hh, kind, grain in CELLS:
        r0, r1 = AH - (y + hh), AH - y                         # numpy rows are bottom-up (Blender pixel order)
        sl = h[r0:r1, x:x + w].astype(np.float64)
        p = np.pad(sl, 1, mode="edge")                          # 3x3 box blur against single-pixel aliasing
        sl = sum(p[i:i + sl.shape[0], j:j + sl.shape[1]] for i in range(3) for j in range(3)) / 9.0
        gy, gx = np.gradient(sl, 1.0 / PPM)
        v = np.stack([-gx, -gy, np.ones_like(sl)], -1)
        n[r0:r1, x:x + w] = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def bake_atlas(tex_dir=None, samples=16, verbose=True):
    """Bake the furniture atlas: every cell is a quad (1 unit = 256 px) carrying its procedural shader-node
    material as pure emission; decal cells get text / shapes floating above them. An orthographic Cycles
    camera captures the 2048 x 1024 atlas three times (emission = albedo, = (1, roughness, metallic), =
    height) to float EXRs; numpy encodes albedo to sRGB, packs ORM and derives the normal map from the
    height. Writes MRS_FurnitureAtlas_{albedo,orm,normal}.png + atlas_layout.json into `tex_dir`."""
    import time
    t0 = time.time()
    tex_dir = os.path.abspath(tex_dir or TEX_DIR); os.makedirs(tex_dir, exist_ok=True)
    sc = bpy.data.scenes.new(MRS + "FurnitureBake")
    col = bpy.data.collections.new(MRS + "FurnitureBakeItems"); sc.collection.children.link(col)
    made, switches, ovmats = [col], [], []
    ext = 4.0 / PPM
    try:
        for name, x, y, w, h, kind, grain in CELLS:
            W, H = w / PPM, h / PPM
            X0, Y0 = x / PPM, (AH - y - h) / PPM
            ex0 = ext if x == 0 else 0.0; ex1 = ext if x + w == AW else 0.0; ey0 = ext if y + h == AH else 0.0; ey1 = ext if y == 0 else 0.0
            me = bpy.data.meshes.new("MRSBake_" + name)
            vs = [(-ex0, -ey0, 0.0), (W + ex1, -ey0, 0.0), (W + ex1, H + ey1, 0.0), (-ex0, H + ey1, 0.0)]
            me.from_pydata(vs, [], [(0, 1, 2, 3)])
            uv = me.uv_layers.new(name="UVMap")
            for i, (vx, vy, _) in enumerate(vs): uv.data[i].uv = (vx / W, vy / H)
            mat = bpy.data.materials.new("MRSBake_" + name); nt = _nt(mat); nt.nodes.clear()
            g = _G(nt)
            c, rough, metal, hgt = SHADERS[name](g, W, H)
            em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], out.inputs[0])
            hs = g.add(hgt, 0.02)                                  # keep emission positive; only the gradient matters
            switches.append((nt, em, {"albedo": g.as_col(c), "orm": g.rgb3(1.0, rough, metal), "height": g.rgb3(hs, hs, hs)}))
            me.materials.append(mat)
            ob = bpy.data.objects.new("MRSBake_" + name, me); ob.location = (X0, Y0, 0.0); col.objects.link(ob)
            made += [ob, me, mat]
            if name in _OVERLAYS: _OVERLAYS[name](_Ov(col, X0, Y0, made, ovmats), W, H)
        cd = bpy.data.cameras.new("MRSBakeCam"); cd.type = "ORTHO"; cd.ortho_scale = AW / PPM; cd.clip_start = 0.1; cd.clip_end = 50.0
        cam = bpy.data.objects.new("MRSBakeCam", cd); cam.location = (AW / PPM / 2, AH / PPM / 2, 5.0); col.objects.link(cam); made += [cam, cd]
        sc.camera = cam
        r = sc.render; r.engine = "CYCLES"; r.resolution_x, r.resolution_y, r.resolution_percentage = AW, AH, 100
        r.film_transparent = False; r.use_compositing = False; r.use_sequencer = False
        cy = sc.cycles; cy.device = "CPU"; cy.samples = samples; cy.use_denoising = False; cy.use_adaptive_sampling = False
        cy.max_bounces = 0; cy.pixel_filter_type = "BOX"; cy.filter_width = 1.0; cy.seed = 0
        r.image_settings.file_format = "OPEN_EXR"; r.image_settings.color_depth = "32"
        exr = {}
        for key in ("albedo", "orm", "height"):
            for nt, em, socks in switches: nt.links.new(socks[key], em.inputs["Color"])
            for em, alb, rough in ovmats:
                em.inputs["Color"].default_value = (*alb, 1.0) if key == "albedo" else ((1.0, rough, 0.0, 1.0) if key == "orm" else (0.02, 0.02, 0.02, 1.0))
            exr[key] = r.filepath = os.path.join(tex_dir, "_bake_%s.exr" % key)
            bpy.ops.render.render(write_still=True, scene=sc.name)
            if verbose: print("[furniture] baked %s pass  %.1f s" % (key, time.time() - t0), flush=True)
        P = _paths(tex_dir)
        _write_png(P["albedo"], _srgb(_read_exr(exr["albedo"])[..., :3]), "sRGB")
        _write_png(P["orm"], _read_exr(exr["orm"])[..., :3], "Non-Color")
        _write_png(P["normal"], _normals(_read_exr(exr["height"])[..., 0]), "Non-Color")
        for p in exr.values():
            try: os.remove(p)
            except OSError: pass
        with open(os.path.join(tex_dir, "atlas_layout.json"), "w", encoding="utf-8") as f: json.dump(_layout_json(), f, indent=1)
    finally:
        for idb in reversed(made):
            try:
                if isinstance(idb, bpy.types.Object): bpy.data.objects.remove(idb)
                elif isinstance(idb, bpy.types.Mesh): bpy.data.meshes.remove(idb)
                elif isinstance(idb, bpy.types.Curve): bpy.data.curves.remove(idb)
                elif isinstance(idb, bpy.types.Material): bpy.data.materials.remove(idb)
                elif isinstance(idb, bpy.types.Camera): bpy.data.cameras.remove(idb)
                elif isinstance(idb, bpy.types.Collection): bpy.data.collections.remove(idb)
            except ReferenceError:
                pass
        bpy.data.scenes.remove(sc)
    if verbose: print("[furniture] atlas baked to %s in %.1f s" % (tex_dir, time.time() - t0), flush=True)
    return _paths(tex_dir)


# ============================================================================== engine materials
def _image(path, colorspace):
    im = bpy.data.images.load(path, check_existing=True); im.reload()
    im.colorspace_settings.name = colorspace
    return im


def atlas_materials(tex_dir=None):
    """MRS_FurnitureAtlas (Principled BSDF + albedo / ORM (G roughness, B metallic) / normal image textures:
    the glTF exporter writes baseColor, metallicRoughness and normal textures) and MRS_FurnitureGlass."""
    tex_dir = tex_dir or TEX_DIR; P = _paths(tex_dir)
    m = bpy.data.materials.get(ATLAS) or bpy.data.materials.new(ATLAS)
    nt = _nt(m); nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (500, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (150, 0); nt.links.new(b.outputs[0], out.inputs["Surface"])
    ta = nt.nodes.new("ShaderNodeTexImage"); ta.location = (-450, 250); ta.image = _image(P["albedo"], "sRGB"); ta.label = "albedo"
    to = nt.nodes.new("ShaderNodeTexImage"); to.location = (-450, -50); to.image = _image(P["orm"], "Non-Color"); to.label = "orm"
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.location = (-450, -350); tn.image = _image(P["normal"], "Non-Color"); tn.label = "normal"
    sp = nt.nodes.new("ShaderNodeSeparateColor"); sp.location = (-150, -50)
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-150, -350)
    nt.links.new(ta.outputs["Color"], b.inputs["Base Color"]); nt.links.new(to.outputs["Color"], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"]); nt.links.new(sp.outputs["Blue"], b.inputs["Metallic"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    m.use_backface_culling = True; m.diffuse_color = (0.35, 0.35, 0.35, 1.0); m.roughness = 0.5
    g = bpy.data.materials.get(GLASS) or bpy.data.materials.new(GLASS)
    nt = _nt(g); nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = (0.55, 0.66, 0.70, 1.0); b.inputs["Roughness"].default_value = 0.05
    b.inputs["IOR"].default_value = 1.5; b.inputs["Alpha"].default_value = 0.3
    try: g.surface_render_method = "BLENDED"
    except (AttributeError, TypeError): pass
    g.use_backface_culling = True; g.diffuse_color = (0.55, 0.66, 0.70, 0.3)
    return m, g


# ============================================================================== mesh building
class _M:
    """bmesh under construction: material_index carries the atlas cell id (CID) until finishing, a
    'nobevel' face flag excludes thin plates / tubes from the chamfer pass."""
    def __init__(self):
        self.bm = bmesh.new(); self.nb = self.bm.faces.layers.int.new("nobevel"); self.anchor = None

    def _since(self, n0):
        self.bm.faces.ensure_lookup_table(); return self.bm.faces[n0:]

    def _tag(self, n0, nobevel=False):
        if nobevel:
            for f in self._since(n0): f[self.nb] = 1

    def box(self, x0, y0, z0, x1, y1, z1, c, nobevel=False, **sides):
        n0 = len(self.bm.faces)
        _box(self.bm, min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1), CID[c])
        if sides:
            fs = self._since(n0)                      # assets._box face order: z0, z1, y0, x1, y1, x0
            for key, i in (("bottom", 0), ("top", 1), ("back", 2), ("right", 3), ("front", 4), ("left", 5)):
                if key in sides: fs[i].material_index = CID[sides[key]]
        self._tag(n0, nobevel)

    def cyl(self, x, y, z0, z1, r0, r1, c, n=16, smooth=True, caps=True, nobevel=None):
        n0 = len(self.bm.faces); _cyl(self.bm, x, y, z0, z1, r0, r1, n, CID[c], smooth, caps)
        self._tag(n0, n < 14 if nobevel is None else nobevel)

    def tube(self, pts, r, c, n=12, caps=True):
        n0 = len(self.bm.faces); _tube(self.bm, pts, r, n, CID[c], caps, True); self._tag(n0, True)

    def lathe(self, prof, c, n=20, x=0.0, y=0.0, smooth=True, caps=True, nobevel=None):
        n0 = len(self.bm.faces); _lathe(self.bm, prof, n, CID[c], x, y, smooth, caps)
        self._tag(n0, n < 14 if nobevel is None else nobevel)
        return n0

    def prism(self, pts, a0, a1, c, axis="y", nobevel=False):
        n0 = len(self.bm.faces); _prism(self.bm, pts, a0, a1, CID[c], axis); self._tag(n0, nobevel)

    def band(self, outer, inner, a0, a1, c, axis="y", nobevel=False):
        n0 = len(self.bm.faces); _band(self.bm, outer, inner, a0, a1, CID[c], axis); self._tag(n0, nobevel)
        return n0

    def ico(self, center, r, c, subdiv=2, scale=(1, 1, 1), amp=0.0, freq=1.0, seed=0, zmin=None):
        n0 = len(self.bm.faces); _ico(self.bm, center, r, subdiv, scale, amp, freq, seed, CID[c], zmin, True); self._tag(n0, True)

    def paint(self, n0, c, pred):
        for f in self._since(n0):
            if pred(f): f.material_index = CID[c]


def _rect(x0, z0, x1, z1): return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def _sq(h): return _rect(-h, -h, h, h)


def _pkey(n):
    ax = max(range(3), key=lambda i: abs(n[i])); return ax * 2 + (1 if n[ax] < 0 else 0)


def _proj(co, k):
    """Planar projection per dominant axis, oriented so a viewer facing the face reads it unmirrored
    (u to the viewer's right, v up; top faces: u = +X, v = +Y)."""
    x, y, z = co
    return ((y, z), (-y, z), (-x, z), (x, z), (x, y), (-x, y))[k]


def _atlas_uv(bm, name):
    """UV every face into its atlas cell. Islands = edge-connected faces with the same cell and projection
    axis. Tile cells: real scale (PPM), long side along the grain, seeded offset inside the cell (8 px
    padding), uniform shrink only when the island is larger than the cell. Decal cells: fitted."""
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    bm.normal_update(); bm.faces.ensure_lookup_table(); bm.faces.index_update()
    faces = list(bm.faces); keys = [(f.material_index, _pkey(f.normal)) for f in faces]
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2 and keys[lf[0].index] == keys[lf[1].index]:
            ra, rb = find(lf[0].index), find(lf[1].index)
            if ra != rb: parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for i in range(len(faces)): groups.setdefault(find(i), []).append(faces[i])
    dens, warn = [], []

    def bounds(p):
        xs = [a for a, b in p.values()]; ys = [b for a, b in p.values()]
        return min(xs), min(ys), max(xs), max(ys)
    for k, root in enumerate(sorted(groups)):
        fs = groups[root]; cid, pk = keys[root]
        if cid == CID["glass"]: cid = CID["white"]                     # glass is untextured: any valid UVs
        cname, cx, cy, cw, ch, kind, grain = CELLS[cid]
        pts = {l: _proj(l.vert.co, pk) for f in fs for l in f.loops}
        a0, b0, a1, b1 = bounds(pts)
        bottom = AH - cy - ch
        if kind == "decal":
            w, h = max(a1 - a0, 1e-6), max(b1 - b0, 1e-6); pad = 1.5
            sx, sy = (cw - 2 * pad) / w, (ch - 2 * pad) / h
            if abs((w / h) / (cw / ch) - 1.0) > 0.06: warn.append("%s: decal %s aspect %.3f vs cell %.3f" % (name, cname, w / h, cw / ch))
            for l, (a, b) in pts.items(): l[uv].uv = ((cx + pad + (a - a0) * sx) / AW, (bottom + pad + (b - b0) * sy) / AH)
            continue
        pad = 8.0; avw, avh = (cw - 2 * pad) / PPM, (ch - 2 * pad) / PPM
        w, h = max(a1 - a0, 1e-6), max(b1 - b0, 1e-6)
        if grain == "u": rot = h > w * 1.05
        elif grain == "v": rot = w > h * 1.05
        else: rot = min(avw / h, avh / w) > min(avw / w, avh / h) * 1.01
        if rot:
            pts = {l: (b, -a) for l, (a, b) in pts.items()}; a0, b0, a1, b1 = bounds(pts)
            w, h = max(a1 - a0, 1e-6), max(b1 - b0, 1e-6)
        s = min(1.0, avw / w, avh / h)
        rnd = random.Random(zlib.crc32(("%s/%d" % (name, k)).encode()))
        ox, oy = rnd.random() * (avw - w * s), rnd.random() * (avh - h * s)
        for l, (a, b) in pts.items():
            l[uv].uv = ((cx + pad + (ox + (a - a0) * s) * PPM) / AW, (bottom + pad + (oy + (b - b0) * s) * PPM) / AH)
        dens.append((PPM * s, sum(f.calc_area() for f in fs)))
    tot = sum(a for _, a in dens) or 1.0
    return {"islands": len(groups), "min_ppm": round(min((d for d, _ in dens), default=PPM), 1),
            "mean_ppm": round(sum(d * a for d, a in dens) / tot, 1), "warnings": warn}


def _finish_mesh(m, name, bevel):
    """Normals, ground-face removal, chamfers / sharp edges (assets._finish), recentring on the XY
    bounding box with min z = 0, atlas UVs, then material_index -> slot (0 atlas, 1 glass)."""
    bm = m.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.normal_update()
    ground = [f for f in bm.faces if f.normal.z < -0.999 and all(abs(v.co.z) < 1e-5 for v in f.verts)]
    if ground: bmesh.ops.delete(bm, geom=ground, context="FACES")
    for f in bm.faces: f.material_index += 1                  # chamfer faces made by the bevel get material 0: shift the cells
    _finish(bm, bevel, recalc=False)                          # by one so they can be found, then give them the cell of their
    new = [f for f in bm.faces if f.material_index == 0]      # largest neighbour
    for _ in range(6):
        left = []
        for f in new:
            nb = [g for e in f.edges for g in e.link_faces if g is not f and g.material_index > 0]
            if nb: f.material_index = max(nb, key=lambda g: g.calc_area()).material_index
            else: left.append(f)
        if not left: break
        new = left
    for f in bm.faces: f.material_index = max(0, f.material_index - 1)
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    d = Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)))
    bmesh.ops.translate(bm, vec=d, verts=bm.verts)
    if m.anchor is not None: m.anchor = (round(m.anchor[0] + d.x, 4), round(m.anchor[1] + d.y, 4))
    stats = _atlas_uv(bm, name)
    lay = bm.faces.layers.int.get("mrs_cell") or bm.faces.layers.int.new("mrs_cell")
    glass = CID["glass"]; stats["glass"] = False
    for f in bm.faces:
        f[lay] = f.material_index
        if f.material_index == glass: stats["glass"] = True
        f.material_index = 1 if f.material_index == glass else 0
    stats["shift"] = tuple(round(c, 4) for c in d)
    return stats


# ============================================================================== objects
def _bench(m):
    for fx, arm in ((-0.80, True), (0.0, False), (0.80, True)):
        t = 0.025 if arm else 0.02; x0, x1 = fx - t, fx + t
        m.box(x0, 0.150, 0.0, x1, 0.200, 0.655 if arm else 0.41, "steel_dark")                                  # front leg / arm post
        m.prism([(-0.215, 0.0), (-0.165, 0.0), (-0.135, 0.40), (-0.225, 0.86), (-0.275, 0.86), (-0.185, 0.40)], x0, x1, "steel_dark", "x")
        m.prism([(-0.20, 0.375), (0.215, 0.395), (0.215, 0.425), (-0.20, 0.405)], x0 - 0.002, x1 + 0.002, "steel_dark", "x")   # seat rail
        if arm: m.box(x0 - 0.008, -0.205, 0.635, x1 + 0.008, 0.235, 0.665, "steel_dark")                          # armrest
        for ya, yb in ((0.143, 0.207), (-0.224, -0.156)): m.box(x0 - 0.006, ya, 0.0, x1 + 0.006, yb, 0.012, "rubber")
    for j in range(5):                                                                                              # seat slats
        y1 = 0.215 - j * 0.082; y0 = y1 - 0.068; zc = 0.405 + ((y0 + y1) / 2 + 0.20) / 0.415 * 0.02
        m.box(-0.90, y0, zc - 0.002, 0.90, y1, zc + 0.033, "wood")
    d = Vector((-0.09, 0.46)).normalized(); nrm = Vector((d.y, -d.x))
    for zc in (0.52, 0.65, 0.78):                                                                                   # back slats on the reclined support
        L = Vector((-0.135 - 0.09 * (zc - 0.40) / 0.46, zc))
        p0 = L - d * 0.045 - nrm * 0.004; p1 = L + d * 0.045 - nrm * 0.004
        m.prism([tuple(p0), tuple(p1), tuple(p1 + nrm * 0.032), tuple(p0 + nrm * 0.032)], -0.90, 0.90, "wood", "x")


def _bench_backless(m):
    for sx in (-1, 1):
        x = sx * 0.62
        m.box(x - 0.13, -0.19, 0.0, x + 0.13, 0.19, 0.38, "concrete")
        m.box(x - 0.09, -0.215, 0.375, x + 0.09, 0.215, 0.40, "steel_dark")
    for j in range(5):
        y0 = -0.214 + j * 0.089; m.box(-0.90, y0, 0.398, 0.90, y0 + 0.072, 0.445, "plastic")


def _keyhole(m, x, y, z, r=0.011):
    m.tube([(x, y - 0.004, z), (x, y + 0.004, z)], r, "stainless", 10)


def _bin_waste(m):
    m.box(-0.20, -0.14, 0.0, 0.20, 0.14, 0.075, "black")                                                         # recessed plinth
    m.box(-0.26, -0.20, 0.07, 0.26, 0.20, 0.925, "steel_dark")                                                   # body
    m.box(-0.275, -0.215, 0.92, 0.275, 0.215, 0.95, "black")                                                     # lid rim
    m.prism([(-0.205, 0.948), (0.205, 0.948), (0.15, 0.99), (-0.15, 0.99)], -0.265, 0.265, "black", "x")        # lid
    m.band(_rect(-0.20, 0.64, 0.20, 0.865), _rect(-0.165, 0.67, 0.165, 0.835), 0.19, 0.235, "steel_dark", "y")  # aperture hood
    m.box(-0.17, 0.195, 0.665, 0.17, 0.205, 0.84, "void", nobevel=True)                                          # dark opening
    m.box(-0.22, 0.198, 0.12, 0.22, 0.204, 0.60, "steel_dark")                                                   # service door
    _keyhole(m, 0.17, 0.205, 0.55)
    m.box(-0.06, 0.2035, 0.40, 0.06, 0.2055, 0.52, "steel_dark", nobevel=True, front="label_litter")


def _bin_recycling(m):
    m.box(-0.44, -0.15, 0.0, 0.44, 0.15, 0.075, "black")
    m.box(-0.48, -0.21, 0.07, 0.48, 0.21, 0.93, "steel_dark")
    for x in (-0.16, 0.16): m.box(x - 0.004, 0.205, 0.10, x + 0.004, 0.214, 0.925, "black", nobevel=True)       # compartment joints
    for cx, c in ((-0.32, "green"), (0.0, "blue"), (0.32, "yellow")):
        m.box(cx - 0.155, -0.222, 0.925, cx + 0.155, 0.222, 0.97, c)                                             # coloured lid
        if c == "green":                                                                                          # bottles: round hole
            m.band(_xf(_ngon(24, 0.085), dx=cx, dz=0.76), _xf(_ngon(24, 0.058), dx=cx, dz=0.76), 0.20, 0.242, c, "y")
            m.prism(_xf(_ngon(24, 0.062), dx=cx, dz=0.76), 0.205, 0.216, "void", "y", nobevel=True)
        elif c == "blue":                                                                                         # paper: slot
            m.band(_rect(cx - 0.12, 0.70, cx + 0.12, 0.82), _rect(cx - 0.095, 0.745, cx + 0.095, 0.775), 0.20, 0.242, c, "y")
            m.box(cx - 0.10, 0.205, 0.74, cx + 0.10, 0.216, 0.78, "void", nobevel=True)
        else:                                                                                                     # cans / plastics: square
            m.band(_rect(cx - 0.105, 0.665, cx + 0.105, 0.855), _rect(cx - 0.075, 0.695, cx + 0.075, 0.825), 0.20, 0.242, c, "y")
            m.box(cx - 0.08, 0.205, 0.69, cx + 0.08, 0.216, 0.83, "void", nobevel=True)
        m.box(cx - 0.13, 0.206, 0.12, cx + 0.13, 0.214, 0.62, "steel_dark")                                     # door
        _keyhole(m, cx + 0.10, 0.215, 0.58)
        m.box(cx - 0.05, 0.2135, 0.47, cx + 0.05, 0.2155, 0.57, "steel_dark", nobevel=True, front="label_recycle")


def _hoop(m, x):
    R, ly, top, r = 0.15, 0.375, 0.75, 0.0254
    pts = [(x, -ly, 0.0), (x, -ly, 0.3), (x, -ly, top - R)]
    pts += [(x, -ly + R + R * math.cos(math.pi - math.pi / 2 * k / 6), top - R + R * math.sin(math.pi - math.pi / 2 * k / 6)) for k in range(1, 7)]
    pts += [(x, ly - R + R * math.cos(math.pi / 2 - math.pi / 2 * k / 6), top - R + R * math.sin(math.pi / 2 - math.pi / 2 * k / 6)) for k in range(0, 6)]
    pts += [(x, ly, top - R), (x, ly, 0.3), (x, ly, 0.0)]
    m.tube(pts, r, "galv", 12)
    m.tube([(x, -ly, 0.15), (x, ly, 0.15)], 0.0127, "galv", 8)                                                   # cane-detection tapping rail
    for y in (-ly, ly): m.cyl(x, y, 0.0, 0.008, 0.06, 0.056, "galv", 16)                                         # base flanges


def _bike_hoop(m): _hoop(m, 0.0)


def _bike_row(m):
    for x in (-1.0, 0.0, 1.0): _hoop(m, x)


SH_X = (-2.0, -0.667, 0.667, 2.0)
ROOF = [(-0.86, 2.40), (0.97, 2.40), (0.97, 2.56), (-0.86, 2.50)]


def _bus_shelter(m):
    for x in SH_X: m.box(x - 0.04, -0.74, 0.0, x + 0.04, -0.66, 2.42, "alu")                                  # rear posts
    for x in (-2.0, 2.0): m.box(x - 0.04, 0.58, 0.0, x + 0.04, 0.66, 2.42, "alu")                              # front end posts
    m.box(-2.0, -0.725, 0.08, 2.0, -0.675, 0.14, "steel_dark")                                                 # back wall rails
    m.box(-2.0, -0.725, 2.22, 2.0, -0.675, 2.30, "alu")
    for xa, xb in zip(SH_X, SH_X[1:]):
        m.box(xa + 0.03, -0.706, 0.135, xb - 0.03, -0.694, 2.225, "glass", nobevel=True)
        m.box(xa + 0.04, -0.709, 1.40, xb - 0.04, -0.691, 1.46, "white", nobevel=True)                         # manifestation band
    m.box(-2.025, -0.67, 0.08, -1.975, 0.59, 0.14, "steel_dark"); m.box(-2.025, -0.67, 2.22, -1.975, 0.59, 2.30, "alu")   # left end screen
    m.box(-2.006, -0.67, 0.135, -1.994, 0.59, 2.225, "glass", nobevel=True)
    m.box(-2.009, -0.66, 1.40, -1.991, 0.58, 1.46, "white", nobevel=True)
    m.box(1.94, -0.67, 0.10, 2.06, 0.59, 2.18, "alu")                                                           # right end: advertising case
    m.box(1.936, -0.60, 0.25, 1.941, 0.60, 2.05, "alu", nobevel=True, left="poster")
    m.box(2.059, -0.60, 0.25, 2.064, 0.60, 2.05, "alu", nobevel=True, right="poster")
    m.prism(ROOF, -2.2, 2.2, "alu", "x")                                                                        # roof, falls to the back
    m.box(-2.2, 0.95, 2.37, 2.2, 0.99, 2.60, "steel_dark")                                                      # fascia
    for x in SH_X: m.prism([(-0.735, 2.26), (-0.735, 2.405), (0.90, 2.405), (0.90, 2.37)], x - 0.03, x + 0.03, "steel_dark", "x")
    m.box(-0.62, -0.66, 0.46, 0.62, -0.36, 0.495, "stainless")                                                  # seat
    for x in (-0.56, 0.56):
        m.box(x - 0.015, -0.69, 0.42, x + 0.015, -0.38, 0.465, "steel_dark"); m.box(x - 0.013, -0.688, 0.14, x + 0.013, -0.662, 0.455, "steel_dark")
    m.box(-1.55, -0.690, 1.04, -1.13, -0.652, 1.66, "alu")                                                      # timetable case (inside, left bay)
    m.box(-1.54, -0.655, 1.05, -1.14, -0.648, 1.65, "alu", nobevel=True, front="timetable")
    m.box(0.75, -0.40, 2.10, 1.25, -0.32, 2.34, "black")                                                        # real-time display
    m.box(0.77, -0.3215, 2.105, 1.23, -0.318, 2.335, "black", nobevel=True, front="display")
    for x in (0.85, 1.15): m.cyl(x, -0.36, 2.33, 2.41, 0.008, 0.008, "steel_dark", 8)


def _bus_shelter_lod1(m):
    for x in SH_X: m.box(x - 0.04, -0.74, 0.0, x + 0.04, -0.66, 2.42, "alu", nobevel=True)
    for x in (-2.0, 2.0): m.box(x - 0.04, 0.58, 0.0, x + 0.04, 0.66, 2.42, "alu", nobevel=True)
    m.box(-1.97, -0.706, 0.08, 1.97, -0.694, 2.30, "glass", nobevel=True)
    m.box(-2.006, -0.66, 0.08, -1.994, 0.58, 2.30, "glass", nobevel=True)
    m.box(1.94, -0.67, 0.10, 2.06, 0.59, 2.18, "alu", nobevel=True)
    m.box(1.936, -0.60, 0.25, 2.064, 0.60, 2.05, "alu", nobevel=True, left="poster", right="poster")
    m.prism(ROOF, -2.2, 2.2, "alu", "x", nobevel=True)
    m.box(-2.2, 0.95, 2.37, 2.2, 0.99, 2.60, "steel_dark", nobevel=True)
    m.box(-0.62, -0.66, 0.46, 0.62, -0.36, 0.495, "stainless", nobevel=True)
    m.box(-1.55, -0.690, 1.04, -1.13, -0.648, 1.66, "alu", nobevel=True, front="timetable")


def _bus_pole(m):
    m.anchor = (0.0, 0.0)
    m.cyl(0, 0, 0.0, 0.10, 0.058, 0.052, "steel_dark", 16)                                                      # base collar
    m.cyl(0, 0, 0.0, 2.96, 0.038, 0.038, "steel_dark", 16)
    m.lathe([(0.042, 2.95), (0.042, 2.97), (0.03, 2.99), (0.0, 2.995)], "black", 16)
    m.box(-0.012, 0.06, 2.20, 0.012, 0.50, 2.84, "alu")                                                         # flag, projects over the kerb (+Y)
    m.box(0.011, 0.08, 2.22, 0.014, 0.48, 2.82, "alu", nobevel=True, right="flag")
    m.box(-0.014, 0.08, 2.22, -0.011, 0.48, 2.82, "alu", nobevel=True, left="flag")
    for z in (2.30, 2.74): m.box(-0.016, 0.0, z - 0.025, 0.016, 0.075, z + 0.025, "steel_dark")
    m.box(-0.22, -0.10, 1.05, 0.22, -0.055, 1.70, "alu")                                                        # timetable case, footway side (-Y)
    m.box(-0.20, -0.1035, 1.075, 0.20, -0.0985, 1.675, "alu", nobevel=True, back="timetable")
    for z in (1.15, 1.60): m.box(-0.02, -0.06, z - 0.02, 0.02, 0.0, z + 0.02, "steel_dark")


def _info_board(m):
    m.box(-0.37, -0.10, 0.0, 0.37, 0.10, 0.06, "black")
    m.box(-0.35, -0.08, 0.055, 0.35, 0.08, 2.24, "steel_dark")
    m.box(-0.36, -0.09, 2.235, 0.36, 0.09, 2.28, "alu")
    for y0, y1, side in ((0.078, 0.083, "front"), (-0.083, -0.078, "back")):
        m.box(-0.30, y0, 0.78, 0.30, y1, 1.98, "alu", nobevel=True, **{side: "map"})
        m.box(-0.08, y0, 2.02, 0.08, y1, 2.18, "alu", nobevel=True, **{side: "label_info"})


def _bollard(m):
    m.lathe([(0.084, 0.0), (0.084, 0.94), (0.079, 0.966), (0.064, 0.985), (0.038, 0.997), (0.0, 1.0)], "black", 20)
    m.cyl(0, 0, 0.80, 0.86, 0.0855, 0.0855, "white", 20)                                                       # reflective band
    m.cyl(0, 0, 0.0, 0.012, 0.11, 0.105, "iron", 20)                                                            # ground collar


def _bollard_removable(m):
    m.box(-0.12, -0.12, 0.0, 0.12, 0.12, 0.012, "galv")                                                         # socket plate
    m.lathe([(0.075, 0.0), (0.075, 0.035), (0.062, 0.045), (0.0, 0.045)], "galv", 20)                           # socket boss
    m.cyl(0, 0, 0.03, 0.95, 0.057, 0.057, "stainless", 20)
    m.lathe([(0.061, 0.945), (0.061, 0.962), (0.05, 0.968), (0.0, 0.968)], "stainless", 20)                     # cap
    for z0 in (0.74, 0.84): m.cyl(0, 0, z0, z0 + 0.06, 0.0585, 0.0585, "yellow", 20)
    m.tube([(0.03 * math.cos(math.pi * (1 - k / 8)), 0.0, 0.962 + 0.03 * math.sin(math.pi * (1 - k / 8))) for k in range(9)], 0.007, "stainless", 8)
    m.box(-0.02, 0.06, 0.012, 0.02, 0.095, 0.05, "galv")                                                        # padlock lug
    m.tube([(0.0, 0.093, 0.032), (0.0, 0.0975, 0.032)], 0.006, "black", 8)


def _ped_barrier(m):
    for x in (-1.0, 1.0):
        m.box(x - 0.03, -0.03, 0.0, x + 0.03, 0.03, 1.06, "galv")
        m.box(x - 0.035, -0.035, 1.055, x + 0.035, 0.035, 1.075, "galv")
    for z in (0.20, 1.00): m.tube([(-1.0, 0.0, z), (1.0, 0.0, z)], 0.021, "galv", 12)
    for i in range(17): m.cyl(-0.88 + i * 0.11, 0.0, 0.19, 1.01, 0.009, 0.009, "galv", 6)


def _planter(m):
    k = math.sqrt(2.0)
    n0 = m.lathe([(0.55 * k, 0.0), (0.60 * k, 0.50), (0.62 * k, 0.50), (0.62 * k, 0.56), (0.56 * k, 0.56), (0.56 * k, 0.49), (0.0, 0.49)],
                 "concrete", 4, smooth=False, nobevel=False)
    vs = list({v for f in m._since(n0) for v in f.verts})
    bmesh.ops.rotate(m.bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 4, 3, "Z"))
    m.paint(n0, "soil", lambda f: all(abs(v.co.z - 0.49) < 1e-5 for v in f.verts))
    m.ico((0.0, 0.0, 0.70), 0.34, "foliage", 2, (1.1, 1.1, 0.8), 0.22, 2.5, 3, zmin=0.49)
    m.ico((0.20, -0.17, 0.84), 0.25, "foliage", 2, (1.0, 1.0, 0.9), 0.2, 3.0, 4, zmin=0.49)
    m.ico((-0.22, 0.19, 0.80), 0.23, "foliage", 2, (1.0, 1.0, 0.9), 0.2, 3.0, 5, zmin=0.49)


def _tree_grate(m):
    m.band(_sq(0.60), _sq(0.56), 0.0, 0.006, "galv", "z", nobevel=True)                                       # angle frame
    N, S, R, zt = 32, 0.558, 0.22, 0.005
    outer, inner = [], []
    for k in range(N):
        a = TAU * k / N; c, s = math.cos(a), math.sin(a); t = S / max(abs(c), abs(s))
        outer.append((c * t, s * t)); inner.append((R * c, R * s))
    n0 = m.band(outer, inner, 0.0, zt, "iron", "z", nobevel=True)
    m.paint(n0, "grate_tree", lambda f: all(abs(v.co.z - zt) < 1e-6 for v in f.verts))
    m.cyl(0, 0, 0.0, 0.002, 0.222, 0.222, "soil", 32, nobevel=True)                                           # mulch around the trunk


def _tree_guard(m):
    """A square street-tree guard, 1.2 m across and 1.1 m tall: four 50 mm dark steel posts at the corners and two flat
    rails (knee and top) round them; the trunk stands in the middle. Placement scales it to the bed it surrounds."""
    P, H = 0.55, 1.10
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box(sx * P - 0.025, sy * P - 0.025, 0.0, sx * P + 0.025, sy * P + 0.025, H, "steel_dark")
            m.box(sx * P - 0.032, sy * P - 0.032, H, sx * P + 0.032, sy * P + 0.032, H + 0.012, "steel_dark", nobevel=True)   # post cap
    for z0, z1 in ((0.30, 0.34), (1.02, 1.06)):
        m.band(_sq(P + 0.035), _sq(P + 0.015), z0, z1, "steel_dark", "z")


def _tree_pit_open(m):
    rnd = random.Random(7); L, J = 0.192, 0.008
    for sy in (-1, 1):
        for i in range(10):
            x0 = -1.0 + J / 2 + i * (L + J); m.box(x0, sy * 0.504, 0.0, x0 + L, sy * 0.596, 0.0052 + 0.0008 * rnd.random(), "granite", nobevel=True)
    for sx in (-1, 1):
        for j in range(5):
            y0 = -0.5 + J / 2 + j * (L + J); m.box(sx * 0.904, y0, 0.0, sx * 0.996, y0 + L, 0.0052 + 0.0008 * rnd.random(), "granite", nobevel=True)
    nx, ny, X, Y = 18, 10, 0.896, 0.496; bm = m.bm; cid = CID["soil"]
    top = [[None] * (ny + 1) for _ in range(nx + 1)]
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = -X + 2 * X * i / nx, -Y + 2 * Y * j / ny
            edge = i in (0, nx) or j in (0, ny)
            bump = max(0.0, (1 - (x / X) ** 2) * (1 - (y / Y) ** 2))
            z = 0.003 if edge else 0.0035 + 0.0035 * bump + 0.0012 * rnd.random()
            top[i][j] = bm.verts.new((x, y, z))
    for i in range(nx):
        for j in range(ny):
            f = bm.faces.new((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1])); f.material_index = cid; f.smooth = True
    ring = [top[i][0] for i in range(nx)] + [top[nx][j] for j in range(ny)] + [top[i][ny] for i in range(nx, 0, -1)] + [top[0][j] for j in range(ny, 0, -1)]
    low = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in ring]
    for k in range(len(ring)):
        f = bm.faces.new((ring[k], low[k], low[(k + 1) % len(ring)], ring[(k + 1) % len(ring)])); f.material_index = cid


def _cabinet(m):
    m.box(-0.53, -0.23, 0.0, 0.53, 0.23, 0.08, "concrete")
    m.box(-0.50, -0.20, 0.075, 0.50, 0.20, 1.28, "grey_light")
    m.prism([(-0.225, 1.275), (0.225, 1.275), (0.225, 1.305), (0.0, 1.34), (-0.225, 1.305)], -0.525, 0.525, "grey_light", "x")
    for s in (-1, 1):
        xa, xb = sorted((s * 0.006, s * 0.488))
        m.box(xa, 0.197, 0.12, xb, 0.206, 1.24, "grey_light")                                                   # door leaf
        m.box(s * 0.04 - 0.012, 0.205, 0.60, s * 0.04 + 0.012, 0.228, 0.80, "black")                           # handle
        _keyhole(m, s * 0.04, 0.21, 0.86, 0.012)
        for z in (0.28, 0.70, 1.12): m.cyl(s * 0.492, 0.212, z, z + 0.06, 0.011, 0.011, "black", 10)            # hinges
        xv = s * 0.50
        m.box(xv, -0.13, 0.93, xv + s * 0.004, 0.13, 1.13, "void", nobevel=True)                                # side vents
        for i in range(5): z = 0.945 + i * 0.037; m.box(xv, -0.125, z, xv + s * 0.016, 0.125, z + 0.018, "grey_light", nobevel=True)
    m.box(-0.004, 0.196, 0.12, 0.004, 0.201, 1.24, "void", nobevel=True)                                       # seam between the leaves
    m.box(-0.30, 0.2055, 1.00, -0.18, 0.2075, 1.12, "grey_light", nobevel=True, front="label_hazard")
    m.box(0.18, 0.2055, 1.08, 0.36, 0.2075, 1.15, "white", nobevel=True)                                       # ID plate


def _hydrant(m):
    m.lathe([(0.15, 0.0), (0.15, 0.03), (0.12, 0.045), (0.0, 0.045)], "iron", 20)                              # ground flange
    for k in range(6):
        a = TAU * k / 6 + 0.26; m.cyl(0.133 * math.cos(a), 0.133 * math.sin(a), 0.025, 0.048, 0.012, 0.012, "iron", 6)
    m.lathe([(0.105, 0.04), (0.10, 0.08), (0.10, 0.55), (0.125, 0.57), (0.125, 0.61), (0.105, 0.63), (0.105, 0.70), (0.12, 0.72),
             (0.09, 0.80), (0.05, 0.83), (0.0, 0.836)], "red", 20)
    m.cyl(0, 0, 0.82, 0.88, 0.03, 0.026, "iron", 5, smooth=False)                                              # operating nut
    for sx in (-1, 1):
        m.tube([(sx * 0.09, 0, 0.42), (sx * 0.19, 0, 0.42)], 0.045, "red", 16)
        m.tube([(sx * 0.188, 0, 0.42), (sx * 0.228, 0, 0.42)], 0.052, "iron", 16)
    m.tube([(0, 0.08, 0.36), (0, 0.19, 0.36)], 0.06, "red", 16)                                                # pumper outlet toward the road
    m.tube([(0, 0.188, 0.36), (0, 0.228, 0.36)], 0.068, "iron", 16)


def _drain_grate(m):
    m.band(_rect(-0.25, -0.175, 0.25, 0.175), _rect(-0.215, -0.14, 0.215, 0.14), 0.0, 0.006, "iron", "z", nobevel=True)
    m.box(-0.217, -0.142, 0.0, 0.217, 0.142, 0.0015, "void", nobevel=True)
    w, n = 0.022, 9; gap = (0.43 - n * w) / (n + 1)
    for i in range(n):                                                                                          # bars across the flow (along Y)
        x0 = -0.215 + gap + i * (w + gap); m.box(x0, -0.141, 0.0, x0 + w, 0.141, 0.005, "iron", nobevel=True)
    m.box(-0.214, -0.012, 0.0, 0.214, 0.012, 0.0045, "iron", nobevel=True)


def _access_cover(m):
    m.band(_sq(0.34), _sq(0.305), 0.0, 0.006, "galv", "z", nobevel=True)
    m.box(-0.307, -0.307, 0.0, 0.307, 0.307, 0.0015, "void", nobevel=True)
    m.box(-0.30, -0.30, 0.0, 0.30, 0.30, 0.005, "iron", nobevel=True, top="iron_tread")
    for sx in (-1, 1): m.box(sx * 0.24 - 0.022, -0.006, 0.0, sx * 0.24 + 0.022, 0.006, 0.0052, "void", nobevel=True)


def _acc(front, back, left, right): return {"front": front, "back": back, "left": left, "right": right}


# name, builder, kind, zone, nominal footprint (w, d), access, walkable, facing, bevel, extra props
SPECS = [
    ("MRS_F_Bench", _bench, "bench", "furniture", (1.80, 0.51), _acc(0.9, 0.2, 0.6, 0.6), False, "walk", 0.006, {}),
    ("MRS_F_BenchBackless", _bench_backless, "bench", "furniture", (1.80, 0.43), _acc(0.9, 0.9, 0.3, 0.3), False, "any", 0.008, {}),
    ("MRS_F_BinWaste", _bin_waste, "bin", "furniture", (0.55, 0.45), _acc(0.6, 0.0, 0.2, 0.2), False, "walk", 0.006, {}),
    ("MRS_F_BinRecycling", _bin_recycling, "bin", "furniture", (0.96, 0.46), _acc(0.6, 0.0, 0.2, 0.2), False, "walk", 0.006, {}),
    ("MRS_F_BikeRackHoop", _bike_hoop, "bike_rack", "furniture", (0.12, 0.87), _acc(1.0, 1.0, 0.45, 0.45), False, "any", 0.0, {"mrs_pitch": 1.0}),
    ("MRS_F_BikeRackRow", _bike_row, "bike_rack", "furniture", (2.12, 0.87), _acc(1.0, 1.0, 0.45, 0.45), False, "any", 0.0, {"mrs_pitch": 1.0}),
    ("MRS_F_BusShelter", _bus_shelter, "bus_shelter", "furniture", (4.40, 1.85), _acc(1.5, 0.3, 0.6, 0.6), False, "carriageway", 0.008,
     {"mrs_lod1": "MRS_F_BusShelter_LOD1"}),
    ("MRS_F_BusShelter_LOD1", _bus_shelter_lod1, "bus_shelter", "furniture", (4.40, 1.85), _acc(1.5, 0.3, 0.6, 0.6), False, "carriageway", 0.0,
     {"mrs_lod": 1, "mrs_lod_of": "MRS_F_BusShelter"}),
    ("MRS_F_BusStopPole", _bus_pole, "bus_pole", "curb", (0.44, 0.60), _acc(0.5, 0.9, 0.3, 0.3), False, "carriageway", 0.005, {}),
    ("MRS_F_InfoBoard", _info_board, "info_board", "furniture", (0.74, 0.20), _acc(1.0, 1.0, 0.3, 0.3), False, "any", 0.008, {}),
    ("MRS_F_Bollard", _bollard, "bollard", "curb", (0.22, 0.22), _acc(0.3, 0.3, 1.2, 1.2), False, "any", 0.004, {"mrs_pitch": 1.5}),
    ("MRS_F_BollardRemovable", _bollard_removable, "bollard", "curb", (0.24, 0.24), _acc(0.3, 0.3, 1.2, 1.2), False, "carriageway", 0.003, {"mrs_pitch": 1.5}),
    ("MRS_F_PedBarrier", _ped_barrier, "barrier", "curb", (2.07, 0.07), _acc(0.45, 0.0, 0.0, 0.0), False, "carriageway", 0.004, {"mrs_pitch": 2.0}),
    ("MRS_F_Planter", _planter, "planter", "furniture", (1.24, 1.24), _acc(0.3, 0.3, 0.3, 0.3), False, "any", 0.015, {}),
    ("MRS_F_TreePitGrate", _tree_grate, "tree_pit", "furniture", (1.20, 1.20), _acc(0.0, 0.0, 0.0, 0.0), True, "any", 0.0, {}),
    ("MRS_F_TreePitOpen", _tree_pit_open, "tree_pit", "furniture", (2.00, 1.20), _acc(0.0, 0.0, 0.0, 0.0), False, "any", 0.0, {}),
    ("MRS_F_TreeGuard", _tree_guard, "tree_guard", "furniture", (1.20, 1.20), _acc(0.0, 0.0, 0.0, 0.0), False, "any", 0.004, {}),
    ("MRS_F_UtilityCabinet", _cabinet, "utility", "frontage", (1.06, 0.46), _acc(0.9, 0.0, 0.3, 0.3), False, "walk", 0.006, {}),
    ("MRS_F_Hydrant", _hydrant, "hydrant", "curb", (0.46, 0.38), _acc(0.9, 0.9, 0.9, 0.9), False, "carriageway", 0.004, {}),
    ("MRS_F_DrainGrate", _drain_grate, "drain", "gutter", (0.50, 0.35), _acc(0.3, 0.3, 0.3, 0.3), True, "carriageway", 0.0, {}),
    ("MRS_F_AccessCover", _access_cover, "access_cover", "flush", (0.68, 0.68), _acc(0.3, 0.3, 0.3, 0.3), True, "any", 0.0, {}),
]
NAMES = tuple(s[0] for s in SPECS)
FLUSH = ("MRS_F_TreePitGrate", "MRS_F_TreePitOpen", "MRS_F_DrainGrate", "MRS_F_AccessCover")
REPORT = {}   # name -> stats of the last build (tris, islands, texel density, uv warnings, recentring shift)


def _tris(me): return sum(len(p.vertices) - 2 for p in me.polygons)


def build_furniture(bake="auto", tex_dir=None, samples=16, verbose=True):
    """(Re)build collection MRS_Furniture (linked under the scene, hidden from render; objects at the origin,
    hidden). bake: "auto" bakes the atlas only when the PNGs / layout are missing or outdated, True always,
    False never. Returns the collection; per-object stats land in `REPORT`."""
    tex_dir = tex_dir or TEX_DIR
    if bake is True or (bake == "auto" and not atlas_current(tex_dir)): bake_atlas(tex_dir, samples, verbose)
    atlas, glass = atlas_materials(tex_dir)
    col = collection(COLLECTION)
    REPORT.clear()
    for name, builder, kind, zone, fp, access, walk, facing, bevel, extra in SPECS:
        old = bpy.data.meshes.get(name)
        if old is not None and old.users == 0: bpy.data.meshes.remove(old)
        m = _M(); builder(m)
        st = _finish_mesh(m, name, bevel)
        me = bpy.data.meshes.new(name); m.bm.to_mesh(me); m.bm.free()
        me.materials.append(atlas)
        if st["glass"]: me.materials.append(glass)
        o = bpy.data.objects.new(name, me); col.objects.link(o); o.hide_render = True; o.hide_viewport = True
        zs = [v.co.z for v in me.vertices]
        low = [v.co for v in me.vertices if v.co.z < 2.0]
        o["mrs_kind"] = kind
        o["mrs_footprint"] = json.dumps([round(fp[0], 3), round(fp[1], 3)])
        o["mrs_access"] = json.dumps(access)
        o["mrs_zone"] = zone
        o["mrs_walkable"] = bool(walk)
        o["mrs_height"] = round(max(zs), 3)
        o["mrs_facing"] = facing
        o["mrs_base_footprint"] = json.dumps([round(min(v.x for v in low), 3), round(min(v.y for v in low), 3), round(max(v.x for v in low), 3), round(max(v.y for v in low), 3)])
        if m.anchor is not None: o["mrs_anchor"] = json.dumps(list(m.anchor))
        for k, v in extra.items(): o[k] = v
        st["tris"] = _tris(me); st["materials"] = [x.name for x in me.materials]
        REPORT[name] = st
        if verbose and st["warnings"]: print("[furniture] UV warnings:", st["warnings"])
    if verbose: print("[furniture] built %d objects in %s, %d tris" % (len(col.objects), COLLECTION, sum(r["tris"] for r in REPORT.values())))
    return col


def export_library_glb(path, names=None):
    """GLB of the library: every MRS_Furniture object as a separate named node at the origin, materials
    exported with their atlas textures, custom properties as glTF extras. Run in the active scene."""
    col = bpy.data.collections[COLLECTION]
    objs = [o for o in col.objects if names is None or o.name in names]
    state = [(o, o.hide_viewport, o.hide_get()) for o in objs]
    try:
        for o in objs: o.hide_viewport = False; o.hide_set(False)
        bpy.context.view_layer.update()
        for o in bpy.context.view_layer.objects: o.select_set(o in objs)
        bpy.context.view_layer.objects.active = objs[0]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_extras=True,
                                  export_materials="EXPORT", export_normals=True, export_texcoords=True, export_image_format="AUTO")
    finally:
        for o, hv, hs in state:
            o.select_set(False); o.hide_set(hs); o.hide_viewport = hv
    return {"objects": len(objs), "tris": sum(_tris(o.data) for o in objs), "bytes": os.path.getsize(path)}
