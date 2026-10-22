class_name BusSystem
extends Node3D
## City buses on three ring lines. Each line is a closed loop of street corners; buses drive
## the right-hand lane with filleted corners, slow for anything in front of them (cars, the
## courier, other buses), pull in at every stop, kneel and open their doors, let passengers
## off and on, chime and close, then pull away. Shelters, stop flags, waiting passengers and
## the bus models come from the Blender transit kit (build_transit.py).

const KIT := "res://world/citykit/transit/%s.glb"
const LINES := [
	{"number": "1", "title": "ATATÜRK RING", "colour": "c8102e", "buses": 2,
		"corners": [Vector2(0, -258), Vector2(0, -678), Vector2(-64, -678), Vector2(-64, -258)]},
	{"number": "2", "title": "RAINLINE DOWNTOWN", "colour": "1d5f8a", "buses": 2,
		"corners": [Vector2(0, -538), Vector2(252, -538), Vector2(252, -258), Vector2(0, -258)]},
	{"number": "3", "title": "SCIENCE QUARTER", "colour": "2f7a3a", "buses": 1,
		"corners": [Vector2(144, -398), Vector2(144, -678), Vector2(468, -678), Vector2(468, -398)]},
]
const CRUISE := 8.5
const CORNER_SPEED := 4.0
const ACCEL := 1.4
const BRAKE := 2.2
const CORNER_RADIUS := 9.0
const DOOR_FRONT := -4.0 ## bus-local z of the front door centre (forward is -z)
const DOOR_MID := 0.4
const WIDTH := 2.55

var lines: Array[Dictionary] = [] ## {"path", "lengths", "total", "stops": [{"s", "shelter", "waiting"}], "colour"}
var buses: Array[Dictionary] = []
var stops: Array[Dictionary] = []
var walkers: Array[Dictionary] = [] ## passengers walking to / from a door
var pool: Array[Node3D] = []
var props: HouseInstancer
var audio: CityAudio
var night := 0.0
var probe_box := BoxShape3D.new()

func _ready() -> void:
	props = StopProps.new()
	props.name = "TransitProps"
	add_child(props)
	probe_box.size = Vector3(2.4, 1.6, 2.0)
	for spec in LINES: build_line(spec)
	props.flush()
	for li in range(lines.size()):
		var line: Dictionary = lines[li]
		for k in range(int(LINES[li].buses)):
			add_bus(li, line.total * float(k) / float(LINES[li].buses) + 20.0)

## Instancer for shelters and stop flags (keeps them in MultiMeshes with line tints).
class StopProps extends HouseInstancer:
	func _ready() -> void:
		body = StaticBody3D.new()
		body.name = "StopCollision"
		add_child(body)

static func road_half(a: Vector2, b: Vector2) -> float:
	var mid := (a + b) * 0.5
	var best := 5.0
	var best_d := INF
	var along_x := absf(b.x - a.x) > absf(b.y - a.y)
	for segment in StreetNames.segments():
		# Only streets running the same way (a junction midpoint lies on both streets).
		if (absf(segment.b.x - segment.a.x) > absf(segment.b.y - segment.a.y)) != along_x: continue
		var d := StreetNames.distance(mid, segment)
		if d < best_d:
			best_d = d
			best = segment.half
	return best

static func lane_of(half: float) -> float:
	return clampf(half * 0.33, 1.64, 2.6)

