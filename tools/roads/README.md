# Mert Road Studio v2

A procedural road-and-street generator for Blender 5.2, written as a Python package that builds
its own Geometry Nodes groups, shader groups, prop library, junction builder, structures, N-panel,
export and five sample scenes. Nothing is hand-modelled; `build_mrs.py` regenerates the whole
deliverable `.blend` from source.

```
# in Blender (Python console / text editor) or through Blender MCP
import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/roads")
import mrs; mrs.build_all(); mrs.register()          # groups, materials, props, panel
mrs.samples.city_block()                             # one of five sample scenes
```
Headless deliverable + smoke test + validation renders:
`blender --background --factory-startup --python tools/roads/build_mrs.py -- tools/roads/mert_road_studio_v2.blend`

Open `tools/roads/mert_road_studio_v2.blend` and the sidebar tab **Road Studio** (N panel) has
everything; the modifier panel of a road shows all inputs grouped in panels.

## v4 additions (complete street environment)
Full rebuild + validation of the demonstration block (build, regeneration scenarios, roundabout /
dead-end networks, export, day / night / traversal renders, save + reopen):
`blender --background --factory-startup --python tools/roads/tests/street_block_v4_test.py` (add
`-- --base` to reuse the cached node-group build in `tmp/roads/v4/base_built.blend`, `--no-render`,
`--quick`). Godot check: `godot --path . --script res://tests/capture_street_block_v4.gd -- <export dir> <out dir> <cameras.json>`.
- **Footbridge** (`footbridge.py`, `Footbridge` group, `docs/roads/FOOTBRIDGE.md`): anchor-driven solver
  (clearance, span supports in allowed regions, stairs / 1:12 ramps folded into switchbacks to fit the
  footprint or reported as impossible, foot paths, columns, lights) + editable GN geometry and collision.
- **Furniture** (`furniture.py`, `docs/roads/FURNITURE.md`): 20 assets on one baked texture atlas, each with
  footprint / access / zone properties.
- **Street trees and plants** (`game_trees.py`): the game's landscape-kit species (LOD0 / LOD1 / impostor in
  Godot through `CityLandscape`) instead of the generated canopies.
- **Lighting** (`lighting.py`, `docs/roads/LIGHTING.md`): road-class presets, real spot lights per fixture,
  night setup; `world/roads/mrs_street_lights.gd` in Godot.
- **Placement v4** (`placement.py`, `docs/roads/PLACEMENT_RULES.md`): sidewalk zones, footprints + access
  envelopes on a spatial hash, reservations first, bus stops, utilities, landscape regions, parks.
- **Routes** (`routes.py`): pedestrian + bicycle graphs with connectivity, step-free and clear-width checks.
- **Roundabouts / dead ends** now have crossings with ramps, continuous corner sidewalks, a shared foot /
  cycle ring, and a filtered through path with a dropped kerb.
- **Godot**: `world/roads/mrs_street_block.gd` (loader), `world/roads/mrs_road.gdshader` (wheel tracks, curb
  dirt, gutter wetness from exported masks).

## v3 additions (street generator brief)
- **Shared street model** (`street_model.py`): every road's lanes, directions, widths, offsets, cycleways,
  sidewalks, trims, ramps, lane / pedestrian paths and every junction's approaches, crossings, signals and
  phases in one JSON (`docs/roads/STREET_MODEL.md`); `export.export_block()` writes it next to the GLBs.
- **Analytic sweep** (`Road_Sweep` group): strips are grids whose vertices sample the rail at their own
  station, so the cross-section is a function of the station: **lane transitions** (`Transition`, end lane
  counts, `Transition Start`, `Taper Length`, merge arrows), **curb ramps + tactile paving** at crossings
  (`Ramp Start/End`), per-station `half_l/half_r/drain` attributes for the shaders.
- **Cycleways** per side: None / Painted / Buffered (hatched buffer) / Protected (curb, posts or planters
  separator) / Two-Way (centre dash, symbols both ways); bicycle symbols + arrows; coloured bicycle
  crossings with elephant feet through junction approaches; **bus lanes**; **planting strips**.
- **Junction v3**: concentric curb / sidewalk corners (tighter outer arcs, roads trimmed at the asphalt
  tangent), zebra or parallel-line crossings, stop lines set back from the crossing, median noses, refuge
  islands, ramps requested on the roads, `control` = none / signals / stop / yield / priority, signal poles
  (`signage.make_signal`) with IDs and non-conflicting phases; slopes > 1.5 m, angles < 25 deg and nearby
  junctions are reported, not faked.
- **Rule-based placement** (`placement.py`, rules in `docs/roads/PLACEMENT_RULES.md`): reserved zones ->
  signs by condition -> lights -> furniture -> trees, with a skipped-items report.
- **Trees** (`trees.py`, `Tree_Variants` group): 12 species variants + LOD1, bark / foliage shaders.
- **Signage** (`signage.py`): 24 sign kinds with editable text, direction boards, signals with per-lens
  `State` materials.
