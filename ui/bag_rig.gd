class_name BagRig
extends Node3D
## The insulated delivery bag worn as a backpack, seen in first person.
## F: the bag swings off your back into view in front of you with its front flap dropped open
## (black courier backpack, foil-lined shelves); packing an order slides the held package into its
## compartment; closing swings the bag back onto your shoulders.
## Handing an order over at a door briefly brings the bag round and lifts the package out.

const OPEN_MODEL := "res://assets/delivery/delivery_bag_open.glb"
var SHOWN := Transform3D(Basis.from_euler(Vector3(0.12, 0.38, 0.0)), Vector3(-0.15, -0.42, -0.98))
var HIDDEN := Transform3D(Basis.from_euler(Vector3(1.25, 0.0, 0.55)), Vector3(0.35, -1.25, -0.25))
const SLOT_KEYS := {"top": "top", "left": "middle_left", "right": "middle_right", "bottom": "bottom"}

var bag: Node3D
var compartments: Dictionary = {}
var contents: Node3D
var _tween: Tween
var out := false
var _glow: MeshInstance3D
var _glow_mat: StandardMaterial3D

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS     # animates while the bag screen pauses the game
	if not ResourceLoader.exists(OPEN_MODEL): return
	bag = load(OPEN_MODEL).instantiate()
	add_child(bag)
	bag.scale = Vector3.ONE * 0.9
	# glTF extras sit on the Blender root empty (DeliveryBag), a child of the scene root.
	for n: Node in [bag] + bag.get_children():
		var extras: Variant = n.get_meta("extras", {})
		if extras is Dictionary and (extras as Dictionary).has("compartments"):
			compartments = (extras as Dictionary)["compartments"]
	transform = HIDDEN
	visible = false
	for mi in bag.find_children("*", "GeometryInstance3D", true, false):
		(mi as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

func animate(to: Transform3D, seconds: float, then: Callable = Callable()) -> void:
	if _tween: _tween.kill()
	_tween = create_tween()
	_tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_tween.tween_property(self, "transform", to, seconds)
	if then.is_valid(): _tween.tween_callback(then)

## Swing the bag off the back into view (flap open).
func take_off() -> void:
	if bag == null: return
	visible = true
	out = true
	animate(shown(), 0.45)

## SHOWN, pulled towards the camera and scaled down by the same factor when a wall, shelf or
## counter is close ahead, so the bag looks the same size but never pokes into the world.
func shown() -> Transform3D:
	var f := clearance_factor()
	return Transform3D(SHOWN.basis.scaled(Vector3.ONE * f), SHOWN.origin * f)

func clearance_factor() -> float:
	var cam := get_parent() as Node3D
	if cam == null or not is_inside_tree(): return 1.0
	var space := get_world_3d().direct_space_state
	var exclude: Array[RID] = []
	var body := cam.get_parent() as CollisionObject3D
	if body: exclude.append(body.get_rid())
	var deepest := 1.0
	# Rays to the far corners of the bag at full size (bag back ~0.36 m behind its front).
	for corner: Vector3 in [Vector3(0.0, 0.0, -0.36), Vector3(-0.26, 0.0, -0.36), Vector3(0.26, 0.0, -0.36), Vector3(0.0, 0.5, -0.36), Vector3(0.26, 0.5, -0.36), Vector3(-0.26, 0.5, -0.36)]:
		var local := SHOWN * corner
		var from := cam.global_position
		var to := cam.global_transform * local
		var q := PhysicsRayQueryParameters3D.create(from, to + (to - from).normalized() * 0.08)
		q.exclude = exclude
		var hit := space.intersect_ray(q)
		if not hit.is_empty():
			deepest = minf(deepest, from.distance_to(hit.position) / (from.distance_to(to) + 0.08))
	return clampf(deepest * 0.96, 0.25, 1.0)

## Swing it back onto the shoulders.
func put_on() -> void:
	if bag == null or not out: return
	highlight("", false)
	out = false
	animate(HIDDEN, 0.4, func(): visible = false)

## Show what is packed: a scaled copy of the package in its compartment.
func show_contents(package: Node3D, slot: String) -> void:
	clear_contents()
	if package == null or bag == null or slot == "": return
	contents = package
	if contents.get_parent(): contents.get_parent().remove_child(contents)
	bag.add_child(contents)
	var c: Dictionary = compartments.get(SLOT_KEYS.get(slot, "top"), {})
	var centre: Vector3 = vec(c.get("center", null), Vector3(0, 0.3, 0))
	var size: Vector3 = vec(c.get("size", null), Vector3(0.38, 0.17, 0.3))
	# Fit the package into the compartment: upright, or laid on its back when that fits better
	# (a tall bag lies down in a low bay), scaled down only if it still does not fit.
	var aabb := Vector3(0.27, 0.32, 0.17)
	for mi in contents.find_children("*", "MeshInstance3D", true, false):
		aabb = (mi as MeshInstance3D).get_aabb().size
		break
	var upright := fit_scale(size, aabb)
	var laid := fit_scale(size, Vector3(aabb.x, aabb.z, aabb.y))
	var rot := Basis.IDENTITY
	var lay := laid > upright + 0.02
	if lay:
		rot = Basis(Vector3.RIGHT, -PI / 2)      # front faces up, top towards the back wall
		upright = laid
	var s := minf(1.0, upright * 0.94)
	var at := centre - Vector3(0, size.y * 0.5, 0)
	if lay: at += Vector3(0, aabb.z * 0.5 * s, aabb.y * 0.5 * s)
	contents.transform = Transform3D(rot.scaled(Vector3.ONE * s), at)

static func fit_scale(room: Vector3, item: Vector3) -> float:
	return minf(room.x / maxf(item.x, 0.01), minf(room.y / maxf(item.y, 0.01), room.z / maxf(item.z, 0.01)))

## Drop a package from the hands into the compartment (animated), then keep it there.
func pack(package: Node3D, slot: String) -> void:
	if bag == null or package == null: return
	var start := package.global_transform
	show_contents(package, slot)
	var end := contents.transform
	contents.global_transform = start
	var t := create_tween()
	t.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	t.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	t.tween_property(contents, "transform", end, 0.45)

func clear_contents() -> void:
	if is_instance_valid(contents): contents.queue_free()
	contents = null

## Delivery: bag comes round, the package lifts out towards the customer, bag goes back.
func handover() -> void:
	if bag == null: return
	visible = true
	out = true
	if _tween: _tween.kill()
	_tween = create_tween()
	_tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_tween.tween_property(self, "transform", shown(), 0.4)
	if is_instance_valid(contents):
		var lift := contents.transform.translated(Vector3(0, 0.45, 0.5))
		_tween.tween_property(contents, "transform", lift, 0.5)
		_tween.tween_callback(clear_contents)
	_tween.tween_property(self, "transform", HIDDEN, 0.4)
	_tween.tween_callback(func(): visible = false; out = false)

## Take the packed package back out: detached from the bag, keeping its world transform.
func take_out() -> Node3D:
	if not is_instance_valid(contents): return null
	var node := contents
	var at := node.global_transform
	node.get_parent().remove_child(node)
	contents = null
	node.top_level = false
	node.set_meta("from", at)
	return node

# --- Drag and drop into the open bag ---------------------------------------------------------

## Compartment box (bag-local centre, size) for a game slot, nudged a little out of the opening
## so aiming at the front edge still counts.
func slot_box(slot: String) -> AABB:
	var c: Dictionary = compartments.get(SLOT_KEYS.get(slot, ""), {})
	if c.is_empty(): return AABB()
	var centre: Vector3 = vec(c.get("center", null), Vector3.ZERO)
	var size: Vector3 = vec(c.get("size", null), Vector3.ZERO)
	return AABB(centre - size * 0.5, size + Vector3(0, 0, 0.06))

## The game slot under a world-space ray (mouse pointer), or "".
func pick(origin: Vector3, direction: Vector3) -> String:
	if bag == null or not out: return ""
	var inv := bag.global_transform.affine_inverse()
	var o := inv * origin
	var d := inv.basis * direction
	var best := ""
	var best_t := INF
	for slot: String in SLOT_KEYS:
		var box := slot_box(slot)
		if box.size == Vector3.ZERO: continue
		var hit: Variant = box.intersects_ray(o, d)
		if hit != null:
			var t := (hit as Vector3).distance_to(o)
			if t < best_t:
				best_t = t
				best = slot
	return best

## World position just in front of a compartment's opening (where a dragged package hovers).
func slot_mouth(slot: String) -> Vector3:
	var box := slot_box(slot)
	return bag.global_transform * (box.get_center() + Vector3(0, 0, box.size.z * 0.5 + 0.1))

## Light up the compartment under the pointer: green if the order fits there, red if not.
func highlight(slot: String, fits: bool) -> void:
	if bag == null: return
	if _glow == null:
		_glow = MeshInstance3D.new()
		_glow.mesh = BoxMesh.new()
		_glow_mat = StandardMaterial3D.new()
		_glow_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_glow_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_glow_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		_glow_mat.no_depth_test = true
		_glow.material_override = _glow_mat
		_glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		bag.add_child(_glow)
	_glow.visible = slot != ""
	if slot == "": return
	var box := slot_box(slot)
	box.size.z -= 0.06
	(_glow.mesh as BoxMesh).size = box.size * 0.96
	_glow.position = box.get_center()
	_glow_mat.albedo_color = Color(0.45, 0.95, 0.65, 0.28) if fits else Color(1.0, 0.35, 0.3, 0.28)

static func vec(v: Variant, fallback: Vector3) -> Vector3:
	if v is Array and (v as Array).size() == 3: return Vector3(float(v[0]), float(v[1]), float(v[2]))
	return fallback
