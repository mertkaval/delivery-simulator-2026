# Cobblestone Ground: graph specification, segment b (26:10-40:41)

Video `30vbbpy9zwg` *Procedural Cobblestone Ground Material (Blender Tutorial)*, Ryan King Art, 2026-01-12, 40:41. Segment b covers the **Node Group** chapter (26:10-40:12) and the closing; the intro (0:00-3:36) was reviewed to match the exposed controls. The tutorial is recorded in **Blender 5.0.1** (status bar).

Evidence classes: **A** observed in a frame, **B** narration only, **C** our inference or pixel measurement, **D** unresolved. Frames and crops: `evidence/b/` (index: `evidence/b/index.json`). Times are video times; frame names use the floor second.

Machine-readable version: `GRAPH_SPEC_b.json` (same data). Operation log: `OPERATION_LOG_b.md`. Open questions: `UNRESOLVED_b.md`. Local decisions: `DECISIONS_b.md`.

## What happens in this segment

The finished material (built in 7:22-26:10) is wrapped into one node group and 36 controls are exposed. **No internal node, link or value is changed**: every group socket is created by dragging an internal node input onto the Group Input's empty socket, so each default/min/max/subtype is copied from that node input. Demo drags and two temporary Value nodes are undone. The internal graph below is therefore the complete final material.

- `26:16-26:22` Ctrl+G on every node except Material Output; the two links that crossed the selection became the group outputs 'Shader' (from the Mix Rocks & Dirt Mix Shader) and 'Displacement' (from the Displacement node). (A)
- `26:28-26:30` Node tree renamed 'Cobblestone Ground' (material name pasted; first paste failed with 'The internal clipboard is empty'). (A)
- `26:46-27:17` First input created from Mapping.Scale as a Vector (XYZ, 1,1,1), converted to Float (subtype None) with default 1.0; the group node's own value had to be set to 1 by hand. (A)
- `27:20-40:02` 35 more inputs created by dragging internal node inputs onto the Group Input's empty socket (default/min/max/subtype/description copied from the node socket); where two node inputs share a control the second one was dragged onto the existing socket (Cobblestone Scale, Cobblestone Cracks, Cobblestone Alignment, Rock Detail, Rock Bump Strength). (A)
- `27:43-38:58` Five panels: Rock Distortion, Dirt & Moss, Cobblestone Chunks, Rocks and Moss, Cobblestone Rocks (Material Scale stays outside panels). (A)
- `33:49-34:04 and 34:44-34:56` Temporary Value nodes for demos; deleted, not part of the result. (A)
- `29:57, 32:04, 32:20, 34:24, 34:42, 36:33` Demo drags (dirt moss noise scale, roughness HSV value, dirt bump strength, Difference factor, Voronoi randomness, mask noise scale); all socket defaults show the original values, so no internal value changed. (A)
- `28:57-40:06` Group Input duplicated into each frame and Ctrl+H used to hide unused sockets (8 copies, UI only). (A)
- `-` No node type, link or internal value was changed while grouping; the internal graph equals the material built in 7:22-26:10 (Displacement Midlevel 0 / Scale 0.02 set at 26:01-26:07). (A/C)

## Scene (as far as visible or narrated)

| item | value | class |
|---|---|---|
| object | Icosphere (mesh) in 'Collection'; viewport stats 642 verts / 1,280 faces / 1,280 tris | A |
| subdivisions | narration 'subdivisions up to six' (4:17) but stats 642/1,280 = Blender icosphere subdivisions 4 | D |
| size | scaled to 0.5 and applied (Ctrl+A) -> ~1 m diameter sphere (narration 4:45-4:53) | B |
| shading | Shade Smooth (4:20) | B |
| modifiers | Subdivision Surface, Levels Viewport 0, Render 3 (4:55-5:05) | B |
| camera | viewport in 'Camera Perspective'; camera aimed at the object, focal length 80 mm (5:23); resolution 2560x2560 (5:28) | A (view) / B (values) |
| lighting | Sun strength 15, temperature 6000 K (5:36-5:42); Area light shape Disk, 300 W, slightly yellow, behind the object as a rim light (5:50-6:02); World: Environment Texture 'fish_hoek_beach' 1K HDR from Poly Haven (6:07-6:38) | B |
| render_engine | Cycles | C |
| samples | viewport 10 ('Sample 5/10' at 40:14); final render samples not shown | A / D |
| film | Transparent (6:40) | B |
| color_management | View 'Filmic', Look 'Very High Contrast' (6:47-6:51) | B |
| displacement | material Displacement = 'Displacement and Bump' (true displacement + bump); Displacement node Object Space, Midlevel 0.000, Scale 0.020 (exposed as Displacement Strength) | A |
| texture_coordinates | Texture Coordinate 'Object' output (no object assigned) -> Mapping (Point) -> every texture vector, except the two cell Voronoi textures, which take the Linear Light result (Mapping vector distorted by a Noise texture) | A |
| mapping | Location 0,0,0 m; Rotation 0,0,0 deg; Scale <- Material Scale (default 1.0, uniform) | A |
| blender_version | 5.0.1 | A |
| units_note | Object space of a ~1 m sphere, so the tutorial scales are already close to metres: Voronoi scale 7 -> stones ~0.14 m, dirt noise 20, moss noises 15-25 | C |

## Material `Cobblestone Ground` (top level)

| setting (UI) | value | bpy hint | class | evidence |
|---|---|---|---|---|
| Name | Cobblestone Ground | material.name | A | 26:46 header, 40:12 |
| Settings > Pass Index | 0 | material.pass_index | A | 26:51 |
| Surface > Displacement | Displacement and Bump | material.displacement_method = 'BOTH' (C; read the enum at build time) | A | 26:51 |
| Surface > Emission Sampling | Auto | Cycles material setting (C) | A | 26:51 |
| Surface > Transparent Shadows | True | Cycles material setting (C) | A | 26:51 |
| Surface > Bump Map Correction | True | Cycles material setting, property name not verified (C) | A | 26:51 |
| Volume > Sampling | Multiple Importance | Cycles material setting (C) | A | 26:51 |
| Volume > Interpolation | Linear | Cycles material setting (C) | A | 26:51 |

Top-level nodes: group node `Cobblestone Ground` (ShaderNodeGroup, node tree `Cobblestone Ground`, Material Scale = 1.000 on the node, other inputs at their defaults) and `Material Output` (target All). Links: group **Shader -> Surface**, group **Displacement -> Displacement** (A, 26:32 and 40:12).

## Group interface (final order, 40:04-40:12)

