extends SceneTree
## Bakes the procedurally built city into a static scene so it can be seen in the Godot editor.
##
## The game builds its world from code at runtime, which the editor never runs. This script
## starts the real game scene (app/app_root.tscn), lets the world build exactly as it does when
## you press Play (same start time, same builders, including the store computers and pickup
## shelves the app adds), then copies every visible piece - meshes, MultiMesh instances (houses,
## trees, grass), lights, labels, sprites, sky/environment - into a plain scene with no scripts
## or physics, and saves it as res://world/editor_preview/city_preview.scn. EditorPreview (in
## app/app_root.tscn) shows that scene inside the editor only.
##
## The copy keeps what decides how a piece looks: visibility ranges and visibility_parent chains
## (house near/far/massing LODs switch exactly like in the game, never drawn on top of each
## other), custom AABBs, per-instance shader parameters (outfit / tint colours), shadows.
##
## Normally run automatically by the City Preview Sync editor plugin (addons/city_preview_sync)
## whenever world files change. By hand (needs a window: MultiMesh data is not kept headless):
##   Godot_v4.7.2-stable_win64_console.exe --path . --script res://tools/bake_editor_preview.gd [-- <signature>]

const OUT := "res://world/editor_preview/city_preview.scn"
const SIGNATURE := "res://world/editor_preview/signature.txt"
var copied := 0
var copies: Dictionary = {}       ## source node -> copy (to re-link visibility_parent)

func _initialize() -> void: call_deferred("run")

func run() -> void:
	root.size = Vector2i(640, 360)
	var game: Node = load("res://app/app_root.tscn").instantiate()
	game.set("save_enabled", false)
	root.add_child(game)
	for i in range(5): await process_frame
	game.call("close_menu")                       # unpause, as in play: deferred builders run
	var world: Node3D = game.get("world")
	var session: DeliverySession = game.get("session")
	# Let deferred builders (furniture, traffic, people, grass, landscape) finish.
	for i in range(60): await process_frame
	world.call("set_time", session.hour())        # the game's start time (11:30)
	for i in range(5): await process_frame
	var preview := Node3D.new()
	preview.name = "CityPreview"
	copy_tree(world, preview, preview)
	relink(preview)
	var packed := PackedScene.new()
	var err := packed.pack(preview)
	if err != OK:
		push_error("pack failed: %d" % err)
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.get_base_dir()))
	err = ResourceSaver.save(packed, OUT, ResourceSaver.FLAG_COMPRESS)
	var args := OS.get_cmdline_user_args()
	if err == OK and args.size() > 0:
		var f := FileAccess.open(SIGNATURE, FileAccess.WRITE)
		if f: f.store_string(args[0])
	print("BAKED %s: %d visual nodes, error %d" % [OUT, copied, err])
	quit(0 if err == OK else 1)

## Copy the visible pieces under `node` into `dest`, flattened to global transforms.
func copy_tree(node: Node, dest: Node3D, owner_node: Node) -> void:
	for child in node.get_children():
		var visible := not (child is Node3D) or (child as Node3D).visible
		if not visible: continue
		var copy := visual_copy(child)
		if copy != null:
			copy.name = "%s_%d" % [child.name, copied]
			dest.add_child(copy)
			copy.owner = owner_node
			if copy is Node3D: (copy as Node3D).global_transform = (child as Node3D).global_transform
			copies[child] = copy
			copied += 1
		copy_tree(child, dest, owner_node)

func visual_copy(n: Node) -> Node:
	if n is MultiMeshInstance3D:
		var src := n as MultiMeshInstance3D
		if src.multimesh == null: return null
		var c := MultiMeshInstance3D.new()
		c.multimesh = src.multimesh.duplicate()
		copy_geometry(src, c)
		return c
	if n is MeshInstance3D:
		var src := n as MeshInstance3D
		if src.mesh == null: return null
		var c := MeshInstance3D.new()
		c.mesh = src.mesh
		for s in range(src.get_surface_override_material_count()):
			c.set_surface_override_material(s, src.get_surface_override_material(s))
		copy_geometry(src, c)
		return c   # skinned people keep their rest pose
	if n is Label3D:
		return (n as Label3D).duplicate(0)
	if n is SpriteBase3D:
		return (n as SpriteBase3D).duplicate(0)
	if n is Light3D:
		return (n as Light3D).duplicate(0)
	if n is WorldEnvironment:
		var c := WorldEnvironment.new()
		c.environment = (n as WorldEnvironment).environment
		c.camera_attributes = (n as WorldEnvironment).camera_attributes
		return c
	return null

func copy_geometry(src: GeometryInstance3D, c: GeometryInstance3D) -> void:
	c.material_override = src.material_override
	c.material_overlay = src.material_overlay
	c.cast_shadow = src.cast_shadow
	c.transparency = src.transparency
	c.custom_aabb = src.custom_aabb
	c.extra_cull_margin = src.extra_cull_margin
	c.visibility_range_begin = src.visibility_range_begin
	c.visibility_range_end = src.visibility_range_end
	c.visibility_range_begin_margin = src.visibility_range_begin_margin
	c.visibility_range_end_margin = src.visibility_range_end_margin
	c.visibility_range_fade_mode = src.visibility_range_fade_mode
	c.lod_bias = src.lod_bias
	c.set_meta("visibility_parent_src", src.visibility_parent)
	c.set_meta("source_node", src)
	# Per-instance shader parameters (outfit colours, tints, LED text rows...).
	for p: Dictionary in src.get_property_list():
		var name: String = p.name
		if name.begins_with("instance_shader_parameters/"):
			c.set(name, src.get(name))

## Re-create visibility_parent links between the copies (LOD chains switch as in the game).
func relink(preview: Node3D) -> void:
	for copy: Node in copies.values():
		if not copy.has_meta("source_node"): continue
		var src: GeometryInstance3D = copy.get_meta("source_node")
		var path: NodePath = copy.get_meta("visibility_parent_src")
		copy.remove_meta("source_node")
		copy.remove_meta("visibility_parent_src")
		if path.is_empty(): continue
		var target: Node = src.get_node_or_null(path)
		if target != null and copies.has(target):
			(copy as GeometryInstance3D).visibility_parent = copy.get_path_to(copies[target])
