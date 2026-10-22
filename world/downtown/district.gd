class_name DowntownDistrict
extends Node3D
## How far behind the facade plane the entrance lobby's floor, ceiling and side walls begin.
const LOBBY_INSET := 0.32
## Ground-floor blank walls are 4.18 m tall (scale of the 3.2 m module): 2 cm under the storefront
## cornice band's top (4.2), which they used to share.
const GROUND_WALL := 4.18 / 3.2
@export var block_count := 1
var batches := {}
var entries: Array[Dictionary]=[]
var buildings: Array[Dictionary]=[]
var static_body: StaticBody3D
var proxy_materials := {}
var lights: Array[OmniLight3D]=[]
var population: Node3D
var crossing_labels: Array[Label3D]=[]
## The city's prop placement (CedarNeighborhood.placer), or a private one when built standalone.
var placer: PropPlacer
func city_placer() -> PropPlacer:
	if placer==null:
		var hood := get_parent()
		placer=hood.get("placer") if hood!=null and hood.get("placer") is PropPlacer else PropPlacer.new()
	return placer
## Frontage prop at a building-local spot (x along the facade, z out towards the kerb): the
## PropPlacer pulls it back towards the facade until it clears the kerb - the sidewalks of the
## 18 m avenue are only 3 m deep, where lamps and trees used to stand on the kerb line.
func kerbside(base: Transform3D,local: Vector3,kind: String,radius: float,yaw: float=0,scale_factor: Vector3=Vector3.ONE) -> Transform3D:
	var wanted := base*Vector3(local.x,0,local.z)
	var spot := city_placer().kerb_clear(kind,wanted,(base.basis*Vector3.FORWARD).normalized(),radius,1.5)
	return base*pose(Vector3(local.x,local.y,local.z-wanted.distance_to(spot)),yaw,scale_factor)
func set_time(_hour: float,daylight: float) -> void:
	if UrbanKit.window_material!=null: UrbanKit.window_material.set_shader_parameter("night",1.0-daylight)
	if UrbanKit.materials.has("UrbanImpostor"): UrbanKit.materials.UrbanImpostor.set_shader_parameter("night",1.0-daylight)
	for light in lights: light.light_energy=(1.0-daylight)*2.2
	if population!=null: population.hour=_hour
func pose(at: Vector3, yaw: float=0, scale_factor: Vector3=Vector3.ONE) -> Transform3D:
	return Transform3D(Basis(Vector3.UP,yaw).scaled_local(scale_factor),at)
## Kit props replaced by the converted realistic props (PropKit) where one exists.
const PROP_SWAP := {"dumpster":"dumpster_large","bollard":"bollard_metal","barrier":"water_barrier_white","trash_bin":"litter_bin_green",
	"recycle_bin":"wheelie_bin_blue","hydrant":"fire_hydrant","cone":"traffic_cone"}
## Primitive colliders for the street props, café furniture and campus signs (PropColliders).
var _solids: PropColliders
func solids() -> PropColliders:
	if _solids==null: _solids=PropColliders.new(self,"DowntownProps")
	return _solids
func place(asset: String, transform: Transform3D, group: int, end: float=180, start: float=0) -> void:
	if start==0 and PropColliders.has(asset): solids().solid(asset,transform)
	var pieces := UrbanKit.get_parts(asset)
	if PROP_SWAP.has(asset) and PropKit.has(PROP_SWAP[asset]): pieces = PropKit.get_parts(PROP_SWAP[asset])
	var cell := Vector2i(floori(transform.origin.x/64),floori(transform.origin.z/64))
	for i in range(pieces.size()):
		var key := "%s_%d_%d_%d_%d_%d" % [asset,i,cell.x,cell.y,int(start),int(end)]
		if not batches.has(key): batches[key]={"piece":pieces[i],"transforms":[],"start":start,"end":end,"asset":asset,"group":group}
		batches[key].transforms.append(transform*pieces[i].transform)
func module(asset: String,transform: Transform3D,group: int) -> void:
	var architectural := asset.begins_with("bay_") or asset.begins_with("storefront_") or asset.begins_with("entrance_") or asset in ["balcony","canopy","awning","loading_door","garage_entry","parking_bay","fire_escape","bus_shelter","traffic_signal","crosswalk_signal"]
	if architectural:
		place(asset,transform,group,115)
		place(asset+"_far",transform,group,220,115)
	else: place(asset,transform,group,95)
	var proxies := {"dumpster":Vector3(2.1,1.35,1.2),"utility_cabinet":Vector3(.9,1.4,.45),"cafe_table":Vector3(.75,.8,.75),"barrier":Vector3(3,.8,.6),"bollard":Vector3(.15,.9,.15)}
	if proxies.has(asset):
		var size: Vector3=proxies[asset]
		collider(transform*Vector3(0,size.y*.5,0),size*transform.basis.get_scale(),transform.basis.get_euler().y)
