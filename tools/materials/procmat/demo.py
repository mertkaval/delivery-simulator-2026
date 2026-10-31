"""PM_CoreDemo / PM_CoreSeamless: the core's self-test materials (not part of the library: LIBRARY = False).

PM_CoreDemo     warped 4D Voronoi cells with dark joints, per-cell tone, 4D noise speckle, bump; outputs BSDF,
                Albedo, Height. Exercises new_group, Coordinates (noise4, voronoi4, warp), ramps, bump, frames.
PM_CoreSeamless a 3D-only texture (Gabor) made seamless in UV mode with Coordinates.seamless(), plus a slab grid
                from Coordinates.periodic() / wrap(); input "Seamless" = 0 gives the raw (non-repeating) Gabor as a control.
PM_CoreDual     PM_CoreDemo with exact3d=True cells (3D Voronoi in object mode, 4D in UV mode): build_dual().
"""
import sys

from . import core, register

KEY = "coredemo"
LIBRARY = False


def build_demo_group(name="CoreDemo", exact3d=False):
    G = core.new_group(name, inputs=[
        ("Scale", "FLOAT", 1.0, 0.01, 100.0, "Multiplies every texture coordinate (1 = the sizes below, in metres)"),
        ("Cell Size", "FLOAT", 0.4, 0.02, 10.0, "Stone cell size (m)"),
        ("Stone Color", "COLOR", (0.30, 0.28, 0.25, 1.0), None, None, "Mean stone colour"),
        ("Joint Color", "COLOR", (0.04, 0.04, 0.04, 1.0), None, None, "Joint colour"),
        ("Joint Width", "FLOAT", 0.08, 0.0, 0.5, "Joint width as a fraction of a cell"),
        ("Warp", "FLOAT", 0.12, 0.0, 1.0, "Linear-light distortion of the coordinates"),
        ("Roughness", "FLOAT", 0.7, 0.0, 1.0, "Base roughness"),
        ("Bump Strength", "FLOAT", 0.5, 0.0, 1.0, "Bump strength"),
    ], outputs=("BSDF", "Albedo", "Height"))
    C = G.coords; I = G.I
    with G.frame("Warp: noise colour distorts the cell coordinates (tutorial idiom)"):
        wn = C.noise4(1.5, detail=4.0, roughness=0.5, label="warp noise", note="C: demo")
        VW = C.warp(wn.outputs["Color"], I("Warp"))
    with G.frame("Cells: 4D Voronoi, joints from distance to edge"):
        vs = G.div(1.0, I("Cell Size"))
        cells = C.voronoi4(vs, "F1", at=VW, exact3d=exact3d, label="cells")
        edges = C.voronoi4(vs, "DISTANCE_TO_EDGE", at=VW, exact3d=exact3d, label="cell edges")
        joint = G.smoothstep(edges.outputs["Distance"], I("Joint Width"), G.mul(I("Joint Width"), 0.4))
        dome = G.smoothstep(cells.outputs["Distance"], 0.9, 0.0)
    with G.frame("Tone: per-cell shade and fine speckle"):
        r, _, _ = G.separate_color(cells.outputs["Color"])
        tone = G.map_range(r, 0.0, 1.0, 0.75, 1.2)
        fine = C.noise4(25.0, detail=6.0, roughness=0.6, label="speckle")
        shade = G.mul(tone, G.madd(fine.outputs["Fac"], 0.3, 0.85))
        stone = G.vmath("SCALE", I("Stone Color"), scale=shade)
        col = G.mixc(joint, stone, I("Joint Color"))
        tint = G.ramp(fine.outputs["Fac"], ((0.35, (0.0, 0.0, 0.0, 1.0)), (0.75, (1.0, 1.0, 1.0, 1.0))), label="speckle contrast")
        col = G.mixc(0.08, col, tint.outputs["Color"], "OVERLAY")
    with G.frame("Surface: height, roughness, bump, BSDF"):
        height = G.add(G.mul(G.invert(joint), G.madd(dome, 0.4, 0.6)), G.mul(fine.outputs["Fac"], 0.1))
        rough = G.clamp(G.add(G.add(I("Roughness"), G.mul(G.sub(fine.outputs["Fac"], 0.5), 0.2)), G.mul(joint, 0.15)))
        nrm = G.bump(height, I("Bump Strength"), 0.02)
        bsdf = G.principled(Base_Color=col, Roughness=rough, Normal=nrm)
    G.out("BSDF", bsdf); G.out("Albedo", col); G.out("Height", G.mul(height, 0.01))
    return G.finish()


