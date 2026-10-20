class_name LivingCitizen
extends Node3D
## Skinned animation follows actual displacement, with distance-based update budgets.
var variants: Array[Node3D]=[]
var players: Array[AnimationPlayer]=[]
var last_position := Vector3.ZERO
var timer := 0.0
var last_clip := ""
var active_lod := -1
var purpose_pose := ""
var walk_phase := 0.0
## Beyond this distance the citizen is hidden and not animated (indoor people use less).
var max_distance := 105.0
func attach_helmet() -> void:
	if name in ["SketchupCitizen", "HumanoidCitizen"]: return   # converted rigs use other bone scales; no helmet prop
	for variant in variants:
		var skeleton: Skeleton3D=variant.find_children("*","Skeleton3D",true,false)[0]
		var index := skeleton.find_bone("Head")
		if index<0:
			for b in range(skeleton.get_bone_count()):
				if skeleton.get_bone_name(b).to_lower().begins_with("head") or skeleton.get_bone_name(b).to_lower().contains(":head_"): index=b
		if index<0: continue
		var head_name := skeleton.get_bone_name(index)
		var attachment := BoneAttachment3D.new()
		attachment.bone_name=head_name
		skeleton.add_child(attachment)
		var helmet := CityAssets.create("helmet",65)
		attachment.add_child(helmet)
		# People vary in height: place the helmet relative to this skeleton's head bone
		# (authored at 1.55 m on the 1.80 m reference, crown 0.14 m above it).
		var head_rest := skeleton.get_bone_global_rest(index)
		var crown := head_rest.origin.y*1.69/1.55
		helmet.transform=head_rest.affine_inverse()*Transform3D(Basis.IDENTITY,Vector3(0,crown,0))
func _ready() -> void:
	last_position=global_position
func _process(delta: float) -> void:
	timer+=delta
	var camera := get_viewport().get_camera_3d()
	var distance := global_position.distance_to(camera.global_position) if camera else 0.0
	if distance>max_distance:
		for i in range(players.size()):
			players[i].pause()
			variants[i].visible=false
		active_lod=-1
		last_position=global_position
		timer=0
		return
	var interval := .033 if distance<18 else (.10 if distance<45 else .25)
	if timer<interval: return
	var speed := global_position.distance_to(last_position)/timer
	last_position=global_position
	var elapsed := timer
	timer=0
	var lod := 0 if distance<18 else (1 if distance<45 else 2)
	if variants.size()==1: lod=0   # converted people: one model, Godot's automatic mesh LOD
	var clip := "Brisk" if speed>1.8 else ("Walk" if speed>.12 else "Idle")
	var legacy_hip := get_node_or_null("HipL") as Node3D
	if legacy_hip!=null and legacy_hip.rotation.x>.75: clip="Sit" if legacy_hip.rotation.x>1.5 else "Cycle"
	if purpose_pose!="" and speed<.12: clip=purpose_pose
	if active_lod!=lod:
		for i in range(variants.size()):
			variants[i].visible=i==lod
			players[i].pause()
		active_lod=lod
		last_clip=""
	var animator: AnimationPlayer=players[lod]
	if not animator.has_animation(clip): clip="Idle" if animator.has_animation("Idle") else animator.get_animation_list()[0]
	if clip!=last_clip:
		animator.play(clip,.18)
		last_clip=clip
	animator.speed_scale=clampf(speed/1.25,.65,1.5) if clip in ["Walk","Brisk"] else .75
	if distance>45:
		walk_phase+=elapsed*animator.speed_scale
		animator.seek(fmod(walk_phase,animator.current_animation_length),true)
		animator.pause()
