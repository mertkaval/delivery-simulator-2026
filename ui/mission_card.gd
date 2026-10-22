class_name MissionCard
extends PanelContainer
## HUD card for the current training task: "TRAINING · TASK 3 OF 12", the task, how to do it,
## a progress bar for measured tasks and one pip per task. Ticks green when a task is done.

const MINT := Color("9bceb7")
const WARM := Color("f4e7c4")

var header: Label
var title: Label
var hint: Label
var bar: ProgressBar
var pips: HBoxContainer
var finished := false
var _shown := -1
var _ticking := false

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(445, 0)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.045, 0.09, 0.1, 0.93)
	style.set_corner_radius_all(14)
	style.border_width_left = 5
	style.border_color = MINT
	style.content_margin_left = 22
	style.content_margin_right = 20
	style.content_margin_top = 12
	style.content_margin_bottom = 14
	add_theme_stylebox_override("panel", style)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 5)
	add_child(col)
	header = label(13, MINT)
	col.add_child(header)
	title = label(21, Color.WHITE)
	col.add_child(title)
	hint = label(15, Color("d4e2dc"))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = 400
	col.add_child(hint)
	bar = ProgressBar.new()
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(400, 6)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(1, 1, 1, 0.12)
	bg.set_corner_radius_all(3)
	var fill := bg.duplicate() as StyleBoxFlat
	fill.bg_color = WARM
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)
	bar.max_value = 1.0
	col.add_child(bar)
	pips = HBoxContainer.new()
	pips.add_theme_constant_override("separation", 4)
	col.add_child(pips)
	# "LOOK FOR" plate: the customer's name, big, while there is an order to collect / deliver.
	target_box = PanelContainer.new()
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color("f7f1df")
	plate.set_corner_radius_all(8)
	plate.content_margin_left = 12
	plate.content_margin_right = 12
	plate.content_margin_top = 6
	plate.content_margin_bottom = 7
	target_box.add_theme_stylebox_override("panel", plate)
	target_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var tcol := VBoxContainer.new()
	tcol.add_theme_constant_override("separation", 0)
	target_box.add_child(tcol)
	var head := Label.new()
	head.text = "ORDER FOR"
	head.add_theme_font_size_override("font_size", 12)
	head.add_theme_color_override("font_color", Color("8a6a2a"))
	tcol.add_child(head)
	target_name = Label.new()
	target_name.add_theme_font_size_override("font_size", 27)
	target_name.add_theme_color_override("font_color", Color("15191a"))
	tcol.add_child(target_name)
	target_info = Label.new()
	target_info.add_theme_font_size_override("font_size", 14)
	target_info.add_theme_color_override("font_color", Color("4a4434"))
	tcol.add_child(target_info)
	target_box.visible = false
	col.add_child(target_box)

var target_box: PanelContainer
var target_name: Label
var target_info: Label

## The customer to look for (empty name hides the plate).
func set_target(customer: String, ticket: String, package: String) -> void:
	if target_box == null: return
	target_box.visible = customer != ""
	target_name.text = customer.to_upper()
	target_info.text = "%s   ·   %s" % [ticket, package]

func label(size: int, colour: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override("shadow_offset_y", 2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l

func set_task(index: int, total: int, task: String, how: String, progress: float) -> void:
	if _ticking and index == _shown: return
	finished = false
	if index != _shown:
		_ticking = false
		_shown = index
		modulate.a = 0.0
		create_tween().tween_property(self, "modulate:a", 1.0, 0.35)
	header.text = "TRAINING  ·  TASK %d OF %d" % [index + 1, total]
	title.text = task
	title.add_theme_color_override("font_color", Color.WHITE)
	hint.text = how
	bar.visible = progress > 0.0
	bar.value = clampf(progress, 0.0, 1.0)
	if pips.get_child_count() != total:
		for c in pips.get_children(): c.queue_free()
		for i in range(total):
			var pip := ColorRect.new()
			pip.custom_minimum_size = Vector2(29, 5)
			pips.add_child(pip)
	for i in range(total):
		(pips.get_child(i) as ColorRect).color = MINT if i < index else (WARM if i == index else Color(1, 1, 1, 0.16))

## The current task is done: tick it.
func complete() -> void:
	_ticking = true
	title.text = "✓  " + title.text
	title.add_theme_color_override("font_color", MINT)
	bar.value = 1.0
	if _shown >= 0 and _shown < pips.get_child_count(): (pips.get_child(_shown) as ColorRect).color = MINT
	pivot_offset = size * 0.5
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2.ONE * 1.04, 0.12)
	tw.tween_property(self, "scale", Vector2.ONE, 0.2)

## A standing goal (not a numbered task), e.g. saving up for the first bicycle.
func set_goal(head: String, task: String, how: String, progress: float) -> void:
	finished = false
	set_target("", "", "")
	_shown = -2
	header.text = head
	title.text = task
	title.add_theme_color_override("font_color", WARM)
	hint.text = how
	bar.visible = true
	bar.value = clampf(progress, 0.0, 1.0)
	for c in pips.get_children(): c.queue_free()

func show_finished(bonus: String, head := "TRAINING COMPLETE", task := "You're ready, courier!", how := "") -> void:
	finished = true
	_ticking = false
	_shown = -1
	visible = true
	set_target("", "", "")
	header.text = head
	title.text = task
	title.add_theme_color_override("font_color", MINT)
	hint.text = how if how != "" else "%s bonus added to your wallet. Now save up for a bicycle: requests arrive automatically while you're online, and lunch and dinner are the busy hours." % bonus
	bar.visible = false
	for c in pips.get_children(): (c as ColorRect).color = MINT
	var tw := create_tween()
	tw.tween_interval(12.0)
	tw.tween_property(self, "modulate:a", 0.0, 0.8)
	tw.tween_callback(func() -> void:
		finished = false
		hide()
		modulate.a = 1.0)
