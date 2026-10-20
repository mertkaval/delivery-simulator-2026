class_name CityKit
extends RefCounted
## Runtime side of the Blender city kit (world/citykit/build_kit.py, build_materials.py).
## Modules are GLBs with one mesh per material named Kit<Material>; this maps those names
## to shared PBR materials. Tiling surfaces are world-aligned triplanar so brick courses run
## continuously across modules and survive the non-uniform scaling DowntownDistrict applies.
## Baked ambient occlusion arrives as vertex colour and multiplies the albedo.

const MODULES := "res://world/citykit/modules/%s.glb"
const TEXTURES := "res://world/citykit/textures/%s_%s.png"
## Material name -> [texture set, metres per texture repeat, metallic, normal strength]
const TEXTURED := {
	"KitBrickRed": ["brick_red", 1.8, 0.0, 1.0],
	"KitBrickBuff": ["brick_buff", 1.8, 0.0, 1.0],
	"KitBrickCharcoal": ["brick_charcoal", 1.8, 0.0, 1.0],
	"KitStucco": ["stucco", 2.0, 0.0, 0.6],
	"KitConcrete": ["concrete", 2.0, 0.0, 0.7],
	"KitLimestone": ["limestone", 2.4, 0.0, 0.8],
	"KitMetalPanel": ["metal_panel", 2.0, 0.55, 1.0],
	"KitRoofGravel": ["roof_gravel", 2.0, 0.0, 1.0],
	"KitSlate": ["slate_roof", 1.8, 0.0, 1.0],
	"KitCedar": ["cedar_boards", 1.8, 0.0, 0.8],
	# Party walls: weathered common brick, darker than the street facades.
	"KitPartyBrick": ["brick_red", 1.8, 0.0, 1.0, "9a8a80"],
	# Residential kit: paint-white bases tinted per house through MultiMesh instance colours.
	"KitLapSiding": ["lap_siding", 1.26, 0.0, 1.0],
	"KitShingleSiding": ["shingle_siding", 1.6, 0.0, 1.0],
	"KitBoardBatten": ["board_batten", 2.0, 0.0, 1.0],
	"KitHouseStucco": ["stucco", 2.0, 0.0, 0.8],
	"KitAsphaltShingles": ["asphalt_shingles", 1.8, 0.0, 1.0],
	"KitDeckBoards": ["deck_boards", 1.96, 0.0, 0.8],
	"KitSoil": ["garden_soil", 2.0, 0.0, 1.0],
	"KitPoleWood": ["cedar_boards", 1.8, 0.0, 0.6, "7a6250"],
	# Restaurant interiors (build_restaurants.py).
	"KitTerrazzo": ["terrazzo", 2.0, 0.0, 0.4],
	"KitSubwayTile": ["subway_tile", 1.2, 0.0, 0.8],
	"KitCini": ["cini_tile", 0.8, 0.0, 0.6],
	"KitWoodFloor": ["wood_floor", 1.6, 0.0, 0.7],
}
## Flat finishes: [colour, roughness, metallic]
const FLAT := {
	"KitFrameDark": ["22282b", 0.38, 0.6], "KitFrameBronze": ["4b3a2a", 0.36, 0.7],
	"KitFrameLight": ["a7acaf", 0.3, 0.8], "KitRail": ["202528", 0.42, 0.6],
	"KitDoor": ["2a3134", 0.5, 0.3], "KitSpandrel": ["182025", 0.12, 0.4],
	"KitPaintGreen": ["274d3d", 0.55, 0.0], "KitPaintNavy": ["243650", 0.55, 0.0],
	"KitAwning": ["3e5c4a", 0.92, 0.0],
	"KitTrimPaint": ["ffffff", 0.45, 0.0], "KitDoorPaint": ["ffffff", 0.35, 0.0], "KitGaragePaint": ["ffffff", 0.5, 0.0],
	"KitDoorWood": ["7a4a2a", 0.4, 0.0], "KitRailBlack": ["15181a", 0.4, 0.5], "KitBinBlack": ["1d2124", 0.55, 0.0],
	"KitBinBlue": ["1f4f8f", 0.5, 0.0], "KitBinGreen": ["2d6a3a", 0.5, 0.0], "KitInsulator": ["cfd6d8", 0.3, 0.0],
	"KitBronze": ["6b4a2c", 0.36, 0.85], "KitSignGreen": ["1f5c3a", 0.4, 0.0],
	"KitPlaster": ["eeebe4", 0.85, 0.0], "KitWallPaint": ["ffffff", 0.8, 0.0], "KitAccentPaint": ["ffffff", 0.45, 0.0],
	"KitUpholstery": ["ffffff", 0.7, 0.0], "KitSteel": ["c4c8ca", 0.28, 0.85], "KitSteelDark": ["5d6366", 0.4, 0.7],
	"KitCounterStone": ["e9e5dc", 0.15, 0.0], "KitOak": ["a77a4f", 0.5, 0.0], "KitChalkboard": ["1d2321", 0.85, 0.0],
	"KitCopper": ["b06a3b", 0.3, 0.9], "KitBrass": ["b8913f", 0.3, 0.9], "KitMeatRoast": ["7a3a1c", 0.55, 0.0],
	"KitMeatRaw": ["a24438", 0.5, 0.0], "KitBread": ["d6a35f", 0.8, 0.0], "KitPastry": ["c78838", 0.45, 0.0],
	"KitPistachio": ["6d8f3a", 0.7, 0.0], "KitPotato": ["c79a5a", 0.8, 0.0], "KitLettuce": ["5f9a35", 0.7, 0.0],
	"KitTomato": ["c0392b", 0.35, 0.0], "KitLemon": ["e8c547", 0.45, 0.0], "KitFishSilver": ["98a3a8", 0.22, 0.6],
	"KitIce": ["e2ecef", 0.12, 0.0], "KitCream": ["efe6d2", 0.55, 0.0], "KitSoup": ["b8622c", 0.25, 0.0],
	"KitCharcoal": ["1a1a1a", 0.95, 0.0], "KitPaperBag": ["b8976a", 0.85, 0.0], "KitBottleGreen": ["2f5e3c", 0.1, 0.2],
	"KitRubber": ["1c1f21", 0.8, 0.0], "KitBusGlass": ["34474f", 0.05, 0.6], "KitBusBody": ["eef0ee", 0.3, 0.15],
	"KitTyre": ["1b1d1f", 0.85, 0.0], "KitLedPanel": ["101214", 0.4, 0.0],
	"KitFur": ["ffffff", 0.9, 0.0], "KitFurLight": ["ffffff", 0.9, 0.0], "KitFeather": ["ffffff", 0.75, 0.0],
	"KitFeatherTip": ["ffffff", 0.75, 0.0], "KitBeak": ["d9a531", 0.4, 0.0], "KitEye": ["0c0c0c", 0.08, 0.0],
	"KitNose": ["161616", 0.3, 0.0], "KitNeckSheen": ["5f8f6a", 0.3, 0.4], "KitPaw": ["3a2e28", 0.8, 0.0], "KitCeramic": ["f5f3ee", 0.2, 0.0], "KitTeaGlass": ["b5462a", 0.1, 0.0],
}
static var materials: Dictionary = {}
static var scenes: Dictionary = {}

