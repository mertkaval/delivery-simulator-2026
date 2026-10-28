# Mert Road Studio

A curve-driven road and street generator for Blender 5.2, built for the Godot delivery simulator.
Everything is generated: an editable Geometry Nodes group, three editable shader groups, explicit
junction meshes, placeholder props, a small N-panel, and a Godot export with separate collision.

```
exec(open("tools/roads/mert_road_studio.py").read())    # Blender text editor, or through Blender MCP
mrs.build_groups(); mrs.register()                       # node groups, materials, props, the panel
mrs.demo_scene()                                         # the validation scene (collection MRS_Demo)
mrs.export_glb("assets/roads/mrs_demo.glb")              # + assets/roads/mrs_demo_collision.glb
```
Re-running the build replaces its own node groups, materials, placeholder props and the demo
collection; other scene content is untouched. Generation is deterministic (seeds are inputs).

Files: `tools/roads/mert_road_studio.py` (the source), `tmp/roads/mert_road_studio.blend` (demo
scene with the groups), `assets/roads/mrs_demo.glb` + `mrs_demo_collision.glb` (export).

## How a road is made (`MRS_Road` node group, framed sections)
- **Road_Profile** - half carriageway = lanes x lane width / 2 + shoulder + median / 2; curb and
  sidewalk outer edges from the inputs.
- **Road_Rail** - Trim Curve (Trim Start / End, in metres, set by the junction manager), Resample
  by length (Resolution), Z-up normals, `along` (spline length) stored on the points.
- **Road_Surface + Sidewalks_Curbs** - each strip is a Curve Line profile (x = lateral, z = up)
  swept with Curve to Mesh: asphalt, curb face and top (both sides), sidewalk slab and outer
  edge (switched by Sidewalk Left / Right), raised median (when Median > 0). The profile's
  lateral position is stored as `lat`.
- **Road_Markings** - thin strips at lateral offsets, 4 mm above the asphalt: centre line (0 none,
  1 solid, 2 dashed, 3 double; none when there is a median), lane lines between lanes, edge
  lines. Dashes are cut with `along mod (dash + gap) > dash` on the face domain.
- **Roadside_Instances** - Curve to Points (Prop Spacing) on a rail shortened by Prop Clear at both
  ends, moved sideways with `tangent x up`, alternating sides (Prop Side 0 / 1 / 2), a collection
  pick by seeded random index, rotation aligned so the prop's +Y faces the road. Manholes the same
  way on the carriageway. Realize Instances is for export.
- **Road_Materials** - Asphalt / Marking / Concrete material inputs; `UVMap` = (lateral metres,
  along metres) so texture scale is stable on any road length; Collision Only drops markings and
  props for the collision export.

Exposed inputs (all live): Lanes, Lane Width, Shoulder, Median, Sidewalk Left/Right, Sidewalk
Width Left/Right, Sidewalk Height, Curb Width, Resolution, Centre Line, Lane Lines, Edge Lines,
Marking Width, Dash Length, Dash Gap, the three materials, Trim Start/End, Props (collection), Prop
Spacing / Offset / Side / Seed / Clear, Manholes (collection), Manhole Spacing, Realize Instances,
Collision Only.

Presets (`mrs.PRESETS`, panel buttons): **residential** (2 x 3.2 m, sidewalks 2 m, dashed centre),
**urban** (4 x 3.5 m, 1.2 m median, shoulders, sidewalks 3 m, edge lines), **service** (one 4.5 m
lane, shoulders, no sidewalks, edge lines).

## Junctions (`mrs.build_junction`, panel "Connect Roads at Cursor")
Explicit: the road ends within 0.6 m of the junction point are connected. For each pair of
neighbouring approaches the asphalt, curb and sidewalk edge lines are intersected to get the
corner points; each road is trimmed to just past its furthest corner (Trim Start / End) and its
Prop Clear is set so no prop stands within 7 m of the junction. The junction object holds the
asphalt polygon through the trimmed road corners, raised curb/sidewalk corner pieces between
neighbouring approaches, a zebra crosswalk on every approach (0.6-3.1 m from the junction) and a
stop line on the incoming half (right-hand traffic).

Supported: 2, 3 or 4 roads meeting at one point, angles between neighbours >= 50 degrees,
straight-through pairs (parallel edges), road ends within 0.05 m in height. Unsupported layouts
raise an error naming the problem (too many roads, acute angle, height mismatch) instead of
producing a fake junction. Not supported yet: roundabouts, slip lanes, roads joining mid-curve,
junctions on slopes, different lane counts meeting with lane tapers.

## Materials (shader groups `MRS_AsphaltShader`, `MRS_PaintShader`, `MRS_ConcreteShader`)
Object-space coordinates in metres (same texel scale on every road). Asphalt: broad tone noise
(Color Variation), Voronoi aggregate + fine grain (bump), repair patches (Voronoi cells gated by
noise, Patch Amount: darker and smoother), Wetness darkens the colour and lowers roughness with
puddles in the low areas of the broad noise. Paint: Paint Wear from a noise mask plus the asphalt
aggregate showing through (colour, roughness and bump together). Concrete: variation, pores,
slab joints every Slab Size metres, Wetness. Exposed: Asphalt Scale, Asphalt Roughness, Color
Variation, Patch Amount, Wetness, Paint Wear, Concrete Variation, Bump Strength. Presets: dry / wet
(panel buttons, `mrs.apply_material_preset`).

## Godot export (`mrs.export_glb`)
Evaluated meshes (instances realized, materials and the metre UVs kept), GLB in metres with +Y up,
and `<name>_collision.glb` with only the asphalt and concrete surfaces (no markings, no props).
The procedural shaders do not transfer: in the game `CityForgeMaterials` maps `MRS_Asphalt`,
`MRS_Paint` and `MRS_Concrete` to its own materials (scanned asphalt with the road shader, paint,
baked paving). Baking the Blender asphalt to a tile is not done yet.

## Validation (tmp/roads/*.png)
Demo scene: straight urban avenue, residential streets, service road, S-curve with one sidewalk,
tight bend without sidewalks, a 4-way and a T junction, dry and wet close-ups. Checked: parameter
changes update the mesh (lanes, sidewalks, presets), no overlapping road strips at junctions
(roads are trimmed), props clear of junctions and roads, markings 4 mm above the asphalt.

## Known limitations
- Junction corners are straight chamfers (no rounded curb radius) and the junction surface is flat.
- No lane tapers where a wide road meets a narrow one; no turn arrows; no traffic signals yet.
- Props are placeholders (streetlight, bollard, barrier, tree, sign, bench, manhole): swap the
  objects in the `MRS_Props` / `MRS_Manholes` collections for real assets.
- Engine side: the demo GLB imports into Godot with the game's materials; traffic lanes for the AI
  are not derived from these roads yet.
