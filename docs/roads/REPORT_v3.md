# Street generator v3 — completion report (2026-10-28)

Brief: extend the Blender road generator into a coherent procedural street generator (shared street
model, lane transitions, cycleways, crossings, rule-based signals/signs/placement, trees, materials,
Godot export) and validate one representative block. Milestones A–F were executed; this report states
what was built, what was measured, and what remains.

Deliverables
- Source: `tools/roads/mrs/` (package; `build_all()` regenerates every node group, material, asset
  and scene). Rebuild instructions: `tools/roads/README.md`.
- Working .blend: `tmp/roads/v3/street_block.blend` (the demonstration block, saved by the validation
  test) and `tools/roads/mert_road_studio_v2.blend` (all sample scenes, rebuilt by `build_mrs.py`).
- Editable node groups: `MRS_Road`, `Road_Profile`, `Road_Sweep`, `MRS_TerrainConform`, `Tree_Variants`
  (Geometry Nodes); `MRS_AsphaltShader`, `MRS_PaintShader`, `MRS_ConcreteShader`, `MRS_EmbankmentShader`,
  `MRS_PavingShader`, `MRS_TactileShader`, `MRS_CyclewayShader`, `MRS_MetalShader`, `MRS_BarkShader`,
  `MRS_FoliageShader` (Shader Nodes).
- Asset collections: `MRS_Props` 17, `MRS_Streetlights` 6, `MRS_Trees` 12 (+12 LOD1, 2 shrubs + LOD1),
  `MRS_Signs` 22 + `MRS_Signage` (24 kinds, direction board, 5 signal styles), `MRS_Barriers` 6,
  `MRS_Pillars` 3, `MRS_Scatter` 9, `MRS_Manholes` 3, `MRS_Drains` 2, `MRS_Markings` 11, `MRS_Structures` 8.
- Presets: road presets (residential, urban, highway, rural, service, bridge), material presets
  (clean, light_wear, heavy_wear, wet, fresh_highway, old_village, dirt_track), placement rules
  (`placement.RULES`), street-design parameters in the `MRS_Road` panels (metres, bounded).
- Documentation: `docs/roads/AUDIT_v3.md`, `docs/roads/PLACEMENT_RULES.md`, `docs/roads/STREET_MODEL.md`,
  this report. Validation images: `docs/roads/v3/*.jpg`.
- Godot export + metadata: `tmp/roads/v3/export/street_block{.glb,_collision.glb,_props.glb,_signals.glb,.json}`,
  verified in Godot 4.7.2 by `tests/capture_street_block.gd`.

## A. Audit (docs/roads/AUDIT_v3.md)
Confirmed in renders: oversized junctions (fillets of the *outer* sidewalk lines pushed the road trims
out to 25 m), abrupt cycleway / median endings, no ramps / tactile, random props, simple trees, strong
crack/patch defaults, no lane transitions. Reference tools: NodeToPython and geonodes are compatible
with 5.2 but were not adopted (the project already generates its graphs from Python); MRoadGen ideas
were adopted in v2; godot-road-generator's RoadLane idea shaped the JSON lane paths; Ucupaint and the
newo-ether MCP were not needed.

## B. Cross-section and junctions
- The road surface is now an analytic sweep (`Road_Sweep`: grid vertices sample the rail at their own
  station) so every boundary is a function of the station (`Road_Profile`). Verified: lane taper 2 -> 3
  forward lanes widens the right side by 3.5 m over 35 m (`road_v3_test`), ramps lower the paving to
  0.006 m at crossings vs 0.15 m mid-road, tactile faces present.
- Junction corners: asphalt fillet + concentric curb / sidewalk arcs (tighter outward), roads trimmed at
  the asphalt tangent (+0.3 m). Trims for a 3.2 m street meeting a 28 m avenue dropped from 25.3 m to
  17.7 m; the avenue's from 16.2 m to 13.4 m.
- Crossings: zebra or parallel-line presets, width / stripe pitch fixed in metres (consistent across
  road widths), stop line 0.4 m behind the crossing, curb ramps + tactile on the road sides, refuge
  islands on medians >= 1.7 m, median noses, bicycle crossings with elephant feet; the crown flattens
  to zero toward a junction so markings sit on the surface.
- Unsupported layouts raise errors: < 2 approaches, neighbours < 25 deg, end heights differing > 1.5 m;
  junctions closer than 25 m and tapers that are too short / too close to a junction are reported in
  `validation[]`.

## C. Transitions, cycleways, pedestrians
- `Transition`, `Lanes Forward/Backward End`, `Transition Start`, `Taper Length`; lane lines appear only
  where the lane exists; a merge arrow marks the dropped (outermost) lane; lane identities are numbered
  from the centre (`index_from_centre`) in the model.
