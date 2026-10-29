# Street hardware polish (Mert Road Studio v5)

The older street assets now match the furniture library's standard (`FURNITURE.md`): baked atlas materials,
chamfers, real thickness, and wear only on exposed edges and at ground contact. The polished assets are the six
streetlights, the six barriers, all signs and signals in `signage.py`, and the footbridge's game materials.
Object names, collections, origins, real-world sizes and every contract property are unchanged. The test checks
all of them against the base commit.

Sources:
- `tools/roads/mrs/hardware.py` (new)
- `tools/roads/mrs/assets.py`: `_streetlights` and `_barriers`, plus the `_hw_*` helpers
- `tools/roads/mrs/signage.py`

Checks:
- Blender: `tools/roads/tests/hardware_test.py`
- Godot: `tests/capture_hardware.gd`

Outputs:
- `tmp/roads/v5/hardware/`: renders, GLB, layout, comparison sheets
- `tmp/roads/materials/hardware/`: textures

## API

```python
import mrs.hardware as HW
HW.build_hardware_materials(bake="auto", tex_dir=None, verbose=True)   # -> {name: material}; called by assets.build_assets()
HW.bake_textures(tex_dir=None)           # regenerate every PNG (numpy, about 10 s)
HW.image_material(name, paths, tile_m=None, emission=0.0)  # plain Principled + albedo / ORM / normal images (+ Mapping 1/tile_m)
HW.glass_material(name="MRS_HW_Glass")   # alpha-blended glazing, no textures
HW.mat(name)                             # one of the materials above (builds on demand)
HW.HM()                                  # bmesh builder: faces carry an atlas cell name or an extra material
HW.make_object(col, name, builder, bevel)  # finish (normals, ground faces, chamfers -> edge cells, atlas UVs) + link hidden
HW.to_mesh(hm, name, bevel, atlas) / HW.finish(hm, name, bevel) / HW.atlas_uv(bm, name, faces)
HW.anchor_bolts(hm, r, n, z, size) / HW.base_door(hm, r, z0, z1, width)
HW.CELLS / HW.CID / HW.TILEABLES / HW.REPORT   # atlas layout, cell ids, tileable set, per-object stats (tris, islands, px/m)

import mrs.signage as S                  # unchanged signatures; new keyword arguments marked *
S.make_sign(name, kind, text=None, value=None, pole_height=2.3, size=None, collection=None, double=False, face_color=None, game=False*)
S.make_direction_board(name, entries, collection=None, clearance=2.5, row_height=0.42, text_size=0.24, game=False*)
S.make_signal(name, style, pole_height, arm_length, heads, setback, lens_size, housing_color, collection)
S.build_signage(game=True*, bake="auto"*, tex_dir=None*)   # library = baked game signs; bakes MRS_SignAtlas when the specs changed
S.bake_sign_atlas(specs=None, tex_dir=None, samples=16)    # authoring signs + text curves -> MRS_SignAtlas_albedo.png + sign_atlas.json
S.sign_atlas_cells() / S.sign_atlas_material() / S.sign_atlas_current()
S.bake_sign_text(obj), S.set_lens_state / set_signal_state / bake_lens_states, S.demo_collection()   # unchanged
```

`mrs.build_all()` needs no change. `assets.build_assets()` calls `hardware.build_hardware_materials()` first,
so the `MRS_HW_*` materials exist before `footbridge.build_footbridge_group()` runs. `signage.build_signage()`
bakes the sign atlas on first use, which takes about 7 s.

## Materials

