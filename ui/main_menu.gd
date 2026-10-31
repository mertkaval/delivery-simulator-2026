class_name MainMenu
extends Control
## Title and pause menu. Transparent buttons on the left over a big living picture of the city:
## the golden-hour skyline slowly drifts (Ken Burns), birds fly across it, and a photo collage
## of one delivery (pickup shelf, ride, doorstep handover) plays out with a live order tracker.
## The stills are rendered from the game world by tools/render_menu_collage.gd.
## In game (Esc) the same menu sits over the paused street instead of the artwork.

signal chosen(action: String)   ## continue, resume, save, new_game, exit_to_menu, quit

const ACCENT := Color("7fe3b5")
const WARM := Color("f4e7c4")
const STILLS := {"city": "res://ui/menu/collage_city.jpg", "ride": "res://ui/menu/collage_ride.jpg",
	"pickup": "res://ui/menu/collage_pickup.jpg", "delivery": "res://ui/menu/collage_delivery.jpg"}
const CYCLE := 9.0   ## seconds for one pickup → ride → delivered loop of the tracker

var in_game := false
var has_save := false
var save_summary := ""
var page := "main"
var t := 0.0
var art: Control
var hero: TextureRect
var flock: Flock
var collage: Control
var tiles: Array[Control] = []
var tile_base: Array[Vector2] = []
var tracker_dot: Control
var tracker_steps: Array[Label] = []
var stamp: Label
var game_shade: ColorRect
var title_box: VBoxContainer
var column: VBoxContainer
var footer: Label
var toast: Label
var _toast_time := 0.0
var _stamp_shown := false
static var _fonts: Dictionary = {}

## Bahnschrift (Windows) reads as a clean game title face; falls back to Segoe UI / Arial.
static func font(weight: int, spacing: int = 0) -> Font:
	var key := "%d_%d" % [weight, spacing]
	if not _fonts.has(key):
		var base := SystemFont.new()
		base.font_names = PackedStringArray(["Bahnschrift", "Segoe UI", "Arial", "sans-serif"])
		base.font_weight = weight
		var v := FontVariation.new()
		v.base_font = base
		v.spacing_glyph = spacing
		_fonts[key] = v
	return _fonts[key]

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	# The artwork: city, birds, collage.
	art = Control.new()
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.clip_contents = true
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(art)
	var bg := ColorRect.new()
	bg.color = Color("0b1216")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.add_child(bg)
	hero = TextureRect.new()
	hero.texture = still("city")
	hero.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	hero.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	hero.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hero.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.add_child(hero)
	flock = Flock.new()
	flock.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.add_child(flock)
	build_collage()
	# Paused-game shade (in game only) and the left-side gradient behind the menu.
	game_shade = ColorRect.new()
	game_shade.color = Color(0.01, 0.02, 0.03, 0.38)
	game_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	game_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(game_shade)
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.3, 0.58])
	grad.colors = PackedColorArray([Color(0.015, 0.025, 0.035, 0.9), Color(0.015, 0.025, 0.035, 0.66), Color(0.015, 0.025, 0.035, 0.0)])
	var gt := GradientTexture2D.new()
	gt.gradient = grad
	gt.width = 256
	gt.height = 4
	var left := TextureRect.new()
	left.texture = gt
	left.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	left.stretch_mode = TextureRect.STRETCH_SCALE
	left.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(left)
	# Title.
	title_box = VBoxContainer.new()
	title_box.position = Vector2(64, 58)
	title_box.add_theme_constant_override("separation", -6)
	add_child(title_box)
	title_box.add_child(text_label("ATATÜRK AVENUE  ·  COURIERNOW", 14, ACCENT, 600, 4))
	title_box.add_child(text_label("DELIVERY", 76, Color.WHITE, 700, 1))
	title_box.add_child(text_label("SIMULATOR 2026", 30, Color(1, 1, 1, 0.82), 400, 9))
	var tag := text_label("Every street is a new beginning.", 17, WARM, 400, 0)
	tag.custom_minimum_size.y = 34
	tag.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	title_box.add_child(tag)
	# Buttons / pages.
	column = VBoxContainer.new()
	column.position = Vector2(56, 292)
	column.custom_minimum_size = Vector2(360, 0)
	column.add_theme_constant_override("separation", 2)
	add_child(column)
	toast = text_label("", 15, ACCENT, 600, 1)
	toast.position = Vector2(66, 640)
	add_child(toast)
	footer = text_label("EARLY DEVELOPMENT  ·  0.3     ↑↓ / mouse  ·  Enter select  ·  Esc back", 12, Color(1, 1, 1, 0.45), 400, 1)
	footer.position = Vector2(66, 676)
	add_child(footer)
	hide()

