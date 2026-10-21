extends SceneTree
## Audio library and CityAudio voice budget: every expected sound file exists and loads, loops
## import with loop points (smpl chunk) and loop forward through CityAudio.stream(), the buses
## carry their trims and still follow the settings sliders, and the 3D pools stay bounded with
## hundreds of vehicles, a burst of one-shots and many walk signals.
var game
var failures := 0
var checks := 0

const WORLD_SOUNDS := ["horn_honk", "truck_brake_squeal", "air_brake_hiss", "shop_door_chime", "cutlery_clink",
	"plate_clink", "pan_clank", "songbird_trill", "blackbird_song", "owl_hoot", "bird_chirp", "footstep_concrete",
	"footstep_grass", "footstep_wood", "footstep_interior", "footstep_wet", "bike_bell", "brake_squeal",
	"ui_notification", "ui_accept", "ui_reject", "delivery_complete", "cash_register", "door_close"]

func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL: ") + what)
	if not ok: failures += 1

func _initialize() -> void: call_deferred("run")

func frames(n: int) -> void:
	for i in range(n): await process_frame

func run() -> void:
	# 1. Files.
	var names: Array[String] = []
	for n: String in CityAudio.GAMEPLAY + CityAudio.LOOPS + WORLD_SOUNDS:
		if not n in names: names.append(n)
	var missing: Array[String] = []
	var bad_loops: Array[String] = []
	for n in names:
		var s := load(CityAudio.SFX % n) as AudioStreamWAV
		if s == null or s.get_length() <= 0.05:
			missing.append(n)
			continue
		if n in CityAudio.LOOPS and (s.loop_mode != AudioStreamWAV.LOOP_FORWARD or s.loop_end <= s.loop_begin):
			bad_loops.append("%s(mode %d, %d..%d)" % [n, s.loop_mode, s.loop_begin, s.loop_end])
	check(missing.is_empty(), "%d expected sounds exist and load %s" % [names.size(), missing])
	check(bad_loops.is_empty(), "%d loops import with forward loop points %s" % [CityAudio.LOOPS.size(), bad_loops])
	var looped := true
	for n: String in CityAudio.LOOPS:
		var s := CityAudio.stream(n)
		looped = looped and s.loop_mode == AudioStreamWAV.LOOP_FORWARD and s.loop_end > 0
	check(looped, "CityAudio.stream() returns forward-looping streams for every loop")

	# 2. Game with CityAudio.
	root.size = Vector2i(1280, 720)
	game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	await frames(10)
	game.new_session()
	await frames(5)
	paused = false
	game.player.camera.make_current()
	await frames(3)
	var audio: CityAudio = game.audio
	check(audio != null and audio.holder != null, "CityAudio is set up with a 3D voice holder in the world")
	for bus: String in ["UI", "Ambience", "SFX"]:
		var idx := AudioServer.get_bus_index(bus)
		var trimmed := false
		if idx != -1:
			for e in range(AudioServer.get_bus_effect_count(idx)):
				if AudioServer.get_bus_effect(idx, e) is AudioEffectAmplify: trimmed = true
		check(idx != -1 and trimmed and AudioServer.get_bus_send(idx) == "Master", "bus %s exists, has its mix trim and sends to Master" % bus)
	# Settings sliders still drive the buses.
	GameSettings.set_value("effects", 0.5)
	GameSettings.set_value("ambience", 0.25)
	GameSettings.apply()
	check(absf(AudioServer.get_bus_volume_db(AudioServer.get_bus_index("SFX")) - linear_to_db(0.5)) < 0.01
		and absf(AudioServer.get_bus_volume_db(AudioServer.get_bus_index("UI")) - linear_to_db(0.5)) < 0.01
		and absf(AudioServer.get_bus_volume_db(AudioServer.get_bus_index("Ambience")) - linear_to_db(0.25)) < 0.01,
		"settings sliders still set the SFX/UI/Ambience bus volumes")
	GameSettings.load_settings()
	GameSettings.apply()

	# 3. Discovery of the real traffic.
	var t0 := Time.get_ticks_usec()
	audio.discover()
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("discover(): %.1f ms, %d vehicle lists, %d signals" % [ms, audio.vehicle_lists.size(), audio.signals.size()])
	check(audio.vehicle_lists.size() >= 1, "discover() finds the traffic containers (%d lists)" % audio.vehicle_lists.size())

	# 4. Many cars around the courier: only MAX_ENGINES engine voices, on the nearest cars.
	var player: Node3D = game.player
	var fleet: Array[Dictionary] = []
	for i in range(200):
		var body := Node3D.new()
		body.name = "AudioTestCar%d" % i
		game.world.add_child(body)
		var a := float(i) * 0.7
		body.global_position = player.global_position + Vector3(cos(a), 0, sin(a)) * (4.0 + float(i) * 0.4)
		fleet.append({"body": body, "speed": 6.0, "id": "civil_garbage_truck" if i % 5 == 0 else "car_sedan", "half": 2.2})
	audio.register_vehicles(fleet)
	await create_timer(0.6).timeout
	await frames(5)
	var stats := audio.pool_stats()
	print("pools: ", stats)
	var engaged := audio.engine_car.filter(func(c: Dictionary) -> bool: return not c.is_empty())
	check(engaged.size() == CityAudio.MAX_ENGINES and int(stats.engines) == CityAudio.MAX_ENGINES,
		"200 cars -> exactly %d engine voices" % CityAudio.MAX_ENGINES)
	var nearest_ok := true
	for c: Dictionary in engaged:
		nearest_ok = nearest_ok and (c.body as Node3D).global_position.distance_to(audio.listener) < 4.0 + 0.4 * 40.0
	check(nearest_ok, "engine voices sit on the nearest vehicles")
	var heavy_voice := false
	for i in range(audio.engines.size()):
		if not audio.engine_car[i].is_empty() and audio.is_heavy(audio.engine_car[i]):
			heavy_voice = heavy_voice or audio.engines[i].stream == CityAudio.stream("truck_engine")
	check(heavy_voice, "heavy vehicles get the diesel engine loop")
	# One-shot burst and signals.
	for i in range(120):
		audio.one_shot_at("horn_honk", player.global_position + Vector3(randf_range(-20, 20), 1, randf_range(-20, 20)), -20.0)
	var sigs: Array[Node3D] = []
	for i in range(50):
		var n := Node3D.new()
		game.world.add_child(n)
		n.global_position = player.global_position + Vector3(float(i % 10) * 2.0, 3, float(i / 10) * 2.0)
		n.set_meta("walk", i % 2 == 0)
		audio.attach_signal_loop(n)
		sigs.append(n)
	await create_timer(0.4).timeout
	stats = audio.pool_stats()
	print("pools: ", stats)
	check(int(stats.oneshots) <= CityAudio.MAX_ONESHOTS, "120 one-shots use at most %d voices (%d)" % [CityAudio.MAX_ONESHOTS, stats.oneshots])
	check(int(stats.signals_playing) <= CityAudio.MAX_SIGNALS and audio.signal_slot.filter(func(s: Dictionary) -> bool: return not s.is_empty()).size() == CityAudio.MAX_SIGNALS,
		"50 walk signals -> %d signal voices" % CityAudio.MAX_SIGNALS)
	var bound := CityAudio.MAX_ENGINES + CityAudio.MAX_TYRES + CityAudio.MAX_SIGNALS + CityAudio.MAX_ONESHOTS
	check(int(stats.voices_3d) <= bound, "3D voice pool stays bounded (%d <= %d)" % [stats.voices_3d, bound])
	# Walk state switches the loop.
	var slot := -1
	for i in range(audio.signal_slot.size()):
		if not audio.signal_slot[i].is_empty(): slot = i
	var sig := audio.signal_slot[slot].node as Node3D
	sig.set_meta("walk", true)
	await create_timer(0.3).timeout
	var walk_ok: bool = audio.signal_players[slot].stream == CityAudio.stream("ped_signal_walk")
	sig.set_meta("walk", false)
	await create_timer(0.3).timeout
	check(walk_ok and audio.signal_players[slot].stream == CityAudio.stream("ped_signal_wait"), "signal loop follows WALK / WAIT")
	# Vehicles going away free their voices.
	for c: Dictionary in fleet: (c.body as Node3D).queue_free()
	for n in sigs: n.queue_free()
	await create_timer(0.4).timeout
	var left := 0
	for i in range(audio.engines.size()):
		if not audio.engine_car[i].is_empty() and fleet.any(func(c: Dictionary) -> bool: return is_same(c, audio.engine_car[i])): left += 1
	check(left == 0, "freed vehicles release their engine voices")
	# Surfaces and gameplay cue playback.
	var steps: Array[String] = [audio.footstep_for(Vector3(-8, 0.2, 23)), audio.footstep_for(Vector3(-64, 0.0, -145)),
		audio.footstep_for(CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(0, 0.3, 0)), audio.footstep_for(ShopCatalog.LOCATIONS["bikes"] + Vector3(0, 0.1, 0))]
	print("footsteps: ", steps)
	check(steps.all(func(s: String) -> bool: return s.begins_with("footstep_") and FileAccess.file_exists(CityAudio.SFX % s))
		and steps[2] == "footstep_wood" and steps[3] == "footstep_interior", "footsteps pick a surface sound (home wood, shop tiles)")
	for n: String in CityAudio.GAMEPLAY: audio.play_ui(n)
	check(audio.ui_players.size() == CityAudio.MAX_UI, "play_ui() for every gameplay cue stays within %d UI voices" % CityAudio.MAX_UI)
	print("AUDIO: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
