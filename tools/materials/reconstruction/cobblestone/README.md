# PM_Cobblestone (procmat)

Procedural cobblestone ground: grey-brown rounded stones in a distorted Voronoi layout, dark brown dirt joints with
moss, olive moss patches on the stones, 6 mm stone relief. Reverse-engineered from Ryan King Art, *Procedural
Cobblestone Ground Material (Blender Tutorial)*, 2026-01-12, 40:41, YouTube `30vbbpy9zwg` (Blender 5.0.1), and
rebuilt for Blender 5.2 in the procmat library (`tools/materials/procmat/cobblestone.py`, key `cobblestone`).

In object mode it reproduces the video's own field: the same stones appear on the same 0.5 m sphere seen from the
same camera (VALIDATION.md). In UV mode (Use UV = 1) it repeats every Tile Size and bakes to seamless tiles; since the
audit (VALIDATION.md section 6, decision CB16) the UV mode / baked tile has the object mode's stone coverage, stone
size and rock relief. At the defaults stones are about 10 cm (median; area-weighted 12.6 cm, 78 % of the stone area in
10-25 cm) with wide dirt joints (49 % stone cover).

| material | for |
|---|---|
| `PM_Cobblestone` | roads, plazas, sidewalks (Mert Road Studio sockets); relief as bump (displacement_method BUMP) |
| `PM_CobblestoneDisplaced` | dense meshes (preview spheres, `plane_hd`, subdivided ground): "Displacement and Bump" as in the video |

Both use the group `PM_Cobblestone`. Files here: `NODES.md` (graphdump), `DECISIONS.md` (class C decisions,
version adaptation, scale), `VALIDATION.md` (renders, comparisons, seam metric, audit), `GRAPH_SPEC_a/b.*` (the
specification), `renders/`, `comparisons/`, `checks/` (audit numbers: graph check, seam, UV-mode match, metres),
`scripts/` (validation and audit scripts), `evidence/` (video frames).

## Controls

