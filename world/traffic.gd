extends Node3D
## City traffic on the residential street grid: seven closed loops, right-hand traffic, right
## turns only, every merge at a signalised junction (SignalPlan / TrafficSignals), so cars from
## different loops only ever meet where the signal phases separate them.
## Cedar Lane traffic-lane centres (StreetGrid.AVENUE.lane), right-hand traffic.
const LOOP = [Vector3(1.95, 0, 38), Vector3(1.95, 0, -242), Vector3(-1.95, 0, -242), Vector3(-1.95, 0, 38)]
var cars: Array[CharacterBody3D] = []
var drivers: Array[Dictionary] = []
var car_dimensions: Array[Vector3] = []
var speeds: Array[float] = []
## Loop index of each driver (parallel to drivers).
var loop_of: Array[int] = []
var elapsed: float = 0
## Kept for CityAudio's fallback discovery; the crossing heads are TrafficSignals now.
var signals: Array[MeshInstance3D] = []
## Vehicles per loop: east and west Cedar loops, the big south loop, the two avenue loops south
## of Refet Bele Street (SE, SW) and the two cross-street loops (Kara Fatma -398 eastbound,
## -538 westbound). 16 before the street-life pass, 70 now.
const COUNTS := [9, 9, 10, 7, 7, 4, 4]   # 50 cars (frame-time budget; was 70)
## Every fourth vehicle is a service vehicle drawn from VehicleCatalog.SERVICE; vehicle 1 is
## always a taxi. The rest are everyday cars (VehicleCatalog.TRAFFIC).
const SERVICE_EVERY := 4
## Per loop: may it carry one long vehicle (bus, fire/garbage truck)? Checked by
## tests/traffic_long_vehicle_test.gd, which sweeps each body along the route against the
## static colliders (a pickup once jammed on a corner pole).
const LONG_OK := [true, true, true, true, true, true, true]
## Corner arcs per loop. Vehicles over 6 m (VehicleCatalog.turns_tight) drive their own copy of
## each loop with tighter corners: both axles stay on the path, so on a wide arc a long body's middle
## cuts across the inner kerb corner; a tighter arc keeps the inner side off the kerb and the
## swing-out stays inside the junction (tests/traffic_long_vehicle_test.gd).
const CORNER := [11.0, 11.0, 9.0, 9.0, 9.0, 9.0, 9.0]
const LONG_CORNER := [6.0, 6.0, 6.0, 6.0, 6.0, 6.0, 6.0]
var loops: Array[SmoothRoute] = []
var long_loops: Array[SmoothRoute] = []
## Seconds until the route leaders (TrafficDriver.order) are re-linked.
var _order_t := 0.0

