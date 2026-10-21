class_name StreetLife
extends RefCounted
## Hooks the street-life pass into the city (CedarNeighborhood calls attach() once the world is
## built and set_time() with the clock): traffic and pedestrian signals (TrafficSignals),
## scrolling LED boards on the shops and restaurants (LedBoards) and the street effects
## (StreetVFX: exhaust puffs, brake lights, grill smoke, wet-road spray).

## Test/benchmark switch: false builds the city without signals, LED boards and effects.
static var enabled := true

static func attach(world: Node3D) -> void:
	if not enabled: return
	var signals := TrafficSignals.new()
	signals.name = "TrafficSignals"
	world.add_child(signals)
	var boards := LedBoards.new()
	boards.name = "LedBoards"
	world.add_child(boards)
	var vfx := StreetVFX.new()
	vfx.name = "StreetVFX"
	world.add_child(vfx)

static func set_time(world: Node3D, hour: float, daylight: float) -> void:
	for name in ["TrafficSignals", "LedBoards", "StreetVFX"]:
		var node := world.get_node_or_null(name)
		if node != null and node.has_method("set_time"): node.call("set_time", hour, daylight)
