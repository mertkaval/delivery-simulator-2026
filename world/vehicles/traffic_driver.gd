class_name TrafficDriver
extends RefCounted
## Shared AI vehicle: a physics body carrying a converted model, driven along a SmoothRoute.
## The body never pivots: it is posed from its rear/front axle positions on the path every
## frame, front wheels steer by the real angle, wheels spin by the distance travelled, and the
## speed follows the curvature ahead with gentle acceleration and firm braking.
##
## think() is the full driver: curve speed, the leader on the same route (smooth car
## following with a standstill gap and a ~1 s headway), anything else in the lane ahead (rays
## that follow the route round bends: the player, people, buses, cars from other routes),
## traffic signals (SignalPlan.limit) and a short reaction time when pulling away. Distant
## vehicles update every step within CLOSE of the camera, every second step up to NEAR and
## beyond NEAR at an eighth of the rate (swept moves only within SWEEP) without
## wheel animation and stop casting shadows beyond SHADOW.

const NEAR := 120.0
const CLOSE := 50.0
const SHADOW := 60.0
const SWEEP := 70.0
const ACCEL := 1.7
const BRAKE := 4.5
const EMERGENCY := 8.0
const FOLLOW_DECEL := 2.8
const HEADWAY := 1.0
static var _touch := KinematicCollision3D.new()

## Creates the body + model and returns the driving state.
static func spawn(parent: Node, id: String, label: String, route: SmoothRoute, s: float, cruise: float, mask := 5) -> Dictionary:
	var body := CharacterBody3D.new()
	body.name = label
	body.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	body.collision_layer = 1
	body.collision_mask = mask
	parent.add_child(body)
	var model := VehicleCatalog.create(id, 165.0)
	body.add_child(model)
	var size := VehicleCatalog.dimensions(id, model)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y * 0.5 + 0.08
	body.add_child(shape)
	# Per-driver character: standstill gap, reaction time and a little cruise variation.
	var h := absi(hash(label))
	var car := {"body": body, "model": model, "id": id, "route": route, "s": s, "speed": 0.0, "cruise": cruise * (0.92 + float(h % 17) / 100.0),
		"wheelbase": VehicleCatalog.wheelbase(id, model), "radius": VehicleCatalog.wheel_radius(id, model),
		"wheels": VehicleCatalog.wheels(model), "pivots": VehicleCatalog.steer_pivots(model),
		"half": size.z * 0.5, "size": size, "steer": 0.0,
		"min_gap": 1.7 + float(h % 11) * 0.11, "react": 0.35 + float((h / 11) % 9) * 0.09, "go_t": 0.0,
		"accel": 0.0, "braking": false, "sig_state": 0, "sig_commit": -1, "dist": 0.0, "curve_v": cruise, "curve_t": 0.0,
		"tick": h % 3, "skip": 0.0, "shadow": true, "near": true}
	body.set_meta("car", car)
	place(car)
	return car

## Pose the body for the current distance along the route.
static func place(car: Dictionary) -> void:
	var route: SmoothRoute = car.route
	var wb: float = car.wheelbase
	var pose := route.pose(float(car.s) - wb * 0.5, wb)
	var body: CharacterBody3D = car.body
	body.position = Vector3(pose.position.x, 0.04, pose.position.z)
	body.rotation = Vector3(0, pose.yaw, 0)

## Current travel direction (unit, horizontal).
static func heading(car: Dictionary) -> Vector3:
	return -(car.body as Node3D).global_basis.z