Outputs first, then `Material Scale` outside any panel, then five panels: `Rock Distortion`, `Dirt & Moss`, `Cobblestone Chunks`, `Rocks and Moss`, `Cobblestone Rocks`. Visible effect = narration of the intro demo (0:25-3:36) unless a segment-b time is given.

| control | in/out | panel | socket type | subtype | default | min / max | internal destination | visible effect | class | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Shader | OUTPUT | - | NodeSocketShader | - | - | - | <- Mix Shader 'Mix Rocks & Dirt' (final_mix).Shader | final surface shader -> Material Output Surface | A | 26:32, 35:50, t2632_group_node_cobblestone_ground.png, t3550_mix_rocks_dirt_displacement.png |
| Displacement | OUTPUT | - | NodeSocketVector | NONE | (0.0, 0.0, 0.0) | - | <- Displacement node (displacement).Displacement | displacement vector -> Material Output Displacement | A | 38:54, t3854_displacement_output_props.png |
| Material Scale | INPUT | - | NodeSocketFloat | NONE | 1.0 | -inf / inf | mapping.Scale (float -> uniform vector) | scales the whole material (all textures share the Mapping node) | A | 26:46, 26:58, 27:04, 27:17, 28:08, t2646_groupinput_scale_to_mapping.png, t2658_scale_socket_vector_xyz.png, t2704_socket_type_menu_float.png, t2717_material_scale_float_default1.png |
| Distortion Scale | INPUT | Rock Distortion | NodeSocketFloat | NONE | 2.0 | -1000.0 / 1000.0 | dist_noise.Scale | size of the edge distortion: high = chunky/random stones, low = round/smooth (0:44) | A | 27:28, 28:36, t2742_distortion_all_four_linked.png, t2836_distortion_scale_props.png |
| Distortion Detail 1 | INPUT | Rock Distortion | NodeSocketFloat | NONE | 7.0 | 0.0 / 15.0 | dist_noise.Detail | more / less distorted stone edges (0:33) | A | 27:32, 28:16, t2816_distortion_detail1_props.png |
| Distortion Detail 2 | INPUT | Rock Distortion | NodeSocketFloat | FACTOR | 0.5 | 0.0 / 1.0 | dist_noise.Roughness | affects the edges of the stones a lot (0:37) | A | 27:36, 28:24, t2824_distortion_detail2_props.png |
| Distortion Strength | INPUT | Rock Distortion | NodeSocketFloat | FACTOR | 0.2 | 0.0 / 1.0 | dist_mix (Linear Light).Factor | 0 = smooth round stones, higher = randomly shaped, chunky (0:54) | A | 27:40, 28:30, t2830_distortion_strength_props.png |
| Dirt Scale | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 20.0 | -1000.0 / 1000.0 | dirt_noise.Scale | scale of the dirt (1:41) | A | 31:27, 32:18, t3146_dirt_noise_scale_detail_links.png, t3218_dirt_scale_props.png |
| Dirt Moss Scale | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 25.0 | -1000.0 / 1000.0 | dmoss_noise.Scale | scale of the moss on the dirt (1:43) | A | 30:00, 30:06, t2959_dirt_moss_noise_scale_drag.png, t3006_dirt_moss_scale_props.png |
| Dirt Color 1 | INPUT | Dirt & Moss | NodeSocketColor | - | #332C24 (narrated hex; UI swatch #312D24) | - | dirt_color_mix.A | first dirt colour (1:22) | B+A | 30:48, 31:16, t3054_dirt_color_A_B_linked.png, t3116_dirt_color1_props.png |
| Dirt Color 2 | INPUT | Dirt & Moss | NodeSocketColor | - | #19140F (narrated hex; UI swatch #18150E) | - | dirt_color_mix.B | second (darker) dirt colour (1:27) | B+A | 30:50, 31:40, t3054_dirt_color_A_B_linked.png, t3140_dirt_color2_props.png |
| Dirt Moss Color | INPUT | Dirt & Moss | NodeSocketColor | - | #232511 (narrated hex; UI swatch #232710) | - | dirt_moss_mix.B | colour of the moss on the dirt (1:32) | B+A | 31:01, 31:08, t3108_dirt_moss_color_props.png |
| Dirt Roughness | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 1.0 | 0.0 / 2.0 | dirt_rough_hsv.Value | more rough / more shiny dirt (32:04) | A | 32:07, 32:10, t3210_dirt_roughness_props.png |
| Dirt Detail 1 | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 10.0 | 0.0 / 15.0 | dirt_noise.Detail | dirt noise detail (31:39; not in the product file) | A | 31:40, 40:04, t3146_dirt_noise_scale_detail_links.png, t4004_final_dirt_and_moss_order.png |
| Dirt Detail 2 | INPUT | Dirt & Moss | NodeSocketFloat | FACTOR | 0.55 | 0.0 / 1.0 | dirt_noise.Roughness | dirt noise roughness (31:42; not in the product file) | A | 31:42, 31:56, t3156_dirt_detail2_props.png |
| Dirt Moss Detail 1 | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 9.0 | 0.0 / 15.0 | dmoss_noise.Detail | detail of the moss on the dirt (1:09) | A | 29:28, 29:32, t2932_dirt_moss_detail1_props.png |
| Dirt Moss Detail 2 | INPUT | Dirt & Moss | NodeSocketFloat | FACTOR | 0.5 | 0.0 / 1.0 | dmoss_noise.Roughness | second detail of the moss on the dirt (1:13) | A | 29:30, 31:58, t3158_dirt_moss_detail2_props.png |
| Dirt Moss Visibility | INPUT | Dirt & Moss | NodeSocketFloat | NONE | 1.0 | 0.0 / 2.0 | dmoss_hsv.Value | up = lots of moss on the dirt, down = none (1:15) | A | 30:19, 30:26, t3019_dirt_moss_noise_factor_to_hsv.png, t3026_dirt_moss_visibility_props.png |
| Dirt Bump Strength | INPUT | Dirt & Moss | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | dirt_bump.Strength | bump of the dirt (1:46) | A | 32:23, 32:50, t3236_dirt_bumps_wiring.png, t3250_dirt_moss_panel_order.png |
| Dirt Moss Bump Strength | INPUT | Dirt & Moss | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | dmoss_bump.Strength | bump of the moss on the dirt (1:48; 'Moss Bump Strength' in the product) | A | 32:31, 32:36, t3236_dirt_moss_bump_strength_props.png |
| Cobblestone Scale | INPUT | Cobblestone Chunks | NodeSocketFloat | NONE | 7.0 | -1000.0 / 1000.0 | cell_vor_smooth.Scale; cell_vor_f1.Scale | bigger / smaller cobblestones (1:55) | A | 33:26, 33:33, t3330_cobblestone_mask_voronoi_difference.png, t3333_cobblestone_scale_props.png |
| Cobblestone Cracks | INPUT | Cobblestone Chunks | NodeSocketFloat | NONE | 0.0 | 0.0 / 15.0 | cell_vor_smooth.Detail; cell_vor_f1.Detail | adds little cracks / chunks to the stones; ~1 recommended, high looks wrong (2:00) | A | 34:06, 34:12, t3352_temp_value_node_detail.png, t3412_cobblestone_cracks_props.png |
| Cobblestone Visibility | INPUT | Cobblestone Chunks | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | cell_diff (Difference).Factor | down = stones sink back into the dirt (2:17, 34:24) | A | 34:31, 34:33, t3433_cobblestone_visibility_props.png |
| Cobblestone Alignment | INPUT | Cobblestone Chunks | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | cell_vor_smooth.Randomness; cell_vor_f1.Randomness | Voronoi randomness: higher = more random layout, lower = more aligned, road-like rows (2:22, 34:51) | A | 34:58, 35:06, t3446_temp_value_node_randomness.png, t3506_cobblestone_alignment_props.png |
| Cobblestone Individual Size | INPUT | Cobblestone Chunks | NodeSocketFloat | FACTOR | 0.6 | 0.0 / 1.0 | cell_vor_smooth.Smoothness (Smooth F1 Voronoi only) | makes each stone bigger / smaller, i.e. wider or narrower dirt joints (2:31, 35:10); 'Cobblestone Size' in the product | A | 35:25, 35:30, 36:36, t3528_individual_size_smoothness_link.png, t3636_rock_moss_scale_link_individual_size_props.png |
| Displacement Strength | INPUT | Cobblestone Chunks | NodeSocketFloat | NONE | 0.02 | 0.0 / 1000.0 | displacement.Scale | how far the stones pop out of the mesh (2:37) | A | 35:53, 35:56, t3550_mix_rocks_dirt_displacement.png, t3556_displacement_strength_props.png |
| Rock Moss Scale | INPUT | Rocks and Moss | NodeSocketFloat | NONE | 15.0 | -1000.0 / 1000.0 | rmmask_noise.Scale (Moss & Rock Mask) | scale of the moss patches on the stones (2:49) | A | 36:34, 36:38, t3638_rock_moss_scale_props.png |
| Rock Moss Visibility | INPUT | Rocks and Moss | NodeSocketFloat | NONE | 1.0 | 0.0 / 2.0 | rmmask_hsv.Value | up = moss covers the stones, down = no moss (3:04) | A | 37:00, 37:08, t3702_mask_noise_hsv_wiring.png, t3708_rock_moss_visibility_props.png |
| Rock Moss Color | INPUT | Rocks and Moss | NodeSocketColor | - | #222812 (narrated hex; UI swatch #212B12) | - | rmoss_bsdf.Base Color | colour of the moss on the stones (2:51) | B+A | 37:26, 37:32, t3728_rock_moss_color_roughness_linked.png, t3732_rock_moss_color_props.png |
| Rock Moss Roughness | INPUT | Rocks and Moss | NodeSocketFloat | FACTOR | 0.65 | 0.0 / 1.0 | rmoss_bsdf.Roughness | roughness of the moss on the stones (2:58) | A | 37:28, 38:24, t3824_rock_moss_roughness_props.png |
| Rock Moss Detail 2 | INPUT | Rocks and Moss | NodeSocketFloat | FACTOR | 0.7 | 0.0 / 1.0 | rmoss_noise.Roughness (Rock Moss Material) | moss detail (3:00); product default 0.704 | A | 37:54, 38:06, t3806_rock_moss_detail2_props.png |
| Rock Moss Detail 1 | INPUT | Rocks and Moss | NodeSocketFloat | NONE | 15.0 | 0.0 / 15.0 | rmoss_noise.Detail (Rock Moss Material) | moss detail (3:00) | A | 37:52, 37:57, t3756_rock_moss_noise_links.png, t3757_rock_moss_detail1_props.png |
| Rock Moss Bump Strength | INPUT | Rocks and Moss | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | rmoss_bump.Strength | bump of the moss on the stones (3:13) | A | 38:12, 38:20, t3812_rock_moss_bump_link.png, t3820_rocks_and_moss_order.png |
| Rock Color 1 | INPUT | Cobblestone Rocks | NodeSocketColor | - | #343534 (narrated hex; UI swatch #343434) | - | rock_color_mix.A | first stone colour, greyish (3:21) | B+A | 38:36, 38:42, t3836_rock_colors_link.png, t3842_rock_color1_props.png |
| Rock Color 2 | INPUT | Cobblestone Rocks | NodeSocketColor | - | #292524 (narrated hex; UI swatch #282421) | - | rock_color_mix.B | second stone colour, brownish (3:24) | B+A | 38:38, 39:10, t3910_rock_color2_props.png |
| Rock Roughness | INPUT | Cobblestone Rocks | NodeSocketFloat | FACTOR | 0.65 | 0.0 / 1.0 | rock_bsdf.Roughness | roughness of the stones (3:29) | A | 39:13, 39:14, t3912_rock_material_wiring.png, t3914_rock_roughness_props.png |
| Rock Detail | INPUT | Cobblestone Rocks | NodeSocketFloat | NONE | 10.0 | 0.0 / 15.0 | rock_noise.Detail; rock_vor.Detail | detail of the stone surface (3:31) | A | 39:28, 39:36, t3936_rock_detail_props.png |
| Rock Bump Strength | INPUT | Cobblestone Rocks | NodeSocketFloat | FACTOR | 1.0 | 0.0 / 1.0 | rock_bump_noise.Strength; rock_bump_vor.Strength | bump strength of the stones (3:34) | A | 39:52, 39:58, t3958_rock_bump_strength_props.png |