func flush() -> void:
	for data: Dictionary in batches.values():
		var instances := MultiMesh.new()
		instances.transform_format=MultiMesh.TRANSFORM_3D
		instances.mesh=data.piece.mesh
		instances.instance_count=data.transforms.size()
		var origin: Vector3=data.transforms[0].origin
		for i in range(instances.instance_count):
			var transform: Transform3D=data.transforms[i]
			transform.origin-=origin
			instances.set_instance_transform(i,transform)
		var batch := MultiMeshInstance3D.new()
		batch.multimesh=instances
		batch.set_meta("prop",data.asset)   # asset id, for audits (tests/prop_placement_test.gd)
		batch.material_override=data.piece.material
		batch.position=origin
		batch.visibility_range_begin=data.start
		batch.visibility_range_end=data.end
		batch.visibility_range_begin_margin=6 if data.start>0 else 0
		batch.visibility_range_end_margin=6
		var structural: bool=data.asset in ["blank_wall","roof_slab","storefront_0","storefront_1","storefront_2","reuse_birch","living_hospital","living_fire_station","living_school"]
		if data.start>0 or not structural: batch.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(batch)
	batches.clear()
func collider(at: Vector3,size: Vector3,yaw: float=0,interaction: String="") -> void:
	var shape := CollisionShape3D.new()
	var bounds := BoxShape3D.new()
	bounds.size=size
	shape.shape=bounds
	shape.transform=pose(at,yaw)
	if interaction=="": static_body.add_child(shape)
	else:
		var body := StaticBody3D.new()
		body.set_meta("interaction",interaction)
		body.add_child(shape)
		add_child(body)
func flat(at: Vector3,size: Vector3,color: String,solid: bool=false,visual: bool=true) -> void:
	# Blender-authored pavement meshes use world-space materials at any parcel size.
	var asphalt := color=="3a4249"
	if visual: place("road_segment" if asphalt else "sidewalk",pose(at+Vector3(0,size.y*.5,0),0,Vector3(size.x/4,1,size.z/(12 if asphalt else 4))),900+int(at.x)+int(at.z),1200)
	if solid: collider(at,size)
func label(words: String,at: Vector3,yaw: float=0,font_size: int=32) -> void:
	var sign := Label3D.new()
	sign.text=words
	sign.position=at
	sign.rotation.y=yaw
	sign.font_size=font_size
	sign.pixel_size=.008
	sign.outline_size=3
	sign.visibility_range_end=90
	add_child(sign)
func occluder(at: Vector3,size: Vector3,yaw: float=0) -> void:
	var node := OccluderInstance3D.new()
	var box := BoxOccluder3D.new()
	box.size=size
	node.occluder=box
	node.transform=pose(at,yaw)
	add_child(node)
func _ready() -> void:
	static_body=StaticBody3D.new()
	static_body.name="UrbanStaticCollision"
	add_child(static_body)
	get_viewport().use_occlusion_culling=true
	build_roads()
	for block_id in range(block_count):
		for building in DowntownCatalog.buildings(block_id):
			buildings.append(building)
			if building.program=="mixed":
				build_building(building)
				street_details(building)
			else: special_parcel(building)
		courtyard(block_id)
	road_details()
	if block_count>1: CivicCampus.build(self)
	if block_count>1: delivery_locations()
	flush()
	if block_count>1:
		population=preload("res://world/downtown/population.gd").new()
		population.name="DowntownActivity"
		add_child(population)
func build_roads() -> void:
	var width := 132.0 if block_count==1 else 372.0
	var depth := 164.0 if block_count==1 else 444.0
	var center := Vector3(198 if block_count==1 else 306,-.15,-328 if block_count==1 else -468)
	flat(center,Vector3(width,.3,depth),"737773",true)
	var xs := [144,252] if block_count==1 else DowntownCatalog.STREET_X
	var zs := [-258,-398] if block_count==1 else DowntownCatalog.STREET_Z
	for x in xs:
		flat(Vector3(x,.025,center.z),Vector3(18 if x==252 else 14,.05,depth),"3a4249")
		for j in range(zs.size()-1):
			for side in [-1,1]: flat(Vector3(x+side*(11 if x==252 else 9),.07,(zs[j]+zs[j+1])*.5),Vector3(4,.14,absf(zs[j]-zs[j+1])-14),"bdc2b8")
	for z in zs:
		# Cross-street carriageway: one piece per block face between the avenues, at the avenues'
		# level (top 0.05). It used to be one slab the whole width with its top at 0.15 - a 10 cm
		# step round every junction square, 12 cm above the street kit it meets at x 120 and 10 cm
		# above the campus street it continues into at x 492 - with the paint 11 cm up in the air
		# over the avenues. The westmost piece is pitched 2 cm down over its 17 m to meet the
		# street kit's 0.03 flush; east of the last avenue CivicCampus lays the carriageway.
		var edges: Array[float] = [center.x-width*.5]
		for x in xs: edges.append_array([x-(9.0 if x==252 else 7.0),x+(9.0 if x==252 else 7.0)])
		edges.append(center.x+width*.5)
		for j in range(0,edges.size(),2):
			var x0: float=edges[j]
			var x1: float=edges[j+1]
			if block_count>1 and j==edges.size()-2: continue
			if block_count>1 and j==0:
				# 3 cm thick, so its underside leaves the base slab's top (y 0) at x 120 rather than
				# dipping into it (its end face lay in the base's end face there).
				var pitch := atan2(.02,x1-x0)
				place("road_segment",Transform3D(Basis(Vector3.BACK,pitch).scaled_local(Vector3((x1-x0)/4,.6,14.0/12)),Vector3((x0+x1)*.5,.04,z)),900+int(x0)+int(z),1200)
			else: flat(Vector3((x0+x1)*.5,.025,z),Vector3(x1-x0,.05,14),"3a4249")
		for j in range(xs.size()-1):
			var left: float=xs[j]+(9 if xs[j]==252 else 7)
			var right: float=xs[j+1]-(9 if xs[j+1]==252 else 7)
			for side in [-1,1]: flat(Vector3((left+right)*.5,.08,z+side*9),Vector3(right-left,.16,4),"bdc2b8")
	for i in range(block_count):
		var parcel := DowntownCatalog.blocks()[i]
		flat(Vector3(parcel.get_center().x,.045,parcel.get_center().y),Vector3(84,.09,8),"3a4249")
		# Courtyard paving 2 cm clear of the facades round it (its end faces lay in their planes).
		for side in [-1,1]: flat(Vector3(parcel.get_center().x,.035,parcel.get_center().y+side*18),Vector3(27.96,.07,27.96),"c1bbaa")
	if block_count>1:
		for z in DowntownCatalog.STREET_Z:
			# Connector carriageway and sidewalks come from StreetGrid (x 69-120); this slab is only
			# their collision now - its top (y 0) lay in the plane of the neighbourhood ground and of
			# the downtown base slab, under the street kit.
			flat(Vector3(106,-.15,z),Vector3(80,.3,22),"737773",true,false)
		collider(Vector3(630,2,-468),Vector3(2,4,444))
		for z in [-691,-245]: collider(Vector3(312,2,z),Vector3(360,4,2))
