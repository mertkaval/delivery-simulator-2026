class_name CourierPlayer
extends CharacterBody3D
var camera: Camera3D
var session: DeliverySession
var sensitivity: float = 0.002
var mounted: bool = false
var bicycle: Node3D
var riding_speed: float = 0.0
var wheels: Array[Node3D] = []
var body_collision: CollisionShape3D
var equipment: Node3D
var headlight: SpotLight3D
var parked_body: StaticBody3D
## Steering state: front-wheel angle (radians, + = left), visual lean and the head-tube pivot.
var steer_angle := 0.0
var lean := 0.0
var steering_pivot: Node3D
## Every node that yaws with the steering input: the bicycle fork pivot and a car's
## front-wheel Steer* pivots. The car's SteeringWheel turns about its own axis.
var steer_pivots: Array[Node3D] = []
var steering_wheel: Node3D
## Optional scene for isolated vehicle tests; the normal shop catalog is unchanged.
@export var vehicle_scene_override: PackedScene
const BIKE_WHEELBASE := 1.1
const CAR_WHEELBASE := 2.7
## Car handling (arcade-smooth): smoothed steering input, a speed-aware turn rate with a little
## yaw inertia, and a chase camera that swings behind the car with a slight lag.
const CAR_CAMERA_OFFSET := Vector3(0, 2.15, 4.3)
const CAR_STEER_IN := 5.0        ## how fast the input builds when you press A/D (1/s)
const CAR_STEER_OUT := 7.0       ## how fast it returns to centre when released (1/s)
const CAR_MAX_YAW := 1.25        ## peak turn rate (rad/s), reached around 15-20 km/h
const CAR_MIN_RADIUS := 4.6      ## tightest circle at walking pace (m)
const CAR_YAW_RESPONSE := 7.0    ## yaw inertia: higher = snappier (1/s)
const CAR_CAMERA_LAG := 2.8      ## how quickly the camera swings back behind the car (1/s)
var car_steer_input := 0.0
var car_yaw_rate := 0.0
var car_camera_yaw := 0.0
var car_look_timer := 0.0
## View: third person (default) or first person, toggled with V (GameSettings "third_person").
## The camera stays this node's child with rotation = aim; PlayerCameraRig moves it.
var third_person := true
var eye_height := 1.65
var view: PlayerCameraRig
var avatar: PlayerAvatar
## Child of the camera that carries a held package: at the camera in first person, in the
## character's hands in third person (app_root parents held packages here).
var hold_socket: Node3D
## Where a held package sits in the socket (first person: two hands, low right of the view).
static var HOLD_POSE := Transform3D(Basis.from_euler(Vector3(0.15, -0.35, 0)), Vector3(0.22, -0.42, -0.55))
## On-foot locomotion (m/s, m/s^2): hold Ctrl to walk, W runs, Shift sprints.
const WALK_SPEED := 1.5
const RUN_SPEED := 3.5
const SPRINT_SPEED := 5.8
const BACK_SPEED := 2.0
const ACCEL := 11.0
const DECEL := 16.0
const AIR_ACCEL := 2.5
const JUMP_SPEED := 5.0
const GRAVITY := 20.0
const COYOTE := 0.12
const JUMP_BUFFER := 0.12
var coyote_time := 0.0
var jump_buffer := 0.0
var last_fall_speed := 0.0
var land_recovery := 0.0
var _was_on_floor := true
var _mouse_still := 0.0
## Bicycle rider markers (Seat, GripL/R, Crank, PedalL/R) and drivetrain state.
var bike_markers: Dictionary = {}
var crank_angle := 0.0
var pedalling := false
var stopped_time := 0.0
var coast_time := 0.0
var stand_lean := 0.0
const GEAR_RATIO := 2.2         ## wheel turns per crank turn (city bike, ~60 rpm at 18 km/h)
var car_eye := Vector3.ZERO
## A courier action is playing (pack / leave / hand over): no walking or jumping, the view
## stays (CourierSequence).
var busy := false