## Advance one physics step. `limit` caps the speed (0 = stop for a signal or obstacle).
## `physics` false skips the swept move and the wheel animation (distant vehicles).
static func drive(car: Dictionary, delta: float, limit: float, physics := true) -> void:
	var route: SmoothRoute = car.route
	var target := minf(limit, route.curve_speed(float(car.s) + float(car.half), float(car.cruise)))
	var v0: float = car.speed
	var v := v0
	var rate := ACCEL if target > v else (EMERGENCY if target < v - 3.0 else BRAKE)
	v = move_toward(v, target, delta * rate)
	var travel := v * delta
	var body: CharacterBody3D = car.body
	if travel > 0.0005:
		var wb: float = car.wheelbase
		var pose := route.pose(float(car.s) + travel - wb * 0.5, wb)
		var motion := Vector3(pose.position.x, 0.04, pose.position.z) - body.position
		# Never drive through the player or another vehicle. A pedestrian (layer 4 only) who
		# stays against the car for a long time (stranded on a zebra next to its wing) is
		# edged past, as people step aside for a creeping car.
		# The swept test only near the camera (rays keep the lane ahead clear further out).
		var hit := physics and float(car.get("dist", 0.0)) < SWEEP and body.test_move(body.global_transform, motion, _touch)
		if hit and float(car.get("go_t", 0.0)) > 1.5:
			var c := _touch.get_collider() as CollisionObject3D
			# Two cars wedged side by side where lanes merge: the one in front drives on (the
			# contact is beside or behind it), which frees the other.
			if c is CharacterBody3D and c.has_meta("car"):
				var rel := (c as Node3D).global_position - body.global_position
				if rel.dot(motion.normalized()) < 0.0: hit = false
			elif float(car.go_t) > 6.0 and c is CharacterBody3D and (c.collision_layer & 1) == 0: hit = false
		if hit:
			v = 0.0
			travel = 0.0
		else:
			car.s = float(car.s) + travel
			body.position += motion
			body.rotation.y = pose.yaw
			car.steer = lerpf(float(car.steer), float(pose.steer), minf(delta * 6.0, 1.0))
	car.accel = (v - v0) / maxf(delta, 0.001)
	car.braking = v < v0 - 0.02 * delta or (v < 0.3 and limit < 0.3)
	car.speed = v
	if not physics: return
	for wheel in car.wheels:
		(wheel as Node3D).rotate_object_local(Vector3.RIGHT, -travel / maxf(float(car.radius), 0.2))
	for pivot in car.pivots:
		(pivot as Node3D).rotation.y = float(car.steer)

## Level of detail: is this vehicle due an update this physics step? Returns the time step to
## simulate (distant vehicles accumulate four steps) or -1. Also toggles shadows by distance.
## `camera` null = everything is near (headless tests).
static func due(car: Dictionary, delta: float, camera: Node3D) -> float:
	var body: CharacterBody3D = car.body
	var dist := body.global_position.distance_to(camera.global_position) if camera != null else 0.0
	car.dist = dist
	var near := dist < NEAR
	car.near = near
	var shadow := dist < SHADOW
	if shadow != bool(car.shadow): set_shadows(car, shadow)
	if dist < CLOSE:
		car.skip = 0.0
		return delta
	# Mid range: every second step (still with swept moves and rays); far: every eighth.
	car.skip = float(car.skip) + delta
	car.tick = (int(car.tick) + 1) % (2 if near else 8)
	if int(car.tick) != 0: return -1.0
	var dt := float(car.skip)
	car.skip = 0.0
	return dt