def build_seamless_group():
    G = core.new_group("CoreSeamless", inputs=[
        ("Scale", "FLOAT", 1.0, 0.01, 100.0, "Multiplies the texture coordinates"),
        ("Seamless", "FLOAT", 1.0, 0.0, 1.0, "1 = cross-faded (repeats in UV mode), 0 = the raw 3D texture (control)"),
    ], outputs=("BSDF", "Albedo"))
    C = G.coords; I = G.I

    def gabor(P):
        n = G.node("ShaderNodeTexGabor", "gabor 3D", gabor_type="3D")
        G.set(n, "Vector", P); G.set(n, "Scale", G.mul(3.0, I("Scale"))); G.set(n, "Frequency", 2.0); G.set(n, "Anisotropy", 0.7)
        return n.outputs["Value"]
    with G.frame("3D-only texture through Coordinates.seamless()"):
        val = C.seamless(gabor, blend=0.2)
        raw = gabor(C.P)
        v = G.mixf(I("Seamless"), raw, val)
        v = G.smoothstep(v, 0.3, 0.7)                       # Gabor Value sits around 0.5: stretch the contrast
        col = G.mixc(v, (0.08, 0.09, 0.11, 1.0), (0.75, 0.77, 0.8, 1.0))
    with G.frame("Slab grid from Coordinates.periodic() (1.3 m, snapped to Tile Size / n in UV mode)"):
        size, n = C.periodic(1.3)
        fx = G.fract(G.div(C.px, size)); fy = G.fract(G.div(C.py, size))
        edge = G.mul(G.minimum(G.minimum(fx, G.invert(fx)), G.minimum(fy, G.invert(fy))), size)
        joint = G.smoothstep(edge, 0.015, 0.005)
        ix = C.wrap(G.math("FLOOR", G.div(C.px, size)), n); iy = C.wrap(G.math("FLOOR", G.div(C.py, size)), n)
        wn = G.node("ShaderNodeTexWhiteNoise", "slab tone", noise_dimensions="3D"); G.set(wn, "Vector", G.combine(ix, iy, 0.0))
        col = G.vmath("SCALE", col, scale=G.map_range(wn.outputs["Value"], 0.0, 1.0, 0.8, 1.1))
        col = G.mixc(G.mul(joint, 0.7), col, (0.02, 0.02, 0.02, 1.0))
    with G.frame("Wave bands with snap_scale() (Wave has no 4D variant); phase wobble from noise4"):
        ph = C.noise4(0.8, detail=2.0, label="phase wobble")
        wv = G.node("ShaderNodeTexWave", "bands", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        G.set(wv, "Vector", C.P); G.set(wv, "Scale", C.snap_scale(2.3, core.TWO_PI / 20.0))
        G.set(wv, "Distortion", 0.0); G.set(wv, "Detail", 0.0); G.set(wv, "Phase Offset", G.mul(ph.outputs["Fac"], 4.0))
        col = G.mixc(0.25, col, wv.outputs["Color"], "MULTIPLY")
        bsdf = G.principled(Base_Color=col, Roughness=0.5)
    G.out("BSDF", bsdf); G.out("Albedo", col)
    return G.finish()


def build():
    demo = core.contract_material("CoreDemo", build_demo_group(), viewport=(0.3, 0.28, 0.25, 1.0), roughness=0.7)
    seam = core.contract_material("CoreSeamless", build_seamless_group(), roughness=0.5)
    return [demo, seam]


def build_dual():
    """PM_CoreDual: the demo with exact3d cells (object mode = 3D Voronoi like the tutorials, UV mode = 4D torus)."""
    return core.contract_material("CoreDual", build_demo_group("CoreDual", exact3d=True), viewport=(0.3, 0.28, 0.25, 1.0), roughness=0.7)


register(sys.modules[__name__])
