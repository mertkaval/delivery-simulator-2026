extends SceneTree
var checks := 0
var failures := 0
func check(ok: bool, message: String) -> void:
	checks+=1
	if not ok:
		failures+=1
		printerr("FAIL: "+message)
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var session := DeliverySession.new()
	check(not session.buy("scooter").contains("purchased"),"Insufficient funds cannot buy")   # $890 scooter vs the $100 start
	for i in range(1800):
		session.offer()
		session.accept()
		session.pickup(session.restaurant_id(),1)
		session.deliver(int(session.order.address),1)
	for id in ShopCatalog.ITEMS:
		if ShopCatalog.is_supply(id): continue    # supplies are bought by quantity on the store computer
		session.buy(id)
		check(session.owns(id),"Purchase "+id)
		var balance := session.wallet
		session.buy(id)
		check(session.wallet==balance,"Idempotent purchase "+id)
	session.active_vehicle="sedan"
	session.hunger=20
	session.hydration=10
	session.bladder=80
	session.consume("meal")
	session.consume("water")
	check(session.hunger==75 and session.hydration==75,"Food and water restore needs")
	session.consume("wc")
	check(session.bladder==0,"WC restores bladder")
	var saved := session.snapshot()
	check(DeliverySession.validate(saved),"Purchases and needs save validates")
	var restored := DeliverySession.new()
	check(restored.restore(saved) and restored.active_vehicle=="sedan" and restored.owns("gloves"),"Ownership and active car persist")
	var bad := saved.duplicate(true)
	bad.lifestyle.hunger=NAN
	check(not DeliverySession.validate(bad),"Reject nonfinite needs")
	bad=saved.duplicate(true)
	bad.lifestyle.inventory.erase("sedan")
	check(not DeliverySession.validate(bad),"Reject unowned active vehicle")
	var legacy := DeliverySession.new().snapshot()
	legacy.erase("lifestyle")
	check(restored.restore(legacy) and restored.active_vehicle=="bicycle","Older saves gain safe defaults")
	restored.tick(60)
	check(restored.hunger<100 and restored.hydration<100 and restored.bladder>0,"Needs change during play")
	restored.calendar_minutes=1440
	check(restored.calendar().day==17 and restored.calendar().month==9 and restored.calendar().year==2026,"Date rolls to next day")
	var game = load("res://app/app_root.tscn").instantiate()
	game.save_enabled=false
	root.add_child(game)
	game.close_menu()
	game.player.set_physics_process(false)
	await physics_frame
	game.player.position=Vector3(-7,.1,19)
	game.interact()
	check(game.player.mounted,"E interaction mounts nearby bike")
	game.interact()
	check(not game.player.mounted,"E interaction dismounts")
	var event := InputEventAction.new()
	event.action="phone"
	event.pressed=true
	game._unhandled_input(event)
	await process_frame
	check(game.mode=="phone" and game.phone.out and not game.modal.visible,"Tab raises the 3D phone")
	check(game.phone.os.page=="home","Phone opens on its home screen")
	game._unhandled_input(event)
	check(game.mode=="" and not game.phone.out,"Second Tab puts the phone away")
	for id in ShopCatalog.LOCATIONS:
		game.player.position=ShopCatalog.LOCATIONS[id]+Vector3(4,.12,2.7)
		game.player.rotation=Vector3.ZERO
		game.player.camera.rotation=Vector3(-.55,0,0)
		await physics_frame
		check(game.player.target().get("id")=="store_"+id,"Physical shop counter "+id)
	for x in [-92,92]:
		for z in [-110,-190]:
			var route := CityCatalog.route(Vector3(x,0,z+10),CityCatalog.PICKUPS[0],true)
			check(route.size()>5,"Apartment route connects through street network")
	check(game.world.park_count==8,"Eight landscaped parks including roundabouts")
	check(game.world.get_node("CityLife").pedestrians.size()>=60,"At least sixty neighbourhood pedestrians")
	check(game.world.get_node("CityLife").cyclists.size()==6,"Six cyclists")
	game.player.session=session
	game.session=session
	for id in ["commuter_bike","scooter","sedan","hatchback","suv","van","pickup"]:
		session.active_vehicle=id
		game.player.mounted=false
		game.player.replace_vehicle(Vector3(0,.15,58))
		game.player.position=Vector3(1.8,.15,58)
		await physics_frame
		var mount_message: String = game.player.toggle_bicycle()
		check(game.player.mounted,"Mount owned "+id+": "+mount_message)
		check(game.player.parked_body.collision_layer==0,"Parked collider disabled while driving "+id)
		game.player.riding_speed=0
		game.player.toggle_bicycle()
		check(not game.player.mounted and game.player.parked_body.collision_layer==1,"Dismount and restore collision "+id)
	print("LIFESTYLE PASS: %d checks, %d failures" % [checks,failures])
	quit(1 if failures else 0)