- **Materials**: `clean` / `light_wear` / `heavy_wear` (+ `wet`, `fresh_highway`, `old_village`, `dirt_track`);
  paving, tactile, cycleway, pole metal groups; masks from `lat`/`half_l`/`half_r`/`drain`.
- **Demo block**: `samples.street_block()`; test `tools/roads/tests/street_block_test.py` (regeneration
  checks, export, renders); Godot check `tests/capture_street_block.gd`.

## Package (`tools/roads/mrs/`)
| module | what it builds |
|---|---|
| `nodes.py` | node-tree builder `T`, interface panels, menu switches, modifier input access |
| `road.py` | **`MRS_Road`** Geometry Nodes group (+ `Road_Profile`, `Road_Sweep` sub-groups; 100+ inputs in 11 panels) |
| `terrain.py` | demo terrain, **`MRS_TerrainConform`** (pull terrain to roads), `conform_terrain()` |
| `roads.py` | road objects, 6 presets, remembered inputs, `refresh_all()` |
| `junction.py` | n-way junctions (crossings, ramps, refuges, signals), roundabouts, dead ends, rebuild + auto-update |
| `street_model.py` / `placement.py` / `trees.py` / `signage.py` | shared model + export JSON, rule-based placement, tree variants, signs and signals |
| `structures.py` | gantry signs with text, custom text signs, cable-stayed pylons + stays, tunnels, bus stops |
| `materials.py` | shader groups `MRS_AsphaltShader` / `PaintShader` / `ConcreteShader`, presets, tile baking |
| `props.py` / `assets.py` | prop collections the group instances from (placeholders / generated library) |
| `ui.py` | N-panel and operators |
| `export.py` | GLB export (+ collision GLB), export-ready mesh copies |
| `samples.py` | city block, mountain road, highway + overpass, roundabout village, cable-stayed bridge |
| `qa.py` | EEVEE validation renders, street-level camera on the evaluated road |

## The road group (`MRS_Road`, one modifier on any curve)
**Output** - Viewport / Render quality menus (Preview = 2.5x coarser sampling via *Is Viewport*),
Realize Instances, Collision Only.
**Terrain** - Terrain object / collection, Conform (raycast every rail point onto the terrain,
+Height Offset), Smoothing (Blur Attribute on the heights and on the banking), Embankment with
Width and Softness (smoothstep slope to the terrain height sampled at every slope vertex; works for
fill *and* cut), Retaining Wall above a cut-depth threshold.
**Profile** - Lanes Forward / Backward (asymmetric), Lane Width, Shoulder, Bike Lane L/R, Parking
L/R, Median + height, Curb width/height/bevel, Sidewalk L/R + widths, **Crown** (parabolic camber in
%), **Superelevation** (banking from the signed turning angle between neighbouring tangents, blurred,
capped in degrees, applied as curve tilt), Resolution.
**Markings** - Centre Line menu (None / Solid / Dashed / Double), Lane Lines, Edge Lines, bike-lane
and parking lines, Parking Ticks (instanced across the bay every Bay Length), **Lane Arrows** per lane
before a junction (inner lane straight+left, outer straight+right, single lane straight), dash
length/gap, marking width.
**Structure** - Mode Ground / **Elevated** (deck of Deck Thickness under the surface, pillars from a
collection every Pillar Spacing, each scaled to the raycast ground height), Barrier Left / Right menus
(None / Guardrail / Jersey / Parapet / Railing), instanced 2 m segments.
**Roadside** - Props (random pick, facing the road, on the sidewalk or the verge), Streetlights with
Side menu (None / Left / Right / Both / Alternate), Trees with offset and jitter, Manholes, Drains.
**Scatter** - grass / rocks distributed on embankment faces only.
**Materials** - six material slots. **Junction** - Trim Start/End, Clear Start/End, height Locks
(set by the junction builder so terrain-conformed roads meet a flat junction).

Mesh attributes: `lat`, `along` (metres), `side`, `kind` (0 asphalt 1 marking 2 concrete 3 structure
4 embankment 5 bike), `UVMap` = (lateral m, along m).

Important Blender 5.2 facts learned the hard way: Curve to Mesh maps the profile's X to the lateral
side, **profile Y to world *down*** (Z-up normals) and profile Z along the tangent; a menu socket's
items only resolve when it feeds exactly one Menu Switch; fields evaluate in the context of the node
that uses them (capture heights as attributes before moving points); a road that reads the terrain
and a terrain that reads the roads is a dependency cycle - the conformed terrain is a second object
sharing the mesh, the roads raycast the hidden source.

## Junctions (`mrs.junction`)
`build_junction(name, at, roads, collection, crosswalks, stop_lines, corner_radius, traffic_lights,
terrain)` - any number of approaches (neighbours >= 25 degrees). For each pair of neighbouring
approaches the asphalt edge, curb line and sidewalk line are filleted with concentric arcs
(radius adapts on sharp angles); roads are trimmed past the furthest tangent point, their roadside
instances cleared, their heights locked to the junction level. The junction mesh carries the asphalt
polygon, curb faces/tops, sidewalk slabs, zebra crosswalks, stop lines; traffic-light poles are placed
on each corner facing the arriving traffic when the collection exists. Straight-through pairs make a
continuous sidewalk. `build_roundabout` (island, ring, entry stubs, splitter islands, yield lines,
outer sidewalk ring), `build_dead_end` (turning circle with sidewalk ring and the road trimmed at the
circle). `rebuild_all()` recomputes every junction from the roads' current curves;
`enable_auto_update()` does it when a road curve is edited.

