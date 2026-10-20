class_name CityMaterials
extends RefCounted
static var cache: Dictionary = {}

static func get_surface(color: String) -> ShaderMaterial:
	if cache.has(color): return cache[color]
	var kind := 0
	if color == "3a4249": kind = 1
	elif color in ["bdc2b8", "d7d6cb", "c1bbaa", "737773", "818c89"]: kind = 2
	elif color in ["859b93", "b6a287", "8298a7", "af9281", "8c9d86", "b8b3a2", "355d59"]: kind = 3
	elif color in ["b98a5c", "9c8060", "9c7c5e", "6d5b49", "d9c6a7", "c5b494"]: kind = 4
	elif color in ["806753", "8a8277", "875247"]: kind = 5
	elif color in ["485257", "434c51"]: kind = 6
	elif color in ["567b8b", "3c5663"]: kind = 7
	elif color in ["384950", "394a50", "344448", "cab787"]: kind = 8
	elif color in ["66765e", "496953", "405d45", "526b48", "607852", "536b45"]: kind = 9
	var material := ShaderMaterial.new()
	material.shader = preload("res://world/surface.gdshader")
	material.set_shader_parameter("tint", Color(color))
	material.set_shader_parameter("surface_kind", kind)
	cache[color] = material
	return material
