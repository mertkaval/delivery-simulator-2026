extends Control
## North-up local radar; every route and road segment is clipped to the circle.
var player: CourierPlayer
var session: DeliverySession
var world: CedarNeighborhood
var range_metres := 75.0
func radius() -> float: return minf(size.x, size.y) * 0.5 - 9
func point(p: Vector3) -> Vector2:
	return size * 0.5 + Vector2(p.x - player.position.x, p.z - player.position.z) * radius() / range_metres
## Redraws only when the view changes (the courier moved or turned, the route changed) or every
## 0.25 s for markers; every map item is culled in world space before it is projected.
var _drawn_at := Vector3(INF, 0, INF)
var _drawn_yaw := INF
var _drawn_route := 0
var _since := 0.0
var _roads: Array = []          ## [a, b, width] static road segments (world)
func _process(delta: float) -> void:
	if not is_visible_in_tree() or not is_instance_valid(player): return
	_since += delta
	var route_key := hash(route_points())
	if _since >= 0.25 or player.position.distance_squared_to(_drawn_at) > 0.04 or absf(wrapf(player.rotation.y - _drawn_yaw, -PI, PI)) > 0.03 or route_key != _drawn_route:
		_since = 0.0
		_drawn_at = player.position
		_drawn_yaw = player.rotation.y
		_drawn_route = route_key
		queue_redraw()
func near(p: Vector3, margin: float = 0.0) -> bool:
	var r := range_metres + margin
	return absf(p.x - player.position.x) < r and absf(p.z - player.position.z) < r
func static_roads() -> Array:
	if not _roads.is_empty(): return _roads
	_roads.append([Vector3(0, 0, -690), Vector3(0, 0, 50), 12.0])
	for x in [-64, 64]: _roads.append([Vector3(x, 0, -678), Vector3(x, 0, -258), 10.0])
	for z in CityCatalog.CROSS_STREETS + [48]: _roads.append([Vector3(-69, 0, z), Vector3(69, 0, z), 10.0])
	for x in DowntownCatalog.STREET_X: _roads.append([Vector3(x, 0, -258), Vector3(x, 0, -678), 18.0 if x == 252 else 14.0])
	for z in DowntownCatalog.STREET_Z: _roads.append([Vector3(64, 0, z), Vector3(630, 0, z), 14.0])
	_roads.append([Vector3(520, 0, -258), Vector3(520, 0, -678), 14.0])
	for site in CivicCampus.SITES: _roads.append([Vector3(520, 0, site.at.z), site.at, 8.0])
	for block in DowntownCatalog.blocks(): _roads.append([Vector3(block.position.x, 0, block.get_center().y), Vector3(block.end.x, 0, block.get_center().y), 8.0])
	if world.has_meta("curved_roads"):
		for path in world.get_meta("curved_roads"):
			for i in range(1, path.size()): _roads.append([path[i - 1], path[i], 8.0])
	return _roads
## Segment a-b comes within the map's square of the courier.
func crosses(a: Vector3, b: Vector3) -> bool:
	var r := range_metres + 10.0
	var px := player.position.x
	var pz := player.position.z
	return not (maxf(a.x, b.x) < px - r or minf(a.x, b.x) > px + r or maxf(a.z, b.z) < pz - r or minf(a.z, b.z) > pz + r)
func segment(a: Vector3, b: Vector3, color: Color, width: float) -> void:
	var start := point(a) - size * 0.5
	var end := point(b) - size * 0.5
	var d := end - start
	var r := radius() - width * 0.5 - 2
	var aa := d.length_squared()
	if aa < 0.0001: return
	var bb := 2 * start.dot(d)
	var cc := start.length_squared() - r * r
	var disc := bb * bb - 4 * aa * cc
	if disc < 0: return
	var low := maxf(0, (-bb - sqrt(disc)) / (2 * aa))
	var high := minf(1, (-bb + sqrt(disc)) / (2 * aa))
	if low <= high: draw_line(size * 0.5 + start + d * low, size * 0.5 + start + d * high, color, width, true)
func road(a: Vector3, b: Vector3, width: float = 10) -> void:
	segment(a, b, Color("34434b"), width * radius() / range_metres)
