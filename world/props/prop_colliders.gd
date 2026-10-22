class_name PropColliders
extends RefCounted
## Simple primitive colliders for the city's instanced props (fences, hedges, yard furniture,
## benches, bins, poles, planters, rocks, café chairs, showroom vehicles...), added by the code that
## places the instances, from the same deterministic transforms - so the solids always match what
## is drawn. One StaticBody3D per 64 m cell and layer holds the shapes (Jolt keeps one compound per
## body; a few thousand shapes cost a few hundred bodies, not one node per instance), and box
## shapes of the same size share one BoxShape3D resource.
##
## Layers (the player's body masks both; nothing else does):
##   LAYER_THIN  (layer 6, value 32): fences, hedges, poles, bins, benches, chairs, planters, rocks.
##     The third-person camera arm ignores them (no jitter along fences and lamp posts), the E /
##     click interaction ray (mask 1) looks through them, AI traffic and pedestrians (masks 1 | 4)
##     never see them.
##   LAYER_BULKY (layer 7, value 64): sheds, the downtown bus shelter, showroom cars - large enough
##     that the camera arm should pull in rather than clip inside them.
## Shapes are kept in local prop space in SOLIDS (centre, size), measured from the meshes at
## courier-body height (0.12-1.8 m above the base; tools/measure_prop_solids.gd prints them).
## DS_NO_PROP_COLLIDERS=1 disables them all (A/B physics timing).

