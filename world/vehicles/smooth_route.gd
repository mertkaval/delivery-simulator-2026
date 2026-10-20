class_name SmoothRoute
extends RefCounted
## Smooth driving for AI vehicles.
##
## A route is turned into a dense, closed path (one point every STEP metres) whose corners are
## circular arcs and whose dead-end reversals are "bulb" U-turns, so the path never has a kink.
## Vehicles are posed like real cars: the rear axle sits on the path at distance s and the front
## axle on the path at s + wheelbase, so the body yaw follows the line between the axles (no
## pivoting on the spot) and the front wheels steer by the real angle. Speed is limited by the
## curvature ahead, so cars slow down smoothly before turns.

const STEP := 0.75
## Comfortable lateral acceleration (m/s^2) used to pick cornering speed.
const LATERAL := 1.9

var points := PackedVector3Array()
var lengths := PackedFloat32Array()   ## cumulative distance at each point
var total := 0.0

## Corners of a closed loop; each corner is rounded with up to `radius` metres.
static func from_corners(corners: PackedVector3Array, radius: float) -> SmoothRoute:
	var r := SmoothRoute.new()
	var raw := PackedVector3Array()
	var n := corners.size()
	for i in range(n):
		var here := corners[i]
		var before := corners[posmod(i - 1, n)]
		var after := corners[(i + 1) % n]
		var a := here.direction_to(before)
		var b := here.direction_to(after)
		var turn := PI - a.angle_to(b)              # heading change at this corner
		if turn < 0.02:
			raw.append(here)
			continue
		# Fillet tangent length t = R * tan(turn / 2), limited to half of each leg.
		var room := minf(here.distance_to(before), here.distance_to(after)) * 0.5
		var rad := minf(radius, room / tan(turn * 0.5))
		var t := rad * tan(turn * 0.5)
		var entry := here + a * t
		var exit := here + b * t
		var centre := entry + (b - a * a.dot(b)).normalized() * rad if absf(a.dot(b)) < 0.999 else here
		var start_v := entry - centre
		var end_v := exit - centre
		var steps := maxi(2, ceili(rad * turn / STEP))
		var sweep := start_v.signed_angle_to(end_v, Vector3.UP)
		for k in range(steps + 1):
			raw.append(centre + start_v.rotated(Vector3.UP, sweep * float(k) / steps))
	r._resample(raw)
	return r

## Two-lane loop along one straight road: drive `a`->`b` in the right-hand lane, bulb U-turn,
## return in the other lane, bulb U-turn. `lane` is the lane-centre offset from the centreline,
## `bulb` the U-turn radius; the car eases out towards the kerb first so the radius can be wider
## than the lane offset (a 4.4 m car cannot turn round inside 2 m).
static func shuttle(a: Vector3, b: Vector3, lane: float, bulb: float, swing := 9.0) -> SmoothRoute:
	var r := SmoothRoute.new()
	var raw := PackedVector3Array()
	for leg in range(2):
		var from := a if leg == 0 else b
		var to := b if leg == 0 else a
		var d := from.direction_to(to)
		var right := d.cross(Vector3.UP).normalized()
		var length := from.distance_to(to)
		var s := bulb + swing
		while s < length - bulb - swing:
			raw.append(from + d * s + right * lane)
			s += STEP
		for k in range(13):
			var t := float(k) / 12.0
			var e := t * t * (3.0 - 2.0 * t)
			raw.append(from + d * (length - bulb - swing + swing * t) + right * lerpf(lane, bulb, e))
		var centre := from + d * (length - bulb)
		var start_v := right * bulb
		var sweep := PI * signf(right.signed_angle_to(d, Vector3.UP))
		var steps := ceili(PI * bulb / STEP)
		for k in range(1, steps):
			raw.append(centre + start_v.rotated(Vector3.UP, sweep * float(k) / steps))
		for k in range(13):
			var t := float(k) / 12.0
			var e := t * t * (3.0 - 2.0 * t)
			raw.append(centre - d * (swing * t) - right * lerpf(bulb, lane, e))
	r._resample(raw)
	return r

func _resample(raw: PackedVector3Array) -> void:
	# Remove duplicates and resample at even spacing for constant-speed sampling.
	var clean := PackedVector3Array()
	for p in raw:
		if clean.is_empty() or clean[-1].distance_to(p) > 0.05: clean.append(Vector3(p.x, 0, p.z))
	if clean.size() > 1 and clean[0].distance_to(clean[-1]) < 0.05: clean.remove_at(clean.size() - 1)
	points = clean
	lengths = PackedFloat32Array()
	total = 0.0
	for i in range(points.size()):
		lengths.append(total)
		total += points[i].distance_to(points[(i + 1) % points.size()])

## Position on the path at distance s (wraps around).
func at(s: float) -> Vector3:
	s = fposmod(s, total)
	var lo := 0
	var hi := lengths.size() - 1
	while lo < hi:
		var mid := (lo + hi + 1) >> 1
		if lengths[mid] <= s: lo = mid
		else: hi = mid - 1
	var a := points[lo]
	var b := points[(lo + 1) % points.size()]
	var seg := a.distance_to(b)
	return a.lerp(b, (s - lengths[lo]) / seg) if seg > 0.0001 else a

## Distance along the path of the point nearest to p.
func project(p: Vector3) -> float:
	var best := 0.0
	var best_d := INF
	for i in range(points.size()):
		var a := points[i]
		var b := points[(i + 1) % points.size()]
		var ab := b - a
		var t := clampf((Vector3(p.x, 0, p.z) - a).dot(ab) / maxf(ab.length_squared(), 0.0001), 0.0, 1.0)
		var d := (a + ab * t).distance_squared_to(Vector3(p.x, 0, p.z))
		if d < best_d:
			best_d = d
			best = lengths[i] + ab.length() * t
	return best

## Unsigned curvature (1/m) around distance s, from the heading change over +-span metres.
func curvature(s: float, span := 3.0) -> float:
	var a := at(s - span)
	var m := at(s)
	var b := at(s + span)
	var turn := absf((m - a).signed_angle_to(b - m, Vector3.UP))
	return turn / (2.0 * span)

## Highest comfortable speed for the next `ahead` metres.
func safe_speed(s: float, cruise: float, ahead := 18.0) -> float:
	var v := cruise
	var d := 0.0
	while d <= ahead:
		var k := curvature(s + d)
		if k > 0.001:
			# Allow braking distance: the further the curve, the more speed is allowed now.
			v = minf(v, sqrt(LATERAL / k + 2.2 * d))
		d += 3.0
	return v

## Pose for a vehicle whose rear axle is at s: {"position", "yaw", "steer", "forward"}.
## `position` is the body origin (midway between the axles), yaw follows Godot's -Z forward.
func pose(s: float, wheelbase: float) -> Dictionary:
	var rear := at(s)
	var front := at(s + wheelbase)
	var forward := rear.direction_to(front)
	if forward.length_squared() < 0.5: forward = rear.direction_to(at(s + wheelbase + 1.0))
	var ahead := at(s + wheelbase + 1.5)
	var steer := forward.signed_angle_to(front.direction_to(ahead), Vector3.UP)
	return {"position": (rear + front) * 0.5, "yaw": atan2(-forward.x, -forward.z), "steer": clampf(steer, -0.6, 0.6), "forward": forward}
