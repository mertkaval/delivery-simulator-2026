extends SceneTree
## Godot check of the Road Studio v3 street-block export: loads the GLB + collision + props + signals
## GLBs and the street-model JSON, checks scale / materials / collision, toggles a signal lens
## (emission on the MRS_Lens_* material) and captures overhead + driver views.
## usage: godot --path . --script res://tests/capture_street_block.gd -- <export_dir> <out_dir>
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String, eye: Vector3, target: Vector3, fov: float) -> void:
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("block_%s.png" % name))
	print("CAPTURED ", name)

func load_glb(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		push_error("glb load failed: %s (%d)" % [path, err]); return null
	return doc.generate_scene(state) as Node3D

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var dir: String = args[0] if args.size() > 0 else "res://tmp/roads/v3/export"
	var out: String = args[1] if args.size() > 1 else "res://tmp/roads/v3"
	root.size = Vector2i(1600, 900)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("4f7fb8"); sky.sky_horizon_color = Color("b9cde0")
	env.sky.sky_material = sky
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ssao_enabled = true
	var we := WorldEnvironment.new(); we.environment = env; root.add_child(we)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-48, -30, 0); sun.shadow_enabled = true; root.add_child(sun)
	var ground := MeshInstance3D.new(); var pm := PlaneMesh.new(); pm.size = Vector2(800, 800); ground.mesh = pm; ground.position.y = -0.15
	var gm := StandardMaterial3D.new(); gm.albedo_color = Color("3d5a2a"); ground.material_override = gm; root.add_child(ground)
	var stats := {}
	for part in ["street_block.glb", "street_block_props.glb", "street_block_signals.glb"]:
		var node := load_glb(dir.path_join(part))
		if node == null: continue
		root.add_child(node)
		var aabb := AABB(); var first := true; var mats := {}; var tris := 0
		for mi in node.find_children("*", "MeshInstance3D", true, false):
			var m := mi as MeshInstance3D
			for s in m.mesh.get_surface_count():
				var mat := m.mesh.surface_get_material(s)
				if mat: mats[mat.resource_name.get_slice(".", 0)] = true
			tris += CityForgeWorld.triangles(m.mesh)
			var b := m.global_transform * m.get_aabb()
			aabb = b if first else aabb.merge(b); first = false
		stats[part] = {"meshes": node.find_children("*", "MeshInstance3D", true, false).size(), "tris": tris, "materials": mats.keys().size(), "size": aabb.size}
		print("BLOCK ", part, " ", stats[part])
	# collision
	var col := load_glb(dir.path_join("street_block_collision.glb"))
	var body := StaticBody3D.new(); var ctris := 0
	if col:
		for mi in col.find_children("*", "MeshInstance3D", true, false):
			var m := mi as MeshInstance3D
			var cs := CollisionShape3D.new(); cs.shape = m.mesh.create_trimesh_shape(); cs.transform = m.global_transform; body.add_child(cs)
			ctris += CityForgeWorld.triangles(m.mesh)
	root.add_child(body)
	await physics_frame; await physics_frame
	var hit := root.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-40, 20, 0), Vector3(-40, -5, 0)))
	print("BLOCK collision tris ", ctris, " ray on the avenue hits at y ", (hit.position as Vector3).y if not hit.is_empty() else "none")
	# metadata
	var f := FileAccess.open(dir.path_join("street_block.json"), FileAccess.READ)
	if f:
		var model: Dictionary = JSON.parse_string(f.get_as_text())
		var roads: Array = model.get("roads", []); var junctions: Array = model.get("junctions", [])
		var lanes := 0; var paths := 0
		for r in roads: lanes += (r["lanes"] as Array).size(); paths += (r["lane_paths"] as Array).size()
		var signals := 0
		for j in junctions: signals += (j["signals"] as Array).size()
		print("BLOCK json roads ", roads.size(), " junctions ", junctions.size(), " lanes ", lanes, " lane_paths ", paths, " signals ", signals, " phases ", junctions[0].get("signal_phases", []) if junctions.size() else [])
	# signal control: find a green lens material and switch its emission on/off
	var toggled := 0
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		for s in m.mesh.get_surface_count():
			var mat := m.mesh.surface_get_material(s) as StandardMaterial3D
			if mat and mat.resource_name.begins_with("MRS_Lens_Green"):
				mat.emission_enabled = true; mat.emission_energy_multiplier = 4.0; toggled += 1
	print("BLOCK signal lenses toggled ", toggled)
	camera = Camera3D.new(); camera.far = 3000.0; root.add_child(camera); camera.current = true
	await shot(out, "godot_over", Vector3(45, 180, 40), Vector3(45, 0, -5), 40.0)
	await shot(out, "godot_driver", Vector3(1.6, 1.3, 70), Vector3(1.6, 0.8, 10), 60.0)
	await shot(out, "godot_junction", Vector3(-25, 12, 30), Vector3(3, 0.5, -3), 45.0)
	quit()
