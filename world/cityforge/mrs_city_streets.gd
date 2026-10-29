class_name MrsCityStreets
extends RefCounted
## Port Halden's streets built by Mert Road Studio (tools/cityforge/mrs_streets.py -> assets/cityforge/mrs):
## roads, junctions, crossings, sidewalks, back lanes and bridges per 256 m chunk, plus the rule-placed street
## assets (lights, signals, signs, bus stops, benches, bins, racks, hydrants, cabinets, street trees).
## CityForgeWorld uses it when the plan says streets = "mrs" (its own street ribbons and street furniture are
## then not built or drawn):
##   chunks/c_<i>_<j>.glb  MrsRoads_<i>_<j> (drawn; "PHX_<material>" proxies -> mrs_materials.glb) and
##                         MrsCol_<i>_<j> (hidden; the drivable / walkable surfaces for the chunk's collision)
##   mrs_kit.glb           one mesh per placed library model (MultiMeshes through CityForgeWorld's kit)
##   mrs_city.json         instances, signals (phase per pole), street-name labels, trees, item footprints
## Records are Blender world coordinates (plan - 1024); Godot = (x, z, -y), yaw unchanged.

static var DIR := "res://assets/cityforge/mrs/"          ## follows CityForgeWorld.use_city()
const ROAD_SHADER := preload("res://world/roads/mrs_road.gdshader")
const LENS_SHADER := preload("res://world/cityforge/mrs_signal_lens.gdshader")
const KIT_SIGNAL := "MRS_PH_Signal"
const KIT_STREETNAME := "MRS_PH_StreetName"
const ROADS_RANGE := 2600.0
const LABEL_RANGE := 45.0
const LAMP_NIGHT := 6.0
## Lens colours of the signal head (MRS_Lens_<key>) and their index in mrs_signal_lens.gdshader.
const LENSES := {"Red": [0, Color(1.0, 0.12, 0.06)], "Amber": [1, Color(1.0, 0.62, 0.1)], "Green": [2, Color(0.2, 1.0, 0.55)],
	"PedRed": [3, Color(1.0, 0.18, 0.1)], "PedGreen": [4, Color(0.75, 1.0, 0.85)]}
## Kit models drawn like CityForge's lamps / signals (far) vs small street props (near only).
const STREET_KINDS := ["Light", "Signal", "Shelter", "StreetName", "Kiosk", "InfoBoard"]
## Collider heights (m) of the placed items by kind (their footprints come from the placement).
const ITEM_HEIGHT := {"light": 6.0, "sign": 2.6, "bench": 0.9, "bin": 1.0, "rack": 0.9, "bike_rack": 0.9, "shelter": 2.6, "bus_shelter": 2.6,
	"bus_pole": 2.6, "bus_info": 2.2, "info_board": 2.2, "cabinet": 1.3, "hydrant": 0.8, "planter": 0.8, "bollard": 1.0, "barrier": 1.0}

static var materials: Dictionary = {}          ## engine material name -> Material (mrs_materials.glb)
static var lamp_materials: Array[BaseMaterial3D] = []

var world: CityForgeWorld
var data: Dictionary = {}
var trees: MrsFoliage
var stats: Dictionary = {}

static func available() -> bool:
	return FileAccess.file_exists(DIR + "mrs_city.json")

func _init(w: CityForgeWorld) -> void:
	world = w
	data = JSON.parse_string(FileAccess.get_file_as_string(DIR + "mrs_city.json")) as Dictionary

## Blender world coordinates -> Godot.
static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

## Plan metres of a Blender-world record (what CityForgeWorld._add takes).
func plan_of(v: Array) -> Array:
	return [float(v[0]) + world.size * 0.5, float(v[1]) + world.size * 0.5]

# --- materials ---------------------------------------------------------------------------------
static func load_materials() -> void:
	if not materials.is_empty(): return
	var path := DIR + "mrs_materials.glb"
	if not ResourceLoader.exists(path): return
	var scene := (load(path) as PackedScene).instantiate()
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var src := mi.mesh.surface_get_material(0)
		if src == null: continue
		materials[str(mi.name)] = road_material(src)
		materials[src.resource_name] = materials[str(mi.name)]
	scene.free()

