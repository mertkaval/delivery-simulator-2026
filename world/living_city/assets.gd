class_name LivingAssets
extends RefCounted
static var scenes := {}
## Twelve designed people (world/living_city/build_people.py); outfits are authored, not tinted.
const VARIANTS := 12
static var citizen_index := 0
static var citizen_materials := {}
static var shared_materials := {}
static var interned := {}
static func scene(asset: String) -> Node3D:
	if not scenes.has(asset): scenes[asset]=load("res://world/living_city/assets/"+asset+".glb")
	var result: Node3D=scenes[asset].instantiate()
	if not interned.has(asset):
		for part in result.find_children("*","MeshInstance3D",true,false):
			for surface in range(part.mesh.get_surface_count()):
				var material: Material=part.mesh.surface_get_material(surface)
				if material is StandardMaterial3D:
					var key := "%s_%s_%s_%s_%s_%s"%[material.resource_name,material.albedo_color.to_html(),material.roughness,material.metallic,material.transparency,material.cull_mode]
					if not shared_materials.has(key): shared_materials[key]=material
					part.mesh.surface_set_material(surface,shared_materials[key])
		interned[asset]=true
	return result
## Converted Sketchfab people (tools/prepare_sketchup_assets.py). The tracksuit man has the full
## clip set (Idle, Walk, Brisk, Wait, Talk, Sit, Cycle) and joins the walking population; the
## others carry a single standing clip and are used as stationary people (staff, guards).
const SKETCHUP_PEOPLE := "res://assets/sketchup/people/%s.glb"
const WALKER := "tracksuit_man"
const STANDING := ["security_guard", "casual_woman", "casual_man"]
## Every WALKER_EVERY-th citizen is the converted walker.
const WALKER_EVERY := 3
static var people_scenes := {}
## The tracksuit rig's FBX node chain imports into Godot a quarter turn off (Blender shows it
## upright): stand it up about X, then turn it to face -Z.
const ORIENTATION_FIX := {"tracksuit_man": Vector2(PI / 2, -PI / 2)}

static func sketchup_person(id: String) -> LivingCitizen:
	if not people_scenes.has(id): people_scenes[id]=load(SKETCHUP_PEOPLE%id)
	var model := LivingCitizen.new()
	model.name="SketchupCitizen"
	var mesh: Node3D=people_scenes[id].instantiate()
	if ORIENTATION_FIX.has(id):
		var fix: Vector2=ORIENTATION_FIX[id]
		(mesh.get_child(0) as Node3D).rotation.x+=fix.x
		mesh.rotate_y(fix.y)
	model.add_child(mesh)
	model.variants.append(mesh)
	var animator: AnimationPlayer=mesh.find_child("AnimationPlayer",true,false)
	for clip in animator.get_animation_list(): animator.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
	model.players.append(animator)
	animator.play("Idle")
	for joint in ["HipL","HipR","KneeL","KneeR","ShoulderL","ShoulderR","ElbowL","ElbowR"]:
		var proxy := Node3D.new()
		proxy.name=joint
		model.add_child(proxy)
	return model

## A standing person for a fixed spot (guard at a door, staff at a counter).
static func standing_person(index: int) -> LivingCitizen:
	# Guards keep their uniform model; clerks and other standing staff are realistic humanoids.
	var person: LivingCitizen = sketchup_person(STANDING[0]) if index%STANDING.size()==0 else humanoid(index)
	person.max_distance=70.0
	if person.humanoid: person.routine=PackedStringArray(["Idle","Idle","Talk","Interact","Look","Phone"])
	return person

## Realistic townspeople (tools/prepare_characters.py) animated with the CC0 Quaternius
## Universal Animation Library through Godot humanoid retargeting (tools/setup_retarget.gd):
## every library clip drives "%GeneralSkeleton:<ProfileBone>", so it plays on any of them.
## Extra clips authored on the library rig (tools/build_npc_clips.py -> ual_npc.glb) add
## carrying a tray, using a phone (standing / seated), eating at a table and window shopping.
const HUMANOIDS := ["casual_male_tshirt", "business_man_eric", "sophia", "casual_female", "casual_male_2"]
const UAL := "res://assets/animations/ual/ual_standard.glb"
const UAL_NPC := "res://assets/animations/ual/ual_npc.glb"
## Game clip name -> library clip.
const CLIPS := {"Idle": "Idle", "Walk": "Walk", "Brisk": "Walk", "Run": "Jog_Fwd", "Wait": "Idle",
	"Talk": "Idle_Talking", "Sit": "Sitting_Idle", "SitTalk": "Sitting_Talking", "Cycle": "Sitting_Idle",
	"Interact": "Interact", "PickUp": "PickUp_Table", "Push": "Push", "WalkFormal": "Walk_Formal",
	"SitDown": "Sitting_Enter", "StandUp": "Sitting_Exit",
	"Carry": "Idle_Carry", "WalkCarry": "Walk_Carry", "Phone": "Idle_Phone", "SitPhone": "Sitting_Phone",
	"SitEat": "Sitting_Eat", "Look": "Idle_Look"}
