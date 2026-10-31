# Cobblestone video, segment a: decisions taken without the user

To be merged into `tools/materials/DECISIONS.md` by the docs step. Segment a = `30vbbpy9zwg` 0:00-26:10 (intro, product demo of the
customizable node, scene setup, the whole procedural build). Binding decisions D1-D11 were followed; nothing was built in Blender and
the user's Blender / Godot were not touched.

| # | decision | reason |
|---|---|---|
| a1 | The final graph of segment a is the flat material at 26:10 (38 nodes, 9 frames, 50 links), i.e. the internals of the group made in segment b. Node ids follow segment b's ids so both specs merge directly. | the task asks for the final demonstrated graph; grouping is segment b |
| a2 | A value read in a UI field beats narration and beats a pixel measurement: ramp positions 0.151 / 0.324 / 0.467 / 0.651 / 0.035 and the grey #999999 replace segment b's measured 0.155 / 0.314 / 0.469 / 0.645 / 0.02 and sampled #989898. | the Pos and Hex fields are visible in segment a while the stops are dragged or typed |
| a3 | The product node seen in the demo (0:00-3:36) is recorded as an interface only (defaults, factor-slider vs number field, demo values, narrated effect). Its internal destinations are given as C, matched by default values against the build; segment b holds the observed links. | segment a never sees inside the product group |
| a4 | Colours: the typed hex is the value; linear RGBA is computed with the sRGB transfer function and listed next to it. The picker HSV is recorded as a check. | Blender colour fields show display-space hex; the material stores linear values |
| a5 | Scene values are taken from the property panels (A), not from narration: Cycles GPU, Film Transparent, Filmic + Very High Contrast, 80 mm, 2560 x 2560, sun 15 / 6000 K / 0.526 deg, rim Area 300 W disk 1 m #FFEDE0, World Environment Texture fish_hoek_beach_1k.hdr strength 1. The HDRI is not downloaded (D6). | frames show these panels; D6 forbids downloads |
| a6 | Geometry for comparisons: ico sphere radius 0.5 m with scale applied, Subdivision Surface render level 3; both Subdivisions 6 (demo object) and 4 (build-file stats) are documented. | both are visible; the material only depends on object coordinates |
| a7 | Evidence: 65 full-resolution PNG frames (78 MB, re-decoded at exact times, names use the floor second) and 66 labelled crops (11 MB), every one cited in `evidence/a/index.json`; the 1-fps and multi-fps work frames stay in `tmp/materials_video/30vbbpy9zwg_work_a/`. | D7; "keep only frames the documents cite" |
| a8 | The 2 s after the segment end (26:12, zoomed-out graph) are used once to confirm the topology. | the task allows looking past the segment where the focus needs it |
| a9 | `evidence/a/.gdignore` added and the Godot-generated `*.png.import` side files in `evidence/a/` removed. The open Godot editor had imported the evidence PNGs because `tools/` lies inside the Godot project; the road tool's `tools/roads/crm_reconstruction/` uses a `.gdignore` for the same reason. Recommend one `.gdignore` at `tools/materials/reconstruction/` (docs step). | evidence is not game content; avoids editor imports and stray files |
