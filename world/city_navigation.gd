class_name CityNavigation
extends RefCounted
## Turn-by-turn style routing over the whole road network (residential avenue and side roads,
## estate roads, cross streets, downtown grid, civic campus) for any destination, plus the
## catalogue of places shown on the city map.
##
## The graph is built once from road centrelines sampled every SAMPLE metres; samples closer
## than MERGE metres are welded, which joins roads at their junctions. A route runs from the
## player to the nearest road node, along the roads (A*), then to the destination.

const SAMPLE := 5.0
const MERGE := 3.8

static var graph: AStar3D
static var points: PackedVector3Array = PackedVector3Array()
static var _grid: Dictionary = {}
## The destination the player picked on the city map: {"name", "kind", "at": Vector3}, or {}.
static var target: Dictionary = {}

static func _cell(p: Vector3) -> Vector2i:
	return Vector2i(floori(p.x / MERGE), floori(p.z / MERGE))

static func _node(p: Vector3) -> int:
	var c := _cell(p)
	for dx in range(-1, 2):
		for dz in range(-1, 2):
			for id in _grid.get(c + Vector2i(dx, dz), []):
				if points[id].distance_to(p) < MERGE: return id
	var id := points.size()
	points.append(p)
	graph.add_point(id, p)
	if not _grid.has(c): _grid[c] = []
	_grid[c].append(id)
	return id

static func _road(path: PackedVector3Array) -> void:
	var previous := -1
	for i in range(path.size()):
		var a: Vector3 = Vector3(path[i].x, 0, path[i].z)
		if i > 0:
			var b: Vector3 = Vector3(path[i - 1].x, 0, path[i - 1].z)
			var steps := maxi(1, ceili(a.distance_to(b) / SAMPLE))
			for k in range(1, steps + 1):
				var id := _node(b.lerp(a, float(k) / steps))
				if previous >= 0 and previous != id and not graph.are_points_connected(previous, id):
					graph.connect_points(previous, id)
				previous = id
		else:
			previous = _node(a)

static func line(a: Vector3, b: Vector3) -> void:
	_road(PackedVector3Array([a, b]))

static func prepare() -> void:
	if graph != null: return
	graph = AStar3D.new()
	points = PackedVector3Array()
	_grid = {}
	# Named streets (avenue, side and cross streets, downtown avenues).
	for s in StreetNames.segments():
		line(Vector3(s.a.x, 0, s.a.y), Vector3(s.b.x, 0, s.b.y))
	# Residential side roads and estate access roads, roundabouts.
	for x in CityCatalog.SIDE_ROADS: line(Vector3(x, 0, -678), Vector3(x, 0, -258))
	for path in CityCatalog.estate_roads(): _road(path)
	# Downtown grid and the civic campus avenue with its spurs.
	for x in DowntownCatalog.STREET_X: line(Vector3(x, 0, -258), Vector3(x, 0, -678))
	for z in DowntownCatalog.STREET_Z: line(Vector3(64, 0, z), Vector3(630, 0, z))
	line(Vector3(520, 0, -258), Vector3(520, 0, -678))
	for site in CivicCampus.SITES: line(Vector3(520, 0, site.at.z), site.at)
	for block in DowntownCatalog.blocks():
		line(Vector3(block.position.x, 0, block.get_center().y), Vector3(block.end.x, 0, block.get_center().y))

static func nearest(p: Vector3) -> int:
	prepare()
	var best := -1
	var best_d := INF
	var c := _cell(p)
	for r in range(0, 40):
		for dx in range(-r, r + 1):
			for dz in range(-r, r + 1):
				if maxi(absi(dx), absi(dz)) != r: continue
				for id in _grid.get(c + Vector2i(dx, dz), []):
					var d := points[id].distance_to(Vector3(p.x, 0, p.z))
					if d < best_d:
						best_d = d
						best = id
		if best >= 0 and best_d < (r - 1) * MERGE: break
	return best

## Route from `from` to `to` along the roads (ground-level points).
static func route(from: Vector3, to: Vector3) -> PackedVector3Array:
	prepare()
	var start := Vector3(from.x, 0, from.z)
	var end := Vector3(to.x, 0, to.z)
	var a := nearest(start)
	var b := nearest(end)
	var path := PackedVector3Array([start])
	if a >= 0 and b >= 0 and start.distance_to(end) > points[a].distance_to(start) + points[b].distance_to(end):
		path.append_array(graph.get_point_path(a, b))
	path.append(end)
	return path

## Every place shown on the city map: {"name", "kind", "at": Vector3, "detail"}.
## Kinds: restaurant, store, park, public, hospital, school, fire, bus, house, home, square.
static func places(world: Node) -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	for i in range(CityCatalog.PICKUPS.size()):
		var detail := ""
		var entry: Array = RestaurantCatalog.entry(CityCatalog.RESTAURANTS[i])
		if not entry.is_empty(): detail = str(entry[2])
		list.append({"name": CityCatalog.NAMES[i], "kind": "restaurant", "at": CityCatalog.PICKUPS[i], "detail": detail})
	for id in ShopCatalog.LOCATIONS:
		var detail: String = {"equipment": "Gear & upgrades", "bikes": "Bicycles", "cars": "Cars · Jetta GLI $0", "scooters": "E-scooters"}.get(id, "")
		list.append({"name": ShopCatalog.TITLES[id], "kind": "store", "at": ShopCatalog.LOCATIONS[id] + Vector3(0, 0, 8), "detail": detail})
	list.append({"name": "Public WC · Water", "kind": "public", "at": Vector3(-40, 0, 40), "detail": "Washroom & drinking water"})
	for centre in StreetNames.PARKS:
		list.append({"name": StreetNames.PARKS[centre], "kind": "park", "at": Vector3(centre.x, 0, centre.y + 15), "detail": "Park"})
	for site in CivicCampus.SITES:
		var kind: String = {"hospital": "hospital", "school": "school", "fire_station": "fire"}.get(site.asset, "public")
		list.append({"name": site.name, "kind": kind, "at": site.at, "detail": "Civic campus"})
	list.append({"name": "Home", "kind": "home", "at": CedarNeighborhood.CEDAR_HOME_ORIGIN + Vector3(0, 0, 6), "detail": "Rest and save"})
	if world != null:
		var signage = world.get("signage")
		if signage != null and signage.monument_at != Vector3.ZERO:
			list.append({"name": StreetNames.SQUARE, "kind": "square", "at": signage.monument_at + Vector3(0, 0, 8), "detail": "Monument"})
		var buses = world.get("buses")
		if buses != null:
			for stop in buses.stops:
				list.append({"name": "Bus stop · Line " + str(stop.line), "kind": "bus", "at": stop.kerb, "detail": StreetNames.name_at(stop.kerb)})
		var doors = world.get("doors")
		if doors != null:
			for i in range(mini(doors.size(), DeliverySession.ADDRESSES.size())):
				list.append({"name": DeliverySession.ADDRESSES[i], "kind": "house", "at": doors[i], "detail": "Address"})
	return list
