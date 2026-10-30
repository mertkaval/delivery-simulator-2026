# Unreadable, hidden or unresolved (class D)

What the tutorial does not show, or shows too briefly to read. Nothing here was filled in from guesses: where the
reconstruction needs a value, the choice is listed in [DECISIONS.md](DECISIONS.md).

## Hidden graphs
- Every CRM node graph except the first nodes of Panel Text: 01. CRM Road, 02. CRM Junctions, the extensions,
  Marking Lines, Tunnel, Cable-Stayed, Terrain. Only modifier panels are shown. Panel Text past Fill Curve (material,
  placement, the "1 Named Attribute" label above the group node) is off screen.
- How the junction merges tongues (boolean, volume, raster...), how it rounds corners, and where its output height comes from.
- How a converted tongue disappears (covered, removed or hidden by the junction): the frames show only the result.

## Panels never opened or scrolled past
- 01. CRM Road: Manage; most of RoadSide below Random Collection; Road Median below Green Belt; Extend / End Point.
- 02. CRM Junctions: Road, RoadSide, Manage.
- 13. CRM Custom Sign: Manage; Text Line 2 / 3 contents; Images 2 / 3 past Material.
- 16. CRM Terrain: Manage.
- 03. CRM Marking Lines: Manage.

## Menus whose full item lists are not shown
- Asphalt Type (New seen; "CRM" and "Wet" narrated at 6:39-6:54).
- RoadSide Type (Concrete, Unpaved* seen), Curb (Concrete), Outer Curb (None).
- Custom Sign Shape (Quad, Octagon), Color (Auto, Blue, Red), Back Post Shape (Pipe; U Channel narrated).
- Marking Line patterns (solid, dashed and None shown as drawn previews, names not readable).
- Parking Order (Bicycle-Parking), Piers Type (Rectangular), Crosswalk Type (Zebra), End Marking (Stop), Light Color (Green).

## Values
- Units of the extension mesh's "Roadside size 6.000" (no unit shown, the object was scaled in object mode).
- The junction's Export Ready effect (narrated for the road only).
- Custom sign post: the sign at 31:06 stands on a post while Poles Count shows 0; whether the post is part of the
  group or a separate object (`Custom Sign St...` at 34:57) is unclear.
- Catalogs after 10. Markings (scrolled out of view).
- The tunnel's entrance "Sign 1/2/3" menu items (Open/Closed, Closed/Open seen).

## Interaction
- Whether the junction updates live or after a depsgraph update: edits between cuts appear updated, which does not
  prove live updating. (The reconstruction is live: see VALIDATION.md.)
- Alt + click on RoadSide sets it on all selected roads (12:16, narrated): this is Blender's standard multi-object
  property edit, not a CRM feature.
