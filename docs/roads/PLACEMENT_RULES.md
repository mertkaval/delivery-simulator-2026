# Placement rules (Mert Road Studio v3)

Source: `tools/roads/mrs/placement.py` (`place_all`), `junction.py` (`_place_signals`), `road.py`
(instanced markings / scatter). All distances in metres along the road's trimmed centre line; sides are
`l` / `r` looking in the curve direction; right-hand traffic puts the *forward* direction on `r`.

## 1. Reserved space first
| zone | extent | blocks |
|---|---|---|
| junction / crossing | trimmed end .. + stop setback 0.6 + crossing 2.5 + 5.0 (3.0 without crossing) | everything |
| junction sightline | trimmed end .. + 15 | trees |
| bus stop | ±10 around the stop | everything |
| manual exclusion | empties named `MRS_Exclude*` (display size = half length) | everything |
| cycleway + buffer | lateral: nothing is ever placed inside the cycleway (offsets are measured from the asphalt edge outward) | all |
| walking width | `sidewalk_min_walk` 1.5 m of paving stays clear; furniture needs a 3.0 m sidewalk | furniture |

## 2. Signals (junction builder, `control = "signals"`)
One combined pole (vehicle 3-aspect + pedestrian 2-aspect) on each corner, standing on the curb corner
0.7 m back, heads facing the cars arriving on the approach to its left. IDs `<junction>_S<i>`; metadata
links each pole to its approach, the pedestrian crossing it serves and a phase. Phases pair opposite
approaches (`signal_phases`), so no conflicting vehicle movements share a green. The demo animation is a
phase sequence only (not a traffic simulation).

## 3. Signs by condition (never random)
| condition | sign | where |
|---|---|---|
| approach whose junction `control` is `stop` | STOP | arriving side, 3 m before the crossing zone |
| `priority` junction, side road | YIELD | arriving side |
| `priority` junction, main road | PRIORITY ROAD | arriving side |
| approach with 0 incoming lanes (one-way against it) | NO ENTRY | facing the junction |
| crossing on the approach | PEDESTRIAN CROSSING | 6 m before the crossing |
| junction | street-name double blade | first corner reached, once per junction |
| `speed_limits[road]` | SPEED n | 12 m after each entry |
| one-way road | ONE WAY | 8 m after the entry |
| cycleway on a side | BICYCLE ROUTE | 10 m after the entry on that side |
Signs keep 4 m from each other and 0.5 m behind the curb. Contradictions are avoided by construction:
a junction has exactly one `control`; `signals` places no stop/yield signs.

## 4. Streetlights
Every 28 m, alternating sides, 0.45 m behind the curb, ≥ 6 m from other items; tall type on roads wider
than 12 m. Skipped where reserved.

## 5. Furniture
Benches / bins / bike racks every 22 m (±2 m jitter, seeded) on both sides where the sidewalk is ≥ 3 m,
in the strip beyond the walking width; ≥ 3 m from other items.

## 6. Trees
Only in planting strips ≥ 0.9 m (or tree pits), every 11 m, species pair chosen by the street style
(`avenue`: oak/maple, `residential`: birch/maple, `boulevard`: poplar, `coastal`: palm, `park`: oak/pine),
A/B variants alternating, scale 0.9–1.1 and yaw seeded; canopy clearance 2.5 m from other items;
never within 15 m of a junction (sightlines) or in the crossing zone.

## 7. Scatter
Grass / rocks only on `kind == embankment` faces (embankments and planting strips) via Geometry Nodes.

## Reporting
`place_all` returns `{"placed": [...], "skipped": [(road, kind, along, reason)], "by_kind": {...}}`; the
demo block prints the skipped items with reasons instead of forcing overlaps.
