/* 3D stitch viewer and review. Reads the exported needle path (playback) and
   draws each sewn stitch as a raised thread over fabric, stacked in sewing
   order. Read-only: it never changes stitches, colours or machine files. */
(() => {
'use strict';
const TUBE_VS=`#version 300 es
precision highp float;
layout(location=0) in vec2 mesh;
layout(location=1) in vec4 ends;
layout(location=2) in vec4 lift;
layout(location=3) in vec4 ink;
uniform mat4 viewProj;uniform float radius;uniform int marked;
out vec3 vNormal,vTangent,vColour,vWorld;out float vAlong,vAround,vMark;
void main(){
 float u=mesh.x,ang=mesh.y*6.28318530718;
 vec2 d=ends.zw-ends.xy;float len=max(length(d),1e-4);vec2 t2=d/len;
 float z=u<.5?mix(lift.x,lift.y,u*2.):mix(lift.y,lift.z,u*2.-1.);
 z+=radius*.45*sin(3.14159265*u)*min(1.,len/1.2)+lift.w*pow(sin(3.14159265*u),.55);
 float slope=lift.w*.55*3.14159265*cos(3.14159265*u)*pow(max(sin(3.14159265*u),.02),-.45)/len;
 vec3 t=normalize(vec3(t2,(lift.z-lift.x)/len+slope));
 vec3 side=vec3(-t2.y,t2.x,0.),up=normalize(cross(t,side));
 float pinch=mix(.45,1.,smoothstep(0.,min(.5,.25/len),u)*smoothstep(0.,min(.5,.25/len),1.-u));
 vec3 n=normalize(cos(ang)*side/1.15+sin(ang)*up/.8);
 vWorld=vec3(mix(ends.xy,ends.zw,u),z)+(side*cos(ang)*radius*1.15+up*sin(ang)*radius*.8)*pinch;
 vNormal=n;vTangent=t;vColour=ink.rgb;vAlong=u*len+ink.a*3.;vAround=mesh.y;
 vMark=gl_InstanceID==marked?1.:0.;
 gl_Position=viewProj*vec4(vWorld,1);
}`;
const TUBE_FS=`#version 300 es
precision highp float;
in vec3 vNormal,vTangent,vColour,vWorld;in float vAlong,vAround,vMark;
uniform vec3 light,eye;out vec4 result;
void main(){
 vec3 n=normalize(vNormal),t=normalize(vTangent),l=normalize(light),v=normalize(eye-vWorld);
 float lambert=max(dot(n,l),0.);
 float tl=dot(t,l),tv=dot(t,v);
 float sheen=pow(max(0.,sqrt(max(0.,1.-tl*tl))*sqrt(max(0.,1.-tv*tv))-tl*tv),36.);
 float twist=.5+.5*cos(6.2831853*(vAlong/.45+vAround*2.));
 float under=smoothstep(-.7,.5,n.z);
 vec3 c=vColour*(.32+.68*lambert)*(.62+.38*under)*(.88+.12*twist)+vec3(.3)*sheen*(.55+.45*twist)*under;
 c=mix(c,vec3(1.,.12,.08),vMark*.7);
 result=vec4(c,1);
}`;
const CLOTH_VS=`#version 300 es
precision highp float;
layout(location=0) in vec2 corner;
uniform mat4 viewProj;uniform vec4 bounds;out vec2 vPos;
void main(){vPos=mix(bounds.xy,bounds.zw,corner);gl_Position=viewProj*vec4(vPos,-.01,1);}`;
const CLOTH_FS=`#version 300 es
precision highp float;
in vec2 vPos;uniform vec3 light,fabric;uniform sampler2D stack;uniform vec4 grid;uniform float visible;
out vec4 result;
const float TAU=6.28318530718;
float weave(vec2 p){return .5+.25*sin(TAU*(p.x+p.y)/.6)+.25*cos(TAU*p.x/.32)*cos(TAU*p.y/.32);}
float covered(vec2 p){
 vec2 uv=(p-grid.xy)/grid.zw;if(any(lessThan(uv,vec2(0)))||any(greaterThan(uv,vec2(1))))return 0.;
 vec2 s=texture(stack,uv).rg;return s.g<visible?s.r:0.;
}
void main(){
 vec2 shift=-normalize(light.xy+1e-5)*.25;float shade=0.;
 for(int i=-1;i<=1;i++)for(int j=-1;j<=1;j++)shade+=covered(vPos+shift+vec2(i,j)*.18);
 shade=clamp(shade/9.*1.6,0.,.45);
 float w=weave(vPos);
 vec3 c=fabric*(.78+.22*max(light.z,0.))*(.9+.1*w)*(1.-shade);
 result=vec4(c,1);
}`;
const LINE_VS=`#version 300 es
precision highp float;
layout(location=0) in vec3 position;layout(location=1) in float step;layout(location=2) in float along;
uniform mat4 viewProj;uniform float pointSize;out float vStep,vAlong;
void main(){vStep=step;vAlong=along;gl_Position=viewProj*vec4(position,1);gl_PointSize=pointSize;}`;
const LINE_FS=`#version 300 es
precision highp float;
in float vStep,vAlong;uniform float visible;uniform vec4 colour;uniform bool dashed,round;out vec4 result;
void main(){
 if(vStep>=visible)discard;
 if(dashed&&fract(vAlong/1.2)>.55)discard;
 if(round&&length(gl_PointCoord-.5)>.5)discard;
 result=colour;
}`;
function shader(gl,vs,fs){
 const p=gl.createProgram();
 for(const [type,code] of [[gl.VERTEX_SHADER,vs],[gl.FRAGMENT_SHADER,fs]]){
  const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const m=gl.getShaderInfoLog(s);gl.deleteShader(s);throw Error(m)}
  gl.attachShader(p,s);gl.deleteShader(s);
 }
 gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));
 const uniforms={};for(let i=0;i<gl.getProgramParameter(p,gl.ACTIVE_UNIFORMS);i++){const n=gl.getActiveUniform(p,i).name;uniforms[n]=gl.getUniformLocation(p,n)}
 return {p,u:uniforms};
}
const rgb=c=>[1,3,5].map(i=>parseInt(String(c).slice(i,i+2),16)/255||0);
function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2),r=1/(near-far);return [f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*r,-1,0,0,2*far*near*r,0]}
function lookAt(e,t,up){
 const z=norm(sub(e,t)),x=norm(cross(up,z)),y=cross(z,x);
 return [x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,e),-dot(y,e),-dot(z,e),1];
}
function mul(a,b){const o=new Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o}
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const l=Math.hypot(...a)||1;return a.map(v=>v/l)};

