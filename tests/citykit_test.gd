extends SceneTree
## City kit, layout, citizens and VFX: logic and contract checks.
var failed := 0
var checks := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		printerr("FAIL: " + text)

func _initialize() -> void:
	call_deferred("run")

func triangles(node: Node) -> int:
	var count := 0
	for part in node.find_children("*", "MeshInstance3D", true, false):
		for s in range(part.mesh.get_surface_count()):
			count += part.mesh.surface_get_array_index_len(s) / 3
	return count

func run() -> void:
	# --- Layout logic ------------------------------------------------------------------
	var specs := CityLayout.buildings()
	var counts := {"terrace": 0, "walkup": 0, "midrise": 0}
	for b in specs: counts[b.type] += 1
	check(counts.terrace >= 10 and counts.walkup == 4 and counts.midrise == 16, "Layout has terraces, 4 walk-ups and 16 corridor buildings: %s" % counts)
	var rects: Array[Rect2] = []
	for b in specs: rects.append(CityLayout.footprint(b))
	for i in range(rects.size()):
		var r := rects[i]
		check(r.position.x > CityCatalog.WORLD_MIN.x and r.end.x < 119 and r.position.y > CityCatalog.WORLD_MIN.y and r.end.y < CityCatalog.WORLD_MAX.y, "Kit building %d inside the playable bounds" % i)
		for j in range(i + 1, rects.size()):
			check(not r.grow(-0.05).intersects(rects[j].grow(-0.05)), "Kit buildings %d and %d do not overlap" % [i, j])
		# Clear of every carriageway and sidewalk (StreetGrid roads incl. 4 m sidewalks).
		for road in StreetGrid.roads():
			var a: Vector2 = road.a
			var bb: Vector2 = road.b
			var half: float = road.profile.half + 4.0
			var road_rect := Rect2(a, Vector2.ZERO).expand(bb).grow_individual(half if is_equal_approx(a.x, bb.x) else 0.0, half if not is_equal_approx(a.x, bb.x) else 0.0, half if is_equal_approx(a.x, bb.x) else 0.0, half if not is_equal_approx(a.x, bb.x) else 0.0)
			check(not r.grow(-0.05).intersects(road_rect), "Kit building %d clear of %s and its sidewalks" % [i, road.name])
		# Clear of the pocket parks and existing houses/doors.
		for z in CityLayout.PARKS:
			for x in [-44.0, 44.0]:
				check(not r.intersects(Rect2(x - 10, z - 16, 20, 32)), "Kit building %d clear of park (%d,%d)" % [i, x, z])
		for k in range(DeliverySession.ADDRESSES.size()):
			var door := CityCatalog.address_position(k)
			check(not r.has_point(Vector2(door.x, door.z)), "Kit building %d does not cover delivery door %d" % [i, k])
	for p in CityCatalog.PICKUPS:
		# Corridor restaurants are inside their midrise on purpose (open ground floor).
		if not CityCatalog.corridor_restaurant_at(p).is_empty(): continue
		for r in rects: check(not r.has_point(Vector2(p.x, p.z)), "Pickup counter not covered by a kit building")
	# --- Restaurants: catalogue contract ------------------------------------------------------
	check(CityCatalog.RESTAURANTS.size() == 21 and CityCatalog.NAMES.size() == 21 and CityCatalog.PICKUPS.size() == 21, "21 pickups with ids and names")
	check(RestaurantCatalog.LIST.size() == 16 and RestaurantCatalog.corridor_buildings().size() == 13, "16 restaurants, 13 in the corridor")
	for k in range(16):
		var entry: Array = RestaurantCatalog.LIST[k]
		var index := k if k < 3 else k + 5
		check(CityCatalog.RESTAURANTS[index] == entry[0] and CityCatalog.NAMES[index] == entry[1], "Catalogue entry %s matches pickup %d" % [entry[0], index])
		check(entry[10].size() == 5, "Menu for " + entry[1])
	for index in range(8, 21):
		var pickup: Vector3 = CityCatalog.PICKUPS[index]
		var path := CityCatalog.route(Vector3(-8, 0, 23), pickup, true)
		check(path[-1].is_equal_approx(Vector3(pickup.x, 0, pickup.z)), "Route reaches the %s counter" % CityCatalog.NAMES[index])
		var back := CityCatalog.route(pickup, CityCatalog.address_position(5), false)
		check(absf(back[3].x) == 8.0, "Route from %s leaves along the cross street to the avenue" % CityCatalog.NAMES[index])
	# --- Residential district logic ----------------------------------------------------------------
	var lots := ResidentialLayout.lots()
	check(lots.size() >= 150, "Dense residential district (%d lots)" % lots.size())
	for i in range(lots.size()):
		var a: Rect2 = lots[i].lot
		for j in range(i + 1, lots.size()):
			check(not a.grow(-0.05).intersects(lots[j].lot.grow(-0.05)), "Lots %d and %d do not overlap" % [i, j])
		var house := ResidentialLayout.house_rect(lots[i])
		check(not house.intersects(Rect2(-10.0, -700, 20.0, 760)), "House %d clear of Atatürk Avenue and its sidewalks" % i)
		for c in CityCatalog.CROSS_STREETS: check(not house.intersects(Rect2(-125, c - 9, 250, 18)), "House %d clear of cross street %d" % [i, c])
		check(absf(lots[i].facing.x) > 0.99, "House %d faces its street" % i)
	for k in range(36):
		var lot := ResidentialLayout.delivery_lot(k)
		check(not lot.is_empty() and absf(lot.line_x) == 10.5, "Address %d is a street-facing avenue house" % k)
		var door := CityCatalog.address_position(k)
		check(CityCatalog.address_facing(k).x * signf(door.x) < 0, "Door %d faces the avenue" % k)
		var path := CityCatalog.route(Vector3(-8, 0, 23), door, false)
		check(path[-1].is_equal_approx(Vector3(door.x, 0, door.z)) and absf(path[-2].x) == 8.0, "Route to door %d ends with the front walk" % k)
	# --- Module contract --------------------------------------------------------------------
	var modules := ["bay_apartment_%d", "bay_office_%d", "storefront_%d", "entrance_%d", "ground_residential_%d", "entrance_residential_%d",
		"cornice_%d", "plain_wall_%d", "th_ground_%d", "th_upper_%d", "th_roof_%d", "th_roof_dormer_%d", "th_gable_%d", "th_chimney_%d"]
	for pattern in modules:
		for s in range(3):
			var name: String = pattern % s
			check(CityKit.has_module(name) and CityKit.has_module(name + "_far"), "Module and far LOD exist: " + name)
			if CityKit.has_module(name):
				var near_scene := CityKit.scene(name).instantiate()
				var far_scene := CityKit.scene(name + "_far").instantiate()
				check(triangles(far_scene) <= triangles(near_scene), "Far LOD is not heavier: " + name)
				for part in near_scene.find_children("*", "MeshInstance3D", true, false):
					var mat: Material = part.mesh.surface_get_material(0)
					check(mat != null and mat.resource_name.begins_with("Kit"), "Kit surface naming: " + name)
					check(CityKit.material(mat.resource_name) != null, "Runtime material for " + mat.resource_name)
				near_scene.free()
				far_scene.free()
	for name in ["blank_wall", "roof_slab", "interior_slab", "parapet", "balcony", "canopy", "awning"]:
		check(CityKit.has_module(name), "Shared module exists: " + name)
	# --- Citizens --------------------------------------------------------------------------------
	for i in range(LivingAssets.VARIANTS):
		var previous := 1 << 30
		for lod in range(3):
			var model := LivingAssets.scene("citizen_%d" % i + ("_lod%d" % lod if lod else ""))
			var animation: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
			for clip in ["Idle", "Walk", "Brisk", "Wait", "Talk", "Sit", "Carry", "Cycle"]: check(animation.has_animation(clip), "citizen_%d clip %s" % [i, clip])
			var rigs := model.find_children("*", "Skeleton3D", true, false)
			check(rigs.size() == 1 and rigs[0].get_bone_count() == 14, "citizen_%d single 14-bone rig" % i)
			var count := triangles(model)
			# 10k at LOD0 (inside 18 m): sculpted faces; LOD1/LOD2 take over beyond.
			check(count < previous and count < 10000, "citizen_%d LOD%d reduces geometry within budget (%d)" % [i, lod, count])
			var surfaces := 0
			for part in model.find_children("*", "MeshInstance3D", true, false): surfaces += part.mesh.get_surface_count()
			check(surfaces <= 7, "citizen_%d draws at most 7 surfaces (%d)" % [i, surfaces])
			previous = count
			model.free()
	# --- World integration ------------------------------------------------------------------------
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	var kit: KitBuilder = game.world.get_node("KitBuildings")
	check(kit.built == specs.size(), "Every layout spec was built")
	var shapes := kit.body.get_child_count()
	check(shapes >= specs.size(), "Every kit building has collision (%d shapes)" % shapes)
	check(KitBuilder.chimney_tops.size() > 20, "Terrace chimneys recorded for smoke")
	var vfx: CityVFX = game.world.vfx
	check(vfx != null and vfx.halos.size() > 50 and vfx.smoke.size() > 5, "VFX: lamp halos and chimney smoke")
	check(vfx.birds.multimesh.instance_count == CityVFX.FLOCKS.size() * CityVFX.BIRDS_PER_FLOCK, "VFX: bird flocks")
	game.world.set_time(23.0)
	check(vfx.halo_node.visible and float(vfx.halo_material.get_shader_parameter("glow")) > 0.3, "Lamp halos glow at night")
	game.world.set_time(12.0)
	check(not vfx.halo_node.visible, "Lamp halos hidden at noon")
	# Player can't walk into a terrace: a ray at chest height from the sidewalk hits its collider.
	var t: Dictionary = specs.filter(func(b: Dictionary) -> bool: return b.type == "terrace")[0]
	var outward := Basis(Vector3.UP, t.yaw) * Vector3.BACK
	var from: Vector3 = t.front + outward * 3.0 + Vector3(0, 1.4, 0) + Basis(Vector3.UP, t.yaw) * Vector3(1.0, 0, 0)
	await physics_frame
	var hit: Dictionary = game.world.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from - outward * 6.0))
	check(not hit.is_empty(), "Terrace facade is solid")
	# Restaurants: open door, clear walk to the shelf, the shelf answers with its pickup id.
	var interiors: RestaurantInteriors = game.world.restaurants
	var waited := 0
	for service: TableService in interiors.services:
		var diners := 0
		for table in service.tables: diners += table.diners.size()
		if service.waiter != null and diners >= 2: waited += 1
	check(interiors.restaurants.size() == 13 and interiors.people.size() >= 26 and waited == 13, "13 fitted restaurants with staff, seated diners and a waiter (%d served)" % waited)
	check(interiors.spinners.size() >= 5, "Döner cones and kokoreç roll turn (%d)" % interiors.spinners.size())
	var space: PhysicsDirectSpaceState3D = game.world.get_world_3d().direct_space_state
	for r in interiors.restaurants:
		var rf: Transform3D = r.frame
		var outside: Vector3 = r.door
		var inside: Vector3 = r.door_inside
		var ray := PhysicsRayQueryParameters3D.create(outside + Vector3(0, 1.0, 0), inside + Vector3(0, 1.0, 0))
		check(space.intersect_ray(ray).is_empty(), "%s door is open" % r.name)
		var pickup: Vector3 = r.pickup
		ray = PhysicsRayQueryParameters3D.create(inside + Vector3(0, 1.0, 0), Vector3(pickup.x, 1.0, pickup.z))
		check(space.intersect_ray(ray).is_empty(), "%s dining room is clear to the pickup shelf" % r.name)
		var local := rf.affine_inverse() * pickup
		ray = PhysicsRayQueryParameters3D.create(rf * Vector3(local.x, 1.2, local.z + 0.3), rf * Vector3(local.x, 1.2, local.z - 1.0))
		var shelf := space.intersect_ray(ray)
		check(not shelf.is_empty() and shelf.collider.get_meta("interaction", "") == "pickup_" + str(r.id), "%s pickup shelf interaction" % r.name)
		ray = PhysicsRayQueryParameters3D.create(rf * Vector3(local.x - 3.2, 2.0, -4.0), rf * Vector3(local.x - 3.2, 2.0, -20.0))
		check(not space.intersect_ray(ray).is_empty(), "%s kitchen is closed to the public" % r.name)
	# Street names, park memorials, monument and murals.
	var signage: StreetSignage = game.world.signage
	check(signage.signs.size() >= 25, "Street-name posts at the junctions (%d)" % signage.signs.size())
	for s in signage.signs:
		check(not StreetNames.on_carriageway(Vector2(s.at.x, s.at.z), 0.3), "Street sign at %s stands off the carriageway" % s.at)
	check(signage.busts.size() == StreetNames.PARKS.size() and signage.murals.size() >= 6, "Park busts and murals")
	check(signage.monument_at.distance_to(Vector3.ZERO) > 100.0, "Atatürk Square monument placed downtown")
	check(StreetNames.describe(Vector3(0, 0, -300)) == "Mustafa Kemal Atatürk Avenue", "Avenue name lookup")
	check(StreetNames.describe(Vector3(30, 0, -398)) == "Rauf Orbay Street", "Cross street name lookup")
	check(StreetNames.describe(Vector3(-44, 0, -330)) == "Yörük Ali Efe Park", "Park name lookup")
	# Buses: three lines, shelters on sidewalks, buses move and serve their stops.
	var transit: BusSystem = game.world.buses
	check(transit.lines.size() == 3 and transit.buses.size() == 5 and transit.stops.size() >= 12, "Bus lines, buses and stops")
	for st in transit.stops:
		var kerb: Vector3 = st.kerb
		check(not StreetNames.on_carriageway(Vector2(kerb.x, kerb.z), 0.4), "Bus shelter at %s is off the road" % kerb)
		check(not CityLayout.blocked(kerb, 0.0), "Bus shelter at %s is not inside a building or lot" % kerb)
	var starts: Array[float] = []
	for bus in transit.buses: starts.append(float(bus.s))
	var served := 0
	for f in range(900):
		await physics_frame
		for bus in transit.buses:
			if bus.state == "dwell": served += 1
	for i in range(transit.buses.size()):
		check(absf(float(transit.buses[i].s) - starts[i]) > 5.0 or transit.buses[i].state == "dwell", "Bus %d is moving along its line" % i)
	check(served > 0, "Buses dwell at stops")
	# Animals: dog walkers, cats, flocks, gulls.
	var life: AnimalLife = game.world.animals
	check(life.dogs.size() >= 6 and life.cats.size() >= 8 and life.flocks.size() >= 10 and life.gulls.size() >= 4, "Animals populate the city")
	for c in life.cats:
		var at: Vector3 = (c.cat.root as Node3D).global_position
		check(not StreetNames.on_carriageway(Vector2(at.x, at.z), 0.0), "Cat at %s is not on the road" % at)
	# Weather: forced rain wets the streets (global shader parameter) and starts the rain.
	var weather: WeatherSystem = game.world.weather
	weather.forced = 1.0
	for f in range(5): await process_frame
	check(weather.rain > 0.9 and weather.wetness > 0.9 and weather.drops.emitting, "Rain falls and the streets get wet")
	var global_wet: Variant = RenderingServer.global_shader_parameter_get("wetness")
	check(global_wet == null or float(global_wet) > 0.9, "Wetness reaches the road shaders (headless renderer may not report it)")
	check(weather.describe().begins_with("Rain"), "HUD weather text: " + weather.describe())
	weather.forced = 0.0
	for f in range(5): await process_frame
	check(weather.rain < 0.05 and not weather.drops.emitting, "Rain stops")
	weather.forced = -1.0
	# Street furniture outside downtown.
	var furniture := {}
	for p in game.world.furniture.placed: furniture[p.asset] = furniture.get(p.asset, 0) + 1
	check(furniture.get("hydrant", 0) >= 6 and furniture.get("bike_rack", 0) >= 16 and furniture.get("storm_drain", 0) >= 20 and furniture.get("cone", 0) >= 8, "Street furniture placed: %s" % furniture)
	# Offer rotation reaches the corridor restaurants after the avenue trio.
	var session: DeliverySession = game.session
	var seen := {}
	for i in range(16):
		session.order = {}
		session.offer_position = Vector3(0, 0, 0)
		session.offer()
		seen[session.restaurant_id()] = true
	check(seen.size() == 16, "Offers rotate through all 16 restaurants (%d)" % seen.size())
	print("CITYKIT PASS: %d checks, %d failures" % [checks, failed] if failed == 0 else "CITYKIT: %d checks, %d failures" % [checks, failed])
	quit(1 if failed else 0)
