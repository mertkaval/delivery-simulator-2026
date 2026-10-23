class_name AnimalLife
extends Node3D
## Animals living in the city, built from the Blender part rigs (build_animals.py) and animated
## procedurally: dogs walked on leads by their owners, cats lounging in front yards (they bolt
## when the courier comes close), pigeon flocks pecking on plazas and park paths that burst
## into the air when disturbed, crows hopping on lawns and cawing, gulls circling overhead.

const DOG_COATS := ["7a5232", "d8c3a0", "2b2622", "c98b4a", "efe9df", "5b4636"]
const CAT_COATS := ["2a2725", "d0873e", "8d8d8d", "efe9df", "6b5444"]
const DOG_ROUTES := [
	[Vector3(7.9, 0.08, -300), Vector3(7.9, 0.08, -372)],
	[Vector3(-7.9, 0.08, -420), Vector3(-7.9, 0.08, -500)],
	[Vector3(-7.9, 0.08, -60), Vector3(-7.9, 0.08, -150)],
	[Vector3(7.9, 0.08, -560), Vector3(7.9, 0.08, -640)],
]

var kit: Kit
var dogs: Array[Dictionary] = []
var cats: Array[Dictionary] = []
var birds: Array[Dictionary] = []
var flocks: Array[Dictionary] = []
var gulls: Array[Dictionary] = []
var audio: CityAudio
var time := 0.0
static var materials := {}

class Kit extends HouseInstancer:
	func _ready() -> void: pass

func _ready() -> void:
	kit = Kit.new()
	add_child(kit)
	for i in range(DOG_ROUTES.size()): add_dog_walker(i, DOG_ROUTES[i])
	# Park loops for two more walkers.
	for i in range(2):
		var c := Vector3(44.0 if i == 0 else -44.0, 0.08, -470.0 if i == 0 else -330.0)
		add_dog_walker(4 + i, [c + Vector3(-7, 0, 12), c + Vector3(-7, 0, -12), c + Vector3(7, 0, -12), c + Vector3(7, 0, 12)])
	var lots := ResidentialLayout.lots()
	for i in range(9):
		var lot: Dictionary = lots[(i * 23 + 7) % lots.size()]
		var door := ResidentialLayout.door_point(lot)
		var facing: Vector3 = lot.facing
		# On the lawn beside the front walk, clear of the steps.
		var side := facing.cross(Vector3.UP) * (1.0 if i % 2 == 0 else -1.0)
		add_cat(i, Vector3(door.x, 0.0, door.z) + facing * 1.8 + side * 2.6 + Vector3(0, 0.05, 0))
	var flock_spots := [Vector3(-44, 0.06, -318), Vector3(44, 0.06, -458), Vector3(-44, 0.06, -578), Vector3(4.5, 0.08, -230),
		Vector3(-4.5, 0.08, -120), Vector3(-64, 0.06, -132)]
	for b in DowntownCatalog.buildings(4):
		if b.program == "plaza": flock_spots.append(Transform3D(Basis(Vector3.UP, b.yaw), b.root) * Vector3(3, 0.1, -11))
	for i in range(flock_spots.size()): add_flock(i, flock_spots[i], "pigeon", 7)
	for i in range(5):
		add_flock(20 + i, [Vector3(40, 0.06, -340), Vector3(-48, 0.06, -480), Vector3(48, 0.06, -600), Vector3(-60, 0.06, -150), Vector3(-30, 0.06, -20)][i], "crow", 2)
	for i in range(5):
		var centre: Vector3 = [Vector3(0, 30, -320), Vector3(250, 38, -400), Vector3(360, 34, -560), Vector3(0, 28, -560), Vector3(140, 32, -258)][i]
		add_gull(i, centre)

## Rig part with tints: coat on Fur/Feather, second tone on FurLight/FeatherTip.
func build(asset: String, parent: Node3D, coat: Color, second: Color, end: float) -> void:
	for p in kit.get_parts(asset, "near"):
		var mesh := MeshInstance3D.new()
		mesh.mesh = p.mesh
		mesh.transform = p.transform
		mesh.visibility_range_end = end
		var colour := Color.WHITE
		match str(p.name):
			"KitFur", "KitFeather": colour = coat
			"KitFurLight", "KitFeatherTip": colour = second
		mesh.material_override = tinted(p.material, colour, asset == "bird_wing")
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if asset.ends_with("_leg") or asset == "bird_wing" else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		parent.add_child(mesh)

