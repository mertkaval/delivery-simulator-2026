"""CityForge material library v2: procedural Blender node materials baked to game textures.

    blender --background --factory-startup --python tools/cityforge/materials.py -- <out_dir> [names...] [--fast]
    In a visible Blender: exec(open("tools/cityforge/materials.py").read()) with LIVE_ARGS set (see materials_live.py)

Every material is a node graph built in code, the way it would be wired by hand: a base pattern
(courses, planks, tiles, cobbles ...) feeding the "realism stack" taken from the reference
shader-ball file (realisticProceduralMaterial_01.blend): the same masks drive colour, roughness and
relief together (realism guide section 4):
  macro tone     low-frequency noise: patches of lighter and darker surface
  per-cell hue   each brick / plank / tile shifts its own hue and value
  grime          dirt in the cavities (mortar joints, plank gaps, pores): darker, rougher
  edge wear      chipped faces (Voronoi cells gated by noise) show the lighter core, more relief
  scratches      thin Voronoi edge lines on painted and metal surfaces: lighter, glossier
  detail noise   fine grain in the relief and a roughness breakup so highlights never read flat
Outputs per material (2048 px, one 2 m tile, seamless through 4D torus noise):
  <name>_albedo.jpg (sRGB, no baked lighting), <name>_normal.png (OpenGL tangent space, what Godot
  expects), <name>_orm.jpg (R occlusion, G roughness, B metallic: Godot's ORMMaterial3D layout).
Tintable materials are baked near-neutral: the game multiplies each house's paint colour in.
"""
import math, os, sys, json
import bpy
import numpy as np

argv = globals().get("LIVE_ARGS") or (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
OUT = os.path.abspath(argv[0]) if argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "cityforge", "materials")
ONLY = set(a for a in argv[1:] if not a.startswith("--"))
RES = 1024 if "--fast" in argv else 2048
TILE = 2.0
LIVE = "--live" in argv            # a visible Blender: keep the scene, add the materials, no save
os.makedirs(OUT, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
try:
    cp = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            cp.compute_device_type = dev
            cp.get_devices()
            if any(d.type == dev for d in cp.devices):
                for d in cp.devices: d.use = d.type == dev
                scene.cycles.device = "GPU"
                print("MATERIALS cycles device", dev)
                break
        except TypeError:
            continue
except Exception as e:
    print("MATERIALS cpu bake:", e)
scene.cycles.samples = 8
scene.cycles.use_denoising = False


# --- node helpers ------------------------------------------------------------------------------
class G:
    """Graph builder: wires values or sockets into new nodes, laid out left to right inside labelled frames."""
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0
        self.y = 0
        self.frame = None

    def section(self, label):
        self.frame = self.nt.nodes.new("NodeFrame")
        self.frame.label = label
        self.y -= 450
        self.x = 0
        return self.frame

    def _place(self, n):
        n.location = (self.x, self.y)
        if self.frame is not None: n.parent = self.frame
        self.x += 190
        if self.x > 3800:
            self.x = 0
            self.y -= 320

    def node(self, kind, *, props=None, **inputs):
        n = self.nt.nodes.new(kind)
        self._place(n)
        for k, v in (props or {}).items():
            setattr(n, k, v)
        for k, v in inputs.items():
            name = k.replace("_", " ")
            sock = n.inputs[name] if name in n.inputs else n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket): self.nt.links.new(v, sock)
            else: sock.default_value = v
        return n

    def math(self, op, a, b=0.0, c=None, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        self._place(n)
        n.operation = op
        n.use_clamp = bool(clamp)
        for i, v in enumerate((a, b) if c is None else (a, b, c)):
            if isinstance(v, bpy.types.NodeSocket): self.nt.links.new(v, n.inputs[i])
            else: n.inputs[i].default_value = v
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.nt.nodes.new("ShaderNodeMix")
        self._place(n)
        n.data_type = "RGBA"
        n.blend_type = blend
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, bpy.types.NodeSocket): self.nt.links.new(v, sock)
            elif isinstance(v, (int, float)): sock.default_value = v if sock.type != "RGBA" else (v, v, v, 1.0)
            else: sock.default_value = v
        return n.outputs[2]

    def ramp(self, fac, stops, interp="LINEAR"):
        n = self.nt.nodes.new("ShaderNodeValToRGB")
        self._place(n)
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > len(stops): cr.elements.remove(cr.elements[-1])
        while len(cr.elements) < len(stops): cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = col if len(col) == 4 else (*col, 1.0)
        self.nt.links.new(fac, n.inputs[0])
        return n.outputs[0]

    def smooth(self, fac, a, b):
        """Scalar smoothstep from a to b (b < a inverts), as a value."""
        lo, hi = (a, b) if a <= b else (b, a)
        stops = [(lo, (0, 0, 0)), (hi, (1, 1, 1))] if a <= b else [(lo, (1, 1, 1)), (hi, (0, 0, 0))]
        c = self.ramp(fac, stops, "EASE")
        return self.node("ShaderNodeSeparateColor", Color=c).outputs[0]

    def gray(self, v):
        return self.node("ShaderNodeCombineColor", Red=v, Green=v, Blue=v).outputs[0]

    def hsv(self, col, hue=0.5, sat=1.0, val=1.0):
        return self.node("ShaderNodeHueSaturation", Color=col, Hue=hue, Saturation=sat, Value=val).outputs[0]


