class_name LivingCitizen
extends Node3D
## A townsperson's body: skinned model(s), clip selection, stride-matched walking, one-shot
## transitions (sit down / stand up / set a plate down), hand props, and animation LOD.
##
## Controllers (CitizenBrain, restaurant waiters, shop browsers) set `ground_speed` every frame
## and choose `locomotion` / `purpose_pose`; legacy callers that only move the node still work
## (speed is then measured from displacement). Animation is advanced manually: every frame up
## close, at 30 / 15 / 8 Hz further out, not at all off screen, hidden beyond `max_distance`.
var variants: Array[Node3D]=[]
var players: Array[AnimationPlayer]=[]
var last_position := Vector3.ZERO
var timer := 0.0
var last_clip := ""
var active_lod := -1
var purpose_pose := ""
var walk_phase := 0.0
## Beyond this distance the citizen is hidden and not animated (indoor people use less).
var max_distance := 85.0:
	set(value):
		max_distance = value
		apply_range()
## Controller-driven ground speed in m/s (-1: measure from displacement).
var ground_speed := -1.0
## Walking clip: Walk, WalkFormal or WalkCarry.
var locomotion := "Walk"
## Ground speed of the walk clip at speed_scale 1 for this body (LivingAssets.STRIDE x scale).
var stride_speed := 1.1
var body_scale := 1.0
var body_id := ""
var humanoid := false
var idle_rate := 1.0
## One-shot clip in progress (SitDown, StandUp, PickUp ...), seconds left, and what follows.
var oneshot := ""
var oneshot_left := 0.0
var anim_accum := 0.0
var hidden_once := false
var notifier: VisibleOnScreenNotifier3D
var skeleton: Skeleton3D
var phone: Node3D
var tray: Node3D
var tray_load: Node3D
var broom: Node3D
var shadows := true
## Waiters: the tray stays in the hands through PickUp (lifting from / setting on a surface).
var tray_active := false
## Standing staff fidget: the idle clip cycles through these (shop clerks, counter staff).
var routine: PackedStringArray = PackedStringArray()
var routine_left := 0.0
var routine_step := 0
## Camera position, read once per frame for every citizen.
static var camera_frame := -1
static var camera_position := Vector3.ZERO
static var camera_known := false
const PHONE_CLIPS := ["Phone", "SitPhone", "Photo", "PhoneCall"]
const TRAY_CLIPS := ["Carry", "WalkCarry"]

func attach_helmet() -> void:
	if name in ["SketchupCitizen", "HumanoidCitizen"]: return   # converted rigs use other bone scales; no helmet prop
	for variant in variants:
		var skel: Skeleton3D=variant.find_children("*","Skeleton3D",true,false)[0]
		var index := skel.find_bone("Head")
		if index<0:
			for b in range(skel.get_bone_count()):
				if skel.get_bone_name(b).to_lower().begins_with("head") or skel.get_bone_name(b).to_lower().contains(":head_"): index=b
		if index<0: continue
		var head_name := skel.get_bone_name(index)
		var attachment := BoneAttachment3D.new()
		attachment.bone_name=head_name
		skel.add_child(attachment)
		var helmet := CityAssets.create("helmet",65)
		attachment.add_child(helmet)
		# People vary in height: place the helmet relative to this skeleton's head bone
		# (authored at 1.55 m on the 1.80 m reference, crown 0.14 m above it).
		var head_rest := skel.get_bone_global_rest(index)
		var crown := head_rest.origin.y*1.69/1.55
		helmet.transform=head_rest.affine_inverse()*Transform3D(Basis.IDENTITY,Vector3(0,crown,0))

func _ready() -> void:
	last_position=global_position
	# Off screen (behind the camera, outside the frustum) the body only animates at 2 Hz.
	# (Processing is never disabled: other systems may hang their own nodes on a citizen.)
	notifier=VisibleOnScreenNotifier3D.new()
	notifier.aabb=AABB(Vector3(-0.6,0,-0.6),Vector3(1.2,2.0,1.2))
	add_child(notifier)
	apply_range()
	if humanoid and not variants.is_empty():
		skeleton=variants[0].find_child("GeneralSkeleton",true,false) as Skeleton3D

