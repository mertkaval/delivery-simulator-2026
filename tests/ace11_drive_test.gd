extends SceneTree
## Ace 11 hatchback (assets/vehicles/ace11, tools/prepare_civil_vehicles.py): vehicle contract,
## shop entry, showroom = bought car, and driving (wheels spin, front pivots and steering wheel
## turn, the car turns and stops).
var failed := 0
var checks := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		printerr("FAIL: " + text)

func _initialize() -> void:
	call_deferred("run")

func ride(game, frames: int) -> void:
	for i in range(frames):
		game.player._physics_process(1.0 / 60.0)

func paint_of(model: Node) -> Array:
	var out: Array = []
	for m in model.find_children("VehiclePaint*", "MeshInstance3D", true, false):
		out.append((m as MeshInstance3D).get_surface_override_material(0))
	return out

func run() -> void:
	# --- shop + catalogue ---
	check(ShopCatalog.ITEMS.has("ace11") and ShopCatalog.ITEMS.ace11.shop == "cars", "Ace 11 is sold at the car shop")
	check(ShopCatalog.is_car("ace11") and ShopCatalog.is_vehicle("ace11"), "Ace 11 counts as a car")
	check(VehicleCatalog.exists("ace11"), "Ace 11 GLB present")
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	var player: CourierPlayer = game.player
	game.session.active_vehicle = "ace11"
	player.replace_vehicle(Vector3(1.95, 0.0, -40))
	var car: Node3D = player.bicycle
	# --- asset contract ---
	var names: Array[String] = []
	for w in player.wheels: names.append(str(w.name))
	names.sort()
	check(names == ["WheelFrontL", "WheelFrontR", "WheelRearL", "WheelRearR"], "Four wheel pivots %s" % [names])
	check(player.steer_pivots.size() == 2, "Two front steer pivots (%d)" % player.steer_pivots.size())
	check(player.steering_wheel != null, "SteeringWheel pivot present")
	check(absf(float(car.get_meta("wheelbase", 0.0)) - 2.405) < 0.05, "Wheelbase metadata (%.2f)" % float(car.get_meta("wheelbase", 0.0)))
	var size: Vector3 = car.get_meta("collision_size", Vector3.ZERO)
	check(size.z > 3.6 and size.z < 3.9 and size.x > 1.6 and size.x < 1.9, "Collision is hatchback sized %s" % size)
	await physics_frame
	for w in player.wheels:
		var local: Vector3 = car.global_transform.affine_inverse() * w.global_position
		check(absf(local.y - 0.298) < 0.03, "%s hub at axle height (%.3f)" % [w.name, local.y])
		check((local.z < 0.0) == str(w.name).begins_with("WheelFront"), "%s on the right axle (z %.2f; front is -Z)" % [w.name, local.z])
		check((local.x < 0.0) == str(w.name).ends_with("L"), "%s on its side (x %.2f)" % [w.name, local.x])
	var sw_local: Vector3 = car.global_transform.affine_inverse() * player.steering_wheel.global_position
	check(sw_local.x < -0.2 and sw_local.z < 0.0 and sw_local.y > 0.8, "Steering wheel in front of the driver's seat %s" % sw_local)
	var column: Vector3 = car.global_basis.inverse() * player.steering_wheel.global_basis.z
	check(column.z > 0.85 and column.y > 0.2, "Steering wheel turns about its column (local +Z points back and up %s)" % column)
	# --- showroom = bought car ---
	var showroom: Node3D = null
	for n in game.world.find_children("*", "Node3D", true, false):
		if n != car and n.scene_file_path == VehicleCatalog.ACE11 and n.global_position.distance_to(ShopCatalog.LOCATIONS.cars) < 8.0:
			showroom = n
	check(showroom != null, "Ace 11 on display at the car shop")
	if showroom: check(paint_of(showroom) == paint_of(car), "Showroom Ace 11 has the bought car's paint")
	var hatch_a := CityAssets.create("hatchback", 100)
	var hatch_b := CityAssets.create_player_vehicle("hatchback")
	check(paint_of(hatch_a) == paint_of(hatch_b), "Showroom hatchback matches the bought hatchback")
	hatch_a.free()
	hatch_b.free()
	# --- driving --- (AI traffic is parked out of the way)
	var traffic: Node = game.world.get_node_or_null("CityTraffic")
	if traffic:
		traffic.set_physics_process(false)
		for c in traffic.cars:
			c.collision_layer = 0
			c.position.y = -50
	player.position = Vector3(1.95, 0.05, -40)
	player.rotation = Vector3.ZERO
	await physics_frame
	var message: String = player.toggle_bicycle()
	check(player.mounted, "Mounted the Ace 11: " + message)
	var start := player.position
	var spin0: float = player.wheels[0].rotation.x
	Input.action_press("move_forward")
	ride(game, 240)
	check(player.riding_speed > 10.0, "Reaches city speed (%.1f m/s)" % player.riding_speed)
	check(player.position.distance_to(start) > 15.0, "Actually moves (%.1f m)" % player.position.distance_to(start))
	check(not is_equal_approx(player.wheels[0].rotation.x, spin0), "Wheels spin with travel")
	var yaw := player.rotation.y
	Input.action_press("move_left")
	ride(game, 40)
	check(player.steer_angle > 0.08, "Front wheels steer left (%.2f rad)" % player.steer_angle)
	for pivot in player.steer_pivots: check(absf(pivot.rotation.y) > 0.05 and str(pivot.name).begins_with("SteerFront"), "%s yaws with the steering" % pivot.name)
	var rest: Transform3D = player.steering_wheel.get_meta("rest")
	var turned := rest.basis.inverse() * player.steering_wheel.transform.basis
	check(absf(turned.get_euler().z) > 0.8, "Steering wheel turns (%.2f rad)" % turned.get_euler().z)
	ride(game, 60)
	check(player.rotation.y - yaw > 0.4, "Car turns left (%.2f rad)" % (player.rotation.y - yaw))
	Input.action_release("move_left")
	Input.action_release("move_forward")
	Input.action_press("jump")
	ride(game, 120)
	Input.action_release("jump")
	check(absf(player.riding_speed) < 0.1, "Brake stops the car")
	var result: String = player.toggle_bicycle()
	check(not player.mounted, "Parked: " + result)
	print("ACE11 DRIVE PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "ACE11 DRIVE: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
