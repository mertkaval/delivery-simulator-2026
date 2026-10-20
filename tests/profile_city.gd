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
	var report := {"resolution":"1280x720", "renderer":"Forward+", "views":[], "grass_clumps":world.get_node("GrassMeadows").clump_count}
	for view in [["street",Vector3(-7.5,1.75,0),Vector3(1,2,-35)],["park",Vector3(57,2.8,-308),Vector3(44,1.7,-332)],["roundabout",Vector3(57,4,-110),Vector3(92,7,-155)]]:
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(90): await process_frame
		var samples: Array[float]=[]
		for i in range(180):
			var before := Time.get_ticks_usec()
			await process_frame
			samples.append((Time.get_ticks_usec()-before)/1000.0)
		samples.sort()
		report.views.append({"view":view[0],"median_ms":samples[90],"p95_ms":samples[171],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"visible_primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
	var file := FileAccess.open("res://tmp/performance.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	print(JSON.stringify(report))
	quit()
