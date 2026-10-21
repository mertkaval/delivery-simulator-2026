class_name CityMonuments
extends Node3D
## Parks, monuments and sports (assets/monuments, built by tools/prepare_monuments.py):
##   * Atatürk Square (downtown plaza): the standing bronze Atatürk on a stepped granite plinth,
##     with the putti fountain behind it.
##   * Halime Çavuş Park (the east roundabout island, x 64 z -145): the equestrian Atatürk on its
##     granite pedestal in a paved round plaza where the park paths meet.
##   * the other seven parks: the putti fountain (NE lawn, the strollers' loop and CityAudio's
##     water loop) with animated water, and the Atatürk bust memorial wall (NW lawn, facing the
##     east-west path). Four of them also have a figure sculpture closing a path axis.
##   * Meridian General Hospital forecourt: the Edward Jenner statue (vaccination pioneer).
##   * Meridian Community School yard: two fenced street basketball courts.
## Each asset gets the simple collision boxes / cylinders listed in assets/monuments/monuments.json,
## a visibility range, and casts shadows only while the camera is near. Every placement is
## recorded (and its footprint reserved) in the city's PropPlacer so later props keep clear.

const CATALOG := "res://assets/monuments/monuments.json"
## Benchmark switch: DS_NO_MONUMENTS=1 builds the city without any of these assets.
static var enabled := OS.get_environment("DS_NO_MONUMENTS") != "1"
static var _catalog: Dictionary = {}
static var _scenes: Dictionary = {}
static var _water: ShaderMaterial
static var _paving: Dictionary = {}

## Park centre (x, z) of the equestrian monument park (no fountain, no bust there).
const EQUESTRIAN_PARK := Vector2(64, -145)
## Parks with a figure sculpture.
const SCULPTURES := {
	Vector2(-64, -145): "sculpture_open_arms",
	Vector2(-44, -330): "sculpture_stretch",
	Vector2(44, -470): "sculpture_open_arms",
	Vector2(44, -590): "sculpture_stretch",
}
## Park-local spots (CedarNeighborhood.build_park layout: oval promenade 9 x 14 m, cross paths
## 2.6 m wide, pergola SW, benches +4,+4 / -4.5,+6 / -3,-10, planters -5,-7 / +5,+8).
const FOUNTAIN_OFFSET := Vector3(4, 0, -5)
const MEMORIAL_OFFSET := Vector3(-4.8, 0, -3.6)   ## NW lawn, front to the east-west path
const PLAZA_RADIUS := 4.5
const STROLL_RADIUS := 3.9
const SQUARE_FOUNTAIN := Vector3(0, 0, -15)        ## plaza frame (behind the monument)
const SQUARE_MONUMENT := Vector3(0, 0, -6.5)
const JENNER_AT := Vector3(545, 0.08, -342)        ## hospital forecourt, south of the entrance walk
const JENNER_YAW := -PI / 2                        ## faces the civic road (west)
const COURTS := [Vector3(597.5, 0.06, -614.5), Vector3(614.5, 0.06, -614.5)]
const COURT_YAW := PI                              ## gates face the school (south)

var placer: PropPlacer
## Placed assets: {"id", "kind", "at": Vector3, "yaw": float, "park": Vector2 (or null)}
var items: Array[Dictionary] = []
var memorials: Dictionary = {}                     ## park centre (Vector2) -> memorial position
var water: Array[MeshInstance3D] = []
var _shadows: Array[Dictionary] = []               ## {"meshes": Array, "at": Vector3, "near": float, "on": bool}
var _shadow_clock := 0.0

# ----------------------------------------------------------------------------- catalogue / layout

static func catalog() -> Dictionary:
	if _catalog.is_empty() and FileAccess.file_exists(CATALOG):
		var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
		if data is Dictionary: _catalog = (data as Dictionary).get("assets", {})
	return _catalog

static func info(id: String) -> Dictionary:
	return catalog().get(id, {})

static func scene(id: String) -> PackedScene:
	if not _scenes.has(id): _scenes[id] = load(String(info(id).get("path", "res://assets/monuments/%s.glb" % id)))
	return _scenes[id]

## The downtown plaza parcel (DowntownCatalog program "plaza"): its frame (front edge, +z out).
static func square_plaza() -> Transform3D:
	for block_id in range(9):
		for b in DowntownCatalog.buildings(block_id):
			if b.program == "plaza": return Transform3D(Basis(Vector3.UP, float(b.yaw)), b.root as Vector3)
	return Transform3D.IDENTITY

