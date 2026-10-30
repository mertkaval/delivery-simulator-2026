# Walkthrough: the City Road Maker 2.1 tutorial, step by step, and its Mert Road Studio reconstruction

Each step: what the video shows (frame, evidence class), then how the reconstruction does it. Times are m:ss into the
video. Full operation list: [OPERATION_LOG.md](OPERATION_LOG.md); interfaces: [CRM_INTERFACES.md](CRM_INTERFACES.md).

## Timestamp map (this video's chapters)

| chapter | starts | what it demonstrates |
|---|---|---|
| Intro | 0:00 | CRM 2.1 is now an asset library, not just a node setup |
| Installing Asset Library | 0:25 | asset library vs appending the collections; Blender 4.3/4.5 vs 5 import (Pack) |
| Road Setup | 4:57 | the road group's panels: Curve, Road, RoadSide, Road Median, Start / End Point, Extend |
| Junction Setup | 10:51 | tongues, the junction object, Roads collection, range, levels, slopes |
| Extension Feature | 18:31 | mesh / curve extensions as extra tongues |
| Extension / Bus Stop | 19:27 | a bus bay from a square extension |
| Extension / Rounded End-road | 21:25 | a cul-de-sac from a round extension |
| Extension / Roundabout | 22:52 | a roundabout from a round extension + a central island |
| Extension / Parking Space | 26:31 | a car park + bay lines (Marking Lines + Array) |
| Custom Sign | 30:35 | the parametric sign: panel, post, texts, images, lines; the font inside Panel Text |
| Tunnel / Bridge | 35:33 | structures follow a duplicate of the road's curve |
| Mountain Road | 36:35 | terrain pulled to the road, a bridge section with piers |

## 1. The road and its tongues

![road with tongues, E10](evidence/crops/E10_6m09_view.png)

*6:09 (A): a road drawn in edit mode; both ends are red (road) with yellow sides (roadside): the tongues.*

The Start / End Point panels hold the tongue length (Tongue Size 10 m, 11.5 m on another road) next to the crosswalk,
end line, end marking and traffic-light options ([panel, 9:56-10:22](evidence/panels/strip_010.png)).

**Reconstruction:** MRS_Road has **Tongue Start** and **Tongue End** (Junction panel). The first / last metres of the
drawn curve are left as footprints with the road's own cross-section: the carriageway (lanes, parking, bike lanes) in
red, kerb + sidewalk in yellow, 2-3 cm under the surface. The road's surfaces, markings and roadside assets stop
where the tongue starts. Realize Instances (export) leaves the tongues out.

## 2. The junction object

![four tongues, E21](evidence/crops/E21_11m06_view.png)

*11:06 (A): four roads meeting; their tongues overlap in a red cross. A junction object is dropped in: nothing
happens until its **Roads** collection is set (11:22, [panel](evidence/crops/E22_11m22_panel.png)).*

![converted, E23](evidence/crops/E23_11m57_view.png)

*11:57 (A): with Roads set, everything in the range circle (Range 40 m) becomes one junction mesh: red -> road,
yellow -> roadside (E25, 12:27).*

**Reconstruction:** MRS_AreaJunction (Junctions panel: Roads, Show, Range + Distance, Export Ready, Inner Radius,
Outer Radius, Resolution; Road; RoadSide):
1. the Roads collection's faces tagged as footprints, the islands that reach the range (or the object's own mesh
   bounds when Range is off, or that lie under its centre);
