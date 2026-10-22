class_name CourierSequence
extends Node
## One-button courier actions, played as one smooth sequence while the courier stands still
## (CourierPlayer.busy) and the camera stays where it is:
##   pack   - at the shelf, after picking the order up: Bag_TakeOff -> Bag_PackItem (into the
##            compartment that fits its kind) -> Bag_PutOn.
##   leave  - leave at door: Bag_TakeOff -> Bag_TakeItem -> PlaceDown in the marked area ->
##            proof photo -> Bag_PutOn (by hand without a bag: PlaceDown -> photo).
##   meet   - meet at door: Bag_TakeOff -> Bag_TakeItem -> Handover -> Bag_PutOn (by hand:
##            Handover).
## Each step plays the courier's action clip (PlayerAvatar.play_action) when the body has it, and
## the bag follows the clip's published bag_track; until those clips exist the steps are posed
## procedurally: the worn bag (WornBackpack) swings off the back into the left hand, the right
## hand moves the package, two-bone IK puts the hands on the handle / the package.
## In first person the existing BagRig view is used instead (the bag swings into view).
## Game effects (session state, sounds, photo, payout) come in as callables from app_root, so
## this node only animates and times.

signal step_started(role: String)
signal finished(kind: String)

## Placeholder step lengths (s) when the body has no clip for the role.
const TIMES := {"pick_up": 0.55, "bag_take_off": 0.8, "bag_pack": 1.0, "bag_take": 0.75, "bag_put_on": 0.8,
	"place_down": 0.95, "handover": 1.0, "photo": 0.45}
## Placeholder poses in the courier's root space (-Z forward, metres). The bag hangs from the left
## hand by its top handle, front-left of the body, its opening (model +Z) turned to the right
## hand.
var BAG_HOLD := Transform3D(Basis(Vector3.UP, PI / 2), Vector3(-0.25, 0.66, -0.38))
## Package in the right hand, front-right of the belly.
var ITEM_RIGHT := Transform3D(Basis(Vector3.UP, -0.25), Vector3(0.2, 0.92, -0.36))

var game                      ## app_root (dynamic: player, session, bag_rig, sounds)
var running := false
var kind := ""
var role := ""                ## the step playing now
var time_scale := 1.0
var _markers: Array[Node3D] = []

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "CourierSequence"
	process_mode = Node.PROCESS_MODE_PAUSABLE

func player() -> CourierPlayer:
	return game.player

func avatar() -> PlayerAvatar:
	return game.player.avatar

func third_person() -> bool:
	var p := player()
	return p.third_person and p.avatar != null and p.avatar.ready_ok and p.avatar.backpack != null

func wait(seconds: float) -> void:
	await get_tree().create_timer(maxf(0.01, seconds / maxf(time_scale, 0.01)), false).timeout

## Begin: lock the courier, face `toward` (world point), frame the action.
func begin(what: String, toward: Vector3) -> void:
	running = true
	kind = what
	var p := player()
	p.busy = true
	p.velocity = Vector3(0, p.velocity.y, 0)
	if p.view: p.view.action_frame = true
	var a := avatar()
	if a != null:
		var d := toward - p.global_position
		if Vector2(d.x, d.z).length() > 0.05: a.face_goal = atan2(-d.x, -d.z)

func end() -> void:
	var p := player()
	var a := avatar()
	if a != null:
		a.face_goal = NAN
		if a.backpack and a.backpack.scene_mode() and a.backpack.has_bag():
			a.backpack.socket_back(true)
			a.backpack.set_body_straps(true, true)
		a.set_hand_goals(null, null)
		a.hand_goal_weight = 0.0
		a.stop_action()
	for m in _markers:
		if is_instance_valid(m): m.queue_free()
	_markers.clear()
	p.busy = false
	if p.view: p.view.action_frame = false
	_clip_on = false
	_pkg_mode = ""
	running = false
	role = ""
	var k := kind
	kind = ""
	finished.emit(k)

## Start a procedural (placeholder) step: returns its time.
func play(step_role: String) -> float:
	role = step_role
	step_started.emit(step_role)
	return float(TIMES.get(step_role, 0.8))

