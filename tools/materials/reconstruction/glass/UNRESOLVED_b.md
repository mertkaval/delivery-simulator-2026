# Glass video, segment b: unresolved and ambiguous points

Video `SNKNqHd0AYI`, segment b (22:32-34:03) plus the overview (00:40-02:42) and the scene setup (03:14-06:10).
Everything here is class **D** (unresolved) unless a fallback class is given. Each entry says what was tried and what the
builder should do. Nothing below blocks a faithful rebuild of the three graphs: every node, link, setting and interface
default of the final graphs was read in frames (class A) except the items marked here.

## Graph values

| # | item | why unresolved | what was tried | fallback for the builder |
|---|---|---|---|---|
| D1 | Wavy: exact numbers of the Gabor **Orientation 3D** vector | the socket is drawn only as a direction ball; no numeric field is ever shown | crops of the ball at 22:55, 23:48 and 25:00 (`evidence/b/crops/t2255_*`, `t2348_wavy_gabor_ball.png`, `t2500_wavy_gabor_ball.png`); least-squares fit of a Lambert-lit sphere to the ball pixels: (0.796, 0.605, -0.009) and (0.799, 0.602, -0.007), default check (0.706, 0.704, -0.08) vs Blender's default (0.707, 0.707, 0) | use (0.797, 0.604, 0.0) (class C, +-0.02). Only the X component lies in the video pane, so the look depends on 0.797 x Gabor scale x frequency |
| D2 | Wavy: the intermediate orientations of the two drags (22:57-23:03, 23:12-23:16) | moving widget, not needed | 4 fps crops 23:12-23:18 | ignore (final state only) |
| D3 | Blobby: interface **Voronoi Detail** min / max | its panel was never selected (the active item stayed on Voronoi Scale while it was renamed) | panel frames 28:56-29:01 and 1 fps sheet 28:43-29:09 | default 2.6 is A (group node at 29:41); use min 0, max 15 (Voronoi Detail socket limits, same as the Noise Detail panel seen at 29:07.5) (C) |
| D4 | Frosted: interface **Frosted Detail 2** subtype / min / max | panel never selected (active item stayed on Frosted Detail 1) | panel frames 32:37-32:45; group node 33:03 shows a full factor bar for 1.000 | Factor, 0..1 (Noise Roughness socket limits; the blobby twin socket shows Factor 0..1 at 29:26) (C) |
| D5 | Full text of the inherited socket descriptions ("The amount...ng each axis", "Scale of the bas...", "The number... re", "Blend factor...o", "Value shift...e it brighter", "The rate at ...ise direction", "Strength of t...p mapping", "The amount...s, XYZ order") | truncated in the N panel | 2x crops of the panels | leave empty or copy Blender's own socket descriptions (C); purely cosmetic |
| D6 | Glass Color exact RGBA | only a white swatch is visible | swatch pixels are pure white | (1, 1, 1, 1) = Glass BSDF default (C) |
| D7 | Glass BSDF Thin Film inputs | the Thin Film panel stays collapsed in every frame | - | Blender defaults: thickness 0, IOR 1.33 (C) |
| D8 | Ramp colours in scene-linear | the picker shows perceptual HSV V and display hex, not the stored linear value | read V and hex at 26:33.25, 30:51.9, 30:55.5 (10-30 fps sampling) | linear = sRGB EOTF(V): 0.448, 0.0958, 0.4755 (C); hex-quantised alternatives 0.445, 0.0953, 0.4735. Assumes the colour-picking role is sRGB (Blender 4.x/5.x default config) |
| D9 | Wavy group-node Scale value right after the Vector->Float change (24:21-24:28) | narrated ("texture's still missing ... turn the scale back to one"), value not read | frames 24:21-24:28 | irrelevant: reset to 1.0 (A at 25:26) |

## Product-file variant (customizable nodes overview, 00:40-02:42)

The overview demonstrates the **purchased** project file, not the tutorial build (objects are `Cube.*`, panes in black frames).

| # | item | why unresolved | what was tried | fallback |
|---|---|---|---|---|
| D10 | internal graphs of the product versions of Wavy, Blobby and Frosted | only the group nodes are shown | overview frames 01:59-02:43 (1 fps), intro 00:00-00:40, closing 33:24-34:03 | build the tutorial graphs (A). Visible control differences: product Wavy has no Gabor Frequency; product Blobby exposes Voronoi Roughness 0.5 and none of the three noise-roughness controls; product Frosted uses the names Glass Roughness / Noise Scale / Noise Detail / Noise Roughness |
| D11 | product Frosted Glass "Scale" default | only seen while dragged (16.7, -3.6) | 02:28-02:33 frames | 1.0 like the other variants (C) |
| D12 | product scene: pane geometry (cubes, thickness), frames, studio floor, lights, camera, render settings of the intro/closing renders | never shown | intro and closing frames | treat those renders as look references only, not as a scene recipe |

## Scene setup (03:14-06:10)

| # | item | why unresolved | what was tried | fallback |
|---|---|---|---|---|
| D13 | exact pane offsets, Suzanne count / scale / positions, camera transform | interactive drags; only mid-drag header values visible ("D: 0.9015 along global X", "D: 0.3990 along global Z") | 1 fps frames 03:30-04:46, header crops | a 3 x 2 grid of 0.8 m panes about 0.9 m apart with red objects behind; camera 50 mm framing the grid |
| D14 | red monkey material colour | the picker was never opened (Base Color dragged to "a strong red") | frames 04:14-04:22 | saturated red Principled (C), only a backdrop |
| D15 | final render samples, light paths, denoising, Cycles "Transparent Glass" sub-option | Sampling / Light Paths panels stay collapsed; only the viewport overlay "Sample n/100" is visible | render panel frames 04:50-05:40 | viewport samples 100 (A); final render settings free (C) |
| D16 | material Settings panel (displacement method, EEVEE render method, backface culling) | never opened in segment b | - | defaults; no displacement output is used, so the displacement method does not matter |
| D17 | HDRI `old_apartments_walkway_1k.hdr` (Poly Haven) | not downloaded (DECISIONS.md D6) | - | use a bundled studio-light HDRI and report lighting differences separately |

## Interpretation notes (resolved, recorded for traceability)

- The 1 fps work frames were sampled at about N + 0.48 s (ffmpeg fps filter rounding); kept evidence frames were re-decoded at the exact times listed in `evidence/b/index.json` (`frame_times`), which is why some file names show the whole second only.
- "Frosted Amount" shows a transient typing state "Frsoted Amount" at 32:53.0; the committed name read at 32:55 and 33:03 is "Frosted Amount" (A).
- The recipe repository (material-apprentice) has no entry for this video; its frosted / etched glass entries come from other tutorials and were not used for any value.
- Bump Distance 0.0007 (Wavy) displays as 0.001 after editing (3-decimal display); the typed text "0.0007" is visible at 23:38 (A).