2. road = union of the road footprints (each extruded into a prism, exact boolean union, top outline), every
   **reflex** corner filleted with Inner Radius (a probe on the corner's bisector tells reflex from convex);
3. roadside = union of all footprints with its reflex corners filleted by Outer Radius, minus the road, raised by
   Curb Height (walls Curb Material, top Roadside Material);
4. every vertex at the nearest footprint's level; the range circle only in the viewport.

Live: moving a road, changing a tongue or a radius rebuilds the junction on the next evaluation (no operator).

## 3. Rules the tutorial gives, and how the reconstruction treats them

| tutorial rule (evidence) | reconstruction |
|---|---|
| tongues should overlap slightly; too long tongues merge badly (13:03, [E26](evidence/crops/E26_13m03_view.png)) | overlaps are unioned exactly; a long tongue only enlarges the area |
| meeting tongues share one global height (13:22) | each vertex takes its nearest footprint's level |
| on a slope keep the last three points level (14:45, [E28](evidence/crops/E28_15m54_view.png)) | same: the tongue follows the drawn points |
| do not rotate / scale the junction in object mode; scale its cube in edit mode (16:23-17:02, [E30](evidence/crops/E30_17m00_view.png)) | Range off uses the mesh bounds in object space; the transform is honoured through Collection Info (relative) |
| Range 1000 m converts every crossing ([E31](evidence/crops/E31_17m45_view.png)) | same |
| two junctions over the same tongues double the mesh: black in Cycles ([E32](evidence/frames/E32_18m21_after.jpg)) | same caution (the MRS validator's overlap check finds it) |

## 4. Extensions

![extensions, E33](evidence/crops/E33_18m42_assets.png)

*18:42 (A): three extensions, two mesh-based (square, round), one curve-based; red / yellow like tongues.*

| example | video | reconstruction |
|---|---|---|
| bus bay | [E35 20:48](evidence/crops/E35_20m48_view.png), [E36 21:33](evidence/crops/E36_21m33_view.png) | square MRS_ExtensionMesh at the kerb, in a junction with the two road halves; shelter + BUS / STOP markings |
| cul-de-sac | [E37 22:48](evidence/crops/E37_22m48_view.png) | round extension at a road end |
| roundabout | [E38 24:30](evidence/crops/E38_24m30_view.png), [E39 26:02](evidence/crops/E39_26m02_view.png) | round extension (ring) + an **Island** extension (cut from the road, raised) |
| car park | [E40 27:51](evidence/crops/E40_27m51_view.png), [E41 28:45](evidence/crops/E41_28m45_view.png) | big square + entrance square; bay lines = MRS_MarkingLines + Array |
| curve extension junction | [E42 30:13](evidence/crops/E42_30m13_view.png) | MRS_ExtensionCurve (Road Size, Roadside Size) |

## 5. Custom sign

![custom sign, E44](evidence/frames/E44_31m45_after.jpg)

*31:45 (A): a blue Quad panel, "CRM 2.1" over a white bar over "Custom Sign"; Text Line 1 holds three texts
(text, colour, size, X, Y each).*

![the only graph shown, 32:52](evidence/graph/G_32m52_nodes.png)

*32:52 (A): inside the nested **Panel Text** group: String to Curves (Bfont Regular, Center / Middle) -> Set Spline
Resolution (6) -> Fill Curve (N-gons). The font is chosen here, not on the modifier.*

**Reconstruction:** MRS_CustomSign with the same panels (Panel, Back Post, Text Line 1-3, Images, Lines Shape) and a
nested MRS_PanelText built exactly as shown (String to Curves -> Set Spline Resolution 6 -> Fill Curve N-gons) plus
material and placement. Presets CRM 2.1 and Stop reproduce the two signs built in the video; Save Sign Preset stores
any other.

## 6. Tunnel, bridge, mountain road

Shown at [E49 36:04](evidence/crops/E49_36m04_view.png), [E50 36:21](evidence/crops/E50_36m21_view.png),
[E52 37:47](evidence/crops/E52_37m47_view.png), [E53 39:13](evidence/crops/E53_39m13_view.png),
[E54 41:03](evidence/crops/E54_41m03_view.png). MRS already does this inside the road itself (Tunnel Start / End,
Mode Elevated with piers and barriers, Conform + MRS_TerrainConform with cut / fill batters): no separate structure
curve to keep in step with the road. Mapping: Pull Terrain = Conform; CRM Terrain's Flatting Size / Smoothness =
MRS_TerrainConform's Edge Band / Reach and batter slopes.

## 7. Side by side

See [VALIDATION.md](VALIDATION.md) for the comparison images (the video's viewport above the reconstruction's render
of the same example) and the measured checks.
