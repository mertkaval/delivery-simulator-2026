class_name CitizenBrain
extends Node
## A walking townsperson: daily destinations on the sidewalk graph (CitizenRoutes), natural
## walking (smoothed velocity and heading, rounded corners, personal walking speed, stride-
## matched animation through LivingCitizen.ground_speed), social avoidance of other people and
## the player (keep right, sidestep, slow behind someone, never leave the sidewalk corridor),
## waiting at kerbs for the signal or a gap in traffic, short pauses (phone, window shopping,
## standing), sitting down on free benches nearby (Sitting_Enter / Sitting_Exit), and going
## into buildings at the destination. People stand on the rendered walking surface
## (CitizenRoutes.ground_y). Distant brains think at a lower rate.
var body: CharacterBody3D
var model: LivingCitizen
var owner_system: Node
var identity := 0
var route := PackedInt64Array()
var cursor := 0
## WALK, WAIT_CROSS, PAUSE, VISIT, INSIDE, TO_SEAT, SIT_DOWN, SEATED, STAND_UP
var state := "WALK"
var destination := {}
var dwell := 0.0
var blocked_time := 0.0
var elapsed := 0.0
var cycle := 0
## Preferred walking speed (m/s).
var speed := 1.25
var base_speed := 1.25
var downtown := true
## Optional fixed loop (park strollers): followed instead of the graph.
var loop: PackedVector3Array = PackedVector3Array()
## Residents keep mostly to the residential streets (cross streets and side roads).
var resident := false
var velocity := Vector3.ZERO
var next_pause := 30.0
var pause_clip := ""
var face_yaw := INF
var seat: Dictionary = {}
var seat_timer := 0.0
var probe_timer := 0.0
var probe_dir := Vector3.ZERO
var think_accum := 0.0
var sleep := 0.0
var cell := Vector2i(1 << 30, 0)
var player: Node3D
var player_lookup := 0.0
const CELL := 4.0
## Camera position and each system's hour, read once per physics tick for every brain.
static var shared_frame := -1
static var camera_position := Vector3.ZERO
static var camera_known := false
static var hours := {}
static var grid := {}   ## Vector2i -> Array of CitizenBrain (shared by every system)

func _ready() -> void:
	body=get_parent() as CharacterBody3D
	for child in body.get_children():
		if child is LivingCitizen: model=child
	downtown=body.position.x>120
	# People's walking speeds: 1.05 - 1.55 m/s, a few slower.
	speed=1.05+0.5*LivingAssets.noise(identity+(1000 if downtown else 0),21)
	if LivingAssets.noise(identity,22)<0.12: speed=0.85+0.15*LivingAssets.noise(identity,23)
	if model and str(model.get_meta("role",""))=="retiree": speed=0.8+0.2*LivingAssets.noise(identity,23)
	base_speed=speed
	# People pass through each other's collision; they steer around one another instead.
	body.collision_mask=1
	next_pause=12.0+50.0*LivingAssets.noise(identity,24)
	choose_destination()

func _exit_tree() -> void:
	leave_cell()

func current_hour() -> float:
	if downtown: return owner_system.hour
	var app := owner_system.get_parent().get_parent()
	return app.session.hour() if "session" in app else 12.0

## Daily life by role (CitizenRoutine): where to go next.
var routine: CitizenRoutine

func choose_destination() -> void:
	cycle+=1
	if not loop.is_empty():
		state="WALK"
		body.set_meta("purpose","park: a stroll round the square")
		body.set_meta("daily_goal","park")
		return
	CitizenRoutes.prepare()
	if routine==null:
		routine=CitizenRoutine.new(identity,downtown,resident,str(model.get_meta("role","resident")) if model else "resident",body.position)
	var chosen := routine.next(current_hour(),body.position,destination,state=="INSIDE",cycle)
	if chosen.get("stay",false):
		dwell=40.0+float((identity*7+cycle*11)%50)
		return
	if chosen.is_empty():
		route=PackedInt64Array()
		return
	var place: String=chosen.place
	if model: model.locomotion=routine.gait(place)
	speed=base_speed*routine.pace(place)
	destination=chosen
	body.set_meta("in_crossing",false)
	route=CitizenRoutes.path(body.position,chosen.node)
	cursor=0
	state="WALK"
	body.set_meta("purpose",place+": "+str(chosen.name))
	body.set_meta("daily_goal",place)
	body.set_meta("routine",routine.routine_name)

