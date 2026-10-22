class_name StoreTerminal
extends Control
## The store computer: a monitor-framed online shop for one store. Product cards (rendered
## thumbnail, name, price, feature bullets, quantity − / +, Add to cart), a cart with per-line
## − / + / remove, the total, the wallet after purchase and a Purchase button. Paid orders wait
## on the store's pickup shelf (vehicles roll out in front of the store).

signal purchased(message: String)
signal closed
signal equip(id: String)        ## "Use this vehicle" on an owned vehicle

const ACCENT := Color("1f8a63")
const INK := Color("1d2427")
const MUTED := Color("5f6b70")
const PAPER := Color("f4f6f5")

var session: DeliverySession
var store := "equipment"
var cart: Dictionary = {}          ## id -> qty
var _pick: Dictionary = {}         ## id -> qty chosen on the card
var studio: IconStudio
var screen: PanelContainer
var grid: GridContainer
var cart_box: VBoxContainer
var total_label: Label
var after_label: Label
var buy_button: Button
var message: Label
var wallet_chip: Label
var _font: SystemFont

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Segoe UI", "Arial", "sans-serif"])
	studio = IconStudio.new()
	add_child(studio)
	hide()

## Open the shop of `store_id` (equipment, bikes, cars, scooters).
func open(store_id: String, s: DeliverySession) -> void:
	store = store_id
	session = s
	cart.clear()
	_pick.clear()
	build()
	show()

func close() -> void:
	hide()
	closed.emit()

func products() -> Array[String]:
	var out: Array[String] = []
	for id: String in ShopCatalog.ITEMS:
		if ShopCatalog.ITEMS[id].shop == store: out.append(id)
	return out

# --- layout ------------------------------------------------------------------------------

func build() -> void:
	for c in get_children():
		if c != studio: c.queue_free()
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	# Monitor: dark bezel, chin with a logo, the screen inside.
	var bezel := PanelContainer.new()
	bezel.position = Vector2(54, 22)
	bezel.size = Vector2(1172, 650)
	var bz := StyleBoxFlat.new()
	bz.bg_color = Color("16181a")
	bz.set_corner_radius_all(16)
	bz.set_border_width_all(2)
	bz.border_color = Color("2c3033")
	bz.content_margin_left = 14
	bz.content_margin_right = 14
	bz.content_margin_top = 14
	bz.content_margin_bottom = 30
	bz.shadow_color = Color(0, 0, 0, 0.6)
	bz.shadow_size = 24
	bezel.add_theme_stylebox_override("panel", bz)
	add_child(bezel)
	var chin := label("● NOVA", 11, Color(1, 1, 1, 0.35))
	chin.position = Vector2(54 + 1172 * 0.5 - 24, 22 + 650 - 24)
	add_child(chin)
	screen = PanelContainer.new()
	var sc := StyleBoxFlat.new()
	sc.bg_color = PAPER
	sc.set_corner_radius_all(4)
	screen.add_theme_stylebox_override("panel", sc)
	bezel.add_child(screen)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 0)
	screen.add_child(page)
	page.add_child(top_bar())
	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 0)
	page.add_child(body)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var pad := MarginContainer.new()
	pad.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for side in ["left", "right", "top", "bottom"]: pad.add_theme_constant_override("margin_" + side, 16)
	scroll.add_child(pad)
	grid = GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 14)
	pad.add_child(grid)
	body.add_child(scroll)
	body.add_child(cart_panel())
	for id in products(): grid.add_child(card(id))
	refresh_cart()

func top_bar() -> Control:
	var bar := PanelContainer.new()
	var st := StyleBoxFlat.new()
	st.bg_color = Color("123a2d") if store == "equipment" else Color("1d2f45")
	st.content_margin_left = 20
	st.content_margin_right = 16
	st.content_margin_top = 10
	st.content_margin_bottom = 10
	bar.add_theme_stylebox_override("panel", st)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	bar.add_child(row)
	var titles := VBoxContainer.new()
	titles.add_theme_constant_override("separation", -2)
	titles.add_child(label(str(ShopCatalog.TITLES.get(store, store)).to_upper(), 22, Color.WHITE, true))
	titles.add_child(label("Online store  ·  order here, collect in store", 13, Color(1, 1, 1, 0.7)))
	titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(titles)
	wallet_chip = label("", 15, Color.WHITE, true)
	row.add_child(wallet_chip)
	var x := flat_button("✕  Close", Color(1, 1, 1, 0.12), Color.WHITE)
	x.pressed.connect(close)
	row.add_child(x)
	return bar

