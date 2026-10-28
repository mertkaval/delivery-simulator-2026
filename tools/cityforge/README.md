# CityForge: the generated city (Port Halden)

The whole city is generated from two spec files, in about a minute, by one command:

```
tools/cityforge/build.sh            # terrain -> plan -> Blender build -> assets/cityforge -> Godot import -> test
```

| Step | Script | Output |
|---|---|---|
| Terrain | `tools/terrain/city_terrain.py` + `port_halden_terrain.json` | relief, hills, lake, river, sea, harbour inlet (`terrain.npz`) |
| Plan | `plan_city.py` + `port_halden_city.json` (+ `overrides.json`) | `city.json`: every road, lot, house, fence, shop, tower, park, lamp, sign, tree, name and address; the ground graded under roads and lots |
| Build | `build_city.py` (Blender, headless) with `geo.py`, `kit.py` | `kit.glb` (repeated models, LOD0 + LOD1), `chunks/c_i_j.glb` (64 × 256 m), `outskirts.glb`, a preview `.blend` |
| Game | `world/cityforge/cityforge_world.gd` (`CityForgeWorld`) | the city in Godot: chunks, MultiMesh instances with HLOD, ground + building collision |
| QA | `qa_render.py` (Blender renders), `tests/capture_cityforge.gd` (Godot renders), `tests/cityforge_test.gd` | evidence and contracts |

Fly round it: open `world/cityforge/port_halden_preview.tscn` in Godot and press F6
(mouse look, WASD, Q/E, Shift, N for night, F for street level).

## The city spec (`port_halden_city.json`)

- `grid`: north-south streets every 200 m, east-west avenues every 100 m, which of them are
  arterials, the steepest grade a local street may climb (steeper slopes are left as green).
- `downtown`: the peninsula polygon, the grid angle (36°), block spacing, the park side, the
  boundary boulevard. The waterfront ring (Seawall Drive) and pocket parks follow from it.
- `diagonal`: the Kingsway-style arterial across the grid. `bridge_max_span_m`: arterials bridge water up to this span.
- `lots`: Burnaby lots, 15 m frontage off the avenues, a back lane, house size range, garage chance.
- `parks`, `industrial`, `public` (city hall, hospital, police, fire halls, schools, library,
  community centre), `neighbourhoods`, `names` (fictional), `palettes` (siding, roof, leaf colours).

## Editing one asset (overrides)

Every planned item has a stable id (`lot_0412`, `house_0412`, `tree_0042`, `lamp_0100` ...; see
`city.json`). Put changes in `tools/cityforge/overrides.json` (next to the spec); they survive
regeneration:

```json
{
  "house_0412": {"archetype": "tudor", "siding": 4, "roof": 1, "fence": "hedge"},
  "house_0007": {"remove": true},
  "lot_0100":   {"remove": true},
  "tree_0042":  {"remove": true},
  "lamp_0100":  {"pos": [1012.5, 1304.0]}
}
```

House archetypes: `craftsman`, `vancouver_special`, `bungalow`, `modern_box`, `foursquare`,
`tudor`, `split_level`, `west_coast`. Fences: `wood`, `hedge`, `brick`, `picket`, `iron`.

## Contracts

- Coordinates: plan metres, x east, y north, origin at the south-west corner. Godot:
  `CityForgeWorld.to_world(x, y, h)` = `(x - 1024, h, -(y - 1024))`. Blender: `(x - 1024, y - 1024, h)`.
- Models face +Y in Blender (-Z in Godot); yaw turns counter-clockwise seen from above.
- Material names `CF_*` map to game materials in `world/cityforge/cityforge_materials.gd`
  (the classic city's procedural surfaces and scanned textures, so both cities share one look).
  Tinted surfaces read COLOR (MultiMesh instance colour or vertex colour); roofs read INSTANCE_CUSTOM.
- Road marking data rides in the road mesh: UV (lateral, along), UV2 (class, to-end), COLOR (control at each end).
- Performance: near a chunk its houses and trees are MultiMeshes per 128 m cell (LOD0); further
  away one merged mesh per chunk (`Far`, built in Blender) replaces them through Godot's HLOD
  (`visibility_parent`). Small props fade at 140 m, lamps and signals at 520 m, fences at 320 m.
  Road, sidewalk and building collision is built per chunk near the player only.
- Never hand-edit the GLBs or `city.json`: change a spec, the overrides or a script and rebuild.
- Exporting the game: include `*.json, *.f32` as non-resource files (the plan and the heights).
