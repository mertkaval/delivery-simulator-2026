# Cobblestone Ground: graph specification, segment a (0:00-26:10)

Video `30vbbpy9zwg` *Procedural Cobblestone Ground Material (Blender Tutorial)*, Ryan King Art, 2026-01-12, 40:41. Segment a covers the product demo of the customizable node (0:25-3:36), the scene setup (4:00-7:22) and the whole procedural build (7:22-26:10). The tutorial is recorded in **Blender 5.0.1** (status bar).

Evidence classes: **A** observed in a frame, **B** narration only, **C** our inference / computation / pixel measurement, **D** unresolved. Frames and crops: `evidence/a/` (index `evidence/a/index.json`). Times are video times (m:ss[.s]). Evidence frames were extracted with an accurate ffmpeg seek at the exact time in index.json (file names use the floor second t<mmss>). 1-fps review frames (work folder tmp/materials_video/30vbbpy9zwg_work_a/, not kept) sample t = N + 0.5 s (checked against exact grabs at 21:33). Narration times come from the auto-caption transcript (about +-1 s).

Machine-readable version: `GRAPH_SPEC_a.json` (same data). Operation log: `OPERATION_LOG_a.md`. Open questions: `UNRESOLVED_a.md`. The node group (Ctrl+G, exposed sockets, panels) is segment b (`GRAPH_SPEC_b.*`); node ids here match segment b's ids.

## Result in one paragraph

One material, **Cobblestone Ground**, with 38 nodes (37 + Material Output) in 9 frames and 50 links. Object coordinates through one identity Mapping feed six Noise and three Voronoi textures. Three Principled BSDFs (dirt, rock, rock moss) are mixed twice: rock vs rock moss by a noise mask, then dirt vs (rock + moss) by a cobblestone mask made from the Difference of a Smooth F1 and an F1 Voronoi (scale 7) whose coordinates are distorted by a Linear Light mix with a Noise (factor 0.2). The same mask drives true displacement (Displacement and Bump, Object Space, Midlevel 0, Scale 0.02). Every value below was read from the UI (class A) unless marked otherwise.

## Scene

| item | value | class | evidence |
|---|---|---|---|
| Blender version | 5.0.1 | A | status bar (every frame) |
| object | Ico sphere mesh named 'Icosphere' in collection 'Collection' (the build file); Add > Mesh > Ico Sphere, redo panel: Subdivisions 6, Radius 1 m, Generate UVs on, Align World, location/rotation 0 (shown on the demo object 'Icosphere.001', 4:17) | A | 4:17 `t0417_add_icosphere_subdiv6.png` |
| size | S 0.5 typed and Ctrl+A > Apply > Scale (4:48-4:53) -> radius 0.5 m, object scale 1 | A | 4:50 / 4:52 `t0450_scale_0p5_typed.png`, `t0452_apply_scale_menu.png` |
| shading | Shade Smooth (narration 4:20) | B | 4:20 |
| build-file mesh | 642 verts / 1,280 faces / 1,280 tris for 'Icosphere' from 4:56 to 26:12 = topology of an ico sphere with Subdivisions 4, not 6 (the demo object Icosphere.001 showed 10,242 / 20,480 = Subdivisions 6) | A (stats) / D (radius of the build object) | 4:56-26:12 status bar |
| modifier | Subdivision Surface: Catmull-Clark, Levels Viewport 0, Render 3, Optimal Display on, Adaptive Subdivision off | A | 5:12 `t0512_subdivision_modifier.png` |
| camera | Perspective, Focal Length 80 mm (drag demo released at 80), Lens Unit mm, Shift 0/0, Clip 0.1 m / 1000 m, DoF off; aimed at the sphere (transform not shown) | A / B / D | 5:21-5:24.5 `t0524_camera_focal_80mm.png` |
| output | 2560 x 2560 px (Y partly behind a tooltip, narrated), pixel aspect 1:1, Render Region ON (border not shown), Crop off, 24 fps, PNG RGBA | A / B | 5:28 `t0528_output_resolution.png` |
| sun | object 'Area' (sun): Temperature ON 6000 K, Tint ~#FFF6EB (pixel sample, C), Strength 15, Exposure 0, Normalize ON, Angle 0.526 deg; rotation not shown | A / C / D | 5:39 `t0539_sun_light.png` |
| rim light | Area light 'Area.001': Temperature OFF, Color #FFEDE0 (HSV 0.074/0.123/1.0; linear 1, 0.8469, 0.7454), Power 300 W, Exposure 0, Normalize ON, Shape Disk, Size 1 m, Spread 180 deg; behind the object | A / B (placement) | 5:56, 6:00 `t0556_area_light_color.png`, `t0600_area_light_settings.png` |
| world | Background, Strength 1.0, Color <- Environment Texture fish_hoek_beach_1k.hdr (Linear, Equirectangular, Single Image, Linear Rec.709, Premultiplied, Vector default). Poly Haven 1K HDR; per D6 not downloaded: use a bundled studio-light HDRI and report lighting separately | A | 6:38 `t0638_world_hdri.png` |
| render engine | Cycles, Device GPU Compute, OSL off; Motion Blur box on (irrelevant for stills) | A | 6:42 `t0642_render_engine_film.png` |
| film | Exposure 1.00, Pixel Filter Blackman-Harris 1.50 px, Transparent ON, Transparent Glass off | A | 6:42 |
| samples | viewport max 10 ('Sample 1/10' overlay); final render samples not shown | A / D | 21:45, 26:08 |
| colour management | Display sRGB, View Filmic, Look Very High Contrast, Exposure 0, Gamma 1 | A | 6:54 `t0654_color_management.png` |
| material settings | Displacement 'Displacement and Bump' (bpy displacement_method 'BOTH'; was Bump Only), Emission Sampling Auto, Transparent Shadows ON, Bump Map Correction ON, Volume Sampling Multiple Importance, Interpolation Linear | A | 25:32-25:42 `t2542_material_displacement_and_bump.png` |
| texture coordinates | Texture Coordinate.Object (no object assigned) -> Mapping (Point, identity) -> Vector of every texture; the two Cobblestone Mask Voronoi textures take the Linear Light result instead (Mapping vector mixed with the distortion Noise Color, factor 0.2). No UV coordinates are used. | A | 7:51, 22:58, 26:12 |
| mapping | Point; Location 0,0,0; Rotation 0,0,0; Scale 1,1,1 | A | 7:51 `t0751_mapping_frame.png` |
| displacement | true displacement + bump; Displacement node Object Space, Midlevel 0.000, Scale 0.020, Height <- Cobblestone Mask ramp (stone interiors 0.3186 linear grey, joints 0) -> stones raised about 0.3186 x 0.02 = 6.4 mm in object space (C) | A / C | 25:00, 25:42, 26:10 |
| units | Object coordinates of a sphere of radius 0.5 m (1 m diameter). Texture scales are per object-space metre: Voronoi 7 -> cells about 0.14 m; dirt noise 20; moss noises 15-25; distortion noise 2. | C | - |

## Final graph (text diagram, state at 26:10)

