# Asphalt reconstruction (segment `all`) - local decisions

Made without the user while reverse-engineering `Eofg9SBcdBY` (00:00-27:08). To be merged into `tools/materials/DECISIONS.md` by the docs agent; binding decisions D1-D11 there were followed.

| # | decision | reason |
|---|---|---|
| A1 | The final graph is taken from the zoomed-out overview at 26:32 (whole tree visible); creation frames only document how and when each part was made. | The task asks for the final demonstrated graph, not a mix of intermediate states; the overview is the only frame with every node and wire. |
| A2 | Where the recipe repo and a legible frame disagree, the frame wins: base ramp stop 0 = `1A1817` (repo `#1A1A1A`); Bump #2 Height = base (Smooth F1) Voronoi Distance (repo: pebble Voronoi). Both values are kept in `UNRESOLVED_all.md` (U15, U16). | Task rule; both frame readings are unambiguous (on-screen captions and the wire path at 21:22-21:28 and 26:32). |
| A3 | Damage mask ramp black stop = 0.35 (class C). | Last legible value 0.343 is followed by a jump cut; pixel measurement after the cut gives 0.350 +-0.005 (U1). |
| A4 | Node types are recorded as the Blender 3.2 idnames seen in the video (`ShaderNodeMixRGB`, ...), each with an explicit `build_5x` mapping for Blender 5.2. | The spec describes the video; the builder works in 5.2. |
| A5 | Reroutes and frames are kept as `NodeReroute` / `NodeFrame` (layout only), plus a collapsed link list without reroutes. | Reroutes are functionally transparent; keeping them lets the builder reproduce the layout exactly. |
| A6 | Colours are stored as the sRGB hex shown on screen and as linear floats. | Blender hex fields are gamma corrected; ramp elements store linear values. |
| A7 | Evidence kept in `tools/`: 53 full-resolution PNG frames (66 MB) and 64 labelled crops (16 MB), every one cited. The 1-fps work frames (1628 JPEG) and sub-second samples stay in `tmp/materials_video/Eofg9SBcdBY_work_all/`. | D7 and "keep only frames the documents cite"; PNG was required by the task (optimised PNG saved nothing). |
| A8 | The group interface is a list of suggested `PM_Asphalt` controls (class C) built from the values the narration explicitly tunes (crack amount, crack width, damage amount, damage darkness, roughness minimum, colours, bump strengths) plus the D2/D4 contract inputs. | The video creates no group; D2/D4 need one. |
| A9 | Blender 5.2 notes come from a read-only headless 5.2.3 API probe (no file saved): Bump is created with Distance 0.001 (set 1.0), has a new Filter Width input; Principled default distribution is MULTI_GGX (set GGX); ramp / noise `Fac` sockets are named `Factor` (identifier `Fac`). | Avoid silent differences when the builder recreates the 3.2 graph. |