## Clips that move the feet over the ground, and the ground speed (m/s) each one covers at
## speed_scale 1 on each body at scale 1: the planted foot's backward speed, measured on the
## retargeted clips (stance frames of LeftToes/RightToes; tmp measurement, see PROJECT_STATE).
## Playback is scaled by ground_speed / (this * body scale), so feet never slide.
const LOCOMOTION := ["Walk", "Brisk", "WalkFormal", "WalkCarry"]
const STRIDE := {"casual_male_tshirt": 1.118, "business_man_eric": 1.100, "sophia": 1.017, "casual_female": 1.102, "casual_male_2": 1.095}
const FORMAL_STRIDE := 0.98   ## Walk_Formal / Walk
## Seated pose, measured on the retargeted Sitting_Idle (= Sitting_Enter end = Sitting_Exit start)
## in body space at scale 1 (body faces +Z): lowest point of the buttocks / thighs (`seat`),
## the back's rearmost point (`back`, z) and the soles (`sole`). The pelvis rests behind the
## body origin: seat contact is ~0.35 m behind it, knees ~0.07 m in front.
const SEATED := {"casual_male_tshirt": Vector3(0.453, -0.449, -0.004), "business_man_eric": Vector3(0.495, -0.443, -0.007),
	"sophia": Vector3(0.427, -0.381, 0.017), "casual_female": Vector3(0.445, -0.439, 0.001), "casual_male_2": Vector3(0.437, -0.478, -0.009)}
static var clip_library: AnimationLibrary
static var outfit_materials := {}

static func game_clips() -> AnimationLibrary:
	if clip_library == null:
		clip_library = AnimationLibrary.new()
		for path in [UAL, UAL_NPC]:
			if not ResourceLoader.exists(path): continue
			var source: Node = load(path).instantiate()
			var full: AnimationLibrary = (source.find_child("AnimationPlayer", true, false) as AnimationPlayer).get_animation_library("")
			for game_name in CLIPS:
				if clip_library.has_animation(game_name) or not full.has_animation(CLIPS[game_name]): continue
				clip_library.add_animation(game_name, full.get_animation(CLIPS[game_name]))
			source.free()
	return clip_library

## Deterministic pseudo-random [0, 1) for person `index`, stream `k`.
static func noise(index: int, k: int) -> float:
	var h := (index * 374761393 + k * 668265263) & 0x7fffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0x7fffffff
	return float(h % 10007) / 10007.0

## Outfit colours for person `index`: [top, bottom] as (hue shift, added saturation, value, strength).
static func outfit_colours(index: int) -> Array[Vector4]:
	var top := Vector4(noise(index, 1), -0.35 + 0.6 * noise(index, 2), 0.75 + 0.4 * noise(index, 3), 1.0)
	if noise(index, 4) < 0.2: top.w = 0.0   # some keep the garment as designed
	var bottom := Vector4(noise(index, 5), -0.3 + 0.42 * noise(index, 6), 0.68 + 0.4 * noise(index, 7), 1.0)
	if noise(index, 8) < 0.35: bottom.w = 0.0   # denim / dark trousers are common
	return [top, bottom]

## Shared outfit material for one surface of one character (instance uniforms carry colours).
static func outfit_material(id: String, surface: int, source: StandardMaterial3D) -> Material:
	var key := "%s_%d" % [id, surface]
	if outfit_materials.has(key): return outfit_materials[key]
	var fixed := Vector2(-1, -1)
	var mask_path := "res://assets/sketchup/people/%s_outfit_mask.png" % id
	if id == "casual_male_tshirt":
		var label := source.resource_name
		fixed = Vector2(1, 0) if label == "outfit_top" else (Vector2(0, 1) if label == "outfit_bottom" else Vector2(-2, -2))
	if fixed.x < -1.5 or (fixed.x < 0 and not ResourceLoader.exists(mask_path)) or source.albedo_texture == null:
		outfit_materials[key] = source
		return source
	var m := ShaderMaterial.new()
	m.shader = preload("res://world/living_city/outfit.gdshader")
	m.set_shader_parameter("albedo_texture", source.albedo_texture)
	if source.normal_enabled and source.normal_texture != null:
		m.set_shader_parameter("normal_texture", source.normal_texture)
		m.set_shader_parameter("use_normal", true)
	if fixed.x < 0: m.set_shader_parameter("mask_texture", load(mask_path))
	m.set_shader_parameter("mask_fixed", fixed)
	m.set_shader_parameter("roughness_value", source.roughness)
	m.resource_name = source.resource_name + "_outfit"
	outfit_materials[key] = m
	return m

