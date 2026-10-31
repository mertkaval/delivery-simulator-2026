# PM_Asphalt - procedural asphalt (Blender 5.2)

A dark, worn asphalt / concrete surface reverse-engineered node for node from Ryan King Art, *Procedural Asphalt
Material (Blender Tutorial)*, 2022, YouTube `Eofg9SBcdBY` (built in Blender 3.2 in the video): soft cellular
mottling from #1A1817 to #4D4D4D, networks of thin black recessed cracks over about half the surface, irregular
broken-away patches that show 9 mm pebbles with recessed edges, a fine grain everywhere, rough (0.41-1.0). Bump only,
no displacement (as in the video). Part of the `procmat` library (`tools/materials/`), separate from the road tool but
built on its material contract, so it plugs into Mert Road Studio's **Asphalt Material** socket. Nothing is applied to
the game.

![video vs ours](comparisons/cmp_final_video_vs_PM_Asphalt.jpg)

| material | what it is |
|---|---|
| **PM_Asphalt** | the one to use: the video's graph with its tuned values as controls (below) |
| PM_AsphaltTutorial | the same graph with the video's literal ColorRamps and constants, no controls besides the contract inputs and Pattern Size: the reference PM_Asphalt is checked against (identical albedo within 4/255) |

Code: `tools/materials/procmat/asphalt.py` (registry key `asphalt`). Spec: `GRAPH_SPEC_all.md`. Nodes: `NODES.md`.
Decisions and the 3.2 -> 5.2 adaptation table: `DECISIONS.md`. Renders, comparisons, bake and road checks:
`VALIDATION.md`.

## Controls (group PM_Asphalt)

Evidence: **A** value read in a video frame, **B** narration, **C** our implementation. Every control is class C as a
control (the video exposes none); the default is the video's value with its own class.

| input | default | range | what it drives (video node) | default from |
|---|---|---|---|---|
| Pattern Size | 1.0 m | 0.05-100 | divides every texture coordinate: 1 = the video's sizes (base cells 0.1 m, crack networks ~0.4 m, damage patches ~0.3 m); 2 = all twice as large except the aggregate | C (D4; the video's sphere radius 1 m assumed, U7) |
| Aggregate Size | 0.00909 m (1/110) | 0.001-0.2 | pebble cells in the damaged patches (`damage_voronoi` Scale 110) and the grain (`bump_noise` Scale 60 x 1/110) | A value (Scale 110, 60), C mapping |
| Color Dark | #1A1817 | colour | base ramp stop 0 (`color_ramp`) | A (06:12 caption) |
| Color Light | #4D4D4D | colour | base ramp stop 1 | A (06:28) |
| Crack Amount | 0.499 | 0-1 | crack mask black stop (`cracks_mask_ramp`): higher = more crack regions | A (09:38, 26:32) |
| Crack Width | 0.094 | 0-1 | crack groove width (`crack_bump_ramp` white stop): lower = thinner | A (23:27, 26:32) |
| Damage Amount | 0.35 | 0-1 | damage mask black stop (`damage_mask_ramp`; white stop +0.092): higher = more and larger broken patches | C (0.343 legible before a jump cut, 0.350 measured, U1) |
| Damage Darkness | 0.338 | 0-1 | darkening of the broken patches (`damage_dark_ramp` black stop): higher = darker | A (18:11, 26:32) |
| Roughness Min | 0.4072 (#ABABAB) | 0-1 | roughness at the base cell edges, 1 in the cell centres (`rough_ramp`): lower = shinier / wet | A (26:22) |
| Bump Grain | 0.1 | 0-1 | `bump1` Strength (grain noise) | A (20:44) |
| Bump Cells | 0.2 | 0-1 | `bump2` Strength (base cells) | A (21:40) |
| Bump Cracks | 0.3 | 0-1 | `bump3` Strength (crack grooves) | A (22:20) |
| Bump Damage | 0.4 | 0-1 | `bump4` Strength (patches and pebbles) | A (24:40) |
| Bump Filter Width | 1.0 | 0-10 | Filter Width of the four Bump nodes (an input 3.2 does not have): 1 = the video's relief, 0.1 = the 5.2 default, about half the relief | C (measured, AS5) |
| Use UV (panel Mapping) | 0 | 0-1 | 0 = object space in metres (roads, previews); 1 = UVMap x Tile Size on a seamless 4D torus (baking tiles), with the object-mode statistics (AS17) | C (contract D2) |
| Tile Size (panel Mapping) | 4.0 m | 0.05-1000 | the repeat of a baked tile in UV mode | C (contract D2) |

Outputs: `BSDF`, `Albedo`. What the controls do: `comparisons/controls_sheet.jpg`.

![controls](comparisons/controls_sheet.jpg)

## Build it alone

```
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
"$B" --background --factory-startup --python tools/materials/run.py -- build asphalt --render out/ --views sphere,road
"$B" --background --factory-startup --python tools/materials/run.py -- build asphalt --save out/asphalt_library.blend --assets
"$B" --background --factory-startup --python tools/materials/run.py -- build asphalt --bake out/ --tile 4 --bake-res 1024 --periodicity
```

Inside Blender (any file, nothing else is touched):

```python
import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/materials")
import procmat
mats = procmat.build("asphalt")                    # [PM_Asphalt, PM_AsphaltTutorial]
procmat.core.set_inputs("PM_Asphalt", **{"Crack Amount": 0.3, "Pattern Size": 1.5})
```

The video's scene (for comparisons): `scripts/video_scene.py` (see VALIDATION.md, Reproduce).

## Use it in the road tool (Mert Road Studio)

The road tool's `MRS_Road` modifier has a material input **Asphalt Material**; any procmat material fits it because
PM_Asphalt follows the same contract as the road tool's own MRS materials (one group node named `MRS`, inputs
`Use UV` / `Tile Size`, outputs `BSDF` / `Albedo`). Proven in a real road scene, see VALIDATION.md section 8.

