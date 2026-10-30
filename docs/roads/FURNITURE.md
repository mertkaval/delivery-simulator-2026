# Sidewalk furniture library (Mert Road Studio)

Source: `tools/roads/mrs/furniture.py`. Test: `tools/roads/tests/furniture_test.py`. Godot check:
`tests/capture_mrs_furniture.gd`. Outputs: `tmp/roads/v4/furniture/` (GLB, renders, layout) and
`tmp/roads/materials/furniture/` (atlas PNGs).

```python
import mrs.furniture as F
col = F.build_furniture(bake="auto", tex_dir=None, samples=16, verbose=True)   # -> bpy collection MRS_Furniture
F.export_library_glb(path, names=None)    # every object a named node at the origin, materials + textures, extras on
F.bake_atlas(tex_dir=None, samples=16)    # rebake the atlas only
F.atlas_materials(tex_dir=None)           # (MRS_FurnitureAtlas, MRS_FurnitureGlass)
F.REPORT                                  # per-object stats of the last build (tris, UV islands, px/m, warnings)
F.SPECS / F.NAMES / F.FLUSH / F.CELLS     # object specs, names, flush items, atlas cells
```

`build_furniture` (re)creates collection **MRS_Furniture**. Like the other `MRS_*` library collections
(`props.collection`), the collection is linked under the active scene and hidden from render. Its objects
sit at the origin with `hide_viewport` / `hide_render` set. Rebuilding replaces the objects and does not
accumulate them. `bake="auto"` rebakes the atlas only when the PNGs or `atlas_layout.json` are missing or
come from an older `BAKE_VERSION`. `True` always rebakes and `False` never does. A build without a bake takes
about 0.3 s, and a bake takes about 15 s on the CPU. The module has no side effects on import.
`mrs.assets.build_assets()` is not required. The test calls it to check that the two coexist.

## Conventions
- Metres, Z up. The origin is the **ground centre of the footprint**: the XY bounding-box centre, with
  min z = 0. Faces lying on the ground (z = 0, facing down) are removed.
- Local **X runs along the kerb**. **+Y is the front**; `left` = -X side and `right` = +X side.
  `mrs_facing` says what the front should face.
  - `walk`: toward the walking corridor (bench seat, bin aperture, cabinet doors).
  - `carriageway`: toward the road.
    - Bus shelter: back wall at -Y, open boarding side +Y.
    - Bus pole: the flag projects +Y over the kerb, and the timetable faces -Y toward the footway.
    - Hydrant: the pumper outlet points +Y.
    - Drain grate: the -Y edge lies on the kerb face.
  - `any`: symmetric or usable from both sides.
- Glass is a second material, `MRS_FurnitureGlass` (alpha blend). Everything else uses `MRS_FurnitureAtlas`.
  No object has more than 2 materials.

