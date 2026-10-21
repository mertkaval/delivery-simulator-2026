class_name HouseInstancer
extends Node3D
## Renders and wires the ResidentialLayout: houses, yards, rear lanes and edge forest.
## Every prop is a MultiMesh per (asset, material part, 128 m cell, LOD) with per-instance paint
## colours, so ~250 houses cost a few draw calls per visible cell. Collision is simple boxes plus
## walkable stair ramps; delivery houses get a door interaction, house number, mailbox and porch light.

const DIR := "res://world/citykit/houses/%s.glb"
const RESTAURANT_DIR := "res://world/citykit/restaurants/%s.glb"
const TRANSIT_DIR := "res://world/citykit/transit/%s.glb"
const NEAR_END := 110.0
const FAR_END := 700.0
const BODY_MATS := ["KitLapSiding", "KitShingleSiding", "KitBoardBatten", "KitHouseStucco"]

var groups := {}
var parts := {}
var body: StaticBody3D
var doors: Array[Vector3] = []
var paths: Array[MeshInstance3D] = []
var porch_lamps: Array[OmniLight3D] = []
var house_count := 0
var wire_key := "wire"

func _ready() -> void:
	body = StaticBody3D.new()
	body.name = "ResidentialCollision"
	add_child(body)
	for lot in ResidentialLayout.lots(): build_lot(lot)
	for lane in ResidentialLayout.lanes(): build_lane(lane)
	for t in ResidentialLayout.forest():
		var tall := int(t.origin.x * 3.0 + t.origin.z) % 3 == 0
		add("tree_cedar" if tall else "tree_fir", t, {}, 650.0)
		trunk(t.origin, t.basis.get_scale().x)
	flush()

func get_parts(asset: String, lod: String) -> Array:
	var key := asset + lod
	if not parts.has(key):
		var dir := RESTAURANT_DIR if asset.begins_with("rs_") else (TRANSIT_DIR if asset.begins_with("bus_") else DIR)
		for prefix in ["dog_", "cat_", "pigeon_", "crow_", "gull_", "bird_"]:
			if asset.begins_with(prefix): dir = "res://world/citykit/animals/%s.glb"
		var path := dir % (asset + ("_far" if lod == "far" else ""))
		var node: Node3D = load(path).instantiate()
		var list: Array = []
		UrbanKit.collect(node, Transform3D.IDENTITY, list)
		for p in list:
			var source: Material = p.mesh.surface_get_material(0)
			p["name"] = source.resource_name.get_slice(".", 0) if source != null else ""
		node.free()
		parts[key] = list
	return parts[key]

## Massing used for every house beyond NEAR_END: wall box + roof prism (eave height, roof rise, ridge axis).
const MASSING := {"house_craftsman": [3.85, 4.6, "x"], "house_special": [5.4, 2.2, "x"], "house_modern": [6.0, 1.0, "z"],
	"house_foursquare": [6.3, 4.05, "z"], "house_splitlevel": [5.2, 2.0, "x"], "house_laneway": [5.6, 3.2, "z"], "house_bungalow": [4.0, 2.8, "x"]}
static var far_wall_material: ShaderMaterial
static var far_roof_material: StandardMaterial3D

## Queue one instance of an asset with per-material tint colours.
## Houses: detailed near LOD in 48 m cells; massing beyond NEAR_END in 256 m cells.
## Props: near only, ending at `end` metres.
func add(asset: String, placement: Transform3D, colours: Dictionary, end: float = 0.0) -> void:
	var is_house := asset.begins_with("house_")
	var cell_size := 48.0 if (is_house or end == 0.0) else 128.0
	var cell := Vector2i(floori(placement.origin.x / cell_size), floori(placement.origin.z / cell_size))
	var range_end: float = NEAR_END if is_house else (end if end > 0.0 else 75.0)
	var list := get_parts(asset, "near")
	for i in range(list.size()):
		var key := "%s|%d|%d_%d" % [asset, i, cell.x, cell.y]
		if not groups.has(key):
			groups[key] = {"piece": list[i], "begin": 0.0, "end": range_end, "shadows": true, "items": []}
		groups[key].items.append([placement * list[i].transform, tint(list[i].name, colours)])
	if is_house: add_massing(asset, placement, colours)

