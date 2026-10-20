extends SceneTree
var game: Node

func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	game = load("res://app/app_root.tscn").instantiate()
	root.add_child(game)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/menu_check.png")
	game.session.offer()
	game.show_menu("phone")
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/phone_check.png")
	game.session.accept()
	game.close_menu()
	game.session.calendar_minutes = 23 * 60
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/night_check.png")
	game.session.calendar_minutes = 12 * 60
	game.player.position = Vector3(2, 0.1, -50)
	game.player.rotation = Vector3.ZERO
	game.player.camera.rotation = Vector3(-0.08, 0, 0)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/city_day_check.png")
	game.player.position = Vector3(-8, 0.1, -88)
	game.player.camera.look_at(Vector3(-18, 2, -100))
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/restaurant_check.png")
	quit()
