# Glass video, segment b: graph specification (Wavy, Blobby, Frosted)

Source: Ryan King Art, *Procedural Textured Frosted Glass Materials (Blender Tutorial)*, YouTube `SNKNqHd0AYI` (2026-05-12, 34:03), segment **b = 22:32-34:03** plus the customizable-nodes overview (00:40-02:42) and the scene setup (03:14-06:10). Machine-readable twin: `GRAPH_SPEC_b.json`. Operation log: `OPERATION_LOG_b.md`. Open points: `UNRESOLVED_b.md`. Decisions: `DECISIONS_b.md`. Evidence: `evidence/b/` (frames, crops, `index.json`).

Evidence classes: **A** seen in a frame, **B** narration only, **C** our inference, **D** unresolved. Blender in the video: **5.1.1** (status bar, A, `evidence/b/crops/t0537_blender_version.png`). Every value below that a builder needs is class A unless marked.

## What this segment builds

Three materials, each made as a flat node graph, then wrapped with Ctrl+G into a node group whose name is pasted from the material name, output socket renamed `BSDF` -> `Shader`, and controls exposed through the Group Input extension socket:

| material = node group | object | time | relief | roughness | exposed controls |
|---|---|---|---|---|---|
| Textured Glass Wavy | Plane.005 | 22:32-25:33 | Gabor 3D -> Bump (0.0007) | constant 0.2 | Scale, Glass Color, Glass Roughness, Glass IOR, Gabor Frequency, Bump Strength, Rotation |
| Textured Glass Blobby | Plane.003 | 25:33-29:50 | Voronoi Smooth F1 -> Bump (0.004) | Noise -> Ramp -> HSV Value | Scale, Glass Color, Glass Roughness, Glass IOR, Voronoi Scale/Detail/Smoothness, Noise Roughness Scale/Detail 1/Detail 2, Bump Strength |
| Frosted Glass | Plane.004 | 29:50-33:24 | none | Noise -> Ramp -> HSV Value | Scale, Glass Color, Frosted Amount, Glass IOR, Frosted Scale, Frosted Detail 1, Frosted Detail 2 |

All three use **Texture Coordinate Object -> Mapping (Point)** (added with Node Wrangler Ctrl+T) and a **Glass BSDF (Multiscatter GGX)**; nothing uses UVs or displacement.

## Textured Glass Wavy

Object `Plane.005`, video 22:32-25:33. Node group `Textured Glass Wavy` (one group, no nesting). Suggested library name (D3): `PM_GlassWavy` (C).

Key evidence (in `evidence/b/crops/`): `t2348_wavy_graph.png (whole graph before Ctrl+G)`; `t2338_wavy_bump_distance_text.png (0.0007)`; `t2348_wavy_gabor_ball.png / t2500_wavy_gabor_ball.png (orientation)`; `wavy_interface_panels.png (8 socket panels)`; `t2517_wavy_group_input_node.png, t2517_wavy_group_sockets_rotation.png`; `t2526_wavy_group_node.png (final group node)`.

### Final graph (text diagram)

```
[Texture Coordinate].Object --> [Mapping POINT].Vector
[Group Input].Scale ----------> [Mapping].Scale        (float -> vector)
[Group Input].Rotation -------> [Mapping].Rotation     (Euler)
[Mapping].Vector -------------> [Gabor 3D  scale 12  aniso 1  orient (0.797,0.604,0)].Vector
[Group Input].Gabor Frequency -> [Gabor].Frequency     (default 5)
[Gabor].Value ----------------> [Bump  distance 0.0007  filter 0.1].Height
[Group Input].Bump Strength --> [Bump].Strength
[Bump].Normal ----------------> [Glass BSDF  Multiscatter GGX].Normal
[Group Input].Glass Color/Roughness/IOR --> [Glass BSDF].Color/Roughness/IOR
[Glass BSDF].BSDF ------------> [Group Output].Shader
material:  [Textured Glass Wavy group].Shader --> [Material Output (All)].Surface
```

### Node inventory (inside the group)

| node | type | settings | input values | class | evidence |
|---|---|---|---|---|---|
| Group Input (`group_input`) | `NodeGroupInput` | - | - | A | 25:17 |
| Group Output (`group_output`) | `NodeGroupOutput` | - | - | A | 24:06 |
| Texture Coordinate (`tex_coord`) | `ShaderNodeTexCoord` | from_instancer=False, object=- | - | A | 22:47, 23:48 |
| Mapping (`mapping`) | `ShaderNodeMapping` | vector_type=POINT | Location=(0, 0, 0); linked: Vector, Rotation, Scale | A | 22:50, 23:48, 25:17 |
| Gabor Texture (`gabor`) | `ShaderNodeTexGabor` | gabor_type=3D | Scale=12, Anisotropy=1, Orientation 3D=(0.797, 0.604, 0); linked: Vector, Frequency; output used: Value | A (Orientation 3D C) | 22:38, 22:50, 22:55, 23:05-23:11, 23:48, 25:00.9 |
| Bump (`bump`) | `ShaderNodeBump` | invert=False | Distance=0.0007, Filter Width=0.1; linked: Strength, Height | A | 23:24-23:30, 23:38, 23:48 |
| Glass BSDF (`glass`) | `ShaderNodeBsdfGlass` | distribution=MULTI_GGX | Thin Film Thickness=0, Thin Film IOR=1.33; linked: Color, Roughness, IOR, Normal | A (Thin Film Thickness C, Thin Film IOR C) | 23:21, 23:44, 23:48 |

