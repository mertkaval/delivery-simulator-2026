# UI / UX: the tutorial's workflow and the reconstruction's

## Where the controls live (A)

CRM 2.1 has no custom panels or operators in the tutorial: every control is a **geometry nodes modifier input** in the
Properties editor (Modifier tab), grouped in collapsible panels (see [CRM_INTERFACES.md](CRM_INTERFACES.md)). Objects
come from the **Asset Browser** (catalogs 01. Roads ... 10. Markings, E02) by drag and drop, or by appending the CRM
collections (File > Append, E06). Editing a road's shape is plain curve edit mode (E10); a junction's area is its cube
in edit mode (E30).

The reconstruction keeps every control on the modifiers (MRS_Road, MRS_AreaJunction, MRS_ExtensionMesh /
MRS_ExtensionCurve, MRS_CustomSign, MRS_MarkingLines) and adds an add-on panel for creation
(`addon/mrs_area_workflow`, 3D View > Sidebar > MRS > Area Junctions):

| control | what it does |
|---|---|
| Build Node Groups | builds MRS_AreaJunction, the extensions, MRS_CustomSign, MRS_MarkingLines (MRS_Road comes from the MRS library) |
| Set Tongues (Start, End) | Tongue Start / Tongue End on every selected MRS road |
| Add Area Junction (Range) | a junction at the 3D cursor; Roads / Junctions collections created when missing; selected roads and extensions move into Roads |
| Add Extension: Square / Round / Curve / Island | an extension at the 3D cursor in Roads |
| Add Custom Sign (preset menu) | CRM 2.1, Stop, and any saved preset |
| Save Sign Preset | the active sign's inputs, by name, into `presets/signs.json` (persistent across sessions) |
| Add Marking Lines | a straight 10 m marking-lines curve at the cursor (add an Array modifier for bays, as in E41) |

## Conditional states (A)
- A value under a checkbox greys out while the checkbox is off (Pick Material -> Material, Manholes -> Spacing,
  Poles Count 0 -> Pole Height, Crosswalk off -> Type / Size X; strip_006, strip_032).
- Junction with an empty Roads collection: nothing converts, no message (11:09).
- A curve object without the road group in Roads: junction Info "Input geometry has unsupported type: ..." (strip_021).
  The reconstruction ignores non-mesh geometry silently (Separate Components -> Mesh).

## User journeys

Tutorial (A unless marked) / reconstruction:

1. **Create a road**: drag "Simple road" from the asset browser, Make Local (packed import), edit mode: extrude /
   scale points (E08-E10). / Add a curve, give it MRS_Road (`roads.make_road`), or the MRS panel's road tools.
2. **Edit width / style**: Road > Size, shoulders, Double Lanes, Asphalt Type; RoadSide Type, Size (E12-E17). /
   MRS_Road Lane Width, lanes, Median, Asphalt Condition, Sidewalk Surface, Curb Width...
3. **Make a junction**: four roads ending at a crossing, drag a junction, make Roads / Junctions collections, put the
   roads in Roads, set the junction's Roads (E21-E23); RoadSide on all roads with Alt + click (E24). / Select the roads,
   Set Tongues, Add Area Junction (collections, Roads assignment and the junction in one step).
4. **Slope**: make the road single-user, keep its last three points level at the junction's height (E28). / Same rule:
   the tongue follows the drawn points; MRS_Road's rail can still conform to a terrain before the tongue.
5. **Bigger area / many crossings**: increase Range, or Range off and scale the cube in edit mode (E30, E31). / Same.
6. **Bus bay / cul-de-sac / roundabout / car park**: drag an extension into the junction area, at the roads' level, in
   Roads; scale it in edit mode (E35-E40). / Add Extension (Square, Round, Island for the roundabout centre, Curve).
7. **Bay lines**: Marking Lines curve + Array modifier (E41). / Add Marking Lines + Array.
8. **Sign**: drag Custom Sign, edit Panel / Back Post / Text / Images / Lines (E43-E48). / Add Custom Sign preset,
   edit the same panels; Save Sign Preset to reuse it.
9. **Terrain**: drag the terrain, Pull Terrain on the road, the terrain's Roads collection, Flatting Size /
   Smoothness (E51-E53). / MRS_Road Conform + MRS_TerrainConform (existing MRS tool: `mrs.terrain.conform_terrain`).
10. **Bridge / tunnel**: duplicate the structure's curve and add the road group to the copy (E49, E50); bridge piers
    on the road's Bridge panel (E54). / MRS_Road Mode Elevated (piers, barriers) and Tunnel Start / End.
11. **Export**: Export Ready on roads and junctions, File > External Data > Unpack Resources (E15). / MRS_Road
    Realize Instances (also drops the tongues), the junction's Export Ready (no guides); `mrs.export`.
12. **Save / reopen**: the modifiers keep every value in the .blend; the add-on is needed only for its buttons. The
    groups are built from Python, so a file made on another machine still opens with its node groups embedded.

## Live versus rebuild
- **Live (reconstruction, measured):** the junction, extensions, signs and marking lines are pure geometry nodes:
  moving a road or an extension, changing a tongue, a radius, a sign text updates on the next depsgraph evaluation
  with no operator (area_junction_test: "follows a moved tongue"; road_tongue_test: "longer tongues: the junction
  grows"; custom_sign_test: "a text edit changes the sign at once").
- **Rebuild:** only after changing the node-group code (Build Node Groups / `mrs.build_all()`).
- **Tutorial:** edits appear updated across cuts; live updating is likely (all geometry nodes) but not proven (D).