func add_massing(asset: String, placement: Transform3D, colours: Dictionary) -> void:
	var spec: Dictionary = ResidentialLayout.TYPES[asset]
	var m: Array = MASSING[asset]
	var w: float = spec.w
	var d: float = spec.d
	var eave: float = m[0]
	var rise: float = m[1]
	# Same 48 m cells as the detailed house, so both LODs switch on the same distance and are never
	# shown together; the massing is also tucked 12 cm inside the walls and under the roof so that,
	# even during the switch, its faces can never sit on (and z-fight with) the real walls.
	var cell := Vector2i(floori(placement.origin.x / 48.0), floori(placement.origin.z / 48.0))
	var inset := 0.24
	var wall := Transform3D(Basis.from_scale(Vector3(w - inset, eave - 0.12, d - inset)), Vector3(0, (eave - 0.12) / 2, -d / 2))
	var roof_basis := Basis.from_scale(Vector3(w + 0.8 - inset, rise - 0.12, d + 0.8 - inset)) if m[2] == "z" else Basis(Vector3.UP, PI / 2) * Basis.from_scale(Vector3(d + 0.8 - inset, rise - 0.12, w + 0.8 - inset))
	var roof := Transform3D(roof_basis, Vector3(0, eave - 0.12 + (rise - 0.12) / 2, -d / 2))
	for part in [["wall", wall, colours.get("body", Color.WHITE)], ["roof", roof, colours.get("roof", Color.WHITE)]]:
		var key := "massing|%s|%d_%d" % [part[0], cell.x, cell.y]
		if not groups.has(key):
			groups[key] = {"piece": massing_piece(part[0]), "begin": NEAR_END, "end": FAR_END, "shadows": false, "items": []}
		groups[key].items.append([placement * part[1], part[2]])

static func massing_piece(kind: String) -> Dictionary:
	if far_wall_material == null:
		far_wall_material = ShaderMaterial.new()
		far_wall_material.shader = preload("res://world/citykit/far_house.gdshader")
		far_roof_material = StandardMaterial3D.new()
		far_roof_material.albedo_color = Color(0.85, 0.85, 0.85)
		far_roof_material.vertex_color_use_as_albedo = true
		far_roof_material.roughness = 0.85
	if kind == "wall":
		var box := BoxMesh.new()
		box.size = Vector3.ONE
		return {"mesh": box, "material": far_wall_material, "transform": Transform3D.IDENTITY}
	var prism := PrismMesh.new()
	prism.size = Vector3.ONE
	return {"mesh": prism, "material": far_roof_material, "transform": Transform3D.IDENTITY}

static func set_night(amount: float) -> void:
	if far_wall_material != null: far_wall_material.set_shader_parameter("night", amount)
static func tint(material_name: String, colours: Dictionary) -> Color:
	if material_name in BODY_MATS: return colours.get("body", Color.WHITE)
	match material_name:
		"KitTrimPaint": return colours.get("trim", Color.WHITE)
		"KitDoorPaint": return colours.get("door", Color.WHITE)
		"KitAsphaltShingles": return colours.get("roof", Color.WHITE)
		"KitGaragePaint": return colours.get("trim", Color.WHITE)
		"KitWallPaint": return colours.get("wall", Color.WHITE)
		"KitAccentPaint": return colours.get("accent", Color.WHITE)
		"KitUpholstery": return colours.get("seat", Color.WHITE)
	return Color.WHITE

func box_collider(center: Vector3, size: Vector3, basis: Basis) -> void:
	var shape := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = size
	shape.shape = b
	shape.transform = Transform3D(basis, center)
	body.add_child(shape)

