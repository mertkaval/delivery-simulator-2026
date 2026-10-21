extends SceneTree
## Native captures of the furnished Cedar House and the restaurant dressing (interior packs),
## plus frame times with the interior props shown and hidden.
## usage: godot --path . --script res://tests/capture_interiors.gd -- <out_dir> [hour] [mode]
##   mode "full" (default): every view + frame times; "perf": frame times only.
## Views: every room of the Cedar House from first-person height (doors opened), the porch,
## bakery counters (Pastry Shop, Dessert Shop, Local Diner), the Pancake House food bar,
## the Rainline Café counter downtown and a restaurant terrace with planter troughs.
var out_dir := "res://tmp"
var report: Array = []
var world: CedarNeighborhood
var props: Array[Node3D] = []

func _initialize() -> void: call_deferred("run")

## House coordinates (Blender axes, as in furnishing.json) to world.
func house(x: float, y: float, z: float) -> Vector3:
	return CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(x, z, -y)

func measure(camera: Camera3D, name: String) -> Dictionary:
	var times: Array[float] = []
	for i in range(60):
		var before := Time.get_ticks_usec()
		await process_frame
		times.append(float(Time.get_ticks_usec() - before) / 1000.0)
	times.sort()
	return {"view": name, "median_ms": snappedf(times[30], 0.01), "p90_ms": snappedf(times[54], 0.01),
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
		"camera": [snappedf(camera.global_position.x, 0.1), snappedf(camera.global_position.z, 0.1)]}

func shot(name: String, camera: Camera3D, at: Vector3, look: Vector3, save: bool = true, settle: int = 30) -> void:
	camera.position = at
	camera.look_at(look)
	for i in range(settle): await process_frame
	if save:
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out_dir.path_join("int_%s.png" % name))

func show_props(on: bool) -> void:
	for p in props:
		if is_instance_valid(p): p.visible = on

func perf(camera: Camera3D) -> void:
	var views := {
		"house_living": [house(0.9, -4.6, 2.35), house(-3.0, -2.6, 1.3)],
		"house_kitchen": [house(0.9, 3.8, 2.35), house(-3.0, 0.8, 1.3)],
		"cedar_lane_front": [house(1.1, -16.0, 1.75), house(0.0, -4.0, 1.5)],
		"avenue": [Vector3(-10.6, 1.75, -60.0), Vector3(-7.0, 1.0, -95.0)],
	}
	for name: String in views:
		var v: Array = views[name]
		await shot("", camera, v[0], v[1], false, 40)
		for on in [true, false]:
			show_props(on)
			for i in range(10): await process_frame
			var r := await measure(camera, name + ("" if on else "_props_hidden"))
			report.append(r)
		show_props(true)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out_dir = args[0]
	var hour: float = float(args[1]) if args.size() > 1 else 13.0
	var mode: String = args[2] if args.size() > 2 else "full"
	DirAccess.make_dir_recursive_absolute(out_dir)
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	world = CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 70
	camera.near = 0.05
	var home: Node3D = world.cedar_house
	for n in home.furnishing: props.append(n)
	for n in world.find_children("*", "Node3D", true, false):
		if n.has_meta("interior_dressing"): props.append(n)
	print("INTERIOR PROPS house=%d total=%d" % [home.furnishing.size(), props.size()])
	# open every door of the house
	for i in range(home.doors.size()): home.toggle_door(i)
	camera.position = house(1.1, -12.0, 1.7)
	for i in range(150): await physics_frame
	if mode != "perf":
		await shot("living_from_hall", camera, house(1.25, -3.9, 2.35), house(-3.0, -3.0, 1.3))
		await shot("living_tv", camera, house(-0.85, -1.5, 2.35), house(-3.8, -3.7, 1.35))
		await shot("living_from_kitchen", camera, house(-1.6, -0.15, 2.35), house(-2.4, -4.6, 1.2))
		await shot("kitchen_counter", camera, house(-1.1, 2.7, 2.35), house(-2.2, 5.3, 1.6))
		await shot("kitchen_dining", camera, house(0.9, 3.8, 2.35), house(-3.0, 0.8, 1.3))
		await shot("bedroom1", camera, house(2.25, -4.55, 2.35), house(3.6, -2.0, 1.2))
		await shot("bedroom2", camera, house(2.25, -0.1, 2.35), house(3.6, 2.6, 1.1))
		await shot("bathroom", camera, house(0.95, 4.1, 2.35), house(3.7, 4.6, 1.2))
		await shot("hall", camera, house(0.8, -4.9, 2.35), house(1.6, 2.5, 1.6))
		await shot("porch", camera, house(1.1, -10.2, 1.85), house(0.0, -6.0, 1.1))
		var restaurants: Node = world.find_child("Restaurants", true, false)
		if restaurants != null:
			for r: Dictionary in restaurants.restaurants:
				var t: Transform3D = r.frame
				var xe: float = (t.affine_inverse() * (r.door_inside as Vector3)).x
				match str(r.id):
					"pastry_shop", "dessert_shop", "local_diner":
						await shot("counter_" + str(r.id), camera, t * Vector3(xe + 0.9, 1.75, -5.0), t * Vector3(xe + 0.9, 1.0, -7.4))
					"pancake_house":
						await shot("food_bar", camera, t * Vector3(xe - 0.5, 1.8, -3.9), t * Vector3(xe - 0.5, 1.0, -7.4))
						await shot("food_bar_close", camera, t * Vector3(xe - 1.6, 1.6, -5.6), t * Vector3(xe - 0.9, 1.1, -7.3))
						await shot("terrace", camera, t * Vector3(xe + 2.6, 1.7, 4.6), t * Vector3(xe - 3.5, 0.4, 0.3))
		await shot("cafe_downtown", camera, Vector3(170.4, 1.7, -271.3), Vector3(169.4, 1.05, -273.6))
	await perf(camera)
	var text := JSON.stringify(report)
	print("INTERIOR_PERF ", text)
	var f := FileAccess.open(out_dir.path_join("int_perf.json"), FileAccess.WRITE)
	if f: f.store_string(text)
	quit()