Descriptions shown in the item properties are the tooltips copied from the source node sockets (truncated in the UI; see JSON `description_seen`). Cobblestone Scale, Cobblestone Alignment, Cobblestone Individual Size and the Displacement output have an empty description (A).

Colour defaults as linear RGBA (computed from the hex, C): Dirt Color 1 (0.033, 0.025, 0.018, 1.0); Dirt Color 2 (0.01, 0.007, 0.005, 1.0); Dirt Moss Color (0.017, 0.018, 0.006, 1.0); Rock Moss Color (0.016, 0.021, 0.006, 1.0); Rock Color 1 (0.034, 0.036, 0.034, 1.0); Rock Color 2 (0.022, 0.018, 0.018, 1.0).

## Node inventory (inside the group)

| node id | type (bpy idname) | label / frame | settings | input values (<- link) | class | evidence |
|---|---|---|---|---|---|---|
| group_input | NodeGroupInput | Group Input / (8 UI copies, see ui_instances) | - | - | A | 26:46, 40:10 |
| group_output | NodeGroupOutput | Group Output / (no frame) | is_active_output=True | Shader: <- link final_mix.Shader, Displacement: <- link displacement.Displacement | A | 35:50, 36:12 |
| tex_coord | ShaderNodeTexCoord | Texture Coordinate / Mapping | object=-, from_instancer=False | - | A | 26:42 |
| mapping | ShaderNodeMapping | Mapping / Mapping | vector_type=POINT | Vector: <- link tex_coord.Object, Location: (0.0, 0.0, 0.0), Rotation: (0.0, 0.0, 0.0), Scale: <- link Material Scale (was 1,1,1) | A | 26:42, 26:46 |
| dist_noise | ShaderNodeTexNoise | Noise Texture / Cobblestone Distortion | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 2.0 <- link Distortion Scale, Detail: 7.0 <- link Distortion Detail 1, Roughness: 0.5 <- link Distortion Detail 2, Lacunarity: 2.0, Distortion: 0.0 | A | 26:42, 27:42 |
| dist_mix | ShaderNodeMix | Linear Light / Cobblestone Distortion | data_type=RGBA, clamp_factor=True, clamp_result=False, blend_type=LINEAR_LIGHT | Factor: 0.2 <- link Distortion Strength, A (RGBA, inputs[6]): <- link mapping.Vector, B (RGBA, inputs[7]): <- link dist_noise.Color | A | 26:42, 27:42 |
| cell_vor_smooth | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Mask | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=EUCLIDEAN, normalize=False | Vector: <- link dist_mix.Result (via reroute), Scale: 7.0 <- link Cobblestone Scale, Detail: 0.0 <- link Cobblestone Cracks, Roughness: 0.5, Lacunarity: 2.0, Smoothness: 0.6 <- link Cobblestone Individual Size, Randomness: 1.0 <- link Cobblestone Alignment | A | 33:30, 35:28 |
| cell_vor_f1 | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Mask | voronoi_dimensions=3D, feature=F1, distance=EUCLIDEAN, normalize=False | Vector: <- link dist_mix.Result (via reroute), Scale: 7.0 <- link Cobblestone Scale, Detail: 0.0 <- link Cobblestone Cracks, Roughness: 0.5, Lacunarity: 2.0, Randomness: 1.0 <- link Cobblestone Alignment | A | 33:30 |
| cell_diff | ShaderNodeMix | Difference / Cobblestone Mask | data_type=RGBA, clamp_factor=True, clamp_result=False, blend_type=DIFFERENCE | Factor: 1.0 <- link Cobblestone Visibility, A (RGBA): <- link cell_vor_smooth.Distance, B (RGBA): <- link cell_vor_f1.Distance | A | 33:30, 34:31 |
| cell_ramp | ShaderNodeValToRGB | Color Ramp / Cobblestone Mask | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.0 #989898, [1] 0.02 #000000 | Fac: <- link cell_diff.Result | A/C/D | 34:26, 40:08 |
| dirt_noise | ShaderNodeTexNoise | Noise Texture / Dirt Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 20.0 <- link Dirt Scale, Detail: 10.0 <- link Dirt Detail 1, Roughness: 0.55 <- link Dirt Detail 2, Lacunarity: 2.0, Distortion: 0.0 | A | 30:44, 31:46 |
| dirt_color_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.155 #000000, [1] 0.553 #FFFFFF | Fac: <- link dirt_noise.Fac | A/C | 30:44, 32:36 |
| dirt_color_mix | ShaderNodeMix | Mix / Dirt Material | data_type=RGBA, clamp_factor=True, clamp_result=False, blend_type=MIX | Factor: <- link dirt_color_ramp.Color, A (RGBA): <- link Dirt Color 1, B (RGBA): <- link Dirt Color 2 | A | 30:44, 30:54 |
| dirt_rough_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.0 #D2D2D2, [1] 1.0 #FFFFFF | Fac: <- link dirt_noise.Fac | A/B/C | 32:36 |
| dirt_rough_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Dirt Material | - | Hue: 0.5, Saturation: 1.0, Value: 1.0 <- link Dirt Roughness, Fac: 1.0, Color: <- link dirt_rough_ramp.Color | A | 32:02, 32:07 |
| dmoss_sharp_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.0 #000000, [1] 0.314 #FFFFFF | Fac: <- link dmoss_ramp.Color | A/C | 32:36 |
| dirt_moss_mix | ShaderNodeMix | Mix / Dirt Material | data_type=RGBA, clamp_factor=True, clamp_result=False, blend_type=MIX | Factor: <- link dmoss_sharp_ramp.Color, A (RGBA): <- link dirt_color_mix.Result, B (RGBA): <- link Dirt Moss Color | A | 31:00, 32:36 |
| dirt_bump | ShaderNodeBump | Bump / Dirt Material | invert=False | Strength: 1.0 <- link Dirt Bump Strength, Distance: 0.02, Filter Width: 0.1, Height: <- link dirt_noise.Fac, Normal: (unlinked) | A | 32:23, 32:36 |
| dmoss_bump | ShaderNodeBump | Bump / Dirt Material | invert=False | Strength: 1.0 <- link Dirt Moss Bump Strength, Distance: 0.005, Filter Width: 0.1, Height: <- link dmoss_ramp.Color, Normal: <- link dirt_bump.Normal | A | 32:31, 32:36 |
| dirt_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Dirt Material | distribution=MULTI_GGX (default, C), subsurface_method=RANDOM_WALK (default, C) | Base Color: <- link dirt_moss_mix.Result, Metallic: 0.0 (C, overview frame too small), Roughness: <- link dirt_rough_hsv.Color, IOR: 1.5 (C default), Alpha: 1.0 (C default), Normal: <- link dmoss_bump.Normal | A/C | 31:00, 40:10 |
| dmoss_noise | ShaderNodeTexNoise | Noise Texture / Dirt Moss Texture | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 25.0 <- link Dirt Moss Scale, Detail: 9.0 <- link Dirt Moss Detail 1, Roughness: 0.5 <- link Dirt Moss Detail 2, Lacunarity: 3.0, Distortion: 0.0 | A | 29:59, 30:19 |
| dmoss_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Dirt Moss Texture | - | Hue: 0.5, Saturation: 1.0, Value: 1.0 <- link Dirt Moss Visibility, Fac: 1.0, Color: <- link dmoss_noise.Fac | A | 30:19 |
| dmoss_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Moss Texture | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.469 #000000, [1] 1.0 #FFFFFF | Fac: <- link dmoss_hsv.Color | A/C | 32:36 |
| rock_noise | ShaderNodeTexNoise | Noise Texture / Cobblestone Rock Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 20.0, Detail: 10.0 <- link Rock Detail, Roughness: 0.5, Lacunarity: 2.0, Distortion: 0.0 | A | 38:36, 39:36 |
| rock_color_mix | ShaderNodeMix | Mix / Cobblestone Rock Material | data_type=RGBA, clamp_factor=True, clamp_result=False, blend_type=MIX | Factor: <- link rock_noise.Fac, A (RGBA): <- link Rock Color 1, B (RGBA): <- link Rock Color 2 | A | 38:36, 39:36 |
| rock_vor | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Rock Material | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=EUCLIDEAN, normalize=False | Vector: <- link mapping.Vector, Scale: 12.0, Detail: 10.0 <- link Rock Detail, Roughness: 0.5, Lacunarity: 2.0, Smoothness: 1.0, Randomness: 1.0 | A | 36:26, 39:36 |
| rock_bump_noise | ShaderNodeBump | Bump / Cobblestone Rock Material | invert=False | Strength: 1.0 <- link Rock Bump Strength, Distance: 0.007, Filter Width: 0.1, Height: <- link rock_noise.Fac, Normal: (unlinked) | A | 38:36, 39:12 |
| rock_bump_vor | ShaderNodeBump | Bump / Cobblestone Rock Material | invert=False | Strength: 1.0 <- link Rock Bump Strength, Distance: 0.015, Filter Width: 0.1, Height: <- link rock_vor.Distance, Normal: <- link rock_bump_noise.Normal | A | 39:12 |
| rock_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Cobblestone Rock Material | - | Base Color: <- link rock_color_mix.Result, Metallic: 0.0, Roughness: 0.65 <- link Rock Roughness, IOR: 1.5, Alpha: 1.0, Normal: <- link rock_bump_vor.Normal | A | 39:12 |
| rmmask_noise | ShaderNodeTexNoise | Noise Texture / Moss & Rock Mask | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 15.0 <- link Rock Moss Scale, Detail: 10.0, Roughness: 0.8, Lacunarity: 2.0, Distortion: 0.0 | A | 36:30, 37:02 |
| rmmask_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Moss & Rock Mask | - | Hue: 0.5, Saturation: 1.0, Value: 1.0 <- link Rock Moss Visibility, Fac: 1.0, Color: <- link rmmask_noise.Fac | A | 37:02 |
| rmmask_ramp | ShaderNodeValToRGB | Color Ramp / Moss & Rock Mask | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.407 #000000, [1] 0.645 #FFFFFF | Fac: <- link rmmask_hsv.Color | A/C | 37:20 |
| rmoss_noise | ShaderNodeTexNoise | Noise Texture / Rock Moss Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 17.0, Detail: 15.0 <- link Rock Moss Detail 1, Roughness: 0.7 <- link Rock Moss Detail 2, Lacunarity: 2.0, Distortion: 0.0 | A | 37:50, 37:56 |
| rmoss_bump | ShaderNodeBump | Bump / Rock Moss Material | invert=False | Strength: 1.0 <- link Rock Moss Bump Strength, Distance: 0.01, Filter Width: 0.1, Height: <- link rmoss_noise.Fac, Normal: (unlinked) | A | 37:56, 38:12 |
| rmoss_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Rock Moss Material | - | Base Color: <- link Rock Moss Color, Metallic: 0.0, Roughness: 0.65 <- link Rock Moss Roughness, IOR: 1.5, Alpha: 1.0, Normal: <- link rmoss_bump.Normal | A | 37:28, 38:12 |
| rock_moss_mix | ShaderNodeMixShader | Mix Shader / (no frame) | - | Fac: <- link rmmask_ramp.Color, Shader (inputs[1]): <- link rock_bsdf.BSDF, Shader (inputs[2]): <- link rmoss_bsdf.BSDF | A | 36:22 |
| final_ramp | ShaderNodeValToRGB | Color Ramp / Mix Rocks & Dirt | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR; stops: [0] 0.0 #000000, [1] 0.03 #FFFFFF | Fac: <- link cell_ramp.Color (via reroute) | A/C | 26:10, 35:50 |
| final_mix | ShaderNodeMixShader | Mix Shader / Mix Rocks & Dirt | - | Fac: <- link final_ramp.Color, Shader (inputs[1]): <- link dirt_bsdf.BSDF, Shader (inputs[2]): <- link rock_moss_mix.Shader | A | 35:50 |
| displacement | ShaderNodeDisplacement | Displacement / Mix Rocks & Dirt | space=OBJECT | Height: <- link cell_ramp.Color (via reroute), Midlevel: 0.0, Scale: 0.02 <- link Displacement Strength, Normal: (unlinked) | A | 26:10, 35:50 |