def uv(g):
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["UV"])
    return g.math("MULTIPLY", sep.outputs["X"], TILE), g.math("MULTIPLY", sep.outputs["Y"], TILE)


def torus_noise(g, u, v, scale, detail=4.0, rough=0.55, kind="noise", seed=0.0, feature="F1", stretch=(1.0, 1.0)):
    """Seamless noise: (u, v) metres on the tile -> 4D torus -> Noise / Voronoi."""
    R = scale * TILE / (2 * math.pi)
    a = g.math("MULTIPLY", u, 2 * math.pi / TILE * stretch[0])
    b = g.math("MULTIPLY", v, 2 * math.pi / TILE * stretch[1])
    x = g.math("MULTIPLY", g.math("COSINE", a), R)
    y = g.math("MULTIPLY", g.math("SINE", a), R)
    z = g.math("MULTIPLY", g.math("COSINE", b), R)
    w = g.math("ADD", g.math("MULTIPLY", g.math("SINE", b), R), seed)
    vec = g.node("ShaderNodeCombineXYZ", X=x, Y=y, Z=z)
    if kind == "voronoi":
        n = g.node("ShaderNodeTexVoronoi", props={"voronoi_dimensions": "4D", "feature": feature}, Vector=vec.outputs[0], W=w, Scale=1.0)
        return n.outputs["Distance"], (n.outputs["Color"] if "Color" in n.outputs else None)
    n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=vec.outputs[0], W=w, Scale=1.0, Detail=detail, Roughness=rough)
    return n.outputs["Fac"], n.outputs["Color"]


def warp(g, u, v, amount=0.012, scale=40.0, seed=71.0):
    """Hand-made edges: the coordinates wobble by a few millimetres (seamless noise), so every
    brick, plank and tile outline is slightly irregular instead of ruler-straight."""
    wu, _ = torus_noise(g, u, v, scale, 3.0, 0.6, seed=seed)
    wv, _ = torus_noise(g, u, v, scale, 3.0, 0.6, seed=seed + 1.0)
    return g.math("ADD", u, g.math("MULTIPLY", g.math("SUBTRACT", wu, 0.5), amount * 2)), g.math("ADD", v, g.math("MULTIPLY", g.math("SUBTRACT", wv, 0.5), amount * 2))


def courses(g, u, v, w, h, mortar, stagger=0.5, soft=0.35, ragged=0.006):
    """Running-bond blocks w x h with joints: (joint mask 1 = mortar, cell u, cell v, distance to joint)."""
    if ragged: u, v = warp(g, u, v, ragged)
    row = g.math("FLOOR", g.math("DIVIDE", v, h))
    shift = g.math("MULTIPLY", g.math("MODULO", row, 2.0), stagger * w)
    us = g.math("ADD", u, shift)
    cu = g.math("FLOOR", g.math("DIVIDE", us, w))
    fu = g.math("SUBTRACT", g.math("DIVIDE", us, w), cu)
    fv = g.math("SUBTRACT", g.math("DIVIDE", v, h), row)
    du = g.math("MULTIPLY", g.math("MINIMUM", fu, g.math("SUBTRACT", 1.0, fu)), w)
    dv = g.math("MULTIPLY", g.math("MINIMUM", fv, g.math("SUBTRACT", 1.0, fv)), h)
    d = g.math("MINIMUM", du, dv)
    joint = g.smooth(g.math("DIVIDE", d, mortar), 1.0 + soft, 0.0)
    return joint, cu, row, d


def cell_rand(g, a, b, seed):
    vec = g.node("ShaderNodeCombineXYZ", X=a, Y=b, Z=seed)
    n = g.node("ShaderNodeTexWhiteNoise", props={"noise_dimensions": "3D"}, Vector=vec.outputs[0])
    return n.outputs["Value"], n.outputs["Color"]


def cell_colour(g, base, alt, cu, row, seed, hue_var=0.03, val_var=0.25):
    """Each cell picks between base and alt, then shifts its own hue and value a little (the per-brick
    variation of real masonry)."""
    r, rc = cell_rand(g, cu, row, seed)
    col = g.mix(r, base, alt)
    rsep = g.node("ShaderNodeSeparateColor", Color=rc)
    hue = g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SUBTRACT", rsep.outputs[0], 0.5), hue_var * 2))
    val = g.math("ADD", 1.0, g.math("MULTIPLY", g.math("SUBTRACT", rsep.outputs[1], 0.5), val_var * 2))
    return g.hsv(col, hue, 1.0, val)


