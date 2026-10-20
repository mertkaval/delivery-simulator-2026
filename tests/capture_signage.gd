extends SceneTree
## Street names, park signs, busts and the Atatürk Square monument.
## usage: godot --path . --script res://tests/capture_signage.gd -- <prefix> [hour]
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	var prefix: String = args[0] if args.size() > 0 else "sign"
	var hour: float = float(args[1]) if args.size() > 1 else 15.5
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 55
	var signage: StreetSignage = world.signage
	print("SIGNS ", signage.signs.size(), " BUSTS ", signage.busts.size(), " MONUMENT ", signage.monument_at)
	var corner: Vector3 = signage.signs.filter(func(s): return s.x_street == "ATATÜRK AV" and s.z_street == "RAUF ORBAY ST")[0].at
	var bust: Vector3 = signage.busts[2]
	var mt: Transform3D = signage.monument_transform
	var mu: Transform3D = signage.murals[0]
	var mu2: Transform3D = signage.murals[3]
	print("MURALS ", signage.murals.size())
	var views := [
		["mural", mu.origin + mu.basis.z * 13.0 + Vector3(2, -1.6, 0), mu.origin],
		["mural2", mu2.origin + mu2.basis.z * 10.0 + Vector3(-3, -1.6, 0), mu2.origin],
		["junction", corner + Vector3(5, 1.8, 5), corner + Vector3(0, 2.8, 0)],
		["junction_far", corner + Vector3(-14, 1.7, 18), corner + Vector3(0, 2.5, 0)],
		["park_sign", bust + Vector3(1.5, 1.7, 22), bust + Vector3(1.5, 1.0, 15)],
		["bust", bust + Vector3(1.2, 1.7, 3.5), bust + Vector3(0, 1.6, 0)],
		["monument", mt * Vector3(6, 2.0, 16), mt * Vector3(0, 4.5, 0)],
		["monument_plaque", mt * Vector3(0.5, 1.8, 5), mt * Vector3(0, 2.4, 1.2)]]
	for view in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(50): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/%s_%s.png" % [prefix, view[0]])
	print("STREET ", StreetNames.describe(Vector3(0, 0, -300)), " | ", StreetNames.describe(Vector3(30, 0, -398)), " | ", StreetNames.describe(Vector3(-44, 0, -330)))
	quit()
