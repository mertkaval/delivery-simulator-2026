extends Node3D
var session := DeliverySession.new()
var saves := DeliverySave.new()
var world: CedarNeighborhood
var street_label: Label
var player: CourierPlayer
var hud: CanvasLayer
var objective: Label
var stats: Label
var prompt: Label
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
var needs_label: Label
var current_shop := "equipment"
var save_enabled := true
var audio: CityAudio

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
	add_child(route_marker)
	session.changed.connect(update_hud)
	bag_rig = BagRig.new()
	bag_rig.name = "BagRig"
	player.camera.add_child(bag_rig)
	shelves = PickupShelves.new()
	shelves.name = "PickupShelves"
	world.add_child(shelves)
	shelves.setup(world, session)
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
	if "--smoke-test" in OS.get_cmdline_user_args():
		call_deferred("smoke_test")

func bind_inputs() -> void:
	if not InputMap.has_action("bicycle"):
		InputMap.add_action("bicycle")
		var bike_key := InputEventKey.new()
		bike_key.physical_keycode = KEY_B
		InputMap.action_add_event("bicycle", bike_key)
	var actions := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D, "sprint": KEY_SHIFT, "jump": KEY_SPACE, "interact": KEY_E, "phone": KEY_TAB, "map": KEY_M, "pause_game": KEY_ESCAPE, "bell": KEY_Q, "bag": KEY_F, "drop": KEY_G, "use_water": KEY_1, "use_snack": KEY_2}
	for action in actions:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = actions[action]
			InputMap.action_add_event(action, key)

func binding(action: String) -> String:
	var event := InputMap.action_get_events(action)[0] as InputEventKey
	return OS.get_keycode_string(event.physical_keycode if event.physical_keycode != 0 else event.keycode)

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
		notify(session.use_supply("water_bottle" if event.is_action_pressed("use_water") else "energy_bar"))
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
	elif mode == "" and event.is_action_pressed("interact"):
		interact()
		get_viewport().set_input_as_handled()

func _process(delta: float) -> void:
	if mode == "bag": update_bag_drag(delta)
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
	var target := player.target()
	prompt.text = ""
	if not target.is_empty():
		var title: String = target.id
		if title == "package":
			var info: Dictionary = target.node.get_meta("package")
			title = "Take order for %s (%s)" % [info.customer, info.ticket]
		elif title == "pickup" or title.begins_with("pickup_"):
			title = "Courier pickup shelf"
		elif title.begins_with("cedar_door_"):
			title = "Open / close house door"
		elif title.begins_with("door_"):
			var mine: bool = session.order.get("state") in DeliverySession.ACTIVE and int(title.trim_prefix("door_")) == int(session.order.get("address", -1))
			title = (("Knock  /  " if session.order.get("method", "meet") == "meet" else "Door  /  ") if mine else "") + DeliverySession.ADDRESSES[int(title.trim_prefix("door_"))]
		elif title.begins_with("kiosk_") or title.begins_with("store_") and title != "store_pickup":
			title = "Use the store computer"
		elif title == "store_pickup":
			var idx := int(target.node.get_meta("pickup_index", -1))
			title = "Collect  " + (str(ShopCatalog.ITEMS[session.pickups[idx].id].name) if idx >= 0 and idx < session.pickups.size() else "item")
		elif title == "dropzone":
			title = "Leave the order here"
		elif title == "customer":
			title = "Hand over the order"
		elif title == "shop":
			title = "Browse delivery equipment"
		elif title == "home":
			title = "Rest and save"
		prompt.text = "[%s]  %s" % [binding("interact"), title]
	# At the door, E works by proximity (see interact): say so whatever the crosshair is on.
	if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"] and (target.is_empty() or str(target.id).begins_with("door_")):
		var flat := Vector2(player.position.x - drop_zone.global_position.x, player.position.z - drop_zone.global_position.z).length()
		if drop_zone.method == "door" and flat < 1.9:
			prompt.text = "[%s]  Leave the order here" % binding("interact")
		elif drop_zone.customer != null and player.position.distance_to(drop_zone.customer.global_position) < 2.2:
			prompt.text = "[%s]  Hand the order to %s" % [binding("interact"), session.order.get("customer", "the customer")]
	show_receipt(target)
	update_held_package()
	update_hud()

