"""PM_Asphalt: procedural asphalt reverse-engineered from Ryan King Art, "Procedural Asphalt Material (Blender
Tutorial)", 2022-06-30, 27:08, YouTube Eofg9SBcdBY (Blender 3.2 in the video). Use in the road tool: the road surface,
modifier socket "Asphalt Material".

Specification : tools/materials/reconstruction/asphalt/GRAPH_SPEC_all.md (node ids in labels / names below are the
                spec's: color_noise, cracks_voronoi, bump3 ...). Evidence classes A frame, B narration / recipe repo,
                C our implementation, D unresolved; every node carries its class in the custom property "pm_note".
Documentation : tools/materials/reconstruction/asphalt/README.md, NODES.md, DECISIONS.md, VALIDATION.md.

Materials (key "asphalt"):
  PM_Asphalt          the library material. The video's final graph (28 shader nodes, 4 reroutes, frames Color /
                      Cracks / Damage) with the values the narration tunes exposed as group inputs. A ColorRamp whose
                      stop is a control becomes the identical Map Range (2 linear stops black -> white) or Mix (colour
                      stops); everything else is node for node.
  PM_AsphaltTutorial  the same graph with the video's literal ColorRamp nodes and constants, no controls besides the
                      contract inputs and Pattern Size: the reference PM_Asphalt is checked against (VALIDATION.md).

Coordinates: the video feeds Texture Coordinate > Object into every texture on a 1 m-radius icosphere, so its
texture scales are already "per metre" (U7: radius 1 m assumed, class C). Here V = Object / Pattern Size (object
mode, the default and what the road tool uses) or the seamless 4D torus of UVMap x Tile Size (Use UV = 1, baking).
Textures that are 3D in the video are built with exact3d=True: object mode samples the same 3D Noise / Voronoi at the
same coordinates as the video, UV mode the 4D torus (decision AS2), its outputs remapped to the 3D nodes' value
distribution (UV_MATCH, AS17: Blender's 4D twins have a narrower spread). The pebble Voronoi is 4D in the video (W = 0), so
object mode keeps W = 0 and UV mode moves along the torus W. Blender 5.2 does not reproduce the video's exact patches
on a 1 m sphere (a view search found no match, VALIDATION.md): the look and statistics match, not the positions.
Version adaptation that changes the look: the 5.2-only Bump "Filter Width" is 1.0 (the 3.2 relief), not 0.1 (AS5).
"""
import sys

from . import core, register

KEY = "asphalt"
EXACT3D = True          # object mode samples the video's 3D textures (EEVEE evaluates the 3D and 4D twins of each)

# Bump "Filter Width" (an input Blender 3.2 does not have; 5.2 creates 0.1). Measured against the video's final render
# at its pixel scale: 1.0 reproduces the 3.2 relief contrast (mid-band 0.26 / 0.36 / 0.33 vs video 0.28 / 0.34 / 0.34),
# 0.1 gives about half (0.17 / 0.26 / 0.23): U13, decision AS5, VALIDATION.md
BUMP_FILTER_WIDTH = 1.0

# Pebble cells: Voronoi Scale 110 on the video's 1 m-radius sphere = cells of 1/110 m
AGGREGATE_DEFAULT = 1.0 / 110.0
DAMAGE_GAP = 0.442 - 0.35   # damage_mask_ramp: white stop (0.442, A) - black stop (0.35, C; U1)

# UV mode (Use UV = 1, the seamless bake path) samples the 4D twin of every 3D texture on the torus, and Blender's 4D
# Noise / Smooth F1 Voronoi have a narrower value spread than the 3D nodes (the base-cell Distance most: std 0.075 vs
# 0.104, mean 0.285 vs 0.310). The UV branch of each Dual is remapped linearly, out = gain x 4D + offset (gain = std3 /
# std4, offset = mean3 - gain x mean4; per channel for the noise colours, whose 3D channels differ), so UV mode has
# the object-mode distribution (audit ASP-1, decision AS17). Fitted by reconstruction/asphalt/scripts/uv_match.py:
# point samples (1 spp emission bakes) of a 32 m plane at 2048 px in both modes; the linear fit leaves quantile errors
# <= 0.003 (p5-p95). Object mode is untouched. key "<node id>.<output>": (gain, offset)
UV_MATCH = {
    "color_noise.Color": ((1.0169, 1.1138, 1.0719), (-0.0085, -0.0571, -0.0357)),
    "color_voronoi.Distance": (1.3796, -0.0825),
    "cracks_mask_noise.Fac": (1.0194, -0.0099),
    "cracks_warp_noise.Color": ((1.0200, 1.1300, 1.0674), (-0.0111, -0.0636, -0.0323)),
    "damage_warp_noise.Fac": (1.0156, -0.0080),
    "damage_mask_noise.Fac": (1.0236, -0.0110),
    "bump_noise.Fac": (1.0165, -0.0082),
}