- Cycleway per side: None / Painted / Buffered (hatched buffer) / Protected (curb or posts or planters)
  / Two-Way (centre dash, symbols both ways), bicycle symbol + arrow spacing, setback from junctions,
  junction continuation bands; `bike` lane paths exported.
- Sidewalks: width, curb height / bevel, planting strip, paving material with slab size, minimum
  walking width in the placement rules; pedestrian paths exported (sidewalk centre lines + crossing
  from/to points).

## D. Signals, signs, placement
- `signage.make_signal` (post / mast arm / pedestrian / bicycle / combined), heads as child nodes,
  lens materials `MRS_Lens_*` with a `State` node; `signage.make_sign` 24 kinds with editable text,
  `make_direction_board`. Junction control preset: none / signals / stop / yield / priority. Signal
  phases pair opposite approaches (4-way: [[0,2],[1,3]]) — a documented sequence, not a simulation.
- Placement (`docs/roads/PLACEMENT_RULES.md`): reserved zones first, then signs by condition, lights,
  furniture, trees; the block placed 90 items and skipped 66 with reasons (e.g. "reserved: junction
  sightline", "too close to light").

## E. Trees, landscape, materials
- `Tree_Variants` group (408 nodes) -> 12 species variants 2,160–7,764 tris, LOD1 272–1,336 tris
  (11–18 %), bark / foliage shaders, deterministic seeds (verified: same seed -> identical mesh).
- Materials: aggregate mosaic, repairs as rare sealed rectangles, cracks 1–2 cm, tire tracks / curb dirt /
  gutter wetness from the `lat`, `half_l/half_r`, `drain` attributes; presets clean / light_wear /
  heavy_wear; 10 materials baked to seamless 1K tiles (seam metric at noise level, see materials test).

## F. Regeneration and export (tools/roads/tests/street_block_test.py, all checks pass)
| test | result |
|---|---|
| lane count 1+1 -> 2+2 on the north street | width 16.1 -> 22.5 m, junction rebuilt, objects 122 -> 122 |
| lane / sidewalk width change | 16.1 -> 19.5 m |
| cycleway types None / Painted / Buffered / Protected / Two-Way | widths 14.5 / 16.1 / 16.6 / 16.6 / 18.2 m |
| moved approach + rebuild | objects 122 (no multiplication) |
| placement re-run with other spacing / seed / style | 87 placed, 55 skipped; placed set regenerated, not accumulated |
| disable scatter + lane lines | triangle count drops |
| junction surfaces | 0 downward faces |
Measured export (block): roads+junctions GLB 91,483 tris / 13 meshes / 20 materials (baked tiles),
collision 13,400 tris, props 90 nodes 64,313 tris (tree LOD1), signals 4 poles 19,240 tris with 9
materials incl. the 5 lens materials, JSON 6 roads / 28 lanes / 28 lane paths / 12 pedestrian paths /
7 crossings / 4 signals / 2 phases / 0 validation warnings. Godot 4.7.2: all GLBs load, scene size
392 x 181 m, collision ray on the avenue hits at the median top (0.47 m), green lens materials found and
toggled (4), captures `tmp/roads/v3/block_godot_*.png`. Build time of the node groups: ~104 s headless.

## Renders inspected (docs/roads/v3)
overhead layout, driver-height (south street), cyclist-height (avenue cycleway), pedestrian-height
(signal pole, crossing), crossing close-up (ramp, tactile domes, stripes), curb close-up, tree
close-up, material close-ups light vs heavy wear, taper, T-junction, S-curve, plus the Godot captures.

## Remaining limitations (honest)
- Lane transitions move the *edge*; a lane that ends has no explicit merge geometry for turn pockets,
  and transitions are per road (one taper per road).
- Roads must end at junctions (no mid-curve joins); junction surfaces are flat (roads flatten their crown
  into them); elevation differences up to 1.5 m are blended by the height locks, steeper cases error.
- Roundabouts and dead ends still use the v2 builders (no ramps / signals / bike continuation).
- Signal animation is a phase list in metadata; no Blender keyframe demo was produced; the game must
  drive the lens emission.
- Engine materials are baked tiles (position-dependent effects such as tire tracks and gutter wetness
  are Blender-only); props export with flat colours; trees' alpha leaf cards are dropped in the engine
  LOD (blob + frond canopies only).
- Node-group build is slow (~100 s) because Blender re-validates the tree on every link; iterate with
  the headless tests rather than the live MCP for full rebuilds.
- Regional sign standards are not claimed; a consistent original style is used.
