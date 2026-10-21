class_name PickupShelves
extends Node3D
## Ready orders waiting at every restaurant's courier pickup point. Each package is a real
## model (food bag, pizza box or drink carrier: assets/delivery) with the restaurant's name on
## its logo panel and a printed receipt stuck on it showing the customer's name and order code.
## The courier must read the receipts and take the package for their own customer; the others
## belong to other couriers' orders (decoys) and are refused.
##
## Shelf frames: corridor restaurants use their three-tier courier rack, the avenue restaurants
## their pickup counter, downtown counters get a rack placed facing their approach.

const MODELS := {"bag": "res://assets/delivery/food_bag.glb", "pizza": "res://assets/delivery/pizza_box.glb", "drinks": "res://assets/delivery/drink_carrier.glb"}
const FALLBACK_SIZE := {"bag": Vector3(0.26, 0.32, 0.16), "pizza": Vector3(0.36, 0.045, 0.36), "drinks": Vector3(0.22, 0.2, 0.14)}
const RACK_SLOTS := [Vector3(-0.24, 0.47, 0.02), Vector3(0.23, 0.47, 0.02), Vector3(-0.24, 0.97, 0.02), Vector3(0.23, 0.97, 0.02), Vector3(0.0, 1.47, 0.02)]
const DECOYS := 3

var session: DeliverySession
var shelves: Dictionary = {}     ## restaurant id -> {"frame": Transform3D, "slots": Array[Vector3]}
var packages: Dictionary = {}    ## restaurant id -> Array[Node3D]
var _spawned_for := ""           ## order id whose package is currently on a shelf
var _rng := RandomNumberGenerator.new()
static var _scenes: Dictionary = {}

func setup(world: Node, s: DeliverySession) -> void:
	session = s
	_rng.seed = 90210
	# Avenue restaurants 0-2: the pickup counter (top at 1.1 m), customers on the +Z side.
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		shelves[CityCatalog.RESTAURANTS[i]] = {"frame": Transform3D(Basis.IDENTITY, p + Vector3(0, 0, 0.1)),
			"slots": [Vector3(-1.0, 1.1, 0), Vector3(-1.55, 1.1, 0), Vector3(-2.1, 1.1, 0), Vector3(-2.65, 1.1, 0), Vector3(-3.2, 1.1, 0)]}
	# Corridor restaurants: their courier rack.
	var interiors: Node = world.find_child("Restaurants", true, false)
	if interiors != null and interiors.get("restaurants") != null:
		for r in interiors.restaurants:
			var t: Transform3D = r.frame
			var rack: Vector3 = (t.affine_inverse() * (r.pickup as Vector3)) + Vector3(0, -1.0, -0.45)
			shelves[str(r.id)] = {"frame": Transform3D(t.basis, t * rack), "slots": RACK_SLOTS}
	# Downtown counters: a rack in front of the collection point, facing the approach.
	var rack_scene: PackedScene = load("res://world/citykit/restaurants/rs_pickup_shelf.glb") if ResourceLoader.exists("res://world/citykit/restaurants/rs_pickup_shelf.glb") else null
	for i in range(DowntownCatalog.PICKUPS.size()):
		var p: Vector3 = DowntownCatalog.PICKUPS[i]
		var approach: Array = DowntownCatalog.PICKUP_APPROACHES[i]
		var toward: Vector3 = (approach[approach.size() - 2] as Vector3) - p
		toward.y = 0
		toward = toward.normalized()
		var basis := Basis(Vector3.UP, atan2(toward.x, toward.z))
		var at := Vector3(p.x, 0.0, p.z) + toward * 0.75
		var frame := Transform3D(basis, at)
		if rack_scene:
			var rack: Node3D = rack_scene.instantiate()
			rack.transform = frame
			add_child(rack)
		shelves[CityCatalog.RESTAURANTS[i + 3]] = {"frame": frame, "slots": RACK_SLOTS}
		var board := MenuBoard.build(CityCatalog.RESTAURANTS[i + 3], Vector2(1.0, 1.3), Color("2f6f8a"))
		board.transform = frame * Transform3D(Basis.IDENTITY, Vector3(1.25, 1.5, -0.1))
		add_child(board)
	# Every shelf starts with a few other couriers' orders on it.
	for id in shelves: restock(id, "")

func scene_for(kind: String) -> PackedScene:
	if not _scenes.has(kind):
		var path: String = MODELS.get(kind, "")
		_scenes[kind] = load(path) if path != "" and ResourceLoader.exists(path) else null
	return _scenes[kind]

