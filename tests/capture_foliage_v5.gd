extends SceneTree
## MRS foliage v5 (Godot side of the Blender / Godot foliage harness; Blender side and metrics:
## tools/roads/tests/foliage_v5_test.py). Run windowed, not headless:
##   godot --path . --windowed --resolution 1280x720 --script res://tests/capture_foliage_v5.gd -- <mode> ...
## modes
##   hedges <before|after>                a hedge row, boxwood balls and a shrub on the lawn under the v4 street-block
##                                        day lighting -> tmp/roads/v5/foliage/hedges/godot_<which>.png (Blender: test hedges)
##   sweep <variant>                      one tree per species (plane_tree, linden_a, walnut_spring, maple_a) seen from
##                                        10 to 250 m in 2 m steps (eye 1.7 m) -> godot_sweep_<variant>/: LOD pops and gaps
##                                        show as jumps of coverage / luminance between steps (foliage_v5_test.py sweep)
##   harness <variant>                    every shot of tmp/roads/v5/foliage/harness.json (written by the Blender side)
##                                        under the matched light rig, transparent background ->
##                                        tmp/roads/v5/foliage/godot_<variant>/<shot>.png (+ capture.json)
##       before_lod0 | before_lod1 | before_imp | before_auto   CityLandscape kit meshes + foliage_wind.gdshader
##       after_lod0 | after_lod1 | after_imp | after_auto       MrsFoliage (mrs_foliage.gdshader, MRS LOD1 / impostors)
##       (auto: the shipping LOD ranges; the others force one representation)
##   block <before|after> [export_dir] [out_dir]   the v4 street block: frame / CPU / GPU time, draw calls, primitives
##                                        at street level, footbridge deck and aerial views (v4 day lighting) + images
##   movie <before|after> <path> [matched]          a moving camera for Movie Maker (--write-movie <ABSOLUTE path>.avi --fixed-fps 30:
##                                        a relative movie path lands in the project root);
##                                        paths: walk (avenue, street level), dolly (10 -> 250 m from a tree group),
##                                        deck (footbridge deck pan). Also writes the path in Blender coordinates
##                                        (tmp/roads/v5/foliage/paths/<path>.json) for the Blender render.

const StreetBlock := preload("res://world/roads/mrs_street_block.gd")
const Foliage := preload("res://world/roads/mrs_foliage.gd")
const OUT := "res://tmp/roads/v5/foliage"
const EXPORT := "res://tmp/roads/v4final/export"

var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var vp_rid: RID
var spec: Dictionary = {}

func _initialize() -> void:
	call_deferred("run")

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

## Blender camera (lens mm on a 36 mm sensor across the 16:9 width) -> Godot vertical fov.
static func vfov(lens: float) -> float:
	var hf := 2.0 * atan(18.0 / lens)
	return rad_to_deg(2.0 * atan(tan(hf * 0.5) * 9.0 / 16.0))

func look(eye: Vector3, target: Vector3, lens: float) -> void:
	camera.position = eye
	camera.look_at(target, Vector3.UP if absf((target - eye).normalized().y) < 0.999 else Vector3.FORWARD)
	camera.fov = vfov(lens)

## Blender sun Euler XYZ (degrees) -> Godot light basis (light travels along -Z).
static func sun_basis(rot: Array) -> Basis:
	var rx := deg_to_rad(float(rot[0]))
	var ry := deg_to_rad(float(rot[1]))
	var rz := deg_to_rad(float(rot[2]))
	var d := Vector3(0, 0, -1)
	d = Vector3(d.x, d.y * cos(rx) - d.z * sin(rx), d.y * sin(rx) + d.z * cos(rx))
	d = Vector3(d.x * cos(ry) + d.z * sin(ry), d.y, -d.x * sin(ry) + d.z * cos(ry))
	d = Vector3(d.x * cos(rz) - d.y * sin(rz), d.x * sin(rz) + d.y * cos(rz), d.z)
	var gd := Vector3(d.x, d.z, -d.y)
	return Basis.looking_at(gd, Vector3.UP)

