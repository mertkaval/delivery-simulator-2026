extends SceneTree
## Street-level views of Port Halden's districts with the game's own sky and lighting
## (CedarNeighborhood in Port Halden mode): for each culture, the local street nearest the district
## centre, seen from its sidewalk; a street-name board at a corner; optionally every street.
## usage: godot --path . --script res://tests/capture_districts.gd -- <out_dir> [all]
var world: CedarNeighborhood
var w: CityForgeWorld
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func shot(out: String, name: String, eye: Vector3, target: Vector3, fov: float = 62.0) -> void:
	w.update_focus(eye, 10.0)
	camera.position = eye
	camera.fov = fov
	camera.look_at(target)
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("%s.png" % name))
	print("CAPTURED ", name)

## Sidewalk eye and look target along a road edge (plan metres), at fraction t, on side +1/-1.
func along(e: Dictionary, t: float, side: float, ahead: float) -> Array:
	var nodes := {}
	for nd: Dictionary in w.city.nodes: nodes[int(nd.id)] = nd.pos
	var a: Array = nodes[int(e.a)]
	var b: Array = nodes[int(e.b)]
	var pa := Vector2(float(a[0]), float(a[1]))
	var pb := Vector2(float(b[0]), float(b[1]))
	var d := (pb - pa).normalized()
	var n := Vector2(-d.y, d.x)
	var off := float(e.width) * 0.5 + 1.6 + 1.5
	var p := pa.lerp(pb, t) + n * off * side
	var q := pa.lerp(pb, minf(1.0, t + ahead)) + n * (off - 4.0) * side
	var eye := w.to_world(p.x, p.y)
	eye.y = w.ground_height(eye) + 1.75
	var tgt := w.to_world(q.x, q.y)
	tgt.y = w.ground_height(tgt) + 2.6
	return [eye, tgt]

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var every := args.has("all")
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
	var roads: Array = w.city.roads
	for n: Dictionary in w.city.neighbourhoods:
		var c := Vector2(float((n.centre as Array)[0]), float((n.centre as Array)[1]))
		var best: Dictionary = {}
		var bd := INF
		for e: Dictionary in roads:
			if str(e.get("culture", "")) != str(n.culture) or str(e.cls) != "local": continue
			var v := _mid(e).distance_squared_to(c)
			if v < bd:
				bd = v
				best = e
		if best.is_empty(): continue
		var pose := along(best, 0.25, 1.0, 0.45)
		await shot(out, "district_%s_%s" % [str(n.culture), str(n.name).to_lower().replace(" ", "_")], pose[0], pose[1])
	# a street-name board, close
	var signs: Array = (w.city.props as Dictionary).street_sign
	var sg: Array = signs[signs.size() / 3]
	var base := w.to_world(float(sg[0]), float(sg[1]), float(sg[2]))
	var look_dir := Vector3(cos(float(sg[3]) + PI / 2), 0, -sin(float(sg[3]) + PI / 2))
	await shot(out, "street_sign_%s" % str(sg[7]), base + look_dir * 3.2 + Vector3(0, 2.4, 0), base + Vector3(0, 2.8, 0), 50.0)
	if every:
		var done := {}
		for e: Dictionary in roads:
			var key := str(e.name)
			if done.has(key) or bool(e.bridge): continue
			done[key] = true
			var pose := along(e, 0.3, 1.0, 0.5)
			await shot(out, "street_%03d_%s" % [done.size(), key.to_lower().replace(" ", "_")], pose[0], pose[1])
	quit()

func _mid(e: Dictionary) -> Vector2:
	for nd: Dictionary in w.city.nodes:
		if int(nd.id) == int(e.a):
			var a: Array = nd.pos
			for nd2: Dictionary in w.city.nodes:
				if int(nd2.id) == int(e.b):
					var b: Array = nd2.pos
					return Vector2((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5)
	return Vector2.ZERO
