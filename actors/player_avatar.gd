class_name PlayerAvatar
extends Node3D
## The courier's visible body (third person), driven by CourierPlayer.
##
## Body: assets/player/courier.glb once its contract assets/player/clips.json is published
## (COURIER_CLIPS roles, overridable there), otherwise the placeholder townsperson
## (casual_male_tshirt) animated with the UAL library. Everything below reads `clips` (role ->
## clip, ground speed, foot contact phases; measured from the clip when not given), so swapping
## the body is the BODY_SCENE constant plus its clips.json.
##
## AnimationTree (manual advance in the physics tick) state machine:
##   Move      idle <-> locomotion; locomotion = walk / jog / sprint on a normalised 1 s timeline
##             (left-foot contact at phase 0), blended by speed and played at
##             ground speed / blended stride so the planted foot does not slide; a reversed walk
##             for backing up in first person; an upper-body carry layer while holding an order.
##   JumpStart take-off (started by the real jump impulse), Air (falling loop), Land (impact-scaled).
##   Bike      seated base pose; PlayerBodyIK puts the hips on the saddle, hands on the grips and
##             the balls of the feet on the pedals of the turning crank.
## Movement feel: the body turns towards the direction of travel at a limited rate, leans into
## turns and with acceleration; turn-in-place when standing and the view swings past ~70 degrees;
## the feet are kept on the ground (ray to the walking surface + measured sole lift of the clip).

const BODY_SCENE := "res://assets/player/courier.glb"
const BODY_CLIPS := "res://assets/player/clips.json"
static var contract_path := BODY_CLIPS
## Placeholder until courier.glb exists: a realistic townsperson body + the UAL clip library.
const PLACEHOLDER_SCENE := "res://assets/sketchup/people/casual_male_tshirt.glb"
const PLACEHOLDER_LIBRARIES := ["res://assets/animations/ual/ual_standard.glb", "res://assets/animations/ual/ual_npc.glb"]

## Clip roles. speed: ground speed (m/s) the clip covers at speed_scale 1 on a body of scale 1
## (planted-foot speed, measured); phase / right: left / right foot contact as a fraction of the
## cycle; offset: seconds skipped at the start.
var clips := {
	"idle": {"name": "Idle"},
	"walk": {"name": "Walk", "speed": 1.101, "phase": 0.071, "right": 0.571},
	"jog": {"name": "Jog_Fwd", "speed": 5.878, "phase": 0.042, "right": 0.529},
	"sprint": {"name": "Sprint", "speed": 8.965, "phase": 0.054, "right": 0.554},
	"jump_start": {"name": "Jump_Start", "offset": 0.1},
	"jump_air": {"name": "Jump"},
	"jump_land": {"name": "Jump_Land", "offset": 0.03},
	"bike": {"name": "Driving"},
	"carry": {"name": "Idle_Carry"},
}
## The courier's own clips (assets/player/courier.glb: the MPFB v3 courier, tools/prepare_courier_v3.py,
## measured on that rig): natural procedural gaits - Walk 1.25 m/s for Ctrl, Run 3.8 m/s for the
## 3.5 m/s run (the "jog" role), Sprint 5.7 m/s for Shift - a real walk backwards and a seated bike
## pose. Speeds come from clips.json (by clip name); foot contact phases are measured at load.
const COURIER_CLIPS := {
	"idle": {"name": "Idle"},
	"walk": {"name": "Walk"},
	"walk_back": {"name": "Walk_Back"},
	"jog": {"name": "Run"},
	"sprint": {"name": "Sprint"},
	"jump_start": {"name": "Jump_Start", "offset": 0.42},
	"jump_air": {"name": "Jump"},
	"jump_land": {"name": "Jump_Land", "offset": 0.03},
	"bike": {"name": "Bike_Seated"},
	"carry": {"name": "Carry_Idle"},
	"carry_walk": {"name": "Carry_Walk"},
	"turn_left": {"name": "Turn_L_90", "yaw": 1.5708, "done": 0.85},
	"turn_right": {"name": "Turn_R_90", "yaw": -1.5708, "done": 0.85},
	# One-shot courier actions (CourierSequence); until the clips exist the sequence poses the
	# arms with IK (placeholder) instead.
	"pick_up": {"name": "PickUp"},
	"bag_take_off": {"name": "Bag_TakeOff"},
	"bag_hold": {"name": "Bag_Hold"},
	"bag_pack": {"name": "Bag_PackItem"},
	"bag_take": {"name": "Bag_TakeItem"},
	"bag_put_on": {"name": "Bag_PutOn"},
	"bag_put_on_holding": {"name": "Bag_PutOn_Holding"},
	"bag_strap_right": {"name": "Bag_StrapRight"},
	"handover": {"name": "Handover"},
	"place_down": {"name": "PlaceDown"},
	# A real fall lands deep (Land_Hard); getting on / off the bicycle are authored in bike space
	# (root = bike origin), played in place at MOUNT_RATE.
	"land_hard": {"name": "Land_Hard", "offset": 0.03},
	"bike_mount": {"name": "Bike_Mount"},
	"bike_dismount": {"name": "Bike_Dismount"},
	# Gestures (play_gesture): at the door, eating / drinking, greeting, idle fidgets.
	"knock_door": {"name": "Knock_Door"},
	"doorbell": {"name": "Press_Doorbell"},
	"eat_drink": {"name": "Eat_Drink"},
	"wave": {"name": "Wave"},
	"nod": {"name": "Nod_Yes"},
	"idle_look": {"name": "Idle_Look"},
	"idle_shift": {"name": "Idle_Shift"},
	"idle_fold": {"name": "Idle_FoldArms"},
}
## Getting on / off the bicycle: the clips play this much faster than authored (2.4 s / 2.2 s).
const MOUNT_RATE := 1.6
## Standing idle this long (s) starts a fidget (look round, shift weight, fold arms).
const FIDGET_AFTER := 9.0
const FIDGETS := [["idle_look", 7.5], ["idle_shift", 7.5], ["idle_fold", 5.0]]
## Action roles CourierSequence can play as one-shots.
const ACTION_ROLES := ["pick_up", "bag_take_off", "bag_hold", "bag_pack", "bag_take", "bag_put_on", "handover", "place_down"]
## Body facing correction (the retargeted bodies face +Z; the game faces -Z) and scale.
var body_yaw := PI
## Rig bone names for the humanoid-profile names PlayerBodyIK uses (only where they differ).
var bone_map := {}
## The bike clip is authored in bike space (hips on the saddle, trunk leaned, hands on the
## grips): the IK then only follows the steering and the turning pedals.
var bike_authored := false
var bike_hips := Vector3.ZERO
var anim_root: Node
var turn_from := 0.0
var turn_role := ""
var body_scale := 1.0
## Hip joint above the saddle contact (m) and ahead of it, measured on the seated pose.
var seat_hip_height := 0.135
var seat_hip_forward := 0.02
## Ball of the foot above the pedal axle (sole + pedal platform).
var pedal_ball_height := 0.065

## Gait thresholds (m/s, from the clips' own speeds): pure walk below walk_top, walk->jog up
## to jog_full, jog->sprint from sprint_from to sprint_full.
var walk_top := 1.6
var jog_full := 5.6
var sprint_from := 5.9
var sprint_full := 8.5
const ARM_BONES := ["LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
	"LeftForeArm", "RightForeArm", "Thumb", "Index", "Middle", "Ring", "Little"]

var player: CourierPlayer
var body: Node3D
var skeleton: Skeleton3D
var tree: AnimationTree
var playback: AnimationNodeStateMachinePlayback
var ik: PlayerBodyIK
var library: AnimationLibrary
var ready_ok := false
var placeholder := true

var state := "Move"
var facing := 0.0             ## world yaw the body faces (radians, Godot yaw; body forward = -Z)
var yaw_rate := 0.0
var roll := 0.0
var pitch_lean := 0.0
var _last_hv := Vector2.ZERO
var move_amount := 0.0
var gait_a := 0.0
var gait_b := 0.0
var gait_rate := 1.0
var gait_phase := 0.0         ## normalised locomotion phase (0 = left foot contact)
var back_amount := 0.0
var carry_amount := 0.0
var turning := false
var _turn_wait := 0.0
var air_time := 0.0
var state_time := 0.0
var land_amount := 1.0
var ground_offset := 0.0      ## smoothed visual floor correction (m)
var sole_lift := 0.0          ## filtered lowest-sole height of the clip (m)
var _ground_y := 0.0
var pelvis_drop := 0.0        ## hips lowered so both feet reach uneven ground when standing
var _jump_queued := false
## Mount transition: 0 standing, 1 seated; mount_from = body transform when it began.
var seat_blend := 0.0
var mount_from := Transform3D.IDENTITY
var mount_t := 1.0
var foot_down := 0.0
var view_first_person := false
var footsteps: Array[Vector3] = []
var step_count := 0
var _visible_mode := -1
## The bag on the back (WornBackpack): the delivery bag or plain backpack once owned.
var backpack: WornBackpack
## Courier actions (CourierSequence): the body turns to face_goal (world yaw, NAN = free) and the
## hands go to hand_goals (markers: origin = palm centre, -Z = fingers, -Y = palm normal) with
## hand_goal_weight; the playing one-shot clip role (or "").
var face_goal := NAN
var hand_goals: Array[Node3D] = [null, null]
var hand_goal_weight := 0.0
var action_role := ""
var _action_clip: AnimationNodeAnimation

