class_name HiggsfieldBicycle
extends RefCounted
## Geometry and materials originate exclusively from Higgsfield 3D Jutsu revision 5.
## courier_bicycle_steer.glb is the same model with the fork, stem, handlebars, mudguard and
## front wheel split into a SteeringPivot on the head-tube axis (local +Y), built in Blender.
const SOURCE = preload("res://world/higgsfield/courier_bicycle_steer.glb")

static func create() -> Node3D:
	var imported: Node3D = SOURCE.instantiate()
	var source: Node3D = imported.find_child("Higgsfield_Courier_Bicycle", true, false)
	assert(source != null, "Higgsfield bicycle root missing")
	var bicycle := Node3D.new()
	bicycle.name = "HiggsfieldBicycle"
	bicycle.set_meta("asset_source", "Higgsfield 3D Jutsu / revision 5")
	# Export faces +Z; the game uses -Z. Keep wheel axes in game coordinates.
	copy_parts(source, Transform3D(Basis(Vector3.UP, PI), Vector3.ZERO), bicycle, Transform3D.IDENTITY)
	imported.free()
	return bicycle

static func copy_parts(node: Node3D, parent_transform: Transform3D, destination: Node3D, destination_transform: Transform3D) -> void:
	var world := parent_transform * node.transform
	var target := destination
	var target_transform := destination_transform
	if str(node.name) == "SteeringPivot":
		# Keep the pivot's orientation: rotating about its local Y steers around the head tube.
		target = Node3D.new()
		target.name = "SteeringPivot"
		destination.add_child(target)
		target.transform = destination_transform.affine_inverse() * world
		target.set_meta("rest", target.transform)
		target_transform = world
	elif str(node.name) in ["FrontWheelPivot", "RearWheelPivot"]:
		target = Node3D.new()
		target.name = "WheelFront" if str(node.name) == "FrontWheelPivot" else "WheelRear"
		destination.add_child(target)
		target.transform = destination_transform.affine_inverse() * Transform3D(Basis.IDENTITY, world.origin)
		target_transform = Transform3D(Basis.IDENTITY, world.origin)
	if node is MeshInstance3D:
		var part := MeshInstance3D.new()
		part.name = node.name
		part.mesh = node.mesh
		part.transform = target_transform.affine_inverse() * world
		target.add_child(part)
	for child in node.get_children():
		if child is Node3D: copy_parts(child, world, target, target_transform)
