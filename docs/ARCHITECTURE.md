# Architecture

How the game's code is organised, where new code goes, and the rules that keep it fast.
Project history lives in `PROJECT_STATE.md`; asset sources and licences in `../ASSET_LICENSES.md`.

## Runtime layers

```
app/app_root.tscn ── GameApp (app/app_root.gd)          composition root: builds, routes input, frame order
   ├─ Neighborhood (world/neighborhood.gd)              the city: roads, buildings, props, life, traffic
   ├─ CourierPlayer (actors/player.gd)                  movement, vehicles, camera rig, avatar
   ├─ GameHud (ui/hud/game_hud.gd)                      HUD, toasts, name tag, route marker
   ├─ GameMenus (app/game_menus.gd)                     title/pause menu, phone, store computers, map, pages
   ├─ PackageFlow (app/package_flow.gd)                 the package from shelf to door, backpack, delivery
   ├─ Interactions (app/interactions.gd)                what E does + the prompt
   ├─ GamePersistence (app/game_persistence.gd)         new career, save / load
   ├─ CourierSequence, TutorialDirector, CityAudio       one-button actions, training, sound
   └─ DeliverySession (systems/session.gd)              the game state: orders, wallet, needs, clock
```

- **State** lives in `DeliverySession` (plain data + rules, no nodes). Everything else reads it;
  `session.changed` refreshes the HUD.
- **GameApp** owns references and the per-frame order (`_process`): session tick → world clock →
  dispatch → drop zone → prompt → name tag → held package → HUD. Members that only forward to a
  module are the stable surface for other systems and tests (`game.interact()`, `game.notify()`,
  `game.drop_zone` ...). New gameplay goes into a module, not into GameApp.
- **Modules** get the app in `setup(app)` / `_init(app)` and talk to each other through it
  (`game.flow`, `game.hud`, `game.menus`). They don't build each other.
- **World systems** (`world/*`) are self-contained builders and simulations under the
  Neighborhood; they never reach into the app. Living city: `LivingAssets` (people models and
  clips), `LivingCitizen` (animation LOD, props), `CitizenBrain` (walking, avoidance, crossings,
  seats), `CitizenRoutine` (daily timetable and places by role), `CitizenRoutes` (sidewalk graph).
- **Catalogs** (`*_catalog.gd`, `people.json`, `ShopCatalog`, `SignalPlan`) hold data; behaviour
  reads them, so adding a shop item, a person or a route is a data change.

## Assets

Every model is built by a script (`tools/`): Blender builds (`tools/npc/`, `tools/prepare_*.py`)
write GLBs under `assets/`, Godot setup scripts (`tools/setup_*.gd`) configure their imports.
Sources and masters: `source_assets/` (masters in Git LFS), raw downloads in `sketchup_assets/`.
Never hand-edit a generated asset: change the script and rebuild.

## Performance rules

The game is CPU-bound (see `PROJECT_STATE.md`, optimisation pass). Budgets are enforced by
`tests/asset_budget_test.gd` and `tests/perf_budget_test.gd`.
- Nothing rebuilds UI every frame: compare and update only on change (HUD key caps, cards).
- Distance LOD for anything that moves: people animate and think less with distance, vehicles
  update less and skip swept tests far away, shadows switch off by distance.
- 3D textures are VRAM compressed with mipmaps, ≤ 2048 px; a townsperson is one mesh, ≤ 3
  materials.
- Measure before optimising: `tests/perf_probe.gd` (`attrib`, `census`, `exp per_script` ...).

## Code style

GDScript 4.7, statically typed (untyped dictionary / array values get explicit types). One class
per file with `class_name`; a `##` comment on each class and non-obvious function says what it is
for. Tests are headless `SceneTree` scripts printing `NAME: n checks, 0 failures`, listed in
`tests/run_tests.ps1`.
