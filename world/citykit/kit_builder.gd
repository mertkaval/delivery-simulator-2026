class_name KitBuilder
extends Node3D
## Assembles CityLayout specs from Blender city-kit modules. Each building's modules are
## merged into one mesh per LOD range with one surface per material (a handful of draw
## calls per building, culled per building); each building gets one box collider and an
## occluder. Upper floors are not enterable: entrances are closed doors.

const FLOOR := 3.2
const GROUND := 4.2
const NEAR_END := 140.0
const FAR_END := 650.0
const TH_FLOOR := 3.0
const TH_PLINTH := 0.45
const TH_RISE := 3.906 ## tan(38 deg) * 5 m: ridge height above the eaves
## Balcony slabs sit this far above their floor line, clear of the ground floor's cornice band
## and with their top 1 cm over the apartment bays' concrete floor band (top 0.2) rather than in
## its plane (the band's top lay in the slab top: coplanar, if the same concrete).
const BALCONY_LIFT := 0.10

var batches := {}
## Test hook: when true, every placed near-LOD piece is also recorded as [building, asset, mesh, transform].
static var record_parts := false
var recorded: Array = []
var body: StaticBody3D
var built := 0
var building := 0 ## index of the building currently being assembled
## Profiling switch: captures can compare frame cost with and without the kit buildings.
static var enabled := true
## World-space tops of terrace chimney stacks (for CityVFX smoke), rebuilt on every load.
static var chimney_tops: Array[Vector3] = []
## Welding the ~16k kit pieces with SurfaceTool took ~13 s of every launch, so the merged
## geometry is cached in user://. A batch's file name hashes everything that shapes it (pieces,
## transforms, glass swap, LOD range) plus the kit GLBs' modification times; bump CACHE_VERSION
## when flush() changes how it builds meshes.
const CACHE_VERSION := 1
const CACHE_DIR := "user://cache/kit_buildings"
static var use_cache := true
var assets_used := {}

func _ready() -> void:
	if not enabled: return
	chimney_tops.clear()
	body = StaticBody3D.new()
	body.name = "KitBuildingCollision"
	add_child(body)
	for b in CityLayout.buildings():
		building = built
		match b.type:
			"terrace": terrace(b)
			"walkup": walkup(b)
			"midrise": midrise(b)
		built += 1
	flush()

static func pose(at: Vector3, yaw: float = 0.0, scale_factor: Vector3 = Vector3.ONE) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, yaw).scaled_local(scale_factor) if scale_factor != Vector3.ONE else Basis(Vector3.UP, yaw), at)

func place(asset: String, placement: Transform3D, end: float, start: float = 0.0, shadows: bool = true) -> void:
	var key := "%d_%d_%d_%d" % [building, int(start), int(end), int(shadows)]
	if not batches.has(key):
		batches[key] = {"start": start, "end": end, "shadows": shadows, "origin": placement.origin, "surfaces": {}, "sig": 0}
	var group: Dictionary = batches[key]
	var swap := clear_glass and (asset.begins_with("storefront_") or (asset.begins_with("entrance_") and not asset.begins_with("entrance_residential")))
	group.sig = hash([group.sig, asset, swap, placement])
	assets_used[asset] = true
	for piece in UrbanKit.get_parts(asset):
		var material: Material = piece.material
		if swap and material == UrbanKit.material("UrbanWindow"): material = CityKit.material("KitClearGlass")
		var id := material.get_instance_id() if material != null else 0
		if not group.surfaces.has(id): group.surfaces[id] = {"material": material, "parts": []}
		group.surfaces[id].parts.append([piece.mesh, placement * piece.transform])
		if record_parts and start == 0.0: recorded.append([building, asset, piece.mesh, placement * piece.transform])

