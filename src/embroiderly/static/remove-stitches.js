/* Remove stitches: click a part of the design to select that whole
   area, or drag to draw around any stitches, then Remove.
   Default: the area is erased from the design and the stitches are rebuilt
   around it (clean edges, tie-offs). "Exact cut" keeps every other stitch as
   it is (stitch_cuts.py). Both are saved with the design and undoable. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const studio=window.embroideryStudio;
 const bar=document.querySelector('.viewbar');
 if(!studio||!bar||window.nativeTextConfig)return;
 const open3d=document.getElementById('open3d');
 const tool=document.createElement('button');tool.type='button';tool.id='removeStitches';tool.textContent='Remove stitches';
 tool.title='Click a part to select it, or draw around stitches, then Remove';
 (open3d||bar.lastElementChild).after(tool);
 // selection: {points, holes} in picture pixels; screen points only while drawing.
 let overlay=null,target=null,selection=null,screen=[],drawing=false,panel=null,start=null;
 const say=text=>(window.studioStatus||(()=>{}))(text);
 const visibleCanvas=()=>[...document.querySelectorAll('canvas#stitched, canvas')].find(c=>c.offsetParent&&c.width>200&&!c.closest('.thread-3d'));
 const prepared=()=>{const m=(document.getElementById('exportPes')?.getAttribute('href')||'').match(/^\/studio-export\/([^/]+)\//);return m?decodeURIComponent(m[1]):null};
 function geometry(){
  const view=studio.playbackView(),size=studio.imageSize();
  if(!view||!size.height)return null;
  return {plan:view.plan,scale:(view.plan.height_mm||1)/size.height,origin:view.plan.origin_mm||[0,0]};
 }
 // Picture pixels -> overlay pixels, measured from the canvas's own mapping.
 function toScreen(){
  const r=target.getBoundingClientRect(),o=overlay.getBoundingClientRect();
  const a=studio.piecePoint({clientX:r.left,clientY:r.top},target),b=studio.piecePoint({clientX:r.left+100,clientY:r.top+100},target);
  const sx=100/(b[0]-a[0]),sy=100/(b[1]-a[1]);
  return p=>[(p[0]-a[0])*sx+r.left-o.left,(p[1]-a[1])*sy+r.top-o.top];
 }
 function ring(x,y,poly){let c=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const [xi,yi]=poly[i],[xj,yj]=poly[j];if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)c=!c}return c}
 const inside=(x,y,sel)=>ring(x,y,sel.points)&&!(sel.holes||[]).some(h=>ring(x,y,h));
 function count(sel){
  const g=geometry();if(!g)return {n:0,cuts:0};let n=0,cuts=0,prev=null,was=false;
  for(const s of g.plan.steps){
   const p=[(s.x+g.origin[0])/g.scale,(s.y+g.origin[1])/g.scale];
   if(s.t==='stitch'&&prev){const hit=inside((p[0]+prev[0])/2,(p[1]+prev[1])/2,sel);if(hit){n++;if(!was)cuts++}was=hit}
   else if(s.t!=='stitch')was=false;
   if(s.t==='stitch'||s.t==='jump')prev=p;
  }
  return {n,cuts};
 }
 function draw(){
  const c=overlay.getContext('2d');c.clearRect(0,0,overlay.width,overlay.height);
  const rings=selection?(m=>[selection.points,...(selection.holes||[])].map(r=>r.map(m)))(toScreen()):[screen];
  if(rings[0].length<2)return;
  c.beginPath();for(const r of rings){r.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath()}
  c.fillStyle='rgba(192,57,43,.22)';c.fill('evenodd');c.setLineDash([6,4]);c.strokeStyle='#c0392b';c.lineWidth=2;c.stroke();
 }
 function stop(){overlay?.remove();panel?.remove();overlay=panel=null;selection=null;screen=[];tool.classList.remove('active');document.removeEventListener('keydown',onKey)}
 function onKey(e){if(e.key==='Escape')stop()}
 function offer(){
  const {n,cuts}=count(selection);panel?.remove();
  panel=document.createElement('div');panel.className='remove-bar';
  const exactAllowed=!/photo|portrait/i.test(geometry()?.plan.engine||'');
  panel.innerHTML=`<span>${n?n.toLocaleString()+' stitches selected':'No stitches inside'}</span>
   ${exactAllowed?'<label title="Keep every other stitch exactly as it is"><input type="checkbox" id="removeExact"> Exact cut</label>':''}
   <span class="muted" id="removeCuts" hidden>adds about ${cuts} cut${cuts===1?'':'s'}</span>
   <button type="button" class="primary" id="removeApply" ${n?'':'disabled'}>Remove</button><button type="button" id="removeCancel">Cancel</button>`;
  overlay.parentElement.append(panel);
  // Exact cut ends every crossing row with a tie-off and a cut: say how many.
  panel.querySelector('#removeExact')?.addEventListener('change',e=>{panel.querySelector('#removeCuts').hidden=!e.target.checked});
  panel.querySelector('#removeCancel').onclick=stop;
  panel.querySelector('#removeApply').onclick=()=>{
   const round=r=>r.map(p=>[Math.round(p[0]*10)/10,Math.round(p[1]*10)/10]);
   const area={points:round(selection.points),...(selection.holes?.length?{holes:selection.holes.map(round)}:{})};
   const o=studio.snapshot(),exact=panel.querySelector('#removeExact')?.checked;
   const patch=exact?{stitch_cuts:[...(o.stitch_cuts||[]),area]}
    :{edits:[...(o.edits||[]),{kind:'erase',shape:'polygon',...area,radius:1,removed:true}]};
   stop();
   try{studio.acceptRefinement(patch);say('Removing stitches and checking again…')}
   catch(error){say(error.message)}
  };
 }
 async function pick(e){
  // A click selects the whole colour area under it, holes included.
  const name=prepared();if(!name)return;
  const [x,y]=studio.piecePoint(e,target);
  try{
   const data=await fetch(`/api/area-at/${encodeURIComponent(name)}?x=${x}&y=${y}`,{cache:'no-store'}).then(r=>r.json());
   if(!data.area){say('Nothing stitched there. Click a part of the design, or draw around stitches.');selection=null;draw();return}
   selection={points:data.area.points,holes:data.area.holes};draw();offer();
  }catch(_){say('That area could not be selected. Draw around it instead.')}
 }
 tool.addEventListener('click',()=>{
  if(overlay){stop();return}
  if(!studio.hasPlayback()){say('Make stitches first.');return}
  if(!visibleCanvas())studio.review('stitched');
  target=visibleCanvas();if(!target)return;
  const host=target.parentElement;if(getComputedStyle(host).position==='static')host.style.position='relative';
  overlay=document.createElement('canvas');overlay.className='remove-overlay';
  overlay.width=target.clientWidth;overlay.height=target.clientHeight;
  overlay.style.left=target.offsetLeft+'px';overlay.style.top=target.offsetTop+'px';
  overlay.style.width=target.clientWidth+'px';overlay.style.height=target.clientHeight+'px';
  host.append(overlay);tool.classList.add('active');document.addEventListener('keydown',onKey);
  say('Click a part to select it, or draw around stitches. Esc cancels.');
  overlay.addEventListener('pointerdown',e=>{panel?.remove();panel=null;drawing=true;selection=null;screen=[];start=[e.clientX,e.clientY];overlay.setPointerCapture(e.pointerId);add(e)});
  overlay.addEventListener('pointermove',e=>{if(drawing)add(e)});
  overlay.addEventListener('pointerup',e=>{
   drawing=false;
   if(Math.hypot(e.clientX-start[0],e.clientY-start[1])<5&&screen.length<4){screen=[];pick(e);return}
   if(screen.length<3){screen=[];draw();return}
   selection={points:drawn.slice(),holes:[]};offer();
  });
 });
 let drawn=[];
 function add(e){
  const r=overlay.getBoundingClientRect(),s=[e.clientX-r.left,e.clientY-r.top];
  const last=screen[screen.length-1];if(last&&Math.hypot(s[0]-last[0],s[1]-last[1])<4)return;
  if(!screen.length)drawn=[];
  screen.push(s);drawn.push(studio.piecePoint(e,target));draw();
 }
 // Only offered once stitches exist.
 const sync=()=>{tool.hidden=!studio.hasPlayback();if(tool.hidden)stop()};
 window.addEventListener('studio:preview',sync);setInterval(sync,1500);sync();
});
