extends SceneTree
## Rendered captures of the courier's gesture / transition clips in the game: knocking, ringing a
## doorbell, waving, drinking water and eating an energy bar (item in the right hand), the idle
## fidgets, a hard landing from a fall, and getting on / off the bicycle (Bike_Mount / _Dismount).
## godot --path . --script res://tests/capture_courier_actions.gd -- <out_dir> [only,sections]
var out := "res://tmp/courier_actions"
var only := ""
var game: Node
var player: CourierPlayer
var free_cam: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(label: String) -> void:
	for i in range(2): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("%s/ca_%s.png" % [out, label])
	print("saved ca_%s (state %s, action %s, gesture %s)" % [label, player.avatar.state, player.avatar.action_role, player.avatar.gesture])

func ticks(n: int) -> void:
	for i in range(n): await physics_frame

func seconds(s: float) -> void:
	await ticks(int(round(s * 60.0)))

func look_from(offset_local: Vector3, at_local: Vector3, basis_node: Node3D = null) -> void:
	var b := basis_node if basis_node != null else player.avatar
	if free_cam.get_parent() != b: free_cam.reparent(b, false)
	free_cam.transform = Transform3D(Basis.looking_at(at_local - offset_local, Vector3.UP), offset_local)
	free_cam.make_current()

func want(label: String) -> bool:
	return only == "" or only.split(",").has(label)

func stand_at(at: Vector3, yaw: float) -> void:
	player.position = at
	player.rotation = Vector3(0, yaw, 0)
	player.avatar.facing = yaw
	await ticks(30)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0]
	if args.size() > 1: only = args[1]
	DirAccess.make_dir_recursive_absolute(out)
	GameSettings.path = "user://capture_courier_actions_settings.cfg"
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	game.world.set_time(14.5)
	player = game.player
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	free_cam = Camera3D.new()
	free_cam.fov = 50
	game.add_child(free_cam)
	var a := player.avatar
	var front := Vector3(1.2, 1.25, -2.2)
	var side := Vector3(2.4, 1.1, -0.6)
	if want("door"):
		await stand_at(Vector3(-6.4, 0.1, 23), 0.0)
		a.play_gesture("knock_door", 0.0)
		look_from(side, Vector3(0, 1.2, -0.3))
		await seconds(0.55)
		await shot("knock")
		await seconds(1.4)
		a.play_gesture("doorbell", 0.0)
		await seconds(0.5)
		await shot("doorbell")
		await seconds(1.0)
		a.play_gesture("wave", 0.0)
		look_from(front, Vector3(0, 1.3, 0))
		await seconds(0.7)
		await shot("wave")
		await seconds(1.6)
	if want("supplies"):
		await stand_at(Vector3(-6.4, 0.1, 23), 0.0)
		a.play_gesture("eat_drink", NAN, -1.0, "water_bottle")
		look_from(Vector3(1.0, 1.55, -1.4), Vector3(0, 1.45, 0))
		await seconds(0.25)
		await shot("drink_lift")
		await seconds(0.6)
		await shot("drink")
		await seconds(1.8)
		a.play_gesture("eat_drink", NAN, -1.0, "energy_bar")
		await seconds(0.8)
		await shot("eat_bar")
		await seconds(1.8)
	if want("fidget"):
		look_from(front, Vector3(0, 1.0, 0))
		for i in range(3):
			a._idle_for = PlayerAvatar.FIDGET_AFTER + 0.1
			await seconds(1.6)
			await shot("fidget_%d" % i)
			a.end_gesture()
			await seconds(0.5)
	if want("fall"):
		await stand_at(Vector3(-6.4, 3.4, 23), 0.0)
		look_from(side, Vector3(0, 0.8, 0))
		var waited := 0
		while not player.is_on_floor() and waited < 180:
			await physics_frame
			waited += 1
		await seconds(0.12)
		await shot("land_hard")
		print("fall speed %.1f hard %s" % [player.last_fall_speed, a.hard_landing])
		await seconds(1.0)
	if want("bike"):
		player.session.active_vehicle = "bicycle"
		player.replace_vehicle(Vector3(1.95, 0.05, -40))
		player.bicycle.rotation = Vector3.ZERO
		await stand_at(Vector3(1.1, 0.1, -39.6), 0.0)
		print(player.toggle_bicycle())
		look_from(Vector3(-2.8, 1.1, -0.4), Vector3(0, 0.8, 0), player.bicycle)
		var mount_len := a.clip_seconds("bike_mount")
		for f in [0.2, 0.45, 0.7, 0.95]:
			await seconds(mount_len * 0.25)
			await shot("mount_%d" % int(f * 100))
		print("mount locked %s, state %s" % [a.mount_locked(), a.state])
		await seconds(0.8)
		await shot("seated")
		print(player.toggle_bicycle())
		var dis_len := a.clip_seconds("bike_dismount")
		for f in [0.3, 0.6, 0.9]:
			await seconds(dis_len * 0.3)
			await shot("dismount_%d" % int(f * 100))
		await seconds(0.8)
		await shot("dismounted")
	print("CAPTURE COURIER ACTIONS done")
	quit()
