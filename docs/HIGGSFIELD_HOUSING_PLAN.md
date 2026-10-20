# Higgsfield modular housing — 2 October 2026

Scope: replace the 36 ordinary delivery houses and 24 side-street houses with exterior-only modular residences. Preserve every delivery ID, doorway coordinate, approach path, street and downtown asset. Preserve the separate playable Cedar starter home and its rest interaction.

Production: Higgsfield 3D Jutsu project 40e06765-d85d-471a-9f4a-3cf2d6c9e567. Build a 2 m bay / 2.8 m storey kit with closed window and door bays, masonry/stucco/siding, foundation, cornice, rainwater goods, three roof forms, porch/canopy, shutters, flower boxes, lighting and utilities. All new geometry and packed texture generation runs in Higgsfield; local Python is retained only as the remote job source.

Integration: deterministically assemble varied footprints, floors, materials and facade details within existing lots. Share meshes/materials; merge static parts per house variant and material where practical; retain automatic mesh LOD and distance culling. Closed exterior collision must match each footprint without blocking doorstep access.

Verification: inspect Higgsfield renders and Godot street views, test all 36 delivery doors and closed house collision, run existing city/gameplay regressions, measure geometry/draw cost, and compare the complete world/downtown file hash manifest with the before snapshot.