Notes: `group_input`: The tutorial duplicates the Group Input into every frame (Shift+D, F, Ctrl+H to hide unused sockets). Functionally one Group Input node is equivalent. `cell_ramp`: Inverted ramp: stone interiors (difference ~0) -> grey 0.31 linear, joints -> black. Feeds both the dirt/rock mask ramp and the Displacement height. `dmoss_sharp_ramp`: Sharpens the moss mask for the colour only; the bump uses the softer dmoss_ramp (narration 11:59-12:12). `rock_bump_noise`: Narration (14:34) says 'a 0.7'; the field reads 0.007 (A wins).

## Colour ramps (all RGB / Linear)

| ramp | stop | position | colour | position class | colour class |
|---|---|---|---|---|---|
| cell_ramp | 0 | 0.0 | #989898 | A | A (UI field sample; narration '6 9' incomplete -> exact hex D) |
| cell_ramp | 1 | 0.02 | #000000 | C (gradient width measured on the bar at 34:26 and 40:08: about 0.015-0.025; exact D) | A |
| dirt_color_ramp | 0 | 0.155 | #000000 | C (measured from the bar; calibrated by stop 1: read 0.549 vs 0.553) | A |
| dirt_color_ramp | 1 | 0.553 | #FFFFFF | A | A |
| dirt_rough_ramp | 0 | 0.0 | #D2D2D2 | A | B (narration 9:32) + A (UI field #D1D1D1) |
| dirt_rough_ramp | 1 | 1.0 | #FFFFFF | C (marker at the right end) | C |
| dmoss_sharp_ramp | 0 | 0.0 | #000000 | A | A |
| dmoss_sharp_ramp | 1 | 0.314 | #FFFFFF | C (measured from the bar) | A |
| dmoss_ramp | 0 | 0.469 | #000000 | C (measured from the bar) | A |
| dmoss_ramp | 1 | 1.0 | #FFFFFF | A | A |
| rmmask_ramp | 0 | 0.407 | #000000 | A | A |
| rmmask_ramp | 1 | 0.645 | #FFFFFF | C (measured from the bar, calibrated with stop 0) | C |
| final_ramp | 0 | 0.0 | #000000 | C (marker at the left end) | A |
| final_ramp | 1 | 0.03 | #FFFFFF | A | A |

