class_name StoreTerminals
extends Node3D
## In each of the four stores: a computer on the counter (E opens the online shop, StoreTerminal)
## and an ONLINE ORDER PICKUP shelf against the back wall where paid orders wait. Each waiting
## item is a real model with an order tag; E on it collects it (DeliverySession.collect).

const KIOSK := "res://assets/gadgets/store_kiosk.glb"
const LOCKER := "res://assets/gadgets/pickup_locker.glb"
const FALLBACK_SLOTS := [Vector3(-0.5, 0.42, 0.0), Vector3(0.0, 0.42, 0.0), Vector3(0.5, 0.42, 0.0),
	Vector3(-0.5, 1.02, 0.0), Vector3(0.0, 1.02, 0.0), Vector3(0.5, 1.02, 0.0)]

var session: DeliverySession
var shelves: Dictionary = {}       ## store -> {"frame": Transform3D, "slots": Array}
var items: Array[Node3D] = []
var _shown := ""
var solids: PropColliders

func setup(s: DeliverySession) -> void:
	session = s
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		place_kiosk(id, at + Vector3(4.0, 1.1, 1.0))
		place_shelf(id, Transform3D(Basis.IDENTITY, at + Vector3(4.9, 0.0, -4.5)))
	refresh()

func place_kiosk(store: String, at: Vector3) -> void:
	var kiosk: Node3D
	if ResourceLoader.exists(KIOSK):
		kiosk = (load(KIOSK) as PackedScene).instantiate()
	else:
		kiosk = Node3D.new()
		var mon := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = Vector3(0.56, 0.34, 0.04)
		mon.mesh = b
		mon.position = Vector3(0, 0.38, 0)
		kiosk.add_child(mon)
	kiosk.name = "Kiosk_" + store
	kiosk.position = at
	add_child(kiosk)
	# Attract screen: the store's name and "order here" over the monitor's display.
	var screen := kiosk.find_child("Screen", true, false) as MeshInstance3D
	var screen_at := Vector3(0, 0.38, 0.025)
	if screen:
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color("123a2d") if store == "equipment" else Color("1d2f45")
		screen.material_override = mat
		screen_at = kiosk.to_local(screen.global_transform * screen.get_aabb().get_center()) + Vector3(0, 0, 0.004)
	var title := Label3D.new()
	title.text = "%s\nONLINE STORE\n\nE · order here" % ShopCatalog.TITLES.get(store, store)
	title.font_size = 32
	title.pixel_size = 0.0016
	title.modulate = Color(1, 1, 1, 0.95)
	title.position = screen_at
	title.double_sided = false
	kiosk.add_child(title)
	var body := StaticBody3D.new()
	body.set_meta("interaction", "kiosk_" + store)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.7, 0.62, 0.45)
	shape.shape = box
	shape.position = Vector3(0, 0.31, 0)
	body.add_child(shape)
	kiosk.add_child(body)

func place_shelf(store: String, frame: Transform3D) -> void:
	var slots: Array = FALLBACK_SLOTS.duplicate()
	if ResourceLoader.exists(LOCKER):
		var locker: Node3D = (load(LOCKER) as PackedScene).instantiate()
		locker.transform = frame
		add_child(locker)
		# The shelving frame is solid on the prop layer: the E ray (mask 1) still reaches the items.
		if solids == null: solids = PropColliders.new(self, "LockerProps")
		solids.solid("pickup_locker", frame)
		for n: Node in [locker] + locker.get_children():
			var extras: Variant = n.get_meta("extras", {})
			if extras is Dictionary and (extras as Dictionary).has("slots"):
				slots.clear()
				for v: Variant in (extras as Dictionary).slots:
					var a: Array = v
					slots.append(Vector3(float(a[0]), float(a[1]), float(a[2])))
	else:
		for y: float in [0.4, 1.0, 1.6]:
			var plank := MeshInstance3D.new()
			var b := BoxMesh.new()
			b.size = Vector3(1.6, 0.03, 0.42)
			plank.mesh = b
			plank.transform = frame * Transform3D(Basis.IDENTITY, Vector3(0, y - 0.015, 0))
			add_child(plank)
	var sign := Label3D.new()
	sign.text = "ONLINE ORDER PICKUP"
	sign.font_size = 40
	sign.pixel_size = 0.004
	sign.outline_size = 8
	sign.modulate = Color("ffd166")
	sign.transform = frame * Transform3D(Basis.IDENTITY, Vector3(0, 2.05, 0.25))
	add_child(sign)
	shelves[store] = {"frame": frame, "slots": slots}

## Rebuild the waiting items from the session's pickups (call after purchases / collecting).
func refresh() -> void:
	var key := str(session.pickups)
	if key == _shown: return
	_shown = key
	for n in items: n.queue_free()
	items.clear()
	var used: Dictionary = {}
	for i in range(session.pickups.size()):
		var p: Dictionary = session.pickups[i]
		var shelf: Dictionary = shelves.get(str(p.store), {})
		if shelf.is_empty(): continue
		var k := int(used.get(p.store, 0))
		used[p.store] = k + 1
		var slots: Array = shelf.slots
		var spot: Vector3 = slots[k % slots.size()]
		var holder := StaticBody3D.new()
		holder.name = "Pickup_%d" % i
		holder.set_meta("interaction", "store_pickup")
		holder.set_meta("pickup_index", i)
		add_child(holder)
		var model := IconStudio.product_model(str(p.id))
		holder.add_child(model)
		fit(model, 0.42)
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(0.44, 0.4, 0.36)
		shape.shape = box
		shape.position.y = 0.2
		holder.add_child(shape)
		var tag := Label3D.new()
		tag.text = "%s%s\nYOUR ORDER · E" % [ShopCatalog.ITEMS[p.id].name, "  ×%d" % int(p.qty) if int(p.qty) > 1 else ""]
		tag.font_size = 22
		tag.pixel_size = 0.0022
		tag.outline_size = 6
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.position.y = 0.55
		holder.add_child(tag)
		holder.transform = (shelf.frame as Transform3D) * Transform3D(Basis.IDENTITY, spot)
		items.append(holder)

## Scale a model down so its largest side is at most `limit` metres; stand it on the shelf.
static func fit(model: Node3D, limit: float) -> void:
	var box := AABB()
	var first := true
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		var g := mi as MeshInstance3D
		var b := model.global_transform.affine_inverse() * g.global_transform * g.get_aabb() if model.is_inside_tree() else g.transform * g.get_aabb()
		box = b if first else box.merge(b)
		first = false
	if first: return
	var biggest := maxf(box.size.x, maxf(box.size.y, box.size.z))
	var s := minf(1.0, limit / maxf(biggest, 0.001))
	model.scale = Vector3.ONE * s
	model.position.y = -box.position.y * s
