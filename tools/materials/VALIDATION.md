# procmat validation: road tool integration, seamless bakes, library file

Date 2026-10-30, Blender 5.2.3 LTS, headless only (one Blender process at a time; the user's Blender and Godot editor
were not touched). Nothing under `tools/roads/`, `app/`, `actors/`, `systems/`, `world/`, `assets/`, `tests/` changed;
`tmp/roads/city/base.blend` was opened and never saved (D10). Every image cited below was opened and looked at.

## Summary

| material | comparison with the video | seam metric (UV mode, 4 m, 1024 px) | audit | open differences |
|---|---|---|---|---|
| PM_Asphalt, PM_AsphaltTutorial ([details](reconstruction/asphalt/VALIDATION.md)) | Same look, scale and statistics in the video's scene (relief, cracks, damaged patches with pebbles, colour range, roughness). The video's exact patches are not reproduced: the view search found best corr 0.21-0.28 against 0.00 +- 0.05 for random views (control 0.63), class D. The literal twin and PM_Asphalt agree within 4/255. | albedo ratio 0.976 (x 0.92 / y 1.03), outlier 0.67; normal 0.973-0.976; roughness 1.001; periodicity OK (mad 0.0011, corr 0.9975) | 5 defects. Fixed: ASP-1 (UV-mode 4D twins remapped to the 3D distributions, AS17), ASP-2 documentation (damage spread measured over 24 views, AS18). Not changed: Damage Amount (video 0.041 vs ours 0.030 +- 0.013, z +0.8, within the spread). | exact patch positions (Blender 3.2 vs 5.2 textures or sphere scale, D); warmer video fill light (no machine_shop_02 HDRI, D6; emitters fitted); higher pixel-level contrast in the video (0.50-0.52 vs 0.33-0.37, < 1.5 px band; mid band matches); Principled v2 grazing brightness not separable from lighting; video view shows somewhat more / darker damage in one view; the 25:10 close-up is a denoised 10-sample viewport |
| PM_Cobblestone, PM_CobblestoneDisplaced ([details](reconstruction/cobblestone/VALIDATION.md)) | Object mode reproduces the video's own stone layout (camera search corr 0.545 at the front view vs <= 0.135 elsewhere). Mean colour within 0.03 per channel; luminance std 0.179 vs 0.202. Default stone fill matches the tutorial build at 26:08. Graph: 91 / 91 spec links, all nodes / settings / constants / 36 inputs match (deviations documented: CB3, CB4, CB16). Stones: median 10.2 cm, area-weighted 12.6 cm, 49 % stone cover. | albedo ratio 1.094 (x 1.14 / y 1.05), outliers 0.78 / 0.79; normal 1.003; roughness 1.25 (outliers 0.66 / 0.79); periodicity OK (mad 0.0010, corr 0.9977); 2 x 2 preview: no seam; Displaced identical | 6 defects. Fixed: CB-1 (medium: UV mode / baked tile had 36 % stone cover vs 49 % in object mode; 4D smoothness x 0.82, now 48.6 %, CB16), CB-2 (UV rock bump 0.84x; 4D rock distance x 1.41), CB-3 viewport colour re-measured, CB-4 docstring, CB-5 checks / scripts added. Not changed: CB-6 product-render stone shape (CB13). | the product render (0:04 = 40:16) has fuller, domed stones / narrower joints (Individual Size about 0.5 comes close; defaults kept, CB13); lighting (unknown sun / rim, courtyard HDRI instead of fish_hoek_beach): bluer sky, slightly lower contrast; stone edges slightly crisper; UV mode uses 4D cells (statistics matched by CB16 at the defaults, slightly more polygonal, not the video's field) |
| PM_Glass* (Circles, Voronoi, Cells, Wavy, Blobby, Frosted) ([details](reconstruction/glass/VALIDATION.md)) | Pattern type, size, relief and frosting match for all six; dominant wavelength equal to the video's within one spectrum bin (Circles, Voronoi, Cells, Wavy, Blobby); Voronoi / Cells / Blobby show the video's own cells (layout correlation peaks at zero shift). | normal ratio 0.97-1.07 (outliers 0.71-0.91), albedo constant tint; roughness 0.98-0.99 where it varies; normal periodicity OK (corr >= 0.9999); roughness periodicity corr 0.80-0.81 for Cells / Blobby / Frosted (mad 0.0026-0.0031: 8-bit quantisation, not a seam) | 8 defects. Fixed: GL-1 (Wavy orientation relative to the surface, G18), GL-2 (variance-preserving Wavy UV cross-fade, G17). Not changed: GL-3 Blobby relief (literal video graph renders pixel-identically; contrast ratio depends on the backdrop, G19). | backdrop brightness / colour and Suzanne redness (no old_apartments_walkway HDRI, D6; placement D); Blobby relief contrast about 0.6x the video's (lighting suspected, unproven); fine Voronoi crinkle visible only under the city HDRI; Circles cell layout not checked; Frosted dominant wavelength 0.156 vs 0.112 on a very low-contrast mottle; Wavy orientation is a fitted class C value; Wavy UV cross-fade slightly softens the streaks in 15 % of the tile; EEVEE look not compared (video Cycles only) |

