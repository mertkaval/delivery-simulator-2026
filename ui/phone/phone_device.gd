class_name PhoneDevice
extends Node3D
## The courier's phone as a real object in first person (assets/gadgets/budget_phone.glb).
## Tab raises it from the pocket into view; the camera narrows its field of view a little so
## the screen is easy to read; Tab lowers it again. The screen shows PhoneOS rendered in a
## SubViewport, and mouse clicks / wheel on the 3D screen are forwarded to it (taps land
## exactly where the pointer is on the glass).

const MODEL := "res://assets/gadgets/budget_phone.glb"
const ZOOM_FOV := 52.0

var viewport: SubViewport
var os: PhoneOS
var model: Node3D
var screen: MeshInstance3D
var out := false
var SHOWN := Transform3D(Basis.from_euler(Vector3(0.06, -0.08, 0.0)), Vector3(0.035, -0.012, -0.2))
var HIDDEN := Transform3D(Basis.from_euler(Vector3(-1.1, 0.0, 0.25)), Vector3(0.16, -0.38, -0.22))
var _tween: Tween
var _fov_before := 78.0

func setup(game: Node) -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	viewport = SubViewport.new()
	viewport.size = Vector2i(PhoneOS.W, PhoneOS.H)
	viewport.disable_3d = true
	viewport.transparent_bg = false
	viewport.gui_embed_subwindows = true
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	add_child(viewport)
	os = PhoneOS.new()
	os.game = game
	viewport.add_child(os)
	if ResourceLoader.exists(MODEL):
		model = (load(MODEL) as PackedScene).instantiate()
		screen = model.find_child("Screen", true, false) as MeshInstance3D
	if model == null or screen == null:
		model = fallback_model()
		screen = model.get_node("Screen") as MeshInstance3D
	add_child(model)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_texture = viewport.get_texture()
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	screen.material_override = mat
	for mi in model.find_children("*", "GeometryInstance3D", true, false):
		(mi as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	transform = HIDDEN
	visible = false

## A plain stand-in phone (used until the Blender model exists).
func fallback_model() -> Node3D:
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = Vector3(0.074, 0.155, 0.0105)
	body.mesh = b
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("2b2f33")
	m.roughness = 0.6
	body.material_override = m
	root.add_child(body)
	var glass := MeshInstance3D.new()
	glass.name = "Screen"
	var q := QuadMesh.new()
	q.size = Vector2(0.0645, 0.136)
	glass.mesh = q
	glass.position.z = 0.0057
	root.add_child(glass)
	return root

func raise(camera: Camera3D) -> void:
	if out: return
	out = true
	visible = true
	os.open_page("home")
	_fov_before = camera.fov
	animate(SHOWN, 0.35)
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(camera, "fov", ZOOM_FOV, 0.35).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)

func lower(camera: Camera3D) -> void:
	if not out: return
	out = false
	animate(HIDDEN, 0.3, func() -> void: visible = false)
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(camera, "fov", _fov_before, 0.3)

func animate(to: Transform3D, seconds: float, then: Callable = Callable()) -> void:
	if _tween: _tween.kill()
	_tween = create_tween()
	_tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_tween.tween_property(self, "transform", to, seconds)
	if then.is_valid(): _tween.tween_callback(then)

## Pixel on the phone screen under the mouse pointer, or (-1, -1) when it's off the glass.
func screen_point(camera: Camera3D, mouse: Vector2) -> Vector2:
	var origin := camera.project_ray_origin(mouse)
	var dir := camera.project_ray_normal(mouse)
	var inv := screen.global_transform.affine_inverse()
	var o := inv * origin
	var d := inv.basis * dir
	var box := screen.get_aabb()
	var plane_z := box.get_center().z
	if absf(d.z) < 1e-6: return Vector2(-1, -1)
	var t := (plane_z - o.z) / d.z
	if t < 0.0: return Vector2(-1, -1)
	var hit := o + d * t
	var u := (hit.x - box.position.x) / maxf(box.size.x, 1e-6)
	var v := (hit.y - box.position.y) / maxf(box.size.y, 1e-6)
	if u < 0.0 or u > 1.0 or v < 0.0 or v > 1.0: return Vector2(-1, -1)
	return Vector2(u * PhoneOS.W, (1.0 - v) * PhoneOS.H)

## Forward a mouse event from the game window onto the phone screen. True if it landed there.
func forward(camera: Camera3D, event: InputEvent) -> bool:
	if not out or not (event is InputEventMouse): return false
	var mouse := (event as InputEventMouse).position
	var p := screen_point(camera, mouse)
	if p.x < 0.0: return false
	var e := event.duplicate() as InputEventMouse
	e.position = p
	e.global_position = p
	viewport.push_input(e, true)
	return true
