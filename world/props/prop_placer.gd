class_name PropPlacer
extends RefCounted
## Procedural placement for city props: the one place that knows the road geometry and hands
## out valid spots for street lights, hydrants, bins, benches, racks, signs, trees and stops.
##
## Road model (static, deterministic): every carriageway is a straight piece with a half width:
##   street    - the Blender street grid (avenue, side roads, cross streets) incl. bike lanes and
##               junction boxes (StreetGrid.roads(), rectangles),
##   estate    - curved estate roads (CityCatalog.estate_roads(), 8 m, capsule pieces),
##   ring      - the two park roundabout rings,
##   downtown  - downtown's own street grid (DowntownCatalog),
##   driveway  - the stretch of a frontage road that runs on into the forecourt it serves,
##   alley/lane - downtown service lanes and residential rear lanes (soft: no AI traffic).
## Sidewalk cross-section: kerb at `half`, a kerb-side furniture zone ~0.4-1.2 m behind the kerb
## (lights, hydrants, signs, racks), a walking line, and the frontage zone at the back edge
## (benches, bins, newspaper boxes, planters).
##
## A PropPlacer instance (CedarNeighborhood.placer) keeps a spatial registry of everything placed
## so far and validates each request: off every carriageway (plus a kerb margin), clear of
## junction boxes, mid-block crossings, house walks/doors, forecourts and bus stops, and a
## minimum clearance from other props. Invalid requests slide along the street to the nearest
## valid spot (deterministic search order) or are dropped.

const STRICT: Array[String] = ["street", "estate", "ring", "downtown", "driveway"]
const SOFT: Array[String] = ["alley", "lane"]
const KERB_MARGIN := 0.25     ## props keep this far behind the kerb face
const CELL := 16.0
const REG_CELL := 4.0
## Signalled mid-block crossings on Atatürk Avenue (z).
const CROSSINGS := [17.0, -93.0, -177.0]

static var _surfaces: Array[Dictionary] = []
static var _grid: Dictionary = {}
static var _walks: Array[Dictionary] = []
static var _walk_grid: Dictionary = {}

# ----------------------------------------------------------------------------- road model

## Every carriageway piece: {"a", "b": Vector2 (x, z), "half", "kind", "id", "name", "caps"}.
static func surfaces() -> Array[Dictionary]:
	if not _surfaces.is_empty(): return _surfaces
	var list: Array[Dictionary] = []
	for road in StreetGrid.roads():
		list.append({"a": road.a, "b": road.b, "half": float(road.profile.half), "kind": "street", "id": str(road.name), "caps": false})
	var k := 0
	var courts := forecourts()
	for path in CityCatalog.estate_roads():
		var ring := path.size() > 8 and path[0].distance_to(path[-1]) < 0.5
		for i in range(1, path.size()):
			var a := Vector2(path[i - 1].x, path[i - 1].z)
			var b := Vector2(path[i].x, path[i].z)
			# Frontage roads run on into the shop / walk-up forecourts they serve: that stretch is
			# the driveway (the asphalt stops 3 m in, the apron carries on at road level).
			var kind := "ring" if ring else "estate"
			for r in courts:
				if r.grow(1.0).has_point((a + b) * 0.5): kind = "driveway"
			list.append({"a": a, "b": b, "half": 4.0, "kind": kind, "id": "Estate%d" % k, "caps": true})
		k += 1
	for x: float in DowntownCatalog.STREET_X:
		list.append({"a": Vector2(x, -246), "b": Vector2(x, -690), "half": 9.0 if x == 252.0 else 7.0, "kind": "downtown", "id": "Downtown%d" % int(x), "caps": false})
	for z: float in DowntownCatalog.STREET_Z:
		list.append({"a": Vector2(120, z), "b": Vector2(492, z), "half": 7.0, "kind": "downtown", "id": "Downtown%d" % int(z), "caps": false})
	for parcel in DowntownCatalog.blocks():
		var c := parcel.get_center()
		list.append({"a": Vector2(c.x - 42, c.y), "b": Vector2(c.x + 42, c.y), "half": 4.0, "kind": "alley", "id": "Alley%d_%d" % [int(c.x), int(c.y)], "caps": false})
	for lane in ResidentialLayout.lanes():
		list.append({"a": Vector2(lane.x, lane.z0), "b": Vector2(lane.x, lane.z1), "half": float(lane.width) * 0.5, "kind": "lane", "id": "Lane%d_%d" % [int(lane.x), int(lane.z0)], "caps": false})
	for i in range(list.size()):
		var s: Dictionary = list[i]
		var lo := Vector2(minf(s.a.x, s.b.x), minf(s.a.y, s.b.y)) - Vector2.ONE * (float(s.half) + 12.0)
		var hi := Vector2(maxf(s.a.x, s.b.x), maxf(s.a.y, s.b.y)) + Vector2.ONE * (float(s.half) + 12.0)
		for gx in range(floori(lo.x / CELL), floori(hi.x / CELL) + 1):
			for gz in range(floori(lo.y / CELL), floori(hi.y / CELL) + 1):
				var key := Vector2i(gx, gz)
				if not _grid.has(key): _grid[key] = []
				(_grid[key] as Array).append(i)
	_surfaces = list
	return list

