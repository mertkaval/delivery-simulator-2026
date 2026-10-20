# Vehicle Dimension Sheet — fictional mid-size sedan ("production" vehicle)

Reference Engineer audit, 2026-10-19.
Sources: `ref_left_side.webp`, `ref_right_side.webp`, `ref_front.webp`, `ref_rear.webp`,
`reference_pixel_measurements.json` (silhouette bbox, tyre clusters, top_profile, glass extents).

Label legend
- **MEASURED** — a dimensionless ratio read from the reference pixels. The pixel source is given.
  "visual" means a landmark located by eye on the image (±15 px ≈ ±0.01 L / ±0.03 H); "json" means it comes from the extracted JSON.
- **PROPOSED TARGET** — a metric value chosen by the engineer, with reasoning. Every metre value in this sheet is a PROPOSED TARGET;
  the references carry no absolute scale. Metric values computed as `measured ratio × target` are labelled "target (derived)".

Modelling frame (used for all landmarks): metres, origin on the ground plane at the wheelbase centre,
+Y = car front, +Z = up, +X = car right (driver's right when seated). "Left/right view" refers to the side of the car shown.

---

## 1. Side-view analysis (dimensionless ratios)

Left view: image 1919×820, silhouette x 78→1791 (L_px = 1713), y 135→705, ground line taken at y ≈ 700 (tyre bottoms 698/702; bbox 705 includes shadow). Front of car on image left.
Right view: image 1774×887, silhouette x 51→1711 (L_px = 1660), y 190→749, ground ≈ 739. Front of car on image right.

Tyre clusters: real wheels are the 289–313 px clusters. The 40/45/94 px clusters (left x=151, x=1739; right x=1647) are headlamp/tail-lamp dark trim, NOT wheels — ignored.

| Ratio | Left view (MEASURED) | Right view (MEASURED) | Pixel source | Real sedan (sanity) |
|---|---|---|---|---|
| wheelbase / L | 0.607 | 0.607 | json wheel x_centers 389→1428 (1039 px); 375→1383 (1008 px) | 0.58–0.60 |
| wheel (tyre) dia / L | 0.183 front, 0.181 rear | 0.189 front, 0.174 rear | json dia_px 313/310; 313/289 | 0.135–0.14 |
| height / L | 0.333 | 0.337 | json bbox | 0.30–0.31 |
| front overhang / L | 0.182 | 0.198 | bbox edge → front wheel centre | 0.18–0.20 |
| rear overhang / L | 0.212 | 0.195 | rear wheel centre → bbox edge | 0.20–0.23 |
| roof peak position / L (from front) | 0.583 | 0.584 | top_profile min y (x=1077, y=135; x=742, y=190) | 0.55–0.60 |
| roof plateau (within 9 px of peak) / L | 0.54 → 0.71 | 0.53 → 0.70 | top_profile | — |
| belt line (front-door glass bottom) / H | 0.663 | 0.678 | visual, y≈322; y≈360 | 0.65–0.69 |
| windscreen base (cowl) / L from front | 0.264 | 0.254 | top_profile slope break x≈530; x≈1290 (visual refinement) | 0.25–0.28 |
| windscreen top (roof start) / L | 0.468 | ~0.47 | top_profile slope break x≈880 | 0.45–0.50 |
| roof end (rear-screen top) / L | 0.713 | ~0.72 | top_profile slope break x≈1300 | 0.68–0.74 |
| rear-screen end (trunk start) / L | 0.888 | 0.89 ±0.03 | visual x≈1600; x≈230 | 0.85–0.90 (fastback) |
| hood height at nose (headlamp top) / H | 0.526 | 0.556 | top_profile x=149,y=385 / visual y≈400; x=1641,y=428 | 0.52–0.58 |
| hood height at cowl / H | 0.693 | 0.687 | top_profile y≈305 at x=506–530; y≈355 at x=1296 | 0.66–0.70 |
| greenhouse height (roof − belt) / H | 0.328 | 0.32 | derived | 0.32–0.36 |
| sill (rocker bottom) height / H | 0.114 | ~0.11 | visual y≈635 | 0.10–0.12 |
| windscreen angle from horizontal (pixel space) | 24.3° | ~24° | atan((305−147)/(880−530)) | 27–32° |

Left-vs-right inconsistencies (the right image is a different AI generation):
1. Overhang split differs: left 0.182/0.212 (rear-biased, classic sedan), right 0.198/0.195 (balanced). Wheelbase ratio is identical, so the body was stretched differently at the ends.
2. Right view rear tyre cluster is 289 px vs 313 px front — not a design feature; the cluster is clipped by the bumper shadow. Both wheels are equal.
3. Right view headlamp is a 3-element projector unit with a slightly deeper lower grille; left view headlamp is a slimmer 2-element unit. Right view is also shot ~1° higher (more hood top visible).
4. JSON `glass_rows`/`glass_cols` are unreliable (142→411 includes headlamp/mirror dark pixels). Visual glass extents were used instead.
5. Belt line 0.663 vs 0.678 and nose height 0.526 vs 0.556 — within AI-generation noise (±0.03 H). Averages used.

## 2. Comparison to real sedans and resolution (CONFLICT C1)

The reference wheels are 0.18 L. At a real 4.80 m length that would be an 0.87 m tyre; conversely keeping a 0.66 m tyre at the reference ratio gives a 3.6 m toy car. The oversize wheels also inflate the reference height ratio (0.333 vs ~0.30 real) because the body sits higher over them.

**Resolution (adopted):** keep real-world overall dimensions and a real 17-inch / 225/50 wheel (0.66 m). Use the references for shape and feature design only: horizontal positions are taken as fractions of L, vertical positions as fractions of H (this implicitly applies a vertical squash of 0.302/0.333 = 0.907 to the body, which is the correct correction for the wheel-driven height inflation). Wheel arches are sized from the real tyre, not from the image.

## 3. Dimension sheet

| # | Item | Value | Status | Source / reasoning |
|---|---|---|---|---|
| 1 | Overall length L | 4.80 m | PROPOSED TARGET | mid-range of the 4.7–4.9 m brief; gives round axle positions |
| 2 | Overall width W (body, no mirrors) | 1.85 m | PROPOSED TARGET | brief 1.84–1.86 m |
| 3 | Width incl. mirrors | 1.98 m | target (derived) | front view mirror outer x=172 vs body 210→1325 → 1.07 W; real cars 2.05–2.10, low confidence (perspective) |
| 4 | Overall height H | 1.45 m | PROPOSED TARGET | brief 1.44–1.47 m |
| 5 | Wheelbase | 2.85 m | PROPOSED TARGET | measured 0.607 L → 2.91 m exceeds the 2.78–2.85 brief; brief upper limit taken (−2 % vs ref). See C2 |
| 6 | Track front / rear | 1.60 / 1.60 m | PROPOSED TARGET | brief; front/rear images cannot resolve track |
| 7 | Front overhang | 0.90 m | PROPOSED TARGET | measured 0.182–0.198 L → 0.87–0.95 m; 0.90 m with L−WB = 1.95 m total |
| 8 | Rear overhang | 1.05 m | PROPOSED TARGET | measured 0.195–0.212 L → 0.94–1.02 m; takes the remainder; keeps the left-view rear-biased stance |
| 9 | Tyre diameter | 0.66 m | PROPOSED TARGET | 225/50 R17; see C1 |
| 10 | Tyre width | 0.225 m | PROPOSED TARGET | 225 section |
| 11 | Rim diameter | 0.432 m (17 in) | PROPOSED TARGET | — |
| 12 | Wheel-arch opening diameter | 0.74 m | target (derived) | arch lip ≈ 1.12 × tyre in left view (≈350 px vs 313 px) |
| 13 | Ground clearance (under-floor) | 0.15 m | PROPOSED TARGET | typical sedan 0.14–0.16 m |
| 14 | Sill (rocker bottom) height | 0.165 m | target (derived) | MEASURED 0.114 H (left y≈635) |
| 15 | Belt line height, front door | 0.97 m | target (derived) | MEASURED 0.663–0.678 H, avg 0.67 |
| 16 | Hood height at nose (headlamp top) | 0.78 m | target (derived) | MEASURED 0.526–0.556 H, avg 0.54 |
| 17 | Hood height at cowl | 1.00 m | target (derived) | MEASURED 0.69 H |
| 18 | Cowl / windscreen base from front bumper | 1.25 m | target (derived) | MEASURED 0.254–0.264 L, avg 0.26 |
| 19 | Windscreen top / roof start from front | 2.25 m | target (derived) | MEASURED 0.468 L |
| 20 | Roof peak from front | 2.80 m (plateau 2.6→3.4 m) | target (derived) | MEASURED 0.583 L; plateau 0.54–0.71 L |
| 21 | Roof end (rear-screen top) from front | 3.42 m | target (derived) | MEASURED 0.713 L |
| 22 | Rear-screen end / trunk start from front | 4.25 m | target (derived) | MEASURED 0.888 L (±0.03) |
| 23 | Trunk lid height at screen end / at lip | 1.10 / 1.02 m | target (derived) | MEASURED 0.763 H (y≈265) / 0.702 H (y≈300) |
| 24 | Roof width, cant rail to cant rail | 1.25 m | PROPOSED TARGET | front view gives 0.59 W = 1.10 m but the shot is perspective; real 1.25–1.30 m. See C4 |
| 25 | Body width at shoulder (belt line) | 1.80 m | PROPOSED TARGET | front view shoulder ≈ 0.87 W; 1.80 m keeps 25 mm per side inside the arches |
| 26 | Body width at sill | 1.74 m | PROPOSED TARGET | typical rocker inset |
| 27 | Tumblehome (belt → cant rail) | ≈31° from vertical (0.275 m per side over 0.45 m) | target (derived) | from #15, #24; glass to be curved so the upper DLO reads ~22° |
| 28 | Greenhouse height | 0.48 m | target (derived) | H − belt; MEASURED 0.328 H |
| 29 | A-pillar / windscreen angle | 24° from horizontal (66° rake) | target (derived) | from #17, #18, #19; pixel-space 24.3°. Shallower than the typical 27–32° — fastback intent. See C5 |
| 30 | Rear-screen angle | 20° from horizontal | target (derived) | from #21, #22, #23; very fast, fastback intent. See C5 |
| 31 | Headlamp extent (side) | Y 2.25→1.84, Z 0.64→0.78 | target (derived) | left view x 105→250, y 400→450 |
| 32 | Headlamp extent (front) | X ±0.48→±0.86, Z 0.65→0.82 | target (derived) | front view x 250→480 / 1050→1280, y 460→550 |
| 33 | Grille (black horizontal bars) | X ±0.48, Z 0.56→0.72 | target (derived) | front view x 480→1060, y 510→600 |
| 34 | Lower honeycomb intake | X ±0.50, Z 0.25→0.39 | target (derived) | front view x 470→1080, y 690→770 |
| 35 | Fog-lamp bezels | X ±0.63→±0.86, Z 0.27→0.47 | target (derived) | front view x 250→390, y 650→760 |
| 36 | Tail lamps (side) | Y −2.00→−2.42, Z 0.79→0.95 | target (derived) | left view x 1620→1770, y 325→390 |
| 37 | Tail lamps (rear) | X ±0.32→±0.85, Z 0.79→0.96 | target (derived) | rear view x 300→590 / 950→1240, y 370→460 — agrees with the side view |
| 38 | Rear reflectors | X ±0.62→±0.85, Z 0.37→0.43 | target (derived) | rear view y 655→690 |
| 39 | Diffuser (black) | X ±0.81, Z 0.20→0.37 | target (derived) | rear view x 320→1215, y 690→780 |
| 40 | Exhaust tips (twin) | X ±0.50, Z 0.21, Ø ≈0.07 | target (derived) | rear view x≈490/1050, y≈775 |
| 41 | Mirror (housing) | Y 0.61→0.86, Z 0.97→1.08, outer X ±0.99 | target (derived) | left view x 600→690, y 275→320; front view x 172/1363 |
| 42 | Front door handle | Y −0.13→+0.12, Z 0.83 | target (derived) | left view x 865→955, y≈375 |
| 43 | Rear door handle | Y −1.27→−1.02, Z 0.865 | target (derived) | left view x 1270→1360, y≈360 |
| 44 | Fuel flap (left side, X = −0.90) | Y −1.77→−1.55, Z 0.78→0.93 | target (derived) | left view x 1460→1540, y 335→395 |
| 45 | Shark-fin antenna | Y −1.24→−1.10, base on roof, h ≈0.05 | target (derived) | left view x 1300→1350 at roof end; rear view centred |
| 46 | B-pillar centre | Y −0.27 | target (derived) | left view x≈1005 (0.541 L) |
| 47 | Front door leading edge | Y +0.96 | target (derived) | left view x≈565 (0.284 L) |
| 48 | Rear door trailing edge | Y −1.34 | target (derived) | left view x≈1385 (0.763 L) |

## 4. Landmark table (modelling frame; metres; origin ground / wheelbase centre; +Y front, +Z up, +X right)

| Landmark | X | Y | Z | Status |
|---|---|---|---|---|
| Front axle centre | ±0.80 (track/2) | +1.425 | 0.33 | target |
| Rear axle centre | ±0.80 | −1.425 | 0.33 | target |
| Front bumper face (most forward point) | 0 | +2.325 | 0.35–0.55 | target |
| Rear bumper face | 0 | −2.475 | 0.35–0.60 | target |
| Nose / headlamp top line | ±0.48→±0.86 | +2.25 | 0.78 | target (derived, 0.54 H) |
| Cowl / windscreen base | 0 | +1.075 | 1.00 | target (derived) |
| Windscreen top / roof start | 0 | +0.08 | 1.44 | target (derived) |
| Roof peak | 0 | −0.47 | 1.45 | target (derived) |
| Roof end / rear-screen top | 0 | −1.10 | 1.43 | target (derived) |
| Rear-screen end / trunk start | 0 | −1.94 | 1.10 | target (derived) |
| Trunk lip | 0 | −2.45 | 1.02 | target (derived) |
| Belt line, front door (glass bottom) | ±0.90 | +0.9→−0.3 | 0.97 | target (derived) |
| Cant rail (roof edge) | ±0.625 | +0.1→−1.1 | 1.40 | target |
| Sill / rocker bottom | ±0.87 | −1.3→+0.9 | 0.165 | target (derived) |
| Shoulder character line | ±0.92 | +2.0→−2.0 | 0.80 (front) → 0.95 (rear) | target (derived; rises from headlamp top to tail-lamp top) |
| Headlamp (each) | ±0.48→±0.86 | +1.84→+2.25 | 0.65→0.80 | target (derived) |
| Grille bars | ±0.48 | +2.30 | 0.56→0.72 | target (derived) |
| Lower intake | ±0.50 | +2.32 | 0.25→0.39 | target (derived) |
| Fog bezels (each) | ±0.63→±0.86 | +2.30 | 0.27→0.47 | target (derived) |
| Mirror housing (each) | ±0.90→±0.99 | +0.61→+0.86 | 0.97→1.08 | target (derived) |
| Front door handle (each) | ±0.92 | −0.13→+0.12 | 0.83 | target (derived) |
| Rear door handle (each) | ±0.92 | −1.27→−1.02 | 0.865 | target (derived) |
| B-pillar | ±0.90 | −0.27 | 0.97→1.42 | target (derived) |
| Fuel flap (left) | −0.90 | −1.77→−1.55 | 0.78→0.93 | target (derived) |
| Tail lamp (each) | ±0.32→±0.85 | −2.00→−2.42 | 0.79→0.95 | target (derived) |
| Rear reflectors (each) | ±0.62→±0.85 | −2.47 | 0.37→0.43 | target (derived) |
| Diffuser | ±0.81 | −2.47 | 0.20→0.37 | target (derived) |
| Exhaust tips (each) | ±0.50 | −2.47 | 0.21 | target (derived) |
| Shark-fin antenna | 0 | −1.24→−1.10 | 1.43→1.48 | target (derived) |
| Wheel-arch centre = axle; arch radius 0.37 | ±0.90 | ±1.425 | 0.33 | target (derived) |

## 5. Design features to reproduce (from the images)

- Slim LED headlamps (2–3 projector elements, L-shaped DRL signature along the lower edge) that run inboard and meet a black grille of 3 horizontal bars; the grille is a wide shallow trapezoid just below the hood's leading edge, body-colour bar above it.
- Lower bumper: wide honeycomb intake with a body-colour surround lip, flanked by black fog bezels with small LED fog lamps; black lower splitter edge.
- Hood with two soft power bulges running from the A-pillars to the headlamp inner corners.
- 5 twin-spoke silver alloys (10 spoke tips), dark centre cap, low-profile tyre.
- Body-colour mirror housings on a short black stalk at the front-door belt corner (not on the A-pillar).
- Fastback-ish profile: long rear screen (~20° from horizontal) flowing into a short high trunk lid with a small integrated lip spoiler; roof plateau between B-pillar and rear-screen top.
- Shoulder character line from headlamp top, through both door handles, rising to the tail-lamp top; a second lower crease along the rockers sweeping up to the rear arch.
- Wrap-around red tail lamps with a dark smoked inner band (two-tone red/dark), joined visually across the trunk by a body-colour crease; separate lower red reflectors in the bumper.
- Black rear diffuser with twin round chrome exhaust tips; four parking sensors in the bumper; small shark-fin antenna at the roof end.
- Chrome pull-type door handles on both doors; fuel flap on the left rear quarter; black B-pillar trim, body-colour A- and C-pillars, chrome DLO surround upper edge.
- Black-rimmed windscreen and rear-screen surrounds.

## 6. Conflict log

| ID | Conflict | Resolution |
|---|---|---|
| C1 | Reference wheel = 0.18 L vs real 0.135–0.14 L (would be a 0.87 m tyre at L=4.80 m). | Keep 0.66 m tyre and real-world L/W/H; references used for shape only. Arches 0.74 m. |
| C2 | Reference wheelbase 0.607 L → 2.91 m at L=4.80, above the 2.78–2.85 brief. | Wheelbase 2.85 m (−2 %). Overhangs absorb the difference (0.90/1.05). |
| C3 | Reference H/L 0.333 vs real 0.302 (caused by C1). | Vertical landmarks taken as fractions of H → implicit 0.907 vertical squash of the body. |
| C4 | Front view: body W/H ≈1.41 vs real 1.28; roof width reads 0.59 W. Perspective product shot, slightly elevated camera. | Front/rear views used only for lateral feature layout (X of lamps, grille, exhausts); W, roof width and track taken from real-world targets. |
| C5 | Derived windscreen (24°) and rear-screen (20°) angles are shallower than typical sedans (27–32°). | Accepted as fastback design intent; modeller may raise the windscreen to 26° by moving the cowl 0.08 m forward if the interior package needs it. |
| C6 | Left vs right view disagree on overhang split (0.182/0.212 vs 0.198/0.195) and headlamp/grille details. | Left view is the primary profile reference (cleaner silhouette, conventional stance). Right view used only to confirm wheelbase ratio and roof peak. |
| C7 | JSON glass_rows/glass_cols include non-glass dark pixels; small tyre clusters (40–94 px) are lamps, not wheels. | Discarded; visual glass extents and only the 290–313 px clusters used. |
| C8 | Right-view rear wheel cluster 289 px vs 313 px front. | Detection artefact (bumper shadow). Both wheels equal. |
