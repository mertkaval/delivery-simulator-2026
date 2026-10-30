# City Road Maker 2.1: what the tutorial shows of its node groups

Read from the video's Properties editor (modifier panels) and the one node-graph excursion (32:20-33:16). Every row
cites a settled panel state (`evidence/panels/strip_NNN.png`, five 360 x 690 crops of the Properties editor per strip,
times over each; index in `evidence/panels/index.json`) or a frame.

Evidence class: **A** read in a frame, **B** narration only, **C** inferred, **D** unresolved. CRM's internal graphs
are hidden apart from Panel Text, so "internal destination" is **D** for every CRM socket: the reconstruction's own
destinations are in [NODES_RECONSTRUCTION.md](NODES_RECONSTRUCTION.md).

## Modifier groups seen (A)

| group (as named in the modifier) | object it sits on | first seen | evidence |
|---|---|---|---|
| `01. CRM Road` | Simple road *GN (curve) | 5:08 | E08 crop, strip_006..011 |
| `02. CRM Junctions` | Custum junction *GN (mesh cube) | 11:22 | E22 crop, strip_017, strip_018, strip_021, strip_024 |
| `03. CRM Marking Lines` | 1. Marking Lines Path (curve) + Array modifier | 28:02 | strip_030 |
| `10. CRM Extension` | 1. Extension Path (curve) | 29:41 | strip_031 |
| `12. CRM_Tunnel` | Tunnel Path (curve) | 35:42 | strip_038 |
| `13. CRM Custom Sign` | Custom Sign *GN (mesh) | 31:33 | strip_032..037 |
| `15. CRM Cable-Stayed ...` | Cable-Stayed B... (curve) | 36:10 | strip_038 |
| `16. CRM Terrain` | Terrain *GN (mesh) | 36:42 | strip_039..041 |
| `19. CRM Extension Mesh` | Extension Square (mesh) | 19:04 | strip_018 |
| `Panel Text` (nested in 13., 9 users) | - | 32:44 | graph/G_32m44_* |

Asset catalogs (A, E02 / E32 frames): 01. Roads, 02. Junctions, 03. Extensions, 04. Signs, 05. Tunnel, 06. Bridge,
07. Retaining Wall, 08. Greenery, 09. Terrain, 10. Markings; further catalogs scroll out of view (D). The asset view
also lists Traffic Light 01..16 (round and arrow heads, E32 frame).

## 01. CRM Road (A unless marked)

Panels in order: Curve, Road, RoadSide, Road Median, Start Point, End Point, Extend, Manage (E08 panel crop, 5:08; strip_007 8:31).

