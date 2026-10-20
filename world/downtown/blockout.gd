extends Node3D
var benchmark_only := true
func surface(at: Vector3,size: Vector3,color: Color,solid: bool=false) -> void:
	var node := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size=size
	node.mesh=mesh
	var material := StandardMaterial3D.new()
	material.albedo_color=color
	node.material_override=material
	node.position=at
	add_child(node)
	if solid:
		var body := StaticBody3D.new()
		var collider := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size=size
		collider.shape=shape
		body.add_child(collider)
		node.add_child(body)
func _ready() -> void:
	surface(Vector3(198,-.2,-328),Vector3(132,.4,164),Color("686f69"),true)
	for x in [144,252]: surface(Vector3(x,.025,-328),Vector3(18,.05,164),Color("333b40"))
	for z in [-258,-398]: surface(Vector3(198,.026,z),Vector3(132,.052,14),Color("333b40"))
	for b in DowntownCatalog.buildings(0):
		var footprint: Rect2=b.footprint
		surface(Vector3(footprint.get_center().x,b.height*.5,footprint.get_center().y),Vector3(footprint.size.x,b.height,footprint.size.y),Color("858f92") if b.floors>3 else Color("976d55"),true)
		var marker := Label3D.new()
		marker.text="%d · %s" % [b.number,b.name]
		marker.position=b.root+Basis(Vector3.UP,b.yaw)*Vector3(0,2,.3)
		marker.rotation.y=b.yaw
		marker.pixel_size=.01
		marker.font_size=32
		add_child(marker)
	surface(Vector3(198,.03,-328),Vector3(84,.06,8),Color("414c51"))
