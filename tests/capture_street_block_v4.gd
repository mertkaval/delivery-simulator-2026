extends SceneTree
## Godot 4.7 verification of the Road Studio v4 street block (MrsStreetBlock loader):
##  * loads <export>/street_block{.glb,_collision.glb,_props.glb,_signals.glb,.json};
##  * captures the Blender camera list (<cameras.json>: name, eye, target, lens, night flag) by day and at
##    night with the same framing -> <out>/godot_<view>.png (night views: godot_<view>_night.png);
##  * collision: rays down on every footbridge / park-path / sidewalk route point (hit height vs route z);
##  * signals: per-signal lens control, phase 0 / phase 1 green counts (no conflicting greens);
##  * performance: frame / CPU / GPU time, draw calls, primitives per view; tree / plant MultiMesh counts;
##    active and shadow-casting lights at night.
## usage: godot --path . --script res://tests/capture_street_block_v4.gd -- <export_dir> <out_dir> <cameras.json>

const StreetBlock := preload("res://world/roads/mrs_street_block.gd")

var camera: Camera3D
var block: StreetBlock
var env: Environment
var sun: DirectionalLight3D
var moon: DirectionalLight3D
var vp_rid: RID
var stats: Dictionary = {}

func _initialize() -> void:
	call_deferred("run")

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

func measure(frames: int) -> Dictionary:
	var cpu := 0.0
	var gpu := 0.0
	var t0 := Time.get_ticks_usec()
	for i in frames:
		await process_frame
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(vp_rid) + RenderingServer.get_frame_setup_time_cpu()
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp_rid)
	var wall := float(Time.get_ticks_usec() - t0) / 1000.0 / float(frames)
	return {"cpu_ms": snappedf(cpu / frames, 0.01), "gpu_ms": snappedf(gpu / frames, 0.01), "frame_ms": snappedf(wall, 0.01),
		"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		"objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)}

func set_view(v: Dictionary) -> void:
	var eye := g(v["eye"] as Array)
	var tgt := g(v["target"] as Array)
	camera.position = eye
	camera.look_at(tgt, Vector3.UP)
	# Blender: 36 mm sensor across the 16:9 width -> vertical fov for KEEP_HEIGHT
	var hf := 2.0 * atan(18.0 / float(v.get("lens", 35.0)))
	camera.fov = rad_to_deg(2.0 * atan(tan(hf * 0.5) * 9.0 / 16.0))

func shot(out: String, name: String) -> Dictionary:
	for i in 6:
		await process_frame
	var m: Dictionary = await measure(20)
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("godot_%s.png" % name))
	print("CAPTURED ", name, " ", m)
	return m

func day() -> void:
	env.background_mode = Environment.BG_SKY
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color(0.38, 0.52, 0.72)
	sky.sky_horizon_color = Color(0.72, 0.76, 0.80)
	sky.ground_horizon_color = Color(0.62, 0.64, 0.62)
	sky.ground_bottom_color = Color(0.28, 0.30, 0.26)
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.glow_enabled = false
	sun.visible = true
	moon.visible = false
	block.street_lights.set_night(0.0)

