extends SceneTree
## Residential conflict audit: every house type (the 7 kit types from build_houses.py and the 3
## imported ones from tools/prepare_new_houses.py) on real lots, as HouseInstancer places them -
## house near LOD, garden bed, fences / hedges, garage, shed, patio, bins, front walk slab, address
## post with its GlyphText plates, mailbox - plus the lawn (ground top y = 0) and the rear lane, in
## world space. Runs headless: the instancer records every placed piece (HouseInstancer.record).
##
##   (a) COPLANAR  overlapping faces of different pieces / materials (or duplicated faces of one
##       piece) within 1.5 cm and 10 degrees of each other. Same facing = conflict; opposite facing
##       only when one side is double-sided (with back-face culling one of the two is never drawn,
##       those back-to-back contacts are reported as info).
##   (b) PIERCING  facade skin (siding / stucco / brick / cedar, glass, door leaves, garage doors)
##       crossing another part's face by more than 1 cm on both sides (boards through a window
##       frame or a wall plane, a lamp sunk into a wall).
##   (c) OPENINGS / ENDS  wall cladding in front of a window or door (inside its rectangle), open
##       ends of modelled siding boards (no trim within 20 cm in front of a board's end grain) and
##       outside corners of horizontal lap / shingle walls without a corner board.
##   (d) LOD       Godot's own visibility-range logic (distance to each node's AABB centre,
##       hysteresis margins, visibility parents) replayed along 24 approach/leave paths per house:
##       steps where two levels (near / far / massing) of the same house are drawn at once, none is
##       drawn, or only some material parts of a level are drawn.
## usage: godot --headless --path . --script res://tests/house_conflict_test.gd [-- verbose] [-- old-lod]
const TOL := 0.015
const COS10 := 0.98481
const AREA_MIN := 0.0004
const PIERCE := 0.01
## Below this separation two surfaces share the depth buffer (true z-fighting); between FIGHT and
## TOL they are "near" (flicker risk at distance / in shadows) unless the farther face is buried.
const FIGHT := 0.004
const CELL := 0.3
const SKIN := ["KitLapSiding", "KitShingleSiding", "KitBoardBatten", "KitHouseStucco", "KitSidingPaint", "KitCedar", "KitBrickRed",
	"KitGlass", "KitDoorPaint", "KitDoorWood", "KitGaragePaint"]
const BODY := ["KitLapSiding", "KitShingleSiding", "KitBoardBatten", "KitHouseStucco", "KitSidingPaint", "KitCedar", "KitBrickRed"]
const LAP := ["KitLapSiding", "KitShingleSiding", "KitSidingPaint"]
const OPENING := ["KitGlass", "KitDoorPaint", "KitDoorWood", "KitGaragePaint"]
const DOUBLE_SIDED := ["KitClearGlass", "KitFoliage", "KitConifer", "KitHedge"]

var verbose := false
var checks := 0
var failed := 0

# Triangle soup of one lot (parallel arrays).
var ta := PackedVector3Array()
var tb := PackedVector3Array()
var tc := PackedVector3Array()
var tn := PackedVector3Array()
var tarea := PackedFloat32Array()
var towner := PackedInt32Array()
var tmat := PackedStringArray()
var owners := PackedStringArray()
var grid := {}
var stamp := PackedInt32Array()
var ray_seen := PackedInt32Array()
var ray_id := 0

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
		print("FAIL: ", what)

func _initialize() -> void: call_deferred("run")

func reset() -> void:
	ta.clear(); tb.clear(); tc.clear(); tn.clear(); tarea.clear(); towner.clear(); tmat.clear(); owners.clear()
	grid.clear()

func add_tri(a: Vector3, b: Vector3, c: Vector3, owner: int, mat: String) -> void:
	# Godot's front faces wind clockwise: outward normal (c - a) x (b - a).
	var n := (c - a).cross(b - a)
	var area := n.length() * 0.5
	if area < 1e-6: return
	# Faces looking down onto the ground (bottoms of things standing on it) are never seen.
	if n.normalized().y < -0.7 and maxf(a.y, maxf(b.y, c.y)) < 0.06: return
	ta.append(a); tb.append(b); tc.append(c); tn.append(n.normalized()); tarea.append(area)
	towner.append(owner); tmat.append(mat)

func add_mesh(mesh: Mesh, xf: Transform3D, label: String, override_mat: String = "") -> void:
	if mesh == null: return
	for s in range(mesh.get_surface_count()):
		var arrays := mesh.surface_get_arrays(s)
		if arrays.is_empty(): continue
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		var m := mesh.surface_get_material(s)
		var mat := override_mat if override_mat != "" else (m.resource_name.get_slice(".", 0) if m != null and m.resource_name != "" else "s%d" % s)
		var owner := owners.size()
		owners.append("%s/%s" % [label, mat])
		var count := idx.size() if idx.size() > 0 else verts.size()
		for k in range(0, count - 2, 3):
			var i0 := idx[k] if idx.size() > 0 else k
			var i1 := idx[k + 1] if idx.size() > 0 else k + 1
			var i2 := idx[k + 2] if idx.size() > 0 else k + 2
			add_tri(xf * verts[i0], xf * verts[i1], xf * verts[i2], owner, mat)

