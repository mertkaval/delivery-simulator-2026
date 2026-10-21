class_name CitySeating
extends RefCounted
## Seats people can sit on, measured from the actual meshes, and the placement that puts a
## LivingCitizen's buttocks on the seat, its back on the backrest and its feet on the floor.
##
## A seat slot is a Dictionary:
##   frame  Transform3D  origin at the slot centre on the seat's base, +Z = the way a sitter faces
##   top    float        seat top height in the frame (y)
##   front  float        seat front edge (z, frame)
##   back   float        backrest front plane (z, frame; negative = behind the seat centre)
##   floor  float        floor height under the sitter's feet (y, frame)
##   user   Object       who sits / is walking to it (null = free)
##
## Seat dimensions (Godot metres, measured from the GLB / kit meshes, tmp seat scan):
##   bench_wood (PropKit street bench)      top 0.44, front +0.24, back -0.20, 1.36 m long, faces +Z
##   reuse_park_bench (downtown kit bench)  top 0.52, front +0.28, back -0.30, 2.0 m long, faces +Z
##   rs chair (build_restaurants.chair)     top 0.49 on its base, front +0.22, back -0.185, faces +Z
##   rs_booth bench                         top 0.56, front 0.25 ahead of the bench centre, back -0.15
##   avenue restaurant chairs (restaurant_0..2.glb) top 0.50
const BENCH := {
	"bench_wood": {"top": 0.44, "front": 0.238, "back": -0.20, "slots": [-0.36, 0.36]},
	"reuse_park_bench": {"top": 0.52, "front": 0.28, "back": -0.30, "slots": [-0.62, 0.0, 0.62]},
}

static func bench_slots(xform: Transform3D, kind: String) -> Array[Dictionary]:
	var spec: Dictionary = BENCH[kind]
	var out: Array[Dictionary] = []
	for x: float in spec.slots:
		out.append({"frame": xform * Transform3D(Basis.IDENTITY, Vector3(x, 0, 0)), "top": spec.top, "front": spec.front,
			"back": spec.back, "floor": 0.0, "user": null, "kind": kind})
	return out

static func slot(frame: Transform3D, top: float, front: float, back: float, floor_y: float, kind: String) -> Dictionary:
	return {"frame": frame, "top": top, "front": front, "back": back, "floor": floor_y, "user": null, "kind": kind}

## Body origin (in the slot frame, model facing +Z of the frame) for a seated person:
## y puts the measured buttock contact on the seat top; z puts the back on the backrest, but
## never so far back that the knees (0.07 m ahead of the origin) sit behind the seat edge.
static func seated_origin(person: LivingCitizen, s: Dictionary) -> Vector3:
	var m: Vector3 = LivingAssets.SEATED.get(person.body_id, Vector3(0.45, -0.44, 0.0))
	var k := person.body_scale
	var y: float = float(s.top) - m.x * k
	var z: float = maxf(float(s.back) - m.y * k, float(s.front) - 0.04 * k)
	return Vector3(0, y, z)

## Where the person stands (feet on the floor) before Sitting_Enter / after Sitting_Exit.
static func standing_origin(person: LivingCitizen, s: Dictionary) -> Vector3:
	var o := seated_origin(person, s)
	return Vector3(0, float(s.floor), o.z)

## Model transform (LivingCitizen faces -Z, so it is turned to face the frame's +Z).
static func pose(s: Dictionary, local: Vector3) -> Transform3D:
	return (s.frame as Transform3D) * Transform3D(Basis(Vector3.UP, PI), local)

## Puts `person` on the seat now (static sitters): seated pose and placement.
static func sit(person: LivingCitizen, s: Dictionary, clip: String = "Sit") -> void:
	person.global_transform = pose(s, seated_origin(person, s))
	person.purpose_pose = clip
	person.ground_speed = 0.0
	s.user = person

## Best body for a seat height among the five characters, with a scale that puts the feet on
## the floor while the buttocks rest on the seat (seat height above floor = (seat - sole) x scale).
static func fit_body(seat_height: float, seed: int) -> Vector2i:
	var best := -1
	var best_err := INF
	for k in range(LivingAssets.HUMANOIDS.size()):
		var id: String = LivingAssets.HUMANOIDS[(k + seed) % LivingAssets.HUMANOIDS.size()]
		var m: Vector3 = LivingAssets.SEATED[id]
		var want := m.x - m.z
		var scale := clampf(seat_height / want, 0.93, 1.07)
		var err := absf(seat_height - want * scale) + 0.004 * k
		if err < best_err:
			best_err = err
			best = (k + seed) % LivingAssets.HUMANOIDS.size()
	return Vector2i(best, 0)

static func fit_scale(seat_height: float, id: String) -> float:
	var m: Vector3 = LivingAssets.SEATED[id]
	return clampf(seat_height / (m.x - m.z), 0.93, 1.07)

## A seated person sized for this seat: picks the body (index chosen so its HUMANOIDS slot fits)
## and scale; outfit colours still come from `index`.
static func seated_person(s: Dictionary, index: int, clip: String = "Sit") -> LivingCitizen:
	var height: float = float(s.top) - float(s.floor)
	var n := LivingAssets.HUMANOIDS.size()
	var body := posmod(index, n)
	var id: String = LivingAssets.HUMANOIDS[body]
	var m: Vector3 = LivingAssets.SEATED[id]
	# Keep the person's own body when a natural scale fits the seat within 3.5 cm; otherwise
	# take the body that fits best (so feet stay on the floor).
	if absf(height - (m.x - m.z) * fit_scale(height, id)) > 0.035:
		body = fit_body(height, index).x
		id = LivingAssets.HUMANOIDS[body]
	# humanoid() picks HUMANOIDS[index % 5]: shift the index onto the chosen body.
	var person_index := index - posmod(index, n) + body
	return LivingAssets.humanoid(person_index, fit_scale(height, id))
