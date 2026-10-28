"""Mert Road Studio materials: MRS_Asphalt / MRS_Paint / MRS_Concrete / MRS_BikeLane / MRS_Structure /
MRS_Embankment on four editable shader groups (MRS_AsphaltShader, MRS_PaintShader, MRS_ConcreteShader,
MRS_EmbankmentShader). Every material holds ONE group node named "MRS"; `apply_material_preset` drives it.

Coordinates: object space in metres (roads of any length keep the same texel scale). With "Use UV" = 1 the
group reads the `UVMap` attribute x "Tile Size" instead and samples every noise on a 4D torus, so the
result is seamless: `bake_tiles` uses that to bake albedo / normal / roughness tiles for Godot.
Position-dependent effects (tire tracks from `lat`, edge dirt, grime by object Z) are muted in UV mode.
"""
import math, os
import bpy
from .nodes import T, MRS, new_tree, sock

TWO_PI = 2.0 * math.pi

# A preset is a complete look: {input name: value} applied to every "MRS" group node that has that input, plus
# "overrides" = {material suffix: {input: value}} for inputs that only apply to one material. Every preset is
# merged over _BASE so applying any of them yields the same deterministic state for all six materials.
_BASE = {"Wetness": 0.0, "Surface Type": 1.0, "Cracks": 0.15, "Patch Amount": 0.15, "Tire Wear": 0.5, "Edge Dirt": 0.4,
         "Paint Wear": 0.35, "Yellow": 0.0, "Grime": 0.0, "Rust Streaks": 0.0, "Concrete Variation": 0.2, "Rockiness": 0.35,
         "overrides": {"BikeLane": {"Surface Type": 0.0, "Cracks": 0.0, "Patch Amount": 0.0, "Tire Wear": 0.15, "Edge Dirt": 0.25},
                       "Structure": {"Grime": 0.5, "Rust Streaks": 0.5, "Concrete Variation": 0.3}}}
_PRESETS = {
    "dry": {},
    "wet": {"Wetness": 0.85},
    "worn_city": {"Surface Type": 1.4, "Cracks": 0.55, "Patch Amount": 0.35, "Tire Wear": 0.8, "Edge Dirt": 0.7, "Paint Wear": 0.6,
                  "Grime": 0.45, "Rust Streaks": 0.5, "Concrete Variation": 0.3, "overrides": {"Structure": {"Grime": 0.8, "Rust Streaks": 0.8}}},
    "fresh_highway": {"Surface Type": 0.0, "Cracks": 0.0, "Patch Amount": 0.0, "Tire Wear": 0.25, "Edge Dirt": 0.15, "Paint Wear": 0.08,
                      "Concrete Variation": 0.12, "overrides": {"Structure": {"Grime": 0.1, "Rust Streaks": 0.05}}},
    "old_village": {"Wetness": 0.1, "Surface Type": 4.0, "Cracks": 0.0, "Patch Amount": 0.0, "Tire Wear": 0.35, "Edge Dirt": 0.5,
                    "Paint Wear": 0.75, "Yellow": 0.85, "Grime": 0.6, "Rust Streaks": 0.4, "Concrete Variation": 0.35,
                    "overrides": {"BikeLane": {"Surface Type": 1.0}, "Structure": {"Grime": 0.9, "Rust Streaks": 0.6}}},
    "dirt_track": {"Surface Type": 5.0, "Cracks": 0.0, "Patch Amount": 0.0, "Tire Wear": 1.0, "Edge Dirt": 1.0, "Paint Wear": 1.0,
                   "Grime": 0.5, "Rust Streaks": 0.3, "Rockiness": 0.6, "overrides": {"BikeLane": {"Surface Type": 5.0}}},
}


def _merge(base, over):
    out = {k: v for k, v in base.items() if k != "overrides"}; out.update({k: v for k, v in over.items() if k != "overrides"})
    ov = {k: dict(v) for k, v in base.get("overrides", {}).items()}
    for k, v in over.get("overrides", {}).items(): ov.setdefault(k, {}).update(v)
    out["overrides"] = ov; return out


MATERIAL_PRESETS = {name: _merge(_BASE, p) for name, p in _PRESETS.items()}

MATERIAL_NAMES = ("Asphalt", "Paint", "Concrete", "BikeLane", "Structure", "Embankment")


