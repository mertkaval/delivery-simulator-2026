class_name TableService
extends Node3D
## One restaurant's front of house: diners seated on the real chairs (CitySeating) and a waiter
## who takes plates from the counter, carries them on a tray (Walk_Carry), sets them down at an
## occupied table (the plates stay on the table while the diners eat), and walks back.
##
## Everything is in this node's local frame (the restaurant frame). Usage:
##   var service := TableService.new(); service.transform = frame; parent.add_child(service)
##   service.add_table(seats, plate_spots, approach, approach_yaw, path)   # path: pass -> approach
##   service.start_waiter(index, pass_spot, pass_yaw, counter_plate_spot)
const PLATE := "res://assets/props/npc/plate_food.glb"
const TEA := "res://assets/props/npc/tea_glass.glb"
const WALK_SPEED := 1.05
static var plate_scene: PackedScene
static var tea_scene: PackedScene

var tables: Array[Dictionary] = []
var waiter: LivingCitizen
var pass_spot := Vector3.ZERO
var pass_yaw := 0.0
var counter_spot := Vector3.ZERO
var state := "WAIT"
var timer := 3.0
var path: PackedVector3Array = PackedVector3Array()
var path_i := 0
var current := -1
var counter_plate: Node3D
var velocity := Vector3.ZERO
var seed := 0
var max_distance := 40.0

static func plate() -> Node3D:
	if plate_scene == null: plate_scene = load(PLATE)
	return plate_scene.instantiate()

static func tea() -> Node3D:
	if tea_scene == null: tea_scene = load(TEA)
	return tea_scene.instantiate()

## Seats diners (one per slot) and records where their plates go (local positions on the table
## top, one per slot), where the waiter stands to serve (local) and his path from the pass.
func add_table(slots: Array[Dictionary], spots: Array[Vector3], approach: Vector3, approach_yaw: float, route: PackedVector3Array, first_index: int) -> void:
	var diners: Array[LivingCitizen] = []
	for k in range(slots.size()):
		var person := CitySeating.seated_person(slots[k], first_index + k * 7)
		person.max_distance = max_distance
		add_child(person)
		CitySeating.sit(person, slots[k], ["Sit", "SitTalk", "SitPhone", "Sit"][(first_index + k) % 4])
		diners.append(person)
	var drinks: Array[Node3D] = []
	for s in spots:
		# A tea glass beside each place, there from the start.
		var glass := tea()
		glass.position = s + Vector3(0.16, 0.0, 0.0).rotated(Vector3.UP, approach_yaw)
		add_child(glass)
		drinks.append(glass)
	tables.append({"diners": diners, "spots": spots, "approach": approach, "yaw": approach_yaw, "route": route,
		"plates": [], "served": false, "timer": 6.0 + 9.0 * tables.size()})

func start_waiter(index: int, spot: Vector3, yaw: float, plate_spot: Vector3) -> void:
	seed = index
	pass_spot = spot
	pass_yaw = yaw
	counter_spot = plate_spot
	waiter = LivingAssets.humanoid(index)
	waiter.max_distance = max_distance
	waiter.locomotion = "WalkCarry"
	add_child(waiter)
	waiter.position = spot
	waiter.rotation.y = yaw
	waiter.purpose_pose = "Idle"
	waiter.carry(null)

