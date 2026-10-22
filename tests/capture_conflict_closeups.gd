extends SceneTree
## Rendered close-ups for conflict QA (z-fighting / interpenetration): a 1.65 m eye-height camera
## 2-6 m from storefront corridors, downtown blocks, restaurant fronts and interiors, the four shops
## (inside), the Cedar House rooms and porch, Atatürk Square and the park monuments, and junctions
## with signals and LED boards. Every view is saved twice ("_a", "_b") from cameras 4 cm apart so
## flicker shows up as a difference between the two frames; "_far" views look down a corridor so
## distant facade corners are covered too.
## usage: godot --path . --script res://tests/capture_conflict_closeups.gd -- <out_dir> [prefix] [only]
var out_dir := "res://tmp"
var prefix := "fix_city_"
var only := ""
var world: CedarNeighborhood
var camera: Camera3D
var count := 0

func _initialize() -> void: call_deferred("run")

func house(x: float, y: float, z: float) -> Vector3:
	return CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(x, z, -y)

func shot(name: String, at: Vector3, look: Vector3, settle: int = 20) -> void:
	if only != "" and not name.contains(only): return
	var side := (look - at).cross(Vector3.UP).normalized()
	for k in range(2):
		camera.position = at + side * (0.04 * k)
		camera.look_at(look + side * (0.04 * k))
		for i in range(settle if k == 0 else 4): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out_dir.path_join("%s%s_%s.png" % [prefix, name, "ab"[k]]))
		count += 1

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out_dir = args[0]
	if args.size() > 1: prefix = args[1]
	if args.size() > 2: only = args[2]
	DirAccess.make_dir_recursive_absolute(out_dir)
	root.size = Vector2i(1280, 720)
	world = CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(13.0)
	camera = Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 78
	camera.near = 0.05
	for i in range(120): await physics_frame
	var eye := 1.65
	# Corridor kit buildings (mixed-use blocks with storefronts) and restaurant fronts.
	var k := 0
	for b in CityLayout.buildings():
		if b.type != "midrise": continue
		var t := Transform3D(Basis(Vector3.UP, float(b.yaw)), b.front as Vector3)
		var half := int(b.bays) * 2.0
		if k < 6:
			# Street corner of the block (storefront end vs side facade), 4 m out.
			await shot("corridor_corner_%d" % k, t * Vector3(half + 2.5, eye, 3.5), t * Vector3(half - 0.5, 2.6, -1.0))
			await shot("corridor_front_%d" % k, t * Vector3(-half + 4.0, eye, 4.5), t * Vector3(-half + 2.0, 3.0, 0.0))
		k += 1
	var restaurants: Node = world.find_child("Restaurants", true, false)
	if restaurants != null:
		var n := 0
		for r: Dictionary in restaurants.restaurants:
			if n >= 6: break
			var t: Transform3D = r.frame
			var xe: float = (t.affine_inverse() * (r.door_inside as Vector3)).x
			await shot("rest_front_%s" % r.id, t * Vector3(xe + 1.5, eye, 4.5), t * Vector3(xe + 0.5, 2.6, 0.0))
			await shot("rest_inside_%s" % r.id, t * Vector3(xe - 0.5, eye, -2.0), t * Vector3(xe + 1.0, 1.0, -7.4))
			await shot("rest_kitchen_%s" % r.id, t * Vector3(xe + 0.2, eye, -6.2), t * Vector3(xe, 1.6, -10.0))
			n += 1
	# Corridor from a distance (distant corners and the far LOD switch).
	await shot("corridor_far", Vector3(70.0, eye, -250.0), Vector3(84.0, 4.0, -330.0))
	# Shops: front and inside.
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		await shot("shop_front_%s" % id, at + Vector3(2.0, eye, 10.0), at + Vector3(2.0, 3.0, 5.0))
		await shot("shop_inside_%s" % id, at + Vector3(-2.0, eye, 2.5), at + Vector3(4.0, 1.2, -3.0))
		await shot("shop_counter_%s" % id, at + Vector3(2.0, eye, 2.8), at + Vector3(4.6, 1.0, -4.5))
	# Cedar House rooms and porch (doors opened).
	var home: Node = world.cedar_house
	if home != null:
		for i in range(home.doors.size()): home.toggle_door(i)
		for i in range(150): await physics_frame
		await shot("cedar_living", house(1.25, -3.9, 2.35), house(-3.0, -3.0, 1.3))
		await shot("cedar_kitchen", house(-1.1, 2.7, 2.35), house(-2.2, 5.3, 1.6))
		await shot("cedar_dining", house(0.9, 3.8, 2.35), house(-3.0, 0.8, 1.3))
		await shot("cedar_bedroom1", house(2.25, -4.55, 2.35), house(3.6, -2.0, 1.2))
		await shot("cedar_bedroom2", house(2.25, -0.1, 2.35), house(3.6, 2.6, 1.1))
		await shot("cedar_bathroom", house(0.95, 4.1, 2.35), house(3.7, 4.6, 1.2))
		await shot("cedar_hall", house(0.8, -4.9, 2.35), house(1.6, 2.5, 1.6))
		await shot("cedar_porch", house(1.1, -10.2, 1.85), house(0.0, -6.0, 1.1))
	# Monuments: Atatürk Square and the parks.
	var plaza := CityMonuments.square_plaza()
	await shot("square_monument", plaza * Vector3(3.0, eye, -1.0), plaza * Vector3(0.0, 1.2, -6.5))
	await shot("square_fountain", plaza * Vector3(-4.0, eye, -12.0), plaza * Vector3(0.0, 0.6, -15.0))
	for c: Vector2 in StreetNames.PARKS:
		var p := Vector3(c.x, 0, c.y)
		if c == CityMonuments.EQUESTRIAN_PARK:
			await shot("park_equestrian", p + Vector3(5.0, eye, 4.0), p + Vector3(0, 0.6, 0))
		else:
			await shot("park_fountain_%d_%d" % [int(c.x), int(c.y)], p + CityMonuments.FOUNTAIN_OFFSET + Vector3(-3.5, eye, 2.5), p + CityMonuments.FOUNTAIN_OFFSET + Vector3(0, 0.4, 0))
			await shot("park_bust_%d_%d" % [int(c.x), int(c.y)], p + CityMonuments.MEMORIAL_OFFSET + Vector3(3.0, eye, 1.5), p + CityMonuments.MEMORIAL_OFFSET + Vector3(0, 0.3, 0))
	# Junctions with signals, LED boards on shops / restaurants.
	for j in [Vector3(0, 0, -258), Vector3(0, 0, -398), Vector3(70, 0, -538), Vector3(252, 0, -398), Vector3(144, 0, -538)]:
		await shot("junction_%d_%d" % [int(j.x), int(j.z)], j + Vector3(9.0, eye, 9.0), j + Vector3(5.0, 1.2, 5.0))
	var leds: Node = world.find_child("LedBoards", true, false)
	if leds != null:
		var m := 0
		for board: Dictionary in leds.boards:
			if m % 4 == 0:
				var node: Node3D = board.node
				var t2 := node.global_transform
				await shot("led_%02d" % m, t2.origin + t2.basis.z * 4.0 + t2.basis.x * 1.5 + Vector3(0, eye - t2.origin.y, 0), t2.origin)
			m += 1
	# Downtown blocks: storefront fascias, signs and street props.
	var shown := 0
	for block_id in range(9):
		for b in DowntownCatalog.buildings(block_id):
			if b.program != "mixed" or shown >= 6: continue
			var t3 := Transform3D(Basis(Vector3.UP, float(b.yaw)), b.root as Vector3)
			await shot("downtown_%d" % int(b.id), t3 * Vector3(-float(b.width) * 0.5 + 3.0, eye, 4.0), t3 * Vector3(-float(b.width) * 0.5 + 1.0, 3.0, 0.0))
			# Building corner: corner post, side modules, remainder walls.
			await shot("downtown_corner_%d" % int(b.id), t3 * Vector3(float(b.width) * 0.5 + 2.5, eye, 3.0), t3 * Vector3(float(b.width) * 0.5, 4.0, -0.6))
			shown += 1
	# Civic campus: school front, a crosswalk over the civic road, the cycle tracks.
	var cz: float = DowntownCatalog.STREET_Z[1]
	await shot("campus_crosswalk", Vector3(522.0, eye, cz + 14.0), Vector3(520.0, 0.0, cz + 8.0))
	await shot("campus_school", Vector3(546.0, eye, -604.0), Vector3(563.0, 3.5, -612.0))
	await shot("campus_cycle_lane", Vector3(470.5, eye, -379.0), Vector3(474.0, 0.0, -387.0))
	# Curved estate roads: the ring seam (east point) and a T junction.
	await shot("ring_seam", Vector3(-40.0, eye, -140.5), Vector3(-45.0, 0.0, -145.0))
	# From the verge (the carriageway spot at x -60 had a parked lorry in the frame).
	await shot("estate_t_junction", Vector3(-54.5, eye, 38.0), Vector3(-64.0, 0.0, 48.0))
	print("CONFLICT CAPTURES %d images in %s" % [count, out_dir])
	quit()
