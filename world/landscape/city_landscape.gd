class_name CityLandscape
extends Node3D
## City-wide planting with the converted tree / plant packs (tools/prepare_landscape.py ->
## assets/landscape/). Everything is MultiMesh-instanced per (asset, LOD, cell) with visibility
## ranges; one shared wind shader (foliage_wind.gdshader) animates every plant from baked vertex
## colours, so no plant has a script. Trees have three levels: LOD0 (near, shadows), LOD1 (one
## shared atlas, shadows) and a crossed-quad impostor (all species in one MultiMesh per cell).
##
## Planting (all spots validated through PropPlacer, so nothing stands on a carriageway, a house
## walk, a forecourt, a junction or another prop):
##   * Atatürk Avenue: plane trees (CedarNeighborhood.tree -> street_tree()).
##   * side roads and cross streets: lindens / walnuts at the back of the sidewalk.
##   * residential lots: front-garden maples / cherries, shrubs and flower beds by the facade,
##     backyard shade trees.
##   * parks: tree groups, shrubs, rocks and grass in the corners outside the oval promenade
##     (the centre, paths, fountain, statue and sign stay clear for the park features).
##   * shops / restaurants: potted plants beside the entrances.
##   * edge forest strips: understory (rocks, small cards, grass); beyond the boundary a forest of
##     the low-poly conifer / birch cards on the meadow and the horizon hills, impostors far away.

const DIR := "res://assets/landscape/"
## Tree species in impostor-slot order (tools/prepare_landscape.py TREES).
const TREES: Array[String] = ["plane_tree", "maple_a", "maple_b", "maple_c", "walnut_spring", "walnut_autumn_a", "walnut_autumn_b",
	"linden_a", "linden_b", "linden_c", "cherry", "grove_a", "grove_b"]
const SHADE_TREES: Array[String] = ["walnut_spring", "walnut_autumn_a", "walnut_autumn_b", "linden_a", "linden_b", "linden_c", "grove_a", "grove_b"]
const STREET_TREES: Array[String] = ["linden_a", "linden_b", "linden_c", "walnut_spring", "grove_a"]
const GARDEN_TREES: Array[String] = ["maple_a", "maple_b", "maple_c", "cherry", "maple_a", "maple_b"]
const PARKS: Array[Vector3] = [Vector3(-64, 0, -145), Vector3(64, 0, -145), Vector3(-44, 0, -330), Vector3(44, 0, -330),
	Vector3(-44, 0, -470), Vector3(44, 0, -470), Vector3(-44, 0, -590), Vector3(44, 0, -590)]
const LOD0_CELL := 32.0
const LOD1_CELL := 96.0
const FAR_CELL := 192.0
## Every tree switches LOD1 -> impostor here, so all impostors of a cell share one MultiMesh.
const TREE_FAR_BEGIN := 125.0
const FAR_END := 1400.0
## Profiling switch (tests/profile_streets.gd "landscape_off"): only the avenue / park trees.
static var enabled := true
## Benchmark baseline (tests/profile_streets.gd "... -- out.json after legacy"): the old kit trees
## on the avenue / in the parks and no landscape planting at all.
static var legacy := false

var placer: PropPlacer
var groups: Dictionary = {}        ## key -> {"mesh", "begin", "end", "shadow", "xf": Array[Transform3D], "cust": Array[Color]}
var counts: Dictionary = {}        ## asset -> instance count
var trunks: StaticBody3D
var rng := RandomNumberGenerator.new()
var lights: Array[Vector3] = []

static var _species: Dictionary = {}   ## tree id -> {"lod0", "lod1", "height", ...}
static var _props: Dictionary = {}     ## garden / forest / rock node name -> {"mesh", "height"}
static var _impostor: Mesh
static var _materials: Dictionary = {}

func _init() -> void:
	name = "Landscape"
	rng.seed = 51921

func _ready() -> void:
	trunks = StaticBody3D.new()
	trunks.name = "TreeTrunks"
	add_child(trunks)

# ----------------------------------------------------------------------------- assets

