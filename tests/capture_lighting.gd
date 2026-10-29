extends SceneTree
## Godot check of the Road Studio street lighting (tools/roads/tests/lighting_test.py export):
## 1. calibration: white Lambert plane under one SpotLight3D (attenuation 2) -> measured value vs energy / d^2
##    (the Blender side is P / (4 pi^2 d^2) per W, so lighting.GODOT_ENERGY_PER_W = 2^EV / (4 pi^2));
## 2. loads lighting_street.glb (roads + poles, no punctual lights) and lighting_lights.json, builds the
##    lights with MrsStreetLights (max_shadowed nearest / brightest cast shadows, distance fade), lights
##    the lamp-head materials, sets up the same night (sky, moon, AgX) and captures the Blender views
##    to <out>/godot_<view>.png, printing active / shadow-casting light counts and frame times;
## 3. shadow budget sweep (0 / 4 / 8 / all) on one view: GPU frame time per budget.
## usage: godot --path . --script res://tests/capture_lighting.gd -- [export_dir] [out_dir] [max_shadowed]
const StreetLights := preload("res://world/roads/mrs_street_lights.gd")

var camera: Camera3D
var rid: RID

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

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func lin(v: Array, k: float = 1.0) -> Color:
	return Color(float(v[0]) * k, float(v[1]) * k, float(v[2]) * k)

## Average CPU / GPU render time (ms) and wall-clock frame time over `frames` frames.
func measure(frames: int) -> Dictionary:
	var cpu := 0.0
	var gpu := 0.0
	var t0 := Time.get_ticks_usec()
	for i in frames:
		await process_frame
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(rid) + RenderingServer.get_frame_setup_time_cpu()
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(rid)
	var wall := float(Time.get_ticks_usec() - t0) / 1000.0 / float(frames)
	return {"cpu_ms": snappedf(cpu / frames, 0.01), "gpu_ms": snappedf(gpu / frames, 0.01), "frame_ms": snappedf(wall, 0.01)}