func base_setup(transparent: bool) -> void:
	# 1280 x 720 physical pixels (the project window is fullscreen and DPI-scaled otherwise)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	root.size = Vector2i(1280, 720)
	vp_rid = root.get_viewport_rid()
	root.transparent_bg = transparent
	root.msaa_3d = Viewport.MSAA_4X
	root.use_debanding = true
	RenderingServer.viewport_set_measure_render_time(vp_rid, true)
	env = Environment.new()
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	camera = Camera3D.new()
	camera.near = 0.05
	camera.far = 3000.0
	root.add_child(camera)
	camera.current = true

## The harness light rig, matched to foliage_v5_test.py (Blender: sun 3.5 W/m2 -> 3.5 / pi here,
## uniform world colour -> constant ambient; linear tonemap = Blender's Standard view transform).
func matched_light() -> void:
	var w: Array = spec.get("world", [0.55, 0.68, 0.85]) as Array
	var wc := Color(float(w[0]), float(w[1]), float(w[2])).linear_to_srgb()
	# a uniform sky (not BG_COLOR): ambient AND reflections see the world colour, as EEVEE's world does
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = wc
	sky.sky_horizon_color = wc
	sky.ground_horizon_color = wc
	sky.ground_bottom_color = wc
	sky.sun_angle_max = 0.0
	sky.sun_curve = 0.0
	sky.sky_energy_multiplier = 1.0
	sky.ground_energy_multiplier = 1.0
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.tonemap_exposure = 1.0
	env.ssao_enabled = false
	env.glow_enabled = false
	sun.basis = sun_basis(spec.get("sun_rot", [52.0, 0.0, -35.0]) as Array)
	sun.light_energy = float(spec.get("sun_strength", 3.5)) / PI
	sun.light_angular_distance = 2.0
	sun.directional_shadow_max_distance = 260.0

## The first harness rig: constant ambient colour, BG_COLOR (no radiance map: weak reflections).
func flat_background() -> void:
	var w: Array = spec.get("world", [0.55, 0.68, 0.85]) as Array
	var wc := Color(float(w[0]), float(w[1]), float(w[2])).linear_to_srgb()
	env.background_mode = Environment.BG_COLOR
	env.background_color = wc
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = wc
	env.reflected_light_source = Environment.REFLECTION_SOURCE_BG

## The v4 street-block night (tests/capture_street_block_v4.gd night()).
func night_light() -> void:
	var nd: Dictionary = block_node.model.get("night", {}) as Dictionary
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
	sun.rotation_degrees = Vector3(-40.0, 145.0, 0.0)
	sun.light_color = Color(0.62, 0.72, 1.0)
	sun.light_energy = float(moon_info.get("godot_energy", 0.16))
	block_node.street_lights.set_night(1.0)

## The v4 street-block day lighting (tests/capture_street_block_v4.gd).
func v4_day() -> void:
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
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
	env.ssao_enabled = true
	env.glow_enabled = false
	sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
	sun.light_energy = 1.35
	sun.directional_shadow_max_distance = 220.0

func grab(path: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)

func settle(frames: int) -> void:
	for i in frames:
		await process_frame

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var mode: String = args[0] if args.size() > 0 else "harness"
	var f := FileAccess.open(OUT.path_join("harness.json"), FileAccess.READ)
	if f:
		spec = JSON.parse_string(f.get_as_text()) as Dictionary
	match mode:
		"harness":
			await harness(args[1] if args.size() > 1 else "before_lod0", args.slice(2))
		"block":
			# block <before|after> [k=v ...]: foliage opts for MrsFoliage.build (numbers / 0-1 switches), tag=<suffix>
			var pos: Array[String] = []
			for a in args.slice(2):
				var kv := a.split("=")
				if kv.size() == 2:
					fol_opts[kv[0]] = (kv[1] == "1") if kv[1] in ["0", "1"] else (float(kv[1]) if kv[1].is_valid_float() else kv[1])
				else:
					pos.append(a)
			await block(args[1] if args.size() > 1 else "after", pos[0] if pos.size() > 0 else EXPORT, pos[1] if pos.size() > 1 else OUT.path_join("block"))
		"hedges":
			await hedges(args[1] if args.size() > 1 else "after")
		"sweep":
			await sweep(args[1] if args.size() > 1 else "after_auto")
		"movie":
			# movie <before|after> <path> [matched]: matched = Blender's QA environment (uniform world sky, sun 3.5 / pi, AgX)
			await movie(args[1] if args.size() > 1 else "after", args[2] if args.size() > 2 else "dolly", EXPORT, args.size() > 3 and args[3] == "matched")
	quit(0)

