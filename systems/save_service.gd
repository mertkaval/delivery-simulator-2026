class_name DeliverySave
extends RefCounted
const PATH = "user://delivery_save.json"
var error: String = ""

func save_game(data: Dictionary, path: String = PATH) -> bool:
	if not valid_envelope(data):
		error = "Save rejected: session data is inconsistent."
		return false
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if file == null:
		error = "Could not write save: " + error_string(FileAccess.get_open_error())
		return false
	file.store_string(JSON.stringify(data))
	file.flush()
	var write_error := file.get_error()
	file.close()
	if write_error != OK or not valid_envelope(read_json(path + ".tmp")):
		error = "Save verification failed. Previous save retained."
		return false
	# Copy only a valid active save; never replace a good backup with corruption.
	if valid_envelope(read_json(path)):
		var backup_error := DirAccess.copy_absolute(path, path + ".bak")
		if backup_error != OK:
			error = "Could not preserve backup. Save stopped."
			return false
	var result := DirAccess.rename_absolute(path + ".tmp", path)
	if result != OK:
		error = "Could not replace save: " + error_string(result)
		return false
	error = ""
	return true

func load_game(path: String = PATH) -> Dictionary:
	for candidate in [path, path + ".bak"]:
		var data: Variant = read_json(candidate)
		if valid_envelope(data):
			error = "Recovered the previous backup; the invalid primary file was preserved." if candidate != path else ""
			return data
	error = "No valid save found. Start a new shift or restore a backup."
	return {}

static func read_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path)) != OK:
		return null
	return parser.data

static func valid_envelope(data: Variant) -> bool:
	if not DeliverySession.validate(data) or not data.has("player") or not data.player is Dictionary:
		return false
	if not data.player.has("position") or not data.player.position is Array or data.player.position.size() != 3:
		return false
	if data.player.has("bicycle"):
		if not data.player.bicycle is Array or data.player.bicycle.size() != 3 or not data.player.get("mounted") is bool:
			return false
		for value in data.player.bicycle:
			if not (value is float or value is int) or not is_finite(float(value)) or absf(float(value)) > 800:
				return false
	for value in data.player.position:
		if not (value is float or value is int) or not is_finite(float(value)) or absf(float(value)) > 800:
			return false
	if data.player.has("bicycle_yaw") and (not (data.player.bicycle_yaw is float or data.player.bicycle_yaw is int) or not is_finite(float(data.player.bicycle_yaw))):
		return false
	if data.player.has("mounted") and not data.player.has("bicycle"):
		return false
	return data.player.has("yaw") and (data.player.yaw is float or data.player.yaw is int) and is_finite(float(data.player.yaw))

