shader_type spatial;
// CityForge ground: the classic city's scanned grass, blended by the terrain data in COLOR:
//   r = lawn (lots and parks: greener, mown), g = sand (shores, lake and sea beds), b = rock (steep),
//   a = 0 under water.
uniform sampler2D grass_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float city_half = 1024.0;       // beyond the city square the land turns to forest
varying vec3 p;
varying vec4 zones;
global uniform float wetness;
float h(vec2 v) { return fract(sin(dot(v, vec2(127.1, 311.7))) * 43758.5453); }
float n(vec2 v) { vec2 i = floor(v), f = fract(v); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
void vertex() {
	p = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	zones = COLOR;
}
void fragment() {
	float broad = n(p.xz * 0.16), patch = n(p.xz * 1.6), fine = n(p.xz * 60.0);
	vec2 uv = p.xz * 0.55;
	vec3 scanned = texture(grass_color, uv).rgb;
	vec3 wild = scanned * mix(0.72, 1.08, broad) * vec3(0.82, 1.0, 0.66);
	vec3 lawn = scanned * mix(0.9, 1.1, patch) * vec3(0.8, 1.05, 0.7);
	vec3 sand = vec3(0.56, 0.5, 0.38) * (0.85 + 0.15 * fine + 0.1 * broad);
	vec3 rock = vec3(0.4, 0.39, 0.37) * (0.7 + 0.3 * n(p.xz * 0.9) + 0.1 * fine);
	vec3 col = mix(wild, lawn, smoothstep(0.2, 0.8, zones.r));
	col = mix(col, sand, smoothstep(0.15, 0.7, zones.g));
	col = mix(col, rock, smoothstep(0.2, 0.75, zones.b + (n(p.xz * 0.3) - 0.5) * 0.3));
	float outside = max(abs(p.x), abs(p.z)) - city_half;
	float forest = smoothstep(30.0, 350.0, outside) * smoothstep(0.25, 0.65, n(p.xz * 0.004) * 0.6 + n(p.xz * 0.02) * 0.4 + 0.25);
	vec3 trees = vec3(0.05, 0.1, 0.045) * (0.7 + 0.6 * n(p.xz * 0.08) + 0.25 * n(p.xz * 0.6));
	col = mix(col, trees, forest * (1.0 - zones.b * 0.7) * zones.a * (1.0 - zones.g));
	col *= mix(0.35, 1.0, zones.a);           // a = 0 under water: dark lake and sea beds
	ALBEDO = col * mix(1.0, 0.7, wetness);
	ROUGHNESS = mix(0.95, 0.6, wetness * zones.b);
	NORMAL_MAP = texture(grass_normal, uv).rgb;
	NORMAL_MAP_DEPTH = 0.45 * (1.0 - max(zones.g, zones.b));
}
