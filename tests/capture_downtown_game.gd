extends SceneTree
func _initialize() -> void: call_deferred("run")
func capture(id: String) -> void:
	for i in range(45): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/downtown_"+id+".png")
func run() -> void:
	root.size=Vector2i(1280,720)
	var game=load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	game.set_process(false)
	game.player.set_physics_process(false)
	game.player.position=Vector3(244,.1,-280)
	game.player.camera.look_at(Vector3(254,3,-370))
	game.player.bicycle.position=Vector3(243.8,.1,-282.5)
	game.session.offer_position=game.player.position
	game.session.offer()
	game.update_hud()
	await capture("gameplay")
	game.show_menu("phone")
	await capture("phone_order")
	game.close_menu()
	game.session.calendar_minutes=21*60
	game.world.set_time(21)
	game.update_hud()
	await capture("night")
	game.world.set_time(14)
	game.player.position=Vector3(247,.1,-487)
	game.player.camera.look_at(Vector3(228,3,-487))
	await capture("construction")
	game.player.position=Vector3(370,.1,-455)
	game.player.camera.look_at(Vector3(386,3,-459))
	await capture("plaza")
	print("DOWNTOWN GAME CAPTURES PASS")
	quit()