| panel / sub-section | control | type | default seen | evidence |
|---|---|---|---|---|
| Curve | Resolution | int | 24 | strip_006 6:15 |
| Curve | Pull Terrain | bool | off | strip_006 6:15; on at 37:58 (strip_040) |
| Curve | Export Ready | bool | off | strip_006 6:15 |
| Road / Road | Size | float (m) | 8 m | strip_007 8:17 |
| Road / Road | Left Shoulder, Right Shoulder | float (m) | 0 m | strip_007 |
| Road / Road | Double Lanes | bool | off (on at 8:38) | strip_008 |
| Road / Road | Middle Shoulder | float (m) | 0 m | strip_007 |
| Road / Road | Asphalt Type | menu | New | strip_006 6:39; other items B ("CRM", "Wet"), D |
| Road / Road | Pick Material, Material, Scale It | bool, material, float | off, empty, 1.000 | strip_006 6:39 |
| Road / Markings Lines | Edge Markings, Line 1, Line 2, Width, Lines Color | bool, menu, menu, float, menu | on, solid, solid, 0.12 m, White | strip_006 6:39 |
| Road / Markings Lines | Center Markings, Line 1, Line 2, Width, X, Lines Color | ... | on, solid, solid, 0.12 m, 0.000, Yellow | strip_006 6:39 |
| Road / Markings Lines | Lane Markings, Duplicate, Line 1, Line 2, Width, Lines Color | ... | on, 1, dashed, None, 0.12 m, White | strip_008 8:47 |
| Road / Parking Lane | Order | menu | Bicycle-Parking | strip_008 8:52 |
| Road / Parking Lane | Left Parking, Right Parking | bool + float | off, 2 m | strip_008 8:52; strip_041 |
| Road / Parking Lane | Line Type, Divider Line, Hatched Area | menu, float, float | dash pattern, 5.5 m, 0 m | strip_041 40:39 |
| Road / Bridge | Bridge, Bridge Barrier, Piers | bool | off / on in the mountain road | strip_041 40:39-41:03 |
| Road / Bridge | Piers Type, Piers Spacing, Pier Height, Piers Diameter, Piers Count | menu, float, float, float, int | Rectangular, 20 m, 10 m (13.5 / 34.9 edited), 2 m, 1 | strip_041 |
| Road / Bus/Taxi Lane | Color, Line Type, Left Lane, ONLY text | menu, menu, bool, bool | Red, solid, -, on | strip_041, strip_006 6:46 |
| Road / Bicycle Lane | Color, Line Type, Left, Right, Path Type | menu, menu, bool, bool, int | Green, dashed, off, off, 1 | strip_006 6:46 |
| Road / Patches | Density, Size Min, Size Max, Seed | float, float, float, int | 0.000, 1.000, 2.500, 5 | strip_006 6:46 |
| Road / Wet Asphalt | Wet*, Puddles, Wetness | bool, float, float | off, 0.400, 0.200 | strip_006 6:46 |
| Road / Manholes | Manholes, Type, Spacing, Random Y | bool, int, float, float | off, 2, 15 m, 0.000 | strip_006 6:46 |
| RoadSide | RoadSide, Type | bool, menu | on, Concrete (Unpaved* at 6:53) | strip_019 19:31; strip_006 6:53 |
| RoadSide | Pick Material, Material, Scale it, Size | bool, material, float, float | off, -, 1.000, 2 m | strip_019 |
| RoadSide | Curb, Outer Curb | menu | Concrete, None | strip_019 |
| RoadSide | Manholes, Spacing, Position, Random Y | bool, float, float, float | off, 20 m, 0 m, 0.000 | strip_019 |
| RoadSide | Wet, Puddles, Wetness | bool, float, float | off, 0.400, 0.200 | strip_006 6:53 |
| RoadSide / My Props | Collection, Left, Right, Spacing, Slope Z, X, Y, Z, Seed | collection, bool x2, float, bool, float x3, int | -, off, off, 10 m, off, 0.000, 2 m, 0 m, 5 | strip_009 9:08-9:41 |
| RoadSide / Random Collection | Collection, Area Size, Y, Z, Random Rotation, Random Size, Distance Min, Density Max, Density Factor, Seed | collection, float x3, bool x2, float x3, int | -, 0.5 m, 0 m, 0 m, on, off, 0 m, 1.000, 0.100, 0 | strip_009 / strip_010 |
| Road Median | Road Median, Open Start, Open End, Type, Pick Material, Material, Scale It, Size, Curb, Manholes, Spacing, Random Y, Green Belt, End Edge... | bool ... | off, off, off, None, off, -, 1.000, 1.5 m, Concrete, off, 20 m, 0.000, off | strip_007 8:33 |
| Start Point | Tongue Size | float (m) | 10 m | strip_010 9:56 |
| Start Point / Crosswalk | Crosswalk, Type, Size X, Offset Y | bool, menu, float, float | off, Zebra, 3 m, 0 m | strip_010 |
| Start Point / Markings | End Line + style, End Marking + kind, Scale, X, Y, Extend Y, Extend -Y | bool + menu, bool + menu, float x5 | off Solid, off Stop, 1.000, 2 m, 0 m, 0 m, 0 m | strip_010 10:07-10:15 |
| Start Point / Traffic Lights | Traffic Lights, Type, Light Color; Arrows: Arrow1 ... | bool, int, menu; bool ... | off, 1, Green; on | strip_011 10:22 |
| End Point | as Start Point; Tongue Size | float | 11.5 m on this sample road | strip_024 23:27 |
| Extend / Start Point (End Point alike) | Offset; Edge Marking Left, Edge Marking Right, Center Marking, Lane Marking, Median Props, Roadside Props, Parking Lane, Bus/Bicycle Lanes, Start Point, Bridge Piers | float; bools | 0 m; all off | strip_011 10:28 |
| Manage | - | - | never opened | D |

