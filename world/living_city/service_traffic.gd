extends Node3D
## Downtown traffic: persistent civic role routes (police, ambulance, fire, school bus, taxis)
## with stops, plus the downtown street traffic. On _ready this node takes over the vehicles
## the downtown population spawned (they keep their models and loops) and adds two east-west
## loops and more cars, then drives them all with TrafficDriver.think: smooth following and
## SignalPlan stop lines on the population's signal phase (ns 0-14 s, ew 16-30 s, pedestrian
## scramble 32-64 s of the 64 s cycle).
var fleet: Array[Dictionary]=[]
## Downtown street traffic (population vehicles + the extra loops). "drivers" so CityAudio
## discovers it like CityTraffic.drivers.
var drivers: Array[Dictionary]=[]
var loops: Array[SmoothRoute]=[]
## Downtown signal clock (SignalPlan "downtown"): follows the population's phase, which its
## walkers use for the scramble crossing, but keeps running if that phase is held (the
## population holds it while anyone is still on a crossing; a stranded walker would otherwise
## keep every downtown light red for good).
var signal_clock := 0.0
var _held := 0.0
var _last_phase := -1.0
var _order_t := 0.0
const ROLES = ["police_cruiser","police_cruiser","ambulance","fire_engine","school_bus","taxi_sedan","taxi_sedan"]
## Converted models (tools/prepare_sketchup_assets.py) for each role.
const MODELS = ["police_interceptor","civil_police_sedan","civil_ambulance","civil_fire_truck","civil_school_bus","civil_taxi","civil_taxi"]
## Extra downtown cars per loop: [population loop A, population loop B, east-west -398, -538].
const EXTRA := [2, 6, 8, 8]
## East-west lane centres sit 3 m off the street centreline (the population loops' -261 / -675),
## north-south lanes 1.7 m.
const EW_LANE := 3.0
static func rounded_route(corners: PackedVector3Array,radius: float=7) -> PackedVector3Array:
	var result := PackedVector3Array()
	for i in range(corners.size()):
		var here := corners[i]
		var before := corners[posmod(i-1,corners.size())]
		var after := corners[(i+1)%corners.size()]
		var entry := here+here.direction_to(before)*radius
		var exit := here+here.direction_to(after)*radius
		for step in range(9):
			var t := float(step)/8
			result.append(entry.lerp(here,t).lerp(here.lerp(exit,t),t))
	return result
func _ready() -> void:
	var population := get_parent()
	for i in range(ROLES.size()):
		var west := 253.7 if i<2 or i>4 else 469.7
		var east := 358.3 if i<2 else 518.3
		# East-west legs in the population loops' lanes (3 m off the centreline).
		var north := -258.0-EW_LANE
		var south := -678.0+EW_LANE
		var corners := PackedVector3Array([Vector3(west,0,north),Vector3(west,0,south),Vector3(east,0,south)])
		if i==4:
			corners.append_array(PackedVector3Array([Vector3(east,0,-638),Vector3(535,0,-638),Vector3(535,0,-619),Vector3(east,0,-611)]))
		elif i==3:
			corners.append_array(PackedVector3Array([Vector3(east,0,-477),Vector3(550,0,-477),Vector3(550,0,-459),Vector3(east,0,-459)]))
		elif i==2:
			corners.append_array(PackedVector3Array([Vector3(east,0,-319),Vector3(547,0,-319),Vector3(547,0,-309),Vector3(east,0,-309)]))
		corners.append(Vector3(east,0,north))
		# Big vehicles get wider corners; the route keeps every turn a smooth arc. The school bus
		# turns tighter (6 m) into its pull-in so its 7.9 m body clears the square's bollards
		# (tests/traffic_long_vehicle_test.gd sweeps every service route).
		var route := SmoothRoute.from_corners(corners,6.0 if i==4 else (9.0 if i in [2,3] else 8.0))
		var start := route.total*float(i)/ROLES.size()
		var car := TrafficDriver.spawn(self,MODELS[i],ROLES[i]+"_%d"%i,route,start,6.0 if i in [3,4] else 7.0)
		var body: CharacterBody3D=car.body
		body.set_meta("role",ROLES[i])
		body.set_meta("assignment",["north district patrol","south district patrol","hospital transfer circuit","station readiness circuit","school stop circuit","taxi rank circuit","taxi passenger circuit"][i])
		car.merge({"points":route.points,"wait":float(i*2),"stop_done":false,"parked":false,"role":ROLES[i],"lap":floori(start/route.total)})
		fleet.append(car)
		SignalPlan.vehicles.append(car)
	# Street traffic: take over the population's loop vehicles (it then has none left to drive).
	var spawned: Variant = population.get("vehicles")
	if spawned is Array:
		for car: Dictionary in spawned:
			drivers.append(car)
			var r: SmoothRoute = car.route
			if not loops.has(r): loops.append(r)
		(spawned as Array).clear()
	while loops.size()<2:
		var pair: Array = [[252.0,360.0],[360.0,468.0]][loops.size()]
		loops.append(SmoothRoute.from_corners(PackedVector3Array([Vector3(pair[0]+1.7,0,-261),Vector3(pair[0]+1.7,0,-675),Vector3(pair[1]-1.7,0,-675),Vector3(pair[1]-1.7,0,-261)]),9.0))
	# East-west loops: along Kara Fatma (-398) eastbound and -538 westbound, closing over the
	# west street (x 144) and the population loops' east leg and top / bottom legs.
	loops.append(SmoothRoute.from_corners(PackedVector3Array([Vector3(145.7,0,-261),Vector3(145.7,0,-398+EW_LANE),Vector3(466.3,0,-398+EW_LANE),Vector3(466.3,0,-261)]),9.0))
	loops.append(SmoothRoute.from_corners(PackedVector3Array([Vector3(466.3,0,-538-EW_LANE),Vector3(145.7,0,-538-EW_LANE),Vector3(145.7,0,-675),Vector3(466.3,0,-675)]),9.0))
	var all: Array[Dictionary]=[]
	all.append_array(drivers)
	all.append_array(fleet)
	var serial := drivers.size()
	for li in range(EXTRA.size()):
		var route: SmoothRoute=loops[li]
		for k in range(0 if VehicleCatalog.legacy_traffic else int(EXTRA[li])):
			var s := TrafficDriver.free_spot(route,route.total*(float(k)+0.5)/float(EXTRA[li]),all,10.0)
			var id: String = VehicleCatalog.next_traffic_id() if (serial%5)!=2 else ["civil_taxi","civil_police_sedan","civil_postvan","civil_taxi"][serial%4]
			var car := TrafficDriver.spawn(self,id,"DowntownVehicle_%02d"%serial,route,s,8.5)
			drivers.append(car)
			all.append(car)
			serial+=1
	for car in drivers: SignalPlan.vehicles.append(car)

