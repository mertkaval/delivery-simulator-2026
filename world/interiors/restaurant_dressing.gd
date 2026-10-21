class_name RestaurantDressing
extends RefCounted
## Interior-pack dressing for the restaurants (props from tools/prepare_interiors.py):
## * bakery trays and bread baskets on the service counters of the bakeries, dessert shops,
##   the soup house and the local diner, and on the Rainline Café counter downtown;
## * the Katydid café food bar (display vitrine, register, grinder, cakes, fruit) as the service
##   counter of the Pancake House (breakfast café), in place of the kit counter;
## * planter troughs along the facades beside the sidewalk tables (restaurant terraces).
## Counter tops keep the courier pickup shelf, the register, the waiter's pass spot
## (xe - 1.0, TableService) and the menu boards clear.

const RANGE := 30.0
const COUNTER_TOP := 1.04      ## rs_counter stone top (restaurant frame)
const COUNTER_Z := -7.34       ## along the counter, a little to the staff side
## Counter slots, x relative to the entrance bay centre xe: -0.42 (between the pass spot and the
## register), 0.95 (left of the ayran machine), 2.27 (right end, before the pickup shelf).
const BAKERY := {
	"pastry_shop": [["tray_rolls", 0.95, 0.0], ["tray_breads", 2.27, 0.0], ["bread_basket", -0.42, 0.2]],
	"dessert_shop": [["tray_pastries", 0.95, 0.0], ["tray_cookies", 2.27, 0.0]],
	"dairy_dessert": [["tray_cookies", 0.95, 0.0]],
	"soup_house": [["bread_basket", 0.95, -0.15]],
	"local_diner": [["bread_basket", 0.95, 0.1], ["tray_breads", 2.27, 0.0]],
}
const FOOD_BAR_RESTAURANT := "pancake_house"
const FOOD_BAR_X := -0.5        ## food bar centre relative to xe: spans xe-3.0 .. xe+2.0
const FOOD_BAR_Y := 0.045       ## its top (0.998 above the base) meets the 1.045 pass-plate height
const TERRACE_TROUGHS := ["planter_trough_a", "planter_trough_b", "planter_trough_c"]

static func uses_food_bar(r: Array) -> bool:
	return str(r[0]) == FOOD_BAR_RESTAURANT and InteriorProps.has("food_bar_counter")

## Interior dressing casts no shadows (like the restaurant kit interiors); terrace planters do.
static func spawn(parent: Node3D, id: String, xform: Transform3D, range_end: float = RANGE, shadows: int = 0) -> Node3D:
	var node := InteriorProps.spawn(id, xform, range_end, shadows)
	if node != null:
		node.set_meta("interior_dressing", true)
		parent.add_child(node)
	return node

## Counter-top bakery props of one corridor restaurant (t = restaurant frame).
static func counter(parent: Node3D, t: Transform3D, r: Array, xe: float) -> void:
	for slot: Array in BAKERY.get(str(r[0]), []):
		spawn(parent, str(slot[0]), t * Transform3D(Basis(Vector3.UP, float(slot[2])), Vector3(xe + float(slot[1]), COUNTER_TOP, COUNTER_Z)))

## The food bar replaces the two kit counter modules, the register and the ayran machine.
static func food_bar(parent: RestaurantInteriors, t: Transform3D, xe: float) -> void:
	var at := Vector3(xe + FOOD_BAR_X, FOOD_BAR_Y, -7.3)
	spawn(parent, "food_bar_counter", t * Transform3D(Basis.IDENTITY, at))
	var size := InteriorProps.size_of("food_bar_counter")
	parent.local_box(t, at + Vector3(0, 0.55, 0), Vector3(size.x, 1.1, size.z))

## Planter troughs under the dining-bay windows, beside the sidewalk tables.
static func terrace(parent: RestaurantInteriors, t: Transform3D, b: Dictionary, e: int, bays: int) -> void:
	for i in range(bays):
		if i == e: continue
		var x := RestaurantCatalog.bay_x(b, i)
		var id: String = TERRACE_TROUGHS[(i + int(b.id)) % TERRACE_TROUGHS.size()]
		var at := Vector3(x, 0.06, 0.3)
		spawn(parent, id, t * Transform3D(Basis.IDENTITY, at), 90.0, 1)
		parent.local_box(t, at + Vector3(0, 0.3, 0), Vector3(1.0, 0.6, 0.5))

## Rainline Café (downtown pickup 3): pastry trays on its lobby service counter.
static func downtown_cafe(parent: Node3D) -> void:
	var b: Dictionary = DowntownCatalog.buildings(0)[0]
	if str(b.name) != "Rainline Café" or bool(b.closed): return
	var bay_count := int(float(b.width) / 4.0)
	@warning_ignore("integer_division")
	var entry_x := -bay_count * 2.0 + 2.0 + (bay_count / 2) * 4.0
	var room := Transform3D(Basis(Vector3.UP, float(b.yaw)), b.root as Vector3) * Transform3D(Basis.IDENTITY, Vector3(entry_x, 0, 0))
	var local := parent.global_transform.affine_inverse() if parent.is_inside_tree() else Transform3D.IDENTITY
	# service counter (DowntownDistrict) at z -3.55, stone top 1.08, POS terminal at x +0.7
	spawn(parent, "tray_pastries", local * room * Transform3D(Basis.IDENTITY, Vector3(-0.95, 1.08, -3.6)))
	spawn(parent, "tray_cookies", local * room * Transform3D(Basis(Vector3.UP, 0.1), Vector3(-0.42, 1.08, -3.62)))
