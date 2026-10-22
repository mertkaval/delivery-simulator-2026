extends SceneTree
## City conflict audit: every static, non-residential piece of the city as it is placed in the
## game (kit buildings by module, downtown, restaurants and their interiors, shops, the Cedar House
## and its furnishing, monuments, streets kit / signals / LED boards, signage, street furniture,
## roads, sidewalks and curbs, landscape), in world space. Run WITHOUT --headless: the dummy
## renderer keeps no MultiMesh instance data.
##
##   (a) COPLANAR  overlapping faces of different parts / materials / objects that lie within
##       TOL (1.5 cm) of each other and within 10 degrees: same facing, or either facing when one
##       side is double-sided, keyed per plane direction. Tiers: "fight" (closer than the depth
##       buffer resolves over the pair's visible range: 1 mm to 150 m, 3 mm to 400 m) and "near"
##       (up to 1.5 cm, same facing, different objects, with no solid's underside sealing the
##       gap). Reported only: "near_intra" (inside one model), "near_opposite" (faces turned
##       against each other 3 mm+ apart - one always faces away), "same_material", "hidden"
##       (capped / covered by another opaque face) and undersides at ground level.
##   (b) PIERCING  one object passing through another's surface (walls through walls, boards /
##       plates / signs in facades, planters / benches / trees in walls or roofs, furniture in
##       walls / counters, props inside props): crossing depth on both sides > PIERCE (2 cm).
##   (c) DECALS    paint, road markings, text and other surface decals must stand MIN_LIFT above
##       the surface they cover (1-3 mm depending on how far they are drawn).
##   (d) LOD       pieces of different LOD / massing ranges visible at the same distance that
##       overlap coplanar (as in (a)), and LOD partners whose switch distances disagree.
## Residential houses / yards / lanes (HouseInstancer "Residences") belong to the houses pass:
## they are loaded as context, only pairs with a non-residential piece are judged, and those are
## listed in "res:" tables (fixed on the residential side), not failed here.
## Failing: per label pair (all its instances) 0.02 m2 of visible fighting between different
## objects; 0.25 m2 inside one placed model ("_intra": an imported prop's or one GLB's own parts);
## any piercing between different objects. Everything is listed down to 4 cm2.
## Optional user args after "--": "verbose" prints every finding.

const TOL := 0.015
const COS_TOL := 0.98481          # cos(10 deg)
const FIGHT := 0.003
const PIERCE := 0.02
const SINK := 0.08                # items may stand up to 8 cm into a floor / paving slab
const AREA_MIN := 0.0004          # per piece pair, m2 (2 x 2 cm): reported
const AREA_FAIL := 0.02           # per label pair, all instances (a 14 x 14 cm patch): failed
## Inside one placed model (an imported prop's own parts, one GLB's materials): authored geometry,
## fixed in the asset (tools/separate_coincident.py, find_zfighting.py); failed from a quarter m2.
const AREA_FAIL_INTRA := 0.25
const CELL := 8.0                 # broad-phase cell, m
const GRID := 0.5                 # per-mesh triangle grid, m
const EXCLUDE_ROOTS := ["CityTraffic", "CityLife", "Animals", "Weather", "CityVFX", "StreetVFX", "GrassMeadows"]
## Downtown kit assets that are surface decals (paint / covers flush with the paving).
const DECAL_ASSETS := ["crosswalk", "lane_dash", "stop_line", "turn_arrow", "manhole", "storm_drain"]
const BUILDERS := ["KitBuildings", "Restaurants", "RainlineDowntown", "StreetGrid", "TrafficCircles", "CurvedRoads", "StreetSignage",
	"StreetFurniture", "Monuments", "Buses", "TrafficSignals", "LedBoards", "Landscape", "CedarHome", "Residences", "StreetCollisions"]
static var DISPLAY := RegEx.create_from_string("(?i)jetta|ace11|hatchback|sedan|scooter|bicycle|helmet|glove|backpack|delivery_bag")
## Vehicle models (parked cars, the campus fleet, the buses): their own GLB internals belong to the
## vehicle production pass; only their placement against the city is judged here.
static var VEHICLE := RegEx.create_from_string("(?i)bus_body|bus_door|bus_wheel|bus_glass|fire_engine|school_bus|ambulance|police|reuse_(sedan|suv|van|pickup|hatchback|taxi|compact|bicycle)|living_.*(car|truck|van)|scooter|bicycle")

## Triangle soup of one mesh in its local space, bucketed in a coarse grid.
class MeshData:
	var tris := PackedVector3Array()      # 3 per triangle
	var surf := PackedInt32Array()        # surface index per triangle
	var grid := {}                        # Vector3i -> PackedInt32Array
	var big := PackedInt32Array()         # triangles too large for the grid
	var count := 0
	var aabb := AABB()
	var surfaces := 0

var checks := 0
var failed := 0
var verbose := false
var meshes := {}                      # Mesh -> MeshData
# Parts (one mesh at one transform), parallel arrays.
var p_mesh: Array[MeshData] = []
var p_xf: Array[Transform3D] = []
var p_aabb: Array[AABB] = []
var p_label: PackedStringArray = []   # builder:asset
var p_mats: Array[PackedInt32Array] = []      # material id per surface
var p_matname: Array[PackedStringArray] = []
var p_double: Array[PackedByteArray] = []
var p_decal: Array[PackedByteArray] = []
var p_res := PackedByteArray()        # 1 = residential (houses pass)
var p_begin := PackedFloat32Array()
var p_end := PackedFloat32Array()
var p_kind := PackedStringArray()     # "arch" (building shell), "item", "ground", "foliage", "label"
var p_group := PackedInt32Array()     # kit building index (modules of one building), else -1
var p_solid := PackedByteArray()      # 1 = opaque surfaces (can hide what is behind it)
var p_obj := PackedInt32Array()       # object id: material parts of one asset instance share it
var obj_ids := {}
var mat_ids := {}
var cells := {}
var bounds := Rect2(-130, -725, 790, 800)   # the city (the horizon forest outside is skipped)
var area_filter := Rect2()                  # optional "x0,z0,x1,z1" user arg: audit one area
var timing := {}
var probe := ""   # user arg "probe=<text>": print the geometry of findings whose label contains it
var probed := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

# ------------------------------------------------------------------------------------ collection

func mesh_data(mesh: Mesh) -> MeshData:
	if meshes.has(mesh): return meshes[mesh]
	var md := MeshData.new()
	md.surfaces = mesh.get_surface_count()
	for s in range(md.surfaces):
		if mesh is ArrayMesh and (mesh as ArrayMesh).surface_get_primitive_type(s) != Mesh.PRIMITIVE_TRIANGLES: continue
		var arrays := mesh.surface_get_arrays(s)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		var n := idx.size() if idx.size() > 0 else verts.size()
		for k in range(0, n - 2, 3):
			var a := verts[idx[k] if idx.size() > 0 else k]
			var b := verts[idx[k + 1] if idx.size() > 0 else k + 1]
			var c := verts[idx[k + 2] if idx.size() > 0 else k + 2]
			if (c - a).cross(b - a).length_squared() < 1e-10: continue
			md.tris.append(a); md.tris.append(b); md.tris.append(c)
			md.surf.append(s)
	md.count = md.surf.size()
	if md.count > 0:
		md.aabb = AABB(md.tris[0], Vector3.ZERO)
		for v in md.tris: md.aabb = md.aabb.expand(v)
	for t in range(md.count):
		var a := md.tris[t * 3]
		var lo := a.min(md.tris[t * 3 + 1]).min(md.tris[t * 3 + 2])
		var hi := a.max(md.tris[t * 3 + 1]).max(md.tris[t * 3 + 2])
		var c0 := Vector3i((lo / GRID).floor())
		var c1 := Vector3i((hi / GRID).floor())
		if (c1.x - c0.x + 1) * (c1.y - c0.y + 1) * (c1.z - c0.z + 1) > 64:
			md.big.append(t)
			continue
		for x in range(c0.x, c1.x + 1):
			for y in range(c0.y, c1.y + 1):
				for z in range(c0.z, c1.z + 1):
					var key := Vector3i(x, y, z)
					if not md.grid.has(key): md.grid[key] = PackedInt32Array()
					var list: PackedInt32Array = md.grid[key]
					list.append(t)
					md.grid[key] = list
	meshes[mesh] = md
	return md

