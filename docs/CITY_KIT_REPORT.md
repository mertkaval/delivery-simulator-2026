# City kit, layout, people and VFX — 13 October 2026

![City layout](city_map.png)

## Evaluation (before)

| Area | Finding |
|---|---|
| Suburban houses | Higgsfield exteriors hold up close; kept. Blocks were sparse: the inner side of both side roads and the four estate lots (white boxes) were empty or placeholder. |
| Downtown | Bays read well at street level but party walls were flat grey, roofs featureless, towers grey slabs; flat colour materials. |
| Lighting | Flat colour ambient, no sky reflections, heavy haze: glass and materials looked dull. |
| People | Six near-identical bodies, tight "hair caps", tiny facial features, stiff clips. |

## What was built

**Lighting.** Sky-based ambient and reflections, AgX tonemapping, SSIL, softer 4-split sun shadows (170 m), subtle glow, aerial-perspective fog, warm golden-hour sun and faint blue moonlight at night (`world/neighborhood.gd`).

**Material library** (`world/citykit/build_materials.py`). Ten seamless PBR sets baked with Cycles from procedural node networks: red, buff and charcoal brick, stucco, precast concrete, limestone panels, standing-seam metal, gravel roof, slate and cedar boards. 1024² albedo, roughness and OpenGL normal maps. Noise is sampled on a 4D torus, so every map tiles without seams. Imports use VRAM compression with mipmaps (`set_import_flags.py`).

**Modular kit** (`world/citykit/build_kit.py`, 52 modules, each with a hand-built far LOD):
- **Downtown contract** (drop-in for `world/downtown/assets`): apartment and office bays, storefronts and open-door entrances in three styles (warehouse brick, civic limestone, contemporary charcoal/curtain wall), party wall, roof and lobby slabs, parapet, balcony, canopy and awning.
- **Residential:** walk-up ground floors and lobby entrances, cornices, wall strips, and a townhouse set on a 5 m unit (ground with front steps and door, upper floor, pitched roof with or without dormer, gable, chimney) in Georgian brick, Victorian stucco (canted bay windows) and modern timber (flat roof).
- **Asset quality:** planar metre-scale UVs, ambient occlusion baked per face corner to vertex colour (bake isolated from the rest of the scene), one mesh per material, 4–358 triangles per near module. Godot maps `Kit*` materials to world-triplanar PBR (`world/citykit/city_kit.gd`), so brick courses run continuously across modules.

**Buildings and layout** (`city_layout.gd`, `kit_builder.gd`). The layout follows an urban transect:
- **Suburb core:** existing houses.
- **14 terrace rows (79 homes):** on the inner side of the side roads, with 1.5 m front gardens, clear of parks and junctions.
- **4 walk-up apartments:** replace the old estate blocks on the same frontage.
- **16 mixed-use corridor buildings:** shops with flats or offices above, along the four downtown connectors.
- **Downtown:** all 87 buildings now use the kit.
- **Civic campus:** unchanged.

Each kit building is merged into one mesh per LOD with one surface per material, and has a single box collider and an occluder. Grass avoids every footprint. All buildings are scenery: doors are closed, and every delivery destination is unchanged.

**People** (`world/living_city/build_people.py`, headless Blender only). Twelve designed citizens, 1.58–1.86 m tall, with male and female builds, six skin tones, 11 hairstyles (with real hairlines), beards, glasses, headphones and bags. Clothing includes hoodies, puffers, long coats, blazers, shirts, t-shirts with bare forearms, skirts, jeans and leggings, and sneakers or boots. The rig and clip contract is unchanged (14 bones, 8 clips, 3 LODs). New procedural animation adds pelvis twist and hip drop, shoulder counter-rotation, knee flex in the swing phase, elbow swing, a steady gaze, breathing and weight shift in idle, look-around in Wait, and gestures in Talk. Each person uses at most 7 materials, since skinned meshes can't batch. The originals are backed up in `tmp/citizens_v1/`.

**VFX** (`world/vfx/city_vfx.gd`):
- Water jets and splash mist at eight park fountains.
- Steam from downtown alley manholes and restaurant kitchen vents.
- Chimney smoke on terrace stacks (stronger in the morning and evening).
- Four bird flocks with flapping wings (one MultiMesh).
- Night lamp halos for every street, porch and downtown lamp (one billboarded MultiMesh).
- Night windows: about a third of rooms lit, in warm, cool and dim tones, with furniture silhouettes.

## Performance (RTX 3070 Laptop, Forward+, 1280×720, VSync off)

| View | Median ms | p95 ms | Draw calls |
|---|---:|---:|---:|
| House close | 2.75 | 4.69 | 403 |
| Residential street | 6.56 | 7.69 | 2,480 |
| Side street | 6.36 | 7.48 | 2,016 |
| Downtown street | 6.67 | 8.03 | 2,088 |
| Downtown facades | 6.09 | 7.38 | 1,366 |
| Towers aerial | 6.45 | 7.83 | 1,513 |
| Civic | 3.06 | 5.01 | 226 |
| People (downtown sidewalk) | 8.20 | 10.25 | 2,396 |
| City aerial | 5.54 | 7.25 | 1,389 |

Texture memory is 306 MiB (270 MiB before the kit, which adds 30 maps). Downtown primitives fell by about half: the facades view went from 854k to 430k. These are short warm measurements, not a frame-rate guarantee. Reproduce them with `tests/capture_evaluation.gd -- <prefix>`.

## Rebuild

```
blender --background --python world/citykit/build_materials.py
python -I world/citykit/set_import_flags.py world/citykit/textures
blender --background --python world/citykit/build_kit.py
blender --background --factory-startup --python world/living_city/build_people.py
godot --headless --path . --import
```

`build_materials.py` and `build_kit.py` also run inside a live Blender session through the Blender MCP. They build in their own collections and never clear the user's scene. `build_people.py` must run headless, because the shared helper's `clear()` empties the scene.

## Verification

All 13 suites in `tests/run_tests.ps1` and the extended suites pass, including `citykit_test.gd` (3,515 checks). That test covers:
- no overlaps between kit buildings, roads, sidewalks, parks, doors and pickups
- every module present with its far LOD
- the twelve citizens' rigs, clips, LODs and material budget
- collision on every building and on the facades
- VFX behaviour by time of day

Captures: `tests/capture_citykit.gd`, `capture_people.gd`, `capture_map.gd` and `capture_evaluation.gd`, all writing to `tmp/`.

## Limits

This is stylised, procedural game art, not photorealism:
- **Faces:** modelled shapes without texture maps.
- **Animation:** hand-keyed procedural cycles, not motion capture, with no foot IK.
- **Kit buildings:** exterior only.
- **Suburb:** the Higgsfield houses remain, and no detached kit houses replace them.
- **Weather:** none (rain, snow and wet surfaces).
- **Draw calls:** dense residential views still reach about 2,500.
