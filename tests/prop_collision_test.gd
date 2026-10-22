extends SceneTree
## Prop collision in the real world (app_root.tscn): the courier cannot walk (or ride) through
## the city's props, while every path he needs stays open and the E ray still reaches its targets.
##   1. pushes the courier into a white picket fence, a hedge, an avenue bench, a litter bin, the
##      yard bins, a street-light pole, a tree trunk, a mailbox, downtown café chairs / benches /
##      lamps, a park rock and Cedar House furniture; and rides the bicycle into a lamp pole;
##   2. walks the key routes: a sidewalk run along Cedar Lane, from the sidewalk to the door of every
##      Cedar Lane delivery house (where the drop zone appears), into every corridor restaurant to its
##      pickup shelf, into the avenue restaurants, through the Cedar House front door into the hall,
##      into the stores to their computers; and checks the spawn / bike / shop spots are free;
##   3. aims the E ray at pickup shelves, doors, store computers and the REST plaque;
##   4. reports the prop collider counts per layer and the physics time while walking.
## godot --headless --path . --script res://tests/prop_collision_test.gd
var failures := 0
var checks := 0
var game: Node
var player: CourierPlayer
var world: CedarNeighborhood
var physics_samples: Array[float] = []
## Optional sections to run (user args): block, bike, sidewalk, doors, restaurants, cedar, stores,
## downtown, spots.
var only: PackedStringArray = OS.get_cmdline_user_args()

func want(section: String) -> bool:
	return only.is_empty() or only.has(section)

func check(ok: bool, what: String) -> void:
	checks += 1
	if ok: print("PASS " + what)
	else:
		failures += 1
		print("FAIL: " + what)

func _initialize() -> void: call_deferred("run")

func ticks(n: int) -> void:
	for i in range(n): await physics_frame
	await process_frame

static func flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0.0, v.z)

func face(dir: Vector3) -> void:
	var d := flat(dir)
	if d.length() < 0.001: return
	player.rotation = Vector3(0, atan2(-d.x, -d.z), 0)
	player.camera.rotation = Vector3(-0.15, 0, 0)

func place(at: Vector3) -> void:
	player.velocity = Vector3.ZERO
	player.position = at + Vector3(0, 0.1, 0)
	player.camera.rotation = Vector3(-0.15, 0, 0)
	player.reset_physics_interpolation()

func capsule_free(at: Vector3) -> bool:
	var q := PhysicsShapeQueryParameters3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 1.8
	q.shape = cap
	q.transform = Transform3D(Basis.IDENTITY, at + Vector3(0, 0.98, 0))
	q.collision_mask = player.collision_mask
	q.exclude = [player.get_rid()]
	return player.get_world_3d().direct_space_state.intersect_shape(q, 1).is_empty()

## What the courier's capsule would touch 0.25 m further along `dir` (names, layers, prop tags).
func what_blocks(dir: Vector3) -> String:
	var q := PhysicsShapeQueryParameters3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.32
	cap.height = 1.8
	q.shape = cap
	q.transform = Transform3D(Basis.IDENTITY, player.global_position + dir * 0.25 + Vector3(0, 0.95, 0))
	q.collision_mask = player.collision_mask
	q.exclude = [player.get_rid()]
	var out: Array[String] = []
	for hit in player.get_world_3d().direct_space_state.intersect_shape(q, 8):
		var c := hit.collider as CollisionObject3D
		var owner_id: int = c.shape_find_owner(int(hit.shape)) if c != null else -1
		var shape_node := c.shape_owner_get_owner(owner_id) as Node if owner_id >= 0 else null
		var tag := str(shape_node.get_meta("prop", c.get_meta("prop", ""))) if shape_node != null else ""
		var at := (shape_node as Node3D).global_position if shape_node is Node3D else c.global_position
		out.append("%s/%s layer %d tag '%s' at (%.2f, %.2f, %.2f)" % [c.get_parent().name, c.name, c.collision_layer, tag, at.x, at.y, at.z])
	return ", ".join(out) if not out.is_empty() else "nothing (steps / slope?)"

