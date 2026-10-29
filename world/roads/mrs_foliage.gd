class_name MrsFoliage
extends Node3D
## Mert Road Studio street trees and planting (v5, docs/roads/FOLIAGE.md).
##
## build(model, opts) instances the street model's `trees[]` (species, pos, yaw, scale) and `plants[]`
## (id, pos, yaw, scale) - Blender Z-up records, Godot = (x, z, -y) - as MultiMeshes per (asset, level, cell),
## adds trunk colliders and returns counts. Same landscape-kit meshes as Blender (tools/roads/mrs/game_trees.py):
##   LOD0       assets/landscape/<sid>.glb                          (detailed leaf cards, bark)
##   LOD1       assets/roads/foliage/<sid>_lod1.glb                 (40 % of the LOD0 cards grown x1.45, decimated
##                                                                   bark; the LOD0 textures and shading)
##   impostor   assets/roads/foliage/impostor_{albedo,normal}.png  (hemi-octahedral, 8 x 8 views per species)
##   plants     assets/landscape/{garden,yard}.glb (hedge / boxwood with the regraded assets/roads/foliage textures)
## Materials: world/roads/mrs_foliage.gdshader / mrs_foliage_impostor.gdshader (the Blender v5 shading model,
## mip-compensated alpha test + alpha-to-coverage, dithered LOD crossfades measured from the main camera, also in
## shadow passes). LOD0 <-> LOD1 switches per 32 m cell (exact node visibility ranges), LOD1 <-> impostor per tree.
##
## opts: "collision" (true)  trunk capsules        "tint" (true)   per-instance colour variation
##       "wind" (1.0)        sway / flutter scale   "force" ("")    "lod0" | "lod1" | "imp": one level everywhere
##       "lod0_end", "lod1_end", "lod0_fade", "lod1_fade"  (m)  override the measured LOD distances
##       "shadows" (true)     everything casts      "shadow_lod1" / "shadow_impostor" / "shadow_plants" (true)
##       "plant_end_tall" / "plant_end_low" (m)     plants taller / lower than 0.8 m fade out there
## Returns {"trees", "plants", "multimeshes", "trunks", "species": {sid: n}, "plant_ids": {id: n}, "lod": {...}}.
## The materials are shared (static): the last build's LOD distances and wind apply to every MrsFoliage.

const LANDSCAPE := "res://assets/landscape/"
const FOLIAGE_DIR := "res://assets/roads/foliage/"
const SHADER := preload("res://world/roads/mrs_foliage.gdshader")
const IMPOSTOR_SHADER := preload("res://world/roads/mrs_foliage_impostor.gdshader")
## Impostor-slot order (game_trees.TREES / CityLandscape.TREES).
const TREES: Array[String] = ["plane_tree", "maple_a", "maple_b", "maple_c", "walnut_spring", "walnut_autumn_a", "walnut_autumn_b",
	"linden_a", "linden_b", "linden_c", "cherry", "grove_a", "grove_b"]
## LOD distances (m) from the harness measurements (docs/roads/FOLIAGE.md): LOD0 keeps the street and the footbridge
## deck detailed; the MRS LOD1 is within 3 % of LOD0 in coverage and 1 % in luminance from 70 m; the impostor within
## 1 % / 1 % at 200 m. Crossfade bands are centred on the distances (LOD0 end: cell distance, LOD1 end: tree distance).
const LOD0_END := 75.0
const LOD0_FADE := 12.0
const LOD1_END := 175.0
const LOD1_FADE := 24.0
const IMPOSTOR_END := 1500.0
const PLANT_END_TALL := 120.0
const PLANT_END_LOW := 60.0
const PLANT_FADE := 12.0
## LOD0 and LOD1 share one grid (the near switch is per cell: exact node ranges, no gaps, no hidden draws);
## impostors use a coarser grid (the far switch is per instance). Cells carry a fixed custom AABB centred
## CELL_LIFT above the node, the point Godot measures visibility ranges to and the shaders' cell distance.
const TREE_CELL := 32.0
const IMP_CELL := 128.0
const PLANT_CELL := 32.0
const LOD_LIFT := 5.0
const TREE_CELL_LIFT := 12.0
const PLANT_CELL_LIFT := 2.0
const TREE_REACH := 10.0
const PLANT_REACH := 2.5
## Materials (game_trees.material_kind): bark | solid (hedge core) | plain | leaves.
const SOLID_FOLIAGE: Array[String] = ["yardleaf_hedge"]
const PLAIN: Array[String] = ["bed_stone", "bed_mulch", "yard_ground", "rock", "plant_Material__1", "plant_Material__6", "plant_Material__13"]
const HEDGE_TEXTURES := {"yardleaf_hedge": "mrs_hedge_leaves.png", "yardleaf_sprays": "mrs_hedge_sprays.png"}
enum Kind { LEAVES, BARK, SOLID, PLAIN }