# --- the realism stack --------------------------------------------------------------------------
def finish(g, alb, height, rough, cav, *, macro=0.12, grime=0.35, grime_col=(0.2, 0.18, 0.15, 1), wear=0.0, wear_col=(0.8, 0.78, 0.74, 1),
           scratches=0.0, scratch_col=(0.9, 0.9, 0.9, 1), detail=0.08, rough_var=0.15, metallic=0.0):
    """The shared finishing passes on a base (albedo, height 0..1, roughness, cavity with 1 = exposed)."""
    g.section("Realism stack: macro tone, grime, wear, scratches, detail")
    u, v = uv(g)
    mac, _ = torus_noise(g, u, v, 1.0, 2.0, 0.5, seed=21.0)
    tone = g.math("ADD", 1.0, g.math("MULTIPLY", g.math("SUBTRACT", mac, 0.5), macro * 2))
    alb = g.mix(1.0, alb, g.gray(tone), "MULTIPLY")
    # cavity grime: dirt in joints and pores, modulated by noise
    gn, _ = torus_noise(g, u, v, 3.0, 5.0, 0.6, seed=33.0)
    gmask = g.math("MULTIPLY", g.smooth(g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav), 1.4), g.math("MULTIPLY", gn, 0.8)), 0.45, 1.1), grime, clamp=True)
    # blotch grime: patches of soot and damp (high-detail noise, soft threshold) spreading over faces too,
    # heavier where the surface is also recessed; plus faint vertical run-off streaks
    bn, _ = torus_noise(g, u, v, 5.0, 8.0, 0.7, seed=34.0)
    streak, _ = torus_noise(g, u, v, 6.0, 4.0, 0.5, seed=35.0, stretch=(1.0, 0.12))
    speck, _ = torus_noise(g, u, v, 90.0, 4.0, 0.7, seed=36.0)
    blotch = g.math("MULTIPLY", g.smooth(g.math("ADD", g.math("MULTIPLY", bn, 0.85), g.math("MULTIPLY", streak, 0.25)), 0.47, 0.7), grime * 1.5, clamp=True)
    blotch = g.math("MULTIPLY", blotch, g.math("ADD", 0.55, g.math("MULTIPLY", speck, 0.6)), clamp=True)   # soot is speckled, not a flat stain
    gmask = g.math("MAXIMUM", gmask, blotch)
    alb = g.mix(gmask, alb, grime_col)
    rough = g.math("ADD", rough, g.math("MULTIPLY", gmask, 0.2))
    if wear > 0:
        vd, _ = torus_noise(g, u, v, 90.0, kind="voronoi", seed=44.0)
        wn, _ = torus_noise(g, u, v, 4.0, 3.0, 0.5, seed=55.0)
        chip = g.math("MULTIPLY", g.smooth(vd, 0.2, 0.12), g.smooth(wn, 1.0 - wear * 0.9, 1.0 - wear * 0.9 + 0.08))
        chip = g.math("MULTIPLY", chip, g.smooth(cav, 0.6, 0.95), clamp=True)
        alb = g.mix(chip, alb, wear_col)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", chip, 0.35))
        rough = g.math("ADD", rough, g.math("MULTIPLY", chip, 0.1))
    if scratches > 0:
        ed, _ = torus_noise(g, u, v, 7.0, kind="voronoi", feature="DISTANCE_TO_EDGE", seed=66.0)
        sn, _ = torus_noise(g, u, v, 2.5, 3.0, 0.5, seed=77.0)
        line = g.math("MULTIPLY", g.smooth(ed, 0.012, 0.003), g.smooth(sn, 1.0 - scratches, 1.0 - scratches + 0.15), clamp=True)
        alb = g.mix(g.math("MULTIPLY", line, 0.7), alb, scratch_col)
        rough = g.math("SUBTRACT", rough, g.math("MULTIPLY", line, 0.25))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", line, 0.08))
    fn, _ = torus_noise(g, u, v, 70.0, 3.0, 0.6, seed=88.0)
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("SUBTRACT", fn, 0.5), detail))
    rn, _ = torus_noise(g, u, v, 12.0, 4.0, 0.6, seed=99.0)
    rough = g.math("MULTIPLY", rough, g.math("ADD", 1.0 - rough_var, g.math("MULTIPLY", rn, rough_var * 2)), clamp=True)
    return alb, height, rough, cav, metallic