# ============================================================================== node helpers
class _G:
    """Per-group helper around the T builder: 4D noise on object coords or on a seamless torus (Use UV)."""

    def __init__(self, tree, scale_name="Asphalt Scale"):
        self.tb = T(tree); self.gi = self.tb.n("NodeGroupInput"); self.go = self.tb.n("NodeGroupOutput")
        tb, gi = self.tb, self.gi
        self.use = gi.outputs["Use UV"]; self.keep = tb.math("SUBTRACT", 1.0, self.use)   # 1 in object mode
        tile = gi.outputs["Tile Size"]
        tc = tb.n("ShaderNodeTexCoord"); uv = tb.n("ShaderNodeAttribute", attribute_name="UVMap")
        obj = tc.outputs["Object"]
        self.objz = tb.separate(obj)[2]
        # P: metres in both modes (object xyz, or UV * Tile Size)
        self.P = self.mixv(self.use, obj, tb.vmath("SCALE", uv.outputs["Vector"], scale=tile))
        self.px, self.py, _ = tb.separate(self.P)
        # torus for seamless 4D noise: (R cos u, R sin u, R cos v) + W = R sin v, arc length = metres
        ux, uy, _ = tb.separate(uv.outputs["Vector"])
        R = tb.math("DIVIDE", tile, TWO_PI); au = tb.math("MULTIPLY", ux, TWO_PI); av = tb.math("MULTIPLY", uy, TWO_PI)
        Vt = tb.combine(tb.math("MULTIPLY", tb.math("COSINE", au), R), tb.math("MULTIPLY", tb.math("SINE", au), R), tb.math("MULTIPLY", tb.math("COSINE", av), R))
        # tilt the torus off the noise lattice axes (an axis-aligned circle picks up the cell grid as column banding)
        rot = tb.n("ShaderNodeVectorRotate", rotation_type="AXIS_ANGLE"); tb.inp(rot, "Vector", Vt); tb.inp(rot, "Axis", (0.53, 0.71, 0.46)); tb.inp(rot, "Angle", 0.83)
        Vt = rot.outputs[0]
        Wt = tb.math("MULTIPLY", tb.math("SINE", av), R)
        s = gi.outputs[scale_name]
        self.V = tb.vmath("SCALE", self.mixv(self.use, obj, Vt), scale=s)
        self.W = tb.math("MULTIPLY", self.mixf(self.use, 0.0, Wt), s)

    # -- generic
    def m(self, op, a, b=0.0, c=None, clamp=False):
        out = self.tb.math(op, a, b, c)
        if clamp: out.node.use_clamp = True
        return out

    def mixf(self, fac, a, b):
        n = self.tb.n("ShaderNodeMix", data_type="FLOAT"); self.tb.inp(n, n.inputs[0].identifier, fac)
        self.tb.inp(n, n.inputs[2].identifier, a); self.tb.inp(n, n.inputs[3].identifier, b); return n.outputs[0]

    def mixv(self, fac, a, b):
        n = self.tb.n("ShaderNodeMix", data_type="VECTOR"); self.tb.inp(n, n.inputs[0].identifier, fac)
        self.tb.inp(n, n.inputs[4].identifier, a); self.tb.inp(n, n.inputs[5].identifier, b); return n.outputs[1]

    def mixc(self, fac, a, b, blend="MIX"):
        n = self.tb.n("ShaderNodeMix", data_type="RGBA", blend_type=blend); self.tb.inp(n, n.inputs[0].identifier, fac)
        self.tb.inp(n, n.inputs[6].identifier, a); self.tb.inp(n, n.inputs[7].identifier, b); return n.outputs[2]

    def ramp(self, v, a, b, smooth=True):
        """a -> 0, b -> 1 (a may be greater than b), smoothstep by default."""
        return self.tb.map_range(v, a, b, 0.0, 1.0, True, "SMOOTHSTEP" if smooth else "LINEAR")

    def scale_col(self, col, f):
        if isinstance(col, (tuple, list)): col = tuple(col[:3])
        return self.tb.vmath("SCALE", col, scale=f)

    def lerp(self, t, a, b):
        """float lerp with math nodes (t may be a socket)."""
        return self.m("ADD", a, self.m("MULTIPLY", t, self.m("SUBTRACT", b, a)))

    def gray(self, v):
        return self.tb.combine(v, v, v)

    # -- textures (all 4D so the torus mode is seamless)
    def stretch(self, sx, sy):
        """Anisotropic coordinates: sx across the road (x), sy along it (y), correct in both modes."""
        fv = self.mixv(self.use, self.tb.combine(sx, sy, 1.0), self.tb.combine(sx, sx, sy))
        return self.tb.vmath("MULTIPLY", self.V, fv), self.m("MULTIPLY", self.W, self.mixf(self.use, 1.0, sy))

    def noise(self, scale, detail=2.0, rough=0.5, distortion=0.0, VW=None, label=None):
        V, W = VW or (self.V, self.W)
        n = self.tb.n("ShaderNodeTexNoise", label, noise_dimensions="4D")
        self.tb.inp(n, "Vector", V); self.tb.inp(n, "W", W); self.tb.inp(n, "Scale", scale); self.tb.inp(n, "Detail", detail)
        self.tb.inp(n, "Roughness", rough); self.tb.inp(n, "Distortion", distortion)
        return n.outputs["Fac"]

    def voronoi(self, scale, feature="F1", metric="EUCLIDEAN", randomness=1.0, VW=None, label=None, smooth=None):
        V, W = VW or (self.V, self.W)
        n = self.tb.n("ShaderNodeTexVoronoi", label, voronoi_dimensions="4D", feature=feature, distance=metric)
        self.tb.inp(n, "Vector", V); self.tb.inp(n, "W", W); self.tb.inp(n, "Scale", scale); self.tb.inp(n, "Randomness", randomness)
        if smooth is not None and "Smoothness" in n.inputs: self.tb.inp(n, "Smoothness", smooth)
        return n

    def white(self, vec):
        n = self.tb.n("ShaderNodeTexWhiteNoise", noise_dimensions="3D"); self.tb.inp(n, "Vector", vec); return n.outputs["Value"]

    def attr(self, name):
        return self.tb.n("ShaderNodeAttribute", attribute_name=name).outputs["Fac"]

    def periodic(self, size):
        """(size, n): a repeat length (slab, stone) snapped to Tile Size / n in UV mode so the bake tiles, and the
        count n to wrap cell indices with (`wrap`); in object mode size is untouched and n is huge."""
        tile = self.gi.outputs["Tile Size"]
        n = self.m("MAXIMUM", self.m("ROUND", self.m("DIVIDE", tile, size)), 1.0)
        return self.mixf(self.use, size, self.m("DIVIDE", tile, n)), self.mixf(self.use, 1.0e6, n)

    def wrap(self, idx, n):
        return self.m("FLOORED_MODULO", idx, n)

    def finish(self, col, rough, height, bump_strength, bump_dist=0.02, coat=None, bump_fade=None):
        tb = self.tb
        bump = tb.n("ShaderNodeBump"); tb.inp(bump, "Distance", bump_dist); tb.inp(bump, "Height", height)
        tb.inp(bump, "Strength", bump_strength if bump_fade is None else self.m("MULTIPLY", bump_strength, bump_fade))
        bsdf = tb.n("ShaderNodeBsdfPrincipled")
        tb.inp(bsdf, "Base Color", col); tb.inp(bsdf, "Roughness", self.m("MINIMUM", self.m("MAXIMUM", rough, 0.02), 1.0)); tb.inp(bsdf, "Normal", bump.outputs[0])
        if coat is not None:
            tb.inp(bsdf, "Coat Weight", coat); tb.inp(bsdf, "Coat Roughness", 0.02)
        tb.link(bsdf.outputs[0], self.go.inputs[0])
        return bsdf

    # -- shared effects
    def wet(self, col, rough, height, wetness, broad):
        """Puddles in the broad-noise lows (edges sharpened), darker and glossier everywhere.
        Returns (col, rough, height_fade, coat)."""
        wobble = self.noise(1.2, 3.0, 0.5)
        level = self.m("ADD", broad, self.m("MULTIPLY", self.m("SUBTRACT", wobble, 0.5), 0.12))
        # puddles and damp blotches only collect on (near-)horizontal faces; walls just darken evenly
        nz = self.tb.separate(self.tb.n("ShaderNodeNewGeometry").outputs["Normal"])[2]
        flat = self.ramp(nz, 0.75, 0.95)
        thr = self.m("ADD", 0.28, self.m("MULTIPLY", wetness, 0.26))           # more wetness = bigger puddles
        puddle = self.m("MULTIPLY", self.m("MULTIPLY", self.ramp(level, thr, self.m("SUBTRACT", thr, 0.04)), self.ramp(wetness, 0.15, 0.4)), flat)
        blotch = self.m("MULTIPLY", self.ramp(level, 0.62, 0.3), self.m("ADD", 0.25, self.m("MULTIPLY", flat, 0.75)))
        damp = self.m("MULTIPLY", wetness, self.m("ADD", 0.55, self.m("MULTIPLY", blotch, 0.45)))
        col = self.mixc(self.m("MULTIPLY", damp, 0.55), col, (0.0, 0.0, 0.0, 1))
        col = self.mixc(self.m("MULTIPLY", puddle, 0.45), col, (0.01, 0.012, 0.015, 1))
        rough = self.m("SUBTRACT", rough, self.m("MULTIPLY", damp, 0.5))
        rough = self.mixf(puddle, rough, 0.04)
        fade = self.m("SUBTRACT", 1.0, self.m("MULTIPLY", puddle, 0.95))
        coat = self.m("ADD", self.m("MULTIPLY", puddle, 1.0), self.m("MULTIPLY", damp, 0.35))
        return col, rough, fade, coat


def _mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; m.node_tree.nodes.clear(); return m


def _group_material(name, group, **vals):
    m = _mat(MRS + name); nt = m.node_tree
    g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = bpy.data.node_groups[MRS + group]; g.name = "MRS"; g.label = MRS + group; g.width = 260
    for k, v in vals.items():
        if k in g.inputs: g.inputs[k].default_value = v
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    nt.links.new(g.outputs[0], out.inputs["Surface"])
    return m


def _inputs(g, rows):
    for nm, st, d in rows: sock(g, nm, "INPUT", st, d)
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")


# ============================================================================== asphalt
ASPHALT_INPUTS = (("Asphalt Scale", "NodeSocketFloat", 1.0), ("Asphalt Roughness", "NodeSocketFloat", 0.86), ("Color Variation", "NodeSocketFloat", 0.25),
                  ("Patch Amount", "NodeSocketFloat", 0.15), ("Wetness", "NodeSocketFloat", 0.0), ("Base Color", "NodeSocketColor", (0.075, 0.075, 0.08, 1)),
                  ("Bump Strength", "NodeSocketFloat", 0.35), ("Surface Type", "NodeSocketFloat", 1.0), ("Cracks", "NodeSocketFloat", 0.15),
                  ("Tire Wear", "NodeSocketFloat", 0.5), ("Lane Width", "NodeSocketFloat", 3.2), ("Lanes", "NodeSocketFloat", 2.0),
                  ("Edge Dirt", "NodeSocketFloat", 0.4), ("Half Width", "NodeSocketFloat", 3.2), ("Slab Size", "NodeSocketFloat", 4.0),
                  ("Stone Size", "NodeSocketFloat", 0.13), ("Use UV", "NodeSocketFloat", 0.0), ("Tile Size", "NodeSocketFloat", 4.0))


