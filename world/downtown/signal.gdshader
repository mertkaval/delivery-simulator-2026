shader_type spatial;
uniform float phase=0;
uniform int lens=0;
uniform vec4 color : source_color=vec4(1,0,0,1);
varying float north_south;
void vertex(){north_south=step(.5,abs((MODEL_MATRIX*vec4(0,0,1,0)).z));}
void fragment(){
	bool ns=north_south>.5;
	bool green=ns ? phase<12.0 : (phase>=16.0 && phase<28.0);
	bool amber=ns ? (phase>=12.0 && phase<14.0) : (phase>=28.0 && phase<30.0);
	bool active=lens==0 ? (!green && !amber) : (lens==1 ? amber : green);
	ALBEDO=color.rgb*(active?1.0:.13);
	EMISSION=color.rgb*(active?2.0:0.0);
	ROUGHNESS=.3;
}
