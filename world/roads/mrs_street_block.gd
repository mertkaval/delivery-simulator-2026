class_name MrsStreetBlock
extends Node3D
## Loads a Mert Road Studio street-block export (tools/roads/mrs/export.py export_block):
##   <base>.glb            roads, junctions, footbridges, paths, buildings (road surfaces get mrs_road.gdshader:
##                         baked tile + wheel tracks / curb dirt / gutter wetness from COLOR_0 and UV2)
##   <base>_collision.glb  drivable / walkable surfaces, footbridge decks, stairs as inclines, rail walls -> trimesh
##   <base>_props.glb      placed furniture / signs / lights (furniture atlas materials)
##   <base>_signals.glb    signal poles; every head gets its own lens materials so each signal is controllable
##   <base>.json           street model: trees / plants (the game's landscape-kit species, MultiMesh LOD0 /
##                         LOD1 / impostor through CityLandscape), light records (MrsStreetLights), signal
##                         phases, route graphs, footbridge plans, placement items
## Records are Blender Z-up; Godot (x, y, z) = (x, z, -y).

const ROAD_SHADER := preload("res://world/roads/mrs_road.gdshader")
const GROUND_SHADER := preload("res://world/roads/mrs_ground.gdshader")
const StreetLights := preload("res://world/roads/mrs_street_lights.gd")
const LensState := {"red": ["Red", "PedRed", "BikeRed"], "amber": ["Amber", "BikeAmber"], "green": ["Green", "PedGreen", "BikeGreen"]}

