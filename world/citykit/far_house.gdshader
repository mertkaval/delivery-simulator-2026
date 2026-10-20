shader_type spatial;
// Distant-house massing: instance colour is the wall paint; windows are drawn procedurally
// on a 3 m bay grid at both storeys and light up at night. Roof surfaces use their own material.
uniform float night = 0.0;
varying vec3 wp;
varying vec3 wn;

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float along = abs(wn.x) > 0.5 ? wp.z : wp.x;
	float bay = fract(along / 3.0);
	float storey = (wp.y > 1.5 && wp.y < 2.9) || (wp.y > 4.3 && wp.y < 5.6) ? 1.0 : 0.0;
	float win = step(0.27, bay) * step(bay, 0.73) * storey * step(abs(wn.y), 0.5);
	float lit = step(0.62, hash(floor(vec2(along / 3.0, wp.y / 2.8)) + floor(wp.xz / 40.0))) * night;
	vec3 paint = COLOR.rgb;
	ALBEDO = mix(paint * 0.92, vec3(0.07, 0.1, 0.12), win);
	ROUGHNESS = mix(0.82, 0.18, win);
	EMISSION = vec3(1.0, 0.74, 0.45) * 0.55 * lit * win;
}
