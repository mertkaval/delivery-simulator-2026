extends Node3D
var session := DeliverySession.new()
var saves := DeliverySave.new()
var world: CedarNeighborhood
var street_label: Label
var player: CourierPlayer
var hud: CanvasLayer
var objective: Label
## The interaction prompt as "[E / Click]  Take ..."; drawn as key caps + text in prompt_bar.
var prompt_text := ""
var notice: Label
var modal: PanelContainer
var modal_body: VBoxContainer
var mode: String = ""
var notification_time: float = 0.0
var route_marker: Label3D
var navigation_label: Label
var minimap: Control
var shelves: PickupShelves
var receipt_panel: PanelContainer
var receipt_label: Label
var held_package: Node3D
var dropped_package: Node3D
var _pickup_from: Variant = null      ## Transform3D a freshly held package flies in from
var _drag_slot := ""                  ## bag compartment under the mouse while the backpack is open
var tutorial: TutorialDirector
var phone: PhoneDevice
var terminal: StoreTerminal
var store_terminals: StoreTerminals
var drop_zone: DropZone
var _zone_for := ""
var _flash: ColorRect
var bag_rig: BagRig
var bag_label: Label
var _held_for := ""
var city_map: Control
var city_map_layer: CanvasLayer
var _arrival_note := ""
var gameplay_ui: Control
var main_menu: MainMenu
var menu_shade: ColorRect
var menu_camera: Camera3D
var phone_width: float = 390.0
var calendar_label: Label
var current_shop := "equipment"
var save_enabled := true
var audio: CityAudio
var crosshair: Control
## One-button courier actions (pack at the shelf, leave at door, hand over): CourierSequence.
var sequence: CourierSequence
var order_plate: PanelContainer
var order_plate_name: Label
var order_plate_info: Label
var receipt_name: Label
var receipt_head: Label
## HUD layout (HudStyle): left column (objective, order chip, training card), right column
## (clock, wallet, needs; package name tag under it), bottom-left (backpack line, minimap, route
## distance), bottom centre (interaction prompt, controls), bottom right (riding speed).
var hud_stack: VBoxContainer
var status_panel: PanelContainer
var clock_label: Label
var weather_label: Label
var wallet_label: Label
var need_bars: Dictionary = {}
var supplies_row: HBoxContainer
var prompt_bar: PanelContainer
var prompt_row: HBoxContainer
var _prompt_shown := "~"
var controls_bar: PanelContainer
var controls_row: HBoxContainer
var _controls_shown := ""
var _controls_age := 0.0
var speed_panel: PanelContainer
var speed_label: Label
var bag_chip: PanelContainer
var bag_head: Label
var bag_keys: HBoxContainer
var _bag_key_shown := "~"
var nav_pill: PanelContainer
var _supplies_shown := "~"
## Shown while the city builds: the Neighborhood child readies (~10-15 s) before this node's _ready.
var loading_screen: LoadingScreen

func _enter_tree() -> void:
	if loading_screen != null: return
	loading_screen = LoadingScreen.new()
	loading_screen.name = "LoadingScreen"
	add_child(loading_screen)
	loading_screen.begin(self)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	GameSettings.load_settings()
	bind_inputs()
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
	player.position = Vector3(-8, 0.2, 23)
	player.setup_bicycle()
	audio = CityAudio.new()
	audio.name = "CityAudio"
	add_child(audio)
	audio.setup(self)
	audio.auto_order_cues = false     # app_root plays the order cues itself (notify_order, delivery_success)
	build_hud()
	var menu_layer := CanvasLayer.new()
	menu_layer.layer = 10
	add_child(menu_layer)
	main_menu = MainMenu.new()
	main_menu.name = "MainMenu"
	menu_layer.add_child(main_menu)
	main_menu.chosen.connect(on_main_menu)
	GameSettings.apply(player)
	menu_camera = Camera3D.new()
	add_child(menu_camera)
	menu_camera.position = Vector3(36, 16, 44)
	menu_camera.look_at(CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(0, 2, 0))
	world.set_time(session.hour())
	route_marker = Label3D.new()
	route_marker.font_size = 40
	route_marker.pixel_size = 0.012
	route_marker.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	route_marker.no_depth_test = true
	route_marker.modulate = Color("b6f3d1")
	route_marker.font = HudStyle.font(HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	route_marker.outline_size = 10
	add_child(route_marker)
	session.changed.connect(update_hud)
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
	var terminal_layer := CanvasLayer.new()
	terminal_layer.layer = 11
	add_child(terminal_layer)
	terminal = StoreTerminal.new()
	terminal.name = "StoreTerminal"
	terminal_layer.add_child(terminal)
	terminal.closed.connect(func() -> void: if mode == "terminal": close_menu())
	terminal.purchased.connect(on_store_purchase)
	terminal.equip.connect(equip_vehicle)
	phone = PhoneDevice.new()
	phone.name = "Phone"
	player.camera.add_child(phone)
	phone.setup(self)
	phone.os.action.connect(on_phone_action)
	_flash = ColorRect.new()
	_flash.color = Color(1, 1, 1, 0)
	_flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(_flash)
	show_menu("start")
	update_hud()
	loading_screen.finish()
	if "--smoke-test" in OS.get_cmdline_user_args():
		call_deferred("smoke_test")

func bind_inputs() -> void:
	if not InputMap.has_action("bicycle"):
		InputMap.add_action("bicycle")
		var bike_key := InputEventKey.new()
		bike_key.physical_keycode = KEY_B
		InputMap.action_add_event("bicycle", bike_key)
	var actions := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D, "sprint": KEY_SHIFT, "jump": KEY_SPACE, "interact": KEY_E, "phone": KEY_TAB, "map": KEY_M, "pause_game": KEY_ESCAPE, "bell": KEY_Q, "bag": KEY_F, "drop": KEY_G, "use_water": KEY_1, "use_snack": KEY_2, "camera_view": KEY_V, "walk": KEY_CTRL}
	for action in actions:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = actions[action]
			InputMap.action_add_event(action, key)

func binding(action: String) -> String:
	var event := InputMap.action_get_events(action)[0] as InputEventKey
	return OS.get_keycode_string(event.physical_keycode if event.physical_keycode != 0 else event.keycode)

## "Use" is E or a left mouse click.
func use_hint() -> String:
	return "%s / Click" % binding("interact")

## Left click on foot (mouse captured, nothing open) works like E.
static func is_use_click(event: InputEvent) -> bool:
	return event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED

## Mouse on the raised phone: taps and scrolling go to the phone screen.
func _input(event: InputEvent) -> void:
	if mode == "phone" and event is InputEventMouse and phone.forward(player.camera, event):
		get_viewport().set_input_as_handled()

func _unhandled_input(event: InputEvent) -> void:
	if mode == "terminal":
		if event.is_action_pressed("pause_game"):
			terminal.close()
			get_viewport().set_input_as_handled()
		return
	if mode == "" and (event.is_action_pressed("use_water") or event.is_action_pressed("use_snack")):
		var item := "water_bottle" if event.is_action_pressed("use_water") else "energy_bar"
		var had := int(session.supplies.get(item, 0))
		notify(session.use_supply(item))
		# On foot the courier drinks / takes a bite (Eat_Drink).
		if int(session.supplies.get(item, 0)) < had and player.avatar != null: player.avatar.play_gesture("eat_drink", NAN, -1.0, item)
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("pause_game"):
		if mode in ["start", "pause"]:
			if not main_menu.back() and mode == "pause": close_menu()
			get_viewport().set_input_as_handled()
			return
		if mode != "":
			close_menu()
		else:
			show_menu("pause")
		get_viewport().set_input_as_handled()
	elif mode == "" and sequence.running and (event.is_action_pressed("phone") or event.is_action_pressed("map") or event.is_action_pressed("bag") or event.is_action_pressed("drop") or event.is_action_pressed("interact") or is_use_click(event)):
		# A courier action is playing (packing, leaving, handing over): it finishes by itself.
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("phone") or event.is_action_pressed("map"):
		if mode in ["start", "pause"]:
			return
		if mode != "":
			close_menu()
		elif event.is_action_pressed("map") and player.mounted:
			notify("Stop and get off to open the city map (%s)." % binding("interact"))
		else:
			show_menu("map" if event.is_action_pressed("map") else "phone")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("bag"):
		if mode == "bag":
			close_menu()
		elif mode == "":
			show_menu("bag")
		get_viewport().set_input_as_handled()
	elif mode == "bag" and event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Drag and drop: drop the held package into the compartment under the pointer, or click
		# a packed compartment to take the order back out.
		if _drag_slot != "": bag_click(_drag_slot)
		get_viewport().set_input_as_handled()
	elif mode == "" and event.is_action_pressed("drop"):
		drop_held()
		get_viewport().set_input_as_handled()
	elif mode == "bag" and event.is_action_pressed("interact"):
		# E inside the bag: put the held package in the compartment it fits.
		if session.holding_package():
			bag_click(OrderDetails.best_slot(str(session.order.get("kind", "bag"))))
		get_viewport().set_input_as_handled()
	elif mode == "" and (event.is_action_pressed("interact") or (is_use_click(event) and not player.mounted)):
		interact()
		get_viewport().set_input_as_handled()

