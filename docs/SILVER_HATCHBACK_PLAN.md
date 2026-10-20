# Silver hatchback — inspection and pending generation

Update: the user subsequently supplied `car_model.glb`. That asset was repaired locally in Blender and made drivable in separate Godot track/city scenes; see `assets/vehicles/repaired_car/README.md` for delivered files, actual tests and remaining visual limitations. The Tripo generation below was never submitted.

Status, 19 October 2026: project inspected, Tripo authenticated, exact generation request dry-run validated. Account balance is 0, frozen credits 0. No generation submitted, no credits spent. Model creation, Blender preparation, integration and driving tests remain pending.

## Reference and preservation

Reference: `C:/Users/mert3/Downloads/Silver-gray compact hatchback reference.png`.
Silver five-door compact hatchback; no branding or text. Match body proportions, lamps, grille, mirrors, glazing, handles, seams, alloys and rubber tires. Review inferred rear/opposite side for consistency.
Original vehicles, catalog and default scene remain unchanged. New work belongs in `assets/vehicles/silver_hatchback/` and a separate test scene.

## Verified project contract

- Installed engine reported by Godot MCP and local executable: **4.7.2.stable.official.ed1daf0bf**. `project.godot` specifies 4.7 / Forward+, Windows D3D12, Jolt, 1280×720, MSAA setting 2.
- Controller: `actors/player.gd`, class `CourierPlayer`, `CharacterBody3D`. Existing arcade kinematic driving, not VehicleBody3D suspension. World metres, Y up, forward −Z, wheel axles local X.
- `CityAssets.create("hatchback")` loads `world/living_city/assets/compact_sport.glb` through `LivingAssets.scene`. Separate `assets/vehicles/silver_sedan/` also exists and must be preserved.
- Catalog body collision size: width 1.79 m × height 1.47 m × length 4.29 m, centred at half height + 0.06 m. Imported compact_sport geometry including protrusions actually spans (2.330, 1.521, 4.492) m, at AABB minimum (−1.165, −0.005, −2.262). Use nominal body dimensions and explicit mirror clearance rather than copying the oversized visual bounds indiscriminately.
- Imported compact_sport: **18,522 triangles**, 22 surfaces, four wheel pivots at x=±0.86, y=0.33, z=±1.31 m; front z negative. Names: WheelFrontL/R, WheelRearL/R. These were inspected in Godot, not inferred from reference image pixels.
- Current controller uses 2.7 m wheelbase, assumed 0.35 m wheel radius, acceleration 3.2 m/s², braking 10 m/s², forward cap 12 m/s and reverse cap 3 m/s. Match or explicitly adapt these to measured new axle centres/radius.
- `CityAssets.wheel_nodes` discovers non-mesh Node3D nodes named Wheel*. Use separate steering parents and axle-centred rotation nodes. Existing `SteeringPivot` controls only a single pivot; a local adapter must apply steering to two front wheels without orbiting them about the car centre.
- PBR uses StandardMaterial3D and shared shaders. `LivingAssets.scene` interns materials using names/scalars without texture paths, so load the new textured car directly in its own scene to avoid accidentally sharing mismatched maps.
- Documented whole-scene performance budgets: 2,000 draw calls, 3 million visible primitives, 512 MiB texture memory, 16.7 ms p95 target at 720p. Prior reports exceed the frame-time target in some views; these historical numbers are not new performance measurements.
- Proposed new-car runtime target: about 20,000 triangles LOD0, with lower LODs; 2K–4K runtime maps as needed, keeping 8K source maps. Final counts and visual quality must be measured after generation. Avoid trading body silhouette for a blind polygon target.
- Blender installed: **5.2.2 LTS**. MCP connection was unavailable during inspection; local executable works. Use an isolated background Blender scene/source without replacing a user's live scene.

## Validated Tripo request

One API call: `POST /v3/generation/image-to-model` using the reference image.
CLI alias `tripo-v3.1`, wire model `v3.1-20260211`.

```powershell
npx --yes tripo-cli@latest make 'C:/Users/mert3/Downloads/Silver-gray compact hatchback reference.png' --model tripo-v3.1 -p geometry_quality=detailed -p texture_quality=extreme -p texture_version=v3.5-20260815 -p delight=true -p texture=true -p pbr=true -p auto_size=true --name silver-hatchback -o assets/vehicles/silver_hatchback/source --dry-run --json
```

CLI returned valid=true, one candidate, no warnings/errors. It accepts Ultra geometry and extreme textures with the selected texture model. No paid conversion, segmentation or additional generation is included. Geometry starts as a high-detail source and is prepared locally.

Estimated cost from the installed plugin price table:

| Component | Credits |
| --- | ---: |
| v3.1 image-to-model, textured | 30 |
| Detailed geometry | 20 |
| Extreme / 8K textures | 20 |
| Total | **70** |

Actual billing must be read from the returned task record, not assumed equal to this estimate. Failed tasks release their held credits. Do not repeat paid generation without user approval.

## Deliverables and verification still required

- Retain generated source/task record under `assets/vehicles/silver_hatchback/source/tripo-out/` and editable Blender source under `source/`.
- Review front, rear, both sides, underbody and wheel close-ups. Repair warped panels, irregular wheels, fused components, texture artifacts and any branding.
- Four separate wheels, centred axle pivots; matched rotations/steering hierarchy; realistic paint/glass/rubber/metal/light materials; local portable textures, UV and normal checks, applied transforms, simplified collision.
- Export Godot-compatible GLB with LODs; supply vehicle scene and isolated driving scene using CourierPlayer with memory-only session state. No save writes.
- Verify acceleration, forward direction, braking, reverse, steering both ways, four wheel rotations and no wheel orbiting; collision obstruction and clearance; render day/night views and inspect materials.
- Report actual triangles, surfaces, texture resolutions, file sizes, performance and screenshots. Explicitly distinguish automated physics checks from visual review and unperformed human playtesting.

No new-car visual or driving checks have been performed because generation is blocked by the empty Tripo balance. The temporary existing-car inspection script is `tmp/inspect_hatchback_contract.gd`; its structural query completed, but the sandbox emitted a user-log-directory warning. It is not a driving or performance test.
