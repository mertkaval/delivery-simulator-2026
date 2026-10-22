extends SceneTree
## Rendered captures of the in-game HUD (HudStyle) in the situations where most of it is on screen:
## walking with the training card and an order, the shelf with the name tag panel, an order
## outside training (order chip, backpack line), riding, the phone, meeting the customer.
## godot --path . --script res://tests/capture_hud.gd -- <out_dir> [prefix] [sections,...|all] [WxH]
## sections: train, shelf, order, ride, phone, meet, bag, receipt, goal
var out := "res://tmp"
var prefix := "hud"
var only := ""
var game: Node
var player: CourierPlayer
var s: DeliverySession

func _initialize() -> void: call_deferred("run")

func shot(label: String) -> void:
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	img.save_png("%s/%s_%s.png" % [out, prefix, label])
	print("saved %s_%s (%dx%d)" % [prefix, label, img.get_width(), img.get_height()])

func ticks(n: int) -> void:
	for i in range(n): await physics_frame

func want(label: String) -> bool:
	return only == "" or only.split(",").has(label)

func aim_at(point: Vector3) -> void:
	var d := point - player.eye_position()
	player.rotation.y = atan2(-d.x, -d.z)
	player.camera.rotation = Vector3(atan2(d.y, Vector2(d.x, d.z).length()), 0, 0)

