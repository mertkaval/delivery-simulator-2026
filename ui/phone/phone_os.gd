class_name PhoneOS
extends Control
## The courier's phone screen (rendered into a SubViewport on the 3D phone, 450 x 950 px).
## Status bar (clock, network, battery), home screen with a date/time + weather widget and a
## day bar (time of day with the lunch/dinner rush marked), an app grid and a home bar.
## Apps: CourierNow (the delivery app: shift on/off, offers, active order, earnings),
## Maps (opens the city map), Wallet (balance and history), Weather (now + next hours);
## the rest are locked "coming soon" apps.
## Game actions go out through `action(name, arg)`; app_root handles them.

signal action(name: String, arg: String)

const W := 450
const H := 950
const APPS := [
	{"id": "courier", "name": "CourierNow", "icon": "➜", "color": "ff6a2b", "live": true},
	{"id": "maps", "name": "Maps", "icon": "◈", "color": "2e9e6a", "live": true},
	{"id": "wallet", "name": "Wallet", "icon": "$", "color": "2f6fd6", "live": true},
	{"id": "weather", "name": "Weather", "icon": "☀", "color": "f0a92a", "live": true},
	{"id": "messages", "name": "Messages", "icon": "✉", "color": "3ba55d", "live": false},
	{"id": "music", "name": "Music", "icon": "♪", "color": "d6336c", "live": false},
	{"id": "camera", "name": "Camera", "icon": "◉", "color": "5c636a", "live": false},
	{"id": "bank", "name": "Bank", "icon": "₺", "color": "0b7285", "live": false},
	{"id": "social", "name": "Chirp", "icon": "✦", "color": "7048e8", "live": false},
	{"id": "rides", "name": "Rides", "icon": "⛟", "color": "212529", "live": false},
	{"id": "games", "name": "Games", "icon": "♞", "color": "e8590c", "live": false},
	{"id": "settings", "name": "Settings", "icon": "⚙", "color": "868e96", "live": false},
]

var game        ## app_root (dynamic)
var page := "home"
var status_time: Label
var status_right: Label
var content: Control
var toast: Label
var _toast_t := 0.0
var _font: SystemFont
var _clock: Label
var _now_marker: Control
var _day_width := 1.0
var _countdown: Label
var _signature := ""

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	size = Vector2(W, H)
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Segoe UI", "Arial", "sans-serif"])
	var bg := ColorRect.new()
	bg.color = Color("0b1418")
	bg.size = size
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	content = Control.new()
	content.position = Vector2(0, 52)
	content.size = Vector2(W, H - 52 - 46)
	add_child(content)
	# Status bar.
	var bar := ColorRect.new()
	bar.color = Color(0, 0, 0, 0.35)
	bar.size = Vector2(W, 52)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bar)
	status_time = text("", 24, Color.WHITE, true)
	status_time.position = Vector2(26, 10)
	add_child(status_time)
	var notch := ColorRect.new()
	notch.color = Color.BLACK
	notch.size = Vector2(16, 16)
	notch.position = Vector2(W * 0.5 - 8, 16)
	add_child(notch)
	status_right = text("", 20, Color.WHITE)
	status_right.position = Vector2(W - 190, 13)
	status_right.size = Vector2(170, 30)
	status_right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	add_child(status_right)
	# Home bar (gesture area): tap to go home.
	var home := Button.new()
	home.flat = true
	home.position = Vector2(0, H - 46)
	home.size = Vector2(W, 46)
	home.focus_mode = Control.FOCUS_NONE
	home.pressed.connect(func() -> void: open_page("home"))
	add_child(home)
	var pill := ColorRect.new()
	pill.color = Color(1, 1, 1, 0.75)
	pill.size = Vector2(140, 6)
	pill.position = Vector2(W * 0.5 - 70, H - 26)
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(pill)
	toast = text("", 22, Color.WHITE, true)
	toast.position = Vector2(30, H - 140)
	toast.size = Vector2(W - 60, 60)
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var ts := StyleBoxFlat.new()
	ts.bg_color = Color(0.1, 0.12, 0.14, 0.94)
	ts.set_corner_radius_all(30)
	toast.add_theme_stylebox_override("normal", ts)
	toast.visible = false
	add_child(toast)
	open_page("home")

func session() -> DeliverySession:
	return game.session if game != null else DeliverySession.new()

