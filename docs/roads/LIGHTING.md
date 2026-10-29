# Street lighting (Mert Road Studio)

Source: `tools/roads/mrs/lighting.py` (Blender side), fixture anchors in `tools/roads/mrs/assets.py::_streetlights()`,
game side `world/roads/mrs_street_lights.gd` (`MrsStreetLights`). Validation: `tools/roads/tests/lighting_test.py`
(Blender, headless) and `tests/capture_lighting.gd` (Godot 4.7.2, needs a renderer). Evidence images are written to
`tmp/roads/v4/lighting/` (git-ignored; regenerate with the two scripts).

```
blender --background --factory-startup --python tools/roads/tests/lighting_test.py      # ~3 min build + ~4 min renders
blender --background tmp/roads/v4/lighting/lighting_test.blend --python tools/roads/tests/lighting_test.py -- --reuse
godot --path . --script res://tests/capture_lighting.gd -- res://tmp/roads/v4/lighting/export res://tmp/roads/v4/lighting 4
```

`mrs/__init__.py` does not list `lighting` in `MODULES` yet (not owned here): use `import mrs.lighting`.

## API (Blender)

| call | does |
|---|---|
| `PRESETS[name]` | road-class presets `residential`, `urban`, `highway`, `path`, `bridge` (+ fixture presets `bollard`, `wallpack`); aliases `avenue`, `boulevard`, `motorway`, `sidewalk`, `park`, `footbridge`, ... |
| `preset_for(road_class, carriageway_width)` | deep copy of the class preset with `arrangement` chosen from the kerb-to-kerb width W and the mounting height H: W <= H one side, W <= 1.5 H staggered, wider opposite (paths: one side up to 1.5 H). Adds `arrangement_rule` (text) and a hint for W > 3 H (median twin-arm). |
| `layout(length, preset, start=None, end=None)` | pole stations `[(along, 'l'/'r')]`; `spacing` = distance between consecutive poles (between pairs for opposite). |
| `fixtures_of(obj)` | fixture anchors of a library object or a placed copy (object prop, mesh prop, or via `mrs_placed`). |
| `add_light_sources(obj, preset, name_prefix=None)` | one light object per anchor, parented to the placed pole, named `<prefix>_Lamp<i>`, aimed along the anchor dir tilted by the preset tilt; replaces earlier ones. Returns the light objects. |
| `remove_light_sources(obj)` | deletes them (and orphaned light data). |
| `add_lights_for_collection(col, preset=None)` | every placed `MRS_Light_*` in a collection; preset = argument, else `mrs_light_class` / `mrs_road_class` on the object, else by library (`LIBRARY_PRESET`). |
| `light_records(col=None)`, `lights_model(col)`, `export_json(path, col, extra)` | game records / the `lights` block for the street-model JSON. |
| `night_setup(scene)`, `day_setup(scene)`, `is_night(scene)` | reversible, idempotent scene setups (below). |
| `kelvin_to_linear(K)`, `linear_to_srgb(c)`, `power_from_candela(cd)`, `fit_godot_cone(blend)` | helpers. |

The placement engine (being rewritten) is expected to: pick `p = preset_for(class, W)`, place `p["library"]` at
`layout(L, p)` stations with lateral offset `half + kerb + p["setback"]` and local +Y toward the carriageway (as
`placement._place` does), then call `add_light_sources(pole, p)`; the exporter adds `lights_model(col)` to the JSON.

## Units and reasoning (no claim of standards compliance)

* Blender light "W": measured in EEVEE and Cycles (`tmp/roads/v4/lighting/calib*.py`): a sun of strength 1 gives a white
  Lambert surface 1/pi; a point or spot of P W gives E = P / (4 pi d^2) on its axis (spot size does not concentrate
  power). The module reads Blender irradiance x 683 as lux, so an axial intensity I (cd) needs P = 4 pi I / 683 W.
* Intensities come from typical luminaire outputs (4,000-18,000 lm road luminaires, ~1,500 lm lanterns) and give the
  nadir illuminances below; uniformity is that of a plain spot cone (cos^3 falloff, no IES / batwing), so pools are
  more pronounced than with real asymmetric optics. The tilt (10-15 deg toward the road) stands in for the
  street-side throw of real optics and cuts the light thrown behind the pole.