static func load_assets() -> void:
	if not _species.is_empty(): return
	var far_scene: Node = (load(DIR + "trees_far.glb") as PackedScene).instantiate()
	for sid in TREES:
		var root: Node = (load(DIR + sid + ".glb") as PackedScene).instantiate()
		var lod0_node := root.find_child("LOD0", true, false) as MeshInstance3D
		var holder: Node = lod0_node.get_parent()
		var extras: Dictionary = holder.get_meta("extras", {}) if holder.has_meta("extras") else {}
		var h: float = float(extras.get("height", 10.0))
		var lod1_node := far_scene.find_child(sid + "_LOD1", true, false) as MeshInstance3D
		_species[sid] = {"lod0": foliage_mesh(lod0_node.mesh, h, sid), "lod1": foliage_mesh(lod1_node.mesh, h, sid + "_lod1"),
			"height": h, "crown": float(extras.get("crown_radius", 3.0)), "crown_base": float(extras.get("crown_base", 2.5)),
			"trunk": clampf(float(extras.get("trunk_radius", 0.25)), 0.12, 0.45), "slot": int(extras.get("far_slot", TREES.find(sid))),
			"far": float(extras.get("far_size", h))}
		root.free()
	var imp := far_scene.find_child("Impostor", true, false) as MeshInstance3D
	_impostor = foliage_mesh(imp.mesh, 1.0, "impostor", true)
	far_scene.free()
	for file in ["forest_pack", "rocks", "garden"]:
		var scene: Node = (load(DIR + file + ".glb") as PackedScene).instantiate()
		for node in scene.find_children("*", "MeshInstance3D", true, false):
			var mi := node as MeshInstance3D
			var extras: Dictionary = mi.get_meta("extras", {}) if mi.has_meta("extras") else {}
			var h: float = float(extras.get("height", mi.mesh.get_aabb().size.y))
			_props[str(mi.name)] = {"mesh": foliage_mesh(mi.mesh, h, str(mi.name)), "height": h, "kind": str(extras.get("kind", "")),
				"slot": int(extras.get("far_slot", -1)), "far": float(extras.get("far_size", h))}
		scene.free()

## A copy of an imported mesh whose surfaces use the shared wind shader (foliage) or a plain
## material without the vertex-colour tint (stone, mulch, pots, rocks).
static func foliage_mesh(source: Mesh, height: float, id: String, impostor: bool = false) -> Mesh:
	var mesh := source.duplicate() as Mesh
	for s in range(mesh.get_surface_count()):
		var src := mesh.surface_get_material(s) as BaseMaterial3D
		mesh.surface_set_material(s, material_for(src, height, id, impostor))
	return mesh

const SOLID := ["bed_stone", "bed_mulch", "rock", "plant_Material__1", "plant_Material__6", "plant_Material__13"]

static func material_for(src: BaseMaterial3D, height: float, id: String, impostor: bool) -> Material:
	var mat_name := src.resource_name if src != null else ""
	var key := "%s|%s|%.1f" % [mat_name, id if impostor else "", height]
	if _materials.has(key): return _materials[key]
	var result: Material
	if src != null and (mat_name in SOLID or mat_name.begins_with("rock")):
		var plain := src.duplicate() as BaseMaterial3D
		plain.vertex_color_use_as_albedo = false
		plain.roughness = maxf(plain.roughness, 0.8)
		result = plain
	else:
		var m := ShaderMaterial.new()
		m.shader = preload("res://world/landscape/foliage_wind.gdshader")
		var bark := mat_name.ends_with("_bark") or mat_name.begins_with("fp_tree_trunk")
		var cut := src != null and src.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		if src != null and src.albedo_texture != null: m.set_shader_parameter("albedo_tex", src.albedo_texture)
		if src != null and src.normal_enabled and src.normal_texture != null:
			m.set_shader_parameter("normal_tex", src.normal_texture)
			m.set_shader_parameter("use_normal_map", true)
		m.set_shader_parameter("leaves", not bark)
		m.set_shader_parameter("cutout", cut or impostor)
		var sway_k := 0.034 if id.begins_with("linden") else 0.022
		m.set_shader_parameter("sway", height * sway_k)
		m.set_shader_parameter("roughness", 0.9 if bark else 0.78)
		if mat_name.begins_with("plant_"):
			m.set_shader_parameter("ao_strength", 0.0)
			m.set_shader_parameter("translucency", 0.2)
		if impostor:
			m.set_shader_parameter("impostor", true)
			m.set_shader_parameter("ao_strength", 0.0)
			m.set_shader_parameter("translucency", 0.15)
		result = m
	_materials[key] = result
	return result

static func species(sid: String) -> Dictionary:
	load_assets()
	return _species[sid]

static func prop(id: String) -> Dictionary:
	load_assets()
	return _props.get(id, {})

static func prop_ids(kind: String) -> Array[String]:
	load_assets()
	var list: Array[String] = []
	for k: String in _props:
		if str(_props[k].kind) == kind: list.append(k)
	list.sort()
	return list

# ----------------------------------------------------------------------------- instancing

func queue(asset: String, mesh: Mesh, xf: Transform3D, cell: float, begin: float, end: float, shadow: bool, custom: Color) -> void:
	var c := Vector2i(floori(xf.origin.x / cell), floori(xf.origin.z / cell))
	var key := "%s|%d|%d|%d" % [asset, int(begin), c.x, c.y]
	if not groups.has(key):
		var xs: Array[Transform3D] = []
		var cs: Array[Color] = []
		groups[key] = {"mesh": mesh, "begin": begin, "end": end, "shadow": shadow, "xf": xs, "cust": cs, "asset": asset}
	(groups[key].xf as Array[Transform3D]).append(xf)
	(groups[key].cust as Array[Color]).append(custom)

