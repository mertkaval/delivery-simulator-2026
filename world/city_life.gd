extends Node3D
## Lightweight articulated citizens with sidewalk routes and signal-aware crossings.
var pedestrians: Array[Dictionary] = []
var cyclists: Array[Dictionary] = []
var staff: Array[Node3D] = []
var traffic: Node
var elapsed := 0.0
## Where a citizen rider's hips sit on the gray bicycle (saddle centre is 0.30 m behind the origin).
const CITIZEN_SADDLE_Z := 0.44

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
	# Atatürk Avenue: both sidewalks, spread along the whole avenue (both directions).
	for i in range(AVENUE_WALKERS):
		var side := -1 if i % 2 == 0 else 1
		# Busiest along the restaurants and shops in the north half.
		var u := float(i) / AVENUE_WALKERS
		var z: float = (30.0 - u / 0.6 * 290.0) if u < 0.6 else (-260.0 - (u - 0.6) / 0.4 * 410.0)
		z += 5.0 * LivingAssets.noise(i, 31)
		add_walker([Vector3(side * 8.4, 0.08, z), Vector3(side * 8.4, 0.08, z - 30)], i)
	# Residential streets: the cross streets and both side roads.
	for i in range(RESIDENTIAL_WALKERS):
		var c: float = CityCatalog.CROSS_STREETS[i % 3]
		var lx := -1.0 if (i / 3) % 2 == 0 else 1.0
		var at: Vector3
		if i % 2 == 0: at = Vector3(lx * (14.0 + 40.0 * LivingAssets.noise(i, 32)), 0.08, c + (7.0 if (i / 6) % 2 == 0 else -7.0))
		else: at = Vector3(lx * (57.0 if (i / 4) % 2 == 0 else 71.0), 0.08, c - 12.0 - 110.0 * LivingAssets.noise(i, 33))
		add_walker([at, at + Vector3(0, 0, -10)], AVENUE_WALKERS + i)
		pedestrians[-1]["resident"] = true
	for i in range(2):
		var z: float = [-93, -177][i]
		add_walker([Vector3(-8, 0.08, z), Vector3(8, 0.08, z)], AVENUE_WALKERS + RESIDENTIAL_WALKERS + i, true)
	# Park strollers walk a loop round each square's fountain.
	var park_index := 0
	for park in PARKS:
		for k in range(2):
			var loop := PackedVector3Array()
			for p: Vector3 in PARK_LOOP: loop.append(park + p + Vector3(0, 0.056, 0))
			if k == 1: loop.reverse()
			var start := loop[(k * 2 + park_index) % loop.size()]
			add_walker([start, start + Vector3(0, 0, -1)], 200 + park_index * 2 + k)
			pedestrians[-1]["loop"] = loop
		park_index += 1
	# Atatürk Avenue restaurants (CityAssets restaurant_0..2): counter staff, seated diners and a waiter.
	for i in range(3):
		var worker := person(i + 3)
		worker.position = CityCatalog.PICKUPS[i] + Vector3(-2.8, -1, -1.5)
		worker.position.y=.05
		worker.rotation.y = PI
		add_child(worker)
		staff.append(worker)
		avenue_dining(i)
	for i in range(6): add_cyclist(i)
	CitizenBrain.attach(self,pedestrians)
	var shops := ShopLife.new()
	shops.name = "ShopLife"
	add_child(shops)
	# Benches are built after this node (StreetFurniture): collect seats once the city stands.
	call_deferred("gather_seats")

## The avenue restaurants' dining (restaurant_0..2.glb, identical layouts, local frame = pickup
## - 1 m): three tables with chairs either side (seat top 0.50, floor 0.05, table top 0.82).
const AVENUE_TABLES := [[Vector3(-8.45, 0, 0.65), 0.6], [Vector3(-8.45, 0, -2.3), 0.75], [Vector3(-5.95, 0, -3.6), 0.62]]
func avenue_dining(i: int) -> void:
	var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
	var service := TableService.new()
	service.name = "AvenueTableService_%d" % i
	service.position = p
	add_child(service)
	var pass_spot := Vector3(-5.6, 0.05, -0.95)
	for k in range(3):
		if k == (i + 1) % 3: continue   # two of the three tables are taken
		var centre: Vector3 = AVENUE_TABLES[k][0]
		var half: float = AVENUE_TABLES[k][1]
		var slots: Array[Dictionary] = []
		var spots: Array[Vector3] = []
		for side: float in [1.0, -1.0]:
			var frame := Transform3D(Basis(Vector3.UP, PI if side > 0 else 0.0), p + centre + Vector3(-0.05, 0, side * half))
			slots.append(CitySeating.slot(frame, p.y + 0.50, 0.25, -0.24, p.y + 0.05, "avenue_chair"))
			spots.append(centre + Vector3(-0.05, 0.825, side * 0.2))
		var approach := centre + Vector3(1.1, 0.05, 0)
		var lane := approach.x + 0.15
		var route := PackedVector3Array([pass_spot, Vector3(lane, 0.05, -1.0), Vector3(lane, 0.05, approach.z), approach])
		service.add_table(slots, spots, approach, PI / 2, route, 300 + i * 10 + k * 3)
	service.start_waiter(320 + i, pass_spot, PI, Vector3(-5.6, 1.15, -0.3))

