extends SceneTree
## Rendered captures of the third-person courier: walking on the avenue (several frames), a jump,
## a turn, riding the bicycle (side, 3/4 and chase at speed), zoomed in / out, against a wall
## (camera collision) and first person after V. Also closeups from a free camera to check the
## feet on the ground, the hips on the saddle, the hands on the grips and the feet on the pedals.
## godot --path . --script res://tests/capture_third_person.gd -- <out_dir> [only,sections] [contract.json]
var out := "res://tmp"
var only := ""
var game: Node
var player: CourierPlayer
var free_cam: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(label: String) -> void:
	for i in range(2): await process_frame
	await RenderingServer.frame_post_draw
	if player.held_package() != null:
		print("  %s: package at %s (avatar %s, visible %s)" % [label, player.held_package().global_position, player.avatar.global_position, player.held_package().is_visible_in_tree()])
	root.get_texture().get_image().save_png("%s/tp_%s.png" % [out, label])
	print("saved tp_%s" % label)

func ticks(n: int) -> void:
	for i in range(n): await physics_frame

## A free camera riding along with `basis_node` (default: the character) at a local offset.
func look_from(offset_local: Vector3, at_local: Vector3, basis_node: Node3D = null) -> void:
	var b := basis_node if basis_node != null else player.avatar
	if free_cam.get_parent() != b: free_cam.reparent(b, false)
	free_cam.transform = Transform3D(Basis.looking_at(at_local - offset_local, Vector3.UP), offset_local)
	free_cam.make_current()

func back_to_player() -> void:
	player.camera.make_current()

func release_all() -> void:
	for a in ["move_forward", "move_back", "move_left", "move_right", "sprint", "jump", "walk"]: Input.action_release(a)