func _process(delta: float) -> void:
	if mode == "bag": update_bag_drag(delta)
	# Third person: the crosshair marks where the interaction ray from the head points.
	if crosshair and player.view:
		crosshair.position = player.view.reticle - crosshair.size * 0.5
		crosshair.visible = not sequence.running and mode == ""
	# Phone, bag, menus: their own instructions replace the prompt and the controls bar.
	if mode != "" and controls_bar:
		controls_bar.visible = false
		prompt_bar.visible = false
	if get_tree().paused:
		return
	session.tick(delta)
	session.offer_position = player.position
	world.set_time(session.hour())
	sync_dropped()
	if tutorial.gate("dispatch") == "" and session.has_phone() and session.has_bag() and session.dispatch(pickup_route_distance()):
		notify("CourierNow · New delivery request\nPress %s and open CourierNow" % binding("phone"))
		sound("notify_order")
		save_session()
	sync_drop_zone()
	store_terminals.refresh()
	notification_time -= delta
	notice.visible = notification_time > 0
	var target := player.target() if not sequence.running else {}
	prompt_text = ""
	# At the pickup shelf with an order to collect, the camera comes in so the tags read well.
	player.view.browse = session.order.get("state") == "ACCEPTED" and not player.mounted and Vector2(player.position.x - session.pickup_position().x, player.position.z - session.pickup_position().z).length() < 4.2
	if not target.is_empty():
		var title: String = target.id
		if title == "package":
			var info: Dictionary = target.node.get_meta("package")
			title = "Take  %s  ·  %s" % [str(info.customer).to_upper(), info.ticket]
		elif title == "pickup" or title.begins_with("pickup_"):
			title = "Courier pickup shelf"
		elif title.begins_with("cedar_door_"):
			title = "Open / close house door"
		elif title.begins_with("door_"):
			var mine: bool = session.order.get("state") in DeliverySession.ACTIVE and int(title.trim_prefix("door_")) == int(session.order.get("address", -1))
			title = (("Knock  ·  " if session.order.get("method", "meet") == "meet" else "Leave it at the door  ·  ") if mine else "") + DeliverySession.ADDRESSES[int(title.trim_prefix("door_"))]
		elif title.begins_with("kiosk_") or title.begins_with("store_") and title != "store_pickup":
			title = "Use the store computer"
		elif title == "store_pickup":
			var idx := int(target.node.get_meta("pickup_index", -1))
			title = "Collect  " + (str(ShopCatalog.ITEMS[session.pickups[idx].id].name) if idx >= 0 and idx < session.pickups.size() else "item")
		elif title == "dropzone":
			title = "Leave %s's order here" % session.order.get("customer", "the")
		elif title == "customer":
			title = "Hand the order to %s" % session.order.get("customer", "the customer")
		elif title == "shop":
			title = "Browse delivery equipment"
		elif title == "home":
			title = "Rest and save"
		prompt_text = "[%s]  %s" % [use_hint(), title]
	# At the door, E works by proximity (see interact): say so whatever the crosshair is on.
	if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"] and not sequence.running and (target.is_empty() or str(target.id).begins_with("door_") or target.id == "dropzone"):
		if drop_zone.method == "door" and near_zone(3.0):
			prompt_text = "[%s]  Leave %s's order in the marked area" % [use_hint(), session.order.get("customer", "the customer")]
		elif drop_zone.customer != null and player.position.distance_to(drop_zone.customer.global_position) < 2.6:
			prompt_text = "[%s]  Hand the order to %s" % [use_hint(), session.order.get("customer", "the customer")]
	elif session.holding_package() and session.has_bag() and target.is_empty() and not sequence.running:
		prompt_text = "[%s]  Pack it in your backpack" % use_hint()
	show_receipt(target)
	update_held_package()
	update_hud()
	layout_hud(delta)

func interact() -> void:
	if sequence.running: return
	if player.mounted:
		notify(player.toggle_bicycle())
		save_session()
		return
	var target := player.target()
	# At the customer's door, E works without aiming exactly: standing at the marked area
	# (leave at door) or next to the waiting customer (meet at door).
	if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"] and (target.is_empty() or str(target.id).begins_with("door_") or target.id == "dropzone"):
		if drop_zone.method == "door" and near_zone(3.0):
			deliver_here({"id": "dropzone"})
			return
		if drop_zone.customer != null and player.position.distance_to(drop_zone.customer.global_position) < 2.6:
			deliver_here({"id": "customer"})
			return
	# Holding an order out of the bag (after F's take-out, or picked up off the ground): one
	# press packs it.
	if session.holding_package() and session.has_bag() and (target.is_empty() or not str(target.id) in ["package", "store_pickup"] and not str(target.id).begins_with("door_") and not str(target.id).begins_with("kiosk_")):
		start_pack(null)
		return
	if session.holding_package() and not session.has_bag() and player.position.distance_to(player.bicycle.position) < 2.5 and player.has_vehicle() and (target.is_empty() or not str(target.id).begins_with("door_")):
		notify("Loose food can't ride along: you need a delivery bag (Trail & Tool, $35). Walk it over by hand.")
		return
	if target.is_empty():
		if player.has_vehicle() and player.position.distance_to(player.bicycle.position) < 2.5:
			notify(player.toggle_bicycle())
			save_session()
		return
	if str(target.id).begins_with("kiosk_") or (str(target.id).begins_with("store_") and target.id != "store_pickup"):
		open_terminal(str(target.id).trim_prefix("kiosk_").trim_prefix("store_"))
		return
	if target.id == "store_pickup":
		notify(session.collect(int(target.node.get_meta("pickup_index", -1))))
		store_terminals.refresh()
		player.refresh_equipment()
		sound("item_pickup")
		save_session()
		return
	if target.id == "dropzone" or target.id == "customer":
		deliver_here(target)
		return
	var result := ""
	if target.id == "package":
		take_package_node(target.node, float(target.distance))
		return
	if str(target.id).begins_with("cedar_door_"):
		world.cedar_house.toggle_door(int(str(target.id).trim_prefix("cedar_door_")))
		return
	if target.id == "wc":
		result = session.consume("wc")
	elif target.id == "water":
		session.hydration = 100
		session.bladder = minf(100, session.bladder + 8)
		result = "Drinking water replenished."
	elif (target.id == "pickup" or str(target.id).begins_with("pickup_")) and session.order.get("state") not in DeliverySession.ACTIVE:
		show_menu("food")
		return
	elif target.id == "pickup" or str(target.id).begins_with("pickup_"):
		var rid := "cedar_kitchen" if target.id == "pickup" else str(target.id).trim_prefix("pickup_")
		if session.order.get("state") == "ACCEPTED" and rid == session.restaurant_id():
			result = "Find the package tagged %s · %s (%s) and take it (%s)." % [str(session.order.get("customer", "?")).to_upper(), session.order.get("ticket", "?"), OrderDetails.package_label(str(session.order.get("kind", "bag")), session.order.get("items", [])).to_lower(), use_hint()]
		elif session.order.get("state") == "ACCEPTED":
			result = "This is not your pickup restaurant. Collect at " + session.restaurant_name() + "."
		else:
			result = "Your order is already with you. Deliver it to " + str(session.order.get("customer", "the customer")) + "."
	elif str(target.id).begins_with("door_") and tutorial.gate("deliver") != "" and session.order.get("state") in DeliverySession.ACTIVE:
		result = tutorial.gate("deliver")
	elif str(target.id).begins_with("door_") and session.order.get("state") in ["IN_HAND", "CARRYING", "DROPPED"] and int(str(target.id).trim_prefix("door_")) == int(session.order.address):
		result = at_door()
	elif str(target.id).begins_with("door_"):
		var was_packed: bool = session.order.get("state") == "CARRYING"
		result = session.deliver(int(str(target.id).trim_prefix("door_")), target.distance)
		if session.order.get("state") == "COMPLETED":
			if was_packed:
				if not is_instance_valid(bag_rig.contents): bag_rig.show_contents(package_model(), "top")
				bag_rig.handover()
			show_menu("receipt")
	elif target.id == "shop":
		current_shop = "equipment"
		show_menu("shop")
		return
	elif target.id == "home":
		if session.order.get("state") in DeliverySession.ACTIVE:
			result = "Finish your active delivery before resting."
		else:
			session.energy = 100.0
			session.bladder = 0
			session.calendar_minutes = (floor(session.calendar_minutes / 1440.0) + 1.0) * 1440.0 + 480.0
			session.schedule_offer()
			result = "Good morning. Rested until 08:00. Energy restored."
	if result != "":
		notify(result)
		save_session()

func style_panel(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.corner_radius_top_left = 14
	style.corner_radius_top_right = 14
	style.corner_radius_bottom_left = 14
	style.corner_radius_bottom_right = 14
	style.content_margin_left = 24
	style.content_margin_right = 24
	style.content_margin_top = 18
	style.content_margin_bottom = 18
	return style

func make_label(text: String, size: int = 20, color: Color = Color("e6efeb")) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.5))
	label.add_theme_constant_override("shadow_offset_x", 0)
	label.add_theme_constant_override("shadow_offset_y", 1)
	return label