- **Group Output**: Single input "Shader" fed by the Glass BSDF.
- **Texture Coordinate**: Added by Node Wrangler Ctrl+T (with Mapping); the Object output is used (narration: "use the object coordinates"). No object is set in the Object field.
- **Mapping**: Float group input "Scale" drives the Vector Scale socket (implicit float->vector (s,s,s)).
- **Gabor Texture**: 2D->3D at 22:52-22:55. Scale 12 and Frequency 5 typed 23:05-23:11 (Frequency 5.0 later becomes the group default). Anisotropy left at 1.0. Orientation 3D is NOT shown as numbers: the direction-ball widget was measured by a shading fit (see measurements.gabor_orientation_fit): (0.796,0.605,-0.009) at 23:48.5 and (0.799,0.602,-0.007) at 25:00.9; recommended (0.797, 0.604, 0.0). Socket identifier is "Orientation 3D" (two inputs are named "Orientation").
- **Bump**: Distance typed "0.0007" at 23:38 (crop); the field then displays 0.001 (3-decimal rounding). Strength 1.0 before grouping, then driven by "Bump Strength". Normal input unconnected. Invert unchecked.
- **Glass BSDF**: Before grouping: Color white, Roughness 0.2 (typed 23:41-23:44), IOR 1.5 (default); these values became the interface defaults. Distribution Multiscatter GGX. Thin Film panel collapsed (defaults assumed, C).

### Connections

| source node | output socket | destination node | input socket | timestamp | class / confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 22:48 | A high |
| mapping | Vector | gabor | Vector | 22:47 (Ctrl+T) | A high |
| gabor | Value | bump | Height | 23:28 | A high |
| bump | Normal | glass | Normal | 23:30 | A high |
| glass | BSDF | group_output | Shader | 23:53 (Ctrl+G) | A high |
| group_input | Scale | mapping | Scale | 24:15 | A high |
| group_input | Glass Color | glass | Color | 24:34 | A high |
| group_input | Glass Roughness | glass | Roughness | 24:37 | A high |
| group_input | Glass IOR | glass | IOR | 24:38 | A high |
| group_input | Gabor Frequency | gabor | Frequency | 24:53 | A high |
| group_input | Bump Strength | bump | Strength | 25:06 | A high |
| group_input | Rotation | mapping | Rotation | 25:15 | A high |

Top level of the material: `group_node`.Shader -> `material_output`.Surface (23:56). Material Output target All. Link times are transcript-based (+-2 s); every link is confirmed in the final frames.

### Group interface

Order as in the N panel (output first). Socket panels: `evidence/b/crops/wavy_interface_panels.png`.

| control | socket type / subtype | default | min .. max | internal destination | visible effect | evidence (class) |
|---|---|---|---|---|---|---|
| Shader (output) | NodeSocketShader | - | - | fed by glass.BSDF | shader result | 24:06-24:10 (wavy), 28:14-28:18 (blobby), 31:34-31:37 (frosted) |
| Scale | NodeSocketFloat | 1 | -inf .. inf | mapping.Scale (float -> vector) | uniform pattern size (1 = tutorial size) | 24:15, 24:19, 24:23 (A) |
| Glass Color | NodeSocketColor | (1, 1, 1, 1) | - | glass.Color | tint | 24:41 (A) |
| Glass Roughness | NodeSocketFloat / FACTOR | 0.2 | 0 .. 1 | glass.Roughness | frost / blur | 24:45 (A) |
| Glass IOR | NodeSocketFloat | 1.5 | 0 .. 1000 | glass.IOR | refraction strength | 24:49 (A) |
| Gabor Frequency | NodeSocketFloat | 5 | 0 .. inf | gabor.Frequency | wave density | 24:53, 25:02 (A) |
| Bump Strength | NodeSocketFloat / FACTOR | 1 | 0 .. 1 | bump.Strength | wave relief strength | 25:06, 25:10 (A) |
| Rotation | NodeSocketVector / EULER | (0, 0, 0) | -inf .. inf | mapping.Rotation | rotates the wave direction (overview demo rotates Y) | 25:15, 25:17 (A) |

- **Shader**: Created by Ctrl+G as "BSDF" (from Glass BSDF output) and renamed "Shader" in the N panel.
- **Scale**: Created as Vector from Mapping Scale, type changed Vector->Float (24:19), default set to 1 (24:23); instance value reset to 1 outside the group (24:24-24:28).
- **Glass Color**: White swatch (exact RGBA 1,1,1,1 is the Glass BSDF default, C).
- **Rotation**: Dimensions 3, defaults 0 deg.

Final group-node values at the end of the part: Scale 1, Glass Color (1, 1, 1, 1), Glass Roughness 0.2, Glass IOR 1.5, Gabor Frequency 5, Bump Strength 1, Rotation (0, 0, 0) (all equal to the interface defaults; A, 25:26 (t2526), 25:31).

### Product-file variant shown in the overview (not built in the tutorial)

customizable-nodes overview 01:59-02:15 (purchased project file, objects named Cube.*). Controls: Scale 1; Glass Color white; Glass Roughness 0.2 factor bar; Glass IOR 1.5; Bump Strength 1 factor bar; Rotation (0, 0, 0) vector, degrees. **Difference**: no "Gabor Frequency" control in the product file; otherwise the same names, order and defaults. Internal graph not shown (D).
 Demo: Rotation Y dragged 65.5, 32.1, 60.6, 26.9 deg and reset (02:10-02:14): rotating Y turns the wave direction in the pane.

