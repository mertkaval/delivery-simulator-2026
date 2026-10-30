# Operation log

Every meaningful operation of the tutorial, in order. Times are the frame that shows the result (m:ss). Class: A directly observed in the frames, B supported by the narration only, C inferred, D unresolved. `before` is the frame 3 s earlier. Crops are cut from the full frame at the bounds given (x, y, w, h on 1920 x 1080).

## Installing Asset Library

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E01 | 0:44 | Edit > Preferences > File Paths: add the CRM 2.1.1 folder as an asset library | asset library entry added (method 1) | B transcript | [after](evidence/frames/E01_0m44_after.jpg) [before](evidence/frames/E01_0m44_before.jpg) |
| E02 | 1:02 | asset browser on library CRM 2.1.1, drag 'Simple road *GN' in | catalogs 01. Roads ... 10. Markings; the road object appears | A observed | [after](evidence/frames/E02_1m02_after.jpg) [before](evidence/frames/E02_1m02_before.jpg) [assets](evidence/crops/E02_1m02_assets.png) `0,610,1525,370` |
| E03 | 1:24 | Blender 4.3 / 4.5: drag-and-drop a road | every drop brings object references again (import issue) | B transcript | [after](evidence/frames/E03_1m24_after.jpg) [before](evidence/frames/E03_1m24_before.jpg) |
| E04 | 1:52 | Blender 5: asset browser, Import Settings 'Pack' | no duplicated references | A observed | [after](evidence/frames/E04_1m52_after.jpg) [before](evidence/frames/E04_1m52_before.jpg) [assets](evidence/crops/E04_1m52_assets.png) `0,610,1525,370` |
| E05 | 2:59 | drag the 'simple intersection' sample (a collection of collections) | some collections come in packed: geometry node inputs not editable | B transcript | [after](evidence/frames/E05_2m59_after.jpg) [before](evidence/frames/E05_2m59_before.jpg) |
| E06 | 3:40 | File > Append > CRM 2.1.1.blend > Collection, select all, append (method 2, recommended) | CRM collections in the current file | A observed | [after](evidence/frames/E06_3m40_after.jpg) [before](evidence/frames/E06_3m40_before.jpg) |
| E07 | 4:47 | copy the two catalog files into the project directory | Current File asset view shows the categories | B transcript | [after](evidence/frames/E07_4m47_after.jpg) [before](evidence/frames/E07_4m47_before.jpg) |

