class_name CedarNeighborhood
extends Node3D
const PICKUP = Vector3(-14, 1.0, 12)
var doors: Array[Vector3] = []
var cedar_house: Node3D
const CEDAR_HOME_ORIGIN = Vector3(17.9, 0.015, 29.6)
var materials: Dictionary = {}
var daylight: DirectionalLight3D
var atmosphere: Environment
var lamps: Array[OmniLight3D] = []
var house_paths: Array[MeshInstance3D] = []
var residential_models: Array[PackedScene] = []
var scenery_houses: Array[Vector2] = []
var sky_material: ShaderMaterial
var last_sky_minute := -1
var park_count := 0
var downtown: DowntownDistrict
var streets: StreetGrid
var residences: HouseInstancer
var signage: StreetSignage
var restaurants: RestaurantInteriors
var buses: BusSystem
var animals: AnimalLife
var weather: WeatherSystem
var furniture: StreetFurniture
var vfx: CityVFX

func set_time(hour: float) -> void:
	var amount := smoothstep(-0.12, 0.35, sin((hour - 6.0) / 24.0 * TAU))
	daylight.rotation_degrees = Vector3(-maxf(8.0, sin((hour - 6.0) / 24.0 * TAU) * 70.0), hour * 15.0, 0)
	# Warm, low sun at golden hour; neutral white at noon.
	var noon := smoothstep(0.25, 0.8, amount)
	daylight.light_color = Color("ffb877").lerp(Color("fff1dc"), noon)
	daylight.light_energy = amount * 1.6
	# Faint blue moonlight keeps night streets readable between lamp pools.
	var moon := 1.0 - smoothstep(0.0, 0.18, amount)
	if moon > 0.0:
		daylight.light_color = daylight.light_color.lerp(Color("8ea6d8"), moon)
		daylight.light_energy = maxf(daylight.light_energy, 0.16 * moon)
	atmosphere.background_color = Color("101c32").lerp(Color("a8bac1"), amount)
	if sky_material != null:
		if int(hour*60)!=last_sky_minute:
			last_sky_minute=int(hour*60)
			sky_material.set_shader_parameter("daylight",amount)
			sky_material.set_shader_parameter("clock_hours",hour)
			sky_material.set_shader_parameter("sun_direction",daylight.global_basis.z)
	atmosphere.fog_light_color = atmosphere.background_color
	atmosphere.fog_light_energy = lerpf(0.1, 0.6, amount)
	# Ambient comes from the sky's radiance; energy only lifts night readability.
	atmosphere.ambient_light_energy = lerpf(1.6, 0.85, amount)
	atmosphere.ambient_light_color = Color("7185b4").lerp(Color("c3d1d6"), amount)
	for lamp in lamps:
		lamp.light_energy = (1.0 - amount) * 3.0
	HiggsfieldHousing.set_daylight(amount)
	if downtown!=null: downtown.set_time(hour,amount)
	CityKit.set_night(1.0 - amount)
	if buses != null: buses.set_night(1.0 - amount)
	if vfx!=null: vfx.set_time(hour,amount)
	if weather != null:
		weather.set_time(hour)
		weather.apply_light(daylight, atmosphere, sky_material)

func lamp_at(at: Vector3) -> void:
	var lamp := OmniLight3D.new()
	lamp.position = at
	lamp.light_color = Color("ffda9a")
	lamp.omni_range = 13.0
	lamp.shadow_enabled = false
	add_child(lamp)
	lamps.append(lamp)

func material(color: String) -> Material:
	if color == "3a4249": return CityAssets.pbr("asphalt_03", 0.5)
	return CityMaterials.get_surface(color)

func box(at: Vector3, size: Vector3, color: String, solid: bool = true, interaction: String = "") -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = size
	mesh.mesh = cube
	mesh.material_override = material(color)
	mesh.position = at
	add_child(mesh)
	if solid:
		var body := StaticBody3D.new()
		var collision := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = size
		collision.shape = shape
		body.add_child(collision)
		mesh.add_child(body)
		if interaction != "":
			body.set_meta("interaction", interaction)
	return mesh