func build_building(b: Dictionary) -> void:
	var base := pose(b.root,b.yaw)
	var w: float=b.width
	var d: float=b.depth
	var h: float=b.height
	var style: int=b.style
	var id: int=b.id
	var bay_count := int(w/4)
	var entry_bay := bay_count/2
	var entry_x := -bay_count*2.0+2+entry_bay*4
	entries.append({"id":id,"number":b.number,"front":base*Vector3(entry_x,1,1),"inside":base*Vector3(entry_x,1,-2.6),"rear":base*Vector3(0,1,-d-1),"yaw":b.yaw,"closed":b.closed})
	# A shallow reachable lobby; opaque upper volume begins above the ground floor.
	collider(base*Vector3(0,2.1,-(d+5)*.5),Vector3(w,4.2,d-5),b.yaw)
	for side in [-1,1]:
		var extent: float = (w*.5-side*entry_x-2.7)
		var x: float = entry_x+side*(2.7+extent*.5)
		collider(base*Vector3(x,2.1,-2.5),Vector3(extent,4.2,5),b.yaw)
	for floor_id in range(int(b.floors)):
		var tower: bool=b.tower and floor_id>=4
		var floor_w := w*.64 if tower else w
		var floor_d := d*.64 if tower else d
		var setback := d*.18 if tower else 0.0
		var y := 0.0 if floor_id==0 else 4.2+(floor_id-1)*3.2
		var count := int(floor_w/4)
		for face in [0,1]:
			var face_transform := base*pose(Vector3(0,y,-setback if face==0 else -setback-floor_d),0 if face==0 else PI)
			var remainder := floor_w-count*4
			# Back-facade bays (and remainder walls) that abut the next building of the block are left
			# out: hidden inside the neighbour, their fins and sills poked through its walls.
			var abutted: bool = face==1 and setback==0.0
			if remainder>.01:
				for edge in [-1,1]:
					# 5 cm short of the corner, inside the corner post: the end face lay in the side
					# facade's plane (the side curtain walls' glass is exactly there).
					var rx: float = edge*(floor_w*.5-remainder*.25-.025)
					if abutted and not back_free(b,-rx,remainder*.25,.5): continue
					place("blank_wall",face_transform*pose(Vector3(rx,0,0),0,Vector3((remainder*.5-.05)/4,GROUND_WALL if floor_id==0 else 1,1)),id,750)
			for bay_index in range(count):
				var x := -count*2.0+2+bay_index*4
				if abutted and not back_free(b,-x,1.9,.5): continue
				var asset := "bay_apartment_%d" % style
				if id%4==3: asset="bay_office_%d" % style
				if floor_id==0: asset=("entrance_" if face==0 and bay_index==entry_bay else "storefront_")+str(style)
				module(asset,face_transform*pose(Vector3(x,0,0)),id)
				# (no balconies on office facades: the bay_office_1 stone fins stand where the slab goes)
				if floor_id>0 and not tower and id%3==2 and id%4!=3 and bay_index%2==0 and face==0:
					# Slab 10 cm up (KitBuilder.BALCONY_LIFT): at 0 it cut through the storefront cornice
					# band (top 4.2) on the first floor; at 9 cm its top lay in the plane of the apartment
					# bay's concrete floor band top (0.2).
					module("balcony",face_transform*pose(Vector3(x,KitBuilder.BALCONY_LIFT,0)),id)
				if floor_id==0 and face==0 and bay_index!=entry_bay and id%3==0: module("awning",face_transform*pose(Vector3(x,3.2,.04)),id)
		for side in [-1,1]:
			# A side that abuts the next building of the row is hidden inside it: no walls or bays.
			if setback==0.0 and not side_free(b,side): continue
			var side_pose := base*pose(Vector3(side*floor_w*.5,y,-setback-floor_d*.5),side*PI/2)
			var alley_face: bool = (id%10 in [6,9] and side==1) or (id%10 in [7,8] and side==-1)
			var active_corner: bool=(id%10 in [0,5] and side==-1) or (id%10 in [2,3] and side==1)
			var windows: bool=floor_id>0 and (tower or id%10 in [0,2,3,5] or alley_face)
			# Side walls stop 2 cm short of the front and back facade planes: their end faces used to lie
			# in those planes, across the corner bays (a 30 cm brick strip fighting the facade).
			if not windows and not (floor_id==0 and active_corner): place("blank_wall",side_pose*pose(Vector3(0,0,-.1),0,Vector3((floor_d-.04)/4,GROUND_WALL if floor_id==0 else 1,1)),id,750)
			if floor_id==0 and alley_face:
				module("loading_door",side_pose*pose(Vector3(0,0,.03)),id)
				module("dumpster",side_pose*pose(Vector3(-8,0,.7)),id)
				module("vent",side_pose*pose(Vector3(5,2,.03)),id)
				module("conduit",side_pose*pose(Vector3(6,0,.03)),id)
			if windows or (floor_id==0 and active_corner):
				var side_count := int(floor_d/4)
				var remainder := floor_d-side_count*4
				# The side run is squeezed 32 cm short of the front / back facade planes, clear of the
				# 0.3 m deep corner bays (fins, piers, fascia and soffit faces of the side modules used to
				# lie in theirs; the corner posts close the gap), and the remainder walls sit 2 cm inside
				# the side plane, clear of the corner bays' fin faces.
				var squeeze: float = (side_count*4.0-.64)/(side_count*4.0) if remainder<=.01 else 1.0
				for j in range(side_count): module(("storefront_%d" if floor_id==0 else "bay_office_%d")%style,side_pose*pose(Vector3((-side_count*2+2+j*4)*squeeze,0,.06),0,Vector3(squeeze,1,1)),id)
				if remainder>.01:
					for edge in [-1,1]: place("blank_wall",side_pose*pose(Vector3(edge*(floor_d*.5-remainder*.25-.01),0,-.02),0,Vector3((remainder*.5-.02)/4,1,1)),id,850)
		if floor_id==int(b.floors)-1 or (b.tower and floor_id==3):
			var roof_y := y+(4.2 if floor_id==0 else 3.2)
			# Roof deck inset 15 cm: its 0.2 m edge used to lie in the facade plane, across the top of the
			# last floor's walls and the parapets (and in the plane of the inset side blank walls).
			place("roof_slab",base*pose(Vector3(0,roof_y,-setback-.15),0,Vector3((floor_w-.3)/4,1,(floor_d-.3)/4)),id,850)
			for face in [0,1]: place("parapet",base*pose(Vector3(0,roof_y,-setback if face==0 else -setback-floor_d),0 if face==0 else PI,Vector3(floor_w/4,1,1)),id,850)
	# Corner posts (7.5 cm wide, 10 cm proud of the front / back facade), one per corner and tier,
	# the full tier height: the side runs and the remainder walls stop 2 cm short
	# of each corner and the posts close it. Not where the side abuts the next building.
	for tier in range(2 if b.tower else 1):
		var tw: float = w*.64 if tier==1 else w
		var td: float = d*.64 if tier==1 else d
		var tset: float = d*.18 if tier==1 else 0.0
		var podium := DowntownCatalog.height(4)
		var low: float = podium if tier==1 else 0.0
		var high: float = podium if (tier==0 and b.tower) else h
		for back in [false,true]:
			for sx in [-1.0,1.0]:
				if tier==0 and not side_free(b,sx): continue
				var corner := base*pose(Vector3(0,low,-tset-td if back else -tset),PI if back else 0.0)
				# x from 3.5 cm inside the corner to 4 cm out, front 10 cm proud: the kit modules' faces by
				# the corner lie at +0 / 2 / 4 / 6 cm (front frame rails, apartment sills: the post's front
				# face used to be at +4 cm) and the side modules' at +6 / 8 / 10 / 12 cm (its side face was
				# at +10 cm); the far side impostors sit at +2 cm. The top runs 2.5 cm past the roof line:
				# it lay in the plane of the side walls' and impostors' tops.
				var px: float = sx*(tw*.5+.0025)*(-1.0 if back else 1.0)
				place("plain_wall_%d" % style,corner*pose(Vector3(px,0,.10),0,Vector3(.075/4,(high-low+.025)/3.2,.44/.3)),id,750)
	# Interior finishes and entrance hierarchy.
	# Lobby floor and ceiling: paved interior slab, not the gravel roof deck.
	# Lobby shell (floor, ceiling, side and back walls) starts 0.32 m behind the facade plane, just
	# inside the storefront frames: their front edges used to lie in the facade plane, across the
	# piers' feet, the fascia band and the neighbouring shop windows.
	var lobby := LOBBY_INSET
	place("interior_slab",base*pose(Vector3(entry_x,.02,-lobby),0,Vector3(1.35,.3,(5.0-lobby)/4.0)),id,120)
	place("interior_slab",base*pose(Vector3(entry_x,4.16,-lobby),0,Vector3(1.35,.3,(5.0-lobby)/4.0)),id,180)
	place("blank_wall",base*pose(Vector3(entry_x,0,-5),0,Vector3(1.35,1.3,1)),id,180)
	for side in [-1,1]: place("blank_wall",base*pose(Vector3(entry_x+side*2.7,0,-2.5-lobby*.5),-side*PI/2,Vector3((5.0-lobby)/4.0,1.3125,1)),id,180)
	# Canopy 3 cm up: its underside lay in the plane of the entrance head soffit (y 3.09). None over
	# a boarded-up entrance (renovation: the loading door and scaffolds stand there).
	if id%11!=7: module("canopy",base*pose(Vector3(entry_x,3.18,.06)),id)
	# Shop sign on the fascia above the entrance canopy's tie rods (y 3.60): it hung across the canopy
	# and the rods ran through it. 4.4 x 0.4 m, between the rods and the cornice band (4.06).
	place("sign_%d" % (7 if id==10 else (id%10+b.block*3)%10),base*pose(Vector3(0,3.70,.06),0,Vector3(1.1,.5,1)),id,160)
	label(str(b.number),base*Vector3(entry_x+1.3,2.6,.18),b.yaw)
	label("CLOSED · RENOVATION" if b.closed else "WELCOME",base*Vector3(entry_x,2.92,-.1),b.yaw,18)
	if not b.closed:
		var room := base*pose(Vector3(entry_x,0,0))
		if id%10 in [2,5,7]:
			module("mailboxes",room*pose(Vector3(-2.15,.6,-2.4),PI/2),id)
			module("unit_door",room*pose(Vector3(0,0,-4.81)),id)
			place("reuse_park_bench",room*pose(Vector3(1.9,0,-2.5),-PI/2),id,65)
			if id not in [2,5]: label("LOBBY  /  UNIT 102",room*Vector3(0,2.65,-4.75),b.yaw,22)
		else:
			module("service_counter",room*pose(Vector3(0,0,-3.55)),id)
			collider(room*Vector3(0,.55,-3.55),Vector3(2.62,1.1,.78),b.yaw)
			module("grocery_shelf",room*pose(Vector3(-2.38,0,-2.5),PI/2),id)
			module("cafe_table",room*pose(Vector3(1.75,0,-1.8)),id)
			module("cafe_chair",room*pose(Vector3(1.75,0,-2.55),PI),id)
			if id not in [0,1,8,10]: label("ORDER COLLECTION",room*Vector3(0,2.5,-4.75),b.yaw,22)
		var light := OmniLight3D.new()
		light.position=room*Vector3(0,3.1,-2.6)
		light.omni_range=5.5
		light.light_color=Color("ffe0b5")
		light.light_energy=.65
		light.distance_fade_enabled=true
		light.distance_fade_begin=45
		light.distance_fade_length=15
		add_child(light)
	# Service fittings on the back facade only where it faces open ground: many back faces abut the
	# next building of the block, and the doors, pipes and fire escapes used to stand inside it.
	if back_free(b,0,1.7,.5): module("loading_door",base*pose(Vector3(0,0,-d-.04),PI),id)
	if back_free(b,-w*.5+1,.2,.3): module("pipe",base*pose(Vector3(-w*.5+1,0,-d-.05),PI),id)
	if back_free(b,w*.5-2,.6,.4): module("vent",base*pose(Vector3(w*.5-2,1.8,-d-.08),PI),id)
	module("hvac",base*pose(Vector3(-3,h+.15,-d*.5)),id)
	module("antenna",base*pose(Vector3(4,h+.1,-d*.6)),id)
	if not b.tower and id%3==0:
		# Landing clear above the back storefronts' cornice band (4.06-4.2 m), its brackets against
		# the wall; at the first spot along the facade with open ground behind it (the stair climbs
		# along the facade - tools/rebuild_fire_escape.py; it used to run 2.5 m into the building).
		for x in [w*.5-3,0.0,-w*.5+3]:
			if back_free(b,x,1.2,1.6):
				module("fire_escape",base*pose(Vector3(x,4.3,-d-.005),PI),id)
				break
	var podium_h := DowntownCatalog.height(4) if b.tower else h
	for tier in range(2 if b.tower else 1):
		var low := podium_h if tier==1 else 0.0
		var high := h if tier==1 else podium_h
		var proxy_w := w*.64 if tier==1 else w
		var proxy_d := d*.64 if tier==1 else d
		var inset := d*.18 if tier==1 else 0.0
		# Distant massing 2.5 cm proud of the facades and 6.5 cm short of every corner (clear of the
		# corner posts and of the front remainder walls, which end 5 cm short): the end faces of the
		# 0.3 m proxy boxes used to lie in the side walls' and remainder walls' planes, and a front
		# proxy 3 cm proud sat 1 cm off the corner post of a building whose side runs on in that
		# plane. Bottom 7 mm up and top 1.6-2.6 cm down (by building): the tops lay in the plane of
		# the roof-line walls and of the neighbouring building's proxies.
		var p_low: float = low+.007
		var p_h: float = high-p_low-(.016+.005*(id%3))
		for face in [0,1]: place("impostor_wall",base*pose(Vector3(0,p_low,-inset+.025 if face==0 else -inset-proxy_d-.025),PI*face,Vector3((proxy_w-.13)/4,p_h/3.2,1)),id,850,220)
		for side in [-1,1]:
			if tier==0 and not side_free(b,side): continue   # inside the neighbour it abuts
			# Sides 2 cm proud (not 3): clear of the corner posts' side faces at +4 cm.
			place("impostor_wall",base*pose(Vector3(side*(proxy_w*.5+.02),p_low,-inset-proxy_d*.5),side*PI/2,Vector3((proxy_d-.13)/4,p_h/3.2,1)),id,850,220)
	occluder(base*Vector3(0,(podium_h+4.3)*.5,-d*.5),Vector3(w-.5,podium_h-4.3,d-.5),b.yaw)
	if b.tower: occluder(base*Vector3(0,(h+podium_h)*.5,-d*.5),Vector3(w*.64-.4,h-podium_h,d*.64-.4),b.yaw)

