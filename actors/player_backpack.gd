class_name WornBackpack
extends Node3D
## The courier's bag worn on the back in third person: the insulated delivery bag once it is
## owned (else the plain courier backpack), on a BoneAttachment3D on the UpperChest, so it rides
## along walking, running, jumping and on the bicycle.
##
## With the animation contract (clips.json "backpack" block): the worn scene
## (assets/player/backpack_worn.tscn, or backpack_plain_worn.tscn) is the attachment's child at
## an identity transform (its "Bag" child carries the fitted offset), the body straps
## (BackpackStrapL / R, skinned in the courier) are shown while it is worn, and the courier's
## locomotion switches to the arms-round-the-bag variants (PlayerAvatar.set_bag_worn). The open
## bag in the hands during the bag sequences is the held scene (backpack_held.tscn) under the
## courier scene root, driven by each clip's bag_track (CourierSequence).
##
## Without the contract (fallback): the closed delivery bag laid along the spine line (up = hips
## -> upper chest), back panel against the back, recomputed every frame from the IK's final pose;
## the procedural sequences swing that model off the back (detach / attach).

const DELIVERY_BAG := "res://assets/delivery/delivery_bag.glb"
const DELIVERY_BAG_OPEN := "res://assets/delivery/delivery_bag_open.glb"
const BACK_GAP := 0.105           ## spine (UpperChest bone) to the back surface (m), fallback
const BOTTOM_BELOW_CHEST := 0.4   ## bag bottom below the UpperChest joint, along the spine (m)

var avatar: PlayerAvatar
var attachment: BoneAttachment3D
var model: Node3D             ## the worn bag (scene root) or the fallback closed bag
var open_model: Node3D        ## fallback: the open delivery bag, shown while packing
var held: Node3D              ## contract: the open bag in the hands (backpack_held.tscn)
var kind := ""                ## "", "delivery_bag", "backpack"
var on_back := true
var spec: Dictionary = {}     ## clips.json "backpack" block ({} without the contract)
var straps: Array[Node3D] = []
var _bone := -1
var _hips := -1
var _depth := 0.24
var _worn := Transform3D.IDENTITY
var _chest_key := "upper_chest"

func setup(owner_avatar: PlayerAvatar) -> void:
	avatar = owner_avatar
	name = "WornBackpack"
	var c: Variant = avatar.read_contract().get("backpack", {})
	spec = c if c is Dictionary and ResourceLoader.exists(str((c as Dictionary).get("worn_scene", ""))) else {}
	var bone := str(spec.get("bone", avatar.ik.names.get("upper_chest", "UpperChest")))
	if avatar.skeleton.find_bone(bone) < 0: bone = str(avatar.ik.names.get("chest", "Chest"))
	attachment = BoneAttachment3D.new()
	attachment.name = "BackpackAttachment"
	attachment.bone_name = bone
	avatar.skeleton.add_child(attachment)
	_bone = avatar.skeleton.find_bone(bone)
	_hips = avatar.skeleton.find_bone(str(avatar.ik.names.get("hips", "Hips")))
	_chest_key = "upper_chest" if bone == str(avatar.ik.names.get("upper_chest", "UpperChest")) else "chest"
	for strap_name: String in ["BackpackStrapL", "BackpackStrapR"]:
		var n := avatar.body.find_child(strap_name, true, false) as Node3D
		if n != null: straps.append(n)
	set_body_straps(false, false)

## Contract scenes in use (worn / held bag scenes, straps, bag variants, tracks).
func scene_mode() -> bool:
	return not spec.is_empty()

func _process(_delta: float) -> void:
	if not scene_mode(): follow()

# --- Fallback placement along the spine -------------------------------------------------------------

func worn_transform() -> Transform3D:
	var sk := avatar.skeleton
	var ik := avatar.ik
	var chest: Transform3D = ik.solved_xf.get(_chest_key, sk.global_transform * sk.get_bone_global_pose(_bone))
	var hips: Vector3 = ik.solved.get("hips", (sk.global_transform * sk.get_bone_global_pose(_hips)).origin if _hips >= 0 else chest.origin - Vector3.UP * 0.36)
	var up := (chest.origin - hips).normalized()
	var fwd := -avatar.global_basis.z
	fwd = (fwd - up * fwd.dot(up)).normalized()
	var z := -fwd
	var x := up.cross(z).normalized()
	# Seated on a bike the trunk leans: the bag settles a little lower onto the small of the back.
	var at := chest.origin - fwd * (BACK_GAP + _depth) - up * (BOTTOM_BELOW_CHEST + 0.07 * avatar.seat_blend)
	return Transform3D(Basis(x, up, z), at)

func follow() -> void:
	if scene_mode() or _bone < 0 or avatar == null or not avatar.ready_ok: return
	_worn = worn_transform()
	if model == null or not on_back or model.get_parent() != attachment: return
	model.global_transform = _worn

func depth_back() -> float:
	if model == null: return 0.24
	var box := PickupShelves.local_box(model)
	return -box.position.z if box.size.z > 0.05 else 0.24

# --- Owning / wearing ------------------------------------------------------------------------------