## Meshes fade out by distance on the GPU too (no per-frame work for far people).
func apply_range() -> void:
	for variant in variants:
		for mesh: GeometryInstance3D in variant.find_children("*","GeometryInstance3D",true,false):
			mesh.visibility_range_end=max_distance+4.0
			mesh.visibility_range_end_margin=4.0

## Plays `clip` once (blending in), then returns to the looping clip choice. Returns its length.
func play_once(clip: String, backwards := false) -> float:
	var animator: AnimationPlayer=players[maxi(active_lod,0)]
	if not animator.has_animation(clip): return 0.0
	oneshot=clip
	var length := animator.get_animation(clip).length
	oneshot_left=length
	if backwards: animator.play_backwards(clip,.2)
	else: animator.play(clip,.2)
	animator.speed_scale=1.0
	last_clip=clip
	return length

## Seated placement for a seat whose top is `seat_top` above this node's parent origin:
## (origin height, distance of the origin ahead of the back's rearmost point). See CitySeating.
func seat_fit(seat_top: float) -> Vector2:
	var m: Vector3=LivingAssets.seated(body_id) if body_id!="" else Vector3(0.45,-0.44,0.0)
	return Vector2(seat_top-m.x*body_scale, -m.y*body_scale)

## Script-time counters read by tests/capture_npc_life.gd (frame-time reports).
static var prof_usec := 0
static var prof_calls := 0
func _process(delta: float) -> void:
	var t0 := Time.get_ticks_usec()
	prof_calls+=1
	_process_body(delta)
	prof_usec+=Time.get_ticks_usec()-t0
