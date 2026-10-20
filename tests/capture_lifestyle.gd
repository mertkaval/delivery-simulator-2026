extends SceneTree
func _initialize() -> void: call_deferred("run")
func capture(id: String) -> void:
	for i in range(30): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/"+id+".png")
func run() -> void:
	root.size=Vector2i(1280,720)
	var game=load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	game.player.set_physics_process(false)
	game.player.position=Vector3(-7.5,.1,19)
	game.session.offer()
	game.show_menu("phone")
	await capture("phone_orders")
	game.show_menu("map")
	await capture("phone_navigation")
	game.close_menu()
	game.player.position=Vector3(57,2,-110)
	game.player.camera.look_at(Vector3(92,7,-155))
	await capture("estate_roads")
	game.player.position=Vector3(-80,.2,-14)
	game.player.camera.look_at(Vector3(-92,2,-30))
	await capture("equipment_store")
	game.session.calendar_minutes=21*60
	game.world.set_time(21)
	await capture("city_night")
	print("LIFESTYLE CAPTURES PASS")
	quit()
