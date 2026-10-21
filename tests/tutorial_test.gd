extends SceneTree
## A New Game career start played through the game's own paths: on foot with $100 and no
## bike; the store computer (cart, purchase) and the pickup shelf; the 3D phone (screen taps)
## and the CourierNow app; the training orders (leave at door into the marked area, meet at
## door: knock, customer comes out, hand over with E); hold / put down / drag-and-drop packing;
## the training gates; the bonus and the bicycle goal afterwards.
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
	print("  (still at '%s')" % game.tutorial.step_id())
	return false

func look_at_point(target: Vector3) -> void:
	var p: CourierPlayer = game.player
	var d := target - p.camera.global_position
	p.rotation.y = atan2(-d.x, -d.z)
	p.camera.rotation = Vector3(atan2(d.y, Vector2(d.x, d.z).length()), 0, 0)

## Stand at `from` and look at `at`.
func stand_and_look(at: Vector3, from: Vector3) -> void:
	game.player.position = from
	await physics_frame
	look_at_point(at)
	for i in range(3): await physics_frame

func take_my_package() -> bool:
	var s: DeliverySession = game.session
	await frames(3)
	var mine: Node3D = null
	for pkg: Node3D in game.shelves.packages.get(s.restaurant_id(), []):
		if (pkg.get_meta("package", {}) as Dictionary).get("customer", "") == s.order.get("customer", "?"): mine = pkg
	if mine == null: return false
	await stand_and_look(mine.global_position + Vector3(0, 0.12, 0), mine.global_position + Vector3(0.0, -1.0, 1.25))
	game.interact()
	return s.holding_package()

func pack() -> void:
	game.show_menu("bag")
	await create_timer(0.7).timeout
	game.bag_click(OrderDetails.best_slot(str(game.session.order.kind)))
	await create_timer(0.5).timeout
	game.close_menu()