func setup(owner_player: CourierPlayer) -> void:
	player = owner_player
	name = "Avatar"
	top_level = true
	if not load_body(): return
	add_child(body)
	body.rotation.y = body_yaw
	body.scale = Vector3.ONE * body_scale
	for gi: GeometryInstance3D in body.find_children("*", "GeometryInstance3D", true, false):
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		# Keep scene-wide static batching away from the skinned body (see LivingAssets).
		var keep := Node.new()
		keep.name = "Skinned"
		gi.add_child(keep)
	skeleton = body.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	skeleton.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	ik = PlayerBodyIK.new()
	ik.name = "PlayerBodyIK"
	for key: String in ik.names:
		if bone_map.has(str(ik.names[key])): ik.names[key] = bone_map[str(ik.names[key])]
	skeleton.add_child(ik)
	build_tree()
	backpack = WornBackpack.new()
	add_child(backpack)
	backpack.setup(self)
	ready_ok = true
	facing = player.global_rotation.y
	global_transform = Transform3D(Basis(Vector3.UP, facing), player.global_position)

## The courier body when it exists, else the placeholder. Returns false if neither loads.
func load_body() -> bool:
	library = AnimationLibrary.new()
	# The courier is used once its contract (clips.json) is published next to the model; until
	# then (or if the model is missing) the placeholder body keeps the game playable.
	var contract := read_contract()
	var scene_path := str(contract.get("scene", contract.get("model", BODY_SCENE)))
	if not contract.is_empty() and ResourceLoader.exists(scene_path):
		clips = COURIER_CLIPS.duplicate(true)
		apply_contract(contract)
		var scene: Node3D = (load(scene_path) as PackedScene).instantiate()
		var lib_path := str(contract.get("library", ""))
		if lib_path != "" and ResourceLoader.exists(lib_path):
			var shared := load(lib_path) as AnimationLibrary
			for clip_name in shared.get_animation_list(): library.add_animation(clip_name, shared.get_animation(clip_name))
		var wanted_root: Node = scene
		for ap: AnimationPlayer in scene.find_children("*", "AnimationPlayer", true, false):
			if library.get_animation_list().is_empty():
				for lib_name in ap.get_animation_library_list():
					var lib := ap.get_animation_library(lib_name)
					for clip_name in lib.get_animation_list():
						if not library.has_animation(clip_name): library.add_animation(clip_name, lib.get_animation(clip_name))
			if ap.get_parent() == scene and ap.root_node != NodePath(""): wanted_root = ap.get_node_or_null(ap.root_node)
			ap.get_parent().remove_child(ap)
			ap.free()
		# Tracks are "%GeneralSkeleton:<Bone>": they resolve from the scene that owns the skeleton.
		anim_root = wanted_root if wanted_root != null else scene.get_node_or_null("Model")
		body = scene
		placeholder = false
	elif ResourceLoader.exists(PLACEHOLDER_SCENE):
		body = (load(PLACEHOLDER_SCENE) as PackedScene).instantiate()
		var wanted := {}
		for role: String in clips: wanted[str((clips[role] as Dictionary).name)] = true
		for path: String in PLACEHOLDER_LIBRARIES:
			if not ResourceLoader.exists(path): continue
			var source: Node = (load(path) as PackedScene).instantiate()
			var ap := source.find_child("AnimationPlayer", true, false) as AnimationPlayer
			var full := ap.get_animation_library("")
			for clip in full.get_animation_list():
				if wanted.has(str(clip)) and not library.has_animation(clip): library.add_animation(clip, full.get_animation(clip))
			source.free()
	else:
		return false
	body.name = "Body"
	return true

## clips.json next to courier.glb: {"scene": path, "clips": {role: {"name", "speed", "phase",
## "right", "offset"}}, "facing": "+Z"|"-Z", "scale", "seat_hip_height", "pedal_ball_height",
## "bones": {profile bone: rig bone}}. Roles may also map straight to a clip name.
func read_contract() -> Dictionary:
	if not FileAccess.file_exists(contract_path): return {}
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(contract_path))
	return data if data is Dictionary else {}

func apply_contract(d: Dictionary) -> void:
	# Roles come from "roles", or from "clips" when it is keyed by role (idle, walk, jog ...).
	var roles: Dictionary = d.get("roles", {}) if d.get("roles", null) is Dictionary else {}
	if roles.is_empty() and d.get("clips", null) is Dictionary:
		for key: String in (d.clips as Dictionary):
			if clips.has(key) or key in ["walk_back"]: roles[key] = (d.clips as Dictionary)[key]
	for role: String in roles:
		var v: Variant = roles[role]
		var entry: Dictionary = (clips.get(role, {}) as Dictionary).duplicate()
		if v is String: entry["name"] = v
		elif v is Dictionary:
			for k: String in (v as Dictionary): entry[k] = (v as Dictionary)[k]
		clips[role] = entry
	var facing_text := str(d.get("facing", "+Z"))
	if facing_text == "-Z" or facing_text.contains("root faces -Z"): body_yaw = 0.0
	# Ground speeds published by clip name.
	if d.get("clips", null) is Dictionary:
		var by_name: Dictionary = d.clips
		for role: String in clips:
			var entry: Dictionary = clips[role]
			var info: Variant = by_name.get(str(entry.get("name", "")), null)
			if info is Dictionary and (info as Dictionary).has("speed"): entry["speed"] = float((info as Dictionary).speed)
	if d.get("bike", null) is Dictionary and (d.bike as Dictionary).get("hips", null) is Array:
		var h: Array = (d.bike as Dictionary).hips
		bike_hips = Vector3(float(h[0]), float(h[1]), float(h[2]))
		bike_authored = true
	body_scale = float(d.get("scale", body_scale))
	seat_hip_height = float(d.get("seat_hip_height", seat_hip_height))
	seat_hip_forward = float(d.get("seat_hip_forward", seat_hip_forward))
	pedal_ball_height = float(d.get("pedal_ball_height", pedal_ball_height))
	if d.get("bones", null) is Dictionary:
		for profile: String in (d.bones as Dictionary): bone_map[profile] = str((d.bones as Dictionary)[profile])

func clip(role: String) -> String:
	return str((clips.get(role, {}) as Dictionary).get("name", ""))

func has_clip(role: String) -> bool:
	return library.has_animation(clip(role))

func clip_value(role: String, key: String, fallback: float) -> float:
	return float((clips.get(role, {}) as Dictionary).get(key, fallback))

## Distance covered per locomotion cycle by a clip at this body's scale.
func stride(role: String) -> float:
	if not has_clip(role): return 1.0
	return clip_value(role, "speed", 1.0) * library.get_animation(clip(role)).length * body_scale

func anim_node(role: String, normalised: bool = false, backward: bool = false) -> AnimationNodeAnimation:
	var node := AnimationNodeAnimation.new()
	var name_ := clip(role) if has_clip(role) else clip("idle")
	node.animation = StringName(name_)
	if not _role_nodes.has(role): _role_nodes[role] = []
	(_role_nodes[role] as Array).append(node)
	if not library.has_animation(name_): return node
	var a := library.get_animation(name_)
	var offset := clip_value(role, "offset", 0.0)
	if normalised:
		# Every locomotion clip on one 1 s timeline, left foot down at 0: blends stay in phase.
		node.use_custom_timeline = true
		node.timeline_length = 1.0
		node.stretch_time_scale = true
		node.start_offset = clip_value(role, "phase", 0.0) * a.length
		node.loop_mode = Animation.LOOP_LINEAR
	elif offset > 0.0:
		node.use_custom_timeline = true
		node.timeline_length = maxf(0.05, a.length - offset)
		node.stretch_time_scale = false
		node.start_offset = offset
		node.loop_mode = a.loop_mode
	if backward: node.play_mode = AnimationNodeAnimation.PLAY_MODE_BACKWARD
	return node

