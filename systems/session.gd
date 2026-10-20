class_name DeliverySession
extends RefCounted
## Single command boundary for the first delivery slice. All currency is cents.
signal changed
## Atatürk Avenue (formerly Cedar Lane): Vancouver block numbering, odd west / even east.
const ADDRESSES = ["105 Atatürk Avenue", "113 Atatürk Avenue", "121 Atatürk Avenue", "106 Atatürk Avenue", "114 Atatürk Avenue", "122 Atatürk Avenue", "137 Atatürk Avenue", "145 Atatürk Avenue", "161 Atatürk Avenue", "138 Atatürk Avenue", "146 Atatürk Avenue", "162 Atatürk Avenue", "305 Atatürk Avenue", "306 Atatürk Avenue", "313 Atatürk Avenue", "314 Atatürk Avenue", "321 Atatürk Avenue", "322 Atatürk Avenue", "329 Atatürk Avenue", "330 Atatürk Avenue", "505 Atatürk Avenue", "506 Atatürk Avenue", "513 Atatürk Avenue", "514 Atatürk Avenue", "521 Atatürk Avenue", "522 Atatürk Avenue", "529 Atatürk Avenue", "530 Atatürk Avenue", "705 Atatürk Avenue", "706 Atatürk Avenue", "713 Atatürk Avenue", "714 Atatürk Avenue", "721 Atatürk Avenue", "722 Atatürk Avenue", "729 Atatürk Avenue", "730 Atatürk Avenue"] + DowntownCatalog.DESTINATION_NAMES
const TERMINAL = ["COMPLETED", "REJECTED", "EXPIRED"]
var wallet: int = 0
var clock: float = 0.0
var online: bool = true
var next_offer: float = 8.0
var calendar_minutes: float = 690.0
var random_seed: int = 7321

func hour() -> float:
	return fmod(calendar_minutes, 1440.0) / 60.0

func demand() -> String:
	var h := hour()
	if h < 8 or h >= 22:
		return "Kitchen closed · opens 08:00"
	if (h >= 11 and h < 14) or (h >= 17 and h < 20):
		return "Busy · meal rush"
	return "Quiet · fewer requests"

func schedule_offer() -> void:
	random_seed = (random_seed * 48271) % 2147483647
	var busy := demand().begins_with("Busy")
	next_offer = clock + (15.0 if busy else 55.0) + float(random_seed % (31 if busy else 66))

func toggle_online() -> void:
	online = not online
	if not online and order.get("state") == "OFFERED":
		order.state = "REJECTED"
		schedule_offer()
	# Toggling availability never shortens an existing wait.
	next_offer = maxf(next_offer, clock + 8.0)
	changed.emit()

func dispatch(pickup_distance: float) -> bool:
	if not online or hour() < 8 or hour() >= 22 or clock < next_offer:
		return false
	if not order.is_empty() and order.state not in TERMINAL:
		return false
	offer(pickup_distance)
	return true
var serial: int = 0
var completed: int = 0
var energy: float = 100.0
var bag_upgrade: bool = false
var ledger: Dictionary = {}
var order: Dictionary = {}
var receipt: String = "Your first earnings start here."
var offer_position := Vector3(-8, 0, 23)
var inventory: Array[String] = []
var active_vehicle := "bicycle"
var hunger := 100.0
var hydration := 100.0
var bladder := 0.0
var purchase_serial := 0

func calendar() -> Dictionary:
	# Day one is 16 September 2026; the engine handles month/year rollover.
	return Time.get_datetime_dict_from_unix_time(1789516800 + int(calendar_minutes * 60))

func date_text() -> String:
	var date := calendar()
	var days := ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
	var months := ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	return "%s  %02d %s %d  |  %02d:%02d" % [days[date.weekday], date.day, months[date.month - 1], date.year, date.hour, date.minute]

func owns(id: String) -> bool:
	return id == "bicycle" or id in inventory or (id == "delivery_bag" and bag_upgrade)

func buy(id: String) -> String:
	if not ShopCatalog.ITEMS.has(id): return "This item is unavailable."
	if owns(id): return "You already own this item."
	if id == "delivery_bag": return purchase_bag()
	var item: Dictionary = ShopCatalog.ITEMS[id]
	if wallet < item.price: return "You need " + money(item.price - wallet) + " more."
	wallet -= int(item.price)
	inventory.append(id)
	ledger["purchase_" + id] = -int(item.price)
	changed.emit()
	return item.name + " purchased."