## Offset loop with filleted corners as a dense polyline (y = 0).
func build_line(spec: Dictionary) -> void:
	var corners: Array = spec.corners
	var n := corners.size()
	var offsets: Array[Dictionary] = []
	for i in range(n):
		var a: Vector2 = corners[i]
		var b: Vector2 = corners[(i + 1) % n]
		var d := (b - a).normalized()
		var right := Vector2(-d.y, d.x)  # (d.x, d.z) x up -> right-hand side
		var half := road_half(a, b)
		offsets.append({"a": a + right * lane_of(half), "b": b + right * lane_of(half), "d": d, "half": half, "right": right})
	var path := PackedVector3Array()
	for i in range(n):
		var seg: Dictionary = offsets[i]
		var next: Dictionary = offsets[(i + 1) % n]
		# Corner point: where this lane line meets the next one.
		var corner := Geometry2D.line_intersects_line(seg.a, seg.d, next.a, next.d) as Vector2
		var start := corner - Vector2(seg.d) * CORNER_RADIUS
		var end := corner + Vector2(next.d) * CORNER_RADIUS
		var prev_corner := Geometry2D.line_intersects_line(offsets[(i - 1 + n) % n].a, offsets[(i - 1 + n) % n].d, seg.a, seg.d) as Vector2
		var from := prev_corner + Vector2(seg.d) * CORNER_RADIUS
		path.append(Vector3(from.x, 0, from.y))
		path.append(Vector3(start.x, 0, start.y))
		for k in range(1, 8):
			var u := k / 8.0
			var q := start.lerp(corner, u).lerp(corner.lerp(end, u), u)
			path.append(Vector3(q.x, 0, q.y))
	var lengths := PackedFloat32Array([0.0])
	for i in range(1, path.size() + 1):
		lengths.append(lengths[-1] + path[i - 1].distance_to(path[i % path.size()]))
	var line := {"path": path, "lengths": lengths, "total": lengths[-1], "stops": [], "colour": Color(spec.colour),
		"number": spec.number, "title": spec.title}
	# Stops: two per side on long sides, one on short ones, shelters on the kerb side.
	for i in range(n):
		var seg: Dictionary = offsets[i]
		var length: float = (seg.b - seg.a).length()
		var fractions := [0.3, 0.72] if length > 300.0 else [0.5]
		for f in fractions:
			var p: Vector2 = seg.a.lerp(seg.b, f)
			p = clear_spot(p, seg)
			add_stop(line, p, seg)
	lines.append(line)

## Slide a stop along its street until the sidewalk there is free of front walks, junctions and
## the restaurant terraces.
func clear_spot(p: Vector2, seg: Dictionary) -> Vector2:
	var hood := get_parent()
	for k in range(14):
		var q: Vector2 = p + Vector2(seg.d) * (k / 2) * 6.0 * (1 if k % 2 == 0 else -1)
		var kerb: Vector2 = q + Vector2(seg.right) * (shelter_offset(seg.half) - lane_of(seg.half))
		var bad := false
		for j in StreetNames.junctions():
			if q.distance_to(j.at) < 26.0: bad = true
		if hood != null and hood.has_method("front_walk_near") and hood.front_walk_near(Vector3(kerb.x, 0, kerb.y)): bad = true
		if CityLayout.blocked(Vector3(kerb.x, 0, kerb.y), 0.6): bad = true
		if kerb.x > 68.0 and kerb.x < 122.0: bad = true  # corridor terraces and sidewalk seating
		if not bad: return q
	return p

static func shelter_offset(half: float) -> float:
	# Aziz Sancar Avenue (18 m) has its facades 3 m behind the kerb: half + 3.2 stood the shelter
	# 1 m inside the storefronts. Its shelters stand 1.95 m back from the kerb instead (back panel
	# 0.45 m off the facades; the 1.9 m placer record stays clear of the carriageway).
	if half >= 8.5: return half + 1.95
	return 9.5 if is_equal_approx(half, 6.0) else half + 3.2

