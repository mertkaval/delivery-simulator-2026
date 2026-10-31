# Unresolved and ambiguous items, segment a (0:00-26:10)

Video `30vbbpy9zwg`. Class **D** = not shown, not readable or contradictory; **C** = our inference or computation, given with the
method so the builder can judge it. Frames are in `evidence/a/frames/`, crops in `evidence/a/crops/`, index `evidence/a/index.json`.

Every node type, node setting, input value, colour-ramp stop and link of the final graph was read from the UI (class A). The open items
below are scene details around the material, the outside of the product node group, and small numeric discrepancies.

## D items

| # | item | what is known | what was tried | recommendation for the builder |
|---|---|---|---|---|
| U1 | Final render samples | The viewport overlay shows "Sample 0/10" (21:45) and "Sample 1/10" (26:08): viewport max samples 10 (A). Render > Sampling is never opened (closed panel at 4:50 and 6:42). | Render-properties frames 4:44-4:53, 6:39-6:54. | Unknown; choose the sample count for the comparison renders yourself. |
| U2 | Camera transform and sensor | Lens Perspective 80 mm, clip 0.1-1000 m, DoF off (A, 5:21-5:24.5). Narration 5:17: "pointed the camera at the object". | Camera Lens panel 5:16-5:25; Camera/Sensor sub-panels stay closed. | Frame the 1 m sphere so that it fills about 80 % of a square 2560 px image, as in `t0004_intro_final_render.png` (C). |
| U3 | Light directions | Sun: Strength 15, 6000 K, Angle 0.526 deg (A 5:39); Area 'Area.001' 300 W disk 1 m (A 6:00) "behind the object" (B 6:00-6:04). No transform is shown. | 5:31-6:04 at 1 fps and the light panels at full resolution. | Key from the camera side, above; rim light behind the sphere (C). Report lighting separately from the material (D6). |
| U4 | Sun Tint | With Temperature on, the colour row reads 'Tint'; the swatch samples about #FFF6EB (C, pixel median at 5:39). | Pixel sampling (the Area colour swatch sampled #FDEBDE against its typed #FFEDE0, so the method is good to about 2 levels). | Use white or #FFF6EB; negligible next to the 6000 K blackbody. |
| U5 | Geometry of the build file | On camera (4:05-4:53) the new 'Icosphere.001' gets Subdivisions 6 (redo panel, A), is scaled 0.5 and the scale applied (A). From 4:56 to 26:12 the prepared file's 'Icosphere' shows 642 verts / 1,280 faces (A) = Subdivisions **4** topology; its size is never shown. | Status bar at 4:20-4:53 (10,242 / 20,480) and 4:56-26:12 (642 / 1,280); modifier panel 5:12. | Use an ico sphere of radius 0.5 m with scale applied (C). For true displacement use Subdivisions 6 or the Subdivision Surface render level 3 (5:12); both were shown. |
| U6 | Render Region border | Output > Render Region is ON (A 5:28); at 1:07-1:13 the camera-view render shows only a small square inside a dashed border. The border rectangle is not shown. | 5:28 output panel; 1:07-1:13 viewport. | Ignore (turn the border off) for comparison renders. |
| U7 | Min / max / subtype of the product's controls | Segment a only sees the product node from outside: factor sliders (blue bar) vs plain number fields are visible (A); limits are not. Demo drags reached 2.000 (Dirt Moss Visibility, Rock Moss Visibility, Dirt Roughness), 3.960 (Cobblestone Cracks), 11.400 (Distortion Detail 1), 0.100 (Distortion Scale). | Every demo value 0:25-3:36 at 1 fps and 2-4 fps. | Take min/max/subtypes from segment b, which created the sockets on camera (A there). |
| U8 | Order of Distortion Detail 1 / 2 in the product | Intro 0:11-0:16 lists Detail 2, Detail 1, Scale, Strength; the demo 0:33-1:01 lists Detail 1, Detail 2, Scale, Strength (A both; `c_t0013_interface_upper.png`, `c_t0043_rock_distortion_order.png`). | Checked 0:11, 0:12, 0:13, 0:14, 0:16, 0:31, 0:35-1:01. | Cosmetic; follow segment b's final order. |
| U9 | Principled BSDF dropdowns and collapsed sub-panels | The three BSDFs show Base Color, Metallic, Roughness, IOR, Alpha, Normal and collapsed panels (Diffuse ... Thin Film); the distribution / subsurface dropdowns are not visible in any frame. | 12:10.5, 14:44, 15:40, 16:51 at full resolution. | Blender defaults (Multiscatter GGX, Random Walk, all sub-panel values default) (C). |
| U10 | Unexplained statistics in the product demo | At 1:10 the status bar shows Verts 301 / Faces 554 for 'Icosphere' (A), at 0:25 642 / 1,280. | Status-bar crops 0:25 and 1:10. | No effect on the material; ignore. |

