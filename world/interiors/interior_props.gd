class_name InteriorProps
extends RefCounted
## Interior props converted by tools/prepare_interiors.py (assets/interiors/<category>/<id>.glb,
## metadata in assets/interiors/catalog.json). Every prop is one mesh with its origin on the floor
## (wall props: centre of the back face) and its front facing +Z.
##
## Interiors only matter up close: props are drawn to `range_end` metres (default 30 m) and only
## props large enough to be worth it cast shadows.

const CATALOG := "res://assets/interiors/catalog.json"
const DEFAULT_RANGE := 30.0
## Props whose largest side is below this never cast shadows (only furniture does).
const SHADOW_MIN_SIZE := 1.0
## Small decor (cups, bottles, books ...) is only drawn this close; medium props (lamps,
## appliances, chairs) to MEDIUM_RANGE. Larger furniture uses the caller's range.
const SMALL_SIZE := 0.4
const SMALL_RANGE := 12.0
const MEDIUM_RANGE := 22.0

static var _catalog: Dictionary = {}
static var _scenes: Dictionary = {}

static func catalog() -> Dictionary:
	if _catalog.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
		if parsed is Dictionary:
			for entry: Dictionary in (parsed as Dictionary).get("props", []):
				_catalog[str(entry.id)] = entry
	return _catalog

static func entry(id: String) -> Dictionary:
	return catalog().get(id, {})

static func has(id: String) -> bool:
	return catalog().has(id)

static func scene(id: String) -> PackedScene:
	if not _scenes.has(id):
		var e := entry(id)
		var path: String = str(e.get("path", ""))
		_scenes[id] = load(path) if path != "" and ResourceLoader.exists(path) else null
		if _scenes[id] == null: push_warning("InteriorProps: missing prop " + id)
	return _scenes[id]

## Size in Godot axes (x width, y height, z depth).
static func size_of(id: String) -> Vector3:
	var s: Array = entry(id).get("size", [0.0, 0.0, 0.0])
	return Vector3(float(s[0]), float(s[1]), float(s[2]))

## Local bounding box of the prop around its origin.
static func local_box(id: String) -> AABB:
	var e := entry(id)
	var size := size_of(id)
	if e.has("bounds_min"):
		var m: Array = e.bounds_min
		return AABB(Vector3(float(m[0]), float(m[1]), float(m[2])), size)
	return AABB(Vector3(-size.x * 0.5, 0.0, -size.z * 0.5), size)

## Instantiate a prop. `shadows`: -1 = automatic (by size), 0 = off, 1 = on.
static func spawn(id: String, xform: Transform3D, range_end: float = DEFAULT_RANGE, shadows: int = -1) -> Node3D:
	var packed := scene(id)
	if packed == null: return null
	var node: Node3D = packed.instantiate()
	node.name = id.to_pascal_case()
	node.transform = xform
	var size := size_of(id) * xform.basis.get_scale()
	var largest := maxf(size.x, maxf(size.y, size.z))
	var cast := shadows == 1 or (shadows == -1 and largest >= SHADOW_MIN_SIZE)
	var end := range_end
	if largest < SMALL_SIZE: end = minf(range_end, SMALL_RANGE)
	elif largest < SHADOW_MIN_SIZE: end = minf(range_end, MEDIUM_RANGE)
	for g in node.find_children("*", "GeometryInstance3D", true, false):
		var gi := g as GeometryInstance3D
		gi.visibility_range_end = end
		gi.visibility_range_end_margin = 2.0
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

## Box collider matching the prop's bounds (optionally shrunk at the top for low furniture).
static func add_box_collider(body: StaticBody3D, id: String, xform: Transform3D, pad: float = 0.0, max_height: float = 0.0) -> CollisionShape3D:
	var box := local_box(id)
	var size := box.size - Vector3(pad, 0.0, pad) * 2.0
	if max_height > 0.0: size.y = minf(size.y, max_height)
	var centre := box.position + Vector3(box.size.x * 0.5, size.y * 0.5, box.size.z * 0.5)
	var shape := BoxShape3D.new()
	shape.size = size * xform.basis.get_scale()
	var node := CollisionShape3D.new()
	node.name = id.to_pascal_case() + "Collision"
	node.shape = shape
	node.transform = Transform3D(xform.basis.orthonormalized(), xform * centre)
	body.add_child(node)
	return node
