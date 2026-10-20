extends SceneTree
var checks := 0
var failures := 0
func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		printerr("FAIL: " + message)
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var models := HiggsfieldHousing.load_variants()
	check(models.size() == 12, "Twelve exterior combinations")
	var imported: Node3D = HiggsfieldHousing.SOURCE.instantiate()
	var kit := imported.find_child("HousingKit", true, false)
	check(kit != null and kit.get_child_count() >= 27, "Expanded editable module library survives export")
	imported.free()
	for i in range(models.size()):
		var house := models[i].instantiate()
		var meshes := house.find_children("*", "MeshInstance3D", true, false)
		check(meshes.size() == 1, "Batched exterior %d" % i)
		check(house.find_children("*", "Light3D", true, false).is_empty(), "No imported studio lights %d" % i)
		check(house.find_children("*", "Camera3D", true, false).is_empty(), "No imported cameras %d" % i)
		var mesh: MeshInstance3D = meshes[0]
		var bounds: AABB = mesh.transform * mesh.get_aabb()
		check(bounds.position.x > -6 and bounds.end.x < 6, "Fits lot width %d" % i)
		check(bounds.position.y > -.15 and bounds.end.y < 9, "Correct height %d" % i)
		check(bounds.position.z > -8 and bounds.end.z < 4, "Correct front and back %d" % i)
		var triangles := 0
		for surface in range(mesh.mesh.get_surface_count()):
			triangles += mesh.mesh.surface_get_array_index_len(surface) / 3
		check(triangles < 60000, "No accumulated source geometry %d: %d" % [i, triangles])
		HiggsfieldHousing.finish(house, i % 6)
		var window_roles := {}
		for surface in range(mesh.mesh.get_surface_count()):
			var window_material: Material = mesh.mesh.surface_get_material(surface)
			window_roles[str(window_material.resource_name)] = window_material
		check(window_roles.has("HK_WindowPrivacy") and window_roles.has("HK_WindowEnamel") and window_roles.has("HK_WindowSeal"), "Layered privacy window %d" % i)
		if window_roles.has("HK_WindowPrivacy"):
			check(window_roles["HK_WindowPrivacy"].albedo_texture != null, "Linen texture exported %d" % i)
		if window_roles.has("HK_Glass"):
			check(window_roles["HK_Glass"].albedo_color.a < .5, "Glass transmits privacy backing %d" % i)
		check(mesh.get_surface_override_material(0) != null, "Palette applied %d" % i)
		for surface in range(mesh.mesh.get_surface_count()):
			var mat: Material = mesh.mesh.surface_get_material(surface)
			if mat is StandardMaterial3D and str(mat.resource_name) in ["HK_Brick", "HK_StuccoTint", "HK_SidingTint"]:
				check(mat.albedo_texture != null and mat.albedo_texture.get_width() == 2048, "2K facade texture %d" % i)
				check(mat.normal_texture != null and mat.roughness_texture != null, "PBR normal and roughness %d" % i)
		if i % 4 in [0,3]:
			var parts := HiggsfieldHousing.collision_parts(i)
			check(parts.size() == 2 and parts[1].end.z < 1, "Recessed wing has matching collision %d" % i)
		house.free()
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	game.player.set_physics_process(false)
	await physics_frame
	# The street now uses the city-kit houses; the Higgsfield library stays available as an asset.
	for i in range(36):
		var door: Vector3 = game.world.doors[i]
		var facing: Vector3 = CityCatalog.address_facing(i)
		game.player.position = door + facing * 1.6 + Vector3(0, -.92, 0)
		game.player.rotation = Vector3(0, atan2(facing.x, facing.z), 0)
		game.player.camera.rotation = Vector3(-.2,0,0)
		await physics_frame
		check(game.player.target().get("id") == "door_%d" % i, "Door interaction %d" % i)
		var ray := PhysicsRayQueryParameters3D.create(door + facing * 2.0, door - facing * 2.0, 1)
		check(not game.world.get_world_3d().direct_space_state.intersect_ray(ray).is_empty(), "Closed exterior %d" % i)
	print("HIGGSFIELD HOUSING: %d checks, %d failures" % [checks, failures])
	quit(failures)