## The full driver step (see the class notes), for a vehicle due() an update. `leader_gap` /
## `leader_speed`: bumper gap to the vehicle ahead on the same route and its speed (INF if
## none). `signal_limit` from SignalPlan.limit.
static func think(car: Dictionary, delta: float, leader_gap: float, leader_speed: float, signal_limit: float,
		space: PhysicsDirectSpaceState3D, mask: int) -> void:
	var near: bool = car.near
	var dist: float = car.dist
	var v: float = car.speed
	var limit: float = car.cruise
	limit = minf(limit, follow_speed(leader_gap, leader_speed, float(car.min_gap)))
	# Rays every other step near the camera (the cached gap shrinks by the distance driven in
	# between, i.e. the obstacle is assumed to stand still); corner rays for people only close up.
	car.ray_t = (int(car.get("ray_t", 0)) + 1) % 2
	if not near or int(car.ray_t) == 0 or not car.has("gap_c"):
		var reach := 6.0 + v * v / (2.0 * FOLLOW_DECEL) + v * HEADWAY
		var hit := gap_ahead(car, reach, space, mask, dist < 45.0)
		car.gap_c = float(hit[0])
		car.gap_v = float(hit[1])
	else:
		car.gap_c = float(car.gap_c) - v * delta
	limit = minf(limit, follow_speed(float(car.gap_c), float(car.gap_v), float(car.min_gap) * 0.8))
	limit = minf(limit, signal_limit)
	# Pulling away from a standstill takes a moment (queues discharge one by one).
	if v < 0.15 and limit > 0.6:
		car.go_t = float(car.go_t) + delta
		if float(car.go_t) < float(car.react): limit = 0.0
	elif v >= 0.15:
		car.go_t = 0.0
	drive(car, delta, limit, near)

## Speed that keeps a safe distance to an obstacle `gap` metres ahead moving at `lead`.
static func follow_speed(gap: float, lead: float, min_gap: float) -> float:
	if gap == INF: return INF
	var room := gap - min_gap
	if room <= 0.0: return 0.0 if lead < 0.5 else minf(lead * 0.5, room + lead)
	return maxf(0.0, minf(sqrt(lead * lead + 2.0 * FOLLOW_DECEL * room), lead + room / HEADWAY))

## Bumper gap (m) to the nearest thing in the lane ahead and its speed: [gap, speed], gap INF
## if clear. Rays run along the route (so they follow bends) at body height; static props
## (poles, signs) are ignored - nothing static stands in a lane (tests/prop_placement_test.gd) -
## and the swept move still stops a car that would touch one. `side` adds two rays at the
## car's corners on the first stretch (people stepping off the kerb).
static func gap_ahead(car: Dictionary, reach: float, space: PhysicsDirectSpaceState3D, mask: int, side := true) -> Array:
	var body: CharacterBody3D = car.body
	var route: SmoothRoute = car.route
	var front: float = float(car.s) + float(car.half)
	var up := Vector3.UP * 0.8
	var start := body.global_position + heading(car) * float(car.half) + up
	var exclude: Array[RID] = [body.get_rid()]
	var best := INF
	var best_speed := 0.0
	var travelled := 0.0
	var steps := 2
	var a := start
	for k in range(steps):
		var b := route.at(front + reach * float(k + 1) / steps) + up
		var hit := ray(space, a, b, mask, exclude)
		if not hit.is_empty():
			best = travelled + a.distance_to(hit.position)
			best_speed = speed_of(hit.collider)
			break
		travelled += a.distance_to(b)
		a = b
	if side:
		var dir := heading(car)
		var lateral := dir.cross(Vector3.UP).normalized() * (float(car.size.x) * 0.5 - 0.15)
		var end := route.at(front + minf(reach, 8.0)) + up
		for sgn in [-1.0, 1.0]:
			var hit := ray(space, start + lateral * sgn, end + lateral * sgn, mask, exclude)
			if not hit.is_empty():
				var d: float = (start + lateral * sgn).distance_to(hit.position)
				if d < best:
					best = d
					best_speed = speed_of(hit.collider)
	return [best, best_speed]

## First non-static hit between a and b (static props are skipped by re-casting past them).
static func ray(space: PhysicsDirectSpaceState3D, a: Vector3, b: Vector3, mask: int, exclude: Array[RID]) -> Dictionary:
	var skip: Array[RID] = exclude.duplicate()
	for attempt in range(3):
		var query := PhysicsRayQueryParameters3D.create(a, b, mask, skip)
		var hit := space.intersect_ray(query)
		if hit.is_empty(): return {}
		var c: Object = hit.collider
		if c is StaticBody3D and not c is AnimatableBody3D:
			skip.append((c as CollisionObject3D).get_rid())
			continue
		return hit
	return {}