func calibrate() -> float:
	var holder := Node3D.new()
	root.add_child(holder)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.BLACK
	env.ambient_light_energy = 0.0
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	holder.add_child(we)
	var plane := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(40, 40)
	plane.mesh = pm
	var m := StandardMaterial3D.new()
	m.albedo_color = Color.WHITE
	m.roughness = 1.0
	m.metallic_specular = 0.0
	plane.material_override = m
	holder.add_child(plane)
	var spot := SpotLight3D.new()
	spot.light_energy = 10.0
	spot.spot_attenuation = 2.0
	spot.spot_range = 1000.0
	spot.spot_angle = 60.0
	spot.spot_angle_attenuation = 0.01
	spot.light_specular = 0.0
	spot.position = Vector3(0, 5, 0)
	spot.rotation_degrees = Vector3(-90, 0, 0)
	holder.add_child(spot)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 0.5
	cam.position = Vector3(0, 20, 0)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	holder.add_child(cam)
	cam.current = true
	for i in 10:
		await process_frame
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	var c := img.get_pixel(img.get_width() / 2, img.get_height() / 2).srgb_to_linear()
	var expected := 10.0 / 25.0
	print("LIGHTING calibration: white Lambert under energy 10 at 5 m = ", snappedf(c.r, 0.0001), " (energy / d^2 = ", expected, ") ratio ", snappedf(c.r / expected, 0.001))
	root.remove_child(holder)
	holder.queue_free()
	return c.r / expected

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var dir: String = args[0] if args.size() > 0 else "res://tmp/roads/v4/lighting/export"
	var out: String = args[1] if args.size() > 1 else "res://tmp/roads/v4/lighting"
	var max_shadowed: int = int(args[2]) if args.size() > 2 else 4
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	root.size = Vector2i(1280, 720)
	rid = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(rid, true)
	var ratio := await calibrate()

	var f := FileAccess.open(dir.path_join("lighting_lights.json"), FileAccess.READ)
	if f == null:
		push_error("no lighting_lights.json in " + dir)
		quit(1)
		return
	var model: Dictionary = JSON.parse_string(f.get_as_text()) as Dictionary
	var records: Array = model.get("lights", []) as Array
	var views: Dictionary = model.get("views", {}) as Dictionary
	var night: Dictionary = model.get("night", {}) as Dictionary
	var moon_info: Dictionary = night.get("moon", {}) as Dictionary
	var sky_info: Dictionary = night.get("sky", {}) as Dictionary

	# night environment matching lighting.night_setup (values pre-multiplied by 2^EV, exposure 1 here)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = lin(sky_info.get("godot_zenith_linear", [0.015, 0.026, 0.064]) as Array).linear_to_srgb()
	sky.sky_horizon_color = lin(sky_info.get("godot_horizon_linear", [0.085, 0.065, 0.05]) as Array).linear_to_srgb()
	sky.ground_horizon_color = sky.sky_horizon_color
	sky.ground_bottom_color = Color(0.02, 0.02, 0.025)
	sky.sun_angle_max = 0.0
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_bloom = 0.02
	env.glow_hdr_threshold = 1.5
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var moon := DirectionalLight3D.new()
	var md: Vector3 = g(moon_info.get("direction", [-0.63, -0.53, -0.57]) as Array).normalized()
	moon.transform = Transform3D(Basis.looking_at(md, Vector3.UP), Vector3.ZERO)
	moon.light_color = lin(moon_info.get("color_linear", [0.62, 0.72, 1.0]) as Array).linear_to_srgb()
	moon.light_energy = float(moon_info.get("godot_energy", 0.16))
	moon.shadow_enabled = true
	root.add_child(moon)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(900, 900)
	ground.mesh = pm
	ground.position = Vector3(50, -0.12, -160)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.16, 0.24, 0.09).linear_to_srgb()
	gm.roughness = 0.95
	ground.material_override = gm
	root.add_child(ground)

	var street := load_glb(dir.path_join("lighting_street.glb"))
	var tris := 0
	if street:
		root.add_child(street)
		for mi in street.find_children("*", "MeshInstance3D", true, false):
			tris += CityForgeWorld.triangles((mi as MeshInstance3D).mesh)
	camera = Camera3D.new()
	camera.far = 2000.0
	camera.near = 0.05
	root.add_child(camera)
	camera.current = true

	var lights: StreetLights = StreetLights.new()
	lights.name = "MrsStreetLights"
	root.add_child(lights)
	var t0 := Time.get_ticks_usec()
	var s: Dictionary = lights.build(records, {"max_shadowed": max_shadowed, "lamp_root": street, "focus": Vector3.ZERO})
	print("LIGHTING build ", snappedf(float(Time.get_ticks_usec() - t0) / 1000.0, 0.01), " ms; street ", tris, " tris; ", s)
	lights.set_night(1.0)

	var names: Array = views.keys()
	names.sort()
	var summary: Array[String] = []
	for vn: Variant in names:
		var name: String = str(vn)
		var v: Dictionary = views[name] as Dictionary
		camera.position = g(v["eye"] as Array)
		camera.fov = float(v.get("fov_v", 45.0))
		camera.look_at(g(v["target"] as Array), Vector3.UP)
		var shadowed: int = lights.update_shadows(camera.global_position)
		for i in 12:
			await process_frame
		var t: Dictionary = await measure(30)
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out.path_join("godot_night_%s.png" % name))
		var visible_lights := 0
		for l: Light3D in lights.lights:
			if l.visible and l.global_position.distance_to(camera.global_position) < l.distance_fade_begin + l.distance_fade_length:
				visible_lights += 1
		var line := "%s: lights within fade %d, shadow-casting %d, cpu %.2f ms, gpu %.2f ms, frame %.2f ms" % [name, visible_lights, shadowed, t["cpu_ms"], t["gpu_ms"], t["frame_ms"]]
		summary.append(line)
		print("CAPTURED ", line)

	# shadow budget sweep on the urban driver view (the busiest one)
	if views.has("urban_driver"):
		var v: Dictionary = views["urban_driver"] as Dictionary
		camera.position = g(v["eye"] as Array)
		camera.fov = float(v.get("fov_v", 45.0))
		camera.look_at(g(v["target"] as Array), Vector3.UP)
		for budget: int in [0, 4, 8, 64]:
			lights.options["max_shadowed"] = budget
			var n: int = lights.update_shadows(camera.global_position)
			for i in 10:
				await process_frame
			var t: Dictionary = await measure(60)
			print("LIGHTING shadow budget ", budget, ": ", n, " shadow-casting, gpu ", t["gpu_ms"], " ms, cpu ", t["cpu_ms"], " ms, frame ", t["frame_ms"], " ms")
	# day toggle
	lights.set_night(0.0)
	var day: Dictionary = lights.stats()
	print("LIGHTING day: active ", day["active"], ", shadowed ", day["shadowed"], ", lamp materials emission ",
		lights.lamp_materials[0].emission_enabled if lights.lamp_materials.size() > 0 else false)

	# stress: the urban / residential / highway records tiled into a 1.9 km x 3 street district (~700 lights),
	# camera on the avenue; distance fade + shadow budget vs. no fade / bigger budgets
	if views.has("urban_driver"):
		var tiled: Array[Dictionary] = []
		for item: Variant in records:
			var rec: Dictionary = item as Dictionary
			if not (str(rec.get("class", "")) in ["urban", "residential", "highway"]):
				continue
			var step: float = 32.0 if str(rec["class"]) == "urban" else (30.0 if str(rec["class"]) == "residential" else 40.0)
			for k in range(-30, 31):
				var r2: Dictionary = rec.duplicate(true)
				var p: Array = r2["position"] as Array
				p[0] = float(p[0]) + float(k) * step * 2.0
				r2["id"] = "%s_t%d" % [str(rec["id"]), k]
				tiled.append(r2)
		lights.set_night(1.0)          # lamp heads glowing again ...
		lights.visible = false         # ... but the 18 real lights hidden (the tiles include them)
		var stress: StreetLights = StreetLights.new()
		stress.name = "Stress"
		root.add_child(stress)
		var v: Dictionary = views["urban_driver"] as Dictionary
		camera.position = g(v["eye"] as Array)
		camera.fov = float(v.get("fov_v", 45.0))
		camera.look_at(g(v["target"] as Array), Vector3.UP)
		for cfg: Dictionary in [{"label": "fade on, 4 shadows", "max": 4, "fade": true},
				{"label": "fade on, 0 shadows", "max": 0, "fade": true},
				{"label": "fade on, 16 shadows", "max": 16, "fade": true},
				{"label": "fade off, 4 shadows", "max": 4, "fade": false}]:
			stress.build(tiled, {"max_shadowed": int(cfg["max"]), "focus": camera.global_position})
			var within := 0
			for l: Light3D in stress.lights:
				l.distance_fade_enabled = bool(cfg["fade"])
				if l.global_position.distance_to(camera.global_position) < l.distance_fade_begin + l.distance_fade_length:
					within += 1
			var n: int = stress.update_shadows(camera.global_position)
			for i in 15:
				await process_frame
			var t: Dictionary = await measure(60)
			print("LIGHTING stress ", cfg["label"], ": ", stress.lights.size(), " lights, ", within if bool(cfg["fade"]) else stress.lights.size(),
				" drawn (within fade), ", n, " shadow-casting, gpu ", t["gpu_ms"], " ms, cpu ", t["cpu_ms"], " ms, frame ", t["frame_ms"], " ms")
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out.path_join("godot_stress_fade_off.png"))
		stress.build(tiled, {"max_shadowed": 4, "focus": camera.global_position})
		for i in 15:
			await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out.path_join("godot_stress_fade_on.png"))
		stress.queue_free()
	print("LIGHTING summary: calibration ratio ", snappedf(ratio, 0.001), ", ", s["records"], " lights, max_shadowed ", max_shadowed)
	quit()
