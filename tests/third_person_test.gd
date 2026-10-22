extends SceneTree
## Third-person courier: V toggles first / third person and is remembered; mouse-wheel zoom is
## clamped; the camera's SpringArm3D pulls in at a wall; E still targets doors and the pickup
## shelf from third person (ray from the head along the view); W moves relative to the camera
## and the body turns towards travel; a jump goes airborne -> lands -> back to locomotion with
## the body on the ground; on the bicycle the hips sit on the Seat marker, palms on the grips
## and the balls of the feet on the pedals (within 3 cm), the crank turns with speed and stops
## when coasting; dismounting returns the body to its feet.
## godot --headless --path . --script res://tests/third_person_test.gd
var failures := 0
var checks := 0
var game: Node
var player: CourierPlayer

func check(ok: bool, what: String) -> void:
	checks += 1
	if ok: print("PASS " + what)
	else:
		failures += 1
		print("FAIL: " + what)

func _initialize() -> void: call_deferred("run")

func ticks(n: int) -> void:
	for i in range(n): await physics_frame
	await process_frame

func press(action: String) -> void:
	var e := InputEventAction.new()
	e.action = action
	e.pressed = true
	player._unhandled_input(e)

func wheel(up: bool) -> void:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_WHEEL_UP if up else MOUSE_BUTTON_WHEEL_DOWN
	e.pressed = true
	player._unhandled_input(e)

func camera_distance() -> float:
	return player.camera.global_position.distance_to(player.eye_position())

