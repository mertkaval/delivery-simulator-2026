# PM_Cobblestone: validation

Blender 5.2.3 LTS, headless (`--background`), one Blender process at a time; the user's Blender and Godot were not
touched. Reference video `30vbbpy9zwg` (Blender 5.0.1). Frames: `evidence/a/frames/`, `evidence/b/frames/`.

## 1. Build and contract

`blender --background --factory-startup --python tools/materials/run.py -- build cobblestone` -> `PM_Cobblestone`,
`PM_CobblestoneDisplaced`, `check_contract` OK for both (`RUN OK`). Group `PM_Cobblestone`: 94 nodes + 10 frames,
205 links (the video's 39 internal nodes / 91 links, plus the 3D / 4D twins, their Use UV mixes, the coordinate block,
the Albedo / Height outputs and the four UV-mode matching nodes of CB16). Node-by-node: NODES.md (every node carries its
evidence note). Graph fidelity is checked mechanically by `scripts/verify_graph.py` (section 6).

## 2. Renders (`renders/`)

| file | what |
|---|---|
| `PM_Cobblestone_sphere.png` | PM_CobblestoneDisplaced in the tutorial scene (CB12): 0.5 m icosphere, sub 4 + subsurf 3, Cycles 128 samples, Filmic Very High Contrast, transparent film, 1434 px |
| `PM_Cobblestone_bump_sphere.png` | PM_Cobblestone (bump only, the road material) in the same scene |
| `PM_Cobblestone_road.png` | real-world scale check: 7 m x 20 m road strip, eye level 1.7 m (rig `eye` camera), Cycles, same sun / HDRI, no rim light |
| `PM_Cobblestone_road_top.png` | the same strip from above (orthographic) |
| `road_tool_PMC_Road.png` | a Mert Road Studio road (built with the road tool's own `make_road()` in `tmp/roads/city/base.blend`, not saved) with PM_Cobblestone in its Asphalt and Paving sockets, EEVEE |
| `eevee/PM_Cobblestone*_{sphere,plane_hd,road}.png` | the core's standard previews (`run.py --render`, EEVEE, AgX, city HDRI, 2 m sphere): EEVEE renders the material, with displacement on `plane_hd` |

Commands: `scripts/render_tutorial.py -- --out tools/materials/reconstruction/cobblestone/renders --views
sphere,bump_sphere,road,road_top --res 1434 --samples 128 --hdri courtyard --sun-az=-45 --sun-el 45 --prefix
PM_Cobblestone` (defaults: --ico 4 --subsurf 3 --cam-az 0 --cam-el -1); `run.py -- build cobblestone --render
.../renders/eevee --views sphere,plane_hd,road`; `scripts/road_check.py` (header has the command).

## 3. Comparisons (`comparisons/`) and iterations

### Camera found: the same stones as the video
The material samples Object coordinates with Blender's deterministic 3D textures, so `scripts/view_search.py` rendered
the stone mask (group output Height through an emission, no lighting) of our sphere from many camera directions and
correlated each with the high-passed video crop of 0:04. Coarse grid (+-15 deg): front view (azimuth 0, elevation 0)
correlation **0.536**, every other direction <= 0.135 (mean 0.128). Refined (+-4 deg, step 2, roll -2 / 0 / 2,
75 views): best 0.545 at azimuth 0, elevation -2, roll 0; elevation 0 gives 0.492. The renders use elevation -1.
`t0004_vs_stone_mask_front_view.png`: **the video's stone layout appears stone for stone on our sphere** (same
five-way joint in the lower centre, same large round stone at the left, same small stones at the right edge). So the
object-mode field of Blender 5.2 equals the video's (5.0.1) and the camera is level from -Y (C, U-item "camera
transform" of segment a resolved by search). The tutorial-build viewport at 26:08 aligns the same way (2D scale /
shift search: correlation 0.59, `t2608_vs_ours_aligned.png`).

### Round 1 (first render, guessed scene)
Camera 8 deg above, sun from the front-left, ico 6 + subsurf 2. Material read: right stone size and colours, but the
stones looked like flat plates with crisp edges and the shading was flat. Changes: mesh density set to the build
file's (ico 4 + subsurf 3 = 81,920 faces), lighting sweep (HDRI city / courtyard / forest / sunset, sun 8 directions).
Lighting, not material: the sky HDRI changes the stone tops from grey to near white (specular of roughness 0.65).

