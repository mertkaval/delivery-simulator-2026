# G3 body surfaces — engineer notes (sedan_v2_body, g3_body_v3)

Starting point: approved G2 v2p. Four geometry builds (renders `g3_body_v1` = build 2, `g3_body_v2` = build 3,
`g3_body_v3` = build 4, final), plus one rebuild that only added a second material slot to BumperSkirt.
Final set: `production/renders/g3_body_v3/` — seven clay views, two 833 px/m arch close-ups, two zebra views.

## What changed (sedan_body.py / build_sedan_v2.py)
- **Frame.** All stations are measured from the sheet nose `Y_NOSE` (2.325); the cage end `Y_FRONT` only compensates
  the end-cap pull. The subdivided nose/tail land on the first/last ring station, so those are pinned → L 4.800,
  nose 2.325, tail −2.475. Shut lines sit at y 0.96 / −0.27 / −1.34 (sheet), closing P3-11 and P3-4.
- **P2-1** chamfer along the corner normal (`end_shape`): for |x|/(W/2) > 0.55 part of the lift becomes an inward x pull.
- **P2-2** arch-wall foot at the sill-bottom height (`arch_section` FLOOR_E z = FLOOR_Z+0.045) and the liner kept
  50–90 mm inside the subdivided wall. The “tabs” were the body’s own arch-end wall foot, not the liner.
- **P2-3** shoulder: straight through the handles (0.83 @ y 0, 0.865 @ y −1.15), eased to 0.80 at the headlamp top and
  bowed to 0.95 at the tail-lamp top. Measured on the mesh: 0.799 / 0.831 / 0.865 / 0.947.
- Greenhouse ring blends into the hood/trunk layout over the last 0.30 m before the cowl / behind the screen base
  (P3-7 S-ripple, P3-8 corner dip). Trunk lid now falls continuously (P3-12) with a creased lip 0.17 m from the tail.
- Hood power dome (ridges at x ±0.15, ~7 mm, cowl → 0.3 m behind the nose). Hood leading-edge gap at y 2.08 ends on
  the headlamp cut.
- **DLO.** Side glass is a cage rectangle (belt→cant, rear door edge→A pillar) trimmed by plane cuts
  (`bmesh.ops.bisect_plane`, no boolean): raked A-pillar line and forward-leaning C-pillar line; screens trimmed by
  plan-view side lines. Glass = one object (screens 5 mm, side glass 12 mm inboard along stored shell normals; black
  ceramic band = boundary face row). BPillar = separate black band 14 mm inboard. The body’s opening rim is extruded
  inboard as a black window-surround wall (depth matched per edge).
- **Apertures** (headlamps, grille, intake on the skirt, tail lamps, fuel flap, mirror pads) at sheet positions:
  plane cuts bound the region exactly, then `inset_region` sinks the floor 9 mm (2 mm for flap/pads), BlackTrim,
  sharp edges, weighted normals with keep_sharp.

## What the renders show (inspected)
- clay_front / front_34 / zebra_hood: lower corner rolls, no diagonal fold; hood gaps straight and ending on the lamps;
  dome ridges read as two soft highlights; zebra bands continuous over the hood and fenders.
- arch close-ups: clean circular lips, no tabs below the sill, liner dark inside.
- clay_left/right, zebra_left: continuous shoulder crease rising to the rear with the kick over the quarter; A/C-pillar
  glass lines, B-pillar band, fuel flap, lamp apertures visible; strips continuous along the side.
- clay_rear / rear_34: tail lamps wrap the corners, trunk lip crisp, rear-screen edges clean (build 3 fins gone).
- clay_top: windscreen/rear-screen side edges straight after dropping the inset band.

## Open items / known defects
See `g3_body_handoff.json → known_defects` (A-pillar glass top-corner stair, C-pillar groove hook, grille pole facet,
band width, 98 mm B pillar, n-gons from the cuts, 21.7–23° rear screen).

## Pipeline notes
- Render out_dir must be absolute: relative paths resolved to the drive root once; a stray empty
  `C:\production\renders\g3_body_v1\` remains for the user to delete.
- `zebra_render.py` is new (glossy clay, 5 strip lights; left ortho + hood view).

## v3.1 (after independent QA of v3, `G3_visual_qa_v3.md`) — renders `g3_body_v3_1/`
- **P2-1 closed**: the windscreen zone had claimed the side-glass G1..CANT faces for y > 0.105, which left a vertical
  glass edge at y 0.163; zone 4 is now the roof-plane faces (+ G faces only in the cowl blend), the windscreen plan line
  moved to x 0.72→0.56 so a 50–80 mm painted A pillar separates it from the side glass, and the raked A-line runs into
  the cant rail as one acute corner (apillar_corner_left/right.png).
- **P2-2 closed**: tail-lamp aperture x bound opened to the quarter skin → lamp y −2.011..tail, wraps the corner
  (tail_lamp_left.png, clay_rear_34).
- P3: ceramic band = constant 15 mm (parallel plane cuts inboard of each straight boundary run, then distance test);
  aperture floors sunk along smooth pre-inset vertex normals (grille pole rise 1.7 mm, was 4–5); HOOD_X_NOSE 0.46 →
  headlamp nose inner edge 0.479; B pillar 83 mm. Remaining: C-pillar groove hook (~50 mm), faint pole mark, 21.7° screen.
- Mesh-verified; 91,539 tris incl. placeholder wheels (Body 76,214). New script `detail_crops.py`.
