# G4 wheel assembly v0.4 — Godot 4.7.2 import validation

Asset: `world/vehicles/production/checkpoints/G4_wheel_v0.4/wheel_assembly.glb` (304,580 B, unchanged).
Handoff: `production/reports/g4_wheel_handoff.json`. Engine: Godot v4.7.2.stable.official (Forward+ for captures,
headless for the contract test). Test: `tests/wheel_import_test.gd`; captures: `tests/capture_wheel.gd`.

## Verdict

**Import contract: PASS, 54/54 checks** (`WHEEL IMPORT PASS: 54 checks, 0 failed`).
**Pipeline: one blocking defect** (checkpoint layout, below) and **two integration defects** (naming vs
`wheel_nodes()`, rolling radius) that must be solved before the assembly goes under the sedan.
**Materials: not ready** for the game lighting as exported (alloy/chrome/well read as one flat sky-grey).

## Blocking pipeline defect: `.blend` next to the GLB aborts headless import

`godot --headless --path . --import` scanned the checkpoint but produced **no `.import`** for the GLB. Log:
`ERROR: Blender path is invalid or not set ... Cannot configure blender path in headless mode.
(modules/gltf/editor/editor_scene_importer_blend.cpp:552)`. Godot's Blender import-support query runs when any
un-ignored `.blend` is in the reimport batch; when it fails the **whole batch is cancelled**, so nothing new in the
project imports (also `production/wip/sedan_v2_body.glb`, the G2 checkpoints and `approved/G2_v2p`). The project
convention keeps `.blend` sources in `source/` folders with a `.gdignore` (10 such folders exist); the vehicle
checkpoints/wip/approved folders break it: `checkpoints/G4_wheel_v0.4/wheel_assembly.blend`,
`checkpoints/G2_v2n|G2_v2p/sedan_v2_body.blend`, `approved/G2_v2p/sedan_v2_body.blend`, `wip/*.blend`.

Fix (Mechanical Engineer / pipeline owner, pick one): move `.blend` files into `<folder>/source/` with a `.gdignore`,
or add `.gdignore` to `production/wip`, `checkpoints` and `approved` and keep only the GLB that the game references
outside them, or set `filesystem/import/blender/enabled=false` in `project.godot` (the project never imports `.blend`
directly). I did not change anything under `world/vehicles` or `project.godot`.

Consequence for this validation: the test loads the GLB through the runtime `GLTFDocument` (same parser as the
editor importer, no `.import` options such as LOD generation or mesh compression applied) and falls back to the
imported `PackedScene` automatically once an `.import` exists (`ResourceLoader.exists(path, "PackedScene")`).

## Contract test results (all measured in Godot)

| Check | Result |
|---|---|
| Node names | all 22 present: `WheelR`, `WheelPivot`, `HubStatic`, 8 LOD0 meshes, `WheelR_LOD1` tree with `_LOD1` suffixes; scene root `wheel_assembly` (Node3D) |
| Node types | `WheelPivot`, `HubStatic` are plain `Node3D`; all 8 meshes are `MeshInstance3D` directly under them; both pivots at identity |
| Hierarchy | `WheelPivot.parent == WheelR`; `HubStatic` is its sibling; Caliper, DustShield under `HubStatic` |
| Axle axis | Tyre mesh AABB size (0.2250, 0.6600, 0.6600) m, centre (0,0,0), node transform identity: thinnest = local X, width 0.225, diameter 0.66 in Y/Z. **Spin about local X is correct**; `rotate_x` in `player.gd` applies unchanged |
| Concentric spin | union AABB of the 6 spinning meshes before/after `rotate_x(PI/2)`: identical, max delta **0.0 mm** (limit 10 mm); Tyre/RimBarrel/BrakeDisc/CentreCap bbox centres 0.00 mm off-axis |
| Triangles LOD0 | Tyre 3456, RimBarrel 1344, RimFace 1216, BrakeDisc 1008, DustShield 260, LugNuts 160, CentreCap 144, Caliper 136 = **7724** (handoff 7724, 0 % delta) |
| Triangles LOD1 | 1024/336/240/320/160/130/60/44 = **2314** (handoff 2314, 0 % delta) |
| Materials | exactly the 7 slots: Rubber, RubberCut, Alloy, RimWell, Chrome, SteelDisc, CaliperDark (no duplicates, no `_001` renames) |
| LOD1 root | `WheelR_LOD1.position = (0, 0, -1.000)` in Godot space (Blender +1 Y → Godot −Z, as the handoff predicts); sibling of `WheelR` |