## Push the courier from `start` towards `centre` for `seconds`; true when he stopped short of it.
func blocked(label: String, start: Vector3, centre: Vector3, seconds: float = 1.8) -> void:
	place(start)
	var dir := flat(centre - start).normalized()
	face(dir)
	await ticks(2)
	Input.action_press("move_forward")
	for i in range(int(seconds * 60.0)):
		face(dir)
		await physics_frame
	Input.action_release("move_forward")
	await ticks(2)
	var reach := flat(centre - start).length()
	var went := flat(player.global_position - start).dot(dir)
	check(went > 0.25 and went < reach - 0.12, "%s blocks the courier (walked %.2f of %.2f m to its centre)" % [label, went, reach])

## True when the floor under `at` is at height `y` (the prop's own floor, not a step below it).
func floor_at(at: Vector3, y: float) -> bool:
	var q := PhysicsRayQueryParameters3D.create(Vector3(at.x, y + 1.0, at.z), Vector3(at.x, y - 0.5, at.z), player.collision_mask, [player.get_rid()])
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	return not hit.is_empty() and absf((hit.position as Vector3).y - y) < 0.12

## A start 1.4-1.8 m from a collider on a free side (tries its local +-x / +-z axes).
func approach(cs: CollisionShape3D, distance: float = 1.6) -> Vector3:
	var xf := cs.global_transform
	var half := Vector3(0.3, 0.3, 0.3)
	if cs.shape is BoxShape3D: half = (cs.shape as BoxShape3D).size * 0.5
	elif cs.shape is CapsuleShape3D:
		var r := (cs.shape as CapsuleShape3D).radius
		half = Vector3(r, (cs.shape as CapsuleShape3D).height * 0.5, r)
	elif cs.shape is CylinderShape3D:
		var r := (cs.shape as CylinderShape3D).radius
		half = Vector3(r, (cs.shape as CylinderShape3D).height * 0.5, r)
	var axes: Array[Vector3] = [xf.basis.z.normalized(), -xf.basis.z.normalized(), xf.basis.x.normalized(), -xf.basis.x.normalized()]
	var extents: Array[float] = [half.z, half.z, half.x, half.x]
	if half.x < half.z:
		axes = [xf.basis.x.normalized(), -xf.basis.x.normalized(), xf.basis.z.normalized(), -xf.basis.z.normalized()]
		extents = [half.x, half.x, half.z, half.z]
	for k in range(4):
		var at := flat(xf.origin + flat(axes[k]) * (extents[k] + distance))
		# Stand on the floor the prop stands on (Cedar House floor 0.75, porch 0.72, sidewalks).
		at.y = maxf(xf.origin.y - half.y, 0.0) + 0.05
		var mid := at.lerp(Vector3(xf.origin.x, at.y, xf.origin.z), 0.3)
		if capsule_free(at + Vector3(0, 0.08, 0)) and capsule_free(mid + Vector3(0, 0.08, 0)) and floor_at(at, at.y - 0.05): return at
	return Vector3.INF

func shapes_tagged(tag: String) -> Array[CollisionShape3D]:
	var out: Array[CollisionShape3D] = []
	for n in world.find_children("*", "CollisionShape3D", true, false):
		var cs := n as CollisionShape3D
		var tagged := str(cs.get_meta("prop", "")) == tag or str(cs.get_parent().get_meta("prop", "")) == tag
		if tagged: out.append(cs)
	return out

func nearest(list: Array[CollisionShape3D], to: Vector3) -> CollisionShape3D:
	var best: CollisionShape3D = null
	var best_d := INF
	for cs in list:
		var d := flat(cs.global_position).distance_to(flat(to))
		if d < best_d:
			best_d = d
			best = cs
	return best

## Push into the tagged collider nearest `near` (a free side is picked automatically).
func push_tagged(label: String, tag: String, near: Vector3) -> void:
	var cs := nearest(shapes_tagged(tag), near)
	if cs == null:
		check(false, "%s: a '%s' collider exists" % [label, tag])
		return
	var start := Vector3.INF
	for d in [1.6, 1.0, 0.5]:
		if start == Vector3.INF: start = approach(cs, d)
	if start == Vector3.INF:
		check(false, "%s: no free side to approach %s at %s" % [label, tag, cs.global_position])
		return
	await blocked(label, start, cs.global_position)

