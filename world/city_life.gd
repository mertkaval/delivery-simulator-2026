extends Node3D
## Lightweight articulated citizens with sidewalk routes and signal-aware crossings.
var pedestrians: Array[Dictionary] = []
var cyclists: Array[Dictionary] = []
var staff: Array[Node3D] = []
var traffic: Node
var elapsed := 0.0

func person(index: int) -> Node3D:
	var model := CityAssets.create("citizen", 75)
	CityAssets.tint(model, "Clothing", Color(["315769", "965a40", "556b46", "a38f65", "473d55", "b5b7ac"][index % 6]))
	CityAssets.tint(model, "Skin", Color(["ad795c", "6b4631", "c89574", "8e6046"][index % 4]))
	return model

func joints(model: Node) -> Dictionary:
	var result := {}
	for joint in ["HipL", "HipR", "KneeL", "KneeR", "ShoulderL", "ShoulderR", "ElbowL", "ElbowR"]:
		result[joint] = model.find_child(joint, true, false)
	return result

func add_walker(route: Array[Vector3], index: int, crossing: bool = false) -> void:
	var body := CharacterBody3D.new()
	body.name = "Pedestrian_%02d" % index
	body.collision_layer = 4
	body.collision_mask = 1 | 4
	body.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	add_child(body)
	body.position = route[0]
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.23
	capsule.height = 1.74
	shape.shape = capsule
	shape.position.y = 0.89
	body.add_child(shape)
	var model := person(index)
	body.add_child(model)
	pedestrians.append({"body": body, "model": model, "route": route, "target": 1, "phase": float(index), "joints": joints(model), "crossing": crossing, "speed": 1.1 + (index % 4) * 0.11})

func _ready() -> void:
	traffic = get_parent().get_node_or_null("CityTraffic")
	# Separate sidewalk tracks avoid opposing pedestrians meeting head-on.
	for i in range(16):
		var side := -1 if i % 2 == 0 else 1
		var x: float = side * (7.35 if i % 4 < 2 else 8.65)
		var z: float = -20 - (i / 2) * 75
		add_walker([Vector3(x, 0.08, z), Vector3(x, 0.08, z - 38)], i)
	for i in range(6):
		var z: float = [-330, -470, -590][i / 2]
		var x: float = -44 if i % 2 == 0 else 44
		add_walker([Vector3(x, 0.08, z - 12), Vector3(x, 0.08, z + 12)], 16 + i)
	for i in range(2):
		var z: float = [-93, -177][i]
		add_walker([Vector3(-8, 0.08, z), Vector3(8, 0.08, z)], 22 + i, true)
	for i in range(3):
		var worker := person(i + 3)
		worker.position = CityCatalog.PICKUPS[i] + Vector3(-2.8, -1, -1.5)
		worker.position.y=.08
		worker.rotation.y = PI
		add_child(worker)
		staff.append(worker)
		# Seated diners are posed at authored dining tables, behind the clear delivery lane.
		var diner := person(i + 7)
		diner.position = CityCatalog.PICKUPS[i] + Vector3(-8.4, -0.99, 1.35)
		diner.position.y=.08
		add_child(diner)
		var pose := joints(diner)
		for side in ["L", "R"]:
			pose["Hip" + side].rotation.x = PI / 2
			pose["Knee" + side].rotation.x = -PI / 2
			pose["Elbow" + side].rotation.x = 0.8
	for i in range(6): add_cyclist(i)
	CitizenBrain.attach(self,pedestrians)

func add_cyclist(index: int) -> void:
	var body := CharacterBody3D.new()
	body.name = "Cyclist_%02d" % index
	body.collision_layer = 4
	body.collision_mask = 1 | 4
	body.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	add_child(body)
	var side := 1 if index % 2 == 0 else -1
	# Centre of the marked bike lane (StreetGrid.AVENUE.bike).
	body.position = Vector3(side * 4.7, 0.06, -35 - index * 90)
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.62, 1.55, 1.75)
	collider.shape = shape
	collider.position.y = 0.85
	body.add_child(collider)
	var bike := CityAssets.create("bicycle", 100)
	body.add_child(bike)
	# Riders use the designed citizens: the converted walker has no cycling pose.
	var rider: Node3D = LivingAssets.classic_citizen(index + 10)
	body.add_child(rider)
	rider.position = Vector3(0, 0.07, 0.46)
	rider.rotation.x = -0.2
	if rider is LivingCitizen: rider.attach_helmet()
	var pose := joints(rider)
	for s in ["L", "R"]:
		pose["Hip" + s].rotation.x = 1.1
		pose["Knee" + s].rotation.x = -1.55
		pose["Shoulder" + s].rotation.x = 0.9
		pose["Elbow" + s].rotation.x = 0.5
	cyclists.append({"body": body, "rider": rider, "bike": bike, "wheels": CityAssets.wheel_nodes(bike), "joints": pose, "direction": -side, "phase": float(index), "speed": 0.0})