# ----------------------------------------------------------------------------- harness

var holder: Node3D

## One tree / plant / calibration sphere in the requested representation.
func place(shot: Dictionary, variant: String) -> void:
	if holder:
		holder.free()
	holder = Node3D.new()
	root.add_child(holder)
	var kind := str(shot["kind"])
	var id := str(shot["id"])
	if kind == "calib":
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 1.0
		sm.height = 2.0
		sm.radial_segments = 64
		sm.rings = 32
		mi.mesh = sm
		var m := StandardMaterial3D.new()
		var c: Array = shot["color"] as Array
		m.albedo_color = Color(float(c[0]), float(c[1]), float(c[2])).linear_to_srgb()
		m.roughness = 1.0
		m.metallic_specular = 0.0
		m.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT
		mi.material_override = m
		mi.position = Vector3(0, 1, 0)
		holder.add_child(mi)
		return
	if variant.begins_with("before"):
		var mesh: Mesh
		var custom := Color(0.5, 0.5, 0.5, 0.0)
		var xf := Transform3D.IDENTITY
		var shadow := true
		if kind == "plant":
			mesh = CityLandscape.prop(id).mesh as Mesh
		else:
			var sp: Dictionary = CityLandscape.species(id)
			if variant.ends_with("lod1"):
				mesh = sp.lod1 as Mesh
				shadow = false
			elif variant.ends_with("imp"):
				mesh = CityLandscape._impostor
				custom.a = (float(sp.slot) + 0.1) / 255.0
				xf = Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(sp.far)), Vector3.ZERO)
				shadow = false
			elif variant.ends_with("auto"):
				var land := CityLandscape.new()
				holder.add_child(land)
				var end0 := snappedf(clampf(float(sp.height) * 3.0, 26.0, 42.0), 2.0)
				land.queue(id + "_0", sp.lod0, xf, CityLandscape.LOD0_CELL, 0.0, end0, true, custom)
				land.queue(id + "_1", sp.lod1, xf, CityLandscape.LOD1_CELL, end0, CityLandscape.TREE_FAR_BEGIN, false, custom)
				var ci := custom
				ci.a = (float(sp.slot) + 0.1) / 255.0
				land.queue("impostor", CityLandscape._impostor, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(sp.far)), Vector3.ZERO),
					CityLandscape.FAR_CELL, CityLandscape.TREE_FAR_BEGIN, CityLandscape.FAR_END, false, ci)
				land.flush()
				return
			else:
				mesh = sp.lod0 as Mesh
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = mesh
		mm.instance_count = 1
		mm.set_instance_transform(0, xf)
		mm.set_instance_custom_data(0, custom)
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		holder.add_child(node)
	else:
		var fol: MrsFoliage = Foliage.new()
		holder.add_child(fol)
		var model: Dictionary = {}
		if kind == "plant":
			model["plants"] = [{"id": id, "pos": [0.0, 0.0, 0.0], "yaw": 0.0, "scale": 1.0}]
		else:
			model["trees"] = [{"species": id, "pos": [0.0, 0.0, 0.0], "yaw": 0.0, "scale": 1.0}]
		var force := ""
		for k: String in ["lod0", "lod1", "imp"]:
			if variant.ends_with(k):
				force = k
		fol.build(model, {"force": force, "collision": false, "tint": false, "wind": 0.0})

## Experiment switches (key=value after the variant): shadows=0, mip=<mip_scale>, a2c=0 (no alpha-to-coverage),
## trans=<translucency>, crown=0 (Godot's back-face normal flip), msaa=0|2|4, only=<shot filter>, tag=<dir suffix>,
## direct=<impostor direct_scale>.
var xopts: Dictionary = {}

func shader_variant(code: String) -> String:
	if xopts.has("a2c") and str(xopts["a2c"]) == "0":
		code = code.replace(", alpha_to_coverage_and_one", "")
	if xopts.has("nolight") and str(xopts["nolight"]) == "1":
		code = code.substr(0, code.find("void light() {"))
	if xopts.has("nodither") and str(xopts["nodither"]) == "1":
		code = code.replace("if (x < 0.0 || x >= 1.0) {", "if (false) {")
	return code

