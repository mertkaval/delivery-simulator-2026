shader_type spatial;
render_mode cull_disabled, diffuse_burley;
uniform bool grass = false;
varying vec3 world_pos;
varying float leaf_height;
void vertex() {
 world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 leaf_height=VERTEX.y;
 float wind=sin(TIME*1.6+world_pos.x*.48+world_pos.z*.31)+.4*sin(TIME*2.8+world_pos.z);
 float bend=grass?pow(clamp(VERTEX.y/.3,0.0,1.0),2.0)*.035:clamp(VERTEX.y/9.0,0.0,1.0)*.075;
 VERTEX.x+=wind*bend;
 VERTEX.z+=cos(TIME+world_pos.x*.4)*bend*.45;
}
void fragment() {
 float variation=fract(sin(dot(floor(world_pos.xz*4.0),vec2(127.1,311.7)))*43758.5453);
 vec3 low=grass?vec3(.025,.07,.008):vec3(.035,.105,.012);
 vec3 high=grass?vec3(.10,.20,.025):vec3(.14,.27,.037);
 float t=grass?clamp(leaf_height/.25,0.0,1.0):variation;
 ALBEDO=mix(low,high,t)*mix(.85,1.14,variation);
 ROUGHNESS=.92;
 BACKLIGHT=ALBEDO*.35;
 if(!FRONT_FACING) NORMAL=-NORMAL;
}
