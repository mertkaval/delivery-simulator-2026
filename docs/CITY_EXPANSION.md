# Residential expansion — 2026-09-16

The playable footprint is now 240 × 780 metres (previously 150 × 330): 3.78 times the area. Cedar Lane extends north through Maple Avenue, Oak Gardens and Northwood Lane. Two parallel residential roads and four cross streets connect the new blocks. There are 36 delivery destinations, 24 additional exterior houses, and the existing furnished starter home. Three restaurants and the original six-car traffic circuit remain operational.

## Houses

`world/build_residential.py` builds three original Blender exterior models: sage siding, a taller roof with brick wainscoting, and a lower roof with timber shutters. Details include closed gables, layered siding, recessed window assemblies, linen edges, sills, casing, attic vents, shingle courses, fascia, gutters/downspouts, masonry chimneys, raised door panels, porch columns/railings/deck boards and light fixtures. Godot adds address signs, fences, mailboxes and planting beds. Shared procedural materials provide siding, timber, masonry and roof surface detail.

Editable sources are in `world/residential/source/house_0.blend` through `house_2.blend`. That folder has `.gdignore`; Godot imports the adjacent GLBs, so playing the project does not require Blender. Regenerate with Blender's `--background --python world/build_residential.py`, then reimport in Godot.

The delivery houses remain exterior-only, with simple building/post collision and existing doorstep interactions. Only the starter house has a furnished walkable interior. Traffic still uses its original southern circuit; this change does not introduce a city-wide traffic simulation.

## Integration and verification

The original twelve address indices are unchanged. New destinations append to the list, preserving existing orders. Route calculations include all 36 door locations; the minimap includes the expanded footprint and side streets. Player and bicycle save limits allow the northern extension.

Repeated box details are instanced by material and city block while their physical bodies remain in place. In the same captured house view, measured draw calls fell from 4,267 to 1,620 (62% reduction). This is a view-specific measurement, not a guaranteed frame rate.

Verified with Godot 4.7.2 Forward+ / D3D12 on the RTX 3070 Laptop GPU:

- Economy smoke and dispatch tests passed.
- General regression: 25 checks, zero failures.
- Expanded city: 165 checks, zero failures, including all 36 physical door interactions, restaurant/traffic behavior, catalog alignment, intersection clearance and northern save positions.
- Starter home: all 11 integration checks passed.
- Native renders inspected at `tmp/house_detail.png`, `tmp/oak_house.png`, `tmp/maple_street.png` and `tmp/expanded_city.png`.

The geometry and surface detail improve realism, but the environment remains stylized procedural game art, with prototype vegetation and commercial buildings.