## Walkable wedge over a flight of steps: top edge at height `top` (z_top), toe at the ground.
func ramp(t: Transform3D, x0: float, x1: float, top: float, z_top: float, z_bottom: float) -> void:
	var shape := CollisionShape3D.new()
	var wedge := ConvexPolygonShape3D.new()
	var pts := PackedVector3Array()
	for x in [x0, x1]:
		pts.append(t * Vector3(x, 0.0, z_top))
		pts.append(t * Vector3(x, top, z_top))
		pts.append(t * Vector3(x, 0.0, z_bottom))
	wedge.points = pts
	shape.shape = wedge
	body.add_child(shape)

func trunk(at: Vector3, scale_factor: float) -> void:
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.3 * scale_factor
	capsule.height = 4.0
	shape.shape = capsule
	shape.position = at + Vector3(0, 2.0, 0)
	body.add_child(shape)

func build_lot(lot: Dictionary) -> void:
	var spec: Dictionary = ResidentialLayout.TYPES[lot.type]
	var t := ResidentialLayout.transform(lot)
	var colours: Dictionary = lot.colours
	add(lot.type, t, colours)
	house_count += 1
	# Collision: body (split around a recessed entry), porch decks, stair ramps.
	var w: float = spec.w
	var d: float = spec.d
	var h: float = spec.h
	if spec.has("recess"):
		var rx0: float = spec.recess[0]
		var rx1: float = spec.recess[1]
		var rd: float = spec.recess[2]
		box_collider(t * Vector3(0, h / 2, -rd - (d - rd) / 2), Vector3(w, h, d - rd), t.basis)
		box_collider(t * Vector3((-w / 2 + rx0) / 2, h / 2, -rd / 2), Vector3(rx0 + w / 2, h, rd), t.basis)
		box_collider(t * Vector3((rx1 + w / 2) / 2, h / 2, -rd / 2), Vector3(w / 2 - rx1, h, rd), t.basis)
	else:
		box_collider(t * Vector3(0, h / 2, -d / 2), Vector3(w, h, d), t.basis)
	for b in spec.boxes: box_collider(t * b[0], b[1], t.basis)
	if not spec.ramp.is_empty():
		var r: Array = spec.ramp
		ramp(t, r[0], r[1], r[2], r[3], r[4])
	# Front walk from the sidewalk to the steps, with a garden bed beside it.
	var door: Vector3 = spec.door
	var walk_len := ResidentialLayout.SETBACK + 0.4
	# 3 cm tall and 4 cm narrower than the steps, so no face lines up with the house concrete.
	add_slab(t * Vector3(door.x, 0.0, ResidentialLayout.SETBACK + 0.2 - walk_len / 2 + 0.6), Vector3(1.26, 0.03, walk_len - 1.2), t.basis, "c1bbaa", lot.delivery >= 0)
	add("garden_bed", t * Transform3D(Basis.IDENTITY, Vector3(-w / 2 + 1.4, 0, 1.4)), colours)
	if lot.fence != "":
		# Front fence/hedge along the property line, open at the walk.
		var line := ResidentialLayout.SETBACK - 0.3
		var lot_w: float = lot.width
		var x := -lot_w / 2 + 1.2
		var panel := 0
		while x < lot_w / 2 - 0.6:
			if absf(x - door.x) > 1.6:
				# Alternate panels step 1.2 cm so the overlapping ends of neighbours never share a plane.
				add("hedge" if lot.fence == "hedge" else "fence_picket", t * Transform3D(Basis.IDENTITY, Vector3(x, 0, line + 0.012 * (panel % 2))), colours)
			x += 2.4
			panel += 1
	# Back yard: side fences to the lane, then a garage, shed or patio.
	var depth: float = lot.depth
	var back := -(depth - ResidentialLayout.SETBACK)
	for side in [-1.0, 1.0]:
		# Neighbouring lots share this boundary and both build a fence on it: keep each lot's fence
		# 8 cm inside its own line so the two never occupy the same plane (no z-fighting).
		var fence_x: float = side * (lot.width / 2 - 0.08)
		var z := -d - 1.2
		var panel := 0
		while z > back + 1.2:
			add("fence_privacy", t * Transform3D(Basis(Vector3.UP, PI / 2), Vector3(fence_x - side * 0.012 * (panel % 2), 0, z)), colours)
			z -= 2.4
			panel += 1
		box_collider(t * Vector3(fence_x, 0.9, (-d + back) / 2), Vector3(0.12, 1.8, absf(back + d)), t.basis)
	if lot.rear == "garage":
		add("garage_single", t * Transform3D(Basis(Vector3.UP, PI), Vector3(lot.width / 2 - 2.6, 0, back + 0.2)), colours)
		box_collider(t * Vector3(lot.width / 2 - 2.6, 1.6, back + 0.2 + 3.1), Vector3(3.8, 3.2, 6.2), t.basis)
	else:
		if lot.rear == "shed":
			add("shed", t * Transform3D(Basis(Vector3.UP, PI), Vector3(lot.width / 2 - 1.8, 0, back + 1.4)), colours)
		add("patio_set", t * Transform3D(Basis.IDENTITY, Vector3(-1.0, 0, -d - 2.4)), colours)
		if int(lot.front.z) % 2 == 0: add("raised_bed", t * Transform3D(Basis.IDENTITY, Vector3(-lot.width / 2 + 1.6, 0, back + 1.2)), colours)
		else: add("bbq", t * Transform3D(Basis.IDENTITY, Vector3(1.6, 0, -d - 1.2)), colours)
	add("bins_trio", t * Transform3D(Basis(Vector3.UP, PI), Vector3(-lot.width / 2 + 1.4, 0, back - 0.6)), colours)
	# Delivery houses: door interaction, number plate, mailbox, porch light.
	if lot.delivery >= 0:
		var index: int = lot.delivery
		var door_body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var b := BoxShape3D.new()
		b.size = Vector3(1.3, 2.2, 0.25)
		shape.shape = b
		door_body.add_child(shape)
		door_body.set_meta("interaction", "door_%d" % index)
		door_body.transform = Transform3D(t.basis, t * Vector3(door.x, door.y + 1.1, door.z - 0.0))
		add_child(door_body)
		doors.append(ResidentialLayout.door_point(lot))
		# Glowing 3D house numbers (Blender glyphs): a big one on an address post at the front walk
		# and a smaller one beside the door at eye level.
		var digits: String = DeliverySession.ADDRESSES[index].get_slice(" ", 0)
		# Address post at the front walk beside the mailbox, facing the street: big digits on
		# a navy plate, visible from the road while riding past.
		var post := MeshInstance3D.new()
		var post_mesh := BoxMesh.new()
		post_mesh.size = Vector3(0.09, 1.25, 0.09)
		post.mesh = post_mesh
		post.material_override = CityMaterials.get_surface("344448")
		post.transform = Transform3D(t.basis, t * Vector3(door.x - 1.25, 0.62, ResidentialLayout.SETBACK - 0.65))
		post.visibility_range_end = 90.0
		add_child(post)
		var above := GlyphText.build(digits, 0.26)
		above.transform = Transform3D(t.basis, t * Vector3(door.x - 1.25, 1.12, ResidentialLayout.SETBACK - 0.6))
		add_child(above)
		var beside := GlyphText.build(digits, 0.14)
		beside.transform = Transform3D(t.basis, t * Vector3(door.x + 0.85, door.y + 1.6, door.z + 0.04))
		add_child(beside)
		var mailbox := CityAssets.create("mailbox", 85)
		mailbox.transform = Transform3D(t.basis, t * Vector3(door.x + 1.2, 0, ResidentialLayout.SETBACK - 0.6))
		add_child(mailbox)
		var lamp := OmniLight3D.new()
		lamp.position = t * Vector3(door.x, door.y + 2.4, door.z + 0.6)
		lamp.light_color = Color("ffd9a0")
		lamp.omni_range = 5.0
		lamp.shadow_enabled = false
		lamp.distance_fade_enabled = true
		lamp.distance_fade_begin = 50.0
		lamp.distance_fade_length = 15.0
		add_child(lamp)
		porch_lamps.append(lamp)

