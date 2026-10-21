extends SceneTree
## Renders the main-menu collage stills from the real game world into ui/menu/:
## city at golden hour, a courier cycling, the pickup shelf, and a doorstep delivery moment.
##   Godot_console.exe --path . --script res://tools/render_menu_collage.gd

func _initialize() -> void: call_deferred("run")

func shot(name: String) -> void:
	for i in range(12): await process_frame
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://ui/menu"))
	img.save_jpg("res://ui/menu/%s.jpg" % name, 0.9)
	print("SAVED ", name)

func run() -> void:
	root.size = Vector2i(1600, 900)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	var cam := Camera3D.new()
	world.add_child(cam)
	cam.current = true
	cam.fov = 50
	for i in range(30): await physics_frame
	# 1. The city at golden hour.
	world.set_time(17.2)
	cam.position = Vector3(-30, 55, 70)
	cam.look_at(Vector3(120, 0, -260))
	await shot("collage_city")
	# 2. A courier cycling down the avenue bike lane.
	world.set_time(10.5)
	var life: Node = world.get_node("CityLife")
	var rider: Node3D = life.cyclists[0].body
	for i in range(60): await physics_frame
	cam.fov = 40
	cam.position = rider.global_position + Vector3(-4.5, 1.3, -3.5)
	cam.look_at(rider.global_position + Vector3(0, 1.0, 0))
	await shot("collage_ride")
	# 3. The courier pickup shelf: named orders waiting under the menu board.
	world.set_time(13.0)
	var s := DeliverySession.new()
	var shelves := PickupShelves.new()
	world.add_child(shelves)
	shelves.setup(world, s)
	var rid: String = world.restaurants.restaurants[2].id
	var frame: Transform3D = shelves.shelves[rid].frame
	cam.fov = 50
	cam.position = frame * Vector3(-0.9, 1.45, 1.6)
	cam.look_at(frame * Vector3(0, 0.9, 0))
	await shot("collage_pickup")
	# 4. The delivery moment: courier hands a branded food bag to a customer at a lobby door.
	world.set_time(17.6)
	var door: Vector3 = world.doors[4]
	var out := Vector3(-signf(door.x), 0, 0)
	door = Vector3(door.x, 0.08, door.z) + out * 2.9   # foot of the porch steps
	var courier: LivingCitizen = LivingAssets.humanoid(0)
	var customer: LivingCitizen = LivingAssets.humanoid(2)
	world.add_child(courier)
	world.add_child(customer)
	customer.position = door + out * 0.2
	courier.position = door + out * 1.2
	courier.look_at(customer.position, Vector3.UP)
	customer.look_at(courier.position, Vector3.UP)
	for c in [courier, customer]: c.set_process(false)
	courier.players[0].play("Interact")
	courier.players[0].seek(0.9, true)
	customer.players[0].play("Talk")
	customer.players[0].seek(1.2, true)
	var bag := shelves.make_package({"customer": "Elif Kaya", "ticket": "KE-221", "kind": "bag", "items": [["Adana Kebab", 1, 1280]], "restaurant": "cedar_kitchen"})
	world.add_child(bag)
	bag.global_position = door + out * 0.72 + Vector3(0, 0.86, 0)
	bag.look_at(bag.global_position + out.cross(Vector3.UP), Vector3.UP)
	var side := out.cross(Vector3.UP)
	cam.fov = 40
	cam.position = door + out * 4.6 + side * 2.6 + Vector3(0, 1.45, 0)
	cam.look_at(door + out * 0.7 + Vector3(0, 1.2, 0))
	await shot("collage_delivery")
	quit()
