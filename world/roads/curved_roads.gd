class_name CurvedRoads
extends Node3D
## Modular curved roads: any centreline polyline (straight, arc, roundabout ring, Bezier
## frontage road) becomes a full street cross-section:
##   asphalt carriageway (same rain-reactive road shader as the street grid),
##   raised concrete sidewalks on both sides with real vertical kerb faces,
##   markings: dashed yellow centre line on two-way roads, white edge lines on one-way rings.
## Paths that overlap at junctions each sit a few millimetres apart (no z-fighting) and markings
## stop short of path ends so they never paint across a junction.

const ROAD_Y := 0.095
const KERB := 0.11         ## kerb height above the carriageway
const STEP := 0.004        ## height step between overlapping paths

## spec: {"path": PackedVector3Array, "width": carriageway width, "walk": sidewalk width,
##        "ring": bool (closed one-way loop), "centre_line": bool}
var specs: Array[Dictionary] = []
var _asphalt: ShaderMaterial
var _concrete: Material
var _yellow: StandardMaterial3D
var _white: StandardMaterial3D

func _ready() -> void:
	_asphalt = ShaderMaterial.new()
	_asphalt.shader = preload("res://world/roads/road_surface.gdshader")
	_asphalt.set_shader_parameter("asphalt", load("res://world/city_assets/textures/asphalt_03_Diffuse.jpg"))
	_asphalt.set_shader_parameter("asphalt_normal", load("res://world/city_assets/textures/asphalt_03_nor_gl.jpg"))
	_asphalt.set_shader_parameter("asphalt_rough", load("res://world/city_assets/textures/asphalt_03_Rough.jpg"))
	_asphalt.set_shader_parameter("lane_centre", -1.0)   # lateral wear needs straight local X
	_asphalt.set_shader_parameter("edge", 100.0)
	_concrete = CityMaterials.get_surface("c4c2b8")
	_yellow = paint(Color("e3b43a"))
	_white = paint(Color("efede4"))
	for spec in specs: spec.path = densify(spec.path, 1.0)
	for i in range(specs.size()):
		build(specs[i], i)
	street_lights()

