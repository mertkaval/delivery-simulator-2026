class_name GamePersistence
extends RefCounted
## New career, saving and loading the shift (DeliverySave), and the title menu's save summary.
## The save is the session snapshot plus where the courier and the vehicle stand.

const START := Vector3(-8, 0.2, 23)
const VEHICLE_START := Vector3(-8, 0, 19)

var game: GameApp

func _init(app: GameApp) -> void:
	game = app

static func has_save() -> bool:
	return FileAccess.file_exists(DeliverySave.PATH) or FileAccess.file_exists(DeliverySave.PATH + ".bak")

## "Day 3 · $142.50 · 7 deliveries" for the Continue button.
static func save_summary() -> String:
	var path := DeliverySave.PATH if FileAccess.file_exists(DeliverySave.PATH) else DeliverySave.PATH + ".bak"
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary: return ""
	var d: Dictionary = data
	var done := int(d.get("completed", 0))
	return "Day %d  ·  %s  ·  %d %s" % [int(float((d.get("dispatch", {}) as Dictionary).get("calendar", 0)) / 1440.0) + 1, DeliverySession.money(int(d.get("wallet", 0))), done, "delivery" if done == 1 else "deliveries"]

func new_session() -> void:
	var player := game.player
	player.mounted = false
	player.riding_speed = 0
	player.camera.position.y = 1.65
	player.bicycle.position = VEHICLE_START
	var session := DeliverySession.new()
	session.start_career()
	game.use_session(session)
	player.replace_vehicle(VEHICLE_START)
	player.position = START
	player.rotation = Vector3.ZERO
	player.camera.rotation = Vector3.ZERO
	game.flow.reset()
	game.tutorial.start()
	save_session()
	game.close_menu()
	player.refresh_equipment()
	game.notify("Welcome! You start on foot with $100. Follow the training tasks on the left.")

func save_session() -> bool:
	if not game.save_enabled or "--smoke-test" in OS.get_cmdline_user_args():
		return true
	var player := game.player
	var data := game.session.snapshot()
	data.player = {"position": [player.position.x, player.position.y, player.position.z], "yaw": player.rotation.y}
	data.player.bicycle = [player.bicycle.position.x, player.bicycle.position.y, player.bicycle.position.z]
	data.player.mounted = player.mounted
	data.player.bicycle_yaw = player.bicycle.rotation.y
	var success := game.saves.save_game(data)
	if not success:
		game.notify(game.saves.error)
	return success

func load_session() -> void:
	var player := game.player
	var data := game.saves.load_game()
	if data.is_empty():
		if game.main_menu.visible: game.main_menu.flash(game.saves.error)
		else: game.menus.add_text(game.saves.error, 18, Color("f0c28b"))
		return
	game.session.restore(data)
	if game.store_terminals: game.store_terminals.session = game.session
	player.replace_vehicle(VEHICLE_START)
	player.position = Vector3(data.player.position[0], data.player.position[1], data.player.position[2])
	player.rotation.y = data.player.yaw
	var bike_position: Array = data.player.get("bicycle", [VEHICLE_START.x, VEHICLE_START.y, VEHICLE_START.z])
	player.bicycle.position = Vector3(bike_position[0], bike_position[1], bike_position[2])
	player.bicycle.rotation.y = data.player.get("bicycle_yaw", data.player.yaw)
	player.mounted = data.player.get("mounted", false)
	player.riding_speed = 0
	player.camera.position.y = 1.85 if player.mounted else 1.65
	player.velocity = Vector3.ZERO
	player.camera.rotation = Vector3.ZERO
	player.apply_vehicle_camera()
	game.world.set_time(game.session.hour())
	game.close_menu()
	game.notify("Shift restored." if game.saves.error == "" else game.saves.error)
