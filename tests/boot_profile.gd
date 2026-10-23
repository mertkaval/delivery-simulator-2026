extends SceneTree
## Where does boot time go?  Godot --path . --script res://tests/boot_profile.gd [-- <depth=2>]
## Timestamps every node entering the tree while app_root builds and charges each gap to the
## subsystem (node path cut to <depth> levels under the app) that was being built. Prints the top
## 30 subsystems by milliseconds (BOOTCOST lines) and the total.
var stamps: Array = []

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var depth: int = int(args[0]) if args.size() > 0 else 2
	var packed: PackedScene = load("res://app/app_root.tscn")
	var app: Node = packed.instantiate()
	app.set("save_enabled", false)
	node_added.connect(func(n: Node) -> void: stamps.append([Time.get_ticks_usec(), n]))
	var t0 := Time.get_ticks_usec()
	root.add_child(app)
	var t1 := Time.get_ticks_usec()
	var cost := {}
	var prev_t := t0
	var prev_key := "(start)"
	for s in stamps:
		var n: Node = s[1]
		if not is_instance_valid(n): continue
		var path := str(app.get_path_to(n)) if app.is_ancestor_of(n) else str(n.get_path())
		var parts := path.split("/")
		var key := "/".join(parts.slice(0, depth))
		cost[prev_key] = float(cost.get(prev_key, 0.0)) + (int(s[0]) - prev_t) / 1000.0
		prev_t = int(s[0])
		prev_key = key
	cost[prev_key] = float(cost.get(prev_key, 0.0)) + (t1 - prev_t) / 1000.0
	var keys := cost.keys()
	keys.sort_custom(func(a: Variant, b: Variant) -> bool: return float(cost[a]) > float(cost[b]))
	for k in keys.slice(0, 30):
		print("BOOTCOST %8.0f ms  %s" % [float(cost[k]), k])
	print("BOOTTOTAL %.0f ms, %d nodes" % [(t1 - t0) / 1000.0, stamps.size()])
	quit()
