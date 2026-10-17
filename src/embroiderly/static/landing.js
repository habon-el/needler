/* Read-only sample. No artwork mutation, upload or stitch generation requests. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),canvas=$('demoCanvas'),ctx=canvas.getContext('2d');
 const layer=new window.StitchLayer(),art=new Image();
 let plan=null,loading=false,stage='artwork',colour='#126957',position=0,playing=false,frame=0,last=0;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const words={artwork:'ARTWORK',plan:'THREAD PLAN',stitches:'STITCHES'};
 function pause(){playing=false;cancelAnimationFrame(frame);$('demoPlay').textContent=position>=100?'Replay stitches':'Play stitches';}
 function draw(){
  const width=canvas.width,height=canvas.height;ctx.clearRect(0,0,width,height);
  const scale=Math.min(width/740,height/320),x=(width-640*scale)/2,y=(height-240*scale)/2;
  if(stage==='artwork'||stage==='plan'){
   if(art.complete&&art.naturalWidth){ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);ctx.drawImage(art,0,0);if(stage==='plan'){ctx.globalCompositeOperation='source-in';ctx.fillStyle=colour;ctx.fillRect(0,0,640,240)}ctx.restore()}
  }else if(plan){
   layer.paint(ctx,plan,Math.floor(plan.steps.length*position/100),{width,height,s:scale,x,y,factor:240/plan.height_mm,threadWidth:.375,relief:true,colourMap:Object.fromEntries(plan.colors.map(c=>[c,colour]))});
  }
  $('demoProgress').value=position;$('demoPercent').value=Math.round(position)+'%';
 }
 function chooseStage(value){
  pause();stage=value;
  document.querySelectorAll('[data-stage]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.stage===stage)));
  $('demoMode').textContent=words[stage];$('demoPlayback').hidden=stage!=='stitches';$('demoColourControls').hidden=stage==='artwork';
  $('demoFacts').textContent=stage==='artwork'?'Original sample artwork':stage==='plan'?'1 thread colour · transparent background':plan?`${plan.stitch_count.toLocaleString()} stitches · ${plan.trim_count} trims`:'Sample not loaded';
  $('demoStatus').textContent=stage==='artwork'?'This sample uses lettering on a transparent background.':stage==='plan'?'Only the lettering receives thread. The colour buttons change this demo, not your designs.':'Actual PES-readback path. Jumps and trims are not drawn as stitches. Sew-out still required.';
  draw();if(stage==='stitches'&&!plan)loadPlan();
 }
 async function loadPlan(){
  if(loading||plan)return;loading=true;$('demoRetry').hidden=true;$('demoStatus').textContent='Loading the saved stitch sample…';
  try{
   const response=await fetch('/static/landing/hello-plan.json',{signal:AbortSignal.timeout(15000)});
   if(!response.ok)throw Error('Sample unavailable');
   const data=await response.json();if(!Array.isArray(data.steps)||!data.steps.length||!Array.isArray(data.colors))throw Error('Invalid sample');
   plan=data;$('demoPlay').disabled=false;$('demoProgress').disabled=false;chooseStage(stage);
  }catch(error){$('demoStatus').textContent='The stitch sample could not load. Your designs are unaffected. Retry or open the studio.';$('demoRetry').hidden=false;}
  finally{loading=false;}
 }
 function tick(now){
  if(!playing)return;const elapsed=Math.min(now-last,100);last=now;position=Math.min(100,position+elapsed/90);draw();
  if(position>=100){pause();$('demoStatus').textContent='Sample complete. Open the studio to try your own artwork.';}else frame=requestAnimationFrame(tick);
 }
 $('demoPlay').addEventListener('click',()=>{
  if(!plan)return;if(playing){pause();return;}if(position>=100)position=0;
  // Reduced-motion visitors get the completed drawing, without animated travel.
  if(reduced.matches){position=100;draw();pause();$('demoStatus').textContent='Finished sample shown. Playback animation is off because reduced motion is enabled.';return;}
  playing=true;$('demoPlay').textContent='Pause stitches';last=performance.now();frame=requestAnimationFrame(tick);
 });
 $('demoProgress').addEventListener('input',()=>{position=Number($('demoProgress').value);pause();draw();});
 $('demoRetry').addEventListener('click',loadPlan);
 document.querySelectorAll('[data-stage]').forEach(b=>b.addEventListener('click',()=>chooseStage(b.dataset.stage)));
 document.querySelectorAll('[data-colour]').forEach(b=>b.addEventListener('click',()=>{colour=b.dataset.colour;document.querySelectorAll('[data-colour]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));draw();}));
 art.addEventListener('load',draw);art.addEventListener('error',()=>{$('demoStatus').textContent='Artwork preview unavailable. The saved stitch sample is available in step 3.';});art.src='/static/landing/hello.png';
 document.addEventListener('visibilitychange',()=>{if(document.hidden)pause()});
 reduced.addEventListener('change',()=>{if(reduced.matches)pause()});
 new ResizeObserver(()=>{const box=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(box.width*dpr);canvas.height=Math.round(box.height*dpr);draw()}).observe(canvas);
})();
