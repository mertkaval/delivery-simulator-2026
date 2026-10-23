class_name GameInput
extends RefCounted
## The game's input actions: default key bindings (added when missing, so remaps in the project or
## by the player are kept), the key a prompt names for an action, and the on-foot "use" click.

const DEFAULTS := {"bicycle": KEY_B, "move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D,
	"sprint": KEY_SHIFT, "jump": KEY_SPACE, "interact": KEY_E, "phone": KEY_TAB, "map": KEY_M, "pause_game": KEY_ESCAPE,
	"bell": KEY_Q, "bag": KEY_F, "drop": KEY_G, "use_water": KEY_1, "use_snack": KEY_2, "camera_view": KEY_V, "walk": KEY_CTRL}

static func bind_defaults() -> void:
	for action: String in DEFAULTS:
		if InputMap.has_action(action): continue
		InputMap.add_action(action)
		var key := InputEventKey.new()
		key.physical_keycode = DEFAULTS[action]
		InputMap.action_add_event(action, key)

## The key bound to `action`, as the prompts show it ("E", "Tab", "Escape").
static func key_label(action: String) -> String:
	var event := InputMap.action_get_events(action)[0] as InputEventKey
	return OS.get_keycode_string(event.physical_keycode if event.physical_keycode != 0 else event.keycode)

## Left click on foot (mouse captured, nothing open) works like E.
static func is_use_click(event: InputEvent) -> bool:
	return event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