/* Geometry: one instance per sewn stitch. Each grid cell counts the threads
   that passed it; a new stitch rests on that many compressed layers, so
   underlay lifts top stitching and crossings sit on each other, while
   side-by-side satin and fill rows stay flat. */
function build(plan,colourMap,radius){
 const steps=plan.steps,ox=plan.origin_mm?.[0]||0,oy=plan.origin_mm?.[1]||0;
 const P=s=>[s.x+ox,-(s.y+oy)];
 // 3D puff: stitches of these threads sew over foam of this thickness.
 const puff=new Set(plan.puff?.threads||[]),foam=Number(plan.puff?.foam_mm)||0;let thread=0;
 let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
 for(const s of steps){if(s.t==='end'||s.t==='unknown')continue;const [x,y]=P(s);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y)}
 if(!isFinite(minX)){minX=minY=0;maxX=maxY=10}
 const pad=2,span=Math.max(maxX-minX,maxY-minY)+2*pad,cell=Math.max(.08,span/1400);
 const gx=minX-pad,gy=minY-pad,W=Math.ceil((maxX-minX+2*pad)/cell)+1,H=Math.ceil((maxY-minY+2*pad)/cell)+1;
 const count=new Uint16Array(W*H),stamp=new Int32Array(W*H).fill(-1),first=new Float32Array(W*H).fill(1e9),raised=new Float32Array(W*H);
 const layer=radius*1.6*.8,ends=[],lifts=[],inks=[],instanceStep=[],layers=[],lengths=[];
 // Thread compresses as it piles up: three layers at full height, then 40%.
 const lift=c=>layer*(c<=3?c:3+(c-3)*.4);
 // The previous stitch shares this stitch's needle hole by construction; it is not underneath.
 let previous=-1;
 const read=(x,y)=>{const i=Math.round((x-gx)/cell),j=Math.round((y-gy)/cell);let c=0;for(let a=-1;a<=1;a++)for(let b=-1;b<=1;b++){const u=i+a,v=j+b;if(u>=0&&v>=0&&u<W&&v<H){const idx=v*W+u;c=Math.max(c,count[idx]-(stamp[idx]===previous?1:0))}}return c};
 const jumps=[],trims=[];let jumpAlong=0;
 for(let k=0;k<steps.length;k++){
  const s=steps[k],prior=k?steps[k-1]:{x:0,y:0};
  const a=P(prior),b=P(s);
  if(s.t==='jump'){const len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len>.05){const arc=Math.min(4,.15*len+.6);for(let i=0;i<8;i++){for(const q of [i,i+1]){const u=q/8;jumps.push(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u,.4+arc*Math.sin(Math.PI*u),k,jumpAlong+u*len)}}jumpAlong+=len}continue}
  if(s.t==='color_change'){thread++;continue}
  if(s.t==='trim'){trims.push(b[0],b[1],lift(read(b[0],b[1]))+.5,k,0);continue}
  if(s.t!=='stitch')continue;
  const len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<.01)continue;
  const n=Math.max(2,Math.ceil(len/(cell*.6))),c=[];
  for(let i=0;i<=n;i++)c.push(read(a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n));
  const third=Math.max(1,Math.floor(n/3)),max=r=>Math.max(...c.slice(r[0],r[1]+1));
  const cA=max([0,third]),cM=max([third,n-third]),cB=max([n-third,n]),[zA,zM,zB]=[cA,cM,cB].map(lift),rz=radius*.8;
  // Satin across the foam domes up; short perforation and travel stitches lie at its pressed edge.
  const dome=puff.has(thread)?(len>=1.3?foam*.85:foam*.12):0;
  for(let i=0;i<=n;i++){
   const u=i/n,x=a[0]+(b[0]-a[0])*u,y=a[1]+(b[1]-a[1])*u,ci=Math.round((x-gx)/cell),cj=Math.round((y-gy)/cell);
   if(ci>=0&&cj>=0&&ci<W&&cj<H){const idx=cj*W+ci;if(stamp[idx]!==k){stamp[idx]=k;count[idx]=Math.min(65000,count[idx]+1)}first[idx]=Math.min(first[idx],k);
    if(dome)raised[idx]=Math.max(raised[idx],dome*Math.pow(Math.sin(Math.PI*u),.55))}
  }
  previous=k;
  ends.push(a[0],a[1],b[0],b[1]);lifts.push(zA+rz,zM+rz,zB+rz,dome);
  const ink=rgb(colourMap?.[s.color]||s.color||'#333333');inks.push(ink[0],ink[1],ink[2],(k*.618)%1);
  instanceStep.push(k);layers.push(cM+1);lengths.push(len);
 }
 const height=new Float32Array(W*H),stack=new Float32Array(W*H*2);for(let i=0;i<W*H;i++){height[i]=(count[i]?lift(count[i]):0)+raised[i];stack[2*i]=height[i];stack[2*i+1]=first[i]}
 return {ends:new Float32Array(ends),lifts:new Float32Array(lifts),inks:new Float32Array(inks),instanceStep,layers,lengths,
  jumps:new Float32Array(jumps),trims:new Float32Array(trims),stack,W,H,grid:[gx,gy,W*cell,H*cell],cell,height,
  bounds:[minX,minY,maxX,maxY],count:instanceStep.length};
}