var model: Dictionary = {}
var foliage: MrsFoliage
var landscape: CityLandscape       ## v4 planting (plant_v4), kept for before / after comparisons
var street_lights: StreetLights
var collision: StaticBody3D
var signals: Dictionary = {}        ## id -> {"node": Node3D, "lenses": {"Red": [mats], ...}, "phase": int, "junction": String}
var junction_phases: Dictionary = {}   ## junction -> Array of phases (lists of approach indices)
var phase_index: int = 0
var phase_timer: float = 0.0
var cycle_green: float = 12.0
var cycle_amber: float = 3.0
var counts: Dictionary = {}

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func load_glb(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(path, state) != OK:
		push_error("MrsStreetBlock: cannot load " + path)
		return null
	return doc.generate_scene(state) as Node3D

## Builds everything. opts: "trees" (true), "lights" (true), "collision" (true), "max_shadowed" (4),
## "focus" (Vector3), "night" (0..1). Returns counts.
func build(dir: String, base: String, opts: Dictionary = {}) -> Dictionary:
	var f := FileAccess.open(dir.path_join(base + ".json"), FileAccess.READ)
	if f == null:
		push_error("MrsStreetBlock: no " + base + ".json in " + dir)
		return {}
	model = JSON.parse_string(f.get_as_text()) as Dictionary
	var main := load_glb(dir.path_join(base + ".glb"))
	if main:
		main.name = "Roads"
		add_child(main)
		counts["road_shader_surfaces"] = road_materials(main)
		counts["ground"] = ground_material(main, dir)
		counts["kit_surfaces"] = kit_materials(main)
	counts["destinations"] = add_destinations()
	if bool(opts.get("collision", true)):
		var col := load_glb(dir.path_join(base + "_collision.glb"))
		if col:
			counts["collision_shapes"] = make_collision(col)
			col.free()
	var props := load_glb(dir.path_join(base + "_props.glb"))
	if props:
		props.name = "Props"
		add_child(props)
		counts["glass_surfaces"] = glass_materials(props) + (glass_materials(main) if main else 0)
	var sig := load_glb(dir.path_join(base + "_signals.glb"))
	if sig:
		sig.name = "Signals"
		add_child(sig)
		counts["signals"] = setup_signals(sig)
	if bool(opts.get("trees", true)):
		counts.merge(plant_v4() if str(opts.get("foliage", "v5")) == "v4" else plant(), true)
	if bool(opts.get("lights", true)):
		street_lights = StreetLights.new()
		street_lights.name = "StreetLights"
		add_child(street_lights)
		var recs: Array = model.get("lights", []) as Array
		var st: Dictionary = street_lights.build(recs, {"max_shadowed": int(opts.get("max_shadowed", 4)), "focus": opts.get("focus", Vector3.ZERO)})
		street_lights.collect_lamp_materials(self)
		street_lights.set_night(float(opts.get("night", 0.0)))
		counts["lights"] = st
	set_phase(0)
	return counts

## Road asphalt surfaces -> mrs_road.gdshader, keeping the imported baked textures and their UV scale.
func road_materials(root: Node) -> int:
	var n := 0
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if src != null:
				src.vertex_color_use_as_albedo = false      # COLOR_0 carries the road masks, not a colour
				# anisotropic: at grazing angles the paving joints mipped down to dark dots where they cross
				src.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
			if src == null or not src.resource_name.begins_with("MRS_Asphalt"):
				continue
			var m := ShaderMaterial.new()
			m.shader = ROAD_SHADER
			m.set_shader_parameter("albedo_tex", src.albedo_texture)
			m.set_shader_parameter("uv_scale", Vector2(src.uv1_scale.x, src.uv1_scale.y))
			m.set_shader_parameter("uv_offset", Vector2(src.uv1_offset.x, src.uv1_offset.y))
			if src.normal_enabled and src.normal_texture != null:
				m.set_shader_parameter("normal_tex", src.normal_texture)
				m.set_shader_parameter("has_normal", true)
			if src.roughness_texture != null:
				m.set_shader_parameter("rough_tex", src.roughness_texture)
				m.set_shader_parameter("has_rough", true)
			m.set_shader_parameter("roughness_base", src.roughness)
			mi.set_surface_override_material(s, m)
			n += 1
	return n

## Glazing (bus shelter panes, lantern panes, footbridge glass): alpha-blended panes of one mesh are not sorted
## against each other, so a pane seen through another one flickered in and out with the view. A depth pre-pass
## (DEPTH_DRAW_ALWAYS) makes the nearest pane win consistently; both faces stay visible (closed 12 mm boxes).
func glass_materials(root: Node) -> int:
	var n := 0
	var seen := {}
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if m == null or seen.has(m) or m.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
				continue
			if not (m.resource_name.contains("Glass") or m.resource_name.contains("Lens")):
				continue
			seen[m] = true
			m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_ALWAYS
			n += 1
	return n

## City-kit buildings (frontage.py): Kit* surfaces get the game's own materials (CityKit.material: world
## triplanar PBR sets, the downtown window shader for KitGlass). The GLB carries flat "<Kit>_Engine" stand-ins.
func kit_materials(root: Node) -> int:
	var n := 0
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(s)
			if src == null or not src.resource_name.begins_with("Kit"):
				continue
			mi.set_surface_override_material(s, CityKit.material(src.resource_name.trim_suffix("_Engine")))
			n += 1
	return n

## Delivery destinations (shop entrances): Marker3D at the door, facing the street, in group
## "mrs_destinations" with the address / name / service access as metadata.
func add_destinations() -> int:
	var recs: Array = model.get("destinations", []) as Array
	if recs.is_empty():
		return 0
	var holder := Node3D.new()
	holder.name = "Destinations"
	add_child(holder)
	for r: Variant in recs:
		var d: Dictionary = r as Dictionary
		var mk := Marker3D.new()
		mk.name = str(d.get("id", "Destination"))
		var door := g(d.get("door", [0, 0, 0]) as Array)
		var face := g(d.get("facing", [0, -1, 0]) as Array)
		mk.position = door
		if face.length() > 0.01:
			mk.basis = Basis.looking_at(face.normalized(), Vector3.UP)
		for k: String in ["name", "address", "road", "kind"]:
			mk.set_meta(k, d.get(k, ""))
		mk.set_meta("entrance", g(d.get("entrance", [0, 0, 0]) as Array))
		var svc: Dictionary = d.get("service", {}) as Dictionary
		if not svc.is_empty():
			mk.set_meta("service_driveway", g(svc.get("driveway", [0, 0, 0]) as Array))
			mk.set_meta("service_yard", g(svc.get("yard", [0, 0, 0]) as Array))
		mk.add_to_group("mrs_destinations")
		holder.add_child(mk)
	return recs.size()

static func texture_file(path: String, srgb: bool = true) -> Texture2D:
	var img := Image.load_from_file(path)
	if img == null:
		push_warning("MrsStreetBlock: missing texture " + path)
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)

