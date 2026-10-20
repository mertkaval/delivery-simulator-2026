@tool
extends Node3D
## Shows the baked city (tools/bake_editor_preview.gd) in the Godot editor so the whole
## environment is visible while editing. The preview is added as an unsaved child, so it never
## ends up in app_root.tscn, and in the running game this node removes itself immediately -
## the game builds the live world from code as before.

const PREVIEW := "res://world/editor_preview/city_preview.scn"

func _ready() -> void:
	if not Engine.is_editor_hint():
		queue_free()
		return
	if not ResourceLoader.exists(PREVIEW):
		push_warning("City preview not baked yet. Run: Godot --path . --script res://tools/bake_editor_preview.gd")
		return
	var scene: PackedScene = load(PREVIEW)
	add_child(scene.instantiate())   # no owner: shown in the editor, never saved into the scene
