extends SceneTree
## Rendered captures of the easy delivery loop: the phone order card (customer name first), the
## pickup shelf with its random layout and name tags (counter and rack), looking at a package
## (tag panel), a wrong package, the one-button pack sequence in third person, walking and riding
## with the backpack on, and the leave-at-door / meet-at-door sequences.
## godot --path . --script res://tests/capture_easy_delivery.gd -- <out_dir> [sections,...]
## sections: phone, shelf, rack, wrong, pack, walk, ride, leave, meet, fp
var out := "res://tmp"
var only := ""
var game: Node
var player: CourierPlayer
var s: DeliverySession
var free_cam: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(label: String) -> void:
	for i in range(2): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("%s/easy_%s.png" % [out, label])
	print("saved easy_%s" % label)

func ticks(n: int) -> void:
	for i in range(n): await physics_frame

func secs(t: float) -> void:
	await create_timer(t, true).timeout

func want(label: String) -> bool:
	return only == "" or only.split(",").has(label)

func look_from(offset_local: Vector3, at_local: Vector3, basis_node: Node3D = null) -> void:
	var b := basis_node if basis_node != null else player.avatar
	if free_cam.get_parent() != b: free_cam.reparent(b, false)
	free_cam.transform = Transform3D(Basis.looking_at(at_local - offset_local, Vector3.UP), offset_local)
	free_cam.make_current()

func back_to_player() -> void:
	player.camera.make_current()

func aim_at(point: Vector3) -> void:
	var d := point - player.eye_position()
	player.rotation.y = atan2(-d.x, -d.z)
	player.camera.rotation = Vector3(atan2(d.y, Vector2(d.x, d.z).length()), 0, 0)

## A fresh order at `restaurant` for `address`, accepted; the shelf restocks.
func new_order(restaurant: int, address: int, method: String) -> void:
	s.order = {}
	s.offer(10.0, restaurant, address, method)
	s.order["expires"] = s.clock + 9999.0
	s.accept()
	await ticks(3)
	for i in range(3): await process_frame

