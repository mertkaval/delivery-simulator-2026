"""PM_Glass*: six textured / frosted glass materials reverse-engineered from Ryan King Art, "Procedural Textured
Frosted Glass Materials (Blender Tutorial)", 2026-05-12, 34:03, YouTube SNKNqHd0AYI (Blender 5.1.1 in the video).
Use in the road tool: glazing - the bus-shelter glass panels of the road tool's furniture
(road_adapter.assign_shelter_glass), building windows later.

Specification : tools/materials/reconstruction/glass/GRAPH_SPEC_a.md (Circles, Voronoi, Cells) and GRAPH_SPEC_b.md
                (Wavy, Blobby, Frosted). Node names are the spec's ids (voronoi, rgb_curves, bump, glass ...); every
                node carries its evidence class in the custom property "pm_note" (A frame, B narration, C our
                implementation, D unresolved).
Documentation : tools/materials/reconstruction/glass/README.md, NODES.md, DECISIONS.md, VALIDATION.md.

Materials (key "glass"); each is one group PM_<Name> in one material PM_<Name> (library contract):
  PM_GlassCircles  "Textured Glass Circles"  dense round dimples: Smooth F1 Voronoi 50/m -> RGB Curves -> inverted bump 2 mm
  PM_GlassVoronoi  "Textured Glass Voronoi"  hammered cells: two Smooth F1 Voronois 30/m -> RGB Curves -> chained inverted
                                              bumps 4 mm + 0.08 mm, clear glass
  PM_GlassCells    "Textured Glass Cells"    faceted plates: Voronoi Distance to Edge 30/m -> Map Range -> inverted bump 3 mm;
                                              noise-varied frost (Noise -> Color Ramp -> Hue/Saturation/Value -> roughness)
  PM_GlassWavy     "Textured Glass Wavy"     vertical wavy streaks: Gabor 3D (scale 12, frequency 5) -> bump 0.7 mm
  PM_GlassBlobby   "Textured Glass Blobby"   crinkled blobs: Smooth F1 Voronoi 10/m detail 2.6 -> bump 4 mm; noise-varied frost
  PM_GlassFrosted  "Frosted Glass"           satin frost, no relief: Noise -> Color Ramp -> Hue/Saturation/Value -> roughness

The glass base every variant repeats in the video (built here by one helper per group, decision G1): Texture
Coordinate Object -> Mapping (Point, Location 0, Rotation 0 - exposed on the Wavy -, Scale = the group's Scale) ->
textures, and one Glass BSDF (Multiscatter GGX) with Color / Roughness / IOR from the group and Normal from the relief.
The video's group output "Shader" is the contract's "BSDF"; "Albedo" is the Glass Color (the tint).

Coordinates: the video's panes have applied scale, so Object coordinates are metres and its texture scales are per
metre (Circles 50 cells/m ...). In front of the video's Mapping sits the library contract: Use UV = 0 -> Object
coordinates (the video), Use UV = 1 -> the seamless 4D torus of UVMap x Tile Size. The Mapping scales by
Scale / Pattern Size (Pattern Size: metres per unit of the video's object space, default 1 = the video; it also scales
the bump distances, so the relief keeps its shape). Voronoi and Noise are built with exact3d: object mode samples the
video's 3D textures exactly, UV mode their 4D twins on the torus. The Gabor has no 4D variant (D5): UV mode cross-fades
four 3D samples (core.Coordinates.seamless) on the pane plane (UV u -> X, UV v -> Z, as on the video's vertical pane),
with a variance-preserving gain so the relief keeps its amplitude in the blend band (G17). In object mode the Gabor
orientation is taken relative to the surface (G18): the video's vector on its X-Z pane, the same streaks on any pane.
"""
import sys

from . import core, register

KEY = "glass"

SOURCE = "Ryan King Art, Procedural Textured Frosted Glass Materials (Blender Tutorial), 2026, YouTube SNKNqHd0AYI"
EXACT3D = True                      # object mode = the video's 3D Voronoi / Noise fields exactly (G3)
BUMP_FILTER_WIDTH = 0.1             # Bump "Filter Width" (Blender 4.4+), the video's 5.1.1 default (A, spec a section 8)
GABOR_SCALE = 12.0                  # A 23:05-23:11, not exposed ("we are already using the scale with the mapping", B 25:00)
GABOR_ORIENTATION = (0.797, 0.604, 0.0)   # C: Lambert fit of the direction-ball widget at 23:48 / 25:00 (spec b, D1)
SEAMLESS_BLEND = 0.15               # Wavy, UV mode: cross-fade band (fraction of the tile) of the 3D Gabor (C, D5)
GABOR_MEAN = 0.5                    # Gabor Value is centred on 0.5 (measured mean in VALIDATION section 6b; C, GL-2)
ORIENT_SIDE = (0.1, -1.0, 0.05)     # picks one side of a pane for the surface-relative Gabor orientation (C, GL-1)
WHITE = (1.0, 1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0, 1.0)


