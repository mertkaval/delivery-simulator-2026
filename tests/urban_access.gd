extends SceneTree
var failures := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool,message: String) -> void:
	if not ok:
		failures+=1
		push_error(message)
func run() -> void:
	var block := DowntownDistrict.new()
	root.add_child(block)
	await physics_frame
	await physics_frame
	var space := block.get_world_3d().direct_space_state
	for entry in block.entries:
		var query := PhysicsRayQueryParameters3D.create(entry.front,entry.inside)
		check(space.intersect_ray(query).is_empty()!=entry.closed,"Entrance open/renovation state: %d"%entry.id)
		var capsule := CapsuleShape3D.new()
		capsule.radius=.33
		capsule.height=1.7
		var clearance := PhysicsShapeQueryParameters3D.new()
		clearance.shape=capsule
		clearance.transform.origin=entry.inside
		check(space.intersect_shape(clearance).is_empty(),"Lobby standing room obstructed: %d"%entry.id)
	for z in [-330.0,-328.0,-326.0]:
		var query := PhysicsRayQueryParameters3D.create(Vector3(150,1,z),Vector3(246,1,z))
		check(space.intersect_ray(query).is_empty(),"Service alley obstructed")
	print("URBAN ACCESS: ",failures," failures; 10 entries and 3 alley lanes checked")
	quit(1 if failures else 0)
