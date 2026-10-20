shader_type spatial;
uniform float night = 0.0;
uniform bool distant = false;
uniform vec4 wall_color : source_color = vec4(.34,.36,.35,1);
varying vec3 world_p;
varying vec3 world_n;
float hash(vec3 p){return fract(sin(dot(p,vec3(12.9898,78.233,37.719)))*43758.5453);}
void vertex(){world_p=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;world_n=normalize(MODEL_NORMAL_MATRIX*NORMAL);}
void fragment(){
 float horizontal=abs(world_n.x)>.5?world_p.z:world_p.x;
 vec2 cell=vec2(horizontal/4.0,(world_p.y-4.2)/3.2);
 vec2 room=fract(cell);
 float seed=hash(vec3(floor(cell),floor((world_p.x+world_p.z)/28.0)));
 // About a third of rooms are lit at night, with warm/cool/dim variation per room.
 float lit=step(.64,seed)*night;
 float tone=hash(vec3(floor(cell)*1.37,7.0));
 vec3 lamp=mix(vec3(1.0,.72,.42),vec3(.78,.86,1.0),step(.78,tone))*mix(.55,1.0,fract(tone*7.3));
 float curtains=step(.78,room.x)*step(.6,seed);
 float furnishing=step(.20,room.y)*step(room.y,.31)*step(.22,room.x)*step(room.x,.74);
 vec3 interior=mix(vec3(.035,.065,.073),vec3(.16,.125,.07),furnishing+curtains*.25);
 vec3 reflection=mix(vec3(.11,.20,.23),vec3(.30,.41,.45),clamp(room.y+.12*VIEW.y,0.,1.));
 vec3 glazing=mix(interior,reflection,.45+seed*.20);
 // Lit rooms: interior colour shows through, brighter at the ceiling, darker behind furniture.
 vec3 room_light=lamp*.32*mix(.6,1.0,smoothstep(.2,.9,room.y))*(1.0-furnishing*.55);
 glazing=mix(glazing,room_light,lit*.75);
 float window_mask=distant?step(.12,room.x)*step(room.x,.88)*step(.23,room.y)*step(room.y,.88):1.0;
 ALBEDO=mix(wall_color.rgb,glazing,window_mask);
 METALLIC=.28*window_mask;
 ROUGHNESS=mix(.86,.22+seed*.12,window_mask);
 EMISSION=lamp*lit*window_mask*mix(.22,.42,smoothstep(.2,.9,room.y))*(1.0-furnishing*.6)*(1.0-curtains*.5);
}