* EEVEE culls a light where its intensity falls below `light_threshold` (default 0.01): a 18 W spot would stop at
  ~7 m, i.e. before reaching the road, and an un-windowed light reads ~12 % low. Every light therefore gets
  `use_custom_distance = True`, `cutoff_distance = range` (= Godot `spot_range`), and night_setup lowers
  `light_threshold` to 0.001. With that, the measured axial falloff matches the inverse-square law (0.995).
* Night exposure +7 EV maps ~20 lux on asphalt to mid grey (an eye / camera adapted to street lighting). Moon
  0.004 W/m^2 (~2.7 lux: full moon ~0.25 lux plus urban sky glow, lifted for readability), sky 0.0005 x
  (warm horizon / navy zenith).
* Spot cone: Blender's falloff (measured, identical in EEVEE and Cycles) is smoothstep((cos a - cos c) / ((1 - cos c) blend));
  Godot's is 1 - rim^n with rim = (1 - cos a) / (1 - cos c). Both depend only on (cos a - cos c) / (1 - cos c), so
  `fit_godot_cone(blend)` least-squares fits n (blend 0.40 -> 3.95, 0.45 -> 3.40, 0.60 -> 2.35).
* Colour: black body via the CIE 1931 fit (Wyman, Sloan, Shirley 2013), linear Rec.709 normalised to luminance 1 like
  Blender's own `temperature_color` (worst relative difference 1.6 %, checked in the test). Blender lights use
  `use_temperature`; Godot gets the sRGB colour with max 1 and the factor folded into the energy.
* Godot: `spot_attenuation = 2.0` is inverse square; a white Lambert plane under energy E at d metres reads E / d^2
  (measured ratio 1.005 in `capture_lighting.gd`). Matching the Blender night at tonemap exposure 1:
  energy = P x 2^7 / (4 pi^2) = 3.24 x P (`GODOT_ENERGY_PER_W`), times max(linear colour).

## Presets

| preset | library | H (emitter) | arm | setback | spacing | arrangement | tilt | intensity -> Blender power | nadir | CCT | cone (full / blend) | range | shadow | Godot energy / half angle / cone exp | fade begin + length (shadow) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| residential | MRS_Light_LED | 6.97 m | 0.9 m | 0.5 m | 30 m (4.3 H) | single_right | 15 deg | 1000 cd -> 18.4 W | 20.6 lx | 3000 K | 140 / 0.40 | 25 m | yes | 104.5 / 70 / 3.95 | 60 + 20 (30) |
| urban (avenue) | MRS_Light_Highway | 9.82 m | 2.4 m | 0.6 m | 32 m (3.3 H) | opposite | 10 deg | 3200 cd -> 58.9 W | 33.2 lx | 4000 K | 150 / 0.45 | 35 m | yes | 267.9 / 75 / 3.40 | 80 + 25 (40) |
| highway | MRS_Light_Highway | 9.82 m | 2.4 m | 2.0 m | 40 m (4.1 H) | single_right | 15 deg | 4500 cd -> 82.8 W | 46.7 lx | 4000 K | 150 / 0.45 | 40 m | yes | 376.8 / 75 / 3.40 | 120 + 30 (60) |
| path | MRS_Light_Lantern | 3.66 m | 0 | 0.4 m | 18 m (4.9 H) | single_right | 0 | 260 cd -> 4.8 W | 19.4 lx | 2700 K | 170 / 0.60 | 15 m | no | 29.6 / 85 / 2.35 | 45 + 15 (22.5) |
| bridge | MRS_Light_LED | 6.97 m | 0.9 m | 0.9 m | 24 m (3.4 H) | staggered | 15 deg | 1400 cd -> 25.8 W | 28.8 lx | 4000 K | 140 / 0.40 | 25 m | yes | 117.2 / 70 / 3.95 | 70 + 20 (35) |
| bollard (fixture) | MRS_Light_Bollard | 0.81 m | 0 | 0.3 m | 6 m | single_right | 0 | 25 cd -> 0.46 W | 38 lx at the foot | 3000 K | 175 / 0.60 | 6 m | no | 2.6 / 87.5 / 2.35 | 30 + 10 |
| wallpack (fixture) | MRS_Light_WallPack | 3.22 m | 0.3 m | 0 | 15 m | single_right | 0 (aim in anchor) | 500 cd -> 9.2 W | - | 4000 K | 120 / 0.40 | 15 m | yes | 41.9 / 60 / 3.95 | 45 + 15 |

