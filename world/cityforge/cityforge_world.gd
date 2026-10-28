class_name CityForgeWorld
extends Node3D
## Port Halden, the generated city (tools/cityforge: plan_city.py -> build_city.py).
## Loads assets/cityforge: city.json (the whole plan: roads, lots, buildings, furniture, names),
## heights.f32 (graded ground), kit.glb (repeated models, LOD0 + LOD1) and one GLB per 256 m chunk
## (terrain, water, roads, walks, fences, buildings, and "Far": every repeated model merged at LOD1).
##
## Drawing: near a chunk its repeated models are MultiMeshes per 128 m cell (LOD0, per-instance
## colours); further away the chunk's merged Far mesh replaces them (HLOD: the cells name the Far
## mesh as their visibility parent, so exactly one of the two is drawn, with a cross-fade).
## Collision: one heightmap for the ground; road/sidewalk trimeshes and building boxes are made
## per chunk on demand near the focus (update_focus), so start-up stays cheap.

const DIR := "res://assets/cityforge/"
const CHUNK := 256.0
const CELL_LOD0 := 128.0
const FAR_BEGIN := 230.0          ## a chunk's Far mesh hides inside this distance (from its centre) ...
const NEAR_END := 430.0           ## ... and its LOD0 cells show to here (230 + chunk half-diagonal 181 < 430: no gaps)
const DETAIL_END := 140.0         ## small props (hydrants, benches, stop signs) only near
const STREET_END := 520.0         ## lamps, signals and shelters (not in the far mesh) fade out here
const PART_RANGE := {"Fences": 320.0, "Walks": 1100.0, "Roads": 2600.0}
const COLLISION_RADIUS := 300.0
## Sidewalk centre from a lot's front line, towards the street (verge 1.6 m beyond it).
const SIDEWALK_OFFSET := 1.5
const TREES := ["tree_maple", "tree_cherry", "tree_column", "tree_linden", "tree_oak", "tree_fir", "tree_birch"]

var city: Dictionary = {}
var size := 2048.0
var grid := 513
var cell := 4.0
var heights := PackedFloat32Array()
var kit: Dictionary = {}                 ## name -> [Mesh LOD0, Mesh LOD1]
var chunks: Dictionary = {}              ## Vector2i -> Node3D (the chunk scene)
var far_nodes: Dictionary = {}           ## Vector2i -> GeometryInstance3D
var collided: Dictionary = {}            ## Vector2i -> true once its collision exists
var lots_by_chunk: Dictionary = {}
var stats: Dictionary = {}
var _focus_timer := 0.0

func _ready() -> void:
	if city.is_empty(): build()

## Collision follows whatever the active camera looks from (the courier in the game).
func _process(delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	if cam != null: update_focus(cam.global_position, delta)

## Everything that does not need a focus: data, ground collision, chunk visuals, instances, labels.
func build() -> void:
	var t0 := Time.get_ticks_msec()
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DIR + "city.json"))
	city = parsed as Dictionary
	size = float(city.size_m)
	grid = int(city.grid)
	cell = float(city.cell_m)
	heights = FileAccess.get_file_as_bytes(DIR + "heights.f32").to_float32_array()
	_build_ground_collision()
	_load_kit()
	_load_chunks()
	_place_instances()
	_place_labels()
	_place_sign_labels()
	stats["build_ms"] = Time.get_ticks_msec() - t0

## City plan metres (x east, y north) and a height -> Godot position.
func to_world(x: float, y: float, h: float = 0.0) -> Vector3:
	return Vector3(x - size * 0.5, h, -(y - size * 0.5))

func to_plan(p: Vector3) -> Vector2:
	return Vector2(p.x + size * 0.5, size * 0.5 - p.z)

## Graded ground height at a world position (bilinear on the 4 m grid).
func ground_height(p: Vector3) -> float:
	var q := to_plan(p) / cell
	var fx := clampf(q.x, 0.0, grid - 1.001)
	var fy := clampf(q.y, 0.0, grid - 1.001)
	var i := int(fx)
	var j := int(fy)
	var tx := fx - i
	var ty := fy - j
	var a := heights[j * grid + i]
	var b := heights[j * grid + i + 1]
	var c := heights[(j + 1) * grid + i]
	var d := heights[(j + 1) * grid + i + 1]
	return lerpf(lerpf(a, b, tx), lerpf(c, d, tx), ty)

