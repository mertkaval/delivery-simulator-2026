# Delivery Simulator project state

## City kit — 13 October 2026

A Blender-authored modular building kit now covers all 87 downtown buildings and adds 34 new kit buildings: 14 terrace rows (79 homes), 4 walk-ups and 16 mixed-use corridor blocks. The pass also adds a seamless PBR material library, a sky-lit lighting setup, twelve new citizen designs with improved animation, and ambient VFX (fountains, steam, chimney smoke, birds, lamp halos and varied night windows). The city layout map is in `docs/city_map.png`. See [CITY_KIT_REPORT.md](CITY_KIT_REPORT.md) for the evaluation, rebuild commands, performance and limits. All delivery destinations, pickups and existing houses are unchanged. `tests/citykit_test.gd` passes 3,515 checks.

## Street kit — 10 October 2026

Cedar Lane, both side roads and the four cross streets (now continuing east to downtown at x = 120) use a Blender-authored street kit instead of flat boxes. `world/roads/build_road_kit.py` builds the pieces (run headless or through the Blender MCP); the source is `world/roads/source/road_kit.blend`. `StreetGrid` (`world/roads/street_grid.gd`) lays them out as batched MultiMeshes.

- Cedar Lane (12 m): double yellow centre line, 3.5 m traffic lanes, white edge lines, 1.7 m green bike lanes with bicycle and arrow symbols, gutter pans and bevelled curbs. Side and cross streets (10 m) use the same layout with 3 m traffic lanes and 1.45 m bike lanes.
- Junctions: asphalt pads with dashed green bike conflict markings, continental crosswalks on every approach, and stop bars on the approach half. Mid-block crossings at z 17, -93 and -177 keep their signals and stop lines.
- Shaders: `road_surface.gdshader` adds wheel-track polish, oil drip lines, a sealed crown joint, sealed cracks, utility-cut patches and grime near the gutter. `road_paint.gdshader` adds paint wear.
- Traffic now drives on lane centres: ±1.95 m on Cedar Lane and 1.64 m off the centreline on the other streets. Cyclists ride in the bike lane at ±4.7 m. Downtown's old connector asphalt and sidewalks were removed (their collision slab remains).
- `tests/street_grid_test.gd` (468 checks) is in `run_tests.ps1`. Captures come from `tests/capture_streets.gd` and are saved to `tmp/streets_*.png`.

Not changed: the 8 m curved estate roads and roundabouts, and downtown's own street grid. Curb corners are square, not radiused. There is still a small height step where the connectors meet downtown's raised streets at x = 120.

## Latest update — 3 October 2026

Sixty ordinary neighborhood houses now use Higgsfield-authored modular exteriors: twelve combinations across four architectural families, six color palettes, revised construction details and portable PBR textures. Door locations, deliveries and the playable Cedar home are preserved. Downtown's 435 source/asset files are unchanged. See [HIGGSFIELD_HOUSING_REPORT.md](HIGGSFIELD_HOUSING_REPORT.md) for sources, validation and limits. The bicycle also uses the Higgsfield asset described in `world/higgsfield/PROVENANCE.md`.

## Current build — 18 September 2026

The neighborhood now connects to nine dense downtown blocks and a civic district with hospital, fire station and school. There are 41 delivery destinations and eight pickup locations. The living-city pass supplies six skinned character variants with eight animations, ten vehicle types, purposeful sidewalk routing, police/service/taxi/school-bus routes, a separated cycleway and landscape planting. Thirty new Blender sources have three GLB detail levels each; the downtown modular kit adds 82 sources.

See [LIVING_CITY_REPORT.md](LIVING_CITY_REPORT.md) for implementation, model sources, current tests, optimization and limitations, and [DOWNTOWN_REPORT.md](DOWNTOWN_REPORT.md) for the dense district. The 16 September overview below is historical; controls, phone, needs, calendar and shop gameplay still apply. This remains procedural game art with stylized details, not photorealistic production art.

## Earlier build — 16 September 2026

This section supersedes the historical notes below. Godot 4.7.2 / Forward+, start `app/app_root.tscn`.

The city is 240 × 780 m with 36 delivery addresses, 24 additional houses, a furnished starter home, three furnished restaurants, four connected apartment blocks, eight parks, four shops, an equipment kiosk and public WC/water. Curved access roads and two roundabouts share their geometry with grass exclusion and local navigation. Blender meadow hills replace the visible boundary walls; collision still bounds the playable area.

Tab opens/closes the phone-shaped CourierNow app at the lower right. M opens its local navigation screen. The circular minimap follows the player over a 75 m radius; phone navigation covers 120 m. Menus pause play. E interacts, mounts a nearby vehicle, or dismounts after stopping. WASD moves/steers, Shift sprints, Space brakes while riding. Cars use a chase camera and matching body collision. Parked vehicles also have collision.

The top bar shows weekday, day/month/year, time and food/water/WC needs. The calendar starts on 16 September 2026 and advances ten game minutes per real minute. Sun, cloud sky, ambient light, street lamps and headlights change with day/night. Food and bottled water can be bought at restaurants; drinking water and WC use are free at the public washroom. Equipment and seven vehicle upgrades are bought with delivery earnings and persist in the save ledger.

Traffic includes 16 vehicles across five body types/eight paint colors, 24 pedestrians, six cyclists, restaurant workers/diners and shop staff. Two cars use the roundabouts. Assets include 34 new Blender-authored city GLBs, plus three residential variants and the furnished starter home. See [ASSET_UPGRADE.md](ASSET_UPGRADE.md) for sources, prices, workflow and optimization.

Verified: economy and dispatch suites, 25 regression checks, 165 city checks, 71 lifestyle/vehicle checks, 11 starter-home checks and the scene delivery smoke test. Native render scripts and a warm world-only benchmark are in `tests/`; outputs are in `tmp/`.

Limits: this is an authored procedural game-art pass, not photorealistic production art. Driving is arcade-style, NPC routes are local scripts, apartments are exterior assets, and the city is deterministic and bounded. There is no injury/helmet-protection simulation, full first-person body, audio pass, dynamic weather or infinite streaming.

**Save incident:** the initial lifestyle test accidentally wrote a fresh shift to `user://delivery_save.json` and its backup. No earlier recoverable copy was found in the project. Tests now disable saving before scene startup or use a memory-only save service. Subsequent tests/captures are isolated.

## Historical notes (superseded)

Updated: 2026-09-11

## Crossing and material correction

Removed the centre-straddling stop bars: each crossing now has two thin lane-specific stop markings, with centre dashes suppressed nearby. Regression tests require four markings outside the centre gap and no thick paint geometry. A reusable procedural shader library distinguishes asphalt, concrete, painted lap siding, timber grain, brick courses, roof shingles, tinted glass, metal and vegetation. Car roofs/pillars, bumpers, grilles and rear plates improve readable construction. These are original procedural look-development materials, not scanned PBR assets or final production meshes.

## City expansion / current state

Playable footprint expanded from 130 x 180 m to 150 x 330 m, with 12 delivery addresses, three functional pickups (Cedar Kitchen, Market Noodles, Harbor Pizza), four background apartment blocks, benches, bins, planters, shutters, mullions and closed roof gables. House paths now end at the sidewalk edge instead of meeting over the road. Reduced the strong noise contrast on shared materials.

Six local AI cars follow a closed two-lane circuit with braking, obstacle probes, swept collision, and red/green pedestrian-crossing phases. Signals pause with menus. This is an initial local traffic model: sharp end turns, no multi-junction reservations, pedestrians or city-wide lane graph yet. No claim of final realistic asset quality or whole-city simulation.

Restaurant IDs are stored in new orders. Legacy orders without the field retain Cedar Kitchen. Every UI pickup label and interaction uses the selected restaurant. New quoted distances and HUD distances derive from the same authored sidewalk route used by the map. Existing accepted quotes remain untouched. Save coordinate validation accommodates the expanded block. Restaurants share the current 08:00–22:00 schedule.

Tests: city_test.gd covers all 12 doors, three physical pickup counters, restaurant selection/ownership/save validation, path exclusion from asphalt, six cars, red stopping, green resumption and player obstacle stopping. Existing economy, dispatch and regression suites remain in the runner. Long city soak tests and real player experience testing remain open.

## Latest fixes and continued transport work

Mounting now aligns the player to the parked bike only across an unobstructed sweep; mouse look while mounted no longer steers the bike. Dismount restores forward camera alignment. Parked yaw is saved. Low energy reduces acceleration, while resting on the bike recovers energy. Bicycle frame tubes, spokes and distance-driven wheel rotation improve the transport prototype.

Kitchen navigation exits the open frontage rather than crossing its side wall. Minimap covers the full block boundary. Going offline with a pending offer schedules the standard cooldown. Save validation checks purchase ownership, delivery counts and whole-cent quotes. Corruption handling uses a quiet JSON parse and retains the damaged primary for recovery. Regression runner is in tests/run_tests.ps1.

## 0.3 repair and look-development pass

Corrected idle dispatch messaging and physical-key display names; moved the street sign out of the carriageway and reduced world text scale. Added procedural surface variation, SSAO, MSAA, clustered tree crowns, sidewalk joints, house foundations, chimneys, sills, door handles and planters. All assets are original code-generated prototypes; this does not meet the document's final realistic-asset target yet.

Added a first bicycle controller: B mounts nearby; W/S pedal; A/D steer; Space brakes; B dismounts after stopping with side collision checks. Pickup/handoff require dismounting. Parking and mounted state persist alongside cargo/session data. Existing saves default to a parked starter bicycle. Basic controller still needs slope tuning, wheel animation, independent riding look, detailed frame art and extended playtesting before the transport milestone is complete.

## Working build

Godot 4.7.2 stable, Forward+, Windows prototype. The project starts at `res://app/app_root.tscn`.

