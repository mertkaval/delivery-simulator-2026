extends SceneTree
var failures := 0
var checks := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool,message: String) -> void:
	checks+=1
	if not ok:
		failures+=1
		push_error(message)
func run() -> void:
	var world := CedarNeighborhood.new()
	root.add_child(world)
	await physics_frame
	await physics_frame
	var space := world.get_world_3d().direct_space_state
	var moving_actors: Array[RID]=[]
	for actor in world.find_children("*","CharacterBody3D",true,false): moving_actors.append(actor.get_rid())
	check(world.doors.size()==41,"Original 36 destinations plus five downtown categories")
	for i in range(5):
		var session := DeliverySession.new()
		session.offer_position=Vector3(244,0,-280)
		session.serial=i
		session.offer()
		check(session.order.address==36+i,"Downtown dispatch category")
		check(session.accept(),"Accept downtown order")
		session.pickup(CityCatalog.RESTAURANTS[3+i],1)
		check(session.order.state=="CARRYING","Collect downtown order")
		session.deliver(36+i,1)
		check(session.order.state=="COMPLETED","Complete downtown order")
		for pair in [[DowntownCatalog.PICKUPS[i],true],[DowntownCatalog.DESTINATIONS[i],false]]:
			var path := CityCatalog.route(Vector3(244,0,-280),pair[0],pair[1])
			check(path.size()>1,"Downtown route exists")
			for j in range(1,path.size()):
				var a: Vector3=path[j-1]+Vector3.UP
				var b: Vector3=path[j]+Vector3.UP
				if a.distance_to(b)<.01: continue
				if j==path.size()-1: b=b.move_toward(a,.55)
				var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(a,b,1,moving_actors))
				check(hit.is_empty(),"Route obstructed category %d pickup %s segment %s to %s"%[i,pair[1],a,b])
	for z in DowntownCatalog.STREET_Z:
		check(space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(70,1,z),Vector3(144,1,z))).is_empty(),"Existing neighborhood connector")
	var player := CourierPlayer.new()
	player.session=DeliverySession.new()
	player.set_physics_process(false)
	root.add_child(player)
	player.set_physics_process(false)
	for category in [0,1]:
		var locations: Array=DowntownCatalog.PICKUPS if category==0 else DowntownCatalog.DESTINATIONS
		var approaches: Array=DowntownCatalog.PICKUP_APPROACHES if category==0 else DowntownCatalog.DESTINATION_APPROACHES
		for i in range(locations.size()):
			var p: Vector3=locations[i]
			var approach: Array=approaches[i]
			var direction: Vector3=approach[-2].direction_to(approach[-1])
			player.position=Vector3(p.x,.10,p.z)-direction*1.5
			player.camera.look_at(p)
			await physics_frame
			var expected: String="pickup_"+CityCatalog.RESTAURANTS[i+3] if category==0 else "door_%d"%(36+i)
			check(player.target().get("id")==expected,"Real interaction ray: "+expected)
	print("DOWNTOWN GAMEPLAY: ",checks," checks, ",failures," failures")
	quit(1 if failures else 0)