```
TexCoord.Object -> Mapping (Point, identity) = M          [frame Mapping]

[Dirt Material + Dirt Moss Texture]
M -> dirt_noise (20 / 10 / 0.55).Fac -+-> dirt_color_ramp (0.151 black, 0.553 white) -> dirt_color_mix.Factor  [A #332C24, B #19140F]
                                      +-> dirt_rough_ramp (0.0 #D2D2D2, 1.0 white) -> dirt_rough_hsv (V 1.0) -> dirt_bsdf.Roughness
                                      +-> dirt_bump (Dist 0.02).Height --Normal--> dmoss_bump.Normal
M -> dmoss_noise (25 / 9 / 0.5, lacunarity 3).Fac -> dmoss_hsv (V 1.0) -> dmoss_ramp (0.467 black, 1.0 white).Color
        dmoss_ramp.Color -+-> dmoss_sharp_ramp (0.0 black, 0.324 white) -> dirt_moss_mix.Factor
                          +-> dmoss_bump (Dist 0.005).Height
dirt_color_mix.Result -> dirt_moss_mix.A ; dirt_moss_mix.B = #232511
dirt_moss_mix.Result -> dirt_bsdf.Base Color ; dmoss_bump.Normal -> dirt_bsdf.Normal

[Cobblestone Rock Material]
M -> rock_noise (20 / 10 / 0.5).Fac -+-> rock_color_mix.Factor [A #343534, B #292524] -> rock_bsdf.Base Color (Roughness 0.65)
                                     +-> rock_bump_noise (Dist 0.007).Height --Normal--> rock_bump_vor.Normal
M -> rock_vor (Smooth F1, 12, Detail 10, Smoothness 1).Distance -> rock_bump_vor (Dist 0.015).Height --Normal--> rock_bsdf.Normal

[Rock Moss Material]
M -> rmoss_noise (17 / 15 / 0.7).Fac -> rmoss_bump (Dist 0.01).Height --Normal--> rmoss_bsdf.Normal (Base #222812, Roughness 0.65)

[Moss & Rock Mask]
M -> rmmask_noise (15 / 10 / 0.8).Fac -> rmmask_hsv (V 1.0) -> rmmask_ramp (0.407 black, 0.651 white).Color -> rock_moss_mix.Fac
rock_bsdf.BSDF -> rock_moss_mix.Shader[1] ; rmoss_bsdf.BSDF -> rock_moss_mix.Shader[2]          (no frame)

[Cobblestone Distortion]
M -> dist_noise (2 / 7 / 0.5).Color -> dist_mix (Linear Light, Factor 0.2).B ; M -> dist_mix.A

[Cobblestone Mask]
dist_mix.Result -(reroute)-+-> cell_vor_smooth (Smooth F1, Scale 7, Detail 0, Smoothness 0.6, Rand 1).Distance -> cell_diff.A
                           +-> cell_vor_f1     (F1,        Scale 7, Detail 0,                  Rand 1).Distance -> cell_diff.B
cell_diff (Difference, Factor 1).Result -> cell_ramp (0.0 #999999, 0.035 black).Color

[Mix Rocks & Dirt]
cell_ramp.Color -+-> final_ramp (0.0 black, 0.030 white).Color -> final_mix.Fac
                 +-> displacement (Object Space, Midlevel 0, Scale 0.02).Height
dirt_bsdf.BSDF -> final_mix.Shader[1] ; rock_moss_mix.Shader -> final_mix.Shader[2]
final_mix.Shader -> Material Output.Surface ; displacement.Displacement -> Material Output.Displacement
```

## Frames (UI)

| frame label | created | children |
|---|---|---|
| Mapping | 7:49-7:57 | tex_coord, mapping |
| Dirt Material | 8:52-8:57 | dirt_noise, dirt_color_ramp, dirt_color_mix, dirt_rough_ramp, dirt_rough_hsv, dirt_bump, dmoss_sharp_ramp, dirt_moss_mix, dmoss_bump, dirt_bsdf |
| Dirt Moss Texture | 11:02-11:10 | dmoss_noise, dmoss_hsv, dmoss_ramp |
| Cobblestone Rock Material | 14:09-14:16 | rock_noise, rock_color_mix, rock_bump_noise, rock_vor, rock_bump_vor, rock_bsdf |
| Rock Moss Material | 16:53-17:05 | rmoss_noise, rmoss_bump, rmoss_bsdf |
| Moss & Rock Mask | 18:03-18:10 | rmmask_noise, rmmask_hsv, rmmask_ramp |
| Cobblestone Mask | 21:16-21:24 | cell_vor_smooth, cell_vor_f1, cell_diff, cell_ramp |
| Cobblestone Distortion | 23:03-23:06 | dist_noise, dist_mix |
| Mix Rocks & Dirt | 24:24-24:28 (+ Displacement moved in 25:04-25:21) | final_ramp, final_mix, displacement |

`rock_moss_mix` and `Material Output` sit outside frames (A, 26:12).

## Node inventory (top level, 38 nodes)

