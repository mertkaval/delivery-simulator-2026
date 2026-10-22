extends SceneTree
## Rendered check of the courier's backpack (tools/courier_bag.py, tools/setup_player.gd): every
## bag / carry clip played on assets/player/courier.tscn with the held bag driven by the clip's
## bag_track (flap_deg, strap / socket events), the package by package_track, the worn bag on a
## BoneAttachment3D (UpperChest) with the body straps shown, the bag-aware locomotion clips and the
## courier riding the gray bicycle with the bag on.
##   Godot_console.exe --path . --script res://tests/capture_backpack.gd -- <out_dir>
## Writes <out_dir>/bag_<clip>.png (rows: side / three-quarter front / behind; columns: key frames).

const CONTRACT := "res://assets/player/clips.json"
const PACKAGE := "res://assets/delivery/food_bag.glb"

var out_dir := "res://tmp"
var camera: Camera3D
var courier: Node3D
var animator: AnimationPlayer
var skeleton: Skeleton3D
var worn: Node3D
var worn_plain: Node3D
var held: Node3D
var package: Node3D
var contract: Dictionary = {}
var backpack: Dictionary = {}
var straps: Dictionary = {}
var failures := 0

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
	gm.albedo_color = Color(0.5, 0.5, 0.48)
	ground.material_override = gm
	world.add_child(ground)
	camera = Camera3D.new()
	camera.fov = 38
	world.add_child(camera)
	camera.current = true
	return world

func shot() -> Image:
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()

func sheet(rows: Array, name: String) -> void:
	var first: Image = (rows[0] as Array)[0]
	var w := first.get_width()
	var h := first.get_height()
	var cols := (rows[0] as Array).size()
	var out := Image.create(w * cols, h * rows.size(), false, first.get_format())
	for r in range(rows.size()):
		var row: Array = rows[r]
		for c in range(row.size()):
			out.blit_rect(row[c] as Image, Rect2i(0, 0, w, h), Vector2i(c * w, r * h))
	var path := out_dir.path_join("bag_%s.png" % name)
	print("saved ", path, " ", out.save_png(path))

func look(from: Vector3, at: Vector3, fov: float = 38.0) -> void:
	camera.fov = fov
	camera.position = from
	camera.look_at(at)

static func xf(a: Array) -> Transform3D:
	return Transform3D(Basis(Quaternion(float(a[3]), float(a[4]), float(a[5]), float(a[6]))), Vector3(float(a[0]), float(a[1]), float(a[2])))

## Track entry at clip time t (linear between the 30 fps frames).
static func track_at(track: Array, t: float) -> Transform3D:
	var f := clampf(t * 30.0, 0.0, track.size() - 1.0)
	var i := int(floor(f))
	var j := mini(i + 1, track.size() - 1)
	return xf(track[i]).interpolate_with(xf(track[j]), f - i)

func set_node_visible(parent: Node, node_name: String, on: bool) -> void:
	var n := parent.find_child(node_name, true, false) as Node3D
	if n != null: n.visible = on

## Pose the courier at clip time t and apply the clip's bag data.
func pose(clip: String, t: float, wear: bool = true, plain: bool = false) -> void:
	animator.play(clip)
	animator.seek(t, true)
	var entry: Dictionary = (contract.get("clips", {}) as Dictionary).get(clip, {})
	var frame := int(round(t * 30.0))
	var state := {"bag_socket": "back" if wear else "none", "body_strap_r": wear, "body_strap_l": wear, "bag_strap_r": false, "bag_strap_l": false, "package": "none"}
	for e: Dictionary in entry.get("events", []):
		if int(e["frame"]) > frame: continue
		var what := str(e["do"])
		if what == "bag_socket" or what == "package": state[what] = str(e["to"])
		else: state[what] = bool(e["visible"])
	var socket := str(state["bag_socket"])
	worn.visible = socket == "back" and not plain
	worn_plain.visible = socket == "back" and plain
	(straps["BackpackStrapL"] as Node3D).visible = bool(state["body_strap_l"]) and socket != "none"
	(straps["BackpackStrapR"] as Node3D).visible = bool(state["body_strap_r"]) and socket != "none"
	held.visible = socket == "track" and entry.has("bag_track")
	if held.visible:
		held.transform = track_at(entry["bag_track"], t)
		var flap := held.get_node(str((backpack["held_nodes"] as Dictionary)["Flap"])) as Node3D
		var fd: Array = entry.get("flap_deg", [0.0])
		flap.rotation.x = deg_to_rad(float(fd[clampi(frame, 0, fd.size() - 1)]))
		set_node_visible(held, "StrapL", bool(state["bag_strap_l"]))
		set_node_visible(held, "StrapR", bool(state["bag_strap_r"]))
	var pkg := str(state["package"])
	package.visible = entry.has("package_track") and pkg != "none" and not (pkg == "released" and clip == "Handover") and pkg != "bag"
	if pkg == "bag" and held.visible:
		# packed: sits in the top compartment where the track left it
		package.visible = true
	if package.visible: package.transform = track_at(entry["package_track"], t)

