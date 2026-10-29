# Street trees and planting: Blender / Godot consistency (Road Studio v5 foliage)

Brief: MRS street trees and plants looked different in Blender and Godot (canopy density, brightness, silhouette),
switched LOD prematurely and abruptly, showed crossed-quad impostors as X shapes from the footbridge and the air, and
the yard kit's hedge / boxwood rendered near-black. This is the measured fix.

| deliverable | file |
|---|---|
| Godot loader | `world/roads/mrs_foliage.gd` (`class_name MrsFoliage`) |
| leaf / bark / plant shader | `world/roads/mrs_foliage.gdshader` |
| hemi-octahedral impostor shader | `world/roads/mrs_foliage_impostor.gdshader` |
| Blender library + v5 materials + asset bake | `tools/roads/mrs/game_trees.py` (`build_game_trees(version=5)`, `_v5_material`, `make_lod1`, `bake_impostors`, `regrade_hedge_textures`, `bake_foliage_assets`, `upgrade_materials`) |
| new assets | `assets/roads/foliage/`: `<species>_lod1.glb` (13), `impostor_albedo.png` (2048², 7.5 MB), `impostor_normal.png` (1024², 2.4 MB), `impostors.json`, `mrs_hedge_leaves.png`, `mrs_hedge_sprays.png`, bake reports |
| harness, Blender side + metrics | `tools/roads/tests/foliage_v5_test.py` |
| harness, Godot side + perf + movies | `tests/capture_foliage_v5.gd` |
| outputs | `tmp/roads/v5/foliage/` (renders, metrics.json per directory, `tables_v5.md`, `doc_tables.md`, `sweep_report.json`, `block/`, `hedges/`, `video/`) |

The game's shared files (`world/landscape/city_landscape.gd`, `foliage_wind.gdshader`, `assets/landscape/`) are
unchanged: MrsFoliage loads the same kit meshes but uses its own materials, LOD1 meshes and impostors.

## 1. Defects, verified

