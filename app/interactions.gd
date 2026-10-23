class_name Interactions
extends RefCounted
## What E (or a left click on foot) does, and the prompt that says so, for whatever the courier
## looks at (CourierPlayer.target()): shelves and packages, doors, the marked delivery area and the
## waiting customer, store computers and pickup counters, the shop, water, WC and home, the bicycle.

var game: GameApp

func _init(app: GameApp) -> void:
	game = app

## The interaction prompt for this frame, as "[E / Click]  Take ..." (HUD key caps).
func prompt(target: Dictionary) -> String:
	var session := game.session
	var player := game.player
	var flow := game.flow
	var text := ""
	if not target.is_empty():
		text = "[%s]  %s" % [game.use_hint(), title(target)]
	# At the door, E works by proximity (see interact): say so whatever the crosshair is on.
	if flow.drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"] and not game.sequence.running and (target.is_empty() or str(target.id).begins_with("door_") or target.id == "dropzone"):
		match flow.door_action(target):
			"dropzone": text = "[%s]  Leave %s's order in the marked area" % [game.use_hint(), session.order.get("customer", "the customer")]
			"customer": text = "[%s]  Hand the order to %s" % [game.use_hint(), session.order.get("customer", "the customer")]
	elif session.holding_package() and session.has_bag() and target.is_empty() and not game.sequence.running:
		text = "[%s]  Pack it in your backpack" % game.use_hint()
	# Riding, or next to your vehicle.
	if player.mounted:
		text = "[Space]  Brake   [%s]  %s" % [game.binding("interact"), "Exit" if ShopCatalog.is_car(session.active_vehicle) else "Dismount"]
	elif player.has_vehicle() and player.position.distance_to(player.bicycle.position) < 2:
		text = "[%s]  Ride the %s" % [game.binding("interact"), session.active_vehicle.replace("_", " ")]
	return text

## What the thing under the crosshair is called in the prompt.
func title(target: Dictionary) -> String:
	var session := game.session
	var id: String = target.id
	if id == "package":
		var info: Dictionary = target.node.get_meta("package")
		return "Take  %s  ·  %s" % [str(info.customer).to_upper(), info.ticket]
	if id == "pickup" or id.begins_with("pickup_"):
		return "Courier pickup shelf"
	if id.begins_with("cedar_door_"):
		return "Open / close house door"
	if id.begins_with("door_"):
		var mine: bool = session.order.get("state") in DeliverySession.ACTIVE and int(id.trim_prefix("door_")) == int(session.order.get("address", -1))
		return (("Knock  ·  " if session.order.get("method", "meet") == "meet" else "Leave it at the door  ·  ") if mine else "") + DeliverySession.ADDRESSES[int(id.trim_prefix("door_"))]
	if id.begins_with("kiosk_") or id.begins_with("store_") and id != "store_pickup":
		return "Use the store computer"
	if id == "store_pickup":
		var idx := int(target.node.get_meta("pickup_index", -1))
		return "Collect  " + (str(ShopCatalog.ITEMS[session.pickups[idx].id].name) if idx >= 0 and idx < session.pickups.size() else "item")
	return {"dropzone": "Leave %s's order here" % session.order.get("customer", "the"),
		"customer": "Hand the order to %s" % session.order.get("customer", "the customer"),
		"shop": "Browse delivery equipment", "home": "Rest and save"}.get(id, id)