### Round 2 (camera from the search, lighting sweep)
`t0004_vs_ours_sphere.png` (also `t4016_vs_ours_sphere.png`: 40:16 is the same image as 0:04). Disc statistics
(display sRGB, centred disc 85 %):

| | mean RGB | luminance mean | std | p10 | p90 |
|---|---|---|---|---|---|
| video 0:04 | 0.382 0.351 0.316 | 0.355 | 0.202 | 0.085 | 0.644 |
| ours (courtyard, sun az -45 el 45) | 0.358 0.329 0.307 | 0.333 | 0.179 | 0.060 | 0.564 |
| ours, sun from above (az 20 el 75) | 0.303 0.271 0.252 | 0.276 | 0.202 | 0.046 | 0.570 |
| ours, sun behind (az 150 el 60) | 0.181 0.156 0.155 | 0.161 | 0.173 | 0.046 | 0.423 |

Mean colour within 0.03 per channel and the same warm-grey balance; contrast slightly lower (std 0.18 vs 0.20).
Lighting differences (separate from the material): the video's top half is lit more evenly and brightly and its
lower-left is darker (sun direction and fish_hoek_beach unknown / not available); our stone tops pick up the
courtyard's blue-white sky on the right; the video's background glow is the viewport, not the render.

### Round 3 (material: stone fill and joints)
`t0004_vs_ours_zoom_lower_centre.png` shows the one clear material-looking difference: in the 0:04 product render the
stones fill more of the surface and the joints are narrow dark lines; ours have wider dirt joints. Tests:
`Cobblestone Individual Size` 0.4 / 0.6 / 0.8 (`t0004_stone_fill_individual_size_0p6_0p4_0p8.png`): lower = fuller
stones; the product look lies between 0.4 and 0.6. Against the **tutorial build** at 26:08 (`t2608_vs_ours_aligned.png`,
`t2608_vs_ours_individual_size_0p6_0p5.png`) our default 0.6 matches the stone outlines and sizes (the large round
stone at the left is about 175 px wide in both crops). Conclusion: the product file (0:04, 40:16) differs from the tutorial
build; the defaults stay the tutorial's (A) and no material value was changed (CB13).

Material parameters changed by the iterations: none. Changes made: scene (camera, mesh density, lights) and the
viewport colour / roughness constants.

`displaced_vs_bump_only.png`: PM_CobblestoneDisplaced vs PM_Cobblestone (bump only). The bump-only road material
keeps the look; only the silhouette and the cast shadows of the stones are lost.

## 4. Seamless bake (UV mode, 4 m tile, 1024 px, 16 samples) -> `tmp/materials_bake/cobblestone/`

Numbers below are the first build (before the audit). After the audit fix CB16 (section 6) the bake was repeated:
albedo ratio 1.094 (x 1.136 / y 1.053), outliers 0.78 / 0.79; normal 1.003 (outliers 0.86 / 0.85); roughness 1.253
(x 1.22 / y 1.29, outliers 0.66 / 0.79); periodicity albedo mad 0.00104, corr 0.9977: **seamless and periodic**
(`checks/bake_seam.json`, 2 x 2 preview `comparisons/bake_2x2_albedo_roughness.jpg`, inspected: no seam on the tile
borders in albedo or roughness). Bake means now albedo linear (0.0200, 0.0200, 0.0139), roughness 0.715 (CB15).

`run.py -- build cobblestone --bake tmp/materials_bake/cobblestone --tile 4.0 --bake-res 1024 --bake-samples 16
--periodicity` (GPU): albedo, normal, roughness PNGs and a 2 x 2 albedo preview (`*_albedo_x2.png`), for both
materials (identical, the bake sets BUMP).

| map | edge_mad | interior_mad | ratio | ratio_x / y | outlier_x / y | is_seamless |
|---|---|---|---|---|---|---|
| albedo | 0.00689 | 0.00629 | 1.095 | 1.226 / 0.964 | 0.919 / 0.715 | yes |
| normal | 0.03516 | 0.03493 | 1.007 | 1.064 / 0.950 | 0.920 / 0.828 | yes |

