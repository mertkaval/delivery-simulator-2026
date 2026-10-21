shader_type spatial;
render_mode cull_disabled, diffuse_burley, world_vertex_coords;
// Shared landscape foliage shader (CityLandscape): trees, shrubs, grass, flowers, forest cards and
// tree impostors. No per-tree scripts - all motion comes from the vertex colours baked by
// tools/prepare_landscape.py:
//   COLOR.r = sway weight (0 trunk base .. 1 crown tips), COLOR.g = leaf flutter weight,
//   COLOR.b = flutter phase, COLOR.a = crown ambient occlusion.
// INSTANCE_CUSTOM (MultiMesh custom data): rgb = tint (0.5 = neutral), a = impostor slot / 255.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool use_normal_map = false;
uniform bool leaves = true;           // soft crown normals, translucency, no back-face flip
uniform bool cutout = true;
uniform float alpha_cut = 0.42;
uniform float sway = 0.16;            // metres of crown sway per metre of tree height... scaled by weight
uniform float flutter = 0.03;
uniform float wind_speed = 1.0;
uniform float translucency = 0.32;
uniform float ao_strength = 1.0;
uniform float roughness = 0.82;
uniform vec4 tint : source_color = vec4(1.0);
uniform bool impostor = false;        // crossed-quad far card: UV selects the species' atlas slot
uniform vec2 impostor_grid = vec2(8.0, 4.0);
varying float ao;
varying vec3 inst_tint;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float seed = fract(sin(dot(origin.xz, vec2(12.9898, 78.233))) * 43758.5453);
	float t = TIME * wind_speed;
	float gust = 0.6 + 0.4 * sin(t * 0.31 + origin.x * 0.012 + origin.z * 0.009);
	float bend = (sin(t * 1.05 + seed * 6.2831 + origin.x * 0.04) * 0.72 + sin(t * 2.2 + seed * 3.7) * 0.28) * gust;
	float scale_y = length(MODEL_MATRIX[1].xyz);
	float w = COLOR.r;
	vec2 dir = normalize(vec2(1.0, 0.42));
	float amount = w * sway * scale_y;
	VERTEX.xz += dir * bend * amount;
	VERTEX.y -= abs(bend) * w * amount * 0.12;
	float ph = COLOR.b * 6.2831 + seed * 12.0;
	VERTEX += NORMAL * sin(t * 6.3 + ph) * COLOR.g * flutter * (0.4 + w) * gust;
	ao = mix(1.0, COLOR.a, ao_strength);
	inst_tint = INSTANCE_CUSTOM.rgb * 2.0;
	if (impostor) {
		float slot = floor(INSTANCE_CUSTOM.a * 255.0 + 0.5);
		float col = 2.0 * mod(slot, 4.0);
		float row = floor(slot / 4.0);
		UV = vec2((col + UV.x * 2.0) / impostor_grid.x, (impostor_grid.y - 1.0 - row + UV.y) / impostor_grid.y);
		// Lit like the crown: mostly up, a little towards the viewer.
		NORMAL = normalize(vec3(0.0, 1.0, 0.0) + normalize(CAMERA_POSITION_WORLD - VERTEX) * 0.6);
	}
}

void fragment() {
	vec4 tex = texture(albedo_tex, UV);
	ALBEDO = tex.rgb * tint.rgb * inst_tint * ao;
	if (cutout) {
		ALPHA = tex.a;
		ALPHA_SCISSOR_THRESHOLD = alpha_cut;
		ALPHA_ANTIALIASING_EDGE = 0.25;
		ALPHA_TEXTURE_COORDINATE = UV * vec2(textureSize(albedo_tex, 0));
	}
	ROUGHNESS = roughness;
	SPECULAR = 0.25;
	if (use_normal_map) NORMAL_MAP = texture(normal_tex, UV).rgb;
	if (leaves) {
		BACKLIGHT = ALBEDO * translucency;
	} else if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
