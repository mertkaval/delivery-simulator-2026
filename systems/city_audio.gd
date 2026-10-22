class_name CityAudio
extends Node
## Game audio. Sounds are asked for by name. Names in SoundBank play the ElevenLabs sounds in
## assets/audio/elevenlabs (tools/elevenlabs_sfx: a random take per play where there are several,
## plus a trim that matches the mix); every other name plays the procedural sfx_forge sound in
## assets/audio/sfx (tools/sfx_forge, loudness-levelled by tools/sfx_forge/inspect_sfx.py).
## - Phone/UI cues follow the order state machine (auto_order_cues), plus play_ui() for callers.
## - Bicycle: tyre roll and chain/freewheel loops driven by speed and pedalling, brake squeal,
##   bell; the player's car gets an engine loop.
## - Footsteps by surface (pavement / wet pavement / grass / wooden floor / indoor tiles).
## - Layered ambience crossfaded by place, time of day and weather: city by day, distant hum
##   at night, park birdsong, crickets, breeze / gusts, rain and downpour, restaurant babble.
## - City life: traffic engines (pooled, nearest vehicles only, pitch by speed), wet tyre hiss,
##   horns when the courier blocks a car (rarely in long jams), heavy-vehicle brake squeal and
##   air-brake hiss, pedestrian signal ticks, shop-door bell, restaurant clinks, birds and owls.
## - World API: one_shot_at(), loop_at(), attach_loop(), attach_signal_loop(), register_vehicles().
## CPU: every 3D voice comes from a bounded pool (MAX_*); fixed loops pause beyond their range.

const SFX := "res://assets/audio/sfx/%s.wav"
## Seamless loops (tools/sfx_forge/synth.py LOOPS: written with a smpl loop chunk).
const LOOPS := ["bike_freewheel", "bike_chain", "tyre_roll", "bus_engine_idle", "fountain_water", "city_ambience",
	"park_ambience", "restaurant_ambience", "grill_sizzle", "wind", "rain", "car_engine", "truck_engine",
	"tyre_wet", "ped_signal_walk", "ped_signal_wait", "crickets", "night_city_hum", "wind_soft", "rain_heavy"]
## Gameplay cues for play_ui(name) / one_shot_at(name, pos) (phone, shop, delivery, tutorial).
const GAMEPLAY := ["phone_raise", "phone_lower", "phone_tap", "phone_unlock", "app_open", "app_locked",
	"notify_order", "kiosk_click", "cart_add", "cart_remove", "purchase_complete", "item_pickup", "package_drop",
	"package_place", "bag_zip", "door_knock", "doorbell", "door_open", "photo_shutter", "delivery_success",
	"customer_thanks", "coins", "step_complete", "mission_complete"]
const PARKS := [Vector3(-44, 0, -330), Vector3(44, 0, -330), Vector3(-44, 0, -470), Vector3(44, 0, -470),
	Vector3(-44, 0, -590), Vector3(44, 0, -590), Vector3(-64, 0, -145), Vector3(64, 0, -145)]
## Mix: per-bus trim (dB) as an Amplify effect, so the settings sliders (bus volume) stay in charge.
const BUS_TRIM := {"UI": -2.0, "Ambience": -3.0, "SFX": -1.0}
## Ambience layers and their gain (dB) at full weight.
const LAYERS := {"city_ambience": -10.0, "night_city_hum": -6.0, "park_ambience": -7.0, "restaurant_ambience": -8.0,
	"rain": -6.0, "rain_heavy": -6.0, "wind_soft": -8.0, "wind": -9.0, "crickets": -7.0, "house_tone": -4.0}
const MAX_UI := 4
const MAX_ONESHOTS := 16
const MAX_ENGINES := 8
const MAX_TYRES := 4
const MAX_SIGNALS := 4
const VEHICLE_RANGE := 50.0
const SIGNAL_RANGE := 22.0
const SCAN_INTERVAL := 0.15
## Vehicle containers found by discover(): Array[Dictionary] properties whose items carry
## "body" (Node3D) and "speed" (TrafficDriver state: CityTraffic.drivers, downtown
## population.vehicles, CivicFleet.fleet).
const VEHICLE_CONTAINERS := ["drivers", "vehicles", "fleet"]
const HEAVY_WORDS := ["bus", "truck", "postvan", "fire", "garbage", "ambulance", "tow", "rdserv"]
const PAVED: Array[String] = ["street", "estate", "ring", "downtown", "driveway", "alley", "lane"]

