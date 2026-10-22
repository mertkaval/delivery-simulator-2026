class_name ResidentialLayout
extends RefCounted
## Vancouver/Burnaby-style residential district: narrow lots filled side by side along every
## street frontage, houses facing their street, rear lanes with garages, bins and power poles,
## and conifer forest on the city edges. Deterministic; every consumer (rendering, collision,
## delivery addresses, routes, grass, minimap, tests) reads the same data.
##
## Lot record: {type, front (house front-centre, ground), yaw, facing, line_x, lot (Rect2 xz),
##   colours {body, trim, door, roof}, rear ("garage"|"patio"|"shed"), fence ("hedge"|"picket"|""),
##   delivery (address index or -1), door (world point used as the delivery address)}

const SETBACK := 5.0
## House types: lot width, body width, body depth, door (local x, floor y, local z),
## stair ramp (x0, x1, top y, z top, z bottom) or empty, extra collision boxes (local centre, size).
const TYPES := {
	"house_craftsman": {"lot": 11.5, "w": 8.4, "d": 11.0, "h": 6.6, "door": Vector3(0.65, 1.05, 0.0),
		"ramp": [0.0, 1.3, 1.05, 2.1, 3.78], "boxes": [[Vector3(0.8, 0.52, 1.05), Vector3(3.9, 1.05, 2.1)]]},
	"house_special": {"lot": 14.0, "w": 12.0, "d": 11.0, "h": 6.8, "door": Vector3(-0.3, 1.35, -1.1),
		"ramp": [-1.1, 0.5, 1.35, 0.0, 2.24], "boxes": [[Vector3(-0.3, 0.67, -0.55), Vector3(1.6, 1.35, 1.1)]], "recess": [-1.1, 0.5, 1.1],
		"number": Vector3(0.95, 1.75, 0.04)},
	"house_modern": {"lot": 12.5, "w": 10.0, "d": 11.0, "h": 7.0, "door": Vector3(0.0, 0.0, 0.0), "ramp": [], "boxes": [],
		"number": Vector3(0.95, 1.6, 0.04)},
	"house_foursquare": {"lot": 11.5, "w": 9.0, "d": 10.0, "h": 9.5, "door": Vector3(0.0, 0.8, 0.0),
		"ramp": [-1.0, 1.0, 0.8, 2.6, 3.72], "boxes": [[Vector3(0.0, 0.4, 1.3), Vector3(9.0, 0.8, 2.6)]],
		"number": Vector3(1.15, 2.4, 0.04)},
	"house_splitlevel": {"lot": 14.0, "w": 12.0, "d": 9.0, "h": 6.6, "door": Vector3(1.1, 0.1, 0.0), "ramp": [], "boxes": []},
	"house_laneway": {"lot": 9.0, "w": 6.4, "d": 8.5, "h": 8.8, "door": Vector3(-1.1, 0.36, 0.0),
		"ramp": [-1.4, -0.2, 0.36, 1.8, 2.36], "boxes": [[Vector3(-0.6, 0.18, 0.9), Vector3(4.2, 0.36, 1.8)]],
		"number": Vector3(0.7, 1.75, 0.04)},
	"house_bungalow": {"lot": 12.5, "w": 10.4, "d": 9.6, "h": 7.0, "door": Vector3(0.0, 1.3, 0.0),
		"ramp": [-0.6, 0.6, 1.3, 1.5, 3.46], "boxes": [[Vector3(0.0, 0.65, 0.75), Vector3(2.0, 1.3, 1.5)]]},
	# Imported models (tools/prepare_new_houses.py -> assets/houses/, values from its houses.json):
	# "hull" replaces the single body collision box, "number" is the beside-door house number,
	# "door2" the upper flat's balcony door of the up/down duplex.
	"house_suburban": {"lot": 18.0, "w": 16.43, "d": 14.68, "h": 7.0, "door": Vector3(-3.43, 0.04, -3.08), "ramp": [], "boxes": [],
		"hull": [[Vector3(2.425, 2.75, -4.55), Vector3(10.75, 5.5, 8.1)], [Vector3(2.0, 2.75, -0.25), Vector3(4.5, 5.5, 0.5)],
			[Vector3(-4.475, 2.6, -5.8), Vector3(3.05, 5.2, 5.6)], [Vector3(-1.0, 2.5, -9.3), Vector3(6.0, 5.0, 1.4)]],
		"number": Vector3(-5.05, 1.6, -2.95)},
	"house_duplex": {"lot": 12.5, "w": 10.2, "d": 16.32, "h": 8.03, "door": Vector3(-0.75, 0.51, -1.89), "door2": Vector3(-0.75, 3.22, -1.89),
		"ramp": [-1.45, -0.05, 0.51, 0.0, 0.84],
		"boxes": [[Vector3(-2.35, 0.255, -0.95), Vector3(4.9, 0.51, 1.9)], [Vector3(2.45, 0.255, -15.05), Vector3(4.7, 0.51, 1.9)]],
		"hull": [[Vector3(0.0, 3.0, -8.0), Vector3(9.6, 6.0, 12.2)], [Vector3(2.45, 3.0, -0.95), Vector3(4.7, 6.0, 1.9)],
			[Vector3(-2.35, 3.0, -15.05), Vector3(4.9, 6.0, 1.9)]],
		"number": Vector3(-1.62, 2.05, -1.85)},
	"house_farmhouse": {"lot": 12.5, "w": 10.35, "d": 7.1, "h": 6.8, "door": Vector3(-1.0, 0.52, -1.78),
		"ramp": [-1.75, 0.5, 0.52, 0.0, 0.95], "boxes": [[Vector3(1.65, 0.26, -0.89), Vector3(6.9, 0.52, 1.78)]],
		"hull": [[Vector3(-3.4, 3.0, -3.45), Vector3(3.2, 6.0, 6.9)], [Vector3(1.6, 3.0, -4.34), Vector3(6.8, 6.0, 5.12)]],
		"number": Vector3(-1.0, 2.85, -1.72)},
}
## Types built from imported models (detailed + _far LOD GLBs in assets/houses/).
const IMPORTED := ["house_suburban", "house_duplex", "house_farmhouse"]
## False = kit houses only (A/B performance comparisons); set before the first lots() call.
static var mix_imported := true
const BODY := ["5d6b82", "4f6b57", "b39a4e", "efece4", "8c3b30", "3a444c", "c9b99a", "7d8f9c", "5a6b45", "a35d3c", "d9cdb0", "6f7f8f"]
const STUCCO := ["e3d6bd", "d8c8a8", "efe8da", "cbb89a", "e6dccb"]
const TRIM := ["f2f0ea", "efe6cf", "f2f0ea", "1f2427", "d9d4c5"]
const DOOR := ["7a1f1f", "1f3a5a", "2f4a2f", "d9a93a", "1d1d1d", "6b4a2a", "2a5a5a"]
const ROOF := ["3a3b3d", "4a4036", "2c2f33", "5a5550", "47362c", "3c4247"]

