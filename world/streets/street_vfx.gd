class_name StreetVFX
extends Node3D
## Street effects for the busier traffic (all cheap, pooled and range-limited):
##   * exhaust puffs: a pool of one-shot GPU emitters handed to cars near the camera as they pull
##     away from a stop (red light, queue, junction),
##   * brake and tail lights: one MultiMesh of glow sprites at the rear corners of nearby
##     vehicles, bright while braking or held at a stop, dim tail lights after dark,
##   * charcoal grill smoke from the rooftop extraction of the corridor grill restaurants
##     (kebab, köfte, kokoreç, fish, İskender, döner, meyhane),
##   * tyre spray on wet roads: a pool of emitters following the nearest fast vehicles while
##     WeatherSystem.wetness is up.
## Particles share their process materials and draw meshes; nothing is allocated per frame.

const EXHAUST_POOL := 16
const SPRAY_POOL := 8
const LIGHT_RANGE := 90.0
const EXHAUST_RANGE := 60.0
const SPRAY_RANGE := 50.0
const GRILLS := ["mangal_doner", "mangal", "kokorec", "fish", "iskender", "doner", "tavern"]

var cars: Array[Dictionary] = []
var exhaust: Array[GPUParticles3D] = []
var exhaust_next := 0
var spray: Array[GPUParticles3D] = []
var spray_car: Array = []
var lights: MultiMeshInstance3D
var light_material: ShaderMaterial
var grills: Array[GPUParticles3D] = []
var weather: Node
var night := 0.0
var _scan := 0.0
var _launch: Dictionary = {}   # body id -> was stopped
var puff: GradientTexture2D

func _ready() -> void:
	puff = radial(Color(1, 1, 1, 0.6), Color(1, 1, 1, 0.0))
	weather = get_parent().get_node_or_null("Weather")
	build_exhaust()
	build_spray()
	build_lights()
	build_grills()
	collect.call_deferred()

## Every AI vehicle list in the city (CityTraffic, downtown traffic and the civic fleet).
func collect() -> void:
	cars.clear()
	var traffic := get_parent().get_node_or_null("CityTraffic")
	if traffic != null: for c: Dictionary in traffic.get("drivers"): cars.append(c)
	var downtown: Variant = get_parent().get("downtown")
	if downtown != null and (downtown as Node).get("population") != null:
		var fleet := ((downtown as Node).get("population") as Node).get_node_or_null("CivicFleet")
		if fleet != null:
			for c: Dictionary in fleet.get("drivers"): cars.append(c)
			for c: Dictionary in fleet.get("fleet"): cars.append(c)
	lights.multimesh.instance_count = cars.size() * 2
	lights.multimesh.visible_instance_count = 0

func set_time(_hour: float, daylight: float) -> void:
	night = 1.0 - daylight
	light_material.set_shader_parameter("strength", lerpf(0.9, 1.6, night))

func radial(inner: Color, outer: Color) -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, inner)
	g.set_color(1, outer)
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 64
	t.height = 64
	return t

func sprite(tint: Color, size: float, texture: Texture2D = null) -> QuadMesh:
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	m.albedo_texture = texture if texture != null else puff
	m.albedo_color = tint
	m.vertex_color_use_as_albedo = true
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.disable_receive_shadows = true
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	q.material = m
	return q