## Night lighting for emissive kit parts (porch lamps) and the distant house windows.
static func set_night(amount: float) -> void:
	if materials.has("KitLampGlow"): materials.KitLampGlow.emission_energy_multiplier = amount * 2.5
	for lamp in ["KitHeadLight", "KitTailLight"]:
		if materials.has(lamp): materials[lamp].emission_energy_multiplier = 0.4 + amount * 3.0
	HouseInstancer.set_night(amount)

static func has_module(asset: String) -> bool:
	return ResourceLoader.exists(MODULES % asset)

static func scene(asset: String) -> PackedScene:
	if not scenes.has(asset): scenes[asset] = load(MODULES % asset)
	return scenes[asset]

## Material for a kit surface name (accepts Blender's ".001" suffixes and Godot's "_001").
static func material(surface_name: String) -> Material:
	var key := surface_name.get_slice(".", 0)
	if key.length() > 4 and key[-4] == "_" and key.right(3).is_valid_int(): key = key.left(-4)
	if materials.has(key): return materials[key]
	var result: Material
	if key == "KitFoliage":
		result = CityAssets.vegetation()
	elif key == "KitConifer":
		var needles := ShaderMaterial.new()
		needles.shader = preload("res://world/citykit/conifer.gdshader")
		result = needles
	elif key in ["KitHedge", "KitBark"]:
		# Existing PBR library: clipped leaves for hedges, bark for trunks and posts.
		var pbr := CityAssets.pbr("leafy_grass" if key == "KitHedge" else "bark_brown_01", 0.9).duplicate() as StandardMaterial3D
		if key == "KitHedge": pbr.albedo_color = Color("6f8f55")
		pbr.vertex_color_use_as_albedo = true
		result = pbr
	elif key == "KitLampGlow":
		var glow := StandardMaterial3D.new()
		glow.albedo_color = Color("e8d9b8")
		glow.emission_enabled = true
		glow.emission = Color("ffcf88")
		glow.emission_energy_multiplier = 0.0
		result = glow
	elif key == "KitClearGlass":
		# Real transparent glass for restaurant storefronts, vitrines and fridge doors.
		var clear := StandardMaterial3D.new()
		clear.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		clear.albedo_color = Color(0.78, 0.88, 0.9, 0.16)
		clear.roughness = 0.04
		clear.metallic = 0.3
		clear.cull_mode = BaseMaterial3D.CULL_DISABLED
		result = clear
	elif key in ["KitHeadLight", "KitTailLight"]:
		var lamp := StandardMaterial3D.new()
		lamp.albedo_color = Color("f4f1e6") if key == "KitHeadLight" else Color("b0221c")
		lamp.emission_enabled = true
		lamp.emission = Color("fff3d8") if key == "KitHeadLight" else Color("ff2a1a")
		lamp.emission_energy_multiplier = 0.4
		result = lamp
	elif key == "KitEmber":
		var ember := StandardMaterial3D.new()
		ember.albedo_color = Color("3a1a0c")
		ember.emission_enabled = true
		ember.emission = Color("ff6a22")
		ember.emission_energy_multiplier = 2.2
		result = ember
	elif key == "KitGlass":
		# Interiors, curtains and night-lit rooms come from the downtown window shader.
		result = UrbanKit.material("UrbanWindow")
	elif TEXTURED.has(key):
		var spec: Array = TEXTURED[key]
		var surface := StandardMaterial3D.new()
		surface.albedo_texture = load(TEXTURES % [spec[0], "albedo"])
		surface.roughness_texture = load(TEXTURES % [spec[0], "rough"])
		surface.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		surface.normal_enabled = true
		surface.normal_texture = load(TEXTURES % [spec[0], "normal"])
		surface.normal_scale = spec[3]
		surface.metallic = spec[2]
		if spec.size() > 4: surface.albedo_color = Color(spec[4])
		surface.uv1_triplanar = true
		surface.uv1_world_triplanar = true
		surface.uv1_triplanar_sharpness = 8.0
		surface.uv1_scale = Vector3.ONE / float(spec[1])
		surface.vertex_color_use_as_albedo = true
		surface.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		result = surface
	else:
		var spec: Array = FLAT.get(key, ["808080", 0.7, 0.0])
		var flat := StandardMaterial3D.new()
		flat.albedo_color = Color(spec[0])
		flat.roughness = spec[1]
		flat.metallic = spec[2]
		flat.vertex_color_use_as_albedo = true
		result = flat
	materials[key] = result
	return result
