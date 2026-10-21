extends SceneTree
## Rendered captures of the landscape pass (run WITHOUT --headless):
##   Godot --path . --script res://tests/capture_landscape.gd -- <out_dir> [view,view...] [legacy]
## Saves <out_dir>/land_<view>.png at 1280x720, 14:00.
const VIEWS := {
	"avenue": [Vector3(-4.5, 1.7, -52), Vector3(1.5, 4.0, -110)],
	"avenue_high": [Vector3(16, 11, -20), Vector3(0, 2, -85)],
	"front_gardens": [Vector3(-7.5, 1.7, -296), Vector3(-17, 1.6, -306)],
	"residential": [Vector3(-60.5, 1.75, -292), Vector3(-64, 3.5, -350)],
	"cross_street": [Vector3(-14, 1.8, -394), Vector3(-50, 3.0, -399)],
	"backyards": [Vector3(-36.5, 2.2, -296), Vector3(-34, 2.5, -340)],
	"park": [Vector3(57, 2.8, -308), Vector3(44, 1.7, -332)],
	"park_high": [Vector3(62, 26, -296), Vector3(44, 0, -330)],
	"roundabout_park": [Vector3(-40, 5, -122), Vector3(-64, 1, -145)],
	"shop": [Vector3(-88, 1.7, -19), Vector3(-92, 1.0, -27)],
	"edge_west": [Vector3(-95, 9, -425), Vector3(-220, 8, -445)],
	"edge_high": [Vector3(-40, 45, -150), Vector3(-260, 0, -330)],
	"edge_south": [Vector3(6, 4, 55), Vector3(0, 8, 200)],
	"skyline": [Vector3(30, 70, 40), Vector3(0, 0, -300)],
}

func _initialize() -> void: call_deferred("run")

func run() -> void:
	root.size = Vector2i(1280, 720)
	var args := OS.get_cmdline_user_args()
	var out: String = args[0] if args.size() > 0 else "res://tmp"
	var only: PackedStringArray = args[1].split(",") if args.size() > 1 and args[1] != "all" else PackedStringArray()
	CityLandscape.legacy = args.size() > 2 and args[2] == "legacy"
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	camera.fov = 70
	camera.far = 3000
	world.add_child(camera)
	camera.current = true
	var land: CityLandscape = world.landscape
	print("LANDSCAPE counts ", JSON.stringify(land.counts))
	for key: String in VIEWS:
		if not only.is_empty() and not only.has(key): continue
		var v: Array = VIEWS[key]
		camera.position = v[0]
		camera.look_at(v[1])
		for i in range(45): await process_frame
		var img := root.get_texture().get_image()
		var path := "%s/land_%s%s.png" % [out, key, "_legacy" if CityLandscape.legacy else ""]
		img.save_png(path)
		print("saved ", path)
	quit()
