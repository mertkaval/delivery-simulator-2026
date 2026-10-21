extends SceneTree
## Rendered frame-time benchmark of the street views (run WITHOUT --headless): the three
## profile_city views plus a busy avenue junction, the avenue mid-block crossing and downtown.
## Prints one JSON line; optional user arg after "--" = output json path.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	# Second user arg: "before" = the pre-street-life city (legacy traffic, no signals/LED/VFX),
	# "traffic" = new traffic without signals/LED/VFX, "visuals" = legacy traffic with them.
	var args := OS.get_cmdline_user_args()
	var mode: String = args[1] if args.size() > 1 else "after"
	var before := mode == "before"
	VehicleCatalog.legacy_traffic = mode in ["before", "visuals"]
	StreetLife.enabled = mode in ["after", "visuals"]
	# Third user arg "legacy": the city before the landscape pass (old kit trees, no planting).
	CityLandscape.legacy = args.size() > 2 and args[2] == "legacy"
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	var traffic: Node = world.get_node("CityTraffic")
	var report := {"resolution": "1280x720", "mode": mode, "city_cars": traffic.drivers.size(), "views": []}
	var views := [["street", Vector3(-7.5, 1.75, 0), Vector3(1, 2, -35)],
		["park", Vector3(57, 2.8, -308), Vector3(44, 1.7, -332)],
		["roundabout", Vector3(57, 4, -110), Vector3(92, 7, -155)],
		["junction", Vector3(14, 6, -372), Vector3(0, 1, -398)],
		["crossing", Vector3(-7, 2.5, -70), Vector3(0, 1, -93)],
		["downtown", Vector3(258, 6, -372), Vector3(252, 2, -398)]]
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(90): await process_frame
		var samples: Array[float] = []
		for i in range(240):
			var t0 := Time.get_ticks_usec()
			await process_frame
			samples.append((Time.get_ticks_usec() - t0) / 1000.0)
		samples.sort()
		# Script cost of the traffic systems (CPU, per physics step / frame), measured directly so
		# other load on the machine does not hide it.
		var cost := {}
		var fleet: Node = world.downtown.population.get_node_or_null("CivicFleet") if world.downtown != null else null
		for entry: Array in [["city_traffic_ms", traffic, true], ["downtown_traffic_ms", fleet, true],
				["signals_ms", world.get_node_or_null("TrafficSignals"), false], ["street_vfx_ms", world.get_node_or_null("StreetVFX"), false]]:
			var node: Node = entry[1]
			if node == null: continue
			var t1 := Time.get_ticks_usec()
			for k in range(30):
				if entry[2]: node._physics_process(1.0 / 60.0)
				else: node._process(1.0 / 60.0)
			cost[entry[0]] = snappedf((Time.get_ticks_usec() - t1) / 30000.0, 0.001)
		report.views.append({"view": view[0], "median_ms": snappedf(samples[120], 0.01), "p95_ms": snappedf(samples[228], 0.01), "script": cost,
			"physics_ms": snappedf(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, 0.01),
			"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
	if not args.is_empty():
		var file := FileAccess.open(args[0], FileAccess.WRITE)
		file.store_string(JSON.stringify(report, "  "))
	print("PROFILE STREETS ", JSON.stringify(report))
	quit()
