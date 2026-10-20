class_name CityLayout
extends RefCounted
## Placement of city-kit buildings, following the urban transect:
##   suburb core (existing houses) -> townhouse terraces on the inner side of the side roads
##   -> walk-up apartments on the four estate lots -> mixed-use corridor along the downtown
##   connectors -> downtown (DowntownDistrict) -> civic campus.
## Every spec is scenery with closed doors; delivery destinations are unchanged.
## Coordinates: `front` is the centre of the street facade at ground level; the facade faces
## `yaw` (0 = +Z) and the building extends `depth` metres behind it.

const TOWNHOUSE_WIDTH := 5.0
const TOWNHOUSE_DEPTH := 10.0
const TOWNHOUSE_FACADE_X := 53.5 ## 1.5 m front gardens behind the side-road sidewalk (x 55-59)
const PARKS := [-330.0, -470.0, -590.0]
const PARK_CLEARANCE := 20.0 ## park garden is +-16 m in z, plus a 4 m path

static var _cache: Array[Dictionary] = []

static func buildings() -> Array[Dictionary]:
	if not _cache.is_empty(): return _cache
	var list: Array[Dictionary] = []
	# Terraces: inner side of both side roads, in each block between cross streets,
	# leaving the pocket parks and the junction corners clear.
	var streets: Array = CityCatalog.CROSS_STREETS
	for b in range(streets.size() - 1):
		var north: float = streets[b] - 11.0
		var south: float = streets[b + 1] + 11.0
		var park: float = PARKS[b]
		for span in [Vector2(park + PARK_CLEARANCE, north), Vector2(south, park - PARK_CLEARANCE)]:
			for side in [-1, 1]:
				_terraces(list, span, side, b)
	# Walk-ups replace the four estate apartment blocks (same 16 m frontage, entrance +Z).
	var lots := [[-92, -110, 4, 0, "CEDAR COURT"], [-92, -190, 4, 1, "ORCHARD HOUSE"], [92, -110, 6, 2, "PARKSIDE APARTMENTS"], [92, -190, 6, 1, "LINDEN MANSIONS"]]
	for lot in lots:
		list.append({"type": "walkup", "front": Vector3(lot[0], 0, lot[1] + 7.5), "yaw": 0.0, "bays": 4, "depth": 16.0,
			"floors": lot[2], "style": lot[3], "name": lot[4]})
	# Mixed-use corridor: both sides of each downtown connector (x 76-116).
	var names := ["Alder Books", "Copper Pot Deli", "Harbor Cycles", "Fern & Thread", "Union Bakery", "Northline Optics", "Kestrel Coffee", "Tidewater Florist"]
	var serial := 0
	for c in streets:
		for side in [-1, 1]:
			for lot in [[84.0, 4], [106.0, 5]]:
				var z: float = c + side * 11.0
				list.append({"type": "midrise", "front": Vector3(lot[0], 0, z), "yaw": 0.0 if side < 0 else PI,
					"bays": lot[1], "depth": 16.0, "floors": 4 + (serial * 5 + 1) % 3, "style": (serial * 2 + 1) % 3,
					"office": serial % 4 == 3, "shop": names[serial % names.size()], "id": serial})
				serial += 1
	_cache = list
	return list

static func _terraces(list: Array[Dictionary], span: Vector2, side: int, block: int) -> void:
	# span = (south z, north z) with south < north; split into rows of at most 7 units.
	var length := span.y - span.x - 2.0
	var units := int(length / TOWNHOUSE_WIDTH)
	if units < 3: return
	var rows := ceili(units / 7.0)
	@warning_ignore("integer_division")
	var per_row := units / rows
	var gap := (length - rows * per_row * TOWNHOUSE_WIDTH) / maxf(rows - 1, 1) if rows > 1 else 0.0
	var cursor := span.x + 1.0 + (length - rows * per_row * TOWNHOUSE_WIDTH - gap * (rows - 1)) * 0.5
	for r in range(rows):
		var row_length := per_row * TOWNHOUSE_WIDTH
		var center_z := cursor + row_length * 0.5
		list.append({"type": "terrace", "front": Vector3(side * TOWNHOUSE_FACADE_X, 0, center_z),
			"yaw": side * PI / 2.0, "units": per_row, "depth": TOWNHOUSE_DEPTH, "style": (block + r + (1 if side > 0 else 0)) % 3})
		cursor += row_length + gap

## Width of the street facade in metres.
static func frontage(b: Dictionary) -> float:
	if b.type == "terrace": return b.units * TOWNHOUSE_WIDTH
	return b.bays * 4.0

## World-space footprint rectangle (x, z), including front steps.
static func footprint(b: Dictionary) -> Rect2:
	var basis := Basis(Vector3.UP, b.yaw)
	var half := frontage(b) * 0.5
	var corners := [Vector3(-half, 0, 1.0), Vector3(half, 0, 1.0), Vector3(-half, 0, -b.depth), Vector3(half, 0, -b.depth)]
	var rect := Rect2(Vector2(b.front.x, b.front.z), Vector2.ZERO)
	for c in corners:
		var p: Vector3 = b.front + basis * c
		rect = rect.expand(Vector2(p.x, p.z))
	return rect

static var _grid: Dictionary = {}
const GRID := 16.0

## True inside any kit building footprint (plus margin). Spatially hashed: the grass
## instancer calls this for every candidate clump.
static func blocked(p: Vector3, margin: float = 0.5) -> bool:
	if _grid.is_empty():
		var rects: Array[Rect2] = []
		for b in buildings(): rects.append(footprint(b).grow(margin))
		# Residential houses (with porches) and rear lanes share the same hash.
		for lot in ResidentialLayout.lots(): rects.append(ResidentialLayout.house_rect(lot).grow(margin))
		for lane in ResidentialLayout.lanes(): rects.append(Rect2(lane.x - 3.0, lane.z0, 6.0, lane.z1 - lane.z0))
		for rect in rects:
			for gx in range(floori(rect.position.x / GRID), floori(rect.end.x / GRID) + 1):
				for gz in range(floori(rect.position.y / GRID), floori(rect.end.y / GRID) + 1):
					var key := Vector2i(gx, gz)
					if not _grid.has(key): _grid[key] = []
					_grid[key].append(rect)
	var cell: Array = _grid.get(Vector2i(floori(p.x / GRID), floori(p.z / GRID)), [])
	for rect: Rect2 in cell:
		if rect.has_point(Vector2(p.x, p.z)): return true
	return false
