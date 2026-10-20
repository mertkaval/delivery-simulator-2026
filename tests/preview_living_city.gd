extends SceneTree
## Interactive review starts beside the cycleway; it never writes the player's save.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,720)
	var game=load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.session.calendar_minutes=14*60
	game.player.position=Vector3(478,.2,-291)
	game.player.rotation.y=.10
	game.player.bicycle.position=Vector3(477.5,.15,-294)
	game.player.bicycle.rotation.y=0
	game.session.offer_position=game.player.position
	game.world.set_time(14)
	game.close_menu()
	game.update_hud()
	game.notify("Explore Meridian  ·  E: bicycle  ·  Tab: phone  ·  M: local map")
