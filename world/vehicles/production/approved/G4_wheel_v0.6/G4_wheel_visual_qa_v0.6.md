# G4 wheel assembly v0.6 — Independent Visual QA (revision 3 of 3)

Component: `player_sedan.wheel_assembly.R` (225/50 R17, OD 0.66 m, 7,920 tris LOD0 / 2,376 LOD1).
Inputs: eight renders in `production/renders/g4_wheel/` (all viewed), `g4_wheel_handoff.json` v0.6, `g4_wheel_notes.md` v0.6 section,
previous report `G4_wheel_visual_qa_v0.4.md`. Review only; no assets or scripts touched. Reviewer: Visual QA, 2026-10-19.

## Verdict: PASS WITH CONDITIONS — fit to the car. No geometry change is required before fitting.

The v0.4 P1 failures are closed. `wheel_face.png` / `wheel_face_vs_ref.png` now show five broad, flat, tapering wedges
(0.060 -> 0.105 m) on a small dome (r 0.072, 33 % of rim) with a dark, dished well behind them; the "rods on a trailer plate"
read is gone and the face is a credible modern alloy at 2 m. The caliper reads as a caliper through the 9 o'clock window.
Remaining items are a P2 cosmetic on the spoke tips and the already-declared in-engine checks; none justify escalation or a
fourth revision.

## Status of previous defects

| v0.4 # | Item | Status | Proving render / evidence |
|---|---|---|---|
| P1-1 | Hub plate oversized (r 0.110) | FIXED | `wheel_face.png`, `wheel_face_vs_ref.png`: dome r 0.072, windows now run to within ~15 mm of the lug circle; dome edge is a soft step, no 90-degree plate rim (`wheel_spoke_closeup.png`). |
| P1-2 | Blade proportion / tube section | FIXED (design deviation accepted) | `wheel_face.png`, `wheel_spoke_closeup.png`: single wedges 60 -> 105 mm, flat machined face, 3 mm chamfer, no cylindrical highlight, strong taper. Twin-spoke read comes only from the 6 mm centre groove: clear in the closeup, faint in `wheel_34.png`, invisible beyond ~5 m. Reads as a 5-spoke rather than the reference's 5 twin-spoke; see note on window ratio below. |
| P1-3 | Caliper does not read | FIXED (face) / unchanged (rear) | `wheel_caliper_window.png`: curved body straddling the disc edge, bridge, bolt boss and pad edge visible between the 9 and 10 o'clock spokes; also visible in `wheel_34.png` behind the left spokes. From inboard (`wheel_rear_brake.png`) the r 0.14 shield still hides disc and caliper completely (caliper reaches only r 0.157 / x -0.028). Acceptable: the inboard side is inside the arch. |
| P2-4 | Face depth | FIXED | `wheel_face.png`: 35 mm dish and darkened SteelDisc/ShieldSteel make the windows read as shadowed depth; disc remains the brightest element behind the face, which is plausible. |
| P2-5 | Decal tick z-fight | NOT TESTABLE HERE (unchanged) | `wheel_tread_closeup.png`: 96 ticks crisp, zero-depth, 0.4 mm proud; no artefacts in EEVEE. Must be checked in Godot at 5/10/15 m. |
| P2-6 | LOD1 pop | IMPROVED | `wheel_lod1_34.png`: four grooves and both ribs present as geometry, spoke count/positions match LOD0. Tyre is a visible 24-gon (chord facets along the whole outline); pop will be seen below ~15 m. |
| P2-7 | Plain centre ribs | NOT FIXED | `wheel_34.png`, `wheel_tread_closeup.png`: three centre ribs still slick. Carried to the texture task; not blocking. |
| P2-8 | Flat sidewall band | FIXED | `wheel_34.png`: continuous sidewall curve, ribs at 1.2 mm read as subtle lines, no raised annulus. |
| P3-9 | Pocket / cap faceting | FIXED | 16-gon pockets, 24-gon cap; no visible faceting in `wheel_spoke_closeup.png`. |
| P3-10 | Inner rim flange bright polygonal annulus | NOT FIXED | `wheel_rear_brake.png`: flange is still a wide mid-grey ring with chord facets visible at 10-11 o'clock; shield edge also faceted. Inboard-only, P3. |
| P3-11 | DustShield material slot | FIXED | `ShieldSteel` slot in handoff and re-import hierarchy. |
| P3-12 | LOD1 radius_max +1 m bug | FIXED | handoff lod1.*.radius_max now root-local (Tyre_LOD1 0.33). |
| P3-13 | Disc-band speckle | RESOLVED | No speckle in v0.6 closeups; was render noise. |

## Open-window ratio (engineer-declared 51.5 % vs ~35 %)

Judged against `wheel_face_vs_ref.png`: the reference face is visibly fuller (spoke pairs nearly meet at the hub, windows are
dark slots); ours shows much more brake through the windows and the five spokes dominate. At vehicle scale (2-15 m) this
reads as a clean sporty 5-spoke alloy, not as an error; the deviation is from the styling intent, not from plausibility.
Accepted. If a fuller face is ever wanted it is a parameter-only change (spoke_w_rim ~0.13 or 10 spokes), not a defect fix.

## New defects (v0.6)

### P2
1. **Spoke tips sit proud of and overhang the lip.** With `face_lift` +5 mm and tips at r 0.214 the straight-cut tip ends
   cross the rolled lip's inner edge; the lip ring is interrupted where each spoke passes it and the tip corners stand
   outboard of the lip with a hard shadow. The spokes read as planks laid on the rim rather than cast with it.
   Evidence: `wheel_spoke_closeup.png` (upper-left spoke tip, ~x 290-340, y 230-470), `wheel_face.png` (3 o'clock tip,
   straight chord against the curved lip), `wheel_34.png` (left spoke tips, 9-10 o'clock). Fix is parameter-only:
   `face_lift` 0.005 -> 0.000-0.002 and arc-cut or round the tip ends so the lip rings them. Does not block fitting.

### P3
2. Lug nuts read as proud cylinders on the dome; the 1 mm recess into the 16-gon pockets is not perceptible even in the
   closeup (`wheel_spoke_closeup.png`, bosses at the lug circle). Reference nuts sit in clearly dark pockets.
3. Centre-groove terminations show a small bright notch where the groove runs out at the dome and at the tip
   (`wheel_spoke_closeup.png`, ~x 500, y 620). Cosmetic.
4. Caliper/lip/spoke-tip shells interpenetrate (declared). No visible clipping in any render; keep as a note for the
   game-asset engineer in case of shadow acne in Godot.

## Required before fitting
Nothing. Fit v0.6 to the car as is.

## Conditions (must be closed at G5 / in-engine sign-off, not by a further studio revision)
1. Godot render set at 2 / 8 / 15 m with the project environment: decal tick z-fight (P2-5) and metal read (Alloy, Chrome,
   SteelDisc). If flicker appears, raise the tick offset to ~1.5 mm or bake the ticks.
2. LOD0 -> LOD1 switch capture; set the transition at >= 15 m (24-gon tyre).
3. Parameter-only follow-up for the spoke-tip lift (new P2-1) may ride along with the G5 material pass; it must not change
   spoke widths, dome radius or budgets, and must re-run the existing checks and re-render `wheel_face.png` /
   `wheel_spoke_closeup.png`.
4. Carry P2-7, P3-10, P3-2/3 to the texture/polish backlog.

Uncertainty: all judgements are from the grey studio renders without HDRI; material and highlight reads will shift in Godot
and should be re-judged there. Pixel estimates are approximate (+-3 %).
