class_name MissionCard
extends PanelContainer
## HUD card for the current training task: "TRAINING · TASK 3 OF 12", the task, how to do it,
## a progress bar for measured tasks and one pip per task. Ticks green when a task is done.
## Compact (HudStyle.COLUMN wide, instruction capped at four lines); it sits in the HUD's left
## column under the objective panel, so it can never overlap the backpack line or minimap.

const MINT := HudStyle.ACCENT
const WARM := HudStyle.WARM
const INNER := HudStyle.COLUMN - 28     ## content width inside the card's margins

var header: Label
var title: Label
var hint: Label
var bar: ProgressBar
var pips: HBoxContainer
var finished := false
var _shown := -1
var _ticking := false

var target_box: PanelContainer
var target_name: Label
var target_info: Label

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(HudStyle.COLUMN, 0)
	add_theme_stylebox_override("panel", HudStyle.panel(MINT, HudStyle.PANEL, 12, 9))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 3)
	add_child(col)
	header = HudStyle.eyebrow("", MINT)
	col.add_child(header)
	title = HudStyle.label("", HudStyle.TITLE, HudStyle.INK, HudStyle.Face.TEXT, HudStyle.SEMIBOLD)
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.custom_minimum_size.x = INNER
	title.max_lines_visible = 2
	col.add_child(title)
	hint = HudStyle.label("", HudStyle.SMALL, HudStyle.INK_SOFT)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = INNER
	hint.max_lines_visible = 4
	hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	hint.add_theme_constant_override("line_spacing", -1)
	col.add_child(hint)
	var spacer := Control.new()
	spacer.custom_minimum_size.y = 2
	col.add_child(spacer)
	bar = HudStyle.meter(INNER, 3.0, WARM)
	col.add_child(bar)
	pips = HBoxContainer.new()
	pips.add_theme_constant_override("separation", 3)
	col.add_child(pips)
	# The order to collect / deliver: the customer's name, big, while there is one.
	target_box = HudStyle.order_chip()
	target_box.add_theme_stylebox_override("panel", HudStyle.panel(HudStyle.AMBER, Color(1, 1, 1, 0.06), 9, 5))
	target_name = target_box.get_node("Col/Name") as Label
	target_info = target_box.get_node("Col/Info") as Label
	target_box.visible = false
	var gap := Control.new()
	gap.custom_minimum_size.y = 3
	col.add_child(gap)
	col.add_child(target_box)

## The customer to look for (empty name hides the plate).
func set_target(customer: String, ticket: String, package: String) -> void:
	if target_box == null: return
	target_box.visible = customer != ""
	target_name.text = customer.to_upper()
	target_info.text = "%s  ·  %s" % [ticket, package]

func label(size: int, colour: Color) -> Label:
	return HudStyle.label("", size, colour)

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
	title.add_theme_color_override("font_color", HudStyle.INK)
	hint.text = how
	bar.visible = progress > 0.0
	bar.value = clampf(progress, 0.0, 1.0)
	if pips.get_child_count() != total:
		for c in pips.get_children(): c.queue_free()
		var w := floorf((INNER - 3.0 * (total - 1)) / float(total))
		for i in range(total):
			var pip := ColorRect.new()
			pip.custom_minimum_size = Vector2(w, 3)
			pip.mouse_filter = Control.MOUSE_FILTER_IGNORE
			pips.add_child(pip)
	for i in range(total):
		(pips.get_child(i) as ColorRect).color = MINT if i < index else (WARM if i == index else HudStyle.FAINT)

## The current task is done: tick it.
func complete() -> void:
	_ticking = true
	title.text = "✓  " + title.text
	title.add_theme_color_override("font_color", MINT)
	bar.value = 1.0
	if _shown >= 0 and _shown < pips.get_child_count(): (pips.get_child(_shown) as ColorRect).color = MINT
	pivot_offset = Vector2(0, size.y * 0.5)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2.ONE * 1.025, 0.12)
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
	hint.text = how if how != "" else "%s bonus added. Next goal: save up for a bicycle. Requests arrive while you're online; lunch and dinner are the busy hours." % bonus
	bar.visible = false
	for c in pips.get_children(): (c as ColorRect).color = MINT
	var tw := create_tween()
	tw.tween_interval(12.0)
	tw.tween_property(self, "modulate:a", 0.0, 0.8)
	tw.tween_callback(func() -> void:
		finished = false
		hide()
		modulate.a = 1.0)
