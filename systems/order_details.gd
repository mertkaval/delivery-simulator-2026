class_name OrderDetails
extends RefCounted
## What is inside each order: the customer, the dishes (from the restaurant's menu), the
## package it travels in, and the printed receipt stuck on that package.
##
## Package kinds and where they ride in the insulated bag (real courier-bag logic):
##   "bag"    - kraft takeaway bag, upright         -> the big TOP compartment
##   "drinks" - drink/dessert carrier, must stay level -> one of the two MIDDLE halves
##   "pizza"  - flat pizza box                       -> the flat BOTTOM compartment

const FIRST := ["Ayşe", "Mehmet", "Elif", "Can", "Zeynep", "Emre", "Selin", "Burak", "Deniz", "Ece", "Kerem", "Defne",
	"Liam", "Olivia", "Noah", "Emma", "Mateo", "Sofia", "Arjun", "Priya", "Wei", "Mei", "Hiro", "Yuna", "Omar", "Leila",
	"Lucas", "Chloé", "Jonas", "Ingrid", "Diego", "Valentina"]
const LAST := ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Arslan", "Doğan", "Aydın", "Öztürk", "Koç", "Kurt", "Polat",
	"Chen", "Nguyen", "Patel", "Singh", "Martin", "Brown", "Wilson", "Tanaka", "Kim", "Haddad", "Rossi", "Novak"]
const SLOTS := ["top", "left", "right", "bottom"]
const SLOT_NAMES := {"top": "Top compartment", "left": "Middle left", "right": "Middle right", "bottom": "Pizza drawer"}
const KIND_NAMES := {"bag": "Food bag", "drinks": "Drinks & dessert carrier", "pizza": "Pizza box"}

## Which compartments a package fits.
static func fits(kind: String, slot: String) -> bool:
	match kind:
		"pizza": return slot == "bottom"
		"drinks": return slot in ["left", "right"]
		_: return slot == "top"

static func best_slot(kind: String) -> String:
	return "bottom" if kind == "pizza" else ("left" if kind == "drinks" else "top")

## Package kind by restaurant: pide/pizza places box, dessert/drinks places use the carrier.
static func package_kind(restaurant_id: String) -> String:
	var entry: Array = RestaurantCatalog.entry(restaurant_id)
	var text := (restaurant_id + " " + (str(entry[1]) if not entry.is_empty() else "")).to_lower()
	if text.contains("pizza") or text.contains("pide"): return "pizza"
	if text.contains("dessert") or text.contains("cafe") or text.contains("café") or text.contains("dairy") or text.contains("pastry") or text.contains("pancake"): return "drinks"
	return "bag"

## Menu as [[dish, cents], ...]; catalogue prices are lira, shown to players in dollars.
static func menu(restaurant_id: String) -> Array:
	var entry: Array = RestaurantCatalog.entry(restaurant_id)
	var out: Array = []
	if not entry.is_empty() and entry.size() > 10:
		for line in entry[10]:
			var text := str(line)
			var at := text.rfind("₺")
			if at < 0: continue
			var lira := int(text.substr(at + 1))
			out.append([text.substr(0, at).strip_edges(), int(round(lira * 4.0))])   # 25 lira ≈ $1
	if out.is_empty():
		# Downtown counters without a catalogue menu.
		var name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(restaurant_id))]
		out = [[name + " Special", 1450], ["House Salad", 890], ["Fresh Lemonade", 420], ["Soup of the Day", 650], ["Baklava", 520]]
	return out

static func random_customer(rng: RandomNumberGenerator) -> String:
	return "%s %s" % [FIRST[rng.randi() % FIRST.size()], LAST[rng.randi() % LAST.size()]]

## Customer, items and totals for an order, deterministic from its serial.
static func build(serial: int, restaurant_id: String, seed: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed * 7919 + serial * 104729
	var dishes := menu(restaurant_id)
	var items: Array = []
	var count := 1 + rng.randi() % 3
	for i in range(count):
		var d: Array = dishes[rng.randi() % dishes.size()]
		var qty := 1 + (1 if rng.randf() < 0.2 else 0)
		items.append([d[0], qty, int(d[1])])
	var subtotal := 0
	for it in items: subtotal += int(it[1]) * int(it[2])
	return {"customer": random_customer(rng), "items": items, "kind": package_kind(restaurant_id),
		"subtotal": subtotal, "ticket": "%s-%03d" % [restaurant_id.substr(0, 2).to_upper(), serial % 1000],
		"payment_method": ["Card · paid", "Apple Pay · paid", "Cash on delivery", "Card · paid"][rng.randi() % 4]}

## Printed receipt text (the paper tag on the package).
static func receipt_text(details: Dictionary, restaurant_name: String, address: String, minute: float) -> String:
	var lines := PackedStringArray()
	lines.append(restaurant_name.to_upper())
	lines.append("Order %s   %02d:%02d" % [details.ticket, int(minute / 60.0) % 24, int(minute) % 60])
	lines.append("CUSTOMER: " + str(details.customer))
	lines.append(address)
	lines.append("------------------------------")
	var subtotal := 0
	for it in details.items:
		lines.append("%dx %-18s %s" % [int(it[1]), str(it[0]).left(18), DeliverySession.money(int(it[1]) * int(it[2]))])
		subtotal += int(it[1]) * int(it[2])
	var tax := int(round(subtotal * 0.12))
	lines.append("------------------------------")
	lines.append("Subtotal %s   Tax %s" % [DeliverySession.money(subtotal), DeliverySession.money(tax)])
	lines.append("TOTAL %s   %s" % [DeliverySession.money(subtotal + tax), details.payment_method])
	lines.append("Package: " + str(KIND_NAMES.get(details.kind, details.kind)))
	return "\n".join(lines)
