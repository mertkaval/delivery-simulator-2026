# Downtown implementation

The original neighborhood is joined to a nine-block downtown through four east-west connectors. Ninety parcels contain 87 mixed-use buildings, a parking structure, a construction site and a plaza. Four towers rise above the mid-rise street wall. Developed footprint coverage is 77.33% of 87,696 m²; service alleys are eight metres wide. Building frontage is arranged around connected roads, sidewalks, alleys and courtyards.

The Blender urban workshop adds 82 modular sources and 164 near/far GLBs: architectural bays, storefronts, entrances, roofs, balconies, service details, street furniture, signals, markings and interior modules. Instancing groups surfaces by material, mesh and 64 m spatial cell. Near facades transition to simpler modules and distant window proxies; solid building cores provide occlusion. Asphalt, brick and timber reuse the recorded PBR texture library.

Five additional pickup points and five destination categories exercise street counter, rear service access, grocery, alley pickup, apartment lobby/unit, office reception, hotel and construction delivery. Original destination IDs remain the first 36 entries. The dispatch system selects the new downtown set when the courier works in that area. All ten pickup/delivery interaction rays and generated delivery paths are checked in `tests/downtown_gameplay.gd`.

The later living-city pass adds the civic district, skinned population, vehicle fleet and landscape described in [LIVING_CITY_REPORT.md](LIVING_CITY_REPORT.md). The latest code and measurements supersede the earlier 16 September project overview.

Before/after measurements are retained in `tmp/downtown_before_metrics.json` and `tmp/downtown_after_metrics.json`. The baseline includes empty terrain where the new city now stands, so it is a capacity comparison rather than an equal-content optimization comparison. Several final entrance camera targets were corrected to the actual entrances during validation. Fourteen pedestrian/vehicle-height views and seven civic views are captured separately from the HUD; gameplay/phone/night views are separate checks.

Rebuild urban sources with Blender `--background --python world/downtown/build_urban_kit.py`. Run Godot editor import before the tests. Do not rerun the original workshop as an upgrade step: new work is additive, and all 75 original source/runtime asset hashes remain unchanged.
