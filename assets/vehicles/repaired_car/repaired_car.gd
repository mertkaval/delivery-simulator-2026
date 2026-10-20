extends Node3D
## Articulated visuals; physics remains in CourierPlayer.
const MODELS = [preload("res://assets/vehicles/repaired_car/car_lod0.glb"), preload("res://assets/vehicles/repaired_car/car_lod1.glb"), preload("res://assets/vehicles/repaired_car/car_lod2.glb")]
const WHEEL_RADIUS := 0.34
const WHEELBASE := 2.62
var axle_nodes: Array[Node3D] = []
var front_pivots: Array[Node3D] = []
var wheel_phase := 0.0

func _ready() -> void:
	set_meta("wheelbase", WHEELBASE)
	set_meta("collision_size", Vector3(1.80, 1.47, 4.29))
	set_meta("collision_lift", 0.0)
	for level in range(3):
		var model: Node3D = MODELS[level].instantiate()
		model.name = "LOD%d" % level
		add_child(model)
		for mesh in model.find_children("*", "MeshInstance3D", true, false):
			mesh.visibility_range_begin = [0.0, 24.0, 60.0][level]
			mesh.visibility_range_end = [24.0, 60.0, 160.0][level]
			mesh.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
		for wheel in CityAssets.wheel_nodes(model): axle_nodes.append(wheel)
		for pivot in model.find_children("SteerFront*", "Node3D", true, false): front_pivots.append(pivot)

func update_driving_visuals(signed_distance: float, steering: float, _braking: bool = false) -> void:
	wheel_phase = wrapf(wheel_phase - signed_distance / WHEEL_RADIUS, -PI, PI)
	for wheel in axle_nodes: wheel.rotation.x = wheel_phase
	for pivot in front_pivots:
		var angle := steering
		if absf(steering) > 0.0001:
			var radius := WHEELBASE / tan(steering)
			# Positive steering turns toward −X. The inner wheel turns further.
			angle = atan(WHEELBASE / (radius + pivot.position.x))
		pivot.rotation.y = angle