func setup_bicycle() -> void:
	replace_vehicle(Vector3(-8, 0, 19))

func replace_vehicle(at: Vector3) -> void:
	if is_instance_valid(bicycle): bicycle.queue_free()
	var asset := ShopCatalog.vehicle_asset(session.active_vehicle) if session.active_vehicle != "" else "bicycle"
	bicycle = vehicle_scene_override.instantiate() if vehicle_scene_override else CityAssets.create_player_vehicle(asset)
	bicycle.name = "CourierBicycle"
	get_parent().add_child(bicycle)
	if bicycle.has_method("bind_driver"): bicycle.bind_driver(self)
	bicycle.position = at
	parked_body=StaticBody3D.new()
	bicycle.add_child(parked_body)
	var parking_shape := CollisionShape3D.new()
	var parking_bounds := BoxShape3D.new()
	parking_bounds.size=vehicle_bounds() if ShopCatalog.is_car(session.active_vehicle) else Vector3(.5,.8,1.6)
	parking_shape.shape=parking_bounds
	parking_shape.position.y=parking_bounds.size.y*.5+vehicle_collision_lift()
	parked_body.add_child(parking_shape)
	# A New Game starts on foot: the vehicle node exists (code keeps a reference) but is hidden
	# and has no collision until a vehicle is bought.
	bicycle.visible = has_vehicle()
	if not has_vehicle(): parked_body.collision_layer = 0
	wheels = CityAssets.wheel_nodes(bicycle)
	steering_pivot = bicycle.find_child("SteeringPivot", true, false) as Node3D
	steer_pivots.clear()
	for node in bicycle.find_children("Steer*", "Node3D", true, false):
		# Only front-axle pivots steer: the Jetta also has SteerRear* pivots (rear hubs), which
		# must stay straight.
		if not node is MeshInstance3D and not str(node.name).begins_with("SteeringWheel") and not str(node.name).begins_with("SteerRear"):
			if not node.has_meta("rest"): node.set_meta("rest", node.transform)
			steer_pivots.append(node)
	if steering_pivot != null and not steer_pivots.has(steering_pivot): steer_pivots.append(steering_pivot)
	steering_wheel = bicycle.find_child("SteeringWheel", true, false) as Node3D
	if steering_wheel != null and not steering_wheel.has_meta("rest"): steering_wheel.set_meta("rest", steering_wheel.transform)
	# Driver's eyes for the in-car first-person view: behind and above the steering wheel.
	car_eye = PlayerAvatar.relative(bicycle, steering_wheel).origin + Vector3(0, 0.34, 0.55) if steering_wheel != null else Vector3.ZERO
	# Rider markers for two-wheelers (the body is hidden inside cars).
	bike_markers = PlayerAvatar.bike_markers(bicycle, asset) if asset in ["bicycle", "scooter"] and not ShopCatalog.is_car(session.active_vehicle) else {}
	crank_angle = 0.0
	steer_angle = 0.0
	lean = 0.0
	refresh_equipment()
	apply_vehicle_camera()

func refresh_equipment() -> void:
	if is_instance_valid(equipment): equipment.queue_free()
	equipment = Node3D.new()
	bicycle.add_child(equipment)
	# The delivery bag (or the plain courier backpack) is worn on the back: seen on the
	# character in third person (WornBackpack), swung round in first person (BagRig).
	if avatar != null and avatar.backpack != null:
		avatar.backpack.refresh("delivery_bag" if session.owns("delivery_bag") else ("backpack" if session.owns("backpack") else ""))
	if session.owns("helmet"):
		var helmet := CityAssets.create("helmet", 60)
		helmet.position = Vector3(0, 1.05, 0.32)
		equipment.add_child(helmet)
	headlight = SpotLight3D.new()
	headlight.position = Vector3(0, 0.9, -2.7 if ShopCatalog.is_car(session.active_vehicle) else -0.7)
	headlight.spot_range = 22
	headlight.spot_angle = 38
	headlight.light_color = Color("fff3da")
	headlight.shadow_enabled = false
	equipment.add_child(headlight)

