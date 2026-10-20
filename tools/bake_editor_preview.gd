extends SceneTree
## Bakes the procedurally built city into a static scene so it can be seen in the Godot editor.
##
## The game builds its world from code at runtime (CedarNeighborhood._ready), which the editor
## never runs. This script builds the real world once, then copies every visible piece -
## meshes, MultiMesh instances (houses, grass, trees), lights, labels, sky/environment - into a
## plain scene with no scripts or physics, and saves it as
## res://world/editor_preview/city_preview.scn. EditorPreview (in app/app_root.tscn) shows that
## scene inside the editor only; it is never loaded in the running game.
##
## Run after changing the world (needs a window: MultiMesh data is not kept in headless mode):
##   Godot_v4.7.2-stable_win64_console.exe --path . --script res://tools/bake_editor_preview.gd

const OUT := "res://world/editor_preview/city_preview.scn"
var copied := 0

func _initialize() -> void: call_deferred("run")

func run() -> void:
	root.size = Vector2i(640, 360)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14.0)
	# Let deferred builders (furniture, traffic, people, grass) finish.
	for i in range(30): await process_frame
	var preview := Node3D.new()
	preview.name = "CityPreview"
	copy_tree(world, preview, preview)
	var packed := PackedScene.new()
	var err := packed.pack(preview)
	if err != OK:
		push_error("pack failed: %d" % err)
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.get_base_dir()))
	err = ResourceSaver.save(packed, OUT, ResourceSaver.FLAG_COMPRESS)
	print("BAKED %s: %d visual nodes, error %d" % [OUT, copied, err])
	quit(0 if err == OK else 1)

## Copy the visible pieces under `node` into `dest`, flattened to global transforms.
func copy_tree(node: Node, dest: Node3D, owner_node: Node) -> void:
	for child in node.get_children():
		var visible := not (child is Node3D) or (child as Node3D).visible
		if not visible: continue
		var copy := visual_copy(child)
		if copy != null:
			copy.name = child.name
			dest.add_child(copy)
			copy.owner = owner_node
			if copy is Node3D: (copy as Node3D).global_transform = (child as Node3D).global_transform
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
	c.cast_shadow = src.cast_shadow
	c.visibility_range_begin = src.visibility_range_begin
	c.visibility_range_end = src.visibility_range_end
	c.visibility_range_begin_margin = src.visibility_range_begin_margin
	c.visibility_range_end_margin = src.visibility_range_end_margin
	c.lod_bias = src.lod_bias