func build_hud() -> void:
	hud = CanvasLayer.new()
	add_child(hud)
	gameplay_ui = Control.new()
	gameplay_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	gameplay_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gameplay_ui.theme = HudStyle.theme()
	hud.add_child(gameplay_ui)
	var m := HudStyle.MARGIN
	# Left column: objective, order chip, training card (TutorialDirector adds it). A VBox, so the
	# blocks stack whatever their text and never overlap.
	hud_stack = VBoxContainer.new()
	hud_stack.name = "HudStack"
	hud_stack.position = Vector2(m, m)
	hud_stack.custom_minimum_size.x = HudStyle.COLUMN
	hud_stack.add_theme_constant_override("separation", HudStyle.GAP)
	hud_stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gameplay_ui.add_child(hud_stack)
	var top := PanelContainer.new()
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_theme_stylebox_override("panel", HudStyle.panel())
	hud_stack.add_child(top)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 1)
	top.add_child(column)
	street_label = HudStyle.eyebrow("", HudStyle.ACCENT)
	street_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	column.add_child(street_label)
	objective = HudStyle.label("", HudStyle.TITLE, HudStyle.INK, HudStyle.Face.TEXT, HudStyle.SEMIBOLD)
	objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	objective.custom_minimum_size.x = HudStyle.COLUMN - 24
	objective.max_lines_visible = 2
	column.add_child(objective)
	order_plate = HudStyle.order_chip()
	order_plate.name = "OrderChip"
	order_plate_name = order_plate.get_node("Col/Name") as Label
	order_plate_info = order_plate.get_node("Col/Info") as Label
	order_plate.visible = false
	hud_stack.add_child(order_plate)
	# Right column: clock, date and weather, wallet; energy / food / water / WC meters.
	status_panel = PanelContainer.new()
	status_panel.name = "StatusPanel"
	status_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	status_panel.add_theme_stylebox_override("panel", HudStyle.panel(Color(0, 0, 0, 0), HudStyle.PANEL, 12, 8))
	status_panel.custom_minimum_size.x = STATUS_WIDTH
	status_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	status_panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	status_panel.offset_right = -m
	status_panel.offset_left = -m - STATUS_WIDTH
	status_panel.offset_top = m
	gameplay_ui.add_child(status_panel)
	var status_col := VBoxContainer.new()
	status_col.add_theme_constant_override("separation", 6)
	status_panel.add_child(status_col)
	var clock_row := HBoxContainer.new()
	clock_row.add_theme_constant_override("separation", 8)
	status_col.add_child(clock_row)
	clock_label = HudStyle.label("12:00", HudStyle.CLOCK, HudStyle.INK, HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	clock_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	clock_row.add_child(clock_label)
	var date_col := VBoxContainer.new()
	date_col.add_theme_constant_override("separation", 1)
	date_col.alignment = BoxContainer.ALIGNMENT_CENTER
	date_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	clock_row.add_child(date_col)
	calendar_label = HudStyle.eyebrow("", HudStyle.INK_SOFT)
	date_col.add_child(calendar_label)
	weather_label = HudStyle.eyebrow("", HudStyle.MUTED)
	date_col.add_child(weather_label)
	wallet_label = HudStyle.label("", 15, HudStyle.ACCENT, HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	wallet_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	wallet_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	clock_row.add_child(wallet_label)
	var needs_row := HBoxContainer.new()
	needs_row.add_theme_constant_override("separation", 8)
	status_col.add_child(needs_row)
	for need in ["ENERGY", "FOOD", "WATER", "WC"]:
		var cell := VBoxContainer.new()
		cell.add_theme_constant_override("separation", 2)
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		needs_row.add_child(cell)
		cell.add_child(HudStyle.eyebrow(need, HudStyle.MUTED, HudStyle.MICRO))
		var bar := HudStyle.meter(0.0, 3.0)
		bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		cell.add_child(bar)
		need_bars[need] = bar
	supplies_row = HBoxContainer.new()
	supplies_row.add_theme_constant_override("separation", 4)
	supplies_row.visible = false
	status_col.add_child(supplies_row)
	# Bottom left: backpack line, minimap, route distance.
	minimap = preload("res://ui/minimap.gd").new()
	minimap.player = player
	minimap.session = session
	minimap.world = world
	minimap.size = Vector2(MINIMAP_SIZE, MINIMAP_SIZE)
	gameplay_ui.add_child(minimap)
	nav_pill = PanelContainer.new()
	nav_pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	nav_pill.add_theme_stylebox_override("panel", HudStyle.pill(HudStyle.PANEL_STRONG, 9, 2))
	gameplay_ui.add_child(nav_pill)
	navigation_label = HudStyle.label("", HudStyle.SMALL, HudStyle.ACCENT, HudStyle.Face.TEXT, HudStyle.SEMIBOLD)
	nav_pill.add_child(navigation_label)
	bag_chip = PanelContainer.new()
	bag_chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bag_chip.add_theme_stylebox_override("panel", HudStyle.panel(Color(0, 0, 0, 0), HudStyle.PANEL, 8, 4))
	gameplay_ui.add_child(bag_chip)
	var bag_row := HBoxContainer.new()
	bag_row.add_theme_constant_override("separation", 6)
	bag_chip.add_child(bag_row)
	bag_keys = HBoxContainer.new()
	bag_keys.add_theme_constant_override("separation", 3)
	bag_row.add_child(bag_keys)
	bag_head = HudStyle.eyebrow("BACKPACK", HudStyle.WARM)
	bag_head.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bag_row.add_child(bag_head)
	bag_label = HudStyle.label("", HudStyle.SMALL, HudStyle.INK_SOFT)
	bag_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bag_row.add_child(bag_label)
	# Bottom centre: the interaction prompt over a quiet, context-aware controls bar.
	prompt_bar = PanelContainer.new()
	prompt_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	prompt_bar.add_theme_stylebox_override("panel", HudStyle.pill(HudStyle.PANEL_STRONG, 12, 5))
	gameplay_ui.add_child(prompt_bar)
	prompt_row = HBoxContainer.new()
	prompt_row.add_theme_constant_override("separation", 5)
	prompt_bar.add_child(prompt_row)
	controls_bar = PanelContainer.new()
	controls_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	controls_bar.add_theme_stylebox_override("panel", HudStyle.pill(Color(0.03, 0.05, 0.06, 0.5), 10, 3))
	gameplay_ui.add_child(controls_bar)
	controls_row = HBoxContainer.new()
	controls_row.add_theme_constant_override("separation", 3)
	controls_bar.add_child(controls_row)
	# Bottom right: riding speed.
	speed_panel = PanelContainer.new()
	speed_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	speed_panel.add_theme_stylebox_override("panel", HudStyle.panel(Color(0, 0, 0, 0), HudStyle.PANEL, 12, 4))
	speed_panel.visible = false
	gameplay_ui.add_child(speed_panel)
	var speed_row := HBoxContainer.new()
	speed_row.add_theme_constant_override("separation", 4)
	speed_panel.add_child(speed_row)
	speed_label = HudStyle.label("0", HudStyle.SPEED, HudStyle.INK, HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	speed_row.add_child(speed_label)
	var unit := HudStyle.eyebrow("KM/H", HudStyle.MUTED)
	unit.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	unit.size_flags_vertical = Control.SIZE_SHRINK_END
	speed_row.add_child(unit)
	# Third person: a small dot where the interaction ray points.
	crosshair = Reticle.new()
	crosshair.size = Vector2(12, 12)
	crosshair.position = Vector2(634, 354)
	gameplay_ui.add_child(crosshair)
	# Toasts: a compact pill at the top centre, between the two columns.
	notice = HudStyle.label("", HudStyle.BODY, HudStyle.INK, HudStyle.Face.TEXT, HudStyle.MEDIUM)
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	notice.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	notice.add_theme_constant_override("line_spacing", -1)
	var notice_bg := HudStyle.panel(Color(0, 0, 0, 0), HudStyle.PANEL_STRONG, 14, 6)
	notice_bg.border_width_bottom = 2
	notice_bg.border_color = HudStyle.ACCENT
	notice_bg.border_width_left = 0
	notice_bg.border_width_right = 0
	notice_bg.border_width_top = 0
	notice.add_theme_stylebox_override("normal", notice_bg)
	gameplay_ui.add_child(notice)
	# Keep gameplay chrome out of the title menu.
	for child in hud.get_children():
		if child != gameplay_ui:
			child.reparent(gameplay_ui)
	menu_shade = ColorRect.new()
	menu_shade.color = Color(0.015, 0.025, 0.035, 0.66)
	menu_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.add_child(menu_shade)
	modal = preload("res://ui/phone_shell.gd").new()
	modal.set("session", session)
	modal.position = Vector2(720, 28)
	modal.custom_minimum_size = Vector2(525, 620)
	modal.add_theme_stylebox_override("panel", style_panel(Color("10252b")))
	modal.theme = HudStyle.theme()
	hud.add_child(modal)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	modal.add_child(scroll)
	modal_body = VBoxContainer.new()
	modal_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_body.add_theme_constant_override("separation", 12)
	scroll.add_child(modal_body)

const STATUS_WIDTH := 248.0
const MINIMAP_SIZE := 148.0
const NOTICE_MAX := 460.0

## The crosshair: a dot with a dark ring, readable on any background.
class Reticle extends Control:
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
	func _draw() -> void:
		var c := size * 0.5
		draw_circle(c, 3.2, Color(0, 0, 0, 0.45))
		draw_circle(c, 2.0, Color(1, 1, 1, 0.92))

## Display name for a key ("Escape" -> "Esc").
func key_name(action: String) -> String:
	var k := binding(action)
	return {"Escape": "Esc", "Ctrl": "Ctrl", "Shift": "Shift"}.get(k, k)

## Positions of the anchored HUD blocks for the current canvas size, the prompt / controls
## rendering and the controls bar fade. Called every frame (cheap: only moves controls).
func layout_hud(delta: float) -> void:
	var view := gameplay_ui.size
	var m := HudStyle.MARGIN
	# Bottom left: minimap with the distance pill hanging off its lower edge, backpack line above.
	minimap.size = Vector2(MINIMAP_SIZE, MINIMAP_SIZE)
	minimap.position = Vector2(m, view.y - m - 10 - MINIMAP_SIZE)
	nav_pill.reset_size()
	nav_pill.position = Vector2(maxf(m * 0.5, m + MINIMAP_SIZE * 0.5 - nav_pill.size.x * 0.5), minimap.position.y + MINIMAP_SIZE - 6)
	bag_chip.reset_size()
	bag_chip.position = Vector2(m, minimap.position.y - HudStyle.GAP - bag_chip.size.y)
	# The left column must end above the backpack line: drop the training instruction to fewer
	# lines on short canvases (never happens at 16:9, kept as a guard).
	var floor_y := (bag_chip.position.y if bag_chip.visible else minimap.position.y) - HudStyle.GAP
	if tutorial and tutorial.card and tutorial.card.visible:
		var hint: Label = tutorial.card.hint
		if hud_stack.position.y + hud_stack.size.y > floor_y and hint.max_lines_visible > 1: hint.max_lines_visible -= 1
		elif hud_stack.position.y + hud_stack.size.y + 16 < floor_y and hint.max_lines_visible < 4: hint.max_lines_visible += 1
	hud_stack.reset_size()
	# Interaction prompt.
	if prompt_text != _prompt_shown:
		_prompt_shown = prompt_text
		HudStyle.fill_keys(prompt_row, HudStyle.parse_keys(prompt_text), HudStyle.PROMPT, HudStyle.INK, HudStyle.CAPTION, HudStyle.SEMIBOLD)
		prompt_bar.reset_size()
	prompt_bar.visible = prompt_text != "" and mode == ""
	controls_bar.visible = mode == ""
	# Controls bar: what the keys do right now; quiet, and fades further once you're moving.
	var mounted := player.mounted
	var car := mounted and ShopCatalog.is_car(session.active_vehicle)
	var controls := ""
	if mounted:
		controls = "[W / S] %s  [A / D] Steer  [Space] Brake  [%s] %s  [%s] Phone  [%s] View  [%s] Pause" % ["Drive" if car else "Pedal", key_name("interact"), "Exit" if car else "Dismount", key_name("phone"), key_name("camera_view"), key_name("pause_game")]
	else:
		controls = "[WASD] Move  [%s] Sprint  [%s] Walk  [Space] Jump  [%s / Click] Use  [%s] Bag  [%s] Phone  [%s] Map  [%s] View  [Wheel] Zoom  [%s] Pause" % [key_name("sprint"), key_name("walk"), key_name("interact"), key_name("bag"), key_name("phone"), key_name("map"), key_name("camera_view"), key_name("pause_game")]
	if controls != _controls_shown:
		_controls_shown = controls
		_controls_age = 0.0
		HudStyle.fill_keys(controls_row, HudStyle.parse_keys(controls), HudStyle.CAPTION, HudStyle.INK_SOFT, HudStyle.MICRO, HudStyle.REGULAR)
		controls_bar.reset_size()
	_controls_age += delta
	controls_bar.modulate.a = lerpf(controls_bar.modulate.a, 0.95 if _controls_age < 12.0 else 0.5, minf(1.0, delta * 2.0))
	controls_bar.position = Vector2(round((view.x - controls_bar.size.x) * 0.5), view.y - 8 - controls_bar.size.y)
	prompt_bar.position = Vector2(round((view.x - prompt_bar.size.x) * 0.5), controls_bar.position.y - 10 - prompt_bar.size.y)
	# Riding speed, bottom right.
	speed_panel.visible = mounted
	if mounted:
		speed_label.text = "%d" % int(absf(player.riding_speed) * 3.6)
		speed_panel.reset_size()
		speed_panel.position = Vector2(view.x - m - speed_panel.size.x, view.y - m - speed_panel.size.y)
	# Toast: as wide as its text, up to NOTICE_MAX, wrapping beyond.
	if notice.visible:
		var f := notice.get_theme_font("font")
		var natural := f.get_multiline_string_size(notice.text, HORIZONTAL_ALIGNMENT_LEFT, -1, HudStyle.BODY).x
		var w := clampf(natural + 30.0, 140.0, NOTICE_MAX)
		notice.custom_minimum_size.x = w
		notice.size = Vector2(w, 0)     # shrinks to the wrapped text's height
		notice.position = Vector2(round((view.x - notice.size.x) * 0.5), m)


func add_text(text: String, size: int = 20, color: Color = Color("e6efeb")) -> void:
	size = roundi(size * (0.7 if mode in ["phone", "map"] else 0.8))     # HudStyle type scale
	var label := make_label(text, size, color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = 0
	modal_body.add_child(label)

func button(text: String, callback: Callable) -> void:
	var control := Button.new()
	control.text = text
	control.custom_minimum_size.y = 36
	control.add_theme_font_size_override("font_size", 13 if mode in ["phone", "map"] else 15)
	control.add_theme_font_override("font", HudStyle.font(HudStyle.Face.TEXT, HudStyle.SEMIBOLD))
	control.add_theme_stylebox_override("normal", style_panel(Color("23424a")))
	control.add_theme_stylebox_override("hover", style_panel(Color("376357")))
	control.add_theme_stylebox_override("focus", style_panel(Color("376357")))
	for state_name in ["normal", "hover", "focus"]:
		var button_style: StyleBoxFlat = control.get_theme_stylebox(state_name).duplicate()
		button_style.content_margin_top = 8
		button_style.content_margin_bottom = 8
		control.add_theme_stylebox_override(state_name, button_style)
	control.pressed.connect(callback)
	modal_body.add_child(control)

func show_menu(which: String) -> void:
	if which in ["start", "pause", "confirm_new"]:
		open_main_menu(which != "pause")
		return
	if which == "phone":
		open_phone()
		return
	if which == "map":
		open_city_map()
		return
	if city_map != null: city_map.hide()
	mode = which
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.show()
	gameplay_ui.visible = true
	menu_shade.visible = true
	var is_phone := which in ["phone", "map"]
	modal.set("phone_mode", is_phone)
	modal.set("session", session)
	if is_phone or which == "bag": menu_shade.visible = false
	modal_body.add_theme_constant_override("separation",8 if is_phone else 12)
	player.camera.make_current()
	modal.custom_minimum_size = Vector2.ZERO
	# Right column, under the status panel (HudStyle).
	var top_y := status_panel.position.y + status_panel.size.y + HudStyle.GAP
	modal.size = Vector2(420, gameplay_ui.size.y - HudStyle.MARGIN - top_y)
	modal.position = Vector2(gameplay_ui.size.x - HudStyle.MARGIN - 420, top_y)
	var style := HudStyle.panel(Color(0, 0, 0, 0), Color(0.03, 0.05, 0.06, 0.93), 20, 16)
	if is_phone:
		modal.position = Vector2(924, 132)
		modal.size = Vector2(328, 566)
		style.bg_color = Color("101c25")
		style.set_corner_radius_all(37)
		style.set_border_width_all(7)
		style.border_color = Color("46545e")
		style.content_margin_left = 21
		style.content_margin_right = 21
		style.content_margin_top = 50
		style.content_margin_bottom = 30
	modal.add_theme_stylebox_override("panel", style)
	for child in modal_body.get_children():
		modal_body.remove_child(child)
		child.queue_free()
	add_text("%02d:%02d       ●       COURIERNOW" % [int(session.hour()), int(session.calendar_minutes) % 60], 14, Color("9bceb7"))
	match which:
		"map":
			add_text("COURIERNOW  /  NAVIGATION", 15, Color("9bceb7"))
			add_text("Atatürk Avenue", 32)
			var large_map: Control = preload("res://ui/minimap.gd").new()
			large_map.player = player
			large_map.session = session
			large_map.world = world
			large_map.custom_minimum_size = Vector2(272, 272)
			large_map.set("range_metres", 120.0)
			modal_body.add_child(large_map)
			add_text("White arrow: you   ·   Mint: route\nGold: pickup   ·   North stays up", 16)
			button("Back to street", close_menu)
		"bag":
			build_bag_menu()
			if session.has_bag():
				bag_rig.take_off()
				sound("bag_zip")
				if session.order.get("state") == "CARRYING" and not is_instance_valid(bag_rig.contents):
					bag_rig.show_contents(package_model(), str(session.order.get("slot", "top")))
		"shop":
			add_text(ShopCatalog.TITLES.get(current_shop, "TRAIL & TOOL"), 29)
			add_text("Wallet  " + DeliverySession.money(session.wallet), 20, Color("9bceb7"))
			for id in ShopCatalog.ITEMS:
				var item: Dictionary = ShopCatalog.ITEMS[id]
				if item.shop != current_shop: continue
				add_text(item.name + "  ·  " + DeliverySession.money(item.price), 22)
				add_text(item.description, 16, Color("b8cac3"))
				if session.owns(id):
					if ShopCatalog.is_vehicle(id): button("Use this vehicle", equip_vehicle.bind(id))
					else: add_text("OWNED / EQUIPPED", 14, Color("9bceb7"))
				else: button("Buy " + item.name, buy_item.bind(id))
			button("Back to street", close_menu)
		"food":
			add_text("Take care of yourself", 29)
			add_text("Food %d%%   Water %d%%\nWallet %s" % [int(session.hunger), int(session.hydration), DeliverySession.money(session.wallet)], 19)
			button("Sandwich  ·  $6.50", consume_item.bind("meal"))
			button("Water  ·  $1.50", consume_item.bind("water"))
			add_text("Public drinking water and washrooms are beside the equipment district.", 16)
			button("Back to street", close_menu)
		"receipt":
			add_text(session.receipt, 25)
			add_text("Wallet  " + DeliverySession.money(session.wallet), 24, Color("9bceb7"))
			add_text("Your next request will arrive automatically while online.", 18)
			button("Back to street", close_menu)
	for child in modal_body.get_children():
		if child is Button:
			child.grab_focus()
			break

## Tab: the phone comes out of your pocket (PhoneDevice); the CourierNow app lives on it.
func open_phone() -> void:
	if not session.has_phone():
		notify("You don't have a phone yet. Trail & Tool sells a budget smartphone for $25." if not session.bought("budget_phone") else "Your phone is waiting on the pickup shelf at Trail & Tool.")
		return
	if city_map != null: city_map.hide()
	mode = "phone"
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.hide()
	menu_shade.hide()
	gameplay_ui.visible = true
	player.camera.make_current()
	phone.raise(player.camera)
	notice.hide()                     # the phone shows its own toasts; keep the screen clear
	notification_time = 0.0
	sound("phone_raise")
	tutorial.event("phone")

func on_phone_action(name: String, arg: String) -> void:
	match name:
		"page":
			tutorial.event("app_" + arg)
		"toggle_online":
			if session.online and tutorial.gate("offline") != "":
				phone.os.flash("Training: stay online")
				return
			if not session.online and not session.has_bag():
				phone.os.flash("You need a delivery bag first")
				return
			session.toggle_online()
			phone.os.flash("You're online" if session.online else "You're offline")
			save_session()
		"accept":
			if session.accept():
				phone.os.flash("Accepted · go to " + session.restaurant_name())
				sound("ui_accept")
				save_session()
		"reject":
			if tutorial.gate("reject") == "" and session.reject():
				save_session()
		"maps":
			close_menu()
			show_menu("map")

## E on a store computer (or its counter): the online shop of that store.
func open_terminal(store: String) -> void:
	if not ShopCatalog.LOCATIONS.has(store): return
	mode = "terminal"
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.hide()
	menu_shade.hide()
	gameplay_ui.hide()
	current_shop = store
	terminal.open(store, session)
	sound("kiosk_click")

func on_store_purchase(message: String) -> void:
	for id in session.bought_vehicles:
		# A new vehicle is rolled out in front of the store and becomes the one you use.
		session.active_vehicle = id
		var shop: Vector3 = ShopCatalog.LOCATIONS[current_shop]
		player.replace_vehicle(Vector3(signf(shop.x) * 79, 0.06, shop.z + 12))
	store_terminals.refresh()
	save_session()
	notify(message)

## The marked delivery area at the active order's door (shown once you have the package).
func sync_drop_zone() -> void:
	var state: String = session.order.get("state", "")
	var id: String = session.order.get("id", "")
	var want: bool = state in ["IN_HAND", "DROPPED", "CARRYING"]
	if want and (drop_zone == null or _zone_for != id or drop_zone.method != str(session.order.get("method", "meet"))):
		if drop_zone: drop_zone.clear()
		var address := int(session.order.address)
		drop_zone = DropZone.new()
		drop_zone.name = "DropZone"
		world.add_child(drop_zone)
		drop_zone.setup(address, world.doors[address], CityCatalog.address_facing(address), str(session.order.get("method", "meet")))
		_zone_for = id
	elif not want and drop_zone != null and drop_zone.customer == null:
		drop_zone.clear()
		drop_zone = null
		_zone_for = ""

## E on the customer's door: knock for "meet at door"; for "leave at door" it is left in the
## marked area in front of the door.
func at_door() -> String:
	if session.order.get("method", "meet") == "door":
		if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"]:
			deliver_here({"id": "dropzone"})
			return ""
		return "Leave it in the yellow marked area in front of the door (%s there)." % use_hint()
	if drop_zone and drop_zone.customer == null:
		# Every other house has a doorbell: ring it (Press_Doorbell, pressed at 0.47 s), else knock
		# (Knock_Door, knuckles on the door from 0.53 s). The courier turns to the door first and
		# waves when the customer opens it.
		var bell := drop_zone.address % 2 == 1
		var to_door := drop_zone.door_point - player.global_position
		var yaw := atan2(-to_door.x, -to_door.z)
		var played := player.avatar.play_gesture("doorbell" if bell else "knock_door", yaw) if player.avatar != null else -1.0
		var lead := (0.47 if bell else 0.5) if played > 0.0 else 0.0
		var tw := create_tween()
		tw.tween_interval(lead)
		tw.tween_callback(sound.bind("doorbell" if bell else "door_knock"))
		tw.tween_interval(1.1 - lead)                  # the door opens 1.1 s after the press, as before
		tw.tween_callback(func() -> void:
			if drop_zone:
				drop_zone.call_customer(session.order)
				sound("door_open")
				if player.avatar != null: player.avatar.play_gesture("wave", yaw))
		return "You ring the doorbell…" if bell else "You knock on the door…"
	return "%s is at the door. Hand the order over with %s." % [session.order.get("customer", "The customer"), use_hint()]

## Standing at (or in) the marked delivery area.
func near_zone(radius: float) -> bool:
	if drop_zone == null: return false
	return Vector2(player.position.x - drop_zone.global_position.x, player.position.z - drop_zone.global_position.z).length() < radius and absf(player.position.y - drop_zone.global_position.y) < 1.6

## Take a package off the shelf (or the ground). Yours: picked up, then packed in the backpack
## in one go (CourierSequence.pack) when you own the bag, else carried by hand. Someone else's:
## who it is for and who you are looking for.
func take_package_node(node: Node3D, distance: float) -> void:
	var info: Dictionary = node.get_meta("package")
	var result := session.take_package(info, distance)
	if not session.holding_package():
		notify(result)
		if result.begins_with("This one is for"):
			sound("ui_reject")
			flash_notice(Color("ffb4a2"))
		return
	_pickup_from = node.global_transform
	if node == dropped_package:
		dropped_package = null
		node.queue_free()
	else:
		shelves.take(node)
	sound("item_pickup")
	save_session()
	if session.has_bag():
		# Straight into the backpack: the order waits where it was until the hand takes it.
		var from: Transform3D = _pickup_from
		_pickup_from = null
		notify(result + " Packing it in your backpack…")
		start_pack(node.global_position, from)
	else:
		update_held_package()
		notify(result + " No delivery bag: carry it by hand (Trail & Tool sells one for $35).")

## One press: the held package goes into the backpack compartment that fits it.
func start_pack(toward: Variant, from: Variant = null) -> void:
	if sequence.running or not session.holding_package() or not session.has_bag(): return
	var slot := OrderDetails.best_slot(str(session.order.get("kind", "bag")))
	var pkg: Node3D = held_package
	if not is_instance_valid(pkg):
		pkg = package_model()
		world.add_child(pkg)
		pkg.global_transform = from if from is Transform3D else Transform3D(Basis.IDENTITY, player.global_position + player.body_forward() * 0.4 + Vector3(0, 1.0, 0))
	held_package = null
	_held_for = ""
	var face: Vector3 = toward if toward is Vector3 else player.global_position + player.body_forward()
	await sequence.pack(pkg, slot, face, func() -> void:
		var msg := session.stow(slot)
		if session.order.get("state") == "CARRYING":
			notify("%s  Deliver to %s · %s." % [msg.get_slice(".", 0) + ".", session.order.get("customer", ""), DeliverySession.ADDRESSES[int(session.order.address)]])
		else:
			notify(msg)
		save_session(), toward is Vector3 and (toward as Vector3).y - player.global_position.y < 0.6)

## Delivery at the door, one press: leave at door (into the marked area, proof photo) or meet at
## door (hand it to the customer), out of the backpack or from your hands (CourierSequence).
func deliver_here(target: Dictionary) -> void:
	var state: String = session.order.get("state", "")
	if not state in ["IN_HAND", "CARRYING", "DROPPED"] or drop_zone == null or sequence.running:
		return
	if tutorial.gate("deliver") != "":
		notify(tutorial.gate("deliver"))
		return
	if state == "DROPPED":
		notify("Pick the order up first (%s on it)." % use_hint())
		return
	var from_bag := state == "CARRYING"
	var slot: String = str(session.order.get("slot", OrderDetails.best_slot(str(session.order.get("kind", "bag")))))
	var pkg: Node3D = package_model() if from_bag else held_package
	if not from_bag:
		held_package = null
		_held_for = ""
	if target.id == "dropzone":
		if session.order.get("method", "meet") != "door":
			notify("This customer wants to meet you. Knock on the door (%s)." % use_hint())
			if not from_bag: held_package = pkg
			return
		# Set down in the middle of the lines, its name tag towards the street.
		var spot := Transform3D(Basis(Vector3.UP, drop_zone.rotation.y), drop_zone.global_position + Vector3(0, 0.005, 0))
		await sequence.leave(pkg, from_bag, slot, spot, func(node: Node3D) -> void:
			if session.order.get("state") == "CARRYING": session.unstow()
			session.drop_package(spot.origin, spot.basis.get_euler().y)
			dropped_package = node
			if dropped_package and not dropped_package.is_inside_tree(): world.add_child(dropped_package)
			complete_left())
		if session.order.get("state") == "COMPLETED": show_menu("receipt")
	elif target.id == "customer":
		var who: Node3D = drop_zone.customer
		await sequence.meet(pkg, from_bag, slot, who, func(node: Node3D) -> void:
			var result := session.deliver(int(session.order.address), 1.0)
			if session.order.get("state") == "COMPLETED":
				if drop_zone: drop_zone.customer_leaves(node)
				delivered("meet", false)
			else:
				if node: node.queue_free()
				notify(result))
		if session.order.get("state") == "COMPLETED": show_menu("receipt")

## Package down inside the lines: proof photo and payout.
func complete_left() -> void:
	if drop_zone == null or session.order.get("state") != "DROPPED": return
	if not drop_zone.contains(session.dropped_position()): return
	var result := session.leave_at_door(int(session.order.address), true)
	if session.order.get("state") == "COMPLETED":
		_flash.color.a = 0.85
		create_tween().tween_property(_flash, "color:a", 0.0, 0.45)
		sound("photo_shutter")
		var left := dropped_package
		dropped_package = null
		if left:
			var tw := left.create_tween()
			tw.tween_interval(3.0)
			tw.tween_callback(left.queue_free)
		delivered("door", not sequence.running)
	else:
		notify(result)

## A coloured pulse on the notice text (wrong package).
func flash_notice(colour: Color) -> void:
	notice.add_theme_color_override("font_color", colour)
	var tw := create_tween()
	tw.tween_interval(2.5)
	tw.tween_callback(func() -> void: notice.add_theme_color_override("font_color", HudStyle.INK))

func delivered(method: String, show_receipt_now := true) -> void:
	sound("delivery_success")
	if method == "meet": sound("customer_thanks")
	var tw := create_tween()
	tw.tween_interval(0.5)
	tw.tween_callback(sound.bind("coins"))
	session.receipt += "\n" + ("Photo proof sent to %s." % session.order.get("customer", "the customer") if method == "door" else "Handed to %s in person." % session.order.get("customer", "the customer"))
	save_session()
	if show_receipt_now: show_menu("receipt")
	else: notify("Delivered to %s!" % session.order.get("customer", "the customer"))

func sound(name: String) -> void:
	if audio and CityAudio.has_sound(name): audio.play_ui(name, -6.0)

## Title screen (new game, continue, settings, exit) or the Esc pause menu (ui/main_menu.gd).
func open_main_menu(title: bool) -> void:
	if city_map != null: city_map.hide()
	if bag_rig and bag_rig.out: bag_rig.put_on()
	mode = "start" if title else "pause"
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.hide()
	menu_shade.hide()
	gameplay_ui.hide()
	if title: menu_camera.make_current()
	else: player.camera.make_current()
	main_menu.has_save = FileAccess.file_exists(DeliverySave.PATH) or FileAccess.file_exists(DeliverySave.PATH + ".bak")
	main_menu.save_summary = save_summary() if main_menu.has_save else ""
	main_menu.open(not title)

func on_main_menu(action: String) -> void:
	match action:
		"continue": load_session()
		"resume": close_menu()
		"save": main_menu.flash("Shift saved." if save_session() else saves.error)
		"new_game": new_session()
		"exit_to_menu":
			save_session()
			show_menu("start")
		"quit":
			if mode == "pause": save_session()
			get_tree().quit()
		"settings_changed": GameSettings.apply(player)

## "Day 3 · $142.50 · 7 deliveries" for the Continue button.
func save_summary() -> String:
	var path := DeliverySave.PATH if FileAccess.file_exists(DeliverySave.PATH) else DeliverySave.PATH + ".bak"
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary: return ""
	var d: Dictionary = data
	var done := int(d.get("completed", 0))
	return "Day %d  ·  %s  ·  %d %s" % [int(float((d.get("dispatch", {}) as Dictionary).get("calendar", 0)) / 1440.0) + 1, DeliverySession.money(int(d.get("wallet", 0))), done, "delivery" if done == 1 else "deliveries"]

## Full-screen city map with clickable places and road navigation (ui/city_map.gd).
func open_city_map() -> void:
	tutorial.event("map")
	mode = "map"
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.hide()
	menu_shade.hide()
	gameplay_ui.hide()
	if city_map == null:
		city_map_layer = CanvasLayer.new()
		city_map_layer.layer = 20
		city_map_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(city_map_layer)
		city_map = preload("res://ui/city_map.gd").new()
		city_map_layer.add_child(city_map)
		city_map.closed.connect(close_menu)
		city_map.destination_chosen.connect(func(place: Dictionary):
			close_menu()
			notify("Navigating to %s · follow the mint route on the minimap." % place.name))
	city_map.open(player, world)

func order_items_text() -> String:
	var parts := PackedStringArray()
	for it in session.order.get("items", []): parts.append("%dx %s" % [int(it[1]), it[0]])
	return ", ".join(parts)

## Receipt panel while looking at a package on a shelf: read it before you take it.
func show_receipt(target: Dictionary) -> void:
	if receipt_panel == null:
		# The package's name tag, read before you take it: a paper card in the right column,
		# under the status panel. Who it is for and the order code big, the printed receipt under it.
		receipt_panel = PanelContainer.new()
		receipt_panel.name = "NameTag"
		receipt_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var paper := HudStyle.panel(HudStyle.AMBER, HudStyle.PAPER, 12, 9)
		paper.shadow_color = Color(0, 0, 0, 0.3)
		receipt_panel.add_theme_stylebox_override("panel", paper)
		receipt_panel.custom_minimum_size.x = STATUS_WIDTH
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 3)
		receipt_panel.add_child(col)
		receipt_head = HudStyle.eyebrow("", HudStyle.PAPER_MUTED, HudStyle.MICRO)
		col.add_child(receipt_head)
		receipt_name = HudStyle.label("", HudStyle.TAG, HudStyle.PAPER_INK, HudStyle.Face.DISPLAY, HudStyle.BOLD)
		receipt_name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		receipt_name.custom_minimum_size.x = STATUS_WIDTH - 27
		receipt_name.add_theme_constant_override("line_spacing", -3)
		col.add_child(receipt_name)
		var rule := ColorRect.new()
		rule.color = HudStyle.AMBER
		rule.custom_minimum_size = Vector2(0, 2)
		col.add_child(rule)
		receipt_label = HudStyle.label("", 9, Color("2a2722"), HudStyle.Face.MONO)
		receipt_label.add_theme_constant_override("line_spacing", -1)
		col.add_child(receipt_label)
		gameplay_ui.add_child(receipt_panel)
	var showing: bool = not target.is_empty() and target.id == "package"
	receipt_panel.visible = showing
	if showing:
		var info: Dictionary = target.node.get_meta("package")
		var name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(str(info.restaurant)))]
		# The tag, big: who it is for and the order code; the printed receipt under it.
		receipt_head.text = "NAME TAG  ·  " + OrderDetails.package_label(str(info.kind), info.get("items", [])).to_upper()
		receipt_name.text = "%s\n%s" % [str(info.customer).to_upper(), info.ticket]
		receipt_label.text = OrderDetails.receipt_text(info, name, DeliverySession.ADDRESSES[int(info.get("address", 0))], session.calendar_minutes)
		receipt_panel.reset_size()
		receipt_panel.position = Vector2(gameplay_ui.size.x - HudStyle.MARGIN - receipt_panel.size.x, status_panel.position.y + status_panel.size.y + HudStyle.GAP)

## The package in your hands (bottom-right of the view) while it is out of the bag.
func update_held_package() -> void:
	if sequence.running: return       # the sequence moves the package itself
	var want: bool = session.holding_package() and not player.mounted
	var id: String = str(session.order.get("id", ""))
	if want and (held_package == null or _held_for != id):
		if held_package: held_package.queue_free()
		var info := {"customer": session.order.customer, "ticket": session.order.ticket, "kind": session.order.kind, "items": session.order.items, "restaurant": session.restaurant_id()}
		var body := shelves.make_package(info)
		body.collision_layer = 0
		held_package = body
		player.hold_socket.add_child(held_package)
		_held_for = id
		if _pickup_from is Transform3D:
			held_package.global_transform = _pickup_from
			to_hands(held_package)
		else:
			held_package.transform = HOLD_POSE
	_pickup_from = null
	if held_package: held_package.visible = want

## Where a held package sits: two hands, low and to the right of the view (in third person the
## player's hold socket puts the same pose into the character's hands).
var HOLD_POSE := CourierPlayer.HOLD_POSE

## Animate a package (child of the player's hold socket) into the hands.
func to_hands(node: Node3D) -> void:
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(node, "transform", HOLD_POSE, 0.4)

## G: put the held package down on the ground (or a counter) just in front of you.
func drop_held() -> void:
	if not session.holding_package():
		notify("You're not holding anything.")
		return
	var forward := player.body_forward()
	var from := player.global_position + forward * 0.8 + Vector3(0, 1.4, 0)
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -3.0, 0))
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
		notify("There's no flat spot to put it down here.")
		return
	var start: Variant = held_package.global_transform if is_instance_valid(held_package) else null
	var result := session.drop_package(hit.position, player.body_yaw())
	if session.order.get("state") == "DROPPED":
		if is_instance_valid(held_package): held_package.queue_free()
		held_package = null
		_held_for = ""
		sync_dropped(start)
		tutorial.event("dropped")
		sound("package_drop")
		save_session()
		if drop_zone and session.order.get("method", "meet") == "door" and drop_zone.contains(hit.position) and tutorial.gate("deliver") == "":
			complete_left()
			return
	notify(result)