func still(key: String) -> Texture2D:
	var path: String = STILLS[key]
	return load(path) if ResourceLoader.exists(path) else null

func text_label(s: String, size: int, colour: Color, weight: int, spacing: int) -> Label:
	var l := Label.new()
	l.text = s
	l.add_theme_font_override("font", font(weight, spacing))
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	l.add_theme_constant_override("shadow_offset_y", 2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l

## Open as the title screen (in_game false) or the pause menu.
func open(as_in_game: bool) -> void:
	in_game = as_in_game
	art.visible = not in_game
	game_shade.visible = in_game
	(title_box.get_child(0) as Label).text = "SHIFT PAUSED  ·  TIMERS STOPPED" if in_game else "ATATÜRK AVENUE  ·  COURIERNOW"
	show()
	show_page("main")
	# Entrance: title and column slide in, buttons fade in one after another.
	for c: Control in [title_box, column]:
		var to := c.position
		c.position.x -= 36
		c.modulate.a = 0.0
		var tw := create_tween().set_parallel()
		tw.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tw.tween_property(c, "position", to, 0.55)
		tw.tween_property(c, "modulate:a", 1.0, 0.45)
	_stamp_shown = false
	t = 0.0

func close() -> void:
	hide()
	page = "main"

## Esc inside a sub page goes back; returns false when already on the main page.
func back() -> bool:
	if page == "main": return false
	if page == "settings": GameSettings.save_settings()
	show_page("main")
	return true

func flash(message: String) -> void:
	toast.text = message
	_toast_time = 3.0

func show_page(which: String) -> void:
	page = which
	for c in column.get_children():
		column.remove_child(c)
		c.queue_free()
	match which:
		"main":
			if in_game:
				menu_button("Continue", func(): emit("resume"))
				menu_button("Save Game", func(): emit("save"))
				menu_button("New Game", func(): show_page("confirm_new"))
				menu_button("Settings", func(): show_page("settings"))
				menu_button("Exit to Menu", func(): emit("exit_to_menu"), "saves your shift")
				menu_button("Exit to Desktop", func(): emit("quit"), "saves your shift")
			else:
				if has_save: menu_button("Continue", func(): emit("continue"), save_summary)
				menu_button("New Game", start_new)
				menu_button("Save Game", func(): pass).disabled = true
				menu_button("Settings", func(): show_page("settings"))
				menu_button("Exit to Menu", func(): pass).disabled = true
				menu_button("Exit to Desktop", func(): emit("quit"))
		"confirm_new":
			column.add_child(text_label("Start a new shift?", 28, Color.WHITE, 600, 0))
			var note := text_label("Your current save will be replaced. The previous save stays in the backup until the next save.", 15, Color(1, 1, 1, 0.72), 400, 0)
			note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			note.custom_minimum_size = Vector2(340, 64)
			column.add_child(note)
			menu_button("Start New Shift", func(): emit("new_game"))
			menu_button("Back", func(): show_page("main"))
		"settings":
			column.add_child(text_label("SETTINGS", 14, ACCENT, 600, 4))
			slider_row("Master volume", "master", 0.0, 1.0, 0.05, true)
			slider_row("City ambience", "ambience", 0.0, 1.0, 0.05, true)
			slider_row("Effects & phone", "effects", 0.0, 1.0, 0.05, true)
			slider_row("Mouse sensitivity", "sensitivity", 0.3, 2.5, 0.05, false)
			slider_row("Field of view", "fov", 60.0, 100.0, 1.0, false)
			toggle_row("Fullscreen", "fullscreen")
			toggle_row("Vertical sync", "vsync")
			toggle_row("Third-person view (V)", "third_person")
			slider_row("Camera distance", "camera_distance", PlayerCameraRig.MIN_DISTANCE, PlayerCameraRig.MAX_DISTANCE, 0.1, false)
			city_row()
			city_build_row()
			menu_button("Back", func(): back())
	for c in column.get_children():
		var focusable := c as Control
		if c is Button and not (c as Button).disabled or c is HBoxContainer:
			if c is HBoxContainer: focusable = c.get_child(1) as Control
			focusable.grab_focus()
			break

func start_new() -> void:
	if has_save: show_page("confirm_new")
	else: emit("new_game")

func emit(action: String) -> void:
	chosen.emit(action)

func menu_sound(sound: String, volume_db: float) -> void:
	var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
	if audio: audio.play_ui(sound, volume_db)

## A transparent menu button: text only; hover/focus lights a soft bar with a mint edge.
func menu_button(label: String, callback: Callable, hint := "") -> Button:
	var b := Button.new()
	b.text = label
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(360, 50 if hint == "" else 58)
	b.add_theme_font_override("font", font(500, 1))
	b.add_theme_font_size_override("font_size", 25)
	b.add_theme_color_override("font_color", Color(1, 1, 1, 0.88))
	b.add_theme_color_override("font_hover_color", Color.WHITE)
	b.add_theme_color_override("font_focus_color", Color.WHITE)
	b.add_theme_color_override("font_hover_pressed_color", ACCENT)
	b.add_theme_color_override("font_pressed_color", ACCENT)
	b.add_theme_color_override("font_disabled_color", Color(1, 1, 1, 0.26))
	b.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.5))
	b.add_theme_constant_override("outline_size", 2)
	var idle := StyleBoxFlat.new()
	idle.bg_color = Color(1, 1, 1, 0.0)
	idle.content_margin_left = 16
	idle.content_margin_bottom = 14 if hint != "" else 0
	var lit := idle.duplicate() as StyleBoxFlat
	lit.bg_color = Color(1, 1, 1, 0.09)
	lit.border_width_left = 3
	lit.border_color = ACCENT
	lit.content_margin_left = 26
	var down := lit.duplicate() as StyleBoxFlat
	down.bg_color = Color(1, 1, 1, 0.16)
	b.add_theme_stylebox_override("normal", idle)
	b.add_theme_stylebox_override("disabled", idle)
	b.add_theme_stylebox_override("hover", lit)
	b.add_theme_stylebox_override("focus", lit)
	b.add_theme_stylebox_override("pressed", down)
	b.add_theme_stylebox_override("hover_pressed", down)
	b.mouse_entered.connect(func():
		if not b.disabled:
			b.grab_focus()
			menu_sound("ui_hover", -14.0))
	if label == "Back": b.pressed.connect(func(): menu_sound("ui_back", -8.0))
	elif label != "": b.pressed.connect(func(): menu_sound("ui_click", -8.0))
	b.pressed.connect(callback)
	if hint != "":
		var h := text_label(hint, 13, WARM if label == "Continue" else Color(1, 1, 1, 0.5), 400, 1)
		h.position = Vector2(18, 36)
		b.add_child(h)
	column.add_child(b)
	return b

