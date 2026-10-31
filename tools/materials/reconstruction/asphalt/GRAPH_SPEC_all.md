# Asphalt reconstruction - graph specification (segment `all`, 00:00-27:08)

Source: *Procedural Asphalt Material (Blender Tutorial)*, Ryan King Art, 2022-06-30, 27:08 (`Eofg9SBcdBY`). Blender seen in the video: **3.2.0** (status bar, A). Machine-readable twin: `tools/materials/reconstruction/asphalt/GRAPH_SPEC_all.json`; evidence index: `tools/materials/reconstruction/asphalt/evidence/all/index.json`; operation log: `tools/materials/reconstruction/asphalt/OPERATION_LOG_all.md`; open items: `tools/materials/reconstruction/asphalt/UNRESOLVED_all.md`.

Evidence classes: **A** observed in a frame, **B** narration / recipe repo only, **C** our inference, **D** unresolved. Every value below was read from a frame unless marked otherwise; the final topology was verified on the zoomed-out overview at 26:32 (`tools/materials/reconstruction/asphalt/evidence/all/frames/t2632_final_graph_overview.jpg`).

## 1. Scene setup

| item | value | class | evidence |
|---|---|---|---|
| render engine | Cycles, Feature Set Supported, Device GPU Compute | A | 00:03, 01:08 |
| samples | viewport 10 ('Sample 9/10'); final render samples not shown | A / D | 18:11, 25:39 |
| other render toggles | Motion Blur on, Simplify off, Freestyle off (irrelevant for a still) | A | 00:03 |
| colour management | panel collapsed (3.2 default Filmic assumed) | D | 00:03 |
| film | rendered viewport shows a checkerboard (transparent film); F12 result shows black around the sphere | C | 21:24, 26:38 |
| resolution | square (1:1); pixel size not shown | A / D | 26:38 |
| geometry | object `Icosphere` (mesh `Icosphere`), 'subdivided so that it's very nice and smooth'; scene stats Verts 10,327 / Faces 20,545 / Tris 20,610, 4 objects -> Subdivisions 6 (C); radius 1 m assumed (C) | A / B / C | 00:38-00:47, status bar |
| camera | added and aimed at the sphere; sphere fills ~95 % of the square frame; focal length / transform not shown | A / D | 00:48, 26:38 |
| key light | object `Lighting` (mesh `Plane`), material `Material`: Emission white, **Strength 100**; seen as a bright ellipse | A | 01:08 |
| rim light | object `Lighting.001` (mesh `Plane.001`), material `Material.001`: Emission white, **Strength 5**; long strip behind the sphere | A | 00:58 |
| world | `World.001`: Background <- Environment Texture `machine_shop_02_1k.hdr`, Linear, Equirectangular, Single Image, Vector Default, **Strength 1.0** | A | 01:20 |
| texture coordinates | Texture Coordinate **Object** (Object field empty) for every texture; the Mapping node from Ctrl+T was deleted; no UV, no Generated | A | 02:34-02:42, 26:32 |
| displacement | none: Material Output Displacement unlinked; relief = 4 chained Bump nodes into Principled Normal; material Settings panel never shown | A / D | 26:32 |
| add-on | Node Wrangler (Ctrl+Shift+click preview, Ctrl+T, Ctrl+0 merge-mix) | A | 01:48 |
| viewport | Ctrl+B render region for close-ups (24:46), reset at 25:16 - viewport only | A | 25:10 |

Library substitutions (not part of the video): the HDRI is replaced by a bundled studio-light HDRI (DECISIONS D6); lighting differences are reported separately.

## 2. Material `Asphalt` - node inventory

No node group is created in the video; everything is top level. 28 shader nodes + 4 reroutes + 3 frames. Node types are the Blender 3.2 idnames seen in the video; the `build_5x` entries in the JSON give the Blender 5.2 equivalents (see section 7).

