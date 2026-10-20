extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	var scene := Node3D.new()
	root.add_child(scene)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode=Environment.BG_COLOR
	env.background_color=Color("687881")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color("d2d9dd")
	env.ambient_light_energy=.6
	environment.environment=env
	scene.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-35,-30,0)
	sun.light_energy=1.2
	sun.shadow_enabled=true
	scene.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(200,200)
	ground.mesh=plane
	var grey := StandardMaterial3D.new()
	grey.albedo_color=Color("515b61")
	grey.roughness=.85
	ground.material_override=grey
	scene.add_child(ground)
	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.current=true
	camera.position=Vector3(2,1.5,-3.2)
	camera.look_at(Vector3(0,1,0))
	camera.fov=43
	var asset := OS.get_cmdline_user_args()[0] if OS.get_cmdline_user_args().size()>0 else "citizen_0"
	var model: Node3D=load("res://world/living_city/assets/"+asset+".glb").instantiate()
	scene.add_child(model)
	if not asset.begins_with("citizen"):
		camera.position=Vector3(4,2.3,-5.8)
		camera.look_at(Vector3(0,.8,0))
	var player: AnimationPlayer=model.find_child("AnimationPlayer",true,false)
	if player: print("CITIZEN ANIMATIONS ",player.get_animation_list())
	if player:
		for name in player.get_animation_list():
			if "Walk" in name:
				player.play(name)
				player.seek(.22,true)
				player.pause()
	for i in range(30): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/living_"+asset+".png")
	quit()
