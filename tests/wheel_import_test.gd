extends SceneTree
## G4 wheel assembly checkpoint: Godot import contract (hierarchy, pivot, axle axis,
## concentric spin, triangle counts vs handoff, material slots, LOD1 offset).
## usage: godot --headless --path . --script res://tests/wheel_import_test.gd
const GLB := "res://world/vehicles/production/checkpoints/G4_wheel_v0.4/wheel_assembly.glb"
const HANDOFF := "res://world/vehicles/production/reports/g4_wheel_handoff.json"
const SPIN_MESHES: Array[String] = ["Tyre", "RimBarrel", "RimFace", "CentreCap", "LugNuts", "BrakeDisc"]
const STATIC_MESHES: Array[String] = ["Caliper", "DustShield"]
const MATERIALS: Array[String] = ["Rubber", "Alloy", "RimWell", "Chrome", "SteelDisc", "CaliperDark", "RubberCut"]
var failed := 0
var checks := 0

func check(ok: bool, text: String) -> void:
	checks += 1
	print(("  ok   " if ok else "  FAIL ") + text)
	if not ok: failed += 1

func _initialize() -> void:
	call_deferred("run")

## Imported PackedScene when the editor import exists; otherwise the runtime glTF loader
## (same GLTFDocument parser, no .import options applied). The checkpoint folder currently
## ships a .blend next to the GLB, which aborts `godot --headless --import` for the whole
## project (Blender importer query fails without a Blender path), so no .import is produced.
func load_wheel(path: String) -> Node3D:
	if ResourceLoader.exists(path, "PackedScene"):
		print("Loading imported PackedScene")
		return (load(path) as PackedScene).instantiate()
	print("No editor import for the GLB; loading through GLTFDocument at runtime")
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		printerr("GLTFDocument.append_from_file failed: ", err)
		return null
	return doc.generate_scene(state) as Node3D

