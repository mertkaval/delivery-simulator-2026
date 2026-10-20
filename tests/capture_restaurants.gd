extends SceneTree
## Corridor restaurant captures: storefront, dining room, counter and kitchen.
## usage: godot --path . --script res://tests/capture_restaurants.gd -- <prefix> [hour] [first] [count]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "rest"
	var hour: float = float(args[1]) if args.size() > 1 else 15.5
	var first: int = int(args[2]) if args.size() > 2 else 0
	var count: int = int(args[3]) if args.size() > 3 else 3
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 70
	var list: Array = world.restaurants.restaurants
	print("RESTAURANTS ", list.size(), " PICKUPS ", CityCatalog.PICKUPS.size())
	var report := []
	if first < 0:
		# Atatürk Avenue restaurants (pickups 0-2): street view and the counter.
		for i in range(3):
			var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
			for view in [["front", p + Vector3(-1, 1.7, 9), p + Vector3(-4, 1.8, -2)], ["inside", p + Vector3(-7.5, 1.65, 2.0), p + Vector3(-1.0, 1.2, -4.0)]]:
				camera.position = view[1]
				camera.look_at(view[2])
				for f in range(50): await process_frame
				await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_png("res://tmp/%s_avenue%d_%s.png" % [prefix, i, view[0]])
		quit()
		return
	for k in range(first, mini(first + count, list.size())):
		var r: Dictionary = list[k]
		var t: Transform3D = r.frame
		var door_inside: Vector3 = r.door_inside
		var local_door := t.affine_inverse() * door_inside
		var views := [
			["front", t * Vector3(local_door.x + 3.0, 1.7, 7.5), t * Vector3(local_door.x, 2.0, -3.0)],
			["dining", t * Vector3(local_door.x - 1.0, 1.65, -0.6), t * Vector3(local_door.x + 1.0, 1.4, -8.0)],
			["counter", t * Vector3(local_door.x + 2.5, 1.65, -5.0), t * Vector3(local_door.x + 1.5, 1.3, -9.5)],
			["kitchen", t * Vector3(local_door.x, 1.7, -10.6), t * Vector3(local_door.x, 1.2, -15.5)]]
		for view in views:
			camera.position = view[1]
			camera.look_at(view[2])
			for i in range(40): await process_frame
			var times: Array[float] = []
			for i in range(20):
				var before := Time.get_ticks_usec()
				await process_frame
				times.append(float(Time.get_ticks_usec() - before) / 1000)
			times.sort()
			report.append({"view": "%s_%s" % [r.id, view[0]], "median_ms": snappedf(times[10], 0.01), "draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)})
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://tmp/%s_%d_%s.png" % [prefix, k, view[0]])
	print("RESTAURANT_CAPTURE ", JSON.stringify(report))
	quit()
