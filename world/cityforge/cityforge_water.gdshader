shader_type spatial;
// CityForge water (sea, lake, river, fountains).
//  - colour: Beer-Lambert absorption over the light's path through the water (depth texture): the bed seen
//    through shallow water turns turquoise / green, deep water becomes its own lit, scattering body colour;
//  - refraction: the bed (screen texture) shifted by the ripples, never sampling things in front of the water;
//  - ripples: three scrolling, rotated layers of one seamless noise normal map (plus a long swell on the sea), the
//    finer ones faded with distance; rivers flow downhill (their mesh normals lean downstream: two-phase flow), the
//    lake is calm, the sea choppy with slow wind patches. Normal-only waves: the meshes are 4 m grids (lake,
//    river) or one quad (the sea), too coarse for vertex waves;
//  - fresnel sky reflection and sun glints come from the scene's radiance and lights (low roughness);
//  - soft shore edges and animated shore foam where the water is thin; lit, never emissive (dark at night).
// The sea is the outskirts quad at sea level - 6 cm; the city's own water cells in the sea follow its bed and are
// sunk out of sight (they would only double the surface).
render_mode blend_mix, depth_draw_always, cull_back, specular_schlick_ggx, world_vertex_coords;

uniform sampler2D ripple_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D ripple_noise : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float sea_level = 0.0;
// absorption per metre of light path (red goes first), and the turbidity that blurs the bed out of sight
uniform vec3 sea_absorb = vec3(0.45, 0.085, 0.075);
uniform vec3 lake_absorb = vec3(0.55, 0.14, 0.22);
uniform float sea_turbidity = 0.12;
uniform float lake_turbidity = 0.2;
// the lit colour deep water scatters back
uniform vec3 sea_scatter : source_color = vec3(0.035, 0.16, 0.19);
uniform vec3 lake_scatter : source_color = vec3(0.05, 0.15, 0.12);
uniform float ripple_strength = 1.0;
uniform float refraction = 0.03;
uniform float foam_amount = 1.0;
uniform vec3 foam_color : source_color = vec3(0.86, 0.89, 0.88);
varying vec3 wp;
varying vec3 wn;

void vertex() {
	wp = VERTEX;                 // world_vertex_coords
	wn = normalize(NORMAL);
	// the city's water cells in the sea lie on the sea bed, under the sea quad: sink them out of sight (a vertex
	// move keeps early depth testing, unlike a discard; the sea quad itself sits at sea_level - 6 cm)
	if (wp.y < sea_level - 0.07) VERTEX.y -= 200.0;
}

// slope (dh/du, dh/dv) of the ripple normal map at uv
vec2 slope_from(vec3 rgb) {
	vec3 n = rgb * 2.0 - 1.0;
	return n.xy / max(n.z, 0.25);
}

vec3 view_pos(mat4 inv_projection, vec2 uv, float z) {
	vec4 v = inv_projection * vec4(uv * 2.0 - 1.0, z, 1.0);
	return v.xyz / v.w;
}

