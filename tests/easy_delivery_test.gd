extends SceneTree
## Easy delivery loop: randomised but deterministic pickup shelves (same order -> same layout,
## different orders -> different layouts, 4-7 decoys with unique names, sometimes look-alike
## names, yours always there and reachable by the interaction ray at the avenue counters, the
## corridor racks and the downtown racks), the wrong-package message, one-button pick-up + pack
## with the delivery bag (CARRYING after the sequence), carrying by hand without a bag, one-button
## leave at door and meet at door (from the bag and from the hands), left click as "use", and the
## worn backpack on the character (on the back, riding, first person, hidden when not owned).
## godot --headless --path . --script res://tests/easy_delivery_test.gd
var game: Node
var s: DeliverySession
var player: CourierPlayer
var failures := 0
var checks := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL: ") + what)
	if not ok: failures += 1

func _initialize() -> void: call_deferred("run")

func frames(n: int) -> void:
	for i in range(n): await process_frame

func physics(n: int) -> void:
	for i in range(n): await physics_frame

func aim_at(point: Vector3) -> void:
	var d := point - player.eye_position()
	player.rotation.y = atan2(-d.x, -d.z)
	player.camera.rotation = Vector3(atan2(d.y, Vector2(d.x, d.z).length()), 0, 0)

## A fresh accepted order at restaurant index `r` for `address`; the shelf restocks.
func new_order(r: int, address: int, method: String) -> void:
	game.close_menu()
	s.order = {}
	s.offer(10.0, r, address, method)
	s.order["expires"] = s.clock + 9999.0
	s.accept()
	await frames(3)

## Stand at your package's shelf spot and aim at it; true when the ray finds it.
func aim_mine() -> bool:
	var mine: Node3D = game.shelves.mine()
	if mine == null: return false
	player.position = game.shelves.stand_point(mine)
	player.velocity = Vector3.ZERO
	await physics(2)
	aim_at(game.shelves.look_point(mine))
	await physics(3)
	var t: Dictionary = player.target()
	if t.get("node") != mine:
		var q := PhysicsRayQueryParameters3D.create(player.eye_position(), game.shelves.look_point(mine), 1)
		q.exclude = [player.get_rid()]
		var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
		print("  (aim miss at %s: target %s, player at %s, package at %s, first hit %s %s)" % [s.restaurant_name(), t.get("id", "none"), player.global_position, mine.global_position, hit.get("collider", null), hit.get("position", null)])
	return t.get("node") == mine

func sequence_done() -> bool:
	var until := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < until:
		if not game.sequence.running: return true
		await process_frame
	return false

func signature(layout: Array) -> String:
	var parts := PackedStringArray()
	for e: Dictionary in layout:
		var xf: Transform3D = e.local
		parts.append("%s|%s|%s|%.3f,%.3f,%.3f|%.2f" % [e.details.customer, e.details.ticket, e.details.kind, xf.origin.x, xf.origin.y, xf.origin.z, xf.basis.get_euler().y])
	return ";".join(parts)