## Keep a package model on the ground while the order is DROPPED (also after loading a save).
func sync_dropped(fall_from: Variant = null) -> void:
	var down: bool = session.order.get("state") == "DROPPED"
	if down and dropped_package == null:
		var a: Array = session.order.get("dropped_at", [0, 0, 0, 0])
		dropped_package = package_model()
		dropped_package.collision_layer = 1
		dropped_package.name = "DroppedPackage"
		world.add_child(dropped_package)
		var rest := Transform3D(Basis(Vector3.UP, float(a[3])), Vector3(float(a[0]), float(a[1]), float(a[2])))
		if fall_from is Transform3D:
			dropped_package.global_transform = fall_from
			var tw := create_tween()
			tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			tw.tween_property(dropped_package, "global_transform", rest, 0.35)
		else:
			dropped_package.global_transform = rest
	elif not down and dropped_package != null:
		dropped_package.queue_free()
		dropped_package = null

## A fresh model of the current order's package (with its logo and receipt).
func package_model() -> Node3D:
	var info := {"customer": session.order.get("customer", ""), "ticket": session.order.get("ticket", ""), "kind": session.order.get("kind", "bag"), "items": session.order.get("items", []), "restaurant": session.restaurant_id(),
		"subtotal": session.order.get("subtotal", 0), "payment_method": session.order.get("payment_method", ""), "address": int(session.order.get("address", 0))}
	var body := shelves.make_package(info)
	body.collision_layer = 0
	return body

