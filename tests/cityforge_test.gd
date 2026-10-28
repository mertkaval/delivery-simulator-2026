extends SceneTree
## Port Halden (CityForge): the generated city loads and keeps its contracts.
## Data (lots on land, houses inside their lots and not overlapping, addresses unique, doors facing
## the street), the HLOD ranges (no gap between the near models and the merged far mesh),
## ground and building collision, and the build-time budget.
var failures := 0
var checks := 0

func _initialize() -> void: call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	print(("PASS: " if ok else "FAIL: ") + text)
	if not ok: failures += 1

func run() -> void:
	var w := CityForgeWorld.new()
	root.add_child(w)
	var city: Dictionary = w.city
	check(w.chunks.size() == 64, "64 chunks of 256 m loaded (%d)" % w.chunks.size())
	var missing: Array[String] = []
	for name: String in ["house_craftsman", "house_vancouver_special", "house_bungalow", "house_modern_box", "house_foursquare",
			"house_tudor", "house_split_level", "house_west_coast", "garage", "lamp", "traffic_light", "stop_sign", "bus_stop",
			"hydrant", "bench"] + Array(CityForgeWorld.TREES):
		if not w.kit.has(name) or (w.kit[name] as Array)[0] == null or (w.kit[name] as Array)[1] == null: missing.append(name)
	check(missing.is_empty(), "Every kit model has LOD0 and LOD1 %s" % str(missing))
	var houses: Array = city.houses
	var lots: Array = city.lots
	check(houses.size() >= 1000 and lots.size() == houses.size(), "Burnaby-style lots, one house each (%d)" % houses.size())
	check(int(w.stats.instances) >= 10000, "Houses, garages, trees and furniture placed as instances (%d)" % int(w.stats.instances))
	# lots carry fences, unique addresses; houses stand inside their lot
	var fenced := {}
	for f: Dictionary in city.fences: fenced[str(f.lot)] = (f.segments as Array).size()
	var no_fence := 0
	var addresses := {}
	var lot_by_id := {}
	for lot: Dictionary in lots:
		lot_by_id[str(lot.id)] = lot
		if int(fenced.get(str(lot.id), 0)) < 3: no_fence += 1
		addresses[str(lot.address)] = true
	check(no_fence == 0, "Every lot is fenced or hedged (%d without)" % no_fence)
	check(addresses.size() == lots.size(), "Every lot has its own address (%d / %d)" % [addresses.size(), lots.size()])
	var outside := 0
	var bad_door := 0
	var off_ground := 0
	for hs: Dictionary in houses:
		var lot: Dictionary = lot_by_id[str(hs.lot)]
		var r: Array = lot.rect
		var pos: Array = hs.pos
		var half := Vector2(float((hs.size as Array)[0]), float((hs.size as Array)[1])) * 0.5
		if float(pos[0]) - half.x < float(r[0]) - 0.05 or float(pos[0]) + half.x > float(r[2]) + 0.05 \
				or float(pos[1]) - half.y < float(r[1]) - 0.05 or float(pos[1]) + half.y > float(r[3]) + 0.05:
			outside += 1
		# the door is on the street side: nearer the lot's front line than the house centre is
		var door := w.to_plan(w.house_door(hs))
		if absf(door.y - float(lot.front_y)) >= absf(float(pos[1]) - float(lot.front_y)): bad_door += 1
		if absf(w.ground_height(w.to_world(float(pos[0]), float(pos[1]))) - float(hs.h)) > 0.6: off_ground += 1
	check(outside == 0, "Houses stand inside their lots (%d outside)" % outside)
	check(bad_door == 0, "Front doors face the street (%d wrong)" % bad_door)
	check(off_ground == 0, "Houses sit on the graded ground (%d off)" % off_ground)
	# no two houses overlap (grid hash on 20 m cells)
	var cells := {}
	var overlaps := 0
	for hs: Dictionary in houses:
		var p := Vector2(float((hs.pos as Array)[0]), float((hs.pos as Array)[1]))
		var key := Vector2i(int(p.x / 20.0), int(p.y / 20.0))
		for dx in [-1, 0, 1]:
			for dy in [-1, 0, 1]:
				for other: Dictionary in cells.get(key + Vector2i(dx, dy), []):
					var q := Vector2(float((other.pos as Array)[0]), float((other.pos as Array)[1]))
					var need := (Vector2(float((hs.size as Array)[0]), float((hs.size as Array)[1])) + Vector2(float((other.size as Array)[0]), float((other.size as Array)[1]))) * 0.5
					if absf(p.x - q.x) < need.x - 0.01 and absf(p.y - q.y) < need.y - 0.01: overlaps += 1
		if not cells.has(key): cells[key] = []
		(cells[key] as Array).append(hs)
	check(overlaps == 0, "No two houses overlap (%d)" % overlaps)
	# parks, public buildings, furniture
	var kinds := {}
	for pb: Dictionary in city.public: kinds[str(pb.kind)] = true
	check(kinds.has("city_hall") and kinds.has("hospital") and kinds.has("police") and kinds.has("fire") and kinds.has("school"),
		"City hall, hospital, police, fire halls and schools placed %s" % str(kinds.keys()))
	var props: Dictionary = city.props
	check((props.bus_stop as Array).size() >= 30 and (props.traffic_light as Array).size() >= 100 and (props.lamp as Array).size() >= 1000,
		"Bus stops, traffic lights and street lamps along the roads")
	# HLOD: a chunk's far mesh hides before its near cells stop drawing (no hole), and every near cell names it
	check(CityForgeWorld.FAR_BEGIN + CityForgeWorld.CHUNK * 0.7072 < CityForgeWorld.NEAR_END, "Near and far ranges overlap (no gap)")
	var unparented := 0
	var street_ranged := true
	var far_ok := true
	for key: Vector2i in w.far_nodes:
		if (w.far_nodes[key] as GeometryInstance3D).visibility_range_begin != CityForgeWorld.FAR_BEGIN: far_ok = false
	for node in w.find_children("*", "MultiMeshInstance3D", true, false):
		var mi := node as MultiMeshInstance3D
		if mi.visibility_range_end == CityForgeWorld.NEAR_END and mi.visibility_parent.is_empty(): unparented += 1
		if str(mi.name).begins_with("lamp_") and (mi.visibility_range_end != CityForgeWorld.STREET_END or not mi.visibility_parent.is_empty()): street_ranged = false
	check(far_ok and w.far_nodes.size() >= 40, "Chunks have merged far meshes (%d)" % w.far_nodes.size())
	check(unparented == 0, "Every near cell hands over to its chunk's far mesh (%d without)" % unparented)
	check(street_ranged, "Street lamps (not in the far mesh) keep their own distance range")
	# collision: the ground everywhere, buildings near the focus
	await physics_frame
	await physics_frame
	var space := w.get_world_3d().direct_space_state
	var hs0: Dictionary = houses[houses.size() / 2]
	var lot0: Dictionary = lot_by_id[str(hs0.lot)]
	var yard := w.to_world((float((lot0.rect as Array)[0]) + float((lot0.rect as Array)[2])) * 0.5, float(lot0.front_y) + float(lot0.front) * -1.5)
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(yard + Vector3.UP * 400.0, yard + Vector3.DOWN * 100.0))
	check(not hit.is_empty() and absf((hit.position as Vector3).y - w.ground_height(yard)) < 0.35, "Ground collision follows the graded terrain")
	var house_pos := w.to_world(float((hs0.pos as Array)[0]), float((hs0.pos as Array)[1]), float(hs0.h))
	w.update_focus(house_pos, 10.0)
	await physics_frame
	await physics_frame
	hit = w.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(house_pos + Vector3.UP * 60.0, house_pos))
	check(not hit.is_empty() and (hit.position as Vector3).y > float(hs0.h) + 3.0, "Houses near the courier are solid")
	check(int(w.stats.build_ms) < 8000, "City builds in %d ms" % int(w.stats.build_ms))
	print("CITYFORGE: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 else 1)
