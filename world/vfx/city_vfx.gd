class_name CityVFX
extends Node3D
## Ambient city effects: park fountains, alley and kitchen steam, chimney smoke on the
## city-kit terraces, flocks of birds and night-time lamp halos. Everything is GPU
## particles or a single MultiMesh, culled by visibility range, and driven by set_time().

const FOUNTAIN_PARKS := [Vector3(-44, 0, -330), Vector3(44, 0, -330), Vector3(-44, 0, -470), Vector3(44, 0, -470),
	Vector3(-44, 0, -590), Vector3(44, 0, -590), Vector3(-64, 0, -145), Vector3(64, 0, -145)]
const FLOCKS := [[Vector3(-44, 22, -470), 18.0], [Vector3(0, 19, -120), 26.0], [Vector3(300, 46, -470), 40.0], [Vector3(44, 20, -330), 15.0]]
const BIRDS_PER_FLOCK := 14

var smoke: Array[GPUParticles3D] = []
var halos: Array[Transform3D] = []
var halo_node: MultiMeshInstance3D
var halo_material: ShaderMaterial
var birds: MultiMeshInstance3D
var bird_phase := 0.0
var soft_puff: GradientTexture2D
var droplet: GradientTexture2D

func _ready() -> void:
	soft_puff = radial_texture(Color(1, 1, 1, 0.55), Color(1, 1, 1, 0.0))
	droplet = radial_texture(Color(1, 1, 1, 1), Color(0.7, 0.85, 1.0, 0.0))
	# The putti fountains (CityMonuments): every park but the equestrian one, and Atatürk Square.
	for spot in CityMonuments.fountain_spots(): fountain(spot)
	# Steam from downtown alley manholes (every third building) and restaurant kitchen vents.
	for block in range(9):
		for b in DowntownCatalog.buildings(block):
			if b.program != "mixed" or b.id % 3 != 0: continue
			var rear: Vector3 = Transform3D(Basis(Vector3.UP, b.yaw), b.root) * Vector3(0, 0.08, -b.depth - 2.5)
			add_child(plume(rear, 0.9, 5.0, Color(0.92, 0.93, 0.95), 140.0))
	for pickup in CityCatalog.PICKUPS.slice(0, 3):
		add_child(plume(pickup + Vector3(-6, 3.6, -6.5), 0.6, 3.5, Color(0.95, 0.95, 0.95), 120.0))
	# Chimney smoke on a few terrace stacks; thicker in the cold morning and evening.
	var stacks: Array = KitBuilder.chimney_tops
	for i in range(0, stacks.size(), 4):
		var p := plume(stacks[i], 1.3, 8.0, Color(0.82, 0.82, 0.84), 260.0)
		smoke.append(p)
		add_child(p)
	build_birds()
	# Night glow around every lamp the world created (street, porch and downtown).
	var world := get_parent()
	if world is CedarNeighborhood:
		for lamp in world.lamps: halo(lamp.position, 0.9)
		if world.downtown != null:
			for lamp in world.downtown.lights: halo(world.downtown.to_global(lamp.position) - world.global_position, 1.1)
	build_halos()

func radial_texture(inner: Color, outer: Color) -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.set_color(0, inner)
	gradient.set_color(1, outer)
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(1.0, 0.5)
	texture.width = 64
	texture.height = 64
	return texture

