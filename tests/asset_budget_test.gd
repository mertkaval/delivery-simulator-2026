extends SceneTree
## Asset budgets that keep the game fast (headless, a few seconds):
##   godot --headless --path . --script res://tests/asset_budget_test.gd
## - 3D textures are VRAM compressed: a texture imported Lossless (the default for textures a
##   scene import extracts; only the editor ever switches them) loads ~7x slower and takes 4-8x
##   the video memory. UI-only folders are exempt.
## - No 3D texture above 2048 px without a size limit.
## - Every townsperson is one skinned mesh with at most three surfaces (crowd export).
## - No .blend inside an imported folder (it breaks the headless import).
const UI_FOLDERS := ["/qa/", "/previews/", "/ui/", "/icons/", "/menu/"]
const MAX_TEXTURE_PX := 2048
var checks := 0
var failures := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		print("FAIL: ", label)

func _initialize() -> void:
	var lossless: Array[String] = []
	var oversized: Array[String] = []
	var blends: Array[String] = []
	walk("res://assets", lossless, oversized, blends)
	walk("res://world", lossless, oversized, blends)
	check(lossless.is_empty(), "3D textures are VRAM compressed (%d lossless: %s)" % [lossless.size(), str(lossless.slice(0, 5))])
	check(oversized.is_empty(), "no 3D texture above %d px (%d: %s)" % [MAX_TEXTURE_PX, oversized.size(), str(oversized.slice(0, 5))])
	check(blends.is_empty(), "no .blend under an imported folder (%s)" % str(blends.slice(0, 5)))
	var people := LivingAssets.load_people()
	check(people.size() >= 30, "townspeople manifest lists the designed people (%d)" % people.size())
	var heavy: Array[String] = []
	for e: Dictionary in people:
		var scene: Node = (load(str(e.scene)) as PackedScene).instantiate()
		var meshes := scene.find_children("*", "MeshInstance3D", true, false)
		var surfaces := 0
		for m: MeshInstance3D in meshes: surfaces += m.mesh.get_surface_count()
		if meshes.size() != 1 or surfaces > 3: heavy.append("%s (%d meshes, %d surfaces)" % [e.id, meshes.size(), surfaces])
		scene.free()
	check(heavy.is_empty(), "townspeople are one mesh with <= 3 surfaces (%s)" % str(heavy.slice(0, 5)))
	print("ASSET BUDGET: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)

func walk(dir: String, lossless: Array[String], oversized: Array[String], blends: Array[String]) -> void:
	if FileAccess.file_exists(dir.path_join(".gdignore")): return
	for f in DirAccess.get_files_at(dir):
		var path := dir.path_join(f)
		if f.ends_with(".blend"): blends.append(path)
		if not f.ends_with(".import"): continue
		if UI_FOLDERS.any(func(u: String) -> bool: return (path + "/").contains(u)): continue
		var cfg := ConfigFile.new()
		if cfg.load(path) != OK or cfg.get_value("remap", "importer", "") != "texture": continue
		var source := path.trim_suffix(".import")
		if int(cfg.get_value("params", "compress/mode", 0)) != 2:
			lossless.append(source)
		var limit := int(cfg.get_value("params", "process/size_limit", 0))
		if limit == 0 or limit > MAX_TEXTURE_PX:
			var image := Image.load_from_file(ProjectSettings.globalize_path(source)) if limit == 0 and _big_file(source) else null
			if image != null and maxi(image.get_width(), image.get_height()) > MAX_TEXTURE_PX: oversized.append(source)
	for d in DirAccess.get_directories_at(dir):
		walk(dir.path_join(d), lossless, oversized, blends)

## Only images large enough to possibly exceed the limit are decoded (keeps the test fast).
func _big_file(path: String) -> bool:
	var f := FileAccess.open(path, FileAccess.READ)
	return f != null and f.get_length() > 1500000
