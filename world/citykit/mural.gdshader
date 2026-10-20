shader_type spatial;
// Street-art mural painted on brick: the artwork follows the mortar relief (shared brick
// normal map tiled at the wall's real scale), paint is matte and slightly worn at the edges.
uniform sampler2D art : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D brick_normal : hint_normal, filter_linear_mipmap;
uniform vec2 size = vec2(8.0, 5.0);
uniform float tile = 1.8;

float hash(vec2 p) { return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453); }

void fragment() {
	vec3 paint = texture(art, UV).rgb;
	// Weathering: speckled chips where the brick shows through, denser towards the edges.
	vec2 cell = floor(UV * size * 40.0);
	float edge = min(min(UV.x, 1.0 - UV.x) * size.x, min(UV.y, 1.0 - UV.y) * size.y);
	float chip = step(0.985 - 0.12 * (1.0 - smoothstep(0.0, 0.35, edge)), hash(cell));
	ALBEDO = mix(paint, vec3(0.42, 0.22, 0.17), chip * 0.7);
	NORMAL_MAP = texture(brick_normal, UV * size / tile).rgb;
	NORMAL_MAP_DEPTH = 0.8;
	ROUGHNESS = 0.88;
	SPECULAR = 0.3;
}
