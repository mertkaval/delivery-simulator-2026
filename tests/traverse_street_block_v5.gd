extends SceneTree
## Swept traversal of a Road Studio street-block export through Godot physics (no tolerance tricks):
## a pedestrian capsule, a cyclist capsule and a car box are moved along every route / movement path
## with kinematic body_test_motion steps (lift by the allowed step, move horizontally, drop to the floor).
## A step is a FAILURE when the horizontal move is blocked by a steep surface, when no floor is found
## within the drop distance (a gap), or when the floor rises more than the allowed step (kerb, seam).
## Also re-probes the v4 ray misses with nearby samples. Writes <out>/traversal.json.
## usage: godot --headless --path . --script res://tests/traverse_street_block_v5.gd -- <export_dir> <out_dir>
const StreetBlock := preload("res://world/roads/mrs_street_block.gd")

## body kind -> [shape radius or half width, height, allowed step up (m), drop search (m), max floor slope deg]
const BODIES := {"ped": [0.28, 1.75, 0.20, 0.6, 50.0], "bike": [0.30, 1.6, 0.045, 0.4, 25.0], "car": [0.95, 1.4, 0.07, 0.4, 20.0]}

var block: StreetBlock
var space: PhysicsDirectSpaceState3D

func _initialize() -> void:
	call_deferred("run")

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

func make_body(kind: String) -> CharacterBody3D:
	var b := CharacterBody3D.new()
	var cs := CollisionShape3D.new()
	var spec: Array = BODIES[kind]
	if kind == "car":
		var bx := BoxShape3D.new()
		bx.size = Vector3(float(spec[0]) * 2.0, float(spec[1]) - 0.12, 4.4)
		cs.shape = bx
		cs.position = Vector3(0, 0.12 + (float(spec[1]) - 0.12) * 0.5, 0)     # 0.12 m ground clearance: kerbs and medians are felt
	else:
		var cap := CapsuleShape3D.new()
		cap.radius = float(spec[0])
		cap.height = float(spec[1])
		cs.shape = cap
		cs.position = Vector3(0, float(spec[1]) * 0.5, 0)
	b.add_child(cs)
	b.collision_mask = 1
	root.add_child(b)
	return b

## Floor height under p (ray from above), or NAN.
func floor_at(p: Vector3, up: float = 1.5, down: float = 3.0) -> float:
	var q := PhysicsRayQueryParameters3D.create(p + Vector3(0, up, 0), p - Vector3(0, down, 0))
	var hit := space.intersect_ray(q)
	return NAN if hit.is_empty() else float((hit["position"] as Vector3).y)

## Moves `body` along pts (Godot coords). Returns {ok, fails[], max_step, max_drop, length}.
func sweep(body: CharacterBody3D, kind: String, pts: Array[Vector3]) -> Dictionary:
	var spec: Array = BODIES[kind]
	var step_up: float = float(spec[2]); var drop: float = float(spec[3])
	var fails: Array = []
	var max_step := 0.0; var max_drop := 0.0; var length := 0.0
	var step_at := Vector3.ZERO
	var start := pts[0]
	var f0 := floor_at(start)
	if is_nan(f0):
		return {"ok": false, "fails": ["no floor at the start"], "max_step": 0.0, "max_drop": 0.0, "length": 0.0}
	body.global_position = Vector3(start.x, f0 + 0.002, start.z)
	body.move_and_collide(Vector3(0, -(drop + 0.2), 0), false, 0.001, true)     # settle (the car box rides 0.12 m above its origin)
	var last_floor := body.global_position.y
	for i in range(1, pts.size()):
		var a := pts[i - 1]; var b := pts[i]
		var seg := Vector3(b.x - a.x, 0, b.z - a.z)
		var L := seg.length()
		if L < 1e-4: continue
		var n := int(ceil(L / 0.2))
		var dir := seg / L
		if kind == "car":
			body.global_basis = Basis.looking_at(dir, Vector3.UP)
		for k in range(n):
			var mv := seg / float(n)
			# 1. lift by the allowed step, 2. horizontal move, 3. drop back onto the floor
			var up_col := body.move_and_collide(Vector3(0, step_up, 0), false, 0.001, true)
			var col := body.move_and_collide(mv, false, 0.001, true)
			if col != null and col.get_normal().y < cos(deg_to_rad(float(spec[4]))):
				fails.append("blocked at %s (normal %s)" % [str(body.global_position.snapped(Vector3.ONE * 0.01)), str(col.get_normal().snapped(Vector3.ONE * 0.01))])
				body.global_position += mv - col.get_travel()     # skip past to keep measuring the rest of the path
			var down := body.move_and_collide(Vector3(0, -(step_up + drop), 0), false, 0.001, true)
			if down == null:
				fails.append("gap / no floor within %.2f m at %s" % [drop, str(body.global_position.snapped(Vector3.ONE * 0.01))])
				var fz := floor_at(body.global_position)
				if not is_nan(fz): body.global_position.y = fz + 0.002
			var fl := body.global_position.y
			var dz := fl - last_floor
			if dz > max_step:
				max_step = dz; step_at = body.global_position
			if -dz > max_drop: max_drop = -dz
			last_floor = fl
			length += mv.length()
			if fails.size() > 6: break
		if fails.size() > 6: break
	return {"ok": fails.is_empty(), "fails": fails, "max_step": snappedf(max_step, 0.001), "max_drop": snappedf(max_drop, 0.001), "length": snappedf(length, 0.1), "step_at": [snappedf(step_at.x, 0.01), snappedf(-step_at.z, 0.01), snappedf(step_at.y, 0.01)]}