## Backpack open: the held package follows the mouse; the compartment under it lights up
## (green: it fits, red: it doesn't). A packed compartment lights up to be taken out.
func update_bag_drag(delta: float) -> void:
	if not bag_rig.out or not session.has_bag():
		_drag_slot = ""
		return
	var mouse := get_viewport().get_mouse_position()
	var origin := player.camera.project_ray_origin(mouse)
	var direction := player.camera.project_ray_normal(mouse)
	var slot := bag_rig.pick(origin, direction)
	var kind: String = session.order.get("kind", "bag")
	if session.holding_package():
		_drag_slot = slot
		bag_rig.highlight(slot, OrderDetails.fits(kind, slot))
		if is_instance_valid(held_package):
			var goal := bag_rig.slot_mouth(slot) if slot != "" else origin + direction * 0.62
			held_package.global_position = held_package.global_position.lerp(goal, minf(1.0, delta * 14.0))
	else:
		var packed: String = session.order.get("slot", "") if session.order.get("state") == "CARRYING" else ""
		_drag_slot = slot if slot == packed else ""
		bag_rig.highlight(_drag_slot, true)
	Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND if _drag_slot != "" else Input.CURSOR_ARROW)

## Bag compartment clicked: pack the held package there, or take the packed one out.
func bag_click(slot: String) -> void:
	var result := ""
	if session.holding_package() and tutorial.gate("stow") != "":
		notify(tutorial.gate("stow"))
		return
	if session.holding_package():
		result = session.stow(slot)
		if session.order.get("state") == "CARRYING":
			# The package goes from your hands into the open bag's compartment.
			if not is_instance_valid(held_package):
				# Still flying into the hands (the bag opened the same frame): make it now.
				session.order.state = "IN_HAND"
				update_held_package()
				session.order.state = "CARRYING"
			var pkg: Node3D = held_package if is_instance_valid(held_package) else package_model()
			held_package = null
			_held_for = ""
			bag_rig.pack(pkg, slot)
			sound("package_place")
	elif session.order.get("state") == "CARRYING" and session.order.get("slot", "") == slot:
		result = session.unstow()
		# Lift it out of the compartment back into your hands.
		var node := bag_rig.take_out()
		if node:
			player.hold_socket.add_child(node)
			node.global_transform = node.get_meta("from")
			held_package = node
			_held_for = str(session.order.get("id", ""))
			to_hands(node)
	else:
		result = "Empty compartment." if session.has_bag() else "You don't own a delivery bag yet."
	notify(result)
	save_session()
	if mode == "bag": show_menu("bag")

