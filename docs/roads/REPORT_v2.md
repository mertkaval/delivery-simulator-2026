# Mert Road Studio v2 — Blender-only procedural road generator (2026-10-28)

Source: `tools/roads/mrs/` (package, ~4,500 lines incl. the generated asset library), manual
`tools/roads/README.md`, deliverable `tools/roads/mert_road_studio_v2.blend` (rebuilt from source by
`tools/roads/build_mrs.py`), asset library `tmp/roads/assets/mrs_assets.blend` (95 assets with
previews and catalogs). Validation sheets: `docs/roads/v2/*.png`.

## What works (all verified by running it headless and by inspecting renders)
- **Road group `MRS_Road`**: ~1,800 nodes, 80 inputs in 10 panels. Terrain raycast conforming with
  smoothing, embankments (fill and cut) with softness, retaining walls in deep cuts, parabolic crown
  camber, superelevation banking from curvature, asymmetric lanes, shoulders, bike lanes, parking
  with bay ticks, raised median, bevelled curbs, sidewalks, four centre-line modes, lane/edge lines,
  lane arrows before junctions, elevated deck with pillars scaled to the ground, five barrier types,
  props / streetlights / trees / manholes / drains / embankment scatter, viewport-vs-render quality,
  collision-only and realize switches, metre UVs and `kind` attribute.
- **Terrain**: `MRS_TerrainConform` lowers a terrain copy under the roads (subdivides near them,
  never lifts terrain, ignores decks) without a dependency cycle.
- **Junctions**: any number of approaches with concentric filleted corners, trims, roadside clearing
  and height locks on the roads; crosswalks, stop lines, sidewalk corner pieces, traffic lights;
  roundabouts (island, ring, entries, splitter islands, yield lines, sidewalk ring); dead ends;
  rebuild-all and auto-update on curve edits.
- **Structures**: gantry signs with text, custom text signs, cable-stayed pylons with stays,
  horseshoe tunnels with portals, bus stops.
- **Asset library**: 95 generated objects (22 signs with extruded text, 9 trees, 6 lights, 4 traffic
  lights, 6 barriers, 3 piers, 17 props, scatter, lids, gratings, structure parts), asset-marked.
- **UI**: N-panel *Road Studio* (presets, terrain, junctions, roundabout, dead end, rebuild/auto,
  structures, custom sign, material presets, export-ready, GLB export).
- **Samples**: city block (8 junctions, dead end, gantry, bus stop), mountain road (terrain, cut/fill,
  tunnel, branch junction), highway with overpass on pillars and gantries, roundabout village,
  cable-stayed bridge over a valley. 20 validation renders, GLB + collision export of every sample
  (city block 106k tris / 30k collision tris).

## Verified vs. inferred vs. proposed (reference products)
- MRoadGen v1.1.0 (CC0): downloaded and inspected headless — verified facts: 385-node generator,
  raycast placement with offset, outline expansion + merge-by-distance junctions, Delaunay embankment,
  overpass pillars at an interval, viewport/render quality menus, panelled inputs. Adopted as ideas
  (re-implemented differently); no nodes or assets copied.
- City Road Maker 2.1: observed from its product and docs pages only (junction tongues, Extension
  Path/Square/Round, Pull Terrain, Export-Ready, 22 setups / 100+ assets / 5 samples). Its node
  internals were never seen; our feature set was proposed from that list.
- The YouTube video (City Road Maker 2.1 update) had no transcript available; nothing was taken from it.

## Not done / limitations (honest list)
- Roads only meet at their ends (no mid-curve joins); junction surfaces are flat.
- Retaining walls are stepped per station; tunnels do not carve the terrain above them.
- No lane tapers, turn pockets, slip lanes, refuges or signal logic; roundabout entries are simple
  curves, not true fillets.
- Materials (final): procedural, six surface types, six presets, seamless 1K/2K bakes verified by a
  seam metric; bakes drop the position-dependent effects (tire tracks, edge dirt, object-Z grime), the
  puddle coat and bump normals are render-engine features; embankment rocks are flat facets.
- Godot integration was explicitly out of scope for this task (Blender only).
