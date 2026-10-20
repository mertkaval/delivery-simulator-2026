extends SceneTree
## Rain captures: wet avenue by day and night, downtown in rain.
## usage: godot --path . --script res://tests/capture_weather.gd -- <prefix>
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var prefix: String = OS.get_cmdline_user_args()[0] if OS.get_cmdline_user_args().size() > 0 else "rain"
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 62
	world.weather.forced = 1.0
	var views := [["day", 14.0, Vector3(3.5, 1.7, -300), Vector3(5, 1.0, -345)],
		["night", 21.5, Vector3(3.5, 1.7, -300), Vector3(5, 1.0, -345)],
		["downtown", 16.0, Vector3(150, 1.7, -300), Vector3(150, 2.0, -360)],
		["dry", 14.0, Vector3(3.5, 1.7, -300), Vector3(5, 1.0, -345)]]
	for v in views:
		if v[0] == "dry": world.weather.forced = 0.0
		world.set_time(v[1])
		camera.position = v[2]
		camera.look_at(v[3])
		for i in range(90):
			world.set_time(v[1])
			await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix, v[0]])
		print("WEATHER ", v[0], " rain=", snappedf(world.weather.rain, 0.01), " wet=", snappedf(world.weather.wetness, 0.01), " ", world.weather.describe())
	quit()
