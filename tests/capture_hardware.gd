extends SceneTree
## Godot check of the Road Studio street hardware (tools/roads/tests/hardware_test.py writes hardware.glb +
## layout.json): loads the GLB at runtime with GLTFDocument, reports per library node triangles, materials,
## textures, texture transforms, glass transparency and glTF extras, then rebuilds the Blender test scenes
## (close-ups of streetlights, signs, signals, barriers, the footbridge material swatches; the same cameras,
## sun and paving) and captures godot_<scene>.png. The night scene uses MrsStreetLights with the light records
## of the Blender night render and switches the lamp materials on.
## usage: godot --path . --script res://tests/capture_hardware.gd -- [glb] [out_dir]
## (not --headless: the dummy renderer captures nothing)
const StreetLights := preload("res://world/roads/mrs_street_lights.gd")

var camera: Camera3D

func _initialize() -> void:
	call_deferred("run")

func load_glb(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		push_error("glb load failed: %s (%d)" % [path, err])
		return null
	return doc.generate_scene(state) as Node3D

func load_tex(path: String) -> Texture2D:
	var img := Image.load_from_file(path)
	if img == null:
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)

static func b2g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func lin(v: Array, k: float = 1.0) -> Color:
	return Color(float(v[0]) * k, float(v[1]) * k, float(v[2]) * k)

func tris(mesh: Mesh) -> int:
	var n := 0
	var am := mesh as ArrayMesh
	if am == null:
		return 0
	for s in am.get_surface_count():
		var idx := am.surface_get_array_index_len(s)
		n += (idx if idx > 0 else am.surface_get_array_len(s)) / 3
	return n

func tree_tris(node: Node) -> int:
	var n := 0
	if node is MeshInstance3D:
		n += tris((node as MeshInstance3D).mesh)
	for c in node.get_children():
		n += tree_tris(c)
	return n

