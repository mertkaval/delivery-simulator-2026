# Operation log, segment b (26:10-40:41) + intro glance

Video `30vbbpy9zwg`. Classes: A frame, B narration, C inference, D unresolved. Frames are under `evidence/b/frames/`.

| t | action | visible result | class | frame |
|---|---|---|---|---|
| 0:01 | Intro: finished material shown in the rendered camera view | icosphere covered in mossy grey cobblestones with dark dirt joints; Cycles viewport, 'Rendering Done' | A | t0001_intro_final_render.png |
| 0:09-0:11 | Intro: product node group 'Cobblestone Ground' panels expanded | 34 controls (Material Scale and 5 panels) with their defaults (product variant) | A | t0009_product_interface_lower.png, t0011_product_interface_upper.png |
| 0:25-3:36 | Customizable Node chapter: each control dragged to show its effect, then reset | effect descriptions used in the interface table (narration) | B | - |
| 26:10 | State at segment start: Displacement node values (set at 26:01-26:07) | Object Space, Height linked, Midlevel 0.000, Scale 0.020; Mix Rocks & Dirt ColorRamp white stop Pos 0.030 | A | t2610_displacement_midlevel0_scale002.png |
| 26:16-26:22 | Box-select every node except Material Output, Ctrl+G (Make Group) | all frames/nodes outlined, group created | A | t2622_ctrlG_make_group.png |
| 26:23-26:26 | Tab out of the group, move the group node | group node 'NodeGroup' with outputs Shader, Displacement wired to Material Output | A | t2628_paste_error_clipboard_empty.png |
| 26:28 | Ctrl+V into the group name field (first attempt) | Report: Error 'The internal clipboard is empty' (mistake, retried) | A | t2628_paste_error_clipboard_empty.png |
| 26:30-26:32 | Paste the material name into the group name; widen the node | node tree named 'Cobblestone Ground'; Shader -> Surface, Displacement -> Displacement | A | t2632_group_node_cobblestone_ground.png |
| 26:33-26:42 | Tab into the group; view the Mapping frame | Texture Coordinate Object -> Mapping (Point, Loc 0, Rot 0, Scale 1,1,1); distortion Noise 3D fBM 2/7/0.5/2/0; Linear Light Factor 0.200, A <- Mapping, B <- Noise Color | A | t2642_mapping_and_distortion_values.png |
| 26:46 | Drag Group Input's empty socket to Mapping Scale | new input 'Scale' linked to Mapping Scale | A | t2646_groupinput_scale_to_mapping.png |
| 26:49-26:51 | N opens the sidebar on the Options tab (material settings visible) | Displacement 'Displacement and Bump', Emission Sampling Auto, Transparent Shadows on, Bump Map Correction on, Volume Multiple Importance / Linear | A | t2651_material_displacement_and_bump.png |
| 26:53-27:02 | Group tab, select 'Scale' item | Vector, subtype XYZ, Dimensions 3, default 1,1,1, min -inf, max inf | A | t2658_scale_socket_vector_xyz.png |
| 27:04-27:08 | Change socket type Vector -> Float, type default 1 | Float, subtype None, default 0.000 then 1.000 | A | t2704_socket_type_menu_float.png |
| 27:10-27:17 | Outside the group set the node's Scale value to 1; back inside | Float None 1.000, -inf..inf | A | t2717_material_scale_float_default1.png |
| 27:20-27:42 | Drag the Group Input to Cobblestone Distortion; link noise Scale, Detail, Roughness and Linear Light Factor to new sockets | new inputs Scale, Detail, Roughness, Factor | A | t2742_distortion_all_four_linked.png |
| 27:43-27:59 | + > Panel, name 'Rock Distortion'; move Factor, Roughness, Detail, Scale into it | panel Rock Distortion | A | t2744_add_panel_menu.png |
| 28:06-28:10 | Rename first Scale -> 'Material Scale' | Material Scale stays at the top level | A | t2816_distortion_detail1_props.png |
| 28:12-28:16 | Rename Detail -> 'Distortion Detail 1' | Float None 7.000, 0..15 | A | t2816_distortion_detail1_props.png |
| 28:19-28:24 | Rename Roughness -> 'Distortion Detail 2' | Float Factor 0.500, 0..1 | A | t2824_distortion_detail2_props.png |
| 28:26-28:30 | Rename Factor -> 'Distortion Strength' | Float Factor 0.200, 0..1 | A | t2830_distortion_strength_props.png |
| 28:31-28:36 | Rename Scale -> 'Distortion Scale' | Float None 2.000, -1000..1000; panel order Scale, Detail 1, Detail 2, Strength | A | t2836_distortion_scale_props.png |
| 28:40-28:55 | Click outside the panel, + > Panel 'Dirt & Moss', drag to the bottom | second top-level panel | B | - |
| 28:57-29:17 | Move the first Group Input into the Mapping frame, Ctrl+H; Shift+D duplicate, F (out of frame), Ctrl+H | UI only: one Group Input copy per frame | B | - |
| 29:21-29:42 | In Dirt Moss Texture: noise Detail and Roughness -> new sockets, renamed 'Dirt Moss Detail 1/2' | Detail 1: Float None 9.000 0..15; Detail 2: Factor 0.500 0..1 | A | t2932_dirt_moss_detail1_props.png, t3158_dirt_moss_detail2_props.png |
| 29:52-29:56 | B: render border in the camera view to preview the dirt | viewport preview region (UI only) | B | - |
| 29:57-30:00 | Dirt moss noise Scale dragged between 25 and 28 (demo) and back to 25.000 | temporary change, restored before linking | A | t2959_dirt_moss_noise_scale_drag.png |
| 30:00-30:13 | Noise Scale -> new socket, renamed 'Dirt Moss Scale', moved to the top of Dirt & Moss | Float None 25.000, -1000..1000 | A | t3006_dirt_moss_scale_props.png |
| 30:14-30:33 | HSV (moss) Value -> new socket, renamed 'Dirt Moss Visibility', placed under the details | Float None 1.000, 0..2; noise Factor feeds HSV Color | A | t3019_dirt_moss_noise_factor_to_hsv.png, t3026_dirt_moss_visibility_props.png |
| 30:42-30:58 | Dirt colour Mix A and B -> new sockets, renamed 'Dirt Color 1' / 'Dirt Color 2' | Color sockets, defaults = the mix colours | A | t3054_dirt_color_A_B_linked.png, t3116_dirt_color1_props.png, t3140_dirt_color2_props.png |
| 30:58-31:08 | Moss Mix B -> new socket, renamed 'Dirt Moss Color' | Color socket, dark olive default | A | t3108_dirt_moss_color_props.png |
| 31:12-31:19 | Move the three colours into Dirt & Moss, Dirt Moss Scale at the top | panel order updated | A | t3116_dirt_color1_props.png |
| 31:20-31:38 | Dirt noise Scale -> new socket 'Dirt Scale', moved to the very top | Float None 20.000, -1000..1000 | A | t3146_dirt_noise_scale_detail_links.png, t3218_dirt_scale_props.png |
| 31:39-31:58 | Dirt noise Detail and Roughness -> 'Dirt Detail 1' / 'Dirt Detail 2', placed above the moss details | Detail 1: None 10.000 0..15; Detail 2: Factor 0.550 0..1 | A | t3146_dirt_noise_scale_detail_links.png, t3156_dirt_detail2_props.png, t4004_final_dirt_and_moss_order.png |
| 32:02-32:17 | Roughness HSV Value dragged to 0 (demo), reset to 1, linked; renamed 'Dirt Roughness', placed under the colours | Float None 1.000, 0..2 | A | t3210_dirt_roughness_props.png |
| 32:18-32:26 | Bump (0.020) Strength dragged to 0.841 (demo), reset, linked; 'Dirt Bump Strength' | Float Factor 1.000, 0..1 | A | t3236_dirt_bumps_wiring.png, t3250_dirt_moss_panel_order.png |
| 32:29-32:36 | Bump (0.005) Strength linked; 'Dirt Moss Bump Strength' | Float Factor 1.000, 0..1 | A | t3236_dirt_moss_bump_strength_props.png |
| 32:36 | Dirt Material and Dirt Moss Texture node values visible (state, made in segment a) | ramps 0.155/0.553, 0.000/1.000, 0.000/0.314, 0.469/1.000; HSV 0.5/1/1/1; Bumps 0.020 and 0.005, Filter Width 0.100 | A | t3236_dirt_bumps_wiring.png |
| 32:37-32:59 | Both bump strengths moved to the bottom of Dirt & Moss; Ctrl+H; panel collapsed; Group Input duplicated | final Dirt & Moss order reached | A | t3250_dirt_moss_panel_order.png |
| 33:05-33:30 | Group Input dropped into Cobblestone Mask; Smooth F1 Voronoi Scale -> new socket, F1 Voronoi Scale -> same socket | both Voronoi Scale driven by one socket; Voronoi values readable | A | t3330_cobblestone_mask_voronoi_difference.png |
| 33:32-33:48 | Rename -> 'Cobblestone Scale'; + > Panel 'Cobblestone Chunks' at the bottom; scale moved in | Float None 7.000, -1000..1000, empty description | A | t3333_cobblestone_scale_props.png |
| 33:49-34:04 | Temporary Value node linked to both Voronoi Detail (0 -> 0.02 -> 1.11 -> 2.09) to demo cracks, then deleted | not part of the final graph | A | t3352_temp_value_node_detail.png |
| 34:06-34:23 | Both Voronoi Detail -> one socket, renamed 'Cobblestone Cracks', bottom of chunks | Float None 0.000, 0..15 | A | t3412_cobblestone_cracks_props.png |
| 34:24-34:30 | Difference Factor dragged 0.926 / 0.862 (demo), back to 1.0 | temporary change | A | t3426_mask_ramp_color_field.png |
| 34:26 | Cobblestone Mask ColorRamp visible: stop 0 at 0.000 selected, colour field grey | stop 0 #989898 (display), black stop very close to 0 | A | t3426_mask_ramp_color_field.png |
| 34:30-34:39 | Difference Factor -> new socket, renamed 'Cobblestone Visibility', bottom of chunks | Float Factor 1.000, 0..1 | A | t3433_cobblestone_visibility_props.png |
| 34:40-34:56 | Voronoi Randomness demo (Smooth F1 dragged to 0.537), temporary Value node to both Randomness, deleted | not part of the final graph | A | t3446_temp_value_node_randomness.png |
| 34:57-35:10 | Both Randomness -> one socket, renamed 'Cobblestone Alignment', bottom of chunks | Float Factor 1.000, 0..1, empty description | A | t3506_cobblestone_alignment_props.png |
| 35:10-35:34 | Smoothness demo; only the Smooth F1 Voronoi has it; Smoothness -> new socket, renamed 'Cobblestone Size' then 'Cobblestone Individual Size' | Float Factor 0.600, 0..1, empty description | A | t3528_individual_size_smoothness_link.png, t3636_rock_moss_scale_link_individual_size_props.png |
| 35:36-35:56 | Group Input duplicated and dragged to Mix Rocks & Dirt; Displacement Scale -> new socket 'Displacement Strength' | Float None 0.020, min 0, max 1000 | A | t3550_mix_rocks_dirt_displacement.png, t3556_displacement_strength_props.png |
| 35:50 | Mix Rocks & Dirt visible: ColorRamp (white stop 0.030), Mix Shader, Displacement, Group Output | mask ramp colour -> ramp Fac and Displacement Height (reroute); dirt BSDF -> Shader 1, rock/moss mix -> Shader 2 | A | t3550_mix_rocks_dirt_displacement.png |
| 35:59-36:14 | Displacement Strength put at the bottom of Cobblestone Chunks; Ctrl+H; Group Input left in the frame | chunks order: Scale, Cracks, Visibility, Alignment, Individual Size, Displacement Strength | A | t3612_cobblestone_chunks_order.png |
| 36:15-36:24 | Duplicate Group Input, drag down to the rocks; rock/moss Mix Shader visible | Mix Shader Fac <- moss mask ramp, Shader 1 <- rock BSDF, Shader 2 <- moss BSDF | A | t3622_rock_moss_mix_shader_inputs.png |
| 36:25-36:41 | Moss & Rock Mask noise Scale dragged to 19.7 (demo), back to 15, linked; renamed 'Rock Moss Scale' | Float None 15.000, -1000..1000 | A | t3638_rock_moss_scale_props.png |
| 36:41-36:56 | + > Panel 'Rocks and Moss' at the bottom; Rock Moss Scale moved in | fourth panel | A | t3638_rock_moss_scale_props.png |
| 36:56-37:09 | Mask HSV Value -> new socket, renamed 'Rock Moss Visibility' | Float None 1.000, 0..2; mask noise Factor feeds HSV Color | A | t3702_mask_noise_hsv_wiring.png, t3708_rock_moss_visibility_props.png |
| 37:15-37:22 | Group Input duplicated into Rock Moss Material; mask ramp visible | Moss & Rock Mask ramp black stop Pos 0.407 | A | t3720_moss_rock_mask_ramp.png |
| 37:22-37:36 | Moss BSDF Base Color and Roughness -> new sockets, renamed 'Rock Moss Color' / 'Rock Moss Roughness' | Color (dark green); Float Factor 0.650 0..1 | A | t3728_rock_moss_color_roughness_linked.png, t3732_rock_moss_color_props.png, t3824_rock_moss_roughness_props.png |
| 37:48-38:08 | Rock moss noise Detail and Roughness -> new sockets, renamed 'Rock Moss Detail 1' / 'Rock Moss Detail 2' | Detail 1: None 15.000 0..15; Detail 2: Factor 0.700 0..1; noise Factor -> Bump Height | A | t3756_rock_moss_noise_links.png, t3757_rock_moss_detail1_props.png, t3806_rock_moss_detail2_props.png |
| 38:10-38:21 | Moss Bump Strength -> new socket 'Rock Moss Bump Strength', bottom of Rocks and Moss | Float Factor 1.000, 0..1 | A | t3812_rock_moss_bump_link.png, t3820_rocks_and_moss_order.png |
| 38:26-38:46 | Group Input duplicated into Cobblestone Rock Material; rock Mix A/B -> new sockets 'Rock Color 1' / 'Rock Color 2' | Color sockets | A | t3836_rock_colors_link.png, t3842_rock_color1_props.png, t3910_rock_color2_props.png |
| 38:52-39:08 | + > Panel 'Cobblestone Rocks' at the bottom (Displacement output shown as the active item); colours moved in | output Displacement: Vector, None, Dimensions 3, default 0 | A | t3854_displacement_output_props.png |
| 39:11-39:20 | Rock BSDF Roughness -> new socket 'Rock Roughness', bottom | Float Factor 0.650, 0..1; rock bump chain 0.007 -> 0.015 visible | A | t3912_rock_material_wiring.png, t3914_rock_roughness_props.png |
| 39:21-39:42 | Rock noise Detail -> new socket, Voronoi Detail -> same socket; renamed 'Rock Detail' | Float None 10.000, 0..15 | A | t3936_rock_detail_props.png |
| 39:44-40:02 | Both rock Bump Strength -> one socket, renamed 'Rock Bump Strength', bottom of Cobblestone Rocks | Float Factor 1.000, 0..1 | A | t3958_rock_bump_strength_props.png |
| 40:04 | Dirt & Moss final order visible; Dirt Detail 1 props | Float None 10.000, 0..15 | A | t4004_final_dirt_and_moss_order.png |
| 40:06-40:10 | Deselect all, N closes the sidebar, zoom out: whole group graph | 9 frames, rock/moss Mix Shader and Group Output outside frames | A | t4008_cobblestone_mask_ramp.png, t4010_graph_overview.png |
| 40:11-40:12 | Tab out of the group; Ctrl+S | group node 'Cobblestone Ground': Material Scale 1.000 + 5 collapsed panels -> Material Output (All); status 'Saved "Tutorial 2.blend"', Blender 5.0.1 | A | t4012_final_group_node.png |
| 40:13-40:16 | Closing render in the camera view | viewport samples run to 10 ('Sample 5/10' at 40:14), 'Rendering Done' at 40:15 | A | t4014_viewport_sample_5of10.png, t4016_closing_render.png |
| 40:17-40:41 | Outro: asset browser / store pages / playlist | not part of the material | A | - |

Transcript anchors used for the B rows: 28:40-28:55 (new panel outside the existing one), 28:57-29:17 (Group Input moved into the Mapping frame, Ctrl+H, Shift+D, F), 29:52-29:56 (B for a render border), 0:25-3:36 (intro demo of every control).
