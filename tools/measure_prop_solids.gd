extends SceneTree
## Measures the prop shapes used by PropColliders.SOLIDS: for each asset the local full AABB, the
## cross-section the courier's body meets ("band": vertices 0.12-1.8 m above the base), the base
## footprint (< 0.3 m) and the 1.0-2.2 m band. Needs a renderer (vertex data):
##   Godot_console.exe --path . --resolution 320x200 --script res://tools/measure_prop_solids.gd
## Re-run after changing a prop GLB and update PropColliders.SOLIDS from its output.

func _initialize() -> void: call_deferred("run")

func verts(parts: Array, lo: float, hi: float, base_y: float) -> AABB:
	var box := AABB()
	var found := false
	for p: Dictionary in parts:
		var mesh: Mesh = p.mesh
		var xf: Transform3D = p.transform
		for s in range(mesh.get_surface_count()):
			var arrays := mesh.surface_get_arrays(s)
			if arrays.is_empty() or arrays[Mesh.ARRAY_VERTEX] == null: continue
			for v0: Vector3 in (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array):
				var v := xf * v0
				if v.y < base_y + lo or v.y > base_y + hi: continue
				if not found:
					box = AABB(v, Vector3.ZERO)
					found = true
				else: box = box.expand(v)
	return box

func whole(parts: Array) -> AABB:
	var box := AABB()
	var first := true
	for p: Dictionary in parts:
		var b: AABB = (p.transform as Transform3D) * (p.mesh as Mesh).get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box

func f(b: AABB) -> String:
	return "c(%.3f,%.3f,%.3f) s(%.3f,%.3f,%.3f)" % [b.get_center().x, b.get_center().y, b.get_center().z, b.size.x, b.size.y, b.size.z]

func report(label: String, parts: Array) -> void:
	if parts.is_empty():
		print("%-28s MISSING" % label)
		return
	var w := whole(parts)
	var band := verts(parts, 0.12, 1.8, w.position.y)
	var base := verts(parts, -0.01, 0.3, w.position.y)
	var mid := verts(parts, 1.0, 2.2, w.position.y)
	print("%-28s full %s | band %s | base %s | mid %s" % [label, f(w), f(band), f(base), f(mid)])

func node_parts(node: Node) -> Array:
	var list: Array = []
	PropKit.collect(node, Transform3D.IDENTITY, list)
	return list

func run() -> void:
	var house := HouseInstancer.new()
	for a in ["fence_picket", "hedge", "fence_privacy", "fence_post", "patio_set", "bbq", "raised_bed", "shed", "cart_trio", "garage_single",
		"bus_shelter",
		"rs_aframe", "rs_planter", "rs_plant", "rs_sidewalk_set", "rs_table4", "rs_table2", "rs_booth", "rs_barrel"]:
		report("house:" + a, house.get_parts(a, "near"))
	house.free()
	for a in ["cafe_chair", "cafe_table", "reuse_park_bench", "reuse_street_lamp", "reuse_birch", "reuse_maple", "reuse_garden_planter", "reuse_bicycle",
		"delivery_cart", "parking_sign", "loading_sign", "parking_meter", "mailboxes", "hydrant", "trash_bin", "recycle_bin", "newspaper_box", "bike_rack",
		"cone", "grocery_shelf", "service_counter", "bus_shelter", "bus_sign", "pallet_supplies", "scaffold",
		"living_stop", "living_cycle_sign", "living_speed", "living_taxi_sign", "living_school_zone", "living_hospital_sign", "living_rain_garden", "living_cycle_separator",
		"dumpster", "utility_cabinet", "bollard", "barrier", "tree_pit", "security_camera"]:
		var parts := UrbanKit.get_parts(a)
		if DowntownDistrict.PROP_SWAP.has(a) and PropKit.has(DowntownDistrict.PROP_SWAP[a]): parts = PropKit.get_parts(DowntownDistrict.PROP_SWAP[a])
		report("urban:" + a, parts)
	for a in ["mailbox", "park_bench", "bicycle", "scooter", "helmet", "store_equipment", "store_bikes", "store_scooters", "store_cars"]:
		var n := CityAssets.create(a, 100)
		report("city:" + a, node_parts(n))
		n.free()
	for id in ["rock_0", "rock_1", "rock_2", "rock_3", "rock_4", "rock_5", "rock_6", "rock_7", "rock_8", "potted_lily", "potted_snake", "pot_geranium_red", "boxwood_ball", "shrub_a", "shrub_b", "shrub_c"]:
		var p := CityLandscape.prop(id)
		if p.is_empty(): report("land:" + id, [])
		else: report("land:" + id, [{"mesh": p.mesh, "transform": Transform3D.IDENTITY}])
	for id in ["potted_plant_tall", "potted_plant_floor", "planter_box_a", "planter_box_b", "planter_trough_a", "planter_trough_c", "wall_shelf_decor", "bin_small", "garbage_bag"]:
		var sc := InteriorProps.scene(id)
		if sc == null: report("int:" + id, [])
		else:
			var n := sc.instantiate()
			report("int:" + id, node_parts(n))
			n.free()
	for id in ["planter_geranium_red", "planter_bamboo_square", "cardboard_box_medium", "cardboard_box_small", "bench_wood", "street_light"]:
		if PropKit.has(id): report("kit:" + id, PropKit.get_parts(id))
	var locker := load("res://assets/gadgets/pickup_locker.glb") as PackedScene
	if locker != null:
		var n := locker.instantiate()
		report("gadget:pickup_locker", node_parts(n))
		n.free()
	quit(0)