## The game's version of an MRS road material: the asphalt gets the road shader (lane wear from the vertex masks),
## everything keeps its baked tiles with anisotropic filtering, COLOR carries masks (not albedo).
static func road_material(src: Material) -> Material:
	var b := src as BaseMaterial3D
	if b == null: return src
	b.vertex_color_use_as_albedo = false
	b.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	if not b.resource_name.begins_with("MRS_Asphalt"): return b
	var m := ShaderMaterial.new()
	m.shader = ROAD_SHADER
	m.set_shader_parameter("albedo_tex", b.albedo_texture)
	m.set_shader_parameter("uv_scale", Vector2(b.uv1_scale.x, b.uv1_scale.y))
	m.set_shader_parameter("uv_offset", Vector2(b.uv1_offset.x, b.uv1_offset.y))
	if b.normal_enabled and b.normal_texture != null:
		m.set_shader_parameter("normal_tex", b.normal_texture)
		m.set_shader_parameter("has_normal", true)
	if b.roughness_texture != null:
		m.set_shader_parameter("rough_tex", b.roughness_texture)
		m.set_shader_parameter("has_rough", true)
	m.set_shader_parameter("roughness_base", b.roughness)
	m.resource_name = b.resource_name
	return m

static func remap_materials(mesh: Mesh) -> void:
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s)
		if m == null: continue
		var key := m.resource_name.trim_prefix("PHX_")
		if materials.has(key): mesh.surface_set_material(s, materials[key])

# --- chunks ------------------------------------------------------------------------------------
## Each chunk's MRS meshes go under CityForge's chunk node (so its collision pass picks up MrsCol).
func attach_chunks() -> void:
	load_materials()
	var n := int(world.size / CityForgeWorld.CHUNK)
	var tris := 0
	var count := 0
	for ci in n:
		for cj in n:
			var parent: Node3D = world.chunks.get(Vector2i(ci, cj), world)
			var col_path := DIR + "chunks/c_%d_%d_col.glb" % [ci, cj]
			if ResourceLoader.exists(col_path):
				var col := (load(col_path) as PackedScene).instantiate() as Node3D
				col.name = "MrsCollision"
				parent.add_child(col)
				for node in col.find_children("*", "MeshInstance3D", true, false): (node as MeshInstance3D).visible = false
			var path := DIR + "chunks/c_%d_%d.glb" % [ci, cj]
			if not ResourceLoader.exists(path): continue
			var scene := (load(path) as PackedScene).instantiate() as Node3D
			scene.name = "MrsStreets"
			parent.add_child(scene)
			count += 1
			for node in scene.find_children("*", "MeshInstance3D", true, false):
				var mi := node as MeshInstance3D
				if str(mi.name).begins_with("MrsCol"):
					mi.visible = false
					continue
				remap_materials(mi.mesh)
				mi.visibility_range_end = ROADS_RANGE
				mi.visibility_range_end_margin = 20.0
				tris += CityForgeWorld.triangles(mi.mesh)
	stats["chunks"] = count
	stats["tris"] = tris

# --- kit and instances -------------------------------------------------------------------------
## Kit meshes into CityForgeWorld.kit (name -> [LOD0, LOD1]); the signal's lenses get the phase shader.
func load_kit(kit: Dictionary) -> void:
	var path := DIR + "mrs_kit.glb"
	if not ResourceLoader.exists(path): return
	var scene := (load(path) as PackedScene).instantiate()
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var mesh := mi.mesh
		for s in mesh.get_surface_count():
			var m := mesh.surface_get_material(s) as BaseMaterial3D
			if m == null: continue
			var key := m.resource_name.get_slice(".", 0)
			if key.begins_with("MRS_Lens_") and LENSES.has(key.trim_prefix("MRS_Lens_")):
				var spec: Array = LENSES[key.trim_prefix("MRS_Lens_")]
				var lens := ShaderMaterial.new()
				lens.shader = LENS_SHADER
				lens.set_shader_parameter("lens", int(spec[0]))
				lens.set_shader_parameter("lens_color", spec[1])
				mesh.surface_set_material(s, lens)
			elif m.emission_enabled and m.emission_energy_multiplier > 0.0 and not key.begins_with("MRS_Lens_"):
				m.set_meta("night_energy", LAMP_NIGHT)
				lamp_materials.append(m)
			elif m.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_ALWAYS
		kit[kit_key(str(mi.name))] = [mesh, null]
	scene.free()
	set_night(0.0)

## Kit node name -> the library name the instance records use: KIT__<name> (and Blender's .001 copies, which
## glTF import turns into _001).
static func kit_key(node_name: String) -> String:
	var k := node_name.trim_prefix("KIT__")
	var rx := RegEx.create_from_string("^(.*)_[0-9]{3}$")
	var m := rx.search(k)
	return m.get_string(1) if m != null and not k.begins_with("MRS_PH_") else k

## Kit model of a signal record: the corner post, or its mast-arm variant (arm length / heads follow the lanes).
static func signal_kit(s: Dictionary) -> String:
	return str(s.get("kit", KIT_SIGNAL))

static func is_street_kind(name_: String) -> bool:
	for k: String in STREET_KINDS:
		if name_.contains(k): return true
	return false