| material | kind | used by |
|---|---|---|
| `MRS_HardwareAtlas` | Principled + albedo / ORM (G = roughness, B = metallic) / normal, 2048 x 1024, 256 px/m | streetlights, barriers, sign posts / clamps / blanks, signal poles |
| `MRS_SignalHousing` | same images as the atlas (keeps the signage contract name) | signal heads: housing, visors, black back plate, yellow retroreflective border, dark ped windows |
| `MRS_SignFace_Atlas` | Principled + `MRS_SignAtlas_albedo.png` (2048 x 2048), roughness 0.38 constant | printed faces of the game signs and boards |
| `MRS_HW_PaintedSteel` | tileable, 2 m / 1024 px, slate blue-grey powder coat | footbridge structure (girders, stringers, kick plate) |
| `MRS_HW_Galvanized` | tileable, 2 m / 1024 px, fine low-contrast spangle, sparse white-rust | footbridge posts, truss, bars |
| `MRS_HW_Stainless` | tileable, 1 m / 512 px, brushed along u | handrails |
| `MRS_HW_Concrete` | tileable, 2 m / 1024 px, precast, fine aggregate + pores | columns, footings, crossheads, stairs, approaches |
| `MRS_HW_DeckAntiSlip` | tileable, 2 m / 1024 px, dark resin with bauxite grit | deck / landings / ramps |
| `MRS_HW_LEDDiffuser` | tileable, 0.5 m / 256 px, opal with a 25 mm LED pitch, emission 3 (albedo-driven) | handrail LED strip |
| `MRS_HW_Glass` | plain Principled, alpha 0.18, BLENDED, backface culling | lantern panes (closed 6 mm panes) |
| `MRS_PropLamp` | unchanged shared lamp emitter (`lighting.py` / `MrsStreetLights` find it by name) | luminaire lenses, bulbs, LED dots |
| `MRS_Lens_*` | unchanged (`State` → `StateStrength` → emission) | signal lenses and ped / bike glyphs |
| `MRS_SignFace_<Colour>` | now plain colours (no noise), so the exporter passes them through | authoring signs only |

Every textured material is a plain Principled BSDF fed directly by Image Texture nodes. `export.engine_material`
returns it unchanged, and the glTF exporter writes `baseColorTexture`, `metallicRoughnessTexture` and
`normalTexture`. The test confirms that `apply_engine_materials` replaces no slot except the lamp emitter, which is
flattened by name as before.

**Tileables and metre UVs.** A Mapping node scales the UV by 1 / tile size. The glTF exporter writes it as
`KHR_texture_transform`, and Godot applies it as `uv1_scale` (measured 0.5 for the 2 m tiles and 2.0 for the LED
strip). The footbridge's UVMap, which is (lateral m, along m), therefore repeats once per tile.

**UV-less faces** (Curve to Mesh tubes, the LED ribbon, columns) have every UV at (0, 0) after the join. They
sample the texture corner. In every tileable, the wrapped corner patch (radius 7 px) is blended to the mean
albedo, the mean ORM and a flat normal. Those faces therefore read as the average material, with no random texel
and no normal-map shading from undefined tangents. The swatch test piece checks this: posts, handrails, bars, the
LED strip and the column have zero UVs, and they look uniform in both Blender and Godot.

**Footbridge switch (for the footbridge owner).** Set the defaults in `footbridge._defaults` by name:

| footbridge input | material |
|---|---|
| Deck Material | `MRS_HW_DeckAntiSlip` |
| Structure Material | `MRS_HW_PaintedSteel` |
| Concrete Material | `MRS_HW_Concrete` |
| Railing Material | `MRS_HW_Galvanized`, or `MRS_HW_Stainless` for the handrail |
| LED Material | `MRS_HW_LEDDiffuser` |

They exist after `assets.build_assets()`, or after `hardware.build_hardware_materials()`.

## Texture generation

There is no Cycles bake for the hardware textures. `hardware.py` synthesises them with numpy:
- periodic spectral noise: Gaussian-filtered white noise in the Fourier domain, with anisotropy for brushed metal
  and wood grain;
- periodic jittered-grid Worley cells: galvanising spangle, foliage leaves, deck grit;
- normals from height by wrapped central differences (OpenGL / glTF +Y).

Every pattern therefore tiles exactly, and a full regeneration takes about 10 s. Albedo is computed in linear
space and encoded to sRGB. ORM is stored linear (R = 1). `hardware_layout.json` holds the cells, the tileables and
`BAKE_VERSION`. `bake="auto"` rebakes when any of these change.

### MRS_HardwareAtlas layout (px, top-left origin, 256 px/m)

