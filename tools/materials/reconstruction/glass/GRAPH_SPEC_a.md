# Glass video, segment a: node-graph specification

Source: `SNKNqHd0AYI` *Procedural Textured Frosted Glass Materials (Blender Tutorial)*, Ryan King Art, 2026-05-12, 34:03
(`tmp/materials_video/SNKNqHd0AYI.webm`, 2560x1440, 60 fps). Segment **a = 00:00-22:32**: the overview of the six product
groups (0:40-2:42), the scene setup (3:14-6:10) and the three materials built in this part of the tutorial:
**Textured Glass Circles** (6:10), **Textured Glass Voronoi** (10:55) and **Textured Glass Cells** (17:52). The
kitchen-course ad 16:43-17:52 is skipped. Machine-readable twin: `GRAPH_SPEC_a.json`; evidence:
`evidence/a/index.json` (123 events, 16 frames, 98 crops).

Blender in the video: **5.1.1** (status bar, class A, `evidence/a/crops/t0506_blender_version.png`).

Classes: **A** seen in a frame, **B** narration / recipe repo only, **C** our inference, **D** unresolved.
Times are true video times `mm:ss.s`. (The 1 fps survey frames showed time N+0.5 s; every time below is corrected,
and evidence frames were extracted with `ffmpeg -ss <t>` at exactly the listed time.)

The recipe repository has no entry for this video; nothing here comes from it.

Paths below are relative to `tools/materials/reconstruction/glass/`.

---

## 1. Scene setup (3:14-6:10)

| item | value | class | evidence |
|---|---|---|---|
| panes | 6 x Plane (Shift+A > Mesh > Plane, 2 m) `S .4` + `R X 90` + Ctrl+A Apply Rotation & Scale -> **0.8 m x 0.8 m vertical panes** (normal -Y, object scale 1), no subdivision, no modifiers | A (keys) / B (option name) | `evidence/a/frames/t0334_setup_apply_object_transform.jpg`, crops `t0326_keys_S_0p4`, `t0329_keys_R_X_90`, `t0330_keys_ctrlA_apply_menu` |
| layout | 2 rows x 3 columns; Shift+D readouts 0.88-0.90 m (X), -1.76 m (X), -0.87 m (Z): columns at x ~ -0.86 / 0 / +0.89, rows 0.87 m apart, then all raised (amount not shown) | C (live drag readouts) | `t0336_header_dup_dx`, `t0338_header_dup_dx2`, `t0341_header_dup_dz`, frame `t0342_setup_six_panes_grid` |
| backdrop | 4 Suzannes (scaled down, scale applied) behind the panes (+Y); size/position not readable | A / D | 3:50-4:03 |
| scene counts | Verts 2,052 / Faces 2,006 / Tris 3,884 (6 planes + 4 Suzannes); Objects 10 before the camera, 11 after: **no lamp** | A | status bar (e.g. 4:18) |
| monkey material | "red": Principled BSDF, Base Color Perceptual HSV (0.009, 1.000, 0.956) = **#F40D00** (linear ~0.905, 0.004, 0); rest default | A | crops `t0417_red_picker_drag`, `t0418_red_picker_final` |
| camera | Perspective, 50 mm, Millimeters, shift 0/0, clip 0.1/1000, DoF off; placed with Ctrl+Alt+Numpad0 then G / G+MMB (transform not shown) | A / D | crop `t0446_camera_lens` |
| engine | **Cycles**, Device GPU Compute, OSL off, Motion Blur checkbox on; viewport samples 100 ("Sample n/100"); render samples never shown | A / D | frame `t0453_setup_render_cycles_gpu`, crops `t0452_render_engine_menu`, `t0453_render_device` |
| world | Background <- Environment Texture **old_apartments_walkway_1k.hdr** (Poly Haven 1K), Linear, Equirectangular, Single Image, Linear Rec.709, Premultiplied, Vector Default; **Strength 0.5** | A | frame `t0506_setup_world_hdri`, crop `t0506_world_hdri` |
| film | **Transparent on**, Exposure 1.00, Blackman-Harris 1.50 px | A | crop `t0530_film_transparent` |
| colour management | Display sRGB, **View Filmic, Look Very High Contrast**, Exposure 0, Gamma 1 | A | crops `t0534_view_transform_menu`, `t0538_color_management` |
| material settings | no material uses true displacement: Material Output Displacement is unlinked in all three; relief = Bump node only. Settings panel never shown (Blender default "Bump Only") | A / C | final graphs |
| coordinates | every texture: Texture Coordinate **Object** -> Mapping (Point, Location 0, Rotation 0, Scale <- group Scale). Scale was applied, so object space = **metres** (Voronoi Scale 50 = 50 cells/m) | A / C | all three final graphs |
| assignment | Plane.002 = Circles, Plane = Voronoi, Plane.001 = Cells; all objects in a collection "Procedural Material" | A | node-editor breadcrumbs, viewport overlay "(52) Procedural Material \| Plane.002" |
| add-on | Node Wrangler: Ctrl+T (TexCoord + Mapping), Ctrl+Shift+click previews | A / B | 6:46, narration 5:53 |