func tint() -> Color:
	var v := rng.randf_range(-0.06, 0.06)
	return Color(0.5 + v + rng.randf_range(-0.02, 0.02), 0.5 + v + rng.randf_range(-0.03, 0.03), 0.5 + v, 0.0)

## One tree with its three LODs and a trunk collider. Returns false when the species is missing.
## Building footprints (x, z) that tree crowns must keep out of: kit buildings (terraces, walk-ups,
## corridor blocks), the residential houses' bodies, the avenue restaurants, the shops / WC and the
## Cedar House. Crowns used to grow through terrace walls and roofs from the side-road sidewalks.
static var _buildings: Array[Rect2] = []
static func building_rects() -> Array[Rect2]:
	if not _buildings.is_empty(): return _buildings
	# Kit facades: bays, sills, gables and the corner posts stand up to ~0.3 m out of the footprint.
	for b in CityLayout.buildings(): _buildings.append(CityLayout.footprint(b).grow(0.35))
	for lot in ResidentialLayout.lots():
		var spec: Dictionary = ResidentialLayout.TYPES[lot.type]
		var t := ResidentialLayout.transform(lot)
		var w: float = spec.w
		var d: float = spec.d
		var rect := Rect2()
		for k in range(4):
			var c: Vector3 = t * Vector3((-0.5 if k % 2 == 0 else 0.5) * w, 0, 0.0 if k < 2 else -d)
			rect = Rect2(Vector2(c.x, c.z), Vector2.ZERO) if k == 0 else rect.expand(Vector2(c.x, c.z))
		_buildings.append(rect.grow(0.8))   # eaves, bays and porch roofs reach past the walls
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		_buildings.append(Rect2(p.x - 10.2, p.z - 8.0, 12.4, 11.0))
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		_buildings.append(Rect2(at.x - 7.2, at.z - 5.2, 14.4, 10.6))
	_buildings.append(Rect2(-47.2, 26.8, 14.4, 10.6))   # public WC (-40, 32)
	var home: Vector3 = CedarNeighborhood.CEDAR_HOME_ORIGIN
	_buildings.append(Rect2(home.x - 6.5, home.z - 7.5, 13.0, 13.0))
	return _buildings

## True when a crown of `radius` at `at` stays clear of every building footprint.
static func crown_clear(at: Vector3, radius: float) -> bool:
	var p := Vector2(at.x, at.z)
	for rect in building_rects():
		var q := Vector2(clampf(p.x, rect.position.x, rect.end.x), clampf(p.y, rect.position.y, rect.end.y))
		if q.distance_to(p) < radius: return false
	return true

func add_tree(sid: String, at: Vector3, yaw: float, scale: float, collide: bool = true, near_end: float = -1.0) -> bool:
	var sp := species(sid)
	if sp.is_empty(): return false
	# Crown reach: the larger of the catalogue crown radius and the LOD0 foliage's own extent.
	var box: AABB = (sp.lod0 as Mesh).get_aabb()
	var reach := maxf(float(sp.crown), maxf(maxf(-box.position.x, box.end.x), maxf(-box.position.z, box.end.z)))
	# ... and of the distant impostor card, which is drawn at the same spot at sp.far scale.
	if _impostor != null:
		var ibox: AABB = _impostor.get_aabb()
		reach = maxf(reach, maxf(maxf(-ibox.position.x, ibox.end.x), maxf(-ibox.position.z, ibox.end.z)) * float(sp.far))
	# A crown that would reach into a building is grown smaller (down to 20 %) before the tree is
	# given up: a smaller tree by the facade instead of none.
	var fitted := scale
	while not crown_clear(at, reach * fitted * 0.95):
		fitted *= 0.88
		if fitted < scale * 0.2: return false
	scale = fitted
	var h: float = sp.height * scale
	var basis := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * scale)
	var xf := Transform3D(basis, at)
	var custom := tint()
	# Switch distances per species (not per instance), so each species/cell is one batch.
	var end0 := snappedf(clampf(float(sp.height) * 3.0, 26.0, 42.0), 2.0) if near_end < 0.0 else near_end
	var end1 := TREE_FAR_BEGIN
	queue(sid + "_0", sp.lod0, xf, LOD0_CELL, 0.0, end0, true, custom)
	# LOD1 casts no shadow: past ~30 m the crown shadow is carried by the sun's coarse cascades
	# and the cost (4 cascades x every LOD1 batch) is not worth it.
	queue(sid + "_1", sp.lod1, xf, LOD1_CELL, end0, end1, false, custom)
	var far: float = sp.far * scale
	custom.a = (float(sp.slot) + 0.1) / 255.0
	queue("impostor", _impostor, Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * far), at), FAR_CELL, end1, FAR_END, false, custom)
	counts[sid] = int(counts.get(sid, 0)) + 1
	if collide:
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = clampf(float(sp.trunk) * scale, 0.14, 0.42)
		capsule.height = 3.5
		shape.shape = capsule
		shape.position = at + Vector3(0, 1.75, 0)
		trunks.add_child(shape)
	return true