## Paved forecourts the frontage roads drive into (shops, walk-ups). Same rects as
## CedarNeighborhood.forecourt_rects().
static func forecourts() -> Array[Rect2]:
	var rects: Array[Rect2] = []
	for id in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		rects.append(Rect2(at.x - 8, at.z + 5, 16, 8))
	for z in [-110, -190]:
		for x in [-92, 92]:
			rects.append(Rect2(x - 9, z + 7.5, 18, 7))
	return rects

## Signed distance from p to the carriageway edge of surface s (negative = on the carriageway).
static func edge_distance(p: Vector2, s: Dictionary) -> float:
	var a: Vector2 = s.a
	var b: Vector2 = s.b
	var half: float = s.half
	if s.caps: return Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p) - half
	var ab := b - a
	var length := ab.length()
	var dir := ab / length
	var t := (p - a).dot(dir)
	var lateral := absf((p - a).dot(Vector2(-dir.y, dir.x))) - half
	var along := maxf(-t, t - length)
	if along <= 0.0: return lateral
	if lateral <= 0.0: return along
	return Vector2(along, lateral).length()

## Surfaces near p (spatial hash).
static func nearby(p: Vector2) -> Array:
	surfaces()
	return _grid.get(Vector2i(floori(p.x / CELL), floori(p.y / CELL)), [])

## The carriageway a disc (p, radius) overlaps, or {} - only `kinds` count.
static func surface_at(p: Vector2, radius: float = 0.0, kinds: Array[String] = STRICT) -> Dictionary:
	var list := surfaces()
	var best := {}
	var best_d := INF
	for i: int in nearby(p):
		var s: Dictionary = list[i]
		if not (String(s.kind) in kinds): continue
		var d := edge_distance(p, s) - radius
		if d < 0.0 and d < best_d:
			best_d = d
			best = s
	return best

## Smallest edge distance from p to any carriageway of `kinds`, ignoring surfaces with id `own`.
static func clearance(p: Vector2, kinds: Array[String] = STRICT, own: String = "") -> float:
	var list := surfaces()
	var best := 12.0
	for i: int in nearby(p):
		var s: Dictionary = list[i]
		if own != "" and String(s.id) == own: continue
		if not (String(s.kind) in kinds): continue
		best = minf(best, edge_distance(p, s))
	return best

## The carriageway a sidewalk point belongs to: the nearest strict surface (its id).
static func lining(p: Vector2) -> Dictionary:
	var list := surfaces()
	var best := {}
	var best_d := INF
	for i: int in nearby(p):
		var s: Dictionary = list[i]
		if not (String(s.kind) in STRICT): continue
		var d := edge_distance(p, s)
		if d < best_d:
			best_d = d
			best = s
	return best

## Front walks of every house: door -> property line -> kerb, as 2D segments.
static func walks() -> Array[Dictionary]:
	if not _walks.is_empty(): return _walks
	for lot in ResidentialLayout.lots():
		var door: Vector3 = ResidentialLayout.TYPES[lot.type].door
		var t := ResidentialLayout.transform(lot)
		var start: Vector3 = t * Vector3(door.x, 0, 0)
		var facing: Vector3 = lot.facing
		var end: Vector3 = start + facing * (ResidentialLayout.SETBACK + 4.2)
		_walks.append({"a": Vector2(start.x, start.z), "b": Vector2(end.x, end.z)})
	# Authored walkways: the starter home path and the WC forecourt path.
	_walks.append({"a": Vector2(19.0, 40.25), "b": Vector2(8.0, 40.25)})
	_walks.append({"a": Vector2(-40.0, 38.0), "b": Vector2(-40.0, 41.6)})
	return _walks

