# Street generator v4: completion report (2026-10-28)

Brief: turn the v3 generator into a complete, believable street environment whose assets are positioned
by rules and hold up in Godot, with priority on the missing footbridge, realistic exported trees,
functional sidewalk furniture placement and end-to-end route connectivity.

Evidence:
- **Validation run:** `tools/roads/tests/street_block_v4_test.py` builds from a factory scene, reports `STREET_BLOCK_V4 OK`, and writes results to `tmp/roads/v4final/street_block_v4_results.json`.
- **Godot run:** `tests/capture_street_block_v4.gd` on Godot 4.7.2 (D3D12, RTX 3070 Laptop, 1280x720, 4x MSAA) writes `tmp/roads/v4final/godot/godot_stats.json`.
- **Images:** in `docs/roads/v4/`.

## Implemented
| area | what exists now | where |
|---|---|---|
| audit | inventory of every MRS collection plus contact sheet; feature matrix before v4; defects found | `AUDIT_v4.md`, `tools/roads/audit_v4.py`, `v4/audit_collections_v3.jpg` |
| footbridge | anchor-driven solver plus editable `Footbridge` GN group (deck / beams by style, stairs on stringers, railings with posts, handrails, bars, kick plate and LED strip, truss, columns with footings and crossheads, collision-only output, metre UVs) | `footbridge.py`, `FOOTBRIDGE.md` |
| route networks | pedestrian graph: sidewalks, corners, crossings with refuges, kerb ramps, bus stop, entrance, park paths, footbridge stairs / ramps / deck. Bicycle graph: cycleways, junction crossings and turns, mixed traffic, shared roundabout ring, dead-end through path, footbridge ramp. Checks: connected components, step-free reachability, measured clear width | `routes.py` |
| inherited builders | **roundabout:** zebra crossings per arm with kerb ramps and tactile paving, corner paving and kerbs joining arm sidewalks to the ring, parallel bicycle crossing, shared foot / cycle ring. **dead end:** sidewalk round the bulb, filtered through path with a dropped kerb | `junction.py` |
| furniture | 20 assets on one baked 2048x1024 atlas (albedo / ORM / normal), each with footprint, access, zone and height properties | `furniture.py`, `FURNITURE.md` |
| placement v4 | sidewalk zone model, oriented footprints and access envelopes on a spatial hash, reservations first, signs by condition, bus stop (shelter aligned to the kerb, boarding area, pole, information board, pad, marking), road-class streetlights, drains / hydrants / cabinets / access covers, benches / bins / racks with access rules, trees with canopy checks, landscape regions, park, entrance paths, skip reasons | `placement.py`, `PLACEMENT_RULES.md` |
| streetlights | road-class presets (height, reach, setback, spacing, arrangement), real spot lights separate from the emissive heads, night setup, Godot `MrsStreetLights` (distance fade, shadow budget) | `lighting.py`, `LIGHTING.md`, `world/roads/mrs_street_lights.gd` |
| trees / plants | the game's landscape-kit species (13 trees, LOD0 + LOD1 + impostor; grass and shrubs) as the MRS library; same meshes in Blender and Godot | `game_trees.py` |
| road materials in Godot | COLOR_0 masks (traffic lane, curb dirt, gutter / drain wetness) and UV2 (lane width, half median); `mrs_road.gdshader` rebuilds wheel tracks per pixel over the baked tile | `export.road_masks`, `world/roads/mrs_road.gdshader` |
| Godot loader | `MrsStreetBlock.build()`: GLBs, double-sided trimesh collision, per-signal lens control with a phase cycle, trees / plants through `CityLandscape` MultiMesh LODs, lights | `world/roads/mrs_street_block.gd` |
| demonstration block | v3 block plus: protected cycleways with junction crossings, footbridge across the 5-lane avenue, furnished bus stop on a widened south sidewalk, park with three paths, a kiosk and park trees, cafe pavilion with an entrance anchor and access path, 1:12 ramp + stair approaches, lawn ground material | `samples.street_block`, `samples.regenerate_block` |

## Tested (measured)
**Regeneration** (14 scenarios, each a full rerun of junctions, footbridge, placement, park and routes):

| scenario | placed | objects | ped. components | narrow edges | overlaps |
|---|---|---|---|---|---|
| baseline | 239 | 430 | 1 | 0 | 0 |
| north street 2+2 lanes, then back to 1+1 | 241 / 239 | 434 / 430 | 1 | 0 | 0 |
| south sidewalk 3.2 m (shelter skipped with the measured shortfall), then 4.6 m | 234 / 239 | 427 / 430 | 1 | 0 | 0 |
| avenue E cycleways painted / buffered, then protected | 238 / 239 | 429 / 430 | 1 | 0 | 0 |
| T-junction moved 4 m, then restored | 241 / 239 | 433 / 430 | 1 | 0 | 0 |
| tree spacing 9 m and lights x0.8, then restored | 257 / 239 | 466 / 430 | 1 | 0 | 0 |
| footbridge anchor moved -22 m (bridge followed), then restored | 240 / 239 | 432 / 430 | 1 | 0 | 0 |
| placement seed 11, then 7 | 238 / 239 | 431 / 430 | 1 | 0 | 0 |

Object counts return exactly to 430 after every round trip, with no duplicated names. The bicycle network stays one component with 5 open road ends as network boundaries, and every scenario takes about 12–14 s.

**Footbridge** (Girder style, avenue station 100 m):

