extends SceneTree

func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	root.size = Vector2i(1280, 720)
	root.msaa_3d = Viewport.MSAA_4X
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(13)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	camera.far = 1500
	var views := [
		["house_detail", Vector3(-10, 4, -1), Vector3(-21, 2.7, -14)],
		["expanded_city", Vector3(150, 230, -200), Vector3(0, 0, -365)],
		["maple_street", Vector3(9, 2.4, -266), Vector3(25, 2.6, -300)],
		["oak_house", Vector3(-10, 3, -26), Vector3(-21, 2.7, -42)],
	]
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(12): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s.png" % view[0])
	print("Visible draw calls: ", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	print("EXPANSION CAPTURE PASS")
	quit()
