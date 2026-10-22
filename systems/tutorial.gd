class_name TutorialDirector
extends Node
## First-shift training, started by New Game: thirteen mandatory tasks done in order that teach
## the controls and the delivery loop on foot: the store computer and pickup shelf (phone + bag),
## the phone and its CourierNow app, finding your package among other couriers' orders (one
## press picks it up and packs it in the backpack), and both delivery methods (leave at door,
## meet at door), each one button press. Afterwards an optional goal card tracks saving up for
## the first bicycle.
## While training is running, normal dispatch is off (the director sends the first order
## itself), and rejecting, going offline or delivering before their task are refused with a
## hint (gate()). Progress lives in DeliverySession.tutorial, so it saves and resumes.
## Finishing pays a one-time bonus (DeliverySession.finish_tutorial).

const STEPS := [
	{"id": "look", "title": "Look around", "hint": "Move the mouse to look around the street."},
	{"id": "walk", "title": "Take a walk", "hint": "Walk with W A S D; hold {sprint} to jog. You start on foot: a bicycle comes later."},
	{"id": "store", "title": "Walk to Trail & Tool", "hint": "Follow the mint route on the minimap to the equipment store."},
	{"id": "order", "title": "Order a phone and a delivery bag", "hint": "Use the computer on the counter ({interact}): buy the Nova budget phone and the insulated delivery bag. You have $100."},
	{"id": "collect", "title": "Collect your order", "hint": "They wait on the ONLINE ORDER PICKUP shelf at the back of the store. Look at each and press {interact}."},
	{"id": "phone", "title": "Open your phone and CourierNow", "hint": "Press {phone} to take out your phone, then tap the orange CourierNow app."},
	{"id": "online", "title": "Start your shift", "hint": "In CourierNow, tap 'Start shift · go online'. A first request will come in."},
	{"id": "accept", "title": "Accept your first order", "hint": "Tap Accept on the request, then put the phone away ({phone})."},
	{"id": "ride", "title": "Walk to {restaurant}", "hint": "Follow the mint route on the minimap to the restaurant's pickup shelf."},
	{"id": "take", "title": "Find {customer}'s package", "hint": "The shelf holds other couriers' orders too. Read the name tags, look at {ticket} ({package}) and press {use}: it goes straight into your backpack."},
	{"id": "leave", "title": "Leave it at the door", "hint": "LEAVE AT DOOR: go to {address} and press {use} in the yellow marked area. You set it down and snap a proof photo."},
	{"id": "accept2", "title": "Accept the next order", "hint": "A new request is waiting, this one MEET AT DOOR. Open the phone ({phone}) and accept it."},
	{"id": "meet", "title": "Meet the customer", "hint": "Take {customer}'s package at {restaurant}. At {address}, knock ({use} on the door) and press {use} again to hand it over."},
]
const LOOK_GOAL := 2.4     ## radians of looking around
const WALK_GOAL := 12.0    ## metres on foot

var game          ## app_root (untyped: dynamic access to its HUD, player and session)
var card: MissionCard
var _check_delay := 0.0
var _last_yaw := 0.0
var _last_pitch := 0.0
var _last_pos := Vector3.INF

func setup(owner_game: Node) -> void:
	game = owner_game
	process_mode = Node.PROCESS_MODE_ALWAYS     # tasks done on the phone advance while it's open
	card = MissionCard.new()
	card.name = "MissionCard"
	# The HUD's left column stacks objective, order chip and this card (no overlaps).
	var stack: Control = game.get("hud_stack")
	if stack != null: stack.add_child(card)
	else:
		game.gameplay_ui.add_child(card)
		card.position = Vector2(16, 120)
	card.hide()

func session() -> DeliverySession:
	return game.session

func active() -> bool:
	return not bool(session().tutorial.get("done", true))

func step() -> int:
	return int(session().tutorial.get("step", 0))

func step_id() -> String:
	return str(STEPS[step()].id) if active() and step() < STEPS.size() else ""

static func index_of(id: String) -> int:
	for i in range(STEPS.size()):
		if STEPS[i].id == id: return i
	return -1

