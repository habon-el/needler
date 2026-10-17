/* Read-only route inspection. Never changes machine commands or thread colours. */
(() => {
'use strict';
function analyze(plan){
 const flags=[],seen=new Map();let jumps=0,stitches=0;
 const key=p=>`${Math.round(p.x*20)},${Math.round(p.y*20)}`;
 for(let i=0;i<plan.steps.length;i++){
  const s=plan.steps[i],p=i?plan.steps[i-1]:{x:0,y:0};
  const length=Math.hypot(s.x-p.x,s.y-p.y);
  if(s.t==='jump'){jumps++;continue}
  if(s.t!=='stitch')continue;
  stitches++;
  if(length>8)flags.push({index:i,length,reason:'Long sewn segment (>8 mm): inspect for an unwanted crossing.'});
  // Ignore tiny lock stitches. Repeated underlay can be intentional.
  if(length>=.5){
   const ends=[key(p),key(s)].sort(),id=s.color+':'+ends.join('|');
   const count=(seen.get(id)||0)+1;seen.set(id,count);
   if(count===3)flags.push({index:i,length,reason:'Third pass over the same segment (0.05 mm tolerance): check whether reinforcement is intended.'});
  }
 }
 return {flags,jumps,stitches};
}
function paint(ctx,plan,cursor,view,showDirections,showJumps){
 const end=Math.min(cursor,plan.steps.length),start=Math.max(0,end-60),scale=view.s;
 const point=s=>[(s.x+plan.origin_mm[0])*view.factor,(s.y+plan.origin_mm[1])*view.factor];
 ctx.save();ctx.lineWidth=1.5/scale;
 for(let i=start;i<end;i++){
  const s=plan.steps[i],p=i?plan.steps[i-1]:{x:0,y:0};
  if(!(s.t==='stitch'&&showDirections)&&!(s.t==='jump'&&showJumps))continue;
  const a=point(p),b=point(s),dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
  if(length*scale<4)continue;
  ctx.strokeStyle=s.t==='jump'?'#d25100':'#007bb8';
  ctx.setLineDash(s.t==='jump'?[4/scale,3/scale]:[]);
  if(s.t==='jump'){ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}
  ctx.setLineDash([]);
  const x=a[0]+dx*.7,y=a[1]+dy*.7,k=Math.min(5/scale,length*.3),ux=dx/length,uy=dy/length;
  ctx.beginPath();ctx.moveTo(x-k*ux-k*.5*uy,y-k*uy+k*.5*ux);ctx.lineTo(x,y);ctx.lineTo(x-k*ux+k*.5*uy,y-k*uy-k*.5*ux);ctx.stroke();
 }
 ctx.restore();
}
if(typeof module!=='undefined')module.exports={analyze};
if(typeof window!=='undefined')window.RouteReview={analyze,paint};
})();