# --- base recipes: (albedo, height 0..1, roughness, cavity) --------------------------------------
def bricks(g, base, alt, mortar_col, w=0.25, h=1.0 / 26, joint=0.011, hue_var=0.02, val_var=0.22, ragged=0.004):
    g.section("Bricks: courses with ragged edges, per-brick colour, speckle, mortar")
    u, v = uv(g)
    j, cu, row, d = courses(g, u, v, w, h, joint, ragged=ragged)
    face = cell_colour(g, base, alt, cu, row, 3.0, hue_var, val_var)
    n1, _ = torus_noise(g, u, v, 24.0, 6.0, 0.6)
    face = g.mix(g.math("MULTIPLY", n1, 0.3), face, (0.1, 0.08, 0.07, 1), "MULTIPLY")
    speck, _ = torus_noise(g, u, v, 120.0, 3.0, 0.7, seed=6.0)
    face = g.mix(g.math("MULTIPLY", speck, 0.35), face, (1.5, 1.45, 1.4, 1), "MULTIPLY")
    pits, _ = torus_noise(g, u, v, 160.0, kind="voronoi", seed=9.0)
    pit = g.smooth(pits, 0.12, 0.06)
    alb = g.mix(j, face, mortar_col)
    mortar_n, _ = torus_noise(g, u, v, 50.0, 4.0, 0.7, seed=5.0)
    alb = g.mix(g.math("MULTIPLY", j, 0.5), alb, g.gray(g.math("ADD", 0.7, g.math("MULTIPLY", mortar_n, 0.5))), "MULTIPLY")
    height = g.math("SUBTRACT", g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", n1, 0.12), 0.88), g.math("MULTIPLY", j, 0.8)), g.math("MULTIPLY", pit, 0.1))
    rough = g.math("ADD", g.math("ADD", 0.72, g.math("MULTIPLY", j, 0.2)), g.math("MULTIPLY", n1, 0.1))
    cav = g.math("SUBTRACT", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", j, 0.7)), g.math("MULTIPLY", pit, 0.3))
    return alb, height, rough, cav


def stucco(g, tone=0.86):
    g.section("Stucco: trowel texture, hairline cracks")
    u, v = uv(g)
    n1, _ = torus_noise(g, u, v, 30.0, 8.0, 0.65)
    n2, _ = torus_noise(g, u, v, 3.0, 4.0, 0.5, seed=2.0)
    trowel, _ = torus_noise(g, u, v, 9.0, 2.0, 0.4, seed=12.0, stretch=(3.0, 1.0))
    val = g.math("ADD", tone, g.math("MULTIPLY", g.math("SUBTRACT", n2, 0.5), 0.1))
    alb = g.gray(val)
    crack_d, _ = torus_noise(g, u, v, 2.0, kind="voronoi", feature="DISTANCE_TO_EDGE", seed=14.0)
    crack = g.math("MULTIPLY", g.smooth(crack_d, 0.006, 0.002), g.smooth(n2, 0.55, 0.65))
    alb = g.mix(g.math("MULTIPLY", crack, 0.6), alb, (0.3, 0.28, 0.25, 1))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", n1, 0.55), g.math("MULTIPLY", trowel, 0.45)), g.math("MULTIPLY", crack, 0.4))
    rough = g.math("ADD", 0.8, g.math("MULTIPLY", n1, 0.12))
    return alb, height, rough, g.math("SUBTRACT", g.math("ADD", 0.85, g.math("MULTIPLY", n1, 0.15)), g.math("MULTIPLY", crack, 0.5))


def lap_siding(g, board=0.18):
    g.section("Lap siding: boards, paint grain, drip shadow")
    u, v = uv(g)
    fv = g.math("FRACT", g.math("DIVIDE", v, board))
    lap = g.math("POWER", fv, 0.6)
    grain, _ = torus_noise(g, g.math("MULTIPLY", u, 0.12), v, 40.0, 6.0, 0.6)
    shadow = g.smooth(fv, 0.08, 0.02)
    val = g.math("SUBTRACT", g.math("ADD", 0.9, g.math("MULTIPLY", grain, 0.08)), g.math("MULTIPLY", shadow, 0.3))
    alb = g.gray(val)
    return alb, g.math("ADD", g.math("MULTIPLY", lap, 0.85), g.math("MULTIPLY", grain, 0.15)), g.math("ADD", 0.5, g.math("MULTIPLY", grain, 0.15)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", shadow, 0.5))


def planks(g, width=0.16, dark=(0.18, 0.12, 0.08, 1), light=(0.42, 0.29, 0.18, 1), vertical=True, knots=True):
    g.section("Planks: grain rings, per-plank tone, gaps, knots")
    u, v = uv(g)
    a, b = (u, v) if vertical else (v, u)
    cell = g.math("FLOOR", g.math("DIVIDE", a, width))
    fa = g.math("FRACT", g.math("DIVIDE", a, width))
    gap = g.smooth(g.math("DIVIDE", g.math("MINIMUM", fa, g.math("SUBTRACT", 1.0, fa)), 0.035), 1.0, 0.0)
    grain, _ = torus_noise(g, g.math("MULTIPLY", a, 6.0), g.math("MULTIPLY", b, 0.35), 6.0, 10.0, 0.75, seed=1.0)
    rings = g.smooth(g.math("FRACT", g.math("MULTIPLY", g.math("ADD", grain, g.math("MULTIPLY", a, 0.6)), 9.0)), 0.0, 1.0)
    wood = cell_colour(g, dark, light, cell, 0.0, 7.0, 0.02, 0.3)
    wood = g.mix(g.math("MULTIPLY", rings, 0.35), wood, (0.35, 0.28, 0.2, 1), "MULTIPLY")
    if knots:
        kd, _ = torus_noise(g, u, v, 3.0, kind="voronoi", seed=19.0)
        knot = g.smooth(kd, 0.08, 0.03)
        wood = g.mix(g.math("MULTIPLY", knot, 0.8), wood, (0.2, 0.12, 0.07, 1))
    alb = g.mix(gap, wood, (0.05, 0.035, 0.025, 1))
    height = g.math("SUBTRACT", g.math("ADD", 0.9, g.math("MULTIPLY", g.math("SUBTRACT", rings, 0.5), 0.12)), g.math("MULTIPLY", gap, 0.9))
    return alb, height, g.math("ADD", 0.58, g.math("MULTIPLY", rings, 0.2)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gap, 0.6))


def ashlar(g, base=(0.78, 0.74, 0.66, 1)):
    g.section("Ashlar: dressed stone courses, tool marks")
    u, v = uv(g)
    j, cu, row, d = courses(g, u, v, 0.5, 0.25, 0.006, 0.5)
    face = cell_colour(g, base, (0.66, 0.62, 0.55, 1), cu, row, 9.0, 0.02, 0.2)
    n1, _ = torus_noise(g, u, v, 14.0, 6.0, 0.6)
    tool, _ = torus_noise(g, u, v, 40.0, 2.0, 0.5, seed=23.0, stretch=(1.0, 6.0))
    alb = g.mix(j, g.mix(g.math("MULTIPLY", n1, 0.3), face, (0.5, 0.48, 0.44, 1), "MULTIPLY"), (0.6, 0.58, 0.54, 1))
    return alb, g.math("SUBTRACT", g.math("ADD", g.math("ADD", 0.86, g.math("MULTIPLY", n1, 0.08)), g.math("MULTIPLY", tool, 0.06)), g.math("MULTIPLY", j, 0.6)), g.math("ADD", 0.72, g.math("MULTIPLY", j, 0.15)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", j, 0.4))


def shingles(g, base, alt, w=0.33, h=0.14, gap=0.012, hue_var=0.01):
    g.section("Shingles: staggered tabs, granules")
    u, v = uv(g)
    j, cu, row, d = courses(g, u, v, w, h, gap, 0.5)
    fv = g.math("FRACT", g.math("DIVIDE", v, h))
    face = cell_colour(g, base, alt, cu, row, 5.0, hue_var, 0.3)
    gran, _ = torus_noise(g, u, v, 200.0, 2.0, 0.5, seed=8.0)
    alb = g.mix(g.math("MULTIPLY", gran, 0.4), face, (1.4, 1.4, 1.4, 1), "MULTIPLY")
    alb = g.mix(j, alb, (0.04, 0.04, 0.045, 1))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, fv), 0.6), g.math("MULTIPLY", gran, 0.1)), g.math("MULTIPLY", j, 0.5))
    return alb, height, g.math("ADD", 0.82, g.math("MULTIPLY", gran, 0.12)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", j, 0.6))


def barrel_tiles(g, base, alt, w=0.25, h=0.4, glaze=0.0):
    g.section("Barrel tiles: ridges, overlaps, per-tile tone, lichen")
    u, v = uv(g)
    fu = g.math("FRACT", g.math("DIVIDE", u, w))
    ridge = g.math("SINE", g.math("MULTIPLY", fu, math.pi))
    row = g.math("FLOOR", g.math("DIVIDE", v, h))
    fv = g.math("FRACT", g.math("DIVIDE", v, h))
    lip = g.smooth(fv, 0.0, 0.1)
    cell = g.math("FLOOR", g.math("DIVIDE", u, w))
    face = cell_colour(g, base, alt, cell, row, 11.0, 0.015, 0.1)
    n1, _ = torus_noise(g, u, v, 18.0, 5.0, 0.55)
    alb = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, ridge), 0.55), face, (0.1, 0.08, 0.07, 1), "MULTIPLY")
    lichen, _ = torus_noise(g, u, v, 5.0, 4.0, 0.6, seed=31.0)
    alb = g.mix(g.math("MULTIPLY", g.smooth(lichen, 0.62, 0.75), 0.5), alb, (0.45, 0.5, 0.3, 1))
    height = g.math("MULTIPLY", ridge, lip)
    rough = g.math("SUBTRACT", g.math("ADD", 0.72, g.math("MULTIPLY", n1, 0.12)), glaze)
    return alb, height, rough, g.math("ADD", 0.5, g.math("MULTIPLY", g.math("MULTIPLY", ridge, lip), 0.5))


