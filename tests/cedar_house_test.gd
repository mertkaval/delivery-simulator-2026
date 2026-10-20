extends SceneTree
var game: Node3D
var failures := 0
var lines: Array[String] = []
class MemorySave extends DeliverySave:
	func save_game(_data: Dictionary, _path: String = PATH) -> bool:
		return true

func _initialize() -> void:
	call_deferred("run")
func check(ok: bool, text: String) -> void:
	lines.append(("PASS: " if ok else "FAIL: ")+text)
	if not ok: failures += 1
func move_player(frames: int, direction: Vector3) -> void:
	for i in range(frames):
		await physics_frame
		game.player.velocity.x = direction.x*3.5
		game.player.velocity.z = direction.z*3.5
		if not game.player.is_on_floor(): game.player.velocity.y -= 20.0/60.0
		game.player.move_and_slide()
func run() -> void:
	game = load("res://app/app_root.tscn").instantiate()
	game.saves = MemorySave.new()
	root.add_child(game)
	game.close_menu()
	game.set_process(false)
	game.player.set_physics_process(false)
	check(game.world.doors.size()==41,"Original and downtown delivery destinations preserved")
	var home: Node3D = game.world.cedar_house
	check(home.doors.size()==5,"Five house doors loaded in the real neighborhood")
	check(home.position.is_equal_approx(Vector3(17.9,.015,29.6)),"House placed on starter-home plot at meter scale")
	game.player.position=Vector3(19,.2,39.8)
	game.player.rotation=Vector3.ZERO
	game.player.camera.rotation=Vector3.ZERO
	await move_player(120,Vector3(0,0,-1))
	check(game.player.position.z>35.3 and game.player.position.z<35.7,"Existing courier collides with closed front door")
	check(absf(game.player.position.y-.735)<.13,"Existing courier walks up veranda steps")
	var hit: Dictionary = game.player.target()
	check(hit.get("id")=="cedar_door_0","Existing interaction ray detects new door")
	var before: float = game.session.calendar_minutes
	game.interact()
	check(home.doors[0].open,"Existing E interaction opens the door")
	check(game.session.calendar_minutes==before,"Opening door does not trigger home rest")
	await move_player(90,Vector3.ZERO)
	await move_player(50,Vector3(0,0,-1))
	check(game.player.position.z<34,"Walkable interior has no old starter-house solid block")
	game.player.position=Vector3(17.8,.76,36.4)
	game.player.camera.look_at(Vector3(17.8,1.66,35.4))
	await move_player(2,Vector3.ZERO)
	check(game.player.target().get("id")=="home","Rest/save plaque remains interactable")
	game.interact()
	check(game.session.calendar_minutes>before,"Existing home rest still advances to morning")
	var report := "\n".join(lines)+"\n"
	print(report)
	var file := FileAccess.open("C:/Users/mert3/Documents/Codex/2026-09-13/b/outputs/Cedar_House/integration_validation.txt",FileAccess.WRITE)
	file.store_string(report)
	quit(0 if failures==0 else 1)

