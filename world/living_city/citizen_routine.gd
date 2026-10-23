class_name CitizenRoutine
extends RefCounted
## A townsperson's daily life, fixed per person (no random wandering): a timetable by role and the
## person's own places and circuits on the sidewalk graph (CitizenRoutes). CitizenBrain asks
## next() where to go when it has arrived or come out of a building, and walks there.

## Daily routine by role: [hour, place]. Fixed places (home, work, lunch, errand, transit, post,
## site) are this person's own (see persona()); circuits (beat, sweep, run, sights, rounds,
## stroll) are fixed loops of stops walked in order while the slot lasts. Hours shift by up to
## +-0.5 h per person so a street does not empty at once.
const ROUTINES := {
	"office": [[0.0, "home"], [7.8, "work"], [12.0, "lunch"], [13.1, "work"], [17.6, "errand"], [18.8, "home"]],
	"commuter": [[0.0, "home"], [7.3, "transit"], [8.2, "work"], [12.3, "lunch"], [13.2, "work"], [17.2, "transit"], [18.2, "home"]],
	"student": [[0.0, "home"], [8.4, "work"], [12.5, "lunch"], [13.5, "work"], [15.5, "errand"], [17.0, "stroll"], [19.5, "home"]],
	"retiree": [[0.0, "home"], [8.5, "errand"], [10.0, "stroll"], [12.0, "lunch"], [14.0, "stroll"], [16.5, "errand"], [18.0, "home"]],
	"resident": [[0.0, "home"], [8.0, "errand"], [9.5, "stroll"], [12.0, "lunch"], [14.0, "errand"], [16.0, "stroll"], [19.0, "home"]],
	"tourist": [[0.0, "home"], [9.0, "sights"], [13.0, "lunch"], [14.2, "sights"], [19.5, "lunch"], [21.0, "home"]],
	"jogger": [[0.0, "home"], [6.5, "run"], [8.5, "home"], [9.2, "work"], [17.5, "run"], [19.0, "home"]],
	"police": [[0.0, "home"], [7.0, "beat"], [12.5, "lunch"], [13.2, "beat"], [19.0, "home"]],
	"security": [[0.0, "home"], [7.5, "post"], [12.5, "lunch"], [13.2, "post"], [19.0, "home"]],
	"street_cleaner": [[0.0, "home"], [6.0, "sweep"], [11.5, "lunch"], [12.3, "sweep"], [16.0, "home"]],
	"construction": [[0.0, "home"], [7.0, "site"], [12.0, "lunch"], [12.8, "site"], [17.0, "home"]],
	"courier": [[0.0, "home"], [8.0, "rounds"], [12.5, "lunch"], [13.2, "rounds"], [18.5, "home"]],
	"worker": [[0.0, "home"], [7.5, "work"], [12.0, "lunch"], [12.8, "work"], [18.0, "errand"], [19.0, "home"]],
}
## Role -> routine (roles not listed live like residents).
const ROUTINE_OF := {"office": "office", "commuter": "commuter", "student": "student", "retiree": "retiree",
	"tourist": "tourist", "jogger": "jogger", "police": "police", "security": "security", "street_cleaner": "street_cleaner",
	"construction": "construction", "delivery_driver": "courier", "moto_courier": "courier", "bike_courier": "courier",
	"paramedic": "worker", "warehouse": "worker", "taxi_driver": "worker", "bus_driver": "worker", "cashier": "worker",
	"barista": "worker", "baker": "worker", "chef": "worker", "server": "worker", "doner": "worker", "pizza": "worker",
	"concierge": "worker"}
## What a role does at a stop of its circuit, or at a fixed outdoor place.
const STOP_POSE := {"beat": "Duty", "post": "Duty", "sweep": "Sweep", "sights": "Photo", "rounds": "Interact", "site": "Kneel"}
const CIRCUITS := ["beat", "sweep", "run", "sights", "rounds", "stroll"]
var identity := 0
var downtown := false
var resident := false
var role := "resident"
var routine_name := "resident"
var places := {}          ## place -> destination Dictionary (fixed per person)
var circuits := {}        ## circuit -> Array of destination Dictionaries
var circuit_step := 0
var slot_place := ""
var hour_shift := 0.0

