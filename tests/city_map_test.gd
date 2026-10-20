extends SceneTree
## City map (M): opens full screen on foot, refuses while mounted, lists every place kind,
## selecting a place yields a road route, choosing it drives the minimap and HUD navigation.
var failures := 0
func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok: failures += 1
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280, 720)
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	for i in range(20): await process_frame
	game.close_menu()
	await process_frame
	game.show_menu("map")
	for i in range(3): await process_frame
	var map: Control = game.city_map
	check(map != null and map.visible, "city map opens full screen")
	check(game.mode == "map" and paused, "game paused while map open")
	var kinds := {}
	for p in map.places: kinds[p.kind] = int(kinds.get(p.kind, 0)) + 1
	print("PLACES ", kinds)
	for k in ["restaurant", "store", "park", "public", "hospital", "school", "fire", "home", "house"]:
		check(kinds.has(k), "map lists " + k)
	var target := -1
	for i in range(map.places.size()):
		if map.places[i].kind == "restaurant": target = i
	map._select(target, true)
	await process_frame
	check(map.route_preview.size() > 2, "route preview to %s (%d pts)" % [map.places[target].name, map.route_preview.size()])
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/city_map_selected.png")
	map.zoom = 0.55
	map.centre = Vector3(250, 0, -330)
	map.queue_redraw()
	for i in range(2): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/city_map_overview.png")
	map._choose(target)
	await process_frame
	check(game.mode == "" and not map.visible, "choosing closes map")
	check(CityNavigation.target.get("name", "") == map.places[target].name, "navigation target set")
	game.update_hud()
	check(game.minimap.route_points().size() > 2, "minimap shows route")
	check(game.navigation_label.text.contains(map.places[target].name), "HUD: " + game.navigation_label.text)
	game.player.position = CityNavigation.target.at + Vector3(2, 0.08, 0)
	game.update_hud()
	check(CityNavigation.target.is_empty(), "arrival clears navigation")
	print("RESULT ", "PASS" if failures == 0 else "FAIL %d" % failures)
	quit()