| node | type (bpy idname) | label / frame | settings | input values (<- link) | class | evidence |
|---|---|---|---|---|---|---|
| tex_coord | ShaderNodeTexCoord | Texture Coordinate / Mapping | object=-, from_instancer=False | - | A | 7:51 |
| mapping | ShaderNodeMapping | Mapping / Mapping | vector_type=POINT | Vector: <- link tex_coord.Object, Location: (0.0, 0.0, 0.0), Rotation: (0.0, 0.0, 0.0), Scale: (1.0, 1.0, 1.0) | A | 7:51 |
| dirt_noise | ShaderNodeTexNoise | Noise Texture / Dirt Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 20.0, Detail: 10.0, Roughness: 0.55, Lacunarity: 2.0, Distortion: 0.0 | A | 8:05-8:10 |
| dirt_color_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.151 #000000; [1] 0.553 #FFFFFF | Fac: <- link dirt_noise.Fac | A | 8:13-8:23, 12:10.5 |
| dirt_color_mix | ShaderNodeMix | Mix / Dirt Material | data_type=RGBA, blend_type=MIX, clamp_factor=True, clamp_result=False, factor_mode=UNIFORM (default, not shown for RGBA, C) | Factor (inputs[0]): <- link dirt_color_ramp.Color, A (inputs[6]): #332C24 (linear 0.0331, 0.02519, 0.01764), B (inputs[7]): #19140F (linear 0.00972, 0.007, 0.00478) | A | 8:23-8:50, 9:05 |
| dirt_rough_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.0 #D2D2D2; [1] 1.0 #FFFFFF | Fac: <- link dirt_noise.Fac | A | 9:05-9:38 |
| dirt_rough_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Dirt Material | - | Hue: 0.5, Saturation: 1.0, Value: 1.0, Fac: 1.0, Color: <- link dirt_rough_ramp.Color | A | 9:38-9:52, 9:56, 12:10.5 |
| dirt_bump | ShaderNodeBump | Bump / Dirt Material | invert=False | Strength: 1.0, Distance: 0.02, Filter Width: 0.1, Height: <- link dirt_noise.Fac, Normal: unlinked | A | 9:52-10:13 |
| dmoss_noise | ShaderNodeTexNoise | Noise Texture / Dirt Moss Texture | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 25.0, Detail: 9.0, Roughness: 0.5, Lacunarity: 3.0, Distortion: 0.0 | A | 10:24-10:41, 10:55.5 |
| dmoss_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Dirt Moss Texture | - | Hue: 0.5, Saturation: 1.0, Value: 1.0, Fac: 1.0, Color: <- link dmoss_noise.Fac | A | 10:52-11:01, 11:04 |
| dmoss_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Moss Texture | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.467 #000000; [1] 1.0 #FFFFFF | Fac: <- link dmoss_hsv.Color | A | 10:41-10:52, 11:04 |
| dmoss_sharp_ramp | ShaderNodeValToRGB | Color Ramp / Dirt Material | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.0 #000000; [1] 0.324 #FFFFFF | Fac: <- link dmoss_ramp.Color | A | 11:39-12:15 |
| dirt_moss_mix | ShaderNodeMix | Mix / Dirt Material | data_type=RGBA, blend_type=MIX, clamp_factor=True, clamp_result=False, factor_mode=UNIFORM (default, not shown for RGBA, C) | Factor (inputs[0]): <- link dmoss_sharp_ramp.Color, A (inputs[6]): <- link dirt_color_mix.Result, B (inputs[7]): #232511 (linear 0.01681, 0.0185, 0.00561) | A | 11:10-11:28, 12:26 |
| dmoss_bump | ShaderNodeBump | Bump / Dirt Material | invert=False | Strength: 1.0, Distance: 0.005, Filter Width: 0.1, Height: <- link dmoss_ramp.Color, Normal: <- link dirt_bump.Normal | A | 12:33-12:50, 12:58.5 |
| dirt_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Dirt Material | distribution=MULTI_GGX (default, C), subsurface_method=RANDOM_WALK (default, C) | Base Color: <- link dirt_moss_mix.Result, Metallic: 0.0, Roughness: <- link dirt_rough_hsv.Color, IOR: 1.5, Alpha: 1.0, Normal: <- link dmoss_bump.Normal, other inputs: defaults (sub-panels collapsed, C) | A | 8:57-9:05, 12:10.5 |
| rock_noise | ShaderNodeTexNoise | Noise Texture / Cobblestone Rock Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 20.0, Detail: 10.0, Roughness: 0.5, Lacunarity: 2.0, Distortion: 0.0 | A | 13:12-13:24, 14:44 |
| rock_color_mix | ShaderNodeMix | Mix / Cobblestone Rock Material | data_type=RGBA, blend_type=MIX, clamp_factor=True, clamp_result=False, factor_mode=UNIFORM (default, not shown for RGBA, C) | Factor (inputs[0]): <- link rock_noise.Fac, A (inputs[6]): #343534 (linear 0.03434, 0.0356, 0.03434), B (inputs[7]): #292524 (linear 0.02217, 0.0185, 0.01764) | A | 13:25-14:01, 14:44 |
| rock_bump_noise | ShaderNodeBump | Bump / Cobblestone Rock Material | invert=False | Strength: 1.0, Distance: 0.007, Filter Width: 0.1, Height: <- link rock_noise.Fac, Normal: unlinked | A | 14:22-14:39, 14:44 |
| rock_vor | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Rock Material | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=EUCLIDEAN, normalize=False | Vector: <- link mapping.Vector, Scale: 12.0, Detail: 10.0, Roughness: 0.5, Lacunarity: 2.0, Smoothness: 1.0, Randomness: 1.0 | A | 14:46-15:20, 15:21 |
| rock_bump_vor | ShaderNodeBump | Bump / Cobblestone Rock Material | invert=False | Strength: 1.0, Distance: 0.015, Filter Width: 0.1, Height: <- link rock_vor.Distance, Normal: <- link rock_bump_noise.Normal | A | 14:53-15:01, 15:35-15:41 |
| rock_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Cobblestone Rock Material | - | Base Color: <- link rock_color_mix.Result, Metallic: 0.0, Roughness: 0.65, IOR: 1.5, Alpha: 1.0, Normal: <- link rock_bump_vor.Normal, other inputs: defaults (C) | A | 14:02-14:22, 14:44, 15:40 |
| rmoss_noise | ShaderNodeTexNoise | Noise Texture / Rock Moss Material | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 17.0, Detail: 15.0, Roughness: 0.7, Lacunarity: 2.0, Distortion: 0.0 | A | 16:01-16:13, 16:51 |
| rmoss_bump | ShaderNodeBump | Bump / Rock Moss Material | invert=False | Strength: 1.0, Distance: 0.01, Filter Width: 0.1, Height: <- link rmoss_noise.Fac, Normal: unlinked | A | 16:13-16:22, 16:43-16:53 |
| rmoss_bsdf | ShaderNodeBsdfPrincipled | Principled BSDF / Rock Moss Material | - | Base Color: #222812 (linear 0.016, 0.02122, 0.00605), Metallic: 0.0, Roughness: 0.65, IOR: 1.5, Alpha: 1.0, Normal: <- link rmoss_bump.Normal, other inputs: defaults (C) | A | 16:25-16:41, 16:51 |
| rmmask_noise | ShaderNodeTexNoise | Noise Texture / Moss & Rock Mask | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 15.0, Detail: 10.0, Roughness: 0.8, Lacunarity: 2.0, Distortion: 0.0 | A | 17:28-17:48, 18:03.5 |
| rmmask_hsv | ShaderNodeHueSaturation | Hue/Saturation/Value / Moss & Rock Mask | - | Hue: 0.5, Saturation: 1.0, Value: 1.0, Fac: 1.0, Color: <- link rmmask_noise.Fac | A | 17:56-18:03 |
| rmmask_ramp | ShaderNodeValToRGB | Color Ramp / Moss & Rock Mask | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.407 #000000; [1] 0.651 #FFFFFF | Fac: <- link rmmask_hsv.Color | A | 17:48-17:56, 18:42-18:53 |
| rock_moss_mix | ShaderNodeMixShader | Mix Shader / (no frame) | - | Fac (inputs[0]): <- link rmmask_ramp.Color, Shader (inputs[1]): <- link rock_bsdf.BSDF, Shader (inputs[2]): <- link rmoss_bsdf.BSDF | A | 18:13-18:31, 18:32-18:41 |
| dist_noise | ShaderNodeTexNoise | Noise Texture / Cobblestone Distortion | noise_dimensions=3D, noise_type=FBM, normalize=True | Vector: <- link mapping.Vector, Scale: 2.0, Detail: 7.0, Roughness: 0.5, Lacunarity: 2.0, Distortion: 0.0 | A | 22:14-22:27 |
| dist_mix | ShaderNodeMix | Linear Light / Cobblestone Distortion | data_type=RGBA, blend_type=LINEAR_LIGHT, clamp_factor=True, clamp_result=False, factor_mode=UNIFORM (default, not shown for RGBA, C) | Factor (inputs[0]): 0.2, A (inputs[6]): <- link mapping.Vector, B (inputs[7]): <- link dist_noise.Color | A | 22:31-22:43, 22:49-23:00 |
| cell_vor_smooth | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Mask | voronoi_dimensions=3D, feature=SMOOTH_F1, distance=EUCLIDEAN, normalize=False | Vector: <- link dist_mix.Result (via reroute), Scale: 7.0, Detail: 0.0, Roughness: 0.5, Lacunarity: 2.0, Smoothness: 0.6, Randomness: 1.0 | A | 20:06-20:27, 22:58 |
| cell_vor_f1 | ShaderNodeTexVoronoi | Voronoi Texture / Cobblestone Mask | voronoi_dimensions=3D, feature=F1, distance=EUCLIDEAN, normalize=False | Vector: <- link dist_mix.Result (via reroute), Scale: 7.0, Detail: 0.0, Roughness: 0.5, Lacunarity: 2.0, Randomness: 1.0 | A | 20:27-20:42 |
| cell_diff | ShaderNodeMix | Difference / Cobblestone Mask | data_type=RGBA, blend_type=DIFFERENCE, clamp_factor=True, clamp_result=False, factor_mode=UNIFORM (default, not shown for RGBA, C) | Factor (inputs[0]): 1.0, A (inputs[6]): <- link cell_vor_smooth.Distance, B (inputs[7]): <- link cell_vor_f1.Distance | A | 20:42-21:00 |
| cell_ramp | ShaderNodeValToRGB | Color Ramp / Cobblestone Mask | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.0 #999999; [1] 0.035 #000000 | Fac: <- link cell_diff.Result | A | 21:24-21:57 |
| final_ramp | ShaderNodeValToRGB | Color Ramp / Mix Rocks & Dirt | color_ramp.color_mode=RGB, color_ramp.interpolation=LINEAR, color_ramp.hue_interpolation=NEAR (default, C), stops: [0] 0.0 #000000; [1] 0.03 #FFFFFF | Fac: <- link cell_ramp.Color | A | 24:04-24:20 |
| final_mix | ShaderNodeMixShader | Mix Shader / Mix Rocks & Dirt | - | Fac (inputs[0]): <- link final_ramp.Color, Shader (inputs[1]): <- link dirt_bsdf.BSDF, Shader (inputs[2]): <- link rock_moss_mix.Shader | A | 23:27-23:52, 25:25 |
| displacement | ShaderNodeDisplacement | Displacement / Mix Rocks & Dirt | space=OBJECT | Height: <- link cell_ramp.Color (via reroute), Midlevel: 0.0, Scale: 0.02, Normal: unlinked | A | 24:38-25:21, 26:00-26:10 |
| material_output | ShaderNodeOutputMaterial | Material Output / (no frame) | target=ALL, is_active_output=True | Surface: <- link final_mix.Shader, Volume: unlinked, Displacement: <- link displacement.Displacement, Thickness: unlinked | A | 24:44-24:48, 25:25 |

