# G6 vehicle materials — Godot 4.7.2 material study

Engine: Godot v4.7.2 Forward+, CedarNeighborhood rig (`world/neighborhood.gd`: sky-shader radiance for ambient and
reflections, SSAO/SSIL, glow, AgX, exposure 1.05). Table: `world/vehicles/vehicle_materials.gd` (`VehicleMaterials`).
Capture: `tests/capture_materials.gd` — one column per slot (0.5 m sphere, r0.3 x 0.4 m curved cylinder panel, 0.1 m
cube, Label3D) on Ataturk Avenue at (3, 0, -300), camera 10 m back at 2.4 m height (wide) and 3 m (close, metals group).
Each capture prints the mean sRGB of a 9x9 window on the upper-left quadrant of every sphere (sun side). Three table
iterations were needed (four runs: the fourth only fixed the capture's probe timing).

## Final table (StandardMaterial3D; `metallic_specular` = spec)

| Slot | Albedo | Metal | Rough | Spec | Extras |
|---|---|---|---|---|---|
| VehiclePaint | #d6d8db | 0.75 | 0.32 | 0.6 | clearcoat 1.0 / 0.10; flake normal: NoiseTexture2D cellular 256px `as_normal_map`, normal_scale 0.12, uv1_scale 60 |
| Glass | #22323a a=0.32 | 0.0 | 0.05 | 0.8 | TRANSPARENCY_ALPHA_DEPTH_PRE_PASS, CULL_BACK, clearcoat 0.6 / 0.03 |
| BlackTrim | #1a1b1d | 0.0 | 0.42 | 0.5 | satin |
| Chrome | #e0e0e0 | 1.0 | 0.15 | 0.5 | |
| Alloy | #b9bbbe | 0.70 | 0.42 | 0.5 | clearcoat 0.6 / 0.12 |
| RimWell | #4a4a4d | 0.70 | 0.60 | 0.5 | |
| Rubber | #242426 | 0.0 | 0.74 | 0.42 | sidewall sheen comes from the lowered roughness + specular |
| RubberCut | #0d0d0d | 0.0 | 1.0 | 0.3 | |
| SteelDisc | #8e8c89 | 0.90 | 0.55 | 0.5 | anisotropy 0.55 (follows UV tangent: needs a radial/lathe UV on the disc) |
| CaliperDark | #6a6a6c | 0.30 | 0.55 | 0.5 | |
| HeadLamp | #f4f1e6 | 0.0 | 0.08 | 0.7 | clearcoat 1.0 / 0.02; emission #fff3d8, energy day 0.2 -> night 1.4 |
| TailLamp | #b0221c | 0.0 | 0.12 | 0.7 | clearcoat 1.0 / 0.03; emission #ff1a0a, energy day 0.3 -> night 1.0 |
| Interior | #2a2a2e | 0.0 | 0.90 | 0.3 | weave normal (simplex 4 oct.) scale 0.25, uv 6 |
| Seat | #3a3632 | 0.0 | 0.93 | 0.25 | weave normal scale 0.5, uv 10 |
| ArchLiner | #141415 | 0.0 | 0.95 | 0.2 | |
| Plate | #f2f2ee | 0.10 | 0.35 | 0.6 | plate graphics are a Blender-side albedo texture (kept if the slot is not overridden) |

API: `VehicleMaterials.material(name)` (cached, strips `.001`/`_001`), `apply(node)` (sets surface override
materials by the glTF material `resource_name` on every MeshInstance3D below `node`), `set_night(amount)` (lamp
emission lerp, call from `CedarNeighborhood.set_time` next to `CityKit.set_night`), `set_wet(amount)` (rain: roughness
of paint/trim/rubber/plate/alloy/well/caliper lerps to 35 % of dry; call with `weather.wetness`). Nothing is wired yet.

## Captures (`tmp/`, 1280x720)

`materials_day.png` (15.5 h, clear), `materials_golden.png` (17.8 h), `materials_night.png` (21.5 h),
`materials_rain.png` (15.5 h, `weather.forced = 1.0`, `set_wet(1.0)`), `materials_day_close.png` (3 m, metals),
`materials_day_probe.png`, `materials_day_probe_close.png`, `materials_night_probe.png` (same views with a ReflectionProbe).

Sphere means (sRGB), day sky-only vs day with probe:

| | Paint | Chrome | Alloy | RimWell | Rubber | BlackTrim | SteelDisc | Glass |
|---|---|---|---|---|---|---|---|---|
| sky-only | 107,137,161 | 112,147,173 | 93,121,144 | 31,43,55 | 19,28,35 | 22,34,44 | 77,96,110 | 158,166,166 |
| probe | 137,151,163 | 155,168,178 | 113,130,144 | 37,45,54 | 22,28,33 | 32,39,45 | 88,100,108 | 159,166,166 |

## What each condition revealed

- **Day, sky-only (10 m).** Every bright metal is a sky-blue ball: the sky radiance is the only reflection source,
  so Paint/Chrome/Plate/HeadLamp land within ~25 values of each other and all carry a blue cast (B > R by ~55).
  Chrome vs Alloy separation is 19 values (brief asks for distinguishable: it is, barely — by the horizon line on
  chrome, not by colour). RimWell (31,43,55) vs Rubber (19,28,35) vs BlackTrim (22,34,44) now separate by 10-15 values
  after lifting the well to #4a4a4d / metallic 0.7; the initial #3a3a3c well was indistinguishable from the tyre at 10 m.
- **Day, 3 m (`materials_day_close`).** Chrome shows the sharp sky/ground horizon, Alloy a soft satin gradient with the
  clearcoat sun hot-spot, RimWell a dark metallic grey with a broad highlight, Rubber matte with a faint sheen,
  RubberCut dead black. All five read as different materials at 3 m even without a probe.
- **Golden hour.** 19.3 h as requested is already night in this world's clock (`set_time` amount = 0, sun energy 0.16
  = moonlight). Golden hour is 17.3-18.3 h; captured at 17.8 h (sun 0.49, warm #ffb877). Alloy/SteelDisc/Plate pick up
  the warm key and the metals finally separate in hue (Alloy 80,81,87 vs Chrome 58,85,109 reflecting the cool sky).
- **Night.** Metals become dark balls with street-lamp highlights; fine for gameplay. Lamp energies at the proposed
  3.0 / 2.5 clipped: HeadLamp (244,241,235) solid white with glow halo, TailLamp (255,144,110) salmon. AgX
  desaturates saturated reds at high energy, so the tail needs a deeper red and less energy: final 1.4 / 1.0 with
  #ff1a0a gives (230,224,214) and (247,86,46) — still a lit lamp, but the tail stays red. These are full-sphere
  emitters; real lens meshes are smaller and read a little dimmer, so 1.4/1.0 is the ceiling, not the floor.
- **Rain.** Sun dims to 35 %, fog rises; with `set_wet(1.0)` the paint/trim/rubber get a water-film gloss (BlackTrim
  22->43, Rubber 19->40, Paint picks up the grey sky). Without `set_wet` the materials do not respond to the weather
  at all (first rain run, wetness 0, was pixel-identical to day). Note: `weather.forced` is applied in `_process`, so
  wait two frames after setting it before reading `wetness`.
- **ReflectionProbe (UPDATE_ONCE, size 14x4x8, box projection).** Removes the blue cast (Paint B-R 54 -> 26, Chrome
  61 -> 23), raises the metals 15-40 values, and at 3 m chrome mirrors the road, kerb and houses — the single biggest
  readability gain in the study. Glass gains a visible reflection. Two gotchas measured: (1) an UPDATE_ONCE probe keeps
  its daylight capture through the night — metals glowed (145,149,151) at 21.5 h until the probe was re-triggered
  (toggle `update_mode` ALWAYS -> ONCE after `set_time`); (2) it snapshots whatever particles/fog are present, so
  trigger it after weather changes settle (150 frames in the capture).

## Probe recommendation

Parent one `ReflectionProbe` to the player vehicle: `size ≈ Vector3(6, 4, 8)`, `box_projection = true`, `interior =
false`, `update_mode = UPDATE_ONCE`, re-triggered when the car has moved > ~8 m since the last capture, or when
`set_time`/weather crosses a threshold (a 1 s timer check is enough). Cost: UPDATE_ONCE renders the 6 cubemap faces once on
trigger (one extra scene pass spread over frames by Godot; not timed in this study — measure the frame spike in the
integration capture), then free until re-triggered; UPDATE_ALWAYS re-renders every frame and is not acceptable with
this scene density. Do not use `REFLECTION_SOURCE_DISABLED`; the probe blends over the sky. Traffic
cars should stay sky-only (the metals still separate at 3 m; at 10 m+ the sky look is acceptable).

## Glass decision: CULL_BACK

Car glass is exported as single-sided shells with outward normals. `CULL_DISABLED` would draw the inner face of
every pane behind the outer one, doubling the alpha overdraw and producing sort flicker between the two faces of the
same pane (Godot sorts per mesh, not per face). With back culling the exterior shows one clean pane and the driver
camera inside the cabin looks out through culled faces — no tinted double layer in the player's view. Depth pre-pass
keeps the panel's far side from bleeding through. If a pane is modelled as a solid with thickness, both faces are
front-facing and still render correctly.

## Blender-side requirements (so names and colours line up)

1. Material names exactly as the table (case-sensitive, no `.001` suffixes; the loader strips them but the glTF
   exporter will emit `VehiclePaint.001` if two materials share a base name — merge them). One material per slot.
2. The game overrides every listed slot, so Principled values only matter for parts without an override (Plate graphics,
   any badge/decal albedo texture): set those textures as Base Color with sRGB colour space; `Plate` keeps its texture
   only if the integration passes `apply()` a skip list — otherwise bake the plate text into a separate `PlateText` slot.
3. `SteelDisc` anisotropy follows UV tangents: unwrap the disc with a lathe/radial UV (cylinder projection about the axle)
   and export tangents (glTF exporter "Tangents" on); with box-projected UVs the brushed highlight runs in one direction.
4. Paint flake and seat weave use `uv1_scale` tiling of UV0: body and seat meshes need a real, roughly uniform-density
   UV unwrap (no stacked or zero-area islands) or the flakes stretch.
5. Glass: single-sided outward normals (see above). Headlamp/taillamp: the lens mesh takes the `HeadLamp`/`TailLamp`
   slot; a separate dark housing behind it should use `BlackTrim`, not the lamp slot, or the whole housing glows at night.
6. `VehiclePaint` must also be in the paint mesh node names (`CityAssets.tint` matches node names, not material names).

## Open issues

- Flake normal at scale 60 is invisible at 3 m in the captures (reads as plain gloss); it starts to show below ~1.5 m.
  Keep or drop based on the first in-car capture; cost is one 256 px noise texture.
- `set_night` and `set_wet` are static and global: all vehicles share lamp/wetness state (same as `CityKit.set_night`).
  Per-vehicle lamps (lights off when parked) need a duplicated material per instance.
- The rain pass still shows the unlit metals as flat; a wet-paint droplet normal (shader) is out of scope for a
  StandardMaterial3D table.
- Pixel sampling in the close captures returns zeros for columns outside the frame (expected; only the metals group
  is in view).