func add_slab(center: Vector3, size: Vector3, basis: Basis, colour: String, record: bool) -> void:
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = size
	mesh.mesh = cube
	mesh.material_override = CityMaterials.get_surface(colour)
	mesh.transform = Transform3D(basis, center + Vector3(0, size.y / 2, 0))
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mesh)
	if record: paths.append(mesh)

func build_lane(lane: Dictionary) -> void:
	var length: float = lane.z1 - lane.z0
	var surface := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = Vector3(lane.width, 0.04, length)
	surface.mesh = cube
	surface.material_override = CityAssets.pbr("asphalt_03", 0.45)
	# Top at 3.2 cm, under the 4 cm yard pads (patios, aprons) that reach the lane edge.
	surface.position = Vector3(lane.x, 0.012, (lane.z0 + lane.z1) / 2)
	surface.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(surface)
	# Power poles every 30 m on the lane edge, with sagging conductors between them.
	var side := 1.0 if lane.x > 0 else -1.0
	var px: float = lane.x + side * (lane.width / 2 + 0.3)
	var poles: Array[Vector3] = []
	var z: float = lane.z0 + 6.0
	var i := 0
	while z < lane.z1 - 3.0:
		var pole := Vector3(px, 0, z)
		add("utility_pole_transformer" if i % 4 == 2 else "utility_pole", Transform3D(Basis(Vector3.UP, PI / 2), pole), {})
		box_collider(pole + Vector3(0, 2.0, 0), Vector3(0.3, 4.0, 0.3), Basis.IDENTITY)
		poles.append(pole)
		z += 30.0
		i += 1
	wire_key = "wire_%d" % roundi(lane.x * 10 + lane.z0)
	for k in range(1, poles.size()):
		for offset in [-1.05, -0.35, 0.35, 1.05]:
			wire(poles[k - 1] + Vector3(0, 9.5, offset), poles[k] + Vector3(0, 9.5, offset), 0.55)
		wire(poles[k - 1] + Vector3(0, 7.4, 0.4), poles[k] + Vector3(0, 7.4, 0.4), 0.7)

