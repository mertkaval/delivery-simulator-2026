# City Road Maker 2.1, reverse-engineered into Mert Road Studio

Source: "How to Use City Road Maker 2.1 – Full Blender Tutorial" (3Dz, 2025-12-18, 43:12, YouTube `4XV2aqDHDtY`,
recorded in Blender 5.0.0). Retrieved 2026-10-29: title, description, chapters, auto captions, the 1080p stream
(`evidence/video_metadata.json`).

The tutorial demonstrates a road kit built as geometry-nodes assets. Its distinctive mechanism, missing from Mert Road
Studio (MRS) until now, is the **tongue / area-junction workflow**: road ends become red (road) and yellow (roadside)
footprints, and one junction object turns every footprint in its range (roads, extensions) into a single junction
mesh. This folder documents what the video shows and reconstructs it as editable, procedural MRS node groups:

| reconstructed in MRS | file | CRM counterpart |
|---|---|---|
| MRS_Road: Tongue Start / Tongue End | `tools/roads/mrs/road.py` (frame "Tongues") | 01. CRM Road, Start / End Point Tongue Size |
| MRS_AreaJunction + MRS_RegionOutline | `tools/roads/mrs/areajunction.py` | 02. CRM Junctions |
| MRS_ExtensionMesh (square, round, island), MRS_ExtensionCurve | `tools/roads/mrs/areajunction.py` | 19. CRM Extension Mesh, 10. CRM Extension |
| MRS_CustomSign + MRS_PanelText | `tools/roads/mrs/customsign.py` | 13. CRM Custom Sign + Panel Text |
| MRS_MarkingLines + MRS_PaintLine | `tools/roads/mrs/markinglines.py` | 03. CRM Marking Lines |
| add-on panel (create, presets) | `addon/mrs_area_workflow` | (CRM uses the asset browser) |

The rest of what the tutorial shows already exists in MRS and is mapped, not duplicated: lanes, markings, parking, bike
and bus lanes, median, sidewalks, props / scatter, manholes, asphalt condition (New / Worn / Wet / Patched), sidewalk
surface, bridges (Mode Elevated: piers, barriers), tunnels (Tunnel Start / End), terrain pulled to roads (Conform +
MRS_TerrainConform), traffic lights and lane-use arrows (MRS junctions). See [UI_UX.md](UI_UX.md), journeys 9-11.

## Documents

| | |
|---|---|
| [WALKTHROUGH.md](WALKTHROUGH.md) | illustrated walkthrough: video evidence next to the reconstruction |
| [OPERATION_LOG.md](OPERATION_LOG.md) | 55 timestamped operations with frames, crops, crop bounds, evidence class |
| [CRM_INTERFACES.md](CRM_INTERFACES.md) | every CRM group interface the video shows (controls, types, defaults, evidence); the Panel Text graph and its connection table |
| [NODES_RECONSTRUCTION.md](NODES_RECONSTRUCTION.md) | the reconstruction's groups: interfaces, node inventories, every connection (generated from the built trees) |
| [UI_UX.md](UI_UX.md) | panels, conditional states, user journeys, live versus rebuild |
| [UNRESOLVED.md](UNRESOLVED.md) | what the video hides or does not show (class D) |
| [DECISIONS.md](DECISIONS.md) | inferred design decisions (class C) and Blender version adaptations |
| [VALIDATION.md](VALIDATION.md) | tests, measurements, comparison images |

Evidence classes everywhere: **A** directly observed, **B** narration only, **C** inferred (our implementation),
**D** unresolved.

## Layout

```
crm_reconstruction/
  README.md WALKTHROUGH.md OPERATION_LOG.md CRM_INTERFACES.md NODES_RECONSTRUCTION.md UI_UX.md UNRESOLVED.md DECISIONS.md VALIDATION.md
  CRM_Reconstruction_groups.blend     the groups + one working example of each (opens in a fresh Blender, 0.3 MB)
  evidence/
    index.json            55 events: time, action, result, class, frames, crops (+ bounds)
    frames/               full 1920 x 1080 frames after (and 3 s before) each event
    crops/                labelled crops (panel / view / assets / nodes) cut from the lossless frame
    panels/               212 settled Properties-editor states as strips (index.json: times, crop bounds)
    graph/                the node-graph excursion (full frames + node-editor crops)
    video_metadata.json   title, chapters, description, format
  comparisons/            video viewport (top) above the reconstruction's render of the same example (bottom)
  addon/mrs_area_workflow the Blender add-on (operators + sidebar panel + sign presets)
  build/
    events.py             the event map + frame / crop extraction
    docs.py               OPERATION_LOG.md from evidence/index.json
    reconstruct.py        the full reconstruction scene on the MRS library (examples A-G) + renders
    compare.py            comparison images
    graph_dump.py         NODES_RECONSTRUCTION.md from the built trees
    light_blend.py        CRM_Reconstruction_groups.blend
```

The downloaded video, the raw auto captions and the 1 s panel crops stay local in `tmp/roads/crm_video/` (not
committed: the author's content); the frames and crops here are the evidence the documents cite.

## Rebuild from a fresh Blender (5.2)

Prerequisites: Blender 5.2 (tested 5.2.3 LTS), this repository; for the evidence tools Python 3.12 + Pillow, ffmpeg,
yt-dlp (`pip install "yt-dlp[default]"` in a venv; the YouTube download needs a JavaScript runtime: Node.js,
`--js-runtimes node`).

1. **Just the new groups** (no MRS library): open Blender, Scripting tab:
   ```python
   import sys; sys.path.insert(0, r"<repo>/tools/roads")
   from mrs import areajunction, customsign, markinglines
   areajunction.build_all(); customsign.build_custom_sign(); markinglines.build_marking_lines()
   ```
   or open `CRM_Reconstruction_groups.blend`.
2. **The add-on**: Edit > Preferences > Add-ons > Install from Disk, the zipped `addon/mrs_area_workflow` folder (set
   "MRS tools path" to `<repo>/tools/roads` if it is installed outside the repository). 3D View > Sidebar > MRS >
   Area Junctions > Build Node Groups.
3. **With MRS roads** (Tongue Start / End need MRS_Road): build the MRS library once (`mrs.build_all()`, or
   `city.ensure_base(<path>)`, about 12 min), then
   ```
   blender --background tmp/roads/city/base.blend --python tools/roads/crm_reconstruction/build/reconstruct.py -- tmp/roads/crm_reconstruction
   python -I tools/roads/crm_reconstruction/build/compare.py tmp/roads/crm_reconstruction
   ```
4. **Evidence** (optional, needs the video): `python -I build/events.py <video.mp4>` then `python -I build/docs.py`.

Tests (headless): `tools/roads/tests/area_junction_test.py`, `road_tongue_test.py`, `custom_sign_test.py`,
`marking_lines_test.py` (see [VALIDATION.md](VALIDATION.md)).
