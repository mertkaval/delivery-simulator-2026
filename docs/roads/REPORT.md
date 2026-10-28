# Mert Road Studio — completion report (2026-10-28)

Source: `tools/roads/mert_road_studio.py` (879 lines, one file, no external add-ons).
Manual: `tools/roads/README.md`. Demo scene: `tools/roads/mert_road_studio_demo.blend` (253 KB, road
scene only; the 156 MB file in commit bf49246 was replaced in 6f9227d). Export:
`assets/roads/mrs_demo.glb` + `assets/roads/mrs_demo_collision.glb`. Godot capture:
`tests/capture_roads.gd`. Screenshots: `docs/roads/validation_{blender,closeups,godot}.png`.

## What was built (all verified by running it)

Geometry Nodes group `MRS_Road` (framed sections Road_Profile, Road_Rail, Road_Surface,
Sidewalks_Curbs, Road_Markings, Roadside_Instances, Road_Materials) applied as a modifier to any
curve object. 32 live inputs: lanes, lane width, shoulder, median, sidewalk on/off + width per side,
sidewalk height, curb width, resolution, centre/lane/edge line modes, marking width, dash length and
gap, three material slots, trim start/end, prop collection, spacing, offset, side, seed, clearance,
manhole collection and spacing, realize instances, collision-only.

Shader groups `MRS_AsphaltShader`, `MRS_PaintShader`, `MRS_ConcreteShader`: object-space metre
coordinates, aggregate + grain bump, repair patches, paint wear showing the aggregate through,
concrete slab joints, wetness with puddles. Exposed controls: Asphalt Scale / Roughness, Color
Variation, Patch Amount, Wetness, Paint Wear, Concrete Variation, Bump Strength. Presets dry / wet.

Junctions (`build_junction`): explicit mesh for 2-, 3- and 4-way meetings; the approach roads are
trimmed to the computed corners, props cleared 7 m from the junction, zebra crosswalks on every
approach, stop line on the incoming half. Unsupported layouts raise an error instead of a fake
junction (more than 4 roads, neighbour angle < 50°, end heights differing by more than 5 cm).

UI: N-panel "Road Studio" with Add Road, preset buttons (residential / urban / service), material
presets (dry / wet), Connect Roads at Cursor, Export GLB. Python API: `make_road`, `set_road`,
`build_junction`, `apply_material_preset`, `export_glb`, `demo_scene`.

Export: evaluated meshes, metre UVs, +Y up, and a separate collision GLB with only the asphalt and
concrete surfaces. In Godot `CityForgeMaterials.apply()` maps `MRS_Asphalt` / `MRS_Paint` /
`MRS_Concrete` to the game's road, paint and paving materials.

## Validation results

Blender (`docs/roads/validation_blender.png`, `validation_closeups.png`): demo scene with a 4-lane
urban avenue, residential streets, a service road, an S-curve with one sidewalk, a tight bend
without sidewalks, a 4-way and a T junction; dry and wet curb close-ups. Parameter check on the
avenue: urban preset 22.4 m wide → 6 lanes 29.4 m → left sidewalk off 19.4 m → urban 22.4 m again
(mesh updates live, deterministic).

Godot (`docs/roads/validation_godot.png`, headless capture): visual bounds 298 × 8.2 × 182 m
(matches the Blender scene), 10 mesh surfaces, the three MRS materials present and remapped,
collision 11,899 triangles, a ray dropped onto the avenue hits at y = 0.000002 m. Suites after the
material change: CITYFORGE 19/19, PORT HALDEN GAME 18/18, ASSET BUDGET 5/5.

## Reference products — observed vs. inferred vs. proposed

- **City Road Maker (Superhive)**: observed from the product page only — curve-driven roads,
  "280+ settings", connect roads, props along the road. No documentation or files were read (the
  download is behind an email form; not downloaded). Features inferred from that page and
  implemented here: curve roads, lanes/sidewalks/markings parameters, junction connection, roadside
  instancing, presets. Not inferred or verified: how it builds junction geometry or its material set.
- **REA (road editor)**: binaries / Electron only, no source or docs readable — nothing was taken
  from it. The YouTube tutorial's transcript was not available.
- Everything in `mert_road_studio.py` was written from scratch against those feature lists.

## Not implemented (do not treat as done)

- Rounded curb radii at junction corners (corners are straight chamfers), sloped junctions, lane
  tapers, roundabouts, slip lanes, roads joining mid-curve, turn arrows, traffic signals.
- The Blender asphalt / paint / concrete shaders are **not baked to textures**; in Godot the game's
  existing materials are used instead. (The CityForge surface shader shows its own dark repair
  patches on the asphalt — visible in `validation_godot.png` — which is the game material, not
  Road Studio's.)
- Props are placeholder meshes (streetlight, bollard, barrier, tree, sign, bench, manhole).
- Traffic lanes for the AI are not derived from these roads; the demo GLB is not placed in Port
  Halden — it is a validation asset.