The arrangement in the table is the preset default; `preset_for` overrides it from the carriageway width (the test
street: residential 6.4 m -> single_right, avenue 24.6 m -> opposite, highway 22.8 m -> opposite, path 3.0 m ->
single_right, bridge 8.0 m -> staggered). Setback is measured from the back of the kerb (placement convention
`half + kerb width + setback`). Spot is the only type the presets use: EEVEE ignores area-light `spread` (measured:
same result at 180 and 90 deg, while Cycles concentrates it 4.5x), so AREA would differ between the engines;
`type: "AREA"` is still supported (rectangle of `area_size`, Godot energy x4 and a cosine lobe).

`light`: Blender light (`type`, `intensity_cd`, `power_w`, `spot_size` full angle, `spot_blend`, `radius` = soft
shadow size, `temperature`, `color` linear, `shadow`, `range`). `godot`: `energy`, `color` (sRGB), `range`,
`attenuation` 2.0, `spot_angle` (half angle), `spot_angle_attenuation`, `shadow`, `fade_begin`, `fade_length`,
`shadow_fade` (= fade_begin / 2). `target`: nadir lux and spacing / height. `reasoning`: one paragraph.

## Fixture contract

Every streetlight library object carries `mrs_fixtures` (JSON string) on the object **and** its mesh (placed copies
share the mesh, so the anchors travel with them): a list with one entry per lamp head,
`{"pos": [x, y, z], "dir": [x, y, z]}` in local metres, origin at the pole base, local +Y toward the road. `pos` is
the head centre 2 cm below (in front of) the emitter faces, `dir` the unit aim before the preset tilt. The tilt turns
`dir` toward the arm (horizontal direction pole -> head; +Y for heads on the pole axis), so the Double's -Y head
tilts toward -Y.

| object | anchors (pos -> dir) | emitter (MRS_PropLamp faces) |
|---|---|---|
| MRS_Light_Highway (10.05 m) | (0, 2.45, 9.80) -> down | 0.17 x 0.4 m under the head, z 9.82 |
| MRS_Light_Double (10.05 m) | (0, +-1.95, 9.80) -> down | two heads |
| MRS_Light_LED (7.03 m) | (0, 0.80, 6.945) -> down | 0.2 x 0.6 m LED panel, z 6.965 |
| MRS_Light_Lantern (4.45 m) | (0, 0, 3.64) -> down | bulb r 0.09 at 3.75 inside the glazing |
| MRS_Light_Bollard (1.0 m) | (0, 0, 0.81) -> down | ring 0.72-0.90 |
| MRS_Light_WallPack (3.5 m) | (0, 0.34, 3.22) -> (0, 0.6, -0.8) | front lens |

Checked by the test: object names / dimensions unchanged, anchors on object and mesh, one per head, every emitter
face within 0.35 m of an anchor, every anchor within 10 cm of its emitter, and for the down-lights the housing is
right above the anchor while the aim (tilt 0 and 10 deg) does not hit the pole's own mesh. The lantern and bollard
lights sit inside their housings, so their presets cast no shadows. The emitter faces were already a separate
material (`MRS_PropLamp`), so no geometry changed; the emissive mesh stays decorative, the light objects do the
lighting.

## Light records (game JSON)

`light_records(col)` -> one dict per light object (`mrs_light = 1`), sorted by name:

