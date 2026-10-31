# Glass video, segment a: unresolved and uncertain items

`SNKNqHd0AYI` 00:00-22:32. Class **D** = not readable / never shown; **C** = filled in by inference (listed so the
builder knows where the spec is not a direct reading). Evidence paths are relative to `evidence/a/`.

None of the D items below touches the node topology, the node settings or the interface defaults of the three
reconstructed groups: every node, link, setting and default in `GRAPH_SPEC_a.json` is class A except where marked C.

## D: never shown or not readable

| # | item | what was tried | impact |
|---|---|---|---|
| D1 | Render samples (Sampling panel) | render-properties frames 4:52-5:38 scanned: Sampling stays collapsed; only the viewport overlay "Sample n/100" is visible (viewport max 100) | renders: choose samples freely |
| D2 | Exact pane positions | the Shift+D drags are read only as live header readouts that change from frame to frame (`crops/t0336_header_dup_dx.png` 0.8845 at 3:36.5; a neighbouring survey frame read 0.9015; `t0338` -1.7553; `t0341` -0.8707); the final "G Z" raise of all panes shows no value | test scene only (spec gives approximate 2x3 layout, ~0.9 m pitch) |
| D3 | Suzanne size / position | S and G were interactive, Ctrl+A applied the scale; no transform panel shown | backdrop only |
| D4 | Camera transform | Ctrl+Alt+Numpad0 then interactive G and G+MMB (4:36-4:44); the N-panel transform never shown. Lens data is A (`crops/t0446_camera_lens.png`) | framing of test renders |
| D5 | What the **Ctrl+Z x4** at 11:28.5 undid (Voronoi material) | frames 11:26.5 (Scale 30, Roughness 0.5) and 11:28.5 (overlay "Ctrl + Z x4", Scale 5.000, Roughness 0.000; `crops/t1128_undo_ctrl_z_x4.png`); narration 12:10 says the scale edit was undone and it is re-typed (30) at 12:12-12:20 | none: final V1 values confirmed at 12:20.5 and in the group defaults |
| D6 | What the **Ctrl+Z x11** at 20:49.5 undid (Cells group) | frames 20:47.5 / 20:48.5 / 20:49.5 / 20:50.5 compared (`crops/t2049_undo_ctrl_z_x11.png`): interface (Shader, Scale Float default 1.0), HSV (0.5 / 1 / 1 / 1) and Glass are the same before and after; only the view moved | none visible: the final group (22:07.5) matches the pre-group graph (20:15.5) |
| D7 | Material Settings panel (displacement method, etc.) | never opened in segment a | none: nothing is linked to Displacement; Blender default "Bump Only" assumed (C) |
| D8 | Full text of the auto-copied socket descriptions | the N panel elides the middle ("The amount...ng each axis", "The influenc...evious layer", "Strength of t...p mapping", "Value shift...e it brighter", "Blend factor...o zero detail", "The number... render time", "Scale of the base noise o...") | none: Blender fills them when a socket is exposed |
| D9 | Internals of the purchased-file groups shown in the overview (0:40-2:42) | never opened; only their controls are readable (`crops/t0042_...` to `t0228_...`) | the product Voronoi (Glass Roughness 0.2, tint, "Voronoi Detail 1" 3.0 plain / "Voronoi Detail 2" 1.0 factor) and product Cells (no noise controls) differ from the tutorial builds; the spec follows the tutorial |
| D10 | Exact Glass Color of the product Voronoi group | only the swatch pixels: mean (236, 254, 240) where white swatches read 254 -> display ~#ECFEF0 (pale mint) | product variant only |
| D11 | Intro render scene (black frames, studio backdrop, its lights and camera) | the product scene is shown rendered (0:00-0:40, objects Cube.00x) but never built or inspected | visual reference only; lighting differs from the tutorial scene |
| D12 | Source of the temporary yellow link into Glass Color at 11:56.5 (Voronoi material) | appeared when the Glass BSDF was dropped into the preview link; removed at 12:04.5 ("unplug the color") | none: Glass Color unlinked from 12:04.5, later fed by the group input |
| D13 | Render resolution / output settings | never shown | renders only |

## C: inferred values (no direct reading)

| # | item | value used | why |
|---|---|---|---|
| C1 | min/max of Circles "Voronoi Detail" and "Voronoi Randomness", Cells "Voronoi Detail" and "Voronoi Randomness" | 0..15 and 0..1 | these sockets were never selected in the N panel; Blender's Voronoi socket limits, identical to the A-observed twins (Voronoi material Detail 1/2 = 0..15, Factor sockets 0..1) |
| C2 | Ctrl+A option "Rotation & Scale" | Rotation & Scale | overlay shows only "Apply Object Transform" (3:34.5, A); the option is named in the narration (B). The plane was at the origin, so "All Transforms" would give the same object space |
| C3 | Colour ramp stop 1 linear value | 0.3916 | picker in Perceptual mode: V 0.659 / #A8A8A8 converted with the sRGB EOTF |
| C4 | Ramp stop 1 is the last legible value | V 0.659 at 19:57.80-19:57.85 | readouts 0.631 (19:57.3) -> 0.647 (19:57.6) -> 0.659 (19:57.8); the popup is closed at 19:57.87, so a change on the very last frame cannot be excluded. The node swatch afterwards reads grey 171-172 in the video, consistent with #A8A8A8 (168) given the video's level shift |
| C5 | Circles lower curve point | (0.3140, 0.2464) | the last move of this point (between 8:08.5, readout 0.2990/0.3035, and 8:10.5, when the upper point is being dragged) was not caught on a frame; the final position is read from 8:14.6 to 10:43.5 and matches the graph pixels (~0.315, 0.245) |
| C6 | Glass BSDF Thin Film inputs | Blender defaults | the Thin Film panel stays collapsed |
| C7 | Link creation times without a frame | transcript time +-1 s | the final links are all A in the final-graph frames; only the moment of creation is approximate |
| C8 | Bump 2 distance | 0.00008 | typed value seen in the field (13:24.5-13:26.5); afterwards the 4-decimal display shows 0.0001 |
| C9 | Order of the intro panes | top Circles / Voronoi / Cells, bottom Wavy / Blobby / Frosted | inferred from the look of each pane and the overview order |
| C10 | Metre interpretation | Object coordinates = metres | the pane scale was applied (A), so object space has unit scale |

## Not in this segment

The tutorial builds of Textured Glass Wavy, Textured Glass Blobby and Frosted Glass (22:32-33:24) are segment b
(`GRAPH_SPEC_b.json`).
