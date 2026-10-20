# G2 Visual QA — body shell v2d (sedan_v2_body.glb)

Independent Visual QA, 2026-10-19. Reviewed: 7 clay renders in `renders/g2_body_v2d/`, `metrics.json`, 4 references, `dimension_sheet.md` (sections 1–4, 6). Measurements below were taken from the orthographic `clay_left.png` (car spans x 52→954 px = 4.736 m, so ≈190 px/m; ground at y≈448) and from mirror-difference / outline masks of `clay_front`, `clay_rear`, `clay_top`. Wheel size vs reference is NOT judged (C1 in the sheet).

## Overall verdict: **FAIL**

Five of eight criteria fail. The shell has the right overall box (L/H/wheelbase/nose and cowl heights land on the sheet), the shut lines are at the right stations and the body is left/right symmetric, but the greenhouse is the wrong shape (upright windscreen, long flat roof, steep short rear screen — a notchback, not the fastback on the sheet), all four wheel arches are sawtoothed, oversize and flat-topped, the tail is a vertical slab with a visibly wavy surface, and there is no shoulder line. These are G2-scope proportion/surface defects, not missing G4 assemblies.

## Criteria table

| # | Criterion | Verdict | Evidence render | Observation |
|---|---|---|---|---|
| 1 | Proportions / stations | **FAIL** | clay_left, metrics.json | L 4.736 (−64 mm), W 1.926 (+76 mm over 1.85), H 1.448 OK; wheelbase ≈2.88 m (+1 %); front overhang ≈0.83 m (target 0.90), rear ≈1.04 OK; nose 0.77 m, cowl 0.26 L / 1.00 m, roof peak 0.58 L, screen end 0.888 L, trunk lid 1.09 m all OK — BUT windscreen top at ≈0.42 L (≈2.0 m vs 2.25) and roof end at ≈0.77 L (≈3.65 m vs 3.42). Greenhouse 0.25 m too far forward at the front and 0.23 m too long at the back. |
| 2 | Side silhouette | **FAIL** | clay_left, clay_right | Roofline continuous, belt line clean (no steps). Windscreen measures ≈29–31° from horizontal (target 24–28); rear screen ≈26–28° over a short 0.5 m run (target 20°, fastback). Profile reads as an upright three-box notchback with a long flat roof (0.42→0.76 L), not the reference's fastback. |
| 3 | Surface quality | **FAIL** | clay_rear, clay_front, clay_rear_34 | Rear bumper face: scalloped/wavy reflection boundary across the full width (clay_rear y≈420–480) = surface waves; creases at both tail-lamp corners (clay_rear x≈250–330 y≈200–260 and x≈650–735 y≈200–275). Front: diagonal fold on the bumper top corner (clay_front x≈230–330 y≈250–310, mirrored right), vertical pinch at the fender/headlamp corner (clay_front x≈105–150 y≈190–300). Rear 3/4: pinch where the rear screen meets the quarter and a surface step at the rear-door trailing edge (clay_rear_34 x≈560–600 y≈330–400). Hood, roof and door skins themselves are smooth; no faceting on main panels (193 flat faces in Body are at the arch cuts). |
| 4 | Character lines | **FAIL** | clay_left, clay_right, clay_front_34 | Body side between belt and sill is a flat featureless slab; the reflection strip shows no shoulder break anywhere along the doors. Only "shoulder" is the rolled top edge at the belt. Sill tuck-under IS defined (dark band clay_left y≈400–415; ledge visible in clay_front_34). Shoulder line: missing. |
| 5 | Wheel arches | **FAIL** | clay_left (x 120–300), clay_front_34 (x 520–720 y 400–600), clay_rear_34 (x 480–680 y 400–600) | Pronounced sawtooth (≈12 teeth per arch) on the arch cut edge of all four arches. Opening ≈0.9 m dia vs 0.74 m target — clearance ring ≈0.11 m all round. Arch top is flat/truncated (clay_left x≈193–220 y≈298) because it nearly reaches the fender top. Arch liner is a flat disc with a straight vertical cut at the trailing side (clay_rear_34) and pokes below the sill on the far side (clay_front_34 x≈140–170 y≈380–410). Tyres are concentric with the arch centre. |
| 6 | Panel separation | **PASS** | clay_left, clay_top, clay_front | Fender/door gap at 0.267 L, B-pillar 0.537 L, rear door 0.768 L (sheet 0.284/0.541/0.763), straight and vertical, matched left/right. Hood perimeter gap visible (clay_top x≈112 front edge + fender lines; clay_front y≈245). Trunk gap in clay_top (x≈720–870). Bumper/fender seam at clay_left x≈108 and bumper/quarter seam at x≈877. Note: hood gap lines in clay_front end abruptly on the hood surface (x≈200–240 / 750–800, y≈200–255) — consistent but visually unresolved. |
| 7 | Nose and tail | **FAIL** | clay_left (tail x 700–970), clay_rear, clay_front, clay_front_34 | Tail: trunk lid level exists (1.09 m) but the bumper is a near-vertical slab from y≈270 to 400 that bulges ≈8 cm proud of the trunk lid, with the wavy surface above — a tacked-on block, explicitly the "vertical slab" failure mode. Nose: hood plane rolls over a crisp edge into a ≈0.6 m tall flat vertical face (clay_front y≈270–520; clay_left nose x 52–110) — no rake, no lower-bumper step; not a bullet nose, but a slab. |
| 8 | Symmetry | **PASS** | clay_front, clay_rear, clay_left vs mirrored clay_right | Outline half-widths match within 2 px (≈5 mm) on every row from roof to belt in both front and rear views; all four side shut lines mirror within ≈10 px between left and right views. Lower bumper corners could not be verified from masks (shadow-side contamination); mirror-difference maps there are lighting-dominated. clay_top shows a difference blob at the front fender/bumper corners (x 50–460, y 130–180 vs 440–490) that is probably lighting but should be eye-checked. |