Notes:

- `tex_coord`: added with Node Wrangler Ctrl+T on the first Noise (7:41); only the Object output is used
- `dirt_color_ramp`: contrast ramp of the dirt colour
- `dirt_color_mix`: colours typed as hex (narration 8:38 '33 2C 24', 8:48 '19 14 0F'); picker HSV 0.088/0.291/0.202 and 0.082/0.392/0.096
- `dirt_rough_ramp`: Ctrl/Shift+D copy of the colour ramp reset with Backspace; black stop recoloured #D2D2D2
- `dirt_rough_hsv`: single roughness control (later 'Dirt Roughness')
- `dmoss_noise`: lacunarity 3 gives the 'subtle dot texture' (narration 10:34)
- `dmoss_hsv`: Value demo up/down at 10:57-11:00, left at 1.000
- `dmoss_sharp_ramp`: sharpens the moss for the colour only; the moss bump keeps the softer dmoss_ramp (narration 11:59-12:12)
- `dirt_moss_mix`: duplicate of the first Mix; B typed as hex 232511 (narration 12:21, picker H 0.181 S 0.545 V 0.144)
- `dmoss_bump`: duplicate of the dirt bump chained after it
- `dirt_bsdf`: the material's default Principled BSDF moved into the frame
- `rock_color_mix`: hex typed (narration 13:53 '34 35 34', 13:58 '2925 24'); hex fields visible 13:54 / 13:58.5
- `rock_bump_noise`: narration says 'a 0.7'; the field reads 0.007
- `rock_bump_vor`: duplicate of rock_bump_noise; narration '015'
- `rmoss_bsdf`: Base Color hex 222812 (narration 16:33, picker H 0.215 S 0.551 V 0.156)
- `rmmask_hsv`: Value demo 1.01..1.30, back to 1.000 at 18:03.25
- `rmmask_ramp`: first set ~0.37/0.63, then 0.417 (18:00), final after the 18:42-18:53 demo
- `rock_moss_mix`: created with Node Wrangler Ctrl+0 on the two BSDFs, then the two shader inputs were swapped; Fac default 0.5 overridden by the link
- `dist_mix`: a vector into a colour socket (implicit conversion); node title shows the blend name
- `cell_vor_f1`: Ctrl+Shift+D copy of cell_vor_smooth (input link kept), feature changed to F1
- `cell_ramp`: inverted: difference 0 (stone interior) -> grey 0.3186 linear, difference >= 0.035 (joint) -> black. Feeds final_ramp and the Displacement height
- `displacement`: added with Midlevel 0.5 / Scale 0.01; demo 0.000-0.080; final Midlevel 0.000, Scale 0.020

## Connections (50)