func run() -> void:
	root.size = Vector2i(1280, 720)
	var settings_path := "user://third_person_test_settings.cfg"
	GameSettings.path = settings_path
	if FileAccess.file_exists(settings_path): DirAccess.remove_absolute(ProjectSettings.globalize_path(settings_path))
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	player = game.player
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	player.position = Vector3(-8, 0.1, 20)
	player.rotation = Vector3.ZERO
	player.camera.rotation = Vector3(-0.2, 0, 0)
	await ticks(30)
	check(player.avatar != null and player.avatar.ready_ok and player.avatar.skeleton != null, "the courier has a visible animated body (%s)" % ("courier.glb" if not player.avatar.placeholder else "placeholder"))
	check(player.third_person and camera_distance() > 2.0, "third person is the default: camera %.2f m from the eyes" % camera_distance())
	var behind := player.global_basis.inverse() * (player.camera.global_position - player.eye_position())
	check(behind.z > 1.5 and behind.x > 0.1, "camera behind and over the right shoulder (%s)" % behind)
	check(player.avatar.visible and player.avatar._visible_mode == 0, "body fully visible in third person")
	# --- V toggles and persists ---
	press("camera_view")
	await ticks(30)
	var cfg := ConfigFile.new()
	cfg.load(settings_path)
	check(not player.third_person and not bool(GameSettings.get_value("third_person")) and cfg.get_value("options", "third_person", true) == false, "V switches to first person and saves it")
	check(camera_distance() < 0.05, "first person camera at the eyes (%.3f m)" % camera_distance())
	check(player.avatar._visible_mode == 1, "first person: body casts its shadow only (no head in view)")
	press("camera_view")
	await ticks(30)
	cfg.load(settings_path)
	check(player.third_person and cfg.get_value("options", "third_person", false) == true and camera_distance() > 2.0, "V back to third person, saved")
	GameSettings.load_settings()
	check(bool(GameSettings.get_value("third_person")), "the choice survives a settings reload")
	# --- Phone / backpack views: the camera blends to the eyes while they are out, then back ---
	game.show_menu("phone")
	await create_timer(0.6, true).timeout
	check(game.mode == "phone" and camera_distance() < 0.05 and player.avatar._visible_mode == 1, "phone out: first-person view for the 3D phone (camera %.3f m from the eyes)" % camera_distance())
	game.close_menu()
	await create_timer(0.6, true).timeout
	check(camera_distance() > 2.0 and player.avatar._visible_mode == 0, "phone away: back to third person")
	if not game.session.inventory.has("delivery_bag"): game.session.inventory.append("delivery_bag")
	game.show_menu("bag")
	await create_timer(0.6, true).timeout
	check(game.mode == "bag" and camera_distance() < 0.05, "backpack open: first-person view of the open bag")
	game.close_menu()
	await create_timer(0.6, true).timeout
	check(camera_distance() > 2.0, "backpack closed: back to third person")
	# --- The delivery bag on the back (owned above): worn scene on the UpperChest, straps, arm variants ---
	player.refresh_equipment()
	await ticks(10)
	var bp: WornBackpack = player.avatar.backpack
	check(bp.has_bag() and bp.model.is_visible_in_tree() and bp.attachment.bone_name == "UpperChest", "owned delivery bag worn on the back (BoneAttachment3D on UpperChest)")
	if bp.scene_mode():
		check(bp.straps.size() == 2 and bp.straps.all(func(n: Node3D) -> bool: return n.visible), "body straps shown while the bag is worn")
		check(player.avatar.bag_worn and player.avatar.worn_clip("Walk") == "Walk_Bag" and player.avatar.worn_clip(player.avatar.clip("idle")) == "Bag_Worn_Idle", "locomotion uses the arms-round-the-bag variants (Walk_Bag, Bag_Worn_Idle)")
	# --- Zoom clamps ---
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	for i in range(40): player.view.zoom(-1.0)
	check(is_equal_approx(player.view.target_distance, PlayerCameraRig.MIN_DISTANCE), "zoom in stops at %.1f m" % player.view.target_distance)
	for i in range(60): player.view.zoom(1.0)
	check(is_equal_approx(player.view.target_distance, PlayerCameraRig.MAX_DISTANCE), "zoom out stops at %.1f m" % player.view.target_distance)
	player.view.target_distance = 3.2
	if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		wheel(true)
		check(player.view.target_distance < 3.2, "mouse wheel up zooms in (%.2f)" % player.view.target_distance)
	player.view.target_distance = 3.2
	await ticks(40)
	check(absf(player.view.distance - 3.2) < 0.05, "zoom eases to the wanted distance")
	# --- Spring arm at a wall ---
	var wall := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(8, 5, 0.3)
	shape.shape = box
	wall.add_child(shape)
	game.world.add_child(wall)
	player.position = Vector3(-8, 0.1, 20)
	player.rotation = Vector3.ZERO
	wall.global_position = Vector3(-8, 2.0, 21.4)
	await ticks(30)
	var cam_z := player.camera.global_position.z
	check(player.view.clear < 1.4 and cam_z < 21.4 - 0.15 - 0.05, "camera pulled in front of a wall behind the player (arm %.2f of %.2f, camera z %.2f)" % [player.view.clear, player.view.arm_length, cam_z])
	wall.queue_free()
	await ticks(60)
	check(player.view.clear > player.view.arm_length - 0.05, "camera eases back out once the wall is gone")
	# --- Interaction from third person ---
	var facing: Vector3 = CityCatalog.address_facing(0)
	player.position = game.world.doors[0] + facing * 1.6 + Vector3(0, -0.92, 0)
	player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	player.camera.rotation = Vector3(-0.2, 0, 0)
	await ticks(3)
	check(camera_distance() > 1.0 and str(player.target().get("id", "")) == "door_0", "E reaches a door from third person (%s)" % str(player.target().get("id", "none")))
	game.session.offer()
	game.session.accept()
	player.position = Vector3(-14, 0.08, 13.8)
	player.rotation = Vector3.ZERO
	player.camera.rotation.x = -0.3
	await ticks(3)
	var t: Dictionary = player.target()
	check(str(t.get("id", "")) in ["pickup", "package"] and float(t.get("distance", 9.0)) <= 2.0, "E reaches the pickup shelf from third person (%s, %.2f m from the head)" % [str(t.get("id", "none")), float(t.get("distance", -1.0))])
	game.session.order = {}
	# --- Camera-relative movement, body turns ---
	player.position = Vector3(-8, 0.1, 10)
	player.rotation = Vector3(0, 1.0, 0)
	player.avatar.facing = -2.0
	await ticks(5)
	Input.action_press("move_forward")
	await ticks(60)
	var v := Vector3(player.velocity.x, 0, player.velocity.z)
	var cam_fwd := -player.global_basis.z
	check(v.length() > 3.0 and v.normalized().dot(cam_fwd) > 0.97, "W runs where the camera looks (%.1f m/s, dot %.2f)" % [v.length(), v.normalized().dot(cam_fwd) if v.length() > 0.01 else 0.0])
	check(absf(angle_difference(player.avatar.facing, 1.0)) < 0.1, "the body turned to face the way it runs (%.2f rad off)" % absf(angle_difference(player.avatar.facing, 1.0)))
	var rate := float(player.avatar.tree.get("parameters/Move/rate/scale"))
	var stride: float = player.avatar.blended_stride()
	check(absf(rate * stride - v.length()) < 0.25, "locomotion plays at ground speed (cycle %.2f/s x stride %.2f m = %.2f m/s vs %.2f)" % [rate, stride, rate * stride, v.length()])
	await ticks(30)
	var steps := player.avatar.step_count
	await ticks(60)
	steps = player.avatar.step_count - steps
	check(steps >= 2 and steps <= 4, "footsteps on the foot contacts (%d in 1 s at %.2f cycles/s)" % [steps, rate])
	Input.action_release("move_forward")
	await ticks(40)
	var ground_gap := player.avatar.global_position.y - player.global_position.y
	check(absf(ground_gap + player.avatar.sole_lift) < 0.05 and player.avatar.state == "Move", "standing: body on the ground (%.3f m)" % ground_gap)
	# --- Turn in place: the view swings 100 degrees left while standing ---
	var face0 := player.avatar.facing
	player.rotation.y = face0 + deg_to_rad(100.0)
	var turn_states := {}
	for i in range(120):
		await physics_frame
		turn_states[player.avatar.state] = true
	var turned_by := angle_difference(face0, player.avatar.facing)
	var stepped := turn_states.keys().any(func(k: String) -> bool: return k.begins_with("Turn_"))
	check(turned_by > deg_to_rad(60.0) and (stepped or player.avatar.placeholder), "standing: the body steps round towards the view (%.0f deg%s)" % [rad_to_deg(turned_by), ", step-turn clip" if stepped else ""])
	# --- Jump ---
	var seen := {}
	Input.action_press("jump")
	await ticks(1)
	Input.action_release("jump")
	var left_floor := false
	for i in range(80):
		await physics_frame
		seen[player.avatar.state] = true
		if not player.is_on_floor(): left_floor = true
	await ticks(30)
	check(left_floor and (seen.has("JumpStart") or seen.has("Air")), "Space jumps: airborne with the take-off / air pose (%s)" % str(seen.keys()))
	check(seen.has("Land") and player.is_on_floor() and player.avatar.state == "Move", "lands, recovers and returns to locomotion")
	# --- Bicycle ---
	player.session.active_vehicle = "bicycle"
	player.replace_vehicle(Vector3(1.95, 0.05, -40))
	player.bicycle.rotation = Vector3.ZERO
	player.position = Vector3(2.9, 0.1, -40)
	player.rotation = Vector3.ZERO
	await ticks(10)
	var msg: String = player.toggle_bicycle()
	check(player.mounted, "mounts the bicycle: " + msg)
	await ticks(10)
	check(player.avatar.mount_t < 1.0 or player.avatar.seat_blend < 1.0, "mounting blends onto the saddle (no teleport)")
	Input.action_press("move_forward")
	await ticks(90)
	var m := player.bike_markers
	var ik := player.avatar.ik
	var up := player.bicycle.global_basis.y.normalized()
	check(not m.is_empty() and m.has("Seat") and m.has("Crank"), "bicycle rider markers found (%s)" % ("measured fallback" if m.get("temporary", true) else "model's own Seat/Grip/Crank/Pedal nodes"))
	var hips: Vector3 = ik.solved.get("hips", Vector3.ZERO)
	var seat: Vector3 = (m.Seat as Node3D).global_position
	check(hips.distance_to(ik.hips_target) < 0.02 and (hips - seat).dot(up) > 0.08 and (hips - seat).dot(up) < 0.2, "hips on the saddle (%.3f m above the Seat marker, %.3f m from target)" % [(hips - seat).dot(up), hips.distance_to(ik.hips_target)])
	for side in ["l_", "r_"]:
		var grip: Vector3 = (m["GripL" if side == "l_" else "GripR"] as Node3D).global_position
		var palm: Vector3 = ik.solved.get(side + "palm", Vector3.ZERO)
		check(palm.distance_to(grip) < 0.03, "%s hand on its grip (palm %.3f m from the grip)" % ["left" if side == "l_" else "right", palm.distance_to(grip)])
		var pedal: Vector3 = (m["PedalL" if side == "l_" else "PedalR"] as Node3D).global_position
		var ball: Vector3 = ik.solved.get(side + "ball", Vector3.ZERO)
		check(ball.distance_to(pedal + up * player.avatar.pedal_ball_height) < 0.03, "%s foot on its pedal (%.3f m)" % ["left" if side == "l_" else "right", ball.distance_to(pedal + up * player.avatar.pedal_ball_height)])
	var c0 := player.crank_angle
	var z0 := player.global_position
	await ticks(30)
	var turned := player.crank_angle - c0
	var expected := player.global_position.distance_to(z0) / 0.35 / CourierPlayer.GEAR_RATIO
	check(turned > 0.5 and absf(turned - expected) < expected * 0.15, "crank turns with the wheels (%.2f rad, expected %.2f)" % [turned, expected])
	Input.action_release("move_forward")
	await ticks(70)
	var c1 := player.crank_angle
	await ticks(20)
	check(player.riding_speed > 0.4 and absf(player.crank_angle - c1) < 0.01, "coasting: wheels roll (%.1f m/s), crank still" % player.riding_speed)
	Input.action_press("jump")
	await ticks(90)
	Input.action_release("jump")
	await ticks(5)
	msg = player.toggle_bicycle()
	check(not player.mounted, "dismounts: " + msg)
	await ticks(60)
	var gap := player.avatar.global_position.y - player.global_position.y
	check(player.avatar.state == "Move" and player.avatar.ik.seat_weight < 0.01 and absf(gap) < 0.08, "back on its feet beside the bike (%s, seat %.2f, %.3f m)" % [player.avatar.state, player.avatar.ik.seat_weight, gap])
	if FileAccess.file_exists(settings_path): DirAccess.remove_absolute(ProjectSettings.globalize_path(settings_path))
	print(("THIRD PERSON PASS: %d checks, %d failures" if failures == 0 else "THIRD PERSON: %d checks, %d failures") % [checks, failures])
	quit(1 if failures > 0 else 0)