def srgb(hexstr):
    """Blender's hex field (gamma-corrected sRGB) -> the linear RGBA a ColorRamp stop / colour socket stores."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out) + (1.0,)


COLOR_DARK = srgb("1A1817")    # color_ramp stop 0 (A, 06:12 caption; the recipe repo's #1A1A1A loses, U15)
COLOR_LIGHT = srgb("4D4D4D")   # color_ramp stop 1 (A, 06:28)
ROUGH_MIN = srgb("ABABAB")[0]  # rough_ramp stop 0 grey (A, 26:22) = 0.4072 linear
WHITE = (1.0, 1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0, 1.0)

# group inputs of PM_Asphalt: (name, type, default, min, max, description[, subtype]) - defaults are the video's values
CONTROLS = [
    ("Pattern Size", "FLOAT", 1.0, 0.05, 100.0,
     "Metres per unit of the video's object space (its sphere radius, 1 m assumed): 1 = the video's sizes "
     "(base cells 0.1 m, crack networks ~0.4 m, damage patches ~0.3 m); 2 = everything except the aggregate twice as large",
     "DISTANCE"),
    ("Aggregate Size", "FLOAT", AGGREGATE_DEFAULT, 0.001, 0.2,
     "Pebble size in metres in the damaged patches (video: Voronoi Scale 110 = 1/110 m = 9.1 mm); the fine bump grain "
     "(video Scale 60) follows it", "DISTANCE"),
    ("Colour", [
        ("Color Dark", "COLOR", COLOR_DARK, None, None, "Asphalt dark tone: base ramp stop 0 (video #1A1817)"),
        ("Color Light", "COLOR", COLOR_LIGHT, None, None, "Asphalt light tone: base ramp stop 1 (video #4D4D4D)"),
    ]),
    ("Cracks", [
        ("Crack Amount", "FLOAT", 0.499, 0.0, 1.0,
         "Share of the surface with cracks: the crack mask ramp's black stop (video 0.499); higher = more crack regions",
         "FACTOR"),
        ("Crack Width", "FLOAT", 0.094, 0.0, 1.0,
         "Width of the recessed crack grooves: the crack bump ramp's white stop (video 0.094); lower = thinner",
         "FACTOR"),
    ]),
    ("Damage", [
        ("Damage Amount", "FLOAT", 0.35, 0.0, 1.0,
         "Share of the surface broken away to the pebbles: the damage mask ramp's black stop (video ~0.35; its white "
         "stop follows at +0.092); higher = more and larger damaged patches", "FACTOR"),
        ("Damage Darkness", "FLOAT", 0.338, 0.0, 1.0,
         "Darkening of the damaged patches: the damage ramp's black stop (video 0.338); higher = darker", "FACTOR"),
    ]),
    ("Surface", [
        ("Roughness Min", "FLOAT", ROUGH_MIN, 0.0, 1.0,
         "Roughness at the base cell edges, rising to 1 in the cell centres (video #ABABAB = 0.407 linear); lower = "
         "shinier / wet", "FACTOR"),
        ("Bump Grain", "FLOAT", 0.1, 0.0, 1.0, "Strength of the fine grain bump (video bump 1: 0.1)", "FACTOR"),
        ("Bump Cells", "FLOAT", 0.2, 0.0, 1.0, "Strength of the base cell undulation (video bump 2: 0.2)", "FACTOR"),
        ("Bump Cracks", "FLOAT", 0.3, 0.0, 1.0, "Depth of the crack grooves (video bump 3: 0.3)", "FACTOR"),
        ("Bump Damage", "FLOAT", 0.4, 0.0, 1.0, "Relief of the damaged patches and pebbles (video bump 4: 0.4)", "FACTOR"),
        ("Bump Filter Width", "FLOAT", BUMP_FILTER_WIDTH, 0.0, 10.0,
         "Finite-difference width of the four Bump nodes in pixels (not in Blender 3.2): 1 = the video's relief, 0.1 = "
         "the Blender 5.2 default (about half the relief contrast)"),
    ]),
]

TUTORIAL_CONTROLS = [CONTROLS[0]]   # PM_AsphaltTutorial: only the metre conversion (+ the contract inputs)


# ======================================================================================== helpers
def _tag(obj, node_id, note):
    """Name / label / evidence note for a node, a Dual (3D + 4D twin) or the node of an output socket."""
    if isinstance(obj, core.Dual):
        for n, suffix in ((obj.n3, "_3d"), (obj.n4, "_4d")):
            n.name = node_id + suffix; n.label = node_id; n["pm_note"] = note
        return obj
    n = obj.node if hasattr(obj, "node") and not hasattr(obj, "inputs") else obj
    n.name = node_id; n.label = node_id; n["pm_note"] = note
    return obj


def _reroute(G, src, node_id, note):
    """The video's reroutes (layout only, functionally transparent): Object -> textures of one frame."""
    r = G.node("NodeReroute", name=node_id, note=note)
    G.link(src, r.inputs[0])
    return r.outputs[0]