Measured positions (C) come from the stop markers' pixel positions along the ramp bar in 1440p frames; where a ramp shows one numeric stop, that stop calibrates the measurement (dirt colour ramp: measured 0.549 vs displayed 0.553). Expect about +-0.01.

## Connections (inside the group)

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 26:42 | A |
| Group Input | Material Scale | mapping | Scale | 26:46 | A |
| mapping | Vector | dist_noise | Vector | 26:42 | A |
| mapping | Vector | dist_mix | A (RGBA, inputs[6]) | 26:42 | A |
| dist_noise | Color | dist_mix | B (RGBA, inputs[7]) | 26:42 | A |
| Group Input | Distortion Scale | dist_noise | Scale | 27:28 | A |
| Group Input | Distortion Detail 1 | dist_noise | Detail | 27:32 | A |
| Group Input | Distortion Detail 2 | dist_noise | Roughness | 27:36 | A |
| Group Input | Distortion Strength | dist_mix | Factor (inputs[0]) | 27:40 | A |
| dist_mix | Result (RGBA, outputs[2]) | cell_vor_smooth | Vector | 33:30 | A |
| dist_mix | Result (RGBA, outputs[2]) | cell_vor_f1 | Vector | 33:30 | A |
| Group Input | Cobblestone Scale | cell_vor_smooth | Scale | 33:26 | A |
| Group Input | Cobblestone Scale | cell_vor_f1 | Scale | 33:29 | A |
| Group Input | Cobblestone Cracks | cell_vor_smooth | Detail | 34:06 | A |
| Group Input | Cobblestone Cracks | cell_vor_f1 | Detail | 34:09 | A |
| Group Input | Cobblestone Alignment | cell_vor_smooth | Randomness | 34:58 | A |
| Group Input | Cobblestone Alignment | cell_vor_f1 | Randomness | 35:00 | A |
| Group Input | Cobblestone Individual Size | cell_vor_smooth | Smoothness | 35:25 | A |
| cell_vor_smooth | Distance | cell_diff | A (RGBA, inputs[6]) | 33:30 | A |
| cell_vor_f1 | Distance | cell_diff | B (RGBA, inputs[7]) | 33:30 | A |
| Group Input | Cobblestone Visibility | cell_diff | Factor (inputs[0]) | 34:31 | A |
| cell_diff | Result (RGBA, outputs[2]) | cell_ramp | Fac | 34:26 | A |
| mapping | Vector | dirt_noise | Vector | 31:46 | A |
| Group Input | Dirt Scale | dirt_noise | Scale | 31:27 | A |
| Group Input | Dirt Detail 1 | dirt_noise | Detail | 31:40 | A |
| Group Input | Dirt Detail 2 | dirt_noise | Roughness | 31:42 | A |
| dirt_noise | Fac | dirt_color_ramp | Fac | 30:44 | A |
| dirt_noise | Fac | dirt_rough_ramp | Fac | 30:44 | A |
| dirt_noise | Fac | dirt_bump | Height | 32:36 | A |
| dirt_color_ramp | Color | dirt_color_mix | Factor (inputs[0]) | 30:44 | A |
| Group Input | Dirt Color 1 | dirt_color_mix | A (RGBA, inputs[6]) | 30:48 | A |
| Group Input | Dirt Color 2 | dirt_color_mix | B (RGBA, inputs[7]) | 30:50 | A |
| dirt_color_mix | Result (RGBA, outputs[2]) | dirt_moss_mix | A (RGBA, inputs[6]) | 31:00 | A |
| dmoss_sharp_ramp | Color | dirt_moss_mix | Factor (inputs[0]) | 32:36 | A |
| Group Input | Dirt Moss Color | dirt_moss_mix | B (RGBA, inputs[7]) | 31:01 | A |
| dirt_moss_mix | Result (RGBA, outputs[2]) | dirt_bsdf | Base Color | 31:00 | A |
| dirt_rough_ramp | Color | dirt_rough_hsv | Color | 32:02 | A |
| Group Input | Dirt Roughness | dirt_rough_hsv | Value | 32:07 | A |
| dirt_rough_hsv | Color | dirt_bsdf | Roughness | 31:00 | A |
| Group Input | Dirt Bump Strength | dirt_bump | Strength | 32:23 | A |
| dirt_bump | Normal | dmoss_bump | Normal | 32:36 | A |
| Group Input | Dirt Moss Bump Strength | dmoss_bump | Strength | 32:31 | A |
| dmoss_ramp | Color | dmoss_bump | Height | 32:36 | A |
| dmoss_bump | Normal | dirt_bsdf | Normal | 32:36 | A |
| mapping | Vector | dmoss_noise | Vector | 29:59 | A |
| Group Input | Dirt Moss Scale | dmoss_noise | Scale | 30:00 | A |
| Group Input | Dirt Moss Detail 1 | dmoss_noise | Detail | 29:28 | A |
| Group Input | Dirt Moss Detail 2 | dmoss_noise | Roughness | 29:30 | A |
| dmoss_noise | Fac | dmoss_hsv | Color | 30:19 | A |
| Group Input | Dirt Moss Visibility | dmoss_hsv | Value | 30:19 | A |
| dmoss_hsv | Color | dmoss_ramp | Fac | 32:36 | A |
| dmoss_ramp | Color | dmoss_sharp_ramp | Fac | 32:36 | A |
| mapping | Vector | rock_noise | Vector | 38:36 | A |
| mapping | Vector | rock_vor | Vector | 38:36 | A |
| Group Input | Rock Detail | rock_noise | Detail | 39:28 | A |
| Group Input | Rock Detail | rock_vor | Detail | 39:30 | A |
| rock_noise | Fac | rock_color_mix | Factor (inputs[0]) | 39:36 | A |
| rock_noise | Fac | rock_bump_noise | Height | 39:36 | A |
| Group Input | Rock Color 1 | rock_color_mix | A (RGBA, inputs[6]) | 38:36 | A |
| Group Input | Rock Color 2 | rock_color_mix | B (RGBA, inputs[7]) | 38:38 | A |
| rock_color_mix | Result (RGBA, outputs[2]) | rock_bsdf | Base Color | 39:12 | A |
| rock_vor | Distance | rock_bump_vor | Height | 39:12 | A |
| Group Input | Rock Bump Strength | rock_bump_noise | Strength | 39:52 | A |
| Group Input | Rock Bump Strength | rock_bump_vor | Strength | 39:54 | A |
| rock_bump_noise | Normal | rock_bump_vor | Normal | 39:12 | A |
| rock_bump_vor | Normal | rock_bsdf | Normal | 39:12 | A |
| Group Input | Rock Roughness | rock_bsdf | Roughness | 39:13 | A |
| mapping | Vector | rmmask_noise | Vector | 36:30 | A |
| Group Input | Rock Moss Scale | rmmask_noise | Scale | 36:34 | A |
| rmmask_noise | Fac | rmmask_hsv | Color | 37:02 | A |
| Group Input | Rock Moss Visibility | rmmask_hsv | Value | 37:00 | A |
| rmmask_hsv | Color | rmmask_ramp | Fac | 37:02 | A |
| rmmask_ramp | Color | rock_moss_mix | Fac | 36:22 | A |
| mapping | Vector | rmoss_noise | Vector | 37:50 | A |
| Group Input | Rock Moss Detail 1 | rmoss_noise | Detail | 37:52 | A |
| Group Input | Rock Moss Detail 2 | rmoss_noise | Roughness | 37:54 | A |
| rmoss_noise | Fac | rmoss_bump | Height | 37:56 | A |
| Group Input | Rock Moss Bump Strength | rmoss_bump | Strength | 38:12 | A |
| rmoss_bump | Normal | rmoss_bsdf | Normal | 38:12 | A |
| Group Input | Rock Moss Color | rmoss_bsdf | Base Color | 37:26 | A |
| Group Input | Rock Moss Roughness | rmoss_bsdf | Roughness | 37:28 | A |
| rock_bsdf | BSDF | rock_moss_mix | Shader (inputs[1]) | 36:22 | A |
| rmoss_bsdf | BSDF | rock_moss_mix | Shader (inputs[2]) | 36:22 | A |
| cell_ramp | Color | final_ramp | Fac | 35:50 | A |
| cell_ramp | Color | displacement | Height | 35:50 | A |
| final_ramp | Color | final_mix | Fac | 35:50 | A |
| dirt_bsdf | BSDF | final_mix | Shader (inputs[1]) | 35:50 | A |
| rock_moss_mix | Shader | final_mix | Shader (inputs[2]) | 35:50 | A |
| Group Input | Displacement Strength | displacement | Scale | 35:53 | A |
| final_mix | Shader | group_output | Shader | 35:50 | A |
| displacement | Displacement | group_output | Displacement | 35:50 | A |