# --- Clip-driven steps (the animation contract: clips + bag_track / package_track / events) -------

var _clip: Dictionary = {}
var _clip_on := false
var _events_done := -1.0
var _pkg: Node3D
var _pkg_mode := ""
var _on_event: Callable
var _flap_prev := -1.0
var _set_down_heard := false   ## PlaceDown's release frame already played the set-down sound

## A sound for the courier's own action (2D, UI bus), at a level relative to game.sound().
func cue(sound: String, volume_db := -6.0) -> void:
	if game.audio != null and CityAudio.has_sound(sound): (game.audio as CityAudio).play_ui(sound, volume_db)

## Third person with the contract's bag scenes and the courier's bag clips.
func clip_mode() -> bool:
	return third_person() and avatar().backpack.scene_mode() and avatar().has_clip("bag_take_off") and avatar().has_clip("bag_pack")

## A transform from a [px, py, pz, qx, qy, qz, qw] per-frame track, interpolated at `frame`.
static func track_xf(track: Array, frame: float) -> Transform3D:
	if track.is_empty(): return Transform3D.IDENTITY
	var f := clampf(frame, 0.0, float(track.size() - 1))
	var i := int(floor(f))
	var j := mini(i + 1, track.size() - 1)
	var t := f - float(i)
	var a: Array = track[i]
	var b: Array = track[j]
	var qa := Quaternion(float(a[3]), float(a[4]), float(a[5]), float(a[6])).normalized()
	var qb := Quaternion(float(b[3]), float(b[4]), float(b[5]), float(b[6])).normalized()
	return Transform3D(Basis(qa.slerp(qb, t)), Vector3(float(a[0]), float(a[1]), float(a[2])).lerp(Vector3(float(b[0]), float(b[1]), float(b[2])), t))

static func track_value(list: Array, frame: float) -> float:
	if list.is_empty(): return 0.0
	var f := clampf(frame, 0.0, float(list.size() - 1))
	var i := int(floor(f))
	return lerpf(float(list[i]), float(list[mini(i + 1, list.size() - 1)]), f - float(i))

## Play a clip step: the body clip, the held bag on its bag_track (flap angle too), the package on
## its package_track, and the clip's events in order. `hold` > 0: play a looping clip that long.
func play_clip(step_role: String, pkg: Node3D = null, on_event := Callable(), hold := -1.0) -> void:
	var a := avatar()
	var length := a.play_action(step_role)
	if length <= 0.0: return
	role = step_role
	step_started.emit(step_role)
	_clip = a.contract_clip(a.action_clip_name)
	_events_done = -1.0
	_flap_prev = -1.0
	if pkg != null: _pkg = pkg
	_on_event = on_event
	_clip_on = true
	apply_clip(0.0)
	var span := hold if hold > 0.0 else length
	await wait(span)
	if hold <= 0.0: apply_clip(length * 30.0)
	_clip_on = false

func _process(_delta: float) -> void:
	if _clip_on: apply_clip(avatar().action_time * 30.0)

func apply_clip(frame: float) -> void:
	var bp := avatar().backpack
	var bag := bp.held_bag()
	if bag and _clip.get("bag_track", null) is Array: bag.transform = track_xf(_clip.bag_track, frame)
	if bag and _clip.get("flap_deg", null) is Array:
		var flap := bp.held_node("Flap")
		var deg := track_value(_clip.flap_deg, frame)
		if flap: flap.rotation.x = deg_to_rad(deg)
		# The flap passing upright: velcro tearing open, or pressed shut.
		if _flap_prev >= 0.0 and _flap_prev < 90.0 and deg >= 90.0: cue("bag_velcro_open")
		elif _flap_prev >= 90.0 and deg < 90.0: cue("bag_flap_close")
		_flap_prev = deg
	if _clip.get("events", null) is Array:
		for e: Dictionary in _clip.events:
			var f := float(e.get("frame", 0.0))
			if f > _events_done and f <= frame: clip_event(e)
	_events_done = maxf(_events_done, frame)
	if _pkg_mode == "track" and is_instance_valid(_pkg) and _clip.get("package_track", null) is Array:
		_pkg.transform = track_xf(_clip.package_track, frame)