func crossing_open(from: Vector3, to: Vector3, waited: float = 0.0) -> bool:
	if downtown:
		var phase := fmod(owner_system.elapsed,64)
		return phase>=32 and phase<38
	# Signalled avenue crossings.
	if absf(from.x)<10 and absf(to.x)<10 and absf(from.z-to.z)<1:
		return owner_system.safe_to_cross(body.position.z)
	# Zebra at a junction: wait for a gap in traffic near the crossing.
	var mid := (from+to)*0.5
	# After a long wait people accept a smaller gap (cars yield to anyone on the crossing).
	var gap := 16.0 if waited<10.0 else 7.0
	var traffic: Node = owner_system.traffic if "traffic" in owner_system else null
	if traffic!=null and "cars" in traffic:
		for car: Node3D in traffic.cars:
			if car.position.distance_squared_to(mid)<gap*gap: return false
	return true

func goal_point() -> Vector3:
	if not loop.is_empty(): return loop[cursor%loop.size()]
	return CitizenRoutes.graph.get_point_position(route[cursor])

func segment_start() -> Vector3:
	if not loop.is_empty(): return loop[(cursor-1+loop.size())%loop.size()]
	return CitizenRoutes.graph.get_point_position(route[cursor-1]) if cursor>0 else body.position

func next_is_crossing() -> bool:
	if not loop.is_empty() or cursor>=route.size()-1: return false
	return CitizenRoutes.crossings.has(Vector2i(route[cursor],route[cursor+1]))

func set_pose(clip: String) -> void:
	if model: model.purpose_pose=clip

## Script-time counters read by tests/capture_npc_life.gd (frame-time reports).
static var prof_usec := 0
static var prof_calls := 0
func _physics_process(delta: float) -> void:
	var t0 := Time.get_ticks_usec()
	prof_calls+=1
	_physics_body(delta)
	prof_usec+=Time.get_ticks_usec()-t0
func _physics_body(delta: float) -> void:
	elapsed+=delta
	# Out of range (> 115 m): look again in a third of a second.
	if sleep>0.0:
		sleep-=delta
		return
	var frame := Engine.get_physics_frames()
	if frame!=shared_frame:
		shared_frame=frame
		hours.clear()
		var camera := get_viewport().get_camera_3d()
		camera_known=camera!=null
		if camera_known: camera_position=camera.global_position
	var distance := body.position.distance_to(camera_position) if camera_known else 0.0
	var key := owner_system.get_instance_id()
	if not hours.has(key): hours[key]=current_hour()
	var active := distance<115 and (float(hours[key])>=6 or identity%4==0)
	var inside := state=="INSIDE"
	body.visible=active and not inside
	body.collision_layer=4 if active and not inside else 0
	if not active:
		if model: model.ground_speed=0.0
		sleep=0.33
		return
	# Thinking rate by distance: every tick up close, every 2nd tick to 70 m, every 6th beyond.
	think_accum+=delta
	var every := 1.0 if distance<30 else (2.0 if distance<70 else 6.0)
	if think_accum<delta*(every-0.5): return
	var step := think_accum
	think_accum=0.0
	match state:
		"INSIDE", "VISIT", "PAUSE":
			dwell-=step
			stop(step)
			if dwell<=0:
				set_pose("")
				if state=="PAUSE": state="WALK"
				else: choose_destination()
			return
		"WAIT_CROSS":
			stop(step)
			dwell+=step
			if crossing_open(goal_point(),CitizenRoutes.graph.get_point_position(route[cursor+1]),dwell):
				set_pose("")
				advance()
			return
		"TO_SEAT", "SIT_DOWN", "SEATED", "STAND_UP":
			seat_step(step)
			return
	if loop.is_empty() and route.is_empty():
		choose_destination()
		if route.is_empty():
			# No path from here: stand a while before trying again.
			state="PAUSE"
			dwell=5.0
		return
	walk(step,distance)

func stop(step: float) -> void:
	velocity=velocity.move_toward(Vector3.ZERO,3.0*step)
	body.position+=velocity*step
	if face_yaw!=INF: turn_to(face_yaw,step,2.5)
	if model: model.ground_speed=velocity.length()