## Show the bag the courier owns: "delivery_bag", "backpack" or "" (none).
func refresh(owned: String) -> void:
	if owned == kind and (model != null or owned == ""): return
	kind = owned
	if model: model.queue_free()
	model = null
	if open_model: open_model.queue_free()
	open_model = null
	if held: held.queue_free()
	held = null
	if scene_mode() and owned != "":
		var path := str(spec.get("worn_scene" if owned == "delivery_bag" else "worn_plain_scene", ""))
		if ResourceLoader.exists(path): model = (load(path) as PackedScene).instantiate()
	elif owned == "delivery_bag" and ResourceLoader.exists(DELIVERY_BAG):
		model = (load(DELIVERY_BAG) as PackedScene).instantiate()
	elif owned == "backpack":
		model = CityAssets.create("backpack", 80)
	if model == null:
		kind = ""
		set_body_straps(false, false)
		avatar.set_bag_worn(false)
		return
	model.name = "WornBag"
	for gi: GeometryInstance3D in model.find_children("*", "GeometryInstance3D", true, false):
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		gi.visibility_range_end = 0.0
	_depth = depth_back()
	attachment.add_child(model)
	model.transform = Transform3D.IDENTITY
	on_back = true
	set_body_straps(scene_mode(), scene_mode())
	avatar.set_bag_worn(scene_mode())
	follow()
	avatar.refresh_visibility()

func has_bag() -> bool:
	return model != null

func set_body_straps(left: bool, right: bool) -> void:
	for n in straps:
		n.visible = left if str(n.name).ends_with("L") else right

## Contract: the worn bag shown on the back (true) or handed over to the held bag (false).
func socket_back(yes: bool) -> void:
	if model: model.visible = yes
	on_back = yes
	var h := held_bag()
	if h: h.visible = not yes and kind == "delivery_bag"

## The open delivery bag held in the hands (contract scene), made on first use, hidden.
func held_bag() -> Node3D:
	if held == null and scene_mode() and ResourceLoader.exists(str(spec.get("held_scene", ""))):
		held = (load(str(spec.held_scene)) as PackedScene).instantiate()
		held.name = "HeldBag"
		held.visible = false
		avatar.body.add_child(held)
		var flap_straps := held_node("FlapStraps")
		if flap_straps: flap_straps.visible = false
		avatar.refresh_visibility()
	return held

## A named part of the held bag (Flap, StrapL, StrapR, Slot_Top, FlapStraps).
func held_node(key: String) -> Node3D:
	if held == null: return null
	var path := str((spec.get("held_nodes", {}) as Dictionary).get(key, "Bag/DeliveryBag/" + key))
	var n := held.get_node_or_null(path) as Node3D
	if n == null: n = held.find_child(key, true, false) as Node3D
	return n

# --- Fallback sequences (procedural) ----------------------------------------------------------------

## Take the bag off the back: it keeps its world pose, now in the courier root's space.
func detach() -> void:
	if model == null or not on_back: return
	var at := model.global_transform
	model.reparent(avatar, false)
	model.global_transform = at
	on_back = false

## Courier-root-space transform of the bag sitting on the back right now (follows the pose).
func back_pose() -> Transform3D:
	return avatar.global_transform.affine_inverse() * (_worn if not scene_mode() else attachment.global_transform)

## Back onto the shoulders (snaps into the attachment).
func attach() -> void:
	if model == null: return
	open(false)
	model.visible = true
	if model.get_parent() != attachment: model.reparent(attachment, false)
	if scene_mode(): model.transform = Transform3D.IDENTITY
	on_back = true
	follow()

## Flap open / closed while the bag is off the back (the open delivery bag model in its place).
func open(yes: bool) -> void:
	if model == null or kind != "delivery_bag": return
	if open_model == null and ResourceLoader.exists(DELIVERY_BAG_OPEN):
		open_model = (load(DELIVERY_BAG_OPEN) as PackedScene).instantiate()
		open_model.name = "WornBagOpen"
		model.add_child(open_model)
	if open_model == null: return
	open_model.visible = yes
	for child in model.get_children():
		if child != open_model and child is Node3D: (child as Node3D).visible = not yes

var _fade := 0.0
## See-through when the third-person camera comes right up to it (a wall behind, browsing a
## shelf), like the townspeople the camera passes through.
func fade_near(camera_at: Vector3, delta: float, at_least := 0.0) -> void:
	if model == null or not model.is_visible_in_tree(): return
	var centre := model.global_transform * Vector3(0, 0.25, 0)
	if scene_mode():
		var bag := model.get_node_or_null("Bag") as Node3D
		if bag: centre = bag.global_transform * Vector3(0, 0.25, 0)
	var want := maxf(at_least, clampf((0.85 - camera_at.distance_to(centre)) / 0.35, 0.0, 0.8))
	var now := move_toward(_fade, want, delta * 5.0)
	if is_equal_approx(now, _fade): return
	_fade = now
	for gi: GeometryInstance3D in model.find_children("*", "GeometryInstance3D", true, false):
		gi.transparency = _fade

## The node the bag shows (closed or open), for hand targets and contents.
func shown() -> Node3D:
	return open_model if open_model != null and open_model.visible else model