Project substitutes (DECISIONS D6): the Poly Haven HDRI is not downloaded; a bundled studiolight replaces it.

---

## 2. Textured Glass Circles (6:10-10:55)

Group `Textured Glass Circles` (one group node in the material). Final graph frame: `evidence/a/frames/t1043_circles_group_final_graph.jpg` (10:43.5).

```
Group Input ─Scale──────────────────────────────► Mapping.Scale
TexCoord.Object ─► Mapping(Point).Vector ─► Voronoi(3D, Smooth F1, Euclidean).Vector
                                            Voronoi.Distance ─► RGB Curves.Color ─► Bump(invert).Height
                                                                                     Bump.Normal ─► Glass(Multiscatter GGX).Normal
Group Input ─Voronoi Scale/Detail/Roughness/Smoothness/Randomness─► Voronoi
Group Input ─Bump Strength─► Bump.Strength
Group Input ─Glass Color / Glass Roughness / Glass IOR─► Glass.Color / Roughness / IOR
Glass.BSDF ─► Group Output.Shader          (material: Group.Shader ─► Material Output.Surface)
```

### Node inventory

| node | type | settings | input values (unlinked) | class | evidence |
|---|---|---|---|---|---|
| group_input | NodeGroupInput | 10 inputs (table below) | - | A | 10:43.5 |
| tex_coord | ShaderNodeTexCoord | object None, From Instancer off | - | A | 6:46.5, 6:56.5, 10:43.5 |
| mapping | ShaderNodeMapping | vector_type POINT | Location (0,0,0), Rotation (0,0,0); Vector, Scale linked | A | 10:43.5 |
| voronoi | ShaderNodeTexVoronoi | 3D, **Smooth F1**, Euclidean, Normalize off | Lacunarity 2.0; Scale 50, Detail 0, Roughness 0.5, Smoothness 1.0, Randomness 1.0 (all now from the group input) | A | 6:34.5, 6:40.5, 10:43.5 |
| rgb_curves | ShaderNodeRGBCurve | C curve points (0,0), **(0.3140, 0.2464)**, **(0.5804, 0.6535)**, (1,1); auto handles; R/G/B untouched | Factor 1.0 | A | 7:46.5-8:14.6, 10:43.5 |
| bump | ShaderNodeBump | **Invert on** | **Distance 0.002**, Filter Width 0.1; Strength linked | A | 7:22.5, 7:55.5, 10:43.5 |
| glass | ShaderNodeBsdfGlass | **Multiscatter GGX** | Color white, Roughness 0.2, IOR 1.5 (all now from the group input); Thin Film defaults (C) | A | 6:19.5, 8:25.5, 10:43.5 |
| group_output | NodeGroupOutput | output "Shader" | - | A | 10:43.5 |

