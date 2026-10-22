extends SceneTree
## Courier flow: $100 start, insulated bag purchase, named orders with receipts on the pickup
## shelf, picking the right package among other couriers' orders, packing it into the bag
## compartment that fits (top / middle halves / pizza drawer), delivering, and save validity.
var checks := 0
var failed := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var s := DeliverySession.new()
	check(s.wallet == 10000, "New courier starts with $100 (%s)" % DeliverySession.money(s.wallet))
	check(DeliverySession.validate(s.snapshot()), "Fresh save validates with starting funds")
	# Bag pricing and ownership.
	check(s.buy("delivery_bag").begins_with("Insulated"), "Bag can be bought with the starting money")
	check(s.bag_upgrade and s.wallet == 6500, "Bag owned, $35 spent")
	check(DeliverySession.validate(s.snapshot()), "Save validates after the purchase")
	# An order with a customer, items, ticket and package kind.
	s.offer()
	var o := s.order
	check(o.has("customer") and str(o.customer).contains(" "), "Offer names the customer (%s)" % o.get("customer"))
	check(o.has("items") and o.items.size() >= 1, "Offer lists the ordered dishes")
	check(o.get("kind") in ["bag", "pizza", "drinks"], "Offer has a package kind (%s)" % o.get("kind"))
	check(s.accept(), "Offer accepted")
	# The pickup shelf in the real world.
	var world := CedarNeighborhood.new()
	root.add_child(world)
	await process_frame
	var shelves := PickupShelves.new()
	world.add_child(shelves)
	shelves.setup(world, s)
	check(shelves.shelves.size() == CityCatalog.RESTAURANTS.size(), "Every restaurant has a pickup shelf (%d)" % shelves.shelves.size())
	shelves._process(0.0)
	var rid := s.restaurant_id()
	var list: Array = shelves.packages.get(rid, [])
	var mine: Node = null
	var decoy: Node = null
	for p in list:
		var info: Dictionary = p.get_meta("package")
		if info.customer == o.customer and info.ticket == o.ticket: mine = p
		else: decoy = p
	check(mine != null, "Your customer's package is on the shelf")
	check(decoy != null, "Other customers' packages are on the shelf too")
	var tag_lines := PackedStringArray()
	for tag in mine.get_children().filter(func(n: Node) -> bool: return n.has_meta("receipt")):
		for l in tag.find_children("*", "Label3D", true, false):
			if l.has_meta("name_line"): tag_lines.append((l as Label3D).text)
	var first := str(o.customer).get_slice(" ", 0).to_upper()
	var last := str(o.customer).substr(str(o.customer).find(" ") + 1).to_upper()
	check(tag_lines.has(first) and tag_lines.has(last), "Name tags on the package show the customer's first and last name (%s)" % ", ".join(tag_lines))
	check(mine.get_children().filter(func(n: Node) -> bool: return n.has_meta("receipt")).size() >= 2, "Name tags on several faces of the package")
	var names := {}
	var same_as_mine := 0
	for p in list:
		var who := str((p.get_meta("package") as Dictionary).customer)
		names[who] = int(names.get(who, 0)) + 1
		if who == str(o.customer): same_as_mine += 1
	check(same_as_mine == 1 and names.size() == list.size(), "no decoy carries your customer's full name, no two tags alike (%s)" % ", ".join(names.keys()))
	check(list.size() >= 1 + PickupShelves.DECOYS_MIN and list.size() <= 1 + PickupShelves.DECOYS_MAX, "4-7 other couriers' orders around yours (%d packages)" % list.size())
	# Wrong package is refused with who it is for; the right one is taken.
	var refused := s.take_package(decoy.get_meta("package"), 1.0)
	check(refused.begins_with("This one is for %s — you're looking for %s" % [(decoy.get_meta("package") as Dictionary).customer, o.customer]) and s.order.state == "ACCEPTED", "Another customer's package is refused: " + refused)
	s.take_package(mine.get_meta("package"), 1.0)
	check(s.holding_package(), "Your package is now in your hands")
	check(DeliverySession.validate(s.snapshot()), "Save validates while holding a package")
	# Bag compartments: only the fitting compartment accepts it.
	var kind: String = s.order.kind
	for slot in OrderDetails.SLOTS:
		if not OrderDetails.fits(kind, slot):
			s.stow(slot)
			check(s.holding_package(), "%s refused in the %s" % [kind, slot])
	s.stow(OrderDetails.best_slot(kind))
	check(s.order.state == "CARRYING" and s.order.slot == OrderDetails.best_slot(kind), "%s packed in the %s" % [kind, OrderDetails.best_slot(kind)])
	check(DeliverySession.validate(s.snapshot()), "Save validates with a packed bag")
	s.unstow()
	check(s.holding_package(), "Package can be taken back out")
	s.stow(OrderDetails.best_slot(kind))
	# Fit rules.
	check(OrderDetails.fits("pizza", "bottom") and not OrderDetails.fits("pizza", "top"), "Pizza only in the bottom drawer")
	check(OrderDetails.fits("drinks", "left") and OrderDetails.fits("drinks", "right") and not OrderDetails.fits("drinks", "bottom"), "Drinks in the middle halves")
	check(OrderDetails.fits("bag", "top") and not OrderDetails.fits("bag", "left"), "Food bags in the top compartment")
	# Deliver.
	var before := s.wallet
	s.deliver(int(s.order.address), 1.0)
	check(s.order.state == "COMPLETED" and s.wallet > before, "Delivered and paid")
	check(DeliverySession.validate(s.snapshot()), "Save validates after delivery")
	# Without a bag you cannot pack (walking by hand only).
	var s2 := DeliverySession.new()
	s2.offer()
	s2.accept()
	s2.order.state = "IN_HAND"
	check(s2.stow("top").contains("need an insulated"), "No bag: packing refused with a hint")
	s2.deliver(int(s2.order.address), 1.0)
	check(s2.order.state == "COMPLETED", "No bag: a hand-carried order can still be delivered on foot")
	print("DELIVERY FLOW %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)