func build_tree() -> void:
	for role in ["idle", "walk", "walk_back", "jog", "sprint", "jump_air", "bike", "carry", "carry_walk"]:
		if has_clip(role): library.get_animation(clip(role)).loop_mode = Animation.LOOP_LINEAR
	for role in ["walk", "walk_back", "jog", "sprint"]:
		if has_clip(role) and not (clips[role] as Dictionary).has("phase"): measure_clip(role)
	# Gait thresholds from the clips: walk up to ~1.45x its own pace, the jog clip pure around
	# its natural speed, then into the sprint clip.
	var walk_speed := clip_value("walk", "speed", 1.1) * body_scale
	var jog_speed := clip_value("jog", "speed", 3.0) * body_scale
	walk_top = walk_speed * 1.45
	jog_full = maxf(walk_top + 0.5, jog_speed * 0.95)
	sprint_from = maxf(jog_full + 0.1, jog_speed)
	sprint_full = maxf(sprint_from + 0.5, clip_value("sprint", "speed", 8.0) * body_scale * 0.95)
	tree = AnimationTree.new()
	tree.name = "AnimationTree"
	add_child(tree)
	tree.add_animation_library("", library)
	tree.root_node = tree.get_path_to(anim_root if anim_root != null else body)
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var move := AnimationNodeBlendTree.new()
	move.add_node("idle", anim_node("idle"), Vector2(0, 0))
	move.add_node("walk", anim_node("walk", true), Vector2(0, 150))
	move.add_node("jog", anim_node("jog", true), Vector2(0, 300))
	move.add_node("sprint", anim_node("sprint", true), Vector2(0, 450))
	# Backing up: the body's own walk-backwards clip, else the walk played in reverse.
	move.add_node("back", anim_node("walk_back", true) if has_clip("walk_back") else anim_node("walk", true, true), Vector2(0, 600))
	# Carrying by hand: Carry_Idle standing, Carry_Walk moving (arms only), when the body has them.
	if has_clip("carry_walk"):
		var carry_gait := AnimationNodeBlend2.new()
		carry_gait.sync = true
		move.add_node("carry_idle", anim_node("carry"), Vector2(-200, 750))
		move.add_node("carry_walk", anim_node("carry_walk"), Vector2(-200, 850))
		move.add_node("carry_pose", carry_gait, Vector2(0, 750))
		move.connect_node("carry_pose", 0, "carry_idle")
		move.connect_node("carry_pose", 1, "carry_walk")
	else:
		move.add_node("carry_pose", anim_node("carry"), Vector2(0, 750))
	for blend_name in ["gait1", "gait2", "backward", "moving"]:
		var b := AnimationNodeBlend2.new()
		b.sync = true
		move.add_node(blend_name, b)
	move.add_node("rate", AnimationNodeTimeScale.new())
	move.add_node("back_rate", AnimationNodeTimeScale.new())
	var carry := AnimationNodeBlend2.new()
	carry.filter_enabled = true
	if has_clip("carry"):
		var a := library.get_animation(clip("carry"))
		for t in range(a.get_track_count()):
			var path := a.track_get_path(t)
			var bone := str(path).get_slice(":", 1)
			for key: String in ARM_BONES:
				if bone.contains(key): carry.set_filter_path(path, true)
	move.add_node("carry", carry)
	move.connect_node("gait1", 0, "walk")
	move.connect_node("gait1", 1, "jog")
	move.connect_node("gait2", 0, "gait1")
	move.connect_node("gait2", 1, "sprint")
	move.connect_node("rate", 0, "gait2")
	move.connect_node("back_rate", 0, "back")
	move.connect_node("backward", 0, "rate")
	move.connect_node("backward", 1, "back_rate")
	move.connect_node("moving", 0, "idle")
	move.connect_node("moving", 1, "backward")
	move.connect_node("carry", 0, "moving")
	move.connect_node("carry", 1, "carry_pose")
	# Courier actions (bag off / pack / take out / put on, hand over, place down) over the whole
	# body: the clip's time is set every tick (action_time), so the bag / package tracks published
	# with each clip line up frame for frame, and chained clips follow each other without a fade.
	var action := AnimationNodeBlend2.new()
	move.add_node("action", action, Vector2(400, 300))
	_action_clip = AnimationNodeAnimation.new()
	_action_clip.animation = StringName(clip("idle"))
	move.add_node("action_clip", _action_clip, Vector2(0, 900))
	move.add_node("action_seek", AnimationNodeTimeSeek.new(), Vector2(200, 900))
	move.connect_node("action_seek", 0, "action_clip")
	move.connect_node("action", 0, "carry")
	move.connect_node("action", 1, "action_seek")
	move.connect_node("output", 0, "action")
	var land := AnimationNodeBlendTree.new()
	land.add_node("idle", anim_node("idle"))
	land.add_node("land", anim_node("jump_land"))
	land.add_node("speed", AnimationNodeTimeScale.new())
	land.add_node("amount", AnimationNodeBlend2.new())
	# A real fall: the deep-knee Land_Hard instead of the hop landing.
	land.add_node("hard", anim_node("land_hard" if has_clip("land_hard") else "jump_land"))
	land.add_node("which", AnimationNodeBlend2.new())
	land.connect_node("which", 0, "land")
	land.connect_node("which", 1, "hard")
	land.connect_node("speed", 0, "which")
	land.connect_node("amount", 0, "idle")
	land.connect_node("amount", 1, "speed")
	land.connect_node("output", 0, "amount")
	var jump := AnimationNodeBlendTree.new()
	jump.add_node("clip", anim_node("jump_start"))
	jump.add_node("speed", AnimationNodeTimeScale.new())
	jump.connect_node("speed", 0, "clip")
	jump.connect_node("output", 0, "speed")
	var sm := AnimationNodeStateMachine.new()
	sm.add_node("Move", move, Vector2(200, 100))
	sm.add_node("JumpStart", jump, Vector2(400, 0))
	sm.add_node("Air", anim_node("jump_air"), Vector2(600, 100))
	sm.add_node("Land", land, Vector2(400, 200))
	sm.add_node("Bike", anim_node("bike"), Vector2(200, 300))
	for turn in ["turn_left", "turn_right"]:
		if has_clip(turn):
			library.get_animation(clip(turn)).loop_mode = Animation.LOOP_NONE
			sm.add_node("Turn_" + turn, anim_node(turn), Vector2(0, 200))
	for pair: Array in [["BikeMount", "bike_mount"], ["BikeDismount", "bike_dismount"]]:
		if not has_clip(pair[1]): continue
		library.get_animation(clip(pair[1])).loop_mode = Animation.LOOP_NONE
		var bt := AnimationNodeBlendTree.new()
		bt.add_node("clip", anim_node(pair[1]))
		bt.add_node("speed", AnimationNodeTimeScale.new())
		bt.connect_node("speed", 0, "clip")
		bt.connect_node("output", 0, "speed")
		sm.add_node(pair[0], bt, Vector2(200, 400))
	var start := AnimationNodeStateMachineTransition.new()
	start.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
	sm.add_transition("Start", "Move", start)
	var fades := {"Move>JumpStart": 0.08, "Move>Air": 0.25, "JumpStart>Air": 0.3, "JumpStart>Land": 0.08, "Air>Land": 0.08,
		"Land>Move": 0.25, "Land>JumpStart": 0.08, "Land>Air": 0.2, "JumpStart>Move": 0.2, "Air>Move": 0.15,
		"Move>Bike": 0.4, "Bike>Move": 0.4, "Land>Bike": 0.3, "Air>Bike": 0.3, "JumpStart>Bike": 0.3}
	for turn in ["turn_left", "turn_right"]:
		if has_clip(turn):
			for pair: Array in [["Move", 0.18], ["JumpStart", 0.08], ["Air", 0.2], ["Bike", 0.3]]:
				fades["Turn_%s>%s" % [turn, pair[0]]] = pair[1]
			fades["Move>Turn_" + turn] = 0.18
	if has_clip("bike_mount"):
		for key: String in ["Move>BikeMount", "Land>BikeMount", "BikeMount>Move", "BikeDismount>BikeMount"]: fades[key] = 0.2
		for t: String in ["turn_left", "turn_right"]:
			if has_clip(t): fades["Turn_%s>BikeMount" % t] = 0.2
		fades["BikeMount>Bike"] = 0.25
	if has_clip("bike_dismount"):
		for key: String in ["Bike>BikeDismount", "BikeDismount>Bike", "BikeMount>BikeDismount"]: fades[key] = 0.2
		fades["BikeDismount>Move"] = 0.3
	for key: String in fades:
		var t := AnimationNodeStateMachineTransition.new()
		t.xfade_time = float(fades[key])
		t.switch_mode = AnimationNodeStateMachineTransition.SWITCH_MODE_IMMEDIATE
		t.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_ENABLED
		t.xfade_curve = ease_curve()
		sm.add_transition(key.get_slice(">", 0), key.get_slice(">", 1), t)
	tree.tree_root = sm
	tree.active = true
	playback = tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	tree.set("parameters/Move/rate/scale", 1.0)
	tree.set("parameters/Move/back_rate/scale", 1.0)
	tree.set("parameters/Land/speed/scale", 1.5)
	tree.set("parameters/JumpStart/speed/scale", 1.15)
	for st in ["BikeMount", "BikeDismount"]:
		if sm.has_node(st): tree.set("parameters/%s/speed/scale" % st, MOUNT_RATE)
	tree.advance(0.0)

