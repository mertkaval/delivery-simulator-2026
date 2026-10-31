extends SceneTree
## Frame-time, boot and memory budgets on the reference machine (RTX 3070 laptop), rendered:
##   godot --path . --script res://tests/perf_budget_test.gd [-- res://assets/cityforge_roads/]
## With a Port Halden build's folder it rides that city instead (the courier's start past the first delivery doors).
## Boots the real game (no save writes), starts a new game and rides the courier at bicycle speed
## past the first delivery addresses for RIDE_S seconds. Fails when a budget is exceeded, so
## regressions (a HUD redrawing every frame, uncompressed textures, a heavy NPC) are caught the day
## they land. Investigate with tests/perf_probe.gd (attrib / census / exp modes).
## Measured 2026-10-23: boot ready ~18 s, first frame ~1.9 s, median ~22 ms, p95 ~32 ms, ~5.5 GB VRAM.
const BUDGET := {"boot_ready_s": 25.0, "first_frame_s": 4.0, "median_ms": 28.0, "p95_ms": 40.0, "vram_mb": 6500.0}
const RIDE_S := 30.0
const SPEED := 9.0
var checks := 0
var failures := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		print("FAIL: ", label)
	else:
		print("PASS ", label)

func _initialize() -> void: call_deferred("run")

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var city_args := OS.get_cmdline_user_args()
	var port_dir := str(city_args[0]) if city_args.size() > 0 and str(city_args[0]).begins_with("res://") else ""
	if port_dir != "":
		CedarNeighborhood.city_override = "port_halden"
		CityForgeWorld.use_city(port_dir)
	var t0 := Time.get_ticks_usec()
	var app: Node = (load("res://app/app_root.tscn") as PackedScene).instantiate()
	app.set("save_enabled", false)
	root.add_child(app)
	var ready_s := (Time.get_ticks_usec() - t0) / 1e6
	var f0 := Time.get_ticks_usec()
	await process_frame
	var first_s := (Time.get_ticks_usec() - f0) / 1e6
	app.call("on_main_menu", "new_game")
	for i in 60: await process_frame
	var player: Node3D = app.get("player")
	var route: Array[Vector3] = [player.global_position]
	var port: CityForgeWorld = null
	if port_dir != "":
		port = (app.get("world") as Node).get("port")
		var doors: Array = (app.get("world") as Node).get("doors")
		for i in 6: route.append(doors[i])
	else:
		for i in 6:
			var lot: Dictionary = ResidentialLayout.delivery_lot(i)
			route.append(Vector3(lot.front) + Vector3(lot.facing) * 6.0)
	var times: Array[float] = []
	var pos: Vector3 = route[0]
	var seg := 0
	var elapsed := 0.0
	var last := Time.get_ticks_usec()
	while elapsed < RIDE_S:
		await process_frame
		var now := Time.get_ticks_usec()
		var ms := (now - last) / 1000.0
		last = now
		elapsed += ms / 1000.0
		times.append(ms)
		var target: Vector3 = route[mini(seg + 1, route.size() - 1)]
		var flat := Vector3(target.x - pos.x, 0, target.z - pos.z)
		var step := SPEED * minf(ms, 100.0) / 1000.0
		if flat.length() <= step: seg = (seg + 1) % (route.size() - 1)
		else: pos += flat.normalized() * step
		player.global_position = Vector3(pos.x, (port.ground_height(pos) if port != null else 0.0) + 0.2, pos.z)
		if flat.length() > 0.1: player.look_at(player.global_position + flat.normalized(), Vector3.UP)
	times = times.slice(5)
	times.sort()
	var median := times[times.size() / 2]
	var p95 := times[int(times.size() * 0.95)]
	var vram := Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0
	check(ready_s <= BUDGET.boot_ready_s, "boot ready %.1f s <= %.0f s" % [ready_s, BUDGET.boot_ready_s])
	check(first_s <= BUDGET.first_frame_s, "first frame %.1f s <= %.0f s" % [first_s, BUDGET.first_frame_s])
	check(median <= BUDGET.median_ms, "ride median frame %.1f ms <= %.0f ms" % [median, BUDGET.median_ms])
	check(p95 <= BUDGET.p95_ms, "ride p95 frame %.1f ms <= %.0f ms" % [p95, BUDGET.p95_ms])
	check(vram <= BUDGET.vram_mb, "video memory %.0f MB <= %.0f MB" % [vram, BUDGET.vram_mb])
	print("PERF BUDGET %s: %d checks, %d failures%s" % ["PASS" if failures == 0 else "FAIL", checks, failures, (" (" + port_dir + ")") if port_dir != "" else ""])
	quit(1 if failures else 0)
