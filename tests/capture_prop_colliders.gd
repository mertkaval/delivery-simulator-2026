extends SceneTree
## Debug captures of the prop colliders over the rendered city: new prop-layer shapes (PropColliders)
## in magenta (thin, layer 6) and orange (bulky, layer 7), every other collider in cyan.
## Usage: Godot_console.exe --path . --script res://tests/capture_prop_colliders.gd [-- <out_dir> [view,...]]
## (needs rendering; default out_dir res://tmp/; views: suburb, suburb_close, yards, lane, avenue,
##  downtown, courtyard, campus, cedar_living, cedar_kitchen, cedar_porch, restaurant_out,
##  restaurant_in, store, park)
func _initialize() -> void: call_deferred("run")

const THIN := Color(1.0, 0.1, 0.85, 1.0)
const BULKY := Color(1.0, 0.55, 0.0, 1.0)
const OTHER := Color(0.1, 0.9, 1.0, 1.0)

func run() -> void:
	var out := "res://tmp/"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: out = args[0].trim_suffix("/").trim_suffix("\\") + "/"
	var only: PackedStringArray = args[1].split(",") if args.size() > 1 else PackedStringArray()
	root.size = Vector2i(1600, 900)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	debug_collisions_hint = true
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(11.5)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current = true
	camera.fov = 70
	for i in range(10): await process_frame
	var counts := {"thin": 0, "bulky": 0, "other": 0}
	for n in world.find_children("*", "CollisionShape3D", true, false):
		var cs := n as CollisionShape3D
		var body := cs.get_parent() as CollisionObject3D
		if body == null: continue
		var kind := "other"
		if body.collision_layer & PropColliders.LAYER_THIN: kind = "thin"
		elif body.collision_layer & PropColliders.LAYER_BULKY: kind = "bulky"
		cs.debug_color = THIN if kind == "thin" else (BULKY if kind == "bulky" else OTHER)
		cs.debug_fill = kind != "other"
		counts[kind] = int(counts[kind]) + 1
	print("shapes: ", counts)
	var home := CedarNeighborhood.CEDAR_HOME_ORIGIN
	var r: Dictionary = world.restaurants.restaurants[0]
	var rf: Transform3D = r.frame
	var rb: Dictionary = {}
	for cand in RestaurantCatalog.corridor_buildings():
		if Vector2(RestaurantCatalog.frame(cand).origin.x, RestaurantCatalog.frame(cand).origin.z).distance_to(Vector2(rf.origin.x, rf.origin.z)) < 0.1: rb = cand
	var xe := RestaurantCatalog.bay_x(rb, RestaurantCatalog.entrance_bay(rb)) if not rb.is_empty() else 0.0
	var cars: Vector3 = ShopCatalog.LOCATIONS["cars"]
	# A downtown lobby with a service counter, shelf and café table (DowntownDistrict.build_building).
	var lobby_out := Vector3(200, 2, -262)
	var lobby_in := Vector3(200, 0.5, -270)
	for e: Dictionary in world.downtown.entries:
		if not bool(e.closed) and not (int(e.id) % 10 in [2, 5, 7]):
			lobby_out = (e.front as Vector3) + ((e.front as Vector3) - (e.inside as Vector3)).normalized() * 0.6 + Vector3(0, 1.2, 0)
			lobby_in = (e.inside as Vector3) + Vector3(0, -0.6, 0)
			break
	var views := [
		["lobby", lobby_out, lobby_in],
		# Cedar Lane west sidewalk: picket fences and hedges along the lots, mailboxes, avenue trees, lamps.
		["suburb", Vector3(-7.4, 2.4, -2.0), Vector3(-11.5, 0.4, -24.0)],
		["suburb_close", Vector3(-8.0, 1.7, -14.0), Vector3(-12.0, 0.6, -20.0)],
		# Back yards from above: bins, patio sets, sheds, privacy fences, the rear lane.
		["yards", Vector3(-28.0, 9.0, -186.0), Vector3(-34.0, 0.0, -206.0)],
		["lane", Vector3(-36.5, 1.8, -170.0), Vector3(-36.0, 0.5, -200.0)],
		# Atatürk Avenue east sidewalk: benches, bins, hydrants, signs, street lights.
		["avenue", Vector3(9.3, 2.2, -10.0), Vector3(9.0, 0.5, -40.0)],
		# Downtown sidewalks and a courtyard.
		["downtown", Vector3(158.0, 2.6, -262.0), Vector3(180.0, 0.5, -268.5)],
		["courtyard", Vector3(185.0, 6.0, -316.0), Vector3(196.0, 0.0, -330.0)],
		["campus", Vector3(492.0, 4.0, -300.0), Vector3(486.0, 0.0, -330.0)],
		# Cedar House interior and porch.
		["cedar_living", home + Vector3(-1.2, 2.0, 1.2), home + Vector3(-3.0, 0.4, 4.2)],
		["cedar_kitchen", home + Vector3(-0.6, 1.9, -1.0), home + Vector3(-3.2, 0.6, -3.6)],
		["cedar_porch", home + Vector3(1.1, 2.6, 9.5), home + Vector3(0.0, 0.6, 5.6)],
		# Corridor restaurant frontage and dining room.
		["restaurant_out", rf * Vector3(xe, 2.2, 6.5), rf * Vector3(xe, 0.6, 0.0)],
		["restaurant_in", rf * Vector3(xe - 1.2, 1.9, -0.8), rf * Vector3(xe + 3.0, 0.6, -7.0)],
		# Car showroom and the bike shop.
		["store", cars + Vector3(0.0, 2.6, 4.5), cars + Vector3(-1.5, 0.3, -2.0)],
		["park", Vector3(-44.0, 7.0, -312.0), Vector3(-44.0, 0.0, -330.0)],
	]
	for view in views:
		if not only.is_empty() and not only.has(str(view[0])): continue
		camera.position = view[1]
		camera.look_at(view[2])
		for i in range(30): await process_frame
		await RenderingServer.frame_post_draw
		var path: String = out + "colliders_" + view[0] + ".png"
		root.get_texture().get_image().save_png(path)
		print("saved ", ProjectSettings.globalize_path(path))
	print("COLLIDER CAPTURES done")
	quit()