Narrated behaviour (B, 5:12): over 280 settings controlling more than 30 road features. Export Ready realizes the
instances into one UV-mapped mesh; enable it only when editing is done (7:28). The asterisked options (Asphalt CRM /
Wet, RoadSide Unpaved) are procedural shaders that do not export (6:54-7:14).

## 02. CRM Junctions (A)

| panel | control | type | default seen | visible effect | evidence |
|---|---|---|---|---|---|
| Junctions | Roads | collection | empty (nothing converts until set) | tongues of the collection's objects in range become junction meshes | strip_017 16:18, E21/E23 |
| Junctions | Show | bool | on | off: the red / yellow tongues show again | strip_017, strip_021 21:50, E25 |
| Junctions | Range | bool + float (m) | on, 40 m (60 m, 253 m, 1000 m edited) | orange range circle in the viewport; off: the object's mesh is the area (17:00, E30) | strip_017, E31 |
| Junctions | Export Ready | bool | off | B: realizes the result | strip_017 |
| Junctions | Inner Radius | float (m) | 2 m (1.7, 0.38, 0.31 edited) | rounding of the road corners | strip_021 20:44 |
| Junctions | Outer Radius | float (m) | 0 m | D (never changed on screen) | strip_017 |
| Junctions | Resolution | int | 10 | D | strip_017 |
| Road, RoadSide, Manage | - | panels | never opened | D | strip_017 |
| Info | "Input geometry has unsupported type: ..." | message | shown while a curve object without the road group sat in Roads (20:44-21:38) | - | strip_021 |

Behaviour (A): red tongue parts become road, yellow parts roadside (12:38-12:54); tongues should overlap slightly
(13:03); all meeting tongues must be at one global height (13:22; the sloped road keeps its last three points level,
14:45); do not rotate / scale the junction in object mode (16:23); scaling its cube in edit mode sets the area
(16:56-17:02); one junction with a large range converts every crossing in it (17:12-17:49); overlapping junctions
double the mesh, which renders black in Cycles (18:06-18:21, E32).

## Extensions (A)

| group | control | type | default seen | evidence |
|---|---|---|---|---|
| 19. CRM Extension Mesh | Roadside size | float | 6.000 | strip_018 19:04 |
| 10. CRM Extension | Resolution | int | 2 | strip_031 29:41 |
| 10. CRM Extension | Road Size | float (m) | 5 m | strip_031 |
| 10. CRM Extension | Roadside Size | float (m) | 2 m | strip_031 |

Three extensions in the catalog: two mesh-based (square, round), one curve-based; drawn red / yellow like tongues
(18:39-18:53). They must be in the Roads collection and at the roads' level (20:04-20:18).

## 03. CRM Marking Lines (A, strip_030 28:02-28:13)

| control | type | default seen |
|---|---|---|
| Resolution | int | 12 |
| Road Size | float | 8 m |
| Edge Marking; Line 1; Line 2; Width; Lines Color | bool; menu; menu; float; menu | on; solid; solid; 0.1 m; White |
| Center Marking; Line 1; Line 2; Width; X; Line Color | bool; menu x2; float x2; menu | on; solid; solid (None edited); 0.1 m; 0.000; Yellow |
| Lane Marking; Duplicate; Line 1; Line 2; Width; X; Lines Color | bool; int; menu x2; float x2; menu | on (off edited); 1; dashed; dashed; 0.1 m; 0.000; White |
| Double Lanes; Middle Shoulder | bool; float | on; 0 m |

Used with an Array modifier (Shape Line, Count 3, Relative Offset X 1.000, Realize Instances on: strip_030 28:39).

## 13. CRM Custom Sign (A)

