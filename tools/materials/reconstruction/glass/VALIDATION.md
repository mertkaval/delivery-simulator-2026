# Glass materials (PM_Glass*): validation

All runs headless (`blender --background --factory-startup`), one Blender process at a time, Blender 5.2.3, Cycles on
the GPU (OptiX/CUDA; the HIP warning in the logs is harmless). Scripts: `scripts/glass_scene.py` (scenes, renders,
bake, dump) and `scripts/compare.py` (system Python, side-by-side and metrics). Nothing under the game or the road tool
was touched.

## Summary

| check | result |
|---|---|
| build + contract (`--modes check`, `renders/check.json`) | 6 / 6 materials pass `core.check_contract` (one group node `MRS`, `BSDF` -> Surface, Use UV / Tile Size present, displacement method Bump) |
| graph vs spec | every class A node, setting, value, ramp stop, curve point and link of the six final video graphs is in the groups (`NODES.md`, `pm_note` per node); class C items in `DECISIONS.md` |
| pattern scale vs video | dominant wavelength of the high-passed pane equal to the video's within one spectrum bin for Circles, Voronoi, Cells, Wavy, Blobby in at least one lighting (table below) |
| same cell layout as the video | Voronoi, Cells, Blobby: layout correlation peaks at zero shift (0.08-0.34, 2-4x the best value elsewhere): the object-mode Voronoi fields are the video's own cells |
| look | matching pattern type, size, relief and frosting for all six; remaining differences are lighting (no video HDRI, D6) and backdrop placement (class D), see section 5 |
| UV-mode bake, 4 m and 1 m tiles, 1024 px | seamless: seam ratio 0.79-1.07 on every varying map (Wavy 1 m 0.79: one 8-bit column step inside the interior spread, section 6); periodicity test passes for 5 / 6 (Frosted: 8-bit quantisation artefact, see section 6); Wavy relief amplitude constant across the blend band (-1 %, section 6b) |
| audit fixes (section 6b) | GL-1 Wavy streaks the same on every pane orientation (fixed); GL-2 Wavy UV-mode amplitude dip removed (fixed); GL-3 Blobby contrast: material proven identical to the video's graph, deviation backdrop-dependent, kept open as scene / lighting |
| real-world checks | 1.2 m x 2 m panel at eye level in front of a wall / checker band / Suzanne / pole, and the rig's road strip: sizes plausible (section 2) |

## 1. Video scene renders (`renders/video_r*`)