func shot(out: String, key: String, eye: Vector3, target: Vector3, fov: float) -> void:
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	var path := out.path_join("godot_%s.png" % key)
	root.get_texture().get_image().save_png(path)
	print("CAPTURED ", path)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var glb: String = args[0] if args.size() > 0 else ProjectSettings.globalize_path("res://tmp/roads/v5/hardware/hardware.glb")
	var out: String = args[1] if args.size() > 1 else glb.get_base_dir().path_join("godot")
	DirAccess.make_dir_recursive_absolute(out)
	DisplayServer.window_set_size(Vector2i(1600, 900))
	root.size = Vector2i(1600, 900)
	var lib := load_glb(glb)
	if lib == null:
		quit(1)
		return
	# ---- report: every top-level library node (its children are signal heads)
	var nodes := {}
	var problems: Array[String] = []
	var mat_names := {}
	for node in lib.get_children():
		var n3 := node as Node3D
		if n3 == null:
			continue
		var key := String(n3.name)
		if key.ends_with("_001"):                   # export copies of the library objects: Blender appended .001
			key = key.substr(0, key.length() - 4)
		nodes[key] = n3
		var mats: Array[String] = []
		for mi_node in [n3] + n3.find_children("*", "MeshInstance3D", true, false):
			var mi := mi_node as MeshInstance3D
			if mi == null or mi.mesh == null:
				continue
			for s in mi.mesh.get_surface_count():
				var mat := mi.mesh.surface_get_material(s) as BaseMaterial3D
				if mat == null:
					problems.append("%s surface %d has no material" % [mi.name, s])
					continue
				var nm := mat.resource_name
				mat_names[nm] = mat
				if not mats.has(nm):
					mats.append(nm)
		var extras := {}
		if n3.has_meta("extras"):
			extras = n3.get_meta("extras") as Dictionary
		print("HW %-30s tris %6d  mats %s  extras %s" % [n3.name, tree_tris(n3), ",".join(mats), ",".join(PackedStringArray(extras.keys()))])
	for nm: String in mat_names:
		var mat: BaseMaterial3D = mat_names[nm]
		if nm.begins_with("MRS_Lens_") or nm.begins_with("MRS_PropLamp"):
			print("HWMAT %-26s emission %s energy %.2f" % [nm, mat.emission_enabled, mat.emission_energy_multiplier])
			continue
		if nm == "MRS_HW_Glass":
			if mat.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
				problems.append("MRS_HW_Glass is opaque")
			print("HWMAT %-26s transparency %d alpha %.2f cull %d" % [nm, mat.transparency, mat.albedo_color.a, mat.cull_mode])
			continue
		if nm == "MRS_SignFace_Atlas":
			if mat.albedo_texture == null:
				problems.append("MRS_SignFace_Atlas has no albedo texture")
			print("HWMAT %-26s albedo %s roughness %.2f (printed sheeting: albedo only)" % [nm, mat.albedo_texture != null, mat.roughness])
			continue
		var ok := mat.albedo_texture != null and mat.normal_enabled and mat.normal_texture != null and mat.roughness_texture != null and mat.metallic_texture != null
		if not ok:
			problems.append("%s lacks albedo / normal / roughness / metallic textures" % nm)
		print("HWMAT %-26s textures %s  uv1_scale %s  emission %s" % [nm, ok, mat.uv1_scale, mat.emission_enabled])
		if nm.begins_with("MRS_HW_") and nm != "MRS_HW_Stainless" and mat.uv1_scale.is_equal_approx(Vector3.ONE):
			problems.append("%s: KHR_texture_transform not applied (uv1_scale 1)" % nm)
	print("HW nodes %d, materials %d" % [nodes.size(), mat_names.size()])
	if problems.is_empty():
		print("HW textures OK (atlas / tileable materials carry albedo, normal, roughness, metallic; glass transparent)")
	for p in problems:
		print("HW PROBLEM ", p)
	# ---- scene: sky, sun, paving (same as the Blender test)
	var f := FileAccess.open(glb.get_base_dir().path_join("layout.json"), FileAccess.READ)
	if f == null:
		push_error("layout.json missing next to the GLB")
		quit(1)
		return
	var layout: Dictionary = JSON.parse_string(f.get_as_text())
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("6f8fb8")
	sky.sky_horizon_color = Color("c3d0de")
	sky.ground_horizon_color = Color("c3d0de")
	sky.ground_bottom_color = Color("a7aaac")
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.light_energy = 1.6
	root.add_child(sun)
	var sd: Array = layout.get("sun_dir", [0.4, 0.6, -0.6])
	var dir := b2g(sd).normalized()
	sun.look_at_from_position(Vector3.ZERO, dir, Vector3.UP if absf(dir.y) < 0.99 else Vector3.FORWARD)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(240, 240)
	ground.mesh = pm
	var gmat := StandardMaterial3D.new()
	var gpaths: Dictionary = layout.get("ground", {})
	var galb := load_tex(String(gpaths.get("albedo", "")))
	if galb:
		gmat.albedo_texture = galb
		gmat.roughness_texture = load_tex(String(gpaths.get("roughness", "")))
		gmat.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		gmat.normal_enabled = true
		gmat.normal_texture = load_tex(String(gpaths.get("normal", "")))
		gmat.uv1_triplanar = true
		gmat.uv1_world_triplanar = true
		gmat.uv1_scale = Vector3.ONE / float(layout.get("tile_m", 4.0))
	else:
		gmat.albedo_color = Color("8a8a86")
	ground.material_override = gmat
	root.add_child(ground)
	camera = Camera3D.new()
	camera.near = 0.05
	camera.far = 500.0
	root.add_child(camera)
	camera.current = true
	var holder := Node3D.new()
	root.add_child(holder)
	var scenes: Dictionary = layout.get("scenes", {})
	var day_keys: Array = []
	for key in scenes.keys():
		if not bool((scenes[key] as Dictionary).get("night", false)):
			day_keys.append(key)
	for key in day_keys:
		await build_and_shoot(holder, nodes, scenes[key] as Dictionary, out, String(key))
	# ---- night: moon + sky of lighting.night_setup, MrsStreetLights from the Blender light records, lamp heads on
	for key in scenes.keys():
		var sc: Dictionary = scenes[key]
		if not bool(sc.get("night", false)):
			continue
		var night: Dictionary = layout.get("night", {}) as Dictionary
		var moon_info: Dictionary = night.get("moon", {}) as Dictionary
		var sky_info: Dictionary = night.get("sky", {}) as Dictionary
		sky.sky_top_color = lin(sky_info.get("godot_zenith_linear", [0.015, 0.026, 0.064]) as Array).linear_to_srgb()
		sky.sky_horizon_color = lin(sky_info.get("godot_horizon_linear", [0.085, 0.065, 0.05]) as Array).linear_to_srgb()
		sky.ground_horizon_color = sky.sky_horizon_color
		sky.ground_bottom_color = Color(0.02, 0.02, 0.025)
		sky.sun_angle_max = 0.0
		env.glow_enabled = true
		env.glow_intensity = 0.4
		env.glow_bloom = 0.02
		env.glow_hdr_threshold = 1.5
		var md: Vector3 = b2g(moon_info.get("direction", [-0.63, -0.53, -0.57]) as Array).normalized()
		sun.look_at_from_position(Vector3.ZERO, md, Vector3.UP if absf(md.y) < 0.99 else Vector3.FORWARD)
		sun.light_color = lin(moon_info.get("color_linear", [0.62, 0.72, 1.0]) as Array).linear_to_srgb()
		sun.light_energy = float(moon_info.get("godot_energy", 0.16))
		for c in holder.get_children():
			c.free()
		var placed := place_items(holder, nodes, sc)
		var lights: StreetLights = StreetLights.new()
		root.add_child(lights)
		var recs: Array = sc.get("lights", []) as Array
		var cam: Dictionary = sc["camera"]
		var st: Dictionary = lights.build(recs, {"max_shadowed": 4, "lamp_root": holder, "focus": b2g(cam["eye"])})
		lights.set_night(1.0)
		print("HW night: %d lights, %d active, %d shadowed, %d lamp materials (%d items)" % [recs.size(), int(st.get("active", 0)), int(st.get("shadowed", 0)), int(st.get("lamp_materials", 0)), placed])
		await shot(out, String(key), b2g(cam["eye"]), b2g(cam["target"]), float(cam["vfov_deg"]))
		lights.set_night(0.0)
		lights.queue_free()
	lib.free()
	quit()

func place_items(holder: Node3D, nodes: Dictionary, sc: Dictionary) -> int:
	var n := 0
	for it in sc["items"] as Array:
		var item: Dictionary = it
		var src: Node3D = nodes.get(String(item["name"]))
		if src == null:
			print("HW PROBLEM: no node %s" % item["name"])
			continue
		var inst := src.duplicate() as Node3D
		inst.position = b2g(item["pos"])
		inst.rotation = Vector3(0.0, float(item["rot_z"]), 0.0)
		holder.add_child(inst)
		n += 1
	return n

func build_and_shoot(holder: Node3D, nodes: Dictionary, sc: Dictionary, out: String, key: String) -> void:
	for c in holder.get_children():
		c.free()
	place_items(holder, nodes, sc)
	var cam: Dictionary = sc["camera"]
	await shot(out, key, b2g(cam["eye"]), b2g(cam["target"]), float(cam["vfov_deg"]))