Top level: `cobblestone_group.Shader -> material_output.Surface` (26:32, A); `cobblestone_group.Displacement -> material_output.Displacement` (26:32, A).

## Frames (NodeFrame labels, UI only)

| frame label | nodes |
|---|---|
| Mapping | tex_coord, mapping |
| Cobblestone Distortion | dist_noise, dist_mix |
| Cobblestone Mask | cell_vor_smooth, cell_vor_f1, cell_diff, cell_ramp |
| Dirt Material | dirt_noise, dirt_color_ramp, dirt_color_mix, dirt_rough_ramp, dirt_rough_hsv, dmoss_sharp_ramp, dirt_moss_mix, dirt_bump, dmoss_bump, dirt_bsdf |
| Dirt Moss Texture | dmoss_noise, dmoss_hsv, dmoss_ramp |
| Cobblestone Rock Material | rock_noise, rock_color_mix, rock_vor, rock_bump_noise, rock_bump_vor, rock_bsdf |
| Moss & Rock Mask | rmmask_noise, rmmask_hsv, rmmask_ramp |
| Rock Moss Material | rmoss_noise, rmoss_bump, rmoss_bsdf |
| Mix Rocks & Dirt | final_ramp, final_mix, displacement |

Outside frames: `rock_moss_mix` (Mix Shader), `group_output`, reroutes. The tutorial keeps one Group Input copy per frame (Ctrl+H hides unused sockets):