func label_at(words: String, at: Vector3, size: int = 48, color: Color = Color.WHITE) -> Label3D:
	var label := Label3D.new()
	label.text = words
	label.position = at
	label.font_size = size
	label.pixel_size = 0.004
	label.modulate = color
	label.outline_size = 4
	add_child(label)
	return label

func _ready() -> void:
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	atmosphere = env
	env.background_mode = Environment.BG_SKY
	sky_material = ShaderMaterial.new()
	sky_material.shader = preload("res://world/sky.gdshader")
	var cloud_texture := NoiseTexture2D.new()
	cloud_texture.width=512
	cloud_texture.height=512
	cloud_texture.seamless=true
	var cloud_noise := FastNoiseLite.new()
	cloud_noise.seed=8026
	cloud_noise.noise_type=FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	cloud_noise.frequency=.013
	cloud_noise.fractal_octaves=5
	cloud_texture.noise=cloud_noise
	sky_material.set_shader_parameter("cloud_noise",cloud_texture)
	var sky := Sky.new()
	sky.sky_material = sky_material
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	sky.process_mode = Sky.PROCESS_MODE_INCREMENTAL
	env.sky = sky
	env.background_color = Color("a8bac1")
	# Image-based lighting from the sky: soft blue fill in shade, sky reflections on glass/paint.
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.ambient_light_color = Color("c3d1d6")
	env.ambient_light_energy = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.05
	env.ssao_enabled = true
	env.ssao_intensity = 1.6
	env.ssao_radius = 1.2
	env.ssao_detail = 0.6
	# Screen-space indirect light: sunlit walls bounce colour into streets and porches.
	env.ssil_enabled = true
	env.ssil_intensity = 0.8
	env.ssil_radius = 4.0
	env.glow_enabled = true
	env.glow_intensity = 0.35
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.2
	env.fog_enabled = true
	env.fog_density = 0.0007
	env.fog_aerial_perspective = 0.55
	env.fog_sky_affect = 0.12
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.06
	env.adjustment_saturation = 1.08
	environment.environment = env
	add_child(environment)
	var sun := DirectionalLight3D.new()
	daylight = sun
	sun.rotation_degrees = Vector3(-42, -28, 0)
	sun.light_color = Color("fff0d2")
	sun.light_energy = 1.7
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 170.0
	sun.directional_shadow_split_1 = 0.08
	sun.directional_shadow_split_2 = 0.22
	sun.directional_shadow_split_3 = 0.5
	sun.directional_shadow_blend_splits = true
	sun.shadow_blur = 1.4
	sun.light_angular_distance = 0.5
	add_child(sun)
	var ground := box(Vector3(0, -0.3, -320), Vector3(240, 0.6, 780), '66765e')
	var grass_surface := ShaderMaterial.new()
	grass_surface.shader = preload('res://world/ground.gdshader')
	grass_surface.set_shader_parameter("grass_color", load("res://world/city_assets/textures/leafy_grass_Diffuse.jpg"))
	grass_surface.set_shader_parameter("grass_normal", load("res://world/city_assets/textures/leafy_grass_nor_gl.jpg"))
	grass_surface.set_shader_parameter("grass_rough", load("res://world/city_assets/textures/leafy_grass_Rough.jpg"))
	ground.material_override = grass_surface
	asset_at("horizon_terrain",Vector3.ZERO,2500)
	# Preserve the source terrain while lowering its downtown footprint at runtime.
	var terrain_surface := ShaderMaterial.new()
	terrain_surface.shader=preload("res://world/downtown/terrain_transition.gdshader")
	for mesh in get_child(get_child_count()-1).find_children("*","MeshInstance3D",true,false): mesh.material_override=terrain_surface
	# Blender street kit: carriageways, curbs, lane/bike markings, junctions, crosswalks.
	streets = StreetGrid.new()
	streets.name = "StreetGrid"
	add_child(streets)
	for run in sidewalk_runs(-690, 50):
		for side in [-1, 1]:
			box(Vector3(side * 8, 0.025, (run.x + run.y) * 0.5), Vector3(4, 0.05, run.y - run.x), "bdc2b8", false)
	# Real collision boundaries, with visible hedges at the edge of the block.
	box(Vector3(-119,2,-320),Vector3(2,4,780),"40594b").hide()
	var boundary_start := -710.0
	for crossing in [-678.0,-538.0,-398.0,-258.0,81.0]:
		var boundary_end: float=crossing-12
		box(Vector3(119,2,(boundary_start+boundary_end)*.5),Vector3(2,4,boundary_end-boundary_start),"40594b").hide()
		boundary_start=crossing+12
	for z in [-709, 69]:
		box(Vector3(0, 2, z), Vector3(240, 4, 2), "40594b").hide()
	# Vancouver-style residential district: street-facing houses on narrow lots, rear lanes,
	# edge forest (ResidentialLayout / HouseInstancer). Delivery doors are addresses 0-35.
	residences = HouseInstancer.new()
	residences.name = "Residences"
	add_child(residences)
	for i in range(36): doors.append(CityCatalog.address_position(i))
	house_paths.assign(residences.paths)
	for lamp in residences.porch_lamps: lamps.append(lamp)
	for lot in ResidentialLayout.lots():
		if lot.delivery < 0: scenery_houses.append(ResidentialLayout.house_rect(lot).get_center() * Vector2.ONE)
	for z in range(-680, 44, 18):
		if near_cross_street(z): continue
		for x in [-10.7, 10.7]:
			if front_walk_near(Vector3(x, 0, z)): continue
			tree(Vector3(x, 0, z))
		asset_at("street_lamp",Vector3(6.5,0,z+5),180)
		lamp_at(Vector3(6.5, 4.3, z + 5))
	build_restaurant(0)
	# Starter porch and equipment stand form a short, readable onboarding area.
	build_cedar_home()
	box(Vector3(7, 2.8, 19), Vector3(1.8, 0.38, 0.08), "254e44", false)
	label_at("ATATÜRK AVENUE", Vector3(7, 2.8, 19.06), 26)
	box(Vector3(7, 1.4, 19), Vector3(0.08, 2.8, 0.08), "394a50")
	for z in range(-246, 48, 3):
		for x in [-8, 8]:
			box(Vector3(x, 0.057, z), Vector3(3.5, 0.012, 0.025), "818c89", false)
	for i in [1, 2]:
		build_restaurant(i)
	for z in [-93, -177]:
		# Crosswalk bars come from StreetGrid. Lane-specific stop paint, flush with
		# the asphalt and spanning traffic + bike lane. Never straddle centre line.
		for side in [-1, 1]:
			var stop := box(Vector3(side * 3, StreetGrid.SURFACE_Y + 0.006, z + side * 5), Vector3(4.8, 0.002, 0.25), "deded3", false)
			stop.material_override = streets.surface("PaintWhite", null)
			stop.name = "StopLine_%d_%d" % [z, side]
	for z in [-38, -140, -216]:
		bench(Vector3(12, 0, z))
	for z in [-110, -190]:
		for x in [-92, 92]:
			commercial_block(Vector3(x, 0, z))
	build_estate()
	# Terraces, walk-ups and the mixed-use corridor from the Blender city kit.
	var kit_buildings := KitBuilder.new()
	kit_buildings.name = "KitBuildings"
	add_child(kit_buildings)
	# Thirteen Turkish restaurants fitted out inside the corridor storefronts.
	restaurants = RestaurantInteriors.new()
	restaurants.name = "Restaurants"
	add_child(restaurants)
	var traffic := preload("res://world/traffic.gd").new()
	traffic.name = 'CityTraffic'
	traffic.process_mode = Node.PROCESS_MODE_PAUSABLE
	add_child(traffic)
	expanded_blocks()
	batch_imported_assets()
	batch_street_details()
	var grass := preload('res://world/vegetation.gd').new()
	grass.name = 'GrassMeadows'
	add_child(grass)
	var life := preload('res://world/city_life.gd').new()
	life.name = 'CityLife'
	add_child(life)
	downtown=DowntownDistrict.new()
	downtown.name="RainlineDowntown"
	downtown.block_count=9
	add_child(downtown)
	# Three ring bus lines with shelters, dwell and boarding (BusSystem).
	buses = BusSystem.new()
	buses.name = "Buses"
	add_child(buses)
	furniture = StreetFurniture.new()
	furniture.name = "StreetFurniture"
	add_child(furniture)
	animals = AnimalLife.new()
	animals.name = "Animals"
	add_child(animals)
	for destination in DowntownCatalog.DESTINATIONS: doors.append(destination)
	# Ambient effects last: they read lamps, downtown lights and kit chimneys built above.
	vfx = CityVFX.new()
	vfx.name = "CityVFX"
	add_child(vfx)
	weather = WeatherSystem.new()
	weather.name = "Weather"
	add_child(weather)