func apply_vehicle_camera() -> void:
	if camera == null or body_collision == null: return
	if is_instance_valid(parked_body): parked_body.collision_layer=0 if mounted else 1
	if mounted and ShopCatalog.is_car(session.active_vehicle):
		camera.position = car_view_position(0.0)
		camera.rotation = Vector3(-0.05 if car_first_person() else -0.17, 0, 0)
		car_camera_yaw = 0.0
		car_steer_input = 0.0
		car_yaw_rate = 0.0
		var bounds := BoxShape3D.new()
		bounds.size = vehicle_bounds()
		body_collision.shape = bounds
		body_collision.position.y = bounds.size.y / 2 + vehicle_collision_lift()
	else:
		# Riding eye height: a seated cyclist leaning forward sees from about 1.5 m, lower than walking.
		eye_height = 1.5 if mounted else 1.65
		camera.position = Vector3(0, eye_height, 0)
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.3
		capsule.height = 1.8
		body_collision.shape = capsule
		body_collision.position.y = 0.9

func has_vehicle() -> bool:
	return session != null and session.active_vehicle != ""

func toggle_bicycle() -> String:
	if not mounted and not has_vehicle():
		return "You don't have a bicycle yet. Save up and buy one at Cedar Cycles."
	if mounted:
		if absf(riding_speed) > 0.5:
			return "Brake to a stop before dismounting."
		for side in [-1, 1]:
			var offset := global_basis.x * float(side) * (1.8 if ShopCatalog.is_car(session.active_vehicle) else 1.0)
			if not test_move(global_transform, offset):
				if avatar: avatar.begin_dismount()
				mounted = false
				rotation.y += camera.rotation.y
				camera.rotation.y = 0
				camera.rotation.z = 0
				lean = 0.0
				stand_lean = 0.0
				steer_angle = 0.0
				bicycle.rotation = Vector3(0, bicycle.rotation.y, 0)
				apply_steering_visuals(0.0)
				if bicycle.has_method("update_driving_visuals"): bicycle.update_driving_visuals(0.0, 0.0, false)
				velocity = Vector3.ZERO
				position += offset
				apply_vehicle_camera()
				return "Vehicle parked." if ShopCatalog.is_car(session.active_vehicle) else "Bicycle parked."
		return "Both sides are blocked. Move to an open space."
	if position.distance_to(bicycle.position) > 2.5:
		return "Move within 2m of your bicycle."
	var travel := bicycle.position - position
	travel.y = 0
	parked_body.collision_layer=0
	if test_move(global_transform, travel):
		parked_body.collision_layer=1
		return "The bicycle is blocked. Approach from an open side."
	if ShopCatalog.is_car(session.active_vehicle):
		var query := PhysicsShapeQueryParameters3D.new()
		var bounds := BoxShape3D.new()
		bounds.size=vehicle_bounds()
		query.shape=bounds
		query.transform=Transform3D(Basis(Vector3.UP,bicycle.rotation.y),bicycle.position+Vector3(0,bounds.size.y*.5+vehicle_collision_lift(),0))
		query.exclude=[get_rid(),parked_body.get_rid()]
		query.collision_mask=1|4
		if not get_world_3d().direct_space_state.intersect_shape(query,1).is_empty():
			parked_body.collision_layer=1
			return "The vehicle needs more clearance before mounting."
	if avatar: avatar.begin_mount()
	var view_yaw := global_rotation.y + camera.rotation.y
	position += travel
	rotation.y = bicycle.rotation.y
	# Third person: keep looking the same way while the body swings onto the bike.
	camera.rotation.y = clampf(angle_difference(rotation.y, view_yaw), -1.1, 1.1) if third_person and not ShopCatalog.is_car(session.active_vehicle) else 0.0
	velocity = Vector3.ZERO
	mounted = true
	stopped_time = 0.0
	riding_speed = 0
	apply_vehicle_camera()
	if ShopCatalog.is_car(session.active_vehicle):
		return "Driving · W accelerate · S reverse · A/D steer · mouse look · Space brake · E get out"
	return "Mounted · W pedal · A/D or mouse steer · Space brake · Q bell · E dismount"

