class_name PickupShelves
extends Node3D
## Ready orders waiting at every restaurant's courier pickup point. Each package is a real
## model (food bag, pizza box or drink carrier: assets/delivery) with the restaurant's name on
## its logo panel and big name tags (customer's first and last name, order code) on its faces
## and top, readable from a couple of metres.
##
## The package hunt: when you accept an order, its restaurant's shelf is restocked with your
## package and 4-7 other couriers' orders, laid out at random - random tier / spot along the
## counter, random turn, varied package kinds and sizes - and sometimes with names you could mix
## up (the same first name, the same last name). The layout is deterministic per order (seeded
## by the order id, ticket and customer), so a reloaded save shows the same shelf. You find yours
## by reading the tags; a wrong one is refused with who it is for (DeliverySession.take_package).
##
## Shelf frames: corridor restaurants use their three-tier courier rack, the avenue restaurants
## their pickup counter, downtown counters get a rack placed facing their approach.

## Kraft takeaway bags come in three sizes by order size (OrderDetails.bag_size).
const MODELS := {"bag_s": "res://assets/delivery/food_bag_s.glb", "bag_m": "res://assets/delivery/food_bag_m.glb", "bag_l": "res://assets/delivery/food_bag_l.glb",
	"pizza": "res://assets/delivery/pizza_box.glb", "drinks": "res://assets/delivery/drink_carrier.glb"}
const FALLBACK_SIZE := {"bag_s": Vector3(0.16, 0.27, 0.11), "bag_m": Vector3(0.19, 0.33, 0.13), "bag_l": Vector3(0.23, 0.39, 0.15),
	"pizza": Vector3(0.36, 0.045, 0.36), "drinks": Vector3(0.22, 0.2, 0.14)}
## Courier rack (rs_pickup_shelf: 0.96 m wide, posts at +-0.45, tiers at 0.45 / 0.95 / 1.45 m,
## header panel from 1.70 m): one lane per tier. x0..x1 along the tier, z = depth centre,
## depth = usable depth, max_h = clearance under the tier above.
const RACK_LANES := [{"y": 0.47, "x0": -0.41, "x1": 0.41, "z": 0.02, "depth": 0.4, "max_h": 0.45},
	{"y": 0.97, "x0": -0.41, "x1": 0.41, "z": 0.02, "depth": 0.4, "max_h": 0.45},
	{"y": 1.47, "x0": -0.41, "x1": 0.41, "z": 0.02, "depth": 0.4, "max_h": 0.21}]
## Avenue pickup counters: one long run of counter top (1.1 m) beside the register.
const COUNTER_LANES := [{"y": 1.1, "x0": -3.5, "x1": -0.7, "z": 0.17, "depth": 0.4, "max_h": 1.0}]
const DECOYS_MIN := 4
const DECOYS_MAX := 7
## Shelves without an order of yours show a few other couriers' orders.
const IDLE_DECOYS := 3
const GAP := 0.035

var session: DeliverySession
var shelves: Dictionary = {}     ## restaurant id -> {"frame": Transform3D, "lanes": Array, "kind": "rack"|"counter"}
var packages: Dictionary = {}    ## restaurant id -> Array[Node3D]
var _spawned_for := ""           ## order id whose package is currently on a shelf
static var _scenes: Dictionary = {}
static var _boxes: Dictionary = {}
static var _tag_font: FontVariation

