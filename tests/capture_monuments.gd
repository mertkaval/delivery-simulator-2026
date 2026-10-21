extends SceneTree
## Parks, monuments and sports: survey shots of the sites and in-context views of every placed
## monument asset (Atatürk Square, the equestrian monument, park busts, fountains, sculptures,
## basketball courts).
## usage: godot --path . --script res://tests/capture_monuments.gd -- <out_dir> [survey|final] [hour]
func _initialize() -> void: call_deferred("run")

func shot(camera: Camera3D, out: String, name: String, eye: Vector3, target: Vector3) -> void:
	camera.position = eye
	var up := Vector3.UP if absf((target - eye).normalized().y) < 0.98 else Vector3(0, 0, -1)
	camera.look_at(target, up)
	for i in range(40): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("%s/mon_%s.png" % [out, name])
	print("SHOT ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var mode: String = args[1] if args.size() > 1 else "final"
	var hour: float = float(args[2]) if args.size() > 2 else 15.5
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 55
	camera.far = 900
	for i in range(20): await process_frame
	var views: Array = []
	if mode == "survey":
		views = [
			["survey_ring_park", Vector3(-64, 46, -145), Vector3(-64, 0, -145.1)],
			["survey_inner_park", Vector3(-44, 40, -330), Vector3(-44, 0, -330.1)],
			["survey_square", Vector3(386, 40, -451), Vector3(386, 0, -451.1)],
			["survey_schoolyard", Vector3(600, 60, -601), Vector3(600, 0, -601.1)],
			["survey_circle", Vector3(64, 30, -398), Vector3(64, 0, -398.1)],
			["survey_ring_eye", Vector3(-40, 2.0, -140), Vector3(-64, 2, -145)]]
	else:
		var m: Variant = world.get("monuments")
		if m is Node and (m as Node).has_method("capture_views"):
			views = (m as Node).call("capture_views")
	for v in views: await shot(camera, out, v[0], v[1], v[2])
	quit()