Direct repeat test (`--periodicity`, UVs shifted by (0.5, 0.25)): albedo mad 0.00092, correlation 0.99826 (unshifted
comparison mad 0.0339): **periodic**. Bake means: albedo linear (0.0187, 0.0183, 0.0122), roughness 0.74 (CB15).
The 2 x 2 preview shows no seam; at 8 m the 4 m repeat of the larger moss / dirt patches is visible.

## 5. Road tool

`scripts/road_check.py` in `tmp/roads/city/base.blend` (never saved): `append_materials` from the saved library,
`road_adapter.assign(road, "Paving Material", PM_Cobblestone)` (Sidewalk Surface -> Default) and "Asphalt Material"
(Asphalt Condition -> Default); evaluated road mesh: `{'MRS_Paint': 128, 'MRS_Concrete': 192, 'PM_Cobblestone': 432}`
-> `ROAD OK`; render `renders/road_tool_PMC_Road.png` (cobbled carriageway and sidewalks, stones about 0.14 m).

## Remaining differences

- Stone fill vs the product render 0:04 / 40:16 (fuller stones, narrower joints): the product file, not the tutorial
  build (CB13). Our default matches the build at 26:08.
- Lighting: sun / rim transforms and the fish_hoek_beach HDRI are not reproducible (D6, D); our sphere is lit less
  evenly on the top and picks up a bluer sky; overall contrast std 0.18 vs 0.20.
- Stone edges look slightly crisper than in the video (where the viewport / render-region denoising also softens
  them); not traced further.
- UV mode uses 4D cells: the baked tile is not the video's field. After CB16 its stone coverage, stone count and
  sizes match object mode (48.6 % vs 48.9 %, area-weighted median 12.6 cm both); the 4D cells are slightly more
  polygonal and their size spread is a little wider (p10 3.9 vs 5.0 cm). The match is calibrated at the defaults:
  at Individual Size 0.4 / 0.8 UV mode keeps a few points more stone than object mode.
- Stone shape vs the product render: the product's stones are domed with rounded shoulders; ours (and the tutorial
  build at 26:08) are flatter plates with a steeper edge from the 0.035-wide cell ramp. Product internals unknown
  (CB13); not changed (audit CB-6).

## Not checked

- The final render sample count of the video (D) and a pixel-exact match; we compare looks and statistics.
- Godot import of the baked tiles (nothing is applied to the game, D10).
- A height-map bake: `Height` peaks at 0.0064 m, which an 8-bit emission bake cannot hold; a float / normalised
  export is left to the Godot mapping step.
- Performance (18 texture nodes in object mode because of the 3D / 4D twins) on large road scenes.
- Non-default control values beyond Individual Size (each is the tutorial's own socket; ranges are the video's).

## 6. Independent audit (2026-10-30)

Adversarial re-check of every claim above, headless, one Blender at a time. Scripts in `scripts/` (`verify_graph.py`,
`measure_bakes.py` + `analyse.py`, `uv_probe.py`, `uv_match_sweep.py`, `render_modes.py`), numbers in `checks/`.

**Graph fidelity** (`scripts/verify_graph.py` -> `checks/verify_graph.json`): every one of GRAPH_SPEC_b's 91 links
exists in the built group (seen through the coordinate block and the `object 3D | UV 4D` mixes, following the 3D twin =
object mode): **91 / 91**. All 39 spec nodes exist with the spec's type, settings (dimensions 3D, feature, metric,
normalize, noise type, blend / data type, clamp flags, space, ramp mode / interpolation) and constant input values
(Lacunarity 2 / 3, Roughness 0.5 / 0.8, Detail 10, Scale 20 / 12 / 17, bump Distances 0.02 / 0.005 / 0.007 / 0.015 /
0.01, Filter Width 0.1, Hue 0.5, Saturation 1, Midlevel 0, Metallic 0, IOR 1.5, Alpha 1). Interface: 36 inputs with
the spec's names, order, panels, defaults, ranges, subtypes and linear colours; outputs BSDF / Albedo / Displacement /
Height. Deviations found: the six ramp stops of spec a vs spec b (CB3), the Mapping node replaced by the core multiply
(CB4) and the UV-mode 4D smoothness gain (CB16): all documented. The 4D twins otherwise carry the same inputs as the 3D
nodes. Extra nodes: 20 coordinate nodes, 9 + 1 Use UV mixes, `mapping_scale`, `albedo_rock`, `albedo`, `height`, the
CB16 nodes.