func blocked(body: CharacterBody3D, direction: Vector3, distance: float) -> bool:
	var query := PhysicsRayQueryParameters3D.create(body.position + Vector3(0, 0.9, 0), body.position + Vector3(0, 0.9, 0) + direction * distance, 1 | 4, [body.get_rid()])
	return not get_world_3d().direct_space_state.intersect_ray(query).is_empty()

func safe_to_cross(z: float) -> bool:
	if traffic == null or not traffic.crossing_red(): return false
	for i in range(traffic.cars.size()):
		var car: Node3D = traffic.cars[i]
		if absf(car.position.x)<6 and (absf(car.position.z-z)<3.8 or (absf(car.position.z-z)<10 and traffic.speeds[i]>.25)): return false
	return true

func _physics_process(delta: float) -> void:
	elapsed += delta
	var camera := get_viewport().get_camera_3d()
	for walker in pedestrians:
		var body: CharacterBody3D = walker.body
		if body.has_meta("purpose_brain"): continue
		var goal: Vector3 = walker.route[walker.target]
		if body.position.distance_to(goal) < 0.20:
			walker.target = (walker.target + 1) % walker.route.size()
			goal = walker.route[walker.target]
		var direction := body.position.direction_to(goal)
		var wait_for_signal: bool = walker.crossing and absf(body.position.x) >= 6.7 and not safe_to_cross(body.position.z)
		var moving: bool = not wait_for_signal and not blocked(body, direction, 0.75)
		body.rotation.y = lerp_angle(body.rotation.y, atan2(-direction.x, -direction.z), minf(delta * 8, 1))
		if moving: body.move_and_collide(direction * minf(walker.speed * delta, body.position.distance_to(goal)))
		if camera != null and body.position.distance_squared_to(camera.global_position) > 80 * 80: continue
		walker.phase += delta * (5.5 if moving else 0.4)
		var swing: float = sin(walker.phase) * (0.38 if moving else 0.025)
		walker.joints.HipL.rotation.x = swing
		walker.joints.HipR.rotation.x = -swing
		walker.joints.KneeL.rotation.x = maxf(0, -swing) * 1.25
		walker.joints.KneeR.rotation.x = maxf(0, swing) * 1.25
		walker.joints.ShoulderL.rotation.x = -swing * 0.7
		walker.joints.ShoulderR.rotation.x = swing * 0.7
	for rider in cyclists:
		var body: CharacterBody3D = rider.body
		var direction := Vector3(0, 0, rider.direction)
		var stop := blocked(body, direction, 3.5)
		if traffic != null and traffic.crossing_red():
			for crossing in [-93, -177]:
				var ahead: float = (crossing - body.position.z) * rider.direction
				if ahead > 0 and ahead < 7: stop = true
		rider.speed = move_toward(rider.speed, 0.0 if stop else 3.4, delta * 3)
		body.rotation.y = 0 if rider.direction < 0 else PI
		if body.move_and_collide(direction * rider.speed * delta): rider.speed = 0
		if body.position.z < -682 or body.position.z > 42:
			rider.direction *= -1
			body.position.x *= -1
		if camera != null and body.position.distance_squared_to(camera.global_position) > 100 * 100: continue
		rider.phase += delta * rider.speed * 2
		for wheel in rider.wheels: wheel.rotate_x(-rider.speed * delta / 0.35)
		for s in ["L", "R"]:
			var phase: float = rider.phase + (PI if s == "R" else 0)
			rider.joints["Hip" + s].rotation.x = 1.1 + sin(phase) * 0.25
			rider.joints["Knee" + s].rotation.x = -1.55 - sin(phase) * 0.4