## Swaps every MrsFoliage material (also the per-plant copies under `under`) to a modified shader copy.
func apply_shader_variants(under: Node) -> void:
	for sh: Shader in [MrsFoliage.SHADER, MrsFoliage.IMPOSTOR_SHADER]:
		var code := shader_variant(sh.code)
		if code == sh.code:
			continue
		var copy := Shader.new()
		copy.code = code
		var mats: Array[ShaderMaterial] = []
		for k: String in MrsFoliage._materials:
			mats.append(MrsFoliage._materials[k] as ShaderMaterial)
		if MrsFoliage._impostor_material:
			mats.append(MrsFoliage._impostor_material)
		if under:
			for c: Node in under.find_children("*", "MultiMeshInstance3D", true, false):
				var mesh := (c as MultiMeshInstance3D).multimesh.mesh
				for si in mesh.get_surface_count():
					var sm := mesh.surface_get_material(si) as ShaderMaterial
					if sm:
						mats.append(sm)
		for m in mats:
			if m.shader == sh:
				m.shader = copy

func apply_experiments() -> void:
	apply_shader_variants(null)
	var mats: Array[ShaderMaterial] = []
	for k: String in MrsFoliage._materials:
		mats.append(MrsFoliage._materials[k] as ShaderMaterial)
	if MrsFoliage._impostor_material:
		mats.append(MrsFoliage._impostor_material)
	for m in mats:
		if xopts.has("mip"):
			m.set_shader_parameter("mip_scale", float(xopts["mip"]))
		if xopts.has("trans"):
			m.set_shader_parameter("translucency", float(xopts["trans"]))
		if xopts.has("crown"):
			m.set_shader_parameter("crown_normals_both_sides", str(xopts["crown"]) != "0")
	if xopts.has("dither") and MrsFoliage._impostor_material:
		MrsFoliage._impostor_material.set_shader_parameter("dither_coverage", str(xopts["dither"]) != "0")
	if xopts.has("cut") and MrsFoliage._impostor_material:
		MrsFoliage._impostor_material.set_shader_parameter("alpha_cut", float(xopts["cut"]))
	if xopts.has("direct") and MrsFoliage._impostor_material:
		MrsFoliage._impostor_material.set_shader_parameter("direct_scale", float(xopts["direct"]))

func harness(variant: String, extra: Array) -> void:
	for e: Variant in extra:
		var kv := str(e).split("=")
		if kv.size() == 2:
			xopts[kv[0]] = kv[1]
	base_setup(true)
	await settle(3)
	matched_light()
	if xopts.has("shadows"):
		sun.shadow_enabled = str(xopts["shadows"]) != "0"
	if xopts.has("sky") and str(xopts["sky"]) == "0":
		flat_background()
	if xopts.has("rig") and str(xopts["rig"]) == "v4":
		v4_day()                                   # the street-block capture's environment (procedural sky, AgX)
	if xopts.has("blur"):
		sun.shadow_blur = float(xopts["blur"])
	if xopts.has("angular"):
		sun.light_angular_distance = float(xopts["angular"])
	if xopts.has("msaa"):
		root.msaa_3d = {"0": Viewport.MSAA_DISABLED, "2": Viewport.MSAA_2X, "4": Viewport.MSAA_4X, "8": Viewport.MSAA_8X}[str(xopts["msaa"])] as Viewport.MSAA
	if variant.begins_with("after"):
		MrsFoliage.load_assets()
		apply_experiments()
	if variant.begins_with("before"):
		CityLandscape.load_assets()
		for k: String in CityLandscape._materials:
			var m := CityLandscape._materials[k] as ShaderMaterial
			if m:
				m.set_shader_parameter("sway", 0.0)
				m.set_shader_parameter("flutter", 0.0)
	var out := OUT.path_join("godot_" + variant + ("_" + str(xopts["tag"]) if xopts.has("tag") else ""))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var w: Array = spec.get("world", [0.55, 0.68, 0.85]) as Array
	var meta := FileAccess.open(out.path_join("capture.json"), FileAccess.WRITE)
	meta.store_string(JSON.stringify({"bg_linear": w, "variant": variant, "msaa": root.msaa_3d, "size": [root.size.x, root.size.y], "experiments": xopts}))
	meta.close()
	var only: String = str(xopts.get("only", ""))
	if extra.size() > 0 and not str(extra[0]).contains("="):
		only = str(extra[0])
	var n := 0
	var t0 := Time.get_ticks_msec()
	for s: Variant in spec.get("shots", []) as Array:
		var sd: Dictionary = s as Dictionary
		if only != "" and not str(sd["name"]).contains(only):
			continue
		place(sd, variant)
		look(g(sd["eye"] as Array), g(sd["target"] as Array), float(sd.get("lens", 30.0)))
		await settle(5)
		await grab(out.path_join(str(sd["name"]) + ".png"))
		n += 1
	print("HARNESS ", variant, " ", n, " shots in ", Time.get_ticks_msec() - t0, " ms -> ", out)