Integration: `ROAD_INTEGRATION OK` (14 / 14 checks, section 1). Library file: `procedural_materials.blend`, 1.64 MB,
10 materials, 9 groups (section 3). Known tool issues: section "Issues" below.

## 1. Road tool integration (`tests/road_integration.py`)

```
blender --background tmp/roads/city/base.blend --python tools/materials/tests/road_integration.py -- tmp/materials_road
```

Result: **ROAD_INTEGRATION OK** (14 / 14 checks; log `tmp/materials_road/run.log`, measurements
`tmp/materials_road/road_integration.json`). Street block build 201 s, whole run about 5 min.

What it does:

1. The road tool's own sample code builds the scene: `mrs.samples.street_block()` (avenue with protected cycleways
   and a footbridge, residential streets, a signalised 4-way and a T junction, sidewalks, placement v4 with two
   furnished bus stops). The road tool is imported read-only (`sys.dont_write_bytecode`), not modified.
2. `procmat.build_all()` builds the 10 materials in that file; all pass `core.check_contract`.
3. `road_adapter.assign_roads(col, {"Asphalt Material": PM_Asphalt, "Paving Material": PM_Cobblestone})` on the 6
   roads (12 assignments, menus Asphalt Condition / Sidewalk Surface -> Default), then the cobbled variant:
   `road_adapter.assign(SB_TSide, "Asphalt Material", PM_Cobblestone)`.
4. Junction meshes (`SB_J4`, `SB_JT`) are plain meshes with `MRS_*` slots (no modifier input):
   `replace_slot_materials(j, "MRS_Asphalt" / "MRS_Paving", ..., per_object=True)`.
5. The placed bus shelters (`SB_South_bus_shelter_r0`, `SB_North_bus_shelter_l0`, mesh shared with the furniture
   library `MRS_F_BusShelter`) get `PM_GlassFrosted` on slot 1 (`MRS_FurnitureGlass`) per object; the library mesh
   keeps `MRS_FurnitureGlass`.

Checks on the **evaluated** meshes (face counts of what renders):

| object | evaluated PM materials (faces) |
|---|---|
| SB_AvenueW / SB_AvenueE | PM_Asphalt 540 / 360, PM_Cobblestone 432 / 288 (no MRS_Asphalt* / MRS_Paving* left) |
| SB_North, SB_South, SB_SCurve | PM_Asphalt + PM_Cobblestone on every one |
| SB_TSide (cobbled variant) | PM_Cobblestone on carriageway and sidewalks, PM_Asphalt 0 |
| SB_J4 / SB_JT | PM_Asphalt 42 / 23, PM_Cobblestone 80 / 44 |
| both shelters | PM_GlassFrosted 24 (glass panels), MRS_FurnitureAtlas 638 |

Markings, curbs (Concrete), cycleways, tactile, embankment keep the road tool's MRS_* materials (not assigned).