func slider_row(label: String, key: String, lo: float, hi: float, step: float, percent: bool) -> void:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(380, 40)
	var name_label := text_label(label, 18, Color(1, 1, 1, 0.88), 500, 0)
	name_label.custom_minimum_size.x = 170
	row.add_child(name_label)
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = float(GameSettings.get_value(key))
	s.custom_minimum_size = Vector2(150, 30)
	s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var track := StyleBoxFlat.new()
	track.bg_color = Color(1, 1, 1, 0.18)
	track.content_margin_top = 2
	track.content_margin_bottom = 2
	track.set_corner_radius_all(2)
	var fill := track.duplicate() as StyleBoxFlat
	fill.bg_color = ACCENT
	s.add_theme_stylebox_override("slider", track)
	s.add_theme_stylebox_override("grabber_area", fill)
	s.add_theme_stylebox_override("grabber_area_highlight", fill)
	row.add_child(s)
	var value := text_label("", 15, WARM, 500, 0)
	value.custom_minimum_size.x = 52
	value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(value)
	var show_value := func(v: float) -> void:
		value.text = "%d%%" % roundi(v * 100.0) if percent else ("%d°" % roundi(v) if key == "fov" else ("%.1f m" % v if key == "camera_distance" else "%.2f×" % v))
	show_value.call(s.value)
	s.value_changed.connect(func(v: float) -> void:
		show_value.call(v)
		GameSettings.set_value(key, v)
		chosen.emit("settings_changed"))
	column.add_child(row)

