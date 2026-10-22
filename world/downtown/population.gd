extends "res://world/city_life.gd"
## Concentrated avenue/transit activity; distant actors sleep with collision disabled.
var vehicles: Array[Dictionary]=[]
var hour := 12.0
var clearance_hold := 0.0
const CLEARANCE_MAX := 8.0
func _ready() -> void:
	for block_id in [0,1,3,4,6,7]:
		var block := DowntownCatalog.blocks()[block_id]
		for i in range(5 if block_id%3==0 else 3):
			var x: float=block.end.x+1.2+(i%2)*.6
			var z: float=block.position.y+20+i*16
			add_walker([Vector3(x,.09,z),Vector3(x,.09,z-12)],block_id*6+i)
	# More people on the west and south pavements of every block.
	for block_id in range(9):
		var block := DowntownCatalog.blocks()[block_id]
		for i in range(4):
			var west := i%2==0
			var at := Vector3(block.position.x-1.2,.09,block.position.y+14+i*22) if west else Vector3(block.position.x+14+i*18,.09,block.end.y+1.2)
			add_walker([at,at+Vector3(0,0,-8)],100+block_id*4+i)
	for i in range(5):
		add_walker([Vector3(243.1,.09,-355+i),Vector3(243.1,.09,-355+i+.1)],40+i)
	for i in range(6):
		var x: float=187+i*3
		add_walker([Vector3(x,.09,-310),Vector3(x+1,.09,-313)],50+i)
	# Shoppers enter through the clear doorway and return to the pavement.
	add_walker([Vector3(170,.09,-268),Vector3(170,.09,-272.5)],60)
	add_walker([Vector3(202,.09,-268),Vector3(202,.09,-272.5)],61)
	# Protected crossing phase shared with vehicles.
	for i in range(4): add_walker([Vector3(241-(i%2)*.7,.09,-389.7+i*.6),Vector3(263,.09,-389.7+i*.6)],70+i,true)
	for i in range(3):
		add_cyclist(i)
		cyclists[-1].body.position=Vector3(473.1,.055,-310-i*95)
		cyclists[-1].direction=-1
	# Downtown loops around the blocks, with rounded corners (SmoothRoute) and the converted fleet.
	var loops: Array[SmoothRoute]=[]
	for pair in [[252.0,360.0],[360.0,468.0]]:
		loops.append(SmoothRoute.from_corners(PackedVector3Array([Vector3(pair[0]+1.7,0,-261),Vector3(pair[0]+1.7,0,-675),Vector3(pair[1]-1.7,0,-675),Vector3(pair[1]-1.7,0,-261)]),9.0))
	for i in range(18):
		var route: SmoothRoute=loops[0 if i<12 else 1]
		var count := 12 if i<12 else 6
		var slot := i if i<12 else i-12
		vehicles.append(TrafficDriver.spawn(self,VehicleCatalog.next_traffic_id(),"DowntownVehicle_%02d"%i,route,route.total*float(slot)/count,8.5))
	for z in [-328,-468,-608]:
		for i in range(2): add_walker([Vector3(529,.1,z+i*2),Vector3(561,.1,z)],80+i)
		# A converted security guard watches each civic entrance, facing the access road.
		var guard: Node3D=LivingAssets.standing_person(0)
		guard.position=Vector3(545,.05,z+5)
		guard.rotation.y=PI/2
		add_child(guard)
	CitizenBrain.attach(self,pedestrians)
	gather_benches()
	var services := preload("res://world/living_city/service_traffic.gd").new()
	services.name="CivicFleet"
	add_child(services)