func views(clip: String, n: int, wear: bool = true, plain: bool = false, centre: float = 0.95) -> Array:
	var a := animator.get_animation(clip)
	var rows: Array = []
	for v: Array in [[Vector3(3.4, 1.05, -0.2), 34.0], [Vector3(2.2, 1.45, -2.7), 34.0], [Vector3(1.0, 1.85, 3.2), 34.0]]:
		var row: Array = []
		for k in range(n):
			var t := a.length * k / maxf(n - 1, 1) if not a.loop_mode else a.length * k / n
			pose(clip, t, wear, plain)
			look(v[0], Vector3(0, centre, 0), v[1])
			row.append(await shot())
		rows.append(row)
	return rows

func run() -> void:
	root.size = Vector2i(400, 600)
	root.msaa_3d = Viewport.MSAA_4X
	var world := studio()
	contract = JSON.parse_string(FileAccess.get_file_as_string(CONTRACT))
	backpack = contract.get("backpack", {})
	courier = (load("res://assets/player/courier.tscn") as PackedScene).instantiate()
	world.add_child(courier)
	animator = courier.get_node("AnimationPlayer") as AnimationPlayer
	animator.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	skeleton = courier.find_child("GeneralSkeleton", true, false) as Skeleton3D
	for n: String in ["BackpackStrapL", "BackpackStrapR"]:
		straps[n] = courier.get_node(str((backpack["strap_nodes"] as Dictionary)[n]))
		if (straps[n] as Node3D).visible:
			print("FAIL: ", n, " should ship hidden in courier.tscn")
			failures += 1
	var attach := BoneAttachment3D.new()
	attach.bone_name = str(backpack.get("bone", "UpperChest"))
	skeleton.add_child(attach)
	worn = (load(str(backpack["worn_scene"])) as PackedScene).instantiate()
	attach.add_child(worn)
	worn_plain = (load(str(backpack["worn_plain_scene"])) as PackedScene).instantiate()
	attach.add_child(worn_plain)
	held = (load(str(backpack["held_scene"])) as PackedScene).instantiate()
	courier.add_child(held)
	package = (load(PACKAGE) as PackedScene).instantiate()
	courier.add_child(package)
	# 1. consistency: the worn bag on the bone == bag_track on the frames before the socket switch
	pose("Bag_TakeOff", 0.0)
	for i in range(2): await process_frame
	var take_off: Dictionary = (contract["clips"] as Dictionary)["Bag_TakeOff"]
	var bag_node := worn.get_node("Bag") as Node3D
	var err := (courier.global_transform.affine_inverse() * bag_node.global_transform).origin.distance_to(xf((take_off["bag_track"] as Array)[0]).origin)
	print("worn bag vs bag_track frame 0: ", snappedf(err * 1000.0, 0.1), " mm")
	if err > 0.01:
		print("FAIL: worn bag and bag_track disagree")
		failures += 1
	# 2. the bag / carry clips
	for clip: String in ["Bag_TakeOff", "Bag_Hold", "Bag_PackItem", "Bag_TakeItem", "Bag_PutOn", "Bag_PutOn_Holding", "Bag_StrapRight", "Carry_Idle", "Carry_Walk", "Handover", "PlaceDown", "Bag_Worn_Idle"]:
		if not animator.has_animation(clip):
			print("FAIL: missing clip ", clip)
			failures += 1
			continue
		sheet(await views(clip, 6, true, false, 0.75 if clip == "PlaceDown" else 0.95), clip.to_lower())
	# 3. worn bag in the bag-aware locomotion; the plain backpack sprinting
	for clip: String in ["Walk_Bag", "Sprint_Bag", "Jump_Bag"]:
		if animator.has_animation(clip): sheet(await views(clip, 4), "worn_" + clip.to_lower())
	if animator.has_animation("Sprint_Bag"): sheet(await views("Sprint_Bag", 4, true, true), "worn_plain_sprint_bag")
	# 4. riding the gray bicycle with the bag on (courier root = bike root, crank synced)
	var bike := CityAssets.create("bicycle")
	world.add_child(bike)
	courier.reparent(bike, false)
	courier.transform = Transform3D.IDENTITY
	var crank := bike.find_child("Crank", true, false) as Node3D
	var pedal_l := bike.find_child("PedalL", true, false) as Node3D
	var pedal_r := bike.find_child("PedalR", true, false) as Node3D
	var rows: Array = []
	for v: Array in [[Vector3(3.3, 1.1, 0.0), 0.8], [Vector3(2.4, 1.6, -2.6), 0.8], [Vector3(0.9, 2.0, 3.4), 1.0], [Vector3(-3.3, 1.1, 0.3), 0.8]]:
		var row: Array = []
		for deg: float in [0.0, 90.0, 180.0, 270.0]:
			pose("Bike_Pedal", deg / 360.0 * animator.get_animation("Bike_Pedal").length)
			crank.rotation.x = -deg_to_rad(deg)
			pedal_l.rotation.x = -crank.rotation.x
			pedal_r.rotation.x = -crank.rotation.x
			look(v[0], Vector3(0, v[1], 0), 30.0)
			row.append(await shot())
		rows.append(row)
	sheet(rows, "riding")
	print("BACKPACK CAPTURES ", "PASS" if failures == 0 else "FAIL", " failures=", failures)
	quit()