Imported material values (StandardMaterial3D from the glTF Principled values; all cull back, no clearcoat):

| Slot | Albedo | Metallic | Roughness |
|---|---|---|---|
| Alloy | #e7e7e6 | 1.00 | 0.25 |
| Chrome | #f9f9f9 | 1.00 | 0.08 |
| RimWell | #6f6f71 | 1.00 | 0.50 |
| SteelDisc | #b5b3b1 | 1.00 | 0.40 |
| CaliperDark | #5d5d5f | 0.00 | 0.55 |
| Rubber | #242426 | 0.00 | 0.90 |
| RubberCut | #0d0d0d | 0.00 | 1.00 |

## Captures (CedarNeighborhood, Atatürk Avenue, wheel at (3.0, 0.33, −300), yawed 90° so the face looks down the avenue, 1280×720)

- `tmp/wheel_godot_face.png` — 15:30, camera 1.6 m in front of the hub at hub height, after 60 frames of spin.
- `tmp/wheel_godot_34.png` — 15:30, camera at (+1.25, +0.42, −1.25) from the hub.
- `tmp/wheel_godot_lod1.png` — same three-quarter view, `WheelR_LOD1` shown in place of LOD0.
- `tmp/wheel_godot_night.png` — 21:00 (street lamps on, rain), face view.

Sampled pixel means (sRGB) from the face capture: sky (155,175,189); alloy blade (134,145,150); alloy hub plate
(170,181,187); chrome centre cap (179,188,194); rim well (99,102,104); tyre sidewall (48,49,49); shoulder (52,53,54).
Night: sky (14,29,50), alloy blade (13,25,40), tyre (0,0,0).

Observations:
1. **Rubber reads correctly.** Dark, slightly glossy shoulder, sidewall ribs, grooves and the decal ticks all read at
   1.6 m and in the three-quarter; no z-fighting of the RubberCut decals at this distance (5–15 m not yet checked).
   Sun shadow and contact look right.
2. **Alloy is a flat sky-coloured disc.** With metallic 1.0 and the sky as the only reflection source
   (`reflected_light_source = REFLECTION_SOURCE_SKY`, no ReflectionProbe near the street), the blades, hub plate and
   chrome lug nuts land within ~10 sRGB values of each other and of the sky; the 20 mm blade dish and the chamfers
   produce no visible shading, and the chrome parts are indistinguishable from the alloy. The design reads as "ten
   pale bars", which matches the visual-QA FAIL note on the rim face, and the materials make it worse.
3. **Rim well is too light and lets the sky through.** The well (metallic 1, #6f) renders as a pale ring; the barrel is
   an open tube behind the spokes, so on-axis you look through the gap between the disc (r 0.15) and the barrel
   (r ~0.215) to the background (trees/houses are visible through the wheel in the face zoom). On the car the arch
   liner must close this; standalone it is by design but the pale well amplifies it.
4. **Night**: the wheel becomes a black disc with the alloy picking up only ambient blue (13,25,40); chrome at
   roughness 0.08 has nothing to reflect. Acceptable for gameplay at distance, but the lamp pools do not pick out the
   rim at all.
5. **LOD1** holds the silhouette and the twin-spoke read at 1.6 m; grooves gone, blades flat-shaded. Fine for its range.
6. Placement note: at y = 0.33 the tyre bottom sits a few mm into the road surface in the face view (flat-looking
   contact). This is the capture's placement, not the asset; the car's `collision_lift` should set the ride height.

## Recommendations for the Material Engineer (values to try in Godot, this lighting rig)

- **Alloy**: albedo #c9cacc, metallic 0.85, roughness 0.38, **clearcoat 0.6 / clearcoat roughness 0.12**. A
  non-unity metallic restores a diffuse term so the dish and chamfers shade under the sun, and the clearcoat gives a
  tight sun highlight that the sky-only reflection cannot. Target: blade/plate contrast ≥ 25 sRGB values in the face view.
- **Chrome** (cap, lug nuts): albedo #e0e0e0, metallic 1.0, roughness 0.18 (0.08 is a pure mirror of a nearly uniform
  sky; a little roughness returns a readable gradient). Keep it visibly different from Alloy.
- **RimWell**: albedo #3a3a3c, metallic 0.6, roughness 0.65. A dark well is what gives the face its depth (visual QA
  1d) and hides the see-through tube.
- **SteelDisc**: albedo #8e8c89, metallic 0.9, roughness 0.55 (0.40 is too clean behind the spokes); a radial
  roughness texture later if the brake gets closeups.
