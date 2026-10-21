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