func turn_to(yaw: float,step: float,rate: float=3.2) -> void:
	var diff := wrapf(yaw-body.rotation.y,-PI,PI)
	var max_turn := rate*step
	body.rotation.y+=clampf(diff*minf(1.0,step*7.0),-max_turn,max_turn)

func advance() -> void:
	var crossing := next_is_crossing()
	cursor+=1
	if not loop.is_empty(): cursor%=loop.size()
	body.set_meta("in_crossing",crossing)
	state="WALK"
	face_yaw=INF

func arrive() -> void:
	body.set_meta("in_crossing",false)
	destination["reached"]=true
	var type: String=destination.get("type","")
	var place: String=destination.get("place","")
	var building: int=destination.get("building",-1)
	face_yaw=INF
	if CitizenRoutine.STOP_POSE.has(place):
		# The job at this stop: on duty, sweeping, a photo, a drop at the door, kneeling at the work.
		state="VISIT"
		var pose: String=CitizenRoutine.STOP_POSE[place]
		if place=="site" and (identity+cycle)%3==0: pose="Interact"
		dwell=(25.0 if place in ["beat","post","site"] else 12.0)+float((identity*7+cycle*5)%20)
		if place=="post": dwell+=40.0
		if place=="sights": dwell=6.0+float((identity+cycle)%5)
		if place=="rounds": dwell=4.0
		set_pose(pose)
		var doing: String={"Duty": "on duty", "Sweep": "sweeping the pavement", "Photo": "taking a photo", "Interact": "at a door", "Kneel": "working"}.get(pose,"working")
		body.set_meta("activity",doing+" at "+str(destination.name))
	elif building>=0 or building==100:
		# Goes in through the door; looks at the routine again on coming out.
		state="INSIDE"
		dwell=40+(identity*7+cycle*11)%50
		if place=="lunch": dwell=30+(identity*5)%30
		body.set_meta("activity","inside "+str(destination.name))
	elif place=="stroll" or type=="street":
		if LivingAssets.noise(identity,cycle*11+5)<0.45 and try_seat(): return
		state="VISIT"
		dwell=4+(identity*5+cycle*3)%8
		set_pose(["Look","Phone","Wait","FoldArms"][(identity+cycle)%4])
		body.set_meta("activity","out for a walk")
	else:
		state="VISIT"
		dwell=6+(identity*5+cycle*3)%10
		set_pose(["Phone","Wait","Look","Talk"][(identity+cycle)%4] if type!="transit" else "Wait")
		body.set_meta("activity","at "+str(destination.name))

