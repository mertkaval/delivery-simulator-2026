shader_type spatial;
// Soft glow sprite in front of a lit signal lamp (MultiMesh of quads): camera-facing, additive,
// only seen from the front of the lamp (the instance's +Z), stronger at night.
// Per instance: COLOR = hue, INSTANCE_CUSTOM.r = lit.
render_mode blend_add, unshaded, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float strength = 0.6;
varying float amount;
varying vec3 hue;

void vertex() {
	vec3 centre = MODEL_MATRIX[3].xyz;
	vec3 to_cam = CAMERA_POSITION_WORLD - centre;
	float facing = dot(normalize(MODEL_MATRIX[2].xyz), normalize(to_cam));
	float size = length(MODEL_MATRIX[0].xyz);
	amount = INSTANCE_CUSTOM.r * smoothstep(0.05, 0.55, facing);
	hue = COLOR.rgb;
	// Billboard round the instance centre, nudged toward the camera so the lens never clips it.
	vec3 world = centre + normalize(to_cam) * 0.12 + (INV_VIEW_MATRIX[0].xyz * VERTEX.x + INV_VIEW_MATRIX[1].xyz * VERTEX.y) * size;
	POSITION = PROJECTION_MATRIX * VIEW_MATRIX * vec4(world, 1.0);
}

void fragment() {
	float r = length(UV - 0.5) * 2.0;
	float halo = exp(-r * r * 5.0) * (1.0 - smoothstep(0.75, 1.0, r));
	ALBEDO = hue * halo * amount * strength;
}
