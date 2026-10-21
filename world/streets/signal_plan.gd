class_name SignalPlan
extends RefCounted
## Signal timing and stop lines for every signalised junction and crossing of the city.
##
## A junction is controlled per *axis*: "ns" = vehicles travelling along z, "ew" = along x.
## Each program gives, per axis, [green start, amber start, red start] inside its cycle, so a
## green is followed by amber, then red; the gap between one axis' red start and the other's
## green start is the all-red clearance. Conflicting axes are never green together.
## Pedestrian heads either run with the parallel vehicle green (WALK for the first `walk`
## seconds, then flashing DON'T WALK until amber) or, with "ped", in an exclusive phase.
##
## Clocks: "city" junctions run on CityTraffic.elapsed (pausable, the clock city_test drives),
## "downtown" junctions on the downtown population's signal phase (its walkers use the same
## phase for the scramble crossing).
##
## Stops: for every route (a closed polyline with cumulative lengths) the points where it
## enters a junction's control rectangle are its stop lines; a vehicle's front bumper must stay
## behind them while its axis shows red, or amber when it can still stop comfortably.

enum { GREEN, AMBER, RED }
enum { DONT_WALK, WALK, FLASH }

const PROGRAMS := {
	# Atatürk Avenue x cross streets: avenue 15 s green, cross street 11 s, 3 s amber, 2 s all-red.
	"avenue": {"cycle": 36.0, "ns": [0.0, 15.0, 18.0], "ew": [20.0, 31.0, 34.0], "walk": 7.0},
	# Side road x cross street: the side road (ns) carries the through traffic.
	"side": {"cycle": 36.0, "ns": [0.0, 16.0, 19.0], "ew": [21.0, 31.0, 34.0], "walk": 7.0},
	# Mid-block pedestrian crossing on the avenue (CityTraffic.crossing_red(): red from 16 s).
	"midblock": {"cycle": 24.0, "ns": [0.0, 13.0, 16.0], "ew": [], "ped": [16.0, 20.5, 23.5]},
	# Downtown grid (DowntownPopulation phase): ns 0-14, ew 16-30, then a pedestrian scramble.
	"downtown": {"cycle": 64.0, "ns": [0.0, 12.0, 14.0], "ew": [16.0, 28.0, 30.0], "ped": [32.0, 41.0, 58.0]},
}
## Distance (m) from the junction box edge to where a front bumper stops: crosswalk gap 0.5,
## crosswalk 3.0, stop bar centre 0.8 (StreetGrid), +0.2 half bar, +0.4 margin.
const STOP_BACK := 4.9
const COMFORT_DECEL := 3.2   ## amber: stop if this is enough
const HARD_DECEL := 6.5      ## red: stop if this is enough (else already committed)
const STOP_DECEL := 2.6      ## profile used to come to rest at the line

static var _junctions: Array[Dictionary] = []
static var _stops: Dictionary = {}   ## route instance id -> Array[Dictionary]
## Every managed AI vehicle (TrafficDriver dictionaries) for the keep-the-box-clear check.
static var vehicles: Array[Dictionary] = []

## All signalised junctions: {"id", "centre": Vector2, "hx", "hz" (box half extents in x / z),
## "stop_ns", "stop_ew" (control rectangle half extents), "program", "offset", "clock",
## "kind" ("junction" / "midblock"), "arms": {"n","s","e","w": bool}, "district"}.
static func junctions() -> Array[Dictionary]:
	if not _junctions.is_empty(): return _junctions
	var list: Array[Dictionary] = []
	var k := 0
	for z: float in [-258.0, -398.0, -538.0, -678.0]:
		list.append(junction("Avenue%d" % int(z), Vector2(0, z), 6.0, 5.0, "avenue", 18.0 * (k % 2), "city"))
		k += 1
	list.append(junction("Side64_398", Vector2(64, -398), 5.0, 5.0, "side", 9.0, "city"))
	list.append(junction("Side-64_538", Vector2(-64, -538), 5.0, 5.0, "side", 27.0, "city"))
	for z: float in [-93.0, -177.0]:
		var mid := junction("Crossing%d" % int(z), Vector2(0, z), 6.0, 1.5, "midblock", 0.0, "city")
		mid.kind = "midblock"
		mid.stop_ns = 5.3
		mid.stop_ew = 6.0
		list.append(mid)
	for x: float in DowntownCatalog.STREET_X:
		for z: float in DowntownCatalog.STREET_Z:
			var dt := junction("Downtown%d_%d" % [int(x), int(z)], Vector2(x, z), 9.0 if x == 252.0 else 7.0, 7.0, "downtown", 0.0, "downtown")
			# Downtown stop bars sit 12 m out on the ns approaches; ew crosswalks at 11 m.
			dt.stop_ns = 12.5
			dt.stop_ew = 13.4
			dt.cw_ns = 9.0
			dt.cw_ew = 11.0
			dt.district = "downtown"
			list.append(dt)
	_junctions = list
	return list