## A single-LOD prop (shrub, grass, potted plant, rock, forest card) from the kit GLBs.
func add_prop(id: String, xf: Transform3D, end: float, shadow: bool, cell: float = 64.0, begin: float = 0.0) -> bool:
	var p := prop(id)
	if p.is_empty(): return false
	queue(id + ("_far" if begin > 0.0 else ""), p.mesh, xf, cell, begin, end, shadow, tint())
	counts[id] = int(counts.get(id, 0)) + 1
	return true

func flush() -> void:
	for key: String in groups:
		var g: Dictionary = groups[key]
		var xs: Array[Transform3D] = g.xf
		var cs: Array[Color] = g.cust
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = g.mesh
		mm.instance_count = xs.size()
		for i in range(xs.size()):
			mm.set_instance_transform(i, xs[i])
			mm.set_instance_custom_data(i, cs[i])
		var node := MultiMeshInstance3D.new()
		node.name = key.replace("|", "_")
		node.multimesh = mm
		node.visibility_range_begin = float(g.begin)
		node.visibility_range_begin_margin = 4.0 if float(g.begin) > 0.0 else 0.0
		node.visibility_range_end = float(g.end)
		node.visibility_range_end_margin = 4.0
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if g.shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.set_meta("prop", str(g.asset))
		add_child(node)
	groups.clear()

# ----------------------------------------------------------------------------- street trees

## Trees requested by CedarNeighborhood.tree() (avenue and the original park trees).
func street_tree(at: Vector3) -> void:
	if legacy:
		# The pre-landscape city kit trees (benchmark baseline).
		var variation := absi(int(at.x * 7 + at.z)) % 3
		var model := CityAssets.create(["maple", "birch", "conifer"][variation], 240)
		model.position = at
		model.rotation.y = fmod(absf(at.z * 0.83 + at.x), TAU)
		model.scale = Vector3.ONE * (0.80 + float(variation) * 0.12)
		add_child(model)
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.24
		capsule.height = 3.5
		shape.shape = capsule
		shape.position = at + Vector3(0, 1.75, 0)
		trunks.add_child(shape)
		return
	var k := absi(int(at.x * 7.0 + at.z * 3.0))
	if absf(at.x) < 13.0 and at.z < 47.0:
		add_tree("plane_tree", at, fposmod(at.z * 0.83 + at.x, TAU), 0.9 + float(k % 5) * 0.05)
	else:
		add_tree(SHADE_TREES[k % SHADE_TREES.size()], at, fposmod(at.z * 0.61, TAU), 0.85 + float(k % 4) * 0.05)

func light_near(p: Vector3, d: float) -> bool:
	for l in lights:
		if absf(l.z - p.z) < d and l.distance_to(p) < d: return true
	return false

## Plant the whole city (called once the streets, houses, parks and furniture exist).
func plant_city() -> void:
	if legacy: return
	load_assets()
	for rec in placer.records:
		if rec.kind == "street_light": lights.append(rec.at)
	if enabled:
		side_road_trees()
		cross_street_trees()
		for lot in ResidentialLayout.lots(): plant_lot(lot)
		for park in PARKS: plant_park(park)
		shop_fronts()
		forest_understory()
		horizon_forest()
	flush()

func street_row(from: Vector3, to: Vector3, across: Vector3, step: float, pool: Array[String], source: String) -> void:
	var dir := (to - from).normalized()
	var length := from.distance_to(to)
	var s := step * 0.5
	var n := 0
	while s < length:
		var want := from + dir * s
		var spot: Variant = placer.place("tree", want, 0.4, {"slide": dir, "max_slide": step * 0.4, "walk": 1.1, "junction": 6.5,
			"gap": 0.5, "source": source})
		if spot != null:
			var p: Vector3 = spot
			if light_near(p, 4.0):
				placer.unrecord_last()
			else:
				var sid: String = pool[(n + int(absf(p.x) * 0.1)) % pool.size()]
				if add_tree(sid, p, rng.randf() * TAU, rng.randf_range(0.82, 0.98)): n += 1
				else: placer.unrecord_last()   # its crown would grow into a building
		s += step

## Side roads south of Refet Bele Street (10 m): trees at the back of both sidewalks.
func side_road_trees() -> void:
	for x: float in CityCatalog.SIDE_ROADS:
		for side in [-1.0, 1.0]:
			var line: float = x + side * 8.45
			street_row(Vector3(line, 0, -268), Vector3(line, 0, -668), Vector3(side, 0, 0), 15.0, STREET_TREES, "side_road_tree")

