class_name PackageFlow
extends Node
## The order's package from shelf to door: taking it (off the shelf or the ground), packing it in
## the backpack (one press, CourierSequence), carrying it in the hands, putting it down (G), the
## backpack's drag-and-drop compartments, the marked delivery area at the customer's door, and the
## delivery itself: leave at door (proof photo) or meet at door (handover), with the payout.

var game: GameApp
var held_package: Node3D
var dropped_package: Node3D
var drop_zone: DropZone
var _pickup_from: Variant = null      ## Transform3D a freshly held package flies in from
var _held_for := ""
var _zone_for := ""
var drag_slot := ""                   ## bag compartment under the mouse while the backpack is open

func setup(app: GameApp) -> void:
	game = app

## A new game or a loaded save: no packages left over from the last one.
func reset() -> void:
	if dropped_package: dropped_package.queue_free()
	dropped_package = null

# --- Per frame --------------------------------------------------------------------------------

## The world follows the order: the package on the ground while DROPPED, the marked area at the
## door while you have the package.
func sync_world() -> void:
	sync_dropped()
	sync_drop_zone()

## The marked delivery area at the active order's door (shown once you have the package).
func sync_drop_zone() -> void:
	var session := game.session
	var state: String = session.order.get("state", "")
	var id: String = session.order.get("id", "")
	var want: bool = state in ["IN_HAND", "DROPPED", "CARRYING"]
	if want and (drop_zone == null or _zone_for != id or drop_zone.method != str(session.order.get("method", "meet"))):
		if drop_zone: drop_zone.clear()
		var address := int(session.order.address)
		drop_zone = DropZone.new()
		drop_zone.name = "DropZone"
		game.world.add_child(drop_zone)
		drop_zone.setup(address, game.world.doors[address], CityCatalog.address_facing(address), str(session.order.get("method", "meet")))
		_zone_for = id
	elif not want and drop_zone != null and drop_zone.customer == null:
		drop_zone.clear()
		drop_zone = null
		_zone_for = ""

## Keep a package model on the ground while the order is DROPPED (also after loading a save).
func sync_dropped(fall_from: Variant = null) -> void:
	var down: bool = game.session.order.get("state") == "DROPPED"
	if down and dropped_package == null:
		var a: Array = game.session.order.get("dropped_at", [0, 0, 0, 0])
		dropped_package = package_model()
		dropped_package.collision_layer = 1
		dropped_package.name = "DroppedPackage"
		game.world.add_child(dropped_package)
		var rest := Transform3D(Basis(Vector3.UP, float(a[3])), Vector3(float(a[0]), float(a[1]), float(a[2])))
		if fall_from is Transform3D:
			dropped_package.global_transform = fall_from
			var tw := create_tween()
			tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			tw.tween_property(dropped_package, "global_transform", rest, 0.35)
		else:
			dropped_package.global_transform = rest
	elif not down and dropped_package != null:
		dropped_package.queue_free()
		dropped_package = null

## The package in your hands (bottom-right of the view) while it is out of the bag.
func update_held_package() -> void:
	if game.sequence.running: return       # the sequence moves the package itself
	var session := game.session
	var want: bool = session.holding_package() and not game.player.mounted
	var id: String = str(session.order.get("id", ""))
	if want and (held_package == null or _held_for != id):
		if held_package: held_package.queue_free()
		var info := {"customer": session.order.customer, "ticket": session.order.ticket, "kind": session.order.kind, "items": session.order.items, "restaurant": session.restaurant_id()}
		var body := game.shelves.make_package(info)
		body.collision_layer = 0
		held_package = body
		game.player.hold_socket.add_child(held_package)
		_held_for = id
		if _pickup_from is Transform3D:
			held_package.global_transform = _pickup_from
			to_hands(held_package)
		else:
			held_package.transform = CourierPlayer.HOLD_POSE
	_pickup_from = null
	if held_package: held_package.visible = want

## A fresh model of the current order's package (with its logo and receipt).
func package_model() -> Node3D:
	var session := game.session
	var info := {"customer": session.order.get("customer", ""), "ticket": session.order.get("ticket", ""), "kind": session.order.get("kind", "bag"), "items": session.order.get("items", []), "restaurant": session.restaurant_id(),
		"subtotal": session.order.get("subtotal", 0), "payment_method": session.order.get("payment_method", ""), "address": int(session.order.get("address", 0))}
	var body := game.shelves.make_package(info)
	body.collision_layer = 0
	return body