func fade_ramp(peak: float) -> GradientTexture1D:
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0.0))
	fade.add_point(0.12, Color(1, 1, 1, peak))
	fade.set_color(fade.get_point_count() - 1, Color(1, 1, 1, 0.0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = fade
	return ramp

func grow_curve(a: float, b: float) -> CurveTexture:
	var c := Curve.new()
	c.add_point(Vector2(0, a))
	c.add_point(Vector2(1, b))
	var t := CurveTexture.new()
	t.curve = c
	return t

# ----------------------------------------------------------------------------- exhaust

func build_exhaust() -> void:
	var process := ParticleProcessMaterial.new()
	# The rain's roof heightfield (WeatherSystem) must not catch these particles.
	process.collision_mode = ParticleProcessMaterial.COLLISION_DISABLED
	process.direction = Vector3(0, 0.35, 1)   # out of the tailpipe (vehicle +Z is the rear)
	process.spread = 18.0
	process.initial_velocity_min = 0.6
	process.initial_velocity_max = 1.3
	process.gravity = Vector3(0, 0.25, 0)
	process.damping_min = 0.6
	process.damping_max = 1.0
	process.angle_min = -180.0
	process.angle_max = 180.0
	process.scale_curve = grow_curve(0.35, 2.4)
	process.color_ramp = fade_ramp(0.75)
	var mesh := sprite(Color(0.46, 0.46, 0.48, 0.9), 0.6)
	for i in range(EXHAUST_POOL):
		var p := GPUParticles3D.new()
		p.name = "Exhaust%d" % i
		p.amount = 14
		p.lifetime = 1.8
		p.one_shot = true
		p.explosiveness = 0.25
		p.local_coords = false
		p.emitting = false
		p.process_material = process
		p.draw_pass_1 = mesh
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.visibility_aabb = AABB(Vector3(-3, -1, -3), Vector3(6, 4, 6))
		p.visibility_range_end = EXHAUST_RANGE
		add_child(p)
		exhaust.append(p)

## A puff from the tailpipe of `car` (pulling away).
func puff_from(car: Dictionary) -> void:
	var body: Node3D = car.body
	var size: Vector3 = car.size
	var p := exhaust[exhaust_next]
	exhaust_next = (exhaust_next + 1) % exhaust.size()
	p.global_transform = body.global_transform * Transform3D(Basis.IDENTITY, Vector3(size.x * 0.28, 0.32, float(car.half) - 0.05))
	p.restart()

# ----------------------------------------------------------------------------- tyre spray

func build_spray() -> void:
	var process := ParticleProcessMaterial.new()
	# The rain's roof heightfield (WeatherSystem) must not catch these particles.
	process.collision_mode = ParticleProcessMaterial.COLLISION_DISABLED
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	process.emission_box_extents = Vector3(0.8, 0.05, 0.1)
	process.direction = Vector3(0, 0.6, 1)
	process.spread = 25.0
	process.initial_velocity_min = 1.5
	process.initial_velocity_max = 3.2
	process.gravity = Vector3(0, -6.0, 0)
	process.damping_min = 1.5
	process.damping_max = 2.5
	process.scale_curve = grow_curve(0.5, 2.0)
	process.color_ramp = fade_ramp(0.55)
	var mesh := sprite(Color(0.92, 0.94, 0.97, 0.7), 0.7)
	for i in range(SPRAY_POOL):
		var p := GPUParticles3D.new()
		p.name = "Spray%d" % i
		p.amount = 70
		p.lifetime = 0.8
		p.local_coords = false
		p.emitting = false
		p.process_material = process
		p.draw_pass_1 = mesh
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.visibility_aabb = AABB(Vector3(-4, -1, -4), Vector3(8, 3, 8))
		p.visibility_range_end = SPRAY_RANGE + 10.0
		add_child(p)
		spray.append(p)
		spray_car.append(null)

# ----------------------------------------------------------------------------- lights

func build_lights() -> void:
	light_material = ShaderMaterial.new()
	light_material.shader = preload("res://world/streets/signal_glow.gdshader")
	light_material.set_shader_parameter("strength", 0.9)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.use_custom_data = true
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	mm.mesh = quad
	lights = MultiMeshInstance3D.new()
	lights.name = "BrakeLights"
	lights.multimesh = mm
	lights.material_override = light_material
	lights.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Instances follow the cars anywhere in the city: never cull the batch by its AABB.
	lights.custom_aabb = AABB(Vector3(-2000, -50, -2000), Vector3(4000, 200, 4000))
	add_child(lights)

# ----------------------------------------------------------------------------- grill smoke

func build_grills() -> void:
	var process := ParticleProcessMaterial.new()
	# The rain's roof heightfield (WeatherSystem) must not catch these particles.
	process.collision_mode = ParticleProcessMaterial.COLLISION_DISABLED
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	process.emission_box_extents = Vector3(0.25, 0.05, 0.25)
	process.direction = Vector3.UP
	process.spread = 10.0
	process.initial_velocity_min = 0.9
	process.initial_velocity_max = 1.4
	process.gravity = Vector3(0.35, 0.15, 0.1)
	process.damping_min = 0.1
	process.damping_max = 0.2
	process.angle_min = -180.0
	process.angle_max = 180.0
	process.scale_curve = grow_curve(0.5, 3.0)
	process.color_ramp = fade_ramp(0.9)
	# Charcoal smoke: a denser puff, grey-brown, so it reads against the sky and the roofs.
	var mesh := sprite(Color(0.36, 0.34, 0.33, 1.0), 1.6, radial(Color(1, 1, 1, 0.95), Color(1, 1, 1, 0.0)))
	var k := 3
	for b in RestaurantCatalog.corridor_buildings():
		var r: Array = RestaurantCatalog.LIST[k]
		k += 1
		if not (String(r[4]) in GRILLS): continue
		var top := 4.2 + (int(b.get("floors", 4)) - 1) * 3.2
		var frame := RestaurantCatalog.frame(b)
		var at := frame * Vector3(RestaurantCatalog.centre_x(b) - 2.0, top + 1.2, -3.0)
		var p := GPUParticles3D.new()
		p.name = "GrillSmoke_%s" % r[0]
		p.amount = 40
		p.lifetime = 5.5
		p.preprocess = 5.0
		p.position = at
		p.process_material = process
		p.draw_pass_1 = mesh
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.visibility_aabb = AABB(Vector3(-4, -1, -4), Vector3(8, 9, 8))
		p.visibility_range_end = 180.0
		add_child(p)
		grills.append(p)

## Once physics is up: sit each grill vent on the actual roof below it.
func _physics_process(_delta: float) -> void:
	set_physics_process(false)
	var space := get_world_3d().direct_space_state
	for p in grills:
		var top := p.position + Vector3.UP * 60.0
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(top, Vector3(p.position.x, 0.5, p.position.z), 1))
		if not hit.is_empty(): p.position.y = (hit.position as Vector3).y + 1.4

# ----------------------------------------------------------------------------- update

func _process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null or cars.is_empty(): return
	var eye := camera.global_position
	var wet := float(weather.get("wetness")) if weather != null else 0.0
	var mm := lights.multimesh
	var n := 0
	for car in cars:
		var body: Node3D = car.body
		if not body.visible: continue
		var d := body.global_position.distance_to(eye)
		var id := body.get_instance_id()
		var v: float = car.speed
		# Exhaust: pulling away from a standstill.
		if d < EXHAUST_RANGE:
			var stopped: bool = _launch.get(id, false)
			if v < 0.3: _launch[id] = true
			elif stopped and float(car.get("accel", 0.0)) > 0.5:
				_launch[id] = false
				puff_from(car)
		if d > LIGHT_RANGE: continue
		var braking: bool = car.get("braking", false)
		var level := 1.0 if braking or v < 0.3 else 0.3 * night
		if level <= 0.01: continue
		var size: Vector3 = car.size
		var xf := body.global_transform
		for k in range(2):
			var side := -1.0 if k == 0 else 1.0
			var at := xf * Vector3(side * (size.x * 0.5 - 0.18), clampf(size.y * 0.55, 0.75, 1.25), float(car.half) + 0.02)
			mm.set_instance_transform(n, Transform3D(xf.basis.scaled(Vector3.ONE * 0.5), at))
			mm.set_instance_color(n, Color(1.0, 0.08, 0.04))
			mm.set_instance_custom_data(n, Color(level, 0, 0, 0))
			n += 1
	mm.visible_instance_count = n
	# Tyre spray on wet roads, re-assigned to the nearest fast vehicles a few times a second.
	_scan -= delta
	if _scan <= 0.0:
		_scan = 0.3
		var picks: Array = []
		if wet > 0.2:
			for car in cars:
				var body: Node3D = car.body
				if not body.visible or float(car.speed) < 4.0: continue
				var d := body.global_position.distance_to(eye)
				if d < SPRAY_RANGE: picks.append([d, car])
			picks.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
		for i in range(spray.size()):
			spray_car[i] = picks[i][1] if i < picks.size() else null
			spray[i].emitting = spray_car[i] != null
			if spray_car[i] != null: spray[i].amount_ratio = clampf(wet, 0.3, 1.0)
	for i in range(spray.size()):
		var car: Variant = spray_car[i]
		if car == null: continue
		var c: Dictionary = car
		var body: Node3D = c.body
		spray[i].global_transform = body.global_transform * Transform3D(Basis.IDENTITY, Vector3(0, 0.1, float(c.half) - 0.6))
