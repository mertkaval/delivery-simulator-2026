extends SceneTree
## Animals: dog walker, cat, pigeon flock (on the ground and taking off), gull overhead.
## usage: godot --path . --script res://tests/capture_animals.gd -- <prefix>
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var prefix: String = OS.get_cmdline_user_args()[0] if OS.get_cmdline_user_args().size() > 0 else "animal"
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 40
	var life: AnimalLife = world.animals
	print("ANIMALS dogs ", life.dogs.size(), " cats ", life.cats.size(), " flocks ", life.flocks.size(), " birds ", life.birds.size(), " gulls ", life.gulls.size())
	camera.position = Vector3(0, 60, 400)
	for i in range(120): await process_frame
	# Dog walker: frame the owner and dog from the side.
	var d: Dictionary = life.dogs[0]
	var dog_root: Node3D = d.dog.root
	camera.position = dog_root.global_position + Vector3(4.5, 1.4, -2.0)
	camera.look_at(dog_root.global_position + Vector3(-0.3, 0.6, 0))
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_dog.png" % prefix)
	# Cat in a front yard (camera far enough not to spook it).
	var cat_root: Node3D = life.cats[3].cat.root
	var cat_dir: Vector3 = ResidentialLayout.delivery_lot(0).facing if false else Vector3.ZERO
	for c in life.cats: print("CAT at ", (c.cat.root as Node3D).global_position, " state ", c.state)
	camera.position = cat_root.global_position + Vector3(0, 3.2, 0) + (Vector3(1, 0, 0) if cat_root.global_position.x > 0 else Vector3(-1, 0, 0)) * -3.4
	camera.look_at(cat_root.global_position + Vector3(0, 0.2, 0))
	for i in range(30): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_cat.png" % prefix)
	# Pigeons: on the ground, then walk the camera in to spook them.
	var flock: Dictionary = life.flocks[0]
	var centre: Vector3 = flock.centre
	camera.position = centre + Vector3(0, 1.6, 9.0)
	camera.look_at(centre + Vector3(0, 0.2, 0))
	for i in range(30): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_pigeons.png" % prefix)
	camera.position = centre + Vector3(0, 1.6, 4.0)
	camera.look_at(centre + Vector3(0, 1.5, 0))
	for i in range(40): await process_frame
	print("FLOCK STATE ", flock.state)
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_takeoff.png" % prefix)
	var gull: Node3D = life.gulls[0].bird.root
	camera.position = gull.global_position + Vector3(0, -6, 10)
	camera.look_at(gull.global_position)
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s_gull.png" % prefix)
	quit()