## Blender coordinates (foliage_v5_test.HEDGE_LAYOUT is the same list).
const HEDGE_LAYOUT: Array = [["hedge_section", -4.8, 0.0], ["hedge_section", -2.4, 0.0], ["hedge_section", 0.0, 0.0], ["hedge_section", 2.4, 0.0],
	["hedge_section", 4.8, 0.0], ["boxwood_ball", -3.0, -1.6], ["boxwood_ball", 0.0, -1.6], ["boxwood_ball", 3.0, -1.6], ["shrub_b", 6.8, -1.2]]

func hedges(which: String) -> void:
	base_setup(false)
	await settle(3)
	v4_day()
	add_ground()
	var out := OUT.path_join("hedges")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var model: Dictionary = {"plants": []}
	for e: Variant in HEDGE_LAYOUT:
		var a: Array = e as Array
		(model["plants"] as Array).append({"id": str(a[0]), "pos": [float(a[1]), float(a[2]), 0.0], "yaw": 0.0, "scale": 1.15 if str(a[0]) == "boxwood_ball" else 1.0})
	if which == "before":
		CityLandscape.load_assets()
		var land := CityLandscape.new()
		root.add_child(land)
		for pd: Variant in model["plants"] as Array:
			var d: Dictionary = pd as Dictionary
			land.queue(str(d["id"]), CityLandscape.prop(str(d["id"])).mesh as Mesh, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(d["scale"])), g(d["pos"] as Array)), 32.0, 0.0, 90.0, true, Color(0.5, 0.5, 0.5, 0.0))
		land.flush()
	else:
		var fol: MrsFoliage = Foliage.new()
		root.add_child(fol)
		fol.build(model, {"tint": false, "collision": false})
	look(g([1.0, -7.5, 1.7]), g([0.5, 0.0, 0.7]), 30.0)
	await settle(10)
	await grab(out.path_join("godot_%s.png" % which))
	print("HEDGES ", which)

const SWEEP_SPECIES: Array[String] = ["plane_tree", "linden_a", "walnut_spring", "maple_a"]

func sweep(variant: String) -> void:
	base_setup(true)
	await settle(3)
	matched_light()
	if variant.begins_with("before"):
		CityLandscape.load_assets()
		for k: String in CityLandscape._materials:
			var m := CityLandscape._materials[k] as ShaderMaterial
			if m:
				m.set_shader_parameter("sway", 0.0)
				m.set_shader_parameter("flutter", 0.0)
	var out := OUT.path_join("godot_sweep_" + variant)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var w: Array = spec.get("world", [0.55, 0.68, 0.85]) as Array
	var meta := FileAccess.open(out.path_join("capture.json"), FileAccess.WRITE)
	meta.store_string(JSON.stringify({"bg_linear": w, "variant": variant}))
	meta.close()
	var heights: Dictionary = spec.get("heights", {}) as Dictionary
	var az := deg_to_rad(25.0)
	for sid in SWEEP_SPECIES:
		place({"kind": "tree", "id": sid}, variant)
		var hgt: float = float(heights.get(sid, 10.0))
		var d := 10
		while d <= 250:
			look(g([float(d) * sin(az), -float(d) * cos(az), 1.7]), g([0.0, 0.0, hgt * 0.55]), 30.0)
			await settle(3)
			await grab(out.path_join("%s_d%03d.png" % [sid, d]))
			d += 2
	print("SWEEP ", variant, " -> ", out)

# ----------------------------------------------------------------------------- street block (perf)

