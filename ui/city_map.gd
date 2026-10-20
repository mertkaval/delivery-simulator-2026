extends Control
## Full-screen city map (M while on foot). Roads, buildings and every place from
## CityNavigation.places(): restaurants, stores, parks, public buildings, bus stops, houses.
## Drag to pan, mouse wheel to zoom, click a symbol (or a name in the side list) to set it as
## the navigation destination; the route is drawn along the roads.

signal destination_chosen(place: Dictionary)
signal closed

var player: Node3D
var world: Node
var places: Array[Dictionary] = []
var zoom := 1.0          ## pixels per metre
var centre := Vector3.ZERO
var hovered := -1
var selected := -1
var dragging := false
var drag_moved := 0.0
var filter := "all"
var list_box: VBoxContainer
var info: Label
var route_preview := PackedVector3Array()

const PANEL_W := 330.0
const COLOURS := {
	"restaurant": Color("f0a640"), "store": Color("5aa7f0"), "park": Color("5fbf6a"), "public": Color("b9a6e8"),
	"hospital": Color("e2554f"), "school": Color("e8c84a"), "fire": Color("e0703a"), "bus": Color("3fb4c8"),
	"house": Color("9aa7a0"), "home": Color("ffd166"), "square": Color("d8b878")}
const TITLES := {"restaurant": "Restaurants", "store": "Stores", "park": "Parks", "public": "Public places",
	"hospital": "Hospital", "school": "School", "fire": "Fire station", "bus": "Bus stops", "house": "Delivery addresses",
	"home": "Home", "square": "Squares"}
const ORDER := ["home", "restaurant", "store", "public", "hospital", "school", "fire", "square", "park", "bus", "house"]

func open(p: Node3D, w: Node) -> void:
	player = p
	world = w
	places = CityNavigation.places(w)
	CityNavigation.prepare()
	centre = player.global_position
	zoom = 1.6
	selected = -1
	if not CityNavigation.target.is_empty():
		for i in range(places.size()):
			if places[i].name == CityNavigation.target.name: selected = i
	_update_preview()
	_build_panel()
	show()
	queue_redraw()

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var panel := PanelContainer.new()
	panel.position = Vector2(16, 16)
	panel.size = Vector2(PANEL_W, 688)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.04, 0.07, 0.085, 0.94)
	style.set_corner_radius_all(10)
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 12
	style.content_margin_bottom = 12
	panel.add_theme_stylebox_override("panel", style)
	add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	panel.add_child(column)
	var title := Label.new()
	title.text = "CITY MAP"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("e6efeb"))
	column.add_child(title)
	var filters := HFlowContainer.new()
	column.add_child(filters)
	for f in [["all", "All"], ["restaurant", "Food"], ["store", "Stores"], ["public", "Public"], ["park", "Parks"], ["house", "Houses"]]:
		var b := Button.new()
		b.text = f[1]
		b.toggle_mode = false
		b.add_theme_font_size_override("font_size", 13)
		b.pressed.connect(func(): filter = f[0]; _build_panel(); queue_redraw())
		filters.add_child(b)
	info = Label.new()
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_theme_font_size_override("font_size", 14)
	info.add_theme_color_override("font_color", Color("b6f3d1"))
	column.add_child(info)
	var actions := HBoxContainer.new()
	column.add_child(actions)
	var go := Button.new()
	go.text = "Navigate here"
	go.pressed.connect(func(): if selected >= 0: _choose(selected))
	actions.add_child(go)
	var clear := Button.new()
	clear.text = "Clear route"
	clear.pressed.connect(func():
		CityNavigation.target = {}
		selected = -1
		_update_preview()
		_update_info()
		queue_redraw())
	actions.add_child(clear)
	var close := Button.new()
	close.text = "Close (M)"
	close.pressed.connect(func(): closed.emit())
	actions.add_child(close)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroll)
	list_box = VBoxContainer.new()
	list_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list_box)