## Cross streets between the avenue and the side roads.
func cross_street_trees() -> void:
	var pool: Array[String] = ["walnut_autumn_a", "linden_b", "walnut_spring", "linden_a", "walnut_autumn_b"]
	for z: float in CityCatalog.CROSS_STREETS:
		for side in [-1.0, 1.0]:
			var line: float = z + side * 8.45
			for span in [Vector2(-54, -14), Vector2(14, 54)]:
				street_row(Vector3(span.x, 0, line), Vector3(span.y, 0, line), Vector3(0, 0, side), 14.0, pool, "cross_street_tree")

# ----------------------------------------------------------------------------- residential lots

## Local rectangles of the porch decks, stair ramp and front walk of a house type (x0, z0, x1, z1).
static func porch_rects(type: String) -> Array[Rect2]:
	var spec: Dictionary = ResidentialLayout.TYPES[type]
	var rects: Array[Rect2] = []
	for b: Array in spec.boxes:
		var c: Vector3 = b[0]
		var s: Vector3 = b[1]
		rects.append(Rect2(c.x - s.x / 2, c.z - s.z / 2, s.x, s.z))
	if not (spec.ramp as Array).is_empty():
		var r: Array = spec.ramp
		rects.append(Rect2(float(r[0]), float(r[3]), float(r[1]) - float(r[0]), float(r[4]) - float(r[3])))
	var door: Vector3 = spec.door
	rects.append(Rect2(door.x - 1.1, -0.2, 2.2, ResidentialLayout.SETBACK + 1.0))   # walk + steps
	rects.append(Rect2(-spec.w / 2 + 0.6, 0.6, 1.6, 1.6))                          # garden_bed
	rects.append(Rect2(door.x - 1.7, 3.6, 3.4, 1.4))                                  # mailbox / number post
	return rects

static func local_clear(rects: Array[Rect2], p: Vector2, r: float) -> bool:
	for rect in rects:
		if rect.grow(r).has_point(p): return false
	return true

func plant_lot(lot: Dictionary) -> void:
	var spec: Dictionary = ResidentialLayout.TYPES[lot.type]
	var t := ResidentialLayout.transform(lot)
	var w: float = spec.w
	var d: float = spec.d
	var lot_w: float = lot.width
	var rects := porch_rects(lot.type)
	var door: Vector3 = spec.door
	var seed_i := absi(int(lot.front.z * 13.0 + lot.front.x * 7.0))
	var avenue := absf(float(lot.line_x)) == 10.5
	# Front garden tree (not on the avenue, whose plane trees already line the lots).
	if not avenue and seed_i % 9 < 4:
		var side := -1.0 if door.x > 0.0 else 1.0
		var local := Vector3(side * (lot_w / 2 - 1.5), 0, 3.3)
		if local_clear(rects, Vector2(local.x, local.z), 0.6):
			var at := t * local
			if placer.place("tree", at, 0.4, {"walk": 1.0, "source": "garden_tree"}) != null:
				if not add_tree(GARDEN_TREES[seed_i % GARDEN_TREES.size()], at, rng.randf() * TAU, rng.randf_range(0.72, 0.86)): placer.unrecord_last()
	# Shrubs at the facade corners and a flower bed beside the porch.
	for sx in [-1.0, 1.0]:
		var ids := prop_ids("shrub")
		var sid: String = ids[(seed_i + int(sx)) % ids.size()]
		var shrub_scale := rng.randf_range(0.7, 0.95)
		# Out from the facade by the shrub's own spread plus the 0.25 m the houses' skirts, sills and
		# bays stand proud of the wall line (it used to grow into the wall / the craftsman's skirt).
		var sbox: AABB = (prop(sid).mesh as Mesh).get_aabb()
		var spread := maxf(maxf(-sbox.position.x, sbox.end.x), maxf(-sbox.position.z, sbox.end.z)) * shrub_scale
		var local := Vector3(sx * (w / 2 - maxf(0.7, spread + 0.05)), 0, maxf(1.1, spread + 0.35))
		if (seed_i + int(sx)) % 5 == 0 or not local_clear(rects, Vector2(local.x, local.z), 0.45): continue
		var at := t * local
		if placer.problem("shrub", at, 0.5, {"walk": 0.6}) != "": continue
		placer.record("shrub", at, 0.5, "front_shrub")
		add_prop(sid, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * shrub_scale), at), 55.0, true)
	if seed_i % 5 < 3:
		var right := door.x + 1.25 + 1.3
		if right + 1.3 < w / 2 - 1.2:
			var local := Vector3(right + 0.1, 0, 0.75)
			var ok := true
			for k in [-1.15, 0.0, 1.15]:
				if not local_clear(rects, Vector2(local.x + float(k), local.z), 0.25): ok = false
			var at := t * local
			if ok and placer.problem("bed", at, 1.2, {"walk": 0.4}) == "":
				placer.record("bed", at, 1.2, "flower_bed", true)
				var basis := Basis(Vector3.UP, float(lot.yaw))
				add_prop("bed_edging", Transform3D(basis, at), 60.0, false)
				var plants: Array[String] = ["bed_croton", "bed_snake", "bed_croton", "grass_b"]
				for k in range(4):
					var off := Vector3(-0.85 + k * 0.57 + rng.randf_range(-0.08, 0.08), 0.06, rng.randf_range(-0.1, 0.1))
					var pid: String = plants[(seed_i + k) % plants.size()]
					add_prop(pid, Transform3D(basis.rotated(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.8, 1.05)), t * (local + off)), 50.0, false)
	# A grass clump by the front fence.
	if seed_i % 3 == 0:
		var local := Vector3((seed_i % 7 - 3) * 0.9, 0, 4.2)
		if local_clear(rects, Vector2(local.x, local.z), 0.5):
			var at := t * local
			if placer.problem("grass", at, 0.3, {"walk": 0.5, "gap": 0.1}) == "":
				add_prop("grass_a", Transform3D(Basis(Vector3.UP, rng.randf() * TAU), at), 45.0, false)
	# Backyard shade tree, on the bins / raised-bed side of the yard.
	var back := -(float(lot.depth) - ResidentialLayout.SETBACK)
	if back + d < -4.5 and seed_i % 7 < 4:
		var local := Vector3(-lot_w / 2 + 3.3, 0, back + 2.9)
		var at := t * local
		if placer.place("tree", at, 0.4, {"walk": 0.5, "soft_ok": false, "source": "backyard_tree"}) != null:
			var planted := add_tree(SHADE_TREES[seed_i % SHADE_TREES.size()], at, rng.randf() * TAU, rng.randf_range(0.7, 0.85))
			if not planted: placer.unrecord_last()
			if planted and seed_i % 2 == 0:
				add_prop("grass_b", Transform3D(Basis(Vector3.UP, rng.randf() * TAU), at + t.basis * Vector3(0.7, 0, 0.5)), 40.0, false)