| measure | value |
|---|---|
| deck level | 6.82 m |
| rise to the sidewalk | 6.67 m |
| span | 41.1 m |
| clearance over the highest asphalt | 5.30 m |
| supports | 12, all in landside regions |
| stairs | 41 risers of 0.163 m, going 0.30 m, 4 flights in 2 legs, 10.8 x 6.5 m footprint |
| ramp | 9 runs of 0.74 m at 1:12, 2 legs, 53.9 x 6.5 m footprint |
| visual triangles | 58,696 (down from 77,648 after switching to 8-triangle bars) |

**Routes** (block):

| measure | value |
|---|---|
| pedestrian network | 75 nodes / 82 edges, 1,766 m, one component, one step-free component |
| narrowest sidewalk clear width | 2.07 m against a 1.8 m rule |
| bicycle network | 22 nodes / 41 edges, 975 m, one component |
| roundabout village | one pedestrian component; 3 crossings for the 3 arms that have sidewalks; shared ring |
| city block with dead end | one pedestrian component; through path |

**Placement** (baseline):

| kind | count |
|---|---|
| drains | 54 |
| lights | 24, with 53 real sources incl. footbridge lights |
| benches | 24 |
| bins | 15 |
| cabinets / access covers | 14 / 14 |
| hydrants | 12 |
| bike racks | 7 |
| signs | 31 |
| street trees / park trees | 29 / 37 |
| landscape regions | 12 (+1 park planting) |
| plants | 2,078 |
| skipped items | 60, each with a reason (e.g. canopy over a light or footbridge, crown base too low over traffic, no furniture zone) |

**Export** (`tmp/roads/v4final/export`):

| file | content |
|---|---|
| roads + junctions + footbridge + paths + buildings | 85,313 tris, 44 meshes, 35 MB (baked 1K tiles dominate) |
| collision | 18,498 tris |
| props | 228 nodes, 106,485 tris, furniture atlas textures |
| signals | 4 poles |
| JSON | 6 roads, 66 trees, 2,078 plants, 53 lights, 1 footbridge, 82 pedestrian edges, 262 placed items with footprints |

**Godot 4.7.2:**
- **Load:** the block loads in 1.4 s. 8 asphalt surfaces get the road shader, and 66 trees plus 2,078 plants go into 258 MultiMeshes.
- **Signals:** 4 are controllable per signal; phase 0 and phase 1 each light 2 greens, always on opposite approaches.
- **Collision rays:** 231 of 236 route points hit. Stairs, ramps, deck, paths and crossings hit at 0.0004 m error. The 5 misses sit exactly on road-end / junction mesh boundaries and at the tip of a park path.
- **Frame cost:** GPU 2.1–7.7 ms per view, CPU 0.3–1.3 ms, 42–1,019 draw calls.
- **Night:** 53 lights; 13–42 inside the fade distance at street level; at most 4 shadow-casting lights (budget 4).
- **Comparison images:** `v4/compare_day_a.jpg`, `compare_day_b.jpg`, `compare_day_c.jpg` and `compare_night.jpg` (Blender left, Godot right, same cameras).

**Save / reopen:** `tmp/roads/v4final/street_block_v4.blend` (41 MB) reopened in a second process with the same 430 objects. The footbridge and roads evaluate, and every node group is present.

**Blender vs Godot differences, explained:**
- Beyond 125 m Godot shows the game's tree impostor cards. They read as crosses from straight above but are built for street-level views.
- Godot lights fade with camera distance (the presets start fading at 60–80 m), so the high overview at night shows few pools while street-level views match.
- Foliage beyond 26–42 m uses the shared LOD1 atlas and reads slightly darker.
- Shadows are cascaded in Godot and soft in EEVEE.

## Fixed defects found on the way
These v3 defects were invisible in renders but wrong in data or engine terms (details in `AUDIT_v4.md`):
- `road_sample` stopped at 54 m on median roads.
- Props floated up to 0.3 m on cambered roads.
- Python's lane-side convention was the mirror of the road group on asymmetric roads. Placement, routes, the footbridge solver and junction corners at road starts were one lane width off; junction approaches now use explicit "looking out" sides.
- `T.vmath` read the wrong output for dot product, length and distance, so all left-side kerb, paving, cycleway and planting faces pointed down. They now point up: zero downward faces, from hundreds per road.
- A near-straight T-junction corner trimmed the S-curve by 48 m.
- The v2 village sample used obsolete input names.

## Incomplete / known limitations
- **Roundabout cycling:** cyclists cross arms on a parallel crossing and use a shared foot / cycle ring. There is no separate Dutch-style cycle track ring.
- **Building entrances:** entrance anchors are supported, but the block has only the cafe pavilion and a kiosk; there are no building frontages.
- **Footbridge styles:** Truss and Box exist in the node group and solver, but only Girder is exercised by the test. Bridge lighting is point lights on the walking line plus the decorative LED handrail strip.
- **Hedges in Godot:** the yard kit's clipped hedge and boxwood render near-black or grey in Godot under the shared foliage shader, so park edges use shrub lines instead.
- **Foliage method:** alpha scissor (the game's shader). It has no sorting artifacts and keeps working shadows; shimmer is limited by mipmaps, LOD1 and impostors. Alpha-to-coverage was not enabled because the shader is shared game code.
- **Lamp emission:** all luminaires share one lamp-emission material (no per-pole switching).
- **Glass in Godot:** the lantern glass loses its alpha in the engine export, and the shelter glass is alpha-blended, so overlapping panes can sort imperfectly.
- **Furniture placement limits:** furniture zones narrower than an asset's access envelope skip it (reported), e.g. bike racks on 3 m sidewalks.
- **Engine materials:** road wear is rebuilt in the Godot shader, while repairs / cracks stay in the baked tile. Prop materials are the furniture atlas or flat colours for the older sign and light assets.
- **Build time:** the node-group build takes about 3 minutes; iterate headless with `-- --base`.