def srgb_to_linear(v):
    """A colour picker's perceptual (sRGB-encoded) value -> the scene-linear value a ramp stop stores (C)."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def grey(v):
    g = srgb_to_linear(v)
    return (g, g, g, 1.0)


# ======================================================================================== interface rows
# (name, type, default, min, max, description[, subtype]); min / max None = Blender's float limits (+-3.4e38, shown
# as -inf / inf), as the video's Scale socket. Defaults, limits and subtypes are the video's (spec tables, class A unless
# the description says C).
def _scale():
    return ("Scale", "FLOAT", 1.0, None, None,
            "The video's Mapping Scale: multiplies the object coordinates (metres); 2 = every feature half the size", "NONE")


def _color():
    return ("Glass Color", "COLOR", WHITE, None, None, "Glass BSDF colour: the tint (white = clear; the video demos #CCEDFF)")


def _rough_factor(default):
    return ("Glass Roughness", "FLOAT", default, 0.0, 1.0, "Glass BSDF roughness: 0 = clear, higher = frosted", "FACTOR")


def _rough_mult(name="Glass Roughness"):
    return (name, "FLOAT", 1.0, 0.0, 2.0, "Multiplies the noise-varied roughness (Hue/Saturation/Value Value): 0 = clear, "
                                          "2 = twice as frosted", "NONE")


def _ior():
    return ("Glass IOR", "FLOAT", 1.5, 0.0, 1000.0, "Index of refraction (1.5 = window glass; 1 = no refraction)", "NONE")


def _bump_strength(name="Bump Strength"):
    return (name, "FLOAT", 1.0, 0.0, 1.0, "Bump strength: 0 = flat glass, 1 = the full relief", "FACTOR")


def _noise_rows(prefix):
    a = "Noise Roughness" if prefix == "noise" else "Frosted"
    return [(a + " Scale", "FLOAT", 20.0, -1000.0, 1000.0, "Noise Scale per metre of the frost / roughness variation "
                                                           "(20 = ~5 cm grain)", "NONE"),
            (a + " Detail 1", "FLOAT", 15.0, 0.0, 15.0, "Noise Detail: octaves of the frost grain", "NONE"),
            (a + " Detail 2", "FLOAT", 1.0, 0.0, 1.0, "Noise Roughness: weight of the finer octaves (\"second layer of "
                                                      "detail\")" + (" (limits C)" if prefix == "frosted" else ""), "FACTOR")]


PATTERN_SIZE = ("Pattern Size", "FLOAT", 1.0, 0.01, 100.0,
                "Metres per unit of the video's object space (its panes have applied scale: 1 unit = 1 m). 1 = the "
                "video's sizes; 2 = every feature and the relief depth twice as large (library control, C)", "DISTANCE")
MAPPING_PANEL = ("Mapping", [PATTERN_SIZE])        # the contract adds Use UV and Tile Size to this (closed) panel

CIRCLES_CONTROLS = [
    _scale(), _color(), _rough_factor(0.2), _ior(),
    ("Voronoi Scale", "FLOAT", 50.0, -1000.0, 1000.0, "Dimples per metre (Voronoi Scale; 50 = 2 cm dimples)", "NONE"),
    ("Voronoi Detail", "FLOAT", 0.0, 0.0, 15.0, "Voronoi Detail: extra layers of smaller dimples (limits C)", "NONE"),
    ("Voronoi Roughness", "FLOAT", 0.5, 0.0, 1.0, "Voronoi Roughness: weight of the detail layers", "FACTOR"),
    ("Voronoi Smoothness", "FLOAT", 1.0, 0.0, 1.0, "Voronoi Smoothness (Smooth F1): roundness of the dimples", "FACTOR"),
    ("Voronoi Randomness", "FLOAT", 1.0, 0.0, 1.0, "Voronoi Randomness: 0 = a regular grid of dimples, 1 = random "
                                                    "(limits C)", "FACTOR"),
    _bump_strength(),
]

VORONOI_CONTROLS = [
    _scale(), _color(), _rough_factor(0.0), _ior(),
    ("Voronoi Scale 1", "FLOAT", 30.0, -1000.0, 1000.0, "Cells per metre of the large hammered cells (30 = 3.3 cm)", "NONE"),
    ("Voronoi Scale 2", "FLOAT", 30.0, -1000.0, 1000.0, "Cells per metre of the fine second layer (its first octave)", "NONE"),
    ("Voronoi Smoothness 1", "FLOAT", 0.1, 0.0, 1.0, "Smooth F1 smoothness of the large cells", "FACTOR"),
    ("Voronoi Smoothness 2", "FLOAT", 0.03, 0.0, 1.0, "Smooth F1 smoothness of the fine layer", "FACTOR"),
    ("Voronoi Detail 1", "FLOAT", 0.0, 0.0, 15.0, "Voronoi Detail of the large cells", "NONE"),
    ("Voronoi Detail 2", "FLOAT", 3.0, 0.0, 15.0, "Voronoi Detail of the fine layer (3 = four octaves)", "NONE"),
    _bump_strength("Bump Strength 1"),
    _bump_strength("Bump Strength 2"),
]

CELLS_CONTROLS = [
    _scale(), _color(), _rough_mult(), _ior(),
    ("Voronoi Scale", "FLOAT", 30.0, -1000.0, 1000.0, "Cells per metre (30 = 3.3 cm plates)", "NONE"),
    ("Voronoi Detail", "FLOAT", 0.0, 0.0, 15.0, "Voronoi Detail: cracks inside the cells (limits C)", "NONE"),
    ("Voronoi Roughness", "FLOAT", 0.5, 0.0, 1.0, "Voronoi Roughness: weight of the detail layers", "FACTOR"),
    ("Voronoi Randomness", "FLOAT", 1.0, 0.0, 1.0, "Voronoi Randomness: 0 = regular grid, 1 = random (limits C)", "FACTOR"),
] + _noise_rows("noise") + [_bump_strength()]

WAVY_CONTROLS = [
    _scale(), _color(), _rough_factor(0.2), _ior(),
    ("Gabor Frequency", "FLOAT", 5.0, 0.0, None, "Gabor Frequency: waves per Gabor cell (12 cells/m: 5 = ~2.1 cm "
                                                 "streaks on a vertical X-Z pane)", "NONE"),
    _bump_strength(),
    ("Rotation", "VECTOR", (0.0, 0.0, 0.0), None, None, "Mapping Rotation: turns the wave direction (rotating Y turns "
                                                        "the streaks in a vertical X-Z pane)", "EULER"),
]

BLOBBY_CONTROLS = [
    _scale(), _color(), _rough_mult(), _ior(),
    ("Voronoi Scale", "FLOAT", 10.0, -1000.0, 1000.0, "Blobs per metre (10 = 10 cm blobs)", "NONE"),
    ("Voronoi Detail", "FLOAT", 2.6, 0.0, 15.0, "Voronoi Detail: smaller blobs inside the blobs (limits C)", "NONE"),
    ("Voronoi Smoothness", "FLOAT", 0.1, 0.0, 1.0, "Smooth F1 smoothness of the blob edges", "FACTOR"),
] + _noise_rows("noise") + [_bump_strength()]

FROSTED_CONTROLS = [
    _scale(), _color(), _rough_mult("Frosted Amount"), _ior(),
] + _noise_rows("frosted")


# ======================================================================================== helpers
def _tag(obj, node_id, note):
    """Name / label / evidence note of a node, of a Dual (3D + 4D twin) or of the node of an output socket."""
    if isinstance(obj, core.Dual):
        for n, suffix in ((obj.n3, "_3d"), (obj.n4, "_4d")):
            n.name = node_id + suffix; n.label = node_id + (" (object 3D)" if suffix == "_3d" else " (UV 4D)")
            n["pm_note"] = note + (" | object mode (Use UV 0): the video's 3D texture" if suffix == "_3d" else
                                   " | UV mode (Use UV 1): 4D twin on the seamless torus (C)")
        return obj
    n = obj.node if isinstance(obj, core.bpy.types.NodeSocket) else obj
    n.name = node_id; n.label = node_id; n["pm_note"] = note
    return obj


def _mode_out(dual, key, node_id):
    """A Dual's output (Mix of the 3D and 4D twins by Use UV), its Mix node named <node_id>_mode."""
    s = dual.outputs[key]
    s.node.name = node_id + "_mode"; s.node.label = node_id + ": object 3D | UV 4D"
    s.node["pm_note"] = "C: Use UV picks the video's 3D texture (0) or its 4D torus twin (1)"
    return s


