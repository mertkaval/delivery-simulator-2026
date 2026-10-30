# Inferred design decisions (class C) and version adaptations

CRM's node graphs are hidden in the tutorial (only Panel Text's first nodes are shown). Everything below is our
implementation, chosen to reproduce the observed input / output behaviour. Each item names the behaviour it
reproduces and the evidence for that behaviour.

## Area junction (MRS_AreaJunction, `tools/roads/mrs/areajunction.py`)

| # | decision | reproduces (evidence) |
|---|---|---|
| C1 | Footprints are faces tagged `mrs_tongue` (1 road, 2 roadside, 3 island) in any object of the Roads collection; the junction reads them through Collection Info (relative space) + Realize Instances depth 1 | "the junction converts the red part to road and the yellow part to roadside" (12:38-12:54, E25); extensions work by being in the Roads collection (19:06, E34) |
| C2 | Road surface = union of the road footprints, every reflex corner filleted with Inner Radius; roadside = union of all footprints, reflex corners filleted with Outer Radius, minus the road | rounded kerb corners at the junction (E23, E25); Inner Radius edits change the corner (20:44, strip_021); Outer Radius 0 gives the square back corners seen (E25) |
| C3 | Union by winding number, no boolean: each footprint island's outline turned counter-clockwise (signed area), all filled at once with Fill Curve's Non-Zero rule; the union's outline is that triangulation's boundary. (A first version used an exact Mesh Boolean of extruded prisms: touching footprints left T-junction seams that read as phantom outlines, a raised square in the middle of a crossing; caught by the comparison renders and a dense raster test) | overlapping tongues merge into one area (13:03 "slightly overlap") |
| C4 | Corner test: a probe 5 cm along the corner's bisector; outside the union = reflex (gets the fillet) | only the inside corners round (E25: the far ends of the tongues stay square) |
| C5 | Levels: each output vertex takes the height of the nearest footprint (Sample Nearest Surface), footprints sit `mrs_drop` under the surface they stand for | junction at the tongues' level (13:16-13:41: one global height); tongues no longer visible once converted (E23) |
| C6 | Range on: a footprint island takes part when any of its vertices is within Distance of the origin; Range off: inside the object's own mesh bounds; either way an island under the area's centre takes part | the range circle (E21-E31); scaling the cube in edit mode sets the area (17:00, E30); Range 1000 m converts every crossing (E31) |
| C7 | Islands (kind 3) are cut from the road and raised with the roadside | the roundabout: a central sidewalk disc ("sidewalk round", 23:52) |
| C8 | Range circle drawn only in the viewport (Is Viewport) and not when Export Ready | orange circle in the viewport (E21-E31), never in renders |
| C9 | Fill as triangles, faces turned up, UVs = world XY x UV Scale, `kind` / `ground_surface` attributes for the MRS exporter | Export Ready "UV mapped and ready to export" (7:47-7:55, narrated for the road) |
| C10a | Holes the road footprints enclose are road (tongues that do not quite meet leave no raised square); the junction area is solid. Raised areas inside a junction come only from Island footprints | E39: the roundabout's only raised centre is its island |
| C10b | The roadside never covers a road's own carriageway (MRS_Road faces of the carriageway kinds in the Roads collection): roadside = area minus every carriageway, from one constrained triangulation whose triangles are kept when their centre is inside the area | an extension's yellow band reaching past a tongue built a raised slab across the road end (found in the cul-de-sac comparison) |
| C10c | Faceless edges left by the fills (a road end lying on the outer outline) are deleted | black lines across every road end in the viewport, stray line primitives in an export (found live in Blender) |
| C10 | The roadside is one raised slab (top Roadside Material, walls Curb Material), Curb Height 0.15 m | yellow becomes roadside (E25); CRM's junction Road / RoadSide panels were never opened (D) |

## Road tongues (MRS_Road, frame "Tongues")

