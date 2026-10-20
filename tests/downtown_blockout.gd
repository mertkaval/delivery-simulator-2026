extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var block := preload("res://world/downtown/blockout.gd").new()
	root.add_child(block)
	await physics_frame
	var buildings := DowntownCatalog.buildings(0)
	var failures := 0
	for i in range(buildings.size()):
		for j in range(i):
			if buildings[i].footprint.intersects(buildings[j].footprint):
				printerr("FAIL: overlapping buildings ",i," ",j)
				failures+=1
		var b: Dictionary=buildings[i]
		var frontage: Vector3=b.root+Basis(Vector3.UP,b.yaw)*Vector3(0,1,.8)
		var query := PhysicsRayQueryParameters3D.create(frontage,frontage+Vector3.UP)
		if not block.get_world_3d().direct_space_state.intersect_ray(query).is_empty(): failures+=1
	var metrics := DowntownCatalog.metrics(1)
	if metrics.building_coverage<.75 or metrics.building_coverage>.90: failures+=1
	var alley := PhysicsRayQueryParameters3D.create(Vector3(146,1,-328),Vector3(250,1,-328))
	if not block.get_world_3d().direct_space_state.intersect_ray(alley).is_empty(): failures+=1
	print("DOWNTOWN BLOCKOUT: ",JSON.stringify(metrics)," failures=",failures)
	quit(1 if failures else 0)
