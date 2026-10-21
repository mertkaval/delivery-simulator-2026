extends SceneTree
## Native captures of the streets (run WITHOUT --headless). The street kit views (lane
## markings, bike lanes, junctions, crossings) and the street-life pass: a signalised junction
## with cars queued on red, a pedestrian signal, the signals at night, LED boards on a shop and
## a restaurant (two frames each, the text scrolls), exhaust puffs, brake lights, grill smoke
## and wet-road spray.
## Output directory: user arg after "--" (default res://tmp/), files streets_<view>.png.
## A second user arg "kit" captures only the street kit views, "life" only the street-life ones.
var out_dir := "res://tmp/"
var world: CedarNeighborhood
var camera: Camera3D

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty(): out_dir = args[0].trim_suffix("/") + "/"
	call_deferred("run")

func shot(name: String, frames := 40) -> void:
	for i in range(frames): await process_frame
	await RenderingServer.frame_post_draw
	var path := out_dir + "streets_" + name + ".png"
	root.get_texture().get_image().save_png(path)
	print("SAVED ", ProjectSettings.globalize_path(path))

func view(from: Vector3, to: Vector3, fov := 60.0) -> void:
	camera.position = from
	if to == Vector3.ZERO: camera.rotation_degrees = Vector3(-90, 0, 0)
	else: camera.look_at(to)
	camera.fov = fov

## The last car queued on the northbound avenue lane (x -1.95) behind the stop line at z_stop.
func queue_tail(traffic: Node, z_stop: float) -> Dictionary:
	var best: Dictionary = {}
	for d: Dictionary in traffic.drivers:
		var p: Vector3 = (d.body as Node3D).position
		if p.x < -1.0 and p.x > -3.0 and p.z < z_stop and p.z > z_stop - 50.0 and float(d.speed) < 0.3:
			if best.is_empty() or p.z < (best.body as Node3D).position.z: best = d
	return best

## Simulated seconds at 4x speed.
func run_for(seconds: float) -> void:
	Engine.time_scale = 4.0
	var t := 0.0
	while t < seconds:
		await physics_frame
		t += 4.0 / Engine.physics_ticks_per_second
	Engine.time_scale = 1.0

func run() -> void:
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var mode: String = OS.get_cmdline_user_args()[1] if OS.get_cmdline_user_args().size() > 1 else ""
	VehicleCatalog.traffic_seed = 5
	world = CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	camera = Camera3D.new()
	world.add_child(camera)
	camera.current = true
	if mode != "life":
		var views := [
			["driver", Vector3(1.95, 1.25, -30), Vector3(1.9, 0.6, -90)],
			["bike_lane", Vector3(4.6, 1.6, -262), Vector3(4.7, 0.2, -282)],
			["junction", Vector3(18, 14, -372), Vector3(0, 0, -398)],
			["side_junction", Vector3(80, 12, -380), Vector3(64, 0, -398)],
			["crossing", Vector3(-7, 4.5, -75), Vector3(0, 0, -93)],
			["junction_top", Vector3(0, 34, -398), Vector3.ZERO],
			["connector", Vector3(58, 9, -528), Vector3(100, 0, -538)]]
		for v in views:
			view(v[1], v[2])
			await shot(v[0], 60)
	if mode == "kit":
		quit()
		return
	var traffic: Node = world.get_node("CityTraffic")
	var j: Dictionary = {}
	for d in SignalPlan.junctions(): if d.id == "Avenue-398": j = d
	# Let the city run, then hold the avenue at red long enough for queues to form.
	await run_for(20.0)
	traffic.elapsed = float(j.offset) + 18.0 + 36.0 * ceilf(traffic.elapsed / 36.0)
	await run_for(15.0)
	# Northbound queue (south-west loop) at Avenue-398; buses only run southbound here.
	view(Vector3(-9.0, 6.5, -436), Vector3(-1.0, 1.2, -398), 55)
	await shot("signal_queue_red")
	# Brake lights: behind the last car of the queue.
	var tail := queue_tail(traffic, -407.9)
	if not tail.is_empty():
		var p: Vector3 = (tail.body as Node3D).global_position
		view(p + Vector3(-1.6, 1.5, -9.0), p + Vector3(0, 0.8, 4.0), 50)
	else: print("no queue found")
	await shot("brake_lights")
	# Green: the queue pulls away - exhaust puffs.
	traffic.elapsed = float(j.offset) + 36.0 * ceilf(traffic.elapsed / 36.0)
	await run_for(1.6)
	await shot("exhaust_pull_away", 8)
	# Pedestrian signal on a corner pole while the cross street's walkers have WALK.
	var signals: TrafficSignals = world.get_node("TrafficSignals")
	var rt: Dictionary = signals.runtime.filter(func(r: Dictionary) -> bool: return r.def.id == "Avenue-398")[0]
	var ped: Dictionary = (rt.peds as Array).filter(func(p: Dictionary) -> bool: return p.axis == "ns")[0]
	var at: Vector3 = (ped.node as Node3D).global_position
	var facing: Vector3 = ped.facing
	view(at + facing * 3.2 + Vector3(0.9, -0.6, 0), at + Vector3(0, -0.1, 0), 45)
	await shot("ped_signal_walk", 10)
	# LED boards: a shop and a corridor restaurant, two frames ~1.2 s apart.
	view(Vector3(-88.5, 3.1, -20.5), Vector3(-87.3, 3.45, -26.7), 45)
	await shot("led_shop_a", 30)
	await shot("led_shop_b", 75)
	view(Vector3(92, 3.2, -259.5), Vector3(89.5, 3.9, -268.4), 45)
	await shot("led_restaurant_a", 30)
	await shot("led_restaurant_b", 75)
	view(Vector3(4, 2.6, -88), Vector3(-12, 3.6, -97), 50)
	await shot("led_avenue_restaurant")
	# Grill smoke over the corridor restaurants (rooftop extraction of the Kokoreç shop).
	var vfx: StreetVFX = world.get_node("StreetVFX")
	print("grill smoke emitters: %d, first at %s" % [vfx.grills.size(), vfx.grills[0].global_position if not vfx.grills.is_empty() else Vector3.ZERO])
	view(Vector3(96, 2.5, -257), Vector3(80, 21, -274), 60)
	await shot("grill_smoke", 90)
	# Signals and LED boards after dark.
	world.set_time(21.5)
	view(Vector3(9.5, 7.5, -366), Vector3(0, 1.5, -400), 55)
	await shot("signals_night", 60)
	view(Vector3(92, 3.2, -259.5), Vector3(89.5, 3.9, -268.4), 45)
	await shot("led_night", 30)
	# Wet roads: tyre spray behind a moving car (camera follows it).
	world.set_time(15)
	var weather: Node = world.get_node_or_null("Weather")
	if weather != null: weather.set("forced", 0.8)
	await run_for(2.0)
	var mover: Dictionary = {}
	for d: Dictionary in traffic.drivers:
		if float(d.speed) > 6.0 and absf((d.body as Node3D).position.x) < 3.0 and not VehicleCatalog.turns_tight(str(d.id)):
			mover = d
			break
	for f in range(45):
		if not mover.is_empty():
			var b: Node3D = mover.body
			view(b.global_position + b.global_basis.z * 9.0 + b.global_basis.x * 2.2 + Vector3.UP * 1.6, b.global_position + Vector3.UP * 0.6, 55)
		await process_frame
	await shot("wet_spray", 1)
	print("STREET CAPTURES done")
	quit()