static var _species: Dictionary = {}     ## sid -> {"lod0": Mesh, "lod1": Mesh, "height", "trunk", "slot", "radius"}
static var _plants: Dictionary = {}      ## plant id -> {"mesh": Mesh, "height": float}
static var _impostor_mesh: ArrayMesh
static var _impostor_material: ShaderMaterial
static var _materials: Dictionary = {}   ## "<material>|<level>" -> ShaderMaterial
static var _impostor_meta: Dictionary = {}

var groups: Dictionary = {}              ## key -> {"mesh", "begin", "end", "shadow", "xf", "cust", "asset", "cell", "lift", ...}
var counts: Dictionary = {}
var trunks: StaticBody3D
var rng := RandomNumberGenerator.new()
var lod := {"lod0_end": LOD0_END, "lod0_fade": LOD0_FADE, "lod1_end": LOD1_END, "lod1_fade": LOD1_FADE}

func _init() -> void:
	name = "MrsFoliage"
	rng.seed = 51921

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func kind(material_name: String) -> Kind:
	var n := material_name.get_slice(".", 0)
	if n.ends_with("_bark") or n.to_lower().contains("trunk"):
		return Kind.BARK
	if n in SOLID_FOLIAGE:
		return Kind.SOLID
	if n in PLAIN or n.begins_with("rock") or n.begins_with("yard_"):
		return Kind.PLAIN
	return Kind.LEAVES

# ----------------------------------------------------------------------------- assets

## A v5 material for an imported kit material at a LOD level (-1 = none, plants), cached.
static func material(src: BaseMaterial3D, level: int, sid: String) -> ShaderMaterial:
	var mname := src.resource_name if src != null else "none"
	var key := "%s|%d" % [mname.get_slice(".", 0), level]
	if _materials.has(key):
		return _materials[key] as ShaderMaterial
	var k := kind(mname)
	var m := ShaderMaterial.new()
	m.shader = SHADER
	var tex: Texture2D = src.albedo_texture if src != null else null
	var base := mname.get_slice(".", 0)
	if HEDGE_TEXTURES.has(base):
		var path: String = FOLIAGE_DIR + str(HEDGE_TEXTURES[base])
		if ResourceLoader.exists(path):
			tex = load(path) as Texture2D
	if tex != null:
		m.set_shader_parameter("albedo_tex", tex)
	m.set_shader_parameter("has_albedo", tex != null)
	if src != null:
		m.set_shader_parameter("base_color", src.albedo_color)
	if k == Kind.BARK and src != null and src.normal_enabled and src.normal_texture != null:
		m.set_shader_parameter("normal_tex", src.normal_texture)
		m.set_shader_parameter("use_normal_map", true)
	var cut := k == Kind.LEAVES and src != null and src.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.set_shader_parameter("kind", 0 if cut else (1 if k == Kind.BARK else (2 if k == Kind.SOLID or k == Kind.LEAVES else 3)))
	m.set_shader_parameter("roughness", 0.9 if k == Kind.BARK or k == Kind.PLAIN else (0.85 if k == Kind.SOLID else 0.78))
	m.set_shader_parameter("ao_strength", 0.0 if k == Kind.PLAIN or base.begins_with("plant_") else 1.0)
	var sway_k := 0.034 if sid.begins_with("linden") else 0.022
	var h: float = float(_species.get(sid, {}).get("height", 1.0)) if sid != "" else 1.0
	m.set_shader_parameter("sway", h * sway_k if sid != "" and _species.has(sid) else 0.0)
	m.set_shader_parameter("lod_level", level)
	m.set_shader_parameter("lod_lift", LOD_LIFT)
	_materials[key] = m
	return m

