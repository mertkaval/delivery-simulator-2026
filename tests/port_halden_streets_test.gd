extends SceneTree
## Port Halden's streets by Mert Road Studio (assets/cityforge/mrs): they load in place of CityForge's own
## street ribbons and street furniture, and they are solid where people walk and drive.
## Rendered run (imported meshes are empty dummies in --headless, so trimesh collision needs a window):
##   godot --path . --script res://tests/port_halden_streets_test.gd
## Checks: the plan says streets = "mrs"; the MRS chunks, kit, signals, street-name labels and street trees
## load; CityForge's replaced props are not drawn; collision (a ray down at the middle of every MRS street longer
## than 40 m, on its carriageway and on both sidewalks) finds the MRS surface above the fitted ground (the
## ground never rises through the paving, and no more than the edge skirt hides); the courier's start point stands
## on a sidewalk.
var failures := 0
var checks := 0

func _initialize() -> void: call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	print(("PASS: " if ok else "FAIL: ") + text)
	if not ok: failures += 1

## The first surface (trimesh) under p: rays pass through the box colliders of street props (shelters, benches, poles).
func surface_hit(space: PhysicsDirectSpaceState3D, p: Vector3) -> Dictionary:
	var top := p + Vector3.UP * 300.0
	for i in 6:
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(top, p + Vector3.DOWN * 200.0))
		if hit.is_empty(): return hit
		var body := hit.collider as CollisionObject3D
		var owner_ := body.shape_owner_get_owner(body.shape_find_owner(int(hit.shape))) as CollisionShape3D if body != null else null
		# the street surfaces (MrsCol_*) or the ground; props, awnings and other overhead structures are looked through
		if owner_ == null or str(owner_.name).begins_with("MrsCol") or str(body.name) == "Ground": return hit
		top = (hit.position as Vector3) + Vector3.DOWN * 0.005
	return {}