static func park_centres() -> Array[Vector2]:
	var list: Array[Vector2] = []
	for c in StreetNames.PARKS: list.append(c as Vector2)
	return list

## Every fountain basin centre (ground level): the parks' plus Atatürk Square's (CityVFX jets,
## CityAudio water loops).
static func fountain_spots() -> Array[Vector3]:
	var list: Array[Vector3] = []
	for c in park_centres():
		if c == EQUESTRIAN_PARK: continue
		list.append(Vector3(c.x, 0, c.y) + FOUNTAIN_OFFSET)
	list.append(square_plaza() * SQUARE_FOUNTAIN)
	return list

## Strollers' loop (park-local points) for parks laid out round a monument, or [] for the usual
## loop round the fountain (CityLife.PARK_LOOP).
static func stroll_loop(park: Vector3) -> Array[Vector3]:
	var loop: Array[Vector3] = []
	if Vector2(park.x, park.z) != EQUESTRIAN_PARK: return loop
	for i in range(12):
		var a := TAU * i / 12.0 + 0.2
		loop.append(Vector3(cos(a), 0, sin(a)) * STROLL_RADIUS)
	return loop

## Where a park's sculpture stands: ring parks close the outer end of the east-west path (facing
## the centre); the square parks (hemmed in by the side-road sidewalk, backyards and the mural
## walls) have it in the NW lawn pocket behind the memorial, facing the north-south path.
static func sculpture_transform(c: Vector2) -> Transform3D:
	var centre := Vector3(c.x, 0, c.y)
	if absf(c.y + 145.0) < 1.0:
		var side := signf(c.x)
		return Transform3D(Basis(Vector3.UP, -side * PI / 2), centre + Vector3(side * 11.3, 0, 0))
	return Transform3D(Basis(Vector3.UP, PI / 2), centre + Vector3(-2.9, 0, -7.0))

# ----------------------------------------------------------------------------- building

func _ready() -> void:
	if not enabled: return
	# Civic campus pieces live in world coordinates (CivicCampus keeps its layout around them).
	var jenner := Transform3D(Basis(Vector3.UP, JENNER_YAW), JENNER_AT)
	put("statue_jenner", jenner, 260.0, 110.0)
	reserve_box(jenner, info("statue_jenner"), 0.6, "monument")
	record("statue", JENNER_AT, 2.4)
	for at: Vector3 in COURTS:
		var t := Transform3D(Basis(Vector3.UP, COURT_YAW), at)
		put("basketball_court", t, 220.0, 55.0)
		reserve_box(t, info("basketball_court"), 0.8, "court")
		record("court", at, 2.0)

## One park's features (called from CedarNeighborhood.build_park for each of the eight parks).
func park(at: Vector3) -> void:
	if not enabled: return
	var c := Vector2(at.x, at.z)
	if c == EQUESTRIAN_PARK:
		plaza(at)
		# The rider faces +z: down the side road towards Nezahat Onbaşı Street and the home side.
		var t := Transform3D(Basis.IDENTITY, at + Vector3(0, 0.05, 0))
		put("ataturk_equestrian", t, 320.0, 120.0, c)
		record("monument", at, PLAZA_RADIUS)
		reserve_disc(at, PLAZA_RADIUS, "monument")
		memorials[c] = at
		return
	fountain(Transform3D(Basis.IDENTITY, at + FOUNTAIN_OFFSET), c)
	var m := Transform3D(Basis.IDENTITY, at + MEMORIAL_OFFSET)
	put("ataturk_bust", m, 130.0, 60.0, c)
	reserve_box(m, info("ataturk_bust"), 0.4, "monument")
	record("memorial", m.origin, 1.9)
	memorials[c] = m.origin
	if SCULPTURES.has(c):
		var s := sculpture_transform(c)
		put(String(SCULPTURES[c]), s, 130.0, 55.0, c)
		reserve_disc(s.origin, 0.9, "monument")
		record("sculpture", s.origin, 0.85)