## `size` overrides the natural height variation (seated people are sized to their seat).
static func humanoid(index: int, size: float = -1.0) -> LivingCitizen:
	var id: String = HUMANOIDS[index%HUMANOIDS.size()]
	if not people_scenes.has(id): people_scenes[id]=load(SKETCHUP_PEOPLE%id)
	var model := LivingCitizen.new()
	model.name="HumanoidCitizen"
	model.humanoid=true
	model.body_id=id
	var body: Node3D=people_scenes[id].instantiate()
	# Retarget convention faces +Z; the game's people face -Z.
	body.rotation.y=PI
	# Natural height variation (about +-7 %) so repeated people do not read as clones.
	if size <= 0.0: size = 0.93+0.14*noise(index, 11)
	body.scale=Vector3.ONE*size
	model.body_scale=size
	model.stride_speed=float(STRIDE[id])*size
	model.add_child(body)
	model.variants.append(body)
	# Clothing recolour: shared material per surface, colours per person (instance uniforms).
	var colours := outfit_colours(index)
	for mesh: MeshInstance3D in body.find_children("*","MeshInstance3D",true,false):
		# A child node keeps scene-wide static batching (CedarNeighborhood.batch_imported_assets,
		# which merges childless meshes into MultiMeshes) away from skinned people.
		var keep := Node.new()
		keep.name="Skinned"
		mesh.add_child(keep)
		var recoloured := false
		for s in range(mesh.mesh.get_surface_count()):
			var source := mesh.mesh.surface_get_material(s) as StandardMaterial3D
			if source == null: continue
			var material := outfit_material(id, s, source)
			if material is ShaderMaterial:
				mesh.set_surface_override_material(s, material)
				recoloured = true
		if recoloured:
			mesh.set_instance_shader_parameter("outfit_top", colours[0])
			mesh.set_instance_shader_parameter("outfit_bottom", colours[1])
	var animator := AnimationPlayer.new()
	animator.name="AnimationPlayer"
	body.add_child(animator)
	animator.root_node=NodePath("..")
	animator.add_animation_library("",game_clips())
	# LivingCitizen switches this to manual advance once it runs (rate by distance / visibility);
	# a citizen placed with set_process(false) keeps a normally playing AnimationPlayer.
	animator.play("Idle")
	animator.seek(fposmod(index*1.37,2.0),true)
	model.players.append(animator)
	model.idle_rate=0.9+0.2*noise(index, 12)
	for joint in ["HipL","HipR","KneeL","KneeR","ShoulderL","ShoulderR","ElbowL","ElbowR"]:
		var proxy := Node3D.new()
		proxy.name=joint
		model.add_child(proxy)
	return model

static func citizen(index: int=-1) -> Node3D:
	if index<0:
		index=citizen_index
		citizen_index+=1
	if ResourceLoader.exists(SKETCHUP_PEOPLE%HUMANOIDS[0]): return humanoid(index)
	return classic_citizen(index)

## The earlier procedural citizens (kept for cyclists: they carry a pedalling clip).
static func classic_citizen(index: int) -> Node3D:
	var model := LivingCitizen.new()
	model.name="SkinnedCitizen"
	for level in range(3):
		var mesh := scene("citizen_%d"%(index%VARIANTS)+("_lod%d"%level if level else ""))
		model.add_child(mesh)
		model.variants.append(mesh)
		var animator: AnimationPlayer=mesh.find_child("AnimationPlayer",true,false)
		for clip in animator.get_animation_list(): animator.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
		model.players.append(animator)
		animator.play("Idle")
		animator.pause()
		mesh.visible=level==0
	# Compatibility nodes preserve old pose callers while the weighted rig animates.
	for joint in ["HipL","HipR","KneeL","KneeR","ShoulderL","ShoulderR","ElbowL","ElbowR"]:
		var proxy := Node3D.new()
		proxy.name=joint
		model.add_child(proxy)
	var colors := [Color("304d60"),Color("8e5147"),Color("53624a"),Color("65656a"),Color("aa9371"),Color("bd753f")]
	for mesh in model.find_children("*","MeshInstance3D",true,false):
		for surface in range(mesh.mesh.get_surface_count()):
			var material: Material=mesh.mesh.surface_get_material(surface)
			if material is StandardMaterial3D and material.resource_name=="CitizenCoat":
				var key := index%6
				if not citizen_materials.has(key):
					var copy := material.duplicate() as StandardMaterial3D
					copy.albedo_color=colors[index%6]
					citizen_materials[key]=copy
				mesh.set_surface_override_material(surface,citizen_materials[key])
	return model
