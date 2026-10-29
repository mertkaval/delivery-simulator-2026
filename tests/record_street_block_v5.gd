extends SceneTree
## Road Studio v5 traversal recordings of the exported street block (Godot Movie Maker):
##   godot --path . --resolution 1280x720 --fixed-fps 30 --write-movie <out.avi> \
##         --script res://tests/record_street_block_v5.gd -- <export_dir> <scene>
## scenes:
##   junction    fixed view of the signalised four-way: a car and a cyclist stop at the red stop line and go on
##               their phase; a pedestrian waits for the crossing's walk phase (the signal's pedestrian_crossing)
##   street      street-level daytime drive along the avenue lane (camera at 1.3 m)
##   frontage    walk along the shop sidewalk; a delivery van turns into the service yard (access_in movement)
##   footbridge  first-person walk: ramp top -> deck -> stairs down (route edges)
##   trees       dolly out from the park trees, 14 m -> 240 m, rising: LOD0 / LOD1 (75 m) / impostor (175 m)
##   night       night: sidewalk under the lights, then the footbridge deck
## Every agent follows the exported movement / route geometry; nothing is hand-placed.
const StreetBlock := preload("res://world/roads/mrs_street_block.gd")

var block: StreetBlock
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var moon: DirectionalLight3D
var scene_name := "junction"
var t := 0.0
var duration := 20.0
var agents: Array[Dictionary] = []
var cam_path: Dictionary = {}          # {"pts": Array[Vector3], "cum": Array[float], "speed", "s0", "height", "look"}
var cam_keys: Array = []               # [[time, eye, target], ...]
var log_lines: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

static func g(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func pts_of(arr: Array) -> Array[Vector3]:
	var out: Array[Vector3] = []
	for p: Variant in arr: out.append(g(p as Array))
	return out

## ------------------------------------------------------------------ polyline helpers
static func cum_of(pts: Array[Vector3]) -> Array[float]:
	var c: Array[float] = [0.0]
	for i in range(1, pts.size()): c.append(c[i - 1] + pts[i].distance_to(pts[i - 1]))
	return c

static func at_dist(pts: Array[Vector3], cum: Array[float], s: float) -> Vector3:
	s = clampf(s, 0.0, cum[cum.size() - 1])
	var i := cum.bsearch(s)
	if i <= 0: return pts[0]
	if i >= pts.size(): return pts[pts.size() - 1]
	var f := (s - cum[i - 1]) / maxf(cum[i] - cum[i - 1], 1e-5)
	return pts[i - 1].lerp(pts[i], f)

static func nearest_s(pts: Array[Vector3], cum: Array[float], p: Vector3) -> float:
	var best := INF; var bs := 0.0
	for i in range(1, pts.size()):
		var a := pts[i - 1]; var b := pts[i]; var d := b - a; d.y = 0
		var L2 := d.length_squared()
		var f := 0.0 if L2 < 1e-9 else clampf((Vector3(p.x - a.x, 0, p.z - a.z)).dot(d) / L2, 0.0, 1.0)
		var q := a + (b - a) * f
		var dd := Vector2(q.x - p.x, q.z - p.z).length()
		if dd < best: best = dd; bs = cum[i - 1] + f * (cum[i] - cum[i - 1])
	return bs

## ------------------------------------------------------------------ world
func setup_world(night: bool) -> void:
	root.use_debanding = true
	root.msaa_3d = Viewport.MSAA_4X
	env = Environment.new()
	env.sky = Sky.new()
	env.ssao_enabled = true
	env.background_mode = Environment.BG_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 220.0
	root.add_child(sun)
	moon = DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-40.0, 145.0, 0.0)
	moon.light_color = Color(0.62, 0.72, 1.0)
	moon.shadow_enabled = true
	root.add_child(moon)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(900, 900)
	ground.mesh = pm
	ground.position = Vector3(50, -0.16, 0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.16, 0.24, 0.09).linear_to_srgb()
	gm.roughness = 0.95
	ground.material_override = gm
	root.add_child(ground)
	camera = Camera3D.new()
	camera.near = 0.05
	camera.far = 2500.0
	camera.fov = 58.0
	root.add_child(camera)
	camera.current = true
	block = StreetBlock.new()
	root.add_child(block)
	block.build(scene_dir, "street_block", {"max_shadowed": 4, "night": 1.0 if night else 0.0})
	block.street_lights.follow(camera)
	var sky := ProceduralSkyMaterial.new()
	if night:
		var nd: Dictionary = block.model.get("night", {}) as Dictionary
		var sky_info: Dictionary = nd.get("sky", {}) as Dictionary
		var zen: Array = sky_info.get("godot_zenith_linear", [0.015, 0.026, 0.064]) as Array
		var hor: Array = sky_info.get("godot_horizon_linear", [0.085, 0.065, 0.05]) as Array
		sky.sky_top_color = Color(float(zen[0]), float(zen[1]), float(zen[2])).linear_to_srgb()
		sky.sky_horizon_color = Color(float(hor[0]), float(hor[1]), float(hor[2])).linear_to_srgb()
		sky.ground_horizon_color = sky.sky_horizon_color
		sky.ground_bottom_color = Color(0.02, 0.02, 0.025)
		sky.sun_angle_max = 0.0
		env.glow_enabled = true
		env.glow_intensity = 0.4
		env.glow_bloom = 0.02
		env.glow_hdr_threshold = 1.5
		sun.visible = false
		moon.light_energy = float(((nd.get("moon", {}) as Dictionary).get("godot_energy", 0.16)))
		block.street_lights.set_night(1.0)
	else:
		sky.sky_top_color = Color(0.38, 0.52, 0.72)
		sky.sky_horizon_color = Color(0.72, 0.76, 0.80)
		sky.ground_horizon_color = Color(0.62, 0.64, 0.62)
		sky.ground_bottom_color = Color(0.28, 0.30, 0.26)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.ambient_light_energy = 3.0           # matched to the Blender day world (capture_street_block_v4.gd)
		moon.visible = false
		block.street_lights.set_night(0.0)
	env.sky.sky_material = sky

