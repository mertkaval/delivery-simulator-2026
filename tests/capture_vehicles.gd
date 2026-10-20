extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1440,900)
	root.msaa_3d=Viewport.MSAA_4X
	var world := Node3D.new()
	root.add_child(world)
	var environment := WorldEnvironment.new()
	var atmosphere := Environment.new()
	atmosphere.background_mode=Environment.BG_COLOR
	atmosphere.background_color=Color("8cabbc")
	atmosphere.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	atmosphere.ambient_light_energy=.7
	environment.environment=atmosphere
	world.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-42,-28,0)
	sun.shadow_enabled=true
	world.add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(60,60)
	floor_mesh.mesh=plane
	floor_mesh.material_override=CityMaterials.get_surface("737773")
	world.add_child(floor_mesh)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.position=Vector3(12,10,15)
	camera.look_at(Vector3(0,0,0))
	for i in range(5):
		var vehicle := CityAssets.create(CityAssets.CAR_TYPES[i])
		world.add_child(vehicle)
		vehicle.position=Vector3((i-2)*3.2,0,0)
		CityAssets.tint(vehicle,"VehiclePaint",Color(CityAssets.PAINTS[i]),.65,.26)
	for i in range(60): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/vehicle_lineup.png")
	print("VEHICLE CAPTURE PASS")
	quit()
