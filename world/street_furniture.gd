class_name StreetFurniture
extends Node3D
## Everyday street furniture and utilities outside downtown, from the urban kit: fire hydrants,
## kerb storm drains and manhole covers, litter and recycling bins, bike racks outside
## restaurants and parks, newspaper boxes, utility cabinets at junctions, and a fenced road-
## works zone on Kara Fatma Street with cones, barriers and an advance warning sign.
## Instanced as MultiMeshes per (asset, piece, 64 m cell); small colliders keep them solid.

const RANGE := 120.0
## Older kit pieces replaced by the converted realistic props (PropKit) where one exists.
const SWAP := {"hydrant": "fire_hydrant", "trash_bin": "litter_bin_green", "recycle_bin": "wheelie_bin_blue",
	"cone": "traffic_cone", "barrier": "water_barrier_orange"}
var groups := {}
var body: StaticBody3D
var placed: Array[Dictionary] = [] ## {"asset", "at"} for tests

func _ready() -> void:
	body = StaticBody3D.new()
	body.name = "FurnitureCollision"
	add_child(body)
	avenue()
	cross_streets()
	restaurants()
	parks()
	road_works()
	benches()
	traffic_signs()
	shopfronts()
	flush()

func put(asset: String, at: Vector3, yaw: float, solid: Vector3 = Vector3.ZERO, end: float = RANGE) -> void:
	var t := Transform3D(Basis(Vector3.UP, yaw), at)
	var cell := Vector2i(floori(at.x / 64.0), floori(at.z / 64.0))
	var id: String = SWAP.get(asset, asset)
	var parts := PropKit.get_parts(id) if PropKit.has(id) else UrbanKit.get_parts(asset)
	for i in range(parts.size()):
		var key := "%s|%d|%d_%d" % [asset, i, cell.x, cell.y]
		if not groups.has(key): groups[key] = {"piece": parts[i], "end": end, "items": []}
		groups[key].items.append(t * parts[i].transform)
	if solid != Vector3.ZERO:
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = solid
		shape.shape = box
		shape.transform = Transform3D(t.basis, at + Vector3(0, solid.y * 0.5, 0))
		body.add_child(shape)
	placed.append({"asset": asset, "at": at})

func clear(at: Vector3, radius: float = 1.6, kerb: bool = false) -> bool:
	var hood := get_parent()
	if hood != null and hood.has_method("front_walk_near") and hood.front_walk_near(at): return false
	for j in StreetNames.junctions():
		if Vector2(at.x, at.z).distance_to(j.at) < 14.0: return false
	if hood != null and hood.get("buses") != null:
		for stop in hood.buses.stops:
			if Vector3(stop.kerb).distance_to(at) < 6.0: return false
	return (kerb or not StreetNames.on_carriageway(Vector2(at.x, at.z), 0.3)) and not CityLayout.blocked(at, 0.2)

## Atatürk Avenue: hydrants between the street lamps, kerb drains, manholes in the lanes.
func avenue() -> void:
	var k := 0
	for z in range(-670, 40, 18):
		var lamp_z := float(z) + 5.0
		for side in [-1.0, 1.0]:
			var hydrant := Vector3(side * 6.9, 0.04, lamp_z + 9.0)
			if k % 5 == 0 and clear(hydrant): put("hydrant", hydrant, PI * 0.5 * side, Vector3(0.45, 0.8, 0.45))
			var drain := Vector3(side * 6.05, 0.03, lamp_z - 2.0)
			if k % 3 == 1 and clear(drain, 1.0, true): put("storm_drain", drain, -PI * 0.5 * side)
		if k % 4 == 2:
			for side in [-1.0, 1.0]: put("manhole", Vector3(side * 1.6, StreetGrid.SURFACE_Y + 0.004, float(z)), 0.0, Vector3.ZERO, 90.0)
		k += 1

## Cross streets: a utility cabinet and drains near each avenue junction.
func cross_streets() -> void:
	for c in CityCatalog.CROSS_STREETS:
		for side in [-1.0, 1.0]:
			var cabinet := Vector3(side * 12.5, 0.04, float(c) - side * 8.4)
			if clear(cabinet): put("utility_cabinet", cabinet, PI if side > 0 else 0.0, Vector3(0.9, 1.3, 0.5))
			for x in [-40.0, 30.0]:
				put("storm_drain", Vector3(x, 0.03, float(c) + side * 5.05), 0.0 if side < 0 else PI)
			put("manhole", Vector3(-24.0 + side * 10.0, StreetGrid.SURFACE_Y + 0.004, float(c) + side * 1.64), 0.0, Vector3.ZERO, 90.0)

