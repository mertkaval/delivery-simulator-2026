# Asphalt reconstruction - operation log (segment `all`, 00:00-27:08)

Video `Eofg9SBcdBY` (Ryan King Art, 2022). Times are video time (mm:ss); windows cover the action and its settle time. Frames are under `tools/materials/reconstruction/asphalt/evidence/all/frames/`, crops under `tools/materials/reconstruction/asphalt/evidence/all/crops/`; the same events with crop bounds are in `tools/materials/reconstruction/asphalt/evidence/all/index.json`. Temporary states (previews, demonstrations, mutes) are logged and marked as such; the final graph is in `GRAPH_SPEC_all.md`.

| # | t | action | visible result | class | frame |
|---|---|---|---|---|---|
| 1 | 00:00-00:08 | Intro shows the finished render overlaid on the Blender UI | dark grey cracked/damaged asphalt sphere on black | A | `t0003_intro_final_render.png` |
| 2 | 00:38-00:47 | Shift+A > Icosphere, subdivided 'so that it's very nice and smooth' | smooth sphere; scene stats Verts 10,327 / Faces 20,545 / Tris 20,610, 4 objects | B | `t0240_texcoord_object_to_voronoi.png` |
| 3 | 00:48-00:51 | Camera added and pointed at the icosphere | camera visible beside the sphere | A | `t0058_rimlight_emission5.png` |
| 4 | 00:52-01:05 | Rim light: object 'Lighting.001' (mesh 'Plane.001') gets Emission, white, Strength 5 | long thin emissive strip; node editor Emission 5.000 | A | `t0058_rimlight_emission5.png` |
| 5 | 01:05-01:13 | Key light: object 'Lighting' (mesh 'Plane') gets Emission, white, Strength 100 | bright elliptical emitter; Emission 100.000 | A | `t0108_keylight_emission100.png` |
| 6 | 01:13-01:39 | World 'World.001': Background colour <- Environment Texture machine_shop_02_1k.hdr | Linear, Equirectangular, Single Image, Vector Default, Strength 1.000 | A | `t0120_world_hdri_machine_shop.png` |
| 7 | 00:03 / 01:08 | Render Properties visible | Cycles, Feature Set Supported, Device GPU Compute; Motion Blur on, Simplify/Freestyle off; Sampling and Color Management collapsed | A | `t0003_intro_final_render.png`, `t0108_keylight_emission100.png` |
| 8 | 01:41-01:52 | Node Wrangler add-on enabled in Preferences > Add-ons | 'Node: Node Wrangler' checked | A | `t0148_node_wrangler_prefs.png` |
| 9 | 01:54-02:00 | Sphere selected, New material, renamed 'Asphalt' | default Principled BSDF -> Material Output; breadcrumb Icosphere > Icosphere > Asphalt | A | `t0240_texcoord_object_to_voronoi.png` |
| 10 | 02:02-02:08 | Shift+A search 'Voronoi Texture', dropped | Voronoi 3D / F1 / Euclidean, Scale 5, Randomness 1 | A | `t0233_ctrlT_texcoord_mapping.png` |
| 11 | 02:10-02:20 | Ctrl+Shift+click (Node Wrangler) previews the Voronoi | temporary 'Viewer' node feeds the output (removed by the end) | A | `t0233_ctrlT_texcoord_mapping.png` |
| 12 | 02:22-02:28 | Ctrl+T (Node Wrangler) on the Voronoi | Texture Coordinate + Mapping added in front of the Voronoi | A | `t0233_ctrlT_texcoord_mapping.png` |
| 13 | 02:31-02:36 | Mapping node deleted (X) | Texture Coordinate and Voronoi only | A | `t0240_texcoord_object_to_voronoi.png` |
| 14 | 02:37-02:42 | Texture Coordinate Object -> Voronoi Vector | object-space placement | A | `t0240_texcoord_object_to_voronoi.png` |
| 15 | 02:48-02:57 | Voronoi feature F1 -> Smooth F1; Smoothness checked at 1.0 | Smooth F1, Smoothness 1.000 | A | `t0310_voronoi_smoothf1_minkowski.png` |
| 16 | 03:00-03:05 | Distance metric Euclidean -> Minkowski | Minkowski; Exponent socket appears | A | `t0310_voronoi_smoothf1_minkowski.png` |
| 17 | 03:05-03:10 | Exponent dragged to the maximum | Exponent 32.000 | A | `t0310_voronoi_smoothf1_minkowski.png` |
| 18 | 03:22-03:31 | Noise Texture dropped between Texture Coordinate and Voronoi | Object -> Noise Vector, Noise Color -> Voronoi Vector | A | `t0350_noise_18_15_06.png` |
| 19 | 03:37-03:49 | Noise Scale 18, Detail 15 (max), Roughness 0.6 | Noise 3D 18 / 15 / 0.6 / Distortion 0 | A | `t0350_noise_18_15_06.png` |
| 20 | 03:55-04:04 | Shift+A 'Mix RGB' dropped after the Noise | Mix Color -> Voronoi Vector | A | `t0450_linear_light_fac01.png` |
| 21 | 04:04-04:15 | Object -> Mix Color1; Noise Color -> Mix Color2 | two inputs wired | A | `t0450_linear_light_fac01.png` |
| 22 | 04:15-04:31 | Fac dragged between 1 and 0 to show the pattern sliding (temporary) | texture slides while dragging | B | - (narration) |
| 23 | 04:31-04:38 | Blend Mix -> Linear Light | header 'Linear Light'; Clamp off | A | `t0450_linear_light_fac01.png` |
| 24 | 04:46-04:49 | Fac set to 0.1 | Fac 0.100 | A | `t0450_linear_light_fac01.png` |
| 25 | 05:06-05:12 | Voronoi Scale 5 -> 10 | Scale 10.000 | A | `t0450_linear_light_fac01.png` |
| 26 | 05:25-05:38 | ColorRamp dropped after the Voronoi; Distance -> Fac; previewed | black-white ramp on the cells | A | `t0643_ramp_to_base_color.png` |
| 27 | 05:50-06:12 | Stop 0 colour -> very dark warm grey | caption + picker 'Hex: 1A1817' | A | `t0612_ramp_hex_1A1817.png` |
| 28 | 06:16-06:30 | Stop 1 colour -> dark grey | caption + picker 'Hex: 4D4D4D' | A | `t0628_ramp_hex_4D4D4D.png` |
| 29 | 06:32-06:37 | ColorRamp Color -> Principled Base Color; Principled previewed | asphalt-like grey cells | A | `t0643_ramp_to_base_color.png` |
| 30 | 06:46-07:05 | Box select, Ctrl+J, F2 rename 'Color' | frame 'Color' (Noise, Linear Light, Voronoi, ColorRamp); Texture Coordinate outside | A | `t1050_frames_color_cracks.png` |
| 31 | 07:15-07:24 | New Voronoi (cracks) added and previewed | default Voronoi | A | `t0735_cracks_voronoi_dte.png` |
| 32 | 07:28-07:34 | Feature -> Distance to Edge | cell-edge lines | A | `t0735_cracks_voronoi_dte.png` |
| 33 | 07:40-07:44 | Object -> Voronoi Vector (superseded by the noise next) | object-space cracks | A | `t0735_cracks_voronoi_dte.png` |
| 34 | 07:46-07:58 | Noise Texture placed before the Voronoi; Object -> Noise Vector; Noise Color -> Voronoi Vector (no mix) | wiggly cracks | A | `t0812_cracks_noise_25.png` |
| 35 | 08:00-08:09 | Noise Scale 2.5, Detail 15 | Noise 2.5 / 15 / 0.5 / 0 | A | `t0812_cracks_noise_25.png` |
| 36 | 08:15-08:18 | Nodes box-selected and moved down | layout only | B | - (narration) |
| 37 | 08:29-08:36 | Shift+D: cracks noise duplicated above (mask noise) | second Noise 2.5 / 15 / 0.5 | A | `t0856_reroute_color_frame.png` |
| 38 | 08:37-08:41 | Object -> mask noise Vector | wired | A | `t0856_reroute_color_frame.png` |
| 39 | 08:41-08:56 | Shift+right-drag across the two Color-frame Object wires | reroute merging Object->Noise Vector and Object->Color1, dragged into frame 'Color' | A | `t0856_reroute_color_frame.png` |
| 40 | 08:58-09:06 | Shift+right-drag across the two cracks Object wires | second reroute feeding both cracks noises | A | `t0904_reroute_cracks.png` |
| 41 | 09:18-09:26 | ColorRamp after the mask noise | mask Noise Fac -> Ramp Fac | A | `t0938_mask_ramp_0499.png` |
| 42 | 09:27-09:33 | Black stop dragged toward the centre | stop 0 Pos 0.499 | A | `t0938_mask_ramp_0499.png` |
| 43 | 09:41-09:52 | Ramp + cracks Voronoi selected, Ctrl+0 (Node Wrangler merge) | MixRGB 'Mix' added | A | `t1009_cracks_mix_links.png` |
| 44 | 09:54-10:02 | Ramp Color -> Mix Fac; Voronoi Distance -> Mix Color1 | rewired | A | `t1009_cracks_mix_links.png` |
| 45 | 10:02-10:06 | Mix Color2 set to white | picker BCBCBC -> BBBBBB -> 'Hex: FFFFFF' | A | `t1005_cracks_mix_color2_FFFFFF.png` |
| 46 | 10:10-10:18 | Ramp previewed to show where cracks are removed (temporary) | white = no cracks | B | - (narration) |
| 47 | 10:20-10:28 | Mask noise Scale 2.5 -> 4.5 | Scale 4.500 | A | `t1050_frames_color_cracks.png` |
| 48 | 10:34-10:51 | Box select, Ctrl+J, F2 rename 'Cracks' | frame 'Cracks' | A | `t1050_frames_color_cracks.png` |
| 49 | 10:58-11:04 | New Voronoi (damage / pebbles) added | default Voronoi | A | `t1140_pebbles_voronoi_4d_110.png` |
| 50 | 11:06-11:10 | Object -> Voronoi Vector; previewed (superseded by the warp below) | wired | A | `t1140_pebbles_voronoi_4d_110.png` |
| 51 | 11:12-11:18 | Feature -> Distance to Edge | edge lines | A | `t1140_pebbles_voronoi_4d_110.png` |
| 52 | 11:18-11:22 | Dimensions 3D -> 4D | W socket appears, W 0.000 | A | `t1140_pebbles_voronoi_4d_110.png` |
| 53 | 11:33-11:38 | Scale -> 110 | Scale 110.000 (small pebbles) | A | `t1140_pebbles_voronoi_4d_110.png` |
| 54 | 11:53-12:04 | Noise Texture dropped between Texture Coordinate and Voronoi | noise warp | A | `t1330_damage_linear_light_002.png` |
| 55 | 12:06-12:17 | Mix RGB dropped between Noise and Voronoi | Mix Color -> Voronoi Vector | A | `t1330_damage_linear_light_002.png` |
| 56 | 12:18-12:27 | Shift+right-drag on the Object wire | reroute (damage) | A | `t1330_damage_linear_light_002.png`, `t1412_damage_mask_noise_35.png` |
| 57 | 12:28-12:33 | Reroute -> Mix Color1 | wired | A | `t1330_damage_linear_light_002.png` |
| 58 | 12:33-12:38 | Noise Fac -> Mix Color2 (Fac, not Color) | wired | A | `t1330_damage_linear_light_002.png` |
| 59 | 12:40-12:59 | Noise Scale 20, Detail 15, Roughness 0.6 | Noise 20 / 15 / 0.6 / 0 | A | `t1330_damage_linear_light_002.png` |
| 60 | 13:01-13:09 | Blend -> Linear Light | header 'Linear Light' | A | `t1330_damage_linear_light_002.png` |
| 61 | 13:23-13:30 | Fac -> 0.02 | Fac 0.020 | A | `t1330_damage_linear_light_002.png` |
| 62 | 13:45-13:52 | Ctrl+Shift+D: noise duplicated keeping its input wire (damage mask noise); previewed | second noise fed by the damage reroute | A | `t1412_damage_mask_noise_35.png` |
| 63 | 14:02-14:12 | Mask noise Scale 3.5, Roughness 0.5 | Noise 3.5 / 15 / 0.5 / 0 | A | `t1412_damage_mask_noise_35.png` |
| 64 | 14:17-14:24 | ColorRamp after the mask noise | mask Noise Fac -> Ramp Fac | A | `t1456_damage_ramp_black_0343.png` |
| 65 | 14:26-14:57 | Both stops dragged together (amount demo, 'to about there and to about there') | stop 0 last legible 0.343 (14:56.5); jump cut ~14:57.1; then stop 1 0.442, stop 0 measures ~0.35 | A | `t1456_damage_ramp_black_0343.png`, `t1457_damage_ramp_after_cut.png` |
| 66 | 15:05-15:13 | Pebble Voronoi + ramp selected, Ctrl+0 | MixRGB added | A | `t1533_lighten.png` |
| 67 | 15:17-15:22 | Blend -> Lighten | header 'Lighten' | A | `t1533_lighten.png` |
| 68 | 15:23-15:30 | Voronoi Distance -> Color1; ramp Color -> Color2; Fac 1 | pebbles only in the black mask areas | A | `t1533_lighten.png` |
| 69 | 15:41-15:56 | Box select, Ctrl+J, F2 rename 'Damage' | frame 'Damage' | A | `t2632_final_graph_overview.png` |
| 70 | 16:04-16:10 | Frames box-selected and spread out | layout only | B | - (narration) |
| 71 | 16:11-16:21 | Base ColorRamp + cracks Mix selected, Ctrl+0 | MixRGB added | A | `t1648_darken_cracks.png` |
| 72 | 16:32-16:36 | Blend -> Darken | header 'Darken' | A | `t1648_darken_cracks.png` |
| 73 | 16:37-16:47 | Base ramp Color -> Color1; cracks Mix Color -> Color2; Fac 1 | cracks darken the base colour | A | `t1648_darken_cracks.png` |
| 74 | 16:52-17:08 | Demonstration: cracks mask black stop dragged (0.231 .. 0.548) | back at Pos 0.499 by 17:08 | A | `t1700_crack_mask_demo_moved.png`, `t1708_crack_mask_back_0499.png` |
| 75 | 17:15-17:21 | Shift+D: Darken duplicated, placed after the first | Darken #2 | A | `t1822_darken_to_base_color.png` |
| 76 | 17:23-17:29 | Lighten Color -> Darken #2 Color2; Darken #1 Color -> Darken #2 Color1 | damage joined | A | `t1822_darken_to_base_color.png` |
| 77 | 17:52-18:00 | ColorRamp dropped between Lighten and Darken #2 | Lighten -> Ramp Fac, Ramp Color -> Darken #2 Color2 | A | `t1811_damage_dark_ramp_0338.png` |
| 78 | 18:02-18:11 | Black stop dragged right | stop 0 Pos 0.338: darker damaged patches | A | `t1811_damage_dark_ramp_0338.png` |
| 79 | 18:17-18:24 | Darken #2 Color -> Principled Base Color; Principled previewed | final base colour | A | `t1822_darken_to_base_color.png` |
| 80 | 18:42-18:53 | New Noise Texture (bump) placed below the Damage frame | default noise | A | `t1946_bump_noise_60.png` |
| 81 | 18:55-19:02 | Object -> bump noise Vector (long wire) | wired | A | `t1946_bump_noise_60.png` |
| 82 | 19:05-19:15 | Shift+right-drag on that wire | reroute (bump) | A | `t2632_final_graph_overview.png` |
| 83 | 19:23-19:46 | Noise Scale 60, Detail 15, Roughness 0.4 | Noise 60 / 15 / 0.4 / 0 | A | `t1946_bump_noise_60.png` |
| 84 | 19:48-19:54 | Noise Fac -> Principled Normal (temporary, wrong data type) | shading artefacts | B | - (narration) |
| 85 | 20:20-20:33 | Bump dropped between noise and Normal: Fac -> Height, Bump Normal -> Principled Normal | bumpy surface | A | `t2045_bump1_01.png` |
| 86 | 20:39-20:44 | Bump Strength 1 -> 0.1 | Strength 0.100, Distance 1.000, Invert off | A | `t2045_bump1_01.png` |
| 87 | 20:51-20:56 | Color-frame Voronoi previewed | blotchy Smooth F1 cells on the sphere | A | `t2122_color_voronoi_to_bump2.png` |
| 88 | 20:58-21:10 | Shift+D: Bump duplicated after Bump #1 | Bump #1 Normal -> Bump #2 Normal, Bump #2 Normal -> Principled Normal | A | `t2128_wire_lands_bump2_height.png` |
| 89 | 21:18-21:30 | Wire pulled from the Color-frame Voronoi Distance 'way up here' down to Bump #2 Height | second bump layer (base cells) | A | `t2122_color_voronoi_to_bump2.png`, `t2124_color_voronoi_wire_drag.png`, `t2128_wire_lands_bump2_height.png` |
| 90 | 21:36-21:40 | Bump #2 Strength 0.2 | Strength 0.200 | A | `t2134_bump2_link.png` |
| 91 | 21:52-21:58 | Shift+D: Bump #3 after Bump #2 (Normal chained) | Bump #3 | A | `t2224_bump3_03.png` |
| 92 | 22:06-22:12 | Cracks Mix Color -> Bump #3 Height | cracks everywhere in the bump | A | `t2210_cracks_mix_to_bump3.png` |
| 93 | 22:14-22:20 | Bump #3 Strength 0.3 | Strength 0.300 | A | `t2224_bump3_03.png` |
| 94 | 22:23-22:34 | Bump #2 and Bump #1 muted (M) to judge Bump #3 (temporary) | greyed bumps; normal-preview colours | A | `t2230_bumps_muted.png` |
| 95 | 22:45-22:57 | ColorRamp dropped between cracks Mix and Bump #3 | Mix Color -> Ramp Fac, Ramp Color -> Bump #3 Height | A | `t2300_crack_bump_ramp_inserted.png` |
| 96 | 22:59-23:28 | White stop dragged toward black (0.899, 0.109, 0.042, 0.057, 0.083) | stop 1 Pos 0.094 (final): only thin crack lines remain | A | `t2327_crack_bump_ramp_0094.png` |
| 97 | 23:30-23:36 | Bump #2 and Bump #1 unmuted | all four bump layers active | A | `t2422_lighten_to_bump4.png` |
| 98 | 23:41-23:45 | Principled previewed again | full material | A | `t2422_lighten_to_bump4.png` |
| 99 | 23:58-24:04 | Two nodes moved for space | layout only | B | - (narration) |
| 100 | 24:04-24:12 | Shift+D: Bump #4 after Bump #3 (Normal chained, Bump #4 Normal -> Principled Normal) | Bump #4 | A | `t2422_lighten_to_bump4.png` |
| 101 | 24:18-24:27 | Lighten Color (damage) -> Bump #4 Height | damaged patches recessed | A | `t2422_lighten_to_bump4.png` |
| 102 | 24:36-24:40 | Bump #4 Strength 0.4 | Strength 0.400 | A | `t2444_bump4_04.png` |
| 103 | 24:46-25:20 | Ctrl+B viewport render region (close-up), later reset to the whole camera | viewport only; close-up shows pebbles, cracks and broken edges | A | `t2510_viewport_closeup_reference.png` |
| 104 | 25:26-25:39 | Wire from the Color-frame Voronoi Distance -> Principled Roughness | too shiny / wet look | A | `t2530_roughness_wire_from_color_voronoi.png`, `t2539_wire_into_roughness.png` |
| 105 | 25:47-25:55 | ColorRamp dropped into the Roughness wire | Voronoi Distance -> Ramp Fac, Ramp Color -> Roughness | A | `t2551_roughness_ramp_inserted.png` |
| 106 | 26:02-26:22 | Stop 0 colour raised to grey | caption + picker 'Hex: ABABAB' | A | `t2622_roughness_hex_ABABAB.png` |
| 107 | 26:26-26:29 | Stop 1 (Pos 1.000) colour opened | picker 'Hex: FFFFFF' (unchanged white) | A | `t2628_roughness_white_FFFFFF.png` |
| 108 | 26:30-26:35 | Zoom out: whole final graph visible | 3 frames, 2 Darken, 4 ramps outside frames, bump chain, Principled, Output; no Viewer node | A | `t2632_final_graph_overview.png` |
| 109 | 26:35-26:38 | Final render (F12) | Render Result, square, black background | A | `t2638_final_render.png` |
| 110 | 26:38-27:08 | Closing: store, material pack and playlist pages (no frame kept) | no material changes | B | - (narration) |

Temporary or superseded states (not in the final graph): Node Wrangler Viewer previews (throughout), the Mapping node (02:22-02:36), Object -> cracks/pebble Voronoi Vector (07:40, 11:06; replaced by the noise warps), Fac 0/1 sliding demo (04:15), cracks mask demo positions 0.231-0.548 (17:00-17:06), Noise Fac -> Principled Normal (19:48), muted Bump #1/#2 (22:23-23:36), crack bump ramp positions 0.899-0.083 (22:59-23:26), viewport render regions (24:46-25:20).