The current slice includes a graybox Cedar Lane neighborhood, first-person walking, a Cedar Kitchen pickup counter, six numbered house destinations, phone offer flow, accept/reject, physical pickup and handoff, wallet and tip calculation, insulated bag purchase, energy, home rest, map panel, pause flow, and versioned save/load with backup recovery.

## Verification

`Godot_v4.7.2-stable_win64_console.exe --headless --path . --quit-after 120 -- --smoke-test`

Result: `SCENE SMOKE PASS: real raycast pickup, correct door, receipt, autosave`.

## Known limits

This is the first graybox milestone. There is no bicycle controller, traffic, pedestrians, weather, authored interiors, route graph, audio, localization, or final art yet. The car decision remains open. The design document's proposed features are treated as proposals until owner-confirmed.

## UI, clock and dispatch update

Version 0.2 adds a north-up minimap with rotating player heading, street/front-path guidance, a larger phone map, cinematic title camera, scrollable phone screens, and a consistent 1280x720 UI canvas across fullscreen aspect ratios. Time advances ten game minutes per real minute of active play; menus pause it. Sunrise/sunset changes sun, sky and ambient light; street and porch lamps illuminate at night. Sleeping at home advances to next-day 08:00 and is blocked during an active job.

CourierNow requests arrive automatically while online. Initial onboarding delay is eight active seconds. Subsequent waits are seeded: 15–45 seconds during 11:00–14:00 and 17:00–20:00, 55–120 seconds otherwise. Cedar Kitchen creates new offers only 08:00–22:00; accepted jobs are honored after closure. Offers expire after 30 active seconds. Rejection has no monetary penalty. Availability, pending wait, calendar, and seed persist in saves; older saves load with defaults. These timing bands are provisional gameplay tuning, not measurements of real delivery platforms.

Navigation is authored for this small block, not a general obstacle-aware city route graph. Final environment art, full settings/remapping, traffic, weather and bicycle transport remain future work. The existing smoke test now avoids overwriting the player's save.

## Next concrete task

Implement the bicycle as a reversible arcade controller with mount, brake, park, safe dismount, and preserved cargo state. Then add a small authored route validator before expanding the city.

## Cedar House integration — 2026-09-13

Replaced the starter YOUR ROOM solid block with the furnished Cedar House asset at (17.9, 0.015, 29.6), scale 1.0. The visual GLB and local collision/door definitions live in world/cedar_house/. The twelve delivery houses and all restaurant interactions are unchanged. Added a walkway from the sidewalk to the front garden, five doors using the existing E interaction and layer 1 collision, indoor lighting, and a separate REST / SAVE plaque on the left side of the entrance. Existing home rest restrictions and session persistence remain in app_root.gd. Door positions reset closed on scene reload. The title camera now looks at the new home.

Verified with Godot 4.7.2 / Jolt: 11 new integration checks passed, existing scene delivery/bicycle smoke test passed, and city_test.gd passed 54 checks. Native Forward+ exterior and interior captures confirmed the model in the existing game HUD and neighborhood. Test saves used a memory-only save service; the player's save was not overwritten. The asset is approximately 74k triangles; five interior shadow lights are active. Full game performance profiling remains project-specific.

## City soul pass (2026-10-13)

- **Bicycle**: real steering (A/D or mouse), kinematic yaw from wheelbase, lean, animated fork/handlebar; `tests/bicycle_steering_test.gd`. The player bike, NPC cyclists and Cedar Cycles displays use the gray city bike `assets/bicycles/gray_bicycle.glb` (rider removed from the supplied `woman_riding_a_gray_bicycle.glb` by `tools/build_gray_bicycle.py`; SteeringPivot/WheelFront/WheelRear rig, ~24.8k tris, QA in `world/vehicles/production/renders/gray_bicycle/`). Even-numbered NPC cyclists carry the supplied model's own rider (`gray_bicycle_rider.glb`). The old Higgsfield bike in `world/higgsfield/` is kept but unused.
- **Housing**: 187 dense Vancouver/Burnaby lots from 7 reference house types (`build_houses.py`, `ResidentialLayout`, `HouseInstancer`), rear lanes with poles and wires, edge forest.
- **Street names** (`StreetNames`): Turkish War of Independence figures on streets/parks, Turkish scientists downtown; junction sign posts, park signs with bronze busts, Atatürk Square monument downtown, 12 street-art murals (`build_murals.py`) on terrace end walls facing parks; live street name in the HUD.
- **Restaurants**: 16 Turkish restaurants (`RestaurantCatalog`). 3 on Atatürk Avenue + 13 fitted into corridor storefronts (`RestaurantInteriors`, Blender kit `build_restaurants.py`): çini/terrazzo/oak interiors, counter + register + courier pickup shelf, menu boards with prices, kitchens, signature equipment (spinning döner, kokoreç, pide oven, fish counter, baklava vitrine, soup cauldrons, kumpir bar…), staff and diners, sidewalk seating. Pickups 8–20; offers rotate through all 16.
- **Buses** (`BusSystem`, `build_transit.py`): 3 ring lines, 5 buses, 16 stops with shelters/flags; buses brake for traffic/courier, kneel, open plug doors, alight/board passengers, chime; engine/door/brake sounds.
- **Animals** (`AnimalLife`, `build_animals.py`): dog walkers on leads, lawn cats that bolt, pigeon/crow flocks that take off when approached, circling gulls; barks/coos/caws/calls.
- **Faces**: sculpted citizen heads (eye sockets, brow, nose, cheekbones, lips, chin, per-person variation) in `build_people.py`.
- **Weather** (`WeatherSystem`): forecast-driven drizzle/rain, GPU rain with roof collision and splashes, global `wetness`/`rain_intensity` (glossy roads, rippling puddles), overcast sky, fog, rain audio, HUD weather.
- **Street furniture** (`StreetFurniture`): hydrants, drains, manholes, bins, bike racks, newspaper boxes, cabinets, Kara Fatma Street road works.
- **Sound**: `tools/sfx_forge` (free, offline procedural SFX + MCP server), `CityAudio`.
- Tests: `tests/run_tests.ps1` (12 suites, all passing). Captures: `tests/capture_*.gd`. Perf: 7.7–10 ms median in residential views (RTX 3070 laptop).

## Courier backpack and main menu (2026-10-20)

- **Delivery bag as a backpack** (`ui/bag_rig.gd`, `BagRig` on the player camera): F swings the open insulated bag (`assets/delivery/delivery_bag_open.glb`) off your back into view. Packing drops the held package into its compartment (`compartments` extra). Closing swings the bag back onto your shoulders. A delivery from the bag brings it round and lifts the package out to the customer. The HUD line reads `BACKPACK · …` / `HOLDING …`. Only the plain courier backpack still rides on the vehicle rack.
- **Main menu** (`ui/main_menu.gd`, `MainMenu`, CanvasLayer 10):
  - Layout: transparent text buttons on the left over a big living city picture.
  - Animation: a slow Ken Burns drift, procedurally drawn bird flocks (V formations and singles, flapping and gliding), and a photo collage of one delivery (pickup shelf → ride → doorstep handover). The collage carries a live order tracker whose dot runs the route, lifts each print in turn and stamps DELIVERED.
  - Buttons on the title: Continue (with a save summary), New Game (confirms over an existing save), Save Game and Exit to Menu (both disabled), Settings, Exit to Desktop.
  - Buttons on the Esc menu, shown over the paused street: Continue, Save Game, New Game, Settings, Exit to Menu (saves), Exit to Desktop (saves).
  - Esc backs out of sub-pages.
  - Stills come from the game world via `tools/render_menu_collage.gd` → `ui/menu/*.jpg`.
- **Settings** (`systems/game_settings.gd`, `user://settings.cfg`): master/ambience/effects volume (audio buses), mouse sensitivity, field of view, fullscreen and vsync. Changes apply live.
- **Tests**: `tests/main_menu_test.gd` has 19 checks and is in `run_tests.ps1`. The scene smoke test (`--smoke-test`) now takes the named package from the shelf. Captures are in `tests/capture_main_menu.gd`.

## Civil service fleet and Ace 11 (2026-10-21)

- **Assets** (`tools/prepare_civil_vehicles.py`, headless Blender): the civil service pack and the Ace 11 hatchback (source GLBs at the project root, set to `importer="skip"` so Godot does not import them) are split into `assets/vehicles/civil/<name>.glb` (ambulance, citybus, fire_truck, garbage_truck, police_sedan, postvan, rdservtruck, school_bus, taxi, towtruck) and `assets/vehicles/ace11/ace11.glb`. Each one is centred and sits on the ground. It faces Blender +Y (Godot -Z) at real scale, with `Wheel*` / `SteerFront*` empties and root extras. Textures are 1024 (512 for small maps). The Ace 11 has a `VehiclePaint` body and a `SteeringWheel` pivot. QA renders are in `world/vehicles/production/renders/civil/`, and metrics are in `world/vehicles/production/reports/civil_vehicles.json`. `VehicleCatalog.path_of` serves `civil_*` ids from the new folder; the older `assets/sketchup/vehicles/civil_*` copies are no longer loaded.
- **Traffic**: of the 16 city cars, slots 1, 3, 7, 11 and 14 are service vehicles. Slot 1 is always a taxi; the others are a weighted draw from `VehicleCatalog.SERVICE` (taxi, police, post van and ambulance are common, tow and road-service trucks less so; garbage truck, school bus, city bus and fire truck are rare). Each loop gets at most one vehicle longer than 7 m. The Ace 11 is part of the everyday mix. Vehicles over 6 m drive copies of the loops with 6 m corner arcs, so they stay off the kerb corners. The street light at (6.5, 45) is gone: it stood inside the 11 m turn into Cedar Lane. The downtown school bus turns 6 m into its pull-in, clear of the square's bollards. `tests/traffic_long_vehicle_test.gd` sweeps every model along every route against static colliders and kerb corners.
- **Shop**: the Ace 11 sells for $1,450 at Northside Motors and is shown between the Jetta and the compact hatchback. Player and showroom cars use the model's factory finish, so the showroom car matches the car you buy. `tests/ace11_drive_test.gd` covers the drive contract.
- The kit city bus (`BusSystem`) is unchanged because its doors and kneeling are tied to that model. The pack's city bus only appears in traffic.

