extends SceneTree
var materials := {}
var static_visuals := 0
var collision_objects := 0
var static_bodies := 0
var active_materials := {}
var collision_shapes := 0
func _initialize() -> void: call_deferred("run")
func inspect(node: Node) -> void:
	if node is CollisionObject3D: collision_objects+=1
	if node is StaticBody3D: static_bodies+=1
	if node is CollisionShape3D: collision_shapes+=1
	if node is GeometryInstance3D:
		static_visuals+=1
		if node.material_override!=null: materials[node.material_override.get_instance_id()]=true
		if node.material_override!=null: active_materials[node.material_override.get_instance_id()]=true
		var mesh: Mesh=null
		if node is MeshInstance3D: mesh=node.mesh
		elif node is MultiMeshInstance3D and node.multimesh!=null: mesh=node.multimesh.mesh
		if mesh!=null:
			for i in range(mesh.get_surface_count()):
				var material := mesh.surface_get_material(i)
				if material!=null: materials[material.get_instance_id()]=true
				if material!=null and node.material_override==null: active_materials[material.get_instance_id()]=true
	for child in node.get_children(): inspect(child)
func run() -> void:
	root.size=Vector2i(1280,720)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var world := CedarNeighborhood.new()
	root.add_child(world)
	world.set_time(14)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.current=true
	camera.fov=65
	for i in range(45): await process_frame
	inspect(world)
	var stage := "after" if "--after" in OS.get_cmdline_user_args() else "before"
	var report := {"stage":stage,"resolution":"1280x720","materials_loaded":materials.size(),"materials_bound":active_materials.size(),"urban_shared_materials":UrbanKit.materials.size(),"geometry_nodes":static_visuals,"static_bodies":static_bodies,"collision_objects":collision_objects,"collision_shapes":collision_shapes,"density":DowntownCatalog.metrics(),"views":[]}
	var views := [["main_avenue",Vector3(243,1.7,-280),Vector3(243,2,-390)],["intersection",Vector3(239,1.7,-388),Vector3(273,4,-420)],["transition",Vector3(112,1.7,-390),Vector3(165,3,-405)],["alley",Vector3(157,1.7,-328),Vector3(228,2,-328)],["skyline",Vector3(104,28,-225),Vector3(316,21,-474)],["restaurant",Vector3(170,1.7,-266),Vector3(170,1.5,-273)],["apartment",Vector3(230,1.7,-268),Vector3(230,1.5,-273)]]
	for view in views:
		for height in [0,1.7]:
			camera.position=view[1]+Vector3.UP*height
			camera.look_at(view[2])
			for i in range(35): await process_frame
			var samples: Array[float]=[]
			for i in range(60):
				var before := Time.get_ticks_usec()
				await process_frame
				samples.append((Time.get_ticks_usec()-before)/1000.0)
			samples.sort()
			var name: String=view[0]+("_pedestrian" if height==0 else "_vehicle")
			report.views.append({"view":name,"median_ms":samples[30],"p95_ms":samples[57],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),"texture_mib":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576.0,"navigation_server_ms":Performance.get_monitor(Performance.TIME_NAVIGATION_PROCESS)*1000})
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://tmp/downtown_%s_%s.png" % [stage,name])
	var route_start := Time.get_ticks_usec()
	for i in range(1000): CityCatalog.route(Vector3(-8,0,23),CityCatalog.address_position(i%36),false)
	report.route_query_mean_ms=(Time.get_ticks_usec()-route_start)/1000000.0
	route_start=Time.get_ticks_usec()
	for i in range(1000): CityCatalog.route(Vector3(244,0,-280),DowntownCatalog.DESTINATIONS[i%5],false)
	report.urban_route_query_mean_ms=(Time.get_ticks_usec()-route_start)/1000000.0
	var file := FileAccess.open("res://tmp/downtown_%s_metrics.json" % stage,FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	print(JSON.stringify(report))
	quit()