static var _lots: Array[Dictionary] = []
static var _lanes: Array[Dictionary] = []
static var _forest: Array[Transform3D] = []
static var _exclusions: Array[Rect2] = []

## Rows: property line x, facing sign (+1 = house faces +x), lot depth, z range, zone, lane side x.
static func rows() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	var streets: Array = CityCatalog.CROSS_STREETS
	# North estate (Cedar Lane between the north road at z=48 and the first cross street).
	var north := Vector2(-248.0, 40.5)
	list.append({"line": -10.5, "s": 1, "depth": 23.0, "z": north, "zone": "north"})
	list.append({"line": 10.5, "s": -1, "depth": 23.0, "z": north, "zone": "north"})
	list.append({"line": -57.5, "s": -1, "depth": 17.5, "z": north, "zone": "estate"})
	list.append({"line": 57.5, "s": 1, "depth": 17.5, "z": north, "zone": "estate"})
	list.append({"line": -70.5, "s": 1, "depth": 22.0, "z": north, "zone": "estate"})
	list.append({"line": 70.5, "s": -1, "depth": 22.0, "z": north, "zone": "estate"})
	for b in range(streets.size() - 1):
		var span := Vector2(streets[b + 1] + 10.0, streets[b] - 10.0)
		list.append({"line": -10.5, "s": 1, "depth": 23.0, "z": span, "zone": "south"})
		list.append({"line": 10.5, "s": -1, "depth": 23.0, "z": span, "zone": "south"})
		list.append({"line": -55.0, "s": -1, "depth": 15.5, "z": span, "zone": "inner"})
		list.append({"line": 55.0, "s": 1, "depth": 15.5, "z": span, "zone": "inner"})
		list.append({"line": -73.5, "s": 1, "depth": 22.0, "z": span, "zone": "outer"})
		list.append({"line": 73.5, "s": -1, "depth": 22.0, "z": span, "zone": "outer"})
	return list

