class_name PropKit
extends RefCounted
## Converted Sketchfab props (tools/prepare_prop_packs.py, assets/sketchup/props/catalog.json):
## street furniture, road signs and barriers, plants and restaurant fittings. Each prop is a
## static GLB in metres, origin at the footprint centre on the ground, front facing Godot +Z.

const CATALOG := "res://assets/sketchup/props/catalog.json"
static var _catalog: Dictionary = {}
static var _parts: Dictionary = {}

static func catalog() -> Dictionary:
	if _catalog.is_empty() and FileAccess.file_exists(CATALOG):
		var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
		if data is Dictionary:
			for p in (data as Dictionary).get("props", []): _catalog[p.id] = p
	return _catalog

static func has(id: String) -> bool:
	return catalog().has(id) and ResourceLoader.exists(String(catalog()[id].path))

## Footprint/height in metres (x width, y height, z depth).
static func size(id: String) -> Vector3:
	var s: Array = catalog()[id].size
	return Vector3(s[0], s[1], s[2])

static func solid(id: String) -> bool:
	return bool(catalog()[id].get("collision", false))

## Mesh pieces ({"mesh", "transform", "material"}) for MultiMesh batching, like UrbanKit parts.
static func get_parts(id: String) -> Array:
	if not _parts.has(id):
		var node: Node = load(String(catalog()[id].path)).instantiate()
		var list: Array = []
		collect(node, Transform3D.IDENTITY, list)
		node.free()
		_parts[id] = list
	return _parts[id]

static func collect(node: Node, parent: Transform3D, out: Array) -> void:
	var t := parent
	if node is Node3D: t = parent * (node as Node3D).transform
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		out.append({"mesh": (node as MeshInstance3D).mesh, "transform": t, "material": null})
	for child in node.get_children(): collect(child, t, out)

## A standalone instance (for one-off placements outside the batched street furniture).
static func create(id: String, visibility := 120.0) -> Node3D:
	var node: Node3D = load(String(catalog()[id].path)).instantiate()
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).visibility_range_end = visibility
		(mesh as MeshInstance3D).visibility_range_end_margin = 8.0
	return node