func card(id: String) -> Control:
	var item: Dictionary = ShopCatalog.ITEMS[id]
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(232, 0)
	var st := StyleBoxFlat.new()
	st.bg_color = Color.WHITE
	st.set_corner_radius_all(10)
	st.set_border_width_all(1)
	st.border_color = Color("dde3e1")
	st.content_margin_left = 12
	st.content_margin_right = 12
	st.content_margin_top = 10
	st.content_margin_bottom = 12
	panel.add_theme_stylebox_override("panel", st)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	panel.add_child(col)
	var pic_bg := PanelContainer.new()
	var pb := StyleBoxFlat.new()
	pb.bg_color = Color("eef2f1")
	pb.set_corner_radius_all(8)
	pic_bg.add_theme_stylebox_override("panel", pb)
	var pic := TextureRect.new()
	pic.custom_minimum_size = Vector2(0, 118)
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	pic_bg.add_child(pic)
	col.add_child(pic_bg)
	studio.request(id, func(tex: Texture2D) -> void:
		if is_instance_valid(pic): pic.texture = tex)
	col.add_child(label(str(item.name), 16, INK, true))
	var price := label(DeliverySession.money(int(item.price)) + ("  each" if ShopCatalog.is_supply(id) else ""), 18, ACCENT, true)
	col.add_child(price)
	for f: Variant in ShopCatalog.features(id).slice(0, 4):
		var line := label("•  " + str(f), 12, MUTED)
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.custom_minimum_size.x = 206
		col.add_child(line)
	var owned := session.bought(id) and not ShopCatalog.is_supply(id)
	if owned:
		col.add_child(label("✓  Owned" + ("  ·  waiting on the pickup shelf" if session.awaiting_pickup(id) else ""), 13, ACCENT, true))
		if ShopCatalog.is_vehicle(id) and session.active_vehicle != id:
			var use := flat_button("Use this vehicle", ACCENT, Color.WHITE)
			use.pressed.connect(func() -> void:
				close()
				equip.emit(id))
			col.add_child(use)
		return panel
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	col.add_child(row)
	_pick[id] = 1
	var qty := label("1", 16, INK, true)
	qty.custom_minimum_size.x = 26
	qty.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var minus := flat_button("−", Color("e6ebe9"), INK)
	var plus := flat_button("+", Color("e6ebe9"), INK)
	minus.pressed.connect(func() -> void:
		_pick[id] = maxi(1, int(_pick[id]) - 1)
		qty.text = str(_pick[id])
		click("cart_remove"))
	plus.pressed.connect(func() -> void:
		var cap := ShopCatalog.max_qty(id) - int(cart.get(id, 0))
		_pick[id] = clampi(int(_pick[id]) + 1, 1, maxi(1, cap))
		qty.text = str(_pick[id])
		click("cart_add"))
	if not ShopCatalog.is_supply(id):
		minus.disabled = true
		plus.disabled = true
	row.add_child(minus)
	row.add_child(qty)
	row.add_child(plus)
	var add := flat_button("Add to cart", ACCENT, Color.WHITE)
	add.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add.pressed.connect(func() -> void: add_to_cart(id, int(_pick[id])))
	row.add_child(add)
	return panel

func cart_panel() -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(300, 0)
	var st := StyleBoxFlat.new()
	st.bg_color = Color("e9eeec")
	st.content_margin_left = 16
	st.content_margin_right = 16
	st.content_margin_top = 14
	st.content_margin_bottom = 14
	panel.add_theme_stylebox_override("panel", st)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	col.add_child(label("🛒  Your cart", 18, INK, true))
	cart_box = VBoxContainer.new()
	cart_box.add_theme_constant_override("separation", 6)
	cart_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(cart_box)
	col.add_child(HSeparator.new())
	total_label = label("", 18, INK, true)
	col.add_child(total_label)
	after_label = label("", 13, MUTED)
	col.add_child(after_label)
	buy_button = flat_button("Purchase", ACCENT, Color.WHITE)
	buy_button.custom_minimum_size.y = 46
	buy_button.add_theme_font_size_override("font_size", 18)
	buy_button.pressed.connect(purchase)
	col.add_child(buy_button)
	message = label("", 13, Color("b3401f"))
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	message.custom_minimum_size.x = 266
	col.add_child(message)
	col.add_child(label("Collect paid orders at the ONLINE ORDER PICKUP shelf in this store.", 11, MUTED))
	(col.get_child(col.get_child_count() - 1) as Label).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return panel

# --- cart --------------------------------------------------------------------------------

func add_to_cart(id: String, qty: int) -> void:
	var cap := ShopCatalog.max_qty(id) if ShopCatalog.is_supply(id) else 1
	cart[id] = clampi(int(cart.get(id, 0)) + qty, 1, cap)
	message.text = ""
	click("cart_add")
	refresh_cart()

func change(id: String, delta: int) -> void:
	var cap := ShopCatalog.max_qty(id) if ShopCatalog.is_supply(id) else 1
	var q := int(cart.get(id, 0)) + delta
	if q <= 0: cart.erase(id)
	else: cart[id] = mini(q, cap)
	click("cart_remove" if delta < 0 else "cart_add")
	refresh_cart()