func cell_of(p: Vector3) -> Vector3i:
	return Vector3i(floori(p.x / CELL), floori(p.y / CELL), floori(p.z / CELL))

func build_grid() -> void:
	grid.clear()
	stamp.resize(ta.size())
	stamp.fill(-1)
	ray_seen.resize(ta.size())
	ray_seen.fill(-1)
	for i in range(ta.size()):
		var lo := ta[i].min(tb[i]).min(tc[i]) - Vector3.ONE * (TOL + 0.001)
		var hi := ta[i].max(tb[i]).max(tc[i]) + Vector3.ONE * (TOL + 0.001)
		var c0 := cell_of(lo)
		var c1 := cell_of(hi)
		var n := tn[i]
		var big := (c1.x - c0.x + 1) * (c1.y - c0.y + 1) * (c1.z - c0.z + 1) > 64
		var reach := CELL * 0.87 + TOL + 0.002
		for x in range(c0.x, c1.x + 1):
			for y in range(c0.y, c1.y + 1):
				for z in range(c0.z, c1.z + 1):
					var key := Vector3i(x, y, z)
					if big:
						var centre := (Vector3(key) + Vector3.ONE * 0.5) * CELL
						if absf(n.dot(centre - ta[i])) > reach: continue
					if not grid.has(key): grid[key] = PackedInt32Array()
					var list: PackedInt32Array = grid[key]
					list.append(i)
					grid[key] = list

## Triangles near triangle i (deduplicated).
func neighbours(i: int, extra: float = 0.0) -> PackedInt32Array:
	var out := PackedInt32Array()
	var lo := ta[i].min(tb[i]).min(tc[i]) - Vector3.ONE * (TOL + extra)
	var hi := ta[i].max(tb[i]).max(tc[i]) + Vector3.ONE * (TOL + extra)
	var c0 := cell_of(lo)
	var c1 := cell_of(hi)
	var n := tn[i]
	var big := (c1.x - c0.x + 1) * (c1.y - c0.y + 1) * (c1.z - c0.z + 1) > 64
	var reach := CELL * 0.87 + TOL + extra + 0.002
	for x in range(c0.x, c1.x + 1):
		for y in range(c0.y, c1.y + 1):
			for z in range(c0.z, c1.z + 1):
				var key := Vector3i(x, y, z)
				if not grid.has(key): continue
				if big and extra == 0.0:
					var centre := (Vector3(key) + Vector3.ONE * 0.5) * CELL
					if absf(n.dot(centre - ta[i])) > reach: continue
				for j: int in grid[key]:
					if stamp[j] == i: continue
					stamp[j] = i
					out.append(j)
	return out

## Point p (already near the plane of j) inside triangle j (1 mm in from its edges)?
func inside(p: Vector3, j: int) -> bool:
	var a := ta[j]
	var v0 := tc[j] - a
	var v1 := tb[j] - a
	var v2 := p - a
	var d00 := v0.dot(v0)
	var d01 := v0.dot(v1)
	var d11 := v1.dot(v1)
	var d20 := v2.dot(v0)
	var d21 := v2.dot(v1)
	var den := d00 * d11 - d01 * d01
	if absf(den) < 1e-14: return false
	var u := (d11 * d20 - d01 * d21) / den
	var v := (d00 * d21 - d01 * d20) / den
	var w := 1.0 - u - v
	# Barycentric margins scaled to ~1 mm along each edge's height.
	var area2 := sqrt(den)
	var mu := 0.001 * v1.length() / area2
	var mv := 0.001 * v0.length() / area2
	var mw := 0.001 * (tb[j] - tc[j]).length() / area2
	return u > mu and v > mv and w > mw