| id | node (header) | type | frame | settings | input values (unlinked) | class | evidence |
|---|---|---|---|---|---|---|---|
| `texcoord` | Texture Coordinate | `ShaderNodeTexCoord` | - | from_instancer=False | - | A | 02:22-02:28 added by Ctrl+T; 02:40; 26:32 |
| `rr_color` | (reroute) | `NodeReroute` | frame_color | - | - | A | 08:41-08:56; 26:32 |
| `rr_cracks` | (reroute) | `NodeReroute` | frame_cracks | - | - | A | 08:58-09:06; 26:32 |
| `rr_damage` | (reroute) | `NodeReroute` | frame_damage | - | - | A | 12:18-12:27; 14:12; 26:32 |
| `rr_bump` | (reroute) | `NodeReroute` | - | - | - | A | 19:05-19:15; 26:32 |
| `color_noise` | Noise Texture | `ShaderNodeTexNoise` | frame_color | noise_dimensions=3D | Scale 18.0, Detail 15.0, Roughness 0.6, Distortion 0.0 | A | 03:22-03:49; 26:32 |
| `color_warp_mix` | Linear Light (header shows blend name) | `ShaderNodeMixRGB` | frame_color | blend_type=LINEAR_LIGHT, use_clamp=False, use_alpha=False | Fac 0.1 | A | 03:55-04:49; 26:32 |
| `color_voronoi` | Voronoi Texture | `ShaderNodeTexVoronoi` | frame_color | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=MINKOWSKI | Scale 10.0, Smoothness 1.0, Exponent 32.0, Randomness 1.0 | A | 02:48-03:10; 05:06-05:12 Scale 10; 26:32 |
| `color_ramp` | ColorRamp | `ShaderNodeValToRGB` | frame_color | color_mode=RGB, interpolation=LINEAR, stops: #1A1817 @ 0.0; #4D4D4D @ 1.0 | - | A | 05:25-06:30; 26:32 |
| `cracks_mask_noise` | Noise Texture | `ShaderNodeTexNoise` | frame_cracks | noise_dimensions=3D | Scale 4.5, Detail 15.0, Roughness 0.5, Distortion 0.0 | A | 08:29-08:41 duplicate; 10:20-10:28 Scale 4.5; 26:32 |
| `cracks_mask_ramp` | ColorRamp | `ShaderNodeValToRGB` | frame_cracks | color_mode=RGB, interpolation=LINEAR, stops: #000000 @ 0.499; #FFFFFF @ 1.0 | - | A | 09:18-09:33; 26:32 |
| `cracks_warp_noise` | Noise Texture | `ShaderNodeTexNoise` | frame_cracks | noise_dimensions=3D | Scale 2.5, Detail 15.0, Roughness 0.5, Distortion 0.0 | A | 07:46-08:09; 26:32 |
| `cracks_voronoi` | Voronoi Texture | `ShaderNodeTexVoronoi` | frame_cracks | voronoi_dimensions=3D, feature=DISTANCE_TO_EDGE, distance=EUCLIDEAN | Scale 5.0, Randomness 1.0 | A | 07:15-07:34; 26:32 |
| `cracks_mix` | Mix | `ShaderNodeMixRGB` | frame_cracks | blend_type=MIX, use_clamp=False, use_alpha=False | Color2 #FFFFFF | A | 09:41-10:06; 10:05 'Hex: FFFFFF'; 26:32 |
| `damage_warp_noise` | Noise Texture | `ShaderNodeTexNoise` | frame_damage | noise_dimensions=3D | Scale 20.0, Detail 15.0, Roughness 0.6, Distortion 0.0 | A | 11:53-12:59; 26:32 |
| `damage_warp_mix` | Linear Light | `ShaderNodeMixRGB` | frame_damage | blend_type=LINEAR_LIGHT, use_clamp=False, use_alpha=False | Fac 0.02 | A | 12:06-13:30; 26:32 |
| `damage_voronoi` | Voronoi Texture | `ShaderNodeTexVoronoi` | frame_damage | voronoi_dimensions=4D, feature=DISTANCE_TO_EDGE, distance=EUCLIDEAN | W 0.0, Scale 110.0, Randomness 1.0 | A | 10:58-11:38; 26:32 |
| `damage_mask_noise` | Noise Texture | `ShaderNodeTexNoise` | frame_damage | noise_dimensions=3D | Scale 3.5, Detail 15.0, Roughness 0.5, Distortion 0.0 | A | 13:45-14:12 (Ctrl+Shift+D keeps the input wire); 26:32 |
| `damage_mask_ramp` | ColorRamp | `ShaderNodeValToRGB` | frame_damage | color_mode=RGB, interpolation=LINEAR, stops: #000000 @ 0.35; #FFFFFF @ 0.442 | - | A | 14:17-14:57; 26:32 |
| `damage_lighten` | Lighten | `ShaderNodeMixRGB` | frame_damage | blend_type=LIGHTEN, use_clamp=False, use_alpha=False | Fac 1.0 | A | 15:05-15:30; 26:32 |
| `darken_cracks` | Darken | `ShaderNodeMixRGB` | - | blend_type=DARKEN, use_clamp=False, use_alpha=False | Fac 1.0 | A | 16:11-16:47; 26:32 |
| `damage_dark_ramp` | ColorRamp | `ShaderNodeValToRGB` | - | color_mode=RGB, interpolation=LINEAR, stops: #000000 @ 0.338; #FFFFFF @ 1.0 | - | A | 17:52-18:11; 26:32 |
| `darken_damage` | Darken | `ShaderNodeMixRGB` | - | blend_type=DARKEN, use_clamp=False, use_alpha=False | Fac 1.0 | A | 17:15-17:29; 18:22; 26:32 |
| `bump_noise` | Noise Texture | `ShaderNodeTexNoise` | - | noise_dimensions=3D | Scale 60.0, Detail 15.0, Roughness 0.4, Distortion 0.0 | A | 18:42-19:46; 26:32 |
| `bump1` | Bump | `ShaderNodeBump` | - | invert=False | Strength 0.1, Distance 1.0 | A | 20:20-20:44; 26:32 |
| `bump2` | Bump | `ShaderNodeBump` | - | invert=False | Strength 0.2, Distance 1.0 | A | 20:58-21:40; 26:32 |
| `crack_bump_ramp` | ColorRamp | `ShaderNodeValToRGB` | - | color_mode=RGB, interpolation=LINEAR, stops: #000000 @ 0.0; #FFFFFF @ 0.094 | - | A | 22:45-23:28; 26:32 |
| `bump3` | Bump | `ShaderNodeBump` | - | invert=False | Strength 0.3, Distance 1.0 | A | 21:52-22:20; 26:32 |
| `bump4` | Bump | `ShaderNodeBump` | - | invert=False | Strength 0.4, Distance 1.0 | A | 24:04-24:40; 26:32 |
| `rough_ramp` | ColorRamp | `ShaderNodeValToRGB` | - | color_mode=RGB, interpolation=LINEAR, stops: #ABABAB @ 0.0; #FFFFFF @ 1.0 | - | A | 25:47-26:29; 26:32 |
| `principled` | Principled BSDF | `ShaderNodeBsdfPrincipled` | - | distribution=GGX, subsurface_method=RANDOM_WALK | Subsurface 0.0, Subsurface Radius default (1.0, 0.2, 0.1) - collapsed, not read (C), Subsurface Color default (0.8, 0.8, 0.8) - swatch only (C), Subsurface IOR 1.4, Subsurface Anisotropy 0.0, Metallic 0.0, Specular 0.5, Specular Tint 0.0, Anisotropic 0.0, Anisotropic Rotation 0.0, Sheen 0.0, Sheen Tint 0.5, Clearcoat 0.0, Clearcoat Roughness 0.03, IOR 1.45, Transmission 0.0, Transmission Roughness 0.0, Emission [0.0, 0.0, 0.0, 1.0], Emission Strength 1.0, Alpha 1.0 | A | 06:43; 18:22; 26:32 |
| `output` | Material Output | `ShaderNodeOutputMaterial` | - | target=ALL | - | A | 01:57; 26:32 |
| `frame_color` | frame 'Color' | `NodeFrame` | - | label 'Color'; members: rr_color, color_noise, color_warp_mix, color_voronoi, color_ramp | - | A | 06:46-07:05 Ctrl+J, F2; 26:32 |
| `frame_cracks` | frame 'Cracks' | `NodeFrame` | - | label 'Cracks'; members: rr_cracks, cracks_mask_noise, cracks_mask_ramp, cracks_warp_noise, cracks_voronoi, cracks_mix | - | A | 10:34-10:51; 26:32 |
| `frame_damage` | frame 'Damage' | `NodeFrame` | - | label 'Damage'; members: rr_damage, damage_warp_noise, damage_warp_mix, damage_voronoi, damage_mask_noise, damage_mask_ramp, damage_lighten | - | A | 15:41-15:56; 26:32 |