func _chunk_key(x: float, y: float) -> Vector2i:
	var n := int(size / CHUNK)
	return Vector2i(clampi(int(x / CHUNK), 0, n - 1), clampi(int(y / CHUNK), 0, n - 1))

# --- ground ----------------------------------------------------------------------------------
func _build_ground_collision() -> void:
	# HeightMapShape3D rows run along +Z (south); the plan's rows run north, so flip them.
	var data := PackedFloat32Array()
	data.resize(grid * grid)
	for r in grid:
		var j := grid - 1 - r
		for i in grid:
			data[r * grid + i] = heights[j * grid + i]
	var shape := HeightMapShape3D.new()
	shape.map_width = grid
	shape.map_depth = grid
	shape.map_data = data
	var body := StaticBody3D.new()
	body.name = "Ground"
	var col := CollisionShape3D.new()
	col.shape = shape
	col.scale = Vector3(cell, 1.0, cell)
	body.add_child(col)
	add_child(body)

# --- kit -------------------------------------------------------------------------------------
func _load_kit() -> void:
	_load_kit_file(DIR + "kit.glb")
	if ResourceLoader.exists(DIR + "houses.glb"): _load_kit_file(DIR + "houses.glb")      # the house catalogue (houses.py)

func _load_kit_file(path: String) -> void:
	var scene := (load(path) as PackedScene).instantiate()
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var key := str(mi.name)
		var lod := 1 if key.ends_with("_LOD1") else 0
		key = key.trim_suffix("_LOD1")
		CityForgeMaterials.apply(mi.mesh)
		if not kit.has(key): kit[key] = [null, null]
		(kit[key] as Array)[lod] = mi.mesh
	scene.free()

# --- chunks ----------------------------------------------------------------------------------
func _load_chunks() -> void:
	var n := int(size / CHUNK)
	var tris := 0
	for ci in n:
		for cj in n:
			var path := DIR + "chunks/c_%d_%d.glb" % [ci, cj]
			if not ResourceLoader.exists(path): continue
			var chunk := (load(path) as PackedScene).instantiate() as Node3D
			chunk.name = "Chunk_%d_%d" % [ci, cj]
			add_child(chunk)
			var key := Vector2i(ci, cj)
			chunks[key] = chunk
			for node in chunk.find_children("*", "MeshInstance3D", true, false):
				var mi := node as MeshInstance3D
				CityForgeMaterials.apply(mi.mesh)
				var part := str(mi.name).get_slice("_", 0)
				if PART_RANGE.has(part):
					mi.visibility_range_end = PART_RANGE[part]
					mi.visibility_range_end_margin = 20.0
				if part == "Far":
					mi.visibility_range_begin = FAR_BEGIN
					mi.visibility_range_begin_margin = 25.0
					mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DEPENDENCIES
					far_nodes[key] = mi
				if part == "Terrain" or part == "Water" or part == "Far":
					mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if part != "Far" else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				tris += triangles(mi.mesh)
	if ResourceLoader.exists(DIR + "outskirts.glb"):
		var ring := (load(DIR + "outskirts.glb") as PackedScene).instantiate() as Node3D
		ring.name = "Outskirts"
		add_child(ring)
		for node in ring.find_children("*", "MeshInstance3D", true, false):
			var mi := node as MeshInstance3D
			CityForgeMaterials.apply(mi.mesh)
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if str(mi.name).begins_with("Sea"): mi.position.y = -0.06     # under the city's own water
	stats["chunks"] = chunks.size()
	stats["chunk_tris"] = tris

static func triangles(mesh: Mesh) -> int:
	var am := mesh as ArrayMesh
	if am == null: return 0
	var n := 0
	for s in am.get_surface_count():
		var idx := am.surface_get_array_index_len(s)
		n += (idx if idx > 0 else am.surface_get_array_len(s)) / 3
	return n