def _uv_match(G, tex, node_id, keys):
    """UV branch of a Dual remapped to the 3D node's distribution (UV_MATCH, AS17): installs, for each output key,
    Mix(Use UV, 3D, gain x 4D + offset) as the Dual's output. A single 4D node (exact3d=False) is left as it is."""
    if not isinstance(tex, core.Dual): return tex
    for key in keys:
        gain, off = UV_MATCH["%s.%s" % (node_id, key)]
        s3 = core.find_socket(tex.n3.outputs, key, tex.n3); s4 = core.find_socket(tex.n4.outputs, key, tex.n4)
        if isinstance(gain, tuple):
            m = G.vmath("MULTIPLY_ADD", s4, gain, off); t = "RGBA"
        else:
            m = G.math("MULTIPLY_ADD", s4, gain, off, clamp=True); t = "FLOAT"
        n = m.node; n.name = node_id + "_uvmatch_" + key.lower(); n.label = node_id + " UV match"
        n["pm_note"] = ("C (AS17, audit ASP-1): UV mode only: 4D %s x %s + %s = the 3D node's distribution "
                        "(uv_match.py); object mode does not use it" % (key, gain, off))
        tex._mixed[key] = G.mix(tex.use, s3, m, t, label="object 3D | UV 4D")
    return tex


def _ramp_bw(G, literal, fac, lo, hi, node_id, note):
    """A 2-stop linear ColorRamp black@lo -> white@hi. literal: the ColorRamp node with the video's stops (floats);
    otherwise a clamped linear Map Range lo..hi -> 0..1 (identical maths; lo / hi may be sockets = controls).
    Returns the output socket (Color of the ramp, Result of the Map Range)."""
    if literal:
        n = G.ramp(fac, ((lo, BLACK), (hi, WHITE)))
        _tag(n, node_id, note)
        return n.outputs["Color"]
    out = G.map_range(fac, lo, hi, 0.0, 1.0, clamp=True)
    _tag(out.node, node_id, note + " | ColorRamp black@lo -> white@hi as a clamped linear Map Range (identical, C)")
    return out


def _bump(G, height, strength, normal, node_id, note, filter_width=BUMP_FILTER_WIDTH):
    out = G.bump(height, strength, 1.0, normal=normal)       # Distance 1.0 (A); 5.2 creates 0.001 (U13)
    n = out.node
    if "Filter Width" in n.inputs: G.set(n, "Filter Width", filter_width)   # 5.x only (C, AS5)
    _tag(n, node_id, note)
    return out


