class_name PortHaldenGame
extends RefCounted
## Port Halden as the game's city: picks the gameplay places from the generated plan and points
## the game's catalogs at them (CityCatalog doors / pickups / routes, DeliverySession addresses,
## ShopCatalog stores, GamePersistence start).
##   start        the courier's first spot: the sidewalk of a house in the starter neighbourhood
##   doors 0-35   the 36 houses nearest the start (the classic residential addresses)
##   doors 36-40  downtown tower lobbies (the classic downtown destinations)
##   pickups 0-20 shop fronts on the nearest commercial strip, a courier rack on the sidewalk
##   stores       the four stores (equipment, bikes, cars, scooters) in north-facing shops
## A roads-only plan (no buildings yet) uses the frontage plots along the streets instead (CityForgeWorld.sites):
## houses -> the nearest plots, towers -> plots nearest downtown, shops -> plots on the main streets.
## Everything is chosen from the plan deterministically, so saves and tests see the same city.

const STARTER := Vector2(1100.0, 1300.0)     ## plan metres: the starter neighbourhood
const DOORS := 36
const DOWNTOWN_DOORS := 5
const DOWNTOWN := Vector2(560, 1640)          ## plan metres: downtown's centre
const PLOT_WALK := 2.5                        ## a plot's door -> the sidewalk in front of it (m)
const MAIN_STREETS := ["arterial", "downtown", "boulevard"]

## Applies the layout to the game's catalogs; returns what the world keeps.
static func apply(w: CityForgeWorld) -> Dictionary:
	var city := w.city
	var houses: Array = w.sites()
	# Start: the house nearest the starter point; the courier stands on its front sidewalk.
	var by_distance := houses.duplicate()
	by_distance.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _plan(a).distance_squared_to(STARTER) < _plan(b).distance_squared_to(STARTER))
	var home: Dictionary = by_distance[0]
	var home_lot := _lot(city, str(home.get("lot", "")))
	var front := _front(home)
	var start: Vector3
	if home_lot.is_empty():          # a plot: the sidewalk in front of it
		start = w.house_door(home) + front * PLOT_WALK
	else:
		var walk_y := float(home_lot.front_y) + float(home_lot.front) * CityForgeWorld.SIDEWALK_OFFSET
		start = w.to_world(float((home.pos as Array)[0]), walk_y, 0.0)
	start.y = w.ground_height(start) + 0.4
	var vehicle := start + Vector3(2.5, 0.0, 0.0)
	vehicle.y = w.ground_height(vehicle) + 0.2
	# Delivery doors: the next 36 houses, then 5 tower lobbies downtown.
	var doors: Array[Vector3] = []
	var facing: Array[Vector3] = []
	var names: Array = []
	for k in range(1, DOORS + 1):
		var hs: Dictionary = by_distance[k]
		doors.append(w.house_door(hs) + Vector3(0, 0.92, 0))
		facing.append(_front(hs))
		names.append(str(hs.address))
	var towers: Array = city.towers
	var used := {}
	for k in DOORS + 1: used[str(by_distance[k].id)] = true
	if towers.is_empty():            # roads only: the plots nearest downtown are its addresses
		var near := houses.filter(func(p: Dictionary) -> bool: return not used.has(str(p.id)))
		near.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			return _plan(a).distance_squared_to(DOWNTOWN) < _plan(b).distance_squared_to(DOWNTOWN))
		for k in DOWNTOWN_DOORS:
			var p: Dictionary = near[k]
			used[str(p.id)] = true
			doors.append(w.house_door(p) + Vector3(0, 0.92, 0))
			facing.append(_front(p))
			names.append(str(p.address))
	var dt := towers.duplicate()
	var centre := DOWNTOWN
	dt.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _plan(a).distance_squared_to(centre) < _plan(b).distance_squared_to(centre))
	for k in (DOWNTOWN_DOORS if not towers.is_empty() else 0):
		var t: Dictionary = dt[k % dt.size()]
		var ang := deg_to_rad(float(t.angle))
		var out := Vector3(0, 0, -1).rotated(Vector3.UP, ang)
		var base := float((t.podium as Array)[0])
		var lobby := w.to_world(float((t.pos as Array)[0]), float((t.pos as Array)[1]), float(t.h)) + out * (base * 0.5 - 2.0 + 0.6)
		lobby.y = w.ground_height(lobby) + 0.2 + 0.92
		doors.append(lobby)
		facing.append(out)
		names.append(str(t.address))
	# Pickups and stores: shop fronts nearest the start.
	var shops: Array = (city.shops as Array).duplicate()
	if shops.is_empty():             # roads only: plots on the main streets stand in for the shop fronts
		shops = houses.filter(func(p: Dictionary) -> bool: return not used.has(str(p.id)) and MAIN_STREETS.has(str(p.get("cls", ""))))
	shops.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _plan(a).distance_squared_to(STARTER) < _plan(b).distance_squared_to(STARTER))
	var stores := {}
	var store_frames := {}
	var store_ids := ["equipment", "bikes", "cars", "scooters"]
	var pickups: Array = []
	var frames: Array[Transform3D] = []
	for s: Dictionary in shops:
		var out := _front(s)
		var depth := float((s.size as Array)[1])
		var shop_front := w.to_world(float((s.pos as Array)[0]), float((s.pos as Array)[1]), 0.0) + out * (depth * 0.5)
		shop_front.y = w.ground_height(shop_front + out * 1.5)
		# the first four shops are the stores (kiosk and order shelf on the sidewalk in front)
		if stores.size() < store_ids.size():
			var id: String = store_ids[stores.size()]
			stores[id] = shop_front
			store_frames[id] = Transform3D(Basis(Vector3.UP, atan2(out.x, out.z)), shop_front)
			continue
		if pickups.size() < CityCatalog.RESTAURANTS.size():
			var rack_at := shop_front + out * 0.9
			pickups.append(rack_at + out * 0.75 + Vector3(0, 1.0, 0))
			frames.append(Transform3D(Basis(Vector3.UP, atan2(out.x, out.z)), rack_at))
		if pickups.size() >= CityCatalog.RESTAURANTS.size() and stores.size() >= store_ids.size(): break
	# Point the game at them.
	CityCatalog.override_doors = doors
	CityCatalog.override_facing = facing
	CityCatalog.PICKUPS = pickups
	CityCatalog.override_router = w.route
	DeliverySession.ADDRESSES = names
	ShopCatalog.LOCATIONS = stores
	ShopCatalog.FRAMES = store_frames
	GamePersistence.START = start
	GamePersistence.VEHICLE_START = vehicle
	GamePersistence.CITY = "port_halden"
	StreetNames.describer = w.describe
	var menu_eye := start + Vector3(28, 14, 30)
	return {"doors": doors, "pickup_frames": frames, "start": start, "menu_eye": menu_eye, "menu_target": start + Vector3(0, 2, 0)}

static func _plan(item: Dictionary) -> Vector2:
	var p: Array = item.pos
	return Vector2(float(p[0]), float(p[1]))

static func _front(item: Dictionary) -> Vector3:
	return Vector3(0, 0, -1).rotated(Vector3.UP, float(item.yaw))

static func _lot(city: Dictionary, id: String) -> Dictionary:
	for lot: Dictionary in city.lots:
		if str(lot.id) == id: return lot
	return {}