func run() -> void:
	var t0 := Time.get_ticks_msec()
	var w := CityForgeWorld.new()
	root.add_child(w)
	var city: Dictionary = w.city
	check(str(city.get("streets", "")) == "mrs", "The plan's streets come from Mert Road Studio")
	check(w.mrs != null, "MRS street data loaded")
	if w.mrs == null:
		print("PORT_HALDEN_STREETS: %d checks, %d failures" % [checks, failures])
		quit(1)
		return
	var st: Dictionary = w.mrs.stats
	print("MRS stats ", st, " build_ms ", w.stats.build_ms)
	check(int(st.get("chunks", 0)) >= 40, "MRS street chunks attached (%d)" % int(st.get("chunks", 0)))
	check(int(st.get("instances", 0)) >= 5000, "MRS street assets placed as instances (%d)" % int(st.get("instances", 0)))
	check(int(st.get("labels", 0)) >= 200, "Street-name blades carry their names (%d labels)" % int(st.get("labels", 0)))
	check(int(st.get("trees", 0)) >= 1000, "MRS street trees planted (%d)" % int(st.get("trees", 0)))
	var data: Dictionary = w.mrs.data
	check((data.get("signals", []) as Array).size() >= 300, "Signal poles at the signalised junctions (%d)" % (data.get("signals", []) as Array).size())
	check(w.kit.has(MrsCityStreets.KIT_SIGNAL) and w.kit.has(MrsCityStreets.KIT_STREETNAME), "Signal and street-name kit models loaded")
	var replaced := 0
	for node in w.find_children("*", "MultiMeshInstance3D", true, false):
		var nm := str(node.name)
		for k: String in CityForgeWorld.MRS_REPLACED:
			if nm.begins_with(k + "_"): replaced += 1
		if nm.begins_with("sign_pole_") or nm.begins_with("sign_blade_"): replaced += 1
	check(replaced == 0, "CityForge's lamps, signals, stops, hydrants, benches and signs are not drawn (%d groups)" % replaced)
	var lens_ok := false
	var sig_mesh: Mesh = (w.kit[MrsCityStreets.KIT_SIGNAL] as Array)[0] if w.kit.has(MrsCityStreets.KIT_SIGNAL) else null
	if sig_mesh != null:
		for s in sig_mesh.get_surface_count():
			var m := sig_mesh.surface_get_material(s) as ShaderMaterial
			if m != null and m.shader == MrsCityStreets.LENS_SHADER: lens_ok = true
	check(lens_ok, "Signal lenses run their phase cycle in the lens shader")
	# collision everywhere at once, then rays
	w.build_all_collision()
	for i in 3: await physics_frame
	var space := w.get_world_3d().direct_space_state
	var probes := 0
	var miss: Array[String] = []
	var bad_h: Array[String] = []
	var half_size := w.size * 0.5
	# the MRS streets themselves (mrs_city.json "roads": centre lines in Blender world coordinates)
	for r: Dictionary in data.get("roads", []):
		var pts: Array = r.pts
		if pts.size() < 2 or str(r.cls) == "lane" or bool(r.get("bridge", false)): continue
		var length := 0.0
		for k in range(1, pts.size()):
			length += Vector2(float(pts[k][0]) - float(pts[k - 1][0]), float(pts[k][1]) - float(pts[k - 1][1])).length()
		if length < 40.0: continue
		var k0 := pts.size() / 2 - 1
		var pa := Vector2(float(pts[k0][0]), float(pts[k0][1])) + Vector2(half_size, half_size)
		var pb := Vector2(float(pts[k0 + 1][0]), float(pts[k0 + 1][1])) + Vector2(half_size, half_size)
		if pa.distance_to(pb) < 0.5: continue
		var mid := (pa + pb) * 0.5
		var d := (pb - pa).normalized()
		var n := Vector2(-d.y, d.x)
		var half := float(r.width) * 0.5
		var lats: Array = [0.0, half + 3.1, -(half + 3.1)]
		if str(r.cls) == "boulevard": lats = [half - 2.0, half + 3.1, -(half + 3.1)]     # the median is planting, not paving
		for lat: float in lats:
			var q := mid + n * lat
			var p := w.to_world(q.x, q.y)
			var hit := surface_hit(space, p)
			probes += 1
			if hit.is_empty():
				miss.append("%s@%.0f" % [str(r.id), lat]); continue
			var y := (hit.position as Vector3).y
			var ground := w.ground_height(p)
			# the street surface stands over the fitted ground (never under it: no ground through the paving), by at most
			# the 1.2 m edge skirt plus the kerb, so no gap shows at a sidewalk's back edge (the fit sinks it 0.3 m)
			if str((hit.collider as Node).name) == "Ground" or y - ground < 0.02 or y - ground > 1.3:
				bad_h.append("%s@%.0f %.2f" % [str(r.id), lat, y - ground])
	check(miss.is_empty(), "Every street probe hits a surface (%d / %d missed %s)" % [miss.size(), probes, str(miss.slice(0, 6))])
	if OS.get_environment("MRS_PROBE_DUMP") != "": print("BAD_H ", bad_h)
	check(bad_h.is_empty(), "Street and sidewalk surfaces stand 0.02-1.3 m over the fitted ground, never under it (%d / %d off %s)" % [bad_h.size(), probes, str(bad_h.slice(0, 6))])
	# the courier's start: on a sidewalk
	var start := PortHaldenGame.apply(w)
	var sp: Vector3 = start.get("start", Vector3.ZERO) if start.has("start") else Vector3.ZERO
	if sp != Vector3.ZERO:
		var hit2 := surface_hit(space, sp)
		var on_street := false
		if not hit2.is_empty():
			var body2 := hit2.collider as CollisionObject3D
			var owner2 := body2.shape_owner_get_owner(body2.shape_find_owner(int(hit2.shape))) as Node
			on_street = owner2 != null and str(owner2.name).begins_with("MrsCol")
		check(on_street and (hit2.position as Vector3).y - w.ground_height(sp) > 0.02,
			"The courier starts on a sidewalk (%s)" % str(hit2.get("position", "none")))
	check(int(w.stats.build_ms) < 15000, "City with MRS streets builds in %d ms" % int(w.stats.build_ms))
	print("PORT_HALDEN_STREETS: %d checks, %d failures (%d ms)" % [checks, failures, Time.get_ticks_msec() - t0])
	quit(0 if failures == 0 else 1)
