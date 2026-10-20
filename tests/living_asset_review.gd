extends SceneTree
var camera: Camera3D
func _initialize() -> void: call_deferred("run")
func capture(name: String) -> void:
	for i in range(30): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/review_"+name+".png")
func run() -> void:
	root.size=Vector2i(1440,900)
	root.msaa_3d=Viewport.MSAA_4X
	var studio := Node3D.new()
	root.add_child(studio)
	var world_environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode=Environment.BG_SKY
	var sky := Sky.new()
	var atmosphere := ProceduralSkyMaterial.new()
	atmosphere.sky_top_color=Color("6b889d")
	atmosphere.sky_horizon_color=Color("c6d0cf")
	sky.sky_material=atmosphere
	env.sky=sky
	env.ambient_light_source=Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy=.55
	env.tonemap_mode=Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled=true
	world_environment.environment=env
	studio.add_child(world_environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-38,-28,0)
	sun.light_energy=1.1
	sun.shadow_enabled=true
	studio.add_child(sun)
	var floor := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(200,200)
	floor.mesh=plane
	floor.material_override=CityMaterials.get_surface("69747a")
	studio.add_child(floor)
	camera=Camera3D.new()
	camera.fov=45
	studio.add_child(camera)
	camera.current=true
	var group := Node3D.new()
	studio.add_child(group)
	for i in range(6):
		var person := LivingAssets.citizen(i)
		group.add_child(person)
		person.position=Vector3((i-2.5)*.85,0,0)
		person.purpose_pose="Wait" if i%2 else "Idle"
		CityAssets.tint(person,"Skin",Color("825030"))
	camera.position=Vector3(4,2.1,-7)
	camera.look_at(Vector3(0,1.0,0))
	await capture("citizen_lineup")
	group.queue_free()
	await process_frame
	group=Node3D.new()
	studio.add_child(group)
	var fleet := ["compact_sport","executive_sedan","urban_crossover","cargo_van","utility_pickup","taxi_sedan","police_cruiser","ambulance","fire_engine","school_bus"]
	for i in range(fleet.size()):
		var model := LivingAssets.scene(fleet[i])
		group.add_child(model)
		model.position=Vector3((i%5-2)*5.6,0,(i/5)*10)
	camera.position=Vector3(21,18,-29)
	camera.look_at(Vector3(0,0,5))
	await capture("fleet_lineup")
	group.queue_free()
	await process_frame
	for asset in ["compact_sport","executive_sedan","ambulance","fire_engine","school_bus"]:
		var model := LivingAssets.scene(asset)
		studio.add_child(model)
		var large: bool=asset in ["ambulance","fire_engine","school_bus"]
		camera.position=Vector3(7,3.8,-10) if large else Vector3(4.7,2.5,-6.7)
		camera.look_at(Vector3(0,1.2 if large else .8,0))
		await capture(asset)
		model.queue_free()
		await process_frame
	for pose in [["Walk",.22],["Walk",.75],["Sit",.2],["Cycle",.4]]:
		var model := LivingAssets.scene("citizen_0")
		studio.add_child(model)
		var player: AnimationPlayer=model.find_child("AnimationPlayer",true,false)
		player.play(pose[0])
		player.seek(pose[1],true)
		player.pause()
		camera.position=Vector3(2.8,1.7,-3)
		camera.look_at(Vector3(0,.9,0))
		await capture("pose_"+str(pose[0])+str(pose[1]))
		model.queue_free()
		await process_frame
	print("ASSET REVIEW CAPTURES COMPLETE")
	quit()