/* Review findings: existing route checks plus thick thread stacks seen in 3D. */
function findings(plan,geo,radius){
 const out=[],ox=plan.origin_mm?.[0]||0,oy=plan.origin_mm?.[1]||0;
 const at=k=>{const s=plan.steps[k],p=k?plan.steps[k-1]:s;return [(s.x+p.x)/2+ox,-((s.y+p.y)/2+oy)]};
 for(const f of (window.RouteReview?.analyze(plan).flags||[])){
  const long=/^Long/.test(f.reason);
  out.push({step:f.index,kind:long?'long':'repeat',title:long?`Long stitch · ${f.length.toFixed(1)} mm`:'Repeated pass (minor)',detail:long?f.reason:'The needle goes over the same stitch a third time. Usually deliberate retracing in line art or outlines; check it is not an accidental overlap.',where:at(f.index)});
 }
 const limit=7;
 for(let i=0;i<geo.count;i++){
  // Over foam, the tack-down, caps and zigzag underlay sit under the satin on purpose (4 more layers).
  if(geo.layers[i]<limit+(geo.lifts[4*i+3]>0?4:0)||geo.lengths[i]<1)continue;  // lock stitches pile up by design
  const k=geo.instanceStep[i],p=at(k);
  out.push({step:k,kind:'stack',title:`Thick build-up · ${geo.layers[i]} layers`,detail:'Many threads pile up here. It can feel hard, pucker the fabric or break needles. Check density, underlay and overlaps.',where:p});
 }
 // One marker per kind and neighbourhood, so a busy area reads as one place to check.
 const [x0,y0,x1,y1]=geo.bounds,size=Math.max(2,Math.max(x1-x0,y1-y0)/14),groups=new Map();
 out.sort((a,b)=>a.step-b.step);
 for(const f of out){
  const key=f.kind+':'+Math.floor(f.where[0]/size)+','+Math.floor(f.where[1]/size),g=groups.get(key);
  if(g){g.count++;g.steps.push(f.step);continue}
  groups.set(key,{...f,count:1,steps:[f.step]});
 }
 // Long stitches and thick spots first; repeats are often deliberate retracing.
 const rank=f=>f.kind==='repeat'?1:0;
// One stitch over a knot is not a pile; a thick spot needs several stitches.
 return [...groups.values()].filter(g=>g.kind!=='stack'||g.count>1).map(g=>g.count>1?{...g,title:g.title.replace(/ · .*$/,'')+` · ${g.count} here`}:g).sort((a,b)=>rank(a)-rank(b)||a.step-b.step).slice(0,120);
}

