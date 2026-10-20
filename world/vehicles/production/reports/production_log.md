# Vehicle production log — fictional mid-size sedan ("player sedan")

Director: Claude (Vehicle Production Director). Engine: Godot 4.7.2. Blender 5.2.2 LTS.
Checkpoints are kept; nothing approved is overwritten. `production/wip/` holds the current
iteration; approved stages are copied to `production/approved/<gate>_<version>/`.

| Gate | Status | Evidence |
|---|---|---|
| G0 Discovery | DONE | `reports/G0_audit.md`, `renders/g0_scan/`, `renders/g0_sedan_v1/` |
| G1 Reference | DONE (Reference Engineer) | `references/dimension_sheet.md/.json` (60 values, 32 landmarks, 8 logged conflicts) |
| G2 Proportions | IN ITERATION | `renders/g2_body_v2a..d/` clay 7-views |
| G3 Body surfaces | pending G2 | |
| G4 Assemblies | pending | |
| G5 Interior | pending | |
| G6 Materials | pending | |
| G7 Game-ready | pending | |
| G8 Integration | pending | existing contract test `tests/car_steering_test.gd` |

## Iterations
- **v1** (build_player_car.py, kept at `world/vehicles/player_sedan.glb`): integration skeleton; body FAIL (slab sides, boxy nose,
  decal-depth lamps, missing left mirror, liners under ground). Still the asset the game loads until v2 passes G8.
- **v2a** (sedan_body.py cage + subdivision): grooves and shoulder line work; FAIL — body side ran from ground clearance to belt
  (0.83 m slab), flat vertical end caps, tiny greenhouse.
- **v2b**: sill at 0.30 m, spherical end rounding, stronger shoulder crease. Better; FAIL — cabin short and rear-set, hood/fender
  groove pinching into the rounded ends, rear bumper cut folding the tail, liner petals, top view blown.
- **v2c**: cabin moved forward/longer, groove terminated before the ends, bumper cuts limited to the lower body, arc liners.
  Better; FAIL — bullet-shaped nose (no bumper face), belt step at the quarter panel/trunk junction, liner teeth.
- **v2d**: dimension-sheet targets applied (sill 0.165, belt 0.97, cowl 1.25 from front, roof 1.45, screens 24°/20°),
  hood-plane → bumper-face corner shaping with a chamfered lower lip, continuous belt over the rear quarter, 64-segment liners
  ending at the fender skin, top-view exposure fixed. → awaiting QA.

## Known limitations / decisions
- References are AI-generated with oversized wheels (0.18 L); real-world dimensions win, references drive styling (conflict C1).
- Subdivision cage approach (parametric Python) chosen over hand-modelled NURBS so the body stays reproducible and tunable from the
  dimension sheet; character lines are creased cage loops, panel gaps are real recessed grooves.
- Wheel arches are boolean cuts in the subdivided shell; an arch lip/flange is G3 work.
- **v2e/v2f**: groove inset along the section's local normal; character lines (shoulder, sill, belt) fade out over the last
  0.5 m so they no longer wrap the bumpers. Visual change small; bumper-face ripples remained → traced to the single n-gon end
  caps of the cage (subdivision pulls an n-gon into radial folds).
