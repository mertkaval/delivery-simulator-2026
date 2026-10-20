class_name CityCatalog
extends RefCounted
## Pickups 0-2: Atatürk Avenue restaurants; 3-7: downtown counters; 8-20: corridor restaurants
## (RestaurantCatalog). Ids are save-game keys and never change; names come from the catalogue.
const RESTAURANTS = ["cedar_kitchen", "market_noodles", "harbor_pizza","rainline_cafe","rainline_rear","juniper_grocery","corner_pantry","service_alley",
	"kokorech_shop", "fish_restaurant", "iskender_house", "dessert_shop", "soup_house", "doner_shop", "local_diner", "tavern",
	"pastry_shop", "bulgur_wrap", "pancake_house", "baked_potato", "dairy_dessert"]
const NAMES = ["Kebab House", "Meatball Restaurant", "Turkish Pizza Parlor","Rainline Café","Juniper rear collection","Juniper Grocery","Corner Pantry","Service Alley Supplies",
	"Kokorech Shop", "Fish Restaurant", "Iskender Kebab House", "Dessert Shop", "Soup House", "Doner Shop", "Local Diner", "Tavern",
	"Pastry Shop", "Spiced Bulgur Wrap Shop", "Pancake House", "Baked Potato Shop", "Dairy Dessert Parlor"]