const LAYER_THIN := 32
const LAYER_BULKY := 64
const CELL := 64.0
## asset -> [[centre, size, bulky?], ...] in the prop's local frame (front +Z, ground at y 0).
const SOLIDS := {
	# Residential yards (HouseInstancer kit pieces). Front fences and hedges are built as runs.
	"patio_set": [[Vector3(0, 0.47, 0), Vector3(1.5, 0.94, 2.0), false]],
	"bbq": [[Vector3(0, 0.595, 0), Vector3(1.0, 1.19, 0.55), false]],
	"raised_bed": [[Vector3(0, 0.23, 0), Vector3(2.46, 0.46, 1.26), false]],
	"shed": [[Vector3(0, 1.36, -0.95), Vector3(2.5, 2.72, 2.0), true]],
	"bins_trio": [[Vector3(0, 0.53, -0.04), Vector3(2.14, 1.06, 0.84), false]],
	"mailbox": [[Vector3(0.014, 0.705, 0.017), Vector3(0.36, 1.41, 0.5), false]],
	"address_post": [[Vector3(0, 0.625, 0), Vector3(0.16, 1.25, 0.16), false]],
	# Restaurant frontage and interior (RestaurantInteriors kit pieces).
	"rs_aframe": [[Vector3(0, 0.5, 0), Vector3(0.6, 1.0, 0.39), false]],
	"rs_planter": [[Vector3(0, 0.46, 0), Vector3(1.2, 0.92, 0.45), false]],
	"rs_plant": [[Vector3(0, 0.5, 0), Vector3(0.46, 1.0, 0.44), false]],
	# Downtown / civic campus (DowntownDistrict.place / module).
	"cafe_chair": [[Vector3(0, 0.425, 0), Vector3(0.43, 0.85, 0.43), false]],
	"reuse_park_bench": [[Vector3(0, 0.5, -0.05), Vector3(1.9, 1.0, 0.7), false]],
	"reuse_street_lamp": [[Vector3(0, 2.5, 0), Vector3(0.22, 5.0, 0.22), false]],
	"reuse_birch": [[Vector3(0, 1.75, 0), Vector3(0.36, 3.5, 0.36), false]],
	"reuse_maple": [[Vector3(0, 1.75, 0), Vector3(0.36, 3.5, 0.36), false]],
	"reuse_garden_planter": [[Vector3(-0.02, 0.5, -0.02), Vector3(1.3, 1.0, 1.1), false]],
	"reuse_bicycle": [[Vector3(0, 0.5, 0), Vector3(0.4, 1.0, 1.75), false]],
	"delivery_cart": [[Vector3(0, 0.49, 0), Vector3(0.9, 0.98, 0.66), false]],
	"parking_sign": [[Vector3(0, 1.3, 0), Vector3(0.12, 2.6, 0.12), false]],
	"loading_sign": [[Vector3(0, 1.3, 0), Vector3(0.12, 2.6, 0.12), false]],
	"bus_sign": [[Vector3(0, 1.3, 0), Vector3(0.12, 2.6, 0.12), false]],
	"parking_meter": [[Vector3(0, 0.785, 0), Vector3(0.2, 1.57, 0.2), false]],
	"mailboxes": [[Vector3(0, 0.7, 0.024), Vector3(1.35, 1.4, 0.3), false]],
	"hydrant": [[Vector3(0, 0.46, 0), Vector3(0.42, 0.92, 0.42), false]],
	"trash_bin": [[Vector3(0, 0.46, 0), Vector3(0.6, 0.92, 0.6), false]],
	"recycle_bin": [[Vector3(0, 0.56, 0), Vector3(0.57, 1.12, 0.69), false]],
	"newspaper_box": [[Vector3(0, 0.61, 0.016), Vector3(0.5, 1.22, 0.47), false]],
	"bike_rack": [[Vector3(0, 0.467, 0), Vector3(1.08, 0.93, 0.18), false]],
	"cone": [[Vector3(0, 0.25, 0), Vector3(0.26, 0.5, 0.26), false]],
	"grocery_shelf": [[Vector3(0, 1.0, 0.2), Vector3(1.62, 2.0, 0.48), false]],
	"pallet_supplies": [[Vector3(0, 0.36, 0), Vector3(1.2, 0.72, 1.1), false]],
	"bus_shelter": [[Vector3(0, 1.3, -0.4), Vector3(4.4, 2.6, 0.8), true]],
	"living_rain_garden": [[Vector3(0, 0.3, 0), Vector3(3.4, 0.6, 1.35), false]],
	"living_stop": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	"living_cycle_sign": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	"living_speed": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	"living_taxi_sign": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	"living_school_zone": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	"living_hospital_sign": [[Vector3(0, 1.4, 0), Vector3(0.12, 2.8, 0.12), false]],
	# Street furniture flower planters (PropKit, StreetFurniture.shopfronts).
	"planter_geranium_red": [[Vector3(0, 0.45, 0), Vector3(0.55, 0.9, 0.55), false]],
	"planter_geranium_pink": [[Vector3(0, 0.45, 0), Vector3(0.55, 0.9, 0.55), false]],
	"planter_geranium_orange": [[Vector3(0, 0.45, 0), Vector3(0.55, 0.9, 0.55), false]],
	"planter_geranium_purple": [[Vector3(0, 0.45, 0), Vector3(0.55, 0.9, 0.55), false]],
	# Landscape kit (CityLandscape): pots by shop doors and rocks (rocks only when >= MIN_ROCK tall).
	"potted_lily": [[Vector3(0, 0.5, 0), Vector3(0.4, 1.0, 0.4), false]],
	"potted_snake": [[Vector3(0, 0.42, 0), Vector3(0.29, 0.83, 0.28), false]],
	"rock_0": [[Vector3(0.07, 0.45, 0.17), Vector3(1.55, 0.9, 1.35), false]],
	"rock_1": [[Vector3(-0.53, 0.36, 0.4), Vector3(1.25, 0.72, 1.0), false]],
	"rock_2": [[Vector3(-0.05, 0.17, 0.33), Vector3(0.6, 0.34, 0.7), false]],
	"rock_3": [[Vector3(0.04, 0.27, -0.12), Vector3(1.0, 0.54, 0.72), false]],
	"rock_4": [[Vector3(-0.05, 0.25, 0.06), Vector3(1.1, 0.5, 1.9), false]],
	"rock_5": [[Vector3(-0.27, 0.38, 0), Vector3(1.2, 0.76, 1.5), false]],
	"rock_6": [[Vector3(-0.19, 0.27, -0.06), Vector3(1.15, 0.54, 0.88), false]],
	"rock_7": [[Vector3(-0.26, 0.19, 0.34), Vector3(0.55, 0.38, 0.62), false]],
	"rock_8": [[Vector3(-0.13, 0.16, -0.16), Vector3(0.55, 0.32, 0.55), false]],
	# Showrooms and store pickup shelves.
	"showroom_bicycle": [[Vector3(0, 0.5, 0), Vector3(0.45, 1.0, 1.75), false]],
	"showroom_scooter": [[Vector3(0, 0.6, 0.015), Vector3(0.6, 1.2, 1.9), false]],
	"pickup_locker": [[Vector3(0, 0.95, 0), Vector3(1.6, 1.9, 0.45), false]],
}
## Rocks lower than this (after scaling) stay walk-over / step-around scenery without a collider.
const MIN_ROCK := 0.4

