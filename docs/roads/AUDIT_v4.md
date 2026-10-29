# Road Studio v4 audit (2026-10-28, before the v4 work)

Starting point: `docs/roads/REPORT_v3.md`, `tmp/roads/v3/street_block.blend`, the `tools/roads/mrs` package.
Inventory script: `tools/roads/audit_v4.py` (lists every `MRS_*` library collection with dimensions,
triangles, materials and custom properties and renders one strip per collection).
Contact sheet of the inherited collections: `docs/roads/v4/audit_collections_v3.jpg`
(`tmp/roads/v4/audit/inventory.json` holds the full table).

## Inherited library collections (v3)
| collection | objects | notes from the inspection |
|---|---|---|
| MRS_Props | 17 | bench x2, bins x2, bike rack, 3 bollards, bus shelter, hydrant, kiosk, mailbox, newspaper box, picnic table, planter, fence post, utility pole; procedural noise materials (flat colour in Godot), no footprint / access data |
| MRS_Streetlights | 6 | highway, double-arm, LED, lantern, bollard, wall pack; emissive lamp faces only, no light sources, no fixture anchors |
| MRS_Signage | 55 | 24 sign kinds + text children, direction board, 5 signal styles with per-lens State materials |
| MRS_Signs / MRS_TrafficLights | 8 / 2 | older v2 assets kept for compatibility |
| MRS_Trees + _LOD1 | 12 + 12 | generated `Tree_Variants` species, 2.2-7.8 k tris; their alpha leaf cards were dropped in the Godot export (blob / frond canopies) |
| MRS_Shrubs + _LOD1 | 2 + 2 | generated shrubs |
| MRS_Scatter | 9 | 4 grass clumps, wildflower, small bush, 3 rocks (simple meshes) |
| MRS_Barriers, Pillars, Drains, Manholes, Markings, Structures | 6, 3, 2, 3, 6, 8 | guardrail .. fence; gully grates; manholes; arrows; gantry, pylon, abutment, tunnel portal, bus shelter, crosswalk signal |

The game itself already contained a much better foliage set: `assets/landscape/*.glb` (13 tree species
with LOD0 / LOD1 atlas / impostor, alpha-scissor leaf clusters, wind data, `CityLandscape` MultiMesh
instancing in Godot) and garden / yard plants. v4 reuses them instead of the generated canopies.

## Feature matrix (state before v4 -> v4)
| feature | existing generator / asset | exposed parameters | placement rule | export | missing (before v4) |
|---|---|---|---|---|---|
| connected walking network | road sidewalks, junction corner rings, v2 roundabout ring, v2 dead-end bulb | sidewalk width / planting strip / curb | - | ped paths = sidewalk centre lines only | no graph, no connectivity or width check, no links to entrances / bus stops / parks / bridges; roundabout arms had a gap between ring and sidewalk, no crossings or ramps; dead end had no through path |
| connected cycle network | cycleway kinds on roads, junction bike bands | kind, width, buffer | - | bike lane paths per road | no network across junctions; roundabout / dead end ended cycleways abruptly |
| footbridge | none (only road bridges with pillars) | - | - | - | everything |
| sidewalk furniture | MRS_Props (above) | none | point spacing every 22 m with jitter | flat colours | footprints, access envelopes, zones, recycling bins, racks with clearance, shelters aligned to the kerb, poles / boards, cabinets, grates, covers |
| bus stop | `structures.bus_stop` (crude shelter + text) | road, station, side | - | flat colours | boarding area, pole, board, bin, pad, connection to routes |
| streetlights | 6 assets | spacing 28 m, alternating | v3 placement | emissive mesh only | road-class presets, arrangement, real lights, night scene, Godot lights |
| trees | Tree_Variants + LOD1 | species / seed in the group | strip every 11 m, species by style | leaf cards dropped | realistic canopies in Godot, canopy clearance checks |
| landscape | road scatter on embankments | density | GN scatter on embankment faces | - | regions, layering, hedges, parks |
| materials in Godot | baked road tiles | - | - | wheel wear, curb dirt, gutter wetness lost; props flat colour | masks for the engine, textured props |
| regeneration | road / junction rebuild, placement re-run | - | - | - | footbridge, routes, park, lights not part of it |

## Defects found while auditing / building v4 (fixed)
- `structures.road_sample` only used vertices within 0.3 m of the centre line: on the avenue (1.8 m median)
  the samples stopped after 54 m, so every later station was clamped and v3 avenue props were misplaced.
  Now the centre is interpolated across the cross-section and cached per road state.
- Props were lifted by `centre z + curb height`; on the 0.32 m crowned avenue they floated up to 0.3 m.
  Now `structures.surface_z(road, along, lat)` samples the evaluated cross-section.
- `nodes.T.vmath` returned the Vector output for DOT_PRODUCT / LENGTH / DISTANCE (the result is on
  "Value"). The Road_Sweep face-flip test therefore never ran: on every road the left-side kerb, paving,
  tactile, planting-strip and cycleway faces pointed down (hidden by double-sided materials, but broken
  for single-sided collision and shading normals). The superelevation curvature term was affected too.
- v3 junction clear zones at road *starts* ignored the trim (zone measured from station 0).
- Junction corners wider than ~150 deg (a road continuing almost straight through a T-junction) got a
  fillet whose tangent points ran out along the nearly parallel edges: the S-curve was trimmed 48 m back
  from the T-junction, and moving the junction 4 m pushed the trim to 278 m (the road vanished). Such
  corners are now straight (no fillet); the S-curve trim is 7.5 m.
- Placement on the `along` of the curve without the road's real drawn extent (A0..A1).