def _build_asphalt():
    g = new_tree(MRS + "AsphaltShader", "ShaderNodeTree"); _inputs(g, ASPHALT_INPUTS)
    G = _G(g); I = G.gi.outputs; m = G.m
    # ---- surface-type weights (linear blend between neighbours)
    S = m("MINIMUM", m("MAXIMUM", I["Surface Type"], 0.0), 5.0)
    w = [m("MAXIMUM", m("SUBTRACT", 1.0, m("ABSOLUTE", m("SUBTRACT", S, float(k)))), 0.0) for k in range(6)]
    fam = m("ADD", m("ADD", w[0], w[1]), w[2])                                  # asphalt family weight

    # ---- shared fields
    broad = G.noise(0.09, 2.0, 0.5, label="broad tone")                        # ~11 m blotches (puddles, tone)
    mid = G.noise(1.3, 3.0, 0.55, label="mid tone")                            # ~0.8 m mottling
    fine = G.noise(45.0, 4.0, 0.65, label="fine grain")
    # aggregate: a packed mosaic of ~1 cm stones (voronoi cells) separated by thin dark bitumen seams; each stone
    # has its own shade (some vanish into the binder, some are pale) and a domed top; sparse 2.5 cm stones on top
    agg = G.voronoi(95.0, "F1", randomness=1.0, label="aggregate")
    agg_e = G.voronoi(95.0, "DISTANCE_TO_EDGE", randomness=1.0, label="aggregate seams")
    seam = G.ramp(agg_e.outputs["Distance"], 0.11, 0.035)                      # 1 in the seam between stones
    dome = G.ramp(agg.outputs["Distance"], 0.7, 0.1)
    asc = G.tb.n("ShaderNodeSeparateColor"); G.tb.link(agg.outputs["Color"], asc.inputs[0])
    stone_rand = asc.outputs[0]                                                # per-stone random 0..1
    stone = m("SUBTRACT", 1.0, seam)
    big = G.voronoi(38.0, "F1", randomness=1.0, label="big stones")
    bsc = G.tb.n("ShaderNodeSeparateColor"); G.tb.link(big.outputs["Color"], bsc.inputs[0])
    bigstone = m("MULTIPLY", G.ramp(big.outputs["Distance"], 0.42, 0.22), G.ramp(bsc.outputs[0], 0.72, 0.85))
    stone = m("MAXIMUM", stone, bigstone)
    stone_rand = G.mixf(bigstone, stone_rand, m("ADD", 0.5, m("MULTIPLY", bsc.outputs[1], 0.5)))
    dome = G.mixf(bigstone, dome, G.ramp(big.outputs["Distance"], 0.42, 0.0))
    sand = G.white(G.tb.vmath("SCALE", G.V, scale=128.0))                      # 128/m: 2 texels per grain in a 1024 px 4 m bake (no moire)
    tone = m("ADD", 1.0, m("MULTIPLY", m("SUBTRACT", broad, 0.5), m("MULTIPLY", I["Color Variation"], 2.4)))
    tone = m("MULTIPLY", tone, m("ADD", 0.88, m("MULTIPLY", mid, 0.24)))

    # ---- asphalt family: fresh (0) dark uniform bitumen, aged (1) grey with exposed stone, cracked (2) paler still
    light = m("DIVIDE", m("ADD", m("ADD", m("MULTIPLY", w[0], 0.5), m("MULTIPLY", w[1], 1.45)), m("MULTIPLY", w[2], 1.6)), m("MAXIMUM", fam, 1e-4))
    expose = m("DIVIDE", m("ADD", m("ADD", m("MULTIPLY", w[0], 0.12), m("MULTIPLY", w[1], 0.8)), m("MULTIPLY", w[2], 0.9)), m("MAXIMUM", fam, 1e-4))
    base = G.scale_col(I["Base Color"], m("MULTIPLY", tone, light))
    # stones: dark / mid / pale grey with the odd brownish one, shaded by the dome; the binder stays near Base Color
    stone_col = G.mixc(G.ramp(stone_rand, 0.15, 0.8), (0.09, 0.09, 0.085, 1), (0.34, 0.33, 0.31, 1))
    stone_col = G.mixc(G.ramp(stone_rand, 0.9, 1.0), stone_col, (0.3, 0.24, 0.18, 1))
    stone_col = G.scale_col(stone_col, m("MULTIPLY", m("ADD", 0.7, m("MULTIPLY", tone, 0.3)), m("ADD", 0.7, m("MULTIPLY", dome, 0.4))))
    stone_col = G.scale_col(stone_col, m("ADD", 0.85, m("MULTIPLY", sand, 0.3)))
    acol = G.mixc(m("MULTIPLY", stone, expose), base, stone_col)
    acol = G.scale_col(acol, m("ADD", 0.9, m("MULTIPLY", sand, 0.2)))
    # paver stripes on fresh asphalt (faint longitudinal sheen bands)
    stripes = G.noise(1.0, 2.0, 0.4, VW=G.stretch(4.0, 0.08))
    acol = G.scale_col(acol, m("ADD", 1.0, m("MULTIPLY", m("MULTIPLY", m("SUBTRACT", stripes, 0.5), 0.25), m("DIVIDE", w[0], m("MAXIMUM", fam, 1e-4)))))
    arough = m("ADD", m("SUBTRACT", I["Asphalt Roughness"], m("MULTIPLY", m("DIVIDE", w[0], m("MAXIMUM", fam, 1e-4)), 0.2)), m("MULTIPLY", m("SUBTRACT", fine, 0.5), 0.15))
    arough = m("ADD", arough, m("MULTIPLY", m("MULTIPLY", stone, dome), 0.06))
    ah = m("MULTIPLY", m("MULTIPLY", stone, m("ADD", 0.35, m("MULTIPLY", dome, 0.65))), m("ADD", 0.4, m("MULTIPLY", expose, 0.6)))
    ah = m("ADD", ah, m("ADD", m("MULTIPLY", fine, 0.2), m("MULTIPLY", sand, 0.08)))
    # repair patches: a random rectangle (saw-cut, road-aligned) in a fraction of 3.2 m cells, fresher darker
    # asphalt inside and a glossy tar seal band along the cut
    psz, pn = G.periodic(3.2)
    pix = G.wrap(m("FLOOR", m("DIVIDE", G.px, psz)), pn); piy = G.wrap(m("FLOOR", m("DIVIDE", G.py, psz)), pn)
    pfx = m("FRACT", m("DIVIDE", G.px, psz)); pfy = m("FRACT", m("DIVIDE", G.py, psz))
    pr = [G.white(G.tb.combine(pix, piy, float(k))) for k in range(5)]
    x0 = m("ADD", 0.04, m("MULTIPLY", pr[0], 0.45)); x1 = m("MINIMUM", m("ADD", x0, m("ADD", 0.2, m("MULTIPLY", pr[1], 0.5))), 0.96)
    y0 = m("ADD", 0.04, m("MULTIPLY", pr[2], 0.45)); y1 = m("MINIMUM", m("ADD", y0, m("ADD", 0.2, m("MULTIPLY", pr[3], 0.5))), 0.96)
    dmin = m("MULTIPLY", m("MINIMUM", m("MINIMUM", m("SUBTRACT", pfx, x0), m("SUBTRACT", x1, pfx)), m("MINIMUM", m("SUBTRACT", pfy, y0), m("SUBTRACT", y1, pfy))), psz)
    pamt = m("MULTIPLY", I["Patch Amount"], m("DIVIDE", m("ADD", m("ADD", m("MULTIPLY", w[0], 0.15), w[1]), m("MULTIPLY", w[2], 1.6)), m("MAXIMUM", fam, 1e-4)))
    p_on = G.ramp(pr[4], m("SUBTRACT", 1.0, pamt), m("SUBTRACT", 1.02, pamt))  # that fraction of the cells carries a patch
    patch = m("MULTIPLY", G.ramp(dmin, 0.0, 0.01), p_on)
    seal = m("MULTIPLY", m("MULTIPLY", G.ramp(m("ABSOLUTE", dmin), 0.045, 0.012), p_on), m("ADD", 0.6, m("MULTIPLY", mid, 0.4)))
    pcol = G.scale_col(I["Base Color"], m("MULTIPLY", 0.85, m("ADD", 0.8, m("MULTIPLY", mid, 0.4))))   # fresher, darker asphalt
    pcol = G.mixc(m("MULTIPLY", stone, 0.3), pcol, G.scale_col(stone_col, 0.6))
    acol = G.mixc(patch, acol, pcol); acol = G.mixc(seal, acol, (0.025, 0.025, 0.028, 1))
    arough = m("SUBTRACT", arough, m("ADD", m("MULTIPLY", patch, 0.12), m("MULTIPLY", seal, 0.35)))
    ah = m("ADD", m("MULTIPLY", ah, m("SUBTRACT", 1.0, m("MULTIPLY", patch, 0.4))), m("MULTIPLY", patch, 0.12))
    ah = m("SUBTRACT", ah, m("MULTIPLY", seal, 0.15))

    # ---- concrete road (3): pale, transverse joints every Slab Size (along y), per-slab tone, broom texture across
    slab, slab_n = G.periodic(I["Slab Size"])
    slab_i = G.wrap(m("FLOOR", m("DIVIDE", G.py, slab)), slab_n)
    slab_tone = m("ADD", 0.84, m("MULTIPLY", G.white(G.tb.combine(slab_i, 0.37, 0.0)), 0.32))
    jy = m("ABSOLUTE", m("SUBTRACT", m("FRACT", m("DIVIDE", G.py, slab)), 0.5))
    jdist = m("MULTIPLY", m("SUBTRACT", 0.5, jy), slab)                        # metres to the nearest transverse joint
    joint = G.ramp(jdist, 0.025, 0.008)                                        # ~2 cm sealed joint
    chamfer = G.ramp(jdist, 0.09, 0.01)
    broom = G.noise(40.0, 3.0, 0.6, VW=G.stretch(1.0, 0.03))                  # stretched across: brushed finish
    pores = G.ramp(G.voronoi(90.0, "F1", randomness=1.0).outputs["Distance"], 0.45, 0.18)   # ~3 mm air pits
    pores = m("MULTIPLY", pores, G.ramp(G.noise(2.0, 2.0, 0.5), 0.3, 0.7))
    cgrain = m("ADD", 0.72, m("MULTIPLY", m("ADD", fine, sand), 0.28))        # cement grain + sand speckle
    ccol = G.scale_col((0.24, 0.235, 0.22, 1), m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", tone, slab_tone), cgrain), m("ADD", 0.86, m("MULTIPLY", broom, 0.28))))
    ccol = G.mixc(m("MULTIPLY", pores, 0.6), ccol, (0.12, 0.115, 0.105, 1))
    ccol = G.mixc(m("MULTIPLY", chamfer, 0.6), ccol, (0.1, 0.1, 0.095, 1))
    ccol = G.mixc(joint, ccol, (0.03, 0.03, 0.03, 1))
    crough = m("ADD", m("ADD", 0.8, m("MULTIPLY", m("SUBTRACT", broom, 0.5), 0.14)), m("ADD", m("MULTIPLY", joint, 0.15), m("MULTIPLY", pores, 0.1)))
    ch = m("SUBTRACT", m("ADD", m("MULTIPLY", broom, 0.35), m("ADD", m("MULTIPLY", fine, 0.15), m("MULTIPLY", sand, 0.1))), m("ADD", m("MULTIPLY", chamfer, 0.6), m("MULTIPLY", pores, 0.45)))

    # ---- cobblestone (4): voronoi setts with mortar, per-stone tone, domed tops
    # setts laid in rows across the road: a brick grid (row offsets random, edges wobbled by noise), domed tops
    ssz, sn_ = G.periodic(I["Stone Size"])
    wobx = m("MULTIPLY", m("SUBTRACT", G.noise(9.0, 2.0, 0.5, label="sett wobble x"), 0.5), m("MULTIPLY", ssz, 0.3))
    woby = m("MULTIPLY", m("SUBTRACT", G.noise(9.0, 2.0, 0.5, VW=G.stretch(1.4, 0.8), label="sett wobble y"), 0.5), m("MULTIPLY", ssz, 0.3))
    gx = m("ADD", G.px, wobx); gy = m("ADD", G.py, woby)
    row = m("FLOOR", m("DIVIDE", gy, ssz)); rowp = G.wrap(row, sn_)
    roff = m("MULTIPLY", G.white(G.tb.combine(rowp, 0.123, 0.0)), ssz)
    ux = m("DIVIDE", m("ADD", gx, roff), ssz); fx = m("FRACT", ux); fy = m("FRACT", m("DIVIDE", gy, ssz))
    colp = G.wrap(m("FLOOR", ux), sn_)
    srand = G.white(G.tb.combine(colp, rowp, 0.0)); srand2 = G.white(G.tb.combine(rowp, colp, 7.0))
    edge = m("MULTIPLY", m("MINIMUM", m("MINIMUM", fx, m("SUBTRACT", 1.0, fx)), m("MINIMUM", fy, m("SUBTRACT", 1.0, fy))), ssz)
    sett = G.ramp(edge, 0.005, 0.016)                                          # 0 in the ~1 cm gap, 1 on the stone
    rr = m("ADD", m("POWER", m("SUBTRACT", fx, 0.5), 2.0), m("POWER", m("SUBTRACT", fy, 0.5), 2.0))
    dome = m("MULTIPLY", G.ramp(rr, 0.32, 0.02), sett)
    st_tone = m("ADD", 0.45, m("MULTIPLY", srand, 0.85))
    warm = G.ramp(srand2, 0.3, 0.8)
    scol = G.mixc(warm, (0.15, 0.15, 0.16, 1), (0.22, 0.17, 0.12, 1))
    scol = G.scale_col(scol, m("MULTIPLY", st_tone, m("ADD", 0.8, m("MULTIPLY", tone, 0.2))))
    scol = G.scale_col(scol, m("ADD", 0.75, m("MULTIPLY", fine, 0.5)))
    scol = G.scale_col(scol, m("ADD", 0.7, m("MULTIPLY", dome, 0.45)))                                      # worn, lighter tops
    scol = G.mixc(m("MULTIPLY", G.ramp(mid, 0.3, 0.75), 0.45), scol, (0.07, 0.08, 0.05, 1))                 # moss / dirt in low areas
    mcol = G.scale_col((0.08, 0.07, 0.06, 1), m("ADD", 0.6, m("MULTIPLY", fine, 0.8)))
    kcol = G.mixc(sett, mcol, scol)
    krough = G.mixf(sett, 0.95, m("SUBTRACT", 0.86, m("MULTIPLY", dome, 0.22)))
    kh = m("ADD", m("MULTIPLY", sett, m("ADD", 0.3, m("MULTIPLY", dome, 0.7))), m("MULTIPLY", fine, 0.05))

    # ---- dirt / gravel (5): tan-brown earth, pebbles, ruts come from the tire-wear tracks
    peb = G.voronoi(40.0, "F1", randomness=1.0, label="pebbles")
    psc = G.tb.n("ShaderNodeSeparateColor"); G.tb.link(peb.outputs["Color"], psc.inputs[0])
    pebble = G.ramp(peb.outputs["Distance"], 0.4, 0.18)
    pebgate = G.ramp(G.noise(0.8, 2.0, 0.5), 0.3, 0.7)
    pebble = m("MULTIPLY", pebble, m("MULTIPLY", pebgate, G.ramp(psc.outputs[0], 0.35, 0.5)))      # not every cell is a stone
    pebcol = G.mixc(psc.outputs[1], (0.1, 0.085, 0.07, 1), (0.2, 0.18, 0.15, 1))                   # dark to light grey-brown stones
    crust = G.ramp(G.noise(0.6, 3.0, 0.55), 0.35, 0.7)                                             # dry pale crust vs damp earth
    dcol = G.mixc(crust, (0.11, 0.07, 0.035, 1), (0.25, 0.18, 0.095, 1))
    dcol = G.scale_col(dcol, m("MULTIPLY", tone, m("ADD", 0.65, m("MULTIPLY", m("ADD", fine, m("MULTIPLY", sand, 0.5)), 0.45))))
    dcol = G.mixc(m("MULTIPLY", G.ramp(mid, 0.6, 0.85), 0.5), dcol, (0.07, 0.05, 0.035, 1))        # damp dark hollows
    dcol = G.mixc(m("MULTIPLY", pebble, 0.7), dcol, pebcol)
    drough = m("SUBTRACT", 0.97, m("MULTIPLY", pebble, 0.12))
    dh = m("ADD", m("ADD", m("MULTIPLY", pebble, 0.3), m("MULTIPLY", G.noise(4.0, 4.0, 0.6), 0.4)), m("ADD", m("MULTIPLY", fine, 0.2), m("MULTIPLY", sand, 0.1)))

    # ---- blend the types
    def blend(parts, amp):
        out = None
        for k, part in parts:
            term = G.tb.vmath("SCALE", part, scale=m("MULTIPLY", w[k], amp[k])) if amp else G.tb.vmath("SCALE", part, scale=w[k])
            out = term if out is None else G.tb.vmath("ADD", out, term)
        return out
    col = blend([(0, acol), (1, acol), (2, acol), (3, ccol), (4, kcol), (5, dcol)], None)
    rough = G.tb.separate(blend([(0, G.gray(arough)), (1, G.gray(arough)), (2, G.gray(arough)), (3, G.gray(crough)), (4, G.gray(krough)), (5, G.gray(drough))], None))[0]
    height = G.tb.separate(blend([(0, G.gray(ah)), (1, G.gray(ah)), (2, G.gray(ah)), (3, G.gray(ch)), (4, G.gray(kh)), (5, G.gray(dh))],
                                 [0.7, 1.0, 1.1, 0.8, 5.0, 2.2]))[0]

    # ---- cracks: wiggly voronoi edges gated by noise, plus a finer alligator net at high amounts
    camt = m("MINIMUM", m("ADD", I["Cracks"], m("ADD", m("MULTIPLY", w[2], 0.85), m("MULTIPLY", w[1], 0.15))), 1.0)
    camt = m("MULTIPLY", camt, m("ADD", fam, w[3]))
    wig = G.noise(6.0, 3.0, 0.6)
    Vc = G.tb.vmath("ADD", G.V, G.tb.vmath("SCALE", G.tb.combine(wig, m("MULTIPLY", wig, 0.7), 0.0), scale=0.12))
    cr1 = G.voronoi(0.55, "DISTANCE_TO_EDGE", randomness=1.0, VW=(Vc, G.W), label="cracks")
    cr2 = G.voronoi(2.8, "DISTANCE_TO_EDGE", randomness=1.0, VW=(Vc, G.W), label="alligator")
    cgate = G.noise(0.35, 2.0, 0.5, label="crack gate")
    thr1 = m("SUBTRACT", 0.72, m("MULTIPLY", camt, 0.55)); thr2 = m("SUBTRACT", 0.8, m("MULTIPLY", camt, 0.5))
    g1 = G.ramp(cgate, thr1, m("ADD", thr1, 0.08)); g2 = G.ramp(cgate, thr2, m("ADD", thr2, 0.08))   # cracked where the gate is high
    cw = m("ADD", 0.5, m("MULTIPLY", G.noise(3.0, 2.0, 0.5), 1.0))             # crack width varies along the crack
    line1 = m("MULTIPLY", G.ramp(cr1.outputs["Distance"], m("MULTIPLY", 0.009, cw), m("MULTIPLY", 0.002, cw)), g1)
    line2 = m("MULTIPLY", G.ramp(cr2.outputs["Distance"], m("MULTIPLY", 0.016, cw), m("MULTIPLY", 0.004, cw)), g2)
    crack = m("MINIMUM", m("ADD", line1, m("MULTIPLY", line2, 0.85)), 1.0)
    crack_soft = m("MULTIPLY", G.ramp(cr1.outputs["Distance"], 0.035, 0.006), m("MULTIPLY", g1, 0.5))                    # darker halo
    col = G.mixc(m("MULTIPLY", crack_soft, 0.4), col, (0.03, 0.03, 0.032, 1))
    col = G.mixc(crack, col, (0.012, 0.012, 0.014, 1))
    rough = m("ADD", rough, m("MULTIPLY", crack, 0.1))
    height = m("SUBTRACT", height, m("MULTIPLY", crack, 0.8))

    # ---- tire wear: two tracks per lane at +-0.8 m of each lane centre (lat attribute)
    lat = G.attr("lat")
    u = m("DIVIDE", m("ADD", lat, m("MULTIPLY", I["Lanes"], m("MULTIPLY", I["Lane Width"], 0.5))), I["Lane Width"])
    d = m("MULTIPLY", m("ABSOLUTE", m("SUBTRACT", m("FRACT", u), 0.5)), I["Lane Width"])
    wander = m("MULTIPLY", m("SUBTRACT", G.noise(0.15, 2.0, 0.5, VW=G.stretch(1.0, 0.3)), 0.5), 0.3)     # tracks drift a little
    track = G.ramp(m("ABSOLUTE", m("SUBTRACT", m("ADD", d, wander), 0.8)), 0.3, 0.06)
    inroad = G.ramp(m("ABSOLUTE", lat), m("ADD", m("MULTIPLY", I["Lanes"], m("MULTIPLY", I["Lane Width"], 0.5)), 0.1), m("MULTIPLY", I["Lanes"], m("MULTIPLY", I["Lane Width"], 0.5)))
    tstreak = G.ramp(G.noise(2.0, 3.0, 0.5, VW=G.stretch(3.0, 0.12)), 0.3, 0.75)
    tire = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", track, inroad), m("ADD", 0.3, m("MULTIPLY", tstreak, 0.7))), m("MULTIPLY", I["Tire Wear"], G.keep))
    tire = m("MULTIPLY", tire, m("ADD", m("ADD", fam, w[3]), m("ADD", m("MULTIPLY", w[4], 0.4), w[5])))
    col = G.mixc(m("MULTIPLY", tire, m("ADD", 0.5, m("MULTIPLY", w[5], 0.3))), col, G.mixc(w[5], (0.012, 0.012, 0.014, 1), (0.07, 0.055, 0.04, 1)))
    rough = m("SUBTRACT", rough, m("MULTIPLY", tire, 0.25))
    height = m("SUBTRACT", m("MULTIPLY", height, m("SUBTRACT", 1.0, m("MULTIPLY", tire, 0.35))), m("MULTIPLY", tire, m("MULTIPLY", w[5], 1.5)))

    # ---- edge dirt: sandy grit band toward the pavement edge
    eband = G.ramp(m("ABSOLUTE", lat), m("SUBTRACT", I["Half Width"], 1.1), m("SUBTRACT", I["Half Width"], 0.15))
    ebreak = G.noise(1.5, 3.0, 0.55, VW=G.stretch(2.5, 0.3))
    edge = m("MULTIPLY", m("MULTIPLY", eband, m("ADD", 0.35, m("MULTIPLY", G.ramp(ebreak, 0.3, 0.75), 0.9))), m("MULTIPLY", I["Edge Dirt"], G.keep))
    edge = m("MINIMUM", edge, 1.0)
    grit = G.ramp(G.voronoi(55.0, "F1").outputs["Distance"], 0.4, 0.15)
    ecol = G.scale_col((0.19, 0.16, 0.12, 1), m("ADD", 0.7, m("MULTIPLY", m("ADD", grit, sand), 0.35)))
    col = G.mixc(m("MULTIPLY", edge, 0.8), col, ecol)
    rough = m("ADD", rough, m("MULTIPLY", edge, 0.12))
    height = m("ADD", height, m("MULTIPLY", edge, m("MULTIPLY", grit, 0.4)))

    # ---- wetness
    col, rough, fade, coat = G.wet(col, rough, height, I["Wetness"], broad)
    G.finish(col, rough, height, I["Bump Strength"], 0.012, coat=coat, bump_fade=fade)
    return g


# ============================================================================== paint
PAINT_INPUTS = (("Paint Color", "NodeSocketColor", (0.85, 0.85, 0.8, 1)), ("Paint Wear", "NodeSocketFloat", 0.35), ("Asphalt Scale", "NodeSocketFloat", 1.0),
                ("Wetness", "NodeSocketFloat", 0.0), ("Bump Strength", "NodeSocketFloat", 0.3), ("Yellow", "NodeSocketFloat", 0.0),
                ("Sparkle", "NodeSocketFloat", 0.6), ("Chipping", "NodeSocketFloat", 0.5), ("Use UV", "NodeSocketFloat", 0.0), ("Tile Size", "NodeSocketFloat", 4.0))


def _build_paint():
    g = new_tree(MRS + "PaintShader", "ShaderNodeTree"); _inputs(g, PAINT_INPUTS)
    G = _G(g); I = G.gi.outputs; m = G.m
    broad = G.noise(0.09, 2.0, 0.5, label="broad tone")                        # same field as the asphalt: puddles coincide
    mid = G.noise(1.3, 3.0, 0.55)
    fine = G.noise(45.0, 4.0, 0.65)
    agg = G.voronoi(95.0, "F1", randomness=1.0, label="aggregate")
    stone = G.ramp(agg.outputs["Distance"], 0.62, 0.12)
    sand = G.white(G.tb.vmath("SCALE", G.V, scale=420.0))
    # the asphalt under the paint
    under = G.scale_col((0.09, 0.09, 0.095, 1), m("MULTIPLY", m("ADD", 0.7, m("MULTIPLY", broad, 0.6)), m("ADD", 0.85, m("MULTIPLY", sand, 0.3))))
    under = G.mixc(m("MULTIPLY", stone, 0.6), under, (0.3, 0.29, 0.27, 1))
    # wear: paint goes first from the stone tops (aggregate), driven by mid-scale wear noise and tire-track scuffing
    wearn = G.noise(2.2, 5.0, 0.65, label="wear")
    wamt = I["Paint Wear"]
    thin = m("MULTIPLY", G.ramp(wearn, m("SUBTRACT", 0.9, m("MULTIPLY", wamt, 0.9)), m("SUBTRACT", 1.25, m("MULTIPLY", wamt, 0.9))), 1.0)
    on_stone = m("MULTIPLY", thin, m("ADD", 0.35, m("MULTIPLY", stone, 0.9)))
    # chipped edges: small cells removed where the wear noise is high
    chips = G.voronoi(38.0, "F1", randomness=1.0, label="chips")
    chip = m("MULTIPLY", G.ramp(chips.outputs["Distance"], 0.5, 0.35), G.ramp(wearn, m("SUBTRACT", 0.95, m("MULTIPLY", wamt, 0.75)), m("SUBTRACT", 1.1, m("MULTIPLY", wamt, 0.75))))
    chip = m("MULTIPLY", chip, I["Chipping"])
    wear = m("MINIMUM", m("ADD", on_stone, chip), 1.0, clamp=True)
    wear = m("MAXIMUM", wear, m("MULTIPLY", G.ramp(wamt, 0.85, 1.0), 0.9))     # Paint Wear 1 = almost gone
    # colour: white -> yellow, dirtied by the mid noise, glass-bead sparkle
    yellow = G.mixc(I["Yellow"], I["Paint Color"], (0.82, 0.58, 0.08, 1))
    dirt = m("MULTIPLY", G.ramp(mid, 0.3, 0.8), m("ADD", 0.1, m("MULTIPLY", wamt, 0.4)))
    pcol = G.scale_col(yellow, m("SUBTRACT", 1.0, m("MULTIPLY", dirt, 0.35)))
    pcol = G.scale_col(pcol, m("ADD", 0.9, m("MULTIPLY", sand, 0.2)))
    col = G.mixc(wear, pcol, under)
    bead = G.white(G.tb.vmath("SCALE", G.V, scale=900.0))
    sparkle = m("MULTIPLY", G.ramp(bead, 0.8, 0.98), I["Sparkle"])
    rough = G.lerp(wear, m("ADD", 0.5, m("MULTIPLY", m("SUBTRACT", fine, 0.5), 0.15)), 0.88)
    rough = m("SUBTRACT", rough, m("MULTIPLY", sparkle, 0.45))
    height = m("ADD", m("MULTIPLY", m("SUBTRACT", 1.0, wear), 0.55), m("ADD", m("MULTIPLY", stone, 0.35), m("MULTIPLY", sand, 0.1)))
    col, rough, fade, coat = G.wet(col, rough, height, I["Wetness"], broad)
    G.finish(col, rough, height, I["Bump Strength"], 0.006, coat=coat, bump_fade=fade)
    return g


# ============================================================================== concrete
CONCRETE_INPUTS = (("Concrete Variation", "NodeSocketFloat", 0.2), ("Asphalt Scale", "NodeSocketFloat", 1.0), ("Wetness", "NodeSocketFloat", 0.0),
                   ("Base Color", "NodeSocketColor", (0.42, 0.41, 0.39, 1)), ("Slab Size", "NodeSocketFloat", 2.0), ("Bump Strength", "NodeSocketFloat", 0.35),
                   ("Rust Streaks", "NodeSocketFloat", 0.0), ("Grime", "NodeSocketFloat", 0.0), ("Grime Height", "NodeSocketFloat", 0.8),
                   ("Use UV", "NodeSocketFloat", 0.0), ("Tile Size", "NodeSocketFloat", 4.0))


def _build_concrete():
    g = new_tree(MRS + "ConcreteShader", "ShaderNodeTree"); _inputs(g, CONCRETE_INPUTS)
    G = _G(g); I = G.gi.outputs; m = G.m
    broad = G.noise(0.3, 3.0, 0.5, label="broad")
    mid = G.noise(2.5, 3.0, 0.55, label="mid")
    fine = G.noise(60.0, 5.0, 0.7, label="fine")
    trowel = G.noise(5.0, 2.0, 0.45, VW=G.stretch(0.25, 1.0), label="trowel")
    pores = G.ramp(G.voronoi(110.0, "F1", randomness=1.0, label="pores").outputs["Distance"], 0.42, 0.16)   # ~2.5 mm air pits
    pores = m("MULTIPLY", pores, G.ramp(G.noise(3.0, 2.0, 0.5), 0.35, 0.65))
    sand = G.white(G.tb.vmath("SCALE", G.V, scale=380.0))
    # slabs: joints every Slab Size in x and y, chamfered edges, per-slab tone
    # slab joints along the two axes the face lies in (a wall gets horizontal joints in z, a floor x and y)
    slab, slab_n = G.periodic(I["Slab Size"])
    geo = G.tb.n("ShaderNodeNewGeometry"); nx, ny, nz = G.tb.separate(geo.outputs["Normal"])
    def axis(p, ncomp):
        f = m("FRACT", m("DIVIDE", p, slab))
        dist = m("MULTIPLY", m("MINIMUM", f, m("SUBTRACT", 1.0, f)), slab)          # metres to the nearest joint
        dist = G.mixf(G.ramp(m("ABSOLUTE", ncomp), 0.5, 0.75), dist, 1000.0)       # not along the face normal
        return dist, G.wrap(m("FLOOR", m("DIVIDE", p, slab)), slab_n)
    dx, ix = axis(G.px, nx); dy, iy = axis(G.py, ny); dz, iz = axis(G.objz, nz)
    dj = m("MINIMUM", m("MINIMUM", dx, dy), dz)
    joint = G.ramp(dj, 0.01, 0.003); chamfer = G.ramp(dj, 0.04, 0.006)
    slab_tone = m("ADD", 0.9, m("MULTIPLY", G.white(G.tb.combine(ix, iy, iz)), m("MULTIPLY", I["Concrete Variation"], 1.0)))
    tone = m("ADD", 1.0, m("MULTIPLY", m("SUBTRACT", broad, 0.5), m("MULTIPLY", I["Concrete Variation"], 2.2)))
    tone = m("MULTIPLY", m("MULTIPLY", tone, slab_tone), m("ADD", 0.92, m("MULTIPLY", mid, 0.16)))
    tone = m("MULTIPLY", tone, m("ADD", 0.94, m("MULTIPLY", trowel, 0.12)))
    col = G.scale_col(I["Base Color"], m("MULTIPLY", tone, m("ADD", 0.8, m("MULTIPLY", m("ADD", sand, fine), 0.2))))
    col = G.mixc(m("MULTIPLY", pores, 0.6), col, (0.14, 0.135, 0.125, 1))
    col = G.mixc(joint, col, (0.06, 0.06, 0.06, 1))
    col = G.mixc(m("MULTIPLY", chamfer, 0.25), col, (0.3, 0.3, 0.29, 1))
    rough = m("ADD", 0.82, m("MULTIPLY", m("SUBTRACT", fine, 0.5), 0.14))
    rough = m("ADD", rough, m("MULTIPLY", pores, 0.1))
    height = m("ADD", m("ADD", m("MULTIPLY", fine, 0.3), m("MULTIPLY", trowel, 0.35)), m("MULTIPLY", sand, 0.1))
    height = m("SUBTRACT", height, m("ADD", m("MULTIPLY", chamfer, 0.6), m("MULTIPLY", pores, 0.35)))
    # rust streaks: vertical (object Z) streaks hanging from random spots
    z = G.objz
    sv = G.tb.combine(m("MULTIPLY", G.px, 7.0), m("MULTIPLY", G.py, 7.0), m("MULTIPLY", z, 0.35))
    sn = G.tb.n("ShaderNodeTexNoise", "streaks", noise_dimensions="3D"); G.tb.inp(sn, "Vector", sv); G.tb.inp(sn, "Scale", 1.0); G.tb.inp(sn, "Detail", 3.0); G.tb.inp(sn, "Roughness", 0.5)
    sgate = G.tb.n("ShaderNodeTexNoise", "streak gate", noise_dimensions="3D"); G.tb.inp(sgate, "Vector", G.tb.combine(G.px, G.py, m("MULTIPLY", z, 0.15))); G.tb.inp(sgate, "Scale", 1.6); G.tb.inp(sgate, "Detail", 2.0)
    streak = m("MULTIPLY", G.ramp(sn.outputs["Fac"], 0.48, 0.66), G.ramp(sgate.outputs["Fac"], m("SUBTRACT", 0.78, m("MULTIPLY", I["Rust Streaks"], 0.45)), m("SUBTRACT", 0.9, m("MULTIPLY", I["Rust Streaks"], 0.45))))
    hang = G.ramp(m("MULTIPLY", m("SUBTRACT", 1.0, m("FRACT", m("DIVIDE", z, slab))), slab), 1.0, 0.0)      # strongest just below a horizontal joint
    streak = m("MULTIPLY", streak, m("ADD", 0.35, m("MULTIPLY", hang, 0.65)))
    streak = m("MULTIPLY", m("MULTIPLY", streak, m("MINIMUM", m("MULTIPLY", I["Rust Streaks"], 1.6), 1.0)), G.keep)
    rust_col = G.mixc(G.ramp(fine, 0.3, 0.7), (0.3, 0.1, 0.03, 1), (0.5, 0.24, 0.07, 1))
    col = G.mixc(m("MULTIPLY", streak, 0.9), col, rust_col)
    rough = m("ADD", rough, m("MULTIPLY", streak, 0.1))
    # grime / moss at the base (object Z near 0) with streaks along the road
    along = G.attr("along")
    gband = G.ramp(z, I["Grime Height"], 0.0)
    gblotch = G.noise(2.0, 5.0, 0.65)
    # vertical streaks: fast across (x / along), slow in z
    gstreak = G.tb.n("ShaderNodeTexNoise", "grime streaks", noise_dimensions="3D"); G.tb.inp(gstreak, "Vector", G.tb.combine(m("MULTIPLY", m("ADD", G.px, along), 6.0), m("MULTIPLY", G.py, 6.0), m("MULTIPLY", z, 0.4))); G.tb.inp(gstreak, "Scale", 1.0); G.tb.inp(gstreak, "Detail", 3.0)
    grime = m("MULTIPLY", gband, m("ADD", m("ADD", 0.3, m("MULTIPLY", G.ramp(gblotch, 0.35, 0.75), 0.35)), m("MULTIPLY", G.ramp(gstreak.outputs["Fac"], 0.4, 0.75), 0.45)))
    grime = m("ADD", grime, m("MULTIPLY", G.ramp(z, 0.35, 0.0), 0.35))        # splash zone right at the base
    grime = m("MINIMUM", m("MULTIPLY", m("MULTIPLY", grime, m("MULTIPLY", I["Grime"], 1.5)), G.keep), 1.0)
    moss = G.ramp(gblotch, 0.55, 0.8)
    gcol = G.mixc(moss, (0.06, 0.06, 0.055, 1), (0.08, 0.13, 0.04, 1))
    col = G.mixc(m("MULTIPLY", grime, 0.85), col, gcol)
    rough = m("ADD", rough, m("MULTIPLY", grime, 0.1))
    col, rough, fade, coat = G.wet(col, rough, height, I["Wetness"], broad)
    G.finish(col, rough, height, I["Bump Strength"], 0.012, coat=coat, bump_fade=fade)
    return g


# ============================================================================== embankment
EMBANKMENT_INPUTS = (("Grass Color", "NodeSocketColor", (0.16, 0.24, 0.07, 1)), ("Dirt Color", "NodeSocketColor", (0.27, 0.2, 0.12, 1)),
                     ("Rockiness", "NodeSocketFloat", 0.35), ("Asphalt Scale", "NodeSocketFloat", 1.0), ("Wetness", "NodeSocketFloat", 0.0),
                     ("Bump Strength", "NodeSocketFloat", 0.5), ("Slope Override", "NodeSocketFloat", -1.0),
                     ("Use UV", "NodeSocketFloat", 0.0), ("Tile Size", "NodeSocketFloat", 4.0))


def _build_embankment():
    g = new_tree(MRS + "EmbankmentShader", "ShaderNodeTree"); _inputs(g, EMBANKMENT_INPUTS)
    G = _G(g); I = G.gi.outputs; m = G.m
    geo = G.tb.n("ShaderNodeNewGeometry"); nz = G.tb.separate(geo.outputs["Normal"])[2]
    steep_n = G.ramp(nz, 0.96, 0.78)                                             # 0 flat, 1 steep (about 16 to 39 degrees)
    use_ov = m("GREATER_THAN", I["Slope Override"], -0.5)
    steep = G.mixf(use_ov, steep_n, m("MINIMUM", m("MAXIMUM", I["Slope Override"], 0.0), 1.0))
    broad = G.noise(0.2, 3.0, 0.5, label="broad")
    mid = G.noise(1.5, 4.0, 0.6, label="mid")
    fine = G.noise(30.0, 6.0, 0.7, label="fine")
    blades = G.noise(70.0, 3.0, 0.6, VW=G.stretch(1.0, 0.25), label="blades")
    steep = m("MINIMUM", m("MAXIMUM", m("ADD", steep, m("MULTIPLY", m("SUBTRACT", mid, 0.5), 0.6)), 0.0), 1.0)
    # grass: two greens, dry patches, blade-scale brightness flicker
    g2 = G.scale_col(I["Grass Color"], 1.6); g2 = G.mixc(0.4, g2, (0.42, 0.42, 0.14, 1))
    grass = G.mixc(G.ramp(mid, 0.3, 0.75), I["Grass Color"], g2)
    grass = G.scale_col(grass, m("MULTIPLY", m("ADD", 0.75, m("MULTIPLY", broad, 0.5)), m("ADD", 0.65, m("MULTIPLY", blades, 0.7))))
    grass = G.mixc(m("MULTIPLY", G.ramp(fine, 0.6, 0.9), 0.5), grass, (0.05, 0.07, 0.02, 1))
    # dirt with pebbles
    peb = G.ramp(G.voronoi(35.0, "F1").outputs["Distance"], 0.4, 0.2)
    dirt = G.scale_col(I["Dirt Color"], m("MULTIPLY", m("ADD", 0.7, m("MULTIPLY", broad, 0.6)), m("ADD", 0.7, m("MULTIPLY", fine, 0.6))))
    dirt = G.mixc(m("MULTIPLY", peb, 0.5), dirt, (0.24, 0.22, 0.19, 1))
    # rock: big voronoi faces where it is steep and rocky
    rk = G.voronoi(1.6, "F1", randomness=0.9, label="rock cells")
    rke = G.voronoi(1.6, "DISTANCE_TO_EDGE", randomness=0.9)
    rock_face = G.ramp(rke.outputs["Distance"], 0.02, 0.12)
    rsc = G.tb.n("ShaderNodeSeparateColor"); G.tb.link(rk.outputs["Color"], rsc.inputs[0])
    rock = G.scale_col((0.36, 0.34, 0.31, 1), m("MULTIPLY", m("ADD", 0.7, m("MULTIPLY", rsc.outputs[0], 0.6)), m("ADD", 0.75, m("MULTIPLY", fine, 0.5))))
    rock = G.mixc(m("MULTIPLY", G.ramp(mid, 0.5, 0.8), 0.5), rock, (0.12, 0.14, 0.09, 1))
    rock = G.mixc(m("SUBTRACT", 1.0, rock_face), rock, (0.1, 0.09, 0.08, 1))
    rgate = G.ramp(G.noise(0.5, 2.0, 0.5), m("SUBTRACT", 0.9, I["Rockiness"]), m("SUBTRACT", 1.0, I["Rockiness"]))   # Rockiness 0.35: ~a third of the steep area
    rockm = m("MULTIPLY", m("MULTIPLY", G.ramp(steep, 0.35, 0.8), rgate), G.ramp(I["Rockiness"], 0.0, 0.2))
    col = G.mixc(steep, grass, dirt)
    col = G.mixc(rockm, col, rock)
    rough = G.lerp(steep, 0.9, 0.95); rough = G.lerp(rockm, rough, m("ADD", 0.7, m("MULTIPLY", fine, 0.15)))
    h_grass = m("ADD", m("MULTIPLY", blades, 0.5), m("MULTIPLY", mid, 0.3))
    h_dirt = m("ADD", m("MULTIPLY", peb, 0.6), m("MULTIPLY", fine, 0.3))
    h_rock = m("ADD", m("MULTIPLY", rock_face, 2.0), m("MULTIPLY", fine, 0.4))
    height = G.lerp(rockm, G.lerp(steep, h_grass, h_dirt), h_rock)
    col, rough, fade, coat = G.wet(col, rough, height, I["Wetness"], broad)
    G.finish(col, rough, height, I["Bump Strength"], 0.03, coat=m("MULTIPLY", coat, 0.3), bump_fade=fade)
    return g


# ============================================================================== public API
def build_materials():
    """MRS_Asphalt, MRS_Paint, MRS_Concrete on the editable shader groups (one "MRS" group node each)."""
    _build_asphalt(); _build_paint(); _build_concrete(); _build_embankment()
    mats = {}
    for name, grp in (("Asphalt", "AsphaltShader"), ("Paint", "PaintShader"), ("Concrete", "ConcreteShader")):
        mats[name] = _group_material(name, grp)
    mats["Asphalt"].diffuse_color = (0.12, 0.12, 0.13, 1); mats["Paint"].diffuse_color = (0.85, 0.85, 0.8, 1); mats["Concrete"].diffuse_color = (0.5, 0.5, 0.48, 1)
    return mats


def extra_materials():
    """Bike lane (tinted fresh asphalt), structure concrete (rust + grime) and the slope-driven embankment."""
    for grp in ("AsphaltShader", "ConcreteShader", "EmbankmentShader"):
        if MRS + grp not in bpy.data.node_groups: build_materials(); break
    bike = _group_material("BikeLane", "AsphaltShader", **{"Base Color": (0.34, 0.09, 0.06, 1), "Patch Amount": 0.0, "Surface Type": 0.0, "Cracks": 0.0,
                                                           "Tire Wear": 0.15, "Edge Dirt": 0.25, "Asphalt Roughness": 0.8})
    bike.diffuse_color = (0.32, 0.08, 0.06, 1)
    struct = _group_material("Structure", "ConcreteShader", **{"Concrete Variation": 0.3, "Slab Size": 3.0, "Rust Streaks": 0.5, "Grime": 0.5, "Grime Height": 1.2})
    struct.diffuse_color = (0.5, 0.5, 0.48, 1)
    emb = _group_material("Embankment", "EmbankmentShader"); emb.diffuse_color = (0.18, 0.2, 0.08, 1)
    return bike, struct, emb


def mrs_nodes():
    """[(material, group node)] for the six MRS materials that exist."""
    out = []
    for suffix in MATERIAL_NAMES:
        mat = bpy.data.materials.get(MRS + suffix)
        node = mat.node_tree.nodes.get("MRS") if mat and mat.node_tree else None
        if node: out.append((mat, node))
    return out


def apply_material_preset(name):
    """Set every input the preset names on every "MRS" group node (only inputs that exist on that group)."""
    preset = MATERIAL_PRESETS[name]
    overrides = preset.get("overrides", {})
    for mat, node in mrs_nodes():
        suffix = mat.name[len(MRS):]
        vals = {k: v for k, v in preset.items() if k != "overrides"}
        vals.update(overrides.get(suffix, {}))
        for k, v in vals.items():
            s = node.inputs.get(k)
            if s is None: continue
            try: s.default_value = v
            except (TypeError, ValueError): pass


# ============================================================================== baking
def _cycles_gpu(scene):
    try: scene.render.engine = "CYCLES"
    except TypeError: return False
    try:
        cp = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                cp.compute_device_type = dev; cp.get_devices()
            except TypeError:
                continue
            if any(d.type == dev for d in cp.devices):
                for d in cp.devices: d.use = d.type in (dev, "CPU")
                scene.cycles.device = "GPU"; return True
    except Exception:
        pass
    scene.cycles.device = "CPU"; return False


def bake_tiles(out_dir, res=2048, samples=16, tile=4.0, materials=MATERIAL_NAMES):
    """Bake every MRS material to seamless albedo / normal / roughness PNGs (<material>_albedo.png ...).
    A tile x tile metre plane with UVs 0-1 carries the material with "Use UV" = 1, so the groups sample
    a 4D torus and the tiles repeat. Cycles, GPU when available. Returns {material: {map: path}}."""
    out_dir = os.path.abspath(out_dir); os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    prev = (scene.render.engine, scene.camera)
    gpu = _cycles_gpu(scene)
    scene.cycles.samples = samples; scene.cycles.use_denoising = False
    bk = scene.render.bake; bk.margin = 16; bk.use_selected_to_active = False; bk.use_clear = True
    # plane with UVs 0..1 (object space offset so it sits away from the demo scene)
    me = bpy.data.meshes.new(MRS + "BakePlane")
    me.from_pydata([(-tile / 2, -tile / 2, 0), (tile / 2, -tile / 2, 0), (tile / 2, tile / 2, 0), (-tile / 2, tile / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))): uv.data[i].uv = co
    me.update()
    ob = bpy.data.objects.new(MRS + "BakePlane", me); scene.collection.objects.link(ob); ob.location = (0, 0, -500)
    for o in scene.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    result = {}
    try:
        for suffix in materials:
            mat = bpy.data.materials.get(MRS + suffix)
            if mat is None: continue
            node = mat.node_tree.nodes.get("MRS")
            saved = {k: node.inputs[k].default_value for k in ("Use UV", "Tile Size") if k in node.inputs}
            node.inputs["Use UV"].default_value = 1.0; node.inputs["Tile Size"].default_value = tile
            me.materials.clear(); me.materials.append(mat)
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage"); tex.name = "MRS_BakeTarget"; mat.node_tree.nodes.active = tex
            paths = {}
            for key, btype, srgb, extra in (("albedo", "DIFFUSE", True, {"pass_filter": {"COLOR"}}), ("normal", "NORMAL", False, {"normal_space": "TANGENT"}), ("roughness", "ROUGHNESS", False, {})):
                img_name = "%s_%s" % (mat.name, key)
                im = bpy.data.images.get(img_name)
                if im is not None: bpy.data.images.remove(im)
                im = bpy.data.images.new(img_name, res, res, alpha=False, float_buffer=False)
                im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
                if not srgb: im.generated_color = (0.5, 0.5, 1.0, 1.0) if key == "normal" else (0.5, 0.5, 0.5, 1.0)
                tex.image = im
                bpy.ops.object.bake(type=btype, margin=16, **extra)
                p = os.path.join(out_dir, "%s_%s.png" % (mat.name, key))
                im.filepath_raw = p; im.file_format = "PNG"; im.save()
                paths[key] = p
            mat.node_tree.nodes.remove(tex)
            for k, v in saved.items(): node.inputs[k].default_value = v
            result[mat.name] = paths
            print("BAKED", mat.name, res, "px", "GPU" if gpu else "CPU", {k: os.path.basename(v) for k, v in paths.items()})
    finally:
        bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
        try: scene.render.engine = prev[0]
        except TypeError: pass
        scene.camera = prev[1]
    return result


def baked_material(name, paths, repeat=1.0):
    """A plain image-textured material from `bake_tiles` output (for seam checks / Godot-like preview)."""
    m = _mat(name); nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (repeat, repeat, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    for i, (key, cs) in enumerate((("albedo", "sRGB"), ("normal", "Non-Color"), ("roughness", "Non-Color"))):
        t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-400, -300 * i)
        t.image = bpy.data.images.load(paths[key], check_existing=True); t.image.colorspace_settings.name = cs
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
        if key == "albedo": nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        elif key == "roughness": nt.links.new(t.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(t.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return m


# ============================================================================== the road group
INPUTS = [  # (name, socket type, default, min, max, description)
    ("Lanes", "NodeSocketInt", 2, 1, 8, "Number of traffic lanes"),
    ("Lane Width", "NodeSocketFloat", 3.2, 2.0, 6.0, "Width of one lane (m)"),
    ("Shoulder", "NodeSocketFloat", 0.0, 0.0, 3.0, "Paved shoulder each side (m)"),
    ("Median", "NodeSocketFloat", 0.0, 0.0, 6.0, "Raised median width (0 = none)"),
    ("Sidewalk Left", "NodeSocketBool", True, None, None, ""), ("Sidewalk Right", "NodeSocketBool", True, None, None, ""),
    ("Sidewalk Width Left", "NodeSocketFloat", 2.0, 0.5, 8.0, ""), ("Sidewalk Width Right", "NodeSocketFloat", 2.0, 0.5, 8.0, ""),
    ("Sidewalk Height", "NodeSocketFloat", 0.15, 0.05, 0.3, "Curb / sidewalk height (m)"),
    ("Curb Width", "NodeSocketFloat", 0.25, 0.1, 0.6, "Curb stone width (m)"),
    ("Resolution", "NodeSocketFloat", 1.0, 0.2, 10.0, "Curve sampling step (m)"),
    ("Centre Line", "NodeSocketInt", 2, 0, 3, "0 none, 1 solid, 2 dashed, 3 double solid"),
    ("Lane Lines", "NodeSocketBool", True, None, None, "Dashed lines between lanes"),
    ("Edge Lines", "NodeSocketBool", False, None, None, "Solid edge lines"),
    ("Marking Width", "NodeSocketFloat", 0.12, 0.05, 0.4, ""), ("Dash Length", "NodeSocketFloat", 3.0, 0.3, 12.0, ""), ("Dash Gap", "NodeSocketFloat", 6.0, 0.3, 20.0, ""),
    ("Marking Material", "NodeSocketMaterial", None, None, None, ""), ("Asphalt Material", "NodeSocketMaterial", None, None, None, ""),
    ("Concrete Material", "NodeSocketMaterial", None, None, None, ""),
    ("Trim Start", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the start (set by junctions)"),
    ("Trim End", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the end (set by junctions)"),
    ("Props", "NodeSocketCollection", None, None, None, "Collection of roadside props (one is picked per point)"),
    ("Prop Spacing", "NodeSocketFloat", 28.0, 2.0, 200.0, ""), ("Prop Offset", "NodeSocketFloat", 0.5, 0.0, 10.0, "Lateral offset behind the curb (m)"),
    ("Prop Side", "NodeSocketInt", 2, 0, 2, "0 left, 1 right, 2 both (alternating)"), ("Prop Seed", "NodeSocketInt", 0, 0, 10000, ""),
    ("Prop Clear", "NodeSocketFloat", 6.0, 0.0, 60.0, "No props this far from a trimmed end (junctions, crosswalks)"),
    ("Manholes", "NodeSocketCollection", None, None, None, ""), ("Manhole Spacing", "NodeSocketFloat", 45.0, 5.0, 300.0, ""),
    ("Realize Instances", "NodeSocketBool", False, None, None, "For export: props become real geometry"),
    ("Collision Only", "NodeSocketBool", False, None, None, "For export: only the drivable / walkable surfaces"),
]
