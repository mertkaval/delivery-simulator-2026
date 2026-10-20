extends SceneTree
## Player sedan in the game world: exterior views, steering lock, driver's seat view.
## usage: godot --path . --script res://tests/capture_car.gd -- <prefix> [hour]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "car"
	var hour: float = float(args[1]) if args.size() > 1 else 15.5
	root.size = Vector2i(1280, 720)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	game.session.active_vehicle = "sedan"
	game.world.set_time(hour)
	# Quiet street for the shots: no buses or traffic passing through the frame.
	for name in ["Buses", "CityTraffic", "CityLife"]:
		var node: Node = game.world.get_node_or_null(name)
		if node != null:
			node.process_mode = Node.PROCESS_MODE_DISABLED
			node.visible = false
	var player: CourierPlayer = game.player
	var at := Vector3(1.95, 0.0, -300)
	player.replace_vehicle(at)
	player.position = at + Vector3(1.6, 0.05, 0)
	var car: Node3D = player.bicycle
	car.rotation.y = 0.0
	var camera := Camera3D.new()
	game.world.add_child(camera)
	camera.current = true
	camera.fov = 45
	# Full steering lock for the exterior shots so the front wheels read.
	for pivot in player.steer_pivots:
		pivot.transform = (pivot.get_meta("rest") as Transform3D) * Transform3D(Basis(Vector3.UP, 0.45), Vector3.ZERO)
	var views := [
		["front_quarter", at + Vector3(4.5, 1.5, -6.0), at + Vector3(0, 0.8, 0)],
		["rear_quarter", at + Vector3(-4.5, 1.6, 6.0), at + Vector3(0, 0.8, 0)],
		["side", at + Vector3(7.5, 1.2, 0.0), at + Vector3(0, 0.75, 0)],
		["front", at + Vector3(0.0, 1.1, -7.5), at + Vector3(0, 0.7, 0)],
		["wheel", at + Vector3(2.4, 0.6, -2.4), at + Vector3(0.8, 0.34, -1.42)],
		["cabin", at + Vector3(0.8, 1.5, -3.6), at + Vector3(-0.2, 1.0, 0.2)]]
	for v in views:
		camera.position = v[1]
		camera.look_at(v[2])
		for i in range(40): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix, v[0]])
	# Driver's view: mount and look through the windscreen at the steering wheel.
	await physics_frame
	print("MOUNT ", player.toggle_bicycle())
	camera.current = false
	player.camera.current = true
	player.steer_angle = 0.3
	player.apply_steering_visuals(0.3)
	for i in range(20): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_driver.png" % prefix)
	print("CAR CAPTURE done mounted=", player.mounted)
	quit()