func batch_imported_assets() -> void:
	var groups := {}
	for root_node in get_children():
		if root_node.name in ["CityTraffic","CedarHome"] or root_node is GeometryInstance3D: continue
		for node in root_node.find_children("*","MeshInstance3D",true,false):
			if not node.is_visible_in_tree() or node.mesh==null or node.get_child_count()>0: continue
			var cell := Vector2i(floori(node.global_position.x/48),floori(node.global_position.z/48))
			var surface: Material = node.material_override
			var key := "%d_%d_%d_%d_%d" % [node.mesh.get_instance_id(),surface.get_instance_id() if surface!=null else 0,cell.x,cell.y,int(node.visibility_range_end)]
			if not groups.has(key): groups[key]=[]
			groups[key].append(node)
	for meshes: Array in groups.values():
		if meshes.size()<2: continue
		var first: MeshInstance3D=meshes[0]
		var instances := MultiMesh.new()
		instances.transform_format=MultiMesh.TRANSFORM_3D
		instances.mesh=first.mesh
		instances.instance_count=meshes.size()
		var origin := first.global_position
		for i in range(meshes.size()):
			var transform: Transform3D=meshes[i].global_transform
			transform.origin-=origin
			instances.set_instance_transform(i,transform)
		var batch := MultiMeshInstance3D.new()
		batch.multimesh=instances
		batch.material_override=first.material_override
		batch.visibility_range_end=first.visibility_range_end
		batch.visibility_range_end_margin=12
		add_child(batch)
		batch.global_position=origin
		for node in meshes: node.queue_free()

