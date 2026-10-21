extends SceneTree
## Captures of the imported house types (tools/prepare_new_houses.py) in the residential district:
## a street view of each type, its delivery door with the house number and the drop zone, a
## mixed-street aerial and a mid-distance view (far LOD). Prints lot counts per type.
## usage (rendered, no --headless): godot --path . --script res://tests/capture_new_houses.gd -- <out_dir> [hour]
func _initialize() -> void: call_deferred("run")

func lot_of(type: String, delivery: bool) -> Dictionary:
	for lot in ResidentialLayout.lots():
		if lot.type == type and (lot.delivery >= 0) == delivery: return lot
	return {}

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out_dir: String = args[0] if args.size() > 0 else "res://tmp"
	var hour: float = float(args[1]) if args.size() > 1 else 15.0
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var counts := {}
	var delivery_types := {}
	for lot in ResidentialLayout.lots():
		counts[lot.type] = int(counts.get(lot.type, 0)) + 1
		if lot.delivery >= 0: delivery_types[lot.type] = int(delivery_types.get(lot.type, 0)) + 1
	print("LOT TYPES ", JSON.stringify(counts), " DELIVERY ", JSON.stringify(delivery_types))
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	var views: Array = []
	var zones: Array[DropZone] = []
	for type: String in ResidentialLayout.IMPORTED:
		var lot := lot_of(type, true)
		var street := lot if not lot.is_empty() else lot_of(type, false)
		if street.is_empty(): continue
		var facing: Vector3 = street.facing
		var side := facing.cross(Vector3.UP)
		var front: Vector3 = street.front
		# From across the street (other sidewalk), slightly up the road.
		views.append(["%s_street" % type, front + facing * 17.0 + side * 7.0 + Vector3(0, 1.7, 0), front - facing * 4.0 + Vector3(0, 3.0, 0)])
		views.append(["%s_corner" % type, front + facing * 9.0 - side * 9.0 + Vector3(0, 2.2, 0), front - facing * 5.0 + Vector3(0, 2.5, 0)])
		if not lot.is_empty():
			var index: int = lot.delivery
			var door: Vector3 = CityCatalog.address_position(index)
			var out: Vector3 = CityCatalog.address_facing(index)
			var zone := DropZone.new()
			world.add_child(zone)
			zone.setup(index, world.doors[index], out, "door")
			zones.append(zone)
			views.append(["%s_door_%d" % [type, index], door + out * 4.2 + out.cross(Vector3.UP) * 0.9 + Vector3(0, 0.75, 0), door + Vector3(0, -0.4, 0)])
			views.append(["%s_walk_%d" % [type, index], front + facing * 8.5 + Vector3(0, 1.7, 0), door])
		views.append(["%s_far" % type, front + facing * 55.0 + side * 20.0 + Vector3(0, 16.0, 0), front + Vector3(0, 3.0, 0)])
	views.append(["aerial", Vector3(-30, 40, -330), Vector3(10, 0, -380)])
	views.append(["avenue", Vector3(-3.0, 1.7, -440), Vector3(-14, 3, -490)])
	var report := []
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(60): await process_frame
		var times: Array[float] = []
		for i in range(30):
			var before := Time.get_ticks_usec()
			await process_frame
			times.append(float(Time.get_ticks_usec() - before) / 1000)
		times.sort()
		report.append({"view": view[0], "median_ms": snappedf(times[15], 0.01), "draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("%s/house_%s.png" % [out_dir, view[0]])
	print("NEW HOUSES ", JSON.stringify(report))
	quit()