# --- repeated models -------------------------------------------------------------------------
## One placement: kit name, plan position/height, yaw, scale, siding (colour) and roof (custom) tints.
func _place_instances() -> void:
	var groups: Dictionary = {}          # [kit name, cell key] -> Array of [Transform3D, Color, Color]
	var pal: Dictionary = city.palettes
	var siding: Array = pal.siding
	var roof: Array = pal.roof
	var leaves: Array = pal.leaves
	for hs: Dictionary in city.houses:
		if hs.has("kit"):            # a catalogue house: its own size, its own paint
			_add(groups, str(hs.kit), hs.pos, float(hs.h), float(hs.yaw), Vector3.ONE, Color(str(hs.tint)), Color(str(hs.roof_tint)))
			continue
		var size_: Array = hs.size
		var sc := Vector3(float(size_[0]) / 10.0, 1.0, float(size_[1]) / 12.0)
		_add(groups, "house_" + str(hs.archetype), hs.pos, float(hs.h), float(hs.yaw), sc,
			Color(str(siding[int(hs.siding) % siding.size()])), Color(str(roof[int(hs.roof) % roof.size()])))
	for g: Dictionary in city.garages:
		_add(groups, "garage", g.pos, float(g.h), float(g.yaw), Vector3.ONE,
			Color(str(siding[int(g.siding) % siding.size()])), Color(str(roof[int(g.roof) % roof.size()])))
	var props: Dictionary = city.props
	var trees: Array = props.tree
	for k in trees.size():
		var t: Array = trees[k]
		var s := 0.85 + 0.3 * fmod(k * 0.6180339, 1.0)
		var choices: Array = leaves[int(t[4])]
		_add(groups, TREES[int(t[4])], [t[0], t[1]], float(t[2]), float(t[3]), Vector3.ONE * s, Color(str(choices[(k * 7919) % choices.size()])), Color.WHITE)
	for kind: String in ["lamp", "traffic_light", "bus_stop", "hydrant", "bench", "stop_sign", "utility_pole", "vending_machine",
			"post_box", "phone_box", "ad_column", "cesme", "cafe_set"]:
		for p: Array in props.get(kind, []):
			_add(groups, kind, [p[0], p[1]], float(p[2]), float(p[3]), Vector3.ONE, Color.WHITE, Color.WHITE)
	# street-name boards: a pole and two blades in the district's colours (the names are Label3Ds)
	var cultures: Dictionary = city.get("cultures", {})
	for p: Array in props.get("street_sign", []):
		var sign_col := Color(str((cultures.get(str(p[7]), {"sign": "1f6b3a"}) as Dictionary).sign))
		_add(groups, "sign_pole", [p[0], p[1]], float(p[2]), 0.0, Vector3.ONE, Color.WHITE, Color.WHITE)
		_add(groups, "sign_blade", [p[0], p[1]], float(p[2]) + 2.95, float(p[3]), Vector3.ONE, sign_col, Color.WHITE)
		_add(groups, "sign_blade", [p[0], p[1]], float(p[2]) + 2.65, float(p[4]), Vector3.ONE, sign_col, Color.WHITE)
		for k in range(8, p.size(), 2):          # extra blades for streets whose own corner had no room
			_add(groups, "sign_blade", [p[0], p[1]], float(p[2]) + 2.35 - 0.3 * ((k - 8) / 2), float(p[k]), Vector3.ONE, sign_col, Color.WHITE)
	var count := 0
	var nodes := 0
	for key: Array in groups:
		var name_: String = key[0]
		var cell_key: Vector2i = key[1]
		var items: Array = groups[key]
		count += items.size()
		var detail := name_ in ["hydrant", "bench", "stop_sign", "sign_pole", "sign_blade", "vending_machine", "post_box", "phone_box",
			"ad_column", "cesme", "cafe_set"]
		var in_far := name_.begins_with("house_") or name_.begins_with("H_") or name_ == "garage" or name_.begins_with("tree_")
		var mi := _multimesh(kit[name_][0] as Mesh, items)
		mi.name = "%s_%d_%d" % [name_, cell_key.x, cell_key.y]
		var centre := Vector2((cell_key.x + 0.5) * CELL_LOD0, (cell_key.y + 0.5) * CELL_LOD0)
		var chunk_key := _chunk_key(centre.x, centre.y)
		var parent: Node3D = chunks.get(chunk_key, self)
		parent.add_child(mi)
		nodes += 1
		if detail:
			mi.visibility_range_end = DETAIL_END
			mi.visibility_range_end_margin = 15.0
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		else:
			mi.visibility_range_end = NEAR_END if in_far else STREET_END
			mi.visibility_range_end_margin = 25.0
			if in_far and far_nodes.has(chunk_key):
				mi.visibility_parent = mi.get_path_to(far_nodes[chunk_key])
	stats["instances"] = count
	stats["instance_nodes"] = nodes