## Ground speed and foot contact phases of a locomotion clip, measured on this skeleton: the
## lowest foot point's backward speed while planted, and when each foot touches down.
func measure_clip(role: String) -> void:
	var a := library.get_animation(clip(role))
	var keys := ["l_toes", "l_foot", "r_toes", "r_foot"]
	var ids_: Array[int] = []
	for k: String in keys: ids_.append(ik.bone_id(k))
	if ids_.has(-1): return
	var n := 60
	var frames: Array = []
	var lowest := INF
	for i in range(n + 1):
		skeleton.reset_bone_poses()
		for t in range(a.get_track_count()):
			var b := skeleton.find_bone(str(a.track_get_path(t)).get_slice(":", 1))
			if b < 0: continue
			match a.track_get_type(t):
				Animation.TYPE_POSITION_3D: skeleton.set_bone_pose_position(b, a.position_track_interpolate(t, a.length * i / n))
				Animation.TYPE_ROTATION_3D: skeleton.set_bone_pose_rotation(b, a.rotation_track_interpolate(t, a.length * i / n))
		var pts: Array[Vector3] = []
		for id in ids_: pts.append(ik.gpose(id).origin)
		frames.append(pts)
		for q in pts: lowest = minf(lowest, q.y)
	skeleton.reset_bone_poses()
	var speeds: Array[float] = []
	var contact := [-1.0, -1.0]
	for i in range(1, n + 1):
		var cur: Array = frames[i]
		var prev: Array = frames[i - 1]
		var lo := 0
		for k in range(4):
			if (cur[k] as Vector3).y < (cur[lo] as Vector3).y: lo = k
		if (cur[lo] as Vector3).y < lowest + 0.02:
			speeds.append(-((cur[lo] as Vector3).z - (prev[lo] as Vector3).z) / (a.length / n))
		for side in range(2):
			var now := minf((cur[side * 2] as Vector3).y, (cur[side * 2 + 1] as Vector3).y)
			var before := minf((prev[side * 2] as Vector3).y, (prev[side * 2 + 1] as Vector3).y)
			if contact[side] < 0.0 and now < lowest + 0.02 and before >= lowest + 0.02: contact[side] = float(i) / n
	if speeds.is_empty(): return
	speeds.sort()
	var entry: Dictionary = clips[role]
	if not entry.has("speed"): entry["speed"] = absf(speeds[speeds.size() / 2])
	entry["phase"] = maxf(float(contact[0]), 0.0)
	entry["right"] = float(contact[1]) if float(contact[1]) >= 0.0 else fposmod(float(entry.phase) + 0.5, 1.0)

static func ease_curve() -> Curve:
	var c := Curve.new()
	c.add_point(Vector2(0, 0), 0, 0)
	c.add_point(Vector2(1, 1), 0, 0)
	return c

func go(to: String) -> void:
	if state == to: return
	state = to
	state_time = 0.0
	if to == "Move": gait_phase = 0.0
	playback.travel(to)

# --- Events from the player -----------------------------------------------------------------

## The jump impulse was applied this tick.
func jumped() -> void:
	_jump_queued = true

## Mounting: the Bike_Mount clip in place on the bike (from where the body stands into its first
## frame over 0.25 s), else a blend from where the body stands to the saddle.
func begin_mount() -> void:
	end_gesture()
	mount_from = global_transform
	mount_t = 0.0
	dismount_clip_left = 0.0
	mount_clip_left = clip_seconds("bike_mount") if uses_mount_clips() else 0.0

## Getting on / off with the clips: game seconds left of each; the dismount plays where the bike
## stood when it began.
var mount_clip_left := 0.0
var dismount_clip_left := 0.0
var dismount_at := Transform3D.IDENTITY
var hard_landing := false

func clip_seconds(role: String) -> float:
	return library.get_animation(clip(role)).length / MOUNT_RATE if has_clip(role) else 0.0

## The mount / dismount clips are authored on the gray bicycle's saddle and bars: not for the
## scooter's floorboard or a car.
func uses_mount_clips() -> bool:
	return has_clip("bike_mount") and player.session != null and not ShopCatalog.is_car(player.session.active_vehicle) \
		and not player.bike_markers.is_empty() and not player.bike_markers.get("footboard", false)

## True while getting on or off: the courier waits (no pedalling, no walking away).
func mount_locked() -> bool:
	return mount_clip_left > 0.0 or dismount_clip_left > 0.0

func ik_off() -> void:
	ik.seat_weight = 0.0
	ik.look_weight = 0.0
	for side in range(2):
		ik.arm_weight[side] = 0.0
		ik.leg_weight[side] = 0.0

# --- Gestures: short clips outside CourierSequence (door, supplies, greeting, idle fidgets) ----

var gesture := ""
var _gesture_left := 0.0
var _gesture_faces := false
var _idle_for := 0.0
var _fidget_next := 0

## One clip on the action layer, turning to `yaw` first (NAN = keep facing); `hold` > 0 plays a
## looping clip that long. Ends at its end, or as soon as the courier moves, jumps, gets on the
## bike or a CourierSequence clip takes the layer. Returns the clip length (-1 when not played).
func play_gesture(role: String, yaw := NAN, hold := -1.0, item := "") -> float:
	if not ready_ok or player.busy or player.mounted or mount_locked() or not has_clip(role): return -1.0
	if action_role != "" and action_role != gesture: return -1.0
	var length := play_action(role)
	if length <= 0.0: return -1.0
	gesture = role
	_gesture_left = hold if hold > 0.0 else length
	_gesture_faces = not is_nan(yaw)
	if _gesture_faces: face_goal = yaw
	show_item(item)
	return length

func end_gesture() -> void:
	if gesture == "": return
	if action_role == gesture: stop_action()
	if _gesture_faces: face_goal = NAN
	gesture = ""
	_gesture_faces = false
	show_item("")

## A small item in the right hand for Eat_Drink: "water_bottle" or "energy_bar" ("" hides it).
var _hand_item: BoneAttachment3D
func show_item(kind: String) -> void:
	if _hand_item == null:
		if kind == "": return
		_hand_item = BoneAttachment3D.new()
		_hand_item.name = "HeldItem"
		_hand_item.bone_name = str(bone_map.get("RightHand", "RightHand"))
		skeleton.add_child(_hand_item)
		_hand_item.add_child(item_mesh("water_bottle"))
		_hand_item.add_child(item_mesh("energy_bar"))
	for c: Node3D in _hand_item.get_children(): c.visible = c.name == kind
	_hand_item.visible = kind != ""

## Hand-bone space (+Y along the hand to the fingers, palm towards -X on the right hand): the
## item sits across the palm, gripped by the fingers.
static func item_mesh(kind: String) -> Node3D:
	var root := Node3D.new()
	root.name = kind
	var body := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	if kind == "water_bottle":
		var c := CylinderMesh.new()
		c.top_radius = 0.032
		c.bottom_radius = 0.034
		c.height = 0.2
		body.mesh = c
		mat.albedo_color = Color(0.55, 0.78, 0.95, 0.75)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
		mat.roughness = 0.15
		var cap := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.016
		cm.bottom_radius = 0.018
		cm.height = 0.025
		cap.mesh = cm
		var capm := StandardMaterial3D.new()
		capm.albedo_color = Color(0.92, 0.94, 0.96)
		cap.material_override = capm
		cap.position = Vector3(0, 0.11, 0)
		body.add_child(cap)
	else:
		var b := BoxMesh.new()
		b.size = Vector3(0.035, 0.12, 0.016)
		body.mesh = b
		mat.albedo_color = Color(0.95, 0.55, 0.12)
		mat.roughness = 0.45
		mat.metallic = 0.3
	body.material_override = mat
	root.add_child(body)
	# Gripped across the palm: the item's long axis along the thumb (hand +Z), half way down the
	# fingers, just off the palm.
	root.transform = Transform3D(Basis(Vector3.RIGHT, PI / 2), Vector3(0.0, 0.075, 0.0))
	return root

func tick_gesture(delta: float, speed: float, grounded: bool, third: bool) -> void:
	if gesture != "":
		_idle_for = 0.0
		if action_role != gesture:
			gesture = ""                       # a CourierSequence clip took over (it owns face_goal now)
			_gesture_faces = false
			return
		_gesture_left -= delta
		if _gesture_left <= 0.0 or speed > 0.6 or player.busy or not grounded or state != "Move": end_gesture()
		return
	var idle := speed < 0.1 and grounded and state == "Move" and third and not player.busy and action_role == "" \
		and player.held_package() == null
	_idle_for = _idle_for + delta if idle else 0.0
	if _idle_for > FIDGET_AFTER:
		var f: Array = FIDGETS[_fidget_next % FIDGETS.size()]
		_fidget_next += 1
		_idle_for = -randf_range(4.0, 10.0)          # the next one a while after this one
		play_gesture(str(f[0]), NAN, float(f[1]))

## Play a courier action clip (ACTION_ROLES) once over the body. Returns its length (s), or
## -1.0 when the body has no such clip (the caller poses it procedurally instead).
func play_action(role: String) -> float:
	if not ready_ok or not has_clip(role) or _action_clip == null: return -1.0
	var name_ := worn_clip(clip(role))
	var a := library.get_animation(name_)
	action_loop = bool(contract_clip(name_).get("loop", false))
	a.loop_mode = Animation.LOOP_LINEAR if action_loop else Animation.LOOP_NONE
	_action_clip.animation = StringName(name_)
	action_role = role
	action_clip_name = name_
	action_time = 0.0
	action_length = a.length
	action_target = 1.0
	if state != "Move": go("Move")
	return a.length

func set_hand_goals(left: Node3D, right: Node3D) -> void:
	hand_goals[0] = left
	hand_goals[1] = right

## Back to normal animation (the action layer fades out).
func stop_action() -> void:
	action_role = ""
	action_target = 0.0

