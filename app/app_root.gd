class_name GameApp
extends Node3D
## The game's composition root (app_root.tscn): builds the city, the courier and the game systems,
## routes input, and runs the per-frame order of work. The work itself lives in focused modules:
##   GameHud          ui/hud/game_hud.gd       HUD, toasts, name tag, route marker
##   Interactions     app/interactions.gd      what E does and the prompt that says so
##   PackageFlow      app/package_flow.gd      the package from shelf to door, backpack, delivery
##   GameMenus        app/game_menus.gd        title/pause menu, phone, store computers, map, pages
##   GamePersistence  app/game_persistence.gd  new career, save / load
## The members and methods below that only forward to a module are the stable surface other
## systems (TutorialDirector, CourierSequence, PhoneDevice ...) and the tests use.

var session := DeliverySession.new()
var saves := DeliverySave.new()
var world: CedarNeighborhood
var player: CourierPlayer
## What has the street paused: "" (playing), "start", "pause", "phone", "map", "terminal", "bag",
## "shop", "food", "receipt".
var mode: String = ""
var save_enabled := true
var audio: CityAudio
var shelves: PickupShelves
var tutorial: TutorialDirector
var store_terminals: StoreTerminals
var bag_rig: BagRig
## One-button courier actions (pack at the shelf, leave at door, hand over): CourierSequence.
var sequence: CourierSequence
var hud: GameHud
var flow: PackageFlow
var menus: GameMenus
var interactions: Interactions
var persistence: GamePersistence
## Shown while the city builds: the Neighborhood child readies (~10-15 s) before this node's _ready.
var loading_screen: LoadingScreen

# Forwarded state (read-only).
var prompt_text: String:
	get: return hud.prompt_text
var notice: Label:
	get: return hud.notice
var navigation_label: Label:
	get: return hud.navigation_label
var minimap: Control:
	get: return hud.minimap
var hud_stack: VBoxContainer:
	get: return hud.hud_stack
var gameplay_ui: Control:
	get: return hud.gameplay_ui
var modal: PanelContainer:
	get: return hud.modal
var receipt_panel: PanelContainer:
	get: return hud.receipt_panel
var receipt_name: Label:
	get: return hud.receipt_name
var drop_zone: DropZone:
	get: return flow.drop_zone
var held_package: Node3D:
	get: return flow.held_package
var dropped_package: Node3D:
	get: return flow.dropped_package
var main_menu: MainMenu:
	get: return menus.main_menu
var phone: PhoneDevice:
	get: return menus.phone
var terminal: StoreTerminal:
	get: return menus.terminal
var city_map: Control:
	get: return menus.city_map
var current_shop: String:
	get: return menus.current_shop

func _enter_tree() -> void:
	if loading_screen != null: return
	loading_screen = LoadingScreen.new()
	loading_screen.name = "LoadingScreen"
	add_child(loading_screen)
	loading_screen.begin(self)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	GameSettings.load_settings()
	GameInput.bind_defaults()
	build_world()
	interactions = Interactions.new(self)
	persistence = GamePersistence.new(self)
	flow = PackageFlow.new()
	flow.name = "PackageFlow"
	add_child(flow)
	flow.setup(self)
	hud = GameHud.new()
	hud.name = "Hud"
	add_child(hud)
	hud.setup(self)
	menus = GameMenus.new()
	menus.name = "Menus"
	add_child(menus)
	menus.setup(self)
	GameSettings.apply(player)
	world.set_time(session.hour())
	session.changed.connect(update_hud)
	build_systems()
	menus.setup_devices()
	show_menu("start")
	update_hud()
	loading_screen.finish()
	if "--smoke-test" in OS.get_cmdline_user_args():
		call_deferred("smoke_test")

## The city (from the scene or built here), the courier and the city's sound.
func build_world() -> void:
	world = get_node_or_null("Neighborhood") as CedarNeighborhood
	if world == null:
		world = CedarNeighborhood.new()
		world.name = "Neighborhood"
		add_child(world)
	world.process_mode = Node.PROCESS_MODE_PAUSABLE
	player = get_node_or_null("CourierPlayer") as CourierPlayer
	if player == null:
		player = CourierPlayer.new()
		player.name = "CourierPlayer"
		add_child(player)
	player.session = session
	player.process_mode = Node.PROCESS_MODE_PAUSABLE
	player.position = GamePersistence.START
	player.setup_bicycle()
	audio = CityAudio.new()
	audio.name = "CityAudio"
	add_child(audio)
	audio.setup(self)
	audio.auto_order_cues = false     # the app plays the order cues itself (notify_order, delivery_success)

