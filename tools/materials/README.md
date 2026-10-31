# procmat - procedural material library (Blender 5.2)

`procmat` is a library of procedural Blender materials, each rebuilt node for node from a Ryan King Art YouTube
tutorial (asphalt, cobblestone ground, textured / frosted glass) and adapted to Blender 5.2.3 LTS. It lives in
`tools/materials/` (Python package `procmat`) and is **separate from the road tool** (Mert Road Studio,
`tools/roads/mrs`): it imports nothing from it (decision D1). It does follow the road tool's material contract, so
every material plugs into a road's material sockets. **Nothing is applied to the game** (D10): the materials live in
Blender files and test scenes only. A later Godot import would use baked tiles (see [Bake](#bake-for-a-later-game-import)).

Binding decisions: [DECISIONS.md](DECISIONS.md) (D1-D11, followed by every decision taken during the
reconstruction). Validation summary: [VALIDATION.md](VALIDATION.md). Python API: [procmat/API.md](procmat/API.md).

![library preview](renders/library_preview_scene.png)

## The contract (every material)

A material `PM_<Name>` holds one shader group node named `MRS` (label = the group `PM_<Name>`), whose `BSDF` output
feeds Material Output > Surface. Every group has the inputs **Use UV** (0 = object space in metres, 1 = `UVMap` x
Tile Size sampled on a flat 4D torus: repeats exactly every Tile Size, bakes to seamless tiles) and **Tile Size**
(m, default 4) in a closed panel "Mapping", plus the outputs `BSDF` and `Albedo` (and `Displacement` / `Height` for
cobblestone). One size control in metres per material (D4). Textures that are 3D in a video have a 3D twin for
object mode (the video's exact field) and a 4D twin for UV mode (seamless).

## Materials

Evidence class of each default: **A** read in a video frame, **B** narration only, **C** our implementation /
inference, **D** unresolved. Full control lists are in each material's README.

| material | node group | video | what it is for |
|---|---|---|---|
| `PM_Asphalt` | `PM_Asphalt` | [asphalt](reconstruction/asphalt/README.md) `Eofg9SBcdBY` (Blender 3.2) | road surface: mottled worn asphalt, cracks, broken patches with pebbles; bump only |
| `PM_AsphaltTutorial` | `PM_AsphaltTutorial` | same | the video's literal graph (ColorRamps, constants), the reference PM_Asphalt is checked against |
| `PM_Cobblestone` | `PM_Cobblestone` | [cobblestone](reconstruction/cobblestone/README.md) `30vbbpy9zwg` (Blender 5.0.1) | sidewalks, plazas, cobbled streets; relief as bump (`displacement_method` BUMP) |
| `PM_CobblestoneDisplaced` | `PM_Cobblestone` (shared) | same | dense meshes: "Displacement and Bump" as in the video |
| `PM_GlassCircles` | `PM_GlassCircles` | [glass](reconstruction/glass/README.md) `SNKNqHd0AYI` (Blender 5.1.1) | round 2 cm dimples (bathroom glass) |
| `PM_GlassVoronoi` | `PM_GlassVoronoi` | same | clear hammered glass |
| `PM_GlassCells` | `PM_GlassCells` | same | faceted crystal plates, patchy frost |
| `PM_GlassWavy` | `PM_GlassWavy` | same | reeded / fluted glass, vertical 2.1 cm streaks on any pane |
| `PM_GlassBlobby` | `PM_GlassBlobby` | same | crinkled 10 cm blobs, speckled frost |
| `PM_GlassFrosted` | `PM_GlassFrosted` | same | satin frosted glass (bus shelters) |

10 materials, 9 node groups.

### Main controls

| group | control | default | range | class |
|---|---|---|---|---|
| all | Use UV (Mapping) | 0 | 0..1 | C (contract D2) |
| all | Tile Size (Mapping) | 4.0 m | 0.05..1000 | C (contract D2) |
| PM_Asphalt | Pattern Size | 1.0 m | 0.05..100 | C (D4; video sphere radius 1 m assumed) |
| PM_Asphalt | Aggregate Size | 0.00909 m (1/110) | 0.001..0.2 | A value (Scale 110), C mapping |
| PM_Asphalt | Color Dark / Color Light | #1A1817 / #4D4D4D | colour | A |
| PM_Asphalt | Crack Amount | 0.499 | 0..1 | A |
| PM_Asphalt | Crack Width | 0.094 | 0..1 | A |
| PM_Asphalt | Damage Amount | 0.35 | 0..1 | C (0.343 / 0.350 readings, AS6) |
| PM_Asphalt | Damage Darkness | 0.338 | 0..1 | A |
| PM_Asphalt | Roughness Min | 0.4072 | 0..1 | A |
| PM_Asphalt | Bump Grain / Cells / Cracks / Damage | 0.1 / 0.2 / 0.3 / 0.4 | 0..1 | A |
| PM_Asphalt | Bump Filter Width | 1.0 | 0..10 | C (measured, AS5) |
| PM_AsphaltTutorial | Pattern Size | 1.0 m | 0.05..100 | C (no other controls: literal graph) |
| PM_Cobblestone | Material Scale | 1.0 | -inf..inf | A |
| PM_Cobblestone | Pattern Size | 1.0 m | 0.01..100 | C (D4) |
| PM_Cobblestone | Cobblestone Scale | 7.0 (0.14 m stones) | -1000..1000 | A |
| PM_Cobblestone | Cobblestone Individual Size | 0.6 | 0..1 | A (0.5 is close to the video's product render, CB13) |
| PM_Cobblestone | Cobblestone Alignment | 1.0 | 0..1 | A (lower = aligned rows / setts) |
| PM_Cobblestone | Cobblestone Cracks | 0.0 | 0..15 | A |
| PM_Cobblestone | Distortion Strength | 0.2 | 0..1 | A |
| PM_Cobblestone | Displacement Strength | 0.02 (6.4 mm relief) | 0..1000 | A |
| PM_Cobblestone | Dirt / Rock Moss Visibility | 1.0 / 1.0 | 0..2 | A |
| PM_Cobblestone | Rock Color 1 / 2 | #343534 / #292524 | colour | B+A |
| PM_Cobblestone | Rock Roughness / Dirt Roughness | 0.65 / 1.0 | 0..1 / 0..2 | A |
| PM_Glass* (all six) | Scale | 1 | -inf..inf | A |
| PM_Glass* (all six) | Glass Color | white | colour | A |
| PM_Glass* (all six) | Glass IOR | 1.5 | 0..1000 | A |
| PM_Glass* (all six) | Pattern Size (Mapping) | 1.0 m | 0.01..100 | C (D4, G4) |
| PM_GlassCircles | Glass Roughness / Voronoi Scale / Bump Strength | 0.2 / 50 / 1 | 0..1 / -1000..1000 / 0..1 | A |
| PM_GlassVoronoi | Voronoi Scale 1 / 2, Smoothness 1 / 2 | 30 / 30, 0.1 / 0.03 | -1000..1000, 0..1 | A |
| PM_GlassCells | Glass Roughness (multiplier) / Voronoi Scale | 1 / 30 | 0..2 / -1000..1000 | A |
| PM_GlassWavy | Gabor Frequency / Rotation | 5 / (0, 0, 0) | 0..inf / Euler | A (orientation inside: C, G7 / G18) |
| PM_GlassBlobby | Voronoi Scale / Detail / Glass Roughness | 10 / 2.6 / 1 | -1000..1000 / 0..15 / 0..2 | A |
| PM_GlassFrosted | Frosted Amount / Frosted Scale | 1 / 20 | 0..2 / -1000..1000 | A |

Complete tables (36 cobblestone inputs, every glass input): [asphalt](reconstruction/asphalt/README.md#controls-group-pm_asphalt),
[cobblestone](reconstruction/cobblestone/README.md#controls), [glass](reconstruction/glass/README.md#controls).

## Folder layout

| path | what |
|---|---|
| `procmat/` | the package: `core` (builder, contract, coordinates), `rig` (preview scenes), `bake` (seamless tiles, seam metric, periodicity test), `graphdump` (NODES.md), `road_adapter` (road tool sockets, shelter glass), `imaging` (PNG stats, side-by-side), `asphalt.py`, `cobblestone.py`, `glass.py`, `demo.py` (core self-test material); [API.md](procmat/API.md), [DECISIONS_CORE.md](procmat/DECISIONS_CORE.md) |
| `run.py` | headless CLI: `build <key or all>`, `list` |
| `tests/` | `test_core.py` (core + road stage), `road_integration.py` (full street block with every material) |
| `reconstruction/<key>/` | per material: README, NODES (graph dump), DECISIONS, VALIDATION, the reverse-engineered spec (`GRAPH_SPEC_*`, `OPERATION_LOG_*`, `UNRESOLVED_*`, extraction `DECISIONS_*`), `evidence/` (cited video frames and crops), `renders/`, `comparisons/`, `checks/`, `scripts/` |
| `renders/` | road-tool integration renders and the library preview |
| `procedural_materials.blend` | the saved library: 10 materials (assets, fake users), 9 groups, preview scene `PM_Library` |
| `DECISIONS.md`, `VALIDATION.md` | library decisions and validation summary |

Not here (not committed, `tmp/` is git-ignored): raw video downloads, transcripts, recipe-repository files
(`tmp/materials_video/`), scratch renders, bakes (`tmp/materials_bake/`) and test logs.

## Rebuild from a fresh Blender 5.2

From the repository root (Git Bash). Every command is headless; never use it in the open Blender session.

```
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"

# list the registered materials
"$B" --background --factory-startup --python tools/materials/run.py -- list

# rebuild the library file (what is committed)
"$B" --background --factory-startup --python tools/materials/run.py -- build all \
    --save tools/materials/procedural_materials.blend --scene --assets

# EEVEE previews of one material (sphere and 7 m x 20 m road strip at eye level)
"$B" --background --factory-startup --python tools/materials/run.py -- build asphalt --render tmp/pm_prev --views sphere,road

# seamless UV-mode tiles (albedo / normal / roughness + 2 x 2 previews) with the direct repeat test
"$B" --background --factory-startup --python tools/materials/run.py -- build all \
    --bake tmp/materials_bake/all --tile 4.0 --bake-res 1024 --bake-samples 16 --periodicity

# node documentation
"$B" --background --factory-startup --python tools/materials/run.py -- build glass --dump tmp/pm_dump
```

Keys: `asphalt`, `cobblestone`, `glass` (or `all`). The last line printed is `RUN OK` / `RUN FAIL` (exit code 0 / 1).
Note: `build all --periodicity` currently prints `RUN FAIL` because it tests the glass albedo, a constant tint (see
[VALIDATION.md](VALIDATION.md#issues)); the glass normal / roughness maps pass.

Inside any Blender session (nothing else in the file is touched):

```python
import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/materials")
import procmat
procmat.build_all()                       # every library material; or procmat.build("glass")
procmat.core.set_inputs("PM_Asphalt", **{"Crack Amount": 0.3, "Pattern Size": 1.5})
# or take them from the saved library
procmat.core.append_materials(r"C:/GodotProjects/delivery-simulator-2026/tools/materials/procedural_materials.blend",
                              ["PM_Asphalt", "PM_Cobblestone", "PM_GlassFrosted"])
```

## Use the materials in the road tool (Mert Road Studio)

First bring the materials into the road file: `procmat.build_all()` there, or `core.append_materials(...)` from
`procedural_materials.blend` (or File > Append / the Asset Browser: the materials are marked as assets).

**With Python** (`procmat.road_adapter`, no road-tool import):

```python
from procmat import road_adapter as RA
RA.assign(road_obj, "Asphalt Material", "PM_Asphalt")       # also sets Asphalt Condition -> Default
RA.assign(road_obj, "Paving Material", "PM_Cobblestone")     # also sets Sidewalk Surface -> Default
RA.assign_roads(collection, {"Asphalt Material": "PM_Asphalt", "Paving Material": "PM_Cobblestone"})  # every road
RA.assign_shelter_glass("PM_GlassFrosted", per_object=True)  # bus shelter glass slot, shared library mesh unchanged
RA.replace_slot_materials(junction_obj, "MRS_Asphalt", "PM_Asphalt", per_object=True)    # junction meshes
RA.replace_slot_materials(junction_obj, "MRS_Paving", "PM_Cobblestone", per_object=True)
RA.reapply(collection)                                       # after the road tool's set_road() / refresh_all()
```

**By hand**: select the road object > Properties > Modifiers > **MRS_Road** > set **Asphalt Condition** to
*Default* and pick `PM_Asphalt` in **Asphalt Material**; set **Sidewalk Surface** to *Default* and pick
`PM_Cobblestone` in **Paving Material**. Any other Condition / Surface replaces the socket with a built-in MRS
material. Junctions and shelters: replace the `MRS_Asphalt*` / `MRS_Paving*` / `MRS_FurnitureGlass` slot in the
object's material slots (make it single-user first for the shelters).

Notes:
- Keep **Use UV = 0** on roads (object space in metres, the same texel scale everywhere); scale the look with
  Pattern Size. Use UV = 1 is for baking.
- Use `PM_Cobblestone` (bump), not `PM_CobblestoneDisplaced`, on road meshes: they are too coarse for displacement.
- Glass objects need applied scale (object coordinates = metres). EEVEE needs Raytracing enabled to show refraction.
- The road tool's refreshes reset the sockets: call `reapply()`; it does not restore junction slots.
- The road tool's glTF export writes PM_* materials as a flat Principled from their viewport colour / roughness.
- Proven on the road tool's `street_block` sample: [VALIDATION.md section 1](VALIDATION.md#1-road-tool-integration-testsroad_integrationpy).

## Bake for a later game import

`procmat.bake` writes seamless PNG tiles of any contract material in UV mode (8-bit; albedo, normal, roughness and
metallic when present):

```python
from procmat import bake
paths = bake.bake("PM_Asphalt", r"C:/.../out", tile=4.0, res=1024, samples=16)   # {map: path}
bake.periodicity("PM_Asphalt", r"C:/.../out_period", tile=4.0)                    # direct repeat test
bake.tile_preview(paths["albedo"], n=2)                                           # 2 x 2 repeat to look at seams
```

or `run.py -- build <key> --bake DIR --tile 4.0 --bake-res 1024 --periodicity`. Recommended tiles: asphalt and
cobblestone 4 m; glass 0.5-1 m and 16-bit (its normals are too subtle for a 4 m / 8-bit tile). Transmission is not
baked: a game needs its own glass shader using the maps. Wiring the tiles into Godot is deliberately not done (D10).

## Sources and licences

| source | use | licence / handling |
|---|---|---|
| Ryan King Art, *Procedural Asphalt Material (Blender Tutorial)*, 2022, YouTube `Eofg9SBcdBY` | asphalt | the author's content: raw downloads, transcripts and captions are not committed (`tmp/materials_video/`); only short cited frames / crops as evidence (D7) |
| Ryan King Art, *Procedural Cobblestone Ground Material (Blender Tutorial)*, 2026, YouTube `30vbbpy9zwg` | cobblestone | as above |
| Ryan King Art, *Procedural Textured Frosted Glass Materials (Blender Tutorial)*, 2026, YouTube `SNKNqHd0AYI` | glass | as above |
| KunalMGupta/material-apprentice (MIT) | its asphalt entry (derived from the same asphalt video) cross-checked node types / values (class B); its cobblestone / glass entries only as background | reference only: nothing executed or copied verbatim (D8); not committed |
| Blender bundled studio-light HDRIs (`datafiles/studiolights/world`) | validation lighting | shipped with Blender; referenced by absolute path, not packed; no HDRI downloaded (D6) |

## Tests

| test | command | last line |
|---|---|---|
| core + road stage | `python tools/materials/tests/test_core.py` (starts the two Blender stages one after the other) | `CORE_TEST OK` / `CORE_TEST FAIL` |
| road integration (all materials on the street block) | `"$B" --background tmp/roads/city/base.blend --python tools/materials/tests/road_integration.py -- tmp/materials_road` (base.blend is never saved) | `ROAD_INTEGRATION OK` (last run: 14 / 14 checks) |
| per material | `reconstruction/<key>/scripts/` (video scenes, comparisons, graph checks, road checks) | see each VALIDATION.md |
| contract | every `run.py build` checks `core.check_contract` | `RUN OK` / `RUN FAIL` |