func consume(id: String) -> String:
	if not ShopCatalog.CONSUMABLES.has(id): return "Service unavailable."
	var item: Dictionary = ShopCatalog.CONSUMABLES[id]
	if wallet < item.price: return "You need " + money(item.price - wallet) + " more."
	if id == "wc":
		bladder = 0
		changed.emit()
		return "Refreshed. Washroom used."
	wallet -= int(item.price)
	purchase_serial += 1
	ledger["consumable_%s_%d" % [id, purchase_serial]] = -int(item.price)
	if id == "meal": hunger = minf(100, hunger + 55)
	if id == "water":
		hydration = minf(100, hydration + 65)
		bladder = minf(100, bladder + 12)
	changed.emit()
	return "Meal enjoyed." if id == "meal" else "Water replenished."

func restaurant_id() -> String:
	return str(order.get("restaurant", "cedar_kitchen"))

func restaurant_name() -> String:
	return CityCatalog.NAMES[CityCatalog.restaurant_index(restaurant_id())]

func pickup_position() -> Vector3:
	return CityCatalog.PICKUPS[CityCatalog.restaurant_index(restaurant_id())]

func offer(pickup_distance: float = 10.0) -> void:
	if not order.is_empty() and order.state not in TERMINAL:
		return
	serial += 1
	var address := (serial - 1) % 36
	var distance := 30.0 + float(address % 3) * 28.0 + (18.0 if address >= 3 else 0.0)
	var restaurant: int = CityCatalog.ROTATION[(serial - 1) % CityCatalog.ROTATION.size()]
	if offer_position.x>120:
		address=36+(serial-1)%DowntownCatalog.DESTINATIONS.size()
		restaurant=3+(serial-1)%DowntownCatalog.PICKUPS.size()
	var counter: Vector3 = CityCatalog.PICKUPS[restaurant]
	pickup_distance = CityCatalog.distance(CityCatalog.route(offer_position, counter, true))
	distance = CityCatalog.distance(CityCatalog.route(counter, CityCatalog.address_position(address), false))
	order = {"id": "job_%06d" % serial, "state": "OFFERED", "address": address,
		"restaurant": CityCatalog.RESTAURANTS[restaurant],
		"quote": 600 + int(round((pickup_distance + distance) * 0.2)), "tip_cap": 300,
		"pickup_distance": pickup_distance, "distance": distance, "expires": clock + 30.0,
		"deadline": 0.0, "bag": "", "payment": ""}
	changed.emit()

func tick(delta: float) -> void:
	if delta < 0 or not is_finite(delta):
		return
	clock += delta
	calendar_minutes += delta / 6.0
	hunger = maxf(0, hunger - delta / 90.0)
	hydration = maxf(0, hydration - delta / 65.0)
	bladder = minf(100, bladder + delta / 110.0)
	if hunger < 15 or hydration < 15 or bladder > 90:
		energy = maxf(0, energy - delta * 0.15)
	if order.get("state") == "OFFERED" and clock >= order.expires:
		order.state = "EXPIRED"
		schedule_offer()
		changed.emit()

func accept() -> bool:
	if order.get("state") != "OFFERED" or clock >= order.expires:
		return false
	order.state = "ACCEPTED"
	changed.emit()
	return true

func reject() -> bool:
	if order.get("state") != "OFFERED":
		return false
	order.state = "REJECTED"
	schedule_offer()
	changed.emit()
	return true

func pickup(restaurant_id: String, distance: float) -> String:
	if order.get("state") != "ACCEPTED":
		return "Accept an offer on your phone first." if order.get("state") != "CARRYING" else "Your delivery bag is already secured."
	if restaurant_id != self.restaurant_id() or not is_finite(distance) or distance < 0 or distance > 2.0:
		return "This is not your pickup counter."
	order.state = "CARRYING"
	order.bag = "bag_" + order.id
	order.deadline = clock + float(order.distance) / 3.5 * 1.35 + 60.0 + (30.0 if bag_upgrade else 0.0)
	changed.emit()
	return "Bag secured. Deliver to " + ADDRESSES[int(order.address)] + "."

