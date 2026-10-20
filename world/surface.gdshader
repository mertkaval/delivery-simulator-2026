shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
uniform vec4 tint : source_color = vec4(1.0);
uniform int surface_kind = 0;
varying vec3 world_position;
varying vec3 world_normal;
global uniform float wetness;
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1,311.7,74.7))) * 43758.5453); }
float noise(vec3 p) {
 vec3 i=floor(p); vec3 f=fract(p); f=f*f*(3.0-2.0*f);
 return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
void vertex() {
 world_position = (MODEL_MATRIX * vec4(VERTEX,1.0)).xyz;
 world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
 vec3 p=world_position;
 float fine=noise(p*65.0);
 float broad=noise(p*1.7);
 float value=0.94+0.08*fine;
 ROUGHNESS=0.85;
 METALLIC=0.0;
 if(surface_kind==1) { // Asphalt: subtle aggregate and broad patches.
  value=0.66+0.22*fine+0.10*broad; ROUGHNESS=0.96;
 } else if(surface_kind==2) { // Concrete pores.
  value=0.79+0.12*fine+0.07*broad; ROUGHNESS=0.91;
 } else if(surface_kind==3) { // Painted horizontal lap siding, 18cm boards.
  float board=p.y/0.18;
  float edge=min(fract(board),1.0-fract(board));
  float seam=smoothstep(0.012,0.012+max(fwidth(board),0.035),edge);
  value=(0.88+0.06*noise(p*vec3(1.0,35.0,1.0)))*mix(0.82,1.0,seam);
  ROUGHNESS=0.66;
 } else if(surface_kind==4) { // Timber grain.
  value=0.65+0.3*noise(p*vec3(4.0,70.0,4.0)); ROUGHNESS=0.76;
 } else if(surface_kind==5) { // Masonry, staggered courses.
  vec2 uv=abs(world_normal.z)>0.5?p.xy:p.zy;
  float row=floor(uv.y/0.12);
  vec2 cell=fract(vec2(uv.x/0.3+mod(row,2.0)*0.5,uv.y/0.12));
  float brick=smoothstep(0.025,0.06,cell.x)*smoothstep(0.03,0.08,cell.y);
  value=mix(0.5,0.8+0.12*fine,brick); ROUGHNESS=0.92;
 } else if(surface_kind==6) { // Dark roof shingles.
  float row=fract(p.z*3.5);
  value=(0.7+0.18*noise(floor(p*vec3(4,1,3.5))))*mix(0.6,1.0,smoothstep(0.02,0.08,row)); ROUGHNESS=0.94;
 } else if(surface_kind==7) { // Tinted glass.
  value=0.72+0.2*smoothstep(-0.5,1.0,world_normal.y); ROUGHNESS=0.14; METALLIC=0.35;
 } else if(surface_kind==8) { value=0.9; METALLIC=0.8; ROUGHNESS=0.35;
 } else if(surface_kind==9) { value=0.62+0.24*broad+0.12*fine; ROUGHNESS=1.0;
 }
 // Rain: surfaces darken, and upward-facing paving turns glossy (grass only darkens).
 float up=smoothstep(0.6,0.95,world_normal.y);
 float w=(surface_kind==7||surface_kind==8)?0.0:wetness;
 value*=mix(1.0,0.66,w*mix(0.45,1.0,up));
 ROUGHNESS=mix(ROUGHNESS,0.2,w*up*(surface_kind==9?0.25:1.0));
 ALBEDO=tint.rgb*value;
}
