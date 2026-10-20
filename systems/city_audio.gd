class_name CityAudio
extends Node
## Game audio. Sounds come from tools/sfx_forge (procedural, free, offline) in assets/audio/sfx.
## - Phone/UI cues follow the order state machine (no call-site wiring needed).
## - Bicycle: tyre roll and chain/freewheel loops driven by speed and pedalling, brake squeal, bell.
## - Footsteps when walking; layered ambience (city / park / restaurant) crossfaded by location.
## - World API for other systems: loop_at(), one_shot_at(), attach_loop().

const SFX := "res://assets/audio/sfx/%s.wav"
const LOOPS := ["bike_freewheel", "bike_chain", "tyre_roll", "bus_engine_idle", "fountain_water", "city_ambience",
	"park_ambience", "restaurant_ambience", "grill_sizzle", "wind", "rain"]
const PARKS := [Vector3(-44, 0, -330), Vector3(44, 0, -330), Vector3(-44, 0, -470), Vector3(44, 0, -470),
	Vector3(-44, 0, -590), Vector3(44, 0, -590), Vector3(-64, 0, -145), Vector3(64, 0, -145)]

static var streams := {}
var game: Node
var ui: AudioStreamPlayer
var ambience := {}
var bike := {}
var last_state := ""
var step_timer := 0.0
var bird_timer := 3.0
var braking := false
var restaurants: Array[Vector3] = []

static func stream(sound: String) -> AudioStreamWAV:
	if not streams.has(sound):
		var s: AudioStreamWAV = load(SFX % sound)
		if s != null and sound in LOOPS:
			s.loop_mode = AudioStreamWAV.LOOP_FORWARD
			s.loop_begin = 0
			s.loop_end = int(s.get_length() * s.mix_rate)
		streams[sound] = s
	return streams[sound]

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("city_audio")
	for bus in ["UI", "Ambience", "SFX"]:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.bus_count - 1, bus)
	ui = AudioStreamPlayer.new()
	ui.bus = "UI"
	add_child(ui)
	for layer in ["city_ambience", "park_ambience", "restaurant_ambience", "rain"]:
		var p := AudioStreamPlayer.new()
		p.stream = stream(layer)
		p.bus = "Ambience"
		p.volume_db = -80.0
		add_child(p)
		p.play()
		ambience[layer] = p

func setup(owner_game: Node) -> void:
	game = owner_game
	var player: Node3D = game.player
	for loop in ["tyre_roll", "bike_chain", "bike_freewheel"]:
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
		for r in game.world.restaurants.restaurants:
			restaurants.append(r.door_inside + Vector3(0, 0, 0))
			loop_at("grill_sizzle", (r.frame as Transform3D) * Vector3(0, 1.2, -9.6), 2.0, 10.0)
	if game.world.buses != null:
		for bus in game.world.buses.buses: attach_loop(bus.body, "bus_engine_idle", 5.0, 55.0)
	for p in PARKS: loop_at("fountain_water", p + Vector3(4, 0.8, -5), 4.0, 28.0)
	for r in restaurants: loop_at("grill_sizzle", r + Vector3(-2, 1.2, -5), 2.0, 12.0)

func play_ui(sound: String, volume_db: float = -4.0) -> void:
	ui.stream = stream(sound)
	ui.volume_db = volume_db
	ui.play()

## Fixed positional loop (fountains, kitchens, idling engines).
func loop_at(sound: String, at: Vector3, unit_size: float, max_distance: float, parent: Node = null) -> AudioStreamPlayer3D:
	var p := AudioStreamPlayer3D.new()
	p.stream = stream(sound)
	p.bus = "SFX"
	p.unit_size = unit_size
	p.max_distance = max_distance
	p.position = at
	(parent if parent != null else game.world as Node).add_child(p)
	p.play()
	return p

## Loop that follows a moving node (buses, cars).
func attach_loop(node: Node3D, sound: String, unit_size: float = 5.0, max_distance: float = 60.0) -> AudioStreamPlayer3D:
	return loop_at(sound, Vector3(0, 1, 0), unit_size, max_distance, node)

## One-shot positional sound that frees itself.
func one_shot_at(sound: String, at: Vector3, volume_db: float = 0.0, unit_size: float = 4.0, pitch: float = 1.0) -> void:
	if game == null: return
	var p := AudioStreamPlayer3D.new()
	p.stream = stream(sound)
	p.bus = "SFX"
	p.unit_size = unit_size
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.max_distance = 80.0
	game.world.add_child(p)
	p.global_position = at
	p.finished.connect(p.queue_free)
	p.play()

