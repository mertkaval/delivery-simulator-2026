shader_type spatial;
// CityForge water (sea, lake, river): moving ripples, fresnel reflection, depth-faded colour.
render_mode blend_mix, depth_draw_always, cull_back, specular_schlick_ggx;
uniform vec3 shallow : source_color = vec3(0.1, 0.27, 0.3);
uniform vec3 deep : source_color = vec3(0.02, 0.07, 0.11);
uniform sampler2D depth_tex : hint_depth_texture, filter_linear;
varying vec3 wp;
float h(vec2 v) { return fract(sin(dot(v, vec2(127.1, 311.7))) * 43758.5453); }
float n(vec2 v) { vec2 i = floor(v), f = fract(v); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
void vertex() { wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec2 q = wp.xz;
	float t = TIME;
	float a = n(q * 0.35 + vec2(t * 0.05, t * 0.03));
	float b = n(q * 1.3 - vec2(t * 0.11, t * 0.07));
	float c = n(q * 4.1 + vec2(t * 0.21, -t * 0.17));
	vec2 slope = vec2(a - 0.5, b - 0.5) * 0.22 + vec2(c - 0.5) * 0.04;
	NORMAL = normalize(NORMAL + (VIEW_MATRIX * vec4(slope.x, 0.0, slope.y, 0.0)).xyz);
	float scene_depth = texture(depth_tex, SCREEN_UV).r;
	vec4 world = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, scene_depth, 1.0);
	float thickness = clamp((-world.z / world.w) - (-VERTEX.z), 0.0, 40.0);
	float d = 1.0 - exp(-thickness * 0.6);
	ALBEDO = mix(shallow, deep, d);
	ALPHA = mix(0.72, 0.97, d);
	ROUGHNESS = 0.1;
	METALLIC = 0.0;
	SPECULAR = 0.6;
}
