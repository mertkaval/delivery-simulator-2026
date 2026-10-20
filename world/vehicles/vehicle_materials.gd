class_name VehicleMaterials
## Game-side material table for the production vehicle GLBs (G6).
## The glTF surfaces carry stable material names (VehiclePaint, Glass, Chrome, ...); the game
## replaces them at load with these StandardMaterial3Ds, tuned for the CedarNeighborhood rig
## (Forward+, sky-only reflections, AgX). Captures: tests/capture_materials.gd; study:
## world/vehicles/production/reports/g6_materials.md.
## Integration (not done here): CityAssets loads the GLB -> VehicleMaterials.apply(model), then
## CityAssets.tint recolours VehiclePaint; CedarNeighborhood.set_time -> VehicleMaterials.set_night.

const NAMES: Array[String] = ["VehiclePaint", "Glass", "BlackTrim", "Chrome", "Alloy", "RimWell",
	"Rubber", "RubberCut", "SteelDisc", "CaliperDark", "HeadLamp", "TailLamp", "Interior", "Seat",
	"ArchLiner", "Plate"]

## Lamp emission (energy multiplier) at full day and full night; see set_night().
const LAMP_DAY := {"HeadLamp": 0.2, "TailLamp": 0.3}
const LAMP_NIGHT := {"HeadLamp": 1.4, "TailLamp": 1.0}
## Dry roughness of the surfaces that darken and sharpen in rain (see set_wet()).
const WET_SURFACES := {"VehiclePaint": 0.32, "BlackTrim": 0.42, "Rubber": 0.74, "Plate": 0.35, "Alloy": 0.42, "RimWell": 0.6, "CaliperDark": 0.55}

static var materials: Dictionary = {}
static var flake_normal: NoiseTexture2D
static var weave_normal: NoiseTexture2D

## Material for a glTF surface name (accepts Blender's ".001" and Godot's "_001" suffixes).
static func material(surface_name: String) -> Material:
	var key := surface_name.get_slice(".", 0)
	if key.length() > 4 and key[-4] == "_" and key.right(3).is_valid_int(): key = key.left(-4)
	if materials.has(key): return materials[key]
	var result: StandardMaterial3D = build(key)
	if result == null: return null
	result.resource_name = key
	materials[key] = result
	return result

static func has(surface_name: String) -> bool:
	return material(surface_name) != null

## Walks MeshInstance3D children and overrides each surface whose glTF material name is known.
static func apply(node: Node) -> void:
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		var mesh: Mesh = mesh_instance.mesh
		if mesh != null:
			for surface in range(mesh.get_surface_count()):
				var source: Material = mesh.surface_get_material(surface)
				if source == null: continue
				var replacement: Material = material(source.resource_name)
				if replacement != null: mesh_instance.set_surface_override_material(surface, replacement)
	for child in node.get_children(): apply(child)

## Night 0 (day) .. 1 (night): lamp emission that reads at night without blowing out by day.
static func set_night(amount: float) -> void:
	for lamp in LAMP_DAY.keys():
		if materials.has(lamp):
			var lamp_material: StandardMaterial3D = materials[lamp]
			lamp_material.emission_energy_multiplier = lerpf(LAMP_DAY[lamp], LAMP_NIGHT[lamp], clampf(amount, 0.0, 1.0))

## Wetness 0..1 (WeatherSystem.wetness): rain water films lower the roughness of exposed surfaces.
static func set_wet(amount: float) -> void:
	for key in WET_SURFACES.keys():
		if materials.has(key):
			var dry: float = WET_SURFACES[key]
			(materials[key] as StandardMaterial3D).roughness = lerpf(dry, dry * 0.35, clampf(amount, 0.0, 1.0))

static func base(albedo: String, roughness: float, metallic: float, specular: float = 0.5) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(albedo)
	m.roughness = roughness
	m.metallic = metallic
	m.metallic_specular = specular
	return m

## Tiny high-frequency normal noise: metallic flake under the paint clearcoat.
static func flakes() -> NoiseTexture2D:
	if flake_normal == null:
		var noise := FastNoiseLite.new()
		noise.seed = 2026
		noise.noise_type = FastNoiseLite.TYPE_CELLULAR
		noise.frequency = 0.9
		noise.cellular_return_type = FastNoiseLite.RETURN_CELL_VALUE
		flake_normal = NoiseTexture2D.new()
		flake_normal.width = 256
		flake_normal.height = 256
		flake_normal.seamless = true
		flake_normal.as_normal_map = true
		flake_normal.bump_strength = 2.0
		flake_normal.noise = noise
	return flake_normal

