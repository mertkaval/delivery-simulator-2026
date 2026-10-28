shader_type spatial;
// CityForge asphalt with painted markings from the road data baked into the mesh:
//   UV   = (metres from the centreline, metres from the road's start)
//   UV2  = (marking class: 0 local, 1 arterial, 2 downtown, -1 intersection; metres to the end)
//   COLOR.r / .g = control at the start / end node: 1 signal (crosswalk + stop bar), 0.5 stop sign.
// Traffic drives on the right: drivers arriving at the start are on +UV.x, at the end on -UV.x.
uniform sampler2D asphalt : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D asphalt_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float texture_scale = 0.32;
varying vec3 world_pos;
varying vec4 marks;
global uniform float wetness;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float band(float x, float a, float b) { return step(a, x) * step(x, b); }

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	marks = COLOR;
}

void fragment() {
	vec2 uv = world_pos.xz * texture_scale;
	vec3 base = texture(asphalt, uv).rgb * vec3(0.52, 0.55, 0.58);
	base *= mix(0.86, 1.08, noise(world_pos.xz * 0.045));
	float u = UV.x, v = 1.0 - UV.y;            // glTF stores V flipped
	float cls = UV2.x, v_end = 1.0 - UV2.y;
	float au = abs(u);
	float paint = 0.0;
	vec3 paint_col = vec3(0.92, 0.92, 0.88);
	if (cls > 0.5) {
		// double yellow centre line
		float yellow = band(au, 0.1, 0.24);
		float lane = cls > 1.5 ? 4.0 : 4.5;
		float edge = cls > 1.5 ? 7.4 : 8.4;
		float dash = band(abs(au - lane), 0.0, 0.07) * step(fract(v / 9.0), 0.34);
		float edge_line = band(abs(au - edge), 0.0, 0.08);
		if (yellow > 0.5) { paint = 1.0; paint_col = vec3(0.9, 0.7, 0.12); }
		else paint = max(dash, edge_line);
	}
	if (cls > -0.5) {
		// crosswalks and stop bars at controlled ends (the markings beat the lane lines)
		float near_start = v, near_end = v_end;
		for (int k = 0; k < 2; k++) {
			float ctrl = k == 0 ? marks.r : marks.g;
			float d = k == 0 ? near_start : near_end;
			float incoming = k == 0 ? step(0.0, u) : step(u, 0.0);
			if (ctrl > 0.6) {
				float zebra = band(d, 0.8, 3.8) * step(fract(u / 1.1), 0.5);
				float stop_bar = band(d, 4.4, 4.85) * incoming * step(0.3, au);
				if (zebra + stop_bar > 0.5) { paint = 1.0; paint_col = vec3(0.92, 0.92, 0.88); }
			} else if (ctrl > 0.1) {
				if (band(d, 1.4, 1.85) * incoming * step(0.3, au) > 0.5) { paint = 1.0; paint_col = vec3(0.92, 0.92, 0.88); }
			}
		}
	}
	float worn = 0.75 + 0.25 * noise(world_pos.xz * 3.0);
	vec3 col = mix(base, paint_col * worn, paint * 0.92);
	float w = wetness;
	ALBEDO = col * mix(1.0, 0.6, w);
	ROUGHNESS = mix(mix(0.93, 0.7, paint), 0.12, w * 0.9);
	NORMAL_MAP = texture(asphalt_normal, uv).rgb;
	NORMAL_MAP_DEPTH = mix(0.8, 0.2, paint);
}
