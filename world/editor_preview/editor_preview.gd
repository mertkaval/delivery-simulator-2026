@tool
extends Node3D
## Shows the baked city (tools/bake_editor_preview.gd) in the Godot editor so the whole
## environment is visible while editing. The preview is added as an unsaved child, so it never
## ends up in app_root.tscn, and in the running game this node removes itself immediately -
## the game builds the live world from code as before. The City Preview Sync plugin rebakes
## the preview when the world changes and calls reload() so the editor stays up to date.

const PREVIEW := "res://world/editor_preview/city_preview.scn"
var _shown: Node

func _ready() -> void:
	if not Engine.is_editor_hint():
		queue_free()
		return
	reload()

## (Re)load the baked city from disk, replacing what is shown.
func reload() -> void:
	if is_instance_valid(_shown):
		_shown.queue_free()
		_shown = null
	if not ResourceLoader.exists(PREVIEW):
		push_warning("City preview not baked yet: Project > Tools > Rebake city preview")
		return
	var scene: PackedScene = ResourceLoader.load(PREVIEW, "", ResourceLoader.CACHE_MODE_REPLACE)
	if scene == null: return
	_shown = scene.instantiate()
	add_child(_shown)   # no owner: shown in the editor, never saved into the scene
