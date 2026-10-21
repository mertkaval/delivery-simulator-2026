class_name ShopLife
extends Node3D
## Customers browsing the four neighbourhood shops (ShopCatalog.LOCATIONS; the clerk behind the
## counter is placed by CedarNeighborhood.build_store). Each shop has one customer who comes in
## through the door, walks between the displays, stops to look at them (Idle_Look / Idle),
## sometimes checks the phone, and leaves for a while before the next visit.
##
## Store-local layout (store GLB floor at y 0.10, door at z +5, displays on the back half):
## the counter area around (4, *, 1) (kiosk) and the back-right corner x 3..7, z -5..-2
## (online-order pickup shelf) are kept clear: every browsing spot is at x <= 1.6.
const FLOOR := 0.1
const SPOTS := {
	"equipment": [[Vector3(-5.0, 0, -3.1), PI * 0.0], [Vector3(-2.0, 0, -3.1), 0.0], [Vector3(-3.5, 0, -1.0), 0.6]],
	"bikes": [[Vector3(-4.0, 0, -1.4), 0.0], [Vector3(-1.2, 0, -1.4), 0.0], [Vector3(0.6, 0, -0.6), 0.9]],
	"cars": [[Vector3(-3.05, 0, 1.6), 0.25], [Vector3(0.05, 0, 1.6), -0.25], [Vector3(-1.5, 0, 2.6), 0.0]],
	"scooters": [[Vector3(-4.0, 0, -1.6), 0.0], [Vector3(-1.2, 0, -1.6), 0.0], [Vector3(-2.6, 0, 0.4), 0.3]],
}
const DOOR_IN := Vector3(-0.5, 0, 3.6)
const DOOR_OUT := Vector3(-0.5, 0, 6.6)
const SPEED := 1.0
var customers: Array[Dictionary] = []

func _ready() -> void:
	var n := 0
	for id in ShopCatalog.LOCATIONS:
		if not SPOTS.has(id): continue
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		var person := LivingAssets.humanoid(500 + n * 3)
		person.max_distance = 45.0
		add_child(person)
		var c := {"person": person, "origin": at, "spots": SPOTS[id], "state": "LOOK", "timer": 3.0 + n * 4.0,
			"path": PackedVector3Array(), "i": 0, "visits": 0, "velocity": Vector3.ZERO, "yaw": 0.0, "seed": n}
		var first: Array = SPOTS[id][n % SPOTS[id].size()]
		person.position = at + first[0] + Vector3(0, FLOOR, 0)
		person.rotation.y = first[1]
		c.yaw = first[1]
		person.purpose_pose = "Look"
		customers.append(c)
		n += 1

func _process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	for c in customers:
		var person: LivingCitizen = c.person
		if camera != null and camera.global_position.distance_to(c.origin) > 60.0: continue
		c.timer -= delta
		match c.state:
			"LOOK":
				turn(person, c.yaw, delta)
				brake(c, delta)
				if c.timer <= 0.0:
					c.visits += 1
					var spots: Array = c.spots
					if c.visits % 4 == 3:
						# Leave the shop for a while.
						c.path = PackedVector3Array([person.position, c.origin + DOOR_IN + Vector3(0, FLOOR, 0), c.origin + DOOR_OUT + Vector3(0, 0.05, 0)])
						c.state = "LEAVE"
					else:
						var target: Array = spots[(c.visits + int(c.seed)) % spots.size()]
						c.path = PackedVector3Array([person.position, c.origin + target[0] + Vector3(0, FLOOR, 0)])
						c.yaw = target[1]
						c.state = "WALK"
					c.i = 1
					person.purpose_pose = ""
			"WALK", "LEAVE", "ENTER":
				if follow(c, delta):
					if c.state == "LEAVE":
						c.state = "AWAY"
						c.timer = 20.0 + 25.0 * LivingAssets.noise(int(c.seed), int(c.visits))
						person.visible = false
					else:
						c.state = "LOOK"
						c.timer = 5.0 + 7.0 * LivingAssets.noise(int(c.seed), int(c.visits) + 9)
						person.purpose_pose = "Look" if c.visits % 3 != 1 else ("Phone" if c.visits % 2 == 0 else "Idle")
			"AWAY":
				if c.timer <= 0.0:
					person.visible = true
					var spots: Array = c.spots
					var target: Array = spots[int(c.visits) % spots.size()]
					person.position = c.origin + DOOR_OUT + Vector3(0, 0.05, 0)
					c.path = PackedVector3Array([person.position, c.origin + DOOR_IN + Vector3(0, FLOOR, 0), c.origin + target[0] + Vector3(0, FLOOR, 0)])
					c.yaw = target[1]
					c.i = 1
					c.state = "ENTER"

func brake(c: Dictionary, delta: float) -> void:
	c.velocity = (c.velocity as Vector3).move_toward(Vector3.ZERO, 3.0 * delta)
	(c.person as LivingCitizen).position += c.velocity * delta
	(c.person as LivingCitizen).ground_speed = (c.velocity as Vector3).length()

func turn(person: Node3D, yaw: float, delta: float) -> void:
	person.rotation.y += clampf(wrapf(yaw - person.rotation.y, -PI, PI) * minf(1.0, delta * 5.0), -2.5 * delta, 2.5 * delta)

func follow(c: Dictionary, delta: float) -> bool:
	var person: LivingCitizen = c.person
	var path: PackedVector3Array = c.path
	if int(c.i) >= path.size(): return true
	var goal := path[c.i]
	var to := Vector3(goal.x - person.position.x, 0, goal.z - person.position.z)
	var last: bool = int(c.i) == path.size() - 1
	if to.length() < (0.12 if last else 0.4):
		c.i = int(c.i) + 1
		if int(c.i) >= path.size():
			c.velocity = Vector3.ZERO
			person.ground_speed = 0.0
			return true
		goal = path[c.i]
		to = Vector3(goal.x - person.position.x, 0, goal.z - person.position.z)
	var want := to.normalized() * (minf(SPEED, to.length() * 2.0 + 0.25) if last else SPEED)
	c.velocity = (c.velocity as Vector3).move_toward(want, 2.0 * delta)
	person.position += c.velocity * delta
	person.position.y = lerpf(person.position.y, goal.y, minf(1.0, delta * 4.0))
	var v: Vector3 = c.velocity
	if v.length() > 0.08: turn(person, atan2(-v.x, -v.z), delta * 1.3)
	person.ground_speed = v.length()
	return false
