extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.0)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 60
	var counts := {}
	for p in world.furniture.placed: counts[p.asset] = counts.get(p.asset, 0) + 1
	print("FURNITURE ", counts)
	var r: Dictionary = world.restaurants.restaurants[4]
	var views := [["works", Vector3(-4, 2.0, -526), Vector3(-26, 0.5, -537)], ["corridor", (r.frame as Transform3D) * Vector3(4, 1.7, 8.5), (r.frame as Transform3D) * Vector3(-2, 0.8, 2.5)], ["avenue", Vector3(4.5, 1.7, -420), Vector3(7, 0.5, -450)]]
	for v in views:
		camera.position = v[1]
		camera.look_at(v[2])
		for i in range(40): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/furn_%s.png" % v[0])
	quit()