func street_details(b: Dictionary) -> void:
	var base := pose(b.root,b.yaw)
	var id: int=b.id
	var half: float=b.width*.5
	var lamp := kerbside(base,Vector3(-half+3,0,2.6),"street_lamp",0.2)
	place("reuse_street_lamp",lamp,id,150)
	var street_light := OmniLight3D.new()
	street_light.position=lamp*Vector3(0,4.3,0)
	street_light.light_color=Color("ffdcac")
	street_light.omni_range=12
	street_light.distance_fade_enabled=true
	street_light.distance_fade_begin=60
	street_light.distance_fade_length=20
	add_child(street_light)
	lights.append(street_light)
	module("storm_drain",base*pose(Vector3(-half+4,.05,3.8)),id)
	module("parking_sign",kerbside(base,Vector3(half-3,0,2.6),"parking_sign",0.1),id)
	if id%2==0: module("parking_meter",kerbside(base,Vector3(half-4,0,2.6),"parking_meter",0.1),id)
	if id%3==0:
		var tree := kerbside(base,Vector3(-half+7,0,2.8),"tree",0.35)
		module("tree_pit",tree*pose(Vector3(0,.09,0),0,Vector3(.67,1,.67)),id)
		place("reuse_birch",tree*pose(Vector3.ZERO,0,Vector3.ONE*.63),id,130)
		module("hydrant",kerbside(base,Vector3(half-2,0,2.4),"hydrant",0.25),id)
	if id%3==1:
		# Bins either side of the street lamp at -half + 3 (the recycle bin stood round its pole).
		place("reuse_park_bench",kerbside(base,Vector3(-half+5.6,0,2.5),"bench",0.35),id,95)
		module("trash_bin",kerbside(base,Vector3(-half+3.9,0,2.5),"trash_bin",0.3),id)
		module("recycle_bin",kerbside(base,Vector3(-half+2.1,0,2.5),"recycle_bin",0.3),id)
	if id%5==0: module("newspaper_box",kerbside(base,Vector3(half-6,0,2.5),"newspaper_box",0.25),id)
	# Camera on the fascia above the awnings (it hung inside the corner bay's awning), poster on the
	# corner pier, 1.4 cm off its face (it floated 0.46 m in front of the shop window).
	var pier_x: float = int(b.width/4)*2.0-.25
	for side in [-1,1]:
		module("security_camera",base*pose(Vector3(side*(half-.45),3.85,.05)),id)
		module("poster",base*pose(Vector3(side*pier_x,1.1,.02),0,Vector3(.55,1,1)),id)
	var rear := base*pose(Vector3(0,0,-b.depth),PI)
	# (rear frame x = -base x; the conduit stands clear of the cabinet it used to run through)
	if back_free(b,half-4,1.1,1.8): module("dumpster",rear*pose(Vector3(-half+4,0,1)),id)
	if back_free(b,-4,.6,1.4): module("delivery_cart",rear*pose(Vector3(4,0,.8)),id)
	if back_free(b,-2,.4,1.0): module("loading_sign",rear*pose(Vector3(2,0,.7)),id)
	if back_free(b,-(half-3),.5,.7): module("utility_cabinet",rear*pose(Vector3(half-3,0,.3)),id)
	if back_free(b,-(half-1.9),.3,.3): module("conduit",rear*pose(Vector3(half-1.9,0,.04)),id)
	if back_free(b,0,.5,3.0): module("manhole",rear*pose(Vector3(0,.055,2.5)),id)
	if id%11==7:
		for x in [-6,-2,2,6]:
			module("scaffold",base*pose(Vector3(x,0,.6)),id)
			module("cone",base*pose(Vector3(x,0,1.5)),id)
		var count := int(b.width/4)
		var entry_x := -count*2.0+2+int(count/2)*4
		place("loading_door",base*pose(Vector3(entry_x,0,.1),0,Vector3(.65,1,1)),id,130)
		collider(base*Vector3(entry_x,1.45,0),Vector3(1.9,2.9,.16),b.yaw)
	# No prop may occupy the central entrance approach.