## Asset library (`mrs.assets`, 95 generated objects)
`build_assets()` fills the collections the road group instances from, all procedural bmesh with
node materials, UVs and bevels, marked as assets with catalogs (`mark_assets`): Props 17 (bollards,
benches, bins, hydrant, bike rack, planter, bus shelter, mailbox, kiosk, newspaper box, picnic table,
fence post, utility pole), Streetlights 6 (emissive heads), Trees 9 species, **Signs 22 with real
extruded text** (STOP, YIELD, 30/50/70/90, no entry, one way, parking, bus, taxi, crossing, children,
roundabout, dead end, curves, roadworks, street-name blades) + `custom_sign(text)`, TrafficLights 4,
Barriers 6 (guardrail, Jersey, parapet, railing, hedge, fence), Pillars 3, Scatter 9, Manholes 3,
Drains 2, Markings 6, Structures 8 (gantry parts, pylon, abutment, tunnel portal, shelter, signal).
Catalogue renders: `tmp/roads/assets/catalogue_*.png`; test: `tools/roads/tests/assets_test.py`.

## Structures (`mrs.structures`)
`gantry_sign(road, along, texts)`, `text_sign(text, pos, shape, color)`, `cable_stays(road)`,
`tunnel(road, a0, a1)` (horseshoe lining + portal frames), `bus_stop(road, along, side)`.

## Materials (`mrs.materials`)
Four shader groups, each material one group node "MRS": `MRS_AsphaltShader` (Surface Type 0 fresh /
1 aged / 2 cracked / 3 concrete road / 4 cobblestone / 5 dirt, Cracks, Patch Amount, Tire Wear from
the `lat` attribute, Edge Dirt, Wetness with puddles + coat, 4D-noise aggregate mosaic), `MRS_PaintShader`
(wear on the aggregate tops, chipping, Yellow, bead Sparkle), `MRS_ConcreteShader` (slab joints by face
orientation, pores, Rust Streaks, Grime at the base), `MRS_EmbankmentShader` (grass -> dirt -> rock by
slope). Presets: dry, wet, worn_city, fresh_highway, old_village, dirt_track (`apply_material_preset`).
`bake_tiles(out_dir, res)` bakes seamless albedo / normal / roughness tiles (Use UV + Tile Size, 4D
torus coordinates) for engines; `tools/roads/tests/materials_test.py` renders every type / preset and a
2x2 seam check (`docs/roads/v2/materials.jpg`).

## Terrain workflow
1. `mrs.terrain.demo_terrain()` or your own mesh -> panel *Use Active as Terrain*.
2. Roads conform to it (Conform on); embankments fill and cut.
3. *Pull Terrain to Roads* makes `<terrain>_Conformed` with `MRS_TerrainConform` (subdivides near the
   roads, lowers terrain under the surfaces, blends within Reach; never raises terrain, ignores decks).

## Export
`mrs.export.export_glb(path, collection)` - evaluated meshes, metre UVs, +Y up; `<path>_collision.glb`
with kinds 0/2/3/4 only. `export_ready(objs)` converts to plain meshes. Procedural shaders need the
baked tiles (`materials.bake_tiles`) in an engine.

## Validation
`tools/roads/build_mrs.py` is the test: it rebuilds everything headless, asserts >= 25 roads and
>= 12 junctions evaluate to meshes with UVs, exports the city block and renders 20 views to
`tmp/roads/v2/samples/`. Contact sheets of the validation renders are in `docs/roads/v2/` (city_block, mountain_road, highway, village, bridge_valley, materials, assets).

## Reference research
MRoadGen v1.1.0 (CC0, github.com/MaartenNauta-Pathtrace/MRoadGen) was downloaded to
`tmp/reference/mroadgen/` and inspected headless: a 385-node generator over a mesh-edge network with
raycast placement, outline expansion + merge-by-distance junctions, Delaunay embankments, overpass
pillars, viewport/render quality menus and panelled inputs. Ideas taken: terrain raycast + smoothing,
embankments, quality menus, input panels. Nothing was copied. City Road Maker 2.1 (Superhive) was only
seen through its product page / docs page: junction "tongues", Extension Path/Square/Round, Pull
Terrain, Export-Ready flags, 22 setups / 100+ assets - those feature categories guided the scope.

## Known limitations
- Roads must *end* at a junction (no joining mid-curve); junction surfaces are flat.
- Retaining walls are per-station slabs (visible steps on steep cuts); the tunnel does not remove
  the terrain above it (the conformed terrain is lowered under the road instead).
- Lane tapers, turn pockets, slip lanes, pedestrian refuges and signal timing are not modelled.
- Traffic lights / detailed props depend on the generated asset library (`assets.py`).
