# Delivery Simulator 2026 — project instructions

Godot 4.7.2 (Forward+) delivery game. Assets are built procedurally in Blender 5.2.2 from
Python scripts and exported as GLB; the game loads them through `CityAssets`/`LivingAssets`.
Tests: `tests/run_tests.ps1` (headless Godot suites). Captures: `tests/capture_*.gd`.
Project history and system notes: `docs/PROJECT_STATE.md`.

## Blender / Godot pipeline rules
- Live Blender MCP (`mcp__blender__*`) drives the user's running Blender: build in a dedicated
  collection, never clear the scene. Full rebuilds run headless:
  `blender --background --factory-startup --python <script>` (Blender at
  `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe`).
- glTF export: Blender +Y forward becomes Godot -Z forward; Y-up. Units are metres.
- After changing a GLB, reimport: `Godot --headless --path . --import`, then run the tests.
- Godot 4.7 GDScript is strictly typed: give untyped dictionary/array values explicit types.

## Vehicle production system (vehicle_agent_system/)
The specialist agents in `.claude/agents/` (reference-engineer, body-surface-engineer,
exterior-detail-engineer, mechanical-engineer, interior-engineer, material-engineer,
visual-qa, game-asset-engineer) follow `vehicle_agent_system/CLAUDE.md` with these project
overrides:
- Target engine is **Godot 4.7.2**, GLB export (not Unreal). Vehicle contract:
  wheels are empties named `WheelFrontL/R`, `WheelRearL/R` (spin about local X), front wheels
  nested under `SteerFrontL/R` (yaw), `SteeringWheel` empty turns about its local Z, paint
  meshes carry `VehiclePaint` in their node name (`CityAssets.tint`), glTF extras on the root
  node (`wheelbase`, `collision_lift`) are read as metadata. Drive/steer code: `actors/player.gd`;
  contract test: `tests/car_steering_test.gd`.
- Production files live in `world/vehicles/`: build scripts, `production/reports/` (handoff
  JSON, audits), `production/renders/` (7-view QA renders from `qa_render.py`),
  `production/references/` (reference images and the dimension sheet).
- Gates G0–G8 apply; QA renders (`qa_render.py`) are required evidence at every geometry gate.
  Never claim visual quality without inspecting rendered output. Keep prior approved versions.