static func tinted(base: Material, colour: Color, double_sided: bool) -> Material:
	var key := "%d_%s_%s" % [base.get_instance_id(), colour.to_html(), double_sided]
	if not materials.has(key):
		var m := base.duplicate() as StandardMaterial3D
		m.albedo_color = m.albedo_color * colour
		if double_sided: m.cull_mode = BaseMaterial3D.CULL_DISABLED
		materials[key] = m
	return materials[key]

func pivot(parent: Node3D, at: Vector3) -> Node3D:
	var n := Node3D.new()
	n.position = at
	parent.add_child(n)
	return n

func quadruped(kind: String, coat: Color, second: Color) -> Dictionary:
	var dog := kind == "dog"
	var root := Node3D.new()
	add_child(root)
	var body := pivot(root, Vector3.ZERO)
	build(kind + "_body", body, coat, second, 70.0)
	var head := pivot(root, Vector3(0, 0.66, -0.4) if dog else Vector3(0, 0.28, -0.18))
	build(kind + "_head", head, coat, second, 55.0)
	var tail := pivot(root, Vector3(0, 0.5, 0.36) if dog else Vector3(0, 0.22, 0.2))
	build(kind + "_tail", tail, coat, second, 55.0)
	var legs: Array[Node3D] = []
	var hip := Vector3(0.09, 0.42, 0.25) if dog else Vector3(0.05, 0.2, 0.13)
	for at in [Vector3(hip.x, hip.y, -hip.z), Vector3(-hip.x, hip.y, -hip.z), Vector3(hip.x, hip.y, hip.z), Vector3(-hip.x, hip.y, hip.z)]:
		var leg := pivot(root, at)
		build(kind + "_leg", leg, coat, second, 45.0)
		legs.append(leg)
	return {"root": root, "body": body, "head": head, "tail": tail, "legs": legs, "phase": randf() * TAU, "kind": kind}

## Gait: diagonal legs move together; `amount` 0 (standing) .. 1 (trot).
func gait(a: Dictionary, speed: float, delta: float) -> void:
	a.phase = float(a.phase) + delta * (2.0 + speed * 5.5)
	var swing := clampf(speed / 1.6, 0.0, 1.0) * 0.55
	var legs: Array = a.legs
	for i in range(4):
		var offset := 0.0 if i in [0, 3] else PI
		legs[i].rotation.x = sin(float(a.phase) + offset) * swing
	a.body.position.y = absf(sin(float(a.phase))) * 0.015 * clampf(speed, 0.0, 1.0)

func add_dog_walker(i: int, route: Array) -> void:
	var owner := LivingAssets.person("dog_walker", 60 + i)
	owner.max_distance = 80.0
	owner.locomotion = "WalkLeash"   # lead in the left hand, right arm swinging
	add_child(owner)
	var coat := Color(DOG_COATS[i % DOG_COATS.size()]).srgb_to_linear()
	var dog := quadruped("dog", coat, coat.lerp(Color(0.95, 0.93, 0.9), 0.5))
	dog.root.scale = Vector3.ONE * (0.85 + (i % 3) * 0.15)
	var leash := MeshInstance3D.new()
	var cord := CylinderMesh.new()
	cord.top_radius = 0.006
	cord.bottom_radius = 0.006
	cord.height = 1.0
	cord.radial_segments = 4
	cord.rings = 1
	leash.mesh = cord
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(["b8322a", "1d5f8a", "2f7a3a", "e2a72e"][i % 4])
	leash.material_override = mat
	leash.visibility_range_end = 50.0
	add_child(leash)
	owner.position = route[0]
	dog.root.position = route[0] + Vector3(0.8, 0, 0)
	dogs.append({"owner": owner, "dog": dog, "route": route, "target": 1, "leash": leash, "pause": 0.0,
		"sniff": randf_range(8.0, 20.0), "bark": 0.0, "speed": 0.0})

