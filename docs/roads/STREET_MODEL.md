# Shared street model and export format (Road Studio v3)

`tools/roads/mrs/street_model.py` — `collect(roads_collection)` builds the model from the authored
roads (curve + `MRS_Road` modifier inputs remembered in `object["mrs_inputs"]`) and the junction
objects (`object["mrs_junction"]`). `export.export_block(path, collection)` writes:

| file | content |
|---|---|
| `<name>.glb` | evaluated road + junction + structure meshes (Y-up, metres), metre UVs, materials |
| `<name>_collision.glb` | only drivable / walkable kinds (asphalt, concrete, structure, embankment, paving, tactile, crossing, bus) |
| `<name>_props.glb` | rule-placed props as named nodes `<road>_<kind>_<side><i>`; trees use the `_LOD1` meshes |
| `<name>_signals.glb` | signal poles, each head a child node `<id>_head<i>`; lens materials `MRS_Lens_<Red/Amber/Green/PedRed/PedGreen>` with `KHR_materials_emissive_strength` |
| `<name>.json` | the model below |

## JSON (Z-up Blender coordinates; the GLBs are Y-up: x, y, z -> x, z, -y)
```
version, units ("m"), axes
roads[]: id, name, preset, length, points[], driving_side, lanes_forward, lanes_backward, lane_width,
         transition {enabled, forward_end, backward_end, start, taper}, shoulder, median,
         parking {l, r}, cycleways {l: {kind, width, buffer}, r}, sidewalks {l: {on, width, planting}, r, curb_height},
         half_widths {l, r}, seed, trims {start, end}, ramps {start, end},
         lanes[]: id, dir (forward|backward|both|none), type (drive|bus|bike|parking), width, offset (m, right +), kind (bike)
         lane_paths[]: lane fields + points[] (world polyline in travel direction, 3 m stations)
         ped_paths[]: id, side, points[] (sidewalk centre line at curb height)
junctions[]: id, type (junction|roundabout|dead_end), at, z, control (none|signals|stop|yield|priority), roads[],
             approaches[]: road, end, heading, trim, lanes_in, lanes_out, half_l, half_r, main
             crossings[]: id, road, end, from, to (curb to curb), style (zebra|parallel), refuge
             signals[]: id, controls_road, approach, phase, pedestrian_crossing, position, heading
             signal_phases[][]: approach indices that are green together (opposite approaches share a phase)
validation[]: {level, road|junction, message}   — short tapers, tapers near junctions, close junctions
placement_report: counts, by_kind, skipped[] (road, kind, along, reason)
export: file names, lens material note, stats (tris, bytes, counts)
```
Lane identities through a transition: lanes are numbered from the centre (`index_from_centre`); a taper
adds or removes the *outermost* lane of a side, inner lanes keep their id and offset; the merge arrow is
placed on the dropped lane.

## v4 additions to the JSON
```
godot_axes      "Blender (x, y, z) -> Godot (x, z, -y); yaw_godot = yaw_blender"
trees[]         name, species (assets/landscape/<species>.glb), pos, yaw, scale, source, road
plants[]        id (garden / yard kit node: grass_a/b, shrub_a/b/c, boxwood_ball, hedge_section, ...), pos, yaw, scale, region
lights[]        mrs.lighting.light_records(): id, parent, library, class, type (spot|omni), position, direction,
                color, energy (Godot), range, spot_angle, shadow, fade_begin, fade_length, ...
night           night sky / moon parameters matching lighting.night_setup()
footbridges[]   footbridge plans (status, messages, deck_z, rise, span, clearance, supports, footprint, ped_edges, lights)
routes          {ped: {nodes, edges}, bike: {nodes, edges}, validation[], stats}
                ped edge kinds: sidewalk (width = measured usable clear width), corner, crossing, ramp (kerb ramp,
                tactile), boarding, path, park_path, path_join, entrance_path, footbridge_stairs / _ramp / _deck,
                ring_sector, bulb_ring, through_path; bike: cycleway, bike_crossing, bike_turn, mixed_traffic,
                shared_path, through_path, footbridge_ramp, footbridge_deck, dismount_link
items[]         every placed item: name, kind, lib, road, side, along, pos, yaw, scale, foot (corners), access, flush
```
Roads in `<name>.glb` carry engine masks for `world/roads/mrs_road.gdshader`: `COLOR_0` = (inside a traffic
lane, curb-dirt band, gutter / drain wetness, 1) and `UV2` = (lane width, half median); `UV` stays
(lat, along) in metres. COLOR_0 is data, not colour: the loader sets `vertex_color_use_as_albedo = false`
on the imported road materials.

Godot (v4): `world/roads/mrs_street_block.gd` (`MrsStreetBlock.build(dir, "street_block")`) loads everything:
road shader, trimesh collision (double-sided), props, per-signal lens control (`set_phase`, `set_signal`),
trees / plants through `CityLandscape` (MultiMesh LOD0 / LOD1 / impostor, the shared wind + alpha-scissor
foliage shader), street lights through `MrsStreetLights`. `tests/capture_street_block_v4.gd` verifies it.

Godot (v3): `tests/capture_street_block.gd` loads the four GLBs + JSON, checks scale / collision, toggles the
green lens emission and captures views (`godot --path . --script res://tests/capture_street_block.gd -- <export_dir> <out_dir>`).
Signal control in the game = set `emission_enabled` / `emission_energy_multiplier` on the lens materials
of a signal node per `signal_phases`; that is the engine's job, not a Blender animation.

## v5 additions
- `movements`: `lanes`, `movements` (junction turns plus `access_in` / `access_out` for driveways), `bike_movements`, `validation` and `stats`. Every path is swept on the real surfaces, with a minimum radius.
- `destinations`: delivery destinations, one per shop entrance:
  - `id`, `kind`, `name`, `address`, `road`, `side`, `along`;
  - `door`, `facing`, `entrance`;
  - `service` (`driveway`, `yard`, `width`);
  - `building`, `kit_modules`.
  - The Godot loader adds a `Marker3D` per destination to the group `mrs_destinations`.
- `frontages`: building records (`footprint`, `width`, `depth`, `height`, `floors`, `style`, `kit_modules`).
- Surface kind **11 (apron)**: dropped-kerb driveway apron and service yard, walked and driven. Kind 10 is the footbridge (movements only).
- `ground` / `ground_files`: the landscape ground mask and tiles (`ground.py`, `mrs_ground.gdshader`).