const BLOCK_VIEWS: Array[Dictionary] = [
	{"name": "street", "eye": [-74.39, -19.05, 1.8], "target": [-40.39, -18.55, 1.35], "lens": 30.0},
	{"name": "street_cyclist", "eye": [46.92, -12.8, 1.97], "target": [76.92, -12.8, 1.67], "lens": 30.0},
	{"name": "deck", "eye": [-51.28, -19.31, 8.47], "target": [-48.5, 18.8, 8.47], "lens": 30.0},
	{"name": "deck_west", "eye": [-50.5, -2.0, 8.5], "target": [-100.0, 10.0, 4.0], "lens": 30.0},
	{"name": "aerial", "eye": [-95.0, -80.0, 45.0], "target": [-50.0, -10.0, 2.0], "lens": 32.0},
	{"name": "overhead", "eye": [20.0, -125.0, 110.0], "target": [10.0, -15.0, 0.0], "lens": 24.0},
]

var block_node: StreetBlock
var foliage: MrsFoliage
var fol_opts: Dictionary = {}

func load_block(which: String, dir: String) -> Dictionary:
	var t0 := Time.get_ticks_usec()
	block_node = StreetBlock.new()
	root.add_child(block_node)
	var counts: Dictionary = block_node.build(dir, "street_block", {"max_shadowed": 4, "trees": which == "before", "lights": true})
	if which == "after":
		foliage = Foliage.new()
		foliage.name = "MrsFoliage"
		block_node.add_child(foliage)
		var fo: Dictionary = fol_opts.duplicate()
		for k: String in ["tag", "a2c", "nolight", "nodither"]:
			if fo.has(k):
				xopts[k] = "1" if (fo[k] is bool and bool(fo[k])) else ("0" if fo[k] is bool else str(fo[k]))
				fo.erase(k)
		counts["foliage"] = foliage.build(block_node.model, fo)
		apply_shader_variants(foliage)
	counts["build_ms"] = float(Time.get_ticks_usec() - t0) / 1000.0
	return counts

func add_ground() -> void:
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

## Median CPU / GPU time over `frames` frames (vsync off: the GPU runs flat out, so clocks do not idle between
## frames and the timings are comparable), plus this frame's draw calls / primitives / objects.
func measure(frames: int) -> Dictionary:
	var cpus: Array[float] = []
	var gpus: Array[float] = []
	var t0 := Time.get_ticks_usec()
	for i in frames:
		await process_frame
		cpus.append(RenderingServer.viewport_get_measured_render_time_cpu(vp_rid) + RenderingServer.get_frame_setup_time_cpu())
		gpus.append(RenderingServer.viewport_get_measured_render_time_gpu(vp_rid))
	cpus.sort()
	gpus.sort()
	var wall := float(Time.get_ticks_usec() - t0) / 1000.0 / float(frames)
	return {"cpu_ms": snappedf(cpus[frames / 2], 0.01), "gpu_ms": snappedf(gpus[frames / 2], 0.01), "frame_ms": snappedf(wall, 0.01),
		"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		"objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)}

func block(which: String, dir: String, out: String) -> void:
	base_setup(false)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	v4_day()
	add_ground()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var counts := load_block(which, dir)
	if block_node.street_lights:
		block_node.street_lights.follow(camera)
		block_node.street_lights.set_night(0.0)
	print("BLOCK ", which, " ", counts)
	await settle(4)
	var stats: Dictionary = {"which": which, "counts": counts, "views": {}}
	for v in BLOCK_VIEWS:
		look(g(v["eye"] as Array), g(v["target"] as Array), float(v["lens"]))
		await settle(8)
		# trees only: the same view with the foliage hidden gives the foliage share of the frame
		var full: Dictionary = await measure(120)
		var fol_node: Node = foliage if which == "after" else block_node.landscape as Node
		var tree_trunks: Node = null
		if fol_node:
			(fol_node as Node3D).visible = false
			await settle(4)
			var bare: Dictionary = await measure(120)
			(fol_node as Node3D).visible = true
			full["without_foliage"] = bare
			# trees only / plants only (the other part hidden)
			for part: String in ["trees_only", "plants_only"]:
				var hidden: Array[Node3D] = []
				for c: Node in fol_node.get_children():
					var mmi := c as MultiMeshInstance3D
					if mmi == null:
						continue
					var is_plant: bool = str(mmi.get_meta("asset", mmi.get_meta("prop", ""))).begins_with("plant_") if which == "after" else not (str(mmi.get_meta("prop", "")).contains("_0") or str(mmi.get_meta("prop", "")).contains("_1") or str(mmi.get_meta("prop", "")) == "impostor")
					if (part == "trees_only") == is_plant:
						mmi.visible = false
						hidden.append(mmi)
				await settle(4)
				full[part] = await measure(120)
				for h in hidden:
					h.visible = true
		await settle(4)
		await grab(out.path_join("%s%s_%s.png" % [which, ("_" + str(fol_opts["tag"])) if fol_opts.has("tag") else "", str(v["name"])]))
		(stats["views"] as Dictionary)[str(v["name"])] = full
		print("VIEW ", v["name"], " ", full)
	stats["opts"] = fol_opts
	var tag := ("_" + str(fol_opts["tag"])) if fol_opts.has("tag") else ""
	# night: the street lamps (omni / spot) through the foliage light() (images only)
	if block_node.street_lights:
		night_light()
		for v in BLOCK_VIEWS:
			if str(v["name"]) in ["street", "aerial", "deck"]:
				look(g(v["eye"] as Array), g(v["target"] as Array), float(v["lens"]))
				block_node.street_lights.update_shadows(camera.global_position)
				await settle(8)
				await grab(out.path_join("%s%s_%s_night.png" % [which, tag, str(v["name"])]))
	var sf := FileAccess.open(out.path_join("perf_%s%s.json" % [which, tag]), FileAccess.WRITE)
	sf.store_string(JSON.stringify(stats, " "))
	sf.close()

