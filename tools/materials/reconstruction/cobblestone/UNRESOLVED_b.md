# Unresolved and ambiguous items, segment b (26:10-40:41)

Video `30vbbpy9zwg`. Class **D** = not readable or contradictory; **C** = our measurement or inference, given with the method so
the builder can judge it. Frames are in `evidence/b/frames/`, crops in `evidence/b/crops/`.

## D items

| # | item | what is known | what was tried | recommendation for the builder |
|---|---|---|---|---|
| U1 | Cobblestone Mask ColorRamp (`cell_ramp`), position of the black stop (index 1) | Stop 0 is selected at Pos 0.000 in every segment-b view (34:26, 40:08), so stop 1's number is never shown. The bar is grey only over its first few pixels, then black. | Pixel map of the bar: at 34:26 (`t3426_mask_ramp_color_field.png`, bar about 409 px wide, scaled from the 40:08 zoom by the +/- button spacing) the grey-to-black gradient ends about 8.5 px after the stop-0 marker, about 0.021; at 40:08 (`t4008_cobblestone_mask_ramp.png`, 210 px bar) it ends within 4 px, at most 0.019. | Use **0.02** (C, range 0.015-0.025). Segment a (21:28-21:56, where the black tab is dragged "pretty close") may show the exact value. |
| U2 | Cobblestone Mask ColorRamp, colour of stop 0 | The colour field of the selected stop reads **#989898** (152,152,152) at 34:26 and 40:08 (A, video compression about +-3). Narration 21:53-21:57: "a hex value of 6 9", word-level captions hold only "6" (21:56.96) and "9" (21:57.44), then about 1 s of untranscribed speech. | Compared with known swatches in the same UI: the roughness ramp stop narrated #D2D2D2 displays as #D1D1D1, Dirt Color 1 narrated #332C24 displays as #312D24, so UI fields show the typed hex faithfully. A typed #696969 would display as 105 grey, not 152. | Use **#989898** (A); treat the narration as incomplete. Re-check if segment a captures the hex field. |
| U3 | Icosphere subdivisions | Narration (4:17): "turn the subdivisions up to six". Status bar in every segment-b frame: Verts 642, Faces 1,280, Tris 1,280 with nothing selected (Objects 0/4). | 642/1,280 is exactly Blender's icosphere with subdivisions 4 (6 would be 10,242 verts). Subdivision Surface viewport level is 0 (narration 4:58), so the stats show the base mesh. | Unknown which is right; for a displacement test use a dense mesh (subdivisions 6 or the Subdivision Surface render level 3, narration 5:04). |
| U4 | Final render samples and render engine | Viewport shows "Sample n/10" (A, 40:14) and Cycles-only material settings (Emission Sampling, Volume Sampling / Interpolation, 26:51). Render properties are never opened in segment b. | Read viewport overlays at 0:30, 0:45, 0:57, 26:11, 26:53, 27:20, 40:13-40:15. | Engine **Cycles** (C); viewport samples 10 (A); final render samples unknown. |
| U5 | Group node input values in the material (40:12) | Only Material Scale = 1.000 is visible; the five panels are collapsed. | Checked 40:11-40:16; panels never reopened after 40:12. | Use the interface defaults (C): new sockets give existing group nodes their default value. |
| U6 | Dirt BSDF Metallic / IOR / Alpha | These unexposed fields are behind the sidebar in every zoomed segment-b view (30:58-31:02) and too small in the 40:10 overview. | Probed 30:58.5, 31:00.5, 31:02.5, 32:04.5-32:08.5, 40:09-40:10. | Blender defaults **0 / 1.5 / 1** (C), matching the rock and moss BSDFs, which read 0.000 / 1.500 / 1.000 (A, 39:12, 38:12). |
| U7 | Reroute nodes | Reroutes exist on the Linear Light -> Voronoi vector wire (33:30), on the mask -> Mix Rocks & Dirt / Displacement wire (35:50) and on long wires organised in segment a (19:10-20:01). | Not counted; they carry no value. | Optional; omit or add for layout only. |
| U8 | Socket subset of the Group Input copy in the Dirt Material frame | Text in the 40:10 overview is ~4 px high. | 40:09-40:10 frames at full resolution. | Cosmetic. The subset in the spec is inferred from the links (C). One Group Input node is enough. |
| U9 | Full socket descriptions | The Group tab shows them truncated (for example "The number o...e render time"). | Read every item; three inputs and the Displacement output have empty descriptions (A). | Copy Blender's tooltip of the source socket or leave empty; cosmetic. |
| U10 | Node locations, node widths, frame colours, frame sizes | Not recorded. | - | Layout is free. Frame labels and membership are in the spec (A). |
| U11 | bpy property behind "Bump Map Correction" (material Settings, 26:51) | The checkbox label is read (on); the API name is not shown. | - | Leave at its default (it showed on); verify the name in Blender 5.2 before setting it. |