## Road Setup

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E08 | 5:08 | select the road: modifier 'GeometryNodes' with node group '01. CRM Road' | panels Curve, Road, RoadSide, Road Median, Start Point, End Point, Extend, Manage | A observed | [after](evidence/frames/E08_5m08_after.jpg) [before](evidence/frames/E08_5m08_before.jpg) [panel](evidence/crops/E08_5m08_panel.png) `1558,310,360,690` |
| E09 | 5:47 | Tab into edit mode on a packed/linked road | error asking to make the data local; Object > Make Local fixes it | A observed | [after](evidence/frames/E09_5m47_after.jpg) [before](evidence/frames/E09_5m47_before.jpg) [view](evidence/crops/E09_5m47_view.png) `0,60,1525,545` |
| E10 | 6:09 | edit mode: scale / extrude the curve points (never scale in object mode) | the road follows the drawn curve (red tongues at both ends) | A observed | [after](evidence/frames/E10_6m09_after.jpg) [before](evidence/frames/E10_6m09_before.jpg) [view](evidence/crops/E10_6m09_view.png) `0,60,1525,545` |
| E11 | 6:15 | Curve panel | Resolution 24, Pull Terrain, Export Ready | A observed | [after](evidence/frames/E11_6m15_after.jpg) [before](evidence/frames/E11_6m15_before.jpg) [panel](evidence/crops/E11_6m15_panel.png) `1558,310,360,690` |
| E12 | 6:39 | Road panel: shoulders, Double Lanes, Asphalt Type, marking lines | Asphalt Type 'New'; Edge / Center / Lane Markings with Line 1 / Line 2 patterns, Width 0.12 m | A observed | [after](evidence/frames/E12_6m39_after.jpg) [before](evidence/frames/E12_6m39_before.jpg) [panel](evidence/crops/E12_6m39_panel.png) `1558,310,360,690` |
| E13 | 6:46 | Road panel: Bicycle Lane, Patches, Wet Asphalt, Manholes | Wet* puddles 0.4 wetness 0.2; Patches density / size min-max / seed | A observed | [after](evidence/frames/E13_6m46_after.jpg) [before](evidence/frames/E13_6m46_before.jpg) [panel](evidence/crops/E13_6m46_panel.png) `1558,310,360,690` |
| E14 | 6:53 | RoadSide panel: Type 'Unpaved*' | roadside type menu, curb, outer curb, manholes, wet | A observed | [after](evidence/frames/E14_6m53_after.jpg) [before](evidence/frames/E14_6m53_before.jpg) [panel](evidence/crops/E14_6m53_panel.png) `1558,310,360,690` |
| E15 | 8:06 | File > External Data > Unpack Resources (textures for export) | menu shown | A observed | [after](evidence/frames/E15_8m06_after.jpg) [before](evidence/frames/E15_8m06_before.jpg) [view](evidence/crops/E15_8m06_view.png) `0,60,1525,545` |
| E16 | 8:47 | Double Lanes on; Road Median panel | median road with its own roadside-like settings; centre marking | A observed | [after](evidence/frames/E16_8m47_after.jpg) [before](evidence/frames/E16_8m47_before.jpg) [panel](evidence/crops/E16_8m47_panel.png) `1558,310,360,690` |
| E17 | 8:52 | Road panel: Parking Lane | Order Bicycle-Parking, Left / Right Parking, Divider Line 5.5 m, Hatched Area | A observed | [after](evidence/frames/E17_8m52_after.jpg) [before](evidence/frames/E17_8m52_before.jpg) [panel](evidence/crops/E17_8m52_panel.png) `1558,310,360,690` |
| E18 | 9:41 | RoadSide: My Props collection + Random Collection 'Rocks' | props every Spacing (10 m) left / right; rocks scattered (Density Factor 0.1) | A observed | [after](evidence/frames/E18_9m41_after.jpg) [before](evidence/frames/E18_9m41_before.jpg) [panel](evidence/crops/E18_9m41_panel.png) `1558,310,360,690` [view](evidence/crops/E18_9m41_view.png) `0,60,1525,545` |
| E19 | 10:45 | Start Point: Tongue Size, Crosswalk Zebra, End Line, End Marking Stop, Traffic Lights | crosswalk, STOP and a signal at the road start; red tongue beyond | A observed | [after](evidence/frames/E19_10m45_after.jpg) [before](evidence/frames/E19_10m45_before.jpg) [panel](evidence/crops/E19_10m45_panel.png) `1558,310,360,690` [view](evidence/crops/E19_10m45_view.png) `0,60,1525,545` |
| E20 | 10:28 | Extend panel | Start / End Point Offset with Edge / Center / Lane Marking, Median / Roadside Props, Parking, Bus/Bicycle, Bridge Piers | A observed | [after](evidence/frames/E20_10m28_after.jpg) [before](evidence/frames/E20_10m28_before.jpg) [panel](evidence/crops/E20_10m28_panel.png) `1558,310,360,690` |