func _process(delta: float) -> void:
	if not is_visible_in_tree() or game == null: return
	var s := session()
	status_time.text = "%02d:%02d" % [int(s.hour()), int(s.calendar_minutes) % 60]
	var battery := 100 - int(fmod(s.clock / 60.0, 80.0))
	status_right.text = "▂▄▆ 4G   %d%% ▮" % battery
	if _toast_t > 0.0:
		_toast_t -= delta
		toast.visible = _toast_t > 0.0
	# Live parts update in place (rebuilding would swallow taps).
	if page == "home" and is_instance_valid(_clock):
		_clock.text = status_time.text
		_now_marker.position.x = clampf((s.hour() - 6.0) / 18.0, 0.0, 1.0) * _day_width - 2.0
	if page == "courier":
		if is_instance_valid(_countdown) and s.order.get("state") == "OFFERED":
			_countdown.text = "%d s to respond" % maxi(0, int(float(s.order.expires) - s.clock))
		if courier_signature() != _signature: open_page("courier", true)

func courier_signature() -> String:
	var s := session()
	return "%s|%s|%s|%s|%s" % [s.order.get("id", ""), s.order.get("state", ""), s.online, s.has_bag(), s.order.get("slot", "")]

func flash(message: String) -> void:
	toast.text = message
	_toast_t = 2.2
	toast.visible = true

# --- pages -------------------------------------------------------------------------------

func open_page(which: String, refresh := false) -> void:
	if not refresh and which != page: sound("app_open" if which != "home" else "phone_tap")
	page = which
	_countdown = null
	for c in content.get_children(): c.queue_free()
	match which:
		"home": build_home()
		"courier": build_courier()
		"wallet": build_wallet()
		"weather": build_weather()
	if not refresh and game != null: action.emit("page", which)

func build_home() -> void:
	var wall := TextureRect.new()
	var grad := Gradient.new()
	grad.colors = PackedColorArray([Color("163b45"), Color("0d1c26"), Color("2a1d3a")])
	grad.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	var gt := GradientTexture2D.new()
	gt.gradient = grad
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(0.4, 1)
	wall.texture = gt
	wall.size = content.size
	wall.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(wall)
	var s := session()
	# Clock + date + weather widget.
	var clock := text("%02d:%02d" % [int(s.hour()), int(s.calendar_minutes) % 60], 88, Color.WHITE, true)
	clock.position = Vector2(30, 14)
	content.add_child(clock)
	_clock = clock
	var date := text(s.date_text(), 24, Color(1, 1, 1, 0.85))
	date.position = Vector2(34, 122)
	content.add_child(date)
	var weather_text := "—"
	if game != null and game.world.weather != null: weather_text = game.world.weather.describe()
	var w := text(weather_icon(weather_text) + "  " + weather_text, 26, Color("ffe8a3"), true)
	w.position = Vector2(34, 158)
	content.add_child(w)
	# Day bar: 06:00 → 24:00 with meal rushes and a "now" marker.
	var bar := Control.new()
	bar.position = Vector2(34, 210)
	bar.size = Vector2(W - 68, 46)
	content.add_child(bar)
	var track := ColorRect.new()
	track.color = Color(1, 1, 1, 0.16)
	track.size = Vector2(bar.size.x, 8)
	track.position.y = 8
	bar.add_child(track)
	for rush: Vector2 in [Vector2(11, 14), Vector2(17, 20)]:
		var r := ColorRect.new()
		r.color = Color("ff9d5c")
		r.position = Vector2((rush.x - 6.0) / 18.0 * bar.size.x, 8)
		r.size = Vector2((rush.y - rush.x) / 18.0 * bar.size.x, 8)
		bar.add_child(r)
	var now := ColorRect.new()
	now.color = Color.WHITE
	now.size = Vector2(4, 22)
	now.position = Vector2(clampf((s.hour() - 6.0) / 18.0, 0.0, 1.0) * bar.size.x - 2, 1)
	bar.add_child(now)
	_now_marker = now
	_day_width = bar.size.x
	var legend := text("06        rush 11–14        rush 17–20        24", 15, Color(1, 1, 1, 0.6))
	legend.position = Vector2(0, 22)
	bar.add_child(legend)
	# App grid.
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 22)
	grid.add_theme_constant_override("v_separation", 18)
	grid.position = Vector2(26, 290)
	content.add_child(grid)
	for app: Dictionary in APPS:
		grid.add_child(app_icon(app))