Defaults, ranges and subtypes are the tutorial group's (segment b, read in the item properties: class A; colours:
the narrated / typed hex, B+A). Sizes: object space = metres (the video's sphere has radius 0.5 m, scale applied).

| control | panel | default | range | class | effect |
|---|---|---|---|---|---|
| Material Scale | - | 1.0 | -inf..inf | A | multiplies every texture coordinate (2 = everything half as large) |
| Pattern Size | - | 1.0 m | 0.01..100 | C | metre control (D4): everything scales with it; 1 = the video |
| Distortion Scale | Rock Distortion | 2.0 | -1000..1000 | A | size of the outline distortion noise |
| Distortion Detail 1 | Rock Distortion | 7.0 | 0..15 | A | more / less ragged stone edges |
| Distortion Detail 2 | Rock Distortion | 0.5 | 0..1 (factor) | A | roughness of the distortion noise |
| Distortion Strength | Rock Distortion | 0.2 | 0..1 (factor) | A | 0 = round smooth stones, higher = chunky shapes |
| Dirt Scale | Dirt & Moss | 20.0 | -1000..1000 | A | dirt noise scale |
| Dirt Moss Scale | Dirt & Moss | 25.0 | -1000..1000 | A | moss-on-dirt scale |
| Dirt Color 1 | Dirt & Moss | #332C24 | colour | B+A | first dirt colour |
| Dirt Color 2 | Dirt & Moss | #19140F | colour | B+A | second, darker dirt colour |
| Dirt Moss Color | Dirt & Moss | #232511 | colour | B+A | moss on the dirt |
| Dirt Roughness | Dirt & Moss | 1.0 | 0..2 | A | dirt roughness multiplier (lower = shinier / wet) |
| Dirt Detail 1 | Dirt & Moss | 10.0 | 0..15 | A | dirt noise detail |
| Dirt Detail 2 | Dirt & Moss | 0.55 | 0..1 (factor) | A | dirt noise roughness |
| Dirt Moss Detail 1 | Dirt & Moss | 9.0 | 0..15 | A | moss-on-dirt detail |
| Dirt Moss Detail 2 | Dirt & Moss | 0.5 | 0..1 (factor) | A | moss-on-dirt roughness |
| Dirt Moss Visibility | Dirt & Moss | 1.0 | 0..2 | A | more / less moss in the joints |
| Dirt Bump Strength | Dirt & Moss | 1.0 | 0..1 (factor) | A | dirt bump |
| Dirt Moss Bump Strength | Dirt & Moss | 1.0 | 0..1 (factor) | A | moss-on-dirt bump |
| Cobblestone Scale | Cobblestone Chunks | 7.0 | -1000..1000 | A | stones per metre (7 = 0.14 m stones) |
| Cobblestone Cracks | Cobblestone Chunks | 0.0 | 0..15 | A | Voronoi detail: small cracks / chunks (about 1 recommended) |
| Cobblestone Visibility | Cobblestone Chunks | 1.0 | 0..1 (factor) | A | lower = stones sink into the dirt |
| Cobblestone Alignment | Cobblestone Chunks | 1.0 | 0..1 (factor) | A | Voronoi randomness: lower = aligned rows (setts) |
| Cobblestone Individual Size | Cobblestone Chunks | 0.6 | 0..1 (factor) | A | lower = fuller stones / narrower joints (0.5 is close to the video's product render) |
| Displacement Strength | Cobblestone Chunks | 0.02 | 0..1000 | A | relief scale: stones rise 0.3185 x this = 6.4 mm |
| Rock Moss Scale | Rocks and Moss | 15.0 | -1000..1000 | A | moss patch scale on the stones |
| Rock Moss Visibility | Rocks and Moss | 1.0 | 0..2 | A | more / less moss on the stones |
| Rock Moss Color | Rocks and Moss | #222812 | colour | B+A | moss on the stones |
| Rock Moss Roughness | Rocks and Moss | 0.65 | 0..1 (factor) | A | moss roughness |
| Rock Moss Detail 2 | Rocks and Moss | 0.7 | 0..1 (factor) | A | moss bump noise roughness |
| Rock Moss Detail 1 | Rocks and Moss | 15.0 | 0..15 | A | moss bump noise detail |
| Rock Moss Bump Strength | Rocks and Moss | 1.0 | 0..1 (factor) | A | moss bump |
| Rock Color 1 | Cobblestone Rocks | #343534 | colour | B+A | stone colour, grey |
| Rock Color 2 | Cobblestone Rocks | #292524 | colour | B+A | stone colour, brownish |
| Rock Roughness | Cobblestone Rocks | 0.65 | 0..1 (factor) | A | stone roughness |
| Rock Detail | Cobblestone Rocks | 10.0 | 0..15 | A | stone surface detail (noise and Voronoi) |
| Rock Bump Strength | Cobblestone Rocks | 1.0 | 0..1 (factor) | A | stone bump (both rock bumps) |
| Use UV | Mapping (closed) | 0 | 0..1 | contract | 0 = object space in metres; 1 = UVMap x Tile Size on the seamless 4D torus |
| Tile Size | Mapping (closed) | 4.0 m | 0.05..1000 | contract | metres covered by UV 0..1 in UV mode |

Outputs: `BSDF`, `Albedo`, `Displacement` (vector, object space), `Height` (stone relief in metres).

## Build it alone

```
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" --background --factory-startup ^
    --python tools/materials/run.py -- build cobblestone --save tmp/materials_cobble/PM_Cobblestone.blend --assets
```

Add `--render DIR --views sphere,plane_hd,road` for the standard previews, `--bake DIR --tile 4.0 --bake-res 1024
--periodicity` for seamless tiles, `--dump DIR` for the node documentation. Inside Blender:
`sys.path.insert(0, "<repo>/tools/materials"); import procmat; procmat.build("cobblestone")`.
The tutorial-scene validation renders: `tools/materials/reconstruction/cobblestone/scripts/render_tutorial.py`
(command in VALIDATION.md).

## Use it in the road tool (Mert Road Studio)

The material follows the road tool's material contract (one group node `MRS`, Use UV / Tile Size, BSDF + Albedo), so
it plugs into the `MRS_Road` modifier's material sockets:

```python
import sys; sys.path.insert(0, r"<repo>/tools/materials")
from procmat import core, road_adapter as RA
core.append_materials(r"<library>.blend", ["PM_Cobblestone"])      # or procmat.build("cobblestone")
RA.assign(road_obj, "Paving Material", "PM_Cobblestone")           # sidewalks / plazas (Sidewalk Surface -> Default)
RA.assign(road_obj, "Asphalt Material", "PM_Cobblestone")          # a cobbled carriageway (Asphalt Condition -> Default)
# RA.assign_roads(mapping={"Paving Material": "PM_Cobblestone"})   # every road; RA.reapply() after a road refresh
```

Use `PM_Cobblestone` (bump) on roads, not `PM_CobblestoneDisplaced`: road meshes are too coarse for true
displacement. Checked on a road built by the road tool (`renders/road_tool_PMC_Road.png`). Nothing is applied to the
game (D10); for Godot, bake UV-mode tiles (`--bake`), which are seamless at any Tile Size.