## Custom-property contract (glTF extras on every node)
| property | type | meaning |
|---|---|---|
| `mrs_kind` | str | `bench, bin, bike_rack, bus_shelter, bus_pole, info_board, bollard, barrier, planter, tree_pit, tree_guard, utility, hydrant, drain, access_cover` |
| `mrs_footprint` | JSON str `"[w, d]"` | physical footprint in metres along local X and Y, i.e. the XY bounds of the mesh including overhangs (test: within 10 % of the mesh bounds) |
| `mrs_access` | JSON str `{"front","back","left","right"}` | clear space in metres that must stay free around the footprint for use or maintenance. **Rule:** the access envelope (footprint grown by these distances in the object's frame) must not contain another object's footprint, a wall or the carriageway. It may overlap other access envelopes and the walking corridor. |
| `mrs_zone` | str | preferred sidewalk zone: `furniture` (between the walking corridor and the kerb), `curb` (kerb edge), `frontage` (building side), `flush` (anywhere, walkable), `gutter` (in the carriageway gutter against the kerb) |
| `mrs_walkable` | bool | true for walkable flush grates and covers |
| `mrs_height` | float | max z in metres |
| `mrs_facing` | str (optional extra) | `walk`, `carriageway` or `any`; see Conventions |
| `mrs_base_footprint` | JSON str `"[xmin, ymin, xmax, ymax]"` (extra) | XY bounds of the geometry below 2.0 m, the part that blocks walking. Shelter roof and pole flag overhang it. |
| `mrs_pitch` | float (extra) | centre spacing for repeated rows: bollards 1.5 (gap 1.28 to 1.33 m keeps the 1.2 m access), bike hoops 1.0, guard rail 2.0 (the posts at the section ends overlap exactly) |
| `mrs_anchor` | JSON str `"[x, y]"` (extra) | bus pole: where the pole stands, relative to the origin |
| `mrs_lod1` / `mrs_lod`, `mrs_lod_of` | str / int, str (extra) | shelter LOD link |

**Bike racks:** each Sheffield hoop lies in its local YZ plane. Bikes lean on both sides (±X) with their
1.8 m length **parallel to Y**. `front/back = 1.0` covers the bike overhang beyond the 0.75 m hoop (0.53 m
each end) plus room to wheel the bike in. `left/right = 0.45` covers the parked bike's width. With X along
the kerb, bikes stand perpendicular to the kerb. To park them parallel in a narrow footway, rotate the rack
90°: the envelope rotates with it.

## Assets (measured by `furniture_test.py`)
| name | kind | zone | facing | footprint w x d (m) | height (m) | access f/b/l/r (m) | tris | materials | px/m (min) |
|---|---|---|---|---|---|---|---|---|---|
| MRS_F_Bench | bench | furniture | walk | 1.80 x 0.51 | 0.86 | 0.9 / 0.2 / 0.6 / 0.6 | 980 | atlas | 256 |
| MRS_F_BenchBackless | bench | furniture | any | 1.80 x 0.43 | 0.445 | 0.9 / 0.9 / 0.3 / 0.3 | 368 | atlas | 256 |
| MRS_F_BinWaste | bin | furniture | walk | 0.55 x 0.45 | 0.99 | 0.6 / 0 / 0.2 / 0.2 | 346 | atlas | 256 |
| MRS_F_BinRecycling | bin | furniture | walk | 0.96 x 0.46 | 0.97 | 0.6 / 0 / 0.2 / 0.2 | 1150 | atlas | 250 |
| MRS_F_BikeRackHoop | bike_rack | furniture | any | 0.12 x 0.87 | 0.775 | 1.0 / 1.0 / 0.45 / 0.45 | 528 | atlas | 256 |
| MRS_F_BikeRackRow | bike_rack | furniture | any | 2.12 x 0.87 | 0.775 | 1.0 / 1.0 / 0.45 / 0.45 | 1584 | atlas | 256 |
| MRS_F_BusShelter | bus_shelter | furniture | carriageway | 4.40 x 1.85 | 2.60 | 1.5 / 0.3 / 0.6 / 0.6 | 1172 | atlas + glass | 55 (roof) |
| MRS_F_BusShelter_LOD1 | bus_shelter | furniture | carriageway | 4.40 x 1.85 | 2.60 | same | 156 (13 %) | atlas + glass | 51 |
| MRS_F_BusStopPole | bus_pole | curb | carriageway | 0.44 x 0.60 | 3.00 | 0.5 / 0.9 / 0.3 / 0.3 | 646 | atlas | 81 (pole) |
| MRS_F_InfoBoard | info_board | furniture | any | 0.74 x 0.20 | 2.28 | 1.0 / 1.0 / 0.3 / 0.3 | 166 | atlas | 110 |
| MRS_F_Bollard | bollard | curb | any | 0.22 x 0.22 | 1.00 | 0.3 / 0.3 / 1.2 / 1.2 | 434 | atlas | 244 |
| MRS_F_BollardRemovable | bollard | curb | carriageway | 0.24 x 0.24 | 1.00 | 0.3 / 0.3 / 1.2 / 1.2 | 1128 | atlas | 256 |
| MRS_F_PedBarrier | barrier | curb | carriageway | 2.07 x 0.07 | 1.075 | 0.45 / 0 / 0 / 0 | 576 | atlas | 120 |
| MRS_F_Planter | planter | furniture | any | 1.24 x 1.24 | 1.06 | 0.3 all | 360 | atlas | 197 |
| MRS_F_TreePitGrate | tree_pit | furniture | any | 1.20 x 1.20 | 0.006 | 0 all | 310 | atlas | 200 |
| MRS_F_TreePitOpen | tree_pit | furniture | any | 2.00 x 1.20 | 0.008 | 0 all | 772 | atlas | 205 |
| MRS_F_UtilityCabinet | utility | frontage | walk | 1.06 x 0.46 | 1.34 | 0.9 / 0 / 0.3 / 0.3 | 738 | atlas | 199 |
| MRS_F_Hydrant | hydrant | curb | carriageway | 0.46 x 0.38 | 0.88 | 0.9 all | 1394 | atlas | 256 |
| MRS_F_DrainGrate | drain | gutter | carriageway | 0.50 x 0.35 | 0.006 | 0.3 all | 134 | atlas | 256 |
| MRS_F_AccessCover | access_cover | flush | any | 0.68 x 0.68 | 0.006 | 0.3 all | 64 | atlas | 182 |

Total LOD0: 12,850 triangles. Only the tree grate, drain grate and access cover are walkable.

What each object is:
- **Bench:** anthracite steel end frames with a reclined back, armrests and rubber feet, plus a middle
  frame. Five hardwood seat slats and three back slats.
- **Backless bench:** two concrete plinths with steel cleats and five recycled-plastic slats.
- **Waste bin:** recessed plinth, aperture hood with a dark opening, service door with a lock, LITTER label.
- **Recycling bin:** three compartments with green, blue and yellow lids and bezels. Round, slot and square
  apertures, recycling labels, doors.
- **Bike racks:** galvanised Sheffield hoops, Ø 51 mm, 0.75 m wide, with a cane-detection tapping rail and
  base flanges. The row has three hoops at a 1.0 m pitch.
- **Bus shelter:** silver posts, cantilever beams, a roof falling to the back and a fascia. Three back glass
  panes and a left glass end screen, all with a manifestation band. A double-sided advertising case at the
  right end, a stainless seat, a timetable case and a real-time display. LOD1 keeps posts, glass, case,
  poster, roof, fascia, seat and timetable.
- **Bus stop pole:** Ø 76 mm pole, two-sided flag with route plates, timetable case on the footway side.
- **Info board:** totem with a walking map on both faces and an "i" panel.
- **Bollard:** fixed Ø 168 mm black bollard with a reflective band and a cast collar.
- **Removable bollard:** stainless Ø 114 mm bollard with yellow bands, a socket plate with a padlock lug and a
  lifting handle.
- **Guard rail:** galvanised posts, top and bottom rails, 17 infill rods.
- **Planter:** tapered concrete planter with a lip, a mulch top and foliage.
- **Tree grate:** galvanised angle frame and a two-half cast grate with radial slots around a Ø 0.44 m trunk
  hole filled with mulch.
- **Open tree pit:** 30 granite setts with 8 mm joints around a mulch bed that is mounded slightly but stays
  below 9 mm.
- **Utility cabinet:** light-grey cabinet on a concrete plinth with two door leaves and a dark seam, handles,
  locks, hinges, side louvres, a hazard sticker and an ID plate.
- **Hydrant:** red pillar on a bolted flange, two side outlets and a pumper outlet with iron caps, and an
  operating nut.
- **Drain grate:** gully frame with nine bars across the flow direction, a cross rib and a dark void.
- **Access cover:** galvanised frame, chequer-plate cover, perimeter gap and lifting keyholes.

**Flush items** (tree grate, open tree pit, drain grate, access cover) keep all geometry between z = 0 and
0.01. The walkable tops sit at 0.005 to 0.006, and the slots, gaps and keyholes are near-black "void"
faces at z = 0.0015 to 0.002, which reads as depth. Place them on top of the finished surface: anything
below z = 0 would be hidden by the paving.

## Shared atlas
Atlas files are written to `tmp/roads/materials/furniture/`, each 2048 x 1024:
- `MRS_FurnitureAtlas_albedo.png` (sRGB)
- `MRS_FurnitureAtlas_orm.png` (linear: R = 1, G = roughness, B = metallic)
- `MRS_FurnitureAtlas_normal.png` (tangent space, OpenGL / glTF +Y)
- `atlas_layout.json` (cells in px and UV, kind, grain, physical size, bake version)

A labelled preview is at `tmp/roads/v4/furniture/atlas_labelled.png`.

There are two kinds of cell:
- **Tiling cells** have a density of 256 px per metre. Their physical size is the pixel size / 256.
- **Decal cells** are fitted to a panel whose aspect ratio matches the cell.

| cell | px rect (x, y, w, h; top-left origin) | kind | size / panel | used for |
|---|---|---|---|---|
| wood | 0,0,512,256 | tile, grain u | 2 x 1 m | hardwood slats (oiled iroko look, ~12 mm grain) |
| steel_dark | 512,0,256,256 | tile | 1 x 1 m | anthracite powder-coated steel (RAL 7016 look) |
| galv | 768,0,256,256 | tile | 1 x 1 m | hot-dip galvanised spangle, white-rust specks (metallic) |
| stainless | 1024,0,256,256 | tile, grain u | 1 x 1 m | brushed stainless (metallic) |
| iron | 1280,0,256,256 | tile | 1 x 1 m | cast iron with rust (partly metallic) |
| black | 1536,0,256,256 | tile | 1 x 1 m | black powder coat |
| alu | 1792,0,256,256 | tile, grain u | 1 x 1 m | anodised aluminium (shelter, totem cap) |
| concrete | 0,256,512,256 | tile | 2 x 1 m | fine-aggregate precast concrete with pores |
| green / blue / yellow | 512 / 768 / 1024,256,256,256 | tile | 1 x 1 m | recycling powder coats |
| red | 1280,256,256,256 | tile | 1 x 1 m | hydrant paint with chips |
| grey_light | 1536,256,256,256 | tile, grain v | 1 x 1 m | light-grey cabinet paint with vertical grime streaks |
| granite | 1792,256,256,256 | tile | 1 x 1 m | speckled grey granite |
| soil | 0,512,256,384 | tile | 1 x 1.5 m | bark-chip mulch over soil |
| rubber | 0,896,256,128 | tile | 1 x 0.5 m | rubber / black plastic |
| map | 256,512,256,512 | decal | 0.6 x 1.2 m panel | walking map ("Harbour Quarter", Port Halden) |
| poster | 512,512,256,384 | decal | 1.2 x 1.8 m (6-sheet) | fictional harbour-festival poster |
| white | 512,896,256,128 | tile | 1 x 0.5 m | white paint, reflective bands, manifestation |
| timetable | 768,512,256,384 | decal | 0.4 x 0.6 m | readable timetable (3 columns) |
| display | 768,896,256,128 | decal | 0.5 x 0.25 m | amber real-time departures |
| flag | 1024,512,256,384 | decal | 0.4 x 0.6 m | bus-stop flag, routes 12 / 47 / N8 |
| void | 1024,896,256,128 | tile | 1 x 0.5 m | near-black cavities |
| grate_tree | 1280,512,256,256 | decal | 1.116 m square | radial tree-grate slots (with height) |
| label_recycle / label_hazard / label_info / label_litter | 1280 / 1408,768 / 896,128,128 | decal | 1:1 stickers | recycling, voltage hazard, "i", LITTER |
| iron_tread | 1536,512,256,256 | tile | 1 x 1 m | cast-iron diamond chequer (32 mm pitch) |
| foliage | 1536,768,256,256 | tile | 1 x 1 m | leaf clusters |
| plastic | 1792,512,256,512 | tile, grain v | 1 x 2 m | recycled-plastic lumber |

All artwork is generated: no external images, and the place names and URLs (`porthalden.example`) are
fictional.

### Bake procedure (`bake_atlas`, headless)
1. Create a temporary scene `MRS_FurnitureBake`. Each cell becomes a quad at 256 px per unit, laid out at
   its atlas position, so Object coordinates are metres for tiling cells and UV is 0 to 1 for decals. Quads
   on the atlas border extend 4 px beyond it so the box filter does not darken the border.
2. Give each quad a procedural node material (noise, Voronoi, wave and brick textures, math) built by the
   `_G` helper. It produces albedo, roughness, metallic and height in metres. Decal cells also get flat
   emission text objects (Blender's built-in font) and polygons floating above the quad.
3. Capture the atlas with an orthographic Cycles camera on the CPU: 2048 x 1024, 16 samples, box filter of
   1 px, 0 bounces, emission only, saved as 32-bit EXR. Do it three times, relinking each Emission input to
   albedo, then `(1, roughness, metallic)`, then height + 0.02 (kept positive for emission).
4. Process the EXRs with numpy:
   - albedo: encode linear to sRGB and save as PNG;
   - ORM: save as linear PNG;
   - normal: 3 x 3 blur, then per-cell central differences of height at 1/256 m per px, giving
     `n = normalize(-dh/du, -dh/dv, 1)`, encoded to PNG.
   Per-cell processing means no gradients cross cell borders. Delete the EXRs and the scene.

`MRS_FurnitureAtlas` is a plain Principled BSDF with three image textures:
- the albedo image feeds Base Color;
- the ORM image goes through Separate Color: G to Roughness, B to Metallic;
- the normal image goes through a Normal Map node to Normal.

The glTF exporter therefore writes `baseColorTexture`, `metallicRoughnessTexture` and `normalTexture`.
Godot's GLTFDocument maps those to albedo, roughness (channel G), metallic (channel B) and the normal
map. This fixes the flat-colour exports that baking only the procedural props' diffuse colour produced.

### UV mapping (`_atlas_uv`)
The atlas cell is carried in `material_index` while building, then stored as the face attribute
`mrs_cell`. Each face is projected on its dominant axis, oriented so the viewer reads it unmirrored (u to
the viewer's right, v up; top faces use u = +X, v = +Y). UV islands are edge-connected faces with the same
cell and projection.
- **Tiling cells:** islands keep real scale (256 px/m). The long side follows the grain (`u` or `v`), or
  the island is rotated when that fits better. A seeded offset (crc32 of name and island) varies the
  pattern per slat and per face, inside an 8 px padding. Islands larger than the cell shrink uniformly,
  never stretched. Only the shelter roof, posts and rails (55 to 100 px/m), the pole and the totem body
  shrink. Everything else stays at about 200 to 256 px/m.
- **Decal cells:** the island fills the cell with 1.5 px padding. The panel aspect ratios match the cells,
  and the test warns above 6 % mismatch.
- **Chamfers:** `assets._finish` bevels with 1 segment; nobevel is set for tubes, thin plates and flush
  items. Bevel faces get material 0, so cells are shifted by +1 before the bevel and the new faces take the
  cell of their largest neighbour.

## Validation
`blender --background --factory-startup --python tools/roads/tests/furniture_test.py [-- --rebake] [--no-render]`
checks:
- names and the property contract (types, enums, JSON);
- footprint vs mesh bounds (10 %), origin at the XY centre with min z = 0, and `mrs_height`;
- flush max z ≤ 0.01, walkable tops between 0.003 and 0.006;
- outward normals: the signed volume about the origin is positive for every shell, no open edges above the
  ground, no non-manifold edges;
- materials (atlas + optional glass), every UV inside its face's cell, the LOD1 budget (≤ 35 %), image-only
  atlas nodes;
- the GLB: 20 named nodes at the origin with extras, 2 materials, 3 images, BLEND glass.

The test writes `tmp/roads/v4/furniture/`:
- `furniture.glb` (4.6 MB, textures embedded)
- `catalogue.png` (contact sheet of 20 per-object renders, via `tools/roads/sheet.py` with the system Python)
- `overview.png`, `closeup_bench_bin_rack.png`, `closeup_shelter_pole_board.png`, `closeup_detail.png`,
  `closeup_flush.png`
- `layout.json`, which holds the same scenes for Godot
- `atlas_labelled.png`

Godot (not headless):
`Godot_v4.7.2-stable_win64_console.exe --path . --script res://tests/capture_mrs_furniture.gd -- <glb> <outdir>`.
It loads the GLB at runtime and prints per-node triangles, sizes, materials and extras. It confirms that
every atlas surface has albedo, normal, roughness and metallic textures, then rebuilds the same scenes on
the same paving tiles and sun direction (AgX in both renderers) and writes `godot_*.png`. Verified: the
triangle counts and sizes match Blender, all 20 nodes carry the extras, and the textures match the
Blender renders (wood grain, printed map and timetable, labels, grates, mulch, metals).

## Known limitations
- Some faces are larger than their 1 m cell and are shrunk: the shelter roof is the extreme case at 55
  px/m. This is fine for the noisy metal cells, but a bigger "large panel" cell would sharpen them.
- Glass is alpha-blended in one mesh with the frame. Godot sorts per object, so overlapping panes can sort
  imperfectly, and the panes cast full shadows in Godot.
- Flush items are overlays and do not cut the paving. The recessed look comes from void faces and the
  normal map.
- Placement rules are not changed here: `placement.py` is being rewritten separately and should read the
  properties above. Collision shapes are not generated; use the footprint and `mrs_height`, or the mesh.
- Atlas textures are 8-bit PNGs. When importing into the project (not at runtime), set the import to VRAM
  compression and mark the normal map as a normal map (see the project's lossless-texture note).
