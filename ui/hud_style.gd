class_name HudStyle
extends RefCounted
## The in-game HUD's look in one place: font stack and weights, type scale, colours, spacing,
## panel / chip / key-cap styles. app_root.gd (objective, status, prompt, toasts, name tag,
## backpack line, controls), ui/mission_card.gd (training card, order chip) and ui/minimap.gd
## build their widgets from here.
##
## Units are canvas units of the 1280 x 720 base canvas (project.godot: stretch mode
## canvas_items), so every size here is multiplied by 1.5 at 1080p and by 2 at 1440p and the
## layout is identical at every 16:9 resolution.
##
## Fonts: the project ships no font files, so the HUD uses Windows system faces through
## SystemFont with fallbacks. To bundle a font later, set BUNDLED_FONT (and optionally
## BUNDLED_DISPLAY_FONT / BUNDLED_MONO_FONT) to a res:// .ttf/.otf path: that one line swaps the
## whole HUD over. Variable fonts get their weight and width through FontVariation axes.

## One-line swap: e.g. "res://assets/fonts/Inter-Variable.ttf" (body text, and headings when
## BUNDLED_DISPLAY_FONT is empty).
const BUNDLED_FONT := ""
const BUNDLED_DISPLAY_FONT := ""
const BUNDLED_MONO_FONT := ""

## Headings, numbers, labels, key caps: a compact DIN-style face (variable: wght 300-700, wdth 75-100).
const DISPLAY_FONTS := ["Bahnschrift", "Segoe UI Variable Display", "Segoe UI", "Arial", "sans-serif"]
## Body text, instructions, prompts.
const TEXT_FONTS := ["Segoe UI Variable Text", "Segoe UI", "Arial", "sans-serif"]
## The printed receipt on a package tag.
const MONO_FONTS := ["Cascadia Mono", "Consolas", "Courier New", "monospace"]

enum Face { DISPLAY, TEXT, MONO }

# --- Type scale (base canvas px; x1.5 at 1080p) -------------------------------------------------
const MICRO := 9        ## key caps in the controls bar, small caps captions
const CAPTION := 10     ## eyebrow labels (uppercase, tracked), meters, secondary lines
const SMALL := 11       ## secondary text, backpack line, receipt
const BODY := 12        ## instructions, toasts
const PROMPT := 13      ## the interaction prompt
const TITLE := 14       ## objective, task title
const NAME := 17        ## customer name on the order chip
const TAG := 19         ## name on the package tag panel
const CLOCK := 21       ## the time in the status panel
const SPEED := 26       ## riding speed

# --- Weights ------------------------------------------------------------------------------------
const REGULAR := 400
const MEDIUM := 500
const SEMIBOLD := 600
const BOLD := 700

# --- Colours ------------------------------------------------------------------------------------
const INK := Color("f3f6f4")             ## primary text
const INK_SOFT := Color("cbd7d2")        ## body text on panels
const MUTED := Color("8ea29b")           ## labels, captions
const FAINT := Color(1, 1, 1, 0.14)      ## empty meter tracks, rules
const ACCENT := Color("7fe3b5")          ## mint: route, training, positive (matches the main menu)
const WARM := Color("f4e7c4")            ## current task, held items
const AMBER := Color("ffc53d")           ## the order (customer name, tags)
const DANGER := Color("ff8f7a")
const PANEL := Color(0.03, 0.05, 0.06, 0.74)
const PANEL_STRONG := Color(0.025, 0.04, 0.05, 0.86)
const EDGE := Color(1, 1, 1, 0.07)       ## hairline around panels
const PAPER := Color("f5f1e6")           ## the package name tag
const PAPER_INK := Color("16191a")
const PAPER_MUTED := Color("7a6334")
const KEY_BG := Color(0.95, 0.97, 0.96, 0.92)
const KEY_INK := Color("101618")

# --- Spacing ------------------------------------------------------------------------------------
const MARGIN := 16      ## screen edge
const GAP := 6          ## between stacked HUD blocks
const RADIUS := 8
const COLUMN := 320     ## left column width (objective, order, training card)

static var _fonts: Dictionary = {}
static var _theme: Theme