func interact() -> void:
	if not player.mounted and session.holding_package():
		var near_vehicle := player.position.distance_to(player.bicycle.position) < 2.5
		var t := player.target()
		if near_vehicle and (t.is_empty() or not str(t.id).begins_with("door_")):
			notify("Put the food in your delivery bag first (%s). Loose food can't ride along." % binding("bag"))
			return
	if player.mounted:
		notify(player.toggle_bicycle())
		save_session()
		return
	var target := player.target()
	# At the customer's door, E works without aiming exactly: standing in/at the marked area
	# (leave at door) or next to the waiting customer (meet at door).
	if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"] and (target.is_empty() or str(target.id).begins_with("door_")):
		var flat := Vector2(player.position.x - drop_zone.global_position.x, player.position.z - drop_zone.global_position.z).length()
		if drop_zone.method == "door" and flat < 1.9:
			deliver_here({"id": "dropzone"})
			return
		if drop_zone.customer != null and player.position.distance_to(drop_zone.customer.global_position) < 2.2:
			deliver_here({"id": "customer"})
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
		var info: Dictionary = target.node.get_meta("package")
		var node: Node3D = target.node
		result = session.take_package(info, target.distance)
		if session.holding_package():
			_pickup_from = node.global_transform
			if node == dropped_package:
				dropped_package = null
				node.queue_free()
			else:
				shelves.take(node)
			save_session()
		notify(result)
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
			result = "Find the package whose receipt says %s · order %s, and take it (%s)." % [session.order.get("customer", "?"), session.order.get("ticket", "?"), binding("interact")]
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
	label.add_theme_color_override("font_shadow_color",Color(0,0,0,.85))
	label.add_theme_constant_override("shadow_offset_x",1)
	label.add_theme_constant_override("shadow_offset_y",2)
	return label

func build_hud() -> void:
	hud = CanvasLayer.new()
	add_child(hud)
	gameplay_ui = Control.new()
	gameplay_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	gameplay_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(gameplay_ui)
	var top := PanelContainer.new()
	top.position = Vector2(24, 24)
	top.custom_minimum_size = Vector2(445, 120)
	top.add_theme_stylebox_override("panel", style_panel(Color(0.055, 0.11, 0.12, 0.94)))
	hud.add_child(top)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	top.add_child(column)
	street_label = make_label("ATATÜRK AVENUE  /  DELIVERY SIMULATOR", 15, Color("9bceb7"))
	column.add_child(street_label)
	objective = make_label("", 21)
	column.add_child(objective)
	stats = make_label("", 16)
	column.add_child(stats)
	var calendar_bar := PanelContainer.new()
	calendar_bar.position = Vector2(610, 24)
	calendar_bar.custom_minimum_size = Vector2(646, 94)
	calendar_bar.add_theme_stylebox_override("panel", style_panel(Color(0.035, 0.065, 0.085, 0.94)))
	hud.add_child(calendar_bar)
	var calendar_column := VBoxContainer.new()
	calendar_bar.add_child(calendar_column)
	calendar_label = make_label("", 18, Color("e1e9ee"))
	calendar_column.add_child(calendar_label)
	needs_label = make_label("", 14, Color("9db9b0"))
	calendar_column.add_child(needs_label)
	minimap = preload("res://ui/minimap.gd").new()
	minimap.player = player
	minimap.session = session
	minimap.world = world
	minimap.position = Vector2(24, 414)
	minimap.size = Vector2(220, 220)
	hud.add_child(minimap)
	navigation_label = make_label("", 15, Color("b6f3d1"))
	navigation_label.position = Vector2(36, 641)
	hud.add_child(navigation_label)
	var controls := make_label("%s  Move     %s  Sprint     %s  Interact     %s  Bag     %s  Drop     %s  Phone     %s  Map     %s  Pause" % ["WASD", binding("sprint"), binding("interact"), binding("bag"), binding("drop"), binding("phone"), binding("map"), binding("pause_game")], 16)
	controls.position = Vector2(24, 679)
	hud.add_child(controls)
	var center := make_label("+", 24)
	center.position = Vector2(633, 343)
	hud.add_child(center)
	prompt = make_label("", 20)
	prompt.position = Vector2(350, 585)
	prompt.size = Vector2(580, 40)
	prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hud.add_child(prompt)
	notice = make_label("", 18)
	notice.position = Vector2(330, 480)
	notice.size = Vector2(620, 100)
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	notice.add_theme_color_override("font_color", Color("ffffff"))
	notice.add_theme_color_override("font_shadow_color", Color.BLACK)
	notice.add_theme_constant_override("shadow_offset_x", 2)
	notice.add_theme_constant_override("shadow_offset_y", 2)
	hud.add_child(notice)
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
	hud.add_child(modal)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	modal.add_child(scroll)
	modal_body = VBoxContainer.new()
	modal_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_body.add_theme_constant_override("separation", 12)
	scroll.add_child(modal_body)