class Thread3D {
 constructor(canvas){
  this.canvas=canvas;
  const gl=this.gl=canvas.getContext('webgl2',{antialias:true,preserveDrawingBuffer:true});
  if(!gl)throw Error('This computer’s browser has no WebGL2 graphics, so the 3D view is unavailable.');
  gl.getExtension('OES_texture_float_linear');
  this.tube=shader(gl,TUBE_VS,TUBE_FS);this.cloth=shader(gl,CLOTH_VS,CLOTH_FS);this.line=shader(gl,LINE_VS,LINE_FS);
  const grid=(segments,sides)=>{const v=[];for(let i=0;i<segments;i++)for(let j=0;j<sides;j++){const a=[i/segments,j/sides],b=[(i+1)/segments,j/sides],c=[i/segments,(j+1)/sides],d=[(i+1)/segments,(j+1)/sides];v.push(...a,...b,...c,...c,...b,...d)}return new Float32Array(v)};
  this.meshes={fine:grid(6,8),coarse:grid(3,5)};
  this.buffers={};for(const n of ['fine','coarse','ends','lifts','inks','cloth','jumps','trims','point'])this.buffers[n]=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers.fine);gl.bufferData(gl.ARRAY_BUFFER,this.meshes.fine,gl.STATIC_DRAW);
  gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers.coarse);gl.bufferData(gl.ARRAY_BUFFER,this.meshes.coarse,gl.STATIC_DRAW);
  gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers.cloth);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([0,0,1,0,0,1,0,1,1,0,1,1]),gl.STATIC_DRAW);
  this.stackTexture=gl.createTexture();this.geo=null;this.marked=-1;
  this.camera={yaw:-.35,pitch:.85,distance:100,target:[0,0,0]};
 }
 load(plan,colourMap,radius){
  const gl=this.gl,geo=this.geo=build(plan,colourMap,radius);this.radius=radius;
  const put=(name,data)=>{gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers[name]);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW)};
  put('ends',geo.ends);put('lifts',geo.lifts);put('inks',geo.inks);put('jumps',geo.jumps);put('trims',geo.trims);
  gl.bindTexture(gl.TEXTURE_2D,this.stackTexture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RG32F,geo.W,geo.H,0,gl.RG,gl.FLOAT,geo.stack);
  for(const [k,v] of [[gl.TEXTURE_MIN_FILTER,gl.NEAREST],[gl.TEXTURE_MAG_FILTER,gl.NEAREST],[gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE],[gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE]])gl.texParameteri(gl.TEXTURE_2D,k,v);
  this.mesh=geo.count>25000?'coarse':'fine';
  return geo;
 }
 frame(){if(!this.geo)return {centre:[0,0,0],size:10,width:10,height:10};const [x0,y0,x1,y1]=this.geo.bounds;return {centre:[(x0+x1)/2,(y0+y1)/2,0],size:Math.max(x1-x0,y1-y0,5),width:Math.max(x1-x0,2),height:Math.max(y1-y0,2)}}
 preset(name){
  // Fit the design's width and height to the viewport (vertical field of view 0.6 rad).
  const f=this.frame(),c=this.camera,aspect=this.canvas.clientWidth/Math.max(1,this.canvas.clientHeight),span=2*Math.tan(.3);
  c.target=f.centre;c.distance=Math.max(f.width*1.15/(span*aspect)*(name==='top'?1:1.45),f.height*1.25/span,6);
  if(name==='top'){c.yaw=0;c.pitch=Math.PI/2-.001}else if(name==='side'){c.yaw=-.2;c.pitch=.18}else{c.yaw=-.35;c.pitch=.85}
 }
 eye(){const c=this.camera,cp=Math.cos(c.pitch);return [c.target[0]+c.distance*cp*Math.sin(c.yaw),c.target[1]-c.distance*cp*Math.cos(c.yaw),c.target[2]+c.distance*Math.sin(c.pitch)]}
 matrix(){
  const w=this.canvas.width,h=this.canvas.height,c=this.camera;
  return mul(perspective(.6,w/Math.max(1,h),Math.max(.05,c.distance/200),c.distance*20),lookAt(this.eye(),c.target,[0,0,1]));
 }
 project(p){const m=this.matrix(),v=[p[0],p[1],p[2]||0,1],o=[0,0,0,0];for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[r]+=m[k*4+r]*v[k];if(o[3]<=0)return null;return [(o[0]/o[3]*.5+.5)*this.canvas.clientWidth,(.5-o[1]/o[3]*.5)*this.canvas.clientHeight]}
 heightAt(x,y){const g=this.geo;if(!g)return 0;const i=Math.round((x-g.grid[0])/g.cell),j=Math.round((y-g.grid[1])/g.cell);return i>=0&&j>=0&&i<g.W&&j<g.H?g.height[j*g.W+i]:0}
 render(state){
  const gl=this.gl,geo=this.geo,c=this.canvas,dpr=Math.min(2,window.devicePixelRatio||1);
  const w=Math.max(1,Math.round(c.clientWidth*dpr)),h=Math.max(1,Math.round(c.clientHeight*dpr));if(c.width!==w||c.height!==h){c.width=w;c.height=h}
  gl.viewport(0,0,w,h);const bg=state.background||[.12,.14,.15];gl.clearColor(bg[0],bg[1],bg[2],1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);
  if(!geo)return;
  let lo=0,hi=geo.count;while(lo<hi){const m=(lo+hi)>>1;if(geo.instanceStep[m]<state.cursor)lo=m+1;else hi=m}const visible=lo;
  const vp=this.matrix(),eye=this.eye(),angle=(state.lightAngle??225)*Math.PI/180,light=norm([Math.cos(angle)*.6,-Math.sin(angle)*.6,.8]);
  // Fabric with contact shadow from the sewn stack.
  const pad=Math.max(6,this.frame().size*.25),[x0,y0,x1,y1]=geo.bounds;
  gl.useProgram(this.cloth.p);gl.uniformMatrix4fv(this.cloth.u.viewProj,false,vp);gl.uniform4f(this.cloth.u.bounds,x0-pad,y0-pad,x1+pad,y1+pad);
  gl.uniform3fv(this.cloth.u.light,light);gl.uniform3fv(this.cloth.u.fabric,rgb(state.fabric||'#c2baa8'));gl.uniform4fv(this.cloth.u.grid,geo.grid);gl.uniform1f(this.cloth.u.visible,state.cursor);
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.stackTexture);gl.uniform1i(this.cloth.u.stack,0);
  for(let i=0;i<4;i++)gl.disableVertexAttribArray(i);
  gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers.cloth);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);gl.vertexAttribDivisor(0,0);
  gl.drawArrays(gl.TRIANGLES,0,6);
  // Threads.
  if(visible){
   gl.useProgram(this.tube.p);gl.uniformMatrix4fv(this.tube.u.viewProj,false,vp);gl.uniform1f(this.tube.u.radius,this.radius);
   gl.uniform3fv(this.tube.u.light,light);gl.uniform3fv(this.tube.u.eye,eye);gl.uniform1i(this.tube.u.marked,this.marked);
   gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers[this.mesh]);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);gl.vertexAttribDivisor(0,0);
   for(const [i,name,size] of [[1,'ends',4],[2,'lifts',4],[3,'inks',4]]){gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers[name]);gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,size,gl.FLOAT,false,0,0);gl.vertexAttribDivisor(i,1)}
   gl.drawArraysInstanced(gl.TRIANGLES,0,this.meshes[this.mesh].length/2,visible);
   for(let i=1;i<4;i++){gl.vertexAttribDivisor(i,0);gl.disableVertexAttribArray(i)}
  }
  // Jumps float above the fabric; trims and the needle are markers.
  gl.useProgram(this.line.p);gl.uniformMatrix4fv(this.line.u.viewProj,false,vp);gl.uniform1f(this.line.u.visible,state.cursor);
  const lines=(name,mode,count,colour,dashed,size)=>{if(!count)return;gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers[name]);
   gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,20,0);gl.enableVertexAttribArray(1);gl.vertexAttribPointer(1,1,gl.FLOAT,false,20,12);gl.enableVertexAttribArray(2);gl.vertexAttribPointer(2,1,gl.FLOAT,false,20,16);
   gl.uniform4fv(this.line.u.colour,colour);gl.uniform1i(this.line.u.dashed,dashed);gl.uniform1i(this.line.u.round,mode===gl.POINTS);gl.uniform1f(this.line.u.pointSize,size||1);gl.drawArrays(mode,0,count);
   for(let i=0;i<3;i++)gl.disableVertexAttribArray(i)};
  if(state.jumps)lines('jumps',gl.LINES,geo.jumps.length/5,[.95,.45,.05,1],true);
  if(state.trims)lines('trims',gl.POINTS,geo.trims.length/5,[.85,.1,.1,1],false,4.5*dpr);
  if(state.needle&&state.cursor<state.total&&state.cursor>0){
   const s=state.needlePoint;if(s){const top=this.heightAt(s[0],s[1]);
    gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers.point);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([s[0],s[1],top,-1,0,s[0],s[1],top+Math.max(4,this.frame().size*.12),-1,0]),gl.DYNAMIC_DRAW);
    lines('point',gl.LINES,2,[.92,.94,.96,1],false);lines('point',gl.POINTS,1,[1,1,1,1],false,6*dpr)}
  }
 }
 dispose(){this.gl.getExtension('WEBGL_lose_context')?.loseContext()}
}

