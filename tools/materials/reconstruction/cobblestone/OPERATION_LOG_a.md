# Cobblestone Ground: operation log, segment a (0:00-26:10)

Video `30vbbpy9zwg` (Ryan King Art, 2026-01-12). Times are video times (m:ss[.s]). Evidence frames were extracted with an accurate ffmpeg seek at the exact time in index.json (file names use the floor second t<mmss>). 1-fps review frames (work folder tmp/materials_video/30vbbpy9zwg_work_a/, not kept) sample t = N + 0.5 s (checked against exact grabs at 21:33). Narration times come from the auto-caption transcript (about +-1 s).

Classes: A observed in a frame, B narration only, C inference, D unresolved. Frames are in `evidence/a/frames/`, crops in `evidence/a/crops/`; 'review' = 1-fps / multi-fps review frames in the work folder (not kept).

| t | action | visible result | class | frame |
|---|---|---|---|---|
| 0:00-0:08 | Intro: the finished material on a sphere (camera view, Cycles rendered viewport + a large final render) | grey stones with moss patches, dark brown dirt joints with fine moss | A | `t0004_intro_final_render.png` |
| 0:09-0:16 | Product node group 'Cobblestone Ground' shown with every panel open; outputs Shader -> Surface, Displacement -> Displacement | 34 inputs: Material Scale + 5 panels (Rock Distortion 4, Dirt & Moss 11, Cobblestone Chunks 6, Rocks and Moss 7, Cobblestone Rocks 5) | A | `t0009_product_interface_lower.png`, `t0013_product_interface_upper.png`; crops `c_t0013_interface_upper.png`, `c_t0013_interface_middle.png`, `c_t0009_interface_lower.png`; review s0011-s0016 |
| 0:11-0:16 vs 0:33-1:01 | Order check of the Rock Distortion panel | intro: Detail 2, Detail 1, Scale, Strength; demo: Detail 1, Detail 2, Scale, Strength | A | `t0013_product_interface_upper.png`, `t0043_demo_rock_distortion_order.png`; crops `c_t0013_interface_upper.png`, `c_t0043_rock_distortion_order.png` |
| 0:20-0:25 | All panels collapsed | Material Scale + five closed panels | A | `t0025_demo_panels_collapsed.png` |
| 0:26-0:31 | Material Scale 1.000 -> 1.240 -> 0.600 -> 1.000 | whole pattern scales (stones larger/smaller) | A (values) / B (effect) | -; review s0027, s0029 |
| 0:31-0:37 | Rock Distortion opened; Distortion Detail 1 11.400 -> 1.100 -> 7.000 | more / less distorted stone outlines | A / B | -; review s0033, s0035 |
| 0:37-0:44 | Distortion Detail 2 0.706, 0.668, 0.714 -> 0.500 | edges of the stones change a lot | A / B | `t0043_demo_rock_distortion_order.png`; crops `c_t0043_rock_distortion_order.png`; review s0037-s0041 |
| 0:44-0:53 | Distortion Scale 6.500, 5.300, 2.700, 0.100 -> 2.000 | high: chunky, random stones; low: round, smooth | A / B | -; review s0045-s0051 |
| 0:53-1:02 | Distortion Strength 0.466, 0.000, 0.075, 0.341, 0.483 -> 0.200 | 0: smooth rounded stones; up: randomly shaped, chunky | A / B | -; review s0053-s0061 |
| 1:03-1:15 | Dirt & Moss opened, camera zoomed close to the joints; Dirt Moss Detail 1 3.200 -> 9.000; Dirt Moss Detail 2 0.000 -> 0.500 | finer / coarser moss on the dirt | A / B | `t0110_demo_closeup_dirt_moss.png`; review s0067-s0073 |
| 1:15-1:22 | Dirt Moss Visibility 2.000, 1.380 -> 1.000 | up: lots of moss on the dirt; down: no moss | A / B | -; review s0077, s0079 |
| 1:22-1:40 | Dirt Color 1 lightened to #8A7762 (HSV 0.088/0.291/0.541), Dirt Color 2 to #534232 (0.082/0.392/0.324), Dirt Moss Color to #858C40 (0.181/0.545/0.550); all restored | hue/saturation of the pickers equal the build colours (#332C24, #19140F, #232511) | A | -; review s0083, s0087, s0095 |
| 1:40-1:50 | Dirt Scale 23.800, Dirt Moss Scale 21.100, Dirt Roughness 2.000, Dirt Bump Strength 0.015, Moss Bump Strength 0.000; all restored | scale/roughness/bump of dirt and moss | A / B | `t0145_demo_dirt_and_moss_panel.png`; crops `c_t0145_dirt_and_moss_values.png`; review s0101-s0109 |
| 1:51-2:00 | Cobblestone Chunks opened; Cobblestone Scale 4.620, 8.210, 10.140 -> 7.000 | bigger / smaller stones | A / B | `t0153_demo_cobblestone_chunks_panel.png`; crops `c_t0153_chunks_values.png`; review s0115-s0119 |
| 2:00-2:17 | Cobblestone Cracks 0.780, 3.960, 0.780, 1.000 -> 0.000 | little cracks/chunks in every stone; too high looks wrong, ~1 recommended | A / B | -; review s0123-s0137 |
| 2:17-2:22 | Cobblestone Visibility 0.640, 0.927 -> 1.000 | stones sink back into the dirt | A / B | -; review s0137, s0139 |
| 2:22-2:29 | Cobblestone Alignment 0.000, 0.177 -> 1.000 | low: aligned, road-like rows; high: random | A / B | -; review s0143, s0147 |
| 2:29-2:37 | Cobblestone Size 0.558, 0.617, 0.226, 0.565 -> 0.600 | size of each stone (joint width) | A / B | -; review s0149-s0155 |
| 2:37-2:42 | Displacement Strength 0.110, 0.000, 0.070 -> 0.020 | stones pop out of the mesh | A / B | -; review s0157-s0161 |
| 2:43-2:58 | Rocks and Moss opened; Rock Moss Scale 16.500 -> 15.000; Rock Moss Color picker HSV 0.215/0.551/0.156 raised to V 0.442 for visibility | scale and colour of the moss on the stones | A / B | `t0251_demo_rock_moss_color_hsv.png`; crops `c_t0251_rock_moss_color_hsv.png`; review s0169-s0173 |
| 2:58-3:16 | Rock Moss Roughness 0.650; Detail 1 15.000; Detail 2 0.565 -> 0.704; Visibility 2.000, 1.990, 0.970, 0.510 -> 1.000; Bump Strength 1.000; colour restored | up: moss covers the stones; down: none | A / B | -; review s0179-s0195 |
| 3:17-3:36 | Cobblestone Rocks opened; Rock Color 1 HSV 0.324/0.028/0.209; Rock Color 2 made browner (0.084/0.789/0.162) then 0.031/0.120/0.162; Rock Roughness 0.417, Rock Detail 0.000, Rock Bump Strength 0.000; restored | grey or brownish stones; stone roughness/detail/bump | A / B | `t0321_demo_rock_color1_hsv.png`, `t0327_demo_rock_color2_hsv.png`; crops `c_t0321_rock_color1_hsv.png`, `c_t0327_rock_color2_hsv.png`; review s0199-s0213 |
| 4:05-4:20 | Add > Mesh > Ico Sphere; redo panel Subdivisions 6, Radius 1 m, Generate UVs, Align World | demo object 'Icosphere.001' 10,242 verts / 20,480 faces | A | `t0417_add_icosphere_subdiv6.png`; crops `c_t0417_add_icosphere.png` |
| 4:20 | Shade Smooth | smooth shading | B | - |
| 4:44-4:53 | S .5 Enter, then Ctrl+A > Apply > Scale | sphere radius 0.5 m, scale applied | A | `t0450_scale_0p5_typed.png`, `t0452_apply_scale_menu.png`; crops `c_t0450_scale_typed.png`, `c_t0452_apply_scale.png` |
| 4:54-5:15 | (prepared file, object 'Icosphere', 642 verts / 1,280 faces) Subdivision Surface: Catmull-Clark, Levels Viewport 0, Render 3, Optimal Display | render-time subdivision for displacement | A | `t0512_subdivision_modifier.png`; crops `c_t0512_subdivision.png` |
| 5:15-5:25 | Camera aimed at the sphere; Focal Length dragged 61..93 mm and released at 80 mm | Perspective, 80 mm, clip 0.1-1000 m | A / B (aim) | `t0524_camera_focal_80mm.png`; crops `c_t0524_focal_80.png` |
| 5:25-5:30 | Output: Resolution 2560 x 2560 px | aspect 1:1, Render Region on, 24 fps, PNG RGBA | A (Y partly hidden) / B | `t0528_output_resolution.png`; crops `c_t0528_output.png` |
| 5:31-5:48 | Sun (object 'Area'): Temperature on 6000 K, Strength 15; viewport set to rendered | bright, slightly yellow outdoor light; Angle 0.526 deg, Normalize on | A | `t0539_sun_light.png`; crops `c_t0539_sun.png` |
| 5:48-6:04 | Rim light: Area light 'Area.001', Color #FFEDE0, Power 300 W, Shape Disk, Size 1 m, placed behind the object | subtle rim light | A / B (placement) | `t0556_area_light_color.png`, `t0600_area_light_settings.png`; crops `c_t0556_area_color.png`, `c_t0600_area_settings.png` |
| 6:05-6:38 | World: fish_hoek_beach 1K HDR (Easy HDRI add-on); world deleted and re-created: Background Color <- Environment Texture fish_hoek_beach_1k.hdr | Strength 1, Linear Rec.709, Equirectangular | A | `t0638_world_hdri.png`; crops `c_t0638_world.png`; review s0366-s0398 |
| 6:39-6:44 | Render properties: Cycles, GPU Compute; Film > Transparent on | Film Exposure 1.00, Blackman-Harris 1.50 px; Motion Blur box on | A | `t0642_render_engine_film.png`; crops `c_t0642_render_film.png` |
| 6:45-6:54 | Colour management: View Filmic, Look Very High Contrast | Display sRGB, Exposure 0, Gamma 1 | A | `t0654_color_management.png`; crops `c_t0654_color_management.png` |
| 6:55-7:22 | Shading workspace, rendered viewport; new material renamed 'Cobblestone Ground'; Node Wrangler enabled in Preferences | empty material with Principled BSDF + Material Output | B (name A at 0:25, 26:12) | -; review s0416-s0442 |
| 7:34-7:47 | Noise Texture added and previewed (Ctrl+Shift+click); Ctrl+T adds Texture Coordinate + Mapping; Object -> Mapping Vector | object-space coordinates | A | `t0751_mapping_frame.png`; crops `c_t0751_mapping.png` |
| 7:49-7:57 | Texture Coordinate + Mapping framed (F), label 'Mapping' | frame 'Mapping' | A | `t0751_mapping_frame.png` |
| 8:00-8:10 | Dirt Noise: Scale 20, Detail 10, Roughness 0.55 | 3D fBM, Normalize on, Lacunarity 2, Distortion 0 | A | `t0810_dirt_noise_settings.png`; crops `c_t0810_dirt_noise.png` |
| 8:13-8:23 | Color Ramp after the noise (Noise Factor -> ramp); black stop dragged to 0.151, white stop to 0.553 | more contrast | A | `t0820_dirt_ramp_stop0_0p151.png`, `t0822_dirt_ramp_stop1_0p553.png`; crops `c_t0820_dirt_ramp_stop0.png`, `c_t0822_dirt_ramp_stop1.png`; review 4 fps 8:17-8:24 |
| 8:23-8:50 | Mix (Color) added: ramp Color -> Factor; A = #332C24, B = #19140F (hex typed) | two dark browns | A | `t0838_dirt_color_A_332C24.png`, `t0848_dirt_color_B_19140F.png`; crops `c_t0838_dirt_color_A.png`, `c_t0848_dirt_color_B.png` |
| 8:52-8:57 | Noise, ramp and Mix framed, label 'Dirt Material' | frame 'Dirt Material' | A | `t1210_dirt_material_overview.png` |
| 8:57-9:05 | Default Principled BSDF moved into the frame; Mix Result -> Base Color | dirt colour on the sphere | A | -; review s0545 |
| 9:05-9:23 | Color Ramp duplicated and reset (Backspace: black 0, white 1); Noise Factor -> ramp; ramp Color -> BSDF Roughness | roughness variation | A | -; review s0562 |
| 9:23-9:38 | Roughness ramp black stop colour #D2D2D2 | rougher dirt overall | A | `t0935_roughness_ramp_D2D2D2.png`; crops `c_t0935_rough_ramp_hex.png` |
| 9:38-9:52 | Hue/Saturation/Value dropped between roughness ramp and Roughness (Hue 0.5, Sat 1, Value 1, Fac 1) | one value to make the roughness lighter/darker | A | `t1210_dirt_material_overview.png`; crops `c_t1210_dirt_material.png`; review s0596 |
| 9:52-10:13 | Bump added: Noise Factor -> Height, Normal -> BSDF Normal; Distance 0.020 | subtle bumpy dirt | A | `t1013_dirt_bump_distance_0p02.png`; crops `c_t1013_dirt_bump.png` |
| 10:16-10:41 | Second Noise (dirt moss): Mapping -> Vector, previewed; Scale 25, Detail 9, Lacunarity 3 (higher lacunarity demo shows a dot pattern) | moss noise | A / B | `t1055_dirt_moss_hsv_inserted.png`; crops `c_t1055_dirt_moss_hsv.png`; review s0626-s0641 |
| 10:41-10:52 | Color Ramp after the noise; black stop dragged to 0.467 | white = where the moss is | A | `t1104_dirt_moss_texture_frame.png`; crops `c_t1104_dirt_moss_ramp.png`; review 4 fps 10:43-10:52 |
| 10:52-11:01 | Hue/Saturation/Value dropped between the noise and the ramp (Noise Factor -> HSV Color); Value demo up/down, left at 1.000 | more / less moss | A | `t1055_dirt_moss_hsv_inserted.png`, `t1104_dirt_moss_texture_frame.png`; crops `c_t1055_dirt_moss_socket.png`, `c_t1104_dirt_moss_ramp.png` |
| 11:02-11:10 | Noise, HSV and ramp framed, label 'Dirt Moss Texture' | frame 'Dirt Moss Texture' | A | `t1104_dirt_moss_texture_frame.png` |
| 11:10-11:29 | Mix duplicated onto the Mix -> Base Color link; dirt-moss ramp Color -> new Mix Factor; first Mix -> A; B temporary bright green | moss layer over the dirt | A | `t1128_dirt_moss_mix2.png`; crops `c_t1128_dirt_mix2.png` |
| 11:39-12:15 | Color Ramp dropped between the dirt-moss ramp and the new Mix Factor; white stop dragged 0.917 ... 0.098 ... 0.324 (black at 0) | sharper moss colour edge; bump keeps the softer ramp | A | `t1210_dirt_material_overview.png`; crops `c_t1210_dirt_material.png`; review s0710-s0735, 2 fps 11:50-12:16, 4 fps 12:08-12:20 |
| 12:02-12:03 | Demo: dirt-moss ramp white stop dragged (0.676, 0.641) and back to 1.000 | no change | A | -; review s0722, s0723 |
| 12:14-12:26 | Mix B (moss colour) = #232511 (hex typed) | subtle greenish-brown moss | A | `t1226_moss_color_232511.png`; crops `c_t1226_moss_color.png` |
| 12:33-12:50 | Bump duplicated after the first (first Bump Normal -> second Bump Normal -> BSDF Normal); dirt-moss ramp Color -> second Bump Height | moss pops out of the mesh | A | `t1249_moss_bump_links.png`; crops `c_t1249_moss_bump_links.png` |
| 12:52-13:03 | Second Bump Distance 0.005 | subtle moss bump | A | `t1258_moss_bump_distance_0p005.png`; crops `c_t1258_moss_bump_distance.png`; review 4 fps 12:59-13:06 |
| 13:08-13:24 | Third Noise (rock): Mapping -> Vector, previewed; Scale 20, Detail 10 | rock noise | A / B | `t1444_rock_noise_mix_bsdf_bump.png`; crops `c_t1444_rock_nodes.png` |
| 13:25-14:01 | Mix (Color): Noise Factor -> Factor; A = #343534, B = #292524 (hex typed) | two greys | A | `t1354_rock_color_A_343534.png`, `t1358_rock_color_B_292524.png`; crops `c_t1354_rock_color_A.png`, `c_t1358_rock_color_B.png` |
| 14:02-14:22 | New Principled BSDF: Mix Result -> Base Color; framed 'Cobblestone Rock Material'; Roughness 0.650 | rock shader | A | `t1444_rock_noise_mix_bsdf_bump.png`; crops `c_t1444_rock_nodes.png` |
| 14:22-14:39 | Bump: Noise Factor -> Height, Normal -> BSDF Normal; Distance 0.007 (narration '0.7') | bumpy rock | A | `t1444_rock_noise_mix_bsdf_bump.png`; crops `c_t1444_rock_noise_socket.png` |
| 14:46-15:01 | Voronoi Texture (Mapping -> Vector); Bump duplicated onto the Bump -> Normal link; Voronoi Distance -> new Bump Height | second bump layer | A | `t1540_rock_bump2_distance_0p015.png`; crops `c_t1540_rock_bump2.png` |
| 15:05-15:20 | Voronoi: Smooth F1, Scale 12, Detail 10 (Smoothness 1, Randomness 1) | detailed rock with small round chunks | A | `t1521_rock_voronoi_settings.png`; crops `c_t1521_rock_voronoi.png` |
| 15:35-15:41 | Second Bump Distance 0.015 | stronger rock detail | A | `t1540_rock_bump2_distance_0p015.png`; crops `c_t1540_rock_bump2.png` |
| 15:43-16:13 | New Principled BSDF and Noise (rock moss): Mapping -> Vector; Scale 17, Detail 15, Roughness 0.7 | moss noise | A | `t1651_rock_moss_noise_bump_bsdf.png`; crops `c_t1651_rock_moss_nodes.png` |
| 16:13-16:22 | Bump dropped between noise and BSDF Normal: Noise Factor -> Height | bump data | A | `t1651_rock_moss_noise_bump_bsdf.png` |
| 16:25-16:41 | Moss BSDF Base Color #222812 (hex), Roughness 0.650 | dark brownish green | A | `t1633_rock_moss_color_222812.png`, `t1640_rock_moss_roughness.png`; crops `c_t1633_rock_moss_color.png`, `c_t1640_rock_moss_roughness.png` |
| 16:43-16:53 | Moss Bump Distance 0.010 | detailed mossy bump | A | `t1651_rock_moss_noise_bump_bsdf.png`; crops `c_t1651_rock_moss_nodes.png` |
| 16:53-17:10 | Moss nodes framed, label 'Rock Moss Material'; frame dragged down | frame 'Rock Moss Material' | A | `t2612_full_graph_overview.png` |
| 17:20-17:48 | Noise + Color Ramp (moss/rock mask): Mapping -> Noise Vector, Noise Factor -> ramp; Scale 15, Detail 10, Roughness 0.8 | mask noise | A | `t1803_moss_rock_mask_noise_hsv.png`; crops `c_t1803_mask_noise_hsv.png` |
| 17:48-17:56 | Ramp stops dragged close together (about 0.37 / 0.63; 0.417 at 18:00) | moss here and there | A | -; review 4 fps 17:46-18:06 |
| 17:56-18:03 | Hue/Saturation/Value dropped between noise and ramp (Noise Factor -> HSV Color); Value demo 1.01-1.30, back to 1.000 | more / less moss | A | `t1803_moss_rock_mask_noise_hsv.png`; crops `c_t1803_mask_noise_socket.png` |
| 18:03-18:10 | Framed, label 'Moss & Rock Mask' | frame 'Moss & Rock Mask' | A | `t1853_mask_ramp_stop0_0p407.png` |
| 18:13-18:31 | Both BSDFs selected, Ctrl+0 (Node Wrangler) -> Mix Shader; mask ramp Color -> Fac; previewed | rock/moss mix | A | -; review 2 fps 18:06-18:52 |
| 18:32-18:41 | Shader inputs swapped: rock BSDF -> Shader 1, rock moss BSDF -> Shader 2 | moss in spots over the rock | A | `t1841_rock_moss_mix_shader_swapped.png`; crops `c_t1841_rock_moss_mix.png` |
| 18:42-18:53 | Mask ramp demo, final black stop 0.407, white stop 0.651 | subtle moss spots | A | `t1849_mask_ramp_stop1_0p651.png`, `t1853_mask_ramp_stop0_0p407.png`; crops `c_t1849_mask_ramp_stop1.png`, `c_t1853_mask_ramp_stop0.png`; review 2 fps 18:44-18:53 |
| 18:53-20:03 | Layout: rock groups dragged down, reroutes added with Shift+right-drag | no functional change | A | -; review s1133-s1203 |
| 20:06-20:16 | Voronoi Texture added and previewed; Mapping -> Vector (via reroute) | cells | A | `t2027_voronoi_smooth_f1.png` |
| 20:16-20:27 | Voronoi 1: Smooth F1, Scale 7, Smoothness 0.6 | Detail 0, Roughness 0.5, Lacunarity 2, Randomness 1, Euclidean, 3D | A | `t2027_voronoi_smooth_f1.png`; crops `c_t2027_voronoi_smooth_f1.png` |
| 20:27-20:42 | Ctrl+Shift+D duplicate (input link kept), reroute; Voronoi 2 feature F1 | hard cell borders | A | `t2042_voronoi_f1.png`; crops `c_t2042_voronoi_f1.png` |
| 20:42-21:00 | Mix Color 'Difference' (search 'difference'): Voronoi 1 Distance -> A, Voronoi 2 Distance -> B, Factor 1.000 | bright lines only at the cell borders, black elsewhere | A | `t2100_difference_mix.png`; crops `c_t2100_difference.png` |
| 21:16-21:24 | Framed, label 'Cobblestone Mask' | frame 'Cobblestone Mask' | A | `t2141_cell_ramp_stop1_0p035.png` |
| 21:24-21:42 | Color Ramp after Difference (Result -> Fac) inside the frame; stops flipped (white left, black right); black stop dragged 0.410 ... 0.048 -> 0.035 | inverted mask: stones light, joints black | A | `t2141_cell_ramp_stop1_0p035.png`; crops `c_t2141_cell_ramp_stop1.png`; review 4 fps 21:30.5-21:46 |
| 21:42-21:57 | White stop colour typed #999999 (HSV value 0.600) | smoother edges in bump/displacement | A | `t2156_cell_ramp_stop0_999999.png`; crops `c_t2156_cell_ramp_hex.png` |
| 22:10-22:30 | Noise Texture dropped on the Mapping -> Voronoi link (auto-insert); Scale 2, Detail 7 | far too distorted ('clouds') | A | `t2227_distortion_noise.png`; crops `c_t2227_distortion_noise.png` |
| 22:31-22:49 | Mix Color 'Linear Light' dropped after the noise; Mapping Vector -> A, Noise Color -> B; Result -> Voronoi vectors | mix of undistorted and distorted coordinates | A | `t2258_linear_light.png`; crops `c_t2258_linear_light.png` |
| 22:49-23:00 | Linear Light Factor dragged 0.145, 0.417, set 0.200 | cobblestones with slightly bumpy, distorted edges | A | `t2258_linear_light.png`; crops `c_t2258_linear_light.png` |
| 23:03-23:06 | Framed, label 'Cobblestone Distortion' | frame 'Cobblestone Distortion' | A | `t2612_full_graph_overview.png` |
| 23:27-23:42 | Mix Shader added: dirt BSDF -> Shader 1 (top), rock/moss Mix Shader -> Shader 2 (bottom); previewed | 50/50 blend | A | `t2340_final_mix_shader_links.png`; crops `c_t2340_final_mix.png` |
| 23:44-23:52 | Cobblestone Mask ramp Color -> Mix Shader Fac | stones and dirt, transition far too smooth | A | `t2525_mix_rocks_dirt_frame.png` |
| 24:04-24:20 | Color Ramp dropped between the mask and the Mix Shader Fac; white stop dragged 0.568, 0.085, 0.033 -> 0.030 | sharp stone/dirt border | A | `t2420_mix_rocks_dirt_ramp_0p030.png`; crops `c_t2420_mix_rocks_dirt_ramp.png` |
| 24:24-24:32 | Framed, label 'Mix Rocks & Dirt'; reroute | frame 'Mix Rocks & Dirt' | A | `t2525_mix_rocks_dirt_frame.png` |
| 24:38-24:48 | Displacement node added (Midlevel 0.5, Scale 0.010, Object Space); Displacement -> Material Output Displacement | bump-only displacement | A | `t2525_mix_rocks_dirt_frame.png`; crops `c_t2525_mix_rocks_dirt.png` |
| 24:49-25:00 | Cobblestone Mask ramp Color -> Displacement Height (long wire) | stones look raised at the silhouette | A | `t2500_displacement_height_link.png`; crops `c_t2500_displacement_link.png` |
| 25:04-25:21 | Reroute added; Displacement moved into the 'Mix Rocks & Dirt' frame | layout only | A | `t2525_mix_rocks_dirt_frame.png`; crops `c_t2525_mix_rocks_dirt.png`, `c_t2525_final_mix_sockets.png` |
| 25:26-25:42 | N panel > Options > Settings: Displacement 'Bump Only' -> 'Displacement and Bump' | true displacement | A | `t2542_material_displacement_and_bump.png`; crops `c_t2542_material_settings.png` |
| 25:44-26:00 | Displacement Scale drag demo 0.010, 0.000, 0.080, 0.070 (Midlevel 0.5) | dirt pushed into the stones at Midlevel 0.5 | A | -; review 2 fps 25:20-26:12 |
| 26:00-26:10 | Midlevel 0.000, Scale typed 0.020 | only the stones pop out of the mesh | A | `t2610_displacement_final.png`, `t2608_viewport_after_displacement.png`; crops `c_t2610_displacement.png` |
| 26:12 | Node editor zoomed out on the whole graph (outside the segment by 2 s; used to confirm the topology) | 9 frames, 38 nodes | A | `t2612_full_graph_overview.png`; crops `c_t2612_overview.png` |