func _build_panel() -> void:
	for c in list_box.get_children(): c.queue_free()
	for kind in ORDER:
		if filter != "all" and kind != filter and not (filter == "public" and kind in ["hospital", "school", "fire", "square", "bus", "home"]): continue
		var items: Array[int] = []
		for i in range(places.size()):
			if places[i].kind == kind: items.append(i)
		if items.is_empty(): continue
		var header := Label.new()
		header.text = TITLES[kind].to_upper()
		header.add_theme_font_size_override("font_size", 12)
		header.add_theme_color_override("font_color", COLOURS[kind])
		list_box.add_child(header)
		items.sort_custom(func(a: int, b: int) -> bool: return _dist(a) < _dist(b))
		for i in items:
			var b := Button.new()
			b.text = "%s   %s" % [places[i].name, _distance_text(i)]
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.add_theme_font_size_override("font_size", 13)
			b.flat = true
			b.pressed.connect(func(): _select(i, true))
			list_box.add_child(b)
	_update_info()

func _dist(i: int) -> float:
	return player.global_position.distance_to(places[i].at)

func _distance_text(i: int) -> String:
	var d := _dist(i)
	return "%d m" % int(d) if d < 1000 else "%.1f km" % (d / 1000.0)

func to_screen(p: Vector3) -> Vector2:
	return size * 0.5 + Vector2(PANEL_W * 0.5, 0) + Vector2(p.x - centre.x, p.z - centre.z) * zoom

func to_world(s: Vector2) -> Vector3:
	var d := (s - size * 0.5 - Vector2(PANEL_W * 0.5, 0)) / zoom
	return Vector3(centre.x + d.x, 0, centre.z + d.y)

func _select(i: int, focus: bool) -> void:
	selected = i
	if focus: centre = places[i].at
	_update_preview()
	_update_info()
	queue_redraw()

func _choose(i: int) -> void:
	selected = i
	CityNavigation.target = places[i]
	_update_preview()
	destination_chosen.emit(places[i])

func _update_preview() -> void:
	route_preview = CityNavigation.route(player.global_position, places[selected].at) if selected >= 0 else PackedVector3Array()

func _update_info() -> void:
	if info == null: return
	if selected < 0:
		info.text = "Click a symbol or a name to see the way.\nDrag to move · wheel to zoom." + ("\nNavigating to: " + CityNavigation.target.name if not CityNavigation.target.is_empty() else "")
		return
	var p: Dictionary = places[selected]
	var length := 0.0
	for k in range(1, route_preview.size()): length += route_preview[k - 1].distance_to(route_preview[k])
	info.text = "%s\n%s · %s · %d m by road (~%d min walk)\n%s" % [p.name, TITLES[p.kind], p.detail, int(length), maxi(1, int(length / 1.4 / 60.0)),
		"✓ Navigation active" if CityNavigation.target.get("name", "") == p.name else "Press “Navigate here” or double-click"]

func _pick(pos: Vector2) -> int:
	var best := -1
	var best_d := 14.0
	for i in range(places.size()):
		if not _visible_kind(places[i].kind): continue
		var d := to_screen(places[i].at).distance_to(pos)
		if d < best_d:
			best_d = d
			best = i
	return best

func _visible_kind(kind: String) -> bool:
	if filter == "all": return kind != "house" or zoom > 1.2
	if filter == "public": return kind in ["public", "hospital", "school", "fire", "square", "bus", "home"]
	return kind == filter

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP or event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			if event.pressed:
				var before := to_world(event.position)
				zoom = clampf(zoom * (1.18 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.18), 0.35, 8.0)
				var after := to_world(event.position)
				centre += before - after
				queue_redraw()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging = true
				drag_moved = 0.0
				if event.double_click:
					var hit := _pick(event.position)
					if hit >= 0: _choose(hit)
			else:
				dragging = false
				if drag_moved < 6.0:
					var hit := _pick(event.position)
					if hit >= 0: _select(hit, false)
			accept_event()
	elif event is InputEventMouseMotion:
		if dragging:
			centre -= Vector3(event.relative.x, 0, event.relative.y) / zoom
			drag_moved += event.relative.length()
			queue_redraw()
		else:
			var h := _pick(event.position)
			if h != hovered:
				hovered = h
				queue_redraw()

func _road(a: Vector3, b: Vector3, width: float, colour: Color) -> void:
	draw_line(to_screen(a), to_screen(b), colour, maxf(1.5, width * zoom), true)