## Action layer per tick: the clip's time, its weight (0.2 s fades), held on its last frame.
var action_time := 0.0
var action_length := 0.0
var action_loop := false
var action_weight := 0.0
var action_target := 0.0
var action_clip_name := ""
func tick_action(delta: float) -> void:
	action_weight = move_toward(action_weight, action_target, delta / 0.2)
	if action_weight <= 0.0 and action_target <= 0.0:
		tree.set("parameters/Move/action/blend_amount", 0.0)
		return
	tree.set("parameters/Move/action_seek/seek_request", action_time)
	tree.set("parameters/Move/action/blend_amount", smoothstep(0.0, 1.0, action_weight))
	action_time += delta
	if action_loop and action_length > 0.0: action_time = fmod(action_time, action_length)
	else: action_time = minf(action_time, maxf(0.0, action_length - 0.001))

# --- Bag worn: the contract's arm variants (arms round the bag) ---------------------------------

var _role_nodes := {}          ## role -> [AnimationNodeAnimation] using that role's clip
var bag_worn := false
var _contract_cache: Dictionary = {}

## clips.json, read once.
func contract() -> Dictionary:
	if _contract_cache.is_empty(): _contract_cache = read_contract()
	return _contract_cache

## The clips.json entry of a clip by name ({} if none).
func contract_clip(clip_name: String) -> Dictionary:
	var by_name: Variant = contract().get("clips", {})
	if by_name is Dictionary and (by_name as Dictionary).get(clip_name, null) is Dictionary: return (by_name as Dictionary)[clip_name]
	return {}

## The clip to play for `clip_name` with the bag on the back: its "_Bag" variant when it has one.
func worn_clip(clip_name: String) -> String:
	if not bag_worn: return clip_name
	var v := str(_bag_variants().get(clip_name, ""))
	return v if v != "" and library.has_animation(v) else clip_name

var _variants: Dictionary = {}
func _bag_variants() -> Dictionary:
	if _variants.is_empty():
		var by_name: Variant = contract().get("clips", {})
		if by_name is Dictionary:
			for n: String in (by_name as Dictionary):
				var e: Variant = (by_name as Dictionary)[n]
				if e is Dictionary and (e as Dictionary).has("bag_variant_of"): _variants[str((e as Dictionary).bag_variant_of)] = n
		if library.has_animation("Bag_Worn_Idle"): _variants[clip("idle")] = "Bag_Worn_Idle"
		_variants["_"] = ""
	return _variants

## The bag goes on / comes off the back: locomotion, idle, jumps and turns switch to (or back
## from) their bag variants.
func set_bag_worn(on: bool) -> void:
	if on == bag_worn: return
	bag_worn = on
	for role: String in _role_nodes:
		var base := clip(role) if has_clip(role) else clip("idle")
		var want := worn_clip(base)
		if library.has_animation(want):
			var a := library.get_animation(want)
			var b := library.get_animation(base)
			a.loop_mode = b.loop_mode
		for node: AnimationNodeAnimation in _role_nodes[role]:
			node.animation = StringName(want)

## Contract package pose while carrying by hand (Carry_Idle's package_track, courier-root space).
func carry_local() -> Transform3D:
	var info := contract_clip("Carry_Idle")
	if info.get("package_track", null) is Array and not (info.package_track as Array).is_empty():
		return CourierSequence.track_xf(info.package_track, 0.0)
	return Transform3D(Basis.IDENTITY, Vector3(0, 1.0, -0.34))

## Re-apply the visibility mode (after nodes were added to the body).
func refresh_visibility() -> void:
	var mode := _visible_mode
	_visible_mode = -1
	if mode >= 0 and body != null: set_mode(mode)

## Dismounting: the Bike_Dismount clip in place on the bike, then a blend from where it ends to
## where the courier stands; else a blend from the saddle to standing beside the bike.
func begin_dismount() -> void:
	mount_from = global_transform
	mount_t = 0.0
	mount_clip_left = 0.0
	dismount_clip_left = clip_seconds("bike_dismount") if uses_mount_clips() else 0.0
	dismount_at = global_transform
	facing = player.global_rotation.y if dismount_clip_left <= 0.0 else global_rotation.y
	yaw_rate = 0.0

# --- Per tick -------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if not ready_ok or player == null or player.session == null: return
	tick(delta)

func tick(delta: float) -> void:
	state_time += delta
	mount_t = minf(1.0, mount_t + delta / 0.55)
	var in_car := player.mounted and ShopCatalog.is_car(player.session.active_vehicle)
	if in_car or (player.mounted and player.bike_markers.is_empty()):
		set_mode(2)
		return
	var on_bike := player.mounted and is_instance_valid(player.bicycle)
	seat_blend = move_toward(seat_blend, 1.0 if on_bike else 0.0, delta / 0.5)
	if on_bike: ride(delta)
	else: walk(delta)
	tick_action(delta)
	if action_weight > 0.0:
		# The action clip poses the arms and head itself.
		ik.look_weight *= 1.0 - action_weight
		for side in range(2): ik.arm_weight[side] = float(ik.arm_weight[side]) * (1.0 - action_weight)
	tree.advance(delta)

## Called every frame by the camera rig (also while the game is paused for the phone / bag).
func update_visibility() -> void:
	if not ready_ok: return
	if player.mounted and (player.bike_markers.is_empty() or player.session != null and ShopCatalog.is_car(player.session.active_vehicle)):
		set_mode(2)
		return
	var rig := player.view
	var fp_amount := 1.0 - (rig.eased() if rig != null else 1.0)
	var close := rig.closeness() if rig != null else 0.0
	# Shadow-only once the camera is near the eyes (V, phone, bag, a wall right behind), so it
	# never sees the inside of the head. (No partial fade: a see-through head shows its inside.)
	set_mode(1 if fp_amount > 0.6 or close > 0.6 else 0)

## 0 visible, 1 shadow only (first person), 2 hidden (in a car).
func set_mode(mode: int) -> void:
	if mode == _visible_mode: return
	_visible_mode = mode
	visible = mode != 2
	for gi: GeometryInstance3D in find_children("*", "GeometryInstance3D", true, false):
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if mode == 1 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON

# --- On foot ---------------------------------------------------------------------------------