- Mapping: Material Scale, Distortion Scale, Distortion Detail 1, Distortion Detail 2, Distortion Strength (A)
- Dirt Moss Texture: Dirt Moss Scale, Dirt Moss Detail 1, Dirt Moss Detail 2, Dirt Moss Visibility (A)
- Dirt Material: Dirt Scale, Dirt Color 1, Dirt Color 2, Dirt Moss Color, Dirt Roughness, Dirt Detail 1, Dirt Detail 2, Dirt Bump Strength, Dirt Moss Bump Strength (C)
- Cobblestone Mask: Cobblestone Scale, Cobblestone Cracks, Cobblestone Visibility, Cobblestone Alignment, Cobblestone Individual Size (A)
- Mix Rocks & Dirt: Displacement Strength (A)
- Moss & Rock Mask: Rock Moss Scale, Rock Moss Visibility (A)
- Rock Moss Material: Rock Moss Color, Rock Moss Roughness, Rock Moss Detail 2, Rock Moss Detail 1, Rock Moss Bump Strength (A)
- Cobblestone Rock Material: Rock Color 1, Rock Color 2, Rock Roughness, Rock Detail, Rock Bump Strength (A)

## Diagram of the final group

```text
TexCoord.Object -> Mapping(Point; Scale <- Material Scale) = V

COBBLESTONE SHAPE
V -> Noise[3D fBM, S 2 <-DistScale, D 7 <-DistDetail1, R 0.5 <-DistDetail2].Color --B--+
V -----------------------------------------------------------------------------A--> Mix LINEAR_LIGHT (Fac 0.2 <- Distortion Strength) = P
P -> Voronoi SMOOTH_F1 [S 7, D 0, Smooth 0.6, Rand 1].Distance --A--+
P -> Voronoi F1        [S 7, D 0, Rand 1].Distance -----------B--> Mix DIFFERENCE (Fac 1 <- Cobblestone Visibility)
      (S <- Cobblestone Scale x2, D <- Cobblestone Cracks x2, Rand <- Cobblestone Alignment x2, Smooth <- Cobblestone Individual Size)
   -> ColorRamp [0.000 #989898 | ~0.02 black] = M         (grey stones, black joints)
M -> ColorRamp [0 black | 0.030 white] -> MixShader_final.Fac
M -> Displacement(Object, Midlevel 0, Scale 0.02 <- Displacement Strength).Height -> Group Output.Displacement

DIRT (MixShader_final.Shader 1)
V -> Noise[S 20 <-DirtScale, D 10 <-DirtDetail1, R 0.55 <-DirtDetail2].Fac
     .Fac -> ColorRamp [0.155 black | 0.553 white] -> Mix(A <- Dirt Color 1, B <- Dirt Color 2) --A--> Mix_moss
     .Fac -> ColorRamp [0 #D2D2D2 | 1 white] -> HSV(Value <- Dirt Roughness) -> BSDF_dirt.Roughness
     .Fac -> Bump(0.020, Strength <- Dirt Bump Strength).Normal -> Bump(0.005).Normal
V -> Noise[S 25 <-DirtMossScale, D 9 <-DirtMossDetail1, R 0.5 <-DirtMossDetail2, Lac 3].Fac
     -> HSV(Value <- Dirt Moss Visibility) -> ColorRamp [0.469 black | 1 white] = DM
DM -> ColorRamp [0 black | 0.314 white] -> Mix_moss.Fac;  Mix_moss.B <- Dirt Moss Color;  Mix_moss -> BSDF_dirt.Base Color
DM -> Bump(0.005, Strength <- Dirt Moss Bump Strength).Height -> BSDF_dirt.Normal

ROCK + MOSS (MixShader_final.Shader 2 = MixShader_rock)
V -> Noise[S 20, D 10 <-RockDetail, R 0.5].Fac -> Mix(A <- Rock Color 1, B <- Rock Color 2) -> BSDF_rock.Base Color
                                          .Fac -> Bump(0.007, Strength <- Rock Bump Strength).Normal --+
V -> Voronoi SMOOTH_F1[S 12, D 10 <-RockDetail, Smooth 1, Rand 1].Distance -> Bump(0.015, Strength <- Rock Bump Strength).Height
                                                                    Bump(0.015).Normal -> BSDF_rock.Normal (Roughness 0.65 <- Rock Roughness)
V -> Noise[S 15 <-RockMossScale, D 10, R 0.8].Fac -> HSV(Value <- Rock Moss Visibility) -> ColorRamp [0.407 black | ~0.645 white] -> MixShader_rock.Fac
V -> Noise[S 17, D 15 <-RockMossDetail1, R 0.7 <-RockMossDetail2].Fac -> Bump(0.010, Strength <- Rock Moss Bump Strength) -> BSDF_moss.Normal
BSDF_moss: Base Color <- Rock Moss Color, Roughness 0.65 <- Rock Moss Roughness
MixShader_rock: Shader 1 <- BSDF_rock, Shader 2 <- BSDF_moss
MixShader_final: Shader 1 <- BSDF_dirt, Shader 2 <- MixShader_rock -> Group Output.Shader
```

