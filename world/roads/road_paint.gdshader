shader_type spatial;
// Thermoplastic road paint with traffic wear: worn spots reveal the asphalt beneath.
uniform vec4 paint_color : source_color = vec4(0.86, 0.86, 0.82, 1.0);
uniform float wear = 0.3; // 0 = fresh, 1 = almost gone
uniform float specular_amount = 0.6;
global uniform float wetness;
uniform sampler2D asphalt : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
varying vec3 world_pos;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float n = noise(world_pos.xz * 1.6) * 0.55 + noise(world_pos.xz * 7.0) * 0.3 + hash(floor(world_pos.xz * 40.0)) * 0.15;
	float worn = smoothstep(1.0 - wear, 1.0 - wear + 0.18, n);
	vec3 road = texture(asphalt, world_pos.xz * 0.32).rgb * vec3(0.5, 0.53, 0.56);
	vec3 paint = paint_color.rgb * mix(0.9, 1.04, noise(world_pos.xz * 0.3));
	ALBEDO = mix(paint, road, worn * 0.8) * mix(1.0, 0.7, wetness);
	// Glass beads give fresh paint a slightly sharper highlight than the asphalt.
	ROUGHNESS = mix(mix(specular_amount < 0.5 ? 0.75 : 0.48, 0.85, worn), 0.2, wetness);
	SPECULAR = mix(specular_amount, 0.4, worn);
}