## Square parks (CedarNeighborhood.build_park): centres, and a stroll loop round the fountain
## (fountain at +4,-5; benches at +4,+4 / -4.5,+6 / -3,-10; pergola at x -6.6..-2.4, z 3.9..8.1).
const PARKS := [Vector3(-64, 0, -145), Vector3(64, 0, -145), Vector3(-44, 0, -330), Vector3(44, 0, -330), Vector3(-44, 0, -470), Vector3(44, 0, -470), Vector3(-44, 0, -590), Vector3(44, 0, -590)]
const PARK_LOOP := [Vector3(0.5, 0, 1.6), Vector3(7.6, 0, 1.4), Vector3(8.2, 0, -5.0), Vector3(7.4, 0, -9.0), Vector3(1.0, 0, -8.6), Vector3(0.0, 0, -4.0)]
const AVENUE_WALKERS := 56
const RESIDENTIAL_WALKERS := 32
var seats: Array[Dictionary] = []
var sitters: Array[LivingCitizen] = []

## Benches people can use: the avenue benches (StreetFurniture, bench_wood, facing the road)
## and the neighbourhood's own benches (parks, forecourts; bench_wood facing +Z). Some park
## benches get people sitting on them; the rest are free for passers-by (CitizenBrain).
func gather_seats() -> void:
	var city := get_parent()
	var furniture := city.get_node_or_null("StreetFurniture")
	if furniture != null:
		for shape in furniture.find_children("*", "CollisionShape3D", true, false):
			if shape.get_meta("prop", "") == "bench_wood":
				var g: Transform3D = (shape as Node3D).global_transform
				g.origin.y -= 0.45
				seats.append_array(CitySeating.bench_slots(g, "bench_wood"))
	var k := 0
	for node in city.get_children():
		if node is Node3D and str(node.scene_file_path).ends_with("bench_wood.glb"):
			var slots := CitySeating.bench_slots((node as Node3D).global_transform, "bench_wood")
			var park := false
			for c: Vector3 in PARKS:
				if Vector2(node.global_position.x - c.x, node.global_position.z - c.z).length() < 16: park = true
			if park and k % 3 != 2:
				for j in range(1 + (k % 2)):
					var s: Dictionary = slots[j]
					s.floor = 0.056
					var sitter := CitySeating.seated_person(s, 400 + k * 3 + j)
					sitter.max_distance = 80.0
					add_child(sitter)
					CitySeating.sit(sitter, s, ["SitPhone", "Sit", "SitTalk"][(k + j) % 3] if k % 2 == 1 else ["Sit", "SitPhone"][k % 2])
					sitters.append(sitter)
			k += 1
			for s in slots:
				if s.user == null: seats.append(s)

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
	var rider: Node3D
	if index % 2 == 0:
		# The supplied model's own rider, sitting exactly on the gray bike (static pose; the
		# wheels spin). Joint proxies keep the shared pedalling code valid.
		rider = CityAssets.create("bicycle_rider", 100)
		body.add_child(rider)
		for joint in ["HipL", "HipR", "KneeL", "KneeR", "ShoulderL", "ShoulderR", "ElbowL", "ElbowR"]:
			var proxy := Node3D.new()
			proxy.name = joint
			rider.add_child(proxy)
	else:
		# Designed citizens with the pedalling clip (the converted walkers have no cycling pose).
		rider = LivingAssets.classic_citizen(index + 10)
		body.add_child(rider)
		rider.position = Vector3(0, 0.07, CITIZEN_SADDLE_Z)
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
