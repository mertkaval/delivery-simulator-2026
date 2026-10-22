extends SceneTree
## Close-up captures of every residential house type in its real in-game placement (tints, yard
## dressing, LODs), from the player's eye height (1.65 m above the ground under the camera):
## 3 m and 6 m from the front door, both front corners, a side window and the back, in daylight.
## Each view is rendered twice with the camera moved 3 mm while the world is paused; the share of
## pixels that change between the two frames ("flicker") is printed per view - z-fighting shows
## up there as a large value while the image itself barely moves.
## usage (rendered, no --headless):
##   godot --path . --script res://tests/capture_house_closeups.gd -- <out_dir> [prefix] [type,type...] [hour]
const EYE := 1.65

func _initialize() -> void: call_deferred("run")

func lot_of(type: String) -> Dictionary:
	var fallback := {}
	for lot in ResidentialLayout.lots():
		if lot.type != type: continue
		if lot.delivery >= 0: return lot
		if fallback.is_empty(): fallback = lot
	return fallback

## Ground (or porch / stair) height under a world point, from the collision world.
func floor_at(world: Node3D, p: Vector3) -> float:
	var space := world.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(Vector3(p.x, p.y + 2.2, p.z), Vector3(p.x, -1.0, p.z))
	var hit := space.intersect_ray(q)
	return maxf(0.0, (hit.position as Vector3).y) if not hit.is_empty() else 0.0

## Local front corners (x, z) of the facade for each type: kit houses have their facade at z = 0.
func corners(type: String, spec: Dictionary) -> Array:
	match type:
		"house_suburban": return [Vector2(-8.2, -3.0), Vector2(-0.44, -0.5), Vector2(-2.68, -3.0), Vector2(7.92, -0.5)]
		"house_duplex": return [Vector2(-5.1, -1.9), Vector2(5.1, 0.0)]
		"house_farmhouse": return [Vector2(-5.17, -0.0), Vector2(5.17, -1.78)]
	return [Vector2(-float(spec.w) / 2.0, 0.0), Vector2(float(spec.w) / 2.0, 0.0)]

func views_for(world: Node3D, type: String) -> Array:
	var lot := lot_of(type)
	if lot.is_empty(): return []
	var spec: Dictionary = ResidentialLayout.TYPES[type]
	var t := ResidentialLayout.transform(lot)
	var door: Vector3 = spec.door
	var w: float = spec.w
	var d: float = spec.d
	var out: Array = []
	var gap := (float(lot.width) - w) / 2.0
	var at := func(tag: String, eye_local: Vector3, target_local: Vector3) -> void:
		var eye: Vector3 = t * eye_local
		eye.y = floor_at(world, eye) + EYE
		out.append([tag, eye, t * target_local])
	at.call("door3m", Vector3(door.x, 0, door.z + 3.0), Vector3(door.x, door.y + 1.2, door.z))
	at.call("door6m", Vector3(door.x, 0, door.z + 6.0), Vector3(door.x, door.y + 1.4, door.z))
	var k := 0
	for c: Vector2 in corners(type, spec):
		var sx := signf(c.x)
		at.call("corner%d" % k, Vector3(c.x + sx * 2.1, 0, c.y + 2.1), Vector3(c.x, 1.6, c.y))
		k += 1
	at.call("side_window", Vector3(w / 2.0 + clampf(gap * 0.85, 0.8, 2.6), 0, 0.5), Vector3(w / 2.0, 1.9, -d * 0.4))
	at.call("side_window_l", Vector3(-w / 2.0 - clampf(gap * 0.85, 0.8, 2.6), 0, 0.5), Vector3(-w / 2.0, 1.9, -d * 0.4))
	at.call("back", Vector3(0.8, 0, -d - 6.0), Vector3(0, 2.2, -d))
	return out

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var out_dir: String = args[0] if args.size() > 0 else "res://tmp"
	var prefix: String = args[1] if args.size() > 1 else "fix_house"
	var only: PackedStringArray = args[2].split(",") if args.size() > 2 and args[2] != "all" else PackedStringArray()
	var hour: float = float(args[3]) if args.size() > 3 else 13.0
	root.size = Vector2i(1280, 720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(hour)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 78
	for i in range(10): await process_frame
	var types: Array = ResidentialLayout.TYPES.keys()
	var report := {}
	for type: String in types:
		if not only.is_empty() and not only.has(type): continue
		var views := views_for(world, type)
		var lot := lot_of(type)
		print("TYPE %s lot at %s (delivery %d), %d views" % [type, str(lot.front), lot.delivery, views.size()])
		for view: Array in views:
			paused = false
			camera.position = view[1]
			camera.look_at(view[2])
			for i in range(40): await process_frame
			paused = true
			for i in range(3): await process_frame
			await RenderingServer.frame_post_draw
			var a := root.get_texture().get_image()
			camera.position = (view[1] as Vector3) + camera.global_basis.x * 0.003 + Vector3(0, 0.002, 0)
			for i in range(3): await process_frame
			await RenderingServer.frame_post_draw
			var b := root.get_texture().get_image()
			var changed := 0
			var total := 0
			for y in range(0, a.get_height(), 2):
				for x in range(0, a.get_width(), 2):
					total += 1
					if absf(a.get_pixel(x, y).get_luminance() - b.get_pixel(x, y).get_luminance()) > 0.12: changed += 1
			var flicker := float(changed) / float(total)
			report["%s/%s" % [type, view[0]]] = snappedf(flicker * 100.0, 0.01)
			var name := "%s/%s_%s_%s" % [out_dir, prefix, type.trim_prefix("house_"), view[0]]
			a.save_png(name + ".png")
			if String(view[0]).begins_with("corner") or flicker > 0.004: b.save_png(name + "_b.png")
			print("VIEW %s %s flicker %.2f%%" % [type, view[0], flicker * 100.0])
	paused = false
	print("HOUSE CLOSEUPS ", JSON.stringify(report))
	quit()
