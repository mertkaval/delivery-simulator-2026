shader_type spatial;
render_mode diffuse_burley;
// Road surface for Mert Road Studio exports (tools/roads/mrs/export.py road_masks()).
// The baked tile (albedo / normal / roughness, metres UV x uv_scale) carries the aggregate, cracks and
// repairs; the position-dependent wear the bake cannot hold comes from per-vertex data:
//   UV.x  = lateral offset from the centre line (m, right +), UV.y = along (m, V flipped by glTF)
//   UV2   = (lane width, half median) of the road
//   COLOR = (inside a traffic lane, curb-dirt band, gutter / drain wetness, 1)
// Wheel tracks are rebuilt per pixel at +-0.8 m of every lane centre (the Blender asphalt shader rule).
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rough_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_normal = false;
uniform bool has_rough = false;
uniform float roughness_base = 0.85;
uniform vec2 uv_scale = vec2(0.25);
uniform vec2 uv_offset = vec2(0.0);
uniform float tire_wear : hint_range(0.0, 1.0) = 0.75;
uniform float edge_dirt : hint_range(0.0, 1.0) = 0.8;
uniform float wetness : hint_range(0.0, 1.0) = 0.55;
uniform float normal_depth = 1.0;
varying vec2 road_layout;
varying vec3 masks;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) { return 0.5 * vnoise(p) + 0.3 * vnoise(p * 2.03) + 0.2 * vnoise(p * 4.1); }

void vertex() {
	road_layout = UV2;
	masks = COLOR.rgb;
}

void fragment() {
	vec2 uv = UV * uv_scale + uv_offset;
	vec3 base = texture(albedo_tex, uv).rgb;
	float rough = has_rough ? texture(rough_tex, uv).g : roughness_base;
	float lat = UV.x;
	float along = UV.y;
	float lw = max(road_layout.x, 2.0);
	float mh = road_layout.y;
	// tyre tracks
	float u = (abs(lat) - mh) / lw;
	float d = abs(fract(u) - 0.5) * lw;
	float wander = (fbm(vec2(along * 0.15, lat * 0.3)) - 0.5) * 0.3;
	float track = 1.0 - smoothstep(0.06, 0.3, abs(d + wander - 0.8));
	float streak = smoothstep(0.3, 0.75, fbm(vec2(along * 0.33, lat * 8.0)));
	float tire = clamp(track * masks.r * (0.3 + 0.7 * streak) * tire_wear, 0.0, 1.0);
	base = mix(base, base * 0.6 + vec3(0.01), tire * 0.55);
	rough -= tire * 0.22;
	// curb dirt: gritty band broken up along the kerb
	float ebreak = smoothstep(0.3, 0.75, fbm(vec2(along * 0.4, lat * 1.2)));
	float edge = clamp(masks.g * (0.35 + 0.9 * ebreak) * edge_dirt, 0.0, 1.0);
	vec3 grit = vec3(0.19, 0.16, 0.12) * (0.75 + 0.5 * vnoise(uv * 160.0));
	base = mix(base, grit, edge * 0.75);
	rough += edge * 0.12;
	// localized wetness at the gutter / drains
	float wet = clamp(masks.b * wetness * (0.55 + 0.45 * fbm(vec2(along * 0.25, lat * 0.9))), 0.0, 1.0);
	base *= 1.0 - 0.38 * wet;
	rough = mix(rough, 0.1, wet);
	ALBEDO = base;
	ROUGHNESS = clamp(rough, 0.05, 1.0);
	METALLIC = 0.0;
	SPECULAR = 0.5;
	if (has_normal) {
		NORMAL_MAP = texture(normal_tex, uv).rgb;
		NORMAL_MAP_DEPTH = normal_depth * (1.0 - 0.75 * wet);
	}
}