## True when the strip beside building b's side facade (`side` -1 / +1, 0.5 m out, full depth)
## is clear of every other building of its block.
func side_free(b: Dictionary,side: float) -> bool:
	var base := pose(b.root,b.yaw)
	var half: float = float(b.width)*.5
	var rect := Rect2()
	for k in range(4):
		var p: Vector3 = base*Vector3(side*(half+(.05 if k%2==0 else .5)),0,-.3 if k<2 else -float(b.depth)+.3)
		rect = Rect2(Vector2(p.x,p.z),Vector2.ZERO) if k==0 else rect.expand(Vector2(p.x,p.z))
	for other in DowntownCatalog.buildings(int(b.block)):
		if int(other.id)==int(b.id) or other.program=="plaza": continue
		if (other.footprint as Rect2).grow(-.05).intersects(rect): return false
	return true

## True when a strip behind building b's back facade - centred at base-frame x, `half_w` either
## side, from the wall out to `out` metres - is clear of every other building of its block.
func back_free(b: Dictionary,x: float,half_w: float,out: float) -> bool:
	var base := pose(b.root,b.yaw)
	var rect := Rect2()
	for k in range(4):
		var p: Vector3 = base*Vector3(x+(half_w if k%2==0 else -half_w),0,-float(b.depth)-(.05 if k<2 else out))
		rect = Rect2(Vector2(p.x,p.z),Vector2.ZERO) if k==0 else rect.expand(Vector2(p.x,p.z))
	for other in DowntownCatalog.buildings(int(b.block)):
		if int(other.id)==int(b.id) or other.program=="plaza": continue
		if (other.footprint as Rect2).grow(-.05).intersects(rect): return false
	return true