func _exit_tree() -> void:
	for car in drivers: SignalPlan.vehicles.erase(car)
	for car in fleet: SignalPlan.vehicles.erase(car)

func _physics_process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	var population := get_parent()
	var pe := float(population.get("elapsed"))
	if is_equal_approx(pe,_last_phase): _held+=delta
	_last_phase=pe
	signal_clock=pe+_held
	var clocks := {"downtown": signal_clock}
	var hour: float=population.get("hour")
	var night := hour<7 or hour>22
	var space := get_world_3d().direct_space_state
	_order_t-=delta
	if _order_t<=0.0:
		_order_t=2.0
		TrafficDriver.order(drivers)
	for i in range(drivers.size()):
		var car: Dictionary=drivers[i]
		var body: CharacterBody3D=car.body
		# At night only every third car is out.
		var active: bool=not night or i%3==0
		if body.visible!=active:
			body.visible=active
			body.collision_layer=1 if active else 0
		if not active: continue
		var dt := TrafficDriver.due(car,delta,camera)
		if dt<0.0: continue
		var lead := TrafficDriver.leader(drivers,i)
		var sig := SignalPlan.limit(car,clocks,SignalPlan.stops_for(car.route))
		TrafficDriver.think(car,dt,float(lead[0]),float(lead[1]),sig,space,5)
		body.set_meta("activity","waiting at a signal" if car.speed<0.2 and sig<0.5 else "driving")
	for car in fleet:
		var body: CharacterBody3D=car.body
		var distance := body.position.distance_to(camera.global_position) if camera else 0.0
		var active := distance<220
		body.visible=active
		body.collision_layer=1 if active else 0
		if not active: continue
		var school_duty: bool=car.role!="school_bus" or (hour>=7 and hour<10) or (hour>=14 and hour<17)
		if not school_duty and car.parked:
			body.set_meta("activity","school route off duty")
			continue
		if school_duty: car.parked=false
		if car.wait>0:
			car.wait-=delta
			body.set_meta("activity","scheduled stop")
			continue
		var route: SmoothRoute=car.route
		var lap := floori(float(car.s)/route.total)
		if lap!=int(car.lap):
			car.lap=lap
			car.wait=8.0 if car.role.begins_with("police") else 18.0
			car.stop_done=false
		# School and taxi stops use the eastbound return corridor's designated pull-up.
		var stop_z := -628.0 if car.role=="school_bus" else (-314.0 if car.role=="ambulance" else (-350.0 if car.role=="taxi_sedan" else -467.0))
		var stop_x := 532.0 if car.role in ["school_bus","ambulance","fire_engine"] else 500.0
		if body.position.x>stop_x and absf(body.position.z-stop_z)<2 and not car.stop_done:
			car.wait=18.0 if car.role=="school_bus" else 7.0
			car.stop_done=true
			car.parked=car.role=="school_bus"
			car.speed=0.0
			continue
		var dt := TrafficDriver.due(car,delta,camera)
		if dt<0.0: continue
		var sig := SignalPlan.limit(car,clocks,SignalPlan.stops_for(route))
		TrafficDriver.think(car,dt,INF,0.0,sig,space,5)
		body.set_meta("activity","yielding" if car.speed<0.2 else "following "+str(body.get_meta("assignment")))
