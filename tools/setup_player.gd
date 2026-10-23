extends SceneTree
## Godot side of the player courier (tools/prepare_player.py builds assets/player/courier.glb).
##
##   Godot_console.exe --headless --path . --script res://tools/setup_player.gd -- configure
##   Godot_console.exe --headless --path . --import
##   Godot_console.exe --headless --path . --script res://tools/setup_player.gd -- build
##
## configure: humanoid retargeting in courier.glb.import (SkeletonProfileHumanoid BoneMap, bone
##   renamer -> unique %GeneralSkeleton, rest fixer like the townspeople: tools/setup_retarget.gd),
##   so the courier's own clips and every UAL library clip drive "%GeneralSkeleton:<ProfileBone>".
##   Also the Avaturn customer (assets/player/customer_avaturn.glb) and the clothed pedestrian
##   (assets/sketchup/people/clothed_man.glb) when they exist.
## build: assets/player/courier_anims.res (AnimationLibrary, embedded copies of the clips, plus
##   the aliases Jog = the supplied Mixamo jog, Run, Sprint), assets/player/courier.tscn
##   (Courier root facing -Z, Model = courier.glb turned round, AnimationPlayer with the library),
##   and assets/player/clips.json: per clip length / loop / kind, the ground speed (m/s at
##   speed_scale 1) measured here on the retargeted skeleton, and the Blender metadata.
##   Backpack (tools/courier_bag.py): the strap meshes BackpackStrapL / R in courier.glb are hidden
##   in courier.tscn; backpack_worn.tscn / backpack_plain_worn.tscn (for a BoneAttachment3D on
##   UpperChest, transform measured here on the retargeted skeleton) and backpack_held.tscn (the
##   open bag driven by the clips' bag_track) are written, and clips.json gets a "backpack" block.

const GLB := "res://assets/player/courier.glb"
const PEOPLE_MAP := "res://assets/sketchup/people/humanoid_bone_map.tres"
const LIB := "res://assets/player/courier_anims.res"
const TSCN := "res://assets/player/courier.tscn"
const BLENDER_JSON := "res://assets/player/clips_blender.json"
const JSON_OUT := "res://assets/player/clips.json"
const CUSTOMER := "res://assets/player/customer_avaturn.glb"
## The rigged clothed pedestrian (tools/prepare_player.py -- clothed), a LivingAssets body.
const CLOTHED := "res://assets/sketchup/people/clothed_man.glb"
## Library name -> clip name in courier.glb.
const ALIASES := {"Jog": "Jog_Mixamo"}
const HIDE := ["Jog_Mixamo"]
const STRAPS := ["BackpackStrapL", "BackpackStrapR"]
const WORN_TSCN := "res://assets/player/backpack_worn.tscn"
const WORN_PLAIN_TSCN := "res://assets/player/backpack_plain_worn.tscn"
const HELD_TSCN := "res://assets/player/backpack_held.tscn"
const BAG_GLB := "res://assets/delivery/delivery_bag.glb"
const BAG_OPEN_GLB := "res://assets/delivery/delivery_bag_open.glb"
const PLAIN_GLB := "res://assets/player/backpack_plain_worn.glb"
## Clip metadata copied from clips_blender.json into clips.json.
const META_KEYS := ["note", "root_yaw_deg", "root_yaw_curve", "root_yaw_samples_30fps", "crank_deg_per_s",
	"hips_bike_space_godot", "knee_flexion_min_deg", "knee_flexion_max_deg", "bag_track", "flap_deg", "bag_model",
	"package_track", "package_box", "events", "package_release_frame", "package_grab_frame", "bag_socket", "bag_variant_of"]

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var stage: String = args[0] if args.size() > 0 else "build"
	if stage == "configure":
		configure(GLB, courier_skeleton_path(), courier_bone_map())
		if FileAccess.file_exists(CUSTOMER + ".import"): configure(CUSTOMER, "Armature/Skeleton3D")
		if FileAccess.file_exists(CLOTHED + ".import"): configure(CLOTHED, "Armature/Skeleton3D")
		quit()
	else:
		build()
		pending = true

