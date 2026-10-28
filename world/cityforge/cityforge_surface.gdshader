shader_type spatial;
// CityForge surfaces: the classic city's procedural look (world/surface.gdshader) plus the kinds
// the generated city needs. COLOR is the per-instance (MultiMesh) or per-vertex tint, in sRGB;
// roof_from_custom takes the tint from INSTANCE_CUSTOM instead (house roofs).
render_mode diffuse_burley, specular_schlick_ggx;
uniform vec4 tint : source_color = vec4(1.0);
uniform int surface_kind = 0;
uniform bool roof_from_custom = false;
uniform bool tinted = false;            // only siding, leaves and facades take COLOR; trim, glass, bark... don't
// Baked material library (tools/cityforge/materials.py): albedo, OpenGL normal, ORM (occlusion,
// roughness, metallic), one 2 m tile. Mapped by world-space box projection: one texel density
// everywhere, walls by height, roofs along their slope, floors by x/z; no UVs needed.
uniform bool textured = false;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float tile_m = 2.0;
uniform float normal_strength = 1.0;
uniform float emission_energy = 0.0;
varying vec3 world_position;
varying vec3 world_normal;
varying vec3 instance_tint;
global uniform float wetness;
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise(vec3 p) {
	vec3 i = floor(p); vec3 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash(i), hash(i + vec3(1, 0, 0)), f.x), mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x), mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
	vec3 c = roof_from_custom ? INSTANCE_CUSTOM.rgb : (tinted ? COLOR.rgb : vec3(1.0));
	instance_tint = pow(max(c, vec3(0.0)), vec3(2.2));
}
void fragment() {
	vec3 p = world_position;
	vec2 uv = vec2(UV.x, 1.0 - UV.y);  // walls: (metres along the wall, metres above the building base); glTF stores V flipped
	float fine = noise(p * 65.0);
	float broad = noise(p * 1.7);
	float value = 0.94 + 0.08 * fine;
	vec3 extra = vec3(1.0);
	bool window_px = false;
	ROUGHNESS = 0.85;
	METALLIC = 0.0;
	if (surface_kind == 1) { // Asphalt
		value = 0.66 + 0.22 * fine + 0.10 * broad; ROUGHNESS = 0.96;
	} else if (surface_kind == 2) { // Concrete, with slab joints every 1.5 m on flat paving
		value = 0.79 + 0.12 * fine + 0.07 * broad; ROUGHNESS = 0.91;
		if (world_normal.y > 0.8) {
			vec2 g = abs(fract(p.xz / 1.5 + 0.5) - 0.5) * 1.5;
			value *= mix(0.78, 1.0, smoothstep(0.0, 0.02, min(g.x, g.y)));
		}
	} else if (surface_kind == 3) { // Painted lap siding, 18 cm boards
		float board = p.y / 0.18;
		float edge = min(fract(board), 1.0 - fract(board));
		float seam = smoothstep(0.012, 0.012 + max(fwidth(board), 0.035), edge);
		value = (0.88 + 0.06 * noise(p * vec3(1.0, 35.0, 1.0))) * mix(0.82, 1.0, seam); ROUGHNESS = 0.66;
	} else if (surface_kind == 4) { // Timber: vertical boards along the wall
		float board = uv.x / 0.14;
		float seam = smoothstep(0.02, 0.08, min(fract(board), 1.0 - fract(board)));
		value = (0.65 + 0.3 * noise(p * vec3(4.0, 70.0, 4.0))) * mix(0.75, 1.0, seam); ROUGHNESS = 0.76;
	} else if (surface_kind == 5) { // Masonry, staggered courses
		vec2 m = abs(world_normal.z) > 0.5 ? p.xy : p.zy;
		float row = floor(m.y / 0.075);
		vec2 cell = fract(vec2(m.x / 0.23 + mod(row, 2.0) * 0.5, m.y / 0.075));
		float brick = smoothstep(0.025, 0.07, cell.x) * smoothstep(0.04, 0.12, cell.y);
		value = mix(0.62, 0.84 + 0.14 * noise(floor(vec3(m.x / 0.23 + mod(row, 2.0) * 0.5, row, 0.0)) * 3.1) + 0.06 * fine, brick); ROUGHNESS = 0.92;
	} else if (surface_kind == 6) { // Roof shingles, rows across the slope
		float row = fract(p.y * 3.6 + p.x * 0.0);
		value = (0.72 + 0.2 * noise(floor(p * vec3(4.0, 3.6, 4.0)))) * mix(0.62, 1.0, smoothstep(0.02, 0.1, row)); ROUGHNESS = 0.94;
	} else if (surface_kind == 7) { // Tinted glass
		value = 0.72 + 0.2 * smoothstep(-0.5, 1.0, world_normal.y); ROUGHNESS = 0.08; METALLIC = 0.45;
	} else if (surface_kind == 8) { // Painted metal
		value = 0.9; METALLIC = 0.7; ROUGHNESS = 0.38;
	} else if (surface_kind == 9) { // Gravel roof / dirt
		value = 0.62 + 0.24 * broad + 0.12 * fine; ROUGHNESS = 1.0;
	} else if (surface_kind == 12 || surface_kind == 20) { // Facades with windows (20: brick walls)
		float wall = surface_kind == 20 ? 0.0 : 1.0;
		if (surface_kind == 20) {
			float row = floor(uv.y / 0.075);
			vec2 cell = fract(vec2(uv.x / 0.23 + mod(row, 2.0) * 0.5, uv.y / 0.075));
			value = mix(0.62, 0.86 + 0.12 * fine, smoothstep(0.025, 0.07, cell.x) * smoothstep(0.04, 0.12, cell.y));
			extra = vec3(0.62, 0.32, 0.24) / max(tint.rgb, vec3(0.01));
		} else {
			value = 0.86 + 0.08 * fine + 0.06 * broad;
		}
		ROUGHNESS = 0.85;
		if (abs(world_normal.y) < 0.5 && uv.y > 3.4) {
			float fx = fract(uv.x / 3.0), fy = fract(uv.y / 3.4);
			float win = step(0.2, fx) * step(fx, 0.8) * step(0.3, fy) * step(fy, 0.86);
			float frame = win * (1.0 - step(0.23, fx) * step(fx, 0.77) * step(0.33, fy) * step(fy, 0.83));
			if (win > 0.5) {
				window_px = true;
				float lit = step(0.7, hash(floor(vec3(uv.x / 3.0, uv.y / 3.4, p.x * 0.01 + p.z * 0.013))));
				value = frame > 0.5 ? 0.95 : 0.22 + 0.1 * smoothstep(-0.2, 1.0, fy);
				extra = frame > 0.5 ? vec3(0.85, 0.85, 0.82) / max(instance_tint * tint.rgb, vec3(0.05)) : vec3(0.45, 0.6, 0.7) / max(instance_tint * tint.rgb, vec3(0.05));
				ROUGHNESS = frame > 0.5 ? 0.5 : 0.08;
				METALLIC = frame > 0.5 ? 0.0 : 0.4;
				EMISSION = vec3(1.0, 0.82, 0.55) * lit * emission_energy * (1.0 - frame);
			}
		}
	} else if (surface_kind == 13) { // Glass curtain wall: mullions every 1.5 m, floor bands every 3.6 m
		float fx = fract(uv.x / 1.5), fy = fract(uv.y / 3.6);
		float mull = 1.0 - step(0.04, fx) * step(fx, 0.96) * step(0.08, fy) * step(fy, 0.92);
		float band = step(fy, 0.08);
		value = mix(0.55 + 0.25 * smoothstep(-0.3, 1.0, world_normal.y) + 0.1 * noise(vec3(floor(uv.x / 1.5), floor(uv.y / 3.6), 0.0) * 7.0), 0.9, mull);
		ROUGHNESS = mix(0.05, 0.4, mull);
		METALLIC = mix(0.7, 0.3, mull);
		if (band > 0.5) extra = vec3(0.6);
		float lit = step(0.78, hash(floor(vec3(uv.x / 1.5, uv.y / 3.6, p.x * 0.01))));
		EMISSION = vec3(1.0, 0.9, 0.7) * lit * emission_energy * (1.0 - mull) * 0.6;
	} else if (surface_kind == 14) { // Ribbed metal siding
		float rib = 0.5 + 0.5 * sin(uv.x * 6.2831 / 0.3);
		value = 0.78 + 0.16 * rib + 0.05 * fine; METALLIC = 0.5; ROUGHNESS = 0.5;
	} else if (surface_kind == 15) { // Awning fabric stripes
		float stripe = step(0.5, fract(uv.x / 0.6));
		extra = mix(vec3(1.0), vec3(0.95) / max(instance_tint * tint.rgb, vec3(0.05)), stripe);
		value = 0.9 + 0.05 * fine; ROUGHNESS = 0.9;
	} else if (surface_kind == 16) { // Picket fence (cut out)
		float fx = fract(uv.x / 0.14);
		bool rail = (uv.y > 0.15 && uv.y < 0.24) || (uv.y > 0.62 && uv.y < 0.7);
		float tip = 0.82 - abs(fx - 0.3) * 0.6;
		if (!rail && (fx > 0.6 || uv.y > tip)) discard;
		value = 0.95 + 0.04 * fine; ROUGHNESS = 0.7;
	} else if (surface_kind == 17) { // Wrought-iron railing (cut out)
		float fx = fract(uv.x / 0.12);
		bool rail = (uv.y > 0.08 && uv.y < 0.13) || (uv.y > 0.8 && uv.y < 0.86);
		if (!rail && (fx > 0.22 || uv.y > 0.86)) discard;
		value = 0.9; METALLIC = 0.6; ROUGHNESS = 0.45;
	} else if (surface_kind == 18 || surface_kind == 19) { // Hedge / tree leaves: clumpy foliage, light through the edges
		float clump = noise(p * 2.3) * 0.55 + noise(p * 7.0) * 0.3 + noise(p * 23.0) * 0.15;
		value = 0.62 + 0.5 * clump; ROUGHNESS = 0.9;
		NORMAL = normalize(NORMAL + (vec3(noise(p * 6.0), noise(p * 6.0 + 4.0), noise(p * 6.0 + 9.0)) - 0.5) * 0.35);
		BACKLIGHT = vec3(0.25, 0.3, 0.12);
	}
	if (textured && !window_px && surface_kind != 13) {
		vec3 n = normalize(world_normal);
		vec3 T;
		vec2 tuv;
		if (abs(n.y) > 0.95) {
			T = vec3(1.0, 0.0, 0.0);
			tuv = vec2(p.x, -p.z * sign(n.y));
		} else {
			vec2 d = normalize(n.xz);
			T = vec3(-d.y, 0.0, d.x);
			float along = dot(p.xz, vec2(-d.y, d.x));
			float up_v = abs(n.y) < 0.2 ? p.y : -dot(p.xz, d) / max(n.y, 0.25);
			tuv = vec2(along, up_v);
		}
		vec3 B = cross(T, n);
		tuv = vec2(tuv.x, -tuv.y) / tile_m;
		vec3 alb = texture(albedo_tex, tuv).rgb;
		vec3 orm = texture(orm_tex, tuv).rgb;
		vec3 nm = texture(normal_tex, tuv).rgb * 2.0 - 1.0;
		nm.xy *= normal_strength;
		vec3 wn = normalize(T * nm.x + B * nm.y + n * nm.z);
		NORMAL = normalize((VIEW_MATRIX * vec4(wn, 0.0)).xyz);
		AO = orm.r;
		AO_LIGHT_AFFECT = 0.3;
		ROUGHNESS = orm.g;
		METALLIC = orm.b;
		value = 1.0;
		extra = alb;
	}
	float up = smoothstep(0.6, 0.95, world_normal.y);
	float w = (surface_kind == 7 || surface_kind == 8 || surface_kind == 13) ? 0.0 : wetness;
	value *= mix(1.0, 0.66, w * mix(0.45, 1.0, up));
	ROUGHNESS = mix(ROUGHNESS, 0.2, w * up * (surface_kind == 9 ? 0.25 : 1.0));
	ALBEDO = clamp(tint.rgb * instance_tint * extra * value, vec3(0.0), vec3(1.0));
	if (surface_kind < 12 && emission_energy > 0.0) EMISSION = tint.rgb * emission_energy;
}