## A face at a weight (100-900) and width (wdth axis, 75-100; condensed headings).
static func font(face: Face = Face.TEXT, weight: int = REGULAR, width: int = 100) -> Font:
	var key := "%d_%d_%d" % [face, weight, width]
	if _fonts.has(key): return _fonts[key]
	var base: Font = null
	var bundled := BUNDLED_MONO_FONT if face == Face.MONO else (BUNDLED_DISPLAY_FONT if face == Face.DISPLAY and BUNDLED_DISPLAY_FONT != "" else BUNDLED_FONT)
	if bundled != "" and ResourceLoader.exists(bundled):
		base = load(bundled) as Font
	if base == null:
		var sys := SystemFont.new()
		var names: Array = MONO_FONTS if face == Face.MONO else (DISPLAY_FONTS if face == Face.DISPLAY else TEXT_FONTS)
		sys.font_names = PackedStringArray(names)
		sys.font_weight = weight
		base = sys
	var v := FontVariation.new()
	v.base_font = base
	var ts := TextServerManager.get_primary_interface()
	var axes := {}
	var supported: Dictionary = base.get_supported_variation_list()
	if supported.has(ts.name_to_tag("wght")): axes[ts.name_to_tag("wght")] = weight
	if supported.has(ts.name_to_tag("wdth")): axes[ts.name_to_tag("wdth")] = width
	v.variation_opentype = axes
	_fonts[key] = v
	return v

## Theme for the HUD root: body face and size by default; widgets override per role.
static func theme() -> Theme:
	if _theme != null: return _theme
	_theme = Theme.new()
	_theme.default_font = font(Face.TEXT, REGULAR)
	_theme.default_font_size = BODY
	_theme.set_color("font_color", "Label", INK)
	return _theme

## A label of the type scale. Free-floating text over the 3D view should pass shadow = true.
static func label(text: String = "", size: int = BODY, colour: Color = INK, face: Face = Face.TEXT, weight: int = REGULAR, shadow := false) -> Label:
	var l := Label.new()
	l.text = text
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_override("font", font(face, weight))
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	if shadow:
		l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
		l.add_theme_constant_override("shadow_offset_x", 0)
		l.add_theme_constant_override("shadow_offset_y", 1)
		l.add_theme_constant_override("shadow_outline_size", 3)
	return l

## Uppercase, tracked caption ("TRAINING · TASK 3 OF 13").
static func eyebrow(text: String = "", colour: Color = MUTED, size: int = CAPTION) -> Label:
	var l := label(text, size, colour, Face.DISPLAY, SEMIBOLD)
	var v := FontVariation.new()
	v.base_font = font(Face.DISPLAY, SEMIBOLD)
	v.spacing_glyph = 1
	l.add_theme_font_override("font", v)
	l.uppercase = true
	return l

## Translucent HUD panel. accent: a coloured bar on the left edge.
static func panel(accent: Color = Color(0, 0, 0, 0), bg: Color = PANEL, pad_x: int = 12, pad_y: int = 9) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(RADIUS)
	s.border_color = EDGE
	s.set_border_width_all(1)
	if accent.a > 0.0:
		s.border_width_left = 3
		s.border_color = accent
		s.border_width_top = 0
		s.border_width_right = 0
		s.border_width_bottom = 0
	s.content_margin_left = pad_x + (2 if accent.a > 0.0 else 0)
	s.content_margin_right = pad_x
	s.content_margin_top = pad_y
	s.content_margin_bottom = pad_y
	s.shadow_color = Color(0, 0, 0, 0.18)
	s.shadow_size = 6
	s.shadow_offset = Vector2(0, 2)
	s.anti_aliasing = true
	return s

## A full pill (toasts, distance chip, prompt).
static func pill(bg: Color = PANEL_STRONG, pad_x: int = 10, pad_y: int = 4) -> StyleBoxFlat:
	var s := panel(Color(0, 0, 0, 0), bg, pad_x, pad_y)
	s.set_corner_radius_all(64)
	return s