var pending := false

## Measuring needs the courier in the tree (AnimationPlayer applies poses only there).
func _process(_delta: float) -> bool:
	if pending:
		pending = false
		measure()
		return true
	return false

## The courier's own BoneMap when its Blender manifest names the rig's bones (the MPFB v3 courier:
## "bone_map_profile_to_mpfb"), saved next to the model; else the townspeople's map.
const COURIER_MAP := "res://assets/player/courier_bone_map.tres"
func courier_bone_map() -> String:
	if not FileAccess.file_exists(BLENDER_JSON): return PEOPLE_MAP
	var meta: Variant = JSON.parse_string(FileAccess.get_file_as_string(BLENDER_JSON))
	if not (meta is Dictionary and (meta as Dictionary).get("bone_map_profile_to_mpfb", null) is Dictionary): return PEOPLE_MAP
	var names: Dictionary = (meta as Dictionary)["bone_map_profile_to_mpfb"]
	var bm := BoneMap.new()
	bm.profile = SkeletonProfileHumanoid.new()
	for profile_bone: String in names: bm.set_skeleton_bone_name(StringName(profile_bone), StringName(str(names[profile_bone])))
	print("bone map ", COURIER_MAP, " ", ResourceSaver.save(bm, COURIER_MAP), " (", names.size(), " bones)")
	return COURIER_MAP

## Path of the courier's Skeleton3D inside the imported scene (run after a plain --import).
func courier_skeleton_path() -> String:
	if not ResourceLoader.exists(GLB): return "Armature/Skeleton3D"
	var scene: Node = (load(GLB) as PackedScene).instantiate()
	var skel := scene.find_children("*", "Skeleton3D", true, false)
	var path := str(scene.get_path_to(skel[0])) if not skel.is_empty() else "Armature/Skeleton3D"
	scene.free()
	return path

func configure(scene: String, skeleton_path: String, bone_map: String = PEOPLE_MAP) -> void:
	var cfg := ConfigFile.new()
	if cfg.load(scene + ".import") != OK:
		push_error("missing " + scene + ".import (run --import first)")
		return
	var sub: Dictionary = cfg.get_value("params", "_subresources", {})
	var nodes: Dictionary = {}                     # only this skeleton (a previous model's path is stale)
	for key: String in (sub.get("nodes", {}) as Dictionary):
		if not key.ends_with("Skeleton3D"): nodes[key] = (sub["nodes"] as Dictionary)[key]
	print(scene, " skeleton ", skeleton_path, " map ", bone_map)
	nodes["PATH:" + skeleton_path] = {
		"retarget/bone_map": load(bone_map),
		"retarget/bone_renamer/rename_bones": true,
		"retarget/bone_renamer/unique_node/make_unique": true,
		"retarget/bone_renamer/unique_node/skeleton_name": "GeneralSkeleton",
		"retarget/rest_fixer/apply_node_transforms": true,
		"retarget/rest_fixer/normalize_position_tracks": true,
		"retarget/rest_fixer/overwrite_axis": true,
		"retarget/rest_fixer/reset_all_bone_poses_after_import": true,
		"retarget/rest_fixer/fix_silhouette/enable": false,
		"retarget/remove_tracks/except_bone_transform": false,
		"retarget/remove_tracks/unimportant_positions": false,
		"retarget/remove_tracks/unmapped_bones": false,
	}
	sub["nodes"] = nodes
	cfg.set_value("params", "_subresources", sub)
	cfg.set_value("params", "animation/fps", 30)
	cfg.set_value("params", "animation/remove_immutable_tracks", true)
	print(scene, " configured: ", cfg.save(scene + ".import"))

