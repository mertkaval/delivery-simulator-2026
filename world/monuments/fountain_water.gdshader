shader_type spatial;
// Fountain basin water: two scrolling ripple normal layers, rings spreading from where the
// spout's water lands, and a fresnel blend from the deep basin colour to the sky reflection.
// Opaque (cheap): the putti rocks simply rise through the disc.

uniform sampler2D ripple : hint_normal, filter_linear_mipmap, repeat_enable;
uniform vec3 deep_color : source_color = vec3(0.07, 0.15, 0.16);
uniform vec3 shallow_color : source_color = vec3(0.22, 0.34, 0.33);
uniform float ripple_strength = 0.55;
uniform float ring_radius = 1.05;   // where the falling water lands (m, from the centre)

varying vec3 local_pos;
varying vec3 world_pos;

void vertex() {
	local_pos = VERTEX;
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = world_pos.xz * 0.55;
	vec3 a = texture(ripple, uv + vec2(TIME * 0.045, TIME * 0.031)).xyz;
	vec3 b = texture(ripple, uv * 1.9 + vec2(-TIME * 0.038, TIME * 0.052)).xyz;
	vec3 n = normalize(a * 2.0 - 1.0 + b * 2.0 - 1.0);
	// concentric splash rings round the landing circle
	float r = length(local_pos.xz);
	float d = r - ring_radius;
	float ring = sin(d * 26.0 - TIME * 7.0) * exp(-abs(d) * 4.0);
	vec2 dir = r > 0.001 ? local_pos.xz / r : vec2(0.0);
	n.xy += dir * ring * 0.35;
	NORMAL_MAP = normalize(n) * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = ripple_strength;
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = mix(deep_color, shallow_color, 0.35 + 0.65 * fres);
	ROUGHNESS = 0.05;
	SPECULAR = 0.65;
	METALLIC = 0.0;
}
