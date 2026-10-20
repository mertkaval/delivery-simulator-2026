class_name TrafficDriver
extends RefCounted
## Shared AI vehicle: a physics body carrying a converted model, driven along a SmoothRoute.
## The body never pivots: it is posed from its rear/front axle positions on the path every
## frame, front wheels steer by the real angle, wheels spin by the distance travelled, and the
## speed follows the curvature ahead with gentle acceleration and firm braking.

## Creates the body + model and returns the driving state.
static func spawn(parent: Node, id: String, label: String, route: SmoothRoute, s: float, cruise: float, mask := 5) -> Dictionary:
	var body := CharacterBody3D.new()
	body.name = label
	body.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	body.collision_layer = 1
	body.collision_mask = mask
	parent.add_child(body)
	var model := VehicleCatalog.create(id, 190.0)
	body.add_child(model)
	var size := VehicleCatalog.dimensions(id, model)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y * 0.5 + 0.08
	body.add_child(shape)
	var car := {"body": body, "model": model, "id": id, "route": route, "s": s, "speed": 0.0, "cruise": cruise,
		"wheelbase": VehicleCatalog.wheelbase(id, model), "radius": VehicleCatalog.wheel_radius(id, model),
		"wheels": VehicleCatalog.wheels(model), "pivots": VehicleCatalog.steer_pivots(model),
		"half": size.z * 0.5, "size": size, "steer": 0.0}
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
static func drive(car: Dictionary, delta: float, limit: float) -> void:
	var route: SmoothRoute = car.route
	var target := minf(limit, route.safe_speed(float(car.s) + float(car.half), float(car.cruise)))
	var v: float = car.speed
	v = move_toward(v, target, delta * (4.5 if target < v else 1.6))
	var travel := v * delta
	var body: CharacterBody3D = car.body
	if travel > 0.0005:
		var wb: float = car.wheelbase
		var pose := route.pose(float(car.s) + travel - wb * 0.5, wb)
		var motion := Vector3(pose.position.x, 0.04, pose.position.z) - body.position
		# Never drive through the player or another vehicle.
		if body.test_move(body.global_transform, motion):
			v = 0.0
			travel = 0.0
		else:
			car.s = float(car.s) + travel
			body.position += motion
			body.rotation.y = pose.yaw
			car.steer = lerpf(float(car.steer), float(pose.steer), minf(delta * 6.0, 1.0))
	car.speed = v
	for wheel in car.wheels:
		(wheel as Node3D).rotate_object_local(Vector3.RIGHT, -travel / maxf(float(car.radius), 0.2))
	for pivot in car.pivots:
		(pivot as Node3D).rotation.y = float(car.steer)
	if car.model.has_method("update_driving_visuals") and car.model.get("traffic") == true:
		pass

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
