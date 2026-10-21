extends SceneTree
## City prop placement audit (headless). Builds the whole world and checks that no prop stands
## on a road surface or in an AI traffic lane:
##   1. every small static collider (poles, lights, hydrants, bins, benches, signs, trees, stops,
##      cabinets...) against the carriageways, bike lanes, junction boxes, rings and forecourt
##      driveways of PropPlacer's road model (street grid, curved estate roads, roundabout
##      rings, downtown streets),
##   2. every small ground-standing visual instance (MeshInstance3D / MultiMesh instance) the
##      same way, by its world bounding box,
##   3. every PropPlacer registry entry (precise pole bases),
##   4. every collider the AI vehicles can hit (layers 1|4) against the AI routes (city traffic,
##      downtown traffic, civic fleet, buses) with the vehicle's half width,
##   5. a 60 s traffic run: no AI vehicle may end up permanently stopped by a static body.
## Offenders print with position, type and street name (StreetNames.describe).

var checks := 0
var failed := 0
## Kara Fatma Street road works close a lane on purpose (cones, barriers, warning sign).
const ROAD_WORKS := Rect2(-42.0, -538.6, 30.5, 4.6)
## Visual instances that are not street props.
const SKIP_ROOTS := ["CityTraffic", "CityLife", "Animals", "Weather", "CityVFX", "StreetVFX", "DowntownActivity", "CivicFleet",
	"TrafficCircles", "StreetGrid", "Restaurants"]

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

static func describe(at: Vector3) -> String:
	return "(%.1f, %.1f) %s" % [at.x, at.z, StreetNames.describe(at)]

## World footprint of a collision shape as a 2D polygon, plus its vertical extent.
static func shape_footprint(cs: CollisionShape3D) -> Dictionary:
	var xf := cs.global_transform
	var poly := PackedVector2Array()
	var y0 := 0.0
	var y1 := 0.0
	var shape := cs.shape
	if shape is BoxShape3D:
		var h: Vector3 = (shape as BoxShape3D).size * 0.5
		for c: Vector3 in [Vector3(-h.x, 0, -h.z), Vector3(h.x, 0, -h.z), Vector3(h.x, 0, h.z), Vector3(-h.x, 0, h.z)]:
			var w: Vector3 = xf * c
			poly.append(Vector2(w.x, w.z))
		var ys: Array[float] = []
		for c: Vector3 in [Vector3(-h.x, -h.y, -h.z), Vector3(h.x, h.y, h.z), Vector3(-h.x, h.y, h.z), Vector3(h.x, -h.y, -h.z)]:
			ys.append((xf * c).y)
		y0 = ys.min()
		y1 = ys.max()
	elif shape is CylinderShape3D or shape is CapsuleShape3D or shape is SphereShape3D:
		var r := 0.0
		var hh := 0.0
		if shape is CylinderShape3D:
			r = (shape as CylinderShape3D).radius
			hh = (shape as CylinderShape3D).height * 0.5
		elif shape is CapsuleShape3D:
			r = (shape as CapsuleShape3D).radius
			hh = (shape as CapsuleShape3D).height * 0.5
		else:
			r = (shape as SphereShape3D).radius
			hh = r
		var scale := xf.basis.get_scale()
		r *= maxf(scale.x, scale.z)
		var o := xf.origin
		for k in range(8):
			var a := TAU * k / 8.0
			poly.append(Vector2(o.x + cos(a) * r, o.z + sin(a) * r))
		y0 = o.y - hh * scale.y
		y1 = o.y + hh * scale.y
	else:
		return {}
	return {"poly": poly, "y0": y0, "y1": y1}

static func poly_size(poly: PackedVector2Array) -> Vector2:
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for p in poly:
		lo = lo.min(p)
		hi = hi.max(p)
	return hi - lo

static func poly_centre(poly: PackedVector2Array) -> Vector2:
	var c := Vector2.ZERO
	for p in poly: c += p
	return c / poly.size()

## Road surface (strict kinds) under any of the polygon's corners, edge midpoints or centre.
static func road_under(poly: PackedVector2Array) -> Dictionary:
	var centre := poly_centre(poly)
	var samples: Array[Vector2] = [centre]
	for i in range(poly.size()):
		var a := poly[i]
		var b := poly[(i + 1) % poly.size()]
		samples.append(a.lerp(centre, 0.04))
		samples.append(a.lerp(b, 0.5).lerp(centre, 0.04))
	for p in samples:
		var hit := PropPlacer.surface_at(p, 0.0)
		if not hit.is_empty(): return hit
	return {}

