class_name RestaurantInteriors
extends HouseInstancer
## Fits out the thirteen corridor restaurants (RestaurantCatalog) inside the ground floors
## of their CityLayout midrises: shell (floor, ceiling, tiled walls, kitchen partition with
## pass and staff door), counter with register and courier pickup shelf, menu boards,
## dining furniture, kitchen line under a hood, and each restaurant's signature equipment.
## Everything is Blender restaurant-kit pieces instanced through MultiMesh with per-restaurant
## tints; döner cones and kokoreç rolls are real nodes that turn.

const INTERIOR_END := 70.0
const SIGNATURE := {
	"mangal_doner": [["rs_doner", -1.0, -9.35], ["rs_grill", 1.2, -9.4]],
	"mangal": [["rs_grill", -1.1, -9.4], ["rs_grill", 1.3, -9.4]],
	"pide": [["rs_pide_oven", -0.6, -8.45]],
	"kokorec": [["rs_kokorec", -0.6, -9.4]],
	"fish": [["rs_grill", 0.8, -9.4], ["rs_fish_display", -2.6, -7.3]],
	"iskender": [["rs_doner", -0.9, -9.35], ["rs_range", 1.0, -9.4]],
	"dessert": [["rs_dessert_vitrine", -2.6, -7.3], ["rs_range", 0.4, -9.4]],
	"soup": [["rs_soup_station", 0.2, -9.3]],
	"doner": [["rs_doner", -1.2, -9.35], ["rs_doner", 0.3, -9.35]],
	"diner": [["rs_bain_marie", -2.7, -7.3], ["rs_range", 0.6, -9.4]],
	"tavern": [["rs_bar", 0.2, -9.45]],
	"pastry": [["rs_simit_rack", -1.0, -9.55], ["rs_dessert_vitrine", -2.6, -7.3]],
	"cigkofte": [["rs_cigkofte_station", -2.6, -7.3], ["rs_prep", 0.6, -9.4]],
	"crepe": [["rs_crepe_griddle", -0.4, -9.35]],
	"kumpir": [["rs_kumpir_bar", -2.7, -7.3]],
	"dairy": [["rs_dairy_display", -2.6, -7.3], ["rs_tea_station_floor", 0.8, -9.4]],
}

var spinners: Array[Dictionary] = [] ## {"node": Node3D, "axis": Vector3, "speed": float}
var restaurants: Array[Dictionary] = [] ## {"id", "name", "frame", "pickup", "door"} for tests/routing
var lights: Array[OmniLight3D] = []

func _ready() -> void:
	body = StaticBody3D.new()
	body.name = "RestaurantCollision"
	add_child(body)
	var buildings := RestaurantCatalog.corridor_buildings()
	for k in range(buildings.size()):
		fit_out(buildings[k], RestaurantCatalog.LIST[3 + k])
	for i in range(3): avenue(i)
	# Interior dressing sits under the building: only the street furniture casts sun shadows.
	for key in groups:
		if not str(key).begins_with("rs_sidewalk") and not str(key).begins_with("rs_aframe") and not str(key).begins_with("rs_planter") and not str(key).begins_with("rs_blade"):
			groups[key].shadows = false
	flush()
	set_process(true)

func _process(delta: float) -> void:
	for s in spinners:
		s.node.rotate_object_local(s.axis, s.speed * delta)

func piece(asset: String, t: Transform3D, colours: Dictionary, x: float, y: float, z: float, yaw: float = 0.0, end: float = INTERIOR_END) -> void:
	add(asset, t * Transform3D(Basis(Vector3.UP, yaw), Vector3(x, y, z)), colours, end)

func local_box(t: Transform3D, centre: Vector3, size: Vector3) -> void:
	box_collider(t * centre, size, t.basis)

