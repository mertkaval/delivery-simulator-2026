extends SceneTree
## Chase camera behind the bought Jetta, a steering sample, and the car showroom display.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280, 720)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	for i in range(10): await process_frame
	game.close_menu()
	game.session.wallet = 100
	game.session.buy("sedan")
	game.equip_vehicle("sedan")
	game.close_menu()
	var p: CourierPlayer = game.player
	p.position = p.bicycle.global_position + Vector3(1.5, 0.1, 0)
	p.toggle_bicycle()
	print("MOUNTED ", p.mounted, " at ", p.position)
	for i in range(30): await physics_frame
	game.world.set_time(15.0)
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/car_chase_view.png")
	# Steering response: full right input held at speed for 1 s.
	Input.action_press("move_forward")
	for i in range(150): await physics_frame
	print("SPEED %.1f km/h" % (p.riding_speed * 3.6))
	# Steering response: tap-and-hold right for 1.5 s, release for 1 s; log every 0.25 s.
	var traffic: Node = game.world.get_node_or_null("CityTraffic")
	if traffic: traffic.set_physics_process(false)
	Input.action_press("move_right")
	var last := p.rotation.y
	for i in range(150):
		await physics_frame
		if i == 89: Input.action_release("move_right")
		if i % 15 == 14:
			print("t=%.2fs speed %.1f km/h yaw rate %.0f deg/s wheels %.0f deg camera lag %.0f deg" % [(i + 1) / 60.0, p.riding_speed * 3.6, rad_to_deg(wrapf(p.rotation.y - last, -PI, PI)) * 4.0, rad_to_deg(p.steer_angle), rad_to_deg(p.car_camera_yaw)])
			last = p.rotation.y
		if i == 45:
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://tmp/car_mid_turn.png")
	Input.action_release("move_forward")
	var shop: Vector3 = ShopCatalog.LOCATIONS["cars"]
	var cam := Camera3D.new()
	game.world.add_child(cam)
	cam.position = shop + Vector3(-2.6, 2.6, 4.5)
	cam.look_at(shop + Vector3(-2.6, 0.6, -3))
	cam.make_current()
	for i in range(5): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/car_showroom.png")
	quit()