static var streams := {}
var game: Node
var ui_players: Array[AudioStreamPlayer] = []
var ui_next := 0
var ambience := {}
var bike := {}
var last_state := ""
var auto_order_cues := true   ## OFFERED/ACCEPTED/CARRYING/COMPLETED cues; set false to drive them yourself
var step_timer := 0.0
var bird_timer := 3.0
var owl_timer := 40.0
var clink_timer := 2.0
var braking := false
var restaurants: Array[Vector3] = []
var listener := Vector3.ZERO
## 3D voice pools (children of `holder`, a node in the world so they pause with the game).
var holder: Node3D
var oneshots: Array[AudioStreamPlayer3D] = []
var engines: Array[AudioStreamPlayer3D] = []
var engine_car: Array[Dictionary] = []
var tyres: Array[AudioStreamPlayer3D] = []
var tyre_car: Array[Dictionary] = []
var signal_players: Array[AudioStreamPlayer3D] = []
var signal_slot: Array[Dictionary] = []
var fixed_loops: Array[AudioStreamPlayer3D] = []
var vehicle_lists: Array[Array] = []
var extra_lists: Array[Array] = []
var vehicle_state := {}
var heavy_cache := {}
var signals: Array[Dictionary] = []   ## {"node": Node3D, "walk": bool, "probe": Callable, "auto": bool}
var scan_timer := 0.0
var discover_at: Array[float] = [1.0, 6.0]
var clock := 0.0
var honk_cooldown := 0.0
var jam_honk_cooldown := 30.0
var shop_inside := {}
var was_on_floor := true
var was_mounted := false
var thunder_timer := 20.0
var thunder_player: AudioStreamPlayer

## The stream for a sound name: a random take of its SoundBank sound, else the sfx_forge file.
static func stream(sound: String) -> AudioStreamWAV:
	if not streams.has(sound):
		var takes: Array[AudioStreamWAV] = []
		var looped := sound in LOOPS
		if SoundBank.BANK.has(sound):
			var entry: Dictionary = SoundBank.BANK[sound]
			looped = looped or bool(entry.loop)
			for path: String in entry.files: takes.append(load(path) as AudioStreamWAV)
		else:
			takes.append(load(SFX % sound) as AudioStreamWAV)
		for s in takes:
			if s != null and looped and (s.loop_mode == AudioStreamWAV.LOOP_DISABLED or s.loop_end <= s.loop_begin):
				s.loop_mode = AudioStreamWAV.LOOP_FORWARD
				s.loop_begin = 0
				s.loop_end = int(s.get_length() * s.mix_rate)
		streams[sound] = takes
	var list: Array[AudioStreamWAV] = streams[sound]
	return list[0] if list.size() == 1 else list[randi() % list.size()]

## Level trim (dB) for a sound name, so a SoundBank sound sits where the mix expects it.
static func trim(sound: String) -> float:
	return float((SoundBank.BANK[sound] as Dictionary).trim) if SoundBank.BANK.has(sound) else 0.0

## Is there a sound for this name (SoundBank or sfx_forge)?
static func has_sound(sound: String) -> bool:
	return SoundBank.BANK.has(sound) or ResourceLoader.exists(SFX % sound)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("city_audio")
	setup_buses()
	for i in range(MAX_UI):
		var u := AudioStreamPlayer.new()
		u.bus = "UI"
		add_child(u)
		ui_players.append(u)
	for layer: String in LAYERS:
		var p := AudioStreamPlayer.new()
		p.stream = stream(layer)
		p.bus = "Ambience"
		p.volume_db = -80.0
		add_child(p)
		p.play(randf() * p.stream.get_length())
		ambience[layer] = p
	thunder_player = AudioStreamPlayer.new()
	thunder_player.bus = "Ambience"
	add_child(thunder_player)

## UI / Ambience / SFX buses with mix trims, and a limiter on Master so stacked cues never clip.
static func setup_buses() -> void:
	for bus: String in ["UI", "Ambience", "SFX"]:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.bus_count - 1, bus)
			AudioServer.set_bus_send(AudioServer.bus_count - 1, "Master")
		var idx := AudioServer.get_bus_index(bus)
		var has_trim := false
		for e in range(AudioServer.get_bus_effect_count(idx)):
			if AudioServer.get_bus_effect(idx, e) is AudioEffectAmplify: has_trim = true
		if not has_trim:
			var trim := AudioEffectAmplify.new()
			trim.volume_db = float(BUS_TRIM[bus])
			AudioServer.add_bus_effect(idx, trim)
	var master := AudioServer.get_bus_index("Master")
	if AudioServer.get_bus_effect_count(master) == 0 and ClassDB.class_exists("AudioEffectHardLimiter"):
		var limiter: AudioEffect = ClassDB.instantiate("AudioEffectHardLimiter")
		limiter.set("ceiling_db", -0.5)
		AudioServer.add_bus_effect(master, limiter)

