class_name VehicleCatalog
extends RefCounted
## Vehicles converted from sketchup_assets/ by tools/prepare_sketchup_assets.py
## (res://assets/sketchup/vehicles/<id>.glb), plus the civil service fleet and the Ace 11 prepared
## by tools/prepare_civil_vehicles.py (assets/vehicles/civil/<name>.glb for id civil_<name>,
## assets/vehicles/ace11/ace11.glb; 1024 textures). Each model follows the vehicle contract:
## wheel empties Wheel*, front wheels under SteerFront*, VehiclePaint meshes, root extras
## wheelbase / wheel_radius / length / width / height (/ collision_lift).

const DIR := "res://assets/sketchup/vehicles/%s.glb"
const CIVIL_DIR := "res://assets/vehicles/civil/%s.glb"
const ACE11 := "res://assets/vehicles/ace11/ace11.glb"
## Everyday traffic mix. "jetta" is the player's Jetta GLI in traffic mode.
const TRAFFIC := ["car_sedan", "car_hatchback", "ace11", "car_wagon", "car_suv", "car_compact", "jetta", "car_minivan",
	"car_pickup", "car_offroad", "ace11", "car_coupe", "car_sport", "sport_car", "muscle_car"]
## Service vehicles mixed into city traffic, id -> relative weight: taxis, police, post vans and
## ambulances are common; tow, road-service and garbage trucks less so; school bus, city bus and
## fire truck are rare. Vehicles longer than LONG_VEHICLE metres only go where the route allows.
const SERVICE := {"civil_taxi": 6.0, "civil_police_sedan": 3.0, "civil_postvan": 3.0, "civil_ambulance": 2.0,
	"civil_towtruck": 1.5, "civil_rdservtruck": 1.5, "civil_garbage_truck": 1.0, "civil_school_bus": 0.7,
	"civil_citybus": 0.5, "civil_fire_truck": 0.5}
const LONG_VEHICLE := 7.0
## Player-purchasable car ids (ShopCatalog / CityAssets.CAR_TYPES) mapped to converted models.
## Player and showroom cars are created with paint "" (factory finish), so the showroom car is
## exactly the car you get.
const PLAYER := {"hatchback": "car_hatchback", "suv": "car_suv", "van": "car_minivan", "pickup": "car_pickup", "ace11": "ace11"}
const SPORT_PAINTS := ["d8dcdf", "b3261e", "1f3e6e", "202224", "e1b12c"]
## Seed for the service-vehicle draw in city traffic (-1 = a new mix every session).
static var traffic_seed := -1
## Benchmark switch: true spawns the pre-street-life traffic (16 city cars on three loops, the
## downtown population's 18 cars) for before/after frame-time comparisons.
static var legacy_traffic := false

static var scenes: Dictionary = {}
static var specs: Dictionary = {}
static var paints: Dictionary = {}
static var serial := 0

static func path_of(id: String) -> String:
	if id == "ace11": return ACE11
	if id.begins_with("civil_") and ResourceLoader.exists(CIVIL_DIR % id.trim_prefix("civil_")):
		return CIVIL_DIR % id.trim_prefix("civil_")
	return DIR % id

static func exists(id: String) -> bool:
	return ResourceLoader.exists(path_of(id))

## A fresh instance with its spec stored as metadata (wheelbase, wheel_radius, collision_size...).
## `paint`: "auto" = next colour of the traffic palette, "" = factory finish, or a hex colour.
static func create(id: String, visibility := 200.0, paint := "auto") -> Node3D:
	if id == "jetta":
		var jetta: Node3D = load("res://assets/vehicles/jetta_gli_2025/jetta.tscn").instantiate()
		jetta.traffic = true
		jetta.paint = Color(CityAssets.TRAFFIC_PAINTS[CityAssets.traffic_serial % CityAssets.TRAFFIC_PAINTS.size()])
		CityAssets.traffic_serial += 1
		return jetta
	if not scenes.has(id): scenes[id] = load(path_of(id))
	var model: Node3D = scenes[id].instantiate()
	var spec := spec_of(id, model)
	for key in spec: model.set_meta(key, spec[key])
	for mesh in model.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).visibility_range_end = visibility
		(mesh as MeshInstance3D).visibility_range_end_margin = 10.0
	# Untextured paint gets a colour per car so repeated models do not look cloned.
	var paint_meshes := model.find_children("VehiclePaint*", "MeshInstance3D", true, false)
	if not paint_meshes.is_empty() and paint != "":
		var colour := Color(paint) if paint != "auto" else Color(SPORT_PAINTS[serial % SPORT_PAINTS.size()])
		if paint == "auto" and id == "ace11":
			# Everyday hatchback: factory-like colours (multiplied onto its light textured paint).
			colour = Color(CityAssets.TRAFFIC_PAINTS[CityAssets.traffic_serial % CityAssets.TRAFFIC_PAINTS.size()])
			CityAssets.traffic_serial += 1
		elif paint == "auto":
			serial += 1
		for mesh in paint_meshes:
			var m := mesh as MeshInstance3D
			for surface in range(m.mesh.get_surface_count()):
				var base := m.mesh.surface_get_material(surface)
				if not base is StandardMaterial3D: continue
				var key := "%s_%s" % [base.get_instance_id(), colour.to_html()]
				if not paints.has(key):
					var copy := (base as StandardMaterial3D).duplicate() as StandardMaterial3D
					copy.albedo_color = colour
					copy.metallic = 0.55
					copy.roughness = 0.28
					paints[key] = copy
				m.set_surface_override_material(surface, paints[key])
	return model

