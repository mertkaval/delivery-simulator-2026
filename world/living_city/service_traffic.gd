extends Node3D
## Persistent role routes with curved junction turns, stops and obstacle braking.
var fleet: Array[Dictionary]=[]
const ROLES = ["police_cruiser","police_cruiser","ambulance","fire_engine","school_bus","taxi_sedan","taxi_sedan"]
## Converted models (tools/prepare_sketchup_assets.py) for each role.
const MODELS = ["police_interceptor","civil_police_sedan","civil_ambulance","civil_fire_truck","civil_school_bus","civil_taxi","civil_taxi"]
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
	for i in range(ROLES.size()):
		var west := 253.7 if i<2 or i>4 else 469.7
		var east := 358.3 if i<2 else 518.3
		var corners := PackedVector3Array([Vector3(west,0,-259.7),Vector3(west,0,-676.3),Vector3(east,0,-676.3)])
		if i==4:
			corners.append_array(PackedVector3Array([Vector3(east,0,-638),Vector3(535,0,-638),Vector3(535,0,-619),Vector3(east,0,-611)]))
		elif i==3:
			corners.append_array(PackedVector3Array([Vector3(east,0,-477),Vector3(550,0,-477),Vector3(550,0,-459),Vector3(east,0,-459)]))
		elif i==2:
			corners.append_array(PackedVector3Array([Vector3(east,0,-319),Vector3(547,0,-319),Vector3(547,0,-309),Vector3(east,0,-309)]))
		corners.append(Vector3(east,0,-259.7))
		# Big vehicles get wider corners; the route keeps every turn a smooth arc.
		var route := SmoothRoute.from_corners(corners,9.0 if i in [2,3,4] else 8.0)
		var start := route.total*float(i)/ROLES.size()
		var car := TrafficDriver.spawn(self,MODELS[i],ROLES[i]+"_%d"%i,route,start,6.0 if i in [3,4] else 7.0)
		var body: CharacterBody3D=car.body
		body.set_meta("role",ROLES[i])
		body.set_meta("assignment",["north district patrol","south district patrol","hospital transfer circuit","station readiness circuit","school stop circuit","taxi rank circuit","taxi passenger circuit"][i])
		car.merge({"points":route.points,"wait":float(i*2),"stop_done":false,"parked":false,"role":ROLES[i],"lap":floori(start/route.total)})
		fleet.append(car)
func _physics_process(delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	var phase := fmod(get_parent().elapsed,64)
	var hour: float=get_parent().hour
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
		var direction := TrafficDriver.heading(car)
		var ns := absf(direction.z)>.7
		var red: bool=phase>=14 if ns else (phase<16 or phase>=30)
		var limit: float=car.cruise
		if red:
			for cross_value in (DowntownCatalog.STREET_Z if ns else [144,252,360,468,520]):
				var ahead: float=(cross_value-body.position.z)*direction.z if ns else (cross_value-body.position.x)*direction.x
				if ahead>8 and ahead<15+float(car.half): limit=0.0
		if TrafficDriver.blocked(car,2.5+float(car.speed)*.65,get_world_3d().direct_space_state): limit=0.0
		TrafficDriver.drive(car,delta,limit)
		body.set_meta("activity","yielding" if limit==0.0 else "following "+str(body.get_meta("assignment")))
