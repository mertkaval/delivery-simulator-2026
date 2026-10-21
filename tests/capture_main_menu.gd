extends SceneTree
## Captures the title menu (start and mid-animation), its settings page and the pause menu.
##   Godot.exe --path . --script res://tests/capture_main_menu.gd -- <out_dir>

var game: Node

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join(name + ".png"))
	print("SAVED ", name)

func wait(seconds: float) -> void:
	var end := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < end: await process_frame

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else ProjectSettings.globalize_path("user://captures")
	DirAccess.make_dir_recursive_absolute(out)
	root.mode = Window.MODE_WINDOWED
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	await wait(1.5)
	await shot(out, "menu_title")
	await wait(5.8)
	await shot(out, "menu_title_delivered")
	var menu: MainMenu = game.main_menu
	menu.show_page("settings")
	await wait(0.4)
	await shot(out, "menu_settings")
	menu.back()
	game.close_menu()
	await wait(0.5)
	game.show_menu("pause")
	await wait(0.9)
	await shot(out, "menu_pause")
	print("MENU mode=", game.mode, " paused=", paused)
	quit()
