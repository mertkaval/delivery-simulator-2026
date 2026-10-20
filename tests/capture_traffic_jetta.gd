extends SceneTree
## Traffic Jettas: count them, let traffic run, then frame two of them.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 50
	var jettas: Array[Node3D] = []
	for n in world.find_children("*", "Node3D", true, false):
		if n.has_method("update_driving_visuals") and n.get("traffic") == true: jettas.append(n)
	print("TRAFFIC JETTAS ", jettas.size())
	for i in range(240): await physics_frame
	for k in range(mini(2, jettas.size())):
		var car: Node3D = jettas[k * 2] if jettas.size() > k * 2 else jettas[k]
		var at := car.global_position
		var fwd := -car.global_basis.z
		camera.position = at + fwd * 7.0 + car.global_basis.x * 4.0 + Vector3(0, 1.6, 0)
		camera.look_at(at + Vector3(0, 0.7, 0))
		for f in range(4): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/traffic_jetta_%d.png" % k)
		print("CAR ", k, " at ", at, " moved_parent ", car.get_parent().name)
	quit()