func night() -> void:
	var nd: Dictionary = block.model.get("night", {}) as Dictionary
	var sky_info: Dictionary = nd.get("sky", {}) as Dictionary
	var moon_info: Dictionary = nd.get("moon", {}) as Dictionary
	var sky := ProceduralSkyMaterial.new()
	var zen: Array = sky_info.get("godot_zenith_linear", [0.015, 0.026, 0.064]) as Array
	var hor: Array = sky_info.get("godot_horizon_linear", [0.085, 0.065, 0.05]) as Array
	sky.sky_top_color = Color(float(zen[0]), float(zen[1]), float(zen[2])).linear_to_srgb()
	sky.sky_horizon_color = Color(float(hor[0]), float(hor[1]), float(hor[2])).linear_to_srgb()
	sky.ground_horizon_color = sky.sky_horizon_color
	sky.ground_bottom_color = Color(0.02, 0.02, 0.025)
	sky.sun_angle_max = 0.0
	env.sky.sky_material = sky
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_bloom = 0.02
	env.glow_hdr_threshold = 1.5
	sun.visible = false
	moon.visible = true
	moon.light_energy = float(moon_info.get("godot_energy", 0.16))
	block.street_lights.set_night(1.0)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var dir: String = args[0] if args.size() > 0 else "res://tmp/roads/v4/export"
	var out: String = args[1] if args.size() > 1 else "res://tmp/roads/v4/godot"
	var cams_path: String = args[2] if args.size() > 2 else dir.path_join("cameras.json")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out) if out.begins_with("res://") else out)
	vp_rid = root.get_viewport_rid()
	root.use_debanding = true
	root.msaa_3d = Viewport.MSAA_4X
	RenderingServer.viewport_set_measure_render_time(vp_rid, true)
	env = Environment.new()
	env.sky = Sky.new()
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 220.0
	root.add_child(sun)
	moon = DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-40.0, 145.0, 0.0)
	moon.light_color = Color(0.62, 0.72, 1.0)
	moon.shadow_enabled = true
	root.add_child(moon)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(900, 900)
	ground.mesh = pm
	ground.position = Vector3(50, -0.12, 0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.16, 0.24, 0.09).linear_to_srgb()
	gm.roughness = 0.95
	ground.material_override = gm
	root.add_child(ground)
	camera = Camera3D.new()
	camera.near = 0.05
	camera.far = 2500.0
	root.add_child(camera)
	camera.current = true

	var t0 := Time.get_ticks_msec()
	block = StreetBlock.new()
	root.add_child(block)
	var counts: Dictionary = block.build(dir, "street_block", {"max_shadowed": 4})
	block.street_lights.follow(camera)
	stats["build_ms"] = Time.get_ticks_msec() - t0
	stats["counts"] = counts
	print("BLOCK ", counts, " in ", stats["build_ms"], " ms")
	for i in 4:
		await process_frame

	# ---- collision rays on route points (footbridge decks / ramps / stairs, park paths, sidewalks)
	var space := root.world_3d.direct_space_state
	var routes: Dictionary = block.model.get("routes", {}) as Dictionary
	var ped: Dictionary = routes.get("ped", {}) as Dictionary
	var ray := {"tested": 0, "hit": 0, "max_err": 0.0, "by_kind": {}}
	for e: Variant in ped.get("edges", []) as Array:
		var ed: Dictionary = e as Dictionary
		var kind := str(ed.get("kind", ""))
		if not (kind.begins_with("footbridge") or kind in ["sidewalk", "park_path", "path", "crossing"]):
			continue
		var pts: Array = ed.get("points", []) as Array
		for i in range(0, pts.size(), maxi(1, pts.size() / 6)):
			var p := g(pts[i] as Array)
			var q := PhysicsRayQueryParameters3D.create(p + Vector3(0, 1.2, 0), p - Vector3(0, 3.0, 0))
			var hit := space.intersect_ray(q)
			ray["tested"] = int(ray["tested"]) + 1
			var bk: Dictionary = (ray["by_kind"] as Dictionary).get(kind, {"tested": 0, "hit": 0, "max_err": 0.0}) as Dictionary
			bk["tested"] = int(bk["tested"]) + 1
			if hit.is_empty() and (ray.get("misses", []) as Array).size() < 12:
				if not ray.has("misses"): ray["misses"] = []
				(ray["misses"] as Array).append([kind, str(ed.get("id", "")).left(40), snappedf(p.x, 0.1), snappedf(p.y, 0.01), snappedf(p.z, 0.1)])
			if not hit.is_empty():
				var err: float = absf((hit["position"] as Vector3).y - p.y)
				ray["hit"] = int(ray["hit"]) + 1
				bk["hit"] = int(bk["hit"]) + 1
				ray["max_err"] = maxf(float(ray["max_err"]), err)
				bk["max_err"] = maxf(float(bk["max_err"]), err)
			(ray["by_kind"] as Dictionary)[kind] = bk
	stats["collision_rays"] = ray
	print("RAYS ", ray)

	# ---- signal control
	block.set_phase(0)
	var g0 := block.green_count()
	block.set_phase(1)
	var g1 := block.green_count()
	block.set_phase(0)
	stats["signals"] = {"count": block.signals.size(), "green_phase0": g0, "green_phase1": g1}
	print("SIGNALS ", stats["signals"])

	# ---- views
	var cams: Array = []
	var cf := FileAccess.open(cams_path, FileAccess.READ)
	if cf:
		cams = JSON.parse_string(cf.get_as_text()) as Array
	var perf: Dictionary = {}
	day()
	for v: Variant in cams:
		var vd: Dictionary = v as Dictionary
		set_view(vd)
		block.street_lights.update_shadows(camera.global_position)
		perf[str(vd["name"])] = await shot(out, str(vd["name"]))
	night()
	for v: Variant in cams:
		var vd: Dictionary = v as Dictionary
		if not bool(vd.get("night", false)):
			continue
		set_view(vd)
		block.street_lights.update_shadows(camera.global_position)
		var m: Dictionary = await shot(out, str(vd["name"]) + "_night")
		m["lights"] = block.street_lights.stats()
		perf[str(vd["name"]) + "_night"] = m
	stats["views"] = perf
	var sf := FileAccess.open(out.path_join("godot_stats.json"), FileAccess.WRITE)
	sf.store_string(JSON.stringify(stats, " "))
	print("GODOT_V4 DONE")
	quit(0)