| source node | output socket | destination node | input socket | timestamp | confidence |
|---|---|---|---|---|---|
| tex_coord | Object | mapping | Vector | 7:41-7:51 | A |
| mapping | Vector | dirt_noise | Vector | 7:41-7:51 | A |
| dirt_noise | Fac | dirt_color_ramp | Fac | 8:13-8:22 | A |
| dirt_color_ramp | Color | dirt_color_mix | Factor (inputs[0]) | 8:27-8:31 | A |
| dirt_color_mix | Result (outputs[2]) | dirt_moss_mix | A (inputs[6]) | 11:16-11:29 (auto-insert, then rewired to A) | A |
| dirt_noise | Fac | dirt_rough_ramp | Fac | 9:13-9:18 | A |
| dirt_rough_ramp | Color | dirt_rough_hsv | Color | 9:38-9:42 (HSV dropped on the ramp->Roughness link) | A |
| dirt_rough_hsv | Color | dirt_bsdf | Roughness | 9:38-9:42 | A |
| dirt_noise | Fac | dirt_bump | Height | 9:56-10:00 | A |
| dirt_bump | Normal | dmoss_bump | Normal | 12:37-12:40 (Bump duplicated after the first) | A |
| mapping | Vector | dmoss_noise | Vector | 10:21-10:24 | A |
| dmoss_noise | Fac | dmoss_hsv | Color | 10:52-10:55.5 | A |
| dmoss_hsv | Color | dmoss_ramp | Fac | 10:52-10:55.5 | A |
| dmoss_ramp | Color | dmoss_sharp_ramp | Fac | 11:39-11:48 (ramp dropped on the link) | A |
| dmoss_sharp_ramp | Color | dirt_moss_mix | Factor (inputs[0]) | 11:39-11:48 | A |
| dmoss_ramp | Color | dmoss_bump | Height | 12:42-12:46 | A |
| dirt_moss_mix | Result (outputs[2]) | dirt_bsdf | Base Color | 11:16-11:18 (Mix duplicated onto the Mix->Base Color link) | A |
| dmoss_bump | Normal | dirt_bsdf | Normal | 12:37-12:40 | A |
| mapping | Vector | rock_noise | Vector | 13:15-13:18 | A |
| rock_noise | Fac | rock_color_mix | Factor (inputs[0]) | 13:27-13:31 | A |
| rock_color_mix | Result (outputs[2]) | rock_bsdf | Base Color | 14:05-14:09 | A |
| rock_noise | Fac | rock_bump_noise | Height | 14:27-14:30 | A |
| mapping | Vector | rock_vor | Vector | 14:50-14:54 | A |
| rock_vor | Distance | rock_bump_vor | Height | 14:57-14:59 | A |
| rock_bump_noise | Normal | rock_bump_vor | Normal | 14:55-14:58 (Bump duplicated onto the Bump->Normal link) | A |
| rock_bump_vor | Normal | rock_bsdf | Normal | 14:55-14:58 | A |
| mapping | Vector | rmoss_noise | Vector | 15:54-15:58 | A |
| rmoss_noise | Fac | rmoss_bump | Height | 16:13-16:22 | A |
| rmoss_bump | Normal | rmoss_bsdf | Normal | 16:13-16:22 | A |
| mapping | Vector | rmmask_noise | Vector | 17:28-17:33 | A |
| rmmask_noise | Fac | rmmask_hsv | Color | 17:56-18:01 (HSV dropped on the noise->ramp link) | A |
| rmmask_hsv | Color | rmmask_ramp | Fac | 17:56-18:01 | A |
| rmmask_ramp | Color | rock_moss_mix | Fac (inputs[0]) | 18:22-18:28 | A |
| rock_bsdf | BSDF | rock_moss_mix | Shader (inputs[1]) | 18:16-18:21 Ctrl+0, inputs swapped 18:32-18:41 | A |
| rmoss_bsdf | BSDF | rock_moss_mix | Shader (inputs[2]) | 18:16-18:21 Ctrl+0, inputs swapped 18:32-18:41 | A |
| mapping | Vector | dist_noise | Vector | 22:14-22:20 (Noise dropped on the Mapping->Voronoi link) | A |
| mapping | Vector | dist_mix | A (inputs[6]) | 22:43-22:46 | A |
| dist_noise | Color | dist_mix | B (inputs[7]) | 22:46-22:49 | A |
| dist_mix | Result (outputs[2]) | cell_vor_smooth | Vector | 22:36-22:38 (Linear Light dropped after the Noise; via reroute) | A |
| dist_mix | Result (outputs[2]) | cell_vor_f1 | Vector | 22:36-22:38 (via the same reroute) | A |
| cell_vor_smooth | Distance | cell_diff | A (inputs[6]) | 20:51-20:54 | A |
| cell_vor_f1 | Distance | cell_diff | B (inputs[7]) | 20:53-20:56 | A |
| cell_diff | Result (outputs[2]) | cell_ramp | Fac | 21:28-21:31 | A |
| cell_ramp | Color | final_ramp | Fac | 24:04-24:10 (ramp dropped on the mask->Fac link made at 23:46-23:50) | A |
| final_ramp | Color | final_mix | Fac (inputs[0]) | 24:04-24:10 | A |
| dirt_bsdf | BSDF | final_mix | Shader (inputs[1]) | 23:30-23:34 | A |
| rock_moss_mix | Shader | final_mix | Shader (inputs[2]) | 23:34-23:40 | A |
| cell_ramp | Color | displacement | Height | 24:49-24:58 (reroute added 25:05) | A |
| final_mix | Shader | material_output | Surface | 23:38-23:40 (Ctrl+Shift+click preview) | A |
| displacement | Displacement | material_output | Displacement | 24:44-24:47 | A |

Every link above was also checked in the zoomed-out overview at 26:12 (`t2612_full_graph_overview.png`). Socket-level zooms: `c_t1055_dirt_moss_socket.png` (Noise Factor, not Color, into the HSV), `c_t1803_mask_noise_socket.png` (same in the mask), `c_t1444_rock_noise_socket.png` (both rock links from Noise Factor), `c_t2525_final_mix_sockets.png` (final Mix Shader inputs).

## Colour ramps (all RGB / Linear interpolation)

| ramp (frame) | stop | position | colour (hex, sRGB) | colour (linear) | position class | colour class | evidence |
|---|---|---|---|---|---|---|---|
| dirt_color_ramp (Dirt Material) | 0 | 0.151 | #000000 | 0, 0, 0 | A | A | 8:19.5-8:20.5 |
| dirt_color_ramp (Dirt Material) | 1 | 0.553 | #FFFFFF | 1, 1, 1 | A | A | 8:22.25; 9:56; 12:10.5 |
| dirt_rough_ramp (Dirt Material) | 0 | 0.0 | #D2D2D2 | 0.64448, 0.64448, 0.64448 | A | A | 9:12 reset; 9:35 hex field |
| dirt_rough_ramp (Dirt Material) | 1 | 1.0 | #FFFFFF | 1, 1, 1 | A | A | 9:12 Backspace reset (stops 0/1) |
| dmoss_ramp (Dirt Moss Texture) | 0 | 0.467 | #000000 | 0, 0, 0 | A | A | 10:46.75-10:51.25; 11:04 |
| dmoss_ramp (Dirt Moss Texture) | 1 | 1.0 | #FFFFFF | 1, 1, 1 | A | A | 11:04; 12:03 (demo drag returned to 1.000) |
| dmoss_sharp_ramp (Dirt Material) | 0 | 0.0 | #000000 | 0, 0, 0 | A | A | 12:10.5 |
| dmoss_sharp_ramp (Dirt Material) | 1 | 0.324 | #FFFFFF | 1, 1, 1 | A | A | 12:10.5-12:15.5 (drag 0.917..0.098..0.324) |
| rmmask_ramp (Moss & Rock Mask) | 0 | 0.407 | #000000 | 0, 0, 0 | A | A | 18:50-18:53 |
| rmmask_ramp (Moss & Rock Mask) | 1 | 0.651 | #FFFFFF | 1, 1, 1 | A | A | 18:49.5 |
| cell_ramp (Cobblestone Mask) | 0 | 0.0 | #999999 | 0.31855, 0.31855, 0.31855 | A | A | 21:42.5 stop 0 at 0.000; hex #999999 / V 0.600 at 21:56 |
| cell_ramp (Cobblestone Mask) | 1 | 0.035 | #000000 | 0, 0, 0 | A | A | 21:36.5-21:42.25 (drag 0.410..0.048..0.035) |
| final_ramp (Mix Rocks & Dirt) | 0 | 0.0 | #000000 | 0, 0, 0 | A | A | 24:10-24:20 (new ramp; only the white stop was dragged, black stays at its default 0.0) |
| final_ramp (Mix Rocks & Dirt) | 1 | 0.03 | #FFFFFF | 1, 1, 1 | A | A | 24:18-24:20.5 (drag 0.568..0.085..0.033..0.030) |