static func junction(id: String, centre: Vector2, hx: float, hz: float, program: String, offset: float, clock: String) -> Dictionary:
	# cw_ns / cw_ew: distance from the centre to the crosswalk that vehicles travelling along z /
	# along x drive over (StreetGrid: box edge + 0.5 gap + half of the 3 m crosswalk).
	var j := {"id": id, "centre": centre, "hx": hx, "hz": hz, "stop_ns": hz + STOP_BACK, "stop_ew": hx + STOP_BACK,
		"cw_ns": hz + 2.0, "cw_ew": hx + 2.0,
		"program": program, "offset": offset, "clock": clock, "kind": "junction", "district": "city"}
	j.arms = arms_of(centre, hx, hz)
	return j

## Which of the four arms (n = +z, s = -z, e = +x, w = -x) have a road at least 9 m long
## beyond the junction box (StreetGrid streets and downtown's grid).
static func arms_of(c: Vector2, hx: float, hz: float) -> Dictionary:
	var out := {"n": false, "s": false, "e": false, "w": false}
	var probes := {"n": c + Vector2(0, hz + 9.0), "s": c - Vector2(0, hz + 9.0), "e": c + Vector2(hx + 9.0, 0), "w": c - Vector2(hx + 9.0, 0)}
	for arm: String in probes:
		var p: Vector2 = probes[arm]
		var hit := PropPlacer.surface_at(p, 0.0, ["street", "downtown"] as Array[String])
		out[arm] = not hit.is_empty()
	return out

# ----------------------------------------------------------------------------- timing

## Vehicle aspect for `axis` ("ns" / "ew") of junction j at clock time t (seconds).
static func state(j: Dictionary, axis: String, t: float) -> int:
	var prog: Dictionary = PROGRAMS[j.program]
	var ph: Array = prog[axis]
	if ph.is_empty(): return GREEN
	var tt := fposmod(t - float(j.offset), float(prog.cycle))
	var g: float = ph[0]
	var a: float = ph[1]
	var r: float = ph[2]
	if tt >= g and tt < a: return GREEN
	if tt >= a and tt < r: return AMBER
	return RED

## Pedestrian aspect for a crosswalk whose walkers move along `walk_axis` ("ns": they cross
## the east-west road, "ew": they cross the north-south road).
static func ped_state(j: Dictionary, walk_axis: String, t: float) -> int:
	var prog: Dictionary = PROGRAMS[j.program]
	var tt := fposmod(t - float(j.offset), float(prog.cycle))
	if prog.has("ped"):
		var p: Array = prog.ped
		if tt >= float(p[0]) and tt < float(p[1]): return WALK
		if tt >= float(p[1]) and tt < float(p[2]): return FLASH
		return DONT_WALK
	var ph: Array = prog[walk_axis]
	if ph.is_empty(): return DONT_WALK
	var g: float = ph[0]
	if tt >= g and tt < g + float(prog.walk): return WALK
	if tt >= g + float(prog.walk) and tt < float(ph[1]): return FLASH
	return DONT_WALK

## Seconds left of the flashing DON'T WALK (countdown), 0 outside it.
static func ped_countdown(j: Dictionary, walk_axis: String, t: float) -> float:
	var prog: Dictionary = PROGRAMS[j.program]
	var tt := fposmod(t - float(j.offset), float(prog.cycle))
	var end := 0.0
	if prog.has("ped"): end = float(prog.ped[2])
	elif not (prog[walk_axis] as Array).is_empty(): end = float(prog[walk_axis][1])
	return maxf(end - tt, 0.0) if ped_state(j, walk_axis, t) == FLASH else 0.0

## The axes are never green or amber at the same time (checked by tests/traffic_signal_test.gd).
static func conflict(j: Dictionary, t: float) -> bool:
	return state(j, "ns", t) != RED and state(j, "ew", t) != RED and not (PROGRAMS[j.program].ew as Array).is_empty()

