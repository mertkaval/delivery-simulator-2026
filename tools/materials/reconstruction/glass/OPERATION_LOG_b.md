# Glass video, segment b: operation log

Video `SNKNqHd0AYI` (Ryan King Art), segment b 22:32-34:03 plus the overview (00:40-02:42) and the scene setup (03:14-06:10). Times are video mm:ss from the transcript and checked on frames (+-1 s); exact kept-frame times are in `evidence/b/index.json` (`frame_times`). Class: A seen in a frame, B narration only, C our inference, D unresolved. Frames are in `evidence/b/frames/`, crops in `evidence/b/crops/`; "video@" marks a frame that was inspected in the work folder but not kept. Temporary states are marked (temporary).

## Customizable nodes overview (product file, 00:40-02:42, variants of this segment only)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 01:59-02:15 | overview: product-file Textured Glass Wavy group node demonstrated | controls Scale 1, Glass Color white, Glass Roughness 0.2, Glass IOR 1.5, Bump Strength 1, Rotation (0,0,0); no Gabor Frequency | A | t0203_overview_product_wavy_group.png<br>crop t0203_overview_wavy_group_node.png |
| 02:10-02:14 | overview: Rotation Y dragged (65.5, 32.1, 60.6, 26.9 deg) then reset | wave direction rotates in the pane (narration: "rotate it on the Y axis") | A | t0211_overview_product_wavy_rotation_y_demo.png<br>crop t0211_overview_wavy_rotation_y.png |
| 02:15-02:27 | overview: product-file Textured Glass Blobby controls | Scale 1, Glass Color, Glass Roughness 1, Glass IOR 1.5, Voronoi Scale 10, Detail 2.6, Roughness 0.5, Smoothness 0.1, Bump Strength 1 | A | t0216_overview_product_blobby_group.png<br>crop t0216_overview_blobby_group_node.png |
| 02:27-02:43 | overview: product-file Frosted Glass controls (Scale dragged) | Scale, Glass Color, Glass Roughness 1, Glass IOR 1.5, Noise Scale 20, Noise Detail 15, Noise Roughness 1 | A | t0230_overview_product_frosted_group.png<br>crop t0230_overview_frosted_group_node.png |

## Scene setup (03:14-06:10, brief)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 03:19-03:21 | Shift+A > Mesh > Plane | default 2 m plane | A | video@03:21 key overlay "Shift+A Add Plane" |
| 03:22-03:24 | S .4 | Scale X/Y/Z = 0.4 -> 0.8 m pane | A | t0324_setup_plane_scale_0p4.png<br>crop t0324_scale_header.png |
| 03:25-03:30 | R X 90 | plane rotated 90 deg about X (header "Rotation ... along global X", keys "9 0 Return") | A | t0330_setup_rotate_x90_apply_menu.png<br>crop t0330_rotate_apply.png |
| 03:29-03:33 | Ctrl+A > Rotation & Scale | transform applied (object space = world-aligned metres) | B | t0330_setup_rotate_x90_apply_menu.png<br>crop t0330_rotate_apply.png |
| 03:35-03:46 | Shift+D along X twice, box select, Shift+D down Z, G Z | 3 x 2 grid of panes (offsets ~0.90 m in X; exact values D) | A | video@03:36 "D: 0.9015 along global X axis"<br>video@03:43 "D: 0.3990 along global Z" (mid-drag) |
| 03:50-04:05 | add Suzanne, scale down, move behind, Ctrl+A scale, duplicate | monkeys behind the glass | A | video@03:55<br>video@04:00<br>video@04:05 |
| 04:06-04:26 | Shading workspace, rendered viewport; monkey material "Red" (strong red Base Color), dragged onto the other monkeys | red monkeys | A | video@04:14<br>video@04:18<br>video@04:22 |
| 04:28-04:46 | add Camera, Ctrl+Alt+Numpad0, G / G+MMB | Camera.001: Perspective 50 mm, clip 0.1-1000 | A | t0440_setup_camera_lens_50mm.png<br>crop t0440_camera_lens.png |
| 04:49-04:56 | Render properties: Cycles | Render Engine Cycles, Device GPU Compute | A | t0450_setup_render_cycles_gpu.png<br>crop t0450_render_engine.png |
| 04:59-05:21 | World: Color -> Environment Texture, open old_apartments_walkway_1k.hdr, Strength 0.5 | HDRI lighting at half strength | A | t0516_setup_world_hdri_strength_0p5.png<br>crop t0516_world_hdri.png |
| 05:23-05:30 | Render > Film > Transparent on | transparent background | A | t0529_setup_film_transparent.png<br>crop t0529_film_transparent.png |
| 05:32-05:40 | Color Management: View Filmic, Look Very High Contrast | more contrast / saturation | A | t0537_setup_filmic_very_high_contrast.png<br>crop t0537_color_management.png<br>crop t0537_blender_version.png |
| 05:53-06:09 | Node Wrangler add-on enabled in Preferences | Ctrl+T and Ctrl+Shift+click available | B | - |