All positions were read from the ramp's 'Pos' field while the stop was selected (A); none is a pixel measurement.

## Colour values

| where | hex typed / shown | HSV in the picker (perceptual) | linear RGB (C) | evidence |
|---|---|---|---|---|
| dirt_color_mix.A | #332C24 | 0.088 / 0.291 / 0.202 | 0.03310, 0.02519, 0.01764 | 8:38 `t0838_dirt_color_A_332C24.png` |
| dirt_color_mix.B | #19140F | 0.082 / 0.392 / 0.096 | 0.00972, 0.00700, 0.00478 | 8:48 `t0848_dirt_color_B_19140F.png` |
| dirt_rough_ramp stop 0 | #D2D2D2 | 0 / 0 / 0.825 | 0.64448, 0.64448, 0.64448 | 9:35 `t0935_roughness_ramp_D2D2D2.png` |
| dirt_moss_mix.B | #232511 | 0.181 / 0.545 / 0.144 | 0.01681, 0.01850, 0.00561 | 12:26 `t1226_moss_color_232511.png` |
| rock_color_mix.A | #343534 | 0.324 / 0.028 / 0.209 | 0.03434, 0.03560, 0.03434 | 13:54 `t1354_rock_color_A_343534.png` |
| rock_color_mix.B | #292524 | 0.031 / 0.120 / 0.162 | 0.02217, 0.01850, 0.01764 | 13:58.5 `t1358_rock_color_B_292524.png` |
| rmoss_bsdf Base Color | #222812 | 0.215 / 0.551 / 0.156 | 0.01600, 0.02122, 0.00605 | 16:33 `t1633_rock_moss_color_222812.png` |
| cell_ramp stop 0 | #999999 | 0 / 0 / 0.600 | 0.31855, 0.31855, 0.31855 | 21:56 `t2156_cell_ramp_stop0_999999.png` |

The demo pickers of the product node show the same hue and saturation for Dirt Color 1/2, Dirt Moss Color (1:23-1:35) and the same full HSV for Rock Moss Color, Rock Color 1 and Rock Color 2 (2:51, 3:21, 3:27), so the product defaults equal these build colours (A/C).

## Group interface of the product node (demo 0:00-3:36)

Segment a sees the finished product group only from outside. The table lists every control in demo order (panels as shown at 0:25-3:36), its default and type as seen in the UI, the values dragged in the demo and their narrated effect, and the build node whose value equals the default (probable internal destination, C; segment b observed the actual links). Factor sliders (blue bars) suggest a FACTOR subtype with 0-1 range; min/max are not visible in segment a (D) - demo drags reached 2.000 (both Visibility controls, Dirt Roughness), 3.960 (Cracks), 11.400 (Distortion Detail 1).