## Instances for CityForgeWorld's MultiMesh groups (same cells, ranges and HLOD rules as its own props).
func add_instances(groups: Dictionary) -> int:
	var n := 0
	var inst: Dictionary = data.get("instances", {})
	for lib: String in inst:
		for r: Array in inst[lib]:
			world._add(groups, lib, plan_of(r), float(r[2]), float(r[3]), Vector3.ONE * float(r[4]), Color.WHITE, Color.WHITE)
			n += 1
	# signals: the phase cycle runs in the lens shader from the instance custom data
	var phases: Dictionary = {}
	for j: Dictionary in data.get("junctions", []):
		phases[str(j.id)] = int(j.phases)
	for s: Dictionary in data.get("signals", []):
		var jid := str(s.junction)
		var offset := float(hash(jid) % 4600) / 100.0 / 100.0
		world._add(groups, signal_kit(s), plan_of(s.pos), float((s.pos as Array)[2]), float(s.yaw), Vector3.ONE, Color.WHITE,
			Color(float(s.phase), float(phases.get(jid, 2)), offset, 1.0))
		n += 1
	for r: Array in data.get("street_name_signs", []):
		world._add(groups, KIT_STREETNAME, plan_of(r), float(r[2]), float(r[3]), Vector3.ONE, Color.WHITE, Color.WHITE)
		n += 1
	stats["instances"] = n
	return n

## Street names on the blades (Label3D, drawn near the camera only).
func place_labels() -> int:
	var holder := Node3D.new()
	holder.name = "MrsStreetNames"
	world.add_child(holder)
	var n := 0
	for l: Dictionary in data.get("labels", []):
		var label := Label3D.new()
		label.text = str(l.text)
		label.font_size = 48
		label.outline_size = 0
		label.modulate = Color("f6f6f2")
		label.pixel_size = clampf(float(l.get("size", 0.11)) / 48.0 * 1.25, 0.0012, 0.004)
		label.double_sided = false
		label.visibility_range_end = LABEL_RANGE
		label.transform = Transform3D(Basis(Vector3.UP, float(l.yaw)), g(l.pos as Array))
		holder.add_child(label)
		n += 1
	stats["labels"] = n
	return n

## Street trees with Mert Road Studio's foliage (LOD0 / LOD1 / impostor, trunk colliders).
func plant_trees() -> int:
	var recs: Array = data.get("trees", [])
	if recs.is_empty(): return 0
	trees = MrsFoliage.new()
	trees.name = "MrsStreetTrees"
	world.add_child(trees)
	var out := trees.build({"trees": recs, "plants": []}, {"collision": true})
	stats["trees"] = int(out.get("trees", 0))
	return stats["trees"]

# --- collision ---------------------------------------------------------------------------------
## Box colliders for the placed items whose base lies in the chunk (lights, signs, benches, shelters ...).
## Items and signal poles bucketed by chunk once (a chunk's collision pass then only walks its own).
var _by_chunk: Dictionary = {}
var _boxes: Dictionary = {}

func _bucket() -> void:
	var half := world.size * 0.5
	for key: String in ["items", "signals"]:
		for it: Dictionary in data.get(key, []):
			var pos: Array = it.get("pos", [])
			if pos.size() < 2: continue
			var k := Vector2i(int((float(pos[0]) + half) / CityForgeWorld.CHUNK), int((float(pos[1]) + half) / CityForgeWorld.CHUNK))
			if not _by_chunk.has(k): _by_chunk[k] = {"items": [], "signals": []}
			((_by_chunk[k] as Dictionary)[key] as Array).append(it)

func add_item_colliders(body: StaticBody3D, lo: Vector2, hi: Vector2) -> int:
	var n := 0
	var half := world.size * 0.5
	if _by_chunk.is_empty(): _bucket()
	var bucket: Dictionary = _by_chunk.get(Vector2i(int(lo.x / CityForgeWorld.CHUNK), int(lo.y / CityForgeWorld.CHUNK)), {"items": [], "signals": []})
	for it: Dictionary in bucket.items:
		var kind := str(it.get("kind", ""))
		var h := float(ITEM_HEIGHT.get(kind, ITEM_HEIGHT.get(kind.get_slice("_", 0), 0.0)))
		if h <= 0.0: continue
		var pos: Array = it.get("pos", [])
		var foot: Array = it.get("foot", [])
		if pos.size() < 3 or foot.size() < 4: continue
		var px := float(pos[0]) + half
		var py := float(pos[1]) + half
		if px < lo.x or py < lo.y or px >= hi.x or py >= hi.y: continue
		var c0: Array = foot[0]
		var c1: Array = foot[1]
		var c3: Array = foot[3]
		var ux := Vector2(float(c1[0]) - float(c0[0]), float(c1[1]) - float(c0[1]))
		var uy := Vector2(float(c3[0]) - float(c0[0]), float(c3[1]) - float(c0[1]))
		var centre := Vector2.ZERO
		for c: Array in foot: centre += Vector2(float(c[0]), float(c[1])) * 0.25
		var size := (Vector3(maxf(ux.length(), 0.12), h, maxf(uy.length(), 0.12)) * 20.0).round() / 20.0
		if not _boxes.has(size):                 # one shape per size (5 cm steps), shared by every item of that size
			var box := BoxShape3D.new()
			box.size = size
			_boxes[size] = box
		var col := CollisionShape3D.new()
		col.shape = _boxes[size]
		var yaw := atan2(ux.y, ux.x)
		col.transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(centre.x, float(pos[2]) + h * 0.5, -centre.y))
		body.add_child(col)
		n += 1
	for s: Dictionary in bucket.signals:
		var sp: Array = s.pos
		if float(sp[0]) + half < lo.x or float(sp[1]) + half < lo.y or float(sp[0]) + half >= hi.x or float(sp[1]) + half >= hi.y: continue
		var pole := BoxShape3D.new()
		pole.size = Vector3(0.3, 4.4, 0.3)
		var pc := CollisionShape3D.new()
		pc.shape = pole
		pc.position = g(sp) + Vector3(0, 2.2, 0)
		body.add_child(pc)
		n += 1
	return n