## Textured Glass Wavy (22:32-25:33)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 22:24-22:31 | H hides the finished panes | faster viewport | B | - |
| 22:32-22:38 | select pane, New material, rename | material "Textured Glass Wavy" on Plane.005 (Principled BSDF default) | A | t2250_wavy_gabor_2d_defaults.png |
| 22:38-22:45 | Shift+A search "Gabor", add Gabor Texture, Ctrl+Shift+click preview | Gabor wired to Material Output (temporary preview) | A | video@22:41<br>video@22:44 |
| 22:47-22:51 | Ctrl+T (Node Wrangler) then Object -> Mapping Vector | Texture Coordinate (Object) -> Mapping (Point) -> Gabor Vector | A | t2250_wavy_gabor_2d_defaults.png<br>crop t2250_wavy_texcoord_mapping_gabor2d.png |
| 22:50 | Gabor defaults visible | 2D, Scale 5, Frequency 2, Anisotropy 1, Orientation 45 deg | A | t2250_wavy_gabor_2d_defaults.png<br>crop t2250_wavy_texcoord_mapping_gabor2d.png |
| 22:52-22:55 | Gabor dimensions 2D -> 3D | Orientation becomes a direction ball (default ~ (0.707, 0.707, 0)) | A | t2255_wavy_gabor_3d_default_orientation.png<br>crop t2255_wavy_gabor_ball_default.png |
| 22:57-23:03 | drag the orientation ball | texture turned "pointing up and down" (intermediate) | A | video@22:59<br>video@23:01<br>video@23:03 |
| 23:05-23:07 | Gabor Scale 12 | smaller waves | A | t2348_wavy_full_graph_before_group.png<br>crop t2348_wavy_graph.png |
| 23:07-23:11 | Gabor Frequency 5 | more detailed waves | A | t2348_wavy_full_graph_before_group.png<br>crop t2348_wavy_graph.png |
| 23:12-23:16 | drag the orientation ball again | final direction ~ (0.797, 0.604, 0.0) (shading fit) | C | t2348_wavy_full_graph_before_group.png<br>t2500_wavy_group_interior_gabor_ball.png<br>crop t2348_wavy_gabor_ball.png<br>crop t2500_wavy_gabor_ball.png |
| 23:17-23:20 | delete Principled BSDF | Gabor Value previewed into Material Output Surface | A | video@23:18<br>video@23:20 |
| 23:21-23:24 | add Glass BSDF on the preview link | Glass BSDF -> Surface; Gabor Value -> Glass Color (temporary) | A | video@23:22 |
| 23:24-23:27 | add Bump | Bump node placed | A | video@23:24<br>video@23:26 |
| 23:27-23:30 | link Gabor Value -> Bump Height, Bump Normal -> Glass Normal | glass bumpy | A | t2348_wavy_full_graph_before_group.png<br>crop t2348_wavy_graph.png<br>video@23:28<br>video@23:30 |
| 23:30-23:32 | unplug Gabor Value from Glass Color | Glass Color back to white | A | video@23:32 |
| 23:33-23:40 | Bump Distance typed 0.0007 | less bumpy; field shows 0.001 afterwards | A | t2338_wavy_bump_distance_typed_0p0007.png<br>crop t2338_wavy_bump_distance_text.png |
| 23:41-23:45 | Glass Roughness 0.2 | slightly frosted | A | t2348_wavy_full_graph_before_group.png<br>crop t2348_wavy_graph.png |
| 23:48 | complete ungrouped graph visible | TexCoord -> Mapping -> Gabor(3D) -> Bump -> Glass -> Output | A | t2348_wavy_full_graph_before_group.png<br>crop t2348_wavy_graph.png |
| 23:48-23:54 | box select all but Material Output, Ctrl+G | node group created | A | video@23:51<br>video@23:53 |
| 23:56-24:01 | Tab out, copy material name, paste into the group name | group "Textured Glass Wavy" | A | video@23:58<br>video@24:00 |
| 24:02-24:10 | Tab in, N panel, rename output BSDF -> Shader | output socket "Shader" | A | video@24:06<br>video@24:09 |
| 24:13-24:23 | Mapping Scale -> extension socket; type Vector -> Float; default 1 | input "Scale" (Float, 1, -inf..inf) | A | crop wavy_interface_panels.png#0<br>crop wavy_interface_panels.png#1 |
| 24:24-24:28 | Tab out, group Scale set back to 1 | pattern visible again | B | video@24:26 |
| 24:30-24:47 | Glass Color, Roughness, IOR -> sockets; renamed Glass Color / Glass Roughness / Glass IOR | inputs with defaults white / 0.2 (factor) / 1.5 (0..1000) | A | crop wavy_interface_panels.png#2<br>crop wavy_interface_panels.png#3<br>crop wavy_interface_panels.png#4 |
| 24:49-24:58 | Gabor Frequency -> socket, renamed "Gabor Frequency" | Float 5.0, min 0, max inf | A | crop wavy_interface_panels.png#5 |
| 24:59-25:03 | Gabor Scale not exposed (Mapping scale already used) | - | B | - |
| 25:04-25:10 | Bump Strength -> socket "Bump Strength" | Factor 1.0, 0..1 | A | crop wavy_interface_panels.png#6 |
| 25:11-25:17 | Mapping Rotation -> socket "Rotation" | Vector, Euler Angles, (0,0,0) | A | t2517_wavy_iface_rotation_group_input.png<br>crop t2517_wavy_group_sockets_rotation.png<br>crop t2517_wavy_group_input_node.png |
| 25:17-25:20 | N closes panel, Tab out | group node with 7 inputs | A | video@25:18<br>video@25:20 |
| 25:21-25:28 | demo Rotation X 1.4 deg, reset | final instance values = defaults | A | t2526_wavy_final_group_node.png<br>crop t2526_wavy_group_node.png |
| 25:30-25:33 | H hides the pane | - | B | - |