## Catenary approximated by 6 straight spans of a thin dark beam (instanced).
func wire(a: Vector3, b: Vector3, sag: float) -> void:
	var prev := a
	for s in range(1, 7):
		var u := float(s) / 6.0
		var p := a.lerp(b, u) - Vector3(0, sag * 4.0 * u * (1.0 - u), 0)
		var mid := (prev + p) * 0.5
		var dir := (p - prev)
		var basis := Basis.looking_at(dir.normalized(), Vector3.UP).scaled(Vector3(0.025, 0.025, dir.length()))
		var key := wire_key
		if not groups.has(key):
			groups[key] = {"piece": {"mesh": unit_box(), "material": wire_material(), "transform": Transform3D.IDENTITY}, "begin": 0.0, "end": 260.0, "shadows": false, "items": []}
		groups[key].items.append([Transform3D(basis, mid), Color.WHITE])
		prev = p

static func unit_box() -> BoxMesh:
	var m := BoxMesh.new()
	m.size = Vector3.ONE
	return m

static func wire_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("16191b")
	m.roughness = 0.6
	return m

func flush() -> void:
	for data: Dictionary in groups.values():
		var items: Array = data.items
		var multi := MultiMesh.new()
		multi.transform_format = MultiMesh.TRANSFORM_3D
		multi.use_colors = true
		multi.mesh = data.piece.mesh
		multi.instance_count = items.size()
		var origin: Vector3 = items[0][0].origin
		for i in range(items.size()):
			var tr: Transform3D = items[i][0]
			tr.origin -= origin
			multi.set_instance_transform(i, tr)
			multi.set_instance_color(i, items[i][1])
		var node := MultiMeshInstance3D.new()
		node.multimesh = multi
		node.material_override = data.piece.material
		node.position = origin
		node.visibility_range_begin = data.begin
		node.visibility_range_end = data.end
		node.visibility_range_begin_margin = 8.0 if data.begin > 0.0 else 0.0
		node.visibility_range_end_margin = 8.0
		if not data.shadows: node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
	groups.clear()