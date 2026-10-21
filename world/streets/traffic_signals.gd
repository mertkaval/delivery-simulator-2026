class_name TrafficSignals
extends Node3D
## Traffic and pedestrian signals at every SignalPlan junction, built from the Blender street
## tech kit (world/streets/build_street_tech.py):
##   * a galvanised mast-arm pole on the far-right corner of every approach, its arm reaching
##     over the approach lane with a three-section head (yellow-bordered backplate) and a second
##     head side-mounted on the pole at driver height,
##   * pedestrian heads (hand / walking figure) and push buttons on the corner poles, facing
##     across each crosswalk; corners without a mast get a plain post,
##   * mid-block crossings get a mast pole beside each landing.
## Poles go through PropPlacer (sidewalk, off every carriageway) and must clear every AI route
## by the vehicle half width (long-vehicle and bus routes by more), sliding along the sidewalk
## if a spot is taken.
## Rendering is batched per junction: one MultiMesh per kit piece, one for all lenses and
## symbols (shared shader, lit state in the instance custom data) and one for the glow sprites.
## A junction's instance data only changes when its aspect code changes (a few times a cycle).

const KIT := "res://world/streets/%s.glb"
const MASTS := [[4.6, "signal_mast_5"], [6.6, "signal_mast_7"], [8.6, "signal_mast_9"]]
const ARM_Y := 5.75
const SIDE_HEAD_Y := 4.4
const LENS_Y := [-0.28, -0.68, -1.08]
const LENS_Z := 0.122
const HUES := [Color(1.0, 0.1, 0.05), Color(1.0, 0.5, 0.0), Color(0.15, 1.0, 0.62)]
const HAND := Color(1.0, 0.42, 0.08)
const WALK := Color(0.92, 0.96, 1.0)
const RANGE := 260.0
const LAMP_RANGE := 420.0

## Runtime per junction: {"def", "code", "lens": MultiMesh, "glow": MultiMesh, "lens_axis":
## PackedInt32Array, "lens_k", "sym": MultiMesh, "sym_axis", "sym_hand", "masts", "heads", "peds"}.
var runtime: Array[Dictionary] = []
var traffic: Node
var population: Node
var _fleet: Node
var placer: PropPlacer
var dropped: Array[String] = []
var _meshes: Dictionary = {}
var _route_grid: Dictionary = {}
var _audio_done := false
var _lamp_material: ShaderMaterial
var _symbol_material: ShaderMaterial
var _glow_material: ShaderMaterial
var _night := 0.0

func _ready() -> void:
	var world := get_parent()
	traffic = world.get_node_or_null("CityTraffic")
	var downtown: Variant = world.get("downtown")
	if downtown != null: population = (downtown as Node).get("population")
	var p: Variant = world.get("placer")
	placer = p if p is PropPlacer else PropPlacer.new()
	_lamp_material = ShaderMaterial.new()
	_lamp_material.shader = preload("res://world/streets/signal_lamp.gdshader")
	_symbol_material = ShaderMaterial.new()
	_symbol_material.shader = preload("res://world/streets/signal_lamp.gdshader")
	_symbol_material.set_shader_parameter("radius", 0.0)
	_symbol_material.set_shader_parameter("pitch", 0.011)
	_symbol_material.set_shader_parameter("energy", 4.0)
	_glow_material = ShaderMaterial.new()
	_glow_material.shader = preload("res://world/streets/signal_glow.gdshader")
	index_routes(world)
	var list := SignalPlan.junctions()
	for ji in range(list.size()):
		build_junction(ji, list[ji])
	_process(0.0)

## Time on the clock a junction runs on.
func clock(def: Dictionary) -> float:
	if String(def.clock) == "downtown":
		if _fleet == null and population != null: _fleet = population.get_node_or_null("CivicFleet")
		return float(_fleet.get("signal_clock")) if _fleet != null else 0.0
	return float(traffic.get("elapsed")) if traffic != null else 0.0

func set_time(_hour: float, daylight: float) -> void:
	_night = 1.0 - daylight
	_glow_material.set_shader_parameter("strength", lerpf(0.35, 2.2, _night))

# ----------------------------------------------------------------------------- routes