## Small discrepancies (resolved, listed for traceability)

| item | evidence | resolution |
|---|---|---|
| Roughness ramp stop 0 | picker shows HSV value 0.825 with hex #D2D2D2 (A 9:35); #D2D2D2 = 0.8235, linear 0.6445; V 0.825 would be linear 0.6471 | use the hex #D2D2D2 (difference 0.4 %) |
| Moss colour (dirt) | hex #232511 typed (narration 12:21, picker 12:26, A); a tooltip at 12:18.75 shows 'Value: 0.0167 0.0181...' (cut off) | use the hex: linear (0.01681, 0.01850, 0.00561) |
| Displacement node as added | shows Midlevel 0.500 and Scale 0.010 at 24:56 (A; Blender's usual default Scale is 1.0) | irrelevant: final Midlevel 0.000, Scale 0.020 (A 26:10) |
| Rock Moss Detail 2 | product default 0.704 (A 0:09) vs build noise Roughness 0.700 (A 16:51) | build value 0.7 inside the graph; the product file was tweaked |
| Narration vs fields | rock bump '0.7' -> 0.007 (14:44); rock bump 2 '015' -> 0.015 (15:40); moss bump '01' -> 0.010 (16:51); dirt moss bump '05' -> 0.005 (12:58.5); mask grey 'hex value of 6 9' -> #999999 (21:56); 'smoothness to a 6' -> 0.6 (20:27); focal '80' (a transient 89 mm at 5:23 during the drag) -> 80 (5:24.5) | the field wins (A) |
| Motion Blur | the Render Motion Blur checkbox is on (A 6:42) | irrelevant for still renders |

## Items that segment b left open and segment a resolves

| segment b item | segment a reading | evidence |
|---|---|---|
| U1 `cell_ramp` black stop position (b: 0.02, C) | **0.035** - the Pos field of stop 1 reads 0.048 ... 0.043, 0.038, 0.035 while dragged, then stop 0 is selected (21:42.5) and never stop 1 again | `t2141_cell_ramp_stop1_0p035.png`, `c_t2141_cell_ramp_stop1.png`; 4 fps strip 21:34-21:46 |
| U2 `cell_ramp` grey stop colour (b: #989898, A swatch) | **#999999**, HSV value 0.600 (hex field of the picker, A); the narration's '6 9' most likely means 'six nines' (C) | `t2156_cell_ramp_stop0_999999.png`, `c_t2156_cell_ramp_hex.png` |
| U3 icosphere subdivisions | 6 on the demo object (redo panel), 4 in the build file (stats) - both A | `t0417_add_icosphere_subdiv6.png`; status bar |
| U4 render engine | **Cycles**, GPU Compute (A) | `t0642_render_engine_film.png` |
| U6 dirt BSDF Metallic / IOR / Alpha | **0.000 / 1.500 / 1.000** (A) | `t1210_dirt_material_overview.png` |
| C items 0.155 / 0.314 / 0.469 / 0.645 | **0.151 / 0.324 / 0.467 / 0.651** read in the Pos field (A) | `t0820_*`, `t1210_*`, `t1104_*`, `t1849_*` |
| scene values that b kept as B | camera 80 mm, 2560 x 2560, sun 15 / 6000 K, rim 300 W disk, fish_hoek_beach_1k.hdr, Filmic Very High Contrast, Film Transparent: all **A** | scene frames 5:12-6:54 |

## What was tried overall

- Transcript map of 0:00-26:10, 1-fps review frames of the whole segment (contact sheets), then 2-10 fps strips around every value change
  (ramp drags, colour pickers, focal length, displacement), exact full-resolution grabs at the settled moments, and 2-5x crops of sockets
  and fields. Enlargement was used only to read text that is legible at full resolution; nothing was guessed from blurred pixels.
- Pixel sampling only for the swatches of the product node and the sun tint (class C).
- Programmatic cross-check against `GRAPH_SPEC_b.json`: the 37 shared node ids have identical types, settings and numeric inputs and
  all 48 internal links match; only the ramp positions above differ.