func walk(step: float,distance: float) -> void:
	var goal := goal_point()
	var flat := Vector3(goal.x,body.position.y,goal.z)
	var to_goal := flat-body.position
	var d := to_goal.length()
	var crossing_next := next_is_crossing()
	var last := loop.is_empty() and cursor==route.size()-1
	var arrive_radius := 0.3 if (crossing_next or last) else 0.55
	if d<arrive_radius:
		# At a kerb / node: off any crossing (even if the next leg is another crossing).
		body.set_meta("in_crossing",false)
		if last:
			arrive()
			return
		if crossing_next and not crossing_open(goal,CitizenRoutes.graph.get_point_position(route[cursor+1])):
			state="WAIT_CROSS"
			dwell=0.0
			var across := CitizenRoutes.graph.get_point_position(route[cursor+1])-goal
			face_yaw=atan2(-across.x,-across.z)
			set_pose("Wait" if LivingAssets.noise(identity,cycle)<0.7 else "Phone")
			body.set_meta("activity","waiting for crossing")
			return
		advance()
		goal=goal_point()
		flat=Vector3(goal.x,body.position.y,goal.z)
		to_goal=flat-body.position
		d=to_goal.length()
		crossing_next=next_is_crossing()
		last=loop.is_empty() and cursor==route.size()-1
	var desired := to_goal/maxf(d,0.001)
	# Round the corner: blend towards the next leg before reaching the node.
	if not crossing_next and not last and d<1.8:
		var after: Vector3
		if loop.is_empty(): after=CitizenRoutes.graph.get_point_position(route[cursor+1])
		else: after=loop[(cursor+1)%loop.size()]
		var leg := Vector3(after.x-goal.x,0,after.z-goal.z).normalized()
		desired=desired.lerp(leg,(1.8-d)/1.8*0.55).normalized()
	var in_crossing: bool=body.get_meta("in_crossing",false)
	var pace := speed*(1.2 if in_crossing else 1.0)*(1.0+0.04*sin(elapsed*0.37+identity))
	var steer := avoid(desired,step) if distance<70 else desired
	var slow: float=steer.y
	steer.y=0
	var want := steer.normalized()*pace*slow
	# Static obstacles (layer 1: walls, props, parked vehicles, the player): look ahead.
	probe_timer-=step
	if probe_timer<=0 and distance<70:
		probe_timer=0.25
		probe_dir=Vector3.ZERO
		if want.length()>0.1 and not clear(want.normalized(),0.85):
			for angle: float in [.45,-.45,.9,-.9]:
				var candidate := want.normalized().rotated(Vector3.UP,angle)
				if clear(candidate,0.85) and within_corridor(candidate):
					probe_dir=candidate
					break
			if probe_dir==Vector3.ZERO: probe_dir=Vector3.UP   # blocked
	# On a crossing the cars wait for people (TrafficDriver rays): someone stopped there for a
	# car's bumper would hold the car, and the car them, for good. After a moment they walk on.
	if probe_dir==Vector3.UP and in_crossing and blocked_time>1.5:
		probe_dir=Vector3.ZERO
	if probe_dir==Vector3.UP:
		want=Vector3.ZERO
		blocked_time+=step
		if blocked_time>6:
			blocked_time=0
			choose_destination()
	elif probe_dir!=Vector3.ZERO:
		want=probe_dir*want.length()
		blocked_time=0
	elif not in_crossing:
		blocked_time=0
	var accel := 1.8 if want.length()>velocity.length() else 3.2
	velocity=velocity.move_toward(want,accel*step)
	var next := body.position+velocity*step
	# Never leave the sidewalk corridor around the current leg.
	var a := segment_start()
	var on_leg := Geometry3D.get_closest_point_to_segment(Vector3(next.x,0,next.z),Vector3(a.x,0,a.z),Vector3(goal.x,0,goal.z))
	var off := Vector3(next.x,0,next.z)-on_leg
	var limit := 0.45 if in_crossing else 0.85
	if off.length()>limit: next=Vector3(on_leg.x,next.y,on_leg.z)+off.normalized()*limit
	next.y=CitizenRoutes.ground_y(next)
	body.position=next
	if velocity.length()>0.08: turn_to(atan2(-velocity.x,-velocity.z),step)
	if model: model.ground_speed=velocity.length()
	update_cell()
	# Occasional pause, a bench to rest on, or a glance at a shop window.
	if not in_crossing and not crossing_next and loop.is_empty():
		next_pause-=step
		if next_pause<=0:
			next_pause=25.0+45.0*LivingAssets.noise(identity,cycle*7+3)
			start_pause()
	body.set_meta("activity","walking to "+str(destination.get("name","the park")))

func within_corridor(direction: Vector3) -> bool:
	if cursor==0 and loop.is_empty(): return true
	var predicted := body.position+direction*0.75
	var on_segment := Geometry3D.get_closest_point_to_segment(predicted,segment_start(),goal_point())
	return Vector2(predicted.x-on_segment.x,predicted.z-on_segment.z).length()<0.8

func clear(direction: Vector3,length: float) -> bool:
	var from := body.position+Vector3.UP*.9
	var query := PhysicsRayQueryParameters3D.create(from,from+direction*length,1,[body.get_rid()])
	return body.get_world_3d().direct_space_state.intersect_ray(query).is_empty()

## Social steering: returns the steering direction with the speed factor in y.
func avoid(desired: Vector3,step: float) -> Vector3:
	var right := Vector3(-desired.z,0,desired.x)
	var push := Vector3.ZERO
	var slow := 1.0
	for dx in [-1,0,1]:
		for dz in [-1,0,1]:
			var c := cell+Vector2i(dx,dz)
			if not grid.has(c): continue
			for other: CitizenBrain in grid[c]:
				if other==self or not other.body.visible: continue
				var r := steer_from(other,desired,right)
				push+=Vector3(r.x,0,r.z)
				slow=minf(slow,r.y)
	var p := find_player()
	if p!=null:
		var rel := p.global_position-body.position
		rel.y=0
		var dist := rel.length()
		if dist<3.5 and dist>0.001:
			var ahead := rel.dot(desired)
			var lateral := rel.dot(right)
			if ahead>-0.2 and absf(lateral)<1.0:
				var side := -signf(lateral) if absf(lateral)>0.15 else 1.0
				push+=right*side*(1.0-dist/3.5)*1.8
				if ahead>0 and dist<1.1: slow=minf(slow,0.3)
			if dist<0.9: push-=rel/dist*(0.9-dist)*3.0
	var out := (desired+push)
	if out.length()<0.05: out=desired*0.05
	out=out.normalized()
	out.y=slow
	return out