### Connections

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 6:56.5 (NW first linked Generated at 6:46.5) | A high |
| mapping | Vector | voronoi | Vector | 6:46.5 | A high |
| voronoi | Distance | rgb_curves | **Color** (not Factor) | 7:37.5 | A high |
| rgb_curves | Color | bump | Height | 7:37.5 | A high |
| bump | Normal | glass | Normal | 7:16.5 | A high |
| glass | BSDF | group_output | Shader | 8:37.5 | A high |
| group_input | Scale | mapping | Scale | 9:07.5 | A high |
| group_input | Glass Color | glass | Color | 9:37.5 | A high |
| group_input | Glass Roughness | glass | Roughness | 9:46.5 | A high |
| group_input | Glass IOR | glass | IOR | 9:52.5 | A high |
| group_input | Voronoi Scale | voronoi | Scale | 10:10.5 | A high |
| group_input | Voronoi Detail | voronoi | Detail | 10:10.5 | A high |
| group_input | Voronoi Roughness | voronoi | Roughness | 10:10.5 | A high |
| group_input | Voronoi Smoothness | voronoi | Smoothness | 10:25.5 | A high |
| group_input | Voronoi Randomness | voronoi | Randomness | 10:25.5 | A high |
| group_input | Bump Strength | bump | Strength | 10:35.5 | A high |

### Group interface