func _process_body(delta: float) -> void:
	if humanoid and not players.is_empty() and players[0].callback_mode_process!=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL:
		players[0].callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	timer+=delta
	anim_accum+=delta
	# Off screen, or hidden by distance: nothing to do until the next 2-3 Hz check.
	if timer<0.4 and active_lod==-1 and hidden_once: return
	if notifier!=null and timer<0.5 and active_lod!=-1 and not notifier.is_on_screen(): return
	var frame := Engine.get_process_frames()
	if frame!=camera_frame:
		camera_frame=frame
		var camera := get_viewport().get_camera_3d()
		camera_known=camera!=null
		if camera_known: camera_position=camera.global_position
	var distance := global_position.distance_to(camera_position) if camera_known else 0.0
	if distance>max_distance or not is_visible_in_tree():
		if active_lod!=-1:
			for i in range(players.size()):
				if players[i].callback_mode_process!=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL: players[i].pause()
				variants[i].visible=false
		active_lod=-1
		hidden_once=true
		last_position=global_position
		timer=0
		anim_accum=0
		return
	if oneshot!="":
		oneshot_left-=delta
		if oneshot_left<=0: oneshot=""
	# Animation update rate by distance (skeletal animation is the main per-person cost).
	var interval := 0.0 if distance<10 else (1.0/20.0 if distance<24 else (1.0/10.0 if distance<45 else 0.2))
	var on_screen := notifier==null or notifier.is_on_screen()
	if not on_screen: interval=maxf(interval,0.5)
	# Standing or seated in place (diners, counter staff, guards): half the rate beyond 10 m.
	elif distance>=10 and ground_speed==0.0 and oneshot=="": interval=maxf(interval*2.0,1.0/15.0)
	if timer<interval: return
	var measured := global_position.distance_to(last_position)/maxf(timer,0.001)
	last_position=global_position
	var elapsed := minf(anim_accum,0.5)
	timer=0
	anim_accum=0
	var lod := 0 if distance<18 else (1 if distance<45 else 2)
	if variants.size()==1: lod=0   # converted people: one model, Godot's automatic mesh LOD
	if active_lod!=lod:
		for i in range(variants.size()):
			variants[i].visible=i==lod
			if i!=lod and players[i].callback_mode_process!=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL: players[i].pause()
		active_lod=lod
		last_clip=""
	var want_shadows := distance<26
	if want_shadows!=shadows:
		shadows=want_shadows
		for mesh: GeometryInstance3D in variants[lod].find_children("*","GeometryInstance3D",true,false):
			mesh.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var animator: AnimationPlayer=players[lod]
	var speed := ground_speed if ground_speed>=0.0 else measured
	if not routine.is_empty() and oneshot=="":
		routine_left-=elapsed
		if routine_left<=0.0:
			routine_step+=1
			purpose_pose=routine[int(LivingAssets.noise(get_instance_id()%9973,routine_step)*routine.size())]
			routine_left=animator.get_animation(purpose_pose).length if purpose_pose=="Interact" and animator.has_animation(purpose_pose) else 4.0+6.0*LivingAssets.noise(routine_step,7)
	if oneshot=="":
		var clip := (locomotion if speed>.15 else "Idle")
		if speed>.15 and not animator.has_animation(clip): clip="Walk"
		if speed<=.15:
			var legacy_hip := get_node_or_null("HipL") as Node3D
			if legacy_hip!=null and legacy_hip.rotation.x>.75: clip="Sit" if legacy_hip.rotation.x>1.5 else "Cycle"
			if purpose_pose!="": clip=purpose_pose
		if not animator.has_animation(clip): clip="Idle" if animator.has_animation("Idle") else animator.get_animation_list()[0]
		if clip!=last_clip:
			animator.play(clip,.3)
			last_clip=clip
		if clip in LivingAssets.LOCOMOTION or LivingAssets.STRIDE_FACTOR.has(clip):
			var reference := stride_speed*float(LivingAssets.STRIDE_FACTOR.get(clip,1.0))
			animator.speed_scale=clampf(speed/maxf(reference,0.1),.55,1.7) if humanoid else clampf(speed/1.25,.65,1.5)
		else:
			animator.speed_scale=idle_rate if humanoid else .75
	if animator.callback_mode_process==AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL:
		if on_screen or elapsed>=0.45: animator.advance(elapsed)
	elif distance>45 and oneshot=="":
		walk_phase+=elapsed*animator.speed_scale
		if animator.current_animation!="": animator.seek(fmod(walk_phase,animator.current_animation_length),true)
		animator.pause()
	elif not animator.is_playing() and last_clip!="":
		animator.play(last_clip)
	update_props(distance)

## Phone in the right hand for phone clips; a tray between both hands for carrying clips.
func update_props(distance: float) -> void:
	if skeleton==null: return
	var clip := last_clip
	var want_phone := clip in PHONE_CLIPS and distance<40
	if want_phone and phone==null:
		phone=attach_phone()
	if phone!=null: phone.visible=want_phone
	var want_tray := tray!=null and (clip in TRAY_CLIPS or (tray_active and clip=="PickUp"))
	if tray!=null:
		tray.visible=want_tray and distance<50
		if tray.visible:
			var l := skeleton.find_bone("LeftHand")
			var r := skeleton.find_bone("RightHand")
			var gl := skeleton.global_transform*skeleton.get_bone_global_pose(l)
			var gr := skeleton.global_transform*skeleton.get_bone_global_pose(r)
			# Tray rests on both palms: between the hands, a palm's length along the fingers.
			var fingers := ((gl.basis.y+gr.basis.y)*0.5).normalized()
			var centre := (gl.origin+gr.origin)*0.5+fingers*0.05*body_scale+Vector3.UP*0.035
			var forward := -global_basis.z
			tray.global_transform=Transform3D(Basis.looking_at(forward,Vector3.UP),centre)

	# Push broom while sweeping: the handle runs through both hands (high left, low right) down
	# to the ground ahead, the brush head flat on the pavement across the stroke.
	var want_broom := clip=="Sweep" and distance<45
	if want_broom and broom==null: broom=make_broom()
	if broom!=null:
		broom.visible=want_broom
		if want_broom:
			var gl := skeleton.global_transform*skeleton.get_bone_global_pose(skeleton.find_bone("LeftHand"))
			var gr := skeleton.global_transform*skeleton.get_bone_global_pose(skeleton.find_bone("RightHand"))
			# grip centres: a little along the fingers from the hand bones
			var high := gl.origin+gl.basis.y.normalized()*0.06*body_scale
			var low := gr.origin+gr.basis.y.normalized()*0.06*body_scale
			var down := (low-high).normalized()
			if down.y>-0.2: down=(down+Vector3.DOWN*0.6).normalized()
			var ground := global_position.y+0.03
			var reach := (high.y-ground)/maxf(-down.y,0.2)
			var foot := high+down*reach
			var forward := Vector3(down.x,0,down.z).normalized() if Vector2(down.x,down.z).length()>0.05 else -global_basis.z
			var handle := broom.get_child(0) as Node3D
			var head := broom.get_child(1) as Node3D
			var top := high-down*0.12
			var length := top.distance_to(foot)
			handle.global_transform=Transform3D(Basis.looking_at(down,forward if absf(down.dot(Vector3.UP))>0.95 else Vector3.UP)*Basis(Vector3.RIGHT,-PI*0.5),(top+foot)*0.5)
			handle.scale=Vector3(1,length,1)
			head.global_transform=Transform3D(Basis.looking_at(forward,Vector3.UP),foot)