static func exclusions() -> Array[Rect2]:
	if not _exclusions.is_empty(): return _exclusions
	var r: Array[Rect2] = []
	for c in CityCatalog.CROSS_STREETS + [48.0]: r.append(Rect2(-125, c - 10, 250, 20))
	for z in CityLayout.PARKS:
		for x in [-44.0, 44.0]: r.append(Rect2(x - 10, z - 17, 20, 34))  # park garden is +-10 x, +-16 z
	for x in [-64.0, 64.0]: r.append(Rect2(x - 27, -172, 54, 54))  # roundabout parks
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i]
		r.append(Rect2(p.x - 17, p.z - 10, 21, 17))
	for at in ShopCatalog.LOCATIONS.values() + [Vector3(-40, 0, 32)]:
		r.append(Rect2(at.x - 9.5, at.z - 6.5, 19, 21))
	r.append(Rect2(8, 14, 23, 33))  # starter home lot, walkway and gear kiosk
	for b in CityLayout.buildings(): r.append(CityLayout.footprint(b).grow(1.0))
	_exclusions = r
	return r

static func blocked(rect: Rect2) -> bool:
	if rect.position.x < -118 or rect.end.x > 118 or rect.position.y < -707 or rect.end.y > 67: return true
	for e in exclusions():
		if e.intersects(rect): return true
	# Curved estate roads with their 13 m sidewalk ribbons.
	var inner := rect.grow(-0.3)
	for p in [inner.position, Vector2(inner.end.x, inner.position.y), inner.end, Vector2(inner.position.x, inner.end.y), inner.get_center()]:
		if CityCatalog.near_estate_road(Vector3(p.x, 0, p.y), 6.6): return true
	return false

static func lots() -> Array[Dictionary]:
	if not _lots.is_empty(): return _lots
	var rng := RandomNumberGenerator.new()
	rng.seed = 60317
	# Imported house types are mixed in by their own generator, so the kit sequence stays put
	# wherever they don't fit.
	var mix := RandomNumberGenerator.new()
	mix.seed = 82311
	var list: Array[Dictionary] = []
	for row in rows():
		var s: int = row.s
		var depth: float = row.depth
		var z: float = row.z.y
		var corner := true  # first lot after a cross street, park or shop
		while z > row.z.x:
			var type := pick_type(rng, row.zone, depth)
			var alt := pick_imported(mix, row.zone, depth, corner)
			var x0: float = row.line
			var x1: float = row.line - s * depth
			if alt != "":
				var alt_width: float = TYPES[alt].lot
				var alt_rect := Rect2(minf(x0, x1), z - alt_width, absf(x1 - x0), alt_width)
				if z - alt_width >= row.z.x and not blocked(alt_rect): type = alt
			var spec: Dictionary = TYPES[type]
			var width: float = spec.lot
			var rect := Rect2(minf(x0, x1), z - width, absf(x1 - x0), width)
			if z - width < row.z.x: break
			if blocked(rect):
				z -= 2.0
				corner = true
				continue
			corner = false
			var yaw := s * PI / 2.0
			var basis := Basis(Vector3.UP, yaw)
			var front := Vector3(row.line - s * SETBACK, 0, z - width / 2.0)
			var rear_depth := depth - SETBACK - float(spec.d)
			var rear := "patio"
			if rear_depth >= 6.6 and rng.randf() < 0.5: rear = "garage"
			elif rng.randf() < 0.35: rear = "shed"
			var stucco: bool = type in ["house_special", "house_splitlevel"]
			list.append({"type": type, "front": front, "yaw": yaw, "facing": basis * Vector3.BACK, "line_x": row.line, "s": s,
				"lot": rect, "depth": depth, "width": width, "rear": rear, "zone": row.zone,
				"fence": ["hedge", "picket", "", ""][rng.randi() % 4],
				"colours": {"body": Color(STUCCO[rng.randi() % STUCCO.size()] if stucco else BODY[rng.randi() % BODY.size()]),
					"trim": Color(TRIM[rng.randi() % TRIM.size()]), "door": Color(DOOR[rng.randi() % DOOR.size()]),
					"roof": Color(ROOF[rng.randi() % ROOF.size()])},
				"delivery": -1})
			z -= width
	assign_deliveries(list)
	_lots = list
	return list

