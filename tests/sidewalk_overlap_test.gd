extends SceneTree
## Sidewalks, paths and forecourts must never lie on a road carriageway. Every upward-facing
## triangle of every flat, raised (sidewalk-height) mesh in the world is tested: its centre must
## not be on a named street's carriageway (StreetNames) or a curved estate road's carriageway.
## Road decks, junction pads, markings and bike lanes are road surfaces and are skipped.
var checks := 0
var failed := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

## Distance-based carriageway test for curved estate roads (8 m wide).
static func on_curved(p: Vector2, roads: Array[PackedVector3Array], margin: float) -> bool:
	var q := Vector3(p.x, 0, p.y)
	# Park islands inside the two estate roundabouts are not carriageway.
	for x in [-64.0, 64.0]:
		if Vector2(p.x - x, p.y + 145.0).length() < 16.2: return false
	for path in roads:
		for i in range(1, path.size()):
			if Geometry3D.get_closest_point_to_segment(q, path[i - 1], path[i]).distance_to(q) < 4.0 - margin: return true
	return false

## Axis-aligned carriageway rectangles of the named streets (no rounded end caps).
static func on_street(p: Vector2, tol: float) -> bool:
	for seg in StreetNames.segments():
		var a: Vector2 = seg.a
		var b: Vector2 = seg.b
		var half: float = float(seg.half) - tol
		var lo := Vector2(minf(a.x, b.x), minf(a.y, b.y))
		var hi := Vector2(maxf(a.x, b.x), maxf(a.y, b.y))
		if is_equal_approx(a.x, b.x):
			if absf(p.x - a.x) < half and p.y > lo.y + tol and p.y < hi.y - tol: return true
		else:
			if absf(p.y - a.y) < half and p.x > lo.x + tol and p.x < hi.x - tol: return true
	return false

func is_road_surface(node: Node, mat: Material) -> bool:
	var path := str(node.get_path())
	if path.contains("StreetGrid") or path.contains("TrafficCircles") or path.contains("Buses"): return true
	var c := Color.WHITE
	if mat is ShaderMaterial:
		var sm := mat as ShaderMaterial
		if sm.shader == null or not sm.shader.resource_path.ends_with("surface.gdshader") or sm.shader.resource_path.contains("road"): return true
		c = sm.get_shader_parameter("tint")
	if mat is StandardMaterial3D: c = (mat as StandardMaterial3D).albedo_color
	if mat is StandardMaterial3D or mat is ShaderMaterial:
		var lum := 0.3 * c.r + 0.59 * c.g + 0.11 * c.b
		if lum < 0.45: return true          # asphalt-dark surfaces
		if c.g > c.r * 1.25 and c.g > c.b * 1.1: return true   # green bike lanes / grass
		if lum > 0.9: return true            # white paint
		if c.r > 0.8 and c.g > 0.6 and c.b < 0.35: return true   # yellow paint
	return false

func run() -> void:
	var world := CedarNeighborhood.new()
	root.add_child(world)
	for i in range(3): await process_frame
	# The curved roads as actually built (stopped at forecourts, trimmed at junction corners).
	var curved: Array[PackedVector3Array] = []
	var cr: CurvedRoads = world.find_child("CurvedRoads", true, false)
	for spec in cr.specs:
		curved.append(CurvedRoads.trim(spec.path, float(spec.get("trim_start", 0.0)), float(spec.get("trim_end", 0.0))))
	var bad := {}
	var tested := 0
	var items: Array = []   # [node, mesh, transform, material_override]
	for node in world.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		if mi.mesh != null and mi.is_visible_in_tree(): items.append([mi, mi.mesh, mi.global_transform, mi.material_override])
	for node in world.find_children("*", "MultiMeshInstance3D", true, false):
		var mm := node as MultiMeshInstance3D
		if mm.multimesh == null or mm.multimesh.mesh == null or not mm.is_visible_in_tree(): continue
		if mm.visibility_range_begin > 0.0: continue
		for k in range(mm.multimesh.instance_count):
			items.append([mm, mm.multimesh.mesh, mm.global_transform * mm.multimesh.get_instance_transform(k), mm.material_override])
	for item in items:
		var mi: GeometryInstance3D = item[0]
		var mesh: Mesh = item[1]
		var xf: Transform3D = item[2]
		var aabb := xf * mesh.get_aabb()
		# Flat, raised, ground-level pieces: sidewalks, walks, forecourts, plazas.
		if aabb.size.y > 0.35 or aabb.end.y < 0.045 or aabb.end.y > 0.32: continue
		if maxf(aabb.size.x, aabb.size.z) < 0.8 or minf(aabb.size.x, aabb.size.z) < 0.3: continue   # skip paint lines
		if aabb.size.y < 0.02 and not str(mi.get_path()).contains("CurvedRoads"): continue   # painted decals (crosswalks)
		if mesh.resource_name.contains("curb_ramp"): continue   # accessible kerb ramps slope down to the road by design
		for s in range(mesh.get_surface_count()):
			var mat: Material = item[3]
			if mat == null and mi is MeshInstance3D: mat = (mi as MeshInstance3D).get_surface_override_material(s)
			if mat == null: mat = mesh.surface_get_material(s)
			if is_road_surface(mi, mat): continue
			var arrays := mesh.surface_get_arrays(s)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			var count := idx.size() if idx.size() > 0 else verts.size()
			for k in range(0, count, 3):
				var a := xf * verts[idx[k] if idx.size() else k]
				var b := xf * verts[idx[k + 1] if idx.size() else k + 1]
				var c := xf * verts[idx[k + 2] if idx.size() else k + 2]
				var n := (c - a).cross(b - a)
				if n.length() < 0.0001 or n.normalized().y < 0.9: continue   # top faces only
				tested += 1
				# Dense barycentric samples (<= ~1 m apart): long sidewalk boxes are two triangles.
				var steps := clampi(ceili(maxf(a.distance_to(b), maxf(b.distance_to(c), c.distance_to(a)))), 1, 600)
				var hit := false
				for i in range(steps + 1):
					if hit: break
					for j in range(steps + 1 - i):
						var u := (float(i) + 0.33) / (steps + 1.0)
						var v := (float(j) + 0.33) / (steps + 1.0)
						if u + v > 0.98: continue
						var probe := a + (b - a) * u + (c - a) * v
						var flat := Vector2(probe.x, probe.z)
						var in_park := Vector2(flat.x - 64.0, flat.y + 145.0).length() < 16.2 or Vector2(flat.x + 64.0, flat.y + 145.0).length() < 16.2
						if not in_park and (on_street(flat, 0.35) or on_curved(flat, curved, 0.35)):
							var key := "%s %s" % [mi.get_path(), aabb]
							if not bad.has(key): bad[key] = []
							bad[key].append(probe.snapped(Vector3.ONE * 0.1))
							hit = true
							break
	print("tested %d sidewalk-level top triangles" % tested)
	for key in bad: print("  ON ROAD: ", key, " at ", bad[key].slice(0, 3))
	check(bad.is_empty(), "No sidewalk/path surface on a carriageway (%d meshes)" % bad.size())
	print("SIDEWALK OVERLAP %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)