class _Base:
    """One glass group: the contract coordinates, the video's Mapping and Glass BSDF around a variant's relief and
    roughness chains (decision G1: every variant carries its own copy, as in the video)."""

    def __init__(self, name, controls, mapping_note, per_sample_mapping=False):
        self.G = G = core.new_group(name, inputs=list(controls) + [MAPPING_PANEL], outputs=("BSDF", "Albedo"), scale=None)
        self.C = C = G.coords
        with G.frame("Mapping (video): Object coordinates -> Mapping Point, Scale = Scale / Pattern Size"):
            self.k = G.div(G.I("Scale"), G.I("Pattern Size"))
            _tag(self.k, "pattern_scale", "C: the Mapping Scale = the video's Scale (A) / Pattern Size (library metres, "
                                          "1 = the video's object space)")
            self.at = None
            if not per_sample_mapping:
                mp = G.node("ShaderNodeMapping", vector_type="POINT")
                G.set(mp, "Vector", C.V); G.set(mp, "Scale", self.k)
                _tag(mp, "mapping", mapping_note + " | Vector = Object coordinates (Use UV 0) or the torus point (Use UV 1, C)")
                W = G.mul(C.W, self.k)
                _tag(W, "mapping_w", "C: the torus' 4th coordinate scaled like the Mapping (0 in object mode)")
                self.at = (mp.outputs["Vector"], W)

    def bump(self, height, strength, distance, invert, node_id, note, normal=None):
        """The video's Bump (Filter Width 0.1) with Distance = video distance x Pattern Size."""
        G = self.G
        dist = G.mul(distance, G.I("Pattern Size"))
        _tag(dist, node_id + "_distance", "C: Bump Distance = the video's %g m (A) x Pattern Size" % distance)
        out = G.bump(height, strength, dist, normal=normal, invert=invert)
        n = out.node
        n.inputs["Filter Width"].default_value = BUMP_FILTER_WIDTH
        _tag(n, node_id, note)
        return out

    def curves(self, value, points, node_id, note):
        """RGB Curves: the combined (C) curve through (0,0), points, (1,1), auto handles; R / G / B untouched."""
        n = self.G.node("ShaderNodeRGBCurve")
        cm = n.mapping; c = cm.curves[3]
        for x, y in points: c.points.new(x, y)
        for p in c.points: p.handle_type = "AUTO"
        cm.update()
        self.G.set(n, "Fac", 1.0); self.G.set(n, "Color", value)
        pts = ", ".join("(%.4g, %.4g)" % (p.location[0], p.location[1]) for p in c.points)
        _tag(n, node_id, note + " | C curve %s, auto handles, Factor 1" % pts)
        return n.outputs["Color"]

    def frost(self, scale, detail, rough, stops, amount, notes):
        """The video's roughness chain: Noise (3D fBM, Normalize, Lacunarity 2, Distortion 0) Factor -> Color Ramp
        (RGB, Linear) -> Hue/Saturation/Value (Hue 0.5, Saturation 1, Factor 1, Value = amount) -> Color."""
        G, C = self.G, self.C
        noise = C.noise4(scale, detail, rough, 2.0, 0.0, "FBM", True, at=self.at, exact3d=EXACT3D)
        _tag(noise, "noise", notes[0])
        fac = _mode_out(noise, "Fac", "noise") if EXACT3D else noise.outputs["Fac"]
        ramp = G.ramp(fac, stops)
        _tag(ramp, "color_ramp", notes[1])
        hsv = G.node("ShaderNodeHueSaturation")
        G.set(hsv, "Hue", 0.5); G.set(hsv, "Saturation", 1.0); G.set(hsv, "Fac", 1.0)
        G.set(hsv, "Value", amount); G.set(hsv, "Color", ramp.outputs["Color"])
        _tag(hsv, "hsv", notes[2])
        return hsv.outputs["Color"]

    def glass(self, roughness, normal, note):
        """Glass BSDF (Multiscatter GGX; Thin Film defaults, C) -> BSDF; Glass Color -> Albedo."""
        G = self.G
        gl = G.node("ShaderNodeBsdfGlass", distribution="MULTI_GGX")
        G.set(gl, "Color", G.I("Glass Color")); G.set(gl, "Roughness", roughness); G.set(gl, "IOR", G.I("Glass IOR"))
        if normal is not None: G.set(gl, "Normal", normal)
        _tag(gl, "glass", note + " | Thin Film Thickness 0 / IOR 1.33 = defaults (panel never opened, C)")
        G.out("BSDF", gl.outputs["BSDF"])
        G.out("Albedo", G.I("Glass Color"))
        return gl


