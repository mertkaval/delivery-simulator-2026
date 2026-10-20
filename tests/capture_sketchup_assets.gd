extends SceneTree
## Converted Sketchfab vehicles and people in the city: traffic on the avenue, a U-turn,
## the civic fleet, the car showroom and a shop guard. Also measures how smooth traffic yaw is.
func _initialize() -> void: call_deferred("run")
func shot(cam: Camera3D, from: Vector3, at: Vector3, file: String) -> void:
	cam.position = from
	cam.look_at(at)
	for f in range(3): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s.png" % file)
func run() -> void:
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14.0)
	var cam := Camera3D.new()
	world.add_child(cam)
	cam.current = true
	cam.fov = 55
	var traffic: Node = world.get_node("CityTraffic")
	# Track the sharpest yaw change per metre travelled over 20 s of traffic.
	var last_yaw: Array[float] = []
	var last_pos: Array[Vector3] = []
	for c in traffic.cars:
		last_yaw.append(c.rotation.y)
		last_pos.append(c.position)
	var worst := 0.0
	var worst_rate := 0.0
	for frame in range(1200):
		await physics_frame
		for i in range(traffic.cars.size()):
			var c: Node3D = traffic.cars[i]
			var dyaw := absf(wrapf(c.rotation.y - last_yaw[i], -PI, PI))
			var moved := c.position.distance_to(last_pos[i])
			worst_rate = maxf(worst_rate, dyaw * 60.0)
			if moved > 0.02: worst = maxf(worst, dyaw / moved)
			last_yaw[i] = c.rotation.y
			last_pos[i] = c.position
	print("TRAFFIC sharpest curvature %.3f 1/m (radius %.1f m), max yaw rate %.1f deg/s" % [worst, 1.0 / maxf(worst, 0.001), rad_to_deg(worst_rate)])
	var ids := []
	for d in traffic.drivers: ids.append(d.id)
	print("MODELS ", ids)
	# Follow car 0 and catch it in its U-turn.
	var car: Node3D = traffic.cars[0]
	await shot(cam, car.position + Vector3(8, 6, 10), car.position + Vector3(0, 0.8, 0), "sk_traffic_follow")
	await shot(cam, Vector3(14, 9, -228), Vector3(0, 0, -242), "sk_uturn_end")
	await shot(cam, Vector3(10, 3, -60), Vector3(0, 1, -110), "sk_avenue")
	var fleet: Node = world.find_child("CivicFleet", true, false)
	if fleet:
		var f: Node3D = fleet.fleet[3].body
		await shot(cam, f.position + Vector3(9, 4, 9), f.position + Vector3(0, 1.2, 0), "sk_fire_truck")
		var a: Node3D = fleet.fleet[2].body
		await shot(cam, a.position + Vector3(-8, 3.5, 8), a.position + Vector3(0, 1.2, 0), "sk_ambulance")
	var shop: Vector3 = ShopCatalog.LOCATIONS["cars"]
	await shot(cam, shop + Vector3(-1, 2.2, 13), shop + Vector3(-3, 1.0, 3), "sk_shop_front")
	# A converted walker.
	for n in world.find_children("SketchupCitizen", "Node3D", true, false):
		var p: Node3D = n
		if p.get_parent() is CharacterBody3D and p.is_visible_in_tree():
			await shot(cam, p.global_position + Vector3(2.5, 1.6, 3.0), p.global_position + Vector3(0, 0.95, 0), "sk_walker")
			print("WALKER at ", p.global_position, " clip ", p.players[0].current_animation)
			break
	quit()