## A copy of a kit mesh with v5 materials for one LOD level. `names` maps surfaces without their own
## material to a source material by name (the MRS LOD1 GLBs carry untextured stand-ins named like LOD0's).
static func with_materials(source: Mesh, level: int, sid: String, by_name: Dictionary = {}) -> Mesh:
	var mesh := source.duplicate() as Mesh
	for s in mesh.get_surface_count():
		var src := mesh.surface_get_material(s) as BaseMaterial3D
		if src != null and by_name.has(src.resource_name.get_slice(".", 0)):
			src = by_name[src.resource_name.get_slice(".", 0)] as BaseMaterial3D
		mesh.surface_set_material(s, material(src, level, sid))
	return mesh

static func load_assets() -> void:
	if not _species.is_empty():
		return
	var mf := FileAccess.open(FOLIAGE_DIR + "impostors.json", FileAccess.READ)
	if mf:
		_impostor_meta = JSON.parse_string(mf.get_as_text()) as Dictionary
	var imp_species: Dictionary = _impostor_meta.get("species", {}) as Dictionary
	for sid in TREES:
		var root: Node = (load(LANDSCAPE + sid + ".glb") as PackedScene).instantiate()
		var lod0_node := root.find_child("LOD0", true, false) as MeshInstance3D
		var holder: Node = lod0_node.get_parent()
		var extras: Dictionary = holder.get_meta("extras", {}) as Dictionary if holder.has_meta("extras") else {}
		var h: float = float(extras.get("height", 10.0))
		_species[sid] = {"height": h, "trunk": clampf(float(extras.get("trunk_radius", 0.25)), 0.12, 0.45),
			"slot": TREES.find(sid), "crown": float(extras.get("crown_radius", 3.0))}
		var by_name: Dictionary = {}
		for s in lod0_node.mesh.get_surface_count():
			var m := lod0_node.mesh.surface_get_material(s) as BaseMaterial3D
			if m != null:
				by_name[m.resource_name.get_slice(".", 0)] = m
		(_species[sid] as Dictionary)["lod0"] = with_materials(lod0_node.mesh, 0, sid)
		var l1_path := FOLIAGE_DIR + sid + "_lod1.glb"
		var lod1_mesh: Mesh = lod0_node.mesh
		if ResourceLoader.exists(l1_path):
			var l1root: Node = (load(l1_path) as PackedScene).instantiate()
			var l1 := l1root.find_children("*", "MeshInstance3D", true, false)
			if not l1.is_empty():
				lod1_mesh = (l1[0] as MeshInstance3D).mesh
			l1root.free()
		(_species[sid] as Dictionary)["lod1"] = with_materials(lod1_mesh, 1, sid, by_name)
		var aabb: AABB = lod0_node.mesh.get_aabb()
		(_species[sid] as Dictionary)["aabb"] = aabb
		var im: Dictionary = imp_species.get(sid, {}) as Dictionary
		(_species[sid] as Dictionary)["radius"] = float(im.get("radius", aabb.size.length() * 0.5))
		root.free()
	for file in ["garden", "yard"]:
		var scene: Node = (load(LANDSCAPE + file + ".glb") as PackedScene).instantiate()
		for node in scene.find_children("*", "MeshInstance3D", true, false):
			var mi := node as MeshInstance3D
			var extras: Dictionary = mi.get_meta("extras", {}) as Dictionary if mi.has_meta("extras") else {}
			var h: float = float(extras.get("height", mi.mesh.get_aabb().size.y))
			_plants[str(mi.name)] = {"mesh": with_materials(mi.mesh, -1, ""), "height": h}
		scene.free()
	_build_impostor()