def _voronoi(B, node_id, note, scale, feature, randomness=1.0, **kw):
    v = B.C.voronoi4(scale, feature, "EUCLIDEAN", randomness, lacunarity=2.0, normalize=False, at=B.at, exact3d=EXACT3D, **kw)
    _tag(v, node_id, note)
    return _mode_out(v, "Distance", node_id) if EXACT3D else v.outputs["Distance"]


# ======================================================================================== the six groups
def build_circles():
    """Textured Glass Circles (spec a section 2, video 6:10-10:55; final graph 10:43.5)."""
    B = _Base("GlassCircles", CIRCLES_CONTROLS, "A 06:46.5, 10:43.5: Mapping Point, Location 0, Rotation 0, Scale <- Scale")
    G, I = B.G, B.G.I
    with G.frame("Relief: Voronoi Smooth F1 -> RGB Curves -> Bump (inverted, 2 mm)"):
        d = _voronoi(B, "voronoi", "A 06:34.5-06:40.5, 10:43.5: Voronoi 3D Smooth F1 Euclidean, Normalize off, Lacunarity 2; "
                                   "Scale 50 / Detail 0 / Roughness 0.5 / Smoothness 1 / Randomness 1 from the group",
                     I("Voronoi Scale"), "SMOOTH_F1", I("Voronoi Randomness"), smoothness=I("Voronoi Smoothness"),
                     detail=I("Voronoi Detail"), roughness=I("Voronoi Roughness"))
        h = B.curves(d, ((0.3140, 0.2464), (0.5804, 0.6535)), "rgb_curves",
                     "A 07:37.5-08:14.6, 10:43.5: Distance -> RGB Curves Color (not Factor); points read 08:14.0 / 08:14.6 "
                     "(lower point's last move C)")
        nrm = B.bump(h, I("Bump Strength"), 0.002, True, "bump",
                     "A 07:22.5, 07:55.5, 10:43.5: Bump Invert on, Distance 0.002, Filter Width 0.1, Strength <- Bump Strength")
    with G.frame("Glass BSDF"):
        B.glass(I("Glass Roughness"), nrm, "A 06:19.5, 08:25.5, 10:43.5: Glass BSDF Multiscatter GGX; Color / Roughness (0.2) / "
                                           "IOR (1.5) from the group, Normal <- Bump")
    return G.finish()