func tri_count(mi: MeshInstance3D) -> int:
	var total := 0
	for s in range(mi.mesh.get_surface_count()):
		var arrays: Array = mi.mesh.surface_get_arrays(s)
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if idx.size() > 0: total += idx.size() / 3
		else: total += (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return total

## AABB of every mesh under `pivot`, expressed in the pivot's parent space.
func group_aabb(pivot: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for mi in pivot.find_children("*", "MeshInstance3D", true, false):
		var xf: Transform3D = pivot.transform * (mi as MeshInstance3D).transform
		var local: AABB = (mi as MeshInstance3D).mesh.get_aabb()
		for i in range(8):
			var p := xf * local.get_endpoint(i)
			if first:
				box = AABB(p, Vector3.ZERO)
				first = false
			else: box = box.expand(p)
	return box

func fmt(v: Vector3) -> String:
	return "(%.4f, %.4f, %.4f)" % [v.x, v.y, v.z]

func run() -> void:
	var handoff: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(HANDOFF))
	var model: Node3D = load_wheel(GLB)
	check(model != null, "GLB loads (imported PackedScene, or runtime GLTFDocument fallback): " + GLB)
	if model == null:
		finish()
		return
	root.add_child(model)
	print("Scene root: ", model.name, " (", model.get_class(), ")")
	# --- hierarchy ---
	var expected: Array[String] = ["WheelR", "WheelPivot", "HubStatic", "WheelR_LOD1", "WheelPivot_LOD1", "HubStatic_LOD1"]
	for n in SPIN_MESHES + STATIC_MESHES:
		expected.append(n)
		expected.append(n + "_LOD1")
	var missing: Array[String] = []
	for n in expected:
		if model.find_child(n, true, false) == null: missing.append(n)
	check(missing.is_empty(), "All %d expected node names present (missing: %s)" % [expected.size(), str(missing)])
	var wheel_r: Node3D = model.find_child("WheelR", true, false)
	var pivot: Node3D = model.find_child("WheelPivot", true, false)
	var hub: Node3D = model.find_child("HubStatic", true, false)
	var lod1: Node3D = model.find_child("WheelR_LOD1", true, false)
	if pivot == null or hub == null or wheel_r == null:
		finish()
		return
	check(pivot is Node3D and not pivot is MeshInstance3D, "WheelPivot is a plain Node3D (%s)" % pivot.get_class())
	check(hub is Node3D and not hub is MeshInstance3D, "HubStatic is a plain Node3D (%s)" % hub.get_class())
	check(pivot.get_parent() == wheel_r, "WheelPivot parent is WheelR (%s)" % pivot.get_parent().name)
	check(hub.get_parent() == pivot.get_parent(), "HubStatic is a sibling of WheelPivot (parent %s)" % hub.get_parent().name)
	for n in SPIN_MESHES:
		var m: Node = model.find_child(n, true, false)
		check(m is MeshInstance3D and m.get_parent() == pivot, "%s is a MeshInstance3D directly under WheelPivot" % n)
	for n in STATIC_MESHES:
		var m: Node = model.find_child(n, true, false)
		check(m is MeshInstance3D and m.get_parent() == hub, "%s is a MeshInstance3D directly under HubStatic" % n)
	check(pivot.transform.is_equal_approx(Transform3D.IDENTITY), "WheelPivot rests at identity (origin %s)" % fmt(pivot.position))
	check(hub.transform.is_equal_approx(Transform3D.IDENTITY), "HubStatic rests at identity (origin %s)" % fmt(hub.position))
	# --- axle axis: Tyre AABB thinnest on X ---
	var tyre: MeshInstance3D = model.find_child("Tyre", true, false)
	var tb: AABB = tyre.mesh.get_aabb()
	print("Tyre AABB size ", fmt(tb.size), " centre ", fmt(tb.get_center()), " node xform ", tyre.transform)
	check(tyre.transform.is_equal_approx(Transform3D.IDENTITY), "Tyre mesh node has identity transform (no baked rotation)")
	check(tb.size.x < tb.size.y and tb.size.x < tb.size.z, "Tyre thinnest dimension is local X (axle = X)")
	check(absf(tb.size.x - 0.225) < 0.005, "Tyre width %.4f m (expect 0.225)" % tb.size.x)
	check(absf(tb.size.y - 0.66) < 0.005 and absf(tb.size.z - 0.66) < 0.005, "Tyre diameter Y %.4f / Z %.4f m (expect 0.66)" % [tb.size.y, tb.size.z])
	check(tb.get_center().length() < 0.002, "Tyre centred on the hub origin (|centre| %.4f m)" % tb.get_center().length())
	# --- concentric spin: rotate WheelPivot about local X by PI/2 ---
	var before := group_aabb(pivot)
	pivot.rotate_x(PI / 2)
	var after := group_aabb(pivot)
	var d_pos := (after.position - before.position).abs()
	var d_end := (after.end - before.end).abs()
	var worst := maxf(d_pos[d_pos.max_axis_index()], d_end[d_end.max_axis_index()])
	print("Spin group AABB before ", before, " after ", after)
	check(worst < 0.01, "WheelPivot group AABB unchanged after 90 deg spin about X (max delta %.1f mm)" % (worst * 1000.0))
	for n in ["Tyre", "RimBarrel", "BrakeDisc", "CentreCap"]:
		var mi: MeshInstance3D = model.find_child(n, true, false)
		var c: Vector3 = mi.mesh.get_aabb().get_center()
		check(Vector2(c.y, c.z).length() < 0.002, "%s revolved mesh concentric with the axle (Y/Z offset %.2f mm)" % [n, Vector2(c.y, c.z).length() * 1000.0])
	pivot.rotate_x(-PI / 2)
	# --- triangle counts vs handoff ---
	var lod0_total := 0
	var lod1_total := 0
	for key in ["lod0", "lod1"]:
		var table: Dictionary = handoff[key]["triangles"]
		for n in table.keys():
			var mi: MeshInstance3D = model.find_child(str(n), true, false)
			if mi == null:
				check(false, "%s missing for triangle count" % n)
				continue
			var got := tri_count(mi)
			var want := int(table[n]["triangles"])
			if key == "lod0": lod0_total += got
			else: lod1_total += got
			check(absf(got - want) <= maxf(1.0, want * 0.02), "%s triangles %d (handoff %d)" % [n, got, want])
	print("Triangles LOD0 %d (handoff %d)  LOD1 %d (handoff %d)" % [lod0_total, int(handoff["lod0"]["triangles_total"]), lod1_total, int(handoff["lod1"]["triangles_total"])])
	check(absf(lod0_total - int(handoff["lod0"]["triangles_total"])) <= lod0_total * 0.02, "LOD0 total within 2 %")
	check(absf(lod1_total - int(handoff["lod1"]["triangles_total"])) <= lod1_total * 0.02, "LOD1 total within 2 %")
	# --- materials ---
	var found: Dictionary = {}
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		for s in range((mi as MeshInstance3D).mesh.get_surface_count()):
			var mat: Material = (mi as MeshInstance3D).mesh.surface_get_material(s)
			if mat == null: continue
			var nm := mat.resource_name
			if not found.has(nm):
				found[nm] = mat
				if mat is BaseMaterial3D:
					var b := mat as BaseMaterial3D
					print("  material %-12s albedo %s metallic %.2f roughness %.2f spec %.2f clearcoat %s cull %d" % [nm, b.albedo_color.to_html(false), b.metallic, b.roughness, b.metallic_specular, str(b.clearcoat_enabled), b.cull_mode])
	for m in MATERIALS:
		check(found.has(m), "Material slot '%s' present" % m)
	check(found.size() == MATERIALS.size(), "No extra material names (%s)" % str(found.keys()))
	# --- LOD1 placement ---
	if lod1 != null:
		print("WheelR_LOD1 offset in Godot space: ", fmt(lod1.position), " parent ", lod1.get_parent().name)
		check(lod1.get_parent() == wheel_r.get_parent(), "WheelR_LOD1 is a sibling of WheelR")
		check(lod1.position.is_equal_approx(Vector3(0, 0, -1)), "WheelR_LOD1 at (0, 0, -1) after Y-up conversion (got %s)" % fmt(lod1.position))
	# --- game contract: what wheel_nodes() would collect on the raw scene ---
	var collected: Array[Node3D] = CityAssets.wheel_nodes(model)
	var collected_names: Array[String] = []
	for c in collected: collected_names.append(str(c.name))
	print("CityAssets.wheel_nodes() on the raw scene collects: ", collected_names)
	finish()

func finish() -> void:
	print("WHEEL IMPORT %s: %d checks, %d failed" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed > 0 else 0)
