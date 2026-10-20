extends SceneTree
var checks := 0
var failures := 0
var metrics := {}
func _initialize() -> void: call_deferred("run")
func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		printerr("FAIL: "+message)
func frames(n: int) -> void:
	for i in range(n): await physics_frame
func run() -> void:
	var track = load("res://tests/jetta_track.tscn").instantiate()
	root.add_child(track)
	await frames(20)
	var p: CourierPlayer = track.player
	var car = p.bicycle
	check(car.get_meta("wheelbase",0)>2.6,"Nonzero measured wheelbase")
	for pivot in car.front_pivots:check(pivot.position.z< -1,"Front axle is forward of body centre")
	check(car.steering_wheels.size()==3,"Steering wheel present in all LODs")
	p.session.calendar_minutes=21*60
	car._process(0)
	for light in car._headlights:check(light.light_energy>0,"Night headlights emit light")
	car.update_driving_visuals(0,0,true)
	car._process(0)
	for material in car._tail_materials:check(material.emission_energy_multiplier>2,"Brake lights brighten")
	car.update_driving_visuals(0,0,false)
	p.session.calendar_minutes=12*60
	car._process(0)
	for light in car._headlights:check(is_zero_approx(light.light_energy),"Day headlights switch off")
	check(car.axle_nodes.size()==12,"Four axle nodes per LOD")
	check(car.front_pivots.size()==6,"Two steering pivots per LOD")
	check(p.body_collision.shape is BoxShape3D,"Simplified box collision")
	check(absf(p.position.y)<.025,"Ground contact puts wheel bottoms at road height: %.4f"%p.position.y)
	var bounds := AABB()
	var first := true
	var triangles := 0
	var materials := []
	for mesh in car.get_node("LOD0").find_children("*","MeshInstance3D",true,false):
		var box: AABB = car.global_transform.affine_inverse()*mesh.global_transform*mesh.get_aabb()
		bounds=box if first else bounds.merge(box)
		first=false
		for s in range(mesh.mesh.get_surface_count()):
			var arr = mesh.mesh.surface_get_arrays(s)
			triangles += int(arr[Mesh.ARRAY_INDEX].size()/3) if arr[Mesh.ARRAY_INDEX].size()>0 else int(arr[Mesh.ARRAY_VERTEX].size()/3)
			check(arr[Mesh.ARRAY_TEX_UV].size()>0,"UVs exist")
			var mat = mesh.get_active_material(s)
			check(mat!=null,"Material resolves")
			if mat is StandardMaterial3D:
				if mat.albedo_texture: check(mat.albedo_texture.get_width()<=2048,"Runtime textures fit budget")
				materials.append({"name":mat.resource_name,"metallic":mat.metallic,"roughness":mat.roughness,"albedo":str(mat.albedo_color),"texture":str(mat.albedo_texture.get_size()) if mat.albedo_texture else "none"})
	metrics["lod0_triangles"]=triangles
	metrics["bounds"]=str(bounds)
	metrics["materials"]=materials
	check(bounds.size.z>4.65 and bounds.size.z<4.85,"Metre-scale length")
	check(bounds.size.y>1.4 and bounds.size.y<1.6,"Metre-scale height")
	check(triangles<140000,"Hero mesh triangle ceiling")
	var centers := []
	for wheel in car.axle_nodes.slice(0,4):
		centers.append(wheel.global_position)
		check(wheel.transform.basis.is_equal_approx(Basis.IDENTITY),"Neutral axle orientation")
	car.update_driving_visuals(.5,.4)
	var sw: Node3D=car.steering_wheels[0]
	var sw_rest: Transform3D=sw.get_meta("rest")
	check(not sw.transform.basis.is_equal_approx(sw_rest.basis),"Cabin steering wheel rotates")
	check(sw.position.distance_to(sw_rest.origin)<.001,"Steering wheel centre stays fixed")
	for i in range(4):check(car.axle_nodes[i].global_position.distance_to(centers[i])<.001,"Steering/spin preserve axle centres")
	car.update_driving_visuals(-.5,0)
	var start := p.position
	Input.action_press("move_forward")
	await frames(180)
	Input.action_release("move_forward")
	metrics["forward_speed_ms"]=p.riding_speed
	metrics["forward_distance_m"]=start.z-p.position.z
	check(p.riding_speed>9 and p.riding_speed<=12.01,"Acceleration approaches forward cap")
	check(p.position.z<start.z-12,"Moves toward −Z")
	var phase_before: float=car.wheel_phase
	await frames(1)
	check(wrapf(car.wheel_phase-phase_before,-PI,PI)<0,"Forward wheel roll has correct sign")
	Input.action_press("jump")
	await frames(90)
	Input.action_release("jump")
	check(absf(p.riding_speed)<.01,"Brakes stop vehicle")
	var stopped := p.position
	await frames(30)
	check(p.position.distance_to(stopped)<.02,"No idle drift")
	track.reset_car()
	Input.action_press("move_back")
	await frames(120)
	Input.action_release("move_back")
	metrics["reverse_speed_ms"]=p.riding_speed
	check(p.riding_speed< -2.9 and p.riding_speed>=-3.01,"Reverse speed cap")
	check(p.position.z>7,"Reverse moves toward +Z")
	phase_before=car.wheel_phase
	await frames(1)
	check(wrapf(car.wheel_phase-phase_before,-PI,PI)>0,"Reverse roll has correct sign")
	for action in ["move_left","move_right"]:
		track.reset_car()
		Input.action_press("move_forward")
		Input.action_press(action)
		await frames(120)
		var left: bool = action=="move_left"
		check(p.rotation.y>.2 if left else p.rotation.y<-.2,"Steers "+action)
		for pivot in car.front_pivots:check(pivot.rotation.y>0 if left else pivot.rotation.y<0,"Front wheel steering follows input")
		Input.action_release(action)
		Input.action_release("move_forward")
	track.reset_car(Vector3(0,.03,-48))
	Input.action_press("move_forward")
	await frames(180)
	Input.action_release("move_forward")
	metrics["barrier_stop_z"]=p.position.z
	check(p.position.z> -52.7,"Collision prevents barrier penetration")
	check(absf(p.riding_speed)<.1,"Collision stops speed")
	track.reset_car()
	await frames(10)
	var message := p.toggle_bicycle()
	check(not p.mounted,"Dismount: "+message)
	check(p.parked_body.collision_layer==1,"Parked car collision enabled")
	await frames(5)
	message=p.toggle_bicycle()
	check(p.mounted,"Remount: "+message)
	check(p.parked_body.collision_layer==0,"Mounted car excludes parked collider")
	metrics["checks"]=checks; metrics["failures"]=failures
	var f := FileAccess.open("res://assets/vehicles/jetta_gli_2025/test_results.json",FileAccess.WRITE)
	f.store_string(JSON.stringify(metrics,"\t"));f.close()
	print("JETTA_TEST %s: %d checks, %d failures; %s"%["PASS" if failures==0 else "FAIL",checks,failures,JSON.stringify(metrics)])
	track.queue_free()
	await process_frame
	quit(1 if failures else 0)

