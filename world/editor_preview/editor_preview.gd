@tool
extends Node3D
## Shows the baked city (tools/bake_editor_preview.gd) in the Godot editor so the whole
## environment is visible while editing. The preview is added as an unsaved child, so it never
## ends up in app_root.tscn, and in the running game this node removes itself immediately -
## the game builds the live world from code as before. The City Preview Sync plugin rebakes
## the preview when the world changes and calls reload() so the editor stays up to date.

const PREVIEW := "res://world/editor_preview/city_preview.scn"
var _shown: Node
var _loading := false

func _ready() -> void:
	set_process(false)
	if not Engine.is_editor_hint():
		queue_free()
		return
	reload()

## (Re)load the baked city from disk, replacing what is shown. The 70 MB scene loads on a
## background thread (a plain load held the editor for 1-3 s); the old preview stays up until then.
func reload() -> void:
	if not ResourceLoader.exists(PREVIEW):
		push_warning("City preview not baked yet: Project > Tools > Rebake city preview")
		return
	if _loading: return
	if ResourceLoader.load_threaded_request(PREVIEW, "", true, ResourceLoader.CACHE_MODE_REPLACE) != OK: return
	_loading = true
	set_process(true)

func _process(_delta: float) -> void:
	var status := ResourceLoader.load_threaded_get_status(PREVIEW)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
	_loading = false
	set_process(false)
	if status != ResourceLoader.THREAD_LOAD_LOADED: return
	var scene := ResourceLoader.load_threaded_get(PREVIEW) as PackedScene
	if scene == null: return
	if is_instance_valid(_shown): _shown.queue_free()
	_shown = scene.instantiate()
	add_child(_shown)   # no owner: shown in the editor, never saved into the scene
