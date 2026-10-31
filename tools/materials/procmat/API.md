# procmat API (core)

Procedural material library for Blender 5.2 (headless-safe), separate from the road tool (decision D1) but built on
its material contract, so Mert Road Studio roads, sidewalks and furniture can use every material. Python package:
`tools/materials/procmat` (put `tools/materials` on `sys.path`). Everything runs inside Blender except
`imaging.py`, which also runs in the system Python. Nothing here touches the game (D10).

| module | what it is for |
|---|---|
| `core` | node-tree builder, contract groups (`new_group`) and materials (`contract_material`), the `Coordinates` every texture samples |
| `rig` | headless preview scene `PM_Rig`: engine, bundled-HDRI world, preset objects, camera presets, `render`, `preview`, `side_by_side` |
| `bake` | seamless PNG tiles of any contract material, `seam_metric`, the direct `periodicity` test, `tile_preview` |
| `graphdump` | Markdown node documentation (interface, node inventory, connections) for the NODES.md files |
| `road_adapter` | material inputs of the road tool's `MRS_Road` modifier, `assign` / `assign_roads` / `reapply`, furniture glass slots |
| `imaging` | PNG load / save / stats / tiling, `side_by_side` (Pillow, through the system Python inside Blender) |
| `__init__` | the registry `MATERIALS`, `register`, `discover`, `build`, `build_all` |

## The contract

A material `PM_<Name>` holds exactly ONE shader group node, named `MRS`, whose label is the group's name
(`PM_<Name>`); its `BSDF` output feeds Material Output > Surface. The group has the inputs `Use UV` (0 = object space
in metres from the Object texture coordinates; 1 = the `UVMap` attribute x `Tile Size`, with every 4D Noise / Voronoi
sampled on a flat 4D torus, so the result repeats exactly every Tile Size and bakes to seamless tiles) and `Tile Size`
(metres covered by UV 0..1), plus the material's own inputs (one size control in metres, D4), and the outputs `BSDF`
and `Albedo` (+ `Metallic`, `Height`, `Displacement`, `Alpha` when the material has them). Only when a material asks
for displacement does its `Displacement` (vector) or `Height` (float, through a Displacement node) output feed
Material Output > Displacement. These are the same names the road tool's `bake_tiles()` and
`apply_material_preset()` look for (`tools/roads/mrs/materials.py`), and any material plugs into the road's material
sockets.

## A material module (procmat/example.py)

```python
import sys
from . import core, register
KEY = "example"                                     # LIBRARY = False keeps a module out of "build all"

def build():
    G = core.new_group("Example", inputs=[("Size", "FLOAT", 0.3, 0.01, 10.0, "Stone size (m)"),
                                          ("Color", "COLOR", (0.4, 0.38, 0.35, 1.0), None, None, "Stone colour")])
    C = G.coords
    with G.frame("Stones"):
        v = C.voronoi4(G.div(1.0, G.I("Size")), at=C.warp(C.noise4(2.0).outputs["Color"], 0.1))
        col = G.vmath("SCALE", G.I("Color"), scale=G.map_range(v.outputs["Distance"], 0.0, 1.0, 1.2, 0.6))
        bsdf = G.principled(Base_Color=col, Roughness=0.8, Normal=G.bump(v.outputs["Distance"], 0.3, 0.01))
    G.out("BSDF", bsdf); G.out("Albedo", col)
    return [core.contract_material("Example", G.finish())]

register(sys.modules[__name__])
```

This exact module was built, rendered and passed the periodicity test (`tmp/materials_core/example/`).
Build it: `blender --background --factory-startup --python tools/materials/run.py -- build example --render out/ --bake out/ --periodicity`.

## CLI (`tools/materials/run.py`)

```
blender --background --factory-startup --python tools/materials/run.py -- build <key|all> [--render DIR] [--bake DIR]
        [--save FILE.blend] [--dump DIR] [--views sphere,road] [--engine EEVEE|CYCLES] [--res 800] [--samples 64]
        [--hdri city] [--strength 1.0] [--rotation 0] [--lights] [--tile 4.0] [--bake-res 1024] [--bake-samples 16]
        [--assets] [--periodicity]
blender --background --factory-startup --python tools/materials/run.py -- list
```