# ----------------------------------------------------------------------------- stop lines

## Stop lines along a closed polyline route (SmoothRoute points / lengths):
## Array of {"s": distance where the front bumper stops, "exit": distance where the route
## leaves the control rectangle, "j": junction index, "axis"}.
static func stops_for(route: SmoothRoute) -> Array[Dictionary]:
	var key := route.get_instance_id()
	if _stops.has(key): return _stops[key]
	var out := stops_along(route.points, route.lengths, route.total)
	_stops[key] = out
	return out

static func stops_along(points: PackedVector3Array, lengths: PackedFloat32Array, total: float) -> Array[Dictionary]:
	# Routes keep straight legs as single long segments, so every segment is clipped against
	# each control rectangle (slab method) rather than testing the points.
	var out: Array[Dictionary] = []
	var list := junctions()
	var n := points.size()
	for ji in range(list.size()):
		var j: Dictionary = list[ji]
		var c: Vector2 = j.centre
		var ex: float = j.stop_ew
		var ez: float = j.stop_ns
		var prog: Dictionary = PROGRAMS[j.program]
		# Start at a point outside the rectangle so no stretch is split at the seam.
		var first := -1
		for i in range(n):
			if absf(points[i].x - c.x) >= ex or absf(points[i].z - c.y) >= ez:
				first = i
				break
		if first < 0: continue
		var inside := false
		var entry_s := 0.0
		var entry_axis := ""
		for step in range(n):
			var i := (first + step) % n
			var a := points[i]
			var b := points[(i + 1) % n]
			var seg := a.distance_to(b)
			if seg < 0.0001: continue
			var s0: float = lengths[i] + (total if i < first else 0.0)
			var d := b - a
			# Parametric interval of the segment inside the rectangle, and which slab bounds the entry.
			var t0 := 0.0
			var t1 := 1.0
			var enter_axis := ""
			var empty := false
			for k in range(2):
				var o: float = a.x - c.x if k == 0 else a.z - c.y
				var v: float = d.x if k == 0 else d.z
				var h: float = ex if k == 0 else ez
				if absf(v) < 0.000001:
					if absf(o) >= h: empty = true
					continue
				var ta := (-h - o) / v
				var tb := (h - o) / v
				if ta > tb:
					var tmp := ta
					ta = tb
					tb = tmp
				if ta > t0:
					t0 = ta
					enter_axis = "ew" if k == 0 else "ns"
				t1 = minf(t1, tb)
			if empty or t0 >= t1: 
				if inside:
					inside = false
					if not (prog[entry_axis] as Array).is_empty():
						out.append({"s": fposmod(entry_s, total), "exit": fposmod(entry_s, total) + (s0 - entry_s), "j": ji, "axis": entry_axis})
				continue
			if not inside and t0 > 0.0:
				inside = true
				entry_s = s0 + seg * t0
				entry_axis = enter_axis
			elif not inside:
				# Starts inside without an entry (only possible at the seam): skip.
				continue
			if t1 < 1.0:
				inside = false
				var exit_s := s0 + seg * t1
				if not (prog[entry_axis] as Array).is_empty():
					out.append({"s": fposmod(entry_s, total), "exit": fposmod(entry_s, total) + (exit_s - entry_s), "j": ji, "axis": entry_axis})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.s) < float(b.s))
	return out

## Is distance s of the route inside a junction control rectangle (between a stop line and the
## far side, plus `margin`)? Used to keep spawned vehicles out of junctions.
static func in_junction(route: SmoothRoute, s: float, margin := 3.0) -> bool:
	for st in stops_for(route):
		var a := float(st.s) - margin
		var d := fposmod(s - a, route.total)
		if d < float(st.exit) - float(st.s) + 2.0 * margin: return true
	return false

## Next stop ahead of a front bumper at distance `front` (wraps): [stop, distance] or [{}, INF].
static func next_stop(stops: Array[Dictionary], front: float, total: float, reach := 70.0) -> Array:
	var best: Dictionary = {}
	var best_d := INF
	for st in stops:
		var d := fposmod(float(st.s) - front, total)
		if d < best_d and d < reach:
			best_d = d
			best = st
	return [best, best_d]

## Speed limit (m/s) imposed by the signals on a vehicle. `car` is a TrafficDriver dictionary;
## `clocks` maps clock name -> current time. Records the decision in car.sig_commit (the stop
## the vehicle has decided to drive through on amber) and car.sig_state for brake lights.
static func limit(car: Dictionary, clocks: Dictionary, stops: Array[Dictionary]) -> float:
	var route: SmoothRoute = car.route
	return decide(car, float(car.s) + float(car.half), route.total, stops, clocks, route)