def build_voronoi():
    """Textured Glass Voronoi (spec a section 3, video 10:55-16:43; final graph 16:26.5)."""
    B = _Base("GlassVoronoi", VORONOI_CONTROLS, "A 11:16.5, 16:26.5: Mapping Point, Location 0, Rotation 0, Scale <- Scale")
    G, I = B.G, B.G.I
    with G.frame("Relief: two Voronoi Smooth F1 -> RGB Curves -> chained Bumps (inverted, 4 mm + 0.08 mm)"):
        d1 = _voronoi(B, "voronoi_1", "A 11:22.5, 11:36.5, 12:20.5, 16:26.5: Voronoi 3D Smooth F1 Euclidean, Normalize off, "
                                      "Roughness 0.0, Lacunarity 2, Randomness 1; Scale 30 / Detail 0 / Smoothness 0.1 from the group",
                      I("Voronoi Scale 1"), "SMOOTH_F1", 1.0, smoothness=I("Voronoi Smoothness 1"),
                      detail=I("Voronoi Detail 1"), roughness=0.0)
        d2 = _voronoi(B, "voronoi_2", "A 12:40.5, 13:00.5, 16:26.5: copy of voronoi_1 (Shift+Ctrl+D) with Roughness 1.0; "
                                      "Scale 30 / Detail 3 / Smoothness 0.03 from the group",
                      I("Voronoi Scale 2"), "SMOOTH_F1", 1.0, smoothness=I("Voronoi Smoothness 2"),
                      detail=I("Voronoi Detail 2"), roughness=1.0)
        h1 = B.curves(d1, ((0.6758, 0.2928),), "rgb_curves_1", "A 13:44.5, 14:05.5, 16:26.5: voronoi_1 Distance -> Color")
        h2 = B.curves(d2, ((0.6331, 0.3000),), "rgb_curves_2", "A 13:44.5, 14:17.5, 16:26.5: voronoi_2 Distance -> Color")
        n2 = B.bump(h2, I("Bump Strength 2"), 0.00008, True, "bump_2",
                    "A 13:04.5-13:26.5: Bump Invert on (copied), Distance typed 0.00008 (displays 0.0001), Filter Width 0.1; "
                    "Normal -> bump_1 Normal")
        n1 = B.bump(h1, I("Bump Strength 1"), 0.004, True, "bump_1",
                    "A 12:08.5, 12:28.5, 13:08.5: Bump Invert on, Distance 0.004, Filter Width 0.1, Normal <- bump_2", normal=n2)
    with G.frame("Glass BSDF"):
        B.glass(I("Glass Roughness"), n1, "A 11:56.5, 16:26.5: Glass BSDF Multiscatter GGX; Roughness 0.0 (clear), IOR 1.5")
    return G.finish()