## New Game: training from the first task.
func start() -> void:
	session().tutorial = {"done": false, "step": 0, "v": 3}
	_last_pos = Vector3.INF
	enter("look")
	refresh()

## "" when `action` is allowed now, otherwise the reason to show the player.
func gate(action: String) -> String:
	if not active(): return ""
	match action:
		"dispatch":
			return "training"
		"reject", "offline":
			return "Training shift: accept this first order and learn the route."
		"deliver":
			if step() < index_of("leave"):
				return "Training: find your package on the shelf and pack it first (%s)." % game.use_hint()
	return ""

## Things the director can't see from state alone.
func event(name: String) -> void:
	if not active(): return
	var t: Dictionary = session().tutorial
	if name == step_id() or (name == "app_courier" and step_id() == "phone"):
		t[name] = true

func _process(delta: float) -> void:
	if game == null: return
	if get_tree().paused and game.mode != "phone": return
	if not active():
		bike_goal()
		return
	var t: Dictionary = session().tutorial
	var id := step_id()
	var player: CourierPlayer = game.player
	# Progress trackers.
	if id == "look":
		var turned := absf(angle_difference(_last_yaw, player.rotation.y)) + absf(player.camera.rotation.x - _last_pitch)
		if turned < 0.5: t["look"] = float(t.get("look", 0.0)) + turned
	elif id == "walk" and not player.mounted and _last_pos != Vector3.INF:
		var moved := Vector2(player.position.x - _last_pos.x, player.position.z - _last_pos.z).length()
		if moved < 2.0: t["walk"] = float(t.get("walk", 0.0)) + moved
	_last_yaw = player.rotation.y
	_last_pitch = player.camera.rotation.x
	_last_pos = player.position
	if _check_delay > 0.0:
		_check_delay -= delta
		if _check_delay <= 0.0: advance()
		return
	if done(id):
		_check_delay = 1.2
		card.complete()
		var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
		if audio: audio.play_ui("step_complete" if CityAudio.has_sound("step_complete") else "ui_accept", -6.0)
		return
	refresh()

func done(id: String) -> bool:
	var s := session()
	var t: Dictionary = s.tutorial
	var state: String = s.order.get("state", "")
	var closed: bool = game.mode == ""
	match id:
		"look": return float(t.get("look", 0.0)) >= LOOK_GOAL
		"walk": return float(t.get("walk", 0.0)) >= WALK_GOAL
		"store":
			var p: Vector3 = game.player.position
			var at: Vector3 = ShopCatalog.LOCATIONS["equipment"]
			return Vector2(p.x - at.x, p.z - at.z).length() < 8.0
		"order": return s.bought("budget_phone") and s.bought("delivery_bag") and closed
		"collect": return s.has_phone() and s.has_bag()
		"phone": return bool(t.get("app_courier", false))
		"online": return s.online
		"accept", "accept2": return state in DeliverySession.ACTIVE and closed
		"ride":
			var p: Vector3 = game.player.position
			var at := s.pickup_position()
			return state != "ACCEPTED" or Vector2(p.x - at.x, p.z - at.z).length() < 9.0
		# Taken off the shelf and packed (the pack sequence runs by itself after the pickup).
		"take": return state == "CARRYING" and closed and not game.sequence.running
		"leave", "meet": return state == "COMPLETED" and closed and not game.sequence.running
	return false

func advance() -> void:
	var t: Dictionary = session().tutorial
	for key in t.keys():
		if key != "done" and key != "step" and key != "v": t.erase(key)
	t["step"] = step() + 1
	if step() >= STEPS.size():
		finish()
		return
	enter(step_id())
	refresh()
	game.save_session()