Renders (EEVEE, the road tool's day lighting, 1280 x 720, 48 samples), all in `tools/materials/renders/`:

| render | what it shows (inspected) |
|---|---|
| `road_eye_busstop.png` | SB_South at eye level: PM_Asphalt carriageway with aggregate and dark patches, PM_Cobblestone sidewalk on the right reads as stones, shelter in the distance |
| `road_45_busstop.png` | 45 degree view of the bus stop: shelter on the cobbled sidewalk, PM_Asphalt bus-stop lane with the road tool's markings |
| `road_glass_closeup.png` | the shelter's PM_GlassFrosted panels: frosted, blurred park behind, poster / timetable unchanged; cobblestones on the floor clearly readable |
| `road_eye_cobbled.png` | SB_TSide with PM_Cobblestone as Asphalt Material: cobbled carriageway with lane markings on top, cobbled sidewalks, MRS curbs |
| `road_45_cobbled.png` | the same road from above: uniform stone pattern at the same scale on carriageway and sidewalks (object-space metres) |
| `road_eye_avenue.png` | SB_AvenueW at eye level: PM_Asphalt over a wide carriageway, footbridge, MRS median and red cycleways |
| `library_preview_scene.png` | the saved library's own preview scene (section 3) |

## 2. Seamless bakes (UV mode, 4 m tile, 1024 px, 16 samples)

```
blender --background --factory-startup --python tools/materials/run.py -- build all --bake tmp/materials_bake/all --tile 4.0 --bake-res 1024 --bake-samples 16 --periodicity
```

Output `tmp/materials_bake/all/` (albedo / normal / roughness PNG + `_x2` 2 x 2 previews; contact sheets
`sheet_ground.png`, `sheet_glass.png`, `sheet_glass_normals_stretched.png`). Seam metric = wrap-around edge
difference / neighbouring-pixel difference (1.0 = no seam; `is_seamless`: outlier <= 1.15, ratio 0.6-1.7).
Periodicity = a bake with UVs shifted by (0.5, 0.25) equals the rolled tile (mad <= 0.012, corr >= 0.97).

| material | albedo ratio (x / y), outlier | normal ratio, outlier | roughness ratio | periodicity |
|---|---|---|---|---|
| PM_Asphalt | 0.98 (0.92 / 1.03), 0.67 | 0.97, 0.86 | 1.00 | OK albedo mad 0.0011 corr 0.9975 |
| PM_AsphaltTutorial | 0.98 (0.92 / 1.03), 0.67 | 0.98, 0.86 | 1.00 | OK albedo mad 0.0011 corr 0.9975 |
| PM_Cobblestone | 1.09 (1.14 / 1.05), 0.79 | 1.00, 0.86 | 1.25 | OK albedo mad 0.0010 corr 0.9977 (after audit CB16) |
| PM_CobblestoneDisplaced | same as PM_Cobblestone (displacement bakes into the normal map) | | | OK |
| PM_GlassCircles | constant (tint) | 1.01, 0.91 | constant | OK normal mad 0.0005 corr 0.99998 |
| PM_GlassVoronoi | constant | 0.99, 0.84 | constant | OK normal mad 0.0019 corr 0.9999 |
| PM_GlassCells | constant | 1.07, 0.90 | 0.99 | normal OK (corr 0.99996); roughness corr 0.80, mad 0.0027 |
| PM_GlassWavy | constant | 0.97, 0.71 | constant | OK normal mad 0.0001 corr 0.99999 |
| PM_GlassBlobby | constant | 1.01, 0.93 | 0.99 | normal OK (corr 0.99998); roughness corr 0.81, mad 0.0031 |
| PM_GlassFrosted | constant | constant (flat) | 0.98 | roughness corr 0.80, mad 0.0026 |

The 2 x 2 previews show no visible seam for any map. The glass periodicity on normal / roughness ran in a second pass
(`tmp/materials_bake/all/glass_period.log`), since the glass albedo is a constant tint.

## 3. Library file

```
blender --background --factory-startup --python tools/materials/run.py -- build all --save tools/materials/procedural_materials.blend --scene --assets
```

`tools/materials/procedural_materials.blend`: 1.64 MB (compressed). Contents (checked by opening it): 10 materials
`PM_*` (marked as assets, tag `procmat`, fake users), 9 node groups `PM_*` (the two cobblestone materials share
`PM_Cobblestone`), scene `PM_Library` with collection `PM_Library_Objects`: one object `PMV_<Name>` per material (1 m
icospheres, 1.6 x 2 m panes for glass, the displaced cobblestone on a plane with a Simple subdivision modifier), camera
`PMV_Camera`, world `PM_World_city` (bundled `city.exr`, absolute path, not packed). No packed images, no lights, no
`MRS_*` data, no factory Cube / Light / Material. `run.py` gained `--scene` for this (and saves with
`relative_remap=False` so the HDRI path survives; the factory leftovers are removed).

## Issues

1. `run.py build all --periodicity` prints RUN FAIL: for the six glass materials it tests the albedo, which is a
   constant tint (corr NaN). The test needs a varying map (normal for Circles / Voronoi / Cells / Wavy / Blobby,
   roughness for Frosted); run with those maps it passes on every normal map.
2. Glass roughness maps (Cells, Blobby, Frosted) fail the periodicity correlation (0.80) although mad is 0.0026-0.0031,
   below one 8-bit level: the maps have std 0.006-0.0075 (16-19 grey levels), so 8-bit quantisation dominates the
   correlation. Seam metric 0.98-0.99. Not a seam; a 16-bit roughness bake would make this test conclusive.
3. Glass baked at a 4 m tile / 1024 px (3.9 mm per pixel) under-resolves the glass patterns (normals nearly flat in
   8 bit; PM_GlassFrosted's normal is fully flat). Glass needs a smaller tile (about 0.5-1 m) for a game bake.
4. Cobblestone seam ratios: after the audit fix CB16 albedo ratio_x 1.14 (first build 1.23) and roughness 1.22 / 1.29 (first build x 1.37); outliers 0.66-0.79 stay under 1.15 and the direct periodicity test passes: the roughness map is two-level
   (stone 0.65 / dirt 0.64-1), so a joint line near a tile edge raises the ratio. No seam visible in the 2 x 2
   previews (`reconstruction/cobblestone/comparisons/bake_2x2_albedo_roughness.jpg`).
5. Cobblestone albedo is dark (mean sRGB about 0.15 / 0.15 / 0.12 after CB16 vs asphalt 0.18): from 15 m+ (`road_45_busstop.png`) the
   cobbled sidewalk reads almost as dark as the asphalt.
6. `road_adapter` has no helper for junctions: junction meshes carry MRS_* slots, not modifier inputs, so the test
   uses `replace_slot_materials` per object. Surfaces outside the road sockets (bus-stop pads, park paths, ground)
   keep the road tool's materials. The road tool's `set_road()` / `refresh_all()` / junction rebuilds reset the
   assignments (`reapply()` restores road sockets, not junction slots).
7. Bus shelter glass uses `per_object=True`: the shelters share the furniture library mesh; a mesh-level replacement
   would change every shelter in the file.
8. The road tool's glTF export writes PM_* materials as flat Principled (viewport colour); the baked PM tiles are not
   wired into the Godot export yet (D10: nothing applied to the game).