var scene_dir := ""

## ------------------------------------------------------------------ agents
func signal_phase_of(signal_id: String) -> int:
	for j: Variant in block.model.get("junctions", []) as Array:
		for s: Variant in (j as Dictionary).get("signals", []) as Array:
			var sd: Dictionary = s as Dictionary
			if str(sd.get("id", "")) == signal_id: return int(sd.get("phase", -1))
	return -1

func walk_phase_of(crossing_id: String) -> int:
	for j: Variant in block.model.get("junctions", []) as Array:
		for s: Variant in (j as Dictionary).get("signals", []) as Array:
			var sd: Dictionary = s as Dictionary
			if str(sd.get("pedestrian_crossing", "")) == crossing_id: return int(sd.get("phase", -1))
	return -1

## 0 = red, 1 = amber, 2 = green for a phase of a two-phase junction cycle (MrsStreetBlock._process)
func light_state(phase: int) -> int:
	if phase < 0: return 2
	var active: int = block.phase_index % 2
	if active != phase: return 0
	return 1 if block.phase_timer > block.cycle_green else 2

func movement(id: String) -> Dictionary:
	var mv: Dictionary = block.model.get("movements", {}) as Dictionary
	for key: String in ["movements", "bike_movements"]:
		for m: Variant in mv.get(key, []) as Array:
			if str((m as Dictionary).get("id", "")) == id: return m as Dictionary
	return {}

func lane(id: String) -> Array[Vector3]:
	for l: Variant in (block.model.get("movements", {}) as Dictionary).get("lanes", []) as Array:
		if str((l as Dictionary).get("id", "")) == id: return pts_of((l as Dictionary)["points"] as Array)
	return []

## path = the lane up to the stop point + the movement + the next lane; stop at `stop` when the phase is red
func add_vehicle(model: Node3D, pts: Array[Vector3], start_s: float, speed: float, stop_s: float, phase: int, wheel_r: float, kind: String) -> Dictionary:
	root.add_child(model)
	var a := {"node": model, "pts": pts, "cum": cum_of(pts), "s": start_s, "v": speed, "vmax": speed, "stop_s": stop_s, "phase": phase,
		"wheels": CityAssets.wheel_nodes(model), "wheel_r": wheel_r, "kind": kind, "spin": 0.0, "waited": 0.0, "decel": 3.0 if kind != "bike" else 2.0}
	agents.append(a)
	return a

func add_walker(person: Node3D, pts: Array[Vector3], start_s: float, speed: float, stop_s: float, phase: int) -> Dictionary:
	root.add_child(person)
	var a := {"node": person, "pts": pts, "cum": cum_of(pts), "s": start_s, "v": speed, "vmax": speed, "stop_s": stop_s, "phase": phase,
		"wheels": [], "wheel_r": 0.0, "kind": "walker", "spin": 0.0, "waited": 0.0, "decel": 4.0}
	agents.append(a)
	return a