### Temporary states (not part of the final graph)

- 22:41-23:20: Node Wrangler preview (Ctrl+Shift+click) of the Gabor: Gabor Value wired straight to Material Output Surface; replaced when the Glass BSDF was dropped on the link
- 22:50-22:55: Gabor in 2D (default): stripes uniform along Z because the plane lies at y=0 in object space; switched to 3D
- 22:57-23:16: two orientation-ball drags (intermediate directions not recorded); final direction measured from 23:48 on
- 23:21-23:32: Glass BSDF dropped on the preview link -> Gabor Value -> Glass Color (temporary); unplugged at 23:32
- 23:38-23:41: Glass roughness 0.0 (Glass BSDF default) until set to 0.2
- 24:21-24:28: group-node Scale not 1 after the Vector->Float change (texture missing, narration; value not read, B); reset to 1.0 outside the group
- 25:21-25:26: Rotation X dragged to 1.4 deg (demo), back to 0

### Notes

- Plane lies in the object X-Z plane (normal -Y); the orientation (0.797, 0.604, 0) projects onto the pane as a wave vector along X only, so the crests run vertically; the in-plane frequency is 12 x 5 x 0.797 = 47.8 cycles/m (period ~2.1 cm on the 0.8 m pane) (C).
- Gabor Scale (12) is deliberately not exposed: "we are already using the scale with the mapping" (25:00, B).

## Textured Glass Blobby

Object `Plane.003`, video 25:33-29:50. Node group `Textured Glass Blobby` (one group, no nesting). Suggested library name (D3): `PM_GlassBlobby` (C).

Key evidence (in `evidence/b/crops/`): `t2742_blobby_graph.png (whole graph before Ctrl+G)`; `t2742_blobby_noise_factor_link.png (Factor, not Color)`; `t2633_blobby_ramp_picker.png (stop 1 = V 0.700, #B2B2B2)`; `blobby_interface_panels.png (10 socket panels)`; `t2833_blobby_iface_glass_roughness.png`; `t2933_blobby_group_interior.png (all group links)`; `t2941_blobby_group_node.png`.

### Final graph (text diagram)

```
[Texture Coordinate].Object --> [Mapping POINT].Vector ;  [Group Input].Scale --> [Mapping].Scale
[Mapping].Vector --+--> [Noise 3D fBM normalize  lac 2  dist 0].Vector
                   +--> [Voronoi 3D Smooth F1 Euclidean  rough 0.5  lac 2  rand 1].Vector
[Group Input].Noise Roughness Scale / Detail 1 / Detail 2 --> [Noise].Scale / Detail / Roughness
[Noise].Factor --> [Color Ramp RGB Linear: 0.0 black | 1.0 grey 0.448 lin].Fac
[Color Ramp].Color --> [Hue/Sat/Value  hue 0.5 sat 1 fac 1].Color ; [Group Input].Glass Roughness --> [HSV].Value
[HSV].Color --> [Glass BSDF].Roughness
[Group Input].Voronoi Scale / Detail / Smoothness --> [Voronoi].Scale / Detail / Smoothness
[Voronoi].Distance --> [Bump  distance 0.004  filter 0.1].Height ; [Group Input].Bump Strength --> [Bump].Strength
[Bump].Normal --> [Glass BSDF  Multiscatter GGX].Normal
[Group Input].Glass Color / Glass IOR --> [Glass BSDF].Color / IOR
[Glass BSDF].BSDF --> [Group Output].Shader
material:  [Textured Glass Blobby group].Shader --> [Material Output (All)].Surface
```

### Node inventory (inside the group)

| node | type | settings | input values | class | evidence |
|---|---|---|---|---|---|
| Group Input (`group_input`) | `NodeGroupInput` | - | - | A | 29:33 |
| Group Output (`group_output`) | `NodeGroupOutput` | - | - | A | 28:14 |
| Texture Coordinate (`tex_coord`) | `ShaderNodeTexCoord` | from_instancer=False, object=- | - | A | 25:45, 27:42 |
| Mapping (`mapping`) | `ShaderNodeMapping` | vector_type=POINT | Location=(0, 0, 0), Rotation=(0, 0, 0); linked: Vector, Scale | A | 25:45, 27:42, 29:33 |
| Noise Texture (`noise`) | `ShaderNodeTexNoise` | noise_dimensions=3D, noise_type=FBM, normalize=True | Lacunarity=2, Distortion=0; linked: Vector, Scale, Detail, Roughness; output used: Factor | A | 25:42, 25:52-25:58, 27:42, 29:33 |
| Color Ramp (`color_ramp`) | `ShaderNodeValToRGB` | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR | linked: Fac | A | 26:18-26:22, 26:23-26:34, 27:42 |
| Hue/Saturation/Value (`hsv`) | `ShaderNodeHueSaturation` | - | Hue=0.5, Saturation=1, Fac=1; linked: Value, Color | A | 26:42-26:50, 27:42, 29:33 |
| Voronoi Texture (`voronoi`) | `ShaderNodeTexVoronoi` | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=EUCLIDEAN, normalize=False | Roughness=0.5, Lacunarity=2, Randomness=1; linked: Vector, Scale, Detail, Smoothness; output used: Distance | A | 26:57, 27:04-27:22, 27:42, 29:33 |
| Bump (`bump`) | `ShaderNodeBump` | invert=False | Distance=0.004, Filter Width=0.1; linked: Strength, Height | A | 27:24-27:31, 27:35-27:39, 27:42 |
| Glass BSDF (`glass`) | `ShaderNodeBsdfGlass` | distribution=MULTI_GGX | Thin Film Thickness=0, Thin Film IOR=1.33; linked: Color, Roughness, IOR, Normal | A (Thin Film Thickness C, Thin Film IOR C) | 26:06-26:11, 27:42, 28:33 |

