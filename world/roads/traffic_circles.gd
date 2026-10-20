class_name TrafficCircles
extends Node3D
## Neighbourhood traffic circles (Vancouver-style): a small kerbed, planted island in the middle
## of a residential intersection that traffic drives around counter-clockwise (right-hand
## traffic). Modular: add a centre to CENTERS and the island, its collision and the traffic
## routing (SmoothRoute bends every route around it) all follow.
##
## Placed only at junctions with no bus line (a 12 m bus cannot turn round a 2 m island).

## Junction centres (x, 0, z). Side road x=64 with Rauf Orbay, Kara Fatma and Şerife Bacı.
const CENTERS := [Vector3(64, 0, -398), Vector3(64, 0, -538), Vector3(64, 0, -678)]
const ISLAND := 2.0      ## kerb radius (m)
const DRIVE := 4.1       ## lane-centre radius cars follow around the island (m)

## Route points bent around every island: points closer than DRIVE are pushed out radially,
## then the bent stretch is relaxed so entry and exit flow into the circle without kinks.
static func bend(points: PackedVector3Array, closed := true) -> PackedVector3Array:
	if points.size() < 2: return points
	# Densify to <= 0.5 m so the circle can be followed smoothly.
	var dense := PackedVector3Array()
	var n := points.size()
	var last := n if closed else n - 1
	for i in range(last):
		var a := points[i]
		var b := points[(i + 1) % n]
		var steps := maxi(1, ceili(a.distance_to(b) / 0.5))
		for k in range(steps): dense.append(a.lerp(b, float(k) / steps))
	if not closed: dense.append(points[-1])
	var touched := false
	for c in CENTERS:
		var centre := Vector3(c.x, 0, c.z)
		var near: Array[int] = []
		for i in range(dense.size()):
			var flat := Vector3(dense[i].x, 0, dense[i].z)
			var d := flat.distance_to(centre)
			if d < DRIVE + 3.0: near.append(i)
			if d < DRIVE:
				var out := (flat - centre).normalized() if d > 0.01 else Vector3.RIGHT
				dense[i] = centre + out * DRIVE
				touched = true
		# Relax the neighbourhood (keeps points outside the island, smooths the hand-over).
		for _sweep in range(6):
			for i in near:
				var p := dense[posmod(i - 1, dense.size())]
				var q := dense[(i + 1) % dense.size()]
				var m := (p + q) * 0.5
				var flat := Vector3(m.x, 0, m.z)
				if flat.distance_to(centre) < DRIVE: m = centre + (flat - centre).normalized() * DRIVE
				dense[i] = dense[i].lerp(m, 0.5)
	return dense if touched else points

static func near_circle(p: Vector3, margin := 0.0) -> bool:
	for c in CENTERS:
		if Vector2(p.x - c.x, p.z - c.z).length() < DRIVE + margin: return true
	return false

func _ready() -> void:
	var body := StaticBody3D.new()
	body.name = "TrafficCircleCollision"
	# Own layer: the player collides with islands, but AI look-ahead rays (masks 1|4) do not,
	# since their routes already bend round the island and a straight ray would see it ahead.
	body.collision_layer = 16
	body.collision_mask = 0
	add_child(body)
	var concrete := CityMaterials.get_surface("c9c6bc")
	var soil := CityMaterials.get_surface("5a4a38")
	var grass := CityMaterials.get_surface("5f8a46")
	var paint := StandardMaterial3D.new()
	paint.albedo_color = Color("f2f0e6")
	paint.roughness = 0.6
	for c in CENTERS:
		var at: Vector3 = c
		# Mountable concrete apron, raised kerb, planted bed.
		add_disc(at + Vector3(0, 0.07, 0), ISLAND + 0.55, 0.06, concrete)
		add_disc(at + Vector3(0, 0.16, 0), ISLAND, 0.16, concrete)
		add_disc(at + Vector3(0, 0.25, 0), ISLAND - 0.18, 0.04, soil)
		add_disc(at + Vector3(0, 0.27, 0), ISLAND - 0.3, 0.02, grass)
		# A small street tree with low shrubs round it.
		var tree: Node3D = load("res://world/citykit/houses/%s.glb" % ("tree_fir" if int(absf(at.z)) % 4 == 2 else "tree_cedar")).instantiate()
		tree.position = at + Vector3(0, 0.28, 0)
		tree.scale = Vector3.ONE * 0.3
		add_child(tree)
		for k in range(5):
			var a := TAU * k / 5.0
			var bush := MeshInstance3D.new()
			var sphere := SphereMesh.new()
			sphere.radius = 0.38
			sphere.height = 0.55
			bush.mesh = sphere
			bush.material_override = CityAssets.vegetation()
			bush.position = at + Vector3(cos(a) * 1.15, 0.45, sin(a) * 1.15)
			bush.visibility_range_end = 140
			add_child(bush)
		# Dashed white circulation guide round the apron.
		for k in range(16):
			var a0 := TAU * k / 16.0
			var dash := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(0.9, 0.012, 0.12)
			dash.mesh = box
			dash.material_override = paint
			var r := ISLAND + 0.75
			dash.position = at + Vector3(cos(a0) * r, 0.072, sin(a0) * r)
			dash.rotation.y = -a0 + PI / 2
			dash.visibility_range_end = 120
			add_child(dash)
		var shape := CollisionShape3D.new()
		var cylinder := CylinderShape3D.new()
		cylinder.radius = ISLAND
		cylinder.height = 1.0
		shape.shape = cylinder
		shape.position = at + Vector3(0, 0.5, 0)
		body.add_child(shape)

func add_disc(at: Vector3, radius: float, height: float, material: Material) -> void:
	var mesh := MeshInstance3D.new()
	var cylinder := CylinderMesh.new()
	cylinder.top_radius = radius
	cylinder.bottom_radius = radius
	cylinder.height = height
	cylinder.radial_segments = 40
	mesh.mesh = cylinder
	mesh.material_override = material
	mesh.position = at - Vector3(0, height * 0.5, 0) + Vector3(0, 0.0, 0)
	mesh.visibility_range_end = 260
	add_child(mesh)
