"""PM_Cobblestone: procedural cobblestone ground reverse-engineered from Ryan King Art, "Procedural Cobblestone Ground
Material (Blender Tutorial)", 2026-01-12, 40:41, YouTube 30vbbpy9zwg (Blender 5.0.1 in the video). Use in the road
tool: paving, plazas and old streets (modifier socket "Paving Material"; also an "Asphalt Material" for a cobbled
street).

Specification : tools/materials/reconstruction/cobblestone/GRAPH_SPEC_b.md (final group, node ids used below) and
                GRAPH_SPEC_a.md (the build; its typed ramp positions / grey win over segment b's bar measurements,
                decision a2). Evidence classes A frame, B narration, C our implementation, D unresolved; every node
                carries its class in the custom property "pm_note".
Documentation : tools/materials/reconstruction/cobblestone/README.md, NODES.md, DECISIONS.md, VALIDATION.md.

Materials (key "cobblestone"), both on the ONE group PM_Cobblestone (the video's 36 controls + Pattern Size + the
contract inputs Use UV / Tile Size):
  PM_Cobblestone           library / road material: the group's Displacement output feeds Material Output >
                           Displacement with displacement_method BUMP (road meshes are coarse: the stone relief
                           becomes bump, decision CB1).
  PM_CobblestoneDisplaced  the video's setup: displacement_method BOTH ("Displacement and Bump", A 25:42 / 26:51) for
                           dense meshes (preview sphere, plane_hd).

Coordinates: the video feeds Texture Coordinate > Object -> Mapping (Scale <- Material Scale) into every texture on a
0.5 m-radius icosphere (scale applied), so its texture scales are "per metre" as they stand (Voronoi Scale 7 = cells
of about 1/7 m). Here V = Object x Material Scale / Pattern Size in object mode (Pattern Size 1 m = the video), or the
seamless 4D torus of UVMap x Tile Size (Use UV = 1, baking). All textures are 3D in the video: they are built with
exact3d=True, so object mode samples the same 3D Noise / Voronoi at the same coordinates as the video and UV mode
samples the 4D torus (decision CB2).
"""
import sys

from . import core, register

KEY = "cobblestone"
EXACT3D = True
FLT_MAX = 3.4028234663852886e38


