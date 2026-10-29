# Mert Road Studio v5: completion report (2026-10-28)

Brief: continue from v4, preserving the working systems. Visual quality and real traversal in Godot come before
new generator features, judged on rendered and traversed evidence rather than asset counts or clean imports.

## Evidence
- **Blender validation:** `tools/roads/tests/street_block_v4_test.py`.
  - Builds the library base from a factory scene, then the block.
  - Runs 16 regeneration scenarios, including the frontage move.
  - Exports, renders day and night, then saves and reopens the `.blend` in a second process.
  - Reports `STREET_BLOCK_V4 OK`. Results are in `tmp/roads/v5/final/street_block_v4_results.json`.
- **Godot:** all on Godot 4.7.2, D3D12, RTX 3070 Laptop, 1280x720 and 1920x1080, MSAA 4x.
  - `tests/capture_street_block_v4.gd`: 23 views, the same cameras as Blender, day and night.
  - `tests/traverse_street_block_v5.gd`: swept bodies plus a 5 cm lip scan.
  - `tests/record_street_block_v5.gd`: Movie Maker recordings.
- **Asset package:** `tools/roads/tests/asset_library_test.py`, which builds the package and checks it in a fresh file.
- **Full run:** `bash tools/roads/tests/run_v5_evidence.sh`.
  - Outputs: `tmp/roads/v5/final/` (renders, `godot/`, `compare/`, `traversal/`, `rec/*.mp4`, the `.blend`).
  - Images: `docs/roads/v5/`.
- **Game suites:** `tests/run_tests.ps1 -HeadlessOnly` reports HEADLESS SUITES PASS.

No parity with City Road Maker is claimed. There is no directly comparable evidence (same scene, same views).

## 1. Trees and foliage (Blender / Godot consistency)
Details are in `docs/roads/FOLIAGE.md`. The harness renders 101 identical shots in both engines (5 species, 6 distances, 3 eye heights, plus hedges) under a matched light rig. A grey calibration sphere agrees to 0.5 %. Values are ratios to Blender LOD0.

| | v4 | v5 |
|---|---|---|
| Godot LOD0 coverage / luminance | 0.81–0.99 / 1.15–1.32 | 0.96–1.02 / 0.96–1.04 at every distance and height |
| LOD1 at 70 m | kit LOD1: 1.20 coverage, silhouette IoU 0.77–0.83 | MRS LOD1: 0.97–0.99, luminance 0.99–1.01 |
| impostor at 200 m | 0.92 / 1.51; X-shaped from above (0.41 coverage) | hemi-octahedral 8x8 views: 0.97–1.00 / 0.99, IoU 0.88–0.91 at every elevation |
| automatic LOD | trees missing (0.46 at 40 m, 0.22 at 120 m) | 0.97–1.03, no gaps |
| pop per 2 m dolly step | up to +49 % coverage, one tree vanished at 128 m | 1.6–2.7 % (movie pop index 1.92 to 1.05) |
| hedge / boxwood luminance | 0.044–0.060 (near black) | 0.135–0.17, Blender and Godot within 3 % |

- **Causes found:**
  - EEVEE barely lit translucent leaves from the sky, making canopies 22 % darker.
  - Godot lacked the translucency and back-face crown normals.
  - Blender alpha has no mips; Godot now uses mip-compensated alpha-to-coverage.
  - LOD0 and LOD1 sat on different cell grids, which caused the missing trees.
  - The hedge textures themselves were too dark.
- **LOD bands:** LOD0 to LOD1 at 75 m (12 m dithered crossfade), LOD1 to impostor at 175 m.
- **Godot node:** `world/roads/mrs_foliage.gd` (`MrsFoliage`), now used by `MrsStreetBlock.plant()`. `{"foliage": "v4"}` keeps the old path for comparisons.
- **Cost:** GPU +0.2 to +1.1 ms per view, because canopies keep their coverage at distance and mid-distance trees now cast shadows.
- **Recordings:** street walk, a 10–250 m dolly and a deck pan, before and after plus side by side, in `tmp/roads/v5/foliage/video/`; also `docs/roads/v5/rec_trees.jpg`.

## 2. Landscape material export
The flat green Godot ground is replaced with the same blend in both engines:
- `tools/roads/mrs/ground.py` paints a 0.25 m block mask:
  - soil for beds and tree bases;
  - wear at access points, path edges and ends, bus stops and footbridge foot paths;
  - macro lush and dry variation.
- Three seamless tiles (grass, soil, worn) are baked from the embankment material.
- Ground mesh: a coarse 8 m grid with metre UVs and mask UV2.
- `world/roads/mrs_ground.gdshader` reproduces the Blender node blend; large-scale variation stays separate from fine detail.
- See `compare_park.jpg` and `compare_tree_close.jpg`.

