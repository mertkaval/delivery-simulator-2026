class_name PlayerCameraRig
extends Node
## Third- / first-person view for CourierPlayer, using the player's one Camera3D.
##
## The camera node keeps its meaning everywhere: it is a child of the player, its rotation is the
## aim (x = pitch, y = look offset on a vehicle, z = roll) and the player's yaw is the view yaw, so
## every system that reads player.camera / player.rotation keeps working. In third person this rig
## only moves the camera *position* each frame: behind and over the right shoulder on an orbit
## around the character (SpringArm3D sweep: never through walls, props or houses), with a
## mouse-wheel zoom (MIN_DISTANCE..MAX_DISTANCE, smooth) that shrinks at once when blocked and
## eases back out. First person puts it at the eyes. While the phone or the backpack is out
## (camera children with `out == true`) it blends to first person so those rigs look as designed,
## then back. Runs while the game is paused (phone / bag screens pause the tree).

const MIN_DISTANCE := 1.6
const MAX_DISTANCE := 6.0
const SHOULDER := 0.5          ## right-shoulder offset at full arm length (m)
const RAISE := 0.26            ## camera line a little above the pivot (m)
const PIVOT_HEIGHT := 1.58     ## orbit pivot above the feet on foot (m)
const PIVOT_HEIGHT_BIKE := 1.48
const BIKE_EXTRA := 0.6        ## a little further back on the bicycle (m)
const PITCH_MIN := -1.05       ## -60 degrees
const PITCH_MAX := 0.61        ## +35 degrees
const BLEND_TIME := 0.28
const PROBE_RADIUS := 0.2

var player: CourierPlayer
var arm: SpringArm3D
var blend := 1.0               ## 1 third person, 0 first person (eased when used)
var target_distance := 3.2
var distance := 3.2
var clear := 3.2               ## free arm length (smoothed outwards, immediate inwards)
var arm_length := 3.2          ## wanted arm length this frame
var pivot := Vector3.ZERO
var _pivot_ready := false
var _arm_ticks := 0             ## physics ticks the SpringArm3D has swept since the last snap
var reticle := Vector2(640, 360)
var aim_point := Vector3.ZERO
var _save_in := -1.0

func setup(owner_player: CourierPlayer) -> void:
	player = owner_player
	name = "CameraRig"
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = 100         # after the player and the avatar have moved
	arm = SpringArm3D.new()
	arm.name = "CameraArm"
	arm.top_level = true
	var probe := SphereShape3D.new()
	probe.radius = PROBE_RADIUS
	arm.shape = probe
	arm.collision_mask = 1 | 16
	arm.margin = 0.04
	arm.spring_length = distance
	player.add_child(arm)
	arm.add_excluded_object(player.get_rid())

## The vehicle chase / in-car camera is handled by the player while driving a car.
func active() -> bool:
	return not (player.mounted and player.session != null and ShopCatalog.is_car(player.session.active_vehicle))

## Phone or backpack out in front of the camera: hold first person until it is put away.
func overridden() -> bool:
	for child in player.camera.get_children():
		if child == player.hold_socket: continue
		if child.get("out") == true: return true
	return false

func eased() -> float:
	return smoothstep(0.0, 1.0, blend)

func zoom(steps: float) -> void:
	target_distance = clampf(target_distance + steps * 0.35 * maxf(target_distance / 3.0, 0.6), MIN_DISTANCE, MAX_DISTANCE)
	_save_in = 1.0

## 0 normally; rises to 1 as a wall pushes the camera into the character's head.
func closeness() -> float:
	if eased() < 0.5: return 0.0
	return clampf(1.0 - (minf(clear, arm_length) - 0.35) / 0.55, 0.0, 1.0)

func snap() -> void:
	blend = 1.0 if player.third_person else 0.0
	distance = target_distance
	clear = distance
	_pivot_ready = false
	_arm_ticks = 0

func _physics_process(_delta: float) -> void:
	if not get_tree().paused: _arm_ticks += 1

func _process(delta: float) -> void:
	if player == null or player.camera == null: return
	if _save_in > 0.0:
		_save_in -= delta
		if _save_in <= 0.0:
			GameSettings.set_value("camera_distance", target_distance)
			GameSettings.save_settings()
	if not active():
		blend = 1.0 if player.third_person else 0.0
		_pivot_ready = false
		player.hold_socket.transform = Transform3D.IDENTITY
		return
	var want := 1.0 if player.third_person and not overridden() else 0.0
	blend = move_toward(blend, want, delta / BLEND_TIME)
	var e := eased()
	distance = lerpf(distance, target_distance, 1.0 - exp(-10.0 * delta))
	var cam := player.camera
	var eye_local := Vector3(0, player.eye_height, 0)
	place_third_person(delta)
	var tp_local := player.global_transform.affine_inverse() * (pivot + arm_dir() * minf(clear, arm_length))
	cam.position = eye_local.lerp(tp_local, e) if e > 0.0 else eye_local
	# Held package: in first person it sits at HOLD_POSE in front of the camera; in third person
	# the same socket carries it into the character's hands.
	if e > 0.0 and player.avatar != null and player.avatar.ready_ok:
		var tp_socket := player.avatar.carry_transform() * CourierPlayer.HOLD_POSE.affine_inverse()
		player.hold_socket.global_transform = cam.global_transform.interpolate_with(tp_socket, e)
	else:
		player.hold_socket.transform = Transform3D.IDENTITY
	if player.avatar != null: player.avatar.update_visibility()
	update_reticle(delta, e)
	fade_people(delta)

