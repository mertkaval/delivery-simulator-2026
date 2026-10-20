# City asset and gameplay upgrade

The 18 September downtown/living-city additions are documented in [LIVING_CITY_REPORT.md](LIVING_CITY_REPORT.md) and [DOWNTOWN_REPORT.md](DOWNTOWN_REPORT.md). The five old car identifiers now instantiate the new fleet equivalents, and citizen creation uses weighted characters. Original files described below remain preserved.

## Blender source workflow

`world/build_city_assets.py` is the deterministic Blender workshop. Run Blender with `--background --python world/build_city_assets.py -- CATEGORY`. Categories are `vehicles`, `nature`, `people`, `buildings`, `details`, `commerce`, `landscape`, or `all`. Editable `.blend` files and triangle manifests are in `world/city_assets/source/`; 34 runtime GLBs are in `world/city_assets/`. Sources are excluded from Godot import with `.gdignore`. Residential variants have their own workshop and source directory.

The models use shaped body sections, wheel arches, bevelled edges, swept tubes, articulated pivots, separate architectural parts and individual leaf/blade polygons. Wheels and NPC joints retain articulation. Hidden simple collision proxies keep small decorative details from snagging the player.

| Family | Details | Triangles per model |
|---|---|---:|
| Five car types | Body profiles, wheel arches, cabins, lamps, mirrors, handles, wheels/rims/treads | 14,136–14,568 |
| Bicycle | Frame, spokes, drivetrain, cables, pedals, rack, kickstand | 7,500 |
| Scooter | Shaped body, footboard, seat, mirrors, steering, wheels | 4,780 |
| Citizen | Face/hair, clothing, limbs, shoes and joints | 4,896 |
| Maple/birch/conifer | Branch networks and leaf polygons | 15,718–28,738 |
| Grass clump | Eighteen bent blades | 54 |
| Park garden | Oval paths, pergola, planters and flowers | 8,828 |
| Shops | Entrance, glazing, counter, shelves and pendants | 2,208–2,856 |

Restaurants include dining furniture, kitchens/appliances, counters, lighting and staff. Apartments have balconies, windows, entrances and roof services. Equipment models include helmet, gloves, backpack and insulated bag. WC fixtures, kiosk, mailboxes, planters, street lamps, benches, fountain and meadow terrain complete the asset set.

## Material sources

Original procedural shaders are combined with 1K PBR textures from Poly Haven. Download URLs, MD5 hashes and CC0 designation are recorded in `world/city_assets/textures/sources.json`.

- [Leafy grass](https://polyhaven.com/a/leafy_grass)
- [Brown bark](https://polyhaven.com/a/bark_brown_01)
- [Brick wall](https://polyhaven.com/a/brick_wall_11)
- [Asphalt](https://polyhaven.com/a/asphalt_03)
- [Wood](https://polyhaven.com/a/synthetic_wood)

Blender files retain editable material assignments. `CityAssets` supplies shared runtime PBR overrides with diffuse, OpenGL normal and roughness maps. Imports generate mipmaps and GPU compression, with anisotropic sampling. Cloud sky uses seamless procedural noise; ground and foliage use custom shaders.

## Shops and needs

Locations are Godot metres `(x,z)`. Shops face positive Z; enter through the centre opening and approach the right-hand counter.

| Shop | Location | Purchases |
|---|---|---|
| Trail & Tool | (-92,-32) | Helmet $28, gloves $18, lights $24, insulated bag $35, backpack $45 |
| Cedar Cycles | (92,22) | Commuter bicycle $320 |
| Northside Motors | (-92,22) | Hatchback $1,950; sedan $2,450; van $2,850; pickup $2,950; SUV $3,150 |
| Volt Scooters | (92,-32) | Scooter $890 |
| Public WC/water | (-40,32) | Free washroom and drinking water |

The kiosk at (13,17) also sells equipment. Meals cost $6.50; bottled water $1.50. Restaurant counters offer these services when no delivery pickup is active. Gloves reduce riding fatigue by 15%, backpack reduces sprint fatigue by 20%, lights illuminate at night, and the insulated bag adds 30 seconds of tip protection on future pickups. Helmet is cosmetic riding kit; no injury system exists. Select an owned vehicle at its shop to place it in the forecourt.

Purchases debit the existing ledger, reject duplicates and insufficient funds, and persist ownership, active vehicle and needs. Validation rejects invalid prices, mismatched ownership, unowned active vehicles and nonfinite needs. Older saves gain safe defaults.

## Layout, optimization and verification

`CityCatalog.estate_roads()` shares driveway and roundabout paths with neighborhood construction, minimap and grass exclusions. Apartment lots at x ±92, z -110/-190 connect through forecourts to side roads, the southern connector and northern cross streets. This is a bounded deterministic layout, not a general city solver.

259,379 grass clumps are instanced in 16 m chunks, with a 48 m render range, shared material/mesh, no collision and no grass shadows. Repeated imported meshes are batched by mesh/material/block. Roadside details are instanced separately. Traffic, articulated people and moving home doors remain independent. Assets use distance limits and imported mesh LODs. Simple collision and unshadowed secondary lights limit physics/shadow cost.

Warm world-only benchmark on RTX 3070 Laptop GPU, Forward+, 1280 × 720, VSync disabled: street median 5.30 ms / p95 8.57 ms; park 3.66 / 7.60 ms; roundabout 3.18 / 7.83 ms. This is a short local measurement before the final landscape addition, not a low-end-device or complete-gameplay guarantee. Reproduce using `tests/profile_city.gd`.

`tests/run_tests.ps1` runs economy, dispatch, regression, city and lifestyle suites. Starter-home tests use a memory-only save service. Capture scripts produce native Godot images in `tmp/`. New test/capture scenes must set `save_enabled = false` before scene startup or inject memory-only saving. The first lifestyle test's save incident is documented in PROJECT_STATE.md.