func add_text(text: String, size: int = 20, color: Color = Color("e6efeb")) -> void:
	if mode in ["phone", "map"]: size = int(size * 0.83)
	var label := make_label(text, size, color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = 0
	modal_body.add_child(label)

func button(text: String, callback: Callable) -> void:
	var control := Button.new()
	control.text = text
	control.custom_minimum_size.y = 46
	control.add_theme_font_size_override("font_size", 16 if mode in ["phone", "map"] else 19)
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
	modal.position = Vector2(830, 28)
	modal.size = Vector2(420, 640)
	var style := style_panel(Color(0.04, 0.075, 0.09, 0.92))
	style.set_corner_radius_all(28 if which == "phone" else 10)
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

## E on the customer's door: knock for "meet at door", a reminder for "leave at door".
func at_door() -> String:
	if session.order.get("method", "meet") == "door":
		return "Leave it in the yellow marked area in front of the door: press %s there, or hold it and press %s." % [binding("interact"), binding("drop")]
	if drop_zone and drop_zone.customer == null:
		sound("door_knock")
		var tw := create_tween()
		tw.tween_interval(1.1)
		tw.tween_callback(func() -> void:
			if drop_zone:
				drop_zone.call_customer(session.order)
				sound("door_open"))
		return "You knock on the door…"
	return "%s is at the door. Hand the order over with %s." % [session.order.get("customer", "The customer"), binding("interact")]

## E on the delivery area (leave at door) or on the customer (meet at door).
func deliver_here(target: Dictionary) -> void:
	var state: String = session.order.get("state", "")
	if not state in ["IN_HAND", "CARRYING", "DROPPED"] or drop_zone == null:
		return
	if tutorial.gate("deliver") != "":
		notify(tutorial.gate("deliver"))
		return
	var address := int(session.order.address)
	if target.id == "dropzone":
		if session.order.get("method", "meet") != "door":
			notify("This customer wants to meet you. Knock on the door (%s)." % binding("interact"))
			return
		if state == "DROPPED":
			notify("Pick the order up and put it down inside the lines.")
			return
		var from: Variant = null
		if state == "CARRYING":
			# The bag swings round and the order comes out of its compartment.
			var node := bag_rig.take_out()
			from = node.get_meta("from") if node else null
			if node: node.queue_free()
			session.unstow()
			bag_rig.take_off()
			var tw := create_tween()
			tw.tween_interval(0.6)
			tw.tween_callback(bag_rig.put_on)
		elif is_instance_valid(held_package):
			from = held_package.global_transform
			held_package.queue_free()
			held_package = null
			_held_for = ""
		session.drop_package(drop_zone.global_position, drop_zone.rotation.y)
		sync_dropped(from)
		complete_left()
	elif target.id == "customer":
		if state == "DROPPED":
			notify("Pick the order up first.")
			return
		var pkg: Node3D = null
		if state == "CARRYING":
			pkg = bag_rig.take_out()
			if pkg:
				world.add_child(pkg)
				pkg.global_transform = pkg.get_meta("from")
			bag_rig.handover()
		elif is_instance_valid(held_package):
			pkg = held_package
			held_package = null
			_held_for = ""
		var result := session.deliver(address, 1.0)
		if session.order.get("state") == "COMPLETED":
			drop_zone.customer_leaves(pkg)
			delivered("meet")
		else:
			if pkg: pkg.queue_free()
			notify(result)

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
		delivered("door")
	else:
		notify(result)

func delivered(method: String) -> void:
	sound("delivery_success")
	if method == "meet": sound("customer_thanks")
	var tw := create_tween()
	tw.tween_interval(0.5)
	tw.tween_callback(sound.bind("coins"))
	session.receipt += "\n" + ("Photo proof sent to the customer." if method == "door" else "Handed over in person.")
	save_session()
	show_menu("receipt")

func sound(name: String) -> void:
	if audio and ResourceLoader.exists(CityAudio.SFX % name): audio.play_ui(name, -6.0)

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
		receipt_panel = PanelContainer.new()
		receipt_panel.add_theme_stylebox_override("panel", style_panel(Color(0.97, 0.96, 0.92, 0.97)))
		receipt_panel.position = Vector2(860, 250)
		receipt_label = Label.new()
		receipt_label.add_theme_font_size_override("font_size", 15)
		receipt_label.add_theme_color_override("font_color", Color("1d1b18"))
		var mono := SystemFont.new()
		mono.font_names = PackedStringArray(["Consolas", "Courier New", "monospace"])
		receipt_label.add_theme_font_override("font", mono)
		receipt_panel.add_child(receipt_label)
		hud.add_child(receipt_panel)
	var showing: bool = not target.is_empty() and target.id == "package"
	receipt_panel.visible = showing
	if showing:
		var info: Dictionary = target.node.get_meta("package")
		var name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(str(info.restaurant)))]
		var mine: bool = info.customer == session.order.get("customer", "") and info.ticket == session.order.get("ticket", "")
		receipt_label.text = OrderDetails.receipt_text(info, name, DeliverySession.ADDRESSES[int(info.get("address", 0))], session.calendar_minutes)
		if mine and session.order.get("state") == "ACCEPTED": receipt_label.text += "\n\n>> YOUR CUSTOMER <<"

