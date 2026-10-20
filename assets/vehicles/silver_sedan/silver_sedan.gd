extends Node3D
## Blender -Y front maps to Godot +Z. Wheel centres retained in imported metadata.
const LODS = [preload("res://assets/vehicles/silver_sedan/silver_sedan_lod0.glb"), preload("res://assets/vehicles/silver_sedan/silver_sedan_lod1.glb"), preload("res://assets/vehicles/silver_sedan/silver_sedan_lod2.glb")]
func _ready() -> void:
	for i in range(3):
		var model = LODS[i].instantiate()
		model.name = "LOD%d" % i
		add_child(model)
		for mesh in model.find_children("*", "MeshInstance3D", true, false):
			mesh.visibility_range_begin = [0.0, 22.0, 55.0][i]
			mesh.visibility_range_end = [22.0, 55.0, 160.0][i]
			mesh.visibility_range_begin_margin = 2.0
			mesh.visibility_range_end_margin = 2.0
