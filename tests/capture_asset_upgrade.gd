extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1440, 900)
	root.msaa_3d = Viewport.MSAA_4X
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 58
	camera.far = 1200
	var bike := CityAssets.create("bicycle")
	world.add_child(bike)
	bike.position = Vector3(-8, 0, 19)
	var views := [
		["upgrade_street", Vector3(-7.5, 1.75, 0), Vector3(1, 2.0, -35)],
		["upgrade_restaurant", Vector3(-8, 2.8, 22), Vector3(-18, 1.8, 9)],
		["upgrade_interior", Vector3(-14, 1.75, 13.6), Vector3(-20, 1.6, 7)],
		["upgrade_bicycle", Vector3(-6.2, 1.05, 17.5), Vector3(-8, 0.58, 19)],
		["upgrade_park", Vector3(57, 2.8, -308), Vector3(44, 1.7, -332)],
		["upgrade_apartment", Vector3(-69, 8, -75), Vector3(-92, 8, -110)],
	]
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(20): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s.png" % view[0])
		print(view[0], " draw_calls=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	print("ASSET CAPTURES PASS")
	quit()
