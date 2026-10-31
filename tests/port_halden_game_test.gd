extends SceneTree
## The game in Port Halden (the generated city): the courier starts on the ground in the starter
## neighbourhood, the 41 delivery doors are Port Halden houses and tower lobbies, the 21 pickups
## and 4 stores stand on its shop fronts, routes follow its streets, orders work end to end, the
## minimap draws its roads, and day / night reach the city's lights.
var failures := 0
var checks := 0
class MemorySave extends DeliverySave:
	func save_game(_data: Dictionary, _path: String = PATH) -> bool:
		return true

func _initialize() -> void: call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	print(("PASS: " if ok else "FAIL: ") + text)
	if not ok: failures += 1

func run() -> void:
	CedarNeighborhood.city_override = "port_halden"
	# a city build's folder as the first argument (-- res://assets/cityforge_roads/); default: the classic city
	var city_args := OS.get_cmdline_user_args()
	if city_args.size() > 0 and str(city_args[0]).begins_with("res://"): CityForgeWorld.use_city(str(city_args[0]))
	var game: GameApp = load("res://app/app_root.tscn").instantiate()
	game.saves = MemorySave.new()
	root.add_child(game)
	game.close_menu()
	var w: CityForgeWorld = game.world.port
	check(w != null and w.chunks.size() == 64, "The game builds Port Halden as its city")
	check(game.world.doors.size() == 41, "41 delivery doors (%d)" % game.world.doors.size())
	var on_house := 0
	for i in 36:
		var hs := w.nearest_house(game.world.doors[i])
		if w.house_door(hs).distance_to(game.world.doors[i] - Vector3(0, 0.92, 0)) < 0.1: on_house += 1
	check(on_house == 36, "Doors 0-35 are the front doors of Port Halden houses (%d)" % on_house)
	check(CityCatalog.address_position(7) == game.world.doors[7], "The catalog's addresses are Port Halden's")
	var a0 := str(DeliverySession.ADDRESSES[0])
	check(a0.get_slice(" ", 0).is_valid_int() and a0.get_slice_count(" ") >= 3, "Addresses are a number and a named street (%s)" % a0)
	check(CityCatalog.PICKUPS.size() == CityCatalog.RESTAURANTS.size(), "Every restaurant has a pickup in Port Halden (%d)" % CityCatalog.PICKUPS.size())
	check(game.shelves.shelves.size() == CityCatalog.RESTAURANTS.size(), "Every pickup has a courier rack (%d)" % game.shelves.shelves.size())
	check(ShopCatalog.LOCATIONS.size() == 4 and ShopCatalog.FRAMES.size() == 4, "The four stores stand on shop fronts")
	var start := GamePersistence.START
	check(absf(start.y - 0.4 - w.ground_height(start)) < 0.01, "The courier starts on the ground of the starter neighbourhood")
	check(game.player.position.distance_to(start) < 0.5, "The courier is placed at the start")
	var here := StreetNames.describe(start)
	check(here.length() > 6 and here != "Port Halden" and not here.ends_with("Park"), "The HUD names Port Halden's street (%s)" % here)
	# routes follow the streets
	var path := CityCatalog.route(start, game.world.doors[20], false)
	check(path.size() >= 3 and CityCatalog.distance(path) >= start.distance_to(game.world.doors[20]) * 0.95, "Routes run along Port Halden's streets (%d points)" % path.size())
	# an order end to end: offered, its door and restaurant are Port Halden's
	game.session.offer(10.0, 2, 11)
	var order: Dictionary = game.session.order
	check(not order.is_empty() and int(order.address) == 11 and float(order.get("distance", 0.0)) > 10.0, "An order is offered with a street distance (%.0f m)" % float(order.get("distance", 0.0)))
	check(game.session.pickup_position() == CityCatalog.PICKUPS[2], "Its pickup is a Port Halden shop front")
	# the minimap draws Port Halden's roads
	check((game.world.get_meta("map_roads", []) as Array).size() > 400, "The minimap has Port Halden's roads")
	# the courier stands on the ground after falling into place
	game.player.set_physics_process(true)
	for i in 90: await physics_frame
	var feet := game.player.global_position
	check(feet.y > w.ground_height(feet) - 0.4 and feet.y < w.ground_height(feet) + 1.2, "The courier stands on the city's ground (%.2f over %.2f)" % [feet.y, w.ground_height(feet)])
	# day and night
	game.world.set_time(23.0)
	var lamp := CityForgeMaterials.get_material("CF_LampGlow") as ShaderMaterial
	check(float(lamp.get_shader_parameter("emission_energy")) > 2.0, "Street lamps light up at night")
	game.world.set_time(12.0)
	check(float(lamp.get_shader_parameter("emission_energy")) < 1.0, "... and dim by day")
	print("PORT HALDEN GAME: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 else 1)