## Fine lip scan: floor height every 5 cm along the polyline (rays from 1.5 m above the path point); the
## largest jump between neighbouring samples is a real surface discontinuity (kerb lip, seam step, slab edge).
func lip_scan(pts: Array[Vector3]) -> Dictionary:
	var worst := 0.0; var at := Vector3.ZERO; var last := NAN; var misses := 0
	var total := 0.0
	for i in range(1, pts.size()): total += Vector2(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z).length()
	var run := 0.0
	for i in range(1, pts.size()):
		var a := pts[i - 1]; var b := pts[i]
		var L := Vector2(b.x - a.x, b.z - a.z).length()
		var n := maxi(1, int(ceil(L / 0.05)))
		for k in range(n):
			var dist := run + L * float(k) / float(n)
			if dist < 0.25 or dist > total - 0.25: continue      # the end points sit on open edges (block boundary, landings)
			var q := a.lerp(b, float(k) / float(n))
			var z := floor_at(q, 1.5, 3.0)
			if is_nan(z):
				misses += 1; continue
			if not is_nan(last) and absf(z - last) > worst:
				worst = absf(z - last); at = q
			last = z
		run += L
	return {"max_lip": snappedf(worst, 0.001), "at (blender xyz)": [snappedf(at.x, 0.01), snappedf(-at.z, 0.01), snappedf(at.y, 0.01)], "misses": misses}