func clip_event(e: Dictionary) -> void:
	var bp := avatar().backpack
	match str(e.get("do", "")):
		"bag_socket":
			var to_back := str(e.get("to", "")) == "back"
			if to_back != bp.on_back: cue("bag_on_shoulder" if to_back else "bag_off_shoulder")
			bp.socket_back(to_back)
		"body_strap_l", "body_strap_r":
			if role == "bag_strap_right" and bool(e.get("visible", true)): cue("bag_on_shoulder", -14.0)
			for n in bp.straps:
				if str(n.name).ends_with("L" if str(e.do).ends_with("_l") else "R"): n.visible = bool(e.get("visible", true))
		"bag_strap_l", "bag_strap_r":
			var strap := bp.held_node("StrapL" if str(e.do).ends_with("_l") else "StrapR")
			if strap: strap.visible = bool(e.get("visible", true))
		"package":
			if not is_instance_valid(_pkg): return
			var to := str(e.get("to", ""))
			if to == "track" and role == "bag_take": cue("package_out_of_bag")
			if to == "released" and role == "place_down":
				cue("package_drop")
				_set_down_heard = true
			if to == "track":
				if _pkg.get_parent() != avatar().body:
					if _pkg.get_parent(): _pkg.reparent(avatar().body, false)
					else: avatar().body.add_child(_pkg)
				_pkg.visible = true
				_pkg_mode = "track"
			elif to == "bag":
				var slot := bp.held_node("Slot_Top")
				_pkg.reparent(slot if slot else bp.held_bag(), false)
				_pkg.transform = Transform3D.IDENTITY
				_pkg_mode = "bag"
			elif to == "released":
				_pkg.reparent(game.world, true)
				_pkg_mode = "released"
			if _on_event.is_valid(): _on_event.call(to)

## The package (a world node) flies onto the right palm, where the next clip's package_track
## starts, while the courier holds the bag out (Bag_Hold).
func grab_to_palm(pkg: Node3D, next_clip: String, seconds: float) -> void:
	var info := avatar().contract_clip(next_clip)
	var start := track_xf(info.get("package_track", []), 0.0)
	var to := avatar().body.global_transform * start
	if pkg.get_parent() == null: game.world.add_child(pkg)
	pkg.visible = true
	_pkg_mode = ""
	var tw := create_tween()
	tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(pkg, "global_transform", to, seconds)
	await play_clip("bag_hold", null, Callable(), seconds + 0.02)

## The package hops from the right palm to `to` (world) with a little arc, the bag held out.
func hop_to(pkg: Node3D, to: Transform3D, seconds: float) -> void:
	_pkg_mode = ""
	if pkg.get_parent() != game.world: pkg.reparent(game.world, true)
	var from := pkg.global_transform
	var tw := create_tween()
	tw.tween_method(func(t: float) -> void:
		if not is_instance_valid(pkg): return
		var e := smoothstep(0.0, 1.0, t)
		var xf := from.interpolate_with(to, e)
		xf.origin.y += sin(PI * t) * 0.12
		pkg.global_transform = xf, 0.0, 1.0, seconds)
	await play_clip("bag_hold", null, Callable(), seconds + 0.05)

func pack_clips(pkg: Node3D, on_packed: Callable) -> void:
	var packed := [false]
	# The bag comes off first (the order still where it was), then the right hand takes the order
	# and pushes it into the top compartment, and the bag goes back on.
	await play_clip("bag_take_off")
	await grab_to_palm(pkg, avatar().clip("bag_pack"), 0.4)
	game.sound("item_pickup")
	await play_clip("bag_pack", pkg, func(what: String) -> void:
		if what == "bag" and not packed[0]:
			packed[0] = true
			game.sound("package_place")
			on_packed.call())
	if not packed[0]: on_packed.call()
	await play_clip("bag_put_on")
	if is_instance_valid(pkg): pkg.queue_free()
	_pkg = null
	end()

## The contract's flow for meet / leave keeps the package in hand: the bag goes back over the
## left shoulder first (Bag_PutOn_Holding), the right arm finds its strap afterwards.
func holding_flow() -> bool:
	return avatar().has_clip("bag_put_on_holding") and avatar().has_clip("bag_strap_right") and avatar().has_clip("place_down") and avatar().has_clip("handover")

