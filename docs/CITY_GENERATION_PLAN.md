# City generation: tool evaluation and plan (2026-10-23)

**Goal (long-term):** rebuild the city as a realistic, detailed, *consistent* city with fictional
names, made of distinct neighbourhoods: Turkish, Japanese, Korean, European (Italian, German,
French), Latin, each with its own street layout, buildings, street and shop names, props and
people, all in one graphic style. Layout inspiration: a Vancouver-like mix of differently angled
street grids, waterfronts and parks (fictional names everywhere).

## 1. The tools, tested

Every Blender add-on was installed in an isolated Blender 5.2.3 profile (not the everyday one),
its code reviewed before running (no network calls, no hidden behaviour), and exercised by a test
scene. The scenes are in the live Blender file, scene `ToolEval` (collections `ToolEval_1..6`).

| Tool | What it is | Licence | Result in our tests | Verdict |
|---|---|---|---|---|
| **Procgen Maps** (Beneking102) | Blender add-on: whole city in one click: zoned blocks, streets, 12 facade types, special buildings (hospital, police...), signage, props, terrain, night mode; glTF/FBX/SVG export | GPL-3.0 | Works on 5.2. Small town 2.4 s (1,373 objects, 92k tris), metropole 48 s (1.1M tris). Grey-box look | **Blockout / ideas**, not final art. Worth copying its ideas: zone classification, rule-based signage, instanced props with LOD, pure-Python/bpy split |
| **Procedural Building Shell Generator** (outerreaches) | Building shells with real window/door openings, storefronts, pilasters, parapets, patios, optional interiors and damage; bulk generation | GPL-3.0 | 52 parameters, 0.02 s and 300-1,200 tris per building, 8 material slots (walls, roof, frames...) | **Strong base for our building generator**: wrap it with per-culture style profiles and our own detail kit and materials |
| **Driving Scenario Creator** (johschmitz) | Road networks in Blender with real lane cross-sections (driving, parking, bike, sidewalk, curbs, markings), junctions; exports **OpenDRIVE** (.xodr) + glTF | GPL-3.0 | Needs the `scenariogeneration` library (installed into the sandbox only). Scripted road creation works through its internal API; urban preset with sidewalks; .xodr + glTF export works | **Use for lane-accurate arterials and junctions**: OpenDRIVE gives traffic AI exact lanes and connections. Interactive-first; materials need our look |
| **Photogrammetry Importer** (SBCV) | Imports COLMAP / Meshroom / OpenMVG... reconstructions (cameras + point clouds/meshes) | MIT | COLMAP model with 8 cameras / 20k points imported in 0.2 s. Its optional geometry-nodes point display is broken on Blender 5 (worked around) | **Reference capture**: photograph your own streets → COLMAP → exact proportions to model from. Not for direct game meshes |
| **Node To Python** (Brendan Parmer, Blender Extensions) | Converts geometry-node / shader / compositor node trees into Python | GPL-3.0 | A facade generator exported as an add-on and rebuilt from the generated code alone: identical (8 nodes, 200 tris) | **Essential glue**: design generators visually in geometry nodes, keep them as code in git, run them headless in build scripts |
| **City Generator** (ProbableTrain, itch.io + GitHub) | Tensor-field street plans: grid / radial districts, coast and river, main/major/minor roads, parks, building lots; PNG/SVG/STL export | LGPL-3.0 (source); exports free to use | Web app tried; then its core run **headless and seeded** in Node: 2,000-6,500 lots in ~1 s, JSON straight to disk (`tools/citygen/`) | **Backbone of the city plan**: one layout file per city (district angles, plazas, water) → streets, blocks, lots |
| **Procedural Road Generator** (Superhive) | Geometry-nodes road / sidewalk generator (.blend) | "Royalty free", free ($0) | Not tested: the download needs a Superhive login | Download it into the project and it can be evaluated |
| **SideFX Labs** | Hundreds of Houdini tools (OSM import, road and building generators, PCG, game-engine plugins) | SideFX Labs licence; needs **Houdini** | Cannot run without Houdini (Apprentice is non-commercial; Indie is paid) | Not needed now; only if the pipeline outgrows Blender |

**Combined prototype (`ToolEval_6`):** a seeded City Generator plan with four differently angled
grid districts around a radial plaza → 396 lots → styled buildings (Turkish, European, Japanese,
Latin palettes and building types), roads with sidewalks: 25 s end to end.

## 2. The pipeline we can build

