extends SceneTree
## Rendered captures + frame timing of front-yard planting and bins (run WITHOUT --headless):
##   Godot --path . --script res://tests/capture_yards.gd -- <out_dir> <prefix> [views|all] [hour]
## Views: street (sidewalk by 105, 1.7 m eye, like the courier's view), street_far (from the
## road), close
## (front yard of 105 three-quarter), porch (walk and steps of 105), row (a run of front yards),
## hedge (a lot with a front hedge), lane (rear-lane yard bins), bench (avenue bench + litter bin),
## park_bins (park entrance bins), corridor (corridor restaurant bins), downtown (kerbside bins).
## Saves <out_dir>/<prefix>_<view>.png at 1280x720 and prints one PERF line per view
## (median / p95 frame ms over 180 frames, draw calls, primitives).
func _initialize() -> void: call_deferred("run")

func lot_with(pred: Callable) -> Dictionary:
	for lot in ResidentialLayout.lots():
		if pred.call(lot): return lot
	return {}

func run() -> void:
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var prefix: String = args[1] if args.size() > 1 else "yard"
	var only: PackedStringArray = args[2].split(",") if args.size() > 2 and args[2] != "all" else PackedStringArray()
	var hour: float = float(args[3]) if args.size() > 3 else 14.0
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	camera.fov = 70
	camera.far = 3000
	world.add_child(camera)
	camera.current = true
	var views: Array = []
	var lot := ResidentialLayout.delivery_lot(0)   # 105 Atatürk Avenue
	var facing: Vector3 = lot.facing
	var side := facing.cross(Vector3.UP)
	var front: Vector3 = lot.front
	var door := ResidentialLayout.door_point(lot)
	views.append(["street", front + facing * 9.0 - side * 9.0 + Vector3(0, 1.7, 0), front - facing * 1.5 + side * 1.5 + Vector3(0, 1.0, 0)])
	views.append(["street_far", front + facing * 16.0 + side * 9.0 + Vector3(0, 1.7, 0), front - facing * 3.0 - side * 4.0 + Vector3(0, 1.4, 0)])
	views.append(["close", front + facing * 6.5 + side * 5.5 + Vector3(0, 1.7, 0), front - facing * 1.0 - side * 1.5 + Vector3(0, 0.6, 0)])
	views.append(["porch", door + facing * 5.0 - side * 2.6 + Vector3(0, 0.7, 0), door - facing * 0.5 + Vector3(0, -0.6, 0)])
	views.append(["row", front + facing * 7.0 + side * 14.0 + Vector3(0, 1.7, 0), front - side * 6.0 + Vector3(0, 0.8, 0)])
	var hedge_lot := lot_with(func(l: Dictionary) -> bool: return l.fence == "hedge" and absf(float(l.line_x)) == 10.5)
	if not hedge_lot.is_empty():
		var hf: Vector3 = hedge_lot.facing
		var hs := hf.cross(Vector3.UP)
		views.append(["hedge", Vector3(hedge_lot.front) + hf * 9.0 + hs * 6.0 + Vector3(0, 1.7, 0), Vector3(hedge_lot.front) - hs * 1.0 + Vector3(0, 0.7, 0)])
	# Rear lane behind 105: the yard bins stand at the back of the lot.
	var back := -(float(lot.depth) - ResidentialLayout.SETBACK)
	var t := ResidentialLayout.transform(lot)
	var bins_at: Vector3 = t * Vector3(-float(lot.width) / 2 + 1.4, 0, back - 0.6)
	views.append(["lane", bins_at - facing * 3.5 + side * 3.0 + Vector3(0, 1.7, 0), bins_at + Vector3(0, 0.6, 0)])
	# Avenue bench + litter bin and other bins (StreetFurniture.placed).
	var furniture: StreetFurniture = null
	for c in world.get_children():
		if c is StreetFurniture: furniture = c
	var bench_bin := Vector3.INF
	var park_bin := Vector3.INF
	var corridor_bin := Vector3.INF
	if furniture != null:
		for p in furniture.placed:
			var at: Vector3 = p.at
			if bench_bin == Vector3.INF and String(p.asset).begins_with("litter_bin") and absf(at.z - front.z) < 60.0: bench_bin = at
			if park_bin == Vector3.INF and p.asset == "trash_bin" and absf(at.x) < 80.0 and at.z < -100.0: park_bin = at
			if corridor_bin == Vector3.INF and p.asset == "recycle_bin" and absf(at.x) > 60.0: corridor_bin = at
	if bench_bin != Vector3.INF:
		var out_dir := Vector3(-signf(bench_bin.x), 0, 0)
		views.append(["bench", bench_bin + out_dir * 2.6 + Vector3(0, 1.6, 2.4), bench_bin + Vector3(0, 0.5, -0.4)])
	if park_bin != Vector3.INF: views.append(["park_bins", park_bin + Vector3(1.5, 1.6, 3.0), park_bin + Vector3(0.2, 0.5, 0)])
	if corridor_bin != Vector3.INF: views.append(["corridor", corridor_bin + Vector3(2.4, 1.6, 2.4), corridor_bin + Vector3(-0.4, 0.5, 0)])
	# Downtown kerbside bins: the trash_bin collider nearest (180, -268).
	var dt := Vector3(180, 0, -268)
	var best := INF
	for n in world.find_children("*", "CollisionShape3D", true, false):
		if str(n.get_meta("prop", "")) != "trash_bin": continue
		var at: Vector3 = (n as Node3D).global_position
		if at.x > 120.0 and at.distance_to(dt) < best:
			best = at.distance_to(dt)
			dt = at
	views.append(["downtown", Vector3(dt.x + 2.2, 1.6, dt.z + 2.6), Vector3(dt.x - 0.3, 0.45, dt.z)])
	for view in views:
		if not only.is_empty() and not only.has(view[0]): continue
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(60): await process_frame
		var samples: Array[float] = []
		for i in range(180):
			var t0 := Time.get_ticks_usec()
			await process_frame
			samples.append((Time.get_ticks_usec() - t0) / 1000.0)
		samples.sort()
		var img := root.get_texture().get_image()
		var path := "%s/%s_%s.png" % [out, prefix, view[0]]
		img.save_png(path)
		print("PERF %s median_ms=%.2f p95_ms=%.2f draw_calls=%d primitives=%d -> %s" % [view[0], samples[90], samples[171],
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME), path])
	quit()
