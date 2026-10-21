shader_type spatial;
// Scrolling dot-matrix LED marquee. Every board in the city shares this material and one atlas
// texture (LedFont.build_atlas: one 9-texel row per message, one texel per LED, coloured per
// segment). Per board (instance uniforms): which atlas row, its pixel length, the board's LED
// columns, scroll speed and phase. The text steps one LED at a time like a real marquee.
render_mode cull_back;
uniform sampler2D atlas : filter_nearest, repeat_disable;
uniform float rows = 11.0;
uniform float energy = 3.2;
uniform float glyph_rows = 9.0;
instance uniform float row = 0.0;
instance uniform float text_len = 60.0;
instance uniform float cols = 55.0;
instance uniform float speed = 14.0;
instance uniform float phase = 0.0;

void fragment() {
	vec2 grid = vec2(cols, rows);
	vec2 g = UV * grid;
	vec2 cell = floor(g);
	vec2 f = fract(g) - 0.5;
	// Scroll position in whole LEDs: text enters at the right edge and leaves on the left.
	float span = text_len + cols;
	float p = mod(floor(TIME * speed + phase), span);
	float tx = cell.x + p - cols;
	float ty = cell.y - (rows - glyph_rows) * 0.5;
	vec4 led = vec4(0.0);
	if (tx >= 0.0 && tx < text_len && ty >= 0.0 && ty < glyph_rows) {
		led = texelFetch(atlas, ivec2(int(tx), int(row * glyph_rows + ty)), 0);
	}
	float d = length(f);
	float dot_shape = smoothstep(0.42, 0.26, d);
	float bloom = exp(-d * d * 9.0) * 0.35;
	// Far away the grid averages out instead of shimmering.
	float aa = clamp(length(fwidth(g)) * 1.6 - 0.6, 0.0, 1.0);
	float mask = mix(dot_shape + bloom, 0.62, aa);
	vec3 lit = led.rgb * led.a;
	vec3 off_dot = vec3(0.035, 0.032, 0.03) * mix(dot_shape, 0.5, aa);
	ALBEDO = off_dot + lit * 0.25 * mask;
	EMISSION = lit * energy * mask;
	ROUGHNESS = 0.22;
	SPECULAR = 0.55;
}
