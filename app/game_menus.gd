class_name GameMenus
extends Node
## Everything that pauses the street: the title / pause menu (MainMenu), the phone (PhoneDevice,
## CourierNow), store computers (StoreTerminal), the full-screen city map, and the modal pages in
## the HUD's right column (shop, food counter, receipt, backpack). GameApp.mode names what is open
## ("" = playing).

var game: GameApp
var main_menu: MainMenu
var menu_camera: Camera3D
var terminal: StoreTerminal
var phone: PhoneDevice
var city_map: Control
var city_map_layer: CanvasLayer
var current_shop := "equipment"

func setup(app: GameApp) -> void:
	game = app
	var menu_layer := CanvasLayer.new()
	menu_layer.layer = 10
	game.add_child(menu_layer)
	main_menu = MainMenu.new()
	main_menu.name = "MainMenu"
	menu_layer.add_child(main_menu)
	main_menu.chosen.connect(on_main_menu)
	menu_camera = Camera3D.new()
	game.add_child(menu_camera)
	menu_camera.position = Vector3(36, 16, 44)
	menu_camera.look_at(CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(0, 2, 0))

## Store computers and the phone (after the player and the HUD exist).
func setup_devices() -> void:
	var terminal_layer := CanvasLayer.new()
	terminal_layer.layer = 11
	game.add_child(terminal_layer)
	terminal = StoreTerminal.new()
	terminal.name = "StoreTerminal"
	terminal_layer.add_child(terminal)
	terminal.closed.connect(func() -> void: if game.mode == "terminal": close())
	terminal.purchased.connect(on_store_purchase)
	terminal.equip.connect(equip_vehicle)
	phone = PhoneDevice.new()
	phone.name = "Phone"
	game.player.camera.add_child(phone)
	phone.setup(game)
	phone.os.action.connect(on_phone_action)

## Pause the street and free the mouse for a menu called `which`.
func _enter(which: String) -> void:
	game.mode = which
	game.get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func show(which: String) -> void:
	if which in ["start", "pause", "confirm_new"]:
		open_main_menu(which != "pause")
		return
	if which == "phone":
		open_phone()
		return
	if which == "map":
		open_city_map()
		return
	var hud := game.hud
	if city_map != null: city_map.hide()
	_enter(which)
	hud.modal.show()
	hud.gameplay_ui.visible = true
	hud.menu_shade.visible = true
	var is_phone := which in ["phone", "map"]
	hud.modal.set("phone_mode", is_phone)
	hud.modal.set("session", game.session)
	if is_phone or which == "bag": hud.menu_shade.visible = false
	hud.modal_body.add_theme_constant_override("separation", 8 if is_phone else 12)
	game.player.camera.make_current()
	_place_modal(is_phone)
	for child in hud.modal_body.get_children():
		hud.modal_body.remove_child(child)
		child.queue_free()
	add_text("%02d:%02d       ●       COURIERNOW" % [int(game.session.hour()), int(game.session.calendar_minutes) % 60], 14, Color("9bceb7"))
	match which:
		"map": page_map()
		"bag": page_bag()
		"shop": page_shop()
		"food": page_food()
		"receipt": page_receipt()
	for child in hud.modal_body.get_children():
		if child is Button:
			child.grab_focus()
			break

## The modal: the right column under the status panel (HudStyle), or a phone frame.
func _place_modal(is_phone: bool) -> void:
	var hud := game.hud
	var modal := hud.modal
	modal.custom_minimum_size = Vector2.ZERO
	var top_y := hud.status_panel.position.y + hud.status_panel.size.y + HudStyle.GAP
	modal.size = Vector2(420, hud.gameplay_ui.size.y - HudStyle.MARGIN - top_y)
	modal.position = Vector2(hud.gameplay_ui.size.x - HudStyle.MARGIN - 420, top_y)
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

func close() -> void:
	var hud := game.hud
	var player := game.player
	if game.bag_rig and game.bag_rig.out: game.bag_rig.put_on()
	if phone and phone.out:
		phone.lower(player.camera)
		game.sound("phone_lower")
	if terminal and terminal.visible: terminal.hide()
	if game.mode == "bag": game.flow.end_bag_drag()
	if main_menu: main_menu.close()
	game.mode = ""
	if city_map != null: city_map.hide()
	hud.modal.hide()
	hud.menu_shade.hide()
	hud.gameplay_ui.show()
	player.camera.make_current()
	game.get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

# --- Page building blocks ---------------------------------------------------------------------

