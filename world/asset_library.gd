class_name CityAssets
extends RefCounted
## Cached Blender scenes, shared PBR surfaces and reusable articulated parts.
static var scenes: Dictionary = {}
static var surfaces: Dictionary = {}
const CAR_TYPES = ["sedan", "hatchback", "suv", "van", "pickup", "ace11"]
const CAR_SIZES = [Vector3(1.9,1.46,4.8),Vector3(1.79,1.47,4.29),Vector3(1.97,1.73,4.73),Vector3(2.02,2.35,5.45),Vector3(2.02,1.88,5.45),Vector3(1.76,1.45,3.73)]
const PAINTS = ["24495d", "853b30", "c6c8bd", "343d40", "b18c4e", "466452", "78858e", "ddddce"]
## Factory-like colours for traffic Jettas (multiplied onto the silver paint).
const TRAFFIC_PAINTS = ["ffffff", "1d2a44", "7a1515", "2a2c2e", "c9ccd1", "34515f", "5a6066", "e8e4da"]
static var traffic_serial := 0
const GRAY_BICYCLE := "res://assets/bicycles/gray_bicycle.glb"
const GRAY_BICYCLE_RIDER := "res://assets/bicycles/gray_bicycle_rider.glb"

## The player's sedan is the Jetta GLI (assets/vehicles/jetta_gli_2025, prepared by
## tools/prepare_jetta.py): 3 LODs, wheel/steer pivots, lamps driven by jetta.gd.
static func create_player_vehicle(asset: String) -> Node3D:
	if asset == "sedan":
		return load("res://assets/vehicles/jetta_gli_2025/jetta.tscn").instantiate()
	if VehicleCatalog.PLAYER.has(asset): return VehicleCatalog.create(VehicleCatalog.PLAYER[asset], 160, "")
	return create(asset,140)

static func create(asset: String, distance: float = 220) -> Node3D:
	if asset == "bicycle":
		# The gray city bike extracted from the supplied rider model (tools/build_gray_bicycle.py):
		# faces -Z, SteeringPivot on the head-tube axis (local +Y) holding the fork, bars and
		# WheelFront; WheelFront/WheelRear spin about local X. (The old Higgsfield bike in
		# world/higgsfield/ is kept on disk but no longer used.)
		if not scenes.has(GRAY_BICYCLE): scenes[GRAY_BICYCLE] = load(GRAY_BICYCLE)
		var bicycle: Node3D = scenes[GRAY_BICYCLE].instantiate()
		bicycle.name = "GrayBicycle"
		bicycle.set_meta("wheelbase", 1.1015)
		bicycle.set_meta("wheel_radius", 0.35)
		bicycle.set_meta("asset_source", "woman_riding_a_gray_bicycle.glb (rider removed)")
		prepare(bicycle, distance)
		return bicycle
	if asset == "bicycle_rider":
		# The supplied model's rider, posed to sit exactly on the gray bicycle's saddle/bars/pedals.
		if not scenes.has(GRAY_BICYCLE_RIDER): scenes[GRAY_BICYCLE_RIDER] = load(GRAY_BICYCLE_RIDER)
		var rider: Node3D = scenes[GRAY_BICYCLE_RIDER].instantiate()
		prepare(rider, distance)
		return rider
	if asset=="citizen": return LivingAssets.citizen()
	if asset == "delivery_bag" and ResourceLoader.exists("res://assets/delivery/delivery_bag.glb"):
		# The Blender-made insulated courier bag (shop display and on the bike's rear rack).
		var bag: Node3D = load("res://assets/delivery/delivery_bag.glb").instantiate()
		prepare(bag, distance)
		return bag
	if asset == "sedan":
		# Traffic sedans are Jettas in traffic mode (lightest LOD, shared materials), each in
		# the next colour of TRAFFIC_PAINTS.
		var sedan: Node3D = load("res://assets/vehicles/jetta_gli_2025/jetta.tscn").instantiate()
		sedan.traffic = true
		sedan.paint = Color(TRAFFIC_PAINTS[traffic_serial % TRAFFIC_PAINTS.size()])
		traffic_serial += 1
		return sedan
	if VehicleCatalog.PLAYER.has(asset):
		# Hatchback, SUV, van, pickup and Ace 11 are the converted Sketchfab models in their
		# factory finish, so the showroom car is the car the player buys.
		return VehicleCatalog.create(VehicleCatalog.PLAYER[asset], distance, "")
	if asset in CAR_TYPES:
		var replacement: String=["executive_sedan","compact_sport","urban_crossover","cargo_van","utility_pickup"][CAR_TYPES.find(asset)]
		var vehicle := LivingAssets.scene(replacement)
		prepare(vehicle,distance)
		return vehicle
	if not scenes.has(asset): scenes[asset] = load("res://world/city_assets/%s.glb" % asset)
	var model: Node3D = scenes[asset].instantiate()
	prepare(model, distance)
	return model

