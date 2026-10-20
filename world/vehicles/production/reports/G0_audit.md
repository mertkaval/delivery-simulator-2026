# G0 — Discovery audit (2026-10-19)

## Project facts (verified)
- Engine: Godot 4.7.2 stable, Forward+ (project.godot `config/features`). Not Unreal.
- Blender: 5.2.2 LTS at `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe`; live MCP add-on 1.8 / protocol 13 connected
  (`get_addon_status`). Python 3.13.13 with numpy, mathutils, bmesh; no PIL/scipy. Render engines in the live session: EEVEE;
  Cycles with OptiX (RTX 3070 Laptop) available for bakes. Headless runs use `--factory-startup`.
- Vehicle contract in the game (`actors/player.gd`, `world/asset_library.gd`, `tests/car_steering_test.gd`): GLB with empties
  `WheelFrontL/R` under `SteerFrontL/R`, `WheelRearL/R`, `SteeringWheel`; wheel spin = rotate about local X, radius 0.35 m assumed by
  the spin code; paint meshes named `*VehiclePaint*`; glTF extras `wheelbase`, `collision_lift` on the root node become metadata.
  Camera distances: chase cam ~5 m behind, pedestrians/kerb views 2–15 m, traffic at 20–180 m (LOD needed).
- Performance budget (measured on the user's RTX 3070 laptop, `tests/capture_residential.gd`): residential views 7.7–10 ms median,
  ~2000 draw calls, ~1.3 M primitives. A hero vehicle may spend ~45–60 k triangles at LOD0 and must come with LOD1/LOD2.
- Agent system: 8 role definitions registered at `.claude/agents/` (tools extended with `mcp__blender__*`); project `CLAUDE.md` created
  (none existed) with the Godot overrides. Subagent files load at session start; this session uses the same role prompts through the
  general-purpose agent.

## Asset A — `car_model.glb` (supplied scan)
Renders: `production/renders/g0_scan/`. Metrics: 1 mesh, 404 598 triangles, 0 smooth faces, bounds 0.80 × 1.00 × 0.52 m.
- Toy proportions: wheel diameter 0.37 of length (real ≈ 0.135); width 0.8 of length (real ≈ 0.38). Non-uniformly squashed.
- Single fused shell: wheels welded into the body, no interior, opaque painted windows, no pivots → cannot spin or steer.
- Flat-shaded triangle soup, lumpy surfaces (see clay renders), scan noise on every panel.
- Texture: 4096² atlas of fragmented charts with baked lighting; ORM in a second map. Unusable for relighting.
Verdict: reject as geometry source; keep only as a styling reference. Preserved untouched at the project root.

## Asset B — `world/vehicles/player_sedan.glb` v1 (procedural, 2026-10-19 morning)
Renders: `production/renders/g0_sedan_v1/`. Metrics: 161 objects, 44 057 triangles, bounds 2.04 × 4.81 × 1.60 m (mirrors included).
What works: scale and wheelbase are real-world; wheels are separate with correct pivots; steering/spin verified in Godot
(`car_steering_test.gd` 36/36); transparent glass with an interior behind it; tints through `VehiclePaint`.
Defects (visual QA, clay renders):
1. Body is a featureless loft: no shoulder character line, no sill crease, no fender/arch flares, no hood-to-fender transition;
   the sides read as a slab and the nose as a rounded box. FAIL G3.
2. Greenhouse too small and too upright relative to the body; roof narrow; A/C pillars are only material bands, not geometry.
3. No real panel gaps: door "seams" are stuck-on strips; hood and trunk are not separated at all.
4. Lamps, grille and intake are surface-hugging bands without depth, bezels, lenses or internals. FAIL G4.
5. Mirrors are boxes; the LEFT mirror is missing from the export (only the right one is in the bounds: x max 1.078 vs min −0.961).
6. Wheel-arch liners extend 0.10 m below the ground plane (bounds min z −0.10).
7. Materials: paint has no flake/clearcoat layering in Godot (StandardMaterial from glTF), glass is a flat alpha tint.
8. Interior is boxes (dashboard, seats) — acceptable only as an occupancy placeholder.
Verdict: usable as the gameplay/integration skeleton (hierarchy, pivots, tests); body shell and details must be rebuilt.

## Reference pack
`production/references/ref_{front,rear,left_side,right_side}.webp` + `reference_pixel_measurements.json`. No top view supplied.
Known conflict: reference wheels are oversized (≈0.18 of length) and the two side views differ slightly; resolution and the dimension
sheet are the Reference Engineer's deliverable (`dimension_sheet.md/.json`).

## Prioritised plan
1. G1 dimension sheet (Reference Engineer) — targets labelled, conflicts logged.
2. G2/G3 body shell v2 (Body Surface Engineer, `sedan_body.py`): quad cage from design curves with landmark indices; creased shoulder and
   sill lines; wheel-arch flares; separated hood / doors / trunk / bumpers with real gap grooves; glass openings as geometry; subdivision
   with controlled creases; 7-view clay + reflection-strip renders; independent Visual QA PASS before G4.
3. G4 assemblies: layered lamps (housing, reflector, lens), grille with depth, intake mesh, mirrors, handles, wipers; wheels with
   tyre profile/tread, rim, brake disc and caliper.
4. G5 interior for the driver camera; G6 materials (clearcoat paint, glass, rubber, plastics, emissives); G7 LODs + collision; G8 Godot
   import + steering test + perf capture.
