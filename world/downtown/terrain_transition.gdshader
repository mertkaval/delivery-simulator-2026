shader_type spatial;
render_mode cull_back;
varying vec3 world_position;
void vertex() {
	vec3 p=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
	float area=smoothstep(105.0,130.0,p.x)*(1.0-smoothstep(635.0,680.0,p.x))*smoothstep(-730.0,-704.0,p.z)*(1.0-smoothstep(-232.0,-205.0,p.z));
	VERTEX.y=mix(VERTEX.y,-0.25,area);
	world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
}
void fragment() {
	float variation=sin(world_position.x*.11)*sin(world_position.z*.09)*.025;
	ALBEDO=vec3(.15,.21,.08)+variation;
	ROUGHNESS=1.0;
}