| reported | measured before (Godot, kit materials, shipping LOD) |
|---|---|
| canopies differ between renderers | under one matched light rig (section 2), Godot LOD0 / Blender LOD0 (both v4): coverage 0.96-0.99 to 70 m falling to 0.81 at 200 m, luminance 1.15-1.32, more saturated (no sky sheen in Godot, little translucency light in EEVEE) and blotchier (0.43 vs 0.36 at 8 m); the kit LOD1 had 1.14-1.21 x the coverage, 1.13-1.33 x the luminance and silhouette IoU 0.77-0.83 of LOD0; the impostor 1.5-2.1 x the luminance. In the v4 street-block images Godot also had a weaker ambient (procedural sky vs EEVEE's uniform world), which made the mismatched canopies read darker |
| LOD switches early and pops | LOD0 -> LOD1 at clamp(h x 3, 26, 42) m: one 2 m step changes coverage by up to +49 % and luminance by up to +28 % (walnut_spring at 46 m, linden_a +27 % at 38 m); LOD1 -> impostor at 125-130 m: up to 35 % |
| trees missing | LOD0 / LOD1 / impostor MultiMeshes sat on different cell grids (32 / 96 / 192 m) and visibility ranges are measured to each node's AABB centre, so a tree could be in neither range: auto-LOD coverage 0.46 at 40 m, 0.22 at 120 m (eye 25 m); walnut_spring vanished at 128 m in the sweep; the v4 park view lost its red cherry |
| X-shaped impostors | crossed-quad coverage from a 25 m eye: 0.41 of LOD0 at 8 m, 0.63 at 20 m |
| canopies thin out with distance | mipmapped alpha against a fixed 0.42 cut: Godot LOD0 coverage 0.67 at 200 m; Blender EEVEE 0.81 (Cycles, which has no mipmaps, is the truth: 1.0) |
| hedge / boxwood near-black | the yard kit paints its hedge leaves at linear luminance 0.042 (garden shrubs 0.22): rendered 0.044-0.060 in both renderers (shrub_b 0.14-0.19); COLOR_0 (wind 0-0.6, AO 0.49-1.0) is fine |

## 2. Harness (task A)

`foliage_v5_test.py render <variant>` (Blender) and `capture_foliage_v5.gd harness <variant>` (Godot) render the same
101 shots: 5 species (plane_tree, linden_a, maple_a, walnut_spring, grove_a) x 6 distances (8, 20, 40, 70, 120,
200 m) x 3 eye heights (1.7, 7, 25 m), camera azimuth 25° (between the old impostor cards), lens 30 mm (36 mm
sensor), 1280 x 720, looking at 0.55 x tree height; plus hedge_section / boxwood_ball / shrub_b at 2.5 / 6 / 14 m and
two calibration spheres. The shot list is written by the Blender side to `tmp/roads/v5/foliage/harness.json`.

Light rig (identical in both): sun 3.5 W/m² at Euler (52°, 0, -35°) = Godot `light_energy` 3.5 / pi; uniform world
(0.55, 0.68, 0.85) = Godot uniform procedural sky (ambient and reflections from the sky: a radiance map is needed
for the leaves' sky sheen); Standard view transform = Godot linear tonemapper; transparent film, so alpha is the
silhouette. Godot: 4x MSAA. Blender: EEVEE 64 samples. Calibration (spheres, below) matches to 0.5 %.

Variants: Blender `lod0` / `lod1` (kit meshes, v4 material), `v5lod0` / `v5lod1` (v5 material, MRS LOD1), `cycles`
(LOD0, no mipmaps: the coverage truth). Godot `before_*` (CityLandscape meshes + foliage_wind.gdshader) and
`after_*` (MrsFoliage), each `lod0` / `lod1` / `imp` (forced) and `auto` (shipping LOD ranges).
Metrics (`foliage_v5_test.py measure`): coverage = mean alpha of the frame; luminance = mean linear Rec.709
luminance of pixels with alpha >= 0.75 (Godot pixels unpremultiplied from the known clear colour); colour = mean
sRGB of those pixels; IoU = silhouette overlap with the reference at 1/4 resolution; blotchiness = std / mean of
the 4 x 4-block luminance inside the canopy. `foliage_v5_test.py check` asserts the acceptance limits (Godot v5 within
6 % of Blender v5 in coverage and luminance for LOD0 at all distances, LOD1 from 70 m, impostor at 200 m, auto
everywhere; Blender v5 within 5 % of Cycles): **FOLIAGE_V5 CHECK OK**.

### Results

Reference = Blender v5 LOD0 (its coverage is within 2 % of Cycles at every distance). Cells: coverage ratio /
luminance ratio (`*` = Cycles, 3 species; Cycles luminance is lower because it occludes the sky inside the crown,
which neither EEVEE without ray tracing nor Godot does - it is the coverage reference). After the fix, Godot / Blender
LOD0 (both v5): coverage 0.96-1.02, luminance 0.96-1.04 at every distance and eye height.

**Eye 1.7 m** - reference: Blender v5 LOD0 absolute coverage (% of the 1280x720 frame) / linear luminance; every other cell is coverage ratio / luminance ratio to it (mean of 5 species)

| d (m) | Blender v5 LOD0 (ref) | Blender v4 LOD0 | Cycles (no mip) | Blender v5 LOD1 | Godot before LOD0 | Godot before LOD1 (kit) | Godot before impostor (X) | Godot before auto | Godot after LOD0 | Godot after LOD1 (MRS) | Godot after impostor (hemi-oct) | Godot after auto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 57.00 % / 0.175 | 1.01 / 0.82 | 1.02 / 0.43* | 0.95 / 1.01 | 0.99 / 0.96 | 1.16 / 1.23 | 0.76 / 2.07 | 0.99 / 0.96 | 0.96 / 1.04 | 0.90 / 1.07 | 0.95 / 1.20 | 0.96 / 1.04 |
| 20 | 14.41 % / 0.182 | 1.01 / 0.81 | 1.02 / 0.44* | 0.96 / 1.01 | 1.00 / 0.94 | 1.20 / 1.25 | 0.77 / 1.79 | 1.00 / 0.94 | 0.97 / 0.99 | 0.92 / 1.02 | 0.99 / 1.17 | 0.97 / 0.99 |
| 40 | 3.70 % / 0.189 | 1.01 / 0.81 | 1.02 / 0.42* | 0.96 / 1.01 | 0.99 / 0.95 | 1.20 / 1.24 | 0.80 / 1.67 | 0.46 / 1.17 | 0.99 / 0.98 | 0.94 / 1.00 | 0.98 / 1.12 | 0.99 / 0.98 |
| 70 | 1.22 % / 0.195 | 0.99 / 0.81 | 1.02 / 0.40* | 0.96 / 1.01 | 0.95 / 1.00 | 1.20 / 1.21 | 0.84 / 1.62 | 1.20 / 1.21 | 1.01 / 1.01 | 0.97 / 1.01 | 0.98 / 1.08 | 1.01 / 1.01 |
| 120 | 0.41 % / 0.201 | 0.93 / 0.80 | 1.02 / 0.38* | 0.96 / 1.01 | 0.85 / 0.96 | 1.20 / 1.18 | 0.89 / 1.58 | 0.87 / 1.17 | 1.02 / 0.99 | 0.99 / 1.00 | 0.97 / 1.05 | 0.99 / 1.00 |
| 200 | 0.15 % / 0.212 | 0.81 / 0.75 | 1.02 / 0.36* | 0.96 / 0.99 | 0.67 / 0.97 | 1.20 / 1.13 | 0.92 / 1.51 | 0.92 / 1.51 | 1.00 / 0.99 | 0.99 / 1.00 | 0.97 / 0.99 | 0.97 / 0.99 |

**Eye 7 m** - reference: Blender v5 LOD0 absolute coverage (% of the 1280x720 frame) / linear luminance; every other cell is coverage ratio / luminance ratio to it (mean of 5 species)

| d (m) | Blender v5 LOD0 (ref) | Blender v4 LOD0 | Cycles (no mip) | Blender v5 LOD1 | Godot before LOD0 | Godot before LOD1 (kit) | Godot before impostor (X) | Godot before auto | Godot after LOD0 | Godot after LOD1 (MRS) | Godot after impostor (hemi-oct) | Godot after auto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 64.53 % / 0.179 | 1.00 / 0.82 | - | 0.96 / 1.01 | 0.99 / 0.98 | 1.14 / 1.33 | 0.82 / 1.82 | 0.99 / 0.98 | 0.96 / 1.01 | 0.92 / 1.04 | 0.89 / 1.17 | 0.96 / 1.01 |
| 20 | 15.25 % / 0.189 | 1.01 / 0.82 | - | 0.96 / 1.01 | 0.99 / 0.95 | 1.18 / 1.27 | 0.79 / 1.68 | 0.99 / 0.95 | 0.97 / 0.98 | 0.92 / 1.00 | 0.97 / 1.13 | 0.97 / 0.98 |
| 40 | 3.74 % / 0.192 | 1.01 / 0.82 | - | 0.96 / 1.01 | 0.99 / 0.95 | 1.19 / 1.25 | 0.81 / 1.63 | 0.46 / 1.18 | 0.99 / 0.98 | 0.95 / 0.99 | 0.98 / 1.10 | 0.99 / 0.98 |
| 70 | 1.22 % / 0.196 | 0.99 / 0.81 | - | 0.96 / 1.01 | 0.95 / 1.01 | 1.20 / 1.22 | 0.84 / 1.60 | 1.20 / 1.22 | 1.01 / 1.01 | 0.97 / 1.01 | 0.98 / 1.07 | 1.01 / 1.01 |
| 120 | 0.41 % / 0.203 | 0.93 / 0.80 | - | 0.96 / 1.01 | 0.85 / 0.96 | 1.20 / 1.18 | 0.89 / 1.56 | 0.87 / 1.17 | 1.02 / 0.99 | 0.99 / 1.00 | 0.98 / 1.04 | 0.99 / 1.00 |
| 200 | 0.15 % / 0.212 | 0.80 / 0.75 | - | 0.96 / 0.99 | 0.67 / 0.99 | 1.20 / 1.13 | 0.92 / 1.51 | 0.92 / 1.51 | 1.00 / 0.99 | 0.99 / 1.00 | 0.98 / 0.99 | 0.98 / 0.99 |

**Eye 25 m** - reference: Blender v5 LOD0 absolute coverage (% of the 1280x720 frame) / linear luminance; every other cell is coverage ratio / luminance ratio to it (mean of 5 species)

| d (m) | Blender v5 LOD0 (ref) | Blender v4 LOD0 | Cycles (no mip) | Blender v5 LOD1 | Godot before LOD0 | Godot before LOD1 (kit) | Godot before impostor (X) | Godot before auto | Godot after LOD0 | Godot after LOD1 (MRS) | Godot after impostor (hemi-oct) | Godot after auto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 16.57 % / 0.212 | 1.01 / 0.83 | 1.03 / 0.46* | 0.95 / 1.01 | 0.99 / 0.97 | 1.20 / 1.29 | 0.41 / 1.45 | 0.79 / 0.97 | 0.97 / 0.96 | 0.92 / 0.98 | 0.89 / 1.08 | 0.97 / 0.96 |
| 20 | 8.69 % / 0.207 | 1.01 / 0.83 | 1.03 / 0.44* | 0.96 / 1.01 | 0.99 / 0.97 | 1.20 / 1.30 | 0.63 / 1.50 | 0.79 / 0.97 | 0.98 / 0.96 | 0.93 / 0.97 | 0.94 / 1.07 | 0.98 / 0.96 |
| 40 | 3.12 % / 0.203 | 1.00 / 0.83 | 1.02 / 0.43* | 0.96 / 1.00 | 0.98 / 0.97 | 1.21 / 1.28 | 0.76 / 1.53 | 0.66 / 1.22 | 1.00 / 0.97 | 0.95 / 0.97 | 0.97 / 1.06 | 1.00 / 0.97 |
| 70 | 1.13 % / 0.202 | 0.99 / 0.82 | 1.02 / 0.41* | 0.96 / 1.00 | 0.94 / 1.02 | 1.21 / 1.24 | 0.84 / 1.54 | 1.21 / 1.24 | 1.01 / 1.00 | 0.97 / 1.00 | 1.01 / 1.06 | 1.01 / 1.00 |
| 120 | 0.40 % / 0.206 | 0.93 / 0.81 | 1.02 / 0.39* | 0.96 / 1.01 | 0.85 / 0.97 | 1.20 / 1.19 | 0.89 / 1.53 | 0.22 / 1.29 | 1.02 / 0.98 | 0.98 / 0.99 | 1.00 / 1.03 | 0.98 / 0.99 |
| 200 | 0.15 % / 0.215 | 0.80 / 0.75 | 1.02 / 0.36* | 0.96 / 0.99 | 0.67 / 1.00 | 1.20 / 1.13 | 0.92 / 1.48 | 0.92 / 1.48 | 1.00 / 0.98 | 0.98 / 0.99 | 1.00 / 0.99 | 1.00 / 0.99 |

**Mean canopy colour** (sRGB of fully covered pixels, unpremultiplied; eye 1.7 m) per species at 20 m / 200 m

| species | Blender v5 LOD0 | Blender v4 LOD0 | Godot before LOD0 | Godot after LOD0 | Godot before auto | Godot after auto |
|---|---|---|---|---|---|---|
| plane_tree | (150, 125, 77) / (161, 131, 80) | (136, 113, 71) / (144, 117, 72) | (158, 125, 63) / (184, 140, 70) | (157, 129, 75) / (171, 136, 77) | (158, 125, 63) / (207, 161, 75) | (157, 129, 75) / (157, 129, 82) |
| linden_a | (79, 84, 67) / (90, 96, 81) | (72, 77, 63) / (77, 78, 71) | (71, 75, 45) / (82, 81, 53) | (73, 77, 50) / (85, 90, 63) | (71, 75, 45) / (100, 100, 63) | (73, 77, 50) / (92, 98, 85) |
| maple_a | (159, 81, 87) / (148, 78, 83) | (147, 73, 79) / (138, 71, 76) | (162, 71, 75) / (156, 73, 74) | (158, 78, 83) / (143, 76, 79) | (162, 71, 75) / (218, 92, 93) | (158, 78, 83) / (149, 80, 84) |
| walnut_spring | (124, 157, 75) / (150, 179, 82) | (112, 143, 67) / (124, 153, 72) | (126, 161, 47) / (151, 177, 50) | (128, 162, 70) / (154, 179, 73) | (126, 161, 47) / (172, 212, 61) | (128, 162, 70) / (150, 177, 83) |
| grove_a | (103, 124, 86) / (108, 126, 90) | (92, 111, 77) / (94, 111, 78) | (98, 121, 70) / (110, 127, 78) | (104, 126, 81) / (112, 129, 88) | (98, 121, 70) / (132, 156, 90) | (104, 126, 81) / (104, 123, 88) |

**Hedge / boxwood / shrub** (eye 1.7 m, linear luminance and sRGB colour)

| plant, distance | Blender v4 | Blender v5 | Godot before | Godot after |
|---|---|---|---|---|
| hedge_section 02.5 | 0.060 (53, 74, 53) | 0.169 (85, 124, 81) | 0.056 (44, 74, 38) | 0.170 (84, 124, 79) |
| hedge_section 06 | 0.056 (52, 72, 53) | 0.154 (82, 119, 78) | 0.048 (41, 69, 36) | 0.149 (79, 117, 76) |
| boxwood_ball 02.5 | 0.054 (50, 71, 51) | 0.150 (80, 117, 76) | 0.050 (41, 70, 35) | 0.154 (80, 119, 75) |
| boxwood_ball 06 | 0.050 (49, 68, 51) | 0.136 (76, 112, 74) | 0.044 (39, 65, 33) | 0.135 (75, 112, 73) |
| shrub_b 02.5 | 0.143 (92, 112, 74) | 0.170 (100, 121, 82) | 0.193 (106, 129, 70) | 0.175 (101, 123, 78) |
| shrub_b 06 | 0.134 (90, 108, 73) | 0.165 (99, 119, 83) | 0.181 (103, 125, 67) | 0.172 (101, 122, 77) |

**Light-rig calibration** (Lambert spheres, mean linear luminance): grey 0.5 - Blender EEVEE 0.5319, Cycles 0.5350, Godot 0.5344; green - EEVEE 0.1054, Cycles 0.1060, Godot 0.1058


## 3. What was wrong and what changed (task B)

**One shading model in both renderers.** Blender v5 (`game_trees._v5_material`): albedo x COLOR_0.a, Mix(Principled
(roughness 0.78, F0 0.04), Translucent, 0.25), alpha test at 0.42, crown normal on both card sides. Godot
(`mrs_foliage.gdshader`): the same as a custom `light()`: diffuse (1 - t) N.L + t (-N.L) (Lambert), GGX specular F0
0.04 weighted (1 - t), `SPECULAR` 0.5 for the sky reflection (F0 0.04), Lambert instead of Burley. Measured, one
term at a time (eye 1.7 m, Godot / Blender luminance):

| term isolated | Godot / Blender |
|---|---|
| pure diffuse (no translucency, specular, shadows) | 0.94-1.00 |
| sky specular share (with / without) | Godot +14-19 %, Blender +14-19 % |
| shadows only | 1.00-1.05 (shadowed / unshadowed: 0.82 vs 0.84) |
| translucency, v4 Blender material | 1.15-1.26: EEVEE's default (sphere) thickness lights the Translucent closure from the world far too little, canopies 22 % darker than Cycles / Godot |
| translucency, v5 (EEVEE thin slab, thickness 0) | 0.94-0.99 |

Blender was the odd one out on translucency (fixed in Blender: `thickness_mode = SLAB`, thickness 0), and on
coverage (below). Godot's foliage_wind shader added BACKLIGHT on top of full diffuse, used Burley and F0 0.02, and
Godot flips back-face normals under `cull_disabled` automatically (the old shader's "no back-face flip for leaves" never
happened; the v5 shaders undo the flip for leaf cards so the soft crown normal holds on both sides, in Blender too).

**Alpha and mipmaps.** The coverage of an alpha-tested card should be the share of its full-resolution texels above
the cut; mipmapped alpha averages them and erodes canopies with distance. Godot v5: alpha x (1 + mip x 0.05)
against 0.42, alpha-to-coverage (`alpha_to_coverage_and_one`, edge 0.42). mip_scale from measurements (coverage /
truth, eye 1.7 m, 8 -> 200 m): 0.0: 0.94 -> 0.64; 0.05: 0.96 -> 1.00; 0.07: 0.96 -> 1.05; 0.1: 0.97 -> 1.10; 0.25:
0.99 -> 1.20. Same at MSAA 2x (the project setting) and 0x. Blender v5 samples the alpha with Closest interpolation
(no mipmap) and lets the 64 samples average it: 1.02 x Cycles at every distance (v4: 0.81 at 200 m).
Remaining Godot / Blender difference at 8 m: Godot's anisotropic filtering and MSAA keep more texture contrast (blotchiness
0.44 vs 0.35 at 8 m, equal from 120 m); it is texture sharpness, not lighting (it is the same without shadows).

**MRS LOD1** (`game_trees.make_lod1`, `assets/roads/foliage/<sid>_lod1.glb`): 40 % of the LOD0 leaf cards (random,
seeded), each grown x1.45 about its centre so the total card area stays, bark decimated to 30 %; the LOD0 materials,
COLOR_0 wind / AO and crown normals. 1.3-2.7k triangles (LOD0 1.8-7.4k; kit LOD1 1.0-2.8k). From 70 m it is within
3 % of LOD0 in coverage and 1 % in luminance (kit LOD1: +20 % / +13-33 %).

## 4. Distant trees (task C): hemi-octahedral impostors

8 x 8 views per species over the upper hemisphere (hemi-octahedral mapping), rendered orthographically from the v5
LOD0 (albedo x AO with coverage alpha, 64 px frames; object-space crown normals, 32 px frames), 13 species in a
4 x 4 atlas (`game_trees.bake_impostors`, ~3 min headless). 64 px is ~1:1 with a tree where impostors start (163 m:
a 13 m tree is ~35 px tall at 720p with the game camera's 78° fov, ~53 px at 1080p) and keeps the atlases within the
asset budget (no 3D texture above 2048 px; a first 128 px bake, 4096², failed `asset_budget_test.gd`). The shader faces one quad to the camera (to the light in
shadow passes, choosing the light's frames: the shadow is the tree's silhouette), finds the hemi-octahedral grid
triangle of the view direction and gives each pixel one of its three frames by a dither against the barycentric
weights (averaging the three frames' alphas eroded the canopy: they are not parallax-aligned), keeps a pixel with the
frame's coverage as probability, and lights it with the baked normals through the same light() as the leaves. It does
not receive shadows (a flat quad would shadow itself); `direct_scale` 0.45 stands in for the crown's self-shadowing
(measured with 64 px frames: 0.55 -> luminance 1.01 x LOD0 at 200 m / 1.05-1.07 at 120 m, 0.45 -> 0.99 / 1.03-1.05). Why not crossed quads with a top card: any
fixed set of planes reads as planes from some elevation; the hemi-octahedral impostor is right from 0-90°.
Measured at 200 m: coverage 0.97 / 0.98 / 1.00 and luminance 0.99 / 0.99 / 0.99 of LOD0 from eye 1.7 / 7 / 25 m,
IoU 0.88-0.91 (crossed quads: 0.92 / 1.51, IoU 0.74; from above at 8 m 0.41 coverage, an X). Images:
`tmp/roads/v5/foliage/scripts/cmp_imp_top.jpg`, block overhead view `tmp/roads/v5/foliage/block/after_overhead.png`.

## 5. LOD distances and transitions

| switch | distance | band | measured on | why |
|---|---|---|---|---|
| LOD0 -> LOD1 | 75 m | 12 m (69-81 m) | 32 m cell (shared LOD0 / LOD1 grid) | MRS LOD1 within 3 % / 1 % of LOD0 from 70 m (6-8 % at 8-20 m); the avenue trees seen from the street and the footbridge deck (8.5 m eye) stay LOD0; GPU cost barely depends on it (LOD0 end 40 / 55 / 75 m: 2.22 / 2.17 / 2.20 ms street view) |
| LOD1 -> impostor | 175 m | 24 m (163-187 m) | each tree | impostor within 3 % of LOD0 in coverage and 1 % in luminance at 200 m (3-5 % at 120 m) |
| impostor end | 1500 m | - | - | |
| plants | 120 m (taller than 0.8 m), 60 m | 12 m fade | 32 m cell | v4: 90 / 45 m hard cut |

Transitions are a dithered crossfade (interleaved-gradient noise in screen space, complementary between the two
levels: no gap, no double density) computed from the main camera (`MAIN_CAM_INV_VIEW_MATRIX`, the same value in shadow
passes, so shadows crossfade too). The near switch uses a per-cell distance: LOD0 and LOD1 cells share one grid, each
MultiMeshInstance3D has a fixed custom AABB and the shader measures to its centre (an `instance uniform`), the point
Godot measures visibility ranges to, so node ranges are exact (no hidden draws, no hysteresis gaps; margins 0). The
far switch is per tree (impostors are two triangles; their cells are 128 m). Distance sweep (one tree, 10-250 m in 2 m
steps, `capture_foliage_v5.gd sweep` + `foliage_v5_test.py sweep`): largest one-step change beyond what forced LOD0
does at the same step:

| species | before (shipping) | after |
|---|---|---|
| linden_a | 34.5 % coverage at 130 m; +27 % luminance at 38 m | 1.6 % |
| walnut_spring | tree vanishes at 128 m; +49 % coverage, +28 % luminance at 46 m | <= 2.7 % |
| plane_tree | 15.6 % at 130 m | 1.9 % |
| maple_a | 8.1 % at 130 m | 1.9 % |

Temporal metric of the movies (mean abs frame difference, 320 x 180 luma; pop index = largest frame difference /
median of the 15 around it; flicker = mean change of the frame difference / its mean):

| movie | pop index | at frame | flicker |
|---|---|---|---|
| godot_dolly_before | 1.92 | 278 | 0.031 |
| godot_dolly_after | 1.05 | 385 | 0.012 |
| godot_walk_before | 1.39 | 347 | 0.020 |
| godot_walk_after | 1.13 | 238 | 0.013 |
| godot_deck_before | 1.02 | 290 | 0.008 |
| godot_deck_after | 1.02 | 322 | 0.008 |

## 6. Hedge and boxwood (task D)

The data, not the shader: the kit's hedge / boxwood textures average linear luminance 0.042 (leaf gaps painted at
sRGB 0.03-0.07). `regrade_hedge_textures()` writes MRS copies (`assets/roads/foliage/mrs_hedge_leaves.png`,
`mrs_hedge_sprays.png`): linear RGB x3.1 / x2.8 to mean luminance 0.13, 15 % less saturated, gaps lifted to a deep
green. The core material (`yardleaf_hedge`) is "solid foliage" (opaque, no translucency, roughness 0.85) in both
renderers; the sprays are leaves. Both MrsFoliage and the Blender v5 library use the copies. Result (table above):
hedge 0.15-0.17, boxwood 0.14-0.15 (shrub_b 0.17) in both renderers, within 3 % of each other. Under the v4 street
lighting: `tmp/roads/v5/foliage/hedges/hedges_compare.jpg` (Blender v4 / Godot before / Blender v5 / Godot after).
The street block can use hedges again (placement is another module).

## 7. MrsFoliage API (task E)

```
var fol := MrsFoliage.new()
add_child(fol)
var counts: Dictionary = fol.build(model, {})      # model = parsed street JSON (uses "trees" and "plants")
```
- trees[]: species, pos (Blender Z-up), yaw, scale -> LOD0 / LOD1 MultiMeshes per (species, 32 m cell), impostors per
  128 m cell, trunk capsule colliders (StaticBody3D "TreeTrunks"; radius clamp(trunk x scale, 0.14, 0.42), 3.5 m).
- plants[]: id (garden / yard kit node), pos, yaw, scale -> one MultiMesh per (id, 32 m cell), fading at 120 / 60 m.
- opts: `collision` (true), `tint` (true: +-6 % per instance), `wind` (1.0), `shadows` (true), `shadow_lod1`,
  `shadow_impostor`, `shadow_plants` (true), `force` ("lod0" | "lod1" | "imp"), `lod0_end` 75, `lod0_fade` 12,
  `lod1_end` 175, `lod1_fade` 24, `plant_end_tall` 120, `plant_end_low` 60.
- returns `{"trees", "plants", "multimeshes", "trunks", "species": {sid: n}, "plant_ids": {id: n}, "lod": {...}}`
  (street block: 66 trees, 2,078 plants, 66 trunks).
- statics: `MrsFoliage.species(sid)`, `MrsFoliage.plant(id)`, `MrsFoliage.set_wind(x)`, `MrsFoliage.set_lod_bands(v)`.
  Materials are shared: the last build's LOD distances apply to every MrsFoliage.
- Switching `MrsStreetBlock.plant()`: replace its CityLandscape body with `var f := MrsFoliage.new()`, `add_child(f)`,
  `return f.build(model)` (it returns the same "trees" / "plants" / "multimeshes" keys and makes its own "TreeTrunks"
  colliders, so plant() no longer needs its own). Until then: build the block with `{"trees": false}` and add a
  MrsFoliage beside it, as `capture_foliage_v5.gd load_block("after")` does.
- Blender side: `game_trees.build_game_trees()` now defaults to `version=5` (v5 materials, MRS LOD1, regraded hedges;
  `version=4` keeps the old library). A scene saved with the v4 library: `game_trees.upgrade_materials(5)`.
- Re-baking the assets: `blender -b --factory-startup --python tools/roads/tests/foliage_v5_test.py -- bake
  [--only hedge|lod1|imp]`, then `godot --headless --path . --import`.

## 8. Performance (task F)

Godot 4.7.2, D3D12, RTX 3070 Laptop, 1280 x 720, 4x MSAA, v4 day lighting (directional shadows to 220 m), vsync off,
median of 120 frames (repeat runs agree within 0.03 ms), street block with all 66 trees and 2,078 plants
(`capture_foliage_v5.gd block before|after`). Views: street = avenue sidewalk (eye 1.8 m), street_cyclist, deck =
footbridge deck looking along it, deck_west = from the deck over the avenue and park, aerial (45 m), overhead (110 m).

| view | GPU ms before / after | foliage GPU share before / after | CPU ms before / after | draw calls before / after | primitives before / after |
|---|---|---|---|---|---|
| aerial | 1.72 / 2.77 | 0.28 / 1.31 | 0.47 / 0.72 | 820 / 1431 | 702k / 1883k |
| deck | 0.90 / 1.08 | 0.07 / 0.23 | 0.24 / 0.31 | 209 / 361 | 335k / 627k |
| deck_west | 1.41 / 2.26 | 0.31 / 1.15 | 0.26 / 0.39 | 201 / 548 | 471k / 1048k |
| overhead | 1.15 / 1.71 | 0.05 / 0.59 | 0.54 / 0.68 | 885 / 1258 | 383k / 695k |
| street | 1.51 / 2.22 | 0.50 / 1.19 | 0.54 / 0.77 | 907 / 1250 | 732k / 1357k |
| street_cyclist | 1.56 / 2.02 | 0.69 / 1.14 | 0.36 / 0.44 | 513 / 679 | 212k / 420k |

Split (GPU ms, trees only / plants only, the other part hidden):

| view | trees before / after | plants before / after | no foliage |
|---|---|---|---|
| aerial | 1.60 / 2.52 | 1.62 / 1.72 | 1.46 |
| deck | 0.83 / 0.96 | 0.90 / 0.95 | 0.85 |
| deck_west | 1.21 / 1.76 | 1.33 / 1.66 | 1.11 |
| overhead | 1.12 / 1.61 | 1.10 / 1.21 | 1.12 |
| street | 1.28 / 1.91 | 1.19 / 1.30 | 1.03 |
| street_cyclist | 1.46 / 1.89 | 1.00 / 1.04 | 0.88 |

What the extra cost is: GPU ms of the "after" build with one thing changed (measured on the build before the plant
ranges were trimmed to 120 / 60 m; the first row is that build unchanged):

| change | street | street_cyclist | deck | deck_west | aerial | overhead |
|---|---|---|---|---|---|---|
| that build, unchanged (plants 140 / 70 m) | 2.20 | 2.07 | 1.06 | 2.24 | 2.80 | 1.78 |
| LOD1 casts no shadow | 2.13 | 2.04 | 1.06 | 2.21 | 2.71 | 1.70 |
| impostors cast no shadow | 2.21 | 2.07 | 1.07 | 2.25 | 2.81 | 1.81 |
| plants cast no shadow | 2.16 | 2.07 | 1.07 | 2.18 | 2.70 | 1.80 |
| plant ranges 90 / 45 m (v4) | 2.16 | 2.04 | 1.06 | 2.11 | 2.78 | 1.58 |
| LOD0 end 55 m | 2.17 | 2.11 | 1.07 | 2.21 | 2.81 | 1.82 |
| LOD0 end 40 m | 2.22 | 2.29 | 1.05 | 2.12 | 2.55 | 1.85 |
| no alpha-to-coverage | 2.23 | 2.08 | 1.11 | 2.25 | 2.80 | 1.81 |
| no LOD dither discard | 2.18 | 2.07 | 1.08 | 2.22 | 2.76 | 1.80 |
| built-in lighting instead of the custom light() | 2.28 | 2.11 | 1.09 | 2.32 | 2.79 | 1.79 |

Custom lighting, alpha-to-coverage and the LOD dither cost nothing measurable; shadows of LOD1 / impostors / plants
<= 0.1 ms each; the LOD0 distance <= 0.25 ms. The increase is fill: canopies now keep their true coverage with
distance (the old ones thinned to 0.67 or switched to the kit LOD1 at 26-42 m), and mid-distance trees cast shadows
(the kit LOD1 cast none, so tree shadows vanished beyond 42 m). Block images: `tmp/roads/v5/foliage/block/`
(`before_final_*.png`, `after_final_*.png`, `*_night.png`, `night_compare.jpg`), `block_cmp.jpg` in `scripts/`.

## 9. Recordings (task G)

13-14 s, 30 fps, 1280 x 720. Godot: Movie Maker (`--write-movie x.avi --fixed-fps 30`), H.264 via ffmpeg (first 10
settle frames trimmed). Blender: the same camera path (`tmp/roads/v5/foliage/paths/<path>.json`, written by the Godot
side) rendered with EEVEE (16 samples, every second frame, frame-doubled to 30 fps) from
`tmp/roads/v4final/street_block_v4.blend` with the v5 materials (`foliage_v5_test.py video ... --v5`).

| path | Godot before (v4 env) | Godot after (v4 env / matched env) | Blender v5 | side by side |
|---|---|---|---|---|
| street-level walk past the avenue trees (2.3 m/s) | `video/godot_walk_before.mp4` | `video/godot_walk_after.mp4` / `video/godot_walk_after_matched.mp4` | `video/blender_walk.mp4` | `video/sbs_walk.mp4` (Blender / Godot, matched env), `video/sbs_walk_v4env.mp4`, `video/sbs_walk_before_after.mp4` |
| dolly 10 -> 250 m from a park tree group (LOD0 -> LOD1 -> impostor) | `video/godot_dolly_before.mp4` | `video/godot_dolly_after.mp4` / `video/godot_dolly_after_matched.mp4` | `video/blender_dolly.mp4` | `video/sbs_dolly.mp4`, `video/sbs_dolly_v4env.mp4`, `video/sbs_dolly_before_after.mp4` |
| footbridge deck pan (8.5 m eye) | `video/godot_deck_before.mp4` | `video/godot_deck_after.mp4` / `video/godot_deck_after_matched.mp4` | `video/blender_deck.mp4` | `video/sbs_deck.mp4`, `video/sbs_deck_v4env.mp4`, `video/sbs_deck_before_after.mp4` |

(all under `tmp/roads/v5/foliage/`). "matched env" = Blender's QA world as a uniform Godot sky + sun 3.5 / pi + AgX
(`capture_foliage_v5.gd movie after <path> matched`). Frame sheets: `video/frames/dolly.jpg`, `walk.jpg`, `deck.jpg`
(before / after), `sbs_matched_sheet.jpg` (Blender / Godot, matched), `sbs_sheet.jpg` (Blender / Godot, v4 env).

## 10. Remaining issues

- Integration: `MrsStreetBlock.plant()` still uses CityLandscape (owned by the street-block engineer); hedges are not
  placed by the v4 block (placement module).
- Impostor frames are 64 px (asset budget): at the impostor start a tree covers ~35-53 px with the game camera, but with a
  narrow lens (e.g. the 30 mm harness camera, ~85 px) they are slightly magnified; forced close up (8-20 m) the impostor
  is soft and dithered. It only shows from 163 m.
- Near (8-20 m) Godot canopies show more texture contrast than EEVEE (blotchiness 0.44 vs 0.35), from texture
  filtering / MSAA vs 64-sample supersampling, not from lighting.
- The look depends on a sky radiance map for the leaves' sky sheen (the game's procedural sky has one; a BG_COLOR
  background without one makes canopies ~15 % darker and more saturated).
- Wind sways LOD0 / LOD1 as before; impostors do not sway (invisible at 160 m+).
- **Environment, not foliage**: the v4 street-block captures light Godot with a procedural sky whose ambient is ~3.8 x
  weaker than EEVEE's uniform world (grey sphere, same v4 rigs: sunlit side 0.531 vs 0.525, shaded side 0.081 vs
  0.311). Everything in shade - canopy interiors and lee sides - therefore reads much darker in Godot in those images
  (`video/sbs_*_v4env.mp4`). With the environment matched (`video/sbs_*.mp4`) the two renderers are equivalent. Fix
  in the scene environment (e.g. `ambient_light_energy` ~3.5 or `AMBIENT_SOURCE_COLOR` = the Blender world colour, or
  a darker Blender world), outside this module.
