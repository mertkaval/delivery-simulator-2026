# Validation

Everything below was run headless in Blender 5.2.3 LTS on library version 21 (2026-10-29). It was also checked
interactively in the user's live Blender through the MCP connection.

## Tests

| test | what it proves | result |
|---|---|---|
| `tools/roads/tests/area_junction_test.py` | junction from four tongues; road at the tongues' level everywhere a red footprint is; reflex kerb corners are arcs of Inner Radius; roadside raised by Curb Height and never over the road; sharp back corners with Outer Radius 0; dense 0.5 m raster (676 cells) all correct; Show off empties it; Range on (5 m) / off (the object's mesh bounds, scaled in edit mode); a tongue outside the range is ignored; a gap the tongues enclose is road (no raised square); the junction follows a moved tongue (live); a mesh extension (bus bay) is road with its roadside band; a curve extension is road; every vertex at the tongues' level (objects at any height); no loose edges; an extension's band over a road's carriageway builds no roadside there but does beside it | OK |
| `tools/roads/tests/road_tongue_test.py` | real MRS roads (library): junction asphalt at road level at the centre; no tongue shows under the junction; the road carries on, crowned, past its tongue; no step where road and junction meet (the crown and bank fade out toward a tongue); the junction runs under the road's first centimetres, 2 mm below it (no hairline crack); the tongue's roadside covered by the raised junction roadside; rounded kerb corner; longer tongues grow the junction | OK (8 / 8) |
| `tools/roads/tests/custom_sign_test.py` | the CRM 2.1 sign: blue panel 0.600 x 0.600 m centred at 2.2 m, white Auto text in the upper half, a text edit changes the sign at once (194 -> 211 faces), the pole reaches the ground; the stop sign: red octagon 0.600 m across the flats, white text and border | OK |
| `tools/roads/tests/marking_lines_test.py` | painted areas exact: two solid edges 6.00 m2, + solid centre 9.00, dashed 3 / 3 7.50, double 10.50, + two dashed lane lines each side 16.50; lane lines at +-1/3, +-2/3 of the half width | OK |
| existing MRS tests: `junction_rules_test.py` (0 problems), `responsive_test.py`, `terrain_conform_test.py`, `grading_test.py` | the existing tool unaffected | OK |

## Comparisons with the video

`comparisons/*.jpg`: the video's viewport (top) over the reconstruction's render of the same example (bottom).
`build/reconstruct.py` builds the examples on real MRS roads at the tutorial's level (1 m).

| view | example | video evidence | assessment |
|---|---|---|---|
| A_top | four-way crossing | E25 12:27 | same layout: roads meet in one asphalt area, kerb corners rounded (CRM: Inner Radius 2 m on narrower, unmarked roads), sidewalks continue round the corners |
| A_persp | crossing, perspective | E27 13:30 | the junction is level with the roads; no seams |
| B_persp | T with a road climbing 6 m to the junction, last points level | E28 15:54 | the approach climbs and flattens into the junction as in the video; the crossing tutorial view is X-shaped, ours is a T (the tutorial's slope example also shows only one sloped arm) |
| C_top / C_persp | bus bay: square extension at the kerb, shelter, BUS / STOP | E35 20:48, E36 21:33 | the notch in the roadside with rounded inner corners, as in the video |
| D_top | cul-de-sac: round extension at a road end | E37 22:48 | the bulb with its sidewalk ring, joined to the road without seams |
| E_top | roundabout: round extension + island | E38 24:30 | ring road with a raised centre and rounded arm corners; CRM's island in the video is greenery on a sidewalk ring (an asset placed on top); ours is the raised island (paving) |
| F_top | car park + entrance + bay lines | E40 27:51 | entrance from the road with rounded corners, 2 x 14 bays (marking lines + Array) |
| G_front | custom signs | E47 34:57 | the CRM 2.1 sign and the stop sign |

Differences that remain are listed with their reasons in [DECISIONS.md](DECISIONS.md). They come from inputs the video
does not show (class D) or from MRS's own road look: textured asphalt and paving, markings from MRS's rules.

## Defects found by validation and fixed in the tool

1. Footprint union returned nothing: Extrude Mesh leaves prisms open, Manifold rejects them. Closed prisms, then a
   different union (item 5).
2. Constant offsets typed into Extrude Mesh were ignored (implicit Normal field): every extrude offset is now linked.
   The bug made the sign panels thick and blank.
3. A group menu socket on several Menu Switch nodes left the menus empty: one Menu Switch per menu socket, Index
   Switch for every other use.
4. Black lines across every road end: the fills left faceless edges where a road end lies on the outer outline. Loose
   edges are deleted; tested (0 loose edges).
5. A raised square in the middle of a crossing: the exact boolean of touching prisms left T-junction seams read as an
   extra outline. Replaced by winding-number fills (no boolean); dense raster test.
6. Tongues that do not quite meet left a raised square: holes enclosed by road footprints are road; the area is solid.
7. An extension's roadside band reaching past a tongue built a raised slab across the road end (the lens-shaped
   highlight in the cul-de-sac render): the roadside never covers a road's own carriageway.
8. A step and a camber mismatch where a road met the junction: the crown and bank fade out toward a tongue end, as
   they do toward a height-locked junction end.
9. The car park entrance stopped at the sidewalk (scene layout, not the tool): the entrance reaches into the
   carriageway, as in the video.

## Live behaviour (measured in the user's Blender)

- Inner Radius 2 -> 6 m: asphalt 262.3 -> 267.6 m2 at once.
- Bus bay moved 4 m: the junction edge followed exactly (x 10.41 -> 14.41).
- Sign text and colour edited: redrawn at once.
- The add-on's Add Custom Sign / Add Extension / Add Area Junction ran and produced working objects; the new
  junction meshed the new extension on the next evaluation.