func add_stop(line: Dictionary, p: Vector2, seg: Dictionary) -> void:
	var right: Vector2 = seg.right
	var d: Vector2 = seg.d
	var lane_point := p
	p = p - right * lane_of(seg.half)  # street centreline
	var kerb := p + right * shelter_offset(seg.half)
	# Shelter opens towards the road (+z towards -right).
	var basis := Basis.looking_at(Vector3(right.x, 0, right.y), Vector3.UP)
	var shelter_t := Transform3D(basis, Vector3(kerb.x, 0.12, kerb.y))
	var tint := {"accent": Color(line.colour).srgb_to_linear(), "trim": Color("f3f1ea").srgb_to_linear()}
	props.add("bus_shelter", shelter_t, tint, 160.0)
	props.box_collider(shelter_t * Vector3(0, 1.25, -0.6), Vector3(3.6, 2.5, 0.1), basis)
	props.box_collider(shelter_t * Vector3(-1.75, 1.25, -0.05), Vector3(0.15, 2.5, 1.1), basis)
	var pole_at: Vector2 = p + right * (seg.half + 0.7) + d * 5.0
	# The stop flag stands in the kerb-side furniture zone: the city's PropPlacer nudges it along
	# the kerb if a street light or sign already stands there, and records the shelter so later
	# furniture keeps clear of the boarding area.
	var placer: PropPlacer = get_parent().get("placer") if get_parent() != null and get_parent().get("placer") is PropPlacer else null
	if placer != null:
		var spot: Variant = placer.place("bus_stop_pole", Vector3(pole_at.x, 0, pole_at.y), 0.1, {"slide": Vector3(d.x, 0, d.y), "max_slide": 4.0, "walk": 0.0, "gap": 0.2, "reserved_ok": true, "source": "bus_stop"})
		if spot != null: pole_at = Vector2((spot as Vector3).x, (spot as Vector3).z)
		placer.record("bus_shelter", Vector3(kerb.x, 0, kerb.y), 1.9, "bus_stop")
	var pole_t := Transform3D(basis, Vector3(pole_at.x, 0.12, pole_at.y))
	props.add("bus_stop_pole", pole_t, tint, 140.0)
	props.box_collider(pole_t * Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), basis)
	for side in [1.0, -1.0]:
		var l := Label3D.new()
		l.text = "%s\nBUS" % line.number
		l.font_size = 40
		l.pixel_size = 0.004
		l.outline_size = 0
		l.modulate = Color.WHITE
		l.double_sided = false
		# 5 mm proud of the flag panel's trim face (it was 1 mm).
		l.transform = pole_t * Transform3D(Basis(Vector3.UP, PI * 0.5 if side > 0 else -PI * 0.5), Vector3(side * 0.05, 2.6, 0))
		l.visibility_range_end = 50.0
		add_child(l)
	# Illuminated advert on the shelter end panel (both faces).
	var ads := ["VISIT ATATÜRK SQUARE\nMONUMENT · FOUNTAIN · CAFÉS", "TRY 16 TURKISH KITCHENS\nKEBAB · PİDE · BAKLAVA", "STREET ART TRAIL\nKARA FATMA · HALİME ÇAVUŞ", "COURIERNOW\nRIDE · DELIVER · EARN"]
	for face in [1.0, -1.0]:
		var ad := Label3D.new()
		ad.text = ads[stops.size() % ads.size()]
		ad.font_size = 22
		ad.pixel_size = 0.0035
		ad.outline_size = 0
		ad.modulate = Color("23313a")
		ad.double_sided = false
		# 9 mm outside the lit advert box (x -1.826 .. -1.674): at 0.07 the text sat inside it.
		ad.transform = shelter_t * Transform3D(Basis(Vector3.UP, -PI * 0.5 if face < 0 else PI * 0.5), Vector3(-1.75 + face * 0.085, 1.4, -0.05))
		ad.visibility_range_end = 30.0
		add_child(ad)
	var name_label := Label3D.new()
	name_label.text = "%s  ·  LINE %s  %s" % [StreetNames.name_at(Vector3(p.x, 0, p.y)).to_upper(), line.number, line.title]
	name_label.font_size = 18
	name_label.pixel_size = 0.004
	name_label.outline_size = 0
	name_label.modulate = Color("f4f1e6")
	name_label.transform = shelter_t * Transform3D(Basis.IDENTITY, Vector3(0, 2.66, 0.71))
	name_label.visibility_range_end = 40.0
	add_child(name_label)
	# Stop position along the loop: bus centre a few metres before the shelter so the front
	# door opens at it.
	var s := project(line, Vector3(lane_point.x, 0, lane_point.y)) + DOOR_FRONT + 1.0
	var stop := {"s": fposmod(s, line.total), "shelter": shelter_t, "kerb": Vector3(kerb.x, 0.12, kerb.y),
		"waiting": [], "respawn": randf_range(2.0, 10.0), "line": line.number, "door_side": Vector3(right.x, 0, right.y)}
	line.stops.append(stop)
	stops.append(stop)

## Arc-length position of the closest point on a line's path.
func project(line: Dictionary, p: Vector3) -> float:
	var path: PackedVector3Array = line.path
	var lengths: PackedFloat32Array = line.lengths
	var best := 0.0
	var best_d := INF
	for i in range(path.size()):
		var a := path[i]
		var b := path[(i + 1) % path.size()]
		var q := Geometry3D.get_closest_point_to_segment(p, a, b)
		var d := q.distance_to(p)
		if d < best_d:
			best_d = d
			best = lengths[i] + a.distance_to(q)
	return best