func toggle_row(label: String, key: String) -> void:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(380, 40)
	var name_label := text_label(label, 18, Color(1, 1, 1, 0.88), 500, 0)
	name_label.custom_minimum_size.x = 170
	row.add_child(name_label)
	var c := CheckButton.new()
	c.button_pressed = bool(GameSettings.get_value(key))
	c.focus_mode = Control.FOCUS_ALL
	c.toggled.connect(func(on: bool) -> void:
		GameSettings.set_value(key, on)
		chosen.emit("settings_changed"))
	row.add_child(c)
	column.add_child(row)

## Which city the game builds (CedarNeighborhood.chosen_city): Port Halden or the classic city.
## Takes effect the next time the game starts.
func city_row() -> void:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(380, 40)
	var name_label := text_label("Port Halden city (restart)", 18, Color(1, 1, 1, 0.88), 500, 0)
	name_label.custom_minimum_size.x = 170
	row.add_child(name_label)
	var c := CheckButton.new()
	c.button_pressed = str(GameSettings.get_value("city")) == "port_halden"
	c.focus_mode = Control.FOCUS_ALL
	c.toggled.connect(func(on: bool) -> void:
		GameSettings.set_value("city", "port_halden" if on else "classic")
		chosen.emit("settings_changed"))
	row.add_child(c)
	column.add_child(row)

## Which Port Halden build (GameSettings city_build): the new Mert Road Studio streets (roads only) or the full city
## with buildings. Takes effect the next time the game starts.
func city_build_row() -> void:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(380, 40)
	var name_label := text_label("New streets, roads only (restart)", 18, Color(1, 1, 1, 0.88), 500, 0)
	name_label.custom_minimum_size.x = 170
	row.add_child(name_label)
	var c := CheckButton.new()
	c.button_pressed = str(GameSettings.get_value("city_build")) == "roads"
	c.focus_mode = Control.FOCUS_ALL
	c.toggled.connect(func(on: bool) -> void:
		GameSettings.set_value("city_build", "roads" if on else "full")
		chosen.emit("settings_changed"))
	row.add_child(c)
	column.add_child(row)

# --- The collage -----------------------------------------------------------------------

func build_collage() -> void:
	collage = Control.new()
	collage.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	collage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.add_child(collage)
	tracker()
	photo("pickup", Vector2(700, 404), Vector2(224, 126), -5.5, "12:41  ·  Pickup  ·  KE-221")
	photo("ride", Vector2(938, 318), Vector2(236, 133), 4.0, "12:48  ·  On the way")
	photo("delivery", Vector2(922, 486), Vector2(288, 162), -2.0, "12:56  ·  Delivered to Elif K.  ★★★★★")
	stamp = text_label("DELIVERED ✓", 22, Color("e8fff4"), 700, 3)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.09, 0.45, 0.31, 0.88)
	sb.set_border_width_all(2)
	sb.border_color = Color("bff5dc")
	sb.set_corner_radius_all(4)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 2
	sb.content_margin_bottom = 2
	stamp.add_theme_stylebox_override("normal", sb)
	stamp.position = Vector2(150, 18)
	stamp.rotation = deg_to_rad(-9)
	stamp.modulate.a = 0.0
	tiles[2].add_child(stamp)

## A white-bordered print with a caption, slightly rotated.
func photo(key: String, at: Vector2, picture: Vector2, degrees: float, caption: String) -> void:
	var frame := Panel.new()
	var border := 9.0
	frame.size = picture + Vector2(border * 2, border + 36)
	frame.position = at
	frame.pivot_offset = frame.size * 0.5
	frame.rotation = deg_to_rad(degrees)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color("f6f3ec")
	sb.set_corner_radius_all(3)
	sb.shadow_color = Color(0, 0, 0, 0.45)
	sb.shadow_size = 14
	sb.shadow_offset = Vector2(3, 6)
	frame.add_theme_stylebox_override("panel", sb)
	var pic := TextureRect.new()
	pic.texture = still(key)
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pic.position = Vector2(border, border)
	pic.size = picture
	pic.clip_contents = true
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(pic)
	var cap := Label.new()
	cap.text = caption
	cap.add_theme_font_override("font", font(500, 0))
	cap.add_theme_font_size_override("font_size", 13)
	cap.add_theme_color_override("font_color", Color("3a3f44"))
	cap.position = Vector2(border + 2, border + picture.y + 7)
	frame.add_child(cap)
	collage.add_child(frame)
	tiles.append(frame)
	tile_base.append(at)

