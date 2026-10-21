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
var _held_for := ""
var city_map: Control
var city_map_layer: CanvasLayer
var _arrival_note := ""
var gameplay_ui: Control
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
	build_hud()
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
	shelves = PickupShelves.new()
	shelves.name = "PickupShelves"
	world.add_child(shelves)
	shelves.setup(world, session)
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
	var actions := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D, "sprint": KEY_SHIFT, "jump": KEY_SPACE, "interact": KEY_E, "phone": KEY_TAB, "map": KEY_M, "pause_game": KEY_ESCAPE, "bell": KEY_Q, "bag": KEY_F}
	for action in actions:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = actions[action]
			InputMap.action_add_event(action, key)

func binding(action: String) -> String:
	var event := InputMap.action_get_events(action)[0] as InputEventKey
	return OS.get_keycode_string(event.physical_keycode if event.physical_keycode != 0 else event.keycode)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause_game"):
		if mode in ["start", "confirm_new"]:
			return
		if mode != "":
			close_menu()
		else:
			show_menu("pause")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("phone") or event.is_action_pressed("map"):
		if mode in ["start", "confirm_new"]:
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
	elif mode == "bag" and event.is_action_pressed("interact"):
		# E inside the bag: put the held package in the compartment it fits.
		if session.holding_package():
			bag_click(OrderDetails.best_slot(str(session.order.get("kind", "bag"))))
		get_viewport().set_input_as_handled()
	elif mode == "" and event.is_action_pressed("interact"):
		interact()
		get_viewport().set_input_as_handled()