func add_cat(i: int, at: Vector3) -> void:
	var coat := Color(CAT_COATS[i % CAT_COATS.size()]).srgb_to_linear()
	var cat := quadruped("cat", coat, coat.lerp(Color(0.95, 0.93, 0.9), 0.6 if i % 2 == 0 else 0.15))
	cat.root.position = at
	cat.root.rotation.y = randf() * TAU
	cats.append({"cat": cat, "home": at, "goal": at, "state": "sit", "timer": randf_range(4.0, 12.0), "speed": 0.0})

func bird(kind: String, index: int) -> Dictionary:
	var root := Node3D.new()
	add_child(root)
	var coat: Color
	var tip: Color
	var size := 1.0
	var wing := 1.0
	match kind:
		"pigeon":
			coat = Color(["8e959c", "7d848c", "a3a6aa", "6f6a66"][index % 4]).srgb_to_linear()
			tip = Color("3f4348").srgb_to_linear()
		"crow":
			coat = Color("1b1c1f").srgb_to_linear()
			tip = Color("101114").srgb_to_linear()
			size = 1.35
			wing = 1.45
		_:
			coat = Color("f2f2ef").srgb_to_linear()
			tip = Color("2a2b2d").srgb_to_linear()
			size = 1.5
			wing = 2.3
	build(kind + "_body", root, coat, tip, 60.0 if kind != "gull" else 400.0)
	var wings: Array[Node3D] = []
	for sx in [1.0, -1.0]:
		var w := pivot(root, Vector3(0.06 * size * sx, 0.15 * size, -0.02 * size))
		w.scale = Vector3.ONE * wing
		# The left wing is the right one turned over (it is flat and double-sided).
		var mirror := pivot(w, Vector3.ZERO)
		if sx < 0.0: mirror.rotation.z = PI
		build("bird_wing", mirror, Color("cfd3d6").srgb_to_linear() * coat if kind == "gull" else coat, tip, 60.0 if kind != "gull" else 400.0)
		wings.append(w)
	return {"root": root, "wings": wings, "kind": kind, "phase": randf() * TAU}

func fold(b: Dictionary, amount: float) -> void:
	# Folded wings lie along the body; spread wings stretch out to the sides.
	var wings: Array = b.wings
	for i in range(2):
		var sx := 1.0 if i == 0 else -1.0
		wings[i].rotation = Vector3(0, -sx * lerpf(1.45, 0.0, amount), sx * lerpf(-0.2, 0.0, amount))

func add_flock(i: int, centre: Vector3, kind: String, count: int) -> void:
	var flock := {"centre": centre, "kind": kind, "birds": [], "state": "ground", "timer": 0.0, "home": centre}
	for k in range(count):
		var b := bird(kind, k + i)
		b.root.position = centre + Vector3(randf_range(-3, 3), 0, randf_range(-3, 3))
		b.root.rotation.y = randf() * TAU
		b["goal"] = b.root.position
		b["peck"] = randf_range(0.5, 3.0)
		b["flight"] = {}
		fold(b, 0.0)
		flock.birds.append(b)
		birds.append(b)
	flock["caw"] = randf_range(5.0, 25.0)
	flocks.append(flock)

func add_gull(i: int, centre: Vector3) -> void:
	var g := bird("gull", i)
	fold(g, 1.0)
	gulls.append({"bird": g, "centre": centre, "radius": randf_range(24.0, 42.0), "angle": randf() * TAU,
		"speed": randf_range(0.22, 0.32) * (1.0 if i % 2 == 0 else -1.0), "call": randf_range(6.0, 30.0)})

func listener() -> Vector3:
	var camera := get_viewport().get_camera_3d()
	return camera.global_position if camera != null else Vector3(0, 1.7, 20)

func sound(name: String, at: Vector3, volume: float = -6.0, pitch: float = 1.0) -> void:
	if audio == null: audio = get_tree().get_first_node_in_group("city_audio") as CityAudio
	if audio != null: audio.one_shot_at(name, at, volume, 4.0, pitch)

