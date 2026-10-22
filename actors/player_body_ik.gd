class_name PlayerBodyIK
extends SkeletonModifier3D
## Procedural pose layer for the player's body, run after the AnimationTree each tick:
## - seat: hips onto a saddle point, torso leaned so the hands reach the grips;
## - limbs: analytic two-bone IK for both arms (hands on grips / a carried package) and both
##   legs (balls of the feet on the pedals, knees forward), with hand/foot orientation;
## - look: neck + head turn towards a look direction within human limits.
## All targets are world space; PlayerAvatar sets them and their weights every tick.
## Bone names follow Godot's humanoid profile (the retargeted "GeneralSkeleton").

const BONES := {"hips": "Hips", "spine": "Spine", "chest": "Chest", "upper_chest": "UpperChest", "neck": "Neck", "head": "Head",
	"l_upper_arm": "LeftUpperArm", "l_lower_arm": "LeftLowerArm", "l_hand": "LeftHand", "l_knuckle": "LeftMiddleProximal",
	"r_upper_arm": "RightUpperArm", "r_lower_arm": "RightLowerArm", "r_hand": "RightHand", "r_knuckle": "RightMiddleProximal",
	"l_upper_leg": "LeftUpperLeg", "l_lower_leg": "LeftLowerLeg", "l_foot": "LeftFoot", "l_toes": "LeftToes",
	"r_upper_leg": "RightUpperLeg", "r_lower_leg": "RightLowerLeg", "r_foot": "RightFoot", "r_toes": "RightToes"}

## Bone names in use (BONES, renamed by the body's contract where its rig differs).
var names: Dictionary = BONES.duplicate()

## Seat: hips bone world position and torso direction (hips -> shoulders, world) to blend towards.
var seat_weight := 0.0
var hips_target := Vector3.ZERO
var torso_up := Vector3.UP
## false: only place the hips (the pose already has its trunk lean).
var seat_bend := true
## Limb targets (world): palm centre / ball of the foot, plus the wanted orientation of the hand
## (fingers direction, palm normal) and foot (toes direction, sole normal), and pole directions.
var arm_weight := [0.0, 0.0]
var arm_target: Array[Vector3] = [Vector3.ZERO, Vector3.ZERO]
var hand_fingers: Array[Vector3] = [Vector3.FORWARD, Vector3.FORWARD]
var hand_palm: Array[Vector3] = [Vector3.DOWN, Vector3.DOWN]
var elbow_pole: Array[Vector3] = [Vector3.DOWN, Vector3.DOWN]
var leg_weight := [0.0, 0.0]
var leg_target: Array[Vector3] = [Vector3.ZERO, Vector3.ZERO]
var foot_forward: Array[Vector3] = [Vector3.FORWARD, Vector3.FORWARD]
var foot_sole: Array[Vector3] = [Vector3.DOWN, Vector3.DOWN]
var knee_pole: Array[Vector3] = [Vector3.FORWARD, Vector3.FORWARD]
## Head: world look direction, weight; limits (radians) of the turn relative to the chest.
var look_weight := 0.0
var look_dir := Vector3.FORWARD
var look_yaw_limit := 1.15
var look_pitch_limit := 0.55
## Roll that keeps the head nearer level when the body leans (0..1 of the chest roll removed).
var head_level := 0.0

var ids := {}
## Rest-space reference directions (skeleton space): body faces +Z, so hand fingers point out
## along +-X with palms down in the T pose; feet point +Z with soles down; the face looks +Z.
var rest_hand_fingers: Array[Vector3] = [Vector3.RIGHT, Vector3.LEFT]
var rest_foot_forward: Array[Vector3] = [Vector3.BACK, Vector3.BACK]
var rest_global := {}
## Last solved positions (world) for tests / debugging.
var solved := {}

func _ready() -> void:
	bind()

func bind() -> void:
	var skeleton := get_skeleton()
	if skeleton == null: return
	ids.clear()
	for key: String in names:
		ids[key] = skeleton.find_bone(str(names[key]))
	for key: String in ids:
		if int(ids[key]) >= 0: rest_global[key] = skeleton.get_bone_global_rest(int(ids[key]))
	# Measure the rest directions instead of assuming them (Mixamo-style rigs differ).
	for side in range(2):
		var p := "l_" if side == 0 else "r_"
		if has_all([p + "hand", p + "knuckle"]):
			rest_hand_fingers[side] = ((rest_global[p + "knuckle"] as Transform3D).origin - (rest_global[p + "hand"] as Transform3D).origin).normalized()
		if has_all([p + "foot", p + "toes"]):
			var f := (rest_global[p + "toes"] as Transform3D).origin - (rest_global[p + "foot"] as Transform3D).origin
			f.y = 0.0
			if f.length() > 0.01: rest_foot_forward[side] = f.normalized()