func _add(groups: Dictionary, name_: String, pos: Array, h: float, yaw: float, sc: Vector3, a: Color, b: Color) -> void:
	if not kit.has(name_): return
	var x := float(pos[0])
	var y := float(pos[1])
	var key := [name_, Vector2i(int(x / CELL_LOD0), int(y / CELL_LOD0))]
	if not groups.has(key): groups[key] = []
	var basis := Basis(Vector3.UP, yaw) * Basis.from_scale(sc)
	(groups[key] as Array).append([Transform3D(basis, to_world(x, y, h)), a, b])

func _multimesh(mesh: Mesh, items: Array) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = items.size()
	for k in items.size():
		var it: Array = items[k]
		mm.set_instance_transform(k, it[0])
		mm.set_instance_color(k, it[1])
		mm.set_instance_custom_data(k, it[2])
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	return mi

# --- names -----------------------------------------------------------------------------------
const SIGN_RANGE := 45.0

## Street names on both faces of every blade of every corner board (only drawn near the camera).
func _place_sign_labels() -> void:
	var cultures: Dictionary = city.get("cultures", {})
	var holder := Node3D.new()
	holder.name = "StreetSigns"
	add_child(holder)
	var count := 0
	for p: Array in (city.props as Dictionary).get("street_sign", []):
		var sign_col := Color(str((cultures.get(str(p[7]), {"sign": "1f6b3a"}) as Dictionary).sign))
		var ink := Color("1c1c1c") if sign_col.get_luminance() > 0.6 else Color("f6f6f2")
		var blades: Array = [[float(p[3]), 2.95, str(p[5])], [float(p[4]), 2.65, str(p[6])]]
		for k in range(8, p.size(), 2): blades.append([float(p[k]), 2.35 - 0.3 * ((k - 8) / 2), str(p[k + 1])])
		for blade: Array in blades:
			var yaw: float = blade[0]
			var basis := Basis(Vector3.UP, yaw)
			var at := to_world(float(p[0]), float(p[1]), float(p[2]) + float(blade[1]))
			for side in [1.0, -1.0]:
				var label := Label3D.new()
				label.text = str(blade[2])
				label.font_size = 48
				label.outline_size = 0
				label.modulate = ink
				label.pixel_size = minf(0.0021, 1.0 / maxf(1.0, label.text.length() * 0.56 * 48.0))
				label.double_sided = false
				label.visibility_range_end = SIGN_RANGE
				label.transform = Transform3D(basis if side > 0 else basis * Basis(Vector3.UP, PI), at + basis * Vector3(0, 0, 0.018 * side))
				holder.add_child(label)
				count += 1
	stats["sign_labels"] = count

func _place_labels() -> void:
	for pb: Dictionary in city.public:
		var label := Label3D.new()
		label.text = str(pb.name)
		label.font_size = 96
		label.pixel_size = 0.012
		label.outline_size = 18
		label.modulate = Color("f4f1e6")
		var pos: Array = pb.pos
		var yaw := float(pb.yaw)
		var front := Vector3(0, 0, -1).rotated(Vector3.UP, yaw)
		var depth: Array = pb.size
		label.position = to_world(float(pos[0]), float(pos[1]), float(pb.h) + 7.5) + front * (minf(float(depth[1]), 30.0) * 0.5 + 0.6)
		label.rotation.y = yaw
		label.visibility_range_end = 220.0
		label.name = "Name_" + str(pb.id)
		add_child(label)