func slot_for(hour: float) -> String:
	var table: Array = ROUTINES[routine_name]
	var place: String = table[0][1]
	for entry: Array in table:
		if hour>=float(entry[0])+hour_shift: place=entry[1]
	return place

func in_district(candidate: Dictionary) -> bool:
	return (CitizenRoutes.graph.get_point_position(candidate.node).x>120)==downtown

## Deterministic choice among `pool` (destinations): the k nearest to `anchor`, picked by `salt`.
func pick_near(pool: Array, anchor: Vector3, k: int, salt: int) -> Dictionary:
	if pool.is_empty(): return {}
	var sorted := pool.duplicate()
	sorted.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return CitizenRoutes.graph.get_point_position(a.node).distance_squared_to(anchor)<CitizenRoutes.graph.get_point_position(b.node).distance_squared_to(anchor))
	return sorted[posmod(identity*31+salt*17,mini(k,sorted.size()))]

func of_type(types: Array) -> Array:
	var out: Array = []
	for d: Dictionary in CitizenRoutes.destinations:
		if d.type in types and in_district(d): out.append(d)
	return out

## Sidewalk nodes between `near` and `far` metres of `anchor`, `count` of them chosen by this
## person, ordered round the anchor (a loop walked in order).
func street_loop(anchor: Vector3, near: float, far: float, count: int, salt: int) -> Array:
	var found: Array = []
	for id in CitizenRoutes.graph.get_point_ids():
		var q := CitizenRoutes.graph.get_point_position(id)
		if (q.x>120)!=downtown: continue
		var dd := Vector2(q.x-anchor.x,q.z-anchor.z).length()
		if dd>=near and dd<=far: found.append(id)
	var chosen: Array = []
	var n := found.size()
	for i in range(mini(count,n)):
		var id: int=found[posmod(identity*53+salt*29+i*(n/maxi(count,1)+7),n)]
		if not chosen.has(id): chosen.append(id)
	chosen.sort_custom(func(a: int, b: int) -> bool:
		var pa := CitizenRoutes.graph.get_point_position(a)-anchor
		var pb := CitizenRoutes.graph.get_point_position(b)-anchor
		return atan2(pa.z,pa.x)<atan2(pb.z,pb.x))
	var out: Array = []
	for id: int in chosen: out.append({"node":id,"type":"street","name":"the street","building":-1})
	return out