var _bases: Dictionary = {}
## The ground contact of a mesh: bounds of its vertices within 0.3 m of its lowest point (pole
## base, trunk, post, bench feet) - tall props overhang the kerb above head height by design.
## Without vertex data (headless) the whole bounding box is used.
func base_aabb(mesh: Mesh) -> AABB:
	var key := mesh.get_rid()
	if _bases.has(key): return _bases[key]
	var whole := mesh.get_aabb()
	var box := whole
	var found := false
	for s in range(mesh.get_surface_count() if DisplayServer.get_name() != "headless" else 0):
		var arrays := mesh.surface_get_arrays(s)
		if arrays.is_empty() or arrays[Mesh.ARRAY_VERTEX] == null: continue
		for v: Vector3 in (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array):
			if v.y > whole.position.y + 0.3: continue
			if not found:
				box = AABB(v, Vector3.ZERO)
				found = true
			else: box = box.expand(v)
	if found: box.size.y = maxf(box.size.y, 0.01)
	_bases[key] = box
	return box

func label_for(node: Node) -> String:
	var n: Node = node
	for i in range(4):
		if n == null: break
		if n.has_meta("prop"): return str(n.get_meta("prop"))
		n = n.get_parent()
	var path := str(node.get_path())
	return path.substr(path.find("CedarNeighborhood") if path.contains("CedarNeighborhood") else 0).replace("/root/", "")

func skipped(node: Node, world: Node) -> bool:
	var n := node
	while n != null and n != world:
		if n is CharacterBody3D or n is RigidBody3D or n is VehicleBody3D or n is AnimatableBody3D: return true
		if n.get_parent() == world and str(n.name) in SKIP_ROOTS: return true
		# Buses: only the stop furniture (TransitProps) is street furniture, not the buses.
		if n.get_parent() == world and str(n.name) == "Buses" and not str(node.get_path()).contains("TransitProps"): return true
		n = n.get_parent()
	return false