func build() -> void:
	var source: Node = (load(GLB) as PackedScene).instantiate()
	var player := source.get_node("AnimationPlayer") as AnimationPlayer
	var clips := player.get_animation_library("")
	var lib := AnimationLibrary.new()
	for clip_name: StringName in clips.get_animation_list():
		if str(clip_name) in HIDE: continue
		lib.add_animation(clip_name, clips.get_animation(clip_name).duplicate(true) as Animation)
	for alias: String in ALIASES:
		if clips.has_animation(ALIASES[alias]):          # the Mixamo courier only; v3 has its own Jog
			lib.add_animation(alias, clips.get_animation(ALIASES[alias]).duplicate(true) as Animation)
	var track := lib.get_animation("Idle").track_get_path(0)
	print("first track path: ", track)
	source.free()
	print("library save ", ResourceSaver.save(lib, LIB), " clips ", lib.get_animation_list())
	# The player scene: root faces -Z like every game actor; the model is turned round because
	# humanoid retargeting wants characters facing +Z.
	var root := Node3D.new()
	root.name = "Courier"
	var model: Node3D = (load(GLB) as PackedScene).instantiate()
	model.name = "Model"
	model.rotation.y = PI
	root.add_child(model)
	model.owner = root
	# The backpack's body-fitted straps ship hidden; the game shows them with the worn bag.
	root.set_editable_instance(model, true)
	for strap_name: String in STRAPS:
		var strap := model.find_child(strap_name, true, false) as Node3D
		if strap != null: strap.visible = false
	var animator := AnimationPlayer.new()
	animator.name = "AnimationPlayer"
	root.add_child(animator)
	animator.owner = root
	animator.root_node = NodePath("../Model")
	animator.add_animation_library("", load(LIB) as AnimationLibrary)
	animator.autoplay = "Idle"
	var packed := PackedScene.new()
	print("pack ", packed.pack(root), " save ", ResourceSaver.save(packed, TSCN))
	root.free()

## Ground speed of each looping clip on the courier as the game plays it: the planted foot (the
## lower of the Foot / Toes joints within 4 cm of the lowest one) moves backwards at the speed the
## root must move for the feet not to slide. Sampled at 240 Hz; stance segments are line-fitted.
func measure() -> void:
	var scene: Node3D = (load(TSCN) as PackedScene).instantiate()
	get_root().add_child(scene)
	var animator := scene.get_node("AnimationPlayer") as AnimationPlayer
	var skeleton := scene.find_child("GeneralSkeleton", true, false) as Skeleton3D
	var info: Dictionary = {}
	var blender: Dictionary = {}
	if FileAccess.file_exists(BLENDER_JSON):
		blender = JSON.parse_string(FileAccess.get_file_as_string(BLENDER_JSON))
	var bclips: Dictionary = blender.get("clips", {})
	var out_clips: Dictionary = {}
	for clip_name: StringName in animator.get_animation_list():
		var clip := animator.get_animation(clip_name)
		var src_name: String = str(clip_name) if bclips.has(str(clip_name)) else ALIASES.get(str(clip_name), str(clip_name))
		var meta: Dictionary = (bclips.get(src_name, {}) as Dictionary).duplicate()
		var entry: Dictionary = {"length": snappedf(clip.length, 0.0001), "loop": clip.loop_mode != Animation.LOOP_NONE,
			"kind": meta.get("kind", ""), "source": src_name}
		for key: String in META_KEYS:
			if meta.has(key): entry[key] = meta[key]
		if meta.get("kind", "") == "locomotion":
			# axis: direction the planted foot moves in Courier space (+Z = backwards for forward motion)
			var ax: Array = meta.get("axis", [0, 1, 0])
			var axis := Vector3(-float(ax[0]), float(ax[2]), float(ax[1]))  # Blender model space -> Courier (model turned round)
			entry["move_direction"] = [-axis.x, -axis.y, -axis.z]
			var g := godot_speed(animator, skeleton, scene, str(clip_name), axis)
			# speed: Blender sole-contact measure (heel / ball / toe-tip points of the shoe mesh); the
			# supplied jog uses its own removed root motion. speed_godot_joints: the same clip sampled
			# here on the retargeted skeleton from the ankle / toe joints (a cross-check, ~5 % low).
			entry["speed"] = meta.get("speed", 0.0)
			if meta.has("root_motion_removed_m"):
				entry["speed"] = snappedf(float(meta["root_motion_removed_m"]) / clip.length, 0.001)
			entry["speed_godot_joints"] = g.x
			entry["foot_slide_m"] = meta.get("slide_m", 0.0)
		out_clips[str(clip_name)] = entry
		print("CLIP ", clip_name, " ", entry)
	info["scene"] = TSCN
	info["model"] = GLB
	info["library"] = LIB
	info["skeleton_path"] = "Model/Armature/GeneralSkeleton (unique name %GeneralSkeleton in Model)"
	info["animation_player"] = "AnimationPlayer (root_node ../Model)"
	info["facing"] = "Courier root faces -Z; the model inside is turned PI (retarget convention +Z)"
	info["height_m"] = blender.get("height_m", 0.0)
	info["triangles"] = blender.get("triangles", 0)
	info["bike"] = blender.get("bike", {})
	info["clips"] = out_clips
	if blender.has("backpack"):
		info["backpack"] = build_backpack(scene, animator, skeleton, blender["backpack"], out_clips)
	var f := FileAccess.open(JSON_OUT, FileAccess.WRITE)
	f.store_string(JSON.stringify(info, "  "))
	f.close()
	print("wrote ", JSON_OUT)
	scene.free()

