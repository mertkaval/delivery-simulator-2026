extends SceneTree
## Native captures of townspeople behaviour, plus frame times.
## usage: godot --path . --script res://tests/capture_npc_life.gd -- <out_dir> [hour] [mode]
##   mode "full" (default): every view; "perf": frame times only, with people on / hidden.
## Views: busy avenue sidewalk, corridor restaurant with seated diners and a waiter carrying a
## tray, avenue restaurant, park bench sitters, shop interior with clerk and customer,
## residential street, downtown pavement.
var out_dir := "res://tmp"
var report: Array = []

func _initialize() -> void: call_deferred("run")

func shot(name: String, camera: Camera3D, at: Vector3, look: Vector3, settle: int = 30) -> void:
	camera.position = at
	camera.look_at(look)
	for i in range(settle): await process_frame
	var times: Array[float] = []
	LivingCitizen.prof_usec = 0
	LivingCitizen.prof_calls = 0
	CitizenBrain.prof_usec = 0
	CitizenBrain.prof_calls = 0
	var proc: Array[float] = []
	var phys: Array[float] = []
	for i in range(40):
		var before := Time.get_ticks_usec()
		await process_frame
		times.append(float(Time.get_ticks_usec() - before) / 1000.0)
		proc.append(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0)
		phys.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
	times.sort()
	proc.sort()
	phys.sort()
	report.append({"view": name, "median_ms": snappedf(times[20], 0.01), "p90_ms": snappedf(times[36], 0.01),
		"process_ms": snappedf(proc[20], 0.01), "physics_ms": snappedf(phys[20], 0.01),
		"citizen_ms": snappedf(LivingCitizen.prof_usec / 40000.0, 0.01), "citizen_calls": LivingCitizen.prof_calls / 40,
		"brain_ms": snappedf(CitizenBrain.prof_usec / 40000.0, 0.01), "brain_calls": CitizenBrain.prof_calls / 40,
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
	await RenderingServer.frame_post_draw
	if name != "":
		root.get_texture().get_image().save_png(out_dir.path_join("npc_%s.png" % name))

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out_dir = args[0]
	var hour: float = float(args[1]) if args.size() > 1 else 13.0
	var mode: String = args[2] if args.size() > 2 else "full"
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	var life: Node = world.get_node("CityLife")
	var downtown: Node = world.find_child("DowntownActivity", true, false)
	var people := 0
	for n in world.find_children("*", "Node3D", true, false):
		if n is LivingCitizen: people += 1
	print("NPC COUNT people=%d avenue_life_walkers=%d downtown_walkers=%d seats=%d" % [people, life.pedestrians.size(), downtown.pedestrians.size() if downtown else 0, life.seats.size()])
	# Let people walk for a while so they spread out, sit down and get served.
	camera.position = Vector3(10.5, 1.7, -60)
	for i in range(240): await physics_frame
	if mode == "perf":
		await perf_views(camera)
		for hide in [true]:
			for n in world.find_children("*", "Node3D", true, false):
				if n is LivingCitizen: n.visible = not hide
			for n in world.find_children("*", "CharacterBody3D", true, false):
				if n.has_meta("purpose_brain"): n.process_mode = Node.PROCESS_MODE_DISABLED
			var before := report.size()
			await perf_views(camera)
			for k in range(before, report.size()): report[k].view += "_no_people"
		print("NPC_PERF ", JSON.stringify(report))
		quit()
		return
	await shot("avenue", camera, Vector3(-10.6, 1.75, -60), Vector3(-7.0, 1.0, -95))
	await shot("avenue_far", camera, Vector3(-10.4, 2.2, -120), Vector3(-6.5, 0.8, -170))
	# Corridor restaurant: wait until a waiter is carrying a tray to a table.
	var services: Array = world.restaurants.services
	var chosen: TableService = null
	# Services pause when nobody is near: stand by a restaurant that has a waiter.
	var near: TableService = null
	for s: TableService in services:
		if s.waiter != null and near == null: near = s
	camera.position = near.global_transform * Vector3(0, 1.7, 1.0)
	for frame in range(2400):
		if near.state == "GO" and near.path_i >= 2: chosen = near
		if chosen != null: break
		await physics_frame
	if chosen != null:
		var w := chosen.waiter.global_position
		var t: Transform3D = chosen.global_transform
		await shot("restaurant_waiter", camera, w + t.basis * Vector3(-2.4, 1.6, 2.6), w + Vector3(0, 0.9, 0), 2)
		# Then the table being served.
		for frame in range(900):
			if chosen.state == "SET" and chosen.timer < 0.3: break
			await physics_frame
		var tb: Dictionary = chosen.tables[chosen.current]
		var a: Vector3 = t * (tb.approach as Vector3)
		await shot("restaurant_serve", camera, a + t.basis * Vector3(1.6, 1.5, 1.8), a + t.basis * Vector3(-0.8, 0.7, 0), 2)
		await shot("restaurant_diners", camera, a + t.basis * Vector3(1.2, 1.3, -1.6), a + t.basis * Vector3(-1.0, 0.6, 0.0), 10)
	else:
		print("NPC no waiter in transit found")
	var avenue_service: Node3D = life.get_node("AvenueTableService_0")
	var p: Vector3 = avenue_service.global_position
	await shot("avenue_restaurant", camera, p + Vector3(-5.2, 1.6, 2.2), p + Vector3(-8.4, 0.7, -1.0))
	# Park bench sitters.
	var sitter: LivingCitizen = life.sitters[0] if life.sitters.size() > 0 else null
	if sitter != null:
		var g := sitter.global_transform
		var front := -g.basis.z.normalized()
		var side := g.basis.x.normalized()
		await shot("park_bench", camera, g.origin + front * 2.2 + side * 1.4 + Vector3(0, 1.1, 0), g.origin + Vector3(0, 0.6, 0))
		await shot("park_bench_side", camera, g.origin + side * 2.4 + front * 0.4 + Vector3(0, 0.8, 0), g.origin + Vector3(0, 0.55, 0))
	# Somebody who sat down on an avenue bench by themselves (wait for one).
	camera.position = Vector3(0, 40, -120)
	var seated: CitizenBrain = null
	for frame in range(4800):
		if frame % 30 == 0:
			for n in life.find_children("*", "Node", true, false):
				if n is CitizenBrain and n.state == "SEATED" and n.seat_timer > 5.0: seated = n
		if seated != null: break
		await physics_frame
	if seated != null:
		var g := seated.body.global_transform
		await shot("avenue_bench", camera, g.origin - g.basis.z * 2.4 + g.basis.x * 1.3 + Vector3(0, 1.2, 0), g.origin + Vector3(0, 0.6, 0), 20)
		await shot("avenue_bench_side", camera, g.origin + g.basis.x * 2.5 - g.basis.z * 0.3 + Vector3(0, 0.8, 0), g.origin + Vector3(0, 0.55, 0), 2)
	else:
		print("NPC nobody sat on an avenue bench")
	# Shop interior: clerk behind the counter and a browsing customer.
	var store: Vector3 = ShopCatalog.LOCATIONS["bikes"]
	await shot("shop", camera, store + Vector3(-2.0, 1.65, 4.4), store + Vector3(2.0, 1.0, -1.5))
	var store2: Vector3 = ShopCatalog.LOCATIONS["equipment"]
	await shot("shop_equipment", camera, store2 + Vector3(1.5, 1.65, 4.2), store2 + Vector3(-2.5, 1.0, -2.5))
	await shot("residential", camera, Vector3(12, 1.7, -264.5), Vector3(40, 1.0, -266))
	await shot("side_road", camera, Vector3(55.5, 1.7, -300), Vector3(57.5, 1.0, -340))
	await shot("downtown", camera, Vector3(254, 1.8, -300), Vector3(250, 1.0, -340))
	await perf_views(camera)
	print("NPC_CAPTURE ", JSON.stringify(report))
	quit()

func perf_views(camera: Camera3D) -> void:
	for v in [["perf_avenue", Vector3(10.6, 1.75, -40), Vector3(7.0, 1.1, -70)], ["perf_restaurants", Vector3(71, 1.7, -401), Vector3(104, 7, -398)],
			["perf_downtown", Vector3(254, 1.8, -300), Vector3(250, 1.0, -340)], ["perf_terraces", Vector3(58.5, 1.7, -292), Vector3(53, 4.5, -276)]]:
		await shot("", camera, v[1], v[2], 60)
		report[-1].view = v[0]