static func _build_impostor() -> void:
	if _impostor_meta.is_empty() or not ResourceLoader.exists(FOLIAGE_DIR + str(_impostor_meta.get("albedo", ""))):
		return
	var m := ShaderMaterial.new()
	m.shader = IMPOSTOR_SHADER
	m.set_shader_parameter("albedo_atlas", load(FOLIAGE_DIR + str(_impostor_meta["albedo"])) as Texture2D)
	m.set_shader_parameter("normal_atlas", load(FOLIAGE_DIR + str(_impostor_meta["normal"])) as Texture2D)
	m.set_shader_parameter("frames", float(_impostor_meta.get("frames", 8)))
	m.set_shader_parameter("grid", float(_impostor_meta.get("grid", 4)))
	m.set_shader_parameter("frame_px", float(_impostor_meta.get("px", 128)))
	m.set_shader_parameter("lod_lift", LOD_LIFT)
	var data := PackedVector4Array()
	data.resize(16)
	var maxr := 1.0
	for sid: String in (_impostor_meta.get("species", {}) as Dictionary):
		var sd: Dictionary = (_impostor_meta["species"] as Dictionary)[sid] as Dictionary
		var c: Array = sd["centre"] as Array
		data[int(sd["slot"])] = Vector4(float(c[0]), float(c[1]), float(c[2]), float(sd["radius"]))
		maxr = maxf(maxr, float(sd["radius"]) + Vector3(float(c[0]), float(c[1]), float(c[2])).length())
	m.set_shader_parameter("species", data)
	_impostor_material = m
	# one quad; the shader places it (camera / light facing) - the AABB covers any species at scale 1.4
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var uvs: Array[Vector2] = [Vector2(0, 0), Vector2(1, 0), Vector2(1, 1), Vector2(0, 0), Vector2(1, 1), Vector2(0, 1)]
	for uv in uvs:
		st.set_uv(uv)
		st.set_normal(Vector3.BACK)
		st.add_vertex(Vector3(uv.x - 0.5, 0.5 - uv.y, 0.0))
	_impostor_mesh = st.commit()
	_impostor_mesh.surface_set_material(0, m)
	var r := maxr * 1.4
	_impostor_mesh.custom_aabb = AABB(Vector3(-r, -1.0, -r), Vector3(2.0 * r, 2.0 * r + 1.0, 2.0 * r))

static func species(sid: String) -> Dictionary:
	load_assets()
	return _species.get(sid, {}) as Dictionary

static func plant(id: String) -> Dictionary:
	load_assets()
	return _plants.get(id, {}) as Dictionary

## LOD bands on every v5 material (shared materials: the last build's distances win).
static func set_lod_bands(bands: Vector4) -> void:
	for k: String in _materials:
		var m := _materials[k] as ShaderMaterial
		m.set_shader_parameter("lod_bands", bands)
	if _impostor_material:
		_impostor_material.set_shader_parameter("lod_bands", bands)

static func set_wind(strength: float) -> void:
	for k: String in _materials:
		(_materials[k] as ShaderMaterial).set_shader_parameter("wind", strength)

# ----------------------------------------------------------------------------- instancing

## Queues an instance into the (asset, cell) group. Node visibility range [rng_begin, rng_end] (end -1: none,
## -2: plant fade); lift > 0 makes a "cell" group (fixed custom AABB centred lift above the node: exact ranges).
func queue(asset: String, mesh: Mesh, xf: Transform3D, cell: float, rng_begin: float, rng_end: float, shadow: bool, custom: Color, lift: float = 0.0, reach: float = 0.0) -> void:
	var c := Vector2i(floori(xf.origin.x / cell), floori(xf.origin.z / cell))
	var key := "%s|%d|%d" % [asset, c.x, c.y]
	if not groups.has(key):
		var xs: Array[Transform3D] = []
		var cs: Array[Color] = []
		groups[key] = {"mesh": mesh, "begin": rng_begin, "end": rng_end, "shadow": shadow, "xf": xs, "cust": cs, "asset": asset,
			"cell": cell, "lift": lift, "reach": reach, "ground": xf.origin.y,
			"centre": Vector3((float(c.x) + 0.5) * cell, 0.0, (float(c.y) + 0.5) * cell)}
	var gq: Dictionary = groups[key]
	gq["ground"] = minf(float(gq["ground"]), xf.origin.y)
	((groups[key] as Dictionary)["xf"] as Array[Transform3D]).append(xf)
	((groups[key] as Dictionary)["cust"] as Array[Color]).append(custom)

func tint_color(on: bool) -> Color:
	if not on:
		return Color(0.5, 0.5, 0.5, 0.0)
	var v := rng.randf_range(-0.06, 0.06)
	return Color(0.5 + v + rng.randf_range(-0.02, 0.02), 0.5 + v + rng.randf_range(-0.03, 0.03), 0.5 + v, 0.0)

