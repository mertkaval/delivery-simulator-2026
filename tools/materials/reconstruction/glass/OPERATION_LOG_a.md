# Glass video, segment a: operation log

`SNKNqHd0AYI` 00:00-22:32. One row per meaningful operation, in video order. **t** is the true video time (mm:ss.s); evidence paths are relative to `tools/materials/reconstruction/glass/evidence/a/`. Class: A seen in a frame, B narration only, C inference, D unresolved. Demo edits on finished group nodes are listed but are not part of the reconstructed values. Generated from `evidence/a/index.json` (same events).


## Intro and customizable nodes overview (0:00-2:42), purchased project file

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 00:04.5 | Intro: finished product render shown in the 3D viewport (Rendering Done) | 3x2 glass panes in black frames on a dark studio backdrop; status bar shows Blender 5.1.1, objects named Cube.00x (product scene) | A | `frames/t0004_intro_final_render_six_panes.jpg` |
| 00:42.5 | Overview: Textured Glass Circles group node (purchased project file), before demo edits | controls: Scale 1, Glass Color white, Glass Roughness 0.200 (factor), Glass IOR 1.500, Voronoi Scale 50, Voronoi Detail 0, Voronoi Roughness 0.5 (f), Voronoi Smoothness 1 (f), Voronoi Randomness 1 (f), Bump Strength 1 (f) | A | `frames/t0042_overview_product_circles_group.jpg`<br>`crops/t0042_product_circles_controls.png` |
| 00:45.5 | Overview demo: Circles Scale dragged (2.7); 0:50 colour picker tint #BEDAFF; 0:54 Glass Roughness 0.454; 0:58-1:02 IOR 1.12/1.29; 1:06 Voronoi Scale 54.4; 1:10 Voronoi Detail 6.7; 1:14 Bump Strength | temporary demo values (not part of the reconstructed defaults) | A | - |
| 01:18.5 | Overview: Textured Glass Voronoi group node (product), before demo edits | controls: Scale 1, Glass Color pale mint (display ~#ECFEF0), Glass Roughness 0.200 (f), Glass IOR 1.5, Voronoi Scale 1 30, Voronoi Scale 2 30, Voronoi Smoothness 1 0.1 (f), Voronoi Smoothness 2 0.03 (f), Voronoi Detail 1 3.000, Voronoi Detail 2 1.000 (factor bar), Bump Strength 1/2 1.0 (f) | A | `frames/t0118_overview_product_voronoi_group.jpg`<br>`crops/t0118_product_voronoi_controls.png` |
| 01:38.5 | Overview: Textured Glass Cells group node (product) | controls: Scale 1, Glass Color white, Glass Roughness 1.000 (plain float), Glass IOR 1.5, Voronoi Scale 30, Voronoi Detail 0, Voronoi Roughness 0.5 (f), Voronoi Randomness 1 (f), Bump Strength 1 (f); no noise controls | A | `frames/t0138_overview_product_cells_group.jpg`<br>`crops/t0138_product_cells_controls.png` |
| 02:00.5 | Overview: Textured Glass Wavy group node (product; built in segment b) | controls: Scale 1, Glass Color white, Glass Roughness 0.2 (f), Glass IOR 1.5, Bump Strength 1 (f), Rotation X/Y/Z 0 deg | A | `crops/t0200_product_wavy_controls.png` |
| 02:16.5 | Overview: Textured Glass Blobby group node (product; built in segment b) | controls: Scale 1, Glass Color white, Glass Roughness 1.000, Glass IOR 1.5, Voronoi Scale 10, Voronoi Detail 2.6, Voronoi Roughness 0.5 (f), Voronoi Smoothness 0.1 (f), Bump Strength 1 (f) | A | `crops/t0216_product_blobby_controls.png` |
| 02:28.5 | Overview: Frosted Glass group node (product; built in segment b) | controls: Scale 1, Glass Color white, Glass Roughness 1.000, Glass IOR 1.5, Noise Scale 20, Noise Detail 15, Noise Roughness 1.0 (f) | A | `crops/t0228_product_frosted_controls.png` |

## Scene setup (3:14-6:10)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 03:22.5 | Layout: Shift+A > Mesh > Plane | default 2 m plane at the origin (overlay 'Add Plane') | A | - |
| 03:26.5 | S .4 Return | plane scaled to 0.4 (0.8 m x 0.8 m) | A | `crops/t0326_keys_S_0p4.png` |
| 03:29.5 | R X 90 Return | plane rotated 90 deg about global X (stands vertical, normal -Y) | A | `crops/t0327_header_rotation_global_x.png`<br>`crops/t0329_keys_R_X_90.png` |
| 03:34.5 | Ctrl+A > Apply Object Transform (Rotation & Scale per narration) | rotation and scale applied (object scale 1, mesh in metres) | A | `frames/t0334_setup_apply_object_transform.jpg`<br>`crops/t0330_keys_ctrlA_apply_menu.png`<br>`crops/t0334_apply_object_transform.png` |
| 03:36.5 | Shift+D, X (interactive) | second pane ~0.88-0.90 m along +X (live readout 'D: 0.8845 along global X') | A | `crops/t0336_header_dup_dx.png` |
| 03:38.5 | Shift+D, X (interactive) | third pane ~-1.76 m from the second (live readout 'D: -1.7553 along global X') | A | `crops/t0338_header_dup_dx2.png` |
| 03:41.5 | box select row, Shift+D, Z (interactive) | second row ~0.87 m below (live readout 'D: -0.8707 along global Z') | A | `crops/t0341_header_dup_dz.png` |
| 03:42.5 | result: 2 rows x 3 panes; then G Z moves all up (amount not shown) | six 0.8 m panes (Plane..Plane.005) | A | `frames/t0342_setup_six_panes_grid.jpg` |
| 03:50.5 | Shift+A > Mesh > Monkey, scaled down, moved, Ctrl+A apply scale, Shift+D duplicates | 4 Suzannes behind the panes (status: 10 objects = 6 planes + 4 monkeys, no lamp) | A | - |
| 04:17.5 | Suzanne.001: New material 'red'; Base Color picker (Perceptual HSV) drag | H 0.009 S 1.000 V 0.906 #E70C00 (still dragging) | A | `crops/t0417_red_picker_drag.png` |
| 04:18.2 | red Base Color final before the picker closes | H 0.009 S 1.000 V 0.956, Hex #F40D00; other Principled inputs default (Metallic 0, Roughness 0.5, IOR 1.5) | A | `crops/t0418_red_picker_final.png` |
| 04:22.5 | drag-and-drop the material onto the other monkeys | overlay 'Drop Named Material on Object' | A | - |
| 04:30.5 | Shift+A > Camera; Ctrl+Alt+Numpad0 at ~4:36; G and G+MMB moves | camera aligned to the view, moved interactively | A | - |
| 04:46.5 | camera properties | Perspective, Focal Length 50 mm, Lens Unit Millimeters, Shift 0/0, Clip 0.1/1000, Depth of Field off | A | `crops/t0446_camera_lens.png` |
| 04:52.5 | Render Engine > Cycles | Cycles; Device GPU Compute; OSL off; Motion Blur checkbox on; Sampling panel never opened | A | `frames/t0453_setup_render_cycles_gpu.jpg`<br>`crops/t0452_render_engine_menu.png`<br>`crops/t0453_render_device.png` |
| 05:06.5 | World: Color > Environment Texture > open HDRI; Strength 0.5 | old_apartments_walkway_1k.hdr (Poly Haven 1K), Linear, Equirectangular, Single Image, Color Space Linear Rec.709, Alpha Premultiplied, Vector Default, Strength 0.500 | A | `frames/t0506_setup_world_hdri.jpg`<br>`crops/t0506_world_hdri.png`<br>`crops/t0506_blender_version.png` |
| 05:30.5 | Render > Film > Transparent on | Exposure 1.00, Pixel Filter Blackman-Harris 1.50 px, Transparent checked | A | `crops/t0530_film_transparent.png` |
| 05:34.5 | Color Management > View > Filmic | View Filmic (menu lists ACES 2.0, Khronos PBR Neutral, AgX, Filmic, Filmic Log, False Color, Raw) | A | `crops/t0534_view_transform_menu.png` |
| 05:38.5 | Color Management > Look > Very High Contrast | Display sRGB, View Filmic, Look Very High Contrast, Exposure 0, Gamma 1 | A | `crops/t0538_color_management.png` |
| 05:50.5 | Shading workspace, camera view; Plane.002 > New material, renamed 'Textured Glass Circles' | material created with default Principled BSDF | A | - |
| 06:00.0 | narration: enable the Node Wrangler add-on (Edit > Preferences > Add-ons) | Node Wrangler used for Ctrl+T and Ctrl+Shift+click previews | B | - |

## Textured Glass Circles (6:10-10:55)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 06:13.5 | select Principled BSDF, X | Principled deleted | A | - |
| 06:19.5 | Shift+A 'glas' > Glass BSDF; BSDF -> Material Output Surface | Glass: Multiscatter GGX, Color white, Roughness 0, IOR 1.5 | A | - |
| 06:28.5 | Shift+A 'vor' > Voronoi Texture; Ctrl+Shift+click preview | defaults 3D/F1/Euclidean, Scale 5, Detail 0, Roughness 0.5, Lacunarity 2, Randomness 1 | A | - |
| 06:34.5 | Voronoi feature F1 -> Smooth F1 | Smoothness socket appears (1.0) | A | `crops/t0634_voronoi_feature_menu.png` |
| 06:40.5 | Voronoi Scale 50 | Scale 50, Detail 0, Roughness 0.5, Lacunarity 2, Smoothness 1, Randomness 1, Normalize off | A | `frames/t0640_circles_voronoi_smoothf1_scale50.jpg`<br>`crops/t0640_voronoi_smoothf1_scale50.png` |
| 06:46.5 | Ctrl+T (Node Wrangler) on the Voronoi | Texture Coordinate + Mapping added; NW linked Generated -> Mapping Vector | A | `crops/t0646_ctrlT_generated_link.png` |
| 06:56.5 | relink Texture Coordinate Object -> Mapping Vector | object coordinates used (final) | A | `crops/t0656_texcoord_object_link.png` |
| 07:01.5 | Voronoi Distance -> Glass Normal (temporary) | replaced by the Bump at 7:13 | A | - |
| 07:16.5 | Shift+A 'bum' > Bump dropped between | Distance -> Bump Height, Bump Normal -> Glass Normal; default Distance 0.001 | A | - |
| 07:22.5 | Bump Distance typed 0.002 | Distance 0.002, Strength 1, Filter Width 0.1 | A | `crops/t0722_bump_distance_typed.png` |
| 07:25.5 | Bump Strength 0 demo, back to 1.000 at 7:28 | temporary | A | - |
| 07:37.5 | Shift+A 'rgb' > RGB Curves dropped between Voronoi and Bump | Distance -> Curves Color input; Curves Color -> Bump Height | A | - |
| 07:46.5 | C curve: first point added (0.5075, 0.4535); 7:49 second point (0.2788, 0.3571) | two interior points | A | - |
| 07:55.5 | Bump Invert on | dots read as dents | A | - |
| 08:14.0 | curve points adjusted in side view (7:52-8:14) | upper point (0.5804, 0.6535) final | A | `crops/t0814_curves_upper_point_invert.png` |
| 08:14.6 | lower point readout after the adjustments | (0.3140, 0.2464) final (unchanged to 10:43) | A | - |
| 08:25.5 | Glass Roughness 0.2 | frosted look | A | `crops/t0825_glass_roughness_0p2.png` |
| 08:37.5 | box select all but Material Output, Ctrl+G | NodeGroup created | A | - |
| 08:46.5 | Tab out, group renamed 'Textured Glass Circles' (pasted material name) | group node in material, Shader -> Surface | A | - |
| 08:52.5 | Tab in, N panel: Group Sockets output 'BSDF' renamed 'Shader' | output socket Shader | A | `crops/t0852_group_sockets_bsdf.png` |
| 09:07.5 | Mapping Scale -> Group Input extra socket | interface 'Scale' Vector XYZ (1,1,1) | A | - |
| 09:16.5 | Scale type Vector -> Float; default typed 1 | Float, subtype None, default 1.000, min -inf, max inf | A | `crops/t0916_np_scale_type_menu.png`<br>`crops/t0922_np_scale_float_default1.png` |
| 09:25.5 | Tab out: group node Scale was 0.000, set back to 1 | group node Scale 1.0 (2.8 drag seen at 9:28) | A | - |
| 09:43.5 | Glass Color -> extra socket, renamed 'Glass Color' | Color, default white | A | `crops/t0943_np_glass_color.png` |
| 09:49.5 | Glass Roughness -> extra socket, renamed | Float Factor 0.200, 0..1 | A | `crops/t0949_np_glass_roughness.png` |
| 09:55.5 | Glass IOR -> extra socket, renamed | Float None 1.500, 0..1000 | A | `crops/t0955_np_glass_ior.png` |
| 10:16.5 | Voronoi Scale, Detail, Roughness -> extra sockets, renamed Voronoi Scale/Detail/Roughness | Voronoi Scale Float 50, -1000..1000 | A | `crops/t1016_np_voronoi_scale.png` |
| 10:22.5 | Voronoi Roughness socket | Float Factor 0.5, 0..1, 'The influenc...evious layer' | A | `crops/t1022_np_voronoi_roughness.png` |
| 10:31.5 | Voronoi Smoothness + Randomness -> extra sockets, renamed | Voronoi Smoothness Factor 1.0, 0..1 | A | `crops/t1031_np_voronoi_smoothness.png` |
| 10:39.5 | Bump Strength -> extra socket, renamed 'Bump Strength' | Factor 1.0, 0..1, 'Strength of t...p mapping' | A | `crops/t1039_np_bump_strength.png` |
| 10:43.5 | final Circles group graph visible | GI -> TexCoord/Mapping -> Voronoi -> RGB Curves -> Bump -> Glass -> Group Output | A | `frames/t1043_circles_group_final_graph.jpg`<br>`crops/t1043_group_input_texcoord_mapping.png`<br>`crops/t1043_mapping_to_group_output.png`<br>`crops/t1043_distance_to_curves_color.png` |
| 10:44.5 | Tab out; result in camera view | finished Circles look (red Suzanne behind) | A | `frames/t1044_circles_viewport_look.jpg`<br>`crops/t1044_viewport_look.png` |
| 10:47.5 | group node demos (Bump Strength 0.445, Voronoi Randomness 0.715, Glass Color picker #CCEDFF at 10:52) | temporary; all defaults again at 22:29 | A | - |
| 22:29.5 | Circles group node seen again at 22:29 (H hides finished panes) | all values at the defaults | A | `crops/t2229_circles_group_node_values.png` |

## Textured Glass Voronoi (10:55-16:43)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 11:00.5 | Plane: New material 'Textured Glass Voronoi'; Voronoi + Ctrl+T, Object coordinates | TexCoord Object -> Mapping -> Voronoi | A | - |
| 11:22.5 | Voronoi feature -> Smooth F1 | Smooth F1, Scale 5 | A | `crops/t1122_voronoi1_feature_smooth_f1.png` |
| 11:26.5 | Scale typed 30 (then undone) | Scale 30 | A | - |
| 11:28.5 | Ctrl+Z x4 | Scale back to 5.000; Roughness 0.000; Detail 0 | A | `crops/t1128_undo_ctrl_z_x4.png` |
| 11:36.5 | Smoothness typed .1 | Smoothness 0.100 | A | `crops/t1136_voronoi1_smoothness_0p1.png` |
| 11:48.5 | Shift+A Bump; Principled deleted; Shift+A Glass BSDF (11:52) | Glass Multiscatter GGX | A | - |
| 12:00.5 | Bump Normal -> Glass Normal; Voronoi Distance -> Bump Height | bump chain | A | - |
| 12:04.5 | unplug the link into Glass Color | Glass Color unlinked (white) | A | `crops/t1204_glass_color_link_removed.png` |
| 12:08.5 | Bump Distance 0.004 | Distance 0.004 | A | `crops/t1208_bump1_distance_0p004.png` |
| 12:20.5 | Voronoi Scale 30 typed again | V1: Smooth F1, Scale 30, Detail 0, Roughness 0, Lacunarity 2, Smoothness 0.1, Randomness 1 | A | `crops/t1220_voronoi1_values.png` |
| 12:28.5 | Bump Invert on | Invert checked | A | `crops/t1228_bump1_invert.png` |
| 12:40.5 | Shift+Ctrl+D on the Voronoi (duplicate keeping input links) | V2 with the Mapping link | A | `crops/t1240_dup_voronoi_shift_ctrl_d.png` |
| 13:00.5 | V2 Detail 3, Roughness 1, Smoothness 0.030 | V2: Scale 30, Detail 3, Roughness 1, Lacunarity 2, Smoothness 0.03, Randomness 1 | A | `crops/t1300_voronoi2_values.png` |
| 13:08.5 | Shift+D Bump; V2 Distance -> Bump2 Height; Bump2 Normal -> Bump1 Normal | two bump layers chained | A | `crops/t1308_bump2_chain.png` |
| 13:26.5 | Bump2 Distance typed 0.00008 | field shows 0.00008; displays 0.0001 afterwards (4-decimal display) | A | `crops/t1326_bump2_distance_typed.png` |
| 13:44.5 | RGB Curves dropped after V1; Shift+D copy dropped after V2 | two curves nodes | A | - |
| 14:05.5 | Curves1 C point added and dragged | (0.6758, 0.2928) final | A | `crops/t1405_curves1_final_point.png` |
| 14:17.5 | Curves2 C point dragged | (0.6331, 0.3000) final | A | `crops/t1417_curves2_final_point.png` |
| 14:29.5 | box select, Ctrl+G; Tab out; renamed 'Textured Glass Voronoi' | group node | A | - |
| 14:59.5 | output BSDF -> 'Shader'; Mapping Scale -> 'Scale' Vector -> Float, default 1 | Float 1.0, -inf..inf | A | `crops/t1459_np_scale_float.png` |
| 15:17.5 | Glass Color -> 'Glass Color' | Color white | A | `crops/t1517_np_glass_color.png` |
| 15:23.5 | Glass Roughness -> 'Glass Roughness' | Float Factor 0.000, 0..1 | A | `crops/t1523_np_glass_roughness_factor0.png` |
| 15:29.5 | Glass IOR -> 'Glass IOR' | Float 1.5, 0..1000 | A | `crops/t1529_np_glass_ior.png` |
| 15:35.5 | V1 Scale then V2 Scale -> extra sockets | two 'Scale' sockets (30, -1000..1000) | A | `crops/t1544_np_voronoi_scale.png` |
| 15:50.5 | V1 then V2 Smoothness -> extra sockets | second Smoothness Factor 0.030 | A | `crops/t1550_np_smoothness2.png` |
| 15:53.5 | V1 then V2 Detail -> extra sockets | second Detail 3.000, 0..15 | A | `crops/t1553_np_detail2.png` |
| 16:05.5 | renamed Voronoi Scale 1/2, Voronoi Smoothness 1/2 | Smoothness 1 Factor 0.100 | A | `crops/t1605_np_smoothness1.png` |
| 16:14.5 | renamed Voronoi Detail 1/2 | Detail 1 Float 0.000, 0..15 | A | `crops/t1614_np_detail1.png` |
| 16:15.5 | Bump1 Strength linked first, then Bump2 Strength (16:16) | Strength sockets in that order | A | `crops/t1615_bump1_strength_linked_first.png` |
| 16:23.5 | renamed Bump Strength 1/2 | Factor 1.0, 0..1 | A | `crops/t1623_np_bump_strength1.png` |
| 16:26.5 | final Voronoi group graph visible | 12 inputs wired; two Voronoi/Curves/Bump chains | A | `frames/t1626_voronoi_group_final_graph.jpg`<br>`crops/t1626_inputs_texcoord_voronois.png`<br>`crops/t1626_curves_bumps.png`<br>`crops/t1626_bumps_glass_output.png`<br>`crops/t1626_viewport_look.png` |
| 16:32.5 | group node demos (Scale 4.7, Glass Color picker turned green, Voronoi Smoothness 1 0.947, Bump Strength 1 0) | temporary; defaults again at 16:41 | A | - |
| 16:41.5 | Voronoi group node values at the end of the chapter | Scale 1, white, Roughness 0, IOR 1.5, 30/30, 0.1/0.03, 0/3, 1/1 | A | `frames/t1641_voronoi_group_node_final.jpg`<br>`crops/t1641_voronoi_group_node_values.png` |

## Textured Glass Cells (17:52-22:32); course ad 16:43-17:52 skipped

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 17:57.5 | Plane.001: New material 'Textured Glass Cells'; Voronoi; Ctrl+T, Object coordinates | TexCoord Object -> Mapping -> Voronoi | A | - |
| 18:17.5 | Voronoi feature F1 -> Distance to Edge | no Smoothness socket | A | `crops/t1817_voronoi_distance_to_edge.png` |
| 18:24.5 | Voronoi Scale 30 | Scale 30, Detail 0, Roughness 0.5, Lacunarity 2, Randomness 1 | A | - |
| 18:40.5 | Bump added, Principled deleted, Glass BSDF -> Surface, Bump Normal -> Glass Normal, Distance -> Height | bump chain | A | - |
| 18:48.5 | Bump Distance 0.003, Invert on | Distance 0.003, Invert checked | A | - |
| 19:04.5 | Shift+A Map Range dropped between Voronoi and Bump | Float, Linear, Clamp on, 0/1/0/1 | A | `crops/t1904_map_range_bump.png` |
| 19:20.5 | From Min dragged (0.19, 0.07, 0.03) and set 0.020 | From Min 0.020 | A | - |
| 19:37.5 | Shift+A Noise Texture; Mapping Vector -> Noise Vector; Scale 20, Detail 15, Roughness 1 | fBM, Normalize on, Lacunarity 2, Distortion 0 | A | `crops/t1937_noise_values.png` |
| 19:44.5 | Noise Factor -> Glass Roughness | - | A | - |
| 19:52.5 | Shift+A 'ram' > Color Ramp dropped between noise and glass | Noise Factor -> Ramp Factor, Ramp Color -> Glass Roughness | A | - |
| 19:57.8 | white stop (index 1, pos 1.0) darkened in the picker | last value before the popup closes: V 0.659 (Perceptual), #A8A8A8 | A | `crops/t1957_ramp_stop1_final_color.png` |
| 20:11.5 | Shift+A Hue/Saturation/Value dropped after the ramp; Value demo drags (0.97, 0.39) | Hue 0.5, Saturation 1, Value 1.0, Factor 1 | A | `crops/t2011_hsv_values.png` |
| 20:15.5 | whole graph before grouping | Noise -> Ramp -> HSV -> Glass Roughness; Voronoi -> Map Range -> Bump -> Glass Normal | A | `frames/t2015_cells_graph_before_grouping.jpg`<br>`crops/t2015_noise_ramp_hsv.png`<br>`crops/t2015_whole_graph.png`<br>`crops/t2015_voronoi_maprange_bump.png` |
| 20:18.5 | box select, Ctrl+G; renamed 'Textured Glass Cells'; output BSDF -> 'Shader' | group node | A | - |
| 20:40.5 | Mapping Scale -> 'Scale'; Vector -> Float; default 1; Tab out: node Scale 0 -> 1 | Float 1.0 | A | `crops/t2041_np_scale_vector_menu.png`<br>`crops/t2047_np_scale_float_default1.png` |
| 20:49.5 | Ctrl+Z x11 (key overlay) | no visible difference before/after; what was undone is unknown (D) | D | `crops/t2049_undo_ctrl_z_x11.png` |
| 20:56.5 | Glass Color -> 'Glass Color' | Color white | A | `crops/t2056_np_glass_color.png` |
| 21:02.5 | HSV Value -> 'Glass Roughness' | Float None 1.000, 0..2, 'Value shift...e it brighter' | A | `crops/t2102_np_glass_roughness_hsv_value.png` |
| 21:11.5 | Glass IOR -> 'Glass IOR' | Float 1.5, 0..1000 | A | `crops/t2111_np_glass_ior.png` |
| 21:20.5 | Voronoi Scale, Detail -> 'Voronoi Scale', 'Voronoi Detail' | Scale 30, -1000..1000 | A | `crops/t2120_np_voronoi_scale.png` |
| 21:36.5 | Voronoi Roughness, Randomness -> 'Voronoi Roughness', 'Voronoi Randomness' | Roughness Factor 0.5, 0..1 | A | `crops/t2136_np_voronoi_roughness.png` |
| 21:46.5 | Noise Scale, Detail, Roughness -> extra sockets; Scale renamed 'Noise Roughness Scale' | Float 20, -1000..1000 | A | `crops/t2144_np_noise_roughness_scale.png` |
| 21:50.5 | noise Roughness socket renamed 'Noise Roughness Detail 2' | Float Factor 1.0, 0..1 'Blend factor...o zero detail' | A | `crops/t2150_np_noise_roughness_detail2.png` |
| 21:54.5 | noise Detail socket renamed 'Noise Roughness Detail 1' | Float 15, 0..15 | A | `crops/t2154_np_noise_roughness_detail1.png` |
| 22:06.5 | Bump Strength -> 'Bump Strength' | Factor 1.0, 0..1 | A | `crops/t2206_np_bump_strength.png` |
| 22:07.5 | group interior with all inputs wired | Cells group final (right side partly behind the N panel; see 20:15) | A | `frames/t2207_cells_group_interior.jpg`<br>`crops/t2207_group_interior.png`<br>`crops/t2207_viewport_look.png` |
| 22:25.5 | Cells group node values at the end of the chapter (Voronoi Detail 2.1 demo at 22:20 reverted) | all defaults | A | `frames/t2225_cells_group_node_final.jpg`<br>`crops/t2225_cells_group_node_values.png` |