func total() -> int:
	var t := 0
	for id: String in cart: t += int(ShopCatalog.ITEMS[id].price) * int(cart[id])
	return t

func refresh_cart() -> void:
	wallet_chip.text = "Wallet  " + DeliverySession.money(session.wallet)
	for c in cart_box.get_children(): c.queue_free()
	if cart.is_empty():
		cart_box.add_child(label("Your cart is empty.\nPick something on the left.", 13, MUTED))
	for id: String in cart:
		var item: Dictionary = ShopCatalog.ITEMS[id]
		var line := VBoxContainer.new()
		line.add_theme_constant_override("separation", 2)
		var name_row := HBoxContainer.new()
		var n := label(str(item.name), 13, INK, true)
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.clip_text = true
		name_row.add_child(n)
		name_row.add_child(label(DeliverySession.money(int(item.price) * int(cart[id])), 13, INK, true))
		line.add_child(name_row)
		var ctl := HBoxContainer.new()
		ctl.add_theme_constant_override("separation", 4)
		var m := flat_button("−", Color.WHITE, INK)
		m.pressed.connect(change.bind(id, -1))
		var q := label("× %d" % int(cart[id]), 13, INK)
		q.custom_minimum_size.x = 34
		q.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var p := flat_button("+", Color.WHITE, INK)
		p.pressed.connect(change.bind(id, 1))
		p.disabled = not ShopCatalog.is_supply(id) or int(cart[id]) >= ShopCatalog.max_qty(id)
		var r := flat_button("Remove", Color(0, 0, 0, 0), Color("b3401f"))
		r.pressed.connect(change.bind(id, -99))
		for b: Control in [m, q, p, r]: ctl.add_child(b)
		line.add_child(ctl)
		cart_box.add_child(line)
	var t := total()
	total_label.text = "Total  " + DeliverySession.money(t)
	after_label.text = "Wallet after purchase  " + DeliverySession.money(session.wallet - t)
	after_label.add_theme_color_override("font_color", MUTED if session.wallet >= t else Color("b3401f"))
	buy_button.disabled = cart.is_empty() or session.wallet < t

func purchase() -> void:
	var result := session.checkout(cart, store)
	if result.begins_with("Paid"):
		cart.clear()
		click("purchase_complete")
		purchased.emit(result)
		show_receipt(result)
	else:
		message.text = result
		click("not_enough_money")

## Thank-you screen after a purchase.
func show_receipt(result: String) -> void:
	for c in screen.get_children(): c.queue_free()
	var col := VBoxContainer.new()
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_theme_constant_override("separation", 14)
	screen.add_child(col)
	var tick := label("✓", 64, ACCENT, true)
	tick.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(tick)
	var t := label("Thank you for your order!", 28, INK, true)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(t)
	var m := label(result + "\nOrder #%04d · %s" % [1000 + session.store_serial + session.inventory.size(), str(ShopCatalog.TITLES.get(store, ""))], 16, MUTED)
	m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(m)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 12)
	var more := flat_button("Continue shopping", Color("e6ebe9"), INK)
	more.pressed.connect(build)
	var done := flat_button("Done", ACCENT, Color.WHITE)
	done.pressed.connect(close)
	row.add_child(more)
	row.add_child(done)
	col.add_child(row)
	done.grab_focus()

# --- widgets -----------------------------------------------------------------------------

func label(text: String, size: int, colour: Color, bold := false) -> Label:
	var l := Label.new()
	l.text = text
	var f := FontVariation.new()
	f.base_font = _font
	f.variation_embolden = 0.6 if bold else 0.0
	l.add_theme_font_override("font", f)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l

func flat_button(text: String, bg: Color, fg: Color) -> Button:
	var b := Button.new()
	b.text = text
	b.add_theme_font_size_override("font_size", 14)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		b.add_theme_color_override(state, fg)
	b.add_theme_color_override("font_disabled_color", Color(fg, 0.35))
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var st := StyleBoxFlat.new()
		st.bg_color = bg.lightened(0.08) if state == "hover" else (bg.darkened(0.12) if state == "pressed" else (Color(bg, bg.a * 0.45) if state == "disabled" else bg))
		st.set_corner_radius_all(7)
		st.content_margin_left = 10
		st.content_margin_right = 10
		st.content_margin_top = 5
		st.content_margin_bottom = 5
		if state == "focus":
			st.draw_center = false
			st.set_border_width_all(2)
			st.border_color = Color(ACCENT, 0.6)
		b.add_theme_stylebox_override(state, st)
	b.mouse_entered.connect(func() -> void: pass)
	return b

func click(sound: String) -> void:
	var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
	if audio and CityAudio.has_sound(sound): audio.play_ui(sound, -8.0)