## Walk the courier along `points` (ground positions); true when every point is reached.
func walk(label: String, points: Array[Vector3], start: Vector3 = Vector3.INF, timeout: float = 0.0) -> bool:
	if start != Vector3.INF: place(start)
	if timeout <= 0.0:
		var length := 0.0
		var from := player.global_position
		for p in points:
			length += flat(p - from).length()
			from = p
		timeout = 4.0 + length / 2.5
	await ticks(2)
	var t := 0.0
	var idx := 0
	var last_progress := 0.0
	var best := INF
	Input.action_press("move_forward")
	while idx < points.size() and t < timeout:
		var to := flat(points[idx] - player.global_position)
		var tolerance := 0.3 if idx == points.size() - 1 else 0.45
		if to.length() < tolerance:
			idx += 1
			best = INF
			continue
		face(to)
		await physics_frame
		physics_samples.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
		t += 1.0 / 60.0
		if to.length() < best - 0.05:
			best = to.length()
			last_progress = t
		if t - last_progress > 2.0: break   # stuck
	Input.action_release("move_forward")
	await ticks(2)
	var ok := idx >= points.size()
	if not ok: print("  blocked by: ", what_blocks(flat(points[mini(idx, points.size() - 1)] - player.global_position).normalized()))
	var where := player.global_position
	check(ok, "%s walkable (%s; at %s after %.1f s)" % [label, "reached" if ok else "stuck before point %d %s" % [idx, points[mini(idx, points.size() - 1)]], "(%.2f, %.2f, %.2f)" % [where.x, where.y, where.z], t])
	return ok

## Aim the E ray from standing at `stand` at `point`; the target id must start with `expect`.
func aims(label: String, stand: Vector3, point: Vector3, expect: String) -> void:
	place(stand)
	await ticks(3)
	var eye := player.eye_position()
	var d := point - eye
	player.rotation = Vector3(0, atan2(-d.x, -d.z), 0)
	player.camera.rotation = Vector3(atan2(d.y, flat(d).length()), 0, 0)
	await ticks(2)
	var hit := player.target()
	var id := str(hit.get("id", ""))
	# "p": the restaurant's pickup shelf, or one of the packages stocked on it (both are the shelf).
	if expect == "p": expect = "pickup" if not id.begins_with("package") else "package"
	check(id.begins_with(expect), "%s: E ray hits '%s' (wanted %s*)" % [label, id, expect])

func run() -> void:
	root.size = Vector2i(1280, 720)
	# One process frame per physics tick: headless runs otherwise spin ~2 idle frames per tick and
	# would hit run_tests.ps1's --quit-after 30000 frame budget.
	Engine.max_fps = 60
	var settings_path := "user://prop_collision_test_settings.cfg"
	GameSettings.path = settings_path
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	player = game.player
	world = game.world
	player.apply_view_settings(true, 3.2)
	await ticks(20)
	var bike_home := player.bicycle.position
	# ---- 0. counts --------------------------------------------------------------------------
	var thin := 0
	var bulky := 0
	var layer1 := 0
	for n in world.find_children("*", "CollisionShape3D", true, false):
		var body := (n as Node).get_parent() as CollisionObject3D
		if body == null or (n as CollisionShape3D).disabled: continue
		if body.collision_layer & PropColliders.LAYER_THIN: thin += 1
		elif body.collision_layer & PropColliders.LAYER_BULKY: bulky += 1
		elif body.collision_layer & 1: layer1 += 1
	print("colliders: %d prop shapes on layer 6 (thin), %d on layer 7 (bulky), %d other layer-1 shapes; %d prop bodies; per kind %s" % [thin, bulky, layer1, PropColliders.body_count, PropColliders.tags])
	check(thin > 1000 and bulky > 20, "prop colliders built (%d thin, %d bulky)" % [thin, bulky])
	check(player.collision_mask & PropColliders.LAYER_THIN and player.collision_mask & PropColliders.LAYER_BULKY, "the courier collides with both prop layers")
	check(player.view.arm.collision_mask & PropColliders.LAYER_THIN == 0 and player.view.arm.collision_mask & PropColliders.LAYER_BULKY != 0, "the camera arm ignores thin props, pulls in at bulky ones")
	if want("block"): await section_block()
	if want("bike"): await section_bike()
	if want("sidewalk"): await section_sidewalk()
	if want("doors"): await section_doors()
	if want("restaurants"): await section_restaurants()
	if want("cedar"): await section_cedar()
	if want("stores"): await section_stores()
	if want("downtown"): await section_downtown()
	if want("spots"): section_spots(bike_home)
	# ---- 4. physics time ----------------------------------------------------------------------
	physics_samples.sort()
	var mean := 0.0
	for s in physics_samples: mean += s
	mean /= maxf(physics_samples.size(), 1.0)
	print("physics: %d walking frames, physics process mean %.3f ms, median %.3f ms, p95 %.3f ms" % [physics_samples.size(), mean, physics_samples[physics_samples.size() / 2] if not physics_samples.is_empty() else 0.0, physics_samples[int(physics_samples.size() * 0.95)] if not physics_samples.is_empty() else 0.0])
	print("frames: %d process, %d physics" % [Engine.get_process_frames(), Engine.get_physics_frames()])
	print("PROP COLLISION %s: %d checks, %d failures" % ["PASS" if failures == 0 else "FAIL", checks, failures])
	quit(1 if failures else 0)