func _ready() -> void:
	collision_mask = 1 | 4 | 16   # 16: traffic-circle islands (ignored by AI traffic rays)
	var shape := CollisionShape3D.new()
	body_collision = shape
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.3
	capsule.height = 1.8
	shape.shape = capsule
	shape.position.y = 0.9
	add_child(shape)
	camera = Camera3D.new()
	camera.position.y = 1.65
	camera.fov = 78
	add_child(camera)
	camera.make_current()
	floor_snap_length = 0.3
	hold_socket = Node3D.new()
	hold_socket.name = "HoldSocket"
	camera.add_child(hold_socket)
	view = PlayerCameraRig.new()
	add_child(view)
	view.setup(self)
	avatar = PlayerAvatar.new()
	add_child(avatar)
	avatar.setup(self)
	view.snap()

## Settings: view mode and third-person distance (GameSettings.apply).
func apply_view_settings(third: bool, distance: float) -> void:
	var changed := third != third_person
	third_person = third
	if view != null:
		view.target_distance = clampf(distance, PlayerCameraRig.MIN_DISTANCE, PlayerCameraRig.MAX_DISTANCE)
	if changed: clamp_pitch()
	apply_vehicle_camera()

## V: first <-> third person (remembered in user://settings.cfg).
func toggle_view() -> void:
	third_person = not third_person
	clamp_pitch()
	GameSettings.set_value("third_person", third_person)
	GameSettings.save_settings()
	if mounted and ShopCatalog.is_car(session.active_vehicle): apply_vehicle_camera()

func clamp_pitch() -> void:
	if camera == null: return
	var limits := pitch_limits()
	camera.rotation.x = clampf(camera.rotation.x, limits.x, limits.y)

func pitch_limits() -> Vector2:
	if mounted and session != null and ShopCatalog.is_car(session.active_vehicle): return Vector2(-0.7, 0.3)
	if third_person: return Vector2(PlayerCameraRig.PITCH_MIN, PlayerCameraRig.PITCH_MAX)
	return Vector2(-1.3, 1.3)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		look(event.relative)
	elif InputMap.has_action("camera_view") and event.is_action_pressed("camera_view"):
		if not busy: toggle_view()
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.pressed and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and third_person and view != null:
		var button := (event as InputEventMouseButton).button_index
		if button == MOUSE_BUTTON_WHEEL_UP or button == MOUSE_BUTTON_WHEEL_DOWN:
			view.zoom(-1.0 if button == MOUSE_BUTTON_WHEEL_UP else 1.0)
			get_viewport().set_input_as_handled()

func look(relative: Vector2) -> void:
	_mouse_still = 0.0
	if mounted and ShopCatalog.is_car(session.active_vehicle):
		# In a car the mouse only looks around; the view drifts back behind the car.
		car_camera_yaw = clampf(car_camera_yaw - relative.x * sensitivity, -2.6, 2.6)
		car_look_timer = 1.2
		camera.rotation.x = clampf(camera.rotation.x - relative.y * sensitivity, -0.7, 0.3)
		return
	if mounted:
		camera.rotation.y = clampf(camera.rotation.y - relative.x * sensitivity, -1.1, 1.1)
	else:
		rotate_y(-relative.x * sensitivity)
	var limits := pitch_limits()
	camera.rotation.x = clampf(camera.rotation.x - relative.y * sensitivity, limits.x, limits.y)

## True once the mouse has rested a moment (turn-in-place waits for the view to settle).
func holding_view_still() -> bool:
	return _mouse_still > 0.15

## The eyes: where the interaction ray starts in both views (2 m reach from the character).
func eye_position() -> Vector3:
	return global_transform * Vector3(0, eye_height, 0)

