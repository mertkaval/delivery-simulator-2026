extends SceneTree
## Godot check of the Road Studio furniture library (tools/roads/tests/furniture_test.py writes
## furniture.glb + layout.json): loads the GLB at runtime with GLTFDocument, reports per-node triangles,
## materials, textures and glTF extras, then rebuilds the Blender test scenes (overview + close-ups) from
## layout.json on the same paving tiles and captures godot_<scene>.png next to the Blender renders.
## usage: godot --path . --script res://tests/capture_mrs_furniture.gd -- <glb> <out_dir>
## (not --headless: the dummy renderer captures nothing)
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func load_glb(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		push_error("glb load failed: %s (%d)" % [path, err]); return null
	return doc.generate_scene(state) as Node3D

func load_tex(path: String) -> Texture2D:
	var img := Image.load_from_file(path)
	if img == null: return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)

func b2g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

func tris(mesh: Mesh) -> int:
	var n := 0
	var am := mesh as ArrayMesh
	if am == null: return 0
	for s in am.get_surface_count():
		var idx := am.surface_get_array_index_len(s)
		n += (idx if idx > 0 else am.surface_get_array_len(s)) / 3
	return n

func shot(out: String, key: String, eye: Vector3, target: Vector3, fov: float) -> void:
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 10: await process_frame
	await RenderingServer.frame_post_draw
	var path := out.path_join("godot_%s.png" % key)
	root.get_texture().get_image().save_png(path)
	print("CAPTURED ", path)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var glb: String = args[0] if args.size() > 0 else ProjectSettings.globalize_path("res://tmp/roads/v4/furniture/furniture.glb")
	var out: String = args[1] if args.size() > 1 else glb.get_base_dir()
	root.size = Vector2i(1600, 900)
	var lib := load_glb(glb)
	if lib == null:
		quit(1); return
	# ---- report: triangles, materials, textures, extras per library node
	var meshes := {}
	var problems: Array[String] = []
	var with_extras := 0
	for node in lib.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		meshes[String(mi.name)] = mi
		var mats: Array[String] = []
		for s in mi.mesh.get_surface_count():
			var mat := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if mat == null:
				problems.append("%s surface %d has no material" % [mi.name, s]); continue
			mats.append(mat.resource_name)
			if mat.resource_name.begins_with("MRS_FurnitureAtlas"):
				if mat.albedo_texture == null: problems.append("%s: atlas without albedo texture" % mi.name)
				if not mat.normal_enabled or mat.normal_texture == null: problems.append("%s: atlas without normal map" % mi.name)
				if mat.roughness_texture == null or mat.metallic_texture == null: problems.append("%s: atlas without roughness/metallic texture" % mi.name)
			elif mat.resource_name.begins_with("MRS_FurnitureGlass"):
				if mat.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED: problems.append("%s: glass is opaque" % mi.name)
			else:
				problems.append("%s: unexpected material %s" % [mi.name, mat.resource_name])
		var extras := {}
		if mi.has_meta("extras"):
			extras = mi.get_meta("extras") as Dictionary
			with_extras += 1
		var size := mi.get_aabb().size
		print("FURN %-24s tris %5d  size %.2f x %.2f x %.2f  mats %s  kind %s  footprint %s" % [mi.name, tris(mi.mesh), size.x, size.z, size.y, ",".join(mats),
			extras.get("mrs_kind", "-"), extras.get("mrs_footprint", "-")])
	print("FURN nodes %d, with extras %d" % [meshes.size(), with_extras])
	if problems.is_empty(): print("FURN textures OK (every atlas surface has albedo, normal, roughness and metallic textures; glass is transparent)")
	for p in problems: print("FURN PROBLEM ", p)
	# ---- scene: sky, sun from the Blender test, paving ground
	var f := FileAccess.open(glb.get_base_dir().path_join("layout.json"), FileAccess.READ)
	if f == null:
		push_error("layout.json missing next to the GLB"); quit(1); return
	var layout: Dictionary = JSON.parse_string(f.get_as_text())
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("6f8fb8"); sky.sky_horizon_color = Color("c3d0de")
	sky.ground_horizon_color = Color("c3d0de"); sky.ground_bottom_color = Color("a7aaac")   # light ground, like the paving metals reflect
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new(); we.environment = env; root.add_child(we)
	var sun := DirectionalLight3D.new(); sun.shadow_enabled = true; sun.light_energy = 1.6; root.add_child(sun)
	var sd: Array = layout.get("sun_dir", [0.4, 0.6, -0.6])
	var dir := b2g(sd).normalized()
	sun.look_at(dir, Vector3.UP if absf(dir.y) < 0.99 else Vector3.FORWARD)
	var ground := MeshInstance3D.new(); var pm := PlaneMesh.new(); pm.size = Vector2(160, 160); ground.mesh = pm
	var gmat := StandardMaterial3D.new()
	var gpaths: Dictionary = layout.get("ground", {})
	var galb := load_tex(String(gpaths.get("albedo", "")))
	if galb:
		gmat.albedo_texture = galb
		gmat.roughness_texture = load_tex(String(gpaths.get("roughness", ""))); gmat.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		gmat.normal_enabled = true; gmat.normal_texture = load_tex(String(gpaths.get("normal", "")))
		gmat.uv1_triplanar = true; gmat.uv1_world_triplanar = true
		var tile: float = layout.get("tile_m", 4.0)
		gmat.uv1_scale = Vector3.ONE / tile
	else:
		gmat.albedo_color = Color("8a8a86")
	ground.material_override = gmat; root.add_child(ground)
	camera = Camera3D.new(); camera.near = 0.05; camera.far = 500.0; root.add_child(camera); camera.current = true
	var holder := Node3D.new(); root.add_child(holder)
	var scenes: Dictionary = layout.get("scenes", {})
	for key in scenes.keys():
		for c in holder.get_children(): c.free()
		var sc: Dictionary = scenes[key]
		var items: Array = sc["items"]
		for it in items:
			var item: Dictionary = it
			var src: MeshInstance3D = meshes.get(String(item["name"]))
			if src == null:
				print("FURN PROBLEM scene %s: no mesh %s" % [key, item["name"]]); continue
			var m := MeshInstance3D.new(); m.mesh = src.mesh
			m.position = b2g(item["pos"]); m.rotation.y = float(item["rot_z"])
			holder.add_child(m)
		var cam: Dictionary = sc["camera"]
		await shot(out, String(key), b2g(cam["eye"]), b2g(cam["target"]), float(cam["vfov_deg"]))
	lib.free()
	quit()
