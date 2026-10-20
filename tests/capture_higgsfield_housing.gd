extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1440,900)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	game.set_process(false)
	game.player.set_physics_process(false)
	game.hud.hide()
	var camera := Camera3D.new()
	game.world.add_child(camera)
	camera.fov = 56
	camera.make_current()
	var report := []
	for spec in [["cedar_street",0,Vector3(6,4,13)], ["brick_house",10,Vector3(4,3,12)], ["hip_house",1,Vector3(-5,4,13)], ["side_street",3,Vector3(5,4,13)], ["porch_detail",0,Vector3(2,0,7)]]:
		game.session.calendar_minutes = 16 * 60
		game.world.set_time(16)
		var target: Vector3 = CityCatalog.address_position(spec[1]) + Vector3(0,1.2,-3)
		game.player.position = target + Vector3(0,0,8)
		camera.position = target + spec[2]
		camera.look_at(target)
		for i in range(45): await process_frame
		var elapsed := []
		for i in range(60):
			var before := Time.get_ticks_usec()
			await process_frame
			elapsed.append((Time.get_ticks_usec()-before)/1000.0)
		elapsed.sort()
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/housing_%s.png" % spec[0])
		report.append({"view":spec[0],"median_ms":elapsed[30],"p95_ms":elapsed[57],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),"texture_mib":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576.0})
	game.session.calendar_minutes = 21 * 60
	game.world.set_time(21)
	for i in range(35): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/housing_night.png")
	var file := FileAccess.open("res://tmp/housing_metrics.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	print("HOUSING CAPTURES COMPLETE")
	quit()