## Temporary states, demos and mistakes (not part of the final graph)

- 4:05-4:53: the sphere added on camera is 'Icosphere.001' (Subdivisions 6, 10,242 verts); from 4:56 the prepared file's 'Icosphere' (642 verts) is used.
- 5:22-5:24: focal length drag demo (61, 69, 81, 93 mm), released at 80 mm.
- 6:12-6:21: the Easy-HDRI world is deleted and rebuilt by hand with the same HDRI.
- 9:00-11:16: Mix (dirt colour) Result went straight to Base Color until the moss Mix was dropped on that link.
- 10:13-12:37: the dirt Bump Normal went straight to the BSDF Normal until the moss Bump was chained after it.
- 10:31-10:38: dirt-moss noise lacunarity demo (higher values show a dot pattern), left at 3.0.
- 10:57-11:00, 17:58-18:03: HSV Value demos, both left at 1.000.
- 11:20-12:14: Mix B (moss colour) temporarily bright green for visibility; 11:47-12:15 contrast-ramp drag 0.917 ... 0.098 ... 0.324.
- 12:02-12:03: dirt-moss ramp white stop dragged and returned to 1.000.
- 14:30-14:33: rock bump distance narrated as '0.7'; the field shows 0.007.
- 17:50-18:00: moss/rock mask ramp first set near 0.37 / 0.63, then 0.417; final 0.407 / 0.651 after the 18:42-18:53 demo.
- 18:16-18:41: Ctrl+0 Mix Shader first had moss on input 1; inputs swapped (rock on 1, moss on 2).
- 21:32-21:42: Cobblestone Mask ramp stops dragged through 0.410, 0.387, 0.085, 0.048 before the final 0.035; stop 0 white then #999999.
- 22:18-22:30: distortion noise inserted without the Linear Light (cells look like clouds) until 22:38.
- 22:50-22:56: Linear Light factor 0.145, 0.417 before 0.200.
- 23:46-24:04: mask fed the Mix Shader Fac directly (too smooth) until the 0-0.03 ramp was inserted.
- 24:12-24:20: Mix Rocks & Dirt ramp white stop dragged 0.568, 0.085, 0.033 before 0.030.
- 24:44-25:42: Displacement plugged in while the material was still 'Bump Only'; 25:46-26:00 Scale drag 0.010/0.000/0.080/0.070 at Midlevel 0.5 (dirt pushed into the rocks); final Midlevel 0.000, Scale 0.020.
- Reroutes (19:12-20:03, 20:33, 24:30, 25:05) only tidy wires.
