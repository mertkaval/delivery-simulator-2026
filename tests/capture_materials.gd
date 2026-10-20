extends SceneTree
## G6 vehicle material study: one column (sphere / curved panel / cube) per VehicleMaterials name,
## on Ataturk Avenue at (3, 0, -300), under day, golden hour, night, rain, and day + ReflectionProbe.
## Prints the mean sRGB of each sphere so metals can be compared numerically.
## usage: godot --path . --script res://tests/capture_materials.gd
func _initialize() -> void: call_deferred("run")

const ORIGIN := Vector3(3.0, 0.0, -300.0)
const SPACING := 0.78
const PER_ROW := 16
const ROW_DEPTH := 1.6
var spheres: Dictionary = {}
var camera: Camera3D
var world: CedarNeighborhood

func column(parent: Node3D, name: String, at: Vector3) -> void:
	var m: Material = VehicleMaterials.material(name)
	assert(m != null, "no material for " + name)
	var sphere := MeshInstance3D.new()
	var sphere_mesh := SphereMesh.new()
	sphere_mesh.radius = 0.25
	sphere_mesh.height = 0.5
	sphere_mesh.radial_segments = 48
	sphere_mesh.rings = 24
	sphere.mesh = sphere_mesh
	sphere.material_override = m
	sphere.position = at + Vector3(0, 1.05, 0)
	parent.add_child(sphere)
	spheres[name] = sphere
	var panel := MeshInstance3D.new()
	var panel_mesh := CylinderMesh.new()
	panel_mesh.top_radius = 0.3
	panel_mesh.bottom_radius = 0.3
	panel_mesh.height = 0.4
	panel_mesh.radial_segments = 48
	panel.mesh = panel_mesh
	panel.material_override = m
	panel.position = at + Vector3(0, 0.5, 0)
	parent.add_child(panel)
	var cube := MeshInstance3D.new()
	var cube_mesh := BoxMesh.new()
	cube_mesh.size = Vector3(0.1, 0.1, 0.1)
	cube.mesh = cube_mesh
	cube.material_override = m
	cube.position = at + Vector3(0, 0.15, 0)
	cube.rotation.y = 0.6
	parent.add_child(cube)
	var label := Label3D.new()
	label.text = name
	label.font_size = 36
	label.pixel_size = 0.004
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = at + Vector3(0, 1.5 if (int(at.x / SPACING * 2.0) % 2 == 0) else 1.75, 0)
	label.outline_size = 8
	parent.add_child(label)

func shoot(at: Vector3, target: Vector3, file: String, frames: int = 40) -> void:
	camera.position = at
	camera.look_at(target)
	for i in range(frames): await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.save_png("res://tmp/%s.png" % file)
	print("saved ", file)
	# Mean sRGB over a 9x9 window at each sphere centre (upper-left quadrant, so it includes the sun side).
	var line := "  spheres:"
	for name in VehicleMaterials.NAMES:
		var sphere: MeshInstance3D = spheres[name]
		var centre: Vector2 = camera.unproject_position(sphere.global_position + Vector3(0, 0.08, 0))
		var sum := Color(0, 0, 0)
		var count := 0
		for dx in range(-4, 5):
			for dy in range(-4, 5):
				var px := Vector2i(int(centre.x) + dx, int(centre.y) + dy)
				if px.x < 0 or px.y < 0 or px.x >= image.get_width() or px.y >= image.get_height(): continue
				sum += image.get_pixelv(px)
				count += 1
		if count > 0: sum = sum / float(count)
		line += " %s(%d,%d,%d)" % [name, int(sum.r8), int(sum.g8), int(sum.b8)]
	print(line)

func night_amount() -> float:
	return 1.0 - clampf(world.daylight.light_energy / 1.6, 0.0, 1.0)

func run() -> void:
	root.size = Vector2i(1280, 720)
	world = CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(15.5)
	for name in ["Buses", "CityTraffic", "CityLife"]:
		var node: Node = world.get_node_or_null(name)
		if node != null:
			node.process_mode = Node.PROCESS_MODE_DISABLED
			node.visible = false
	world.weather.forced = 0.0
	var rig := Node3D.new()
	world.add_child(rig)
	rig.position = ORIGIN
	var names: Array[String] = VehicleMaterials.NAMES
	for i in range(names.size()):
		var row := i / PER_ROW
		var col := i % PER_ROW
		var x := (col - (PER_ROW - 1) * 0.5) * SPACING
		column(rig, names[i], Vector3(x, 0, -row * ROW_DEPTH))
	camera = Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 45
	# Front row at z=0, back row at z=-1.6 (further down the avenue). Camera on the +z side looking -z.
	var centre := ORIGIN + Vector3(0, 0.8, 0.0)
	var wide := ORIGIN + Vector3(0, 2.4, 10.0)
	var passes: Array = [[15.5, "day"], [17.8, "golden"], [21.5, "night"]]
	for p in passes:
		var hour: float = p[0]
		var tag: String = p[1]
		world.set_time(hour)
		VehicleMaterials.set_night(night_amount())
		print(tag, " hour ", hour, " night ", night_amount(), " sun energy ", world.daylight.light_energy)
		await shoot(wide, centre, "materials_%s" % tag)
	# Close view (about 3 m) of the metals group: Chrome, Alloy, RimWell, SteelDisc, VehiclePaint at day.
	world.set_time(15.5)
	VehicleMaterials.set_night(night_amount())
	var metals_centre := ORIGIN + Vector3(-1.9, 0.8, 0.0)
	await shoot(ORIGIN + Vector3(-1.7, 1.5, 3.0), metals_centre, "materials_day_close")
	# Rain, day.
	world.weather.forced = 1.0
	for i in range(3): await process_frame
	world.set_time(15.5)
	VehicleMaterials.set_wet(world.weather.wetness)
	print("rain wetness ", world.weather.wetness)
	await shoot(wide, centre, "materials_rain")
	VehicleMaterials.set_wet(0.0)
	world.weather.forced = 0.0
	# Let the rain particles die and the fog settle before the probe snapshots the scene.
	for i in range(150): await process_frame
	world.set_time(15.5)
	# ReflectionProbe around the row: what local reflections buy versus sky-only.
	var probe := ReflectionProbe.new()
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.size = Vector3(14, 4, 8)
	probe.box_projection = true
	probe.intensity = 1.0
	probe.position = Vector3(0, 1.9, 0.0)
	probe.origin_offset = Vector3.ZERO
	rig.add_child(probe)
	await shoot(wide, centre, "materials_day_probe", 60)
	await shoot(ORIGIN + Vector3(-1.7, 1.5, 3.0), metals_centre, "materials_day_probe_close", 20)
	world.set_time(21.5)
	VehicleMaterials.set_night(night_amount())
	# UPDATE_ONCE keeps the daytime capture: re-trigger the probe after the time change.
	probe.update_mode = ReflectionProbe.UPDATE_ALWAYS
	await process_frame
	await process_frame
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	await shoot(wide, centre, "materials_night_probe", 60)
	print("MATERIALS CAPTURE done")
	quit()