func run() -> void:
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	await frames(10)
	check(not game.tutorial.active(), "no training before New Game (old saves / tests stay untouched)")
	game.new_session()
	var s: DeliverySession = game.session
	var t: TutorialDirector = game.tutorial
	await frames(3)
	check(t.active() and t.step_id() == "look", "New Game starts training at 'Look around'")
	check(s.wallet == 10000 and not game.player.has_vehicle() and not game.player.bicycle.visible, "New Game: $100, on foot, no bike")
	check(game.player.toggle_bicycle().begins_with("You don't have a bicycle"), "no bike to ride")
	check(not s.has_phone() and not s.has_bag() and not s.online, "no phone, no bag, offline")
	game.show_menu("phone")
	check(game.mode == "", "no phone to open yet")
	s.next_offer = 0.0
	s.calendar_minutes = 720.0
	await frames(5)
	check(s.order.is_empty(), "no random offers while training")
	# 1 look, 2 walk
	for i in range(40):
		game.player.rotation.y += 0.08
		await process_frame
	check(await wait_step("walk"), "looking around completes 'look'")
	for i in range(70):
		game.player.position.x += 0.25
		await physics_frame
	check(await wait_step("store"), "walking completes 'walk'")
	check(CityNavigation.target.get("name", "") == "Trail & Tool", "minimap guides to Trail & Tool")
	# 3 store
	var shop: Vector3 = ShopCatalog.LOCATIONS["equipment"]
	game.player.position = shop + Vector3(4.0, 0.1, 2.6)
	check(await wait_step("order"), "reaching the store completes 'store'")
	# 4 order on the store computer (real ray on the kiosk)
	await stand_and_look(shop + Vector3(4.0, 1.4, 1.0), shop + Vector3(4.0, 0.1, 2.4))
	check(str(game.player.target().get("id", "")) == "kiosk_equipment", "the store computer is on the counter")
	game.interact()
	check(game.mode == "terminal" and game.terminal.visible, "E opens the store computer")
	var term: StoreTerminal = game.terminal
	term.add_to_cart("budget_phone", 1)
	term.add_to_cart("delivery_bag", 1)
	term.add_to_cart("water_bottle", 3)
	term.change("water_bottle", -1)
	check(int(term.cart.get("water_bottle", 0)) == 2 and term.total() == 2500 + 3500 + 300, "cart: phone + bag + 2 water ($63)")
	term.add_to_cart("budget_phone", 1)
	check(int(term.cart["budget_phone"]) == 1, "equipment can't be added twice")
	term.purchase()
	check(s.wallet == 10000 - 6300 and s.pickups.size() == 3, "purchase pays and puts 3 items on the pickup shelf")
	check(not s.has_phone() and s.bought("budget_phone"), "bought items wait on the shelf until collected")
	term.close()
	await frames(2)
	check(game.mode == "", "closing the computer returns to the game")
	check(await wait_step("collect"), "ordering completes 'order'")
	# 5 collect from the pickup shelf (real ray per item)
	await frames(2)
	for k in range(3):
		var items: Array[Node3D] = game.store_terminals.items
		if items.is_empty(): break
		var it: Node3D = items[0]
		await stand_and_look(it.global_position + Vector3(0, 0.15, 0), it.global_position + Vector3(0, -1.1, 1.3))
		game.interact()
		await frames(2)
	check(s.pickups.is_empty() and s.has_phone() and s.has_bag() and int(s.supplies.get("water_bottle", 0)) == 2, "E on each shelf item collects it")
	check(await wait_step("phone"), "collecting completes 'collect'")
	# 6 phone: raise it, tap CourierNow on the screen
	game.show_menu("phone")
	await create_timer(0.5).timeout
	var phone: PhoneDevice = game.phone
	check(game.mode == "phone" and phone.out, "Tab raises the phone")
	var cam: Camera3D = game.player.camera
	var centre: Vector3 = phone.screen.global_transform * phone.screen.get_aabb().get_center()
	var px := phone.screen_point(cam, cam.unproject_position(centre))
	check(px.distance_to(Vector2(PhoneOS.W, PhoneOS.H) * 0.5) < 12.0, "a click on the screen centre lands mid-screen (%s)" % px)
	phone.os.tap_app(PhoneOS.APPS[6])
	check(phone.os.page == "home" and phone.os.toast.visible, "locked apps say coming soon")
	phone.os.tap_app(PhoneOS.APPS[0])
	check(phone.os.page == "courier", "CourierNow opens")
	check(await wait_step("online"), "opening CourierNow completes 'phone'")
	# 7 online -> the training order arrives in the app
	game.on_phone_action("toggle_online", "")
	check(s.online, "Start shift puts you online")
	check(await wait_step("accept"), "going online completes 'online'")
	await frames(3)
	check(s.order.get("state") == "OFFERED" and s.order.get("method") == "door", "the first training order (leave at door) arrives")
	game.on_phone_action("reject", "")
	check(s.order.get("state") == "OFFERED", "training orders can't be declined")
	game.on_phone_action("toggle_online", "")
	check(s.online, "you can't go offline during training")
	game.on_phone_action("accept", "")
	game.close_menu()
	check(await wait_step("ride"), "accepting completes 'accept'")
	# 9 ride (walk) to the restaurant, 10 take, 11 drop, 12 pack
	var mine_ok: bool = await take_my_package()
	check(mine_ok, "E on your package on the shelf picks it up")
	check(await wait_step("drop"), "reaching the restaurant and taking the package advance training")
	game.bag_click("top")
	check(s.holding_package(), "packing is refused before practising put down / pick up")
	look_at_point(game.player.global_position + Vector3(0, 0, -1.0))
	await physics_frame
	game.drop_held()
	check(s.order.get("state") == "DROPPED" and game.dropped_package != null, "G puts the package down")
	await create_timer(0.6).timeout
	await stand_and_look(game.dropped_package.global_position + Vector3(0, 0.1, 0), game.player.position)
	game.interact()
	check(s.holding_package(), "E on it picks it up again")
	check(await wait_step("pack"), "'drop' completes")
	await pack()
	check(s.order.get("state") == "CARRYING", "packed in the backpack")
	check(await wait_step("leave"), "'pack' completes")
	# 13 leave at door: the marked area appears; E on it delivers with a proof photo
	await frames(3)
	var zone: DropZone = game.drop_zone
	check(zone != null and zone.method == "door", "the delivery area is marked at the door")
	var address := int(s.order.address)
	var facing: Vector3 = CityCatalog.address_facing(address)
	await stand_and_look(zone.global_position, zone.global_position + facing * 0.9 + Vector3(0, 0.1, 0))
	check(str(game.player.target().get("id", "")) == "dropzone", "the area can be targeted")
	game.interact()
	check(s.order.get("state") == "COMPLETED" and s.order.get("proof") == "photo", "leaving it in the area completes the delivery")
	game.close_menu()
	check(await wait_step("accept2"), "'leave' completes")
	# 14 second order: meet at door
	await frames(3)
	check(s.order.get("state") == "OFFERED" and s.order.get("method") == "meet", "the second training order is meet at door")
	game.show_menu("phone")
	await frames(2)
	game.on_phone_action("accept", "")
	game.close_menu()
	check(await wait_step("meet"), "accepting completes 'accept2'")
	mine_ok = await take_my_package()
	check(mine_ok, "second package taken")
	await pack()
	address = int(s.order.address)
	facing = CityCatalog.address_facing(address)
	game.player.position = game.world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
	game.player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	game.player.camera.rotation = Vector3(-0.2, 0, 0)
	for i in range(3): await physics_frame
	game.interact()
	await create_timer(1.5).timeout
	check(game.drop_zone != null and game.drop_zone.customer != null, "knocking brings the customer to the door")
	await stand_and_look(game.drop_zone.customer.global_position + Vector3(0, 1.1, 0), game.player.position)
	check(str(game.player.target().get("id", "")) == "customer", "the customer can be targeted")
	var before := s.wallet
	game.interact()
	check(s.order.get("state") == "COMPLETED" and s.wallet > before, "E hands the order to the customer")
	game.close_menu()
	for i in range(200):
		if not t.active(): break
		await process_frame
	check(not t.active() and s.tutorial.done, "training finishes")
	check(s.ledger.get("bonus_tutorial", 0) == DeliverySession.TUTORIAL_BONUS, "the training bonus is paid once")
	check(DeliverySession.validate(s.snapshot()), "the save validates")
	var copy := DeliverySession.new()
	check(copy.restore(s.snapshot()) and copy.economy == 2 and not copy.owns("bicycle") and copy.has_phone(), "career save restores (no bike, phone owned)")
	check(t.gate("dispatch") == "" and t.gate("reject") == "", "after training, dispatch and declining are back")
	await create_timer(0.2).timeout
	print("TUTORIAL PASS: %d checks, %d failures" % [checks, failures] if failures == 0 else "TUTORIAL FAIL: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