## Animate a package (child of the player's hold socket) into the hands: two hands, low and to the
## right of the view (CourierPlayer.HOLD_POSE; in third person the same pose is the character's).
func to_hands(node: Node3D) -> void:
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(node, "transform", CourierPlayer.HOLD_POSE, 0.4)

func _let_go() -> void:
	held_package = null
	_held_for = ""

# --- Taking and packing -----------------------------------------------------------------------

## Take a package off the shelf (or the ground). Yours: picked up, then packed in the backpack
## in one go (CourierSequence.pack) when you own the bag, else carried by hand. Someone else's:
## who it is for and who you are looking for.
func take_package_node(node: Node3D, distance: float) -> void:
	var session := game.session
	var info: Dictionary = node.get_meta("package")
	var result := session.take_package(info, distance)
	if not session.holding_package():
		game.notify(result)
		if result.begins_with("This one is for"):
			game.sound("ui_reject")
			game.hud.flash_notice(Color("ffb4a2"))
		return
	_pickup_from = node.global_transform
	if node == dropped_package:
		dropped_package = null
		node.queue_free()
	else:
		game.shelves.take(node)
	game.sound("item_pickup")
	game.save_session()
	if session.has_bag():
		# Straight into the backpack: the order waits where it was until the hand takes it.
		var from: Transform3D = _pickup_from
		_pickup_from = null
		game.notify(result + " Packing it in your backpack…")
		start_pack(node.global_position, from)
	else:
		update_held_package()
		game.notify(result + " No delivery bag: carry it by hand (Trail & Tool sells one for $35).")

## One press: the held package goes into the backpack compartment that fits it.
func start_pack(toward: Variant, from: Variant = null) -> void:
	var session := game.session
	var player := game.player
	if game.sequence.running or not session.holding_package() or not session.has_bag(): return
	var slot := OrderDetails.best_slot(str(session.order.get("kind", "bag")))
	var pkg: Node3D = held_package
	if not is_instance_valid(pkg):
		pkg = package_model()
		game.world.add_child(pkg)
		pkg.global_transform = from if from is Transform3D else Transform3D(Basis.IDENTITY, player.global_position + player.body_forward() * 0.4 + Vector3(0, 1.0, 0))
	_let_go()
	var face: Vector3 = toward if toward is Vector3 else player.global_position + player.body_forward()
	await game.sequence.pack(pkg, slot, face, func() -> void:
		var msg := session.stow(slot)
		if session.order.get("state") == "CARRYING":
			game.notify("%s  Deliver to %s · %s." % [msg.get_slice(".", 0) + ".", session.order.get("customer", ""), DeliverySession.ADDRESSES[int(session.order.address)]])
		else:
			game.notify(msg)
		game.save_session(), toward is Vector3 and (toward as Vector3).y - player.global_position.y < 0.6)

## G: put the held package down on the ground (or a counter) just in front of you.
func drop_held() -> void:
	var session := game.session
	var player := game.player
	if not session.holding_package():
		game.notify("You're not holding anything.")
		return
	var forward := player.body_forward()
	var from := player.global_position + forward * 0.8 + Vector3(0, 1.4, 0)
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -3.0, 0))
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
		game.notify("There's no flat spot to put it down here.")
		return
	var start: Variant = held_package.global_transform if is_instance_valid(held_package) else null
	var result := session.drop_package(hit.position, player.body_yaw())
	if session.order.get("state") == "DROPPED":
		if is_instance_valid(held_package): held_package.queue_free()
		_let_go()
		sync_dropped(start)
		game.tutorial.event("dropped")
		game.sound("package_drop")
		game.save_session()
		if drop_zone and session.order.get("method", "meet") == "door" and drop_zone.contains(hit.position) and game.tutorial.gate("deliver") == "":
			complete_left()
			return
	game.notify(result)

# --- Backpack (F) -----------------------------------------------------------------------------