func fit_out(b: Dictionary, r: Array) -> void:
	var t := RestaurantCatalog.frame(b)
	var colours := RestaurantCatalog.colours(r)
	var bays := int(b.bays) - 1
	var e := RestaurantCatalog.entrance_bay(b)
	var xe := RestaurantCatalog.bay_x(b, e)
	var xl := -int(b.bays) * 2.0
	var xr := xl + RestaurantCatalog.restaurant_width(b)
	var wood: bool = r[5] == "wood"
	var door_bay := 0 if e != 0 else bays - 1
	# --- shell -----------------------------------------------------------------------------
	for i in range(bays):
		var x := RestaurantCatalog.bay_x(b, i)
		piece("rs_floor_wood" if wood else "rs_floor", t, colours, x, 0, 0)
		piece("rs_floor_kitchen", t, colours, x, 0, 0)
		piece("rs_ceiling", t, colours, x, 0, 0)
		piece("rs_back", t, colours, x, 0, 0.45)
		piece("rs_pass" if i == e else ("rs_door" if i == door_bay else "rs_plain"), t, colours, x, 0, 0)
		pass   # the old blank menu boards are replaced by one readable MenuBoard (menu())
	# Dining side walls: 4 m modules plus a half-length one, 10 m deep on each side.
	var wall := "rs_wall_wood" if r[6] == "wood" else "rs_wall"
	for run in [[0.0, 1.0], [-4.0, 1.0], [-8.0, 0.5]]:
		add(wall, t * Transform3D(Basis.IDENTITY.scaled(Vector3(1, 1, run[1])), Vector3(xl + 0.3, 0, run[0])), colours, INTERIOR_END)
		add(wall, t * Transform3D(Basis(Vector3.UP, PI).scaled(Vector3(1, 1, run[1])), Vector3(xr - 0.1, 0, run[0] - 4.0 * run[1])), colours, INTERIOR_END)
	piece("rs_wall_kitchen", t, colours, xl + 0.3, 0, 0)
	piece("rs_wall_kitchen", t, colours, xr - 0.1, 0, -26.0, PI)
	# --- counter, pickup, drinks --------------------------------------------------------------
	piece("rs_counter", t, colours, xe - 0.5, 0, -7.3)
	piece("rs_counter", t, colours, xe + 1.5, 0, -7.3)
	piece("rs_register", t, colours, xe + 0.3, 0, -7.35)
	piece("rs_ayran_machine" if r[4] != "tavern" else "rs_tea_station", t, colours, xe + 1.7, 1.04, -7.45)
	piece("rs_pickup_shelf", t, colours, xe + 3.2, 0, -7.3)
	piece("rs_drink_fridge", t, colours, xr - 0.45, 0, -7.6, -PI / 2)
	piece("rs_condiments", t, colours, xl + 0.6, 0, -6.6, PI / 2)
	piece("rs_plant", t, colours, xr - 0.5, 0, -0.9)
	# --- kitchen line along the back wall, under the hood ---------------------------------------
	var kz := -15.05
	piece("rs_fryer", t, colours, xe - 1.0, 0, kz)
	piece("rs_range", t, colours, xe, 0, kz)
	piece("rs_grill" if r[4] != "pide" else "rs_range", t, colours, xe + 1.15, 0, kz)
	piece("rs_hood", t, colours, xe, 0, kz + 0.1)
	piece("rs_prep", t, colours, xe - 2.9, 0, kz)
	piece("rs_shelf", t, colours, xe - 2.9, 0, kz - 0.18)
	piece("rs_sink", t, colours, xe + 2.8, 0, kz)
	piece("rs_fridge", t, colours, xl + 1.0, 0, -12.0, PI / 2)
	piece("rs_prep", t, colours, xr - 0.8, 0, -12.4, -PI / 2)
	# --- signature equipment --------------------------------------------------------------------
	for s in SIGNATURE[r[4]]:
		var asset: String = s[0]
		if asset == "rs_tea_station_floor":
			piece("rs_counter", t, colours, xe + float(s[1]), 0, -9.4)
			piece("rs_tea_station", t, colours, xe + float(s[1]), 1.04, -9.4)
			continue
		piece(asset, t, colours, xe + float(s[1]), 0, float(s[2]))
		if asset == "rs_doner": spinner("rs_doner_cone", t * Vector3(xe + float(s[1]), 0, float(s[2]) - 0.08), t.basis, Vector3.UP, 0.6, colours)
		if asset == "rs_kokorec": spinner("rs_kokorec_roll", t * Vector3(xe + float(s[1]), 1.25, float(s[2])), t.basis, Vector3.RIGHT, 1.4, colours)
	# --- dining ---------------------------------------------------------------------------------
	for i in range(bays):
		if i == e: continue
		var x := RestaurantCatalog.bay_x(b, i)
		if r[4] == "tavern":
			piece("rs_barrel", t, colours, x - 0.9, 0, -2.6)
			piece("rs_table4", t, colours, x + 0.6, 0, -4.8)
			local_box(t, Vector3(x - 0.9, 0.5, -2.6), Vector3(0.8, 1.0, 0.8))
		elif i == 0:
			piece("rs_booth", t, colours, xl + 0.62, 0, -2.6)
			piece("rs_booth", t, colours, xl + 0.62, 0, -5.0)
			piece("rs_table2", t, colours, x + 0.7, 0, -3.8)
			local_box(t, Vector3(xl + 0.65, 0.5, -3.8), Vector3(1.2, 1.0, 4.3))
		else:
			piece("rs_table4", t, colours, x, 0, -2.7)
			piece("rs_table2", t, colours, x, 0, -5.0)
		if i != 0 or r[4] == "tavern":
			local_box(t, Vector3(x, 0.45, -2.7), Vector3(1.1, 0.9, 1.6))
			local_box(t, Vector3(x, 0.45, -5.0), Vector3(1.7, 0.9, 0.7))
		piece("rs_bar_ledge", t, colours, x, 0, -0.55)
		local_box(t, Vector3(x, 0.55, -0.75), Vector3(3.8, 1.1, 0.8))
		for z in [-2.7, -5.0]: piece("rs_pendant", t, colours, x, 0, z)
	piece("rs_pendant", t, colours, xe + 0.5, 0, -7.3)
	# --- collision: walls, facade with the door gap, counter line, kitchen ----------------------
	var w := RestaurantCatalog.restaurant_width(b)
	var cx := (xl + xr) * 0.5
	local_box(t, Vector3(xl + 0.15, 1.6, -8.0), Vector3(0.3, 3.2, 16.0))
	local_box(t, Vector3(xr - 0.05, 1.6, -8.0), Vector3(0.1, 3.2, 16.0))
	local_box(t, Vector3(cx, 1.6, -10.0), Vector3(w, 3.2, 0.2))
	local_box(t, Vector3(cx, 0.55, -8.5), Vector3(w, 1.1, 3.0))
	var door0 := xe - 0.92
	var door1 := xe + 0.92
	local_box(t, Vector3((xl + door0) * 0.5, 1.6, -0.15), Vector3(door0 - xl, 3.2, 0.3))
	local_box(t, Vector3((door1 + xr) * 0.5, 1.6, -0.15), Vector3(xr - door1, 3.2, 0.3))
	local_box(t, Vector3(xr - 0.45, 1.0, -7.6), Vector3(0.6, 2.0, 0.7))
	local_box(t, Vector3(xl + 0.6, 0.5, -6.6), Vector3(0.5, 1.0, 1.0))
	# --- pickup interaction, labels, lights, exterior ------------------------------------------
	var pickup := StaticBody3D.new()
	pickup.set_meta("interaction", "pickup_" + str(r[0]))
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(1.0, 1.7, 0.45)
	shape.shape = box
	pickup.add_child(shape)
	pickup.transform = Transform3D(t.basis, t * Vector3(xe + 3.2, 0.85, -7.3))
	add_child(pickup)
	label(t, "COURIER PICKUP", Vector3(xe + 3.2, 1.74, -7.06), 20, Color("fff4d8"))
	menu(t, r, xe, e, door_bay, bays, b)
	for i in range(bays):
		light(t * Vector3(RestaurantCatalog.bay_x(b, i), 2.75, -4.0), Color("ffd9a6"), 1.3, 7.5)
	light(t * Vector3(xe, 2.7, -13.0), Color("f1f4ff"), 0.9, 7.0)
	exterior(t, b, r, xe, e, bays, colours)
	# People: a server at the register, a cook on the line, two diners at a table.
	var seed := restaurants.size()
	person(t, Vector3(xe + 0.6, 0.06, -7.95), 0.0, "Talk", seed * 3)
	person(t, Vector3(xe + 0.2, 0.06, -14.25), PI, "Idle", seed * 3 + 1)
	var table_bay := 0 if e != 0 else 1
	var tx := RestaurantCatalog.bay_x(b, table_bay) + (0.7 if table_bay == 0 and r[4] != "tavern" else 0.0)
	if table_bay == 0 and r[4] != "tavern":
		person(t, Vector3(tx - 0.62, 0.06, -3.8), PI / 2, "Sit", seed * 3 + 2)
		person(t, Vector3(tx + 0.62, 0.06, -3.8), -PI / 2, "Sit", seed * 3 + 5)
	else:
		person(t, Vector3(tx - 0.3, 0.06, -2.7 - 0.62), 0.0, "Sit", seed * 3 + 2)
		person(t, Vector3(tx + 0.3, 0.06, -2.7 + 0.62), PI, "Sit", seed * 3 + 5)
	restaurants.append({"id": r[0], "name": r[1], "frame": t, "pickup": t * RestaurantCatalog.pickup_local(b),
		"door": RestaurantCatalog.door_outside(b), "door_inside": t * Vector3(xe, 0, -2.0)})