func _process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera != null and camera.global_position.distance_to(global_position) > max_distance + 15.0: return
	for t in tables:
		if t.served:
			t.timer -= delta
			if t.timer <= 0.0:
				# Finished: plates cleared, back to talking; they order again later.
				for p: Node3D in t.plates: p.queue_free()
				t.plates = []
				t.served = false
				t.timer = 25.0 + 20.0 * LivingAssets.noise(seed, tables.find(t) + int(Time.get_ticks_msec() / 1000))
				for k in range(t.diners.size()):
					t.diners[k].purpose_pose = ["SitTalk", "Sit", "SitPhone"][k % 3]
		elif t.timer > 0.0:
			t.timer -= delta
	if waiter == null: return
	timer -= delta
	match state:
		"WAIT":
			hold(pass_yaw, delta)
			if timer <= 0.0:
				current = -1
				for i in range(tables.size()):
					if not tables[i].served and tables[i].timer <= 0.0 and current < 0: current = i
				if current < 0:
					timer = 3.0
					waiter.purpose_pose = ["Idle", "Talk", "Idle", "Phone"][int(Time.get_ticks_msec() / 4000) % 4]
					return
				# The kitchen puts the order on the counter; the waiter picks it up.
				counter_plate = plate()
				add_child(counter_plate)
				counter_plate.position = counter_spot
				waiter.tray_active = true
				timer = waiter.play_once("PickUp")
				state = "PICK"
		"PICK":
			hold(pass_yaw, delta)
			if timer <= 0.4 and counter_plate != null:
				waiter.carry(counter_plate)
				counter_plate = null
			if timer <= 0.0:
				path = tables[current].route
				path_i = 0
				waiter.purpose_pose = "Carry"
				waiter.locomotion = "WalkCarry"
				state = "GO"
		"GO", "BACK":
			if follow(delta):
				if state == "GO":
					state = "SERVE"
					timer = 0.6
				else:
					state = "WAIT"
					waiter.purpose_pose = "Idle"
					timer = 4.0 + 6.0 * LivingAssets.noise(seed, path_i + current)
		"SERVE":
			hold(tables[current].yaw, delta)
			if timer <= 0.0 and waiter.oneshot == "":
				# Lower the tray to the table: the plates go onto the places.
				timer = waiter.play_once("PickUp", true)
				state = "SET"
		"SET":
			hold(tables[current].yaw, delta)
			var t: Dictionary = tables[current]
			if timer <= 0.45 and t.plates.is_empty():
				waiter.carry(null)
				for s: Vector3 in t.spots:
					var p := plate()
					p.position = s
					p.rotation.y = LivingAssets.noise(seed, t.plates.size()) * TAU
					add_child(p)
					t.plates.append(p)
				t.served = true
				t.timer = 70.0 + 50.0 * LivingAssets.noise(seed, current + 5)
				for d: LivingCitizen in t.diners: d.purpose_pose = "SitEat"
			if timer <= 0.0:
				waiter.tray_active = false
				var back := PackedVector3Array(t.route)
				back.reverse()
				path = back
				path_i = 0
				waiter.purpose_pose = "Idle"
				waiter.locomotion = "Walk"
				state = "BACK"

func hold(yaw: float, delta: float) -> void:
	velocity = velocity.move_toward(Vector3.ZERO, 3.0 * delta)
	waiter.position += velocity * delta
	waiter.ground_speed = velocity.length()
	waiter.rotation.y += clampf(wrapf(yaw - waiter.rotation.y, -PI, PI) * minf(1.0, delta * 6.0), -3.0 * delta, 3.0 * delta)

## Walks the waiter along `path` (smooth velocity, rounded corners). True on arrival.
func follow(delta: float) -> bool:
	if path_i >= path.size(): return true
	var goal := path[path_i]
	var to := Vector3(goal.x - waiter.position.x, 0, goal.z - waiter.position.z)
	var last := path_i == path.size() - 1
	if to.length() < (0.12 if last else 0.4):
		path_i += 1
		if path_i >= path.size():
			velocity = Vector3.ZERO
			waiter.ground_speed = 0.0
			return true
		goal = path[path_i]
		to = Vector3(goal.x - waiter.position.x, 0, goal.z - waiter.position.z)
	var want := to.normalized() * minf(WALK_SPEED, to.length() * 2.0 + 0.25) if last else to.normalized() * WALK_SPEED
	velocity = velocity.move_toward(want, 2.2 * delta)
	waiter.position += velocity * delta
	waiter.position.y = goal.y
	if velocity.length() > 0.08:
		var yaw := atan2(-velocity.x, -velocity.z)
		waiter.rotation.y += clampf(wrapf(yaw - waiter.rotation.y, -PI, PI) * minf(1.0, delta * 7.0), -3.5 * delta, 3.5 * delta)
	waiter.ground_speed = velocity.length()
	return false