## Which way the body faces (the avatar turns towards travel in third person).
func body_forward() -> Vector3:
	if avatar != null and avatar.ready_ok and not mounted:
		return Vector3(-sin(avatar.facing), 0, -cos(avatar.facing))
	var f := -global_basis.z
	f.y = 0.0
	return f.normalized()

func body_yaw() -> float:
	return avatar.facing if avatar != null and avatar.ready_ok and not mounted else global_rotation.y

## Foot contacts since the last call (world positions; CityAudio plays the footsteps).
func take_footsteps() -> Array[Vector3]:
	var steps: Array[Vector3] = []
	if avatar == null or not avatar.ready_ok: return steps
	steps = avatar.footsteps.duplicate()
	avatar.footsteps.clear()
	return steps

## The package node in the hands (child of hold_socket), if any.
func held_package() -> Node3D:
	if hold_socket == null: return null
	for child in hold_socket.get_children():
		if child is Node3D and (child as Node3D).visible: return child
	return null

func car_first_person() -> bool:
	return not third_person and car_eye != Vector3.ZERO

## Car camera: chase offset swung by the look yaw, or the driver's eyes.
func car_view_position(yaw: float) -> Vector3:
	if car_first_person(): return car_eye
	return CAR_CAMERA_OFFSET.rotated(Vector3.UP, yaw)

func _physics_process(delta: float) -> void:
	if session == null:
		return
	if is_instance_valid(headlight):
		headlight.light_energy = 3.0 if (session.owns("lights") or session.active_vehicle=="scooter" or ShopCatalog.is_car(session.active_vehicle)) and (session.hour() < 7 or session.hour() > 18) and not bicycle.get_meta("has_vehicle_lights",false) else 0.0
	if mounted:
		var pedal := Input.get_axis("move_back", "move_forward")
		var brake := Input.is_action_pressed("jump")
		var powered := session.active_vehicle=="scooter" or ShopCatalog.is_car(session.active_vehicle)
		var acceleration := 3.2 if powered else (1.2 if session.energy < 20 else 2.5)
		var top_speed := ShopCatalog.speed(session.active_vehicle)
		if pedal < 0 and powered: top_speed = 3.0
		riding_speed = move_toward(riding_speed, 0.0 if brake else pedal * top_speed, (10.0 if brake else acceleration) * delta)
		steer(delta)
		var forward := -global_basis.z * riding_speed
		velocity.x = forward.x
		velocity.z = forward.z
		velocity.y -= 20 * delta
		move_and_slide()
		if is_on_wall(): riding_speed = 0.0
		bicycle.position = position
		# Stopped with a foot down, the bike leans a little onto that (left) foot.
		stand_lean = lerpf(stand_lean, 0.09 * avatar.foot_down if avatar != null and avatar.ready_ok else 0.0, minf(delta * 5.0, 1.0))
		bicycle.rotation = Vector3(0, rotation.y, lean + stand_lean)
		if bicycle.has_method("update_driving_visuals"):
			bicycle.update_driving_visuals(get_position_delta().dot(-global_basis.z), steer_angle, brake)
		else:
			var radius := float(bicycle.get_meta("wheel_radius", 0.35))   # per-model (Ace 11: 0.298 m)
			for wheel in wheels:
				wheel.rotate_x(-get_position_delta().length() / radius * signf(riding_speed))
			drive_crank(delta, pedal, radius)
		var fatigue := (0.0 if powered else absf(riding_speed) * 0.15) * (0.85 if session.owns("gloves") else 1.0)
		session.energy = clampf(session.energy + (2.0 if absf(riding_speed) < 0.1 else -fatigue) * delta, 0, 100)
		return
	walk(delta)