| # | decision | reproduces |
|---|---|---|
| C11 | Tongue Start / Tongue End take the first / last metres of the drawn curve (after any junction trim): the road surfaces stop there, the piece becomes footprints with the road's own widths (carriageway red, kerb + sidewalk yellow) | red / yellow ends on a freshly drawn road (E10, 6:09); Tongue Size 10 m / 11.5 m (strip_010, strip_024) |
| C12 | Tongues hidden when the road realizes its instances (MRS's Export Ready) | B: Export Ready is the "done editing" state (7:28) |
| C13 | Tongue height = the drawn curve's points (not the terrain-conformed rail) | "the last three points must be aligned" for a sloped approach (14:45-15:14, E28) |

## Extensions

| # | decision | reproduces |
|---|---|---|
| C14 | MRS_ExtensionMesh: the mesh's faces are road; a band of Roadside Size centred on its outline (mitred at corners: profile scaled by 1 / cos(half the turn)) is roadside; Island option | square / round extensions with a yellow border (E33-E40) |
| C15 | MRS_ExtensionCurve: the curve swept to Road Size (road) inside Road Size + 2 x Roadside Size (roadside); Resolution = spline resolution | "10. CRM Extension" (strip_031) |
| C16 | Our Roadside Size default 2 m (CRM's mesh extension showed 6.000 on an object scaled in object mode, so its unit is unclear: D) | strip_018 |

## Custom sign (MRS_CustomSign, MRS_PanelText)

| # | decision | reproduces |
|---|---|---|
| C17 | Panel shapes Quad / Octagon / Circle / Triangle / Diamond, each 1 unit wide before Scale X / Y; Octagon flat-topped | Quad and Octagon seen (strip_032, strip_036); the other entries are our additions (the menu's full list is D) |
| C18 | Colour menus: White, Black, Red, Blue, Green, Yellow, Orange, Brown, Grey; "Auto" = white on dark panels, black on light | Auto, Blue, Red seen; white text on blue / red (E44, E47) |
| C19 | Outline = band between the panel shape inset by Position and by Position + Width (inset by scaling about the centre) | stop sign border at Position 0.021 / Width 0.026 (E47) |
| C20 | Back post: H Struts (horizontal pipes behind the panel, Post Width long), Poles Count poles to the ground; Pipe / U Channel / Square cross-sections; Panel Height 2.2 m (our input: CRM's sign sat on a separate post, D) | strip_032 31:06 |
| C21 | A text slot with empty text, an image without material, a line of length 0 draw nothing | empty third text slot (strip_033); Images empty by default (strip_035) |
| C22 | Panel Text takes a Material (CRM passes Color Index + Menu); one Menu Switch per menu socket, further uses through Index Switch | Panel Text's inputs (G_32m44); Blender requires one Menu Switch per menu socket |

## Marking lines (MRS_MarkingLines, MRS_PaintLine)

| # | decision | reproduces |
|---|---|---|
| C23 | Patterns None / Solid / Dashed / Dotted; Dash / Gap inputs (3 m / 3 m); Line 2 drawn beside Line 1 (double line, 0.12 m apart) | Line 1 / Line 2 pattern menus (strip_030) |
| C24 | Lane lines: Duplicate per side, evenly between the centre and the edges | Lane Marking Duplicate (strip_030) |
| C25 | Dashes by deleting faces of the line swept over a 0.1 m resampling | (implementation) |

## Version adaptations

| tutorial behaviour / node | installed-version equivalent | adaptation | expected effect |
|---|---|---|---|
| Blender 5.0.0 (status bar of every frame) | Blender 5.2.3 LTS | none needed for the nodes used | same |
| Asset library "Pack" import (1:52) | 5.2 keeps the Pack import method | we ship no asset library: the groups are built from Python (`mrs.build_all()` / the add-on's Build button) | no packed-data "make local" step |
| Fill Curve mode N-gons (Panel Text) | Fill Curve has Mode and Fill Rule sockets in 5.2 | Panel Text keeps N-gons; the junction uses Triangles + Even-Odd | identical text; planar junction faces at any level |
| Mesh Boolean (CRM's union: hidden) | 5.2 Fill Curve with a Fill Rule input (Non-Zero / Even-Odd) | union and differences by winding rules on one triangulation, no boolean | exact, seam-free, fast |
| Extrude Mesh Offset typed as a constant | the socket has an implicit Normal field | offsets linked through Combine XYZ | (a constant would be ignored) |
| Group menu socket on several Menu Switch nodes | 5.2 allows one Menu Switch per menu socket | one Menu Switch to an index, Index Switch elsewhere | menus keep their entries |
| String to Curves font (picked in the node, 33:09) | same in 5.2 (no font socket type) | font picked on MRS_PanelText's String to Curves | same |