## Rebuild a shelf: decoys for other customers plus, if `mine` is an order, its package.
func restock(restaurant_id: String, mine: String) -> void:
	for n in packages.get(restaurant_id, []):
		if is_instance_valid(n): n.queue_free()
	packages[restaurant_id] = []
	var shelf: Dictionary = shelves[restaurant_id]
	var slots: Array = shelf.slots
	var order_slot := -1
	if mine != "": order_slot = _rng.randi() % slots.size()
	var used := 0
	for k in range(slots.size()):
		var details: Dictionary
		var is_mine := k == order_slot
		if is_mine:
			details = {"customer": session.order.customer, "ticket": session.order.ticket, "kind": session.order.kind,
				"items": session.order.items, "subtotal": session.order.subtotal, "payment_method": session.order.payment_method, "address": int(session.order.address)}
		else:
			if used >= DECOYS: continue
			used += 1
			details = OrderDetails.build(1000 + _rng.randi() % 90000, restaurant_id, _rng.randi())
			details["address"] = _rng.randi() % 36
		details["restaurant"] = restaurant_id
		var pkg := make_package(details)
		pkg.transform = (shelf.frame as Transform3D) * Transform3D(Basis.IDENTITY, slots[k])
		add_child(pkg)
		packages[restaurant_id].append(pkg)
	if mine != "": _spawned_for = mine

## A package with its logo and printed receipt, selectable with the interaction ray.
func make_package(details: Dictionary) -> StaticBody3D:
	var kind: String = details.kind
	var body := StaticBody3D.new()
	body.name = "Package_" + str(details.ticket)
	body.set_meta("interaction", "package")
	body.set_meta("package", details)
	var size: Vector3 = FALLBACK_SIZE[kind]
	var scene := scene_for(kind)
	var extras := {}
	if scene:
		var model: Node3D = scene.instantiate()
		body.add_child(model)
		for n in [model] + model.get_children():
			if n.has_meta("extras") and n.get_meta("extras") is Dictionary: extras = n.get_meta("extras")
	else:
		var mesh := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = size
		mesh.mesh = box
		mesh.position.y = size.y * 0.5
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color("b98a5c") if kind != "drinks" else Color("d9d2c3")
		mesh.material_override = mat
		body.add_child(mesh)
	var restaurant_name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(str(details.restaurant)))]
	# Logo: restaurant name printed on the logo panel.
	var logo_c: Vector3 = vec(extras.get("logo_center", null), Vector3(0, size.y * 0.6, size.z * 0.5 + 0.002))
	var logo_n: Vector3 = vec(extras.get("logo_normal", null), Vector3(0, 0, 1))
	body.add_child(print_label(restaurant_name.to_upper(), logo_c, logo_n, 22, Color("7a1f12"), 0.0011))
	# Receipt: customer name in large type plus the order code.
	var rc: Vector3 = vec(extras.get("receipt_center", null), Vector3(size.x * 0.32, size.y * 0.45, size.z * 0.5 + 0.003))
	var rn: Vector3 = vec(extras.get("receipt_normal", null), Vector3(0, 0, 1))
	var tag := print_label("%s\n%s\n%d item%s" % [str(details.customer).to_upper(), details.ticket, details.items.size(), "" if details.items.size() == 1 else "s"], rc, rn, 18, Color("111111"), 0.0009)
	tag.set_meta("receipt", true)
	body.add_child(tag)
	var shape := CollisionShape3D.new()
	var box_shape := BoxShape3D.new()
	box_shape.size = size + Vector3(0.04, 0.04, 0.04)
	shape.shape = box_shape
	shape.position.y = size.y * 0.5
	body.add_child(shape)
	return body

static func vec(v: Variant, fallback: Vector3) -> Vector3:
	if v is Array and (v as Array).size() == 3:
		# Package extras are already in Godot local axes (Y up, front +Z).
		return Vector3(float(v[0]), float(v[1]), float(v[2]))
	return fallback

static func print_label(text: String, at: Vector3, normal: Vector3, size: int, colour: Color, pixel: float) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font_size = size
	l.pixel_size = pixel
	l.modulate = colour
	l.outline_size = 0
	l.double_sided = false
	l.width = 400
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.visibility_range_end = 8.0
	l.position = at + normal * 0.002
	if normal.y > 0.7: l.rotation = Vector3(-PI / 2, 0, 0)
	else: l.rotation.y = atan2(normal.x, normal.z)
	return l

## Keep shelves in step with the order: the player's package appears when an order is
## accepted, and is removed when taken.
func _process(_delta: float) -> void:
	if session == null: return
	var state: String = session.order.get("state", "")
	var id: String = session.order.get("id", "")
	if state == "ACCEPTED" and _spawned_for != id:
		var rid := session.restaurant_id()
		if shelves.has(rid): restock(rid, id)

## Remove a package once it has been taken.
func take(pkg: Node) -> void:
	for rid in packages:
		var list: Array = packages[rid]
		if pkg in list:
			list.erase(pkg)
	pkg.queue_free()
