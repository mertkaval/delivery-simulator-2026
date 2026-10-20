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
	# Existing neighborhood retains its sidewalk corridor and two controlled crossings.
	for x in [-8.4,8.4]:
		var previous := -1
		for z in [35.0,12.0,-38.0,-93.0,-140.0,-177.0,-220.0,-300.0,-400.0,-500.0,-600.0,-675.0]:
			var id := node(Vector3(x,.1,z))
			if previous>=0: link(previous,id)
			previous=id
			destinations.append({"node":id,"type":"home" if x>0 else ("cafe" if z>-221 else "work"),"name":"Cedar neighbourhood","building":-1})
	for z in [-93.0,-177.0]: link(node(Vector3(-8.4,.1,z)),node(Vector3(8.4,.1,z)),true)
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

