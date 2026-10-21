class_name CitizenRoutes
extends RefCounted
static var graph: AStar3D
static var points := {}
static var crossings := {}
static var destinations: Array[Dictionary]=[]
static var edges: Array[Vector2i]=[]
static func node(p: Vector3) -> int:
	var key := "%0.2f_%0.2f"%[p.x,p.z]
	if points.has(key): return points[key]
	var id := graph.get_available_point_id()
	graph.add_point(id,p)
	points[key]=id
	return id
static func link(a: int,b: int,crossing: bool=false) -> void:
	if a==b or graph.are_points_connected(a,b): return
	graph.connect_points(a,b)
	edges.append(Vector2i(a,b))
	if crossing:
		crossings[Vector2i(a,b)]=true
		crossings[Vector2i(b,a)]=true
static func prepare() -> void:
	if graph!=null: return
	graph=AStar3D.new()
	var corners: Array[int]=[]
	for block in DowntownCatalog.blocks():
		var l := block.position.x
		var r := block.end.x
		var top := block.position.y
		var bottom := block.end.y
		var ring := [Vector3(l-3,.1,top-3),Vector3(l+12,.1,top-1.2),Vector3(r-12,.1,top-1.2),Vector3(r+3,.1,top-3),Vector3(r+1.2,.1,top+12),Vector3(r+1.2,.1,bottom-12),Vector3(r+3,.1,bottom+3),Vector3(r-12,.1,bottom+1.2),Vector3(l+12,.1,bottom+1.2),Vector3(l-3,.1,bottom+3),Vector3(l-1.2,.1,bottom-12),Vector3(l-1.2,.1,top+12)]
		var ids: Array[int]=[]
		for i in range(ring.size()):
			ids.append(node(ring[i]))
			if i%3==0: corners.append(ids[-1])
		for i in range(ids.size()): link(ids[i],ids[(i+1)%ids.size()])
		var middle := block.get_center()
		var west := node(Vector3(l-1.2,.1,middle.y))
		var east := node(Vector3(r+1.2,.1,middle.y))
		var center := node(Vector3(middle.x,.1,middle.y))
		link(west,ids[10]); link(west,ids[11])
		link(east,ids[4]); link(east,ids[5])
		link(west,center); link(center,east)
		for side in [-1,1]:
			var court := node(Vector3(middle.x,.1,middle.y+side*18))
			link(center,court)
			destinations.append({"node":court,"type":"cafe","name":"Courtyard seating","building":-2})
	for a in corners:
		for b in corners:
			var p := graph.get_point_position(a)
			var q := graph.get_point_position(b)
			if p.distance_to(q)>12 and p.distance_to(q)<27 and (absf(p.x-q.x)<.1 or absf(p.z-q.z)<.1): link(a,b,true)
	for block_id in range(9):
		for building in DowntownCatalog.buildings(block_id):
			if building.closed or building.program!="mixed": continue
			var count := int(building.width/4)
			var entry_x := -count*2.0+2+int(count/2)*4
			var p: Vector3=building.root+Basis(Vector3.UP,building.yaw)*Vector3(entry_x+1.5,.1,1.2)
			var closest := Vector2i.ZERO
			var distance := INF
			for edge in edges:
				if crossings.has(edge): continue
				var q := Geometry3D.get_closest_point_to_segment(p,graph.get_point_position(edge.x),graph.get_point_position(edge.y))
				if q.distance_to(p)<distance:
					distance=q.distance_to(p)
					closest=edge
			var id := node(p)
			link(id,closest.x)
			link(id,closest.y)
			var type: String=["cafe","shop","home","work","cafe","transit","shop","work","shop","service"][building.id%10]
			destinations.append({"node":id,"type":type,"name":building.name,"building":building.id})
	# Civic entrances connect through pavements and explicit crossings of both roads.
	var civic_last := -1
	for z in [-267.0,-328.0,-389.0,-407.0,-468.0,-529.0,-547.0,-608.0,-669.0]:
		var id := node(Vector3(529,.1,z))
		if civic_last>=0: link(civic_last,id)
		civic_last=id
		if z in [-267.0,-389.0,-407.0,-529.0,-547.0,-669.0]:
			var west := node(Vector3(459,.1,z))
			var cycle_edge := node(Vector3(477,.1,z))
			var campus_edge := node(Vector3(511,.1,z))
			link(west,cycle_edge,true)
			link(cycle_edge,campus_edge)
			link(campus_edge,id,true)
		else:
			var entry := node(Vector3(560.8,.1,z-1.5))
			link(id,entry)
			destinations.append({"node":entry,"type":"service" if z!=-608 else "work","name":"Hospital" if z==-328 else ("Fire station" if z==-468 else "School"),"building":100})
	neighbourhood()