void fragment() {
	float t = TIME;
	float dist = length(VERTEX);
	vec2 q = wp.xz;
	float sea = 1.0 - smoothstep(1.0, 1.6, wp.y - sea_level);      // the sea and the river's estuary reach

	// --- ripples -------------------------------------------------------------------------------------------
	float tilt = length(wn.xz);
	vec2 flow = wn.xz / max(tilt, 1e-5) * smoothstep(0.0006, 0.0013, tilt) * (1.0 - sea);   // downstream, rivers only
	float wind = texture(ripple_noise, q / 460.0 + t * vec2(0.0021, 0.0013)).r;           // slow gusty patches
	float chop = mix(0.62, mix(0.65, 1.3, smoothstep(0.3, 0.72, wind)), sea) * ripple_strength;
	// (layers that are not needed - no flow, too far, no shore - are skipped; explicit gradients keep the
	// branched samples filtered like the others)
	vec2 dqx = dFdx(q);
	vec2 dqy = dFdy(q);
	// sea swell: long, low crests across the wind (the sea only)
	vec2 sc0 = vec2(1.0 / 150.0, 1.0 / 70.0);
	vec2 s0 = slope_from(textureGrad(ripple_normal, q * sc0 + t * vec2(0.0016, 0.0042), dqx * sc0, dqy * sc0).xyz) * sea;
	// large layer, stretched across the wind
	vec2 sc1 = vec2(1.0 / 41.0, 1.0 / 23.0);
	vec2 s1 = slope_from(textureGrad(ripple_normal, q * sc1 + t * vec2(0.004, 0.011), dqx * sc1, dqy * sc1).xyz);
	// medium layer, rotated; on rivers it flows (two phases, crossfaded, reset while the other shows)
	mat2 r2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	vec2 gx2 = r2 * dqx / 12.0;
	vec2 gy2 = r2 * dqy / 12.0;
	float ph = fract(t / 5.0);
	vec2 drift = flow * 0.9 * 5.0;
	vec2 m0 = r2 * (q - drift * ph) / 12.0 + t * vec2(-0.017, 0.026);
	vec2 s2 = slope_from(textureGrad(ripple_normal, m0, gx2, gy2).xyz);
	if (dot(flow, flow) > 0.0) {
		vec2 m1 = r2 * (q - drift * fract(ph + 0.5)) / 12.0 + t * vec2(-0.017, 0.026) + vec2(0.37, 0.61) * length(flow);
		s2 = mix(s2, slope_from(textureGrad(ripple_normal, m1, gx2, gy2).xyz), abs(ph * 2.0 - 1.0));
	}
	// fine layer, rotated the other way, gone by ~70 m (further out it would only shimmer)
	mat2 r3 = mat2(vec2(0.47, -0.88), vec2(0.88, 0.47));
	float near = 1.0 - smoothstep(15.0, 70.0, dist);
	vec2 s3 = vec2(0.0);
	if (near > 0.0) {
		s3 = slope_from(textureGrad(ripple_normal, r3 * (q - flow * t * 0.6) / 3.3 + t * vec2(0.041, -0.032),
			r3 * dqx / 3.3, r3 * dqy / 3.3).xyz);
	}
	float far = mix(1.0, 0.45, smoothstep(120.0, 1400.0, dist));
	vec2 slope = (s0 * 0.45 + s1 * 0.45 + s2 * 0.3 + s3 * 0.2 * near) * chop * far;
	vec3 n_world = normalize(wn + vec3(-slope.x, 0.0, -slope.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);

	// --- the water under this pixel -------------------------------------------------------------------------
	vec3 bed = view_pos(INV_PROJECTION_MATRIX, SCREEN_UV, texture(depth_tex, SCREEN_UV).r);
	float depth_v = wp.y - (INV_VIEW_MATRIX * vec4(bed, 1.0)).y;          // vertical water depth (view independent)
	// refraction: ripples shift the bed, less in thin water and far away; never sample what is above the water
	vec2 ofs = (VIEW_MATRIX * vec4(slope.x, 0.0, slope.y, 0.0)).xy * refraction
		* smoothstep(0.0, 1.2, depth_v) / (1.0 + dist * 0.03);
	vec2 ruv = SCREEN_UV + vec2(ofs.x, -ofs.y);
	vec3 bed_r = view_pos(INV_PROJECTION_MATRIX, ruv, texture(depth_tex, ruv).r);
	if (bed_r.z > VERTEX.z - 0.05) { ruv = SCREEN_UV; bed_r = bed; }
	float path = max(distance(bed_r, VERTEX), 0.0);                        // light path through the water
	vec3 under = texture(screen_tex, ruv).rgb;

	// --- Beer-Lambert colour ----------------------------------------------------------------------------------
	vec3 absorb = mix(lake_absorb, sea_absorb, sea) + mix(lake_turbidity, sea_turbidity, sea);
	vec3 trans = exp(-absorb * path);
	float body = 1.0 - (trans.g + trans.b) * 0.5;                           // light lost: the water's own colour
	vec3 scatter = mix(lake_scatter, sea_scatter, sea);
	float fres = 0.02 + 0.98 * pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 5.0);

	// --- shore foam ----------------------------------------------------------------------------------------
	float shore = 1.0 - smoothstep(0.0, mix(0.35, 0.9, sea), depth_v);
	float foam = 0.0;
	if (shore * foam_amount > 0.0) {
		float fa = textureGrad(ripple_noise, q / 6.5 + t * vec2(0.031, -0.019), dqx / 6.5, dqy / 6.5).r;
		float fb = textureGrad(ripple_noise, r2 * q / 3.6 - t * vec2(0.047, 0.036), r2 * dqx / 3.6, r2 * dqy / 3.6).r;
		float rolling = 0.5 + 0.5 * sin(depth_v * 8.0 + t * 1.4 + fa * 6.0);  // lines running in towards the beach
		foam = shore * shore * smoothstep(0.38, 0.85, fa * 0.5 + fb * 0.35 + rolling * 0.3 * sea + shore * 0.2);
		foam *= smoothstep(0.0, 0.06, depth_v) * foam_amount * mix(0.45, 0.85, sea);
	}
	ALBEDO = mix(scatter * body * (1.0 - fres), foam_color, foam);
	EMISSION = under * trans * (1.0 - fres) * (1.0 - foam) * EXPOSURE;      // the refracted bed (already lit)
	ROUGHNESS = mix(mix(0.075, 0.14, smoothstep(40.0, 1200.0, dist)), 0.85, foam);
	SPECULAR = mix(0.4, 0.2, foam);
	METALLIC = 0.0;
	ALPHA = smoothstep(0.0, 0.1, depth_v);                                  // soft waterline
}