## Sample points on triangle i, about `spacing` apart (at least 4, at most 256).
func samples(i: int, spacing: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	var a := ta[i]
	var b := tb[i]
	var c := tc[i]
	var longest := maxf((b - a).length(), maxf((c - b).length(), (a - c).length()))
	var n := clampi(ceili(longest / spacing), 2, 22)
	for s in range(n):
		for t in range(n - s):
			var u := (float(s) + 0.33) / float(n)
			var v := (float(t) + 0.33) / float(n)
			if u + v > 0.999: continue
			out.append(a + (b - a) * u + (c - a) * v)
	return out

## Neighbouring facets of one piece (a vertex within 3 mm): one surface, not an overlap.
func shares_vertex(i: int, j: int) -> bool:
	var shared := 0
	for p in [ta[i], tb[i], tc[i]]:
		for q in [ta[j], tb[j], tc[j]]:
			if (p as Vector3).distance_squared_to(q) < 9e-6:
				shared += 1
				break
	return shared > 0 and shared < 3      # all three shared = a duplicated face

## Ray from p along d (length len) against the soup; returns [triangle, distance] or [-1, INF].
func raycast(p: Vector3, d: Vector3, len: float, skip_owner: int = -1, only_owner: int = -1) -> Array:
	var best := -1
	var best_t := INF
	ray_id += 1
	var step := CELL * 0.25
	var steps := ceili(len / step)
	var last := Vector3i(1 << 30, 0, 0)
	for s in range(steps + 1):
		var q := p + d * minf(len, float(s) * step)
		var key := cell_of(q)
		if key == last or not grid.has(key): continue
		last = key
		for j: int in grid[key]:
			if ray_seen[j] == ray_id or towner[j] == skip_owner or (only_owner >= 0 and towner[j] != only_owner): continue
			ray_seen[j] = ray_id
			var e1 := tb[j] - ta[j]
			var e2 := tc[j] - ta[j]
			var h := d.cross(e2)
			var det := e1.dot(h)
			if absf(det) < 1e-12: continue
			var f := 1.0 / det
			var sv := p - ta[j]
			var u := f * sv.dot(h)
			if u < 0.0 or u > 1.0: continue
			var qv := sv.cross(e1)
			var v := f * d.dot(qv)
			if v < 0.0 or u + v > 1.0: continue
			var t := f * e2.dot(qv)
			if t > 0.0005 and t < len and t < best_t:
				best_t = t
				best = j
		if best >= 0 and best_t < float(s) * step - CELL: break
	return [best, best_t]

## All crossings of a ray with the faces of `owner`, sorted: [[t, triangle], ...]. Faces lying in
## the start point's own plane (within 1 mm, parallel) are skipped.
func crossings(p: Vector3, d: Vector3, len: float, owner: int) -> Array:
	var out: Array = []
	ray_id += 1
	var step := CELL * 0.25
	var steps := ceili(len / step)
	var last := Vector3i(1 << 30, 0, 0)
	for s in range(steps + 1):
		var key := cell_of(p + d * minf(len, float(s) * step))
		if key == last or not grid.has(key): continue
		last = key
		for j: int in grid[key]:
			if ray_seen[j] == ray_id or towner[j] != owner: continue
			ray_seen[j] = ray_id
			if absf(tn[j].dot(d)) > 0.99 and absf(tn[j].dot(p - ta[j])) < 0.001: continue
			var e1 := tb[j] - ta[j]
			var e2 := tc[j] - ta[j]
			var h := d.cross(e2)
			var det := e1.dot(h)
			if absf(det) < 1e-12: continue
			var f := 1.0 / det
			var sv := p - ta[j]
			var u := f * sv.dot(h)
			if u < 0.0 or u > 1.0: continue
			var qv := sv.cross(e1)
			var v := f * d.dot(qv)
			if v < 0.0 or u + v > 1.0: continue
			var t := f * e2.dot(qv)
			if t > 0.0002 and t < len: out.append([t, j])
	out.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
	return out

## p lies inside the closed part `owner`: going out along `front` the ray leaves that part (first
## crossing an exit, odd count) and going the other way it also leaves it through a face. Such a
## face, a few mm behind another part's face, is buried in that part - interpenetrating joinery
## (rails in posts, chair legs in seats, a glow box in its lamp) - not a visible overlap.
func inside_solid(p: Vector3, owner: int, front: Vector3) -> bool:
	var ahead := crossings(p, front, 1.0, owner)
	if ahead.is_empty() or ahead.size() % 2 == 0: return false
	if tn[ahead[0][1]].dot(front) <= 0.0: return false
	var behind := crossings(p, -front, 1.0, owner)
	return not behind.is_empty() and tn[behind[0][1]].dot(-front) > 0.0

func pair_label(i: int, j: int) -> String:
	var x := owners[towner[i]]
	var y := owners[towner[j]]
	var rx := RegEx.create_from_string("#[0-9]+")
	x = rx.sub(x, "", true)
	y = rx.sub(y, "", true)
	return "%s <-> %s" % ([x, y] if x < y else [y, x])

var local_xf := Transform3D.IDENTITY
var example_i := -1
var example_j := -1

func tri_text(i: int) -> String:
	if i < 0: return ""
	var inv := local_xf.affine_inverse()
	return "%s %s %s n%s" % [str((inv * ta[i]).snapped(Vector3.ONE * 0.001)), str((inv * tb[i]).snapped(Vector3.ONE * 0.001)), str((inv * tc[i]).snapped(Vector3.ONE * 0.001)), str((inv.basis * tn[i]).snapped(Vector3.ONE * 0.01))]

func add_finding(table: Dictionary, label: String, area: float, at: Vector3) -> void:
	if not table.has(label): table[label] = [0.0, at, 0, tri_text(example_i), tri_text(example_j)]
	table[label][0] = float(table[label][0]) + area
	table[label][2] = int(table[label][2]) + 1

## (a) and (b) over the whole soup.
func analyse_faces() -> Dictionary:
	var coplanar := {}
	var contact := {}
	var same_paint := {}
	var pierce := {}
	for i in range(ta.size()):
		var near := neighbours(i)
		var ni := tn[i]
		for j: int in near:
			if j <= i: continue
			var same_owner := towner[i] == towner[j]
			var nj := tn[j]
			var cosang := ni.dot(nj)
			if absf(cosang) >= COS10:
				if same_owner and shares_vertex(i, j): continue
				if tmat[i] == "Ground" and tmat[j] == "Ground": continue
				# j's vertices all beyond TOL on one side of i's plane: no overlap within TOL.
				var da := ni.dot(ta[j] - ta[i])
				var db := ni.dot(tb[j] - ta[i])
				var dc := ni.dot(tc[j] - ta[i])
				if (da > TOL and db > TOL and dc > TOL) or (da < -TOL and db < -TOL and dc < -TOL): continue
				var area := 0.0
				var at := Vector3.ZERO
				var max_gap := 0.0
				for dir in [[i, j], [j, i]]:
					var s: int = dir[0]
					var t: int = dir[1]
					var pts := samples(s, 0.05)
					var hits := 0
					for p in pts:
						var dist := tn[t].dot(p - ta[t])
						if absf(dist) >= TOL: continue
						if inside(p - tn[t] * dist, t):
							# More than FIGHT apart and the farther face buried inside the nearer one's closed
							# part (behind t: is p inside t's part; in front: is t's point inside s's part).
							if cosang > 0.0 and dist < -FIGHT and inside_solid(p, towner[t], tn[t]): continue
							if cosang > 0.0 and dist > FIGHT and inside_solid(p - tn[t] * dist, towner[s], tn[s]): continue
							hits += 1
							at = p
							max_gap = maxf(max_gap, absf(dist))
					area = maxf(area, tarea[s] * float(hits) / float(maxi(1, pts.size())))
				if area <= 0.0: continue
				var double := tmat[i] in DOUBLE_SIDED or tmat[j] in DOUBLE_SIDED
				example_i = i
				example_j = j
				# Faces of one part (one mesh surface of one instance = one paint and one tint: crossing
				# muntins, a casing stacked on its frame): (a) is about different parts / materials,
				# and the two faces shade the same - reported as "same part", not failed.
				# ...unless they lie in one plane (< FIGHT): then they share the depth buffer (what
				# tests/zfighting_test.gd flags) and count.
				if same_owner and cosang > 0.0 and max_gap >= FIGHT: add_finding(same_paint, pair_label(i, j), area, at)
				elif cosang > 0.0 or double: add_finding(coplanar, pair_label(i, j), area, at)
				else: add_finding(contact, pair_label(i, j), area, at)
			elif not same_owner and (tmat[i] in SKIN or tmat[j] in SKIN) and tmat[i] != tmat[j]:
				if (tmat[i] == "KitAsphaltShingles" or tmat[j] == "KitAsphaltShingles"): continue
				if tmat[i] == "Ground" or tmat[j] == "Ground": continue
				var depth := cross_depth(i, j)
				example_i = i
				example_j = j
				if depth > PIERCE: add_finding(pierce, pair_label(i, j), depth, (ta[i] + tb[i] + tc[i]) / 3.0)
	return {"coplanar": coplanar, "contact": contact, "pierce": pierce, "same_paint": same_paint}

## How far triangles i and j cross each other: the smaller of (how far each pokes through the
## other's plane on its less-deep side), measured only where they actually intersect.
func cross_depth(i: int, j: int) -> float:
	var di := PackedFloat32Array([tn[j].dot(ta[i] - ta[j]), tn[j].dot(tb[i] - ta[j]), tn[j].dot(tc[i] - ta[j])])
	if (di[0] > -PIERCE and di[1] > -PIERCE and di[2] > -PIERCE) or (di[0] < PIERCE and di[1] < PIERCE and di[2] < PIERCE): return 0.0
	var dj := PackedFloat32Array([tn[i].dot(ta[j] - ta[i]), tn[i].dot(tb[j] - ta[i]), tn[i].dot(tc[j] - ta[i])])
	if (dj[0] > -PIERCE and dj[1] > -PIERCE and dj[2] > -PIERCE) or (dj[0] < PIERCE and dj[1] < PIERCE and dj[2] < PIERCE): return 0.0
	# Intersection segments of each triangle with the other's plane, on the common line.
	var dir := tn[i].cross(tn[j])
	if dir.length() < 1e-6: return 0.0
	dir = dir.normalized()
	var si := segment(ta[i], tb[i], tc[i], di, dir)
	var sj := segment(ta[j], tb[j], tc[j], dj, dir)
	var lo := maxf(si.x, sj.x)
	var hi := minf(si.y, sj.y)
	if hi - lo < 0.02: return 0.0
	return minf(depth_of(di), depth_of(dj))

func depth_of(d: PackedFloat32Array) -> float:
	var pos := maxf(d[0], maxf(d[1], d[2]))
	var neg := -minf(d[0], minf(d[1], d[2]))
	return minf(pos, neg)

func segment(a: Vector3, b: Vector3, c: Vector3, d: PackedFloat32Array, dir: Vector3) -> Vector2:
	var pts := [a, b, c]
	var ts: Array[float] = []
	for k in range(3):
		var k2 := (k + 1) % 3
		var p: Vector3 = pts[k]
		var q: Vector3 = pts[k2]
		if (d[k] > 0.0) != (d[k2] > 0.0):
			var t := d[k] / (d[k] - d[k2])
			ts.append(dir.dot(p.lerp(q, t)))
	if ts.size() < 2: return Vector2(0, -1)
	return Vector2(minf(ts[0], ts[1]), maxf(ts[0], ts[1]))

## (c) cladding inside openings, open board ends, uncovered lap-siding corners.
func analyse_openings() -> Dictionary:
	var in_opening := {}
	var open_ends := {}
	var bare_corners := {}
	for g in range(ta.size()):
		if not tmat[g] in OPENING or absf(tn[g].y) > 0.25 or tarea[g] < 0.01: continue
		var ng := tn[g]
		for j: int in neighbours(g, 0.25):
			if not tmat[j] in BODY: continue
			var hits := 0
			var pts := samples(j, 0.04)
			for p in pts:
				var h := ng.dot(p - ta[g])
				if h < 0.003 or h > 0.25: continue
				if inside_margin(p - ng * h, g, 0.03): hits += 1
			example_i = g
			example_j = j
			if hits > 0: add_finding(in_opening, pair_label(g, j), tarea[j] * float(hits) / float(pts.size()), (ta[j] + tb[j] + tc[j]) / 3.0)
	# Board end grain: small vertical siding faces whose normal runs along the wall.
	for i in range(ta.size()):
		if tmat[i] != "KitSidingPaint" or absf(tn[i].y) > 0.3: continue
		var lo := ta[i].min(tb[i]).min(tc[i])
		var hi := ta[i].max(tb[i]).max(tc[i])
		if hi.y < 0.005: continue      # under the lawn
		var size := hi - lo
		var horizontal := Vector2(size.x, size.z).length()
		if horizontal > 0.05: continue
		var pts := samples(i, 0.03)
		var open := 0
		for p in pts:
			var hit := raycast(p + tn[i] * 0.001, tn[i], 0.2, towner[i])
			if hit[0] == -1 or tmat[hit[0]] in BODY: open += 1
		if open > 0:
			example_i = i
			example_j = -1
			add_finding(open_ends, "%s board end grain without trim" % owners[towner[i]].get_slice("#", 0), tarea[i] * float(open) / float(pts.size()), (ta[i] + tb[i] + tc[i]) / 3.0)
	# Outside corners of lap / shingle walls: vertical edges shared by two perpendicular wall faces.
	var edges := {}
	for i in range(ta.size()):
		if not tmat[i] in LAP or absf(tn[i].y) > 0.2: continue
		var pts := [ta[i], tb[i], tc[i]]
		for k in range(3):
			var p: Vector3 = pts[k]
			var q: Vector3 = pts[(k + 1) % 3]
			var e := q - p
			if e.length() < 0.08 or absf(e.normalized().y) < 0.985: continue
			var key := Vector2i(roundi(p.x / 0.03), roundi(p.z / 0.03))
			if not edges.has(key): edges[key] = []
			(edges[key] as Array).append([i, minf(p.y, q.y), maxf(p.y, q.y)])
	var done := {}
	for key: Vector2i in edges:
		var list: Array = edges[key]
		for x in range(list.size()):
			for y in range(x + 1, list.size()):
				var i: int = list[x][0]
				var j: int = list[y][0]
				if absf(tn[i].dot(tn[j])) > 0.3: continue
				var y0 := maxf(float(list[x][1]), float(list[y][1]))
				var y1 := minf(float(list[x][2]), float(list[y][2]))
				if y1 - y0 < 0.06: continue
				var corner := Vector3(float(key.x) * 0.03, 0, float(key.y) * 0.03)
				var ci := (ta[i] + tb[i] + tc[i]) / 3.0
				var cj := (ta[j] + tb[j] + tc[j]) / 3.0
				ci.y = 0; cj.y = 0
				# Convex (outside) corner: each face's normal points away from the other face.
				if tn[i].dot(cj - corner) > -0.01 or tn[j].dot(ci - corner) > -0.01: continue
				var bis := Vector3(tn[i].x + tn[j].x, 0, tn[i].z + tn[j].z).normalized()
				var dk := "%d_%d_%d" % [key.x, key.y, roundi(y0 * 50)]
				if done.has(dk): continue
				done[dk] = true
				var bare := 0
				var probes := 0
				var yy := y0 + minf(0.1, (y1 - y0) * 0.5)
				while yy < y1 - 0.02:
					probes += 1
					var start := corner + Vector3(0, yy, 0) + bis * 0.25
					var hit := raycast(start, -bis, 0.35)
					if hit[0] == -1 or tmat[hit[0]] in BODY: bare += 1
					yy += 0.4
				if bare > 0: add_finding(bare_corners, "%s outside corner without corner board" % tmat[i], (y1 - y0) * float(bare) / float(maxi(1, probes)), corner + Vector3(0, y0, 0))
	return {"in_opening": in_opening, "open_ends": open_ends, "bare_corners": bare_corners}

func inside_margin(p: Vector3, j: int, margin: float) -> bool:
	if not inside(p, j): return false
	# Distance from p to each edge of j must exceed `margin` (within the opening, not at its rim).
	var pts := [ta[j], tb[j], tc[j]]
	for k in range(3):
		var a: Vector3 = pts[k]
		var b: Vector3 = pts[(k + 1) % 3]
		var e := (b - a).normalized()
		var off := (p - a) - e * (p - a).dot(e)
		if off.length() < margin: return false
	return true

## (d) Replays Godot's visibility-range / visibility-parent logic for one house.
class Vis:
	var node: GeometryInstance3D
	var lod := ""
	var centre := Vector3.ZERO
	var state := false
	var hidden_close := false
	var dep_hidden := false
	var parent: Vis = null

func range_check(v: Vis, cam: Vector3) -> int:
	var n := v.node
	var dist := cam.distance_to(v.centre)
	var begin_off := -n.visibility_range_begin_margin
	var end_off := n.visibility_range_end_margin
	if not v.state:
		begin_off = -begin_off
		end_off = -end_off
	if n.visibility_range_end > 0.0 and dist > n.visibility_range_end + end_off:
		v.state = false
		return 1
	if n.visibility_range_begin > 0.0 and dist < n.visibility_range_begin + begin_off:
		v.state = false
		return -1
	v.state = true
	return 0

func analyse_lod(inst: HouseInstancer, lot: Dictionary) -> Dictionary:
	var cell := Vector2i(floori(lot.front.x / HouseInstancer.HOUSE_CELL), floori(lot.front.z / HouseInstancer.HOUSE_CELL))
	var key: String = inst.lot_lod_keys.get(lot.front, "%s|%d_%d" % [lot.type, cell.x, cell.y])
	var mkey := "massing|%d_%d" % [cell.x, cell.y]
	var vis: Array[Vis] = []
	var by_node := {}
	for child in inst.get_children():
		if not child is MultiMeshInstance3D or not child.has_meta("lod"): continue
		var k: String = child.get_meta("lod_key")
		if k != key and k != mkey: continue
		var v := Vis.new()
		v.node = child
		v.lod = child.get_meta("lod")
		var box: AABB = (child as GeometryInstance3D).custom_aabb
		if box.size != Vector3.ZERO: v.centre = (child as Node3D).global_transform * box.get_center()
		else: v.centre = (child.get_meta("aabb") as AABB).get_center()
		vis.append(v)
		by_node[child] = v
	for v in vis:
		if v.node.visibility_parent != NodePath(""):
			var p := v.node.get_node_or_null(v.node.visibility_parent)
			if p != null and by_node.has(p): v.parent = by_node[p]
	var order := {"massing": 0, "far": 1, "near": 2}
	vis.sort_custom(func(x: Vis, y: Vis) -> bool: return order[x.lod] < order[y.lod])
	var house: Vector3 = ResidentialLayout.transform(lot) * Vector3(0, 0, -float(ResidentialLayout.TYPES[lot.type].d) / 2.0)
	var overlap := 0
	var hole := 0
	var torn := 0
	var steps := 0
	for a in range(24):
		var dir := Vector3(cos(TAU * a / 24.0), 0, sin(TAU * a / 24.0))
		for v in vis:
			v.state = false
			v.hidden_close = false
			v.dep_hidden = false
		var path: Array[float] = []
		var r := 180.0
		while r > 2.0:
			path.append(r)
			r -= 0.25
		while r < 180.0:
			path.append(r)
			r += 0.25
		for dist in path:
			var cam := house + dir * dist + Vector3(0, 1.65, 0)
			var shown := {"near": 0, "far": 0, "massing": 0}
			var total := {"near": 0, "far": 0, "massing": 0}
			for v in vis:
				total[v.lod] += 1
				if v.parent != null and (v.parent.dep_hidden or not v.parent.hidden_close):
					v.dep_hidden = true
					v.hidden_close = false
					continue
				var rc := range_check(v, cam)
				v.hidden_close = rc == -1
				v.dep_hidden = rc == 1
				if rc == 0: shown[v.lod] += 1
			steps += 1
			var levels := 0
			for l in shown:
				if shown[l] > 0: levels += 1
				if shown[l] > 0 and shown[l] < total[l]: torn += 1
			if levels > 1: overlap += 1
			if levels == 0: hole += 1
	return {"overlap": overlap, "hole": hole, "torn": torn, "steps": steps, "nodes": vis.size()}

## lod "far" / "massing": that level of the lot's house instead (they are never drawn together
## with the near model or each other, see analyse_lod), with the lawn.
func gather(inst: HouseInstancer, lot: Dictionary, level := "near") -> void:
	reset()
	var distant := level != "near"
	var rect: Rect2 = (lot.lot as Rect2).grow(1.5)
	var n := 0
	for rec in inst.recorded:
		if distant and rec.lod != level: continue
		if not distant and (rec.lod == "far" or rec.lod == "massing"): continue
		var mesh: Mesh = rec.mesh
		var box := mesh.get_aabb()
		var xforms: Array[Transform3D] = rec.xforms
		for xf in xforms:
			var hit := false
			if String(rec.asset).begins_with("house_") or rec.asset == "massing":
				hit = rect.has_point(Vector2(xf.origin.x, xf.origin.z))
			else:
				var wb := xf * box
				hit = rect.intersects(Rect2(wb.position.x, wb.position.z, wb.size.x, wb.size.z))
			if not hit: continue
			add_mesh(mesh, xf, "%s#%d" % [rec.asset, n])
			n += 1
	# Plain nodes: walk slabs, lane surface, address posts, GlyphText numbers and plates, mailboxes.
	for node in ([] if distant else inst.find_children("*", "MeshInstance3D", true, false)):
		var mi := node as MeshInstance3D
		if mi.mesh == null: continue
		var wb: AABB = mi.global_transform * mi.mesh.get_aabb()
		if not rect.intersects(Rect2(wb.position.x, wb.position.z, wb.size.x, wb.size.z)): continue
		var label := String(mi.get_parent().name if mi.get_parent() != inst else mi.name).replace("@", "")
		var mat := ""
		if mi.material_override != null: mat = "Node%s" % mi.mesh.get_class()
		add_mesh(mi.mesh, mi.global_transform, "%s#%d" % [label, n], mat)
		n += 1
	# The lawn: ground box top at y = 0 over the lot.
	var owner := owners.size()
	owners.append("lawn/Ground")
	var r: Rect2 = lot.lot
	var p0 := Vector3(r.position.x, 0, r.position.y)
	var p1 := Vector3(r.end.x, 0, r.position.y)
	var p2 := Vector3(r.end.x, 0, r.end.y)
	var p3 := Vector3(r.position.x, 0, r.end.y)
	add_tri(p0, p1, p2, owner, "Ground")
	add_tri(p0, p2, p3, owner, "Ground")
	# Fix the winding so the lawn faces up.
	for k in [ta.size() - 2, ta.size() - 1]:
		if tn[k].y < 0:
			var tmp := tb[k]
			tb[k] = tc[k]
			tc[k] = tmp
			tn[k] = -tn[k]
	build_grid()

func pick_lots(type: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var wants := ["delivery", "garage", "shed", "patio"]
	for want in wants:
		for lot in ResidentialLayout.lots():
			if lot.type != type or out.has(lot): continue
			var ok := false
			match want:
				"delivery": ok = lot.delivery >= 0
				_: ok = lot.rear == want and lot.fence != ""
			if ok:
				out.append(lot)
				break
		if out.size() >= 2: break
	if out.is_empty():
		for lot in ResidentialLayout.lots():
			if lot.type == type:
				out.append(lot)
				break
	return out

func report(title: String, table: Dictionary, limit: int = 12) -> void:
	var keys := table.keys()
	keys.sort_custom(func(x, y): return float(table[x][0]) > float(table[y][0]))
	var inv := local_xf.affine_inverse()
	for k in keys.slice(0, limit if not verbose else 400):
		print("      %-9s %8.4f  x%-4d %s  at %s (local %s)" % [title, float(table[k][0]), int(table[k][2]), k, str((table[k][1] as Vector3).snapped(Vector3.ONE * 0.01)), str((inv * (table[k][1] as Vector3)).snapped(Vector3.ONE * 0.01))])
		if verbose and table[k].size() > 3: print("          A ", table[k][3], "
          B ", table[k][4])

## Findings (triangle pairs / faces) over all labels whose total exceeds `minimum`.
func count_above(table: Dictionary, minimum: float) -> int:
	var n := 0
	for k in table:
		if float(table[k][0]) > minimum: n += int(table[k][2])
	return n

func run() -> void:
	var args := OS.get_cmdline_user_args()
	verbose = args.has("verbose")
	if args.has("old-lod"): HouseInstancer.lod_parents = false
	var only := ""
	for a in args:
		if String(a).begins_with("house_"): only = a
	HouseInstancer.record = true
	var inst := HouseInstancer.new()
	inst.name = "Residences"
	root.add_child(inst)
	await process_frame
	var started := Time.get_ticks_msec()
	var summary := {}
	for type: String in ResidentialLayout.TYPES:
		if only != "" and type != only: continue
		var totals := {"coplanar": 0, "pierce": 0, "in_opening": 0, "open_ends": 0, "bare_corners": 0, "lod": 0, "contact": 0, "distant": 0}
		for lot in pick_lots(type):
			gather(inst, lot)
			local_xf = ResidentialLayout.transform(lot)
			example_i = -1
			example_j = -1
			var faces := analyse_faces()
			var ops := analyse_openings()
			var lod := analyse_lod(inst, lot)
			var c := count_above(faces.coplanar, AREA_MIN)
			var p := count_above(faces.pierce, 0.0)
			var o := count_above(ops.in_opening, 0.0005)
			var e := count_above(ops.open_ends, 0.0)
			var b := count_above(ops.bare_corners, 0.0)
			var lod_bad: int = lod.overlap + lod.hole + lod.torn
			print("LOT %s at %s rear=%s fence=%s delivery=%d: %d tris | coplanar %d, piercing %d, cladding in openings %d, open board ends %d, bare corners %d, LOD overlap/hole/torn %d/%d/%d of %d steps (%d nodes) | back-to-back contacts %d" % [
				type, str(lot.front), lot.rear, lot.fence, lot.delivery, ta.size(), c, p, o, e, b, lod.overlap, lod.hole, lod.torn, lod.steps, lod.nodes, faces.contact.size()])
			report("coplanar", faces.coplanar)
			report("pierce", faces.pierce)
			report("opening", ops.in_opening)
			report("end", ops.open_ends)
			report("corner", ops.bare_corners)
			if verbose: report("contact", faces.contact, 400)
			if not (faces.same_paint as Dictionary).is_empty(): print("    same-part layered faces (one mesh surface of one instance; reported only): %d" % count_above(faces.same_paint, AREA_MIN))
			# Far LOD (imported houses, 45-110 m) and massing (beyond 110 m), each on the lawn.
			for level in ["far", "massing"]:
				gather(inst, lot, level)
				var far_faces := analyse_faces()
				var fc := count_above(far_faces.coplanar, AREA_MIN)
				print("    %s: %d tris, coplanar %d" % [level, ta.size(), fc])
				report(level, far_faces.coplanar)
				totals.distant += fc
			totals.coplanar += c
			totals.pierce += p
			totals.in_opening += o
			totals.open_ends += e
			totals.bare_corners += b
			totals.lod += lod_bad
			totals.contact += (faces.contact as Dictionary).size()
		summary[type] = totals
		check(totals.coplanar == 0, "%s: no coplanar / near-coplanar overlaps (%d)" % [type, totals.coplanar])
		check(totals.pierce == 0, "%s: no facade faces piercing other parts (%d)" % [type, totals.pierce])
		check(totals.in_opening == 0, "%s: no cladding in front of windows / doors (%d)" % [type, totals.in_opening])
		check(totals.open_ends == 0, "%s: no open siding board ends (%d)" % [type, totals.open_ends])
		check(totals.bare_corners == 0, "%s: lap / shingle outside corners have corner boards (%d)" % [type, totals.bare_corners])
		check(totals.distant == 0, "%s: far LOD / massing free of coplanar overlaps (%d)" % [type, totals.distant])
		check(totals.lod == 0, "%s: exactly one LOD level drawn at every distance (%d bad steps)" % [type, totals.lod])
	print("HOUSE CONFLICT SUMMARY ", JSON.stringify(summary))
	print("time %.1f s" % [float(Time.get_ticks_msec() - started) / 1000.0])
	print("HOUSE CONFLICT %s: %d checks, %d failures" % ["PASS" if failed == 0 else "FAIL", checks, failed])
	quit(1 if failed else 0)
