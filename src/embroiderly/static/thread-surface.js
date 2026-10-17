/* GPU counterpart of thread_surface.py. Only supplied exported-readback segments
 * deposit thread. Lighting does not edit, reroute or regenerate a stitch. */
(() => {
'use strict';
const vertex=`#version 300 es
precision highp float;
layout(location=0) in vec4 ends;
layout(location=1) in vec4 inkSeed;
uniform vec2 size, offset;
uniform float ppm, strand;
out vec2 point;
flat out vec4 line, ink;
void main(){
 vec2 corners[6]=vec2[6](vec2(0,0),vec2(1,0),vec2(0,1),vec2(0,1),vec2(1,0),vec2(1,1));
 vec2 lo=min(ends.xy,ends.zw)-strand*.55,hi=max(ends.xy,ends.zw)+strand*.55;
 point=mix(lo,hi,corners[gl_VertexID]);line=ends;ink=inkSeed;
 vec2 screen=point*ppm+offset;gl_Position=vec4(screen.x/size.x*2.-1.,1.-screen.y/size.y*2.,0,1);
}`;
const ridge=`
 vec2 delta=line.zw-line.xy;float len=length(delta);vec2 t=delta/len;
 vec2 relative=point-line.xy;float along=dot(relative,t),across=dot(relative,vec2(-t.y,t.x));
 float taper=clamp(min(along,len-along)/max(strand*.75,.001),0.,1.);taper=taper*taper*(3.-2.*taper);
 across-=(ink.a-.5)*strand*.035*taper;
 float radius=strand*.5;float h=radius*sqrt(max(0.,1.-pow(across/radius,2.)))*taper;
 if(abs(across)>=radius||along<=0.||along>=len||h<=.00001)discard;
`;
const heightFragment=`#version 300 es
precision highp float;
in vec2 point;flat in vec4 line,ink;uniform float strand;out vec4 result;
void main(){${ridge}result=vec4(h,0,0,1);}`;
const materialFragment=`#version 300 es
precision highp float;
in vec2 point;flat in vec4 line,ink;uniform float strand;
layout(location=0) out vec4 direction;layout(location=1) out vec4 colour;
void main(){${ridge}direction=vec4(t,cos(6.28318530718*(along/.55+across/max(strand,.001)*.7+ink.a)),ink.a);colour=vec4(ink.rgb,1);}`;
const screenVertex=`#version 300 es
precision highp float;
void main(){vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}`;
const litFragment=`#version 300 es
precision highp float;
uniform sampler2D heights,directions,colours,cloth,palette;
uniform float paletteCount;
uniform vec2 size,offset;uniform float ppm;uniform vec3 light,fabric;
uniform int weaveKind;uniform bool neutral;
out vec4 result;
const float TAU=6.28318530718;
vec3 toLab(vec3 c){
 vec3 linear=mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));
 vec3 xyz=mat3(.4124564,.2126729,.0193339,.3575761,.7151522,.1191920,.1804375,.0721750,.9503041)*linear/vec3(.95047,1,1.08883);
 vec3 f=mix(7.787*xyz+16./116.,pow(max(xyz,vec3(0)),vec3(1./3.)),step(vec3(.008856),xyz));
 return vec3(116.*f.y-16.,500.*(f.x-f.y),200.*(f.y-f.z));
}
vec3 toRGB(vec3 lab){
 float fy=(lab.x+16.)/116.;vec3 f=vec3(fy+lab.y/500.,fy,fy-lab.z/200.);vec3 cube=f*f*f;
 vec3 xyz=mix((f-16./116.)/7.787,cube,step(vec3(.008856),cube))*vec3(.95047,1,1.08883);
 vec3 c=mat3(3.2404542,-.9692660,.0556434,-1.5371385,1.8760108,-.2040259,-.4985314,.0415560,1.0572252)*xyz;
 return clamp(mix(c*12.92,1.055*pow(max(c,vec3(0)),vec3(1./2.4))-.055,step(vec3(.0031308),c)),0.,1.);
}
float weave(vec2 p){
 if(weaveKind==1)return .016*cos(TAU*p.x/.7)*cos(TAU*p.y/.7);
 if(weaveKind==2)return .014*sin(TAU*p.x/.65+.7*sin(TAU*p.y/.9))+.006*cos(TAU*p.y/.9);
 if(weaveKind==3)return .006*(sin(TAU*(p.x*4.+p.y*3.))+cos(TAU*(p.x*7.-p.y*5.))+sin(TAU*(p.x*11.+p.y*9.)));
 float pitch=weaveKind==4?.45:.6;
 return .012*sin(TAU*(p.x+p.y)/pitch)+.006*cos(TAU*p.x/.35)*cos(TAU*p.y/.35);
}
float heightAt(vec2 uv){return texture(heights,uv).r;}
void main(){
 vec2 uv=gl_FragCoord.xy/size,pixel=1./size;
 float h=heightAt(uv),left=heightAt(uv-vec2(pixel.x,0)),right=heightAt(uv+vec2(pixel.x,0));
 float up=heightAt(uv+vec2(0,pixel.y)),down=heightAt(uv-vec2(0,pixel.y));
 vec3 normal=normalize(vec3(-(right-left)*ppm*.5,-(down-up)*ppm*.5,1));
 vec4 d=texture(directions,uv);vec3 halfLight=normalize(light+vec3(0,0,1));
 float shine=pow(max(0.,1.-pow(dot(d.xy,halfLight.xy),2.)),6.);
 float ao=clamp(((left+right+up+down)*.25-h)*2.,0.,.3);
 if(h>0.){
  float delta=12.*(dot(normal,light)-light.z*.78)+14.*(shine-.6)+2.*d.z+.9*(d.w-.5)-15.*ao;
  if(neutral)delta=clamp(delta,-1.25,1.25);
  float index=texture(colours,uv).r;
  result=vec4(texture(palette,vec2((clamp(delta,-32.,32.)+32.)/64.*255./256.+.5/256.,(index+.5)/paletteCount)).rgb,1);return;
 }
 vec2 p=(vec2(gl_FragCoord.x,size.y-gl_FragCoord.y)-offset)/ppm;
 vec4 clothData=texture(cloth,uv);
 float diffuse=dot(clothData.xyz,light),shadow=0.;
 float distance[3]=float[3](.18,.4,.8);float weights[3]=float[3](.5,.3,.2);
 for(int i=0;i<3;i++){vec2 shift=vec2(light.x,-light.y)*distance[i]*ppm/size;shadow+=weights[i]*clamp((heightAt(uv+shift)-h-distance[i]*light.z)/.15,0.,1.);}
 result=vec4(clamp(fabric*(1.+.16*(diffuse-light.z)+.035*clothData.w/.018-.23*shadow-.2*ao),0.,1.),1);
}`;
const clothFragment=`#version 300 es
precision highp float;
uniform vec2 size,offset;uniform float ppm;uniform int weaveKind;
const float TAU=6.28318530718;
${litFragment.slice(litFragment.indexOf('float weave('),litFragment.indexOf('float heightAt('))}
out vec4 result;
void main(){
 vec2 p=(vec2(gl_FragCoord.x,size.y-gl_FragCoord.y)-offset)/ppm;
 float wx=-(weave(p+vec2(.02,0))-weave(p-vec2(.02,0)))/.04;
 float wy=-(weave(p+vec2(0,.02))-weave(p-vec2(0,.02)))/.04;
 result=vec4(normalize(vec3(wx,wy,1)),weave(p));
}`;
function colourRamp(colour){
 const c=hex(colour).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
 const xyz=[(.4124564*c[0]+.3575761*c[1]+.1804375*c[2])/.95047,.2126729*c[0]+.7151522*c[1]+.0721750*c[2],(.0193339*c[0]+.1191920*c[1]+.9503041*c[2])/1.08883];
 const f=xyz.map(v=>v>.008856?Math.cbrt(v):7.787*v+16/116),lab=[116*f[1]-16,500*(f[0]-f[1]),200*(f[1]-f[2])],out=[];
 for(let i=0;i<256;i++){
  const L=Math.max(0,Math.min(100,lab[0]+i*64/255-32)),fy=(L+16)/116;
  const q=[fy+lab[1]/500,fy,fy-lab[2]/200].map(v=>v**3>.008856?v**3:(v-16/116)/7.787);
  const [x,y,z]=[q[0]*.95047,q[1],q[2]*1.08883];
  out.push(...[3.2404542*x-1.5371385*y-.4985314*z,-.9692660*x+1.8760108*y+.0415560*z,.0556434*x-.2040259*y+1.0572252*z].map(v=>Math.round(255*Math.max(0,Math.min(1,v<=.0031308?12.92*v:1.055*Math.max(0,v)**(1/2.4)-.055)))) ,255);
 }
 return out;
}
const hex=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16)/255);
function program(gl,v,f){
 const p=gl.createProgram();
 for(const [type,code] of [[gl.VERTEX_SHADER,v],[gl.FRAGMENT_SHADER,f]]){
  const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(s);gl.deleteShader(s);throw Error(message)}
  gl.attachShader(p,s);gl.deleteShader(s);
 }
 gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;
}
class ThreadSurface {
 constructor(){
  this.canvas=document.createElement('canvas');
  const gl=this.gl=this.canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
  if(!gl||!gl.getExtension('EXT_color_buffer_float'))throw Error('WebGL2 floating-point surfaces unavailable');
  this.heightProgram=program(gl,vertex,heightFragment);this.materialProgram=program(gl,vertex,materialFragment);this.lightProgram=program(gl,screenVertex,litFragment);this.clothProgram=program(gl,screenVertex,clothFragment);this.paletteTexture=gl.createTexture();
  this.buffer=gl.createBuffer();this.vao=gl.createVertexArray();this.screenVao=gl.createVertexArray();this.textures=[];this.fbos=[];this.cursor=0;this.key='';this.plan=null;this.builds=0;
  this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.lost=true});
 }
 reset(){this.plan=null;this.key='';this.cursor=0;this.shadeKey=''}
 dispose(){const gl=this.gl;this.textures.forEach(t=>gl.deleteTexture(t));this.fbos.forEach(f=>gl.deleteFramebuffer(f));[this.heightProgram,this.materialProgram,this.lightProgram,this.clothProgram].forEach(p=>gl.deleteProgram(p));gl.deleteTexture(this.paletteTexture);gl.deleteBuffer(this.buffer);gl.deleteVertexArray(this.vao);gl.deleteVertexArray(this.screenVao)}
 allocate(w,h){
  const gl=this.gl;
  if(w*h>8_000_000||w>gl.getParameter(gl.MAX_TEXTURE_SIZE)||h>gl.getParameter(gl.MAX_TEXTURE_SIZE))throw Error('Viewport exceeds the realistic preview memory limit');
  this.textures.forEach(t=>gl.deleteTexture(t));this.fbos.forEach(f=>gl.deleteFramebuffer(f));this.textures=[];this.fbos=[];
  this.canvas.width=w/2;this.canvas.height=h/2;this.bufferWidth=w;this.bufferHeight=h;this.fabricKey='';
  for(const format of [gl.RGBA16F,gl.RGBA16F,gl.RGBA16F,gl.RGBA16F,gl.RGBA8]){
   const t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.texStorage2D(gl.TEXTURE_2D,1,format,w,h);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);this.textures.push(t);
  }
  for(const indices of [[0],[1,2],[3],[4]]){
   const f=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,f);
   indices.forEach((t,i)=>gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0+i,gl.TEXTURE_2D,this.textures[t],0));gl.drawBuffers(indices.map((_,i)=>gl.COLOR_ATTACHMENT0+i));
   if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Thread surface framebuffer unavailable');this.fbos.push(f);
  }
 }
 geometry(plan,map){
  const data=[],ends=[];let prior={x:0,y:0};
  const colours=[...new Set(plan.colors.map(c=>map?.[c]||c))];this.paletteCount=colours.length;
  if(colours.length>256)throw Error('More than 256 preview colours');
  const gl=this.gl;gl.bindTexture(gl.TEXTURE_2D,this.paletteTexture);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,256,colours.length,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(colours.flatMap(colourRamp)));
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  for(let i=0;i<plan.steps.length;i++){
   const s=plan.steps[i];
   if(s.t==='stitch'&&(s.x!==prior.x||s.y!==prior.y)){
    data.push(prior.x,prior.y,s.x,s.y,colours.indexOf(map?.[s.color]||s.color),0,0,((i*37+17)%997)/997);ends.push(i+1);
   }prior=s;
  }
  this.ends=ends;this.data=new Float32Array(data);this.gl.bindBuffer(this.gl.ARRAY_BUFFER,this.buffer);this.gl.bufferData(this.gl.ARRAY_BUFFER,this.data,this.gl.STATIC_DRAW);
 }
 uniforms(p,w,h,ppm,offset,strand){
  const gl=this.gl;gl.useProgram(p);gl.uniform2f(gl.getUniformLocation(p,'size'),w,h);gl.uniform2f(gl.getUniformLocation(p,'offset'),...offset);gl.uniform1f(gl.getUniformLocation(p,'ppm'),ppm);gl.uniform1f(gl.getUniformLocation(p,'strand'),strand);
 }
 paint(context,plan,cursor,view){
  if(this.lost||this.gl.isContextLost())throw Error('Graphics context lost');
  const started=performance.now(),gl=this.gl,ss=2,w=view.width*ss,h=view.height*ss,ppm=view.factor*view.s*ss;
  const offset=[(view.x+plan.origin_mm[0]*view.factor*view.s)*ss,(view.y+plan.origin_mm[1]*view.factor*view.s)*ss];
  const colours=JSON.stringify(view.colourMap||{}),key=JSON.stringify([w,h,ppm,offset,view.threadWidth]);
  if(this.plan!==plan||this.colours!==colours){this.geometry(plan,view.colourMap);this.plan=plan;this.colours=colours;this.key='';this.shadeKey=''}
  if(!this.textures.length||this.bufferWidth!==w||this.bufferHeight!==h){this.allocate(w,h);this.key='';this.shadeKey=''}
  let lo=0,hi=this.ends.length;while(lo<hi){const mid=(lo+hi)>>>1;if(this.ends[mid]<=cursor)lo=mid+1;else hi=mid}const target=lo;
  const shadeKey=JSON.stringify([key,target,colours,view.texture,view.lightAngle,view.neutralLight,view.fabric]);
  if(this.shadeKey===shadeKey){this.copyTo(context,view);this.lastFrameMs=performance.now()-started;return;}
  gl.viewport(0,0,w,h);
  if(this.key!==key||target<this.cursor){
   this.cursor=0;this.key=key;this.builds++;gl.clearColor(0,0,0,0);
   for(const f of this.fbos.slice(0,2)){gl.bindFramebuffer(gl.FRAMEBUFFER,f);gl.clear(gl.COLOR_BUFFER_BIT)}
  }
  const fabricKey=key+'|'+(view.texture||'twill');
  if(this.fabricKey!==fabricKey){
   gl.disable(gl.BLEND);gl.bindVertexArray(this.screenVao);gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbos[2]);this.uniforms(this.clothProgram,w,h,ppm,offset,view.threadWidth);
   gl.uniform1i(gl.getUniformLocation(this.clothProgram,'weaveKind'),Math.max(0,['twill','pique','knit','fleece','cap'].indexOf(view.texture||'twill')));
   gl.drawArrays(gl.TRIANGLES,0,3);this.fabricKey=fabricKey;
  }
  if(target>this.cursor){
   gl.bindVertexArray(this.vao);gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
   for(let i=0;i<2;i++){gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,4,gl.FLOAT,false,32,this.cursor*32+i*16);gl.vertexAttribDivisor(i,1)}
   gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbos[0]);this.uniforms(this.heightProgram,w,h,ppm,offset,view.threadWidth);gl.enable(gl.BLEND);gl.blendEquation(gl.FUNC_ADD);gl.blendFunc(gl.ONE,gl.ONE);gl.drawArraysInstanced(gl.TRIANGLES,0,6,target-this.cursor);
   gl.disable(gl.BLEND);gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbos[1]);this.uniforms(this.materialProgram,w,h,ppm,offset,view.threadWidth);gl.drawArraysInstanced(gl.TRIANGLES,0,6,target-this.cursor);this.cursor=target;
  }
  gl.bindVertexArray(this.screenVao);gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbos[3]);gl.disable(gl.BLEND);
  const p=this.lightProgram;this.uniforms(p,w,h,ppm,offset,view.threadWidth);
  ['heights','directions','colours','cloth'].forEach((name,i)=>{gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,this.textures[i]);gl.uniform1i(gl.getUniformLocation(p,name),i)});
  gl.activeTexture(gl.TEXTURE4);gl.bindTexture(gl.TEXTURE_2D,this.paletteTexture);gl.uniform1i(gl.getUniformLocation(p,'palette'),4);gl.uniform1f(gl.getUniformLocation(p,'paletteCount'),this.paletteCount);
  const angle=(view.lightAngle??225)*Math.PI/180;const light=view.neutralLight?[0,0,1]:[Math.cos(angle)*Math.SQRT1_2,Math.sin(angle)*Math.SQRT1_2,Math.SQRT1_2];
  gl.uniform3f(gl.getUniformLocation(p,'light'),...light);gl.uniform3f(gl.getUniformLocation(p,'fabric'),...hex(view.fabric||'#c2baa8'));
  gl.uniform1i(gl.getUniformLocation(p,'weaveKind'),Math.max(0,['twill','pique','knit','fleece','cap'].indexOf(view.texture||'twill')));gl.uniform1i(gl.getUniformLocation(p,'neutral'),!!view.neutralLight);
  gl.drawArrays(gl.TRIANGLES,0,3);
  // Resolve 2× supersampling on the GPU, avoiding a large CPU canvas resample.
  gl.bindFramebuffer(gl.READ_FRAMEBUFFER,this.fbos[3]);gl.readBuffer(gl.COLOR_ATTACHMENT0);gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
  gl.blitFramebuffer(0,0,w,h,0,0,view.width,view.height,gl.COLOR_BUFFER_BIT,gl.LINEAR);
  // Leave neither read nor draw FBO attached when another canvas consumes us.
  gl.bindFramebuffer(gl.FRAMEBUFFER,null);
  if(gl.getError()!==gl.NO_ERROR)throw Error('Graphics driver rejected the thread surface');
  this.shadeKey=shadeKey;this.copyTo(context,view);
  this.lastFrameMs=performance.now()-started;
 }
 copyTo(context,view){
  context.save();context.setTransform(1,0,0,1,0,0);context.imageSmoothingEnabled=true;context.imageSmoothingQuality='high';context.drawImage(this.canvas,0,0,view.width,view.height);context.restore();
 }
}
window.ThreadSurface=ThreadSurface;
})();