## A glassy order tracker: Picked up → On the way → Delivered, with a courier dot running along.
func tracker() -> void:
	var card := PanelContainer.new()
	card.position = Vector2(704, 300)
	card.custom_minimum_size = Vector2(212, 0)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.03, 0.06, 0.07, 0.72)
	sb.set_corner_radius_all(10)
	sb.border_color = Color(1, 1, 1, 0.16)
	sb.set_border_width_all(1)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 10
	sb.content_margin_bottom = 12
	card.add_theme_stylebox_override("panel", sb)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	collage.add_child(card)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	card.add_child(col)
	col.add_child(text_label("ORDER KE-221  ·  ELIF KAYA", 11, ACCENT, 600, 2))
	var line := Control.new()
	line.custom_minimum_size = Vector2(184, 14)
	col.add_child(line)
	var rail := ColorRect.new()
	rail.color = Color(1, 1, 1, 0.2)
	rail.position = Vector2(4, 6)
	rail.size = Vector2(176, 2)
	line.add_child(rail)
	tracker_dot = Panel.new()
	var dot := StyleBoxFlat.new()
	dot.bg_color = ACCENT
	dot.set_corner_radius_all(6)
	dot.shadow_color = Color(ACCENT, 0.6)
	dot.shadow_size = 6
	tracker_dot.add_theme_stylebox_override("panel", dot)
	tracker_dot.size = Vector2(12, 12)
	tracker_dot.position = Vector2(0, 1)
	line.add_child(tracker_dot)
	var steps := HBoxContainer.new()
	steps.add_theme_constant_override("separation", 0)
	col.add_child(steps)
	for i in range(3):
		var s := text_label(["Picked up", "On the way", "Delivered"][i], 12, Color(1, 1, 1, 0.5), 500, 0)
		s.custom_minimum_size.x = 62
		s.horizontal_alignment = [HORIZONTAL_ALIGNMENT_LEFT, HORIZONTAL_ALIGNMENT_CENTER, HORIZONTAL_ALIGNMENT_RIGHT][i]
		steps.add_child(s)
		tracker_steps.append(s)

func _process(delta: float) -> void:
	if not visible: return
	t += delta
	if _toast_time > 0.0:
		_toast_time -= delta
		toast.modulate.a = clampf(_toast_time / 0.6, 0.0, 1.0)
	if not art.visible: return
	# Ken Burns: a slow push in towards downtown and back over 50 s.
	var k := 0.5 - 0.5 * cos(t * TAU / 50.0)
	hero.pivot_offset = hero.size * Vector2(0.64 - 0.06 * k, 0.42)
	hero.scale = Vector2.ONE * (1.03 + 0.07 * k)
	# Prints float gently.
	for i in range(tiles.size()):
		tiles[i].position = tile_base[i] + Vector2(0, sin(t * 0.7 + i * 1.9) * 3.0)
	# Tracker: dot runs pickup → ride → delivered, the matching print lifts, then the stamp lands.
	var p := fmod(t, CYCLE) / CYCLE
	var run := clampf(p / 0.72, 0.0, 1.0)
	var eased := run * run * (3.0 - 2.0 * run)
	tracker_dot.position.x = 172.0 * eased
	var step := 0 if eased < 0.3 else (1 if eased < 0.97 else 2)
	for i in range(3):
		var on := i <= step
		tracker_steps[i].add_theme_color_override("font_color", (ACCENT if i == step else Color(1, 1, 1, 0.8)) if on else Color(1, 1, 1, 0.4))
		var lift := 1.045 if i == step else 1.0
		tiles[i].scale = tiles[i].scale.lerp(Vector2.ONE * lift, minf(1.0, delta * 5.0))
		tiles[i].z_index = 2 if i == step else 0
	if step == 2 and not _stamp_shown:
		_stamp_shown = true
		stamp.scale = Vector2.ONE * 1.7
		stamp.pivot_offset = stamp.size * 0.5
		var tw := create_tween().set_parallel()
		tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.tween_property(stamp, "scale", Vector2.ONE, 0.35)
		tw.tween_property(stamp, "modulate:a", 1.0, 0.2)
	elif step < 2 and _stamp_shown:
		_stamp_shown = false
		create_tween().tween_property(stamp, "modulate:a", 0.0, 0.3)