func spinner(asset: String, at: Vector3, basis: Basis, axis: Vector3, speed: float, colours: Dictionary) -> void:
	var root := Node3D.new()
	root.transform = Transform3D(basis, at)
	add_child(root)
	for p in get_parts(asset, "near"):
		var mesh := MeshInstance3D.new()
		mesh.mesh = p.mesh
		mesh.material_override = p.material
		mesh.transform = p.transform
		mesh.visibility_range_end = INTERIOR_END
		root.add_child(mesh)
	spinners.append({"node": root, "axis": axis, "speed": speed})

func label(t: Transform3D, text: String, at: Vector3, size: int, colour: Color, yaw: float = 0.0, width: float = 0.0) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font_size = size
	l.pixel_size = 0.003 if width == 0.0 else minf(0.004, width / (text.length() * size * 0.55))
	l.outline_size = 0
	l.modulate = colour
	l.double_sided = false
	l.transform = t * Transform3D(Basis(Vector3.UP, yaw), at)
	l.visibility_range_end = 45.0
	add_child(l)
	return l

## Menu boards: restaurant name and five dishes with prices on each board.
func menu(t: Transform3D, r: Array, xe: float, _e: int, _door_bay: int, _bays: int, b: Dictionary) -> void:
	# A large readable menu board on the back wall above the kitchen line, and a smaller one
	# beside the entrance outside (MenuBoard: full menu, dollar prices, high-contrast type).
	var accent := Color(str(r[8]))
	var xl := -int(b.bays) * 2.0
	var cx := xl + RestaurantCatalog.restaurant_width(b) * 0.5
	var inside := MenuBoard.build(str(r[0]), Vector2(3.4, 1.15), accent)
	inside.transform = Transform3D(t.basis, t * Vector3(cx, 2.55, -9.86))
	add_child(inside)
	var outside := MenuBoard.build(str(r[0]), Vector2(0.95, 1.25), accent)
	outside.transform = Transform3D(t.basis, t * Vector3(xe + 1.55, 1.55, 0.1))
	add_child(outside)

