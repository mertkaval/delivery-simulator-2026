extends SceneTree
## Townspeople behaviour checks (headless): ~3 simulated minutes of the whole city.
##   godot --headless --path . --script res://tests/npc_life_test.gd
## The downtown signal clock keeps advancing (no walker holds the all-red clearance forever),
## nobody is left flagged in_crossing while waiting at a kerb, walkers stand on the rendered
## walking surfaces and keep off the carriageways outside crossings, most people get somewhere,
## seats/diners/waiters exist, and seated people sit on their seat.
var checks := 0
var failures := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		print("FAIL: ", label)

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(13.0)
	var life: Node = world.get_node("CityLife")
	var downtown: Node = world.find_child("DowntownActivity", true, false)
	check(life.pedestrians.size() >= 100, "neighbourhood walkers (%d)" % life.pedestrians.size())   # 56 avenue + 32 residential + park + crossers
	check(downtown != null and downtown.pedestrians.size() >= 80, "downtown walkers")
	var brains: Array = []
	for n in world.find_children("*", "Node", true, false):
		if n is CitizenBrain: brains.append(n)
	var start := {}
	for b: CitizenBrain in brains: start[b] = b.body.position
	# 3 simulated minutes at 4x time scale.
	Engine.time_scale = 4.0
	var clock0: float = downtown.elapsed
	var off_road := 0
	var bad_height := 0
	var stale_crossing := 0
	var seated_seen := 0
	for step in range(180):
		for i in range(15): await physics_frame
		for b: CitizenBrain in brains:
			if not b.body.visible: continue
			var p := b.body.position
			if b.state == "WAIT_CROSS" and b.body.get_meta("in_crossing", false): stale_crossing += 1
			if b.state == "SEATED": seated_seen += 1
			if b.state == "WALK" and absf(p.y - CitizenRoutes.ground_y(p)) > 0.03: bad_height += 1
			if b.state == "WALK" and b.loop.is_empty() and not b.body.get_meta("in_crossing", false) and p.x < 120 and absf(p.x) < 5.5 and absf(p.z + 93) > 4 and absf(p.z + 177) > 4:
				off_road += 1
	Engine.time_scale = 1.0
	var advanced: float = downtown.elapsed - clock0
	check(advanced > 150.0, "downtown signal clock keeps advancing (%.1f s of ~180)" % advanced)
	check(stale_crossing == 0, "nobody waits at a kerb flagged in_crossing (%d samples)" % stale_crossing)
	check(bad_height == 0, "walkers stand on the walking surface (%d samples off)" % bad_height)
	check(off_road == 0, "walkers keep off the avenue carriageway outside crossings (%d samples)" % off_road)
	var moved := 0
	for b: CitizenBrain in brains:
		if b.body.position.distance_to(start[b]) > 3.0 or b.state in ["INSIDE", "SEATED"]: moved += 1
	check(moved > brains.size() * 0.85, "people get somewhere (%d / %d moved)" % [moved, brains.size()])
	check(life.seats.size() > 40, "free bench seats registered (%d)" % life.seats.size())
	check(life.sitters.size() >= 6, "park bench sitters (%d)" % life.sitters.size())
	var services: Array = world.restaurants.services
	var waiters := 0
	for s: TableService in services:
		if s.waiter != null: waiters += 1
	check(waiters == 13, "a waiter in every corridor restaurant (%d)" % waiters)
	check(life.get_node_or_null("ShopLife") != null and life.get_node("ShopLife").customers.size() == 4, "a customer in each of the four shops")
	# Seated people: buttocks on the seat (body origin height = seat top - measured contact).
	var seated_ok := true
	for p: LivingCitizen in life.sitters:
		var m: Vector3 = LivingAssets.SEATED[p.body_id]
		if p.purpose_pose.begins_with("Sit") == false: seated_ok = false
		if absf(p.body_scale - clampf(p.body_scale, 0.93, 1.07)) > 0.001: seated_ok = false
		if m.x <= 0: seated_ok = false
	check(seated_ok, "park sitters use seated clips at a natural scale")
	print("NPC LIFE: %d checks, %d failures; %d brains, seated samples %d" % [checks, failures, brains.size(), seated_seen])
	quit(1 if failures else 0)