## This person's own places (CitizenRoutes must be prepared): home near where they live
## (`here`), a workplace for the role, the cafe near work they lunch at, the shop near home they
## run errands to, and their circuits.
func _init(person: int, in_downtown: bool, is_resident: bool, person_role: String, here: Vector3) -> void:
	identity=person
	downtown=in_downtown
	resident=is_resident
	role=person_role
	routine_name=str(ROUTINE_OF.get(role,"resident"))
	if routine_name=="resident" and not resident and LivingAssets.noise(identity,41)<0.35: routine_name="commuter"
	hour_shift=(LivingAssets.noise(identity,40)-0.5)*1.0
	var homes := of_type(["home"])
	if resident:
		var local: Array = []
		for d: Dictionary in homes:
			var q := CitizenRoutes.graph.get_point_position(d.node)
			if q.x<120 and absf(q.x)>12: local.append(d)
		if not local.is_empty(): homes=local
	places["home"]=pick_near(homes,here,4,1)
	var home_at: Vector3 = CitizenRoutes.graph.get_point_position(places.home.node) if not (places.home as Dictionary).is_empty() else here
	var work_types: Array = ["service"] if role=="paramedic" else (["shop","cafe"] if role in ["cashier","barista","baker","chef","server","doner","pizza"] else ["work"])
	var works := of_type(work_types)
	if works.is_empty(): works=of_type(["work","shop","service"])
	places["work"]=works[posmod(identity*37+11,works.size())] if not works.is_empty() else places.home
	var work_at: Vector3 = CitizenRoutes.graph.get_point_position(places.work.node) if not (places.work as Dictionary).is_empty() else here
	places["lunch"]=pick_near(of_type(["cafe"]),home_at if routine_name in ["resident","retiree"] else work_at,3,2)
	places["errand"]=pick_near(of_type(["shop"]),home_at,3,3)
	places["transit"]=pick_near(of_type(["transit"]),home_at,2,4)
	places["post"]=places.work
	places["site"]=places.work
	for key: String in places.keys():
		if (places[key] as Dictionary).is_empty(): places[key]=places.home if not (places.home as Dictionary).is_empty() else places.errand
	var landmarks: Array = []
	for d: Dictionary in CitizenRoutes.destinations:
		if in_district(d) and (int(d.building)>=0 or int(d.building)==100): landmarks.append(d)
	var sights: Array = []
	for i in range(4):
		if landmarks.is_empty(): break
		var d: Dictionary=landmarks[posmod(identity*19+i*(landmarks.size()/4+3),landmarks.size())]
		if not sights.has(d): sights.append(d)
	if sights.is_empty(): sights=street_loop(home_at,40.0,200.0,4,9)
	circuits["sights"]=sights
	var rounds: Array = []
	var stops := of_type(["shop","work","cafe"])
	for i in range(5):
		if stops.is_empty(): break
		var d: Dictionary=stops[posmod(identity*23+i*(stops.size()/5+2),stops.size())]
		if not rounds.has(d): rounds.append(d)
	circuits["rounds"]=rounds
	circuits["beat"]=street_loop(work_at,25.0,110.0,4,5)
	circuits["sweep"]=street_loop(work_at,8.0,60.0,6,6)
	circuits["run"]=street_loop(home_at,70.0,220.0,5,7)
	circuits["stroll"]=street_loop(home_at,20.0,110.0,3,8)


## Where to go now: {"stay": true} (inside the building the timetable wants: stay in), {} (nowhere
## reachable) or a destination Dictionary (node, type, name, building, place). `current` is where
## the person last went, `inside` whether they are in its building.
func next(hour: float, here: Vector3, current: Dictionary, inside: bool, cycle: int) -> Dictionary:
	var place := slot_for(hour)
	if place=="transit" and not downtown: place="errand"
	var here_node := CitizenRoutes.graph.get_closest_point(here)
	var chosen: Dictionary = {}
	if place in CIRCUITS:
		if place!=slot_place: circuit_step=0
		var stops: Array = circuits.get(place,[])
		if stops.is_empty(): stops=circuits.get("stroll",[])
		for attempt in range(mini(2,stops.size())):
			chosen=stops[circuit_step%stops.size()]
			circuit_step+=1
			if chosen.node!=here_node: break
	else:
		chosen=places.get(place,{})
		if inside and not chosen.is_empty() and chosen.node==current.get("node",-1):
			slot_place=place
			return {"stay": true}
		# Already there and it is not a door to go through: linger round the place.
		if not chosen.is_empty() and place==slot_place and chosen.node==current.get("node",-1) and int(chosen.building)<0 and not STOP_POSE.has(place):
			var around := street_loop(CitizenRoutes.graph.get_point_position(chosen.node),6.0,30.0,3,cycle)
			if not around.is_empty(): chosen=around[cycle%around.size()]
	slot_place=place
	if chosen.is_empty(): return {}
	var out := chosen.duplicate()
	out["place"]=place
	return out

## Gait for the errand: jog the run, formal to the office, else a walk.
func gait(place: String) -> String:
	if place=="run": return "Run"
	if routine_name=="office" and place in ["work","lunch"]: return "WalkFormal"
	return "Walk"

## Walking pace relative to the person's own: jogging, brisk on delivery rounds.
func pace(place: String) -> float:
	return 2.35 if place=="run" else (1.15 if place=="rounds" else 1.0)
