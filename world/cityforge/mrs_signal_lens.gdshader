shader_type spatial;
render_mode diffuse_burley;
// Signal lens of the Mert Road Studio signal head in Port Halden (one MultiMesh for every pole in the city).
// Every pole's phase cycle runs on the GPU from its instance custom data:
//   INSTANCE_CUSTOM.r = the phase of the approach the head faces, .g = the junction's phase count,
//   .b = the junction's cycle offset (x 100 s)
// Each phase: GREEN s green, AMBER s amber, then ALL_RED s of all red before the next phase. The pole's
// pedestrian head (crossing the next approach) walks during the first WALK s of its phase.
uniform int lens = 0;                 // 0 red, 1 amber, 2 green, 3 pedestrian red, 4 pedestrian green
uniform vec3 lens_color : source_color = vec3(1.0, 0.1, 0.05);
uniform float on_energy = 5.0;
uniform float off_energy = 0.04;
const float GREEN = 18.0;
const float AMBER = 3.0;
const float ALL_RED = 2.0;
const float WALK = 12.0;
varying float lit;

void vertex() {
	float slot = GREEN + AMBER + ALL_RED;
	float phases = max(INSTANCE_CUSTOM.g, 1.0);
	float t = mod(TIME + INSTANCE_CUSTOM.b * 100.0, phases * slot);
	float active = floor(t / slot);
	float s = t - active * slot;
	bool mine = abs(active - INSTANCE_CUSTOM.r) < 0.5;
	int state = mine ? (s < GREEN ? 2 : (s < GREEN + AMBER ? 1 : 0)) : 0;
	bool walk = mine && s < WALK;
	lit = 0.0;
	if (lens <= 2) lit = state == lens ? 1.0 : 0.0;
	else if (lens == 3) lit = walk ? 0.0 : 1.0;
	else lit = walk ? 1.0 : 0.0;
}

void fragment() {
	ALBEDO = lens_color * 0.08;
	ROUGHNESS = 0.2;
	EMISSION = lens_color * mix(off_energy, on_energy, lit);
}
