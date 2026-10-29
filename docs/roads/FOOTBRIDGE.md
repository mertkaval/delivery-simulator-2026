# Procedural pedestrian footbridge (Road Studio v4)

`tools/roads/mrs/footbridge.py`: a Python connection solver plus the editable `Footbridge` Geometry Nodes
group. Python decides *where* everything goes (span, landings, stairs, ramps, supports, foot paths,
lights) and checks it against the street; Geometry Nodes turns the solved skeleton into deck, beams,
stairs, railings, columns and collision.

## Placement (explicit, never scattered)
An anchor empty `MRS_FootbridgeAnchor_<name>` next to a road defines the crossing station (its position is
projected onto the road centre line). Its custom property `mrs_footbridge` (JSON) holds the solver
parameters. A bridge exists only where an anchor was placed by the author or by a demand rule.

```python
from mrs import footbridge
obj, plan = footbridge.make("SB_Footbridge", road, along=100.0, collection=col, width=3.0, clearance=5.3, style="Girder")
footbridge.rebuild("SB_Footbridge")      # after moving the anchor / editing the road or the Style input
footbridge.rebuild_all(collection)       # every anchor in a collection (used by regeneration)
```

## Solver parameters (`DEFAULTS`, metres)
| parameter | default | meaning |
|---|---|---|
| width | 3.0 | deck / ramp / stair width |
| clearance | 5.3 | required clear height over the highest asphalt point under the span |
| style | Girder | Girder (fascia beams, 1.05 m structure depth), Truss (through truss, 0.55 m), Box (1.3 m) |
| landside_gap | 0.6 | head landings start this far behind the back of the sidewalk |
| landside_depth | 16 | depth available behind the sidewalk for switchback legs |
| max_span | 42 | longer spans need an intermediate support in an allowed region |
| support_spacing | 9 | column spacing under the approach legs |
| stair_rise_max / stair_going | 0.165 / 0.30 | risers are equal: n = ceil(H / rise_max) |
| stair_max_risers / stair_landing | 12 / 1.5 | flights of at most 12 risers, landings between |
| ramp_max_slope / ramp_max_rise / ramp_landing | 1:12 / 0.75 / 1.6 | runs of at most 0.75 m rise, landings between |
| leg_gap / max_legs | 0.5 / 6 | switchback leg spacing and limit |
| ends | stairs on the shorter side, ramp on the longer | per end (l / r): list of {type, dir: long / short / +1 / -1, switchback} |
| along_clear | 18 | approaches stay this far from the road ends (junction zones) |
| lights / light_spacing | on / 9 | real point lights along deck and approaches |

These are the generator's design defaults, not a claim of compliance with a specific accessibility or
bridge standard.

## What the solver does
1. Widths at the station include a completed lane transition (the avenue widens through its taper).
2. Walking level = highest asphalt under the span + clearance + structure depth of the style.
3. Head landings sit landside on both ends; span supports go under them. When the span exceeds
   `max_span`, intermediate supports are tried only in allowed regions (median >= 1.45 m with 0.5 m
   clearance, planting strips / verges). Lanes, cycleways, sidewalks and crossings are never used. When
   no region fits, the plan is marked incomplete and says why.
4. Each approach (stairs or ramp) is split into runs / flights with landings, then folded into 1..6
   switchback legs until it fits the available length along the road and depth behind the sidewalk.
   If nothing fits, the approach is **not** generated and the message names the space it would need
   (a 1:12 ramp for 6.7 m of rise needs about 9 runs, 80 m of run plus landings).
5. The foot of every approach is joined to the sidewalk by a paved path; where that path passes under
   the structure the headroom is checked (>= 2.3 m) and the path is moved beyond the structure if not.
6. Columns under head landings, turn platforms and every <= 9 m along legs higher than 1.4 m.
7. Output: skeleton chains, footprint polygons (reserved by placement), supports with region/validity,
   pedestrian route edges (sidewalk -> foot path -> stairs/ramp -> head landing -> deck), light points.

## Geometry Nodes group `Footbridge`
Input: the skeleton mesh (edge chains with point attributes `part`, `side` (mitred), `width`, `depth`,
`kind`, `fwd`, `going`, `rise`, `top`, `foot`). Panels:
- **Structure**: Style (menu), Column Radius, Truss Height, Truss Panel.
- **Railing**: Railing Height (1.3 m), Handrail Height (0.9 m), Post Spacing, Baluster Spacing, Balusters.
- **Lighting**: Handrail LED (decorative emissive strip; real lights are separate objects).
- **Materials**: Deck, Structure, Concrete, Railing, LED.
- **Output**: Collision Only (walk surfaces with stairs as inclines, rail walls, columns).

Frames: skeleton -> curves; Road_Surface (deck, landings, ramps with the style profile); stairs (steps
between stringers); columns, footings, crossheads; railings (posts, top rail, handrail, bottom rail,
bars, kick plate, LED); truss (span only); assembly + collision. Cross-section profiles are editable
mesh loops in `MRS_FootbridgeProfiles` (`MRS_FB_Profile_Girder/Box/Truss/Stair`) with per-point
`px` (fraction of width), `pxm` (m), `pd` (fraction of depth), `pt` (m), `pmat` (0 walking surface).

## Metadata and game export
- `obj["mrs_footbridge_plan"]` (JSON): status, messages, deck_z, rise, span, clearance, supports,
  footprint polygons, ped_edges (with `step_free`, `max_slope`, `rise`, `length`, points), lights.
- The bridge is part of `<block>.glb`; its collision-only evaluation is part of `<block>_collision.glb`.
- `<block>.json` -> `footbridges[]` (plans without the drawing chains) and the route graph edges
  `footbridge_stairs`, `footbridge_ramp`, `footbridge_deck`, plus a `footbridge_ramp` /
  `dismount_link` pair in the bicycle graph.
