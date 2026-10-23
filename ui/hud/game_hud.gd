class_name GameHud
extends CanvasLayer
## The in-game HUD (HudStyle): left column (street, objective, order chip, training card), right
## column (clock, date and weather, wallet, needs; the package name tag under it), bottom left
## (backpack line, minimap, route distance), bottom centre (interaction prompt over a context-aware
## controls bar), bottom right (riding speed), the crosshair, toasts, the photo flash, the menu
## shade and modal shell, and the 3D route marker over the current goal.
##
## GameApp owns the game state; the HUD only reads it: refresh() rewrites the texts (on
## session.changed and every frame), frame() runs the toast timer and lays the blocks out.

const STATUS_WIDTH := 248.0
const MINIMAP_SIZE := 148.0
const NOTICE_MAX := 460.0

var game: GameApp
## The interaction prompt as "[E / Click]  Take ..."; drawn as key caps + text in prompt_bar.
var prompt_text := ""
var notification_time := 0.0

var gameplay_ui: Control
var hud_stack: VBoxContainer
var street_label: Label
var objective: Label
var order_plate: PanelContainer
var order_plate_name: Label
var order_plate_info: Label
var status_panel: PanelContainer
var clock_label: Label
var calendar_label: Label
var weather_label: Label
var wallet_label: Label
var need_bars: Dictionary = {}
var supplies_row: HBoxContainer
var minimap: Control
var nav_pill: PanelContainer
var navigation_label: Label
var bag_chip: PanelContainer
var bag_keys: HBoxContainer
var bag_head: Label
var bag_label: Label
var prompt_bar: PanelContainer
var prompt_row: HBoxContainer
var controls_bar: PanelContainer
var controls_row: HBoxContainer
var speed_panel: PanelContainer
var speed_label: Label
var crosshair: Control
var notice: Label
var menu_shade: ColorRect
var modal: PanelContainer
var modal_body: VBoxContainer
var receipt_panel: PanelContainer
var receipt_head: Label
var receipt_name: Label
var receipt_label: Label
var route_marker: Label3D
var _flash: ColorRect
var _prompt_shown := "~"
var _controls_shown := ""
var _controls_age := 0.0
var _bag_key_shown := "~"
var _supplies_shown := "~"

func setup(app: GameApp) -> void:
	game = app
	build()
	route_marker = Label3D.new()
	route_marker.font_size = 40
	route_marker.pixel_size = 0.012
	route_marker.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	route_marker.no_depth_test = true
	route_marker.modulate = Color("b6f3d1")
	route_marker.font = HudStyle.font(HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	route_marker.outline_size = 10
	game.add_child(route_marker)
	_flash = ColorRect.new()
	_flash.color = Color(1, 1, 1, 0)
	_flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_flash)

## The minimap follows the current session (new game, loaded save).
func use_session(session: DeliverySession) -> void:
	minimap.session = session
	if modal != null: modal.set("session", session)

# --- Building ---------------------------------------------------------------------------------

func build() -> void:
	gameplay_ui = Control.new()
	gameplay_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	gameplay_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gameplay_ui.theme = HudStyle.theme()
	add_child(gameplay_ui)
	build_left_column()
	build_status()
	build_bottom()
	# Third person: a small dot where the interaction ray points.
	crosshair = Reticle.new()
	crosshair.size = Vector2(12, 12)
	crosshair.position = Vector2(634, 354)
	gameplay_ui.add_child(crosshair)
	build_notice()
	menu_shade = ColorRect.new()
	menu_shade.color = Color(0.015, 0.025, 0.035, 0.66)
	menu_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(menu_shade)
	modal = preload("res://ui/phone_shell.gd").new()
	modal.set("session", game.session)
	modal.position = Vector2(720, 28)
	modal.custom_minimum_size = Vector2(525, 620)
	modal.add_theme_stylebox_override("panel", HudStyle.card(Color("10252b")))
	modal.theme = HudStyle.theme()
	add_child(modal)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	modal.add_child(scroll)
	modal_body = VBoxContainer.new()
	modal_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_body.add_theme_constant_override("separation", 12)
	scroll.add_child(modal_body)