func batch_street_details() -> void:
	# Share one instanced draw per material and block, retaining physical bodies.
	# Paths and crossing markers remain inspectable by the gameplay tests.
	var batches: Dictionary = {}
	var collisions := Node3D.new()
	collisions.name = "StreetCollisions"
	add_child(collisions)
	for child in get_children():
		if not child is MeshInstance3D or not child.visible: continue
		if not child.mesh is BoxMesh: continue
		if child in house_paths or str(child.name).begins_with("StopLine_"): continue
		var dimensions: Vector3 = child.mesh.size
		# Large terrain/road surfaces should retain their own culling bounds.
		if dimensions.x > 30 or dimensions.z > 30: continue
		var key := "%d_%d_%d" % [child.material_override.get_instance_id(), floori(child.position.x / 64), floori(child.position.z / 64)]
		if not batches.has(key):
			batches[key] = {"material": child.material_override, "transforms": []}
		batches[key].transforms.append(child.transform.scaled_local(dimensions))
		for body in child.get_children(): body.reparent(collisions, true)
		child.queue_free()
	var unit := BoxMesh.new()
	unit.size = Vector3.ONE
	for data: Dictionary in batches.values():
		var instances := MultiMesh.new()
		instances.transform_format = MultiMesh.TRANSFORM_3D
		instances.mesh = unit
		instances.instance_count = data.transforms.size()
		for i in range(data.transforms.size()):
			instances.set_instance_transform(i, data.transforms[i])
		var batch := MultiMeshInstance3D.new()
		batch.multimesh = instances
		batch.material_override = data.material
		add_child(batch)