## F: the insulated bag. Top: one big compartment (food bags). Middle: two halves (drinks and
## desserts stay level). Bottom: a flat full-width drawer for pizza boxes.
func build_bag_menu() -> void:
	add_text("INSULATED DELIVERY BAG", 22, Color("9bceb7"))
	if not session.has_bag():
		add_text("You don't own a delivery bag yet.\nTrail & Tool (equipment store) sells an insulated courier bag for $35. Without it you can only walk an order to the customer by hand.", 18)
		if session.holding_package(): add_text("Holding: %s's order" % session.order.customer, 18, Color("f4e7c4"))
		button("Close (%s)" % binding("bag"), close_menu)
		return
	var state: String = session.order.get("state", "")
	var kind: String = session.order.get("kind", "bag")
	var holding := session.holding_package()
	if holding:
		add_text("Holding %s's %s\nMove it over a compartment in the bag and click to drop it in, or press %s" % [session.order.customer, str(OrderDetails.KIND_NAMES[kind]).to_lower(), binding("interact")], 16, Color("f4e7c4"))
	else:
		add_text("Click a packed order to take it out.", 16, Color("f4e7c4"))
	var grid := VBoxContainer.new()
	grid.add_theme_constant_override("separation", 6)
	modal_body.add_child(grid)
	grid.add_child(bag_slot("top", Vector2(0, 150), state, kind, holding))
	var middle := HBoxContainer.new()
	middle.add_theme_constant_override("separation", 6)
	grid.add_child(middle)
	middle.add_child(bag_slot("left", Vector2(0, 92), state, kind, holding))
	middle.add_child(bag_slot("right", Vector2(0, 92), state, kind, holding))
	grid.add_child(bag_slot("bottom", Vector2(0, 62), state, kind, holding))
	button("Close (%s)" % binding("bag"), close_menu)