## Near module with its hand-built far LOD beyond NEAR_END.
func module(asset: String, placement: Transform3D) -> void:
	# Corner modules of perpendicular facades share planes (a storefront's end face lies in the
	# side street facade plane). Step every module out along its own facing - 12 mm for modules
	# facing the street (+-Z), 10 mm for side facades (+-X) - so those planes never coincide.
	var out := placement.basis.z.normalized()
	placement.origin += out * (0.012 if absf(out.z) > 0.7 else 0.01)
	place(asset, placement, NEAR_END)
	place(asset + "_far", placement, FAR_END, NEAR_END, false)

func collider(center: Vector3, size: Vector3, yaw: float) -> void:
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.transform = Transform3D(Basis(Vector3.UP, yaw), center)
	body.add_child(shape)

func occluder(center: Vector3, size: Vector3, yaw: float) -> void:
	var node := OccluderInstance3D.new()
	var box := BoxOccluder3D.new()
	box.size = size
	node.occluder = box
	node.transform = Transform3D(Basis(Vector3.UP, yaw), center)
	add_child(node)

func sign_label(text: String, at: Vector3, yaw: float, size: int = 34) -> void:
	var label := Label3D.new()
	label.text = text
	label.position = at
	label.rotation.y = yaw
	label.font_size = size
	label.pixel_size = 0.006
	label.outline_size = 2
	label.modulate = Color("f1ead7")
	label.visibility_range_end = 70
	add_child(label)

## Four facades of a 4 m-bay block. `ground(bay, face)` and `upper(bay, face, floor)` pick modules;
## face 0 = street, 1 = left, 2 = back, 3 = right. Returns the roof height.
func block_facades(base: Transform3D, bays: int, depth: float, floors: int, ground: Callable, upper: Callable, style: int = -1) -> float:
	var width := bays * 4.0
	var depth_bays := int(depth / 4.0)
	var faces := [
		[pose(Vector3(0, 0, 0)), bays],
		[pose(Vector3(-width * 0.5, 0, -depth * 0.5), -PI / 2), depth_bays],
		[pose(Vector3(0, 0, -depth), PI), bays],
		[pose(Vector3(width * 0.5, 0, -depth * 0.5), PI / 2), depth_bays],
	]
	for f in range(4):
		var face: Transform3D = base * faces[f][0]
		var count: int = faces[f][1]
		for i in range(count):
			var x := -count * 2.0 + 2.0 + i * 4.0
			module(ground.call(i, f, count), face * pose(Vector3(x, 0, 0)))
			for fl in range(1, floors):
				module(upper.call(i, f, fl), face * pose(Vector3(x, GROUND + (fl - 1) * FLOOR, 0)))
	var top := GROUND + (floors - 1) * FLOOR
	if style >= 0: corner_posts(base, width, depth, top, style)
	return top

## Corner quoins: a 7 cm post up each building corner, 2 cm proud of both facades. The street
## modules' end faces (piers, fascia, trims) end in the side facade's plane and the side wall
## steps only 1 cm out past them - coplanar slivers that shimmered at a distance, and a 1 cm slot
## open down the corner. The post covers both and closes the corner.
const POST_IN := 0.04 ## post reaches this far inside the street facade's end
const POST_OUT := 0.025 ## and stands this far proud of both facades (at 2 cm its face lay in the far LOD's fascia / window quads)
const POST_DEPTH := 0.34 ## back from the street facade's front plane (module depth 0.3)
func corner_posts(base: Transform3D, width: float, depth: float, top: float, style: int) -> void:
	var street_out := 0.012 ## module() steps for facades facing +-Z / +-X (local frame of the block)
	var side_out := 0.01
	var w := POST_IN + side_out + POST_OUT
	var d := POST_DEPTH + street_out + POST_OUT
	for back in [false, true]:
		for sx in [-1.0, 1.0]:
			# Post frame: front (local +z of the module) on the street / back facade, x out to the side.
			var face := base * pose(Vector3(0, 0, -depth if back else 0.0), PI if back else 0.0)
			var cx: float = sx * (width * 0.5 - POST_IN + w * 0.5)
			var placement := face * pose(Vector3(cx, 0, street_out + POST_OUT), 0.0, Vector3(w / 4.0, top / FLOOR, d / 0.3))
			place("plain_wall_%d" % style, placement, NEAR_END)
			place("plain_wall_%d_far" % style, placement, FAR_END, NEAR_END, false)