func new_order(restaurant: int, address: int, method: String) -> void:
	s.order = {}
	s.offer(10.0, restaurant, address, method)
	s.order["expires"] = s.clock + 9999.0
	s.accept()
	await ticks(3)
	for i in range(3): await process_frame

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0]
	if args.size() > 1: prefix = args[1]
	if args.size() > 2 and args[2] != "all": only = args[2]
	DirAccess.make_dir_recursive_absolute(out)
	GameSettings.path = "user://capture_hud_settings.cfg"
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	if args.size() > 3:
		# Window size, e.g. 1280x720 (the game's settings start it fullscreen).
		var wh := args[3].split("x")
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		for i in range(5): await process_frame
		DisplayServer.window_set_size(Vector2i(int(wh[0]), int(wh[1])))
		for i in range(5): await process_frame
	game.world.set_time(13.0)
	player = game.player
	s = game.session
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	s.bag_upgrade = true
	s.ledger["upgrade_insulated_bag"] = -3500
	s.wallet = 4000
	player.refresh_equipment()
	s.online = true
	s.next_offer = 1e9
	s.calendar_minutes = 12 * 60
	s.energy = 71
	s.hunger = 97
	s.hydration = 64
	s.bladder = 22
	# --- Training: find the package (task 10 of 13), walking on the sidewalk -------------------
	if want("train") or want("shelf"):
		s.tutorial = {"done": false, "step": game.tutorial.index_of("take"), "v": 3}
		await new_order(0, 0, "door")
		game.notify("Accepted · go to " + s.restaurant_name())
		player.position = Vector3(-6.4, 0.1, 6)
		player.rotation = Vector3(0, PI * 0.5, 0)
		player.camera.rotation = Vector3(-0.15, 0, 0)
		player.view.snap()
		await ticks(30)
		if want("train"): await shot("train_walk")
		if want("shelf"):
			var mine: Node3D = game.shelves.mine()
			var decoy: Node3D = null
			for p: Node3D in game.shelves.packages[s.restaurant_id()]:
				if p != mine and decoy == null: decoy = p
			player.position = game.shelves.stand_point(decoy)
			await ticks(2)
			aim_at(game.shelves.look_point(decoy))
			player.avatar.facing = player.rotation.y
			await ticks(30)
			await shot("shelf_tag")
			game.interact()
			await ticks(5)
			await shot("shelf_wrong")
		s.tutorial = {"done": true, "step": 13, "v": 3}
		game.tutorial.card.hide()
	s.tutorial = {"done": true, "step": 13, "v": 3}
	# --- Outside training: carrying an order (order chip, backpack, nav, supplies) ---------------
	if want("order"):
		await new_order(0, 5, "meet")
		s.order["state"] = "CARRYING"
		s.order["slot"] = "top"
		s.supplies["water_bottle"] = 2
		s.supplies["energy_bar"] = 1
		game.notify("Packed in the top compartment.  Deliver to %s · %s." % [s.order.customer, DeliverySession.ADDRESSES[int(s.order.address)]])
		player.position = Vector3(-6.4, 0.1, 20)
		player.rotation = Vector3.ZERO
		player.camera.rotation = Vector3(-0.12, 0, 0)
		player.view.snap()
		await ticks(30)
		await shot("order_walk")
		s.supplies.clear()
	# --- Riding the bicycle ---------------------------------------------------------------------
	if want("ride"):
		s.active_vehicle = "bicycle"
		for z in [-40.0, -60.0, -30.0, -75.0, 30.0]:
			player.replace_vehicle(Vector3(1.95, 0.05, z))
			player.bicycle.rotation = Vector3.ZERO
			player.position = Vector3(2.9, 0.1, z)
			player.rotation = Vector3.ZERO
			await ticks(30)
			var said := player.toggle_bicycle()
			print("mount at z %.0f: %s" % [z, said])
			if player.mounted: break
		Input.action_press("move_forward")
		await ticks(120)
		await shot("ride")
		Input.action_release("move_forward")
		Input.action_press("jump")
		await ticks(120)
		Input.action_release("jump")
		print(player.toggle_bicycle())
		await ticks(20)
	# --- Phone ----------------------------------------------------------------------------------
	if want("phone"):
		s.order = {}
		s.offer(10.0, 0, 2, "door")
		s.order["expires"] = s.clock + 9999.0
		player.position = Vector3(-9, 0.1, 16)
		await ticks(10)
		game.show_menu("phone")
		for i in range(40): await process_frame
		game.phone.os.open_page("courier")
		for i in range(30): await process_frame
		await shot("phone")
		game.close_menu()
		for i in range(10): await process_frame
	# --- Meet at the door: customer out, notice, prompt -------------------------------------------
	if want("meet"):
		await new_order(0, 3, "meet")
		s.order["state"] = "CARRYING"
		s.order["slot"] = "top"
		await ticks(5)
		var address := int(s.order.address)
		var facing: Vector3 = CityCatalog.address_facing(address)
		player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
		player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
		player.camera.rotation = Vector3(-0.2, 0, 0)
		await ticks(5)
		game.interact()
		await create_timer(1.6, true).timeout
		var cust: Node3D = game.drop_zone.customer
		if cust:
			aim_at(cust.global_position + Vector3(0, 1.1, 0))
			player.avatar.facing = player.rotation.y
		game.notify(game.at_door())
		await ticks(20)
		await shot("meet")
	# --- Backpack open and the delivery receipt (modal menus) -------------------------------------
	if want("bag"):
		await new_order(0, 5, "meet")
		s.order["state"] = "CARRYING"
		s.order["slot"] = "top"
		await ticks(5)
		game.show_menu("bag")
		for i in range(30): await process_frame
		await shot("bag")
		game.close_menu()
		await ticks(5)
	if want("receipt"):
		s.receipt = "Delivered to Liam Arslan · 122 Atatürk Avenue
Fare $6.35  ·  Tip $2.00
Handed to Liam Arslan in person."
		game.show_menu("receipt")
		for i in range(10): await process_frame
		await shot("receipt")
		game.close_menu()
		await ticks(5)
	# --- After training: the bicycle goal card ----------------------------------------------------
	if want("goal"):
		s.order = {}
		s.economy = 2
		s.active_vehicle = ""
		s.tutorial = {"done": true, "step": 13, "v": 3}
		game.tutorial.card.finished = false
		player.position = Vector3(-6.4, 0.1, 20)
		player.rotation = Vector3.ZERO
		await ticks(30)
		await shot("goal")
	print("CAPTURE HUD done")
	quit()
