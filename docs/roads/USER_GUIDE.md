# Mert Road Studio: user guide

Mert Road Studio (MRS) builds roads, junctions, markings, signs, signals and street assets procedurally in Blender
5.2. You draw curves and set parameters; the tool derives everything else. The workflow (chosen 2026-10-29):

1. Build the layout in Blender. Everything stays live and editable.
2. **Validate** in Blender. The validator lists every mistake; nothing goes further while it lists one.
3. **Export** to Godot. Godot only imports: it adds no fixes and no logic. If something is wrong in Godot, the tool is
   wrong and gets fixed, never the game.

## 1. Setup (once)

1. Install Blender 5.2.
2. Install the add-on: Edit > Preferences > Add-ons > Install from Disk, then pick the zipped folder
   `tools/roads/addon/mert_road_studio`.
   - Set **MRS tools path** to `<repo>/tools/roads`.
   - Set **Library file** to `<repo>/tmp/roads/city/base.blend`.
3. 3D View > Sidebar (N) > **Road Studio** tab > **Open Library as New Project**. This opens the MRS library (every
   node group, material, sign, signal, tree and prop). Save it under your own name and work in that file.
4. If the library file is missing or out of date, **Build Library** rebuilds it (about 13 minutes). The library
   carries a version number (`city.BASE_VERSION`); a mismatch is rebuilt on its own.

## 1a. Examples (start here)

**Road Studio > Examples > Load Example** builds a finished scene in a scene of its own. Look at how it is made,
change its parameters, or copy its roads into your own scene:

| example | what it shows |
|---|---|
| Street Block | the demonstration block: avenue with a lane taper, bus stop, footbridge, S-curve, T junction, furniture |
| City Block | avenues with cycle lanes and parking, a residential grid, signalised junctions, a dead end, a gantry |
| Mountain Road | a winding road on hills: embankments, cuts, a tunnel, a service branch |
| Highway | a dual carriageway with guardrails and banking, an overpass |
| Roundabout Village | a four-arm roundabout, village streets, a bus stop |
| Bridge Valley | a cable-stayed bridge between two mountain road sections |
| Area Junction Crossing | the tongue workflow: four roads in tongues, one area junction, a round plaza extension, a custom sign, marking lines |

Every example validates with no problem (`tools/roads/tests/examples_test.py` checks this), so each one is a known
good starting point.

## 2. Roads

- **Add Road** (Residential, Urban, Highway, Rural, Service, Bridge) puts a road at the 3D cursor. With a plain
  curve selected, it turns that curve into a road.
- **Shape:** Tab into edit mode on the road and move, extrude or delete points. Never scale or rotate a road in
  object mode.
- **Everything else** is in the road's **Modifier** panel, grouped:
  - **Profile:** lanes, widths, transitions, parking, median, kerbs, sidewalks, crown, banking.
  - **Cycleway**, **Markings**, **Structure** (bridge / tunnel), **Roadside** (lights, trees, props, spacing,
    Object Clearance), **Scatter**, **Materials** (Asphalt Condition, Sidewalk Surface).
  - **Junction:** set by junctions; you only set Tongue Start / End there.
- **Limits.** Every numeric input is limited to the range the limit tests proved safe, with a safety margin. The UI
  cannot go outside it. The ranges and their evidence are in [LIMITS.md](LIMITS.md).
