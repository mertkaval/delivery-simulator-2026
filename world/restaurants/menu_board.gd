class_name MenuBoard
extends RefCounted
## Readable restaurant menu boards: a dark board with a coloured frame, the restaurant name in
## large type, its specialty line, and every dish with a dotted leader to its price (dollars,
## the game's currency). High-contrast unshaded text sized to read from several metres.
## Used inside above the counter and outside beside the door.

static var _font: SystemFont
static var _board_mat: StandardMaterial3D
static var _frames: Dictionary = {}

static func font() -> SystemFont:
	if _font == null:
		_font = SystemFont.new()
		_font.font_names = PackedStringArray(["Segoe UI Semibold", "Segoe UI", "Arial", "Helvetica", "sans-serif"])
		_font.font_weight = 600
	return _font

## A board `size` (width x height, metres) whose front faces local +Z, origin at its centre.
static func build(restaurant_id: String, size: Vector2, accent: Color, title_override := "") -> Node3D:
	var root := Node3D.new()
	root.name = "MenuBoard"
	var entry: Array = RestaurantCatalog.entry(restaurant_id)
	var title: String = title_override if title_override != "" else (str(entry[1]) if not entry.is_empty() else CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(restaurant_id))])
	var subtitle: String = (str(entry[2]) + "  ·  " + str(entry[3])) if not entry.is_empty() else "FRESH · MADE TO ORDER"
	# Board and frame.
	if _board_mat == null:
		_board_mat = StandardMaterial3D.new()
		_board_mat.albedo_color = Color("16191b")
		_board_mat.roughness = 0.8
	var key := accent.to_html()
	if not _frames.has(key):
		var m := StandardMaterial3D.new()
		m.albedo_color = accent
		m.metallic = 0.4
		m.roughness = 0.35
		m.emission_enabled = true
		m.emission = accent
		m.emission_energy_multiplier = 0.25
		_frames[key] = m
	root.add_child(box(Vector3(size.x, size.y, 0.04), Vector3(0, 0, -0.02), _board_mat))
	var t := 0.045
	for y in [-1.0, 1.0]: root.add_child(box(Vector3(size.x + t * 2, t, 0.06), Vector3(0, y * (size.y + t) * 0.5, -0.01), _frames[key]))
	for x in [-1.0, 1.0]: root.add_child(box(Vector3(t, size.y, 0.06), Vector3(x * (size.x + t) * 0.5, 0, -0.01), _frames[key]))
	# Text: sized from the board height, then shrunk to fit the width (no line may overflow).
	var unit := size.y / 10.0
	var pad := size.x * 0.06
	var inner := size.x - pad * 2.0
	root.add_child(text(title.to_upper(), Vector3(0, size.y * 0.5 - unit * 1.3, 0.002), fit(title, unit * 1.5, inner), accent.lightened(0.45), HORIZONTAL_ALIGNMENT_CENTER, inner))
	# Neighbouring lines' label quads overlap: they alternate 2 / 3.5 mm off the board (they lay in
	# one plane and flickered where the quads cross).
	root.add_child(text(subtitle.to_upper(), Vector3(0, size.y * 0.5 - unit * 2.35, 0.0035), fit(subtitle, unit * 0.6, inner), Color("cfc6b2"), HORIZONTAL_ALIGNMENT_CENTER, inner))
	var dishes := OrderDetails.menu(restaurant_id)
	var row := unit * (6.0 / maxf(1.0, float(dishes.size())))
	var y0 := size.y * 0.5 - unit * 3.3
	var name_w := inner * 0.7
	var price_w := inner * 0.28
	var longest := ""
	for d in dishes: if str(d[0]).length() > longest.length(): longest = str(d[0])
	var dish_h := minf(fit(longest, unit * 0.85, name_w), row * 0.8)
	for i in range(dishes.size()):
		var y := y0 - row * (i + 0.5)
		var d: Array = dishes[i]
		var lift := 0.002 if i % 2 == 0 else 0.0035
		# Label3D anchors left-aligned text at its left edge and right-aligned at its right edge.
		root.add_child(text(str(d[0]), Vector3(-size.x * 0.5 + pad, y, lift), dish_h, Color("f4efe2"), HORIZONTAL_ALIGNMENT_LEFT, name_w))
		root.add_child(text(DeliverySession.money(int(d[1])), Vector3(size.x * 0.5 - pad, y, lift + 0.0015), dish_h, accent.lightened(0.55), HORIZONTAL_ALIGNMENT_RIGHT, price_w))
	root.add_child(text("ORDER AT THE COUNTER · COURIER PICKUP INSIDE", Vector3(0, -size.y * 0.5 + unit * 0.55, 0.0065), fit("ORDER AT THE COUNTER · COURIER PICKUP INSIDE", unit * 0.34, inner), Color("9a917f"), HORIZONTAL_ALIGNMENT_CENTER, inner))
	return root

## Text size (em, metres) for `s` to fit `width` metres: about 0.6 em per character.
static func fit(s: String, height: float, width: float) -> float:
	return minf(height, width / maxf(1.0, s.length() * 0.6))

## Label sized by world height of its capital letters (`height` metres).
static func text(s: String, at: Vector3, height: float, colour: Color, align: HorizontalAlignment, block_width: float) -> Label3D:
	var l := Label3D.new()
	l.text = s
	l.font = font()
	l.font_size = 64
	l.pixel_size = height / 64.0   # `height` is the em size in metres
	l.modulate = colour
	l.outline_size = 0
	l.shaded = false
	l.double_sided = false
	# One line, anchored at `at` (left edge, right edge or centre per alignment); sizes come
	# from fit() so it never overflows `block_width`.
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
	l.horizontal_alignment = align
	l.position = at
	l.visibility_range_end = 30.0
	return l

static func box(size: Vector3, at: Vector3, mat: Material) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	m.mesh = b
	m.material_override = mat
	m.position = at
	m.visibility_range_end = 60.0
	return m
