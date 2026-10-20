# Repaired supplied car

Prepared from the user's `car_model.glb` in Blender 5.2.2 through Blender MCP, 19 October 2026. Original GLB preserved. No paid generation or external replacement asset was used.

## Play

Open `res://tests/repaired_car_city.tscn` and press F6 to drive in the full delivery city. This sandbox disables save writes and starts with the new car. The default game scene and shop vehicles remain unchanged.

For an empty collision/handling course, run `res://tests/repaired_car_track.tscn`.
W accelerates, S reverses, A/D steer, Space brakes, E enters/exits. The test course also supports R reset and Esc to release the mouse.

## Delivered files

| File | Purpose |
| --- | --- |
| `source/repaired_car.blend` | Editable model, separate wheel assemblies and pivots, packed original 4096×4096 textures |
| `source/normalized_original.blend` | Pre-repair inspection snapshot |
| `car_lod0.glb` | Close-up model, 82,111 triangles, 8,944,168 bytes |
| `car_lod1.glb` | Medium-distance model, 31,179 triangles, 7,430,780 bytes |
| `car_lod2.glb` | Far model, 10,624 triangles, 6,705,580 bytes |
| `repaired_car.tscn` / `.gd` | Reusable visual scene, LOD ranges and articulated wheel animation |
| `textures/body_albedo.png` | 2048×2048 runtime albedo atlas; embedded in exports as well |
| `textures/body_orm.png` | 2048×2048 original ORM reference; rebuilt materials use tuned scalar surface values |
| `asset_report.json` | Measured mesh counts and dimensions |
| `test_results.json` | Godot structural and driving checks |
| `city_test_results.json` | Full-city check and sampled performance |
| `previews/godot_*.png` | Actual Godot captures, including city and steering views |

Godot dimensions are 1.999 m wide including mirrors × 1.470 m tall × 4.289 m long. Y is up and −Z is forward. Four 0.34 m radius wheels rotate about local X; front steering parents rotate about Y. The actual axle spacing is 2.62 m. Each LOD has five mesh objects and 15 material surfaces. Detail switches occur at 24/60 m and visibility ends at 160 m.

## Repairs and integration

- Replaced fused oval wheels with four round tires, machined alloy spokes/rims, hubs, lugs and brake discs. Axle pivots are independent from steering parents. Front wheels use different inner/outer steering angles.
- Removed old wheel geometry, adjusted the arch shape and added stationary arch liners/undertray.
- Replaced cloudy window appearance with fitted dark glass surfaces and rubber seals. Glass is opaque reflective tint; there is no furnished transparent cabin.
- Validated duplicate/degenerate mesh data and normals, kept UVs, corrected scale/orientation, tuned paint/metal/rubber/glass response and exported portable GLBs. Final export runs had no invalid-mesh warnings.
- Reduced 404,598 source triangles to 82,111 near triangles (79.7% reduction), with two further LODs. This exceeds the earlier provisional 20k target: aggressive reduction damaged the body, grille and window borders. The new car is intended as the single player vehicle, not a high-volume traffic replacement.
- Added an optional scene override and metadata hooks to the existing `CourierPlayer`. Existing vehicles retain their previous code path. The new vehicle uses an inexpensive 1.80×1.47×4.29 m box for mounted and parked collision, rather than triangle-mesh collision. That shape includes wheel support and does not simulate the open underbody.
- Rolling uses actual signed travel distance and the measured tire radius, so reverse and forward wheel directions are correct. Steering does not orbit the wheels around the car centre.

## Actual validation

Godot **4.7.2.stable.official.ed1daf0bf**, Forward+, D3D12, Jolt.

- `tests/repaired_car_test.gd`: **74 checks, 0 failures**, exit 0. Covers imported scale/UV/materials/2K texture, axle orientation and centre stability, forward acceleration, reverse, braking, idle drift, both steering directions, obstacle collision, ground contact and entering/exiting.
- 3 s acceleration reached **9.6 m/s** and travelled **14.48 m**. Reverse capped at **−3.0 m/s**. Braking stopped the car. The front barrier stopped the root at **z=−52.604 m**, outside the obstacle.
- `tests/repaired_car_city_check.gd`: **PASS**, exit 0. Drove **4.752 m** in the actual city and braked to zero, mounted, with saving disabled.
- One warmed 1280×720 city view on the RTX 3070 Laptop GPU, 180 sampled frames: **8.256 ms median, 9.756 ms p95**, 1,536 draw calls, 1,148,438 visible primitives, 458.08 MiB texture memory. Within the documented per-view budgets. This is not an all-city or long-session frame-rate guarantee.
- Existing `bicycle_steering_test.gd`: **14 checks, 0 failures**, exit 0.
- Existing `lifestyle_test.gd`: **71 checks, 0 failures**, exit 0.
- Actual front/rear/side/steering and city screenshots inspected. The separate test renders used native Forward+ rendering, not headless visual approximations.
- The city sandbox was also launched through Godot MCP and subsequently exited with code 0. Existing project lint warnings remain; the new unused-parameter warning was corrected.

## Remaining limitations

The supplied generated body has a saloon-like rear, uneven panel seams, small shape ripples and baked texture distortions. Those remain visible in close-ups; this is an improved, drivable repair, not a hand-retopologized photorealistic automobile or an exact copy of the original hatchback reference. Tires and glass are newly constructed; body details largely retain the supplied asset's design.

Driving intentionally uses the existing arcade controller. No suspension simulation, tire forces, articulated doors, cockpit interior or damage system was added. Night lighting, extended slope/curb driving and human handling feedback have not been fully evaluated. Automated tests establish specific checks, not the absence of every possible defect.

## Rebuild

Run `tools/repair_car_model.py` then `tools/export_repaired_car.py` in an isolated Blender session. The first reads the original GLB and recreates the repaired geometry; the second prepares source/runtime assets and LODs. Do not run them in an unrelated unsaved scene: the repair builder replaces that session's scene contents.

Original GLB SHA-256: `31B4AFF80A64642200C5EB82182310F0273715DB074874C6F958FF995F4BCC4F`.