func step_agent(a: Dictionary, dt: float) -> void:
	var cum: Array[float] = a["cum"]
	var pts: Array[Vector3] = a["pts"]
	var s: float = a["s"]; var v: float = a["v"]; var vmax: float = a["vmax"]
	var stop_s: float = a["stop_s"]
	var must_stop := false
	if stop_s > 0.0 and s < stop_s:
		var st := light_state(int(a["phase"]))
		var dist := stop_s - s
		# amber: stop if there is room to (else clear the junction)
		if st == 0 or (st == 1 and dist > v * v / (2.0 * float(a["decel"])) + 1.0): must_stop = true
		if str(a["kind"]) == "walker" and st != 2: must_stop = true      # pedestrians start only on the walk phase
	if must_stop:
		var dist2 := maxf(stop_s - s - 0.2, 0.0)
		var v_allowed := sqrt(2.0 * float(a["decel"]) * dist2)
		v = minf(v + 2.0 * dt, minf(vmax, v_allowed))
		if v < 0.05: a["waited"] = float(a["waited"]) + dt
	else:
		v = minf(vmax, v + (2.5 if str(a["kind"]) != "walker" else 3.0) * dt)
	s = minf(s + v * dt, cum[cum.size() - 1])
	if s >= cum[cum.size() - 1] - 0.01: v = 0.0
	a["s"] = s; a["v"] = v
	var node: Node3D = a["node"]
	var p := at_dist(pts, cum, s)
	var ahead := at_dist(pts, cum, s + 1.5)
	node.global_position = p
	var d := ahead - p; d.y = 0.0
	if d.length() > 0.05:
		var yaw := atan2(-d.x, -d.z)
		node.rotation.y = lerp_angle(node.rotation.y, yaw, minf(1.0, dt * 10.0))
	if str(a["kind"]) == "walker":
		node.set("ground_speed", v)
	else:
		a["spin"] = float(a["spin"]) + v * dt / maxf(float(a["wheel_r"]), 0.1)
		for w: Node3D in a["wheels"]:
			w.rotation.x = -float(a["spin"])
		if str(a["kind"]) == "bike" and a.has("cyclist"):
			BikeRider.ride(a["cyclist"] as Dictionary, v * dt)

## ------------------------------------------------------------------ camera
func cam_follow_path(pts: Array[Vector3], speed: float, height: float, s0: float = 0.0, look: float = 8.0) -> void:
	cam_path = {"pts": pts, "cum": cum_of(pts), "speed": speed, "s0": s0, "height": height, "look": look}

func update_camera() -> void:
	if not cam_path.is_empty():
		var pts: Array[Vector3] = cam_path["pts"]; var cum: Array[float] = cam_path["cum"]
		var s: float = float(cam_path["s0"]) + float(cam_path["speed"]) * t
		var h := Vector3(0, float(cam_path["height"]), 0)
		var eye := at_dist(pts, cum, s) + h
		var tgt := at_dist(pts, cum, s + float(cam_path["look"])) + h - Vector3(0, 0.25, 0)
		if eye.distance_to(tgt) > 0.1: camera.look_at_from_position(eye, tgt, Vector3.UP)
		return
	if cam_keys.is_empty(): return
	var k0: Array = cam_keys[0]; var k1: Array = cam_keys[cam_keys.size() - 1]
	for i in range(1, cam_keys.size()):
		if float((cam_keys[i] as Array)[0]) >= t:
			k0 = cam_keys[i - 1]; k1 = cam_keys[i]; break
	var span := maxf(float(k1[0]) - float(k0[0]), 1e-4)
	var f := clampf((t - float(k0[0])) / span, 0.0, 1.0)
	f = f * f * (3.0 - 2.0 * f)
	var eye2 := (k0[1] as Vector3).lerp(k1[1] as Vector3, f)
	var tgt2 := (k0[2] as Vector3).lerp(k1[2] as Vector3, f)
	camera.look_at_from_position(eye2, tgt2, Vector3.UP)

