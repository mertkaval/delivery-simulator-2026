extends SceneTree
## The MPFB v3 courier and its full clip set in the game:
## - the body is the v3 courier (clips.json), every PlayerAvatar role resolves to a clip, the run
##   gait is Run and the sprint gait is Sprint, ground speeds measured in Godot;
## - gestures (knock, doorbell, wave, eat / drink with the item in the right hand) play on the
##   action layer, end on their own and are cut short by moving;
## - standing idle starts a fidget (look round, shift weight, fold arms);
## - a real fall lands hard (Land_Hard), a hop does not;
## - getting on / off the bicycle plays Bike_Mount / Bike_Dismount in place, holds pedalling /
##   walking until the leg is over, then riding and walking work as before.
## godot --headless --path . --script res://tests/courier_actions_test.gd
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

func seconds(s: float) -> void:
	await ticks(int(round(s * 60.0)))

func stand_at(at: Vector3) -> void:
	player.position = at
	player.rotation = Vector3.ZERO
	player.velocity = Vector3.ZERO
	await ticks(40)

func run() -> void:
	root.size = Vector2i(1280, 720)
	GameSettings.path = "user://courier_actions_test_settings.cfg"
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	player = game.player
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	var a := player.avatar
	await stand_at(Vector3(-6.4, 0.1, 23))
	# Body and contract.
	var contract := a.contract()
	check(not a.placeholder and str(contract.get("model", "")).ends_with("courier.glb"), "the courier body is assets/player/courier.glb")
	check(int(contract.get("triangles", 0)) > 40000 and (contract.get("clips", {}) as Dictionary).size() >= 87, "the v3 courier contract: %d tris, %d clips" % [int(contract.get("triangles", 0)), (contract.get("clips", {}) as Dictionary).size()])
	var missing: Array[String] = []
	for role: String in PlayerAvatar.COURIER_CLIPS:
		if not a.has_clip(role): missing.append(role)
	check(missing.is_empty(), "every courier role has its clip (missing: %s)" % ", ".join(missing))
	check(a.clip("jog") == "Run" and a.clip("sprint") == "Sprint" and a.clip("walk") == "Walk", "gaits: Walk / Run / Sprint")
	var run_speed := a.clip_value("jog", "speed", 0.0)
	var sprint_speed := a.clip_value("sprint", "speed", 0.0)
	check(absf(run_speed - CourierPlayer.RUN_SPEED) < 0.5 and absf(sprint_speed - CourierPlayer.SPRINT_SPEED) < 0.4, "clip speeds fit the movement: Run %.2f m/s for %.1f, Sprint %.2f for %.1f" % [run_speed, CourierPlayer.RUN_SPEED, sprint_speed, CourierPlayer.SPRINT_SPEED])
	# Gestures.
	var length := a.play_gesture("knock_door", 0.0)
	await ticks(6)
	check(length > 1.0 and a.action_role == "knock_door" and a.action_weight > 0.0, "knocking plays Knock_Door on the action layer (%.2f s)" % length)
	await seconds(length + 0.4)
	check(a.gesture == "" and a.action_role == "" and is_nan(a.face_goal), "the knock ends by itself and releases the facing")
	a.play_gesture("wave", 0.0)
	Input.action_press("move_forward")
	await seconds(0.6)
	Input.action_release("move_forward")
	check(a.gesture == "" and a.action_role == "", "walking off cuts a wave short")
	await stand_at(Vector3(-6.4, 0.1, 23))
	length = a.play_gesture("eat_drink", NAN, -1.0, "water_bottle")
	await seconds(0.5)
	var item := a._hand_item
	check(length > 2.0 and item != null and item.visible and (item.get_node("water_bottle") as Node3D).visible, "drinking: Eat_Drink with the water bottle in the right hand")
	var to_hand := item.global_position.distance_to(a.skeleton.global_transform * a.skeleton.get_bone_global_pose(a.skeleton.find_bone("RightHand")).origin) if item != null else 9.0
	check(to_hand < 0.12, "the bottle sits in the right hand (%.3f m from the hand bone)" % to_hand)
	await seconds(length)
	check(item != null and not item.visible, "the item is put away when the clip ends")
	check(a.play_gesture("doorbell", 0.0) > 1.0, "ringing a doorbell plays Press_Doorbell")
	await seconds(1.6)
	# Idle fidgets.
	await stand_at(Vector3(-6.4, 0.1, 23))
	a._idle_for = 0.0
	await seconds(PlayerAvatar.FIDGET_AFTER + 0.5)
	check(a.gesture.begins_with("idle_"), "standing idle %.0f s starts a fidget (%s)" % [PlayerAvatar.FIDGET_AFTER, a.gesture])
	Input.action_press("move_forward")
	await seconds(0.4)
	Input.action_release("move_forward")
	check(a.gesture == "", "moving ends the fidget")
	# Landings.
	await stand_at(Vector3(-6.4, 3.4, 23))
	var waited := 0
	while not player.is_on_floor() and waited < 200:
		await physics_frame
		waited += 1
	await ticks(2)
	check(a.state == "Land" and a.hard_landing, "a 3 m fall lands hard (Land_Hard, %.1f m/s)" % player.last_fall_speed)
	await seconds(1.0)
	check(a.state == "Move", "back on its feet after the hard landing")
	Input.action_press("jump")
	await ticks(3)
	Input.action_release("jump")
	waited = 0
	await ticks(10)
	while not player.is_on_floor() and waited < 120:
		await physics_frame
		waited += 1
	await ticks(2)
	check(not a.hard_landing, "a hop lands softly (Jump_Land)")
	await seconds(0.8)
	# Bicycle: mount / dismount clips.
	player.session.active_vehicle = "bicycle"
	player.replace_vehicle(Vector3(1.95, 0.05, -40))
	player.bicycle.rotation = Vector3.ZERO
	await stand_at(Vector3(1.1, 0.1, -39.6))
	player.toggle_bicycle()
	await ticks(4)
	check(a.mount_locked() and a.state == "BikeMount", "getting on plays Bike_Mount (%.2f s at x%.1f)" % [a.clip_seconds("bike_mount"), PlayerAvatar.MOUNT_RATE])
	Input.action_press("move_forward")
	await seconds(a.clip_seconds("bike_mount") * 0.5)
	check(absf(player.riding_speed) < 0.05, "no pedalling while the leg swings over")
	await seconds(a.clip_seconds("bike_mount") * 0.5 + 1.2)
	check(not a.mount_locked() and a.state == "Bike" and player.riding_speed > 1.0, "then seated and riding (%.1f m/s)" % player.riding_speed)
	Input.action_release("move_forward")
	Input.action_press("jump")
	await seconds(2.0)
	Input.action_release("jump")
	await seconds(0.5)
	var msg := player.toggle_bicycle()
	await ticks(4)
	check(msg.contains("parked") and a.mount_locked() and a.state == "BikeDismount", "getting off plays Bike_Dismount (%s)" % msg)
	var at := player.global_position
	Input.action_press("move_forward")
	await seconds(a.clip_seconds("bike_dismount") * 0.6)
	check(player.global_position.distance_to(at) < 0.05, "the courier waits for the feet before walking off")
	await seconds(a.clip_seconds("bike_dismount") * 0.4 + 1.0)
	Input.action_release("move_forward")
	check(not a.mount_locked() and a.state == "Move" and player.global_position.distance_to(at) > 0.5, "then walks away (%.1f m)" % player.global_position.distance_to(at))
	print("COURIER ACTIONS %s: %d checks, %d failures" % ["PASS" if failures == 0 else "FAIL", checks, failures])
	quit(1 if failures > 0 else 0)