# ----------------------------------------------------------------------------- parks

## True inside the park's oval promenade or on its cross paths (kept clear for the park features).
static func park_core(park: Vector3, p: Vector3, margin: float) -> bool:
	var dx := p.x - park.x
	var dz := p.z - park.z
	if absf(dx) < 1.3 + margin or absf(dz) < 1.3 + margin: return true
	return Vector2(dx / (9.0 + margin), dz / (14.0 + margin)).length() < 1.0

func plant_park(park: Vector3) -> void:
	var round_park := absf(park.z + 145.0) < 1.0
	var spots: Array[Vector3] = []
	for k in range(140):
		var p := park + Vector3(rng.randf_range(-9.6, 9.6), 0, rng.randf_range(-15.6, 15.6))
		if round_park and Vector2(p.x - park.x, p.z - park.z).length() > 14.2: continue
		if park_core(park, p, 1.4): continue
		spots.append(p)
	var trees := 0
	var pool: Array[String] = ["walnut_autumn_a", "linden_a", "grove_a", "walnut_spring", "linden_c", "grove_b", "walnut_autumn_b"]
	if round_park: pool.assign(["cherry", "maple_a", "maple_c", "grove_b"])
	for p in spots:
		if trees >= (6 if round_park else 7): break
		if placer.problem("tree", p, 0.4, {"spacing": 5.5, "gap": 1.0}) != "": continue
		var sid: String = pool[(trees + int(absf(park.z))) % pool.size()]
		if trees == 2 and not round_park: sid = "cherry"
		if not add_tree(sid, p, rng.randf() * TAU, rng.randf_range(0.7, 0.85) if not round_park else rng.randf_range(0.75, 0.9)): continue
		placer.record("tree", p, 0.4, "park_tree")
		trees += 1
	# Shrub groups, a rock group and grass tufts.
	var shrubs := prop_ids("shrub")
	var placed := 0
	for p in spots:
		if placed >= 9: break
		if placer.problem("shrub", p, 0.6, {"gap": 0.6}) != "": continue
		placer.record("shrub", p, 0.6, "park_shrub")
		add_prop(shrubs[placed % shrubs.size()], Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.8, 1.15)), p), 60.0, true)
		for g in range(2):
			var q := p + Vector3(rng.randf_range(-1.3, 1.3), 0, rng.randf_range(-1.3, 1.3))
			if not park_core(park, q, 0.6):
				add_prop("grass_a" if g == 0 else "grass_b", Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.8, 1.2)), q), 45.0, false)
		placed += 1
	var rocks := prop_ids("rock")
	for p in spots:
		if placer.problem("rock", p, 1.0, {"gap": 0.8}) != "": continue
		placer.record("rock", p, 1.0, "park_rocks")
		for r in range(3):
			var q := p + Vector3(rng.randf_range(-0.9, 0.9), 0, rng.randf_range(-0.9, 0.9))
			add_prop(rocks[rng.randi() % rocks.size()], Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.9, 1.6)), q), 90.0, false)
		break