func has_all(keys: Array) -> bool:
	for k: String in keys:
		if int(ids.get(k, -1)) < 0: return false
	return true

func bone_id(key: String) -> int:
	return int(ids.get(key, -1))

## Global (skeleton-space) pose of a bone from the current local poses.
func gpose(b: int) -> Transform3D:
	var skeleton := get_skeleton()
	var t := skeleton.get_bone_pose(b)
	var p := skeleton.get_bone_parent(b)
	while p >= 0:
		t = skeleton.get_bone_pose(p) * t
		p = skeleton.get_bone_parent(p)
	return t

func parent_global(b: int) -> Transform3D:
	var p := get_skeleton().get_bone_parent(b)
	return gpose(p) if p >= 0 else Transform3D.IDENTITY

## Give bone `b` the skeleton-space basis `basis` (rotation only).
func set_bone_global_basis(b: int, basis: Basis) -> void:
	var local := parent_global(b).basis.inverse() * basis
	get_skeleton().set_bone_pose_rotation(b, local.orthonormalized().get_rotation_quaternion())

## Rotate bone `b` by the skeleton-space rotation `q` (about its own origin).
func rotate_global(b: int, q: Quaternion) -> void:
	set_bone_global_basis(b, Basis(q) * gpose(b).basis)

func _process_modification_with_delta(_delta: float) -> void:
	var skeleton := get_skeleton()
	if skeleton == null: return
	if ids.is_empty(): bind()
	var to_skel := skeleton.global_transform.affine_inverse()
	var basis_to_skel := to_skel.basis.orthonormalized()
	if seat_weight > 0.001 and has_all(["hips", "spine", "chest", "neck"]):
		seat(to_skel * hips_target, (basis_to_skel * torso_up).normalized(), seat_weight)
	if look_weight > 0.001 and has_all(["neck", "head"]):
		look((basis_to_skel * look_dir).normalized(), look_weight)
	for side in range(2):
		var p := "l_" if side == 0 else "r_"
		if float(arm_weight[side]) > 0.001 and has_all([p + "upper_arm", p + "lower_arm", p + "hand"]):
			solved[p + "palm"] = skeleton.global_transform * limb(bone_id(p + "upper_arm"), bone_id(p + "lower_arm"), bone_id(p + "hand"), bone_id(p + "knuckle"), to_skel * arm_target[side],
				(basis_to_skel * elbow_pole[side]).normalized(), basis_to_skel * hand_fingers[side], basis_to_skel * hand_palm[side],
				rest_hand_fingers[side], Vector3.DOWN, float(arm_weight[side]), true)
		if float(leg_weight[side]) > 0.001 and has_all([p + "upper_leg", p + "lower_leg", p + "foot"]):
			solved[p + "ball"] = skeleton.global_transform * limb(bone_id(p + "upper_leg"), bone_id(p + "lower_leg"), bone_id(p + "foot"), bone_id(p + "toes"), to_skel * leg_target[side],
				(basis_to_skel * knee_pole[side]).normalized(), basis_to_skel * foot_forward[side], basis_to_skel * foot_sole[side],
				rest_foot_forward[side], Vector3.DOWN, float(leg_weight[side]), false)
	if true:
		var xf := skeleton.global_transform
		for key in ["hips", "l_hand", "r_hand", "l_knuckle", "r_knuckle", "l_foot", "r_foot", "l_toes", "r_toes", "head", "l_upper_arm", "r_upper_arm"]:
			if bone_id(key) >= 0: solved[key] = xf * gpose(bone_id(key)).origin

## Hips to the seat point, then bend the spine so the torso points along `up`.
func seat(hips_at: Vector3, up: Vector3, w: float) -> void:
	var skeleton := get_skeleton()
	var hips := bone_id("hips")
	var hips_g := gpose(hips)
	var want := hips_g.origin.lerp(hips_at, w)
	var parent := parent_global(hips)
	skeleton.set_bone_pose_position(hips, parent.affine_inverse() * want)
	if not seat_bend: return
	# Torso: shoulders onto the line from the hips along `up`. Spine takes ~half the bend, the
	# chest the rest (a rounded back); each joint turns the shoulders towards that point.
	var hips_now := gpose(hips).origin
	var start := shoulders()
	var span := start.distance_to(hips_now)
	var goal_dir := (start - hips_now).normalized().slerp(up, w).normalized()
	var goal := hips_now + goal_dir * span
	for pass_index in range(3):
		var bone := bone_id("spine") if pass_index == 0 else bone_id("chest")
		var share := 0.5 if pass_index == 0 else 1.0
		var pivot := gpose(bone).origin
		var current := (shoulders() - pivot).normalized()
		var target := (goal - pivot).normalized()
		if current.dot(target) > 0.999999: continue
		rotate_global(bone, Quaternion.IDENTITY.slerp(Quaternion(current, target), share))
	# Neck: a leaning rider holds the head up over the shoulders instead of letting it hang.
	if has_all(["neck", "head"]):
		var neck := bone_id("neck")
		var neck_g := gpose(neck)
		var head_at := gpose(bone_id("head")).origin
		var along := (head_at - neck_g.origin).normalized()
		var neck_dir := along.slerp(goal_dir.slerp(Vector3.UP, 0.7).normalized(), w).normalized()
		if along.dot(neck_dir) < 0.999999:
			rotate_global(neck, Quaternion(along, neck_dir))

