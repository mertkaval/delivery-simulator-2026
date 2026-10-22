class_name BikeRider
extends RefCounted
## Townsperson cyclists ride exactly like the courier: a humanoid citizen plays the courier's
## Bike_Pedal clip (assets/player/courier_anims.res, authored in bicycle space: hips on the
## gray bicycle's Seat, hands on GripL/GripR, feet on the pedals) and the bike's Crank turns in
## step with the clip, so the feet stay on the pedals at any speed. One clip second = one
## crank revolution; Crank.rotation.x = -angle, pedals counter-rotate to stay level.

const ANIMS := "res://assets/player/courier_anims.res"
const CLIP := "rider/Bike_Pedal"
const WHEEL_RADIUS := 0.35
const GEAR := 2.2              ## rear-wheel turns per crank turn (matches actors/player_avatar.gd)
static var _lib: AnimationLibrary

static func available() -> bool:
	return ResourceLoader.exists(ANIMS)

## Seat a humanoid townsperson on `bike` (a CityAssets "bicycle"). Returns the rider node.
static func mount(bike: Node3D, index: int) -> Node3D:
	var rider: LivingCitizen = LivingAssets.humanoid(index)
	bike.add_child(rider)
	rider.transform = Transform3D.IDENTITY    # the clip is authored with the rider root at the bike root
	rider.set_process(false)                  # its walking logic would replace the riding clip
	if rider.has_method("attach_helmet"): rider.attach_helmet()
	if _lib == null: _lib = load(ANIMS)
	for p in rider.find_children("*", "AnimationPlayer", true, false):
		var ap := p as AnimationPlayer
		if not ap.has_animation_library("rider"): ap.add_animation_library("rider", _lib)
		ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		ap.play(CLIP)
		ap.seek(0.0, true)
	return rider

## Advance the pedalling by the distance ridden and pose rider + crank to match.
static func ride(cyclist: Dictionary, distance: float) -> void:
	var angle: float = float(cyclist.get("crank", 0.0)) + distance / WHEEL_RADIUS / GEAR
	angle = fmod(angle, TAU)
	cyclist["crank"] = angle
	var bike: Node3D = cyclist.bike
	var crank := bike.find_child("Crank", true, false) as Node3D
	if crank:
		crank.rotation.x = -angle
		for pedal in ["PedalL", "PedalR"]:
			var p := crank.find_child(pedal, false, false) as Node3D
			if p: p.rotation.x = angle
	var rider: Node3D = cyclist.rider
	for p in rider.find_children("*", "AnimationPlayer", true, false):
		var ap := p as AnimationPlayer
		if ap.current_animation == CLIP: ap.seek(angle / TAU, true)
