/* Guides, grid and snap on the design canvas (canvas_guides.py). A guide is a line across (axis y)
   or down (axis x) at a position in mm from the hoop centre, like piece positions. Guides are saved
   with the design (preparation option canvas_guides) on their own route, with no new preview: they
   never change stitches. Snap and the grid step are per-browser preferences. */
(() => {
 'use strict';
 // Snapping math in mm, kept free of the page so tests can run it.
 const Snap={
  // The shift that puts the closest of `values` on the closest target within `tolerance`, else 0.
  offset(values,targets,tolerance){
   let best=0,distance=Infinity;
   for(const v of values)for(const t of targets){const d=t-v;if(Math.abs(d)<=tolerance&&Math.abs(d)<distance){best=d;distance=Math.abs(d)}}
   return best;
  },
  // Lines on one axis: the hoop centre line and the guides; with a grid, the grid line nearest each value.
  axis(values,axis,{guides=[],grid=0,tolerance}){
   const targets=[0,...guides.filter(g=>g.axis===axis).map(g=>g.mm)];
   if(grid>0)for(const v of values)targets.push(Math.round(v/grid)*grid);
   return Snap.offset(values,targets,tolerance);
  },
  point([x,y],settings){return [x+Snap.axis([x],'x',settings),y+Snap.axis([y],'y',settings)]},
  // A moved box (centre and size in mm): its left, centre or right edge, and top, centre or bottom, snap.
  move(box,dx,dy,settings){
   const xs=[-1,0,1].map(k=>box.x_mm+dx+k*box.width_mm/2),ys=[-1,0,1].map(k=>box.y_mm+dy+k*box.height_mm/2);
   return [dx+Snap.axis(xs,'x',settings),dy+Snap.axis(ys,'y',settings)];
  }
 };
 if(typeof window==='undefined'){module.exports=Snap;return}
 const studio=window.embroideryStudio,$=id=>document.getElementById(id),canvas=$('prepared');
 if(!studio||!canvas||window.nativeTextConfig)return;
 const MAX=20,LIMIT=500,SNAP_PX=6,EDGE_PX=8,HIT_PX=5;
 let guides=[],report=studio.pieceReport()||null,scale=1,drag=null,saving=null,waiting=false;
 const remembered=(key,fallback)=>{try{return localStorage.getItem(key)??fallback}catch(_){return fallback}};
 let snap=remembered('needler.snap','off')==='on',grid=Number(remembered('needler.grid','0'))||0;
 const ready=()=>!!(report&&report.scale&&report.origin_mm);
 const settings=(skip=-1)=>({guides:guides.filter((_,i)=>i!==skip),grid,tolerance:SNAP_PX/scale*report.scale});
 const toMm=(p,axis)=>axis==='x'?p[0]*report.scale-report.origin_mm[0]:p[1]*report.scale-report.origin_mm[1];
 const toPixel=(mm,axis)=>(mm+report.origin_mm[axis==='x'?0:1])/report.scale;
 // Hooks used by piece-panel.js: drawing points (picture pixels) and drag-to-move (mm).
 window.snapPoint=p=>{
  if(!snap||!ready())return p;
  const [x,y]=Snap.point([toMm(p,'x'),toMm(p,'y')],settings());
  return [toPixel(x,'x'),toPixel(y,'y')];
 };
 window.snapMove=(box,dx,dy)=>snap&&ready()&&box?Snap.move(box,dx,dy,settings()):[dx,dy];

 const box=document.createElement('fieldset');box.id='canvasGuides';
 box.innerHTML=`<legend>Guides and snap</legend><div class="piece-arrange" role="group" aria-label="Add a guide">
 <button type="button" data-guide="y" title="A line across. Drag it on the canvas, or drag one in from the top edge.">+ Across</button><button type="button" data-guide="x" title="A line down. Drag it on the canvas, or drag one in from the left edge.">+ Down</button></div>
 <div id="guideList"></div>
 <div class="piece-arrange"><label class="piece-repeat-check" title="Moving and drawing pieces lock onto guides, the hoop centre lines and the grid"><input id="guideSnap" type="checkbox"> Snap</label>
 <label>Grid <select id="guideGrid"><option value="0">Off</option><option value="1">1 mm</option><option value="5">5 mm</option><option value="10">10 mm</option></select></label></div>
 <p id="guideNote" class="muted" role="status"></p>`;
 (document.querySelector('.piece-properties #pieceDraw')||{after:()=>{}}).after(box);
 const list=box.querySelector('#guideList'),note=box.querySelector('#guideNote');
 box.querySelector('#guideSnap').checked=snap;box.querySelector('#guideGrid').value=String(grid);
 const inches=()=>document.documentElement.dataset.units==='in';
 const shown=mm=>(mm/(inches()?25.4:1)).toFixed(inches()?3:1);
 function render(){
  list.replaceChildren(...guides.map((g,i)=>{
   const row=document.createElement('div');row.className='piece-repeat-row';
   const label=document.createElement('label');label.textContent=(g.axis==='y'?'Across · Y ':'Down · X ')+(inches()?'in':'mm');
   const input=document.createElement('input');input.inputMode='decimal';input.value=shown(g.mm);
   input.setAttribute('aria-label',label.textContent);
   input.onchange=()=>{
    const value=Number(input.value.replace(',','.'))*(inches()?25.4:1);
    if(!Number.isFinite(value)||Math.abs(value)>LIMIT){note.textContent=`Use a position within ${LIMIT} mm of the hoop centre.`;input.value=shown(g.mm);return}
    g.mm=Math.round(value*10)/10;keep();
   };
   const remove=document.createElement('button');remove.type='button';remove.textContent='✕';remove.title='Remove this guide';
   remove.setAttribute('aria-label','Remove guide');remove.onclick=()=>{guides.splice(i,1);keep()};
   label.append(input);row.append(label,remove);return row;
  }));
  box.querySelectorAll('[data-guide]').forEach(b=>b.disabled=guides.length>=MAX);
 }
 // Save after a short pause; while the studio is busy the save waits for its preview.
 function keep(){
  render();studio.redraw();note.textContent='';
  clearTimeout(saving);saving=setTimeout(async()=>{
   try{waiting=!await studio.keepGuides(guides.map(g=>({axis:g.axis,mm:g.mm})))}
   catch(error){note.textContent=error.message}
  },300);
 }
 function add(axis,mm=0){
  if(guides.length>=MAX){note.textContent=`Keep up to ${MAX} guides.`;return -1}
  guides.push({axis,mm});keep();return guides.length-1;
 }
 box.querySelectorAll('[data-guide]').forEach(b=>b.onclick=()=>add(b.dataset.guide));
 box.querySelector('#guideSnap').onchange=e=>{snap=e.target.checked;try{localStorage.setItem('needler.snap',snap?'on':'off')}catch(_){}};
 box.querySelector('#guideGrid').onchange=e=>{grid=Number(e.target.value)||0;try{localStorage.setItem('needler.grid',String(grid))}catch(_){}studio.redraw()};
 const load=()=>{if(drag)return;const saved=studio.snapshot().canvas_guides;guides=Array.isArray(saved)?saved.map(g=>({...g})):[];render()};
 window.addEventListener('studio:controls',()=>{load();studio.redraw()});
 window.addEventListener('studio:preview',e=>{report=e.detail.report?.piece_layout||null;if(waiting){waiting=false;keep()}});
 new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:['data-units']});
 load();

 // Drag a guide on the canvas, or a new one in from the top or left edge; drop it off the canvas to remove it.
 // Listening on the canvas's parent (capture) runs before the piece and tool handlers on the canvas.
 const area=canvas.parentElement;
 area.addEventListener('pointerdown',e=>{
  if(e.button!==0||!ready()||$('tool').value==='measure'||studio.navigationGesture(e)||studio.isBusy())return;
  const rect=canvas.getBoundingClientRect(),p=studio.piecePoint(e,canvas);
  if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)return;
  let index=guides.findIndex(g=>Math.abs((g.axis==='x'?p[0]:p[1])-toPixel(g.mm,g.axis))*scale<=HIT_PX);
  if(index<0&&e.clientY-rect.top<=EDGE_PX)index=add('y',Math.round(toMm(p,'y')*10)/10);
  else if(index<0&&e.clientX-rect.left<=EDGE_PX)index=add('x',Math.round(toMm(p,'x')*10)/10);
  if(index<0)return;
  e.stopPropagation();e.preventDefault();
  drag={index,before:guides[index].mm,pointer:e.pointerId};area.setPointerCapture(e.pointerId);
 },true);
 area.addEventListener('pointermove',e=>{
  if(!drag)return;e.stopPropagation();
  const g=guides[drag.index];let mm=toMm(studio.piecePoint(e,canvas),g.axis);
  if(snap)mm+=Snap.axis([mm],g.axis,settings(drag.index));
  g.mm=Math.max(-LIMIT,Math.min(LIMIT,Math.round(mm*10)/10));
  note.textContent=(g.axis==='y'?'Y ':'X ')+shown(g.mm)+(inches()?' in':' mm');studio.redraw();
 },true);
 area.addEventListener('pointerup',e=>{
  if(!drag)return;e.stopPropagation();
  const rect=canvas.getBoundingClientRect(),{index}=drag;drag=null;
  if(area.hasPointerCapture(e.pointerId))area.releasePointerCapture(e.pointerId);
  if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom){guides.splice(index,1);keep();note.textContent='Guide removed.'}
  else keep();
 },true);
 const cancel=()=>{if(drag){guides[drag.index].mm=drag.before;drag=null;render();studio.redraw()}};
 area.addEventListener('pointercancel',cancel,true);area.addEventListener('lostpointercapture',cancel,true);

 window.CanvasGuides={Snap,paint(c,s){
  scale=s;if(!ready()||(!guides.length&&!grid))return;
  // The visible part of the canvas in picture pixels.
  const m=c.getTransform(),left=-m.e/m.a,top=-m.f/m.d,right=(c.canvas.width-m.e)/m.a,bottom=(c.canvas.height-m.f)/m.d;
  c.save();c.lineWidth=1/s;
  const step=grid/report.scale;
  if(grid&&step*s>=6){
   c.strokeStyle='rgba(120,130,140,.22)';c.beginPath();
   for(let k=Math.ceil(toMm([left,0],'x')/grid);k*grid<=toMm([right,0],'x');k++){const x=toPixel(k*grid,'x');c.moveTo(x,top);c.lineTo(x,bottom)}
   for(let k=Math.ceil(toMm([0,top],'y')/grid);k*grid<=toMm([0,bottom],'y');k++){const y=toPixel(k*grid,'y');c.moveTo(left,y);c.lineTo(right,y)}
   c.stroke();
  }
  c.strokeStyle='#d0308a';c.beginPath();
  for(const g of guides){const v=toPixel(g.mm,g.axis);if(g.axis==='x'){c.moveTo(v,top);c.lineTo(v,bottom)}else{c.moveTo(left,v);c.lineTo(right,v)}}
  c.stroke();c.restore();
 }};
})();