func _process(delta: float) -> void:
	if get_tree().paused:
		return
	session.tick(delta)
	session.offer_position = player.position
	world.set_time(session.hour())
	if session.dispatch(pickup_route_distance()):
		notify("CourierNow · New delivery request\nPress Tab to review your offer")
		save_session()
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
			title = "Deliver  /  " + DeliverySession.ADDRESSES[int(title.trim_prefix("door_"))]
		elif title == "shop":
			title = "Browse delivery equipment"
		elif title == "home":
			title = "Rest and save"
		prompt.text = "[%s]  %s" % [binding("interact"), title]
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
	if target.is_empty():
		if player.position.distance_to(player.bicycle.position) < 2.5:
			notify(player.toggle_bicycle())
			save_session()
		return
	var result := ""
	if target.id == "package":
		var info: Dictionary = target.node.get_meta("package")
		result = session.take_package(info, target.distance)
		if session.holding_package():
			shelves.take(target.node)
			save_session()
		notify(result)
		return
	if str(target.id).begins_with("cedar_door_"):
		world.cedar_house.toggle_door(int(str(target.id).trim_prefix("cedar_door_")))
		return
	if str(target.id).begins_with("store_"):
		current_shop = str(target.id).trim_prefix("store_")
		show_menu("shop")
		return
	if target.id == "wc":
		result = session.consume("wc")
	elif target.id == "water":
		session.hydration = 100
		session.bladder = minf(100, session.bladder + 8)
		result = "Drinking water replenished."
	elif (target.id == "pickup" or str(target.id).begins_with("pickup_")) and session.order.get("state") not in ["ACCEPTED", "IN_HAND", "CARRYING"]:
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
	elif str(target.id).begins_with("door_"):
		result = session.deliver(int(str(target.id).trim_prefix("door_")), target.distance)
		if session.order.get("state") == "COMPLETED":
			show_menu("receipt")
	elif target.id == "shop":
		current_shop = "equipment"
		show_menu("shop")
		return
	elif target.id == "home":
		if session.order.get("state") in ["ACCEPTED", "IN_HAND", "CARRYING"]:
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
	var controls := make_label("%s  Move     %s  Sprint     %s  Interact     %s  Phone     %s  Map     %s  Pause" % ["WASD", binding("sprint"), binding("interact"), binding("phone"), binding("map"), binding("pause_game")], 16)
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
	if which == "map":
		open_city_map()
		return
	if city_map != null: city_map.hide()
	mode = which
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modal.show()
	var title_screen := which in ["start", "confirm_new"]
	gameplay_ui.visible = not title_screen
	menu_shade.visible = true
	var is_phone := which in ["phone", "map"]
	modal.set("phone_mode", is_phone)
	modal.set("session", session)
	if is_phone: menu_shade.visible = false
	modal_body.add_theme_constant_override("separation",8 if is_phone else 12)
	if title_screen:
		menu_camera.make_current()
	else:
		player.camera.make_current()
	modal.custom_minimum_size = Vector2.ZERO
	modal.position = Vector2(70, 58) if title_screen else Vector2(830, 28)
	modal.size = Vector2(480, 600) if title_screen else Vector2(420, 640)
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
	add_text("DELIVERY SIMULATOR   /   ATATÜRK AVENUE" if title_screen else "%02d:%02d       ●       COURIERNOW" % [int(session.hour()), int(session.calendar_minutes) % 60], 14, Color("9bceb7"))
	match which:
		"start":
			add_text("DELIVERY\nSIMULATOR", 48)
			add_text("Every street is a new beginning.", 21, Color("c3d0ca"))
			add_text("Build your routine. Learn your neighborhood.\nEarn a better tomorrow.", 17)
			if FileAccess.file_exists(DeliverySave.PATH) or FileAccess.file_exists(DeliverySave.PATH + ".bak"):
				button("Continue saved shift", load_session)
			button("New game", func():
				if FileAccess.file_exists(DeliverySave.PATH): show_menu("confirm_new")
				else: new_session())
			button("Quit", func(): get_tree().quit())
			add_text("EARLY DEVELOPMENT   ·   0.2\nKeyboard & mouse  /  Windows", 13, Color("8eaaa0"))
		"confirm_new":
			add_text("Start over?", 30)
			add_text("Starting a new shift replaces the current save. Your previous valid save remains in the backup until the next save.")
			button("Start new shift", new_session)
			button("Back", func(): show_menu("start"))
		"phone":
			add_text("CourierNow", 34)
			add_text("YOUR CITY. YOUR NEXT DELIVERY.", 12, Color("8fb4a7"))
			add_text(("ONLINE  /  " if session.online else "OFFLINE  /  ") + session.demand(), 16, Color("9bceb7"))
			var state: String = session.order.get("state", "")
			if state == "OFFERED":
				add_text("NEW OFFER  /  " + session.restaurant_name(), 21, Color("9bceb7"))
				add_text("Customer: %s  ·  Order %s\n%s  ·  %s" % [session.order.get("customer", "?"), session.order.get("ticket", "?"), order_items_text(), OrderDetails.KIND_NAMES.get(session.order.get("kind", "bag"), "")], 17, Color("f4e7c4"))
				add_text(DeliverySession.money(session.order.quote) + " guaranteed", 32)
				add_text("Up to $3.00 tip  |  One bag\nPickup %dm  ·  Delivery %dm\nEstimated %d min  ·  Ready now\n%s\nUse the marked collection point or destination entrance.\n%ds to respond · paused in phone" % [int(session.order.pickup_distance), int(session.order.distance), maxi(1, int((session.order.pickup_distance + session.order.distance) / 3.5 / 60.0) + 1), DeliverySession.ADDRESSES[int(session.order.address)], maxi(0, int(session.order.expires - session.clock))], 17)
				button("Accept delivery", func(): session.accept(); save_session(); close_menu(); notify("Collect at " + session.restaurant_name() + ". Follow the minimap."))
				button("Reject without penalty", func(): session.reject(); save_session(); show_menu("phone"))
			elif state in ["ACCEPTED", "IN_HAND", "CARRYING"]:
				add_text("ORDER " + session.order.id.to_upper(), 20, Color("9bceb7"))
				add_text("Collect at " + session.restaurant_name() if state == "ACCEPTED" else "Deliver to " + DeliverySession.ADDRESSES[int(session.order.address)], 25)
				add_text("Customer: %s  ·  Order %s\n%s" % [session.order.get("customer", "?"), session.order.get("ticket", "?"), order_items_text()], 18, Color("f4e7c4"))
				add_text("Guaranteed pay: " + DeliverySession.money(session.order.quote) + "\nPackage: " + str({"ACCEPTED": "waiting on the pickup shelf", "IN_HAND": "in your hands · press F to pack it", "CARRYING": "in your bag · " + str(OrderDetails.SLOT_NAMES.get(session.order.get("slot", ""), ""))}[state]))
			else:
				add_text("Looking for requests nearby" if session.online else "You're offline", 24)
				add_text("Requests arrive automatically while you explore. Lunch and dinner are busier. Cedar Kitchen, Market Noodles and Harbor Pizza serve 08:00–22:00.", 18)
				add_text("Time pauses while the phone is open. Close it to continue your shift.", 16, Color("9bceb7"))
			button("Go offline" if session.online else "Go online", func(): session.toggle_online(); save_session(); show_menu("phone"))
			button("Local navigation", func(): show_menu("map"))
			add_text("Wallet  " + DeliverySession.money(session.wallet) + "  /  %d deliveries" % session.completed, 19)
			button("Back to street", close_menu)
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
		"pause":
			add_text("Take a breather.", 32)
			add_text("The shift and all order timers are paused.")
			button("Resume", close_menu)
			button("Save shift", func(): if save_session(): notify("Shift saved."); close_menu())
			button("Load saved shift", load_session)
			button("Save and quit", func(): if save_session(): get_tree().quit())
			button("Quit without saving", func(): get_tree().quit())
	for child in modal_body.get_children():
		if child is Button:
			child.grab_focus()
			break

## Full-screen city map with clickable places and road navigation (ui/city_map.gd).
func open_city_map() -> void:
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
		held_package.position = Vector3(0.22, -0.42, -0.55)
		held_package.rotation = Vector3(0.15, -0.35, 0)
		_held_for = id
	if held_package: held_package.visible = want

