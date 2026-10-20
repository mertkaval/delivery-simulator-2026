extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=58
	var views := [
		["hospital",Vector3(519,2,-294),Vector3(567,5,-328)],
		["fire_station",Vector3(537,1.8,-449),Vector3(569,3,-468)],
		["school",Vector3(529,2,-575),Vector3(567,3,-608)],
		["cycle_lane",Vector3(477,1.7,-295),Vector3(474,1.3,-374)],
		["garden",Vector3(179,1.7,-313),Vector3(182,0.5,-311)],
		["pedestrians",Vector3(244,1.7,-306),Vector3(241,1.3,-326)],
		["civic_aerial",Vector3(627,100,-248),Vector3(538,0,-449)]]
	var report := []
	for view in views:
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(70): await process_frame
		var times: Array[float]=[]
		for i in range(90):
			var before := Time.get_ticks_usec()
			await process_frame
			times.append(float(Time.get_ticks_usec()-before)/1000)
		times.sort()
		report.append({"view":view[0],"median_ms":times[45],"p95_ms":times[85],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),"texture_mib":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576})
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/living_city_"+view[0]+".png")
	var file := FileAccess.open("res://tmp/living_city_metrics.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	print("LIVING CAPTURES ",JSON.stringify(report))
	quit()
