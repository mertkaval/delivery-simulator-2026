# Street frontage (v5)

`tools/roads/mrs/frontage.py` puts one finished shop frontage on the demonstration block. It uses the game's
existing city-kit facade modules (`world/citykit/modules/*.glb`), so the building is made of real game assets,
not a generator placeholder.

## What a frontage is
A frontage is a spec stored on the scene (`sc["mrs_frontages"]`, JSON). For the block it is
`samples.SB_FRONTAGES`:

```
{"id": "SB_Shop", "road": "SB_North", "side": "l", "along": 22.0, "bays": 4, "floors": 2, "depth": 12.0, "style": 1,
 "name": "Halden Grocer", "number": 24, "street": "Maple St", "yard_side": "ahead", "yard_width": 9.0, "drive_width": 5.0}
```

`samples.regenerate_block` rebuilds every frontage first, then syncs the driveways into the road, then runs the
rest in order: placement, ground, routes and movements. Changing the spec and regenerating moves everything
that depends on it.

| object | content |
|---|---|
| `SB_Shop` | Kit modules placed by the `district.gd::build_building` rules: storefronts and the entrance on the ground floor, apartment bays above, party-brick sides and back, roof slab, parapets, corner posts and awnings. One world-space mesh, so the Kit materials stay world-triplanar. A shop room sits behind the open kit door: terrazzo floor, plaster walls, counter and shelving. |
| `SB_Shop_Plinth` | base from sidewalk height down into the ground |
| `SB_Shop_Signs` | fascia lettering "HALDEN GROCER" (cap height about 0.34 m, 2 cm stand-off on the navy fascia) and an enamel address plate "24 / MAPLE ST" on the pier beside the door |
| `SB_Shop_Yard` | concrete service yard (`mrs_kind` drive: walked and driven). It rises from 1 cm above the dropped kerb to floor level at the back, has metre UVs and a yellow loading box. |
| `SB_Shop_RollerDoor` | 3.2 x 3.4 m roller shutter with guide rails and coil box, plus a "DELIVERIES 24" panel |
| `SB_Shop_Downlight0..3` | warm 3000 K spot lights under the fascia. They are real light records and switch on with the street lights. |
| `MRS_Entrance_SB_Shop` | entrance anchor 0.7 m in front of the door; the delivery destination (`mrs_destination` JSON) |
| `MRS_Driveway_SB_Shop` | service-access anchor at the yard mouth (`mrs_width`, `mrs_yard`) |

## Rules that read the anchors
- **Entrance envelope:** a 2.4 m wide strip from the door to the kerb that nothing optional may enter. An entrance on the sidewalk gets no separate access path; the old one lay coplanar on the paving.
- **Driveway:**
  - `frontage.sync_driveways` writes each `MRS_Driveway_*` anchor's station, side and width into the road's `Driveways` input, a point cloud read by Geometry Nodes.
  - The road drops the kerb to 4 % of its height, which is 6 mm.
  - The planting strip, slab and kerb faces over the drop become a concrete apron (kind 11).
  - The flat part is widened by half a station step so at least the requested width is fully dropped at any resolution.
  - Placement keeps the driveway width plus 2 m clear.
- **Building footprints:** the building and its yard are keep-out areas for landscape, trees and furniture. A 1.6 m active-frontage strip in front of the facade keeps cabinets, bins, planters, information boards and hydrants away from the shop windows.
- **Bike parking:** an entrance with `mrs_bike_parking` attracts a rack 5-13 m away in the furniture zone. Generic racks keep 25 m from it.
- **Bus stop:** `S2` on the shop side of Maple St, about 26 m from the door. Its pole steps back along the boarding area when a sign already stands at the front.
- **Vehicle access:** `movements.py` adds `access_in` (kerb-side lane into the yard, 4.6 m minimum radius) and `access_out`. Both are swept with the car footprint on road, apron and yard surfaces only.
- **Routes:** the entrance is a pedestrian-graph node. The Godot loader adds a `Marker3D` per destination in the group `mrs_destinations`, with name, address, door, entrance, service driveway and yard as metadata.

## Godot
- Surfaces whose material name starts with `Kit` get `CityKit.material(name)`: the same triplanar PBR sets and window shader as downtown.
- `MrsStreetLights.set_night` also drives the window shader's `night` parameter, so the shop windows light up with the street lights.
- The GLB carries flat `<Kit>_Engine` stand-ins, not the textures.

## Tests
`street_block_v4_test.py`, frontage section:
- **Baseline:** destination present, no placed item inside the entrance or driveway envelopes, rack within 13 m, kerb at the driveway under 3 cm and 10 m away over 12 cm, both access movements clear.
- **Rules adapt:** the shop moves to station 14 and the driveway, envelopes, rack and kerb drop follow. Restored to 22, the object count is unchanged.