The video scene rebuilt from the spec (DECISIONS G14): six 0.8 m panes with the video's object coordinates, red
Suzannes behind, 50 mm camera at 4.435 m, Filmic + Very High Contrast, film transparent (composited on the viewport
grey #2B2B2B for the comparisons), bundled HDRI at strength 0.5. `video_full_grey.png` = whole camera view,
`video_Glass<Name>.png` = each pane cropped by its projected bounding box, `video.json` = settings and pane boxes.

| folder | lighting | samples / denoise | purpose |
|---|---|---|---|
| `renders/video_r1_city180/` | city 180 deg | 256, OIDN | round 1 |
| `renders/video_r2_interior90/` | interior 90 deg | 256, OIDN | round 2: closest overall brightness |
| `renders/video_r4_sunset270/` | sunset 270 deg | 100, none | round 4 (round 3 = same lighting with 256 + OIDN, comparisons only): matches the video's viewport frames (Sample n/100, no denoising) |

## 2. Real-world scale checks (`renders/`)

- `panel_<Name>.png` (and `panel_none.png` without glass): a 1.2 m x 2 m pane (bottom 0.25 m) seen from 3 m at eye
  level 1.7 m (35 mm), city HDRI, AgX. Behind it: a plain wall with a black-and-white checker band at 1.25-1.95 m, a
  Suzanne 0.55 m behind and a blue pole 0.6 m behind. Close-up sheet: `comparisons/panel_glass_zoom.png` (Circles,
  Cells, Wavy, Frosted). At this scale Circles reads as fine dimpled bathroom glass (2 cm), Cells as faceted
  "crystal" glass, Wavy as reeded / fluted glass, Frosted as satin glass that keeps shapes but blurs edges, Voronoi and
  Blobby as hammered glass. The refraction displaces the 0.6 m distant pole by about its width, the frost blurs
  the checker to a soft pattern - plausible for real patterned glass.
- `PM_Glass<Name>_road.png`: the rig's road strip (7 x 20 m, camera at 1.7 m). Glass lying on a road is not a use
  case; the view only confirms the material renders on the road tool's mesh type and that it builds in UV-metre
  coordinates without errors. The relief is too fine to see at this distance (as expected for 2-10 cm features).

## 3. Lighting first, then the material

The video's HDRI (`old_apartments_walkway_1k`, Poly Haven) is not available (D6). Eighteen bundled-HDRI variants were
rendered with the unchanged materials (`comparisons/lighting_hdri_sheet.png`, top-left = the video at 33:23; then
city 150 / 210, interior 0 / 90 / 180 / 270, studio 90 / 270, forest 90, sunset 270; round-1 sheet with city and
courtyard 0-270 under `tmp/materials_glass/hdri_test/`). Changing only the HDRI changes the high-pass contrast seen
through the same glass by up to 1.8x (Cells 0.039 -> 0.070, Wavy 0.026 -> 0.017), the mean brightness by 2x and the
apparent redness of the Suzannes (Filmic desaturates the brightly lit red to pink under interior 90). These numbers
are therefore read as **lighting**, not material, unless they stay the same across lightings.

## 4. Comparisons and iterations (`comparisons/`)

`<Name>_<round>_video_vs_ours.png`: left the video's converged pane ("Rendering Done" frames 10:44.5, 16:26.5, 22:07.5,
25:20, 29:36, 33:03; pane box measured on the orange outline), right our pane from the same camera, same
pane-relative crop. `all_panes_<round>_video_vs_ours.png`: the whole 33:23 camera view (sample 1/100 in the video) vs
ours. Metrics in `compare_<round>.json` (luminance, 512 px): `wavelength_*` dominant feature wavelength (pane
fraction), `hf_contrast_*` std of the high-passed luminance, `ncc0` / `layout_*` correlation at zero shift and its peak.

| material | wavelength video | ours r2 / r3 / r4 | hf contrast video | ours r2 / r3 / r4 | layout peak (shift px) r4 |
|---|---|---|---|---|---|
| Circles | 0.0372 | 0.0372 / 0.0372 / 0.0372 | 0.048 | 0.053 / 0.057 / 0.058 | 0.03 (no peak; not verified) |
| Voronoi | 0.0411 | 0.0411 / 0.0460 / 0.0460 | 0.090 | 0.060 / 0.078 / 0.079 | 0.28 at (0, 0), elsewhere 0.12 |
| Cells | 0.0289 | 0.0269 / 0.0289 / 0.0289 | 0.043 | 0.039 / 0.070 / 0.070 | 0.34 at (-1, 0), elsewhere 0.16 |
| Wavy | 0.0269 | 0.0252 / 0.0269 / 0.0269 | 0.016 | 0.026 / 0.017 / 0.019 | 0.04 (raw ncc0 0.41 in r2) |
| Blobby | 0.0312 | 0.0312 / 0.0372 / 0.0372 | 0.047 | 0.023 / 0.028 / 0.029 | 0.26 at (0, 0), elsewhere 0.06 |
| Frosted | 0.1116 | 0.156 / 0.156 / 0.156 | 0.0099 | 0.0050 / 0.0047 / **0.0098** | - (no cells) |

Rounds (all with the same material values; the materials were never changed after the comparisons, G16):

1. **r1 city 180** (`*_r1_*`): pattern type and size right for all six. Voronoi shows the video's fine crinkle of the
   second Voronoi layer with sharp highlights (the city HDRI has sharp building edges); under the softer interior /
   sunset HDRIs the same crinkle is barely visible, i.e. the crinkle's visibility is lighting.
2. **r2 interior 90** (`*_r2_*`): closest mean brightness of Voronoi / Blobby; Cells and Frosted look very close; the
   Suzannes behind Circles / Wavy look pink (overexposed red through Filmic, lighting).