func godot_speed(animator: AnimationPlayer, skeleton: Skeleton3D, scene: Node3D, clip_name: String, axis: Vector3) -> Vector2:
	var clip := animator.get_animation(clip_name)
	animator.play(clip_name)
	var dt := 1.0 / 240.0
	var steps := int(round(clip.length / dt))
	var series: Dictionary = {"Left": [], "Right": []}
	# skeleton -> Courier root transform (the scene is not in the tree while the script initialises)
	var chain := Transform3D.IDENTITY
	var node: Node = skeleton
	while node != scene and node != null:
		if node is Node3D: chain = (node as Node3D).transform * chain
		node = node.get_parent()
	for i in range(steps):
		animator.seek(i * dt, true)
		for side: String in ["Left", "Right"]:
			var foot := chain * skeleton.get_bone_global_pose(skeleton.find_bone(side + "Foot")).origin
			var toes := chain * skeleton.get_bone_global_pose(skeleton.find_bone(side + "Toes")).origin
			(series[side] as Array).append([foot, toes])
	var lowest := 1e9
	for side: String in ["Left", "Right"]:
		for p: Array in series[side]: lowest = minf(lowest, minf((p[0] as Vector3).y, (p[1] as Vector3).y))
	var slopes: Array[float] = []
	var weights: Array[float] = []
	var slide := 0.0
	for side: String in ["Left", "Right"]:
		var s: Array = series[side]
		var n := s.size()
		var down: Array[bool] = []
		for p: Array in s: down.append(minf((p[0] as Vector3).y, (p[1] as Vector3).y) < lowest + 0.04)
		var start := down.find(false)
		if start < 0: continue
		var i := 0
		while i < n:
			if not down[(start + i) % n]:
				i += 1
				continue
			var run: Array[int] = []
			while i < n and down[(start + i) % n]:
				run.append((start + i) % n)
				i += 1
			if run.size() < 6: continue
			var mid: Array = s[run[run.size() / 2]]
			var use_toes: bool = (mid[1] as Vector3).y < (mid[0] as Vector3).y
			var ts: Array[float] = []
			var ys: Array[float] = []
			for j in range(run.size()):
				var p: Vector3 = (s[run[j]] as Array)[1 if use_toes else 0]
				ts.append(j * dt)
				ys.append(p.dot(axis))
			var fit := line_fit(ts, ys)
			slopes.append(fit.x)
			weights.append(float(run.size()))
			for j in range(ts.size()): slide = maxf(slide, absf(ys[j] - (fit.x * ts[j] + fit.y)))
	if slopes.is_empty(): return Vector2.ZERO
	var total := 0.0
	var wsum := 0.0
	for k in range(slopes.size()):
		total += slopes[k] * weights[k]
		wsum += weights[k]
	return Vector2(snappedf(total / wsum, 0.001), snappedf(slide, 0.001))

