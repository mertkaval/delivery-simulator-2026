# Port Halden's streets by Mert Road Studio

Port Halden (the generated city, `tools/cityforge`) no longer draws its own streets. Mert Road Studio builds
them from the city plan: every road, junction, crossing, kerb, sidewalk, back lane and bridge, and the street
assets placed on them by the studio's rules (lights, signals, signs, bus stops, benches, bins, racks,
hydrants, cabinets, drains and street trees). Since the 2026-10-29 rework the new city is a road layout only:
CityForge keeps the terrain and water; its lots, houses, shops, towers, public buildings, parks and furniture are
left out of the plan (the classic city and every asset file stay; buildings will be placed on the frontage plots
later). `mrs_streets.py --with-buildings` builds the earlier variant.

Two cities side by side: the classic city (buildings, the game's default) stays in `assets/cityforge`; the
roads-only city is installed in `assets/cityforge_roads` (`tools/cityforge/build.sh`, default) and opens with
`world/cityforge/port_halden_roads_preview.tscn` (F6). `CityForgeWorld.use_city(dir)` points the world (and its
streets) at either; `tests/cityforge_test.gd -- res://assets/cityforge_roads/` and `tests/capture_cityforge.gd ...
city=res://assets/cityforge_roads/` test / capture the new one. `build.sh --with-buildings` rebuilds the classic.

Blender first: `build.sh` assembles the whole map in Blender (`tmp/cityforge/port_halden_map.blend`: streets,
junctions, signals, signs, markings, street assets, graded terrain and water; open it to check anything), validates
every road, junction, sign and lane mouth there (`mrs_junction_atlas.py`, with a render of every junction:
`tmp/cityforge/atlas/junctions_*.jpg`) and installs into Godot only when the validation is clean (`--force`
overrides).

```
tools/cityforge/build.sh            # terrain -> plan -> MRS streets -> CityForge build -> install -> import -> test
tools/cityforge/build.sh --cf-streets   # the old CityForge street ribbons instead
```

| Step | Where | What |
|---|---|---|
| Network | `tools/roads/mrs/citynet.py` (pure Python) | city.json graph -> MRS roads, junctions, lanes (rules below) |
| Build | `tools/roads/mrs/city.py` `build()` | curves + MRS_Road modifiers, driveways, junctions (tilted planes), anchors, placement |
| Export | `city.export()` | chunk GLBs, collision, materials, kit, records, the adapted plan + fitted ground |
| Driver | `tools/cityforge/mrs_streets.py` (Blender, headless) | `-- <plan> <out> [--region x0,y0,x1,y1] [--blend f] [--from-blend f] [--plan-only] [--profile]` |
| Game | `world/cityforge/mrs_city_streets.gd` (`MrsCityStreets`) | used by `CityForgeWorld` when the plan says `streets = "mrs"` |
| QA | `tools/cityforge/mrs_streets_render.py`, `tests/capture_cityforge.gd`, `tests/port_halden_streets_test.gd`, `tests/port_halden_streets_perf.gd`, `tools/roads/tests/road_bank_test.py` | renders, captures, contracts, timing |

The MRS base library (node groups, materials, asset collections) is built once into
`tmp/roads/city/base.blend` (~6 min, versioned by `city.BASE_VERSION`); a city build then takes ~13 min and the
export ~10 min.

## Rework (2026-10-29): roads only, every rule derived in the tool

The city is now a road layout only, and the tool derives everything from the roads' own parameters instead of
fitting the city:

| Rule | Where | Derived from |
|---|---|---|
| Paint clear zone: lane, centre, edge and cycle paint, cycle colour, buffer hatching and bicycle symbols stop at the junction's stop line / crossing | road inputs `Mark Clear Start / End` (set by `junction.end_zone`) | crossing setback + width + stop line gap / width |
| Turn arrows: each arriving lane shows the movements it may make | road inputs `Turns Start / End` (`junction.movements`: 1 left + 2 straight + 4 right per leg with outgoing lanes), `junction.lane_use`; arrows `Straight / Left / Right / StraightLeft / StraightRight / LeftRight / All` | the junction's legs and their lanes (U-turns excluded); the vehicle movement paths (`movements.py`) use the same `lane_use` |
| Arrow position | `Arrow Distance` measured from the stop line; `Arrow Min Lanes` (default 2) | the clear zone |
| Cycle crossings | junction: coloured bands with elephant feet joining the cycle lanes of opposite legs through the junction, never on a zebra; a band leaving the asphalt is not drawn | the legs' cycle lane offsets |
| Signals | a mast arm at the stop line with one head over each arriving lane (`ARM_LANES` = 2+), plus the corner post (vehicle + pedestrian heads) | lane count, lane width, median, kerb (`signage.make_signal(arm_side, head_x)`); one kit model per variant in the game |
| Speed signs | road input `Speed Limit`; `assets.speed_sign(v)` builds any value on demand | the road's speed |
| Back-lane dropped kerbs | `citynet._lane_mouth` (the lane's ray meets the street centre line), lot line from the built street's cross-section, station on the street as built (after the junction trims) | street geometry |
| Vertical alignment | `mrs/grading.py` `network_profiles`: natural ground averaged per class (`SMOOTH`), node heights shared, grade limited per class (`MAX_GRADE`: local 16 %, downtown / arterial 12 %, boulevard 10 %, lane 18 %, bridge 6 %) | the natural terrain (`terrain.npz`), not CityForge's graded lots |
| Bridges | decks span bank to bank at `BRIDGE_CLEARANCE` (4 m) over the water level, their end nodes lifted so the deck reaches it at the bridge grade; `citynet.bridge_gaps` joins dead-end streets facing each other across water | water mask + level |
| Ground | `grading.grade`: under a surface 0.3 m below it; beyond, the natural ground clipped by cut (1:1) / fill (1:2) batters from the surfaces; the first cell keeps the per-street plane cap | the built road and junction surfaces |
| Addresses | `city.frontage_plots`: a plot every 20 m on both sides of every street, behind the sidewalk, clear of junctions, other corridors and water, facing the street, unique addresses | the streets |

Bugs found on the way (all in the tool, all fixed): the asset library's markings step cleared the collection, so
the bicycle symbol (and merge arrows, separator posts) had no model; and an unlinked constant `Instance Index` is
ignored by Instance on Points (its implicit field is the point index): bicycle symbols, parking ticks and merge
arrows drew a row of different arrow models (the "wedge" in the cycle lane). Driveway stations were taken on the
untrimmed street, so a lane's dropped kerb landed metres away whenever a junction trimmed the street.

Checks: `mrs/validate.py` (road paint in clear zones, arrow kind / direction / count, junction inputs, cycle bands
on zebras, signal heads over lanes, speed signs, lane-mouth kerbs) - on a test scene
(`tools/roads/tests/junction_rules_test.py`) and on the whole city (`tools/cityforge/mrs_junction_atlas.py`, with a
render of every junction).

## The network (citynet)

CityForge draws its streets as overlapping straight ribbons, so its graph tolerates what the MRS builders
reject. `citynet.build()` resolves it, recording every decision in the report:

- **Clusters.** Nodes joined by a road shorter than 10 m merge. A road shorter than the two junction trims it
  connects (computed exactly like `junction.build_junction`) first gets tighter corner radii at both ends (down
  to 3 m), then its junctions merge. A merged junction sits at the centroid of its nodes weighted by the roads
  leaving it (rank² × width), so boulevards and arterials keep their line.
- **Duplicates.** Two roads between the same pair of junctions: the more important one stays.
- **Angles.** Approaches closer than 25° (CityForge has crescents leaving a node 1-7° apart): the less important
  road is dropped.
- **Chains.** Roads through plain bends of the same class become one MRS road; each bend gets a circular fillet
  sized for the inner sidewalk, or stays a 2-way junction when the segments are too short for it. A short
  connector of another class between two long roads takes their class (a 25 m "local" piece inside a boulevard).
- **Lanes.** Back lanes become 6 m service roads from lot line to lot line; the streets they meet get an MRS
  driveway there (dropped kerb, concrete apron across the sidewalk).
- **Junction planes.** A junction on a slope is a tilted plane fitted to its approach roads' graded profiles
  (0-22 m out, grade capped at 22 %). The roads lock to the plane's height and bank to its cross-fall at their
  ends (road inputs `Bank Start` / `Bank End`), so the edges meet. A flat plate would have left 56 junctions more
  than 0.5 m off their approach roads; the planes leave 14 (the 3 worst are steeper than the cap).

Result for Port Halden: 473 CityForge roads -> 414 MRS roads (50.1 km) + 80 back lanes (14.2 km), 203
junctions (all built), 80 road ends, 15 merged clusters, 4 duplicates and 6 near-parallel approaches removed,
21 bend fillets.

## Street profiles

Every profile fills CityForge's right of way exactly (carriageway, then kerb 0.25 m + sidewalk 4.35 m =
verge 1.6 + sidewalk 3.0), so lots, fences, front walks and doors keep their places.

| CityForge class | Width | MRS profile |
|---|---|---|
| local | 11 m | 1 + 1 lanes × 3.0 m, parking 2.5 m both sides, no centre line, 1.35 m planting strip |
| arterial | 18 m | 2 + 2 lanes × 3.25 m, double centre line, buffered cycle lanes 1.8 m + 0.7 m buffer, planting strip |
| boulevard | 18 m | 2 + 2 lanes × 3.4 m, 4.4 m median with refuges, planting strip |
| downtown | 16 m | 2 + 2 lanes × 3.0 m, parking 2.0 m, double centre line, fully paved sidewalks (tree pits) |
| bridge | 18 m | elevated deck on pillars (ground probe), 2 + 2 × 3.25 m + 2.5 m shoulders, 2.2 m sidewalks, parapets |
| lane | 6 m | 1 + 1 × 2.75 m service road, flush edges, no markings |

All city roads: no superelevation, a 1.2 m skirt under the sidewalk's back edge (`Edge Depth`; streets on fill), the node group's
own manhole covers and gratings off (the placement puts drain grates and access covers as kit instances).
Junction control: CityForge signal -> MRS signals (zebra crossings, signal poles with phases), stop -> stop
signs, uncontrolled T -> priority / yield, other uncontrolled -> none (parallel-line crossings). Speed limits:
local 30, downtown 40, arterial / boulevard 50.

## Placement

`placement.place_all` over the whole network, with entrance anchors at every house door and shop / tower /
public / warehouse front (the sidewalk in front stays clear), exclusion anchors at the CityForge furniture that
stays, CityForge's 74 bus-stop positions as MRS bus stops, street styles by class (tree species), and city
densities: benches every 72 m, bins 110 m, racks 150 m, utility cabinets only at signalised junctions, no
real light sources (thousands of lamps: the heads glow at night) and no planting-strip scatter (not drawn by the
game). Result: 18 888 placed (lights 2389, trees 3690, drains 5371, hydrants 793, benches 943, bins 1604, racks
430, cabinets 755, bus stops 72 of 74 with 50 shelters, signs 1993), 3179 optional items skipped with a reason.

## The plan adapts

`city.write_plan()` writes the plan CityForge then builds from:

- `streets = "mrs"`: `build_city.py` skips its road ribbons, junction patches, corners, sidewalks, kerbs and lanes;
  `CityForgeWorld` does not draw its lamps, traffic lights, stops, hydrants, benches, stop signs and name boards
  (the lists stay in city.json for game systems).
- Street trees (within the right of way): removed, 3999 (MRS plants its own).
- Buildings a street runs through: 7 houses (with lot, fence, garage) and 31 shops that CityForge had drawn
  across the diagonal arterial and boulevards are removed (listed in `mrs_removed`).
- The ground: every grid point under an MRS surface goes 0.3 m below it (raised or lowered: deeper than a kerb, so
  the ground between a sidewalk point and a road point stays under both). Every point within one cell of one goes
  no higher than the street surface's plane minus 0.15 m: one plane per street round the point (fitted to that
  street's grid targets and extended to the point), the lowest of them, so neither the terrain mesh nor the
  height-map collider (both split a 4 m cell into triangles) rises through a sidewalk's back edge, a steep street
  does not drag its neighbours down by its grade, and a road meeting a higher cross street is not lifted by it.
  Points at least 1.5 m inside a house or garage keep their height; shops, towers and public buildings stand on
  0.8 m foundations at their lot lines, so the ground under their street edge may follow the sidewalk down.
- Public buildings' forecourts stop at the lot line (they lay 1 cm over the new sidewalks).
- The road graph (routes, minimap, the HUD's street names) loses the 10 CityForge roads the network dropped
  (duplicates and near-parallel approaches).

Also fixed in CityForge (both street modes): corner shops on arterial street ends are turned a quarter but their
size was not swapped, so 74 of them overhung their sidewalks by ~5 m each side (`plan_city.py`).

## Export contract (assets/cityforge/mrs)

- `chunks/c_<i>_<j>.glb`: `MrsRoads_<i>_<j>`, the drawn streets of the 256 m chunk (polygons by centre), city
  coordinates. Materials are texture-less proxies `PHX_<name>`; UV = (lateral, along) metres, UV2 = (lane width,
  half median), COLOR = road shader masks. Stations are merged along straight stretches where the strips stay
  coplanar (the cross-section keeps every vertex), smooth shading with sharp edges.
- `chunks/c_<i>_<j>_col.glb`: `MrsCol_<i>_<j>`, the drivable / walkable surfaces (no markings), positions only;
  polygons within 1 m of a chunk edge are in both chunks (a ray exactly on a shared edge cannot slip between two
  separate trimeshes).
- `mrs_materials.glb`: one quad per road material with its baked tiles (JPEG); the game maps the proxies by name.
- `mrs_kit.glb`: `KIT__<library object>` per placed model, `MRS_PH_Signal`, `MRS_PH_StreetName` (blank blades).
- `mrs_city.json`: Blender world coordinates (Godot = (x, z, -y), yaw unchanged): `instances` {lib: [x, y, z,
  yaw, scale]}, `signals` (junction, phase, approach, pos, yaw), `junctions` (phase count), `labels` (street-name
  blade texts), `street_name_signs`, `trees` (species), `items` (footprints for colliders), `roads` (MRS street
  centre lines: class, width, bridge, the CityForge roads each replaces), `report`.

## In the game

`CityForgeWorld` (when `streets = "mrs"`) hands the streets to `MrsCityStreets`: the chunk scenes go under the
CityForge chunk nodes (the collision pass builds trimeshes from `MrsCol_*` near the courier, like its own
parts), road materials come from `mrs_materials.glb` (asphalt with the MRS road shader), the kit joins
CityForge's MultiMesh groups (same cells, ranges, fades), signals cycle on the GPU (`mrs_signal_lens.gdshader`:
per-pole phase in the instance custom data; green 18 s, amber 3 s, all-red 2 s, walk 12 s), street names are
Label3Ds on the blades, street trees use the MRS foliage (LOD0 / LOD1 / impostor, trunk colliders), placed items
get box colliders (bucketed by chunk, one shape per size), and lamp heads follow `set_night`. In play a chunk's
collision is built as one job per frame (each trimesh, then the boxes) instead of all at once.

## Evidence (2026-10-29)

All on Godot 4.7.2, Windows, the reference RTX 3070 laptop. Images in `docs/roads/city/`.

| Check | Result |
|---|---|
| `tools/cityforge/build.sh` (terrain to test, one command) | completes; streets stage 22 min, CityForge build ~5 min |
| Network | 414 MRS roads, 203 junctions built, 0 failures; 80 back lanes, 160 lane driveways |
| `tools/roads/tests/road_bank_test.py` | BANK_TEST OK: banked ends match the plane's cross-fall (-0.0995 vs -0.100), seam step 3.2-3.4 cm on 10-15 % planes vs 2.65 cm flat (the kerb bevel) |
| `tests/port_halden_streets_test.gd` (rendered) | 14 / 14: 64 chunks, 15 651 instances, 453 signal poles, 386 street-name labels, 3690 trees; 1182 probes on every MRS street (carriageway + both sidewalks) all hit a street surface 0.02-1.3 m over the fitted ground, never under it; the courier starts on a sidewalk |
| `tests/cityforge_test.gd` | 19 / 19 (houses on their ground, HLOD, collision, build time) |
| `tests/port_halden_game_test.gd` | 18 / 18 (doors, pickups, stores, routes in Port Halden) |
| `tests/run_tests.ps1` | every headless suite passes; rendered: city conflict 10 / 10, Port Halden streets 14 / 14; perf budget: boot and video memory pass, ride frame time fails under machine load (see below) |
| `tests/asset_budget_test.gd` | 5 / 5 after `tools/cityforge/vram_textures.py` (textures extracted from the MRS GLBs come in lossless) |
| Captures | `compare_*.jpg`: the same game cameras with CityForge's streets (before) and MRS streets (after); `game_street_level.jpg`, `game_courier_views.jpg` (the real game, courier camera); `blender_renders.jpg` |

Performance, `tests/port_halden_streets_perf.gd` (the city alone, a camera at 1.7 m on an 855 m street route from
the starter neighbourhood into downtown at 12 m/s, 40 s, vsync off, 1600 x 900):

| | CityForge streets | MRS streets |
|---|---|---|
| median frame | 2.9-3.2 ms | 2.8 ms |
| p95 frame | 5.2-5.5 ms | 3.9-4.0 ms |
| worst frame | 40 ms | 70-78 ms |
| draw calls (median) | ~1815 | ~2455 |
| primitives drawn (median) | ~0.87 M | ~1.91 M |
| video memory | 2962 MB | 3031 MB (extracted textures VRAM-compressed; 3236 MB lossless) |
| city build (load) | 1.9 s | 5.6-5.9 s |
| files | chunks 73 MB | chunks 62 MB + MRS 85 MB (streets 58 MB, kit 11 MB, textures, records 3.5 MB) |

Frame times above are from a quiet machine. A later run with other sessions loading the CPU (43 %) gave median
3.3 ms, p95 4.8 ms and an 11.4 s load, so compare the two columns only within one session. The game's own
frame-time budget (`tests/perf_budget_test.gd`, the classic city, which this work does not load) measured a
52 ms ride median under that load (budget 28 ms; 22 ms measured 2026-10-23); boot (19.9 s) and video memory
(5.36 GB) were within budget.

## Limitations

- The worst frames (70-78 ms) come when the courier first nears a chunk and its collision is built: the slowest
  single job is CityForge's own fence trimesh (54 ms for one chunk); the MRS street trimeshes take 10-34 ms. The
  city also loads ~4 s slower (MRS chunks, 3690 trees, kit).
- Merged junction clusters (diagonal / boulevard triangles, 15 of them, up to 74 m across) are single large
  junctions: crossings and stop lines are at the approaches, the middle is plain asphalt, and the minor roads bend
  up to ~20 m into the junction centre.
- 3 junctions on slopes steeper than 22 % keep a partly levelled plate (more than 2 m off their approaches before
  the roads' 14 m blend); the ground was refitted under them by up to ~5 m.
- Road ends without a junction (80, mostly at the city edge) end with the plain road cross-section.
- No real light sources on the 2389 lamps (the heads glow at night, as CityForge's did); night views are as dark
  as before.
- CityForge's own culture furniture, fences, buildings and their collision are unchanged (only reserved around).
- The game's road graph is still CityForge's (routes follow its node positions; the 10 roads the network dropped
  are removed from it); traffic, townspeople and buses are still not in Port Halden.

