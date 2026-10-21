class_name BagRig
extends Node3D
## The insulated delivery bag worn as a backpack, seen in first person.
## F: the bag swings off your back into view in front of you with its lid open; packing an order
## drops the held package into its compartment; closing swings the bag back onto your shoulders.
## Handing an order over at a door briefly brings the bag round and lifts the package out.

const OPEN_MODEL := "res://assets/delivery/delivery_bag_open.glb"
var SHOWN := Transform3D(Basis.from_euler(Vector3(0.75, 0.25, 0.0)), Vector3(-0.22, -0.5, -0.95))
var HIDDEN := Transform3D(Basis.from_euler(Vector3(1.25, 0.0, 0.55)), Vector3(0.35, -1.25, -0.25))
const SLOT_KEYS := {"top": "top", "left": "middle_left", "right": "middle_right", "bottom": "bottom"}

var bag: Node3D
var compartments: Dictionary = {}
var contents: Node3D
var _tween: Tween
var out := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS     # animates while the bag screen pauses the game
	if not ResourceLoader.exists(OPEN_MODEL): return
	bag = load(OPEN_MODEL).instantiate()
	add_child(bag)
	bag.scale = Vector3.ONE * 0.9
	var extras: Dictionary = bag.get_meta("extras", {}) if bag.has_meta("extras") else {}
	compartments = extras.get("compartments", {})
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

## Swing the bag off the back into view (lid open).
func take_off() -> void:
	if bag == null: return
	visible = true
	out = true
	animate(SHOWN, 0.45)

## Swing it back onto the shoulders.
func put_on() -> void:
	if bag == null or not out: return
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
	# Scale the package to sit inside the compartment (game-rule fit for the pizza drawer).
	var aabb := Vector3(0.27, 0.32, 0.17)
	for mi in contents.find_children("*", "MeshInstance3D", true, false):
		aabb = (mi as MeshInstance3D).get_aabb().size
		break
	var s := minf(1.0, minf(size.x / maxf(aabb.x, 0.01), minf(size.y / maxf(aabb.y, 0.01), size.z / maxf(aabb.z, 0.01))) * 0.92)
	contents.transform = Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * s), centre - Vector3(0, size.y * 0.5, 0))

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
	_tween.tween_property(self, "transform", SHOWN, 0.4)
	if is_instance_valid(contents):
		var lift := contents.transform.translated(Vector3(0, 0.45, 0.5))
		_tween.tween_property(contents, "transform", lift, 0.5)
		_tween.tween_callback(clear_contents)
	_tween.tween_property(self, "transform", HIDDEN, 0.4)
	_tween.tween_callback(func(): visible = false; out = false)

static func vec(v: Variant, fallback: Vector3) -> Vector3:
	if v is Array and (v as Array).size() == 3: return Vector3(float(v[0]), float(v[1]), float(v[2]))
	return fallback