- **Group Output**: Single input "Shader" fed by the Glass BSDF.
- **Texture Coordinate**: Added by Node Wrangler Ctrl+T (with Mapping); the Object output is used (narration: "use the object coordinates"). No object is set in the Object field.
- **Mapping**: Float group input "Scale" drives the Vector Scale socket (implicit float->vector (s,s,s)).
- **Noise Texture**: Scale 20, Detail 15, Roughness 1.0 typed 25:52-25:58; they become the defaults of Noise Roughness Scale / Detail 1 / Detail 2. Output used: Factor (crop shows the link starting at Factor).
- **Hue/Saturation/Value**: Inserted after the ramp so its Value acts as a roughness multiplier (roughness = ramp grey x Value). Value 1.0 before grouping; becomes "Glass Roughness" (0..2). Factor socket identifier is "Fac".
- **Voronoi Texture**: F1 -> Smooth F1 (27:05), Scale 10 (27:10), Detail 2.6 (27:12-27:14), Smoothness 0.1 (27:18-27:21); Roughness/Lacunarity/Randomness left at defaults 0.5/2.0/1.0. Output used: Distance.
- **Bump**: Distance field showed 0.001 (Blender 5.x default) and was edited to 0.004 at 27:37-27:38. Strength 1.0 before grouping. Normal input unconnected.
- **Glass BSDF**: Before grouping: Color white, IOR 1.5 (defaults). Roughness driven by HSV Color (colour->float conversion of a grey = the grey value).

### Colour ramp stops

Colour mode RGB, interpolation Linear (A). The picker was in Perceptual + HSV mode; hex is display sRGB. Ramp colours are stored scene-linear, so the builder sets the linear grey (sRGB EOTF of V, class C).

| stop | position | V (perceptual, as read) | hex (as read) | linear RGB to set | class | note |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | #000000 | (0, 0, 0) | A | default black stop, not edited |
| 1 | 1 | 0.7 | #B2B2B2 | (0.448, 0.448, 0.448) | A (perceptual V and hex read) / C (linear conversion) | white stop darkened to a light grey ("light gray or a mid gray"); picker shows Perceptual + HSV, V 0.700, Hex #B2B2B2. Linear = sRGB EOTF(0.700) = 0.448 (hex-quantised 0.445). |

### Connections

| source node | output socket | destination node | input socket | timestamp | class / confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 25:48 | A high |
| mapping | Vector | noise | Vector | 25:45 (Ctrl+T) | A high |
| mapping | Vector | voronoi | Vector | 27:00 | A high |
| noise | Factor | color_ramp | Fac | 26:13 / 26:20 (ramp inserted on the link) | A high |
| color_ramp | Color | hsv | Color | 26:46 (HSV inserted on the link) | A high |
| hsv | Color | glass | Roughness | 26:46 | A high |
| voronoi | Distance | bump | Height | 27:27 | A high |
| bump | Normal | glass | Normal | 27:29 | A high |
| glass | BSDF | group_output | Shader | 27:46 (Ctrl+G) | A high |
| group_input | Scale | mapping | Scale | 28:00 | A high |
| group_input | Glass Color | glass | Color | 28:21 | A high |
| group_input | Glass Roughness | hsv | Value | 28:28 | A high |
| group_input | Glass IOR | glass | IOR | 28:33 | A high |
| group_input | Voronoi Scale | voronoi | Scale | 28:42 | A high |
| group_input | Voronoi Detail | voronoi | Detail | 28:43 | A high |
| group_input | Voronoi Smoothness | voronoi | Smoothness | 28:46 | A high |
| group_input | Noise Roughness Scale | noise | Scale | 29:04 | A high |
| group_input | Noise Roughness Detail 1 | noise | Detail | 29:06 | A high |
| group_input | Noise Roughness Detail 2 | noise | Roughness | 29:07 | A high |
| group_input | Bump Strength | bump | Strength | 29:28 | A high |

Top level of the material: `group_node`.Shader -> `material_output`.Surface (27:51). Material Output target All. Link times are transcript-based (+-2 s); every link is confirmed in the final frames.

### Group interface

Order as in the N panel (output first). Socket panels: `evidence/b/crops/blobby_interface_panels.png`.

