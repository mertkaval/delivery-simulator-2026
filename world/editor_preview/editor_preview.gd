@tool
extends Node3D
## Shows the game's city in the Godot editor so the whole environment is visible while editing:
## Port Halden (the generated city: its chunk GLBs with the merged far LOD and the outskirts, and its
## Mert Road Studio streets: street chunks, street assets and street trees as plain MultiMeshes) when
## it is the chosen city, else the baked classic city (tools/bake_editor_preview.gd). The preview
## is added as an unsaved child, so it never ends up in app_root.tscn, and in the running game
## this node removes itself immediately - the game builds the live world from code as before. The
## City Preview Sync plugin rebakes the classic preview when it changes and calls reload().

const PREVIEW := "res://world/editor_preview/city_preview.scn"
var _shown: Node
var _loading: PackedStringArray = []

func _ready() -> void:
	set_process(false)
	if not Engine.is_editor_hint():
		queue_free()
		return
	reload()

## The scenes that make up the city shown in the editor.
func _sources() -> PackedStringArray:
	var out := PackedStringArray()
	if CedarNeighborhood.chosen_city() == "port_halden":
		var dir := CityForgeWorld.DIR
		out.append(dir + "outskirts.glb")
		for ci in 8:
			for cj in 8:
				var path := dir + "chunks/c_%d_%d.glb" % [ci, cj]
				if ResourceLoader.exists(path): out.append(path)
		# the streets (assets/cityforge/mrs): drawn street chunks (not the collision ones) and the street-asset kit
		var md := MrsCityStreets.DIR
		if FileAccess.file_exists(md + "mrs_city.json"):
			for ci in 8:
				for cj in 8:
					var path := md + "chunks/c_%d_%d.glb" % [ci, cj]
					if ResourceLoader.exists(path): out.append(path)
			if ResourceLoader.exists(md + "mrs_kit.glb"): out.append(md + "mrs_kit.glb")
		return out
	if ResourceLoader.exists(PREVIEW): out.append(PREVIEW)
	else: push_warning("City preview not baked yet: Project > Tools > Rebake city preview")
	return out

## (Re)load the city from disk, replacing what is shown. Scenes load on background threads (a
## plain load held the editor for 1-3 s); the old preview stays up until they are all in.
func reload() -> void:
	if not _loading.is_empty(): return
	for path in _sources():
		if ResourceLoader.load_threaded_request(path, "", true, ResourceLoader.CACHE_MODE_REPLACE) == OK:
			_loading.append(path)
	if not _loading.is_empty(): set_process(true)

func _process(_delta: float) -> void:
	for path in _loading:
		if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
	set_process(false)
	var root := Node3D.new()
	root.name = "CityPreview"
	for path in _loading:
		var scene := ResourceLoader.load_threaded_get(path) as PackedScene
		if scene == null: continue
		var node := scene.instantiate()
		if path.begins_with(MrsCityStreets.DIR):
			_add_streets(root, node, path)
			continue
		root.add_child(node)
		if path.begins_with(CityForgeWorld.DIR):
			for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
				CityForgeMaterials.apply(mi.mesh)
				if str(mi.name).begins_with("Sea"): mi.position.y = -0.06
	if root.has_node("MrsStreetAssets"): MrsCityStreets.editor_trees(root.get_node("MrsStreetAssets") as Node3D)
	_loading = PackedStringArray()
	if is_instance_valid(_shown): _shown.queue_free()
	_shown = root
	add_child(_shown)   # no owner: shown in the editor, never saved into the scene

## A Mert Road Studio file of the preview: a street chunk (road materials from mrs_materials.glb) or the kit
## (its models become MultiMeshes of every placed street asset; the kit scene itself is not shown).
func _add_streets(root: Node3D, node: Node, path: String) -> void:
	if path.ends_with("mrs_kit.glb"):
		var holder := Node3D.new()
		holder.name = "MrsStreetAssets"
		root.add_child(holder)
		MrsCityStreets.editor_props(node, holder)
		node.free()
		return
	MrsCityStreets.load_materials()
	for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		MrsCityStreets.remap_materials(mi.mesh)
	root.add_child(node)
