extends SceneTree
## Bus lines: buses driving and dwelling, shelters with waiting passengers.
## usage: godot --path . --script res://tests/capture_buses.gd -- <prefix> [hour]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "bus"
	var hour: float = float(args[1]) if args.size() > 1 else 15.5
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	var system: BusSystem = world.buses
	print("BUS LINES ", system.lines.size(), " BUSES ", system.buses.size(), " STOPS ", system.stops.size())
	for line in system.lines: print("  line ", line.number, " length ", int(line.total), " stops ", line.stops.size())
	camera.position = Vector3(0, 40, -300)
	# Let the buses run for ~40 s of game time.
	var dwell_seen := 0
	for i in range(2400):
		await physics_frame
		for bus in system.buses:
			if bus.state == "dwell": dwell_seen += 1
	for bus in system.buses: print("  bus ", bus.body.name, " s=", int(bus.s), " v=", snappedf(bus.speed, 0.1), " state=", bus.state, " next=", bus.next_stop)
	print("DWELL FRAMES ", dwell_seen)
	var stop: Dictionary = system.stops[1]
	for st in system.stops: print("  stop line ", st.line, " kerb ", st.kerb)
	var t: Transform3D = stop.shelter
	var views := [
		["shelter", t * Vector3(4.5, 1.7, 9.0), t * Vector3(0, 1.2, 0)],
		["shelter_top", t * Vector3(0.0, 22.0, 6.0), t * Vector3(0, 0, 3.0)],
	]
	for k in range(views.size()):
		camera.position = views[k][1]
		camera.look_at(views[k][2])
		for f in range(30): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix, views[k][0]])
	# Follow two buses: kerb-side three-quarter view, then wait for a dwell.
	for b in range(2):
		var bus: Dictionary = system.buses[b * 2]
		for f in range(1800):
			await physics_frame
			if bus.state == "dwell" and bus.timer > 2.5: break
		var bt: Transform3D = bus.body.global_transform
		camera.position = bt * Vector3(7.5, 2.2, -12.0)
		camera.look_at(bt * Vector3(0, 1.5, -2.0))
		for f in range(4): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_bus%d.png" % [prefix, b])
		print("  captured bus ", bus.body.name, " state=", bus.state, " door=", snappedf(bus.door_open, 0.1))
	quit()
