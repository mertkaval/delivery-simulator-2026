# G3 Visual QA — body surfaces v3 (sedan_v2_body.glb, checkpoint G3_v3)

Independent Visual QA, 2026-10-19. Reviewed: the 11 renders in `renders/g3_body_v3/` (7 clay views, 2 arch close-ups at 833 px/m, zebra_left, zebra_hood), `metrics.json`, `g3_body_handoff.json` (incl. known_defects), `g3_body_notes.md`, `references/dimension_sheet.md`, prior gate `G2_visual_qa_v2p.md`. Eye-check: `checkpoints/G3_v3/sedan_v2_body.glb` imported read-only into a temporary `QA_G3` collection in the live Blender 5.2.2 (solid and material-preview looks, bmesh measurements), removed afterwards; no asset or script was edited.

Measurement basis. clay_left / clay_right: car spans x 55→1144 px (left) / 54→1145 (right) for 4.80 m → **226.9 px/m**, ground y 535, height 328 px = 1.446 m. clay_front / clay_rear ≈ 512 px/m. Mesh numbers below are from the GLB in Blender (sheet frame: +Y front, +Z up, origin on the ground at the wheelbase centre).

## Overall verdict: **PASS WITH CONDITIONS**

The shell is smooth and symmetric, the three G2 conditions are closed and demonstrated, stations and shut lines sit on the sheet to the millimetre, zebra bands are continuous over hood, roof, fenders, doors and quarters, and every aperture is mirrored left/right to the millimetre. Two things stop a clean pass: (1) the front side-glass front-top corner is not a "2 cm stair" as declared — the glass is terminated by a vertical cut at y ≈ 0.16 over z 1.21–1.38 (a 60–170 mm vertical step in the DLO outline, both sides), and (2) the tail-lamp aperture does not wrap onto the quarter: it starts at y −2.184 instead of the sheet's −2.00 (handoff claims "y −2.00 .. tail"). Both are P2 and affect G4 placement (DLO trim, tail lamps). The ceramic band is a sawtooth of 4–40 mm triangles (visible inside ~1.5 m) — P3 with a fix path. G4 may proceed on everything else (see the last section).

## Criteria table