## City buses (BusSystem lines: {"path", "lengths", "total"}; bus {"s" = body centre, "speed"}):
## the same stop-line rules for the 12 m bus (its front is 6 m ahead of s).
static func bus_limit(bus: Dictionary, line: Dictionary, clocks: Dictionary) -> float:
	if not line.has("signal_stops"): line["signal_stops"] = stops_along(line.path, line.lengths, float(line.total))
	var stops: Array[Dictionary] = line["signal_stops"]
	return decide(bus, float(bus.s) + 6.0, float(line.total), stops, clocks, null)

## Signal clocks of a city world (CedarNeighborhood): "city" = CityTraffic.elapsed,
## "downtown" = the downtown traffic's signal clock.
static func clocks_for(world: Node) -> Dictionary:
	var out := {"city": 0.0, "downtown": 0.0}
	var traffic := world.get_node_or_null("CityTraffic")
	if traffic != null: out.city = float(traffic.get("elapsed"))
	var downtown: Variant = world.get("downtown")
	if downtown != null and (downtown as Node).get("population") != null:
		var fleet := ((downtown as Node).get("population") as Node).get_node_or_null("CivicFleet")
		if fleet != null: out.downtown = float(fleet.get("signal_clock"))
	return out

## The stop-line decision (see limit). `route` null skips the keep-the-box-clear check.
static func decide(car: Dictionary, front: float, total: float, stops: Array[Dictionary], clocks: Dictionary, route: SmoothRoute) -> float:
	var hit := next_stop(stops, front, total)
	var st: Dictionary = hit[0]
	car.sig_state = GREEN
	if st.is_empty(): return INF
	var d: float = hit[1]
	var j: Dictionary = junctions()[int(st.j)]
	var t: float = clocks.get(String(j.clock), 0.0)
	var aspect := state(j, String(st.axis), t)
	var v: float = car.speed
	var key: int = int(st.j) * 100000 + int(float(st.s))
	# A commitment holds only while the car keeps moving on from where it decided (a car
	# teleported back, or a whole lap later, decides again).
	var since: float = float(car.s) - float(car.get("sig_at", -INF))
	var committed: bool = int(car.get("sig_commit", -1)) == key and since >= -0.1 and since < 40.0
	car.sig_state = aspect
	var stop := false
	if aspect == AMBER and not committed:
		if v * v / (2.0 * maxf(d - 0.3, 0.05)) <= COMFORT_DECEL or v < 1.0: stop = true
		else: commit(car, key)
	elif aspect == RED and not committed:
		stop = v * v / (2.0 * maxf(d - 0.3, 0.05)) <= HARD_DECEL or v < 2.0
		if not stop: commit(car, key)
	elif aspect == GREEN:
		# Keep the junction clear: only enter when there is room beyond it.
		if d < 3.0 + v * v / (2.0 * COMFORT_DECEL) and not committed:
			if route != null and exit_blocked(car, route, float(st.exit)): stop = true
			elif d < 1.5: commit(car, key)
	if not stop: return INF
	return 0.0 if d < 0.6 else sqrt(2.0 * STOP_DECEL * (d - 0.6))

static func commit(car: Dictionary, key: int) -> void:
	car.sig_commit = key
	car.sig_at = float(car.s)

## Is the lane just beyond the junction occupied by a slow vehicle (no room to clear the box)?
static func exit_blocked(car: Dictionary, route: SmoothRoute, exit_s: float) -> bool:
	var need: float = float(car.size.z) + 3.0
	var a := route.at(exit_s + need * 0.5)
	var dir := a.direction_to(route.at(exit_s + need * 0.5 + 2.0))
	for other in vehicles:
		if is_same(other, car) or float(other.speed) >= 3.5: continue
		var body: Node3D = other.body
		var p := body.global_position
		if absf(p.x - a.x) > need + 4.0 or absf(p.z - a.z) > need + 4.0: continue
		var rel := Vector3(p.x - a.x, 0.0, p.z - a.z)
		# Same lane (lateral < 1.6 m) and overlapping the space the car needs.
		if absf(rel.dot(dir)) < need * 0.5 + float(other.half) and absf(rel.cross(dir).y) < 1.6:
			return true
	return false