func setup(owner_game: Node) -> void:
	game = owner_game
	holder = Node3D.new()
	holder.name = "CityAudio3D"
	game.world.add_child(holder)
	for i in range(MAX_ENGINES):
		engines.append(pooled_player(8.0, VEHICLE_RANGE + 10.0))
		engine_car.append({})
	for i in range(MAX_TYRES):
		tyres.append(pooled_player(5.0, 40.0))
		tyre_car.append({})
	for i in range(MAX_SIGNALS):
		signal_players.append(pooled_player(3.0, SIGNAL_RANGE + 6.0))
		signal_slot.append({})
	var player: Node3D = game.player
	for loop: String in ["tyre_roll", "bike_chain", "bike_freewheel", "car_engine", "bike_wind"]:
		var p := AudioStreamPlayer3D.new()
		p.stream = stream(loop)
		p.bus = "SFX"
		p.volume_db = -80.0
		p.unit_size = 3.0
		player.add_child(p)
		p.position = Vector3(0, 0.4, 0)
		p.play()
		bike[loop] = p
	for i in range(3): restaurants.append(CityCatalog.PICKUPS[i] - Vector3(4, 1, 2))
	if game.world.restaurants != null:
		for r: Dictionary in game.world.restaurants.restaurants:
			restaurants.append(r.door_inside)
			loop_at("grill_sizzle", (r.frame as Transform3D) * Vector3(0, 1.2, -9.6), 2.0, 10.0)
	if game.world.buses != null:
		for bus: Dictionary in game.world.buses.buses: attach_loop(bus.body, "bus_engine_idle", 5.0, 55.0)
	for p: Vector3 in CityMonuments.fountain_spots(): loop_at("fountain_water", p + Vector3(0, 0.8, 0), 4.0, 28.0)
	for r in restaurants: loop_at("grill_sizzle", r + Vector3(-2, 1.2, -5), 2.0, 12.0)

func pooled_player(unit_size: float, max_distance: float) -> AudioStreamPlayer3D:
	var p := AudioStreamPlayer3D.new()
	p.bus = "SFX"
	p.unit_size = unit_size
	p.max_distance = max_distance
	p.attenuation_filter_cutoff_hz = 6000.0
	holder.add_child(p)
	return p

# ----------------------------------------------------------------------------- public API

## 2D cue on the UI bus (phone, shop, menus). Overlapping cues use separate voices.
func play_ui(sound: String, volume_db: float = -4.0, pitch: float = 1.0) -> void:
	var s := stream(sound)
	if s == null: return
	var u: AudioStreamPlayer = null
	for candidate in ui_players:
		if not candidate.playing:
			u = candidate
			break
	if u == null:
		u = ui_players[ui_next % ui_players.size()]
		ui_next += 1
	u.stream = s
	u.volume_db = volume_db + trim(sound)
	u.pitch_scale = pitch
	u.play()

## Fixed positional loop (fountains, kitchens, idling engines). Paused while out of range.
func loop_at(sound: String, at: Vector3, unit_size: float, max_distance: float, parent: Node = null) -> AudioStreamPlayer3D:
	var p := AudioStreamPlayer3D.new()
	p.stream = stream(sound)
	p.bus = "SFX"
	p.volume_db = trim(sound)
	p.unit_size = unit_size
	p.max_distance = max_distance
	p.position = at
	(parent if parent != null else game.world as Node).add_child(p)
	p.play(randf() * p.stream.get_length())
	fixed_loops.append(p)
	return p

## Loop that follows a moving node (buses, cars).
func attach_loop(node: Node3D, sound: String, unit_size: float = 5.0, max_distance: float = 60.0) -> AudioStreamPlayer3D:
	return loop_at(sound, Vector3(0, 1, 0), unit_size, max_distance, node)

## One-shot positional sound from a bounded pool: skipped beyond max_distance; when every
## voice is busy the farthest one is stolen (if it is farther than this sound).
func one_shot_at(sound: String, at: Vector3, volume_db: float = 0.0, unit_size: float = 4.0, pitch: float = 1.0, max_distance: float = 80.0) -> void:
	if game == null or holder == null: return
	if at.distance_to(listener) > max_distance: return
	var p: AudioStreamPlayer3D = null
	for candidate in oneshots:
		if not candidate.playing:
			p = candidate
			break
	if p == null and oneshots.size() < MAX_ONESHOTS:
		p = pooled_player(unit_size, max_distance)
		oneshots.append(p)
	if p == null:
		var far := at.distance_to(listener)
		for candidate in oneshots:
			var d := candidate.global_position.distance_to(listener)
			if d > far:
				far = d
				p = candidate
	if p == null: return
	p.stop()
	p.stream = stream(sound)
	p.unit_size = unit_size
	p.max_distance = max_distance
	p.volume_db = volume_db + trim(sound)
	p.pitch_scale = pitch
	p.global_position = at
	p.play()

## Pedestrian signal sound (for the streets agent). Register one node per push-button / signal
## head; CityAudio loops ped_signal_wait (slow tick) or ped_signal_walk (rapid tick) from it,
## for the nearest MAX_SIGNALS within SIGNAL_RANGE only. Give the state one of three ways:
##   attach_signal_loop(node, func() -> bool: return walk_phase)   # polled ~7x a second
##   set_signal_walk(node, true / false)                            # push on each change
##   node.set_meta("walk", true / false)                            # read when no probe is set
## Registering near (<3 m) one of CityAudio's own fallback signals replaces it.
func attach_signal_loop(node: Node3D, is_walk: Callable = Callable(), auto := false) -> void:
	if node == null: return
	for s in signals:
		if is_same(s.node, node): return
		if auto and not bool(s.auto) and signal_near(s, node): return
	if not auto:
		for i in range(signals.size() - 1, -1, -1):
			var s := signals[i]
			if bool(s.auto) and (not is_instance_valid(s.node) or signal_near(s, node)):
				signals.remove_at(i)
	signals.append({"node": node, "walk": false, "probe": is_walk, "auto": auto})