## Left column: street, objective, order chip, training card (TutorialDirector adds it). A VBox,
## so the blocks stack whatever their text and never overlap.
func build_left_column() -> void:
	var m := HudStyle.MARGIN
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

## Right column: clock, date and weather, wallet; energy / food / water / WC meters; supplies.
func build_status() -> void:
	var m := HudStyle.MARGIN
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

## Bottom: backpack line, minimap and route distance (left), the interaction prompt over the
## controls bar (centre), riding speed (right).
func build_bottom() -> void:
	minimap = preload("res://ui/minimap.gd").new()
	minimap.player = game.player
	minimap.session = game.session
	minimap.world = game.world
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

## Toasts: a compact pill at the top centre, between the two columns.
func build_notice() -> void:
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

## The crosshair: a dot with a dark ring, readable on any background.
class Reticle extends Control:
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
	func _draw() -> void:
		var c := size * 0.5
		draw_circle(c, 3.2, Color(0, 0, 0, 0.45))
		draw_circle(c, 2.0, Color(1, 1, 1, 0.92))

# --- Toasts and flashes -----------------------------------------------------------------------

func notify(message: String) -> void:
	notice.text = message
	notification_time = 7.0
	notice.visible = true

## Hides the toast at once (the phone shows its own).
func clear_notice() -> void:
	notice.hide()
	notification_time = 0.0

## A coloured pulse on the notice text (wrong package).
func flash_notice(colour: Color) -> void:
	notice.add_theme_color_override("font_color", colour)
	var tw := create_tween()
	tw.tween_interval(2.5)
	tw.tween_callback(func() -> void: notice.add_theme_color_override("font_color", HudStyle.INK))

## The proof-photo flash (leave at door).
func flash_photo() -> void:
	_flash.color.a = 0.85
	create_tween().tween_property(_flash, "color:a", 0.0, 0.45)

# --- Per frame --------------------------------------------------------------------------------

## Crosshair and bar visibility (also while paused: menus hide the bars).
func frame_always() -> void:
	var player := game.player
	if crosshair and player.view:
		crosshair.position = player.view.reticle - crosshair.size * 0.5
		crosshair.visible = not game.sequence.running and game.mode == ""
	# Phone, bag, menus: their own instructions replace the prompt and the controls bar.
	if game.mode != "" and controls_bar:
		controls_bar.visible = false
		prompt_bar.visible = false

## Toast timer, then the texts and the layout.
func frame(delta: float) -> void:
	notification_time -= delta
	notice.visible = notification_time > 0
	refresh()
	layout(delta)

## Display name for a key ("Escape" -> "Esc").
func key_name(action: String) -> String:
	var k := game.binding(action)
	return {"Escape": "Esc", "Ctrl": "Ctrl", "Shift": "Shift"}.get(k, k)

## Positions of the anchored HUD blocks for the current canvas size, the prompt / controls
## rendering and the controls bar fade (cheap: only moves controls; key caps are rebuilt only when
## their text changes).
func layout(delta: float) -> void:
	var view := gameplay_ui.size
	var m := HudStyle.MARGIN
	var player := game.player
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
	var tutorial := game.tutorial
	if tutorial and tutorial.card and tutorial.card.visible:
		var hint: Label = tutorial.card.hint
		if hud_stack.position.y + hud_stack.size.y > floor_y and hint.max_lines_visible > 1: hint.max_lines_visible -= 1
		elif hud_stack.position.y + hud_stack.size.y + 16 < floor_y and hint.max_lines_visible < 4: hint.max_lines_visible += 1
	hud_stack.reset_size()
	if prompt_text != _prompt_shown:
		_prompt_shown = prompt_text
		HudStyle.fill_keys(prompt_row, HudStyle.parse_keys(prompt_text), HudStyle.PROMPT, HudStyle.INK, HudStyle.CAPTION, HudStyle.SEMIBOLD)
		prompt_bar.reset_size()
	prompt_bar.visible = prompt_text != "" and game.mode == ""
	controls_bar.visible = game.mode == ""
	# Controls bar: what the keys do right now; quiet, and fades further once you're moving.
	var mounted := player.mounted
	var car := mounted and ShopCatalog.is_car(game.session.active_vehicle)
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

