shader_type spatial;
render_mode cull_disabled, diffuse_lambert, world_vertex_coords, alpha_to_coverage_and_one, shadows_disabled;
// MRS foliage v5 distant trees (MrsFoliage, docs/roads/FOLIAGE.md): hemi-octahedral impostors.
// Every species was rendered from IMP_N x IMP_N directions over the upper hemisphere (tools/roads/mrs/game_trees.py
// bake_impostors: albedo x AO with coverage alpha, object-space normals). Here one camera-facing quad per tree picks
// the three frames around the view direction (grid triangle, barycentric weights) (hemi-octahedral grid triangle) and blends them, so the silhouette is
// right from the street, the footbridge deck and the air (the old crossed quads read as an X from above).
// In shadow passes the quad faces the light and picks the light's frames: the shadow is the tree's silhouette.
// It is lit like the leaves (Lambert + translucency + GGX, mrs_foliage.gdshader) with the baked normals; it does
// not receive shadows (a flat quad would shadow itself).
// INSTANCE_CUSTOM: rgb = tint (0.5 neutral), a = species slot / 255.
uniform sampler2D albedo_atlas : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_atlas : filter_linear_mipmap, repeat_disable;
uniform float frames = 8.0;           // IMP_N
uniform float grid = 4.0;             // species slots per atlas side
uniform float frame_px = 128.0;
uniform vec4 species[16];             // xyz = bounds centre (object space), w = bounding radius
uniform float alpha_cut = 0.42;
uniform float mip_scale = 0.05;      // measured: coverage within 0.96-1.02 of the supersampled truth, 8-200 m
uniform float translucency = 0.25;
uniform float roughness = 0.78;
uniform float direct_scale = 0.45;    // stands in for the crown's self-shadowing: measured, impostor / LOD0 luminance 0.99 at 200 m, 1.03-1.05 at 120 m
uniform bool dither_coverage = true;  // alpha = baked coverage: keep a pixel with that probability (else A2C test at alpha_cut)
uniform vec4 tint : source_color = vec4(1.0);
uniform int lod_level = 2;
uniform vec4 lod_bands = vec4(70.0, 10.0, 170.0, 20.0);
uniform float lod_lift = 5.0;

varying vec2 uv_a;
varying vec2 uv_b;
varying vec2 uv_c;
varying flat vec2 off_a;
varying flat vec2 off_b;
varying flat vec2 off_c;
varying flat vec3 wts;
varying flat vec3 inst_tint;
varying float lod_x;

float band(float d, float at, float width) {
	return clamp((d - (at - 0.5 * width)) / max(width, 1e-3), 0.0, 1.0);
}

vec2 hemi_oct_encode(vec3 v) {
	vec3 a = abs(v);
	vec2 p = v.xz / (a.x + a.y + a.z);
	return vec2(p.x + p.y, p.x - p.y);
}

vec3 hemi_oct_decode(vec2 o) {
	vec2 p = vec2(o.x + o.y, o.x - o.y) * 0.5;
	return normalize(vec3(p.x, 1.0 - abs(p.x) - abs(p.y), p.y));
}

// frame-local uv (0..1, v down) of a point `rel` (world, relative to the bounds centre) in frame fi
vec2 frame_uv(vec2 fi, vec3 rel, mat3 rot, float r) {
	vec3 d = rot * hemi_oct_decode(fi / (frames - 1.0) * 2.0 - 1.0);
	vec3 right = vec3(d.z, 0.0, -d.x);
	float l = length(right);
	right = l > 1e-5 ? right / l : rot[0];
	vec3 up = cross(d, right);
	return vec2(dot(rel, right), -dot(rel, up)) / (2.0 * r) + 0.5;
}

vec2 frame_offset(vec2 fi, int slot) {
	vec2 tile = vec2(float(slot % int(grid)), float(slot / int(grid)));
	return (tile * frames + fi) / (grid * frames);
}