- **v2g**: end caps rebuilt as two concentric quad rings with a slight bulge; front face now smooth with a chamfered lip; rear face
  still showed a diagonal fold (cap rings scaled about z 0.5 while the tail ring's centroid is ~0.65). Symmetry metrics: flank
  |xR−xL| ≤ 0.5 mm over 231 samples; identical face/boundary counts per side.
- **v2h**: cap rings scaled about the end ring centroid; liner radius +3 mm. (The liner end-inside-skin edit missed this build:
  rim teeth expected to persist in v2h; fixed for v2i.) → awaiting render.
- **Independent QA of v2d** (`reports/G2_visual_qa_v2d.md`): **FAIL**. Pass: panel gaps, symmetry, main stations on the sheet.
  P1: arch sawtooth; arches oversize (~0.9 m vs 0.74); windscreen top too far forward / rear screen too steep (notchback);
  rear bumper vertical slab, wavy; no shoulder line. P2: corner creases/pinches, width +76 mm, front overhang −70 mm.
- **v2i**: liner moved inside the skin → proved the teeth are the raw boolean edge of the zero-thickness shell, not the liner.
- **v2j**: ellipse-relaxed cap rings; rear X-fold persisted. Cage inspection (live Blender wireframe) showed the cause: the cap
  rings were bulged forward, i.e. a shallow pyramid whose diagonals subdivide into ridges.
- **v2k** (addresses QA P1/P2): planar bumper caps (the `end_shape` roll/chamfer still shapes the ends); wheel-arch openings
  reduced to Ø0.74 and finished with a 28 mm inward flange (`arch_flange`) that hides the cut edge; near-planar windscreen
  (24°) and rear-screen (20°) profiles eased only at their ends; shoulder crease 3 cm proud with a concave scallop below;
  body width corrected to 1.85; ends extended to compensate subdivision shrink. → awaiting render + QA.
- Parallel: Mechanical Engineer building the 225/50 R17 wheel + brake assembly (`wheel_assembly.py`, separate files).
- **v2k render review (director)**: rear and front bumper faces now smooth (X-fold gone), arches Ø0.74 and concentric, width 1.874 / length 4.82 on target. Residual: faint scalloped arch rim. Sent to independent QA. **v2l**: 128-segment cutter, degenerate-sliver dissolve before the flange, soft-shaded rim.
- **v2l/v2m**: finer cutter, sliver dissolve, soft rim, even re-spacing of the rim polyline — no visible change. Wireframe of the
  arch in the live Blender showed why: the boolean on the subdivided shell leaves ~565 sliver triangles per arch with rim vertices
  scattered across x 0.62–0.92 m; weighted normals over them are the scallops. Rim patches cannot fix a topology problem.
- **v2n**: boolean removed. Wheel arches are now part of the cage: inside ±0.37 m of each axle the lower side landmarks become the
  arch lip (creased) and a 30 mm inward flange, stations densified to 55 mm, so the opening subdivides to a clean quad circle.
  → awaiting render.
- **v2n review (director)**: arches now clean quad circles with a visible lip, no scallops; body reads as a sedan in all 7 views. Checkpointed to production/checkpoints/G2_v2n. Nose 4 cm short (2.285 vs 2.325) → v2o.
- **v2o**: nose on target (y 2.325); tail 2 cm short (−2.455 vs −2.475) → offset staged for the next build. Bounds 1.875 × 4.78 × 1.448, 83.8 k tris incl. placeholder wheels (body shell itself to be re-measured at G7). v2o is the G2 candidate awaiting the independent reviewer.
- **Wheel assembly v0.3** (Mechanical Engineer, `wheel_assembly.py`, `production/wip/wheel_assembly.glb`): LOD0 6,768 / LOD1 2,394 tris;
  concentricity 0.0 mm, zero non-manifold/n-gons, fresh-Blender re-import of all 22 nodes verified; WheelPivot (spinning) /
  HubStatic (caliper, shield) split matches the game contract. Director visual review: NOT accepted — thin paddle spokes, no rim
  lip/dish, flat sidewall, caliper hidden behind the dust shield, zig-zag sipes. Revision 1 of 3 requested (v0.4) with specific
  blade/hub/lip/tread/caliper fixes.
- **Independent QA of v2k** (`reports/G2_visual_qa_v2k.md`): **FAIL (narrow)**. Proportions and silhouette now PASS (stations within
  ~1 %, windscreen 24.9°, fastback 23°); symmetry PASS. Remaining P1: arch sawtooth (already fixed in v2n by cage arches) and the
  shoulder line not at the sheet stations. P2: liners showing below the sill, fenders proud of doors / waisted plan (1.70 vs 1.87),
  rear-screen-base and cowl folds, no nose rake, bumper top-corner fold, shut lines jog at the belt.
- **v2p**: shoulder line 0.80→0.95 m through the handle stations (independent of the belt); flare 12 mm and door skin +18 mm
  (flush panels, full plan width); cowl/trunk-lid steps blended out; front lower face raked (chamfer from 0.55 m); plan rounding
  radius matched to the top roll (corner fold); door grooves run to the cant rail; liners clipped at the sill. Adds the reviewer's
  requested ≥400 px/m arch close-ups (`arch_crops.py`). → awaiting render, then resubmission to the same reviewer.
- **v2p review (director)**: shoulder line reads front-to-rear, arches clean in the 833 px/m close-ups, both bumper faces smooth, width 1.857, tail on target; nose 4 cm long (staged −4 cm). Checkpointed to production/checkpoints/G2_v2p and resubmitted to the independent reviewer.
- **Wheel assembly v0.4** (revision 1): LOD0 7,724 / LOD1 2,314 tris; broad chamfered twin blades rooted in a 0.11 m hub plate with
  booleaned lug pockets, rolled rim lip and dark well, rounded tyre shoulder with rim-protector rib, 4 circumferential grooves +
  decal transverse cuts (clean 48-gon silhouette), dished shield so the vented disc and caliper show. Tests re-run and passing
  (concentricity 0.000 mm, no n-gons, fresh-Blender re-import). Director: accepted conditionally for G4; checkpointed to
  production/checkpoints/G4_wheel_v0.4. Open: independent visual QA at vehicle scale; alloy/chrome read in Godot; RubberCut
  second material slot to be consolidated by the game-asset engineer.
- Parallel: independent visual QA of wheel v0.4 and a Godot 4.7 import/spin/material validation of the same checkpoint (game-asset engineer, owns tests/wheel_import_test.gd, tests/capture_wheel.gd, reports/g4_wheel_godot.md). Body v2p is with the independent reviewer.
- **G2 — PASS WITH CONDITIONS on v2p** (`reports/G2_visual_qa_v2p.md`): all 8 criteria pass; arches verified continuous at 833 px/m,
  panels flush, stations within ~1 %, symmetry ≤2 px. Conditions carried into G3: bumper chamfer/corner diagonal fold (P2-1),
  liner tabs below the sill (P2-2), shoulder line through the handle heights 0.83/0.865 (P2-3); P3: nose +40 mm, rear screen
  23°, cowl ripple, shut lines 70–100 mm ahead of the sheet, DLO/pillars. Promoted to production/approved/G2_v2p.
- **Independent QA of wheel v0.4** (eports/G4_wheel_visual_qa_v0.4.md): **FAIL** on the rim face (hub plate ~51 % of rim diameter, tube-like blades with constant slot, caliper unreadable); tyre/brake pass with conditions. Revision 2 of 3 (v0.5) requested with explicit hub/blade/caliper/LOD1 specifications.
- **Godot validation of wheel v0.4** (`reports/g4_wheel_godot.md`): contract 54/54 (axle = local X, spin concentric to 0.0 mm,
  triangles exact, 7 slots). Pipeline defect found: `.blend` files beside GLBs abort Godot's whole import batch → fixed by
  `world/vehicles/production/.gdignore` (production is not game content; approved GLBs are copied out at integration).
  Integration findings for G7/G8: exactly one `Wheel*` Node3D per corner (rename pivots per corner, LOD by visibility range not
  offset); rolling radius in player.gd 0.35 → 0.33; left wheels must be mirrored (scale.x −1), not rotated; metals collapse to
  sky-grey under sky-only reflections → Material Engineer to use alloy m0.85 r0.38 + clearcoat, chrome r0.18, dark well, and a
  ReflectionProbe on the car.
- Game regression after the production .gdignore: car_steering 36/36, regression 25/25, city 169/169 — import pipeline healthy. Parallel: Material Engineer studying vehicle PBR under the game's own lighting (day / golden hour / night / rain, with and without a ReflectionProbe).
- Session usage limit interrupted the G3 body engineer, the wheel v0.5 revision and the material study before any output; all three resumed from their saved state after the reset (no files were half-written: G3 had not yet edited sedan_body.py; wheel v0.5 patch scripts were staged in the scratchpad only).
- **External change detected (19:09–19:17, during/after the usage-limit window, not by this team):** `tools/prepare_jetta.py`,
  `assets/vehicles/jetta_gli_2025/` (jetta_lod0/1/2.glb — 22 MB LOD0 with baked textures — jetta.gd/.tscn), `tests/jetta_track.*`,
  `tests/jetta_city.*`, and edits to `world/asset_library.gd` (the game's "sedan" now instantiates
  `assets/vehicles/jetta_gli_2025/jetta.tscn`) and `actors/player.gd`. Effect: `tests/car_steering_test.gd` now FAILS (12 wheel
  pivots, 196,800 tris, none of the contract materials). This bypasses the G0–G8 pipeline and uses a real trademarked design
  (Volkswagen Jetta GLI), which `vehicle_agent_system/CLAUDE.md` says to avoid. Not reverted — escalated to the user for a decision.
  The production pipeline (approved G2 body, wheel v0.5, materials) is unaffected and continues.
- User decision: keep the production pipeline. Restored CityAssets.create_player_vehicle() to the production path (Jetta files left untouched; player.gd hooks bind_driver/has_vehicle_lights kept as harmless generics). car_steering_test: CAR STEERING PASS: 36 checks, 0 failures
- **Wheel v0.5** (revision 2): hub dome r 0.072, straight tapered twin blades 0.045→0.075, two-piece caliper straddling the disc, LOD1 keeps grooves; all automated tests pass; composite vs reference produced. Director: still ~30 % narrower than the reference and the reference spoke is a single broad wedge with a split groove, not two blades → revision 3 of 3 (v0.6) requested with exact proportions (0.105→0.060 m wedges, 6 mm groove, ~35 % open windows, dome blended into spokes). Regression after the sedan-path restore: regression 25/25, city 169/169, lifestyle 71/71, economy PASS.
- **Wheel v0.6** (revision 3 of 3): five single wedge spokes 0.060→0.105 m with a 6×4 mm centre groove, booleaned into a step-free
  hub dome (RimFace closed shell), lip rings the tips; LOD0 7,920 / LOD1 2,376; all automated tests pass. Engineer flagged a spec
  conflict honestly: with these widths the windows are 51.5 % open vs ~35 % in the reference. Director: reads as the reference
  design; sent to independent visual QA (decides fit-or-escalate). Checkpointed to production/checkpoints/G4_wheel_v0.6.
- **G6 material study** (`reports/g6_materials.md`, `world/vehicles/vehicle_materials.gd` — not yet wired): measured in Godot —
  sky-only reflections turn every bright metal into a blue ball; a per-car ReflectionProbe (UPDATE_ONCE, ~6×4×8 m, re-triggered
  on movement/time/weather) is the single biggest gain; final table (chrome #e0e0e0 r0.15, alloy #b9bbbe m0.7 r0.42 cc0.6, well
  #4a4a4d, glass α0.32 cull-back with depth pre-pass, rubber r0.74 spec 0.42, lamps 0.2→1.4 / 0.3→1.0 day→night); set_wet()
  for rain; Blender-side requirements (exact slot names, VehiclePaint in node names, lamp housings on BlackTrim). Gotchas:
  19.3 h is already night in the game clock; an UPDATE_ONCE probe keeps its daytime capture at night unless re-triggered.
- Director verified the G6 captures (day / day+probe / night+probe / rain): the ReflectionProbe is decisive for chrome and alloy, lamps read at night without clipping, rain darkens and glosses. G6 material table accepted as the integration target (wiring at G8).
- **Independent QA of wheel v0.6** (`reports/G4_wheel_visual_qa_v0.6.md`): **PASS WITH CONDITIONS — fit to the car.** P1-1/2/3 FIXED;
  51.5 % windows accepted (reads as a clean 5-spoke at 2–15 m). New P2: spoke tips 5 mm proud of the lip with straight-cut ends
  (parameter-only fix: face lift → 0, arc-cut tips). Conditions for sign-off at integration: Godot render set at 2/8/15 m
  (tick z-fight, metals), LOD switch ≥ 15 m. Promoted to production/approved/G4_wheel_v0.6.
- **Wheel v0.6.1** (parameter-only): tips flush and arc-cut to the lip (continuous lip ring), nuts recessed 1.5 mm with chamfered pockets; LOD0 7,918 / LOD1 2,376; all tests pass. Director verified wheel_face.png. This is the fitting version → production/approved/G4_wheel_v0.6.1 (v0.6 kept).

## G3 (Body Surface Engineer)
- **g3 build 1–2** (`renders/g3_body_v1`): stations re-based on the sheet nose (shut lines 0.96/−0.27/−1.34 exactly), chamfer along the
  corner normal (P2-1), shoulder through the handles (P2-3), cowl/screen-base ring blending, hood dome, recessed DLO with A/C-pillar plane
  cuts, black window surround, separate BPillar, sheet-frame apertures with inset floors. Found: centre apertures only on x>0, tail lamp
  missed the rear face, bisect slivers → finned glass edges, liner tabs persisted, nose 2.305.
- **g3 build 3** (`renders/g3_body_v2`): |x| for centre apertures, lamps wrap onto the end faces, bisect snap 4 mm, per-edge surround depth.
  Tabs still there → identified as the body's arch-end wall foot (not the liner); nose unchanged → the subdivided end sits on the last ring
  station (quantised by the station step).
- **g3 build 4 = final** (`renders/g3_body_v3`): end stations pinned (L 4.800, nose 2.325, tail −2.475), arch-wall foot at the sill-bottom
  height (tabs gone at 833 px/m), ceramic band as a boundary face row (clean cut edges), zebra lighting tuned. Mesh-measured shoulder
  0.799/0.831/0.865/0.947 at y 2.0/0/−1.15/−2.0. 91,580 tris incl. placeholder wheels (Body 76,748). Handoff:
  `reports/g3_body_handoff.json`, notes `reports/g3_body_notes.md`. QA_status pending → independent G3 review requested.
- **G3 v3 delivered** (Body Surface Engineer): pinned L 4.800 / nose 2.325 / tail −2.475, shut lines on the sheet, G2 conditions P2-1..3 closed by measurement, DLO with A/B/C pillars and recessed glass, hood dome, lamp/grille/intake/tail/fuel-flap/mirror apertures (plane cuts + insets, no booleans), zebra renders continuous. Open: ~2 cm stair at the side-glass front-top corner, groove hook at the cant rail, B pillar 98 mm, 145 n-gons for G7. Director: checkpointed to checkpoints/G3_v3; sent to independent QA. Stray empty C:\production\ left for the user (root path protected).
- **G3 — PASS WITH CONDITIONS on v3** (eports/G3_visual_qa_v3.md): all G2 conditions closed, shading/symmetry/grooves/zebra PASS, apertures on sheet. Conditions before DLO trim and tail lenses: P2-1 ~65 mm vertical notch at the front side-glass top corner (both sides); P2-2 tail-lamp aperture lacks its quarter-panel wrap (sheet y −2.00..−2.42). P3: ceramic band sawtooth, C-pillar glass hook, grille centre pole. Promoted to approved/G3_v3; v3.1 fixes assigned to the body engineer; G4 exterior details started in parallel on cleared surfaces.
- Parallel after the G3 pass: Body engineer on v3.1 (A-pillar glass corner, tail-lamp wrap, ceramic band, grille pole, B pillar 80 mm); Exterior Detail Engineer on G4 parts (lamps with internals, grille, intake, mirrors, handles, exhausts, wipers; LOD1); Interior Engineer on G5 cabin (dash, wheel on the SteeringWheel pivot, seats, console, door cards, headliner; DriverEye empty). Integration (G7/G8) waits for all three.
- **g3 v3.1** (`renders/g3_body_v3_1`, after `G3_visual_qa_v3.md` PASS WITH CONDITIONS; v3 kept in approved/G3_v3): P2-1 A-pillar
  glass line continuous into the cant rail (windscreen zone fix + plan line 0.72→0.56), P2-2 tail lamps wrap onto the quarter
  (y −2.011..tail); P3: constant 15 mm ceramic band by parallel cuts, aperture floors along smooth normals (grille pole 1.7 mm),
  headlamp inner edge 0.479, B pillar 83 mm. Three rebuilds, full 14-render set incl. 833 px/m A-pillar corner and tail-lamp crops.
  Residual P3: C-pillar groove hook, faint pole mark. Handoff v3.1 updated, QA_status pending → re-review of criteria 5 and 9.
- **G3 v3.1** (body engineer): A-pillar glass boundary now one continuous raked cut (cause: windscreen zone claimed side-glass faces), tail-lamp aperture wraps the quarter (y −2.011..−2.47, |x| ≤ 0.894), constant 15 mm ceramic band, grille pole 1.7 mm, B pillar 83 mm, headlamp inner edge 0.479. Residual P3: C-pillar glass hook, C-foot tone break. Director verified the 833 px/m crops; checkpointed to checkpoints/G3_v3_1; sent to the same reviewer for the reopened criteria; G4/G5 engineers re-targeted to v3.1.
