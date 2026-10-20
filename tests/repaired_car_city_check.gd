extends SceneTree
func _initialize() -> void:call_deferred("run")
func run() -> void:
	root.mode=Window.MODE_WINDOWED
	root.size=Vector2i(1280,720)
	var game=load("res://tests/repaired_car_city.tscn").instantiate()
	root.add_child(game)
	game.session.online=false
	game.set_process(false)
	for i in range(30): await physics_frame
	var start: Vector3=game.player.position
	Input.action_press("move_forward")
	for i in range(90):await physics_frame
	Input.action_release("move_forward")
	Input.action_press("jump")
	for i in range(40):await physics_frame
	Input.action_release("jump")
	var moved: float=game.player.position.distance_to(start)
	var ok: bool=moved>2 and absf(game.player.riding_speed)<.01 and not game.save_enabled and game.player.mounted
	game.player.set_physics_process(false)
	var cam:=Camera3D.new()
	game.add_child(cam)
	cam.position=game.player.position+Vector3(5,2.8,-6)
	cam.fov=48
	cam.look_at(game.player.position+Vector3(0,.75,0))
	cam.make_current()
	for i in range(45):await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://assets/vehicles/repaired_car/previews/godot_city.png")
	var times:=[]
	var previous:=Time.get_ticks_usec()
	for i in range(180):
		await process_frame
		var now:=Time.get_ticks_usec()
		times.append((now-previous)/1000.0)
		previous=now
	times.sort()
	var result: Dictionary={"pass":ok,"moved_m":moved,"stopped_speed_ms":game.player.riding_speed,"save_enabled":game.save_enabled,"resolution":str(root.size),"median_frame_ms":times[90],"p95_frame_ms":times[171],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),"texture_memory_mib":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576.0}
	var f:=FileAccess.open("res://assets/vehicles/repaired_car/city_test_results.json",FileAccess.WRITE)
	f.store_string(JSON.stringify(result,"\t"));f.close()
	print("REPAIRED_CAR_CITY %s: %s"%["PASS" if ok else "FAIL",JSON.stringify(result)])
	game.queue_free()
	await process_frame
	quit(0 if ok else 1)