static func speed_of(collider: Object) -> float:
	if collider == null: return 0.0
	if collider.has_meta("car"):
		var other: Dictionary = collider.get_meta("car")
		return maxf(float(other.speed), 0.0)
	if collider is CharacterBody3D: return (collider as CharacterBody3D).velocity.length()
	return 0.0

## Cast shadows near the camera only (distant traffic is the bulk of the shadow casters).
static func set_shadows(car: Dictionary, on: bool) -> void:
	car.shadow = on
	if not car.has("meshes"):
		var found: Array[GeometryInstance3D] = []
		for m in (car.model as Node).find_children("*", "GeometryInstance3D", true, false): found.append(m as GeometryInstance3D)
		car.meshes = found
	for m: GeometryInstance3D in car.meshes:
		m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if on else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

## Bumper gaps to the vehicle ahead on the same route for every car of `list`:
## returns {car instance id -> [gap, leader speed]}. Cars are grouped by route and sorted by s.
## Links every car to the one ahead of it on the same route: car.ahead = index into `list`
## (-1 if alone). Cars on a route never overtake each other, so callers refresh this only
## every couple of seconds (and after moving cars about).
static func order(list: Array[Dictionary]) -> void:
	var groups: Dictionary = {}
	for i in range(list.size()):
		var key: int = (list[i].route as SmoothRoute).get_instance_id()
		if not groups.has(key): groups[key] = []
		(groups[key] as Array).append(i)
	for key: int in groups:
		var idx: Array = groups[key]
		var total: float = (list[idx[0]].route as SmoothRoute).total
		idx.sort_custom(func(a: int, b: int) -> bool: return fposmod(float(list[a].s), total) < fposmod(float(list[b].s), total))
		for k in range(idx.size()):
			list[idx[k]].ahead = -1 if idx.size() == 1 else int(idx[(k + 1) % idx.size()])

## [gap, speed] to the vehicle ahead on the same route (order() must have run).
static func leader(list: Array[Dictionary], i: int) -> Array:
	var me: Dictionary = list[i]
	var a: int = me.get("ahead", -1)
	if a < 0 or a >= list.size(): return [INF, 0.0]
	var ahead: Dictionary = list[a]
	var total: float = (me.route as SmoothRoute).total
	return [fposmod(float(ahead.s) - float(me.s), total) - float(ahead.half) - float(me.half), float(ahead.speed)]

## A spawn distance at or after `s` on `route` that is clear of junctions and at least `min_d`
## metres from every vehicle in `others` (vehicles of other routes share lanes after merges).
static func free_spot(route: SmoothRoute, s: float, others: Array[Dictionary], min_d := 10.0) -> float:
	for attempt in range(80):
		var p := route.at(s)
		var ok := not SignalPlan.in_junction(route, s, 4.0)
		if ok:
			for other in others:
				if (other.body as Node3D).position.distance_to(Vector3(p.x, 0.04, p.z)) < min_d:
					ok = false
					break
		if ok: return s
		s += 3.0
	return s

## Is something within `reach` metres straight ahead (three rays across the car's width)?
static func blocked(car: Dictionary, reach: float, space: PhysicsDirectSpaceState3D, mask := 5) -> bool:
	var body: CharacterBody3D = car.body
	var dir := heading(car)
	var side := dir.cross(Vector3.UP).normalized()
	for offset in [-0.7, 0.0, 0.7]:
		var origin: Vector3 = body.global_position + Vector3.UP * 0.8 + side * float(offset)
		var query := PhysicsRayQueryParameters3D.create(origin, origin + dir * (float(car.half) + reach), mask, [body.get_rid()])
		if not space.intersect_ray(query).is_empty(): return true
	return false
