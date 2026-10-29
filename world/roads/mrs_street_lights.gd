class_name MrsStreetLights
extends Node3D
## Street lights from Mert Road Studio light records (tools/roads/mrs/lighting.py light_records(),
## the "lights" list of the street-model / lighting JSON). Records are in Blender Z-up coordinates;
## Godot position = (x, z, -y). One SpotLight3D (OmniLight3D for type "omni") per record:
## inverse-square attenuation (2.0), spot_range = the record's range, distance fade per class and
## shadows only on the `max_shadowed` lights that contribute most at the focus point (camera).
## Lamp heads are the emissive MRS_PropLamp* / MRS_Lamp* materials of the imported poles; set_night()
## switches them together with the lights.
##
##   var lights := MrsStreetLights.new(); add_child(lights)
##   lights.build(records, {"max_shadowed": 4, "focus": camera.global_position, "lamp_root": poles_node})
##   lights.follow(camera)          # re-picks the shadow casters as the camera moves
##   lights.set_night(1.0)          # 0 = day (lights hidden, lamp emission off)

const DEFAULTS: Dictionary = {
	"max_shadowed": 4,            # shadow-casting lights at once (positional shadow atlas budget)
	"energy_scale": 1.0,          # multiplies every record's energy (game exposure differs from the Blender night)
	"fade_scale": 1.0,            # multiplies fade_begin / fade_length (quality presets)
	"bake_mode": "disabled",      # disabled | static | dynamic (dynamic feeds SDFGI / VoxelGI at a cost per light)
	"soft_shadows": false,        # light_size from the luminaire size (PCSS, costs more)
	"shadow_bias": 0.04,
	"lamp_emission": 6.0,         # emission_energy_multiplier of the lamp materials at night
	"specular": 0.5,
}

var options: Dictionary = {}
var records: Array[Dictionary] = []
var lights: Array[Light3D] = []
var lamp_materials: Array[BaseMaterial3D] = []
var night: float = 1.0
var focus: Vector3 = Vector3.ZERO
var follow_target: Node3D = null
var _since_update: float = 0.0
var _last_focus: Vector3 = Vector3(INF, INF, INF)

static func to_godot(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

static func bake_mode_of(name: String) -> Light3D.BakeMode:
	match name:
		"static": return Light3D.BAKE_STATIC
		"dynamic": return Light3D.BAKE_DYNAMIC
	return Light3D.BAKE_DISABLED

## Creates the lights. Options: see DEFAULTS, plus "focus" (Vector3, Godot coordinates) for the first
## shadow pick and "lamp_root" (Node) whose MRS_PropLamp* / MRS_Lamp* materials set_night() drives.
## Returns {"records", "active", "shadowed", "spot", "omni", "lamp_materials"}.
func build(recs: Array, opts: Dictionary = {}) -> Dictionary:
	clear()
	options = DEFAULTS.duplicate()
	options.merge(opts, true)
	var energy_scale: float = float(options["energy_scale"])
	var fade_scale: float = float(options["fade_scale"])
	var bake: Light3D.BakeMode = bake_mode_of(str(options["bake_mode"]))
	var soft: bool = bool(options["soft_shadows"])
	for item: Variant in recs:
		var rec: Dictionary = item as Dictionary
		var pos: Vector3 = to_godot(rec["position"] as Array)
		var dir: Vector3 = to_godot(rec["direction"] as Array).normalized()
		var rng: float = float(rec.get("range", 20.0))
		var att: float = float(rec.get("attenuation", 2.0))
		var light: Light3D
		if str(rec.get("type", "spot")) == "omni":
			var omni := OmniLight3D.new()
			omni.omni_range = rng
			omni.omni_attenuation = att
			light = omni
		else:
			var spot := SpotLight3D.new()
			spot.spot_range = rng
			spot.spot_attenuation = att
			spot.spot_angle = clampf(float(rec.get("spot_angle", 60.0)), 1.0, 179.0)
			spot.spot_angle_attenuation = float(rec.get("spot_angle_attenuation", 1.0))
			light = spot
		light.name = str(rec.get("id", "Lamp%d" % lights.size()))
		var c: Array = rec.get("color", [1.0, 1.0, 1.0]) as Array
		light.light_color = Color(float(c[0]), float(c[1]), float(c[2]))
		light.light_energy = float(rec.get("energy", 1.0)) * energy_scale
		light.light_specular = float(options["specular"])
		light.light_bake_mode = bake
		light.shadow_enabled = false
		light.shadow_bias = float(options["shadow_bias"])
		if soft:
			light.light_size = 0.25
		light.distance_fade_enabled = true
		light.distance_fade_begin = float(rec.get("fade_begin", 60.0)) * fade_scale
		light.distance_fade_length = float(rec.get("fade_length", 20.0)) * fade_scale
		light.distance_fade_shadow = float(rec.get("shadow_fade", 30.0)) * fade_scale
		var up: Vector3 = Vector3.FORWARD if absf(dir.y) > 0.95 else Vector3.UP
		light.transform = Transform3D(Basis.looking_at(dir, up), pos)
		light.set_meta("base_energy", light.light_energy)
		light.set_meta("shadow_ok", bool(rec.get("shadow", false)))
		light.set_meta("class", str(rec.get("class", "")))
		add_child(light)
		lights.append(light)
		records.append(rec)
	if options.has("lamp_root") and options["lamp_root"] is Node:
		collect_lamp_materials(options["lamp_root"] as Node)
	var f: Variant = options.get("focus", Vector3.ZERO)
	focus = f if f is Vector3 else Vector3.ZERO
	update_shadows(focus)
	set_night(night)
	var s: Dictionary = stats()
	print("MrsStreetLights: ", s["records"], " records, ", s["active"], " active (", s["spot"], " spot / ", s["omni"], " omni), ", s["in_range"], " within fade of the focus, ",
		s["shadowed"], " shadow-casting (max ", options["max_shadowed"], "), ", s["lamp_materials"], " lamp materials")
	return s

func clear() -> void:
	for l: Light3D in lights:
		l.queue_free()
	lights.clear()
	records.clear()

## active = enabled lights; in_range = enabled lights closer to the focus than fade_begin + fade_length
## (the ones the renderer still draws); shadowed = shadow-casting lights.
func stats() -> Dictionary:
	var active := 0
	var in_range := 0
	var shadowed := 0
	var spots := 0
	for l: Light3D in lights:
		if l.visible:
			active += 1
			var p: Vector3 = l.global_position if l.is_inside_tree() else l.position
			if not l.distance_fade_enabled or p.distance_to(focus) < l.distance_fade_begin + l.distance_fade_length:
				in_range += 1
		if l.visible and l.shadow_enabled:
			shadowed += 1
		if l is SpotLight3D:
			spots += 1
	return {"records": records.size(), "active": active, "in_range": in_range, "shadowed": shadowed, "spot": spots,
		"omni": lights.size() - spots, "lamp_materials": lamp_materials.size()}

## Shadows on the `max_shadowed` shadow-eligible lights with the largest contribution at `at`
## (energy / distance^2, within each light's shadow fade distance); all others shadow-free.
## Returns the number of shadow-casting lights.
func update_shadows(at: Vector3) -> int:
	focus = at
	_last_focus = at
	var limit: int = int(options.get("max_shadowed", 4))
	var scored: Array[Vector2] = []    # (score, index)
	for i in lights.size():
		var l: Light3D = lights[i]
		l.shadow_enabled = false
		if not bool(l.get_meta("shadow_ok", false)) or not l.visible:
			continue
		var d2: float = maxf(l.global_position.distance_squared_to(at) if l.is_inside_tree() else l.position.distance_squared_to(at), 1.0)
		var reach: float = l.distance_fade_shadow     # shadows cut off beyond this camera distance
		if d2 > reach * reach:
			continue
		scored.append(Vector2(l.light_energy / d2, float(i)))
	scored.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x > b.x)
	var n := 0
	for s: Vector2 in scored:
		if n >= limit:
			break
		lights[int(s.y)].shadow_enabled = true
		n += 1
	return n

