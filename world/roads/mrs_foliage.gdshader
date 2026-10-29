shader_type spatial;
render_mode cull_disabled, diffuse_lambert, world_vertex_coords, alpha_to_coverage_and_one;
// MRS foliage v5 (MrsFoliage, docs/roads/FOLIAGE.md): street trees (LOD0 and the MRS LOD1), shrubs, grass,
// hedges and beds of the landscape kit. One shading model shared with Blender
// (tools/roads/mrs/game_trees.py _v5_material), so both renderers agree under the same light:
//   albedo  texture x COLOR.a (crown / bark AO) x tint x per-instance tint (INSTANCE_CUSTOM.rgb, 0.5 = neutral)
//   leaves  diffuse (1 - t) Lambert(N.L) + t Lambert(-N.L) = Blender Mix(Principled, Translucent, t), GGX specular
//           F0 0.04 weighted (1 - t); the soft crown normal on both sides of a card (Godot's automatic back-face
//           flip undone), so a crown shades as one rounded volume instead of a patchwork of flipped cards
//   alpha   leaf test at alpha_cut on alpha x (1 + mip x mip_scale): the coverage of the full-resolution texture at
//           any distance (plain mipmapped alpha erodes canopies with distance), alpha-to-coverage under MSAA
//   LOD     per-instance distance from the MAIN camera (also in shadow passes) to the crown; levels crossfade by
//           a screen-space dither over a band (MrsFoliage sets lod_level / lod_bands), no cell-wide pops or gaps
//   wind    as foliage_wind.gdshader: COLOR.r sway, COLOR.g flutter, COLOR.b phase
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_albedo = true;
uniform bool use_normal_map = false;
uniform int kind = 0;                 // 0 leaves (cut-out, translucent), 1 bark, 2 solid foliage (hedge core), 3 plain
uniform float alpha_cut = 0.42;
uniform float mip_scale = 0.05;      // measured: coverage within 0.96-1.02 of the supersampled truth, 8-200 m
uniform float translucency = 0.25;
uniform float roughness = 0.78;
uniform float ao_strength = 1.0;
uniform vec4 base_color : source_color = vec4(1.0);
uniform vec4 tint : source_color = vec4(1.0);
uniform bool crown_normals_both_sides = true;
uniform float sway = 0.16;
uniform float flutter = 0.03;
uniform float wind_speed = 1.0;
uniform float wind = 1.0;
uniform int lod_level = -1;           // -1: no LOD levels (plants: fade_end only), 0 / 1: tree LOD0 / LOD1
uniform vec4 lod_bands = vec4(70.0, 10.0, 170.0, 20.0);   // LOD0 -> 1 at x over a band y, LOD1 -> impostor at z over w
uniform vec2 fade_end = vec2(0.0, 0.0);                     // plants: fade out at x over a band y (0 = never)
uniform float lod_lift = 5.0;         // per-instance distance: to origin + lift x instance scale (the crown)
instance uniform vec3 cell_point = vec3(0.0);   // per-cell distance: to the cell node's custom AABB centre (set by
                                      // MrsFoliage), the point Godot measures visibility ranges to: node ranges and dither agree

varying float ao;
varying vec3 inst_tint;
varying float lod_x;