## True if p lies within `radius` (< 6 m) of a house's front walk.
static func on_walk(p: Vector2, radius: float) -> bool:
	if _walk_grid.is_empty():
		var list := walks()
		for i in range(list.size()):
			var lo: Vector2 = (list[i].a as Vector2).min(list[i].b) - Vector2.ONE * 6.0
			var hi: Vector2 = (list[i].a as Vector2).max(list[i].b) + Vector2.ONE * 6.0
			for gx in range(floori(lo.x / CELL), floori(hi.x / CELL) + 1):
				for gz in range(floori(lo.y / CELL), floori(hi.y / CELL) + 1):
					var key := Vector2i(gx, gz)
					if not _walk_grid.has(key): _walk_grid[key] = []
					(_walk_grid[key] as Array).append(i)
	for i: int in _walk_grid.get(Vector2i(floori(p.x / CELL), floori(p.y / CELL)), []):
		var w: Dictionary = _walks[i]
		if Geometry2D.get_closest_point_to_segment(p, w.a, w.b).distance_to(p) < radius: return true
	return false

## Sidewalk cross-section: a point `back` metres behind the kerb of a carriageway whose
## centreline passes through `centre` with half width `half`, on the `across` side (unit).
## Kerb-side furniture zone: back 0.4-1.2 m. Frontage zone: back ~ sidewalk width - 0.4 m.
static func kerb_spot(centre: Vector3, across: Vector3, half: float, back: float) -> Vector3:
	return Vector3(centre.x, 0.0, centre.z) + across * (half + back)

## Street name for reports (StreetNames, else the district).
static func describe(at: Vector3) -> String:
	return StreetNames.describe(at)

# ----------------------------------------------------------------------------- registry

var seed_value := 2026
## Every accepted placement: {"kind", "at": Vector3, "radius", "source"}.
var records: Array[Dictionary] = []
## Keep-clear zones: {"rect": Rect2, "tag"} (shop / walk-up / restaurant forecourts).
var reserved: Array[Dictionary] = []
var rejected: Array[Dictionary] = []   ## {"kind", "at", "reason"} requests that found no spot
var relocated := 0
var _cells: Dictionary = {}

func _init(seed_in: int = 2026) -> void:
	seed_value = seed_in
	for r in forecourts(): reserve(r, "forecourt")
	# Restaurant forecourts on Atatürk Avenue (three pickups).
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		reserve(Rect2(p.x - 10, p.z + 3, 12, 2), "restaurant_forecourt")

func reserve(rect: Rect2, tag: String) -> void:
	reserved.append({"rect": rect, "tag": tag})

