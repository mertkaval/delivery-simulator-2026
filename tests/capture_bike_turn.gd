extends SceneTree
## First-person and chase views of the bicycle mid-turn.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	game.world.set_time(15)
	var player: CourierPlayer = game.player
	player.bicycle.position=Vector3(1.95,0.05,-60)
	player.bicycle.rotation=Vector3.ZERO
	player.position=Vector3(2.5,0.05,-60)
	await physics_frame
	player.toggle_bicycle()
	player.riding_speed=4.5
	Input.action_press("move_forward")
	Input.action_press("move_left")
	for i in range(40): await physics_frame
	player.camera.rotation.x=-0.55
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/bike_turn_fp.png")
	var chase := Camera3D.new()
	game.world.add_child(chase)
	chase.global_position=player.global_position+player.global_basis*Vector3(2.2,1.6,-2.4)
	chase.look_at(player.global_position+Vector3(0,0.8,0))
	chase.make_current()
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/bike_turn_chase.png")
	Input.action_release("move_left")
	Input.action_release("move_forward")
	print("BIKE CAPTURE done steer=", player.steer_angle, " lean=", player.lean)
	quit()