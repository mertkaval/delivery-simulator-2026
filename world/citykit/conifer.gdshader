shader_type spatial;
render_mode cull_disabled;
// Pacific Northwest conifer foliage: dark needle mass with fine needle streaks along the branch,
// lighter new-growth tips, deeper colour towards the trunk, and a slow wind sway with height.
uniform vec4 needle_dark : source_color = vec4(0.07, 0.14, 0.07, 1.0);
uniform vec4 needle_light : source_color = vec4(0.22, 0.34, 0.15, 1.0);
varying vec3 wp;
varying float radial;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	radial = length(VERTEX.xz);
	vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float sway = sin(TIME * 0.9 + world.x * 0.15 + world.z * 0.1) * 0.06 * VERTEX.y / 10.0;
	VERTEX.x += sway * radial * 0.4;
	VERTEX.z += sway * radial * 0.25;
	wp = world;
}

void fragment() {
	// Needle streaks run outwards from the trunk.
	vec2 polar = vec2(atan(wp.z, wp.x) * 6.0, radial * 3.0);
	float streak = noise(vec2(polar.x * 8.0, polar.y * 0.6)) * 0.6 + noise(wp.xz * 9.0 + wp.y) * 0.4;
	float tip = smoothstep(0.55, 1.0, fract(radial * 0.35)) * 0.5;
	float tone = clamp(streak * 0.7 + tip, 0.0, 1.0);
	vec3 col = mix(needle_dark.rgb, needle_light.rgb, tone);
	col *= mix(0.55, 1.0, clamp(radial * 0.6, 0.0, 1.0));  // self-shadowing towards the trunk
	ALBEDO = col * (FRONT_FACING ? 1.0 : 0.7);
	ROUGHNESS = 0.92;
	SPECULAR = 0.25;
	BACKLIGHT = vec3(0.12, 0.16, 0.06);
}