## The package in your hands (bottom-right of the view) while it is out of the bag.
func update_held_package() -> void:
	var want: bool = session.holding_package() and not player.mounted
	var id: String = str(session.order.get("id", ""))
	if want and (held_package == null or _held_for != id):
		if held_package: held_package.queue_free()
		var info := {"customer": session.order.customer, "ticket": session.order.ticket, "kind": session.order.kind, "items": session.order.items, "restaurant": session.restaurant_id()}
		var body := shelves.make_package(info)
		body.collision_layer = 0
		held_package = body
		player.camera.add_child(held_package)
		_held_for = id
		if _pickup_from is Transform3D:
			held_package.global_transform = _pickup_from
			to_hands(held_package)
		else:
			held_package.transform = HOLD_POSE
	_pickup_from = null
	if held_package: held_package.visible = want

## Where a held package sits: two hands, low and to the right of the view.
var HOLD_POSE := Transform3D(Basis.from_euler(Vector3(0.15, -0.35, 0)), Vector3(0.22, -0.42, -0.55))

## Animate a package (child of the camera) into the hands.
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
	var forward := -player.global_basis.z
	forward.y = 0.0
	forward = forward.normalized()
	var from := player.global_position + forward * 0.8 + Vector3(0, 1.4, 0)
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -3.0, 0))
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
		notify("There's no flat spot to put it down here.")
		return
	var start: Variant = held_package.global_transform if is_instance_valid(held_package) else null
	var result := session.drop_package(hit.position, player.rotation.y)
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
			player.camera.add_child(node)
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
	street_label.text = "◆  " + StreetNames.describe(player.position).to_upper()
	objective.text = ("Online · requests arrive automatically" if session.online else "Offline · open your phone to go online")
	if session.online and session.demand().begins_with("Kitchen closed"):
		objective.text = "Kitchen closed · opens 08:00"
	route_marker.visible = false
	if state == "OFFERED":
		objective.text = "New offer  /  [%s] Open phone" % binding("phone")
	elif state == "ACCEPTED":
		objective.text = "01  /  Collect at " + session.restaurant_name()
		route_marker.position = session.pickup_position() + Vector3(0, 2, 0)
	elif state == "DROPPED":
		objective.text = "02  /  Pick up %s's order" % session.order.customer
		route_marker.visible = player.position.distance_to(session.dropped_position()) > 4.0
		route_marker.position = session.dropped_position() + Vector3(0, 1.2, 0)
		route_marker.text = "YOUR PACKAGE\n%d m" % int(player.position.distance_to(session.dropped_position()))
	elif state in ["CARRYING", "IN_HAND"]:
		objective.text = "02  /  " + DeliverySession.ADDRESSES[int(session.order.address)]
		route_marker.position = world.doors[int(session.order.address)] + Vector3(0, 2.5, 0)
		route_marker.text = "DELIVER\n%d m" % int(player.position.distance_to(world.doors[int(session.order.address)]))
	if bag_label == null:
		bag_label = make_label("", 14, Color("f4e7c4"))
		bag_label.position = Vector2(36, 380)
		hud.add_child(bag_label)
	var bag_state := ""
	if session.has_bag():
		bag_state = "BACKPACK  ·  " + ("%s's %s in the %s" % [session.order.customer, str(OrderDetails.KIND_NAMES.get(session.order.get("kind", "bag"), "order")).to_lower(), str(OrderDetails.SLOT_NAMES.get(session.order.get("slot", ""), "bag")).to_lower()] if state == "CARRYING" else "empty") + "   [%s] open" % binding("bag")
	if state == "IN_HAND":
		bag_state = "HOLDING %s's order  ·  [%s] %s  ·  [%s] put down" % [session.order.customer, binding("bag"), "pack it in your backpack" if session.has_bag() else "no bag: walk it over", binding("drop")]
	elif state == "DROPPED":
		bag_state = "%s's order is on the ground  ·  [%s] pick it up" % [session.order.customer, binding("interact")]
	bag_label.text = bag_state
	stats.text = "Day %d  ·  %02d:%02d  |  %s  |  Energy %d%%" % [int(session.calendar_minutes / 1440) + 1, int(session.hour()), int(session.calendar_minutes) % 60, DeliverySession.money(session.wallet), int(session.energy)]
	calendar_label.text = "DAY %02d   ·   %s" % [int(session.calendar_minutes / 1440) + 1, session.date_text()]
	if world.weather != null: calendar_label.text += "   ·   " + world.weather.describe().to_upper()
	needs_label.text = "FOOD %d%%   WATER %d%%   WC %d%%   ·   %s" % [int(session.hunger), int(session.hydration), int(session.bladder), "Night" if session.hour() < 6 or session.hour() >= 20 else "Daylight"]
	var water := int(session.supplies.get("water_bottle", 0))
	var snack := int(session.supplies.get("energy_bar", 0))
	if water + snack > 0: needs_label.text += "   ·   [%s] water ×%d   [%s] bar ×%d" % [binding("use_water"), water, binding("use_snack"), snack]
	if player.mounted:
		prompt.text = "Space: brake   ·   E: dismount   ·   %d km/h" % int(absf(player.riding_speed) * 3.6)
	elif player.has_vehicle() and player.position.distance_to(player.bicycle.position) < 2:
		prompt.text = "E: mount " + session.active_vehicle.replace("_", " ")
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
		var destination := world.doors[int(session.order.address)]
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
		route_marker.text = "%s