func _ready() -> void:
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
	# The south grid: side roads x = +-64, cross streets z = -258 / -398 / -538 / -678 and the
	# avenue between them. Lane centres 1.64 m off the street centrelines, 1.95 m on the avenue.
	var south := PackedVector3Array([Vector3(-62.36, 0, -259.64), Vector3(-62.36, 0, -676.36), Vector3(62.36, 0, -676.36), Vector3(62.36, 0, -259.64)])
	var south_east := PackedVector3Array([Vector3(62.36, 0, -259.64), Vector3(1.95, 0, -259.64), Vector3(1.95, 0, -676.36), Vector3(62.36, 0, -676.36)])
	var south_west := PackedVector3Array([Vector3(-1.95, 0, -676.36), Vector3(-1.95, 0, -259.64), Vector3(-62.36, 0, -259.64), Vector3(-62.36, 0, -676.36)])
	var kara_fatma := PackedVector3Array([Vector3(-62.36, 0, -259.64), Vector3(-62.36, 0, -396.36), Vector3(62.36, 0, -396.36), Vector3(62.36, 0, -259.64)])
	var lower := PackedVector3Array([Vector3(62.36, 0, -676.36), Vector3(62.36, 0, -539.64), Vector3(-62.36, 0, -539.64), Vector3(-62.36, 0, -676.36)])
	var paths: Array[PackedVector3Array] = [east, west, south, south_east, south_west, kara_fatma, lower]
	for li in range(paths.size()):
		loops.append(SmoothRoute.from_corners(paths[li], float(CORNER[li])))
		long_loops.append(SmoothRoute.from_corners(paths[li], float(LONG_CORNER[li])))
	var rng := RandomNumberGenerator.new()
	if VehicleCatalog.traffic_seed >= 0: rng.seed = VehicleCatalog.traffic_seed
	else: rng.randomize()
	var i := 0
	for li in range(paths.size()):
		var long_used := false
		var count: int = COUNTS[li] if not VehicleCatalog.legacy_traffic else [5, 5, 6, 0, 0, 0, 0][li]
		if count == 0: continue
		for slot in range(count):
			var service := i == 1 or i % SERVICE_EVERY == 3
			var id := VehicleCatalog.next_traffic_id() if not service else ("civil_taxi" if i == 1 else VehicleCatalog.next_service_id(rng, bool(LONG_OK[li]) and not long_used))
			if VehicleCatalog.is_long(id): long_used = true
			var route := route_for(li, id)
			# Buses and trucks cruise a little slower.
			var cruise := 6.5 if VehicleCatalog.turns_tight(id) else 8.0
			# Even spacing with a little jitter, so the queues do not look stamped.
			var s := route.total * (float(slot) + rng.randf_range(-0.12, 0.12)) / count
			# Loops share lanes after their merges: never spawn on top of another loop's car.
			s = TrafficDriver.free_spot(route, s, drivers, 10.0)
			var car := TrafficDriver.spawn(self, id, "TrafficCar%d" % i, route, s, cruise, 1 | 4)
			drivers.append(car)
			cars.append(car.body)
			car_dimensions.append(car.size)
			speeds.append(0)
			loop_of.append(li)
			SignalPlan.vehicles.append(car)
			i += 1

func _exit_tree() -> void:
	for car in drivers: SignalPlan.vehicles.erase(car)

## The route a vehicle of this model drives on loop `li` (tighter corners for long vehicles).
func route_for(li: int, id: String) -> SmoothRoute:
	return long_loops[li] if VehicleCatalog.turns_tight(id) else loops[li]

## Points on a circle from angle a0 to a1 (radians, either direction), every ~2 m.
static func ring_arc(centre: Vector3, radius: float, a0: float, a1: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	var steps := maxi(2, ceili(absf(a1 - a0) * radius / 2.0))
	for k in range(steps + 1):
		var a := lerpf(a0, a1, float(k) / steps)
		out.append(centre + Vector3(cos(a) * radius, 0, sin(a) * radius))
	return out

## Mid-block crossings (z -93 / -177): vehicles red, pedestrians WALK (SignalPlan "midblock").
func crossing_red() -> bool:
	return fmod(elapsed, 24.0) >= 16.0

func _physics_process(delta: float) -> void:
	elapsed += delta
	var space := get_world_3d().direct_space_state
	var camera: Node3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	var clocks := {"city": elapsed}
	_order_t -= delta
	if _order_t <= 0.0:
		_order_t = 2.0
		TrafficDriver.order(drivers)
	for i in range(drivers.size()):
		var car: Dictionary = drivers[i]
		var dt := TrafficDriver.due(car, delta, camera)
		if dt < 0.0: continue
		var lead := TrafficDriver.leader(drivers, i)
		var sig := SignalPlan.limit(car, clocks, SignalPlan.stops_for(car.route))
		TrafficDriver.think(car, dt, float(lead[0]), float(lead[1]), sig, space, 1 | 4)
		speeds[i] = car.speed

## Re-link the route leaders now (after cars were moved about, e.g. by tests).
func reorder() -> void:
	_order_t = 0.0