## Midpoint of the shoulder joints (upper arms), or the neck.
func shoulders() -> Vector3:
	if has_all(["l_upper_arm", "r_upper_arm"]):
		return (gpose(bone_id("l_upper_arm")).origin + gpose(bone_id("r_upper_arm")).origin) * 0.5
	return gpose(bone_id("neck")).origin

## Neck + head towards `dir` (skeleton space), limited relative to the upper chest.
func look(dir: Vector3, w: float) -> void:
	var chest := gpose(bone_id("upper_chest") if bone_id("upper_chest") >= 0 else bone_id("chest"))
	var chest_rest: Transform3D = rest_global.get("upper_chest", rest_global.get("chest", Transform3D.IDENTITY))
	# Chest frame without rest orientation: forward / up of the torso now.
	var frame := chest.basis * chest_rest.basis.inverse()
	var local := (frame.inverse() * dir).normalized()
	var yaw := clampf(atan2(local.x, local.z), -look_yaw_limit, look_yaw_limit)
	var pitch := clampf(asin(clampf(-local.y, -1.0, 1.0)), -look_pitch_limit, look_pitch_limit)
	var wanted := frame * (Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch) * Vector3.BACK)
	for pass_index in range(2):
		var bone := bone_id("neck") if pass_index == 0 else bone_id("head")
		var share := 0.4 if pass_index == 0 else 1.0
		var head_g := gpose(bone_id("head"))
		var head_rest: Transform3D = rest_global["head"]
		var face := (head_g.basis * head_rest.basis.inverse() * Vector3.BACK).normalized()
		var target := face.slerp(wanted.normalized(), w).normalized()
		if face.dot(target) < 0.99999:
			rotate_global(bone, Quaternion.IDENTITY.slerp(Quaternion(face, target), share))
	# Level the head a little against body roll.
	if head_level > 0.001:
		var head := bone_id("head")
		var hg := gpose(head)
		var head_rest2: Transform3D = rest_global["head"]
		var up_now := (hg.basis * head_rest2.basis.inverse() * Vector3.UP).normalized()
		var face2 := (hg.basis * head_rest2.basis.inverse() * Vector3.BACK).normalized()
		var flat_up := (Vector3.UP - face2 * Vector3.UP.dot(face2)).normalized()
		if up_now.dot(flat_up) < 0.99999 and flat_up.length() > 0.5:
			rotate_global(head, Quaternion.IDENTITY.slerp(Quaternion(up_now, flat_up), head_level * w))

## limb() keeping the end bone's animated orientation (in skeleton space).
func limb_position_only(root: int, mid: int, end: int, tip: int, target: Vector3, pole: Vector3, w: float, palm: bool) -> Vector3:
	var end_g := gpose(end)
	var tip_point := end_g.origin
	if tip >= 0:
		var knuckle := gpose(tip).origin
		tip_point = end_g.origin.lerp(knuckle, 0.55 if palm else 1.0)
	var offset := tip_point - end_g.origin
	var joint_target := end_g.origin.lerp(target - offset, w)
	var local_basis := gpose(end).basis
	solve_chain(root, mid, end, joint_target, pole)
	set_bone_global_basis(end, local_basis)
	return gpose(end).origin + offset

