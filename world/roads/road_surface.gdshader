shader_type spatial;
// Street asphalt for the Blender road kit. Local X is the lateral offset from the
// road centreline, so lane-dependent wear lines up with the authored cross-section.
uniform sampler2D asphalt : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D asphalt_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D asphalt_rough : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float lane_centre = 1.95; // |x| of each traffic lane; negative disables lane wear
uniform float wheel_offset = 0.78; // half track width of a car
uniform float edge = 5.55; // asphalt edge (gutter line)
uniform float texture_scale = 0.32;
varying vec3 world_pos;
varying float lateral;
global uniform float wetness;
global uniform float rain_intensity;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	lateral = VERTEX.x;
}

void fragment() {
	vec2 uv = world_pos.xz * texture_scale;
	vec3 base = texture(asphalt, uv).rgb * vec3(0.52, 0.55, 0.58);
	float rough = texture(asphalt_rough, uv).r;
	// Broad tonal drift between resurfacing batches.
	base *= mix(0.86, 1.08, noise(world_pos.xz * 0.045));
	float polish = 0.0;
	float oil = 0.0;
	float seam = 0.0;
	float grime = 0.0;
	if (lane_centre > 0.0) {
		float d = abs(abs(lateral) - lane_centre);
		polish = smoothstep(0.42, 0.12, abs(d - wheel_offset)) * mix(0.6, 1.0, noise(world_pos.xz * 0.6));
		oil = smoothstep(0.38, 0.05, d) * smoothstep(0.35, 0.75, noise(world_pos.xz * vec2(1.3, 1.3)));
		// Longitudinal paving joint at the crown, sealed with tar.
		seam = smoothstep(0.05, 0.0, abs(lateral + (noise(world_pos.xz * 0.9) - 0.5) * 0.05));
		grime = smoothstep(edge - 0.7, edge, abs(lateral));
	}
	// Meandering sealed cracks, clustered in older areas.
	float crack_line = smoothstep(0.012, 0.0, abs(noise(world_pos.xz * 0.21) - 0.5));
	float cracks = crack_line * smoothstep(0.62, 0.75, noise(world_pos.xz * 0.025 + 11.0)) * 0.7;
	// Rectangular utility-cut patches on a 9 m grid.
	vec2 cell = floor(world_pos.xz / 9.0);
	vec2 local = fract(world_pos.xz / 9.0);
	float repair = step(0.93, hash(cell)) * step(0.15, local.x) * step(local.x, 0.62) * step(0.2, local.y) * step(local.y, 0.55);
	vec3 colour = base;
	colour *= mix(1.0, 0.8, polish);
	colour *= mix(1.0, 0.7, oil);
	colour = mix(colour, vec3(0.025), max(seam, cracks) * 0.85);
	colour *= mix(1.0, 1.25, repair);
	colour = mix(colour, colour * vec3(0.78, 0.74, 0.68), grime * 0.6);
	// Rain (WeatherSystem): darker, glossy asphalt; water pools in the gutters, wheel ruts
	// and low patches, where raindrops ring the surface.
	float low = smoothstep(0.58, 0.82, noise(world_pos.xz * 0.16 + 3.0));
	float puddle = clamp(low + grime * 0.7 + polish * 0.35 + repair * 0.4, 0.0, 1.0) * smoothstep(0.35, 0.95, wetness);
	colour *= mix(1.0, 0.58, wetness);
	colour *= mix(1.0, 0.72, puddle);
	ALBEDO = colour;
	// Tar sealant is only slightly glossier than the surrounding aggregate.
	float dry_rough = clamp(rough * 0.95 - polish * 0.18 - oil * 0.25 - max(seam, cracks) * 0.1, 0.45, 1.0);
	ROUGHNESS = mix(mix(dry_rough, 0.24, wetness), 0.03, puddle);
	SPECULAR = mix(0.5, 0.7, wetness);
	vec3 nm = texture(asphalt_normal, uv).rgb;
	// Expanding ripple rings, one per 0.5 m cell, restarting at random times.
	vec2 rc = floor(world_pos.xz * 2.0);
	vec2 rp = fract(world_pos.xz * 2.0) - (vec2(hash(rc), hash(rc + 7.1)) * 0.6 + 0.2);
	float age = fract(TIME * 1.4 + hash(rc + 3.3));
	float ring = sin((length(rp) - age * 0.45) * 60.0) * smoothstep(0.08, 0.0, abs(length(rp) - age * 0.45)) * (1.0 - age);
	vec2 ripple = normalize(rp + 1e-4) * ring * 0.18 * rain_intensity * smoothstep(0.45, 0.9, puddle);
	NORMAL_MAP = mix(nm, vec3(0.5, 0.5, 1.0), puddle * 0.85) + vec3(ripple, 0.0);
	NORMAL_MAP_DEPTH = mix(0.45, 0.15, polish);
}
