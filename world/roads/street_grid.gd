class_name StreetGrid
extends Node3D
## Lays the Blender street kit (world/roads/build_road_kit.py) over the neighbourhood
## grid: decks with gutters and curbs, double yellow centre lines, edge lines, green
## bike lanes with symbols, junction pads with dashed bike conflict markings,
## continental crosswalks and stop bars. Right-hand traffic.

const KIT := "res://world/roads/%s.glb"
const SURFACE_Y := 0.03
const SEGMENT := 12.0
## Cross-sections; distances are from the centreline. Must match build_road_kit.py.
const AVENUE := {"deck": "avenue_deck", "marks": "avenue_marks_half", "half": 6.0, "edge": 5.55,
	"lane": 1.95, "bike": 4.7, "bike_width": 1.7}
const STREET := {"deck": "street_deck", "marks": "street_marks_half", "half": 5.0, "edge": 4.7,
	"lane": 1.64, "bike": 3.975, "bike_width": 1.45}
const CROSSWALK_GAP := 0.5 ## junction edge to crosswalk
const CROSSWALK_LENGTH := 3.0
const STOP_OFFSET := 0.8 ## crosswalk to stop bar centre
const MIN_MARKED_RUN := 8.0
const SYMBOL_SPACING := 48.0

var _pieces: Dictionary = {} ## piece key -> {"mesh": Mesh, "transforms": Array[Transform3D]}
var _materials: Dictionary = {}
## Placed transforms per piece, kept for validation (MultiMesh data is GPU-side).
var layout: Dictionary = {}

## Roads as centrelines in (x, z); `crossings` are mid-block pedestrian crossings by z/x.
static func roads() -> Array[Dictionary]:
	var list: Array[Dictionary] = [
		{"name": "CedarLane", "a": Vector2(0, 44), "b": Vector2(0, -690), "profile": AVENUE, "crossings": [17.0, -93.0, -177.0]},
	]
	for x in CityCatalog.SIDE_ROADS:
		list.append({"name": "SideRoad%d" % x, "a": Vector2(x, -258), "b": Vector2(x, -678), "profile": STREET, "crossings": []})
	for z in CityCatalog.CROSS_STREETS:
		# Cross streets continue east to the downtown street grid at x = 120.
		list.append({"name": "CrossStreet%d" % z, "a": Vector2(-69, z), "b": Vector2(120, z), "profile": STREET, "crossings": []})
	return list

## Lateral offset of the traffic-lane centre for vehicles on the given profile.
static func lane_offset(profile: Dictionary) -> float:
	return profile.lane

func _ready() -> void:
	var list := roads()
	var pads: Dictionary = {}
	for road in list:
		build_road(road, junctions_for(road, list, pads))
	for key in pads:
		var pad: Dictionary = pads[key]
		add_piece("junction_pad", null, Transform3D(Basis.from_scale(Vector3(pad.size.x, 1, pad.size.y)), Vector3(pad.at.x, SURFACE_Y, pad.at.y)))
	flush()

## Junctions along `road` as {"s", "half", "pad"}, registering junction pads by position.
func junctions_for(road: Dictionary, list: Array[Dictionary], pads: Dictionary) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var a: Vector2 = road.a
	var b: Vector2 = road.b
	var along_z := is_equal_approx(a.x, b.x)
	for other in list:
		if other == road: continue
		var oa: Vector2 = other.a
		var ob: Vector2 = other.b
		if is_equal_approx(oa.x, ob.x) == along_z: continue
		var point := Vector2(a.x, oa.y) if along_z else Vector2(oa.x, a.y)
		if not (on_segment(point, a, b) and on_segment(point, oa, ob)): continue
		# `band` is the crossing road's bike lane, measured from the junction centre.
		var band := Vector2(other.profile.edge - other.profile.bike_width, other.profile.edge)
		result.append({"s": a.distance_to(point), "half": other.profile.half, "band": band})
		var size := Vector2(road.profile.half, other.profile.half) * 2 if along_z else Vector2(other.profile.half, road.profile.half) * 2
		pads["%d_%d" % [roundi(point.x), roundi(point.y)]] = {"at": point, "size": size}
	result.sort_custom(func(l, r): return l.s < r.s)
	return result

static func on_segment(p: Vector2, a: Vector2, b: Vector2) -> bool:
	return Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p) < 0.01

