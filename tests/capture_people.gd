extends SceneTree
## In-game lineup of the twelve citizen variants (walk and idle) plus VFX views.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.0)
	world.get_node("CityLife").process_mode=Node.PROCESS_MODE_DISABLED
	var lineup := Node3D.new()
	world.add_child(lineup)
	for i in range(12):
		var person := LivingAssets.citizen(i)
		lineup.add_child(person)
		person.position=Vector3(-13.5+i*1.0 if i<6 else -13.5+(i-6)*1.0, 0.08, -40.0 if i<6 else -42.2)
		person.rotation.y=PI
		person.set_process(false)
		person.variants[0].visible=true
		var animator: AnimationPlayer=person.players[0]
		animator.play("Walk" if i%2==0 else "Idle")
		animator.seek(0.3+i*0.07,true)
		animator.pause()
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=42
	var views := [
		["lineup",Vector3(-10.9,1.45,-35.2),Vector3(-10.9,1.1,-41),15.0],
		["faces",Vector3(-11.0,1.6,-38.0),Vector3(-11.0,1.5,-40),15.0],
		["face_close",Vector3(-11.5,1.62,-39.1),Vector3(-11.5,1.6,-40),15.0],
		["face_close2",Vector3(-9.5,1.58,-39.1),Vector3(-9.5,1.55,-40),15.0],
		["fountain",Vector3(40,2.2,-480),Vector3(48,1.4,-475),11.0],
		["chimneys_morning",Vector3(30,9,-262),Vector3(53,9,-292),8.2],
		["night_street",Vector3(3,1.7,-300),Vector3(0,2,-360),22.5],
		["night_downtown",Vector3(146,1.7,-300),Vector3(146,8,-380),22.5]]
	for view in views:
		world.set_time(view[3])
		camera.position=view[1]
		camera.look_at(view[2])
		for i in range(90): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://tmp/people_%s.png" % view[0])
	print("PEOPLE CAPTURES done")
	quit()