## Cedar neighbourhood sidewalks (x < 120): Atatürk Avenue both sides (x +-8.4, the walking line
## between the kerb furniture and the benches), the four cross streets (z = c +- 7) out to the
## side roads, and both sidewalks of each side road (x = +-64 +- 7). Signalled mid-block avenue
## crossings at z -93 / -177; every junction crossing is a zebra (gap acceptance, see
## CitizenBrain.crossing_open). Sidewalk centrelines follow neighborhood.gd's sidewalk boxes.
const AVENUE_Z := [35.0, 12.0, -38.0, -93.0, -140.0, -177.0, -220.0, -300.0, -350.0, -450.0, -500.0, -600.0, -640.0]
static func neighbourhood() -> void:
	var streets: Array = CityCatalog.CROSS_STREETS
	for x in [-8.4, 8.4]:
		var zs: Array[float] = []
		for z in AVENUE_Z: zs.append(z)
		for c in streets:
			zs.append(float(c) + 7.0)
			if c != streets[-1]: zs.append(float(c) - 7.0)
		zs.sort()
		zs.reverse()
		var previous := -1
		for z in zs:
			# Junction corners sit 0.5 m nearer the kerb: kerbside furniture stands on the
			# walking line at the cross streets.
			var corner := not (z in AVENUE_Z)
			var id := node(Vector3(signf(x)*7.9 if corner else x,.1,z))
			if previous>=0:
				var pz := graph.get_point_position(previous).z
				# Through a cross-street junction: a zebra across the side street.
				link(previous,id,absf(pz-z)==14.0 and streets.has(int(round((pz+z)*0.5))))
			previous=id
			if z in AVENUE_Z:
				destinations.append({"node":id,"type":"home" if x>0 else ("cafe" if z>-221 else "work"),"name":"Cedar neighbourhood","building":-1})
	for z in [-93.0,-177.0]: link(node(Vector3(-8.4,.1,z)),node(Vector3(8.4,.1,z)),true)
	for c in streets:
		for s in [-1.0, 1.0]:
			if c == streets[-1] and s < 0: continue   # the south side of the last street has no walk
			var z: float = c + s * 7.0
			for lx in [-1.0, 1.0]:
				var previous := -1
				for ax in [7.9, 20.0, 32.0, 44.0, 57.0]:
					var id := node(Vector3(lx * ax, .1, z))
					if previous >= 0: link(previous, id)
					previous = id
					if ax in [20.0, 44.0]:
						destinations.append({"node": id, "type": ["home", "shop", "home", "work"][posmod(int(c) / 10 + int(ax), 4)], "name": "Cedar neighbourhood", "building": -1})
				# Across the side road at the junction.
				link(node(Vector3(lx * 57.0, .1, z)), node(Vector3(lx * 71.0, .1, z)), true)
	# Side roads (x +-64, z -258 .. -678): inner and outer sidewalks, zebras across each junction.
	for road_x in CityCatalog.SIDE_ROADS:
		for off in [-7.0, 7.0]:
			var x: float = road_x + off
			var zs: Array[float] = []
			for k in range(streets.size()):
				var c: float = streets[k]
				if k > 0: zs.append(c + 7.0)
				if k < streets.size() - 1:
					zs.append(c - 7.0)
					var next: float = streets[k + 1]
					var span: float = (c - 7.0) - (next + 7.0)
					var steps := int(span / 35.0)
					for j in range(1, steps + 1): zs.append(c - 7.0 - span * j / (steps + 1))
			zs.sort()
			zs.reverse()
			var previous := -1
			for z in zs:
				var id := node(Vector3(x, .1, z))
				if previous >= 0:
					var pz := graph.get_point_position(previous).z
					link(previous, id, absf(pz - z) == 14.0)
				previous = id
			# The first junction (z -258) is a T: its north corner is on the cross-street sidewalk.
			link(node(Vector3(x, .1, float(streets[0]) - 7.0)), node(Vector3(x, .1, float(streets[0]) + 7.0)), true)
			var mid := node(Vector3(x, .1, zs[zs.size() / 2]))
			destinations.append({"node": mid, "type": "home", "name": "Cedar neighbourhood", "building": -1})