func section_block() -> void:
	# ---- 1. blocked -------------------------------------------------------------------------
	await push_tagged("White picket fence (Cedar Lane west)", "fence_picket", Vector3(-11, 0, -30))
	await push_tagged("White picket fence (Cedar Lane east)", "fence_picket", Vector3(11, 0, -120))
	await push_tagged("Hedge", "hedge", Vector3(-11, 0, -60))
	await push_tagged("Avenue bench", "bench_wood", Vector3(-9.6, 0, -20))
	await push_tagged("Litter bin", "litter_bin_red", Vector3(-9.6, 0, -20))
	await push_tagged("Yard bins", "bins_trio", Vector3(-30, 0, -20))
	await push_tagged("Delivery mailbox", "mailbox", Vector3(-12, 0, -20))
	await push_tagged("Patio set", "patio_set", Vector3(-30, 0, -20))
	await push_tagged("Garden shed", "shed", Vector3(-30, 0, -200))
	await push_tagged("Fire hydrant", "hydrant", Vector3(7, 0, -40))
	await push_tagged("Restaurant planter", "rs_planter", Vector3(80, 0, -270))
	await push_tagged("Downtown café chair", "cafe_chair", Vector3(190, 0, -330))
	await push_tagged("Downtown bench", "reuse_park_bench", Vector3(190, 0, -300))
	await push_tagged("Downtown street lamp", "reuse_street_lamp", Vector3(160, 0, -268))
	await push_tagged("Downtown trash bin", "trash_bin", Vector3(180, 0, -268))
	await push_tagged("Park rock", "rock_0", Vector3(-44, 0, -330))
	# Street light pole and tree trunk (layer-1 colliders from before) - still solid.
	var light_body: StaticBody3D = null
	for n in world.find_children("*", "StaticBody3D", true, false):
		if str(n.get_meta("prop", "")) == "street_light" and (light_body == null or flat((n as Node3D).global_position).distance_to(Vector3(6.5, 0, -30)) < flat(light_body.global_position).distance_to(Vector3(6.5, 0, -30))):
			light_body = n
	if light_body != null:
		await blocked("Street-light pole", flat(light_body.global_position) + Vector3(0, 0, 1.6), light_body.global_position)
	else: check(false, "a street-light pole collider exists")
	var trunk_shapes: Array[CollisionShape3D] = []
	for c in world.landscape.trunks.get_children():
		if c is CollisionShape3D: trunk_shapes.append(c)
	var trunk := nearest(trunk_shapes, Vector3(-10.7, 0, -50))
	if trunk != null:
		var start := approach(trunk)
		if start != Vector3.INF: await blocked("Avenue tree trunk", start, trunk.global_position)
	# Cedar House furniture (layer 1) and floor plants (prop layer).
	var furnish := world.cedar_house.find_child("FurnishingCollision", true, false)
	# Furniture with an open side to walk at (most pieces stand against walls and each other).
	var tested := 0
	for name in ["SofaCollision", "FridgeCollision", "BedPlaidCollision", "BedBlueCollision", "ArmchairReadingCollision", "EtagereCollision", "SideboardCollision", "HallMirrorConsoleCollision"]:
		var cs := furnish.find_child(name, false, false) as CollisionShape3D if furnish != null else null
		if cs == null: continue
		var start := approach(cs, 0.8)
		if start == Vector3.INF: start = approach(cs, 0.5)
		if start == Vector3.INF:
			print("  note: Cedar House %s has no open side to walk at" % name)
			continue
		tested += 1
		await blocked("Cedar House " + name.trim_suffix("Collision"), start, cs.global_position, 1.2)
	check(tested >= 4, "Cedar House furniture pushed into (%d pieces)" % tested)
	await push_tagged("Cedar House porch planter", "planter_trough_a", CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(-2.3, 0, 6))

