class_name TutorialDirector
extends Node
## First-shift training, started by New Game: twelve mandatory tasks done in order that teach
## the controls and the delivery loop (phone, map, gear, bike, offer, pickup shelf, holding and
## putting down a package, packing the backpack, handing over at the door).
## While training is running, normal dispatch is off (the director sends the first order
## itself), and rejecting, going offline, packing or delivering before their task are refused
## with a hint (gate()). Progress lives in DeliverySession.tutorial, so it saves and resumes.
## Finishing pays a one-time bonus (DeliverySession.finish_tutorial).

const STEPS := [
	{"id": "look", "title": "Look around", "hint": "Move the mouse to look around the street."},
	{"id": "walk", "title": "Take a walk", "hint": "Walk with W A S D. Hold {sprint} to jog."},
	{"id": "phone", "title": "Check your courier phone", "hint": "Press {phone} to open CourierNow: offers, orders and your wallet live here. Press {phone} again to put it away."},
	{"id": "map", "title": "Open the city map", "hint": "On foot, press {map}. Pick any place and the minimap guides you there. Press {map} to close it."},
	{"id": "bag", "title": "Buy an insulated delivery bag", "hint": "Food travels in a delivery backpack. Follow the minimap to Trail & Tool, press {interact} at the shop and buy the bag ($35)."},
	{"id": "bike", "title": "Get on your bicycle", "hint": "Follow the minimap back to your bike and press {interact} to ride. {interact} again gets you off."},
	{"id": "accept", "title": "Accept your first order", "hint": "A request just came in. Press {phone} and accept it."},
	{"id": "ride", "title": "Ride to {restaurant}", "hint": "Follow the mint route on the minimap. Park by the restaurant and get off ({interact})."},
	{"id": "take", "title": "Take the right package", "hint": "Look at the packages on the pickup shelf and read their receipts. Take the one for {customer} · {ticket} with {interact}."},
	{"id": "drop", "title": "Put it down, pick it up", "hint": "You're holding the order. Press {drop} to set it down, then look at it and press {interact} to pick it up again."},
	{"id": "pack", "title": "Pack it in your backpack", "hint": "Press {bag} to swing the backpack round. Move the package over the {slot} and click to drop it in (or press {interact}). Close with {bag}."},
	{"id": "deliver", "title": "Deliver to {customer}", "hint": "Ride to {address}, get off at the house and hand the order over at the door with {interact}."},
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
	process_mode = Node.PROCESS_MODE_PAUSABLE
	card = MissionCard.new()
	card.name = "MissionCard"
	game.gameplay_ui.add_child(card)
	card.position = Vector2(24, 156)
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
	session().tutorial = {"done": false, "step": 0}
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
		"stow":
			if step() < index_of("pack"):
				return "Training: first practise putting the package down (%s) and picking it up (%s)." % [game.binding("drop"), game.binding("interact")]
		"deliver":
			if step() < index_of("deliver"):
				return "Training: pack the order in your backpack first (%s)." % game.binding("bag")
	return ""

## Things the director can't see from state alone.
func event(name: String) -> void:
	if not active(): return
	var t: Dictionary = session().tutorial
	if name == step_id() or (name == "dropped" and step_id() == "drop"):
		t[name] = true

func _process(delta: float) -> void:
	if game == null: return
	if not active():
		if card.visible and not card.finished: card.hide()
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
	if id == "bike" and not player.mounted:
		CityNavigation.target = {"name": "Your bicycle", "kind": "home", "at": player.bicycle.position}
	if _check_delay > 0.0:
		_check_delay -= delta
		if _check_delay <= 0.0: advance()
		return
	if done(id):
		_check_delay = 1.2
		card.complete()
		var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
		if audio: audio.play_ui("ui_accept", -6.0)
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
		"phone": return bool(t.get("phone", false)) and closed
		"map": return bool(t.get("map", false)) and closed
		"bag": return s.bag_upgrade and closed
		"bike": return game.player.mounted
		"accept": return state in DeliverySession.ACTIVE and closed
		"ride":
			var p: Vector3 = game.player.position
			var at := s.pickup_position()
			return state != "ACCEPTED" or Vector2(p.x - at.x, p.z - at.z).length() < 9.0
		"take": return state in ["IN_HAND", "DROPPED", "CARRYING"]
		"drop": return bool(t.get("dropped", false)) and state == "IN_HAND"
		"pack": return state == "CARRYING" and closed
		"deliver": return state == "COMPLETED"
	return false

func advance() -> void:
	var t: Dictionary = session().tutorial
	for key in t.keys():
		if key != "done" and key != "step": t.erase(key)
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
		"bag":
			CityNavigation.target = {"name": "Trail & Tool", "kind": "store", "at": ShopCatalog.LOCATIONS["equipment"]}
		"bike":
			CityNavigation.target = {"name": "Your bicycle", "kind": "home", "at": game.player.bicycle.position}
		"accept":
			CityNavigation.target = {}
			if s.order.is_empty() or s.order.get("state", "") in DeliverySession.TERMINAL:
				s.online = true
				s.offer_position = game.player.position
				s.offer()
				s.order["expires"] = s.clock + 86400.0     # the training order never times out
			game.notify("CourierNow · New delivery request\nPress %s to review your offer" % game.binding("phone"))
		_:
			pass

func finish() -> void:
	var s := session()
	s.finish_tutorial()
	s.schedule_offer()
	CityNavigation.target = {}
	card.show_finished(DeliverySession.money(DeliverySession.TUTORIAL_BONUS))
	game.notify("Training complete! %s bonus added.\nRequests now arrive automatically while you're online." % DeliverySession.money(DeliverySession.TUTORIAL_BONUS))
	game.save_session()

## Current task text with keys and order details filled in.
func refresh() -> void:
	if not active():
		return
	var i := step()
	var s := session()
	var kind: String = s.order.get("kind", "bag")
	var info := {"sprint": game.binding("sprint"), "phone": game.binding("phone"), "map": game.binding("map"),
		"interact": game.binding("interact"), "bag": game.binding("bag"), "drop": game.binding("drop"),
		"restaurant": s.restaurant_name() if not s.order.is_empty() else "the restaurant",
		"customer": str(s.order.get("customer", "your customer")), "ticket": str(s.order.get("ticket", "")),
		"address": DeliverySession.ADDRESSES[int(s.order.get("address", 0))],
		"slot": str(OrderDetails.SLOT_NAMES.get(OrderDetails.best_slot(kind), "top compartment")).to_lower()}
	var t: Dictionary = s.tutorial
	var progress := 0.0
	match step_id():
		"look": progress = float(t.get("look", 0.0)) / LOOK_GOAL
		"walk": progress = float(t.get("walk", 0.0)) / WALK_GOAL
		"drop": progress = 0.5 if bool(t.get("dropped", false)) else 0.0
	var hint := str(STEPS[i].hint).format(info)
	if step_id() == "drop" and s.order.get("state") == "DROPPED":
		hint = "Now look at the package and press %s to pick it up." % game.binding("interact")
	card.set_task(i, STEPS.size(), str(STEPS[i].title).format(info), hint, progress)
	card.visible = true