func courtyard(block_id: int) -> void:
	var parcel := DowntownCatalog.blocks()[block_id]
	var center := parcel.get_center()
	for side in [-1,1]:
		var at := Vector3(center.x,0,center.y+side*18)
		place("reuse_garden_planter",pose(at+Vector3(-9,0,0)),100+block_id,95)
		place("reuse_park_bench",pose(at+Vector3(0,0,9),PI),100+block_id,95)
		for dx in [-5,4]:
			module("cafe_table",pose(at+Vector3(dx,0,0)),100+block_id)
			for dz in [-.75,.75]: module("cafe_chair",pose(at+Vector3(dx,0,dz),0 if dz>0 else PI),100+block_id)
		for dx in [-9,-7,-5]: module("bike_rack",pose(at+Vector3(dx,0,-8),PI/2),100+block_id)
		place("reuse_bicycle",pose(at+Vector3(-7,.05,-8)),100+block_id,90)
		label("COURTYARD · PEDESTRIAN ACCESS",at+Vector3(0,2,-10),0,23)
	for x in [parcel.position.x+2,parcel.end.x-2]:
		module("loading_sign",pose(Vector3(x,0,center.y+3.5),PI/2),100+block_id)
func road_details() -> void:
	var xs := [144,252] if block_count==1 else DowntownCatalog.STREET_X
	var zs := [-258,-398] if block_count==1 else DowntownCatalog.STREET_Z
	var lower := -398 if block_count==1 else -678
	for x in xs:
		for z in range(lower+18,-270,8):
			var junction := false
			for crossing in zs:
				if absf(z-crossing)<16: junction=true
			if junction: continue
			# Paint 5 mm over the carriageway top (0.05); dashes and arrows used to float 3.5-4 cm.
			place("lane_dash",pose(Vector3(x,.055,z)),200+int(x),400)
			if x==252:
				for offset in [-3,3]: place("lane_dash",pose(Vector3(x+offset,.055,z)),200+int(x),250)
	for x in xs:
		for z in zs:
			for side in [-1,1]:
				crossing(pose(Vector3(x,.055,z+side*9)),18 if x==252 else 14,300+int(x+z))
				crossing(pose(Vector3(x+side*11,.055,z),PI/2),14,300+int(x+z))
				place("stop_line",pose(Vector3(x+side*1.5,.055,z+side*12)),300+int(x+z),180)
				place("turn_arrow",pose(Vector3(x+side*1.5,.055,z+side*20),0 if side>0 else PI),300+int(x+z),130)
				# Traffic and pedestrian signals: TrafficSignals (world/streets), on the
				# population's signal phase (SignalPlan "downtown").
				module("curb_ramp",pose(Vector3(x+side*9,.01,z-side*9),side*PI/2),300+int(x+z))
	module("bus_shelter",pose(Vector3(241.5,0,-353),PI/2),400)
	module("bus_sign",pose(Vector3(242.3,0,-348),PI/2),400)
	for block_id in range(block_count):
		var parcel := DowntownCatalog.blocks()[block_id]
		var x: float=parcel.end.x+6.7
		# Six-metre curb bays leave hydrants, junctions and alley mouths clear.
		for offset in [22,46,82]:
			var z: float=parcel.position.y+offset
			for end in [-3,3]: place("stop_line",pose(Vector3(x,.055,z+end),0,Vector3(.6,1,.5)),500+block_id,140)
			if offset!=46:
				var kind: String=CityAssets.CAR_TYPES[(block_id+offset)%5]
				place("reuse_"+kind,pose(Vector3(x,.055,z),PI),500+block_id,140)
				collider(Vector3(x,1,z),Vector3(1.9,2,5.2))
			else:
				# The loading-bay sign stands on the sidewalk, not in the kerb lane (x - 3 was 0.7 m
				# out on the carriageway).
				var sign_at := city_placer().kerb_clear("loading_sign",Vector3(x-3,0,z),Vector3.LEFT,0.1,2.0)
				label("LOADING  15 MIN",Vector3(sign_at.x+1,2,z),PI/2,21)
				module("loading_sign",pose(sign_at),500+block_id)
	# A quiet edge street reserves its curb lane for bicycles.
	for z in range(-658,-274,12):
		place("lane_dash",pose(Vector3(472.7,.055,z)),700,250)
		if z%3==0: place("turn_arrow",pose(Vector3(474,.055,z)),700,120)

