# Glass video, segment a: decisions taken without the user

To be merged into `tools/materials/DECISIONS.md` by the docs step. Segment a = `SNKNqHd0AYI` 00:00-22:32
(overview of the six product groups, scene setup, Textured Glass Circles, Textured Glass Voronoi, Textured Glass Cells).
Binding project decisions D1-D11 are unchanged.

| # | decision | reason |
|---|---|---|
| a1 | The specification describes the graphs **built in the tutorial** (final demonstrated state). The purchased-file groups shown in the overview are recorded as variants only (control names, order, types, values). | the product graphs are never opened (class D); the tutorial graphs are fully visible (class A). The product Voronoi and Cells groups differ from the tutorial builds (see `GRAPH_SPEC_a.md` section 6) |
| a2 | All times are true video times; the 1 fps survey frames (which showed time N+0.5 s because of the ffmpeg fps filter) were used only to locate events, and every cited frame was re-extracted with `ffmpeg -ss <t> -frames:v 1` at the listed time. | the first extraction at N.0 showed the wrong state at fast changes (e.g. the overview at 1:38.0 still showed the Voronoi group) |
| a3 | Demo edits made on a finished group node (colour pickers, slider drags, typed test values) are not part of the reconstruction. Defaults come from the N-panel socket properties and the group-node values at the end of each chapter, which are back at the defaults. | the narration presents them as demonstrations; the end-of-chapter frames confirm the defaults |
| a4 | Where a picker value was still being dragged, the **last legible value before the popup closes** is used: Cells ramp stop 1 = Perceptual V 0.659 / #A8A8A8 -> linear 0.3916; monkey red = #F40D00. | the popup closing ends the edit; earlier readouts (0.631, 0.647 / #E70C00) are intermediate |
| a5 | Interface limits that were never displayed take Blender's socket limits (class C): Voronoi Detail 0..15, Randomness 0..1. | their twin sockets show exactly these limits |
| a6 | Units: the panes have applied scale, so Object coordinates are metres. Densities (Circles 50 cells/m, Voronoi 2 x 30/m, Cells 30/m + noise 20/m) and bump distances (0.002, 0.004 + 0.00008, 0.003 m) are recorded in metres for the D4 conversion. | `S .4` + Apply Rotation & Scale observed at 3:26-3:34 |
| a7 | Bump 2 of the Voronoi material uses the typed value 0.00008, not the displayed 0.0001. | the field showed "0.00008" while typing; the UI rounds to 4 decimals afterwards |
| a8 | After an undo (Ctrl+Z x4 at 11:28, Ctrl+Z x11 at 20:49) only the resulting state counts; what was undone stays class D. | the final graphs are fully visible later and agree with the surrounding frames |
| a9 | Evidence budget: 16 full-resolution PNG frames + 98 labelled PNG crops (about 36 MB). A crop whose full frame is not kept cites the video time as its source (`evidence/a/index.json`). | the task asks for cited frames only, no bulk dumps; crops carry the readable detail |
| a10 | The HDRI named in the video (`old_apartments_walkway_1k`, Poly Haven) is recorded but not downloaded; renders use a bundled studiolight (D6). | D6 |