func material_id(mat: Material, fallback: String) -> int:
	var key: Variant = mat if mat != null else fallback
	if not mat_ids.has(key): mat_ids[key] = mat_ids.size() + 1
	return mat_ids[key]

func material_name(mat: Material, fallback: String) -> String:
	if mat == null: return fallback
	if mat.resource_name != "": return mat.resource_name
	if mat is ShaderMaterial and (mat as ShaderMaterial).shader != null:
		return (mat as ShaderMaterial).shader.resource_path.get_file().get_basename()
	if mat is StandardMaterial3D:
		var sm := mat as StandardMaterial3D
		if sm.albedo_texture != null and sm.albedo_texture.resource_path != "": return sm.albedo_texture.resource_path.get_file().get_basename()
		return "#" + sm.albedo_color.to_html(false)
	return mat.get_class()

func is_double(mat: Material) -> bool:
	if mat is BaseMaterial3D: return (mat as BaseMaterial3D).cull_mode == BaseMaterial3D.CULL_DISABLED
	if mat is ShaderMaterial and (mat as ShaderMaterial).shader != null:
		return (mat as ShaderMaterial).shader.code.contains("cull_disabled")
	return false

func is_paint(mat: Material) -> bool:
	return mat is ShaderMaterial and (mat as ShaderMaterial).shader != null and (mat as ShaderMaterial).shader.resource_path.ends_with("road_paint.gdshader")

func is_foliage(mat: Material) -> bool:
	if mat is ShaderMaterial and (mat as ShaderMaterial).shader != null:
		var path := (mat as ShaderMaterial).shader.resource_path
		return path.contains("foliage") or path.contains("conifer")
	if mat is BaseMaterial3D: return (mat as BaseMaterial3D).transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	return false

