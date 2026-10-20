shader_type spatial;
uniform sampler2D grass_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_rough : filter_linear_mipmap, repeat_enable;
varying vec3 p;
float h(vec2 v){return fract(sin(dot(v,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 v){vec2 i=floor(v),f=fract(v);f=f*f*(3.0-2.0*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
void vertex(){p=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
 float broad=n(p.xz*.16),patch=n(p.xz*1.6),fine=n(p.xz*70.0);
 vec3 grass=mix(vec3(.024,.049,.009),vec3(.09,.145,.028),broad*.6+patch*.4);
 vec3 soil=vec3(.14,.105,.060);
 vec2 uv=p.xz*.55;
 vec3 scanned=texture(grass_color,uv).rgb;
 ALBEDO=scanned*mix(.72,1.12,broad)*vec3(.84,1.0,.78);
 NORMAL_MAP=texture(grass_normal,uv).rgb;
 NORMAL_MAP_DEPTH=.45;
 ROUGHNESS=texture(grass_rough,uv).r;
}