## Junction Setup

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E21 | 11:06 | four roads ending at a crossing, drag 'Custum junction' in | red cross of road tongues; nothing converts yet | A observed | [after](evidence/frames/E21_11m06_after.jpg) [before](evidence/frames/E21_11m06_before.jpg) [view](evidence/crops/E21_11m06_view.png) `0,60,1525,545` |
| E22 | 11:22 | junction modifier '02. CRM Junctions' | Roads collection empty; Show, Range 40 m, Inner Radius 2 m, Resolution 10 | A observed | [after](evidence/frames/E22_11m22_after.jpg) [before](evidence/frames/E22_11m22_before.jpg) [panel](evidence/crops/E22_11m22_panel.png) `1558,310,360,690` |
| E23 | 11:57 | collections 'Roads' and 'Junctions'; set the junction's Roads | tongues inside the range become one junction mesh | A observed | [after](evidence/frames/E23_11m57_after.jpg) [before](evidence/frames/E23_11m57_before.jpg) [view](evidence/crops/E23_11m57_view.png) `0,60,1525,545` |
| E24 | 12:21 | Alt + click RoadSide on all selected roads | every road gets its roadside; junction corners yellow | A observed | [after](evidence/frames/E24_12m21_after.jpg) [before](evidence/frames/E24_12m21_before.jpg) [view](evidence/crops/E24_12m21_view.png) `0,60,1525,545` |
| E25 | 12:27 | junction RoadSide on; Show off / on | red part -> road, yellow part -> roadside | A observed | [after](evidence/frames/E25_12m27_after.jpg) [before](evidence/frames/E25_12m27_before.jpg) [view](evidence/crops/E25_12m27_view.png) `0,60,1525,545` [panel](evidence/crops/E25_12m27_panel.png) `1558,310,360,690` |
| E26 | 13:03 | tongues must overlap slightly; a too long tongue | merging issues | A observed | [after](evidence/frames/E26_13m03_after.jpg) [before](evidence/frames/E26_13m03_before.jpg) [view](evidence/crops/E26_13m03_view.png) `0,60,1525,545` |
| E27 | 13:30 | tongues must share one global height | misaligned tongues avoided | B transcript | [after](evidence/frames/E27_13m30_after.jpg) [before](evidence/frames/E27_13m30_before.jpg) [view](evidence/crops/E27_13m30_view.png) `0,60,1525,545` |
| E28 | 15:54 | downhill road: Make Local + single user, last three points level (global Z) | aligned tongue on a slope; junction clean after moving the point back | A observed | [after](evidence/frames/E28_15m54_after.jpg) [before](evidence/frames/E28_15m54_before.jpg) [view](evidence/crops/E28_15m54_view.png) `0,60,1525,545` |
| E29 | 16:18 | do not rotate / scale the junction in object mode | range circle | B transcript | [after](evidence/frames/E29_16m18_after.jpg) [before](evidence/frames/E29_16m18_before.jpg) [view](evidence/crops/E29_16m18_view.png) `0,60,1525,545` |
| E30 | 17:00 | edit mode: scale the junction's cube | everything inside the volume converts | A observed | [after](evidence/frames/E30_17m00_after.jpg) [before](evidence/frames/E30_17m00_before.jpg) [view](evidence/crops/E30_17m00_view.png) `0,60,1525,545` |
| E31 | 17:45 | Range 1000 m | every intersection in the scene converted by one junction object | A observed | [after](evidence/frames/E31_17m45_after.jpg) [before](evidence/frames/E31_17m45_before.jpg) [view](evidence/crops/E31_17m45_view.png) `0,60,1525,545` [panel](evidence/crops/E31_17m45_panel.png) `1558,310,360,690` |
| E32 | 18:21 | overlapping junctions | double meshes: black effect in Cycles | A observed | [after](evidence/frames/E32_18m21_after.jpg) [before](evidence/frames/E32_18m21_before.jpg) [view](evidence/crops/E32_18m21_view.png) `0,60,1525,545` |

## Extension Feature

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E33 | 18:42 | Extensions catalog | three extensions: two mesh-based, one curve-based, red / yellow like tongues | A observed | [after](evidence/frames/E33_18m42_after.jpg) [before](evidence/frames/E33_18m42_before.jpg) [assets](evidence/crops/E33_18m42_assets.png) `0,610,1525,370` |
| E34 | 19:16 | square extension in the Roads collection inside the junction | converted to road mesh | A observed | [after](evidence/frames/E34_19m16_after.jpg) [before](evidence/frames/E34_19m16_before.jpg) [view](evidence/crops/E34_19m16_view.png) `0,60,1525,545` [panel](evidence/crops/E34_19m16_panel.png) `1558,310,360,690` |