void vertex() {
	int slot = int(INSTANCE_CUSTOM.a * 255.0 + 0.5);
	vec4 sd = species[slot];
	mat3 basis = mat3(MODEL_MATRIX[0].xyz, MODEL_MATRIX[1].xyz, MODEL_MATRIX[2].xyz);
	float s = length(basis[1]);
	mat3 rot = basis / s;
	vec3 origin = MODEL_MATRIX[3].xyz;
	vec3 centre = origin + basis * sd.xyz;
	float r = sd.w * s;
	float d = distance(MAIN_CAM_INV_VIEW_MATRIX[3].xyz, origin + vec3(0.0, lod_lift * s, 0.0));
	// the LOD1 <-> impostor band on the instance distance (as mrs_foliage.gdshader); LOD0 is never this far
	lod_x = lod_level >= 0 ? 1.0 + band(d, lod_bands.z, lod_bands.w) - float(lod_level) : 0.0;
	// view direction towards the viewer (shadow passes are orthographic: the light direction)
	bool ortho = PROJECTION_MATRIX[3][3] > 0.5;
	vec3 v = ortho ? normalize(INV_VIEW_MATRIX[2].xyz) : normalize(INV_VIEW_MATRIX[3].xyz - centre);
	vec3 vo = transpose(rot) * v;
	vo.y = max(vo.y, 0.0);
	vo = normalize(vo + vec3(0.0, 1e-4, 0.0));
	// the three frames around the view direction (grid triangle, barycentric weights)
	vec2 g = (hemi_oct_encode(vo) * 0.5 + 0.5) * (frames - 1.0);
	vec2 g0 = clamp(floor(g), vec2(0.0), vec2(frames - 2.0));
	vec2 f = clamp(g - g0, vec2(0.0), vec2(1.0));
	vec2 fa;
	vec2 fb;
	vec2 fc;
	if (f.x + f.y < 1.0) {
		fa = g0; fb = g0 + vec2(1.0, 0.0); fc = g0 + vec2(0.0, 1.0);
		wts = vec3(1.0 - f.x - f.y, f.x, f.y);
	} else {
		fa = g0 + vec2(1.0); fb = g0 + vec2(0.0, 1.0); fc = g0 + vec2(1.0, 0.0);
		wts = vec3(f.x + f.y - 1.0, 1.0 - f.x, 1.0 - f.y);
	}
	// camera-facing quad through the bounds centre
	vec3 right = cross(vec3(0.0, 1.0, 0.0), v);
	right = length(right) > 1e-4 ? normalize(right) : rot[0];
	vec3 up = cross(v, right);
	vec2 q = vec2(UV.x - 0.5, 0.5 - UV.y);
	vec3 p = centre + (right * q.x + up * q.y) * 2.0 * r;
	uv_a = frame_uv(fa, p - centre, rot, r);
	uv_b = frame_uv(fb, p - centre, rot, r);
	uv_c = frame_uv(fc, p - centre, rot, r);
	off_a = frame_offset(fa, slot);
	off_b = frame_offset(fb, slot);
	off_c = frame_offset(fc, slot);
	VERTEX = (lod_x <= -1.0 || lod_x >= 1.0) ? origin : p;
	NORMAL = v;
	inst_tint = INSTANCE_CUSTOM.rgb * 2.0;
}

float ign(vec2 p) {
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

void fragment() {
	// One frame per pixel, picked by a dither against the barycentric weights: the frames are not parallax-aligned,
	// so averaging their alphas would erode the canopy below the cut; picking keeps each frame's coverage.
	float pick = ign(FRAGCOORD.yx * 1.37 + vec2(23.0, 61.0));
	vec2 uv = pick < wts.x ? uv_a : (pick < wts.x + wts.y ? uv_b : uv_c);
	vec2 off = pick < wts.x ? off_a : (pick < wts.x + wts.y ? off_b : off_c);
	float cell = 1.0 / (grid * frames);
	float edge = 0.5 / frame_px;
	float inside = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
	vec2 auv = off + clamp(uv, vec2(edge), vec2(1.0 - edge)) * cell;
	// gradients from the continuous uv_a (all frames share the scale): no mip jumps where neighbours pick other frames
	vec2 gx = dFdx(uv_a) * cell;
	vec2 gy = dFdy(uv_a) * cell;
	vec4 sa = textureGrad(albedo_atlas, auv, gx, gy);
	vec3 n = textureGrad(normal_atlas, auv, gx, gy).rgb * 2.0 - 1.0;
	vec2 dx = dFdx(uv_a * frame_px);
	vec2 dy = dFdy(uv_a * frame_px);
	float mip = max(0.0, 0.5 * log2(max(dot(dx, dx), dot(dy, dy))));
	float x = lod_x + ign(FRAGCOORD.xy);
	if (x < 0.0 || x >= 1.0) {
		discard;
	}
	ALBEDO = sa.rgb * tint.rgb * inst_tint;
	float cov = sa.a * inside * (1.0 + mip * mip_scale);
	if (dither_coverage) {
		// the frames' alpha is coverage (fractions of a 10 cm texel covered by leaves): a cut would drop the sparse
		// crown edges, a per-pixel keep-with-probability keeps the mean coverage (independent of the other dithers)
		float h = fract(sin(dot(floor(FRAGCOORD.xy), vec2(12.9898, 78.233))) * 43758.5453);
		ALPHA = cov > h ? 1.0 : 0.0;
		ALPHA_SCISSOR_THRESHOLD = 0.5;
		ALPHA_ANTIALIASING_EDGE = 0.0;
	} else {
		ALPHA = cov;
		ALPHA_SCISSOR_THRESHOLD = alpha_cut;
		ALPHA_ANTIALIASING_EDGE = alpha_cut;
	}
	ALPHA_TEXTURE_COORDINATE = uv_a * frame_px;
	ROUGHNESS = roughness;
	SPECULAR = 0.5;
	vec3 nw = normalize(mat3(MODEL_MATRIX) * normalize(n));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}

void light() {
	float t = translucency;
	float ndl = dot(NORMAL, LIGHT);
	vec3 irr = LIGHT_COLOR * ATTENUATION * direct_scale;
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