func _process(delta: float) -> void:
	time += delta
	var me := listener()
	for d in dogs: update_dog(d, delta, me)
	for c in cats: update_cat(c, delta, me)
	for f in flocks: update_flock(f, delta, me)
	for g in gulls: update_gull(g, delta, me)

func face(node: Node3D, direction: Vector3, delta: float, rate: float = 6.0) -> void:
	if direction.length() < 0.001: return
	var target := atan2(-direction.x, -direction.z)
	node.rotation.y = lerp_angle(node.rotation.y, target, minf(1.0, delta * rate))

func update_dog(d: Dictionary, delta: float, me: Vector3) -> void:
	var owner: Node3D = d.owner
	var dog: Dictionary = d.dog
	var route: Array = d.route
	if owner.global_position.distance_to(me) > 120.0: return
	d.sniff = float(d.sniff) - delta
	d.bark = maxf(0.0, float(d.bark) - delta)
	var walking := true
	if float(d.pause) > 0.0:
		d.pause = float(d.pause) - delta
		walking = false
	elif float(d.sniff) <= 0.0:
		d.pause = randf_range(2.5, 5.0)
		d.sniff = randf_range(12.0, 26.0)
	var goal: Vector3 = route[d.target]
	var to_goal := goal - owner.global_position
	to_goal.y = 0
	if to_goal.length() < 0.3:
		d.target = (int(d.target) + 1) % route.size()
	var speed := 1.15 if walking else 0.0
	d.speed = move_toward(float(d.speed), speed, delta * 2.0)
	if float(d.speed) > 0.01:
		owner.global_position += to_goal.normalized() * float(d.speed) * delta
		face(owner, to_goal, delta, 5.0)
	if owner is LivingCitizen: (owner as LivingCitizen).ground_speed = float(d.speed)
	# The dog trots a step ahead on the owner's left (the lead hand), sniffing the verge when they stop.
	var forward := -owner.global_basis.z
	var right := forward.cross(Vector3.UP).normalized()
	var spot: Vector3 = owner.global_position + forward * 0.9 - right * 0.75
	var root: Node3D = dog.root
	var gap := spot - root.global_position
	gap.y = 0
	var dog_speed := clampf(gap.length() * 2.2, 0.0, 2.4)
	if gap.length() > 0.05: root.global_position += gap.normalized() * dog_speed * delta
	face(root, gap if gap.length() > 0.2 else forward, delta)
	gait(dog, dog_speed, delta)
	var head: Node3D = dog.head
	head.rotation.x = lerpf(head.rotation.x, -0.55 if not walking else 0.05 * sin(time * 3.0), minf(1.0, delta * 4.0))
	dog.tail.rotation.y = sin(time * (9.0 if float(d.bark) > 0.0 else 6.0)) * 0.6
	# Bark at the courier now and then.
	if root.global_position.distance_to(me) < 6.0 and float(d.bark) <= 0.0 and randf() < delta * 0.4:
		d.bark = 18.0
		sound("dog_bark", root.global_position + Vector3(0, 0.5, 0), -4.0, randf_range(0.9, 1.1))
	# Lead from the owner's hand to the collar, with a little sag.
	var hand: Vector3 = owner.global_position + Vector3(0, 0.95, 0) - right * 0.28
	var skeleton: Skeleton3D = (owner as LivingCitizen).skeleton if owner is LivingCitizen else null
	if skeleton != null and skeleton.find_bone("LeftHand") >= 0:
		var grip := skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("LeftHand"))
		hand = grip.origin + grip.basis.y.normalized() * 0.06
	var collar: Vector3 = root.global_transform * Vector3(0, 0.53, -0.31)
	var mid := (hand + collar) * 0.5 - Vector3(0, 0.08, 0)
	var leash: MeshInstance3D = d.leash
	var span := hand.distance_to(collar)
	leash.global_transform = Transform3D(Basis.looking_at((collar - hand).normalized(), Vector3.UP) * Basis(Vector3.RIGHT, PI * 0.5), mid)
	leash.scale = Vector3(1, span, 1)

