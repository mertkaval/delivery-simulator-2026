extends Node3D

## Smoke test for the Blender -> Godot asset pipeline: loads a GLB exported
## from Blender and prints what it contains so the MCP console capture can verify it.

const ASSET_PATH := "res://assets/props/delivery_box.glb"


func _ready() -> void:
	var packed := load(ASSET_PATH) as PackedScene
	if packed == null:
		push_error("PIPELINE_CHECK FAIL: could not load %s" % ASSET_PATH)
		get_tree().quit(1)
		return

	var asset := packed.instantiate()
	add_child(asset)
	var meshes := asset.find_children("*", "MeshInstance3D", true, false)
	for node in meshes:
		var mesh_instance := node as MeshInstance3D
		var aabb := mesh_instance.get_aabb()
		print("PIPELINE_CHECK mesh=%s size=%s surfaces=%d material=%s" % [
			mesh_instance.name, aabb.size, mesh_instance.mesh.get_surface_count(),
			mesh_instance.mesh.surface_get_material(0).resource_name])
	print("PIPELINE_CHECK OK: %d meshes loaded from %s" % [meshes.size(), ASSET_PATH])
	get_tree().quit(0 if meshes.size() > 0 else 1)