# ----------------------------------------------------------------------------- movies

## Camera paths (Blender coordinates, as the Blender video render reads them): list of frames.
static func path_frames(name: String) -> Array:
	var frames: Array = []
	match name:
		"walk":
			# 13 s along the avenue's south sidewalk (centre y -14.7, tree pits y -13.3) at 2.3 m/s, eye 1.7 m
			for i in 390:
				var t := float(i) / 30.0
				var x := -140.0 + t * 2.3
				frames.append({"eye": [x, -15.6, 2.25], "target": [x + 25.0, -13.0 + 1.5 * sin(t * 0.3), 3.6], "lens": 30.0})
		"dolly":
			# 14 s: from 10 m to 250 m south of a park tree group (7 trees within 20 m, >= 7.7 m from every trunk on
			# the way), eye rising 1.7 -> 9 m, eased: LOD0 -> LOD1 -> impostor for every tree in view
			var c := [-70.0, -71.0, 5.0]
			for i in 420:
				var u := float(i) / 419.0
				var e := u * u * (3.0 - 2.0 * u)
				var d := 10.0 * pow(25.0, e)
				frames.append({"eye": [c[0], c[1] - d, 1.7 + 7.3 * e], "target": c, "lens": 30.0})
		"deck":
			# 12 s on the footbridge deck (6.8 m): pan from west along the avenue over the park to east, eye 8.5 m
			for i in 360:
				var u := float(i) / 359.0
				var a := deg_to_rad(lerpf(180.0, 360.0, u))
				var eye := [-50.6, -12.0 + u * 10.0, 8.5]
				frames.append({"eye": eye, "target": [float(eye[0]) + cos(a) * 40.0, float(eye[1]) + sin(a) * 40.0, 5.5], "lens": 30.0})
	return frames

func movie(which: String, path_name: String, dir: String, matched: bool = false) -> void:
	base_setup(false)
	v4_day()
	if matched:
		matched_light()
		env.tonemap_mode = Environment.TONE_MAPPER_AGX
	add_ground()
	var counts := load_block(which, dir)
	if block_node.street_lights:
		block_node.street_lights.follow(camera)
		block_node.street_lights.set_night(0.0)
	var frames := path_frames(path_name)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.path_join("paths")))
	var pf := FileAccess.open(OUT.path_join("paths/%s.json" % path_name), FileAccess.WRITE)
	pf.store_string(JSON.stringify({"frames": frames}))
	pf.close()
	print("MOVIE ", which, " ", path_name, " frames ", frames.size(), " ", counts)
	# Movie Maker: one engine frame per movie frame (--fixed-fps 30)
	var first: Dictionary = frames[0] as Dictionary
	look(g(first["eye"] as Array), g(first["target"] as Array), float(first["lens"]))
	await settle(10)
	for fr: Variant in frames:
		var fd: Dictionary = fr as Dictionary
		look(g(fd["eye"] as Array), g(fd["target"] as Array), float(fd["lens"]))
		await process_frame