func walk(delta: float) -> void:
	var p := player
	if dismount_clip_left > 0.0:
		# Getting off: the clip in place where the bike stands, then the usual blend to the courier.
		dismount_clip_left -= delta
		if state != "BikeDismount": go("BikeDismount")
		global_transform = dismount_at
		yaw_rate = 0.0
		ik_off()
		if dismount_clip_left <= 0.0:
			mount_from = global_transform
			mount_t = 0.0
			go("Move")
		return
	var hv := Vector2(p.velocity.x, p.velocity.z)
	var real := p.get_real_velocity()
	var speed := Vector2(real.x, real.z).length() if p.is_on_floor() else hv.length()
	var grounded := p.is_on_floor() or p.coyote_time > 0.0
	var aim_yaw := p.global_rotation.y
	var third := p.view == null or p.view.blend > 0.5
	tick_gesture(delta, speed, grounded, third)
	# Facing: towards the direction of travel; standing still it keeps its heading (third person)
	# or follows the view (first person); backing up in first person keeps facing the view.
	var target_yaw := facing
	var backing := false
	if speed > 0.25:
		var move_yaw := atan2(-hv.x, -hv.y)
		if not third and absf(angle_difference(aim_yaw, move_yaw)) > deg_to_rad(115.0):
			backing = true
			target_yaw = aim_yaw
		else:
			target_yaw = move_yaw
		turning = false
		_turn_wait = 0.0
	elif not is_nan(face_goal):
		# A courier action: face the shelf / the door / the customer.
		target_yaw = face_goal
		turning = false
		_turn_wait = 0.0
	elif p.busy:
		target_yaw = facing
	elif not third:
		target_yaw = aim_yaw
	else:
		var off := absf(angle_difference(facing, aim_yaw))
		if state.begins_with("Turn_"):
			target_yaw = facing
		elif turning:
			target_yaw = aim_yaw
			if off < deg_to_rad(6.0): turning = false
		elif off > deg_to_rad(70.0) and grounded and p.holding_view_still() and state == "Move":
			_turn_wait += delta
			if _turn_wait > 0.25:
				_turn_wait = 0.0
				# A real 90-degree step turn when the body has one, else a shuffle round.
				var role := "turn_left" if angle_difference(facing, aim_yaw) > 0.0 else "turn_right"
				if has_clip(role):
					turn_role = role
					turn_from = facing
					go("Turn_" + role)
				else:
					turning = true
		else:
			_turn_wait = 0.0
	# Limited, weighty turn rate: quick when slow, wider arcs at a sprint.
	var max_rate := lerpf(9.5, 5.0, clampf(speed / 6.0, 0.0, 1.0))
	if turning: max_rate = 3.6
	if not grounded: max_rate *= 0.35
	if state.begins_with("Turn_"):
		# Step turn: the clip turns the body in place; the root follows its yaw curve
		# (yaw * smoothstep(t / done)) so the feet stay planted, then idles.
		var info: Dictionary = clips[turn_role]
		var done := float(info.get("done", 0.85))
		var before_yaw := facing
		facing = wrapf(turn_from + float(info.get("yaw", 0.0)) * smoothstep(0.0, 1.0, minf(state_time + delta, done) / done), -PI, PI)
		yaw_rate = angle_difference(before_yaw, facing) / maxf(delta, 0.0001)
		if speed > 0.25 or state_time + delta >= done: go("Move")
		if absf(state_time - 0.3) < delta * 0.5 or absf(state_time - 0.6) < delta * 0.5: step(0)
	else:
		var diff := angle_difference(facing, target_yaw)
		var want_rate := clampf(diff * 9.0, -max_rate, max_rate)
		yaw_rate = move_toward(yaw_rate, want_rate, 55.0 * delta)
		if absf(diff) < absf(yaw_rate * delta): yaw_rate = diff / maxf(delta, 0.0001)
		facing = wrapf(facing + yaw_rate * delta, -PI, PI)
	# Lean into the turn (centripetal, softened and limited) and with acceleration.
	var accel := (hv.length() - _last_hv.length()) / maxf(delta, 0.0001)
	_last_hv = hv
	var want_roll := clampf(atan(speed * yaw_rate / 9.81) * 0.45, -0.2, 0.2) if grounded else 0.0
	roll = lerpf(roll, want_roll, 1.0 - exp(-8.0 * delta))
	pitch_lean = lerpf(pitch_lean, clampf(accel * 0.012, -0.07, 0.09) + clampf(speed * 0.008, 0.0, 0.05), 1.0 - exp(-6.0 * delta))
	# States.
	if state == "Bike": go("Move")
	if _jump_queued:
		_jump_queued = false
		go("JumpStart")
		air_time = 0.0
	if not p.is_on_floor():
		air_time += delta
		if state == "JumpStart" and (p.velocity.y < -0.5 or state_time > 0.55): go("Air")
		elif (state in ["Move", "Land"] or state.begins_with("Turn_")) and air_time > 0.18 and p.velocity.y < -1.5 and drop_below() > 0.45: go("Air")
	else:
		if state in ["Air", "JumpStart"] and (air_time > 0.12 or state == "Air"):
			# Impact-scaled landing: a hop dips lightly, a real fall crouches deep.
			land_amount = clampf(remap(p.last_fall_speed, 3.0, 9.0, 0.35, 1.0), 0.3, 1.0)
			if speed > 2.0: land_amount *= 0.5
			# A real fall (not a hop) standing or walking: the deep-knee hard landing.
			hard_landing = p.last_fall_speed > 7.5 and speed < 2.0 and has_clip("land_hard")
			tree.set("parameters/Land/which/blend_amount", 1.0 if hard_landing else 0.0)
			tree.set("parameters/Land/amount/blend_amount", land_amount)
			go("Land")
			step(0)
		elif state == "JumpStart" and state_time > 0.2: go("Move")
		elif state == "Land" and (state_time > (0.75 if hard_landing else 0.42) or (speed > 1.0 and state_time > 0.16)): go("Move")
		air_time = 0.0
	# Locomotion blend: gait by speed, playback at ground speed / blended stride.
	var turning_step := turning and speed < 0.25
	var want_move := clampf(speed / 0.45, 0.0, 1.0)
	if turning_step: want_move = 0.55
	move_amount = lerpf(move_amount, want_move, 1.0 - exp(-12.0 * delta))
	var a := smoothstep(walk_top, jog_full, speed)
	var b := smoothstep(sprint_from, sprint_full, speed) if has_clip("sprint") else 0.0
	gait_a = lerpf(gait_a, a, 1.0 - exp(-10.0 * delta))
	gait_b = lerpf(gait_b, b, 1.0 - exp(-10.0 * delta))
	var blended := blended_stride()
	gait_rate = maxf(speed, 0.0) / maxf(blended, 0.01)
	if turning_step: gait_rate = 0.9
	gait_rate = clampf(gait_rate, 0.55 if move_amount > 0.05 else 0.0, 3.0)
	back_amount = move_toward(back_amount, 1.0 if backing else 0.0, delta / 0.2)
	var back_rate := speed / maxf(absf(stride("walk_back" if has_clip("walk_back") else "walk")), 0.01)
	var holding := p.held_package() != null and (p.view == null or p.view.blend > 0.5)
	carry_amount = move_toward(carry_amount, 1.0 if holding else 0.0, delta / 0.25)
	tree.set("parameters/Move/moving/blend_amount", move_amount)
	tree.set("parameters/Move/gait1/blend_amount", gait_a)
	tree.set("parameters/Move/gait2/blend_amount", gait_b)
	tree.set("parameters/Move/rate/scale", gait_rate)
	tree.set("parameters/Move/back_rate/scale", maxf(back_rate, 0.5))
	tree.set("parameters/Move/backward/blend_amount", back_amount)
	tree.set("parameters/Move/carry/blend_amount", carry_amount)
	if has_clip("carry_walk"): tree.set("parameters/Move/carry_pose/blend_amount", move_amount)
	# Footsteps on the clip's foot contacts (phase 0 = left, `right` = right foot).
	if state == "Move" and move_amount > 0.4 and grounded:
		var rate_now := (back_rate if backing else gait_rate)
		var before := gait_phase
		gait_phase = fposmod(gait_phase + rate_now * delta, 1.0)
		var right := lerpf(clip_value("walk", "right", 0.5) - clip_value("walk", "phase", 0.0), clip_value("jog", "right", 0.5) - clip_value("jog", "phase", 0.0), gait_a)
		if crossed(before, gait_phase, 0.0): step(-1)
		if crossed(before, gait_phase, right): step(1)
	elif state == "Move":
		gait_phase = fposmod(gait_phase + gait_rate * delta, 1.0)
	# Body placement: on the walking surface under the body, sole lift of the clip removed.
	var mount_blend := smoothstep(0.0, 1.0, mount_t)
	var ground := p.global_position.y
	if grounded and state != "Air" and state != "JumpStart":
		var hit := surface_below()
		if not is_nan(hit) and absf(hit - ground) < 0.3: ground = hit
		_ground_y = ground if absf(_ground_y - ground) > 0.5 else lerpf(_ground_y, ground, 1.0 - exp(-(22.0 if ground < _ground_y else 14.0) * delta))
	else:
		_ground_y = p.global_position.y
	measure_sole(delta)
	var basis := Basis.from_euler(Vector3(-pitch_lean, facing, roll))
	var stand := Transform3D(basis, Vector3(p.global_position.x, _ground_y - sole_lift + pelvis_drop, p.global_position.z))
	global_transform = mount_from.interpolate_with(stand, mount_blend) if mount_t < 1.0 else stand
	var plant := clampf(1.0 - move_amount * 2.5, 0.0, 1.0) if grounded and (state == "Move" or state.begins_with("Turn_")) and not turning_step and mount_t >= 1.0 else 0.0
	plant_feet(delta, plant)
	# IK: head looks along the view (third person); hands onto a carried package.
	var look_w := 0.0
	if third and state in ["Move", "Land"]: look_w = lerpf(0.75, 0.35, clampf(speed / 5.0, 0.0, 1.0))
	ik.look_weight = lerpf(ik.look_weight, look_w, 1.0 - exp(-6.0 * delta))
	ik.look_dir = -p.camera.global_basis.z
	if p.busy:
		# Courier action: eyes on the hands (the bag / the package).
		var sum := Vector3.ZERO
		var n := 0
		for g: Node3D in hand_goals:
			if is_instance_valid(g):
				sum += g.global_position
				n += 1
		if n > 0:
			var head := global_position + Vector3.UP * 1.6 * body_scale
			ik.look_dir = (sum / float(n) - head).normalized()
			ik.look_weight = lerpf(ik.look_weight, 0.85, 1.0 - exp(-6.0 * delta))
	ik.look_pitch_limit = 0.55 if not p.busy else 0.8
	ik.head_level = 0.0
	ik.seat_weight = seat_blend * (1.0 - mount_blend) if mount_t < 1.0 else 0.0
	if mount_t < 1.0:
		for side in range(2): ik.leg_weight[side] = float(ik.leg_weight[side]) * (1.0 - mount_blend)
	carry_hands(delta, holding)

## Standing on steps, kerbs and slopes: each foot onto the surface under it (leg IK, sole along
## the surface) and the hips lowered so the lower foot can reach - no floating or sunk foot.
func plant_feet(delta: float, w: float) -> void:
	var drops: Array[float] = [0.0, 0.0]
	var targets: Array[Vector3] = [Vector3.ZERO, Vector3.ZERO]
	var normals: Array[Vector3] = [Vector3.UP, Vector3.UP]
	var ok := w > 0.01 and not ik.rest_global.is_empty()
	if ok:
		var to_world := skeleton.global_transform
		for side in range(2):
			var key := "l_toes" if side == 0 else "r_toes"
			var id := ik.bone_id(key)
			if id < 0:
				ok = false
				break
			var toes := to_world * ik.gpose(id).origin
			var rest_h := (ik.rest_global[key] as Transform3D).origin.y * body_scale
			var q := PhysicsRayQueryParameters3D.create(toes + Vector3(0, 0.45, 0), toes + Vector3(0, -0.45, 0), player.collision_mask)
			q.exclude = [player.get_rid()]
			var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
			if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
				ok = false
				break
			# How far this foot's ground is from where the clip puts the sole (+ up, - down).
			drops[side] = clampf((hit.position as Vector3).y + rest_h - toes.y, -0.3, 0.3)
			targets[side] = toes
			normals[side] = hit.normal
	var want_drop := minf(0.0, minf(drops[0], drops[1])) * w if ok else 0.0
	pelvis_drop = lerpf(pelvis_drop, want_drop, 1.0 - exp(-12.0 * delta))
	var fwd := Vector3(-sin(facing), 0, -cos(facing))
	for side in range(2):
		var lw := w if ok else 0.0
		ik.leg_weight[side] = lerpf(float(ik.leg_weight[side]), lw, 1.0 - exp(-14.0 * delta)) if lw > 0.0 or float(ik.leg_weight[side]) > 0.01 else 0.0
		if not ok: continue
		# The clip's toes were measured with the hips already lowered by the previous drop.
		ik.leg_target[side] = targets[side] + Vector3.UP * drops[side]
		var n: Vector3 = normals[side]
		ik.foot_forward[side] = (fwd - n * fwd.dot(n)).normalized()
		ik.foot_sole[side] = -n
		ik.knee_pole[side] = (fwd + Vector3.UP * 0.1).normalized()