| panel | control | type | defaults seen | evidence |
|---|---|---|---|---|
| Panel | Shape | menu | Quad; Octagon for the stop sign | strip_032 31:00, strip_036 34:57 |
| Panel | Scale X, Scale Y | float (m) | 0.6 m, 0.6 m | strip_032 |
| Panel | Color | menu | Blue; Red | strip_032, strip_036 |
| Panel | Rotation | angle | 0 deg | strip_032 |
| Panel | Bevel Radius, Bevel Res | float, int | 0.044 m, 4 (stop: 0 m) | strip_032 |
| Panel | Outline; Position; Width; Color | bool; float; float; menu | on; 0.000 (stop 0.021); 0.030 (stop 0.026); Auto | strip_032, strip_036 |
| Back Post | Shape; Width; H Struts Count; Poles Count; Pole Height | menu; float; int; int; float | Pipe (U Channel narrated 31:10); 0.372 m; 2; 0; 0 m (disabled while Poles Count is 0) | strip_032 31:06 |
| Text Line 1 / 2 / 3 | three texts each: Text, Color, Size, X, Y | string, menu, float, float, float | "CRM 2.1", Auto, 0.097, 0 m, 0.155 m; "Custom Sign", Auto, 0.100, 0 m, -0.163 m; "", Auto, 0.400, 1 m, 0.56 m | strip_033 31:36 |
| Images | three: Material, Size, X, Y | material, float x3 | empty, 0.500, 0 m, 0 m | strip_035 33:22 |
| Lines Shap | Line 1..3: Color, Length, Width, Rotation, X, Y | menu, float x5 | Auto, 0.45 m, 0.054 m, 0 deg, 0 m, 0 m (Line 2: length 0 m, width 0.03 m) | strip_037 35:11-35:17 |
| Manage | - | - | never opened | D |

The font is not a group input: it is chosen on the String to Curves node inside Panel Text (31:56-33:16, B + A).

### Panel Text: the one graph shown (32:36-33:16)

Nodes (A unless marked):

| node | type | settings read | evidence |
|---|---|---|---|
| Group Input | NodeGroupInput | outputs Text, Color, Size, X, Y (of the Custom Sign group, one text slot) | G_32m44 |
| Panel Text (group node, 9 users) | GeometryNodeGroup | inputs Text, Size, X, Y, Color Index, Menu; output Geometry; label "1 Named Attribute" above it (D: a frame or node label) | G_32m44 |
| String to Curves | GeometryNodeStringToCurves | font Bfont Regular; Overflow; Align X Center; Align Y Middle; Pivot Point Bottom Left | G_32m52, G_33m10 |
| Set Spline Resolution | GeometryNodeSetSplineResolution | Selection unlinked; Resolution 6 | G_32m52 |
| Fill Curve | GeometryNodeFillCurve | Group ID unlinked; mode N-gons | G_32m52 |
| (rest of the subgraph) | - | out of view | D |

Connections:

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| Group Input (Custom Sign) | Text | Panel Text | Text | 32:44 | A |
| Group Input (Custom Sign) | Size | Panel Text | Size | 32:44 | A |
| Group Input (Custom Sign) | X | Panel Text | X | 32:44 | A |
| Group Input (Custom Sign) | Y | Panel Text | Y | 32:44 | A |
| Group Input (Custom Sign) | Color | Panel Text | Menu | 32:44 | B (the wire crosses to the Menu socket; read at 1080p) |
| (off-screen) | - | Panel Text | Color Index | 32:44 | D |
| Panel Text | Geometry | (off-screen join) | - | 32:44 | D |
| Group Input (Panel Text) | Text | String to Curves | String | 32:52 | A |
| Group Input (Panel Text) | Size | String to Curves | Size | 32:52 | A |
| String to Curves | Curve Instances | Set Spline Resolution | Curve | 32:52 | A |
| Set Spline Resolution | Curve | Fill Curve | Curve | 32:52 | A |

## 16. CRM Terrain (A, strip_039 / strip_040)

| control | type | default seen | evidence |
|---|---|---|---|
| Flatting Size | float (m) | 25 m (32.5 m edited) | strip_039 36:42, strip_040 39:13 |
| Smoothness | int | 2 (3 edited) | strip_039, strip_040 |
| Roads (four slots) | collection | empty; Roads set at 38:00 | strip_040 |

Only roads with Pull Terrain on pull the terrain (37:39-37:54, A + B).

## 12. CRM_Tunnel and 15. CRM Cable-Stayed (A, strip_038)

Tunnel: Resolution 2, Width 10 m, Lights 0.300, Entrances: Entrance Wall on, Sign 1 Open/Closed X -0.16 m, Sign 2
Open/Closed X 2.25 m, Sign 3 Closed/Open X -2.63 m. Cable-stayed bridge: Pylons Count 3, Legs Spacing 17 m, Legs Height
22 m, Cables Length 80 m, Info "Based on Curve". Both come without a road: duplicate the curve and give the copy the
road group so the road runs exactly through (35:48-36:23).