func crossing(transform: Transform3D,width: float,group: int) -> void:
	var full := int(width/4)
	for i in range(full): place("crosswalk",transform*pose(Vector3(-width*.5+2+i*4,0,0)),group,250)
	var remaining := width-full*4
	if remaining>0: place("crosswalk",transform*pose(Vector3(width*.5-remaining*.5,0,0),0,Vector3(remaining/4,1,1)),group,250)

func delivery_locations() -> void:
	for i in range(DowntownCatalog.PICKUPS.size()):
		var p: Vector3=DowntownCatalog.PICKUPS[i]
		collider(p,Vector3(.8,.9,.20) if i!=3 else Vector3(.20,.9,.8),0,"pickup_"+CityCatalog.RESTAURANTS[i+3])
		# 10 cm out in front of the pickup along its facing (a fixed +z put the yaw-PI one inside the
		# back facade).
		var pickup_yaw: float = PI/2 if i==3 else (PI if i==1 else 0.0)
		label("COLLECT  /  "+CityCatalog.NAMES[i+3],p+Basis(Vector3.UP,pickup_yaw)*Vector3(0,1.1,.1),pickup_yaw,20)
	for i in range(DowntownCatalog.DESTINATIONS.size()):
		var p: Vector3=DowntownCatalog.DESTINATIONS[i]
		collider(p,Vector3(.8,.9,.16) if i!=4 else Vector3(.16,.9,.8),0,"door_%d"%(36+i))
		label(["LOBBY","UNIT 102 DELIVERY","OFFICE RECEPTION","HOTEL RECEPTION","SITE DELIVERIES"][i],p+Vector3(0,1.25,.12),PI if i==3 else (PI/2 if i==4 else 0),18)
		# Building/unit number in large 3D glyphs above the delivery point.
		var yaw: float=PI if i==3 else (PI/2 if i==4 else 0.0)
		var number: String=DeliverySession.ADDRESSES[36+i].get_slice(" ",0)
		if i==1: number="604-102"
		var plate := GlyphText.build(number,0.32,true,0.017)   # digits 1.7 cm proud of the plate
		plate.transform=Transform3D(Basis(Vector3.UP,yaw),p+Vector3(0,1.75,0)+Basis(Vector3.UP,yaw)*Vector3(0,0,0.14))
		add_child(plate)

