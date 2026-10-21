class_name IconStudio
extends SubViewport
## Renders product thumbnails for the store computers from the real game models: one off-screen
## studio (own world, soft light, transparent background), one product at a time, cached.
## request(id, callback) calls back with an ImageTexture when ready (also while paused).

const SIZE := 256
static var cache: Dictionary = {}

var _queue: Array[Array] = []      ## [id, callback]
var _busy := false
var _stage: Node3D
var _camera: Camera3D

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	size = Vector2i(SIZE, SIZE)
	own_world_3d = true
	transparent_bg = true
	render_target_update_mode = SubViewport.UPDATE_DISABLED
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_CLEAR_COLOR
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.76, 0.8)
	env.environment.ambient_light_energy = 0.9
	env.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation = Vector3(-0.7, 0.6, 0)
	key.light_energy = 1.6
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation = Vector3(-0.3, 2.6, 0)
	rim.light_energy = 0.7
	add_child(rim)
	_camera = Camera3D.new()
	_camera.fov = 30
	add_child(_camera)
	_stage = Node3D.new()
	add_child(_stage)

func request(id: String, callback: Callable) -> void:
	if cache.has(id):
		callback.call(cache[id])
		return
	_queue.append([id, callback])
	if not _busy: _next()

func _next() -> void:
	if _queue.is_empty():
		_busy = false
		return
	_busy = true
	var job: Array = _queue.pop_front()
	var id: String = job[0]
	if cache.has(id):
		(job[1] as Callable).call(cache[id])
		_next.call_deferred()
		return
	for c in _stage.get_children(): c.queue_free()
	var model := product_model(id)
	_stage.add_child(model)
	# Frame the model's bounds from a three-quarter front view.
	var box := AABB()
	var first := true
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		var g := mi as MeshInstance3D
		if not g.visible: continue
		var b := g.global_transform * g.get_aabb()
		box = b if first else box.merge(b)
		first = false
	var centre := box.get_center()
	var radius := maxf(box.size.length() * 0.5, 0.05)
	var dir := Vector3(0.75, 0.45, 1.0).normalized()
	_camera.position = centre + dir * radius / sin(deg_to_rad(_camera.fov * 0.5)) * 1.05
	_camera.look_at(centre)
	render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var tex := ImageTexture.create_from_image(get_texture().get_image())
	cache[id] = tex
	(job[1] as Callable).call(tex)
	_next()

## The model shown for a product (falls back to a simple shape).
static func product_model(id: String) -> Node3D:
	if id == "budget_phone" and ResourceLoader.exists("res://assets/gadgets/budget_phone.glb"):
		var phone: Node3D = (load("res://assets/gadgets/budget_phone.glb") as PackedScene).instantiate()
		phone.rotation = Vector3(0, -0.35, 0)
		return phone
	if id == "water_bottle" or id == "energy_bar":
		return supply_model(id)
	if ShopCatalog.is_vehicle(id):
		var v := CityAssets.create_player_vehicle(ShopCatalog.vehicle_asset(id))
		v.rotation.y = PI
		return v
	if ResourceLoader.exists("res://world/city_assets/%s.glb" % id) or id == "delivery_bag":
		return CityAssets.create(id, 400)
	return supply_model(id)

## Small procedural products: a water bottle, an energy bar, or a labelled box.
static func supply_model(id: String) -> Node3D:
	var root := Node3D.new()
	var m := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	if id == "water_bottle":
		var c := CylinderMesh.new()
		c.top_radius = 0.022
		c.bottom_radius = 0.033
		c.height = 0.21
		m.mesh = c
		mat.albedo_color = Color(0.55, 0.78, 0.95, 0.75)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.roughness = 0.1
		var cap := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.014
		cm.bottom_radius = 0.014
		cm.height = 0.02
		cap.mesh = cm
		var capm := StandardMaterial3D.new()
		capm.albedo_color = Color("1f6fb2")
		cap.material_override = capm
		cap.position.y = 0.115
		root.add_child(cap)
	elif id == "energy_bar":
		var b := BoxMesh.new()
		b.size = Vector3(0.13, 0.018, 0.04)
		m.mesh = b
		mat.albedo_color = Color("e08a2c")
		mat.roughness = 0.4
		mat.metallic = 0.3
	else:
		var b := BoxMesh.new()
		b.size = Vector3(0.2, 0.12, 0.15)
		m.mesh = b
		mat.albedo_color = Color("b98a5c")
	m.material_override = mat
	root.add_child(m)
	return root