## Deterministic random stream for a placement family.
func rng(key: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = hash(key) ^ seed_value
	return r

## Why a disc at `at` with `radius` is not a valid spot for `kind` (empty string = valid).
## opts: "own" (road id the prop lines; default the nearest), "junction" (min distance to
## any other carriageway edge), "walk" (clearance from front walks), "gap" (between props),
## "spacing" (min distance to props of the same kind), "on_road" (allowed on the road, e.g.
## road works), "reserved_ok" (may stand on forecourts), "soft_ok" (may stand on lanes),
## "roads_only" (only the carriageway + kerb margin rule, for densely dressed frontages).
func problem(kind: String, at: Vector3, radius: float, opts: Dictionary = {}) -> String:
	var p := Vector2(at.x, at.z)
	if opts.get("roads_only", false):
		var road := surface_at(p, radius + KERB_MARGIN)
		return "" if road.is_empty() else "on %s %s" % [road.kind, road.id]
	if not opts.get("on_road", false):
		var hit := surface_at(p, radius + KERB_MARGIN)
		if not hit.is_empty(): return "on %s %s" % [hit.kind, hit.id]
		if not opts.get("soft_ok", false):
			var soft := surface_at(p, radius, SOFT)
			if not soft.is_empty(): return "on %s %s" % [soft.kind, soft.id]
		var junction: float = opts.get("junction", 0.0)
		if junction > 0.0:
			var own: String = opts.get("own", "")
			if own == "": own = String(lining(p).get("id", ""))
			if clearance(p, STRICT, own) < junction: return "junction"
		# Crossing landings: the kerb ramp and the walking line (|x| < 8.4) stay clear; the
		# frontage zone at the back of the sidewalk may still hold a bench.
		for c: float in CROSSINGS:
			if absf(p.y - c) < 3.5 + radius and absf(p.x) - radius < 8.4: return "crossing"
	var walk: float = opts.get("walk", 1.0)
	if walk > 0.0 and on_walk(p, walk + radius): return "walk"
	if not opts.get("reserved_ok", false):
		for r in reserved:
			if (r.rect as Rect2).grow(radius).has_point(p): return String(r.tag)
	var gap: float = opts.get("gap", 0.35)
	var spacing: float = opts.get("spacing", 0.0)
	var reach := maxf(spacing, radius + gap + 2.0)
	var c0 := Vector2i(floori((p.x - reach) / REG_CELL), floori((p.y - reach) / REG_CELL))
	var c1 := Vector2i(floori((p.x + reach) / REG_CELL), floori((p.y + reach) / REG_CELL))
	for gx in range(c0.x, c1.x + 1):
		for gz in range(c0.y, c1.y + 1):
			for idx: int in _cells.get(Vector2i(gx, gz), []):
				var rec: Dictionary = records[idx]
				if rec.get("flat", false): continue
				var d := Vector2(rec.at.x, rec.at.z).distance_to(p)
				if d < radius + float(rec.radius) + gap: return "near %s" % rec.kind
				if spacing > 0.0 and rec.kind == kind and d < spacing: return "spacing"
	return ""

func record(kind: String, at: Vector3, radius: float, source: String = "", flat: bool = false) -> void:
	var rec := {"kind": kind, "at": at, "radius": radius, "source": source, "flat": flat}
	records.append(rec)
	var key := Vector2i(floori(at.x / REG_CELL), floori(at.z / REG_CELL))
	if not _cells.has(key): _cells[key] = []
	(_cells[key] as Array).append(records.size() - 1)

## Withdraw the most recent record (a spot that was taken but then not used), keeping the
## spatial index in step with `records`.
func unrecord_last() -> void:
	if records.is_empty(): return
	var rec: Dictionary = records.pop_back()
	var key := Vector2i(floori((rec.at as Vector3).x / REG_CELL), floori((rec.at as Vector3).z / REG_CELL))
	if _cells.has(key): (_cells[key] as Array).erase(records.size())

## Validate a spot; on failure slide along `slide` (unit, horizontal) up to `max_slide` metres
## in 0.5 m steps, alternating sides (nearest first), then try each of `lateral` offsets
## (metres along `across`). Records and returns the spot, or null when none is valid.
func place(kind: String, at: Vector3, radius: float, opts: Dictionary = {}) -> Variant:
	var slide: Vector3 = opts.get("slide", Vector3.ZERO)
	var max_slide: float = opts.get("max_slide", 0.0)
	var offsets: Array[Vector3] = [Vector3.ZERO]
	var across: Vector3 = opts.get("across", Vector3.ZERO)
	for l: float in opts.get("lateral", []): offsets.append(across * l)
	for o in offsets:
		var d := 0.0
		while d <= max_slide + 0.001:
			for sgn: float in ([1.0] if d == 0.0 else [1.0, -1.0]):
				var q := at + o + slide * d * sgn
				if problem(kind, q, radius, opts) == "":
					record(kind, q, radius, String(opts.get("source", "")))
					if q.distance_to(at) > 0.01:
						relocated += 1
						records[-1]["from"] = at
						records[-1]["why"] = problem(kind, at, radius, opts)
					return q
			d += 0.5
			if slide == Vector3.ZERO: break
	rejected.append({"kind": kind, "at": at, "reason": problem(kind, at, radius, opts)})
	return null

## Spot for a street light with its pole `back` metres behind the kerb of the carriageway it
## lines, arm over the road. `at` is the requested pole spot (any height), `face` points from
## the pole over the road. Lights keep 6 m from junction boxes and `spacing` from each other.
func street_light(at: Vector3, face: Vector3, opts: Dictionary = {}) -> Variant:
	var o := {"junction": 6.0, "spacing": 8.0, "walk": 1.2, "gap": 0.4, "max_slide": 8.0,
		"slide": face.cross(Vector3.UP).normalized(), "source": "street_light"}
	o.merge(opts, true)
	return place("street_light", Vector3(at.x, 0.0, at.z), 0.2, o)

## Frontage props in tight spots (downtown sidewalks, shop forecourts): keep the requested spot
## if it is clear of every carriageway (plus the kerb margin), otherwise pull it back along
## `toward` (unit, away from the road) in `step` increments. Records and returns the spot.
func kerb_clear(kind: String, at: Vector3, toward: Vector3, radius: float, max_pull: float = 2.0, step: float = 0.1) -> Vector3:
	var d := 0.0
	while d <= max_pull + 0.001:
		var q := at + toward * d
		if problem(kind, q, radius, {"roads_only": true}) == "":
			record(kind, q, radius, "kerb_clear")
			if d > 0.0:
				relocated += 1
				records[-1]["from"] = at
				records[-1]["why"] = problem(kind, at, radius, {"roads_only": true})
			return q
		d += step
	rejected.append({"kind": kind, "at": at, "reason": problem(kind, at, radius, {"roads_only": true})})
	record(kind, at, radius, "kerb_clear")
	return at