`build` imports procmat and its material modules (`procmat.asphalt`, `procmat.cobblestone`, `procmat.glass` when they
exist: a missing one is skipped with a message, one that fails to import prints its traceback), builds `<key>` (or every
library module with `all`), checks the contract, then in this order: `--save` (a clean library .blend; materials keep
fake users; `--assets` marks them as assets), `--dump` (`<material>_NODES.md`), `--render` (object mode,
`rig.preview`), `--bake` (UV-mode tiles + seam metric + 2 x 2 preview; `--periodicity` adds the direct repeat test).
Views: `sphere`, `sphere45`, `plane`, `plane_hd` (300 x 300 quads, for displacement), `cube`, `pane` (vertical glass
pane), `road` (7 m x 20 m strip, eye level 1.7 m), `road_top`. Last line `RUN OK` / `RUN FAIL`, exit code 0 / 1.

Tests: `python tools/materials/tests/test_core.py` (system Python launcher: stage `core` in a factory-startup Blender,
then stage `road` in `tmp/roads/city/base.blend`, one Blender at a time; prints `CORE_TEST OK` / `CORE_TEST FAIL`).

## core

Constants: `PREFIX = "PM_"`, `GROUP_NODE = "MRS"`, `TWO_PI`, `TORUS_AXIS`, `TORUS_ANGLE` (the road tool's tilt),
`TYPES` (FLOAT / INT / BOOL / COLOR / VECTOR / SHADER -> socket idnames), `OUTPUT_TYPES` (known output names),
`CONTRACT_INPUTS`, `CONTRACT_PANEL = "Mapping"`.

### Groups and materials

| signature | returns / does |
|---|---|
| `new_group(name, inputs=(), outputs=("BSDF", "Albedo"), contract=True, scale="Scale", uv_map="UVMap", closed_panels=True)` | `Group` builder for shader group `PM_<name>` (rebuilt in place when it exists, materials keep pointing at it). `inputs`: rows `(name, type, default, min, max, description[, subtype])` or panels `("Panel", [rows])`. `outputs`: names (`BSDF`, `Albedo`, `Metallic`, `Height`, `Displacement`, `Alpha` have known types) or `(name, type)`. `contract=True` appends `Use UV` / `Tile Size` (panel "Mapping") and requires `BSDF` + `Albedo`. `scale` names the input that multiplies every texture coordinate. |
| `contract_material(name, group, displacement=None, viewport=None, roughness=None, metallic=None, settings=None, fake_user=True, **defaults)` | Material `PM_<name>` with one `MRS` group node -> Surface. `defaults` = group input values (underscores for spaces: `Tile_Size=8.0`, or `**{"Stone Size": 0.2}`). `displacement`: None = surface only; True / "BOTH" / "DISPLACEMENT" / "BUMP" links `Displacement` (or `Height` through a Displacement node, midlevel 0, scale 1) and sets `displacement_method` (True = BOTH). `viewport` / `roughness` / `metallic`: viewport display values (default colour: the first `... Color` input) - also what the road tool's glTF export falls back to for non-MRS materials. `settings`: other material attributes, e.g. `{"surface_render_method": "BLENDED"}`. Sets `mat["procmat"] = group name`. |
| `check_contract(mat)` | list of problems (empty = OK) |
| `material(m)` | Material from a Material / name / name without `PM_` |
| `group_node(mat)` | the material's `MRS` node or None |
| `set_inputs(target, **values)` | set inputs of a material's `MRS` node (or any node) by name; returns the names not found |
| `append_materials(blend_path, names=None, link=False)` | load PM materials (and their groups) from a saved library .blend into the open file (e.g. a road scene) |
| `pm_name(name)`, `input_names(tree)`, `output_names(tree)` | helpers |
| `add_socket(tree, name, in_out, stype, default=None, minv=None, maxv=None, desc="", parent=None, subtype=None)` | one interface socket |
| `find_socket(sockets, key, node=None)` | socket by index, identifier or name (enabled namesake first) |

### Builder (also the base of `Group`)

Math helpers return output sockets; texture / ramp / BSDF helpers return the node. Every value argument also takes a
socket (linked instead) or a node (its first output).

| signature | returns / does |
|---|---|
| `node(idname, label=None, name=None, note=None, **props)` / `n(...)` | new node, properties set in order (e.g. `data_type` first); `note` -> custom property `pm_note` (an evidence tag, shown by graphdump) |
| `set(node, key, value)` / `inp(...)` | set or link an input by name (underscores for spaces), identifier or index; colours take 3 / 4 components or a grey float |
| `link(a, b)`, `input(node, key)`, `output(node, key=0)` | links / socket lookup |
| `with frame(label, color=None):` | nodes created inside go into a new frame (frames nest); `new_frame(...)`, `with into(frame):` re-enter one |
| `value(v)`, `rgb(color)` | Value / RGB node output |
| `math(op, a, b=0.0, c=None, clamp=False)` / `m(...)` | Math node output (`op` = Blender identifier: ADD, MULTIPLY, POWER, FLOORED_MODULO, ...) |
| `add sub mul div minimum maximum power (a, b)`, `fract(a)`, `invert(a)` (1 - a), `madd(a, b, c)` (a b + c), `lerp(t, a, b)`, `clamp(v, lo=0, hi=1)` | shortcuts |
| `vmath(op, a, b=None, c=None, scale=None)` | Vector Math output (`Value` for DOT_PRODUCT / LENGTH / DISTANCE) |
| `combine(x, y, z)`, `separate(v)` -> (x, y, z), `separate_color(c)` -> (r, g, b), `gray(v)` | |
| `mix(fac, a, b, data_type="RGBA", blend="MIX", clamp_result=False, clamp_factor=True)` | Mix node Result of that type; `mixf`, `mixv`, `mixc(fac, a, b, blend="MIX", clamp=False)` |
| `ramp(fac, stops=((0, 0), (1, 1)), interpolation="LINEAR")` | Color Ramp node (`.outputs["Color"]`, `["Alpha"]`); stops `(position, colour or grey)` |
| `map_range(v, a0, a1, b0=0, b1=1, clamp=True, interp="LINEAR")`, `smoothstep(v, a, b)` | Map Range outputs (`smoothstep`: 0 at a, 1 at b, a may be > b) |
| `bump(height, strength=1.0, distance=1.0, normal=None, invert=False)` | Bump Normal; chain bumps with `normal=` |
| `principled(**inputs)` | Principled BSDF node (`Base_Color=`, `Roughness=`, `Normal=`, `Transmission_Weight=`, `IOR=` ...) |
| `group(tree, **inputs)` | nested group node |
| `layout(dx=280, gap=28, band_gap=140)` | auto layout: columns by distance to the output, one band per top-level frame, no overlaps, unused Group Input sockets hidden |

### Group (from `new_group`)

`G.tree`, `G.I(name)` (a group input socket; one Group Input node per frame), `G.out(name, value)` (feed a group
output), `G.coords` / `G.C` (the `Coordinates`), `G.finish()` (layout + a warning for unfed outputs; returns the tree).

### Coordinates (`G.coords`)

Attributes (built on first use, frame "Coordinates"): `use` (Use UV), `keep` (1 - use: multiply position-dependent
effects by it so UV mode stays generic), `tile`, `scale`, `obj` (Object coordinates), `uv` (UVMap attribute), `P`
(metres in both modes: obj, or UV x Tile Size), `px` / `py` / `pz`, `V`, `W`, `VW` (the 4D sample point, multiplied by
the scale input: object mode V = obj x scale, W = 0; UV mode V = rotate(R cos u, R sin u, R cos v), W = R sin v,
R = Tile Size / 2 pi, u = 2 pi UV.x, v = 2 pi UV.y: a flat torus whose arc length is metres, so a 4D texture keeps its
object-mode feature size and repeats every Tile Size).

| signature | returns / does |
|---|---|
| `noise4(scale=5, detail=2, roughness=0.5, lacunarity=2, distortion=0, noise_type="FBM", normalize=True, at=None, seed=0.0, exact3d=False, **extra)` | 4D Noise node (`Fac`, `Color`) at `at=(V, W)` (default the group's); `seed` shifts W; `extra`: `Offset=`, `Gain=` |
| `voronoi4(scale=5, feature="F1", metric="EUCLIDEAN", randomness=1, exponent=None, smoothness=None, detail=None, roughness=None, lacunarity=None, normalize=None, at=None, seed=0.0, exact3d=False)` | 4D Voronoi node (`Distance`, `Color`, `Position`, `W`, `Radius`) |
| `exact3d=True` (both) | object mode samples a 3D texture at V (the tutorials' exact field), UV mode the 4D torus; returns a `Dual` whose `.outputs[name]` is a Mix of the two by Use UV (both are evaluated: 2x cost) |
| `warp(color, amount, at=None, blend="LINEAR_LIGHT")` | (V', W): the tutorials' vector distortion, Mix Linear Light (A = coordinates, B = `color`): V' = V + amount (2 B - 1) |
| `stretch(sx, sy, sz=1.0)` | anisotropic (V, W): x / UV u by sx, y / UV v by sy (still seamless) |
| `offset(dv=(0, 0, 0), dw=0.0, at=None)` | (V + dv, W + dw): decorrelated layers |
| `periodic(size)` | (size', n): a repeat length snapped to Tile Size / n in UV mode, and n for `wrap`; object mode keeps size (n = 1e6) |
| `wrap(idx, n)` | cell index modulo n (per-cell randoms repeat with the tile) |
| `snap_scale(scale, period=1.0)` | a Scale for a periodic 3D texture fed with `P` so whole periods fit the tile: Wave bands `period = 2 pi / 20`, Checker `2.0` (Wave distortion / detail use 3D noise: keep them 0 in UV mode, drive Phase Offset from a `noise4`) |
| `seamless(make, blend=0.15)` | fallback for 3D-only textures (Gabor, Brick, Magic, distorted Wave): `make(P)` builds the texture at a metre position and returns a socket (or tuple); UV mode cross-fades `f(P)`, `f(P-(T,0))`, `f(P-(0,T))`, `f(P-(T,T))` (P = fract(UV) x T) over the last `blend` of the tile: exact repeat, 4 evaluations, slightly lower contrast in the blend band |

Rule of thumb for UV mode: raw `P` is NOT periodic. Feed textures with `V`/`W` (4D), with `P` through `periodic`,
`snap_scale` or `seamless`, or with an input that is itself periodic (any texture whose Vector is the Color of a
`noise4` is seamless even in 3D).

## rig

`RIG_SCENE = "PM_Rig"`, `HDRIS = (city, courtyard, forest, interior, night, studio, sunrise, sunset)` (bundled, D6),
`VIEWS`, `CAMERA_PRESETS = (front, 45, top, eye)`.

| signature | returns / does |
|---|---|
| `scene(name="PM_Rig", engine="EEVEE", samples=64, res=(800, 800), gpu=True, view="AgX", hdri="city", strength=1.0, rotation=0.0)` | the preview scene (its own scene; others untouched) |
| `set_engine(sc, engine="EEVEE", samples=64, gpu=True, denoise=True)`, `cycles_gpu(sc)` | EEVEE (identifier read from the enum: `BLENDER_EEVEE` in 5.2) or Cycles on OPTIX / CUDA / HIP / ONEAPI / METAL, else CPU |
| `world(sc, hdri="city", strength=1.0, rotation=0.0, visible=True)`, `hdri_path(name)` | world `PM_World_<hdri>` from a bundled HDRI, rotation in degrees about Z |
| `icosphere(sc=None, subdivisions=6, radius=1.0, location=(0, 0, 1))` | the tutorials' smooth icosphere with UVs |
| `plane(sc=None, size=2.0, uv_tiles=1.0, cuts=0)`, `plane_hd(sc=None, size=2.0, cuts=300)` | UV 0..uv_tiles; `plane_hd` for true displacement |
| `cube(sc=None, size=2.0)`, `pane(sc=None, width=1.2, height=1.8)` | cube with UVs; vertical glass pane facing -Y |
| `road_strip(sc=None, width=7.0, length=20.0, uv_scale=1.0, step=0.5)` | x across, y along 0..length, UVMap = (x, y) x uv_scale (metres like road meshes; `1 / Tile Size` previews a baked tile), point attributes `lat`, `along` |
| `assign(ob, mat)`, `show_only(sc, objs)`, `collection(sc)` | rig object helpers |
| `tutorial_lights(sc=None, key=1000, rim=300)`, `remove_lights()` | two area lights approximating the tutorials' emission planes |
| `camera(sc=None, preset="front", target=None, lens=None)`, `look_at(ob, eye, target)` | front close-up / 45 degrees / top orthographic (frames the object's XY extent exactly) / eye level 1.7 m over a road strip |
| `render(path, res=None, samples=None, scene=None)` | PNG of the scene camera |
| `preview(material, out_dir, views=("sphere", "road"), engine="EEVEE", res=800, samples=64, hdri="city", strength=1.0, rotation=0.0, prefix=None, lights=False, **inputs)` | renders `<prefix or name>_<view>.png`; `inputs` = temporary group input overrides (`Use_UV=1.0` ...). Returns {view: path} |
| `side_by_side(left_png, right_png, out_png, labels=("left", "right"), extra=())` | labelled comparison (Pillow) |

## bake

| signature | returns / does |
|---|---|
| `bake(material, out_dir, tile=4.0, res=1024, samples=16, maps=None, margin=16, use_uv=True, plane_size=None, gpu=True, prefix=None, verbose=True, uv_offset=(0, 0))` | {map: path} of `<prefix or name>_<map>.png`. Plane tile x tile m, Use UV = 1, Tile Size = tile (restored after). Maps: albedo (emission of `Albedo`, else diffuse colour), normal (tangent), roughness, metallic (when the group has it), any other group output name through emission (height, alpha ...). Cycles, GPU when available, own scene `PM_Bake`; displacement reaches the normal map as bump. `use_uv=False` / `plane_size` / `uv_offset` serve the controls and checks. |
| `seam_metric(png)` | {edge_mad, interior_mad, ratio, ratio_x, ratio_y, outlier_x, outlier_y, pct_x, pct_y, size}: wrap-around seam difference vs neighbouring-pixel difference (ratio ~ 1 and outlier <= 1 = no seam) |
| `is_seamless(metric, outlier=1.15, ratio=(0.6, 1.7))` | thresholds used by the tests |
| `periodicity(material, out_dir, tile=4.0, res=512, samples=16, offset=(0.5, 0.25), maps=("albedo",))`, `is_periodic(result, mad=0.012, corr=0.97)` | the direct repeat test: a bake with the material's UVs shifted by `offset` must equal the first tile rolled by offset x res px (robust where one seam column is not: a joint grid snapped onto the seam) |
| `tile_preview(png, n=2, out=None)` | n x n repeat |
| `baked_material(name, paths, repeat=1.0)` | plain image-textured material from bake output (what an engine shows) |

## graphdump

`dump(target, recurse=True)` -> Markdown for a material (its tree, then each group it uses) or a group: interface
(socket, in/out, type, default, min, max, panel, description), node inventory (type, label, frame, non-default settings
and input values compared with a fresh node, colour-ramp stops, `pm_note`), connections. `write(target, path)`.

## road_adapter (no road-tool import)

Road material inputs (`MRS_Road` modifier, `MATERIAL_SOCKETS`): Asphalt Material, Marking Material, Yellow Marking
Material, Concrete Material, Paving Material, Tactile Material, Cycleway Material, Bus Lane Material, Structure
Material, Embankment Material. `Asphalt Condition` (Default / New / Worn / Wet / Patched) and `Sidewalk Surface`
(Default / Tiles / Hexagon / Cobblestone / Brick / Gravel) replace the socket's material with a built-in MRS one unless
"Default"; `assign` sets them to "Default" (also in the object's remembered `mrs_inputs`).

| signature | returns / does |
|---|---|
| `material_sockets(road_obj)` | material input names in interface order |
| `assign(road_obj, socket_name, material, default_menu=True, record=True)` | sets the modifier input by interface name (Blender 5.2 `mod.properties.inputs.<identifier>.value`), the menu to Default, records `obj["pm_materials"]`; returns {object, socket, material, previous, set_via, menu: (menu, old, "Default")} |
| `assign_roads(collection=None, mapping=None)` | `assign` on every road; mapping default `{"Asphalt Material": "PM_Asphalt", "Paving Material": "PM_Cobblestone"}`; missing materials skipped |
| `reapply(collection=None)` | the road tool's `set_road()` / `refresh_all()` put its MRS_* materials back: this restores the recorded ones |
| `evaluated_materials(obj, depsgraph=None)` | {material: face count} of the evaluated road mesh |
| `road_modifier(obj)`, `is_road(obj)`, `roads(collection=None)`, `get_input(mod, name)`, `set_input(mod, name, value)` | helpers |
| `replace_slot_materials(obj, name_contains, material, per_object=False)` | [(slot, previous name)]; per_object links the slot to the object instead of changing the shared mesh |
| `shelter_glass_slots()`, `assign_shelter_glass(material, objects=None, per_object=False)` | bus shelter glass: `MRS_F_BusShelter` / `MRS_F_BusShelter_LOD1` slot 1 `MRS_FurnitureGlass` (slot 0 `MRS_FurnitureAtlas`); older `MRS_BusShelter` / `MRS_BusStopShelter` slot 1 `MRS_PropGlass` |

## registry (`procmat`)

`MATERIALS` {key: module}; `register(module, key=None)` (key = `module.KEY` or the file name);
`discover(names=None, verbose=True)` -> {name: ok / missing / error}; `build(key)` -> [materials];
`library_keys()` (modules with `LIBRARY = False` are left out); `build_all(include_demo=False)` -> {key: [materials]};
`reload()`. `procmat.demo` (key `coredemo`, not in the library) builds PM_CoreDemo / PM_CoreSeamless (and PM_CoreDual).

## imaging (Blender or system Python)

`load(path)` float (H, W, C) top-down, `save(a, path)`, `stats(path)`, `tile(path, n=2, out=None)`, `seam_metric`,
`is_seamless`, `side_by_side(left, right, out, labels, extra=())`, `find_python()`.
CLI: `python -I imaging.py side_by_side L R OUT --labels A B`, `... seam X.png`, `... tile X.png 2 OUT.png`.

## Notes for builders

- Scales: object coordinates are metres; the tutorials' preview object is a 1 m radius icosphere, so a tutorial
  texture Scale is "per metre" as it stands. Expose sizes in metres and pass `1 / size` (D4).
- 4D slices: in a 2D slice of 4D cells (both modes of `voronoi4`) cells vary more in size and Distance to Edge widths
  vary per edge (see `tmp/materials_core/renders/CoreDemo_4Dslice_vs_exact3d.png`); `exact3d=True` keeps the
  tutorials' 3D cells in object mode (UV mode still uses the torus). Noise looks alike either way.
- Position-dependent effects (wear by height, road `lat` / `along` attributes) should be multiplied by `C.keep` so the
  UV-mode tiles stay generic, as the road tool's materials do.
- Displacement: `contract_material(..., displacement=True)` only on dense meshes (`rig.plane_hd`); road meshes are
  coarse, keep the bump. `bake()` turns the displacement into the normal map.
- Glass: pass EEVEE settings with `settings={"surface_render_method": "BLENDED", ...}` (read enum identifiers first).
- The road tool re-applies its own MRS_* materials whenever it refreshes a road: call `road_adapter.reapply()` after.
- The road tool's glTF export (`export.engine_material`) only looks for baked tiles named MRS_*; for PM_* materials it
  writes a flat Principled from the material's viewport colour / roughness / metallic. Mapping PM tiles into Godot is a
  later step (nothing is applied to the game, D10).
