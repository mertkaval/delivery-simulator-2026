class_name DropZone
extends Node3D
## The delivery area at the customer's door for the active order: a small glowing lined
## rectangle on the porch/doorstep with corner brackets, a soft fill, a bobbing, slowly turning
## arrow above it and a label with the delivery method.
## - Leave at door: put the package down inside the lines (G, or E with it in your bag).
## - Meet at door: knock (E on the door) and the customer comes out to the doorstep; hand the
##   order over with E. The customer is a real citizen model with a collider ("customer").

const ARROW_MODEL := "res://assets/gadgets/drop_arrow.glb"
const SIZE := Vector2(1.3, 1.0)
const COLOURS := {"door": Color("ffd166"), "meet": Color("7fe3b5")}

var method := "door"
var address := -1
var facing := Vector3.BACK
var door_point := Vector3.ZERO
var arrow: Node3D
var label: Label3D
var customer: Node3D
var _t := 0.0
var _mat: StandardMaterial3D
var _fill_mat: StandardMaterial3D

## Build the zone in front of `door` (the door's world point, ~0.9 m above its floor),
## `out` = the direction out of the house.
func setup(at_address: int, door: Vector3, out: Vector3, how: String) -> void:
	address = at_address
	method = how
	door_point = door
	facing = Vector3(out.x, 0, out.z).normalized()
	var centre := find_floor(door, facing)
	global_position = centre
	basis = Basis(Vector3.UP, atan2(facing.x, facing.z))
	var colour: Color = COLOURS.get(method, COLOURS.door)
	_mat = StandardMaterial3D.new()
	_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat.albedo_color = colour
	_mat.emission_enabled = true
	_mat.emission = colour
	_fill_mat = StandardMaterial3D.new()
	_fill_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_fill_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_fill_mat.albedo_color = Color(colour, 0.16)
	_fill_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	# Lines: an outline plus thicker corner brackets, a few mm above the floor.
	var w := SIZE.x
	var d := SIZE.y
	for z: float in [-d * 0.5, d * 0.5]: strip(Vector3(0, 0.006, z), Vector3(w, 0.006, 0.03))
	for x: float in [-w * 0.5, w * 0.5]: strip(Vector3(x, 0.006, 0), Vector3(0.03, 0.006, d))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			strip(Vector3(sx * (w * 0.5 - 0.14), 0.008, sz * d * 0.5), Vector3(0.28, 0.01, 0.07))
			strip(Vector3(sx * w * 0.5, 0.008, sz * (d * 0.5 - 0.14)), Vector3(0.07, 0.01, 0.28))
	var fill := MeshInstance3D.new()
	var quad := PlaneMesh.new()
	quad.size = SIZE
	fill.mesh = quad
	fill.material_override = _fill_mat
	fill.position.y = 0.004
	fill.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(fill)
	# Arrow.
	if ResourceLoader.exists(ARROW_MODEL):
		arrow = (load(ARROW_MODEL) as PackedScene).instantiate()
		for mi in arrow.find_children("*", "MeshInstance3D", true, false):
			var m := mi as MeshInstance3D
			for i in range(m.mesh.get_surface_count()):
				var src := m.mesh.surface_get_material(i)
				if src and src.resource_name == "ArrowFill": m.set_surface_override_material(i, _mat)
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	else:
		arrow = Node3D.new()
		var cone := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.2
		cm.bottom_radius = 0.0
		cm.height = 0.36
		cone.mesh = cm
		cone.material_override = _mat
		cone.position.y = 0.18
		arrow.add_child(cone)
	add_child(arrow)
	label = Label3D.new()
	label.text = ("LEAVE HERE" if method == "door" else "MEET AT DOOR")
	label.font_size = 40
	label.pixel_size = 0.006
	label.outline_size = 10
	label.modulate = colour
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.position.y = 2.25
	add_child(label)
	# A flat collider so the interaction ray can target the area ("dropzone").
	var body := StaticBody3D.new()
	body.set_meta("interaction", "dropzone")
	body.collision_layer = 1
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(SIZE.x, 0.02, SIZE.y)
	shape.shape = box
	shape.position.y = 0.01
	body.add_child(shape)
	add_child(body)
	# Sparkle ring around the area.
	var sparks := GPUParticles3D.new()
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(SIZE.x * 0.5, 0.02, SIZE.y * 0.5)
	pm.direction = Vector3.UP
	pm.spread = 10.0
	pm.initial_velocity_min = 0.15
	pm.initial_velocity_max = 0.35
	pm.gravity = Vector3.ZERO
	pm.scale_min = 0.5
	pm.scale_max = 1.0
	sparks.process_material = pm
	var dot := QuadMesh.new()
	dot.size = Vector2(0.018, 0.018)
	var dot_mat := StandardMaterial3D.new()
	dot_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dot_mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	dot_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dot_mat.albedo_color = Color(colour, 0.8)
	dot.material = dot_mat
	sparks.draw_pass_1 = dot
	sparks.amount = 24
	sparks.lifetime = 1.6
	sparks.visibility_aabb = AABB(Vector3(-1, 0, -1), Vector3(2, 1.5, 2))
	add_child(sparks)

