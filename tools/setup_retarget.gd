extends SceneTree
## Sets up Godot humanoid retargeting so the CC0 Quaternius Universal Animation Library
## (assets/animations/ual) plays on every converted character (assets/sketchup/people).
##
## Both the library rig and each character get a BoneMap to SkeletonProfileHumanoid in their
## .import settings, with the bone renamer (skeleton becomes the unique node %GeneralSkeleton,
## bones get profile names) and the rest fixer (overwrite axis + fix silhouette, so T- and
## A-pose rigs share one rest). After a reimport, any library clip's tracks read
## "%GeneralSkeleton:<ProfileBone>" and play on any character.
##
##   Godot_console.exe --headless --path . --script res://tools/setup_retarget.gd
##   Godot_console.exe --headless --path . --import

const UAL := "res://assets/animations/ual/ual_standard.glb"
const UAL_MAP := "res://assets/animations/ual/ual_bone_map.tres"
const PEOPLE_MAP := "res://assets/sketchup/people/humanoid_bone_map.tres"
const PEOPLE := ["casual_male_tshirt", "business_man_eric", "sophia", "casual_female", "casual_male_2"]

## Quaternius (Rigify DEF-) bone names for each humanoid profile bone.
const UAL_BONES := {
	"Root": "root", "Hips": "DEF-hips", "Spine": "DEF-spine.001", "Chest": "DEF-spine.002",
	"UpperChest": "DEF-spine.003", "Neck": "DEF-neck", "Head": "DEF-head",
	"LeftUpperLeg": "DEF-thigh.L", "LeftLowerLeg": "DEF-shin.L", "LeftFoot": "DEF-foot.L", "LeftToes": "DEF-toe.L",
	"RightUpperLeg": "DEF-thigh.R", "RightLowerLeg": "DEF-shin.R", "RightFoot": "DEF-foot.R", "RightToes": "DEF-toe.R",
}

func _initialize() -> void:
	var profile := SkeletonProfileHumanoid.new()
	var ual := BoneMap.new()
	ual.profile = profile
	for key in UAL_BONES: ual.set_skeleton_bone_name(key, UAL_BONES[key])
	for side in ["Left", "Right"]:
		var s := "L" if side == "Left" else "R"
		ual.set_skeleton_bone_name(side + "Shoulder", "DEF-shoulder." + s)
		ual.set_skeleton_bone_name(side + "UpperArm", "DEF-upper_arm." + s)
		ual.set_skeleton_bone_name(side + "LowerArm", "DEF-forearm." + s)
		ual.set_skeleton_bone_name(side + "Hand", "DEF-hand." + s)
		for f in [["Thumb", "thumb", ["Metacarpal", "Proximal", "Distal"]], ["Index", "f_index", ["Proximal", "Intermediate", "Distal"]],
				["Middle", "f_middle", ["Proximal", "Intermediate", "Distal"]], ["Ring", "f_ring", ["Proximal", "Intermediate", "Distal"]],
				["Little", "f_pinky", ["Proximal", "Intermediate", "Distal"]]]:
			for k in range(3):
				ual.set_skeleton_bone_name("%s%s%s" % [side, f[0], f[2][k]], "DEF-%s.0%d.%s" % [f[1], k + 1, s])
	print("UAL map save ", ResourceSaver.save(ual, UAL_MAP))
	# The converted characters already use the profile's own bone names.
	var people := BoneMap.new()
	people.profile = SkeletonProfileHumanoid.new()
	for b in range(profile.bone_size):
		var n := profile.get_bone_name(b)
		people.set_skeleton_bone_name(n, n)
	print("People map save ", ResourceSaver.save(people, PEOPLE_MAP))
	configure(UAL, "Rig/Skeleton3D", UAL_MAP, true)
	for id in PEOPLE: configure("res://assets/sketchup/people/%s.glb" % id, "Armature/Skeleton3D", PEOPLE_MAP, false)
	quit()

func configure(scene: String, skeleton_path: String, map_path: String, library: bool) -> void:
	var cfg := ConfigFile.new()
	var path := scene + ".import"
	if cfg.load(path) != OK:
		push_error("missing " + path)
		return
	var sub: Dictionary = cfg.get_value("params", "_subresources", {})
	var nodes: Dictionary = sub.get("nodes", {})
	nodes["PATH:" + skeleton_path] = {
		"retarget/bone_map": load(map_path),
		"retarget/bone_renamer/rename_bones": true,
		"retarget/bone_renamer/unique_node/make_unique": true,
		"retarget/bone_renamer/unique_node/skeleton_name": "GeneralSkeleton",
		"retarget/rest_fixer/apply_node_transforms": true,
		"retarget/rest_fixer/normalize_position_tracks": true,
		"retarget/rest_fixer/overwrite_axis": true,
		"retarget/rest_fixer/reset_all_bone_poses_after_import": true,
		"retarget/rest_fixer/fix_silhouette/enable": true,
		"retarget/remove_tracks/except_bone_transform": false,
		"retarget/remove_tracks/unimportant_positions": false,
		"retarget/remove_tracks/unmapped_bones": false,  # true trips a Godot import bug that drops most tracks
	}
	sub["nodes"] = nodes
	cfg.set_value("params", "_subresources", sub)
	print(scene, " configured: ", cfg.save(path))