func roof(base: Transform3D, bays: int, depth: float, top: float, style: int, variant: int) -> void:
	var width := bays * 4.0
	var depth_bays := int(depth / 4.0)
	# Cornice on all four faces, gravel roof deck inside it.
	var faces := [[pose(Vector3(0, top, 0)), bays], [pose(Vector3(-width * 0.5, top, -depth * 0.5), -PI / 2), depth_bays],
		[pose(Vector3(0, top, -depth), PI), bays], [pose(Vector3(width * 0.5, top, -depth * 0.5), PI / 2), depth_bays]]
	for f in faces:
		for i in range(f[1]):
			module("cornice_%d" % style, base * f[0] * pose(Vector3(-f[1] * 2.0 + 2.0 + i * 4.0, 0, 0)))
	place("roof_slab", base * pose(Vector3(0, top + 0.1, -0.25), 0, Vector3((width - 0.5) / 4.0, 1, (depth - 0.5) / 4.0)), FAR_END)
	# Rooftop services: plant, stair bulkhead, aerial.
	place("hvac", base * pose(Vector3(-width * 0.2, top + 0.2, -depth * 0.55)), 260)
	if variant % 2 == 0: place("hvac", base * pose(Vector3(width * 0.22, top + 0.2, -depth * 0.35), PI / 2), 260)
	place("blank_wall", base * pose(Vector3(width * 0.25, top + 0.2, -depth * 0.7), 0, Vector3(0.75, 0.8, 8.0)), FAR_END)
	place("antenna", base * pose(Vector3(-width * 0.3, top + 0.2, -depth * 0.3)), 220)

func walkup(b: Dictionary) -> void:
	var base := pose(b.front, b.yaw)
	var s: int = b.style
	var entry := 1
	var top := block_facades(base, b.bays, b.depth, b.floors,
		func(i: int, face: int, _count: int) -> String: return ("entrance_residential_%d" if face == 0 and i == entry else "ground_residential_%d") % s,
		func(_i: int, _face: int, _floor: int) -> String: return "bay_apartment_%d" % s, s)
	roof(base, b.bays, b.depth, top, s, int(absf(b.front.x + b.front.z)))
	# Balconies on alternate bays of the street face for the contemporary style.
	if s == 2:
		for fl in range(1, b.floors):
			for i in [0, 2, 3]:
				module("balcony", base * pose(Vector3(-b.bays * 2.0 + 2.0 + i * 4.0, GROUND + (fl - 1) * FLOOR + BALCONY_LIFT, 0)))
	_solid(base, b, top + 0.75)
	var entry_x: float = -b.bays * 2.0 + 2.0 + entry * 4.0
	sign_label(b.name, base * Vector3(entry_x, 3.62, 0.2), b.yaw, 30)