func line_fit(xs: Array[float], ys: Array[float]) -> Vector2:
	var n := float(xs.size())
	var sx := 0.0
	var sy := 0.0
	var sxx := 0.0
	var sxy := 0.0
	for i in range(xs.size()):
		sx += xs[i]
		sy += ys[i]
		sxx += xs[i] * xs[i]
		sxy += xs[i] * ys[i]
	var den := n * sxx - sx * sx
	if absf(den) < 1e-12: return Vector2(0, sy / n)
	var m := (n * sxy - sx * sy) / den
	return Vector2(m, (sy - m * sx) / n)

# --- backpack ----------------------------------------------------------------------------------

## [px, py, pz, qx, qy, qz, qw] (Courier-root space, from tools/courier_bag.py) -> Transform3D.
static func track_xf(a: Array) -> Transform3D:
	return Transform3D(Basis(Quaternion(float(a[3]), float(a[4]), float(a[5]), float(a[6]))),
		Vector3(float(a[0]), float(a[1]), float(a[2])))

static func xf_list(t: Transform3D) -> Array:
	var q := t.basis.get_rotation_quaternion()
	return [snappedf(t.origin.x, 0.0001), snappedf(t.origin.y, 0.0001), snappedf(t.origin.z, 0.0001),
		snappedf(q.x, 0.00001), snappedf(q.y, 0.00001), snappedf(q.z, 0.00001), snappedf(q.w, 0.00001)]

## Skeleton space -> Courier root.
func skeleton_chain(skeleton: Skeleton3D, scene: Node3D) -> Transform3D:
	var chain := Transform3D.IDENTITY
	var node: Node = skeleton
	while node != scene and node != null:
		if node is Node3D: chain = (node as Node3D).transform * chain
		node = node.get_parent()
	return chain

func bone_in_root(animator: AnimationPlayer, skeleton: Skeleton3D, scene: Node3D, clip: String, frame: int, bone: String) -> Transform3D:
	animator.play(clip)
	animator.seek(frame / 30.0, true)
	return skeleton_chain(skeleton, scene) * skeleton.get_bone_global_pose(skeleton.find_bone(bone))

