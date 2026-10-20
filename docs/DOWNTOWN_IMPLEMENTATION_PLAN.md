# Downtown implementation plan — 16 September 2026

This plan is written before downtown runtime changes. The brief in the supplied attachment is the acceptance baseline. Work proceeds through a single representative block before district replication.

## 1. Audit and diagnosis

The existing 240 × 780 m map contains 60 detached exterior houses plus the furnished starter home, three restaurants, four apartments, eight parks, four shops, grass meadows and arterial/side roads. Most occupied lots are detached with large setbacks, front/side gardens and open land behind them. Commercial buildings are isolated. Apartment height alone does not produce a street wall. There is no connected downtown alley grid, podium hierarchy, transit frontage or parcel-use allocation.

Code inspection estimates existing building footprints at approximately 8,000 m² (about 4% of the total playable footprint; this is an estimate, not a surveyed parcel ratio). The current map's open ground and 259,379 grass clumps dominate long views. New downtown parcels will be measured from explicit footprint/use polygons, with separate building coverage and developed-land ratios.

Existing scene: `app/app_root.tscn`; runtime environment: `world/neighborhood.gd`. `systems/session.gd` owns dispatch, ledger, inventory, needs and save validation. `actors/player.gd` owns walking/riding and interaction rays. `CityCatalog` supplies destinations/routes. `CityAssets` caches imported meshes/materials. Traffic and people use scripted local paths, not navigation meshes. Layer 1 is world/vehicles, layer 4 is people. Save coordinates permit ±800 m. No existing occlusion culling system is enabled.

Renderer: Forward+ / D3D12, 4× MSAA, SSAO, directional shadows, unshadowed secondary lights, procedural sky. Imported GLBs generate LODs/shadow meshes. Static repeated meshes are instanced by block; grass renders only within 48 m. Existing warm world-only 720p median frame intervals are 3.18–5.30 ms, p95 7.60–8.57 ms. A dedicated before/after audit will additionally record material count, texture memory, static/physical object counts and navigation cost.

## 2. Preservation and reuse

Preserve every existing model/source, original scene, delivery address ID, pickup ID, player control, ledger/save command and test. Add the downtown as an independent child district with narrow catalog/render/map integration hooks. Extend existing content tables instead of substituting a new delivery system. The original neighborhood becomes the low-rise transition into downtown; connections use the existing cross streets. Existing saved order indices remain valid.

Reuse the bicycle, five car variants, scooter, articulated citizens, restaurant furnishings, shops, trees, benches, planters, lamps, equipment, PBR textures, sky, batching helpers and starter home. Keep original Blender sources intact. New Blender work is isolated in `world/downtown/` with its own manifests and naming.

## 3. New modular kit and art direction

Contemporary Pacific Northwest: muted brick, pale concrete, charcoal metal, timber accents, blue-green glazing, warm occupied windows and restrained storefront colors. Original architecture; no copied landmark buildings.

Use a 4 m structural bay, 4.2 m ground storey, 3.2 m upper storey, metre scale, façade origin at ground/front, consistent positive-Z frontage, and 2 m half-bays when needed. Create interchangeable storefronts, apartment/office windows, blank/party walls, corner returns, lobby/restaurant/garage/loading entrances, parapets, HVAC, fire escapes, balconies, awnings, conduits and rear façades. Add parking-structure modules, road/sidewalk/curb/ramp/marking modules, construction/retaining elements and the requested street/service/transit props. Editable Blender sources, UVs, two authored mesh-detail tiers plus engine LODs, shared material palette and collision metadata are mandatory outputs.

## 4. Proposed district geometry

Place the downtown east of the existing neighborhood, within current save-coordinate limits, connected at the existing cross streets. Street axes x = 144, 252, 360, 468 m; cross streets z = -258, -398, -538, -678 m. Nine blocks have 108 × 140 m centre-line dimensions, with approximately 84 × 116 m buildable parcels. Existing x=64 cross streets extend east to the new network. The first benchmark block is bounded by x144/252 and z-258/-398.

