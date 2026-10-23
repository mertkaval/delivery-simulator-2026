extends SceneTree
## Lineup of every designed townsperson (assets/people) in its role clip, with role props:
##   godot --path . --script res://tests/capture_townspeople.gd   -> tmp/townspeople_*.png
const ROLE_POSE := {"police": "Duty", "security": "Duty", "street_cleaner": "Sweep", "tourist": "Photo",
	"dog_walker": "WalkLeash", "parent": "WalkPush", "chef": "Counter", "pizza": "Counter", "doner": "Counter",
	"barista": "Counter", "baker": "Counter", "cashier": "Counter", "construction": "Kneel", "jogger": "Run",
	"office": "WalkFormal", "server": "Carry", "retiree": "Walk", "commuter": "PhoneCall", "student": "Phone"}
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size = Vector2i(1600, 900)
	var stage := Node3D.new()
	root.add_child(stage)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.42, 0.45, 0.5)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.55, 0.57, 0.6)
	env.environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	stage.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(-0.8, 0.5, 0)
	sun.shadow_enabled = true
	stage.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 30)
	ground.mesh = plane
	stage.add_child(ground)
	var people := LivingAssets.load_people()
	var per_row := 7
	for i in range(people.size()):
		var e: Dictionary = people[i]
		var who := LivingAssets.people_body(e, i)
		stage.add_child(who)
		var row := i / per_row
		who.position = Vector3((i % per_row - (per_row - 1) * 0.5) * 1.2, 0, -row * 4.0)
		who.rotation.y = PI
		var pose: String = ROLE_POSE.get(str(e.role), "Idle")
		if pose in ["Walk", "WalkFormal", "WalkLeash", "WalkPush", "Run", "WalkCarry"]:
			who.locomotion = pose
			who.ground_speed = 2.6 if pose == "Run" else 1.2
		else:
			who.ground_speed = 0.0
			who.purpose_pose = pose
		if pose == "Carry": who.carry(null)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.current = true
	camera.fov = 40
	for k in range(90): await process_frame
	var views: Array = []
	for row in range(int(ceil(people.size() / float(per_row)))):
		views.append(["row%d" % row, Vector3(0, 1.25, -row * 4.0 + 5.6), Vector3(0, 0.9, -row * 4.0)])
		views.append(["row%d_side" % row, Vector3(4.6, 1.3, -row * 4.0 + 3.6), Vector3(0.6, 0.9, -row * 4.0)])
	for view: Array in views:
		camera.position = view[1]
		camera.look_at(view[2])
		for k in range(20): await process_frame
		root.get_texture().get_image().save_png("res://tmp/townspeople_%s.png" % view[0])
	print("TOWNSPEOPLE CAPTURED %d" % people.size())
	quit()