# --- collision near the focus ----------------------------------------------------------------
## Call with the player's position (cheap; does real work only every half second and per new chunk).
func update_focus(p: Vector3, delta: float = 1.0) -> void:
	_focus_timer -= delta
	if _focus_timer > 0.0: return
	_focus_timer = 0.5
	var q := to_plan(p)
	for key: Vector2i in chunks:
		if collided.has(key): continue
		var centre := Vector2((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)
		if q.distance_to(centre) < COLLISION_RADIUS + CHUNK * 0.71:
			_build_chunk_collision(key)

func _build_chunk_collision(key: Vector2i) -> void:
	collided[key] = true
	var chunk: Node3D = chunks[key]
	var body := StaticBody3D.new()
	body.name = "Collision"
	chunk.add_child(body)
	for node in chunk.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var part := str(mi.name).get_slice("_", 0)
		if part in ["Roads", "Walks", "Buildings", "Fences"]:
			var shape := mi.mesh.create_trimesh_shape()
			var col := CollisionShape3D.new()
			col.shape = shape
			col.transform = mi.transform
			body.add_child(col)
	# repeated models: boxes (houses, garages) and thin posts
	var lo := Vector2(key.x * CHUNK, key.y * CHUNK)
	var hi := lo + Vector2(CHUNK, CHUNK)
	for hs: Dictionary in city.houses:
		_box_if_inside(body, hs.pos, lo, hi, float(hs.h), float(hs.yaw), Vector3(float((hs.size as Array)[0]), float(hs.get("height", 6.5)), float((hs.size as Array)[1])))
	for g: Dictionary in city.garages:
		_box_if_inside(body, g.pos, lo, hi, float(g.h), float(g.yaw), Vector3(6.4, 3.4, 6.4))
	var props: Dictionary = city.props
	for kind: String in ["lamp", "traffic_light", "tree"]:
		for p: Array in props[kind]:
			_box_if_inside(body, [p[0], p[1]], lo, hi, float(p[2]), 0.0, Vector3(0.45, 4.0, 0.45))

func _box_if_inside(body: StaticBody3D, pos: Array, lo: Vector2, hi: Vector2, h: float, yaw: float, extent: Vector3) -> void:
	var x := float(pos[0])
	var y := float(pos[1])
	if x < lo.x or y < lo.y or x >= hi.x or y >= hi.y: return
	var shape := BoxShape3D.new()
	shape.size = extent
	var col := CollisionShape3D.new()
	col.shape = shape
	col.transform = Transform3D(Basis(Vector3.UP, yaw), to_world(x, y, h + extent.y * 0.5))
	body.add_child(col)

## Every chunk's collision at once (tests, or a loading screen that wants it all).
func build_all_collision() -> void:
	for key: Vector2i in chunks:
		if not collided.has(key): _build_chunk_collision(key)

# --- roads for game systems -----------------------------------------------------------------
var _graph_pos: PackedVector2Array
var _graph_links: Array = []

func _build_graph() -> void:
	var ids := {}
	for nd: Dictionary in city.nodes:
		ids[int(nd.id)] = _graph_pos.size()
		var p: Array = nd.pos
		_graph_pos.append(Vector2(float(p[0]), float(p[1])))
		_graph_links.append([])
	for r: Dictionary in city.roads:
		var a: int = ids[int(r.a)]
		var b: int = ids[int(r.b)]
		(_graph_links[a] as Array).append(b)
		(_graph_links[b] as Array).append(a)

func _nearest_node(q: Vector2) -> int:
	var best := -1
	var bd := INF
	for i in _graph_pos.size():
		if (_graph_links[i] as Array).is_empty(): continue
		var d := q.distance_squared_to(_graph_pos[i])
		if d < bd:
			bd = d
			best = i
	return best

## A street route between two world points (A* over the road graph), for the minimap and distances.
func route(from: Vector3, to: Vector3) -> PackedVector3Array:
	if _graph_pos.is_empty(): _build_graph()
	var a := _nearest_node(to_plan(from))
	var b := _nearest_node(to_plan(to))
	var out := PackedVector3Array([Vector3(from.x, 0, from.z)])
	if a >= 0 and b >= 0 and a != b:
		var came := {a: -1}
		var cost := {a: 0.0}
		var open: Array = [a]
		while not open.is_empty():
			var cur: int = open[0]
			var best_f := INF
			for n: int in open:
				var f: float = float(cost[n]) + _graph_pos[n].distance_to(_graph_pos[b])
				if f < best_f:
					best_f = f
					cur = n
			if cur == b: break
			open.erase(cur)
			for nb: int in _graph_links[cur]:
				var c: float = float(cost[cur]) + _graph_pos[cur].distance_to(_graph_pos[nb])
				if not cost.has(nb) or c < float(cost[nb]):
					cost[nb] = c
					came[nb] = cur
					if not open.has(nb): open.append(nb)
		if came.has(b):
			var chain: Array = []
			var n := b
			while n != -1:
				chain.push_front(n)
				n = came[n]
			for i: int in chain:
				out.append(to_world(_graph_pos[i].x, _graph_pos[i].y))
	out.append(Vector3(to.x, 0, to.z))
	return out

var _described_at := Vector3(INF, 0, INF)
var _description := ""

## The HUD's location line: the street you are on, else the park, else the neighbourhood.
func describe(at: Vector3) -> String:
	if at.distance_squared_to(_described_at) < 4.0: return _description
	_described_at = at
	var q := to_plan(at)
	var ids := {}
	for nd: Dictionary in city.nodes: ids[int(nd.id)] = nd.pos
	var best := ""
	var best_d := INF
	for r: Dictionary in city.roads:
		var a: Array = ids[int(r.a)]
		var b: Array = ids[int(r.b)]
		var pa := Vector2(float(a[0]), float(a[1]))
		var pb := Vector2(float(b[0]), float(b[1]))
		var d := q.distance_to(Geometry2D.get_closest_point_to_segment(q, pa, pb)) - float(r.width) * 0.5
		if d < best_d:
			best_d = d
			best = str(r.name)
	if best_d < 6.0:
		_description = best
		return best
	for pk: Dictionary in city.parks:
		if pk.has("rect"):
			var rc: Array = pk.rect
			if q.x > float(rc[0]) and q.x < float(rc[2]) and q.y > float(rc[1]) and q.y < float(rc[3]):
				_description = str(pk.name)
				return _description
	var near_name := "Port Halden"
	var nd_best := INF
	for n: Dictionary in city.neighbourhoods:
		var d2 := q.distance_squared_to(Vector2(float((n.centre as Array)[0]), float((n.centre as Array)[1])))
		if d2 < nd_best:
			nd_best = d2
			near_name = str(n.name)
	_description = near_name
	return near_name

## Road centre lines for the minimap: [from, to, width] in world metres.
func map_roads() -> Array:
	var ids := {}
	for nd: Dictionary in city.nodes: ids[int(nd.id)] = nd.pos
	var out: Array = []
	for r: Dictionary in city.roads:
		var a: Array = ids[int(r.a)]
		var b: Array = ids[int(r.b)]
		out.append([to_world(float(a[0]), float(a[1])), to_world(float(b[0]), float(b[1])), float(r.width)])
	for ln: Dictionary in city.lanes:
		out.append([to_world(float((ln.a as Array)[0]), float((ln.a as Array)[1])), to_world(float((ln.b as Array)[0]), float((ln.b as Array)[1])), 5.0])
	return out

# --- queries for game systems ----------------------------------------------------------------
## The lot / house / address nearest to a world position (deliveries, map).
func nearest_house(p: Vector3) -> Dictionary:
	var q := to_plan(p)
	var best: Dictionary = {}
	var bd := INF
	for hs: Dictionary in city.houses:
		var pos: Array = hs.pos
		var d := q.distance_squared_to(Vector2(float(pos[0]), float(pos[1])))
		if d < bd:
			bd = d
			best = hs
	return best

## The front door of a house (world position on the step, facing out).
func house_door(hs: Dictionary) -> Vector3:
	var pos: Array = hs.pos
	var base := to_world(float(pos[0]), float(pos[1]), float(hs.h))
	var basis := Basis(Vector3.UP, float(hs.yaw))
	if hs.has("door"):           # the catalogue's door (Blender x, y: front +Y) plus a step out
		var d: Array = hs.door
		return base + basis * Vector3(float(d[0]), 0.0, -float(d[1]) - 0.4)
	var depth := float((hs.size as Array)[1])
	return base + basis * Vector3(0, 0, -(depth * 0.5 + 0.4))

func set_night(amount: float) -> void:
	CityForgeMaterials.set_night(amount)