func build_road(road: Dictionary, junctions: Array[Dictionary]) -> void:
	var profile: Dictionary = road.profile
	var a: Vector2 = road.a
	var b: Vector2 = road.b
	var length := a.distance_to(b)
	var dir2 := (b - a) / length
	var along := Vector3(dir2.x, 0, dir2.y)
	var right := Vector3(-along.z, 0, along.x)
	var point := func(s: float, lateral: float, outward: Vector3) -> Vector3:
		var p := a + dir2 * s
		return Vector3(p.x, SURFACE_Y, p.y) + outward * lateral
	# Deck runs fill everything outside junction boxes.
	var blocked: Array[Vector2] = []
	for j in junctions: blocked.append(Vector2(j.s - j.half, j.s + j.half))
	var runs := subtract(Vector2(0, length), blocked)
	for run in runs:
		var count := maxi(1, roundi((run.y - run.x) / SEGMENT))
		var piece := (run.y - run.x) / count
		for i in range(count):
			var mid := run.x + piece * (i + 0.5)
			add_piece(profile.deck, profile, Transform3D(Basis(right, Vector3.UP, right.cross(Vector3.UP) * piece / SEGMENT), point.call(mid, 0, right)))
	for half in [1.0, -1.0]:
		var outward: Vector3 = right * half
		var travel := -outward.cross(Vector3.UP) # local -Z of the half basis
		var t := signf(travel.dot(along)) # +1 when this half travels toward increasing s
		var half_basis := Basis(outward, Vector3.UP, outward.cross(Vector3.UP))
		var cuts: Array[Vector2] = []
		for j in junctions:
			var near: float = j.half + CROSSWALK_GAP + CROSSWALK_LENGTH + STOP_OFFSET + 0.2
			var far: float = j.half + CROSSWALK_GAP + CROSSWALK_LENGTH + 0.3
			# Approach side ends at the stop bar; departure side resumes after the crosswalk.
			cuts.append(Vector2(j.s - near, j.s + far) if t > 0 else Vector2(j.s - far, j.s + near))
		for c in road.crossings:
			var sc := absf(c - (a.y if is_equal_approx(a.x, b.x) else a.x))
			# Signalled crossings keep their stop bars 5 m out (see CedarNeighborhood).
			cuts.append(Vector2(sc - 5.15, sc + 1.8) if t > 0 else Vector2(sc - 1.8, sc + 5.15))
		for run in runs:
			if run.y - run.x < MIN_MARKED_RUN: continue
			for marked in subtract(run, cuts):
				var span := marked.y - marked.x
				if span < 1.0: continue
				var count := maxi(1, roundi(span / SEGMENT))
				var piece := span / count
				for i in range(count):
					var mid := marked.x + piece * (i + 0.5)
					var stretched := Basis(outward, Vector3.UP, outward.cross(Vector3.UP) * piece / SEGMENT)
					add_piece(profile.marks, profile, Transform3D(stretched, point.call(mid, 0, outward)))
				# Bike symbols a few metres into each marked stretch, then at intervals.
				var s := marked.x + 5.0 if t > 0 else marked.y - 5.0
				while (s < marked.y - 4.0) if t > 0 else (s > marked.x + 4.0):
					add_piece("bike_symbol", null, Transform3D(half_basis, point.call(s, profile.bike, outward) + Vector3(0, 0.001, 0)))
					s += SYMBOL_SPACING * t
		for j in junctions:
			var before := has_run(runs, j.s - j.half - 1.0)
			var after := has_run(runs, j.s + j.half + 1.0)
			# Dashed green conflict markings carry the bike lane through the junction.
			# Symmetric 1 m dashes, leaving the crossing road's own bike lane clear.
			if before and after:
				for k in range(-4, 5):
					var offset := k * 2.0
					if absf(offset) + 0.5 > j.half: continue
					if absf(offset) + 0.5 > j.band.x and absf(offset) - 0.5 < j.band.y: continue
					add_tile("bike_conflict_tile", point.call(j.s + offset, profile.bike, outward), along, 1.0, profile.bike_width)
			var approach := before if t > 0 else after
			if approach and run_length_at(runs, j.s - t * (j.half + 1.0)) >= MIN_MARKED_RUN:
				var stop_s: float = j.s - t * (j.half + CROSSWALK_GAP + CROSSWALK_LENGTH + STOP_OFFSET)
				var inner := 0.25
				var outer: float = profile.edge - 0.15
				add_tile("paint_white_tile", point.call(stop_s, (inner + outer) * 0.5, outward), along, 0.4, outer - inner)
	# Continental crosswalk bars: beside every junction with a marked approach, and mid-block.
	var crossings: Array[float] = []
	for j in junctions:
		for side in [-1.0, 1.0]:
			var s: float = j.s + side * (j.half + CROSSWALK_GAP + CROSSWALK_LENGTH * 0.5)
			if run_length_at(runs, j.s + side * (j.half + 1.0)) >= MIN_MARKED_RUN: crossings.append(s)
	for c in road.crossings: crossings.append(absf(c - (a.y if is_equal_approx(a.x, b.x) else a.x)))
	var bars := floori((profile.edge - 0.3) * 2 / 1.2) + 1
	for s in crossings:
		for i in range(bars):
			var lateral := -(bars - 1) * 0.6 + i * 1.2
			add_tile("paint_white_tile", point.call(s, lateral, right), along, CROSSWALK_LENGTH, 0.6)