## Procedural prop placement (2026-10-21)

- **Bug**: a Cedar Lane street light was placed at (6.5, 45) by a fixed `z + 5` offset loop that ran past the avenue's end (z 44), so its pole stood on the Nezahat Onbaşı Street carriageway (z 44-52), inside the cars' turn into Cedar Lane; the east traffic loop queued behind it.
- **`PropPlacer`** (`world/props/prop_placer.gd`, `CedarNeighborhood.placer`): one road model for the whole city (street grid with bike lanes and junction boxes, curved estate roads, roundabout rings, frontage driveways, downtown streets; alleys and rear lanes as soft surfaces) and a spatial registry of placed props. `place()` / `street_light()` keep a requested spot if it is valid (off every carriageway plus a 0.25 m kerb margin, clear of junction boxes for lights, mid-block crossing landings, front walks, forecourts and other props, same-kind spacing) and otherwise slide it along the street to the nearest valid spot (or drop it). `kerb_clear()` pulls tight frontage props back from the kerb. Deterministic.
- Routed through it: avenue and side-road street lights and avenue trees (`CedarNeighborhood`), curved-road lights (`CurvedRoads`), all street furniture (`StreetFurniture.put`), bus stop flags and shelters (`BusSystem`), junction/park signs (`StreetSignage`, recorded), downtown frontage props and loading-bay signs (`DowntownDistrict.kerbside`). Fixed on the way: the park-roundabout sign in a frontage road mouth (z -176), downtown lamps/trees/benches on the 3 m Aziz Sancar Avenue sidewalks, loading signs 0.7 m out in the kerb lane, a campus bollard in the school bus's turning arc.
- **`tests/prop_placement_test.gd`** (in `run_tests.ps1`): every small static collider and ground-standing prop mesh against the road model, every placer record, every collider vs the AI routes (city, downtown, civic fleet, buses), and a 60 s traffic run with no car stopped by a static body. Headless skips MultiMesh visuals (the dummy renderer keeps no instance data); run it without `--headless` for all 9,000 instances. Captures: `tests/capture_prop_placement.gd`.

## Paper food bags and black courier backpack (2026-10-21)

- **Food bags** (`tools/build_delivery_assets.py`) are kraft SOS bags: flat bottom, gusset creases, top folded once over the front with a pinked edge, no handles.
  - Three sizes: `food_bag_s/m/l.glb` are 16×10×26, 19×12×32 and 23×14×38 cm. `food_bag.glb` is the medium one.
  - `OrderDetails.bag_size(items)` picks the size from the portion count: 1 → s, 2–3 → m, 4+ → l.
  - `PickupShelves` loads the matching model and shrinks the restaurant-name label to fit its sticker.
- **Courier backpack** (`delivery_bag.glb`, `delivery_bag_open.glb`) is black 600D with a reflective band, side pockets, a clear front pocket, a top handle and shoulder straps.
  - The front flap is hinged at the bottom and drops open (100°) on two straps.
  - The interior is lined with matte crinkled foil. Shelves: pizza drawer, two middle bays, top bay. Compartments are in root extras as before.
  - `BagRig` frames the open front. A package that fits better lying down is laid on its back.
  - The rig ray-tests the space ahead and pulls the bag closer and smaller near walls and shelves, so it never clips into the world.
  - The previous orange top-lid bag and the handled food bag are in `assets/delivery/archive/v1/` (`.gdignore`).

## Hold / put down / drag-and-drop packing, and the training shift (2026-10-21)

- **Holding a package:** picking an order up (from the shelf or the ground) flies it into your hands (`HOLD_POSE`, camera child).
  - **G** (`drop`) sets it down on the flat surface in front of you, and **E** on it picks it up again.
  - The order state is `DROPPED` with `order.dropped_at` = [x, y, z, yaw]. It is in `DeliverySession.ACTIVE`, validated, and saved and restored; `sync_dropped()` re-spawns the model.
  - While it is down, the minimap routes you back to it, deliveries are refused and the clock keeps running.
- **Drag and drop into the backpack:** with the bag open (F), the held package follows the mouse.
  - `BagRig.pick()` ray-tests the compartment boxes (root extras, now read from the `DeliveryBag` child where glTF puts them). `highlight()` shows green when the order fits that compartment and red when it doesn't.
  - Click drops the package in (`bag_click`). Clicking a packed compartment lifts the order back into your hands (`take_out`). E still quick-packs, and the UI slot buttons still work.