/* Studio integration: a 3D button beside the view buttons, an overlay on the
   canvas, and a findings list. Playback, timeline and speed stay shared. */
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{
 const studio=window.embroideryStudio,$=id=>document.getElementById(id);
 const panels=document.querySelector('.panels'),viewbar=document.querySelector('.viewbar');
 if(!studio?.playbackView||!panels||!viewbar)return;
 const open=document.createElement('button');open.type='button';open.id='open3d';open.textContent='3D view';open.title='See the stitches as raised thread in 3D, and review problems';open.disabled=true;
 (viewbar.querySelector('[data-view=compare]')||viewbar.firstElementChild).after(open);
 const box=document.createElement('section');box.className='view3d';box.hidden=true;box.setAttribute('aria-label','3D stitch view');
 box.innerHTML=`<canvas aria-label="3D stitches. Drag to rotate, right-drag or Shift-drag to pan, scroll to zoom." tabindex="0"></canvas>
 <div class="view3d-bar" role="toolbar" aria-label="3D view">
  <button type="button" data-preset="tilted" aria-pressed="true">Tilted</button><button type="button" data-preset="top">Top</button><button type="button" data-preset="side">Side</button>
  <span class="view3d-sep"></span>
  <label><input type="checkbox" data-show="jumps" checked> Jumps</label><label><input type="checkbox" data-show="trims" checked> Cuts</label><label><input type="checkbox" data-show="needle" checked> Needle</label>
  <span class="view3d-sep"></span>
  <button type="button" data-action="review" aria-pressed="true">Review</button><button type="button" data-action="close" title="Back to the flat view (Esc)">Close 3D</button>
 </div>
 <aside class="view3d-review" aria-label="Stitch review"><h2>Stitch review</h2><p class="view3d-summary" role="status"></p><ol></ol></aside>
 <div class="view3d-labels" aria-hidden="true"></div>
 <p class="view3d-help">Drag to rotate · Right-drag or Shift-drag to pan · Scroll to zoom · Double-click to reset</p>
 <p class="view3d-error" role="alert" hidden></p>`;
 panels.append(box);
 const canvas=box.querySelector('canvas'),list=box.querySelector('ol'),labels=box.querySelector('.view3d-labels'),summary=box.querySelector('.view3d-summary');
 let reviewChosen=false,viewer=null,plan=null,colours='',width=0,items=[],dirty=true,frame=0,last=-1,active=-1;
 const show={jumps:true,trims:true,needle:true};
 const background=()=>{const v=getComputedStyle(document.documentElement).getPropertyValue('--ui-background').trim();const m=/^#([0-9a-f]{6})$/i.exec(v);return m?rgb(v):[.12,.14,.15]};
 function needlePoint(state){const s=state.plan.steps[Math.max(0,state.cursor-1)],o=state.plan.origin_mm||[0,0];return s?[s.x+o[0],-(s.y+o[1])]:null}
 function sync(){open.disabled=!studio.hasPlayback();if(open.disabled&&!box.hidden)close()}
 function load(state){
  plan=state.plan;colours=JSON.stringify(state.colourMap||{});width=state.threadWidth;
  const geo=viewer.load(plan,state.colourMap,Math.max(.08,(state.threadWidth||.375)/2));
  if(last<0)viewer.preset('tilted');
  items=findings(plan,geo,viewer.radius);
  const counts={long:0,repeat:0,stack:0};items.forEach(f=>counts[f.kind]+=f.count);
  const major=items.filter(f=>f.kind!=='repeat').length;
  summary.textContent=items.length?(major?`${major} place${major===1?'':'s'} to check (${counts.long} long stitches · ${counts.stack} thick spots)`:'No long stitches or thick spots found')+(counts.repeat?` · ${counts.repeat} repeated passes, usually deliberate`:'')+'. Click an item to fly there.':'No problems found by these checks. A sample sew-out is still needed.';
  list.replaceChildren(...items.map((f,i)=>{const li=document.createElement('li'),b=document.createElement('button');b.type='button';b.dataset.kind=f.kind;
   b.innerHTML=`<span class="view3d-num">${i+1}</span><span><strong></strong><small></small></span>`;b.querySelector('strong').textContent=f.title;b.querySelector('small').textContent=f.detail;
   b.onclick=()=>focus(i);li.append(b);return li}));
  labels.replaceChildren(...items.map((f,i)=>{const s=document.createElement('span');s.textContent=i+1;s.dataset.kind=f.kind;return s}));
  last=0;dirty=true;
 }
 function focus(i){
  const f=items[i];if(!f)return;active=i;
  list.querySelectorAll('button').forEach((b,j)=>b.setAttribute('aria-current',String(j===i)));
  const geo=viewer.geo;let lo=0,hi=geo.count;while(lo<hi){const m=(lo+hi)>>1;if(geo.instanceStep[m]<f.step)lo=m+1;else hi=m}
  viewer.marked=geo.instanceStep[lo]===f.step?lo:-1;
  studio.seek(f.step+1);
  const c=viewer.camera,from={...c,target:c.target.slice()},to={target:[f.where[0],f.where[1],0],distance:Math.max(6,viewer.frame().size*.12),pitch:.75,yaw:c.yaw};
  const t0=performance.now();const step=t=>{const k=Math.min(1,(t-t0)/450),e=k*(2-k);c.target=from.target.map((v,j)=>v+(to.target[j]-v)*e);c.distance=from.distance+(to.distance-from.distance)*e;c.pitch=from.pitch+(to.pitch-from.pitch)*e;dirty=true;if(k<1)requestAnimationFrame(step)};requestAnimationFrame(step);
 }
 function tick(){
  frame=0;if(box.hidden)return;
  const state=studio.playbackView();
  if(!state){close();return}
  if(state.plan!==plan||JSON.stringify(state.colourMap||{})!==colours||state.threadWidth!==width)load(state);
  if(state.cursor!==last){last=state.cursor;dirty=true}
  if(dirty){
   dirty=false;
   try{viewer.render({...state,total:state.plan.steps.length,...show,needlePoint:needlePoint(state),background:background()})}
   catch(e){fail(e);return}
   const shown=true;
   [...labels.children].forEach((s,i)=>{const f=items[i],p=shown&&f.kind!=='repeat'&&f.step<state.cursor?viewer.project([f.where[0],f.where[1],viewer.heightAt(f.where[0],f.where[1])+.3]):null;s.hidden=!p;if(p){s.style.transform=`translate(${p[0]}px,${p[1]}px)`;s.classList.toggle('is-active',i===active)}});
  }
  frame=requestAnimationFrame(tick);
 }
 function fail(error){const e=box.querySelector('.view3d-error');e.textContent=error.message||String(error);e.hidden=false}
 function show3d(){
  if(!studio.hasPlayback())return;
  box.hidden=false;open.setAttribute('aria-pressed','true');panels.classList.add('has-3d');
  if(!reviewChosen){const wide=box.clientWidth>=760;box.classList.toggle('review-hidden',!wide);box.querySelector('[data-action=review]').setAttribute('aria-pressed',String(wide))}
  try{viewer??=new Thread3D(canvas)}catch(e){fail(e);return}
  dirty=true;cancelAnimationFrame(frame);frame=requestAnimationFrame(tick);canvas.focus({preventScroll:true});
 }
 function close(){box.hidden=true;open.setAttribute('aria-pressed','false');panels.classList.remove('has-3d');cancelAnimationFrame(frame);frame=0}
 open.onclick=()=>box.hidden?show3d():close();
 box.querySelector('.view3d-bar').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.preset){viewer?.preset(b.dataset.preset);box.querySelectorAll('[data-preset]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));dirty=true}
  if(b.dataset.action==='close')close();
  if(b.dataset.action==='review'){reviewChosen=true;const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));box.classList.toggle('review-hidden',!on);dirty=true}
 });
 box.querySelectorAll('[data-show]').forEach(input=>input.onchange=()=>{show[input.dataset.show]=input.checked;dirty=true});
 // Orbit camera: left-drag rotates, right/Shift-drag pans, wheel zooms toward the target.
 let drag=null;
 canvas.addEventListener('contextmenu',e=>e.preventDefault());
 canvas.addEventListener('pointerdown',e=>{if(!viewer)return;canvas.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey||e.button===1}});
 canvas.addEventListener('pointermove',e=>{
  if(!drag||!viewer)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;const c=viewer.camera;
  if(drag.pan){const k=c.distance*.0016,s=Math.sin(c.yaw),co=Math.cos(c.yaw);c.target[0]-=(dx*co+dy*s*Math.sin(c.pitch))*k;c.target[1]-=(dx*s-dy*co*Math.sin(c.pitch))*k}
  else{c.yaw-=dx*.008;c.pitch=Math.max(.05,Math.min(Math.PI/2-.001,c.pitch+dy*.008))}
  box.querySelectorAll('[data-preset]').forEach(x=>x.setAttribute('aria-pressed','false'));dirty=true;
 });
 const end=()=>{drag=null};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
 canvas.addEventListener('wheel',e=>{if(!viewer)return;e.preventDefault();const c=viewer.camera,f=viewer.frame().size;c.distance=Math.max(2,Math.min(f*8,c.distance*Math.exp(e.deltaY*.0012)));dirty=true},{passive:false});
 canvas.addEventListener('dblclick',()=>{if(!viewer)return;viewer.preset('tilted');active=-1;viewer.marked=-1;dirty=true});
 canvas.addEventListener('keydown',e=>{
  if(!viewer)return;const c=viewer.camera,k={ArrowLeft:[-.08,0],ArrowRight:[.08,0],ArrowUp:[0,.06],ArrowDown:[0,-.06]}[e.key];
  if(k){c.yaw+=k[0];c.pitch=Math.max(.05,Math.min(Math.PI/2-.001,c.pitch+k[1]));dirty=true;e.preventDefault()}
  else if(e.key==='+'||e.key==='='){c.distance*=.85;dirty=true}else if(e.key==='-'){c.distance/=.85;dirty=true}
 });
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!box.hidden&&!(e.target instanceof Element&&e.target.closest('input,textarea,select'))){close();open.focus()}});
 new ResizeObserver(()=>{dirty=true}).observe(box);
 window.addEventListener('studio:stitch-state',sync);window.addEventListener('studio:preview',sync);
 window.addEventListener('studio:view',e=>{if(e.detail!=='stitched'&&!box.hidden)close()});
 sync();setInterval(sync,1500);
 window.Thread3D={open:show3d,close,viewer:()=>viewer,findings:()=>items};
});
if(typeof module!=='undefined')module.exports={build,findings};
})();