## ------------------------------------------------------------------ scenes
func setup_junction() -> void:
	duration = 26.0
	# car: avenue west -> east straight (signal S3); cyclist: avenue west cycleway straight (S3); pedestrian: the
	# crossing over the avenue west arm, walking with the other phase (in front of the waiting car)
	var mv := movement("SB_J4_SB_AvenueW_r0_SB_AvenueE_r0")
	var ln := lane("SB_AvenueW_r0")
	var stop := g(mv["stop_point"] as Array)
	var ln_cum := cum_of(ln)
	var s_stop := nearest_s(ln, ln_cum, stop)
	var path: Array[Vector3] = []
	for i in ln.size():
		if ln_cum[i] < s_stop - 0.5: path.append(ln[i])
	path.append_array(pts_of(mv["points"] as Array))
	var exit_ln := lane("SB_AvenueE_r0")
	for i in range(1, mini(exit_ln.size(), 12)): path.append(exit_ln[i])
	var pc := cum_of(path)
	var stop_s := nearest_s(path, pc, stop)
	var car := CityAssets.create("sedan", 400)
	add_vehicle(car, path, maxf(stop_s - 48.0, 0.0), 9.0, stop_s, signal_phase_of(str(mv["signal"])), 0.33, "car")
	# cyclist
	var bmv := movement("SB_J4_SB_AvenueW_bike_SB_AvenueE_straight")
	if not bmv.is_empty():
		var bp := pts_of(bmv["points"] as Array)
		var b0 := bp[0]; var b1 := bp[1]
		var back := (b0 - b1).normalized()
		var bpath: Array[Vector3] = []
		for k in range(12, 0, -1): bpath.append(b0 + back * 3.0 * k)
		bpath.append_array(bp)
		var bike := CityAssets.create("bicycle", 400)
		var holder := Node3D.new()
		holder.add_child(bike)
		var ba := add_vehicle(holder, bpath, 6.0, 5.0, cum_of(bpath)[12] - 0.3, signal_phase_of(str(bmv.get("signal", ""))), 0.35, "bike")
		ba["wheels"] = CityAssets.wheel_nodes(bike)
		if BikeRider.available():
			var rider := BikeRider.mount(bike, 3)
			ba["cyclist"] = {"bike": bike, "rider": rider, "crank": 0.0}
	# pedestrian on the avenue-west crossing
	var xid := ""
	for j: Variant in block.model.get("junctions", []) as Array:
		for x: Variant in (j as Dictionary).get("crossings", []) as Array:
			if str((x as Dictionary).get("road", "")) == "SB_AvenueW": xid = str((x as Dictionary)["id"])
	var routes: Dictionary = block.model.get("routes", {}) as Dictionary
	var xpts: Array[Vector3] = []
	for e: Variant in (routes.get("ped", {}) as Dictionary).get("edges", []) as Array:
		var ed: Dictionary = e as Dictionary
		if str(ed.get("kind", "")) == "crossing" and str(ed.get("a", "")).begins_with(xid): xpts = pts_of(ed["points"] as Array)
	if xpts.size() >= 2:
		var dirx := (xpts[xpts.size() - 1] - xpts[0]).normalized()
		var side := Vector3(-dirx.z, 0, dirx.x)
		var wpath: Array[Vector3] = [xpts[0] - dirx * 1.2 - side * 6.0, xpts[0] - dirx * 1.2]
		wpath.append_array(xpts)
		wpath.append(xpts[xpts.size() - 1] + dirx * 2.0)
		wpath.append(xpts[xpts.size() - 1] + dirx * 2.0 + side * 6.0)
		var wc := cum_of(wpath)
		var person := LivingAssets.person("pedestrian", 4)
		add_walker(person, wpath, 0.0, 1.35, wc[1] + 0.9, walk_phase_of(xid))
		log_lines.append("pedestrian crossing %s walk phase %d" % [xid, walk_phase_of(xid)])
	log_lines.append("car %s signal %s phase %d" % [str(mv["id"]), str(mv["signal"]), signal_phase_of(str(mv["signal"]))])
	cam_keys = [[0.0, g([-34.0, -24.0, 13.0]), g([-6.0, 2.0, 0.0])], [26.0, g([-30.0, -28.0, 11.0]), g([4.0, 0.0, 0.0])]]