## C items (measured or inferred values the builder will reproduce)

| item | value | method | uncertainty |
|---|---|---|---|
| `dirt_color_ramp` stop 0 (black) | 0.155 | marker centre along the bar at 32:36 (`t3236_dirt_bumps_wiring.png`); the same measurement gives 0.549 for stop 1, displayed 0.553 | +-0.01 |
| `dmoss_sharp_ramp` stop 1 (white) | 0.314 | marker centre along the bar at 32:36 | +-0.01 |
| `dmoss_ramp` stop 0 (black) | 0.469 | marker centre along the bar at 32:36 (stop 1 displayed 1.000) | +-0.01 |
| `rmmask_ramp` stop 1 (white) | 0.645 | marker centre at 37:20 (`t3720_moss_rock_mask_ramp.png`), calibrated with stop 0 displayed 0.407 | +-0.01 |
| `final_ramp` stop 0 (black) | 0.000 | marker at the left end of the bar at 35:50, only stop 1 (0.030) displayed | small |
| `dirt_rough_ramp` stop 1 (white) | 1.000 | marker at the right end of the bar at 32:36, bar white there | small |
| Colour defaults | narrated hex (segment a: 8:38-8:52, 12:21-12:25, 13:51-14:00, 16:30-16:36) | UI swatches in segment b agree within 1-3 levels per channel (A); narration gives the exact typed values | swatch +-3 |
| Render engine | Cycles | Cycles-only material settings visible at 26:51; viewport "Sample n/10" | - |
| Units | object space of a ~1 m sphere (narration 4:45-4:53: scaled 0.5 and applied) | Voronoi scale 7 gives stones about 0.14 m across | - |

## Contradictions resolved by the frames (for the record)

- Rock noise Bump Distance: narration 14:34 "turn it to a 0.7", field reads **0.007** (A, 38:36 and 39:12). The frame wins.
- The mask ramp grey (U2) is the only narration/frame conflict left open.
- 1 fps review frames were extracted with ffmpeg's fps filter, which samples t = N + 0.5 s (checked: frame 2150 matches an exact seek to
  2150.5 s with a mean difference of 0.74 levels against 4.6 at 2150.0 s). Every cited evidence frame was re-extracted at the exact time
  listed in `evidence/b/index.json` and checked against the reviewed view.

## Product file vs tutorial (not unresolved, a choice)

The intro (0:09-0:11) shows the purchasable file, whose interface differs slightly from the group the tutorial builds: no Dirt Detail
1/2, "Cobblestone Size" instead of "Cobblestone Individual Size", "Moss Bump Strength" instead of "Dirt Moss Bump Strength", Rock Moss
Detail 2 = 0.704 instead of 0.700, and a different order inside three panels. The spec follows the **tutorial's final group** (the
demonstrated graph); the product names are listed in `GRAPH_SPEC_b.md` so the builder can expose them as aliases if wanted.