static func has_run(runs: Array[Vector2], s: float) -> bool:
	return run_length_at(runs, s) > 0.0

static func run_length_at(runs: Array[Vector2], s: float) -> float:
	for run in runs:
		if s >= run.x and s <= run.y: return run.y - run.x
	return 0.0

## Interval `span` minus `cuts`, as sorted (start, end) pairs.
static func subtract(span: Vector2, cuts: Array[Vector2]) -> Array[Vector2]:
	var pieces: Array[Vector2] = [span]
	for cut in cuts:
		var next: Array[Vector2] = []
		for p in pieces:
			if cut.y <= p.x or cut.x >= p.y:
				next.append(p)
				continue
			if cut.x > p.x: next.append(Vector2(p.x, cut.x))
			if cut.y < p.y: next.append(Vector2(cut.y, p.y))
		pieces = next
	return pieces

## Flat paint tile: `length` along the road direction, `width` across it.
func add_tile(piece: String, at: Vector3, along: Vector3, length: float, width: float) -> void:
	var tile := Basis(Vector3.UP.cross(along) * width, Vector3.UP, along * length)
	add_piece(piece, null, Transform3D(tile, at))

func add_piece(piece: String, profile, placement: Transform3D) -> void:
	var key := piece
	if not _pieces.has(key):
		_pieces[key] = {"mesh": kit_mesh(piece, profile), "transforms": []}
	_pieces[key].transforms.append(placement)

func kit_mesh(piece: String, profile) -> Mesh:
	var scene: PackedScene = load(KIT % piece)
	var root := scene.instantiate()
	var source: MeshInstance3D = root.find_children("*", "MeshInstance3D", true, false)[0]
	var mesh: Mesh = source.mesh.duplicate()
	root.free()
	for i in range(mesh.get_surface_count()):
		var original := mesh.surface_get_material(i)
		mesh.surface_set_material(i, surface(original.resource_name if original else "", profile))
	return mesh

func surface(material_name: String, profile) -> Material:
	var key := material_name
	if material_name == "Asphalt": key += "_%s" % (profile.deck if profile else "pad")
	if _materials.has(key): return _materials[key]
	var result: Material
	match material_name:
		"Asphalt":
			var asphalt := ShaderMaterial.new()
			asphalt.shader = preload("res://world/roads/road_surface.gdshader")
			asphalt.set_shader_parameter("asphalt", load("res://world/city_assets/textures/asphalt_03_Diffuse.jpg"))
			asphalt.set_shader_parameter("asphalt_normal", load("res://world/city_assets/textures/asphalt_03_nor_gl.jpg"))
			asphalt.set_shader_parameter("asphalt_rough", load("res://world/city_assets/textures/asphalt_03_Rough.jpg"))
			asphalt.set_shader_parameter("lane_centre", profile.lane if profile else -1.0)
			asphalt.set_shader_parameter("edge", profile.edge if profile else 100.0)
			result = asphalt
		"GutterConcrete": result = CityMaterials.get_surface("bdc2b8")
		"CurbConcrete": result = CityMaterials.get_surface("d7d6cb")
		_:
			var paint := ShaderMaterial.new()
			paint.shader = preload("res://world/roads/road_paint.gdshader")
			paint.set_shader_parameter("asphalt", load("res://world/city_assets/textures/asphalt_03_Diffuse.jpg"))
			var colours := {"PaintYellow": Color("d9a52a"), "BikeLaneGreen": Color("2a6440"), "PaintWhite": Color("e4e4dc")}
			paint.set_shader_parameter("paint_color", colours.get(material_name, Color("e4e4dc")))
			# Green surfacing is a matte, gritty coating rather than beaded line paint.
			var green := material_name == "BikeLaneGreen"
			paint.set_shader_parameter("wear", 0.22 if green else 0.3)
			paint.set_shader_parameter("specular_amount", 0.3 if green else 0.6)
			result = paint
	_materials[key] = result
	return result

func flush() -> void:
	for key in _pieces:
		var data: Dictionary = _pieces[key]
		var instances := MultiMesh.new()
		instances.transform_format = MultiMesh.TRANSFORM_3D
		instances.mesh = data.mesh
		instances.instance_count = data.transforms.size()
		for i in range(data.transforms.size()):
			instances.set_instance_transform(i, data.transforms[i])
		var node := MultiMeshInstance3D.new()
		node.name = key
		node.multimesh = instances
		# Flat street surfaces only receive shadows.
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
		layout[key] = data.transforms
	_pieces.clear()