float band(float d, float at, float width) {
	return clamp((d - (at - 0.5 * width)) / max(width, 1e-3), 0.0, 1.0);
}

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float scale_y = length(MODEL_MATRIX[1].xyz);
	// ---- LOD coordinate from the main camera (the same value in colour and shadow passes). LOD0 <-> LOD1 and the
	// plant fade use the cell distance (LOD0 / LOD1 cells share a grid and position: exact node ranges, no gaps);
	// LOD1 <-> impostor uses the instance distance (impostors are on a coarser grid; they cost two triangles).
	vec3 cam = MAIN_CAM_INV_VIEW_MATRIX[3].xyz;
	float d_cell = distance(cam, cell_point);
	float d_inst = distance(cam, origin + vec3(0.0, lod_lift * scale_y, 0.0));
	if (lod_level >= 0) {
		lod_x = band(d_cell, lod_bands.x, lod_bands.y) + band(d_inst, lod_bands.z, lod_bands.w) - float(lod_level);
	} else if (fade_end.x > 0.0) {
		lod_x = band(d_cell, fade_end.x, fade_end.y);
	} else {
		lod_x = 0.0;
	}
	// ---- wind (foliage_wind.gdshader)
	float seed = fract(sin(dot(origin.xz, vec2(12.9898, 78.233))) * 43758.5453);
	float t = TIME * wind_speed;
	float gust = 0.6 + 0.4 * sin(t * 0.31 + origin.x * 0.012 + origin.z * 0.009);
	float bend = (sin(t * 1.05 + seed * 6.2831 + origin.x * 0.04) * 0.72 + sin(t * 2.2 + seed * 3.7) * 0.28) * gust;
	float w = COLOR.r;
	vec2 dir = normalize(vec2(1.0, 0.42));
	float amount = w * sway * scale_y * wind;
	VERTEX.xz += dir * bend * amount;
	VERTEX.y -= abs(bend) * w * amount * 0.12;
	float ph = COLOR.b * 6.2831 + seed * 12.0;
	VERTEX += NORMAL * sin(t * 6.3 + ph) * COLOR.g * flutter * wind * (0.4 + w) * gust;
	// ---- outside this level's band: collapse (nothing rasterised)
	if (lod_x <= -1.0 || lod_x >= 1.0) {
		VERTEX = origin;
	}
	ao = mix(1.0, COLOR.a, ao_strength);
	inst_tint = INSTANCE_CUSTOM.rgb * 2.0;
}

// interleaved gradient noise: a stable screen-space dither in [0, 1)
float ign(vec2 p) {
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

void fragment() {
	vec4 tex = has_albedo ? texture(albedo_tex, UV) : vec4(1.0);
	ALBEDO = tex.rgb * base_color.rgb * tint.rgb * inst_tint * ao;
	vec2 tsz = vec2(textureSize(albedo_tex, 0));
	float a = 1.0;
	if (kind == 0) {
		vec2 dx = dFdx(UV * tsz);
		vec2 dy = dFdy(UV * tsz);
		float mip = max(0.0, 0.5 * log2(max(dot(dx, dx), dot(dy, dy))));
		a = tex.a * (1.0 + mip * mip_scale);
	}
	// dithered LOD crossfade: this level owns the pixels where lod_x + noise falls in [0, 1)
	float x = lod_x + ign(FRAGCOORD.xy);
	if (x < 0.0 || x >= 1.0) {
		discard;
	}
	ALPHA = a;
	ALPHA_SCISSOR_THRESHOLD = kind == 0 ? alpha_cut : 0.0;
	ALPHA_ANTIALIASING_EDGE = kind == 0 ? alpha_cut : 0.0;
	ALPHA_TEXTURE_COORDINATE = UV * tsz;
	ROUGHNESS = roughness;
	SPECULAR = 0.5;
	if (use_normal_map) {
		NORMAL_MAP = texture(normal_tex, UV).rgb;
	}
	if (kind == 0 && crown_normals_both_sides && !FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}

void light() {
	float t = kind == 0 ? translucency : 0.0;
	float ndl = dot(NORMAL, LIGHT);
	vec3 irr = LIGHT_COLOR * ATTENUATION;
	DIFFUSE_LIGHT += irr * ((1.0 - t) * max(ndl, 0.0) + t * max(-ndl, 0.0)) / PI;
	if (ndl > 0.0) {
		vec3 h = normalize(LIGHT + VIEW);
		float ndh = max(dot(NORMAL, h), 0.0);
		float ndv = max(dot(NORMAL, VIEW), 1e-3);
		float r2 = ROUGHNESS * ROUGHNESS;
		float a2 = r2 * r2;
		float dd = ndh * ndh * (a2 - 1.0) + 1.0;
		float dist = a2 / (PI * dd * dd);
		float k = r2 * 0.5;
		float vis = (ndl / (ndl * (1.0 - k) + k)) * (ndv / (ndv * (1.0 - k) + k));
		float fr = 0.04 + 0.96 * pow(1.0 - max(dot(LIGHT, h), 0.0), 5.0);
		SPECULAR_LIGHT += irr * SPECULAR_AMOUNT * (1.0 - t) * dist * vis * fr / (4.0 * ndv);
	}
}