func strip(at: Vector3, size: Vector3) -> void:
	var m := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	m.mesh = b
	m.material_override = _mat
	m.position = at
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(m)

## The floor just outside the door: porch floor or front step (ray down from ~1 m out).
func find_floor(door: Vector3, out: Vector3) -> Vector3:
	var space := get_world_3d().direct_space_state if is_inside_tree() else null
	for dist: float in [1.05, 1.3, 1.6, 2.0, 2.6, 3.2]:
		var probe := door + out * dist
		if space == null: break
		# The door point is ~0.9 m above its floor: start just above it, under any porch roof.
		var q := PhysicsRayQueryParameters3D.create(probe + Vector3(0, 0.25, 0), probe + Vector3(0, -2.5, 0), 1)
		var hit := space.intersect_ray(q)
		if not hit.is_empty() and (hit.normal as Vector3).y > 0.85 and not (hit.collider as Node).has_meta("interaction") and door.y - (hit.position as Vector3).y < 1.6:
			return hit.position
	return Vector3(door.x, door.y - 0.92, door.z) + out * 1.05

## Is a world point inside the lines (with a little tolerance)?
func contains(p: Vector3) -> bool:
	var local := global_transform.affine_inverse() * p
	return absf(local.x) <= SIZE.x * 0.5 + 0.12 and absf(local.z) <= SIZE.y * 0.5 + 0.12 and local.y > -0.4 and local.y < 0.8

func _process(delta: float) -> void:
	_t += delta
	if arrow:
		arrow.visible = customer == null
		arrow.position.y = 1.25 + 0.16 * sin(_t * 2.6)
		arrow.rotation.y = _t * 1.2
	# The method label is for finding the door from the street; hide it up close.
	var cam := get_viewport().get_camera_3d()
	if label and cam: label.visible = customer == null and cam.global_position.distance_to(global_position) > 4.0
	var pulse := 0.5 + 0.5 * sin(_t * 3.4)
	if _mat: _mat.emission_energy_multiplier = 0.8 + 1.2 * pulse
	if _fill_mat: _fill_mat.albedo_color.a = 0.1 + 0.12 * pulse

## Meet at door: the customer opens the door and waits on the doorstep.
func call_customer(order: Dictionary) -> void:
	if customer != null or method != "meet": return
	# A resident of the customer's gender (designed townspeople); else the talking Avaturn avatar.
	var who: Node3D = LivingAssets.resident_for(str(order.get("customer", ""))) if not LivingAssets.load_people().is_empty() else LivingAssets.door_customer()
	if who == null: who = LivingAssets.humanoid(absi(hash(str(order.get("customer", "")))) % 6)
	customer = who
	who.name = "Customer"
	get_parent().add_child(who)
	var stand := find_floor(door_point, facing)
	who.global_position = door_point + facing * 0.55
	who.global_position.y = stand.y
	who.look_at(who.global_position + facing, Vector3.UP)   # the citizen faces its node's -Z: out of the house
	var players := who.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		var ap := players[0] as AnimationPlayer
		for clip: String in ["Talk", "Idle", "Idle_Loop"]:
			if ap.has_animation(clip):
				ap.play(clip)
				break
	var body := StaticBody3D.new()
	body.set_meta("interaction", "customer")
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.32
	capsule.height = 1.75
	shape.shape = capsule
	shape.position.y = 0.88
	body.add_child(shape)
	who.add_child(body)
	var hello := Label3D.new()
	hello.text = "Hi! Is that my order?"
	hello.font_size = 30
	hello.pixel_size = 0.005
	hello.outline_size = 8
	hello.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	hello.position.y = 2.05
	hello.name = "Speech"
	who.add_child(hello)

## Handover done: the customer thanks you, takes the package and goes back inside.
func customer_leaves(package: Node3D) -> void:
	if customer == null: return
	var who := customer
	customer = null
	var speech := who.get_node_or_null("Speech") as Label3D
	if speech: speech.text = "Thank you! Have a nice day."
	var players := who.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		var ap := players[0] as AnimationPlayer
		for clip: String in ["Interact", "Wave", "Talk"]:
			if ap.has_animation(clip):
				ap.play(clip)
				break
	if package:
		package.reparent(who)
		var tw := package.create_tween()
		tw.tween_property(package, "position", Vector3(0.0, 1.0, 0.32), 0.45)
	var tw2 := who.create_tween()
	tw2.tween_interval(2.4)
	tw2.tween_callback(func() -> void: who.rotate_y(PI))
	tw2.tween_property(who, "global_position", door_point - facing * 0.6 + Vector3(0, who.global_position.y - door_point.y, 0), 1.2)
	tw2.tween_callback(who.queue_free)
	# The door shuts behind them (a tween on this zone, so it dies with the zone).
	var tw3 := create_tween()
	tw3.tween_interval(3.6)
	tw3.tween_callback(func() -> void:
		var audio := get_tree().get_first_node_in_group("city_audio") as CityAudio
		if audio: audio.one_shot_at("door_close", door_point + Vector3(0, 1.2, 0), -6.0, 4.0))

func clear() -> void:
	if customer: customer.queue_free()
	customer = null
	queue_free()
