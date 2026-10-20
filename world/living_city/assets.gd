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
	var person := sketchup_person(STANDING[index%STANDING.size()])
	person.max_distance=70.0
	return person

static func citizen(index: int=-1) -> Node3D:
	if index<0:
		index=citizen_index
		citizen_index+=1
	if index%WALKER_EVERY==1 and ResourceLoader.exists(SKETCHUP_PEOPLE%WALKER): return sketchup_person(WALKER)
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