static var enabled := OS.get_environment("DS_NO_PROP_COLLIDERS") != "1"
## Statistics for tests / profiling: shapes per tag, bodies created.
static var shape_count := 0
static var body_count := 0
static var tags: Dictionary = {}
static var _boxes: Dictionary = {}

var owner: Node3D
var prefix: String
var bodies: Dictionary = {}

func _init(parent: Node3D, body_prefix: String = "PropCollision") -> void:
	owner = parent
	prefix = body_prefix

static func has(asset: String) -> bool:
	return SOLIDS.has(asset)

static func box_shape(size: Vector3) -> BoxShape3D:
	var key := "%d_%d_%d" % [roundi(size.x * 1000.0), roundi(size.y * 1000.0), roundi(size.z * 1000.0)]
	if not _boxes.has(key):
		var b := BoxShape3D.new()
		b.size = size
		_boxes[key] = b
	return _boxes[key]

func body_for(at: Vector3, bulky: bool) -> StaticBody3D:
	var cell := Vector2i(floori(at.x / CELL), floori(at.z / CELL))
	var key := "%d_%d_%s" % [cell.x, cell.y, "b" if bulky else "t"]
	if not bodies.has(key):
		var body := StaticBody3D.new()
		body.name = "%s_%s" % [prefix, key]
		body.collision_layer = LAYER_BULKY if bulky else LAYER_THIN
		body.collision_mask = 0
		body.set_meta("prop_colliders", true)
		owner.add_child(body)
		bodies[key] = body
		body_count += 1
	return bodies[key]

## A box with centre `centre` (world, in the owner's frame) and `size` along `basis` (scale is
## folded into the size; the basis may carry one).
func box(centre: Vector3, size: Vector3, basis: Basis, bulky: bool = false, tag: String = "") -> CollisionShape3D:
	if not enabled: return null
	var s := size * basis.get_scale()
	var node := CollisionShape3D.new()
	node.shape = box_shape(Vector3(absf(s.x), absf(s.y), absf(s.z)))
	node.transform = Transform3D(basis.orthonormalized(), centre)
	if tag != "":
		node.set_meta("prop", tag)
		tags[tag] = int(tags.get(tag, 0)) + 1
	body_for(centre, bulky).add_child(node)
	shape_count += 1
	return node

## The SOLIDS shapes of `asset` placed with `xform` (owner frame). False when it has none.
func solid(asset: String, xform: Transform3D) -> bool:
	if not enabled or not SOLIDS.has(asset): return false
	for part: Array in SOLIDS[asset]:
		var centre: Vector3 = part[0]
		var size: Vector3 = part[1]
		if asset.begins_with("rock_") and size.y * xform.basis.get_scale().y < MIN_ROCK: continue
		box(xform * centre, size, xform.basis, bool(part[2]), asset)
	return true

## One box along a straight run from `a` to `b` (ground points, owner frame): fences, hedges.
func run(a: Vector3, b: Vector3, height: float, thickness: float, tag: String, bulky: bool = false) -> void:
	if not enabled or a.distance_to(b) < 0.05: return
	var along := b - a
	along.y = 0.0
	var basis := Basis(Vector3.UP, atan2(along.x, along.z))
	box((a + b) * 0.5 + Vector3(0, height * 0.5, 0), Vector3(thickness, height, along.length()), basis, bulky, tag)

static func reset_stats() -> void:
	shape_count = 0
	body_count = 0
	tags.clear()
