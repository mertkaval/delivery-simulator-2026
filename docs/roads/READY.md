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
- Limit = last value passing every check, minus a safety margin (about 10 % of the range).
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
| B3 | terrain and bridges: conform, batters, cut / fill, deep cut, bridge / tunnel settings | to do |
| B4 | area-junction workflow: tongues, radii, extensions, custom sign, marking lines | to do |
| B5 | placed objects: signs, signals, lights, trees, furniture, bus stops: no conflicts, no strange placements | road-placed objects done (surface-following, priority clearance, scatter clearance); placer signs / bus stops: to do |
| B6 | apply: socket min / max with margin, combination warnings, validator rules, LIMITS.md | to do |
| C | city: junction reach at acute angles + junction merging from one shared reach rule; rebuild the roads-only city; 0 problems; install; Godot tests; commit | to do |
| D | user guide + example scenes | guide + add-on written (docs/roads/USER_GUIDE.md, tools/roads/addon); example scenes to do |
| E | full test suite (tool + Godot), final commit | to do |