func _physics_process(delta: float) -> void:
	var occupied := false
	for walker in pedestrians:
		if walker.body.visible and walker.body.get_meta("in_crossing",false): occupied=true
	# Clearance holds all approaches red until the last pedestrian reaches the curb, for at
	# most CLEARANCE_MAX seconds per cycle (a stuck walker can never freeze the signals).
	var holding: bool=fmod(elapsed,64)>63.7 and occupied
	if holding and clearance_hold<CLEARANCE_MAX: clearance_hold+=delta
	else:
		elapsed+=delta
		if fmod(elapsed,64)<1.0: clearance_hold=0.0
	var phase := fmod(elapsed,64)
	for i in range(3):
		if UrbanKit.materials.has("Signal%d"%i): UrbanKit.materials["Signal%d"%i].set_shader_parameter("phase",phase)
	for sign_node in get_parent().crossing_labels:
		sign_node.text="WALK" if phase>=32 and phase<38 else "WAIT"
		sign_node.modulate=Color("b4f8c5") if phase>=32 and phase<38 else Color("ef7948")
	var camera := get_viewport().get_camera_3d()
	var night := hour<7 or hour>22
	for i in range(pedestrians.size()):
		var walker: Dictionary=pedestrians[i]
		var body: CharacterBody3D=walker.body
		if body.has_meta("purpose_brain"): continue
		var active: bool=(not night or i%4==0) and (camera==null or body.position.distance_to(camera.global_position)<115)
		body.visible=active
		body.collision_layer=4 if active else 0
		if not active: continue
		var goal: Vector3=walker.route[walker.target]
		if body.position.distance_to(goal)<.2:
			walker.target=(walker.target+1)%walker.route.size()
			goal=walker.route[walker.target]
		var direction := body.position.direction_to(goal)
		var wait: bool=walker.crossing and phase<32 and (body.position.x<243 or body.position.x>261)
		var moving: bool=not wait and not blocked(body,direction,.65)
		body.rotation.y=lerp_angle(body.rotation.y,atan2(-direction.x,-direction.z),delta*8)
		if moving: body.move_and_collide(direction*minf(walker.speed*delta,body.position.distance_to(goal)))
		walker.phase+=delta*(5.5 if moving else .4)
		var swing: float=sin(walker.phase)*(.36 if moving else .015)
		walker.joints.HipL.rotation.x=swing
		walker.joints.HipR.rotation.x=-swing
		walker.joints.KneeL.rotation.x=maxf(0,-swing)*1.2
		walker.joints.KneeR.rotation.x=maxf(0,swing)*1.2
		walker.joints.ShoulderL.rotation.x=-swing*.7
		walker.joints.ShoulderR.rotation.x=swing*.7
	for i in range(vehicles.size()):
		var car: Dictionary=vehicles[i]
		var body: CharacterBody3D=car.body
		var active: bool=(not night or i%3==0) and (camera==null or body.position.distance_to(camera.global_position)<180)
		body.visible=active
		body.collision_layer=1 if active else 0
		if not active: continue
		var direction := TrafficDriver.heading(car)
		var north_south := absf(direction.z)>.7
		var red: bool=phase>=14 if north_south else (phase<16 or phase>=30)
		var limit: float=car.cruise
		if red:
			for crossing in (DowntownCatalog.STREET_Z if north_south else DowntownCatalog.STREET_X):
				var ahead: float=(crossing-body.position.z)*direction.z if north_south else (crossing-body.position.x)*direction.x
				if ahead>9 and ahead<17: limit=0.0
		if TrafficDriver.blocked(car,3.5,get_world_3d().direct_space_state): limit=0.0
		TrafficDriver.drive(car,delta,limit)
	for rider in cyclists:
		var body: CharacterBody3D=rider.body
		var active: bool=not night and (camera==null or body.position.distance_to(camera.global_position)<120)
		body.visible=active
		body.collision_layer=4 if active else 0
		if not active: continue
		var direction := Vector3(0,0,rider.direction)
		var stop := blocked(body,direction,3)
		for crossing in DowntownCatalog.STREET_Z:
			var ahead: float=(crossing-body.position.z)*rider.direction
			if phase>=14 and ahead>8 and ahead<13: stop=true
		rider.speed=move_toward(rider.speed,0 if stop else 3.4,delta*3)
		body.rotation.y=0 if rider.direction<0 else PI
		body.move_and_collide(direction*rider.speed*delta)
		if body.position.z<-664 or body.position.z>-272:
			rider.direction*=-1
			body.position.x=473.1 if rider.direction<0 else 475.1
		rider.phase+=delta*rider.speed*2
		for wheel in rider.wheels: wheel.rotate_x(-rider.speed*delta/.35)
		if rider.joints.is_empty():
			BikeRider.ride(rider,rider.speed*delta)
			continue
		for side in ["L","R"]:
			var phase_offset: float=rider.phase+(PI if side=="R" else 0)
			rider.joints["Hip"+side].rotation.x=1.1+sin(phase_offset)*.25
			rider.joints["Knee"+side].rotation.x=-1.55-sin(phase_offset)*.4

## Downtown kit benches (reuse_park_bench, batched by DowntownDistrict): courtyard benches get
## people sitting on them, the others are free seats for passers-by. MultiMesh instance data
## exists only with a renderer (headless runs skip this).
func gather_benches() -> void:
	if DisplayServer.get_name() == "headless": return
	var district := get_parent()
	var parts: Array = UrbanKit.get_parts("reuse_park_bench")
	if parts.is_empty(): return
	var piece: Transform3D = parts[0].transform
	var k := 0
	for batch in district.get_children():
		if not batch is MultiMeshInstance3D or batch.get_meta("prop", "") != "reuse_park_bench": continue
		var mm: MultiMesh = (batch as MultiMeshInstance3D).multimesh
		if mm.mesh != parts[0].mesh: continue
		for i in range(mm.instance_count):
			var bench: Transform3D = (batch as Node3D).global_transform * mm.get_instance_transform(i) * piece.affine_inverse()
			bench.origin.y = CitizenRoutes.ground_y(bench.origin)
			var slots := CitySeating.bench_slots(bench, "reuse_park_bench")
			var courtyard := false
			for b in DowntownCatalog.blocks():
				var c: Vector2 = b.get_center()
				if absf(bench.origin.x - c.x) < 16 and absf(absf(bench.origin.z - c.y) - 9) < 12: courtyard = true
			if courtyard and k % 2 == 0:
				var s: Dictionary = slots[k % 3]
				var sitter := CitySeating.seated_person(s, 600 + k)
				sitter.max_distance = 80.0
				add_child(sitter)
				CitySeating.sit(sitter, s, ["SitPhone", "Sit", "SitTalk"][k % 3])
				sitters.append(sitter)
			k += 1
			for s in slots:
				if s.user == null: seats.append(s)
