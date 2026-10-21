extends SceneTree
## Parks, monuments and sports assets (assets/monuments, CityMonuments): asset budgets and
## materials, then their placement in the city: counts, collision, off every carriageway, park
## paths and AI routes' kerbs, PropPlacer records / reservations and the fountain VFX/audio spots.
## usage: godot --headless --path . --script res://tests/monuments_test.gd
var failures := 0
var checks := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

func textures_of(node: Node, out: Array[Texture2D]) -> void:
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		var mesh := (node as MeshInstance3D).mesh
		for i in range(mesh.get_surface_count()):
			var m := mesh.surface_get_material(i) as BaseMaterial3D
			if m == null: continue
			for t: Texture2D in [m.albedo_texture, m.normal_texture, m.roughness_texture, m.metallic_texture]:
				if t != null and not out.has(t): out.append(t)
	for c in node.get_children(): textures_of(c, out)

func tris_of(node: Node) -> int:
	var n := 0
	for g in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := (g as MeshInstance3D).mesh
		for i in range(mesh.get_surface_count()):
			var arrays := mesh.surface_get_arrays(i)
			var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			n += idx.size() / 3 if idx.size() > 0 else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return n

func material_named(node: Node, prefix: String) -> BaseMaterial3D:
	for g in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := (g as MeshInstance3D).mesh
		for i in range(mesh.get_surface_count()):
			var m := mesh.surface_get_material(i) as BaseMaterial3D
			if m != null and m.resource_name.begins_with(prefix): return m
	return null

