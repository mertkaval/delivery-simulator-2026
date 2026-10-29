shader_type spatial;
render_mode diffuse_burley;
// Street-block ground (tools/roads/mrs/ground.py): the same blend as the Blender material.
//   UV  = world metres (x, y); tiles repeat every 4 m      UV2 = block mask coordinates (0..1)
//   mask.r = soil / beds / tree bases (smoothstep 0.35..0.65: defined bed edges)
//   mask.g = trampled wear at access points and path edges (smoothstep 0.15..0.85)
//   mask.b = broad lush / dry variation (brightness 0.86..1.08, slight hue shift to yellow when dry)
uniform sampler2D mask_tex : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D grass_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D worn_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D soil_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D worn_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D worn_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float tile_scale = 0.25;
varying vec2 mask_uv;

void vertex() {
	mask_uv = UV2;
}

vec3 hue_shift(vec3 c, float h) {
	// small rotation around the grey axis (h in turns)
	float a = h * 6.2831853;
	vec3 k = vec3(0.57735);
	return c * cos(a) + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cos(a));
}

void fragment() {
	vec4 m = texture(mask_tex, mask_uv);
	float wear = smoothstep(0.15, 0.85, m.g);
	float soil = smoothstep(0.35, 0.65, m.r);
	vec2 uv = UV * tile_scale;
	vec3 col = mix(texture(grass_albedo, uv).rgb, texture(worn_albedo, uv).rgb, wear);
	col = mix(col, texture(soil_albedo, uv).rgb, soil);
	float lush = mix(0.86, 1.08, m.b);
	col = hue_shift(col * lush, mix(0.015, -0.01, m.b));
	float r = mix(texture(grass_rough, uv).r, texture(worn_rough, uv).r, wear);
	r = mix(r, texture(soil_rough, uv).r, soil);
	vec3 n = mix(texture(grass_normal, uv).rgb, texture(worn_normal, uv).rgb, wear);
	n = mix(n, texture(soil_normal, uv).rgb, soil);
	ALBEDO = clamp(col, 0.0, 1.0);
	ROUGHNESS = r;
	NORMAL_MAP = n;
	SPECULAR = 0.35;
}