## The two-bone solve itself: rotate root and mid so the end joint lands on `joint_target`.
func solve_chain(root: int, mid: int, end: int, joint_target: Vector3, pole: Vector3) -> void:
	var skeleton := get_skeleton()
	var root_g := gpose(root)
	var mid_g := root_g * skeleton.get_bone_pose(mid)
	var end_g := mid_g * skeleton.get_bone_pose(end)
	var a := root_g.origin.distance_to(mid_g.origin)
	var b := mid_g.origin.distance_to(end_g.origin)
	var to_t := joint_target - root_g.origin
	var d := clampf(to_t.length(), absf(a - b) + 0.002, a + b - 0.002)
	var dir := to_t.normalized()
	var pole_dir := pole - dir * pole.dot(dir)
	if pole_dir.length() < 0.001: pole_dir = Vector3.UP - dir * dir.y
	pole_dir = pole_dir.normalized()
	var cos_a := clampf((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0)
	var mid_new := root_g.origin + (dir * cos_a + pole_dir * sqrt(1.0 - cos_a * cos_a)) * a
	var from1 := (mid_g.origin - root_g.origin).normalized()
	var to1 := (mid_new - root_g.origin).normalized()
	if from1.dot(to1) < 0.999999:
		set_bone_global_basis(root, Basis(Quaternion(from1, to1)) * root_g.basis)
	var root2 := gpose(root)
	var mid2 := root2 * skeleton.get_bone_pose(mid)
	var end2 := mid2 * skeleton.get_bone_pose(end)
	var from2 := (end2.origin - mid2.origin).normalized()
	var to2 := (root_g.origin + dir * d - mid2.origin).normalized()
	if from2.dot(to2) < 0.999999:
		set_bone_global_basis(mid, Basis(Quaternion(from2, to2)) * mid2.basis)

## Two-bone IK, returns where the effector ended up. `target` is where the end effector point should go: for an arm the palm centre
## (between wrist and knuckles), for a leg the ball of the foot (toes joint). The end bone gets
## the orientation that maps its rest "fingers / toes" direction onto `fwd` and down onto `normal`.
func limb(root: int, mid: int, end: int, tip: int, target: Vector3, pole: Vector3, fwd: Vector3, normal: Vector3,
		rest_fwd: Vector3, rest_normal: Vector3, w: float, palm: bool) -> Vector3:
	var skeleton := get_skeleton()
	var root_g := gpose(root)
	var mid_g := root_g * skeleton.get_bone_pose(mid)
	var end_g := mid_g * skeleton.get_bone_pose(end)
	# Wanted end-bone orientation (skeleton space) from the rest frame.
	var end_rest: Transform3D = Transform3D.IDENTITY
	for key: String in rest_global:
		if bone_id(key) == end: end_rest = rest_global[key]
	if fwd == Vector3.ZERO:
		# Keep the animated orientation of the end bone; only the position is solved.
		return limb_position_only(root, mid, end, tip, target, pole, w, palm)
	var f := fwd.normalized()
	var n := (normal - f * normal.dot(f)).normalized()
	var rf := rest_fwd.normalized()
	var rn := (rest_normal - rf * rest_normal.dot(rf)).normalized()
	var want_frame := Basis(f, n, f.cross(n))
	var rest_frame := Basis(rf, rn, rf.cross(rn))
	var end_basis := (want_frame * rest_frame.inverse()) * end_rest.basis
	end_basis = end_g.basis.orthonormalized().slerp(end_basis.orthonormalized(), w)
	# Offset from the end joint to the effector point in that orientation.
	var tip_local := Vector3.ZERO
	if tip >= 0:
		var tip_rest_g: Transform3D = Transform3D.IDENTITY
		for key: String in rest_global:
			if bone_id(key) == tip: tip_rest_g = rest_global[key]
		var off_rest := tip_rest_g.origin - end_rest.origin
		# Palm centre is halfway to the knuckles, a little towards the palm side.
		var off := off_rest * (0.55 if palm else 1.0)
		tip_local = end_rest.basis.inverse() * off
		if palm: tip_local += end_rest.basis.inverse() * (rn * 0.02)
	var joint_target := target - end_basis * tip_local
	joint_target = end_g.origin.lerp(joint_target, w)
	var a := root_g.origin.distance_to(mid_g.origin)
	var b := mid_g.origin.distance_to(end_g.origin)
	var to_t := joint_target - root_g.origin
	var d := clampf(to_t.length(), absf(a - b) + 0.002, a + b - 0.002)
	var dir := to_t.normalized()
	var pole_dir := pole - dir * pole.dot(dir)
	if pole_dir.length() < 0.001: pole_dir = Vector3.UP - dir * dir.y
	pole_dir = pole_dir.normalized()
	var cos_a := clampf((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0)
	var mid_new := root_g.origin + (dir * cos_a + pole_dir * sqrt(1.0 - cos_a * cos_a)) * a
	var from1 := (mid_g.origin - root_g.origin).normalized()
	var to1 := (mid_new - root_g.origin).normalized()
	if from1.dot(to1) < 0.999999:
		set_bone_global_basis(root, Basis(Quaternion(from1, to1)) * root_g.basis)
	var root2 := gpose(root)
	var mid2 := root2 * skeleton.get_bone_pose(mid)
	var end2 := mid2 * skeleton.get_bone_pose(end)
	var from2 := (end2.origin - mid2.origin).normalized()
	var to2 := (root_g.origin + dir * d - mid2.origin).normalized()
	if from2.dot(to2) < 0.999999:
		set_bone_global_basis(mid, Basis(Quaternion(from2, to2)) * mid2.basis)
	set_bone_global_basis(end, end_basis)
	# The effector point where it ended up (palm centre / ball of the foot), skeleton space.
	return gpose(end) * tip_local