def standing_seam(g, base=(0.85, 0.85, 0.85, 1)):
    g.section("Standing seam: panels, seams, oil-canning")
    u, v = uv(g)
    fu = g.math("FRACT", g.math("DIVIDE", u, 0.5))
    seam = g.smooth(g.math("ABSOLUTE", g.math("SUBTRACT", fu, 0.5)), 0.03, 0.015)
    can, _ = torus_noise(g, u, v, 2.0, 2.0, 0.4, stretch=(1.0, 4.0))
    alb = g.mix(g.math("MULTIPLY", can, 0.15), base, (0.6, 0.62, 0.63, 1))
    return alb, g.math("ADD", g.math("MULTIPLY", seam, 0.9), g.math("MULTIPLY", can, 0.1)), g.math("ADD", 0.32, g.math("MULTIPLY", can, 0.15)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", seam, 0.2))


def concrete(g, tone=0.62, slabs=0.0):
    g.section("Concrete: pores, patches, slab joints")
    u, v = uv(g)
    n1, _ = torus_noise(g, u, v, 40.0, 8.0, 0.65)
    n2, _ = torus_noise(g, u, v, 2.5, 4.0, 0.5, seed=3.0)
    pores, _ = torus_noise(g, u, v, 140.0, kind="voronoi")
    pit = g.smooth(pores, 0.1, 0.05)
    val = g.math("ADD", tone, g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", n1, 0.5), 0.1), g.math("MULTIPLY", g.math("SUBTRACT", n2, 0.5), 0.14)))
    j = None
    if slabs:
        j, _, _, _ = courses(g, u, v, slabs, slabs, 0.006, 0.0)
        val = g.math("SUBTRACT", val, g.math("MULTIPLY", j, 0.3))
    alb = g.mix(g.math("MULTIPLY", pit, 0.5), g.gray(val), (0.4, 0.4, 0.4, 1))
    height = g.math("SUBTRACT", g.math("ADD", 0.8, g.math("MULTIPLY", n1, 0.2)), g.math("MULTIPLY", pit, 0.3))
    cav = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", pit, 0.3))
    if j is not None:
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", j, 0.6))
        cav = g.math("SUBTRACT", cav, g.math("MULTIPLY", j, 0.4))
    return alb, height, g.math("ADD", 0.84, g.math("MULTIPLY", n1, 0.1)), cav


def cobbles(g):
    g.section("Cobbles: stones, joints, domes")
    u, v = uv(g)
    edge, _ = torus_noise(g, u, v, 14.0, kind="voronoi", feature="DISTANCE_TO_EDGE")
    _, col = torus_noise(g, u, v, 14.0, kind="voronoi")
    n1, _ = torus_noise(g, u, v, 30.0, 5.0, 0.6)
    joint = g.smooth(edge, 0.07, 0.0)
    shade = g.node("ShaderNodeSeparateColor", Color=col)
    stone = g.hsv(g.mix(shade.outputs[0], (0.36, 0.34, 0.31, 1), (0.54, 0.52, 0.47, 1)), g.math("ADD", 0.48, g.math("MULTIPLY", shade.outputs[1], 0.04)), 1.0, 1.0)
    alb = g.mix(joint, g.mix(g.math("MULTIPLY", n1, 0.35), stone, (0.3, 0.29, 0.27, 1), "MULTIPLY"), (0.16, 0.15, 0.13, 1))
    dome = g.math("POWER", g.math("SUBTRACT", 1.0, joint), 0.5)
    return alb, g.math("ADD", g.math("MULTIPLY", dome, 0.85), g.math("MULTIPLY", n1, 0.15)), g.math("ADD", 0.6, g.math("MULTIPLY", joint, 0.3)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", joint, 0.6))


def leaves(g, base=(0.13, 0.26, 0.09, 1), alt=(0.26, 0.4, 0.13, 1)):
    g.section("Hedge: leaf clumps")
    u, v = uv(g)
    dist, col = torus_noise(g, u, v, 60.0, kind="voronoi")
    n1, _ = torus_noise(g, u, v, 8.0, 4.0, 0.6)
    alb = g.mix(g.math("ADD", g.math("MULTIPLY", n1, 0.6), g.math("MULTIPLY", dist, 0.6)), base, alt)
    return alb, g.math("SUBTRACT", 1.0, dist), g.math("ADD", 0.7, g.math("MULTIPLY", dist, 0.2)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", dist, 0.7))


def tatami(g):
    g.section("Tatami: rush weave, cloth borders")
    u, v = uv(g)
    weave = g.math("SINE", g.math("MULTIPLY", v, 2 * math.pi / 0.006))
    n1, _ = torus_noise(g, u, v, 20.0, 4.0, 0.5)
    border = g.smooth(g.math("FRACT", g.math("DIVIDE", u, 1.0)), 0.045, 0.035)
    alb = g.mix(g.math("MULTIPLY", n1, 0.3), (0.62, 0.6, 0.38, 1), (0.5, 0.48, 0.28, 1))
    alb = g.mix(border, alb, (0.12, 0.14, 0.12, 1))
    return alb, g.math("ADD", 0.5, g.math("MULTIPLY", weave, 0.3)), 0.8, 0.95


def floor_tiles(g, size=0.5, base=(0.85, 0.84, 0.8, 1), alt=(0.78, 0.77, 0.73, 1)):
    g.section("Floor tiles: grout, veining")
    u, v = uv(g)
    j, cu, row, d = courses(g, u, v, size, size, 0.004, 0.0)
    face = cell_colour(g, base, alt, cu, row, 13.0, 0.01, 0.1)
    vein, _ = torus_noise(g, u, v, 4.0, 6.0, 0.7, seed=17.0, stretch=(1.0, 3.0))
    face = g.mix(g.math("MULTIPLY", g.smooth(vein, 0.55, 0.7), 0.3), face, (0.6, 0.6, 0.62, 1))
    alb = g.mix(j, face, (0.45, 0.44, 0.42, 1))
    return alb, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", j, 0.7)), g.math("ADD", 0.22, g.math("MULTIPLY", j, 0.6)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", j, 0.4))


# name: (recipe, bump strength, tintable, finish kwargs)
LIBRARY = {
    "brick_red": (lambda g: bricks(g, (0.27, 0.075, 0.045, 1), (0.36, 0.12, 0.07, 1), (0.5, 0.48, 0.44, 1)), 0.7, False, dict(grime=0.45, wear=0.3, wear_col=(0.55, 0.3, 0.2, 1))),
    "brick_london": (lambda g: bricks(g, (0.42, 0.3, 0.16, 1), (0.3, 0.22, 0.13, 1), (0.52, 0.5, 0.46, 1), hue_var=0.06, val_var=0.45), 0.7, False, dict(grime=0.6, wear=0.25, wear_col=(0.6, 0.5, 0.35, 1), grime_col=(0.12, 0.11, 0.1, 1))),
    "brick_painted": (lambda g: bricks(g, (0.9, 0.9, 0.88, 1), (0.8, 0.8, 0.78, 1), (0.86, 0.86, 0.84, 1), hue_var=0.0, val_var=0.14), 0.6, True, dict(grime=0.55, grime_col=(0.11, 0.08, 0.05, 1), wear=0.45, wear_col=(0.55, 0.32, 0.22, 1), scratches=0.2, scratch_col=(0.6, 0.55, 0.5, 1))),
    "stucco": (stucco, 0.3, True, dict(grime=0.3, detail=0.1)),
    "siding": (lap_siding, 0.6, True, dict(grime=0.2, scratches=0.2, wear=0.15, wear_col=(0.55, 0.45, 0.35, 1))),
    "cedar_planks": (lambda g: planks(g), 0.5, False, dict(grime=0.35, grime_col=(0.1, 0.08, 0.06, 1), scratches=0.1, scratch_col=(0.6, 0.5, 0.4, 1))),
    "yakisugi": (lambda g: planks(g, 0.2, (0.05, 0.045, 0.04, 1), (0.12, 0.1, 0.09, 1), knots=False), 0.7, False, dict(grime=0.2, grime_col=(0.02, 0.02, 0.02, 1), wear=0.2, wear_col=(0.3, 0.2, 0.12, 1))),
    "light_wood": (lambda g: planks(g, 0.12, (0.5, 0.37, 0.22, 1), (0.66, 0.5, 0.32, 1)), 0.35, False, dict(grime=0.2, scratches=0.15, scratch_col=(0.8, 0.7, 0.55, 1))),
    "ashlar": (lambda g: ashlar(g), 0.5, False, dict(grime=0.45, wear=0.25, wear_col=(0.85, 0.82, 0.75, 1))),
    "shingle_asphalt": (lambda g: shingles(g, (0.6, 0.6, 0.6, 1), (0.82, 0.82, 0.82, 1)), 0.7, True, dict(grime=0.3, grime_col=(0.25, 0.25, 0.22, 1))),
    "slate": (lambda g: shingles(g, (0.17, 0.19, 0.22, 1), (0.26, 0.28, 0.32, 1), 0.25, 0.2, 0.008, hue_var=0.03), 0.7, False, dict(grime=0.3, wear=0.15, wear_col=(0.4, 0.42, 0.45, 1), rough_var=0.25)),
    "terracotta": (lambda g: barrel_tiles(g, (0.55, 0.24, 0.13, 1), (0.64, 0.32, 0.17, 1)), 1.0, False, dict(grime=0.55, grime_col=(0.18, 0.13, 0.1, 1), wear=0.15, wear_col=(0.78, 0.5, 0.35, 1), macro=0.18)),
    "kawara": (lambda g: barrel_tiles(g, (0.17, 0.18, 0.2, 1), (0.25, 0.26, 0.28, 1), 0.25, 0.25, 0.35), 1.0, False, dict(grime=0.3, rough_var=0.2)),
    "standing_seam": (lambda g: standing_seam(g), 0.5, True, dict(grime=0.25, scratches=0.35, scratch_col=(0.95, 0.95, 0.95, 1), metallic=0.75, rough_var=0.2)),
    "concrete": (lambda g: concrete(g), 0.3, False, dict(grime=0.45, wear=0.2, wear_col=(0.8, 0.8, 0.78, 1))),
    "paving": (lambda g: concrete(g, 0.66, 0.5), 0.4, False, dict(grime=0.5, wear=0.25, wear_col=(0.82, 0.8, 0.76, 1), scratches=0.1, scratch_col=(0.3, 0.3, 0.3, 1))),
    "cobbles": (cobbles, 0.9, False, dict(grime=0.55, grime_col=(0.1, 0.1, 0.09, 1))),
    "hedge": (lambda g: leaves(g), 1.0, True, dict(grime=0.1, macro=0.2, detail=0.15)),
    "tatami": (tatami, 0.3, False, dict(grime=0.1, detail=0.03)),
    "floor_tiles": (lambda g: floor_tiles(g), 0.3, False, dict(grime=0.2, scratches=0.2, scratch_col=(0.6, 0.6, 0.6, 1), rough_var=0.1)),
    "parquet": (lambda g: planks(g, 0.09, (0.36, 0.22, 0.12, 1), (0.48, 0.31, 0.17, 1), vertical=False, knots=False), 0.3, False, dict(grime=0.15, scratches=0.25, scratch_col=(0.7, 0.6, 0.45, 1), rough_var=0.1)),
}


# --- building and baking -------------------------------------------------------------------------
def build_material(name):
    """The node graph for one library entry (also what a visible Blender session shows)."""
    recipe, strength, tintable, fin = LIBRARY[name]
    mat = bpy.data.materials.get("CFLIB_" + name) or bpy.data.materials.new("CFLIB_" + name)
    mat.use_nodes = True
    g = G(mat)
    alb, height, rough, cav = recipe(g)
    alb, height, rough, cav, metallic = finish(g, alb, height, rough, cav, **fin)
    g.section("Output: bump -> Principled BSDF")
    bump = g.node("ShaderNodeBump", Strength=strength, Distance=0.02, Height=height)
    bsdf = g.node("ShaderNodeBsdfPrincipled", Base_Color=alb, Normal=bump.outputs["Normal"], Metallic=metallic)
    if isinstance(rough, bpy.types.NodeSocket): g.nt.links.new(rough, bsdf.inputs["Roughness"])
    else: bsdf.inputs["Roughness"].default_value = rough
    out = g.node("ShaderNodeOutputMaterial")
    g.nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, alb, rough, cav, metallic, tintable


def bake_plane():
    me = bpy.data.meshes.new("BakePlane")
    me.from_pydata([(0, 0, 0), (TILE, 0, 0), (TILE, TILE, 0), (0, TILE, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for loop, co in zip(uvl.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    ob = bpy.data.objects.new("BakePlane", me)
    scene.collection.objects.link(ob)
    return ob


def bake(ob, mat, kind, image, socket=None):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    img_node = nt.nodes.new("ShaderNodeTexImage")
    img_node.image = image
    nt.nodes.active = img_node
    keep = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    if kind == "EMIT":
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(socket, em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        bpy.ops.object.bake(type="EMIT", margin=0)
        nt.nodes.remove(em)
        if keep is not None: nt.links.new(keep, out.inputs["Surface"])
    else:
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=0)
    nt.nodes.remove(img_node)


def bake_material(name, ob):
    mat, alb, rough, cav, metallic, tintable = build_material(name)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    def value_socket(v):
        if isinstance(v, bpy.types.NodeSocket): return v
        n = mat.node_tree.nodes.new("ShaderNodeValue")
        n.outputs[0].default_value = float(v)
        return n.outputs[0]

    def img(suffix, srgb):
        im = bpy.data.images.get(name + suffix)
        if im is None or im.size[0] != RES:
            if im is not None: bpy.data.images.remove(im)
            im = bpy.data.images.new(name + suffix, RES, RES, alpha=False, float_buffer=False)
        im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
        return im

    a = img("_albedo", True)
    bake(ob, mat, "EMIT", a, alb)
    nrm = img("_normal", False)
    bake(ob, mat, "NORMAL", nrm)
    r = img("_rough", False)
    bake(ob, mat, "EMIT", r, value_socket(rough))
    c = img("_cav", False)
    bake(ob, mat, "EMIT", c, value_socket(cav))
    px_r = np.array(r.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
    px_c = np.array(c.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
    orm_px = np.ones((RES, RES, 4), np.float32)
    orm_px[..., 0] = np.clip(px_c[..., 0], 0, 1)
    orm_px[..., 1] = np.clip(px_r[..., 0], 0.03, 1)
    orm_px[..., 2] = metallic
    orm = img("_orm", False)
    orm.pixels.foreach_set(orm_px.ravel())
    scene.render.image_settings.quality = 92
    for im, suffix, fmt in ((a, "_albedo", "JPEG"), (nrm, "_normal", "PNG"), (orm, "_orm", "JPEG")):
        im.filepath_raw = os.path.join(OUT, name + suffix + (".jpg" if fmt == "JPEG" else ".png"))
        im.file_format = fmt
        im.save()
    for im in (r, c): bpy.data.images.remove(im)
    print("MATERIAL", name, RES, "tintable" if tintable else "")
    return tintable


def main():
    if not LIVE:
        for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
    ob = bpy.data.objects.get("BakePlane") or bake_plane()
    scene.render.bake.margin = 0
    meta = {}
    for name in LIBRARY:
        if ONLY and name not in ONLY: continue
        meta[name] = {"tile_m": TILE, "tintable": bake_material(name, ob), "res": RES}
    mpath = os.path.join(OUT, "library.json")
    old = json.load(open(mpath)) if os.path.exists(mpath) else {}
    old.update(meta)
    json.dump(old, open(mpath, "w"), indent=1)
    if not LIVE:
        blend = os.path.abspath(os.path.join(OUT, "..", "..", "..", "tmp", "cityforge", "material_library.blend"))
        os.makedirs(os.path.dirname(blend), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend)


if not LIVE:
    main()