## Offer rotation outside downtown: the avenue trio first, then the corridor restaurants.
const ROTATION = [0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
static var PICKUPS: Array = [Vector3(-14, 1, 12), Vector3(-14, 1, -100), Vector3(-14, 1, -184)] + DowntownCatalog.PICKUPS + RestaurantCatalog.corridor_pickups()
const WORLD_MIN = Vector2(-120, -710)
const WORLD_MAX = Vector2(120, 70)
const ROAD_MIN = -690
const ROAD_MAX = 50
const CROSS_STREETS = [-258, -398, -538, -678]
const SIDE_ROADS = [-64, 64]

static func estate_roads() -> Array[PackedVector3Array]:
	var roads: Array[PackedVector3Array] = []
	roads.append(PackedVector3Array([Vector3(-64,0,48), Vector3(64,0,48)]))
	for side in [-1,1]:
		for ends in [Vector2(48,-125),Vector2(-165,-258)]:
			roads.append(PackedVector3Array([Vector3(side*64,0,ends.x),Vector3(side*64,0,ends.y)]))
		var ring := PackedVector3Array()
		for i in range(65):
			var angle := TAU*i/64.0
			ring.append(Vector3(side*64+cos(angle)*20,0,-145+sin(angle)*20))
		roads.append(ring)
		for frontage in [34,-20,-96,-176]:
			var curve := Curve3D.new()
			curve.add_point(Vector3(side*64,0,frontage+10),Vector3.ZERO,Vector3(0,0,-8))
			curve.add_point(Vector3(side*92,0,frontage),Vector3(-side*12,0,0),Vector3.ZERO)
			roads.append(curve.tessellate(5,2))
	return roads

static func near_estate_road(p: Vector3, margin: float = 7.5) -> bool:
	for path in estate_roads():
		for i in range(1,path.size()):
			if Geometry3D.get_closest_point_to_segment(p,path[i-1],path[i]).distance_to(p) < margin: return true
	return false

static func restaurant_index(id: String) -> int:
	return RESTAURANTS.find(id)

static func address_position(index: int) -> Vector3:
	if index>=36: return DowntownCatalog.DESTINATIONS[index-36]
	# Street-facing houses of the residential district (ResidentialLayout).
	return ResidentialLayout.door_point(ResidentialLayout.delivery_lot(index))

## Unit vector pointing out of the delivery door towards the street (horizontal).
static func address_facing(index: int) -> Vector3:
	if index>=36: return Vector3.BACK
	return ResidentialLayout.delivery_lot(index).facing
static func route(from: Vector3, destination: Vector3, pickup: bool) -> PackedVector3Array:
	if from.x>120 or destination.x>120: return UrbanNavigation.route(from,destination,pickup)
	var start := Vector3(from.x, 0, from.z)
	var end := Vector3(destination.x, 0, destination.z)
	var path := PackedVector3Array([start])
	if absf(start.x) > 34 and start.z > -248 and corridor_restaurant_at(start).is_empty():
		var side := signf(start.x)
		var frontage := start.z
		var lot := false
		for building_z in [22,-32,-110,-190]:
			if absf(start.x-side*92)<12 and absf(start.z-building_z)<13:
				frontage = building_z + (12 if building_z in [22,-32] else 14)
				lot=true
		if lot:
			path.append(Vector3(start.x,0,frontage))
			path.append(Vector3(side*92,0,frontage))
			for access in estate_roads():
				if access[-1].is_equal_approx(Vector3(side*92,0,frontage)):
					for i in range(access.size()-2,-1,-1): path.append(access[i])
					frontage=access[0].z
		elif frontage>=-165 and frontage<=-125:
			var angle := atan2(start.z+145,maxf(.01,side*start.x-64))
			for i in range(17):
				var a := lerpf(angle,PI/2,i/16.0)
				path.append(Vector3(side*(64+20*cos(a)),0,-145+20*sin(a)))
			frontage=-125
		else:
			path.append(Vector3(side*64,0,frontage))
		if frontage < -165:
			path.append(Vector3(side*64,0,-165))
			for i in range(1,17):
				var a := -PI/2+PI*i/16.0
				path.append(Vector3(side*(64+20*cos(a)),0,-145+20*sin(a)))
		path.append(Vector3(side*64,0,48))
		path.append(Vector3(side*8,0,48))
		start = Vector3(side*8,0,48)
	# Leaving a corridor restaurant: out through its door and along the cross-street sidewalk.
	var from_restaurant := corridor_restaurant_at(start)
	if not from_restaurant.is_empty():
		for p in corridor_walk(from_restaurant): path.append(p)
		start = path[-1]
	# Step out to the Atatürk Avenue sidewalk (x = +-8), walk along it, then approach the target.
	var exit_path := sidewalk_exit(start)
	for p in exit_path: path.append(p)
	var walk_x: float = exit_path[-1].x if not exit_path.is_empty() else start.x
	if pickup and not corridor_restaurant_at(end).is_empty():
		# Corridor restaurant: cross-street sidewalk to its door, then in to the pickup shelf.
		var walk := corridor_walk(corridor_restaurant_at(end))
		walk.reverse()
		path.append(Vector3(walk_x, 0, walk[0].z))
		for p in walk: path.append(p)
		path.append(end)
		return path
	if pickup:
		# Restaurant counters face +z: approach from in front of the counter.
		var front := end.z + 3.0
		if absf(start.x - end.x) < 1 and start.z >= end.z and start.z <= front:
			path.append(end)
			return path
		path.append(Vector3(walk_x, 0, front))
		path.append(Vector3(end.x, 0, front))
	else:
		# Houses face the avenue: walk to the end of their front path, then up it.
		var side_x := 8.0 * signf(end.x)
		path.append(Vector3(walk_x, 0, end.z))
		if not is_equal_approx(walk_x, side_x): path.append(Vector3(side_x, 0, end.z))
	path.append(end)
	return path

## Points that take someone from `p` to the avenue sidewalk on their side.
static func sidewalk_exit(p: Vector3) -> PackedVector3Array:
	var out := PackedVector3Array()
	var side := signf(p.x) if p.x != 0.0 else 1.0
	if absf(p.x) <= 8.5: return out
	for counter in PICKUPS.slice(0, 3):
		if p.x > counter.x - 11 and p.x < counter.x + 3 and p.z > counter.z - 4 and p.z < counter.z + 3:
			out.append(Vector3(p.x, 0, counter.z + 3))
			out.append(Vector3(side * 8, 0, counter.z + 3))
			return out
	# From a house door (or anywhere in a front yard) straight along the front walk.
	out.append(Vector3(side * 8, 0, p.z))
	return out
static func distance(path: PackedVector3Array) -> float:
	var result := 0.0
	for i in range(1, path.size()):
		result += path[i - 1].distance_to(path[i])
	return result



## Corridor restaurant building (CityLayout midrise) containing `p`, or {}.
static func corridor_restaurant_at(p: Vector3) -> Dictionary:
	if p.x < 70.0 or p.x > 120.0: return {}
	for b in RestaurantCatalog.corridor_buildings():
		var local := RestaurantCatalog.frame(b).affine_inverse() * Vector3(p.x, 0, p.z)
		var xl := -int(b.bays) * 2.0
		if local.x > xl - 0.5 and local.x < xl + RestaurantCatalog.restaurant_width(b) + 0.5 and local.z > -16.0 and local.z < 0.5:
			return b
	return {}

## From inside a corridor restaurant to the Atatürk Avenue sidewalk: dining room, door,
## the cross-street sidewalk in front of it, then west along that sidewalk to x = 8.
static func corridor_walk(b: Dictionary) -> PackedVector3Array:
	var t := RestaurantCatalog.frame(b)
	var door_x := RestaurantCatalog.bay_x(b, RestaurantCatalog.entrance_bay(b))
	var outside := RestaurantCatalog.door_outside(b)
	return PackedVector3Array([t * Vector3(door_x, 0, -2.0), outside, Vector3(8, 0, outside.z)])