## Textured Glass Blobby (25:33-29:50)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 25:34-25:41 | select next pane, New material "Textured Glass Blobby" | Plane.003 | A | video@25:38<br>video@25:40 |
| 25:41-25:50 | add Noise Texture, Ctrl+T, Object -> Mapping Vector, preview | TexCoord(Object) -> Mapping -> Noise | A | video@25:44<br>video@25:48 |
| 25:52-25:58 | Noise Scale 20, Detail 15, Roughness 1.0 | very detailed noise (for roughness) | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png |
| 26:05-26:13 | delete Principled, add Glass BSDF, BSDF -> Surface, Noise Factor -> Glass Roughness | noisy frosted glass | A | video@26:06<br>video@26:10<br>video@26:12 |
| 26:18-26:22 | add Color Ramp after the noise (on the link) | Noise Factor -> Ramp Fac -> Glass Roughness | A | video@26:20<br>video@26:22 |
| 26:23-26:34 | white stop darkened to light grey | stop 1 (pos 1.0) V 0.700 perceptual, #B2B2B2 (linear 0.448) | A | t2633_blobby_ramp_white_stop_v0p700.png<br>crop t2633_blobby_ramp_picker.png |
| 26:42-26:50 | add Hue/Saturation/Value after the ramp | Ramp Color -> HSV Color -> Glass Roughness; Value is the roughness control | A | video@26:46<br>video@26:50 |
| 26:52-27:03 | add Voronoi, Mapping Vector -> Voronoi Vector, preview | Voronoi on the same mapping | A | video@26:58<br>video@27:02 |
| 27:04-27:08 | Voronoi F1 -> Smooth F1 | smooth blob edges | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png |
| 27:09-27:15 | Voronoi Scale 10, Detail 2.6 | blobs with a little detail | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png |
| 27:17-27:22 | Voronoi Smoothness 0.1 | tiny bit of smoothness | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png |
| 27:23-27:32 | add Bump; Voronoi Distance -> Height; Bump Normal -> Glass Normal; preview glass | blobby relief | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png<br>video@27:28<br>video@27:31 |
| 27:35-27:40 | Bump Distance 0.001 -> 0.004 | more bumpy | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png<br>video@27:37.75 field "0.00|" while typing |
| 27:42 | complete ungrouped graph visible (box select) | all nodes and links readable | A | t2742_blobby_full_graph_before_group.png<br>crop t2742_blobby_graph.png<br>crop t2742_blobby_noise_factor_link.png |
| 27:41-27:47 | Ctrl+G | node group | A | video@27:46 |
| 27:48-27:53 | Tab out, copy material name into the group name | group "Textured Glass Blobby" | A | video@27:50<br>video@27:52 |
| 27:54-28:12 | Tab in; Mapping Scale -> socket; Vector -> Float; default 1; Tab out reset instance Scale 1; Tab in | input "Scale" | A | crop blobby_interface_panels.png#0 |
| 28:14-28:18 | rename BSDF -> Shader | output "Shader" | A | video@28:16 |
| 28:19-28:25 | Glass Color -> socket "Glass Color" | Color, white | A | crop blobby_interface_panels.png#1 |
| 28:27-28:32 | HSV Value -> socket "Glass Roughness" | Float 1.0, 0..2 | A | t2833_blobby_iface_glass_roughness_hsv_value.png<br>crop t2833_blobby_iface_glass_roughness.png<br>crop blobby_interface_panels.png#2 |
| 28:33-28:38 | Glass IOR -> socket "Glass IOR" | Float 1.5, 0..1000 | A | crop blobby_interface_panels.png#3 |
| 28:39-29:00 | Voronoi Scale, Detail, Smoothness -> sockets; renamed Voronoi Scale / Detail / Smoothness | 10 (-1000..1000) / 2.6 / 0.1 factor | A | crop blobby_interface_panels.png#4<br>crop blobby_interface_panels.png#5 |
| 29:02-29:24 | Noise Scale, Detail, Roughness -> sockets; renamed Noise Roughness Scale / Detail 1 / Detail 2 | 20 (-1000..1000) / 15 (0..15) / 1.0 factor | A | crop blobby_interface_panels.png#6<br>crop blobby_interface_panels.png#7<br>crop blobby_interface_panels.png#8 |
| 29:25-29:32 | Bump Strength -> socket "Bump Strength" | Factor 1.0 | A | crop blobby_interface_panels.png#9 |
| 29:33 | zoomed-out group interior | all 11 group-input links confirmed | A | t2933_blobby_group_interior_links.png<br>crop t2933_blobby_group_interior.png |
| 29:32-29:36 | N closes panel, group input moved back, Tab out | - | A | video@29:35 |
| 29:37-29:46 | demo Scale 4.7, Glass Color green, reset | final instance values = defaults | A | t2941_blobby_final_group_node.png<br>crop t2941_blobby_group_node.png<br>video@29:37<br>video@29:39 |
| 29:47-29:50 | H hides the pane | - | B | - |