func app_icon(app: Dictionary) -> Control:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 4)
	var b := Button.new()
	b.custom_minimum_size = Vector2(84, 84)
	b.text = str(app.icon)
	b.add_theme_font_size_override("font_size", 40)
	b.focus_mode = Control.FOCUS_NONE
	var colour := Color(str(app.color))
	if not app.live: colour = colour.darkened(0.45)
	for state in ["normal", "hover", "pressed"]:
		var st := StyleBoxFlat.new()
		st.bg_color = colour.lightened(0.1) if state == "hover" else (colour.darkened(0.15) if state == "pressed" else colour)
		st.set_corner_radius_all(22)
		b.add_theme_stylebox_override(state, st)
	for c in ["font_color", "font_hover_color", "font_pressed_color"]:
		b.add_theme_color_override(c, Color(1, 1, 1, 1.0 if app.live else 0.45))
	b.pressed.connect(tap_app.bind(app))
	col.add_child(b)
	if not app.live:
		var lock := text("🔒", 22, Color.WHITE)
		lock.position = Vector2(58, 54)
		b.add_child(lock)
	var name := text(str(app.name), 17, Color(1, 1, 1, 1.0 if app.live else 0.55))
	name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name.custom_minimum_size.x = 84
	col.add_child(name)
	return col

func tap_app(app: Dictionary) -> void:
	if not app.live:
		sound("app_locked")
		flash("%s · coming soon" % app.name)
		return
	match str(app.id):
		"maps":
			sound("app_open")
			action.emit("maps", "")
		_:
			open_page(str(app.id))

func header(title: String, colour: Color) -> VBoxContainer:
	var bg := ColorRect.new()
	bg.color = Color("f3f5f4")
	bg.size = content.size
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(bg)
	var top := ColorRect.new()
	top.color = colour
	top.size = Vector2(W, 86)
	content.add_child(top)
	var back := Button.new()
	back.text = "‹"
	back.flat = true
	back.focus_mode = Control.FOCUS_NONE
	back.add_theme_font_size_override("font_size", 46)
	back.add_theme_color_override("font_color", Color.WHITE)
	back.position = Vector2(8, 8)
	back.size = Vector2(60, 70)
	back.pressed.connect(func() -> void: open_page("home"))
	content.add_child(back)
	var t := text(title, 34, Color.WHITE, true)
	t.position = Vector2(72, 20)
	content.add_child(t)
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(0, 86)
	scroll.size = Vector2(W, content.size.y - 86)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	content.add_child(scroll)
	var pad := MarginContainer.new()
	pad.custom_minimum_size.x = W
	for side in ["left", "right", "top", "bottom"]: pad.add_theme_constant_override("margin_" + side, 20)
	scroll.add_child(pad)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	pad.add_child(col)
	return col

