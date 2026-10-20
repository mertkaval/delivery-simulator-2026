class_name WeatherSystem
extends Node3D
## Vancouver weather: dry spells, overcast, drizzle and steady rain on a deterministic
## forecast driven by game time. Rain falls around the camera as GPU particles that stop at
## roofs and awnings (height-field collision) and splash where they land; the global shader
## parameters `wetness` and `rain_intensity` darken and gloss roads, sidewalks and plazas,
## fill gutters and ruts with rippling puddles; the sky closes over, the sun dims, fog
## thickens, and CityAudio crossfades in the rain loop.

const STATES := ["Clear", "Overcast", "Drizzle", "Rain"]
var rain := 0.0          ## current rainfall 0..1
var overcast := 0.0      ## cloud cover 0..1
var wetness := 0.0       ## surface water 0..1 (lags the rain, dries slowly)
var forced := -1.0       ## >= 0 overrides the forecast (tests, captures)
var minutes := 0.0       ## continuous game minutes (days roll over)
var last_hour := -1.0
var day := 0
var drops: GPUParticles3D
var splashes: GPUParticles3D
var cover: GPUParticlesCollisionHeightField3D
var follow: Node3D

func _ready() -> void:
	follow = Node3D.new()
	follow.top_level = true
	add_child(follow)
	# Rain streaks: vertical billboards falling at ~10 m/s with a slight wind slant.
	drops = GPUParticles3D.new()
	drops.amount = 6000
	drops.lifetime = 1.4
	drops.preprocess = 1.4
	drops.visibility_aabb = AABB(Vector3(-28, -24, -28), Vector3(56, 30, 56))
	drops.local_coords = false
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	process.emission_box_extents = Vector3(24, 1, 24)
	process.direction = Vector3(0.12, -1, 0.05)
	process.spread = 2.0
	process.initial_velocity_min = 10.0
	process.initial_velocity_max = 12.0
	process.gravity = Vector3(0, -2, 0)
	process.collision_mode = ParticleProcessMaterial.COLLISION_HIDE_ON_CONTACT
	process.collision_use_scale = false
	process.sub_emitter_mode = ParticleProcessMaterial.SUB_EMITTER_AT_COLLISION
	process.sub_emitter_amount_at_collision = 1
	drops.process_material = process
	var streak := QuadMesh.new()
	streak.size = Vector2(0.008, 0.5)
	var streak_mat := StandardMaterial3D.new()
	streak_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	streak_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	streak_mat.albedo_color = Color(0.78, 0.83, 0.88, 0.26)
	streak_mat.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	streak_mat.billboard_keep_scale = true
	streak.material = streak_mat
	drops.draw_pass_1 = streak
	drops.position = Vector3(0, 14, 0)
	follow.add_child(drops)
	# Splashes: tiny flat rings that spread and fade where a drop lands.
	splashes = GPUParticles3D.new()
	splashes.amount = 1500
	splashes.lifetime = 0.3
	splashes.local_coords = false
	var splash_process := ParticleProcessMaterial.new()
	splash_process.gravity = Vector3.ZERO
	splash_process.scale_min = 0.6
	splash_process.scale_max = 1.2
	var grow := CurveTexture.new()
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0.2))
	curve.add_point(Vector2(1, 1.0))
	grow.curve = curve
	splash_process.scale_curve = grow
	var fade := GradientTexture1D.new()
	var gradient := Gradient.new()
	gradient.set_color(0, Color(1, 1, 1, 0.5))
	gradient.set_color(1, Color(1, 1, 1, 0.0))
	fade.gradient = gradient
	splash_process.color_ramp = fade
	splashes.process_material = splash_process
	var ring := QuadMesh.new()
	ring.size = Vector2(0.09, 0.09)
	ring.orientation = PlaneMesh.FACE_Y
	var ring_mat := StandardMaterial3D.new()
	ring_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring_mat.vertex_color_use_as_albedo = true
	ring_mat.albedo_color = Color(0.85, 0.9, 0.95, 0.6)
	ring.material = ring_mat
	splashes.draw_pass_1 = ring
	splashes.emitting = false  # driven by the drops' collisions
	follow.add_child(splashes)
	drops.sub_emitter = drops.get_path_to(splashes)
	# Roofs, awnings and trees shelter what is under them.
	cover = GPUParticlesCollisionHeightField3D.new()
	cover.size = Vector3(56, 40, 56)
	cover.resolution = GPUParticlesCollisionHeightField3D.RESOLUTION_512
	cover.follow_camera_enabled = true
	cover.update_mode = GPUParticlesCollisionHeightField3D.UPDATE_MODE_WHEN_MOVED
	add_child(cover)
	apply_globals()

## Forecast: long dry spells, a couple of rainy periods a day, drizzle around them.
func forecast(t: float) -> Vector2:
	var a := sin(t / 190.0 + 1.3) * 0.6 + sin(t / 71.0 + float(day) * 2.1) * 0.4
	var cloud := clampf(0.5 + a * 0.9, 0.0, 1.0)
	var wet := smoothstep(0.62, 0.9, cloud)
	return Vector2(wet, cloud)

func set_time(hour: float) -> void:
	if last_hour >= 0.0 and hour < last_hour - 12.0: day += 1
	last_hour = hour
	minutes = day * 1440.0 + hour * 60.0

func describe() -> String:
	var state := "Clear"
	if rain > 0.55: state = "Rain"
	elif rain > 0.12: state = "Drizzle"
	elif overcast > 0.55: state = "Overcast"
	elif wetness > 0.25: state = "Wet roads"
	var temperature := 11 + int(round(5.0 * sin((last_hour - 9.0) / 24.0 * TAU) - rain * 3.0))
	return "%s  %d°C" % [state, temperature]

func _process(delta: float) -> void:
	var target := forecast(minutes)
	if forced >= 0.0:
		# Forced weather (tests, captures) applies at once.
		rain = forced
		overcast = maxf(forced, 0.25) if forced > 0.0 else 0.0
		wetness = forced
		target = Vector2(rain, overcast)
	rain = move_toward(rain, target.x, delta * 0.05 if forced < 0.0 else 1.0)
	overcast = move_toward(overcast, maxf(target.y, rain), delta * 0.04 if forced < 0.0 else 1.0)
	# Surfaces soak quickly in rain and dry over ~20 minutes of game time afterwards.
	if rain > wetness: wetness = move_toward(wetness, rain, delta * (0.06 if forced < 0.0 else 1.0))
	else: wetness = move_toward(wetness, rain, delta * (0.008 if forced < 0.0 else 1.0))
	var camera := get_viewport().get_camera_3d()
	if camera != null:
		follow.global_position = camera.global_position + Vector3(camera.global_basis.z.x, 0, camera.global_basis.z.z) * -8.0
	drops.emitting = rain > 0.02
	drops.amount_ratio = clampf(rain, 0.05, 1.0)
	apply_globals()

func apply_globals() -> void:
	RenderingServer.global_shader_parameter_set("wetness", wetness)
	RenderingServer.global_shader_parameter_set("rain_intensity", rain)

## Darken the light and thicken the fog after the day/night cycle has set them.
func apply_light(sun: DirectionalLight3D, environment: Environment, sky: ShaderMaterial) -> void:
	sun.light_energy *= 1.0 - overcast * 0.65
	sun.shadow_opacity = 1.0 - overcast * 0.6
	environment.fog_density = 0.0007 + overcast * 0.0012 + rain * 0.0016
	environment.ambient_light_energy *= 1.0 - overcast * 0.15
	if sky != null: sky.set_shader_parameter("overcast", overcast)