func signal_near(s: Dictionary, node: Node3D) -> bool:
	if not is_instance_valid(s.node) or not node.is_inside_tree() or not (s.node as Node3D).is_inside_tree(): return false
	return (s.node as Node3D).global_position.distance_to(node.global_position) < 3.0

func set_signal_walk(node: Node3D, walk: bool) -> void:
	for s in signals:
		if is_same(s.node, node): s.walk = walk

func detach_signal_loop(node: Node3D) -> void:
	for i in range(signals.size() - 1, -1, -1):
		if is_same(signals[i].node, node): signals.remove_at(i)

## Add a list of TrafficDriver-style vehicle dictionaries ({"body", "speed", "id"}) by reference.
func register_vehicles(list: Array) -> void:
	for l in extra_lists:
		if is_same(l, list): return
	extra_lists.append(list)
	if not vehicle_lists.any(func(x: Array) -> bool: return is_same(x, list)): vehicle_lists.append(list)

## Voice counts (tests / debugging).
func pool_stats() -> Dictionary:
	var busy := func(pool: Array[AudioStreamPlayer3D]) -> int: return pool.filter(func(p: AudioStreamPlayer3D) -> bool: return p.playing).size()
	return {"oneshots": oneshots.size(), "oneshots_playing": busy.call(oneshots), "engines": engines.size(),
		"engines_playing": busy.call(engines), "tyres_playing": busy.call(tyres), "signals": signals.size(),
		"signals_playing": busy.call(signal_players), "voices_3d": holder.get_child_count() if holder else 0,
		"vehicle_lists": vehicle_lists.size()}

# ----------------------------------------------------------------------------- frame update

func _process(delta: float) -> void:
	if game == null or game.session == null: return
	if auto_order_cues: order_cues()
	if get_tree().paused:
		for p: AudioStreamPlayer3D in bike.values(): p.volume_db = -80.0
		return
	clock += delta
	var player: CourierPlayer = game.player
	var camera := get_viewport().get_camera_3d()
	listener = camera.global_position if camera != null else player.global_position
	if not discover_at.is_empty() and clock >= discover_at[0]:
		discover_at.pop_front()
		discover()
	var hour: float = game.session.hour()
	ride_sounds(player, delta)
	walk_sounds(player, delta)
	mix_ambience(player.global_position, hour, delta)
	ambient_birds(player.global_position, hour, delta)
	restaurant_life(player.global_position, delta)
	shop_doors(player.global_position)
	honk_cooldown -= delta
	jam_honk_cooldown -= delta
	scan_timer -= delta
	if scan_timer <= 0.0:
		scan_timer = SCAN_INTERVAL
		scan_vehicles(SCAN_INTERVAL)
		scan_signals()
		cull_fixed_loops()
	drive_vehicle_voices()

func order_cues() -> void:
	var state: String = game.session.order.get("state", "")
	if state == last_state: return
	match state:
		"OFFERED": play_ui("ui_notification")
		"ACCEPTED": play_ui("ui_accept")
		"CARRYING": play_ui("cash_register", -8.0)
		"COMPLETED": play_ui("delivery_complete")
		_:
			if last_state == "OFFERED": play_ui("ui_reject", -6.0)
	last_state = state

func ride_sounds(player: CourierPlayer, delta: float) -> void:
	var speed := absf(player.riding_speed) if player.mounted else 0.0
	var car := ShopCatalog.is_car(game.session.active_vehicle)
	var pedalling := player.mounted and Input.get_axis("move_back", "move_forward") > 0.1
	if player.mounted != was_mounted:
		was_mounted = player.mounted
		if not car: one_shot_at("bike_mount" if player.mounted else "bike_dismount", player.global_position + Vector3(0, 0.6, 0), -6.0, 3.0)
	var roll_db := -80.0 if speed < 0.3 else lerpf(-26.0, -8.0, clampf(speed / 9.0, 0.0, 1.0)) + trim("tyre_roll")
	bike.tyre_roll.volume_db = move_toward(bike.tyre_roll.volume_db, roll_db, 120.0 * delta)
	bike.tyre_roll.pitch_scale = clampf(0.75 + speed * 0.05, 0.75, 1.4)
	var wind_db := -80.0 if speed < 4.0 or car else lerpf(-24.0, -10.0, clampf((speed - 4.0) / 8.0, 0.0, 1.0)) + trim("bike_wind")
	bike.bike_wind.volume_db = move_toward(bike.bike_wind.volume_db, wind_db, 60.0 * delta)
	var chain_db := -14.0 + trim("bike_chain") if pedalling and speed > 0.5 and not car else -80.0
	var free_db := -12.0 + trim("bike_freewheel") if not pedalling and speed > 0.8 and not car else -80.0
	bike.bike_chain.volume_db = move_toward(bike.bike_chain.volume_db, chain_db, 200.0 * delta)
	bike.bike_chain.pitch_scale = clampf(0.7 + speed * 0.06, 0.7, 1.5)
	bike.bike_freewheel.volume_db = move_toward(bike.bike_freewheel.volume_db, free_db, 200.0 * delta)
	bike.bike_freewheel.pitch_scale = clampf(0.5 + speed * 0.12, 0.5, 1.8)
	var load := clampf(speed / 14.0, 0.0, 1.0)
	var engine_db := lerpf(-16.0, -6.0, load) if car and player.mounted else -80.0
	bike.car_engine.volume_db = move_toward(bike.car_engine.volume_db, engine_db, 90.0 * delta)
	bike.car_engine.pitch_scale = move_toward(bike.car_engine.pitch_scale, 0.75 + load * 0.85, 2.0 * delta)
	var brake_now := player.mounted and Input.is_action_pressed("jump") and speed > 2.5 and not car
	if brake_now and not braking: one_shot_at("brake_squeal", player.global_position + Vector3(0, 0.5, 0), -10.0)
	braking = brake_now
	if player.mounted and not car and InputMap.has_action("bell") and Input.is_action_just_pressed("bell"):
		one_shot_at("bike_bell", player.global_position + Vector3(0, 1.0, 0) - player.global_basis.z * 0.6, -6.0)

