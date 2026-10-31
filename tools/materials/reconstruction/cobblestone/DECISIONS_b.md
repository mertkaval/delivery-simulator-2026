# Cobblestone video, segment b: decisions taken without the user

To be merged into `tools/materials/DECISIONS.md` by the docs step. Segment b = `30vbbpy9zwg` 26:10-40:41 (Node Group chapter and
closing) plus the intro 0:00-3:36 (finished look, product controls). Binding decisions D1-D11 were followed; nothing was built.

| # | decision | reason |
|---|---|---|
| b1 | The specification describes the group **built in the tutorial** (36 inputs, 5 panels, final state at 40:04-40:12). The purchasable file shown at 0:09-0:11 (34 controls, no Dirt Detail 1/2, "Cobblestone Size", "Moss Bump Strength", Rock Moss Detail 2 = 0.704, other order) is recorded as a variant only. | the task asks for the final demonstrated graph; the product file is never opened |
| b2 | The internal graph in `GRAPH_SPEC_b.*` is the complete material: grouping changed no node, link or value (A), so the nodes and values read while the controls were exposed (26:42-39:58) and in the 40:10 overview describe the final graph. | every group socket was created by dragging a node input onto the Group Input; demo drags and two temporary Value nodes were undone |
| b3 | One logical Group Input node in the spec; the tutorial's eight per-frame copies (Ctrl+H) are listed as UI only. Reroutes are optional. | both are functionally transparent |
| b4 | Colour defaults use the **narrated hex** (segment-a transcript), with the segment-b UI swatch as the frame check (agreement within 1-3 levels); linear RGBA is computed with the sRGB EOTF. | typed hex values are exact; swatch pixels carry video compression |
| b5 | Cobblestone Mask ramp: stop 0 = **#989898** at 0.000 (UI colour field, A) instead of the incomplete narration "6 9"; stop 1 black at **0.02** (bar measurement, C). | a typed #696969 would display as grey 105, the field shows 152 at 34:26 and 40:08; the black stop number is never displayed in segment b |
| b6 | Undisplayed ramp positions are measured from the stop markers on the ramp bar and calibrated where the same ramp shows a number: 0.155, 0.314, 0.469, 0.645 (C, +-0.01); 0.0 / 1.0 where the marker sits at an end. | no frame shows these values as numbers |
| b7 | The dirt Principled BSDF's unexposed Metallic / IOR / Alpha use Blender's defaults 0 / 1.5 / 1 (C). | hidden behind the sidebar in every zoomed view; the rock and moss BSDFs read exactly these values |
| b8 | Render engine recorded as Cycles (C), viewport samples 10 (A); scene values that are only narrated (sun 15 / 6000 K, disk rim light 300 W, fish_hoek_beach HDRI, 80 mm, 2560x2560, Filmic Very High Contrast) stay class B. | Cycles-only material settings are visible at 26:51; render properties are never opened in segment b |
| b9 | Evidence frames are re-decoded at exact times (listed in `evidence/b/index.json`, `frames`); file names use the whole second. 76 full-resolution PNG frames (101 MB) and 88 labelled crops (15 MB) are kept, every one cited; the 1 fps work frames stay in `tmp/materials_video/30vbbpy9zwg_work_b/`. | the 1 fps work extraction samples at N + 0.5 s (checked against exact seeks); D7 and "keep only frames the documents cite" |
| b10 | Where narration and a legible field disagree, the field wins: rock noise Bump Distance **0.007** (narration "0.7", 14:34). | task rule (A over B) |