## Out of the bag into the hands: Bag_TakeOff -> Bag_TakeItem (-> Bag_PutOn_Holding).
func take_out_clips(pkg: Node3D) -> void:
	await play_clip("bag_take_off")
	pkg.visible = false
	avatar().body.add_child(pkg)
	await play_clip("bag_take", pkg)
	if holding_flow(): await play_clip("bag_put_on_holding", pkg)

## PlaceDown from the hands; the package slides into the lines if it landed outside them.
func place_down_clip(pkg: Node3D, spot: Transform3D, zone_check: Callable) -> void:
	await play_clip("place_down", pkg)
	if is_instance_valid(pkg) and not bool(zone_check.call(pkg.global_position)):
		var tw := create_tween()
		tw.tween_property(pkg, "global_transform", spot, 0.25)
		await wait(0.27)

func leave_clips(pkg: Node3D, from_bag: bool, spot: Transform3D, zone_check: Callable, on_down: Callable) -> void:
	if from_bag and holding_flow():
		await take_out_clips(pkg)
		await place_down_clip(pkg, spot, zone_check)
		if not _set_down_heard: game.sound("package_drop")
		_set_down_heard = false
		_pkg_mode = ""
		role = "photo"
		step_started.emit("photo")
		on_down.call(pkg)
		await wait(float(TIMES.photo))
		await play_clip("bag_strap_right")
		_pkg = null
		end()
		return
	if from_bag:
		await take_out_clips(pkg)
		# Set down in the marked area while the bag is held out.
		role = "place_down"
		step_started.emit("place_down")
		await hop_to(pkg, spot, 0.55)
	else:
		await play_clip("place_down", pkg)
		if is_instance_valid(pkg) and not bool(zone_check.call(pkg.global_position)):
			var tw := create_tween()
			tw.tween_property(pkg, "global_transform", spot, 0.25)
			await wait(0.27)
	if not _set_down_heard: game.sound("package_drop")
	_set_down_heard = false
	_pkg_mode = ""
	role = "photo"
	step_started.emit("photo")
	on_down.call(pkg)
	await wait(float(TIMES.photo))
	if from_bag: await play_clip("bag_put_on")
	_pkg = null
	end()

func meet_clips(pkg: Node3D, from_bag: bool, customer: Node3D, toward: Vector3, on_handed: Callable) -> void:
	if from_bag and holding_flow():
		await take_out_clips(pkg)
		await handover_clip(pkg, on_handed)
		await play_clip("bag_strap_right")
		_pkg = null
		end()
		return
	if from_bag:
		await take_out_clips(pkg)
		role = "handover"
		step_started.emit("handover")
		var to := Transform3D(Basis(Vector3.UP, atan2(player().global_position.x - toward.x, player().global_position.z - toward.z)), toward + Vector3(0, 0.98, 0) + (player().global_position - toward).normalized() * 0.28)
		to.origin.y = toward.y + 0.98
		await hop_to(pkg, to, 0.5)
		game.sound("item_pickup")
		on_handed.call(pkg)
		await play_clip("bag_put_on")
	else:
		await handover_clip(pkg, on_handed)
	_pkg = null
	end()

## Handover from both hands: the customer takes it at the clip's release frame.
func handover_clip(pkg: Node3D, on_handed: Callable) -> void:
	var handed := [false]
	await play_clip("handover", pkg, func(what: String) -> void:
		if what == "released" and not handed[0]:
			handed[0] = true
			game.sound("item_pickup")
			on_handed.call(_pkg))
	if not handed[0]: on_handed.call(pkg)

## Courier-root-space transform -> world.
func root_xf(local: Transform3D) -> Transform3D:
	return avatar().global_transform * local

## A hand marker under `parent`: palm centre `at` (parent space), fingers / palm normal directions.
func marker(parent: Node3D, at: Vector3, fingers: Vector3, palm: Vector3) -> Node3D:
	var m := Node3D.new()
	m.name = "HandMarker"
	var z := -fingers.normalized()
	var y := -palm
	y = (y - z * y.dot(z)).normalized()
	m.transform = Transform3D(Basis(y.cross(z), y, z), at)
	parent.add_child(m)
	_markers.append(m)
	return m

