class_name UrbanKit
extends RefCounted
static var parts := {}
static var materials := {}
static var window_material: ShaderMaterial
static func material(name: String) -> Material:
	if materials.has(name): return materials[name]
	var surface: Material
	if name in ["UrbanWindow","UrbanImpostor"]:
		var shader := ShaderMaterial.new()
		shader.shader=preload("res://world/downtown/window.gdshader")
		if name=="UrbanWindow": window_material=shader
		else: shader.set_shader_parameter("distant",true)
		surface=shader
	elif name=="UrbanBrick": surface=CityAssets.pbr("brick_wall_11",.25)
	elif name=="UrbanTimber": surface=CityAssets.pbr("synthetic_wood",.6)
	elif name=="UrbanAsphalt":
		var road := ShaderMaterial.new()
		road.shader=preload("res://world/downtown/road.gdshader")
		road.set_shader_parameter("asphalt",load("res://world/city_assets/textures/asphalt_03_Diffuse.jpg"))
		road.set_shader_parameter("normal_map",load("res://world/city_assets/textures/asphalt_03_nor_gl.jpg"))
		surface=road
	else:
		var colors := {"UrbanConcrete":"929894","UrbanMetal":"25353d","UrbanTrim":"b3b6ac","UrbanLight":"dfc38a","UrbanPaint":"d7d2b9","UrbanGreen":"244f42","UrbanSafety":"c45923","UrbanPaper":"b7a17c","UrbanRubber":"202629"}
		var standard := StandardMaterial3D.new()
		standard.albedo_color=Color(colors.get(name,"78827c"))
		standard.roughness=.38 if name in ["UrbanMetal","UrbanTrim"] else .85
		standard.metallic=.5 if name in ["UrbanMetal","UrbanTrim"] else 0
		surface=standard
	materials[name]=surface
	return surface
static func collect(node: Node, parent: Transform3D, result: Array) -> void:
	var transform := parent
	if node is Node3D: transform=parent*node.transform
	if node is MeshInstance3D:
		var surface: Material=node.material_override
		var source: Material=node.mesh.surface_get_material(0) if node.mesh!=null and node.mesh.get_surface_count()>0 else null
		if source!=null and source.resource_name.begins_with("Kit"): surface=CityKit.material(source.resource_name)
		elif str(node.name).begins_with("Urban"): surface=material(str(node.name))
		elif str(node.name)=="CivicBrick": surface=CityAssets.pbr("brick_wall_11",.25)
		elif str(node.name)=="CivicGrass":
			if not materials.has("CivicLawn"):
				var lawn := CityAssets.pbr("leafy_grass",.6).duplicate() as StandardMaterial3D
				lawn.albedo_color=Color(.40,.66,.30)
				materials.CivicLawn=lawn
			surface=materials.CivicLawn
		result.append({"mesh":node.mesh,"transform":transform,"material":surface})
	for child in node.get_children(): collect(child,transform,result)
static func get_parts(asset: String) -> Array:
	if not parts.has(asset):
		if asset=="impostor_wall":
			var proxy := get_parts("blank_wall").duplicate(true)
			for piece in proxy: piece.material=material("UrbanImpostor")
			parts[asset]=proxy
			return proxy
		var node: Node3D
		if asset.begins_with("living_"): node=LivingAssets.scene(asset.trim_prefix("living_"))
		elif asset.begins_with("reuse_"): node=CityAssets.create(asset.trim_prefix("reuse_"))
		elif CityKit.has_module(asset):
			# Blender city kit modules replace the original urban kit where they exist.
			node=CityKit.scene(asset).instantiate()
		else:
			var scene: PackedScene=load("res://world/downtown/assets/"+asset+".glb")
			node=scene.instantiate()
		var result: Array=[]
		collect(node,Transform3D.IDENTITY,result)
		if asset=="reuse_grass_clump":
			if not materials.has("CivicGrassBlade"):
				var blades := ShaderMaterial.new()
				blades.shader=preload("res://world/foliage.gdshader")
				blades.set_shader_parameter("grass",true)
				materials.CivicGrassBlade=blades
			for piece in result: piece.material=materials.CivicGrassBlade
		if asset in ["crosswalk_signal","crosswalk_signal_far"]:
			result=result.filter(func(piece: Dictionary) -> bool: return piece.material!=material("UrbanLight"))
		if asset in ["traffic_signal","traffic_signal_far"]:
			for piece in result:
				for i in range(3):
					var name: String=["UrbanSafety","UrbanLight","UrbanGreen"][i]
					if piece.material==material(name):
						var key := "Signal%d"%i
						if not materials.has(key):
							var light := ShaderMaterial.new()
							light.shader=preload("res://world/downtown/signal.gdshader")
							light.set_shader_parameter("lens",i)
							light.set_shader_parameter("color",Color(["e84836","edb93f","49be75"][i]))
							materials[key]=light
						piece.material=materials[key]
		node.free()
		parts[asset]=result
	return parts[asset]

