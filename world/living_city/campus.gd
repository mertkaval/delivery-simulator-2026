class_name CivicCampus
extends RefCounted
const SITES = [
	{"asset":"hospital","at":Vector3(563,0,-328),"width":42.0,"depth":24.0,"height":14.4,"name":"Meridian General Hospital"},
	{"asset":"fire_station","at":Vector3(563,0,-468),"width":30.0,"depth":23.0,"height":8.8,"name":"Fire & Rescue Station 04"},
	{"asset":"school","at":Vector3(563,0,-608),"width":48.0,"depth":22.0,"height":7.2,"name":"Meridian Community School"}]
static func model(d: DowntownDistrict,asset: String,at: Vector3,yaw: float=0,large: bool=false) -> void:
	var transform := d.pose(at,yaw)
	d.place("living_"+asset,transform,1000,95)
	d.place("living_"+asset+"_lod1",transform,1000,220,95)
	if large: d.place("living_"+asset+"_lod2",transform,1000,620,220)
static func build(d: DowntownDistrict) -> void:
	d.flat(Vector3(560,-.15,-468),Vector3(140,.30,444),"737773",true)
	d.flat(Vector3(520,.025,-468),Vector3(14,.05,434),"3a4249")
	for side in [-1,1]: d.flat(Vector3(520+side*9,.07,-468),Vector3(4,.14,420),"bdc2b8")
	for z in DowntownCatalog.STREET_Z:
		d.flat(Vector3(552,.025,z),Vector3(160,.05,14),"3a4249")
		for side in [-1,1]: d.flat(Vector3(574,.07,z+side*9),Vector3(112,.14,4),"bdc2b8")
		for x in [511,529]:
			model(d,"stop",Vector3(x,0,z+9),0 if x==511 else PI)
		for x in range(514,528,2): d.place("crosswalk",d.pose(Vector3(x,.10,z+8),0),1000,150)
	# Linear rain-garden park between the cycleway and civic road, with clear cross paths.
	var planting := RandomNumberGenerator.new()
	planting.seed=8192
	for row in range(3):
		var middle: float=-328-row*140
		for j in range(-4,5):
			var z: float=middle+j*10
			d.place("living_garden_lawn",d.pose(Vector3(497,.08,z),0,Vector3(2,1,1)),1000,650)
		for z in [middle-34,middle-10,middle+18,middle+36]:
			d.place("reuse_maple",d.pose(Vector3(498,.08,z)),1000,260)
			model(d,"rain_garden",Vector3(486,0,z))
			d.place("reuse_park_bench",d.pose(Vector3(483,0,z),PI/2),1000,100)
		for z in [middle-32,middle+32]:
			d.place("living_garden_lawn",d.pose(Vector3(614,.08,z),0,Vector3(2,1,2.5)),1000,650)
			d.place("reuse_maple",d.pose(Vector3(615,.08,z)),1000,260)
		for i in range(600):
			var grass_at := Vector3(planting.randf_range(487.5,506.5),.095,middle+planting.randf_range(-44,44))
			d.place("reuse_grass_clump",d.pose(grass_at,planting.randf_range(0,TAU),Vector3.ONE*planting.randf_range(.7,1.3)),1000,50)
	for z in range(-648,-288,40):
		var at := Vector3(530,0,z)
		d.place("reuse_street_lamp",d.pose(at,PI/2),1000,180)
		var light := OmniLight3D.new()
		light.position=at+Vector3(-1.2,4.5,0)
		light.light_color=Color("ffd29b")
		light.omni_range=13
		light.light_energy=0
		light.distance_fade_enabled=true
		light.distance_fade_begin=55
		light.distance_fade_length=20
		d.add_child(light)
		d.lights.append(light)
	for site in SITES:
		model(d,site.asset,site.at,-PI/2,true)
		var w: float=site.width
		var depth: float=site.depth
		var h: float=site.height
		var base := d.pose(site.at,-PI/2)
		# Accessible forecourt, driveway and shallow vestibule; apparatus bays stay clear.
		d.flat(Vector3(548,.04,site.at.z),Vector3(30,.08,w+16),"bdc2b8")
		var driveway_z: float=site.at.z+(13 if site.asset=="hospital" else 0)
		d.flat(Vector3(542,.075,driveway_z),Vector3(42,.15,10 if site.asset!="fire_station" else 28),"3a4249")
		if site.asset=="fire_station":
			d.collider(base*Vector3(0,2.5,-21.5),Vector3(w,5,3),-PI/2)
			for x in [-14,-4.7,4.7,14]: d.collider(base*Vector3(x,2.7,0),Vector3(.85,5.4,.6),-PI/2)
		else:
			d.collider(base*Vector3(0,2,-(depth+5)*.5),Vector3(w,4,depth-5),-PI/2)
			for side in [-1,1]: d.collider(base*Vector3(side*(w/4+1.5),1.8,-2.5),Vector3(w/2-3,3.6,5),-PI/2)
		d.collider(base*Vector3(0,(h+4)*.5,-depth*.5),Vector3(w,h-4,depth),-PI/2)
		d.occluder(base*Vector3(0,h*.5,-depth*.6),Vector3(w-.8,h-.6,depth*.7),-PI/2)
		for side in [-1,1]:
			for j in range(3):
				var p := Vector3(541+j*7,0,site.at.z+side*(w*.5+7))
				model(d,"rain_garden",p,PI/2)
				d.place("reuse_birch",d.pose(p+Vector3(0,0,side*3)),1000,230)
				# One bollard per driveway side, 1.5 m inside the civic fleet's turning arcs (it stood
				# in the school bus's swept path at x 532).
				if j==0: d.module("bollard",d.pose(Vector3(530.5,0,site.at.z+side*(w*.5+2))),1000)
		if site.asset=="hospital": model(d,"hospital_sign",Vector3(530,0,-301),-PI/2)
		if site.asset=="school":
			d.collider(base*Vector3(17,4.4,-32),Vector3(14,8.8,18),-PI/2)
			model(d,"school_zone",Vector3(511,0,-565))
			d.flat(Vector3(606,.025,-601),Vector3(33,.05,60),"3a4249")
			for z in [-579,-623]:
				d.module("barrier",d.pose(Vector3(611,0,z)),1000)
				d.place("reuse_birch",d.pose(Vector3(613,0,z+7)),1000,230)
	# Two separated cycle tracks with marked crossings and flexible posts.
	for x in [473.0,475.1]:
		for z in range(-666,-268,6):
			var junction := false
			for cross_z in DowntownCatalog.STREET_Z:
				if absf(float(z)-cross_z)<11: junction=true
			if not junction: model(d,"cycle_lane",Vector3(x,.075,z))
		for z in [-298,-354,-438,-494,-578,-634]: model(d,"cycle_stencil",Vector3(x,.105,z),0 if x<474 else PI)
	for z in range(-664,-275,12):
		var clear := true
		for cross_z in DowntownCatalog.STREET_Z:
			if absf(float(z)-cross_z)<14: clear=false
		if clear: model(d,"cycle_separator",Vector3(471.7,.06,z))
	for z in [-286,-426,-566]:
		model(d,"cycle_sign",Vector3(477,0,z))
		model(d,"speed",Vector3(459,0,z),PI)
		model(d,"taxi_sign",Vector3(242,0,z))
	for block in DowntownCatalog.blocks():
		for side in [-1,1]:
			var p := Vector3(block.get_center().x+side*17,0,block.get_center().y+side*17)
			model(d,"rain_garden",p)
	# Service parking is separate from through lanes and pedestrian entrances.
	model(d,"ambulance",Vector3(555,.08,-315),-PI/2)
	model(d,"fire_engine",Vector3(570,.08,-477),-PI/2)
	model(d,"school_bus",Vector3(543,.08,-639),0)
	d.collider(Vector3(555,1.5,-315),Vector3(6.38,2.84,2.28))
	d.collider(Vector3(570,1.6,-477),Vector3(7.8,3.04,2.44))
	d.collider(Vector3(543,1.6,-639),Vector3(2.43,3.10,9.2))