## Every AI path (with the clearance a vehicle on it needs) in a 4 m grid.
func index_routes(world: Node) -> void:
	var paths: Array = []
	if traffic != null:
		for r: SmoothRoute in traffic.get("loops"): paths.append([r.points, 1.7])
		for r: SmoothRoute in traffic.get("long_loops"): paths.append([r.points, 2.4])
	if population != null:
		var fleet := population.get_node_or_null("CivicFleet")
		if fleet != null:
			for r: SmoothRoute in fleet.get("loops"): paths.append([r.points, 1.7])
			for car: Dictionary in fleet.get("fleet"): paths.append([(car.route as SmoothRoute).points, 2.4])
	var buses: Variant = world.get("buses")
	if buses != null:
		for line: Dictionary in (buses as Node).get("lines"): paths.append([line.path, 2.2])
	for entry: Array in paths:
		var pts: PackedVector3Array = entry[0]
		for q in pts:
			var cell := Vector2i(floori(q.x / 4.0), floori(q.z / 4.0))
			if not _route_grid.has(cell): _route_grid[cell] = PackedVector3Array()
			var arr: PackedVector3Array = _route_grid[cell]
			arr.append(Vector3(q.x, q.z, float(entry[1])))
			_route_grid[cell] = arr

func route_clear(q: Vector3, radius: float) -> bool:
	var c := Vector2i(floori(q.x / 4.0), floori(q.z / 4.0))
	for gx in range(c.x - 1, c.x + 2):
		for gz in range(c.y - 1, c.y + 2):
			for e: Vector3 in _route_grid.get(Vector2i(gx, gz), PackedVector3Array()):
				if Vector2(e.x - q.x, e.y - q.z).length() < e.z + radius: return false
	return true

## A valid pole spot near `base`, sliding along `slide` (unit) and then out along `out`.
func pole_spot(kind: String, base: Vector3, slide: Vector3, out: Vector3, radius: float) -> Variant:
	for m: float in [0.0, 0.4, 0.8, 1.2]:
		for k in range(0, 15):
			var q := base + slide * (k * 0.5) + out * m
			if not route_clear(q, radius): continue
			if placer.problem(kind, q, radius, {"junction": 0.0, "walk": 0.6, "gap": 0.3}) != "": continue
			placer.record(kind, q, radius, "traffic_signals")
			return q
	return null

# ----------------------------------------------------------------------------- building

func piece(name: String) -> Mesh:
	if _meshes.has(name): return _meshes[name]
	var root: Node = (load(KIT % name) as PackedScene).instantiate()
	var mesh: Mesh = (root.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D).mesh
	root.free()
	_meshes[name] = mesh
	return mesh

## Lane-centre offset for vehicles approaching along `axis` at junction j.
static func lane_of(def: Dictionary, axis: String) -> float:
	if String(def.district) == "downtown": return 1.7 if axis == "ns" else 3.0
	var half: float = def.hx if axis == "ns" else def.hz
	return 1.95 if half >= 6.0 else 1.64

