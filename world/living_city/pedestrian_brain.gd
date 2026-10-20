class_name CitizenBrain
extends Node
var body: CharacterBody3D
var model: LivingCitizen
var owner_system: Node
var identity := 0
var route := PackedInt64Array()
var cursor := 0
var state := "WALK"
var destination := {}
var dwell := 0.0
var blocked_time := 0.0
var elapsed := 0.0
var cycle := 0
var speed := 1.25
var downtown := true
func _ready() -> void:
	body=get_parent() as CharacterBody3D
	model=body.get_node_or_null("SkinnedCitizen") as LivingCitizen
	downtown=body.position.x>120
	speed=1.12+(identity%7)*.045
	choose_destination()
func current_hour() -> float:
	if downtown: return owner_system.hour
	var app := owner_system.get_parent().get_parent()
	return app.session.hour() if "session" in app else 12.0
func choose_destination() -> void:
	CitizenRoutes.prepare()
	cycle+=1
	var hour := current_hour()
	var desired := "work" if (hour>=8 and hour<11) or (hour>=14 and hour<17) else ("cafe" if hour>=11 and hour<14 else ("shop" if hour>=17 and hour<20 else "home"))
	if identity%5==0: desired="service" if downtown else "cafe"
	if identity%6==1 and hour>=7 and hour<20: desired="transit"
	var best := -INF
	var chosen := {}
	for candidate in CitizenRoutes.destinations:
		var p := CitizenRoutes.graph.get_point_position(candidate.node)
		if (p.x>120)!=downtown: continue
		if candidate.node==destination.get("node",-1): continue
		var distance := p.distance_to(body.position)
		var jitter := float(posmod(identity*73+candidate.node*31+cycle*19,101))/101.0
		var score := (5.0 if candidate.type==desired else 0.0)+jitter*3.0-distance*.009
		if distance<8: score-=6
		if score>best:
			best=score
			chosen=candidate
	destination=chosen
	route=CitizenRoutes.path(body.position,chosen.node)
	cursor=0
	state="WALK"
	body.set_meta("purpose",chosen.type+": "+chosen.name)
	body.set_meta("daily_goal",desired)
func crossing_open() -> bool:
	if downtown:
		var phase := fmod(owner_system.elapsed,64)
		return phase>=32 and phase<38
	return owner_system.safe_to_cross(body.position.z)
func _physics_process(delta: float) -> void:
	elapsed+=delta
	var camera := get_viewport().get_camera_3d()
	var distance := body.position.distance_to(camera.global_position) if camera else 0.0
	var active := distance<115 and (current_hour()>=6 or identity%4==0)
	body.visible=active
	body.collision_layer=4 if active else 0
	if not active: return
	if state=="VISIT":
		dwell-=delta
		if model: model.purpose_pose="Talk" if destination.type in ["cafe","shop","service"] else "Wait"
		if dwell<=0: choose_destination()
		return
	if route.is_empty(): return
	var goal := CitizenRoutes.graph.get_point_position(route[cursor])
	if body.position.distance_to(goal)<.22:
		body.set_meta("in_crossing",false)
		if cursor==route.size()-1:
			state="VISIT"
			dwell=12+(identity*7+cycle*11)%31
			# Stand to one side of the entrance while visiting.
			body.set_meta("activity","visiting "+destination.name)
			return
		var crossing := CitizenRoutes.crossings.has(Vector2i(route[cursor],route[cursor+1]))
		if crossing and not crossing_open():
			if model: model.purpose_pose="Wait"
			body.set_meta("activity","waiting for crossing")
			return
		cursor+=1
		body.set_meta("in_crossing",crossing)
		goal=CitizenRoutes.graph.get_point_position(route[cursor])
	if model: model.purpose_pose=""
	var direction := body.position.direction_to(goal)
	var chosen := Vector3.ZERO
	for angle in [0.0,.35,-.35,.7,-.7]:
		var candidate := direction.rotated(Vector3.UP,angle)
		# Keep avoidance within the walk corridor instead of drifting into a carriageway.
		if cursor>0:
			var predicted := body.position+candidate*.75
			var on_segment := Geometry3D.get_closest_point_to_segment(predicted,CitizenRoutes.graph.get_point_position(route[cursor-1]),goal)
			if predicted.distance_to(on_segment)>.65: continue
		var query := PhysicsRayQueryParameters3D.create(body.position+Vector3.UP*.9,body.position+Vector3.UP*.9+candidate*.75,5,[body.get_rid()])
		if body.get_world_3d().direct_space_state.intersect_ray(query).is_empty():
			chosen=candidate
			break
	if chosen==Vector3.ZERO:
		blocked_time+=delta
		if blocked_time>6:
			choose_destination()
			blocked_time=0
		return
	blocked_time=0
	body.rotation.y=lerp_angle(body.rotation.y,atan2(-chosen.x,-chosen.z),minf(delta*5,1))
	body.move_and_collide(chosen*minf(speed*delta,body.position.distance_to(goal)))
	body.set_meta("activity","walking to "+destination.name)
static func attach(system: Node,walkers: Array) -> void:
	CitizenRoutes.prepare()
	for i in range(walkers.size()):
		var walker: Dictionary=walkers[i]
		var edge := CitizenRoutes.nearest_edge(walker.body.position)
		walker.body.position=Geometry3D.get_closest_point_to_segment(walker.body.position,CitizenRoutes.graph.get_point_position(edge.x),CitizenRoutes.graph.get_point_position(edge.y))
		var brain := CitizenBrain.new()
		brain.identity=i
		brain.owner_system=system
		walker.body.set_meta("purpose_brain",true)
		walker.body.add_child(brain)