# ----------------------------------------------------------------------------- frontages

func shop_fronts() -> void:
	var pots: Array[String] = ["potted_lily", "potted_snake"]
	var k := 0
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		for x in [-2.9, 2.9]:
			var p := at + Vector3(x, 0, 5.55)
			if placer.problem("planter", p, 0.35, {"reserved_ok": true, "walk": 0.3}) != "": continue
			placer.record("planter", p, 0.35, "shop_pot")
			add_prop(pots[k % pots.size()], Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * 1.15), p), 60.0, false)
			k += 1
	for i in range(3):
		var p0: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		for x in [-10.4, 1.6]:
			var p := p0 + Vector3(x, 0, 3.4)
			if placer.problem("planter", p, 0.35, {"reserved_ok": true, "walk": 0.3}) != "": continue
			placer.record("planter", p, 0.35, "restaurant_pot")
			add_prop(pots[k % pots.size()], Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * 1.1), p), 60.0, false)
			k += 1

# ----------------------------------------------------------------------------- forests

## Understory in the edge-forest strips (ResidentialLayout.forest()): rocks, small cards, grass.
func forest_understory() -> void:
	var smalls := prop_ids("understory")
	var rocks := prop_ids("rock")
	var i := 0
	for f in ResidentialLayout.forest():
		i += 1
		if i % 3 != 0: continue
		var p := f.origin + Vector3(rng.randf_range(-2.2, 2.2), 0, rng.randf_range(-2.2, 2.2))
		if not PropPlacer.surface_at(Vector2(p.x, p.z), 1.5).is_empty(): continue
		var basis := Basis(Vector3.UP, rng.randf() * TAU)
		match i % 4:
			0:
				var rid: String = rocks[rng.randi() % rocks.size()]
				var rscale := rng.randf_range(1.0, 2.2)
				# Clear of the forest's trunks (rocks used to sit through them).
				var rbox: AABB = (prop(rid).mesh as Mesh).get_aabb()
				var rr := maxf(rbox.size.x, rbox.size.z) * 0.5 * rscale + 0.45
				var hits_trunk := false
				for g in ResidentialLayout.forest():
					if Vector2(g.origin.x - p.x, g.origin.z - p.z).length() < rr: hits_trunk = true
				# ... and of the rear lanes' power poles (HouseInstancer.build_lane: lane edge + 0.3 m,
				# every 30 m from 6 m in): a rock sat through one.
				for lane in ResidentialLayout.lanes():
					var px: float = float(lane.x) + (1.0 if float(lane.x) > 0 else -1.0) * (float(lane.width) / 2 + 0.3)
					if absf(px - p.x) > rr + 0.2: continue
					var z: float = float(lane.z0) + 6.0
					while z < float(lane.z1) - 3.0:
						if Vector2(px - p.x, z - p.z).length() < rr + 0.2: hits_trunk = true
						z += 30.0
				if not hits_trunk: add_prop(rid, Transform3D(basis.scaled(Vector3.ONE * rscale), p), 110.0, false, 64.0)
			1: add_prop(smalls[rng.randi() % smalls.size()], Transform3D(basis.scaled(Vector3.ONE * rng.randf_range(0.6, 1.0)), p), 90.0, false, 64.0)
			_: add_prop("grass_a" if i % 2 == 0 else "grass_b", Transform3D(basis.scaled(Vector3.ONE * rng.randf_range(1.0, 1.5)), p), 50.0, false, 64.0)

## Ground height of the horizon terrain (world/build_city_assets.py landscape(), with the
## downtown footprint lowered as terrain_transition.gdshader does).
static func terrain_height(x: float, z: float) -> float:
	var outside := maxf(maxf(absf(x) - 135.0, z - 78.0), maxf(-718.0 - z, 0.0))
	var rise := maxf(0.0, outside - 35.0)
	var y := -0.12 + rise * (0.04 + 0.07 * pow(sin(x * 0.011 + z * 0.004), 2.0)) + minf(rise, 80.0) * 0.15 * sin(z * 0.018) * cos(x * 0.016)
	var area := smoothstep(105.0, 130.0, x) * (1.0 - smoothstep(635.0, 680.0, x)) * smoothstep(-730.0, -704.0, z) * (1.0 - smoothstep(-232.0, -205.0, z))
	return lerpf(y, -0.25, area)

## Bilinear sample of terrain_height on the terrain mesh's 20 m grid (what is actually rendered).
static func ground(x: float, z: float) -> float:
	var gx := (x + 660.0) / 20.0
	var gz := (z + 1120.0) / 20.0
	var x0 := floorf(gx) * 20.0 - 660.0
	var z0 := floorf(gz) * 20.0 - 1120.0
	var fx := gx - floorf(gx)
	var fz := gz - floorf(gz)
	var a := lerpf(terrain_height(x0, z0), terrain_height(x0 + 20.0, z0), fx)
	var b := lerpf(terrain_height(x0, z0 + 20.0), terrain_height(x0 + 20.0, z0 + 20.0), fx)
	return lerpf(a, b, fz)