func build_junction(ji: int, def: Dictionary) -> void:
	var c := Vector3(def.centre.x, 0.0, def.centre.y)
	var parts: Dictionary = {}   # piece -> Array[Transform3D]
	var lens_x: Array[Transform3D] = []
	var lens_axis := PackedInt32Array()
	var lens_k := PackedInt32Array()
	var sym_x: Array[Transform3D] = []
	var sym_axis := PackedInt32Array()
	var sym_hand := PackedInt32Array()
	var body := StaticBody3D.new()
	body.name = "SignalPoles_%s" % def.id
	add_child(body)
	var rt := {"def": def, "code": -1, "masts": 0, "heads": [], "peds": [], "poles": []}
	var add := func(name: String, t: Transform3D) -> void:
		if not parts.has(name): parts[name] = []
		(parts[name] as Array).append(t)
	var arms: Dictionary = def.arms
	# Approaches: travel direction into the junction from each arm.
	var approaches: Array[Vector3] = []
	if def.kind == "midblock": approaches = [Vector3(0, 0, -1), Vector3(0, 0, 1)]
	else:
		if arms.n: approaches.append(Vector3(0, 0, -1))
		if arms.s: approaches.append(Vector3(0, 0, 1))
		if arms.e: approaches.append(Vector3(-1, 0, 0))
		if arms.w: approaches.append(Vector3(1, 0, 0))
	var corner_poles: Dictionary = {}   # Vector2i(sx, sz) -> pole position
	var side_facing: Dictionary = {}    # Vector2i(sx, sz) -> facing of the pole's side head
	for d in approaches:
		var axis := "ns" if absf(d.z) > 0.5 else "ew"
		var r := d.cross(Vector3.UP)
		var along: float = def.hz if axis == "ns" else def.hx
		var lateral: float = def.hx if axis == "ns" else def.hz
		# Far-right corner, just beyond the crosswalk (walkers keep a clear landing) and close
		# to the kerb (clear of the walking line).
		var cw: float = def.cw_ns if axis == "ns" else def.cw_ew
		var base := c + d * (cw + 2.15) + r * (lateral + 0.6)
		if def.kind == "midblock": base = c + d * 3.9 + r * (lateral + 0.6)
		var q: Variant = pole_spot("traffic_signal", base, d, r, 0.2)
		if q == null:
			dropped.append("%s mast %s" % [def.id, axis])
			continue
		var pole: Vector3 = q
		var lat := (pole - c).dot(r)
		var reach := lat - lane_of(def, axis)
		var mast: Array = MASTS[-1]
		for m: Array in MASTS:
			if float(m[0]) >= reach + 0.3:
				mast = m
				break
		reach = minf(reach, float(mast[0]) - 0.3)
		add.call(mast[1], Transform3D(Basis(-r, Vector3.UP, d), pole))
		collider(body, pole, 0.13, 6.4)
		rt.masts = int(rt.masts) + 1
		rt.poles.append(pole)
		# Overhead head over the lane, facing the oncoming drivers (head +Z = -d).
		var face := Basis(Vector3.UP.cross(-d), Vector3.UP, -d)
		var heads: Array[Transform3D] = [Transform3D(face, pole - r * reach + Vector3.UP * (ARM_Y + 0.012 * reach - 0.07)),
			Transform3D(face, pole - d * 0.27 + Vector3.UP * SIDE_HEAD_Y)]
		for h in heads:
			add.call("signal_head", h)
			rt.heads.append({"at": h.origin, "axis": axis, "facing": -d})
			for k in range(3):
				lens_x.append(h * Transform3D(Basis.IDENTITY, Vector3(0, LENS_Y[k], LENS_Z)))
				lens_axis.append(0 if axis == "ns" else 1)
				lens_k.append(k)
		var sx := int(signf((pole - c).x))
		var sz := int(signf((pole - c).z))
		corner_poles[Vector2i(sx, sz)] = pole
		side_facing[Vector2i(sx, sz)] = -d
		if def.kind == "midblock":
			# Pedestrian head on the same pole, facing across the avenue (walkers along x).
			ped(rt, add, sym_x, sym_axis, sym_hand, pole, Vector3(-signf((pole - c).x), 0, 0), 2.95, "ew")
	if def.kind != "midblock":
		# Crosswalks on every arm; heads on the corner poles facing across.
		for corner: Vector2i in [Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]:
			var has_x: bool = arms.n if corner.y > 0 else arms.s    # crosswalk across the ns road on that arm
			var has_z: bool = arms.e if corner.x > 0 else arms.w    # crosswalk across the ew road
			if not has_x and not has_z: continue
			var pole: Variant = corner_poles.get(corner)
			if pole == null:
				var base := c + Vector3(corner.x * (float(def.hx) + 0.6), 0, corner.y * (float(def.cw_ns) + 2.15))
				pole = pole_spot("signal_post", base, Vector3(0, 0, corner.y), Vector3(corner.x, 0, 0), 0.12)
				if pole == null:
					dropped.append("%s post %s" % [def.id, corner])
					continue
				add.call("signal_post", Transform3D(Basis.IDENTITY, pole))
				collider(body, pole, 0.09, 3.6)
				rt.poles.append(pole)
			# Two heads per pole: the one facing the same way as the pole's side-mounted vehicle
			# head (or, on a post, the second one) hangs lower so the housings never touch.
			var side: Vector3 = side_facing.get(corner, Vector3.ZERO)
			var fx := Vector3(-corner.x, 0, 0)
			var fz := Vector3(0, 0, -corner.y)
			var low_x := side.dot(fx) > 0.9
			if has_x: ped(rt, add, sym_x, sym_axis, sym_hand, pole, fx, 2.4 if low_x else 2.95, "ew")
			if has_z: ped(rt, add, sym_x, sym_axis, sym_hand, pole, fz, 2.95 if low_x else 2.4, "ns")
	# Batches.
	for name: String in parts:
		var mmi := batch(piece(name), parts[name], c, null, RANGE)
		mmi.name = "%s_%s" % [name, def.id]
		mmi.set_meta("prop", name)
	if not lens_x.is_empty():
		var lens := batch(piece("signal_lens"), lens_x, c, _lamp_material, LAMP_RANGE, true)
		lens.name = "Lamps_%s" % def.id
		var quad := QuadMesh.new()
		quad.size = Vector2.ONE
		var glow_x: Array[Transform3D] = []
		for t in lens_x: glow_x.append(Transform3D(t.basis.scaled(Vector3.ONE * 1.25), t.origin + t.basis.z * 0.05))
		var glow := batch(quad, glow_x, c, _glow_material, LAMP_RANGE, true)
		glow.name = "Glow_%s" % def.id
		glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in range(lens_x.size()):
			lens.multimesh.set_instance_color(i, HUES[lens_k[i]])
			glow.multimesh.set_instance_color(i, HUES[lens_k[i]])
		rt.lens = lens.multimesh
		rt.glow = glow.multimesh
		rt.lens_axis = lens_axis
		rt.lens_k = lens_k
	if not sym_x.is_empty():
		# Hand and walking figure are two meshes: two MultiMeshes sharing the instance order.
		var hands: Array[Transform3D] = []
		var walks: Array[Transform3D] = []
		var hand_axis := PackedInt32Array()
		var walk_axis := PackedInt32Array()
		for i in range(sym_x.size()):
			if sym_hand[i] == 1:
				hands.append(sym_x[i])
				hand_axis.append(sym_axis[i])
			else:
				walks.append(sym_x[i])
				walk_axis.append(sym_axis[i])
		var hm := batch(piece("ped_hand"), hands, c, _symbol_material, RANGE, true)
		hm.name = "PedHand_%s" % def.id
		var wm := batch(piece("ped_walk"), walks, c, _symbol_material, RANGE, true)
		wm.name = "PedWalk_%s" % def.id
		for i in range(hands.size()): hm.multimesh.set_instance_color(i, HAND)
		for i in range(walks.size()): wm.multimesh.set_instance_color(i, WALK)
		rt.hand = hm.multimesh
		rt.walk = wm.multimesh
		rt.hand_axis = hand_axis
		rt.walk_axis = walk_axis
	runtime.append(rt)

