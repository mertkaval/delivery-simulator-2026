# G4 wheel assembly — mechanical engineer notes (v0.6.1 parameter follow-up on the QA-passed v0.6)

## v0.6.1 (wip files only; approved/G4_wheel_v0.6 untouched)
- face_lift 0.005 -> 0.0: spoke tips flush with the rolled lip.
- Spoke tips arc-cut concentric with the lip (last prism ring at constant radius 0.214) so the lip ring is continuous.
- Lug recess perceptible: nut crowns 1.5 mm below the local dome surface; 3 mm chamfer cutter at each pocket mouth.
- No width/budget/design change: LOD0 7918 (rim 2966, RimFace 1574), LOD1 2376; all tests + fresh re-import PASS;
  wheel_face / wheel_spoke_closeup / wheel_face_vs_ref re-rendered and inspected.

# v0.6 notes (director revision 3 of 3)

## v0.6 changes (director review of the v0.5 composite)
- Spokes: 5 single wedges 0.060 (hub) -> 0.105 m (rim), flat machined face, 3 mm chamfers, 0.035 dish, centre groove
  6 x 4 mm along the full length (twin-spoke read, not a through-slot), root flare +12 mm blending into the dome.
- Hub: spokes are EXACT-boolean UNIONED into the step-free shallow dome r 0.072 (one closed shell, 0 boundary edges,
  `rim_face.spokes_unioned_into_dome = true` in the handoff), then 16-gon lug pockets cut; nuts recessed; centre cap
  r 0.028 with a 2 mm raised lip (24-gon).
