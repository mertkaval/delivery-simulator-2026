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

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var stage: String = args[0] if args.size() > 0 else "build"
	if stage == "configure":
		configure(GLB, "Armature/Skeleton3D")
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

func configure(scene: String, skeleton_path: String) -> void:
	var cfg := ConfigFile.new()
	if cfg.load(scene + ".import") != OK:
		push_error("missing " + scene + ".import (run --import first)")
		return
	var sub: Dictionary = cfg.get_value("params", "_subresources", {})
	var nodes: Dictionary = sub.get("nodes", {})
	nodes["PATH:" + skeleton_path] = {
		"retarget/bone_map": load(PEOPLE_MAP),
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
		var src_name: String = ALIASES.get(str(clip_name), str(clip_name))
		var meta: Dictionary = (bclips.get(src_name, {}) as Dictionary).duplicate()
		var entry: Dictionary = {"length": snappedf(clip.length, 0.0001), "loop": clip.loop_mode != Animation.LOOP_NONE,
			"kind": meta.get("kind", ""), "source": src_name}
		for key: String in ["note", "root_yaw_deg", "root_yaw_curve", "root_yaw_samples_30fps", "crank_deg_per_s",
				"hips_bike_space_godot", "knee_flexion_min_deg", "knee_flexion_max_deg"]:
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