func finish_residence(node: Node, index: int) -> void:
	if node is MeshInstance3D:
		var surface_name := str(node.name).to_lower()
		var color := ""
		if surface_name.begins_with("painted") and "cedar" in surface_name:
			color = ["859b93", "b6a287", "8298a7"][index % 3]
		elif surface_name.begins_with("slate"): color = "485257"
		elif surface_name.begins_with("chimney"): color = "806753"
		elif surface_name.begins_with("cedar"): color = "9c8060"
		elif surface_name.begins_with("foundation"): color = "737773"
		elif surface_name.begins_with("gutters"): color = "384950"
		if color != "": node.material_override = material(color)
		node.visibility_range_end = 600
	for child in node.get_children(): finish_residence(child, index)

## North-south sidewalk spans between `from_z` and `to_z`, interrupted by cross-street junctions.
func sidewalk_runs(from_z: float, to_z: float) -> Array[Vector2]:
	var junctions: Array[Vector2] = []
	for crossing in CityCatalog.CROSS_STREETS:
		junctions.append(Vector2(crossing - 5, crossing + 5))
	var runs: Array[Vector2] = []
	for run in StreetGrid.subtract(Vector2(from_z, to_z), junctions):
		if run.y - run.x > 0.5: runs.append(run)
	return runs

## True if a street tree at t would stand in a house's front walk.
func front_walk_near(at: Vector3) -> bool:
	for lot in ResidentialLayout.lots():
		if signf(lot.line_x) == signf(at.x) and absf(lot.line_x) == 10.5:
			var door: Vector3 = ResidentialLayout.TYPES[lot.type].door
			var walk: Vector3 = ResidentialLayout.transform(lot) * Vector3(door.x, 0, 0)
			if absf(walk.z - at.z) < 1.8: return true
	return false

func near_cross_street(z: float) -> bool:
	for crossing in CityCatalog.CROSS_STREETS:
		if absf(z - crossing) < 10: return true
	return false

func expanded_blocks() -> void:
	# Carriageways and markings come from StreetGrid; sidewalks stop at junctions,
	# and cross-street sidewalks run between the Cedar Lane and side-road sidewalks.
	for x in CityCatalog.SIDE_ROADS:
		for run in sidewalk_runs(-678, -258):
			for side in [-1, 1]:
				box(Vector3(x + side * 7, 0.04, (run.x + run.y) * 0.5), Vector3(4, 0.08, run.y - run.x), "bdc2b8", false)
	for z in CityCatalog.CROSS_STREETS:
		for side in [-1, 1]:
			for x in [-32.5, 32.5]:
				box(Vector3(x, 0.04, z + side * 7), Vector3(45, 0.08, 4), "bdc2b8", false)
			# Connector sidewalk from the east side-road sidewalk to downtown, wide enough
			# to cover the downtown connector's collision slab (z +-11).
			box(Vector3(96.5, 0.04, z + side * 8), Vector3(47, 0.08, 6), "bdc2b8", false)
	for row in range(12):
		var z: float = CityCatalog.address_position(12 + row * 2).z - 1.3
		for side in [-1, 1]:
			asset_at("street_lamp",Vector3(side*70,0,z+5),180)
			lamp_at(Vector3(side * 70, 4.5, z + 5))
	# Small landscaped squares occupy the otherwise empty inner blocks.
	for z in [-330, -470, -590]:
		for side in [-1, 1]:
			var x: float = side * 44
			build_park(Vector3(x, 0, z))
	# Street-name posts at every junction, park signs and memorial busts (StreetNames).
	signage = StreetSignage.new()
	signage.name = "StreetSignage"
	add_child(signage)