func update_cat(c: Dictionary, delta: float, me: Vector3) -> void:
	var cat: Dictionary = c.cat
	var root: Node3D = cat.root
	var distance := root.global_position.distance_to(me)
	if distance > 80.0: return
	c.timer = float(c.timer) - delta
	if distance < 4.0 and c.state != "flee":
		var away := root.global_position - me
		away.y = 0
		c.goal = Vector3(c.home) + away.normalized() * 7.0
		c.state = "flee"
	elif c.timer <= 0.0 and c.state == "sit":
		c.state = "walk"
		c.goal = Vector3(c.home) + Vector3(randf_range(-4, 4), 0, randf_range(-4, 4))
	var target := 0.0
	if c.state in ["walk", "flee"]:
		var gap: Vector3 = Vector3(c.goal) - root.global_position
		gap.y = 0
		if gap.length() < 0.2:
			if c.state == "flee": c.home = root.global_position
			c.state = "sit"
			c.timer = randf_range(6.0, 16.0)
		else:
			target = 3.6 if c.state == "flee" else 0.55
			root.global_position += gap.normalized() * float(c.speed) * delta
			face(root, gap, delta, 8.0)
	c.speed = move_toward(float(c.speed), target, delta * 6.0)
	gait(cat, float(c.speed), delta)
	var sitting: bool = c.state == "sit" and float(c.speed) < 0.05
	var legs: Array = cat.legs
	legs[2].rotation.x = lerpf(legs[2].rotation.x, -1.2 if sitting else legs[2].rotation.x, minf(1.0, delta * 5.0))
	legs[3].rotation.x = lerpf(legs[3].rotation.x, -1.2 if sitting else legs[3].rotation.x, minf(1.0, delta * 5.0))
	cat.body.rotation.x = lerpf(cat.body.rotation.x, 0.22 if sitting else 0.0, minf(1.0, delta * 5.0))
	cat.tail.rotation.y = sin(time * 1.7 + float(cat.phase)) * (0.5 if sitting else 0.25)
	cat.head.rotation.y = sin(time * 0.5 + float(cat.phase)) * 0.6 if sitting else 0.0

func update_flock(f: Dictionary, delta: float, me: Vector3) -> void:
	var centre: Vector3 = f.centre
	var distance := centre.distance_to(me)
	if distance > 90.0 and f.state == "ground": return
	var birds_list: Array = f.birds
	var spook := 5.5 if f.kind == "pigeon" else 8.0
	if f.state == "ground":
		var nearest := INF
		for b in birds_list: nearest = minf(nearest, (b.root as Node3D).global_position.distance_to(me))
		if nearest < spook:
			# Take off: everyone climbs away from the intruder, circles, and lands at home again.
			f.state = "air"
			f.timer = randf_range(7.0, 11.0)
			var away := centre - me
			away.y = 0
			for b in birds_list:
				var from: Vector3 = b.root.global_position
				var peak := from + away.normalized() * randf_range(6.0, 10.0) + Vector3(randf_range(-3, 3), randf_range(5.0, 8.0), randf_range(-3, 3))
				b.flight = {"from": from, "peak": peak, "t": 0.0, "land": Vector3(f.home) + Vector3(randf_range(-3, 3), 0, randf_range(-3, 3))}
			sound("wing_flap", centre + Vector3(0, 0.5, 0), -2.0)
			if f.kind == "crow": sound("crow_caw", centre + Vector3(0, 2, 0), -4.0)
		else:
			f.caw = float(f.caw) - delta
			if f.caw <= 0.0 and distance < 45.0:
				f.caw = randf_range(10.0, 30.0)
				sound("pigeon_coo" if f.kind == "pigeon" else "crow_caw", centre + Vector3(0, 0.3, 0), -10.0 if f.kind == "pigeon" else -6.0, randf_range(0.92, 1.08))
			for b in birds_list: ground_bird(b, centre, delta)
	else:
		f.timer = float(f.timer) - delta
		for b in birds_list: fly_bird(b, f, delta)
		if f.timer <= 0.0:
			var landed := true
			for b in birds_list:
				if not b.flight.is_empty(): landed = false
			if landed: f.state = "ground"