## Pedestrian head (+ push button) on a pole, facing `facing` (unit, horizontal), top at `top`.
func ped(rt: Dictionary, add: Callable, sym_x: Array[Transform3D], sym_axis: PackedInt32Array, sym_hand: PackedInt32Array,
		pole: Vector3, facing: Vector3, top: float, walk_axis: String) -> void:
	var basis := Basis(Vector3.UP.cross(facing), Vector3.UP, facing)
	var t := Transform3D(basis, pole + facing * 0.12 + Vector3.UP * top)
	add.call("ped_head", t)
	add.call("ped_button", Transform3D(basis, pole + facing * 0.125 + Vector3.UP * (1.05 if top > 2.5 else 1.25)))
	var axis_i := 0 if walk_axis == "ns" else 1
	sym_x.append(t * Transform3D(Basis.IDENTITY, Vector3(0, -0.21, 0.249)))
	sym_axis.append(axis_i)
	sym_hand.append(1)
	sym_x.append(t * Transform3D(Basis.IDENTITY, Vector3(0, -0.55, 0.249)))
	sym_axis.append(axis_i)
	sym_hand.append(0)
	var marker := Node3D.new()
	marker.name = "PedSignal_%s_%d" % [rt.def.id, (rt.peds as Array).size()]
	marker.position = t.origin + Vector3.DOWN * 0.4
	add_child(marker)
	rt.peds.append({"node": marker, "axis": walk_axis, "facing": facing})

