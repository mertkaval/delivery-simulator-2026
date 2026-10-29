extends SceneTree
## Port Halden street-level performance (rendered, real time): the city world alone (no game systems) with the
## capture environment, a camera at 1.7 m flying along the road graph from the starter neighbourhood through
## downtown at 12 m/s (route() over city.json), collision following the camera. Prints the build time and
##   PERF median / p95 / max frame ms, draw calls, primitives (median), video memory
## so the CityForge streets and the Mert Road Studio streets can be compared on the same machine and route.
##   godot --path . --script res://tests/port_halden_streets_perf.gd -- [seconds=40]
var world: CityForgeWorld
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var seconds := float(args[0]) if args.size() > 0 else 40.0
	root.size = Vector2i(1600, 900)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)      # frame times, not the display's refresh
	Engine.max_fps = 0
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 300.0
	root.add_child(sun)
	var t0 := Time.get_ticks_msec()
	world = CityForgeWorld.new()
	root.add_child(world)
	var build_ms := Time.get_ticks_msec() - t0
	camera = Camera3D.new()
	camera.far = 3000.0
	root.add_child(camera)
	camera.current = true
	var path := world.route(world.to_world(1100, 1300), world.to_world(560, 1640))
	var pts: Array[Vector3] = []
	for p in path:
		var q := Vector3(p.x, 0, p.z)
		q.y = world.ground_height(q) + 1.7
		pts.append(q)
	var total := 0.0
	for i in range(1, pts.size()): total += pts[i - 1].distance_to(pts[i])
	print("ROUTE %d points, %.0f m, build %d ms" % [pts.size(), total, build_ms])
	camera.position = pts[0]
	for i in 30: await process_frame
	var times: Array[float] = []
	var spikes: Array[String] = []
	var draws: Array[int] = []
	var prims: Array[int] = []
	var travelled := 0.0
	var last := Time.get_ticks_usec()
	var start := last
	while (last - start) / 1e6 < seconds:
		await process_frame
		var now := Time.get_ticks_usec()
		var dt := (now - last) / 1e6
		last = now
		times.append(dt * 1000.0)
		if dt > 0.03: spikes.append("%.1fs %.0fms" % [(now - start) / 1e6, dt * 1000.0])
		draws.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
		prims.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
		travelled = fmod(travelled + 12.0 * minf(dt, 0.1), maxf(total, 1.0))
		var s := travelled
		for i in range(1, pts.size()):
			var L := pts[i - 1].distance_to(pts[i])
			if s <= L or i == pts.size() - 1:
				var f := clampf(s / maxf(L, 0.01), 0.0, 1.0)
				var p := pts[i - 1].lerp(pts[i], f)
				var ahead := pts[mini(i + 1, pts.size() - 1)] if f > 0.8 else pts[i]
				camera.position = p
				if ahead.distance_to(p) > 0.5: camera.look_at(Vector3(ahead.x, p.y - 0.3, ahead.z))
				break
			s -= L
		world.update_focus(camera.global_position, dt)
	times.sort()
	draws.sort()
	prims.sort()
	var n := times.size()
	print("PERF frames %d median %.1f ms p95 %.1f ms max %.1f ms | draw calls %d | primitives %d | video memory %.0f MB" % [n, times[n / 2], times[int(n * 0.95)], times[n - 1],
		draws[n / 2], prims[n / 2], RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576.0])
	print("SPIKES over 30 ms (time into the ride, frame): ", spikes)
	print("STATS ", world.stats)
	quit()