## A hand on the left (side -1) or right (+1) face of a package, palm inwards, fingers forward.
func side_marker(pkg: Node3D, side: int) -> Node3D:
	var box := avatar().package_box(pkg)
	var x := box.position.x - 0.005 if side < 0 else box.end.x + 0.005
	return marker(pkg, Vector3(x, box.position.y + box.size.y * 0.42, box.get_center().z), Vector3(0, 0, -1), Vector3(-float(side), 0, 0))

func hands(left: Node3D, right: Node3D, weight := 1.0) -> void:
	var a := avatar()
	if a == null: return
	a.set_hand_goals(left, right)
	create_tween().tween_property(a, "hand_goal_weight", weight, 0.2)

## Move `node` (a child of the avatar) to `to` (avatar space) over `seconds`, swinging out by
## `arc` (avatar space) at mid-way.
func swing(node: Node3D, to: Transform3D, seconds: float, arc := Vector3.ZERO) -> void:
	var from := node.transform
	var tw := create_tween()
	tw.tween_method(func(t: float) -> void:
		if not is_instance_valid(node): return
		var e := smoothstep(0.0, 1.0, t)
		var xf := from.interpolate_with(to, e)
		xf.origin += arc * sin(PI * t)
		node.transform = xf, 0.0, 1.0, seconds / maxf(time_scale, 0.01))

## The package node: re-parented to the avatar (keeping its world pose) so the steps can move it.
func adopt(pkg: Node3D) -> void:
	if pkg == null or not third_person(): return
	var at := pkg.global_transform
	if pkg.get_parent(): pkg.reparent(avatar(), false)
	else: avatar().add_child(pkg)
	pkg.global_transform = at
	pkg.visible = true

## Bag off the back into the left hand (third person), or swung into view (first person).
func take_off_bag() -> void:
	var t := play("bag_take_off")
	game.sound("bag_zip")
	if third_person():
		var bp := avatar().backpack
		bp.detach()
		var handle := marker(bp.model, Vector3(0, 0.53, 0.0), Vector3(1, 0, 0), Vector3(0, -1, 0))
		var a := avatar()
		hands(handle, a.hand_goals[1] if a.hand_goals[1] != null else null)
		swing(bp.model, BAG_HOLD, t * 0.9, Vector3(-0.28, 0.12, 0.1))
	else:
		game.bag_rig.take_off()
	await wait(t)

## Bag back onto the shoulders.
func put_on_bag() -> void:
	var t := play("bag_put_on")
	game.sound("bag_zip")
	if third_person():
		var bp := avatar().backpack
		bp.open(false)
		var a := avatar()
		hands(a.hand_goals[0], null)
		swing(bp.model, bp.back_pose(), t * 0.85, Vector3(-0.3, 0.15, 0.1))
		await wait(t * 0.9)
		bp.attach()
		a.hand_goal_weight = 0.0
		a.set_hand_goals(null, null)
		await wait(t * 0.1)
	else:
		game.bag_rig.put_on()
		await wait(t)

## Where the bag's compartment for `slot` is, in the shown bag model's space.
func compartment(slot: String) -> Vector3:
	var bp := avatar().backpack
	var node := bp.shown()
	for n: Node in [node] + node.get_children():
		var extras: Variant = n.get_meta("extras", {})
		if extras is Dictionary and (extras as Dictionary).has("compartments"):
			var c: Dictionary = ((extras as Dictionary)["compartments"] as Dictionary).get(BagRig.SLOT_KEYS.get(slot, "top"), {})
			var centre := BagRig.vec(c.get("center", null), Vector3(0, 0.32, 0))
			return (node.transform.affine_inverse() * (n as Node3D).transform * centre) if n != node else centre
	return Vector3(0, 0.32, 0)

# --- Sequences ---------------------------------------------------------------------------------