func want(label: String) -> bool:
	return only == "" or only.split(",").has(label)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0]
	if args.size() > 1: only = args[1]
	# Optional third arg: a body contract to try (e.g. a draft clips.json for the courier).
	if args.size() > 2: PlayerAvatar.contract_path = args[2]
	DirAccess.make_dir_recursive_absolute(out)
	GameSettings.path = "user://capture_third_person_settings.cfg"
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
	# Walking up the avenue sidewalk.
	if want("walk"):
		player.position = Vector3(-6.4, 0.1, 23)
		player.rotation = Vector3(0, 0, 0)
		player.camera.rotation = Vector3(-0.22, 0, 0)
		await ticks(20)
		Input.action_press("move_forward")
		await ticks(50)
		for i in range(4):
			await ticks(9)
			await shot("walk_%d" % i)
		look_from(Vector3(2.6, 1.0, 0.0), Vector3(0, 0.9, 0))
		await shot("walk_side")
		look_from(Vector3(0.9, 0.35, -0.2), Vector3(0, 0.2, 0))
		await shot("walk_feet")
		Input.action_press("sprint")
		await ticks(40)
		look_from(Vector3(3.2, 1.1, 0.0), Vector3(0, 0.9, 0))
		await shot("sprint_side")
		back_to_player()
		await shot("sprint")
		Input.action_release("sprint")
		Input.action_press("walk")
		await ticks(40)
		look_from(Vector3(2.4, 1.0, 0.3), Vector3(0, 0.9, 0))
		await shot("slow_walk_side")
		back_to_player()
		release_all()
		await ticks(40)
		look_from(Vector3(1.6, 1.2, -1.8), Vector3(0, 0.9, 0))
		await shot("idle_front")
		back_to_player()
	# Turn: the view swings round, the body turns to run the other way.
	if want("turn"):
		player.position = Vector3(-8, 0.1, 10)
		player.rotation = Vector3.ZERO
		await ticks(20)
		player.rotation.y = PI * 0.75
		Input.action_press("move_forward")
		await ticks(9)
		await shot("turn_0")
		await ticks(6)
		await shot("turn_1")
		release_all()
		await ticks(30)
		player.rotation.y += 1.6
		await ticks(25)
		await shot("turn_in_place")
	# Jump.
	if want("jump"):
		player.position = Vector3(-8, 0.1, 15)
		player.rotation = Vector3.ZERO
		await ticks(20)
		Input.action_press("move_forward")
		await ticks(30)
		Input.action_press("jump")
		await ticks(1)
		Input.action_release("jump")
		await ticks(9)
		await shot("jump_air")
		look_from(Vector3(3.0, 1.2, 0.0), Vector3(0, 1.0, 0))
		await shot("jump_side")
		back_to_player()
		await ticks(14)
		await shot("jump_land")
		release_all()
	# Zoom.
	if want("zoom"):
		player.position = Vector3(-8, 0.1, 20)
		player.rotation = Vector3(0, 0.5, 0)
		player.camera.rotation.x = -0.25
		player.view.target_distance = PlayerCameraRig.MIN_DISTANCE
		await ticks(60)
		await shot("zoom_in")
		player.view.target_distance = PlayerCameraRig.MAX_DISTANCE
		await ticks(60)
		await shot("zoom_out")
		player.view.target_distance = 3.2
	# Wall: back to a house wall, camera pulled in front of it.
	if want("wall"):
		# Kebab House's brick side wall runs along the sidewalk at x ~ -11.9: stand 0.9 m in front
		# of it looking away, so the camera's place is inside the wall.
		player.position = Vector3(-10.95, 0.1, 9.0)
		player.rotation = Vector3(0, -PI / 2, 0)
		player.camera.rotation.x = -0.15
		await ticks(60)
		await shot("wall")
		print("wall clear=%.2f arm=%.2f" % [player.view.clear, player.view.arm_length])
	# First person after V.
	if want("fp"):
		player.position = Vector3(-8, 0.1, 20)
		player.rotation = Vector3.ZERO
		player.camera.rotation.x = -0.3
		player.toggle_view()
		await ticks(40)
		await shot("first_person")
		player.toggle_view()
		await ticks(30)
	# Carrying an order in both hands; then the phone and the backpack (first-person rigs).
	if want("carry"):
		var s: DeliverySession = game.session
		if not s.inventory.has("delivery_bag"): s.inventory.append("delivery_bag")
		s.offer()
		s.accept()
		player.position = s.pickup_position() + Vector3(0, 0.1, 2.0)
		await ticks(20)
		for i in range(10): await process_frame
		var mine: Node3D = null
		for p: Node3D in game.shelves.packages.get(s.restaurant_id(), []):
			if is_instance_valid(p) and (p.get_meta("package", {}) as Dictionary).get("customer", "") == s.order.get("customer", "?"): mine = p
		if mine != null:
			s.take_package(mine.get_meta("package"), 1.0)
			game.shelves.take(mine)
		print("holding: ", s.holding_package())
		player.position = Vector3(-6.5, 0.1, 30)
		player.rotation = Vector3(0, 0.3, 0)
		player.camera.rotation.x = -0.25
		await ticks(40)
		await shot("carry_idle")
		look_from(Vector3(1.4, 1.2, -1.6), Vector3(0, 1.0, 0))
		await shot("carry_front")
		back_to_player()
		Input.action_press("move_forward")
		await ticks(40)
		await shot("carry_walk")
		look_from(Vector3(2.6, 1.1, 0.0), Vector3(0, 0.95, 0))
		await shot("carry_walk_side")
		back_to_player()
		release_all()
		await ticks(20)
		game.show_menu("bag")
		for i in range(40): await process_frame
		await shot("bag_open")
		game.bag_click(OrderDetails.best_slot(str(s.order.get("kind", "bag"))))
		for i in range(40): await process_frame
		await shot("bag_packed")
		game.close_menu()
		for i in range(30): await process_frame
		game.show_menu("phone")
		for i in range(40): await process_frame
		await shot("phone_open")
		game.close_menu()
		for i in range(30): await process_frame
		await shot("after_phone")
	# Bicycle.
	if want("bike"):
		player.session.active_vehicle = "bicycle"
		player.replace_vehicle(Vector3(1.95, 0.05, -40))
		player.bicycle.rotation = Vector3.ZERO
		player.position = Vector3(2.9, 0.1, -40)
		player.rotation = Vector3(0, 0.6, 0)
		await ticks(30)
		print(player.toggle_bicycle())
		await ticks(12)
		await shot("bike_mounting")
		await ticks(40)
		look_from(Vector3(3.0, 1.0, 0.0), Vector3(0, 0.85, 0), player.bicycle)
		await shot("bike_parked_side")
		back_to_player()
		Input.action_press("move_forward")
		await ticks(120)
		await shot("bike_chase")
		look_from(Vector3(3.2, 1.0, 0.0), Vector3(0, 0.85, 0), player.bicycle)
		await shot("bike_side")
		look_from(Vector3(2.4, 1.4, -2.6), Vector3(0, 0.85, 0), player.bicycle)
		await shot("bike_34")
		look_from(Vector3(1.0, 1.35, -0.6), Vector3(0, 1.0, -0.2), player.bicycle)
		await shot("bike_hands")
		look_from(Vector3(1.2, 0.5, 0.15), Vector3(0, 0.35, 0.15), player.bicycle)
		await shot("bike_feet")
		Input.action_press("move_left")
		await ticks(30)
		back_to_player()
		await shot("bike_turn_chase")
		look_from(Vector3(0.3, 1.3, -3.8), Vector3(0, 0.9, 0), player.bicycle)
		await shot("bike_turn_front")
		Input.action_release("move_left")
		Input.action_release("move_forward")
		await ticks(20)
		look_from(Vector3(3.2, 1.0, 0.0), Vector3(0, 0.85, 0), player.bicycle)
		await shot("bike_coast_side")
		Input.action_press("jump")
		await ticks(120)
		Input.action_release("jump")
		look_from(Vector3(1.2, 1.1, -2.6), Vector3(0, 0.7, 0), player.bicycle)
		await shot("bike_stopped")
		look_from(Vector3(-2.6, 0.9, -0.8), Vector3(0, 0.6, 0), player.bicycle)
		await shot("bike_stopped_left")
		back_to_player()
		await shot("bike_stopped_chase")
		print(player.toggle_bicycle())
		await ticks(12)
		await shot("bike_dismounting")
		await ticks(40)
		await shot("bike_dismounted")
	# Porch steps of the Cedar House: feet on the treads, never hovering or sunk.
	if want("steps"):
		player.position = Vector3(19, 0.2, 40.6)
		player.rotation = Vector3.ZERO
		player.camera.rotation.x = -0.2
		await ticks(30)
		Input.action_press("walk")
		Input.action_press("move_forward")
		for i in range(4):
			await ticks(22)
			look_from(Vector3(2.2, 0.9, 0.0), Vector3(0, 0.6, 0))
			await shot("steps_%d" % i)
			back_to_player()
			print("steps_%d: player y %.3f avatar y %.3f" % [i, player.global_position.y, player.avatar.global_position.y])
		release_all()
		await ticks(30)
		look_from(Vector3(2.2, 0.9, 0.3), Vector3(0, 0.6, 0))
		await shot("steps_standing")
		back_to_player()
	# Electric scooter (floorboard) and the car's in-car first-person view (V).
	if want("scooter"):
		player.session.active_vehicle = "scooter"
		player.replace_vehicle(Vector3(1.95, 0.05, -40))
		player.bicycle.rotation = Vector3.ZERO
		player.position = Vector3(2.9, 0.1, -40)
		player.rotation = Vector3.ZERO
		await ticks(20)
		print(player.toggle_bicycle())
		Input.action_press("move_forward")
		await ticks(60)
		look_from(Vector3(3.0, 1.0, 0.0), Vector3(0, 0.85, 0), player.bicycle)
		await shot("scooter_side")
		back_to_player()
		await shot("scooter_chase")
		release_all()
		Input.action_press("jump")
		await ticks(120)
		release_all()
		print(player.toggle_bicycle())
		await ticks(30)
	if want("car"):
		player.session.active_vehicle = "ace11"
		if not player.session.inventory.has("ace11"): player.session.inventory.append("ace11")
		player.replace_vehicle(Vector3(1.95, 0.05, -60))
		player.bicycle.rotation = Vector3.ZERO
		player.position = Vector3(4.0, 0.1, -60)
		player.rotation = Vector3.ZERO
		await ticks(20)
		print(player.toggle_bicycle())
		await ticks(30)
		await shot("car_chase")
		player.toggle_view()
		await ticks(30)
		await shot("car_first_person")
		player.toggle_view()
		await ticks(5)
	release_all()
	print("CAPTURE THIRD PERSON done")
	quit()