## Visible walking-surface height at p (the ground collision is a flat slab at y 0, so people
## are placed on the rendered sidewalks / road decks instead): neighbourhood sidewalk boxes
## (neighborhood.gd), downtown pavements and carriageways (DowntownDistrict.build_roads).
static func ground_y(p: Vector3) -> float:
	if p.x < 120.0:
		var ax := absf(p.x)
		for c in CityCatalog.CROSS_STREETS:
			if absf(p.z - float(c)) < 5.0 and ax < 69.0: return 0.036
		if ax >= 6.0 and ax <= 10.0 and p.z <= 44.0: return 0.05
		for c in CityCatalog.CROSS_STREETS:
			var dz := absf(p.z - float(c))
			if dz <= 9.0 and ax < 69.0: return 0.08
			if dz <= 11.0 and p.x > 69.0: return 0.08
		for sx in CityCatalog.SIDE_ROADS:
			var dx := absf(p.x - float(sx))
			if dx < 5.0: return 0.036
			if dx <= 9.0: return 0.08
		if ax < 6.0: return 0.036
		return 0.05
	var top := 0.0
	for x in DowntownCatalog.STREET_X:
		var half := 9.0 if x == 252 else 7.0
		var dx := absf(p.x - float(x))
		if dx < half: top = maxf(top, 0.05)
		elif dx <= half + 4.0: top = maxf(top, 0.14)
	for z in DowntownCatalog.STREET_Z:
		var dz := absf(p.z - float(z))
		if dz < 7.0: top = maxf(top, 0.15)
		elif dz <= 11.0: top = maxf(top, 0.16)
	return top

static func nearby(p: Vector3) -> int:
	prepare()
	return graph.get_closest_point(p)
static func path(from: Vector3,target: int) -> PackedInt64Array:
	var edge := nearest_edge(from)
	var best := INF
	var result := PackedInt64Array()
	for start in [edge.x,edge.y]:
		var candidate := graph.get_id_path(start,target)
		var cost := from.distance_to(graph.get_point_position(start))
		for i in range(1,candidate.size()): cost+=graph.get_point_position(candidate[i-1]).distance_to(graph.get_point_position(candidate[i]))
		if cost<best:
			best=cost
			result=candidate
	return result
static func nearest_edge(p: Vector3) -> Vector2i:
	prepare()
	var result := Vector2i.ZERO
	var best := INF
	for edge in edges:
		if crossings.has(edge): continue
		var a := graph.get_point_position(edge.x)
		if (a.x>120)!=(p.x>120): continue
		var q := Geometry3D.get_closest_point_to_segment(p,a,graph.get_point_position(edge.y))
		if q.distance_squared_to(p)<best:
			best=q.distance_squared_to(p)
			result=edge
	return result

