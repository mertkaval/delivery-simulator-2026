extends Node3D
## Supplied Jetta GLI, driven by the project's CourierPlayer controller.
const MODELS = [preload("res://assets/vehicles/jetta_gli_2025/jetta_lod0.glb"), preload("res://assets/vehicles/jetta_gli_2025/jetta_lod1.glb"), preload("res://assets/vehicles/jetta_gli_2025/jetta_lod2.glb")]
const WHEEL_RADIUS := 0.3303983
const WHEELBASE := 2.6803436
var axle_nodes: Array[Node3D] = []
var front_pivots: Array[Node3D] = []
var steering_wheels: Array[Node3D] = []
var wheel_phase := 0.0
var _driver: WeakRef
var _braking := false
var _tail_materials: Array[StandardMaterial3D] = []
var _headlights: Array[SpotLight3D] = []
var _previous_lamp_state := -1
## Traffic mode: only the lightest LOD (17k tris), materials shared between all traffic cars of
## the same paint, no headlight spotlights. Set before adding to the tree.
var traffic := false
## Body paint for traffic cars (the "Gris Franela" surface); null keeps the factory colour.
var paint: Variant = null
const PAINT_KEY := "Gris Franela"
static var traffic_materials: Dictionary = {}

func _ready() -> void:
	set_meta("wheelbase", WHEELBASE)
	set_meta("wheel_radius", WHEEL_RADIUS)
	set_meta("collision_size", Vector3(1.86,1.47,4.7567))
	set_meta("collision_lift", 0.0)
	set_meta("has_vehicle_lights", true)
	var shared_materials: Dictionary = {}
	var levels: Array = [2] if traffic else [0, 1, 2]
	for level in levels:
		var model: Node3D = MODELS[level].instantiate()
		model.name = "LOD%d" % level
		add_child(model)
		for mesh in model.find_children("*", "MeshInstance3D", true, false):
			mesh.visibility_range_begin = 0.0 if traffic else [0.0,25.0,65.0][level]
			mesh.visibility_range_end = 180.0 if traffic else [25.0,65.0,180.0][level]
			for surface in range(mesh.mesh.get_surface_count()):
				var material: Material = mesh.mesh.surface_get_material(surface)
				if material == null: continue
				var key: String = material.resource_name
				var store: Dictionary = shared_materials
				if traffic:
					var pkey: String = (paint as Color).to_html() if paint != null else "factory"
					if not traffic_materials.has(pkey): traffic_materials[pkey] = {}
					store = traffic_materials[pkey]
				if not store.has(key):
					var copy: Material = material.duplicate()
					if paint != null and copy is StandardMaterial3D and key.begins_with(PAINT_KEY):
						(copy as StandardMaterial3D).albedo_color = paint
					store[key] = copy
					if not traffic and copy is StandardMaterial3D and key.begins_with("Glow Red"):
						_tail_materials.append(copy)
				mesh.set_surface_override_material(surface,store[key])
		for wheel in CityAssets.wheel_nodes(model): axle_nodes.append(wheel)
		for pivot in model.find_children("SteerFront*", "Node3D", true, false): front_pivots.append(pivot)
		for pivot in model.find_children("SteeringWheel*", "Node3D", true, false):
			pivot.set_meta("rest",pivot.transform)
			if level==0: pivot.name="SteeringWheel"
			steering_wheels.append(pivot)
	if traffic: return
	for side in [-1,1]:
		var light := SpotLight3D.new()
		light.name = "HeadlightL" if side<0 else "HeadlightR"
		light.position = Vector3(side*.63,.72,-2.22)
		light.rotation.x = -.045
		light.light_color = Color("fff7e8")
		light.spot_range = 32
		light.spot_angle = 38
		light.spot_attenuation = 1.3
		light.shadow_enabled = false
		light.light_energy = 0
		add_child(light)
		_headlights.append(light)
	_update_lights(false)

func bind_driver(driver: Node) -> void:
	_driver = weakref(driver)

func _process(_delta: float) -> void:
	if traffic: return
	var driver = _driver.get_ref() if _driver else null
	var night: bool = driver != null and driver.session != null and (driver.session.hour()<7 or driver.session.hour()>18)
	_update_lights(night)

func _update_lights(night: bool) -> void:
	var state := int(night)*2+int(_braking)
	if state==_previous_lamp_state: return
	_previous_lamp_state=state
	for light in _headlights:light.light_energy=2.0 if night else 0.0
	for material in _tail_materials:
		material.emission_energy_multiplier=3.0 if _braking else .8 if night else .15

func update_driving_visuals(signed_distance: float, steering: float, braking: bool = false) -> void:
	wheel_phase=wrapf(wheel_phase-signed_distance/WHEEL_RADIUS,-PI,PI)
	for wheel in axle_nodes: wheel.rotation.x=wheel_phase
	for pivot in front_pivots:
		var angle:=steering
		if absf(steering)>.0001:
			angle=atan(WHEELBASE/(WHEELBASE/tan(steering)+pivot.position.x))
		pivot.rotation.y=angle
	for pivot in steering_wheels:
		var rest: Transform3D = pivot.get_meta("rest")
		pivot.transform=rest*Transform3D(Basis(Vector3.BACK,clampf(-steering*14.0,-2.6,2.6)),Vector3.ZERO)
	_braking=braking
	_previous_lamp_state=-1