# --- Texts ------------------------------------------------------------------------------------

## Objective, route marker, order chip, backpack line, status (clock, weather, wallet, needs,
## supplies) and the route distance.
func refresh() -> void:
	if objective == null:
		return
	var session := game.session
	var player := game.player
	var world := game.world
	var state: String = session.order.get("state", "")
	street_label.text = StreetNames.describe(player.position).to_upper()
	objective.text = ("Online · requests arrive automatically" if session.online else "Offline · open your phone to go online")
	if session.online and session.demand().begins_with("Kitchen closed"):
		objective.text = "Kitchen closed · opens 08:00"
	route_marker.visible = false
	var who := str(session.order.get("customer", ""))
	var address_short: String = DeliverySession.ADDRESSES[int(session.order.get("address", 0))].replace(" Avenue", " Ave").replace(" Street", " St")
	if state == "OFFERED":
		objective.text = "New offer: %s · open phone (%s)" % [who, game.binding("phone")]
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
	refresh_bag_line(state, who)
	refresh_status()
	refresh_navigation(state)

## The order chip under the objective while an order is active (the training card shows the
## same chip itself): "ORDER FOR / ELIF KAYA / CE-012 · Food bag · medium".
func update_order_plate(state: String) -> void:
	var session := game.session
	var plate_on: bool = state in DeliverySession.ACTIVE and game.tutorial != null and not game.tutorial.active()
	order_plate.visible = plate_on
	if plate_on:
		order_plate_name.text = str(session.order.get("customer", "")).to_upper()
		order_plate_info.text = "%s  ·  %s" % [session.order.get("ticket", ""), OrderDetails.package_label(str(session.order.get("kind", "bag")), session.order.get("items", []))]

## Backpack line: [key] HEAD  what's in it / what you're doing with the order.
func refresh_bag_line(state: String, who: String) -> void:
	var session := game.session
	var bag_key := ""
	var bag_title := ""
	var bag_text := ""
	if session.has_bag():
		bag_key = game.binding("bag")
		bag_title = "BACKPACK"
		bag_text = ("%s's %s · %s" % [who, str(OrderDetails.KIND_NAMES.get(session.order.get("kind", "bag"), "order")).to_lower(), str(OrderDetails.SLOT_NAMES.get(session.order.get("slot", ""), "bag")).to_lower()]) if state == "CARRYING" else "Empty · look inside"
	if game.sequence != null and game.sequence.running:
		bag_key = ""
		bag_title = str({"pack": "PACKING", "leave": "LEAVING AT DOOR", "meet": "HANDING OVER"}.get(game.sequence.kind, "ORDER"))
		bag_text = "%s's order…" % who
	elif state == "IN_HAND":
		bag_key = game.use_hint() if session.has_bag() else ""
		bag_title = "HOLDING"
		bag_text = "%s's order · %s" % [who, "pack it" if session.has_bag() else "no bag: carry it by hand"]
	elif state == "DROPPED":
		bag_key = game.use_hint()
		bag_title = "ON THE GROUND"
		bag_text = "%s's order · pick it up" % who
	bag_chip.visible = bag_title != ""
	if bag_key != _bag_key_shown:
		_bag_key_shown = bag_key
		HudStyle.fill_keys(bag_keys, HudStyle.parse_keys(("[%s]" % bag_key) if bag_key != "" else ""), HudStyle.SMALL, HudStyle.INK, HudStyle.CAPTION)
		bag_keys.visible = bag_key != ""
	bag_head.text = bag_title
	bag_label.text = bag_text

const WEEKDAYS := ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
const MONTHS := ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