func _draw() -> void:
	if player == null: return
	draw_rect(Rect2(Vector2.ZERO, size), Color("1b2a26"))
	# Downtown and civic ground.
	var dt0 := to_screen(Vector3(120, 0, -246))
	var dt1 := to_screen(Vector3(630, 0, -690))
	draw_rect(Rect2(dt0, dt1 - dt0), Color("27322f"))
	var road := Color("3d4c52")
	for s in StreetNames.segments(): _road(Vector3(s.a.x, 0, s.a.y), Vector3(s.b.x, 0, s.b.y), s.half * 2.0, road)
	for x in CityCatalog.SIDE_ROADS: _road(Vector3(x, 0, -678), Vector3(x, 0, -258), 10, road)
	for path in CityCatalog.estate_roads():
		for i in range(1, path.size()): _road(path[i - 1], path[i], 8, road)
	for x in DowntownCatalog.STREET_X: _road(Vector3(x, 0, -258), Vector3(x, 0, -678), 14, road)
	for z in DowntownCatalog.STREET_Z: _road(Vector3(64, 0, z), Vector3(630, 0, z), 14, road)
	_road(Vector3(520, 0, -258), Vector3(520, 0, -678), 14, road)
	for site in CivicCampus.SITES: _road(Vector3(520, 0, site.at.z), site.at, 8, road)
	# Parks.
	for c in StreetNames.PARKS:
		var a := to_screen(Vector3(c.x - 10, 0, c.y - 16))
		var b := to_screen(Vector3(c.x + 10, 0, c.y + 16))
		draw_rect(Rect2(a, b - a), Color("2f5a37"))
	# Buildings: houses and kit buildings as blocks, downtown blocks.
	for lot in ResidentialLayout.lots():
		var r: Rect2 = ResidentialLayout.house_rect(lot)
		var a := to_screen(Vector3(r.position.x, 0, r.position.y))
		var b := to_screen(Vector3(r.end.x, 0, r.end.y))
		draw_rect(Rect2(a, b - a), Color("56625d"))
	for spec in CityLayout.buildings():
		var r: Rect2 = CityLayout.footprint(spec)
		var a := to_screen(Vector3(r.position.x, 0, r.position.y))
		var b := to_screen(Vector3(r.end.x, 0, r.end.y))
		draw_rect(Rect2(a, b - a), Color("6a6660"))
	for block in DowntownCatalog.blocks():
		var a := to_screen(Vector3(block.position.x + 4, 0, block.position.y + 4))
		var b := to_screen(Vector3(block.end.x - 4, 0, block.end.y - 4))
		draw_rect(Rect2(a, b - a), Color("5b5f66"))
	# Route preview.
	var route := route_preview if selected >= 0 else (CityNavigation.route(player.global_position, CityNavigation.target.at) if not CityNavigation.target.is_empty() else PackedVector3Array())
	for i in range(1, route.size()):
		draw_line(to_screen(route[i - 1]), to_screen(route[i]), Color(0.05, 0.1, 0.08), 7.0, true)
		draw_line(to_screen(route[i - 1]), to_screen(route[i]), Color("69ebbb"), 4.0, true)
	# Places.
	var font := ThemeDB.fallback_font
	var taken: Array[Rect2] = []
	var labels: Array[int] = []
	if selected >= 0: labels.append(selected)
	if hovered >= 0 and hovered != selected: labels.append(hovered)
	for i in range(places.size()):
		var p: Dictionary = places[i]
		if not _visible_kind(p.kind): continue
		var s := to_screen(p.at)
		if s.x < PANEL_W + 10 or s.x > size.x + 20 or s.y < -20 or s.y > size.y + 20: continue
		_icon(s, p.kind, i == selected or i == hovered)
		var show_label: bool = i == selected or i == hovered or p.kind in ["restaurant", "store", "hospital", "school", "fire", "home", "square"] or (p.kind in ["park", "public"] and zoom > 0.8) or zoom > 3.0
		if show_label and not i in labels: labels.append(i)
	# Labels: selected/hovered first, then the rest only where they do not collide.
	for i in labels:
		var text: String = places[i].name
		var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
		var at := to_screen(places[i].at) + Vector2(-w * 0.5, -15)
		var box := Rect2(at + Vector2(-4, -12), Vector2(w + 8, 16))
		var clash := false
		for r in taken:
			if r.intersects(box): clash = true
		if clash and i != selected and i != hovered: continue
		taken.append(box)
		draw_rect(box, Color(0, 0, 0, 0.6))
		draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color.WHITE if i != selected else Color("69ebbb"))
	# Player arrow.
	var c := to_screen(player.global_position)
	var arrow := PackedVector2Array()
	for q in [Vector2(0, -12), Vector2(8, 9), Vector2(0, 5), Vector2(-8, 9)]: arrow.append(c + q.rotated(-player.rotation.y))
	draw_colored_polygon(arrow, Color.WHITE)
	draw_polyline(arrow + PackedVector2Array([arrow[0]]), Color.BLACK, 1.5, true)
	draw_string(font, Vector2(size.x - 40, 40), "N ↑", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.WHITE)
	draw_string(font, Vector2(PANEL_W + 30, size.y - 18), "Drag: move   ·   Wheel: zoom   ·   Click: select   ·   Double-click: navigate   ·   M: close", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("c3d0ca"))

