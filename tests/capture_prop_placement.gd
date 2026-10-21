extends SceneTree
## Native captures of procedural prop placement (PropPlacer): the Nezahat Onbaşı Street /
## Atatürk Avenue corner where a street light used to stand on the asphalt and jam the traffic,
## from a cyclist's first-person height, plus a wide residential street view.
## Usage: Godot_console.exe --path . --script res://tests/capture_prop_placement.gd [-- <out_dir>]
## (needs rendering; default out_dir res://tmp/)
func _initialize() -> void: call_deferred("run")

func run() -> void:
	var out := "res://tmp/"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0].trim_suffix("/") + "/"
	root.size = Vector2i(1600, 900)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(11.9)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 75
	# Let the traffic run for a while so the corner shows moving cars, not a queue.
	camera.position = Vector3(10, 1.6, 30)
	Engine.time_scale = 4.0
	for i in range(600): await physics_frame
	Engine.time_scale = 1.0
	for rec in world.placer.records:
		if rec.kind == "street_light" and Vector2(rec.at.x, rec.at.z).distance_to(Vector2(6, 44)) < 25:
			print("light pole at (%.1f, %.1f) %s" % [rec.at.x, rec.at.z, StreetNames.describe(rec.at)])
	var views := [
		# Riding north in the avenue's east bike lane towards the Nezahat Onbaşı corner.
		["nezahat_corner_bike", Vector3(4.7, 1.55, 24.0), Vector3(5.5, 1.3, 50.0)],
		# On Nezahat Onbaşı Street heading west to the corner, where the cars turn south.
		["nezahat_street_bike", Vector3(24.0, 1.55, 49.6), Vector3(0.0, 1.2, 46.0)],
		# Wide view down a residential stretch of the avenue: lights on the east kerb.
		["residential_wide", Vector3(14.0, 11.0, -118.0), Vector3(0.0, 0.0, -170.0)],
		# Estate road with a roundabout and frontage roads (curved-road lights, roundabout signs).
		["estate_wide", Vector3(-48.0, 16.0, -190.0), Vector3(-64.0, 0.0, -160.0)],
	]
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(45): await process_frame
		await RenderingServer.frame_post_draw
		var path: String = out + "props_" + view[0] + ".png"
		root.get_texture().get_image().save_png(path)
		print("saved ", ProjectSettings.globalize_path(path))
	# Any AI car stuck at the corner? (every car on the north loops should keep moving)
	var traffic := world.get_node("CityTraffic")
	var stopped := 0
	for car: Dictionary in traffic.drivers:
		if float(car.speed) < 0.1 and (car.body as Node3D).global_position.distance_to(Vector3(6, 0, 44)) < 30: stopped += 1
	print("cars stopped near the corner: %d" % stopped)
	print("PROP CAPTURES done")
	quit()