## Backpack open: the held package follows the mouse; the compartment under it lights up
## (green: it fits, red: it doesn't). A packed compartment lights up to be taken out.
func update_bag_drag(delta: float) -> void:
	var session := game.session
	var bag_rig := game.bag_rig
	if not bag_rig.out or not session.has_bag():
		drag_slot = ""
		return
	var camera := game.player.camera
	var mouse := get_viewport().get_mouse_position()
	var origin := camera.project_ray_origin(mouse)
	var direction := camera.project_ray_normal(mouse)
	var slot := bag_rig.pick(origin, direction)
	var kind: String = session.order.get("kind", "bag")
	if session.holding_package():
		drag_slot = slot
		bag_rig.highlight(slot, OrderDetails.fits(kind, slot))
		if is_instance_valid(held_package):
			var goal := bag_rig.slot_mouth(slot) if slot != "" else origin + direction * 0.62
			held_package.global_position = held_package.global_position.lerp(goal, minf(1.0, delta * 14.0))
	else:
		var packed: String = session.order.get("slot", "") if session.order.get("state") == "CARRYING" else ""
		drag_slot = slot if slot == packed else ""
		bag_rig.highlight(drag_slot, true)
	Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND if drag_slot != "" else Input.CURSOR_ARROW)

## The backpack closes: nothing under the mouse; a held package goes back into the hands.
func end_bag_drag() -> void:
	drag_slot = ""
	Input.set_default_cursor_shape(Input.CURSOR_ARROW)
	if is_instance_valid(held_package) and game.session.holding_package(): to_hands(held_package)

## Bag compartment clicked: pack the held package there, or take the packed one out.
func bag_click(slot: String) -> void:
	var session := game.session
	var bag_rig := game.bag_rig
	var result := ""
	if session.holding_package() and game.tutorial.gate("stow") != "":
		game.notify(game.tutorial.gate("stow"))
		return
	if session.holding_package():
		result = session.stow(slot)
		if session.order.get("state") == "CARRYING":
			# The package goes from your hands into the open bag's compartment.
			if not is_instance_valid(held_package):
				# Still flying into the hands (the bag opened the same frame): make it now.
				session.order.state = "IN_HAND"
				update_held_package()
				session.order.state = "CARRYING"
			var pkg: Node3D = held_package if is_instance_valid(held_package) else package_model()
			_let_go()
			bag_rig.pack(pkg, slot)
			game.sound("package_place")
	elif session.order.get("state") == "CARRYING" and session.order.get("slot", "") == slot:
		result = session.unstow()
		# Lift it out of the compartment back into your hands.
		var node := bag_rig.take_out()
		if node:
			game.player.hold_socket.add_child(node)
			node.global_transform = node.get_meta("from")
			held_package = node
			_held_for = str(session.order.get("id", ""))
			to_hands(node)
	else:
		result = "Empty compartment." if session.has_bag() else "You don't own a delivery bag yet."
	game.notify(result)
	game.save_session()
	if game.mode == "bag": game.show_menu("bag")

# --- At the door ------------------------------------------------------------------------------

## Standing at (or in) the marked delivery area.
func near_zone(radius: float) -> bool:
	if drop_zone == null: return false
	var p := game.player.position
	return Vector2(p.x - drop_zone.global_position.x, p.z - drop_zone.global_position.z).length() < radius and absf(p.y - drop_zone.global_position.y) < 1.6

## What E does at the customer's door by proximity, whatever the crosshair is on: "dropzone"
## (leave at door, standing in the marked area), "customer" (next to the waiting customer) or "".
func door_action(target: Dictionary) -> String:
	var session := game.session
	if drop_zone == null or not session.order.get("state") in ["IN_HAND", "CARRYING"]: return ""
	if not (target.is_empty() or str(target.id).begins_with("door_") or target.id == "dropzone"): return ""
	if drop_zone.method == "door" and near_zone(3.0): return "dropzone"
	if drop_zone.customer != null and game.player.position.distance_to(drop_zone.customer.global_position) < 2.6: return "customer"
	return ""

## E on the customer's door: knock for "meet at door"; for "leave at door" it is left in the
## marked area in front of the door.
func at_door() -> String:
	var session := game.session
	var player := game.player
	if session.order.get("method", "meet") == "door":
		if drop_zone and session.order.get("state") in ["IN_HAND", "CARRYING"]:
			deliver_here({"id": "dropzone"})
			return ""
		return "Leave it in the yellow marked area in front of the door (%s there)." % game.use_hint()
	if drop_zone and drop_zone.customer == null:
		# Every other house has a doorbell: ring it (Press_Doorbell, pressed at 0.47 s), else knock
		# (Knock_Door, knuckles on the door from 0.53 s). The courier turns to the door first and
		# waves when the customer opens it.
		var bell := drop_zone.address % 2 == 1
		var to_door := drop_zone.door_point - player.global_position
		var yaw := atan2(-to_door.x, -to_door.z)
		var played := player.avatar.play_gesture("doorbell" if bell else "knock_door", yaw) if player.avatar != null else -1.0
		var lead := (0.47 if bell else 0.5) if played > 0.0 else 0.0
		var tw := create_tween()
		tw.tween_interval(lead)
		tw.tween_callback(game.sound.bind("doorbell" if bell else "door_knock"))
		tw.tween_interval(1.1 - lead)                  # the door opens 1.1 s after the press
		tw.tween_callback(func() -> void:
			if drop_zone:
				drop_zone.call_customer(session.order)
				game.sound("door_open")
				if player.avatar != null: player.avatar.play_gesture("wave", yaw))
		return "You ring the doorbell…" if bell else "You knock on the door…"
	return "%s is at the door. Hand the order over with %s." % [session.order.get("customer", "The customer"), game.use_hint()]

