extends SceneTree
## Godot side of the townspeople (tools/npc/: build_npc.py -> export_all.sh -> assets/people/*.glb
## + people.json). Every NPC shares the MPFB game_engine rig of the v3 courier, so they all use
## the courier's BoneMap (assets/player/courier_bone_map.tres) for humanoid retargeting: the
## courier's clips, the UAL libraries and the role clips (npc_role_clips.glb) drive any of them.
##
##   Godot_console.exe --headless --path . --import
##   Godot_console.exe --headless --path . --script res://tools/setup_people.gd
##   Godot_console.exe --headless --path . --import          (again: applies the retargeting)
const MANIFEST := "res://assets/people/people.json"
const BONE_MAP := "res://assets/player/courier_bone_map.tres"

func _initialize() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
	var done := 0
	for p: Dictionary in data.people:
		if configure(str(p.scene), "%s/Skeleton3D" % p.name): done += 1
	if configure(str(data.clips), "Courier/Skeleton3D"): done += 1
	print("SETUP PEOPLE configured %d imports, %d textures set to VRAM compression" % [done, compress_textures("res://assets/people")])
	quit()

func configure(scene: String, skeleton_path: String) -> bool:
	var cfg := ConfigFile.new()
	if cfg.load(scene + ".import") != OK:
		push_error("missing " + scene + ".import (run --import first)")
		return false
	var sub: Dictionary = cfg.get_value("params", "_subresources", {})
	var nodes: Dictionary = {}
	nodes["PATH:" + skeleton_path] = {
		"retarget/bone_map": load(BONE_MAP),
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
	cfg.set_value("params", "meshes/generate_lods", true)
	return cfg.save(scene + ".import") == OK

## Textures the scene import extracted from the GLBs default to lossless (Godot only switches them
## to VRAM compression after seeing them in 3D in the editor): slow to load, 4-8x the video
## memory. Set them to VRAM compressed with mipmaps (normal maps as RGTC) before the next import.
func compress_textures(dir: String) -> int:
	var count := 0
	for f in DirAccess.get_files_at(dir):
		if not f.ends_with(".import"): continue
		var path := dir.path_join(f)
		var cfg := ConfigFile.new()
		if cfg.load(path) != OK or cfg.get_value("remap", "importer", "") != "texture": continue
		if int(cfg.get_value("params", "compress/mode", 0)) == 2: continue
		cfg.set_value("params", "compress/mode", 2)
		cfg.set_value("params", "mipmaps/generate", true)
		cfg.set_value("params", "detect_3d/compress_to", 0)
		var normal := f.contains("_normal") or f.contains("_n_")
		cfg.set_value("params", "compress/normal_map", 1 if normal else 2)
		cfg.save(path)
		count += 1
	return count
