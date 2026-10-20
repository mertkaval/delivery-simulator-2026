shader_type spatial;
uniform sampler2D asphalt : source_color,filter_linear_mipmap_anisotropic,repeat_enable;
uniform sampler2D normal_map : hint_normal,filter_linear_mipmap_anisotropic,repeat_enable;
varying vec3 p;
global uniform float wetness;
float hash(vec2 q){return fract(sin(dot(q,vec2(127.1,311.7)))*43758.5453);}
void vertex(){p=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
	vec2 uv=p.xz*.45;
	vec2 cell=floor(p.xz/9.0);
	vec2 local=fract(p.xz/9.0);
	float repair=step(.91,hash(cell))*step(.12,local.x)*step(local.x,.75)*step(.18,local.y)*step(local.y,.70);
	float damp=max(smoothstep(.7,.95,sin(p.x*.23)*sin(p.z*.13)),wetness*.85);
	ALBEDO=texture(asphalt,uv).rgb*vec3(.56,.62,.68)*mix(1.0,.62,repair)*mix(1.0,.7,damp);
	NORMAL_MAP=texture(normal_map,uv).rgb;
	NORMAL_MAP_DEPTH=.3;
	ROUGHNESS=mix(.91,.2,damp);
}