Main avenue x252: four 3 m travel lanes, selected 2 m curb loading/parking strips, protected bike treatment only where width permits, and 3–4 m sidewalks. Secondary/local streets: two 3 m travel lanes, selected 2 m parking strips, 3 m sidewalks. Junction crossings, curb cuts and stop lines must fit these widths. Each appropriate block has a 6–8 m service alley. Pedestrian routes remain at least 1.8 m clear. Buildings normally sit 0–2 m behind the sidewalk, never more than 4 m without a programmed setback. Curved existing roads remain as the residential transition.

Target 75–90% developed parcel area, reporting building footprints separately from paved/service/landscaped use. Continuous party-wall street frontage; every remainder is assigned to alley, court, loading, parking, plaza, construction or pocket park. Target building count mix: approximately 20% 1–3 storeys, 60% 4–8 storeys, 15% 9–15 storeys and 5% landmark towers. Taller buildings use podiums; landmark placements preserve intersection sightlines. No downtown grass meadows.

## 5. Gameplay and population

Add clearly reachable, numbered category destinations: street/rear restaurant, apartment lobby/unit, office reception, hotel lobby, convenience/grocery pickup, service-alley pickup and construction delivery. Full rooms only at critical destinations; use shallow storefront/lobby depth elsewhere. Add loading/parking opportunities, rear access and pedestrian-only spaces. Parking legality is tagged and signed; do not invent a fine system. Extend the existing pickup/delivery catalog and interaction handlers without replacing ledger/dispatch logic.

Use activity zones around main avenue, transit, cafés and loading areas. Apply time-of-day visibility/activity rules; keep alleys/residential edges quieter. Reuse existing vehicle/character models and integrate movement through district paths. Avoid uniform random population placement.

## 6. Performance budget and validation

Target p95 ≤16.7 ms at 1280 × 720 on the available RTX 3070 laptop after warm-up, ≤2,000 visible draw calls, ≤3 million rendered primitives including shadow passes, ≤128 distinct urban materials, and ≤512 MiB texture memory. These are validation targets, not promises for other hardware. Route-query target ≤0.5 ms; report NavigationServer cost separately (zero/unavailable when unused). Count collision/static objects before/after and prioritize block-level proxies over decorative colliders.

Use shared kit meshes/materials, block-local MultiMeshes, conservative solid-wall occluders, authored near/far tiers, Godot mesh LODs, detail activation ranges, shallow interior illusion, limited shadow lights and simplified collision. Measure seven repeatable viewpoints at pedestrian and vehicle camera heights: commercial avenue, four-way intersection, residential transition, service alley, skyline, restaurant pickup and apartment delivery. Record frame intervals, draw calls, primitives, materials, texture memory, static visuals, collision bodies and navigation timings.

## 7. Exact implementation order / gates

1. Preserve a project-file snapshot; capture baseline metrics and map/scene audit.
2. Add deterministic parcel/road catalog and a separate representative-block blockout scene.
3. Validate dimensions, road joins, vehicle clearance, parking and entrance routes in the blockout.
4. Build/export the modular Blender kit, with UV/detail/collision manifests.
5. Assemble the representative block using the kit; validate pedestrian/vehicle views and performance. Revise gaps/repetition before replication.
6. Populate the remaining eight blocks with controlled height/frontage/use variation; preserve original content and append district connectors.
7. Add physical delivery locations and catalog hooks; validate every reachable entrance and original delivery flow.
8. Add logically placed street/transit/service/construction props and signed parking/loading areas.
9. Apply glazing/interior variation, wear/repair markings, lighting, occupied-window shader and skyline composition; add activity zones/time rules.
10. Run original and new tests, all 14 validation views, density/clearance audits and before/after performance reports. Correct failures, document actual results and launch the integrated game.

No user approval gate is required for these already authorized reversible local changes. Any inability to meet a budget or requested feature must be reported accurately, not hidden behind a completion claim.