**Contract**: exactly one group node `MRS` (label `PM_Cobblestone`), inputs Use UV / Tile Size, outputs BSDF + Albedo
(+ Displacement, Height); Material Output Surface <- MRS.BSDF, Displacement <- MRS.Displacement; methods BUMP / BOTH.
Object mode in metres (`checks/metres_check.json`): a 1 m plane equals the centre metre of a 4 m plane (albedo mad
0.0021, corr 0.993; stone mask corr 0.999; median stone 10.2 cm on both).

**Real-world scale** (stone mask bakes, `checks/uv_mode_match.json`): object mode 50 whole stones / m2, equivalent
diameter median 10.2 cm (p10 5.0, p90 14.8), area-weighted median 12.6 cm, 78 % of the stone area in 10-25 cm; stones
cover 49 % of the ground (the tutorial's wide dirt joints). Eye level (`comparisons/eye_object_uv_baked.jpg`,
`near_object_vs_uv.jpg`, Cycles, courtyard HDRI + sun): reads as small rounded cobbles at 1-3 m, a fine stone texture
by 10 m. Within the 10-25 cm target at its lower end; defaults unchanged (CB5).

**Defects found**

| id | severity | defect | evidence | status |
|---|---|---|---|---|
| CB-1 | medium | UV mode (the baked tiles, i.e. the game path) had far fewer / smaller stones than object mode: stone coverage 36.3 % vs 48.9 %, median 8.9 vs 10.2 cm, rounder stones in wider dirt. Cause: a 2D slice of 4D Voronoi cells has more neighbours at similar distances, so the same Smooth F1 smoothness eats more of each stone (4D distance std 0.83-0.88x the 3D one). | `comparisons/uv_mode_stone_mask_before_after.jpg` (left / middle), `checks/uv_mode_match.json` | fixed (CB16): 4D Smoothness = Individual Size x 0.82 -> 48.6 % coverage, area-weighted median 12.6 cm (= object mode), 54 vs 50 stones / m2 |
| CB-2 | low | UV mode rock bump weaker: the 4D rock Voronoi Distance std is 0.71x the 3D one; stone-top normal std 0.0475 vs 0.0564 | `checks/uv_mode_match.json` | fixed (CB16): 4D Distance x 1.41 -> 0.0579 |
| CB-3 | low | viewport colour / roughness (glTF fallback) are bake means and changed with CB-1 | `checks/bake_seam.json` | updated: (0.0200, 0.0200, 0.0139), 0.72 (CB15) |
| CB-4 | low | `cobblestone.py` docstring cited CB3 for the BUMP road material (it is CB1) | source | fixed |
| CB-5 | low | evidence standard: no `checks/` numbers, no graph verifier, comparisons as 1-2 MB PNGs | folder listing | `checks/` and the scripts added; new comparisons are JPEG; old PNGs kept |
| CB-6 | low | stone shape vs the product render (domed stones there, flatter plates here) | `comparisons/t0004_vs_ours_zoom_lower_centre.png` | not changed: the product file's internals are not shown, the tutorial build matches (CB13) |

Not defects (claims confirmed): object mode reproduces the video's stone layout (looked at
`t0004_vs_stone_mask_front_view.png`, `t2608_vs_ours_aligned.png`: same stones); colour and contrast differences in
`t0004_vs_ours_sphere.png` are dominated by lighting (warm even fill in the video vs the courtyard sky; D6); the six
noises have the same distribution in both modes (std ratio 0.98-1.09, `uv_probe.py`).

**After the fix** (inspected): `comparisons/uv_mode_stone_mask_before_after.jpg` (UV mask now as full as object mode),
`near_object_vs_uv.jpg` (same stone size, joint width and relief at 1-3 m), `eye_object_uv_baked.jpg` (object mode,
UV mode and the baked 4 m tile on an image material look alike at eye level). Object mode is unchanged (only 4D-twin inputs changed): object-mode
bakes before / after differ by at most 1/255 on a handful of pixels (mean 1e-6). Seam: section 4.