func deliver(address: int, distance: float) -> String:
	if order.get("state") != "CARRYING":
		return "There is no delivery bag to hand over."
	if address != int(order.address):
		return "Wrong address. Your customer is at " + ADDRESSES[int(order.address)] + "."
	if not is_finite(distance) or distance < 0 or distance > 2.0 or order.bag != "bag_" + order.id:
		return "Move closer to the correct door with your bag."
	var transaction: String = "payment_" + order.id
	if ledger.has(transaction):
		return "This delivery has already been paid."
	var late := maxf(0.0, clock - float(order.deadline))
	var quality := clampf(1.0 - 0.005 * late, 0.0, 1.0)
	var tip := int(round(float(order.tip_cap) * quality))
	var total := int(order.quote) + tip
	ledger[transaction] = total
	wallet += total
	completed += 1
	order.payment = transaction
	order.bag = ""
	order.state = "COMPLETED"
	schedule_offer()
	receipt = "DELIVERY COMPLETE\nGuaranteed  %s\nTip  %s\nTotal earned  %s\n%s" % [money(order.quote), money(tip), money(total), "On time. Nicely done." if late == 0 else "Late by %ds; guaranteed pay preserved." % int(late)]
	changed.emit()
	return receipt

func purchase_bag() -> String:
	if bag_upgrade:
		return "You already own the insulated bag."
	if wallet < 3500:
		return "Insulated bag costs $35.00. You need " + money(3500 - wallet) + " more."
	wallet -= 3500
	bag_upgrade = true
	ledger["upgrade_insulated_bag"] = -3500
	changed.emit()
	return "Insulated bag purchased. Future pickups gain 30 seconds before tips decline."

func snapshot() -> Dictionary:
	return {"schema_version": 1, "content_version": 1, "wallet": wallet, "clock": clock,
		"serial": serial, "completed": completed, "energy": energy, "bag_upgrade": bag_upgrade,
		"ledger": ledger.duplicate(true), "order": order.duplicate(true), "receipt": receipt,
		"dispatch": {"online": online, "next_offer": next_offer, "calendar": calendar_minutes, "seed": random_seed},
		"lifestyle": {"inventory": inventory.duplicate(), "vehicle": active_vehicle, "hunger": hunger, "hydration": hydration, "bladder": bladder, "purchase_serial": purchase_serial}}

