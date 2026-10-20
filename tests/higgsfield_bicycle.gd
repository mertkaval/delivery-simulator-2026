extends SceneTree
var failures := 0
func check(value: bool, label: String) -> void:
	if not value:
		failures += 1
		printerr("FAIL: " + label)
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1100, 850)
	var studio := Node3D.new()
	root.add_child(studio)
	var bike := CityAssets.create("bicycle")
	studio.add_child(bike)
	check(bike.has_meta("asset_source"), "Higgsfield provenance")
	var wheels := CityAssets.wheel_nodes(bike)
	check(wheels.size() == 2, "Exactly two animated wheels")
	check(bike.find_children("*", "MeshInstance3D", true, false).size() == 4, "Four batched meshes")
	check(bike.find_children("*", "Camera3D", true, false).is_empty(), "Studio cameras excluded")
	check(bike.find_children("*", "Light3D", true, false).is_empty(), "Studio lights excluded")
	for wheel in wheels:
		check(absf(wheel.position.y - .35) < .005, "Axle height")
		check(absf(absf(wheel.position.z) - .55) < .005, "Wheelbase")
		check(wheel.position.z < 0 if wheel.name == "WheelFront" else wheel.position.z > 0, "Travel direction")
		check(wheel.basis.is_equal_approx(Basis.IDENTITY), "Wheel animation axes")
	var player := CourierPlayer.new()
	player.session = DeliverySession.new()
	studio.add_child(player)
	player.set_physics_process(false)
	player.setup_bicycle()
	player.bicycle.position = Vector3(5,0,0)
	player.position = Vector3(6,0,0)
	await physics_frame
	player.toggle_bicycle()
	check(player.mounted, "Mount Higgsfield bicycle")
	player.toggle_bicycle()
	check(not player.mounted, "Dismount Higgsfield bicycle")
	player.bicycle.queue_free()
	player.queue_free()
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("526575")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("d1dfef")
	environment.environment.ambient_light_energy = .75
	studio.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40,-35,0)
	light.shadow_enabled = true
	studio.add_child(light)
	var floor := MeshInstance3D.new()
	floor.mesh = PlaneMesh.new()
	floor.mesh.size = Vector2(12,12)
	floor.material_override = CityMaterials.get_surface("939c9c")
	studio.add_child(floor)
	var camera := Camera3D.new()
	studio.add_child(camera)
	camera.position = Vector3(-2.8,1.75,-3.4)
	camera.look_at(Vector3(0,.53,0))
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.55
	camera.make_current()
	for i in range(24): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/higgsfield_bicycle_godot.png")
	print("HIGGSFIELD BICYCLE: 15 checks, ", failures, " failures")
	quit(failures)
