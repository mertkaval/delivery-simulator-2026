shader_type spatial;
// Townspeople outfit recolouring (LivingAssets.humanoid): the character's own atlas, with hue /
// saturation / value shifted only where the outfit mask marks clothing (tools/build_outfit_masks.py:
// R = top, G = bottom). Skin, hair, face, hands and shoes keep their scanned colours. One shared
// material per character surface; every person sets their own colours as instance uniforms.
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool use_normal = false;
uniform sampler2D mask_texture : hint_default_black, filter_linear_mipmap;
// >= 0: the whole surface is one garment (top, bottom) instead of reading the mask.
uniform vec2 mask_fixed = vec2(-1.0, -1.0);
uniform float roughness_value : hint_range(0.0, 1.0) = 0.9;
// x: hue shift (turns; absolute hue for grey / black / white cloth), y: saturation change
// (+ towards full colour, - towards grey),
// z: value multiplier, w: strength (0 keeps the original garment).
instance uniform vec4 outfit_top = vec4(0.0, 0.0, 1.0, 0.0);
instance uniform vec4 outfit_bottom = vec4(0.0, 0.0, 1.0, 0.0);

vec3 rgb2hsv(vec3 c) {
	vec4 k = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, k.wz), vec4(c.gb, k.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-6)), d / (q.x + 1e-6), q.x);
}

vec3 hsv2rgb(vec3 c) {
	vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
	return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

vec3 to_srgb(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c)); }
vec3 to_linear(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)); }

vec3 recolour(vec3 linear_rgb, vec4 o) {
	vec3 hsv = rgb2hsv(to_srgb(linear_rgb));
	float grey = 1.0 - smoothstep(0.06, 0.22, hsv.y);
	float value = clamp(hsv.z * o.z, 0.0, 1.0);
	// Positive y saturates towards full colour, negative y fades towards grey.
	float sat = o.y >= 0.0 ? hsv.y + o.y * (1.0 - hsv.y) : hsv.y * (1.0 + o.y);
	vec3 shifted = hsv2rgb(vec3(fract(hsv.x + o.x), clamp(sat, 0.0, 1.0), value));
	vec3 dyed = hsv2rgb(vec3(o.x, clamp(hsv.y + max(o.y, 0.0) * 0.6, 0.0, 1.0), value));
	return to_linear(mix(shifted, dyed, grey));
}

void fragment() {
	vec3 c = texture(albedo_texture, UV).rgb;
	vec2 m = mask_fixed.x >= 0.0 ? mask_fixed : texture(mask_texture, UV).rg;
	c = mix(c, recolour(c, outfit_top), m.r * outfit_top.w);
	c = mix(c, recolour(c, outfit_bottom), m.g * outfit_bottom.w);
	ALBEDO = c;
	ROUGHNESS = roughness_value;
	if (use_normal) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
	}
}
