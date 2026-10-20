extends SceneTree
## G4 wheel assembly in the game world (Atatürk Avenue): face, three-quarter, night, LOD1.
## usage: godot --path . --script res://tests/capture_wheel.gd
const GLB := "res://world/vehicles/production/checkpoints/G4_wheel_v0.4/wheel_assembly.glb"
func _initialize() -> void: call_deferred("run")

func shoot(camera: Camera3D, at: Vector3, target: Vector3, file: String, frames: int = 30) -> void:
	camera.position = at
	camera.look_at(target)
	for i in range(frames): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://tmp/%s.png" % file)
	print("saved ", file)

## Imported PackedScene if the GLB has been imported, else the runtime glTF loader
## (see tests/wheel_import_test.gd for why the checkpoint GLB currently has no .import).
func load_wheel(path: String) -> Node3D:
	if ResourceLoader.exists(path, "PackedScene"):
		return (load(path) as PackedScene).instantiate()
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	assert(doc.append_from_file(path, state) == OK)
	return doc.generate_scene(state) as Node3D

func run() -> void:
	root.size = Vector2i(1280, 720)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	for name in ["Buses", "CityTraffic", "CityLife"]:
		var node: Node = world.get_node_or_null(name)
		if node != null:
			node.process_mode = Node.PROCESS_MODE_DISABLED
			node.visible = false
	var hub := Vector3(3.0, 0.33, -300)
	var model: Node3D = load_wheel(GLB)
	world.add_child(model)
	model.position = hub
	# Wheel face is +X in the asset; yaw 90 deg so it faces -Z (down the avenue, at the camera).
	model.rotation.y = PI / 2
	var pivot: Node3D = model.find_child("WheelPivot", true, false)
	var lod1: Node3D = model.find_child("WheelR_LOD1", true, false)
	var lod0: Node3D = model.find_child("WheelR", true, false)
	lod1.visible = false
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 45
	camera.position = hub + Vector3(0, 0, -1.6)
	camera.look_at(hub)
	# Spin the wheel for 60 frames (0.35 m rolling radius, ~2 m/s).
	for i in range(60):
		pivot.rotate_x(-(2.0 / 60.0) / 0.35)
		await process_frame
	await shoot(camera, hub + Vector3(0, 0, -1.6), hub, "wheel_godot_face")
	await shoot(camera, hub + Vector3(1.25, 0.42, -1.25), hub, "wheel_godot_34")
	# LOD1 from the same three-quarter view.
	lod0.visible = false
	lod1.visible = true
	lod1.position = Vector3.ZERO
	await shoot(camera, hub + Vector3(1.25, 0.42, -1.25), hub, "wheel_godot_lod1")
	lod1.visible = false
	lod0.visible = true
	world.set_time(21.0)
	await shoot(camera, hub + Vector3(0, 0, -1.6), hub, "wheel_godot_night", 40)
	print("WHEEL CAPTURE done")
	quit()
