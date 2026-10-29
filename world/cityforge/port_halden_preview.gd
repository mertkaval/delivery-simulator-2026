extends Node3D
## Fly round Port Halden (the generated city) without the game: open
## world/cityforge/port_halden_preview.tscn (the classic city) or port_halden_roads_preview.tscn (the roads-only
## city: assets/cityforge_roads) and press F6.
## Mouse: look (click to capture, Esc to release) - WASD: fly - Q/E: down/up - Shift: fast
## N: day / night - F: drop to street level - Wheel: speed.

var world: CityForgeWorld
var camera: Camera3D
var sun: DirectionalLight3D
var env: Environment
var speed := 30.0
var yaw := 0.0
var pitch := -0.35
var night := false
var hud: Label
## The city build to show (empty: the classic city in assets/cityforge).
@export var city_dir := ""

func _ready() -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("4f7fb8")
	sky.sky_horizon_color = Color("b9cde0")
	env.sky.sky_material = sky
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.fog_enabled = true
	env.fog_density = 0.0005
	env.fog_light_color = Color("b9cde0")
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 350.0
	add_child(sun)
	CityForgeWorld.use_city(city_dir if city_dir != "" else CityForgeWorld.CLASSIC_DIR)
	world = CityForgeWorld.new()
	add_child(world)
	camera = Camera3D.new()
	camera.far = 6000.0
	camera.fov = 65.0
	add_child(camera)
	camera.position = world.to_world(1050, 1250, 0) + Vector3.UP * (world.ground_height(world.to_world(1050, 1250)) + 60.0)
	yaw = deg_to_rad(30.0)
	hud = Label.new()
	hud.position = Vector2(12, 10)
	hud.add_theme_color_override("font_outline_color", Color.BLACK)
	hud.add_theme_constant_override("outline_size", 6)
	add_child(hud)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT: Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		if mb.pressed and mb.button_index == MOUSE_BUTTON_WHEEL_UP: speed = minf(speed * 1.25, 400.0)
		if mb.pressed and mb.button_index == MOUSE_BUTTON_WHEEL_DOWN: speed = maxf(speed / 1.25, 2.0)
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var mm := event as InputEventMouseMotion
		yaw -= mm.relative.x * 0.003
		pitch = clampf(pitch - mm.relative.y * 0.003, -1.5, 1.5)
	elif event is InputEventKey and (event as InputEventKey).pressed:
		match (event as InputEventKey).keycode:
			KEY_ESCAPE: Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_N:
				night = not night
				sun.light_energy = 0.04 if night else 1.0
				env.background_energy_multiplier = 0.04 if night else 1.0
				env.ambient_light_energy = 0.12 if night else 1.0
				world.set_night(1.0 if night else 0.0)
			KEY_F:
				camera.position.y = world.ground_height(camera.position) + 1.7
				speed = 6.0

func _process(delta: float) -> void:
	camera.basis = Basis.from_euler(Vector3(pitch, yaw, 0.0))
	var dir := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): dir -= camera.basis.z
	if Input.is_key_pressed(KEY_S): dir += camera.basis.z
	if Input.is_key_pressed(KEY_A): dir -= camera.basis.x
	if Input.is_key_pressed(KEY_D): dir += camera.basis.x
	if Input.is_key_pressed(KEY_E): dir += Vector3.UP
	if Input.is_key_pressed(KEY_Q): dir -= Vector3.UP
	var fast := 4.0 if Input.is_key_pressed(KEY_SHIFT) else 1.0
	camera.position += dir.normalized() * speed * fast * delta
	camera.position.y = maxf(camera.position.y, world.ground_height(camera.position) + 0.6)
	world.update_focus(camera.position, delta)
	var q := world.to_plan(camera.position)
	var hs := world.nearest_house(camera.position)
	hud.text = "Port Halden  x %d  y %d  h %.0f m   %d fps   speed %.0f m/s\nnearest address: %s" % [
		q.x, q.y, camera.position.y, Engine.get_frames_per_second(), speed * fast, str(hs.get("address", ""))]