func walk_sounds(player: CourierPlayer, delta: float) -> void:
	var speed := Vector2(player.velocity.x, player.velocity.z).length()
	# Landing after a jump or a drop: harder falls land louder.
	var on_floor := player.is_on_floor()
	if on_floor and not was_on_floor and not player.mounted and player.last_fall_speed > 3.0:
		var hard := clampf((player.last_fall_speed - 3.0) / 6.0, 0.0, 1.0)
		one_shot_at("jump_land", player.global_position, lerpf(-18.0, -9.0, hard), 2.0, randf_range(0.92, 1.05), 25.0)
	was_on_floor = on_floor
	# With a visible body the steps land on its foot contacts (PlayerAvatar).
	if player.avatar != null and player.avatar.ready_ok:
		for at in player.take_footsteps():
			one_shot_at(step_sound(at, speed), at, randf_range(-20.0, -17.0), 2.0, randf_range(0.9, 1.1), 25.0)
		return
	if player.mounted or not on_floor: return
	if speed < 0.6:
		step_timer = 0.0
		return
	step_timer -= delta
	if step_timer <= 0.0:
		step_timer = 1.6 / maxf(speed, 1.0)
		var at := player.global_position
		one_shot_at(step_sound(at, speed), at, randf_range(-20.0, -17.0), 2.0, randf_range(0.9, 1.1), 25.0)

## Footstep for the surface, with the running takes on pavement at running speed.
func step_sound(at: Vector3, speed: float) -> String:
	var surface := footstep_for(at)
	return "footstep_run" if surface == "footstep_concrete" and speed > CourierPlayer.RUN_SPEED + 0.8 else surface

## Footstep sound for the surface at `at`.
func footstep_for(at: Vector3) -> String:
	if in_home(at): return "footstep_wood"
	if in_shop(at) != "" or restaurant_weight(at) > 0.5: return "footstep_interior"
	var paved := at.y > 0.07 or at.x > 200.0 or PropPlacer.clearance(Vector2(at.x, at.z), PAVED) < 3.6
	if not paved: return "footstep_grass"
	var wet: float = game.world.weather.wetness if game.world.weather != null else 0.0
	return "footstep_wet" if wet > 0.45 else "footstep_concrete"

func in_home(at: Vector3) -> bool:
	var d := at - CedarNeighborhood.CEDAR_HOME_ORIGIN
	return absf(d.x) < 4.6 and d.z > -5.5 and d.z < 4.8

## Shop id whose interior contains `at` ("" outside).
func in_shop(at: Vector3) -> String:
	for id: String in ShopCatalog.LOCATIONS:
		var c: Vector3 = ShopCatalog.LOCATIONS[id]
		if absf(at.x - c.x) < 7.0 and at.z > c.z - 5.0 and at.z < c.z + 5.0: return id
	return ""

func restaurant_weight(at: Vector3) -> float:
	var inside := 0.0
	for r in restaurants: inside = maxf(inside, 1.0 - clampf((at.distance_to(r) - 4.0) / 4.0, 0.0, 1.0))
	return inside

