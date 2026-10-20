extends "res://app/app_root.gd"
## Full delivery-city sandbox with the new car. Deliberately disables save writes.
func _ready() -> void:
	save_enabled = false
	session.active_vehicle = "hatchback"
	session.inventory.append("hatchback")
	session.online = false
	var driver := CourierPlayer.new()
	driver.name = "CourierPlayer"
	driver.vehicle_scene_override = preload("res://assets/vehicles/repaired_car/repaired_car.tscn")
	add_child(driver)
	super._ready()
	close_menu()
	player.replace_vehicle(Vector3(1.95,.04,-60))
	player.position = Vector3(1.95,.04,-60)
	player.rotation = Vector3.ZERO
	player.mounted = true
	player.apply_vehicle_camera()
	player.camera.fov = 65
	notify("Repaired car drive · WASD · Space brake · E exit · Saves disabled")