## Keep the shadow casters near `target` (usually the camera); re-picked every 0.25 s once it moved 2 m.
func follow(target: Node3D) -> void:
	follow_target = target
	set_process(target != null)

func _process(delta: float) -> void:
	if follow_target == null or not is_instance_valid(follow_target):
		return
	_since_update += delta
	var p: Vector3 = follow_target.global_position
	if _since_update >= 0.25 and p.distance_squared_to(_last_focus) > 4.0:
		_since_update = 0.0
		update_shadows(p)

## Finds the lamp-head materials (MRS_PropLamp*, MRS_Lamp*) under `root`: mesh surface materials,
## surface overrides and material overrides. Returns how many distinct materials were found.
func collect_lamp_materials(root: Node) -> int:
	var seen: Dictionary = {}
	for n: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		var mats: Array[Material] = [mi.material_override]
		for s in mi.mesh.get_surface_count():
			mats.append(mi.mesh.surface_get_material(s))
			mats.append(mi.get_surface_override_material(s))
		for m: Material in mats:
			var bm := m as BaseMaterial3D
			if bm == null or seen.has(bm):
				continue
			var nm: String = bm.resource_name
			if nm.begins_with("MRS_PropLamp") or nm.begins_with("MRS_Lamp"):
				seen[bm] = true
				if not bm.has_meta("night_emission"):
					var col: Color = bm.emission if bm.emission_enabled else bm.albedo_color
					bm.set_meta("night_emission", col)
				lamp_materials.append(bm)
	return lamp_materials.size()

## 1 = night (lights on, lamp heads glowing), 0 = day (lights hidden: a dark light still costs
## culling; lamp emission off). Values between dim the energies (dusk).
func set_night(amount: float) -> void:
	night = clampf(amount, 0.0, 1.0)
	for l: Light3D in lights:
		l.visible = night > 0.02
		l.light_energy = float(l.get_meta("base_energy", 1.0)) * night
	var e: float = float(options.get("lamp_emission", 6.0)) * night
	for m: BaseMaterial3D in lamp_materials:
		m.emission_enabled = night > 0.02
		m.emission = m.get_meta("night_emission", Color(1.0, 0.93, 0.75)) as Color
		m.emission_energy_multiplier = e
	# city-kit glazing (frontage buildings): the downtown window shader lights its interiors at night
	if UrbanKit.window_material != null:
		UrbanKit.window_material.set_shader_parameter("night", night)
	if night > 0.02:
		update_shadows(focus)
