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

## Paired toggles: median frame / process / physics time with a category switched off.
func sample(frames: int) -> Array:
	var times: Array[float] = []
	var phys: Array[float] = []
	var proc: Array[float] = []
	var last := Time.get_ticks_usec()
	for i in frames:
		await process_frame
		var now := Time.get_ticks_usec()
		times.append((now - last) / 1000.0)
		phys.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
		proc.append(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0)
		last = now
	times.sort()
	phys.sort()
	proc.sort()
	return [times[frames / 2], proc[frames / 2], phys[frames / 2]]

func experiments(app: Node) -> void:
	for i in 120: await process_frame
	var all: Array[Node] = root.find_children("*", "", true, false)
	var people: Array[Node] = []
	var brains: Array[Node] = []
	var walker_bodies: Array[Node] = []
	var drivers: Array[Node] = []
	for n in all:
		if n is LivingCitizen: people.append(n)
		elif n is CitizenBrain:
			brains.append(n)
			walker_bodies.append(n.get_parent())
		elif n.get_script() != null and str(n.get_script().resource_path).get_file() in ["traffic.gd", "population.gd", "service_traffic.gd", "bus_system.gd", "traffic_circles.gd"]:
			drivers.append(n)
	var env: Environment = (root.find_children("*", "WorldEnvironment", true, false)[0] as WorldEnvironment).environment
	var sun: DirectionalLight3D = root.find_children("*", "DirectionalLight3D", true, false)[0]
	var physics_nodes: Array[Node] = []
	for n in all:
		if n.is_physics_processing(): physics_nodes.append(n)
	var statics: Array[Node] = root.find_children("*", "StaticBody3D", true, false)
	var chars: Array[Node] = root.find_children("*", "CharacterBody3D", true, false)
	var only := OS.get_cmdline_user_args()
	var toggles := {
		"physics_server": func(on: bool) -> void: PhysicsServer3D.set_active(on),
		"navigation": func(on: bool) -> void: NavigationServer3D.set_active(on),
		"physics_scripts": func(on: bool) -> void:
			for n in physics_nodes: n.set_physics_process(on),
		"static_bodies": func(on: bool) -> void:
			for n in statics: (n as CollisionObject3D).process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED,
		"char_bodies": func(on: bool) -> void:
			for n in chars: (n as CollisionObject3D).process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED,
		"people_anim": func(on: bool) -> void:
			for n in people: n.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED,
		"people_visible": func(on: bool) -> void:
			for n in people: (n as Node3D).visible = on,
		"brains": func(on: bool) -> void:
			for n in brains: n.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED,
		"walker_bodies": func(on: bool) -> void:
			for n in walker_bodies:
				for c in n.get_children(): if c is CollisionShape3D: (c as CollisionShape3D).disabled = not on,
		"vehicle_ai": func(on: bool) -> void:
			for n in drivers: n.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED,
		"sun_shadows": func(on: bool) -> void: sun.shadow_enabled = on,
		"ssil": func(on: bool) -> void: env.ssil_enabled = on,
		"ssao": func(on: bool) -> void: env.ssao_enabled = on,
		"glow_fog": func(on: bool) -> void:
			env.glow_enabled = on
			env.fog_enabled = on,
	}
	if only.has("per_script"):
		var groups := {}
		for n in physics_nodes:
			var sc: Script = n.get_script()
			var k := "phys:" + (sc.resource_path.get_file() if sc else n.get_class())
			if not groups.has(k): groups[k] = []
			(groups[k] as Array).append(n)
		for k: String in groups:
			var list: Array = groups[k]
			toggles[k] = func(on: bool) -> void:
				for n: Node in list: n.set_physics_process(on)
			only.append(k)
	if only.has("per_process"):
		var groups := {}
		for n in all:
			if not n.is_processing(): continue
			var sc: Script = n.get_script()
			var k := "proc:" + (sc.resource_path.get_file() if sc else n.get_class())
			if not groups.has(k): groups[k] = []
			(groups[k] as Array).append(n)
		for k: String in groups:
			var list: Array = groups[k]
			toggles[k] = func(on: bool) -> void:
				for n: Node in list: n.set_process(on)
			only.append(k)
	for key: String in toggles:
		if only.size() > 3 and not only.has(key): continue
		var f: Callable = toggles[key]
		var base: Array = await sample(90)
		f.call(false)
		for i in 10: await process_frame
		var off: Array = await sample(90)
		f.call(true)
		for i in 10: await process_frame
		print("EXP %-15s frame %5.1f -> %5.1f (save %4.1f)  process %5.1f -> %5.1f  physics %5.1f -> %5.1f" % [key, base[0], off[0], base[0] - off[0], base[1], off[1], base[2], off[2]])

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
	if args.has("exp"):
		await experiments(app)
		quit()
		return
	if args.has("census"):
		var by := {}
		for n: Node in root.find_children("*", "", true, false):
			var key := n.get_class()
			var sc: Script = n.get_script()
			if sc: key = sc.resource_path.get_file()
			var row: Array = by.get(key, [0, 0, 0, 0])
			row[0] += 1
			if n.is_processing(): row[1] += 1
			if n.is_physics_processing(): row[2] += 1
			if n is CollisionObject3D: row[3] += 1
			if n is AnimationMixer and (n as AnimationMixer).active: row[3] += 0
			by[key] = row
		var rows: Array = []
		for k: String in by: rows.append([k] + by[k])
		rows.sort_custom(func(a: Array, b: Array) -> bool: return int(a[2]) + int(a[3]) > int(b[2]) + int(b[3]))
		for r: Array in rows.slice(0, 25): print("CENSUS %-34s nodes %6d process %5d physics %5d bodies %5d" % r)
		print("CENSUS physics active=%d pairs=%d islands=%d" % [Performance.get_monitor(Performance.PHYSICS_3D_ACTIVE_OBJECTS), Performance.get_monitor(Performance.PHYSICS_3D_COLLISION_PAIRS), Performance.get_monitor(Performance.PHYSICS_3D_ISLAND_COUNT)])
		var bodies := {}
		for n: Node in root.find_children("*", "CollisionObject3D", true, false): bodies[n.get_class()] = int(bodies.get(n.get_class(), 0)) + 1
		print("CENSUS bodies ", bodies)
		var cars := 0
		var car_nodes := 0
		var car_meshes := 0
		var car_lights := 0
		for n: Node in root.find_children("*", "CharacterBody3D", true, false):
			if not n.has_meta("car"): continue
			cars += 1
			car_nodes += n.find_children("*", "", true, false).size()
			car_meshes += n.find_children("*", "GeometryInstance3D", true, false).size()
			car_lights += n.find_children("*", "Light3D", true, false).size()
		print("CENSUS cars=%d nodes=%d meshes=%d lights=%d" % [cars, car_nodes, car_meshes, car_lights])
		var people_meshes := 0
		var skeletons := 0
		for n: Node in root.find_children("*", "Skeleton3D", true, false): skeletons += 1
		for n: Node in root.find_children("*", "MeshInstance3D", true, false):
			if (n as MeshInstance3D).skin != null or (n as MeshInstance3D).skeleton != NodePath(): people_meshes += 1
		var players := 0
		for n: Node in root.find_children("*", "AnimationPlayer", true, false): players += 1
		print("CENSUS skeletons=%d skinned_meshes=%d animation_players=%d lights=%d" % [skeletons, people_meshes, players, root.find_children("*", "Light3D", true, false).size()])
		quit()
		return
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
	var vp := root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var gpu: Array[float] = []
	var cpu_render: Array[float] = []
	LivingCitizen.prof_usec = 0
	CitizenBrain.prof_usec = 0
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
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		cpu_render.append(RenderingServer.viewport_get_measured_render_time_cpu(vp) + RenderingServer.get_frame_setup_time_cpu())
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
	print("PEOPLE per frame: animation %.2f ms, brains %.2f ms" % [LivingCitizen.prof_usec / 1000.0 / maxf(times.size(), 1), CitizenBrain.prof_usec / 1000.0 / maxf(times.size(), 1)])
	gpu.sort()
	cpu_render.sort()
	print("RENDER median gpu=%.1f ms p95 gpu=%.1f ms, render cpu=%.1f ms, process=%.1f ms physics=%.1f ms" % [gpu[gpu.size() / 2], gpu[int(gpu.size() * 0.95)], cpu_render[cpu_render.size() / 2],
		Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0])
	var sorted := times.duplicate()
	sorted.sort()
	var n := sorted.size()
	print("PERF frames=%d median=%.1f p95=%.1f p99=%.1f max=%.0f ms spikes>50ms=%d draws=%d nodes=%d static_mem_mb=%.0f vram_mb=%.0f" % [n,
		sorted[n / 2], sorted[int(n * 0.95)], sorted[int(n * 0.99)], sorted[n - 1], spikes,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0])
	quit()