## The delivery app.
func build_courier() -> void:
	var s := session()
	_signature = courier_signature()
	var col := header("CourierNow", Color("ff6a2b"))
	var state: String = s.order.get("state", "")
	# Shift status + toggle.
	var status := card(col)
	var line := HBoxContainer.new()
	status.add_child(line)
	var dot := text("●", 26, Color("2fb36b") if s.online else Color("9aa3a8"))
	line.add_child(dot)
	var st := text("  Online · " + s.demand() if s.online else "  Offline", 22, Color("1d2427"), true)
	st.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(st)
	if not s.has_bag():
		status.add_child(wrapped(text("You need an insulated delivery bag before you can take orders. Trail & Tool sells one.", 18, Color("b3401f"))))
	var toggle := big_button("Go offline" if s.online else "Start shift · go online", Color("1d2427") if s.online else Color("2fb36b"))
	toggle.disabled = not s.has_bag() and not s.online
	toggle.pressed.connect(func() -> void: action.emit("toggle_online", ""))
	status.add_child(toggle)
	if state == "OFFERED":
		var c := card(col, Color("fff4ec"))
		c.add_child(text("NEW REQUEST", 16, Color("ff6a2b"), true))
		c.add_child(wrapped(text(s.restaurant_name(), 30, Color("1d2427"), true)))
		c.add_child(method_chip(str(s.order.get("method", "door"))))
		c.add_child(wrapped(text("%s · %s\n%s" % [s.order.get("customer", "?"), s.order.get("ticket", ""), items_text(s)], 19, Color("3a4448"))))
		c.add_child(text(DeliverySession.money(int(s.order.quote)) + "  + tip", 38, Color("1d2427"), true))
		c.add_child(wrapped(text("Pickup %d m · Drop-off %d m\n%s" % [int(s.order.pickup_distance), int(s.order.distance), DeliverySession.ADDRESSES[int(s.order.address)]], 18, Color("5f6b70"))))
		_countdown = text("", 18, Color("ff6a2b"), true)
		c.add_child(_countdown)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		var accept := big_button("Accept", Color("2fb36b"))
		accept.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		accept.pressed.connect(func() -> void: action.emit("accept", ""))
		row.add_child(accept)
		if game.tutorial.gate("reject") == "":
			var decline := big_button("Decline", Color("9aa3a8"))
			decline.pressed.connect(func() -> void: action.emit("reject", ""))
			row.add_child(decline)
		c.add_child(row)
	elif state in DeliverySession.ACTIVE:
		var c := card(col, Color("eef8f2"))
		var picked := state != "ACCEPTED"
		c.add_child(text("ACTIVE ORDER · " + str(s.order.get("ticket", "")), 16, Color("1f8a63"), true))
		c.add_child(wrapped(text(("1  Pick up at " + s.restaurant_name()) if not picked else ("2  Deliver to " + str(s.order.get("customer", ""))), 26, Color("1d2427"), true)))
		c.add_child(method_chip(str(s.order.get("method", "door"))))
		var where: String = s.restaurant_name() if not picked else DeliverySession.ADDRESSES[int(s.order.address)]
		c.add_child(wrapped(text("%s\n%s" % [where, items_text(s)], 19, Color("3a4448"))))
		var how := {"ACCEPTED": "Find the package with your customer's name on the pickup shelf.",
			"IN_HAND": "In your hands. Pack it in the backpack (F) or put it down (G).",
			"DROPPED": "You put it down. Go back and pick it up (E).",
			"CARRYING": "Packed in your backpack."}
		c.add_child(wrapped(text(str(how.get(state, "")), 17, Color("5f6b70"))))
		if picked:
			c.add_child(wrapped(text("At the door: " + ("leave it inside the yellow marked area." if s.order.get("method", "door") == "door" else "knock (E on the door), then hand it over (E)."), 17, Color("1f8a63"), true)))
		var nav := big_button("Navigate", Color("2e9e6a"))
		nav.pressed.connect(func() -> void: action.emit("maps", ""))
		c.add_child(nav)
	else:
		var c := card(col)
		c.add_child(wrapped(text("Waiting for requests near you…" if s.online else "Go online to receive delivery requests.", 22, Color("3a4448"))))
		c.add_child(wrapped(text("Lunch 11–14 and dinner 17–20 are the busy hours.", 17, Color("5f6b70"))))
	var e := card(col)
	e.add_child(text("TODAY", 16, Color("5f6b70"), true))
	e.add_child(text("%s   ·   %d deliveries" % [DeliverySession.money(s.wallet), s.completed], 26, Color("1d2427"), true))

func build_wallet() -> void:
	var s := session()
	var col := header("Wallet", Color("2f6fd6"))
	var c := card(col)
	c.add_child(text("BALANCE", 16, Color("5f6b70"), true))
	c.add_child(text(DeliverySession.money(s.wallet), 54, Color("1d2427"), true))
	var bike := ShopCatalog.ITEMS["bicycle"]
	if not s.owns("bicycle"):
		var goal := card(col, Color("eef3ff"))
		goal.add_child(text("Saving for a bicycle", 20, Color("2f6fd6"), true))
		var bar := ProgressBar.new()
		bar.max_value = float(bike.price)
		bar.value = float(s.wallet)
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(0, 16)
		goal.add_child(bar)
		goal.add_child(text("%s of %s · Cedar Cycles" % [DeliverySession.money(s.wallet), DeliverySession.money(int(bike.price))], 17, Color("5f6b70")))
	var h := card(col)
	h.add_child(text("HISTORY", 16, Color("5f6b70"), true))
	var keys: Array = s.ledger.keys()
	keys.reverse()
	for k: String in keys.slice(0, 10):
		var v := int(s.ledger[k])
		var row := HBoxContainer.new()
		var name := text(ledger_name(k), 18, Color("1d2427"))
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(name)
		row.add_child(text(("+" if v > 0 else "") + DeliverySession.money(v), 18, Color("1f8a63") if v > 0 else Color("b3401f"), true))
		h.add_child(row)

