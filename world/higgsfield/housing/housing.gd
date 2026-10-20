class_name HiggsfieldHousing
extends RefCounted
## Preassembled exterior combinations of the editable Higgsfield modular kit.
const SOURCE = preload("res://world/higgsfield/housing/modular_housing.glb")
const WIDTHS = [8.0, 9.0, 10.0, 8.6]
const DEPTHS = [6.4, 8.0, 7.2]
const PALETTES = ["9ead9a", "d3bfa0", "8fa6b3", "c7c4b4", "a1aaa9", "b99d88"]
const DOORS = ["243e3d", "644133", "354956", "6a5638", "314d43", "633b36"]
static var variants: Array[PackedScene] = []
static var materials: Dictionary = {}

static func load_variants() -> Array[PackedScene]:
	if not variants.is_empty(): return variants
	var imported: Node3D = SOURCE.instantiate()
	for i in range(12):
		var source: Node3D = imported.find_child("Example_Home_%02d" % i, true, false)
		assert(source != null, "Higgsfield house variant missing: %d" % i)
		var house := Node3D.new()
		house.name = "HiggsfieldResidence"
		house.set_meta("higgsfield_variant", i)
		house.set_meta("asset_source", "Higgsfield 3D Jutsu modular housing")
		for child in source.get_children():
			if child is MeshInstance3D:
				var part := MeshInstance3D.new()
				part.name = "Exterior"
				part.mesh = child.mesh
				# Source front is Z=0. Existing delivery doors stay at Z=1.3.
				part.transform = child.transform
				part.position.z += 1.0
				part.visibility_range_end = 600.0
				part.visibility_range_end_margin = 24.0
				house.add_child(part)
				part.owner = house
		var packed := PackedScene.new()
		assert(packed.pack(house) == OK)
		variants.append(packed)
		house.free()
	imported.free()
	return variants

static func variant_for(index: int, active: bool) -> int:
	return posmod(index * 5 + (0 if active else 7), 12)

static func dimensions(variant: int) -> Vector3:
	return Vector3(WIDTHS[variant % 4], [3.04, 5.35, 5.84, 5.84][variant % 4], DEPTHS[variant % 3])

static func collision_parts(variant: int) -> Array[AABB]:
	var size := dimensions(variant)
	var family := variant % 4
	var result: Array[AABB] = []
	if family in [0,3]:
		var split := size.x * (.16 if family == 0 else .15)
		var recess := 1.2 if family == 0 else .65
		var low_height := 2.72 if family == 0 else 3.04
		result.append(AABB(Vector3(-size.x*.5,0,1-size.z),Vector3(split+size.x*.5,size.y,size.z)))
		result.append(AABB(Vector3(split,0,1-size.z),Vector3(size.x*.5-split,low_height,size.z-recess)))
	else:
		result.append(AABB(Vector3(-size.x*.5,0,1-size.z),size))
		if family == 1:
			result.append(AABB(Vector3(-size.x*.29-.96,0,.98),Vector3(1.92,2.62,.76)))
	return result

static func finish(house: Node3D, palette: int) -> void:
	palette = posmod(palette, PALETTES.size())
	house.set_meta("higgsfield_palette", palette)
	for mesh in house.find_children("*", "MeshInstance3D", true, false):
		for surface in range(mesh.mesh.get_surface_count()):
			var base: Material = mesh.mesh.surface_get_material(surface)
			if not base is StandardMaterial3D: continue
			var key := "%d:%d" % [base.get_instance_id(), palette]
			if not materials.has(key):
				var material := base.duplicate() as StandardMaterial3D
				var label := str(base.resource_name)
				if label in ["HK_SidingTint", "HK_StuccoTint"]:
					material.albedo_color = Color(PALETTES[palette])
				elif label == "HK_DoorTint": material.albedo_color = Color(DOORS[palette])
				elif label == "HK_Brick": material.albedo_color = Color("c9b9a9") if palette % 2 else Color.WHITE
				elif label == "HK_SlateRoof": material.albedo_color = Color("a5adb0") if palette % 3 else Color("a69b90")
				material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
				materials[key] = material
			mesh.set_surface_override_material(surface, materials[key])

static func set_daylight(amount: float) -> void:
	for key in materials:
		var material: StandardMaterial3D = materials[key]
		if str(material.resource_name) == "HK_WindowPrivacy":
			var occupied := int(str(key).get_slice(":", 1)) % 3 != 0
			material.emission_enabled = occupied
			material.emission = Color("e7bc7b")
			material.emission_energy_multiplier = (1.0 - amount) * .45 if occupied else 0.0