func setup(world: Node, s: DeliverySession) -> void:
	session = s
	if world.has_meta("pickup_frames"):
		_setup_racks(world.get_meta("pickup_frames") as Array)
		return
	# Avenue restaurants 0-2: the pickup counter (top at 1.1 m), customers on the +Z side.
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		shelves[CityCatalog.RESTAURANTS[i]] = {"frame": Transform3D(Basis.IDENTITY, p + Vector3(0, 0, 0.1)), "lanes": COUNTER_LANES, "kind": "counter"}
	# Corridor restaurants: their courier rack.
	var interiors: Node = world.find_child("Restaurants", true, false)
	if interiors != null and interiors.get("restaurants") != null:
		for r in interiors.restaurants:
			var t: Transform3D = r.frame
			var rack: Vector3 = (t.affine_inverse() * (r.pickup as Vector3)) + Vector3(0, -1.0, -0.45)
			shelves[str(r.id)] = {"frame": Transform3D(t.basis, t * rack), "lanes": RACK_LANES, "kind": "rack"}
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
		shelves[CityCatalog.RESTAURANTS[i + 3]] = {"frame": frame, "lanes": RACK_LANES, "kind": "rack"}
		var board := MenuBoard.build(CityCatalog.RESTAURANTS[i + 3], Vector2(1.0, 1.3), Color("2f6f8a"))
		board.transform = frame * Transform3D(Basis.IDENTITY, Vector3(1.25, 1.5, -0.1))
		add_child(board)
	# Every shelf starts with a few other couriers' orders on it.
	for id in shelves: restock(id, "")

## Port Halden: every restaurant's courier rack stands on the sidewalk in front of its shop.
func _setup_racks(frames: Array) -> void:
	var rack_scene: PackedScene = load("res://world/citykit/restaurants/rs_pickup_shelf.glb") if ResourceLoader.exists("res://world/citykit/restaurants/rs_pickup_shelf.glb") else null
	for i in mini(frames.size(), CityCatalog.RESTAURANTS.size()):
		var frame: Transform3D = frames[i]
		if rack_scene:
			var rack: Node3D = rack_scene.instantiate()
			rack.transform = frame
			add_child(rack)
		shelves[CityCatalog.RESTAURANTS[i]] = {"frame": frame, "lanes": RACK_LANES, "kind": "rack"}
		var board := MenuBoard.build(CityCatalog.RESTAURANTS[i], Vector2(1.0, 1.3), Color("2f6f8a"))
		board.transform = frame * Transform3D(Basis.IDENTITY, Vector3(1.25, 1.5, -0.1))
		add_child(board)
	for id in shelves: restock(id, "")

func scene_for(kind: String) -> PackedScene:
	if not _scenes.has(kind):
		var path: String = MODELS.get(kind, "")
		_scenes[kind] = load(path) if path != "" and ResourceLoader.exists(path) else null
	return _scenes[kind]

static func model_key(kind: String, items: Array) -> String:
	return "bag_" + OrderDetails.bag_size(items) if kind == "bag" else kind

## Size of a package model (x wide, y tall, z deep), measured once from its meshes.
func model_size(key: String) -> Vector3:
	if _boxes.has(key): return _boxes[key]
	var size: Vector3 = FALLBACK_SIZE.get(key, Vector3(0.2, 0.3, 0.14))
	var scene := scene_for(key)
	if scene:
		var model: Node3D = scene.instantiate()
		var box := local_box(model)
		if box.size.length() > 0.05: size = box.size
		model.free()
	_boxes[key] = size
	return size

