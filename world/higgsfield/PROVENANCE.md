# Higgsfield bicycle — 2026-10-02

Created exclusively through the connected Higgsfield 3D Jutsu service.
Project: https://higgsfield.ai/3d-jutsu/2c43d2a1-c03a-4aaf-ba31-09d733cc1c1c
Delivered revision: 5. GLB: 517,812 bytes. Editable source: source/courier_bicycle.blend.
No local Blender or alternative generation service was used for this bicycle.

The remote scene contains a metric commuter bicycle with enamel frame, 32 spokes per wheel, disc rotors, cassette, crank, chain, mudguards, luggage carrier, saddle, cables and reflectors. Higgsfield batched 340 bicycle mesh objects into four meshes with 24,744 triangles. Wheelbase: 1.10 m; tyre radius: 0.35 m.

Godot adapter extracts only the bicycle, excludes studio floor/cameras/lights, aligns forward to -Z and preserves two correctly oriented wheel pivots. CityAssets' bicycle entry now supplies this model to the player and cyclists. Godot import generates mesh LODs; existing distance culling remains active. Original bicycle files remain available unchanged.

Verification: Higgsfield Cycles preview, final Eevee preview and Godot render inspected. tests/higgsfield_bicycle.gd passed 15 checks for provenance, mesh count, scene isolation, dimensions, wheel axes, mounting and dismounting. tests/lifestyle_test.gd passed 71 checks. Both final logs contain zero errors. Godot meshes/generate_lods=true confirmed. This is a detailed procedural model; its chain is simplified and the crank/pedals do not yet animate. No claim of photogrammetric realism or a completed mechanical simulation.