%d m" % [CityNavigation.target.name, int(player.position.distance_to(goal))]
	else:
		navigation_label.text = "Online · awaiting requests" if session.online else "Offline · open phone to work"

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
	# Take your named package off the pickup shelf (same path as pressing E on it).
	await get_tree().process_frame
	await get_tree().process_frame
	var mine: Node3D = null
	for p: Node3D in shelves.packages.get(session.restaurant_id(), []):
		if is_instance_valid(p) and p.get_meta("package").get("customer") == session.order.customer: mine = p
	assert(mine != null, "Your package waits on the pickup shelf")
	session.take_package(mine.get_meta("package"), 1.0)
	shelves.take(mine)
	assert(session.order.state == "IN_HAND")
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
	var face := drop_zone.customer.global_position + Vector3(0, 1.1, 0) - player.camera.global_position
	player.rotation.y = atan2(-face.x, -face.z)
	player.camera.rotation = Vector3(atan2(face.y, Vector2(face.x, face.z).length()), 0, 0)
	await get_tree().physics_frame
	await get_tree().physics_frame
	assert(player.target().get("id") == "customer", "The customer can be handed the order")
	interact()
	assert(session.order.state == "COMPLETED" and session.wallet > 0)
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
	print("SCENE SMOKE PASS: real raycast pickup, named package, knock + customer handover, receipt; test does not write player save")
	get_tree().quit()