func midrise(b: Dictionary) -> void:
	var base := pose(b.front, b.yaw)
	var s: int = b.style
	var lobby: int = b.bays - 1
	var upper_kind := "bay_office_%d" if b.office else "bay_apartment_%d"
	# Restaurants (RestaurantCatalog) open their ground floor: clear glass, an open entrance
	# bay, and collision/occlusion only for the lobby and the floors above.
	var restaurant := RestaurantCatalog.entry_for_building(b)
	var entrance := RestaurantCatalog.entrance_bay(b) if not restaurant.is_empty() else -1
	clear_glass = not restaurant.is_empty()
	var top := block_facades(base, b.bays, b.depth, b.floors,
		func(i: int, face: int, _count: int) -> String:
			if face == 0:
				if i == lobby: return "entrance_residential_%d" % s
				return ("entrance_%d" if i == entrance else "storefront_%d") % s
			return "ground_residential_%d" % s,
		func(_i: int, _face: int, _floor: int) -> String: return upper_kind % s, s)
	clear_glass = false
	roof(base, b.bays, b.depth, top, s, b.id)
	for i in range(b.bays - 1):
		var x: float = -b.bays * 2.0 + 2.0 + i * 4.0
		if restaurant.is_empty() and (i + b.id) % 2 == 0: module("awning", base * pose(Vector3(x, 3.2, 0.04)))
		if not restaurant.is_empty() and i != entrance:
			# The first bay's awning starts clear of the restaurant's blade sign (RestaurantInteriors
			# hangs it at the left edge, x + 0.2 from the facade end).
			if i == 0: module("awning", base * pose(Vector3(x + 0.225, 3.2, 0.04), 0.0, Vector3(3.45 / 3.9, 1, 1)))
			else: module("awning", base * pose(Vector3(x, 3.2, 0.04)))
		if not b.office and s == 2 and i % 2 == 1:
			for fl in range(1, b.floors): module("balcony", base * pose(Vector3(x, GROUND + (fl - 1) * FLOOR + BALCONY_LIFT, 0)))
	if restaurant.is_empty():
		_solid(base, b, top + 0.75)
		# Shop name on the fascia of the first storefront bay.
		sign_label(b.shop.to_upper(), base * Vector3(-b.bays * 2.0 + 2.0 + 4.0, 3.62, 0.15), b.yaw, 34)
		return
	var width: float = b.bays * 4.0
	var height := top + 0.75
	collider(base * Vector3(0, (3.2 + height) * 0.5, -b.depth * 0.5), Vector3(width, height - 3.2, b.depth), b.yaw)
	occluder(base * Vector3(0, (4.4 + height) * 0.5, -b.depth * 0.5), Vector3(width - 0.6, height - 4.4 - 0.3, b.depth - 0.6), b.yaw)
	var lobby_x: float = width * 0.5 - 2.0
	collider(base * Vector3(lobby_x, 1.6, -b.depth * 0.5), Vector3(4.0, 3.2, b.depth), b.yaw)
	var entrance_x: float = -b.bays * 2.0 + 2.0 + entrance * 4.0
	sign_label("%s  ·  %s" % [str(restaurant[1]).to_upper(), str(restaurant[2]).to_upper()], base * Vector3(entrance_x, 3.68, 0.15), b.yaw, 30)

## Restaurant storefronts swap the window-shader glass for real transparent glass.
var clear_glass := false

func terrace(b: Dictionary) -> void:
	var base := pose(b.front, b.yaw)
	var s: int = b.style
	var units: int = b.units
	var width := units * 5.0
	var depth: float = b.depth
	var eaves := TH_PLINTH + 2 * TH_FLOOR
	for u in range(units):
		var x := -width * 0.5 + 2.5 + u * 5.0
		for face in [0, 1]:
			# Street face, then the garden face (rear doors, same windows).
			var f := base * pose(Vector3(x, 0, 0.0 if face == 0 else -depth), 0.0 if face == 0 else PI)
			module("th_ground_%d" % s, f)
			module("th_upper_%d" % s, f * pose(Vector3(0, TH_PLINTH + TH_FLOOR, 0)))
		var dormer := s != 2 and u % 3 == 1
		module(("th_roof_dormer_%d" if dormer else "th_roof_%d") % s, base * pose(Vector3(x, eaves, 0)))
		# Chimney stacks sit on the party walls, astride the ridge.
		if s != 2 and u > 0:
			module("th_chimney_%d" % s, base * pose(Vector3(x - 2.5, eaves + TH_RISE - 0.55, -depth * 0.5)))
			chimney_tops.append(base * Vector3(x - 2.5, eaves + TH_RISE - 0.55 + 1.8, -depth * 0.5))
	for side in [-1, 1]:
		var gable := base * pose(Vector3(side * width * 0.5, 0, -depth * 0.5), side * PI / 2)
		var scale_y := (eaves + 0.92) / eaves if s == 2 else 1.0
		module("th_gable_%d" % s, gable * pose(Vector3.ZERO, 0, Vector3(1, scale_y, 1)))
	# Paths from each front door to the sidewalk; one collider for the row, low ones for steps.
	var ridge := eaves + (TH_RISE if s != 2 else 0.9)
	collider(base * Vector3(0, ridge * 0.5, -depth * 0.5), Vector3(width, ridge, depth), b.yaw)
	for u in range(units):
		var door_x := -width * 0.5 + 2.5 + u * 5.0 - 1.55
		collider(base * Vector3(door_x, TH_PLINTH * 0.5, 0.45), Vector3(1.4, TH_PLINTH, 0.9), b.yaw)
		place("interior_slab", base * pose(Vector3(door_x, 0.0, 1.6), 0, Vector3(0.3, 0.5, 0.375)), 120, 0.0, false)
	occluder(base * Vector3(0, eaves * 0.5, -depth * 0.5), Vector3(width - 0.4, eaves - 0.2, depth - 0.4), b.yaw)

