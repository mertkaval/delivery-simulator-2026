extends SceneTree
## Player sedan (Jetta GLI): asset contract and driving — the car accelerates, all wheels spin
## with travel, the front wheels and steering wheel turn, the car turns, brakes, parks, and the
## lamps react to night and braking.
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

func run() -> void:
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	var player: CourierPlayer = game.player
	game.session.active_vehicle = "sedan"
	player.replace_vehicle(Vector3(1.95, 0.0, -40))
	var car: Node3D = player.bicycle
	# --- asset contract ---
	check(car.has_method("update_driving_visuals") and car.has_method("bind_driver"), "Sedan is the Jetta vehicle scene")
	check(car.get_node_or_null("LOD0") != null and car.get_node_or_null("LOD1") != null and car.get_node_or_null("LOD2") != null, "Three LODs")
	check(car.axle_nodes.size() == 12, "Four wheel pivots per LOD (%d)" % car.axle_nodes.size())
	check(car.front_pivots.size() == 6, "Two front steer pivots per LOD (%d)" % car.front_pivots.size())
	check(not car.steering_wheels.is_empty(), "Steering wheel pivot present")
	check(absf(float(car.get_meta("wheelbase", 0.0)) - 2.68) < 0.05, "Wheelbase metadata (%.2f)" % float(car.get_meta("wheelbase", 0.0)))
	var size: Vector3 = car.get_meta("collision_size", Vector3.ZERO)
	check(size.z > 4.5 and size.z < 5.0 and size.x > 1.7 and size.x < 2.0, "Collision is sedan sized %s" % size)
	var lod0_wheels: Array = car.axle_nodes.filter(func(w: Node3D) -> bool: return car.get_node("LOD0").is_ancestor_of(w))
	check(lod0_wheels.size() == 4, "LOD0 has four wheels")
	var xs: Array[float] = []
	for w in lod0_wheels:
		xs.append(w.global_position.x - car.global_position.x)
		check(absf(w.global_position.y - car.global_position.y - 0.33) < 0.03, "%s hub at axle height (%.3f)" % [w.name, w.global_position.y - car.global_position.y])
	check(xs.min() < -0.7 and xs.max() > 0.7, "Wheels sit at the track width")
	var mesh_count := car.find_children("*", "MeshInstance3D", true, false).size()
	check(mesh_count > 0, "Meshes present (%d)" % mesh_count)
	# --- driving --- (AI traffic is parked out of the way so it cannot block the test drive)
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
	check(player.mounted, "Mounted the car: " + message)
	var start := player.position
	var phase0: float = car.wheel_phase
	Input.action_press("move_forward")
	ride(game, 240)
	check(player.riding_speed > 10.0, "Car reaches city speed (%.1f m/s)" % player.riding_speed)
	check(player.position.distance_to(start) > 15.0, "Car actually moves (%.1f m)" % player.position.distance_to(start))
	check(not is_equal_approx(car.wheel_phase, phase0), "Wheels spin with travel")
	var spun := true
	for w in car.axle_nodes:
		if not is_equal_approx(w.rotation.x, car.wheel_phase): spun = false
	check(spun, "Every wheel pivot follows the roll phase")
	check(car.global_position.distance_to(player.global_position) < 0.01, "Body follows the driver")
	var yaw := player.rotation.y
	Input.action_press("move_left")
	ride(game, 40)
	check(player.steer_angle > 0.08, "Front wheels steer left (%.2f rad)" % player.steer_angle)
	for pivot in car.front_pivots: check(absf(pivot.rotation.y) > 0.05, "%s yaws with the steering" % pivot.name)
	var sw: Node3D = car.steering_wheels[0]
	var rest: Transform3D = sw.get_meta("rest")
	var turned := rest.basis.inverse() * sw.transform.basis
	check(absf(turned.get_euler().z) > 0.8, "Steering wheel turns (%.2f rad)" % turned.get_euler().z)
	check(is_zero_approx(player.lean), "Cars do not lean")
	ride(game, 60)
	check(player.rotation.y - yaw > 0.4, "Car turns left (%.2f rad)" % (player.rotation.y - yaw))
	Input.action_release("move_left")
	ride(game, 90)
	check(absf(player.steer_angle) < 0.05, "Wheels return to centre")
	Input.action_release("move_forward")
	Input.action_press("jump")
	ride(game, 90)
	check(car._braking, "Brake lamps on while braking")
	Input.action_release("jump")
	check(absf(player.riding_speed) < 0.1, "Brake stops the car")
	# Lamps: night switches the headlights on.
	game.session.calendar_minutes = 22 * 60
	car._process(0.016)
	var lit := 0
	for light in car._headlights: if light.light_energy > 0.5: lit += 1
	check(lit == 2, "Headlights on at night (%d)" % lit)
	var result: String = player.toggle_bicycle()
	check(not player.mounted, "Parked: " + result)
	for pivot in car.front_pivots: check(is_zero_approx(pivot.rotation.y), "%s straight when parked" % pivot.name)
	check(sw.transform.is_equal_approx(rest), "Steering wheel centred when parked")
	print("CAR STEERING PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "CAR STEERING: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