## Atatürk Square: the monument in the plaza frame and the fountain behind it. Returns the
## monument transform (StreetSignage keeps it for navigation / tests).
func square(plaza_frame: Transform3D) -> Transform3D:
	var t := plaza_frame * Transform3D(Basis.IDENTITY, SQUARE_MONUMENT)
	if not enabled: return t
	put("ataturk_monument", t, 480.0, 140.0)
	reserve_box(t, info("ataturk_monument"), 0.5, "monument")
	record("monument", t.origin, 3.6)
	var lines := [["ATATÜRK SQUARE", 44, 2.62], ["MUSTAFA KEMAL ATATÜRK · 1881–1938", 20, 2.32], ["“Peace at home, peace in the world.”", 18, 2.1]]
	var front: float = float(info("ataturk_monument").get("panel_front_z", 1.32)) + 0.006
	for line: Array in lines:
		var label := Label3D.new()
		label.text = String(line[0])
		label.font_size = int(line[1])
		label.pixel_size = minf(0.004, 1.5 / (String(line[0]).length() * float(line[1]) * 0.6))
		label.outline_size = 0
		label.modulate = Color("f0dca0")
		label.transform = t * Transform3D(Basis.IDENTITY, Vector3(0, float(line[2]), front))
		label.double_sided = false
		label.visibility_range_end = 50.0
		add_child(label)
	fountain(plaza_frame * Transform3D(Basis.IDENTITY, SQUARE_FOUNTAIN), Vector2.INF)
	return t

func fountain(t: Transform3D, park_centre: Vector2) -> void:
	var node := put("fountain_putti", t, 170.0, 60.0, park_centre)
	record("fountain", t.origin, 1.75)
	reserve_disc(t.origin, 1.8, "monument")
	var data := info("fountain_putti")
	var disk := CylinderMesh.new()
	var r: float = float(data.get("water_radius", 1.5))
	disk.top_radius = r
	disk.bottom_radius = r
	disk.height = 0.02
	disk.radial_segments = 40
	disk.rings = 1
	var surface := MeshInstance3D.new()
	surface.name = "Water"
	surface.mesh = disk
	surface.material_override = water_material()
	surface.position.y = float(data.get("water_y", 0.17)) - 0.01
	surface.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	surface.visibility_range_end = 120.0
	node.add_child(surface)
	water.append(surface)

## Paved round plaza where the park paths meet (equestrian park): granite setts and a darker
## kerb band, flush with the gravel paths.
func plaza(at: Vector3) -> void:
	for ring: Array in [[PLAZA_RADIUS + 0.25, 0.028, Color("7d7a74")], [PLAZA_RADIUS, 0.04, Color("b9b5ad")]]:
		var disk := CylinderMesh.new()
		disk.top_radius = float(ring[0])
		disk.bottom_radius = float(ring[0])
		disk.height = 0.02
		disk.radial_segments = 64
		disk.rings = 1
		var mesh := MeshInstance3D.new()
		mesh.mesh = disk
		mesh.material_override = paving_material(ring[2] as Color)
		mesh.position = at + Vector3(0, float(ring[1]), 0)
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mesh.visibility_range_end = 200.0
		add_child(mesh)

## Instance an asset with its collision; `near` = distance within which it casts shadows.
func put(id: String, t: Transform3D, range_end: float, near: float, park_centre: Variant = null) -> Node3D:
	var node: Node3D = scene(id).instantiate()
	node.name = id.to_pascal_case()
	node.transform = t
	add_child(node)
	var meshes: Array[GeometryInstance3D] = []
	for g in node.find_children("*", "GeometryInstance3D", true, false):
		var gi := g as GeometryInstance3D
		var fine := str(gi.name).begins_with("CourtNets")
		gi.visibility_range_end = 70.0 if fine else range_end
		gi.visibility_range_end_margin = 10.0
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if not fine: meshes.append(gi)
	_shadows.append({"meshes": meshes, "at": t.origin, "near": near, "on": false})
	var shapes: Array = info(id).get("collision", [])
	if not shapes.is_empty():
		var body := StaticBody3D.new()
		body.name = "Collision"
		node.add_child(body)
		for s: Dictionary in shapes:
			var cs := CollisionShape3D.new()
			var c: Array = s.center
			cs.position = Vector3(float(c[0]), float(c[1]), float(c[2]))
			if s.type == "cylinder":
				var cyl := CylinderShape3D.new()
				cyl.radius = float(s.radius)
				cyl.height = float(s.height)
				cs.shape = cyl
			else:
				var box := BoxShape3D.new()
				var z: Array = s.size
				box.size = Vector3(float(z[0]), float(z[1]), float(z[2]))
				cs.shape = box
			cs.set_meta("prop", id)
			body.add_child(cs)
	items.append({"id": id, "kind": String(info(id).get("kind", "")), "at": t.origin, "yaw": t.basis.get_euler().y, "park": park_centre})
	return node

func record(kind: String, at: Vector3, radius: float) -> void:
	if placer != null: placer.record(kind, Vector3(at.x, 0, at.z), radius, "monuments")

func reserve_disc(at: Vector3, radius: float, tag: String) -> void:
	if placer != null: placer.reserve(Rect2(at.x - radius, at.z - radius, radius * 2, radius * 2), tag)

