extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.mode=Window.MODE_WINDOWED
	root.size=Vector2i(1280,720)
	var track=load("res://tests/repaired_car_track.tscn").instantiate()
	root.add_child(track)
	track.reset_car(Vector3(0,.02,0))
	track.player.set_physics_process(false)
	var camera: Camera3D=track.review_camera
	camera.fov=44
	camera.make_current()
	for view in [{"name":"front","pos":Vector3(5,2.8,-6)},{"name":"rear","pos":Vector3(-5,2.6,6)},{"name":"side","pos":Vector3(7,1.9,0)},{"name":"steering","pos":Vector3(-4,1.8,-4)}]:
		camera.position=view.pos
		camera.look_at(Vector3(0,.75,0))
		if view.name=="steering":track.player.bicycle.update_driving_visuals(0,.45)
		for i in range(12):await process_frame
		await RenderingServer.frame_post_draw
		var file="res://assets/vehicles/repaired_car/previews/godot_%s.png"%view.name
		root.get_texture().get_image().save_png(file)
		print("CAPTURE "+file)
	print("CAR_CAPTURE_PASS")
	track.queue_free()
	await process_frame
	quit()
