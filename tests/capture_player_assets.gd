extends SceneTree
## Rendered check of the player courier assets (tools/prepare_player.py, tools/setup_player.gd):
## the courier playing its clips, seated / pedalling on the gray bicycle (crank synced to
## Bike_Pedal), the Avaturn door customer talking and the clothed pedestrian walking.
##   Godot_console.exe --path . --script res://tests/capture_player_assets.gd -- <out_dir>
## Writes <out_dir>/player_<name>.png (contact sheets of 4 frames per clip).

var out_dir := "res://tmp"
var camera: Camera3D

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out_dir = args[0]
	call_deferred("run")

func studio() -> Node3D:
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.ssao_enabled = true
	env.environment = e
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.shadow_enabled = true
	sun.light_energy = 1.3
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30, 30)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.46, 0.46, 0.44)
	gm.uv1_scale = Vector3(30, 30, 1)
	gm.albedo_texture = checker()
	ground.material_override = gm
	world.add_child(ground)
	camera = Camera3D.new()
	camera.fov = 40
	world.add_child(camera)
	camera.current = true
	return world

func checker() -> ImageTexture:
	var img := Image.create(64, 64, false, Image.FORMAT_RGB8)
	for y in range(64):
		for x in range(64):
			var c := 0.62 if ((x / 32) + (y / 32)) % 2 == 0 else 0.5
			img.set_pixel(x, y, Color(c, c, c * 0.97))
	return ImageTexture.create_from_image(img)

func shot() -> Image:
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()

func sheet(images: Array[Image], name: String) -> void:
	var w := images[0].get_width()
	var h := images[0].get_height()
	var out := Image.create(w * images.size(), h, false, images[0].get_format())
	for i in range(images.size()): out.blit_rect(images[i], Rect2i(0, 0, w, h), Vector2i(i * w, 0))
	var path := out_dir.path_join("player_%s.png" % name)
	print("saved ", path, " ", out.save_png(path))

func look(from: Vector3, at: Vector3) -> void:
	camera.position = from
	camera.look_at(at)

func run() -> void:
	root.size = Vector2i(720, 900)
	root.msaa_3d = Viewport.MSAA_4X
	var world := studio()
	var courier: Node3D = (load("res://assets/player/courier.tscn") as PackedScene).instantiate()
	world.add_child(courier)
	var ap := courier.get_node("AnimationPlayer") as AnimationPlayer
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	# clips: side view (character faces -Z, camera on its right), 4 frames each
	for clip: String in ["Idle", "Idle_Shift", "Walk", "Jog", "Run", "Sprint", "Walk_Back", "Strafe_L", "Jump_Start", "Jump", "Jump_Land", "Land_Hard", "Turn_L_90", "PickUp"]:
		var a := ap.get_animation(clip)
		var frames: Array[Image] = []
		for k in range(4):
			ap.play(clip)
			ap.seek(a.length * k / 4.0 + (a.length * 0.1 if not a.loop_mode else 0.0), true)
			if clip.begins_with("Turn"):
				courier.rotation.y = deg_to_rad(90.0) * smoothstep(0.0, 1.0, clampf((a.length * k / 4.0) / 0.85, 0.0, 1.0))
			else:
				courier.rotation.y = 0.0
			var side := Vector3(3.6, 1.15, 0.0) if not clip.begins_with("Strafe") else Vector3(0.0, 1.15, -3.6)
			look(side, Vector3(0, 0.9, 0))
			frames.append(await shot())
		sheet(frames, "clip_" + clip.to_lower())
	courier.rotation.y = 0.0
	# close-up: face and hands in Idle, 3/4 front
	ap.play("Idle")
	ap.seek(0.5, true)
	var close: Array[Image] = []
	look(Vector3(1.0, 1.6, -1.6), Vector3(0, 1.55, 0))
	camera.fov = 22
	close.append(await shot())
	look(Vector3(2.2, 1.3, -3.0), Vector3(0, 0.95, 0))
	camera.fov = 40
	close.append(await shot())
	look(Vector3(-2.2, 1.3, 3.0), Vector3(0, 0.95, 0))
	close.append(await shot())
	sheet(close, "closeup")
	# riding the gray bicycle: courier root = bike root, crank synced to Bike_Pedal
	var bike := CityAssets.create("bicycle")
	world.add_child(bike)
	courier.reparent(bike, false)
	courier.transform = Transform3D.IDENTITY
	var crank := bike.find_child("Crank", true, false) as Node3D
	var pedal_l := bike.find_child("PedalL", true, false) as Node3D
	var pedal_r := bike.find_child("PedalR", true, false) as Node3D
	for view: Array in [["bike_side", Vector3(3.4, 1.0, 0.0)], ["bike_34", Vector3(2.4, 1.6, -2.6)], ["bike_front", Vector3(0.0, 1.2, -3.6)], ["bike_left", Vector3(-3.4, 1.0, 0.3)]]:
		var frames: Array[Image] = []
		for deg: float in [0.0, 90.0, 180.0, 270.0]:
			ap.play("Bike_Pedal")
			ap.seek(deg / 360.0 * ap.get_animation("Bike_Pedal").length, true)
			crank.rotation.x = -deg_to_rad(deg)
			pedal_l.rotation.x = -crank.rotation.x
			pedal_r.rotation.x = -crank.rotation.x
			look(view[1], Vector3(0, 0.75, 0))
			frames.append(await shot())
		sheet(frames, view[0])
	bike.queue_free()
	# the door customer (Avaturn) talking, and the clothed pedestrian walking
	var who := LivingAssets.door_customer()
	world.add_child(who)
	var cap := who.find_child("AnimationPlayer", true, false) as AnimationPlayer
	cap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var talk: Array[Image] = []
	for t: float in [1.0, 4.0, 7.5]:
		cap.play("Talk")
		cap.seek(t, true)
		look(Vector3(0.6, 1.65, -1.3), Vector3(0, 1.6, 0))
		camera.fov = 25
		talk.append(await shot())
	cap.seek(4.0, true)
	camera.fov = 40
	look(Vector3(1.4, 1.2, -3.4), Vector3(0, 0.95, 0))
	talk.append(await shot())
	sheet(talk, "customer_talk")
	who.queue_free()
	var person := LivingAssets.humanoid(5)
	person.set_process(false)
	world.add_child(person)
	var pap := person.players[0] as AnimationPlayer
	pap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var walk: Array[Image] = []
	for k in range(4):
		pap.play("Walk")
		pap.seek(pap.get_animation("Walk").length * k / 4.0, true)
		look(Vector3(2.6, 1.2, -2.2), Vector3(0, 0.9, 0))
		walk.append(await shot())
	sheet(walk, "clothed_man_walk")
	print("PLAYER CAPTURES PASS body=", person.body_id)
	quit()