# --- Townspeople walking through the camera ------------------------------------------------

var _people: Array[Node3D] = []
var _people_parents: Array[Node] = []
var _people_scan := 1.5         ## first full scan shortly after start (title menu), then cheap ones
var _full_scans := 0
var _faded: Dictionary = {}     ## LivingCitizen -> current fade (0..1)
var _fade_tick := 0

## Pedestrians have no colliders, so the arm cannot dodge them: anyone the third-person camera
## is about to pass through fades out (and back in as it moves on) instead of filling the view.
## The people are found by two whole-tree scans while the title menu is up (about 20 ms each);
## afterwards only the containers they live in are re-read every few seconds.
func fade_people(delta: float) -> void:
	_people_scan -= delta
	if _people_scan <= 0.0:
		_people_scan = 6.0
		scan_people(_full_scans < 2)
	_fade_tick += 1
	var cam := player.camera.global_position
	var active := eased() > 0.01 and player.camera.current
	if _fade_tick % 4 == 0 and active:
		for person: Node3D in _people:
			if not is_instance_valid(person) or _faded.has(person): continue
			var d := person.global_position - cam
			if d.y < 0.4 and d.y > -2.1 and d.x * d.x + d.z * d.z < 1.0:
				_faded[person] = 0.0
	for person: Node3D in _faded.keys():
		if not is_instance_valid(person):
			_faded.erase(person)
			continue
		var d := person.global_position - cam
		var flat := Vector2(d.x, d.z).length()
		var want := 0.0 if not active or d.y > 0.4 or d.y < -2.1 else clampf((0.85 - flat) / 0.4, 0.0, 1.0)
		var now := move_toward(float(_faded[person]), want, delta * 6.0)
		_faded[person] = now
		for gi: GeometryInstance3D in person.find_children("*", "GeometryInstance3D", true, false):
			gi.transparency = now
		if now <= 0.0 and want <= 0.0: _faded.erase(person)

func scan_people(full: bool) -> void:
	var found: Array[Node3D] = []
	if full:
		_full_scans += 1
		_people_scan = 8.0
		_people_parents.clear()
		for n in player.get_tree().root.find_children("*", "LivingCitizen", true, false):
			found.append(n as Node3D)
			if not _people_parents.has(n.get_parent()): _people_parents.append(n.get_parent())
	else:
		for parent in _people_parents:
			if not is_instance_valid(parent): continue
			for child in parent.get_children():
				if child is LivingCitizen: found.append(child as Node3D)
	_people = found

var _dir := Vector3.BACK
func arm_dir() -> Vector3:
	return _dir

## Orbit pivot (smoothed), arm direction from the aim, and the SpringArm3D sweep.
func place_third_person(delta: float) -> void:
	var on_bike := player.mounted
	var height := PIVOT_HEIGHT_BIKE if on_bike else PIVOT_HEIGHT
	var target := player.global_position + Vector3(0, height, 0)
	if not _pivot_ready or pivot.distance_to(target) > 4.0:
		pivot = target
		_pivot_ready = true
	else:
		var h := Vector2(pivot.x, pivot.z).lerp(Vector2(target.x, target.z), 1.0 - exp(-28.0 * delta))
		pivot = Vector3(h.x, lerpf(pivot.y, target.y, 1.0 - exp(-11.0 * delta)), h.y)
	var aim := player.camera.global_basis.orthonormalized()
	var reach := distance + (BIKE_EXTRA if on_bike else 0.0)
	var offset := aim * Vector3(SHOULDER, RAISE, reach)
	arm_length = offset.length()
	_dir = offset / maxf(arm_length, 0.001)
	arm.global_transform = Transform3D(basis_towards(_dir), pivot)
	arm.spring_length = arm_length
	var hit := arm.get_hit_length() if _arm_ticks > 1 else arm_length
	hit = clampf(hit, 0.05, arm_length)
	# Pull in at once when something gets between; ease back out when it is clear.
	clear = hit if hit < clear else move_toward(clear, hit, 3.0 * delta)
	clear = minf(clear, arm_length)

## Basis whose +Z points along `dir` (SpringArm3D sweeps along its local +Z).
static func basis_towards(dir: Vector3) -> Basis:
	var z := dir.normalized()
	var x := Vector3.UP.cross(z)
	if x.length() < 0.01: x = Vector3.RIGHT
	x = x.normalized()
	return Basis(x, z.cross(x), z)

## Crosshair: in third person it marks what the interaction ray from the head points at.
func update_reticle(delta: float, e: float) -> void:
	var cam := player.camera
	var size := cam.get_viewport().get_visible_rect().size
	var centre := size * 0.5
	if e < 0.01:
		reticle = centre
		return
	var eye := player.eye_position()
	var dir := -cam.global_basis.z
	var q := PhysicsRayQueryParameters3D.create(eye, eye + dir * 30.0, 1)
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	aim_point = (hit.position as Vector3) if not hit.is_empty() else eye + dir * 30.0
	var want := centre
	if not cam.is_position_behind(aim_point): want = cam.unproject_position(aim_point)
	want = want.lerp(centre, 1.0 - e)
	reticle = reticle.lerp(want, 1.0 - exp(-30.0 * delta))
