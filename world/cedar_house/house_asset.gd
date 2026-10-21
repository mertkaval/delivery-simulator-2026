extends Node3D
## Self-contained house. Coordinates and physics are authored in meters.
## Import this scene into another project along with assets/ and this script.
## The interior is furnished from furnishing.json (props from assets/interiors, InteriorProps).
signal door_changed(door_name: String, is_open: bool)
var doors: Array[Dictionary] = []
## Furnishing props are only drawn within this distance (interiors only matter up close).
const FURNISHING_RANGE := 30.0
var furnishing: Array[Node3D] = []

func point(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

func _ready() -> void:
	var package_path: String = get_script().resource_path.get_base_dir()
	var definitions: Array = JSON.parse_string(FileAccess.get_file_as_string(package_path.path_join("assets/collisions.json")))
	var static_body := StaticBody3D.new()
	static_body.name = "ArchitectureCollision"
	add_child(static_body)
	for item: Dictionary in definitions:
		var shape_node := CollisionShape3D.new()
		shape_node.name = str(item.name).validate_node_name()
		if item.has("ramp"):
			var x: float = item.x
			var w: float = item.width * 0.5
			var a: float = item.y0
			var b: float = item.y1
			var low: float = item.z0
			var high: float = item.z1
			var v := PackedVector3Array([
				Vector3(x-w, 0, -a), Vector3(x+w, 0, -a),
				Vector3(x+w, 0, -b), Vector3(x-w, 0, -b),
				Vector3(x-w, low, -a), Vector3(x+w, low, -a),
				Vector3(x+w, high, -b), Vector3(x-w, high, -b)])
			var faces := PackedVector3Array()
			for i: int in [4,5,6,4,6,7,0,4,7,0,7,3,1,2,6,1,6,5,3,7,6,3,6,2]:
				faces.append(v[i])
			var ramp := ConcavePolygonShape3D.new()
			ramp.backface_collision = true
			ramp.set_faces(faces)
			shape_node.shape = ramp
		else:
			var shape := BoxShape3D.new()
			var dimensions: Array = item.d
			shape.size = Vector3(dimensions[0], dimensions[2], dimensions[1])
			shape_node.shape = shape
			shape_node.position = point(item.p)
			shape_node.rotation.y = float(item.rz)
		static_body.add_child(shape_node)
	var definitions_doors: Array = JSON.parse_string(FileAccess.get_file_as_string(package_path.path_join("assets/doors.json")))
	for item: Dictionary in definitions_doors:
		var pivot := find_child(str(item.name), true, false) as Node3D
		if pivot == null:
			push_error("Missing exported door pivot: " + str(item.name))
			continue
		var body := AnimatableBody3D.new()
		body.name = "DoorCollision"
		body.collision_layer = 1
		body.sync_to_physics = false
		pivot.add_child(body)
		var shape_node := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = Vector3(float(item.width), float(item.height), 0.075)
		shape_node.shape = shape
		shape_node.position = Vector3(float(item.width)*0.5, float(item.height)*0.5, 0)
		body.add_child(shape_node)
		body.set_meta("door_index", doors.size())
		body.set_meta("interaction", "cedar_door_%d" % doors.size())
		var opening_angle := deg_to_rad(100.0) if str(item.name) in ["DoorFrontPivot", "DoorRearPivot"] else -deg_to_rad(100.0)
		doors.append({"pivot": pivot, "body": body, "closed_angle": pivot.rotation.y, "opening_angle": opening_angle, "open": false})
	furnish(package_path.path_join("furnishing.json"))

## Place the furnishing props (house coordinates, Blender axes, yaw in degrees about up) and give
## the furniture box colliders. Small decor (snapped onto counters and shelves) has no collision.
func furnish(path: String) -> void:
	if not FileAccess.file_exists(path): return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary: return
	var root := Node3D.new()
	root.name = "Furnishing"
	add_child(root)
	var body := StaticBody3D.new()
	body.name = "FurnishingCollision"
	add_child(body)
	for item: Dictionary in (data as Dictionary).get("items", []):
		var id := str(item.id)
		if not InteriorProps.has(id): continue
		var scale_factor := float(item.get("s", 1.0))
		var xform := Transform3D(Basis(Vector3.UP, deg_to_rad(float(item.get("yaw", 0.0)))).scaled(Vector3.ONE * scale_factor), point(item.p))
		var node := InteriorProps.spawn(id, xform, FURNISHING_RANGE)
		if node == null: continue
		node.set_meta("room", str(item.get("room", "")))
		root.add_child(node)
		furnishing.append(node)
		var collide: bool = item.get("collide", InteriorProps.entry(id).get("collision", false)) and not item.get("snap", false)
		if collide: InteriorProps.add_box_collider(body, id, xform)

func toggle_door(index: int) -> void:
	if index < 0 or index >= doors.size():
		return
	doors[index].open = not doors[index].open
	door_changed.emit(str(doors[index].pivot.name), doors[index].open)

func _physics_process(delta: float) -> void:
	for door: Dictionary in doors:
		var pivot: Node3D = door.pivot
		var target: float = float(door.closed_angle) + (float(door.opening_angle) if door.open else 0.0)
		pivot.rotation.y = move_toward(pivot.rotation.y, target, delta * 1.6)