## Outside every corridor restaurant: bike rack, bins and a newspaper box on the sidewalk.
func restaurants() -> void:
	for b in RestaurantCatalog.corridor_buildings():
		var t := RestaurantCatalog.frame(b)
		var xl := -int(b.bays) * 2.0
		var xr := xl + RestaurantCatalog.restaurant_width(b)
		var rack := t * Vector3(xr - 1.2, 0.06, 3.4)
		put("bike_rack", rack, t.basis.get_euler().y + PI * 0.5, Vector3(0.3, 0.8, 1.8))
		put("trash_bin", t * Vector3(xl + 0.8, 0.06, 3.6), t.basis.get_euler().y, Vector3(0.6, 1.0, 0.6))
		put("recycle_bin", t * Vector3(xl + 1.6, 0.06, 3.6), t.basis.get_euler().y, Vector3(0.6, 1.0, 0.6))
		put("newspaper_box", t * Vector3(xr - 2.8, 0.06, 3.6), t.basis.get_euler().y + PI, Vector3(0.5, 1.0, 0.5))
	# Atatürk Avenue restaurants: racks by the forecourt.
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		put("bike_rack", p + Vector3(-1.0, 0.04, 4.6), 0.0, Vector3(1.8, 0.8, 0.3))
		put("trash_bin", p + Vector3(1.2, 0.04, 4.5), 0.0, Vector3(0.6, 1.0, 0.6))

## Park entrances: bins and a bike rack beside the entrance sign.
func parks() -> void:
	for centre in StreetNames.PARKS:
		var at := Vector3(centre.x, 0.04, centre.y)
		put("trash_bin", at + Vector3(2.2, 0, 15.0), 0.0, Vector3(0.6, 1.0, 0.6))
		put("recycle_bin", at + Vector3(2.9, 0, 15.0), 0.0, Vector3(0.6, 1.0, 0.6))
		put("bike_rack", at + Vector3(-3.4, 0, 14.6), 0.0, Vector3(1.8, 0.8, 0.3))

## Road works on Kara Fatma Street (west of the avenue): the south lane is closed behind a
## taper of cones and a run of barriers, with an advance warning sign.
func road_works() -> void:
	var z := -538.0 + 1.64
	for i in range(7):
		var x := -14.0 - i * 1.6
		put("cone", Vector3(x, StreetGrid.SURFACE_Y, z + 1.4 - i * 0.22), 0.0, Vector3(0.35, 0.7, 0.35), 90.0)
	for i in range(6):
		put("barrier", Vector3(-26.0 - i * 2.2, StreetGrid.SURFACE_Y, z), PI * 0.5, Vector3(2.0, 1.0, 0.4), 110.0)
	for i in range(4):
		put("cone", Vector3(-27.0 - i * 3.0, StreetGrid.SURFACE_Y, z - 1.2), 0.0, Vector3(0.35, 0.7, 0.35), 90.0)
	put("road_sign", Vector3(-8.5, 0.04, -538.0 + 6.2), PI * 0.5, Vector3(0.3, 2.0, 0.3))
	var label := Label3D.new()
	label.text = "ROAD WORK\nAHEAD"
	label.font_size = 26
	label.pixel_size = 0.004
	label.modulate = Color("1c1c1c")
	label.outline_size = 0
	label.position = Vector3(-8.45, 1.65, -538.0 + 6.2)
	label.rotation.y = PI * 0.5
	label.visibility_range_end = 50.0
	add_child(label)

## Atatürk Avenue sidewalks: benches facing the road with a litter bin beside each, along the
## inner (property-line) edge so the walking line at ~8.4 m stays free.
func benches() -> void:
	if not PropKit.has("bench_wood"): return
	var k := 0
	for z in range(-640, 30, 48):
		for side in [-1.0, 1.0]:
			var at := Vector3(side * 9.65, 0.05, float(z) + 13.0 + side * 6.0)
			k += 1
			if not clear(at, 1.8) or not clear(at + Vector3(0, 0, 1.4), 1.0): continue
			put("bench_wood", at, -side * PI * 0.5, Vector3(0.6, 0.9, 1.4))
			put("litter_bin_red" if k % 2 else "litter_bin_green", at + Vector3(0, 0, 1.25), 0.0, Vector3(0.6, 0.9, 0.6))