## 3. Collision misses and real traversal
**The five v4 ray misses** (231 of 236 hit) were real gaps, not exact-edge hits:
- **Seam gaps:** junction edges sat at the straight-line trim, but roads end at their arc-length trim, leaving 1–4 cm gaps.
  - *Fix:* `junction._actual_ends` fits each road's evaluated end cross-section from its last station's vertices.
- **Corner step:** junction corners stood at 0.15 m against ramped road sidewalks at 0.099 m.
  - *Fix:* corner heights now slope to the road's ramp height at both ends.
- **Park path tip:** fixed by the path rule below.
- **Result:** Godot collision rays hit at **260 / 260** route points, and the v4 probe points hit at 0, ±1 and ±5 cm offsets.

The v5 tests found more defects, each fixed in the surface rather than the tolerance:

| defect (found by) | fix |
|---|---|
| T-junction corner: a 0.7 m strip of bare ground beside the S-curve sidewalk (Blender ray grid) | end section fitted from the mesh; the centre-line chord tangent was off on the curved road |
| protected-cycleway separator 10 cm high across the crossings (Blender ray probe) | separator heights scale with the crossing and driveway drop |
| park path started on the footbridge's raised approach path: a 12 cm upstand, then 30 cm down (lip scan) | path start chosen by rule: clear of footbridge approach paths and of any structure under 2.5 m headroom (`samples._clear_of_footbridges`) |
| 3 cm lips at refuges and crossings: 2.5 m preview stations cannot represent 2.5 m ramps (lip scan) | game export evaluates roads at Final quality, 1 m stations (+23 % triangles) |
| 3 cm cracks at the T-junction after `rebuild_all()` ran with another scene active (lip scan in the full run) | each road is evaluated in a depsgraph of its own scene (`junction._road_depsgraph`); fallbacks are logged |
| capsule-only test hid lips under 0.2 m | new 5 cm lip scan of every path |

**Godot swept traversal** (`traverse_street_block_v5.gd`): kinematic `move_and_collide` steps (lift, horizontal move, drop) along every route:

| body | paths | ok | largest step |
|---|---|---|---|
| pedestrian capsule (r 0.28, step 0.2 m) | 86 (sidewalks, corners, crossings, ramps, park paths, entrance, footbridge stairs / ramps / deck) | 86 | 0.113 m (stair risers) |
| cyclist (r 0.30, step 4.5 cm) | 32 (cycleways, junction bike movements, footbridge ramps) | 32 | 0.018 m |
| car box (1.9 x 4.4 m, 12 cm clearance, step 7 cm) | 42 (18 lanes, 22 junction movements, 2 driveway accesses) | 42 | 0.022 m |

- **Lip scan:** floor height every 5 cm along all 134 paths. **No jump over 2 cm**; the largest is 1.1 cm, at a ramped corner and a refuge edge.
- **Route-point heights:** stored z differs from the floor by up to 0.26 m where a straight node-to-node route line crosses a dip such as the driveway. The traversal and lip scan follow the floor and pass.

## 4. Route network verified geometrically
`tools/roads/mrs/movements.py` (new) builds the movements from the road geometry:
- **Lanes:** per-side polylines following tapers.
- **Lane use:** single lanes take every move; the inner lane goes straight or turns across; the outer lane goes straight or turns kerbside.
- **Turns:** cubic Bezier turns from the stop point.
- **Clearance:** each path is swept on the real surfaces (footprint ray casts with allowed surface kinds) and checked for minimum radius (car 4.5 m, bike 2.5 m).
- **Signals:** each movement links to its signal ID and phase.
- **Pedestrian corners:** they follow the junction's walking line.
- **Bicycles:** graph links are ridden paths or explicit two-stage links.

| | result |
|---|---|
| lanes | 18 |
| vehicle movements | 24 / 24 clear: 22 at junctions (6 left, 10 straight, 6 right; 15 signalised) plus 2 driveway accesses |
| bicycle movements | 8 / 8 clear (straight and kerbside right; lefts are two-stage) |
| walking edges swept in Blender | 65 / 65 |