## Bag compartment clicked: pack the held package there, or take the packed one out.
func bag_click(slot: String) -> void:
	var result := ""
	if session.holding_package():
		result = session.stow(slot)
	elif session.order.get("state") == "CARRYING" and session.order.get("slot", "") == slot:
		result = session.unstow()
	else:
		result = "Empty compartment." if session.bag_upgrade else "You don't own a delivery bag yet."
	notify(result)
	save_session()
	if mode == "bag": show_menu("bag")

## F: the insulated bag. Top: one big compartment (food bags). Middle: two halves (drinks and
## desserts stay level). Bottom: a flat full-width drawer for pizza boxes.
func build_bag_menu() -> void:
	add_text("INSULATED DELIVERY BAG", 22, Color("9bceb7"))
	if not session.bag_upgrade:
		add_text("You don't own a delivery bag yet.\nTrail & Tool (equipment store) sells an insulated courier bag for $35. Without it you can only walk an order to the customer by hand.", 18)
		if session.holding_package(): add_text("Holding: %s's order" % session.order.customer, 18, Color("f4e7c4"))
		button("Close (%s)" % binding("bag"), close_menu)
		return
	var state: String = session.order.get("state", "")
	var kind: String = session.order.get("kind", "bag")
	var holding := session.holding_package()
	if holding:
		add_text("Holding %s's %s\nClick its compartment or press %s" % [session.order.customer, str(OrderDetails.KIND_NAMES[kind]).to_lower(), binding("interact")], 16, Color("f4e7c4"))
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
	player.session = session
	player.replace_vehicle(Vector3(-8, 0, 19))
	minimap.session = session
	if shelves: shelves.session = session
	session.changed.connect(update_hud)
	player.position = Vector3(-8, 0.2, 23)
	player.rotation = Vector3.ZERO
	player.camera.rotation = Vector3.ZERO
	save_session()
	close_menu()
	notify("You're online. Your first offer will arrive shortly.\nTab: phone   ·   M: map")

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
		add_text(saves.error, 18, Color("f0c28b"))
		return
	session.restore(data)
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
	elif state in ["CARRYING", "IN_HAND"]:
		objective.text = "02  /  " + DeliverySession.ADDRESSES[int(session.order.address)]
		route_marker.position = world.doors[int(session.order.address)] + Vector3(0, 2.5, 0)
		route_marker.text = "DELIVER\n%d m" % int(player.position.distance_to(world.doors[int(session.order.address)]))
	stats.text = "Day %d  ·  %02d:%02d  |  %s  |  Energy %d%%" % [int(session.calendar_minutes / 1440) + 1, int(session.hour()), int(session.calendar_minutes) % 60, DeliverySession.money(session.wallet), int(session.energy)]
	calendar_label.text = "DAY %02d   ·   %s" % [int(session.calendar_minutes / 1440) + 1, session.date_text()]
	if world.weather != null: calendar_label.text += "   ·   " + world.weather.describe().to_upper()
	needs_label.text = "FOOD %d%%   WATER %d%%   WC %d%%   ·   %s" % [int(session.hunger), int(session.hydration), int(session.bladder), "Night" if session.hour() < 6 or session.hour() >= 20 else "Daylight"]
	if player.mounted:
		prompt.text = "Space: brake   ·   E: dismount   ·   %d km/h" % int(absf(player.riding_speed) * 3.6)
	elif player.position.distance_to(player.bicycle.position) < 2:
		prompt.text = "E: mount " + session.active_vehicle.replace("_", " ")
	if navigation_label == null:
		return
	if state == "OFFERED":
		navigation_label.text = "New request · %s to review" % binding("phone")
	elif state == "ACCEPTED":
		var pickup_distance := CityCatalog.distance(minimap.route_points())
		navigation_label.text = "%d m · %s" % [int(pickup_distance), session.restaurant_name()]
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
	assert(hit.get("id") == "pickup", "Pickup counter must be physically interactable")
	interact()
	assert(session.order.state == "CARRYING")
	var destination := world.doors[int(session.order.address)]
	player.position = destination + Vector3(0, -0.92, 1.6)
	player.camera.rotation.x = -0.2
	await get_tree().physics_frame
	await get_tree().physics_frame
	hit = player.target()
	assert(hit.get("id") == "door_0", "Correct door must be physically interactable")
	interact()
	assert(session.order.state == "COMPLETED" and session.wallet > 0)
	close_menu()
	player.position = player.bicycle.position + Vector3(1, 0.1, 0)
	assert(player.toggle_bicycle().begins_with("Mounted"))
	player.riding_speed = 3
	assert(player.toggle_bicycle().begins_with("Brake"))
	player.riding_speed = 0
	await get_tree().physics_frame
	assert(player.toggle_bicycle() == "Bicycle parked.")
	print("SCENE SMOKE PASS: real raycast pickup, correct door, receipt; test does not write player save")
	get_tree().quit()
