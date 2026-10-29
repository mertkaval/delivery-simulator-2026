# Placement rules (Mert Road Studio v4)

Source: `tools/roads/mrs/placement.py` (`place_all`, `entrance_paths`, `place_park`), `junction.py`
(signals), `footbridge.py` (bridge reservations), `lighting.py` (presets, real light sources),
`furniture.py` (footprint / access contract, see `FURNITURE.md`). Stations are metres along the evaluated
road centre line (`structures.centre_line`); heights come from the evaluated cross-section
(`structures.surface_z`), so nothing floats on cambered roads. Sides `l` / `r` look in the curve
direction; right-hand traffic puts the forward direction on `r`. Deterministic for a seed; skipped
optional items are recorded with a reason, never forced.

## 0. Sidewalk zone model (per road side, d = metres from the kerb line outward)
| zone | extent | used by |
|---|---|---|
| planting / furniture strip | 0 .. strip | trees (mulch bed), grass / low shrubs, benches / bins / racks on paved pads, lights, signs |
| kerb zone | 0 .. 0.7 (no strip) | lights, signs, hydrants, bus pole |
| furniture zone | 0.35 .. walk0 | benches, bins, racks, cabinets, tree pits with grates, shelters |
| walking corridor | walk0 .. walk1, width `walk_min` = 1.8 | kept free of every physical footprint (reserved rects every 3 m) |
| frontage | walk1 .. sidewalk width (0.3) | |
Each item is an oriented rectangle (its `mrs_footprint`, local +Y = front) plus access rectangles
(`mrs_access` front/back/left/right). A footprint may not touch another footprint, an access space or
a reserved area; an access space may not touch a footprint and (benches, bins, racks, cabinets, shelters)
may not reach the carriageway; bike-rack access may not enter the walking corridor. Occupancy uses a 4 m
spatial hash.

## 1. Reservations (first)
| reservation | extent | blocks |
|---|---|---|
| walking corridor | see above | every physical footprint |
| crossing landing / kerb ramp | road end .. setback + crossing + 1.2, full sidewalk | everything |
| junction corner | landing + 3 m | furniture, trees, lights, utilities, bus items |
| junction sight triangle | corner + 12 m, sidewalk + 6 m behind | items taller than 1.2 m (poles of signs / lights / signals are exempt) |
| bus boarding area | 12 m x 1.6 m at the kerb | all but the stop's own items |
| building entrance `MRS_Entrance_*` | 2.4 m path from the back of the sidewalk to the anchor | everything (+ a paved access path is built) |
| driveway `MRS_Driveway_*` | 4 m | everything |
| manual override `MRS_Exclude_*` | display size | everything |
| footbridge span footprint | plan footprint | trees, lights, tall items, plants |
| footbridge approaches + foot paths + columns | plan footprint | everything |
| signal poles | 0.6 m square | (solid) |
| park paths | path + 0.6 m | everything |

## 2. Infrastructure
- **Signals** (junction builder, `control = "signals"`): one combined pole per corner, IDs `<junction>_S<i>`,
  phases pair opposite approaches (no conflicting greens). In Godot `MrsStreetBlock.set_phase()` drives the
  per-signal lens materials (each signal has its own copies).
- **Signs by condition** (unchanged from v3, re-positioned beyond the crossing landing): STOP / YIELD /
  PRIORITY by the junction `control` (roundabout entries: YIELD), NO ENTRY against one-way approaches,
  PEDESTRIAN CROSSING before crossings, street-name double blade once per junction, SPEED n after each
  entry, ONE WAY, BICYCLE ROUTE where a cycleway starts. All face the traffic they address.
- **Bus stop** (`bus_stops=[{id, road, along, side}]` or `MRS_BusStopAnchor_*` empties): shelter at the back
  of the sidewalk with its open side to the kerb (`MRS_F_BusShelter`), boarding + walking space in front
  (>= max(1.6, walk_min) m, otherwise the shelter is skipped with the measured shortfall), the planting
  strip paved along the 12 m boarding area, flag pole at the front end of the boarding area facing the
  arriving bus, information board, bin, BUS STOP lane text.
- **Streetlights**: `lighting.preset_for(road class, carriageway width)` gives library, spacing, setback and
  arrangement (single / staggered / opposite; roads with a median >= 1.5 m use median double-arm poles);
  candidates shift +-2 / 4 m before skipping; `lighting.add_light_sources()` adds the real spot lights as
  children (the emissive lamp mesh stays decorative). `RULES["light_spacing_scale"]` scales the spacing.
- **Drain grates**: in the gutter (0.28 m inside the carriageway edge) just upstream of every crossing
  landing, then every 24 m; never in a crossing.
- **Hydrants**: kerb zone, one per side per 90 m from a quarter of the road length, access 0.9 m all round.
- **Utility cabinets**: one per junction end and side, in the furniture zone just beyond the sight
  triangle, door to the walking corridor, on a pad, with an access cover beside it.

## 3. Furniture
- **Benches**: every 36 m (phase differs per side), back to the kerb, front clearance 0.9 m onto the paving;
  70 % with back, 30 % backless; a bin 0.75 m beside the bench (never in front of it).
- **Bike racks**: every 55 m; rows / hoops oriented so the bike access envelope stays out of the walking
  corridor (parallel to the kerb in narrow furniture zones), else skipped with the zone depth.
- **Bins**: next to benches, at the bus stop and just beyond each crossing landing.
- **Pads**: items standing in a planting strip get a paved pad (footprint + margin), edges sunk so they
  never float.

## 4. Planting
- **Street trees** (`game_trees`: the game's landscape-kit species, LOD0 + LOD1 + impostor): in planting
  strips >= 0.9 m (mulch ring), else tree pits with grates in furniture zones >= 1.25 m. Species pool by
  street style (`avenue`: plane / lindens, `residential`: linden / maple / cherry, `park`: walnut / grove /
  linden / maple); each candidate tries species, scale (1.05 / 0.95 / 0.85) and +-1.5 m until the crown
  clears: crown base >= 4.6 m over traffic lanes, >= 2.6 m over cycleways, >= 2.3 m over sidewalks;
  canopy away from streetlight heads; no tree within 30 m upstream of a sign (or 40 m of a signal) with a
  crown base below the sign face; canopy (+1 m) out of every footbridge footprint; canopies of neighbours
  overlap at most 45 %.
- **Landscape regions**: planting strips (grass layer with low-frequency density, low shrub clusters
  between trees) and the region behind each sidewalk by style: `park` (hedge line with gaps at paths /
  entrances / sight triangles, shrub groups, grass), `verge` (sparse shrubs and grass), `none`
  (`RULES["landscape"]["<road>:<side>"]`). Plants never enter paths, boarding areas, access spaces or
  sight triangles (low plants only). Points go to one scatter object per region with the
  `Landscape_Scatter` node group (instances from `MRS_GamePlants`).
- **Parks** (`place_park(col, rep, name, polygon, paths)`): paved paths (ramped onto the sidewalk, route
  connected, `dest` end = destination), Poisson-spaced park trees clear of paths / footbridges / sight
  lines, shrub groups around trees, meadow tufts in patches.

## Reporting
`place_all` returns `placed`, `skipped` `(road, kind, along, reason)`, `skip_summary`, `by_kind`, `items`
(world footprint corners + access rects per item), `regions`, `bus_stops`, `corridors`, `light_presets`.
`routes.build()` then checks connectivity and clear widths against these footprints.
