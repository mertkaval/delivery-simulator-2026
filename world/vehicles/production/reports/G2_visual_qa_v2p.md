# G2 Visual QA — body shell v2p (sedan_v2_body.glb), re-review of v2k

Independent Visual QA, 2026-10-19. Reviewed: 7 clay renders + 2 orthographic arch close-ups in `renders/g2_body_v2p/`, `metrics.json` (bounds 1.857 x 4.84 x 1.448 m, 83 844 tris, Body flat_faces 1200), `dimension_sheet.md`, previous reports `G2_visual_qa_v2d.md` and `G2_visual_qa_v2k.md`. Scope unchanged (shell only, placeholder wheels, 0.66 m tyre target). Every item in the engineer's change list was checked against the renders; nothing is taken on trust.

Measurement basis. `clay_left.png`: car spans x 59→1144 px for 4.84 m → **224.4 px/m**; ground (tyre bottom) y = 534; height 326 px = 1.453 m (metrics 1.448). Front/rear views ≈512 px/m. Top view ≈220 px/m. Arch close-ups 833 px/m (1000 px = 1.2 m). Stations are metres from the front bumper face; note the nose is 40 mm long (metrics Y max 2.365 vs 2.325), so sheet stations referenced to the nose read 40 mm further back in this build.

## Overall verdict: **PASS WITH CONDITIONS**

Both carried-over P1 items are closed: the arch cut edges are clean circles (verified at 833 px/m on both close-ups, no stair-steps in any of the nine renders) and a continuous shoulder crease now runs from the fender to the quarter at the correct rise. Proportions, silhouette, tail, bumper surfaces, panel flushness and symmetry hold. G3 (surface detailing) may start. Conditions: three P2 items below (front-bumper chamfer fold, liner tabs below the sill, shoulder line sitting 40–70 mm above the handle heights) must be closed and shown in the first G3 render set; the P3 list carries into G3.

## Criteria table

