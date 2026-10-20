shader_type sky;
uniform float daylight = 1.0;
uniform float clock_hours = 11.5;
uniform vec3 sun_direction = vec3(0.0,0.8,0.4);
uniform sampler2D cloud_noise : filter_linear_mipmap, repeat_enable;
uniform float overcast = 0.0; // WeatherSystem: 0 clear .. 1 heavy rain cloud
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
 vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
 return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);
}
void sky() {
 float elevation=max(EYEDIR.y,0.0);
 vec3 horizon=mix(vec3(.025,.04,.075),vec3(.56,.67,.73),daylight);
 vec3 zenith=mix(vec3(.003,.008,.023),vec3(.12,.29,.53),daylight);
 vec3 color=mix(horizon,zenith,pow(elevation,.45));
 float dusk=(1.0-abs(daylight*2.0-1.0))*pow(1.0-elevation,5.0);
 color=mix(color,vec3(.7,.28,.12),dusk*.45);
 float sun=dot(EYEDIR,normalize(sun_direction));
 color+=vec3(1.0,.77,.43)*pow(max(sun,0.0),90.0)*daylight*.3;
 color+=vec3(4.0,3.4,2.3)*smoothstep(.99990,.99996,sun)*daylight*(1.0-overcast);
 if (!AT_CUBEMAP_PASS && EYEDIR.y>.01) {
  vec2 p=EYEDIR.xz/(EYEDIR.y+.15)*2.2+vec2(clock_hours*.3,clock_hours*.07);
  float n=texture(cloud_noise,p*.065).r;
  float cloud=smoothstep(.49-overcast*.45,.69-overcast*.3,n)*smoothstep(.01,.12,elevation);
  vec3 cloud_color=mix(vec3(.055,.07,.11),mix(vec3(.55,.60,.64),vec3(.98,.97,.91),smoothstep(.5,.72,n)*(1.0-overcast*.8)),daylight);
  cloud_color*=1.0-overcast*.35;
  color=mix(color,cloud_color,cloud*.94);
  float star=step(.9991,hash(floor(EYEDIR.xz/(EYEDIR.y+.3)*650.0)));
  color+=vec3(.6,.7,.9)*star*(1.0-daylight)*(1.0-cloud)*smoothstep(.1,.4,elevation);
 }
 // Rain cloud: a grey lid over the whole sky, the sun disc hidden.
 color=mix(color,mix(vec3(.02,.025,.035),vec3(.42,.46,.5),daylight),overcast*.85*smoothstep(-.05,.2,EYEDIR.y));
 COLOR=color;
}
