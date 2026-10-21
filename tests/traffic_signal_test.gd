extends SceneTree
## Traffic signals (headless): SignalPlan phases never let conflicting directions go together,
## amber always follows green and an all-red clearance follows amber, walk signals only run
## with their parallel green (or in the exclusive scramble); every loop has a stop line at each
## signalised junction it crosses; a car approaching on red stops before the line, the car
## behind queues behind it, and both clear the junction on green; and a few simulated minutes
## of the whole city's traffic end with no deadlock, no vehicle held for good and no two
## vehicles inside each other.
var checks := 0
var failed := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

func phases() -> void:
	for j in SignalPlan.junctions():
		var prog: Dictionary = SignalPlan.PROGRAMS[j.program]
		var cycle: float = prog.cycle
		var conflicts := 0
		var bad_order := 0
		var bad_walk := 0
		var seen := {"ns": [false, false, false], "ew": [false, false, false]}
		var last := {"ns": SignalPlan.state(j, "ns", -0.05), "ew": SignalPlan.state(j, "ew", -0.05)}
		var red_since := {"ns": -100.0, "ew": -100.0}
		var t := 0.0
		while t < cycle * 2.0:
			if SignalPlan.conflict(j, t): conflicts += 1
			for axis: String in ["ns", "ew"]:
				var s := SignalPlan.state(j, axis, t)
				(seen[axis] as Array)[s] = true
				var before: int = last[axis]
				# Green -> amber -> red -> green, never green -> red or red -> amber.
				if before != s and not ((before == SignalPlan.GREEN and s == SignalPlan.AMBER) or (before == SignalPlan.AMBER and s == SignalPlan.RED) or (before == SignalPlan.RED and s == SignalPlan.GREEN)):
					if not (prog[axis] as Array).is_empty(): bad_order += 1
				if s == SignalPlan.RED and before != SignalPlan.RED: red_since[axis] = t
				last[axis] = s
				# Walk only when the parallel traffic has green (concurrent) or all traffic is red.
				var walk := SignalPlan.ped_state(j, axis, t)
				if walk == SignalPlan.WALK:
					var ns := SignalPlan.state(j, "ns", t)
					var ew := SignalPlan.state(j, "ew", t)
					if prog.has("ped"):
						if ns != SignalPlan.RED or (ew != SignalPlan.RED and not (prog.ew as Array).is_empty()): bad_walk += 1
					elif SignalPlan.state(j, axis, t) != SignalPlan.GREEN: bad_walk += 1
			# All-red clearance: when an axis turns green the other has been red >= 1.5 s.
			for axis: String in ["ns", "ew"]:
				var other := "ew" if axis == "ns" else "ns"
				if (prog[other] as Array).is_empty(): continue
				if SignalPlan.state(j, axis, t) == SignalPlan.GREEN and SignalPlan.state(j, axis, t - 0.05) != SignalPlan.GREEN:
					if t - float(red_since[other]) < 1.5 and t > cycle: bad_order += 1
			t += 0.05
		check(conflicts == 0, "%s: conflicting directions never green together (%d)" % [j.id, conflicts])
		check(bad_order == 0, "%s: green -> amber -> red with all-red clearance (%d)" % [j.id, bad_order])
		check(bad_walk == 0, "%s: WALK only with the parallel green / scramble (%d)" % [j.id, bad_walk])
		check((seen.ns as Array)[0] and (seen.ns as Array)[1] and (seen.ns as Array)[2], "%s: ns shows green, amber and red" % j.id)