## Delivery at the door, one press: leave at door (into the marked area, proof photo) or meet at
## door (hand it to the customer), out of the backpack or from your hands (CourierSequence).
func deliver_here(target: Dictionary) -> void:
	var session := game.session
	var state: String = session.order.get("state", "")
	if not state in ["IN_HAND", "CARRYING", "DROPPED"] or drop_zone == null or game.sequence.running:
		return
	if game.tutorial.gate("deliver") != "":
		game.notify(game.tutorial.gate("deliver"))
		return
	if state == "DROPPED":
		game.notify("Pick the order up first (%s on it)." % game.use_hint())
		return
	var from_bag := state == "CARRYING"
	var slot: String = str(session.order.get("slot", OrderDetails.best_slot(str(session.order.get("kind", "bag")))))
	var pkg: Node3D = package_model() if from_bag else held_package
	if not from_bag: _let_go()
	if target.id == "dropzone":
		if session.order.get("method", "meet") != "door":
			game.notify("This customer wants to meet you. Knock on the door (%s)." % game.use_hint())
			if not from_bag: held_package = pkg
			return
		# Set down in the middle of the lines, its name tag towards the street.
		var spot := Transform3D(Basis(Vector3.UP, drop_zone.rotation.y), drop_zone.global_position + Vector3(0, 0.005, 0))
		await game.sequence.leave(pkg, from_bag, slot, spot, func(node: Node3D) -> void:
			if session.order.get("state") == "CARRYING": session.unstow()
			session.drop_package(spot.origin, spot.basis.get_euler().y)
			dropped_package = node
			if dropped_package and not dropped_package.is_inside_tree(): game.world.add_child(dropped_package)
			complete_left())
		if session.order.get("state") == "COMPLETED": game.show_menu("receipt")
	elif target.id == "customer":
		var who: Node3D = drop_zone.customer
		await game.sequence.meet(pkg, from_bag, slot, who, func(node: Node3D) -> void:
			var result := session.deliver(int(session.order.address), 1.0)
			if session.order.get("state") == "COMPLETED":
				if drop_zone: drop_zone.customer_leaves(node)
				delivered("meet", false)
			else:
				if node: node.queue_free()
				game.notify(result))
		if session.order.get("state") == "COMPLETED": game.show_menu("receipt")

## Package down inside the lines: proof photo and payout.
func complete_left() -> void:
	var session := game.session
	if drop_zone == null or session.order.get("state") != "DROPPED": return
	if not drop_zone.contains(session.dropped_position()): return
	var result := session.leave_at_door(int(session.order.address), true)
	if session.order.get("state") == "COMPLETED":
		game.hud.flash_photo()
		game.sound("photo_shutter")
		var left := dropped_package
		dropped_package = null
		if left:
			var tw := left.create_tween()
			tw.tween_interval(3.0)
			tw.tween_callback(left.queue_free)
		delivered("door", not game.sequence.running)
	else:
		game.notify(result)

func delivered(method: String, show_receipt_now := true) -> void:
	var session := game.session
	game.sound("delivery_success")
	if method == "meet": game.sound("customer_thanks")
	var tw := create_tween()
	tw.tween_interval(0.5)
	tw.tween_callback(game.sound.bind("coins"))
	session.receipt += "\n" + ("Photo proof sent to %s." % session.order.get("customer", "the customer") if method == "door" else "Handed to %s in person." % session.order.get("customer", "the customer"))
	game.save_session()
	if show_receipt_now: game.show_menu("receipt")
	else: game.notify("Delivered to %s!" % session.order.get("customer", "the customer"))
