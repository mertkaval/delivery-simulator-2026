# PM_Glass* - six procedural textured / frosted glass materials (Blender 5.2)

Reverse-engineered from Ryan King Art, "Procedural Textured Frosted Glass Materials (Blender Tutorial)", 2026,
YouTube `SNKNqHd0AYI` (34:03, built in Blender 5.1.1). Builder: `tools/materials/procmat/glass.py`, library key
`glass`. Intended use: glazing - the bus-shelter glass of the road tool's furniture now, building windows later.
Nothing is applied to the game (D10).

| material | video group | look | relief | roughness |
|---|---|---|---|---|
| `PM_GlassCircles` | Textured Glass Circles | dense round dimples (2 cm) | Voronoi Smooth F1 50/m -> RGB Curves -> inverted Bump 2 mm | 0.2 |
| `PM_GlassVoronoi` | Textured Glass Voronoi | clear hammered glass | two Voronoi Smooth F1 30/m -> RGB Curves -> chained inverted Bumps 4 mm + 0.08 mm | 0 |
| `PM_GlassCells` | Textured Glass Cells | faceted crystal plates with patchy frost | Voronoi Distance to Edge 30/m -> Map Range -> inverted Bump 3 mm | Noise 20/m -> Color Ramp -> Hue/Sat/Value (0..0.39) |
| `PM_GlassWavy` | Textured Glass Wavy | reeded / fluted glass, vertical wavy streaks (2.1 cm on any pane) | Gabor 3D (12/m, frequency 5, orientation relative to the surface) -> Bump 0.7 mm | 0.2 |
| `PM_GlassBlobby` | Textured Glass Blobby | crinkled blobs with speckled frost | Voronoi Smooth F1 10/m detail 2.6 -> Bump 4 mm | Noise -> Ramp -> HSV (0..0.45) |
| `PM_GlassFrosted` | Frosted Glass | satin frosted glass | none | Noise -> Ramp -> HSV (0.10..0.48) |

All six: Texture Coordinate Object -> Mapping -> textures -> Glass BSDF (Multiscatter GGX, IOR 1.5, white). Every
node carries its evidence class (A frame / B narration / C ours / D unresolved) and video times in `pm_note`.
Graphs: `NODES.md`; decisions and the version table: `DECISIONS.md`; renders, comparisons and bake: `VALIDATION.md`;
the extraction: `GRAPH_SPEC_a/b.md`, `OPERATION_LOG_a/b.md`, `UNRESOLVED_a/b.md`, `evidence/`.

## Controls

Every group starts with the video's controls (names, order, defaults, ranges as in the video), then the closed
**Mapping** panel with the library inputs. Sizes are per metre (the video's panes have applied scale; see
DECISIONS "Scale conversion").

Common to all six:

| control | default | range | class | effect |
|---|---|---|---|---|
| Scale | 1 | -inf..inf | A | the video's Mapping Scale; 2 = every feature half the size |
| Glass Color | white | colour | A (exact RGBA C) | tint; also the `Albedo` output |
| Glass IOR | 1.5 | 0..1000 | A | refraction strength |
| Mapping > Pattern Size | 1 m | 0.01..100 | C (library) | metres per video unit; scales features and bump depth together |
| Mapping > Use UV | 0 | 0..1 | contract | 0 = object space metres (the video); 1 = UVMap x Tile Size on the seamless torus |
| Mapping > Tile Size | 4 m | 0.05..1000 | contract | repeat length in UV mode |

Per material (class A unless noted):

