# Street generator audit (Milestone A) — 2026-10-28

Live Blender: 5.2.3 LTS, file `tmp/cityforge/refmat/realisticProceduralMaterial_01.blend` (the user's
material reference file; the road scenes were added to it as separate scenes). Backup saved:
`tmp/roads/backup_live_v2_2026-10-28.blend` (143 MB). Units: metric, metres, scale 1.0.
Godot: 4.7.2 Forward+, project at the repo root (`project.godot`), assets consumed from `assets/` with
`.import` files; existing road capture `tests/capture_roads.gd` reads `assets/roads/mrs_demo.glb`.

## What exists and how it is made
| part | technique | source |
|---|---|---|
| road body, curbs, sidewalks, median, markings, dashes, arrows, ticks, bike/parking strips, deck, pillars, barriers, props, lights, trees, manholes, drains, embankments, scatter | **Geometry Nodes** `MRS_Road` (one group, ~1,800 nodes, 80 inputs, 10 panels) built by `tools/roads/mrs/road.py` | Python-generated graph |
| terrain pull | Geometry Nodes `MRS_TerrainConform` | `terrain.py` |
| junction surfaces, curb corners, crosswalks, stop lines, signal poles; roundabouts; dead ends | **Python meshes** (bmesh), rebuilt from stored metadata | `junction.py` |
| gantries, text signs, cable stays, tunnels, bus stops | Python meshes | `structures.py` |
| asphalt / paint / concrete / bike / structure / embankment | **Shader Nodes** groups (4) + 6 materials | `materials.py` |
| 95 props, signs, lights, signals, barriers, piers, scatter, structure parts | static library meshes (procedural bmesh, asset-marked) in hidden collections | `assets.py` |
| presets, UI, export | Python | `roads.py`, `ui.py`, `export.py` |

## Weaknesses confirmed in renders (docs/roads/v2/*.jpg)
1. Intersection areas oversized: corner radius 6–8 m plus trims past the furthest tangent point make
   the junction polygon very large on wide roads; the asphalt polygon is one flat sheet.
2. Bike lanes and the median end abruptly at the trim line (no crossing treatment, no median nose).
3. Crossings exist (zebra) but no ramps, no tactile paving, stop-line setback fixed; no parallel-line
   preset; no refuge islands.
4. Asphalt repair patches (random rectangles) and crack scale too strong by default.
5. Curb profile OK (bevel) but no sidewalk paving module/size control; no planting strip.
6. Trees: 9 simple shells; landscape outside embankments empty.
7. Props: random pick from one collection at a fixed spacing; no placement priority or exclusion
   zones except the junction clear distance; signs are random, not rule-based.
8. Parameter changes: verified for widths/presets (v2 report); lane-count transitions along a road are
   not supported (fixed cross-section per road).

## Reference tools — compatibility checked, decisions
- NodeToPython 4.2.0 (GPL-3): supports Blender 4.2–5.2; exports node trees to Python. Not needed: our
  graphs are already generated from Python (`road.py`), which is the editable source of truth.
- geonodes (al1brn): supports Blender 5.2; a nicer authoring DSL. Not adopted: the project's `T` builder
  already exists and switching would rewrite 2,000 lines for no functional gain. (At most one library
  was to be added — none is.)
- nodebpy: not evaluated further for the same reason.
- newo-ether/blender-mcp: the existing MCP connection already executes Python and screenshots.
- IRCSS Trees-With-Geometry-Nodes (MIT): approach (trunk curve taper + noise, branches as instanced
  splines, leaves instanced) adopted as the design of `Tree_Variants`; nothing downloaded.
- godot-road-generator (MIT): RoadPoint cross-sections, auto-generated RoadLanes for agents; our
  metadata export follows its idea (lane paths per road with direction and type) in JSON.
- Ucupaint (GPL-3): layer painting/baking add-on; not used — baking is done by `materials.bake_tiles`.
- City Road Maker: feature list only (see REPORT_v2.md).
