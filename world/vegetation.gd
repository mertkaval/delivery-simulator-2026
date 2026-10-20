extends Node3D
## Chunked, deterministic grass. Only nearby chunks render; no blade collision.
var clump_count := 0
var patches := 0
var estate: Array[PackedVector3Array] = CityCatalog.estate_roads()

func _ready() -> void:
	var source := CityAssets.create("grass_clump")
	var mesh_node: MeshInstance3D = source.find_children("*", "MeshInstance3D", true, false)[0]
	var clump: Mesh = mesh_node.mesh
	var surface := ShaderMaterial.new()
	surface.shader = preload("res://world/foliage.gdshader")
	surface.set_shader_parameter("grass", true)
	var rng := RandomNumberGenerator.new()
	rng.seed = 45199
	for x in range(-112, 113, 16):
		for z in range(-696, 57, 16):
			var transforms: Array[Transform3D] = []
			for i in range(640):
				var at := Vector3(x + rng.randf_range(-8, 8), 0.015, z + rng.randf_range(-8, 8))
				if not permitted(at): continue
				var scale_factor := rng.randf_range(0.7, 1.5)
				transforms.append(Transform3D(Basis(Vector3.UP, rng.randf_range(0, TAU)).scaled(Vector3.ONE * scale_factor), at - Vector3(x, 0, z)))
			if transforms.is_empty(): continue
			var batch := MultiMesh.new()
			batch.transform_format = MultiMesh.TRANSFORM_3D
			batch.mesh = clump
			batch.instance_count = transforms.size()
			for i in range(transforms.size()): batch.set_instance_transform(i, transforms[i])
			var node := MultiMeshInstance3D.new()
			node.multimesh = batch
			node.material_override = surface
			node.position = Vector3(x, 0, z)
			node.visibility_range_end = 48
			node.visibility_range_end_margin = 8
			node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(node)
			clump_count += transforms.size()
			patches += 1
	source.free()

func permitted(p: Vector3) -> bool:
	if absf(p.x) < 11 or absf(p.x) > 116: return false
	if CityLayout.blocked(p): return false
	if p.x>64:
		for crossing in DowntownCatalog.STREET_Z:
			if absf(p.z-crossing)<11.5: return false
	if p.z > -266:
		for path in estate:
			for i in range(1,path.size()):
				if Geometry3D.get_closest_point_to_segment(p,path[i-1],path[i]).distance_to(p) < 6.8: return false
		for at in ShopCatalog.LOCATIONS.values()+[Vector3(-40,0,32)]:
			if absf(p.x-at.x)<8.5 and p.z>at.z-5.5 and p.z<at.z+14: return false
	if p.z < -247 and p.z > -690:
		if absf(absf(p.x) - 64) < 10: return false
		for z in CityCatalog.CROSS_STREETS:
			if absf(p.z - z) < 10 and absf(p.x) < 74: return false
	# Houses, porches and rear lanes are excluded through CityLayout.blocked().
	for counter in CityCatalog.PICKUPS:
		if p.x > counter.x - 11 and p.x < counter.x + 3 and p.z > counter.z - 9 and p.z < counter.z + 6: return false
	if p.x > 10 and p.x < 27 and p.z > 20 and p.z < 43: return false
	if p.x > 10 and p.x < 16 and p.z > 15 and p.z < 19: return false
	for z in [-110, -190]:
		for x in [-92, 92]:
			if absf(p.x-x)<9.5 and p.z>z-8 and p.z<z+15: return false
	if absf(absf(p.x)-64)<11 and absf(p.z+145)<18: return false
	for z in [-330, -470, -590]:
		if absf(absf(p.x) - 44) < 11 and absf(p.z - z) < 18:
			if absf(absf(p.x) - 44) < 1.7 or absf(p.z - z) < 1.6: return false
			var oval := Vector2((absf(p.x) - 44) / 9.0, (p.z - z) / 14.0).length()
			if oval > 0.84 and oval < 1.04: return false
			if Vector2(absf(p.x) - 48, p.z - z + 5).length() < 2: return false
	return true
