extends SceneTree
var failures := 0
var checks := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool,words: String) -> void:
	checks+=1
	if not ok:
		failures+=1
		push_error(words)
func triangles(node: Node) -> int:
	var total := 0
	if node is MeshInstance3D:
		for surface in range(node.mesh.get_surface_count()):
			var arrays: Array=node.mesh.surface_get_arrays(surface)
			total+=arrays[Mesh.ARRAY_INDEX].size()/3 if arrays[Mesh.ARRAY_INDEX]!=null and arrays[Mesh.ARRAY_INDEX].size()>0 else arrays[Mesh.ARRAY_VERTEX].size()/3
	for child in node.get_children(): total+=triangles(child)
	return total
func run() -> void:
	var tinted_citizen := LivingAssets.citizen(0)
	CityAssets.tint(tinted_citizen,"Skin",Color("825030"))
	for part in tinted_citizen.find_children("*","MeshInstance3D",true,false): check(part.material_override==null,"Legacy skin tint preserves clothing material slots")
	tinted_citizen.free()
	for i in range(6):
		var previous := 1000000
		for lod in range(3):
			var model := LivingAssets.scene("citizen_%d"%i+("_lod%d"%lod if lod else ""))
			var animation: AnimationPlayer=model.find_child("AnimationPlayer",true,false)
			for clip in ["Idle","Walk","Brisk","Wait","Talk","Sit","Carry","Cycle"]: check(animation.has_animation(clip),"Character animation missing "+clip)
			var rigs := model.find_children("*","Skeleton3D",true,false)
			check(rigs.size()==1 and rigs[0].get_bone_count()>=14,"Weighted skeleton required")
			var count := triangles(model)
			check(count<previous,"Character LOD must reduce geometry")
			previous=count
			model.free()
	for asset in ["compact_sport","executive_sedan","urban_crossover","cargo_van","utility_pickup","taxi_sedan","police_cruiser","ambulance","fire_engine","school_bus","hospital","fire_station","school","rain_garden"]:
		var previous := 10000000
		for lod in range(3):
			var model := LivingAssets.scene(asset+("_lod%d"%lod if lod else ""))
			var count := triangles(model)
			check(count>0 and count<previous,"Reduced valid LOD "+asset+" level "+str(lod))
			if asset in ["compact_sport","executive_sedan","police_cruiser","ambulance","fire_engine","school_bus"]: check(CityAssets.wheel_nodes(model).size()==4,"Four articulated wheel pivots "+asset)
			previous=count
			model.free()
	var world := CedarNeighborhood.new()
	root.add_child(world)
	await physics_frame
	await physics_frame
	var excluded: Array[RID]=[]
	for actor in world.find_children("*","CharacterBody3D",true,false): excluded.append(actor.get_rid())
	CitizenRoutes.prepare()
	var space := world.get_world_3d().direct_space_state
	var blocked: Array=[]
	for edge in CitizenRoutes.edges:
		var a := CitizenRoutes.graph.get_point_position(edge.x)+Vector3.UP*.8
		var b := CitizenRoutes.graph.get_point_position(edge.y)+Vector3.UP*.8
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(a,b,1,excluded))
		if not hit.is_empty(): blocked.append({"a":a,"b":b,"hit":hit.position})
	check(blocked.is_empty(),"Sidewalk graph has obstructed edges: "+str(blocked))
	var civic_count := 0
	for goal in CitizenRoutes.destinations:
		if goal.building==100:
			civic_count+=1
			check(CitizenRoutes.path(Vector3(243,.1,-280),goal.node).size()>2,"Civic site reachable from downtown")
	check(civic_count==3,"Three civic destinations")
	var people := world.find_children("*","CharacterBody3D",true,false).filter(func(n: Node)->bool: return n.has_meta("purpose_brain"))
	check(people.size()>=65,"Purposeful population attached")
	for body in people:
		check(body.has_meta("purpose") and body.has_meta("daily_goal"),"Citizen owns a destination and schedule")
	var services := world.find_child("CivicFleet",true,false)
	check(services!=null and services.fleet.size()==7,"Seven dedicated civic vehicles")
	for car in services.fleet:
		var pts: PackedVector3Array=car.points
		for j in range(0,pts.size(),4):
			var a: Vector3=pts[j]+Vector3.UP*.9
			var b: Vector3=pts[(j+4)%pts.size()]+Vector3.UP*.9
			check(space.intersect_ray(PhysicsRayQueryParameters3D.create(a,b,1,excluded)).is_empty(),"Service route obstruction: "+str(car.role)+" "+str(a)+" to "+str(b))
	var phase_system := world.find_child("DowntownActivity",true,false)
	var first: CharacterBody3D=phase_system.pedestrians[0].body
	phase_system.elapsed=63.8
	first.visible=true
	first.set_meta("in_crossing",true)
	phase_system._physics_process(.1)
	check(phase_system.elapsed==63.8,"Occupied crossing holds all-red clearance")
	first.set_meta("in_crossing",false)
	phase_system._physics_process(.1)
	check(phase_system.elapsed>63.8,"Clear crossing releases traffic clock")
	print("LIVING CITY: ",checks," checks, ",failures," failures; graph ",CitizenRoutes.graph.get_point_count()," nodes / ",CitizenRoutes.edges.size()," edges")
	quit(1 if failures else 0)
