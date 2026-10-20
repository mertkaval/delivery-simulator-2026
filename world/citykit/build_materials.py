"""City kit material library: seamless procedural PBR sets baked with Cycles.

Each material is authored as a node network on a 1 x 1 UV tile that represents
TILE metres of real surface. Noise is sampled on a 4D torus (cos/sin of U and V)
and brick/panel patterns use integer counts per tile, so every map tiles seamlessly.

Outputs world/citykit/textures/<name>_albedo.png, _rough.png, _normal.png (OpenGL +Y).

Run inside Blender (MCP or GUI):
    MATERIALS = ["stucco"]        # optional subset; default = all
    exec(open(r".../build_materials.py").read())
or headless: blender --background --python build_materials.py
"""
import bpy
import math
import os

ROOT = r"C:\GodotProjects\delivery-simulator-2026\world\citykit"
OUT = os.path.join(ROOT, "textures")
SIZE = 1024
TAU = math.tau


class Graph:
    """Small helper for building shader node trees in code."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0
        tc = self.node("ShaderNodeTexCoord")
        sep = self.node("ShaderNodeSeparateXYZ")
        self.link(tc.outputs["UV"], sep.inputs[0])
        self.u, self.v = sep.outputs[0], sep.outputs[1]

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, val in props.items():
            setattr(n, k, val)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, val in enumerate((a, b)):
            if val is None:
                continue
            if isinstance(val, (int, float)):
                n.inputs[i].default_value = val
            else:
                self.link(val, n.inputs[i])
        return n.outputs[0]

    def mix(self, fac, a, b):
        """Linear blend of two floats/sockets by fac."""
        return self.math("ADD", self.math("MULTIPLY", self.math("SUBTRACT", 1.0, fac), a), self.math("MULTIPLY", fac, b))

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        els = n.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
        for pos, col in stops[1:]:
            e = els.new(pos)
            e.color = (*col, 1)
        self.link(fac, n.inputs[0])
        return n.outputs[0]

    def torus(self, freq_u, freq_v=None):
        """4D coordinates (vector, w) on a torus: seamless in U and V with `freq` features per tile."""
        freq_v = freq_v or freq_u
        a = self.math("MULTIPLY", self.u, TAU)
        b = self.math("MULTIPLY", self.v, TAU)
        ru, rv = freq_u / TAU, freq_v / TAU
        comb = self.node("ShaderNodeCombineXYZ")
        self.link(self.math("MULTIPLY", self.math("COSINE", a), ru), comb.inputs[0])
        self.link(self.math("MULTIPLY", self.math("SINE", a), ru), comb.inputs[1])
        self.link(self.math("MULTIPLY", self.math("COSINE", b), rv), comb.inputs[2])
        w = self.math("MULTIPLY", self.math("SINE", b), rv)
        return comb.outputs[0], w

    def noise(self, freq_u, freq_v=None, detail=4.0, rough=0.55, distortion=0.0, seed=0.0):
        vec, w = self.torus(freq_u, freq_v)
        n = self.node("ShaderNodeTexNoise", noise_dimensions="4D")
        self.link(vec, n.inputs["Vector"])
        self.link(self.math("ADD", w, seed * 17.31), n.inputs["W"])
        n.inputs["Scale"].default_value = 1.0
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs["Fac"]

    def voronoi(self, freq, feature="F1", output="Distance", seed=0.0):
        vec, w = self.torus(freq)
        n = self.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature=feature)
        self.link(vec, n.inputs["Vector"])
        self.link(self.math("ADD", w, seed * 9.7), n.inputs["W"])
        n.inputs["Scale"].default_value = 1.0
        return n.outputs[output]

    def cell_random(self, cx, cy, seed=0.0):
        """Per-cell random value from integer (already wrapped) cell coordinates."""
        comb = self.node("ShaderNodeCombineXYZ")
        for i, val in enumerate((cx, cy)):
            if isinstance(val, (int, float)):
                comb.inputs[i].default_value = val
            else:
                self.link(val, comb.inputs[i])
        comb.inputs[2].default_value = seed
        wn = self.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
        self.link(comb.outputs[0], wn.inputs["Vector"])
        return wn.outputs["Value"]

    def grid(self, count_u, count_v, joint_u, joint_v, stagger=0.0):
        """Running-bond/stack grid. Returns (joint mask 0=joint 1=face, cell random)."""
        row = self.math("FLOOR", self.math("MULTIPLY", self.v, count_v))
        shift = self.math("MULTIPLY", self.math("MODULO", row, 2.0), stagger)
        x = self.math("ADD", self.math("MULTIPLY", self.u, count_u), shift)
        y = self.math("MULTIPLY", self.v, count_v)
        fx, fy = self.math("FRACT", x), self.math("FRACT", y)
        # Distance to the nearest joint in metres-normalised cell units.
        ex = self.math("MINIMUM", fx, self.math("SUBTRACT", 1.0, fx))
        ey = self.math("MINIMUM", fy, self.math("SUBTRACT", 1.0, fy))
        # 0 inside the joint, ramping to 1 over a soft arris of 35% of the joint width.
        mx = self.math("DIVIDE", self.math("SUBTRACT", ex, joint_u * 0.5), joint_u * 0.35)
        my = self.math("DIVIDE", self.math("SUBTRACT", ey, joint_v * 0.5), joint_v * 0.35)
        mask = self.math("MINIMUM", self.math("MINIMUM", mx, my), 1.0)
        mask = self.math("MAXIMUM", mask, 0.0)
        cell = self.cell_random(self.math("MODULO", self.math("FLOOR", x), float(count_u)), row)
        return mask, cell

    def output(self, colour, rough, height, height_scale, metallic=0.0):
        bsdf = self.node("ShaderNodeBsdfPrincipled")
        self.link(colour, bsdf.inputs["Base Color"])
        self.link(rough, bsdf.inputs["Roughness"])
        bsdf.inputs["Metallic"].default_value = metallic
        bump = self.node("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = height_scale
        self.link(height, bump.inputs["Height"])
        self.link(bump.outputs["Normal"], bsdf.inputs["Normal"])
        out = self.node("ShaderNodeOutputMaterial")
        self.link(bsdf.outputs[0], out.inputs[0])


def rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


# --- material recipes -------------------------------------------------------------
# TILE: metres of real surface covered by one texture repeat (Godot uses UV in metres / TILE).

def brick(g, face_dark, face_light, mortar):
    # 8 bricks x 24 courses on a 1.8 m tile: 225 x 75 mm modules with 10 mm joints.
    mask, cell = g.grid(8, 24, 0.010 / 0.225, 0.010 / 0.075, stagger=0.5)
    grime = g.noise(3, 3, detail=3)
    fine = g.noise(90, 90, detail=2, seed=3)
    tone = g.math("ADD", g.math("MULTIPLY", cell, 0.7), g.math("MULTIPLY", grime, 0.3))
    face = g.ramp(tone, [(0.0, rgb(face_dark)), (1.0, rgb(face_light))])
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(mask, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*rgb(mortar), 1)
    g.link(face, mix.inputs["B"])
    rough = g.mix(mask, 0.95, g.math("ADD", 0.78, g.math("MULTIPLY", fine, 0.15)))
    height = g.math("ADD", g.math("MULTIPLY", mask, 0.8), g.math("MULTIPLY", fine, 0.12))
    g.output(mix.outputs["Result"], rough, height, 0.012)


def stucco(g):
    broad = g.noise(2, 2, detail=3)
    mid = g.noise(14, 14, detail=5, rough=0.6, seed=1)
    fine = g.noise(160, 160, detail=2, seed=2)
    tone = g.math("ADD", g.math("MULTIPLY", broad, 0.6), g.math("MULTIPLY", mid, 0.4))
    col = g.ramp(tone, [(0.25, rgb("d9d1c1")), (0.75, rgb("ece6d8"))])
    rough = g.math("ADD", 0.82, g.math("MULTIPLY", fine, 0.12))
    height = g.math("ADD", g.math("MULTIPLY", mid, 0.4), g.math("MULTIPLY", fine, 0.6))
    g.output(col, rough, height, 0.004)


def concrete(g):
    broad = g.noise(2, 2, detail=3)
    mottle = g.noise(9, 9, detail=5, rough=0.65, seed=13)
    # Faint rain streaks run down the facade: stretched along V, still periodic.
    streak = g.noise(26, 3, detail=3, seed=4)
    pores = g.voronoi(140, seed=5)
    pore_mask = g.math("GREATER_THAN", pores, 0.08)
    tone = g.math("ADD", g.math("ADD", g.math("MULTIPLY", broad, 0.35), g.math("MULTIPLY", mottle, 0.45)), g.math("MULTIPLY", streak, 0.2))
    col = g.ramp(tone, [(0.3, rgb("8f918c")), (0.7, rgb("b4b5ae"))])
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(pore_mask, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*rgb("5e605c"), 1)
    g.link(col, mix.inputs["B"])
    rough = g.math("ADD", 0.84, g.math("MULTIPLY", streak, 0.1))
    height = g.math("ADD", pore_mask, g.math("MULTIPLY", broad, 0.3))
    g.output(mix.outputs["Result"], rough, height, 0.003)


def limestone(g):
    # 2 x 4 stack-bond panels of 1.2 x 0.6 m on a 2.4 m tile, 6 mm joints.
    mask, cell = g.grid(2, 4, 0.006 / 1.2, 0.006 / 0.6)
    speck = g.voronoi(220, seed=6)
    vein = g.noise(6, 6, detail=6, distortion=0.4, seed=7)
    tone = g.math("ADD", g.math("MULTIPLY", cell, 0.5), g.math("MULTIPLY", vein, 0.5))
    col = g.ramp(tone, [(0.2, rgb("c8bea8")), (0.8, rgb("ddd5c2"))])
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(mask, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*rgb("8a8478"), 1)
    g.link(col, mix.inputs["B"])
    rough = g.math("ADD", 0.7, g.math("MULTIPLY", speck, 0.4))
    height = g.math("ADD", g.math("MULTIPLY", mask, 0.9), g.math("MULTIPLY", speck, 0.1))
    g.output(mix.outputs["Result"], rough, height, 0.006)


def metal_panel(g):
    # Standing-seam cladding: 4 vertical seams per 2 m tile.
    seam_u = g.math("FRACT", g.math("MULTIPLY", g.u, 4.0))
    ridge = g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", seam_u, 0.5)), 0.012)), 0.0)
    wear = g.noise(3, 10, detail=4, seed=8)
    col = g.ramp(wear, [(0.3, rgb("2d3338")), (0.7, rgb("3a4148"))])
    rough = g.math("ADD", 0.38, g.math("MULTIPLY", wear, 0.25))
    g.output(col, rough, ridge, 0.02, metallic=0.75)


def roof_gravel(g):
    stones = g.voronoi(180, feature="F1", output="Color", seed=9)
    dist = g.voronoi(180, seed=9)
    sep = g.node("ShaderNodeSeparateColor")
    g.link(stones, sep.inputs[0])
    # Low-contrast ballast: individual stones read up close without shimmering from the air.
    tone = g.ramp(sep.outputs[0], [(0.0, rgb("6f6d68")), (0.5, rgb("7c7a74")), (1.0, rgb("8a877f"))])
    dirt = g.noise(3, 3, detail=4, seed=10)
    mix = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    mix.inputs["Factor"].default_value = 0.3
    g.link(tone, mix.inputs["A"])
    dcol = g.ramp(dirt, [(0.3, rgb("7a7468")), (0.7, rgb("ffffff"))])
    g.link(dcol, mix.inputs["B"])
    height = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", dist, 2.0))
    g.output(mix.outputs["Result"], g.math("ADD", 0.9, 0.0), height, 0.01)


def slate_roof(g):
    # 6 slates x 9 courses per 1.8 m tile, half-bond, 3 mm gaps and a course shadow line.
    mask, cell = g.grid(6, 9, 0.004 / 0.3, 0.02 / 0.2, stagger=0.5)
    course = g.math("FRACT", g.math("MULTIPLY", g.v, 9.0))
    lip = g.math("POWER", course, 3.0)
    tone = g.math("ADD", g.math("MULTIPLY", cell, 0.6), g.math("MULTIPLY", g.noise(30, 30, detail=3, seed=11), 0.4))
    col = g.ramp(tone, [(0.0, rgb("2c3034")), (1.0, rgb("4a5056"))])
    rough = g.math("ADD", 0.6, g.math("MULTIPLY", cell, 0.25))
    height = g.math("MULTIPLY", mask, g.math("ADD", 0.4, g.math("MULTIPLY", lip, 0.6)))
    g.output(col, rough, height, 0.012)


def cedar_boards(g):
    # Vertical boards 150 mm wide: 12 per 1.8 m tile, random tone per board, fine grain along V.
    board = g.math("FLOOR", g.math("MULTIPLY", g.u, 12.0))
    fx = g.math("FRACT", g.math("MULTIPLY", g.u, 12.0))
    groove = g.math("MINIMUM", g.math("DIVIDE", g.math("MINIMUM", fx, g.math("SUBTRACT", 1.0, fx)), 0.04), 1.0)
    cell = g.cell_random(board, 0.0, 3.0)
    grain = g.noise(60, 4, detail=6, distortion=0.6, seed=12)
    tone = g.math("ADD", g.math("MULTIPLY", cell, 0.55), g.math("MULTIPLY", grain, 0.45))
    col = g.ramp(tone, [(0.1, rgb("6b4a33")), (0.9, rgb("a77a52"))])
    shade = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    g.link(g.math("SUBTRACT", 1.0, groove), shade.inputs["Factor"])
    g.link(col, shade.inputs["A"])
    shade.inputs["B"].default_value = (*rgb("3a2a1e"), 1)
    rough = g.math("ADD", 0.62, g.math("MULTIPLY", grain, 0.2))
    height = g.math("ADD", groove, g.math("MULTIPLY", grain, 0.1))
    g.output(shade.outputs["Result"], rough, height, 0.006)


def lap_siding(g):
    # Painted horizontal lap boards: 7 boards per 1.26 m exposure, shadow line under each lap.
    # Light neutral base: the game tints it per house (instance colour).
    rows = 10
    v = g.math("FRACT", g.math("MULTIPLY", g.v, rows))
    lap = g.math("POWER", v, 4.0)  # board thickens towards its lower edge
    shadow = g.math("MINIMUM", g.math("DIVIDE", v, 0.06), 1.0)
    board = g.cell_random(g.math("FLOOR", g.math("MULTIPLY", g.u, 2.0)), g.math("FLOOR", g.math("MULTIPLY", g.v, rows)), 4.0)
    grain = g.noise(3, 40, detail=4, seed=14)
    tone = g.math("ADD", 0.86, g.math("ADD", g.math("MULTIPLY", board, 0.05), g.math("MULTIPLY", grain, 0.06)))
    tone = g.math("MULTIPLY", tone, g.mix(shadow, 0.55, 1.0))
    col = g.ramp(tone, [(0.0, (0, 0, 0)), (1.0, (1, 1, 1))])
    rough = g.math("ADD", 0.55, g.math("MULTIPLY", grain, 0.15))
    height = g.math("ADD", g.math("MULTIPLY", lap, 0.9), g.math("MULTIPLY", grain, 0.05))
    g.output(col, rough, height, 0.012)


def shingle_siding(g):
    # Cedar shake siding: 8 courses x 8 shingles per 1.6 m tile, random widths, butt shadows.
    mask, cell = g.grid(8, 8, 0.006 / 0.2, 0.03 / 0.2, stagger=0.5)
    course = g.math("FRACT", g.math("MULTIPLY", g.v, 8.0))
    butt = g.math("POWER", g.math("SUBTRACT", 1.0, course), 6.0)
    grain = g.noise(30, 4, detail=5, seed=15)
    tone = g.math("ADD", 0.75, g.math("ADD", g.math("MULTIPLY", cell, 0.15), g.math("MULTIPLY", grain, 0.12)))
    tone = g.math("MULTIPLY", tone, g.mix(mask, 0.45, 1.0))
    col = g.ramp(tone, [(0.0, (0, 0, 0)), (1.0, (1, 1, 1))])
    rough = g.math("ADD", 0.7, g.math("MULTIPLY", grain, 0.15))
    height = g.math("MULTIPLY", mask, g.math("ADD", 0.5, g.math("MULTIPLY", butt, 0.5)))
    g.output(col, rough, height, 0.01)


def board_batten(g):
    # Vertical board-and-batten: 5 battens per 2 m tile, painted (tinted in game).
    fx = g.math("FRACT", g.math("MULTIPLY", g.u, 5.0))
    batten = g.math("SUBTRACT", 1.0, g.math("MINIMUM", g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", fx, 0.5)), 0.08), 1.0))
    grain = g.noise(4, 30, detail=4, seed=16)
    tone = g.math("ADD", 0.88, g.math("MULTIPLY", grain, 0.06))
    edge = g.math("MINIMUM", g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", g.math("SUBTRACT", fx, 0.5)), 0.08)), 0.02), 1.0)
    tone = g.math("MULTIPLY", tone, g.mix(edge, 0.7, 1.0))
    col = g.ramp(tone, [(0.0, (0, 0, 0)), (1.0, (1, 1, 1))])
    rough = g.math("ADD", 0.6, g.math("MULTIPLY", grain, 0.1))
    g.output(col, rough, g.math("ADD", batten, g.math("MULTIPLY", grain, 0.05)), 0.015)


def asphalt_shingles(g):
    # Laminated architectural shingles: 12 courses per 1.8 m, irregular tabs, granule speckle.
    rows = 12
    row = g.math("FLOOR", g.math("MULTIPLY", g.v, rows))
    tabs_x = g.math("ADD", g.math("MULTIPLY", g.u, 6.0), g.math("MULTIPLY", g.cell_random(row, 0.0, 9.0), 0.8))
    tab = g.cell_random(g.math("MODULO", g.math("FLOOR", tabs_x), 6.0), row, 2.0)
    course = g.math("FRACT", g.math("MULTIPLY", g.v, rows))
    shadow = g.math("MINIMUM", g.math("DIVIDE", course, 0.12), 1.0)
    speck = g.voronoi(260, seed=17)
    tone = g.math("ADD", 0.38, g.math("ADD", g.math("MULTIPLY", tab, 0.25), g.math("MULTIPLY", speck, 0.25)))
    tone = g.math("MULTIPLY", tone, g.mix(shadow, 0.45, 1.0))
    col = g.ramp(tone, [(0.0, (0, 0, 0)), (1.0, (1, 1, 1))])
    rough = g.math("ADD", 0.82, g.math("MULTIPLY", speck, 0.15))
    height = g.math("ADD", g.math("MULTIPLY", shadow, 0.7), g.math("MULTIPLY", speck, 0.2))
    g.output(col, rough, height, 0.01)


def deck_boards(g):
    # Decking: 140 mm boards with 6 mm gaps, staggered butt joints, weathered tone.
    boards = 14
    board = g.math("FLOOR", g.math("MULTIPLY", g.u, boards))
    fx = g.math("FRACT", g.math("MULTIPLY", g.u, boards))
    gap = g.math("MINIMUM", g.math("DIVIDE", g.math("MINIMUM", fx, g.math("SUBTRACT", 1.0, fx)), 0.04), 1.0)
    shift = g.cell_random(board, 0.0, 11.0)
    joint = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", g.v, 1.0), shift))
    butt = g.math("MINIMUM", g.math("DIVIDE", g.math("MINIMUM", joint, g.math("SUBTRACT", 1.0, joint)), 0.005), 1.0)
    grain = g.noise(40, 3, detail=6, distortion=0.5, seed=18)
    tone = g.math("ADD", g.math("MULTIPLY", g.cell_random(board, 1.0, 5.0), 0.5), g.math("MULTIPLY", grain, 0.5))
    col = g.ramp(tone, [(0.1, rgb("6e5843")), (0.9, rgb("9a7d5c"))])
    shade = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    g.link(g.math("SUBTRACT", 1.0, g.math("MINIMUM", gap, butt)), shade.inputs["Factor"])
    g.link(col, shade.inputs["A"])
    shade.inputs["B"].default_value = (*rgb("1e1712"), 1)
    g.output(shade.outputs["Result"], g.math("ADD", 0.7, g.math("MULTIPLY", grain, 0.15)), g.math("MULTIPLY", g.math("MINIMUM", gap, butt), 1.0), 0.008)


def garden_soil(g):
    # Bark mulch / garden soil for beds.
    chips = g.voronoi(60, feature="F1", output="Color", seed=19)
    sep = g.node("ShaderNodeSeparateColor")
    g.link(chips, sep.inputs[0])
    col = g.ramp(sep.outputs[0], [(0.0, rgb("2a1d14")), (0.6, rgb("4a3322")), (1.0, rgb("6b4a30"))])
    dist = g.voronoi(60, seed=19)
    g.output(col, g.math("ADD", 0.9, 0.0), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", dist, 2.0)), 0.012)


def terrazzo(g):
    # Cream terrazzo: marble chips in three tones set in a warm binder, polished.
    chips = g.voronoi(70, feature="F1", output="Color", seed=21)
    dist = g.voronoi(70, seed=21)
    sep = g.node("ShaderNodeSeparateColor")
    g.link(chips, sep.inputs[0])
    chip_col = g.ramp(sep.outputs[0], [(0.0, rgb("8c7b6a")), (0.35, rgb("c9b9a3")), (0.7, rgb("e8e0d2")), (1.0, rgb("a14f3a"))])
    is_chip = g.math("LESS_THAN", dist, 0.32)
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(is_chip, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*rgb("ddd3c3"), 1)
    g.link(chip_col, mix.inputs["B"])
    fine = g.noise(40, 40, detail=3, seed=22)
    g.output(mix.outputs["Result"], g.math("ADD", 0.22, g.math("MULTIPLY", fine, 0.12)), g.math("MULTIPLY", is_chip, 0.2), 0.002)


def subway_tile(g):
    # Kitchen wall: 150 x 75 mm glazed tiles, half bond, 3 mm grout, on a 1.2 m tile.
    mask, cell = g.grid(8, 16, 0.003 / 0.15, 0.003 / 0.075, stagger=0.5)
    tone = g.math("ADD", 0.9, g.math("MULTIPLY", cell, 0.06))
    col = g.ramp(g.math("MULTIPLY", tone, g.mix(mask, 0.62, 1.0)), [(0.0, (0, 0, 0)), (1.0, rgb("f4f2ec"))])
    g.output(col, g.mix(mask, 0.9, 0.08), mask, 0.004)


def cini_tile(g):
    # Iznik-style çini: 4 x 4 tiles of 200 mm, cobalt eight-petal rosette with turquoise
    # leaves and a red centre on a white glaze; thin grout.
    mask, cell = g.grid(4, 4, 0.003 / 0.2, 0.003 / 0.2)
    cu = g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", g.u, 4.0)), 0.5)
    cv = g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", g.v, 4.0)), 0.5)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", cu, cu), g.math("MULTIPLY", cv, cv)))
    ang = g.math("ARCTAN2", cv, cu)
    petal_r = g.math("ADD", 0.2, g.math("MULTIPLY", g.math("ABSOLUTE", g.math("COSINE", g.math("MULTIPLY", ang, 4.0))), 0.18))
    petal = g.math("LESS_THAN", r, petal_r)
    centre = g.math("LESS_THAN", r, 0.07)
    # Corner quarter-rosettes join neighbouring tiles into a continuous pattern.
    corner = g.math("LESS_THAN", g.math("SUBTRACT", 0.7071, r), 0.16)
    leaf = g.math("MULTIPLY", g.math("LESS_THAN", r, 0.47), g.math("GREATER_THAN", r, 0.4))
    white = (*rgb("f3efe4"), 1)
    col = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(leaf, col.inputs["Factor"])
    col.inputs["A"].default_value = white
    col.inputs["B"].default_value = (*rgb("2a9d9a"), 1)
    c2 = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(g.math("MAXIMUM", petal, corner), c2.inputs["Factor"])
    g.link(col.outputs["Result"], c2.inputs["A"])
    c2.inputs["B"].default_value = (*rgb("1d3f8f"), 1)
    c3 = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(centre, c3.inputs["Factor"])
    g.link(c2.outputs["Result"], c3.inputs["A"])
    c3.inputs["B"].default_value = (*rgb("b8322a"), 1)
    c4 = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(mask, c4.inputs["Factor"])
    c4.inputs["A"].default_value = (*rgb("b9b3a6"), 1)
    g.link(c3.outputs["Result"], c4.inputs["B"])
    g.output(c4.outputs["Result"], g.mix(mask, 0.85, 0.12), mask, 0.003)


def wood_floor(g):
    # Oiled oak strip floor: 9 boards per 1.6 m tile, random lengths, warm tones.
    boards = 9
    board = g.math("FLOOR", g.math("MULTIPLY", g.v, boards))
    fy = g.math("FRACT", g.math("MULTIPLY", g.v, boards))
    gap = g.math("MINIMUM", g.math("DIVIDE", g.math("MINIMUM", fy, g.math("SUBTRACT", 1.0, fy)), 0.03), 1.0)
    shift = g.cell_random(board, 0.0, 13.0)
    joint = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", g.u, 2.0), shift))
    butt = g.math("MINIMUM", g.math("DIVIDE", g.math("MINIMUM", joint, g.math("SUBTRACT", 1.0, joint)), 0.004), 1.0)
    grain = g.noise(4, 50, detail=6, distortion=0.5, seed=23)
    tone = g.math("ADD", g.math("MULTIPLY", g.cell_random(board, g.math("FLOOR", g.math("ADD", g.math("MULTIPLY", g.u, 2.0), shift)), 7.0), 0.5), g.math("MULTIPLY", grain, 0.5))
    col = g.ramp(tone, [(0.1, rgb("6a4528")), (0.9, rgb("a8754a"))])
    shade = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    g.link(g.math("SUBTRACT", 1.0, g.math("MINIMUM", gap, butt)), shade.inputs["Factor"])
    g.link(col, shade.inputs["A"])
    shade.inputs["B"].default_value = (*rgb("2a1a10"), 1)
    g.output(shade.outputs["Result"], g.math("ADD", 0.4, g.math("MULTIPLY", grain, 0.15)), g.math("MINIMUM", gap, butt), 0.005)


RECIPES = {
    "terrazzo": (2.0, terrazzo),
    "subway_tile": (1.2, subway_tile),
    "cini_tile": (0.8, cini_tile),
    "wood_floor": (1.6, wood_floor),
    "lap_siding": (1.26, lap_siding),
    "shingle_siding": (1.6, shingle_siding),
    "board_batten": (2.0, board_batten),
    "asphalt_shingles": (1.8, asphalt_shingles),
    "deck_boards": (1.96, deck_boards),
    "garden_soil": (2.0, garden_soil),
    "brick_buff": (1.8, lambda g: brick(g, "a9875f", "c9a979", "b7b0a2")),
    "brick_charcoal": (1.8, lambda g: brick(g, "3b3533", "5a504b", "8c8780")),
    "brick_red": (1.8, lambda g: brick(g, "7a3326", "a24c35", "a59b8e")),
    "stucco": (2.0, stucco),
    "concrete": (2.0, concrete),
    "limestone": (2.4, limestone),
    "metal_panel": (2.0, metal_panel),
    "roof_gravel": (2.0, roof_gravel),
    "slate_roof": (1.8, slate_roof),
    "cedar_boards": (1.8, cedar_boards),
}


def bake(name):
    tile, recipe = RECIPES[name]
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
    except TypeError as err:
        print("engine:", err)
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
    col = bpy.data.collections.get("CityKitBake")
    if col is None:
        col = bpy.data.collections.new("CityKitBake")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mesh = bpy.data.meshes.new("bake_plane")
    mesh.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    obj = bpy.data.objects.new("bake_" + name, mesh)
    col.objects.link(obj)
    mat = bpy.data.materials.get("kit_" + name) or bpy.data.materials.new("kit_" + name)
    mat.use_nodes = True
    graph = Graph(mat)
    recipe(graph)
    mesh.materials.append(mat)
    target = graph.node("ShaderNodeTexImage")
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    results = []
    for suffix, bake_type, colour in (("albedo", "DIFFUSE", "sRGB"), ("rough", "ROUGHNESS", "Non-Color"), ("normal", "NORMAL", "Non-Color")):
        img_name = f"{name}_{suffix}"
        img = bpy.data.images.get(img_name)
        if img:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(img_name, SIZE, SIZE, alpha=False, float_buffer=False)
        img.colorspace_settings.name = colour
        target.image = img
        mat.node_tree.nodes.active = target
        kwargs = {"type": bake_type, "margin": 0, "use_clear": True}
        if bake_type == "DIFFUSE":
            kwargs["pass_filter"] = {"COLOR"}
        if bake_type == "NORMAL":
            kwargs["normal_space"] = "TANGENT"
        bpy.ops.object.bake(**kwargs)
        path = os.path.join(OUT, img_name + ".png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        results.append(path)
    mat["tile_metres"] = tile
    print(f"baked {name} (tile {tile} m):", ", ".join(os.path.basename(p) for p in results))
    return tile


names = globals().get("MATERIALS") or list(RECIPES)
tiles = {n: bake(n) for n in names}
print("TILES", tiles)