## One neighbour's influence: lateral push in x/z, speed factor in y.
func steer_from(other: CitizenBrain,desired: Vector3,right: Vector3) -> Vector3:
	var push := Vector3.ZERO
	var slow := 1.0
	var rel := other.body.position-body.position
	rel.y=0
	var dist := rel.length()
	if dist>2.8 or dist<0.001: return Vector3(0,1,0)
	var ahead := rel.dot(desired)
	var lateral := rel.dot(right)
	if ahead>0.0 and absf(lateral)<0.8:
		var oncoming := other.velocity.dot(desired)<-0.2
		if oncoming or other.velocity.length()<0.2:
			# Pass on the right of oncoming people, around anyone standing still.
			var side := -signf(lateral) if absf(lateral)>0.15 else 1.0
			push+=right*side*(1.0-dist/2.8)*1.3
		elif dist<1.6:
			# Walking the same way and catching up: slow down or overtake on the left.
			var ratio := other.velocity.length()/maxf(speed,0.1)
			if ratio<0.8 and dist>0.9: push-=right*(1.0-dist/1.6)*0.9
			else: slow=minf(slow,clampf(ratio+(dist-0.8)*0.5,0.35,1.0))
	if dist<0.7: push-=rel/dist*(0.7-dist)*3.0
	return Vector3(push.x,slow,push.z)

func find_player() -> Node3D:
	player_lookup-=0.02
	if player!=null and is_instance_valid(player): return player
	if player_lookup>0: return null
	player_lookup=3.0
	var n: Node=owner_system
	while n!=null:
		if "player" in n and n.get("player") is Node3D:
			player=n.get("player")
			return player
		n=n.get_parent()
	return null

func update_cell() -> void:
	var c := Vector2i(floori(body.position.x/CELL),floori(body.position.z/CELL))
	if c==cell: return
	leave_cell()
	cell=c
	if not grid.has(c): grid[c]=[]
	(grid[c] as Array).append(self)

func leave_cell() -> void:
	if grid.has(cell):
		(grid[cell] as Array).erase(self)
		if (grid[cell] as Array).is_empty(): grid.erase(cell)

func neighbours() -> Array:
	var out: Array=[]
	for dx in [-1,0,1]:
		for dz in [-1,0,1]:
			var c := cell+Vector2i(dx,dz)
			if grid.has(c): out.append_array(grid[c])
	return out

## A short stop: phone, a look at the shop window beside the walk, a seat on a free bench.
func start_pause() -> void:
	var roll := LivingAssets.noise(identity,cycle*13+int(elapsed))
	if roll<0.3 and try_seat(): return
	state="PAUSE"
	dwell=4.0+6.0*LivingAssets.noise(identity,cycle*5+int(elapsed))
	velocity*=0.5
	var window := Vector3.ZERO
	if roll<0.65:
		var leg := (goal_point()-segment_start())
		leg.y=0
		leg=leg.normalized()
		for side: float in [1.0,-1.0]:
			var across := Vector3(-leg.z,0,leg.x)*side
			var from := body.position+Vector3.UP*1.3
			var hit := body.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from,from+across*4.0,1,[body.get_rid()]))
			if not hit.is_empty() and absf((hit.normal as Vector3).y)<0.3:
				window=across
				break
	if window!=Vector3.ZERO:
		face_yaw=atan2(-window.x,-window.z)
		set_pose("Look")
		body.set_meta("activity","looking in a shop window")
	else:
		face_yaw=INF
		set_pose("Phone" if roll<0.85 else "Wait")
		body.set_meta("activity","checking the phone" if roll<0.85 else "standing")

