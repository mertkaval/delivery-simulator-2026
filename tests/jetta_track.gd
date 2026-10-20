extends "res://tests/repaired_car_track.gd"
func _ready() -> void:
	super._ready()
	player.session.active_vehicle="sedan"
	player.vehicle_scene_override=null
	player.replace_vehicle(Vector3(0,.03,5))
	reset_car()
	for layer in get_children():
		if layer is CanvasLayer:
			for label in layer.get_children():
				if label is Label and label.text.begins_with("REPAIRED CAR"):
					label.text=label.text.replace("REPAIRED CAR","VOLKSWAGEN JETTA GLI 2025")