| cell | rect | mode | notes |
|---|---|---|---|
| galv | 0,0,512,256 | tile | hot-dip galvanised: 16 mm spangle at ±4 % brightness, patina patches, sparse white-rust |
| galv_contact | 512,0,512,256 | ground | galv + grime / splash / damp line fading out by 0.45 m |
| paint_dark | 1024,0,256,256 | tile (edge: paint_dark_edge) | anthracite powder coat (RAL 7016 look), faint orange peel |
| paint_dark_edge | 1280,0,256,256 | tile | worn lighter tone with sparse chips to the primer |
| paint_dark_contact | 1536,0,512,256 | ground | paint + ground grime |
| concrete | 0,256,512,256 | tile (edge: concrete_edge) | mid-grey precast, aggregate, pores, narrow tone range (no blanket blotches) |
| concrete_contact | 512,256,512,256 | ground | road grime, splash and a damp line at the base |
| concrete_edge | 1024,256,256,256 | tile | arris wear: lighter with small spalls |
| concrete_streak | 1280,256,512,256 | top | rain run-off streaks under a coping (anchored at the island top) |
| alu_cast | 1792,256,256,256 | tile (edge: alu_cast_edge) | painted die-cast aluminium (luminaire bodies) |
| stainless / alu_mill | 0 / 256,512,256,256 | tile, grain u | brushed stainless / mill-finish sign backs |
| alu_cast_edge | 512,512,256,256 | tile | worn die-cast edges |
| iron_black / iron_black_edge | 768 / 1024,512,256,256 | tile | satin black cast iron / chipped edges with rust |
| housing | 1280,512,256,256 | tile | signal housing polycarbonate |
| wood | 1536,512,512,256 | tile, grain u | weathered treated softwood, checks |
| foliage | 0,768,512,256 | tile | 20 mm leaves in clumps, soft gaps |
| wood_contact | 512,768,512,256 | ground | vertical-grain post with a soil stain |
| galv_dark | 1024,768,256,256 | tile | aged matte galvanised (clamps, guardrail bolts / spacer) |
| paint_yellow, white_refl, yellow_refl, red_refl | 1280–1535,768–1023 (128 px) | tile | push-button yellow, micro-prism retroreflective sheeting |
| rubber, black_plastic, void, glass_dark | 1536–1791,768–1023 (128 px) | tile | caps, bezels, recesses, ped windows |
| paint_grey | 1792,768,256,256 | tile | spare grey powder coat |

**UV mapping (`atlas_uv`).** Each face is projected on its dominant axis, unmirrored. Islands are edge-connected
faces with the same cell and projection.
- **Tile cells:** islands keep 256 px/m. The long side follows the grain, or the cell's long axis when there is no
  grain, with a seeded offset (8 px padding). Islands longer than the cell are cut greedily at their loops into runs
  that fit, instead of being shrunk; tall shafts carry a loop at least every 1.9 m. Every atlas face measures at
  least 150 px/m, except the 1 cm drip-groove strips under the parapet coping (void cell, 58 px/m) and a few sub-cm²
  chamfer slivers.
- **Ground cells:** v = height above the object's origin, so grime sits exactly at z = 0. Horizontal faces use the
  fallback cell.
- **Top cells:** v is anchored at the island top.
- **Edge variants:** `finish()` gives chamfer faces their largest neighbour's edge cell. Hardware neighbours are
  preferred over lens and face materials, so lens chamfers stay housing.

### MRS_SignAtlas (`bake_sign_atlas`)

The editable authoring path is the source of the game signs.
1. Each library spec is built with `make_sign(...)` / `make_direction_board(...)`: coloured face polygons, border
   bands, pictogram meshes and FONT legends.
2. The face regions that `_plate` / `_blank` register are flattened: u = the viewer's right, v = up.
3. Polygons are stacked by their depth in front of the sheet, and FONT children are evaluated to meshes.
4. The cell is filled with the colour at the plate edge (bleed), then the drawing is rendered as flat emission with
   an orthographic Cycles camera (CPU, 16 samples, Blackman–Harris 1.2 px).

Results:
- 26 signs / boards, 27 faces in 2048 x 2048;
- 424 px/m for plates ≤ 1.5 m wide, 283 px/m for boards (scale 0.88 after packing);
- a 0.1 m street name is 42 px tall.

`sign_atlas.json` stores per name the px rect, padding, px/m, (u0, u1, v0, v1), axis and plane, plus a hash of
the specs. The library rebakes when the specs, `FACE_RGB` or `SIGN_BAKE_VERSION` change.

**Game sign** (`make_sign(..., game=True)`):
- The geometry is the same hardware, but the face is one polygon in `MRS_SignFace_Atlas`.
- Borders, pictograms and text are dropped, and there are no FONT children. `mrs_sign.legends` is `[]` and
  `baked_legends` holds the text.
- Street-name blades map the back face mirrored, so they read correctly from both sides.
- A name without an atlas cell (e.g. a junction street-name sign with custom text) falls back to the authoring
  version. Those legends are real FONT geometry with plain face colours, so they export crisp too.