| control | socket type / subtype | default | min .. max | internal destination | visible effect | evidence (class) |
|---|---|---|---|---|---|---|
| Shader (output) | NodeSocketShader | - | - | fed by glass.BSDF | shader result | 24:06-24:10 (wavy), 28:14-28:18 (blobby), 31:34-31:37 (frosted) |
| Scale | NodeSocketFloat | 1 | -inf .. inf | mapping.Scale | uniform pattern size | 28:00, 28:05-28:13 (A) |
| Glass Color | NodeSocketColor | (1, 1, 1, 1) | - | glass.Color | tint | 28:21-28:25 (A) |
| Glass Roughness | NodeSocketFloat | 1 | 0 .. 2 | hsv.Value | multiplies the noise-driven roughness (0 = clear, 2 = twice as frosted) | 28:28-28:33 (A) |
| Glass IOR | NodeSocketFloat | 1.5 | 0 .. 1000 | glass.IOR | refraction | 28:35-28:37 (A) |
| Voronoi Scale | NodeSocketFloat | 10 | -1000 .. 1000 | voronoi.Scale | blob size | 28:42, 28:55-28:59 (A) |
| Voronoi Detail | NodeSocketFloat | 2.6 | 0 .. 15 | voronoi.Detail | small blobs inside blobs | 28:43, 29:41 (value) (A (default) / C (min, max)) |
| Voronoi Smoothness | NodeSocketFloat / FACTOR | 0.1 | 0 .. 1 | voronoi.Smoothness | blob edge softness | 28:46, 29:03 (A) |
| Noise Roughness Scale | NodeSocketFloat | 20 | -1000 .. 1000 | noise.Scale | size of the roughness speckle | 29:04, 29:13-29:15 (A) |
| Noise Roughness Detail 1 | NodeSocketFloat | 15 | 0 .. 15 | noise.Detail | roughness speckle octaves | 29:06, 29:07.5, 29:16-29:24 (A) |
| Noise Roughness Detail 2 | NodeSocketFloat / FACTOR | 1 | 0 .. 1 | noise.Roughness | second layer of speckle detail | 29:07, 29:23-29:26 (A) |
| Bump Strength | NodeSocketFloat / FACTOR | 1 | 0 .. 1 | bump.Strength | blob relief | 29:28-29:32 (A) |

- **Shader**: Created by Ctrl+G as "BSDF" (from Glass BSDF output) and renamed "Shader" in the N panel.
- **Scale**: Vector->Float, default 1, instance reset to 1 outside the group.
- **Voronoi Detail**: Panel never selected on screen; min 0 / max 15 are the Voronoi Detail socket limits (same as the Noise Detail panel).

Final group-node values at the end of the part: Scale 1, Glass Color (1, 1, 1, 1), Glass Roughness 1, Glass IOR 1.5, Voronoi Scale 10, Voronoi Detail 2.6, Voronoi Smoothness 0.1, Noise Roughness Scale 20, Noise Roughness Detail 1 15, Noise Roughness Detail 2 1, Bump Strength 1 (all equal to the interface defaults; A, 29:41 (t2941)).

### Product-file variant shown in the overview (not built in the tutorial)

customizable-nodes overview 02:15-02:27 (purchased project file). Controls: Scale 1; Glass Color white; Glass Roughness 1; Glass IOR 1.5; Voronoi Scale 10; Voronoi Detail 2.6; Voronoi Roughness 0.5 factor bar; Voronoi Smoothness 0.1 factor bar; Bump Strength 1 factor bar. **Difference**: product exposes "Voronoi Roughness" (0.5) and does NOT expose the three noise-roughness controls built in the tutorial. Internal graph not shown (D).

### Temporary states (not part of the final graph)