## The landscape ground (ground.py): block mask + grass / soil / worn tiles in mrs_ground.gdshader.
func ground_material(root: Node, dir: String) -> int:
	var rec: Dictionary = model.get("ground", {}) as Dictionary
	if rec.is_empty():
		return 0
	var m := ShaderMaterial.new()
	m.shader = GROUND_SHADER
	var mask_img := Image.load_from_file(dir.path_join(str(rec["mask"])))
	if mask_img != null:
		m.set_shader_parameter("mask_tex", ImageTexture.create_from_image(mask_img))
	var tiles: Dictionary = rec["tiles"] as Dictionary
	for pair: Array in [["GroundGrass", "grass"], ["GroundSoil", "soil"], ["GroundWorn", "worn"]]:
		var maps: Dictionary = tiles.get(pair[0], {}) as Dictionary
		for k: String in ["albedo", "rough", "normal"]:
			var key := "roughness" if k == "rough" else k
			if maps.has(key):
				m.set_shader_parameter("%s_%s" % [pair[1], k], texture_file(dir.path_join(str(maps[key]))))
	m.set_shader_parameter("tile_scale", 1.0 / float(rec.get("tile_size", 4.0)))
	var n := 0
	for node: Node in root.find_children(str(rec["name"]) + "*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			mi.set_surface_override_material(s, m)
		n += 1
	return n

func make_collision(root: Node) -> int:
	collision = StaticBody3D.new()
	collision.name = "Collision"
	add_child(collision)
	var n := 0
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var shape := CollisionShape3D.new()
		var tm := mi.mesh.create_trimesh_shape()
		tm.backface_collision = true
		shape.shape = tm
		shape.transform = mi.transform if mi.get_parent() == root else (mi.get_parent() as Node3D).transform * mi.transform
		collision.add_child(shape)
		n += 1
	return n

## Every signal root gets private copies of its lens materials, so set_signal() controls one signal.
func setup_signals(root: Node) -> int:
	var by_id: Dictionary = {}
	for j: Variant in model.get("junctions", []) as Array:
		var jd: Dictionary = j as Dictionary
		junction_phases[str(jd.get("id", ""))] = jd.get("signal_phases", []) as Array
		for s: Variant in jd.get("signals", []) as Array:
			var sd: Dictionary = s as Dictionary
			by_id[str(sd["id"])] = {"phase": int(sd.get("phase", 0)), "junction": str(jd.get("id", ""))}
	for child: Node in root.find_children("*", "Node3D", true, false):
		# node names get Blender copy suffixes (SB_J4_S0.001 -> SB_J4_S0_001): the id is in the extras
		var extras: Dictionary = child.get_meta("extras", {}) as Dictionary if child.has_meta("extras") else {}
		var id := str(extras.get("mrs_signal_id", ""))
		if id == "":
			var nm := str(child.name)
			var rx := RegEx.create_from_string("^(.*?)(_\\d{3})?$")
			var mt := rx.search(nm)
			id = mt.get_string(1) if mt else nm
		if not by_id.has(id) or signals.has(id):
			continue
		var lenses: Dictionary = {}
		for node: Node in child.find_children("*", "MeshInstance3D", true, false):
			var mi := node as MeshInstance3D
			for s in mi.mesh.get_surface_count():
				var src := mi.mesh.surface_get_material(s) as BaseMaterial3D
				if src == null or not src.resource_name.begins_with("MRS_Lens_"):
					continue
				var key := src.resource_name.trim_prefix("MRS_Lens_")
				var m := src.duplicate() as BaseMaterial3D
				m.set_meta("on_color", src.emission if src.emission_enabled else src.albedo_color)
				mi.set_surface_override_material(s, m)
				if not lenses.has(key):
					lenses[key] = []
				(lenses[key] as Array).append(m)
		signals[id] = {"node": child, "lenses": lenses, "phase": int(by_id[id]["phase"]), "junction": by_id[id]["junction"]}
	return signals.size()

## state: "red" | "amber" | "green" for the vehicle head; pedestrian heads show green only with "green".
func set_signal(id: String, state: String) -> void:
	if not signals.has(id):
		return
	var lenses: Dictionary = (signals[id] as Dictionary)["lenses"] as Dictionary
	for key: String in lenses:
		var on := false
		for s: String in LensState:
			if key in (LensState[s] as Array):
				on = s == state or (s == "red" and state == "amber" and key.begins_with("Ped"))
		for m: Variant in lenses[key] as Array:
			var bm := m as BaseMaterial3D
			bm.emission_enabled = true
			bm.emission = bm.get_meta("on_color", Color.WHITE) as Color
			bm.emission_energy_multiplier = 6.0 if on else 0.0
			bm.albedo_color = (bm.get_meta("on_color", Color.WHITE) as Color) * (1.0 if on else 0.12)

## Phase k green for every junction (signals of other phases red): the documented non-conflicting sequence.
func set_phase(k: int) -> void:
	phase_index = k
	for id: String in signals:
		var sd: Dictionary = signals[id]
		var phases: Array = junction_phases.get(sd["junction"], []) as Array
		var active: int = k % maxi(phases.size(), 1)
		set_signal(id, "green" if int(sd["phase"]) == active else "red")

func green_count() -> int:
	var n := 0
	for id: String in signals:
		var lenses: Dictionary = (signals[id] as Dictionary)["lenses"] as Dictionary
		for m: Variant in lenses.get("Green", []) as Array:
			if (m as BaseMaterial3D).emission_energy_multiplier > 0.0:
				n += 1
				break
	return n

func _process(delta: float) -> void:
	if signals.is_empty():
		return
	phase_timer += delta
	if phase_timer > cycle_green + cycle_amber:
		phase_timer = 0.0
		set_phase(phase_index + 1)
	elif phase_timer > cycle_green:
		for id: String in signals:
			var sd: Dictionary = signals[id]
			var phases: Array = junction_phases.get(sd["junction"], []) as Array
			if int(sd["phase"]) == phase_index % maxi(phases.size(), 1):
				set_signal(id, "amber")

## Trees and plants: MrsFoliage (v5, world/roads/mrs_foliage.gd): the game's landscape-kit species with Blender-matched
## leaf shading, MRS LOD1 meshes and hemi-octahedral impostors on shared LOD grids (no gaps / pops), plant
## MultiMeshes and trunk capsule colliders. `opts` passes through (lod bands, shadows, force a level ...).
func plant(opts: Dictionary = {}) -> Dictionary:
	foliage = MrsFoliage.new()
	foliage.name = "Foliage"
	add_child(foliage)
	return foliage.build(model, opts)

## v4 planting: trees and plants through the game's CityLandscape kit directly (kit LOD1 + kit impostors).
func plant_v4() -> Dictionary:
	CityLandscape.load_assets()
	landscape = CityLandscape.new()
	add_child(landscape)
	var trunks := StaticBody3D.new()
	trunks.name = "TreeTrunks"
	add_child(trunks)
	var nt := 0
	for t: Variant in model.get("trees", []) as Array:
		var td: Dictionary = t as Dictionary
		var sid := str(td["species"])
		var sp: Dictionary = CityLandscape.species(sid)
		if sp.is_empty():
			continue
		var sc: float = float(td.get("scale", 1.0))
		var at := g(td["pos"] as Array)
		var yaw: float = float(td.get("yaw", 0.0))
		var xf := Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * sc), at)
		var custom := landscape.tint()
		var end0 := snappedf(clampf(float(sp.height) * 3.0, 26.0, 42.0), 2.0)
		landscape.queue(sid + "_0", sp.lod0, xf, CityLandscape.LOD0_CELL, 0.0, end0, true, custom)
		landscape.queue(sid + "_1", sp.lod1, xf, CityLandscape.LOD1_CELL, end0, CityLandscape.TREE_FAR_BEGIN, false, custom)
		var cimp := custom
		cimp.a = (float(sp.slot) + 0.1) / 255.0
		landscape.queue("impostor", CityLandscape._impostor, Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * float(sp.far) * sc), at),
			CityLandscape.FAR_CELL, CityLandscape.TREE_FAR_BEGIN, CityLandscape.FAR_END, false, cimp)
		var shape := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = clampf(float(sp.trunk) * sc, 0.14, 0.42)
		cap.height = 3.5
		shape.shape = cap
		shape.position = at + Vector3(0, 1.75, 0)
		trunks.add_child(shape)
		nt += 1
	var np := 0
	for p: Variant in model.get("plants", []) as Array:
		var pd: Dictionary = p as Dictionary
		var pr: Dictionary = CityLandscape.prop(str(pd["id"]))
		if pr.is_empty():
			continue
		var xf2 := Transform3D(Basis(Vector3.UP, float(pd.get("yaw", 0.0))).scaled(Vector3.ONE * float(pd.get("scale", 1.0))), g(pd["pos"] as Array))
		var tall: bool = float(pr.get("height", 0.5)) > 0.8
		landscape.queue(str(pd["id"]), pr.mesh, xf2, 32.0, 0.0, 90.0 if tall else 45.0, tall, landscape.tint())
		np += 1
	landscape.flush()
	return {"trees": nt, "plants": np, "multimeshes": landscape.get_child_count()}
