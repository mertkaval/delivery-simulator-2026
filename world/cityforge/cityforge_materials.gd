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
	"CF_Door": [4, "8a5a40"], "CF_Brick": [5, "ffffff"], "CF_Concrete": [2, "ffffff"], "CF_Wood": [4, "ffffff"],
	"CF_Metal": [8, "3a4249"], "CF_RoofFlat": [9, "9a9a96"], "CF_Bark": [4, "5a4636"], "CF_Leaves": [19, "ffffff"],
	"CF_Sidewalk": [2, "ffffff"], "CF_Curb": [2, "f2f0e8"], "CF_Lane": [1, "4a4a48"], "CF_Parking": [1, "3f4142"],
	"CF_Facade": [12, "ffffff"], "CF_SidingV": [3, "ffffff"], "CF_RoofV": [6, "ffffff"], "CF_LeavesV": [19, "ffffff"], "CF_BrickFacade": [20, "ffffff"], "CF_Stone": [12, "ffffff"], "CF_Curtain": [13, "ffffff"],
	"CF_MetalSiding": [14, "ffffff"], "CF_Awning": [15, "ffffff"], "CF_Storefront": [13, "8fa3ad"], "CF_SignBoard": [0, "ffffff"],
	"CF_FenceWood": [4, "ffffff"], "CF_Picket": [16, "f2f1ea"], "CF_Iron": [17, "1c1d1f"], "CF_Hedge": [18, "ffffff"],
	"CF_FireDoor": [8, "b0201a"], "CF_Railing": [8, "8a9096"], "CF_Path": [2, "e8dcc6"], "CF_SignalPole": [8, "c9a227"],
	"CF_Hydrant": [8, "d8b62a"], "CF_HydrantCap": [8, "b52a20"], "CF_SignGreen": [0, "1f6b3a"], "CF_SignRed": [0, "b81c1c"],
	"CF_SignWhite": [0, "f3f3f0"], "CF_SignBlue": [0, "1d4aa0"],
	"CF_BrickLondon": [5, "ffffff"], "CF_BrickPainted": [5, "ffffff"], "CF_Stucco": [0, "ffffff"], "CF_Ashlar": [5, "ffffff"],
	"CF_Cedar": [4, "ffffff"], "CF_Yakisugi": [4, "ffffff"], "CF_LightWood": [4, "ffffff"], "CF_RoofSlate": [6, "ffffff"],
	"CF_RoofTerracotta": [6, "ffffff"], "CF_RoofKawara": [6, "ffffff"], "CF_RoofSeam": [8, "ffffff", "roof"], "CF_Cobbles": [2, "ffffff"],
	"CF_Tatami": [0, "ffffff"], "CF_FloorTiles": [0, "ffffff"], "CF_Parquet": [4, "ffffff"], "CF_Paper": [0, "f2ead8", 0.0],
	"CF_TimberDark": [4, "4a3626"], "CF_Lacquer": [8, "8c1d16"], "CF_Plaster": [0, "ffffff"], "CF_Shutter": [4, "3d6650"],
	"CF_SignPlate": [8, "ffffff"], "CF_SignEdge": [0, "f2f2ee"], "CF_VendGlow": [0, "e8f2ff", 1.2], "CF_PostRed": [8, "b0140f"],
	"CF_Posters": [0, "e6d8b8"], "CF_Brass": [8, "b8903a"], "CF_Plaque": [0, "efe8d4"], "CF_Parasol": [0, "efe6d2"],
	"CF_RoofSeamV": [8, "ffffff"],
	"CF_LampGlow": [0, "fff1c8", 2.5], "CF_SignalRed": [0, "e0281c", 1.6], "CF_SignalAmber": [0, "ffaa1a", 0.25],
	"CF_SignalGreen": [0, "2fe08a", 0.25], "CF_SignalWalk": [0, "f5f2e6", 0.8],
}
## Baked library textures (assets/cityforge/materials/<name>_albedo/_normal/_orm) per CF material.
const TEXTURED := {
	"CF_Siding": "siding", "CF_SidingV": "siding", "CF_Brick": "brick_red", "CF_BrickFacade": "brick_red",
	"CF_BrickLondon": "brick_london", "CF_BrickPainted": "brick_painted", "CF_Stucco": "stucco", "CF_Facade": "stucco",
	"CF_Stone": "ashlar", "CF_Ashlar": "ashlar", "CF_Wood": "cedar_planks", "CF_Cedar": "cedar_planks", "CF_Yakisugi": "yakisugi",
	"CF_LightWood": "light_wood", "CF_Door": "light_wood", "CF_FenceWood": "cedar_planks", "CF_Roof": "shingle_asphalt",
	"CF_RoofV": "shingle_asphalt", "CF_RoofSlate": "slate", "CF_RoofTerracotta": "terracotta", "CF_RoofKawara": "kawara",
	"CF_RoofSeam": "standing_seam", "CF_RoofSeamV": "standing_seam", "CF_Plaster": "stucco", "CF_Concrete": "concrete", "CF_Curb": "concrete", "CF_Sidewalk": "paving",
	"CF_Path": "paving", "CF_Cobbles": "cobbles", "CF_Hedge": "hedge", "CF_Tatami": "tatami", "CF_FloorTiles": "floor_tiles",
	"CF_Parquet": "parquet", "CF_RoofFlat": "concrete",
}
const MAT_DIR := "res://assets/cityforge/materials/"

## Surfaces tinted by COLOR (MultiMesh instance colour or vertex colour); the rest keep their own colour.
const TINTED := ["CF_Siding", "CF_Leaves", "CF_SidingV", "CF_RoofV", "CF_LeavesV", "CF_Facade", "CF_Stone", "CF_Curtain",
	"CF_MetalSiding", "CF_Awning", "CF_SignBoard", "CF_BrickFacade", "CF_Stucco", "CF_BrickPainted", "CF_RoofSeamV", "CF_Hedge",
	"CF_Plaster", "CF_SignPlate"]
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
		if TEXTURED.has(key) and ResourceLoader.exists(MAT_DIR + str(TEXTURED[key]) + "_albedo.jpg"):
			var lib: String = MAT_DIR + str(TEXTURED[key])
			surface.set_shader_parameter("textured", true)
			surface.set_shader_parameter("albedo_tex", load(lib + "_albedo.jpg"))
			surface.set_shader_parameter("normal_tex", load(lib + "_normal.png"))
			surface.set_shader_parameter("orm_tex", load(lib + "_orm.jpg"))
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