## Dimensions read from the glTF extras on the root (Godot keeps them as "extras" metadata).
static func spec_of(id: String, model: Node3D = null) -> Dictionary:
	if specs.has(id): return specs[id]
	if model == null:
		# create() measures and caches the spec; the probe instance is not needed afterwards.
		var probe := create(id, 200.0, "")
		probe.free()
		return specs[id]
	var extras: Dictionary = {}
	for node in [model] + model.get_children():
		if node.has_meta("extras"):
			var e: Variant = node.get_meta("extras")
			if e is Dictionary and (e as Dictionary).has("wheelbase"): extras = e
	if extras.is_empty():
		# Fall back to measuring the meshes.
		var box := AABB()
		var first := true
		for mesh in model.find_children("*", "MeshInstance3D", true, false):
			var m := mesh as MeshInstance3D
			var b := m.get_aabb()
			b = (model.global_transform.affine_inverse() * m.global_transform * b) if m.is_inside_tree() else b
			box = b if first else box.merge(b)
			first = false
		extras = {"wheelbase": box.size.z * 0.6, "wheel_radius": 0.33, "length": box.size.z, "width": box.size.x, "height": box.size.y}
	var spec := {"wheelbase": float(extras.wheelbase), "wheel_radius": float(extras.wheel_radius),
		"collision_size": Vector3(float(extras.width) * 0.96, float(extras.height), float(extras.length) * 0.97),
		"collision_lift": float(extras.get("collision_lift", 0.0)), "has_vehicle_lights": false,
		"length": float(extras.length)}
	specs[id] = spec
	return spec

## Next model of the everyday traffic mix.
static var traffic_index := 0
static func next_traffic_id() -> String:
	for attempt in range(TRAFFIC.size()):
		var id: String = TRAFFIC[traffic_index % TRAFFIC.size()]
		traffic_index += 1
		if id == "jetta" or exists(id): return id
	return "jetta"

## Weighted draw from SERVICE; `allow_long` false skips vehicles longer than LONG_VEHICLE.
static func next_service_id(rng: RandomNumberGenerator, allow_long: bool) -> String:
	var ids: Array[String] = []
	var weights: Array[float] = []
	var total := 0.0
	for id: String in SERVICE:
		if not exists(id) or (not allow_long and is_long(id)): continue
		ids.append(id)
		weights.append(float(SERVICE[id]))
		total += float(SERVICE[id])
	if ids.is_empty(): return next_traffic_id()
	var pick := rng.randf() * total
	for k in range(ids.size()):
		pick -= weights[k]
		if pick <= 0.0: return ids[k]
	return ids[-1]

static func is_long(id: String) -> bool:
	return id != "jetta" and float(spec_of(id).length) > LONG_VEHICLE

## Vehicles over 6 m (ambulance, tow truck and every long vehicle) take tighter corner arcs.
const TIGHT_TURN_LENGTH := 6.0
static func turns_tight(id: String) -> bool:
	return id != "jetta" and float(spec_of(id).length) > TIGHT_TURN_LENGTH

## Wheel spin nodes and steering pivots of a model.
static func wheels(model: Node3D) -> Array[Node3D]:
	if model.get("axle_nodes") != null: return model.axle_nodes
	return CityAssets.wheel_nodes(model)

static func steer_pivots(model: Node3D) -> Array[Node3D]:
	if model.get("front_pivots") != null: return model.front_pivots
	var out: Array[Node3D] = []
	for n in model.find_children("SteerFront*", "Node3D", true, false):
		if not n is MeshInstance3D: out.append(n)
	return out

static func dimensions(id: String, model: Node3D) -> Vector3:
	if id == "jetta": return Vector3(1.86, 1.47, 4.76)
	return spec_of(id, model).collision_size

static func wheelbase(id: String, model: Node3D) -> float:
	if id == "jetta": return 2.68
	return float(spec_of(id, model).wheelbase)

static func wheel_radius(id: String, model: Node3D) -> float:
	if id == "jetta": return 0.33
	return float(spec_of(id, model).wheel_radius)
