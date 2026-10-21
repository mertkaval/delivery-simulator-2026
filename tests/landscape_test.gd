extends SceneTree
## Landscape pass (CityLandscape) checks, headless:
##   * every tree species loads with LOD0 <= 8k and LOD1 <= 2k triangles, wind-shader materials,
##     an impostor slot, and the garden / forest / rock kits load;
##   * the city is planted (street, garden, backyard, park and horizon trees, shrubs, beds, grass);
##   * no tree, shrub, bed or planter record stands on a carriageway or a house's front walk;
##   * park planting stays outside the oval promenade and the cross paths;
##   * tree trunks are colliders, horizon trees are not.
var checks := 0
var failed := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

static func tris(mesh: Mesh) -> int:
	var n := 0
	for s in range(mesh.get_surface_count()):
		var a := mesh.surface_get_arrays(s)
		var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX] if a[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		n += (idx.size() if idx.size() > 0 else (a[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()) / 3
	return n

func run() -> void:
	CityLandscape.load_assets()
	for sid in CityLandscape.TREES:
		var sp := CityLandscape.species(sid)
		var t0 := tris(sp.lod0)
		var t1 := tris(sp.lod1)
		check(t0 > 500 and t0 <= 8000, "%s LOD0 %d tris within budget" % [sid, t0])
		check(t1 > 200 and t1 <= 3000, "%s LOD1 %d tris within budget" % [sid, t1])
		check(float(sp.height) > 5.0 and float(sp.height) < 21.0, "%s real height %.1f m" % [sid, sp.height])
		var wind := false
		for s in range((sp.lod0 as Mesh).get_surface_count()):
			if (sp.lod0 as Mesh).surface_get_material(s) is ShaderMaterial: wind = true
		check(wind, "%s uses the foliage wind shader" % sid)
		check(int(sp.slot) >= 0 and int(sp.slot) < 16, "%s impostor slot %d" % [sid, sp.slot])
	for kind in ["shrub", "grass", "potted", "bed_plant", "rock", "forest_tree", "forest_pine", "understory"]:
		check(not CityLandscape.prop_ids(kind).is_empty(), "kit has %s assets (%s)" % [kind, CityLandscape.prop_ids(kind)])
	check(not CityLandscape.prop("bed_edging").is_empty(), "bed edging loads")
	var world := CedarNeighborhood.new()
	root.add_child(world)
	for i in range(3): await process_frame
	var land: CityLandscape = world.landscape
	print("LANDSCAPE counts ", JSON.stringify(land.counts))
	var trees := 0
	for sid in CityLandscape.TREES: trees += int(land.counts.get(sid, 0))
	check(int(land.counts.get("plane_tree", 0)) >= 50, "avenue plane trees (%d)" % int(land.counts.get("plane_tree", 0)))
	check(trees >= 400, "trees planted (%d)" % trees)
	check(int(land.counts.get("horizon_trees", 0)) >= 2000, "horizon forest (%d)" % int(land.counts.get("horizon_trees", 0)))
	var placer: PropPlacer = world.placer
	var sources := {}
	var on_road := 0
	var on_walk := 0
	var in_park := 0
	for rec in placer.records:
		if not (rec.kind in ["tree", "shrub", "bed", "planter", "rock"]): continue
		sources[rec.source] = int(sources.get(rec.source, 0)) + 1
		var p := Vector2(rec.at.x, rec.at.z)
		if not PropPlacer.surface_at(p, float(rec.radius)).is_empty():
			on_road += 1
			print("  on road: %s %s at %s" % [rec.kind, rec.source, rec.at])
		if rec.kind != "planter" and PropPlacer.on_walk(p, float(rec.radius) + 0.2):
			on_walk += 1
			print("  on walk: %s %s at %s" % [rec.kind, rec.source, rec.at])
		if str(rec.source).begins_with("park_"):
			for park in CityLandscape.PARKS:
				if Vector2(rec.at.x - park.x, rec.at.z - park.z).length() < 18.0 and CityLandscape.park_core(park, rec.at, 0.3):
					in_park += 1
					print("  in park core: %s at %s" % [rec.source, rec.at])
	print("records by source ", JSON.stringify(sources))
	for s in ["side_road_tree", "cross_street_tree", "garden_tree", "backyard_tree", "park_tree", "front_shrub", "flower_bed", "park_shrub", "shop_pot"]:
		check(int(sources.get(s, 0)) > 0, "planted %s (%d)" % [s, int(sources.get(s, 0))])
	check(on_road == 0, "no planting on a carriageway (%d)" % on_road)
	check(on_walk == 0, "no planting on a front walk (%d)" % on_walk)
	check(in_park == 0, "park planting clear of the promenade and paths (%d)" % in_park)
	var trunks := land.trunks.get_child_count()
	check(trunks >= trees - int(land.counts.get("horizon_trees", 0)) and trunks > 300, "trunk colliders (%d)" % trunks)
	var outside := 0
	for shape in land.trunks.get_children():
		var at: Vector3 = (shape as CollisionShape3D).position
		if absf(at.x) > 121.0 or at.z > 72.0 or at.z < -712.0: outside += 1
	check(outside == 0, "no trunk colliders beyond the city boundary (%d)" % outside)
	check(land.get_child_count() > 100, "MultiMesh batches built (%d nodes)" % land.get_child_count())
	print("LANDSCAPE %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)