Notes per node:

- `texcoord`: Object output feeds every texture (via 4 reroutes); Object field empty = the material's own object; the Mapping node Ctrl+T added was deleted at 02:34
- `rr_color`: layout only: merges Object->Noise Vector and Object->Linear Light Color1
- `rr_cracks`: layout only: merges the two cracks noise Vector wires
- `rr_damage`: layout only: feeds damage warp noise, Linear Light Color1 and the damage mask noise
- `rr_bump`: layout only: long wire down to the bump noise
- `color_warp_mix`: use_alpha is not visible in 3.2 (sidebar option); default False assumed (C). Result = Object + 0.1*(2*NoiseColor-1): a +-0.1 domain warp that does not slide the pattern
- `color_voronoi`: Distance output drives three things: base colour ramp, Bump 2 Height and the roughness ramp
- `cracks_mask_ramp`: crack-amount control: 16:52-17:06 the black stop was dragged 0.231-0.548 as a demonstration, back at 0.499 by 17:08
- `cracks_warp_noise`: its Color goes DIRECTLY into the cracks Voronoi Vector (no mix): the Voronoi is evaluated in noise-colour space
- `cracks_voronoi`: distance metric is hidden for Distance to Edge and never changed (EUCLIDEAN default, C)
- `cracks_mix`: white where the mask ramp is white = cracks removed there
- `damage_warp_noise`: its scalar Fac (not Color) feeds Linear Light Color2: the warp offset is equal on X, Y and Z
- `damage_voronoi`: pebbles / chunks under the asphalt; 4D with W = 0 (a 3D slice of 4D Voronoi, different cells than 3D)
- `damage_mask_ramp`: damage-amount control (14:43-14:52 narration): stops far apart = more damage
- `damage_lighten`: = max(pebbles, mask): pebbles only survive where the mask is black
- `damage_dark_ramp`: darkens the damaged patches before they enter Darken #2
- `bump2`: Height comes from the BASE (Color-frame, Smooth F1) Voronoi, not from the pebble Voronoi as the recipe repo says (see UNRESOLVED U16)
- `crack_bump_ramp`: flattens everything except the thin crack lines; white stop tried 0.899 -> 0.109 -> 0.042 -> 0.057 -> 0.083 -> 0.094 (final)
- `rough_ramp`: linear roughness 0.407 (cell edges) to 1.0 (cell centres)