func bag_slot(slot: String, min_size: Vector2, state: String, kind: String, holding: bool) -> Button:
	var b := Button.new()
	b.name = "Slot_" + slot
	b.custom_minimum_size = min_size
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var packed: bool = state == "CARRYING" and session.order.get("slot", "") == slot
	var fits: bool = holding and OrderDetails.fits(kind, slot)
	var hint := "pizza boxes" if slot == "bottom" else ("drinks & desserts" if slot != "top" else "food bags")
	b.text = "%s\n%s" % [str(OrderDetails.SLOT_NAMES[slot]).to_upper(), ("● " + str(session.order.customer) + " · " + str(OrderDetails.KIND_NAMES[kind])) if packed else ("fits this order" if fits else hint)]
	var box := StyleBoxFlat.new()
	box.bg_color = Color("2f6f58") if packed else (Color("3f5a4f") if fits else Color("1d2a2c"))
	box.border_color = Color("9bceb7") if fits or packed else Color("4b5e60")
	box.set_border_width_all(2)
	box.set_corner_radius_all(8)
	for st in ["normal", "hover", "pressed", "focus"]: b.add_theme_stylebox_override(st, box)
	b.add_theme_font_size_override("font_size", 15)
	b.pressed.connect(bag_click.bind(slot))
	return b

func close_menu() -> void:
	if bag_rig and bag_rig.out: bag_rig.put_on()
	if phone and phone.out:
		phone.lower(player.camera)
		sound("phone_lower")
	if terminal and terminal.visible: terminal.hide()
	if mode == "bag":
		_drag_slot = ""
		Input.set_default_cursor_shape(Input.CURSOR_ARROW)
		if is_instance_valid(held_package) and session.holding_package(): to_hands(held_package)
	if main_menu: main_menu.close()
	mode = ""
	if city_map != null: city_map.hide()
	modal.hide()
	menu_shade.hide()
	gameplay_ui.show()
	player.camera.make_current()
	get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func buy_item(id: String) -> void:
	var result := session.buy(id)
	player.refresh_equipment()
	save_session()
	show_menu("shop")
	notify(result)

func consume_item(id: String) -> void:
	var result := session.consume(id)
	save_session()
	show_menu("food")
	notify(result)

func equip_vehicle(id: String) -> void:
	if not session.owns(id) or not ShopCatalog.is_vehicle(id): return
	if player.mounted:
		notify("Park before changing vehicles.")
		return
	session.active_vehicle = id
	var shop: Vector3 = ShopCatalog.LOCATIONS[current_shop]
	player.replace_vehicle(Vector3(signf(shop.x) * 79, 0.06, shop.z + 12))
	save_session()
	close_menu()
	notify("Your vehicle is parked in the shop forecourt. Walk up and press E.")

func new_session() -> void:
	player.mounted = false
	player.riding_speed = 0
	player.camera.position.y = 1.65
	player.bicycle.position = Vector3(-8, 0, 19)
	session = DeliverySession.new()
	session.start_career()
	player.session = session
	player.replace_vehicle(Vector3(-8, 0, 19))
	if store_terminals: store_terminals.session = session
	minimap.session = session
	if shelves: shelves.session = session
	session.changed.connect(update_hud)
	player.position = Vector3(-8, 0.2, 23)
	player.rotation = Vector3.ZERO
	player.camera.rotation = Vector3.ZERO
	if dropped_package: dropped_package.queue_free()
	dropped_package = null
	tutorial.start()
	save_session()
	close_menu()
	player.refresh_equipment()
	notify("Welcome! You start on foot with $100. Follow the training tasks on the left.")

func pickup_route_distance() -> float:
	# Manhattan path via the open sidewalk and kitchen frontage.
	return absf(player.position.z - 15.0) + absf(player.position.x + 14.0) + 3.0