```
city layout (JSON)          districts: culture, grid angle, density, plazas, water, parks
   │  City Generator (headless, seeded)
   ▼
street plan                 roads by class, blocks, lots, parks, coast/river
   │  name generator        street, district and building names per culture (fictional)
   ▼
Blender build scripts       roads + junctions (own builder / OpenDRIVE via Driving Scenario Creator)
                            buildings: Building Shell base + culture style profiles + shared detail
                            kit (geometry-node generators kept as code with Node To Python)
                            props, trees, signage per culture
   │  export: one GLB per city block (LODs, atlas textures, VRAM-compressed), prop MultiMeshes
   ▼
Godot                       streamed blocks, sidewalk graph + traffic lanes from the plan, delivery
                            addresses from lots, people and routines per neighbourhood
```

### Neighbourhood style profiles (one data file each)
- **Turkish**: 4-6 floor apartment blocks, cumba (bay) windows, balconies with railings, ground-floor
  shops with awnings and Turkish signage, cream / ochre / terracotta.
- **Japanese**: narrow 2-4 floor lots, flat roofs and tiled pitched roofs, small shopfronts with
  noren and vertical signs, vending machines, utility poles, greys and dark wood.
- **Korean**: low-rise villas and mid-rise mixed use, hanok-inspired accents, dense neon signage in
  Hangul, convenience stores, warm brick and white.
- **European**: Italian (terracotta, shutters, arcades), German (gables, timber accents, tidy
  facades), French (Haussmann limestone, mansard roofs, wrought-iron balconies).
- **Latin**: 1-3 floor stucco houses in strong colours, wrought-iron balconies, patios, murals,
  tiled roofs.

### Keeping one consistent look
One material library (shared PBR textures, one texel density), one lighting and colour grade, one
level of modelling detail, style profiles that only change *forms, layouts and palettes*, and a QA
render sheet per district compared side by side (the same rule the vehicle pipeline uses).

### Names
Street, district and shop names come from per-culture word lists and patterns, never from real
addresses: Turkish *Sokak / Caddesi*, Japanese *-dōri / -chō*, Korean *-ro / -gil*, Italian *Via*,
German *-straße*, French *Rue*, Spanish/Portuguese *Calle / Rua*.

## 3. Roadmap

1. **Pipeline skeleton** (1-2 weeks): layout file → plan → Blender grey-box → Godot, one district,
   names system, sidewalk graph and delivery addresses from the plan; replaces the current
   generator for one area. Budget tests extended to the new blocks.
2. **Building kit v1** with the first neighbourhood (Turkish: the game's current setting).
3. **One neighbourhood at a time**: Japanese, Korean, European, Latin; each with its props, signage
   and people.
4. **Roads and traffic**: lane-accurate arterials/junctions (OpenDRIVE) feeding the traffic AI.
5. **Migration**: retire the old city pieces, keep saves, tests and deliveries working.

### Risks and rules
- **Licences**: the GPL/LGPL tools are used as build tools only (never shipped), which is fine; code
  copied *into* our tools must keep their licence. Generated assets are ours.
- **Performance**: the game is CPU-bound today; a bigger city needs block streaming, impostors and
  the asset budgets (`tests/asset_budget_test.gd`, `tests/perf_budget_test.gd`) from day one.
- **Cultural care**: work from references for each culture, avoid caricature; fictional names.
- **Consistency**: no district ships without the shared material library and a QA sheet review.

## 4. Terrain first (added 2026-10-23)

The city is planned on real ground: hills, lowlands, lakes and rivers, not a flat plate. Order of
work: **terrain → water → road plan → sidewalks, traffic lights, bus stops → public building
markers (police, hospital, city hall...) → neighbourhoods and parks**.

Terrain tools compared:
| Tool | Result | Verdict |
|---|---|---|
| A.N.T. Landscape (official Blender extension, GPL-2) | 20 noise types + an erosion simulator (rain, rivers, avalanches); 130k-tri terrain in 0.4 s, erosion 7 s | Generic noise; no lakes, river networks or "where can a city go" |
| Erosion terrain generator (Blender 5.2 extension, GPL-3) | Droplet erosion on noise | Same limits |
| SRTM Terrain Importer / BlenderGIS / PTerrain | Real-world elevation (NASA SRTM, public domain) | Option: real topography as a base, fictional names on top |
| Gaea | Best-in-class | Free edition is non-commercial only; commercial needs a paid tier |
| Terrain3D (Godot, MIT) | Runtime terrain with LOD, painting, collision | The Godot side: imports our 16-bit heightmap |
| **`tools/terrain/city_terrain.py`** (ours) | From a JSON (hills, basins, lakes, sea edge): relief, thermal erosion, lakes filled to their spill level, rivers that follow real drainage (priority-flood + D8 flow) carved into the ground and running to the sea | **Chosen.** 2 km × 2 km at 4 m in ~5 s; outputs a 16-bit heightmap, water / slope / buildable masks, river lines, lake levels and a planning map |

Next: the road planner reads `meta.json` and the masks: no lots on water or steep ground, roads
along the contours on hills (the tensor field turns with the slope), bridges where roads cross rivers.