| # | G3 criterion | Result | Proving render(s) | Observation |
|---|---|---|---|---|
| 1 | No faceted / lumpy shading | **PASS** | clay_front, clay_rear, clay_front_34, clay_rear_34, zebra_left, zebra_hood | Hood, roof, doors, quarters, trunk and both bumpers read smooth; weighted normals hold on the clay. Power-dome ridges read as two soft highlights (zebra_hood x 420–520 / 700–800, y 330–450), not as creases. Body `flat_faces` 2043 of 76 748 tris are the intended sharp aperture/surround walls. |
| 2 | No unwanted intersections | **PASS** | arch_front_left, arch_rear_left, clay_front_34, clay_rear_34 | Liner stays inside the arch wall (dark ring 25–40 px, no protrusion); glass sits 5/12 mm inboard of the surround; B-pillar band 2 mm behind the glass (no z-fight seen in material preview). |
| 3 | No collapsed surfaces / pinching | **PASS (one P3)** | clay_top, clay_rear_34, Blender look at the rear-screen corner | Cowl / A-pillar base S-ripple from G2 (P3-7) is now a single soft blend (clay_top x 300–330, y 225–240 and 500–515). Rear-screen lower corner dip (G2 P3-8) is gone (clay_rear_34 x 740–800, y 400–430 smooth). Residual: faint tone break at the C-pillar foot where the pillar meets the quarter and trunk shut line (Blender look at (−0.6, −1.85, 1.12)) — P3. |
| 4 | No obvious asymmetry | **PASS** | clay_front, clay_rear, clay_top, mesh | Outline mid-x 599.5 ± 0.5 px on every sampled row of clay_front and clay_rear (≤ 1 px ≈ 2 mm); left/right render spans 1089 vs 1091 px. Mesh: headlamp L/R clusters 988/988 faces with mirrored bounds (|x| 0.480–0.865, y 1.838–2.313, z 0.651–0.801), tail lamps 301/301 (|x| 0.321–0.842, y −2.461…−2.184, z 0.789–0.949), mirror pads 58/58 (|x| 0.787–0.860, y 0.721–0.880, z 0.978–1.029); A-pillar glass corner vertices mirror exactly (±0.564, 0.443, 1.256 …). Fuel flap single-sided by design (x −0.926…−0.913, y −1.769…−1.551, z 0.781–0.929). |
| 5 | Glass openings connected, DLO reads correctly | **PASS WITH CONDITIONS (P2-1, P3-3/4)** | clay_left, clay_right, clay_front_34, clay_rear_34, Blender looks | 6 glass components present, recessed, with black surround; A/B/C pillars read in the 3/4 views; windscreen side lines straight in clay_top. **But** the front side-glass front-top corner is a vertical cut (y 0.161–0.164 from z 1.214 to 1.381 on the mesh boundary) meeting the raked line with a kink — visible as a notch in clay_left x 535–545, y 235–250 and clay_right x 352–366, y 240–262 (≈ 15 px ≈ 65 mm of exposed step) and as a ~0.17 m vertical glass edge in the Blender material look along the left side. Rear-door glass top-rear corner shows the declared hook/wedge (clay_rear_34 x 700–720, y 300–330; mirrored on the right). B-pillar band 98 mm (brief 60–80). |
| 6 | Grooves straight | **PASS** | clay_left, clay_right, clay_top, clay_front_34 | Shut lines run straight belt→sill and up to the cant rail; the only jogs are the intended kink where a gap crosses the proud shoulder crease. Hood gaps now terminate on the headlamp cut (clay_front x 215–350 / 850–985, y 225–330; zebra_hood) — G2 P3-6 closed. |
| 7 | Curvature continuity (zebra) | **PASS** | zebra_left, zebra_hood | zebra_left: all 5 strips continuous fender→door→quarter (x 200–1250); breaks only at the mirror pad and the lamp/flap recesses (intended). zebra_hood: strips continuous over hood→fender→A-pillar base; the front lower corner rolls (no diagonal fold) at x 320–420, y 520–620. Shoulder crease is a clean highlight break along the whole side. |
| 8 | Shut lines at y 0.96 / −0.27 / −1.34 | **PASS** | mesh, clay_left | Mesh groove vertex clusters at y 0.942–0.967 (centre 0.96), −0.292…−0.249 (centre −0.27), −1.359…−1.321 (centre −1.34). Render: 0.96 → x 365 px (seen 364–367), −0.27 → 644 (seen 643–646), −1.34 → 887 (seen 885–889). |
| 9 | Apertures at sheet positions, clean-edged | **PASS WITH CONDITIONS (P2-2, P3-1/2)** | Blender material looks (nose, rear), clay_front, clay_rear | Headlamp |x| 0.48–0.865, y 1.838–nose, z 0.651–0.801 (sheet 0.48–0.86 / 1.84–2.25 / 0.65–0.80) — on sheet; the nose-face upper part begins at |x| 0.607 where the hood gap ends (sheet 0.48; headlamp and grille merge into one black field for z 0.65–0.72, which the sheet also implies). Grille |x| ≤ 0.48, z 0.559–0.757 on the nose (sheet ±0.48, 0.56–0.72). Lower intake on the skirt |x| ≤ 0.499, z 0.257–0.395 (sheet ±0.50, 0.25–0.39). Fuel flap and mirror pads on sheet (see #4). **Tail lamps**: rear face |x| 0.321–0.842, z 0.789–0.949 on sheet, but no side portion — aperture starts at y −2.184 (sheet −2.00); the quarter is still at |x| 0.886 at y −2.05 and 0.866 at −2.15, so 0.18 m of sheet lamp length is un-apertured body. Edges are crisp; the grille floor at the centre pole shows a 4–5 mm rise of the lower edge for |x| < 0.1 (mesh z 0.564 vs 0.559–0.561 elsewhere) — a faint jog visible in the material look at 2.4 m. |
| 10 | Proportions / stations (regression) | **PASS** | clay_left, metrics.json | L 4.800 (nose 2.325, tail −2.475 — G2 P3-4 closed), W 1.857, H 1.448. Profile from clay_left: cowl z 1.00 at 1.10–1.21 m from the nose (sheet 1.25 m / 1.00), windscreen top z 1.41 at 2.20 m (sheet 2.25), roof plateau z 1.446 from 2.65 to 2.98 m, roof end ≈ 3.42 m (z 1.42), screen end ≈ 4.19 m at z 1.11 (sheet 4.25 / 1.10), lid falls continuously to z 1.067 at 4.63 m (G2 P3-12 closed). Shoulder line at max-x on the mesh: z 0.800 (y 2.0), 0.816 (1.0), 0.831 (0), 0.845 (−0.5), 0.865 (−1.15), 0.907 (−1.6), 0.947 (−2.0). |

## G2 conditions and carried P3 items

| G2 item | Status | Proof |
|---|---|---|
| P2-1 front bumper chamfer-to-corner fold | **CLOSED** | clay_front x 130–230 / 970–1070, y 450–650: the lower face rolls around the corner, no diagonal crease on either side (left side now lit); zebra_hood x 320–420, y 520–620 continuous. |
| P2-2 arch-liner tabs below the sill | **CLOSED** | arch_front_left and arch_rear_left: sill underside is a clean line either side of the tyre (y 690–720), no flat tabs; the raised arch-wall foot reads as a short chamfer (arch_rear_left x 170–240 and 760–830, y 650–700). |
| P2-3 shoulder line through the handle heights | **CLOSED** | mesh max-x z = 0.831 at y 0 (handle 0.83) and 0.865 at y −1.15 (handle 0.865); 0.800 at the headlamp top, 0.947 at the tail-lamp top. G4 handles can sit on the line. |
| P3-4 nose 40 mm long | CLOSED | metrics Y max 2.325. |
| P3-5 rear screen 23° | OPEN, accepted (fastback intent; sheet landmarks give 21.7°) | clay_left fit x 840–1000. |
| P3-6 hood gaps end in open surface | CLOSED | clay_front, zebra_hood: gaps end on the headlamp cut. |
| P3-7 cowl S-ripple | CLOSED (soft blend) | clay_top x 300–330. |
| P3-8 rear-screen corner dip | CLOSED | clay_rear_34 x 740–800, y 400–430. |
| P3-9 nick at rear-door shut / arch flange | CLOSED | arch_rear_left x 410–450, y 290–340: groove meets the flange cleanly. |
| P3-10 rear bumper lower-corner step | CLOSED | clay_rear x 140–200 and 1000–1060, y 600–650 smooth both sides. |
| P3-11 shut-line stations | CLOSED | criterion 8. |
| P3-12 level trunk lid | CLOSED | criterion 10. |
| P3-13 DLO definition | DONE (with new P2-1) | criterion 5. |
| P3-14 L/R render length | CLOSED (1089 vs 1091 px) | clay_left / clay_right. |

## Engineer's declared open issues — severity judged

| Declared | QA finding | Severity |
|---|---|---|
| Side-glass front-top corner 2-step stair ~2 cm | Understated. The glass boundary is a vertical cut at y 0.161–0.164 from z 1.214 to 1.381 (0.17 m) before it turns onto the raked A-line; exposed step in the DLO outline ≈ 65 mm in the side renders, more in oblique views. Symmetric L/R. | **P2** |
| Rear-door glass top-rear hook at the cant rail | Confirmed, ~50 mm wedge where the door-shut groove ends on the recessed corner; symmetric. Reads as a trim detail at ≥ 4 m. | **P3** (fix with P2-1, same corner logic) |
| Grille centre cap pole facet | Confirmed as a 4–5 mm rise of the grille lower edge over |x| < 0.1; faint but on the car's centre line. | **P3** |
| Ceramic band one subdivided face row (15–35 mm) | Band faces measure 4–40 mm across (median 17 mm) and are triangles pointing into the glass — a sawtooth on every screen and side-glass edge, obvious inside ~1.5 m in material preview, invisible in the clay set. | **P3** (must be fixed before G6 materials; suggest a UV/texture band or a constant-offset loop) |
| B-pillar 98 mm (brief 60–80) | Confirmed 98 mm (y −0.316…−0.218). Reads heavy but proportionate. | **P3** |
| Headlamp inner edge |x| 0.607 vs sheet 0.48 | Only the part above z 0.72 starts at 0.607; below that the recess reaches 0.48 and merges with the grille, which matches the sheet's overlapping boxes. | **P3** (G4 lens must be designed to the built cut) |
| 145/8/10 n-gons, weighted normals | Export is fully triangulated (76 748 tris, 0 n-gons in the GLB); no shading artefacts seen. | note only |
| Rear screen 21.7–23° | accepted | — |

## Defects in v3, prioritised

### P1 — blocking
None.

### P2 — conditions (close before G4 touches the DLO trim and tail lamps; re-render clay_left/right, clay_rear_34 and a 833 px/m crop of each corner)
1. **Front side-glass front-top corner.** Vertical cut at y ≈ 0.163 over z 1.21–1.38 instead of a continuous raked A-line into the cant rail; exposed as a 65 mm notch in clay_left x 535–545, y 235–250 / clay_right x 352–366, y 240–262, and as a 0.17 m vertical glass edge in the Blender side look. Both sides. Extend the raked plane cut up to the cant edge (or trim the cage rectangle's front limit along the A-line) so the corner is a single acute vertex. Dependent: G4 A-pillar/DLO trim and mirror sail.
2. **Tail-lamp aperture has no side portion.** BlackTrim cluster y −2.461…−2.184, no BlackTrim at |x| > 0.85; sheet lamp Y −2.00→−2.42 on the quarter. Either extend the cut to y −2.00 along the quarter (|x| 0.87–0.90) or update the sheet; the handoff statement "y −2.00 .. tail" is not what was built. Dependent: G4 tail lamps.

### P3 — carry into G4 log
3. Ceramic band sawtooth (Glass BlackTrim row, 4–40 mm triangles) on all six glass edges — fix before G6.
4. Rear-door glass top-rear hook (clay_rear_34 x 700–720, y 300–330; mirrored right).
5. Grille lower edge +4–5 mm over |x| < 0.1 (centre pole).
6. B-pillar 98 mm vs brief 60–80.
7. Headlamp nose-face upper inner edge at |x| 0.607 (hood-gap end) — design G4 lens to the built cut or move the gap end to 0.48.
8. Faint tone break at the C-pillar foot / trunk shut line junction (Blender look at (−0.6, −1.85, 1.12)); not visible in the clay set.
9. Rear screen 21.7–23° — accepted.
10. Placeholder wheels (flat-shaded rims) — replaced at G4.

## What G4 (exterior details) may proceed on
Proceed now on: hood, fenders, doors, quarters, bumpers and skirt surfaces; shoulder line (handles at z 0.83 / 0.865, y −0.13…0.12 and −1.27…−1.02, x ±0.92); headlamp recesses (|x| 0.48–0.865, z 0.651–0.801, upper inner edge 0.607), grille (±0.48, z 0.56–0.72), lower intake (±0.499, z 0.257–0.395), fuel flap, mirror pads (|x| 0.787–0.860, y 0.721–0.880, z 0.978–1.029), B-pillar trim at 98 mm, shut lines at 0.96 / −0.27 / −1.34, arches (Ø0.73, clean), wheel assembly.
Hold until P2-1 / P2-2 are closed: A-pillar / DLO trim and anything keyed to the side-glass front corner; tail-lamp lenses and bezels (aperture length on the quarter is undecided).

## Gate statement
**G3 body surfaces v3: PASS WITH CONDITIONS.** Conditions P2-1 and P2-2 to be closed in a v4 of the body (or P2-2 resolved by a sheet change signed off by the Reference Engineer) and shown in the same 11-render set plus corner crops; no re-review of criteria 1, 2, 4, 6, 7, 8, 10 is needed unless the cage or shoulder topology is reopened. P3 items 3–10 are tracked in the G4 log.

## Evidence files
Renders: `C:\GodotProjects\delivery-simulator-2026\world\vehicles\production\renders\g3_body_v3\` (clay_front/rear/left/right/top/front_34/rear_34, arch_front_left, arch_rear_left, zebra_left, zebra_hood, metrics.json). Mesh: `C:\GodotProjects\delivery-simulator-2026\world\vehicles\production\checkpoints\G3_v3\sedan_v2_body.glb`. Blender eye-check looks were taken in the live session (temporary `QA_G3` collection, removed) at: nose material view 2.4 m, headlamp/grille 2.6 m, tail 2.8 m, A-pillar corners L/R 0.7 m, C-pillar corners L/R 0.8 m, windscreen edge 1.2 m, rear-screen corner 1.3 m, left DLO 2.6 m.