## Position and forward direction at arc length s.
func sample(line: Dictionary, s: float) -> Array:
	var path: PackedVector3Array = line.path
	var lengths: PackedFloat32Array = line.lengths
	s = fposmod(s, line.total)
	var i := lengths.bsearch(s, true) - 1
	i = clampi(i, 0, path.size() - 1)
	var a := path[i]
	var b := path[(i + 1) % path.size()]
	var seg := maxf(lengths[i + 1] - lengths[i], 0.001)
	return [a.lerp(b, (s - lengths[i]) / seg), (b - a).normalized()]

func add_bus(li: int, s: float) -> void:
	var line: Dictionary = lines[li]
	var body := AnimatableBody3D.new()
	body.name = "Bus_%s_%d" % [line.number, buses.size()]
	body.sync_to_physics = false
	body.collision_layer = 1
	body.collision_mask = 0
	add_child(body)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(WIDTH, 2.9, 12.0)
	shape.shape = box
	shape.position.y = 1.6
	body.add_child(shape)
	var tint := {"accent": Color(line.colour).srgb_to_linear()}
	var model := Node3D.new()
	body.add_child(model)
	attach(model, "bus_body", Transform3D.IDENTITY, tint)
	var wheels: Array[Node3D] = []
	for z in [-3.35, 2.35]:
		for sx in [-1.0, 1.0]:
			var w := Node3D.new()
			w.position = Vector3(sx * 1.08, 0.5, z)
			w.rotation.y = 0.0 if sx > 0 else PI
			model.add_child(w)
			attach(w, "bus_wheel", Transform3D.IDENTITY, tint)
			wheels.append(w)
	var doors: Array[Node3D] = []
	for z0 in [-4.6, -0.2]:
		for leaf in range(2):
			var d := Node3D.new()
			var hinge_z: float = z0 + (0.0 if leaf == 0 else 1.2)
			d.position = Vector3(WIDTH / 2 - 0.03, 0.0, hinge_z)
			d.rotation.y = 0.0 if leaf == 0 else PI
			model.add_child(d)
			attach(d, "bus_door", Transform3D.IDENTITY, tint)
			doors.append(d)
	for spec in [[Vector3(0, 2.69, -5.63), 0.0, "%s  %s" % [line.number, line.title], 30], [Vector3(0, 2.15, 6.02), PI, line.number, 60]]:
		var l := Label3D.new()
		l.text = spec[2]
		l.font_size = spec[3]
		l.pixel_size = 0.0035 if spec[3] < 40 else 0.004
		l.outline_size = 0
		l.modulate = Color("ffb43c")
		l.double_sided = false
		l.transform = Transform3D(Basis(Vector3.UP, PI + spec[1]), spec[0])
		l.visibility_range_end = 80.0
		model.add_child(l)
	var lights: Array[OmniLight3D] = []
	var head := SpotLight3D.new()
	head.position = Vector3(0, 0.8, -6.2)
	head.light_color = Color("fff1d6")
	head.spot_range = 22.0
	head.spot_angle = 35.0
	head.light_energy = 0.0
	head.distance_fade_enabled = true
	head.distance_fade_begin = 90.0
	model.add_child(head)
	var bus := {"body": body, "model": model, "line": li, "s": s, "speed": 0.0, "wheels": wheels, "doors": doors,
		"state": "drive", "timer": 0.0, "next_stop": next_stop_index(line, s), "door_open": 0.0, "blocked": 0.0,
		"head": head, "boarded": false, "sound": null}
	buses.append(bus)
	place(bus)

func attach(parent: Node3D, asset: String, t: Transform3D, colours: Dictionary) -> void:
	for p in props.get_parts(asset, "near"):
		var mesh := MeshInstance3D.new()
		mesh.mesh = p.mesh
		mesh.material_override = p.material
		mesh.transform = t * p.transform
		mesh.visibility_range_end = 260.0
		var tint_colour := HouseInstancer.tint(p.name, colours)
		if tint_colour != Color.WHITE:
			mesh.material_override = tinted(p.material, tint_colour)
		parent.add_child(mesh)

static var tinted_cache := {}
static func tinted(base: Material, colour: Color) -> Material:
	var key := "%d_%s" % [base.get_instance_id(), colour.to_html()]
	if not tinted_cache.has(key):
		var m := base.duplicate() as StandardMaterial3D
		m.albedo_color = m.albedo_color * colour
		tinted_cache[key] = m
	return tinted_cache[key]