## Distance per locomotion cycle of the current walk / jog / sprint blend.
func blended_stride() -> float:
	return (1.0 - gait_a) * (1.0 - gait_b) * stride("walk") + gait_a * (1.0 - gait_b) * stride("jog") + gait_b * stride("sprint")

static func crossed(before: float, after: float, mark: float) -> bool:
	mark = fposmod(mark, 1.0)
	if after >= before: return before < mark and after >= mark
	return before < mark or after >= mark

func step(side: int) -> void:
	step_count += 1
	var at := player.global_position
	if side != 0 and ik.solved.has("l_toes" if side < 0 else "r_toes"):
		at = ik.solved["l_toes" if side < 0 else "r_toes"]
	footsteps.append(at)
	if footsteps.size() > 8: footsteps.pop_front()

## Height of the walkable surface straight under the body (NAN if none near).
func surface_below() -> float:
	var from := player.global_position + Vector3(0, 0.45, 0)
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -0.85, 0), player.collision_mask)
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty() or (hit.normal as Vector3).y < 0.6: return NAN
	return (hit.position as Vector3).y

func drop_below() -> float:
	var from := player.global_position + Vector3(0, 0.2, 0)
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -3.0, 0), player.collision_mask)
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	return 3.0 if hit.is_empty() else from.y - 0.2 - (hit.position as Vector3).y

## Lowest sole point of the current pose above the body's floor (skeleton space, peak-hold
## filtered over the gait cycle so running flight phases do not pull the body down).
func measure_sole(delta: float) -> void:
	if state not in ["Move", "Land"] or ik.rest_global.is_empty():
		sole_lift = move_toward(sole_lift, 0.0, delta * 0.5)
		return
	var lift := INF
	for p in ["l_", "r_"]:
		for part in ["foot", "toes"]:
			var key: String = p + part
			var id := ik.bone_id(key)
			if id < 0: continue
			var now := ik.gpose(id).origin.y
			var rest := (ik.rest_global[key] as Transform3D).origin.y
			lift = minf(lift, (now - rest) * body_scale)
	if lift == INF: return
	lift = clampf(lift, -0.05, 0.12)
	sole_lift = lift if lift < sole_lift else lerpf(sole_lift, lift, 1.0 - exp(-2.5 * delta))

## Hands onto the sides of the package carried in front of the body (or onto the markers a
## courier action gives them).
func carry_hands(delta: float, holding: bool) -> void:
	if hand_goals[0] != null or hand_goals[1] != null or hand_goal_weight > 0.01:
		action_hands(delta)
		return
	var pkg := player.held_package()
	var w := carry_amount if holding and pkg != null else 0.0
	for side in range(2):
		ik.arm_weight[side] = lerpf(float(ik.arm_weight[side]), w, 1.0 - exp(-12.0 * delta)) if w > 0.0 or float(ik.arm_weight[side]) > 0.01 else 0.0
	if pkg == null or w <= 0.0: return
	var box := package_box(pkg)
	var right := global_basis.x.normalized()
	var fwd := -global_basis.z.normalized()
	var centre := pkg.global_transform * box.get_center()
	var half := box.size.x * 0.5 * pkg.global_basis.get_scale().x
	for side in range(2):
		var s := -1.0 if side == 0 else 1.0
		ik.arm_target[side] = centre + right * s * (half + 0.01) + Vector3(0, -box.size.y * 0.15, 0)
		ik.hand_fingers[side] = (fwd * 0.7 + Vector3.DOWN * 0.3 + right * s * -0.2).normalized()
		ik.hand_palm[side] = -right * s
		ik.elbow_pole[side] = (right * s * 0.6 + Vector3.DOWN * 0.8 - fwd * 0.2).normalized()

## Courier action hands: each hand to its marker (palm centre, fingers along -Z, palm normal -Y),
## faded by hand_goal_weight; a hand without a marker goes back to the clip.
func action_hands(delta: float) -> void:
	var right := global_basis.x.normalized()
	var fwd := -global_basis.z.normalized()
	for side in range(2):
		var goal: Node3D = hand_goals[side]
		var w := hand_goal_weight if is_instance_valid(goal) else 0.0
		ik.arm_weight[side] = lerpf(float(ik.arm_weight[side]), w, 1.0 - exp(-14.0 * delta))
		if float(ik.arm_weight[side]) < 0.005: ik.arm_weight[side] = 0.0
		if not is_instance_valid(goal): continue
		var s := -1.0 if side == 0 else 1.0
		var b := goal.global_basis.orthonormalized()
		ik.arm_target[side] = goal.global_position
		ik.hand_fingers[side] = -b.z
		ik.hand_palm[side] = -b.y
		ik.elbow_pole[side] = (right * s * 0.7 + Vector3.DOWN * 0.7 - fwd * 0.1).normalized()

func package_box(pkg: Node3D) -> AABB:
	if pkg.has_meta("hold_box"): return pkg.get_meta("hold_box")
	var box := AABB(Vector3(-0.1, 0, -0.07), Vector3(0.2, 0.3, 0.14))
	var first := true
	for mi: MeshInstance3D in pkg.find_children("*", "MeshInstance3D", true, false):
		var local := pkg.global_transform.affine_inverse() * mi.global_transform
		var b := local * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	pkg.set_meta("hold_box", box)
	return box

## Where a carried package sits (world): in front of the belly, held in both hands (the
## Carry_Idle clip's package pose when the contract has it).
func carry_transform() -> Transform3D:
	var flat := Basis(Vector3.UP, facing)
	if _carry_local == null: _carry_local = carry_local()
	var local: Transform3D = _carry_local
	return Transform3D(flat, global_position) * Transform3D(local.basis, local.origin * body_scale)
var _carry_local: Variant = null

# --- On the bicycle --------------------------------------------------------------------------