func is_clear(mat: Material) -> bool:
	if mat is BaseMaterial3D: return (mat as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED
	return false

func add_part(mesh: Mesh, xf: Transform3D, label: String, mats: Array, residential: bool, begin: float, end: float, decal_all: bool, kind: String, group: int = -1, obj_key: String = "") -> void:
	var box := xf * mesh.get_aabb()
	if not bounds.intersects(Rect2(box.position.x, box.position.z, box.size.x, box.size.z)): return
	if area_filter.has_area() and not area_filter.intersects(Rect2(box.position.x, box.position.z, box.size.x, box.size.z).grow(0.5)): return
	var md := mesh_data(mesh)
	if md.count == 0: return
	var foliage := true
	var solid := 0
	for m in mats:
		if not is_foliage(m): foliage = false
		if not is_foliage(m) and not is_clear(m): solid = 1
	if mats.is_empty(): foliage = false
	if kind == "label": solid = 0
	p_mesh.append(md)
	p_xf.append(xf)
	p_aabb.append(xf * md.aabb)
	p_label.append(label)
	var ids := PackedInt32Array()
	var names := PackedStringArray()
	var dbl := PackedByteArray()
	var dec := PackedByteArray()
	# Decals: flat horizontal pieces (paint, plates, joints, covers up to 1.6 cm) and flat pieces in
	# any plane (symbols, stickers, film: under 5 mm thick).
	var wsize := (xf * md.aabb).size
	var thin := wsize.y <= 0.016 or (kind != "arch" and minf(wsize.x, minf(wsize.y, wsize.z)) <= 0.005 and maxf(wsize.x, maxf(wsize.y, wsize.z)) <= 1.2)
	for s in range(md.surfaces):
		var m: Material = mats[s] if s < mats.size() else null
		var nm := material_name(m, "s%d" % s)
		ids.append(material_id(m, label + nm))
		names.append(nm)
		dbl.append(1 if is_double(m) else 0)
		dec.append(1 if (decal_all or is_paint(m) or thin) else 0)
	p_mats.append(ids)
	p_matname.append(names)
	p_double.append(dbl)
	p_decal.append(dec)
	p_res.append(1 if residential else 0)
	p_begin.append(begin)
	p_end.append(end if end > 0.0 else 100000.0)
	p_kind.append("foliage" if foliage else kind)
	p_group.append(group)
	p_solid.append(solid)
	# One object = same builder, same asset (mesh name up to its _Kit<Material> part), same placement.
	var base := label.get_slice("_Kit", 0)
	var ok := obj_key if obj_key != "" else "%s|%s|%s" % [base, str(xf.origin.snapped(Vector3.ONE * 0.002)), str(xf.basis.z.snapped(Vector3.ONE * 0.01))]
	if not obj_ids.has(ok): obj_ids[ok] = obj_ids.size()
	p_obj.append(obj_ids[ok])

func surface_materials(gi: GeometryInstance3D, mesh: Mesh) -> Array:
	var list: Array = []
	for s in range(mesh.get_surface_count()):
		var m: Material = gi.material_override
		if m == null and gi is MeshInstance3D: m = (gi as MeshInstance3D).get_active_material(s)
		if m == null: m = mesh.surface_get_material(s)
		list.append(m)
	return list

var group_assets := {}   # Mesh -> asset name, from the instancers' `groups` (HouseInstancer, StreetFurniture ...)

func learn_groups(node: Node) -> void:
	var groups: Variant = node.get("groups")
	if not groups is Dictionary: return
	for key in groups:
		var data: Variant = groups[key]
		if data is Dictionary and (data as Dictionary).has("piece"):
			var piece: Dictionary = data.piece
			if piece.get("mesh") is Mesh and not group_assets.has(piece.mesh): group_assets[piece.mesh] = str(key).get_slice("|", 0)

func asset_name(gi: GeometryInstance3D, mesh: Mesh) -> String:
	if gi.has_meta("prop"): return str(gi.get_meta("prop"))
	if gi.has_meta("asset"): return str(gi.get_meta("asset"))
	if mesh != null and group_assets.has(mesh): return group_assets[mesh]
	var n := str(gi.name)
	if gi is MultiMeshInstance3D and mesh != null and mesh.resource_name != "": return mesh.resource_name
	if not n.begins_with("@") and not n.begins_with("MeshInstance3D") and not n.begins_with("MultiMeshInstance3D"):
		var parent := gi.get_parent()
		if parent != null and not str(parent.name).begins_with("@") and parent.get_parent() != null and parent.get_parent().get_parent() != root.get_child(0): return "%s/%s" % [parent.name, n]
		return n
	if mesh != null and mesh.resource_name != "": return mesh.resource_name
	if mesh is BoxMesh: return "box"
	if mesh is QuadMesh or mesh is PlaneMesh: return "quad"
	var parent2 := gi.get_parent()
	if parent2 != null and not str(parent2.name).begins_with("@"): return str(parent2.name)
	return gi.get_class()

func excluded(node: Node, top: Node) -> bool:
	if str(top.name) in EXCLUDE_ROOTS: return true
	var p: Node = node
	while p != null and p != top.get_parent():
		if p is PhysicsBody3D and not p is StaticBody3D: return true
		if p is Skeleton3D or p is TableService: return true
		if p is Node3D and p.get_script() != null and str((p.get_script() as Script).get_global_name()) in ["LivingCitizen", "LivingPerson"]: return true
		p = p.get_parent()
	return false

func label_mesh(l: Label3D) -> ArrayMesh:
	var box := l.get_aabb()
	if box.size.x < 0.001 or box.size.y < 0.001: return null
	var am := ArrayMesh.new()
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	var a := Vector3(box.position.x, box.position.y, 0)
	var b := Vector3(box.end.x, box.position.y, 0)
	var c := Vector3(box.end.x, box.end.y, 0)
	var d := Vector3(box.position.x, box.end.y, 0)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([a, c, b, a, d, c])   # clockwise = front +Z
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return am

func collect(world: Node3D) -> void:
	var kit: KitBuilder = world.get_node_or_null("KitBuildings")
	for top in world.get_children():
		var nodes: Array = []
		if top is GeometryInstance3D: nodes.append(top)
		nodes.append_array(top.find_children("*", "GeometryInstance3D", true, false))
		learn_groups(top)
		var residential := str(top.name) == "Residences"
		if DISPLAY.search(str(top.name)) != null: continue   # shop display goods (vehicles, gear)
		var builder := str(top.name) if str(top.name) in BUILDERS else "Neighborhood"
		var prefix := "" if builder != "Neighborhood" or str(top.name).begins_with("@") else str(top.name) + "/"
		for node in nodes:
			var gi := node as GeometryInstance3D
			if not gi.is_visible_in_tree() or excluded(gi, top): continue
			if gi is GPUParticles3D or gi is CPUParticles3D: continue
			# Kit buildings are judged by module (KitBuilder.recorded) instead of merged meshes.
			if top == kit and gi.visibility_range_begin == 0.0 and gi is MeshInstance3D: continue
			var begin := gi.visibility_range_begin
			var end := gi.visibility_range_end
			if gi is Label3D:
				var lm := label_mesh(gi as Label3D)
				if lm == null: continue
				var lab := gi as Label3D
				var lmat := StandardMaterial3D.new()
				lmat.cull_mode = BaseMaterial3D.CULL_DISABLED if lab.double_sided else BaseMaterial3D.CULL_BACK
				lmat.resource_name = "Label3D"
				add_part(lm, gi.global_transform, "%s:label'%s'" % [builder, lab.text.left(18).replace("\n", " ")], [lmat], residential, begin, end, true, "label")
				continue
			if gi is MultiMeshInstance3D:
				var mm: MultiMesh = (gi as MultiMeshInstance3D).multimesh
				if mm == null or mm.mesh == null: continue
				var mats := surface_materials(gi, mm.mesh)
				var asset := asset_name(gi, mm.mesh)
				var decal: bool = asset in DECAL_ASSETS
				# Batched kit / prop pieces (DowntownDistrict, StreetFurniture: one MultiMesh per asset piece
				# and 64 m cell, instances appended in placement order): the k-th instance of every piece
				# of an asset in a cell is the same placed object.
				var cell := Vector2i.ZERO
				if mm.instance_count > 0:
					var o0 := (gi.global_transform * mm.get_instance_transform(0)).origin
					cell = Vector2i(floori(o0.x / 64.0), floori(o0.z / 64.0))
				for k in range(mm.instance_count):
					var key := "%s|%s|%d|%d|%d" % [builder, asset, cell.x, cell.y, k] if gi.has_meta("prop") else ""
					add_part(mm.mesh, gi.global_transform * mm.get_instance_transform(k), "%s:%s%s" % [builder, prefix, asset], mats, residential, begin, end, decal, kind_of(builder, asset), -1, key + "|%d" % int(begin) if key != "" else "")
			elif gi is MeshInstance3D and (gi as MeshInstance3D).mesh != null:
				var mi := gi as MeshInstance3D
				var mats2 := surface_materials(gi, mi.mesh)
				if mats2.size() > 0 and mats2[0] is ShaderMaterial and (mats2[0] as ShaderMaterial).shader != null and (mats2[0] as ShaderMaterial).shader.resource_path.contains("terrain_transition"): continue
				var asset2 := asset_name(gi, mi.mesh)
				# Nodes of one instanced model (a GLB scene: the Cedar House, a shop, a prop) are one object.
				var owner_key := "owner%d" % gi.owner.get_instance_id() if gi.owner != null and gi.owner != world else ""
				add_part(mi.mesh, gi.global_transform, "%s:%s%s" % [builder, prefix, asset2], mats2, residential, begin, end, str(gi.name).begins_with("StopLine_"), kind_of(builder, asset2), -1, owner_key)
	if kit != null:
		for r in kit.recorded:
			var mesh: Mesh = r[2]
			var mats3: Array = []
			for s in range(mesh.get_surface_count()):
				var src := mesh.surface_get_material(s)
				mats3.append(CityKit.material(src.resource_name) if src != null else null)
			add_part(mesh, r[3], "KitBuildings:%s" % r[1], mats3, false, 0.0, KitBuilder.NEAR_END, false, "arch", int(r[0]))

func kind_of(builder: String, asset: String) -> String:
	if builder in ["StreetGrid", "TrafficCircles", "CurvedRoads"]: return "ground"
	if builder == "Residences": return "arch" if asset.begins_with("house_") else "item"
	if builder == "KitBuildings": return "arch"
	if builder == "Neighborhood" and (asset.begins_with("box") or asset.contains("ground") or asset.contains("ParkGravel") or asset.contains("Lawn")): return "ground"
	if builder == "Neighborhood" and (asset.begins_with("Restaurant_") or asset.begins_with("store_")): return "arch"
	if builder == "CedarHome" and (asset.begins_with("Architecture") or asset.begins_with("Garden") or asset.begins_with("Interior") or asset.begins_with("Roof")): return "arch"
	if builder == "Restaurants":
		for prefix in ["rs_floor", "rs_ceiling", "rs_back", "rs_wall", "rs_pass", "rs_door", "rs_plain"]:
			if asset.begins_with(prefix): return "arch"
	if builder == "RainlineDowntown":
		for prefix in ["road_segment", "sidewalk", "alley_pavement", "curb"]:
			if asset.begins_with(prefix): return "ground"
		for prefix in ["bay_", "storefront_", "entrance_", "blank_wall", "plain_wall", "roof_slab", "parapet", "interior_slab", "cornice", "impostor", "parking_bay", "garage_entry", "loading_door", "living_hospital", "living_school", "living_fire_station"]:
			if asset.begins_with(prefix): return "arch"
	return "item"

# ------------------------------------------------------------------------------------ geometry

## World triangles of part `i` whose bounds touch `region` (world AABB):
## [verts (3 per tri), normals, surface index, aabb min, aabb max].
func world_tris(i: int, region: AABB) -> Array:
	var md := p_mesh[i]
	var xf := p_xf[i]
	var local := xf.affine_inverse() * region
	var picked := {}
	var c0 := Vector3i((local.position / GRID).floor())
	var c1 := Vector3i((local.end / GRID).floor())
	var cells := (c1.x - c0.x + 1) * (c1.y - c0.y + 1) * (c1.z - c0.z + 1)
	var out_v := PackedVector3Array()
	var out_n := PackedVector3Array()
	var out_s := PackedInt32Array()
	var out_lo := PackedVector3Array()
	var out_hi := PackedVector3Array()
	var candidates := PackedInt32Array()
	if cells > md.grid.size():
		for t in range(md.count): candidates.append(t)
	else:
		for x in range(c0.x, c1.x + 1):
			for y in range(c0.y, c1.y + 1):
				for z in range(c0.z, c1.z + 1):
					var key := Vector3i(x, y, z)
					if md.grid.has(key):
						for t in md.grid[key]:
							if not picked.has(t):
								picked[t] = true
								candidates.append(t)
		for t in md.big: candidates.append(t)
	for t in candidates:
		var a := xf * md.tris[t * 3]
		var b := xf * md.tris[t * 3 + 1]
		var c := xf * md.tris[t * 3 + 2]
		var lo := a.min(b).min(c)
		var hi := a.max(b).max(c)
		if hi.x < region.position.x or lo.x > region.end.x or hi.y < region.position.y or lo.y > region.end.y or hi.z < region.position.z or lo.z > region.end.z: continue
		var n := (c - a).cross(b - a)
		if n.length_squared() < 1e-12: continue
		out_v.append(a); out_v.append(b); out_v.append(c)
		out_n.append(n.normalized())
		out_s.append(md.surf[t])
		out_lo.append(lo)
		out_hi.append(hi)
	return [out_v, out_n, out_s, out_lo, out_hi]

## Overlap of triangle (a0,a1,a2) with triangle (b0,b1,b2) projected on A's plane:
## [area, centroid] or [] when they do not overlap.
static func overlap(a0: Vector3, a1: Vector3, a2: Vector3, na: Vector3, b0: Vector3, b1: Vector3, b2: Vector3) -> Array:
	var u := (a1 - a0).normalized()
	var v := na.cross(u)
	var poly := PackedVector2Array([Vector2.ZERO, Vector2((a1 - a0).dot(u), (a1 - a0).dot(v)), Vector2((a2 - a0).dot(u), (a2 - a0).dot(v))])
	var clip := PackedVector2Array([Vector2((b0 - a0).dot(u), (b0 - a0).dot(v)), Vector2((b1 - a0).dot(u), (b1 - a0).dot(v)), Vector2((b2 - a0).dot(u), (b2 - a0).dot(v))])
	if (clip[1] - clip[0]).cross(clip[2] - clip[0]) < 0.0: clip = PackedVector2Array([clip[0], clip[2], clip[1]])
	if (poly[1] - poly[0]).cross(poly[2] - poly[0]) < 0.0: poly = PackedVector2Array([poly[0], poly[2], poly[1]])
	for e in range(3):
		var p := clip[e]
		var q := clip[(e + 1) % 3]
		var edge := q - p
		var next := PackedVector2Array()
		var count := poly.size()
		if count == 0: return []
		for k in range(count):
			var cur := poly[k]
			var prev := poly[(k + count - 1) % count]
			var cin := edge.cross(cur - p) >= 0.0
			var pin := edge.cross(prev - p) >= 0.0
			if cin:
				if not pin: next.append(intersect(prev, cur, p, q))
				next.append(cur)
			elif pin:
				next.append(intersect(prev, cur, p, q))
		poly = next
	if poly.size() < 3: return []
	var area := 0.0
	var cx := Vector2.ZERO
	for k in range(poly.size()):
		var p0 := poly[k]
		var p1 := poly[(k + 1) % poly.size()]
		var cr := p0.cross(p1)
		area += cr
		cx += (p0 + p1) * cr
	if absf(area) < 1e-9: return []
	cx /= (3.0 * area)
	return [absf(area) * 0.5, a0 + u * cx.x + v * cx.y]

static func intersect(a: Vector2, b: Vector2, p: Vector2, q: Vector2) -> Vector2:
	var r := b - a
	var s := q - p
	var den := r.cross(s)
	if absf(den) < 1e-12: return a
	return a + r * ((p - a).cross(s) / den)

## Coplanar overlaps between parts i and j (j == i: between different surfaces of one part).
## Returns [[surface_i, surface_j, area, separation, same_facing], ...].
func coplanar(i: int, j: int) -> Array:
	var region := p_aabb[i].grow(TOL).intersection(p_aabb[j].grow(TOL))
	var ta := world_tris(i, region)
	if (ta[2] as PackedInt32Array).is_empty(): return []
	var tb := ta if i == j else world_tris(j, region)
	if (tb[2] as PackedInt32Array).is_empty(): return []
	var av: PackedVector3Array = ta[0]
	var an: PackedVector3Array = ta[1]
	var as_: PackedInt32Array = ta[2]
	var alo: PackedVector3Array = ta[3]
	var ahi: PackedVector3Array = ta[4]
	var bv: PackedVector3Array = tb[0]
	var bn: PackedVector3Array = tb[1]
	var bs: PackedInt32Array = tb[2]
	var blo: PackedVector3Array = tb[3]
	var bhi: PackedVector3Array = tb[4]
	var mi := p_mats[i]
	var mj := p_mats[j]
	var di := p_double[i]
	var dj := p_double[j]
	var hits := {}
	for x in range(as_.size()):
		var lo := alo[x] - Vector3.ONE * TOL
		var hi := ahi[x] + Vector3.ONE * TOL
		var na := an[x]
		# Undersides at ground level (slab and box bottoms) can't be seen from anywhere.
		if na.y < -0.7 and ahi[x].y < 0.4: continue
		var start := x + 1 if i == j else 0
		for y in range(start, bs.size()):
			if i == j and mi[as_[x]] == mj[bs[y]]: continue
			if blo[y].x > hi.x or bhi[y].x < lo.x or blo[y].y > hi.y or bhi[y].y < lo.y or blo[y].z > hi.z or bhi[y].z < lo.z: continue
			var dot := na.dot(bn[y])
			if absf(dot) < COS_TOL: continue
			if bn[y].y < -0.7 and bhi[y].y < 0.4: continue
			var same := dot > 0.0
			if not same and di[as_[x]] == 0 and dj[bs[y]] == 0: continue
			var a0 := av[x * 3]
			# Quick plane distance reject: B's vertices against A's plane.
			var d0 := na.dot(bv[y * 3] - a0)
			var d1 := na.dot(bv[y * 3 + 1] - a0)
			var d2 := na.dot(bv[y * 3 + 2] - a0)
			if minf(d0, minf(d1, d2)) > TOL or maxf(d0, maxf(d1, d2)) < -TOL: continue
			var ov := overlap(a0, av[x * 3 + 1], av[x * 3 + 2], na, bv[y * 3], bv[y * 3 + 1], bv[y * 3 + 2])
			if ov.is_empty() or float(ov[0]) < 1e-6: continue
			# Signed: where A's overlap lies relative to B's plane (along B's normal).
			var sd := bn[y].dot((ov[1] as Vector3) - bv[y * 3])
			var sep := absf(sd)
			if sep > TOL: continue
			# Keyed by surface pair, facing and plane direction (26 buckets): the end faces, tops and
			# bottoms of one pair of surfaces are separate findings with their own normal and gap.
			var key := Vector4i(as_[x], bs[y], 1 if same else 0, (roundi(na.x * 1.4) + 1) * 9 + (roundi(na.y * 1.4) + 1) * 3 + roundi(na.z * 1.4) + 1)
			var h: Array = hits.get(key, [0.0, 1.0, [], na])
			h[0] = float(h[0]) + float(ov[0])
			h[1] = minf(float(h[1]), sep)
			var pts: Array = h[2]
			# Up to 6 sample points (area-weighted): the overlap centroids of the largest pieces.
			if pts.size() < 6: pts.append([ov[1], float(ov[0]), sd])
			else:
				var smallest := 0
				for q in range(pts.size()):
					if float(pts[q][1]) < float(pts[smallest][1]): smallest = q
				if float(ov[0]) > float(pts[smallest][1]): pts[smallest] = [ov[1], float(ov[0]), sd]
			hits[key] = h
	var out: Array = []
	for key in hits:
		var h: Array = hits[key]
		var points: Array = []
		var gaps: Array = []
		for q in h[2]:
			points.append(q[0])
			gaps.append(q[2])
		out.append([key.x, key.y, h[0], h[1], key.z == 1, points, h[3], gaps])
	return out

## Crossing depth of part j through the surfaces of part i: for every plane of i (quantised normal
## and offset), the vertices of j that project onto one of its triangles within 0.6 m - and more than
## PIERCE inside the outline of that plane's face (a slab tucked 1 cm into a wall puts the wall's
## foot 1 cm inside the slab's edge: grazing, not crossing); the depth is min(furthest in front,
## furthest behind) - how far j sticks through on both sides. Returns [depth, where].
func crossing(ta: Array, tb: Array) -> Array:
	var av: PackedVector3Array = ta[0]
	var an: PackedVector3Array = ta[1]
	var alo: PackedVector3Array = ta[3]
	var ahi: PackedVector3Array = ta[4]
	var bv: PackedVector3Array = tb[0]
	if av.is_empty() or bv.is_empty(): return [0.0, Vector3.ZERO]
	# Vertices of j bucketed by 0.5 m cell (deduplicated).
	var grid := {}
	var seen := {}
	for v in bv:
		var q := Vector3i((v * 1000.0).round())
		if seen.has(q): continue
		seen[q] = true
		var c := Vector3i((v / 0.5).floor())
		if not grid.has(c): grid[c] = PackedVector3Array()
		var l: PackedVector3Array = grid[c]
		l.append(v)
		grid[c] = l
	var edge_count := {}
	for t in range(an.size()):
		var pk0 := plane_key(an[t], av[t * 3])
		for e in range(3):
			var ek := edge_key(pk0, av[t * 3 + e], av[t * 3 + (e + 1) % 3])
			edge_count[ek] = int(edge_count.get(ek, 0)) + 1
	var planes := {}   # plane key -> [front, behind, where]
	for t in range(an.size()):
		var n := an[t]
		var a := av[t * 3]
		var b := av[t * 3 + 1]
		var c3 := av[t * 3 + 2]
		var outline: Array[int] = []
		var pk := plane_key(n, a)
		for e in range(3):
			if int(edge_count.get(edge_key(pk, av[t * 3 + e], av[t * 3 + (e + 1) % 3]), 0)) == 1: outline.append(e)
		var lo := alo[t] - Vector3.ONE * 1.0
		var hi := ahi[t] + Vector3.ONE * 1.0
		var c0 := Vector3i((lo / 0.5).floor())
		var c1 := Vector3i((hi / 0.5).floor())
		if (c1.x - c0.x + 1) * (c1.y - c0.y + 1) * (c1.z - c0.z + 1) > 4096: continue
		var v0 := c3 - a
		var v1 := b - a
		var d00 := v0.dot(v0)
		var d01 := v0.dot(v1)
		var d11 := v1.dot(v1)
		var den := d00 * d11 - d01 * d01
		if absf(den) < 1e-12: continue
		# Per triangle (a plane's far-apart triangles used to pool their front and behind vertices:
		# a dishwasher in its cabinet gap 'crossed' the cabinet run's front).
		var rec: Array = [0.0, 0.0, Vector3.ZERO, n]
		var changed := false
		for x in range(c0.x, c1.x + 1):
			for y in range(c0.y, c1.y + 1):
				for z in range(c0.z, c1.z + 1):
					var key := Vector3i(x, y, z)
					if not grid.has(key): continue
					for v: Vector3 in grid[key]:
						var d := n.dot(v - a)
						if absf(d) > 0.6: continue
						var v2 := v - n * d - a
						var d20 := v2.dot(v0)
						var d21 := v2.dot(v1)
						var u := (d11 * d20 - d01 * d21) / den
						var w := (d00 * d21 - d01 * d20) / den
						# Strictly inside (a vertex resting on a face's edge - a register on a counter top
						# whose end face ends at the same height - does not cross it).
						if u < 0.002 or w < 0.002 or u + w > 0.998: continue
						if not outline.is_empty():
							var on_face := v - n * d
							var grazing := false
							for e: int in outline:
								if Geometry3D.get_closest_point_to_segment(on_face, av[t * 3 + e], av[t * 3 + (e + 1) % 3]).distance_to(on_face) < PIERCE: grazing = true
							if grazing: continue
						if d > float(rec[0]): rec[0] = d; changed = true
						if -d > float(rec[1]):
							rec[1] = -d
							rec[2] = v
							changed = true
		if changed: planes[t] = rec
	var best := 0.0
	var where := Vector3.ZERO
	for k in planes:
		var r: Array = planes[k]
		var depth := minf(float(r[0]), float(r[1]))
		# Resting on a floor / paving / counter top: feet and bases may sink up to SINK into an
		# upward surface (hidden inside the slab) - that is not a visible conflict.
		if (r[3] as Vector3).y > 0.9 and float(r[1]) <= SINK: continue
		if depth > best:
			best = depth
			where = r[2]
	return [best, where]

static func plane_key(n: Vector3, a: Vector3) -> Vector4i:
	return Vector4i(roundi(n.x * 50), roundi(n.y * 50), roundi(n.z * 50), roundi(n.dot(a) * 50))

static func edge_key(pk: Vector4i, p: Vector3, q: Vector3) -> String:
	var a := Vector3i((p * 1000.0).round())
	var b := Vector3i((q * 1000.0).round())
	if b < a:
		var t := a
		a = b
		b = t
	return "%s|%s|%s" % [pk, a, b]

## Piercing between parts i and j: max crossing depth either way.
func pierce(i: int, j: int) -> Array:
	var region := p_aabb[i].intersection(p_aabb[j])
	if region.size.x < PIERCE and region.size.y < PIERCE and region.size.z < PIERCE: return [0.0, Vector3.ZERO]
	region = region.grow(1.0)
	var ta := world_tris(i, region)
	var tb := world_tris(j, region)
	var r1 := crossing(ta, tb)
	var r2 := crossing(tb, ta)
	return r1 if float(r1[0]) >= float(r2[0]) else r2

# ------------------------------------------------------------------------------------ findings

var findings := {}   # category -> {label -> [area/depth, count, min_sep, where, builder]}

func note(cat: String, label: String, amount: float, sep: float, where: Vector3) -> void:
	# A pair with a residential piece (house, yard, lane, residential tree / pole, the lots'
	# mailboxes HouseInstancer places) is the houses pass's to fix on its side: reported in its own
	# "res:" table, not failed here.
	if (label.contains("Residences:") or label.contains(":mailbox_")) and cat in ["a_fight", "a_near", "b_pierce", "b_buried", "c_decal", "d_lod"]: cat = "res:" + cat
	if not findings.has(cat): findings[cat] = {}
	var table: Dictionary = findings[cat]
	var f: Array = table.get(label, [0.0, 0, 1e9, where])
	f[0] = float(f[0]) + amount
	f[1] = int(f[1]) + 1
	if sep < float(f[2]):
		f[2] = sep
		f[3] = where
	table[label] = f

static func min_lift(distance: float) -> float:
	# fix_city_depth_probe: 0.2 mm fights beyond 25 m, 1 mm at 150-250 m, 3 mm clean to 400 m.
	return clampf(distance * 1.0e-5, 0.001, 0.003)

## True when an opaque face (of any part, the pair's own other faces included) facing the same way
## lies in front of `p` along `n`, between `start` (beyond the pair's own separation) and 0.5 m:
## the overlap is capped - a deck over a slab, a plinth over its own footprint, a wall in front
## of a hidden end face.
func covered(p: Vector3, n: Vector3, i: int, j: int, start: float, capped: bool = false) -> bool:
	var a := p + n * start
	var b := p + n * 0.5
	var seg := AABB(a, Vector3.ZERO).expand(b).grow(0.002)
	var key := Vector2i(floori(p.x / CELL), floori(p.z / CELL))
	if not cells.has(key): return false
	var lo_i := minf(p_end[i], p_end[j])
	for k: int in cells[key]:
		if p_solid[k] == 0: continue
		if not p_aabb[k].intersects(seg): continue
		if p_begin[k] >= lo_i or p_end[k] <= maxf(p_begin[i], p_begin[j]): continue
		var t := world_tris(k, seg)
		var v: PackedVector3Array = t[0]
		var nn: PackedVector3Array = t[1]
		for q in range(nn.size()):
			if nn[q].dot(n) < 0.2: continue
			var hit: Variant = Geometry3D.segment_intersects_triangle(a, b, v[q * 3], v[q * 3 + 1], v[q * 3 + 2])
			if hit != null: return true
	# Capped by a solid resting on it (same-facing pairs only): an opposite-facing face of a third
	# part (the underside of the box above, the back of a panel against it) within 4 mm in front of
	# the point seals the overlap.
	if not capped: return false
	var c0 := p - n * 0.001
	var c1 := p + n * 0.004
	var cap := AABB(c0, Vector3.ZERO).expand(c1).grow(0.002)
	for k: int in cells[key]:
		if k == i or k == j or p_solid[k] == 0 or not p_aabb[k].intersects(cap): continue
		if p_begin[k] >= lo_i or p_end[k] <= maxf(p_begin[i], p_begin[j]): continue
		var t2 := world_tris(k, cap)
		var v2: PackedVector3Array = t2[0]
		var n2: PackedVector3Array = t2[1]
		for q in range(n2.size()):
			if n2[q].dot(n) > -0.9: continue
			if Geometry3D.segment_intersects_triangle(c0, c1, v2[q * 3], v2[q * 3 + 1], v2[q * 3 + 2]) != null: return true
	return false

## True when an opaque face turned against `n` (the underside / back of a solid) lies between the
## sample point `p` (on face A) and face B, `gap` behind or in front of it along `n` (1 mm slack).
func sealed(p: Vector3, n: Vector3, gap: float) -> bool:
	var a := p + n * (0.001 if gap > 0.0 else -0.001)
	var b := p - n * (gap + (0.001 if gap > 0.0 else -0.001))
	var seg := AABB(a, Vector3.ZERO).expand(b).grow(0.002)
	var key := Vector2i(floori(p.x / CELL), floori(p.z / CELL))
	if not cells.has(key): return false
	for k: int in cells[key]:
		if p_solid[k] == 0 or not p_aabb[k].intersects(seg): continue
		var t := world_tris(k, seg)
		var v: PackedVector3Array = t[0]
		var nn: PackedVector3Array = t[1]
		for q in range(nn.size()):
			if nn[q].dot(n) > -0.9: continue
			if Geometry3D.segment_intersects_triangle(a, b, v[q * 3], v[q * 3 + 1], v[q * 3 + 2]) != null: return true
	return false

## True when the part holding the front face reaches down to (or into) the back face's plane: an
## object standing on / fixed against that surface (a table's base plate, a bracket), not a sheet
## floating in front of it.
func rests_on(front: int, p: Vector3, n: Vector3, gap: float) -> bool:
	var back := p - n * gap if gap > 0.0 else p
	var box := p_aabb[front]
	var lowest := INF
	for c in range(8):
		lowest = minf(lowest, n.dot(box.get_endpoint(c)))
	return lowest <= n.dot(back) + 0.001

## True when the back face of a same-facing pair lies inside one solid: a face of the solid turned
## along `n` above it (the front face's own part, within the gap) and one turned against `n` below
## it within 10 cm (a table foot's plate set into the paving it stands on).
func buried_back(p: Vector3, n: Vector3, gap: float) -> bool:
	var back := p - n * gap if gap > 0.0 else p
	var up_a := back + n * 0.001
	var up_b := back + n * (absf(gap) + 0.001)
	var down_a := back - n * 0.001
	var down_b := back - n * 0.1
	var seg := AABB(down_b, Vector3.ZERO).expand(up_b).grow(0.002)
	var key := Vector2i(floori(p.x / CELL), floori(p.z / CELL))
	if not cells.has(key): return false
	for k: int in cells[key]:
		if p_solid[k] == 0 or not p_aabb[k].intersects(seg): continue
		var t := world_tris(k, seg)
		var v: PackedVector3Array = t[0]
		var nn: PackedVector3Array = t[1]
		var above := false
		var below := false
		for q in range(nn.size()):
			var d := nn[q].dot(n)
			if d > 0.9 and not above and Geometry3D.segment_intersects_triangle(up_a, up_b, v[q * 3], v[q * 3 + 1], v[q * 3 + 2]) != null: above = true
			elif d < -0.9 and not below and Geometry3D.segment_intersects_triangle(down_a, down_b, v[q * 3], v[q * 3 + 1], v[q * 3 + 2]) != null: below = true
			if above and below: return true
	return false

func judge_pair(i: int, j: int, results: Array) -> void:
	for r in results:
		var si: int = r[0]
		var sj: int = r[1]
		var area: float = r[2]
		var sep: float = r[3]
		var points: Array = r[5]
		var n: Vector3 = r[6]
		if area < AREA_MIN * 0.25: continue
		# Hidden fraction: sample points capped by another opaque part in front.
		var open := 0
		var start := maxf(0.004, sep + 0.003)
		var gaps: Array = r[7] if r.size() > 7 else []
		for g in range(points.size()):
			var q: Vector3 = points[g]
			if covered(q, n, i, j, start, r[4]) or (not r[4] and covered(q, -n, i, j, start, false)): continue
			# Same-facing 3 mm+ apart with a solid's underside between them (a foot, mat, plate or
			# box standing on / mounted against the face behind): the back face is enclosed.
			if r[4] and sep >= FIGHT and g < gaps.size() and (sealed(q, n, float(gaps[g])) or buried_back(q, n, float(gaps[g])) or rests_on(i if float(gaps[g]) > 0.0 else j, q, n, float(gaps[g]))): continue
			open += 1
		var visible := area * float(open) / maxf(1.0, float(points.size()))
		var li := "%s/%s" % [p_label[i], p_matname[i][si]]
		var lj := "%s/%s" % [p_label[j], p_matname[j][sj]]
		var label := "%s <-> %s" % ([li, lj] if li < lj else [lj, li])
		var where: Vector3 = points[0] if not points.is_empty() else p_aabb[i].get_center()
		if probe != "" and label.contains(probe) and probed < 12:
			probed += 1
			print("PROBE %s  area %.4f sep %.4f same %s n %s  points %s  xf_i %s  xf_j %s" % [label, area, sep, r[4], n.snapped(Vector3.ONE * 0.01), str(points.map(func(q): return (q as Vector3).snapped(Vector3.ONE * 0.001))), p_xf[i], p_xf[j]])
		if visible < AREA_MIN * 0.25:
			note("hidden", label, area, sep, where)
			continue
		var lod := p_begin[i] > 0.0 or p_begin[j] > 0.0
		var decal := p_decal[i][si] == 1 or p_decal[j][sj] == 1
		var same_mat := p_mats[i][si] == p_mats[j][sj]
		if same_mat:
			# Same material on both faces (sidewalk over sidewalk, a paint line over the next tile's
			# line): renders the same either way unless the triplanar / vertex AO differs - reported.
			note("a_same_material", label, visible, sep, where)
		elif decal:
			var lift_needed := min_lift(minf(minf(p_end[i], p_end[j]), 400.0))
			if sep < lift_needed: note("c_decal" if p_obj[i] != p_obj[j] else "c_decal_intra", label, visible, sep, where)
			else: note("c_decal_ok", label, visible, sep, where)
		elif lod:
			if p_obj[i] != p_obj[j]: note("d_lod", label, visible, sep, where)
			else: note("d_lod_intra" if sep < FIGHT else "a_near_intra", label, visible, sep, where)
		elif same_mat:
			# Same material on both faces (sidewalk over sidewalk): renders the same either way
			# unless the triplanar / vertex AO differs - reported, fixed where cheap.
			note("a_same_material", label, visible, sep, where)
		elif sep < min_lift(minf(minf(p_end[i], p_end[j]), 400.0)):
			# Closer than the depth buffer resolves over the distance both stay visible to
			# (fix_city_depth_probe: 1 mm to 150 m - interior props end at 30 m -, 3 mm to 400 m).
			note("a_fight" if p_obj[i] != p_obj[j] else "a_fight_intra", label, visible, sep, where)
		elif not r[4]:
			# Turned against each other 3 mm - 1.5 cm apart (a cabinet back against the wall behind
			# it, a slab tucked into a wall): one of the two always faces away from any viewpoint,
			# and the depth buffer separates them beyond 3 mm anyway - reported, not failed.
			note("a_near_opposite", label, visible, sep, where)
		elif p_obj[i] == p_obj[j]:
			# 3 mm - 1.5 cm inside one model (a sign's lettering on its plate, a frame round its
			# glass): clear of the depth-buffer fight (fix_city_depth_probe: 3 mm is clean to
			# 400 m), reported but not failed.
			note("a_near_intra", label, visible, sep, where)
		else:
			note("a_near", label, visible, sep, where)

## Which pairs are judged for piercing.
func pierce_pair(i: int, j: int) -> bool:
	var ki := p_kind[i]
	var kj := p_kind[j]
	if ki == "ground" or kj == "ground": return false
	# Text quads are clear apart from their glyphs: a quad edge through a pole is not visible. Labels
	# are judged for coplanarity (c), for burial (b_buried) and for their lift instead.
	if ki == "label" or kj == "label": return false
	# Flat decals (paint, covers) and trees standing in their own pit grate are not piercing.
	if p_aabb[i].size.y <= 0.03 or p_aabb[j].size.y <= 0.03: return false
	if (p_label[i].ends_with("tree_pit") and p_label[j].contains("birch")) or (p_label[j].ends_with("tree_pit") and p_label[i].contains("birch")): return false
	if p_obj[i] == p_obj[j]: return false
	# Parts of vehicles together, a bicycle in its rack, glow sprites on signal heads.
	if VEHICLE.search(p_label[i]) != null and VEHICLE.search(p_label[j]) != null: return false
	if (p_label[i].contains("bike_rack") and p_label[j].contains("bicycle")) or (p_label[j].contains("bike_rack") and p_label[i].contains("bicycle")): return false
	if p_label[i].contains("/Glow_") or p_label[j].contains("/Glow_"): return false
	if ki == "foliage" and kj == "foliage": return false
	if ki == "foliage" and kj != "arch" or kj == "foliage" and ki != "arch": return false
	# Modules of one kit building interlock by design (trims, sills, balconies set into walls).
	if ki == "arch" and kj == "arch" and p_group[i] >= 0 and p_group[i] == p_group[j]: return false
	if ki == "arch" and kj == "arch" and p_label[i].get_slice(":", 0) == "RainlineDowntown" and p_label[j].get_slice(":", 0) == "RainlineDowntown": return false
	if p_res[i] == 1 and p_res[j] == 1: return false
	if p_label[i] == p_label[j] and p_xf[i].origin.is_equal_approx(p_xf[j].origin): return false
	return true

## Labels and other text must not be buried behind (inside) a facade: centre of the text quad
## behind an opaque face that faces the same way, within 0.3 m.
func buried(i: int) -> bool:
	var c := p_aabb[i].get_center()
	var n := p_xf[i].basis.z.normalized()
	var a := c + n * 0.3
	var seg := AABB(c, Vector3.ZERO).expand(a).grow(0.002)
	var key := Vector2i(floori(c.x / CELL), floori(c.z / CELL))
	for k: int in cells.get(key, PackedInt32Array()):
		if k == i or p_solid[k] == 0 or not p_aabb[k].intersects(seg): continue
		if p_begin[k] >= p_end[i]: continue
		var t := world_tris(k, seg)
		var v: PackedVector3Array = t[0]
		var nn: PackedVector3Array = t[1]
		for q in range(nn.size()):
			if nn[q].dot(n) < 0.7: continue
			if Geometry3D.segment_intersects_triangle(c + n * 0.001, a, v[q * 3], v[q * 3 + 1], v[q * 3 + 2]) != null: return true
	return false

func run() -> void:
	var args := OS.get_cmdline_user_args()
	verbose = "verbose" in args
	for arg in args:
		if arg.begins_with("probe="): probe = arg.trim_prefix("probe=")
		if arg.count(",") == 3:
			var f := arg.split_floats(",")
			area_filter = Rect2(f[0], f[1], f[2] - f[0], f[3] - f[1])
	var t0 := Time.get_ticks_msec()
	KitBuilder.record_parts = true
	var world := CedarNeighborhood.new()
	root.add_child(world)
	for k in range(3): await process_frame
	collect(world)
	print("CONFLICT parts %d, meshes %d (%.1f s)" % [p_mesh.size(), meshes.size(), (Time.get_ticks_msec() - t0) / 1000.0])
	check(p_mesh.size() > (500 if area_filter.has_area() else 50000), "the city was built and collected (%d parts)" % p_mesh.size())
	# Broad phase: parts by 8 m cell; a pair is tested in the cell holding its overlap's min corner.
	for i in range(p_mesh.size()):
		var box := p_aabb[i].grow(TOL)
		var c0 := Vector2i(floori(box.position.x / CELL), floori(box.position.z / CELL))
		var c1 := Vector2i(floori(box.end.x / CELL), floori(box.end.z / CELL))
		for x in range(c0.x, c1.x + 1):
			for z in range(c0.y, c1.y + 1):
				var key := Vector2i(x, z)
				if not cells.has(key): cells[key] = PackedInt32Array()
				var list: PackedInt32Array = cells[key]
				list.append(i)
				cells[key] = list
	# Intra-part: different surfaces of one mesh (judged once per mesh + material set).
	var seen := {}
	for i in range(p_mesh.size()):
		if p_res[i] == 1 or p_mesh[i].surfaces < 2 or p_kind[i] == "foliage" or VEHICLE.search(p_label[i]) != null: continue
		var key := "%d|%s" % [p_mesh[i].get_instance_id(), str(p_mats[i])]
		if seen.has(key): continue
		seen[key] = true
		judge_pair(i, i, coplanar(i, i))
	var cache := {}
	var pcache := {}
	var pairs := 0
	var tested := 0
	var pierced := 0
	for key in cells:
		var list: PackedInt32Array = cells[key]
		for a in range(list.size()):
			var i := list[a]
			var bi := p_aabb[i].grow(TOL)
			for b in range(a + 1, list.size()):
				var j := list[b]
				if p_res[i] == 1 and p_res[j] == 1: continue
				var bj := p_aabb[j]
				if not bi.intersects(bj): continue
				# Visible together? (LOD ranges [begin, end) must overlap.)
				if p_begin[i] >= p_end[j] or p_begin[j] >= p_end[i]: continue
				var inter := bi.intersection(bj.grow(TOL))
				if Vector2i(floori(inter.position.x / CELL), floori(inter.position.z / CELL)) != key: continue
				pairs += 1
				var t1 := Time.get_ticks_usec()
				# Same meshes at the same relative placement give the same answer (downtown modules).
				var rel := p_xf[i].affine_inverse() * p_xf[j]
				var ck := "%d|%d|%s|%s|%s|%s%s%s" % [p_mesh[i].get_instance_id(), p_mesh[j].get_instance_id(), str(p_mats[i]), str(p_mats[j]), str(rel.origin.snapped(Vector3.ONE * 0.001)), str(rel.basis.x.snapped(Vector3.ONE * 0.001)), str(rel.basis.y.snapped(Vector3.ONE * 0.001)), str(rel.basis.z.snapped(Vector3.ONE * 0.001))]
				var res: Array = []
				var both_foliage := p_kind[i] == "foliage" or p_kind[j] == "foliage"
				var vehicle_parts := VEHICLE.search(p_label[i]) != null and VEHICLE.search(p_label[j]) != null
				if not both_foliage and not vehicle_parts:
					if cache.has(ck):
						for r in cache[ck]:
							var copy: Array = (r as Array).duplicate()
							var pts: Array = []
							for q: Vector3 in r[5]: pts.append(p_xf[i] * q)
							copy[5] = pts
							copy[6] = (p_xf[i].basis * (r[6] as Vector3)).normalized()
							res.append(copy)
					else:
						tested += 1
						res = coplanar(i, j)
						var stored: Array = []
						var inv := p_xf[i].affine_inverse()
						for r in res:
							var copy2: Array = (r as Array).duplicate()
							var pts2: Array = []
							for q: Vector3 in r[5]: pts2.append(inv * q)
							copy2[5] = pts2
							copy2[6] = (inv.basis * (r[6] as Vector3)).normalized()
							stored.append(copy2)
						cache[ck] = stored
					judge_pair(i, j, res)
				if pierce_pair(i, j):
					var pr: Array
					if pcache.has(ck):
						pr = [pcache[ck][0], p_xf[i] * (pcache[ck][1] as Vector3)]
					else:
						pierced += 1
						pr = pierce(i, j)
						pcache[ck] = [pr[0], p_xf[i].affine_inverse() * (pr[1] as Vector3)]
					# A balcony slab let a few cm into its facade (through a string course) is how it is
					# fixed to the wall, not a clash.
					var attached: bool = float(pr[0]) <= 0.06 and (p_label[i].ends_with(":balcony") or p_label[j].ends_with(":balcony"))
					if float(pr[0]) > PIERCE and not attached:
						var la := p_label[i]
						var lb := p_label[j]
						# Parts of one model through each other (a mailbox on its post): authored, reported.
						note("b_pierce" if p_obj[i] != p_obj[j] else "b_pierce_intra", "%s <-> %s" % ([la, lb] if la < lb else [lb, la]), float(pr[0]), float(pr[0]), pr[1])
						if probe != "" and (la + lb).contains(probe) and probed < 12:
							probed += 1
							print("PROBE pierce %s <-> %s  depth %.3f at %s  xf_i %s  xf_j %s" % [la, lb, float(pr[0]), pr[1], p_xf[i], p_xf[j]])
				var tk := "%s + %s" % [p_label[i].get_slice(":", 0), p_label[j].get_slice(":", 0)]
				timing[tk] = float(timing.get(tk, 0.0)) + (Time.get_ticks_usec() - t1) / 1e6
	print("CONFLICT broad-phase pairs %d, coplanar tests %d, piercing tests %d (%.1f s)" % [pairs, tested, pierced, (Time.get_ticks_msec() - t0) / 1000.0])
	for i in range(p_mesh.size()):
		if p_kind[i] == "label" and p_res[i] == 0 and buried(i):
			note("b_buried", p_label[i], 1.0, 0.0, p_aabb[i].get_center())
	report()
	var tk2 := timing.keys()
	tk2.sort_custom(func(x, y): return float(timing[x]) > float(timing[y]))
	var line := "CONFLICT time by builder pair:"
	for k in tk2.slice(0, 12): line += "  %s %.0fs" % [k, timing[k]]
	print(line)
	print("CITY CONFLICT %s: %d checks, %d failures (%.0f s)" % ["PASS" if failed == 0 else "FAIL", checks, failed, (Time.get_ticks_msec() - t0) / 1000.0])
	quit(1 if failed else 0)

func report() -> void:
	for cat in ["a_fight", "a_fight_intra", "a_near", "a_near_intra", "a_near_opposite", "a_same_material", "b_pierce", "b_pierce_intra", "b_buried", "c_decal", "c_decal_intra", "d_lod", "d_lod_intra", "c_decal_ok", "hidden",
			"res:a_fight", "res:a_near", "res:b_pierce", "res:b_buried", "res:c_decal", "res:d_lod"]:
		var table: Dictionary = findings.get(cat, {})
		var keys := table.keys()
		keys.sort_custom(func(x, y): return float(table[x][0]) > float(table[y][0]))
		var total := 0.0
		var big := 0
		var per_builder := {}
		var threshold := 0.0 if cat in ["b_pierce", "b_buried"] else AREA_MIN
		var fail_at := 0.0 if cat in ["b_pierce", "b_buried"] else (AREA_FAIL_INTRA if cat.ends_with("_intra") else AREA_FAIL)
		var failing := 0
		for k in keys:
			total += float(table[k][0])
			if float(table[k][0]) >= threshold: big += 1
			if float(table[k][0]) >= fail_at: failing += 1
			var bl := "%s + %s" % [String(k).get_slice(":", 0), String(k).get_slice(" <-> ", 1).get_slice(":", 0)]
			per_builder[bl] = int(per_builder.get(bl, 0)) + int(table[k][1])
		print("== %s: %d label pairs (%d over %.4f m2, %d failing at %.2f m2), %.2f total, %d instances" % [cat, keys.size(), big, threshold, failing, fail_at, total, per_builder.values().reduce(func(acc, v): return acc + v, 0)])
		print("   by builder: ", per_builder)
		var shown := 0 if cat == "hidden" and not verbose else (80 if verbose else 30)
		for k in keys.slice(0, shown):
			var f: Array = table[k]
			print("   %9.4f x%-4d sep %5.1f mm  %s  near %s" % [f[0], f[1], float(f[2]) * 1000.0, k, (f[3] as Vector3).snapped(Vector3.ONE * 0.1)])
		if cat in ["a_fight", "a_fight_intra", "a_near", "b_pierce", "b_buried", "c_decal", "c_decal_intra", "d_lod", "d_lod_intra"]:
			check(failing == 0, "%s: %d label pairs over %.2f m2" % [cat, failing, fail_at])
