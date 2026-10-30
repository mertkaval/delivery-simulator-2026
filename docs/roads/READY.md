# Mert Road Studio: road to "ready to use"

Workflow (user's choice, 2026-10-29): **option 1**. The tool builds in Blender; Godot only imports, with no fixes and
no logic of its own. The Godot import is the acceptance test.

## Done means (user's definition)
1. The roads-only Port Halden city is built by the tool, has 0 Blender validation problems, is installed in Godot, and
   passes the Godot tests.
2. The tool is usable by the user alone: a user guide plus example scenes.
3. The area-junction work (City Road Maker 2.1 reconstruction) is finished: comparison renders, validation report,
   committed.

## Rules for parameter limits
- Every hand-set parameter gets a tested range: dense sweeps, the boundary refined and confirmed across scenarios
  (straight / curved / sloped / junction), never the first failure alone.
- Limit = last value passing every check, moved inward by 10 % of that boundary value (user's answer, 2026-10-29;
  at least 1 mm, whole steps for integers). Boundaries are bisected to 1 % of their own value.
- Combinations that fail are reported as a warning on the modifier and a validator failure (never auto-corrected).
- Scope: roads, junctions, terrain and bridges, the area-junction workflow, every placed landscape object (no strange
  placements, no conflicts).
- Evidence for every limit lives in `docs/roads/LIMITS.md` and `tmp/roads/limits/*.json`.
- No major updates; existing tests stay green; anything unclear is asked, not assumed.

## Phases
| phase | content | status |
|---|---|---|
| A | finish the area-junction work: reconstruction scene, renders, comparisons, VALIDATION.md, commit | done (9 defects found and fixed, see crm_reconstruction/VALIDATION.md) |
| B0 | sweep harness: one Blender process builds a scene per value, runs the checker suite, refines boundaries | done: tools/roads/limits (checks proven by detector_test.py; self-test green on furnished roads) |
| B1 | roads: lanes, widths, sidewalks, curbs, bike / parking / bus lanes, median, curvature, grades, transitions | to do |
| B2 | junctions: corner radius, approach angles, number of arms, crossing widths, controls | done: 1008 builds; acute-corner trim fixed; paint-zone spacing rule (refuse / validate / city merge); no geometric failure left |
| B3 | terrain and bridges: conform, batters, cut / fill, deep cut, bridge / tunnel settings | done: terrain_sweep.py, 11 inputs of MRS_TerrainConform on the mountain road, one passing region each (minimums: Sink 2.5 cm, Cut Slope 0.70, Fill Slope 0.26, Edge Band 1.9 m, Subdivide 1 ...); bridge / tunnel inputs are MRS_Road inputs (B1) |
| B4 | area-junction workflow: tongues, radii, extensions, custom sign, marking lines | done: area_sweep.py, 84 inputs of 5 groups; 19 tested limits (sign content and line offsets depend on the panel / Road Size: combination warnings instead of single limits) |
| B5 | placed objects: signs, signals, lights, trees, furniture, bus stops: no conflicts, no strange placements | road-placed objects done (surface-following, priority clearance, scatter clearance); placer: validator check_placed (placed_conflict / placed_road / placed_ground / placed_building) found and the tool now fixes: furniture sunk 0.14 m into the pavement (paint-only stations in the cross-sections), a kerb ramp in surface_z (now an exact ray onto the road's top faces), mulch rings over furniture pads (a tree occupies its mulch bed, pads are reserved); junction test scene: 855 placed objects, 0 problems, every base within 3 mm of its surface |
| B6 | apply: socket min / max with margin, combination warnings, validator rules, LIMITS.md | in progress: limits.json written by report.py --apply (12 tested limits: MRS_Road Lanes Backward / Object Clearance / Resolution, MarkingLines Edge Width, 8 TerrainConform inputs; bend rule R >= 1.076 x inner half width from bend_sweep.py); combination warnings on MRS_Road (bend, taper past the end, forbidden gaps), MRS_CustomSign (content off the panel), MRS_MarkingLines (line off the road); validate reports `warning`; library v27 rebuilding; Planting Strip L / R to re-sweep on v27 |
| C | city: junction reach at acute angles + junction merging from one shared reach rule; rebuild the roads-only city; 0 problems; install; Godot tests; commit | done (2026-10-30): designed street grades (0 over limit), level junctions, landing-aware profiles; validation 2115 -> 204 -> 23 -> 9 -> 0 problems over six rounds (last fixes: benches on city driveways, a tree bed past a strip's end); installed; every Godot suite passes |
| D | user guide + example scenes | guide + add-on written (docs/roads/USER_GUIDE.md, tools/roads/addon); 7 example scenes (Load Example in the panel), every one validates with 0 problems (tests/examples_test.py); add-on install test to do |
| E | full test suite (tool + Godot), final commit | done (2026-10-30): tool tests (junction rules, examples, responsive, terrain conform, bank, detectors, tongue, area junction, custom sign, marking lines, warnings, furniture, grading) and tests/run_tests.ps1 green on library v32 |