func setup_street() -> void:
	duration = 16.0
	# avenue lane -> straight through the signalised junction -> the next lane (one continuous driven path)
	var path := lane("SB_AvenueW_r0")
	var mv := movement("SB_J4_SB_AvenueW_r0_SB_AvenueE_r0")
	if not mv.is_empty():
		var mp := pts_of(mv["points"] as Array)
		var pc := cum_of(path)
		var cut := nearest_s(path, pc, mp[0])
		var head: Array[Vector3] = []
		for i in path.size():
			if pc[i] < cut - 0.5: head.append(path[i])
		head.append_array(mp)
		head.append_array(lane("SB_AvenueE_r0").slice(1))
		path = head
	cam_follow_path(path, 9.0, 1.3, 15.0, 20.0)

func setup_frontage() -> void:
	duration = 26.0
	var recs: Array = block.model.get("destinations", []) as Array
	if recs.is_empty(): return
	var d: Dictionary = recs[0] as Dictionary
	var door := g(d["door"] as Array); var face := g(d["facing"] as Array)
	var tan := Vector3.UP.cross(face).normalized()
	# from the bus stop past the service yard to the shop door, behind a shopper; the van turns in ahead
	var walk: Array[Vector3] = [door + face * 2.6 + tan * 34.0 - Vector3(0, 1.1, 0), door + face * 2.6 - tan * 14.0 - Vector3(0, 1.1, 0)]
	cam_follow_path(walk, 1.45, 1.62, 0.0, 10.0)
	# delivery van: southbound lane -> access_in into the yard (the movement ends on the loading box)
	var acc := {}
	for m: Variant in (block.model.get("movements", {}) as Dictionary).get("movements", []) as Array:
		if str((m as Dictionary).get("turn", "")) == "access_in": acc = m as Dictionary
	if not acc.is_empty():
		var lpts := lane(str(acc["from_lane"]))
		var ap := pts_of(acc["points"] as Array)
		var lc := cum_of(lpts)
		var s0 := nearest_s(lpts, lc, ap[0])
		var path: Array[Vector3] = []
		for i in lpts.size():
			if lc[i] < s0 - 0.3 and lc[i] > s0 - 70.0: path.append(lpts[i])
		path.append_array(ap)
		var van := CityAssets.create("van", 400)
		var va := add_vehicle(van, path, 0.0, 7.0, -1.0, -1, 0.36, "car")
		va["slow_turn"] = true
		log_lines.append("van via %s (%d points)" % [str(acc["id"]), path.size()])
	# a shopper walks to the shop door from the bus stop side
	var person := LivingAssets.person("shopper", 2)
	var ent := g(d["entrance"] as Array)
	add_walker(person, [ent + face * 1.6 + tan * 30.0, ent + face * 1.6 + tan * 2.0, ent, door - face * 0.4 - Vector3(0, 1.1, 0)], 0.0, 1.4, -1.0, -1)

