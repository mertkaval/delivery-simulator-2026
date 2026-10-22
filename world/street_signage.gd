class_name StreetSignage
extends HouseInstancer
## Street-name posts at every junction, park entrance signs (memorials: CityMonuments), and the
## name plaques (StreetNames). Uses the Blender props from build_houses.py, instanced like
## the residential props; the names are Label3D text so they stay crisp.

const SIGN_RANGE := 70.0
var signs: Array[Dictionary] = [] ## {"at": Vector3, "x_street", "z_street"} for tests
var busts: Array[Vector3] = []

func _ready() -> void:
	body = StaticBody3D.new()
	body.name = "SignageCollision"
	add_child(body)
	for j in StreetNames.junctions(): junction_sign(j)
	for centre in StreetNames.PARKS: park(Vector3(centre.x, 0, centre.y), StreetNames.PARKS[centre])
	murals_on_terraces()
	for block_id in range(9):
		for b in DowntownCatalog.buildings(block_id):
			if b.program == "plaza": monument(Transform3D(Basis(Vector3.UP, b.yaw), b.root))
	flush()

var monument_at := Vector3.ZERO
var monument_transform := Transform3D.IDENTITY

## Atatürk Square: the standing bronze Atatürk on its stepped granite plinth, facing the street,
## with the inscription and the fountain behind (CityMonuments.square).
func monument(plaza: Transform3D) -> void:
	var monuments := monuments_node()
	monument_transform = monuments.square(plaza)
	monument_at = monument_transform.origin

## The city's CityMonuments (CedarNeighborhood.monuments), or a local one when built standalone.
func monuments_node() -> CityMonuments:
	var city := get_parent()
	var found: Variant = city.get("monuments") if city != null else null
	if found is CityMonuments: return found
	var own := get_node_or_null("Monuments") as CityMonuments
	if own == null:
		own = CityMonuments.new()
		own.name = "Monuments"
		var placer: Variant = city.get("placer") if city != null else null
		if placer is PropPlacer: own.placer = placer
		add_child(own)
	return own

## Corner post on the sidewalk, on the first corner that is clear of every carriageway.
func junction_sign(j: Dictionary) -> void:
	var at: Vector2 = j.at
	for corner in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:
		var p: Vector2 = at + corner * Vector2(j.x_half + 2.2, j.z_half + 2.2)
		if StreetNames.on_carriageway(p): continue
		var origin := Vector3(p.x, 0.12, p.y)
		add("street_sign", Transform3D(Basis.IDENTITY, origin), {}, SIGN_RANGE)
		post_below_blades(Transform3D(Basis.IDENTITY, origin))
		box_collider(origin + Vector3(0, 1.6, 0), Vector3(0.1, 3.2, 0.1), Basis.IDENTITY)
		# Blade A runs along x and names the east-west street; blade B names the north-south one.
		for side in [1.0, -1.0]:
			blade_text(j.z_street, origin + Vector3(0, 3.02, side * 0.026), 0.0 if side > 0 else PI)
			blade_text(j.x_street, origin + Vector3(side * 0.026, 2.74, 0), side * PI * 0.5)
		signs.append({"at": origin, "x_street": j.x_street, "z_street": j.z_street})
		record_prop("street_sign", origin, 0.1)
		return

## The street_sign post (KitFrameLight, 3.32 m) ran up through the middle of both name blades, in
## front of the centre of every street name. It now stops under the lower blade (2.62 m), and a
## short clamp joins the two blades (2.855-2.905 m) - the names read across the whole blade.
const POST_TOP := 2.62
func post_below_blades(placement: Transform3D) -> void:
	var list := get_parts("street_sign", "near")
	for i in range(list.size()):
		if not str(list[i].get("name", "")).begins_with("KitFrameLight"): continue
		var cell := Vector2i(floori(placement.origin.x / 128.0), floori(placement.origin.z / 128.0))
		var key := "%s|%d|%d_%d" % ["street_sign", i, cell.x, cell.y]
		if not groups.has(key): return
		var items: Array = groups[key].items
		var height: float = (list[i].mesh as Mesh).get_aabb().end.y
		var colour: Color = items[-1][1]
		items[-1] = [placement * Transform3D(Basis.from_scale(Vector3(1, POST_TOP / height, 1)), Vector3.ZERO) * list[i].transform, colour]
		# Clamp 2.5 mm inside both blades' faces (at 0.6 of the post's 7 cm its faces were 1 mm off
		# the blades' and their trims'): only the 4 cm between the blades shows.
		items.append([placement * Transform3D(Basis.from_scale(Vector3(0.5, 0.05 / height, 0.5)), Vector3(0, 2.855, 0)) * list[i].transform, colour])
		return