1. Bring the material into the road file, either by building it there (`procmat.build("asphalt")`) or by appending it
   from a saved library: `procmat.core.append_materials(r".../asphalt_library.blend", ["PM_Asphalt"])`.
2. Assign it:
   - by hand: road object > Modifiers > MRS_Road > set **Asphalt Condition** to *Default* (any other condition
     replaces the socket's material with a built-in MRS one) and pick `PM_Asphalt` in **Asphalt Material**;
   - or by script: `procmat.road_adapter.assign(road, "Asphalt Material", "PM_Asphalt")` (sets the condition to
     Default and records the assignment), or for every road of a collection
     `procmat.road_adapter.assign_roads(collection, {"Asphalt Material": "PM_Asphalt"})`.
3. The road tool re-applies its own MRS_* materials whenever it refreshes a road (`set_road()`, `refresh_all()`):
   call `procmat.road_adapter.reapply(collection)` afterwards.
4. Keep **Use UV = 0** on roads: road meshes are in metres and the material works in object space, so every road has
   the same texel scale. Use UV = 1 is for baking tiles. The road tool's material presets (`apply_material_preset`)
   do not touch PM_Asphalt (no shared input names). Scale the look with Pattern Size (and Aggregate Size), not with
   the mesh.
5. Godot: not wired yet (decision D10). The road tool's glTF export writes a flat Principled from the viewport colour
   (0.028 linear grey) and roughness (0.59) for non-MRS materials; seamless 4 m tiles for a later Godot material are
   produced with `run.py ... --bake` (examples in `tmp/materials_bake/asphalt/`).

Note: each texture that is 3D in the video has a 4D twin for the seamless UV mode, so the group holds 16 textures
where the video has 9; EEVEE evaluates both twins (shader cost not measured). Blender's 4D Noise / Voronoi have a
narrower value spread than the 3D nodes, so each twin's output is remapped (`UV_MATCH`, decision AS17): a baked tile
has the same mottling, crack and damage statistics as the object-mode material (measured, VALIDATION.md 7a).

## Files

| path | what |
|---|---|
| `tools/materials/procmat/asphalt.py` | the builder (both materials) |
| `GRAPH_SPEC_all.*`, `OPERATION_LOG_all.md`, `UNRESOLVED_all.md`, `DECISIONS_all.md`, `evidence/` | the reverse-engineered specification and its evidence (extraction step) |
| `NODES.md` | interface, node inventory, connections of both groups + mapping to the spec |
| `DECISIONS.md` | build decisions AS1-AS18, 3.2 -> 5.2 adaptation table, scale conversion |
| `VALIDATION.md` | renders, comparisons, measurements, bake seam metric, road-tool checks, remaining differences |
| `renders/`, `comparisons/`, `checks/` | evidence (PNG renders, JPEG panels, JSON numbers) |
| `scripts/` | `video_scene.py` (video scene, close-up, road renders), `compare.py` (panels, metrics), `verify_graph.py` (spec links), `metres_check.py`, `sphere_maps.py` + `view_match.py` (view search), `road_check.py` (road tool), `uv_match.py` (per-texture object vs UV distributions, the AS17 fit) + `uv_stats.py` (whole-material object vs UV statistics), `damage_views.py` + `damage_detect.py` (damage coverage across views vs the video) |

## Limits

- The look, scale and statistics match the video; the exact positions of its cracks and patches do not (VALIDATION.md
  section 5): Blender 5.2's textures do not reproduce the video's field on a 1 m sphere. The video's view shows a
  little more damage than our comparison view (0.041 vs 0.030 +- 0.013 over 24 of our views): within the spread
  between views, so Damage Amount keeps the video's value (AS18).
- Lighting in the comparisons is a fitted substitute (bundled HDRI, emitter sizes unknown); the video's fill is warmer.
- Bump only. Very large object coordinates (far from the road object's origin) were not tested for float precision.
