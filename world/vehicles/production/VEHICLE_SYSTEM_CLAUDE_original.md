# Vehicle Production System — Claude Code

Mission: build realistic, game-ready passenger vehicles using Blender MCP and Python, with independent quality gates. Target engine: Unreal Engine unless the active project explicitly specifies otherwise. Do not assume Blender MCP can do an operation; discover available tools and fall back to Blender background Python if appropriate.

## Non-negotiable rules
- Do not call a car finished based on silhouette alone. Reject primitive-looking body shells.
- Preserve source scenes, references, and prior approved versions. Never destructively overwrite approved artifacts.
- Use real, internally consistent orthographic references and a dimension sheet. If references conflict, log the conflict; do not invent dimensions as facts.
- All parts must have explicit ownership, stable names, units in meters, and versioned exports.
- Geometry quality before microdetail; do not use texture to disguise poor geometry.
- Do not subdivide indiscriminately. Evaluate curvature, shading, panel continuity, silhouette, and topology.
- Render front, rear, left, right, top, front 3/4, rear 3/4 under neutral studio lights at every geometry milestone. Compare against references.
- QA agent is independent of creator. A failed gate blocks downstream work. Limit repair loops to 3 per gate before escalating with evidence.
- Separate wheels, doors, hood, trunk, steering wheel, and other animated components with correct pivots.
- Prefer geometry-based and physically based materials over fake detail. Document any texture baking and LOD compromises.
- Treat TRELLIS-generated geometry as optional candidate input, not automatically approved. Never replace failed generated geometry with crude primitives and claim success.
- Validate export by re-importing into a clean Blender scene and target engine when tools allow. Record actual checks versus unverified ones.
- Avoid licensing/trademark risks: use fictional vehicle styling unless user supplies licensed designs.

## Pipeline and gates
G0 Discovery: inspect project, MCP tools, Blender version, references, target engine and performance budgets; create production manifest.
G1 Reference: consistent orthographic image set, dimensions, landmark coordinates, camera calibration; block on inconsistent source views.
G2 Proportions: body silhouette, wheelbase, overhangs, roof line, greenhouse, track; neutral clay renders; QA approval required.
G3 Body surfaces: hood, roof, fenders, doors, bumpers, wheel arches, glass openings, panel gaps; curvature and reflection-strip QA.
G4 Assemblies: wheels/tires/brakes, lights, grille, mirrors, handles, trims; detailed close-up renders.
G5 Interior: dashboard, seats, steering, doors and visible cabin; driver camera QA.
G6 Materials: layered paint, glass, rubber, plastics, metals, light assemblies; neutral HDRI and varied lighting QA.
G7 Game-ready: clean topology, material consolidation, texture budget, LODs, collision, pivots, correct scale and orientation.
G8 Integration: GLB/FBX as appropriate, import validation, wheel rotation and suspension attachment checks, performance report.

## Handoff contract
Each agent writes `reports/<stage>/<component>_handoff.json` with: component_id, source_blend, export_path, version, units, coordinate_system, bounds_m, triangle_count, material_slots, pivot, reference_ids, renders, known_defects, QA_status, tests_run. No undocumented assumptions.

## Quality gates
- Proportions: compare dimensionless ratios and measured landmarks against agreed references; no visually obvious mismatch.
- Body: no faceted or lumpy shading, unwanted intersections, collapsed surfaces, pinching, obvious asymmetry, or disconnected glass openings.
- Functional: wheels separate, circular and concentric, correctly aligned, rotation axes consistent; moving panels separated if required.
- Details: assemblies modeled with credible depth and layered structure; not painted rectangles or featureless blocks.
- Materials: PBR maps connected and texture resolution appropriate; metallic/roughness response checked in multiple light setups.
- Export: target engine can import; pivots, normals, materials and scale retained; LODs and collisions verified.
- Performance: actual triangle counts, draw calls, texture memory and test FPS measured where possible; do not invent values.

## Execution policy
Before any modeling, deliver an audit and G1 reference pack. Work incrementally; checkpoint each accepted stage. Parallel agents may research or create separate files but must never concurrently edit the same .blend. Director merges only QA-approved components. Summarize progress with evidence, not optimistic claims.
