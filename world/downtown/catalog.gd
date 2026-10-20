class_name DowntownCatalog
extends RefCounted
const STREET_X = [144.0,252.0,360.0,468.0]
const STREET_Z = [-258.0,-398.0,-538.0,-678.0]
const FIRST_BLOCK = Rect2(156,-386,84,116)
const GROUND_HEIGHT = 4.2
const FLOOR_HEIGHT = 3.2
const PICKUPS = [Vector3(170,1.25,-273.1),Vector3(200,1.25,-298.1),Vector3(202,1.25,-273.1),Vector3(237,1.25,-347),Vector3(226,1.25,-331.8)]
const DESTINATIONS = [Vector3(228.2,1.3,-272.4),Vector3(230,1.3,-274.75),Vector3(278,1.3,-273.1),Vector3(226,1.3,-381.2),Vector3(241,1.3,-485)]
const DESTINATION_NAMES = ["604 Meridian — lobby","604 Meridian — unit 102","620 Harbor — reception","610 Union Hotel — lobby","676 Civic Works — site gate"]
const PICKUP_APPROACHES = [[Vector3(170,0,-268),Vector3(170,0,-273.1)],[Vector3(198,0,-328),Vector3(198,0,-303),Vector3(200,0,-303),Vector3(200,0,-298.1)],[Vector3(202,0,-268),Vector3(202,0,-273.1)],[Vector3(242,0,-347),Vector3(237,0,-347)],[Vector3(226,0,-328),Vector3(226,0,-331.8)]]
const DESTINATION_APPROACHES = [[Vector3(230,0,-268),Vector3(230,0,-272.4),Vector3(228.2,0,-272.4)],[Vector3(230,0,-268),Vector3(230,0,-274.75)],[Vector3(278,0,-268),Vector3(278,0,-273.1)],[Vector3(226,0,-388),Vector3(226,0,-381.2)],[Vector3(243,0,-485),Vector3(241,0,-485)]]
static func blocks() -> Array[Rect2]:
	var result: Array[Rect2]=[]
	for row in range(3):
		for col in range(3): result.append(Rect2(156+108*col,-386-140*row,84,116))
	return result
static func height(floors: int) -> float: return GROUND_HEIGHT+(floors-1)*FLOOR_HEIGHT
static func buildings(block_id: int=0) -> Array[Dictionary]:
	var parcel := blocks()[block_id]
	var records: Array[Dictionary]=[]
	var widths := [28,32,24] if block_id%2==0 else [24,28,32]
	for side in [0,1]:
		var cursor := parcel.position.x
		for w in widths:
			var root := Vector3(cursor+w*.5,0,parcel.end.y if side==0 else parcel.position.y)
			records.append({"root":root,"width":float(w),"depth":28.0,"yaw":0.0 if side==0 else PI,"footprint":Rect2(cursor,parcel.end.y-28 if side==0 else parcel.position.y,w,28)})
			cursor+=w
	for side in [0,1]:
		for segment in [0,1]:
			var z: float = parcel.position.y+28+segment*34
			var root := Vector3(parcel.position.x if side==0 else parcel.end.x,0,z+13)
			records.append({"root":root,"width":26.0,"depth":28.0,"yaw":-PI/2 if side==0 else PI/2,"footprint":Rect2(parcel.position.x if side==0 else parcel.end.x-28,z,28,26)})
	var names := ["Rainline Café","Juniper Market","Meridian Apartments","Pacific Pharmacy","Seawall Noodles","Union Hotel","Moss & Paper","Harbor Offices","Corner Pantry","Civic Works"]
	for i in range(records.size()):
		var serial := block_id*10+i
		var profile := serial%20
		var floors: int = [2,3][serial%2] if profile<4 else (4+serial%5 if profile<16 else 10+serial%5)
		if serial in [12,24,42,65]: floors=20+serial%4
		records[i].merge({"id":serial,"block":block_id,"floors":floors,"height":height(floors),"style":(serial*7+block_id)%3,"name":names[(i+block_id*3)%names.size()],"number":600+serial*2,"tower":floors>15,"closed":serial%11==7})
		records[i].program="parking" if serial==17 else ("construction" if serial==38 else ("plaza" if serial==57 else "mixed"))
		if serial==17:
			records[i].floors=4
			records[i].height=12.8
		if serial==38:
			records[i].floors=3
			records[i].height=9.6
		if serial==57:
			records[i].floors=0
			records[i].height=0
		if serial==10: records[i].name="Harbor Offices"
	return records
static func metrics(block_count: int=9) -> Dictionary:
	var parcels := 0.0
	var roofs := 0.0
	var low := 0
	var mid := 0
	var high := 0
	var towers := 0
	for i in range(block_count):
		parcels+=blocks()[i].get_area()
		for b in buildings(i):
			if b.program!="plaza": roofs+=b.footprint.get_area()
			else: continue
			if b.floors<=3: low+=1
			elif b.floors<=8: mid+=1
			elif b.floors<=15: high+=1
			else: towers+=1
	return {"parcel_m2":parcels,"building_footprint_m2":roofs,"building_coverage":roofs/parcels,"low_rise":low,"mid_rise":mid,"upper_mid_rise":high,"towers":towers,"alley_width":8,"setback_range_m":[0,2]}


