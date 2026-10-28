extends SceneTree
## The baked prototype house (assets/cityforge/prototypes/<name>.glb) on its Port Halden lot, in the
## game's own lighting, next to the catalogue neighbours: street view, entrance, facade and roof edge.
## usage: godot --path . --script res://tests/capture_prototype.gd -- <out_dir> [H_name]
var world: CedarNeighborhood
var w: CityForgeWorld
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String, eye: Vector3, target: Vector3, fov: float) -> void:
	w.update_focus(eye, 10.0)
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 10: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("godot_%s.png" % name))
	print("CAPTURED ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var kit_name: String = args[1] if args.size() > 1 else "H_eur_casa_2"
	root.size = Vector2i(1600, 900)
	CedarNeighborhood.city_override = "port_halden"
	world = CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(10.5)
	w = world.port
	camera = Camera3D.new()
	camera.far = 5000.0
	root.add_child(camera)
	camera.current = true
	# the first house of this type in the city: the prototype replaces it
	var target: Dictionary = {}
	for hs: Dictionary in w.city.houses:
		if str(hs.get("kit", "")) == kit_name:
			target = hs
			break
	if target.is_empty():
		print("NO HOUSE OF TYPE ", kit_name)
		quit(1)
		return
	var pos := w.to_world(float((target.pos as Array)[0]), float((target.pos as Array)[1]), float(target.h))
	var yaw := float(target.yaw)
	# hide the instanced copy (scale it to nothing) and put the baked GLB in its place
	for node in w.find_children("*", "MultiMeshInstance3D", true, false):
		var mmi := node as MultiMeshInstance3D
		if not str(mmi.name).begins_with(kit_name + "_"): continue
		var mm := mmi.multimesh
		for i in mm.instance_count:
			if mm.get_instance_transform(i).origin.distance_to(pos) < 0.2:
				mm.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), pos))
	var path := "res://assets/cityforge/prototypes/%s.glb" % kit_name
	var scene := load(path) as PackedScene
	var proto := scene.instantiate() as Node3D
	proto.transform = Transform3D(Basis(Vector3.UP, yaw), pos)
	w.add_child(proto)
	var mats := 0
	for node in proto.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if m: mats += 1
	print("PROTOTYPE ", kit_name, " at ", pos, " materials ", mats)
	var front := Vector3(0, 0, -1).rotated(Vector3.UP, yaw)
	var right := Vector3(1, 0, 0).rotated(Vector3.UP, yaw)
	var ground := w.ground_height(pos + front * 12.0)
	await shot(out, "1_street", pos + front * 13.0 + right * -7.0 + Vector3(0, ground - pos.y + 1.7, 0), pos + Vector3(0, 4.5, 0), 55.0)
	await shot(out, "2_entrance", pos + front * 9.0 + right * -2.0 + Vector3(0, 1.6, 0), pos + front * 5.0 + Vector3(0, 1.6, 0), 45.0)
	await shot(out, "3_window", pos + front * 8.0 + right * 3.5 + Vector3(0, 4.4, 0), pos + front * 5.0 + right * 2.3 + Vector3(0, 4.6, 0), 50.0)
	await shot(out, "4_roof_edge", pos + front * 9.5 + right * -7.5 + Vector3(0, 11.5, 0), pos + front * 4.5 + right * -3.5 + Vector3(0, 9.6, 0), 45.0)
	quit()