# ======================================================================================== the graph
def build_group(name="Asphalt", literal=False, exact3d=EXACT3D):
    """PM_<name>: the video's final graph. literal=True keeps its ColorRamp nodes and constants (PM_AsphaltTutorial);
    literal=False exposes the tuned values as inputs (PM_Asphalt). Returns the tree."""
    G = core.new_group(name, inputs=TUTORIAL_CONTROLS if literal else CONTROLS, outputs=("BSDF", "Albedo"), scale=None)
    I = G.I
    # V = Object / Pattern Size (object mode) or the UV torus x 1 / Pattern Size (UV mode): the core's Coordinates with
    # a computed scale socket (a metre size control rather than a multiplier)
    inv = G.div(1.0, I("Pattern Size"))
    _tag(inv.node, "pattern_scale", "C: 1 / Pattern Size multiplies every texture coordinate (V, W); 1 = the video's object space")
    G.coords = C = core.Coordinates(G, "Use UV", "Tile Size", inv, "UVMap")
    if literal:
        pebble_scale, grain_scale = 110.0, 60.0
    else:
        ratio = G.div(I("Pattern Size"), I("Aggregate Size"))      # V is already divided by Pattern Size
        _tag(ratio.node, "aggregate_scale",
             "C: Pattern Size / Aggregate Size = the pebble Voronoi Scale (110 at the defaults: 1 / (1/110 m))")
        pebble_scale = ratio
        grain_scale = G.mul(ratio, 60.0 / 110.0)
        _tag(grain_scale.node, "grain_scale", "C: bump grain Scale = 60/110 x pebble Scale (60 at the defaults)")

    # -------------------------------------------------------------------- Color frame (spec section 2, A)
    with G.frame("Color"):
        V = _reroute(G, C.V, "rr_color", "A 08:41-08:56; 26:32 (layout only)")
        at = (V, C.W)
        color_noise = C.noise4(18.0, 15.0, 0.6, 2.0, 0.0, at=at, exact3d=exact3d)
        _tag(color_noise, "color_noise", "A 03:22-03:49; 26:32: Noise 3D Scale 18 Detail 15 Roughness 0.6 Distortion 0")
        _uv_match(G, color_noise, "color_noise", ("Color",))
        Vw, Ww = C.warp(color_noise.outputs["Color"], 0.1, at=at)
        _tag(Vw.node, "color_warp_mix", "A 03:55-04:49; 26:32: MixRGB Linear Light Fac 0.1, Clamp off, Color1 Object, "
                                        "Color2 Noise Color (5.2: Mix RGBA, C)")
        color_voronoi = C.voronoi4(10.0, "SMOOTH_F1", "MINKOWSKI", 1.0, exponent=32.0, smoothness=1.0, at=(Vw, Ww),
                                   exact3d=exact3d)
        _tag(color_voronoi, "color_voronoi", "A 02:48-03:10, 05:06; 26:32: Voronoi 3D Smooth F1 Minkowski Scale 10 "
                                             "Smoothness 1 Exponent 32 Randomness 1")
        _uv_match(G, color_voronoi, "color_voronoi", ("Distance",))
        dist = color_voronoi.outputs["Distance"]       # drives the base colour, Bump 2 and the roughness (A)
        if literal:
            n = G.ramp(dist, ((0.0, COLOR_DARK), (1.0, COLOR_LIGHT)))
            _tag(n, "color_ramp", "A 05:25-06:30; 26:32: #1A1817 @ 0 -> #4D4D4D @ 1, RGB, Linear")
            base = n.outputs["Color"]
        else:
            base = G.mixc(dist, I("Color Dark"), I("Color Light"))
            _tag(base.node, "color_ramp", "A 05:25-06:30: ColorRamp #1A1817 @ 0 -> #4D4D4D @ 1 as Mix(Color Dark, "
                                          "Color Light) by the clamped Distance (identical, C)")

    # -------------------------------------------------------------------- Cracks frame
    with G.frame("Cracks"):
        V = _reroute(G, C.V, "rr_cracks", "A 08:58-09:06; 26:32 (layout only)")
        at = (V, C.W)
        mask_noise = C.noise4(4.5, 15.0, 0.5, 2.0, 0.0, at=at, exact3d=exact3d)
        _tag(mask_noise, "cracks_mask_noise", "A 08:29-08:41, 10:20-10:28; 26:32: Noise 3D Scale 4.5 Detail 15 Roughness 0.5")
        _uv_match(G, mask_noise, "cracks_mask_noise", ("Fac",))
        mask = _ramp_bw(G, literal, mask_noise.outputs["Fac"], 0.499 if literal else I("Crack Amount"), 1.0,
                        "cracks_mask_ramp", "A 09:18-09:38, 17:08; 26:32: black @ 0.499 -> white @ 1.0 on the noise Fac")
        warp_noise = C.noise4(2.5, 15.0, 0.5, 2.0, 0.0, at=at, exact3d=exact3d)
        _tag(warp_noise, "cracks_warp_noise", "A 07:46-08:09; 26:32: Noise 3D Scale 2.5 Detail 15 Roughness 0.5; "
                                              "its Color goes straight into the Voronoi Vector")
        _uv_match(G, warp_noise, "cracks_warp_noise", ("Color",))
        vor = G.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="DISTANCE_TO_EDGE", distance="EUCLIDEAN")
        G.set(vor, "Vector", warp_noise.outputs["Color"]); G.set(vor, "Scale", 5.0); G.set(vor, "Randomness", 1.0)
        _tag(vor, "cracks_voronoi", "A 07:15-07:34; 26:32: Voronoi 3D Distance to Edge Scale 5 Randomness 1 (metric "
                                    "hidden, Euclidean C). 3D in both modes: its Vector is a noise colour, periodic in UV mode")
        cracks = G.mixc(mask, vor.outputs["Distance"], WHITE)
        _tag(cracks.node, "cracks_mix", "A 09:41-10:06; 26:32: MixRGB Mix, Fac = mask ramp, Color1 = Voronoi Distance, "
                                        "Color2 = #FFFFFF, Clamp off")

    # -------------------------------------------------------------------- Damage frame
    with G.frame("Damage"):
        V = _reroute(G, C.V, "rr_damage", "A 12:18-12:27, 14:12; 26:32 (layout only)")
        at = (V, C.W)
        dwarp = C.noise4(20.0, 15.0, 0.6, 2.0, 0.0, at=at, exact3d=exact3d)
        _tag(dwarp, "damage_warp_noise", "A 11:53-12:59; 26:32: Noise 3D Scale 20 Detail 15 Roughness 0.6")
        _uv_match(G, dwarp, "damage_warp_noise", ("Fac",))
        Vp, Wp = C.warp(dwarp.outputs["Fac"], 0.02, at=at)
        _tag(Vp.node, "damage_warp_mix", "A 12:06-13:30; 26:32: MixRGB Linear Light Fac 0.02, Color1 Object, Color2 = "
                                         "noise Fac (scalar: equal offset on X, Y, Z)")
        pebbles = C.voronoi4(pebble_scale, "DISTANCE_TO_EDGE", "EUCLIDEAN", 1.0, at=(Vp, Wp))
        _tag(pebbles, "damage_voronoi", "A 10:58-11:38; 26:32: Voronoi 4D Distance to Edge W 0 Scale 110 Randomness 1 "
                                        "(object mode W = 0 exactly; UV mode W = the torus W)")
        dmask_noise = C.noise4(3.5, 15.0, 0.5, 2.0, 0.0, at=at, exact3d=exact3d)
        _tag(dmask_noise, "damage_mask_noise", "A 13:45-14:12; 26:32: Noise 3D Scale 3.5 Detail 15 Roughness 0.5")
        _uv_match(G, dmask_noise, "damage_mask_noise", ("Fac",))
        if literal:
            dlo, dhi = 0.35, 0.442
        else:
            dlo = I("Damage Amount"); dhi = G.add(dlo, DAMAGE_GAP)
            _tag(dhi.node, "damage_mask_white", "C: white stop = Damage Amount + 0.092 (the video's 0.35 -> 0.442 gap)")
        dmask = _ramp_bw(G, literal, dmask_noise.outputs["Fac"], dlo, dhi, "damage_mask_ramp",
                         "C/A 14:17-14:57; 26:32: black @ 0.35 (C: 0.343 last legible before a jump cut, 0.350 measured "
                         "after, U1) -> white @ 0.442 (A)")
        lighten = G.mixc(1.0, pebbles.outputs["Distance"], dmask, "LIGHTEN")
        _tag(lighten.node, "damage_lighten", "A 15:05-15:30; 26:32: MixRGB Lighten Fac 1, Color1 = pebbles, Color2 = mask")

    # -------------------------------------------------------------------- combine (no frame in the video)
    darken1 = G.mixc(1.0, base, cracks, "DARKEN")
    _tag(darken1.node, "darken_cracks", "A 16:11-16:47; 26:32: MixRGB Darken Fac 1, Color1 = base ramp, Color2 = cracks mix")
    ddark = _ramp_bw(G, literal, lighten, 0.338 if literal else I("Damage Darkness"), 1.0, "damage_dark_ramp",
                     "A 17:52-18:11; 26:32: black @ 0.338 -> white @ 1.0 on the Lighten result")
    albedo = G.mixc(1.0, darken1, ddark, "DARKEN")
    _tag(albedo.node, "darken_damage", "A 17:15-17:29, 18:22; 26:32: MixRGB Darken Fac 1 -> Principled Base Color")

    # -------------------------------------------------------------------- bump chain and roughness (no frame)
    V = _reroute(G, C.V, "rr_bump", "A 19:05-19:15; 26:32 (layout only)")
    bump_noise = C.noise4(grain_scale, 15.0, 0.4, 2.0, 0.0, at=(V, C.W), exact3d=exact3d)
    _tag(bump_noise, "bump_noise", "A 18:42-19:46; 26:32: Noise 3D Scale 60 Detail 15 Roughness 0.4")
    _uv_match(G, bump_noise, "bump_noise", ("Fac",))
    st = (0.1, 0.2, 0.3, 0.4) if literal else (I("Bump Grain"), I("Bump Cells"), I("Bump Cracks"), I("Bump Damage"))
    fw = BUMP_FILTER_WIDTH if literal else I("Bump Filter Width")
    n1 = _bump(G, bump_noise.outputs["Fac"], st[0], None, "bump1",
               "A 20:20-20:44; 26:32: Strength 0.1 Distance 1.0, Height = bump noise Fac", fw)
    n2 = _bump(G, dist, st[1], n1, "bump2", "A 20:58-21:40; 26:32: Strength 0.2 Distance 1.0, Height = base (Smooth F1) "
                                            "Voronoi Distance (frame wins over the recipe repo, U16)", fw)
    crack_h = _ramp_bw(G, literal, cracks, 0.0, 0.094 if literal else I("Crack Width"), "crack_bump_ramp",
                       "A 22:45-23:28; 26:32: black @ 0 -> white @ 0.094 on the cracks mix")
    n3 = _bump(G, crack_h, st[2], n2, "bump3", "A 21:52-22:20; 26:32: Strength 0.3 Distance 1.0", fw)
    n4 = _bump(G, lighten, st[3], n3, "bump4", "A 24:04-24:40; 26:32: Strength 0.4 Distance 1.0, Height = damage Lighten", fw)
    if literal:
        n = G.ramp(dist, ((0.0, srgb("ABABAB")), (1.0, WHITE)))
        _tag(n, "rough_ramp", "A 25:47-26:29; 26:32: #ABABAB @ 0 -> #FFFFFF @ 1 on the base Voronoi Distance")
        rough = n.outputs["Color"]
    else:
        rough = G.map_range(dist, 0.0, 1.0, I("Roughness Min"), 1.0, clamp=True)
        _tag(rough.node, "rough_ramp", "A 25:47-26:29: ColorRamp #ABABAB @ 0 -> #FFFFFF @ 1 as Map Range 0..1 -> "
                                       "Roughness Min..1 (identical, C)")
    bsdf = G.principled(**{"Base Color": albedo, "Roughness": rough, "Normal": n4, "Metallic": 0.0, "IOR": 1.5,
                           "Specular IOR Level": 0.5, "Subsurface Weight": 0.0, "Coat Weight": 0.0,
                           "Sheen Weight": 0.0, "Transmission Weight": 0.0})
    bsdf.distribution = "GGX"                                   # A (5.2 default MULTI_GGX)
    try: bsdf.subsurface_method = "RANDOM_WALK"                  # A (no effect at weight 0)
    except (TypeError, AttributeError): pass
    _tag(bsdf, "principled", "A 06:43, 18:22; 26:32: GGX, Random Walk, Specular 0.5 / IOR 1.45 (3.2) -> IOR 1.5 + "
                             "Specular IOR Level 0.5 (same F0 0.04, C), other weights 0")
    G.out("BSDF", bsdf)
    G.out("Albedo", albedo)
    return G.finish()


# viewport colour / roughness (also the road tool's glTF fallback for non-MRS materials): the means of the 4 m UV-mode
# bake at the defaults (after AS17), albedo (0.0278, 0.0271, 0.0267) linear and roughness 0.593 (VALIDATION.md)
VIEWPORT = (0.0278, 0.0271, 0.0267, 1.0)
VIEWPORT_ROUGHNESS = 0.59


def build():
    mats = []
    g = build_group("Asphalt", literal=False)
    mats.append(core.contract_material("Asphalt", g, viewport=VIEWPORT, roughness=VIEWPORT_ROUGHNESS))
    t = build_group("AsphaltTutorial", literal=True)
    mats.append(core.contract_material("AsphaltTutorial", t, viewport=VIEWPORT, roughness=VIEWPORT_ROUGHNESS))
    for m in mats:
        m["pm_source"] = "Ryan King Art, Procedural Asphalt Material (Blender Tutorial), 2022, YouTube Eofg9SBcdBY"
        m["pm_road_socket"] = "Asphalt Material"
    return mats


register(sys.modules[__name__])
