class_name GlyphText
extends RefCounted
## 3D lettering from the Blender glyph set (assets/delivery/glyphs.glb: glyph_A..Z, glyph_0..9,
## glyph_dash/dot/slash/amp/space, each with an "advance" extra, cap height 1 m), used for big,
## easy-to-read house numbers, unit numbers and shop numbers. Digits are white with a soft glow
## so they also read at night, on a dark navy plate.

const SOURCE := "res://assets/delivery/glyphs.glb"
static var _meshes: Dictionary = {}     ## char -> {"mesh": Mesh, "advance": float}
static var _plate: Mesh
static var _paint: StandardMaterial3D
static var _loaded := false

static func available() -> bool:
	return ResourceLoader.exists(SOURCE)

static func _load() -> void:
	if _loaded: return
	_loaded = true
	if not available(): return
	var scene: Node = load(SOURCE).instantiate()
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var name := str(mi.name)
		var holder: Node = mi
		while holder != null and not str(holder.name).begins_with("glyph_") and not str(holder.name).begins_with("number_plate"):
			holder = holder.get_parent()
		if holder == null: continue
		var key := str(holder.name)
		var extras: Dictionary = holder.get_meta("extras", {}) if holder.has_meta("extras") else {}
		if key.begins_with("number_plate"):
			_plate = mi.mesh
			continue
		var ch := key.trim_prefix("glyph_")
		ch = {"dash": "-", "dot": ".", "slash": "/", "amp": "&", "space": " "}.get(ch, ch)
		_meshes[ch] = {"mesh": mi.mesh, "advance": float(extras.get("advance", mi.mesh.get_aabb().size.x + 0.12)), "offset": mi.transform}
	scene.free()
	_paint = StandardMaterial3D.new()
	_paint.albedo_color = Color("f7f4ea")
	_paint.roughness = 0.4
	_paint.emission_enabled = true
	_paint.emission = Color("fff3d6")
	_paint.emission_energy_multiplier = 0.55

## Text `height` metres tall (cap height), centred on the origin, front facing +Z, on a plate.
## proud > 0: the digits are deepened so their faces stand `proud` metres in front of the plate
## (their backs sunk 3 mm into it) - house numbers use 1.7 cm so the faces never sit within a few
## mm of the plate (z-fighting at distance). Default: the original thin glyphs 2 mm above it.
static func build(text: String, height: float, plate := true, proud := 0.0) -> Node3D:
	_load()
	var root := Node3D.new()
	root.name = "Number_" + text
	var t := text.to_upper()
	if _meshes.is_empty():
		# Fallback when the glyph set is missing: a large Label3D.
		var l := Label3D.new()
		l.text = t
		l.font_size = 96
		l.pixel_size = height / 70.0
		l.outline_size = 8
		l.modulate = Color("f7f4ea")
		root.add_child(l)
		return root
	var x := 0.0
	var pieces: Array = []
	for i in range(t.length()):
		var ch := t[i]
		if not _meshes.has(ch):
			x += 0.5 * height
			continue
		var g: Dictionary = _meshes[ch]
		pieces.append([g, x])
		x += float(g.advance) * height
	var width := x
	for p in pieces:
		var g: Dictionary = p[0]
		var mi := MeshInstance3D.new()
		mi.mesh = g.mesh
		mi.material_override = _paint
		mi.scale = Vector3.ONE * height
		mi.position = Vector3(float(p[1]) - width * 0.5, -height * 0.5, 0.0205 if plate else 0.0)   # plate front is at z 0.02
		if plate and proud > 0.0:
			var aabb: AABB = (g.mesh as Mesh).get_aabb()
			if aabb.size.z > 1e-5:
				# Plate face at 0.018 (plate mesh front 0.02, plate node at -0.002).
				mi.scale.z = (proud + 0.003) / aabb.size.z
				mi.position.z = 0.015 - aabb.position.z * mi.scale.z
		mi.visibility_range_end = 70.0
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)
	if plate:
		var pm := MeshInstance3D.new()
		var margin := height * 0.35
		if _plate != null:
			pm.mesh = _plate
			pm.scale = Vector3(width + margin * 2.0, height + margin * 2.0, 1.0)
		else:
			var b := BoxMesh.new()
			b.size = Vector3(width + margin * 2.0, height + margin * 2.0, 0.02)
			pm.mesh = b
			var m := StandardMaterial3D.new()
			m.albedo_color = Color("1d2b45")
			pm.material_override = m
		pm.position.z = -0.002
		pm.visibility_range_end = 70.0
		root.add_child(pm)
	return root