## E / left click on foot.
func interact() -> void:
	var session := game.session
	var player := game.player
	var flow := game.flow
	if game.sequence.running: return
	if player.mounted:
		game.notify(player.toggle_bicycle())
		game.save_session()
		return
	var target := player.target()
	# At the customer's door, E works without aiming exactly: standing at the marked area
	# (leave at door) or next to the waiting customer (meet at door).
	var at_door := flow.door_action(target)
	if at_door != "":
		flow.deliver_here({"id": at_door})
		return
	# Holding an order out of the bag (after F's take-out, or picked up off the ground): one
	# press packs it.
	if session.holding_package() and session.has_bag() and (target.is_empty() or not str(target.id) in ["package", "store_pickup"] and not str(target.id).begins_with("door_") and not str(target.id).begins_with("kiosk_")):
		flow.start_pack(null)
		return
	if session.holding_package() and not session.has_bag() and player.position.distance_to(player.bicycle.position) < 2.5 and player.has_vehicle() and (target.is_empty() or not str(target.id).begins_with("door_")):
		game.notify("Loose food can't ride along: you need a delivery bag (Trail & Tool, $35). Walk it over by hand.")
		return
	if target.is_empty():
		if player.has_vehicle() and player.position.distance_to(player.bicycle.position) < 2.5:
			game.notify(player.toggle_bicycle())
			game.save_session()
		return
	var id := str(target.id)
	if id.begins_with("kiosk_") or (id.begins_with("store_") and id != "store_pickup"):
		game.menus.open_terminal(id.trim_prefix("kiosk_").trim_prefix("store_"))
		return
	if id == "store_pickup":
		game.notify(session.collect(int(target.node.get_meta("pickup_index", -1))))
		game.store_terminals.refresh()
		player.refresh_equipment()
		game.sound("item_pickup")
		game.save_session()
		return
	if id == "dropzone" or id == "customer":
		flow.deliver_here(target)
		return
	if id == "package":
		flow.take_package_node(target.node, float(target.distance))
		return
	if id.begins_with("cedar_door_"):
		game.world.cedar_house.toggle_door(int(id.trim_prefix("cedar_door_")))
		return
	if (id == "pickup" or id.begins_with("pickup_")) and session.order.get("state") not in DeliverySession.ACTIVE:
		game.show_menu("food")
		return
	if id == "shop":
		game.menus.current_shop = "equipment"
		game.show_menu("shop")
		return
	var result := use(target)
	if result != "":
		game.notify(result)
		game.save_session()

## The rest: water, WC, the pickup counter with an order, doors, rest at home. Returns the message.
func use(target: Dictionary) -> String:
	var session := game.session
	var id := str(target.id)
	if id == "wc":
		return session.consume("wc")
	if id == "water":
		session.hydration = 100
		session.bladder = minf(100, session.bladder + 8)
		return "Drinking water replenished."
	if id == "pickup" or id.begins_with("pickup_"):
		var rid := "cedar_kitchen" if id == "pickup" else id.trim_prefix("pickup_")
		if session.order.get("state") == "ACCEPTED" and rid == session.restaurant_id():
			return "Find the package tagged %s · %s (%s) and take it (%s)." % [str(session.order.get("customer", "?")).to_upper(), session.order.get("ticket", "?"), OrderDetails.package_label(str(session.order.get("kind", "bag")), session.order.get("items", [])).to_lower(), game.use_hint()]
		if session.order.get("state") == "ACCEPTED":
			return "This is not your pickup restaurant. Collect at " + session.restaurant_name() + "."
		return "Your order is already with you. Deliver it to " + str(session.order.get("customer", "the customer")) + "."
	if id.begins_with("door_"):
		if game.tutorial.gate("deliver") != "" and session.order.get("state") in DeliverySession.ACTIVE:
			return game.tutorial.gate("deliver")
		if session.order.get("state") in ["IN_HAND", "CARRYING", "DROPPED"] and int(id.trim_prefix("door_")) == int(session.order.address):
			return game.flow.at_door()
		var was_packed: bool = session.order.get("state") == "CARRYING"
		var result := session.deliver(int(id.trim_prefix("door_")), target.distance)
		if session.order.get("state") == "COMPLETED":
			if was_packed:
				if not is_instance_valid(game.bag_rig.contents): game.bag_rig.show_contents(game.flow.package_model(), "top")
				game.bag_rig.handover()
			game.show_menu("receipt")
		return result
	if id == "home":
		if session.order.get("state") in DeliverySession.ACTIVE:
			return "Finish your active delivery before resting."
		session.energy = 100.0
		session.bladder = 0
		session.calendar_minutes = (floor(session.calendar_minutes / 1440.0) + 1.0) * 1440.0 + 480.0
		session.schedule_offer()
		return "Good morning. Rested until 08:00. Energy restored."
	return ""