func build_weather() -> void:
	var col := header("Weather", Color("f0a92a"))
	var c := card(col, Color("fff8e8"))
	var now := "—"
	var ws: WeatherSystem = game.world.weather if game != null else null
	if ws != null: now = ws.describe()
	c.add_child(text(weather_icon(now) + "  " + now, 40, Color("1d2427"), true))
	c.add_child(text("Atatürk Avenue district", 17, Color("5f6b70")))
	if ws != null:
		var f := card(col)
		f.add_child(text("NEXT HOURS · CHANCE OF RAIN", 16, Color("5f6b70"), true))
		for h in range(1, 7):
			var fc := ws.forecast(ws.minutes + h * 60.0)
			var row := HBoxContainer.new()
			var hour := text("%02d:00" % ((int(session().hour()) + h) % 24), 20, Color("1d2427"))
			hour.custom_minimum_size.x = 100
			row.add_child(hour)
			row.add_child(text(("🌧" if fc.x > 0.4 else ("☁" if fc.y > 0.55 else "☀")) + "  %d%%" % int(fc.x * 100.0), 20, Color("1d2427")))
			f.add_child(row)

# --- widgets -----------------------------------------------------------------------------

func card(parent: Control, bg := Color.WHITE) -> VBoxContainer:
	var p := PanelContainer.new()
	var st := StyleBoxFlat.new()
	st.bg_color = bg
	st.set_corner_radius_all(18)
	st.content_margin_left = 18
	st.content_margin_right = 18
	st.content_margin_top = 14
	st.content_margin_bottom = 16
	st.shadow_color = Color(0, 0, 0, 0.08)
	st.shadow_size = 6
	p.add_theme_stylebox_override("panel", st)
	parent.add_child(p)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	p.add_child(col)
	return col

func method_chip(method: String) -> Control:
	var chip := text(("⌂  LEAVE AT DOOR" if method == "door" else "☺  MEET AT DOOR"), 17, Color.WHITE, true)
	var st := StyleBoxFlat.new()
	st.bg_color = Color("c98a00") if method == "door" else Color("1f8a63")
	st.set_corner_radius_all(12)
	st.content_margin_left = 12
	st.content_margin_right = 12
	st.content_margin_top = 4
	st.content_margin_bottom = 4
	chip.add_theme_stylebox_override("normal", st)
	chip.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	return chip

func big_button(label: String, colour: Color) -> Button:
	var b := Button.new()
	b.text = label
	b.custom_minimum_size = Vector2(0, 64)
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 24)
	for c in ["font_color", "font_hover_color", "font_pressed_color"]: b.add_theme_color_override(c, Color.WHITE)
	b.add_theme_color_override("font_disabled_color", Color(1, 1, 1, 0.5))
	for state in ["normal", "hover", "pressed", "disabled"]:
		var st := StyleBoxFlat.new()
		st.bg_color = colour.lightened(0.08) if state == "hover" else (colour.darkened(0.15) if state == "pressed" else (Color(colour, 0.4) if state == "disabled" else colour))
		st.set_corner_radius_all(16)
		b.add_theme_stylebox_override(state, st)
	b.pressed.connect(func() -> void: sound("phone_tap"))
	return b

func text(s: String, size: int, colour: Color, bold := false) -> Label:
	var l := Label.new()
	l.text = s
	var f := FontVariation.new()
	f.base_font = _font
	f.variation_embolden = 0.7 if bold else 0.0
	l.add_theme_font_override("font", f)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l

func wrapped(l: Label) -> Label:
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = W - 76
	return l

func items_text(s: DeliverySession) -> String:
	var parts := PackedStringArray()
	for it: Array in s.order.get("items", []): parts.append("%dx %s" % [int(it[1]), it[0]])
	return ", ".join(parts)

func ledger_name(key: String) -> String:
	if key.begins_with("payment_job_"): return "Delivery " + key.trim_prefix("payment_job_").lstrip("0")
	if key.begins_with("purchase_"): return str(ShopCatalog.ITEMS.get(key.trim_prefix("purchase_"), {}).get("name", "Purchase"))
	if key.begins_with("store_order_"): return "Store supplies"
	if key.begins_with("consumable_"): return "Food & drink"
	return {"starting_funds": "Starting money", "upgrade_insulated_bag": "Delivery bag", "bonus_tutorial": "Training bonus"}.get(key, key)

static func weather_icon(desc: String) -> String:
	if desc.begins_with("Rain") or desc.begins_with("Drizzle"): return "🌧"
	if desc.begins_with("Overcast"): return "☁"
	return "☀"

func sound(name: String) -> void:
	var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
	if audio and ResourceLoader.exists(CityAudio.SFX % name): audio.play_ui(name, -10.0)