## Backpack, pickup shelves, courier actions, training, store computers.
func build_systems() -> void:
	bag_rig = BagRig.new()
	bag_rig.name = "BagRig"
	player.camera.add_child(bag_rig)
	shelves = PickupShelves.new()
	shelves.name = "PickupShelves"
	world.add_child(shelves)
	shelves.setup(world, session)
	sequence = CourierSequence.new()
	add_child(sequence)
	sequence.setup(self)
	tutorial = TutorialDirector.new()
	tutorial.name = "Tutorial"
	add_child(tutorial)
	tutorial.setup(self)
	store_terminals = StoreTerminals.new()
	store_terminals.name = "StoreTerminals"
	world.add_child(store_terminals)
	store_terminals.setup(session)

## A new session (new career): everything that reads it follows.
func use_session(next: DeliverySession) -> void:
	session = next
	player.session = session
	if store_terminals: store_terminals.session = session
	if shelves: shelves.session = session
	hud.use_session(session)
	session.changed.connect(update_hud)

# --- Input ------------------------------------------------------------------------------------

func binding(action: String) -> String:
	return GameInput.key_label(action)

## "Use" is E or a left mouse click.
func use_hint() -> String:
	return "%s / Click" % binding("interact")

## Mouse on the raised phone: taps and scrolling go to the phone screen.
func _input(event: InputEvent) -> void:
	if mode == "phone" and event is InputEventMouse and phone.forward(player.camera, event):
		get_viewport().set_input_as_handled()

func _unhandled_input(event: InputEvent) -> void:
	if handle_input(event): get_viewport().set_input_as_handled()

## Routes one input event; true when it was used.
func handle_input(event: InputEvent) -> bool:
	if mode == "terminal":
		if event.is_action_pressed("pause_game"):
			terminal.close()
			return true
		return false
	if mode == "" and (event.is_action_pressed("use_water") or event.is_action_pressed("use_snack")):
		use_supply("water_bottle" if event.is_action_pressed("use_water") else "energy_bar")
		return true
	if event.is_action_pressed("pause_game"):
		if mode in ["start", "pause"]:
			if not main_menu.back() and mode == "pause": close_menu()
		elif mode != "": close_menu()
		else: show_menu("pause")
		return true
	var use_click := GameInput.is_use_click(event)
	if mode == "" and sequence.running and (event.is_action_pressed("phone") or event.is_action_pressed("map") or event.is_action_pressed("bag") or event.is_action_pressed("drop") or event.is_action_pressed("interact") or use_click):
		# A courier action is playing (packing, leaving, handing over): it finishes by itself.
		return true
	if event.is_action_pressed("phone") or event.is_action_pressed("map"):
		if mode in ["start", "pause"]: return false
		if mode != "": close_menu()
		elif event.is_action_pressed("map") and player.mounted: notify("Stop and get off to open the city map (%s)." % binding("interact"))
		else: show_menu("map" if event.is_action_pressed("map") else "phone")
		return true
	if event.is_action_pressed("bag"):
		if mode == "bag": close_menu()
		elif mode == "": show_menu("bag")
		return true
	if mode == "bag" and event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Drag and drop: drop the held package into the compartment under the pointer, or click
		# a packed compartment to take the order back out.
		if flow.drag_slot != "": bag_click(flow.drag_slot)
		return true
	if mode == "" and event.is_action_pressed("drop"):
		flow.drop_held()
		return true
	if mode == "bag" and event.is_action_pressed("interact"):
		# E inside the bag: put the held package in the compartment it fits.
		if session.holding_package(): bag_click(OrderDetails.best_slot(str(session.order.get("kind", "bag"))))
		return true
	if mode == "" and (event.is_action_pressed("interact") or (use_click and not player.mounted)):
		interact()
		return true
	return false

## 1 / 2: drink water or eat an energy bar from your supplies (on foot with the gesture).
func use_supply(item: String) -> void:
	var had := int(session.supplies.get(item, 0))
	notify(session.use_supply(item))
	if int(session.supplies.get(item, 0)) < had and player.avatar != null: player.avatar.play_gesture("eat_drink", NAN, -1.0, item)

# --- Frame ------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	if mode == "bag": flow.update_bag_drag(delta)
	hud.frame_always()
	if get_tree().paused:
		return
	session.tick(delta)
	session.offer_position = player.position
	world.set_time(session.hour())
	flow.sync_dropped()
	if tutorial.gate("dispatch") == "" and session.has_phone() and session.has_bag() and session.dispatch(pickup_route_distance()):
		notify("CourierNow · New delivery request\nPress %s and open CourierNow" % binding("phone"))
		sound("notify_order")
		save_session()
	flow.sync_drop_zone()
	store_terminals.refresh()
	var target := player.target() if not sequence.running else {}
	# At the pickup shelf with an order to collect, the camera comes in so the tags read well.
	var pickup := session.pickup_position()
	player.view.browse = session.order.get("state") == "ACCEPTED" and not player.mounted and Vector2(player.position.x - pickup.x, player.position.z - pickup.z).length() < 4.2
	hud.prompt_text = interactions.prompt(target)
	hud.show_name_tag(target)
	flow.update_held_package()
	hud.frame(delta)