## Prioritised defect list

### P1 — blocking
1. **Wheel arch sawtooth on all four arches.** clay_left front arch (x 130–290, y 290–440) and rear arch (x 680–850); clay_front_34 near rear arch (x 530–620, y 410–470, teeth along the upper-left rim); clay_rear_34 near rear arch (x 500–560, y 410–440). Arch cut edge must be a clean circular boolean/loop, not a stair-step.
2. **Arches oversize and flat-topped.** clay_left: opening ≈0.9 m vs 0.74 m target; the top of the arch (x≈193–220, y≈298) is clipped flat just under the fender top edge. Reduce to 0.74 m, round the crown, keep ≥0.15 m of fender above the arch.
3. **Greenhouse stations wrong / not a fastback.** clay_left: windscreen top at ≈0.42 L (move rearwards to 0.47 L = 2.25 m, which also brings the rake from ≈30° to ≈24–26°); roof end at ≈0.77 L (move forwards to 0.713 L = 3.42 m); rear screen then runs 3.42→4.25 m at ≈20° instead of the present ≈27° over 0.5 m.
4. **Rear bumper face is a vertical slab with surface waves.** clay_rear: scalloped reflection edge y≈420–480 across x≈200–800; clay_left tail: face vertical from y≈270 to 400 and proud of the trunk lid by ≈15 px. Rebuild the tail as trunk lip → raked upper bumper → lower bumper step (sheet: trunk lip 1.02 m, bumper face Z 0.35–0.60).
5. **Shoulder character line missing.** clay_left/clay_right: no light break between belt (y≈255) and sill (y≈400) along the full side. Sheet: shoulder line Z 0.80 (front) → 0.95 (rear) at X ±0.92, through both handle stations.

### P2 — should fix
6. **Tail-lamp corner creases.** clay_rear (x≈250–330, y≈200–260) and mirror (x≈650–735, y≈200–275): a curved fold where the quarter wraps into the rear face.
7. **Front bumper diagonal fold.** clay_front (x≈230–330, y≈250–310, also mirrored at x≈670–770): a crease from the fender corner into the bumper top that terminates in the open surface; clay_front_34 shows the same at x≈760–990, y≈400–440 running into the hood gap.
8. **Fender/headlamp corner pinch.** clay_front x≈105–150, y≈190–300 (and mirror): vertical crease on the upper outer fender corner with a concave pinch below it down to y≈500.
9. **Nose is a vertical slab.** clay_left x 52–110: front face vertical from y≈300 to 400; give the bumper face the sheet's rake (most-forward point at Z 0.35–0.55, hood leading edge at 0.78 m).
10. **Rear screen / quarter pinch and rear-door surface step.** clay_rear_34 x≈700–760, y≈330–360 (pinch at the rear screen lower corner into the trunk) and x≈560–600, y≈330–400 (the rear-door trailing shut line reads as a step in the quarter surface, not a gap).
11. **Arch liner geometry.** clay_rear_34 (x≈500–560, y≈420–560): liner is a flat disc with a straight vertical cut on the trailing side; clay_front_34 (x≈140–170, y≈380–410): far-side liner protrudes below the sill.
12. **No DLO / window placement.** clay_front_34, clay_rear_34: greenhouse is one smooth dome merged with the body; the only reading of windows is the soft belt crease and the shut lines running up the glass. Window outlines, A/B/C pillar widths and the belt reveal need to be defined so door/window placement can be judged.
13. **Front overhang short / width over.** metrics: W 1.926 vs 1.85 m (+76 mm); clay_left front overhang ≈0.83 vs 0.90 m, L 4.736 vs 4.80 m. Push the nose forward ≈65 mm and pull the sides in ≈38 mm per side.

### P3 — polish
14. **Plan-view slab sides.** clay_top: body sides are dead straight between x≈270 and 700 with no plan curvature; real sedans bow out at the B-pillar.
15. **Hood gap termination.** clay_front x≈200–240 / 750–800, y≈200–255: the fender cut lines stop in open surface instead of meeting the hood leading-edge line.
16. **Cowl / A-pillar base corners.** clay_top (x≈150–200, y≈150–175 and y≈440–465): the greenhouse plan outline has square notches at the windscreen base; clay_front_34 shows a hard kink at the same spot.
17. **Verify front-corner symmetry.** clay_top mirror-diff blob at x 50–460, y 130–180 vs 440–490 (hood/fender/bumper corners) — probably lighting, eye-check once in Blender.
18. **Placeholder rims** are flat-shaded (135/140 flat faces each) — acceptable as placeholders.

## Deferred to G4 (not counted against G2)
- Headlamps, grille, lower intake, fog bezels, tail lamps, reflectors, diffuser, exhaust tips, parking sensors.
- Mirrors (sheet #41), door handles (#42/43), fuel flap (#44), shark-fin (#45), DLO chrome / black trim, badges.
- Detailed wheels (5 twin-spoke alloys), tyre sidewall detail, brake hardware.
- Interior, glass tint/surround, under-floor.
- Hood power bulges (sheet §5) — surface detail that can wait, but note that the hood is currently perfectly flat.

## Re-review conditions
Resubmit renders from the same seven camera positions after P1 items 1–5 are addressed; P2 items 6–11 should also be visible-fixed before the G3 surface gate. Criteria 1, 2, 3, 4, 5, 7 are re-judged; 6 and 8 only need a regression glance.
