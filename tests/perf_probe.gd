extends SceneTree
## Boot + ride-through performance probe (run WITHOUT --headless; the player's save is never touched):
##   Godot --path . --script res://tests/perf_probe.gd -- [seconds=60] [speed_mps=9]
## Prints BOOT (scene load, city build in _ready, first frames), then rides the courier along a loop of
## delivery addresses at bicycle speed and prints every frame over 50 ms (SPIKE) with the engine's
## process / physics time, draw calls and object count, and a PERF summary (median / p95 / p99 / max).
## With "attrib" as an extra argument it stands at the start instead and pauses each subsystem
## (Neighborhood children, the player, app-level nodes) for 90 frames: ATTRIB lines rank them by
## how many ms of median frame time pausing them saves.
func _initialize() -> void: call_deferred("run")

func median_ms(frames: int) -> float:
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	for i in frames:
		await process_frame
		var now := Time.get_ticks_usec()
		times.append((now - last) / 1000.0)
		last = now
	times.sort()
	return times[frames / 2]

func attribute(app: Node) -> void:
	for i in 60: await process_frame
	var nodes: Array[Node] = []
	for c in app.get_node("Neighborhood").get_children():
		if c.get_script() != null: nodes.append(c)          # scripted subsystems only
	for c in app.get_children():
		if c.name != "Neighborhood": nodes.append(c)
	var rows: Array = []
	var total := 0.0
	for n in nodes:
		var base: float = await median_ms(60)               # paired baseline: the city drifts
		var mode := n.process_mode
		n.process_mode = Node.PROCESS_MODE_DISABLED
		var off: float = await median_ms(60)
		n.process_mode = mode
		total += base
		var script: Script = n.get_script()
		rows.append([base - off, "%s (%s)" % [n.name, script.resource_path.get_file() if script else n.get_class()]])
	rows.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]))
	print("ATTRIB baseline_median=%.1f ms over %d subsystems" % [total / maxf(nodes.size(), 1), nodes.size()])
	for r in rows.slice(0, 20): print("ATTRIB %6.1f ms  %s" % [float(r[0]), r[1]])

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var args := OS.get_cmdline_user_args()
	var seconds: float = float(args[0]) if args.size() > 0 else 60.0
	var speed: float = float(args[1]) if args.size() > 1 else 9.0
	var t0 := Time.get_ticks_usec()
	var packed: PackedScene = load("res://app/app_root.tscn")
	var t1 := Time.get_ticks_usec()
	var app: Node = packed.instantiate()
	app.set("save_enabled", false)
	root.add_child(app)                          # _ready builds the whole city
	var t2 := Time.get_ticks_usec()
	var first: Array[float] = []
	for i in 5:
		var f0 := Time.get_ticks_usec()
		await process_frame
		first.append((Time.get_ticks_usec() - f0) / 1000.0)
	print("BOOT load_scene_ms=%.0f ready_ms=%.0f first_frames_ms=%s" % [(t1 - t0) / 1000.0, (t2 - t1) / 1000.0, str(first)])
	var s0 := Time.get_ticks_usec()
	app.call("on_main_menu", "new_game")
	await process_frame
	print("BOOT new_game_ms=%.0f" % ((Time.get_ticks_usec() - s0) / 1000.0))
	for i in 30:
		await process_frame
	var player: Node3D = app.get("player")
	if args.has("attrib"):
		await attribute(app)
		quit()
		return
	var route: Array[Vector3] = [player.global_position]
	for i in 8:
		var lot: Dictionary = ResidentialLayout.delivery_lot(i)
		route.append(Vector3(lot.front) + Vector3(lot.facing) * 6.0)
	route.append(route[0])
	var times: Array[float] = []
	var spikes := 0
	var seg := 0
	var pos: Vector3 = route[0]
	var elapsed := 0.0
	var last := Time.get_ticks_usec()
	while elapsed < seconds:
		await process_frame
		var now := Time.get_ticks_usec()
		var ms := (now - last) / 1000.0
		last = now
		elapsed += ms / 1000.0
		times.append(ms)
		if ms > 50.0 and times.size() > 3:
			spikes += 1
			print("SPIKE t=%.1fs %.0f ms at %s process=%.1f physics=%.1f draws=%d objects=%d nodes=%d" % [elapsed, ms, str(pos.round()),
				Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0,
				Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
				Performance.get_monitor(Performance.OBJECT_NODE_COUNT)])
		# ride: move along the route at bicycle speed, looking ahead
		var target: Vector3 = route[(seg + 1) % route.size()]
		var step: float = speed * minf(ms, 100.0) / 1000.0
		var flat := Vector3(target.x - pos.x, 0, target.z - pos.z)
		if flat.length() <= step:
			seg = (seg + 1) % (route.size() - 1)
		else:
			pos += flat.normalized() * step
		player.global_position = Vector3(pos.x, 0.2, pos.z)
		if flat.length() > 0.1:
			player.look_at(player.global_position + flat.normalized(), Vector3.UP)
	var sorted := times.duplicate()
	sorted.sort()
	var n := sorted.size()
	print("PERF frames=%d median=%.1f p95=%.1f p99=%.1f max=%.0f ms spikes>50ms=%d draws=%d nodes=%d static_mem_mb=%.0f vram_mb=%.0f" % [n,
		sorted[n / 2], sorted[int(n * 0.95)], sorted[int(n * 0.99)], sorted[n - 1], spikes,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0])
	quit()
