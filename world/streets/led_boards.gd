class_name LedBoards
extends Node3D
## Scrolling LED marquee boards on the city's businesses (Blender frames from
## world/streets/build_street_tech.py, dot-matrix text from led_board.gdshader + LedFont):
##   * the four shops: a wall board on the right of the shop-name header (ShopCatalog),
##   * the three Atatürk Avenue restaurants: a double-sided blade sign projecting from the
##     avenue-side corner of the fascia, readable from the avenue (RestaurantCatalog 0-2),
##   * the thirteen corridor restaurants: a blade sign on the pier between the restaurant
##     fascia and the lobby, above the awnings (RestaurantCatalog corridor frames),
##   * downtown storefronts: a long board on the fascia band beside the shop sign.
## All boards share one material and one atlas texture (one row per message); each board
## picks its row, length, speed and phase through instance uniforms.

const KIT := "res://world/streets/%s.glb"
## Screen size (m) and LED columns per frame (11 LED rows; square pitch).
const KINDS := {"led_board_wall": 57.0, "led_board_long": 81.0, "led_board_blade": 36.0}
const AMBER := Color(1.0, 0.62, 0.08)
const RED := Color(1.0, 0.16, 0.1)
const GREEN := Color(0.3, 1.0, 0.35)
const WHITE := Color(0.95, 0.95, 0.9)
const CYAN := Color(0.25, 0.85, 1.0)
const RANGE := 120.0
## Downtown storefronts that get a board (DowntownCatalog names) and their message.
const DOWNTOWN := {
	"Juniper Market": [["JUNIPER MARKET", AMBER], [" • FRESH PRODUCE • ", WHITE], ["APPLES $2.99/LB", RED], [" • OPEN 7AM-11PM • ", GREEN], ["DELIVERY AVAILABLE", CYAN]],
	"Rainline Café": [["RAINLINE CAFÉ", AMBER], [" • FLAT WHITE ", WHITE], ["$4.50", RED], [" • FRESH CROISSANTS • ", WHITE], ["OPEN", GREEN], [" • FREE WIFI •", CYAN]],
	"Pacific Pharmacy": [["PACIFIC PHARMACY", GREEN], [" • OPEN 24 HOURS • ", WHITE], ["FLU SHOTS TODAY", RED], [" • PRESCRIPTIONS READY IN 15 MIN •", AMBER]],
	"Seawall Noodles": [["SEAWALL NOODLES", AMBER], [" • RAMEN ", WHITE], ["$13", RED], [" • DUMPLINGS ", WHITE], ["$8", RED], [" • ORDER ON COURIERNOW •", GREEN]],
	"Corner Pantry": [["CORNER PANTRY", AMBER], [" • COFFEE • SNACKS • LOTTO • ", WHITE], ["2 FOR $5", RED], [" • OPEN LATE •", GREEN]],
	"Union Hotel": [["UNION HOTEL", AMBER], [" • ROOMS AVAILABLE • ", GREEN], ["FROM $129", RED], [" • BAR & GRILL OPEN •", WHITE]],
	"Moss & Paper": [["MOSS & PAPER", AMBER], [" • BOOKS • PLANTS • STATIONERY • ", WHITE], ["20% OFF", RED], [" • OPEN •", GREEN]],
}

var boards: Array[Dictionary] = []   ## {"node": MeshInstance3D, "kind", "business", "row", "text_len"}
var material: ShaderMaterial
var atlas: Dictionary