3. **r3 sunset 270, 256 spp + denoise** (`*_r3_*`): bright neutral backdrop like the video's. Contrast metrics move by
   up to 1.8x with lighting alone (section 3). Frosted contrast stays at half the video's in r2 and r3.
4. **r4 sunset 270, 100 spp, no denoise** (`*_r4_*`, the video's viewport settings): Frosted contrast becomes equal
   (0.0098 vs 0.0099): the denoiser had removed the mottle, a render-setting difference, not a material one.
   `GlassBlobby_r4_zoom.png` compares the blobs at 2x: same blob size and two-level structure; the video shows strong
   dark / light shading from a contrasty environment that our uniform backdrop does not have.

Material candidates that were considered and rejected (would mean changing class A values to compensate lighting):
raising Blobby bump (contrast 0.6x the video under every bundled HDRI, but its shape and size match and the video
environment has dark regions behind that pane), raising Voronoi bump 2 (visible under city light), lowering Wavy bump
(its contrast is 0.017-0.026 vs 0.016, lighting-dependent).

## 5. Remaining differences

| difference | class | cause |
|---|---|---|
| backdrop colours / brightness (grey-white walkway vs bundled HDRIs), redness of the Suzannes | lighting | D6: video HDRI not available |
| Suzannes slightly smaller / higher than in the video; the middle panes show less red | scene | Suzanne placement is class D (spec a / b D13); fitted by eye |
| Blobby relief contrast about 0.6x the video's | scene / lighting (open) | the material is pixel-identical to the video's literal graph and the bump distance was typed 0.004; the Blobby / Voronoi ratio moves with the backdrop (0.34-0.46, section 6b) but never reached the video's 0.52 in our scenes. Kept open: the video's environment is not available (D6); a 5.1.1 renderer difference cannot be tested |
| Voronoi fine crinkle less visible in r2-r4 | lighting | visible under the city HDRI (r1) |
| Circles: cell layout not confirmed against the video | not verified | the 10:44.5 reference is zoomed with the pane cut by the frame (box extrapolated by 121 px), so the crop registration is not good enough for a 2 cm pattern; pattern size and contrast match |
| Frosted wavelength 0.156 vs 0.112 of the pane | minor | low-contrast mottle (std 0.01) where the spectrum peak is flat; the look is the same uniform satin blur |
| Wavy orientation | class C | Gabor Orientation 3D from a widget fit (0.797, 0.604, 0); the streak period matches (0.0269 = 0.0269); applied relative to the surface off the video's pane (DECISIONS G18) |

## 6. Bake (UV mode, `tmp/materials_bake/glass/`, `renders/bake.json`, `renders/bake.log`)

`bake.bake(material, tile=4.0 and 1.0 m, res=1024, samples=16)` in UV mode (Use UV = 1), maps albedo / normal /
roughness (the contract's glass outputs). **Transmission is not baked**: a baked tile carries the tint (albedo =
Glass Color), the relief (normal) and the roughness; refraction / IOR must be set by the engine's glass shader.

| material | 4 m tile: normal seam ratio | roughness | 1 m tile: normal | roughness | periodicity (normal / roughness, offset 0.5, 0.25) |
|---|---|---|---|---|---|
| Circles | 1.014 | constant 0.2 | 1.009 | constant | mad 0.0005, corr 0.99998 OK |
| Voronoi | 0.994 | constant 0.0 | 1.008 | constant | mad 0.0019, corr 0.99989 OK |
| Cells | 1.066 | 0.988 (mean 0.196) | 0.999 | 0.974 | mad 0.0009, corr 0.99996 OK |
| Wavy | 0.967 (before G17: 0.995) | constant 0.2 | 0.787 (before: 0.794) | constant | mad 0.0001, corr 0.99999 OK |
| Blobby | 1.013 | 0.992 (mean 0.224) | 1.037 | 0.976 | mad 0.0005, corr 0.99998 OK |
| Frosted | flat (no relief) | 0.979 (mean 0.286) | flat | 0.968 | roughness mad 0.0026, corr 0.80 **FAIL by the test threshold** |

Seam ratio = edge MAD / interior MAD (1 = the seam looks like any other pixel step). All varying maps are seamless.
Albedo is constant white (the default Glass Color). Frosted: its roughness varies by only std 0.0064 (13 grey levels in
the 8-bit PNG), so the per-pixel correlation of the shifted bake is dominated by quantisation; averaged over 4 x 4
pixels the rolled correlation is 0.96 against -0.007 unrolled, i.e. the tile repeats. (Because of this threshold the
`--modes bake` run ends with `GLASS RUN FAIL`; every other check in it passed.) The Frosted normal map is
constant (no bump in the video), its "seam ratio 0" is the metric on a flat map. Contrast-stretched normal maps around
the tile seam: `comparisons/bake_normal_seam_stretch_wavy_cells_voronoi.png` (no seam visible; Wavy normals vary only
along u, as the vertical streaks should; image from the pre-G17 bake). Wavy 1 m seam ratio 0.79: its normal map spans
only std 2.5 grey levels, so the single wrap step (0.47 levels) is compared with a noisy mean; the interior column
steps have mean 0.60, std 0.14, 5th percentile 0.39, and the steps next to the seam are 0.52-0.73, so the wrap step
lies inside that spread (8-bit quantisation, not a seam). Before G17 the band centre also lost a third of the relief
(section 6b). Note: glass normals are subtle (Wavy spans 114-139 of 255), so a game bake
should use 16-bit PNGs; the core bake writes 8 bit.

## 6b. Audit fixes (GL-1, GL-2, GL-3)

The probe scripts were throwaway (scratchpad); their outputs stay under `tmp/materials_verify/glass/` and the sheets
named below are copied to `comparisons/`.

**GL-1 Wavy object mode depended on the pane plane (fixed, DECISIONS G18).** Probe: the built group's Gabor field
(`gabor_relief` -> emission, 16-bit linear) on 1 m planes, FFT peak (`tmp/materials_verify/glass/fix_probe/`, sheet
`comparisons/wavy_orientation_surface_relative.png`):

| plane | before (audit) | after | streaks after |
|---|---|---|---|
| X-Z (video pane; the shelter's back glass), front | 0.020 m, vertical | 0.0200 m | vertical; field corr 0.9996 to the pre-fix probe (identical up to 8 bit) |
| X-Z seen from behind | - | 0.0200 m | vertical (mirror image of the front: the same field) |
| Y-Z (the shelter's side glass) | 0.0278 m (+39 %), vertical | 0.0217 m | vertical |
| X-Y (flat; the rig's road strip) | 0.018 m, diagonal at 142 deg | 0.0199 m | along Y |
| UV mode, 1 m tile on X-Z | - | 0.0213 m | along V |

Expected period 1 / (12 x 5 x 0.797) = 0.0209 m. Re-rendered `renders/panel_GlassWavy.png` (X-Z pane: same image,
mean abs difference 0.00015 = sampling noise) and `renders/PM_GlassWavy_road.png` (object mode, X-Y strip: the streaks
now run along the road instead of diagonally; before / after sheet
`tmp/materials_verify/glass/wavy_road_panel_before_after.png`). The video-scene renders r1-r4 stay valid: the Wavy pane
there is the X-Z pane, where the field is unchanged.

**GL-2 Wavy UV-mode cross-fade dip (fixed, DECISIONS G17).** Variance-preserving gain. Column std of the field or of
the baked normal R channel; band = last 15 % of the tile in u, centre = 7.5 % from the edge:

| measurement | before (audit) | after |
|---|---|---|
| field probe, 1 m tile, 512 px: column std band centre vs interior | - | 0.0920 vs 0.0929 (-1 %); mean abs u-step band 0.04553 vs interior 0.04548 |
| bake 1 m, normal R: column std band centre vs interior | 1.62-1.68 vs 2.48-2.49 (-33..-35 %) | 2.471 vs 2.499 (-1 %) |
| bake 1 m: mean abs u-gradient, last 15 % vs interior | 0.511 vs 0.607 | 0.619 vs 0.617 (+0 %) |
| bake 4 m (streak period 5 px, undersampled): band centre / u-gradient | -33 % / 1.764 vs 2.206 | -8 % / 2.138 vs 2.241 (-5 %) |
| field mean (centre of the gain) | - | 0.4997-0.5002 on every probe plane |
| periodicity (normal, offsets 0.5 / 0.25) | corr 0.99999 | corr 0.99999, mad 0.00014 |

**GL-3 Blobby relief weaker than the video's (investigated; material unchanged; kept open, DECISIONS G19).**

1. Bump chain against the frames 27:24-27:42: `evidence/b/crops/t2742_blobby_graph.png` shows Voronoi 3D Smooth F1
   Euclidean, Normalize off, Scale 10, Detail 2.600, Roughness 0.500, Lacunarity 2.000, Smoothness 0.100,
   Randomness 1.000; Distance -> Bump Height; Bump Invert off, Strength 1, Distance 0.004, Filter Width 0.100 - all as
   built. The text typed at 27:37.9 reads "0.004" with the cursor after the 4
   (`comparisons/blobby_bump_distance_typed_2737.png`, 8 fps from 27:37.4): the distance is exactly 0.004.
2. Literal graph: the 27:42 graph typed node by node into a plain material (no library wrapper) renders
   pixel-identically to `PM_GlassBlobby` on the same pane (mean abs difference 0.0, HDRI only and checker card).
   Nothing unseen in our chain changes the result.
3. Controlled backdrops: one centred 0.8 m video pane, the video camera (50 mm at 4.435 m), sunset 270 x 0.5, 100 spp,
   no denoise, Filmic Very High Contrast; a 1.6 m card 1.2 m behind (`comparisons/GlassBlobby_controlled_backdrops.png`,
   `comparisons/blobby_controlled.json`; hf contrast as in compare.py, 3 % inset, 512 px):

| backdrop | Voronoi hf | Blobby hf | Blobby / Voronoi |
|---|---|---|---|
| HDRI only | 0.0234 | 0.0108 | 0.46 |
| black / white checker, 10 cm squares | 0.2066 | 0.0709 | 0.34 |
| bright emissive spot on dark grey (like the light behind the video's middle column) | 0.0611 | 0.0276 | 0.45 |
| video scene r2 / r4 (section 4) | 0.060 / 0.079 | 0.023 / 0.029 | 0.38 / 0.37 |
| **video** (16:26.5 / 29:36) | 0.090 | 0.047 | **0.52** |

The ratio moves by 1.35x with the backdrop alone, so it is not a fixed property of the material, but none of our
backdrops reaches 0.52. With the graph identical to the frames and every value class A, the remaining cause lies
outside the material: the video's environment (HDRI not available, D6; backdrop class D) or a renderer difference
between Blender 5.1.1 and 5.2.3 that cannot be tested here. No value was tuned (G16).

## 7. Not checked

- Exact video lighting, exact Suzanne / camera placement (D), the purchased product scene of the intro / closing renders
  (product graphs never shown, D).
- EEVEE look (the video uses Cycles only; the EEVEE settings G13 build but were not compared).
- The road tool's bus shelter in a real road scene (`road_adapter.assign_shelter_glass`) - the slot mapping is the core's
  and is tested there; no road tool file was opened here.
- Godot import of baked glass tiles (nothing applied to the game, D10).
- Circles cell layout against the video (section 5).

## Reproduce

```
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
S=tools/materials/reconstruction/glass/scripts/glass_scene.py
"$B" --background --factory-startup --python $S -- --modes check,dump,panel,road --samples 128 --out tools/materials/reconstruction/glass/renders
"$B" --background --factory-startup --python $S -- --modes video --out tmp/materials_glass/r4 --hdri sunset --rotation 270 --strength 0.5 --samples 100 --denoise 0
"$B" --background --factory-startup --python $S -- --modes bake --out tools/materials/reconstruction/glass/renders
python -I tools/materials/reconstruction/glass/scripts/compare.py --ours tmp/materials_glass/r4 --tag r4 --label "round 4" --light "sunset HDRI 270 deg x 0.5"
"$B" --background --factory-startup --python $S -- --modes panel,road --samples 128 --materials PM_GlassWavy --out tools/materials/reconstruction/glass/renders
```