## Frosted Glass and closing (29:50-34:03)

| t | action | visible result | class | frame / crop |
|---|---|---|---|---|
| 29:50-29:56 | select last pane, New material "Frosted Glass" | Plane.004 | A | video@29:52<br>video@29:56 |
| 30:01-30:10 | add Noise Texture, Ctrl+T, Object coordinates | TexCoord(Object) -> Mapping -> Noise | A | video@30:04<br>video@30:08<br>video@30:10 |
| 30:11-30:19 | preview noise; Scale 20, Detail 15, Roughness 1.0 | very detailed noise | A | t3116_frosted_full_graph_before_group.png<br>crop t3116_frosted_graph.png<br>video@30:14<br>video@30:16 |
| 30:20-30:28 | add Glass BSDF (search), delete Principled, Glass -> Surface | glass shader (a temporary noise link into the Principled disappears with it) | A | video@30:20<br>video@30:24<br>video@30:26<br>video@30:28 |
| 30:28-30:30 | Noise Factor -> Glass Roughness | "too rough" | A | video@30:30 |
| 30:35-30:40 | add Color Ramp after the noise | Noise Factor -> Ramp -> Roughness | A | video@30:36<br>video@30:40 |
| 30:40-30:45 | stop 0 (black) lifted | V 0.415 #6A6A6A (temporary) | A | t3044_frosted_ramp_stop0_temp_v0p415.png<br>crop t3044_frosted_ramp_stop0_temp.png |
| 30:45-30:52 | stop 1 (white) darkened | final V 0.719 #B7B7B7 (linear 0.4755) | A | t3051_frosted_ramp_stop1_v0p719.png<br>crop t3051_frosted_ramp_stop1.png |
| 30:52-30:56 | stop 0 re-edited | final V 0.342 #575757 (linear 0.0958) | A | t3055_frosted_ramp_stop0_v0p342.png<br>crop t3055_frosted_ramp_stop0.png |
| 31:01-31:08 | add Hue/Saturation/Value after the ramp | Ramp Color -> HSV Color -> Glass Roughness | A | video@31:04<br>video@31:06 |
| 31:08-31:12 | HSV Value demo 0 -> 2 -> 1 | Value left at 1.0 | A | video@31:08<br>video@31:10<br>video@31:12 |
| 31:16 | complete ungrouped graph visible | TexCoord -> Mapping -> Noise -> Ramp -> HSV -> Glass Roughness -> Output | A | t3116_frosted_full_graph_before_group.png<br>crop t3116_frosted_graph.png<br>crop t3116_frosted_noise_factor_link.png |
| 31:16-31:22 | box select, Ctrl+G | node group | A | video@31:18<br>video@31:20 |
| 31:22-31:28 | Tab out, paste material name as group name | group "Frosted Glass" | A | video@31:24<br>video@31:26 |
| 31:28-31:37 | Tab in, N, rename BSDF -> Shader | output "Shader" | A | video@31:34<br>video@31:36 |
| 31:38-31:54 | Mapping Scale -> socket; Vector -> Float; default 1; Tab out; instance Scale 1 | input "Scale" | A | crop frosted_interface_panels.png#0 |
| 31:54-32:08 | Tab in; Glass Color, HSV Value, Glass IOR -> sockets | 3 inputs | A | video@32:01<br>video@32:05 |
| 32:07-32:19 | rename to Glass Color / Glass Roughness / Glass IOR | white / 1.0 (0..2) / 1.5 (0..1000) | A | crop frosted_interface_panels.png#1<br>crop frosted_interface_panels.png#2<br>crop frosted_interface_panels.png#3 |
| 32:19-32:28 | Noise Scale, Detail, Roughness -> sockets | 3 inputs | A | video@32:22<br>video@32:25 |
| 32:28-32:44 | rename Scale -> Noise Roughness Scale -> Frosted Scale; Detail -> Frosted Detail 1; Roughness -> Frosted Detail 2 | 20 (-1000..1000) / 15 (0..15) / 1.0 | A | crop frosted_interface_panels.png#4<br>crop frosted_interface_panels.png#5 |
| 32:44-32:54 | rename Glass Roughness -> Frosted Amount | Float 1.0, 0..2 | A | crop frosted_interface_panels.png#6 |
| 32:58 | group interior zoomed out | all 7 group-input links confirmed | A | t3258_frosted_group_interior_links.png<br>crop t3258_frosted_group_interior.png |
| 32:58-33:02 | N closes panel, Tab out | - | A | video@33:00 |
| 33:04-33:18 | demo Frosted Amount 2, Glass IOR 0, Frosted Detail 2 0.99, reset | final instance values = defaults | A | t3303_frosted_final_group_node.png<br>crop t3303_frosted_group_node.png<br>video@33:11<br>video@33:13<br>video@33:15 |
| 33:18-33:22 | Alt+H unhides all panes | all six panes visible | A | t3323_closing_viewport_all_panes.png<br>crop t3323_viewport_panes.png |
| 33:24-33:30 | closing: product render of the six panes | reference look | A | t3326_closing_final_render_six_panes.png<br>t0004_intro_final_render_six_panes.png<br>crop t3326_render_six_panes.png<br>crop t0004_render_bottom_row.png |

## Totals

102 logged operations; final graphs: Wavy 7 nodes / 12 links in the group, Blobby 10 / 20, Frosted 8 / 13, plus one group node -> Material Output link per material.