- **Combination warnings.** Two inputs that are fine alone but not together (for example a bend tighter than the
  road's own width) show a warning on the modifier, and Validate reports them.
- **Presets.** Selected roads > preset applies a whole profile. **Material Preset** sets the look of every material
  at once.

## 3. Junctions

There are two kinds, and both can be used in one scene.

### Rule junctions (the default)

Select the roads whose ends meet, place the 3D cursor at the meeting point, then click **Connect Roads at Cursor**.
The junction derives from the roads' own parameters:

- trims and corner pieces
- crossings and ramps
- stop lines, STOP letters and give-way teeth (from its control: signals, stop, priority, yield)
- turn arrows for each lane
- mast arms with one signal head per lane, and arrow heads for turn-only lanes
- lane-use signs, cycle crossings and the yellow box

**Junction Settings** changes the corner radius, crossing, control or box and rebuilds. With **Auto: on**,
editing a road rebuilds its junctions. Use **Roundabout at Cursor** and **Dead End at Cursor** for those layouts.

The builder **refuses** two kinds of layout, with a message saying what to change:

- **Neighbouring roads closer than the minimum angle.**
- **A road too short for this junction's trim plus the paint zones of both its ends.** Two junctions too close
  would paint over each other. Lengthen the road or widen the angle.

### Area junctions (tongues)

This workflow is reconstructed from City Road Maker 2.1 (`tools/roads/crm_reconstruction`).

1. Select the roads, then click **Set Tongues** (Start / End, default 10 m). Their ends become red (road) and yellow
   (roadside) footprints.
2. Place the 3D cursor where they meet, then click **Area Junction at Cursor**. The selected roads move into a
   **Roads** collection, and everything in **Range** becomes one junction with rounded kerb corners.
3. **Extensions** add free-form road areas: Square (bus bay, car park), Round (cul-de-sac, roundabout ring), Curve
   (a lane), Island (a roundabout's raised centre). Put one in the junction's area at the roads' level, then scale
   it in edit mode.
4. **Marking Lines at Cursor** paints lines along a curve. Add an Array modifier for parking bays.
5. On the junction: **Show** off shows the tongues again. **Range** off uses the junction object's own mesh as the
   area (scale its cube in edit mode). **Inner Radius** and **Outer Radius** round the corners.

Rules the tool enforces:

- Overlapping tongues merge.
- Gaps the tongues enclose are filled as road.
- An extension's roadside never covers a road.

## 4. Terrain, bridges, tunnels

- **Use Active as Terrain** (a mesh), then **Pull Terrain to Roads**. The terrain is cut and filled to the roads with
  batters: 1:1 cut, 2:1 past 6 m deep, 1:2 fill.
  Beside a road the terrain takes the height of the road surface nearest to it in plan, so on a steep street in a cut
  it meets the kerb beside it, not one uphill.
- **Bridge:** set the road's **Mode** to Elevated. Piers, barriers and deck come from the road's Structure inputs.
  A pulled terrain stays at least **Deck Clearance** (2 m) under an elevated deck, and beside a deck it stays under
  the cut batter from the deck, so a hill or an abutment never rises through a bridge or over a low deck's edge.
- **Tunnel:** set **Tunnel Start** and **Tunnel End**.

## 5. Street assets and signs

- **Place Street Assets** puts signs by junction control, speed signs, street names, bus stops and furniture.
  With **Auto: on** it re-places after edits.
- **Street trees** (Place Street Assets) stand in a square guard of steel posts and rails, sized to their bed: in a paved
  sidewalk on a tree-pit grate, in a planting strip of 1.2 m or more inside a square concrete edging with a soil bed, in a
  narrower strip on a mulch ring. The tree reserves its whole surround: benches, lights and signs keep clear of it. A
  tree is only planted where its whole bed lies on the surface (never hanging past a strip's end). Only species whose
  trunk stands straight are used: the placer measures each tree model's trunk lean (bark rings near the ground against
  rings up the trunk) and skips a species leaning more than 12 degrees.
- **Driveways.** Nothing optional (benches, bins, trees, lights) is placed across a road's driveways (its Driveways
  input, the dropped kerb and apron), whether they come from MRS_Driveway anchors or straight from a city plan.
- **Slopes.** Posts, poles, signs, hydrants and trees are set into the ground at the lowest point under them; benches,
  bins and racks only go where the ground rises at most 10 cm across them (measured on the road and junction surfaces,
  else the placer tries the next spot); bus
  shelters and utility cabinets stand on a level concrete plinth that reaches down to the slope.
- Roadside lights, trees and props come from the road itself (Roadside inputs). Their placement follows four rules:
  - Every object stands on the surface below it.
  - Lights win over trees, and trees win over props, within **Object Clearance**.
  - Scatter keeps half that distance from them.
  - Gullies and manholes stay on the carriageway.
- **Flush items** (drain grates, manhole covers) lie on the surface plane under them: the placer samples the road
  and junction surfaces at their corners and tilts them to the cross-fall and grade, so they sit neither under nor over
  the asphalt. A spot steeper than 1:4 is skipped.
- **Bus stop text** ("BUS STOP" on the carriageway) goes in the outermost traffic lane and is scaled to fit that lane's
  width less 0.3 m each side.
- **Custom Sign at Cursor** places a live parametric sign: panel shape and colour, border, post, nine text slots,
  images, lines. Edit it in its Modifier panel.

## 6. Validate (always, before export)

Click **Validate** in the panel. Every problem is listed with the object and what is wrong. A clean scene shows
**ok**. The checks:

| check | what it means |
|---|---|
| paint_clear | road paint inside a junction's crossing / stop zone |
| arrow_kind, arrow_count | a turn arrow showing the wrong movement, in the wrong lane, or missing |
| end_inputs, end_marking | a road's junction-derived inputs or end marking do not match its junction |
| bike_on_zebra | a cycle band or road paint on a pedestrian crossing |
| signal_lanes | a missing mast arm, or a head / lane-use sign / arrow head not matching a lane |
| speed_sign | a speed sign not showing its road's speed limit |
| overlap | two roads or junctions covering the same ground |
| trimmed_away, junction_zones | a road eaten by its junctions, or two junctions so close their paint meets |
| limit | an input set outside its tested range by a script, or inside a forbidden gap |
| warning | a combination warning on a modifier (see below) |
| tongue_uncovered | a road tongue no area junction covers (out of every junction's range): a hole at the road's end |
| placed_conflict | two placed objects overlapping (bases, pads, mulch beds) |
| placed_road | a placed object other than a drain or cover standing on the carriageway |
| placed_ground | a placed object floating over or sunk into the surface under it (more than 5 cm) |
| placed_building | (cities) a placed object inside a building |
| building | (cities) a building standing on a street |

**Combination warnings.** Some inputs are fine alone but wrong together. The modifier shows a warning (and Validate
reports it) when:

- a bend is tighter than the road's outer half width allows (the inner side would fold over itself);
- an input lies in a forbidden gap between two passing ranges (for example a parking strip too narrow to park in);
- a sign's text, image or line reaches beyond its panel (depends on the panel's size, shape and corner rounding);
- a centre or lane line of Marking Lines lies outside its Road Size.

Nothing is corrected for you: the warning names what to change.

Never export with problems: fix the parameter the message names.

## 7. Export to Godot

- **Single scenes:** **Make Export-Ready Meshes**, then **Export GLB (+ collision)**. Put the GLB in the Godot
  project and reimport (`Godot --headless --path . --import`).
- **A whole city** (Port Halden): run `bash tools/cityforge/build.sh tmp/cityforge_roads`. It builds the streets,
  terrain and water, writes the map file, and validates everything in Blender. It installs into Godot only when
  validation is clean, then reimports and runs the Godot checks.
- **Ground next to a street.** The game's ground is a 4 m height grid. Under a street it lies 0.3 m below the
  surface; at a grid point next to a street it stays between 0.15 m and 0.75 m under the street's extended plane.
  That keeps the ground at any street edge inside the 1.2 m edge skirt, so cut and fill batters start one grid cell
  out and no gap opens under a sidewalk.
- **In the game.** Port Halden plays the roads-only city by default (main menu: "New streets, roads only"). The
  Godot test suite (`tests/run_tests.ps1`) runs the Port Halden tests on both builds: the classic city and the
  roads-only city.

## 8. When something is wrong

1. Validate in Blender first: the message names the object and the rule.
2. If Blender is clean but the result is wrong in Godot, the tool is wrong at that point: report it, do not fix it in
   the game.
3. Limits and rules come from tests. `tools/roads/limits/` holds the sweeps; `docs/roads/LIMITS.md` holds the
   evidence for each value.