func light(at: Vector3, colour: Color, energy: float, range_m: float) -> void:
	var l := OmniLight3D.new()
	l.position = at
	l.light_color = colour
	l.light_energy = energy
	l.omni_range = range_m
	l.shadow_enabled = false
	l.distance_fade_enabled = true
	l.distance_fade_begin = 55.0
	l.distance_fade_length = 15.0
	add_child(l)
	lights.append(l)

## Facade dressing: projecting blade sign, sidewalk tables and parasols, A-frame menu, planters.
func exterior(t: Transform3D, b: Dictionary, r: Array, xe: float, e: int, bays: int, colours: Dictionary) -> void:
	var xl := -int(b.bays) * 2.0
	piece("rs_blade_sign", t, colours, xl + 0.2, 3.5, 0.0, 0.0, 160.0)
	for side in [1.0, -1.0]:
		label(t, str(r[1]).to_upper(), Vector3(xl + 0.2 + side * 0.035, 3.0, 0.7), 22, Color("fff3dc"), side * PI * 0.5, 0.7)
	for i in range(bays):
		if i == e: continue
		var x := RestaurantCatalog.bay_x(b, i)
		piece("rs_sidewalk_set", t, colours, x, 0.06, 1.7, 0.0, 120.0)
		local_box(t, Vector3(x, 0.4, 1.7), Vector3(1.5, 0.8, 0.8))
	piece("rs_aframe", t, colours, xe + 1.5, 0.06, 1.0, PI / 2, 90.0)
	for x in [xe - 1.4, xe + 1.4]:
		piece("rs_planter", t, colours, x, 0.06, 0.45, 0.0, 120.0)
	label(t, str(r[3]), Vector3(xe, 3.3, 0.16), 16, Color("f1ead7"))

var people: Array[Node3D] = []

func person(t: Transform3D, at: Vector3, yaw: float, pose: String, index: int) -> void:
	var model := LivingAssets.citizen(index)
	# Citizen rigs face -z: turn them so `yaw` is the direction they look.
	model.transform = t * Transform3D(Basis(Vector3.UP, yaw + PI), at)
	model.purpose_pose = pose
	model.max_distance = 40.0  # indoors: only seen through the storefront up close
	add_child(model)
	people.append(model)

## Signature equipment for the three Atatürk Avenue restaurants (CityAssets buildings):
## behind their long counter and in the open kitchen along the back wall.
func avenue(i: int) -> void:
	var t := Transform3D(Basis.IDENTITY, CityCatalog.PICKUPS[i] - Vector3.UP)
	var colours := RestaurantCatalog.colours(RestaurantCatalog.LIST[i])
	match i:
		0:
			piece("rs_doner", t, colours, -1.6, 0, -1.35)
			spinner("rs_doner_cone", t * Vector3(-1.6, 0, -1.43), t.basis, Vector3.UP, 0.6, colours)
			piece("rs_grill", t, colours, -4.4, 0, -5.3)
			local_box(t, Vector3(-1.6, 0.9, -1.45), Vector3(0.75, 1.8, 0.6))
		1:
			piece("rs_grill", t, colours, -2.2, 0, -1.45)
			piece("rs_grill", t, colours, -4.4, 0, -5.3)
			local_box(t, Vector3(-2.2, 0.5, -1.45), Vector3(1.25, 1.0, 0.75))
		2:
			piece("rs_pide_oven", t, colours, -4.4, 0, -4.45)
			local_box(t, Vector3(-4.4, 0.9, -5.0), Vector3(2.0, 1.8, 1.8))
	piece("rs_ayran_machine", t, colours, -5.6, 1.1, 0.0)