## 3. Connections (final graph)

All 42 links below are present in the 26:32 overview (confidence high unless noted). Collapsed without reroutes the graph has 38 links (`links_collapsed_without_reroutes` in the JSON).

| # | source node | output socket | destination node | input socket | timestamp (creation) | class | confidence | note |
|---|---|---|---|---|---|---|---|---|
| 1 | `texcoord` | Object | `rr_color` | Input | 08:41-08:56 | A | high |  |
| 2 | `rr_color` | Output | `color_noise` | Vector | 03:22-03:31 (via reroute since 08:56) | A | high |  |
| 3 | `rr_color` | Output | `color_warp_mix` | Color1 | 04:04-04:10 (via reroute since 08:56) | A | high |  |
| 4 | `color_noise` | Color | `color_warp_mix` | Color2 | 04:10-04:15 | A | high |  |
| 5 | `color_warp_mix` | Color | `color_voronoi` | Vector | 03:55-04:04 (mix dropped on the Noise->Voronoi wire) | A | high |  |
| 6 | `color_voronoi` | Distance | `color_ramp` | Fac | 05:30-05:38 | A | high |  |
| 7 | `color_voronoi` | Distance | `bump2` | Height | 21:18-21:30 | A | high | repo says pebble Voronoi; frames show the Color-frame Voronoi (U16) |
| 8 | `color_voronoi` | Distance | `rough_ramp` | Fac | 25:26-25:39 (to Roughness), ramp inserted 25:47-25:55 | A | high |  |
| 9 | `color_ramp` | Color | `darken_cracks` | Color1 | 16:37-16:41 | A | high |  |
| 10 | `texcoord` | Object | `rr_cracks` | Input | 08:58-09:06 | A | high |  |
| 11 | `rr_cracks` | Output | `cracks_mask_noise` | Vector | 08:37-08:41 (via reroute since 09:04) | A | high |  |
| 12 | `rr_cracks` | Output | `cracks_warp_noise` | Vector | 07:46-07:52 (via reroute since 09:04) | A | high |  |
| 13 | `cracks_mask_noise` | Fac | `cracks_mask_ramp` | Fac | 09:18-09:26 | A | high | Fac, not Color (crop c_t0938_mask_noise_fac_to_ramp) |
| 14 | `cracks_warp_noise` | Color | `cracks_voronoi` | Vector | 07:52-07:58 | A | high |  |
| 15 | `cracks_mask_ramp` | Color | `cracks_mix` | Fac | 09:54-09:58 | A | high |  |
| 16 | `cracks_voronoi` | Distance | `cracks_mix` | Color1 | 09:58-10:02 | A | high |  |
| 17 | `cracks_mix` | Color | `darken_cracks` | Color2 | 16:41-16:45 | A | high |  |
| 18 | `cracks_mix` | Color | `crack_bump_ramp` | Fac | 22:06-22:12 (to Bump 3 Height), ramp inserted 22:45-22:57 | A | high |  |
| 19 | `texcoord` | Object | `rr_damage` | Input | 12:18-12:27 | A | high |  |
| 20 | `rr_damage` | Output | `damage_warp_noise` | Vector | 11:53-12:04 (via reroute since 12:27) | A | high |  |
| 21 | `rr_damage` | Output | `damage_warp_mix` | Color1 | 12:28-12:33 | A | high |  |
| 22 | `rr_damage` | Output | `damage_mask_noise` | Vector | 13:45-13:52 (Ctrl+Shift+D keeps the input wire) | A | high |  |
| 23 | `damage_warp_noise` | Fac | `damage_warp_mix` | Color2 | 12:33-12:38 | A | high | Fac, not Color (crop c_t1330_damage_noise_fac_to_color2) |
| 24 | `damage_warp_mix` | Color | `damage_voronoi` | Vector | 12:06-12:17 (mix dropped on the Noise->Voronoi wire) | A | high |  |
| 25 | `damage_mask_noise` | Fac | `damage_mask_ramp` | Fac | 14:17-14:24 | A | high |  |
| 26 | `damage_voronoi` | Distance | `damage_lighten` | Color1 | 15:23-15:26 | A | high |  |
| 27 | `damage_mask_ramp` | Color | `damage_lighten` | Color2 | 15:25-15:28 | A | high |  |
| 28 | `damage_lighten` | Color | `damage_dark_ramp` | Fac | 17:23-17:27 (to Darken #2 Color2), ramp inserted 17:52-18:00 | A | high |  |
| 29 | `damage_lighten` | Color | `bump4` | Height | 24:18-24:27 | A | high |  |
| 30 | `darken_cracks` | Color | `darken_damage` | Color1 | 17:27-17:29 | A | high |  |
| 31 | `damage_dark_ramp` | Color | `darken_damage` | Color2 | 17:52-18:00 | A | high |  |
| 32 | `darken_damage` | Color | `principled` | Base Color | 18:17-18:24 | A | high |  |
| 33 | `texcoord` | Object | `rr_bump` | Input | 19:05-19:15 | A | high |  |
| 34 | `rr_bump` | Output | `bump_noise` | Vector | 18:55-19:02 (via reroute since 19:15) | A | high |  |
| 35 | `bump_noise` | Fac | `bump1` | Height | 20:20-20:33 | A | high |  |
| 36 | `bump1` | Normal | `bump2` | Normal | 20:58-21:10 | A | high |  |
| 37 | `bump2` | Normal | `bump3` | Normal | 21:52-21:58 | A | high |  |
| 38 | `crack_bump_ramp` | Color | `bump3` | Height | 22:45-22:57 | A | high |  |
| 39 | `bump3` | Normal | `bump4` | Normal | 24:04-24:12 | A | high |  |
| 40 | `bump4` | Normal | `principled` | Normal | 24:04-24:12 (end of the chain; Bump 1 -> Normal since 20:33) | A | high |  |
| 41 | `rough_ramp` | Color | `principled` | Roughness | 25:47-25:55 | A | high |  |
| 42 | `principled` | BSDF | `output` | Surface | 01:57 (default material) | A | high |  |

## 4. Colour ramp stops

All ramps: Color Mode RGB, Interpolation Linear (A). Hex values are Blender's gamma-corrected sRGB; linear values are what the ramp stores.

| ramp | stop | position | colour (hex sRGB) | linear RGB | class | evidence |
|---|---|---|---|---|---|---|
| `color_ramp` | 0 | 0.0 | #1A1817 | (0.0103, 0.0091, 0.0086) | A | 06:12 caption 'Hex: 1A1817' |
| `color_ramp` | 1 | 1.0 | #4D4D4D | (0.0742, 0.0742, 0.0742) | A | 06:28 caption 'Hex: 4D4D4D'; 26:32 'Pos 1.000' |
| `cracks_mask_ramp` | 0 | 0.499 | #000000 | (0.0000, 0.0000, 0.0000) | A | 09:38 'Pos 0.499'; 17:08 restored; 26:32 |
| `cracks_mask_ramp` | 1 | 1.0 | #FFFFFF | (1.0000, 1.0000, 1.0000) | A | 26:32 marker at the right end (default stop) |
| `damage_mask_ramp` | 0 | 0.35 | #000000 | (0.0000, 0.0000, 0.0000) | C | 14:56.5 last legible 'Pos 0.343' (A) before a jump cut at ~14:57.1; after the cut the bar measures 0.350 +-0.005 (14:57.4, 26:32) - final value not legible: 0.343 (A, pre-cut) vs 0.350 measured; spec uses 0.35, see UNRESOLVED U1 |
| `damage_mask_ramp` | 1 | 0.442 | #FFFFFF | (1.0000, 1.0000, 1.0000) | A | 14:57.4 'Pos 0.442'; 26:32 'Pos 0.442' |
| `damage_dark_ramp` | 0 | 0.338 | #000000 | (0.0000, 0.0000, 0.0000) | A | 18:11 'Pos 0.338'; 26:32 'Pos 0.338' |
| `damage_dark_ramp` | 1 | 1.0 | #FFFFFF | (1.0000, 1.0000, 1.0000) | A | 26:32 marker at the right end (default stop) |
| `crack_bump_ramp` | 0 | 0.0 | #000000 | (0.0000, 0.0000, 0.0000) | A | 26:32 marker at the left end (default stop, never moved) |
| `crack_bump_ramp` | 1 | 0.094 | #FFFFFF | (1.0000, 1.0000, 1.0000) | A | 23:27 'Pos 0.094'; 24:22; 26:32 'Pos 0.094' |
| `rough_ramp` | 0 | 0.0 | #ABABAB | (0.4072, 0.4072, 0.4072) | A | 26:00 'Pos 0.000'; 26:22 caption 'Hex: ABABAB' |
| `rough_ramp` | 1 | 1.0 | #FFFFFF | (1.0000, 1.0000, 1.0000) | A | 26:28 'Pos 1.000' picker 'Hex: FFFFFF' |

## 5. Group interface

The video creates **no group and exposes no controls** (A: no Ctrl+G, no group sockets in any frame). The table lists the controls the narration explicitly tunes, as candidates for the library group `PM_Asphalt` (all class C; the values are the video's).

| control | socket type | default | min / max | internal destination | visible effect | evidence |
|---|---|---|---|---|---|---|
| Crack Amount | NodeSocketFloat | 0.499 | 0.0 / 1.0 | cracks_mask_ramp element 0 position | higher = more crack regions (noise below the black stop keeps its cracks; demo 0.231-0.548 at 17:00-17:06) | 16:52-17:08 narration (B) + demo frames (A) |
| Crack Width | NodeSocketFloat | 0.094 | 0.0 / 1.0 | crack_bump_ramp element 1 position | lower = thinner recessed crack lines (tried 0.042-0.109) | 22:59-23:30 (A values, B effect) |
| Damage Amount | NodeSocketFloat | 0.35 | 0.0 / 1.0 | damage_mask_ramp element 0 (0.35) and element 1 (0.442) positions, keep the 0.092 gap | stops further right = more/larger damaged patches | 14:43-14:52 narration (B) |
| Damage Darkness | NodeSocketFloat | 0.338 | 0.0 / 1.0 | damage_dark_ramp element 0 position | higher = darker damaged patches | 18:02-18:11 |
| Roughness Min | NodeSocketFloat | 0.407 | 0.0 / 1.0 | rough_ramp element 0 colour (linear grey; ABABAB sRGB = 0.407 linear) | lower = shinier / wet look | 25:57-26:22 narration (B), value A |
| Color Dark | NodeSocketColor | 1A1817 sRGB (0.0103, 0.0091, 0.0086) | - | color_ramp element 0 colour | asphalt dark tone | 06:12 (A value) |
| Color Light | NodeSocketColor | 4D4D4D sRGB (0.0742) | - | color_ramp element 1 colour | asphalt light tone | 06:28 (A value) |
| Bump Strength (x4) | NodeSocketFloat | 0.1 / 0.2 / 0.3 / 0.4 | 0.0 / 1.0 | bump1..bump4 Strength | grain / cell undulation / crack depth / damage relief | 20:44, 21:40, 22:20, 24:40 (A values) |
| Aggregate Size (m) | NodeSocketFloat | derived: scales 18/10/2.5/4.5/5/20/110/3.5/60 on a ~1 m-radius object | - | all texture Scale inputs (common factor), per DECISIONS D4 | texel scale in metres | library contract (not in video) |
| Use UV / Tile Size | NodeSocketFloat | 0 / builder | - | coordinate source (Object vs UV torus), per DECISIONS D2 | library contract | DECISIONS D2 (not in video) |

## 6. Final graph diagram

```
Texture Coordinate.Object
 |-[rr_color]-> Noise(3D 18/15/0.6/0).Vector --Color--> LinearLight(Fac 0.1).Color2
 |            `-------------------------------------> LinearLight.Color1
 |   LinearLight.Color -> Voronoi(3D Smooth F1 Minkowski, Scale 10, Smooth 1, Exp 32, Rand 1).Vector
 |   Voronoi.Distance --+--> Ramp[#1A1817@0 -> #4D4D4D@1] -------------------------> Darken#1.Color1
 |                      +--> Bump#2.Height
 |                      `--> Ramp[#ABABAB@0 -> #FFFFFF@1] -------------------------> Principled.Roughness
 |-[rr_cracks]-> Noise(4.5/15/0.5/0).Fac -> Ramp[black@0.499 -> white@1].Color --> Mix(MIX).Fac
 |            `-> Noise(2.5/15/0.5/0).Color -> Voronoi(3D Distance to Edge, Scale 5).Vector
 |   Voronoi(DtE).Distance -> Mix.Color1 ;  Mix.Color2 = white
 |   Mix.Color --+--> Darken#1.Color2
 |               `--> Ramp[black@0 -> white@0.094] -> Bump#3.Height
 |-[rr_damage]-> Noise(20/15/0.6/0).Fac -> LinearLight(Fac 0.02).Color2
 |            |-> LinearLight(0.02).Color1
 |            `-> Noise(3.5/15/0.5/0).Fac -> Ramp[black@~0.35 -> white@0.442] -> Lighten(Fac 1).Color2
 |   LinearLight(0.02).Color -> Voronoi(4D Distance to Edge, W 0, Scale 110, Rand 1).Vector
 |   Voronoi(4D).Distance -> Lighten.Color1
 |   Lighten.Color --+--> Ramp[black@0.338 -> white@1] -> Darken#2.Color2
 |                   `--> Bump#4.Height
 |   Darken#1(Fac 1).Color -> Darken#2(Fac 1).Color1 ;  Darken#2.Color -> Principled.Base Color
 `-[rr_bump]-> Noise(60/15/0.4/0).Fac -> Bump#1(Strength 0.1, Dist 1).Height
     Bump#1.Normal -> Bump#2(0.2).Normal -> Bump#3(0.3).Normal -> Bump#4(0.4).Normal -> Principled.Normal
     Principled BSDF (GGX, Random Walk, 3.2 defaults otherwise).BSDF -> Material Output.Surface   (Displacement unlinked)
```

Frames (layout only): **Color** = rr_color, Noise 18, Linear Light 0.1, Voronoi Smooth F1, base ramp; **Cracks** = rr_cracks, two noises, mask ramp, Distance-to-Edge Voronoi, Mix; **Damage** = rr_damage, two noises, Linear Light 0.02, 4D Voronoi, mask ramp, Lighten. Everything else is outside the frames.

## 7. Building it in Blender 5.2 (version mapping)

| 3.2 in the video | 5.2 build | class |
|---|---|---|
| `ShaderNodeMixRGB` (Linear Light / Mix / Lighten / Darken, Clamp off) | `ShaderNodeMix`, `data_type='RGBA'`, same `blend_type`, `clamp_result=False`, `clamp_factor=True`; Fac -> inputs[0], Color1 -> inputs[6] (A), Color2 -> inputs[7] (B), Color -> outputs[2] | C |
| Bump Distance 1.0 (3.2 default) | 5.2 creates Bump with **Distance 0.001**: set **1.0** explicitly; new `Filter Width` input (0.1 default) has no 3.2 equivalent - compare 0.1 vs 1.0 (U13) | A value / C |
| Noise (3.2 fBm) | `noise_type='FBM'`, `normalize=True`, Lacunarity 2 (defaults) | C |
| Voronoi (3.2 single octave) | Detail 0, `normalize=False` (defaults) | C |
| Principled: GGX, Specular 0.5, IOR 1.45 | `distribution='GGX'` (5.x default is MULTI_GGX), IOR 1.5, Specular IOR Level 0.5 (same F0 0.04), other weights 0 | C |
| ramp `Fac` input / Noise `Fac` output | named `Factor` in 5.x, identifier still `Fac` - look sockets up by identifier | A (API probe) |
| hex colours | convert sRGB hex to linear before writing `color_ramp.elements[i].color` (values in section 4) | C |
| 4D Voronoi with W = 0 | already 4D; a torus (seamless) mode that needs W must keep the W=0 slice look (DECISIONS D5) | C |

Value semantics (C): Linear Light = A + Fac*(2B-1), so the Object coordinates are offset by +-0.1 (colour) and +-0.02 (pebbles, equal on X/Y/Z because a scalar Fac feeds B) without sliding; Darken/Lighten with Fac 1 are per-channel min/max. Texture scales are in the icosphere's object space (radius ~1 m assumed): base cells ~0.1 m, pebble cells ~9 mm, bump grain Scale 60.

## 8. Recipe repository cross-check (`tmp/materials_video/apprentice/asphalt_material*.txt/.py`)

| item | repo | frame | verdict |
|---|---|---|---|
| Base ColorRamp stop 0 | #1A1A1A (procedure + program) | Hex 1A1817 (06:12 caption) | CONFLICT - frame wins (U15) |
| Base ColorRamp stop 1 | #4D4D4D | Hex 4D4D4D (06:28) | agree |
| Colour Noise | 18 / 15 / 0.6 / 0 | 18 / 15 / 0.6 / 0 | agree |
| Colour warp MixRGB | Linear Light 0.10, Object->Color1, Noise Color->Color2 | same | agree |
| Base Voronoi | Smooth F1, Minkowski, Smoothness 1, Exponent 32, Scale 10 | same (+ Randomness 1, 3D) | agree |
| Cracks warp Noise | 2.5 / 15 / 0.5 / 0, Color->Voronoi Vector | same | agree |
| Cracks Voronoi | Distance to Edge (scale not given) | Distance to Edge, Scale 5, Randomness 1 | agree (repo default) |
| Cracks mask Noise | 4.5 / 15 / 0.5 / 0, Fac->ramp | same | agree |
| Cracks mask ramp | 'black stop toward the centre' (no number); per-frame notes ~0.48-0.49 | black 0.499 (09:38, 26:32) | frame gives the number |
| Cracks Mix | Fac=mask ramp, Color1=Voronoi, Color2=white | same, blend Mix, Clamp off | agree |
| Pebble warp | Noise 20/15/0.6/0, Fac->Color2, Linear Light 0.02 | same | agree |
| Pebble Voronoi | Distance to Edge, 4D, Scale 110, Randomness 1 | same, W 0 | agree |
| Damage mask Noise | 3.5 / 15 / 0.5 / 0 | same | agree |
| Damage mask ramp | 'stops close together' (no number); per-frame notes 0.27-0.31 / 0.37-0.42 (OCR) | black 0.343 legible pre-cut (~0.35 after), white 0.442 | frame gives the numbers (U1) |
| Lighten | Fac 1, Color1 = pebbles, Color2 = mask ramp | same | agree |
| Darken #1 / #2 | Fac 1; base ramp + cracks mix; combined + damage-dark ramp | same | agree |
| Damage dark ramp | 'black stop to the right' (no number) | black 0.338 (18:11, 26:32) | frame gives the number |
| Bump noise | 60 / 15 / 0.4 / 0 | same | agree |
| Bump 1 | Strength 0.10 | Strength 0.1, Distance 1.0 | agree (repo omits Distance) |
| Bump 2 Height | Voronoi('pebbles') Distance | Color-frame (base, Smooth F1) Voronoi Distance (21:22-21:28, 26:32) | CONFLICT - frame wins (U16) |
| Bump 3 | ramp(cracks mix) -> Height, 0.30 | same; white stop 0.094 | agree |
| Bump 4 | Damage Lighten -> Height, 0.40 -> Normal | same | agree |
| Roughness ramp | #ABABAB -> #FFFFFF, base Voronoi Distance | ABABAB (26:22) -> FFFFFF (26:28), base Voronoi Distance | agree |

## 9. Reference frames of the finished look

| t | frame | what |
|---|---|---|
| 00:03.5 | `tools/materials/reconstruction/asphalt/evidence/all/frames/t0003_intro_final_render.jpg` | intro overlay of the finished render: camera view, whole sphere, Cycles, key emitter 100 + rim strip 5 + machine_shop_02_1k HDRI, black background |
| 26:38.5 | `tools/materials/reconstruction/asphalt/evidence/all/frames/t2638_final_render.jpg` | F12 Render Result of the finished material, same camera and lighting, square image |
| 25:10.5 | `tools/materials/reconstruction/asphalt/evidence/all/frames/t2510_viewport_closeup_reference.jpg` | Cycles viewport close-up (render region, 10 samples) of a damaged patch with pebbles, recessed edges and cracks; roughness ramp not yet connected (constant 0.5) |
| 26:32.5 | `tools/materials/reconstruction/asphalt/evidence/all/frames/t2632_final_graph_overview.jpg` | final node graph fully visible + camera-view viewport of the final material (render region) |

Final look (A, 26:38): a dark warm-grey asphalt/concrete sphere; soft cellular mottling from the Smooth-F1 Minkowski cells; sparse networks of thin black recessed cracks (about half the surface masked out); large irregular very dark damaged patches with fine pebble relief and raised broken edges; fine grain over everything; rough, slightly glossy highlights from the strong key emitter, a thin rim on the right edge, black background.