| # | Criterion | v2k | v2p | Evidence render | Observation (v2p) |
|---|---|---|---|---|---|
| 1 | Proportions / stations | PASS | **PASS** | clay_left, metrics.json | L 4.84 (+40 mm, all at the nose — engineer-acknowledged), W 1.857 (+7 mm), H 1.448. Tyre contact centres 0.923 m and 3.786 m from the nose → wheelbase **2.863** (target 2.85), front overhang 0.92 (0.90 + the 0.04 nose), rear overhang 1.054 (1.05). Cowl 1.25 m at Z 1.00–1.02; windscreen top ≈2.27 m; roof peak Z 1.453 over 2.67→2.90 m; roof end ≈3.40 m; screen end 4.19 m at Z 1.105; trunk lid flat at Z 1.105 from 4.19 to 4.45 m then falls to the lip Z 1.04–1.065 at 4.68 m (sheet 1.10/1.02). Shut lines 1.30 / 2.54 / 3.61 m = 0.269 / 0.525 / 0.747 L (sheet 0.284 / 0.541 / 0.763): unchanged from v2k, 70–100 mm ahead of the sheet, mutually consistent — recorded as P3. |
| 2 | Side silhouette | PASS | **PASS** | clay_left, clay_right | Windscreen fit x 360–540: **24.9°** (resid 2.8 px); rear screen fit x 840–1000: **22.8–23.1°** (target ≈20°, acknowledged); hood 9.0°, trunk −5.7°. Roofline continuous; left and mirrored right silhouettes agree within 5 px on every sampled row. |
| 3 | Surface quality (incl. bumper faces) | PARTIAL | **PASS (one P2)** | clay_front, clay_rear, clay_front_34, clay_rear_34 | Rear bumper face and tail-lamp zone smooth (contrast-stretched clay_rear y 150–470 and y 400–744). Hood, roof, door and quarter skins smooth. Rear-screen base fold from v2k is blended out — only a soft dip remains at the screen's lower corners (clay_rear_34 x≈747–793, y≈407–430). Remaining: on the front bumper the new lower chamfer meets the plan-rounded corner in a diagonal fold (clay_front x≈930–1010, y≈470–640; mirror x≈190–270 in shadow) — P2. Cowl/A-pillar base now an S-ripple instead of a notch (clay_top x≈185–200, y≈195–230 and y≈515–550; clay_front_34 x≈180–230, y≈245–285) — P3. |
| 4 | Character lines | PARTIAL | **PASS (one P2)** | clay_left, clay_front_34, clay_rear_34 | A single crease runs continuously fender → front door → rear door → quarter (contrast-stretched clay_left x 340–900; clay_front_34 shows it as a light break with the shut lines jogging where they cross it, i.e. it is proud). Height from the vertical gradient scan: Z 0.87 at 1.88 m, 0.87–0.90 at 2.23 m, 0.92–0.94 at 3.12 m, 0.93–0.945 at 3.39 m — rising front→rear as the sheet asks. At the handle stations the sheet wants Z 0.83 (front door) and 0.865 (rear door); measured ≈0.88 and ≈0.93, i.e. **40–70 mm high**. A straight 0.80→0.95 line between Y +2.0 and −2.0 cannot pass through both handle heights; the line needs a slight bow (or the sheet's handle Z must move) — P2 because G4 handle placement depends on it. Belt-edge crease and sill tuck-under present. |
| 5 | Wheel arches Ø0.74, round, concentric, clean edge | FAIL | **PASS (one P2)** | arch_front_left, arch_rear_left, clay_left, both 3/4 views | Close-ups: tyre light run at row 600 = 227→776 px = **0.659 m** (front) / 223→772 (rear); arch lip top at y = 294 → radius 305 px about the tyre centre (x≈501, y≈599) = 0.366 m → **Ø≈0.73 m**, lip points at (731,400) and (689,420) lie on the same circle (r = 304–305 px) → round and concentric within ≈5 px (6 mm). 30 mm flange reads as a 25–42 px dark ring. **No stair-steps anywhere** on the lip in either close-up or in clay_left / clay_front_34 / clay_rear_34 (near and far arches). Residual: liner clipped at the sill but the clipped edge shows as small flat tabs below the sill either side of the tyre (arch_front_left x≈228–262 and 745–780, y≈712–740; arch_rear_left x≈225–260 and 740–775, y≈712–740; also visible in clay_rear_34 x≈620–650, y≈610–650) — P2. Tiny nick where the rear-door shut line meets the rear arch flange (arch_rear_left x≈355–385, y≈320–350) — P3. |
| 6 | Panel separation | PARTIAL | **PASS** | clay_top, clay_front_34, clay_rear_34, clay_left | Plan outline is straight: top-view half-width 206.5–208.5 px about a constant centre row 372.5 from x 250 to 950 (Y 0.9→4.1 m) — no waist; the v2k fender/quarter flares are gone. Fender/door and door/quarter shut lines read as gaps, not ledges (clay_front_34 x≈630–660, y≈400–620; clay_rear_34 x≈440–470, y≈310–560); the jog at the shoulder crease is the expected kink of a gap crossing a proud line. B-pillar and door shut lines now run up to the cant rail (clay_front_34 x≈400–450, y≈220–300; clay_rear_34 x≈470–520, y≈240–300). Hood perimeter, trunk perimeter, bumper splits (0.335 m and 4.43 m) present. Hood gap lines still stop short of the hood leading-edge line (clay_front x≈215–285 and 915–985, y≈240–300 vs centre line y≈295) — P3. |
| 7 | Nose and tail form | PARTIAL | **PASS** | clay_left (x 59–125 and 1100–1144), clay_front, clay_front_34 | Nose: hood edge Z 0.80–0.86, vertical band Z 0.70→0.50 (0.20 m, was 0.27), then a raked lower face from Z≈0.50 down to Z 0.17 with 0.285 m setback (≈48° from vertical) — the claimed "chamfer from 0.55 m" is measured at ≈0.50–0.53. Most-forward band Z 0.50–0.70 vs sheet 0.35–0.55: still ≈0.15 m high but the nose now has a rake and a lower step. Tail unchanged from v2k: lip → raked upper → vertical band Z 0.78–0.43 → tuck-under; smooth. |
| 8 | Symmetry | PASS | **PASS** | clay_front, clay_rear, clay_top, clay_left vs mirrored clay_right | Outline mid-x (background threshold 15) = 599.0–601.5 on every row y 260–620 in both clay_front and clay_rear (≤2 px ≈ 4 mm). Top-view centre row 372.5 ± 1 from x 250 to 950. Mirrored right view matches the left within 5 px. The 6 px nose-to-tail length difference between the left and right renders (1086 vs 1092 px) is identical to v2k and the rear outline is symmetric, so it is camera framing — keep as a P3 eye-check only. |

## Status of previous defects (v2k report numbering)

| v2k # | Defect | Status | Proof |
|---|---|---|---|
| P1-1 | Arch cut edges sawtoothed on all four arches | **FIXED** | arch_front_left / arch_rear_left: continuous circular lip at 833 px/m; clay_left x 176–347 / 817–990; clay_front_34 near arch x 660–720, far arch x 190–215; clay_rear_34 near x 630–690, far x 190–230 — no teeth |
| P1-2 | Shoulder character line absent | **FIXED** (height at the handle stations 40–70 mm above the sheet — new P2-3) | clay_left gradient breaks at y 333–342 (Z 0.87–0.90, front door) and y 322–329 (Z 0.93–0.945, rear door); clay_front_34 light break along the whole side |
| P2-3 | Arch liners: straight-cut disc hanging below the sill | **IMPROVED** — clipped at the sill, but the clipped edge still shows as flat tabs below the sill line | arch_front_left x 228–262 / 745–780, y 712–740; arch_rear_left same rows; clay_rear_34 x 620–650, y 610–650 |
| P2-4 | Panels not flush at the shut lines / waisted plan | **FIXED** | clay_top half-width constant 206.5–208.5 px x 250→950; clay_front_34 x 630–660; clay_rear_34 x 440–470 |
| P2-5 | Fold along rear-screen base, C-pillar base dent | **FIXED** (soft dip at the screen lower corners only — P3) | clay_rear_34 x 700–900, y 350–450 |
| P2-6 | Nose a radiused vertical box | **IMPROVED → accepted** (raked lower face present; most-forward band still Z 0.50–0.70) | clay_left front profile y 376–496 |
| P2-7 | Front bumper top-corner fold | **IMPROVED** at the top corner; a new fold appears lower down where the chamfer meets the plan rounding (new P2-1) | clay_front x 930–1010, y 470–640 |
| P2-8 | No DLO / pillar definition | **NOT FIXED** — acknowledged, planned for G3 | clay_front_34, clay_rear_34 |
| P3-9 | Rear screen 23° vs 20° | **NOT FIXED** — acknowledged | clay_left fit x 840–1000 |
| P3-10 | Hood gap lines end in open surface | **NOT FIXED** | clay_front x 215–285 / 915–985, y 240–300 |
| P3-11 | Cowl / A-pillar base notches | **IMPROVED** (now a soft S-ripple) | clay_top x 185–200, y 195–230 / 515–550 |
| P3-12 | L/R render length 6 px | **unchanged**, framing | clay_left 59→1144 vs clay_right 54→1145 |
| P3-13 | Rear bumper rearmost band Z 0.43–0.79 | **unchanged** (G4 placement note) | clay_left tail profile |

## Defects in v2p, prioritised

### P1 — blocking
None.

### P2 — conditions on the G3 start (close in the first G3 render set)
1. **Front bumper chamfer-to-corner fold.** The raked lower face terminates against the plan-rounded corner in a diagonal crease — clay_front x≈930–1010, y≈470–640 (right side; left side x≈190–270 is in shadow and must be checked in Blender). Blend the chamfer around the corner or end it in a deliberate, mirrored edge.
2. **Arch liner tabs below the sill.** Flat tabs of the clipped liner protrude below the sill line both sides of each tyre — arch_front_left x≈228–262 and 745–780, y≈712–740; arch_rear_left x≈225–260 and 740–775, y≈712–740; clay_rear_34 x≈620–650, y≈610–650. Trim the liner to the sill underside (or recess it 20 mm inboard of the sill).
3. **Shoulder line height at the handle stations.** Measured Z≈0.88 at the front-door handle station (≈2.3–2.55 m from the nose) and ≈0.93 at the rear-door handle station (≈3.45–3.7 m) against the sheet's 0.83 / 0.865. Either bow the line (0.80 at the headlamp top → 0.83 at the front handle → 0.865 at the rear handle → 0.95 at the tail-lamp top) or raise the sheet's handle Z values before G4; G4 handles must sit on the line.

### P3 — carry into G3
4. Nose 40 mm long (metrics Y max 2.365) — acknowledged; the front overhang is 0.92 m until corrected.
5. Rear screen 23° vs 20° — acknowledged; acceptable as fastback intent.
6. Hood gap lines still stop in open hood surface (clay_front x≈215–285 / 915–985, y≈240–300); the cowl line also has a small zig at x≈265–280, y≈217–225.
7. Cowl / A-pillar base S-ripple (clay_top x≈185–200, y≈195–230 and y≈515–550; clay_front_34 x≈180–230, y≈245–285).
8. Soft dip at the rear-screen lower corners (clay_rear_34 x≈747–793, y≈407–430).
9. Nick where the rear-door shut line meets the rear arch flange (arch_rear_left x≈355–385, y≈320–350) and a small notch at the top of the fender/door shut line on the silhouette (clay_left x≈350–354, y≈308–312).
10. Rear bumper lower-right corner shows a small step at the skirt edge (clay_rear x≈1010–1030, y≈625–645); left side in shadow — eye-check both in Blender.
11. Shut-line stations 70–100 mm ahead of the sheet (0.269/0.525/0.747 L vs 0.284/0.541/0.763) — consistent across builds; either accept and update the sheet or shift all three together.
12. Trunk lid runs dead level at Z 1.105 for 0.26 m behind the screen before falling to the lip; the sheet implies a continuous fall 1.10→1.02. Cosmetic.
13. DLO / A-B-C pillar definition — planned G3 item.
14. Left/right render length 6 px — confirm camera framing once.
15. Placeholder rims flat-shaded — acceptable.

## Deferred to G4 (unchanged)
Lamps, grille, intakes, fog bezels, reflectors, diffuser, exhausts, sensors; mirrors, handles (place on the shoulder line, see P2-3), fuel flap, shark-fin, trim, badges; detailed wheels and brakes; interior and glass; hood power bulges.

## Gate statement
**G2 body shell: PASS WITH CONDITIONS. G3 (surface detailing) may start on v2p.** Conditions: P2-1, P2-2 and P2-3 are closed and demonstrated in the first G3 render set (same seven cameras plus the two arch close-ups); no further G2 re-review is required unless the arch flange or shoulder-line topology is reopened. P3 items 4–14 are to be tracked in the G3 log. Criteria 1, 2, 6, 8 need only a regression glance at the G3 gate.