- 25:50-26:05: noise previewed (Ctrl+Shift+click)
- 26:13-26:22: Noise Factor directly into Glass Roughness before the ramp was inserted
- 26:23-26:33: white ramp stop dragged from 1.0 down through ~0.71 to the final 0.700
- 27:00-27:31: Voronoi previewed; glass previewed again at 27:31
- 29:37-29:46: demo: Scale 4.7 and Glass Color green (#1AFF1BFF, H 0.334 S 0.896 V 1.0), then back to defaults

### Notes

- Roughness = ramp(noise Factor) x Glass Roughness: ramp maps 0 -> black, 1 -> 0.448 linear grey, so with the normalised noise around 0.5 the roughness sits near 0.22 (C).
- Bump height = Smooth-F1 Voronoi distance (fractal, detail 2.6) x 0.004 m (C: object space, unit-scale object).
- Voronoi feature size ~1/10 m, roughness speckle ~1/20 m at Scale 1 (C).

## Frosted Glass

Object `Plane.004`, video 29:50-33:24. Node group `Frosted Glass` (one group, no nesting). Suggested library name (D3): `PM_GlassFrosted` (C).

Key evidence (in `evidence/b/crops/`): `t3116_frosted_graph.png (whole graph before Ctrl+G)`; `t3116_frosted_noise_factor_link.png`; `t3044_frosted_ramp_stop0_temp.png (temporary 0.415)`; `t3051_frosted_ramp_stop1.png (0.719)`; `t3055_frosted_ramp_stop0.png (0.342)`; `frosted_interface_panels.png (7 socket panels)`; `t3258_frosted_group_interior.png`; `t3303_frosted_group_node.png`.

### Final graph (text diagram)

```
[Texture Coordinate].Object --> [Mapping POINT].Vector ;  [Group Input].Scale --> [Mapping].Scale
[Mapping].Vector --> [Noise 3D fBM normalize  lac 2  dist 0].Vector
[Group Input].Frosted Scale / Frosted Detail 1 / Frosted Detail 2 --> [Noise].Scale / Detail / Roughness
[Noise].Factor --> [Color Ramp RGB Linear: 0.0 grey 0.0958 lin | 1.0 grey 0.4755 lin].Fac
[Color Ramp].Color --> [Hue/Sat/Value  hue 0.5 sat 1 fac 1].Color ; [Group Input].Frosted Amount --> [HSV].Value
[HSV].Color --> [Glass BSDF  Multiscatter GGX].Roughness       (Normal unconnected: no bump)
[Group Input].Glass Color / Glass IOR --> [Glass BSDF].Color / IOR
[Glass BSDF].BSDF --> [Group Output].Shader
material:  [Frosted Glass group].Shader --> [Material Output (All)].Surface
```

### Node inventory (inside the group)

| node | type | settings | input values | class | evidence |
|---|---|---|---|---|---|
| Group Input (`group_input`) | `NodeGroupInput` | - | - | A | 32:58 |
| Group Output (`group_output`) | `NodeGroupOutput` | - | - | A | 31:34 |
| Texture Coordinate (`tex_coord`) | `ShaderNodeTexCoord` | from_instancer=False, object=- | - | A | 30:07, 31:16 |
| Mapping (`mapping`) | `ShaderNodeMapping` | vector_type=POINT | Location=(0, 0, 0), Rotation=(0, 0, 0); linked: Vector, Scale | A | 30:07, 31:16, 32:58 |
| Noise Texture (`noise`) | `ShaderNodeTexNoise` | noise_dimensions=3D, noise_type=FBM, normalize=True | Lacunarity=2, Distortion=0; linked: Vector, Scale, Detail, Roughness; output used: Factor | A | 30:03, 30:13-30:19, 31:16, 32:58 |
| Color Ramp (`color_ramp`) | `ShaderNodeValToRGB` | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR | linked: Fac | A | 30:35-30:40, 30:40-30:56, 31:16 |
| Hue/Saturation/Value (`hsv`) | `ShaderNodeHueSaturation` | - | Hue=0.5, Saturation=1, Fac=1; linked: Value, Color | A | 31:01-31:08, 31:08-31:12 (demo 0 -> 2 -> 1), 31:16 |
| Glass BSDF (`glass`) | `ShaderNodeBsdfGlass` | distribution=MULTI_GGX | Thin Film Thickness=0, Thin Film IOR=1.33; linked: Color, Roughness, IOR | A (Thin Film Thickness C, Thin Film IOR C) | 30:22-30:28, 31:16 |

- **Group Output**: Single input "Shader" fed by the Glass BSDF.
- **Texture Coordinate**: Added by Node Wrangler Ctrl+T (with Mapping); the Object output is used (narration: "use the object coordinates"). No object is set in the Object field.
- **Mapping**: Float group input "Scale" drives the Vector Scale socket (implicit float->vector (s,s,s)).
- **Noise Texture**: Scale 20, Detail 15, Roughness 1.0 (30:13-30:19); become defaults of Frosted Scale / Frosted Detail 1 / Frosted Detail 2. Output used: Factor.
- **Hue/Saturation/Value**: Value demonstrated at 0.0 and 2.0, left at 1.0; becomes "Frosted Amount" (renamed from Glass Roughness).
- **Glass BSDF**: No bump: Normal input unconnected. Before grouping Color white, IOR 1.5 (defaults).

### Colour ramp stops

Colour mode RGB, interpolation Linear (A). The picker was in Perceptual + HSV mode; hex is display sRGB. Ramp colours are stored scene-linear, so the builder sets the linear grey (sRGB EOTF of V, class C).

| stop | position | V (perceptual, as read) | hex (as read) | linear RGB to set | class | note |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.342 | #575757 | (0.0958, 0.0958, 0.0958) | A (perceptual V and hex) / C (linear) | black stop first lifted to V 0.415 (#6A6A6A, 30:41-30:44), then re-edited to the final V 0.342 at 30:53-30:55.5 ("make like a dark color") |
| 1 | 1 | 0.719 | #B7B7B7 | (0.4755, 0.4755, 0.4755) | A (perceptual V and hex) / C (linear) | white stop darkened 1.0 -> 0.719 -> 0.399 -> 0.186 -> 0.283, closed, reopened, 0.687 -> 0.729 -> final 0.719 (30:45-30:52) ("light color") |

### Connections

| source node | output socket | destination node | input socket | timestamp | class / confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 30:09 | A high |
| mapping | Vector | noise | Vector | 30:07 (Ctrl+T) | A high |
| noise | Factor | color_ramp | Fac | 30:28 / 30:38 (ramp inserted on the link) | A high |
| color_ramp | Color | hsv | Color | 31:05 (HSV inserted on the link) | A high |
| hsv | Color | glass | Roughness | 31:05 | A high |
| glass | BSDF | group_output | Shader | 31:20 (Ctrl+G) | A high |
| group_input | Scale | mapping | Scale | 31:41 | A high |
| group_input | Glass Color | glass | Color | 31:58 | A high |
| group_input | Frosted Amount | hsv | Value | 32:01 | A high |
| group_input | Glass IOR | glass | IOR | 32:05 | A high |
| group_input | Frosted Scale | noise | Scale | 32:22 | A high |
| group_input | Frosted Detail 1 | noise | Detail | 32:25 | A high |
| group_input | Frosted Detail 2 | noise | Roughness | 32:26 | A high |

Top level of the material: `group_node`.Shader -> `material_output`.Surface (31:24). Material Output target All. Link times are transcript-based (+-2 s); every link is confirmed in the final frames.

### Group interface

Order as in the N panel (output first). Socket panels: `evidence/b/crops/frosted_interface_panels.png`.

| control | socket type / subtype | default | min .. max | internal destination | visible effect | evidence (class) |
|---|---|---|---|---|---|---|
| Shader (output) | NodeSocketShader | - | - | fed by glass.BSDF | shader result | 24:06-24:10 (wavy), 28:14-28:18 (blobby), 31:34-31:37 (frosted) |
| Scale | NodeSocketFloat | 1 | -inf .. inf | mapping.Scale | pattern size (barely visible: very fine noise, narration 33:04) | 31:42, 31:44-31:49 (A) |
| Glass Color | NodeSocketColor | (1, 1, 1, 1) | - | glass.Color | tint | 32:09 (A) |
| Frosted Amount | NodeSocketFloat | 1 | 0 .. 2 | hsv.Value | more / less frosted (roughness multiplier) | 32:01, 32:13, 32:46-32:54 (A) |
| Glass IOR | NodeSocketFloat | 1.5 | 0 .. 1000 | glass.IOR | refraction | 32:16-32:19 (A) |
| Frosted Scale | NodeSocketFloat | 20 | -1000 .. 1000 | noise.Scale | frost grain size | 32:22, 32:30-32:36 (A) |
| Frosted Detail 1 | NodeSocketFloat | 15 | 0 .. 15 | noise.Detail | frost octaves | 32:25, 32:37-32:42 (A) |
| Frosted Detail 2 | NodeSocketFloat / FACTOR | 1 | 0 .. 1 | noise.Roughness | second detail layer | 32:26, 32:42-32:44, 33:03 (value, factor bar) (A (default, factor display) / C (min, max)) |

- **Shader**: Created by Ctrl+G as "BSDF" (from Glass BSDF output) and renamed "Shader" in the N panel.
- **Scale**: Default shown 0.000 after the type change, set to 1.000; instance reset to 1.
- **Frosted Amount**: First named "Glass Roughness" (32:12-32:15); renamed "Frosted Amount" (a transient typo "Frsoted" is visible while typing at 32:53; final name read at 33:03).
- **Frosted Scale**: Renamed "Noise Scale" -> "Noise Roughness Scale" -> "Frosted Scale".
- **Frosted Detail 2**: Panel never selected; Factor 0..1 are the Noise Roughness socket limits (the blobby twin socket shows Factor 0..1 at 29:26).

Final group-node values at the end of the part: Scale 1, Glass Color (1, 1, 1, 1), Frosted Amount 1, Glass IOR 1.5, Frosted Scale 20, Frosted Detail 1 15, Frosted Detail 2 1 (all equal to the interface defaults; A, 33:03 (t3303), 33:23).

### Product-file variant shown in the overview (not built in the tutorial)

customizable-nodes overview 02:27-02:43 (purchased project file). Controls: Scale dragged (16.7, -3.6); default not seen; Glass Color white; Glass Roughness 1; Glass IOR 1.5; Noise Scale 20; Noise Detail 15; Noise Roughness 1 factor bar. **Difference**: product names: Glass Roughness / Noise Scale / Noise Detail / Noise Roughness; tutorial build renames them Frosted Amount / Frosted Scale / Frosted Detail 1 / Frosted Detail 2. Internal graph not shown (D).

### Temporary states (not part of the final graph)

- 30:11-30:20: noise previewed; a temporary link from the noise into the Principled BSDF before it was deleted (30:20-30:26)
- 30:28-30:38: Noise Factor directly into Glass Roughness before the ramp was inserted ("too rough")
- 30:41-30:44: ramp stop 0 at V 0.415 (#6A6A6A), later re-edited to 0.342
- 31:08-31:12: HSV Value demo 0.0 and 2.0, left at 1.0
- 33:04-33:18: group demo: Frosted Amount 2.0, Glass IOR 0.0, Frosted Detail 2 0.99, then back to defaults

### Notes

- Roughness = ramp(noise Factor) x Frosted Amount; ramp maps 0 -> 0.0958, 1 -> 0.4755 linear, so roughness ~0.29 around the noise mean 0.5 (C).
- No bump / normal: the frosted look is roughness only.

## Measurement: Gabor Orientation 3D (Wavy)

The video never shows the vector as numbers; the socket is drawn as a direction ball. Blender draws the Orientation 3D socket as a direction ball lit by the vector (x = screen right, y = screen up, z = toward viewer: Blender UNITVEC widget). Inside the ball we fitted brightness = gain * max(0, n.w) + offset over all pixels (n = sphere normal from the circle) and solved for the unit vector w.

| time | frame / crop | fitted unit vector | rmse |
|---|---|---|---|
| 22:54.95-22:55.23 (default check) | - | (0.706, 0.704, -0.08) | 0.045 |
| 23:48.48 | `t2348_wavy_gabor_ball.png` | (0.796, 0.605, -0.009) | 0.0055 |
| 25:00.86 | `t2500_wavy_gabor_ball.png` | (0.799, 0.602, -0.007) | 0.0043 |

Default check: Blender 5.x default Orientation 3D (sqrt2, sqrt2, 0) normalised = (0.707, 0.707, 0); mouse cursor over the ball raises the error; the default is recovered within ~0.01 in x/y. **Use (0.797, 0.604, 0.0)** (C, +-0.02 per component; z ~ 0 is consistent with the drag ending outside the circle (rim clamp); azimuth 37.1 deg from +X towards +Y). On the video pane (object X-Z plane) only the X component lies in the surface, so the crests run vertically and the in-plane frequency is 0.797 x 12 x 5 = 47.8 cycles/m.

## Scene setup (03:14-06:10, shared glass base)

| item | value | class | evidence |
|---|---|---|---|
| geometry | 6 planes in a 3 x 2 grid: default 2 m plane, S 0.4 (0.8 x 0.8 m), R X 90 deg, Ctrl+A Rotation & Scale applied, then Shift+D copies along X and down Z | A (scale 0.4, rotate X 90, apply menu) / B (apply rotation & scale) / D (exact offsets) | `evidence/b/crops/t0324_scale_header.png`, `evidence/b/crops/t0330_rotate_apply.png` |
| objects of segment b | Wavy Plane.005, Blobby Plane.003, Frosted Plane.004 | A | breadcrumbs in the node editor |
| thickness | planes have no thickness in the tutorial scene (C); the product file uses Cube objects (overview breadcrumbs "Cube.006 > Cube.008") | C / A | overview breadcrumbs |
| background objects | Suzanne monkeys scaled down (scale applied) behind the panes, material "Red" = Principled with a strong red Base Color (A visually; exact RGB D); status bar shows 11 objects | A / D | 03:50-04:26 |
| modifiers | none added | A | 03:14-06:10 |
| camera | Camera object (data Camera.001), Perspective, focal length 50 mm, clip 0.1-1000 m, aligned with Ctrl+Alt+Numpad0 then moved (G, G+MMB dolly) | A (lens panel) / D (transform) | `evidence/b/crops/t0440_camera_lens.png` |
| lighting | World Background <- Environment Texture "old_apartments_walkway_1k.hdr" (Poly Haven), Linear, Equirectangular, Single Image, colour space Linear Rec.709, alpha Premultiplied, Vector Default; Background Strength 0.5. No lamps added. | A | `evidence/b/crops/t0516_world_hdri.png` |
| HDRI in this project | D6: not downloaded; use a bundled studio-light HDRI and report lighting differences separately | decision | DECISIONS.md D6 |
| render engine | Cycles, GPU Compute | A | `evidence/b/crops/t0450_render_engine.png` |
| samples | viewport 100 ("Sample n/100" overlay); final render samples not shown | A / D | viewport overlay |
| film | exposure 1.0, Blackman-Harris 1.50 px, Transparent on | A | `evidence/b/crops/t0529_film_transparent.png` |
| colour management | display sRGB, view Filmic, look Very High Contrast, exposure 0, gamma 1 | A | `evidence/b/crops/t0537_color_management.png` |
| texture coordinates | Object output -> Mapping Point (location 0, rotation 0 unless exposed, scale from group) | A | all three graphs |
| displacement | none; bump through the Glass Normal (Wavy, Blobby); material displacement method not shown | A / D | graphs |
| Blender | 5.1.1 | A | status bar |

## Reference frames of the finished look

| time | frame | what |
|---|---|---|
| 00:04 | `t0004_intro_final_render_six_panes.png` | final render, product scene: six glass panes in black frames on a dark studio floor; bottom row = Wavy | Blobby | Frosted (crop t0004_render_bottom_row.png) |
| 33:26 | `t3326_closing_final_render_six_panes.png` | closing render, same product scene and layout |
| 33:23 | `t3323_closing_viewport_all_panes.png` | tutorial scene in the rendered viewport (Cycles, camera view, HDRI 0.5, film transparent): six planes with red Suzannes behind; Frosted group node shown |
| 25:26 | `t2526_wavy_final_group_node.png` | Wavy pane (tutorial build) in the viewport: vertical wavy refraction streaks over the red monkey |
| 29:41 | `t2941_blobby_final_group_node.png` | Blobby pane (tutorial build): crinkled refraction with fine roughness speckle |
| 33:03 | `t3303_frosted_final_group_node.png` | Frosted pane (tutorial build): uniformly blurred monkey |
| 02:03 | `t0203_overview_product_wavy_group.png` | product-file Wavy pane in the viewport (Cube object) with its controls |
| 02:16 | `t0216_overview_product_blobby_group.png` | product-file Blobby pane in the viewport |
| 02:30 | `t0230_overview_product_frosted_group.png` | product-file Frosted pane in the viewport |

The intro and closing renders are the purchased product scene (cube panes in black frames, dark studio, own lighting), not the tutorial scene; the tutorial look is the Cycles viewport over the red Suzannes with the HDRI at strength 0.5. Compare lighting separately (D6).

## Notes for the builder (class C)

- D5: the Gabor Texture has only 2D/3D modes, so the 4D torus (seamless) mode of the library contract cannot use it as-is; the Wavy needs a mode adaptation (e.g. periodic construction along the wave vector), listed as a version/mode adaptation.
- The Wavy direction depends on the surface orientation in object space: the video pane is the X-Z plane, so (0.797, 0.604, 0) acts as a wave along X. On an X-Y surface (road-tool or a horizontal quad) the same vector gives a different stripe direction and frequency; keep the in-plane component explicit.
- D4 metres: pane 0.8 m, unit-scale objects. Wavy Gabor 12/m with frequency 5 (period ~2.1 cm along X); Blobby Voronoi 10/m, roughness noise 20/m; Frosted noise 20/m; bump distances 0.0007 m and 0.004 m.
- Interface descriptions were inherited from the node sockets (truncated in the UI); they can be left empty or copied from the Blender socket descriptions.
- Segment b group outputs are named "Shader"; the library contract (D2) wraps them in the MRS group with BSDF/Albedo outputs.
- Kept frame times are exact seconds in `evidence/b/index.json` (`frame_times`); file names use the whole second.