func collider(body: StaticBody3D, at: Vector3, radius: float, height: float) -> void:
	var shape := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = radius
	cyl.height = height
	shape.shape = cyl
	shape.position = at + Vector3.UP * height * 0.5
	body.add_child(shape)

func batch(mesh: Mesh, xforms: Array, origin: Vector3, material: Material, range_end: float, data := false) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	if data:
		mm.use_colors = true
		mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = xforms.size()
	for i in range(xforms.size()):
		var t: Transform3D = xforms[i]
		t.origin -= origin
		mm.set_instance_transform(i, t)
	var node := MultiMeshInstance3D.new()
	node.multimesh = mm
	node.position = origin
	if material != null: node.material_override = material
	node.visibility_range_end = range_end
	node.visibility_range_end_margin = 20.0
	add_child(node)
	return node

# ----------------------------------------------------------------------------- switching

## Aspect code of a junction at time t (changes only when a lamp changes).
static func code_of(def: Dictionary, t: float) -> int:
	var ns := SignalPlan.state(def, "ns", t)
	var ew := SignalPlan.state(def, "ew", t)
	var pn := SignalPlan.ped_state(def, "ns", t)
	var pe := SignalPlan.ped_state(def, "ew", t)
	var blink := int(floorf(t * 2.0)) % 2
	return ns + 3 * ew + 9 * pn + 27 * pe + 81 * blink

func _process(_delta: float) -> void:
	for rt in runtime:
		var def: Dictionary = rt.def
		var t := clock(def)
		var code := code_of(def, t)
		if code == int(rt.code): continue
		rt.code = code
		var aspects := [SignalPlan.state(def, "ns", t), SignalPlan.state(def, "ew", t)]
		var peds := [SignalPlan.ped_state(def, "ns", t), SignalPlan.ped_state(def, "ew", t)]
		var blink := int(floorf(t * 2.0)) % 2 == 0
		if rt.has("lens"):
			var lens: MultiMesh = rt.lens
			var glow: MultiMesh = rt.glow
			var axes: PackedInt32Array = rt.lens_axis
			var ks: PackedInt32Array = rt.lens_k
			for i in range(axes.size()):
				var a: int = aspects[axes[i]]
				var k: int = ks[i]
				var lit := 1.0 if (a == SignalPlan.RED and k == 0) or (a == SignalPlan.AMBER and k == 1) or (a == SignalPlan.GREEN and k == 2) else 0.0
				lens.set_instance_custom_data(i, Color(lit, 0, 0, 0))
				glow.set_instance_custom_data(i, Color(lit, 0, 0, 0))
		if rt.has("hand"):
			var hand: MultiMesh = rt.hand
			var walk: MultiMesh = rt.walk
			var ha: PackedInt32Array = rt.hand_axis
			var wa: PackedInt32Array = rt.walk_axis
			for i in range(ha.size()):
				var s: int = peds[ha[i]]
				hand.set_instance_custom_data(i, Color(1.0 if s == SignalPlan.DONT_WALK or (s == SignalPlan.FLASH and blink) else 0.0, 0, 0, 0))
			for i in range(wa.size()):
				walk.set_instance_custom_data(i, Color(1.0 if peds[wa[i]] == SignalPlan.WALK else 0.0, 0, 0, 0))
	if not _audio_done: register_audio()

## Walk-signal sound (CityAudio) for every pedestrian head; replaces CityAudio's fallbacks.
func register_audio() -> void:
	var audio := get_tree().get_first_node_in_group("city_audio")
	if audio == null or not audio.has_method("attach_signal_loop"): return
	_audio_done = true
	for rt in runtime:
		var def: Dictionary = rt.def
		for p: Dictionary in rt.peds:
			var axis: String = p.axis
			audio.call("attach_signal_loop", p.node, func() -> bool: return SignalPlan.ped_state(def, axis, clock(def)) == SignalPlan.WALK)