| control | socket type | default | min / max | internal destination | visible effect | evidence |
|---|---|---|---|---|---|---|
| Shader (output) | Shader | - | - | glass.BSDF | material output (BSDF renamed Shader) | 8:52.5 A |
| Scale | Float (changed from Vector), subtype None | 1.0 | -inf / inf | mapping.Scale | larger = smaller dimples | 9:16.5, 9:22.5 A |
| Glass Color | Color | white (1,1,1,1) | - | glass.Color | tint (demo #CCEDFF at 10:52) | 9:43.5 A |
| Glass Roughness | Float Factor | 0.2 | 0 / 1 | glass.Roughness | frost | 9:49.5 A |
| Glass IOR | Float None | 1.5 | 0 / 1000 | glass.IOR | refraction | 9:55.5 A |
| Voronoi Scale | Float None | 50 | -1000 / 1000 | voronoi.Scale | dimple density | 10:16.5 A |
| Voronoi Detail | Float None | 0 | 0 / 15 (C) | voronoi.Detail | extra dimple layers | 10:13.5 A, limits C |
| Voronoi Roughness | Float Factor | 0.5 | 0 / 1 | voronoi.Roughness | detail-layer weight | 10:22.5 A |
| Voronoi Smoothness | Float Factor | 1.0 | 0 / 1 | voronoi.Smoothness | cell-edge rounding | 10:31.5 A |
| Voronoi Randomness | Float Factor | 1.0 | 0 / 1 (C) | voronoi.Randomness | grid -> random | 10:28.5 A, limits C |
| Bump Strength | Float Factor | 1.0 | 0 / 1 | bump.Strength | bump intensity | 10:39.5 A |

Group node values at the end (22:29.5, `evidence/a/crops/t2229_circles_group_node_values.png`): all equal to the defaults above.

### RGB Curves (C channel)

| point | x | y | class | evidence |
|---|---|---|---|---|
| 0 | 0.0 | 0.0 | A (endpoint untouched) | 10:43.5 |
| 1 | 0.3140 | 0.2464 | A (readout 8:14.6-10:43.5; graph pixel ~0.315/0.245) | `crops/t1043_distance_to_curves_color.png` |
| 2 | 0.5804 | 0.6535 | A (readout 8:14.0; graph pixel ~0.581/0.656) | `crops/t0814_curves_upper_point_invert.png` |
| 3 | 1.0 | 1.0 | A | 10:43.5 |

---

## 3. Textured Glass Voronoi (10:55-16:43)

Group `Textured Glass Voronoi`. Final graph frame: `evidence/a/frames/t1626_voronoi_group_final_graph.jpg` (16:26.5).

```
TexCoord.Object ─► Mapping(Point).Vector ─┬─► Voronoi 1 (3D, Smooth F1).Vector ─Distance─► RGB Curves 1.Color ─► Bump 1(invert, 0.004).Height
                                           └─► Voronoi 2 (3D, Smooth F1).Vector ─Distance─► RGB Curves 2.Color ─► Bump 2(invert, 0.00008).Height
Bump 2.Normal ─► Bump 1.Normal ;  Bump 1.Normal ─► Glass(Multiscatter GGX).Normal ;  Glass.BSDF ─► Group Output.Shader
Group Input: Scale ─► Mapping.Scale ; Glass Color/Roughness/IOR ─► Glass ;
             Voronoi Scale 1/2, Smoothness 1/2, Detail 1/2 ─► Voronoi 1/2 ; Bump Strength 1/2 ─► Bump 1/2.Strength
```

### Node inventory

| node | type | settings | input values (unlinked) | class | evidence |
|---|---|---|---|---|---|
| group_input | NodeGroupInput | 12 inputs | - | A | 16:26.5 |
| tex_coord | ShaderNodeTexCoord | - | - | A | 11:16.5, 16:26.5 |
| mapping | ShaderNodeMapping | POINT | Location 0, Rotation 0 | A | 16:26.5 |
| voronoi_1 (upper) | ShaderNodeTexVoronoi | 3D, Smooth F1, Euclidean, Normalize off | **Roughness 0.0**, Lacunarity 2.0, Randomness 1.0; Scale 30, Detail 0, Smoothness 0.1 from the group input | A | 11:22.5, 11:36.5, 12:20.5 |
| voronoi_2 (lower) | ShaderNodeTexVoronoi | 3D, Smooth F1, Euclidean, Normalize off | **Roughness 1.0**, Lacunarity 2.0, Randomness 1.0; Scale 30, Detail 3, Smoothness 0.03 from the group input | A | 12:40.5, 13:00.5 |
| rgb_curves_1 | ShaderNodeRGBCurve | C points (0,0), **(0.6758, 0.2928)**, (1,1) | Factor 1.0 | A | 14:05.5, 16:26.5 |
| rgb_curves_2 | ShaderNodeRGBCurve | C points (0,0), **(0.6331, 0.3000)**, (1,1) | Factor 1.0 | A | 14:17.5, 16:26.5 |
| bump_1 | ShaderNodeBump | Invert on | **Distance 0.004**, Filter Width 0.1 | A | 12:08.5, 12:28.5 |
| bump_2 | ShaderNodeBump | Invert on (copied from bump_1) | **Distance 0.00008** (typed; displays 0.0001), Filter Width 0.1 | A | 13:04.5, 13:26.5 |
| glass | ShaderNodeBsdfGlass | Multiscatter GGX | Color white, **Roughness 0.0**, IOR 1.5 (from the group input) | A | 11:56.5, 16:26.5 |
| group_output | NodeGroupOutput | Shader | - | A | 16:26.5 |

### Connections

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 11:16 | A high |
| mapping | Vector | voronoi_1 | Vector | 11:16 | A high |
| mapping | Vector | voronoi_2 | Vector | 12:40.5 (kept by Shift+Ctrl+D) | A high |
| voronoi_1 | Distance | rgb_curves_1 | Color | 13:44.5 | A high |
| rgb_curves_1 | Color | bump_1 | Height | 13:44.5 | A high |
| voronoi_2 | Distance | rgb_curves_2 | Color | 13:44.5 | A high |
| rgb_curves_2 | Color | bump_2 | Height | 13:44.5 | A high |
| bump_2 | Normal | bump_1 | Normal | 13:08.5 | A high |
| bump_1 | Normal | glass | Normal | 11:56.5 | A high |
| glass | BSDF | group_output | Shader | 14:29.5 | A high |
| group_input | Scale | mapping | Scale | 14:56.5 | A high |
| group_input | Glass Color | glass | Color | 15:11.5 | A high |
| group_input | Glass Roughness | glass | Roughness | 15:20.5 | A high |
| group_input | Glass IOR | glass | IOR | 15:26.5 | A high |
| group_input | Voronoi Scale 1 | voronoi_1 | Scale | 15:33.3 (upper linked first) | A high |
| group_input | Voronoi Scale 2 | voronoi_2 | Scale | 15:34.3 | A high |
| group_input | Voronoi Smoothness 1 | voronoi_1 | Smoothness | 15:41.5 | A high |
| group_input | Voronoi Smoothness 2 | voronoi_2 | Smoothness | 15:47.5 | A high |
| group_input | Voronoi Detail 1 | voronoi_1 | Detail | 15:50.5 | A high |
| group_input | Voronoi Detail 2 | voronoi_2 | Detail | 15:53.5 | A high |
| group_input | Bump Strength 1 | bump_1 | Strength | 16:15.5 | A high |
| group_input | Bump Strength 2 | bump_2 | Strength | 16:16.5 | A high |

### Group interface

| control | socket type | default | min / max | internal destination | visible effect | evidence |
|---|---|---|---|---|---|---|
| Shader (output) | Shader | - | - | glass.BSDF | | 14:53.5 A |
| Scale | Float None (from Vector) | 1.0 | -inf / inf | mapping.Scale | pattern size | 14:59.5 A |
| Glass Color | Color | white | - | glass.Color | tint | 15:17.5 A |
| Glass Roughness | Float Factor | **0.0** | 0 / 1 | glass.Roughness | frost (left clear) | 15:23.5 A |
| Glass IOR | Float None | 1.5 | 0 / 1000 | glass.IOR | | 15:29.5 A |
| Voronoi Scale 1 | Float None | 30 | -1000 / 1000 | voronoi_1.Scale | big hammered cells | 15:44.5, 15:59.5 A |
| Voronoi Scale 2 | Float None | 30 | -1000 / 1000 | voronoi_2.Scale | fine layer | 15:44.5, 16:02.5 A |
| Voronoi Smoothness 1 | Float Factor | 0.1 | 0 / 1 | voronoi_1.Smoothness | edge softness | 16:05.5 A |
| Voronoi Smoothness 2 | Float Factor | 0.03 | 0 / 1 | voronoi_2.Smoothness | | 15:50.5 A |
| Voronoi Detail 1 | Float None | 0 | 0 / 15 | voronoi_1.Detail | | 16:14.5 A |
| Voronoi Detail 2 | Float None | 3 | 0 / 15 | voronoi_2.Detail | | 15:53.5 A |
| Bump Strength 1 | Float Factor | 1.0 | 0 / 1 | bump_1.Strength | big cells relief | 16:23.5 A |
| Bump Strength 2 | Float Factor | 1.0 | 0 / 1 | bump_2.Strength | fine relief | 16:23.5 A |

Group node values at the end (16:41.5, `evidence/a/crops/t1641_voronoi_group_node_values.png`): equal to the defaults.

### RGB Curves (C channel)

| node | points (x, y) | class | evidence |
|---|---|---|---|
| rgb_curves_1 | (0,0), (0.6758, 0.2928), (1,1) | A | `crops/t1405_curves1_final_point.png`, `crops/t1626_curves_bumps.png` |
| rgb_curves_2 | (0,0), (0.6331, 0.3000), (1,1) | A | `crops/t1417_curves2_final_point.png`, `crops/t1626_curves_bumps.png` |

---

## 4. Textured Glass Cells (17:52-22:32)

Group `Textured Glass Cells`. Frames: `evidence/a/frames/t2015_cells_graph_before_grouping.jpg` (20:15.5, whole graph
before Ctrl+G) and `evidence/a/frames/t2207_cells_group_interior.jpg` (22:07.5, inside the group with all inputs wired).

```
TexCoord.Object ─► Mapping(Point).Vector ─┬─► Voronoi(3D, Distance to Edge).Vector ─Distance─► Map Range(Float, Linear, Clamp).Value
                                           │        Map Range.Result ─► Bump(invert, 0.003).Height ;  Bump.Normal ─► Glass.Normal
                                           └─► Noise(3D, fBM, Normalize).Vector ─Factor─► Color Ramp.Factor ─Color─► Hue/Sat/Value.Color
                                                    HSV.Color ─► Glass(Multiscatter GGX).Roughness ;  Glass.BSDF ─► Group Output.Shader
Group Input: Scale ─► Mapping.Scale ; Glass Color ─► Glass.Color ; Glass Roughness ─► HSV.Value ; Glass IOR ─► Glass.IOR ;
             Voronoi Scale/Detail/Roughness/Randomness ─► Voronoi ; Noise Roughness Scale/Detail 1/Detail 2 ─► Noise Scale/Detail/Roughness ;
             Bump Strength ─► Bump.Strength
```

### Node inventory

| node | type | settings | input values (unlinked) | class | evidence |
|---|---|---|---|---|---|
| group_input | NodeGroupInput | 12 inputs | - | A | 22:07.5 |
| tex_coord | ShaderNodeTexCoord | - | - | A | 18:04, 22:07.5 |
| mapping | ShaderNodeMapping | POINT | Location 0, Rotation 0 | A | 22:07.5 |
| voronoi | ShaderNodeTexVoronoi | 3D, **Distance to Edge**, Normalize off (no Smoothness socket) | Lacunarity 2.0; Scale 30, Detail 0, Roughness 0.5, Randomness 1 from the group input | A | 18:17.5, 18:24.5, 20:15.5 |
| map_range | ShaderNodeMapRange | data_type FLOAT, interpolation LINEAR, **Clamp on** | **From Min 0.02**, From Max 1, To Min 0, To Max 1 | A | 19:04.5, 19:20.5, 22:07.5 |
| bump | ShaderNodeBump | Invert on | **Distance 0.003**, Filter Width 0.1 | A | 18:44.5, 18:48.5, 20:15.5 |
| noise | ShaderNodeTexNoise | 3D, **fBM**, **Normalize on** | Lacunarity 2.0, Distortion 0.0; Scale 20, Detail 15, Roughness 1.0 from the group input | A | 19:37.5, 20:15.5 |
| color_ramp | ShaderNodeValToRGB | RGB, Linear; stops below | - | A | 19:52.5-19:57.85 |
| hsv | ShaderNodeHueSaturation | - | Hue 0.5, Saturation 1.0, Factor 1.0; Value 1.0 from the group input | A | 20:11.5, 20:49.5 |
| glass | ShaderNodeBsdfGlass | Multiscatter GGX | Color white, IOR 1.5 (from the group input); Roughness linked from HSV | A | 18:36.5, 20:15.5 |
| group_output | NodeGroupOutput | Shader | - | A | 20:20.5 |

### Colour ramp stops

| index | position | colour (as read) | scene-linear to set | class | evidence |
|---|---|---|---|---|---|
| 0 | 0.000 | black #000000 (default, untouched) | (0, 0, 0, 1) | A | 20:15.5 |
| 1 | 1.000 | Perceptual HSV (0, 0, **0.659**), Hex **#A8A8A8** | (0.3916, 0.3916, 0.3916, 1) | A (readout) / C (conversion) | `crops/t1957_ramp_stop1_final_color.png` (19:57.8) |

The white stop was dragged darker; the picker shows 0.631 at 19:57.3, 0.647 at 19:57.6 and **0.659 / #A8A8A8** at
19:57.80-19:57.85; it closes at 19:57.87 (last legible value used).

### Connections

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 18:04 | A high |
| mapping | Vector | voronoi | Vector | 18:04 | A high |
| mapping | Vector | noise | Vector | 19:28.5 | A high |
| voronoi | Distance | map_range | Value | 19:00.5 | A high |
| map_range | Result | bump | Height | 19:00.5 | A high |
| bump | Normal | glass | Normal | 18:40.5 | A high |
| noise | **Factor** (bpy Fac, grey wire) | color_ramp | Factor | 19:52.5 | A high |
| color_ramp | Color | hsv | Color | 20:08 | A high |
| hsv | Color | glass | Roughness | 20:08 | A high |
| glass | BSDF | group_output | Shader | 20:18.5 | A high |
| group_input | Scale | mapping | Scale | 20:37 | A high |
| group_input | Glass Color | glass | Color | 20:53.5 | A high |
| group_input | Glass Roughness | hsv | **Value** | 21:00 | A high |
| group_input | Glass IOR | glass | IOR | 21:06.5 | A high |
| group_input | Voronoi Scale | voronoi | Scale | 21:17.5 | A high |
| group_input | Voronoi Detail | voronoi | Detail | 21:20 | A high |
| group_input | Voronoi Roughness | voronoi | Roughness | 21:27 | A high |
| group_input | Voronoi Randomness | voronoi | Randomness | 21:28 | A high |
| group_input | Noise Roughness Scale | noise | Scale | 21:36 | A high |
| group_input | Noise Roughness Detail 1 | noise | Detail | 21:37 | A high |
| group_input | Noise Roughness Detail 2 | noise | Roughness | 21:38 | A high |
| group_input | Bump Strength | bump | Strength | 22:02.5 | A high |

### Group interface

| control | socket type | default | min / max | internal destination | visible effect | evidence |
|---|---|---|---|---|---|---|
| Shader (output) | Shader | - | - | glass.BSDF | | 20:32.5 A |
| Scale | Float None (from Vector) | 1.0 | -inf / inf | mapping.Scale | pattern size | 20:47.5 A |
| Glass Color | Color | white | - | glass.Color | tint | 20:56.5 A |
| Glass Roughness | Float None | **1.0** | **0 / 2** | **hsv.Value** | scales the noise roughness (0 clear .. 2 very frosted) | 21:02.5 A |
| Glass IOR | Float None | 1.5 | 0 / 1000 | glass.IOR | | 21:11.5 A |
| Voronoi Scale | Float None | 30 | -1000 / 1000 | voronoi.Scale | cell size | 21:20.5 A |
| Voronoi Detail | Float None | 0 | 0 / 15 (C) | voronoi.Detail | cracks inside cells (demo 2.1) | 22:25.5 A, limits C |
| Voronoi Roughness | Float Factor | 0.5 | 0 / 1 | voronoi.Roughness | | 21:36.5 A |
| Voronoi Randomness | Float Factor | 1.0 | 0 / 1 (C) | voronoi.Randomness | | 22:25.5 A, limits C |
| Noise Roughness Scale | Float None | 20 | -1000 / 1000 | noise.Scale | size of roughness patches | 21:46.5 A |
| Noise Roughness Detail 1 | Float None | 15 | 0 / 15 | noise.Detail | | 21:54.5 A |
| Noise Roughness Detail 2 | Float Factor | 1.0 | 0 / 1 | noise.Roughness | "second layer of detail" | 21:50.5 A |
| Bump Strength | Float Factor | 1.0 | 0 / 1 | bump.Strength | | 22:06.5 A |

Group node values at the end (22:25.5, `evidence/a/crops/t2225_cells_group_node_values.png`): equal to the defaults.

---

## 5. Top level of each material

| material | nodes | link | group node values |
|---|---|---|---|
| Textured Glass Circles | ShaderNodeGroup (`Textured Glass Circles`), ShaderNodeOutputMaterial (target All) | Group.Shader -> Output.Surface | defaults (22:29.5) |
| Textured Glass Voronoi | ShaderNodeGroup (`Textured Glass Voronoi`), Material Output | same | defaults (16:41.5) |
| Textured Glass Cells | ShaderNodeGroup (`Textured Glass Cells`), Material Output | same | defaults (22:25.5) |

Volume, Displacement and Thickness of the Material Output stay unlinked.

---

## 6. Overview 0:40-2:42: product groups (purchased file) and their controls

Read from the group nodes before the demo edits (class A for names, order, types and values; internals never shown = D).
"(f)" = factor slider.

| group | t | controls (default) | vs. the tutorial build |
|---|---|---|---|
| Textured Glass Circles | 0:42.5 | Scale 1, Glass Color white, Glass Roughness 0.2 (f), Glass IOR 1.5, Voronoi Scale 50, Voronoi Detail 0, Voronoi Roughness 0.5 (f), Voronoi Smoothness 1 (f), Voronoi Randomness 1 (f), Bump Strength 1 (f) | identical |
| Textured Glass Voronoi | 1:18.5 | Scale 1, Glass Color pale mint (display ~#ECFEF0), Glass Roughness 0.2 (f), Glass IOR 1.5, Voronoi Scale 1 30, Voronoi Scale 2 30, Voronoi Smoothness 1 0.1 (f), Voronoi Smoothness 2 0.03 (f), Voronoi Detail 1 3.0, Voronoi Detail 2 1.0 (f), Bump Strength 1 1 (f), Bump Strength 2 1 (f) | differs: roughness 0.2 (tutorial 0), tint, Detail 1/2 = 3.0 / 1.0 factor (tutorial 0 / 3) |
| Textured Glass Cells | 1:38.5 | Scale 1, Glass Color white, Glass Roughness 1.0 (plain 0..2), Glass IOR 1.5, Voronoi Scale 30, Voronoi Detail 0, Voronoi Roughness 0.5 (f), Voronoi Randomness 1 (f), Bump Strength 1 (f) | no noise controls (tutorial adds 3) |
| Textured Glass Wavy | 2:00.5 | Scale 1, Glass Color white, Glass Roughness 0.2 (f), Glass IOR 1.5, Bump Strength 1 (f), Rotation (0, 0, 0) deg | built in segment b |
| Textured Glass Blobby | 2:16.5 | Scale 1, Glass Color white, Glass Roughness 1.0, Glass IOR 1.5, Voronoi Scale 10, Voronoi Detail 2.6, Voronoi Roughness 0.5 (f), Voronoi Smoothness 0.1 (f), Bump Strength 1 (f) | built in segment b |
| Frosted Glass | 2:28.5 | Scale 1, Glass Color white, Glass Roughness 1.0, Glass IOR 1.5, Noise Scale 20, Noise Detail 15, Noise Roughness 1 (f) | built in segment b |

Crops: `evidence/a/crops/t0042_product_circles_controls.png`, `t0118_product_voronoi_controls.png`,
`t0138_product_cells_controls.png`, `t0200_product_wavy_controls.png`, `t0216_product_blobby_controls.png`,
`t0228_product_frosted_controls.png`.

---

## 7. Reference frames of the finished look

| frame | t | what |
|---|---|---|
| `evidence/a/frames/t0004_intro_final_render_six_panes.jpg` | 0:04.5 | product render: 3x2 framed panes on a dark studio backdrop (top Circles / Voronoi / Cells, bottom Wavy / Blobby / Frosted; order C) |
| `evidence/a/frames/t0042_overview_product_circles_group.jpg` | 0:42.5 | Circles pane, red Suzanne behind, Cycles viewport |
| `evidence/a/frames/t0118_overview_product_voronoi_group.jpg` | 1:18.5 | Voronoi pane (product, mint tint) |
| `evidence/a/frames/t0138_overview_product_cells_group.jpg` | 1:38.5 | Cells pane (product) |
| `evidence/a/frames/t1044_circles_viewport_look.jpg` | 10:44.5 | tutorial Circles result, camera view zoomed onto Plane.002 |
| `evidence/a/frames/t1626_voronoi_group_final_graph.jpg` | 16:26.5 | tutorial Voronoi result (left viewport) |
| `evidence/a/frames/t1641_voronoi_group_node_final.jpg` | 16:41.5 | Voronoi pane result |
| `evidence/a/frames/t2207_cells_group_interior.jpg` | 22:07.5 | tutorial Cells result (left viewport) |
| `evidence/a/frames/t2225_cells_group_node_final.jpg` | 22:25.5 | Voronoi (left) and Cells (right) panes side by side |

All tutorial views: Cycles viewport (100 samples), HDRI old_apartments_walkway at 0.5, Filmic + Very High Contrast,
transparent film, a red Suzanne behind the pane (its distance is not readable, class D).

---

## 8. Notes for the builder (class C)

- Only 3D Voronoi and Noise are used: all have 4D variants, so the D2 torus (seamless) mode needs no D5 substitution here.
- Units: Object coordinates of an applied-scale object are metres. Tutorial densities: Circles 50 cells/m, Voronoi 30/m
  (two layers), Cells 30/m with noise 20/m; bump distances 0.002 / 0.004 + 0.00008 / 0.003 m.
- Exposing a socket by dragging to the Group Input copies type, subtype, limits and description; the tutorial then turns
  Scale from Vector into Float, types default 1 and resets the group node's Scale (it reads 0 after the type change).
- Socket names are UI labels of Blender 5.1: "Factor" on Color Ramp / Noise / HSV / RGB Curves may be `Fac` in bpy;
  look sockets up by identifier or index.
- Bump "Filter Width" (0.1) exists in Blender 4.4+; set it explicitly.
- Ramp stop 1 linear value = sRGB EOTF of 0.659 = 0.3916.