## Real traffic signs (face toward the traffic they address; prop fronts face +Z):
## stop signs where cross streets meet the avenue, roundabout signs on every traffic-circle and
## park-roundabout approach, pedestrian-crossing signs before the avenue's mid-block crossings.
func traffic_signs() -> void:
	if not PropKit.has("sign_stop"): return
	var pole := Vector3(0.18, 2.8, 0.18)
	for z in CityCatalog.CROSS_STREETS:
		if z != -538: put("sign_stop", Vector3(-8.6, 0.04, z + 6.2), -PI * 0.5, pole)   # eastbound approach
		put("sign_stop", Vector3(8.6, 0.04, z - 6.2), PI * 0.5, pole)                  # westbound approach
	for c in TrafficCircles.CENTERS:
		var at: Vector3 = c
		if at.z > -670.0: put("sign_roundabout", at + Vector3(-6.4, 0.04, -6.6), PI, pole)  # from the north
		put("sign_roundabout", at + Vector3(6.4, 0.04, 6.6), 0.0, pole)                     # from the south
		put("sign_roundabout", at + Vector3(-6.6, 0.04, 6.4), -PI * 0.5, pole)              # from the west
		put("sign_roundabout", at + Vector3(6.6, 0.04, -6.4), PI * 0.5, pole)               # from the east
	for x in [-64.0, 64.0]:
		put("sign_roundabout", Vector3(x - 5.4, 0.15, -176.0), PI, pole)
		put("sign_roundabout", Vector3(x + 5.4, 0.15, -114.0), 0.0, pole)
	for z in [17.0, -93.0, -177.0]:
		put("sign_pedestrian_crossing", Vector3(7.2, 0.04, z + 9.0), 0.0, pole)
		put("sign_pedestrian_crossing", Vector3(-7.2, 0.04, z - 9.0), PI, pole)
	put("sign_speed_limit_50", Vector3(7.2, 0.04, -24.0), 0.0, pole)
	put("sign_speed_limit_50", Vector3(-7.2, 0.04, -232.0), PI, pole)

## Shop forecourts and restaurant frontages: planters, a post box and delivery parcels.
func shopfronts() -> void:
	if not PropKit.has("planter_bamboo_square"): return
	var k := 0
	for id in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		put("planter_bamboo_square", at + Vector3(-7.2, 0.08, 6.0), 0.0, Vector3(0.9, 1.0, 0.9))
		put("planter_bamboo_square", at + Vector3(7.2, 0.08, 6.0), 0.0, Vector3(0.9, 1.0, 0.9))
		put("cardboard_box_large", at + Vector3(5.6, 0.08, 6.0), 0.3, Vector3(0.5, 0.95, 0.5))
		put("cardboard_box_medium", at + Vector3(5.0, 0.08, 6.2), -0.2)
		put("cardboard_box_small", at + Vector3(5.3, 0.08, 6.7), 0.6)
		if k == 0: put("post_box_red", at + Vector3(-6.2, 0.08, 12.0), 0.0, Vector3(0.6, 1.1, 0.45))
		k += 1
	var flowers := ["planter_geranium_red", "planter_geranium_pink", "planter_geranium_orange", "planter_geranium_purple"]
	var i := 0
	for b in RestaurantCatalog.corridor_buildings():
		var t := RestaurantCatalog.frame(b)
		var xl := -int(b.bays) * 2.0
		var xr := xl + RestaurantCatalog.restaurant_width(b)
		put(flowers[i % 4], t * Vector3(xl + 0.45, 0.06, 0.55), t.basis.get_euler().y)
		put(flowers[(i + 1) % 4], t * Vector3(xr - 0.45, 0.06, 0.55), t.basis.get_euler().y)
		i += 1
	for p in range(3):
		var at: Vector3 = CityCatalog.PICKUPS[p] - Vector3.UP
		put(flowers[p % 4], at + Vector3(2.6, 0.04, 4.4), 0.0)

func flush() -> void:
	for data: Dictionary in groups.values():
		var items: Array = data.items
		var multi := MultiMesh.new()
		multi.transform_format = MultiMesh.TRANSFORM_3D
		multi.mesh = data.piece.mesh
		multi.instance_count = items.size()
		var origin: Vector3 = items[0].origin
		for i in range(items.size()):
			var tr: Transform3D = items[i]
			tr.origin -= origin
			multi.set_instance_transform(i, tr)
		var node := MultiMeshInstance3D.new()
		node.multimesh = multi
		node.material_override = data.piece.material
		node.position = origin
		node.visibility_range_end = data.end
		node.visibility_range_end_margin = 8.0
		add_child(node)
	groups.clear()