## A keyboard key: "E", "Tab", "Space", "Click".
static func keycap(text: String, size: int = CAPTION) -> PanelContainer:
	var box := PanelContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var s := StyleBoxFlat.new()
	s.bg_color = KEY_BG
	s.set_corner_radius_all(3)
	s.content_margin_left = 4
	s.content_margin_right = 4
	s.content_margin_top = 0
	s.content_margin_bottom = 0
	s.border_width_bottom = 1
	s.border_color = Color(0.55, 0.62, 0.6, 0.9)
	s.anti_aliasing = true
	box.add_theme_stylebox_override("panel", s)
	var l := label(text, size, KEY_INK, Face.DISPLAY, BOLD)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size.x = size + 2
	box.add_child(l)
	return box

## "[E / Click] Take X  [F] Bag" -> [["E / Click", "Take X"], ["F", "Bag"]]; text before the first
## bracket comes back with an empty key.
static func parse_keys(text: String) -> Array[PackedStringArray]:
	var parts: Array[PackedStringArray] = []
	var first := text.find("[")
	if first != 0:
		var lead := text.substr(0, first if first >= 0 else text.length()).strip_edges()
		if lead != "": parts.append(PackedStringArray(["", lead]))
	if first < 0: return parts
	var re := RegEx.new()
	re.compile("\\[([^\\]]+)\\]\\s*([^\\[]*)")
	for m in re.search_all(text.substr(first)):
		parts.append(PackedStringArray([m.get_string(1).strip_edges(), m.get_string(2).strip_edges()]))
	return parts

## Fill `row` with key caps and labels for parse_keys() parts. "E / Click" becomes two caps.
static func fill_keys(row: HBoxContainer, parts: Array[PackedStringArray], text_size: int, colour: Color, key_size: int, weight: int = MEDIUM) -> void:
	for c in row.get_children():
		row.remove_child(c)
		c.queue_free()
	for i in range(parts.size()):
		var key: String = parts[i][0]
		if key != "":
			var keys := key.split(" / ")
			for k in range(keys.size()):
				if k > 0: row.add_child(label("/", key_size, MUTED, Face.DISPLAY, SEMIBOLD))
				row.add_child(keycap(keys[k], key_size))
		if parts[i][1] != "":
			var l := label(parts[i][1], text_size, colour, Face.TEXT, weight)
			row.add_child(l)
		if i < parts.size() - 1:
			var gap := Control.new()
			gap.custom_minimum_size.x = 6
			gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
			row.add_child(gap)

## A thin horizontal meter (needs, training progress).
static func meter(width: float, height: float = 3.0, fill: Color = ACCENT) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.custom_minimum_size = Vector2(width, height)
	bar.max_value = 1.0
	var bg := StyleBoxFlat.new()
	bg.bg_color = FAINT
	bg.set_corner_radius_all(2)
	var fg := bg.duplicate() as StyleBoxFlat
	fg.bg_color = fill
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fg)
	return bar

static func set_meter_colour(bar: ProgressBar, colour: Color) -> void:
	var fg := bar.get_theme_stylebox("fill") as StyleBoxFlat
	if fg and fg.bg_color != colour: fg.bg_color = colour

## The order chip: who the order is for, big, with ticket and package. Used under the objective
## and inside the training card. Children: Col/Head, Col/Name, Col/Info.
static func order_chip() -> PanelContainer:
	var chip := PanelContainer.new()
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	chip.add_theme_stylebox_override("panel", panel(AMBER, PANEL_STRONG, 10, 6))
	var col := VBoxContainer.new()
	col.name = "Col"
	col.add_theme_constant_override("separation", -1)
	chip.add_child(col)
	var head := eyebrow("ORDER FOR", AMBER, MICRO)
	head.name = "Head"
	col.add_child(head)
	var who := label("", NAME, INK, Face.DISPLAY, BOLD)
	who.name = "Name"
	who.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	col.add_child(who)
	var info := label("", SMALL, INK_SOFT, Face.TEXT, REGULAR)
	info.name = "Info"
	info.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	col.add_child(info)
	return chip

## A rounded card (14 px corners, roomy padding): the modal shell and menu buttons.
static func card(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(14)
	style.content_margin_left = 24
	style.content_margin_right = 24
	style.content_margin_top = 18
	style.content_margin_bottom = 18
	return style

## A plain label with a soft drop shadow (menu pages).
static func shadow_label(text: String, size: int = 20, color: Color = Color("e6efeb")) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.5))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	return l