static func prepare(node: Node, distance: float) -> void:
	if node is GeometryInstance3D:
		node.visibility_range_end = distance
		node.visibility_range_end_margin = 12
	if node is MeshInstance3D:
		var label := str(node.name)
		if label == "Foliage": node.material_override = vegetation()
		elif label in ["OiledOak", "TreeBark", "WarmBrick"]:
			node.material_override = pbr({"OiledOak": "synthetic_wood", "TreeBark": "bark_brown_01", "WarmBrick": "brick_wall_11"}[label], 0.25 if label == "WarmBrick" else 0.7)
		elif label == "ArchitecturalConcrete": node.material_override = CityMaterials.get_surface("737773")
	for child in node.get_children(): prepare(child, distance)

static func vegetation() -> ShaderMaterial:
	if not surfaces.has("foliage"):
		var surface := ShaderMaterial.new()
		surface.shader = preload("res://world/foliage.gdshader")
		surfaces.foliage = surface
	return surfaces.foliage

static func pbr(asset: String, scale_factor: float = 1.0) -> StandardMaterial3D:
	var key := "pbr_%s_%s" % [asset, scale_factor]
	if not surfaces.has(key):
		var surface := StandardMaterial3D.new()
		var base := "res://world/city_assets/textures/%s_" % asset
		surface.albedo_texture = load(base + "Diffuse.jpg")
		surface.normal_enabled = true
		surface.normal_texture = load(base + "nor_gl.jpg")
		surface.normal_scale = 0.35
		surface.roughness_texture = load(base + "Rough.jpg")
		surface.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		surface.uv1_triplanar = true
		surface.uv1_world_triplanar = true
		surface.uv1_triplanar_sharpness = 16
		surface.uv1_scale = Vector3.ONE * scale_factor
		surface.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		surfaces[key] = surface
	return surfaces[key]

static func tint(node: Node, starts: String, color: Color, metallic: float = 0, roughness: float = 0.75) -> void:
	# Legacy "Skin" name matching must not paint the entire new SkinnedBody mesh.
	if node is LivingCitizen: return
	var key := "%s_%s" % [starts, color.to_html()]
	if not surfaces.has(key):
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.metallic = metallic
		material.roughness = roughness
		if metallic > 0.4:
			material.clearcoat_enabled = true
			material.clearcoat = 0.5
			material.clearcoat_roughness = 0.18
		surfaces[key] = material
	if node is MeshInstance3D and str(node.name).contains(starts): node.material_override = surfaces[key]
	for child in node.get_children(): tint(child, starts, color, metallic, roughness)

static func wheel_nodes(model: Node) -> Array[Node3D]:
	var wheels: Array[Node3D] = []
	for child in model.find_children("Wheel*", "Node3D", true, false):
		if child is Node3D and not child is MeshInstance3D: wheels.append(child)
	return wheels