func mix_ambience(at: Vector3, hour: float, delta: float) -> void:
	var park := 0.0
	for p: Vector3 in PARKS: park = maxf(park, 1.0 - clampf((Vector2(at.x, at.z).distance_to(Vector2(p.x, p.z)) - 12.0) / 25.0, 0.0, 1.0))
	var dining := restaurant_weight(at)
	var inside := maxf(dining, 1.0 if in_shop(at) != "" or in_home(at) else 0.0)
	var downtown := clampf((at.x - 100.0) / 60.0, 0.0, 1.0)
	var day := smoothstep(5.0, 7.0, hour) * (1.0 - smoothstep(20.0, 22.0, hour))
	var night := 1.0 - day
	var city := (0.55 + 0.45 * downtown) * (1.0 - park * 0.6) * (1.0 - inside * 0.8)
	var weather: WeatherSystem = game.world.weather
	var rain_amount: float = weather.rain if weather != null else 0.0
	var overcast: float = weather.overcast if weather != null else 0.0
	var outdoors := 1.0 - inside * 0.9
	var grassy := maxf(park, (1.0 - downtown) * 0.45)
	var targets := {
		"city_ambience": city * (0.3 + 0.7 * day),
		"night_city_hum": city * night * 0.9,
		"park_ambience": park * 0.8 * (1.0 - rain_amount * 0.7) * (0.15 + 0.85 * day),
		"crickets": night * grassy * (1.0 - rain_amount) * outdoors,
		"restaurant_ambience": dining,
		"wind_soft": (0.35 + 0.4 * overcast) * outdoors,
		"wind": clampf((overcast - 0.4) * 1.2 + rain_amount * 0.3, 0.0, 1.0) * outdoors,
		"rain": rain_amount * (1.0 - inside * 0.6),
		"rain_heavy": clampf((rain_amount - 0.5) * 2.0, 0.0, 1.0) * (1.0 - inside * 0.6),
		"house_tone": 1.0 if in_home(at) else 0.0}
	for layer: String in targets:
		var linear: float = targets[layer]
		var db := -80.0 if linear < 0.01 else linear_to_db(linear) + float(LAYERS[layer]) + trim(layer)
		var p: AudioStreamPlayer = ambience[layer]
		p.volume_db = move_toward(p.volume_db, db, 40.0 * delta)
	# Thunder now and then in heavy weather, muffled indoors.
	thunder_timer -= delta
	if thunder_timer <= 0.0:
		thunder_timer = randf_range(25.0, 70.0)
		if rain_amount > 0.6 and overcast > 0.5 and not thunder_player.playing:
			thunder_player.stream = stream("thunder")
			thunder_player.volume_db = randf_range(-12.0, -4.0) + trim("thunder") - inside * 8.0
			thunder_player.pitch_scale = randf_range(0.85, 1.05)
			thunder_player.play()

func ambient_birds(at: Vector3, hour: float, delta: float) -> void:
	# Songbirds in the trees by day (a dawn chorus, quieter dusk), owls at night in the suburbs.
	var rain_amount: float = game.world.weather.rain if game.world.weather != null else 0.0
	var night := hour < 5.0 or hour >= 21.5
	owl_timer -= delta
	if night and owl_timer <= 0.0:
		owl_timer = randf_range(35.0, 80.0)
		if at.x < 120.0 and rain_amount < 0.4:
			var dir := Vector3.FORWARD.rotated(Vector3.UP, randf() * TAU)
			one_shot_at("owl_hoot", at + dir * randf_range(22.0, 38.0) + Vector3(0, 8, 0), -6.0, 10.0, randf_range(0.95, 1.05), 90.0)
	bird_timer -= delta
	if bird_timer > 0.0: return
	if night or rain_amount > 0.5:
		bird_timer = randf_range(6.0, 12.0)
		return
	var dawn := hour < 9.0
	var dusk := hour >= 18.0
	bird_timer = (randf_range(2.5, 6.0) if dawn else (randf_range(7.0, 15.0) if dusk else randf_range(4.0, 11.0)))
	bird_timer *= (2.5 if at.x > 120.0 else 1.0) * (1.0 + rain_amount * 2.0)
	var pick := randf()
	var sound := "blackbird_song" if (dawn or dusk) and pick < 0.35 else ("songbird_trill" if pick < 0.5 else "bird_chirp")
	var offset := Vector3(randf_range(-18, 18), randf_range(4, 9), randf_range(-18, 18))
	one_shot_at(sound, at + offset, -12.0, 6.0, randf_range(0.9, 1.12), 60.0)

func restaurant_life(at: Vector3, delta: float) -> void:
	# Cutlery, plates and the odd pan from around the room while the courier is inside.
	if restaurant_weight(at) < 0.5: return
	clink_timer -= delta
	if clink_timer > 0.0: return
	clink_timer = randf_range(1.2, 4.0)
	var pick := randf()
	var sound := "cutlery_clink" if pick < 0.55 else ("plate_clink" if pick < 0.88 else "pan_clank")
	var dir := Vector3.FORWARD.rotated(Vector3.UP, randf() * TAU)
	one_shot_at(sound, at + dir * randf_range(2.0, 6.0) + Vector3(0, 1.0, 0), -12.0, 3.0, randf_range(0.93, 1.07), 20.0)

func shop_doors(at: Vector3) -> void:
	var now := in_shop(at)
	for id: String in ShopCatalog.LOCATIONS:
		var inside := id == now
		if inside and not bool(shop_inside.get(id, false)):
			one_shot_at("shop_door_chime", (ShopCatalog.LOCATIONS[id] as Vector3) + Vector3(0, 2.6, 5.0), -8.0, 4.0)
		shop_inside[id] = inside

# ----------------------------------------------------------------------------- traffic

## Find the traffic containers and the existing walk signals in the world (runs a couple of
## times after start; other systems can also call register_vehicles / attach_signal_loop).
func discover() -> void:
	vehicle_lists.clear()
	vehicle_lists.append_array(extra_lists)
	var stack: Array[Node] = [game.world]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n.get_script() != null:
			for prop: String in VEHICLE_CONTAINERS:
				var v: Variant = n.get(prop)
				if v is Array and not (v as Array).is_empty() and (v as Array)[0] is Dictionary:
					var first: Dictionary = (v as Array)[0]
					if first.has("body") and first.has("speed") and not vehicle_lists.any(func(x: Array) -> bool: return is_same(x, v)):
						vehicle_lists.append(v as Array)
			fallback_signals(n)
		stack.append_array(n.get_children())

