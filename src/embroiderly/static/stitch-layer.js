/* Cache actual sewn paths in viewport pixels. Jumps/trims never draw thread. */
(() => {
'use strict';
class StitchLayer {
 constructor(){this.canvas=document.createElement('canvas');this.reset()}
 reset(){this.plan=null;this.key=null;this.cursor=0;this.processed=0;this.surface?.reset()}
 retry(){this.surface?.dispose();this.surface=null;this.surfaceError='';this.reset()}
 paint(context,plan,cursor,view){
  if(view.relief&&window.ThreadSurface&&!this.surfaceError){
   try{
    this.surface??=new window.ThreadSurface();this.surface.paint(context,plan,cursor,view);
    this.status='Realistic preview · sew a sample to check the result';return;
   }catch(error){this.surfaceError=error.message;this.surface?.dispose();this.surface=null;}
  }
  this.status=view.relief&&this.surfaceError?"Realistic preview isn't available on this computer, so you're seeing a flat preview.":'Flat stitch preview · lighting off';
  const key=JSON.stringify(view),target=Math.max(0,Math.min(plan.steps.length,cursor));
  const c=this.canvas;
  if(this.plan!==plan||this.key!==key||target<this.cursor){
   c.width=view.width;c.height=view.height;this.cursor=0;this.plan=plan;this.key=key;
  }
  const ink=c.getContext('2d'),factor=view.factor;
  ink.setTransform(view.s,0,0,view.s,view.x,view.y);
  ink.lineWidth=(view.threadWidth??.22)*factor;ink.lineCap='round';
  for(let i=this.cursor;i<target;i++){
   const step=plan.steps[i],prior=i?plan.steps[i-1]:{x:0,y:0};
   if(step.t==='stitch'){
    ink.lineWidth=(view.threadWidth??.22)*factor;
    ink.strokeStyle=view.colourMap?.[step.color]||step.color;ink.beginPath();
    ink.moveTo((prior.x+plan.origin_mm[0])*factor,(prior.y+plan.origin_mm[1])*factor);
    ink.lineTo((step.x+plan.origin_mm[0])*factor,(step.y+plan.origin_mm[1])*factor);
    ink.stroke();
   }
   this.processed++;
  }
  this.cursor=target;
  context.save();context.setTransform(1,0,0,1,0,0);context.drawImage(c,0,0);context.restore();
 }
}
window.StitchLayer=StitchLayer;
})();