| control | panel | socket type | default | min/max if visible | internal destination (probable) | visible effect | demo values seen | class | evidence |
|---|---|---|---|---|---|---|---|---|---|
| Shader (output) | - | NodeSocketShader | - | - | -> Material Output.Surface | - | - | A | 0:13, 0:25 |
| Displacement (output) | - | NodeSocketVector | - | - | -> Material Output.Displacement | - | - | A | 0:13, 0:25 |
| Material Scale | - | NodeSocketFloat (number field) | 1.0 | not shown (D) | mapping.Scale (uniform; segment b A) | changes the size of the entire material (narration 0:26-0:31) | 1.240 (0:27.5), 0.600 (0:29.5) | A (default) / B (effect) | 0:13, 0:27, 0:29 |
| Distortion Detail 1 | Rock Distortion | NodeSocketFloat (number field) | 7.0 | not shown (D) | dist_noise.Detail (build 7.0) | more or less distorted stone outlines (0:33-0:37) | 11.400 (0:33.5), 1.100 (0:35.5) | A / B / C | 0:13, 0:33, 0:35, 0:43 |
| Distortion Detail 2 | Rock Distortion | NodeSocketFloat (factor slider) | 0.5 | not shown (D) | dist_noise.Roughness (build 0.5) | strongly affects the edges of the stones (0:37-0:44) | 0.706 (0:37.5), 0.668 (0:39.5), 0.714 (0:41.5) | A / B / C | 0:13, 0:37, 0:43 |
| Distortion Scale | Rock Distortion | NodeSocketFloat (number field) | 2.0 | not shown (D) | dist_noise.Scale (build 2.0) | high = chunkier, more random stones; low = round and smooth (0:44-0:53) | 6.500 (0:45.5), 5.300 (0:47.5), 2.700 (0:49.5), 0.100 (0:51.5) | A / B / C | 0:45, 0:51 |
| Distortion Strength | Rock Distortion | NodeSocketFloat (factor slider) | 0.2 | not shown (D) | dist_mix.Factor (Linear Light, build 0.2) | 0 = smooth, rounded stones; higher = randomly shaped, chunky (0:54-1:02) | 0.466 (0:53.5), 0.000 (0:55.5), 0.075, 0.341, 0.483 (1:01.5) | A / B / C | 0:53, 0:55, 1:01 |
| Dirt Moss Detail 1 | Dirt & Moss | NodeSocketFloat (number field) | 9.0 | not shown (D) | dmoss_noise.Detail (build 9.0) | detail of the moss on the dirt (1:09-1:13) | 3.200 (1:11.5) | A / B / C | 0:13, 1:11 |
| Dirt Moss Detail 2 | Dirt & Moss | NodeSocketFloat (factor slider) | 0.5 | not shown (D) | dmoss_noise.Roughness (build 0.5) | second moss detail (1:13-1:15) | 0.000 (1:13.5) | A / B / C | 0:13, 1:13 |
| Dirt Moss Visibility | Dirt & Moss | NodeSocketFloat (number field) | 1.0 | not shown (D) | dmoss_hsv.Value (build 1.0) | up = lots of moss on the dirt, down = no moss (1:15-1:22) | 2.000 (1:17.5), 1.380 (1:19.5) | A / B / C | 0:13, 1:17 |
| Dirt Color 1 | Dirt & Moss | NodeSocketColor (colour) | #332C24 (linear 0.0331, 0.02519, 0.01764) | not shown (D) | dirt_color_mix.A (build #332C24, same H/S) | first (lighter) dirt colour (1:22-1:27) | lightened to #8A7762 (HSV 0.088/0.291/0.541, 1:23.5), restored | A (swatch ~#322B24, picker H/S) / C (hex = build) | 0:13, 1:23 |
| Dirt Color 2 | Dirt & Moss | NodeSocketColor (colour) | #19140F (linear 0.00972, 0.007, 0.00478) | not shown (D) | dirt_color_mix.B (build #19140F, same H/S) | second, darker brown dirt colour (1:27-1:32) | lightened to #534232 (HSV 0.082/0.392/0.324, 1:27.5), restored | A / C | 0:13, 1:27 |
| Dirt Moss Color | Dirt & Moss | NodeSocketColor (colour) | #232511 (linear 0.01681, 0.0185, 0.00561) | not shown (D) | dirt_moss_mix.B (build #232511, same H/S) | colour of the moss on the dirt; kept dark green (1:32-1:40) | raised to #858C40 (HSV 0.181/0.545/0.550, 1:35.5), restored to dark | A / C | 0:13, 1:35 |
| Dirt Scale | Dirt & Moss | NodeSocketFloat (number field) | 20.0 | not shown (D) | dirt_noise.Scale (build 20) | scale of the dirt (1:40-1:43) | 23.800 (1:41.5) | A / B / C | 0:13, 1:41 |
| Dirt Moss Scale | Dirt & Moss | NodeSocketFloat (number field) | 25.0 | not shown (D) | dmoss_noise.Scale (build 25) | scale of the moss on the dirt (1:43-1:45) | 21.100 (1:43.5) | A / B / C | 0:13, 1:43 |
| Dirt Roughness | Dirt & Moss | NodeSocketFloat (number field) | 1.0 | not shown (D) | dirt_rough_hsv.Value (build 1.0) | roughness of the dirt (1:45-1:47) | 2.000 (1:45.5) | A / B / C | 0:13, 1:45 |
| Dirt Bump Strength | Dirt & Moss | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | dirt_bump.Strength (build 1.0) | dirt bump (1:47-1:49) | 0.015 (1:47.5) | A / B / C | 0:13, 1:47 |
| Moss Bump Strength | Dirt & Moss | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | dmoss_bump.Strength (build 1.0) | moss-on-dirt bump (1:48-1:51) | 0.000 (1:49.5) | A / B / C | 0:13, 1:49 |
| Cobblestone Scale | Cobblestone Chunks | NodeSocketFloat (number field) | 7.0 | not shown (D) | cell_vor_smooth.Scale + cell_vor_f1.Scale (build 7) | bigger / smaller stones (1:55-2:00) | 4.620 (1:55.5), 8.210 (1:57.5), 10.140 (1:59.5) | A / B / C | 0:13, 1:53, 1:55, 1:59 |
| Cobblestone Cracks | Cobblestone Chunks | NodeSocketFloat (number field) | 0.0 | not shown (D) | cell_vor_smooth.Detail + cell_vor_f1.Detail (build 0) | little cracks / chunks in every stone; about 1 recommended, high values look wrong (2:00-2:16) | 0.780 (2:03-2:07), 3.960 (2:09.5), 0.780, 1.000 (2:13.5), 0.000 (2:17.5) | A / B / C | 1:53, 2:03, 2:09, 2:13 |
| Cobblestone Visibility | Cobblestone Chunks | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | cell_diff.Factor (Difference, build 1.0; segment b A) | down = stones sink back into the dirt (2:17-2:22) | 0.640 (2:17.5), 0.927 (2:19.5) | A / B / C | 1:53, 2:17, 2:19 |
| Cobblestone Alignment | Cobblestone Chunks | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | cell_vor_smooth.Randomness + cell_vor_f1.Randomness (build 1.0): lower = more aligned | aligned, road-like rows vs random layout (2:22-2:30) | 0.000 (2:23.5), 0.177 (2:27.5) | A / B / C | 1:53, 2:23, 2:27 |
| Cobblestone Size | Cobblestone Chunks | NodeSocketFloat (factor slider) | 0.6 | not shown (D) | cell_vor_smooth.Smoothness (build 0.6) | size of each individual stone (joint width) (2:30-2:37) | 0.558 (2:29.5), 0.617 (2:31.5), 0.226 (2:33.5), 0.565 (2:35.5) | A / B / C | 1:53, 2:29, 2:33 |
| Displacement Strength | Cobblestone Chunks | NodeSocketFloat (number field) | 0.02 | not shown (D) | displacement.Scale (build 0.02) | how far the stones pop out of the mesh (2:37-2:42) | 0.110 (2:37.5), 0.000 (2:39.5), 0.070 (2:41.5) | A / B / C | 1:53, 2:37, 2:39 |
| Rock Moss Scale | Rocks and Moss | NodeSocketFloat (number field) | 15.0 | not shown (D) | rmmask_noise.Scale (build 15) | scale of the moss patches on the stones (2:47-2:58) | 16.500 (2:49.5) | A / B / C | 0:13, 2:49 |
| Rock Moss Color | Rocks and Moss | NodeSocketColor (colour) | #222812 (linear 0.016, 0.02122, 0.00605) | not shown (D) | rmoss_bsdf.Base Color (build #222812, identical HSV) | colour of the moss on the stones | picker HSV 0.215/0.551/0.156 (2:51.5); raised to V 0.442 for the demo (2:53), restored (3:15) | A | 0:09, 2:51, 3:15 |
| Rock Moss Roughness | Rocks and Moss | NodeSocketFloat (factor slider) | 0.65 | not shown (D) | rmoss_bsdf.Roughness (build 0.65) | roughness of the moss on the stones (2:58-3:00) | - | A / B / C | 0:09 |
| Rock Moss Detail 1 | Rocks and Moss | NodeSocketFloat (number field) | 15.0 | not shown (D) | rmoss_noise.Detail (build 15) | moss detail (3:00-3:04) | dragged at 2:59 (15.000 shown) | A / B / C | 0:09, 2:59 |
| Rock Moss Detail 2 | Rocks and Moss | NodeSocketFloat (factor slider) | 0.704 | not shown (D) | rmoss_noise.Roughness (build 0.700!) | moss detail (3:00-3:04) | 0.565 (3:01.5) | A / B / C | 0:09, 3:01 |
| Rock Moss Visibility | Rocks and Moss | NodeSocketFloat (number field) | 1.0 | not shown (D) | rmmask_hsv.Value (build 1.0) | way up = moss covers the stones; down = no moss on the stones (3:04-3:12) | 2.000 (3:05.5), 1.990, 0.970 (3:09.5), 0.510 (3:11.5), 1.000 (3:13.5) | A / B / C | 0:09, 3:05, 3:11 |
| Rock Moss Bump Strength | Rocks and Moss | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | rmoss_bump.Strength (build 1.0) | bump of the moss on the stones (3:13-3:15) | - | A / B / C | 0:09 |
| Rock Color 1 | Cobblestone Rocks | NodeSocketColor (colour) | #343534 (linear 0.03434, 0.0356, 0.03434) | not shown (D) | rock_color_mix.A (build #343534, identical HSV) | first stone colour, greyish (3:21-3:25) | picker HSV 0.324/0.028/0.209 (3:21.5) | A | 0:09, 3:21 |
| Rock Color 2 | Cobblestone Rocks | NodeSocketColor (colour) | #292524 (linear 0.02217, 0.0185, 0.01764) | not shown (D) | rock_color_mix.B (build #292524, identical HSV) | second stone colour, brownish variant possible (3:24-3:29) | made browner HSV 0.084/0.789/0.162 (3:25.5), restored 0.031/0.120/0.162 (3:27.5) | A | 0:09, 3:25, 3:27 |
| Rock Roughness | Cobblestone Rocks | NodeSocketFloat (factor slider) | 0.65 | not shown (D) | rock_bsdf.Roughness (build 0.65) | roughness of the stones (3:29-3:31) | 0.417 (3:29.5) | A / B / C | 0:09, 3:29 |
| Rock Detail | Cobblestone Rocks | NodeSocketFloat (number field) | 10.0 | not shown (D) | rock_noise.Detail + rock_vor.Detail (build 10 / 10) | detail of the stone surface (3:31-3:33) | 0.000 (3:31.5) | A / B / C | 0:09, 3:31 |
| Rock Bump Strength | Cobblestone Rocks | NodeSocketFloat (factor slider) | 1.0 | not shown (D) | rock_bump_noise.Strength + rock_bump_vor.Strength (build 1 / 1) | bump strength of the stones (3:33-3:36) | 0.000 (3:33.5) | A / B / C | 0:09, 3:33 |

