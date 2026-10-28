# Procedural building materials prototype — report (2026-10-28)

Building: `H_eur_casa_2` (European stucco villa from the CityForge catalogue), chosen because it
mixes stucco, terracotta roof, painted shutters/door, wood trim and glass on one object.

Files: `tools/cityforge/proto_materials.py` (node groups, materials, unwrap, bake, export),
`tools/cityforge/proto_bake_cli.py` (headless pipeline), `tmp/cityforge/prototype_casa.blend`
(working scene), `assets/cityforge/prototypes/H_eur_casa_2.glb` + six 2K PNGs (two atlases ×
albedo / normal / ORM), `docs/prototype_casa_before_after.png`, `tests/capture_prototype.gd`.

## Node groups created (shader editor, reusable on any object)

| Group | Role |
|---|---|
| `CF_Coord` | wall-aligned metre coordinates (picks (y,z) or (x,z) per face) + Up output |
| `CF_GeoMasks` | pointiness edge mask, AO cavity mask, height-above-ground mask |
| `CF_EdgeWear` | edge mask × noise → exposed under-layer at corners/edges |
| `CF_Scratches` | stretched noise streaks, directional, masked by wear amount |
| `CF_Damage` | Voronoi chips with raised rims (colour + bump) |
| `CF_Grime` | blotch grime + gravity streaks under sills, strongest near the ground |
| `CF_Layer` | stacks one wear layer over a base (colour / roughness / bump / mask) |
| `CF_Base_Stucco`, `CF_Base_Terracotta`, `CF_Base_PaintedMetal`, `CF_Base_Wood`, `CF_Base_Glass` | base materials with exposed colour / scale / roughness |
| `CF_BakeTarget` | image-texture target node for baking |

Materials assembled from them: `CF_Stucco`, `CF_RoofTerracotta`, `CF_Trim`, `CF_Shutter`,
`CF_Door`, `CF_Metal`, `CF_Concrete`, `CF_Glass`. One `seed` input shifts every noise together.

## Verified techniques vs. implementation choices

Verified against the tutorial frames the user supplied (Node Wrangler workflow, Noise/Voronoi/
ColorRamp/Bump stack, grimy whitewashed brick): layered masks multiplied into a base, grime kept in
cavities and near the ground, bump from the same masks as colour, ragged ColorRamp edges.
Implementation choices made here (not from the tutorial): pointiness-based edge wear (needs
enough geometry — the house meshes were triangulated so it reads), ORM packing for Godot,
two atlases per building to stay inside a 2K budget, OpenGL-convention normals.

## Pipeline that works headlessly
hidden-face removal (cone raycast) → bmesh split into two atlases → triangulate → Smart UV Project
→ Cycles GPU bakes (DIFFUSE colour, NORMAL tangent, ROUGHNESS, EMIT-as-metallic, AO) → ORM pack →
glTF with fresh image datablocks. Godot: `setup_materials.py` sets VRAM compression and the
normal-map flag; import verified in a headless capture (`tests/capture_prototype.gd`); asset budget
test passes.

## Limitations
- Stucco normal detail is thin at 2K over a whole façade (≈ 4 mm/texel); fine chips read, pores do not.
- Two 2K atlases per building = 6 textures, 24 MB GLB — fine for one hero, not for 148 houses
  unshared. Applying the system to the rest of the catalogue needs per-material tiling bakes
  (the `materials.py` route) with only the wear masks baked per object.
- Glass is opaque in the bake (no transmission export).
- Only `H_eur_casa_2` has been processed; the other 147 houses still use the tiled library.
