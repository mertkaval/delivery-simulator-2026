extends SceneTree
## Main menu: the game opens on the title menu (paused, artwork shown, Save/Exit to Menu
## disabled); Esc opens the in-game menu over the street; settings pages apply live to the
## player; Continue resumes; Exit to Menu returns to the title; Esc backs out of sub pages.
var failures := 0
var checks := 0
func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL: ") + what)
	if not ok: failures += 1
func _initialize() -> void: call_deferred("run")

func buttons(menu: MainMenu) -> Dictionary:
	var found := {}
	for c in menu.column.get_children():
		if c is Button: found[(c as Button).text] = c
	return found

func esc(game: Node) -> void:
	var e := InputEventAction.new()
	e.action = "pause_game"
	e.pressed = true
	game._unhandled_input(e)

func run() -> void:
	root.size = Vector2i(1280, 720)
	var saved_settings: Dictionary = GameSettings.values.duplicate()
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	for i in range(10): await process_frame
	var menu: MainMenu = game.main_menu
	check(game.mode == "start" and paused and menu.visible, "game starts on the title menu, paused")
	check(menu.art.visible and menu.hero.texture != null, "title shows the city artwork")
	check(menu.tiles.size() == 3 and menu.flock.birds.size() > 0, "collage prints and a flock of birds are on screen")
	var b := buttons(menu)
	for name in ["New Game", "Save Game", "Settings", "Exit to Menu", "Exit to Desktop"]:
		check(b.has(name), "title has " + name)
	check((b["Save Game"] as Button).disabled and (b["Exit to Menu"] as Button).disabled, "Save / Exit to Menu disabled on the title")
	esc(game)
	check(game.mode == "start" and menu.visible, "Esc does not leave the title menu")
	# Settings apply live.
	menu.show_page("settings")
	var sliders: Array[HSlider] = []
	for row in menu.column.get_children():
		for c in row.get_children():
			if c is HSlider: sliders.append(c)
	check(sliders.size() == 5, "settings has 5 sliders")
	sliders[3].value = 2.0
	sliders[4].value = 90.0
	check(is_equal_approx(game.player.sensitivity, 0.004) and is_equal_approx(game.player.camera.fov, 90.0), "sensitivity and FOV apply to the player")
	GameSettings.values = saved_settings.duplicate()
	GameSettings.apply(game.player)
	menu.show_page("main")
	# Start a shift, then the in-game menu.
	game.new_session()
	await process_frame
	check(game.mode == "" and not paused and not menu.visible, "New Game starts the shift")
	esc(game)
	await process_frame
	check(game.mode == "pause" and paused and menu.visible and not menu.art.visible, "Esc opens the in-game menu over the street")
	b = buttons(menu)
	check(not (b["Save Game"] as Button).disabled and b.has("Exit to Menu") and b.has("Continue"), "in-game menu has Continue, Save and Exit to Menu")
	menu.show_page("settings")
	esc(game)
	check(game.mode == "pause" and menu.page == "main", "Esc backs out of settings first")
	GameSettings.values = saved_settings.duplicate()
	esc(game)
	check(game.mode == "" and not paused, "second Esc resumes")
	game.show_menu("pause")
	game.on_main_menu("resume")
	check(game.mode == "" and not paused, "Continue resumes the shift")
	game.show_menu("pause")
	game.on_main_menu("exit_to_menu")
	check(game.mode == "start" and menu.art.visible and paused, "Exit to Menu returns to the title")
	print("MAIN MENU: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
