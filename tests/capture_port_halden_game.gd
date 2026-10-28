extends SceneTree
## The real game in Port Halden, through the courier's camera: the start, the title menu, a
## pickup rack on a shop front, and the city at dusk.
## usage: godot --path . --script res://tests/capture_port_halden_game.gd -- <out_dir>
class MemorySave extends DeliverySave:
	func save_game(_data: Dictionary, _path: String = PATH) -> bool:
		return true

func _initialize() -> void: call_deferred("run")

func grab(out: String, name: String, frames: int = 20) -> void:
	for i in frames: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("ph_%s.png" % name))
	print("CAPTURED ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	root.size = Vector2i(1600, 900)
	CedarNeighborhood.city_override = "port_halden"
	var game: GameApp = load("res://app/app_root.tscn").instantiate()
	game.saves = MemorySave.new()
	root.add_child(game)
	await grab(out, "menu", 30)
	game.close_menu()
	game.world.set_time(10.5)
	await grab(out, "start", 60)
	# turn round to face the street
	game.player.rotation.y += PI
	await grab(out, "street", 30)
	# a pickup rack on a shop front
	var frame: Transform3D = (game.world.get_meta("pickup_frames") as Array)[0]
	game.player.position = frame * Vector3(0, 0.4, 4.0)
	game.player.look_at(Vector3(frame.origin.x, game.player.position.y, frame.origin.z))
	await grab(out, "pickup", 60)
	game.world.set_time(20.6)
	game.player.position = GamePersistence.START
	game.player.rotation.y = 0.0
	await grab(out, "dusk", 60)
	quit()
