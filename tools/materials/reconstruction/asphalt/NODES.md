# PM_Asphalt / PM_AsphaltTutorial - node documentation

Generated from the built groups (Blender 5.2.3, `tools/materials/run.py -- build asphalt --dump DIR`, `procmat.graphdump`), plus a mapping to the reverse-engineered spec (`GRAPH_SPEC_all.md`). Spec node ids are the node names / labels in both groups; a texture that is 3D in the video exists twice (`<id>_3d` object mode, `<id>_4d` UV torus) behind a Mix labelled `object 3D | UV 4D` (decision AS2). Every built node carries its evidence class and timestamps in the custom property `pm_note` (column *note*).

## Check against the spec

`scripts/verify_graph.py` traces every link of the spec's collapsed link list (38 links, reroutes collapsed) through the built groups, seeing through reroutes, the 3D/4D mixes and the Coordinates frame (the 3D path; re-run after AS17), with 3.2 -> 5.2 socket names (MixRGB Fac / Color1 / Color2 / Color -> Mix Factor / A / B / Result; a ColorRamp that became a control -> Map Range Value / Result or Mix Factor / Result). Result (`checks/verify_graph.json`):

| group | spec links found | spec nodes missing |
|---|---|---|
| PM_AsphaltTutorial | 38 / 38 | none |
| PM_Asphalt | 38 / 38 | none |

## Spec node -> built nodes

| spec id | video node (3.2) | class | PM_AsphaltTutorial | PM_Asphalt | PM_Asphalt control |
|---|---|---|---|---|---|
| texcoord | Texture Coordinate (Object) | A | Texture Coordinate (Coordinates frame) -> V = Object / Pattern Size | same | Pattern Size (m), Use UV, Tile Size |
| rr_color | NodeReroute | A | rr_color (NodeReroute) | rr_color (NodeReroute) | - |
| rr_cracks | NodeReroute | A | rr_cracks (NodeReroute) | rr_cracks (NodeReroute) | - |
| rr_damage | NodeReroute | A | rr_damage (NodeReroute) | rr_damage (NodeReroute) | - |
| rr_bump | NodeReroute | A | rr_bump (NodeReroute) | rr_bump (NodeReroute) | - |
| color_noise | TexNoise | A | color_noise_3d (TexNoise), color_noise_4d (TexNoise) | color_noise_3d (TexNoise), color_noise_4d (TexNoise) | - |
| color_warp_mix | MixRGB | A | color_warp_mix (Mix) | color_warp_mix (Mix) | - |
| color_voronoi | TexVoronoi | A | color_voronoi_3d (TexVoronoi), color_voronoi_4d (TexVoronoi) | color_voronoi_3d (TexVoronoi), color_voronoi_4d (TexVoronoi) | - |
| color_ramp | ValToRGB | A | color_ramp (ValToRGB) | color_ramp (Mix) | Mix RGBA by the clamped Distance between inputs Color Dark / Color Light |
| cracks_mask_noise | TexNoise | A | cracks_mask_noise_3d (TexNoise), cracks_mask_noise_4d (TexNoise) | cracks_mask_noise_3d (TexNoise), cracks_mask_noise_4d (TexNoise) | - |
| cracks_mask_ramp | ValToRGB | A | cracks_mask_ramp (ValToRGB) | cracks_mask_ramp (MapRange) | Map Range Crack Amount..1 -> 0..1 |
| cracks_warp_noise | TexNoise | A | cracks_warp_noise_3d (TexNoise), cracks_warp_noise_4d (TexNoise) | cracks_warp_noise_3d (TexNoise), cracks_warp_noise_4d (TexNoise) | - |
| cracks_voronoi | TexVoronoi | A | cracks_voronoi (TexVoronoi) | cracks_voronoi (TexVoronoi) | - |
| cracks_mix | MixRGB | A | cracks_mix (Mix) | cracks_mix (Mix) | - |
| damage_warp_noise | TexNoise | A | damage_warp_noise_3d (TexNoise), damage_warp_noise_4d (TexNoise) | damage_warp_noise_3d (TexNoise), damage_warp_noise_4d (TexNoise) | - |
| damage_warp_mix | MixRGB | A | damage_warp_mix (Mix) | damage_warp_mix (Mix) | - |
| damage_voronoi | TexVoronoi | A | damage_voronoi (TexVoronoi) | damage_voronoi (TexVoronoi) | Scale = Pattern Size / Aggregate Size |
| damage_mask_noise | TexNoise | A | damage_mask_noise_3d (TexNoise), damage_mask_noise_4d (TexNoise) | damage_mask_noise_3d (TexNoise), damage_mask_noise_4d (TexNoise) | - |
| damage_mask_ramp | ValToRGB | A | damage_mask_ramp (ValToRGB) | damage_mask_ramp (MapRange) | Map Range Damage Amount..+0.092 -> 0..1 |
| damage_lighten | MixRGB | A | damage_lighten (Mix) | damage_lighten (Mix) | - |
| darken_cracks | MixRGB | A | darken_cracks (Mix) | darken_cracks (Mix) | - |
| damage_dark_ramp | ValToRGB | A | damage_dark_ramp (ValToRGB) | damage_dark_ramp (MapRange) | Map Range Damage Darkness..1 -> 0..1 |
| darken_damage | MixRGB | A | darken_damage (Mix) | darken_damage (Mix) | - |
| bump_noise | TexNoise | A | bump_noise_3d (TexNoise), bump_noise_4d (TexNoise) | bump_noise_3d (TexNoise), bump_noise_4d (TexNoise) | Scale = 60/110 x Pattern Size / Aggregate Size |
| bump1 | Bump | A | bump1 (Bump) | bump1 (Bump) | Strength = Bump Grain |
| bump2 | Bump | A | bump2 (Bump) | bump2 (Bump) | Strength = Bump Cells |
| crack_bump_ramp | ValToRGB | A | crack_bump_ramp (ValToRGB) | crack_bump_ramp (MapRange) | Map Range 0..Crack Width -> 0..1 |
| bump3 | Bump | A | bump3 (Bump) | bump3 (Bump) | Strength = Bump Cracks |
| bump4 | Bump | A | bump4 (Bump) | bump4 (Bump) | Strength = Bump Damage |
| rough_ramp | ValToRGB | A | rough_ramp (ValToRGB) | rough_ramp (MapRange) | Map Range 0..1 -> Roughness Min..1 |
| principled | BsdfPrincipled | A | principled (BsdfPrincipled) | principled (BsdfPrincipled) | - |
| output | Material Output | A | group output BSDF -> material `PM_AsphaltTutorial` Material Output Surface | same in `PM_Asphalt` | - |
| frame_color | frame 'Color' | A | frame 'Color' | frame 'Color' | - |
| frame_cracks | frame 'Cracks' | A | frame 'Cracks' | frame 'Cracks' | - |
| frame_damage | frame 'Damage' | A | frame 'Damage' | frame 'Damage' | - |

Nodes the video does not have (all class C, listed in the dumps below): the Coordinates frame (Object metres / UV torus, from `procmat.core.Coordinates`), `pattern_scale` (1 / Pattern Size), in PM_Asphalt `aggregate_scale`, `grain_scale`, `damage_mask_white` (+0.092) and the Group Input nodes; the four Bump nodes get Filter Width (1.0, decision AS5; an input in PM_Asphalt). UV mode only: the seven `<id>_uvmatch_<output>` nodes (Math / Vector Math Multiply Add, label `<id> UV match`) between each 4D twin and its `object 3D | UV 4D` Mix remap the 4D output to the 3D node's value distribution (decision AS17, audit ASP-1; constants `UV_MATCH` in `procmat/asphalt.py`, fitted by `scripts/uv_match.py`). Object mode never reads them.