**Recording `rec_junction`:**
- **Car:** follows the avenue lane and the straight movement. It stops at its stop point on red, waits 8.3 s, and goes on phase 1.
- **Cyclist:** stops at the cycle stop line (waits 8.0 s) and goes with the same phase.
- **Pedestrian:** crosses the avenue on the crossing that walks with phase 0 (the signal's `pedestrian_crossing`), in front of the waiting car.
- **Signals:** green per phase is 2 and 2, with no conflicting greens.

## 5. Night lighting from reachable views
- **Budget:** 57 light records (24 street-light spots, 29 omni incl. the deck LEDs, 4 shopfront downlights). At most 4 cast shadows; 2 did in the measured views. Lights fade by distance; 37 are in range of the deck.
- **Night GPU time:** 3.2–8.3 ms per view (deck 3.3, bus stop 7.4, aerial 8.3).
- **Coordinated emission:**
  - The shop's city-kit windows light with the street lights through the downtown window shader's `night` parameter.
  - In Blender the kit glass glows at an exposure-correct strength.
  - The footbridge deck lights now use the 3000 K of their light records in Blender too; the deck was white in Blender and warm in Godot.
- **Lantern:** four real transparent panes (hardware polish).
- **Glazing:** the loader gives every glazing material (bus shelter, lantern, footbridge glass) a depth pre-pass. The shelter panes are closed 12 mm boxes, so both faces show and overlapping panes resolve consistently.
- **Images:** `compare_bridge_3_deck_night.jpg`, `compare_busstop_night.jpg`, `compare_shop_front_night.jpg`, `compare_aerial_bridge_night.jpg`, and `rec_night.jpg` (sidewalk under the lights, then the deck).

## 6. Older assets polished
Details are in `docs/roads/HARDWARE.md`; see also `hardware_*.jpg`.
- **Streetlights:** flange plates and bolts, weld collars, service doors, galvanised or painted shafts, swept arms, a lofted luminaire with fins and a bezelled lens, and an LED dot array.
- **Barriers:** a real W-beam with splice bolts, a jersey with drainage slot and lifting anchors, and a parapet with drip grooves and rain streaks.
- **Signs:** galvanised posts with band clamps, rolled-rim aluminium blanks, and double-sided street blades, baked onto a 2048² sign atlas at 424 px/m.
- **Signals:** base plates, flange joint and clamps, push buttons, back plates with a reflective border, and visors.
- **Footbridge materials:** six tileable hardware materials: painted steel, galvanised, stainless, precast concrete, anti-slip deck and LED diffuser.
- Wear is restrained and material separation is real; there is no uniform white and no blanket noise.

## 7. One real street frontage
Details are in `docs/roads/FRONTAGE.md`; see `compare_shop_*.jpg`, `frontage_rules_adapt.jpg` and `rec_frontage.jpg`.
- **The building:** "Halden Grocer, 24 Maple St", built from the game's existing city-kit modules under the `district.gd` rules: storefronts, entrance, apartment bays, awnings, parapets, corner posts and a shop room behind the open door. Godot maps every `Kit*` surface to `CityKit.material`.
- **Signage:** fascia lettering and an enamel address plate beside the door.
- **Delivery destination:** the entrance anchor becomes a pedestrian-graph node and a `Marker3D` in group `mrs_destinations` with address, door, facing and service access.
- **Service access:** a real **dropped kerb** through the new `Driveways` road input. The kerb drops to 6 mm with a concrete apron across the sidewalk (kind 11), then a sloped yard with a loading box, roller door and "DELIVERIES 24" panel. Both `access_in` and `access_out` are swept clear.
- **Nearby:** a second bus stop (S2, shelter, pole and information board) about 26 m from the door, and a bike rack 5 m from the entrance.
- **New rules:**
  - building footprints are keep-out areas;
  - an active frontage strip keeps cabinets and bins off the shop windows;
  - the driveway envelope is the driveway width plus its flanks;
  - entrances attract bike racks;
  - the bus pole steps back if a sign holds its spot.
- **Rules adapt:** moving the shop from station 22 to 14 m and regenerating moved the driveway (34.5 to 26.5 m), the kerb drop, the entrance envelope and the rack. No item ended up inside an envelope, and both access movements stayed clear. Restored, the object count was unchanged at 441.
- **Recording:** a delivery van follows `access_in` into the yard while the camera walks behind a shopper from the bus stop to the door.

## 8. Packaged system
Details are in `docs/roads/ASSET_LIBRARY.md`; see `asset_library_thumbnails.jpg`.
- **Contents:** 111 assets in 9 catalogs: Roads 6, Footbridges 3, Furniture 20, Lighting 6, Signs 31, Barriers 6, Trees 26, Plants 12, Buildings 1.
- **Metadata:** rendered thumbnails, descriptions, tags and stable catalog UUIDs.
- **Package:** one `.blend` with all 107 images packed (80 MB), next to `blender_assets.cats.txt`.
- **Procedural controls:** the road and footbridge Geometry Nodes modifiers stay live.
- **Fresh-file test:** in a factory-startup file every asset appends and evaluates with no missing images.
  - Urban road: lanes 1 to 3 widen it 32.2 to 35.7 m; sidewalk 5 m widens it to 37.2 m; a protected cycleway adds 116 triangles.
  - Footbridge: Girder to Truss changes 53,032 to 54,088 triangles.
- **Repository:** the 80 MB library is regenerated by the test into `tmp/roads/v5/library/`. It is not committed, to keep LFS small.

## Regeneration (full run, every scenario re-solves junctions where needed, footbridge, frontage, placement, ground, routes, movements)
| scenario | placed | objects | ped. components | narrow edges | overlaps |
|---|---|---|---|---|---|
| baseline | 243 | 441 | 1 | 0 | 0 |
| north 2+2 lanes, back to 1+1 | 245 / 243 | 444 / 441 | 1 | 0 | 0 |
| south sidewalk 3.2 m (shelter skipped with reason), back to 4.6 m | 238 / 243 | 438 / 441 | 1 | 0 | 0 |
| avenue E cycleways painted / buffered, back to protected | 242 / 243 | 440 / 441 | 1 | 0 | 0 |
| T-junction moved 4 m, restored | 245 / 243 | 444 / 441 | 1 | 0 | 0 |
| tree spacing 9 m and lights x0.8, restored | 262 / 243 | 478 / 441 | 1 | 0 | 0 |
| footbridge anchor -22 m, restored | 244 / 243 | 444 / 441 | 1 | 0 | 0 |
| placement seed 11, back to 7 | 245 / 243 | 441 / 441 | 1 | 0 | 0 |
| shop moved 22 to 14 m, restored | 243 / 243 | 441 / 441 | 1 | 0 | 0 |

The saved `.blend` (40 MB) reopens in a second process with 441 objects, the node groups and 4 scenes.

## Performance (Godot, measured per view; frames are vsync-capped at 16.7 ms)
| view | GPU ms | CPU ms | draw calls | primitives |
|---|---|---|---|---|
| overhead | 3.5 | 1.1 | 1,208 | 0.81 M |
| aerial over the footbridge | 4.8 | 1.3 | 1,418 | 2.01 M |
| pedestrian on the avenue | 4.3 | 1.1 | 1,160 | 1.46 M |
| cyclist | 5.6 | 0.7 | 634 | 0.50 M |
| footbridge deck | 3.1 | 0.6 | 398 | 0.63 M |
| footbridge stairs (worst day view) | 9.2 | 0.9 | 1,054 | 1.18 M |
| park | 7.6 | 0.7 | 766 | 1.57 M |
| shop front | 2.9 | 0.5 | 298 | 0.32 M |
| shop yard (elevated) | 7.0 | 0.9 | 896 | 0.88 M |
| night: deck / bus stop / avenue / aerial | 3.3 / 7.4 / 6.3 / 8.3 | 0.8–1.4 | 641–1,514 | 1.1–2.4 M |

- **Block load:** 2.4 s.
- **Exported sizes:**
  - Main GLB: 55 MB, 120 k triangles (Final quality; it was 97 k at Preview).
  - Collision: 48 k triangles.
  - Props: 21 MB, 138 k triangles.
  - Signals: 6.5 MB.
- **Scene content:** 66 trees and 2,056 plants in 283 MultiMeshes.

## Remaining limitations
- **Paving speckle:** at mid distance in shade, Godot paving shows a fine dot pattern. The baked tile's joint crossings carry small dark corner chips that survive mipmapping. It is not a normal, AO or filtering issue (all three were tested). Fix: a cleaner paving bake.
- **Metal and ambient:** galvanised railings read darker in Godot than in EEVEE (metal reflecting the procedural sky). The capture environment's sky ambient is raised to 3.0 to match EEVEE's world, from the grey-sphere measurement; it is not identical lighting.
- **Window interiors:** Godot uses the downtown window shader (varied lit interiors); Blender shows a uniform warm glow.
- **Delivery destination:** a marker with metadata. It is not wired into the game's mission and dispatch system, whose addresses live in the residential layout.
- **Driveway exit:** `access_out` assumes the vehicle has turned in the 9 x 12 m yard; the three-point turn is not modelled.
- **Other junction types:** roundabouts and dead ends do not use the end-section fit and were not lip-scanned (only the four-way and T-junction on this block were).
- **Size:** hardware atlases are embedded separately in the props and signals GLBs (signals 1.1 to 6.5 MB). Streetlights are 2–3 k triangles each with no LODs.
- **One GPU outlier:** the footbridge-stairs view (9–14 ms across runs) is unexplained.
- **Hedges:** hedges are not placed on this block (placement uses shrubs for hedge layers).
- **Asset library:** generated, not committed (80 MB).
