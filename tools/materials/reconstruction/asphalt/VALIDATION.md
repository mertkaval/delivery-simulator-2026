# Asphalt material (PM_Asphalt): validation

What was rendered, compared, measured and baked, what still differs from the video and what was not checked.
Blender 5.2.3 LTS, headless (`--background --factory-startup`), Cycles on the GPU (OptiX). Video reference: Ryan King
Art, *Procedural Asphalt Material*, 2022 (Blender 3.2): the F12 render at 26:38 (`evidence/all/frames/t2638_final_render.jpg`,
Render Result square 1301 x 1301 px at (630, 98)), the intro overlay at 00:03 and the viewport close-up at 25:10.
Decisions referenced as ASn are in `DECISIONS.md`; U-numbers are the spec's open items (`UNRESOLVED_all.md`).

## Summary

| check | result | evidence |
|---|---|---|
| contract (`core.check_contract`) | PM_Asphalt and PM_AsphaltTutorial OK | `tmp/materials_bake/asphalt/bake.log` |
| graph against the spec | 38 / 38 spec links and every spec node present in both groups | `checks/verify_graph.json`, `NODES.md` |
| look against the video (same scene, framing, pixel scale) | relief, cracks, damaged patches with pebbles, colour range and roughness read like the video; lighting fitted to log-rms 0.22 in 24 sectors | `comparisons/cmp_final_video_vs_PM_Asphalt.jpg`, `metrics.json` |
| exact patches of the video | **not reproduced** (view search: best corr 0.21-0.28, control 0.63) | `comparisons/cmp_view_search.jpg`, `checks/view_match_*.json` |
| literal twin vs controlled material | albedo identical within 4/255 (mean 0.004/255) | `comparisons/cmp_literal_vs_controls.jpg` |
| sizes in metres | 2 m @ Pattern Size 1 = 4 m @ Pattern Size 2: bit-identical | `checks/metres_check.json` |
| seamless bake (UV mode, 4 m, 1024 px) | seam ratio 0.98 / 0.97 (albedo / normal), worst-column outliers <= 0.86, periodicity MAD 0.0011, corr 0.9975 | `checks/bake_seam.json` |
| UV mode vs object mode (bake path vs video field) | equal statistics after AS17: intact mottling p95-p5 0.0782 vs 0.0780 (0.0580 before), crack-tone fraction 0.097 vs 0.100 (0.092 before), damage 0.077 vs 0.079 | section 7a, `checks/uv_mode_match.json`, `comparisons/cmp_uv_match.jpg` |
| damage coverage, video vs view spread | video 0.041 (detector) vs our 24 views 0.030 +- 0.013 (z +0.8, 4 / 24 views above); true per-view coverage 0.011-0.070 | section 9, `checks/damage_views.json`, `comparisons/cmp_damage_views.jpg` |
| road tool | 9 / 9 checks in a real MRS road scene (append, assign, presets, set_road / reapply, the road tool's bake_tiles, EEVEE and Cycles renders) | `checks/road_check.json`, `comparisons/cmp_mrs_road_eevee_cycles.jpg` |

## 1. Renders (`renders/`)

All by `scripts/video_scene.py` (the core rig plus the video's emission planes, AS7 / AS8) unless noted.

| file | what |
|---|---|
| `PM_Asphalt_video.png`, `PM_AsphaltTutorial_video.png` | the video's scene: icosphere subdivisions 6 (10,242 v), radius 1 m, object mode, Cycles 256 samples + denoise, Filmic, 1301 px square, 50 mm at 95 % fill, key disc Strength 100, rim strip Strength 5, `studio` HDRI 0.2 desaturated, black background |
| `PM_Asphalt_fw0.1_video.png` | the same with Bump Filter Width 0.1 (the 5.2 default; U13) |
| `PM_Asphalt_flat.png`, `PM_AsphaltTutorial_flat.png` | the group's Albedo as emission, view Standard: the pattern without lighting |
| `PM_AsphaltTutorial_closeup.png` | 5x zoom on a damaged patch (like the 25:10 render-region close-up), roughness 0.5 as at 25:10 (the roughness ramp came later) |
| `PM_Asphalt_closeup.png` | the same close-up, final material |
| `PM_Asphalt_road.png` | real-world scale check: the rig's 7 m x 20 m road strip, eye level 1.7 m, `city` HDRI visible, object mode (`rig.preview`) |
| `PM_Asphalt_baked_road.png` | the same strip with the UV-mode bake (4 m tile, 1024 px) as an image material (`bake.baked_material`): what an engine would show |
| `PM_Asphalt_mrs_road_eevee.png`, `PM_Asphalt_mrs_road_cycles.png` | a residential road built by Mert Road Studio's own `make_road()` in `tmp/roads/city/base.blend`, `Asphalt Material` = PM_Asphalt (`scripts/road_check.py`) |

## 2. Comparisons (`comparisons/`, built by `scripts/compare.py`)

| file | left -> right |
|---|---|
| `cmp_final_video_vs_PM_Asphalt.jpg` | video 26:38 / PM_Asphalt / PM_Asphalt albedo only |
| `cmp_intro_vs_PM_Asphalt.jpg` | video 00:03 intro overlay / PM_Asphalt |
| `cmp_rounds.jpg` | video / round 1 / final lighting with Filter Width 0.1 / final |
| `cmp_zoom_bump_filter_width.jpg` | two windows (lit upper right, centre) at the same pixel scale: video / FW 0.1 / FW 1.0 / FW 2.0 |
| `cmp_closeup.jpg` | video 25:10 close-up / PM_AsphaltTutorial as at 25:10 / PM_Asphalt |
| `cmp_literal_vs_controls.jpg` | PM_AsphaltTutorial / PM_Asphalt / difference x 10 |
| `cmp_view_search.jpg` | the view search on the video (no match) and on our own render (control, recovered) |
| `cmp_road_live_vs_baked.jpg`, `cmp_mrs_road_eevee_cycles.jpg` | road strip live / baked tile; MRS road EEVEE / Cycles |
| `cmp_uv_match.jpg` | 2 m crop of a 4 m albedo tile (x2.5): object mode / UV mode before AS17 / UV mode after (section 7a; assembled from the `procmat.bake` tiles of the audit, `tmp/materials_verify/asphalt/bake/`, and the rebake, `tmp/materials_asphalt/uvbake/`) |
| `cmp_damage_views.jpg` | the damage detector (red = detected pebbles, yellow = true mask edge, blue = scored lit region): video 26:38 / our view 0 / our view with the most detected damage (section 9) |
| `cmp_eevee_cli_preview.jpg` | the library's default preview (`run.py -- build asphalt --render DIR`): EEVEE sphere and road strip, `city` HDRI |
| `controls_sheet.jpg` | defaults, Crack Amount 0.3 / 0.7, Damage Amount 0.2 / 0.5, Roughness Min 0.1, Pattern Size 2, Crack Width 0.03 (512 px, 64 samples) |

## 3. Lighting first, then the material

The video's lights are visible only in the viewport (U6) and its HDRI cannot be used (D6, U12), so the lighting was
fitted to the reference before any material change, and the remaining lighting differences are reported apart.

- **Key direction and size**: a Lambert fit of the 26:38 shading gives a key nearly perpendicular to the view, up and
  right; three render rounds (384 px) on 24 sectors (12 angles x 2 rings) picked direction (0.80, 0.58, 0.25) in
  camera space, disc size 2.1 at 4 m (Strength 100 as in the video). Final mean display-linear luminance per sector:

  | ring | video | PM_Asphalt |
  |---|---|---|
  | inner (r < 0.5) | 0.218 0.230 0.181 0.099 0.050 0.030 0.022 0.020 0.024 0.035 0.066 0.140 | 0.204 0.214 0.163 0.090 0.041 0.022 0.018 0.018 0.021 0.031 0.063 0.131 |
  | outer (0.5-0.92) | 0.429 0.385 0.266 0.095 0.038 0.020 0.007 0.006 0.008 0.012 0.054 0.213 | 0.380 0.402 0.264 0.091 0.022 0.008 0.007 0.008 0.008 0.013 0.051 0.180 |

  (sectors counter-clockwise from the right; log-rms 0.22). The upper-left limb (sectors 120-180 deg, outer) is darker
  here: the video's HDRI and rim light reach it.
- **Fill tint**: chroma (r, g, b / mean) in a shadowed window: video (1.052, 1.020, 0.928), PM_Asphalt (1.009, 1.000,
  0.991), our albedo (1.019, 0.997, 0.984). The video's fill is warm (its HDRI); ours is neutral on purpose (AS8).
  The material's own colour (#1A1817 -> #4D4D4D, slightly warm) is unchanged.

## 4. Iterations on the material

| round | change | what the comparison showed |
|---|---|---|
| 1 | first build (Bump Filter Width 0.1 = the 5.2 default), rig-style render 1024 px | cracks, patches, pebbles and colours in place; the relief clearly softer than the video at the same scale (`cmp_rounds.jpg`, second panel) |
| 2 | ruled out render causes: 1301 px (the video's displayed size), denoise on / off (no change), Filter Width 0.01 / 0.1 / 1.0 / 2.0 | mid-band relief contrast (std of band-passed log luminance, 1.5-6 px; windows lit / centre / right): video 0.279 / 0.339 / 0.338; FW 0.1 0.161 / 0.251 / 0.225; **FW 1.0 0.256 / 0.347 / 0.323**; FW 2.0 0.319 / 0.410 / 0.377. Adopted 1.0 (AS5) |
| 3 | colour and scale checks: neutral / tinted / warm HDRIs (AS8); normalised power spectra of the same three windows | colour difference = HDRI tint (section 3); spectra: per-band ratios ours / video scatter both ways (0.3-3.2, no consistent shift between windows), so no evidence of a scale error at one view; no further material change |

The literal twin renders the same (render mean difference 0.31/255, 2.8 % of pixels differ by more than 2/255 through
path-tracing noise; albedo at most 4/255), so every comparison holds for both materials.

## 5. The exact field (view search)

Object mode samples the same 3D textures at the same coordinates as the video (AS2), so if Blender 5.2 computed the
same values as 3.2 and the video's sphere were a 1 m sphere in object space, some camera view of our sphere would
show the video's exact cracks and patches. `scripts/sphere_maps.py` renders our albedo over the whole sphere
(equirectangular, from the centre) and `scripts/view_match.py` correlates band-passed log luminance of the video with
every view: 6,000 directions x 60 rolls at a 50 mm perspective, then refinement of the best five (+-4 deg, roll +-6
deg, distances 2.2-10 radii and orthographic).

| run | best correlation | random views (400) |
|---|---|---|
| video 26:38 | 0.21 refined (0.28 coarse, top of 360,000 candidates) | mean 0.00, std 0.05, max 0.13 |
| control: our own render from a known camera (direction (0.30, -0.81, 0.51), roll 10 deg) | 0.63, recovered direction within ~1 deg, roll 11 deg | mean 0.00, std 0.05, max 0.14 |

The search works (control) and finds nothing in the video: the patches are **not** the video's. Unresolved (D):
either the 5.2 Noise / Voronoi values differ from 3.2's or the video's sphere is not a 1 m sphere in object space (U7).
All comparisons are therefore statistical: same scene, framing, scale and lighting, different patches.

## 6. Size controls in metres

`scripts/metres_check.py` bakes the albedo in object mode: a 2 m plane at Pattern Size 1 / Aggregate Size 1/110 m and
a 4 m plane at Pattern Size 2 / Aggregate Size 2/110 m give **bit-identical** images (MAD 0.0, correlation 1.0); a
4 m plane at Pattern Size 2 with the aggregate kept at 1/110 m differs in 0.4 % of the pixels (the pebbles only).

## 7. Bake (UV mode, seamless tiles)

`run.py -- build asphalt --bake tmp/materials_bake/asphalt --tile 4 --bake-res 1024 --bake-samples 16 --periodicity`
(Cycles GPU, Use UV = 1, Tile Size 4 m): `tmp/materials_bake/asphalt/PM_Asphalt_{albedo,normal,roughness}.png`
(+ `_albedo_x2.png`, the 2 x 2 repeat; the same set for PM_AsphaltTutorial).

Re-baked after AS17 (the UV match changes values, not periodicity):

| map | edge MAD | interior MAD | ratio (x / y) | worst-column outlier (x / y) |
|---|---|---|---|---|
| albedo | 0.00861 | 0.00883 | 0.976 (0.923 / 1.028) | 0.614 / 0.669 |
| normal | 0.05326 | 0.05476 | 0.973 (1.037 / 0.911) | 0.857 / 0.762 |

Both pass the core's thresholds (`is_seamless`: outliers <= 1.15, ratios 0.6-1.7). The direct repeat test (bake with
the UVs shifted by (0.5, 0.25) = the first tile rolled by (256, 128) px at 512 px): MAD 0.00107, correlation 0.9975
(threshold 0.012 / 0.97; unshifted control MAD 0.0400). Bake means at the defaults: albedo (0.0278, 0.0271, 0.0267)
linear, roughness 0.593 (p1-p99 0.45-0.72), used as the viewport / glTF fallback values (AS14; before AS17 0.0264 /
0.0257 / 0.0253 and 0.577).

## 7a. UV mode against object mode (audit ASP-1, decision AS17)

UV mode is the path a Godot bake takes, so it must look like object mode (the video's field), not only tile. The
first build claimed "statistically equal" without measuring it; an audit measured UV mode flatter. Measured here in
two steps (`checks/uv_mode_match.json`).

Per texture (`scripts/uv_match.py`: emission bakes of each `object 3D | UV 4D` Mix, 1 sample per pixel = point
samples, 32 m plane at 2048 px, object mode vs UV mode with Tile Size 32 m):

| texture . output | object (3D) mean / std | UV before (4D) mean / std | UV after AS17 mean / std |
|---|---|---|---|
| color_noise . Color | 0.500 / 0.0652 (channels 0.062 / 0.068 / 0.065) | 0.500 / 0.0611 (all channels 0.061) | 0.500 / 0.0652 |
| color_voronoi . Distance | 0.310 / 0.1040 | **0.285 / 0.0754** | 0.310 / 0.1038 |
| cracks_mask_noise . Fac | 0.500 / 0.0719 | 0.500 / 0.0705 | 0.500 / 0.0719 |
| cracks_warp_noise . Color | 0.500 / 0.0755 | 0.500 / 0.0703 | 0.500 / 0.0755 |
| damage_warp_noise . Fac | 0.500 / 0.0620 | 0.500 / 0.0611 | 0.500 / 0.0620 |
| damage_mask_noise . Fac | 0.500 / 0.0719 | 0.499 / 0.0703 | 0.500 / 0.0719 |
| bump_noise . Fac | 0.500 / 0.0813 | 0.500 / 0.0800 | 0.500 / 0.0813 |

The base-cell Voronoi is the main cause (its Distance drives the colour, the roughness and Bump 2); the noises are
1.5-13 % narrower. Quantiles after the fit: within 0.003 of object mode from p5 to p95.

Whole material (`scripts/uv_stats.py`: PM_Asphalt at the defaults, 16 m plane, 4096 px, 4 spp, 16 windows of 4 m;
masks from the group's own sockets: crack groove = `crack_bump_ramp` < 0.5, damage = `damage_mask_ramp` < 0.5,
crack tone = the cracks darken the base colour by > 0.01 sRGB, intact = neither; mean +- sd over the windows):

| measure | object mode | UV before AS17 | UV after AS17 |
|---|---|---|---|
| intact albedo p95 - p5 (sRGB) | 0.0780 +- 0.0007 | 0.0580 +- 0.0007 | **0.0782 +- 0.0010** |
| intact albedo std (sRGB) | 0.0239 +- 0.0002 | 0.0177 +- 0.0002 | **0.0239 +- 0.0003** |
| crack-tone fraction | 0.0996 +- 0.0019 | 0.0924 +- 0.0036 | **0.0971 +- 0.0040** |
| crack groove fraction | 0.1566 +- 0.0028 | 0.1578 +- 0.0057 | 0.1550 +- 0.0058 |
| damage fraction | 0.0792 +- 0.0048 | 0.0732 +- 0.0074 | 0.0766 +- 0.0077 |
| mean albedo (sRGB) | 0.1705 | 0.1671 | 0.1710 |

On the audit's own kind of bake (16 m, 4096 px albedo PNG through `procmat.bake`), the dark-pixel fraction below 0.10
/ 0.12 / 0.14 sRGB per 4 m window: object 0.079 / 0.099 / 0.144, UV before 0.075 / 0.091 / 0.122, UV after 0.079 /
0.100 / 0.143; albedo p95 0.220 / 0.207 / 0.220. The crack geometry (groove fraction) was never different: the cracks
looked fainter in UV mode because the base cells were darker and flatter, so fewer crack pixels stood out. The small
rest (crack tone -2.5 %, damage -3 %) is within about one window sd of the field's own variation. Visual check
`comparisons/cmp_uv_match.jpg`: after AS17 the UV-mode mottling and crack contrast read like object mode. The 2 x 2 repeat shows no
seam; at eye level on the road strip the 4 m repeat is not noticeable (`cmp_road_live_vs_baked.jpg`).

## 8. Road tool (`scripts/road_check.py` in `tmp/roads/city/base.blend`, never saved)

| check | result |
|---|---|
| PM_Asphalt appended from a saved procmat library (`run.py -- build asphalt --save ...`, `core.append_materials`), contract intact | OK |
| residential road built by the road tool's `make_road()` | OK (MRS_Asphalt 240 faces) |
| `road_adapter.assign(road, "Asphalt Material", PM_Asphalt)` | OK: Asphalt Condition Default, evaluated road surface = PM_Asphalt on 240 faces, no MRS_Asphalt left |
| the road tool's `apply_material_preset("heavy_wear")` / `("wet")` | OK: no PM_Asphalt input changed (no shared names) |
| `roads.set_road()` then `road_adapter.reapply()` | OK: set_road puts MRS_Asphalt back, reapply restores PM_Asphalt |
| the road tool's own `bake_tiles()` on a copy named `MRS_PMAsphaltCheck` | OK: albedo / normal / roughness, seamless (ratio 1.06, outliers 0.64 / 0.70) |
| eye-level renders, EEVEE and Cycles | OK (`renders/PM_Asphalt_mrs_road_{eevee,cycles}.png`) |

## 9. Remaining differences

Lighting (not material):
- The video's fill is warm and its HDRI lights the upper-left limb; ours is a neutral, weaker fill there (section 3).
- Emitter shapes, sizes and positions are fitted, not known (U6); highlight shapes differ slightly.

Version / renderer (not separable here):
- Principled v2 (5.2) conserves energy between specular and diffuse and has no Disney retro-reflection; the 3.2
  surface may be slightly brighter at grazing angles (AS11 table).
- Pixel-level contrast (< 1.5 px band) is higher in the video: 0.50-0.52 vs 0.33-0.37. Likely render noise / the
  unknown render resolution scaled for display (U2, U4); the mid band matches (section 4).

Pattern:
- The positions of cracks and patches differ (section 5). In the comparison view the video shows somewhat more damaged
  patches than ours. Measured after an audit (ASP-2, decision AS18; `scripts/damage_views.py`, `scripts/damage_detect.py`,
  `checks/damage_views.json`): 24 views of our sphere in the same scene (lights follow the camera), each with a rendered
  ground-truth mask (`damage_mask_ramp` < 0.5), scored in the lit region the video and the view share (inside 0.85 of
  the image radius, smoothed luminance > 0.06). True damage coverage per view: mean 0.030, sd 0.0135, min 0.011, max
  0.070; our comparison view (view 0) 0.022. A detector (fine-band / mid-band texture energy plus local darkness;
  raw band energy alone does not separate patches from the intact relief) with its threshold calibrated on our views
  tracks the per-view truth with corr 0.74 (mean abs. error 0.0075; pixel IoU only 0.15, so it is a coverage estimate,
  not a segmentation). It gives the video 0.041 against our views' 0.030 +- 0.013: z = +0.8, 4 of 24 views have more.
  The video's lower-left patches lie in shadow and are not scored on either side. Conclusion: the difference is within
  the view-to-view spread of the field on a 1 m sphere (flat 2 m x 2 m windows understate it: a view scores roughly
  0.8 m^2 of curved surface and its coverage is set by a few 0.3 m patches). Of the suggested causes, the 0.343 stop
  *lowers* the damage fraction (0.0655 vs 0.0792 at 0.35, object mode, 64 windows of 2 m), and the 3.2 Noise Fac
  histogram cannot be measured without Blender 3.2 (D). Detected patches are not darker in the video (median smoothed
  luminance 0.187 vs ours 0.159; lighting not separable). Damage Amount stays at the video's 0.35.
- The 25:10 close-up was a 10-sample viewport render (denoised), so its intact surface looks smoother than our
  256-sample close-up; the pebbles' crumpled relief and the recessed patch edges match.

## 10. Not checked

- Godot: nothing was imported or applied (D10); the baked tiles are not wired to the game.
- EEVEE was rendered only through the default preview (`cmp_eevee_cli_preview.jpg`) and the MRS road; it was not
  compared with the video. EEVEE shader compile time and frame cost with 16 detail-15 textures (each 3D texture has a
  4D twin) were not measured.
- Very large object coordinates (road objects far from their origin): float precision of the 110-per-metre pebbles
  above roughly 5 km was not tested.
- The damage stop 0.343 alternative (U1) was measured as a bake statistic only (AS6), not rendered in the video scene.
- Blender 3.2's Noise / Voronoi value distributions (whether 5.2's 3D nodes differ from 3.2's): not measurable here (D).
- Other HDRIs than those listed in AS8, the AgX view transform, displacement (the material is bump only, like the
  video), animation.
- Exact 3.2 numerics: Blender 3.2 is not installed and was not downloaded, so the 3.2 -> 5.2 equivalences in
  `DECISIONS.md` come from the node formulas and the comparisons above.

## Reproduce

```
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
S=tools/materials/reconstruction/asphalt/scripts
"$B" -b --factory-startup --python tools/materials/run.py -- build asphalt --bake tmp/materials_bake/asphalt --tile 4 --bake-res 1024 --periodicity --save tmp/materials_bake/asphalt/asphalt_library.blend --dump tmp/materials_asphalt/dump
"$B" -b --factory-startup --python $S/video_scene.py -- --out tools/materials/reconstruction/asphalt/renders --views video,flat,closeup --materials PM_Asphalt,PM_AsphaltTutorial --res 1301 --samples 256 --state2510 --zoom 5 --offset 0.5,0.4
"$B" -b --factory-startup --python $S/video_scene.py -- --out tools/materials/reconstruction/asphalt/renders --views video --materials PM_Asphalt --res 1301 --filter-width 0.1 --prefix PM_Asphalt_fw0.1
"$B" -b --factory-startup --python $S/video_scene.py -- --out tools/materials/reconstruction/asphalt/renders --views road,road_baked --materials PM_Asphalt --res 1280 --samples 128
"$B" -b --factory-startup tmp/roads/city/base.blend --python $S/road_check.py -- --library tmp/materials_bake/asphalt/asphalt_library.blend --out tmp/materials_asphalt/road_check
"$B" -b --factory-startup --python $S/verify_graph.py -- tools/materials/reconstruction/asphalt/GRAPH_SPEC_all.json tmp/materials_asphalt/verify_graph.json
"$B" -b --factory-startup --python $S/metres_check.py -- tmp/materials_asphalt/metres
"$B" -b --factory-startup --python $S/sphere_maps.py -- tmp/materials_asphalt/match
python -I $S/view_match.py tools/materials/reconstruction/asphalt/evidence/all/frames/t2638_final_render.jpg tmp/materials_asphalt/match tmp/materials_asphalt/match
python -I $S/compare.py C:/GodotProjects/delivery-simulator-2026
# UV mode vs object mode (7a) and the damage-coverage spread (9)
"$B" -b --factory-startup --python $S/uv_match.py -- tmp/materials_asphalt/uvmatch/after
"$B" -b --factory-startup --python $S/uv_stats.py -- tmp/materials_asphalt/uvstats/after          # --no-match = before AS17
"$B" -b --factory-startup --python $S/uv_stats.py -- tmp/materials_asphalt/uvstats/d0343 --modes object --win 2 --set "Damage Amount=0.343"
"$B" -b --factory-startup --python $S/damage_views.py -- tmp/materials_asphalt/dviews/default --n 24
python -I $S/damage_detect.py tools/materials/reconstruction/asphalt/evidence/all/frames/t2638_final_render.jpg tmp/materials_asphalt/dviews/default tmp/materials_asphalt/dviews/det_default.json --panel tools/materials/reconstruction/asphalt/comparisons/cmp_damage_views.jpg
```

(One Blender at a time. `compare.py` also reads the round-1 render and the Filter Width 2.0 test kept in
`tmp/materials_asphalt/`; it skips them when they are missing.)