## Soft low-frequency normal noise: fabric weave / grain for seats and trim.
static func weave() -> NoiseTexture2D:
	if weave_normal == null:
		var noise := FastNoiseLite.new()
		noise.seed = 77
		noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		noise.frequency = 0.08
		noise.fractal_octaves = 4
		weave_normal = NoiseTexture2D.new()
		weave_normal.width = 256
		weave_normal.height = 256
		weave_normal.seamless = true
		weave_normal.as_normal_map = true
		weave_normal.bump_strength = 4.0
		weave_normal.noise = noise
	return weave_normal

static func build(key: String) -> StandardMaterial3D:
	var m: StandardMaterial3D
	match key:
		"VehiclePaint":
			# Metallic silver base; CityAssets.tint multiplies the albedo per instance, so keep it light.
			m = base("d6d8db", 0.32, 0.75, 0.6)
			m.clearcoat_enabled = true
			m.clearcoat = 1.0
			m.clearcoat_roughness = 0.1
			m.normal_enabled = true
			m.normal_texture = flakes()
			m.normal_scale = 0.12
			m.uv1_scale = Vector3(60, 60, 60)
		"Glass":
			# Single-sided shell, back faces culled (see g6_materials.md for the reasoning).
			m = base("22323a", 0.05, 0.0, 0.8)
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
			m.albedo_color = Color(Color("22323a"), 0.32)
			m.cull_mode = BaseMaterial3D.CULL_BACK
			m.clearcoat_enabled = true
			m.clearcoat = 0.6
			m.clearcoat_roughness = 0.03
		"BlackTrim":
			m = base("1a1b1d", 0.42, 0.0, 0.5)
		"Chrome":
			m = base("e0e0e0", 0.15, 1.0, 0.5)
		"Alloy":
			m = base("b9bbbe", 0.42, 0.7, 0.5)
			m.clearcoat_enabled = true
			m.clearcoat = 0.6
			m.clearcoat_roughness = 0.12
		"RimWell":
			m = base("4a4a4d", 0.6, 0.7, 0.5)
		"Rubber":
			m = base("242426", 0.74, 0.0, 0.42)
		"RubberCut":
			m = base("0d0d0d", 1.0, 0.0, 0.3)
		"SteelDisc":
			m = base("8e8c89", 0.55, 0.9, 0.5)
			m.anisotropy_enabled = true
			m.anisotropy = 0.55
		"CaliperDark":
			m = base("6a6a6c", 0.55, 0.3, 0.5)
		"HeadLamp":
			# Lens and reflector in one slot: glossy clearcoat over a warm emissive body.
			m = base("f4f1e6", 0.08, 0.0, 0.7)
			m.clearcoat_enabled = true
			m.clearcoat = 1.0
			m.clearcoat_roughness = 0.02
			m.emission_enabled = true
			m.emission = Color("fff3d8")
			m.emission_energy_multiplier = LAMP_DAY["HeadLamp"]
		"TailLamp":
			m = base("b0221c", 0.12, 0.0, 0.7)
			m.clearcoat_enabled = true
			m.clearcoat = 1.0
			m.clearcoat_roughness = 0.03
			m.emission_enabled = true
			m.emission = Color("ff1a0a")
			m.emission_energy_multiplier = LAMP_DAY["TailLamp"]
		"Interior":
			m = base("2a2a2e", 0.9, 0.0, 0.3)
			m.normal_enabled = true
			m.normal_texture = weave()
			m.normal_scale = 0.25
			m.uv1_scale = Vector3(6, 6, 6)
		"Seat":
			m = base("3a3632", 0.93, 0.0, 0.25)
			m.normal_enabled = true
			m.normal_texture = weave()
			m.normal_scale = 0.5
			m.uv1_scale = Vector3(10, 10, 10)
		"ArchLiner":
			m = base("141415", 0.95, 0.0, 0.2)
		"Plate":
			m = base("f2f2ee", 0.35, 0.1, 0.6)
		_:
			return null
	return m
