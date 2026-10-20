extends SceneTree
## Native captures of the Blender city kit in the game world.
## usage: godot --path . --script res://tests/capture_citykit.gd -- <prefix> [hour]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "citykit"
	var hour: float = float(args[1]) if args.size() > 1 else 16.0
	if args.has("nokit"): KitBuilder.enabled = false
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=60
	var views := [
		["terraces",Vector3(58.5,1.7,-292),Vector3(53,4.5,-276)],
		["terraces_aerial",Vector3(22,26,-252),Vector3(52,0,-292)],
		["terrace_rear",Vector3(36,1.7,-372),Vector3(44,4,-360)],
		["walkup",Vector3(-80,1.8,-86),Vector3(-92,9,-102)],
		["corridor",Vector3(71,1.7,-401),Vector3(104,7,-398)],
		["corridor_aerial",Vector3(56,38,-352),Vector3(100,0,-398)],
		["city_aerial",Vector3(-90,210,-120),Vector3(150,0,-450)]]
	var report := []
	for view in views:
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(70): await process_frame
		var times: Array[float]=[]
		for i in range(40):
			var before := Time.get_ticks_usec()
			await process_frame
			times.append(float(Time.get_ticks_usec()-before)/1000)
		times.sort()
		report.append({"view":view[0],"median_ms":snappedf(times[20],0.01),"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix,view[0]])
	print("CITYKIT ",JSON.stringify(report))
	quit()