## Side effects when a task begins: waypoints and the scripted first order.
func enter(id: String) -> void:
	var s := session()
	match id:
		"store":
			CityNavigation.target = {"name": "Trail & Tool", "kind": "store", "at": ShopCatalog.LOCATIONS["equipment"]}
		"accept", "accept2":
			CityNavigation.target = {}
			if s.order.is_empty() or s.order.get("state", "") in DeliverySession.TERMINAL:
				s.offer_position = game.player.position
				# Training orders from Kebab House: the first is left at the door, the second met in person.
				s.offer(10.0, 0, 0 if id == "accept" else 3, "door" if id == "accept" else "meet")
				s.order["expires"] = s.clock + 86400.0     # training orders never time out
			game.notify("CourierNow · New delivery request\nPress %s to review it" % game.binding("phone"))
		_:
			pass

func finish() -> void:
	var s := session()
	s.finish_tutorial()
	s.schedule_offer()
	CityNavigation.target = {}
	card.show_finished(DeliverySession.money(DeliverySession.TUTORIAL_BONUS))
	var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
	if audio and CityAudio.has_sound("mission_complete"): audio.play_ui("mission_complete", -4.0)
	game.notify("Training complete! %s bonus added.\nRequests now arrive automatically while you're online." % DeliverySession.money(DeliverySession.TUTORIAL_BONUS))
	game.save_session()

## After training (new careers): an optional goal card, saving up for the first bicycle.
func bike_goal() -> void:
	var s := session()
	if card.finished: return
	if s.economy != 2 or bool(s.tutorial.get("bike_goal", false)):
		if card.visible: card.hide()
		return
	var price := int(ShopCatalog.ITEMS["bicycle"].price)
	if s.owns("bicycle"):
		s.tutorial["bike_goal"] = true
		card.show_finished("", "GOAL REACHED", "Your first bicycle!", "Press %s next to it to ride. Deliveries are faster now: more orders, more tips." % game.binding("interact"))
		return
	card.set_goal("GOAL", "Save up for a bicycle", "Cedar Cycles sells a gray city bike for %s. Keep delivering on foot: %s to go." % [DeliverySession.money(price), DeliverySession.money(maxi(0, price - s.wallet))], float(s.wallet) / float(price))
	card.visible = game.mode == "" or game.mode == "bag"

## Current task text with keys and order details filled in.
func refresh() -> void:
	if not active():
		return
	var i := step()
	var s := session()
	var kind: String = s.order.get("kind", "bag")
	var info := {"sprint": game.binding("sprint"), "phone": game.binding("phone"), "map": game.binding("map"),
		"interact": game.binding("interact"), "bag": game.binding("bag"), "drop": game.binding("drop"), "use": game.use_hint(),
		"restaurant": s.restaurant_name() if not s.order.is_empty() else "the restaurant",
		"customer": str(s.order.get("customer", "your customer")), "ticket": str(s.order.get("ticket", "")),
		"address": DeliverySession.ADDRESSES[int(s.order.get("address", 0))],
		"package": OrderDetails.package_label(kind, s.order.get("items", [])).to_lower()}
	var t: Dictionary = s.tutorial
	var progress := 0.0
	match step_id():
		"order": progress = (0.5 if s.bought("budget_phone") else 0.0) + (0.5 if s.bought("delivery_bag") else 0.0)
		"collect": progress = (0.5 if s.has_phone() else 0.0) + (0.5 if s.has_bag() else 0.0)
		"look": progress = float(t.get("look", 0.0)) / LOOK_GOAL
		"walk": progress = float(t.get("walk", 0.0)) / WALK_GOAL
		"take": progress = 0.5 if s.order.get("state") == "IN_HAND" else 0.0
	var hint := str(STEPS[i].hint).format(info)
	if step_id() == "take" and s.order.get("state") == "IN_HAND" and not game.sequence.running:
		hint = "Press %s to pack it in your backpack." % game.use_hint()
	card.set_task(i, STEPS.size(), str(STEPS[i].title).format(info), hint, progress)
	# The name to look for, big on the card, while there is an order to collect or deliver.
	var state: String = s.order.get("state", "")
	if state in DeliverySession.ACTIVE: card.set_target(str(s.order.get("customer", "")), str(s.order.get("ticket", "")), OrderDetails.package_label(kind, s.order.get("items", [])))
	else: card.set_target("", "", "")
	card.visible = true