func save_session() -> bool:
	if not save_enabled or "--smoke-test" in OS.get_cmdline_user_args():
		return true
	var data := session.snapshot()
	data.player = {"position": [player.position.x, player.position.y, player.position.z], "yaw": player.rotation.y}
	data.player.bicycle = [player.bicycle.position.x, player.bicycle.position.y, player.bicycle.position.z]
	data.player.mounted = player.mounted
	data.player.bicycle_yaw = player.bicycle.rotation.y
	var success := saves.save_game(data)
	if not success:
		notify(saves.error)
	return success

func load_session() -> void:
	var data := saves.load_game()
	if data.is_empty():
		if main_menu.visible: main_menu.flash(saves.error)
		else: add_text(saves.error, 18, Color("f0c28b"))
		return
	session.restore(data)
	if store_terminals: store_terminals.session = session
	player.replace_vehicle(Vector3(-8, 0, 19))
	player.position = Vector3(data.player.position[0], data.player.position[1], data.player.position[2])
	player.rotation.y = data.player.yaw
	var bike_position: Array = data.player.get("bicycle", [-8, 0, 19])
	player.bicycle.position = Vector3(bike_position[0], bike_position[1], bike_position[2])
	player.bicycle.rotation.y = data.player.get("bicycle_yaw", data.player.yaw)
	player.mounted = data.player.get("mounted", false)
	player.riding_speed = 0
	player.camera.position.y = 1.85 if player.mounted else 1.65
	player.velocity = Vector3.ZERO
	player.camera.rotation = Vector3.ZERO
	player.apply_vehicle_camera()
	world.set_time(session.hour())
	close_menu()
	notify("Shift restored." if saves.error == "" else saves.error)

func notify(message: String) -> void:
	notice.text = message
	notification_time = 7.0
	notice.visible = true

func update_hud() -> void:
	if objective == null:
		return
	var state: String = session.order.get("state", "")
	street_label.text = StreetNames.describe(player.position).to_upper()
	objective.text = ("Online · requests arrive automatically" if session.online else "Offline · open your phone to go online")
	if session.online and session.demand().begins_with("Kitchen closed"):
		objective.text = "Kitchen closed · opens 08:00"
	route_marker.visible = false
	var who := str(session.order.get("customer", ""))
	var address_short: String = DeliverySession.ADDRESSES[int(session.order.get("address", 0))].replace(" Avenue", " Ave").replace(" Street", " St")
	if state == "OFFERED":
		objective.text = "New offer: %s · open phone (%s)" % [who, binding("phone")]
	elif state == "ACCEPTED":
		objective.text = "Collect %s's order at %s" % [who, session.restaurant_name()]
		route_marker.position = session.pickup_position() + Vector3(0, 2, 0)
	elif state == "DROPPED":
		objective.text = "Pick up %s's order" % who
		route_marker.visible = player.position.distance_to(session.dropped_position()) > 4.0
		route_marker.position = session.dropped_position() + Vector3(0, 1.2, 0)
		route_marker.text = "YOUR PACKAGE\n%d m" % int(player.position.distance_to(session.dropped_position()))
	elif state in ["CARRYING", "IN_HAND"]:
		objective.text = "Deliver to %s · %s" % [who, address_short]
		route_marker.position = world.doors[int(session.order.address)] + Vector3(0, 2.5, 0)
		route_marker.text = "%s\n%d m" % [who.to_upper(), int(player.position.distance_to(world.doors[int(session.order.address)]))]
	update_order_plate(state)
	# Backpack line: [key] HEAD  what's in it / what you're doing with the order.
	var bag_key := ""
	var bag_title := ""
	var bag_text := ""
	if session.has_bag():
		bag_key = binding("bag")
		bag_title = "BACKPACK"
		bag_text = ("%s's %s · %s" % [who, str(OrderDetails.KIND_NAMES.get(session.order.get("kind", "bag"), "order")).to_lower(), str(OrderDetails.SLOT_NAMES.get(session.order.get("slot", ""), "bag")).to_lower()]) if state == "CARRYING" else "Empty · look inside"
	if sequence != null and sequence.running:
		bag_key = ""
		bag_title = str({"pack": "PACKING", "leave": "LEAVING AT DOOR", "meet": "HANDING OVER"}.get(sequence.kind, "ORDER"))
		bag_text = "%s's order…" % who
	elif state == "IN_HAND":
		bag_key = use_hint() if session.has_bag() else ""
		bag_title = "HOLDING"
		bag_text = "%s's order · %s" % [who, "pack it" if session.has_bag() else "no bag: carry it by hand"]
	elif state == "DROPPED":
		bag_key = use_hint()
		bag_title = "ON THE GROUND"
		bag_text = "%s's order · pick it up" % who
	bag_chip.visible = bag_title != ""
	if bag_key != _bag_key_shown:
		_bag_key_shown = bag_key
		HudStyle.fill_keys(bag_keys, HudStyle.parse_keys(("[%s]" % bag_key) if bag_key != "" else ""), HudStyle.SMALL, HudStyle.INK, HudStyle.CAPTION)
		bag_keys.visible = bag_key != ""
	bag_head.text = bag_title
	bag_label.text = bag_text
	# Status: clock, date · day, weather, wallet, needs.
	var day := int(session.calendar_minutes / 1440) + 1
	var date := session.calendar()
	clock_label.text = "%02d:%02d" % [int(date.hour), int(date.minute)]
	var weekdays := ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
	var months := ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	calendar_label.text = "%s %d %s  ·  DAY %d" % [weekdays[int(date.weekday)], int(date.day), months[int(date.month) - 1], day]
	weather_label.text = world.weather.describe().replace("  ", " · ").to_upper() if world.weather != null else ("NIGHT" if session.hour() < 6 or session.hour() >= 20 else "DAYLIGHT")
	wallet_label.text = DeliverySession.money(session.wallet)
	set_need("ENERGY", session.energy / 100.0, false)
	set_need("FOOD", session.hunger / 100.0, false)
	set_need("WATER", session.hydration / 100.0, false)
	set_need("WC", session.bladder / 100.0, true)
	var water := int(session.supplies.get("water_bottle", 0))
	var snack := int(session.supplies.get("energy_bar", 0))
	var supplies := ("[%s] Water ×%d  [%s] Energy bar ×%d" % [binding("use_water"), water, binding("use_snack"), snack]) if water + snack > 0 else ""
	if supplies != _supplies_shown:
		_supplies_shown = supplies
		HudStyle.fill_keys(supplies_row, HudStyle.parse_keys(supplies), HudStyle.CAPTION, HudStyle.INK_SOFT, HudStyle.MICRO)
		supplies_row.visible = supplies != ""
		status_panel.reset_size()
	if player.mounted:
		prompt_text = "[Space]  Brake   [%s]  %s" % [binding("interact"), "Exit" if ShopCatalog.is_car(session.active_vehicle) else "Dismount"]
	elif player.has_vehicle() and player.position.distance_to(player.bicycle.position) < 2:
		prompt_text = "[%s]  Ride the %s" % [binding("interact"), session.active_vehicle.replace("_", " ")]
	if navigation_label == null:
		return
	if state == "OFFERED":
		navigation_label.text = "New request · %s to review" % binding("phone")
	elif state == "ACCEPTED":
		var pickup_distance := CityCatalog.distance(minimap.route_points())
		navigation_label.text = "%d m · %s" % [int(pickup_distance), session.restaurant_name()]
	elif state == "DROPPED":
		navigation_label.text = "%d m · your package" % int(player.position.distance_to(session.dropped_position()))
	elif state in ["CARRYING", "IN_HAND"]:
		var distance := CityCatalog.distance(minimap.route_points())
		navigation_label.text = "%d m · %s" % [int(distance), DeliverySession.ADDRESSES[int(session.order.address)]]
	elif not CityNavigation.target.is_empty():
		var goal: Vector3 = CityNavigation.target.at
		if player.position.distance_to(goal) < 7.0:
			notify("You have arrived at %s." % CityNavigation.target.name)
			CityNavigation.target = {}
			return
		navigation_label.text = "%d m · %s" % [int(CityCatalog.distance(minimap.route_points())), CityNavigation.target.name]
		route_marker.visible = true
		route_marker.position = goal + Vector3(0, 3, 0)
		route_marker.text = "%s\n%d m" % [CityNavigation.target.name, int(player.position.distance_to(goal))]
	else:
		navigation_label.text = "Online · awaiting requests" if session.online else "Offline · open phone to work"

## One needs meter: full is good (energy, food, water) or bad (WC).
func set_need(need: String, value: float, high_is_bad: bool) -> void:
	var bar: ProgressBar = need_bars.get(need)
	if bar == null: return
	bar.value = clampf(value, 0.0, 1.0)
	var level := 1.0 - value if high_is_bad else value
	HudStyle.set_meter_colour(bar, HudStyle.ACCENT if level > 0.35 else (HudStyle.AMBER if level > 0.15 else HudStyle.DANGER))

## The order chip under the objective while an order is active (the training card shows the
## same chip itself): "ORDER FOR / ELIF KAYA / CE-012 · Food bag · medium".
func update_order_plate(state: String) -> void:
	var plate_on: bool = state in DeliverySession.ACTIVE and tutorial != null and not tutorial.active()
	order_plate.visible = plate_on
	if plate_on:
		order_plate_name.text = str(session.order.get("customer", "")).to_upper()
		order_plate_info.text = "%s  ·  %s" % [session.order.get("ticket", ""), OrderDetails.package_label(str(session.order.get("kind", "bag")), session.order.get("items", []))]

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