## Status: clock, date · day, weather, wallet, needs, supplies.
func refresh_status() -> void:
	var session := game.session
	var day := int(session.calendar_minutes / 1440) + 1
	var date := session.calendar()
	clock_label.text = "%02d:%02d" % [int(date.hour), int(date.minute)]
	calendar_label.text = "%s %d %s  ·  DAY %d" % [WEEKDAYS[int(date.weekday)], int(date.day), MONTHS[int(date.month) - 1], day]
	weather_label.text = game.world.weather.describe().replace("  ", " · ").to_upper() if game.world.weather != null else ("NIGHT" if session.hour() < 6 or session.hour() >= 20 else "DAYLIGHT")
	wallet_label.text = DeliverySession.money(session.wallet)
	set_need("ENERGY", session.energy / 100.0, false)
	set_need("FOOD", session.hunger / 100.0, false)
	set_need("WATER", session.hydration / 100.0, false)
	set_need("WC", session.bladder / 100.0, true)
	var water := int(session.supplies.get("water_bottle", 0))
	var snack := int(session.supplies.get("energy_bar", 0))
	var supplies := ("[%s] Water ×%d  [%s] Energy bar ×%d" % [game.binding("use_water"), water, game.binding("use_snack"), snack]) if water + snack > 0 else ""
	if supplies != _supplies_shown:
		_supplies_shown = supplies
		HudStyle.fill_keys(supplies_row, HudStyle.parse_keys(supplies), HudStyle.CAPTION, HudStyle.INK_SOFT, HudStyle.MICRO)
		supplies_row.visible = supplies != ""
		status_panel.reset_size()

## One needs meter: full is good (energy, food, water) or bad (WC).
func set_need(need: String, value: float, high_is_bad: bool) -> void:
	var bar: ProgressBar = need_bars.get(need)
	if bar == null: return
	bar.value = clampf(value, 0.0, 1.0)
	var level := 1.0 - value if high_is_bad else value
	HudStyle.set_meter_colour(bar, HudStyle.ACCENT if level > 0.35 else (HudStyle.AMBER if level > 0.15 else HudStyle.DANGER))

## Route distance pill under the minimap (and the marker over a destination chosen on the map).
func refresh_navigation(state: String) -> void:
	var session := game.session
	var player := game.player
	if state == "OFFERED":
		navigation_label.text = "New request · %s to review" % game.binding("phone")
	elif state == "ACCEPTED":
		navigation_label.text = "%d m · %s" % [int(CityCatalog.distance(minimap.route_points())), session.restaurant_name()]
	elif state == "DROPPED":
		navigation_label.text = "%d m · your package" % int(player.position.distance_to(session.dropped_position()))
	elif state in ["CARRYING", "IN_HAND"]:
		navigation_label.text = "%d m · %s" % [int(CityCatalog.distance(minimap.route_points())), DeliverySession.ADDRESSES[int(session.order.address)]]
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

# --- Package name tag -------------------------------------------------------------------------

## The package's name tag, read before you take it: a paper card in the right column, under the
## status panel. Who it is for and the order code big, the printed receipt under it.
func show_name_tag(target: Dictionary) -> void:
	if receipt_panel == null: build_name_tag()
	var showing: bool = not target.is_empty() and target.id == "package"
	receipt_panel.visible = showing
	if showing:
		var info: Dictionary = target.node.get_meta("package")
		var name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(str(info.restaurant)))]
		receipt_head.text = "NAME TAG  ·  " + OrderDetails.package_label(str(info.kind), info.get("items", [])).to_upper()
		receipt_name.text = "%s\n%s" % [str(info.customer).to_upper(), info.ticket]
		receipt_label.text = OrderDetails.receipt_text(info, name, DeliverySession.ADDRESSES[int(info.get("address", 0))], game.session.calendar_minutes)
		receipt_panel.reset_size()
		receipt_panel.position = Vector2(gameplay_ui.size.x - HudStyle.MARGIN - receipt_panel.size.x, status_panel.position.y + status_panel.size.y + HudStyle.GAP)

func build_name_tag() -> void:
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
