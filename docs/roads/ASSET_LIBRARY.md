# Asset Browser package (v5)

`tools/roads/mrs/library.py` packages the working Road Studio pieces as Blender assets. The package is one
self-contained `.blend` with every image packed, plus its catalog file.

    blender --background --factory-startup --python tools/roads/tests/asset_library_test.py

The output goes to `tmp/roads/v5/library/`:

| file | contents |
|---|---|
| `MertRoadStudio_Library.blend` | the assets |
| `blender_assets.cats.txt` | the catalogs |
| `thumbnails/` | 256 px renders |
| `library.json` | names, catalogs, descriptions |
| `verify.json` | fresh-file check |

To use it, add the folder as an Asset Library in Blender (Preferences, File Paths, Asset Libraries). Or open
the file and use the "Current File" library. Nothing is written to your preferences by the build.

## Catalogs (`Mert Road Studio/...`)
| catalog | assets | procedural controls kept |
|---|---|---|
| Roads | one 40 m road per preset: residential, urban, highway, rural, service, bridge | the `MRS_Road` Geometry Nodes modifier with every input live (lanes and transitions, widths, cycleways, kerbs, crossing ramps, driveways, markings, structure, materials). Edit the curve and the road regenerates. |
| Footbridges | Girder, Truss and Box footbridges solved over a demo avenue | the `MRS_Footbridge` modifier: style, width, railings, LED handrail, deck lights, hardware materials. Re-solve over your own road with `footbridge.make(name, road, along, collection)`. |
| Furniture | the 20-item sidewalk furniture set on its baked atlas | footprint, access and zone properties used by the placer |
| Lighting | Highway, Double, LED, Lantern, Bollard, WallPack streetlights | light anchors (`mrs_fixtures`) for the real light sources |
| Signs | regulatory, warning and information signs (baked game versions) and direction boards | sign metadata. Editable text versions come from `signage.make_sign`. |
| Barriers | guardrail, jersey, parapet, railing, fence, hedge (2 m tiling segments) | used by the road's barrier inputs |
| Trees / Plants | the game's landscape-kit species, LOD0 and LOD1, and the planting set | the same meshes the Godot MultiMesh LODs use |
| Buildings | the city-kit shop frontage | rebuild any size or position with `frontage.make_shop(spec, roads_collection)` |

Every asset has a description, the author "Mert Road Studio", tags and a rendered thumbnail. The catalog IDs
are stable UUIDv5 values, so rebuilding the library keeps catalog membership.

## Verification
The test runs in two processes:
1. **Build:** loads the library builders, makes the assets, renders the thumbnails, packs the images and saves.
2. **Fresh file:** a separate `--factory-startup` process:
   - opens the library and checks catalog IDs against the catalog file, descriptions, previews of at least 128 px, and that no image is external;
   - resets to an empty file and appends every asset, which must evaluate to geometry;
   - changes parameters: urban road lanes 1 to 3, sidewalk to 5 m, right cycleway to Protected; footbridge style Girder to Truss;
   - checks that the generated geometry follows.
