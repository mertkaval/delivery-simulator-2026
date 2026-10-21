extends SceneTree
## Training shift (TutorialDirector) played start to finish through the game's own paths, plus
## the hold / put down / pick up mechanic and drag-and-drop packing into the open backpack:
## tasks advance in order, normal dispatch and rejecting are blocked while training, packing
## before the put-down task and delivering before packing are refused, a dropped package
## saves and reloads, and finishing pays the one-time bonus and turns dispatch back on.
var game
var failures := 0
var checks := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL: ") + what)
	if not ok: failures += 1

func _initialize() -> void: call_deferred("run")

func frames(n: int) -> void:
	for i in range(n): await process_frame

func wait_step(id: String) -> bool:
	for i in range(400):
		if game.tutorial.step_id() == id: return true
		await process_frame
	return false

func look_at_point(target: Vector3) -> void:
	var p: CourierPlayer = game.player
	var d := target - p.camera.global_position
	p.rotation.y = atan2(-d.x, -d.z)
	p.camera.rotation.x = atan2(d.y, Vector2(d.x, d.z).length())

func run() -> void:
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	await frames(10)
	var s: DeliverySession = game.session
	check(not game.tutorial.active(), "no training before New Game (old saves / tests stay untouched)")
	game.new_session()
	s = game.session
	var t: TutorialDirector = game.tutorial
	await frames(3)
	check(t.active() and t.step_id() == "look", "New Game starts training at 'Look around'")
	check(t.card.visible and t.card.header.text.contains("TASK 1 OF 12"), "mission card shows task 1 of 12")
	# Normal dispatch is off during training.
	s.next_offer = 0.0
	s.calendar_minutes = 720.0
	await frames(5)
	check(s.order.is_empty(), "no random offers while training")
	# 1 look, 2 walk
	for i in range(40):
		game.player.rotation.y += 0.08
		await process_frame
	check(await wait_step("walk"), "looking around completes task 1")
	for i in range(70):
		game.player.position.x += 0.25
		await physics_frame
	check(await wait_step("phone"), "walking completes task 2")
	# 3 phone, 4 map
	game.show_menu("phone")
	await frames(2)
	game.close_menu()
	check(await wait_step("map"), "opening and closing the phone completes task 3")
	game.show_menu("map")
	await frames(2)
	game.close_menu()
	check(await wait_step("bag"), "opening and closing the map completes task 4")
	check(CityNavigation.target.get("name", "") == "Trail & Tool", "minimap guides to Trail & Tool")
	# 5 bag
	game.buy_item("delivery_bag")
	game.close_menu()
	check(await wait_step("bike"), "buying the delivery bag completes task 5")
	# 6 bike
	game.player.position = game.player.bicycle.position + Vector3(1, 0.1, 0)
	game.notify(game.player.toggle_bicycle())
	check(await wait_step("accept"), "mounting the bike completes task 6")
	check(s.order.get("state") == "OFFERED" and s.restaurant_id() == "cedar_kitchen", "training sends the first order (Kebab House)")
	game.show_menu("phone")
	var reject_shown := false
	for c in game.modal_body.get_children():
		if c is Button and (c as Button).text.begins_with("Reject"): reject_shown = true
	check(not reject_shown, "the training order can't be rejected")
	s.clock += 200.0
	check(s.order.get("state") == "OFFERED", "the training order never times out")
	s.accept()
	game.close_menu()
	check(await wait_step("ride"), "accepting completes task 7")
	# 8 ride
	game.player.riding_speed = 0.0
	game.notify(game.player.toggle_bicycle())
	var rid := s.restaurant_id()
	var mine: Node3D = null
	var decoy: Node3D = null
	for pkg: Node3D in game.shelves.packages.get(rid, []):
		if pkg.get_meta("package").customer == s.order.customer: mine = pkg
		else: decoy = pkg
	check(mine != null and decoy != null, "your package and others' wait on the shelf")
	game.player.position = mine.global_position + Vector3(0.0, -1.0, 1.25)
	check(await wait_step("take"), "reaching the restaurant completes task 8")
	# 9 take (real ray + E)
	check(s.take_package(decoy.get_meta("package"), 1.0).begins_with("Wrong package"), "another customer's package is refused")
	look_at_point(mine.global_position + Vector3(0, 0.12, 0))
	for i in range(3): await physics_frame
	game.interact()
	check(s.holding_package(), "E on your package picks it up into your hands")
	await frames(2)
	check(is_instance_valid(game.held_package) and game.held_package.visible, "the package is held in view")
	check(await wait_step("drop"), "taking the right package completes task 9")
	# Gates: no packing before the put-down task, no delivering before packing.
	game.bag_click("top")
	check(s.holding_package(), "packing is refused until you've practised putting it down")
	# 10 drop / pick up
	look_at_point(game.player.global_position + Vector3(0, 0, -1.0))
	await physics_frame
	game.drop_held()
	check(s.order.get("state") == "DROPPED" and game.dropped_package != null, "G puts the package down in front of you")
	check(DeliverySession.validate(s.snapshot()), "a save with the package on the ground validates")
	var copy := DeliverySession.new()
	check(copy.restore(s.snapshot()) and copy.order.state == "DROPPED" and copy.dropped_position().is_equal_approx(s.dropped_position()), "the dropped package survives save/load")
	check(s.deliver(int(s.order.address), 1.0).contains("Pick it up first"), "you can't deliver from the ground")
	await create_timer(0.6).timeout      # let the put-down animation land
	look_at_point(game.dropped_package.global_position + Vector3(0, 0.1, 0))
	for i in range(3): await physics_frame
	game.interact()
	check(s.holding_package() and game.dropped_package == null, "E on the dropped package picks it up again")
	check(await wait_step("pack"), "put down + pick up completes task 10")
	# 11 drag and drop into the backpack
	game.show_menu("bag")
	await create_timer(0.7).timeout      # bag swings round
	var kind: String = s.order.kind
	var slot := OrderDetails.best_slot(kind)
	var cam: Camera3D = game.player.camera
	var screen := cam.unproject_position(game.bag_rig.slot_mouth(slot))
	check(game.bag_rig.pick(cam.project_ray_origin(screen), cam.project_ray_normal(screen)) == slot, "pointing at the %s picks that compartment" % slot)
	var wrong := "bottom" if slot != "bottom" else "top"
	game.bag_click(wrong)
	check(s.holding_package(), "dropping it into a compartment it doesn't fit is refused")
	game.bag_click(slot)
	check(s.order.get("state") == "CARRYING" and is_instance_valid(game.bag_rig.contents), "dropping it into the right compartment packs it")
	await create_timer(0.6).timeout
	game.bag_click(slot)
	check(s.holding_package() and is_instance_valid(game.held_package), "clicking the packed compartment lifts it back into your hands")
	await create_timer(0.6).timeout
	game.bag_click(slot)
	check(s.order.get("state") == "CARRYING", "and it can be packed again")
	game.close_menu()
	check(await wait_step("deliver"), "packing completes task 11")
	# 12 deliver
	var address := int(s.order.address)
	var facing: Vector3 = CityCatalog.address_facing(address)
	game.player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
	game.player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	game.player.camera.rotation = Vector3(-0.2, 0, 0)
	for i in range(3): await physics_frame
	var wallet_before := s.wallet
	game.interact()
	check(s.order.get("state") == "COMPLETED", "handing over at the door completes the delivery")
	game.close_menu()
	for i in range(200):
		if not t.active(): break
		await process_frame
	check(not t.active() and s.tutorial.done, "training finishes after the first delivery")
	check(s.ledger.get("bonus_tutorial", 0) == DeliverySession.TUTORIAL_BONUS and s.wallet > wallet_before, "the training bonus is paid once")
	check(DeliverySession.validate(s.snapshot()), "the finished save validates")
	check(t.gate("dispatch") == "" and t.gate("reject") == "", "after training, dispatch and rejecting are back")
	print("TUTORIAL PASS: %d checks, %d failures" % [checks, failures] if failures == 0 else "TUTORIAL FAIL: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
