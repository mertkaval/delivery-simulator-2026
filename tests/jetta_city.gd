extends "res://app/app_root.gd"
## Full-city Jetta sandbox; no player save is loaded or written.
func _ready() -> void:
	save_enabled=false
	session.active_vehicle="sedan"
	session.inventory.append("sedan")
	session.online=false
	super._ready()
	close_menu()
	player.replace_vehicle(Vector3(1.95,.04,-60))
	player.position=Vector3(1.95,.04,-60)
	player.rotation=Vector3.ZERO
	player.mounted=true
	player.apply_vehicle_camera()
	player.camera.fov=65
	notify("Jetta GLI · WASD drive · Space brake · E exit · Saves disabled")