## Registers a placed sign with the city's PropPlacer so later furniture keeps clear of it.
func record_prop(kind: String, at: Vector3, radius: float) -> void:
	var placer: Variant = get_parent().get("placer") if get_parent() != null else null
	if placer is PropPlacer: (placer as PropPlacer).record(kind, at, radius, "signage")

func blade_text(words: String, at: Vector3, yaw: float) -> void:
	var label := Label3D.new()
	label.text = words
	label.font_size = 32
	label.outline_size = 0
	label.pixel_size = minf(0.0042, 1.16 / (words.length() * 19.0))
	label.modulate = Color("f4f7f2")
	label.position = at
	label.rotation.y = yaw
	label.double_sided = false
	label.visibility_range_end = SIGN_RANGE - 25.0
	add_child(label)

## Timber entrance sign on the park's south edge.
func park(centre: Vector3, title: String) -> void:
	var sign_at := centre + Vector3(0, 0, 15.2)
	add("park_sign", Transform3D(Basis.IDENTITY, sign_at), {}, 90.0)
	box_collider(sign_at + Vector3(0, 0.75, 0), Vector3(2.4, 1.5, 0.2), Basis.IDENTITY)
	record_prop("park_sign", sign_at, 0.5)
	for side in [1.0, -1.0]:
		var label := Label3D.new()
		label.text = title.to_upper()
		label.font_size = 40
		label.pixel_size = minf(0.0045, 2.15 / (title.length() * 24.0))
		label.outline_size = 0
		label.modulate = Color("f1e9c8")
		label.position = sign_at + Vector3(0, 1.15, side * 0.052)
		label.rotation.y = 0.0 if side > 0 else PI
		label.double_sided = false
		label.visibility_range_end = 60.0
		add_child(label)
	# The park's Atatürk memorial (bust wall, or the equestrian monument) comes from CityMonuments.
	var memorial: Variant = monuments_node().memorials.get(Vector2(centre.x, centre.z))
	busts.append(memorial if memorial is Vector3 else centre)

var murals: Array[Transform3D] = []

## Street art: the terrace end walls that face each pocket park carry a mural
## (world/citykit/murals, rendered by build_murals.py), painted onto the brick.
func murals_on_terraces() -> void:
	var serial := 0
	for b in CityLayout.buildings():
		if b.type != "terrace": continue
		var half: float = CityLayout.frontage(b) * 0.5
		var side := signf(b.front.x)
		for end in [-1.0, 1.0]:
			var wall_z: float = b.front.z + end * half
			var faces_park := false
			for park_z in CityLayout.PARKS:
				if absf(wall_z - park_z) < 24.0 and signf(park_z - wall_z) == end: faces_park = true
			if not faces_park: continue
			var t := Transform3D(Basis(Vector3.UP, 0.0 if end > 0 else PI), Vector3(b.front.x - side * 5.0, 3.3, wall_z + end * 0.07))
			mural(t, serial % StreetNames.MURALS.size())
			serial += 1

func mural(t: Transform3D, index: int) -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(8.0, 5.0)
	var material := ShaderMaterial.new()
	material.shader = preload("res://world/citykit/mural.gdshader")
	material.set_shader_parameter("art", load("res://world/citykit/murals/mural_%d.png" % index))
	material.set_shader_parameter("brick_normal", load("res://world/citykit/textures/brick_red_normal.png"))
	var node := MeshInstance3D.new()
	node.mesh = quad
	node.material_override = material
	node.transform = t
	node.visibility_range_end = 220.0
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	murals.append(t)
