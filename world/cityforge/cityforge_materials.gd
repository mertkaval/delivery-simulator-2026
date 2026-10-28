class_name CityForgeMaterials
extends RefCounted
## The CityForge material set: Blender material names (CF_*) on the generated GLBs -> the game's
## materials (the same procedural surfaces and scanned textures as the classic city).
## tools/cityforge/build_city.py and kit.py name the materials; this is the other half of that contract.

const SURFACE := preload("res://world/cityforge/cityforge_surface.gdshader")
const TEX := "res://world/city_assets/textures/"
## name -> [surface kind, tint, extra]: extra "roof" tints from INSTANCE_CUSTOM, a number is emission.
const SURFACES := {
	"CF_Siding": [3, "ffffff"], "CF_Roof": [6, "ffffff", "roof"], "CF_Trim": [0, "e9e6dc"], "CF_Glass": [7, "3c5663"],
	"CF_Door": [4, "6b3a2a"], "CF_Brick": [5, "9a5a46"], "CF_Concrete": [2, "b9b8b0"], "CF_Wood": [4, "a07850"],
	"CF_Metal": [8, "3a4249"], "CF_RoofFlat": [9, "6a6c6a"], "CF_Bark": [4, "5a4636"], "CF_Leaves": [19, "ffffff"],
	"CF_Sidewalk": [2, "c8c6bd"], "CF_Curb": [2, "d6d4cb"], "CF_Lane": [1, "4a4a48"], "CF_Parking": [1, "3f4142"],
	"CF_Facade": [12, "ffffff"], "CF_SidingV": [3, "ffffff"], "CF_RoofV": [6, "ffffff"], "CF_LeavesV": [19, "ffffff"], "CF_BrickFacade": [20, "ffffff"], "CF_Stone": [12, "ffffff"], "CF_Curtain": [13, "ffffff"],
	"CF_MetalSiding": [14, "ffffff"], "CF_Awning": [15, "ffffff"], "CF_Storefront": [13, "8fa3ad"], "CF_SignBoard": [0, "ffffff"],
	"CF_FenceWood": [4, "8a6440"], "CF_Picket": [16, "f2f1ea"], "CF_Iron": [17, "1c1d1f"], "CF_Hedge": [18, "3d6a2a"],
	"CF_FireDoor": [8, "b0201a"], "CF_Railing": [8, "8a9096"], "CF_Path": [2, "b8ad98"], "CF_SignalPole": [8, "c9a227"],
	"CF_Hydrant": [8, "d8b62a"], "CF_HydrantCap": [8, "b52a20"], "CF_SignGreen": [0, "1f6b3a"], "CF_SignRed": [0, "b81c1c"],
	"CF_SignWhite": [0, "f3f3f0"], "CF_SignBlue": [0, "1d4aa0"],
	"CF_LampGlow": [0, "fff1c8", 2.5], "CF_SignalRed": [0, "e0281c", 1.6], "CF_SignalAmber": [0, "ffaa1a", 0.25],
	"CF_SignalGreen": [0, "2fe08a", 0.25], "CF_SignalWalk": [0, "f5f2e6", 0.8],
}
## Surfaces tinted by COLOR (MultiMesh instance colour or vertex colour); the rest keep their own colour.
const TINTED := ["CF_Siding", "CF_Leaves", "CF_SidingV", "CF_RoofV", "CF_LeavesV", "CF_Facade", "CF_Stone", "CF_Curtain",
	"CF_MetalSiding", "CF_Awning", "CF_SignBoard", "CF_BrickFacade"]
static var cache: Dictionary = {}

static func get_material(name: String) -> Material:
	var key := name.get_slice(".", 0)          # Blender duplicates: CF_Glass.001
	if cache.has(key): return cache[key]
	var material: Material
	if key == "CF_Asphalt":
		var road := ShaderMaterial.new()
		road.shader = preload("res://world/cityforge/cityforge_road.gdshader")
		road.set_shader_parameter("asphalt", load(TEX + "asphalt_03_Diffuse.jpg"))
		road.set_shader_parameter("asphalt_normal", load(TEX + "asphalt_03_nor_gl.jpg"))
		material = road
	elif key == "CF_Terrain" or key == "CF_Verge":
		var ground := ShaderMaterial.new()
		ground.shader = preload("res://world/cityforge/cityforge_terrain.gdshader") if key == "CF_Terrain" else preload("res://world/ground.gdshader")
		ground.set_shader_parameter("grass_color", load(TEX + "leafy_grass_Diffuse.jpg"))
		ground.set_shader_parameter("grass_normal", load(TEX + "leafy_grass_nor_gl.jpg"))
		if key == "CF_Verge": ground.set_shader_parameter("grass_rough", load(TEX + "leafy_grass_Rough.jpg"))
		material = ground
	elif key == "CF_Water":
		var water := ShaderMaterial.new()
		water.shader = preload("res://world/cityforge/cityforge_water.gdshader")
		material = water
	else:
		var spec: Array = SURFACES.get(key, [0, "8a8f8c"])
		var surface := ShaderMaterial.new()
		surface.shader = SURFACE
		surface.set_shader_parameter("surface_kind", int(spec[0]))
		surface.set_shader_parameter("tint", Color(str(spec[1])))
		if spec.size() > 2:
			if spec[2] is String: surface.set_shader_parameter("roof_from_custom", true)
			else: surface.set_shader_parameter("emission_energy", float(spec[2]))
		if key in TINTED: surface.set_shader_parameter("tinted", true)
		if key in ["CF_Facade", "CF_Curtain", "CF_Stone", "CF_BrickFacade"]:
			surface.set_meta("night_windows", true)
		material = surface
	cache[key] = material
	return material

## Every surface of the mesh gets its CityForge material (by the imported material's name).
static func apply(mesh: Mesh) -> void:
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s)
		var key: String = m.resource_name if m != null else ""
		if key.begins_with("CF_"):
			mesh.surface_set_material(s, get_material(key))

## Lit windows and lamps follow the time of day (0 by day, 1 at night).
static func set_night(amount: float) -> void:
	for key: String in cache:
		var m := cache[key] as ShaderMaterial
		if m == null: continue
		if m.has_meta("night_windows"): m.set_shader_parameter("emission_energy", 1.4 * amount)
	var lamp := cache.get("CF_LampGlow") as ShaderMaterial
	if lamp: lamp.set_shader_parameter("emission_energy", 0.4 + 3.0 * amount)
