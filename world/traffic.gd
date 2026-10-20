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
	# Closed circuits, right-hand traffic, no U-turns anywhere: two loops share the avenue (one
	# northbound, one southbound) and close through Refet Bele Street, the estate roads with their
	# park roundabouts (driven counter-clockwise) and Nezahat Onbaşı Street. The north loop runs
	# the side streets and passes the traffic circles (SmoothRoute bends round each island).
	var east := PackedVector3Array([Vector3(1.95, 0, 46), Vector3(1.95, 0, -256.36), Vector3(62, 0, -256.36), Vector3(62, 0, -172)])
	east.append_array(ring_arc(Vector3(64, 0, -145), 22.0, -PI / 2 - 0.3, -3 * PI / 2 + 0.3))
	east.append_array(PackedVector3Array([Vector3(62, 0, -118), Vector3(62, 0, 46)]))
	var west := PackedVector3Array([Vector3(-1.95, 0, -256.36), Vector3(-1.95, 0, 46), Vector3(-62, 0, 46), Vector3(-62, 0, -118)])
	west.append_array(ring_arc(Vector3(-64, 0, -145), 22.0, PI / 2 - 0.3, -PI / 2 + 0.3))
	west.append_array(PackedVector3Array([Vector3(-62, 0, -172), Vector3(-62, 0, -256.36)]))
	var loops: Array[SmoothRoute] = [SmoothRoute.from_corners(east, 8.0), SmoothRoute.from_corners(west, 8.0),
		SmoothRoute.from_corners(PackedVector3Array([Vector3(-62.36, 0, -259.64), Vector3(-62.36, 0, -676.36), Vector3(62.36, 0, -676.36), Vector3(62.36, 0, -259.64)]), 9.0)]
	for i in range(16):
		var li := 0 if i < 5 else (1 if i < 10 else 2)
		var count := 5 if li < 2 else 6
		var slot := i - (0 if li == 0 else (5 if li == 1 else 10))
		var route: SmoothRoute = loops[li]
		var car := TrafficDriver.spawn(self, VehicleCatalog.next_traffic_id(), "TrafficCar%d" % i, route, route.total * float(slot) / count, 8.0, 1 | 4)
		drivers.append(car)
		cars.append(car.body)
		car_dimensions.append(car.size)
		speeds.append(0)

## Points on a circle from angle a0 to a1 (radians, either direction), every ~2 m.
static func ring_arc(centre: Vector3, radius: float, a0: float, a1: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	var steps := maxi(2, ceili(absf(a1 - a0) * radius / 2.0))
	for k in range(steps + 1):
		var a := lerpf(a0, a1, float(k) / steps)
		out.append(centre + Vector3(cos(a) * radius, 0, sin(a) * radius))
	return out

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