func run() -> void:
	phases()
	VehicleCatalog.traffic_seed = 11
	var world := CedarNeighborhood.new()
	root.add_child(world)
	for i in range(3): await physics_frame
	var traffic: Node = world.get_node("CityTraffic")
	var signals: TrafficSignals = world.get_node("TrafficSignals")
	check(signals.runtime.size() == SignalPlan.junctions().size(), "Every junction has its signals (%d)" % signals.runtime.size())
	var masts := 0
	var peds := 0
	for rt in signals.runtime:
		masts += int(rt.masts)
		peds += (rt.peds as Array).size()
		check(int(rt.masts) >= 2, "%s has mast-arm signals (%d)" % [rt.def.id, rt.masts])
	check(signals.dropped.is_empty(), "No signal pole dropped for lack of space %s" % [signals.dropped])
	print("signals: %d junctions, %d mast poles, %d pedestrian heads" % [signals.runtime.size(), masts, peds])
	# Stop lines on every loop at the junctions it crosses.
	var expect := {0: ["Crossing-93", "Crossing-177", "Avenue-258"], 3: ["Avenue-258", "Avenue-398", "Avenue-538", "Avenue-678", "Side64_398"],
		4: ["Avenue-678", "Avenue-538", "Avenue-398", "Avenue-258", "Side-64_538"], 5: ["Avenue-398", "Side64_398", "Avenue-258"], 6: ["Avenue-538", "Side-64_538", "Avenue-678"]}
	for li: int in expect:
		var ids: Array = SignalPlan.stops_for(traffic.loops[li]).map(func(s: Dictionary) -> String: return String(SignalPlan.junctions()[int(s.j)].id))
		for want: String in expect[li]: check(want in ids, "Loop %d stops at %s (%s)" % [li, want, ids])
	# ---- red light, queue, green --------------------------------------------------------
	# (Real physics steps: queries see the bodies where the previous step left them.)
	var fleet: Node = world.downtown.population.get_node("CivicFleet")
	var loop: SmoothRoute = traffic.loops[3]   # south-east loop: southbound on the avenue
	var stop: Dictionary = {}
	for st in SignalPlan.stops_for(loop):
		if SignalPlan.junctions()[int(st.j)].id == "Avenue-398": stop = st
	var junction: Dictionary = SignalPlan.junctions()[int(stop.j)]
	var mine: Array[Dictionary] = []
	for i in range(traffic.drivers.size()):
		if traffic.loop_of[i] == 3 and not VehicleCatalog.turns_tight(str(traffic.drivers[i].id)): mine.append(traffic.drivers[i])
	var lead: Dictionary = mine[0]
	var follow: Dictionary = mine[1]
	# The rest of this loop's vehicles (both corner variants) wait far down the loop.
	var k := 0
	for i in range(traffic.drivers.size()):
		var d: Dictionary = traffic.drivers[i]
		if traffic.loop_of[i] != 3 or d == lead or d == follow: continue
		var others: Array[Dictionary] = []
		for o: Dictionary in traffic.drivers: if o != d: others.append(o)
		d.s = TrafficDriver.free_spot(d.route, float(stop.s) + 150.0 + 55.0 * k, others, 10.0)
		d.speed = 0.0
		TrafficDriver.place(d)
		k += 1
	lead.s = float(stop.s) - float(lead.half) - 45.0
	lead.speed = 8.0
	follow.s = float(lead.s) - 22.0
	follow.speed = 8.0
	TrafficDriver.place(lead)
	TrafficDriver.place(follow)
	traffic.reorder()
	# Ns red at Avenue-398 (offset 18, red from 18 s of the 36 s cycle).
	traffic.elapsed = float(junction.offset) + 18.5
	check(SignalPlan.state(junction, "ns", traffic.elapsed) == SignalPlan.RED, "Test junction shows red")
	for f in range(60 * 12): await physics_frame
	var front_gap: float = float(stop.s) - (float(lead.s) + float(lead.half))
	check(front_gap >= -0.05 and front_gap < 3.0, "Car on red stops at the stop line (%.2f m before it)" % front_gap)
	check(float(lead.speed) < 0.05, "Car on red reaches a standstill (%.2f m/s)" % lead.speed)
	var queue_gap: float = float(lead.s) - float(lead.half) - (float(follow.s) + float(follow.half))
	check(queue_gap > 1.0 and queue_gap < 5.0, "Second car queues behind it (%.2f m gap)" % queue_gap)
	check(float(follow.speed) < 0.05, "Queued car waits")
	# Green: the queue clears the junction.
	traffic.elapsed = float(junction.offset) + 36.0
	for f in range(60 * 12): await physics_frame
	check(float(lead.s) + float(lead.half) > float(stop.exit), "Leader clears the junction on green")
	check(float(follow.s) > float(stop.exit), "Queued car clears the junction on green")
	# ---- whole-city soak: no deadlock, nobody held for good, nobody inside anybody ---------
	var all: Array[Dictionary] = []
	all.append_array(traffic.drivers)
	all.append_array(fleet.get("drivers"))
	var start: Array[float] = []
	var still: Array[float] = []
	var longest: Array[float] = []
	for d in all:
		start.append(float(d.s))
		still.append(0.0)
		longest.append(0.0)
	Engine.time_scale = 4.0
	Engine.max_fps = 30
	var sim := 0.0
	var overlaps := 0
	var worst := ""
	var next_sample := 5.0
	while sim < 300.0:
		await physics_frame
		var dt := 4.0 / Engine.physics_ticks_per_second
		sim += dt
		for i in range(all.size()):
			var d: Dictionary = all[i]
			if not (d.body as Node3D).visible: continue
			if float(d.speed) < 0.05: still[i] += dt
			else: still[i] = 0.0
			longest[i] = maxf(longest[i], still[i])
		if sim >= next_sample:
			next_sample += 5.0
			var o := overlap_pairs(all)
			overlaps += o.size()
			if not o.is_empty() and worst == "": worst = str(o)
	Engine.time_scale = 1.0
	Engine.max_fps = 0
	var stuck := 0
	var slowest := INF
	for i in range(all.size()):
		var d: Dictionary = all[i]
		if not (d.body as Node3D).visible: continue
		var moved := float(d.s) - start[i]
		slowest = minf(slowest, moved)
		if longest[i] > 130.0 or moved < 60.0:
			stuck += 1
			print("held: %s moved %.0f m, longest stop %.0f s at %s %s" % [(d.body as Node).name, moved, longest[i], StreetNames.describe((d.body as Node3D).position), why(d)])
	var mean := 0.0
	for i in range(all.size()): mean += float(all[i].s) - start[i]
	mean /= maxf(all.size(), 1)
	print("soak: %d vehicles, 300 s simulated, mean %.0f m, slowest %.0f m, longest stop %.0f s, %d overlaps %s" % [all.size(), mean, slowest, longest.max(), overlaps, worst])
	check(stuck == 0, "No vehicle held at a signal or in a queue for good (%d)" % stuck)
	check(overlaps == 0, "No two vehicles inside each other (%d)" % overlaps)
	check(mean > 400.0, "Traffic keeps flowing (mean %.0f m in 300 s)" % mean)
	print("TRAFFIC SIGNAL %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)

## What holds a vehicle: its signal state, the obstacle ahead and what its swept move touches.
func why(d: Dictionary) -> String:
	var body: CharacterBody3D = d.body
	var space := body.get_world_3d().direct_space_state
	var gap: Array = TrafficDriver.gap_ahead(d, 25.0, space, 5)
	var kc := KinematicCollision3D.new()
	var pose := (d.route as SmoothRoute).pose(float(d.s) + 0.1 - float(d.wheelbase) * 0.5, float(d.wheelbase))
	var touch := body.test_move(body.global_transform, Vector3(pose.position.x, 0.04, pose.position.z) - body.position, kc)
	var stop: Array = SignalPlan.next_stop(SignalPlan.stops_for(d.route), float(d.s) + float(d.half), (d.route as SmoothRoute).total)
	var jid: String = SignalPlan.junctions()[int(stop[0].j)].id if not (stop[0] as Dictionary).is_empty() else "-"
	return "(%.1f, %.1f) v=%.2f sig=%s next stop %s %.1f m, gap %.1f, touching %s; curve %.2f go %.2f/%.2f cruise %.1f s %.1f" % [body.position.x, body.position.z, d.speed, d.get("sig_state", -1), jid, float(stop[1]), float(gap[0]), (kc.get_collider() as Node).name if touch else "-", float(d.curve_v), float(d.go_t), float(d.react), float(d.cruise), float(d.s)]

## Pairs of vehicles whose footprints overlap by more than 5 cm (2D separating axis test).
func overlap_pairs(list: Array[Dictionary]) -> Array[String]:
	var out: Array[String] = []
	for a in range(list.size()):
		var A: Dictionary = list[a]
		var ba: Node3D = A.body
		if not ba.visible: continue
		for b in range(a + 1, list.size()):
			var B: Dictionary = list[b]
			var bb: Node3D = B.body
			if not bb.visible or ba.position.distance_to(bb.position) > 14.0: continue
			if obb_overlap(ba, A.size, bb, B.size): out.append("%s/%s" % [ba.name, bb.name])
	return out

func obb_overlap(a: Node3D, sa: Vector3, b: Node3D, sb: Vector3) -> bool:
	var axes: Array[Vector2] = []
	for n: Node3D in [a, b]:
		var x := n.global_basis.x
		var z := n.global_basis.z
		axes.append(Vector2(x.x, x.z).normalized())
		axes.append(Vector2(z.x, z.z).normalized())
	for ax in axes:
		var ra := proj(a, sa, ax)
		var rb := proj(b, sb, ax)
		var ca := Vector2(a.global_position.x, a.global_position.z).dot(ax)
		var cb := Vector2(b.global_position.x, b.global_position.z).dot(ax)
		if absf(ca - cb) > ra + rb - 0.05: return false
	return true

func proj(n: Node3D, size: Vector3, ax: Vector2) -> float:
	var x := Vector2(n.global_basis.x.x, n.global_basis.x.z).normalized()
	var z := Vector2(n.global_basis.z.x, n.global_basis.z.z).normalized()
	return absf(x.dot(ax)) * size.x * 0.5 + absf(z.dot(ax)) * size.z * 0.5
