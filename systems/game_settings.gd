class_name GameSettings
extends RefCounted
## Player options from the main menu, stored in user://settings.cfg and applied on start:
## audio bus volumes, mouse sensitivity, field of view, fullscreen and vsync.

const PATH := "user://settings.cfg"
const DEFAULTS := {"master": 0.85, "ambience": 0.8, "effects": 0.9, "sensitivity": 1.0, "fov": 78.0, "fullscreen": true, "vsync": true}

static var values: Dictionary = DEFAULTS.duplicate()

static func load_settings() -> void:
	values = DEFAULTS.duplicate()
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK: return
	for key: String in DEFAULTS:
		var v: Variant = cfg.get_value("options", key, DEFAULTS[key])
		if typeof(v) == typeof(DEFAULTS[key]) or (DEFAULTS[key] is float and v is int): values[key] = v

static func save_settings() -> void:
	var cfg := ConfigFile.new()
	for key: String in values: cfg.set_value("options", key, values[key])
	cfg.save(PATH)

static func get_value(key: String) -> Variant:
	return values.get(key, DEFAULTS.get(key))

static func set_value(key: String, value: Variant) -> void:
	values[key] = value

## Push the options into the audio buses, the window and (if given) the player.
static func apply(player: CourierPlayer = null) -> void:
	for pair: Array in [["Master", "master"], ["Ambience", "ambience"], ["SFX", "effects"], ["UI", "effects"]]:
		var bus := AudioServer.get_bus_index(str(pair[0]))
		if bus == -1: continue
		var level := float(get_value(str(pair[1])))
		AudioServer.set_bus_volume_db(bus, linear_to_db(maxf(level, 0.0001)))
		AudioServer.set_bus_mute(bus, level <= 0.001)
	if DisplayServer.get_name() != "headless":
		var want_full := bool(get_value("fullscreen"))
		var is_full := DisplayServer.window_get_mode() in [DisplayServer.WINDOW_MODE_FULLSCREEN, DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN]
		if want_full != is_full:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if want_full else DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if bool(get_value("vsync")) else DisplayServer.VSYNC_DISABLED)
	if player != null:
		player.sensitivity = 0.002 * float(get_value("sensitivity"))
		if player.camera != null: player.camera.fov = float(get_value("fov"))
