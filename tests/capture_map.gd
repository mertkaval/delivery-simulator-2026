extends SceneTree
## Orthographic top-down city map: tmp/city_map.png (north = -Z at the top).
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1800,1400)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(12.5)
	# Map render: no haze, no horizon hills.
	world.atmosphere.fog_enabled=false
	world.atmosphere.ssil_enabled=false
	for child in world.get_children():
		if str(child.name).contains("horizon") or (child is Node3D and child.scene_file_path.contains("horizon")): child.visible=false
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=800.0 # metres covered vertically
	camera.far=600.0
	# Centre on the whole map: x -120..630, z -710..70.
	# Orthographic: height doesn't change framing; keep everything inside its LOD ranges.
	camera.position=Vector3(255,300,-320)
	camera.rotation_degrees=Vector3(-90,0,0)
	for i in range(120): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/city_map.png")
	print("MAP done")
	quit()
