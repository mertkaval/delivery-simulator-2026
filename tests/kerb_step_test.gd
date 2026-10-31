extends SceneTree
## On foot the courier steps up a kerb (CourierPlayer.step_up, up to STEP_MAX) without jumping, steps back down off
## it, and is still stopped by a wall higher than a step. Built on a test pad far above the city.
## godot --headless --path . --script res://tests/kerb_step_test.gd
var failures := 0
var checks := 0
var player: CourierPlayer

func check(ok: bool, what: String) -> void:
	checks += 1
	if ok: print("PASS " + what)
	else:
		failures += 1
		print("FAIL: " + what)

func _initialize() -> void: call_deferred("run")

func ticks(n: int) -> void:
	for i in range(n): await physics_frame
	await process_frame

## A static box: centre, size.
func block(parent: Node, centre: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	body.add_child(shape)
	body.position = centre
	parent.add_child(body)

## Walk forward (-Z) for n physics frames from `from`; returns where the courier ends up.
func walk_from(from: Vector3, n: int) -> Vector3:
	player.position = from
	player.rotation = Vector3.ZERO
	player.velocity = Vector3.ZERO
	await ticks(10)
	Input.action_press("move_forward")
	await ticks(n)
	Input.action_release("move_forward")
	await ticks(20)
	return player.position

func run() -> void:
	var game: Node = load("res://app/app_root.tscn").instantiate()
	game.save_enabled = false
	root.add_child(game)
	game.close_menu()
	player = game.player
	var pad := Node3D.new()
	pad.position = Vector3(0, 400, 0)
	root.add_child(pad)
	var top := 400.0
	# road (y 0) 40 m long; from z = -6 on a 0.15 m kerb (sidewalk), in a second lane a 0.6 m wall
	block(pad, Vector3(0, -0.5, 0), Vector3(30, 1.0, 40))
	block(pad, Vector3(-4, 0.075, -12), Vector3(4, 0.15, 12))
	block(pad, Vector3(6, 0.3, -12), Vector3(4, 0.6, 12))
	var on_kerb := await walk_from(Vector3(-4, top + 0.05, 0), 180)
	check(on_kerb.z < -7.0 and absf(on_kerb.y - (top + 0.15)) < 0.06, "walks up a 15 cm kerb without a jump (ends at z %.1f, %.2f m up)" % [on_kerb.z - 0.0, on_kerb.y - top])
	# back down: turn round and walk off the kerb onto the road
	player.position = Vector3(-4, top + 0.2, -10)
	player.rotation = Vector3(0, PI, 0)
	player.velocity = Vector3.ZERO
	await ticks(10)
	Input.action_press("move_forward")
	await ticks(180)
	Input.action_release("move_forward")
	await ticks(20)
	check(player.position.z > -5.0 and absf(player.position.y - top) < 0.06, "walks down off the kerb onto the road (%.2f m)" % (player.position.y - top))
	var at_wall := await walk_from(Vector3(6, top + 0.05, 0), 180)
	check(at_wall.z > -6.0 and at_wall.y < top + 0.1, "a 60 cm wall still stops the courier (ends at z %.1f)" % at_wall.z)
	check(CourierPlayer.STEP_MAX < 0.6 and CourierPlayer.STEP_MAX >= 0.2, "step height %.2f m: kerbs yes, walls no" % CourierPlayer.STEP_MAX)
	print("KERB STEP: %d checks, %d failures" % [checks, failures])
	quit(1 if failures > 0 else 0)