- **CaliperDark**: fine as is, or lift to #6a6a6c with metallic 0.3 so it separates from the shadowed well.
- **Rubber**: keep. **RubberCut**: keep.
- Scene-side (Integration, not the material pass): one `ReflectionProbe` (box ~5×3×6 m, update once, interior off)
  parented to the car would give all four wheels a horizon/road reflection and fix the sky-mirror flatness without
  pushing the metallic values down further. Test with the current Alloy values before approving any new ones.

## Recommendations for the integration (4 wheels + HubStatic under SteerFrontL/R, WheelRearL/R)

1. **Naming collides with `CityAssets.wheel_nodes()`.** It collects every non-mesh `Node3D` named `Wheel*`
   recursively. On the raw scene it returns `["WheelR", "WheelPivot", "WheelR_LOD1", "WheelPivot_LOD1"]` (measured).
   Instanced as-is per corner the drive code would `rotate_x` both `WheelR` and `WheelPivot`: the tyre spins at 2× and
   `HubStatic` (caliper, dust shield) spins with `WheelR`. Rule: **exactly one `Wheel*` Node3D per corner, and it must
   be the spinning one.** Per the vehicle contract that node is `WheelFrontL/R` / `WheelRearL/R`, so in the car scene
   rename `WheelPivot` → `WheelFrontL` etc. and give the assembly root and the static hub non-`Wheel` names
   (e.g. `CornerFL` > `WheelFrontL` + `HubFL`), or re-parent the pivot and hub directly under `SteerFrontL/R`
   (front) and a `CornerRL/RR` empty (rear). Front: `SteerFrontL/R` yaws about Y (`player.gd` builds
   `rest * Basis(UP, angle)`), so the steer empty must sit at the kingpin/hub centre with `WheelFrontX` and `HubFX`
   both as children; the caliper then steers with the wheel, which is correct.
2. **Left wheels**: the asset is the right wheel (face +X, caliper +Z). **Do not use a rotation to mirror it.** The
   handoff's "180° about Z" (and a 180° yaw) both map local X to world −X, so `rotate_x(-distance/0.35)` spins the
   left wheels in the opposite sense to the right ones (visibly backwards), and the Z version also moves the caliper
   bosses upside down. A true mirror keeps the spin sense (M·Rx(θ)·M = Rx(θ) for M = diag(−1,1,1)), the caliper at
   the rear and the lettered sidewall outboard. Preferred: export a `WheelL` variant from Blender (mirror X, flip
   normals, same hierarchy) so the GLB stays winding-clean. Fallback: `scale.x = -1` on the left corner node; Godot 4
   renders negative-determinant instances with flipped front faces, but confirm once in `capture_car.gd` that the
   left tyre is not inside-out and that the caliper sits at the rear.
3. **LOD1**: strip `WheelR_LOD1` (sitting at (0,0,−1)) from the per-corner instance or move it into a `visibility_range`
   setup: give the LOD0 meshes `visibility_range_end = 25` and the LOD1 meshes `visibility_range_begin = 25` with
   `visibility_range_fade_mode = VISIBILITY_RANGE_FADE_SELF`, and place `WheelPivot_LOD1` under the same spinning node
   (one `Wheel*` node per corner still holds). Never leave the LOD1 copy at its export offset.
4. **Rolling radius**: `player.gd:199` uses `/ 0.35`; the imported tyre radius is **0.330 m** (AABB 0.66). Use 0.33 (or
   read it from a glTF extra `tyre_radius` next to `wheelbase`) or the wheels under-rotate by 6 %.
5. **Arch liner**: the rim barrel is an open tube, so the sedan body needs inner arch surfaces behind each wheel or
   the road shows through the spokes on the inboard side.
6. **Dust shield** shares the `Rubber` slot (visual QA item 11); if `CityAssets.tint`-style overrides ever touch
   tyre materials by name, the shield will follow. Separate slot recommended before the material pass.
7. Reimport check after the `.blend` fix: `godot --headless --path . --import`, then
   `Godot_v4.7.2-stable_win64_console.exe --headless --path . --script res://tests/wheel_import_test.gd` must print
   "Loading imported PackedScene" and still pass 54/54 (triangle counts may change if the importer generates LODs;
   the test reads surface index counts of the imported ArrayMesh, so compare against the handoff with the 2 % tolerance).

## How to rerun

```
"C:\Godot\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe" --headless --path . --quit-after 2000 --script res://tests/wheel_import_test.gd
"C:\Godot\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe" --path . --script res://tests/capture_wheel.gd
```