- **Training shift** (`systems/tutorial.gd` `TutorialDirector`, `ui/mission_card.gd` `MissionCard`, HUD left column). New Game starts 12 mandatory tasks in order:
  1. look around
  2. walk
  3. open and close the phone
  4. open and close the map
  5. buy the delivery bag (minimap guides you to Trail & Tool)
  6. get on the bike (guided)
  7. accept the scripted first order (Kebab House → 105 Atatürk Ave; it never expires and can't be rejected)
  8. ride to the restaurant
  9. take the right package by its receipt
  10. put it down and pick it up
  11. drag it into the backpack
  12. deliver at the door
- **Rules while training:** `gate()` blocks normal dispatch, rejecting, going offline, packing before task 10 and delivering before task 11, each with a hint.
- **Saving:** progress is in `DeliverySession.tutorial` and saved. Old saves and fresh sessions count as trained.
- **Finishing** pays a one-time $15 bonus (ledger `bonus_tutorial`, validated) and turns dispatch on.
- **Tests:** `tests/tutorial_test.gd` (39 checks) plays the whole training through the real input paths and is part of `run_tests.ps1`.

## Townspeople behaviour pass (2026-10-21)

- **Clips** (`tools/build_npc_clips.py`, headless Blender → `assets/animations/ual/ual_npc.glb`, retargeted like the library via `tools/setup_npc_clips.gd`): `Idle_Carry` / `Walk_Carry` (tray on both palms), `Idle_Phone`, `Sitting_Phone`, `Sitting_Eat` (plate → mouth → chew), `Idle_Look` (window shopping). Each starts from a library clip and re-poses arms/head per frame with two-bone IK on the library rig. `LivingAssets.CLIPS` adds `Carry, WalkCarry, Phone, SitPhone, SitEat, Look, SitDown, StandUp, WalkFormal`.
- **Props** (`tools/build_npc_props.py` → `assets/props/npc/`): tray, plate of food, tea glass, phone.
- **Outfits** (`tools/build_outfit_masks.py` → `assets/sketchup/people/<id>_outfit_mask.png`, `world/living_city/outfit.gdshader`): top/bottom clothing masks (rest-pose regions, minus the character's own skin tone and hair); one shared material per character surface, per-person hue/saturation/value through instance uniforms (`LivingAssets.outfit_colours`). Natural height variation 0.93–1.07.
- **Walking** (`LivingCitizen`, `CitizenBrain`): playback scaled by ground speed / measured stride (`LivingAssets.STRIDE`, planted-foot speed of each retargeted body), smoothed velocity and turn rate, rounded corners, personal speeds 0.85–1.55 m/s, keep-right avoidance of people and the player, waits at signals and for gaps at junction zebras, phone / window / bench pauses, buildings entered at destinations. Heights follow the rendered walking surfaces (`CitizenRoutes.ground_y`; the ground collider is flat). The sidewalk graph now covers the cross streets and side roads. Animation runs only on screen (VisibleOnScreenEnabler3D) and at 30/15/8 Hz with distance; shadows within 38 m.
- **Sitting** (`CitySeating`): seat slots measured from the meshes (bench_wood top 0.44, downtown bench 0.52, restaurant chair 0.49 on 0.06 floor, booth 0.56, avenue restaurant chair 0.50); the seated pose (Sitting_Idle buttock contact, back, soles per body) puts hips on the seat and feet on the floor (body/scale chosen per seat). Walkers sit on free benches with Sitting_Enter / Sitting_Exit.
- **Restaurants** (`TableService`): diners on the real chairs/booths, a waiter takes a plate from the counter, carries it on a tray, sets plates down at the table (diners switch to eating), returns; sidewalk-table customers outside. Avenue restaurants get the same.
- **Shops** (`ShopLife`): one browsing customer per shop (clear of the counter kiosk and the back-right pickup shelf); clerks cycle idle / talk / interact / phone (`LivingCitizen.routine`).
- Counts: neighbourhood walkers 24 → 162 (96 avenue, 48 residential, 16 park strollers, 2 crossers), downtown 47 → 83. Captures: `tests/capture_npc_life.gd`.

## Street life: busier traffic, signals, LED boards, street VFX (2026-10-21)

- **Traffic** (`world/traffic.gd`, `world/living_city/service_traffic.gd`, `world/vehicles/traffic_driver.gd`):
  - City cars: 16 → 70 on seven right-turn-only loops. The two Cedar loops and the south grid stay. New loops: the avenue south of Refet Bele St (SE southbound, SW northbound) and two cross-street loops (-398 eastbound, -538 westbound).
  - Every merge happens at a signalised junction, so the phases keep merging cars apart.
  - Downtown: 18 → 42 cars. `CivicFleet` takes over the population's loop cars (`CivicFleet.drivers`; `population.vehicles` is left empty) and adds east-west loops on -398 / -538. The civic fleet's east-west legs now use the loops' lanes (3 m off the centreline).
  - Drivers (`TrafficDriver.think`) follow the car ahead smoothly: a 1.7–2.8 m standstill gap, about 1 s headway and a 0.35–1.1 s reaction time when pulling away. Route-following rays see the player, people, buses and other loops' cars.
  - Distant cars (> 120 m) update at 1/3 rate without swept moves, and only cars within 60 m cast shadows.
  - A car stranded against a pedestrian for more than 6 s edges past. The player is never driven through.
- **Signals** (`world/streets/signal_plan.gd` `SignalPlan`, `traffic_signals.gd` `TrafficSignals`, Blender kit `world/streets/build_street_tech.py`):
  - 24 junctions: 4 avenue × cross street, 2 side road × cross street, 2 mid-block crossings and the 16 downtown junctions. There are 82 galvanised mast-arm poles, each with an overhead 3-section head (yellow-bordered backplate) and a side-mounted head, plus 160 pedestrian heads (hand / walking figure) and push buttons.
  - Programs: green → amber 3 s → all-red 2 s, never two conflicting directions at once. Walk signals run with the parallel green; downtown has a scramble phase.
  - The mid-block crossings keep `CityTraffic.crossing_red()`. Downtown runs on `CivicFleet.signal_clock`, which follows the population's phase but keeps running if that phase is held.
  - Cars and buses (`BusSystem`) stop at the stop line on red, and on amber when they can. They queue, and only enter a junction when the exit has room.
  - Poles are placed through `PropPlacer` beyond the crosswalks, near the kerb and clear of every AI path. The old downtown kit signals and WAIT labels are removed.
  - Lamps and symbols are per-junction MultiMeshes with one shared shader (LED cluster, glow sprites). Instance data changes only when a junction's aspect changes. Walk sounds are registered with `CityAudio.attach_signal_loop`.
- **LED boards** (`world/streets/led_boards.gd` `LedBoards`, `led_board.gdshader`, 5×7 font `led_font.gd`):
  - 28 scrolling dot-matrix marquees: wall boards on the 4 shop headers, double-sided blade signs on the 3 avenue and 13 corridor restaurants, and long boards on downtown storefront fascias.
  - Messages carry the name, offers and prices (₺ for restaurants) and OPEN / PAKET SERVİS.
  - One shared material and one CPU-built atlas texture (one texel per LED). The text steps one LED at a time.
- **VFX** (`world/streets/street_vfx.gd` `StreetVFX`):
  - exhaust puffs when cars pull away (16 pooled one-shot emitters),
  - brake and tail-light glow (one MultiMesh),
  - charcoal grill smoke from the rooftops of 5 corridor grill restaurants,
  - tyre spray on wet roads (8 pooled emitters).
  - These particles disable heightfield collision so the rain's roof collider cannot catch them.
- `world/streets/street_life.gd` hooks the pass into `CedarNeighborhood`. `StreetLife.enabled` and `VehicleCatalog.legacy_traffic` give the "before" city for benchmarks (`tests/profile_streets.gd -- out.json before|after`).
- **Tests:** `tests/traffic_signal_test.gd` is in `run_tests.ps1`. It covers phase safety for every junction, stop lines per loop, a red-light stop, a queue and green discharge, and a 300 s whole-city soak (no vehicle held, no overlaps).
  - `city_test`, `street_grid_test`, `traffic_long_vehicle_test` and `prop_placement_test` were updated for the new loop set and the downtown takeover.
  - Captures: `tests/capture_streets.gd -- <dir> [kit|life]`.

## Courier career v2: phone, store computers, delivery zones (2026-10-21)

- **New Game career** (`DeliverySession.start_career`, `economy = 2`): you start on foot with $100, offline, with no phone, no bag and no vehicle.
  - The phone ($25), the bag ($35) and every vehicle are bought. The basic gray city bicycle is $120 at Cedar Cycles.
  - The Jetta is no longer free ($2,600).
  - Old saves (`economy` 1) keep their bicycle and phone.
  - The player's vehicle node stays but is hidden, with no collision, until a vehicle is bought (`CourierPlayer.has_vehicle`).
- **Store computers** (`world/delivery/store_terminals.gd`, `ui/store_terminal.gd`, `ui/icon_studio.gd`): a kiosk computer on each shop counter (`assets/gadgets/store_kiosk.glb`) opens a monitor-framed online shop.
  - Product cards show a rendered thumbnail, price and features, with − / + quantity. The cart has per-line − / + / remove, total, wallet-after and Purchase.
  - `DeliverySession.checkout()` charges the cart. Equipment is sold once; supplies (water bottle, energy bar) go by quantity, with ledger `store_order_N`.
  - Paid items wait on the ONLINE ORDER PICKUP shelf (`pickup_locker.glb`) as real models with tags; E collects them (`collect`).
  - Vehicles roll out in front of the store.
  - Supplies are used with keys 1 (water) and 2 (energy bar).
- **The phone** (`ui/phone/phone_device.gd`, `ui/phone/phone_os.gd`, `assets/gadgets/budget_phone.glb`): a 3D phone in first person. Tab raises it and the camera narrows its field of view; PhoneOS renders in a SubViewport on the "Screen" mesh, and mouse events are ray-cast onto the glass and pushed into the viewport.
  - Status bar: time, network, battery.
  - Home screen: a clock / date / weather widget, a day bar with the lunch and dinner rushes, and an app grid.
  - Apps: CourierNow (shift on/off, offers with delivery method, active order and steps, earnings), Maps (city map), Wallet (balance, history, bicycle savings goal), Weather (now plus 6 hours of rain chance).
  - Locked "coming soon" apps: Messages, Music, Camera, Bank, Chirp, Rides, Games, Settings.
- **Delivery methods** (`order.method`: `door` / `meet`), with a `DropZone` (`world/delivery/drop_zone.gd`) at the customer's door once you have the package. The zone is a glowing lined rectangle with corner brackets, a pulsing fill, sparkles, a bobbing `drop_arrow.glb` and a method label.
  - **Leave at door:** E at the area (the bag swings round and the order is set down) or G inside it. This takes a proof photo (flash + shutter) and calls `leave_at_door`.
  - **Meet at door:** E on the door knocks; the customer (a citizen) comes out to the doorstep. E hands the order over (from the bag or your hands); they thank you and go back in.
  - E works by proximity at the door, and the prompt says so.
- **Training v2** (`TutorialDirector`), 15 tasks:
  1. look
  2. walk
  3. walk to Trail & Tool
  4. order the phone and bag on the computer
  5. collect them
  6. open the phone and CourierNow
  7. start the shift
  8. accept the first order (leave at door)
  9. walk to Kebab House
  10. take the right package
  11. put it down / pick it up
  12. pack it
  13. leave it in the marked area
  14. accept the second order (meet at door)
  15. collect and hand it to the customer
  - The director runs while the phone is open.
  - Afterwards a goal card tracks saving for the bicycle.
- **Gameplay sounds** come from the new CityAudio presets (phone raise / lower / taps, kiosk, cart, purchase, item pickup, package drop / place, bag zip, knock, door, shutter, delivery success, customer thanks, coins, step / mission complete). `auto_order_cues` is off; app_root plays order cues itself.
- **Tests:** `tests/tutorial_test.gd` (55 checks) plays the whole career start through real input paths. The smoke test uses knock + customer handover.
- **Frame time:** with more people and traffic, the busiest spot (avenue near the start) is about 20–25% heavier than before. Levers:
  - `CityLife.AVENUE_WALKERS` / `RESIDENTIAL_WALKERS` (now 56 / 32)
  - `CityTraffic.COUNTS` (now 50 cars)
  - LivingCitizen animation rate tiers (full < 10 m, 20 Hz < 24 m, 10 Hz < 45 m, 5 Hz beyond)

## Parks, monuments and sports (2026-10-21)

- **Assets** (`tools/prepare_monuments.py`, headless Blender, sources in `source_assets/incoming_2026_10_21/`) → `assets/monuments/*.glb`, metrics and collision primitives in `assets/monuments/monuments.json`, 7-view QA sheets in `assets/monuments/qa/`. Origin at the footprint centre on the ground, front Godot +Z, Godot auto-LODs.
  - `ataturk_monument` — standing bronze Atatürk (4.8 m figure, scan atlas re-graded to warm bronze, the white back-seam fills mapped to a plain bronze patch) on a new stepped granite plinth; 9.15 m, 13.7k tris, 2048×1024 + 512 granite.
  - `ataturk_equestrian` — the untextured horse statue at 4.5× (8.5 m: 4.3 m pedestal, rider and horse above); bronze/granite split by height, Cycles AO baked into vertex colours (patina in hollows), box-mapped granite; 14.5k tris.
  - `ataturk_bust` — the memorial wall with the bust ("Hayatta en hakiki mürşit ilimdir"), cut from the scanned pavement and pole, on a clean travertine platform; 3.74 × 1.73 m, 9.2k tris (109k), 2048 (8192).
  - `sculpture_open_arms` / `sculpture_stretch` — the two figure scans recast as polished bronze / brushed steel sculptures on granite plinths; 2.55 m, 11.7k tris each (235k / 250k), 1024.
  - `statue_jenner` — the Hyde Park Edward Jenner statue on a granite slab; 5.76 m, 14.6k tris (447k), 2048 (8192).
  - `fountain_putti` — the Lužánky fountain with three putti; 3.24 m, 17.5k tris (89k), 2048 base/normal + 1024 ORM (metallic baked to 0).
  - `basketball_court` — fenced 13.5 × 27.4 m street court; 16.8k tris (138k), chain-link and markings as alpha scissor, textures ≤ 2048.
- **Placement** (`world/monuments/city_monuments.gd` `CityMonuments`, `CedarNeighborhood.monuments`, from `build_park` and `StreetSignage.monument`):
  - Atatürk Square plaza: the monument (inscription labels on its bronze panel) with the putti fountain behind it (replaces the old procedural plinth/figure and `reuse_fountain`).
  - Halime Çavuş Park (east roundabout island, 64, −145): the equestrian monument at the path crossing on a 4.5 m granite plaza, rider facing down the side road toward the home side; no fountain there, its strollers circle the plaza (`CityMonuments.stroll_loop`).
  - The other seven parks: putti fountain at +4,−5 (animated `fountain_water.gdshader` film, CityVFX jet now from the 2.95 m column top, CityAudio water loop — all from `CityMonuments.fountain_spots()`), and the bust memorial in the NW lawn (−4.8, −3.6) facing the east-west path (replaces the procedural busts; `StreetSignage.busts` lists each park's memorial).
  - Sculptures: Open Arms in Gördesli Makbule (west ring, west path end) and Şahin Bey; Stretch in Yörük Ali Efe and Bombacı Ahmet (square parks: NW lawn pocket −2.9, −7 facing the north-south path).
  - Jenner statue on the Meridian General Hospital forecourt (545, −342), facing the civic road, south of the entrance walk.
  - Two courts in the north half of the school yard (597.5 / 614.5, −614.5), gates facing the school; the barrier/birch pair at z −623 (`campus.gd`) moved out.
  - Every asset: JSON collision boxes/cylinders on layer 1, visibility ranges (nets 70 m), shadows only within 55–140 m of the camera (twice-a-second toggle), `PropPlacer.record` + a reserved keep-clear rect, so trees and furniture avoid them.
- **Tests:** `tests/monuments_test.gd` (asset budgets/materials, counts, collision, off carriageways and park paths, placer records). Captures: `tests/capture_monuments.gd -- <dir> [survey|final]`. Benchmark switch: `DS_NO_MONUMENTS=1`.

## Cedar House interior and restaurant dressing (2026-10-21)

- **Props** (`tools/prepare_interiors.py`, headless Blender, sources in `source_assets/incoming_2026_10_21/`) → `assets/interiors/<category>/<id>.glb`, metadata in `assets/interiors/catalog.json`, QA renders in `assets/interiors/qa/` (`.gdignore`). 119 props: one mesh per prop, materials merged, real scale, origin on the floor (wall props: back face), front +Z, textures ≤ 1024 (small props ≤ 512).
  - kitchen_decor_pack (284k tris) → 30 props: fridge, range (oven + cooktop), dishwasher, built-in coffee machine, airfryer, blender, toaster, spices, bottles, utensils, board and knife, plates, bowls, fruit bowl, wine crate, cookbooks, succulent, hanging plant (macramé hanger added).
  - sofa_set (inches) → sofa, two armchairs, coffee table, side table with lamp. tv_unit (255k tris, polygon soup, welded and split) → TV console with decor, TV with an added stand, floating wall shelf, hall mirror + drawer console, pouf. decor_shelf → cube shelf, staggered bookcase, sideboard, étagère.
  - stylized plant pots (915k) → 3 planter boxes + 3 troughs, ≤ 5k tris each (leaves thinned and enlarged, pots kept).
  - trailer_park_props → beds, armchair, chair, side table, lamps, clocks, radio, frames, vases, flowers, plants, cookware, bathroom items, bin, AC unit, fuse box, garbage bags, watering can.
  - baked_goods (459 MB, 4K maps) → 12 breads/rolls/pastries (0.0012 scale, 512 maps) + bread basket and four bakery trays. food_bar (Katydid café, 0.29 scale) → the 5 m service counter with vitrine, register, grinder and food.
  - Decimation keeps carcass boards/boxes untouched and collapses only dense decor; budgets 300–2,000 tris for small props, ≤ 5k for appliances and plants, 9.9k for the TV console.
- **Cedar House**: the original box furniture the props replace (sofa, coffee table, bookcase, range, fridge, one base cabinet, fruit bowl, both beds) is stripped from `cedar_house.glb` and `collisions.json` by the same tool (originals in `world/cedar_house/archive/`, `.gdignore`). `world/cedar_house/furnishing.json` lists 96 props in house coordinates; `house_asset.gd` `furnish()` places them through `InteriorProps` (`world/interiors/interior_props.gd`) and gives furniture box colliders. `tools/layout_furnishing.py` (headless Blender) drops snapped props onto counters/shelves/tables, checks walls, door swings and walkways, and renders room views.
  - Living room: TV console and TV under the west window, sofa facing it with its back to the hall, coffee table, two armchairs, side tables, pouf, plant, staggered bookcase and cube shelf with decor, wall clock. Kitchen: new fridge, range (pots on it), dishwasher in the cabinet run, counter appliances and spices, built-in coffee machine, sideboard with canisters under the window, étagère with dishes/cookbooks, hanging plant, fruit bowl and bread basket on the dining table, wine crate on the fridge. Bedrooms: blue and plaid beds, picture wall, reading armchair, desk with lamp and radio, alarm clocks. Bathroom: shampoo, soap, toothbrush cup, paper holder, bin. Hall: mirror console with lamp, wall shelf, plant. Outside: porch troughs and plant, watering can, garbage bags by the bins, AC unit and fuse box on the east wall. Doors, REST / SAVE and walking paths stay clear.
- **Restaurants** (`world/interiors/restaurant_dressing.gd`, hooked from `RestaurantInteriors`): bakery trays / bread baskets on the counters of the Pastry Shop, Dessert Shop, Dairy Dessert Parlor, Soup House and Local Diner and on the Rainline Café counter downtown; the Pancake House (breakfast café) uses the food bar as its counter (own collider, waiter pass spot kept); planter troughs under the dining-bay windows of every corridor restaurant. Pickup shelves, registers, menus and TableService routes are unchanged.
- **Performance**: small props draw to 12 m, medium to 22 m, furniture to 30 m; only props ≥ 1 m cast shadows; restaurant interior dressing casts none. Measured (`tests/capture_interiors.gd -- <dir> 13 perf`, other agents' processes running): living room 20.9 ms vs 21.5 ms with props hidden, kitchen 18.2 vs 16.7, Cedar Lane in front of the house 25.8 vs 24.9, avenue 22.6 vs 20.4 (same draw calls, noise).
- **Tests**: `tests/cedar_house_test.gd` 18 checks (furnishing count, rooms, collision, lot bounds, visibility ranges, hall and kitchen walkable). Captures: `tests/capture_interiors.gd`.

## Imported house types (2026-10-21)

- **Conversion** (`tools/prepare_new_houses.py`, headless Blender; sources in `source_assets/incoming_2026_10_21/`) → `assets/houses/<type>.glb` + `<type>_far.glb`, metadata in `assets/houses/houses.json` and as glTF extras on the root, QA renders in `assets/houses/qa/` (`.gdignore`). Same contract as `build_houses.py`: origin front-centre on the ground, street facade +Z, one mesh per `Kit*` material (shared CityKit materials, per-house body/trim/door/roof tint, no source textures), baked AO in vertex colour.
  - `house_suburban` (suburban_house, real scale, turned 180°): gambrel 1.5-storey with side carport and rear deck, 16.4 × 15.0 × 7.5 m; 145k → 19.5k tris (scale figures removed, interior culled by ray visibility), far 6.4k. Door leaf repainted as `KitDoorPaint`.
  - `house_duplex` (duplex_house, SketchUp inches × 0.0254): up/down two-flat, brick + siding, 10.2 × 16.9 × 8.0 m; 19.5k → 2.9k tris (10k-tri door hardware dropped), far 1.1k. Added a two-tread stair to the 0.51 m porch. Two front doors (lower = delivery door, upper on the balcony) and two mailboxes.
  - `house_farmhouse` (house.glb): farmhouse cottage with deep porch, 10.4 × 8.0 × 6.8 m; 4.8k → 1.8k tris, far 0.7k. Lawn plane removed; the alpha storm door replaced by a solid leaf with a glazed light.
  - Pipeline steps: bake transforms, drop junk, scale, ground, remap materials, merge doubles, ray-visibility culling (opaque windows, ground blocks), flip back-facing / double thin faces, limited dissolve, collapse to budget, coplanar fix (same test as `zfighting_test.gd`), smooth-by-angle, AO bake, far LOD.
- **Layout** (`ResidentialLayout`): `TYPES` has the three types with `hull` collision boxes (replace the single body box), porch deck boxes, stair ramps, `number` spots and the duplex `door2`; `pick_imported` (own RNG) gives 60% of corner lots (first lot after a cross street, park or shop; north/south/outer rows) to the 18 m suburban house and about one in nine mid-block lots each to the duplex and farmhouse (12.5 m lots), falling back to the kit house when it doesn't fit. 183 lots: 10 suburban, 21 duplex, 15 farmhouse; delivery addresses: 5 suburban, 5 duplex, 1 farmhouse. `ResidentialLayout.mix_imported = false` restores kit-only lots for A/B timing (`tmp/houses_profile_kitonly.gd`).
- **Rendering** (`HouseInstancer`): imported houses draw their detailed LOD to 45 m, the `_far` LOD 45–110 m (same 48 m MultiMesh cells), then the usual wall+roof massing (`MASSING` main-body sizes). Deep duplex/suburban lots skip the back-yard furniture that would land in the lane.
- **Verification**: city, citykit, higgsfield_housing, urban_access, regression, delivery_flow, tutorial and prop_placement tests pass; z-fighting test cells over 0.6 m² 227 → 205 (none involve the new houses; still failing on kit storefronts). Profile (A/B, same session): street 17.8 → 18.1 ms, park 17.2 → 17.3, roundabout 14.2 → 14.6, junction 15.7 → 15.6, crossing 19.5 → 19.0, downtown 14.1 → 14.3. Captures: `tests/capture_new_houses.gd -- <dir> [hour]`.

## Landscape: trees, plants and the forested horizon (2026-10-21)

- **Assets** (`tools/prepare_landscape.py`, headless Blender, sources in `source_assets/incoming_2026_10_21/`) -> `assets/landscape/`. QA renders and metrics: `assets/landscape/qa/` (`landscape_report.json`). Rebuild: `blender --background --factory-startup --python tools/prepare_landscape.py -- [--only id,...] [--qa-only]`, then `python -I tools/landscape_import_flags.py` (no automatic mesh LODs) and reimport.
  - 13 tree species at real size, origin at the trunk base: `plane_tree` (13 m, platano), `maple_a/b/c` (7-8 m red maples), `walnut_spring`, `walnut_autumn_a/b` (14.5-15.5 m), `linden_a/b/c` (10.5-12.5 m, from the animated tree; sway weights baked from its wind shape keys), `cherry` (7 m blossom tree; the 1.8M-triangle trunk is welded, pruned and decimated), `grove_a/b` (12.5 / 10 m, from the tree scene).
  - Each tree: LOD0 (2.7k-7.4k tris; bark decimated, leaves either re-carded as leaf-cluster cards whose texture is rendered from the source leaves, or the source cluster cards thinned and enlarged), LOD1 (1.0k-1.5k, cherry 2.8k; every species in one shared 1024 atlas, `trees_far.glb`) and a crossed-quad impostor (one 2048x1024 atlas, 16 slots incl. three conifers).
  - Kits: `forest_pack.glb` (8 background conifer/birch cards, 4 trunk+branch pines, 5 understory cards), `rocks.glb` (9 rocks), `garden.glb` (2 grass clumps, 3 shrubs, potted lily/snake/croton, bed plants, a 2.4 x 0.9 m bed edging). Textures <= 1024 (512 for small items); leaves are alpha-scissor.
  - `COLOR_0` = wind data (R sway, G flutter, B phase, A crown AO) for the shared shader `world/landscape/foliage_wind.gdshader` (no per-plant scripts).
- **`CityLandscape`** (`world/landscape/city_landscape.gd`, `CedarNeighborhood.landscape`): MultiMesh per (asset, LOD, cell) with visibility ranges (LOD0 to 26-42 m with shadows, LOD1 to 125 m without, impostors to 1400 m in one batch per 192 m cell). `CedarNeighborhood.tree()` routes the avenue and park trees here; `plant_city()` runs last in `_ready` so every spot goes through `PropPlacer` clear of everything already placed.
  - Atatürk Avenue: 57 plane trees. Side roads (İnönü / Çakmak) and cross streets: ~140 lindens / walnuts / groves at the back of the sidewalk, clear of lights, junctions and walks.
  - Lots: front-garden maples / cherries (not on the avenue), shrubs by the facade corners, 32 flower beds, grass by the fences, ~70 backyard shade trees.
  - Parks: one more tree per park (the corners outside the oval promenade; the original three trees keep their spots), shrub groups, grass and a rock group. The promenade, cross paths, fountain, statue and sign area stay free for `CityMonuments`.
  - Shops and the avenue restaurants: potted plants beside the doors. Edge-forest strips: rocks, understory cards, grass.
  - Horizon: ~8,400 trees on the meadow and hills outside the boundary (`terrain_height()` mirrors `build_city_assets.py landscape()`), dense in the band seen from the streets, noise patches further out, card conifers near and impostors far.
- `CityLandscape.legacy` (profile/capture arg `legacy`) restores the old kit trees without planting for benchmarks: `tests/profile_streets.gd -- out.json after legacy`. Measured on the same tree: street 12.9 -> 13.6 ms, park 12.7 -> 13.7, roundabout 11.5 -> 11.7, junction 11.8 -> 12.2, crossing 14.1 -> 15.1, downtown 11.5 -> 11.6 (+90..+410 draw calls; fewer primitives than the old trees in most views).
- Tests: `tests/landscape_test.gd` (in `run_tests.ps1`): budgets, kits, counts, no planting on carriageways / walks / park cores, trunk colliders. Captures: `tests/capture_landscape.gd -- <dir> [views] [legacy]`.

## City conflict audit: z-fighting, piercing, decals, LODs (2026-10-21)

- **Audit** `tests/city_conflict_test.gd` (rendered, in `run_tests.ps1`; `-- verbose [x0,z0,x1,z1] [probe=<text>]`): collects every non-residential mesh (kit buildings, downtown, restaurants and interiors, shops, Cedar House and furnishing, monuments, streets kit, signage, roads, landscape) and reports coplanar overlaps keyed by surface pair / facing / direction (`a_fight` under the depth-resolvable lift for the pair's visibility range - 1 mm to 150 m, 3 mm to 400 m -, `a_near`, `a_near_opposite`, `a_same_material`), face piercing (`b_pierce`, `b_buried`), decal lift (`c_decal`), LOD/massing overlaps (`d_lod`); `_intra` buckets for one model's own parts; pairs with the residential houses are listed as `res:*` for the house pipeline. Fails on any cross-object pierce, 0.02 m² fights/decals/LOD pairs, 0.25 m² intra. Baseline: 478 fighting pairs (6253 m²), 772 pierce, 42 decal, 144 LOD pairs; now 0 failing.
- **Fixes at source**: kit offsets (`kit_builder.gd` POST_OUT, `build_kit.py`), downtown corner posts / impostors (`district.gd`), restaurant interiors (floors trimmed like the ceilings, menu boards and chalkboards layered 1.5-3.5 mm), LED blades, street signs, bus shelters, civic buildings (`build_civic.py`), curved estate roads (junction extension, ring seam, asphalt trimmed on the street grid), landscape trees shrunk/dropped against buildings and impostor cards, Cedar House (`tools/cedar_shell_offsets.py`: consistent windings, sheets lifted 3 mm, opaque materials culled back-face in `house_asset.gd`; furnishing offsets in `furnishing.json`), coincident faces inside imported props separated with `tools/separate_coincident.py` (and `tools/find_zfighting.py --opposite`).
- **Downtown road levels** (`district.gd`, `campus.gd`): cross streets are now one carriageway piece per block face at the avenues' level (top 0.05; they were one 0.15 slab the whole width - a 10 cm step round every junction square, 12 cm over the street kit at x 120, with crosswalks 11 cm in the air), the westmost piece pitched 2 cm down to meet the street kit at x 120; paint 5 mm over the asphalt; campus cross streets start at the avenue's edge and stop at the civic road; civic sidewalks in runs between the cross streets. The urban-kit pavement slabs (`build_urban_kit.py` road_segment / intersection / alley_pavement / sidewalk) carry no bevel any more: stretched 25x it was a 10-30 cm groove along every seam.
- **Captures**: `tests/capture_conflict_closeups.gd -- <dir> [prefix] [only]` (99 views × 2 frames 4 cm apart, 1.65 m eye).

## Editor preview stays in sync with the game (2026-10-22)

- `tools/bake_editor_preview.gd` now bakes from the real game scene (`app/app_root.tscn`, menu closed, world built exactly as on Play, at the game's 11:30 start time). It includes the app-added store computers and pickup shelves.
- The copy keeps visibility ranges, re-links `visibility_parent` chains (so house near / far / massing LODs switch as in game and never draw on top of each other), `custom_aabb`, transparency and per-instance shader parameters (outfit and tint colours).
- A verification compared the bake with the live game: static content is identical (17,100 drawable nodes, 248,433 MultiMesh instances); only moving traffic differs.
- **City Preview Sync** editor plugin (`addons/city_preview_sync`, enabled in project.godot):
  - It fingerprints `app/ actors/ systems/ world/ assets/` (path + mtime of scripts, scenes, models, textures, data; about 200 ms).
  - When the fingerprint differs from `world/editor_preview/signature.txt`, it rebakes in a background Godot process (about 70 s). It waits until there have been no changes for 20 s, no game is playing and no `tmp/import.lock` exists.
  - It then reloads `EditorPreview` in the open scene.
  - A manual rebake is under Project > Tools > Rebake city preview.
  - `city_preview.scn` and `signature.txt` are machine-local (git-ignored).

## Third-person courier, rideable bike rig, new NPCs (2026-10-22)

- **Player body:** `assets/player/courier.tscn`, from the supplied Mixamo Ch42 + Jog Forward (`tools/prepare_player.py`, `tools/setup_player.gd`). It is 1.805 m, 42k tris, with a humanoid-retargeted `%GeneralSkeleton`.
  - The clips are in `assets/player/courier_anims.res`:
    - idles (Idle, Idle_Shift, Idle_Look, Idle_Talk)
    - Walk / Walk_Back / Strafe_L / Strafe_R
    - Jog (the supplied Mixamo jog) / Run / Sprint
    - Turn_L_90 / Turn_R_90
    - Jump_Start / Jump / Jump_Land / Land_Hard
    - Interact / PickUp
    - Bike_Seated / Bike_Pedal
  - Speeds and turn curves are in `clips.json`.
- **Camera** (`actors/player_camera.gd`): one Camera3D. Third person is the default: an over-the-shoulder SpringArm3D with collision, zoom 1.6–6 m on the mouse wheel, pitch -60..+35°. V toggles first person; the choice and the zoom are saved in `GameSettings`. Phone and bag views blend the camera to the eyes. The car keeps its chase camera, and V there gives an in-car view. The interaction ray (`target()`) starts at the character's eyes.
- **Body** (`actors/player_avatar.gd`, `actors/player_body_ik.gd`): an AnimationTree.
  - Locomotion is speed-matched, so there is no foot sliding.
  - Turn-in-place steps, physics-driven jumps with coyote time, and foot placement on steps.
  - The body turns at a limited rate toward travel and leans.
  - Footsteps fire on foot contacts.
  - Ctrl walks, W jogs, Shift sprints.
- **Gray bicycle drivetrain** (`tools/build_gray_bicycle.py`): a new 42T chainring, 172.5 mm cranks and pedals on a rotating `Crank`. Markers: `Seat` (0.870 m), `GripL` / `GripR` (on SteeringPivot) and `PedalL` / `PedalR`.
  - The rider sits at the bike root using Bike_Seated / Bike_Pedal: hips on the saddle, hands IK'd to the grips, feet on the pedals.
  - The crank turns with the rear wheel ÷ 2.2, and stops when coasting.
  - When stopped, the rider puts the left foot down.
  - Mounting and dismounting are 0.55 s blends.
  - The previous bike is in `assets/bicycles/archive/v1/`.
- **City cyclists** (`world/living_city/bike_rider.gd`, `BikeRider`): townspeople play the same Bike_Pedal clip with the crank synced, so they also sit on the saddle with their feet on the pedals.
- **NPCs:** the Avaturn avatar is the meet-at-door customer (`LivingAssets.door_customer()`, its own talking clip with face blendshapes). `character_with_clothes` was rigged in Blender and is pedestrian variant `clothed_man`.
- **Tests:** `tests/third_person_test.gd` (40 checks). Captures are in `tests/capture_third_person.gd` and `tests/capture_player_assets.gd`.

## Easy delivery: name tags, package hunt, one-button bag sequences, worn backpack (2026-10-22)

- **Customer name everywhere:** the phone's offer and active-order cards lead with the customer's name (44 px) plus order-code and package chips (`Food bag · medium`); the HUD objective reads "Collect Elif Kaya's order at Kebab House" / "Deliver to Elif Kaya · 105 Atatürk Ave"; an ORDER FOR plate under the top panel (the training card has the same plate); looking at a package shows a big NAME TAG panel above its receipt. Packages carry white name stickers (heavy first + last name, order code on an amber strip) on the front, back, wide sides and pizza lids (`PickupShelves.add_name_tags`).
- **Package hunt** (`PickupShelves.plan`): accepting an order restocks its shelf with yours and 4-7 other couriers' orders at random lanes / spots / turns, mixed kinds and sizes, often one or two look-alike names (same first or last name, `OrderDetails.confusable_name`), never a duplicate full name. Deterministic per order (seed = restaurant, order id, ticket, customer). Only lanes visible from the customer side are used (`find_usable_lanes`: two racks stand behind a counter). A wrong package says "This one is for Zeynep Arslan — you're looking for Elif Kaya (CE-012)."; no helper marks yours. Standing at the shelf brings the camera in over the shoulder.
- **One button** (E or left click on foot; F bag view and G drop stay as optional controls). `CourierSequence` (`actors/player_sequence.gd`) with the animation contract (`clips.json` "backpack" + per-clip `bag_track` / `package_track` / `flap_deg` / events):
  - shelf: Bag_TakeOff -> (package to the right palm, Bag_Hold) -> Bag_PackItem -> Bag_PutOn, ~4 s; state CARRYING when it drops into the compartment that fits.
  - leave at door: Bag_TakeOff -> Bag_TakeItem -> Bag_PutOn_Holding -> PlaceDown (in the marked area) -> proof photo -> Bag_StrapRight.
  - meet at door: knock, then Bag_TakeOff -> Bag_TakeItem -> Bag_PutOn_Holding -> Handover -> Bag_StrapRight.
  - without a bag: carried by hand (Carry_Idle / Carry_Walk), PlaceDown / Handover from the hands.
  - The courier stands still (`CourierPlayer.busy`); a second camera swings to a clear side / three-quarter view and back (`PlayerCameraRig.action_view`); first person uses the BagRig view. Without the contract the steps fall back to procedural IK poses.
- **Worn backpack** (`actors/player_backpack.gd`): `backpack_worn.tscn` / `backpack_plain_worn.tscn` on a BoneAttachment3D on the UpperChest, body straps shown, locomotion / idle / jumps / turns switched to their `_Bag` variants (`PlayerAvatar.set_bag_worn`); visible walking, running, jumping and riding; shadow-only in first person.
- **Training v3:** 13 tasks; the put-down practice and the drag-to-pack task are gone ("Find Elif Kaya's package" packs it in one press). Old saves in the removed tasks resume at the new one.
- **Tests:** `tests/easy_delivery_test.gd` (47 checks, in `run_tests.ps1`), `tutorial_test.gd` (59), `delivery_flow_test.gd`, `third_person_test.gd`, smoke test. Captures: `tests/capture_easy_delivery.gd -- <dir> [phone,shelf,wrong,pack,walk,ride,leave,meet,fp]`.

## ElevenLabs sound effects in the game (2026-10-22)
- **Sounds:** 82 sounds / 154 files from ElevenLabs text-to-sound-effects v2 in `assets/audio/elevenlabs/<category>/` (Git LFS). Generator `tools/elevenlabs_sfx/generate.py` + prompts in `sounds.json`; hit sequences (footsteps, landings, clicks, barks, clinks) are sliced into numbered takes (raw recordings in `_source/`, `.gdignore`d). Key: `.env.local` (gitignored, from `npx @elevenlabs/cli onboard`); venv at `C:\elevenlabs_venv`. Free plan: ~10 credits per second of audio; free-plan licence needs checking before a commercial release.
- **Wiring:** `systems/sound_bank.gd` (generated by `tools/elevenlabs_sfx/bank.py`) maps CityAudio's sound names to ElevenLabs files with a dB trim that matches each to the loudness of the sfx_forge sound it replaced (boost capped at +6 dB). `CityAudio.stream()` picks a random take; `trim()` is applied in play_ui / one_shot_at / loop_at / ambience / bike loops / signals; `has_sound()` replaces the old file-exists checks. Names not in the bank (owls, birds, engines, wet steps, bus door, customer thanks...) still play `assets/audio/sfx`.
- **New cues:** bag sequence sounds follow the clip data (`PlayerSequence.clip_event` / flap angle): bag off and onto the shoulder, velcro open / flap shut, package in / out, set-down at PlaceDown's release frame, strap; running steps on pavement (`footstep_run`), jump landings by fall speed, bike mount / kickstand, riding wind loop, house room tone, thunder in storms, long horn in jams, door closing behind the customer, menu hover / click / back, "not enough money" at the store.
- **Tests:** `audio_test.gd` checks every bank take loads, loops loop and trims stay sane. `easy_delivery_test.gd`: three frame-timing checks (tag panel, bag on the back while riding, first-person shadow) now wait up to ~1 s for the state instead of a fixed frame count (they flaked on the committed code too).

## HUD redesign and HudStyle theme (2026-10-22)
- **One style source:** `ui/hud_style.gd` (`HudStyle`) holds the HUD font stack, weights, type scale, colours, spacing and the panel / pill / key-cap / meter / order-chip builders; `app/app_root.gd`, `ui/mission_card.gd` and `ui/minimap.gd` build from it. No font files ship: DISPLAY = Bahnschrift (variable wght/wdth via `FontVariation`) for headings, numbers, labels and key caps; TEXT = Segoe UI Variable Text -> Segoe UI -> Arial for body text; MONO = Cascadia Mono -> Consolas for the printed receipt. To bundle a font later set `HudStyle.BUNDLED_FONT` (and optionally `BUNDLED_DISPLAY_FONT` / `BUNDLED_MONO_FONT`) to a res:// path.
- **Type scale** in 1280x720 canvas units (stretch `canvas_items`: x1.5 at 1080p, x2 at 1440p, identical layout at every 16:9 size): 9 key caps / small caps, 10 eyebrow captions (uppercase, tracked), 11 secondary, 12 body / toasts, 13 prompt, 14 objective and task title, 17 customer name, 19 name tag, 21 clock, 26 speed. Previously the objective was 21 and the HUD mixed system fonts per widget.
- **Layout:** left column 320 wide stacked in a VBox (`hud_stack`: objective panel with street eyebrow, then the ORDER FOR chip outside training, then the training card), so nothing can overlap. Right column 248 wide: clock, date · day, weather, wallet, ENERGY / FOOD / WATER / WC meters (mint / amber / red), supplies as key caps; the package NAME TAG paper card and the menu modal open under it. Bottom left: backpack line (`[F] BACKPACK  Empty · look inside`, or PACKING / HOLDING / ON THE GROUND), 148 px minimap (dark rim, N pill), route distance pill. Bottom centre: interaction prompt pill with key caps (`prompt_text` "[E / Click]  Take ..." is parsed by `HudStyle.parse_keys`) over a context-aware controls bar (on foot / riding / car) that fades to half opacity after 12 s. Bottom right: speed while riding. Toasts: top-centre pill sized to the text (max 460, wraps). Crosshair: a small ringed dot. Prompt, controls and crosshair hide while the phone, bag or a menu is open.
- **Training card:** 320 wide, 14 px title, 11 px instruction capped at 4 lines (shorter task hints in `systems/tutorial.gd`), 3 px progress bar and pips, the order chip inside; `TutorialDirector` adds it to `hud_stack`.
- **Captures:** `tests/capture_hud.gd -- <dir> [prefix] [train,shelf,order,ride,phone,meet,bag,receipt,goal|all] [WxH]` (rendered; the size argument switches the window to windowed at that size after the game's settings applied fullscreen).

## Prop colliders: the courier no longer walks through street and yard props (2026-10-22)
- **`PropColliders`** (`world/props/prop_colliders.gd`): primitive boxes for instanced props, added by the code that places the instances (same deterministic transforms, so solids always match the visuals). Local shapes are in `SOLIDS`, measured at courier-body height with `tools/measure_prop_solids.gd` (rendered; re-run after changing a prop GLB). One StaticBody3D per 64 m cell and layer holds the shapes (184 bodies), boxes of one size share a BoxShape3D. `DS_NO_PROP_COLLIDERS=1` turns them off for A/B timing.
- **New colliders (1,869 shapes):** front picket fences and hedges (one box per unbroken run, open at the front walk), yard bins, patio sets, BBQs, raised beds, sheds, delivery mailboxes and address posts (`HouseInstancer`); restaurant A-frames, door planters and corner plants (`RestaurantInteriors`); downtown / campus café chairs, benches, street lamps, birch / maple trunks, garden planters, parked courtyard bicycles, delivery carts, parking / loading / campus signs, parking meters, lobby mailboxes and grocery shelves, hydrants, bins, newspaper boxes, bike racks, cones, pallets, rain gardens, the downtown bus shelter (`DowntownDistrict.place`); flower planters (`StreetFurniture`); shop pots and rocks >= 0.4 m (`CityLandscape.add_prop`); park raised planters and showroom cars / bikes / scooters (`CedarNeighborhood`); store pickup lockers (`StoreTerminals`); Cedar House floor plants and porch troughs (`house_asset.gd`).
- **Already solid before (unchanged, layer 1):** houses, garages, side privacy fences, utility poles, Cedar House furniture, restaurant counters / tables / walls, avenue street lights, all tree trunks, `StreetFurniture` benches / bins / hydrants / racks / signs, signal poles, bus stops, monuments, buildings.
- **Deliberately walk-through:** grass, flower beds and garden beds, shrubs, forest understory cards, low rocks, cycle-track flexible posts, scaffolds, wall pipes / conduits, decals and markings, canopies, lamp heads, wires, small counter / shelf decor, NPCs (scripted), the horizon forest outside the boundary. Kitchen equipment stays behind the restaurant counter-line collider.
- **Layers:** 6 (value 32) thin props, 7 (64) bulky props (sheds, showroom cars, bus shelter). The player body masks 1 | 4 | 16 | 32 | 64 (on foot, bicycle and car). The third-person SpringArm masks 1 | 16 | 64 (it ignores thin props: no twitching along fences and poles); the action-view probe 1 | 16 | 32 | 64. The E / click ray (mask 1), AI traffic and pedestrian rays (1 | 4) never see the prop layers, so a counter or planter cannot swallow the ray to a shelf or door and traffic is unchanged.
- **Cost (headless, whole city, 3 runs each with / without):** physics process while walking 9.70 vs 9.60 ms mean (noise; the time is AI traffic and people), courier capsule `test_move` 9.2 vs 9.0 us per sweep. Static bodies cost nothing per step in Jolt.
- **Tests:** `tests/prop_collision_test.gd` (in `run_tests.ps1`, 194 checks, ~5 min; sections selectable with `-- block bike sidewalk doors restaurants cedar stores downtown spots`): pushes into fences, hedges, benches, bins, mailboxes, sheds, hydrants, planters, café chairs, lamps, rocks, a street light, a tree trunk and Cedar House furniture; rides the bike into a lamp post; walks Cedar Lane sidewalks, to all 36 delivery doors, into the 13 corridor and 3 avenue restaurants to their pickups, through the Cedar House front door, into the 4 stores and the 79 open downtown lobbies; aims the E ray at shelves, counters, doors, kiosks and the REST plaque; checks spawn / bike / door spots are free. `prop_placement_test` still finds 0 colliders on road surfaces. Captures: `tests/capture_prop_colliders.gd -- <dir> [views]` (debug shapes: magenta thin, orange bulky, cyan other).
- **Notes:** 39 new downtown colliders stand on pedestrian-graph lines (kerbside benches, bins, hydrants, campus stop signs); NPCs walk through them as they already did visually. Existing thin layer-1 colliders (street lights, signs, signal poles, trunks) still stop the camera arm.

## Front-yard planting, hedges and bins (2026-10-22)
- **Removed** (primitive kit pieces, GLBs deleted, dropped from `build_houses.py` / `manifest.json`): `garden_bed` (the lumpy flat-shaded blob bushes beside every front walk), `hedge` (a textured box) and `bins_trio` (three coloured boxes at the lane). The raised bed in back yards still carries small blob plants.
- **Yard kit** `assets/landscape/yard.glb` (`tools/prepare_yard_planting.py`, headless Blender; reuses `prepare_landscape.py` helpers; QA `assets/landscape/qa/yard_*.png`): `flower_bed_a..c` (2.4 x 0.8 m) and `flower_bed_d` (1.6 m): bevelled granite setts, domed mulch, two staggered rows of flowering geraniums (red / pink / lilac / orange, from `sketchup_assets/geranium_flowering_plants_free.glb`, one 1024 atlas); `pot_geranium_red/pink/lilac/orange` (rolled-rim terracotta / charcoal / cream pots, 0.8 m); `boxwood_ball`; `hedge_section` (2.36 x 1.1 x 0.8 m clipped privet: lumpy rounded core with a seamless procedurally painted small-leaf texture plus leaf-spray cards). Stone, mulch and pots share one plain atlas (`yard_ground`), so a bed or pot is 2 surfaces. Wind data in COLOR_0 as the other landscape kits.
- **Placement** `CityLandscape.front_planting` (seeded per lot): each side of the front walk gets the longest bed that fits along the facade where the house's low parts stand < 0.5 m proud (`front_profile`: lot-local max z of every near-LOD vertex below 0.95 m per 10 cm strip, so beds never meet porches, stairs, bays or skirts), 20 cm in front of them, 1.1 m from the walk centre line; long beds get a boxwood ball at their corner end, sometimes another at the house corner; a matching pair of potted geraniums at the foot of the steps (or beside a ground-floor door). Delivery lots always get both beds; spots pass `PropPlacer.problem` (driveways, walks, mailboxes, other props) and are recorded (`flower_bed`, `front_boxwood`, `door_pot`). The facade-corner shrubs only fill corners the beds left free. Visibility 45-48 m; pots and balls cast shadows, beds do not.
- **Hedges** stay `HouseInstancer` pieces (same sections, same `PropColliders` runs) drawn with `hedge_section` (`LANDSCAPE_PIECES`; MultiMesh custom data carries the foliage tint).
- **Lane carts** `assets/sketchup/props/street/cart_trio.glb` (`tools/prepare_yard_bins.py`, modelled): black garbage, blue recycling and green organics carts with domed lids, hinge and handle bars, wheels; grime / scuff plastic atlas; 3 surfaces for the trio. (The street pack's wheelie bins were tried first: their rims are layered shells 0.4-1 mm apart that `house_conflict_test` flags.) `bins_trio` collider resized to 2.1 x 1.08 x 0.74 m.
- **Litter bins** `litter_bin_slat_green/black/red.glb` (`tools/prepare_litter_bins.py`, modelled): 24 powder-coated flat-bar slats on three hoops, a dark liner with a black bag folded over its lip, a domed rain bonnet on three stays, grime at the foot. `StreetFurniture.SWAP` draws the avenue bench bins (`litter_bin_red/green`, names kept for colliders and tests) and the park / corridor `trash_bin` with them; downtown `trash_bin` uses the black one (`DowntownDistrict.PROP_SWAP`). Downtown `trash_bin` collider now 0.58 x 0.98 m. The old perforated bins stay in the catalog, unused.
- **Shader fix** `foliage_wind.gdshader`: the alpha outputs were written only on the cutout branch, so opaque surfaces using the shader (bark, the new hedge / boxwood cores) were partly see-through. All four are now assigned on every path.
- **Colliders:** door pots get `PropColliders` boxes (0.42 x 0.8 m, thin layer); beds and boxwood balls stay walk-through.
- **Captures / timing:** `tests/capture_yards.gd -- <dir> <prefix> [street,street_far,close,porch,row,hedge,lane,bench,park_bins,corridor,downtown|all] [hour]` (rendered; prints median / p95 frame ms, draw calls, primitives per view). Draw calls in the suburban views +0..+80 (about +3 %), primitives +4-17 %; frame times were within run-to-run noise (9-18 ms medians for identical code on this laptop).

## Boot freeze fixed: building-mesh cache, live loading screen, lighter editor (2026-10-22)

- **Problem (measured, `tests/perf_probe.gd`):** the city is built synchronously while `app_root.tscn` loads (the Neighborhood child readies before app_root). That held the main thread for 41.8 s, so Windows showed the window as "Not responding". `tests/boot_profile.gd` charged 15.8 s of it to KitBuildings: `KitBuilder.flush()` welded 16,161 kit pieces (836k vertices) through SurfaceTool on every launch, with identical output each time.
- **KitBuilder cache** (`world/citykit/kit_builder.gd`): merged building meshes (geometry only, no materials) are stored in `user://cache/kit_buildings/<hash>.res`, 142 files and 28 MB. The hash covers each batch's pieces, transforms, glass swap and LOD range, the kit GLBs' modification times and `CACHE_VERSION` (bump it if `merge()` changes). Stale files are pruned after a rebuild. Headless runs never read or write the cache, because their dummy renderer cannot be trusted for mesh data, so test suites keep exercising the live merge. With a warm cache KitBuildings takes 0.48 s instead of 12–16 s. Cold and warm renders (`capture_citykit.gd`) are identical on the buildings; the only differences are wind-moved foliage and birds.
- **Loading screen** (`ui/loading_screen.gd`, started from `app_root._enter_tree()`): it counts `SceneTree.node_added` while the city builds and, every 50 ms, draws a title, the subsystem name and a progress bar straight into a RenderingServer canvas item. It then pumps window events and force-draws one frame. Control widgets cannot be used for this, because their redraws are deferred calls that never run while the main loop is blocked. While loading, root-viewport 3D is off (a forced frame never renders or compiles shaders for the half-built city) and root-viewport input is off. In headless runs the screen does nothing.
- **Result:** boot is 14.6 s (was 41.8 s), and the window responded in 59 of 59 half-second samples (`Process.Responding`). Riding at 9 m/s for 60 s: median 22 ms, p99 31 ms, worst 71 ms, two frames over 50 ms (was a 281 ms worst). Gameplay is script-bound (about 20 ms of process time per frame), spread over many systems at 1–3 ms each (`perf_probe.gd -- 60 9 attrib`); no single hotspot.
- **Editor:**
  - `EditorPreview.reload()` now loads the 70 MB `city_preview.scn` on a background thread. The synchronous load held the editor for 1.3 s or more at open and after each rebake; the old preview stays visible until the new one is ready.
  - `sketchup_assets/`, `reference_images/` and `volkswagen-jetta-gli-2025/` get `.gdignore`. These are Blender-side sources read by `tools/*.py` straight from disk; the game never loads them, yet Godot imported about 480 files (1.5 GB) from them.
  - The root download GLBs (`car_model.glb`, `generic_passenger_car_pack.glb`, `ace_11_*.glb`, `generic_civil_service_vehicles_pack.glb`) are also unused by the game but stay where they are.
- **Probes:**
  - `Godot --path . --script res://tests/perf_probe.gd -- [seconds] [speed] [attrib]`: BOOT, SPIKE and PERF lines, or ATTRIB per-subsystem frame cost.
  - `Godot --path . --script res://tests/boot_profile.gd -- [depth]`: BOOTCOST per subsystem.