def build_cells():
    """Textured Glass Cells (spec a section 4, video 17:52-22:32; graph 20:15.5, group interior 22:07.5)."""
    B = _Base("GlassCells", CELLS_CONTROLS, "A 18:04, 22:07.5: Mapping Point, Location 0, Rotation 0, Scale <- Scale")
    G, I = B.G, B.G.I
    with G.frame("Relief: Voronoi Distance to Edge -> Map Range -> Bump (inverted, 3 mm)"):
        d = _voronoi(B, "voronoi", "A 18:17.5, 18:24.5, 20:15.5: Voronoi 3D Distance to Edge Euclidean, Normalize off, "
                                   "Lacunarity 2; Scale 30 / Detail 0 / Roughness 0.5 / Randomness 1 from the group",
                     I("Voronoi Scale"), "DISTANCE_TO_EDGE", I("Voronoi Randomness"), detail=I("Voronoi Detail"),
                     roughness=I("Voronoi Roughness"))
        h = G.map_range(d, 0.02, 1.0, 0.0, 1.0, clamp=True)
        _tag(h, "map_range", "A 19:04.5, 19:20.5, 22:07.5: Map Range Float Linear Clamp, From Min 0.02, From Max 1, To 0..1")
        nrm = B.bump(h, I("Bump Strength"), 0.003, True, "bump",
                     "A 18:44.5, 18:48.5, 20:15.5: Bump Invert on, Distance 0.003, Filter Width 0.1")
    with G.frame("Roughness: Noise -> Color Ramp -> Hue/Saturation/Value (Glass Roughness multiplies)"):
        rough = B.frost(I("Noise Roughness Scale"), I("Noise Roughness Detail 1"), I("Noise Roughness Detail 2"),
                        ((0.0, BLACK), (1.0, grey(0.659))), I("Glass Roughness"),
                        ("A 19:37.5, 20:15.5: Noise 3D fBM Normalize, Lacunarity 2, Distortion 0; Scale 20 / Detail 15 / "
                         "Roughness 1 from the group; Factor -> ramp",
                         "A 19:52.5-19:57.85: Color Ramp RGB Linear, black @ 0, #A8A8A8 (Perceptual V 0.659, A) @ 1 = linear "
                         "%.4f (C)" % srgb_to_linear(0.659),
                         "A 20:11.5, 21:00: Hue/Saturation/Value Hue 0.5, Saturation 1, Factor 1, Value <- Glass Roughness"))
    with G.frame("Glass BSDF"):
        B.glass(rough, nrm, "A 18:36.5, 20:15.5: Glass BSDF Multiscatter GGX; Roughness <- HSV Color, IOR 1.5")
    return G.finish()