func ped_edges(prefix: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for e: Variant in ((block.model.get("routes", {}) as Dictionary).get("ped", {}) as Dictionary).get("edges", []) as Array:
		if str((e as Dictionary).get("id", "")).begins_with(prefix): out.append(e as Dictionary)
	return out

func footbridge_path() -> Array[Vector3]:
	# ramp (r side) bottom -> head, deck, head (l) -> stairs down (route edge points run sidewalk -> head)
	var ramp: Array[Vector3] = []; var deck: Array[Vector3] = []; var stairs: Array[Vector3] = []
	for e: Dictionary in ped_edges("SB_Footbridge"):
		var k := str(e.get("kind", ""))
		var p := pts_of(e["points"] as Array)
		if k == "footbridge_ramp" and str(e["id"]).contains("_r_"): ramp = p
		elif k == "footbridge_stairs" and str(e["id"]).contains("_l_"): stairs = p
		elif k == "footbridge_deck": deck = p
	var path: Array[Vector3] = []
	path.append_array(ramp)
	if not deck.is_empty():
		if path.size() > 0 and deck[0].distance_to(path[path.size() - 1]) > deck[deck.size() - 1].distance_to(path[path.size() - 1]): deck.reverse()
		path.append_array(deck)
	if not stairs.is_empty():
		if path.size() > 0 and stairs[0].distance_to(path[path.size() - 1]) > stairs[stairs.size() - 1].distance_to(path[path.size() - 1]): stairs.reverse()
		path.append_array(stairs)
	return path

func setup_footbridge() -> void:
	var path := footbridge_path()
	var c := cum_of(path)
	var total: float = c[c.size() - 1]
	var s0 := maxf(0.0, total - 95.0)
	duration = (total - s0) / 2.6 + 1.0
	cam_follow_path(path, 2.6, 1.62, s0, 7.0)
	log_lines.append("footbridge path %.1f m from s %.1f" % [total, s0])

func setup_trees() -> void:
	duration = 22.0
	# a group of park / avenue trees: dolly out along a line away from their centre, rising
	var trees: Array = block.model.get("trees", []) as Array
	var c := Vector3.ZERO; var n := 0
	for tr: Variant in trees:
		var p := g((tr as Dictionary)["pos"] as Array)
		if p.x < -60.0 and p.x > -130.0 and p.z > 20.0 and p.z < 90.0:
			c += p; n += 1
	c = c / maxf(n, 1) if n > 0 else g([-90.0, -55.0, 0.0])
	var dir := Vector3(0.55, 0, -0.83).normalized()
	cam_keys = [[0.0, c + dir * 20.0 + Vector3(0, 3.0, 0), c + Vector3(0, 4.0, 0)],
		[22.0, c + dir * 240.0 + Vector3(0, 30.0, 0), c + Vector3(0, 3.0, 0)]]      # past LOD0->LOD1 (75 m) and LOD1->impostor (175 m)
	log_lines.append("trees: %d in the group, centre %s" % [n, str(c)])

func setup_night() -> void:
	duration = 18.0
	# first 9 s: the avenue's south sidewalk under the lights (the footbridge ramp's sidewalk point), then the deck
	var sp := Vector3(-60.0, 0.15, 20.0)
	for f: Variant in block.model.get("footbridges", []) as Array:
		for e: Variant in (f as Dictionary).get("ped_edges", []) as Array:
			var ed: Dictionary = e as Dictionary
			if str(ed.get("kind", "")) == "ramp" and str(ed.get("end", "")) == "r": sp = g(ed["sidewalk_point"] as Array)
	var along := Vector3(1, 0, 0); var side := Vector3(0, 0, -1.0)      # +x along the avenue; toward the kerb (Blender +y)
	var a0 := sp - along * 26.0 + side * 1.0 + Vector3(0, 1.62, 0)
	var a1 := sp - along * 10.0 + side * 1.0 + Vector3(0, 1.62, 0)
	var path := footbridge_path()
	var c := cum_of(path)
	var mid: float = c[c.size() - 1] * 0.5
	var deck_pos := at_dist(path, c, mid)
	var deck_ahead := at_dist(path, c, mid + 12.0)
	var fwd := (deck_ahead - deck_pos).normalized()
	cam_keys = [[0.0, a0, a0 + along * 12.0 - Vector3(0, 0.35, 0)], [8.5, a1, a1 + along * 12.0 - Vector3(0, 0.35, 0)],
		[8.55, deck_pos + Vector3(0, 1.62, 0), deck_pos + fwd * 12.0 + Vector3(0, 1.4, 0)],
		[18.0, deck_ahead + Vector3(0, 1.62, 0), deck_ahead + fwd * 12.0 + Vector3(0, 1.4, 0)]]

## ------------------------------------------------------------------ main
func run() -> void:
	var args := OS.get_cmdline_user_args()
	scene_dir = args[0] if args.size() > 0 else "res://tmp/roads/v5/block/export"
	scene_name = args[1] if args.size() > 1 else "junction"
	setup_world(scene_name == "night")
	for i in 3: await process_frame
	match scene_name:
		"junction": setup_junction()
		"street": setup_street()
		"frontage": setup_frontage()
		"footbridge": setup_footbridge()
		"trees": setup_trees()
		"night": setup_night()
	for l in log_lines: print("RECORD ", l)
	block.set_phase(0); block.phase_timer = 0.0
	var dt := 1.0 / 30.0
	var frames := int(duration / dt)
	var events: Array[String] = []
	var last_state := {}
	for f in frames:
		t = f * dt
		for a: Dictionary in agents:
			step_agent(a, dt)
			var key := str(a["kind"]) + str(a.get("node", null))
			var moving := float(a["v"]) > 0.3
			if last_state.get(key, true) != moving:
				events.append("%.1fs %s %s (phase %d active %d)" % [t, str(a["kind"]), "moves" if moving else "stops", int(a["phase"]), block.phase_index % 2])
				last_state[key] = moving
		update_camera()
		await process_frame
	for e in events: print("EVENT ", e)
	var waited: Array = []
	for a: Dictionary in agents: waited.append([str(a["kind"]), snappedf(float(a["waited"]), 0.1)])
	print("RECORD DONE ", scene_name, " frames ", frames, " waited ", waited)
	quit(0)