## Per-asset changes

**Streetlights.** Galvanised or painted metal. Every column has:
- a round flange plate (n = 16, which keeps the library extents);
- 4 anchor bolts with washers and nuts;
- a weld collar;
- a ground-contact base section;
- a tapered shaft with loops every 1.9 m;
- a raised service door with a lock on the -Y side.

Per object:
- **Highway / Double:** bracket sleeve over the column top with grub screws, and tapered swept arms (single or
  twin). The new luminaire is a lofted die-cast body: canopy peak at 10.05 m, gear compartment, cooling fins, flat
  optical bay, black bezel, a lens of `MRS_PropLamp` with its underside at 9.82 m, a spigot sleeve and a latch.
- **LED:** anthracite column with a swept post-top bracket. The slim LED head is no longer the 6 cm slab: it has a
  lofted body, 7 heat-sink fins, a black LED board and a 4 x 12 array of lens dots (`MRS_PropLamp` quads) facing
  down.
- **Lantern:**
  - satin cast-iron column with a moulded base, a fluted lower shaft, collars and a ladder bar;
  - square flared lantern: tray, corner posts, top frame, reflector plate, eaves, a pyramid roof with a vent crown
    and a finial;
  - 4 closed 6 mm panes of `MRS_HW_Glass`, which stay transparent in Godot (alphaMode BLEND,
    transparency = alpha);
  - pear bulb (24 segments) on a holder, visible through the glass.
- **Bollard:** contact-cell body (14-gon, extents kept), opal core of `MRS_PropLamp` between 7 louvre bars, domed
  cap.
- **WallPack:** square base plate with bolts and a contact section, painted post with a pyramid cap, mounting
  plate, die-cast body with a sloped lid and side fins, and a bezel round a recessed lens.

The fixture anchors (`mrs_fixtures`) are byte-identical. The test re-runs the lighting checks:
- emitters within 0.35 m;
- anchor-to-emitter distance under 10 cm;
- aim at tilt 0° and 10° clear of the mesh;
- housing above the down-lights.

**Barriers.** Each segment is still 2 m along Y, so instanced runs join.
- **Guardrail:** smooth W-beam profile in 3 mm steel, an overlapping splice layer at the far end with 8 button-head
  bolts, a post bolt with a slotted washer, a sigma post open at the back (ground cell), a C-channel blockout and a
  delineator with retroreflective sheeting.
- **Jersey:** New Jersey profile with chamfers, a drainage scupper (a real through-slot), recessed lifting anchors
  with steel loops and end connector plates. Contact grime on the faces, edge wear on the chamfers.
- **Parapet:** wall cut at 0.5 m. Below the cut is the contact cell; above it are run-off streaks under the coping.
  The coping is ±0.32 wide (the old odd strip was dropped) with drip grooves.
- **Railing:** 70 mm SHS post with a base plate and 4 bolts, a cap and a handrail saddle. The open-ended rails
  (r 23.8 / 12 mm) join neighbours, with 14 balusters at a 125 mm pitch.
- **Fence:** post with a cap plate and a pyramid (wood_contact below 0.95 m), two mortised rails and 12 gothic
  pickets 19 mm thick.
- **Hedge:** clipped rounded-box hedge with noise lumps and a narrower base. The ends are open-rounded so segments
  merge (it overlaps by 2.8 cm each side). The foliage atlas cell replaces the ellipsoid blob.

**Signs** (library = game versions; authoring = `make_sign` default):
- galvanised Ø 70 mm post with a ground-contact base and a black plastic cap; the post ends where the plate is
  still at least 14 cm wide, so no cap pokes above a triangle apex;
- 1 or 2 band clamps with brackets;
- channel rails across the back of plates wider than 0.62 m, clipped to the outline's chord;
- 3 mm aluminium blank with a 18 mm rolled-rim lip (mill-finish back);
- face 1 cm further forward (y = 0.055) to leave room for the clamps;
- discs use a 24-gon blank, while the texture keeps the round edge;
- street-name blades: rounded corners, double-sided (6 mm), clamped to the post;
- direction board: two posts with base plates and bolts, U-bolt clamps and rails.

**Signals:**
- pole: base plate (r0 x 3, extents kept) with 4 anchor bolts, a flared ground-contact base, a 16-gon shaft with
  loops and a cap;