## At the shelf, just picked up: pack `pkg` (the held package node) into `slot`.
## on_packed() is called the moment it goes in (session.stow). `low`: it was picked up from
## near the floor (the PickUp clip bends down for it; from a counter the arms just reach).
func pack(pkg: Node3D, slot: String, toward: Vector3, on_packed: Callable, low := false) -> void:
	begin("pack", toward)
	if clip_mode():
		await pack_clips(pkg, on_packed)
		return
	var fp := not third_person()
	# PickUp / carry: the package has just flown into the hands.
	if fp or not low:
		role = "pick_up"
		step_started.emit("pick_up")
		await wait(float(TIMES.pick_up))
	else:
		await wait(play("pick_up"))
	if fp:
		game.bag_rig.take_off()
		game.sound("bag_zip")
		await wait(0.5)
		role = "bag_pack"
		step_started.emit("bag_pack")
		game.bag_rig.pack(pkg, slot)
		game.sound("package_place")
		on_packed.call()
		await wait(0.9)
		role = "bag_put_on"
		step_started.emit("bag_put_on")
		game.bag_rig.put_on()
		game.sound("bag_zip")
		await wait(0.55)
		end()
		return
	adopt(pkg)
	var a := avatar()
	var bp := a.backpack
	# Package into the right hand while the left takes the bag off.
	var right := side_marker(pkg, 1)
	a.set_hand_goals(null, right)
	a.hand_goal_weight = 1.0
	swing(pkg, ITEM_RIGHT, 0.35)
	await take_off_bag()
	# Into the bag: flap open, the right hand slides it in through the opening.
	var t := play("bag_pack")
	bp.open(true)
	var inside := compartment(slot)
	var mouth := Transform3D(Basis.IDENTITY, inside + Vector3(0, 0.02, 0.32))
	var bag_xf := bp.model.transform
	swing(pkg, bag_xf * mouth * Transform3D(Basis(Vector3.UP, -PI / 2), Vector3.ZERO), t * 0.45, Vector3(0, 0.08, 0))
	await wait(t * 0.5)
	game.sound("package_place")
	pkg.reparent(bp.shown(), true)
	var tw := create_tween()
	tw.tween_property(pkg, "position", inside, t * 0.35 / time_scale)
	await wait(t * 0.4)
	on_packed.call()
	a.set_hand_goals(a.hand_goals[0], null)
	await wait(t * 0.1)
	pkg.queue_free()
	await put_on_bag()
	end()

## Leave at door: out of the bag (or from the hands) and down onto `spot` (world), then the
## photo. on_down() is called when it is down (the payout follows inside it).
func leave(pkg: Node3D, from_bag: bool, slot: String, spot: Transform3D, on_down: Callable) -> void:
	begin("leave", spot.origin)
	if clip_mode():
		await leave_clips(pkg, from_bag, spot, func(at: Vector3) -> bool: return game.drop_zone != null and game.drop_zone.contains(at), on_down)
		return
	var fp := not third_person()
	var a := avatar()
	if from_bag:
		if fp:
			game.bag_rig.take_off()
			game.sound("bag_zip")
			await wait(0.5)
			role = "bag_take"
			step_started.emit("bag_take")
			game.bag_rig.show_contents(pkg, slot)
			await wait(0.4)
			pkg = game.bag_rig.take_out()
			game.world.add_child(pkg)
			pkg.global_transform = pkg.get_meta("from")
		else:
			await take_off_bag()
			pkg = await take_item(pkg, slot)
	elif not fp:
		adopt(pkg)
		hands(side_marker(pkg, -1), side_marker(pkg, 1))
	# PlaceDown: onto the marked area.
	var t := play("place_down")
	if fp:
		var at := pkg.global_transform
		if pkg.get_parent() != game.world: pkg.reparent(game.world, true)
		pkg.global_transform = at
		var tw := create_tween()
		tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
		tw.tween_property(pkg, "global_transform", spot, t * 0.8 / time_scale)
	else:
		var local_spot := a.global_transform.affine_inverse() * spot
		swing(pkg, local_spot, t * 0.8, Vector3(0, 0.12, -0.05))
	await wait(t * 0.82)
	game.sound("package_drop")
	if is_instance_valid(pkg):
		pkg.reparent(game.world, true)
	if not fp:
		a.set_hand_goals(a.hand_goals[0] if from_bag else null, null)
		if not from_bag: a.hand_goal_weight = 0.0
	await wait(t * 0.18)
	# Proof photo.
	role = "photo"
	step_started.emit("photo")
	on_down.call(pkg)
	await wait(float(TIMES.photo))
	if from_bag:
		if fp:
			game.bag_rig.put_on()
			game.sound("bag_zip")
			await wait(0.5)
		else:
			await put_on_bag()
	end()