## Birds crossing the sky: small flocks in loose V formation and a few singles, flapping and
## gliding, drawn as two-stroke silhouettes.
class Flock extends Control:
	var birds: Array[Dictionary] = []
	var clock := 0.0
	var next_flock := 1.0
	var next_single := 4.0
	var rng := RandomNumberGenerator.new()

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		process_mode = Node.PROCESS_MODE_ALWAYS
		rng.randomize()
		spawn_flock(0.55)

	func spawn_flock(progress := 0.0) -> void:
		var count := rng.randi_range(4, 8)
		var dir := -1.0 if rng.randf() < 0.7 else 1.0
		var w := maxf(size.x, 1280.0)
		var start := Vector2(w + 60.0 if dir < 0 else -60.0, rng.randf_range(60.0, 230.0))
		start.x = lerpf(start.x, w * 0.5, progress)
		var speed := rng.randf_range(34.0, 52.0)
		var depth := rng.randf_range(0.75, 1.15)
		for i in range(count):
			var rank := int((i + 1) / 2.0)
			var arm := -1.0 if i % 2 == 0 else 1.0
			var offset := Vector2(-dir * rank * 24.0, arm * rank * 13.0) * depth if i > 0 else Vector2.ZERO
			birds.append({"pos": start + offset + Vector2(rng.randf_range(-4, 4), rng.randf_range(-3, 3)), "vel": Vector2(dir * speed, rng.randf_range(-2.0, 2.0)),
				"size": depth * rng.randf_range(0.85, 1.1), "phase": rng.randf() * TAU, "flap": rng.randf_range(7.0, 9.5)})

	func spawn_single() -> void:
		var dir := -1.0 if rng.randf() < 0.5 else 1.0
		var w := maxf(size.x, 1280.0)
		birds.append({"pos": Vector2(w + 30.0 if dir < 0 else -30.0, rng.randf_range(40.0, 320.0)), "vel": Vector2(dir * rng.randf_range(55.0, 80.0), rng.randf_range(-6.0, 6.0)),
			"size": rng.randf_range(0.55, 0.8), "phase": rng.randf() * TAU, "flap": rng.randf_range(9.0, 12.0)})

	func _process(delta: float) -> void:
		if not is_visible_in_tree(): return
		clock += delta
		next_flock -= delta
		next_single -= delta
		if next_flock <= 0.0:
			spawn_flock()
			next_flock = rng.randf_range(14.0, 22.0)
		if next_single <= 0.0:
			spawn_single()
			next_single = rng.randf_range(5.0, 11.0)
		var w := maxf(size.x, 1280.0)
		for i in range(birds.size() - 1, -1, -1):
			var b: Dictionary = birds[i]
			var p: Vector2 = b.pos
			var v: Vector2 = b.vel
			p += v * delta + Vector2(0, sin(clock * 1.3 + float(b.phase)) * 4.0 * delta)
			b.pos = p
			if p.x < -120.0 or p.x > w + 120.0: birds.remove_at(i)
		queue_redraw()

	func _draw() -> void:
		var ink := Color(0.07, 0.08, 0.1, 0.82)
		for b: Dictionary in birds:
			var p: Vector2 = b.pos
			var s := float(b.size)
			var phase := float(b.phase)
			# Flap, with stretches of gliding.
			var glide := 0.5 + 0.5 * sin(clock * 0.45 + phase)
			var wing := sin(clock * float(b.flap) + phase) * lerpf(1.0, 0.18, smoothstep(0.55, 0.9, glide))
			var span := 10.0 * s
			var tip := -wing * span * 0.6
			var pts := PackedVector2Array([p + Vector2(-span, tip + 1.5 * s), p + Vector2(-span * 0.45, tip * 0.45 - 1.6 * s), p,
				p + Vector2(span * 0.45, tip * 0.45 - 1.6 * s), p + Vector2(span, tip + 1.5 * s)])
			draw_polyline(pts, ink, maxf(1.2, 1.9 * s), true)
			draw_circle(p + Vector2(0, 0.4 * s), 1.4 * s, ink)