## Walk-signal sound for the crossings that already exist (downtown WALK/WAIT labels, Cedar
## Lane crossing lights). Signals registered by the streets agent replace these.
func fallback_signals(n: Node) -> void:
	var labels: Variant = n.get("crossing_labels")
	if labels is Array:
		for label: Variant in labels:
			if label is Label3D:
				var l := label as Label3D
				attach_signal_loop(l, func() -> bool: return is_instance_valid(l) and l.text.begins_with("WALK"), true)
	var lights: Variant = n.get("signals")
	if lights is Array and n.has_method("crossing_red"):
		for light: Variant in lights:
			if light is Node3D:
				attach_signal_loop(light as Node3D, func() -> bool: return is_instance_valid(n) and bool(n.call("crossing_red")), true)

func is_heavy(car: Dictionary) -> bool:
	var id := str(car.get("id", ""))
	if not heavy_cache.has(id):
		var heavy := false
		for w: String in HEAVY_WORDS:
			if id.contains(w): heavy = true
		if not heavy and id != "" and VehicleCatalog.exists(id): heavy = VehicleCatalog.turns_tight(id)
		heavy_cache[id] = heavy
	return bool(heavy_cache[id])

func scan_vehicles(dt: float) -> void:
	var near: Array[Dictionary] = []
	var dist: Array[float] = []
	for list in vehicle_lists:
		for item: Variant in list:
			if not item is Dictionary: continue
			var car: Dictionary = item
			var b: Variant = car.get("body")
			if not is_instance_valid(b) or not b is Node3D: continue
			var body := b as Node3D
			if not body.is_visible_in_tree(): continue
			var d := body.global_position.distance_to(listener)
			if d > VEHICLE_RANGE: continue
			near.append(car)
			dist.append(d)
			vehicle_events(car, body, d, dt)
	var order: Array[int] = []
	for i in range(near.size()): order.append(i)
	order.sort_custom(func(a: int, b: int) -> bool: return dist[a] < dist[b])
	var want_engines: Array[Dictionary] = []
	var want_tyres: Array[Dictionary] = []
	var wet: float = game.world.weather.wetness if game.world.weather != null else 0.0
	for i in order:
		if want_engines.size() < MAX_ENGINES: want_engines.append(near[i])
		if wet > 0.05 and want_tyres.size() < MAX_TYRES and absf(float(near[i].get("speed", 0.0))) > 2.0 and dist[i] < 35.0:
			want_tyres.append(near[i])
	for slot in assign(engines, engine_car, want_engines):
		var p := engines[slot]
		p.stream = stream("truck_engine" if is_heavy(engine_car[slot]) else "car_engine")
		p.volume_db = -30.0
		p.play(randf() * p.stream.get_length())
	for slot in assign(tyres, tyre_car, want_tyres):
		tyres[slot].stream = stream("tyre_wet")
		tyres[slot].volume_db = -40.0
		tyres[slot].play(randf() * 3.5)
	if vehicle_state.size() > 400: vehicle_state.clear()

## Keep pool slots on the wanted items (no restart for ones already sounding); returns the
## slots that were given a new item.
func assign(pool: Array[AudioStreamPlayer3D], owners: Array[Dictionary], wanted: Array[Dictionary]) -> Array[int]:
	var fresh: Array[int] = []
	for i in range(pool.size()):
		if owners[i].is_empty(): continue
		if not wanted.any(func(w: Dictionary) -> bool: return is_same(w, owners[i])):
			owners[i] = {}
			pool[i].stop()
	for w in wanted:
		if owners.any(func(o: Dictionary) -> bool: return is_same(o, w)): continue
		for i in range(pool.size()):
			if owners[i].is_empty():
				owners[i] = w
				fresh.append(i)
				break
	return fresh

## Per-frame: engine and tyre voices follow their vehicles; pitch and level follow speed.
func drive_vehicle_voices() -> void:
	var wet: float = game.world.weather.wetness if game.world.weather != null else 0.0
	for i in range(engines.size()):
		var car := engine_car[i]
		if car.is_empty(): continue
		var b: Variant = car.get("body")
		if not is_instance_valid(b):
			engine_car[i] = {}
			engines[i].stop()
			continue
		var p := engines[i]
		var speed := absf(float(car.get("speed", 0.0)))
		var load := clampf(speed / 11.0, 0.0, 1.0)
		var heavy := is_heavy(car)
		p.global_position = (b as Node3D).global_position + Vector3(0, 0.7, 0)
		p.pitch_scale = (0.85 + load * 0.45) if heavy else (0.8 + load * 0.7)
		p.volume_db = move_toward(p.volume_db, lerpf(-11.0, -4.0, load) if heavy else lerpf(-15.0, -7.0, load), 1.5)
	for i in range(tyres.size()):
		var car := tyre_car[i]
		if car.is_empty(): continue
		var b: Variant = car.get("body")
		if not is_instance_valid(b):
			tyre_car[i] = {}
			tyres[i].stop()
			continue
		var speed := absf(float(car.get("speed", 0.0)))
		var amount := clampf(wet, 0.0, 1.0) * clampf(speed / 9.0, 0.0, 1.0)
		tyres[i].global_position = (b as Node3D).global_position + Vector3(0, 0.3, 0)
		tyres[i].pitch_scale = clampf(0.8 + speed * 0.03, 0.8, 1.3)
		tyres[i].volume_db = move_toward(tyres[i].volume_db, -80.0 if amount < 0.02 else linear_to_db(amount) - 4.0, 2.0)