## Meet at door: out of the bag (or from the hands) into the customer's hands. on_handed(pkg)
## is called as they take it.
func meet(pkg: Node3D, from_bag: bool, slot: String, customer: Node3D, on_handed: Callable) -> void:
	var toward := customer.global_position if is_instance_valid(customer) else player().global_position - player().global_basis.z
	begin("meet", toward)
	if clip_mode():
		await meet_clips(pkg, from_bag, customer, toward, on_handed)
		return
	var fp := not third_person()
	var a := avatar()
	if from_bag:
		if fp:
			# First person: the bag comes round and the package lifts out towards the customer.
			role = "bag_take_off"
			step_started.emit("bag_take_off")
			game.bag_rig.take_off()
			game.sound("bag_zip")
			await wait(0.45)
			role = "bag_take"
			step_started.emit("bag_take")
			game.bag_rig.show_contents(pkg, slot)
			await wait(0.35)
			role = "handover"
			step_started.emit("handover")
			var node: Node3D = game.bag_rig.take_out()
			if node:
				game.world.add_child(node)
				node.global_transform = node.get_meta("from")
				var tw := create_tween()
				tw.tween_property(node, "global_position", toward + Vector3(0, 1.0, 0), 0.5 / time_scale)
			await wait(0.5)
			on_handed.call(node)
			game.bag_rig.put_on()
			game.sound("bag_zip")
			await wait(0.5)
			end()
			return
		await take_off_bag()
		pkg = await take_item(pkg, slot)
	elif fp:
		role = "handover"
		step_started.emit("handover")
		await wait(0.5)
		var at := pkg.global_transform
		pkg.reparent(game.world, false)
		pkg.global_transform = at
		on_handed.call(pkg)
		await wait(0.4)
		end()
		return
	else:
		adopt(pkg)
		hands(side_marker(pkg, -1), side_marker(pkg, 1))
	# Handover: held out towards the customer, who takes it.
	var t := play("handover")
	var to_customer := toward + Vector3(0, 1.0, 0)
	var reach := a.global_transform.affine_inverse() * to_customer
	var out_xf := Transform3D(Basis.IDENTITY, Vector3(0.05, 1.08, maxf(reach.z * 0.55, -0.62)))
	swing(pkg, out_xf, t * 0.6, Vector3(0, 0.05, 0))
	await wait(t * 0.65)
	game.sound("package_place")
	if is_instance_valid(pkg): pkg.reparent(game.world, true)
	a.set_hand_goals(a.hand_goals[0] if from_bag else null, null)
	if not from_bag: a.hand_goal_weight = 0.0
	on_handed.call(pkg)
	await wait(t * 0.35)
	if from_bag: await put_on_bag()
	end()

## Bag_TakeItem: the package comes out of the open bag into the right hand. Returns it.
func take_item(pkg: Node3D, slot: String) -> Node3D:
	var t := play("bag_take")
	var a := avatar()
	var bp := a.backpack
	bp.open(true)
	var inside := compartment(slot)
	bp.shown().add_child(pkg)
	pkg.transform = Transform3D(Basis(Vector3.UP, -PI / 2), inside)
	pkg.visible = true
	var right := side_marker(pkg, 1)
	a.set_hand_goals(a.hand_goals[0], right)
	var tw := create_tween()
	tw.tween_property(pkg, "position", inside + Vector3(0, 0.02, 0.34), t * 0.4 / time_scale)
	await wait(t * 0.42)
	pkg.reparent(a, true)
	swing(pkg, ITEM_RIGHT, t * 0.5, Vector3(0, 0.06, 0))
	await wait(t * 0.58)
	bp.open(false)
	return pkg
