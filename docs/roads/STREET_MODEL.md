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

Godot: `tests/capture_street_block.gd` loads the four GLBs + JSON, checks scale / collision, toggles the
green lens emission and captures views (`godot --path . --script res://tests/capture_street_block.gd -- <export_dir> <out_dir>`).
Signal control in the game = set `emission_enabled` / `emission_energy_multiplier` on the lens materials
of a signal node per `signal_phases`; that is the engine's job, not a Blender animation.