func next_stop_index(line: Dictionary, s: float) -> int:
	var best := 0
	var best_gap := INF
	for i in range(line.stops.size()):
		var gap := fposmod(float(line.stops[i].s) - s, line.total)
		if gap > 1.0 and gap < best_gap:
			best_gap = gap
			best = i
	return best

func place(bus: Dictionary) -> void:
	var line: Dictionary = lines[bus.line]
	var front: Array = sample(line, bus.s + 3.0)
	var back: Array = sample(line, bus.s - 3.0)
	var centre: Vector3 = (front[0] + back[0]) * 0.5
	var forward: Vector3 = (front[0] - back[0]).normalized()
	var basis := Basis.looking_at(forward, Vector3.UP)
	var kneel := 0.06 * float(bus.door_open)
	bus.body.global_transform = Transform3D(basis, centre + Vector3(0, 0.04 - kneel, 0))

func _physics_process(delta: float) -> void:
	if audio == null:
		audio = get_tree().get_first_node_in_group("city_audio") as CityAudio
	var space := get_world_3d().direct_space_state
	var clocks := SignalPlan.clocks_for(get_parent()) if get_parent() != null else {}
	for bus in buses:
		var line: Dictionary = lines[bus.line]
		var stop: Dictionary = line.stops[bus.next_stop]
		var to_stop := fposmod(float(stop.s) - float(bus.s), line.total)
		var target := CRUISE
		# Corners: slow down when the path ahead turns.
		var here: Array = sample(line, bus.s)
		var ahead: Array = sample(line, bus.s + 14.0)
		if Vector3(here[1]).dot(ahead[1]) < 0.9: target = CORNER_SPEED
		match bus.state:
			"drive":
				target = minf(target, sqrt(maxf(0.0, 2.0 * BRAKE * (to_stop - 0.3))) + 0.3)
				# Traffic signals: stop at the stop line on red, and on amber when it can.
				target = minf(target, SignalPlan.bus_limit(bus, line, clocks))
				if to_stop < 0.4:
					bus.state = "dwell"
					bus.timer = 0.0
					bus.boarded = false
					target = 0.0
					sound("air_brake_hiss", bus, -6.0)
			"dwell":
				target = 0.0
				bus.timer += delta
				dwell(bus, stop, delta)
			"depart":
				bus.timer += delta
				if bus.timer > 1.0: bus.state = "drive"
		# Anything in front (courier, cars, another bus): brake, and give way after a while.
		if bus.state != "dwell" and bus.speed > -1.0:
			# Swept boxes along the path ahead (they follow corners), at body height so the
			# road and kerbs never count; only moving things (vehicles, people) stop the bus.
			var reach: float = 3.0 + bus.speed * bus.speed / (2.0 * BRAKE)
			var blocker: Object = null
			var probe := PhysicsShapeQueryParameters3D.new()
			probe.shape = probe_box
			probe.collision_mask = 1 | 4
			probe.exclude = [bus.body.get_rid()]
			var step := 0.0
			while step < reach and blocker == null:
				var at: Array = sample(line, bus.s + 6.6 + step + 1.0)
				probe.transform = Transform3D(Basis.looking_at(at[1], Vector3.UP), at[0] + Vector3(0, 1.4, 0))
				for hit in space.intersect_shape(probe, 4):
					if hit.collider is CharacterBody3D or hit.collider is AnimatableBody3D:
						blocker = hit.collider
						break
				step += 2.0
			if blocker != null:
				# AI cars (TrafficDriver) queue at signals and always move on, so the bus waits for
				# them; only two buses waiting on each other at a junction edge through.
				var vehicle := str(blocker.name).begins_with("Bus_")
				bus.blocked += delta
				if not (vehicle and bus.blocked > 8.0): target = 0.0
			else:
				bus.blocked = 0.0
		bus.speed = move_toward(bus.speed, target, delta * (ACCEL if target > bus.speed else BRAKE * 1.6))
		var travel: float = bus.speed * delta
		bus.s = fposmod(bus.s + travel, line.total)
		for w in bus.wheels: w.rotate_object_local(Vector3.RIGHT, -travel / 0.5)
		# Doors: plug doors swing out and slide along the body.
		var goal := 1.0 if bus.state == "dwell" and bus.timer > 0.8 and bus.timer < float(stop.get("close", 9.0)) else 0.0
		bus.door_open = move_toward(bus.door_open, goal, delta * 1.6)
		for i in range(bus.doors.size()):
			var leaf: Node3D = bus.doors[i]
			var hinge_z: float = (-4.6 if i < 2 else -0.2) + (0.0 if i % 2 == 0 else 1.2)
			var slide: float = (0.55 if i % 2 == 0 else -0.55) * bus.door_open
			leaf.position = Vector3(WIDTH / 2 - 0.03 + 0.12 * bus.door_open, 0.0, hinge_z - slide)
		place(bus)
		bus.head.light_energy = 1.6 * night
	walk(delta)
	respawn(delta)

