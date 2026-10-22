@tool
extends EditorPlugin
## City Preview Sync: keeps the city you see in the editor the same as the game.
##
## The game builds its world from code, so the editor shows a baked copy
## (world/editor_preview/city_preview.scn, made by tools/bake_editor_preview.gd). This plugin
## fingerprints the files the world is built from (scripts, scenes, models, textures, data under
## app/, actors/, systems/, world/, assets/); when the fingerprint differs from the one the last
## bake recorded, it waits until things are quiet (no changes for QUIET seconds, the game is not
## running, no import in progress), runs the bake in a background Godot process and then
## reloads the preview in the open scene. Also: Project > Tools > Rebake city preview.

const WATCH := ["res://app", "res://actors", "res://systems", "res://world", "res://assets"]
const SKIP := ["res://world/editor_preview"]
const EXTS := ["gd", "gdshader", "glb", "gltf", "tscn", "scn", "tres", "res", "json", "png", "jpg", "jpeg", "webp", "obj"]
const SIGNATURE := "res://world/editor_preview/signature.txt"
const BAKER := "res://tools/bake_editor_preview.gd"
const QUIET := 20.0          ## seconds without file changes before a rebake starts
const LOCK := "res://tmp/import.lock"

var _pid := -1
var _sig := ""
var _failed_sig := ""
var _dirty_at := 0.0         ## check once shortly after the editor opens
var _timer: Timer

func _enter_tree() -> void:
	add_tool_menu_item("Rebake city preview", func() -> void: _check(true))
	_timer = Timer.new()
	_timer.wait_time = 2.0
	_timer.timeout.connect(_tick)
	add_child(_timer)
	_timer.start()
	var fs := EditorInterface.get_resource_filesystem()
	fs.filesystem_changed.connect(_on_change)
	fs.resources_reimported.connect(func(_r: PackedStringArray) -> void: _on_change())
	resource_saved.connect(func(_r: Resource) -> void: _on_change())
	_dirty_at = _now() - QUIET + 8.0

func _exit_tree() -> void:
	remove_tool_menu_item("Rebake city preview")
	if _timer: _timer.queue_free()

func _now() -> float:
	return Time.get_ticks_msec() / 1000.0

func _on_change() -> void:
	if _pid < 0: _dirty_at = _now()

func _tick() -> void:
	if _pid >= 0:
		if OS.is_process_running(_pid): return
		_pid = -1
		var stored := _stored_sig()
		if stored == _sig:
			print("City Preview Sync: preview rebaked, reloading.")
			EditorInterface.get_resource_filesystem().update_file("res://world/editor_preview/city_preview.scn")
			_reload_previews()
		else:
			_failed_sig = _sig
			push_warning("City Preview Sync: the bake did not finish; see tools/bake_editor_preview.gd. Will retry after the next change.")
		_dirty_at = -1.0
		return
	if _dirty_at < 0.0 or _now() - _dirty_at < QUIET: return
	if EditorInterface.is_playing_scene() or FileAccess.file_exists(LOCK): return
	_dirty_at = -1.0
	_check(false)

## Rebake if the world files changed since the last bake (or always when forced).
func _check(force: bool) -> void:
	if _pid >= 0: return
	var sig := fingerprint()
	if not force and (sig == _stored_sig() or sig == _failed_sig): return
	_sig = sig
	var args := PackedStringArray(["--path", ProjectSettings.globalize_path("res://"), "--script", BAKER,
		"--resolution", "640x360", "--position", "40,40", "--", sig])
	_pid = OS.create_process(OS.get_executable_path(), args)
	if _pid < 0:
		push_warning("City Preview Sync: could not start the bake process.")
	else:
		print("City Preview Sync: world changed, rebaking the editor preview in the background (pid %d)." % _pid)

func _stored_sig() -> String:
	return FileAccess.get_file_as_string(SIGNATURE).strip_edges() if FileAccess.file_exists(SIGNATURE) else ""

## A hash of path + modification time of every file the world is built from.
func fingerprint() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	for dir: String in WATCH: _walk(dir, ctx)
	return ctx.finish().hex_encode()

func _walk(dir: String, ctx: HashingContext) -> void:
	if dir in SKIP or FileAccess.file_exists(dir.path_join(".gdignore")): return
	var d := DirAccess.open(dir)
	if d == null: return
	var files := d.get_files()
	files.sort()
	for f: String in files:
		if not f.get_extension().to_lower() in EXTS: continue
		var path := dir.path_join(f)
		ctx.update(("%s|%d\n" % [path, FileAccess.get_modified_time(path)]).to_utf8_buffer())
	var subs := d.get_directories()
	subs.sort()
	for s: String in subs:
		if not s.begins_with("."): _walk(dir.path_join(s), ctx)

func _reload_previews() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null: return
	for n in [root] + root.find_children("*", "Node3D", true, false):
		if n.has_method("reload") and n.get_script() != null and str(n.get_script().resource_path).ends_with("editor_preview.gd"):
			n.call("reload")
