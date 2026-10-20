# G4 wheel assembly v0.4 — Independent Visual QA

Component: `player_sedan.wheel_assembly.R` (225/50 R17, OD 0.66 m, 7,724 tris LOD0 / 2,314 LOD1)
Inputs reviewed: six renders in `production/renders/g4_wheel/`, `g4_wheel_handoff.json`, `g4_wheel_notes.md`,
`references/ref_left_side.webp`, `references/ref_front.webp`. Review only; no assets or scripts touched.
Reviewer: Visual QA, 2026-10-19.

## Verdict: FAIL (rim face design). Tyre and brake sub-assemblies would pass with conditions.

The build is mechanically clean (budgets, concentricity, manifold, round-trip all hold and the renders confirm no
visible holes, flips or misalignment). What fails is the thing the director asked v0.4 to fix: the rim face does not
read as the reference's 5 twin-spoke alloy. It reads as ten slender rounded bars laid on an oversized flat plate.
That is a design/proportion failure of the primary visible surface, not a polish item, so the wheel should not be
fitted to the car until the face is re-proportioned and re-rendered.

## Criteria table

| # | Criterion | Judgement | Evidence (render) | Notes |
|---|-----------|-----------|-------------------|-------|
| 1a | Spoke blade width / pairing / taper vs reference | FAIL | `wheel_face.png`, `wheel_spoke_closeup.png` vs `ref_left_side.webp` | Reference pairs are broad flat wedges that merge into one spoke at the hub and split toward the rim; each pair is ~2x wider at the rim than at the hub. v0.4 blades are 32 -> 42 mm (only ~30 % taper), keep a constant 22 mm slot open all the way to the plate, and the dish + 2-seg chamfer makes each blade shade like a round tube (`wheel_face.png`, all ten blades show a cylindrical highlight). Reads as rods, not blades. |
| 1b | Hub plate | FAIL | `wheel_face.png`, `wheel_spoke_closeup.png` | Plate r 0.110 m = 0.22 m dia on a 0.432 m rim (~51 %). Pixel estimate on `wheel_face.png`: plate ~260 px vs lip ~600 px (~43 % of visible rim opening). Reference centre boss is ~30 % of the rim. The plate dominates the face and shortens every spoke window; combined with the hard 90-degree plate edge (`wheel_spoke_closeup.png`, left) it reads as a steel wheel / trailer hub. |
| 1c | Lug nut read | PASS (minor) | `wheel_face.png`, `wheel_spoke_closeup.png` | 5 chrome hexes in pockets, correctly on PCD, visible at face distance. Pocket walls are low-poly (~12 segments, visible facets in the closeup). |
| 1d | Rim well depth | PASS WITH CONDITIONS | `wheel_spoke_closeup.png`, `wheel_face.png` | Well, conical step and dark floor are present and read behind the blades. But the bright, flat SteelDisc/DustShield fills the windows and flattens perceived depth; the 20 mm dish is barely perceptible in `wheel_face.png`. Needs a 30-40 mm dish and a darker back-plane to read as a modern alloy. |
| 2a | Rim lip | PASS | `wheel_spoke_closeup.png`, `wheel_face.png` | Rolled lip is a convincing thin bright ring with a dark bead gap outside it. Blade tips terminate correctly at the lip; no visible protrusion. |
| 2b | Tyre shoulder / sidewall | PASS WITH CONDITIONS | `wheel_34.png`, `wheel_face.png`, `wheel_rear_brake.png` | Shoulder arc and rim-protector rib are plausible. Outer sidewall between the two lettering ribs reads as a flat annular band with a hard edge (`wheel_34.png`, 2-5 o'clock) rather than a continuous sidewall curve; at 2 m it resembles a raised whitewall band. Inner sidewall shows stepped shoulder facets (`wheel_rear_brake.png`, top right). |
| 3a | Tread read at 2-15 m | PASS WITH CONDITIONS | `wheel_34.png` | Four circumferential grooves + outer-rib ticks give a credible directional-touring pattern at 3/4 view. Three centre ribs are completely plain, so at 2-4 m the tyre reads half-slick. |
| 3b | Tread close-up | PASS WITH CONDITIONS | `wheel_tread_closeup.png` | Decal ticks are crisp but obviously zero-depth (no shadow on the cut wall, no sidewall relief), uniform length and angle; they stop short of the shoulder so the shoulder block edge never breaks the silhouette. Acceptable for budget, but the 0.4 mm proud offset is a z-fight risk at 10-15 m in Godot's depth buffer — must be checked in engine. |
| 4a | Disc / caliper visible and plausible from the face | FAIL (caliper) / PASS (disc) | `wheel_face.png`, `wheel_34.png`, `wheel_spoke_closeup.png` | Disc edge and vanes show through the windows (good). The caliper does not read as a caliper: from the face it is a flat light-grey sheet with two small bosses at 9 o'clock, mostly hidden behind the plate, with no visible body depth or pad bridge. From the rear it is a plain dark wedge. Handoff lists Caliper `radius_max` 0.088 m against a 0.150 m disc; something about its radial placement or the metric is wrong — verify it actually straddles the disc edge. |
| 4b | Dust shield | PASS WITH CONDITIONS | `wheel_rear_brake.png` | Shield is a large matte dish with hub stub; plausible from inside the arch. It hides the disc entirely from the rear (only ~10 mm of disc should show, and none does), and uses the `Rubber` slot, so it will take tyre material changes. Inner rim flange renders as a wide, bright, visibly polygonal annulus (left side of the ring) that reads like a hubcap ring. |
| 5 | LOD1 silhouette vs LOD0 | PASS WITH CONDITIONS | `wheel_lod1_34.png` vs `wheel_34.png` | Outer outline, hub position and spoke count match. Tyre silhouette is visibly polygonal (chord facets along the whole outer edge), all grooves and ticks are gone (round-trip hierarchy shows `Tyre_LOD1` lost the `RubberCut` slot), spokes become flat boxes and the face loses its dish. Expect a visible pop at the LOD switch unless the transition distance is >= 20 m. |
| 6 | Faceting / interpenetration / flat shading / symmetry | PASS WITH CONDITIONS | `wheel_spoke_closeup.png`, `wheel_rear_brake.png`, `wheel_lod1_34.png` | Blade roots now sink into the plate; the blade/plate and blade/lip interpenetration seams are visible only in the closeup as a thin bright line and are acceptable. Faceting visible on lug pockets, centre cap rim, inner rim flange and LOD1 tyre. Speckled noise along the disc outer band in the closeup should be confirmed as EEVEE shadow noise and not a coplanar disc/shield surface. Five-fold symmetry is correct; no odd blade. |
| 7 | Credible as a modern sim-game wheel at 7.7 k tris | FAIL | all | Tyre is credible. The face is not: the budget is there (2,864 rim tris) but it is spent on a thick plate, chamfered rods and a 1,344-tri barrel rather than on wide, dished, faceted-to-shape spokes. A player will see this wheel from 2 m every time they walk to the car. |

## Prioritised defects

### P1 — blocks fitting
1. **Hub plate oversized** — `RimFace`, plate r 0.110 m. Reduce to r ~0.065-0.075 m (30-35 % of rim dia) so the spoke windows reach toward the centre as in `ref_left_side.webp`. Evidence: `wheel_face.png`.
2. **Blade proportion and section** — `RimFace` blades 0.032 -> 0.042 m. Target: each blade ~0.025 m at the hub widening to ~0.055-0.060 m at the rim, flat top face with a single small chamfer (remove the tube-like highlight), pair slot tapering to zero or near-zero at the hub so the pair reads as one split spoke. Evidence: `wheel_face.png`, `wheel_spoke_closeup.png`.
3. **Caliper does not read** — `Caliper`, 136 tris. Needs a visible body block (bridge + outboard half) that shows through the window at 9 o'clock from the face and wraps the disc edge from the rear; verify radial placement (`radius_max` 0.088 m vs disc 0.150 m). Evidence: `wheel_face.png`, `wheel_rear_brake.png`.

### P2 — fix before G5 / in-engine sign-off
4. **Face depth** — increase blade dish to 30-40 mm and darken the back-plane (SteelDisc/DustShield albedo or a darker hub face) so the windows read as shadowed depth. Evidence: `wheel_face.png`, `wheel_spoke_closeup.png`.
5. **Decal tick z-fight risk** — 96 `RubberCut` quads 0.4 mm proud. Confirm in Godot at 5, 10, 15 m with the project camera near/far; if flicker appears, raise the offset to ~1.5 mm or bake the ticks into the Rubber material. Evidence: `wheel_tread_closeup.png`.
6. **LOD1 pop** — LOD1 tyre has no grooves and a visibly polygonal outline. Either add the 4 grooves as a texture band on `Tyre_LOD1` or push the switch distance out. Confirm whether `Tyre_LOD1` is meant to lose the `RubberCut` slot (handoff build table says two slots, reimport says one). Evidence: `wheel_lod1_34.png`.
7. **Plain centre ribs** — three centre ribs have no sipes/cuts; add a sparse offset sipe decal row on the centre rib or accept as a texture task. Evidence: `wheel_34.png`.
8. **Flat sidewall band** — the band between the two lettering ribs reads as a flat raised annulus at 3/4; soften the rib heights (1.5 mm -> ~0.8 mm) or break them into a lettering texture. Evidence: `wheel_34.png`.

### P3 — polish
9. Lug pockets and centre cap rims show ~12-gon faceting in the closeup; +8 segments each is cheap. Evidence: `wheel_spoke_closeup.png`.
10. Inner rim flange is a wide, bright, polygonal annulus from the rear; narrow it and give it the `RimWell` dark value. Evidence: `wheel_rear_brake.png`.
11. DustShield shares the `Rubber` slot; give it its own `ShieldSteel` slot so tyre material tweaks do not recolour it.
12. Handoff metric bug: every `lod1.*.radius_max` is inflated by +1.0 m (e.g. Tyre_LOD1 1.33, Caliper_LOD1 0.9134) because the +1 m root offset is not subtracted. Report only; no geometry impact.
13. Speckle along the disc outer band in `wheel_spoke_closeup.png` — confirm it is render noise, not a coplanar face with the shield.

## Required before this wheel is fitted to the car
1. Rework `RimFace` per P1-1, P1-2 and P2-4 (smaller plate, wide flat tapering split-spokes, deeper dish). Re-render `wheel_face.png` and `wheel_spoke_closeup.png` side by side with a crop of `ref_left_side.webp` at matched scale.
2. Rework `Caliper` per P1-3 and add one render looking through the spoke window at 9 o'clock from 1.5 m.
3. One in-engine render set (Godot, project HDRI/environment, 2 m / 8 m / 15 m) covering the decal tick z-fight check (P2-5) and the metal read the engineer already flagged.
4. One LOD0 -> LOD1 switch capture at the intended transition distance (P2-6).
5. Keep all existing automated checks green (budgets, concentricity, manifold, round-trip); the rim budget headroom (636 tris) is sufficient for the face rework.

Re-review on resubmission; tyre and brake-side items in P2/P3 can ride along to G5 if the P1 items are closed.