def srgb(hexstr):
    """Blender's hex field (display sRGB) -> linear RGBA (what a colour socket / ramp stop stores)."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out) + (1.0,)


WHITE = (1.0, 1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0, 1.0)

# Colour ramp stops (spec a typed values, A; decision a2 over segment b's measured 0.155 / 0.314 / 0.469 / 0.645 / 0.02)
CELL_RAMP = ((0.0, srgb("999999")), (0.035, BLACK))         # A 21:42-21:57: stones grey 0.3185 linear, joints black
FINAL_RAMP = ((0.0, BLACK), (0.03, WHITE))                   # A 24:04-24:20
DIRT_COLOR_RAMP = ((0.151, BLACK), (0.553, WHITE))           # A 8:19-8:22
DIRT_ROUGH_RAMP = ((0.0, srgb("D2D2D2")), (1.0, WHITE))      # A 9:12 / 9:35
DMOSS_RAMP = ((0.467, BLACK), (1.0, WHITE))                  # A 10:46-11:04
DMOSS_SHARP_RAMP = ((0.0, BLACK), (0.324, WHITE))            # A 12:10-12:15
RMMASK_RAMP = ((0.407, BLACK), (0.651, WHITE))               # A 18:49-18:53

F = "FACTOR"
# Group inputs: (name, type, default, min, max, description[, subtype]); defaults / ranges / subtypes are the
# tutorial group's (segment b, A); colours are the typed hex values (B+A)
CONTROLS = [
    ("Material Scale", "FLOAT", 1.0, -FLT_MAX, FLT_MAX,
     "Tutorial Mapping Scale: multiplies every texture coordinate (2 = everything half as large)"),
    ("Pattern Size", "FLOAT", 1.0, 0.01, 100.0,
     "Metres per unit of the tutorial's object space (its 1 m-diameter sphere): 1 = the video's sizes, stones about "
     "1 / Cobblestone Scale = 0.14 m; 2 = everything twice as large (procmat metre control, C)", "DISTANCE"),
    ("Rock Distortion", [
        ("Distortion Scale", "FLOAT", 2.0, -1000.0, 1000.0, "Scale of the noise that distorts the stone outlines"),
        ("Distortion Detail 1", "FLOAT", 7.0, 0.0, 15.0, "Detail of the distortion noise (more / less ragged edges)"),
        ("Distortion Detail 2", "FLOAT", 0.5, 0.0, 1.0, "Roughness of the distortion noise", F),
        ("Distortion Strength", "FLOAT", 0.2, 0.0, 1.0, "0 = round smooth stones, higher = chunky random shapes", F),
    ]),
    ("Dirt & Moss", [
        ("Dirt Scale", "FLOAT", 20.0, -1000.0, 1000.0, "Scale of the dirt noise in the joints"),
        ("Dirt Moss Scale", "FLOAT", 25.0, -1000.0, 1000.0, "Scale of the moss on the dirt"),
        ("Dirt Color 1", "COLOR", srgb("332C24"), None, None, "First dirt colour (#332C24)"),
        ("Dirt Color 2", "COLOR", srgb("19140F"), None, None, "Second, darker dirt colour (#19140F)"),
        ("Dirt Moss Color", "COLOR", srgb("232511"), None, None, "Colour of the moss on the dirt (#232511)"),
        ("Dirt Roughness", "FLOAT", 1.0, 0.0, 2.0, "Value multiplier of the dirt roughness (lower = shinier dirt)"),
        ("Dirt Detail 1", "FLOAT", 10.0, 0.0, 15.0, "Detail of the dirt noise"),
        ("Dirt Detail 2", "FLOAT", 0.55, 0.0, 1.0, "Roughness of the dirt noise", F),
        ("Dirt Moss Detail 1", "FLOAT", 9.0, 0.0, 15.0, "Detail of the dirt moss noise"),
        ("Dirt Moss Detail 2", "FLOAT", 0.5, 0.0, 1.0, "Roughness of the dirt moss noise", F),
        ("Dirt Moss Visibility", "FLOAT", 1.0, 0.0, 2.0, "More (up) or less (down) moss on the dirt"),
        ("Dirt Bump Strength", "FLOAT", 1.0, 0.0, 1.0, "Bump of the dirt", F),
        ("Dirt Moss Bump Strength", "FLOAT", 1.0, 0.0, 1.0, "Bump of the moss on the dirt", F),
    ]),
    ("Cobblestone Chunks", [
        ("Cobblestone Scale", "FLOAT", 7.0, -1000.0, 1000.0, "Stones per unit of object space (7 = about 0.14 m stones)"),
        ("Cobblestone Cracks", "FLOAT", 0.0, 0.0, 15.0, "Voronoi detail: little cracks / chunks in the stones (~1 recommended)"),
        ("Cobblestone Visibility", "FLOAT", 1.0, 0.0, 1.0, "Lower = the stones sink back into the dirt", F),
        ("Cobblestone Alignment", "FLOAT", 1.0, 0.0, 1.0, "Voronoi randomness: lower = more aligned rows", F),
        ("Cobblestone Individual Size", "FLOAT", 0.6, 0.0, 1.0, "Smooth F1 smoothness: lower = bigger stones / narrower joints, higher = smaller stones", F),
        ("Displacement Strength", "FLOAT", 0.02, 0.0, 1000.0,
         "Displacement Scale (object space, m per unit height; the stone height is 0.3185 x this = 6.4 mm)"),
    ]),
    ("Rocks and Moss", [
        ("Rock Moss Scale", "FLOAT", 15.0, -1000.0, 1000.0, "Scale of the moss patches on the stones"),
        ("Rock Moss Visibility", "FLOAT", 1.0, 0.0, 2.0, "More (up) or less (down) moss on the stones"),
        ("Rock Moss Color", "COLOR", srgb("222812"), None, None, "Colour of the moss on the stones (#222812)"),
        ("Rock Moss Roughness", "FLOAT", 0.65, 0.0, 1.0, "Roughness of the moss on the stones", F),
        ("Rock Moss Detail 2", "FLOAT", 0.7, 0.0, 1.0, "Roughness of the moss bump noise", F),
        ("Rock Moss Detail 1", "FLOAT", 15.0, 0.0, 15.0, "Detail of the moss bump noise"),
        ("Rock Moss Bump Strength", "FLOAT", 1.0, 0.0, 1.0, "Bump of the moss on the stones", F),
    ]),
    ("Cobblestone Rocks", [
        ("Rock Color 1", "COLOR", srgb("343534"), None, None, "First stone colour, grey (#343534)"),
        ("Rock Color 2", "COLOR", srgb("292524"), None, None, "Second stone colour, brownish (#292524)"),
        ("Rock Roughness", "FLOAT", 0.65, 0.0, 1.0, "Roughness of the stones", F),
        ("Rock Detail", "FLOAT", 10.0, 0.0, 15.0, "Detail of the stone surface noise and Voronoi"),
        ("Rock Bump Strength", "FLOAT", 1.0, 0.0, 1.0, "Bump strength of the stones (both rock bumps)", F),
    ]),
]

OUTPUTS = ("BSDF", "Albedo", "Displacement", "Height")


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


def _ramp(G, fac, stops, node_id, note):
    n = G.ramp(fac, stops)
    n.color_ramp.color_mode = "RGB"; n.color_ramp.interpolation = "LINEAR"
    _tag(n, node_id, note)
    return n.outputs["Color"]


def _hsv(G, color, value, node_id, note):
    n = G.node("ShaderNodeHueSaturation")
    G.set(n, "Hue", 0.5); G.set(n, "Saturation", 1.0); G.set(n, "Fac", 1.0)
    G.set(n, "Value", value); G.set(n, "Color", color)
    _tag(n, node_id, note)
    return n.outputs["Color"]


def _bump(G, height, strength, distance, normal, node_id, note):
    out = G.bump(height, strength, distance, normal=normal)
    n = out.node
    if "Filter Width" in n.inputs: G.set(n, "Filter Width", 0.1)     # A (5.0.1 shows it; 5.2 default too)
    _tag(n, node_id, note)
    return out


def _bsdf(G, base, rough, normal, node_id, note):
    b = G.principled(**{"Base Color": base, "Roughness": rough, "Normal": normal, "Metallic": 0.0, "IOR": 1.5,
                        "Alpha": 1.0})
    _tag(b, node_id, note)
    return b


def _mix_shader(G, fac, s1, s2, node_id, note):
    n = G.node("ShaderNodeMixShader")
    G.link(fac, n.inputs[0]); G.link(s1.outputs[0] if hasattr(s1, "outputs") else s1, n.inputs[1])
    G.link(s2.outputs[0] if hasattr(s2, "outputs") else s2, n.inputs[2])
    _tag(n, node_id, note)
    return n


# UV-mode match (audit CB-1 / CB-2, decision CB16): a 2D slice of 4D Voronoi cells has other distance statistics than
# the video's 3D cells. Object mode is untouched (the video's graph). In UV mode (the baked tiles) the 4D Smooth F1
# twin gets Smoothness = Individual Size x UV_SMOOTH_GAIN, so the tile keeps the object-mode stone coverage / joint
# width (more neighbours lie at similar distances in 4D: the same smoothness eats more of each stone), and the 4D
# rock Voronoi Distance is multiplied by UV_ROCK_GAIN (its std is 0.71x the 3D one: rock bump relief).
# Calibrated at the defaults on a 4 m tile (VALIDATION.md section 6).
UV_SMOOTH_GAIN = 0.82
UV_ROCK_GAIN = 1.41


def _uv_matched(G, C, dual, gain, node_id, tag):
    """Distance of a 3D / 4D Voronoi twin: object mode the 3D node (video), UV mode the 4D node x gain (C)."""
    if not isinstance(dual, core.Dual): return dual.outputs["Distance"]
    v = G.tree.nodes.get(node_id)
    if v is None:
        v = G.node("ShaderNodeValue"); v.outputs[0].default_value = gain
        _tag(v, node_id, "C (audit CB-2 / CB16): UV-mode gain on the 4D Voronoi Distance, matches the 3D statistics")
    g4 = G.mul(dual.n4.outputs["Distance"], v.outputs[0])
    _tag(g4.node, node_id + "_" + tag, "C (CB16): 4D Distance x gain (UV mode only)")
    return G.mix(C.use, dual.n3.outputs["Distance"], g4, "FLOAT", label="object 3D | UV 4D")


# ======================================================================================== the graph
def build_group(name="Cobblestone", exact3d=EXACT3D):
    """PM_<name>: the tutorial's final 'Cobblestone Ground' group (segment b) on the procmat coordinates."""
    G = core.new_group(name, inputs=CONTROLS, outputs=OUTPUTS, scale=None)
    I = G.I
    with G.frame("Mapping"):
        s = G.div(I("Material Scale"), I("Pattern Size"))
        _tag(s.node, "mapping_scale", "A 26:46 (Mapping Point, loc 0, rot 0, Scale <- Material Scale) + C: / Pattern "
                                      "Size (metres). V = Object x Scale is the Mapping node's Point transform")
    G.coords = C = core.Coordinates(G, "Use UV", "Tile Size", s, "UVMap")
    VW = (C.V, C.W)

    # ---------------------------------------------------------------- Cobblestone Distortion
    with G.frame("Cobblestone Distortion"):
        dist_noise = C.noise4(I("Distortion Scale"), I("Distortion Detail 1"), I("Distortion Detail 2"), 2.0, 0.0,
                              at=VW, exact3d=exact3d)
        _tag(dist_noise, "dist_noise", "A 22:14-22:27, 27:28-27:40: Noise 3D fBM Scale 2 Detail 7 Roughness 0.5 Lac 2")
        Vd, Wd = C.warp(dist_noise.outputs["Color"], I("Distortion Strength"), at=VW)
        _tag(Vd.node, "dist_mix", "A 22:31-23:00: Mix RGBA Linear Light Factor 0.2 <- Distortion Strength, A = Mapping, "
                                  "B = noise Color, clamp result off (UV mode: W unwarped, C)")

    # ---------------------------------------------------------------- Cobblestone Mask
    with G.frame("Cobblestone Mask"):
        vs = C.voronoi4(I("Cobblestone Scale"), "SMOOTH_F1", "EUCLIDEAN", I("Cobblestone Alignment"),
                        smoothness=I("Cobblestone Individual Size"), detail=I("Cobblestone Cracks"), roughness=0.5,
                        lacunarity=2.0, normalize=False, at=(Vd, Wd), exact3d=exact3d)
        _tag(vs, "cell_vor_smooth", "A 20:06-20:27, 33:30, 35:28: Voronoi 3D Smooth F1 Euclidean Scale 7 Detail 0 "
                                    "Roughness 0.5 Lac 2 Smoothness 0.6 Randomness 1")
        if isinstance(vs, core.Dual):                       # UV mode: 4D smoothness x gain (CB16)
            sv = G.node("ShaderNodeValue"); sv.outputs[0].default_value = UV_SMOOTH_GAIN
            _tag(sv, "uv_smooth_gain", "C (audit CB-1 / CB16): UV-mode gain on the 4D Smooth F1 smoothness")
            sm4 = G.mul(I("Cobblestone Individual Size"), sv.outputs[0])
            _tag(sm4.node, "uv_smooth_4d", "C (CB16): Individual Size x gain -> 4D Smoothness (UV mode only)")
            G.set(vs.n4, "Smoothness", sm4)
        vf = C.voronoi4(I("Cobblestone Scale"), "F1", "EUCLIDEAN", I("Cobblestone Alignment"),
                        detail=I("Cobblestone Cracks"), roughness=0.5, lacunarity=2.0, normalize=False,
                        at=(Vd, Wd), exact3d=exact3d)
        _tag(vf, "cell_vor_f1", "A 20:27-20:42, 33:30: Voronoi 3D F1 Euclidean Scale 7 Detail 0 Randomness 1")
        diff = G.mixc(I("Cobblestone Visibility"), vs.outputs["Distance"], vf.outputs["Distance"], "DIFFERENCE")
        _tag(diff.node, "cell_diff", "A 20:42-21:00, 34:31: Mix RGBA Difference Factor 1 <- Cobblestone Visibility, "
                                     "A = Smooth F1 Distance, B = F1 Distance")
        mask = _ramp(G, diff, CELL_RAMP, "cell_ramp", "A 21:24-21:57 (spec a, a2): 0.000 #999999 -> 0.035 #000000, "
                                                      "Linear; segment b measured 0.02 / #989898 (C, superseded)")

    # ---------------------------------------------------------------- Dirt Moss Texture
    with G.frame("Dirt Moss Texture"):
        dmoss_noise = C.noise4(I("Dirt Moss Scale"), I("Dirt Moss Detail 1"), I("Dirt Moss Detail 2"), 3.0, 0.0,
                               at=VW, exact3d=exact3d)
        _tag(dmoss_noise, "dmoss_noise", "A 10:24-10:55, 29:28-30:19: Noise 3D Scale 25 Detail 9 Roughness 0.5 Lacunarity 3")
        dm_hsv = _hsv(G, dmoss_noise.outputs["Fac"], I("Dirt Moss Visibility"), "dmoss_hsv",
                      "A 10:52-11:04, 30:19: Hue/Saturation/Value H 0.5 S 1 V 1 <- Dirt Moss Visibility, Fac 1")
        dm = _ramp(G, dm_hsv, DMOSS_RAMP, "dmoss_ramp", "A 10:46-11:04: 0.467 black -> 1.0 white")

    # ---------------------------------------------------------------- Dirt Material
    with G.frame("Dirt Material"):
        dirt_noise = C.noise4(I("Dirt Scale"), I("Dirt Detail 1"), I("Dirt Detail 2"), 2.0, 0.0, at=VW, exact3d=exact3d)
        _tag(dirt_noise, "dirt_noise", "A 8:05-8:10, 31:27-31:46: Noise 3D Scale 20 Detail 10 Roughness 0.55")
        dfac = dirt_noise.outputs["Fac"]
        dcr = _ramp(G, dfac, DIRT_COLOR_RAMP, "dirt_color_ramp", "A 8:19-8:22: 0.151 black -> 0.553 white")
        dcol = G.mixc(dcr, I("Dirt Color 1"), I("Dirt Color 2"))
        _tag(dcol.node, "dirt_color_mix", "A 8:23-8:50, 30:48-30:50: Mix RGBA Mix, A = Dirt Color 1, B = Dirt Color 2")
        drr = _ramp(G, dfac, DIRT_ROUGH_RAMP, "dirt_rough_ramp", "A 9:12-9:35: 0.0 #D2D2D2 -> 1.0 white")
        drough = _hsv(G, drr, I("Dirt Roughness"), "dirt_rough_hsv", "A 9:38-9:56, 32:07: HSV V <- Dirt Roughness")
        sharp = _ramp(G, dm, DMOSS_SHARP_RAMP, "dmoss_sharp_ramp", "A 12:10-12:15: 0.0 black -> 0.324 white")
        dalb = G.mixc(sharp, dcol, I("Dirt Moss Color"))
        _tag(dalb.node, "dirt_moss_mix", "A 11:10-12:26, 31:01: Mix RGBA Mix, A = dirt colour, B = Dirt Moss Color")
        b1 = _bump(G, dfac, I("Dirt Bump Strength"), 0.02, None, "dirt_bump",
                   "A 9:52-10:13, 32:23: Bump Strength 1 Distance 0.02 Filter Width 0.1, Height = dirt noise Fac")
        b2 = _bump(G, dm, I("Dirt Moss Bump Strength"), 0.005, b1, "dmoss_bump",
                   "A 12:33-12:58, 32:31: Bump Strength 1 Distance 0.005, Height = dmoss_ramp")
        dirt_bsdf = _bsdf(G, dalb, drough, b2, "dirt_bsdf", "A 8:57-12:10: Principled (Metallic 0, IOR 1.5, Alpha 1; "
                                                            "hidden dropdowns: 5.x defaults, C)")

    # ---------------------------------------------------------------- Cobblestone Rock Material
    with G.frame("Cobblestone Rock Material"):
        rock_noise = C.noise4(20.0, I("Rock Detail"), 0.5, 2.0, 0.0, at=VW, exact3d=exact3d)
        _tag(rock_noise, "rock_noise", "A 13:12-13:24, 39:28: Noise 3D Scale 20 Detail 10 <- Rock Detail Roughness 0.5")
        rfac = rock_noise.outputs["Fac"]
        rcol = G.mixc(rfac, I("Rock Color 1"), I("Rock Color 2"))
        _tag(rcol.node, "rock_color_mix", "A 13:25-14:01, 38:36: Mix RGBA Mix, A = Rock Color 1, B = Rock Color 2")
        rock_vor = C.voronoi4(12.0, "SMOOTH_F1", "EUCLIDEAN", 1.0, smoothness=1.0, detail=I("Rock Detail"),
                              roughness=0.5, lacunarity=2.0, normalize=False, at=VW, exact3d=exact3d)
        _tag(rock_vor, "rock_vor", "A 14:46-15:21, 39:30: Voronoi 3D Smooth F1 Scale 12 Detail 10 <- Rock Detail "
                                   "Smoothness 1 Randomness 1")
        rb1 = _bump(G, rfac, I("Rock Bump Strength"), 0.007, None, "rock_bump_noise",
                    "A 14:22-14:44, 39:52: Bump Distance 0.007 (narration '0.7', field wins b10)")
        rb2 = _bump(G, _uv_matched(G, C, rock_vor, UV_ROCK_GAIN, "uv_rock_gain", "rock"), I("Rock Bump Strength"), 0.015, rb1, "rock_bump_vor",
                    "A 14:53-15:41, 39:54: Bump Distance 0.015, Height = rock Voronoi Distance")
        rock_bsdf = _bsdf(G, rcol, I("Rock Roughness"), rb2, "rock_bsdf", "A 14:02-15:40: Principled Roughness 0.65")

    # ---------------------------------------------------------------- Moss & Rock Mask
    with G.frame("Moss & Rock Mask"):
        rm_noise = C.noise4(I("Rock Moss Scale"), 10.0, 0.8, 2.0, 0.0, at=VW, exact3d=exact3d)
        _tag(rm_noise, "rmmask_noise", "A 17:28-18:03, 36:34: Noise 3D Scale 15 Detail 10 Roughness 0.8")
        rm_hsv = _hsv(G, rm_noise.outputs["Fac"], I("Rock Moss Visibility"), "rmmask_hsv",
                      "A 17:56-18:03, 37:00: HSV V <- Rock Moss Visibility")
        rmask = _ramp(G, rm_hsv, RMMASK_RAMP, "rmmask_ramp", "A 18:49-18:53: 0.407 black -> 0.651 white")

    # ---------------------------------------------------------------- Rock Moss Material
    with G.frame("Rock Moss Material"):
        rmoss_noise = C.noise4(17.0, I("Rock Moss Detail 1"), I("Rock Moss Detail 2"), 2.0, 0.0, at=VW, exact3d=exact3d)
        _tag(rmoss_noise, "rmoss_noise", "A 16:01-16:51, 37:52: Noise 3D Scale 17 Detail 15 Roughness 0.7")
        mb = _bump(G, rmoss_noise.outputs["Fac"], I("Rock Moss Bump Strength"), 0.01, None, "rmoss_bump",
                   "A 16:13-16:53, 38:12: Bump Distance 0.01")
        rmoss_bsdf = _bsdf(G, I("Rock Moss Color"), I("Rock Moss Roughness"), mb, "rmoss_bsdf",
                           "A 16:25-16:51, 37:26: Principled Base Color #222812, Roughness 0.65")

    rock_moss = _mix_shader(G, rmask, rock_bsdf, rmoss_bsdf, "rock_moss_mix",
                            "A 18:13-18:41: Mix Shader Fac = rmmask_ramp, Shader 1 = rock, Shader 2 = moss")

    # ---------------------------------------------------------------- Mix Rocks & Dirt
    with G.frame("Mix Rocks & Dirt"):
        fr = _ramp(G, mask, FINAL_RAMP, "final_ramp", "A 24:04-24:20: 0.0 black -> 0.030 white on the cell mask")
        final = _mix_shader(G, fr, dirt_bsdf, rock_moss, "final_mix",
                            "A 23:27-25:25: Mix Shader, Shader 1 = dirt, Shader 2 = rock & moss")
        disp = G.node("ShaderNodeDisplacement", space="OBJECT")
        G.set(disp, "Height", mask); G.set(disp, "Midlevel", 0.0); G.set(disp, "Scale", I("Displacement Strength"))
        _tag(disp, "displacement", "A 24:38-26:10, 35:53: Displacement Object Space, Midlevel 0, Scale 0.02 <- "
                                   "Displacement Strength, Height = cell_ramp")
        # procmat outputs (C): Albedo = the same mixes on colours; Height = stone relief in metres
        alb_rock = G.mixc(rmask, rcol, I("Rock Moss Color"))
        _tag(alb_rock.node, "albedo_rock", "C: Albedo of rock_moss_mix (same factor, the two Base Colors)")
        albedo = G.mixc(fr, dalb, alb_rock)
        _tag(albedo.node, "albedo", "C: Albedo of final_mix (same factor, dirt / rock-moss Base Colors)")
        height = G.mul(mask, I("Displacement Strength"))
        _tag(height.node, "height", "C: Height output = cell_ramp grey x Displacement Strength (metres of stone relief)")

    G.out("BSDF", final)
    G.out("Albedo", albedo)
    G.out("Displacement", disp.outputs["Displacement"])
    G.out("Height", height)
    return G.finish()


# viewport colour / roughness (also the road tool's glTF fallback for non-MRS materials): linear means of the 4 m
# UV-mode bake at the defaults (VALIDATION.md section 6, after CB16)
VIEWPORT = (0.0200, 0.0200, 0.0139, 1.0)
VIEWPORT_ROUGHNESS = 0.72


def build():
    g = build_group("Cobblestone")
    mats = [core.contract_material("Cobblestone", g, displacement="BUMP", viewport=VIEWPORT, roughness=VIEWPORT_ROUGHNESS),
            core.contract_material("CobblestoneDisplaced", g, displacement="BOTH", viewport=VIEWPORT,
                                   roughness=VIEWPORT_ROUGHNESS)]
    for m in mats:
        m["pm_source"] = ("Ryan King Art, Procedural Cobblestone Ground Material (Blender Tutorial), 2026, "
                          "YouTube 30vbbpy9zwg")
        m["pm_road_socket"] = "Paving Material"
    return mats


register(sys.modules[__name__])