func try_seat() -> bool:
	if model==null or not model.humanoid or not ("seats" in owner_system): return false
	var best: Dictionary = {}
	var best_d := 7.0
	for s: Dictionary in owner_system.seats:
		if s.user!=null: continue
		var p: Vector3=(s.frame as Transform3D).origin
		var dd := Vector2(p.x-body.position.x,p.z-body.position.z).length()
		if dd<best_d:
			best_d=dd
			best=s
	if best.is_empty(): return false
	seat=best
	seat.user=self
	state="TO_SEAT"
	seat_timer=0.0
	body.set_meta("activity","going to sit on a bench")
	return true

func seat_step(step: float) -> void:
	var f: Transform3D=seat.frame
	match state:
		"TO_SEAT":
			var stand := CitySeating.standing_origin(model,seat)
			var target := f*Vector3(0,0,stand.z+0.45) if seat_timer<0.5 else f*Vector3(0,0,stand.z)
			var to := Vector3(target.x-body.position.x,0,target.z-body.position.z)
			if to.length()<0.12:
				if seat_timer<0.5:
					seat_timer=0.5
					return
				velocity=Vector3.ZERO
				model.ground_speed=0.0
				# Turn the back to the bench, then sit.
				var face := atan2(-(f.basis.z.x),-(f.basis.z.z))
				turn_to(face,step,3.0)
				if absf(wrapf(face-body.rotation.y,-PI,PI))<0.08:
					body.rotation.y=face
					state="SIT_DOWN"
					seat_timer=model.play_once("SitDown")
					set_pose("Sit")
				return
			var want := to.normalized()*minf(speed*0.8,to.length()*2.5+0.2)
			velocity=velocity.move_toward(want,2.5*step)
			body.position+=velocity*step
			body.position.y=lerpf(body.position.y,(f*Vector3(0,float(seat.floor),0)).y,0.2)
			if velocity.length()>0.08: turn_to(atan2(-velocity.x,-velocity.z),step)
			model.ground_speed=velocity.length()
		"SIT_DOWN":
			seat_timer-=step
			var total: float=maxf(model.players[0].get_animation("SitDown").length,0.1) if model.players[0].has_animation("SitDown") else 1.0
			var k := smoothstep(0.0,1.0,1.0-seat_timer/total)
			body.global_transform=CitySeating.pose(seat,CitySeating.standing_origin(model,seat).lerp(CitySeating.seated_origin(model,seat),k))*model.transform.affine_inverse()
			if seat_timer<=0:
				state="SEATED"
				seat_timer=20.0+40.0*LivingAssets.noise(identity,cycle*3+7)
				set_pose(["Sit","SitPhone","Sit","SitTalk"][(identity+cycle)%4])
				body.set_meta("activity","sitting on a bench")
		"SEATED":
			seat_timer-=step
			model.ground_speed=0.0
			if seat_timer<=0:
				state="STAND_UP"
				set_pose("")
				seat_timer=model.play_once("StandUp")
		"STAND_UP":
			seat_timer-=step
			var total: float=maxf(model.players[0].get_animation("StandUp").length,0.1) if model.players[0].has_animation("StandUp") else 1.0
			var k := smoothstep(0.0,1.0,seat_timer/total)
			body.global_transform=CitySeating.pose(seat,CitySeating.standing_origin(model,seat).lerp(CitySeating.seated_origin(model,seat),k))*model.transform.affine_inverse()
			if seat_timer<=0:
				seat.user=null
				seat={}
				body.rotation.x=0
				body.rotation.z=0
				# Back to the walk: route on from here.
				var dest: int=destination.get("node",-1)
				body.set_meta("in_crossing",false)
				if destination.get("reached",false):
					choose_destination()
					return
				if dest>=0:
					route=CitizenRoutes.path(body.position,dest)
					cursor=0
				state="WALK"

static func attach(system: Node,walkers: Array) -> void:
	CitizenRoutes.prepare()
	for i in range(walkers.size()):
		var walker: Dictionary=walkers[i]
		var brain := CitizenBrain.new()
		brain.identity=i
		brain.owner_system=system
		brain.resident=walker.get("resident",false)
		if walker.has("loop"):
			brain.loop=walker.loop
		else:
			var edge := CitizenRoutes.nearest_edge(walker.body.position)
			walker.body.position=Geometry3D.get_closest_point_to_segment(walker.body.position,CitizenRoutes.graph.get_point_position(edge.x),CitizenRoutes.graph.get_point_position(edge.y))
		walker.body.position.y=CitizenRoutes.ground_y(walker.body.position)
		walker.body.set_meta("purpose_brain",true)
		walker.body.add_child(brain)