static func validate(data: Variant) -> bool:
	if not data is Dictionary:
		return false
	if not data.get("ledger") is Dictionary: return false
	if data.has("lifestyle"):
		var life: Variant = data.lifestyle
		if not life is Dictionary or not life.get("inventory") is Array: return false
		var seen := {}
		for id in life.inventory:
			if not id is String or not ShopCatalog.ITEMS.has(id) or seen.has(id): return false
			seen[id] = true
			if id == "delivery_bag" or not data.get("ledger", {}).has("purchase_" + id): return false
		if not life.get("vehicle") is String or not ShopCatalog.is_vehicle(life.vehicle): return false
		if life.vehicle != "bicycle" and not life.vehicle in life.inventory: return false
		for key in ["hunger", "hydration", "bladder", "purchase_serial"]:
			var number: Variant = life.get(key)
			if not (number is float or number is int) or not is_finite(float(number)) or number < 0: return false
			if key != "purchase_serial" and number > 100: return false
		if float(life.purchase_serial) != floor(float(life.purchase_serial)): return false
	if data.has("dispatch"):
		var dispatch_data: Variant = data.dispatch
		if not dispatch_data is Dictionary or not dispatch_data.get("online") is bool:
			return false
		for key in ["next_offer", "calendar", "seed"]:
			var value: Variant = dispatch_data.get(key)
			if not (value is int or value is float) or not is_finite(float(value)) or value < 0:
				return false
	for key in ["schema_version", "content_version", "wallet", "clock", "serial", "completed", "energy", "bag_upgrade", "ledger", "order", "receipt"]:
		if not data.has(key):
			return false
	if data.schema_version != 1 or data.content_version != 1 or not data.ledger is Dictionary or not data.order is Dictionary:
		return false
	for key in ["wallet", "clock", "serial", "completed", "energy"]:
		if not (data[key] is float or data[key] is int) or not is_finite(float(data[key])) or data[key] < 0:
			return false
	for key in ["wallet", "serial", "completed"]:
		if float(data[key]) != floor(float(data[key])):
			return false
	if data.energy > 100 or not data.bag_upgrade is bool or not data.receipt is String:
		return false
	var balance := 0
	var payment_count := 0
	for key in data.ledger:
		if not key is String:
			return false
		var value: Variant = data.ledger[key]
		if not (value is float or value is int) or not is_finite(float(value)) or float(value) != floor(float(value)):
			return false
		if key == "upgrade_insulated_bag":
			if value != -3500:
				return false
		elif key.begins_with("purchase_"):
			var id: String = key.trim_prefix("purchase_")
			if not ShopCatalog.ITEMS.has(id) or value != -ShopCatalog.ITEMS[id].price: return false
			if not data.has("lifestyle") or not id in data.lifestyle.inventory: return false
		elif key.begins_with("consumable_"):
			var parts: PackedStringArray = key.split("_")
			if parts.size() != 3 or not ShopCatalog.CONSUMABLES.has(parts[1]) or not parts[2].is_valid_int(): return false
			if not data.has("lifestyle") or int(parts[2]) < 1 or int(parts[2]) > data.lifestyle.purchase_serial: return false
			if value != -ShopCatalog.CONSUMABLES[parts[1]].price: return false
		elif key.begins_with("payment_job_"):
			if value < 0:
				return false
			payment_count += 1
		else:
			return false
		balance += int(value)
	if payment_count != int(data.completed) or data.bag_upgrade != data.ledger.has("upgrade_insulated_bag"):
		return false
	if balance != int(data.wallet):
		return false
	var job: Dictionary = data.order
	if job.has("restaurant") and (not job.restaurant is String or CityCatalog.restaurant_index(job.restaurant) < 0):
		return false
	if job.is_empty():
		return true
	for key in ["id", "state", "address", "quote", "tip_cap", "pickup_distance", "distance", "expires", "deadline", "bag", "payment"]:
		if not job.has(key):
			return false
	for key in ["id", "state", "bag", "payment"]:
		if not job[key] is String:
			return false
	for key in ["address", "quote", "tip_cap", "pickup_distance", "distance", "expires", "deadline"]:
		if not (job[key] is float or job[key] is int) or not is_finite(float(job[key])) or job[key] < 0:
			return false
	if job.address >= ADDRESSES.size() or float(job.address) != floor(float(job.address)) or job.state not in ["OFFERED", "ACCEPTED", "CARRYING", "COMPLETED", "REJECTED", "EXPIRED"]:
		return false
	if (job.state == "CARRYING") != (job.bag == "bag_" + job.id):
		return false
	if job.state != "CARRYING" and job.bag != "":
		return false
	var paid: bool = data.ledger.has("payment_" + job.id)
	for key in ["quote", "tip_cap"]:
		if float(job[key]) != floor(float(job[key])):
			return false
	if job.id != "job_%06d" % int(data.serial):
		return false
	return (job.state == "COMPLETED") == paid and (job.payment == "payment_" + job.id if paid else job.payment == "")

func restore(data: Dictionary) -> bool:
	if not validate(data):
		return false
	wallet = int(data.wallet)
	clock = float(data.clock)
	serial = int(data.serial)
	completed = int(data.completed)
	energy = float(data.energy)
	bag_upgrade = data.bag_upgrade
	ledger = data.ledger.duplicate(true)
	order = data.order.duplicate(true)
	receipt = data.receipt
	var dispatch_data: Dictionary = data.get("dispatch", {})
	online = dispatch_data.get("online", true)
	next_offer = float(dispatch_data.get("next_offer", clock + 8.0))
	calendar_minutes = float(dispatch_data.get("calendar", 690.0 + clock / 6.0))
	random_seed = int(dispatch_data.get("seed", 7321))
	var life: Dictionary = data.get("lifestyle", {})
	inventory.assign(life.get("inventory", []))
	active_vehicle = life.get("vehicle", "bicycle")
	hunger = float(life.get("hunger", 100))
	hydration = float(life.get("hydration", 100))
	bladder = float(life.get("bladder", 0))
	purchase_serial = int(life.get("purchase_serial", 0))
	changed.emit()
	return true

static func money(cents: int) -> String:
	return "$%.2f" % (float(cents) / 100.0)