## Manhattan path to the kitchen via the open sidewalk and its frontage (dispatch distance).
func pickup_route_distance() -> float:
	return absf(player.position.z - 15.0) + absf(player.position.x + 14.0) + 3.0

# --- Forwarders (the stable surface) ----------------------------------------------------------

func interact() -> void: interactions.interact()
func show_menu(which: String) -> void: menus.show(which)
func close_menu() -> void: menus.close()
func notify(message: String) -> void: hud.notify(message)
func update_hud() -> void: hud.refresh()
func sound(name: String) -> void:
	if audio and CityAudio.has_sound(name): audio.play_ui(name, -6.0)
func save_session() -> bool: return persistence.save_session()
func load_session() -> void: persistence.load_session()
func new_session() -> void: persistence.new_session()
func on_main_menu(action: String) -> void: menus.on_main_menu(action)
func on_phone_action(name: String, arg: String) -> void: menus.on_phone_action(name, arg)
func equip_vehicle(id: String) -> void: menus.equip_vehicle(id)
func at_door() -> String: return flow.at_door()
func bag_click(slot: String) -> void: flow.bag_click(slot)
func sync_drop_zone() -> void: flow.sync_drop_zone()
func complete_left() -> void: flow.complete_left()
func drop_held() -> void: flow.drop_held()
func package_model() -> Node3D: return flow.package_model()

# --- Scene smoke test (--smoke-test) ----------------------------------------------------------

func smoke_test() -> void:
	# Scene integration test uses the same commands, world raycast and persistence path.
	close_menu()
	await get_tree().physics_frame
	session.offer()
	assert(session.accept())
	player.position = Vector3(-14, 0.08, 13.8)
	player.camera.rotation.x = -0.3
	await get_tree().physics_frame
	await get_tree().physics_frame
	var hit := player.target()
	assert(hit.get("id") in ["pickup", "package"], "Pickup counter must be physically interactable")
	# Find your named package among the others and take it with E (real ray).
	await get_tree().process_frame
	await get_tree().process_frame
	var mine := shelves.mine()
	assert(mine != null, "Your package waits on the pickup shelf")
	player.position = shelves.stand_point(mine)
	await get_tree().physics_frame
	var aim := shelves.look_point(mine) - player.eye_position()
	player.rotation.y = atan2(-aim.x, -aim.z)
	player.camera.rotation = Vector3(atan2(aim.y, Vector2(aim.x, aim.z).length()), 0, 0)
	await get_tree().physics_frame
	await get_tree().physics_frame
	assert(player.target().get("node") == mine, "Your package can be aimed at")
	interact()
	assert(session.order.state == "IN_HAND", "E takes it (no bag: carried by hand)")
	var address := int(session.order.address)
	var facing: Vector3 = CityCatalog.address_facing(address)
	player.position = world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
	player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
	player.camera.rotation = Vector3(-0.2, 0, 0)
	await get_tree().physics_frame
	await get_tree().physics_frame
	hit = player.target()
	assert(hit.get("id") == "door_%d" % address, "Correct door must be physically interactable")
	# Meet at door: knock, the customer comes out, hand the order over with E.
	session.order["method"] = "meet"
	sync_drop_zone()
	interact()
	await get_tree().create_timer(1.5).timeout
	assert(drop_zone != null and drop_zone.customer != null, "Knocking brings the customer to the door")
	var face := drop_zone.customer.global_position + Vector3(0, 1.1, 0) - player.eye_position()
	player.rotation.y = atan2(-face.x, -face.z)
	player.camera.rotation = Vector3(atan2(face.y, Vector2(face.x, face.z).length()), 0, 0)
	await get_tree().physics_frame
	await get_tree().physics_frame
	assert(player.target().get("id") == "customer", "The customer can be handed the order")
	interact()
	assert(sequence.running, "The handover plays")
	await get_tree().create_timer(3.0).timeout
	assert(session.order.state == "COMPLETED" and session.wallet > 0 and not sequence.running)
	close_menu()
	if not player.has_vehicle():
		session.active_vehicle = "bicycle"
		player.replace_vehicle(player.position + Vector3(3, 0, 0))
	player.position = player.bicycle.position + Vector3(1, 0.1, 0)
	assert(player.toggle_bicycle().begins_with("Mounted"))
	player.riding_speed = 3
	assert(player.toggle_bicycle().begins_with("Brake"))
	player.riding_speed = 0
	await get_tree().physics_frame
	assert(player.toggle_bicycle() == "Bicycle parked.")
	print("SCENE SMOKE PASS: real raycast pickup of the named package among decoys, knock + one-button customer handover, receipt; test does not write player save")
	get_tree().quit()