| material | control | default | range |
|---|---|---|---|
| Circles | Glass Roughness | 0.2 | 0..1 (factor) |
| | Voronoi Scale / Detail / Roughness / Smoothness / Randomness | 50 / 0 / 0.5 / 1.0 / 1.0 | -1000..1000 / 0..15 (C) / 0..1 / 0..1 / 0..1 (C) |
| | Bump Strength | 1 | 0..1 |
| Voronoi | Glass Roughness | 0 | 0..1 |
| | Voronoi Scale 1 / 2 | 30 / 30 | -1000..1000 |
| | Voronoi Smoothness 1 / 2 | 0.1 / 0.03 | 0..1 |
| | Voronoi Detail 1 / 2 | 0 / 3 | 0..15 |
| | Bump Strength 1 / 2 | 1 / 1 | 0..1 |
| Cells | Glass Roughness (multiplier, HSV Value) | 1 | 0..2 |
| | Voronoi Scale / Detail / Roughness / Randomness | 30 / 0 / 0.5 / 1 | -1000..1000 / 0..15 (C) / 0..1 / 0..1 (C) |
| | Noise Roughness Scale / Detail 1 / Detail 2 | 20 / 15 / 1 | -1000..1000 / 0..15 / 0..1 |
| | Bump Strength | 1 | 0..1 |
| Wavy | Glass Roughness | 0.2 | 0..1 |
| | Gabor Frequency | 5 | 0..inf |
| | Bump Strength | 1 | 0..1 |
| | Rotation (Euler, Mapping Rotation) | (0, 0, 0) | - (object axes: tilt the streaks by rotating about the pane's normal axis - Y on an X-Z pane, X on a Y-Z pane) |
| Blobby | Glass Roughness (multiplier) | 1 | 0..2 |
| | Voronoi Scale / Detail / Smoothness | 10 / 2.6 / 0.1 | -1000..1000 / 0..15 (C) / 0..1 |
| | Noise Roughness Scale / Detail 1 / Detail 2 | 20 / 15 / 1 | as Cells |
| | Bump Strength | 1 | 0..1 |
| Frosted | Frosted Amount (multiplier) | 1 | 0..2 |
| | Frosted Scale / Detail 1 / Detail 2 | 20 / 15 / 1 | -1000..1000 / 0..15 / 0..1 (C) |

Outputs: `BSDF` (the Glass BSDF) and `Albedo` (Glass Color).

## Build it alone

```
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
"$B" --background --factory-startup --python tools/materials/run.py -- build glass --save tmp/glass.blend
"$B" --background --factory-startup --python tools/materials/run.py -- build glass --render tmp/glass_prev --engine CYCLES
```

In Python inside Blender (with `tools/materials` on `sys.path`):

```python
import procmat
mats = procmat.build("glass")                  # all six PM_Glass* materials
from procmat import glass
glass.build(["GlassWavy"])                      # one variant
procmat.core.set_inputs(procmat.core.group_node("PM_GlassFrosted"), Frosted_Amount=0.5)
```

The video scene, real-world checks and bake: `scripts/glass_scene.py` (see `VALIDATION.md`, Reproduce).

## Use it in the road tool (Mert Road Studio)

The materials follow the library contract (one group node `MRS`, outputs `BSDF` / `Albedo`, inputs `Use UV` /
`Tile Size`), so the road tool can take them like any `MRS_*` material:

```python
import procmat
from procmat import road_adapter as RA
procmat.build("glass")
RA.assign_shelter_glass("PM_GlassFrosted")           # bus shelter glass slot (MRS_FurnitureGlass / MRS_PropGlass)
RA.assign_shelter_glass("PM_GlassWavy", per_object=True)   # one shelter only, without changing the shared mesh
RA.reapply()                                         # after the road tool refreshes and restores its own materials
```

- Glazing objects should have applied scale (object coordinates = metres) or UVs in metres with `Use UV = 1`.
  Typical choices: shelter side panels `PM_GlassFrosted` or `PM_GlassWavy`; office windows `PM_GlassVoronoi` /
  `PM_GlassCells` with `Pattern Size` 1; bathroom windows `PM_GlassCircles` / `PM_GlassBlobby`.
- `PM_GlassWavy` reads its wave direction from the surface (DECISIONS G18): in object mode every pane - the shelter's
  back glass (X-Z) and side glass (Y-Z) in the same mesh, or a horizontal plane - gets the video's vertical streaks
  with the same 2.1 cm period, seen from either side. In UV mode the streaks run along V (UVs in metres, Tile Size).
- EEVEE: the materials use Dithered render method with raytraced refraction; enable Raytracing in the scene's EEVEE
  settings to see refraction.
- Bakes (`procmat.bake.bake(..., use_uv=True)`) give seamless albedo / normal / roughness tiles; transmission is not
  baked - a game needs its own glass shader using those maps. The road tool's glTF export writes a flat Principled from
  the viewport colour (pale blue-grey, alpha 0.3-0.6) and roughness for PM_* materials.

## Limits

- The video HDRI is not available (D6): validation used bundled HDRIs; lighting differences are documented separately.
- Wavy in UV mode uses a four-sample cross-fade (no 4D Gabor) with a variance-preserving gain (G17): the streak
  amplitude stays within 1 % across the 15 % blend band, but the streaks inside the band are a blend of two fields
  (less coherent wave crests over about 2 cm at the band centre).
- Wavy in object mode: the streak direction follows the surface normal; on curved glass whose normal crosses the
  plane N . (0.1, -1, 0.05) = 0 the side choice flips and leaves a seam (flat panes are not affected).
- Blobby's relief through the glass reaches 0.65-0.9x the video's Blobby / Voronoi contrast ratio in our scenes
  (0.34-0.46 vs 0.52, backdrop dependent). The graph is pixel-identical to the video's literal graph, so this is
  scene / lighting (VALIDATION section 6b); kept open, no value tuned.
- Glass normals are subtle; game bakes should be written at 16 bit.