func run() -> void:
	# ---- assets
	var budget := {"ataturk_monument": 15000, "ataturk_equestrian": 15000, "ataturk_bust": 10000, "sculpture_open_arms": 15000,
		"sculpture_stretch": 15000, "statue_jenner": 15000, "fountain_putti": 20000, "basketball_court": 20000}
	for id: String in budget:
		var data := CityMonuments.info(id)
		check(not data.is_empty(), "%s in monuments.json" % id)
		var node: Node3D = CityMonuments.scene(id).instantiate()
		var t := tris_of(node)
		check(t > 1000 and t <= int(budget[id]), "%s triangle budget (%d <= %d)" % [id, t, budget[id]])
		var texs: Array[Texture2D] = []
		textures_of(node, texs)
		var biggest := 0
		for tex in texs: biggest = maxi(biggest, maxi(tex.get_width(), tex.get_height()))
		check(biggest <= 2048, "%s textures <= 2048 (%d)" % [id, biggest])
		check((data.get("collision", []) as Array).size() >= 1, "%s has collision shapes" % id)
		print("asset %-20s tris %6d  textures %d (max %d)  size %s" % [id, t, texs.size(), biggest, data.get("size")])
		if id == "ataturk_equestrian":
			var bronze := material_named(node, "EquestrianBronze")
			check(bronze != null and bronze.vertex_color_use_as_albedo, "Equestrian bronze uses its baked AO vertex colours")
		if id == "basketball_court":
			var fence := material_named(node, "Court_M_Fence")
			check(fence != null and fence.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR, "Court chain-link uses alpha scissor")
			var marks := material_named(node, "Court_BCourt")
			check(marks != null and marks.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR, "Court markings use alpha scissor")
		node.free()
	# ---- placement in the city
	var world := CedarNeighborhood.new()
	root.add_child(world)
	for i in range(3): await process_frame
	var mon: CityMonuments = world.monuments
	check(mon != null, "CedarNeighborhood builds CityMonuments")
	var count := {}
	for it in mon.items: count[it.id] = int(count.get(it.id, 0)) + 1
	print("placed: ", count)
	check(int(count.get("ataturk_monument", 0)) == 1, "Atatürk Square monument")
	check(int(count.get("ataturk_equestrian", 0)) == 1, "Equestrian monument")
	check(int(count.get("ataturk_bust", 0)) == 7, "Bust memorials in seven parks")
	check(int(count.get("fountain_putti", 0)) == 8, "Putti fountains: seven parks + the square")
	check(int(count.get("sculpture_open_arms", 0)) + int(count.get("sculpture_stretch", 0)) == 4, "Four park sculptures")
	check(int(count.get("statue_jenner", 0)) == 1, "Jenner statue at the hospital")
	check(int(count.get("basketball_court", 0)) == 2, "Two school basketball courts")
	check(world.signage.busts.size() == StreetNames.PARKS.size(), "Every park has its Atatürk memorial")
	check(world.signage.monument_at.distance_to(mon.items.filter(func(it: Dictionary) -> bool: return it.id == "ataturk_monument")[0].at) < 0.01, "Signage monument_at is the placed monument")
	check(CityMonuments.fountain_spots().size() == 8, "Fountain spots for VFX/audio")
	check(mon.water.size() == 8, "Every fountain has its water surface")
	# collision bodies and footprints
	var bodies := 0
	for it in mon.items:
		var id: String = it.id
		var data := CityMonuments.info(id)
		var t := Transform3D(Basis(Vector3.UP, float(it.yaw)), it.at as Vector3)
		var s: Array = data.size
		var h := Vector3(float(s[0]), 0, float(s[2])) * 0.5
		var on_road := ""
		for k in range(9):
			var corner := Vector3(h.x * (k % 3 - 1), 0, h.z * (k / 3 - 1))
			var p := t * corner
			var hit := PropPlacer.surface_at(Vector2(p.x, p.z), 0.25)
			if not hit.is_empty(): on_road = "%s %s" % [hit.kind, hit.id]
		check(on_road == "", "%s at %s off every carriageway (%s)" % [id, it.at, on_road])
		# park paths: the cross paths (|x| or |z| < 1.3 within the oval) and the oval promenade
		if it.park is Vector2 and id != "ataturk_equestrian":
			var c: Vector2 = it.park
			for k in range(9):
				var p := t * Vector3(h.x * (k % 3 - 1), 0, h.z * (k / 3 - 1))
				var l := Vector2(p.x - c.x, p.z - c.y)
				var on_cross := (absf(l.x) < 1.35 and absf(l.y) < 16.0) or (absf(l.y) < 1.35 and absf(l.x) < 10.0)
				var e := Vector2(l.x / 9.0, l.y / 14.0).length()
				var on_oval := e > 0.86 and e < 1.0
				check(not on_cross and not on_oval, "%s in %s clear of the park paths (local %s)" % [id, c, l])
		for n in mon.get_children():
			if n is Node3D and (n as Node3D).global_position.distance_to(it.at as Vector3) < 0.01 and n.get_node_or_null("Collision") != null:
				bodies += 1
				break
	check(bodies == mon.items.size(), "Every monument has a collision body (%d/%d)" % [bodies, mon.items.size()])
	var recs := world.placer.records.filter(func(r: Dictionary) -> bool: return r.source == "monuments")
	check(recs.size() == mon.items.size(), "PropPlacer records every monument (%d)" % recs.size())
	var reserved := world.placer.reserved.filter(func(r: Dictionary) -> bool: return r.tag in ["monument", "court"])
	check(reserved.size() >= mon.items.size(), "PropPlacer keep-clear zones for the monuments (%d)" % reserved.size())
	# other props keep clear: no placer record from another source inside a monument footprint
	var intruders := 0
	for r in world.placer.records:
		if r.source == "monuments" or r.get("flat", false): continue
		for z in reserved:
			if (z.rect as Rect2).has_point(Vector2((r.at as Vector3).x, (r.at as Vector3).z)) and r.source != "park" and r.source != "bench":
				intruders += 1
				print("  intruder ", r.kind, " ", r.source, " at ", r.at)
	check(intruders == 0, "No other placed prop inside a monument footprint (%d)" % intruders)
	# equestrian strollers loop keeps 1 m from the pedestal
	var loop := CityMonuments.stroll_loop(Vector3(64, 0, -145))
	var ped: Array = CityMonuments.info("ataturk_equestrian").size
	var worst := INF
	for p in loop:
		var q := p   # the equestrian stands unrotated (rider faces +z)
		worst = minf(worst, Vector2(maxf(absf(q.x) - float(ped[0]) * 0.5, 0), maxf(absf(q.z) - float(ped[2]) * 0.5, 0)).length())
	check(worst > 0.9, "Equestrian park stroll loop clears the pedestal (%.2f m)" % worst)
	print("MONUMENTS: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