func _solid(base: Transform3D, b: Dictionary, height: float) -> void:
	var width: float = b.bays * 4.0
	collider(base * Vector3(0, height * 0.5, -b.depth * 0.5), Vector3(width, height, b.depth), b.yaw)
	occluder(base * Vector3(0, height * 0.5, -b.depth * 0.5), Vector3(width - 0.6, height - 0.6, b.depth - 0.6), b.yaw)

## Changes whenever a kit GLB the batches use is re-exported.
func source_stamp() -> int:
	var names := assets_used.keys()
	names.sort()
	var stamp := CACHE_VERSION
	for asset: String in names:
		for path in [CityKit.MODULES % asset, "res://world/downtown/assets/%s.glb" % asset]:
			if FileAccess.file_exists(path): stamp = hash([stamp, asset, FileAccess.get_modified_time(path)])
	return stamp

## One mesh per building and LOD range, one surface per material, local to the building (no
## materials: they are set after loading/saving so the cache holds geometry only).
static func merge(data: Dictionary) -> ArrayMesh:
	var origin: Vector3 = data.origin
	var merged := ArrayMesh.new()
	for surface: Dictionary in data.surfaces.values():
		var tool := SurfaceTool.new()
		for part in surface.parts:
			var mesh: Mesh = part[0]
			var t: Transform3D = part[1]
			t.origin -= origin
			for s in range(mesh.get_surface_count()): tool.append_from(mesh, s, t)
		tool.commit(merged)
	return merged

func flush() -> void:
	var stamp := source_stamp()
	# headless runs (tests) use a dummy renderer: never write or trust their meshes
	var cache := use_cache and DisplayServer.get_name() != "headless" and DirAccess.make_dir_recursive_absolute(CACHE_DIR) == OK
	var used := {}
	var missed := 0
	for data: Dictionary in batches.values():
		var origin: Vector3 = data.origin
		var file := "%s/%08x.res" % [CACHE_DIR, hash([stamp, data.sig, data.start, data.end, data.shadows, origin])]
		used[file.get_file()] = true
		var merged: ArrayMesh = null
		if cache and FileAccess.file_exists(file):
			merged = ResourceLoader.load(file, "ArrayMesh", ResourceLoader.CACHE_MODE_IGNORE) as ArrayMesh
			if merged != null and (merged.get_surface_count() != data.surfaces.size() or merged.surface_get_array_len(0) == 0): merged = null
		if merged == null:
			missed += 1
			merged = merge(data)
			if cache: ResourceSaver.save(merged, file)
		var surface_index := 0
		for surface: Dictionary in data.surfaces.values():
			merged.surface_set_material(surface_index, surface.material)
			surface_index += 1
		var node := MeshInstance3D.new()
		node.mesh = merged
		node.position = origin
		node.visibility_range_begin = data.start
		node.visibility_range_end = data.end
		node.visibility_range_begin_margin = 8.0 if data.start > 0 else 0.0
		node.visibility_range_end_margin = 8.0
		if not data.shadows: node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
	batches.clear()
	if cache and missed > 0:
		# drop meshes no current batch uses (old layouts / re-exported modules)
		for name in DirAccess.get_files_at(CACHE_DIR):
			if not used.has(name): DirAccess.remove_absolute(CACHE_DIR.path_join(name))