func run() -> void:
	var t0 := Time.get_ticks_msec()
	var world := CedarNeighborhood.new()
	world.name = "CedarNeighborhood"
	root.add_child(world)
	for i in range(3): await process_frame
	print("world built in %d ms" % (Time.get_ticks_msec() - t0))
	# ---- 1. colliders -----------------------------------------------------------------------
	var colliders: Array[Dictionary] = []   # {"cs", "poly", "y0", "y1", "body"}
	for node in world.find_children("*", "CollisionShape3D", true, false):
		var cs := node as CollisionShape3D
		if cs.disabled or cs.shape == null: continue
		var body := cs.get_parent()
		if not body is StaticBody3D or body is AnimatableBody3D: continue   # buses are animatable
		var fp := shape_footprint(cs)
		if fp.is_empty(): continue
		fp.cs = cs
		fp.body = body
		colliders.append(fp)
	var collider_offenders: Array[String] = []
	var tested := 0
	for fp in colliders:
		var body: StaticBody3D = fp.body
		if str(body.get_path()).contains("TrafficCircle"): continue   # the islands are the circle
		var size := poly_size(fp.poly)
		if maxf(size.x, size.y) > 4.5 or float(fp.y1) - float(fp.y0) < 0.25 or float(fp.y0) > 0.8 or float(fp.y1) < 0.2: continue
		tested += 1
		var centre := poly_centre(fp.poly)
		if ROAD_WORKS.has_point(centre): continue
		var hit := road_under(fp.poly)
		if not hit.is_empty():
			var at := Vector3(centre.x, 0, centre.y)
			collider_offenders.append("OFFENDER collider %s %.2fx%.2f m on %s %s at %s" % [label_for(fp.cs), size.x, size.y, hit.kind, hit.id, describe(at)])
	for line in collider_offenders: print(line)
	print("colliders: %d prop colliders tested, %d on a road surface" % [tested, collider_offenders.size()])
	check(collider_offenders.is_empty(), "No prop collider on a carriageway / bike lane / junction / ring / driveway (%d)" % collider_offenders.size())
	# ---- 2. visuals -------------------------------------------------------------------------
	var visual_offenders: Dictionary = {}
	var visuals := 0
	# The headless (dummy) renderer keeps no MultiMesh instance data: there, batched instances are
	# covered by their colliders and the PropPlacer registry; run with rendering for all of them.
	var multimesh_data := DisplayServer.get_name() != "headless"
	if not multimesh_data: print("visuals: headless run, MultiMesh instances skipped (run without --headless to include them)")
	for node in world.find_children("*", "GeometryInstance3D", true, false):
		if not (node is MeshInstance3D or (node is MultiMeshInstance3D and multimesh_data)): continue
		var gi := node as GeometryInstance3D
		if not gi.is_visible_in_tree() or skipped(gi, world): continue
		if gi is MultiMeshInstance3D and (gi as MultiMeshInstance3D).visibility_range_begin > 0.0: continue
		var mesh: Mesh = (gi as MeshInstance3D).mesh if gi is MeshInstance3D else ((gi as MultiMeshInstance3D).multimesh.mesh if (gi as MultiMeshInstance3D).multimesh != null else null)
		if mesh == null: continue
		var whole := mesh.get_aabb()
		if whole.size.y < 0.3: continue
		var asset := label_for(gi)
		if asset.begins_with("reuse_") and asset.substr(6) in CityAssets.CAR_TYPES: continue   # parked cars
		if asset.contains("cycle_separator"): continue   # flexible posts dividing the cycle track, by design
		var local := base_aabb(mesh)
		var xforms: Array[Transform3D] = []
		if gi is MeshInstance3D: xforms.append(gi.global_transform)
		else:
			var mm := (gi as MultiMeshInstance3D).multimesh
			for k in range(mm.instance_count): xforms.append(gi.global_transform * mm.get_instance_transform(k))
		for xf in xforms:
			if (xf * whole).position.y > 0.6: continue   # not standing on the ground
			var box := xf * local
			if box.size.x > 3.2 or box.size.z > 3.2: continue
			visuals += 1
			var poly := PackedVector2Array([Vector2(box.position.x, box.position.z), Vector2(box.end.x, box.position.z),
				Vector2(box.end.x, box.end.z), Vector2(box.position.x, box.end.z)])
			var centre := poly_centre(poly)
			if ROAD_WORKS.has_point(centre): continue
			var hit := road_under(poly)
			if hit.is_empty(): continue
			var key := "%s|%s|%d_%d" % [label_for(gi), mesh.resource_name, roundi(centre.x), roundi(centre.y)]
			visual_offenders[key] = "OFFENDER visual %s (%s) %.2fx%.2f m on %s %s at %s" % [label_for(gi), mesh.resource_name, box.size.x, box.size.z, hit.kind, hit.id, describe(Vector3(centre.x, 0, centre.y))]
	for key in visual_offenders: print(visual_offenders[key])
	print("visuals: %d ground-standing prop instances tested, %d on a road surface" % [visuals, visual_offenders.size()])
	check(visual_offenders.is_empty(), "No ground-standing prop mesh on a road surface (%d)" % visual_offenders.size())
	# ---- 3. placer registry -----------------------------------------------------------------
	var placer: PropPlacer = world.get("placer")
	if placer != null:
		var bad := 0
		for rec in placer.records:
			if rec.flat or ROAD_WORKS.has_point(Vector2(rec.at.x, rec.at.z)): continue
			var hit := PropPlacer.surface_at(Vector2(rec.at.x, rec.at.z), float(rec.radius))
			if not hit.is_empty():
				bad += 1
				print("OFFENDER placed %s r=%.2f on %s %s at %s" % [rec.kind, rec.radius, hit.kind, hit.id, describe(rec.at)])
		var kinds := {}
		for rec in placer.records: kinds[rec.kind] = int(kinds.get(rec.kind, 0)) + 1
		print("placer: %d placements %s, %d relocated, %d dropped" % [placer.records.size(), kinds, placer.relocated, placer.rejected.size()])
		for rec in placer.records:
			if rec.has("from"): print("  relocated %s %.1f m (%s) from %s" % [rec.kind, (rec.from as Vector3).distance_to(rec.at), rec.why, describe(rec.from)])
		for rej in placer.rejected: print("  dropped %s (%s) at %s" % [rej.kind, rej.reason, describe(rej.at)])
		var curved := world.find_child("CurvedRoads", true, false)
		if curved != null: print("curved-road lights: %d placed of %d regular spots" % [int(curved.get_meta("street_lights", 0)), int(curved.get_meta("street_lights_requested", 0))])
		check(bad == 0, "Every PropPlacer placement is off the carriageway (%d)" % bad)
		check(placer.records.size() > 300, "PropPlacer placed the city props (%d)" % placer.records.size())
	else:
		check(false, "CedarNeighborhood exposes its PropPlacer")
	# ---- 4. AI lanes ------------------------------------------------------------------------
	var routes: Array[Dictionary] = []   # {"name", "points": PackedVector3Array, "half"}
	var traffic := world.get_node_or_null("CityTraffic")
	if traffic != null:
		for car: Dictionary in traffic.drivers:
			routes.append({"name": str((car.body as Node).name), "points": (car.route as SmoothRoute).points, "half": float((car.size as Vector3).x) * 0.5})
	var population: Node = world.downtown.population if world.downtown != null else null
	if population != null:
		for car: Dictionary in population.vehicles:
			routes.append({"name": str((car.body as Node).name), "points": (car.route as SmoothRoute).points, "half": float((car.size as Vector3).x) * 0.5})
		var fleet := population.get_node_or_null("CivicFleet")
		if fleet != null:
			for car: Dictionary in fleet.fleet:
				routes.append({"name": str((car.body as Node).name), "points": (car.route as SmoothRoute).points, "half": float((car.size as Vector3).x) * 0.5})
			# Downtown street traffic (driven by CivicFleet since the street-life pass).
			for car: Dictionary in fleet.get("drivers"):
				routes.append({"name": str((car.body as Node).name), "points": (car.route as SmoothRoute).points, "half": float((car.size as Vector3).x) * 0.5})
	if world.buses != null:
		for line: Dictionary in world.buses.lines:
			var pts: PackedVector3Array = (line.path as PackedVector3Array).duplicate()
			pts.append(pts[0])
			routes.append({"name": "Bus line %s" % line.number, "points": pts, "half": BusSystem.WIDTH * 0.5})
	# Spatial hash of route segments (8 m cells), deduplicated per route.
	var seen_routes := {}
	var seg_grid := {}
	var segs: Array[Array] = []   # [a: Vector2, b: Vector2, half, name]
	for r in routes:
		var pts: PackedVector3Array = r.points
		var key := "%d_%.1f_%.1f" % [pts.size(), pts[0].x, pts[0].z]
		if seen_routes.has(key): continue
		seen_routes[key] = true
		for i in range(1, pts.size()):
			var a := Vector2(pts[i - 1].x, pts[i - 1].z)
			var b := Vector2(pts[i].x, pts[i].z)
			segs.append([a, b, float(r.half), str(r.name)])
			var lo := a.min(b)
			var hi := a.max(b)
			for gx in range(floori(lo.x / 8.0), floori(hi.x / 8.0) + 1):
				for gz in range(floori(lo.y / 8.0), floori(hi.y / 8.0) + 1):
					var cell := Vector2i(gx, gz)
					if not seg_grid.has(cell): seg_grid[cell] = []
					seg_grid[cell].append(segs.size() - 1)
	var lane_offenders: Dictionary = {}
	for fp in colliders:
		var body: StaticBody3D = fp.body
		if body.collision_layer & 5 == 0: continue
		if float(fp.y1) < 0.3 or float(fp.y0) > 2.2: continue
		var poly: PackedVector2Array = fp.poly
		var size := poly_size(poly)
		var centre := poly_centre(poly)
		var reach := maxf(size.x, size.y) * 0.5 + 4.0
		var cells := {}
		for gx in range(floori((centre.x - reach) / 8.0), floori((centre.x + reach) / 8.0) + 1):
			for gz in range(floori((centre.y - reach) / 8.0), floori((centre.y + reach) / 8.0) + 1):
				for idx: int in seg_grid.get(Vector2i(gx, gz), []): cells[idx] = true
		for idx: int in cells:
			var s: Array = segs[idx]
			var d := INF
			if Geometry2D.is_point_in_polygon(s[0], poly) or Geometry2D.is_point_in_polygon(s[1], poly): d = 0.0
			else:
				for i in range(poly.size()):
					var pts := Geometry2D.get_closest_points_between_segments(s[0], s[1], poly[i], poly[(i + 1) % poly.size()])
					d = minf(d, pts[0].distance_to(pts[1]))
			if d < float(s[2]) + 0.15:
				var key := "%d_%d" % [roundi(centre.x * 2), roundi(centre.y * 2)]
				lane_offenders[key] = "OFFENDER lane collider %s %.2fx%.2f m %.2f m from %s path at %s" % [label_for(fp.cs), size.x, size.y, d, s[3], describe(Vector3(centre.x, 0, centre.y))]
				break
	for key in lane_offenders: print(lane_offenders[key])
	print("lanes: %d AI routes (%d segments) checked against %d colliders, %d obstructions" % [seen_routes.size(), segs.size(), colliders.size(), lane_offenders.size()])
	check(lane_offenders.is_empty(), "No static collider inside an AI vehicle's swept lane (%d)" % lane_offenders.size())
	# ---- 5. traffic flow --------------------------------------------------------------------
	var drivers: Array[Dictionary] = []
	if traffic != null: for car: Dictionary in traffic.drivers: drivers.append(car)
	if population != null:
		for car: Dictionary in population.vehicles: drivers.append(car)
		var civic := population.get_node_or_null("CivicFleet")
		if civic != null:
			for car: Dictionary in civic.fleet: drivers.append(car)
			for car: Dictionary in civic.get("drivers"): drivers.append(car)
	# 4x time; cap the frame rate so the run stays well inside run_tests.ps1's --quit-after frames.
	Engine.time_scale = 4.0
	Engine.max_fps = 30
	var start_s: Array[float] = []
	var mid_s: Array[float] = []
	for car in drivers: start_s.append(float(car.s))
	var sim_start := Time.get_ticks_msec()
	var simulated := 0.0
	while simulated < 60.0:
		await physics_frame
		simulated += 4.0 / Engine.physics_ticks_per_second
		if mid_s.is_empty() and simulated >= 30.0:
			for car in drivers: mid_s.append(float(car.s))
	Engine.time_scale = 1.0
	Engine.max_fps = 0
	var space := world.get_world_3d().direct_space_state
	var stuck := 0
	var moved := 0.0
	for i in range(drivers.size()):
		var car: Dictionary = drivers[i]
		var progress := float(car.s) - mid_s[i]
		moved += float(car.s) - start_s[i]
		if progress > 4.0: continue
		var body: CharacterBody3D = car.body
		var dir := TrafficDriver.heading(car)
		var side := dir.cross(Vector3.UP).normalized()
		var blocker := "nothing ahead"
		var static_block := false
		for offset in [-0.7, 0.0, 0.7]:
			var origin: Vector3 = body.global_position + Vector3.UP * 0.8 + side * float(offset)
			var query := PhysicsRayQueryParameters3D.create(origin, origin + dir * (float(car.half) + 8.0), 5, [body.get_rid()])
			var hit := space.intersect_ray(query)
			if hit.is_empty(): continue
			var collider: Object = hit.collider
			if collider is StaticBody3D:
				static_block = true
				blocker = "static %s" % label_for(collider as Node)
			elif blocker == "nothing ahead": blocker = "vehicle %s" % (collider as Node).name
		# The swept move (test_move) also stops a car: what does it touch just ahead?
		var touch := KinematicCollision3D.new()
		if body.test_move(body.global_transform, dir * 0.4, touch) and touch.get_collider() is StaticBody3D and not touch.get_collider() is AnimatableBody3D:
			static_block = true
			blocker = "static (swept) %s" % label_for(touch.get_collider() as Node)
		if static_block:
			stuck += 1
			print("OFFENDER traffic %s stopped %.1f m in 30 s, blocked by %s at %s" % [body.name, progress, blocker, describe(body.global_position)])
		else:
			print("note: %s moved %.1f m in the last 30 s (%s) at %s" % [body.name, progress, blocker, describe(body.global_position)])
	print("traffic: %d vehicles, %.1f s simulated in %d ms, mean %.0f m travelled, %d stopped by a static body" % [drivers.size(), simulated, Time.get_ticks_msec() - sim_start, moved / maxf(drivers.size(), 1), stuck])
	check(stuck == 0, "No AI vehicle permanently stopped by a static prop (%d)" % stuck)
	check(moved / maxf(drivers.size(), 1) > 120.0, "Traffic flows (mean %.0f m in 60 s)" % (moved / maxf(drivers.size(), 1)))
	print("frames: %d" % Engine.get_process_frames())
	print("PROP PLACEMENT %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)