func ride(delta: float) -> void:
	var p := player
	var bike := p.bicycle
	var m := p.bike_markers
	if mount_clip_left > 0.0:
		# Getting on: the clip in place on the bike (authored in bike space), the body easing from
		# where it stood into the clip's first frame; then the seated pose and the IK take over.
		mount_clip_left -= delta
		if state != "BikeMount": go("BikeMount")
		var into := smoothstep(0.0, 1.0, minf(1.0, (clip_seconds("bike_mount") - mount_clip_left) / 0.25))
		global_transform = mount_from.interpolate_with(bike.global_transform, into)
		facing = bike.global_rotation.y
		yaw_rate = 0.0
		sole_lift = 0.0
		ik_off()
		if mount_clip_left <= 0.0:
			mount_from = bike.global_transform
			mount_t = 0.0
		return
	if state != "Bike": go("Bike")
	var bike_xf := bike.global_transform
	var mount_blend := smoothstep(0.0, 1.0, mount_t)
	global_transform = mount_from.interpolate_with(bike_xf, mount_blend) if mount_t < 1.0 else bike_xf
	facing = bike.global_rotation.y
	yaw_rate = 0.0
	sole_lift = 0.0
	var w := smoothstep(0.15, 1.0, mount_t)
	var up := bike_xf.basis.y.normalized()
	var fwd := -bike_xf.basis.z.normalized()
	var right := bike_xf.basis.x.normalized()
	# Foot down when stopped: slide forward off the saddle, left foot on the ground.
	var stopped := absf(p.riding_speed) < 0.15 and not p.pedalling
	foot_down = move_toward(foot_down, 1.0 if stopped and p.stopped_time > 0.35 else 0.0, delta / 0.45)
	var fd := smoothstep(0.0, 1.0, foot_down)
	var seat: Vector3 = (m.Seat as Node3D).global_position
	var hips := seat + up * seat_hip_height * body_scale + fwd * (seat_hip_forward + 0.13 * fd) - up * 0.07 * fd
	if bike_authored:
		# The clip already sits on the saddle with the trunk leaned; only the stop (foot down)
		# moves the hips.
		# The trunk lean is only re-aimed so both hands reach the grips at a relaxed ~88 %
		# of arm length (the clip's 37 degrees leave the right arm a little short).
		hips = bike_xf * bike_hips + fwd * 0.13 * fd - up * 0.07 * fd
		ik.seat_weight = w
		ik.torso_up = torso_direction(hips, up, fwd, right, m)
		ik.seat_bend = true
	else:
		ik.seat_weight = w
		ik.torso_up = torso_direction(hips, up, fwd, right, m)
		ik.seat_bend = true
	ik.hips_target = hips
	# Hands on the grips: palms on top of the bar, fingers forward and down around it.
	for side in range(2):
		var s := -1.0 if side == 0 else 1.0
		var grip: Node3D = m.GripL if side == 0 else m.GripR
		var bar_fwd := -grip.global_basis.z.normalized()
		ik.arm_weight[side] = w
		ik.arm_target[side] = grip.global_position + (Vector3.ZERO if bike_authored else up * 0.012)
		# Authored grip: keep the clip's hand orientation (ZERO), only follow the bars.
		ik.hand_fingers[side] = Vector3.ZERO if bike_authored else (bar_fwd * 0.75 + right * s * 0.12 - up * 0.55).normalized()
		ik.hand_palm[side] = (-up * 0.85 + bar_fwd * 0.3).normalized()
		ik.elbow_pole[side] = (right * s * 0.75 - up * 0.55 - fwd * 0.2).normalized()
	# Balls of the feet on the pedals; ankle drops a little at the bottom of the stroke.
	for side in range(2):
		var s := -1.0 if side == 0 else 1.0
		var pedal: Node3D = m.PedalL if side == 0 else m.PedalR
		var crank: Node3D = m.Crank
		var arm := pedal.global_position - crank.global_position
		var phase := atan2(arm.dot(-fwd), arm.dot(up))   # 0 top, +PI/2 front... (crank angle seen from the side)
		var heel := 0.08 if m.get("footboard", false) else 0.18 + 0.12 * sin(phase)
		var target := pedal.global_position + up * pedal_ball_height * body_scale
		var foot_fwd := (fwd * cos(heel) - up * sin(heel)).normalized()
		if side == 0 and fd > 0.0:
			var ground := ground_point(bike_xf.origin - right * 0.36 - fwd * 0.08)
			target = target.lerp(ground + Vector3.UP * 0.055, fd)
			foot_fwd = foot_fwd.slerp((fwd - right * 0.15).normalized(), fd)
		ik.leg_weight[side] = w
		ik.leg_target[side] = target
		ik.foot_forward[side] = foot_fwd
		ik.foot_sole[side] = -up
		ik.knee_pole[side] = (fwd * 0.9 + up * 0.25 + right * s * 0.12).normalized()
	# Head: eyes on the road ahead, into the turn and where the camera looks.
	var view := -p.camera.global_basis.z
	view.y = 0.0
	var ahead := fwd.slerp(view.normalized(), 0.6) if view.length() > 0.1 else fwd
	ik.look_dir = (ahead.rotated(Vector3.UP, p.steer_angle * 0.8) - Vector3.UP * 0.12).normalized()
	ik.look_weight = w
	ik.look_pitch_limit = 1.0
	ik.head_level = 0.45

## Torso lean (hips -> neck direction) that brings the shoulders within a relaxed reach of the
## grips: the arms end at ~88 % of their length, elbows softly bent.
func torso_direction(hips: Vector3, up: Vector3, fwd: Vector3, right: Vector3, m: Dictionary) -> Vector3:
	var r := ik.rest_global
	if not r.has("hips") or not r.has("neck") or not r.has("l_upper_arm"): return (up + fwd * 0.5).normalized()
	var s := body_scale
	var hips_rest: Vector3 = (r.hips as Transform3D).origin
	var shoulder_rest: Vector3 = (r.l_upper_arm as Transform3D).origin
	var torso := Vector2(shoulder_rest.y - hips_rest.y, shoulder_rest.z - hips_rest.z).length() * s
	var shoulder_side := absf(shoulder_rest.x) * s
	var reach := 0.0
	if r.has("l_lower_arm") and r.has("l_hand"):
		reach = ((r.l_upper_arm as Transform3D).origin.distance_to((r.l_lower_arm as Transform3D).origin) + (r.l_lower_arm as Transform3D).origin.distance_to((r.l_hand as Transform3D).origin)) * s + 0.07
	var grip: Vector3 = ((m.GripL as Node3D).global_position + (m.GripR as Node3D).global_position) * 0.5
	var best := 0.5
	var best_err := INF
	for i in range(31):
		var th := deg_to_rad(float(i) * 2.0)
		var dir := (up * cos(th) + fwd * sin(th)).normalized()
		var shoulder := hips + dir * torso
		var lateral := ((m.GripR as Node3D).global_position - grip).length() - shoulder_side
		var d := sqrt(shoulder.distance_squared_to(grip) + lateral * lateral)
		var err := absf(d - reach * 0.88)
		if err < best_err:
			best_err = err
			best = th
	return (up * cos(best) + fwd * sin(best)).normalized()

func ground_point(at: Vector3) -> Vector3:
	var q := PhysicsRayQueryParameters3D.create(at + Vector3(0, 1.0, 0), at + Vector3(0, -1.5, 0), player.collision_mask)
	q.exclude = [player.get_rid()]
	var hit := player.get_world_3d().direct_space_state.intersect_ray(q)
	return at if hit.is_empty() else (hit.position as Vector3)

# --- Bicycle markers ---------------------------------------------------------------------------

## The bicycle's rider markers: Seat (saddle contact), GripL / GripR (under the steering pivot),
## Crank (bottom bracket, turns about local X) with PedalL / PedalR. Uses the model's own nodes
## when it has them; otherwise adds markers measured from the current gray bicycle geometry.
static func bike_markers(bike: Node3D, kind: String = "bicycle") -> Dictionary:
	var found := {}
	if kind == "scooter": return scooter_markers(bike)
	for key in ["Seat", "GripL", "GripR", "Crank", "PedalL", "PedalR"]:
		var n := bike.find_child(key, true, false) as Node3D
		if n != null and not n is MeshInstance3D: found[key] = n
	if found.size() == 6:
		found["temporary"] = false
		return found
	# Fallback for a model without markers, measured on the first gray_bicycle.glb (bike space,
	# -Z forward): saddle top 0.918 m with the sit bones over its rear half; grip centres
	# +-0.302 / 1.008 / -0.297 with the bars straight; crank axle 0.31 m up, 0.09 m behind the
	# origin; 0.155 m cranks, pedals 0.135 m off centre.
	var pivot := bike.find_child("SteeringPivot", true, false) as Node3D
	if not found.has("Seat"):
		found["Seat"] = marker(bike, "Seat", Vector3(0.0, 0.918, 0.32))
	for key in ["GripL", "GripR"]:
		if found.has(key): continue
		var at := Vector3(-0.302 if key == "GripL" else 0.302, 1.008, -0.297)
		if pivot != null:
			var rest: Transform3D = pivot.get_meta("rest", pivot.transform)
			var pivot_in_bike := relative(bike, pivot.get_parent() as Node3D) * rest
			found[key] = marker(pivot, key, pivot_in_bike.affine_inverse() * at)
		else: found[key] = marker(bike, key, at)
	# Crank angle 0 = cranks level, left pedal behind (the same convention as the rebuilt model).
	if not found.has("Crank"):
		found["Crank"] = marker(bike, "Crank", Vector3(0.0, 0.31, 0.09))
	var crank: Node3D = found["Crank"]
	if not found.has("PedalL"): found["PedalL"] = marker(crank, "PedalL", Vector3(-0.135, 0.0, 0.155))
	if not found.has("PedalR"): found["PedalR"] = marker(crank, "PedalR", Vector3(0.135, 0.0, -0.155))
	found["temporary"] = true
	return found

## The electric scooter (world/city_assets/scooter.glb, no rider nodes): saddle top 0.81 m over
## z 0..0.8, handlebar grips +-0.30 / 1.08 / -0.55, floorboard 0.30 m at z -0.4..-0.1. The feet
## rest on the floorboard ("footboard": the crank never turns).
static func scooter_markers(bike: Node3D) -> Dictionary:
	var found := {"temporary": true, "footboard": true}
	found["Seat"] = marker(bike, "Seat", Vector3(0.0, 0.81, 0.14))
	found["GripL"] = marker(bike, "GripL", Vector3(-0.3, 1.08, -0.55))
	found["GripR"] = marker(bike, "GripR", Vector3(0.3, 1.08, -0.55))
	found["Crank"] = marker(bike, "Crank", Vector3(0.0, 0.3, -0.2))
	found["PedalL"] = marker(found["Crank"] as Node3D, "PedalL", Vector3(-0.13, -0.01, 0.0))
	found["PedalR"] = marker(found["Crank"] as Node3D, "PedalR", Vector3(0.13, -0.01, 0.0))
	return found

## Transform of `node` in `ancestor`'s space from local transforms (works outside the tree).
static func relative(ancestor: Node3D, node: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n := node
	while n != null and n != ancestor:
		t = n.transform * t
		n = n.get_parent() as Node3D
	return t

static func marker(parent: Node3D, label: String, at: Vector3) -> Node3D:
	var n := Node3D.new()
	n.name = label
	n.position = at
	parent.add_child(n)
	return n
