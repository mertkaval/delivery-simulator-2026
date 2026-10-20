extends SceneTree
var failed := 0
var checks := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		printerr("FAIL: " + text)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	game.player.set_physics_process(false)
	check(game.world.doors.size() == 41, "Thirty-six original destinations plus five downtown destinations")
	check(game.world.scenery_houses.size() >= 120, "Dense street-facing residential district (%d other houses)" % game.world.scenery_houses.size())
	var far_session := DeliverySession.new()
	far_session.serial = 35
	far_session.offer()
	var far_save := far_session.snapshot()
	far_save.player = {"position": [21, 0.1, -646.7], "yaw": 0.0, "bicycle": [21, 0.1, -646.7], "mounted": false}
	check(DeliverySave.valid_envelope(far_save), "Far-north delivery and bicycle positions can be saved")
	for i in range(game.world.doors.size()):
		check(game.world.doors[i].is_equal_approx(CityCatalog.address_position(i)), "Catalog and physical door agree %d" % i)
		if i >= 12 and i<36:
			check(not game.world.near_cross_street(game.world.doors[i].z), "New house entrance clears intersections %d" % i)
	var stop_count := 0
	for child in game.world.get_children():
		if str(child.name).begins_with("StopLine_"):
			stop_count += 1
			check(absf(child.position.x) - child.mesh.size.x / 2 > 0.5, "Stop paint stays in one lane")
			check(child.mesh.size.y <= 0.0021, "Stop marking is flat paint")
	check(stop_count == 4, "Both approaches marked at two crossings")
	for path in game.world.house_paths:
		var half_width: float = path.mesh.size.x / 2
		check(absf(path.position.x) - half_width >= 9, "House path stays outside carriageway")
	for i in range(36):
		var facing: Vector3 = CityCatalog.address_facing(i)
		game.player.position = game.world.doors[i] + facing * 1.6 + Vector3(0, -0.92, 0)
		game.player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
		game.player.camera.rotation = Vector3(-0.2, 0, 0)
		await physics_frame
		check(game.player.target().get("id") == "door_%d" % i, "Door interaction %d" % i)
	for i in range(3):
		game.player.position = CityCatalog.PICKUPS[i] + Vector3(0, -0.92, 1.8)
		game.player.rotation = Vector3.ZERO
		game.player.camera.rotation.x = -0.3
		await physics_frame
		var expected: String = "pickup" if i == 0 else "pickup_" + CityCatalog.RESTAURANTS[i]
		check(game.player.target().get("id") == expected, "Restaurant physical counter %d" % i)
		var session := DeliverySession.new()
		session.serial = i
		session.offer()
		check(session.restaurant_id() == CityCatalog.RESTAURANTS[i], "Offer restaurant selection")
		session.accept()
		session.pickup("invalid", 1)
		check(session.order.state == "ACCEPTED", "Wrong restaurant preserves cargo")
		session.pickup(CityCatalog.RESTAURANTS[i], 1)
		check(session.order.state == "CARRYING", "Correct restaurant pickup")
		check(DeliverySession.validate(session.snapshot()), "Restaurant save validates")
	var traffic: Node
	for child in game.world.get_children():
		if child.get_script() == load("res://world/traffic.gd"): traffic = child
	check(traffic != null and traffic.cars.size() == 16, "Sixteen varied AI vehicles")
	traffic.set_physics_process(false)
	game.player.position = Vector3(30, 0.1, 40)
	var first: Dictionary = traffic.drivers[0]
	first.s = (first.route as SmoothRoute).project(Vector3(1.95, 0, -79))
	first.speed = 7.0
	TrafficDriver.place(first)
	traffic.speeds[0] = 7
	traffic.elapsed = 16
	await physics_frame
	for frame in range(180):
		traffic._physics_process(1.0 / 60.0)
	check(traffic.cars[0].position.z > -90, "Red crossing stops vehicle before crosswalk")
	check(traffic.speeds[0] < 0.1, "Red crossing reaches standstill")
	traffic.elapsed = 0
	var before: float = traffic.cars[0].position.z
	for frame in range(60): traffic._physics_process(1.0 / 60.0)
	check(traffic.cars[0].position.z < before, "Green crossing resumes traffic")
	var lead: Dictionary = traffic.drivers[0]
	lead.s = (lead.route as SmoothRoute).project(Vector3(1.95, 0, -52))
	lead.speed = 4.0
	TrafficDriver.place(lead)
	traffic.speeds[0] = 4
	game.player.position = Vector3(1.95, 0.1, -61)
	await physics_frame
	for frame in range(120): traffic._physics_process(1.0 / 60.0)
	check(traffic.cars[0].position.z > -58.5, "Traffic stops before player in lane")
	print("CITY PASS: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)