func section_bike() -> void:
	# On the bicycle: ride into a downtown lamp post at speed.
	var lamp := nearest(shapes_tagged("reuse_street_lamp"), Vector3(160, 0, -268))
	if lamp != null and player.has_vehicle():
		var at := approach(lamp, 4.0)
		if at != Vector3.INF:
			player.bicycle.position = at
			player.bicycle.rotation = Vector3(0, atan2(-(lamp.global_position - at).x, -(lamp.global_position - at).z), 0)
			place(at + player.bicycle.global_basis.x * 0.7)
			await ticks(2)
			player.toggle_bicycle()
			if player.mounted:
				var dir := flat(lamp.global_position - at).normalized()
				player.rotation.y = atan2(-dir.x, -dir.z)
				player.riding_speed = 5.0
				player.camera.rotation = Vector3.ZERO
				Input.action_press("move_forward")
				for i in range(120):
					player.rotation.y = atan2(-dir.x, -dir.z)
					player.camera.rotation = Vector3.ZERO
					await physics_frame
				Input.action_release("move_forward")
				var went := flat(player.global_position - at).dot(dir)
				check(went < flat(lamp.global_position - at).length() - 0.12, "Bicycle stops at the lamp post (rode %.2f of %.2f m)" % [went, flat(lamp.global_position - at).length()])
				player.riding_speed = 0.0
				await ticks(5)
				player.toggle_bicycle()
				await ticks(40)
			else: check(false, "could mount the bicycle for the lamp-post ride")

func section_sidewalk() -> void:
	await walk("Cedar Lane west sidewalk run (z 20 -> -40)", [Vector3(-8.3, 0, -10), Vector3(-8.3, 0, -40)] as Array[Vector3], Vector3(-8.3, 0.05, 20))
	await walk("Cedar Lane east sidewalk run (z -100 -> -160)", [Vector3(8.3, 0, -130), Vector3(8.3, 0, -160)] as Array[Vector3], Vector3(8.3, 0.05, -100))

func section_doors() -> void:
	var door_ok := 0
	var door_total := 0
	for lot in ResidentialLayout.lots():
		if int(lot.delivery) < 0 or absf(float(lot.line_x)) != 10.5: continue
		var t := ResidentialLayout.transform(lot)
		var door: Vector3 = ResidentialLayout.TYPES[lot.type].door
		var side := signf(float(lot.line_x))
		var kerb := Vector3(side * 8.3, 0.05, (t * Vector3(door.x, 0, 0)).z)
		var path: Array[Vector3] = [t * Vector3(door.x, 0, ResidentialLayout.SETBACK + 0.2), t * Vector3(door.x, 0, 1.2), t * Vector3(door.x, 0, door.z + 0.55)]
		door_total += 1
		if await walk("Sidewalk to the door of address %d" % int(lot.delivery), path, kerb): door_ok += 1
	check(door_ok == door_total, "every Cedar Lane delivery door is reachable from the sidewalk (%d / %d)" % [door_ok, door_total])