## Extension / Bus Stop

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E35 | 20:48 | square extension at the road edge, Make Local, scale in edit mode | bus bay notch in the roadside | A observed | [after](evidence/frames/E35_20m48_after.jpg) [before](evidence/frames/E35_20m48_before.jpg) [view](evidence/crops/E35_20m48_view.png) `0,60,1525,545` |
| E36 | 21:33 | bus stop asset + BUS / STOP markings (at level 1 like the roads) | furnished bus bay | A observed | [after](evidence/frames/E36_21m33_after.jpg) [before](evidence/frames/E36_21m33_before.jpg) [view](evidence/crops/E36_21m33_view.png) `0,60,1525,545` |

## Extension / Rounded End-road

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E37 | 22:48 | round extension at a road end, smaller, roadside smaller | cul-de-sac bulb | A observed | [after](evidence/frames/E37_22m48_after.jpg) [before](evidence/frames/E37_22m48_before.jpg) [view](evidence/crops/E37_22m48_view.png) `0,60,1525,545` |

## Extension / Roundabout

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E38 | 24:30 | round extension at a crossing + 'sidewalk round' + greenery | roundabout | A observed | [after](evidence/frames/E38_24m30_after.jpg) [before](evidence/frames/E38_24m30_before.jpg) [view](evidence/crops/E38_24m30_view.png) `0,60,1525,545` |
| E39 | 26:02 | alternative: tongues + sidewalk round only | roundabout without the big rounded asphalt | A observed | [after](evidence/frames/E39_26m02_after.jpg) [before](evidence/frames/E39_26m02_before.jpg) [view](evidence/crops/E39_26m02_view.png) `0,60,1525,545` |

## Extension / Parking Space

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E40 | 27:51 | big square extension + small square entrance (apply scale) | parking area with an entrance | A observed | [after](evidence/frames/E40_27m51_after.jpg) [before](evidence/frames/E40_27m51_before.jpg) [view](evidence/crops/E40_27m51_view.png) `0,60,1525,545` |
| E41 | 28:45 | Marking Lines curve ('03. CRM Marking Lines'), Array modifier | parking bay lines | A observed | [after](evidence/frames/E41_28m45_after.jpg) [before](evidence/frames/E41_28m45_before.jpg) [view](evidence/crops/E41_28m45_view.png) `0,60,1525,545` [panel](evidence/crops/E41_28m45_panel.png) `1558,310,360,690` |
| E42 | 30:13 | curve extension ('10. CRM Extension'), junction range increased to cover the tongues | a junction made of extensions | A observed | [after](evidence/frames/E42_30m13_after.jpg) [before](evidence/frames/E42_30m13_before.jpg) [view](evidence/crops/E42_30m13_view.png) `0,60,1525,545` [panel](evidence/crops/E42_30m13_panel.png) `1558,310,360,690` |

## Custom Sign

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E43 | 31:06 | Custom Sign: Panel shape / colour, Back Post shape / struts / poles | sign panel and post | A observed | [after](evidence/frames/E43_31m06_after.jpg) [before](evidence/frames/E43_31m06_before.jpg) [view](evidence/crops/E43_31m06_view.png) `0,60,1525,545` [panel](evidence/crops/E43_31m06_panel.png) `1558,310,360,690` |
| E44 | 31:45 | Text Line 1..3: three texts each (colour, size, X, Y) | up to nine texts | A observed | [after](evidence/frames/E44_31m45_after.jpg) [before](evidence/frames/E44_31m45_before.jpg) [panel](evidence/crops/E44_31m45_panel.png) `1558,310,360,690` |
| E45 | 32:47 | node editor: '13. CRM Custom Sign' > 'Panel Text' > String to Curves font | the font is chosen inside the group | A observed | [after](evidence/frames/E45_32m47_after.jpg) [before](evidence/frames/E45_32m47_before.jpg) [nodes](evidence/crops/E45_32m47_nodes.png) `0,470,1575,435` [panel](evidence/crops/E45_32m47_panel.png) `1628,330,290,650` |
| E46 | 33:22 | Images: material + size / X / Y (three) | image on the sign from a material | A observed | [after](evidence/frames/E46_33m22_after.jpg) [before](evidence/frames/E46_33m22_before.jpg) [panel](evidence/crops/E46_33m22_panel.png) `1558,310,360,690` |
| E47 | 34:57 | a stop sign built with the custom sign (Octagon, Red, outline) | stop sign | A observed | [after](evidence/frames/E47_34m57_after.jpg) [before](evidence/frames/E47_34m57_before.jpg) [view](evidence/crops/E47_34m57_view.png) `0,60,1525,545` [panel](evidence/crops/E47_34m57_panel.png) `1558,310,360,690` |
| E48 | 35:17 | Lines Shap: up to three lines (colour, length, width, rotation, X, Y) | lines on the panel | A observed | [after](evidence/frames/E48_35m17_after.jpg) [before](evidence/frames/E48_35m17_before.jpg) [panel](evidence/crops/E48_35m17_panel.png) `1558,310,360,690` |