- Rim face lifted +0.005 outboard (tips end at r 0.214, 1 mm proud of the lip's inner edge so the rolled lip rings them).
- Tyre and brake unchanged from v0.5. LOD1 spokes are plain 4-point wedges.
- EXPLICIT SPEC CONFLICT: 0.105/0.060 widths and "~35 % windows" cannot both hold. With the specified widths the open
  windows are 51.5 % of the face annulus (dome edge r 0.072 to lip r 0.202); window arc 0.149 m at the lip, 0.101 m
  at r 0.150. Widths were followed; the window share is reported, not approximated.
- Budget: LOD0 7920/9000 (tyre 3456, rim 2968 [barrel 1040, face 1576, cap 192, lugs 160], brake 1496), LOD1 2376/2500.
  All tests re-run and green incl. fresh-Blender re-import; composite check 850 vs 869 px.

---
(v0.5 notes below, kept for history)


Component: `player_sedan.wheel_assembly.R` — one right-side wheel, 225/50 R17 on a 17 x 7.5J twin-spoke alloy, with
vented disc, fixed two-piece caliper and dust shield. Built by `world/vehicles/wheel_assembly.py` (Blender 5.2.2 headless).

## Reproduce
```
blender --background --factory-startup --python world/vehicles/wheel_assembly.py              # build, export, renders, handoff
blender --background --factory-startup --python world/vehicles/wheel_assembly.py -- --verify  # fresh re-import check
```
Outputs: `production/wip/wheel_assembly.{glb,blend}`, `production/renders/g4_wheel/` (wheel_face, wheel_34, wheel_rear_brake,
wheel_tread_closeup, wheel_spoke_closeup, wheel_caliper_window, wheel_lod1_34, wheel_face_vs_ref), `production/reports/g4_wheel_handoff.json`.

## Frame and rig (unchanged)
- Axle = local X, right-wheel face at +X, origin at the hub centre, spin about local X; Y-up export keeps X, so Godot spins about
  local X. Left wheel: rotate the instance 180 deg about Z.
- `WheelR` > `WheelPivot` (Tyre, RimBarrel, RimFace, CentreCap, LugNuts, BrakeDisc) + `HubStatic` (Caliper, DustShield).
- `WheelR_LOD1`: same hierarchy, `_LOD1` suffixes, root at +1 m Blender Y.

## v0.5 changes (QA P1-1..3, P2 face/LOD, selected P3)
- P1-1 Hub: shallow dome r 0.072 m (33 % of rim dia; 0.065 would be breached by 12.5 mm pockets on the 0.112 m PCD), 16-gon
  pockets cut with an EXACT boolean, edge 90 deg -> 4 mm step.
- P1-2 Blades: straight tapered wedges in the pair frame, pair 0.045 m (hub) -> 0.075 m (rim), slot 0.008 -> 0.022 so the pair
  merges into one root; flat face, single 3 mm chamfer (sharp edges, no tube highlight), dish 0.035 m (t^1.3), 4 steps; well
  cylinder 0.040 m behind the rim face then a step down to the dark floor.
- P1-3 Caliper: inboard + outboard halves straddling the disc (total width 0.068 m, 2.5 mm pad gap), r 0.085-0.157 (overlaps the
  0.150 disc edge), 0.17 m along the arc, three rounded bridges with two pad windows, pads on a `BrakePad` slot, two 8-gon
  bolt bosses; at the car rear (-Y), visible through the 9 o'clock window (`wheel_caliper_window.png`, 1.5 m, 135 mm).
- P2 Face depth: dish 35 mm; SteelDisc darkened to 0.34; shield on its own dark `ShieldSteel` slot; studio exposure corrected
  (-1.1 EV, key 260 W) so rubber reads black and the windows read as shadowed depth.
- P2 LOD1: four circumferential grooves as geometry, groove bottoms on `RubberCut` (slot survives the GLB round-trip, confirmed by
  re-import: `Tyre_LOD1 mat=['Rubber','RubberCut']`), two lettering ribs, 24-gon tyre; no decal ticks.
- Tyre LOD0: ribs 1.2 mm on a continuous sidewall curve, groove bottoms on `RubberCut`; cap 24-gon with raised rim; lug nuts
  0.019 AF chrome, 1 mm recessed.
- P3-12 metric bug fixed (LOD1 radius_max now root-local); P3-11 ShieldSteel slot; P3-9 cap/pocket segments raised.
- Composite `wheel_face_vs_ref.png`: our face render (left) beside the reference front wheel scaled to the same tyre pixel
  diameter. Reference tyre measured from pixels (280 px, sheet said 313) because Blender returns linear pixels; numeric check
  850 px vs 869 px target (2 %).

## Measured (handoff JSON)
| | LOD0 | LOD1 | budget |
|---|---|---|---|
| Tyre | 3456 | 1296 | 3500 |
| Rim (barrel 1040, face 1336, cap 240, lugs 160) | 2776 | 760 | 3500 |
| Brake (disc 912, caliper 344, shield 240) | 1496 | 400 | 1500 |
| Total | 7728 | 2456 | 9000 / 2500 |

Bounds LOD0 X +-0.1125, Y/Z +-0.33. Concentricity 0.000 mm on all revolved parts. No n-gons, no 3+-face edges; boundary edges
only on Tyre (384 decal quads). Materials: Alloy, BrakePad, CaliperDark, Chrome, RimWell, Rubber, RubberCut, ShieldSteel, SteelDisc.

## Verified
Budgets; concentricity; tyre OD/width/inset; manifold scan; fresh-Blender GLB re-import (22 names, Caliper under HubStatic, Tyre under
WheelPivot, LOD1 root (0,1,0), bounds unchanged); eight images viewed; composite scale checked numerically.

## Known defects / honest reads
- Against the reference in `wheel_face_vs_ref.png` the pairs still read ~30 % narrower: the reference pair is ~0.10-0.11 m at
  the rim with near-closed windows at the hub, versus the specified 0.075 m. Recommend pair_w_rim 0.10 / pair_w_hub 0.055 for
  v0.6 if the director agrees (parameters only, no code change).
- Decal ticks (0.4 mm proud) still need the in-engine z-fight check; grooves are real geometry.
- Caliper pads only show their top edge; no hose / bleed nipple. Shells interpenetrate (pockets are the only boolean).
- LOD1 tyre is a 24-gon: visible LOD pop under ~15 m. Metals need the Godot environment check.