func run() -> void:
	root.size = Vector2i(1280, 720)
	GameSettings.path = "user://easy_delivery_test_settings.cfg"
	if FileAccess.file_exists(GameSettings.path): DirAccess.remove_absolute(ProjectSettings.globalize_path(GameSettings.path))
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	s = game.session
	player = game.player
	player.apply_view_settings(true, 3.2)
	player.view.snap()
	s.next_offer = 1e9
	await frames(5)
	var shelves: PickupShelves = game.shelves
	# --- Layout: deterministic per order, different between orders ---------------------------------
	await new_order(0, 0, "door")
	var rid := s.restaurant_id()
	var a := signature(shelves.plan(rid, s.order))
	var b := signature(shelves.plan(rid, s.order.duplicate(true)))
	check(a == b and a != "", "same order -> same shelf layout")
	var restocked := PackedStringArray()
	for pkg: Node3D in shelves.packages[rid]:
		var d: Dictionary = pkg.get_meta("package")
		var xf: Transform3D = pkg.get_meta("local")
		restocked.append("%s|%s|%s|%.3f,%.3f,%.3f|%.2f" % [d.customer, d.ticket, d.kind, xf.origin.x, xf.origin.y, xf.origin.z, xf.basis.get_euler().y])
	check(";".join(restocked) == a, "the shelf in the world shows that layout (a reloaded order rebuilds the same shelf)")
	var other := s.order.duplicate(true)
	other["id"] = "job_000777"
	other["ticket"] = "CE-777"
	check(signature(shelves.plan(rid, other)) != a, "a different order -> a different layout")
	# Many orders at every kind of shelf: yours always placed, 4-7 decoys, unique names, look-alikes.
	var look_alike := 0
	var kinds := {}
	var positions := {}
	var all_ok := true
	var decoys_ok := true
	var names_ok := true
	var tested := 0
	for r in [0, 1, 2, 3, 5, 8, 11, 14, 17, 20]:
		if r >= CityCatalog.RESTAURANTS.size(): continue
		var rr: String = CityCatalog.RESTAURANTS[r]
		if not shelves.shelves.has(rr): continue
		for k in range(6):
			var order := {"id": "job_%06d" % (100 + k * 7 + r), "customer": OrderDetails.random_customer(rng_for(r * 31 + k)), "ticket": "%s-%03d" % [rr.substr(0, 2).to_upper(), k * 37 + r],
				"kind": OrderDetails.package_kind(rr), "items": [["Dish", 1 + k % 3, 900]], "address": 0, "subtotal": 900, "payment_method": "Card · paid"}
			var layout := shelves.plan(rr, order)
			tested += 1
			var first: Dictionary = layout[0].details if not layout.is_empty() else {}
			var mine_found := false
			var seen := {}
			for e: Dictionary in layout:
				var who := str(e.details.customer)
				if who == str(order.customer) and str(e.details.ticket) == str(order.ticket): mine_found = true
				elif who == str(order.customer): names_ok = false
				if seen.has(who): names_ok = false
				seen[who] = true
				kinds[str(e.details.kind)] = true
				var o: Vector3 = (e.local as Transform3D).origin
				positions["%.2f,%.2f" % [o.x, o.y]] = true
				if who != str(order.customer):
					var p1 := who.split(" ")
					var p0 := str(order.customer).split(" ")
					if p1[0] == p0[0] or p1[p1.size() - 1] == p0[p0.size() - 1]: look_alike += 1
			if not mine_found: all_ok = false
			if layout.size() - 1 < PickupShelves.DECOYS_MIN or layout.size() - 1 > PickupShelves.DECOYS_MAX: decoys_ok = false
	check(all_ok, "your package is always on the shelf (%d orders, 3 kinds of shelf)" % tested)
	check(decoys_ok, "4-7 other couriers' orders on every shelf")
	check(names_ok, "never two packages with the same full name, never a decoy with yours")
	check(look_alike >= tested / 4, "look-alike names (same first or last name) show up often (%d in %d orders)" % [look_alike, tested])
	check(kinds.size() >= 2 and positions.size() > tested * 3, "varied package kinds (%s) and spots (%d)" % [", ".join(kinds.keys()), positions.size()])
	# --- Reachable by the interaction ray at the counter, a corridor rack and a downtown rack ------
	for r in [0, 2, 3, 6, 9, 15]:
		if r >= CityCatalog.RESTAURANTS.size(): continue
		var hits := 0
		for k in range(3):
			await new_order(r, 0, "door")
			if await aim_mine(): hits += 1
		check(hits == 3, "%s (%s): your package is reachable by the ray in every layout (%d/3)" % [CityCatalog.NAMES[r], shelves.shelves[CityCatalog.RESTAURANTS[r]].kind, hits])
	# --- Wrong package ------------------------------------------------------------------------------
	await new_order(0, 0, "door")
	var decoy: Node3D = null
	for pkg: Node3D in shelves.packages[s.restaurant_id()]:
		if decoy == null and not s.is_mine(pkg.get_meta("package")): decoy = pkg
	player.position = shelves.stand_point(decoy)
	await physics(2)
	aim_at(shelves.look_point(decoy))
	await physics(3)
	check(player.target().get("node") == decoy, "a decoy can be looked at")
	await frames(1)
	check(game.receipt_panel.visible and game.receipt_name.text.begins_with(str((decoy.get_meta("package") as Dictionary).customer).to_upper()), "looking at a package shows its tag big: " + game.receipt_name.text.replace("\n", " "))
	game.interact()
	var expect := "This one is for %s — you're looking for %s" % [(decoy.get_meta("package") as Dictionary).customer, s.order.customer]
	check(s.order.state == "ACCEPTED" and game.notice.text.begins_with(expect), "wrong package: '%s'" % game.notice.text)
	# --- Worn backpack ------------------------------------------------------------------------------
	var bp: WornBackpack = player.avatar.backpack
	check(bp != null and not bp.has_bag(), "no bag owned: nothing on the back")
	s.bag_upgrade = true
	s.ledger["upgrade_insulated_bag"] = -3500
	s.wallet -= 3500
	player.refresh_equipment()
	await physics(5)
	await frames(2)
	check(bp.has_bag() and bp.model.is_visible_in_tree() and bp.attachment.bone_name == "UpperChest" and bp.model.get_parent() == bp.attachment, "delivery bag worn: visible, on a BoneAttachment3D on the UpperChest")
	var chest: Vector3 = bp.attachment.global_position
	var to_bag := bag_centre(bp) - chest
	check(to_bag.length() < 0.6 and to_bag.dot(player.body_forward()) < -0.15, "the bag sits against the back (%.2f m from the chest, %.2f behind)" % [to_bag.length(), -to_bag.dot(player.body_forward())])
	# --- One-button pack with the bag ----------------------------------------------------------------
	await new_order(0, 0, "door")
	check(await aim_mine(), "aiming at your package")
	var roles := {}
	game.sequence.step_started.connect(func(r: String) -> void: roles[r] = true)
	game.interact()
	check(s.order.state == "IN_HAND" and game.sequence.running and game.sequence.kind == "pack" and player.busy, "E: picked up, the pack sequence plays, the courier stands still")
	var held_at := player.global_position
	Input.action_press("move_forward")
	await physics(20)
	Input.action_release("move_forward")
	check(player.global_position.distance_to(held_at) < 0.05, "no walking during the sequence")
	check(await sequence_done(), "the pack sequence finishes")
	check(s.order.state == "CARRYING" and s.order.slot == OrderDetails.best_slot(str(s.order.kind)) and not player.busy, "packed: CARRYING in the %s, free to move again" % s.order.slot)
	check(roles.has("bag_take_off") and roles.has("bag_pack") and roles.has("bag_put_on"), "Bag_TakeOff -> Bag_PackItem -> Bag_PutOn (%s)" % ", ".join(roles.keys()))
	check(bp.on_back and bp.model.get_parent() == bp.attachment, "the bag is back on the shoulders")
	# --- Leave at door --------------------------------------------------------------------------------
	await frames(3)
	var zone: DropZone = game.drop_zone
	var facing: Vector3 = CityCatalog.address_facing(int(s.order.address))
	player.position = zone.global_position + facing * 1.0 + Vector3(0, 0.1, 0)
	await physics(2)
	aim_at(zone.global_position)
	await physics(3)
	var before := s.wallet
	game.interact()
	check(game.sequence.running and game.sequence.kind == "leave", "E at the marked area: the leave-at-door sequence")
	roles.clear()
	check(await sequence_done(), "the leave-at-door sequence finishes")
	check(s.order.state == "COMPLETED" and s.order.get("proof") == "photo" and s.wallet > before, "left at the door with a proof photo, paid")
	check(roles.has("bag_take") and roles.has("place_down") and roles.has("photo") and (roles.has("bag_put_on") or roles.has("bag_put_on_holding") and roles.has("bag_strap_right")), "Bag_TakeItem -> (Bag_PutOn_Holding) -> PlaceDown -> photo -> Bag_PutOn / Bag_StrapRight (%s)" % ", ".join(roles.keys()))
	check(game.mode == "receipt", "the receipt shows after the sequence")
	game.close_menu()
	# --- Meet at door ----------------------------------------------------------------------------------
	await new_order(0, 3, "meet")
	check(await aim_mine(), "aiming at the next package")
	game.interact()
	await sequence_done()
	check(s.order.state == "CARRYING", "packed again")
	var address := int(s.order.address)
	facing = CityCatalog.address_facing(address)
	player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
	player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	player.camera.rotation = Vector3(-0.2, 0, 0)
	await physics(3)
	game.interact()
	await create_timer(1.6).timeout
	check(game.drop_zone != null and game.drop_zone.customer != null, "first E on the door knocks: the customer comes out")
	aim_at(game.drop_zone.customer.global_position + Vector3(0, 1.1, 0))
	await physics(3)
	before = s.wallet
	game.interact()
	check(game.sequence.running and game.sequence.kind == "meet", "E next to the customer: the handover sequence")
	roles.clear()
	check(await sequence_done(), "the handover sequence finishes")
	check(s.order.state == "COMPLETED" and s.wallet > before, "handed over in person, paid")
	check(roles.has("bag_take") and roles.has("handover") and (roles.has("bag_put_on") or roles.has("bag_put_on_holding") and roles.has("bag_strap_right")), "Bag_TakeItem -> (Bag_PutOn_Holding) -> Handover -> Bag_PutOn / Bag_StrapRight (%s)" % ", ".join(roles.keys()))
	game.close_menu()
	# --- Riding with the backpack on, first person ----------------------------------------------------
	s.active_vehicle = "bicycle"
	player.replace_vehicle(Vector3(1.95, 0.05, -40))
	player.bicycle.rotation = Vector3.ZERO
	player.position = Vector3(2.9, 0.1, -40)
	player.rotation = Vector3.ZERO
	await physics(10)
	player.toggle_bicycle()
	Input.action_press("move_forward")
	await physics(80)
	await frames(2)
	chest = bp.attachment.global_position
	to_bag = bag_centre(bp) - chest
	check(player.mounted and bp.model.is_visible_in_tree() and to_bag.length() < 0.7 and to_bag.dot(-player.bicycle.global_basis.z) < -0.1, "riding: the bag stays on the back (%.2f m from the chest)" % to_bag.length())
	Input.action_release("move_forward")
	Input.action_press("jump")
	await physics(100)
	Input.action_release("jump")
	player.toggle_bicycle()
	await physics(30)
	player.toggle_view()
	await frames(20)
	var shadow_only := true
	for gi: GeometryInstance3D in bp.model.find_children("*", "GeometryInstance3D", true, false):
		if gi.is_visible_in_tree() and gi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY: shadow_only = false
	check(shadow_only, "first person: the worn bag only casts its shadow (never in the view)")
	player.toggle_view()
	await frames(20)
	# --- Without a bag: carried by hand, handed over from the hands; left click works as E ------------
	s.bag_upgrade = false
	s.ledger.erase("upgrade_insulated_bag")
	player.refresh_equipment()
	check(not bp.has_bag(), "bag gone: nothing on the back")
	await new_order(0, 3, "meet")
	check(await aim_mine(), "aiming at the package (no bag)")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		game._unhandled_input(click)
		check(s.order.state == "IN_HAND", "left click takes it, like E")
	else:
		game.interact()
		check(s.order.state == "IN_HAND", "E takes it (left click needs a captured mouse: not available headless)")
	check(not game.sequence.running and game.notice.text.contains("carry it by hand"), "no bag: carried by hand, and the message says so")
	await physics(10)
	check(player.held_package() != null, "the package is in the hands")
	address = int(s.order.address)
	facing = CityCatalog.address_facing(address)
	player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
	player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	player.camera.rotation = Vector3(-0.2, 0, 0)
	await physics(3)
	game.interact()
	await create_timer(1.6).timeout
	aim_at(game.drop_zone.customer.global_position + Vector3(0, 1.1, 0))
	await physics(3)
	game.interact()
	check(await sequence_done() and s.order.state == "COMPLETED", "handed over from the hands")
	game.close_menu()
	if FileAccess.file_exists(GameSettings.path): DirAccess.remove_absolute(ProjectSettings.globalize_path(GameSettings.path))
	print(("EASY DELIVERY PASS: %d checks, %d failures" if failures == 0 else "EASY DELIVERY FAIL: %d checks, %d failures") % [checks, failures])
	quit(1 if failures > 0 else 0)

func bag_centre(bp: WornBackpack) -> Vector3:
	var box := AABB()
	var first := true
	for mi: MeshInstance3D in bp.model.find_children("*", "MeshInstance3D", true, false):
		if not mi.is_visible_in_tree(): continue
		var b := mi.global_transform * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	print("  bag box ", box, " chest ", bp.attachment.global_position)
	return box.get_center()

func rng_for(seed: int) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = seed
	return r