func _process(delta: float) -> void:
	if game == null or game.session == null: return
	var paused := get_tree().paused
	order_cues()
	if paused:
		for p in bike.values(): p.volume_db = -80.0
		return
	var player: CourierPlayer = game.player
	ride_sounds(player, delta)
	walk_sounds(player, delta)
	mix_ambience(player.global_position, delta)
	ambient_birds(player.global_position, delta)

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
	var roll_db := -80.0 if speed < 0.3 else lerpf(-26.0, -8.0, clampf(speed / 9.0, 0.0, 1.0))
	bike.tyre_roll.volume_db = move_toward(bike.tyre_roll.volume_db, roll_db, 120.0 * delta)
	bike.tyre_roll.pitch_scale = clampf(0.75 + speed * 0.05, 0.75, 1.4)
	var chain_db := -14.0 if pedalling and speed > 0.5 and not car else -80.0
	var free_db := -12.0 if not pedalling and speed > 0.8 and not car else -80.0
	bike.bike_chain.volume_db = move_toward(bike.bike_chain.volume_db, chain_db, 200.0 * delta)
	bike.bike_chain.pitch_scale = clampf(0.7 + speed * 0.06, 0.7, 1.5)
	bike.bike_freewheel.volume_db = move_toward(bike.bike_freewheel.volume_db, free_db, 200.0 * delta)
	bike.bike_freewheel.pitch_scale = clampf(0.5 + speed * 0.12, 0.5, 1.8)
	var brake_now := player.mounted and Input.is_action_pressed("jump") and speed > 2.5 and not car
	if brake_now and not braking: one_shot_at("brake_squeal", player.global_position + Vector3(0, 0.5, 0), -10.0)
	braking = brake_now
	if player.mounted and not car and InputMap.has_action("bell") and Input.is_action_just_pressed("bell"):
		one_shot_at("bike_bell", player.global_position + Vector3(0, 1.0, 0) - player.global_basis.z * 0.6, -6.0)

func walk_sounds(player: CourierPlayer, delta: float) -> void:
	if player.mounted or not player.is_on_floor(): return
	var speed := Vector2(player.velocity.x, player.velocity.z).length()
	if speed < 0.6:
		step_timer = 0.0
		return
	step_timer -= delta
	if step_timer <= 0.0:
		step_timer = 1.6 / maxf(speed, 1.0)
		one_shot_at("footstep_concrete", player.global_position, -16.0, 2.0, randf_range(0.9, 1.1))

func mix_ambience(at: Vector3, delta: float) -> void:
	var park := 0.0
	for p in PARKS: park = maxf(park, 1.0 - clampf((Vector2(at.x, at.z).distance_to(Vector2(p.x, p.z)) - 12.0) / 25.0, 0.0, 1.0))
	var inside := 0.0
	for r in restaurants: inside = maxf(inside, 1.0 - clampf((at.distance_to(r) - 4.0) / 4.0, 0.0, 1.0))
	var downtown := clampf((at.x - 100.0) / 60.0, 0.0, 1.0)
	var city := (0.55 + 0.45 * downtown) * (1.0 - park * 0.6) * (1.0 - inside * 0.8)
	var rain_amount: float = game.world.weather.rain if game.world.weather != null else 0.0
	var targets := {"city_ambience": city, "park_ambience": park * 0.8 * (1.0 - rain_amount * 0.7), "restaurant_ambience": inside,
		"rain": rain_amount * (1.0 - inside * 0.6) * 1.1}
	for layer in targets:
		var linear: float = targets[layer]
		var db := -80.0 if linear < 0.01 else linear_to_db(linear) - 10.0
		ambience[layer].volume_db = move_toward(ambience[layer].volume_db, db, 40.0 * delta)

func ambient_birds(at: Vector3, delta: float) -> void:
	# Songbirds in trees around the player, more in the suburbs and parks than downtown.
	bird_timer -= delta
	if bird_timer > 0.0: return
	bird_timer = randf_range(4.0, 11.0) * (2.5 if at.x > 120.0 else 1.0)
	var offset := Vector3(randf_range(-18, 18), randf_range(4, 9), randf_range(-18, 18))
	one_shot_at("bird_chirp", at + offset, -14.0, 6.0, randf_range(0.85, 1.2))
