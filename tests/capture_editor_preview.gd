extends SceneTree
## What the Godot editor shows of Port Halden (world/editor_preview/editor_preview.gd): its sources loaded and
## assembled with the preview's own functions (CityForge chunks + outskirts, Mert Road Studio street chunks, street
## assets and street trees as MultiMeshes), rendered from a few cameras.
##   godot --path . --script res://tests/capture_editor_preview.gd -- <out_dir>
func _initialize() -> void: call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	root.size = Vector2i(1600, 900)
	CedarNeighborhood.city_override = "port_halden"
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ep: Node3D = load("res://world/editor_preview/editor_preview.gd").new()
	var preview := Node3D.new()
	preview.name = "CityPreview"
	var srcs: PackedStringArray = ep.call("_sources")
	for path in srcs:
		var node := (load(path) as PackedScene).instantiate()
		if path.begins_with(MrsCityStreets.DIR):
			ep.call("_add_streets", preview, node, path)
			continue
		preview.add_child(node)
		for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
			CityForgeMaterials.apply(mi.mesh)
	var trees := 0
	if preview.has_node("MrsStreetAssets"): trees = MrsCityStreets.editor_trees(preview.get_node("MrsStreetAssets") as Node3D)
	root.add_child(preview)
	var mm := preview.find_children("*", "MultiMeshInstance3D", true, false).size()
	print("EDITOR_PREVIEW sources %d, multimeshes %d, trees %d" % [srcs.size(), mm, trees])
	var w := CityForgeWorld.new()           # only for coordinates / heights (not added to the tree)
	w.city = JSON.parse_string(FileAccess.get_file_as_string(CityForgeWorld.DIR + "city.json")) as Dictionary
	w.heights = FileAccess.get_file_as_bytes(CityForgeWorld.DIR + "heights.f32").to_float32_array()
	var cam := Camera3D.new()
	cam.far = 5000.0
	root.add_child(cam)
	cam.current = true
	for v: Array in [["aerial", Vector2(1024, -350), 900.0, Vector2(1024, 1100), 0.0],
			["junction", Vector2(1080, 1270), 35.0, Vector2(1100, 1300), 0.0],
			["street", Vector2(1046, 1306), 1.7, Vector2(1150, 1300), 1.5]]:
		var e: Vector2 = v[1]
		var t: Vector2 = v[3]
		var eye := w.to_world(e.x, e.y)
		eye.y = w.ground_height(eye) + float(v[2])
		var at := w.to_world(t.x, t.y)
		at.y = w.ground_height(at) + float(v[4])
		cam.position = eye
		cam.look_at(at)
		for i in 15: await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out.path_join("editor_%s.png" % v[0]))
		print("CAPTURED ", v[0])
	w.free()
	ep.free()
	quit()
