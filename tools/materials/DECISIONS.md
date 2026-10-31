# Procedural materials library: decisions log

Work order from the user (2026-10-30, verbatim intent): after the current road / game work, build procedural
materials in Blender from three Ryan King Art tutorials, reverse-engineered with the extraction tools and the recipe
repository; do not apply them to the game yet; keep them separate from the road tool, but make sure the road tool can
use them; work alone, save the decisions. This file records every decision made without the user, with the reason.

Evidence classes (as in tools/roads/crm_reconstruction): **A** directly observed in the video, **B** narration only,
**C** inferred (our implementation), **D** unresolved.

## Sources

| key | video | author / date | length | used for |
|---|---|---|---|---|
| asphalt | `Eofg9SBcdBY` Procedural Asphalt Material (Blender Tutorial) | Ryan King Art, 2022-06-30 | 27:08 | road surface |
| cobblestone | `30vbbpy9zwg` Procedural Cobblestone Ground Material (Blender Tutorial) | Ryan King Art, 2026-01-12 | 40:41 | paving, plazas, old streets |
| glass | `SNKNqHd0AYI` Procedural Textured Frosted Glass Materials (Blender Tutorial) | Ryan King Art, 2026-05-12 | 34:03 | glazing (bus shelters, buildings) |

## Decisions

