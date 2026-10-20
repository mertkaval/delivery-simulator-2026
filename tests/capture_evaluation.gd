extends SceneTree
## Art-direction review captures: residential, downtown, towers, civic, people, aerial.
## usage: godot --path . --script res://tests/capture_evaluation.gd -- <prefix>
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "eval"
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=60
	var views := [
		["house_close",Vector3(-12,1.7,-128),Vector3(-21,2.5,-124)],
		["residential_street",Vector3(3,1.7,-300),Vector3(0,2,-360)],
		["side_street_houses",Vector3(70,1.7,-330),Vector3(85,3,-360)],
		["downtown_street",Vector3(146,1.7,-300),Vector3(146,8,-380)],
		["downtown_facades",Vector3(200,1.7,-262),Vector3(230,10,-270)],
		["towers",Vector3(180,40,-230),Vector3(300,30,-450)],
		["civic",Vector3(500,8,-300),Vector3(560,5,-330)],
		["people",Vector3(244,1.7,-306),Vector3(241,1.3,-326)],
		["aerial_city",Vector3(-60,260,40),Vector3(220,0,-420)]]
	var report := []
	for view in views:
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(80): await process_frame
		var times: Array[float]=[]
		for i in range(60):
			var before := Time.get_ticks_usec()
			await process_frame
			times.append(float(Time.get_ticks_usec()-before)/1000)
		times.sort()
		report.append({"view":view[0],"median_ms":snappedf(times[30],0.01),"p95_ms":snappedf(times[57],0.01),"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),"texture_mib":snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576,0.1)})
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix,view[0]])
	var file := FileAccess.open("res://tmp/%s_metrics.json" % prefix,FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	print("EVAL ",JSON.stringify(report))
	quit()