func build_park(at: Vector3) -> void:
	park_count += 1
	var garden := CityAssets.create("park_garden", 200)
	garden.position = at
	add_child(garden)
	var fountain := CityAssets.create("fountain", 150)
	fountain.position = at + Vector3(4, 0, -5)
	add_child(fountain)
	var basin := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	var cylinder := CylinderShape3D.new()
	cylinder.radius = 1.75
	cylinder.height = 0.55
	collision.shape = cylinder
	collision.position.y = 0.275
	basin.add_child(collision)
	fountain.add_child(basin)
	var water := MeshInstance3D.new()
	var disk := CylinderMesh.new()
	disk.top_radius = 1.49
	disk.bottom_radius = 1.49
	disk.height = 0.01
	disk.radial_segments = 48
	water.mesh = disk
	var surface := StandardMaterial3D.new()
	surface.albedo_color = Color("477d87")
	surface.metallic = 0.45
	surface.roughness = 0.17
	water.material_override = surface
	water.position.y = 0.43
	fountain.add_child(water)
	for delta in [Vector3(4, 0, 4), Vector3(-4.5, 0, 6), Vector3(-3, 0, -10)]: bench(at + delta)
	for delta in [Vector3(-8, 0, -10), Vector3(8, 0, 11), Vector3(-8, 0, 11)]: tree(at + delta)
	for x in [-6.5, -2.5]:
		for z in [4, 8]: box(at + Vector3(x, 1.42, z), Vector3(0.16, 2.84, 0.16), "9c8060").hide()

func tree(at: Vector3) -> void:
	var variation := absi(int(at.x * 7 + at.z)) % 3
	var model := CityAssets.create(["maple", "birch", "conifer"][variation], 240)
	model.position = at
	model.rotation.y = fmod(absf(at.z * 0.83 + at.x), TAU)
	model.scale = Vector3.ONE * (0.80 + float(variation) * 0.12)
	add_child(model)
	# Only the trunk needs collision; branches and leaves are visual.
	var trunk := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.24
	capsule.height = 3.5
	shape.shape = capsule
	shape.position.y = 1.75
	trunk.add_child(shape)
	model.add_child(trunk)

func bench(at: Vector3) -> void:
	var model := CityAssets.create("park_bench", 120)
	model.position = at
	add_child(model)
	box(at + Vector3(0, 0.48, 0), Vector3(2.03, 0.96, 0.7), "344448").hide()

func build_restaurant(index: int) -> void:
	var p: Vector3 = CityCatalog.PICKUPS[index] - Vector3.UP
	var model := CityAssets.create("restaurant_%d" % index, 300)
	model.name = "Restaurant_%d" % index
	model.position = p
	add_child(model)
	# Solid walls and shop windows surround a genuinely open 3.3m entry.
	for x in [-10, 2]: box(p + Vector3(x, 2.15, -2.6), Vector3(0.22, 4.3, 10.6), "806753").hide()
	box(p + Vector3(-4, 2.15, -7.9), Vector3(12, 4.3, 0.22), "806753").hide()
	box(p + Vector3(-5.8, 1.6, 2.75), Vector3(8.2, 3.2, 0.12), "344448").hide()
	var interaction: String = "pickup" if index == 0 else "pickup_" + CityCatalog.RESTAURANTS[index]
	box(p + Vector3(-3, 0.55, 0), Vector3(7, 1.1, 1), "b98a5c", true, interaction).hide()
	box(p + Vector3(0, 1.35, 0), Vector3(0.45, 0.55, 0.3), "d4b885", true, interaction).hide()
	for at in [Vector3(-8.4, 0.4, 0.65), Vector3(-8.4, 0.4, -2.3), Vector3(-5.9, 0.4, -3.6)]:
		box(p + at, Vector3(1.25, 0.8, 1.8), "9c8060").hide()
	box(p + Vector3(-5.5, 0.5, -6.9), Vector3(8, 1, 1.5), "384950").hide()
	box(p + Vector3(0.9, 1.15, -6.9), Vector3(1.45, 2.3, 1.3), "384950").hide()
	label_at(CityCatalog.NAMES[index].to_upper(), p + Vector3(-4, 3.65, 3.05), 62)
	label_at("ORDER PICKUP", p + Vector3(-0.1, 0.9, 0.57), 21)
	var entry: Array = RestaurantCatalog.LIST[index]
	label_at("%s  ·  %s" % [str(entry[2]).to_upper(), entry[3]], p + Vector3(-4, 3.38, 3.055), 20)
	for x in [-7.5, -4, 0]:
		var light := OmniLight3D.new()
		light.position = p + Vector3(x, 2.55, -2.4)
		light.light_color = Color("ffdfab")
		light.light_energy = 0.9
		light.omni_range = 5
		light.shadow_enabled = false
		add_child(light)
	box(p + Vector3(-4, 0.035, 4), Vector3(12, 0.07, 2), "bdc2b8", false)
	bench(p + Vector3(-7, 0, 4.5))