func special_parcel(b: Dictionary) -> void:
	var base := pose(b.root,b.yaw)
	var id: int=b.id
	var w: float=b.width
	var d: float=b.depth
	if b.program=="parking":
		for floor_id in range(4):
			for face in [0,1]:
				for j in range(int(w/8)):
					if floor_id==0 and face==0 and j==1: continue
					module("parking_bay",base*pose(Vector3(-w*.5+4+j*8,floor_id*3.2,-d*face),PI*face),id)
			# 5 cm inside the bays' column ends (its edges lay in their end faces' planes).
			place("roof_slab",base*pose(Vector3(0,floor_id*3.2,-.15),0,Vector3((w-.1)/4,1,(d-.1)/4)),id,600)
		module("garage_entry",base*pose(Vector3(0,0,.05)),id)
		label("PUBLIC PARKING  /  2 HOUR",base*Vector3(0,3.7,.35),b.yaw,36)
		# Vehicle entrance has a clear 5 m throat and a shallow playable ground level.
		collider(base*Vector3(0,1.5,-d+1),Vector3(w,3,2),b.yaw)
		for side in [-1,1]: collider(base*Vector3(side*(w*.5-.3),1.5,-d*.5),Vector3(.6,3,d),b.yaw)
		for x in [-7,7]: place("reuse_sedan",base*pose(Vector3(x,.04,-8)),id,130)
		occluder(base*Vector3(0,7.9,-d*.5),Vector3(w-.5,9,d-.5),b.yaw)
	elif b.program=="construction":
		for y in [0,3.2,6.4]:
			place("roof_slab",base*pose(Vector3(0,y,-1),0,Vector3((w-2)/4,1,(d-2)/4)),id,400)
			for x in [-w*.5+2,0,w*.5-2]:
				for z in [-2,-d+2]: place("blank_wall",base*pose(Vector3(x,y,z),0,Vector3(.15,1,2)),id,400)
		for x in range(-int(w*.5)+2,int(w*.5),4):
			module("barrier",base*pose(Vector3(x,0,.6)),id)
			module("scaffold",base*pose(Vector3(x,0,-.3)),id)
		for x in [-7,6]: module("pallet_supplies",base*pose(Vector3(x,0,-4)),id)
		module("delivery_cart",base*pose(Vector3(0,0,1.2)),id)
		label("CIVIC WORKS  /  SITE DELIVERIES →",base*Vector3(0,2,.9),b.yaw,30)
		collider(base*Vector3(0,1.5,-d*.5-1),Vector3(w,3,d-2),b.yaw)
	else:
		for x in [-8,8]:
			place("reuse_garden_planter",base*pose(Vector3(x,0,-6)),id,120)
			place("reuse_birch",base*pose(Vector3(x,0,-10)),id,200)
			place("reuse_park_bench",base*pose(Vector3(x,0,-15),PI),id,120)
		# Atatürk Square: the monument and the putti fountain behind it come from
		# StreetSignage.monument() / CityMonuments.square().
		for x in [-8,-4,4,8]: module("bollard",base*pose(Vector3(x,0,.8)),id)