```
id, parent (placed pole), library, class, type (spot | omni), axes "z_up (godot: x, z, -y)",
position [x, y, z]  (Blender world, Z-up, metres), direction [x, y, z] (unit aim, Blender world),
color (sRGB, max 1: Godot light_color), color_linear (luminance 1), temperature (K),
energy (Godot light_energy), power_w (Blender), range (m), attenuation (2.0), spot_angle (half angle, deg),
spot_angle_attenuation, shadow (bool: may cast shadows), fade_begin, fade_length, shadow_fade (m)
```
Coordinates stay Z-up like the rest of `STREET_MODEL.md`; Godot = (x, z, -y). `lights_model(col)` wraps them:
`{version, units, axes, godot_energy_per_w, night_exposure_ev, night {exposure_ev, lamp_emission, moon {strength,
color, direction, godot_energy}, sky {strength, horizon / zenith colours, godot_* pre-multiplied}}, presets, lights}`.
World positions come from the parent chain (valid before the depsgraph has evaluated new objects). Lights tagged
`mrs_light` by other generators (e.g. the footbridge's own POINT lights) get records derived from the light data:
type from the Blender type (POINT -> omni), energy = power x `GODOT_ENERGY_PER_W`, range = custom distance or 20 m,
colour from temperature / colour, no shadows.

GLB: the test exports roads + poles **without** `KHR_lights_punctual` (`export_lights=False`). The game builds the
lights from the records instead: one source of truth for energies / fades / shadow policy, and Godot's glTF importer
would create lights with its own unit conversion, no distance fade and fixed shadow flags, duplicating the JSON
lights. The lamp heads export with `KHR_materials_emissive_strength`.

## Night / day (Blender)

`night_setup(scene)`: world `MRS_NightWorld` (gradient warm horizon -> navy zenith; colour and strength come from
linked nodes so `qa.ensure_camera_and_sun`, which resets the Background node's defaults, cannot turn it back to day),
`MRS_Moon` sun (0.004 W/m^2, bluish, 1.5 deg soft shadows, 35 deg elevation), day suns hidden, AgX view at +7 EV,
EEVEE: `use_shadows`, `shadow_ray_count` 2, `shadow_step_count` 8, `shadow_resolution_scale` 1, `shadow_pool_size`
1024 MB, `light_threshold` 0.001; light sources `hide_render = False`; lamp materials (names starting
`MRS_PropLamp` / `MRS_Lamp`) emission strength 40. Per light: `use_shadow_jitter` (soft shadows from `radius`),
custom distance = range. The first call stores the day state on the scene (`mrs_lighting_state`); repeated calls only
re-apply. EEVEE (Next) in 5.2 has no light-count setting (read from RNA: `scene.eevee` exposes `light_threshold`,
`shadow_pool_size`, `shadow_ray_count`, `shadow_step_count`, `shadow_resolution_scale`, `use_shadows`; per light
`use_custom_distance`, `cutoff_distance`, `use_shadow_jitter`, `shadow_soft_size`, `use_temperature`).
`day_setup(scene)`: restores world, view transform / look / exposure / gamma, the EEVEE values and sun visibility,
hides the moon and the light sources (streetlights are off by day) and sets the lamp emission to 0. Verified in the
test: day -> night -> night -> day returns the same world, exposure, threshold and sun state.

## Godot strategy (`MrsStreetLights`)

```gdscript
var lights := MrsStreetLights.new(); add_child(lights)
lights.build(records, {"max_shadowed": 4, "focus": camera.global_position, "lamp_root": poles})
lights.follow(camera)        # re-pick shadow casters every 0.25 s once the camera moved 2 m
lights.set_night(1.0)        # 0 = day: lights hidden, lamp emission off; in between dims (dusk)
```
* One `SpotLight3D` per record (`OmniLight3D` for type omni): `spot_range` = record range (25-40 m), inverse-square
  `spot_attenuation` 2.0, `spot_angle` = half the Blender cone, fitted `spot_angle_attenuation`.
* Distance fade on every light (`distance_fade_begin/length`: residential 60+20, bridge 70+20, urban 80+25, highway
  120+30, path 45+15 m; `fade_scale` option for quality levels); shadows fade at `distance_fade_shadow` = begin / 2.
  Beyond that a lamp is only its glowing head (emissive material) - the classic far-field trick, and it keeps the
  per-view light count well under Forward+'s clustered element limit (512 by default).
* Shadows: only records with `shadow = true` (all road classes except path / bollard), and only the `max_shadowed`
  (default 4) with the largest energy / d^2 at the focus inside their shadow distance; all others are shadow-free.
  Godot's positional shadow atlas holds 4 + 4 + 16 + 64 shadows by default and caches static shadows, so the steady
  cost is low; it grows when moving geometry (cars, people) is inside a shadowed light's range.
* `light_bake_mode` = disabled by default (`bake_mode` option: `static` for baked LightmapGI nights, `dynamic` feeds
  SDFGI / VoxelGI at a per-light cost).
* `energy_scale` option: the energies match the Blender night at tonemap exposure 1; the game's own night
  environment (ambient, exposure) may want a different scale.
* Lamp heads: `collect_lamp_materials(root)` finds `MRS_PropLamp*` / `MRS_Lamp*` materials (surface, override and
  material_override) and `set_night` sets `emission_enabled` / `emission_energy_multiplier` (default 6) on them.

## Measured (tools/roads/tests/lighting_test.py, tests/capture_lighting.gd)

Test street: five straight 60 m roads 80 m apart (residential, urban avenue 2+2 with parking / buffered bike lanes /
median, highway 2+2 with shoulders and guardrails, 3 m path, elevated 2-lane bridge with parapets), poles from
`layout(60, preset_for(...), start=0)`, 18 lights (14 with shadow-capable presets). Result: **PASS**.

Aim check (analytic): every light points down (direction z < -0.85); the aim hits the street (carriageway + kerb +
sidewalk) and, for arm luminaires, lands inside the pole line; post-top lanterns aim straight down at their pole.

Pools (orthographic top-down EXR, 0.2 m/px, x 0..60 m, scene-linear luminance x 1e-3; "off" = light objects hidden,
moon / sky / glowing heads unchanged):

| class | carriageway on / off | sidewalk on / off | outside on | gain (carriageway) | share of added light on the street | pool centroid |
|---|---|---|---|---|---|---|
| residential | 0.439 / 0.095 | 1.051 / 0.257 | 0.151 | 4.6x | 71 % | -1.4 m (right lanes, lights on the right) |
| urban | 1.054 / 0.125 | 1.955 / 0.255 | 0.419 | 8.5x | 85 % | 0.0 m (opposite pairs) |
| highway | 1.337 / 0.118 | - | 0.771 | 11.3x | 58 % | 0.0 m |
| path | 0.503 / 0.100 | - | 0.155 | 5.0x | 31 % (post-tops beside a 3 m path) | -2.3 m = lantern line |
| bridge | 0.700 / 0.111 | 1.628 / 0.221 | 0.167 | 6.3x | 84 % | -0.7 m |

So the street is lit by the light objects (4.6-11x over moon + sky + glowing heads), not by the emissive heads;
the `nolights` renders show the same (heads still glow, road dark). Kelvin colour vs Blender black body: worst
1.6 %. night_setup / day_setup: day -> night -> night -> day restores world, exposure, light threshold and sun.
EEVEE render time 1280x720, 48 samples: 2-5 s per night view (RTX 3070 Laptop).

Godot 4.7.2 (D3D12 Forward+, RTX 3070 Laptop GPU, 1280x720, vsync off):

* calibration: white Lambert plane under energy 10 at 5 m reads 0.402 (energy / d^2 = 0.4), ratio 1.005.
* build of 18 lights: 1.6-3 ms; 18 active, 1 lamp material found and toggled; day: 0 active, 0 shadowed, emission off.
* per view: 3-11 lights within fade distance, 0-4 shadow-casting (overhead views at ~55 m have none: beyond the
  shadow fade), GPU 0.9-1.35 ms, CPU 0.16-0.4 ms, frame 1.1-2.0 ms.
* shadow budget on the avenue driver view: 0 -> 0.99 ms GPU, 4 -> 1.08 ms (more are not eligible there: only 4
  shadow-capable lights inside their shadow distance).
* stress, records tiled into ~1.9 km x 3 streets = 671 lights, camera on the avenue: with distance fade 26 lights
  drawn, 4 shadow-casting: GPU 1.09 ms / CPU 0.31 ms; 0 shadows 0.98 / 0.27; budget 16 (6 eligible) 1.10 / 0.31;
  fade off (671 drawn) 1.26 / 0.44 ms. The scene is light (68k tris, static shadows cached), so absolute costs are
  small; the fade cuts the per-view light list 26x and leaves far streets as glowing heads only.

## Evidence

All under `tmp/roads/v4/lighting/` (regenerated by the scripts above):

| file | shows |
|---|---|
| `sheet_night_blender.png` | EEVEE night, rows residential / urban / highway / path / bridge, columns driver (1.2 m, path 1.4 m) / pedestrian (1.65 m on the sidewalk; highway: verge) / overhead |
| `sheet_night_godot.png` | the same 15 views in Godot (`godot_night_<class>_<view>.png`) |
| `sheet_blender_vs_godot.png` | side by side: residential driver, avenue pedestrian, path pedestrian, highway overhead |
| `sheet_day_night_nolights.png` | residential and avenue driver: day / night / night with the light objects hidden |
| `sheet_pools.png`, `measure/<class>_added_light.png` | light added by the light objects (on - off, log scale, top down, +Y up; blue dotted = carriageway / street edges) |
| `sheet_godot_stress.png` | 671 tiled lights, distance fade on vs off |
| `inspect/row_side.png`, `inspect/row_below.png` | the six library streetlights by day (inspection before the work) |
| `export/lighting_street.glb`, `export/lighting_lights.json` | roads + poles (30 MB with baked 1K tiles, 67,902 tris, no punctual lights), 18 records + views + pools + night block |
| `lighting_test.blend` | the test scene (night state), `--reuse` input |

Library judgement (inspection renders): the Highway / Double cobra heads are boxy but read correctly at street
distance and already had a separate flat emitter; the 7 m LED head is a plain 6 cm slab - acceptable from the
road, plain from below; the lantern is a good decorative path light. Within the allowed scope (anchors only, names /
dimensions / collection unchanged) no geometry was changed.

## Known issues / limits

* Spot cones are symmetric (no IES / batwing / house-side shield): pools are centred under the head and part of the
  light falls behind the pole (residential 71 %, highway 58 % of the added light on the street); the tilt only
  partly stands in for asymmetric optics. Post-top lanterns beside a 3 m path put ~1/3 of their light on it.
* All six luminaires share one lamp material (`MRS_PropLamp`), so one night emission strength (40 in Blender, 6 in
  Godot) for all; per-type luminance (LED panel vs lantern bulb) and per-pole switching / flicker would need separate
  materials (or `material_override` per pole in Godot).
* `mrs.export.engine_material` (not owned here) drops the alpha of `MRS_PropGlass`, so the lantern glazing is
  opaque in the GLB and the bulb is hidden in Godot (only the glow at the base shows).
* The lantern and bollard lights sit inside their housings: no shadows by design (path / bollard presets).
* Bridge setback 0.9 m assumes the road group's parapet (placed at the sidewalk edge - 0.25 m, ~0.5 m wide).
* Overhead views at 55-63 m are inside the fade zone of the residential (60 + 20) and path (45 + 15) presets, so in
  Godot those pools dim / vanish there (the fade working as designed; use `fade_scale` for map / drone cameras).
* Godot energies match the Blender night at tonemap exposure 1 and this capture's environment; the game's current
  night (ambient energy 1.6, exposure 1.05) is brighter, so it may want `energy_scale` < 1 or a darker ambient.
* Arrangements are single_left / single_right / opposite / staggered; a median twin-arm layout (MRS_Light_Double,
  whose two anchors are supported) is only suggested by `preset_for` for W > 3 H, not placed.
* Light objects by day are switched off with `hide_render`; their viewport visibility is not changed.
* `mrs/__init__.py` MODULES does not include `lighting` yet (reload() will not refresh it); import it explicitly.