static func densify(path: PackedVector3Array, step: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	for i in range(path.size() - 1):
		var a := path[i]
		var b := path[i + 1]
		var n := maxi(1, ceili(a.distance_to(b) / step))
		for k in range(n): out.append(a.lerp(b, float(k) / n))
	out.append(path[-1])
	return out

## True where point p lies on another path's carriageway (a junction): sidewalks and kerbs
## are left open there so the roads actually connect.
func on_other_carriageway(p: Vector3, own: int) -> bool:
	for j in range(specs.size()):
		if j == own: continue
		var path: PackedVector3Array = specs[j].path
		var half: float = float(specs[j].get("width", 8.0)) * 0.5 + 0.25
		for i in range(1, path.size()):
			if Geometry3D.get_closest_point_to_segment(p, path[i - 1], path[i]).distance_to(p) < half: return true
	return false

## Split `path` into runs where the lateral offsets [from, to] stay off other carriageways.
func open_runs(path: PackedVector3Array, offsets: Array, own: int) -> Array:
	var runs: Array = []
	var run := PackedVector3Array()
	for i in range(path.size()):
		var x := across(path, i)
		var blocked := false
		for o: float in offsets:
			if on_other_carriageway(Vector3(path[i].x, 0, path[i].z) + x * o, own): blocked = true
		if blocked:
			if run.size() >= 2: runs.append(run)
			run = PackedVector3Array()
		else:
			run.append(path[i])
	if run.size() >= 2: runs.append(run)
	return runs

static func paint(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.55
	return m

func build(spec: Dictionary, index: int) -> void:
	var path: PackedVector3Array = spec.path
	var half: float = float(spec.get("width", 8.0)) * 0.5
	var walk: float = spec.get("walk", 2.2)
	var y := ROAD_Y + STEP * (index % 6)
	var ring: bool = spec.get("ring", false)
	# Carriageway.
	add_strip(path, -half, half, y, y, _asphalt)
	# Sidewalks with kerb faces on both sides, open wherever another road joins.
	for side: float in [-1.0, 1.0]:
		var inner := half * side
		var outer := (half + walk) * side
		for run: PackedVector3Array in open_runs(path, [inner, (inner + outer) * 0.5, outer], index):
			add_strip(run, minf(inner, outer), maxf(inner, outer), y + KERB, y + KERB, _concrete)
			add_wall(run, inner, y, y + KERB, side)
	# Markings, inset from both ends of open paths.
	var mark_y := y + 0.006
	if spec.get("centre_line", not ring):
		add_dashes(path, 0.0, 0.14, 3.0, 3.0, mark_y, _yellow, 6.0 if not ring else 0.0)
	if ring:
		for side: float in [-1.0, 1.0]:
			for run: PackedVector3Array in open_runs(path, [(half + 0.3) * side], index):
				add_dashes(run, (half - 0.35) * side, 0.14, 1000.0, 0.0, mark_y, _white, 0.0)

## Street lights every LIGHT_SPACING metres on the outer sidewalk, alternating sides on two-way
## roads and on the outside of rings, arm over the carriageway; batched into one MultiMesh per
## mesh piece, with a thin pole collider. Skipped where another road joins.
const LIGHT_SPACING := 30.0
const POLE_BACK := 1.93   ## street_light.glb: pole base sits 1.93 m behind the footprint centre
func street_lights() -> void:
	if not PropKit.has("street_light"): return
	var pieces := PropKit.get_parts("street_light")
	var transforms: Array[Transform3D] = []
	var body := StaticBody3D.new()
	body.name = "StreetLightPoles"
	add_child(body)
	for index in range(specs.size()):
		var spec: Dictionary = specs[index]
		var path: PackedVector3Array = spec.path
		var half: float = float(spec.get("width", 8.0)) * 0.5
		var ring: bool = spec.get("ring", false)
		var next := 6.0
		var travelled := 0.0
		var k := 0
		for i in range(1, path.size()):
			travelled += path[i].distance_to(path[i - 1])
			if travelled < next: continue
			next += LIGHT_SPACING
			var x := across(path, i)
			var side := 1.0 if ring else (1.0 if k % 2 == 0 else -1.0)
			k += 1
			var at := Vector3(path[i].x, 0.0, path[i].z) + x * side * (half + 0.55)
			if on_other_carriageway(at, index) or on_other_carriageway(at + x * side * 1.5, index): continue
			# Front (+Z) must point back over the road: towards -x*side.
			var face := -x * side
			var basis := Basis(Vector3.UP, atan2(face.x, face.z))
			# The arm reaches to the model's +Z; its pole stands POLE_BACK behind the origin, so shift
			# the origin over the road to put the pole itself at `at` on the sidewalk.
			transforms.append(Transform3D(basis, at + face * POLE_BACK + Vector3.UP * (ROAD_Y + KERB)))
			var shape := CollisionShape3D.new()
			var cyl := CylinderShape3D.new()
			cyl.radius = 0.15
			cyl.height = 6.0
			shape.shape = cyl
			shape.position = at + Vector3.UP * 3.0
			body.add_child(shape)
	for piece in pieces:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = piece.mesh
		mm.instance_count = transforms.size()
		for j in range(transforms.size()): mm.set_instance_transform(j, transforms[j] * (piece.transform as Transform3D))
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		node.visibility_range_end = 400.0
		add_child(node)
	set_meta("street_lights", transforms.size())

## Lateral frame at each point (tangent x up), averaged over neighbours for smooth curves.
static func across(path: PackedVector3Array, i: int) -> Vector3:
	var t := (path[mini(i + 1, path.size() - 1)] - path[maxi(0, i - 1)])
	t.y = 0
	return t.normalized().cross(Vector3.UP)

func add_strip(path: PackedVector3Array, from: float, to: float, y0: float, y1: float, material: Material) -> void:
	add_strips([path], from, to, y0, y1, material)

## Several strips with the same cross-section merged into one mesh (one draw call).
func add_strips(paths: Array, from: float, to: float, y0: float, y1: float, material: Material) -> void:
	var v := PackedVector3Array()
	var n := PackedVector3Array()
	var uv := PackedVector2Array()
	var idx := PackedInt32Array()
	for path: PackedVector3Array in paths:
		strip_into(path, from, to, y0, y1, v, n, uv, idx)
	if not v.is_empty(): commit(v, n, uv, idx, material)

func strip_into(path: PackedVector3Array, from: float, to: float, y0: float, y1: float, v: PackedVector3Array, n: PackedVector3Array, uv: PackedVector2Array, idx: PackedInt32Array) -> void:
	var first := v.size()
	var length := 0.0
	for i in range(path.size()):
		var x := across(path, i)
		if i > 0: length += path[i].distance_to(path[i - 1])
		var base := Vector3(path[i].x, 0, path[i].z)
		v.append(base + x * from + Vector3.UP * y0)
		v.append(base + x * to + Vector3.UP * y1)
		n.append(Vector3.UP)
		n.append(Vector3.UP)
		uv.append(Vector2(from, length))
		uv.append(Vector2(to, length))
		if i > 0:
			var k := first + i * 2
			idx.append_array(PackedInt32Array([k - 2, k, k - 1, k - 1, k, k + 1]))

## Vertical kerb face along offset `at`, facing the carriageway.
func add_wall(path: PackedVector3Array, at: float, y0: float, y1: float, side: float) -> void:
	var v := PackedVector3Array()
	var n := PackedVector3Array()
	var uv := PackedVector2Array()
	var idx := PackedInt32Array()
	for i in range(path.size()):
		var x := across(path, i)
		var base := Vector3(path[i].x, 0, path[i].z) + x * at
		v.append(base + Vector3.UP * y0)
		v.append(base + Vector3.UP * y1)
		n.append(-x * side)
		n.append(-x * side)
		uv.append(Vector2(0, i))
		uv.append(Vector2(1, i))
		if i > 0:
			var k := i * 2
			if side > 0: idx.append_array(PackedInt32Array([k - 2, k - 1, k, k - 1, k + 1, k]))
			else: idx.append_array(PackedInt32Array([k - 2, k, k - 1, k - 1, k, k + 1]))
	commit(v, n, uv, idx, _concrete)

## Dashed (or solid when gap = 0) painted line at lateral offset `at`.
func add_dashes(path: PackedVector3Array, at: float, width: float, dash: float, gap: float, y: float, material: Material, inset: float) -> void:
	# Resample the path by distance so dashes have even length.
	var total := 0.0
	var acc := PackedFloat32Array([0.0])
	for i in range(1, path.size()):
		total += path[i].distance_to(path[i - 1])
		acc.append(total)
	var pieces: Array = []
	var s := inset
	while s < total - inset:
		var e := minf(s + dash, total - inset)
		var piece := PackedVector3Array()
		var t := s
		while t < e:
			piece.append(sample(path, acc, t))
			t += 1.0
		piece.append(sample(path, acc, e))
		if piece.size() >= 2: pieces.append(piece)
		s = e + gap if gap > 0.0 else total
	add_strips(pieces, at - width * 0.5, at + width * 0.5, y, y, material)

static func sample(path: PackedVector3Array, acc: PackedFloat32Array, s: float) -> Vector3:
	for i in range(1, acc.size()):
		if acc[i] >= s:
			var f := (s - acc[i - 1]) / maxf(acc[i] - acc[i - 1], 0.0001)
			return path[i - 1].lerp(path[i], f)
	return path[-1]

func commit(v: PackedVector3Array, n: PackedVector3Array, uv: PackedVector2Array, idx: PackedInt32Array, material: Material) -> void:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = v
	arrays[Mesh.ARRAY_NORMAL] = n
	arrays[Mesh.ARRAY_TEX_UV] = uv
	arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.visibility_range_end = 450.0
	add_child(node)