---

## Material PM_Asphalt

- displacement_method: BUMP
- surface_render_method: DITHERED
- use_backface_culling: false
- diffuse_color: (0.0264, 0.0257, 0.0253, 1)
- roughness: 0.58
- metallic: 0
- procmat group: PM_Asphalt

### Material tree

#### Nodes (2; frames 0)

Types: ShaderNodeGroup x1, ShaderNodeOutputMaterial x1

| node | type | label | frame | settings (non-default) | input values (non-default, unlinked) | note |
|---|---|---|---|---|---|---|
| MRS | ShaderNodeGroup | PM_Asphalt |  | node_tree=PM_Asphalt |  |  |
| Material Output | ShaderNodeOutputMaterial |  |  |  |  |  |

#### Connections (1)

| from | to |
|---|---|
| MRS.BSDF | Material Output.Surface |

### Group PM_Asphalt

#### Interface

| socket | in/out | type | default | min | max | panel | description |
|---|---|---|---|---|---|---|---|
| Pattern Size | input | Float | 1 | 0.05 | 100 |  | Metres per unit of the video's object space (its sphere radius, 1 m assumed): 1 = the video's sizes (base cells 0.1 m, crack networks ~0.4 m, damage patches ~0.3 m); 2 = everything except the aggregate twice as large |
| Aggregate Size | input | Float | 0.009091 | 0.001 | 0.2 |  | Pebble size in metres in the damaged patches (video: Voronoi Scale 110 = 1/110 m = 9.1 mm); the fine bump grain (video Scale 60) follows it |
| Color Dark | input | Color | (0.01033, 0.009134, 0.008568, 1) |  |  | Colour | Asphalt dark tone: base ramp stop 0 (video #1A1817) |
| Color Light | input | Color | (0.07421, 0.07421, 0.07421, 1) |  |  | Colour | Asphalt light tone: base ramp stop 1 (video #4D4D4D) |
| Crack Amount | input | Float | 0.499 | 0 | 1 | Cracks | Share of the surface with cracks: the crack mask ramp's black stop (video 0.499); higher = more crack regions |
| Crack Width | input | Float | 0.094 | 0 | 1 | Cracks | Width of the recessed crack grooves: the crack bump ramp's white stop (video 0.094); lower = thinner |
| Damage Amount | input | Float | 0.35 | 0 | 1 | Damage | Share of the surface broken away to the pebbles: the damage mask ramp's black stop (video ~0.35; its white stop follows at +0.092); higher = more and larger damaged patches |
| Damage Darkness | input | Float | 0.338 | 0 | 1 | Damage | Darkening of the damaged patches: the damage ramp's black stop (video 0.338); higher = darker |
| Roughness Min | input | Float | 0.4072 | 0 | 1 | Surface | Roughness at the base cell edges, rising to 1 in the cell centres (video #ABABAB = 0.407 linear); lower = shinier / wet |
| Bump Grain | input | Float | 0.1 | 0 | 1 | Surface | Strength of the fine grain bump (video bump 1: 0.1) |
| Bump Cells | input | Float | 0.2 | 0 | 1 | Surface | Strength of the base cell undulation (video bump 2: 0.2) |
| Bump Cracks | input | Float | 0.3 | 0 | 1 | Surface | Depth of the crack grooves (video bump 3: 0.3) |
| Bump Damage | input | Float | 0.4 | 0 | 1 | Surface | Relief of the damaged patches and pebbles (video bump 4: 0.4) |
| Bump Filter Width | input | Float | 1 | 0 | 10 | Surface | Finite-difference width of the four Bump nodes in pixels (not in Blender 3.2): 1 = the video's relief, 0.1 = the Blender 5.2 default (about half the relief contrast) |
| Use UV | input | Float | 0 | 0 | 1 | Mapping | 0 = object space in metres; 1 = UVMap x Tile Size, every 4D texture sampled on a seamless torus (baked tiles repeat) |
| Tile Size | input | Float | 4 | 0.05 | 1000 | Mapping | Metres covered by UV 0..1 in UV mode: the repeat length of a baked tile |
| BSDF | output | Shader |  |  |  |  |  |
| Albedo | output | Color | (0, 0, 0, 1) |  |  |  |  |

#### Nodes (83; frames 4)

Types: ShaderNodeMath x21, ShaderNodeMix x17, ShaderNodeTexNoise x12, NodeGroupInput x5, ShaderNodeMapRange x5, NodeReroute x4, ShaderNodeBump x4, ShaderNodeTexVoronoi x4, ShaderNodeVectorMath x4, NodeGroupOutput x1, ShaderNodeAttribute x1, ShaderNodeBsdfPrincipled x1, ShaderNodeCombineXYZ x1, ShaderNodeSeparateXYZ x1, ShaderNodeTexCoord x1, ShaderNodeVectorRotate x1

| node | type | label | frame | settings (non-default) | input values (non-default, unlinked) | note |
|---|---|---|---|---|---|---|
| Group Output | NodeGroupOutput |  |  |  |  |  |
| Group Input | NodeGroupInput |  |  |  |  |  |
| pattern_scale | ShaderNodeMath | pattern_scale |  | operation=DIVIDE | Value=1 | C: 1 / Pattern Size multiplies every texture coordinate (V, W); 1 = the video's object space |
| aggregate_scale | ShaderNodeMath | aggregate_scale |  | operation=DIVIDE |  | C: Pattern Size / Aggregate Size = the pebble Voronoi Scale (110 at the defaults: 1 / (1/110 m)) |
| grain_scale | ShaderNodeMath | grain_scale |  | operation=MULTIPLY | Value_001=0.5455 | C: bump grain Scale = 60/110 x pebble Scale (60 at the defaults) |
| darken_cracks | ShaderNodeMix | darken_cracks |  | data_type=RGBA; blend_type=DARKEN |  | A 16:11-16:47; 26:32: MixRGB Darken Fac 1, Color1 = base ramp, Color2 = cracks mix |
| damage_dark_ramp | ShaderNodeMapRange | damage_dark_ramp |  |  |  | A 17:52-18:11; 26:32: black @ 0.338 -> white @ 1.0 on the Lighten result \| ColorRamp black@lo -> white@hi as a clamped linear Map Range (identical, C) |
| darken_damage | ShaderNodeMix | darken_damage |  | data_type=RGBA; blend_type=DARKEN |  | A 17:15-17:29, 18:22; 26:32: MixRGB Darken Fac 1 -> Principled Base Color |
| rr_bump | NodeReroute |  |  | socket_idname=NodeSocketVector |  | A 19:05-19:15; 26:32 (layout only) |
| bump_noise_3d | ShaderNodeTexNoise | bump_noise |  |  | Detail=15; Roughness=0.4 | A 18:42-19:46; 26:32: Noise 3D Scale 60 Detail 15 Roughness 0.4 |
| bump_noise_4d | ShaderNodeTexNoise | bump_noise |  | noise_dimensions=4D | Detail=15; Roughness=0.4 | A 18:42-19:46; 26:32: Noise 3D Scale 60 Detail 15 Roughness 0.4 |
| bump_noise_uvmatch_fac | ShaderNodeMath | bump_noise UV match |  | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.016; Value_002=-0.0082 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0165 + -0.0082 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.009 | ShaderNodeMix | object 3D \| UV 4D |  |  |  |  |
| bump1 | ShaderNodeBump | bump1 |  |  | Distance=1 | A 20:20-20:44; 26:32: Strength 0.1 Distance 1.0, Height = bump noise Fac |
| bump2 | ShaderNodeBump | bump2 |  |  | Distance=1 | A 20:58-21:40; 26:32: Strength 0.2 Distance 1.0, Height = base (Smooth F1) Voronoi Distance (frame wins over the recipe repo, U16) |
| crack_bump_ramp | ShaderNodeMapRange | crack_bump_ramp |  |  |  | A 22:45-23:28; 26:32: black @ 0 -> white @ 0.094 on the cracks mix \| ColorRamp black@lo -> white@hi as a clamped linear Map Range (identical, C) |
| bump3 | ShaderNodeBump | bump3 |  |  | Distance=1 | A 21:52-22:20; 26:32: Strength 0.3 Distance 1.0 |
| bump4 | ShaderNodeBump | bump4 |  |  | Distance=1 | A 24:04-24:40; 26:32: Strength 0.4 Distance 1.0, Height = damage Lighten |
| rough_ramp | ShaderNodeMapRange | rough_ramp |  |  |  | A 25:47-26:29: ColorRamp #ABABAB @ 0 -> #FFFFFF @ 1 as Map Range 0..1 -> Roughness Min..1 (identical, C) |
| principled | ShaderNodeBsdfPrincipled | principled |  | distribution=GGX |  | A 06:43, 18:22; 26:32: GGX, Random Walk, Specular 0.5 / IOR 1.45 (3.2) -> IOR 1.5 + Specular IOR Level 0.5 (same F0 0.04, C), other weights 0 |
| rr_color | NodeReroute |  | Color | socket_idname=NodeSocketVector |  | A 08:41-08:56; 26:32 (layout only) |
| color_noise_3d | ShaderNodeTexNoise | color_noise | Color |  | Scale=18; Detail=15; Roughness=0.6 | A 03:22-03:49; 26:32: Noise 3D Scale 18 Detail 15 Roughness 0.6 Distortion 0 |
| color_noise_4d | ShaderNodeTexNoise | color_noise | Color | noise_dimensions=4D | Scale=18; Detail=15; Roughness=0.6 | A 03:22-03:49; 26:32: Noise 3D Scale 18 Detail 15 Roughness 0.6 Distortion 0 |
| color_noise_uvmatch_color | ShaderNodeVectorMath | color_noise UV match | Color | operation=MULTIPLY_ADD | Vector_001=(1.017, 1.114, 1.072); Vector_002=(-0.0085, -0.0571, -0.0357) | C (AS17, audit ASP-1): UV mode only: 4D Color x (1.0169, 1.1138, 1.0719) + (-0.0085, -0.0571, -0.0357) = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.003 | ShaderNodeMix | object 3D \| UV 4D | Color | data_type=RGBA |  |  |
| color_warp_mix | ShaderNodeMix | color_warp_mix | Color | data_type=RGBA; blend_type=LINEAR_LIGHT | Factor=0.1 | A 03:55-04:49; 26:32: MixRGB Linear Light Fac 0.1, Clamp off, Color1 Object, Color2 Noise Color (5.2: Mix RGBA, C) |
| color_voronoi_3d | ShaderNodeTexVoronoi | color_voronoi | Color | distance=MINKOWSKI; feature=SMOOTH_F1 | Scale=10; Exponent=32 | A 02:48-03:10, 05:06; 26:32: Voronoi 3D Smooth F1 Minkowski Scale 10 Smoothness 1 Exponent 32 Randomness 1 |
| color_voronoi_4d | ShaderNodeTexVoronoi | color_voronoi | Color | voronoi_dimensions=4D; distance=MINKOWSKI; feature=SMOOTH_F1 | Scale=10; Exponent=32 | A 02:48-03:10, 05:06; 26:32: Voronoi 3D Smooth F1 Minkowski Scale 10 Smoothness 1 Exponent 32 Randomness 1 |
| color_voronoi_uvmatch_distance | ShaderNodeMath | color_voronoi UV match | Color | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.38; Value_002=-0.0825 | C (AS17, audit ASP-1): UV mode only: 4D Distance x 1.3796 + -0.0825 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.004 | ShaderNodeMix | object 3D \| UV 4D | Color |  |  |  |
| Group Input.002 | NodeGroupInput |  | Color |  |  |  |
| color_ramp | ShaderNodeMix | color_ramp | Color | data_type=RGBA |  | A 05:25-06:30: ColorRamp #1A1817 @ 0 -> #4D4D4D @ 1 as Mix(Color Dark, Color Light) by the clamped Distance (identical, C) |
| Group Input.001 | NodeGroupInput |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Texture Coordinate | ShaderNodeTexCoord |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Attribute | ShaderNodeAttribute | UV | Coordinates: object metres, or UVMap x Tile Size on a seamless  | attribute_name=UVMap |  |  |
| Vector Math | ShaderNodeVectorMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SCALE |  |  |
| Mix | ShaderNodeMix | P (m) | Coordinates: object metres, or UVMap x Tile Size on a seamless  | data_type=VECTOR |  |  |
| Separate XYZ | ShaderNodeSeparateXYZ |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Math | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=DIVIDE | Value_001=6.283 |  |
| Math.001 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY | Value_001=6.283 |  |
| Math.002 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY | Value_001=6.283 |  |
| Math.003 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=COSINE |  |  |
| Math.004 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SINE |  |  |
| Math.005 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=COSINE |  |  |
| Math.006 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SINE |  |  |
| Math.007 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Math.008 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Math.009 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Combine XYZ | ShaderNodeCombineXYZ | torus | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Vector Rotate | ShaderNodeVectorRotate | tilt off the lattice | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  | Axis=(0.53, 0.71, 0.46); Angle=0.83 |  |
| Math.010 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Mix.001 | ShaderNodeMix |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | data_type=VECTOR |  |  |
| Mix.002 | ShaderNodeMix |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Vector Math.001 | ShaderNodeVectorMath | V | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SCALE |  |  |
| Math.011 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| rr_cracks | NodeReroute |  | Cracks | socket_idname=NodeSocketVector |  | A 08:58-09:06; 26:32 (layout only) |
| cracks_mask_noise_3d | ShaderNodeTexNoise | cracks_mask_noise | Cracks |  | Scale=4.5; Detail=15 | A 08:29-08:41, 10:20-10:28; 26:32: Noise 3D Scale 4.5 Detail 15 Roughness 0.5 |
| cracks_mask_noise_4d | ShaderNodeTexNoise | cracks_mask_noise | Cracks | noise_dimensions=4D | Scale=4.5; Detail=15 | A 08:29-08:41, 10:20-10:28; 26:32: Noise 3D Scale 4.5 Detail 15 Roughness 0.5 |
| cracks_mask_noise_uvmatch_fac | ShaderNodeMath | cracks_mask_noise UV match | Cracks | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.019; Value_002=-0.0099 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0194 + -0.0099 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.005 | ShaderNodeMix | object 3D \| UV 4D | Cracks |  |  |  |
| Group Input.003 | NodeGroupInput |  | Cracks |  |  |  |
| cracks_mask_ramp | ShaderNodeMapRange | cracks_mask_ramp | Cracks |  |  | A 09:18-09:38, 17:08; 26:32: black @ 0.499 -> white @ 1.0 on the noise Fac \| ColorRamp black@lo -> white@hi as a clamped linear Map Range (identical, C) |
| cracks_warp_noise_3d | ShaderNodeTexNoise | cracks_warp_noise | Cracks |  | Scale=2.5; Detail=15 | A 07:46-08:09; 26:32: Noise 3D Scale 2.5 Detail 15 Roughness 0.5; its Color goes straight into the Voronoi Vector |
| cracks_warp_noise_4d | ShaderNodeTexNoise | cracks_warp_noise | Cracks | noise_dimensions=4D | Scale=2.5; Detail=15 | A 07:46-08:09; 26:32: Noise 3D Scale 2.5 Detail 15 Roughness 0.5; its Color goes straight into the Voronoi Vector |
| cracks_warp_noise_uvmatch_color | ShaderNodeVectorMath | cracks_warp_noise UV match | Cracks | operation=MULTIPLY_ADD | Vector_001=(1.02, 1.13, 1.067); Vector_002=(-0.0111, -0.0636, -0.0323) | C (AS17, audit ASP-1): UV mode only: 4D Color x (1.02, 1.13, 1.0674) + (-0.0111, -0.0636, -0.0323) = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.006 | ShaderNodeMix | object 3D \| UV 4D | Cracks | data_type=RGBA |  |  |
| cracks_voronoi | ShaderNodeTexVoronoi | cracks_voronoi | Cracks | feature=DISTANCE_TO_EDGE |  | A 07:15-07:34; 26:32: Voronoi 3D Distance to Edge Scale 5 Randomness 1 (metric hidden, Euclidean C). 3D in both modes: its Vector is a noise colour, periodic in UV mode |
| cracks_mix | ShaderNodeMix | cracks_mix | Cracks | data_type=RGBA | B=(1, 1, 1, 1) | A 09:41-10:06; 26:32: MixRGB Mix, Fac = mask ramp, Color1 = Voronoi Distance, Color2 = #FFFFFF, Clamp off |
| rr_damage | NodeReroute |  | Damage | socket_idname=NodeSocketVector |  | A 12:18-12:27, 14:12; 26:32 (layout only) |
| damage_warp_noise_3d | ShaderNodeTexNoise | damage_warp_noise | Damage |  | Scale=20; Detail=15; Roughness=0.6 | A 11:53-12:59; 26:32: Noise 3D Scale 20 Detail 15 Roughness 0.6 |
| damage_warp_noise_4d | ShaderNodeTexNoise | damage_warp_noise | Damage | noise_dimensions=4D | Scale=20; Detail=15; Roughness=0.6 | A 11:53-12:59; 26:32: Noise 3D Scale 20 Detail 15 Roughness 0.6 |
| damage_warp_noise_uvmatch_fac | ShaderNodeMath | damage_warp_noise UV match | Damage | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.016; Value_002=-0.008 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0156 + -0.008 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.007 | ShaderNodeMix | object 3D \| UV 4D | Damage |  |  |  |
| damage_warp_mix | ShaderNodeMix | damage_warp_mix | Damage | data_type=RGBA; blend_type=LINEAR_LIGHT | Factor=0.02 | A 12:06-13:30; 26:32: MixRGB Linear Light Fac 0.02, Color1 Object, Color2 = noise Fac (scalar: equal offset on X, Y, Z) |
| damage_voronoi | ShaderNodeTexVoronoi | damage_voronoi | Damage | voronoi_dimensions=4D; feature=DISTANCE_TO_EDGE |  | A 10:58-11:38; 26:32: Voronoi 4D Distance to Edge W 0 Scale 110 Randomness 1 (object mode W = 0 exactly; UV mode W = the torus W) |
| damage_mask_noise_3d | ShaderNodeTexNoise | damage_mask_noise | Damage |  | Scale=3.5; Detail=15 | A 13:45-14:12; 26:32: Noise 3D Scale 3.5 Detail 15 Roughness 0.5 |
| damage_mask_noise_4d | ShaderNodeTexNoise | damage_mask_noise | Damage | noise_dimensions=4D | Scale=3.5; Detail=15 | A 13:45-14:12; 26:32: Noise 3D Scale 3.5 Detail 15 Roughness 0.5 |
| damage_mask_noise_uvmatch_fac | ShaderNodeMath | damage_mask_noise UV match | Damage | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.024; Value_002=-0.011 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0236 + -0.011 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.008 | ShaderNodeMix | object 3D \| UV 4D | Damage |  |  |  |
| Group Input.004 | NodeGroupInput |  | Damage |  |  |  |
| damage_mask_white | ShaderNodeMath | damage_mask_white | Damage |  | Value_001=0.092 | C: white stop = Damage Amount + 0.092 (the video's 0.35 -> 0.442 gap) |
| damage_mask_ramp | ShaderNodeMapRange | damage_mask_ramp | Damage |  |  | C/A 14:17-14:57; 26:32: black @ 0.35 (C: 0.343 last legible before a jump cut, 0.350 measured after, U1) -> white @ 0.442 (A) \| ColorRamp black@lo -> white@hi as a clamped linear Map Range (identical, C) |
| damage_lighten | ShaderNodeMix | damage_lighten | Damage | data_type=RGBA; blend_type=LIGHTEN |  | A 15:05-15:30; 26:32: MixRGB Lighten Fac 1, Color1 = pebbles, Color2 = mask |

#### Connections (144)

| from | to |
|---|---|
| principled.BSDF | Group Output.BSDF |
| darken_damage.Result | Group Output.Albedo |
| Group Input.Pattern Size | pattern_scale.Value_001 |
| Group Input.Pattern Size | aggregate_scale.Value |
| Group Input.Aggregate Size | aggregate_scale.Value_001 |
| aggregate_scale.Value | grain_scale.Value |
| Group Input.001.Tile Size | Vector Math.Scale |
| Attribute.Vector | Vector Math.Vector |
| Texture Coordinate.Object | Mix.A |
| Vector Math.Vector | Mix.B |
| Group Input.001.Use UV | Mix.Factor |
| Attribute.Vector | Separate XYZ.Vector |
| Group Input.001.Tile Size | Math.Value |
| Separate XYZ.X | Math.001.Value |
| Separate XYZ.Y | Math.002.Value |
| Math.001.Value | Math.003.Value |
| Math.001.Value | Math.004.Value |
| Math.002.Value | Math.005.Value |
| Math.002.Value | Math.006.Value |
| Math.003.Value | Math.007.Value |
| Math.Value | Math.007.Value_001 |
| Math.004.Value | Math.008.Value |
| Math.Value | Math.008.Value_001 |
| Math.005.Value | Math.009.Value |
| Math.Value | Math.009.Value_001 |
| Math.007.Value | Combine XYZ.X |
| Math.008.Value | Combine XYZ.Y |
| Math.009.Value | Combine XYZ.Z |
| Combine XYZ.Vector | Vector Rotate.Vector |
| Math.006.Value | Math.010.Value |
| Math.Value | Math.010.Value_001 |
| Texture Coordinate.Object | Mix.001.A |
| Vector Rotate.Vector | Mix.001.B |
| Group Input.001.Use UV | Mix.001.Factor |
| Math.010.Value | Mix.002.B |
| Group Input.001.Use UV | Mix.002.Factor |
| pattern_scale.Value | Vector Math.001.Scale |
| Mix.001.Result | Vector Math.001.Vector |
| Mix.002.Result | Math.011.Value |
| pattern_scale.Value | Math.011.Value_001 |
| Vector Math.001.Vector | rr_color.Input |
| rr_color.Output | color_noise_3d.Vector |
| rr_color.Output | color_noise_4d.Vector |
| Math.011.Value | color_noise_4d.W |
| color_noise_4d.Color | color_noise_uvmatch_color.Vector |
| color_noise_3d.Color | Mix.003.A |
| color_noise_uvmatch_color.Vector | Mix.003.B |
| Group Input.001.Use UV | Mix.003.Factor |
| rr_color.Output | color_warp_mix.A |
| Mix.003.Result | color_warp_mix.B |
| color_warp_mix.Result | color_voronoi_3d.Vector |
| color_warp_mix.Result | color_voronoi_4d.Vector |
| Math.011.Value | color_voronoi_4d.W |
| color_voronoi_4d.Distance | color_voronoi_uvmatch_distance.Value |
| color_voronoi_3d.Distance | Mix.004.A |
| color_voronoi_uvmatch_distance.Value | Mix.004.B |
| Group Input.001.Use UV | Mix.004.Factor |
| Group Input.002.Color Dark | color_ramp.A |
| Group Input.002.Color Light | color_ramp.B |
| Mix.004.Result | color_ramp.Factor |
| Vector Math.001.Vector | rr_cracks.Input |
| rr_cracks.Output | cracks_mask_noise_3d.Vector |
| rr_cracks.Output | cracks_mask_noise_4d.Vector |
| Math.011.Value | cracks_mask_noise_4d.W |
| cracks_mask_noise_4d.Factor | cracks_mask_noise_uvmatch_fac.Value |
| cracks_mask_noise_3d.Factor | Mix.005.A |
| cracks_mask_noise_uvmatch_fac.Value | Mix.005.B |
| Group Input.001.Use UV | Mix.005.Factor |
| Group Input.003.Crack Amount | cracks_mask_ramp.From Min |
| Mix.005.Result | cracks_mask_ramp.Value |
| rr_cracks.Output | cracks_warp_noise_3d.Vector |
| rr_cracks.Output | cracks_warp_noise_4d.Vector |
| Math.011.Value | cracks_warp_noise_4d.W |
| cracks_warp_noise_4d.Color | cracks_warp_noise_uvmatch_color.Vector |
| cracks_warp_noise_3d.Color | Mix.006.A |
| cracks_warp_noise_uvmatch_color.Vector | Mix.006.B |
| Group Input.001.Use UV | Mix.006.Factor |
| Mix.006.Result | cracks_voronoi.Vector |
| cracks_voronoi.Distance | cracks_mix.A |
| cracks_mask_ramp.Result | cracks_mix.Factor |
| Vector Math.001.Vector | rr_damage.Input |
| rr_damage.Output | damage_warp_noise_3d.Vector |
| rr_damage.Output | damage_warp_noise_4d.Vector |
| Math.011.Value | damage_warp_noise_4d.W |
| damage_warp_noise_4d.Factor | damage_warp_noise_uvmatch_fac.Value |
| damage_warp_noise_3d.Factor | Mix.007.A |
| damage_warp_noise_uvmatch_fac.Value | Mix.007.B |
| Group Input.001.Use UV | Mix.007.Factor |
| rr_damage.Output | damage_warp_mix.A |
| Mix.007.Result | damage_warp_mix.B |
| aggregate_scale.Value | damage_voronoi.Scale |
| damage_warp_mix.Result | damage_voronoi.Vector |
| Math.011.Value | damage_voronoi.W |
| rr_damage.Output | damage_mask_noise_3d.Vector |
| rr_damage.Output | damage_mask_noise_4d.Vector |
| Math.011.Value | damage_mask_noise_4d.W |
| damage_mask_noise_4d.Factor | damage_mask_noise_uvmatch_fac.Value |
| damage_mask_noise_3d.Factor | Mix.008.A |
| damage_mask_noise_uvmatch_fac.Value | Mix.008.B |
| Group Input.001.Use UV | Mix.008.Factor |
| Group Input.004.Damage Amount | damage_mask_white.Value |
| damage_mask_white.Value | damage_mask_ramp.From Max |
| Group Input.004.Damage Amount | damage_mask_ramp.From Min |
| Mix.008.Result | damage_mask_ramp.Value |
| damage_voronoi.Distance | damage_lighten.A |
| damage_mask_ramp.Result | damage_lighten.B |
| color_ramp.Result | darken_cracks.A |
| cracks_mix.Result | darken_cracks.B |
| Group Input.Damage Darkness | damage_dark_ramp.From Min |
| damage_lighten.Result | damage_dark_ramp.Value |
| darken_cracks.Result | darken_damage.A |
| damage_dark_ramp.Result | darken_damage.B |
| Vector Math.001.Vector | rr_bump.Input |
| grain_scale.Value | bump_noise_3d.Scale |
| rr_bump.Output | bump_noise_3d.Vector |
| grain_scale.Value | bump_noise_4d.Scale |
| rr_bump.Output | bump_noise_4d.Vector |
| Math.011.Value | bump_noise_4d.W |
| bump_noise_4d.Factor | bump_noise_uvmatch_fac.Value |
| bump_noise_3d.Factor | Mix.009.A |
| bump_noise_uvmatch_fac.Value | Mix.009.B |
| Group Input.001.Use UV | Mix.009.Factor |
| Group Input.Bump Filter Width | bump1.Filter Width |
| Mix.009.Result | bump1.Height |
| Group Input.Bump Grain | bump1.Strength |
| Group Input.Bump Filter Width | bump2.Filter Width |
| Mix.004.Result | bump2.Height |
| bump1.Normal | bump2.Normal |
| Group Input.Bump Cells | bump2.Strength |
| Group Input.Crack Width | crack_bump_ramp.From Max |
| cracks_mix.Result | crack_bump_ramp.Value |
| Group Input.Bump Filter Width | bump3.Filter Width |
| crack_bump_ramp.Result | bump3.Height |
| bump2.Normal | bump3.Normal |
| Group Input.Bump Cracks | bump3.Strength |
| Group Input.Bump Filter Width | bump4.Filter Width |
| damage_lighten.Result | bump4.Height |
| bump3.Normal | bump4.Normal |
| Group Input.Bump Damage | bump4.Strength |
| Group Input.Roughness Min | rough_ramp.To Min |
| Mix.004.Result | rough_ramp.Value |
| darken_damage.Result | principled.Base Color |
| bump4.Normal | principled.Normal |
| rough_ramp.Result | principled.Roughness |

---

## Material PM_AsphaltTutorial

- displacement_method: BUMP
- surface_render_method: DITHERED
- use_backface_culling: false
- diffuse_color: (0.0264, 0.0257, 0.0253, 1)
- roughness: 0.58
- metallic: 0
- procmat group: PM_AsphaltTutorial

### Material tree

#### Nodes (2; frames 0)

Types: ShaderNodeGroup x1, ShaderNodeOutputMaterial x1

| node | type | label | frame | settings (non-default) | input values (non-default, unlinked) | note |
|---|---|---|---|---|---|---|
| MRS | ShaderNodeGroup | PM_AsphaltTutorial |  | node_tree=PM_AsphaltTutorial |  |  |
| Material Output | ShaderNodeOutputMaterial |  |  |  |  |  |

#### Connections (1)

| from | to |
|---|---|
| MRS.BSDF | Material Output.Surface |

### Group PM_AsphaltTutorial

#### Interface

| socket | in/out | type | default | min | max | panel | description |
|---|---|---|---|---|---|---|---|
| Pattern Size | input | Float | 1 | 0.05 | 100 |  | Metres per unit of the video's object space (its sphere radius, 1 m assumed): 1 = the video's sizes (base cells 0.1 m, crack networks ~0.4 m, damage patches ~0.3 m); 2 = everything except the aggregate twice as large |
| Use UV | input | Float | 0 | 0 | 1 | Mapping | 0 = object space in metres; 1 = UVMap x Tile Size, every 4D texture sampled on a seamless torus (baked tiles repeat) |
| Tile Size | input | Float | 4 | 0.05 | 1000 | Mapping | Metres covered by UV 0..1 in UV mode: the repeat length of a baked tile |
| BSDF | output | Shader |  |  |  |  |  |
| Albedo | output | Color | (0, 0, 0, 1) |  |  |  |  |

#### Nodes (77; frames 4)

Types: ShaderNodeMath x18, ShaderNodeMix x16, ShaderNodeTexNoise x12, ShaderNodeValToRGB x6, NodeReroute x4, ShaderNodeBump x4, ShaderNodeTexVoronoi x4, ShaderNodeVectorMath x4, NodeGroupInput x2, NodeGroupOutput x1, ShaderNodeAttribute x1, ShaderNodeBsdfPrincipled x1, ShaderNodeCombineXYZ x1, ShaderNodeSeparateXYZ x1, ShaderNodeTexCoord x1, ShaderNodeVectorRotate x1

| node | type | label | frame | settings (non-default) | input values (non-default, unlinked) | note |
|---|---|---|---|---|---|---|
| Group Output | NodeGroupOutput |  |  |  |  |  |
| Group Input | NodeGroupInput |  |  |  |  |  |
| pattern_scale | ShaderNodeMath | pattern_scale |  | operation=DIVIDE | Value=1 | C: 1 / Pattern Size multiplies every texture coordinate (V, W); 1 = the video's object space |
| darken_cracks | ShaderNodeMix | darken_cracks |  | data_type=RGBA; blend_type=DARKEN |  | A 16:11-16:47; 26:32: MixRGB Darken Fac 1, Color1 = base ramp, Color2 = cracks mix |
| damage_dark_ramp | ShaderNodeValToRGB | damage_dark_ramp |  | ramp[LINEAR]=0.338:(0, 0, 0, 1), 1:(1, 1, 1, 1) |  | A 17:52-18:11; 26:32: black @ 0.338 -> white @ 1.0 on the Lighten result |
| darken_damage | ShaderNodeMix | darken_damage |  | data_type=RGBA; blend_type=DARKEN |  | A 17:15-17:29, 18:22; 26:32: MixRGB Darken Fac 1 -> Principled Base Color |
| rr_bump | NodeReroute |  |  | socket_idname=NodeSocketVector |  | A 19:05-19:15; 26:32 (layout only) |
| bump_noise_3d | ShaderNodeTexNoise | bump_noise |  |  | Scale=60; Detail=15; Roughness=0.4 | A 18:42-19:46; 26:32: Noise 3D Scale 60 Detail 15 Roughness 0.4 |
| bump_noise_4d | ShaderNodeTexNoise | bump_noise |  | noise_dimensions=4D | Scale=60; Detail=15; Roughness=0.4 | A 18:42-19:46; 26:32: Noise 3D Scale 60 Detail 15 Roughness 0.4 |
| bump_noise_uvmatch_fac | ShaderNodeMath | bump_noise UV match |  | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.016; Value_002=-0.0082 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0165 + -0.0082 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.009 | ShaderNodeMix | object 3D \| UV 4D |  |  |  |  |
| bump1 | ShaderNodeBump | bump1 |  |  | Strength=0.1; Distance=1; Filter Width=1 | A 20:20-20:44; 26:32: Strength 0.1 Distance 1.0, Height = bump noise Fac |
| bump2 | ShaderNodeBump | bump2 |  |  | Strength=0.2; Distance=1; Filter Width=1 | A 20:58-21:40; 26:32: Strength 0.2 Distance 1.0, Height = base (Smooth F1) Voronoi Distance (frame wins over the recipe repo, U16) |
| crack_bump_ramp | ShaderNodeValToRGB | crack_bump_ramp |  | ramp[LINEAR]=0:(0, 0, 0, 1), 0.094:(1, 1, 1, 1) |  | A 22:45-23:28; 26:32: black @ 0 -> white @ 0.094 on the cracks mix |
| bump3 | ShaderNodeBump | bump3 |  |  | Strength=0.3; Distance=1; Filter Width=1 | A 21:52-22:20; 26:32: Strength 0.3 Distance 1.0 |
| bump4 | ShaderNodeBump | bump4 |  |  | Strength=0.4; Distance=1; Filter Width=1 | A 24:04-24:40; 26:32: Strength 0.4 Distance 1.0, Height = damage Lighten |
| rough_ramp | ShaderNodeValToRGB | rough_ramp |  | ramp[LINEAR]=0:(0.407, 0.407, 0.407, 1), 1:(1, 1, 1, 1) |  | A 25:47-26:29; 26:32: #ABABAB @ 0 -> #FFFFFF @ 1 on the base Voronoi Distance |
| principled | ShaderNodeBsdfPrincipled | principled |  | distribution=GGX |  | A 06:43, 18:22; 26:32: GGX, Random Walk, Specular 0.5 / IOR 1.45 (3.2) -> IOR 1.5 + Specular IOR Level 0.5 (same F0 0.04, C), other weights 0 |
| rr_color | NodeReroute |  | Color | socket_idname=NodeSocketVector |  | A 08:41-08:56; 26:32 (layout only) |
| color_noise_3d | ShaderNodeTexNoise | color_noise | Color |  | Scale=18; Detail=15; Roughness=0.6 | A 03:22-03:49; 26:32: Noise 3D Scale 18 Detail 15 Roughness 0.6 Distortion 0 |
| color_noise_4d | ShaderNodeTexNoise | color_noise | Color | noise_dimensions=4D | Scale=18; Detail=15; Roughness=0.6 | A 03:22-03:49; 26:32: Noise 3D Scale 18 Detail 15 Roughness 0.6 Distortion 0 |
| color_noise_uvmatch_color | ShaderNodeVectorMath | color_noise UV match | Color | operation=MULTIPLY_ADD | Vector_001=(1.017, 1.114, 1.072); Vector_002=(-0.0085, -0.0571, -0.0357) | C (AS17, audit ASP-1): UV mode only: 4D Color x (1.0169, 1.1138, 1.0719) + (-0.0085, -0.0571, -0.0357) = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.003 | ShaderNodeMix | object 3D \| UV 4D | Color | data_type=RGBA |  |  |
| color_warp_mix | ShaderNodeMix | color_warp_mix | Color | data_type=RGBA; blend_type=LINEAR_LIGHT | Factor=0.1 | A 03:55-04:49; 26:32: MixRGB Linear Light Fac 0.1, Clamp off, Color1 Object, Color2 Noise Color (5.2: Mix RGBA, C) |
| color_voronoi_3d | ShaderNodeTexVoronoi | color_voronoi | Color | distance=MINKOWSKI; feature=SMOOTH_F1 | Scale=10; Exponent=32 | A 02:48-03:10, 05:06; 26:32: Voronoi 3D Smooth F1 Minkowski Scale 10 Smoothness 1 Exponent 32 Randomness 1 |
| color_voronoi_4d | ShaderNodeTexVoronoi | color_voronoi | Color | voronoi_dimensions=4D; distance=MINKOWSKI; feature=SMOOTH_F1 | Scale=10; Exponent=32 | A 02:48-03:10, 05:06; 26:32: Voronoi 3D Smooth F1 Minkowski Scale 10 Smoothness 1 Exponent 32 Randomness 1 |
| color_voronoi_uvmatch_distance | ShaderNodeMath | color_voronoi UV match | Color | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.38; Value_002=-0.0825 | C (AS17, audit ASP-1): UV mode only: 4D Distance x 1.3796 + -0.0825 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.004 | ShaderNodeMix | object 3D \| UV 4D | Color |  |  |  |
| color_ramp | ShaderNodeValToRGB | color_ramp | Color | ramp[LINEAR]=0:(0.01, 0.009, 0.009, 1), 1:(0.074, 0.074, 0.074, 1) |  | A 05:25-06:30; 26:32: #1A1817 @ 0 -> #4D4D4D @ 1, RGB, Linear |
| Group Input.001 | NodeGroupInput |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Texture Coordinate | ShaderNodeTexCoord |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Attribute | ShaderNodeAttribute | UV | Coordinates: object metres, or UVMap x Tile Size on a seamless  | attribute_name=UVMap |  |  |
| Vector Math | ShaderNodeVectorMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SCALE |  |  |
| Mix | ShaderNodeMix | P (m) | Coordinates: object metres, or UVMap x Tile Size on a seamless  | data_type=VECTOR |  |  |
| Separate XYZ | ShaderNodeSeparateXYZ |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Math | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=DIVIDE | Value_001=6.283 |  |
| Math.001 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY | Value_001=6.283 |  |
| Math.002 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY | Value_001=6.283 |  |
| Math.003 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=COSINE |  |  |
| Math.004 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SINE |  |  |
| Math.005 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=COSINE |  |  |
| Math.006 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SINE |  |  |
| Math.007 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Math.008 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Math.009 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Combine XYZ | ShaderNodeCombineXYZ | torus | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Vector Rotate | ShaderNodeVectorRotate | tilt off the lattice | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  | Axis=(0.53, 0.71, 0.46); Angle=0.83 |  |
| Math.010 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| Mix.001 | ShaderNodeMix |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | data_type=VECTOR |  |  |
| Mix.002 | ShaderNodeMix |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  |  |  |  |
| Vector Math.001 | ShaderNodeVectorMath | V | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=SCALE |  |  |
| Math.011 | ShaderNodeMath |  | Coordinates: object metres, or UVMap x Tile Size on a seamless  | operation=MULTIPLY |  |  |
| rr_cracks | NodeReroute |  | Cracks | socket_idname=NodeSocketVector |  | A 08:58-09:06; 26:32 (layout only) |
| cracks_mask_noise_3d | ShaderNodeTexNoise | cracks_mask_noise | Cracks |  | Scale=4.5; Detail=15 | A 08:29-08:41, 10:20-10:28; 26:32: Noise 3D Scale 4.5 Detail 15 Roughness 0.5 |
| cracks_mask_noise_4d | ShaderNodeTexNoise | cracks_mask_noise | Cracks | noise_dimensions=4D | Scale=4.5; Detail=15 | A 08:29-08:41, 10:20-10:28; 26:32: Noise 3D Scale 4.5 Detail 15 Roughness 0.5 |
| cracks_mask_noise_uvmatch_fac | ShaderNodeMath | cracks_mask_noise UV match | Cracks | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.019; Value_002=-0.0099 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0194 + -0.0099 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.005 | ShaderNodeMix | object 3D \| UV 4D | Cracks |  |  |  |
| cracks_mask_ramp | ShaderNodeValToRGB | cracks_mask_ramp | Cracks | ramp[LINEAR]=0.499:(0, 0, 0, 1), 1:(1, 1, 1, 1) |  | A 09:18-09:38, 17:08; 26:32: black @ 0.499 -> white @ 1.0 on the noise Fac |
| cracks_warp_noise_3d | ShaderNodeTexNoise | cracks_warp_noise | Cracks |  | Scale=2.5; Detail=15 | A 07:46-08:09; 26:32: Noise 3D Scale 2.5 Detail 15 Roughness 0.5; its Color goes straight into the Voronoi Vector |
| cracks_warp_noise_4d | ShaderNodeTexNoise | cracks_warp_noise | Cracks | noise_dimensions=4D | Scale=2.5; Detail=15 | A 07:46-08:09; 26:32: Noise 3D Scale 2.5 Detail 15 Roughness 0.5; its Color goes straight into the Voronoi Vector |
| cracks_warp_noise_uvmatch_color | ShaderNodeVectorMath | cracks_warp_noise UV match | Cracks | operation=MULTIPLY_ADD | Vector_001=(1.02, 1.13, 1.067); Vector_002=(-0.0111, -0.0636, -0.0323) | C (AS17, audit ASP-1): UV mode only: 4D Color x (1.02, 1.13, 1.0674) + (-0.0111, -0.0636, -0.0323) = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.006 | ShaderNodeMix | object 3D \| UV 4D | Cracks | data_type=RGBA |  |  |
| cracks_voronoi | ShaderNodeTexVoronoi | cracks_voronoi | Cracks | feature=DISTANCE_TO_EDGE |  | A 07:15-07:34; 26:32: Voronoi 3D Distance to Edge Scale 5 Randomness 1 (metric hidden, Euclidean C). 3D in both modes: its Vector is a noise colour, periodic in UV mode |
| cracks_mix | ShaderNodeMix | cracks_mix | Cracks | data_type=RGBA | B=(1, 1, 1, 1) | A 09:41-10:06; 26:32: MixRGB Mix, Fac = mask ramp, Color1 = Voronoi Distance, Color2 = #FFFFFF, Clamp off |
| rr_damage | NodeReroute |  | Damage | socket_idname=NodeSocketVector |  | A 12:18-12:27, 14:12; 26:32 (layout only) |
| damage_warp_noise_3d | ShaderNodeTexNoise | damage_warp_noise | Damage |  | Scale=20; Detail=15; Roughness=0.6 | A 11:53-12:59; 26:32: Noise 3D Scale 20 Detail 15 Roughness 0.6 |
| damage_warp_noise_4d | ShaderNodeTexNoise | damage_warp_noise | Damage | noise_dimensions=4D | Scale=20; Detail=15; Roughness=0.6 | A 11:53-12:59; 26:32: Noise 3D Scale 20 Detail 15 Roughness 0.6 |
| damage_warp_noise_uvmatch_fac | ShaderNodeMath | damage_warp_noise UV match | Damage | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.016; Value_002=-0.008 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0156 + -0.008 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.007 | ShaderNodeMix | object 3D \| UV 4D | Damage |  |  |  |
| damage_warp_mix | ShaderNodeMix | damage_warp_mix | Damage | data_type=RGBA; blend_type=LINEAR_LIGHT | Factor=0.02 | A 12:06-13:30; 26:32: MixRGB Linear Light Fac 0.02, Color1 Object, Color2 = noise Fac (scalar: equal offset on X, Y, Z) |
| damage_voronoi | ShaderNodeTexVoronoi | damage_voronoi | Damage | voronoi_dimensions=4D; feature=DISTANCE_TO_EDGE | Scale=110 | A 10:58-11:38; 26:32: Voronoi 4D Distance to Edge W 0 Scale 110 Randomness 1 (object mode W = 0 exactly; UV mode W = the torus W) |
| damage_mask_noise_3d | ShaderNodeTexNoise | damage_mask_noise | Damage |  | Scale=3.5; Detail=15 | A 13:45-14:12; 26:32: Noise 3D Scale 3.5 Detail 15 Roughness 0.5 |
| damage_mask_noise_4d | ShaderNodeTexNoise | damage_mask_noise | Damage | noise_dimensions=4D | Scale=3.5; Detail=15 | A 13:45-14:12; 26:32: Noise 3D Scale 3.5 Detail 15 Roughness 0.5 |
| damage_mask_noise_uvmatch_fac | ShaderNodeMath | damage_mask_noise UV match | Damage | operation=MULTIPLY_ADD; use_clamp=true | Value_001=1.024; Value_002=-0.011 | C (AS17, audit ASP-1): UV mode only: 4D Fac x 1.0236 + -0.011 = the 3D node's distribution (uv_match.py); object mode does not use it |
| Mix.008 | ShaderNodeMix | object 3D \| UV 4D | Damage |  |  |  |
| damage_mask_ramp | ShaderNodeValToRGB | damage_mask_ramp | Damage | ramp[LINEAR]=0.35:(0, 0, 0, 1), 0.442:(1, 1, 1, 1) |  | C/A 14:17-14:57; 26:32: black @ 0.35 (C: 0.343 last legible before a jump cut, 0.350 measured after, U1) -> white @ 0.442 (A) |
| damage_lighten | ShaderNodeMix | damage_lighten | Damage | data_type=RGBA; blend_type=LIGHTEN |  | A 15:05-15:30; 26:32: MixRGB Lighten Fac 1, Color1 = pebbles, Color2 = mask |

#### Connections (121)

| from | to |
|---|---|
| principled.BSDF | Group Output.BSDF |
| darken_damage.Result | Group Output.Albedo |
| Group Input.Pattern Size | pattern_scale.Value_001 |
| Group Input.001.Tile Size | Vector Math.Scale |
| Attribute.Vector | Vector Math.Vector |
| Texture Coordinate.Object | Mix.A |
| Vector Math.Vector | Mix.B |
| Group Input.001.Use UV | Mix.Factor |
| Attribute.Vector | Separate XYZ.Vector |
| Group Input.001.Tile Size | Math.Value |
| Separate XYZ.X | Math.001.Value |
| Separate XYZ.Y | Math.002.Value |
| Math.001.Value | Math.003.Value |
| Math.001.Value | Math.004.Value |
| Math.002.Value | Math.005.Value |
| Math.002.Value | Math.006.Value |
| Math.003.Value | Math.007.Value |
| Math.Value | Math.007.Value_001 |
| Math.004.Value | Math.008.Value |
| Math.Value | Math.008.Value_001 |
| Math.005.Value | Math.009.Value |
| Math.Value | Math.009.Value_001 |
| Math.007.Value | Combine XYZ.X |
| Math.008.Value | Combine XYZ.Y |
| Math.009.Value | Combine XYZ.Z |
| Combine XYZ.Vector | Vector Rotate.Vector |
| Math.006.Value | Math.010.Value |
| Math.Value | Math.010.Value_001 |
| Texture Coordinate.Object | Mix.001.A |
| Vector Rotate.Vector | Mix.001.B |
| Group Input.001.Use UV | Mix.001.Factor |
| Math.010.Value | Mix.002.B |
| Group Input.001.Use UV | Mix.002.Factor |
| pattern_scale.Value | Vector Math.001.Scale |
| Mix.001.Result | Vector Math.001.Vector |
| Mix.002.Result | Math.011.Value |
| pattern_scale.Value | Math.011.Value_001 |
| Vector Math.001.Vector | rr_color.Input |
| rr_color.Output | color_noise_3d.Vector |
| rr_color.Output | color_noise_4d.Vector |
| Math.011.Value | color_noise_4d.W |
| color_noise_4d.Color | color_noise_uvmatch_color.Vector |
| color_noise_3d.Color | Mix.003.A |
| color_noise_uvmatch_color.Vector | Mix.003.B |
| Group Input.001.Use UV | Mix.003.Factor |
| rr_color.Output | color_warp_mix.A |
| Mix.003.Result | color_warp_mix.B |
| color_warp_mix.Result | color_voronoi_3d.Vector |
| color_warp_mix.Result | color_voronoi_4d.Vector |
| Math.011.Value | color_voronoi_4d.W |
| color_voronoi_4d.Distance | color_voronoi_uvmatch_distance.Value |
| color_voronoi_3d.Distance | Mix.004.A |
| color_voronoi_uvmatch_distance.Value | Mix.004.B |
| Group Input.001.Use UV | Mix.004.Factor |
| Mix.004.Result | color_ramp.Factor |
| Vector Math.001.Vector | rr_cracks.Input |
| rr_cracks.Output | cracks_mask_noise_3d.Vector |
| rr_cracks.Output | cracks_mask_noise_4d.Vector |
| Math.011.Value | cracks_mask_noise_4d.W |
| cracks_mask_noise_4d.Factor | cracks_mask_noise_uvmatch_fac.Value |
| cracks_mask_noise_3d.Factor | Mix.005.A |
| cracks_mask_noise_uvmatch_fac.Value | Mix.005.B |
| Group Input.001.Use UV | Mix.005.Factor |
| Mix.005.Result | cracks_mask_ramp.Factor |
| rr_cracks.Output | cracks_warp_noise_3d.Vector |
| rr_cracks.Output | cracks_warp_noise_4d.Vector |
| Math.011.Value | cracks_warp_noise_4d.W |
| cracks_warp_noise_4d.Color | cracks_warp_noise_uvmatch_color.Vector |
| cracks_warp_noise_3d.Color | Mix.006.A |
| cracks_warp_noise_uvmatch_color.Vector | Mix.006.B |
| Group Input.001.Use UV | Mix.006.Factor |
| Mix.006.Result | cracks_voronoi.Vector |
| cracks_voronoi.Distance | cracks_mix.A |
| cracks_mask_ramp.Color | cracks_mix.Factor |
| Vector Math.001.Vector | rr_damage.Input |
| rr_damage.Output | damage_warp_noise_3d.Vector |
| rr_damage.Output | damage_warp_noise_4d.Vector |
| Math.011.Value | damage_warp_noise_4d.W |
| damage_warp_noise_4d.Factor | damage_warp_noise_uvmatch_fac.Value |
| damage_warp_noise_3d.Factor | Mix.007.A |
| damage_warp_noise_uvmatch_fac.Value | Mix.007.B |
| Group Input.001.Use UV | Mix.007.Factor |
| rr_damage.Output | damage_warp_mix.A |
| Mix.007.Result | damage_warp_mix.B |
| damage_warp_mix.Result | damage_voronoi.Vector |
| Math.011.Value | damage_voronoi.W |
| rr_damage.Output | damage_mask_noise_3d.Vector |
| rr_damage.Output | damage_mask_noise_4d.Vector |
| Math.011.Value | damage_mask_noise_4d.W |
| damage_mask_noise_4d.Factor | damage_mask_noise_uvmatch_fac.Value |
| damage_mask_noise_3d.Factor | Mix.008.A |
| damage_mask_noise_uvmatch_fac.Value | Mix.008.B |
| Group Input.001.Use UV | Mix.008.Factor |
| Mix.008.Result | damage_mask_ramp.Factor |
| damage_voronoi.Distance | damage_lighten.A |
| damage_mask_ramp.Color | damage_lighten.B |
| color_ramp.Color | darken_cracks.A |
| cracks_mix.Result | darken_cracks.B |
| damage_lighten.Result | damage_dark_ramp.Factor |
| darken_cracks.Result | darken_damage.A |
| damage_dark_ramp.Color | darken_damage.B |
| Vector Math.001.Vector | rr_bump.Input |
| rr_bump.Output | bump_noise_3d.Vector |
| rr_bump.Output | bump_noise_4d.Vector |
| Math.011.Value | bump_noise_4d.W |
| bump_noise_4d.Factor | bump_noise_uvmatch_fac.Value |
| bump_noise_3d.Factor | Mix.009.A |
| bump_noise_uvmatch_fac.Value | Mix.009.B |
| Group Input.001.Use UV | Mix.009.Factor |
| Mix.009.Result | bump1.Height |
| Mix.004.Result | bump2.Height |
| bump1.Normal | bump2.Normal |
| cracks_mix.Result | crack_bump_ramp.Factor |
| crack_bump_ramp.Color | bump3.Height |
| bump2.Normal | bump3.Normal |
| damage_lighten.Result | bump4.Height |
| bump3.Normal | bump4.Normal |
| Mix.004.Result | rough_ramp.Factor |
| darken_damage.Result | principled.Base Color |
| bump4.Normal | principled.Normal |
| rough_ramp.Color | principled.Roughness |
