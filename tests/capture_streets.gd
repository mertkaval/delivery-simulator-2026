extends SceneTree
## Native captures of the Blender street kit: lane markings, bike lanes, junctions, crossings.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=60
	var views := [
		["driver",Vector3(1.95,1.25,-30),Vector3(1.9,0.6,-90)],
		["bike_lane",Vector3(4.6,1.6,-262),Vector3(4.7,0.2,-282)],
		["junction",Vector3(18,14,-372),Vector3(0,0,-398)],
		["side_junction",Vector3(80,12,-380),Vector3(64,0,-398)],
		["crossing",Vector3(-7,4.5,-75),Vector3(0,0,-93)],
		["junction_top",Vector3(0,34,-398),Vector3.ZERO],
		["connector",Vector3(58,9,-528),Vector3(100,0,-538)]]
	for view in views:
		camera.position=view[1]
		if view[2]==Vector3.ZERO: camera.rotation_degrees=Vector3(-90,0,0)
		else: camera.look_at(view[2])
		for i in range(60): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/streets_"+view[0]+".png")
	print("STREET CAPTURES done")
	quit()
