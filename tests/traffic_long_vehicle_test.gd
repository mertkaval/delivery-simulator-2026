extends SceneTree
## Sweeps every traffic vehicle type along the city traffic loops (and the downtown service
## routes) exactly as TrafficDriver poses it, and checks the body box never meets a static
## collider (poles, signals, hydrants, buildings, kerb blocks). A hit would jam that vehicle for
## good, as a pickup once did on a corner pole. Vehicles a route does not allow are reported only.
var checks := 0
var failed := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		printerr("FAIL: " + text)

func _initialize() -> void:
	call_deferred("run")

## Static colliders the box would overlap at distance s (rear axle) along the route.
func hits_at(space: PhysicsDirectSpaceState3D, route: SmoothRoute, s: float, size: Vector3, wb: float) -> Array[String]:
	var pose := route.pose(s, wb)
	var box := BoxShape3D.new()
	box.size = size
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = box
	q.collision_mask = 1 | 4
	var p: Vector3 = pose.position
	q.transform = Transform3D(Basis(Vector3.UP, float(pose.yaw)), Vector3(p.x, 0.04 + size.y * 0.5 + 0.08, p.z))
	var out: Array[String] = []
	for hit in space.intersect_shape(q, 8):
		var c: Object = hit.collider
		if c is CharacterBody3D or c is RigidBody3D: continue
		var n := c as Node3D
		out.append("%s@(%.0f,%.0f)" % [n.name, p.x, p.z])
	return out

func sweep(space: PhysicsDirectSpaceState3D, route: SmoothRoute, id: String) -> Array[String]:
	var spec := VehicleCatalog.spec_of(id)
	var size: Vector3 = VehicleCatalog.dimensions(id, null) if id == "jetta" else spec.collision_size
	var wb: float = 2.68 if id == "jetta" else float(spec.wheelbase)
	var found: Array[String] = []
	var s := 0.0
	while s < route.total:
		for h in hits_at(space, route, s, size, wb):
			var where := "%s s=%.0f" % [h, s]
			if found.size() < 6 and not found.any(func(f: String) -> bool: return f.begins_with(h)): found.append(where)
		s += 0.75
	return found

## Square kerb corners of every StreetGrid junction (Cedar Lane, side roads x cross streets).
func kerb_corners() -> PackedVector2Array:
	var out := PackedVector2Array()
	var roads := StreetGrid.roads()
	for a in roads:
		for b in roads:
			var a_ns: bool = is_equal_approx((a.a as Vector2).x, (a.b as Vector2).x)
			var b_ns: bool = is_equal_approx((b.a as Vector2).x, (b.b as Vector2).x)
			if not a_ns or b_ns: continue
			var x: float = (a.a as Vector2).x
			var z: float = (b.a as Vector2).y
			var z_lo := minf((a.a as Vector2).y, (a.b as Vector2).y) - 6.0
			var z_hi := maxf((a.a as Vector2).y, (a.b as Vector2).y) + 6.0
			var x_lo := minf((b.a as Vector2).x, (b.b as Vector2).x) - 6.0
			var x_hi := maxf((b.a as Vector2).x, (b.b as Vector2).x) + 6.0
			if z < z_lo or z > z_hi or x < x_lo or x > x_hi: continue
			var hx: float = a.profile.half
			var hz: float = b.profile.half
			for sx in [-1.0, 1.0]:
				for sz in [-1.0, 1.0]: out.append(Vector2(x + sx * hx, z + sz * hz))
	return out

## Deepest a kerb corner gets inside the body footprint along the route (m, 0 = never).
func kerb_cut(route: SmoothRoute, id: String, corners: PackedVector2Array) -> Vector3:
	var spec := VehicleCatalog.spec_of(id)
	var size: Vector3 = VehicleCatalog.dimensions(id, null) if id == "jetta" else spec.collision_size
	var wb: float = 2.68 if id == "jetta" else float(spec.wheelbase)
	var worst := Vector3.ZERO   # depth, x, z
	var s := 0.0
	while s < route.total:
		var pose := route.pose(s, wb)
		var p: Vector3 = pose.position
		var basis := Basis(Vector3.UP, float(pose.yaw))
		for k in corners:
			if absf(k.x - p.x) > 12.0 or absf(k.y - p.z) > 12.0: continue
			var local := basis.inverse() * (Vector3(k.x, 0, k.y) - p)
			var depth := minf(size.x * 0.5 - absf(local.x), size.z * 0.5 - absf(local.z))
			if depth > worst.x: worst = Vector3(depth, k.x, k.y)
		s += 0.5
	return worst

func run() -> void:
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	for i in range(3): await physics_frame
	var space: PhysicsDirectSpaceState3D = game.world.get_world_3d().direct_space_state
	var traffic: Node = game.world.get_node("CityTraffic")
	# Park every AI vehicle out of the way so only the static world is tested.
	for d in traffic.drivers: (d.body as Node3D).position.y = -80
	var services: Node = null
	for n in game.world.find_children("*", "Node3D", true, false):
		if n.get_script() == load("res://world/living_city/service_traffic.gd"): services = n
	if services: for d in services.fleet: (d.body as Node3D).position.y = -80
	await physics_frame
	await physics_frame
	var ids: Array[String] = ["car_sedan", "car_minivan", "ace11"]
	for id: String in VehicleCatalog.SERVICE: ids.append(id)
	var corners := kerb_corners()
	check(corners.size() >= 32, "Kerb corners found (%d)" % corners.size())
	for li in range(traffic.loops.size()):
		for id in ids:
			var allowed: bool = not VehicleCatalog.is_long(id) or bool(traffic.LONG_OK[li])
			var route: SmoothRoute = traffic.route_for(li, id)
			var found := sweep(space, route, id)
			var cut := kerb_cut(route, id, corners)
			print("loop %d %-20s %s %s  kerb cut %.2f m at (%.0f, %.0f)" % [li, id, "allowed" if allowed else "not used", "clear" if found.is_empty() else str(found), cut.x, cut.y, cut.z])
			if allowed: check(found.is_empty(), "Traffic loop %d: %s sweeps clear of static colliders %s" % [li, id, found])
			# Vehicles over 6 m get tighter corner arcs so their bodies stay off the kerb corners.
			if allowed and VehicleCatalog.turns_tight(id): check(cut.x < 0.25, "Traffic loop %d: %s stays off the kerb corners (%.2f m)" % [li, id, cut.x])
	# Every vehicle actually spawned in the city loops is allowed there and on its route.
	for d in traffic.drivers:
		var li: int = traffic.drivers.find(d)
		li = 0 if li < 5 else (1 if li < 10 else 2)
		check(not VehicleCatalog.is_long(str(d.id)) or bool(traffic.LONG_OK[li]), "%s may drive loop %d" % [d.id, li])
		check(d.route == traffic.route_for(li, str(d.id)), "%s drives its size's route" % d.id)
	if services:
		for d in services.fleet:
			var found := sweep(space, d.route, str(d.id))
			print("service %-22s %s" % [d.id, "clear" if found.is_empty() else str(found)])
	print("TRAFFIC LONG VEHICLE PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "TRAFFIC LONG VEHICLE: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
