extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	root.msaa_3d=Viewport.MSAA_4X
	var scene := Node3D.new()
	root.add_child(scene)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode=Environment.BG_SKY
	var sky := Sky.new()
	sky.sky_material=ProceduralSkyMaterial.new()
	env.sky=sky
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color("c3d0d5")
	env.ambient_light_energy=.45
	env.ssao_enabled=true
	env.ssao_intensity=1.5
	environment.environment=env
	scene.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-38,-24,0)
	sun.light_energy=1.1
	sun.shadow_enabled=true
	scene.add_child(sun)
	var block := DowntownDistrict.new()
	if "--district" in OS.get_cmdline_user_args(): block.block_count=9
	scene.add_child(block)
	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.current=true
	camera.fov=65
	for view in [["frontage",Vector3(247,1.7,-252),Vector3(189,4,-282)],["interior",Vector3(170,1.7,-269),Vector3(170,1.5,-274)],["intersection",Vector3(258,3.4,-247),Vector3(224,8,-303)],["alley",Vector3(247,1.7,-328),Vector3(187,2,-328)],["roof",Vector3(264,42,-245),Vector3(197,6,-328)]]:
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(50): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/urban_benchmark_"+view[0]+".png")
		print("URBAN BLOCK ",view[0]," calls=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	quit()