## Product file shown in the intro (0:09-0:11) vs the tutorial result

The intro demonstrates the purchasable file. Its controls match the tutorial except:

- product has no 'Dirt Detail 1' / 'Dirt Detail 2' (the tutorial exposes the dirt noise Detail and Roughness)
- 'Cobblestone Size' (product) = 'Cobblestone Individual Size' (tutorial)
- 'Moss Bump Strength' (product) = 'Dirt Moss Bump Strength' (tutorial)
- Rock Moss Detail 2 default 0.704 (product) vs 0.700 (tutorial)
- socket order inside Rock Distortion, Dirt & Moss and Rocks and Moss differs (see tables)

| panel | product controls in order (default) |
|---|---|
| (top) | Material Scale 1.0 |
| Rock Distortion | Distortion Detail 2 0.5, Distortion Detail 1 7.0, Distortion Scale 2.0, Distortion Strength 0.2 |
| Dirt & Moss | Dirt Moss Detail 1 9.0, Dirt Moss Detail 2 0.5, Dirt Moss Visibility 1.0, Dirt Color 1 #312D24 (swatch), Dirt Color 2 #18150E (swatch), Dirt Moss Color #232710 (swatch), Dirt Scale 20.0, Dirt Moss Scale 25.0, Dirt Roughness 1.0, Dirt Bump Strength 1.0, Moss Bump Strength 1.0 |
| Cobblestone Chunks | Cobblestone Scale 7.0, Cobblestone Cracks 0.0, Cobblestone Visibility 1.0, Cobblestone Alignment 1.0, Cobblestone Size 0.6, Displacement Strength 0.02 |
| Rocks and Moss | Rock Moss Scale 15.0, Rock Moss Color #222B12 (swatch), Rock Moss Roughness 0.65, Rock Moss Detail 1 15.0, Rock Moss Detail 2 0.704, Rock Moss Visibility 1.0, Rock Moss Bump Strength 1.0 |
| Cobblestone Rocks | Rock Color 1 #343434 (swatch), Rock Color 2 #282421 (swatch), Rock Roughness 0.65, Rock Detail 10.0, Rock Bump Strength 1.0 |

## Reference frames for visual comparison

| t | frame | what |
|---|---|---|
| 0:01 | `t0001_intro_final_render.png` | finished look (product file): rendered camera view (Cycles viewport) of the ~1 m icosphere, sun + disk rim light + fish_hoek_beach HDRI, Filmic Very High Contrast; moss on stones and dirt, displaced stones |
| 0:09 | `t0009_product_interface_lower.png` | product group: Cobblestone Chunks, Rocks and Moss, Cobblestone Rocks defaults |
| 0:11 | `t0011_product_interface_upper.png` | product group: Material Scale, Rock Distortion, Dirt & Moss defaults |
| 40:10 | `t4010_graph_overview.png` | zoomed-out final internal graph (9 frames) |
| 40:12 | `t4012_final_group_node.png` | final group node in the material with Material Output (All) |
| 40:16 | `t4016_closing_render.png` | closing render of the tutorial-built material, same camera, object and lighting as 0:01 |

## Notes for the builder

- Socket names are the UI labels. The Noise output and the ColorRamp / Hue-Saturation / Mix Shader factor inputs have the identifier 'Fac' (label 'Factor'); look sockets up by identifier or index, not by label.
- ShaderNodeMix in RGBA mode: Factor = inputs[0], A = inputs[6], B = inputs[7], Result = outputs[2].
- ShaderNodeMixShader: Fac = inputs[0], first Shader = inputs[1] (shown on top), second Shader = inputs[2].
- Colour defaults: hex values are Blender's gamma-corrected hex; use default_linear_rgba for socket default_value.
- Interface min -inf/inf for Material Scale: use -3.4028234663852886e38 / 3.4028234663852886e38.
- Bump nodes: set Distance explicitly (0.020 / 0.005 / 0.007 / 0.015 / 0.010) and Filter Width 0.1; the video shows the Filter Width input (Blender 5.0.1).
- The mapping of this spec onto the PM_ contract (D2-D5: Use UV / Tile Size, metres, 4D torus) is the builder's job; nothing here is adapted.