## Horns, brake squeal and air-brake hiss for one nearby vehicle (called every scan).
func vehicle_events(car: Dictionary, body: Node3D, d: float, dt: float) -> void:
	var speed := absf(float(car.get("speed", 0.0)))
	var key := body.get_instance_id()
	if not vehicle_state.has(key):
		vehicle_state[key] = {"prev": speed, "stopped": 0.0, "honk": 0.0, "squealed": true, "hissed": true}
	var st: Dictionary = vehicle_state[key]
	var prev: float = st.prev
	st.prev = speed
	st.honk = maxf(0.0, float(st.honk) - dt)
	st.stopped = float(st.stopped) + dt if speed < 0.25 else 0.0
	var heavy := is_heavy(car)
	var at := body.global_position + Vector3(0, 1.0, 0)
	if heavy:
		if speed > 4.0:
			st.squealed = false
			st.hissed = false
		if not bool(st.squealed) and prev > 2.5 and prev - speed > 0.45 and d < 40.0:
			st.squealed = true
			if randf() < 0.55: one_shot_at("truck_brake_squeal", at, -6.0, 6.0, randf_range(0.92, 1.08), 60.0)
		if not bool(st.hissed) and prev > 0.3 and speed < 0.05 and d < 40.0:
			st.hissed = true
			one_shot_at("air_brake_hiss", at, -10.0, 5.0, randf_range(0.95, 1.05), 50.0)
	if float(st.honk) > 0.0 or float(st.stopped) < 2.0: return
	var horn_pitch := randf_range(0.72, 0.8) if heavy else randf_range(0.95, 1.08)
	if honk_cooldown <= 0.0 and player_blocks(car, body):
		one_shot_at("horn_honk", at, -4.0, 7.0, horn_pitch, 70.0)
		st.honk = 9.0
		honk_cooldown = 3.0
	elif float(st.stopped) > 12.0 and jam_honk_cooldown <= 0.0 and d < 45.0 and randf() < 0.01:
		one_shot_at("horn_long", at, -9.0, 7.0, horn_pitch, 70.0)
		st.honk = 20.0
		jam_honk_cooldown = randf_range(35.0, 70.0)

## Is the courier standing right in front of this vehicle?
func player_blocks(car: Dictionary, body: Node3D) -> bool:
	var to: Vector3 = (game.player as Node3D).global_position - body.global_position
	var fwd := -body.global_basis.z
	var along := to.dot(fwd)
	var lateral := absf(to.dot(fwd.cross(Vector3.UP).normalized()))
	return along > 0.0 and along < float(car.get("half", 2.3)) + 6.0 and lateral < 1.8

# ----------------------------------------------------------------------------- signals & culling

func scan_signals() -> void:
	var cand: Array[Dictionary] = []
	var dist: Array[float] = []
	for i in range(signals.size() - 1, -1, -1):
		var s := signals[i]
		if not is_instance_valid(s.node):
			signals.remove_at(i)
			continue
		var node := s.node as Node3D
		if not node.is_inside_tree(): continue
		var d := node.global_position.distance_to(listener)
		if d > SIGNAL_RANGE: continue
		var probe: Callable = s.probe
		if probe.is_valid(): s.walk = bool(probe.call())
		elif node.has_meta("walk"): s.walk = bool(node.get_meta("walk"))
		cand.append(s)
		dist.append(d)
	var order: Array[int] = []
	for i in range(cand.size()): order.append(i)
	order.sort_custom(func(a: int, b: int) -> bool: return dist[a] < dist[b])
	var wanted: Array[Dictionary] = []
	for i in order:
		if wanted.size() < MAX_SIGNALS: wanted.append(cand[i])
	assign(signal_players, signal_slot, wanted)
	for i in range(signal_players.size()):
		var s := signal_slot[i]
		if s.is_empty(): continue
		var p := signal_players[i]
		var sound := "ped_signal_walk" if bool(s.walk) else "ped_signal_wait"
		var want := stream(sound)
		p.global_position = (s.node as Node3D).global_position
		if p.stream != want or not p.playing:
			p.stream = want
			p.volume_db = (-6.0 if bool(s.walk) else -9.0) + trim(sound)
			p.play()

func cull_fixed_loops() -> void:
	for i in range(fixed_loops.size() - 1, -1, -1):
		var p := fixed_loops[i]
		if not is_instance_valid(p):
			fixed_loops.remove_at(i)
			continue
		if not p.is_inside_tree() or p.max_distance <= 0.0: continue
		p.stream_paused = p.global_position.distance_to(listener) > p.max_distance + 4.0