static func pick_type(rng: RandomNumberGenerator, zone: String, depth: float) -> String:
	var weights: Dictionary = {"north": {"house_craftsman": 4, "house_foursquare": 3, "house_bungalow": 3, "house_special": 1},
		"south": {"house_craftsman": 3, "house_foursquare": 2, "house_bungalow": 2, "house_special": 3, "house_splitlevel": 2, "house_modern": 2},
		"inner": {"house_laneway": 3, "house_modern": 2, "house_bungalow": 1},
		"outer": {"house_special": 3, "house_splitlevel": 3, "house_modern": 3, "house_bungalow": 2, "house_laneway": 1},
		"estate": {"house_modern": 2, "house_bungalow": 2, "house_craftsman": 2, "house_laneway": 1}}[zone]
	var total := 0
	for t in weights:
		if TYPES[t].d + SETBACK <= depth: total += weights[t]
	var pick := rng.randi() % total
	for t in weights:
		if TYPES[t].d + SETBACK > depth: continue
		pick -= weights[t]
		if pick < 0: return t
	return "house_laneway"

## Imported types: the big gambrel house takes 60% of corner lots (end of a block, beside a
## park), the up/down duplex and the farmhouse cottage about one mid-block lot in nine each.
## Always draws exactly one number so the sequence is stable.
static func pick_imported(rng: RandomNumberGenerator, zone: String, depth: float, corner: bool) -> String:
	var roll := rng.randf()
	if not mix_imported: return ""
	if corner and zone in ["north", "south", "outer"]:
		return "house_suburban" if roll < 0.6 and TYPES.house_suburban.d + SETBACK <= depth else ""
	if roll < 0.11 and zone != "inner" and TYPES.house_duplex.d + SETBACK <= depth: return "house_duplex"
	if roll > 0.89 and TYPES.house_farmhouse.d + SETBACK <= depth: return "house_farmhouse"
	return ""

## The 36 original delivery addresses move to the nearest street-facing Cedar Lane lot on the
## same side, in address order, so routes and distances stay comparable.
static func assign_deliveries(list: Array[Dictionary]) -> void:
	for i in range(36):
		var old := legacy_address(i)
		var best := -1
		var best_d := INF
		for k in range(list.size()):
			var lot: Dictionary = list[k]
			if lot.delivery >= 0 or absf(lot.line_x) != 10.5 or signf(lot.line_x) != signf(old.x): continue
			var d := absf(lot.front.z - old.z)
			if d < best_d:
				best_d = d
				best = k
		var chosen: Dictionary = list[best]
		chosen.delivery = i
		chosen.fence = "picket" if chosen.fence == "hedge" else chosen.fence
		chosen.door = door_point(chosen)

static func legacy_address(index: int) -> Vector3:
	if index >= 12:
		@warning_ignore("integer_division")
		var row := (index - 12) / 2
		@warning_ignore("integer_division")
		return Vector3(-21 if index % 2 == 0 else 21, 1, -282.7 - row * 28 - (row / 4) * 28)
	if index < 6:
		return Vector3(-21 if index < 3 else 21, 1, -10.7 - (index % 3) * 28)
	return Vector3(-21 if index < 9 else 21, 1, [-122.7, -150.7, -206.7][(index - 6) % 3])

static func transform(lot: Dictionary) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, lot.yaw), lot.front)

## World point 12 cm in front of the door surface at mid-door height (delivery address).
static func door_point(lot: Dictionary) -> Vector3:
	var d: Vector3 = TYPES[lot.type].door
	return transform(lot) * Vector3(d.x, d.y + 1.0, d.z + 0.12)