# --- night -------------------------------------------------------------------------------------
static func set_night(amount: float) -> void:
	for m: BaseMaterial3D in lamp_materials:
		m.emission_energy_multiplier = float(m.get_meta("night_energy", LAMP_NIGHT)) * amount

# --- the editor's view -------------------------------------------------------------------------
## Street assets for the editor preview (world/editor_preview): no game logic runs in the editor, so the kit
## meshes the preview loaded become plain MultiMeshes (one per model for the whole city) from mrs_city.json.
static func editor_props(kit_scene: Node, holder: Node3D) -> int:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "mrs_city.json")) as Dictionary
	var meshes: Dictionary = {}
	for node in kit_scene.find_children("*", "MeshInstance3D", true, false):
		meshes[kit_key(str(node.name))] = (node as MeshInstance3D).mesh
	var groups: Dictionary = {}
	var inst: Dictionary = data.get("instances", {})
	for lib: String in inst:
		for r: Array in inst[lib]:
			_editor_add(groups, lib, Transform3D(Basis(Vector3.UP, float(r[3])).scaled(Vector3.ONE * float(r[4])), g(r)))
	for s: Dictionary in data.get("signals", []):
		_editor_add(groups, signal_kit(s), Transform3D(Basis(Vector3.UP, float(s.yaw)), g(s.pos as Array)))
	for r: Array in data.get("street_name_signs", []):
		_editor_add(groups, KIT_STREETNAME, Transform3D(Basis(Vector3.UP, float(r[3])), g(r)))
	var n := 0
	for name_: String in groups:
		if not meshes.has(name_): continue
		var mi := _editor_multimesh(meshes[name_] as Mesh, groups[name_] as Array)
		mi.name = "Mrs_" + name_
		mi.visibility_range_end = STREET_RANGE_EDITOR if is_street_kind(name_) else DETAIL_RANGE_EDITOR
		holder.add_child(mi)
		n += (groups[name_] as Array).size()
	return n

## Street trees for the editor preview: each species' LOD1 mesh (assets/roads/foliage) as one MultiMesh.
static func editor_trees(holder: Node3D) -> int:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "mrs_city.json")) as Dictionary
	var groups: Dictionary = {}
	for t: Dictionary in data.get("trees", []):
		_editor_add(groups, str(t.species), Transform3D(Basis(Vector3.UP, float(t.yaw)).scaled(Vector3.ONE * float(t.get("scale", 1.0))), g(t.pos as Array)))
	var n := 0
	for sid: String in groups:
		var path := "res://assets/roads/foliage/%s_lod1.glb" % sid
		if not ResourceLoader.exists(path): continue
		var scene := (load(path) as PackedScene).instantiate()
		var found := scene.find_children("*", "MeshInstance3D", true, false)
		if not found.is_empty():
			var mi := _editor_multimesh((found[0] as MeshInstance3D).mesh, groups[sid] as Array)
			mi.name = "MrsTrees_" + sid
			mi.visibility_range_end = 900.0
			holder.add_child(mi)
			n += (groups[sid] as Array).size()
		scene.free()
	return n

const STREET_RANGE_EDITOR := 700.0
const DETAIL_RANGE_EDITOR := 250.0

static func _editor_add(groups: Dictionary, name_: String, xf: Transform3D) -> void:
	if not groups.has(name_): groups[name_] = []
	(groups[name_] as Array).append(xf)

static func _editor_multimesh(mesh: Mesh, xfs: Array) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = xfs.size()
	for k in xfs.size(): mm.set_instance_transform(k, xfs[k])
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	return mi