## Builds every tree / plant of the street model. Returns counts.
func build(model: Dictionary, opts: Dictionary = {}) -> Dictionary:
	load_assets()
	for k: String in ["lod0_end", "lod0_fade", "lod1_end", "lod1_fade"]:
		if opts.has(k):
			lod[k] = float(opts[k])
	var force := str(opts.get("force", ""))
	var tint_on := bool(opts.get("tint", true))
	var shadows := bool(opts.get("shadows", true))
	var shadow_lod1 := bool(opts.get("shadow_lod1", true))
	var shadow_imp := bool(opts.get("shadow_impostor", true))
	var shadow_plants := bool(opts.get("shadow_plants", true))
	var e0: float = float(lod["lod0_end"])
	var f0: float = float(lod["lod0_fade"])
	var e1: float = float(lod["lod1_end"])
	var f1: float = float(lod["lod1_fade"])
	# a forced level: bands that put every distance in that level
	match force:
		"lod0": set_lod_bands(Vector4(1e7, 1.0, 2e7, 1.0))
		"lod1": set_lod_bands(Vector4(-1e7, 1.0, 1e7, 1.0))
		"imp": set_lod_bands(Vector4(-2e7, 1.0, -1e7, 1.0))
		_: set_lod_bands(Vector4(e0, f0, e1, f1))
	set_wind(float(opts.get("wind", 1.0)))
	if bool(opts.get("collision", true)):
		trunks = StaticBody3D.new()
		trunks.name = "TreeTrunks"
		add_child(trunks)
	var nt := 0
	var per_species: Dictionary = {}
	for t: Variant in model.get("trees", []) as Array:
		var td: Dictionary = t as Dictionary
		var sid := str(td.get("species", ""))
		var sp: Dictionary = species(sid)
		if sp.is_empty():
			continue
		var sc: float = float(td.get("scale", 1.0))
		var at := g(td["pos"] as Array)
		var yaw: float = float(td.get("yaw", 0.0))
		var xf := Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * sc), at)
		var custom := tint_color(tint_on)
		var forced := force != ""
		var slack := TREE_CELL * 0.71 + TREE_REACH          # per-instance far band on a cell node: AABB centre to tree
		if force == "" or force == "lod0":
			queue(sid + "_0", sp.lod0 as Mesh, xf, TREE_CELL, 0.0, -1.0 if forced else e0 + f0 * 0.5 + 1.0, shadows, custom, TREE_CELL_LIFT, TREE_REACH)
		if force == "" or force == "lod1":
			queue(sid + "_1", sp.lod1 as Mesh, xf, TREE_CELL, 0.0 if forced else maxf(0.0, e0 - f0 * 0.5 - 1.0),
				-1.0 if forced else e1 + f1 * 0.5 + slack, shadows and shadow_lod1, custom, TREE_CELL_LIFT, TREE_REACH)
		if (force == "" or force == "imp") and _impostor_mesh != null:
			var ci := custom
			ci.a = (float(sp.slot) + 0.1) / 255.0
			queue("impostor", _impostor_mesh, xf, IMP_CELL, 0.0 if forced else maxf(0.0, e1 - f1 * 0.5 - IMP_CELL * 0.71 - TREE_REACH),
				-1.0 if forced else IMPOSTOR_END, shadows and shadow_imp, ci)
		if trunks:
			var shape := CollisionShape3D.new()
			var cap := CapsuleShape3D.new()
			cap.radius = clampf(float(sp.trunk) * sc, 0.14, 0.42)
			cap.height = 3.5
			shape.shape = cap
			shape.position = at + Vector3(0, 1.75, 0)
			trunks.add_child(shape)
		per_species[sid] = int(per_species.get(sid, 0)) + 1
		nt += 1
	var np := 0
	var per_plant: Dictionary = {}
	var end_tall: float = float(opts.get("plant_end_tall", PLANT_END_TALL))
	var end_low: float = float(opts.get("plant_end_low", PLANT_END_LOW))
	for p: Variant in model.get("plants", []) as Array:
		var pd: Dictionary = p as Dictionary
		var id := str(pd.get("id", ""))
		var pr: Dictionary = plant(id)
		if pr.is_empty():
			continue
		var xf2 := Transform3D(Basis(Vector3.UP, float(pd.get("yaw", 0.0))).scaled(Vector3.ONE * float(pd.get("scale", 1.0))), g(pd["pos"] as Array))
		var tall: bool = float(pr.get("height", 0.5)) > 0.8
		queue("plant_" + id + ("_tall" if tall else ""), pr.mesh as Mesh, xf2, PLANT_CELL, 0.0, -2.0 if force == "" else -1.0,
			tall and shadows and shadow_plants, tint_color(tint_on), PLANT_CELL_LIFT, PLANT_REACH)
		per_plant[id] = int(per_plant.get(id, 0)) + 1
		np += 1
	var mm := flush(end_tall, end_low)
	counts = {"trees": nt, "plants": np, "multimeshes": mm, "species": per_species, "plant_ids": per_plant,
		"trunks": trunks.get_child_count() if trunks else 0,
		"lod": {"lod0_end": e0, "lod0_fade": f0, "lod1_end": e1, "lod1_fade": f1, "impostor_end": IMPOSTOR_END,
			"plant_end_tall": end_tall, "plant_end_low": end_low, "plant_fade": PLANT_FADE, "force": force,
			"shadows": {"lod0": shadows, "lod1": shadows and shadow_lod1, "impostor": shadows and shadow_imp, "plants_tall": shadows and shadow_plants}}}
	return counts