func make_broom() -> Node3D:
	var root := Node3D.new()
	root.name="Broom"
	root.top_level=true
	add_child(root)
	var wood := StandardMaterial3D.new()
	wood.albedo_color=Color(0.55,0.4,0.24)
	wood.roughness=0.7
	var handle := MeshInstance3D.new()
	var stick := CylinderMesh.new()
	stick.top_radius=0.014
	stick.bottom_radius=0.014
	stick.height=1.0
	stick.radial_segments=6
	stick.rings=1
	stick.material=wood
	handle.mesh=stick
	root.add_child(handle)
	var head := MeshInstance3D.new()
	var block := BoxMesh.new()
	block.size=Vector3(0.46,0.05,0.07)
	var bristle := StandardMaterial3D.new()
	bristle.albedo_color=Color(0.12,0.11,0.1)
	bristle.roughness=0.9
	block.material=bristle
	head.mesh=block
	root.add_child(head)
	for mesh: GeometryInstance3D in [handle,head]:
		mesh.visibility_range_end=50.0
	return root

## Gives this person a tray to carry (shown while a carrying clip plays); `load` sits on it.
func carry(item: Node3D) -> void:
	if tray==null:
		tray=load("res://assets/props/npc/tray.glb").instantiate()
		tray.top_level=true
		add_child(tray)
		tray.visible=false
	if tray_load!=null and tray_load!=item:
		tray_load.queue_free()
	tray_load=item
	if item!=null and item.get_parent()!=tray:
		if item.get_parent()!=null: item.get_parent().remove_child(item)
		tray.add_child(item)
		item.position=Vector3(0,0.008,0)

func attach_phone() -> Node3D:
	var hand := skeleton.find_bone("RightHand")
	var thumb := skeleton.find_bone("RightThumbProximal")
	if hand<0: return null
	var attachment := BoneAttachment3D.new()
	attachment.bone_name="RightHand"
	skeleton.add_child(attachment)
	# Palm normal in the hand bone's frame from the rest pose (thumb on the palm's leading edge).
	var rest := skeleton.get_bone_global_rest(hand)
	var along := Vector3.UP
	var palm := Vector3.FORWARD
	if thumb>=0:
		var t := rest.affine_inverse()*skeleton.get_bone_global_rest(thumb).origin
		t=(t-along*t.dot(along)).normalized()
		palm=-along.cross(t).normalized()
	var model: Node3D=load("res://assets/props/npc/phone.glb").instantiate()
	attachment.add_child(model)
	var side := palm.cross(along).normalized()
	# Phone lies on the palm, screen facing out of the palm (to the eyes), long axis along the fingers.
	model.transform=Transform3D(Basis(side,palm,along),along*0.075/body_scale+palm*0.02/body_scale)
	model.scale=Vector3.ONE/body_scale
	return attachment