## The worn scenes (child of a BoneAttachment3D on UpperChest), the held scene, and the contract.
func build_backpack(scene: Node3D, animator: AnimationPlayer, skeleton: Skeleton3D, bp: Dictionary, clips: Dictionary) -> Dictionary:
	var bone := str(bp.get("bone", "UpperChest"))
	if bone.contains("("): bone = bone.get_slice("(", 1).get_slice(")", 0)   # "spine_03 (UpperChest)" -> the retargeted name
	bp["bone"] = bone
	var at := bone_in_root(animator, skeleton, scene, "Idle", 0, bone)
	var local := at.affine_inverse() * track_xf(bp["worn_idle_frame0_courier_root"])
	var local_plain := at.affine_inverse() * track_xf(bp["worn_plain_idle_frame0_courier_root"])
	# Cross-check: the worn frames of Bag_TakeOff's bag_track against bone pose * local.
	var worst := 0.0
	var take_off: Dictionary = clips.get("Bag_TakeOff", {})
	if take_off.has("bag_track"):
		var track: Array = take_off["bag_track"]
		for frame: int in [0, 6, 13]:
			var bone_xf := bone_in_root(animator, skeleton, scene, "Bag_TakeOff", frame, bone)
			worst = maxf(worst, ((bone_xf * local).origin - track_xf(track[frame]).origin).length())
	print("backpack: worn local ", local, " check vs bag_track ", snappedf(worst * 1000.0, 0.1), " mm")
	save_bag_scene(WORN_TSCN, "BackpackWorn", BAG_GLB, local, ["StrapL", "StrapR"])
	if ResourceLoader.exists(PLAIN_GLB): save_bag_scene(WORN_PLAIN_TSCN, "BackpackPlainWorn", PLAIN_GLB, local_plain, [])
	save_bag_scene(HELD_TSCN, "BackpackHeld", BAG_OPEN_GLB, Transform3D.IDENTITY, ["FlapStraps"])
	var held: Node3D = (load(HELD_TSCN) as PackedScene).instantiate()
	var paths: Dictionary = {}
	for n: String in ["Flap", "StrapL", "StrapR", "FlapStraps", "Slot_Top"]:
		var node := held.find_child(n, true, false)
		if node != null: paths[n] = str(held.get_path_to(node))
	held.free()
	var strap_paths: Dictionary = {}
	for n: String in STRAPS:
		var node := scene.find_child(n, true, false)
		if node != null: strap_paths[n] = str(scene.get_path_to(node))
	var out := bp.duplicate(true)
	out.merge({
		"worn_scene": WORN_TSCN, "worn_plain_scene": WORN_PLAIN_TSCN, "held_scene": HELD_TSCN,
		"attach": "BoneAttachment3D under %GeneralSkeleton with bone_name '" + bone + "'; instance worn_scene (or worn_plain_scene) as its child with an identity transform (the bag sits at Bag.transform = attach_local inside the scene)",
		"attach_local": xf_list(local), "attach_local_plain": xf_list(local_plain),
		"attach_check_mm": snappedf(worst * 1000.0, 0.1),
		"strap_nodes": strap_paths,
		"held_nodes": paths,
		"track_format": "bag_track / package_track: one entry per frame at 30 fps (frame = clip time * 30, frames 0..N), [px, py, pz, qx, qy, qz, qw] = transform of the bag / package scene root in Courier-root space (the node that holds the AnimationPlayer root; Courier faces -Z): node.transform = Transform3D(Basis(Quaternion(qx, qy, qz, qw)), Vector3(px, py, pz)) for a child of that node. Interpolate between frames. flap_deg: held bag Flap.rotation.x in degrees (0 closed, 180 hanging open). events [{frame, do, ...}]: bag_socket -> back (worn scene on the bone, held bag hidden) / track (held bag driven by bag_track, worn scene hidden); body_strap_l / body_strap_r = visible of BackpackStrapL / R in the courier; bag_strap_l / bag_strap_r = visible of StrapL / StrapR of the held bag; package -> track (follow package_track) / bag (parent into the top compartment, Slot_Top) / released (customer takes it, or it stays where package_track ends).",
	}, true)
	return out

func save_bag_scene(path: String, root_name: String, glb: String, local: Transform3D, hidden: Array[String]) -> void:
	if not ResourceLoader.exists(glb):
		push_error("missing " + glb)
		return
	var root := Node3D.new()
	root.name = root_name
	var bag: Node3D = (load(glb) as PackedScene).instantiate()
	bag.name = "Bag"
	root.add_child(bag)
	bag.owner = root
	bag.transform = local
	root.set_editable_instance(bag, true)
	for n: String in hidden:
		var node := bag.find_child(n, true, false) as Node3D
		if node != null: node.visible = false
	var packed := PackedScene.new()
	print("backpack: ", path, " pack ", packed.pack(root), " save ", ResourceSaver.save(packed, path))
	root.free()
