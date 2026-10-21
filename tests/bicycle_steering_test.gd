extends SceneTree
## Bicycle steering: keys and mouse-look turn the bike, handlebars and lean animate, dismount resets.
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
	check(player.steering_pivot != null, "Bicycle has a steering pivot")
	# Mount: stand next to the parked bike on open park lawn (the avenue now has traffic).
	player.bicycle.position = Vector3(-52, 0.05, -128)
	player.bicycle.rotation = Vector3.ZERO
	player.position = Vector3(-51.4, 0.05, -128)
	await physics_frame
	var message: String = player.toggle_bicycle()
	check(player.mounted, "Mounted: " + message)
	# Keys: hold A at speed.
	player.riding_speed = 5.0
	var yaw := player.rotation.y
	Input.action_press("move_forward")
	Input.action_press("move_left")
	ride(game, 30)
	check(player.steer_angle > 0.15, "Handlebars turn left with A (%.2f rad)" % player.steer_angle)
	var pivot_rest: Transform3D = player.steering_pivot.get_meta("rest")
	check(not player.steering_pivot.transform.basis.is_equal_approx(pivot_rest.basis), "Steering pivot rotates the fork and front wheel")
	check(player.lean > 0.05, "Rider leans into a left turn (%.2f)" % player.lean)
	ride(game, 60)
	check(player.rotation.y - yaw > 0.5, "Bike actually turns left (%.2f rad in 1.5 s)" % (player.rotation.y - yaw))
	Input.action_release("move_left")
	# Each manoeuvre starts on open road so a fence never stops the bike mid-test.
	player.position = Vector3(1.95, 0.05, -60)
	player.rotation = Vector3.ZERO
	player.riding_speed = 5.0
	Input.action_press("move_right")
	yaw = player.rotation.y
	ride(game, 60)
	check(player.lean < -0.05, "Rider leans into a right turn (%.2f)" % player.lean)
	ride(game, 30)
	check(player.rotation.y - yaw < -0.5, "Bike turns right with D (%.2f rad)" % (player.rotation.y - yaw))
	Input.action_release("move_right")
	ride(game, 60)
	check(absf(player.steer_angle) < 0.05, "Handlebars return to centre without input")
	# Mouse steering on open road: look right, bike follows and the camera re-centres.
	player.position = Vector3(1.95, 0.05, -60)
	player.rotation = Vector3.ZERO
	player.riding_speed = 5.0
	player.camera.rotation.y = -0.6
	yaw = player.rotation.y
	ride(game, 120)
	check(player.rotation.y - yaw < -0.3, "Looking right steers the bike right (%.2f)" % (player.rotation.y - yaw))
	check(absf(player.camera.rotation.y) < 0.35, "Camera re-centres as the bike turns (%.2f)" % player.camera.rotation.y)
	Input.action_release("move_forward")
	# Stop and dismount resets the animation.
	player.riding_speed = 0.0
	player.camera.rotation.y = 0.0
	ride(game, 10)
	var result: String = player.toggle_bicycle()
	check(not player.mounted, "Dismounted: " + result)
	check(player.steering_pivot.transform.is_equal_approx(player.steering_pivot.get_meta("rest")), "Handlebars straight when parked")
	check(is_zero_approx(player.bicycle.rotation.z), "Parked bike stands upright")
	print("BICYCLE STEERING PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "BICYCLE STEERING: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
