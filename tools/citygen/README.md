# City generation prototype (2026-10-23)

Evaluation tooling for the city plan pipeline described in `docs/CITY_GENERATION_PLAN.md`.
Nothing here is used by the game yet.

## 1. Street plan: City Map Generator, headless and seeded

[probabletrain/MapGenerator](https://github.com/probabletrain/MapGenerator) (LGPL-3.0) is the
engine behind the itch.io City Generator. `generate.ts` runs its pure `impl/` core in Node with a
seeded `Math.random`, so the same seed + layout always gives the same city:
coast and river → main → major → minor roads → parks → building lots.

```
git clone --depth 1 https://github.com/probabletrain/MapGenerator.git
cd MapGenerator && npm ci --ignore-scripts
mkdir headless && cp <repo>/tools/citygen/generate.ts <repo>/tools/citygen/tsconfig.json headless/
./node_modules/.bin/tsc -p headless/tsconfig.json      # type warnings about two imports are expected
node out/headless/generate.js <seed> <out.json> [layout.json]
```

`layout.json`: world size, grid fields `[x, y, size, decay, angle]` (one per district: its street
angle), radial fields `[x, y, size, decay]` (plazas, old towns), `water`. Output JSON (map units;
the prototype uses 1 unit = 4 m): `main` / `major` / `minor` road polylines, `coast`, `sea`,
`river`, `parks`, `lots`, `intersections`. A city of ~2,000-6,500 lots takes about a second.

## 2. Street plan → Blender

`city_from_map.py` (Blender, with the Procedural Building Shell Generator add-on enabled) turns a
plan into roads with sidewalks, parks, water and one styled building per lot: each lot's
minimum-area rectangle, front turned to the nearest road, the district's cultural style profile
(floors, windows, storefronts, pilasters, palette) from the nearest grid field.

`sandbox.sh` runs Blender headless in an isolated profile (`sandbox/config`, `sandbox/scripts`,
`sandbox/extensions` next to this folder's parent), so evaluation add-ons never touch the
everyday Blender preferences. `evalkit.py`: shared helpers (enable add-ons, stats, renders).
