extends Node3D
## Local lane-following traffic with a timed pedestrian crossing phase.
## Cedar Lane traffic-lane centres (StreetGrid.AVENUE.lane), right-hand traffic.
const LOOP = [Vector3(1.95, 0, 38), Vector3(1.95, 0, -242), Vector3(-1.95, 0, -242), Vector3(-1.95, 0, 38)]
var cars: Array[CharacterBody3D] = []
var drivers: Array[Dictionary] = []
var car_dimensions: Array[Vector3] = []
var speeds: Array[float] = []
var elapsed: float = 0
var signals: Array[MeshInstance3D] = []

func _ready() -> void:
	for z in [-93, -177]:
		for x in [-7, 7]:
			var pole := MeshInstance3D.new()
			var shape := CylinderMesh.new()
			shape.top_radius = 0.07
			shape.bottom_radius = 0.07
			shape.height = 3
			pole.mesh = shape
			var steel := StandardMaterial3D.new()
			steel.albedo_color = Color("39464b")
			pole.material_override = steel
			pole.position = Vector3(x, 1.5, z)
			add_child(pole)
			part(self, Vector3(x, 3.05, z), Vector3(0.42, 0.62, 0.28), Color("202b30"))
			var light := MeshInstance3D.new()
			var globe := SphereMesh.new()
			globe.radius = 0.12
			globe.height = 0.24
			light.mesh = globe
			light.position = Vector3(x, 3.1, z + (0.17 if x > 0 else -0.17))
			light.material_override = StandardMaterial3D.new()
			add_child(light)
			signals.append(light)
	# Smooth routes: the avenue shuttle turns round with bulb U-turns at both ends; the side-road
	# loop and the two roundabouts have rounded corners (SmoothRoute).
	var avenue := SmoothRoute.shuttle(Vector3(0, 0, 38), Vector3(0, 0, -242), 1.95, 4.4)
	var north := SmoothRoute.from_corners(PackedVector3Array([Vector3(-62.36, 0, -259.64), Vector3(-62.36, 0, -676.36), Vector3(62.36, 0, -676.36), Vector3(62.36, 0, -259.64)]), 9.0)
	var circles: Array[SmoothRoute] = []
	for center_x in [-64.0, 64.0]:
		var ring := PackedVector3Array()
		for sample in range(48):
			var a := -TAU * sample / 48.0
			ring.append(Vector3(center_x + 20 * cos(a), 0, -145 + 20 * sin(a)))
		circles.append(SmoothRoute.from_corners(ring, 30.0))
	for i in range(16):
		var route: SmoothRoute = avenue if i < 6 else (north if i < 14 else circles[i - 14])
		var start := route.total * (float(i % 6) / 6.0 if i < 6 else (float(i - 6) / 8.0 if i < 14 else 0.0))
		var car := TrafficDriver.spawn(self, VehicleCatalog.next_traffic_id(), "TrafficCar%d" % i, route, start, 4.2 if i >= 14 else 8.0, 1 | 4)
		drivers.append(car)
		cars.append(car.body)
		car_dimensions.append(car.size)
		speeds.append(0)
func part(car: Node3D, position: Vector3, dimensions: Vector3, color: Color) -> void:
	var visual := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = dimensions
	visual.mesh = mesh
	visual.position = position
	var surface := StandardMaterial3D.new()
	surface.albedo_color = color
	surface.metallic = 0.3
	surface.roughness = 0.35
	if color == Color("3f5361"):
		surface.roughness = 0.12
		surface.metallic = 0.5
	visual.material_override = surface
	car.add_child(visual)

func crossing_red() -> bool:
	return fmod(elapsed, 24.0) >= 16.0

func _physics_process(delta: float) -> void:
	elapsed += delta
	for signal_mesh in signals:
		var material := signal_mesh.material_override as StandardMaterial3D
		material.albedo_color = Color("e35145") if crossing_red() else Color("64cc8c")
	var space := get_world_3d().direct_space_state
	for i in range(drivers.size()):
		var car: Dictionary = drivers[i]
		var body: CharacterBody3D = car.body
		var direction := TrafficDriver.heading(car)
		var limit: float = car.cruise
		var clearance: float = float(car.half) + 1.0 + float(car.speed) * float(car.speed) / 10.0
		if TrafficDriver.blocked(car, clearance + 1.5, space, 1 | 4):
			limit = 0.0
		if crossing_red():
			for crossing in [-93.0, -177.0]:
				var ahead: float = (crossing - body.position.z) * direction.z
				if absf(body.position.x) < 6.0 and ahead > 3 and ahead < clearance + 5:
					limit = 0.0
		TrafficDriver.drive(car, delta, limit)
		speeds[i] = car.speed