## On foot: camera-relative WASD with acceleration / deceleration curves; Ctrl walks, Shift
## sprints. In third person the body must turn before it runs flat out (no sideways skating).
## Jumps start from the floor or within COYOTE s of leaving it; a press just before landing is
## kept for JUMP_BUFFER s; hard landings cost a moment of speed.
func walk(delta: float) -> void:
	_mouse_still += delta
	var movement := Input.get_vector("move_left", "move_right", "move_forward", "move_back") if not busy else Vector2.ZERO
	var direction := transform.basis * Vector3(movement.x, 0, movement.y)
	var sprinting := Input.is_action_pressed("sprint") and session.energy > 0.0 and movement.length() > 0.0
	var walking := InputMap.has_action("walk") and Input.is_action_pressed("walk")
	var speed := WALK_SPEED if walking else (SPRINT_SPEED if sprinting else RUN_SPEED)
	if not third_person and movement.y > 0.5: speed = minf(speed, BACK_SPEED)
	if third_person and avatar != null and avatar.ready_ok and direction.length() > 0.1:
		var move_yaw := atan2(-direction.x, -direction.z)
		var misalign := absf(angle_difference(avatar.facing, move_yaw))
		speed *= lerpf(1.0, 0.4, smoothstep(deg_to_rad(50.0), deg_to_rad(150.0), misalign))
	if land_recovery > 0.0:
		land_recovery -= delta
		speed *= 0.65
	var on_floor := is_on_floor()
	var h := Vector2(velocity.x, velocity.z)
	var want := Vector2(direction.x, direction.z) * speed
	var rate := (ACCEL if want.length() > h.length() + 0.01 else DECEL) if on_floor else AIR_ACCEL
	h = h.move_toward(want, rate * delta)
	velocity.x = h.x
	velocity.z = h.y
	coyote_time = COYOTE if on_floor else maxf(0.0, coyote_time - delta)
	jump_buffer = JUMP_BUFFER if Input.is_action_just_pressed("jump") and not busy else maxf(0.0, jump_buffer - delta)
	if not on_floor:
		velocity.y -= GRAVITY * delta
	if jump_buffer > 0.0 and coyote_time > 0.0 and velocity.y <= 0.5:
		velocity.y = JUMP_SPEED
		jump_buffer = 0.0
		coyote_time = 0.0
		if avatar: avatar.jumped()
	var falling := -velocity.y
	move_and_slide()
	if is_on_floor() and not _was_on_floor:
		last_fall_speed = falling
		if falling > 6.5: land_recovery = 0.25
	_was_on_floor = is_on_floor()
	session.energy = clampf(session.energy + ((-4.8 if session.owns("backpack") else -6.0) if sprinting else 2.0) * delta, 0.0, 100.0)

## Bicycle drivetrain: the crank turns with the rear wheel / gear ratio while pedalling and
## freewheels when coasting (the rider then backpedals to level pedals); the pedal platforms
## stay level.
func drive_crank(delta: float, pedal: float, radius: float) -> void:
	pedalling = pedal > 0.1 and riding_speed > 0.15
	stopped_time = stopped_time + delta if absf(riding_speed) < 0.15 and not pedalling else 0.0
	if bike_markers.is_empty() or bike_markers.get("footboard", false):
		pedalling = false
		return
	var travelled := get_position_delta().dot(-global_basis.z)
	if pedalling:
		crank_angle += maxf(travelled, 0.0) / radius / GEAR_RATIO
		coast_time = 0.0
	else:
		coast_time += delta
		if coast_time > 0.35:
			# Pedals level (crank angle 0 / PI) by turning backwards a little, never forwards.
			var level := floorf(crank_angle / PI + 0.0001) * PI
			if crank_angle - level < 1.3: crank_angle = move_toward(crank_angle, level, 2.2 * delta)
	var crank := bike_markers.get("Crank") as Node3D
	if is_instance_valid(crank):
		crank.rotation.x = -crank_angle
		for key in ["PedalL", "PedalR"]:
			var pedal_node := bike_markers.get(key) as Node3D
			if is_instance_valid(pedal_node): pedal_node.rotation.x = crank_angle

