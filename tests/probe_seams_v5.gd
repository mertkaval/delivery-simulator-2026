extends SceneTree
## Dense seam probe: rays every 2 mm along short lines through given points (Blender xy), reporting every run of
## misses / drops (a crack between two collision meshes) with its width and the floor heights either side.
## usage: godot --headless --path . --script res://tests/probe_seams_v5.gd -- <export_dir> x,y,dx,dy[;x,y,dx,dy...]
const StreetBlock := preload("res://world/roads/mrs_street_block.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var block := StreetBlock.new()
	root.add_child(block)
	block.build(args[0], "street_block", {"lights": false, "trees": false})
	for i in 3: await physics_frame
	var space := root.world_3d.direct_space_state
	for spec: String in args[1].split(";"):
		var v := spec.split(",")
		var c := Vector3(float(v[0]), 0, -float(v[1]))
		var d := Vector3(float(v[2]), 0, -float(v[3])).normalized()
		var prev := NAN; var runs: Array = []; var start := -1.0; var before := NAN
		for k in range(-250, 251):
			var p := c + d * (k * 0.002)
			var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(p + Vector3(0, 2, 0), p - Vector3(0, 3, 0)))
			var z := NAN if hit.is_empty() else float((hit["position"] as Vector3).y)
			var low: bool = is_nan(z) or (not is_nan(prev) and z < prev - 0.05)
			if low and start < 0.0:
				start = k * 0.002; before = prev
			elif not low and start >= 0.0 and not is_nan(z) and (is_nan(before) or z > before - 0.05):
				runs.append("crack %.3f m wide at %+.3f (floor %.3f | %.3f)" % [k * 0.002 - start, start, before, z])
				start = -1.0
			if not low: prev = z
		print("SEAM ", spec, " -> ", runs if not runs.is_empty() else ["continuous"])
	quit(0)
