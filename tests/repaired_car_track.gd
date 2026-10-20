extends Node3D
## Standalone playable test course. No save service or player-save reads/writes.
var player: CourierPlayer
var speed_label: Label
var review_camera: Camera3D

func _ready() -> void:
	var actions := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D, "sprint": KEY_SHIFT, "jump": KEY_SPACE, "interact": KEY_E}
	for action in actions:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = actions[action]
			InputMap.action_add_event(action, key)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color("7199bd")
	sky_material.sky_horizon_color = Color("dbe5eb")
	sky.sky_material = sky_material
	environment.environment.sky = sky
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -28, 0)
	sun.light_energy = 1.5
	sun.shadow_enabled = true
	add_child(sun)
	block("TestSurface", Vector3(0,-0.15,-25), Vector3(80,.3,160), Color("515963"), true)
	for x in [-5.0,5.0]: block("LaneLine",Vector3(x,.006,-30),Vector3(.12,.008,115),Color("dbdddf"),false)
	for z in range(-85,35,6): block("Dash",Vector3(0,.009,z),Vector3(.10,.008,2.7),Color("ece2ad"),false)
	block("CollisionBarrier",Vector3(0,.65,-55),Vector3(10,1.3,.5),Color("b9bdc3"),true)
	for x in [-12,12]:
		for z in [-30,-15,0,15]:block("Marker",Vector3(x,.3,z),Vector3(.5,.6,.5),Color("df8c3b"),true)
	player = CourierPlayer.new()
	player.name = "TestDriver"
	player.session = DeliverySession.new()
	player.session.active_vehicle = "hatchback"
	player.session.online = false
	player.vehicle_scene_override = preload("res://assets/vehicles/repaired_car/repaired_car.tscn")
	add_child(player)
	player.replace_vehicle(Vector3(0,.03,5))
	player.position = Vector3(0,.03,5)
	player.mounted = true
	player.apply_vehicle_camera()
	player.camera.fov = 60
	review_camera = Camera3D.new()
	add_child(review_camera)
	var hud := CanvasLayer.new()
	add_child(hud)
	var help := Label.new()
	help.position = Vector2(24,20)
	help.text = "REPAIRED CAR · Test course\nW accelerate · S reverse · A/D steer · Space brake\nE exit / enter · R reset · Esc release mouse · Click to look"
	help.add_theme_font_size_override("font_size",19)
	hud.add_child(help)
	speed_label = Label.new()
	speed_label.position = Vector2(24,115)
	speed_label.add_theme_font_size_override("font_size",22)
	hud.add_child(speed_label)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func block(label: String, at: Vector3, size: Vector3, color: Color, collision: bool) -> void:
	var mesh := MeshInstance3D.new()
	mesh.name = label
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = .87
	mesh.material_override = material
	mesh.position = at
	add_child(mesh)
	if collision:
		var body := StaticBody3D.new()
		mesh.add_child(body)
		var shape := CollisionShape3D.new()
		var bounds := BoxShape3D.new()
		bounds.size = size
		shape.shape = bounds
		body.add_child(shape)

func _process(_delta: float) -> void:
	speed_label.text = "%02d km/h  ·  %s" % [absi(roundi(player.riding_speed*3.6)), "REVERSE" if player.riding_speed<-.05 else "DRIVE" if player.mounted else "ON FOOT"]

func reset_car(at := Vector3(0,.03,5)) -> void:
	player.position = at
	player.rotation = Vector3.ZERO
	player.velocity = Vector3.ZERO
	player.riding_speed = 0
	player.steer_angle = 0
	player.camera.rotation = Vector3(-.24,0,0)
	player.bicycle.position = at
	player.bicycle.rotation = Vector3.ZERO
	player.bicycle.update_driving_visuals(0,0)
	player.mounted = true
	player.apply_vehicle_camera()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_ESCAPE: Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		if event.physical_keycode == KEY_R: reset_car()
		if event.physical_keycode == KEY_E: player.toggle_bicycle()
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

