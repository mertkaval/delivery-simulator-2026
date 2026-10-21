extends SceneTree
## Rendered check of the civil service fleet and the Ace 11 in city traffic (run without
## --headless). Adds one of every new model to the Cedar Lane loops next to the normal traffic,
## lets them drive, then saves: an avenue overview, a city bus mid-way round an 11 m corner
## (from above, to see the kerb), close-ups and the car showroom.
## Output: user arg after "--" (directory), default res://tmp/.
var out_dir := "res://tmp/"

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty(): out_dir = args[0].trim_suffix("/") + "/"
	call_deferred("run")

func shot(camera: Camera3D, name: String) -> void:
	for f in range(3): await process_frame
	await RenderingServer.frame_post_draw
	var path := out_dir + "civil_" + name + ".png"
	root.get_texture().get_image().save_png(path)
	print("SAVED ", ProjectSettings.globalize_path(path))

func add(traffic: Node, id: String, route: SmoothRoute, at: Vector3) -> Dictionary:
	var car := TrafficDriver.spawn(traffic, id, "Capture_" + id, route, route.project(at), 6.5 if VehicleCatalog.turns_tight(id) else 8.0, 1 | 4)
	traffic.drivers.append(car)
	traffic.cars.append(car.body)
	traffic.car_dimensions.append(car.size)
	traffic.speeds.append(0.0)
	return car

func frame_car(camera: Camera3D, car: Dictionary, side := 1.0, dist := 1.0) -> void:
	var body: Node3D = car.body
	var size: Vector3 = car.size
	var fwd := -body.global_basis.z
	var reach := maxf(size.z, 4.0) * dist
	camera.position = body.global_position + fwd * reach * 0.95 + body.global_basis.x * side * reach * 0.75 + Vector3(0, 1.4 + size.y * 0.35, 0)
	camera.look_at(body.global_position + Vector3(0, size.y * 0.45, 0))

func run() -> void:
	root.size = Vector2i(1280, 720)
	VehicleCatalog.traffic_seed = 7
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 50
	for f in range(5): await physics_frame
	var traffic: Node = world.get_node("CityTraffic")
	var mix: Array[String] = []
	for d in traffic.drivers: mix.append(str(d.id))
	print("CITY TRAFFIC MIX ", mix)
	# Northbound on Cedar Lane (loop 0) and southbound (loop 1), spaced by length.
	var north: Array[String] = ["ace11", "civil_taxi", "civil_police_sedan", "civil_postvan", "civil_ambulance", "civil_rdservtruck", "civil_towtruck"]
	var south: Array[String] = ["civil_fire_truck", "civil_garbage_truck", "civil_school_bus", "ace11", "civil_taxi"]
	var added: Dictionary = {}
	var z := -12.0
	for id in north:
		added[id] = add(traffic, id, traffic.route_for(0, id), Vector3(1.95, 0, z))
		z -= VehicleCatalog.spec_of(id).length + 9.0
	z = -150.0
	for id in south:
		added["s_" + id] = add(traffic, id, traffic.route_for(1, id), Vector3(-1.95, 0, z))
		z += VehicleCatalog.spec_of(id).length + 9.0
	# A city bus approaching the Cedar Lane / Refet Bele Street corner (right turn, z = -256).
	var bus := add(traffic, "civil_citybus", traffic.route_for(0, "civil_citybus"), Vector3(1.95, 0, -226))
	for f in range(150): await physics_frame
	# 1. Avenue overview looking north over both lanes.
	camera.position = Vector3(9.5, 9.0, -8.0)
	camera.look_at(Vector3(0, 0.5, -55))
	await shot(camera, "avenue")
	# 2. Close-ups.
	for key in ["ace11", "civil_taxi", "civil_police_sedan", "civil_ambulance", "s_civil_fire_truck", "s_civil_school_bus"]:
		var car: Dictionary = added[key]
		frame_car(camera, car)
		await shot(camera, "close_" + key.trim_prefix("s_"))
	# 3. The bus through the corner, from above.
	for f in range(900):
		await physics_frame
		var turn: float = absf(wrapf((bus.body as Node3D).rotation.y, -PI, PI))
		if turn > PI * 0.22 and turn < PI * 0.3: break
	print("BUS at ", (bus.body as Node3D).global_position, " yaw ", (bus.body as Node3D).rotation.y, " speed ", bus.speed)
	camera.position = Vector3(10.0, 24.0, -238.0)
	camera.look_at(Vector3(8.0, 0, -256.0))
	await shot(camera, "bus_corner_top")
	frame_car(camera, bus, -1.0, 1.1)
	await shot(camera, "bus_corner")
	# 4. The car showroom: Jetta, Ace 11, compact hatchback.
	var shop: Vector3 = ShopCatalog.LOCATIONS.cars
	camera.position = shop + Vector3(0.5, 2.6, 6.5)
	camera.look_at(shop + Vector3(-1.2, 0.6, -2.0))
	await shot(camera, "showroom")
	quit()
