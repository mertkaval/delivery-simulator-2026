extends SceneTree
## Gives the extra townspeople clips (assets/animations/ual/ual_npc.glb, authored by
## tools/build_npc_clips.py on the library rig) the library's humanoid retarget settings, so
## their tracks read "%GeneralSkeleton:<ProfileBone>" like ual_standard.glb (tools/setup_retarget.gd).
##
##   Godot_console.exe --headless --path . --import            (creates the .import file)
##   Godot_console.exe --headless --path . --script res://tools/setup_npc_clips.gd
##   Godot_console.exe --headless --path . --import            (re-imports with the bone map)

const CLIPS := "res://assets/animations/ual/ual_npc.glb"
const UAL := "res://assets/animations/ual/ual_standard.glb"

func _initialize() -> void:
	var source := ConfigFile.new()
	var target := ConfigFile.new()
	if source.load(UAL + ".import") != OK or target.load(CLIPS + ".import") != OK:
		push_error("run --import first")
		quit(1)
		return
	# Same skeleton path (Rig/Skeleton3D), bone map and rest fixer as the library.
	target.set_value("params", "_subresources", source.get_value("params", "_subresources", {}))
	for key in ["animation/fps", "animation/remove_immutable_tracks", "nodes/import_as_skeleton_bones"]:
		target.set_value("params", key, source.get_value("params", key))
	print(CLIPS, " configured: ", target.save(CLIPS + ".import"))
	quit()