def build_wavy():
    """Textured Glass Wavy (spec b, video 22:32-25:33; graph 23:48, group 25:17-25:26)."""
    B = _Base("GlassWavy", WAVY_CONTROLS, "", per_sample_mapping=True)
    G, C, I = B.G, B.C, B.G.I
    count = [0]

    with G.frame("Wave direction relative to the surface (object mode): the video's (0.797, 0.604, 0) on any pane"):
        # The video's orientation on its X-Z pane (object normal -Y) = 0.797 x the horizontal in-plane tangent X
        # + 0.604 x the pane normal reversed (+Y). Rebuilt from the shading normal so every pane sees the same projection
        # (vertical streaks, ~2.1 cm on any vertical pane; on the video's pane the vector is exactly the video's).
        tc = G.node("ShaderNodeTexCoord")
        _tag(tc, "surface_normal", "C (GL-1): Texture Coordinate Normal = the object-space shading normal")
        n = G.vmath("NORMALIZE", tc.outputs["Normal"])
        sgn = G.math("SIGN", G.vmath("DOT_PRODUCT", n, ORIENT_SIDE))
        _tag(sgn, "normal_side", "C (GL-1): the normal's sign made independent of the side seen (back faces flip the "
                                 "shading normal): N . %s > 0 picks the side, so -Y on the video's pane" % (ORIENT_SIDE,))
        n = G.vmath("SCALE", n, scale=sgn)
        h = G.vmath("NORMALIZE", G.vmath("ADD", G.vmath("CROSS_PRODUCT", (0.0, 0.0, 1.0), n), (1e-3, 0.0, 0.0)))
        _tag(h, "pane_horizontal", "C (GL-1): horizontal in-plane tangent = Z x N (X on the video's pane; X on "
                                   "horizontal faces)")
        o_surf = G.vmath("SUBTRACT", G.vmath("SCALE", h, scale=GABOR_ORIENTATION[0]),
                         G.vmath("SCALE", n, scale=GABOR_ORIENTATION[1]))
        _tag(o_surf, "orientation_surface", "C (GL-1): 0.797 x horizontal tangent - 0.604 x N = the video's vector "
                                            "expressed in the pane's frame")
        orient = G.mixv(C.use, o_surf, GABOR_ORIENTATION)
        _tag(orient, "orientation", "C (GL-1): object mode = surface-relative orientation; UV mode = the video's constant "
                                    "(UV is laid on the video's X-Z pane plane)")

    def make(P):
        """The video's chain at one metre position P: (UV mode: u -> X, v -> Z) -> Mapping (Rotation, Scale) -> Gabor 3D."""
        i = count[0]; count[0] += 1
        sfx = "" if i == 0 else "_seam%d" % i
        px, py, pz = G.separate(P)
        P3 = G.combine(px, G.mixf(C.use, py, pz), G.mixf(C.use, pz, py))
        _tag(P3, "pane_plane" + sfx, "C: object mode keeps (x, y, z); UV mode puts UV u on X and UV v on Z (the video's "
                                     "vertical X-Z pane), so the streaks run along v")
        mp = G.node("ShaderNodeMapping", vector_type="POINT")
        G.set(mp, "Vector", P3); G.set(mp, "Rotation", I("Rotation")); G.set(mp, "Scale", B.k)
        _tag(mp, "mapping" + sfx, "A 22:47-22:50, 25:15-25:17: Mapping Point, Location 0, Rotation <- Rotation (Euler), "
                                  "Scale <- Scale")
        gb = G.node("ShaderNodeTexGabor", gabor_type="3D")
        G.set(gb, "Vector", mp.outputs["Vector"]); G.set(gb, "Scale", GABOR_SCALE); G.set(gb, "Frequency", I("Gabor Frequency"))
        G.set(gb, "Anisotropy", 1.0); G.set(gb, "Orientation 3D", orient)
        _tag(gb, "gabor" + sfx, ("A 22:52-23:11, 23:48: Gabor 3D, Scale 12, Frequency <- Gabor Frequency (5), Anisotropy 1; "
                                 "Orientation 3D (0.797, 0.604, 0) measured from the direction ball (C), applied relative to "
                                 "the surface (orientation node, GL-1); Value -> Bump")
                + ("" if i == 0 else " | UV-mode cross-fade sample %d (C, D5)" % i))
        return gb.outputs["Value"]

    with G.frame("Relief: Gabor 3D -> Bump (0.7 mm); UV mode cross-fades four samples (no 4D Gabor)"):
        val = C.seamless(make, blend=SEAMLESS_BLEND)
        _tag(val, "gabor_seamless", "C (D5): object mode = gabor (the video's field); UV mode = smoothstep cross-fade of four "
                                    "samples over the last %g of the tile, so the tile repeats exactly" % SEAMLESS_BLEND)
        # GL-2: the linear cross-fade of independent samples lowers the field's deviation by sqrt(sum of squared weights)
        # (to 0.5 at the band centre); dividing the deviation from the mean by it keeps the relief amplitude constant.
        # Object mode: weights 0 -> factor 1 (the video's field unchanged).
        ux, uy, _ = G.separate(C.uv)
        wu = G.mul(C.use, G.smoothstep(G.fract(ux), 1.0 - SEAMLESS_BLEND, 1.0))
        wv = G.mul(C.use, G.smoothstep(G.fract(uy), 1.0 - SEAMLESS_BLEND, 1.0))

        def sq_sum(w):
            return G.add(G.power(G.invert(w), 2.0), G.power(w, 2.0))
        k = G.math("INVERSE_SQRT", G.mul(sq_sum(wu), sq_sum(wv)))
        _tag(k, "seam_gain", "C (GL-2): 1 / sqrt(((1-wu)^2 + wu^2)((1-wv)^2 + wv^2)), the variance-preserving gain of the "
                             "four-sample cross-fade (1 outside the band and in object mode)")
        val = G.madd(G.sub(val, GABOR_MEAN), k, GABOR_MEAN)
        _tag(val, "gabor_relief", "C (GL-2): mean %g + (cross-faded value - mean) x seam_gain -> Bump" % GABOR_MEAN)
        nrm = B.bump(val,I("Bump Strength"), 0.0007, False, "bump",
                     "A 23:24-23:38, 23:48: Bump Invert off, Distance typed 0.0007 (displays 0.001), Filter Width 0.1")
    with G.frame("Glass BSDF"):
        B.glass(I("Glass Roughness"), nrm, "A 23:21-23:48: Glass BSDF Multiscatter GGX; Roughness 0.2, IOR 1.5")
    return G.finish()


