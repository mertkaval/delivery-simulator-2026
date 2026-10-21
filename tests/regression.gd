extends SceneTree
var failures: int = 0
var checks: int = 0

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		printerr("FAIL: " + message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var session := DeliverySession.new()
	session.offer()
	session.accept()
	session.pickup("cedar_kitchen", NAN)
	check(session.order.state == "ACCEPTED", "NaN pickup cannot create cargo")
	session.pickup("cedar_kitchen", 1)
	session.deliver(0, -1)
	check(session.order.state == "CARRYING", "Negative distance cannot pay")
	var saver := DeliverySave.new()
	var path := "user://regression_test_%d.json" % Time.get_ticks_usec()
	var data := session.snapshot()
	data.player = {"position": [-8, 0.1, 19], "yaw": 0.0, "bicycle": [-8, 0, 19], "bicycle_yaw": 1.2, "mounted": false}
	check(saver.save_game(data, path), "Write carrying save")
	var restored := DeliverySession.new()
	check(restored.restore(saver.load_game(path)), "Restore carrying save")
	check(restored.order.bag == session.order.bag, "Cargo survives restart")
	for i in range(20): restored.deliver(0, 1)
	check(restored.completed == 1 and restored.ledger.keys().filter(func(k): return str(k).begins_with("payment_")).size() == 1, "Twenty handoffs credit once")
	var after := restored.snapshot()
	after.player = data.player
	check(saver.save_game(after, path), "Write completed save with backup")
	var broken := after.duplicate(true)
	broken.bag_upgrade = true
	check(not DeliverySave.valid_envelope(broken), "Unpaid upgrade rejected")
	broken = after.duplicate(true)
	broken.order.quote = 1.5
	check(not DeliverySave.valid_envelope(broken), "Fractional cents rejected")
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string("{interrupted")
	file.close()
	var recovered := saver.load_game(path)
	check(not recovered.is_empty() and recovered.order.state == "CARRYING", "Corrupt primary recovers backup")
	check(FileAccess.get_file_as_string(path) == "{interrupted", "Recovery preserves corrupt primary")
	for suffix in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(path + suffix): DirAccess.remove_absolute(path + suffix)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	await physics_frame
	game.player.position = Vector3(-7, 0.1, 19)
	game.player.bicycle.rotation.y = 0.8
	check(game.player.toggle_bicycle().begins_with("Mounted"), "Mount works")
	check(is_equal_approx(game.player.position.x, game.player.bicycle.position.x), "Mount aligns player, not bike teleport")
	var heading: float = game.player.rotation.y
	var motion := InputEventMouseMotion.new()
	motion.relative = Vector2(80, 0)
	game.player.look(motion.relative)
	check(game.player.rotation.y == heading and game.player.camera.rotation.y != 0, "Riding look independent of steering")
	game.player.riding_speed = 4
	check(game.player.toggle_bicycle().begins_with("Brake"), "Moving dismount denied")
	game.player.riding_speed = 0
	check(game.player.toggle_bicycle() == "Bicycle parked.", "Stopped dismount works")
	check(game.player.camera.rotation.y == 0, "Walking camera realigned")
	game.show_menu("phone")
	var before: float = game.session.clock
	await create_timer(0.1, true).timeout
	check(game.session.clock == before, "Phone pauses simulation clock")
	game.session.offer()
	game.session.accept()
	game.player.position = Vector3(-14, 0.1, 13.2)
	game.session.pickup("cedar_kitchen", 1)
	var route: PackedVector3Array = game.minimap.route_points()
	check(route.size() > 2 and route[1].z == 15.0, "Route leaves kitchen through open front")
	game.close_menu()
	game.player.set_physics_process(false)
	for i in range(6):
		var facing: Vector3 = CityCatalog.address_facing(i)
		game.player.position = game.world.doors[i] + facing * 1.6 + Vector3(0, -0.92, 0)
		game.player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
		game.player.camera.rotation = Vector3(-0.2, 0, 0)
		await physics_frame
		await physics_frame
		check(game.player.target().get("id") == "door_%d" % i, "Door %d reachable by interaction ray" % i)
	print("REGRESSION: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