| # | decision | reason |
|---|---|---|
| D1 | The library lives in `tools/materials/` (Python package `procmat`), not in `tools/roads/`. It imports nothing from the road tool at run time. | "separate from road tool" |
| D2 | Every material follows the road tool's material contract: one shader group node named `MRS` in the material, inputs `Use UV` (0 = object space in metres, 1 = `UVMap` x `Tile Size` sampled on a 4D torus, seamless) and `Tile Size` (m), outputs `BSDF` plus `Albedo` (and `Metallic` where metallic). | the road tool's `MRS_Road` material sockets take any material; `tools/roads/mrs/materials.py bake_tiles()` and `apply_material_preset()` find the group node named `MRS`; the torus mode makes seamless tiles for a later Godot bake |
| D3 | Names: node groups `PM_<Name>` and materials `PM_<Name>` (PM = procedural material). | no clash with the road tool's `MRS_*` names; easy to filter |
| D4 | Scales are converted to real-world metres (the tutorials work on a ~2 m object). Each material exposes a size control in metres (aggregate, stone size, pattern size). | roads, sidewalks and glazing of any size keep the same texel scale |
| D5 | Textures without a 4D variant in Blender (Wave, Brick, Checker, Magic, Gradient) are rebuilt from 4D Noise / Voronoi or periodic maths when the torus mode needs them, and listed as version / mode adaptations. | the torus (seamless) mode samples 4D coordinates |
| D6 | No HDRI is downloaded. The tutorials name Poly Haven HDRIs (`machine_shop_02` for asphalt, `fish_hoek_beach` for cobblestone); renders use Blender's bundled studio-light HDRIs (`datafiles/studiolights/world`), and lighting differences are reported separately from material differences. | downloads beyond the three videos and the recipe repository were not authorised; a bundled HDRI is reproducible |
| D7 | Raw downloads (videos, auto captions, transcripts, recipe files) stay in `tmp/materials_video/` (not committed: the authors' content). Evidence frames and crops cited by the documents live under `tools/materials/reconstruction/<key>/evidence/`. | same rule as the City Road Maker reconstruction (`tools/roads/crm_reconstruction`) |
| D8 | The recipe repository (KunalMGupta/material-apprentice, MIT) is reference data only: its `Asphalt/asphalt_material*` entry is derived from the same asphalt video and is used to cross-check node types and values read from frames (class B until a frame confirms it). Its cobblestone and frosted-glass entries come from other tutorials and are used only as general background. Nothing from it is run or copied verbatim. | user: "use the reverse engineering repo"; my earlier evaluation recommended mining its recipes, not running it |
| D9 | Builds and renders run headless (`blender --background --factory-startup`), at most two background Blender processes at a time; the user's open Blender and Godot editor are not touched. | project rules (CLAUDE.md, memory) |
| D10 | Nothing is applied to the game: no file under `app/`, `actors/`, `systems/`, `world/`, `assets/` changes, and the road tool's materials are not replaced. The road tool compatibility is proven in a test scene. | "do not apply it to game yet", "do not edit game"; writing under those folders also triggers the editor's City Preview Sync rebake |
| D11 | The pending road / game commit waits for a clean `tests/run_tests.ps1` pass. The perf budget test failed only because the machine was loaded (the open Godot editor held 3.7 GB of the 8 GB VRAM with the city preview; the GPU stood at 27 % with nothing of ours running): same code passed earlier at 20.1 s boot / 17.1 ms median / 22.0 ms p95, and failed at 26.7-33.7 s boot / up to 120 ms median while loaded. | the user's rule: commit to main only when the tests pass |

## Decisions made during the reconstruction

Summary of every class C decision (our implementation or inference) and every version / mode adaptation taken while
building the library, merged from the per-material logs. D1-D11 above are unchanged and binding; the full reasons,
measurements and tables are in the linked files. Classes: **A** frame, **B** narration / recipe repository, **C**
ours, **D** unresolved.

### Shared core ([procmat/DECISIONS_CORE.md](procmat/DECISIONS_CORE.md))

| # | decision (class C) |
|---|---|
| C1 | Package layout `core` / `rig` / `bake` / `graphdump` / `road_adapter` / `imaging` / registry; `road_adapter` re-implements the road tool's modifier-input setter instead of importing it (D1). |
| C2 | `Coordinates` reproduces the road tool's mapping: object mode = Object coordinates in metres, W = 0; UV mode = UVMap x Tile Size on a rotated flat 4D torus (arc length = metres). |
| C3 | `noise4` / `voronoi4` are 4D in both modes by default; `exact3d=True` adds a 3D twin for object mode (the tutorials' exact field), mixed by Use UV. |
| C4 | Textures without 4D (Gabor, Brick, Wave, Magic, Checker): `seamless()` 4-sample cross-fade, `periodic()` / `wrap()`, `snap_scale()` (D5). |
| C5-C6 | `contract_material`: one `MRS` group node, displacement off (BUMP) unless asked, fake user, viewport colour / roughness = the road tool's glTF fallback; `Use UV` / `Tile Size` in a closed "Mapping" panel. |
| C7-C8 | Bakes in a private scene `PM_Bake` with two UV maps, 8-bit PNG; seam evidence = `seam_metric` plus the decisive `periodicity()` test (UVs shifted by (0.5, 0.25) = rolled tile). |
| C9-C10 | Preview rig: own scene, EEVEE previews, Cycles GPU bakes, bundled HDRIs only, AgX; Pillow through the system Python. |
| C11-C12 | `road_adapter.assign` sets Asphalt Condition / Sidewalk Surface to Default and records choices for `reapply()`; shelter glass = `MRS_F_BusShelter(_LOD1)` slot 1, replaced per object. |
| C13-C16 | Tests in sequential Blender runs, base.blend never saved; self-registering material modules; automatic node layout; `pm_note` evidence tags on nodes. |

### Asphalt ([reconstruction/asphalt/DECISIONS.md](reconstruction/asphalt/DECISIONS.md))

| # | decision | class |
|---|---|---|
| AS1 | Two materials: `PM_Asphalt` (ColorRamps that are controls become exact Map Range / Mix maths) and `PM_AsphaltTutorial` (the literal graph); albedo identical within 4/255. | C |
| AS2 | Video 3D textures built with `exact3d` (3D in object mode, 4D twin in UV mode); the cracks Voronoi stays 3D (fed by a periodic noise colour); the pebble Voronoi is 4D as in the video. | C |
| AS3 | The video's object space on a 1 m-radius sphere = metres (radius assumed, U7); `Pattern Size` and `Aggregate Size` (1/110 m) controls; rescaling verified bit-identical. | C |
| AS4 | Exposed controls with the video's values as defaults; names chosen not to collide with the road tool's preset inputs. | C (values A) |
| AS5 | Bump Filter Width 1.0 (not the 5.2 default 0.1): measured to match the 3.2 relief contrast. | C (measured) |
| AS6 | Damage black stop 0.35 (0.343 legible before a jump cut, 0.350 after; 0.343 would reduce damage by 17 %). | C |
| AS7-AS10 | Validation scene rebuilt (icosphere, Cycles 256 spp, Filmic, emitters fitted in 24 sectors); world = desaturated bundled `studio.exr` at 0.2; comparisons from -Y; the video's exact field was not found by a 6,000-direction view search (D). | C / D |
| AS11-AS13 | Principled v2 with F0 0.04; MixRGB -> Mix (RGBA, factor clamped); reroutes / frames kept, layout by the core. | C |
| AS14 | Viewport colour (0.0278, 0.0271, 0.0267), roughness 0.59 = the UV-bake means. | C (measured) |
| AS15-AS16 | Evidence as PNG renders / JPEG panels / JSON numbers; road compatibility proven in base.blend (never saved). | C |
| AS17 | Audit ASP-1: each 4D twin's output is linearly remapped (`UV_MATCH`, gain x 4D + offset) to the 3D distribution, so UV-mode bakes have the object-mode statistics. A mode adaptation, not a video value. | C (measured) |
| AS18 | Audit ASP-2: Damage Amount kept at the video's value; the video's extra damage (0.041 vs 0.030 +- 0.013) is within the view-to-view spread (z +0.8). | C (measured) |

Adaptations 3.2 -> 5.2: MixRGB -> Mix node; ColorRamp `Fac` looked up by identifier; Noise / Voronoi defaults
equivalent (identical values not confirmed, D); Bump Distance set to 1.0; Filter Width 1.0 (AS5); Principled v1 -> v2
(slightly darker at grazing angles); 3D textures + remapped 4D twins (AS2 / AS17); `machine_shop_02` HDRI -> bundled
`studio.exr` (D6).

### Cobblestone ([reconstruction/cobblestone/DECISIONS.md](reconstruction/cobblestone/DECISIONS.md))

| # | decision | class |
|---|---|---|
| CB1 | One group `PM_Cobblestone`, two materials: `PM_Cobblestone` (BUMP, for coarse road meshes) and `PM_CobblestoneDisplaced` (BOTH, the video's "Displacement and Bump"). | C |
| CB2 | Every texture `exact3d`; object mode reproduces the video's own stones (found by a camera search). | C |
| CB3 | Ramp positions / grey from segment a's typed values over segment b's bar measurements. | C (values A) |
| CB4-CB6 | Mapping (Point, Scale <- Material Scale) = core coordinates x Material Scale / Pattern Size; the video's object space = metres (scale applied); Displacement Strength and bump distances stay in metres (not divided by Pattern Size). | C |
| CB7-CB8 | The tutorial's 36-input interface kept; outputs `BSDF`, `Albedo`, `Displacement`, `Height` (relief in metres). | C (interface A) |
| CB9-CB11 | Hidden Principled settings at 5.2 defaults, Filter Width 0.1; reroutes left out; the UV-mode warp moves V only (W not warped). | C |
| CB12 | Validation scene: 0.5 m sphere, Cycles, Filmic Very High Contrast, camera from the view search, sun / rim fitted, bundled `courtyard` HDRI (D6). | C |
| CB13 | The product render (0:04 / 40:16) is not the reference: defaults stay the tutorial build's; Individual Size about 0.5 approximates the product look. | C |
| CB14 | `.gdignore` in `reconstruction/cobblestone/` (evidence is not game content). | C |
| CB15 | Viewport colour (0.0187, 0.0183, 0.0122), roughness 0.74 = the UV-bake means. | C (measured) |

Adaptations 5.0.1 -> 5.2: Mapping replaced by the core multiply; 3D + 4D twins; W unwarped in UV mode; method BUMP for
the road material; `fish_hoek_beach` HDRI -> bundled `courtyard.exr` (D6). All other nodes identical.

### Glass ([reconstruction/glass/DECISIONS.md](reconstruction/glass/DECISIONS.md))

| # | decision | class |
|---|---|---|
| G1-G2 | Six self-contained groups (no shared sub-group); `Shader` -> `BSDF`, `Albedo` = Glass Color. | C |
| G3 | Voronoi / Noise as `exact3d` twins; object mode = the video's cells (layout correlation peaks at zero shift). | C |
| G4-G5 | `Pattern Size` divides the Mapping Scale and multiplies every Bump Distance; the video's Mapping is fed by the contract coordinates (W scaled alike). | C |
| G6 | Wavy, UV mode: no 4D Gabor, so a 4-sample cross-fade on the video's pane plane. | C |
| G7 | Gabor Orientation 3D (0.797, 0.604, 0) fitted from the direction-ball widget; Gabor Scale 12 internal. | C / A |
| G8-G9 | Ramp stops converted from the picker's perceptual values to linear; RGB Curves points as read, auto handles. | C / A |
| G10-G12 | Bump Filter Width 0.1 and typed distances (A); limits never shown take Blender's; Thin Film at defaults. | A / C |
| G13 | Material: Bump method; EEVEE Dithered + raytraced refraction; viewport colour (0.80, 0.85, 0.87), alpha 0.3-0.6. | C |
| G14-G15 | Validation scene rebuilt (six 0.8 m panes, red Suzannes fitted, D); lighting searched over the bundled HDRIs before any material change. | C |
| G16 | No material value changed after the comparisons; remaining differences are lighting / placement. | - |
| G17 | Audit GL-2: variance-preserving gain for the Wavy UV cross-fade (relief -1 % in the blend band, was -33 %). | C |
| G18 | Audit GL-1: Wavy orientation applied relative to the surface (0.797 H - 0.604 N), so every pane gets the video's vertical 2.1 cm streaks; exact on the video's X-Z pane. | C |
| G19 | Audit GL-3: Blobby relief kept: the video's literal graph renders pixel-identically; the contrast ratio depends on the backdrop; stays open as scene / lighting. | A / C |

Adaptations 5.1.1 -> 5.2: nodes identical; UV mode adds 4D twins (Gabor: cross-fade, G6 / G17); the object-mode Wavy
orientation follows the surface (G18); ramp colours linearised (G8); `old_apartments_walkway` HDRI -> bundled HDRIs
(D6).

### Integration and library file ([VALIDATION.md](VALIDATION.md))

| # | decision | class |
|---|---|---|
| I1 | The integration test builds the road tool's own `street_block()` sample in base.blend (never saved): PM_Asphalt -> Asphalt Material, PM_Cobblestone -> Paving Material, one cobbled carriageway, junction slots and shelter glass replaced per object. | C |
| I2 | `run.py --scene` saves a preview scene `PM_Library` in the library file, with `relative_remap=False` so the bundled HDRI path survives; factory leftovers removed; no packed images. | C |
| I3 | Glass bakes for a game should use a 0.5-1 m tile at 16 bit (a 4 m / 8-bit tile under-resolves the normals). | C (measured) |

The extraction decisions behind the specifications are in
[reconstruction/asphalt/DECISIONS_all.md](reconstruction/asphalt/DECISIONS_all.md),
[reconstruction/cobblestone/DECISIONS_a.md](reconstruction/cobblestone/DECISIONS_a.md) /
[DECISIONS_b.md](reconstruction/cobblestone/DECISIONS_b.md) and
[reconstruction/glass/DECISIONS_a.md](reconstruction/glass/DECISIONS_a.md) /
[DECISIONS_b.md](reconstruction/glass/DECISIONS_b.md).

### Cobblestone audit (2026-10-30, [reconstruction/cobblestone/VALIDATION.md](reconstruction/cobblestone/VALIDATION.md#6-independent-audit-2026-10-30))

| # | decision | class |
|---|---|---|
| CB16 | Audit CB-1 / CB-2: UV mode only (object mode = the video's graph, unchanged): 4D Smooth F1 Smoothness = Individual Size x 0.82, 4D rock Voronoi Distance x 1.41, so the baked tile has the object-mode stone coverage (48.6 % vs 48.9 %, was 36 %), stone size (area-weighted median 12.6 cm both) and rock relief. A mode adaptation calibrated at the defaults, like AS17. CB15's viewport colour / roughness re-measured: (0.0200, 0.0200, 0.0139), 0.72. | C (measured) |

## Repository size

| # | decision | reason |
|---|---|---|
| D12 | The full-resolution evidence frames (`reconstruction/*/evidence/*/frames/`, grabs of the VP9 video) are stored as JPEG quality 92 (4:4:4) instead of PNG: 242 frames, 311 MB -> 128 MB; every reference was relinked. Crops, renders and comparisons stay as they are. `tools/materials/.gdignore` keeps Godot from importing the folder. | the frames come from a lossy video, so PNG kept no extra detail; PNG and JPEG go to Git LFS, whose size the project keeps small |