## Keep-clear rectangle (axis-aligned bound of the rotated footprint, plus a margin).
func reserve_box(t: Transform3D, data: Dictionary, margin: float, tag: String) -> void:
	if placer == null or data.is_empty(): return
	var s: Array = data.size
	var h := Vector3(float(s[0]), 0, float(s[2])) * 0.5
	var rect := Rect2(Vector2(t.origin.x, t.origin.z), Vector2.ZERO)
	for corner in [Vector3(h.x, 0, h.z), Vector3(-h.x, 0, h.z), Vector3(h.x, 0, -h.z), Vector3(-h.x, 0, -h.z)]:
		var p := t * (corner as Vector3)
		rect = rect.expand(Vector2(p.x, p.z))
	placer.reserve(rect.grow(margin), tag)

static func water_material() -> ShaderMaterial:
	if _water == null:
		_water = ShaderMaterial.new()
		_water.shader = preload("res://world/monuments/fountain_water.gdshader")
		var noise := FastNoiseLite.new()
		noise.seed = 4117
		noise.frequency = 0.05
		noise.fractal_octaves = 3
		var tex := NoiseTexture2D.new()
		tex.width = 256
		tex.height = 256
		tex.seamless = true
		tex.as_normal_map = true
		tex.bump_strength = 6.0
		tex.noise = noise
		_water.set_shader_parameter("ripple", tex)
	return _water

static func paving_material(tint: Color) -> StandardMaterial3D:
	var key := tint.to_html()
	if _paving.has(key): return _paving[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = tint
	if ResourceLoader.exists("res://assets/monuments/ataturk_equestrian_granite.jpg"):
		m.albedo_texture = load("res://assets/monuments/ataturk_equestrian_granite.jpg")
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE * 0.7
	m.roughness = 0.75
	_paving[key] = m
	return m

# ----------------------------------------------------------------------------- runtime

## Shadows only near the camera (checked twice a second; ~40 entries).
func _process(delta: float) -> void:
	_shadow_clock -= delta
	if _shadow_clock > 0.0: return
	_shadow_clock = 0.5
	var camera := get_viewport().get_camera_3d() if get_viewport() != null else null
	if camera == null: return
	var eye := camera.global_position
	for e in _shadows:
		var on := eye.distance_to(e.at as Vector3) < float(e.near)
		if on == bool(e.on): continue
		e.on = on
		for g: GeometryInstance3D in e.meshes:
			if is_instance_valid(g):
				g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if on else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

## Camera views of every placed asset in context: [name, eye, target] (tests/capture_monuments.gd).
func capture_views() -> Array:
	var views: Array = []
	var seen := {}
	for it in items:
		var id: String = it.id
		var at: Vector3 = it.at
		var yaw: float = it.yaw
		var front := Basis(Vector3.UP, yaw) * Vector3(0, 0, 1)
		var side := Basis(Vector3.UP, yaw) * Vector3(1, 0, 0)
		var h: float = float(info(id).get("height", 3.0))
		var key := id
		if seen.has(key) and id != "basketball_court": continue
		seen[key] = true
		var dist := clampf(h * 1.7, 5.0, 22.0)
		if id == "basketball_court":
			if seen.has("court_done"): continue
			seen["court_done"] = true
			views.append(["court_aerial", Vector3(606, 26, -585), Vector3(606, 0, -614)])
			views.append(["court_gate", at + Vector3(4, 1.7, 22), at + Vector3(0, 1.2, 0)])
			continue
		var eye := at + front * dist + side * dist * 0.45 + Vector3(0, 1.7, 0)
		if id == "ataturk_equestrian": eye = at + front * 9.0 + side * 3.0 + Vector3(0, 1.7, 0)   # from the plaza edge
		views.append([id, eye, at + Vector3(0, h * 0.45, 0)])
	views.append(["park_overview", Vector3(-44, 22, -305), Vector3(-44, 0, -333)])
	views.append(["fountain_close", Vector3(-38.5, 1.6, -331.5), Vector3(-40, 1.0, -335)])
	views.append(["sculpture_pocket", Vector3(-40.5, 1.7, -334), Vector3(-46.9, 1.5, -337)])
	views.append(["equestrian_ring", Vector3(64, 2.0, -112), Vector3(64, 4.0, -145)])
	var sq := square_plaza()
	views.append(["square_street", sq * Vector3(5, 1.7, 14), sq * Vector3(0, 4.0, -7)])
	views.append(["jenner_forecourt", JENNER_AT + Vector3(-16, 1.7, 6), JENNER_AT + Vector3(0, 2.0, 0)])
	return views