## Bounds of every mesh under `root`, in `root`'s space (works outside the tree).
static func local_box(root: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null: continue
		var b := PlayerAvatar.relative(root, mi) * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box

## Deterministic seed for an order's shelf layout.
static func layout_seed(restaurant_id: String, order: Dictionary) -> int:
	if order.is_empty(): return absi(hash("idle|" + restaurant_id))
	return absi(hash("%s|%s|%s|%s" % [restaurant_id, order.get("id", ""), order.get("ticket", ""), order.get("customer", "")]))

## Rebuild a shelf: other couriers' orders plus, if `mine` is an order id, your package.
func restock(restaurant_id: String, mine: String) -> void:
	for n in packages.get(restaurant_id, []):
		if is_instance_valid(n): n.queue_free()
	packages[restaurant_id] = []
	var shelf: Dictionary = shelves[restaurant_id]
	if mine != "" and not shelf.has("usable"): find_usable_lanes(restaurant_id)
	var order: Dictionary = session.order if mine != "" and session != null else {}
	var layout := plan(restaurant_id, order)
	for entry: Dictionary in layout:
		var pkg := make_package(entry.details)
		pkg.transform = (shelf.frame as Transform3D) * (entry.local as Transform3D)
		pkg.set_meta("shelf", restaurant_id)
		pkg.set_meta("local", entry.local)
		add_child(pkg)
		packages[restaurant_id].append(pkg)
	if mine != "": _spawned_for = mine

## The layout for a shelf: [{"details", "local": Transform3D in the shelf frame, "lane"}].
## Same restaurant + order -> same layout. Your package is always placed (first), decoys fill in
## where they fit.
func plan(restaurant_id: String, order: Dictionary) -> Array:
	var shelf: Dictionary = shelves[restaurant_id]
	var lanes: Array = shelf.get("usable", shelf.lanes)
	var rng := RandomNumberGenerator.new()
	rng.seed = layout_seed(restaurant_id, order)
	var items: Array = []
	var taken := {}
	var tickets := {}
	var home_kind := OrderDetails.package_kind(restaurant_id)
	if not order.is_empty():
		items.append({"customer": order.get("customer", ""), "ticket": order.get("ticket", ""), "kind": order.get("kind", home_kind),
			"items": order.get("items", []), "subtotal": order.get("subtotal", 0), "payment_method": order.get("payment_method", ""),
			"address": int(order.get("address", 0)), "restaurant": restaurant_id})
		taken[str(order.get("customer", ""))] = true
		tickets[str(order.get("ticket", ""))] = true
	var decoys := IDLE_DECOYS if order.is_empty() else DECOYS_MIN + rng.randi() % (DECOYS_MAX - DECOYS_MIN + 1)
	# How many decoys get a name you could mix up with yours: often one, sometimes two.
	var confusing := 0
	if not order.is_empty():
		var roll := rng.randf()
		confusing = 2 if roll < 0.3 else (1 if roll < 0.85 else 0)
	for k in range(decoys):
		var details := OrderDetails.build(1000 + rng.randi() % 90000, restaurant_id, rng.randi())
		details["address"] = rng.randi() % 36
		details["restaurant"] = restaurant_id
		# Varied packages: mostly the restaurant's own kind, some drink carriers and bags.
		var roll := rng.randf()
		details["kind"] = home_kind if roll < 0.62 else ("drinks" if roll < 0.84 else "bag")
		if details.kind == "pizza" and home_kind != "pizza": details["kind"] = "bag"
		if k < confusing:
			var similar := OrderDetails.confusable_name(rng, str(order.get("customer", "")), taken)
			if similar != "": details["customer"] = similar
		var guard := 0
		while taken.has(str(details.customer)) and guard < 400:
			details["customer"] = OrderDetails.random_customer(rng)
			guard += 1
		while tickets.has(str(details.ticket)):
			details["ticket"] = "%s-%03d" % [restaurant_id.substr(0, 2).to_upper(), rng.randi() % 1000]
		taken[str(details.customer)] = true
		tickets[str(details.ticket)] = true
		items.append(details)
	# Turn each package: mostly name-out, some back to front or sideways, all a little askew.
	var placed: Array = []
	var lane_items: Array = []
	for l in lanes: lane_items.append([])
	var used: Array[float] = []
	for l in lanes: used.append(0.0)
	for details: Dictionary in items:
		var size := model_size(model_key(str(details.kind), details.get("items", [])))
		var best := -1
		var yaw := 0.0
		var span := 0.0
		for attempt in range(6):
			var r := rng.randf()
			var base := 0.0 if r < 0.5 else (PI if r < 0.68 else (PI / 2 if r < 0.84 else -PI / 2))
			if attempt >= 3: base = 0.0
			var turn := base + rng.randf_range(-0.32, 0.32) * (1.0 if attempt < 4 else 0.0)
			var along := absf(cos(turn)) * size.x + absf(sin(turn)) * size.z
			var deep := absf(sin(turn)) * size.x + absf(cos(turn)) * size.z
			var fits: Array[int] = []
			for li in range(lanes.size()):
				var lane: Dictionary = lanes[li]
				var length: float = float(lane.x1) - float(lane.x0)
				if size.y <= float(lane.max_h) and deep <= float(lane.depth) and used[li] + along + GAP <= length: fits.append(li)
			if fits.is_empty(): continue
			best = fits[rng.randi() % fits.size()]
			yaw = turn
			span = along
			break
		if best < 0 and placed.is_empty() and (lane_items as Array).all(func(l: Array) -> bool: return l.is_empty()):
			# Yours (always first) goes on the lowest lane that takes its height, square on.
			for li in range(lanes.size()):
				if size.y <= float((lanes[li] as Dictionary).max_h) + 0.05:
					best = li
					break
			best = maxi(best, 0)
			yaw = 0.0
			span = size.x
		if best < 0: continue      # no room left for this decoy
		used[best] += span + GAP
		(lane_items[best] as Array).append({"details": details, "yaw": yaw, "span": span, "size": size})
	# Spread each lane's packages along it in a random order with random gaps.
	for li in range(lanes.size()):
		var lane: Dictionary = lanes[li]
		var list: Array = lane_items[li]
		if list.is_empty(): continue
		for i in range(list.size() - 1, 0, -1):
			var j := rng.randi() % (i + 1)
			var tmp: Variant = list[i]
			list[i] = list[j]
			list[j] = tmp
		var length: float = float(lane.x1) - float(lane.x0)
		var total := 0.0
		for e: Dictionary in list: total += float(e.span)
		var free := maxf(0.0, length - total - GAP * float(list.size() - 1))
		var weights: Array[float] = []
		var wsum := 0.0
		for i in range(list.size() + 1):
			var w := rng.randf_range(0.2, 1.0)
			weights.append(w)
			wsum += w
		var x := float(lane.x0)
		for i in range(list.size()):
			var e: Dictionary = list[i]
			x += free * weights[i] / wsum + (GAP if i > 0 else 0.0)
			var size: Vector3 = e.size
			var deep := absf(sin(float(e.yaw))) * size.x + absf(cos(float(e.yaw))) * size.z
			var slack := maxf(0.0, (float(lane.depth) - deep) * 0.5)
			var at := Vector3(x + float(e.span) * 0.5, float(lane.y), float(lane.z) + rng.randf_range(-slack, slack) * 0.8)
			x += float(e.span)
			placed.append({"details": e.details, "local": Transform3D(Basis(Vector3.UP, float(e.yaw)), at), "lane": li})
	return placed

## The lanes a courier standing in front of the shelf can see into (some racks stand behind a
## counter or a display, which hides the low tier from the customer side): rays from the eyes at
## the stand point to three spots on each lane, through the pickup volumes and the packages.
## Measured once per shelf when its first order is restocked (the physics world is up by then);
## the layout only uses these lanes, so yours is always in reach.
func find_usable_lanes(restaurant_id: String) -> void:
	var shelf: Dictionary = shelves[restaurant_id]
	var lanes: Array = shelf.lanes
	if not is_inside_tree():
		return
	var space := get_world_3d().direct_space_state
	var frame: Transform3D = shelf.frame
	var skip: Array[RID] = []
	for n in packages.get(restaurant_id, []):
		if is_instance_valid(n): skip.append((n as CollisionObject3D).get_rid())
	var usable: Array = []
	var front := float((lanes[0] as Dictionary).z) + float((lanes[0] as Dictionary).depth) * 0.5 + (0.62 if shelf.kind == "rack" else 0.75)
	for lane: Dictionary in lanes:
		var seen := 0
		for k in range(3):
			var x := lerpf(float(lane.x0) + 0.12, float(lane.x1) - 0.12, float(k) * 0.5)
			var eye := frame * Vector3(x, 1.65, front)
			var spot := frame * Vector3(x, float(lane.y) + 0.12, float(lane.z))
			var ex := skip.duplicate()
			var clear := true
			for attempt in range(5):
				var q := PhysicsRayQueryParameters3D.create(eye, spot, 1)
				q.exclude = ex
				var hit := space.intersect_ray(q)
				if hit.is_empty(): break
				var what := str((hit.collider as Node).get_meta("interaction", ""))
				if what.begins_with("pickup") or what == "package":
					ex.append(hit.rid)
					continue
				clear = false
				break
			if clear: seen += 1
		if seen >= 2: usable.append(lane)
	shelf["usable"] = usable if not usable.is_empty() else lanes

## Where to stand to take `pkg` off its shelf (world, on the floor in front of it) and the point
## on it to look at.
func stand_point(pkg: Node3D) -> Vector3:
	var shelf: Dictionary = shelves.get(str(pkg.get_meta("shelf", "")), {})
	if shelf.is_empty(): return pkg.global_position + Vector3(0, -1.0, 1.0)
	var local: Transform3D = pkg.get_meta("local")
	var frame: Transform3D = shelf.frame
	var out := 0.62 if shelf.kind == "rack" else 0.75
	return frame * Vector3(local.origin.x, 0.08, float((shelf.lanes as Array)[0].z) + float((shelf.lanes as Array)[0].depth) * 0.5 + out)

func look_point(pkg: Node3D) -> Vector3:
	var size := model_size(model_key(str((pkg.get_meta("package") as Dictionary).get("kind", "bag")), (pkg.get_meta("package") as Dictionary).get("items", [])))
	return pkg.global_position + Vector3(0, size.y * 0.5, 0)

## The package for the active order on its shelf (null when it is not there).
func mine() -> Node3D:
	if session == null: return null
	for pkg: Node3D in packages.get(session.restaurant_id(), []):
		if is_instance_valid(pkg) and session.is_mine(pkg.get_meta("package")): return pkg
	return null

## A package with its logo and name tags, selectable with the interaction ray.
func make_package(details: Dictionary) -> StaticBody3D:
	var kind: String = details.kind
	var key := model_key(kind, details.get("items", []))
	var body := StaticBody3D.new()
	body.name = "Package_" + str(details.ticket)
	body.set_meta("interaction", "package")
	body.set_meta("package", details)
	var size: Vector3 = FALLBACK_SIZE[key]
	var scene := scene_for(key)
	var extras := {}
	var box := AABB(Vector3(-size.x * 0.5, 0, -size.z * 0.5), size)
	if scene:
		var model: Node3D = scene.instantiate()
		body.add_child(model)
		for n in [model] + model.get_children():
			if n.has_meta("extras") and n.get_meta("extras") is Dictionary: extras = n.get_meta("extras")
		var measured := local_box(model)
		if measured.size.length() > 0.05:
			box = measured
			size = measured.size
	else:
		var mesh := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = size
		mesh.mesh = bm
		mesh.position.y = size.y * 0.5
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color("b98a5c") if kind != "drinks" else Color("d9d2c3")
		mesh.material_override = mat
		body.add_child(mesh)
	var restaurant_name: String = CityCatalog.NAMES[maxi(0, CityCatalog.restaurant_index(str(details.restaurant)))]
	# Logo: restaurant name printed on the logo panel.
	var logo_c: Vector3 = vec(extras.get("logo_center", null), Vector3(0, size.y * 0.6, size.z * 0.5 + 0.002))
	var logo_n: Vector3 = vec(extras.get("logo_normal", null), Vector3(0, 0, 1))
	var logo_w: float = float((extras.get("logo_size", [size.x * 0.8, 0.05]) as Array)[0])
	var pixel := minf(0.0011, logo_w * 0.92 / maxf(1.0, restaurant_name.length() * 0.6 * 22.0))
	if kind == "bag":
		body.add_child(print_label(restaurant_name.to_upper(), logo_c, logo_n, 22, Color("7a1f12"), pixel))
	# Name tags: front and back, the sides when they are wide enough, and the top of flat boxes.
	add_name_tags(body, details, box, kind, extras)
	var shape := CollisionShape3D.new()
	var box_shape := BoxShape3D.new()
	box_shape.size = size + Vector3(0.04, 0.04, 0.04)
	shape.shape = box_shape
	shape.position = box.get_center()
	body.add_child(shape)
	return body

## Big, high-contrast name stickers: white paper, the first name in heavy black capitals, the
## last name under it, the order code on a coloured strip. Front, back and wide-enough sides;
## pizza boxes get a big one on the lid and their edges.
func add_name_tags(body: Node3D, details: Dictionary, box: AABB, kind: String, extras: Dictionary) -> void:
	var c := box.get_center()
	var s := box.size
	var faces: Array = []
	if kind == "pizza":
		faces.append({"at": Vector3(c.x, box.end.y, c.z), "n": Vector3.UP, "w": s.x * 0.8, "h": s.z * 0.52})
		for n: Vector3 in [Vector3.BACK, Vector3.FORWARD, Vector3.RIGHT, Vector3.LEFT]:
			var half := absf(n.x) * s.x * 0.5 + absf(n.z) * s.z * 0.5
			faces.append({"at": Vector3(c.x, c.y, c.z) + n * half, "n": n, "w": s.x * 0.8, "h": s.y * 0.8, "strip": true})
	else:
		var bottom := box.position.y + 0.018
		var top := box.position.y + s.y * 0.55
		if kind == "bag":
			# Under the restaurant logo, on the flat front of the bag.
			var logo_c: Vector3 = vec(extras.get("logo_center", null), Vector3(0, box.position.y + s.y * 0.62, 0))
			var logo_h := float((extras.get("logo_size", [0.1, 0.05]) as Array)[1])
			top = logo_c.y - logo_h * 0.5 - 0.008
		else:
			# Drink carrier: on the tray's front panel, below the cups.
			var rc: Vector3 = vec(extras.get("receipt_center", null), Vector3(0, box.position.y + 0.07, 0))
			bottom = maxf(bottom, rc.y - 0.045)
			top = rc.y + 0.045
		var h := clampf(top - bottom, 0.05, 0.15)
		var mid := (top + bottom) * 0.5
		for n: Vector3 in [Vector3.BACK, Vector3.FORWARD]:
			faces.append({"at": Vector3(c.x, mid, c.z) + n * (s.z * 0.5), "n": n, "w": minf(s.x * 0.9, 0.21), "h": h})
		if s.z >= 0.095:
			for n: Vector3 in [Vector3.RIGHT, Vector3.LEFT]:
				faces.append({"at": Vector3(c.x, mid, c.z) + n * (s.x * 0.5), "n": n, "w": s.z * 0.84, "h": h * 0.9})
	var first := str(details.customer).get_slice(" ", 0).to_upper()
	var last := str(details.customer).substr(str(details.customer).find(" ") + 1).to_upper()
	for f: Dictionary in faces:
		var tag := name_tag(first, last, str(details.ticket), float(f.w), float(f.h), bool(f.get("strip", false)))
		var n: Vector3 = f.n
		tag.position = (f.at as Vector3) + n * 0.0025
		if n.y > 0.7: tag.rotation = Vector3(-PI / 2, 0, 0)
		else: tag.rotation.y = atan2(n.x, n.z)
		tag.set_meta("receipt", true)
		body.add_child(tag)

## One sticker (local +Z out of the face, centred). `strip`: a single line for thin edges.
func name_tag(first: String, last: String, ticket: String, w: float, h: float, strip: bool) -> Node3D:
	var root := Node3D.new()
	root.name = "NameTag"
	var paper := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(w, h)
	paper.mesh = quad
	paper.material_override = tag_material()
	paper.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	paper.visibility_range_end = 14.0
	root.add_child(paper)
	if strip:
		var one := tag_text("%s %s" % [first, last.left(1) + "."], w * 0.94, h * 0.78, Color("111111"))
		one.position.z = 0.0012
		root.add_child(one)
		one.set_meta("name_line", true)
		return root
	# Order code strip along the bottom (black on amber).
	var band_h := h * 0.22
	var band := MeshInstance3D.new()
	var bq := QuadMesh.new()
	bq.size = Vector2(w, band_h)
	band.mesh = bq
	band.material_override = band_material()
	band.position = Vector3(0, -h * 0.5 + band_h * 0.5, 0.0006)
	band.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	band.visibility_range_end = 14.0
	root.add_child(band)
	var first_l := tag_text(first, w * 0.92, h * 0.36, Color("0d0d0d"))
	first_l.position = Vector3(0, h * 0.5 - h * 0.05 - h * 0.18, 0.0012)
	first_l.set_meta("name_line", true)
	root.add_child(first_l)
	var last_l := tag_text(last, w * 0.92, h * 0.27, Color("1a1a1a"))
	last_l.position = Vector3(0, h * 0.5 - h * 0.43 - h * 0.12, 0.0012)
	last_l.set_meta("name_line", true)
	root.add_child(last_l)
	var code := tag_text(ticket, w * 0.6, band_h * 0.8, Color("111111"))
	code.position = Vector3(0, -h * 0.5 + band_h * 0.5, 0.0014)
	root.add_child(code)
	return root

## A line of heavy type fitted into w x h (metres).
static func tag_text(text: String, w: float, h: float, colour: Color) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font = tag_font()
	l.font_size = 64
	# Cap height ~0.72 em, average capital ~0.68 em wide in the heavy face.
	var by_h := h / (64.0 * 0.95)
	var by_w := w / maxf(1.0, text.length() * 0.66 * 64.0)
	l.pixel_size = minf(by_h, by_w)
	l.modulate = colour
	l.outline_size = 0
	l.double_sided = false
	l.shaded = false
	l.alpha_cut = Label3D.ALPHA_CUT_DISCARD
	l.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.visibility_range_end = 14.0
	return l

static func tag_font() -> FontVariation:
	if _tag_font == null:
		var sys := SystemFont.new()
		sys.font_names = PackedStringArray(["Arial Black", "Segoe UI Black", "Impact", "Arial", "sans-serif"])
		sys.font_weight = 900
		_tag_font = FontVariation.new()
		_tag_font.base_font = sys
		_tag_font.variation_embolden = 0.35
	return _tag_font

static var _paper: StandardMaterial3D
static var _band: StandardMaterial3D
static func tag_material() -> StandardMaterial3D:
	if _paper == null:
		_paper = StandardMaterial3D.new()
		_paper.albedo_color = Color("fbfaf6")
		_paper.roughness = 0.85
		# A little self-light so the white reads even on a dim shelf.
		_paper.emission_enabled = true
		_paper.emission = Color("fbfaf6")
		_paper.emission_energy_multiplier = 0.22
	return _paper

static func band_material() -> StandardMaterial3D:
	if _band == null:
		_band = StandardMaterial3D.new()
		_band.albedo_color = Color("ffc53d")
		_band.roughness = 0.8
		_band.emission_enabled = true
		_band.emission = Color("ffc53d")
		_band.emission_energy_multiplier = 0.15
	return _band

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

## Keep shelves in step with the order: the shelf is restocked (your package among the others)
## when an order is accepted; your package is removed when taken.
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