- mast arm: bolted flange plate, tapered arm, brace, and hanger clamps around the arm;
- side mounts: galvanised clamp rings;
- push-button unit: yellow box with a stainless button and a tactile plate;
- heads: housing with door hinges and a drain boss, a black back plate with a yellow retroreflective border,
  visors with black insides, and 20-segment lens discs.

The lens / State wiring, `mrs_signal`, `mrs_signal_head`, head child names and mesh names are unchanged.

## Triangles and materials (`tmp/roads/v5/hardware/tris.json`)

"Materials" counts material slots, i.e. draw calls per object. The old signs carried 12 slots, of which 3–6 were
used.

| asset | tris before | tris after | materials |
|---|---|---|---|
| MRS_Light_Highway | 916 | 2,150 | 2 → 2 |
| MRS_Light_Double | 1,358 | 3,094 | 2 → 2 |
| MRS_Light_LED | 568 | 1,902 | 2 → 2 |
| MRS_Light_Lantern | 1,124 | 2,894 | 3 → 3 |
| MRS_Light_Bollard | 410 | 454 | 2 → 2 |
| MRS_Light_WallPack | 154 | 832 | 2 → 2 |
| **lights total** | **4,530** | **11,326** | |
| MRS_Guardrail | 404 | 1,098 | 3 → 1 |
| MRS_Jersey | 224 | 416 | 2 → 1 |
| MRS_Parapet | 206 | 146 | 1 → 1 |
| MRS_Railing | 432 | 816 | 1 → 1 |
| MRS_Fence | 862 | 778 | 1 → 1 |
| MRS_Hedge | 1,280 | 1,628 | 1 → 1 |
| **barriers total** | **3,408** | **4,882** | |
| signs, discs (Speed50, NoEntry, NoLeft/RightTurn, Straight/TurnLeft/TurnRightOnly, BicycleRoute, NoParking, Roundabout, SpeedZoneEnd) | 552–880 | 474 | 12 → 2 |
| Stop / Yield / Children / Roadworks / GiveWayAhead | 105–508 | 264–314 | 12 → 2 |
| Parking / PedestrianCrossing / DeadEnd / PriorityRoad | 132–240 | 274 | 12 → 2 |
| BusStop / OneWay / StreetName / StreetNameDouble / Sign_DirectionBoard | 444–2,032 | 214–366 | 12 → 2 |
| **signs total (25)** | **14,564** | **8,990** | |
| MRS_DirectionBoard | 2,126 | 2,724 | 12 → 2 |
| MRS_Signal_Post / Combined / MastArm / Pedestrian / Bicycle | 3,022 / 4,810 / 5,642 / 2,238 / 5,086 | 2,782 / 4,032 / 4,776 / 2,138 / 3,786 | 7–9 → 4–7 |
| **signals total** | **20,798** | **17,514** | |

The streetlights are the only family that grew a lot: 2.5x, about 2–3 k triangles per column. This is the cost of
real luminaire heads, bolts and doors, and it buys no extra draw calls. The sign hardware has no chamfer pass, the
signal lenses have 20 segments instead of 24, and the signs and boards dropped from up to 12 material slots to 2.

## Verification

```
blender --background --factory-startup --python tools/roads/tests/hardware_test.py -- --baseline   # before (base commit fe2bd6a)
blender --background --factory-startup --python tools/roads/tests/hardware_test.py                 # after + GLB + layout
Godot_v4.7.2-stable_win64_console.exe --path . --script res://tests/capture_hardware.gd -- <abs>/tmp/roads/v5/hardware/hardware.glb <abs>/tmp/roads/v5/hardware/godot
blender --background --factory-startup --python tools/roads/tests/hardware_test.py -- --compose    # before | after | Godot sheets
```

`hardware_test.py` builds:
- `materials.build_materials()` / `extra_materials()`;
- `props.build_prop_collections()`;
- `assets.build_assets()`;
- `signage.build_signage()`;
- `hardware.build_hardware_materials()`.

It checks against `baseline.json`, which the base commit's `assets.py` / `signage.py` produce through `git show`
in a temporary copy of the package:
- library names, collections, children and origins;
- dimensions: 2 mm for lights and barriers; signs 1 cm wide / tall and 3 cm deep; signals 1 cm;
- min z = 0;
- `mrs_fixtures` (object and mesh);
- `mrs_signal` (style / heights / setback / lens size / housing / heads) and `mrs_signal_head`;
- `mrs_sign` (kind / text / value / size / pole height / double / faces), with legends preserved as
  `legends + baked_legends`;
