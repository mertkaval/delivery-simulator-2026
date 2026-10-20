extends PanelContainer
var phone_mode := false
var session: DeliverySession
func _draw() -> void:
	if not phone_mode: return
	var notch := StyleBoxFlat.new()
	notch.bg_color = Color("03070a")
	notch.set_corner_radius_all(11)
	draw_style_box(notch, Rect2(size.x * 0.5 - 40, 12, 80, 21))
	draw_circle(Vector2(size.x * 0.5 + 22, 22), 3, Color("203447"))
	draw_line(Vector2(size.x * 0.5 - 17, 22), Vector2(size.x * 0.5 + 8, 22), Color("283139"), 3)
	if session != null:
		draw_string(ThemeDB.fallback_font, Vector2(23, 28), "%02d:%02d" % [int(session.hour()), int(session.calendar_minutes) % 60], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("d8e6ec"))
	draw_rect(Rect2(size.x - 46, 18, 20, 9), Color("9bdbc4"), false, 1)
	draw_rect(Rect2(size.x - 44, 20, 14, 5), Color("9bdbc4"))
	draw_line(Vector2(size.x * 0.5 - 35, size.y - 14), Vector2(size.x * 0.5 + 35, size.y - 14), Color("bdcad2"), 4, true)
func _process(_delta: float) -> void:
	if visible and phone_mode: queue_redraw()