## Kinematic steering for bicycles, scooters and cars.
## A/D turn the handlebars; the mouse steers too: looking left or right makes the bike
## gradually turn towards the view while the camera re-centres. Yaw follows the bicycle model
## yaw_rate = v * tan(steer) / wheelbase, with less steering lock at speed.
func steer(delta: float) -> void:
	var car := ShopCatalog.is_car(session.active_vehicle)
	if car:
		steer_car(delta)
		return
	var speed := absf(riding_speed)
	# Full lock at walking pace, about 19 degrees at 16 km/h, 8 degrees at top speed.
	var lock := deg_to_rad(lerpf(35.0, 8.0, clampf((speed - 1.0) / 6.0, 0.0, 1.0)))
	if car:
		# Cars: gentler lock that eases off smoothly with speed (24 deg parking, ~6 deg at 40 km/h).
		lock = deg_to_rad(lerpf(24.0, 6.0, clampf(speed / 11.0, 0.0, 1.0)))
	var keys := -Input.get_axis("move_left", "move_right")
	var look_assist := clampf(camera.rotation.y * (0.6 if car else 1.4), -1.0, 1.0) if absf(camera.rotation.y) > 0.04 else 0.0
	var target_steer := clampf(keys + (look_assist if keys == 0.0 else 0.0), -1.0, 1.0) * lock
	if car:
		# Smooth wheel: eases towards the target (no snapping), returns to centre a bit faster.
		var rate := 2.2 if absf(target_steer) > absf(steer_angle) else 3.5
		steer_angle = lerpf(steer_angle, target_steer, 1.0 - exp(-rate * delta))
	else:
		steer_angle = move_toward(steer_angle, target_steer, 4.5 * delta)
	var wheelbase := CAR_WHEELBASE if car else BIKE_WHEELBASE
	if is_instance_valid(bicycle): wheelbase = float(bicycle.get_meta("wheelbase", wheelbase))
	var yaw_rate := riding_speed * tan(steer_angle) / wheelbase
	if speed < 0.4 and not car:
		# Walking pace: let the rider shuffle the bike round on the spot.
		yaw_rate += keys * 0.9 * (1.0 - speed / 0.4)
	var turned := yaw_rate * delta
	rotate_y(turned)
	# Keep the view pointing the same way in the world while the bike swings under it.
	camera.rotation.y = move_toward(camera.rotation.y, 0.0, absf(turned)) if look_assist != 0.0 else camera.rotation.y
	apply_steering_visuals(steer_angle)
	# Two-wheelers lean into the turn: tan(lean) = v * yaw_rate / g.
	var target_lean := 0.0 if car else clampf(atan(riding_speed * yaw_rate / 9.81), -0.45, 0.45)
	lean = lerpf(lean, target_lean, minf(delta * 6.0, 1.0))
	camera.rotation.z = lean * (0.15 if third_person else 0.35)