Interface notes:

- **Distortion Detail 1**: intro (0:11-0:16) lists it BELOW Distortion Detail 2; demo (0:33-1:01) lists it ABOVE
- **Moss Bump Strength**: segment b's rebuilt group calls it 'Dirt Moss Bump Strength'
- **Cobblestone Size**: segment b's rebuilt group calls it 'Cobblestone Individual Size'
- **Rock Moss Detail 2**: product default 0.704 differs from the build value 0.700 (16:51)
- Panel order: Material Scale (no panel), Rock Distortion, Dirt & Moss, Cobblestone Chunks, Rocks and Moss, Cobblestone Rocks (A 0:09-0:25).
- Demo frames: `c_t0013_interface_upper.png`, `c_t0013_interface_middle.png`, `c_t0009_interface_lower.png`, `c_t0043_rock_distortion_order.png`, `c_t0145_dirt_and_moss_values.png`, `c_t0153_chunks_values.png`, colour pickers `c_t0251_*`, `c_t0321_*`, `c_t0327_*`.

## Cross-check with segment b

Segment b (`GRAPH_SPEC_b.md`) reconstructed the same internal graph from the grouping chapter, where several ramp positions had to be measured. Segment a saw the values typed or dragged with the Pos field visible:

| item | segment a | segment b | use |
|---|---|---|---|
| dirt_color_ramp stop 0 position | 0.151 (A: Pos field 8:19.5-8:20.5) | 0.155 (C: bar measurement) | use 0.151 |
| dmoss_ramp stop 0 position | 0.467 (A: Pos field 10:46.75-11:04) | 0.469 (C) | use 0.467 |
| dmoss_sharp_ramp stop 1 position | 0.324 (A: Pos field 12:10.5-12:15.5) | 0.314 (C) | use 0.324 |
| rmmask_ramp stop 1 position | 0.651 (A: Pos field 18:49.5) | 0.645 (C) | use 0.651 |
| cell_ramp stop 1 position | 0.035 (A: Pos field 21:41.5-21:42.25, never reselected later) | 0.02 (C: visible grey width 0.015-0.025) | use 0.035; a linear-space ramp from 0.3186 to 0 looks black well before 0.035 on screen, which explains the short measurement |
| cell_ramp stop 0 colour | #999999 (A: hex field 21:56, HSV value 0.600) | #989898 (A: UI swatch sample) | use #999999 (linear 0.31855) |
| dirt_rough_ramp stop 1 | 1.0 white (A: Backspace reset 9:12) | 1.0 (C) | same |
| dirt_bsdf Metallic / IOR / Alpha | 0.0 / 1.5 / 1.0 (A: 12:10.5) | C | same |
| render engine | Cycles, GPU Compute (A 6:42) | Cycles (C) | same |
| camera, output, lights, world | A (5:12-6:54 panels) | B (narration) | values agree |
| rock_bump_noise Distance | 0.007 (A 14:44; narration '0.7') | 0.007 (A) | same |
| Rock Moss Detail 2 default | product 0.704 vs build 0.700 (A both) | build 0.7 (A) | the builder uses 0.7 inside; product file had 0.704 |

Checked by script against `GRAPH_SPEC_b.json` (C): the 37 shared node ids have identical types, settings and numeric inputs, and all 48 internal links are identical (segment b adds Group Input/Output, segment a has the Material Output); only the ramp values above differ.

## Reference frames of the finished look

| t | frame | what |
|---|---|---|
| 0:04 | `t0004_intro_final_render.png` | intro: Cycles render of the finished material on the sphere (large 1:1 image at right, dark vignette background) plus the camera-view rendered viewport at left; sun + rim light + fish_hoek_beach HDRI, Filmic Very High Contrast, transparent film |
| 0:25 | `t0025_demo_panels_collapsed.png` | rendered viewport ('Rendering Done'), camera view, whole sphere with the product group at its defaults; group node with collapsed panels |
| 1:10 | `t0110_demo_closeup_dirt_moss.png` | rendered viewport, camera zoomed in with the render border on (Output > Render Region): only a small square renders - close-up of a stone and the mossy dirt joint at the product defaults |
| 26:08 | `t2608_viewport_after_displacement.png` | end of the build: rendered viewport (Sample 1/10) of the hand-built material with Displacement and Bump, Midlevel 0, Scale 0.02 - stones raised, mossy joints |
| 26:12 | `t2612_full_graph_overview.png` | node editor zoomed out: the complete flat graph (9 frames) right before grouping |

## Notes for the builder

- Idnames: Hue/Saturation/Value = ShaderNodeHueSaturation; Color Ramp = ShaderNodeValToRGB; Mix (Color) = ShaderNodeMix with data_type 'RGBA' (Factor inputs[0], A inputs[6], B inputs[7], Result outputs[2]); Mix Shader = ShaderNodeMixShader (Fac inputs[0], Shader inputs[1], Shader inputs[2]).
- Noise and Color Ramp sockets show 'Factor' in the 5.0 UI; in the Python API they have been 'Fac' - access them by index to be safe (Noise outputs[0] = Fac, outputs[1] = Color; Color Ramp inputs[0] = Fac, outputs[0] = Color) and verify the names in 5.2 (C).
- The Bump node's third value field reads 'Filter Wi...' (Filter Width, 0.100 default) in 5.0.1 (A, truncated label).
- Every texture uses the same Mapping (object space, identity); no UVs. Only the two Cobblestone Mask Voronoi textures are fed by the Linear Light result.
- All textures are Noise and Voronoi, which both support 4D: the torus (seamless) mode of D2 needs no Wave/Brick replacement (D5 not triggered). The Linear Light distortion mixes the 3D coordinate with a Noise colour; in torus mode apply it to the coordinate the Voronoi textures receive (C).
- Hex colours are display (sRGB) values typed into Blender colour fields; Blender stores them linear. Linear values are listed next to each hex (C, computed with the sRGB transfer function).
- Scales are per object-space unit of a 0.5 m radius sphere (scale applied), i.e. already roughly per metre (C). D4 asks for a size control in metres: Voronoi Scale 7 = about 0.14 m cells; keep the tutorial values as the 1 m reference.
- The colour ramp in 'Cobblestone Mask' feeds both the shader mask (via the 0-0.03 ramp) and the true displacement; its grey stop (#999999 = 0.3186 linear) sets the stone height: (0.3186 - Midlevel 0) x Scale 0.02 = 6.4 mm (C).
- Reroute nodes (19:00-20:03, 20:29, 24:30, 25:05) only tidy the wires; they can be omitted.
