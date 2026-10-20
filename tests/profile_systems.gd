extends SceneTree
## Frame-time cost of each city system: measure the street view with everything on, then with
## one system switched off at a time (hidden and not processing).
func _initialize() -> void: call_deferred("run")

func measure(frames: int = 60) -> Array:
	for i in range(30): await process_frame
	var times: Array[float] = []
	for i in range(frames):
		var before := Time.get_ticks_usec()
		await process_frame
		times.append(float(Time.get_ticks_usec() - before) / 1000.0)
	times.sort()
	return [snappedf(times[frames / 2], 0.01), Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)]

func run() -> void:
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	camera.position = Vector3(3.0, 1.7, -300)
	camera.look_at(Vector3(14, 3, -340))
	for i in range(60): await process_frame
	print("PROFILE all ", await measure())
	for name in ["Animals", "Buses", "Restaurants", "Weather", "StreetSignage", "CityLife", "CityTraffic", "CityVFX", "Residences", "KitBuildings", "RainlineDowntown", "GrassMeadows"]:
		var node := world.get_node_or_null(name)
		if node == null: continue
		var mode := node.process_mode
		node.process_mode = Node.PROCESS_MODE_DISABLED
		if node is Node3D: node.visible = false
		print("PROFILE without ", name, " ", await measure())
		node.process_mode = mode
		if node is Node3D: node.visible = true
	quit()