## One MultiMeshInstance3D per (asset, cell), placed at its cell centre (instance transforms relative to it).
## "cell" groups (LOD0 / LOD1 / plants) get a fixed custom AABB centred `lift` above the node: Godot measures the
## node visibility range to that point and the shaders' cell distance uses the same point, so the ranges are exact
## (the dithered band inside them is the crossfade). Impostors keep their own AABB with a slack range (their band is
## per instance). Plants (end -2) get a per-distance copy of their materials with the fade band and the kit's sway.
func flush(end_tall: float, end_low: float) -> int:
	var n := 0
	var plant_mats: Dictionary = {}
	for key: String in groups:
		var gd: Dictionary = groups[key]
		var xs: Array[Transform3D] = gd["xf"] as Array[Transform3D]
		var cs: Array[Color] = gd["cust"] as Array[Color]
		var centre: Vector3 = gd["centre"] as Vector3
		centre.y = float(gd["ground"])
		var mesh: Mesh = gd["mesh"] as Mesh
		var end: float = float(gd["end"])
		var asset := str(gd["asset"])
		var lift: float = float(gd["lift"])
		if end == -2.0:
			var tall := asset.ends_with("_tall")
			var pend := end_tall if tall else end_low
			var mkey := "%s|%d" % [asset, int(pend)]
			if not plant_mats.has(mkey):
				var pid := asset.trim_prefix("plant_").trim_suffix("_tall")
				var ph: float = float((_plants.get(pid, {}) as Dictionary).get("height", 1.0))
				var pm := mesh.duplicate() as Mesh
				for s in pm.get_surface_count():
					var m := (pm.surface_get_material(s) as ShaderMaterial).duplicate() as ShaderMaterial
					m.set_shader_parameter("fade_end", Vector2(pend, PLANT_FADE))
					m.set_shader_parameter("sway", ph * 0.022)
					pm.surface_set_material(s, m)
				plant_mats[mkey] = pm
			mesh = plant_mats[mkey] as Mesh
			end = pend + PLANT_FADE * 0.5 + 1.0
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = mesh
		mm.instance_count = xs.size()
		for i in xs.size():
			var xf: Transform3D = xs[i]
			xf.origin -= centre
			mm.set_instance_transform(i, xf)
			mm.set_instance_custom_data(i, cs[i])
		var node := MultiMeshInstance3D.new()
		node.name = key.replace("|", "_")
		node.multimesh = mm
		node.position = centre
		if lift > 0.0:
			var hw: float = float(gd["cell"]) * 0.5 + float(gd["reach"])
			node.custom_aabb = AABB(Vector3(-hw, 0.0, -hw), Vector3(2.0 * hw, 2.0 * lift, 2.0 * hw))
			node.set_instance_shader_parameter("cell_point", centre + Vector3(0.0, lift, 0.0))
		if end > 0.0:
			node.visibility_range_begin = float(gd["begin"])
			node.visibility_range_end = end
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if bool(gd["shadow"]) else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.set_meta("asset", asset)
		add_child(node)
		n += 1
	groups.clear()
	return n
