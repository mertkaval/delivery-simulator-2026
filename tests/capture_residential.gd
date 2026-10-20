extends SceneTree
## Residential district captures: street, aerial, rear lane, forest edge, delivery door.
## usage: godot --path . --script res://tests/capture_residential.gd -- <prefix> [hour]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "res"
	var hour: float = float(args[1]) if args.size() > 1 else 15.5
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=60
	var lot: Dictionary = ResidentialLayout.delivery_lot(14)
	var door: Vector3 = CityCatalog.address_position(14)
	var facing: Vector3 = CityCatalog.address_facing(14)
	var lane: Dictionary = ResidentialLayout.lanes()[0]
	var views := [
		["street", Vector3(3.0, 1.7, -300), Vector3(14, 3, -340)],
		["street_north", Vector3(-3.0, 1.7, -60), Vector3(-14, 3, -110)],
		["delivery_door", door + facing * 9.0 + Vector3(0, 0.7, 0), door],
		["aerial", Vector3(-20, 45, -270), Vector3(30, 0, -330)],
		["rear_lane", Vector3(lane.x, 1.7, lane.z1 - 4), Vector3(lane.x, 3, lane.z1 - 60)],
		["forest_edge", Vector3(98.5, 1.7, -470), Vector3(112, 6, -500)],
		["outer_row", Vector3(66, 1.7, -440), Vector3(78, 3, -480)]]
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
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix, view[0]])
	print("RESIDENTIAL ", JSON.stringify(report))
	quit()