- the lens / lamp materials;
- UVs, no loose verts, no zero-area faces, 50–3000 verts (the `assets_test` range);
- pass-through by `export.engine_material`;
- the lighting fixture rules;
- the GLB: baseColor / metallicRoughness / normal textures on every hardware material (albedo only on the sign
  atlas), `KHR_texture_transform` on the 2 m tiles, and `alphaMode BLEND` on the glass.

**Result:** `HARDWARE OK`. The existing suites also pass against the new modules:
- `signage_test.py` (full, with renders and the lens lit-pixel check): `SIGNAGE OK`;
- `assets_test.py -- --quick`: `PASS`;
- `lighting_test.py -- --no-render` (full `build_all`, the streetlight dimension / anchor / aim checks):
  `LIGHTING TEST PASS`.

Godot 4.7.2 (`capture_hardware.gd`) loads the 50 library and swatch nodes:
- every atlas and tileable material has albedo, normal, roughness and metallic textures;
- the sign atlas has albedo;
- `uv1_scale` is 0.5 on the 2 m tiles and 2.0 on the LED strip;
- `MRS_HW_Glass` is alpha-transparent (0.18);
- the extras arrive (`mrs_fixtures`, `mrs_sign`, `mrs_signal`);
- the night scene has 7 `MrsStreetLights` lights (4 shadowed) and the lamp material lit.

### Comparison images (before | after | Godot)
- `tmp/roads/v5/hardware/compare_lights.jpg`: lights row, Highway head, LED head, lantern glass, pole bases,
  bollard + wall pack, night
- `tmp/roads/v5/hardware/compare_signs.jpg`: sign row, sign faces, sign backs (clamps / rails / rim), direction
  board, signals row, vehicle head, ped head
- `tmp/roads/v5/hardware/compare_barriers.jpg`: barrier row, guardrail splice / post, jersey + parapet, railing +
  fence + hedge
- `tmp/roads/v5/hardware/compare_footbridge_materials.jpg`: footbridge-like test piece (FB_Steel / PropConcrete /
  PropSteel / Paving before, `MRS_HW_*` after)
- `tmp/roads/v5/hardware/catalogue_{lights,barriers,signs,signals,boards}.jpg`: per object, before | after
- Individual renders: `before/`, `after/`, `godot/` (`godot_<scene>.png`)
- `layout.json`: the scenes and cameras shared with Godot
- `tris.json`, `baseline.json`
- `hardware.glb` (about 21 MB, textures embedded)

## Known issues
- **Triangle budget:** streetlights are about 2.5x heavier than before (the Double has 3.1 k triangles). There are
  no LODs yet; a LOD1 without bolts, door and fins would roughly halve them.
- **Lamp material:** `MRS_PropLamp` is still the shared procedural lamp material (contract). The exporter flattens
  it to `MRS_PropLamp_Engine` with its emission, as before, so all luminaires glow alike.
- **Footbridge slab sides:** the footbridge's UVMap gives slab and beam side faces a constant u (lateral). Any
  texture is sampled along one column there and shows faint streaks along the deck edge. The low-contrast
  tileables keep this subtle. A (along, z) mapping for the side faces would remove it; that is footbridge-side
  work.
- **Junction street names:** signs with custom text (junction street names) stay authoring signs, with FONT
  legends and plain colours, unless their text is baked into a sign atlas. `bake_sign_atlas(specs)` accepts any
  specs, but the library bakes only its own.
- **Old MRS_Signs signs:** `MRS_Sign_Speed30/70/90`, `Taxi`, `CurveLeft/Right` and `StreetName_A/B`
  (`assets._signs`, MRS_Signs collection) are not part of this pass. Placement still uses Speed30/70/90 when a
  road has that limit; adding them to `signage._sign_specs` would move them to MRS_Signage.
- **Texture import:** textures are 8-bit PNGs. In the project, import them with VRAM compression and mark the
  normal maps as normal maps (see the lossless-texture note in `FURNITURE.md`).
- **Glass sorting:** the lantern glass is one alpha-blended surface. Godot sorts per object, so the four panes can
  sort imperfectly against each other. At alpha 0.18 with an identical tint this is not visible in the captures.