func _ready() -> void:
	var specs: Array[Dictionary] = []   # {"kind", "xf": Transform3D, "business", "message": Array}
	for id: String in ShopCatalog.LOCATIONS:
		var at: Vector3 = ShopCatalog.LOCATIONS[id]
		specs.append({"kind": "led_board_wall", "xf": Transform3D(Basis.IDENTITY, at + Vector3(4.75, 3.47, 5.26)),
			"business": String(ShopCatalog.TITLES[id]), "message": shop_message(id)})
	for i in range(3):
		var p: Vector3 = CityCatalog.PICKUPS[i] - Vector3.UP
		specs.append({"kind": "led_board_blade", "xf": Transform3D(Basis.IDENTITY, p + Vector3(1.75, 4.05, 3.08)),
			"business": String(RestaurantCatalog.LIST[i][1]), "message": restaurant_message(RestaurantCatalog.LIST[i])})
	var k := 3
	for b in RestaurantCatalog.corridor_buildings():
		var r: Array = RestaurantCatalog.LIST[k]
		var x := -int(b.bays) * 2.0 + RestaurantCatalog.restaurant_width(b)
		specs.append({"kind": "led_board_blade", "xf": RestaurantCatalog.frame(b) * Transform3D(Basis.IDENTITY, Vector3(x, 4.45, 0.1)),
			"business": String(r[1]), "message": restaurant_message(r)})
		k += 1
	var used := {}
	for block_id in range(9):
		for b in DowntownCatalog.buildings(block_id):
			var name := String(b.name)
			if not DOWNTOWN.has(name) or b.program != "mixed" or b.closed or absf(sin(float(b.yaw))) > 0.5: continue
			if int(used.get(name, 0)) >= 2: continue
			used[name] = int(used.get(name, 0)) + 1
			var frame := Transform3D(Basis(Vector3.UP, float(b.yaw)), b.root)
			specs.append({"kind": "led_board_long", "xf": frame * Transform3D(Basis.IDENTITY, Vector3(-float(b.width) * 0.5 + 2.4, 3.6, 0.12)),
				"business": name, "message": DOWNTOWN[name]})
	var messages: Array = []
	for s in specs: messages.append(s.message)
	atlas = LedFont.build_atlas(messages)
	material = ShaderMaterial.new()
	material.shader = preload("res://world/streets/led_board.gdshader")
	material.set_shader_parameter("atlas", atlas.texture)
	var widths: PackedInt32Array = atlas.widths
	for i in range(specs.size()):
		var s: Dictionary = specs[i]
		var node := MeshInstance3D.new()
		node.name = "LedBoard_%02d" % i
		node.mesh = mesh(String(s.kind))
		node.transform = s.xf
		for surface in range(node.mesh.get_surface_count()):
			var m := node.mesh.surface_get_material(surface)
			if m != null and m.resource_name == "LedScreen": node.set_surface_override_material(surface, material)
		node.visibility_range_end = RANGE
		node.visibility_range_end_margin = 15.0
		node.set_instance_shader_parameter("row", float(i))
		node.set_instance_shader_parameter("text_len", float(widths[i]))
		node.set_instance_shader_parameter("cols", float(KINDS[s.kind]))
		node.set_instance_shader_parameter("speed", 15.0 + float(i % 4) * 1.5)
		node.set_instance_shader_parameter("phase", float((i * 37) % 200))
		add_child(node)
		boards.append({"node": node, "kind": s.kind, "business": s.business, "row": i, "text_len": widths[i]})

var _meshes := {}
func mesh(kind: String) -> Mesh:
	if not _meshes.has(kind):
		var root: Node = (load(KIT % kind) as PackedScene).instantiate()
		_meshes[kind] = (root.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D).mesh
		root.free()
	return _meshes[kind]

## Shop marquee: name, three products with prices, opening hours.
static func shop_message(id: String) -> Array:
	var out: Array = [[String(ShopCatalog.TITLES[id]), AMBER]]
	var n := 0
	for item: String in ShopCatalog.ITEMS:
		var it: Dictionary = ShopCatalog.ITEMS[item]
		if String(it.get("shop", "")) != id or n >= 3: continue
		var short := String(it.name).split(" (")[0]
		out.append([" • " + short + " ", WHITE])
		out.append(["$%d" % int(round(float(it.price) / 100.0)), RED])
		n += 1
	out.append([" • OPEN 08-22 •", GREEN])
	return out

## Restaurant marquee: Turkish name, tagline, two dishes with prices, delivery and a greeting.
static func restaurant_message(r: Array) -> Array:
	var out: Array = [[LedFont.upper_tr(String(r[2])), AMBER], [" • " + String(r[3]) + " • ", GREEN]]
	var menu: Array = r[10]
	for j in range(mini(2, menu.size())):
		var dish := String(menu[j])
		var at := dish.rfind(" ")
		out.append([LedFont.upper_tr(dish.substr(0, at)) + " ", WHITE])
		out.append([dish.substr(at + 1), RED])
		out.append([" • ", WHITE])
	out.append(["PAKET SERVİS ", CYAN])
	out.append(["♥ AFİYET OLSUN •", RED])
	return out