## Smooth car handling. A/D build a steering input that eases in and out; the car's turn rate
## follows that input scaled by speed (sharp enough to park, calm at speed, never tighter than
## CAR_MIN_RADIUS) and approaches it with a little inertia, so turns flow in and out instead of
## snapping. The wheels show the steering angle that turn rate needs; the camera trails the turn.
func steer_car(delta: float) -> void:
	var keys := -Input.get_axis("move_left", "move_right")
	var rate := CAR_STEER_IN if absf(keys) > absf(car_steer_input) and signf(keys) == signf(car_steer_input) or car_steer_input == 0.0 else CAR_STEER_OUT
	if keys != 0.0 and signf(keys) != signf(car_steer_input) and car_steer_input != 0.0: rate = CAR_STEER_OUT
	car_steer_input = move_toward(car_steer_input, keys, rate * delta)
	# Ease-in curve: small taps make gentle corrections, full input gives the full turn.
	var shaped := signf(car_steer_input) * pow(absf(car_steer_input), 1.35)
	var speed := absf(riding_speed)
	var peak := CAR_MAX_YAW * lerpf(1.0, 0.62, clampf((speed - 5.0) / 8.0, 0.0, 1.0))
	var max_yaw := minf(peak, speed / CAR_MIN_RADIUS)
	var target := shaped * max_yaw * signf(riding_speed) if speed > 0.05 else 0.0
	car_yaw_rate = lerpf(car_yaw_rate, target, 1.0 - exp(-CAR_YAW_RESPONSE * delta))
	var turned := car_yaw_rate * delta
	rotate_y(turned)
	var wheelbase := float(bicycle.get_meta("wheelbase", CAR_WHEELBASE)) if is_instance_valid(bicycle) else CAR_WHEELBASE
	var wheel_target := atan(car_yaw_rate * wheelbase / maxf(speed, 1.0)) * signf(riding_speed if riding_speed != 0.0 else 1.0)
	if speed < 0.3: wheel_target = shaped * deg_to_rad(30.0)   # standing still: wheels still follow A/D
	steer_angle = lerpf(steer_angle, clampf(wheel_target, -0.6, 0.6), 1.0 - exp(-10.0 * delta))
	apply_steering_visuals(steer_angle)
	lean = 0.0
	# Chase camera: the car turns under the camera, which then swings round behind it.
	car_camera_yaw -= turned
	car_look_timer = maxf(0.0, car_look_timer - delta)
	if car_look_timer == 0.0:
		car_camera_yaw = lerpf(car_camera_yaw, 0.0, 1.0 - exp(-CAR_CAMERA_LAG * delta))
	car_camera_yaw = clampf(car_camera_yaw, -2.6, 2.6)
	camera.position = car_view_position(car_camera_yaw)
	camera.rotation.y = car_camera_yaw
	camera.rotation.z = 0.0

## Fork / front wheels yaw by the steer angle; the steering wheel turns ~14x (a real rack
## ratio), capped at a lock-and-a-half.
func apply_steering_visuals(angle: float) -> void:
	for pivot in steer_pivots:
		if not is_instance_valid(pivot): continue
		var rest: Transform3D = pivot.get_meta("rest")
		pivot.transform = rest * Transform3D(Basis(Vector3.UP, angle), Vector3.ZERO)
	if is_instance_valid(steering_wheel):
		var rest: Transform3D = steering_wheel.get_meta("rest")
		steering_wheel.transform = rest * Transform3D(Basis(Vector3.BACK, clampf(-angle * 14.0, -2.6, 2.6)), Vector3.ZERO)

func vehicle_bounds() -> Vector3:
	if is_instance_valid(bicycle) and bicycle.has_meta("collision_size"):
		return bicycle.get_meta("collision_size")
	return CityAssets.CAR_SIZES[CityAssets.CAR_TYPES.find(session.active_vehicle)]

func vehicle_collision_lift() -> float:
	return float(bicycle.get_meta("collision_lift", 0.06)) if is_instance_valid(bicycle) else 0.06

## What E would act on: a 2 m ray from the character's eyes along the view (the crosshair). In
## third person the HUD crosshair is drawn where this ray points (PlayerCameraRig.reticle).
func target() -> Dictionary:
	var origin := eye_position()
	var query := PhysicsRayQueryParameters3D.create(origin, origin - camera.global_basis.z * 2.0, 1)
	query.exclude = [get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	# Packages sit inside the pickup shelf's interaction volume: look through the shelf to them.
	if not hit.is_empty() and not str(hit.collider.get_meta("interaction", "")) in ["package", ""] and str(hit.collider.get_meta("interaction", "")).begins_with("pickup"):
		var skip: Array[RID] = [get_rid(), hit.rid]
		for attempt in range(4):
			query.exclude = skip
			var behind := get_world_3d().direct_space_state.intersect_ray(query)
			if behind.is_empty(): break
			if behind.collider.get_meta("interaction", "") == "package":
				hit = behind
				break
			skip.append(behind.rid)
	if not hit.is_empty() and hit.collider.has_meta("interaction"):
		return {"id": hit.collider.get_meta("interaction"), "distance": origin.distance_to(hit.position), "node": hit.collider}
	return {}