func add_text(text: String, size: int = 20, color: Color = Color("e6efeb")) -> void:
	size = roundi(size * (0.7 if game.mode in ["phone", "map"] else 0.8))     # HudStyle type scale
	var label := HudStyle.shadow_label(text, size, color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = 0
	game.hud.modal_body.add_child(label)

func button(text: String, callback: Callable) -> void:
	var control := Button.new()
	control.text = text
	control.custom_minimum_size.y = 36
	control.add_theme_font_size_override("font_size", 13 if game.mode in ["phone", "map"] else 15)
	control.add_theme_font_override("font", HudStyle.font(HudStyle.Face.TEXT, HudStyle.SEMIBOLD))
	for state_name: String in ["normal", "hover", "focus"]:
		var style := HudStyle.card(Color("23424a") if state_name == "normal" else Color("376357"))
		style.content_margin_top = 8
		style.content_margin_bottom = 8
		control.add_theme_stylebox_override(state_name, style)
	control.pressed.connect(callback)
	game.hud.modal_body.add_child(control)

# --- Pages ------------------------------------------------------------------------------------

func page_map() -> void:
	add_text("COURIERNOW  /  NAVIGATION", 15, Color("9bceb7"))
	add_text("Atatürk Avenue", 32)
	var large_map: Control = preload("res://ui/minimap.gd").new()
	large_map.player = game.player
	large_map.session = game.session
	large_map.world = game.world
	large_map.custom_minimum_size = Vector2(272, 272)
	large_map.set("range_metres", 120.0)
	game.hud.modal_body.add_child(large_map)
	add_text("White arrow: you   ·   Mint: route\nGold: pickup   ·   North stays up", 16)
	button("Back to street", close)

func page_shop() -> void:
	var session := game.session
	add_text(ShopCatalog.TITLES.get(current_shop, "TRAIL & TOOL"), 29)
	add_text("Wallet  " + DeliverySession.money(session.wallet), 20, Color("9bceb7"))
	for id: String in ShopCatalog.ITEMS:
		var item: Dictionary = ShopCatalog.ITEMS[id]
		if item.shop != current_shop: continue
		add_text(item.name + "  ·  " + DeliverySession.money(item.price), 22)
		add_text(item.description, 16, Color("b8cac3"))
		if session.owns(id):
			if ShopCatalog.is_vehicle(id): button("Use this vehicle", equip_vehicle.bind(id))
			else: add_text("OWNED / EQUIPPED", 14, Color("9bceb7"))
		else: button("Buy " + item.name, buy_item.bind(id))
	button("Back to street", close)

func page_food() -> void:
	var session := game.session
	add_text("Take care of yourself", 29)
	add_text("Food %d%%   Water %d%%\nWallet %s" % [int(session.hunger), int(session.hydration), DeliverySession.money(session.wallet)], 19)
	button("Sandwich  ·  $6.50", consume_item.bind("meal"))
	button("Water  ·  $1.50", consume_item.bind("water"))
	add_text("Public drinking water and washrooms are beside the equipment district.", 16)
	button("Back to street", close)

func page_receipt() -> void:
	add_text(game.session.receipt, 25)
	add_text("Wallet  " + DeliverySession.money(game.session.wallet), 24, Color("9bceb7"))
	add_text("Your next request will arrive automatically while online.", 18)
	button("Back to street", close)

## F: the insulated bag. Top: one big compartment (food bags). Middle: two halves (drinks and
## desserts stay level). Bottom: a flat full-width drawer for pizza boxes. The 3D bag comes off
## the back and opens (BagRig); the order packed in it shows.
func page_bag() -> void:
	var session := game.session
	add_text("INSULATED DELIVERY BAG", 22, Color("9bceb7"))
	if not session.has_bag():
		add_text("You don't own a delivery bag yet.\nTrail & Tool (equipment store) sells an insulated courier bag for $35. Without it you can only walk an order to the customer by hand.", 18)
		if session.holding_package(): add_text("Holding: %s's order" % session.order.customer, 18, Color("f4e7c4"))
		button("Close (%s)" % game.binding("bag"), close)
		return
	var state: String = session.order.get("state", "")
	var kind: String = session.order.get("kind", "bag")
	var holding := session.holding_package()
	if holding:
		add_text("Holding %s's %s\nMove it over a compartment in the bag and click to drop it in, or press %s" % [session.order.customer, str(OrderDetails.KIND_NAMES[kind]).to_lower(), game.binding("interact")], 16, Color("f4e7c4"))
	else:
		add_text("Click a packed order to take it out.", 16, Color("f4e7c4"))
	var grid := VBoxContainer.new()
	grid.add_theme_constant_override("separation", 6)
	game.hud.modal_body.add_child(grid)
	grid.add_child(bag_slot("top", Vector2(0, 150), state, kind, holding))
	var middle := HBoxContainer.new()
	middle.add_theme_constant_override("separation", 6)
	grid.add_child(middle)
	middle.add_child(bag_slot("left", Vector2(0, 92), state, kind, holding))
	middle.add_child(bag_slot("right", Vector2(0, 92), state, kind, holding))
	grid.add_child(bag_slot("bottom", Vector2(0, 62), state, kind, holding))
	button("Close (%s)" % game.binding("bag"), close)
	game.bag_rig.take_off()
	game.sound("bag_zip")
	if state == "CARRYING" and not is_instance_valid(game.bag_rig.contents):
		game.bag_rig.show_contents(game.flow.package_model(), str(session.order.get("slot", "top")))

func bag_slot(slot: String, min_size: Vector2, state: String, kind: String, holding: bool) -> Button:
	var session := game.session
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
	for st: String in ["normal", "hover", "pressed", "focus"]: b.add_theme_stylebox_override(st, box)
	b.add_theme_font_size_override("font_size", 15)
	b.pressed.connect(game.flow.bag_click.bind(slot))
	return b

# --- Shop actions -----------------------------------------------------------------------------

func buy_item(id: String) -> void:
	var result := game.session.buy(id)
	game.player.refresh_equipment()
	game.save_session()
	show("shop")
	game.notify(result)

func consume_item(id: String) -> void:
	var result := game.session.consume(id)
	game.save_session()
	show("food")
	game.notify(result)

## The vehicle is rolled out in front of the store you are at.
func park_new_vehicle() -> void:
	var shop: Vector3 = ShopCatalog.LOCATIONS[current_shop]
	game.player.replace_vehicle(Vector3(signf(shop.x) * 79, 0.06, shop.z + 12))

func equip_vehicle(id: String) -> void:
	var session := game.session
	if not session.owns(id) or not ShopCatalog.is_vehicle(id): return
	if game.player.mounted:
		game.notify("Park before changing vehicles.")
		return
	session.active_vehicle = id
	park_new_vehicle()
	game.save_session()
	close()
	game.notify("Your vehicle is parked in the shop forecourt. Walk up and press E.")

# --- Phone, store computers, map, title menu --------------------------------------------------

## Tab: the phone comes out of your pocket (PhoneDevice); the CourierNow app lives on it.
func open_phone() -> void:
	var session := game.session
	if not session.has_phone():
		game.notify("You don't have a phone yet. Trail & Tool sells a budget smartphone for $25." if not session.bought("budget_phone") else "Your phone is waiting on the pickup shelf at Trail & Tool.")
		return
	if city_map != null: city_map.hide()
	_enter("phone")
	game.hud.modal.hide()
	game.hud.menu_shade.hide()
	game.hud.gameplay_ui.visible = true
	game.player.camera.make_current()
	phone.raise(game.player.camera)
	game.hud.clear_notice()             # the phone shows its own toasts; keep the screen clear
	game.sound("phone_raise")
	game.tutorial.event("phone")

func on_phone_action(name: String, arg: String) -> void:
	var session := game.session
	var tutorial := game.tutorial
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
			game.save_session()
		"accept":
			if session.accept():
				phone.os.flash("Accepted · go to " + session.restaurant_name())
				game.sound("ui_accept")
				game.save_session()
		"reject":
			if tutorial.gate("reject") == "" and session.reject():
				game.save_session()
		"maps":
			close()
			show("map")

## E on a store computer (or its counter): the online shop of that store.
func open_terminal(store: String) -> void:
	if not ShopCatalog.LOCATIONS.has(store): return
	_enter("terminal")
	game.hud.modal.hide()
	game.hud.menu_shade.hide()
	game.hud.gameplay_ui.hide()
	current_shop = store
	terminal.open(store, game.session)
	game.sound("kiosk_click")

func on_store_purchase(message: String) -> void:
	var session := game.session
	for id: String in session.bought_vehicles:
		# A new vehicle is rolled out in front of the store and becomes the one you use.
		session.active_vehicle = id
		park_new_vehicle()
	game.store_terminals.refresh()
	game.save_session()
	game.notify(message)

## Full-screen city map with clickable places and road navigation (ui/city_map.gd).
func open_city_map() -> void:
	game.tutorial.event("map")
	_enter("map")
	game.hud.modal.hide()
	game.hud.menu_shade.hide()
	game.hud.gameplay_ui.hide()
	if city_map == null:
		city_map_layer = CanvasLayer.new()
		city_map_layer.layer = 20
		city_map_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		game.add_child(city_map_layer)
		city_map = preload("res://ui/city_map.gd").new()
		city_map_layer.add_child(city_map)
		city_map.closed.connect(close)
		city_map.destination_chosen.connect(func(place: Dictionary) -> void:
			close()
			game.notify("Navigating to %s · follow the mint route on the minimap." % place.name))
	city_map.open(game.player, game.world)

## Title screen (new game, continue, settings, exit) or the Esc pause menu (ui/main_menu.gd).
func open_main_menu(title: bool) -> void:
	if city_map != null: city_map.hide()
	if game.bag_rig and game.bag_rig.out: game.bag_rig.put_on()
	_enter("start" if title else "pause")
	game.hud.modal.hide()
	game.hud.menu_shade.hide()
	game.hud.gameplay_ui.hide()
	if title: menu_camera.make_current()
	else: game.player.camera.make_current()
	main_menu.has_save = GamePersistence.has_save()
	main_menu.save_summary = GamePersistence.save_summary() if main_menu.has_save else ""
	main_menu.open(not title)

func on_main_menu(action: String) -> void:
	match action:
		"continue": game.persistence.load_session()
		"resume": close()
		"save": main_menu.flash("Shift saved." if game.save_session() else game.saves.error)
		"new_game": game.persistence.new_session()
		"exit_to_menu":
			game.save_session()
			show("start")
		"quit":
			if game.mode == "pause": game.save_session()
			game.get_tree().quit()
		"settings_changed": GameSettings.apply(game.player)
