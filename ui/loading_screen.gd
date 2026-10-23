class_name LoadingScreen
extends CanvasLayer
## Keeps the window alive while app_root builds the city synchronously (~10-15 s; the
## Neighborhood child readies before app_root). Every node entering the tree is counted; at most
## every PUMP_MS the bar and the subsystem being built are redrawn, window events are pumped (no
## "Not responding") and one frame is force-drawn.
## - Drawn straight into a RenderingServer canvas item: Control redraws are deferred calls that
##   never run while the main loop is blocked.
## - The root viewport's 3D is off while loading, so a forced frame never renders (or compiles
##   shaders for) the half-built city.
## - Root-viewport input is off until finish(), so pumped clicks and keys never reach half-built
##   nodes. Headless runs (tests) skip all of it.

const PUMP_MS := 50
## Nodes a full city boot adds (36.5k in October 2026); only scales the bar, which stops at 97 %.
const EXPECTED_NODES := 36500
const NAMES := {"KitBuildings": "Terraces and walk-ups", "Residences": "Houses", "GrassMeadows": "Meadows",
	"RainlineDowntown": "Downtown", "CityTraffic": "Traffic", "CurvedRoads": "Roads", "Buses": "Buses",
	"Landscape": "Trees and gardens", "CedarHome": "Your home", "Restaurants": "Restaurants",
	"StreetSignage": "Street signs", "StreetFurniture": "Street furniture", "CityLife": "People",
	"Animals": "Animals", "Monuments": "Parks and monuments", "CourierPlayer": "Courier"}

var count := 0
var last_pump := 0
var watching: Node
var pumping := false
var item: RID
var title_font: Font
var text_font: Font
var had_3d := false

func _init() -> void:
	layer = 120
	process_mode = Node.PROCESS_MODE_ALWAYS

## Start watching `app` being built.
func begin(app: Node) -> void:
	watching = app
	pumping = DisplayServer.get_name() != "headless"
	if not pumping: return
	title_font = HudStyle.font(HudStyle.Face.DISPLAY, HudStyle.SEMIBOLD)
	text_font = HudStyle.font(HudStyle.Face.TEXT, HudStyle.REGULAR)
	item = RenderingServer.canvas_item_create()
	RenderingServer.canvas_item_set_parent(item, get_canvas())
	var viewport := get_viewport()
	had_3d = not viewport.disable_3d
	viewport.disable_3d = true
	viewport.set_disable_input(true)
	get_tree().node_added.connect(_on_node_added)
	_pump("Loading the city")

func _on_node_added(node: Node) -> void:
	count += 1
	if Time.get_ticks_msec() - last_pump < PUMP_MS: return
	var key := ""
	if is_instance_valid(watching) and watching.is_ancestor_of(node):
		var parts := str(watching.get_path_to(node)).split("/")
		key = parts[1] if parts.size() > 1 and parts[0] == "Neighborhood" else parts[0]
	_pump("Building: %s" % NAMES.get(key, key.capitalize()) if key != "" else "Loading the city")

func _pump(text: String) -> void:
	last_pump = Time.get_ticks_msec()
	_draw_screen(text, minf(float(count) / EXPECTED_NODES, 0.97))
	DisplayServer.process_events()
	RenderingServer.force_draw(true, 0.0)

func _draw_screen(text: String, progress: float) -> void:
	var size := get_viewport().get_visible_rect().size
	var scale := clampf(size.y / 720.0, 1.0, 2.0)     # the HUD's 720p sizes on bigger screens
	var w := 360.0 * scale
	var at := Vector2((size.x - w) * 0.5, size.y * 0.5 - 24.0 * scale)
	RenderingServer.canvas_item_clear(item)
	RenderingServer.canvas_item_add_rect(item, Rect2(Vector2.ZERO, size), Color("0d1416"))
	title_font.draw_string(item, at, "DELIVERY SIMULATOR 2026", HORIZONTAL_ALIGNMENT_LEFT, -1, int(HudStyle.TITLE * scale), HudStyle.ACCENT)
	text_font.draw_string(item, at + Vector2(0, 26 * scale), text, HORIZONTAL_ALIGNMENT_LEFT, -1, int(HudStyle.BODY * scale), HudStyle.INK_SOFT)
	var bar := Rect2(at + Vector2(0, 42 * scale), Vector2(w, 4 * scale))
	RenderingServer.canvas_item_add_rect(item, bar, HudStyle.FAINT)
	RenderingServer.canvas_item_add_rect(item, Rect2(bar.position, Vector2(w * progress, bar.size.y)), HudStyle.ACCENT)

func finish() -> void:
	if pumping:
		get_tree().node_added.disconnect(_on_node_added)
		var viewport := get_viewport()
		viewport.set_disable_input(false)
		viewport.disable_3d = not had_3d
		RenderingServer.free_rid(item)
	queue_free()