func pts_of(arr: Array) -> Array[Vector3]:
	var out: Array[Vector3] = []
	for p: Variant in arr: out.append(g(p as Array))
	return out

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var dir: String = args[0] if args.size() > 0 else "res://tmp/roads/v5/block/export"
	var out: String = args[1] if args.size() > 1 else "res://tmp/roads/v5/traversal"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out) if out.begins_with("res://") else out)
	block = StreetBlock.new()
	root.add_child(block)
	block.build(dir, "street_block", {"lights": false})
	for i in 3: await physics_frame
	space = root.world_3d.direct_space_state
	var model: Dictionary = block.model
	var report: Dictionary = {"ped": {}, "bike": {}, "car": {}, "probes": []}
	# --- pedestrians: every walking edge of the route graph (sidewalks, corners, crossings, ramps, paths, footbridge)
	var ped := make_body("ped")
	var routes: Dictionary = model.get("routes", {}) as Dictionary
	# --- lips: every walking edge except stairs, every cycle path and every vehicle path, scanned at 5 cm
	var lips: Array = []
	var scan := func(id: String, kind: String, arr: Array) -> void:
		var pp := pts_of(arr)
		if pp.size() < 2: return
		var r := lip_scan(pp)
		r["id"] = id; r["kind"] = kind
		lips.append(r)
	for e: Variant in (routes.get("ped", {}) as Dictionary).get("edges", []) as Array:
		var ed: Dictionary = e as Dictionary
		if str(ed.get("kind", "")) != "footbridge_stairs": scan.call(str(ed.get("id", "")), str(ed.get("kind", "")), ed.get("points", []) as Array)
	var mvd: Dictionary = model.get("movements", {}) as Dictionary
	for key: String in ["movements", "bike_movements", "lanes"]:
		for e: Variant in mvd.get(key, []) as Array:
			var ed: Dictionary = e as Dictionary
			scan.call(str(ed.get("id", "")), key, ed.get("points", []) as Array)
	lips.sort_custom(func(x: Variant, y: Variant) -> bool: return float((x as Dictionary)["max_lip"]) > float((y as Dictionary)["max_lip"]))
	var over: Array = lips.filter(func(x: Variant) -> bool: return float((x as Dictionary)["max_lip"]) > 0.02)
	report["lips"] = {"paths": lips.size(), "over_2cm": over.size(), "largest": lips.slice(0, 8)}
	print("LIPS ", lips.size(), " paths scanned at 5 cm, ", over.size(), " with a jump > 2 cm")
	for x: Variant in lips.slice(0, 6): print("   lip ", x)
	var ped_res: Array = []
	for e: Variant in (routes.get("ped", {}) as Dictionary).get("edges", []) as Array:
		var ed: Dictionary = e as Dictionary
		var pts := pts_of(ed.get("points", []) as Array)
		if pts.size() < 2: continue
		var r := sweep(ped, "ped", pts)
		r["id"] = ed.get("id", ""); r["kind"] = ed.get("kind", "")
		ped_res.append(r)
	# --- cyclists: cycleways + junction bike movements
	var bike := make_body("bike")
	var bike_res: Array = []
	for e: Variant in (routes.get("bike", {}) as Dictionary).get("edges", []) as Array:
		var ed: Dictionary = e as Dictionary
		if str(ed.get("kind", "")) in ["mixed_traffic", "dismount_link"] or str(ed.get("geometry", "")) == "link": continue    # graph links, not ridden paths
		var pts := pts_of(ed.get("points", []) as Array)
		if pts.size() < 2: continue
		var r := sweep(bike, "bike", pts)
		r["id"] = ed.get("id", ""); r["kind"] = ed.get("kind", "")
		bike_res.append(r)
	var mv: Dictionary = model.get("movements", {}) as Dictionary
	for e: Variant in mv.get("bike_movements", []) as Array:
		var ed: Dictionary = e as Dictionary
		var r := sweep(bike, "bike", pts_of(ed.get("points", []) as Array))
		r["id"] = ed.get("id", ""); r["kind"] = "bike_movement"
		bike_res.append(r)
	# --- cars: every lane (full length) and every junction movement
	var car := make_body("car")
	var car_res: Array = []
	for e: Variant in mv.get("lanes", []) as Array:
		var ed: Dictionary = e as Dictionary
		var r := sweep(car, "car", pts_of(ed.get("points", []) as Array))
		r["id"] = ed.get("id", ""); r["kind"] = "lane"
		car_res.append(r)
	for e: Variant in mv.get("movements", []) as Array:
		var ed: Dictionary = e as Dictionary
		var r := sweep(car, "car", pts_of(ed.get("points", []) as Array))
		r["id"] = ed.get("id", ""); r["kind"] = "movement_" + str(ed.get("turn", ""))
		car_res.append(r)
	for pair: Array in [["ped", ped_res], ["bike", bike_res], ["car", car_res]]:
		var res: Array = pair[1]
		var bad: Array = []
		var mstep := 0.0
		for r: Variant in res:
			var rd: Dictionary = r as Dictionary
			mstep = maxf(mstep, float(rd["max_step"]))
			if not bool(rd["ok"]): bad.append({"id": rd["id"], "kind": rd["kind"], "fails": rd["fails"]})
		var ranked := res.duplicate()
		ranked.sort_custom(func(x: Variant, y: Variant) -> bool: return float((x as Dictionary)["max_step"]) > float((y as Dictionary)["max_step"]))
		var top: Array = []
		for r: Variant in ranked.slice(0, 5):
			var rd: Dictionary = r as Dictionary
			top.append({"id": rd["id"], "kind": rd["kind"], "max_step": rd["max_step"], "at (blender xyz)": rd["step_at"]})
		report[pair[0]] = {"paths": res.size(), "ok": res.size() - bad.size(), "max_step": mstep, "largest_steps": top, "failures": bad}
		print("TRAVERSE ", pair[0], ": ", res.size() - bad.size(), "/", res.size(), " ok, max step ", snappedf(mstep, 0.001))
		for b: Variant in bad.slice(0, 8): print("   FAIL ", b)
		for t: Variant in top: print("   step ", t)
	# --- the v4 ray misses, with nearby samples (exact edge vs gap)
	var probes: Array = [Vector3(106.6, 0.1, -15.5), Vector3(106.6, 0.1, 15.5), Vector3(-6.8, 0.1, -17.7), Vector3(-70.4, -0.09, 65.2)]
	for p: Vector3 in probes:
		var row: Array = []
		for off: float in [-0.05, -0.01, 0.0, 0.01, 0.05]:
			for ax: int in [0, 2]:
				var q := p
				q[ax] += off
				row.append("%s%+.2f:%s" % ["x" if ax == 0 else "z", off, "hit" if not is_nan(floor_at(q)) else "MISS"])
		report["probes"].append({"at": str(p), "samples": row})
		print("PROBE ", p, " ", row)
	var f := FileAccess.open(out.path_join("traversal.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	print("TRAVERSE DONE")
	quit(0)
