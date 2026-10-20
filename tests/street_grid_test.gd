extends SceneTree
## Street kit layout: pieces present, markings clear of junctions, traffic and cyclists in their lanes.
var failed := 0
var checks := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		printerr("FAIL: " + text)

func _initialize() -> void:
	call_deferred("run")

func origins(grid: StreetGrid, piece: String) -> Array[Transform3D]:
	var result: Array[Transform3D] = []
	if grid.get_node_or_null(piece) is MultiMeshInstance3D:
		for t in grid.layout.get(piece, []): result.append(t)
	return result

func run() -> void:
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	var grid: StreetGrid = game.world.streets
	check(grid != null, "Street grid built")
	for piece in ["avenue_deck", "street_deck", "junction_pad", "avenue_marks_half", "street_marks_half", "bike_symbol", "paint_white_tile", "bike_conflict_tile"]:
		check(origins(grid, piece).size() > 0, "Kit piece placed: " + piece)
	var pads := origins(grid, "junction_pad")
	check(pads.size() == 12, "Twelve junction pads (3 north-south roads x 4 cross streets)")
	var boxes: Array[Rect2] = []
	for pad in pads:
		var size := Vector2(pad.basis.x.length(), pad.basis.z.length())
		boxes.append(Rect2(Vector2(pad.origin.x, pad.origin.z) - size * 0.5, size).grow(-0.05))
	for piece in ["avenue_marks_half", "street_marks_half", "bike_symbol", "avenue_deck", "street_deck"]:
		var inside := 0
		for t in origins(grid, piece):
			for box in boxes:
				if box.has_point(Vector2(t.origin.x, t.origin.z)): inside += 1
		check(inside == 0, "No %s inside a junction box" % piece)
	for t in origins(grid, "avenue_marks_half") + origins(grid, "street_marks_half"):
		check(is_equal_approx(t.origin.y, StreetGrid.SURFACE_Y), "Markings sit on the deck surface")
	# Bike symbols point along travel for right-hand traffic: local -Z = travel, local +X = outward.
	for t in origins(grid, "bike_symbol"):
		var travel := -t.basis.z.normalized()
		var outward := t.basis.x.normalized()
		check(outward.cross(Vector3.UP).dot(-travel) > 0.99, "Bike symbol faces right-hand travel")
	var traffic: Node = game.world.get_node("CityTraffic")
	check(is_equal_approx(absf(traffic.LOOP[0].x), StreetGrid.AVENUE.lane), "Cedar Lane traffic uses lane centre")
	# Straight stretches of the side-road loop run on lane centres (corners are smooth arcs).
	var side_route: SmoothRoute = traffic.drivers[10].route
	for p in side_route.points:
		var on_side_road := absf(absf(p.x) - 64.0)
		var on_cross := minf(absf(p.z + 678.0), absf(p.z + 258.0))
		var in_corner := absf(absf(p.x) - 64.0) < 12.0 and on_cross < 12.0
		if in_corner or TrafficCircles.near_circle(p, 4.0): continue
		check(absf(on_side_road - StreetGrid.STREET.lane) < 0.01 or absf(on_cross - StreetGrid.STREET.lane) < 0.01, "Side-road route on lane centre")
	# The avenue shuttle never turns tighter than a car can (bulb U-turns, no kinks).
	var avenue: SmoothRoute = traffic.drivers[0].route
	var sharpest := 0.0
	for k in range(0, int(avenue.total), 2): sharpest = maxf(sharpest, avenue.curvature(float(k)))
	# No U-turns: the avenue loops never reverse direction on a road.
	var reversals := 0
	for k in range(0, int(avenue.total), 5):
		if (avenue.at(float(k) + 2.0) - avenue.at(float(k))).dot(avenue.at(float(k) + 12.0) - avenue.at(float(k) + 10.0)) < -0.5: reversals += 1
	check(reversals == 0, "Avenue traffic makes no U-turns (%d reversals)" % reversals)
	check(sharpest < 1.0 / 4.0, "Avenue loop turning radius stays above 4 m (%.1f m)" % (1.0 / maxf(sharpest, 0.001)))
	var life: Node = game.world.get_node("CityLife")
	for rider in life.cyclists:
		var x := absf(rider.body.position.x)
		check(x > StreetGrid.AVENUE.edge - StreetGrid.AVENUE.bike_width and x < StreetGrid.AVENUE.edge, "Cyclist rides inside the bike lane")
	print("STREET GRID PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "STREET GRID: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
