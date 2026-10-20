class_name CityAssets
extends RefCounted
## Cached Blender scenes, shared PBR surfaces and reusable articulated parts.
static var scenes: Dictionary = {}
static var surfaces: Dictionary = {}
const CAR_TYPES = ["sedan", "hatchback", "suv", "van", "pickup"]
const CAR_SIZES = [Vector3(1.9,1.46,4.8),Vector3(1.79,1.47,4.29),Vector3(1.97,1.73,4.73),Vector3(2.02,2.35,5.45),Vector3(2.02,1.88,5.45)]
const PAINTS = ["24495d", "853b30", "c6c8bd", "343d40", "b18c4e", "466452", "78858e", "ddddce"]
## Factory-like colours for traffic Jettas (multiplied onto the silver paint).
const TRAFFIC_PAINTS = ["ffffff", "1d2a44", "7a1515", "2a2c2e", "c9ccd1", "34515f", "5a6066", "e8e4da"]
static var traffic_serial := 0

## The player's sedan is the Jetta GLI (assets/vehicles/jetta_gli_2025, prepared by
## tools/prepare_jetta.py): 3 LODs, wheel/steer pivots, lamps driven by jetta.gd.
static func create_player_vehicle(asset: String) -> Node3D:
	if asset == "sedan":
		return load("res://assets/vehicles/jetta_gli_2025/jetta.tscn").instantiate()
	if VehicleCatalog.PLAYER.has(asset): return VehicleCatalog.create(VehicleCatalog.PLAYER[asset], 160)
	return create(asset,140)

static func create(asset: String, distance: float = 220) -> Node3D:
	if asset == "bicycle":
		var bicycle := HiggsfieldBicycle.create()
		prepare(bicycle, distance)
		return bicycle
	if asset=="citizen": return LivingAssets.citizen()
	if asset == "sedan":
		# Traffic sedans are Jettas in traffic mode (lightest LOD, shared materials), each in
		# the next colour of TRAFFIC_PAINTS.
		var sedan: Node3D = load("res://assets/vehicles/jetta_gli_2025/jetta.tscn").instantiate()
		sedan.traffic = true
		sedan.paint = Color(TRAFFIC_PAINTS[traffic_serial % TRAFFIC_PAINTS.size()])
		traffic_serial += 1
		return sedan
	if VehicleCatalog.PLAYER.has(asset):
		# Hatchback, SUV, van and pickup are the converted Sketchfab models (same in the showroom).
		return VehicleCatalog.create(VehicleCatalog.PLAYER[asset], distance)
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