## Tunnel / Bridge

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E49 | 36:04 | tunnel ('12. CRM_Tunnel') comes without a road: duplicate its curve, add Geometry Nodes '01. CRM Road' | road exactly under the tunnel | A observed | [after](evidence/frames/E49_36m04_after.jpg) [before](evidence/frames/E49_36m04_before.jpg) [view](evidence/crops/E49_36m04_view.png) `0,60,1525,545` [panel](evidence/crops/E49_36m04_panel.png) `1558,310,360,690` |
| E50 | 36:21 | cable-stayed bridge ('15. CRM Cable-Stayed'): the same | road on the bridge | A observed | [after](evidence/frames/E50_36m21_after.jpg) [before](evidence/frames/E50_36m21_before.jpg) [view](evidence/crops/E50_36m21_view.png) `0,60,1525,545` [panel](evidence/crops/E50_36m21_panel.png) `1558,310,360,690` |

## Mountain Road

| id | time | action | visible result | class | evidence |
|---|---|---|---|---|---|
| E51 | 36:52 | terrain ('16. CRM Terrain'), view clip end 10000 | terrain object | A observed | [after](evidence/frames/E51_36m52_after.jpg) [before](evidence/frames/E51_36m52_before.jpg) [view](evidence/crops/E51_36m52_view.png) `0,60,1525,545` [panel](evidence/crops/E51_36m52_panel.png) `1558,310,360,690` |
| E52 | 37:47 | draw a road on it, Pull Terrain on, terrain Roads = 'Roads' | terrain pulled to the road | A observed | [after](evidence/frames/E52_37m47_after.jpg) [before](evidence/frames/E52_37m47_before.jpg) [view](evidence/crops/E52_37m47_view.png) `0,60,1525,545` [panel](evidence/crops/E52_37m47_panel.png) `1558,310,360,690` |
| E53 | 39:13 | Flatting Size 32.5 m, Smoothness 3; fix the road's rotation | flattened corridor | A observed | [after](evidence/frames/E53_39m13_after.jpg) [before](evidence/frames/E53_39m13_before.jpg) [view](evidence/crops/E53_39m13_view.png) `0,60,1525,545` [panel](evidence/crops/E53_39m13_panel.png) `1558,310,360,690` |
| E54 | 41:03 | bridge segment: Pull Terrain off, Bridge, Bridge Barrier, Piers, Pier Height | bridge over the valley | A observed | [after](evidence/frames/E54_41m03_after.jpg) [before](evidence/frames/E54_41m03_before.jpg) [view](evidence/crops/E54_41m03_view.png) `0,60,1525,545` [panel](evidence/crops/E54_41m03_panel.png) `1558,310,360,690` |
| E55 | 42:44 | bridge abutment assets at both ends (rotation Z 180) | finished mountain road | A observed | [after](evidence/frames/E55_42m44_after.jpg) [before](evidence/frames/E55_42m44_before.jpg) [view](evidence/crops/E55_42m44_view.png) `0,60,1525,545` |

