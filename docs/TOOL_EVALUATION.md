# Tool evaluation for the city and character pipeline (2026-10-28)

Every tool was installed in an isolated Blender 5.2.3 profile (never the everyday Blender) or a
throwaway Godot project, its code reviewed before running (network, subprocess, eval), and
exercised headless by a test script. Test scenes, renders and logs live outside the repo (session
scratchpad `tools_eval/`). Licences: build tools under GPL/LGPL are fine as long as they are not
shipped and their code is not copied into ours; generated assets are ours.

| Tool | Licence | Result | Verdict / how it is used |
|---|---|---|---|
| **Procgen Maps** | GPL-3 | Whole grey-box city in 2-48 s | Ideas only (zoning, signage rules, instanced props) |
| **Procedural Building Shell Generator** | GPL-3 | Shells with real openings, 0.02 s per building | Candidate base for shop / apartment shells in the culture districts |
| **Building Tools** (ranjian0) | MIT | Houses 0.15-1.2 s, 1.6-3.5k tris; a 14-storey tower took 77 s (each window re-processes the mesh) | Offline house-variant catalogue later; not for towers. CityForge's own kit (`tools/cityforge/kit.py`) covers the first 8 house types |
| **Driving Scenario Creator** | GPL-3 | Lane-accurate roads, OpenDRIVE export | Reference for lanes and junctions |
| **MRoadGen** | CC0 | Beautiful roads in Blender, but ~70 tris/m, one huge mesh, Blender-only materials, no lanes | Optional, for special pieces (overpasses) |
| **Godot Road Generator** (TheDuckCow) | MIT | Runs on 4.7.2: 7 junctions + 24 segments in 44 ms, 140 traffic lanes with turn lanes, bakes to GLB | **Next: traffic lanes for Port Halden** from the CityForge road graph (nodes -> intersections, edges -> road points) |
| **City Generator / MapGenerator** (ProbableTrain) | LGPL-3 | Run headless and seeded in Node (`tools/citygen`) | Tensor-field plans for the future culture districts |
| **BlenderGIS** | GPL-3 | Works with workarounds; downloads a native DLL at start (blocked); roads without width; DEM import crashes on NaN | Coordinate / GeoTIFF helper only |
| **Blosm** | GPL | Best OSM + terrain importer (roads with width, draped), offline re-import 0.4 s; TLS checks off; flaky Overpass | Reference scenes only. **Ship no OSM geometry** (ODbL share-alike, real addresses): use real areas for statistics and look-dev |
| **NodeToPython** | GPL-3 | Node trees -> Python, verified identical | Keeps geometry-node generators as code in git |
| **Rokoko Studio Live** | LGPL-3 | Retargeter works headless after two Blender-5 fixes; stock mode pushes arms into the torso, fixed with a pose-match step; Mixamo jog -> courier 52/52 bones | **Use** as the retarget stage for outside clips (UAL2, Mixamo, mocap) |
| **Procedural Multi-Rig (Procedural Walk)** | GPL-3 | Knees never bend, pelvis floats, arms swapped; idle floats 6 m up | Don't use; our clips are far better |
| **FreeMoCap** | AGPL-3 | Not installed: ~1 GB of unpinned dependencies, telemetry on by default, kills the process on port 8005, installs into the user's Blender | Later, optional: 2-3 webcam capture of custom role actions, then Rokoko retarget |
| **MPFB** | GPL-3 (assets CC0) | In use: the courier and 37 townspeople | Keep |
| **Blender MCP** | - | In use: live Blender previews | Keep |
| **Node Wrangler** | GPL (bundled) | Interactive node-editing helper | Use by hand; nothing to automate |
| **SideFX Labs** | SideFX | Needs Houdini (Apprentice is non-commercial) | Not now |
| **OpenRW** | GPL-3, needs GTA III data | Not installed | Design ideas only (streaming, traffic paths); no code copied |
| **re3** | DMCA'd reverse-engineered code | Declined | Not used |

## What was built from this (CityForge)

`tools/cityforge/` generates Port Halden: a fictional Vancouver/Burnaby-like city with real
topography (hills, a lake in a park, a river with bridges, a harbour, a peninsula downtown on a
rotated grid, a diagonal arterial), Burnaby-style fenced lots with lanes and garages, shop strips
on the arterials, towers, public buildings, parks and full street furniture. See
`tools/cityforge/README.md` and `CITY_GENERATION_PLAN.md` section 5.