## Map symbols, drawn as vector icons so they stay sharp at every zoom.
func _icon(s: Vector2, kind: String, highlight: bool) -> void:
	var col: Color = COLOURS.get(kind, Color.WHITE)
	var r := 9.0 if kind != "house" else 5.0
	if highlight: draw_circle(s, r + 5, Color(1, 1, 1, 0.35))
	var dark := Color(0.08, 0.1, 0.1)
	match kind:
		"restaurant":
			draw_circle(s, r, col)
			draw_line(s + Vector2(-3, -5), s + Vector2(-3, 5), dark, 1.6)     # fork
			for dx in [-4.5, -3.0, -1.5]: draw_line(s + Vector2(dx, -5), s + Vector2(dx, -2), dark, 1.0)
			draw_line(s + Vector2(3, -5), s + Vector2(3, 5), dark, 1.6)       # knife
			draw_line(s + Vector2(3, -5), s + Vector2(4.5, -1), dark, 1.6)
		"store":
			draw_rect(Rect2(s - Vector2(r, r), Vector2(r, r) * 2), col)
			draw_rect(Rect2(s + Vector2(-4.5, -2), Vector2(9, 7)), dark)      # bag
			draw_arc(s + Vector2(0, -2), 3.0, PI, TAU, 8, dark, 1.4)
		"park":
			draw_circle(s, r, col)
			draw_colored_polygon(PackedVector2Array([s + Vector2(0, -6), s + Vector2(5, 3), s + Vector2(-5, 3)]), dark)
			draw_line(s + Vector2(0, 3), s + Vector2(0, 6), dark, 1.6)
		"hospital":
			draw_rect(Rect2(s - Vector2(r, r), Vector2(r, r) * 2), Color.WHITE)
			draw_rect(Rect2(s + Vector2(-1.8, -6), Vector2(3.6, 12)), col)
			draw_rect(Rect2(s + Vector2(-6, -1.8), Vector2(12, 3.6)), col)
		"school":
			draw_circle(s, r, col)
			draw_colored_polygon(PackedVector2Array([s + Vector2(-6, -1), s + Vector2(0, -5), s + Vector2(6, -1), s + Vector2(0, 3)]), dark)
			draw_line(s + Vector2(4, 0), s + Vector2(4, 5), dark, 1.2)
		"fire":
			draw_circle(s, r, col)
			draw_colored_polygon(PackedVector2Array([s + Vector2(0, -6), s + Vector2(4, 2), s + Vector2(0, 6), s + Vector2(-4, 2)]), Color("fff0b0"))
		"bus":
			draw_rect(Rect2(s - Vector2(7, 7), Vector2(14, 14)), col)
			draw_string(ThemeDB.fallback_font, s + Vector2(-4, 5), "B", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, dark)
		"public":
			draw_circle(s, r, col)
			draw_string(ThemeDB.fallback_font, s + Vector2(-6, 5), "WC", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, dark)
		"square":
			draw_circle(s, r, col)
			draw_rect(Rect2(s + Vector2(-2, -6), Vector2(4, 9)), dark)
			draw_rect(Rect2(s + Vector2(-5, 3), Vector2(10, 3)), dark)
		"home", "house":
			var h := r if kind == "house" else r + 1
			draw_colored_polygon(PackedVector2Array([s + Vector2(0, -h), s + Vector2(h, -0.1 * h), s + Vector2(h * 0.75, h), s + Vector2(-h * 0.75, h), s + Vector2(-h, -0.1 * h)]), col)
			if kind == "home": draw_rect(Rect2(s + Vector2(-2, 2), Vector2(4, 7)), dark)