func commercial_block(at: Vector3) -> void:
	# The building itself is a city-kit walk-up (CityLayout/KitBuilder) with its own
	# collision and name sign; only the forecourt paving is laid here.
	box(at + Vector3(0, 0.04, 9), Vector3(17, 0.08, 3), "bdc2b8", false)
	box(at+Vector3(0,.035,12),Vector3(18,.07,5),"bdc2b8",false)

func asset_at(id: String, at: Vector3, distance: float = 220) -> Node3D:
	var model := CityAssets.create(id,distance)
	model.position = at
	add_child(model)
	return model

func ribbon(path: PackedVector3Array, width: float, height: float, surface: Material) -> void:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uv := PackedVector2Array()
	var indices := PackedInt32Array()
	var length := 0.0
	for i in range(path.size()):
		var tangent := (path[mini(i+1,path.size()-1)]-path[maxi(0,i-1)]).normalized()
		var across := tangent.cross(Vector3.UP)*width*.5
		if i>0: length += path[i].distance_to(path[i-1])
		for side in [-1,1]:
			vertices.append(path[i]+across*side+Vector3.UP*height)
			normals.append(Vector3.UP)
			uv.append(Vector2(side,length))
		if i>0:
			var k := i*2
			indices.append_array(PackedInt32Array([k-2,k,k-1,k-1,k,k+1]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX]=vertices
	arrays[Mesh.ARRAY_NORMAL]=normals
	arrays[Mesh.ARRAY_TEX_UV]=uv
	arrays[Mesh.ARRAY_INDEX]=indices
	var geometry := ArrayMesh.new()
	geometry.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var node := MeshInstance3D.new()
	node.mesh=geometry
	node.material_override=surface
	add_child(node)

func build_estate() -> void:
	var roads := CityCatalog.estate_roads()
	set_meta("curved_roads",roads)
	for path in roads:
		ribbon(path,13,.08,material("bdc2b8"))
		ribbon(path,8,.095,material("3a4249"))
	for x in [-64,64]:
		build_park(Vector3(x,0,-145))
	for id in ShopCatalog.LOCATIONS:
		build_store(id,ShopCatalog.LOCATIONS[id])
	build_store("wc",Vector3(-40,0,32))
	box(Vector3(-40,.04,43),Vector3(14,.08,10),"bdc2b8",false)

func build_store(id: String, at: Vector3) -> void:
	asset_at("store_"+id,at,260)
	for x in [-7,7]: box(at+Vector3(x,1.9,0),Vector3(.26,3.8,10),"737773").hide()
	box(at+Vector3(0,1.9,-5),Vector3(14,3.8,.26),"737773").hide()
	for x in [-4.5,4.5]: box(at+Vector3(x,1.65,5),Vector3(5,3.3,.05),"737773").hide()
	box(at+Vector3(4,.55,1),Vector3(3,1.1,.8),"737773",true,"wc" if id=="wc" else "store_"+id).hide()
	box(at+Vector3(0,.04,9),Vector3(16,.08,8),"bdc2b8",false)
	var sign_label := label_at("PUBLIC WC · WATER" if id=="wc" else ShopCatalog.TITLES[id],at+Vector3(0,3.5,5.23),64)
	sign_label.pixel_size=.009
	label_at("E · USE WC" if id=="wc" else "E · SHOP",at+Vector3(4,1.45,1.45),28)
	if id=="wc":
		box(at+Vector3(-3,.3,-2),Vector3(.7,.6,.8),"737773",true,"wc").hide()
		box(at+Vector3(-1,1.1,-2.5),Vector3(.12,2.2,4.5),"737773").hide()
		box(at+Vector3(-3.5,1.1,-.4),Vector3(5,2.2,.12),"737773").hide()
		box(at+Vector3(3,.9,-3),Vector3(.85,.30,.65),"737773",true,"water").hide()
		label_at("DRINKING WATER",at+Vector3(3,1.5,-3),22)
	else:
		var displays: Array = {"equipment":["helmet","gloves","backpack","delivery_bag"],"bikes":["bicycle","bicycle"],"cars":["sedan","hatchback"],"scooters":["scooter","scooter"]}[id]
		for i in range(displays.size()):
			# The showroom sedan is the exact car the player gets after buying it (factory paint, full LODs).
			var model: Node3D
			if displays[i] == "sedan":
				model = CityAssets.create_player_vehicle("sedan")
				model.position = at+Vector3(-4+i*2.8,.12,-3)
				add_child(model)
			else:
				model = asset_at(displays[i],at+Vector3(-4+i*2.8,1.84 if id=="equipment" else .12,-3),110)
			if id=="equipment": model.position=at+Vector3(-5+(i%2)*3,.46+(i/2)*.7,-4.5)
			if id=="cars": model.position=at+Vector3(-3.8+i*6.5,.12,-1.8)
		# Converted Sketchfab people: a clerk at the counter and a guard at the door.
		var shop_index: int = ShopCatalog.LOCATIONS.keys().find(id)
		var clerk: Node3D = LivingAssets.standing_person(1 + shop_index)
		clerk.position=at+Vector3(4,.1,-.2)
		clerk.rotation.y=PI
		add_child(clerk)
		var guard: Node3D = LivingAssets.standing_person(0)
		guard.position=at+Vector3(-6.2,.05,6.4)
		guard.rotation.y=PI
		add_child(guard)
	var light := OmniLight3D.new()
	light.position=at+Vector3(0,2.9,0)
	light.light_color=Color("ffe4bd")
	light.light_energy=1.4
	light.omni_range=10
	add_child(light)

func build_cedar_home() -> void:
	cedar_house = preload("res://world/cedar_house/cedar_house.tscn").instantiate()
	cedar_house.name = "CedarHome"
	cedar_house.position = CEDAR_HOME_ORIGIN
	add_child(cedar_house)
	# Reach the front garden from Cedar Lane without crossing its side fence.
	box(Vector3(13.5, 0.06, 40.25), Vector3(11, 0.04, 1.55), "c1bbaa", false)
	# Rest remains a distinct interaction, so opening the front door never skips a day.
	box(Vector3(17.8, 1.66, 35.40), Vector3(0.30, 0.18, 0.035), "344f53", true, "home")
	label_at("REST / SAVE", Vector3(17.8, 1.88, 35.44), 16)
	label_at("YOUR HOME", Vector3(19, 2.97, 35.34), 27)
	for at in [Vector3(-1.5, 3.15, 3), Vector3(-1.3, 3.15, -2), Vector3(2.9, 3.15, 3), Vector3(2.9, 3.15, -1.2), Vector3(2.9, 3.15, -4.2)]:
		var lamp := OmniLight3D.new()
		lamp.position = CEDAR_HOME_ORIGIN + at
		lamp.light_color = Color("ffdfb0")
		lamp.light_energy = 0.65
		lamp.omni_range = 3.6
		lamp.shadow_enabled = true
		add_child(lamp)
	lamp_at(CEDAR_HOME_ORIGIN + Vector3(1.1, 2.65, 6.3))



