extends SceneTree
## Mert Road Studio export in Godot: loads assets/roads/mrs_demo.glb (visual) and
## mrs_demo_collision.glb (collision), maps the MRS_* materials to the game's, checks the scale and
## the collision (a ray onto the avenue), and captures an overhead and a street-level view.
## usage: godot --path . --script res://tests/capture_roads.gd -- <out_dir>
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String, eye: Vector3, target: Vector3, fov: float) -> void:
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("roads_%s.png" % name))
	print("CAPTURED ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	root.size = Vector2i(1600, 900)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("4f7fb8")
	sky.sky_horizon_color = Color("b9cde0")
	env.sky.sky_material = sky
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -30, 0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(800, 800)
	ground.mesh = pm
	ground.position.y = -0.03
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color("3d5a2a")
	ground.material_override = gm
	root.add_child(ground)
	var visual := (load("res://assets/roads/mrs_demo.glb") as PackedScene).instantiate() as Node3D
	root.add_child(visual)
	var aabb := AABB()
	var first := true
	var mats := {}
	for node in visual.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s)
			if m: mats[m.resource_name.get_slice(".", 0)] = true
		CityForgeMaterials.apply(mi.mesh)
		var b := mi.global_transform * mi.get_aabb()
		aabb = b if first else aabb.merge(b)
		first = false
	print("ROADS visual size ", aabb.size, " materials ", mats.keys(), " surfaces ", visual.find_children("*", "MeshInstance3D", true, false).size())
	var col := (load("res://assets/roads/mrs_demo_collision.glb") as PackedScene).instantiate() as Node3D
	var body := StaticBody3D.new()
	var tris := 0
	for node in col.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var cs := CollisionShape3D.new()
		cs.shape = mi.mesh.create_trimesh_shape()
		cs.transform = mi.global_transform
		body.add_child(cs)
		tris += CityForgeWorld.triangles(mi.mesh)
	root.add_child(body)
	await physics_frame
	await physics_frame
	var hit := root.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-60, 20, 0), Vector3(-60, -5, 0)))
	print("ROADS collision tris ", tris, " ray on the avenue hits at y ", (hit.position as Vector3).y if not hit.is_empty() else "none")
	camera = Camera3D.new()
	camera.far = 3000.0
	root.add_child(camera)
	camera.current = true
	await shot(out, "overhead", Vector3(30, 200, 10), Vector3(30, 0, -10), 50.0)
	await shot(out, "street", Vector3(-40, 1.7, 2.5), Vector3(-5, 1.2, -0.5), 60.0)
	await shot(out, "junction", Vector3(-26, 2.2, 10), Vector3(2, 0.8, -2), 55.0)
	quit()
