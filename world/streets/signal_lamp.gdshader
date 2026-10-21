shader_type spatial;
// Signal lenses and pedestrian symbols (MultiMesh): per-instance COLOR = lamp hue,
// INSTANCE_CUSTOM.r = lit (0/1). Lit lamps show an LED cluster with a brighter core; unlit
// lamps are dark tinted glass. One material for every lamp of the city.
render_mode cull_back;
uniform float energy = 6.0;
uniform float pitch = 0.016;      // LED spacing (m) in the lamp plane
uniform float radius = 0.138;     // lens radius for the core falloff (0 = flat symbol)
varying vec3 local;
varying float lit;
varying vec3 hue;

void vertex() {
	local = VERTEX;
	lit = INSTANCE_CUSTOM.r;
	hue = COLOR.rgb;
}

void fragment() {
	vec2 g = local.xy / pitch;
	vec2 cell = fract(g) - 0.5;
	float led = smoothstep(0.46, 0.2, length(cell));
	// Far away the LED grid averages out instead of shimmering.
	float aa = clamp(length(fwidth(g)) * 1.4 - 0.5, 0.0, 1.0);
	float pattern = mix(led, 0.6, aa);
	float core = radius > 0.0 ? 1.0 - 0.45 * smoothstep(0.2, 1.0, length(local.xy) / radius) : 1.0;
	vec3 off = hue * 0.05 + vec3(0.012);
	ALBEDO = mix(off, hue * 0.55, lit);
	ROUGHNESS = 0.14;
	SPECULAR = 0.7;
	EMISSION = hue * energy * lit * (0.3 + 0.7 * pattern) * core;
}