static func delivery_lot(index: int) -> Dictionary:
	for lot in lots():
		if lot.delivery == index: return lot
	return {}

## House body footprint (with porch/stairs) in world xz.
static func house_rect(lot: Dictionary) -> Rect2:
	var spec: Dictionary = TYPES[lot.type]
	var t := transform(lot)
	var rect := Rect2(Vector2(lot.front.x, lot.front.z), Vector2.ZERO)
	for c in [Vector3(-spec.w / 2, 0, 4.0), Vector3(spec.w / 2, 0, 4.0), Vector3(-spec.w / 2, 0, -spec.d), Vector3(spec.w / 2, 0, -spec.d)]:
		var p: Vector3 = t * c
		rect = rect.expand(Vector2(p.x, p.z))
	return rect

## Rear lanes: one per contiguous run of lots backing onto the same lane line.
static func lanes() -> Array[Dictionary]:
	if not _lanes.is_empty(): return _lanes
	# Group lots by lane line, then split into runs wherever lots stop (cross streets, parks,
	# shops): a lane never crosses a street or cuts through another block.
	var by_line := {}
	for lot in lots():
		if lot.zone == "inner": continue
		var x: float = lot.line_x - lot.s * (lot.depth + 3.0)
		var key := "%d" % roundi(x)
		if not by_line.has(key): by_line[key] = {"x": x, "spans": []}
		by_line[key].spans.append(Vector2(lot.lot.position.y, lot.lot.end.y))
	for key in by_line:
		var spans: Array = by_line[key].spans
		spans.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
		var run: Vector2 = spans[0]
		for i in range(1, spans.size() + 1):
			var next: Vector2 = spans[i] if i < spans.size() else Vector2(INF, INF)
			if next.x - run.y > 3.0:
				if run.y - run.x > 20.0:
					_lanes.append({"x": by_line[key].x, "z0": run.x, "z1": run.y, "width": 6.0})
				run = next
			else:
				run.y = maxf(run.y, next.y)
	return _lanes

## Forest on the city edges: firs and cedars on a jittered 5.5 m grid outside the lanes.
static func forest() -> Array[Transform3D]:
	if not _forest.is_empty(): return _forest
	var rng := RandomNumberGenerator.new()
	rng.seed = 9917
	var strips: Array[Rect2] = [Rect2(-117, -700, 15, 760), Rect2(102, -700, 15, 760)]
	for strip in strips:
		var z: float = strip.position.y
		while z < strip.end.y:
			var x: float = strip.position.x
			while x < strip.end.x:
				var p := Vector3(x + rng.randf_range(-1.8, 1.8), 0, z + rng.randf_range(-1.8, 1.8))
				var r := Rect2(p.x - 1.5, p.z - 1.5, 3, 3)
				var clear := true
				for e in exclusions():
					if e.intersects(r): clear = false
				for lot in lots():
					if lot.lot.grow(1.0).intersects(r): clear = false
				for lane in lanes():
					if absf(p.x - lane.x) < 4.5 and p.z > lane.z0 - 3 and p.z < lane.z1 + 3: clear = false
				if clear and not CityCatalog.near_estate_road(p, 9.0):
					var s := rng.randf_range(0.75, 1.35)
					var yaw := rng.randf() * TAU
					# The lowest branch tier spreads ~3.4 m (x scale): keep the whole crown off
					# the kit buildings beside the strips, not just the 3 m trunk square.
					var crown := Rect2(p.x - 3.5 * s, p.z - 3.5 * s, 7.0 * s, 7.0 * s)
					for b in CityLayout.buildings():
						if CityLayout.footprint(b).intersects(crown): clear = false
					if clear:
						_forest.append(Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * s), p))
				x += 5.5
			z += 5.5
	return _forest

## True on any house, garage or lane (grass and other systems keep clear of them).
static func blocked_point(p: Vector3) -> bool:
	for lot in lots():
		if house_rect(lot).grow(0.3).has_point(Vector2(p.x, p.z)): return true
	for lane in lanes():
		if absf(p.x - lane.x) < 3.0 and p.z > lane.z0 and p.z < lane.z1: return true
	return false
