extends SceneTree
## Port Halden (CityForge) views rendered by the game: aerial, residential street, downtown,
## harbour, lake, and the same street at night.
## usage: godot --path . --script res://tests/capture_cityforge.gd -- <out_dir> [view ...]
var world: CityForgeWorld
var camera: Camera3D
var sun: DirectionalLight3D
var env: Environment

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String, eye: Vector3, target: Vector3, fov: float = 50.0) -> void:
	world.update_focus(eye, 10.0)
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 12: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("cf_%s.png" % name))
	print("CAPTURED ", name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var views: Array = Array(args.slice(1)) if args.size() > 1 else ["aerial", "street", "downtown", "harbour", "lake", "night"]
	root.size = Vector2i(1600, 900)
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("4f7fb8")
	sky.sky_horizon_color = Color("b9cde0")
	env.sky.sky_material = sky
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.fog_enabled = true
	env.fog_density = 0.0007
	env.fog_light_color = Color("b9cde0")
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 400.0
	root.add_child(sun)
	world = CityForgeWorld.new()
	root.add_child(world)
	camera = Camera3D.new()
	camera.far = 5000.0
	root.add_child(camera)
	camera.current = true
	print("CITYFORGE ", world.stats)
	var w := world
	# a residential avenue (1300 m north) between Douglas and Elm streets, looking east
	var street_a := w.to_world(1046, 1306)
	street_a.y = w.ground_height(street_a) + 1.7
	var street_b := w.to_world(1150, 1300)
	street_b.y = w.ground_height(street_b) + 2.0
	for v: String in views:
		match v:
			"aerial":
				env.fog_density = 0.00012
				await shot(out, v, w.to_world(1024, -350, 900), w.to_world(1024, 1100, 0), 50)
				env.fog_density = 0.0007
			"map":
				env.fog_enabled = false
				await shot(out, v, w.to_world(1024, 1000, 3400), w.to_world(1024, 1024, 0), 50)
				env.fog_enabled = true
			"street": await shot(out, v, street_a, street_b, 60)
			"downtown":
				var e := w.to_world(960, 1330, 0)
				e.y = w.ground_height(e) + 90
				await shot(out, v, e, w.to_world(560, 1650, 40), 55)
			"harbour": await shot(out, v, w.to_world(1150, 2040, 45), w.to_world(650, 1700, 20), 55)
			"lake":
				var e2 := w.to_world(1420, 840, 0)
				e2.y = w.ground_height(e2) + 40
				await shot(out, v, e2, w.to_world(1600, 1020, 10), 55)
			"corner":
				var c := w.to_world(1010, 1215, 0)
				c.y = w.ground_height(c) + 6
				await shot(out, v, c, w.to_world(1000, 1200, 0) + Vector3(0, w.ground_height(w.to_world(1000, 1200)) , 0), 60)
			"junction", "junction_close", "sidewalk", "busstop":
				# street-level views of the Mert Road Studio streets (assets/cityforge/mrs): the signalised junction
				# nearest the starter neighbourhood, its corner, a sidewalk next to a tree, a bus stop
				if w.mrs == null: continue
				var md: Dictionary = w.mrs.data
				var near := w.to_world(1100, 1300)
				var best: Vector3 = near
				var bd := INF
				for j: Dictionary in md.get("junctions", []):
					var p := MrsCityStreets.g(j.at as Array)
					if p.distance_to(near) < bd:
						bd = p.distance_to(near)
						best = p
				if v == "junction": await shot(out, v, best + Vector3(-26, 14, 30), best, 55)
				elif v == "junction_close": await shot(out, v, best + Vector3(-13, 1.7, 9), best + Vector3(4, 1.0, -6), 62)
				elif v == "sidewalk":
					var t0 := best
					for t: Dictionary in md.get("trees", []):
						var q := MrsCityStreets.g(t.pos as Array)
						if q.distance_to(near) < 220.0 and q.distance_to(best) > 40.0:
							t0 = q
							break
					await shot(out, v, t0 + Vector3(3.5, 1.7, 9.0), t0 + Vector3(-1.0, 1.4, -6.0), 62)
				else:
					var stops: Array = (md.get("instances", {}) as Dictionary).get("MRS_F_BusShelter", [])
					if stops.is_empty(): continue
					var bs: Array = stops[0]
					for r: Array in stops:
						if MrsCityStreets.g(r).distance_to(near) < MrsCityStreets.g(bs).distance_to(near): bs = r
					var q2 := MrsCityStreets.g(bs)
					var fwd := Vector3(0, 0, -1).rotated(Vector3.UP, float(bs[3]))
					await shot(out, v, q2 + fwd * 9.0 + fwd.cross(Vector3.UP) * 6.0 + Vector3(0, 1.8, 0), q2 + Vector3(0, 1.2, 0), 60)
			"night":
				sun.light_energy = 0.05
				env.background_energy_multiplier = 0.05
				env.ambient_light_energy = 0.15
				world.set_night(1.0)
				await shot(out, v, street_a, street_b, 60)
				var e3 := w.to_world(960, 1330, 0)
				e3.y = w.ground_height(e3) + 90
				await shot(out, "night_downtown", e3, w.to_world(560, 1650, 40), 55)
	quit()