func _draw() -> void:
	if not is_instance_valid(player) or session == null or not is_instance_valid(world): return
	var center := size * 0.5
	# HudStyle: dark translucent rim, a thin light ring, muted green ground.
	draw_circle(center, radius() + 8, Color(0, 0, 0, 0.16))
	draw_circle(center, radius() + 6, HudStyle.PANEL_STRONG)
	draw_circle(center, radius(), Color(0.13, 0.2, 0.19, 0.94))
	draw_arc(center, radius() + 2.5, 0, TAU, 96, Color(1, 1, 1, 0.22), 1.0, true)
	for r: Array in static_roads():
		if crosses(r[0], r[1]): road(r[0], r[1], r[2])
	for site in CivicCampus.SITES:
		if near(site.at):
			var at := point(site.at)
			if at.distance_to(center)<radius()-10:
				draw_rect(Rect2(at-Vector2(5,7),Vector2(10,14)),Color("9cbdcf"))
	for p in world.doors:
		if not near(p, 6.0): continue
		var map_pos := point(p + Vector3(0, 0, -4))
		if map_pos.distance_to(center) < radius() - 8: draw_rect(Rect2(map_pos - Vector2(5, 4), Vector2(10, 8)), Color("91a699"))
	for p in world.scenery_houses:
		if not near(Vector3(p.x, 0, p.y)): continue
		var at := point(Vector3(p.x, 0, p.y))
		if at.distance_to(center) < radius() - 7: draw_rect(Rect2(at - Vector2(4, 4), Vector2(8, 8)), Color("899c92"))
	for index in range(CityCatalog.PICKUPS.size()):
		var at := point(CityCatalog.PICKUPS[index])
		if at.distance_to(center) < radius() - 8: draw_circle(at, 4, Color("eec782"))
	for shop in ShopCatalog.LOCATIONS.values():
		var at := point(shop)
		if at.distance_to(center) < radius() - 8: draw_rect(Rect2(at - Vector2(3, 3), Vector2(6, 6)), Color("93bff5"))
	for x in [-92,92]:
		for z in [-110,-190]:
			var at := point(Vector3(x,0,z))
			if at.distance_to(center)<radius()-12: draw_rect(Rect2(at-Vector2(7,7),Vector2(14,14)),Color("a8aaa0"))
	var route := route_points()
	for i in range(1, route.size()): segment(route[i - 1], route[i], Color("69ebbb"), 3)
	if route.size() > 1:
		var destination := point(route[-1]) - center
		if destination.length() > radius() - 12: destination = destination.normalized() * (radius() - 12)
		draw_circle(center + destination, 5, Color("69ebbb"))
	var arrow := PackedVector2Array()
	for p in [Vector2(0, -9), Vector2(6, 7), Vector2(0, 4), Vector2(-6, 7)]: arrow.append(center + p.rotated(-player.rotation.y))
	draw_colored_polygon(arrow, Color.WHITE)
	# North marker: a small pill on the rim.
	var north := Vector2(center.x, center.y - radius() - 2)
	draw_circle(north, 7.5, HudStyle.PANEL_STRONG)
	draw_arc(north, 7.5, 0, TAU, 32, Color(1, 1, 1, 0.25), 1.0, true)
	var f := HudStyle.font(HudStyle.Face.DISPLAY, HudStyle.BOLD)
	var w := f.get_string_size("N", HORIZONTAL_ALIGNMENT_LEFT, -1, HudStyle.CAPTION).x
	draw_string(f, north + Vector2(-w * 0.5, f.get_ascent(HudStyle.CAPTION) * 0.5 - 1), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, HudStyle.CAPTION, HudStyle.ACCENT)
var _route_cache := PackedVector3Array()
var _route_goal := Vector3(INF, 0, INF)
var _route_from := Vector3(INF, 0, INF)
var _route_state := ""
var _nav_cache := PackedVector3Array()
var _nav_from := Vector3(INF, 0, INF)
var _nav_goal := Vector3(INF, 0, INF)
func route_points() -> PackedVector3Array:
	var state: String = session.order.get("state", "")
	if state not in DeliverySession.ACTIVE:
		# Destination picked on the city map (M).
		if CityNavigation.target.is_empty(): return PackedVector3Array()
		var goal: Vector3 = CityNavigation.target.at
		if goal != _nav_goal or player.position.distance_to(_nav_from) > 3.0:
			_nav_goal = goal
			_nav_from = player.position
			_nav_cache = CityNavigation.route(player.position, goal)
		var live := _nav_cache.duplicate()
		if live.size() > 0: live[0] = Vector3(player.position.x, 0, player.position.z)
		return live
	var destination: Vector3 = session.pickup_position() if state == "ACCEPTED" else world.doors[int(session.order.address)]
	if state == "DROPPED": destination = session.dropped_position()      # back to the package you put down
	# The route is planned again only after the courier moves 2 m (called several times a frame).
	if destination != _route_goal or state != _route_state or player.position.distance_to(_route_from) > 2.0:
		_route_goal = destination
		_route_state = state
		_route_from = player.position
		_route_cache = CityCatalog.route(player.position, destination, state == "ACCEPTED")
	return _route_cache