func stand_at_mine() -> Node3D:
	var mine: Node3D = game.shelves.mine()
	if mine == null: return null
	player.position = game.shelves.stand_point(mine)
	await ticks(2)
	aim_at(game.shelves.look_point(mine))
	player.avatar.facing = player.rotation.y
	await ticks(3)
	return mine

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0]
	if args.size() > 1: only = args[1]
	DirAccess.make_dir_recursive_absolute(out)
	GameSettings.path = "user://capture_easy_settings.cfg"
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	game.world.set_time(14.0)
	player = game.player
	s = game.session
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	free_cam = Camera3D.new()
	free_cam.fov = 50
	game.add_child(free_cam)
	# Owned: phone (economy 1), the delivery bag.
	s.bag_upgrade = true
	s.ledger["upgrade_insulated_bag"] = -3500
	s.wallet -= 3500
	player.refresh_equipment()
	s.online = true
	s.next_offer = 1e9
	# --- The phone: offer card and active-order card --------------------------------------------
	if want("phone"):
		player.position = Vector3(-9, 0.1, 16)
		await ticks(10)
		s.order = {}
		s.offer(10.0, 0, 0, "door")
		s.order["expires"] = s.clock + 9999.0
		game.show_menu("phone")
		print("phone: mode %s paused %s state %s" % [game.mode, paused, s.order.get("state")])
		for i in range(40): await process_frame
		game.phone.os.open_page("courier")
		for i in range(30): await process_frame
		await shot("phone_offer")
		game.on_phone_action("accept", "")
		for i in range(40): await process_frame
		await shot("phone_active")
		game.close_menu()
		for i in range(30): await process_frame
	# --- Kebab House counter: the random layout with name tags ----------------------------------
	if want("shelf") or want("wrong") or want("pack"):
		await new_order(0, 0, "door")
		var mine := await stand_at_mine()
		print("order for %s %s at %s, %d packages" % [s.order.customer, s.order.ticket, s.restaurant_name(), game.shelves.packages[s.restaurant_id()].size()])
		for p: Node3D in game.shelves.packages[s.restaurant_id()]:
			print("   ", (p.get_meta("package") as Dictionary).customer, "  ", (p.get_meta("package") as Dictionary).ticket, "  ", (p.get_meta("package") as Dictionary).kind, "  ", p.global_position)
		# Step back a little to see the whole counter run from the third-person camera.
		player.position += Vector3(0.6, 0, 0.5)
		aim_at(mine.global_position + Vector3(0.6, 0.0, 0))
		await ticks(40)
		await shot("shelf_tp")
		# Free view of the counter run at reading distance (~1.6 m).
		var mid: Vector3 = mine.global_position
		free_cam.reparent(game, false)
		var frame: Transform3D = game.shelves.shelves[s.restaurant_id()].frame
		free_cam.global_transform = Transform3D(Basis.looking_at(frame * Vector3(-2.1, 1.2, 0) - frame * Vector3(-2.1, 1.75, 1.9), Vector3.UP), frame * Vector3(-2.1, 1.75, 1.9))
		free_cam.make_current()
		await shot("shelf_tags")
		back_to_player()
		mine = await stand_at_mine()
		await ticks(40)
		await shot("shelf_aim_mine")
		if want("wrong") or want("shelf"):
			# Look at a decoy: the tag panel; take it: the wrong-package message.
			var decoy: Node3D = null
			for p: Node3D in game.shelves.packages[s.restaurant_id()]:
				if p != mine and decoy == null: decoy = p
			player.position = game.shelves.stand_point(decoy)
			await ticks(2)
			aim_at(game.shelves.look_point(decoy))
			await ticks(30)
			await shot("receipt_decoy")
			game.interact()
			await ticks(5)
			await shot("wrong_package")
	# --- One-button pack (third person) ---------------------------------------------------------
	if want("pack"):
		var mine := await stand_at_mine()
		await ticks(30)
		game.notify("")
		game.interact()
		var t0 := Time.get_ticks_msec()
		var frames := 0
		while game.sequence.running and frames < 8:
			await secs(0.42)
			await shot("pack_%d" % frames)
			print("   pack_%d  t=%.2f s  step %s  state %s" % [frames, (Time.get_ticks_msec() - t0) / 1000.0, game.sequence.role, s.order.state])
			frames += 1
		await secs(0.5)
		print("after pack: state %s slot %s" % [s.order.state, s.order.get("slot", "")])
		await shot("pack_done")
		# The same pack seen from the side (free camera riding along).
		await new_order(0, 0, "door")
		mine = await stand_at_mine()
		await ticks(20)
		game.interact()
		var k := 0
		while game.sequence.running and k < 8:
			await secs(0.42)
			look_from(Vector3(-2.4, 1.25, -0.25), Vector3(0, 0.95, -0.25))
			await shot("pack_side_%d" % k)
			back_to_player()
			k += 1
		await secs(0.5)
	# --- Walking with the backpack on -----------------------------------------------------------
	if want("walk"):
		player.position = Vector3(-6.4, 0.1, 23)
		player.rotation = Vector3.ZERO
		player.camera.rotation = Vector3(-0.22, 0, 0)
		await ticks(20)
		Input.action_press("move_forward")
		await ticks(60)
		await shot("walk_backpack")
		look_from(Vector3(2.6, 1.2, 0.4), Vector3(0, 1.0, 0))
		await shot("walk_backpack_side")
		look_from(Vector3(1.4, 1.5, 2.4), Vector3(0, 1.1, 0))
		await shot("walk_backpack_back")
		back_to_player()
		Input.action_press("sprint")
		await ticks(40)
		look_from(Vector3(2.8, 1.1, 0.3), Vector3(0, 1.0, 0))
		await shot("run_backpack_side")
		back_to_player()
		Input.action_release("sprint")
		Input.action_release("move_forward")
		await ticks(30)
	# --- Riding the bicycle with the backpack ---------------------------------------------------
	if want("ride"):
		s.active_vehicle = "bicycle"
		player.replace_vehicle(Vector3(1.95, 0.05, -40))
		player.bicycle.rotation = Vector3.ZERO
		player.position = Vector3(2.9, 0.1, -40)
		player.rotation = Vector3.ZERO
		await ticks(30)
		print(player.toggle_bicycle())
		Input.action_press("move_forward")
		await ticks(120)
		await shot("ride_chase")
		look_from(Vector3(3.0, 1.1, 0.2), Vector3(0, 1.0, 0), player.bicycle)
		await shot("ride_side")
		look_from(Vector3(1.6, 1.7, 2.6), Vector3(0, 1.1, 0), player.bicycle)
		await shot("ride_back")
		back_to_player()
		Input.action_release("move_forward")
		Input.action_press("jump")
		await ticks(120)
		Input.action_release("jump")
		print(player.toggle_bicycle())
		await ticks(40)
	# --- Leave at door ----------------------------------------------------------------------------
	if want("leave"):
		await new_order(0, 0, "door")
		var mine := await stand_at_mine()
		game.interact()
		while game.sequence.running: await secs(0.1)
		print("packed: ", s.order.state)
		var address := int(s.order.address)
		await ticks(5)
		var zone: DropZone = game.drop_zone
		var facing: Vector3 = CityCatalog.address_facing(address)
		player.position = zone.global_position + facing * 1.1 + Vector3(0, 0.1, 0)
		await ticks(3)
		aim_at(zone.global_position)
		player.camera.rotation.x = -0.35
		player.avatar.facing = player.rotation.y
		await ticks(30)
		await shot("leave_before")
		game.interact()
		var k := 0
		while game.sequence.running and k < 10:
			await secs(0.45)
			await shot("leave_%d" % k)
			print("   leave_%d step %s state %s" % [k, game.sequence.role, s.order.state])
			k += 1
		await secs(0.3)
		await shot("leave_receipt")
		game.close_menu()
		await secs(0.3)
		look_from(Vector3(1.6, 1.4, -1.6), Vector3(0, 0.3, -0.9))
		await shot("leave_left_package")
		back_to_player()
	# --- Meet at door -----------------------------------------------------------------------------
	if want("meet"):
		await new_order(0, 3, "meet")
		var mine := await stand_at_mine()
		game.interact()
		while game.sequence.running: await secs(0.1)
		var address := int(s.order.address)
		var facing: Vector3 = CityCatalog.address_facing(address)
		player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
		player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
		player.camera.rotation = Vector3(-0.2, 0, 0)
		await ticks(5)
		game.interact()
		await secs(1.6)
		var cust: Node3D = game.drop_zone.customer
		aim_at(cust.global_position + Vector3(0, 1.1, 0))
		player.avatar.facing = player.rotation.y
		await ticks(20)
		await shot("meet_customer")
		game.interact()
		var k := 0
		while game.sequence.running and k < 10:
			await secs(0.42)
			await shot("meet_%d" % k)
			if k == 3:
				look_from(Vector3(2.2, 1.4, -0.6), Vector3(0, 1.1, -0.6))
				await shot("meet_side")
				back_to_player()
			print("   meet_%d step %s state %s" % [k, game.sequence.role, s.order.state])
			k += 1
		await secs(0.3)
		await shot("meet_receipt")
		game.close_menu()
	# --- First person: the existing bag view during the pack -------------------------------------
	if want("fp"):
		await new_order(0, 0, "door")
		player.toggle_view()
		var mine := await stand_at_mine()
		await ticks(20)
		game.interact()
		var k := 0
		while game.sequence.running and k < 6:
			await secs(0.4)
			await shot("fp_pack_%d" % k)
			k += 1
		player.toggle_view()
	print("CAPTURE EASY DELIVERY done")
	quit()
