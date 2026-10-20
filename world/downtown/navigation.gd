class_name UrbanNavigation
extends RefCounted
static var graph: AStar3D
static var edges: Array[Vector2i]=[]
static func prepare() -> void:
	if graph!=null: return
	graph=AStar3D.new()
	var zs := [-258.0,-328.0,-398.0,-468.0,-538.0,-608.0,-678.0]
	for x in range(4):
		for z in range(7): graph.add_point(x*7+z,Vector3(DowntownCatalog.STREET_X[x],0,zs[z]))
	for x in range(4):
		for z in range(7):
			if z<6: link(x*7+z,x*7+z+1)
			if x<3: link(x*7+z,(x+1)*7+z)
	for z in range(7): graph.add_point(28+z,Vector3(520,0,zs[z]))
	for z in range(7):
		if z<6: link(28+z,29+z)
		if z%2==0: link(21+z,28+z)
static func link(a: int,b: int) -> void:
	graph.connect_points(a,b)
	edges.append(Vector2i(a,b))
static func approach(p: Vector3) -> PackedVector3Array:
	var ground := Vector3(p.x,0,p.z)
	var best := 2.4
	var result := PackedVector3Array([ground])
	for pair in [[DowntownCatalog.PICKUPS,DowntownCatalog.PICKUP_APPROACHES],[DowntownCatalog.DESTINATIONS,DowntownCatalog.DESTINATION_APPROACHES]]:
		for i in range(pair[0].size()):
			var target: Vector3=pair[0][i]
			var distance := Vector2(p.x-target.x,p.z-target.z).length()
			if distance<best:
				best=distance
				var path := PackedVector3Array(pair[1][i])
				path[-1]=ground
				result=path
	return result
static func attach(id: int,p: Vector3) -> Vector3:
	var best := INF
	var chosen := Vector2i.ZERO
	var projected := p
	for edge in edges:
		var q := Geometry3D.get_closest_point_to_segment(p,graph.get_point_position(edge.x),graph.get_point_position(edge.y))
		if q.distance_squared_to(p)<best:
			best=q.distance_squared_to(p)
			chosen=edge
			projected=q
	graph.add_point(id,projected)
	graph.connect_points(id,chosen.x)
	graph.connect_points(id,chosen.y)
	return projected
static func route(from: Vector3,to: Vector3,pickup: bool) -> PackedVector3Array:
	prepare()
	var start := from
	var end := to
	var prefix := PackedVector3Array()
	var suffix := PackedVector3Array()
	if from.x<120:
		var z: float=DowntownCatalog.STREET_Z[0]
		for cross in DowntownCatalog.STREET_Z:
			if absf(cross-from.z)+absf(cross-to.z)<absf(z-from.z)+absf(z-to.z): z=cross
		prefix=CityCatalog.route(from,Vector3(64,0,z),false)
		start=Vector3(144,0,z)
	if to.x<120:
		var z: float=DowntownCatalog.STREET_Z[0]
		for cross in DowntownCatalog.STREET_Z:
			if absf(cross-from.z)+absf(cross-to.z)<absf(z-from.z)+absf(z-to.z): z=cross
		end=Vector3(144,0,z)
		suffix=CityCatalog.route(Vector3(64,0,z),to,pickup)
	var first := approach(start)
	var last := approach(end)
	var a := attach(1000,first[0])
	var b := attach(1001,last[0])
	# Direct travel on one road avoids an unnecessary trip to its intersection.
	for edge in edges:
		var p := graph.get_point_position(edge.x)
		var q := graph.get_point_position(edge.y)
		if Geometry3D.get_closest_point_to_segment(a,p,q).distance_to(a)<.01 and Geometry3D.get_closest_point_to_segment(b,p,q).distance_to(b)<.01:
			graph.connect_points(1000,1001)
	var result := prefix
	first.reverse()
	result.append_array(first)
	result.append_array(graph.get_point_path(1000,1001))
	result.append_array(last)
	result.append_array(suffix)
	graph.remove_point(1000)
	graph.remove_point(1001)
	return result