## At a stop: alight 0-2 passengers from the middle door, board everyone waiting through the
## front door, chime, close and pull away.
func dwell(bus: Dictionary, stop: Dictionary, _delta: float) -> void:
	var t := bus.body.global_transform as Transform3D
	if not bus.boarded and bus.timer > 1.2:
		bus.boarded = true
		sound("bus_door", bus, -4.0)
		var count := randi() % 3
		for k in range(count):
			var p := passenger(k + buses.find(bus) * 3)
			p.global_position = t * Vector3(WIDTH / 2 + 0.4, 0.0, DOOR_MID + 0.6)
			var away: Vector3 = Vector3(stop.kerb) + (t.basis * Vector3(0, 0, 1.0 if k % 2 == 0 else -1.0)) * randf_range(8.0, 14.0)
			walkers.append({"node": p, "to": away, "then": "vanish"})
		var waiting: Array = stop.waiting
		for k in range(waiting.size()):
			var w: Node3D = waiting[k]
			walkers.append({"node": w, "to": t * Vector3(WIDTH / 2 + 0.35, 0.0, DOOR_FRONT), "then": "board", "delay": k * 0.9})
		stop.waiting = []
		stop.close = 4.5 + waiting.size() * 1.1 + count * 0.6
		stop.respawn = randf_range(18.0, 40.0)
	if bus.timer > float(stop.get("close", 9.0)) - 0.6 and bus.timer < float(stop.get("close", 9.0)) - 0.6 + get_physics_process_delta_time():
		sound("bus_stop_chime", bus, -8.0)
	if bus.timer > float(stop.get("close", 9.0)) + 1.0:
		bus.state = "depart"
		bus.timer = 0.0
		bus.next_stop = (bus.next_stop + 1) % lines[bus.line].stops.size()
		sound("bus_door", bus, -6.0)

func passenger(index: int) -> Node3D:
	var p: Node3D = pool.pop_back() if not pool.is_empty() else null
	if p == null:
		p = LivingAssets.citizen(index + 40)
		p.max_distance = 70.0
		add_child(p)
	p.visible = true
	p.purpose_pose = ""
	return p

## Waiting passengers gather at shelters between buses.
func respawn(delta: float) -> void:
	for stop in stops:
		stop.respawn = float(stop.respawn) - delta
		if stop.respawn > 0.0 or stop.waiting.size() >= 3: continue
		stop.respawn = randf_range(12.0, 30.0)
		var t: Transform3D = stop.shelter
		var k: int = stop.waiting.size()
		var p := passenger(stops.find(stop) * 3 + k)
		p.global_transform = t * Transform3D(Basis(Vector3.UP, PI + randf_range(-0.6, 0.6)), Vector3(-0.9 + k * 0.9, 0.0, 0.25 + 0.3 * (k % 2)))
		p.purpose_pose = "Wait" if k % 2 == 0 else "Idle"
		stop.waiting.append(p)

func walk(delta: float) -> void:
	for i in range(walkers.size() - 1, -1, -1):
		var w: Dictionary = walkers[i]
		if w.get("delay", 0.0) > 0.0:
			w.delay = float(w.delay) - delta
			continue
		var node: Node3D = w.node
		var to: Vector3 = w.to
		var step := 1.3 * delta
		var flat := Vector3(to.x - node.global_position.x, 0, to.z - node.global_position.z)
		if flat.length() <= step:
			node.visible = false
			pool.append(node)
			walkers.remove_at(i)
			continue
		node.global_position += flat.normalized() * step
		node.global_basis = Basis.looking_at(-flat.normalized(), Vector3.UP)

func sound(name: String, bus: Dictionary, volume: float) -> void:
	if audio != null: audio.one_shot_at(name, bus.body.global_position + Vector3(0, 1.5, 0), volume, 6.0)

func set_night(amount: float) -> void:
	night = amount