## True where the horizon forest may grow: outside the playable city and off downtown / civic land.
static func wild(p: Vector3) -> bool:
	if p.x > -123.0 and p.x < 123.0 and p.z > -713.0 and p.z < 74.0: return false
	if p.x > 100.0 and p.x < 700.0 and p.z > -735.0 and p.z < -200.0: return false   # downtown, civic campus
	if absf(p.x) > 650.0 or p.z < -1110.0 or p.z > 470.0: return false
	return true

const CONIFER_NEAR := 340.0

func conifer(id: String, p: Vector3, yaw: float, scale: float, shadow: bool) -> void:
	var c := prop(id)
	var basis := Basis(Vector3.UP, yaw)
	queue(id, c.mesh, Transform3D(basis.scaled(Vector3.ONE * scale), p), FAR_CELL, 0.0, CONIFER_NEAR, shadow, tint())
	var custom := tint()
	custom.a = (float(c.slot) + 0.1) / 255.0
	queue("impostor", _impostor, Transform3D(basis.scaled(Vector3.ONE * float(c.far) * scale), p), FAR_CELL, CONIFER_NEAR, FAR_END, false, custom)
	counts[id] = int(counts.get(id, 0)) + 1

func horizon_forest() -> void:
	var noise := FastNoiseLite.new()
	noise.seed = 3317
	noise.frequency = 0.012
	var big := prop_ids("forest_tree")
	var far_big: Array[String] = []
	for id in big:
		if int(prop(id).slot) >= 0: far_big.append(id)
	var pines := prop_ids("forest_pine")
	var smalls := prop_ids("understory")
	var made := 0
	var extra := false
	var z := -1100.0
	while z < 470.0:
		var x := -650.0
		while x < 650.0:
			var p := Vector3(x + rng.randf_range(-4.0, 4.0), 0, z + rng.randf_range(-4.0, 4.0))
			# Distance beyond the city edge: dense forest near the boundary, patches further out.
			var edge := maxf(maxf(absf(p.x) - 120.0, p.z - 70.0), -712.0 - p.z)
			# The band seen from the streets gets a second, offset tree per cell.
			if edge < 70.0 and not extra:
				extra = true
				p += Vector3(5.5, 0, 5.5)
			else:
				extra = false
				x += 11.0
			if not wild(p): continue
			edge = maxf(maxf(absf(p.x) - 120.0, p.z - 70.0), -712.0 - p.z)
			var density := noise.get_noise_2d(p.x, p.z) * 0.5 + 0.5
			var keep := 0.95 if edge < 40.0 else (0.4 + density * 0.6) * (1.0 if edge < 250.0 else 0.75)
			if density < 0.3 and edge > 40.0: keep *= 0.3
			if rng.randf() > keep: continue
			p.y = ground(p.x, p.z) - 0.25
			var basis := Basis(Vector3.UP, rng.randf() * TAU)
			var r := rng.randf()
			var shadow := edge < 30.0
			if edge > 70.0 or r < 0.55:
				# Card conifer near, its impostor (shared atlas, one MultiMesh per cell) far away.
				conifer(far_big[rng.randi() % far_big.size()], p, rng.randf() * TAU, rng.randf_range(0.55, 0.85), shadow)
			elif r < 0.75:
				# The other conifer / birch cards only in the band seen from the streets.
				add_prop(big[rng.randi() % big.size()], Transform3D(basis.scaled(Vector3.ONE * rng.randf_range(0.55, 0.85)), p), 600.0, shadow, FAR_CELL)
			elif r < 0.87:
				add_prop(pines[rng.randi() % pines.size()], Transform3D(basis.scaled(Vector3.ONE * rng.randf_range(0.8, 1.1)), p), 450.0, shadow, FAR_CELL)
			else:
				# Deciduous trees at the forest edge, with full LODs (no collision beyond the boundary).
				var sid: String = SHADE_TREES[rng.randi() % SHADE_TREES.size()]
				add_tree(sid, p, rng.randf() * TAU, rng.randf_range(0.8, 1.0), false)
			if edge < 50.0 and rng.randf() < 0.35:
				var q := p + Vector3(rng.randf_range(-3, 3), 0, rng.randf_range(-3, 3))
				q.y = ground(q.x, q.z) - 0.1
				add_prop(smalls[rng.randi() % smalls.size()], Transform3D(basis.scaled(Vector3.ONE * rng.randf_range(0.6, 1.0)), q), 140.0, false, 128.0)
			made += 1
		z += 11.0
	counts["horizon_trees"] = made
