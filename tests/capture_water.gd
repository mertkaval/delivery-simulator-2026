extends SceneTree
## Port Halden's water (sea, harbour, inlet, lake, river) under the game's own sky, fog and sun
## (CedarNeighborhood.build_sky + set_time), rendered from street level, from the air and at night.
## usage: godot --path . --script res://tests/capture_water.gd -- <out_dir> [prefix] [view ...]
##   writes <out_dir>/<prefix>_<view>.png (prefix defaults to "water")
var world: CityForgeWorld
var camera: Camera3D
var sky: CedarNeighborhood

func _initialize() -> void: call_deferred("run")

## A camera at plan (x, y) `up` metres over the ground (or the water), looking at plan (tx, ty) at height th.
func shot(out: String, name: String, eye_plan: Vector2, up: float, at_plan: Vector2, th: float, fov: float = 60.0) -> void:
	var eye := world.to_world(eye_plan.x, eye_plan.y)
	eye.y = maxf(world.ground_height(eye), 0.0) + up
	var at := world.to_world(at_plan.x, at_plan.y, th)
	world.update_focus(eye, 10.0)
	camera.position = eye
	camera.fov = fov
	camera.look_at(at)
	for i in 30: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("%s.png" % name))
	print("CAPTURED ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp/water"
	var prefix: String = args[1] if args.size() > 1 else "water"
	var views: Array = Array(args.slice(2)) if args.size() > 2 else ["harbour_street", "sea_aerial", "sea_glint", "inlet",
		"lake_shore", "lake_closeup", "river", "river_aerial", "river_bridge", "sea_sunset", "night_harbour", "night_lake"]
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out) if out.begins_with("res://") else out)
	root.size = Vector2i(1600, 900)
	# The game's sky, fog, tonemapping and sun (neighborhood.gd build_sky), without building its city.
	sky = CedarNeighborhood.new()
	sky.build_sky()
	for c in sky.get_children():
		sky.remove_child(c)
		root.add_child(c)
	world = CityForgeWorld.new()
	root.add_child(world)
	sky.port = world
	camera = Camera3D.new()
	camera.far = 5000.0
	camera.near = 0.1
	root.add_child(camera)
	camera.current = true
	sky.set_time(10.5)
	print("WATER_CAPTURE ", world.stats)
	for v: String in views:
		var n := prefix + "_" + v
		match v:
			# north beach (plan x 1000, y ~1900) looking out to sea, the sun ahead
			"harbour_street": await shot(out, n, Vector2(1000, 1898), 1.7, Vector2(985, 2010), 0.0, 62)
			"sea_aerial": await shot(out, n, Vector2(1000, 1840), 60.0, Vector2(900, 1990), 0.0, 58)
			"sea_glint": await shot(out, n, Vector2(760, 1915), 6.0, Vector2(700, 2300), 4.0, 60)
			# the inlet (plan y 1316-1394) from its south bank
			"inlet": await shot(out, n, Vector2(300, 1300), 2.5, Vector2(360, 1370), -1.0, 62)
			# the lake (level 8.86) from its north shore, and a close look down at the shore
			"lake_shore": await shot(out, n, Vector2(1586, 1172), 2.0, Vector2(1570, 1040), 8.0, 62)
			"lake_closeup": await shot(out, n, Vector2(1586, 1168), 2.6, Vector2(1586, 1146), 8.86, 62)
			# the river (plan y 252-306, surface 0.8-5.8 m) from its south bank, and from above
			"river": await shot(out, n, Vector2(1000, 232), 1.7, Vector2(1090, 285), 1.5, 62)
			"river_aerial": await shot(out, n, Vector2(940, 180), 45.0, Vector2(1040, 290), 0.0, 58)
			"river_bridge": await shot(out, n, Vector2(960, 236), 9.0, Vector2(1010, 275), 1.5, 60)
			# where the river (surface ~0.8 m) meets the west sea
			"river_mouth": await shot(out, n, Vector2(190, 190), 14.0, Vector2(95, 240), 0.0, 60)
			# the downtown plaza fountain (a 5 cm sheet of water on its stone basin)
			"fountain":
				var f := world.to_world(495.75, 1650.18)
				await shot(out, n, Vector2(495.75 - 7.0, 1650.18 - 7.0), 3.2, Vector2(495.75, 1650.18), world.ground_height(f) + 0.8, 60)
			# low western sun over the west sea: the glitter path
			"sea_sunset":
				sky.set_time(17.2)
				await shot(out, n, Vector2(132, 1000), 5.0, Vector2(-300, 1010), -20.0, 62)
				sky.set_time(10.5)
			"night_harbour", "night_lake":
				sky.set_time(22.5)
				if v == "night_harbour": await shot(out, n, Vector2(1000, 1898), 1.7, Vector2(985, 2010), 0.0, 62)
				else: await shot(out, n, Vector2(1586, 1172), 2.0, Vector2(1570, 1040), 8.0, 62)
				sky.set_time(10.5)
	sky.free()
	quit()