def build_blobby():
    """Textured Glass Blobby (spec b, video 25:33-29:50; graph 27:42, group 29:33)."""
    B = _Base("GlassBlobby", BLOBBY_CONTROLS, "A 25:45, 27:42, 29:33: Mapping Point, Location 0, Rotation 0, Scale <- Scale")
    G, I = B.G, B.G.I
    with G.frame("Roughness: Noise -> Color Ramp -> Hue/Saturation/Value (Glass Roughness multiplies)"):
        rough = B.frost(I("Noise Roughness Scale"), I("Noise Roughness Detail 1"), I("Noise Roughness Detail 2"),
                        ((0.0, BLACK), (1.0, grey(0.700))), I("Glass Roughness"),
                        ("A 25:42-25:58, 27:42: Noise 3D fBM Normalize, Lacunarity 2, Distortion 0; Scale 20 / Detail 15 / "
                         "Roughness 1 from the group; Factor -> ramp",
                         "A 26:18-26:34: Color Ramp RGB Linear, black @ 0, #B2B2B2 (Perceptual V 0.700, A) @ 1 = linear "
                         "%.4f (C)" % srgb_to_linear(0.700),
                         "A 26:42-26:50, 28:28: Hue/Saturation/Value Hue 0.5, Saturation 1, Factor 1, Value <- Glass Roughness"))
    with G.frame("Relief: Voronoi Smooth F1 -> Bump (4 mm)"):
        d = _voronoi(B, "voronoi", "A 26:57-27:22, 27:42: Voronoi 3D Smooth F1 Euclidean, Normalize off, Roughness 0.5, "
                                   "Lacunarity 2, Randomness 1; Scale 10 / Detail 2.6 / Smoothness 0.1 from the group",
                     I("Voronoi Scale"), "SMOOTH_F1", 1.0, smoothness=I("Voronoi Smoothness"), detail=I("Voronoi Detail"),
                     roughness=0.5)
        nrm = B.bump(d, I("Bump Strength"), 0.004, False, "bump",
                     "A 27:24-27:39, 27:42: Bump Invert off, Distance 0.004, Filter Width 0.1, Height <- Voronoi Distance")
    with G.frame("Glass BSDF"):
        B.glass(rough, nrm, "A 26:06-26:11, 27:42: Glass BSDF Multiscatter GGX; Roughness <- HSV Color, IOR 1.5")
    return G.finish()


def build_frosted():
    """Frosted Glass (spec b, video 29:50-33:24; graph 31:16, group 32:58)."""
    B = _Base("GlassFrosted", FROSTED_CONTROLS, "A 30:07, 31:16, 32:58: Mapping Point, Location 0, Rotation 0, Scale <- Scale")
    G, I = B.G, B.G.I
    with G.frame("Roughness: Noise -> Color Ramp -> Hue/Saturation/Value (Frosted Amount multiplies); no relief"):
        rough = B.frost(I("Frosted Scale"), I("Frosted Detail 1"), I("Frosted Detail 2"),
                        ((0.0, grey(0.342)), (1.0, grey(0.719))), I("Frosted Amount"),
                        ("A 30:03-30:19, 31:16: Noise 3D fBM Normalize, Lacunarity 2, Distortion 0; Scale 20 / Detail 15 / "
                         "Roughness 1 from the group; Factor -> ramp",
                         "A 30:35-30:56: Color Ramp RGB Linear, #575757 (V 0.342) @ 0 = linear %.4f, #B7B7B7 (V 0.719) @ 1 = "
                         "linear %.4f (A readouts, C conversion)" % (srgb_to_linear(0.342), srgb_to_linear(0.719)),
                         "A 31:01-31:12, 32:01: Hue/Saturation/Value Hue 0.5, Saturation 1, Factor 1, Value <- Frosted Amount"))
    with G.frame("Glass BSDF"):
        B.glass(rough, None, "A 30:22-30:28, 31:16: Glass BSDF Multiscatter GGX; Normal unconnected (no bump), IOR 1.5")
    return G.finish()


# ======================================================================================== materials
# name -> (builder, the video's group name, viewport alpha, viewport roughness: the mean BSDF roughness)
VARIANTS = {
    "GlassCircles": (build_circles, "Textured Glass Circles", 0.35, 0.2),
    "GlassVoronoi": (build_voronoi, "Textured Glass Voronoi", 0.3, 0.0),
    "GlassCells": (build_cells, "Textured Glass Cells", 0.45, 0.2),
    "GlassWavy": (build_wavy, "Textured Glass Wavy", 0.35, 0.2),
    "GlassBlobby": (build_blobby, "Textured Glass Blobby", 0.45, 0.22),
    "GlassFrosted": (build_frosted, "Frosted Glass", 0.6, 0.29),
}
VIEWPORT_RGB = (0.80, 0.85, 0.87)   # pale glass grey-blue for Solid mode and the road tool's flat glTF fallback (C)
EEVEE_SETTINGS = {"surface_render_method": "DITHERED", "use_raytrace_refraction": True}   # EEVEE refraction (C)


def build(variants=None):
    """Build the glass groups and materials (all six, or the names in `variants`). Returns the materials."""
    mats = []
    for name, (fn, title, alpha, rough) in VARIANTS.items():
        if variants and name not in variants and core.pm_name(name) not in variants: continue
        tree = fn()
        tree["pm_video_group"] = title
        m = core.contract_material(name, tree, viewport=VIEWPORT_RGB + (alpha,), roughness=rough, metallic=0.0,
                                   settings=EEVEE_SETTINGS)
        m["pm_source"] = SOURCE
        m["pm_video_group"] = title
        m["pm_road_use"] = "glazing: bus shelter glass (road_adapter.assign_shelter_glass), building windows later"
        mats.append(m)
    return mats


register(sys.modules[__name__])