func section_restaurants() -> void:
	for r: Dictionary in world.restaurants.restaurants:
		var frame: Transform3D = r.frame
		var b: Dictionary = {}
		for cand in RestaurantCatalog.corridor_buildings():
			if flat(RestaurantCatalog.frame(cand).origin).distance_to(flat(frame.origin)) < 0.1: b = cand
		if b.is_empty(): continue
		var xe := RestaurantCatalog.bay_x(b, RestaurantCatalog.entrance_bay(b))
		var path: Array[Vector3] = [frame * Vector3(xe, 0, 1.2), frame * Vector3(xe, 0, -2.0), frame * Vector3(xe, 0, -6.3), frame * Vector3(xe + 3.2, 0, -6.6)]
		if await walk("Into %s to its pickup shelf" % r.name, path, frame * Vector3(xe, 0.05, 3.0)):
			await aims("%s pickup shelf" % r.name, frame * Vector3(xe + 3.2, 0.06, -6.6), frame * Vector3(xe + 3.2, 1.0, -7.3), "p")
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		if await walk("Into %s to its counter" % CityCatalog.NAMES[i], [p + Vector3(0.4, 0, 3.0), p + Vector3(0.1, 0, 1.0)] as Array[Vector3], p + Vector3(0.4, 0.05, 6.0)):
			await aims("%s pickup counter" % CityCatalog.NAMES[i], p + Vector3(0.1, 0.05, 1.0), p + Vector3(0, 1.35, 0), "pickup")

func section_cedar() -> void:
	var home := CedarNeighborhood.CEDAR_HOME_ORIGIN
	world.cedar_house.toggle_door(0)
	await ticks(150)
	await walk("Cedar House: sidewalk -> garden -> front door -> hall", [Vector3(13.0, 0, 40.25), Vector3(19.0, 0, 40.25), Vector3(19.0, 0, 37.0), Vector3(19.0, 0, 34.0), home + Vector3(1.2, 0, 2.5)] as Array[Vector3], Vector3(9.5, 0.05, 40.25))
	world.cedar_house.toggle_door(0)
	await ticks(150)
	await aims("Cedar House front door", home + Vector3(1.1, 0.05, 7.0), home + Vector3(1.1, 1.2, 5.5), "cedar_door_0")
	await aims("REST / SAVE plaque", Vector3(17.8, 0.05, 36.6), Vector3(17.8, 1.66, 35.40), "home")

func section_stores() -> void:
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		if await walk("Into %s store to its computer" % id, [at + Vector3(1.0, 0, 6.0), at + Vector3(4.0, 0, 2.4)] as Array[Vector3], at + Vector3(1.0, 0.05, 11.0)):
			await aims("%s store computer" % id, at + Vector3(4.0, 0.05, 2.4), at + Vector3(4.0, 1.4, 1.0), "kiosk_" + id)

func section_spots(bike_home: Vector3) -> void:
	for spot: Vector3 in [Vector3(-8, 0.2, 23), Vector3(-14, 0.08, 13.8), bike_home + Vector3(1, 0.1, 0)]:
		check(capsule_free(spot), "spawn / bike spot %s is free of colliders" % spot)
	for address in range(36):
		var lot := ResidentialLayout.delivery_lot(address)
		var facing: Vector3 = lot.facing
		var spot: Vector3 = world.doors[address] + facing * 1.6 + Vector3(0, -0.92, 0)
		if not capsule_free(spot + Vector3(0, 0.05, 0)): check(false, "door stand spot of address %d is free (%s)" % [address, spot])

## Downtown lobbies (pickup counters, café tables, shelves and mailboxes inside): from the sidewalk
## through the entrance to the counter / lobby.
func section_downtown() -> void:
	var ok := 0
	var total := 0
	for e: Dictionary in world.downtown.entries:
		if bool(e.closed): continue
		var front: Vector3 = e.front
		var inside: Vector3 = e.inside
		var out := flat(front - inside).normalized()
		total += 1
		# 2.2 m in: past the doors, short of the pickup lobbies' courier shelves (DowntownCatalog.PICKUPS).
		var lobby := flat(front.lerp(inside, 0.6))
		if await walk("Downtown lobby %s" % str(e.number), [flat(front), lobby] as Array[Vector3], flat(front) + out * 1.5 + Vector3(0, 0.15, 0)): ok += 1
	check(ok == total, "every open downtown lobby is reachable (%d / %d)" % [ok, total])