func billboard_material(texture: Texture2D, tint: Color, additive: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if additive else BaseMaterial3D.BLEND_MODE_MIX
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED if additive else BaseMaterial3D.SHADING_MODE_PER_PIXEL
	m.albedo_texture = texture
	m.albedo_color = tint
	m.vertex_color_use_as_albedo = true
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.disable_receive_shadows = true
	return m

func fountain(at: Vector3) -> void:
	# The putti fountain (assets/monuments/fountain_putti.glb): water bubbles up from the top of
	# the reed column (2.95 m) and spills in arcs down over the putti into the basin (r ~1.5 m).
	var jet := GPUParticles3D.new()
	jet.amount = 220
	jet.lifetime = 1.0
	jet.preprocess = 2.0
	jet.position = at + Vector3(0, 2.95, 0)
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3.UP
	process.spread = 38.0
	process.initial_velocity_min = 1.5
	process.initial_velocity_max = 2.2
	process.gravity = Vector3(0, -9.8, 0)
	process.scale_min = 0.6
	process.scale_max = 1.2
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0.9))
	fade.set_color(1, Color(1, 1, 1, 0.0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = fade
	process.color_ramp = ramp
	jet.process_material = process
	var quad := QuadMesh.new()
	quad.size = Vector2(0.13, 0.13)
	quad.material = billboard_material(droplet, Color(0.85, 0.93, 1.0, 0.85))
	jet.draw_pass_1 = quad
	jet.visibility_range_end = 70.0
	jet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	jet.visibility_aabb = AABB(Vector3(-2, -3.2, -2), Vector3(4, 4.4, 4))
	add_child(jet)
	# Splash mist where the water lands.
	var mist := plume(at + Vector3(0, 0.25, 0), 0.5, 1.2, Color(0.95, 0.97, 1.0), 60.0)
	(mist.process_material as ParticleProcessMaterial).emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	(mist.process_material as ParticleProcessMaterial).emission_ring_radius = 1.1
	(mist.process_material as ParticleProcessMaterial).emission_ring_inner_radius = 0.7
	(mist.process_material as ParticleProcessMaterial).emission_ring_height = 0.05
	(mist.process_material as ParticleProcessMaterial).emission_ring_axis = Vector3.UP
	add_child(mist)

## Rising, expanding, fading puffs (steam, smoke, mist).
func plume(at: Vector3, size: float, rise: float, tint: Color, range_end: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 18
	p.lifetime = rise
	p.preprocess = rise
	p.position = at
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3.UP
	process.spread = 12.0
	process.initial_velocity_min = 0.35
	process.initial_velocity_max = 0.65
	process.gravity = Vector3(0.25, 0.12, 0.08) # light breeze from the west
	process.damping_min = 0.05
	process.damping_max = 0.1
	process.angle_min = -180.0
	process.angle_max = 180.0
	var grow := Curve.new()
	grow.add_point(Vector2(0, 0.35))
	grow.add_point(Vector2(1, 1.6))
	var grow_texture := CurveTexture.new()
	grow_texture.curve = grow
	process.scale_curve = grow_texture
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0.0))
	fade.add_point(0.15, Color(1, 1, 1, 0.5))
	fade.set_color(fade.get_point_count() - 1, Color(1, 1, 1, 0.0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = fade
	process.color_ramp = ramp
	p.process_material = process
	var quad := QuadMesh.new()
	quad.size = Vector2(size, size)
	quad.material = billboard_material(soft_puff, tint)
	p.draw_pass_1 = quad
	p.visibility_range_end = range_end
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-3, -0.5, -3), Vector3(6, rise * 1.2 + 2, 6))
	return p

func build_birds() -> void:
	# Low-poly bird: body and two wings; the shader flaps the wings per instance.
	var mesh := ArrayMesh.new()
	var v := PackedVector3Array([Vector3(0, 0, -0.16), Vector3(0.03, 0, 0.1), Vector3(-0.03, 0, 0.1),
		Vector3(0, 0, -0.05), Vector3(0.32, 0, 0.02), Vector3(0, 0, 0.07),
		Vector3(0, 0, -0.05), Vector3(0, 0, 0.07), Vector3(-0.32, 0, 0.02)])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = v
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode cull_disabled;
uniform vec4 colour : source_color = vec4(0.12, 0.12, 0.13, 1.0);
void vertex() {
	float span = abs(VERTEX.x);
	float flap = sin(TIME * 11.0 + float(INSTANCE_ID) * 1.7);
	VERTEX.y += span * span * 4.5 * flap;
}
void fragment() { ALBEDO = colour.rgb; ROUGHNESS = 0.9; }
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	mesh.surface_set_material(0, material)
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = mesh
	multi.instance_count = FLOCKS.size() * BIRDS_PER_FLOCK
	birds = MultiMeshInstance3D.new()
	birds.multimesh = multi
	birds.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	birds.extra_cull_margin = 120.0
	add_child(birds)
	update_birds(0.0)

func update_birds(delta: float) -> void:
	bird_phase += delta
	var multi := birds.multimesh
	for f in range(FLOCKS.size()):
		var centre: Vector3 = FLOCKS[f][0]
		var radius: float = FLOCKS[f][1]
		for i in range(BIRDS_PER_FLOCK):
			var k := f * BIRDS_PER_FLOCK + i
			var speed := 0.32 + 0.05 * sin(float(k) * 2.3)
			var a := bird_phase * speed + float(i) * 0.37 + float(f)
			var wobble := Vector3(sin(a * 2.1 + i) * 2.5, sin(a * 1.3 + i * 0.7) * 2.0, cos(a * 1.7 + i) * 2.5)
			var p := centre + Vector3(cos(a) * radius, 0, sin(a) * radius) + wobble
			var ahead := centre + Vector3(cos(a + 0.05) * radius, 0, sin(a + 0.05) * radius) + wobble
			var facing := Basis.looking_at(ahead - p, Vector3.UP).scaled(Vector3.ONE * 1.3)
			multi.set_instance_transform(k, Transform3D(facing, p))

## Lamp halo for night glow: positions are collected, then drawn as one billboarded MultiMesh.
func halo(at: Vector3, size: float = 1.0) -> void:
	halos.append(Transform3D(Basis.from_scale(Vector3.ONE * size), at))

func build_halos() -> void:
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;
uniform float glow = 0.0;
uniform sampler2D puff : source_color;
void vertex() {
	// Camera-facing quad around each instance origin, keeping the instance scale.
	float scale = length(MODEL_MATRIX[0].xyz);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * scale, INV_VIEW_MATRIX[1] * scale, INV_VIEW_MATRIX[2] * scale, MODEL_MATRIX[3]);
}
void fragment() {
	vec4 t = texture(puff, UV);
	ALBEDO = vec3(1.0, 0.8, 0.52) * t.a * glow;
}
"""
	halo_material = ShaderMaterial.new()
	halo_material.shader = shader
	halo_material.set_shader_parameter("puff", soft_puff)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	quad.material = halo_material
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = quad
	multi.instance_count = halos.size()
	for i in range(halos.size()): multi.set_instance_transform(i, halos[i])
	halo_node = MultiMeshInstance3D.new()
	halo_node.multimesh = multi
	halo_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	halo_node.visible = false
	add_child(halo_node)
func set_time(hour: float, daylight: float) -> void:
	var night := 1.0 - daylight
	if halo_node != null:
		halo_node.visible = night > 0.05
		halo_material.set_shader_parameter("glow", night * 0.45)
	# Chimneys draw in the morning and evening.
	var cold := clampf(1.0 - absf(hour - 13.0) / 6.0, 0.0, 1.0)
	for s in smoke: s.amount_ratio = lerpf(1.0, 0.35, cold)

func _process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null: return
	# Birds only need updating when a flock could be on screen.
	update_birds(delta)