func ground_bird(b: Dictionary, centre: Vector3, delta: float) -> void:
	var root: Node3D = b.root
	b.peck = float(b.peck) - delta
	var gap: Vector3 = Vector3(b.goal) - root.global_position
	gap.y = 0
	if gap.length() < 0.05 and float(b.peck) <= 0.0:
		b.goal = centre + Vector3(randf_range(-3.5, 3.5), 0, randf_range(-3.5, 3.5))
		b.peck = randf_range(0.8, 3.0)
	var step := 0.0
	if gap.length() >= 0.05:
		step = 0.45 if b.kind == "pigeon" else 0.6
		root.global_position += gap.normalized() * minf(step * delta, gap.length())
		face(root, gap, delta, 10.0)
	# Head-bob walk; pecking dips the whole bird forward.
	var bob := sin(time * 12.0 + float(b.phase)) * 0.12 if step > 0.0 else 0.0
	var pecking := float(b.peck) > 0.0 and float(b.peck) < 0.5
	root.rotation.x = lerpf(root.rotation.x, -0.5 * absf(sin(time * 9.0)) if pecking else bob * 0.3, minf(1.0, delta * 10.0))
	fold(b, 0.0)

func fly_bird(b: Dictionary, f: Dictionary, delta: float) -> void:
	var root: Node3D = b.root
	if b.flight.is_empty(): return
	var flight: Dictionary = b.flight
	flight.t = float(flight.t) + delta / 7.0
	var t: float = flight.t
	var land: Vector3 = flight.land
	var from: Vector3 = flight.from
	var peak: Vector3 = flight.peak
	# Out to the peak, then a wide loop back down to a landing spot near home.
	var p: Vector3
	if t < 0.5:
		var u := t / 0.5
		p = from.lerp(peak, u) + Vector3(0, sin(u * PI) * 1.5, 0)
	else:
		var u := (t - 0.5) / 0.5
		var loop := Vector3(cos(u * PI) * 6.0, 0, sin(u * PI) * 6.0)
		p = peak.lerp(land, u) + loop * (1.0 - u) * 0.5 + Vector3(0, sin(u * PI) * 2.0, 0)
	var heading := p - root.global_position
	root.global_position = p
	face(root, heading, delta, 10.0)
	root.rotation.x = clampf(-heading.y / maxf(0.01, delta) * 0.05, -0.5, 0.5)
	var flap := sin(time * (16.0 if b.kind == "pigeon" else 11.0) + float(b.phase))
	var wings: Array = b.wings
	wings[0].rotation = Vector3(0, 0, flap * 0.9)
	wings[1].rotation = Vector3(0, 0, -flap * 0.9)
	if t >= 1.0:
		b.flight = {}
		b.goal = root.global_position
		root.rotation.x = 0.0
		fold(b, 0.0)

func update_gull(g: Dictionary, delta: float, me: Vector3) -> void:
	var b: Dictionary = g.bird
	var root: Node3D = b.root
	g.angle = float(g.angle) + float(g.speed) * delta
	var a: float = g.angle
	var centre: Vector3 = g.centre
	var p := centre + Vector3(cos(a) * float(g.radius), sin(a * 0.7) * 3.0, sin(a) * float(g.radius))
	var heading := p - root.global_position
	root.global_position = p
	face(root, heading, delta, 3.0)
	root.rotation.z = -signf(float(g.speed)) * 0.35  # banked turn
	# Mostly gliding, with a few lazy wingbeats now and then.
	var beat := sin(time * 6.0 + float(b.phase))
	var flapping := fmod(time + float(b.phase) * 3.0, 9.0) < 2.0
	var wings: Array = b.wings
	wings[0].rotation = Vector3(0, 0, (beat * 0.6 if flapping else 0.08))
	wings[1].rotation = Vector3(0, 0, -(beat * 0.6 if flapping else 0.08))
	g.call = float(g.call) - delta
	if g.call <= 0.0:
		g.call = randf_range(14.0, 40.0)
		if p.distance_to(me) < 70.0: sound("seagull_call", p, -8.0, randf_range(0.9, 1.1))