## A spot right in front of a house wall with the view pointing away from it.
func find_wall() -> Array:
	var space := player.get_world_3d().direct_space_state
	for z in range(0, -400, -6):
		for x in [-30.0, -22.0, 30.0, 22.0]:
			var from := Vector3(x, 1.2, float(z))
			var dir := Vector3(signf(x), 0, 0)
			var q := PhysicsRayQueryParameters3D.create(from, from + dir * 8.0, 1)
			var hit := space.intersect_ray(q)
			if hit.is_empty() or absf((hit.normal as Vector3).y) > 0.2: continue
			# A real wall: rays 0.7 m either side and 1 m higher hit it at the same depth.
			var flat := true
			for off: Vector3 in [Vector3(0, 0, 0.7), Vector3(0, 0, -0.7), Vector3(0, 1.0, 0)]:
				var q2 := PhysicsRayQueryParameters3D.create(from + off, from + off + dir * 8.0, 1)
				var h2 := space.intersect_ray(q2)
				if h2.is_empty() or absf((h2.position as Vector3).x - (hit.position as Vector3).x) > 0.05: flat = false
			if not flat: continue
			var at: Vector3 = (hit.position as Vector3) - dir * 1.0
			var down := PhysicsRayQueryParameters3D.create(at + Vector3(0, 0.5, 0), at + Vector3(0, -2, 0), 1)
			var g := space.intersect_ray(down)
			if g.is_empty(): continue
			# Facing away from the wall: the wall is behind the character, where the camera goes.
			return [Vector3(at.x, (g.position as Vector3).y + 0.05, at.z), atan2(dir.x, dir.z)]
	return [Vector3(-8, 0.1, 20), 0.0]
